"""企微 OpenAPI 客户端：token 缓存与打卡/通讯录/审批/日报拉取（PRD §5 外部依赖）。

重试策略（ARCHITECTURE §9 / E20）：
- 网络/5xx → 指数退避重试 3 次（1s, 2s, 4s）
- 企微业务 errcode ≠ 0 → 不重试，快速失败
- token 过期 42001 → 清缓存后重试 1 次
"""
from __future__ import annotations

import time

import httpx

from attendance_audit_integration.config import settings
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)

# 企微 useridlist 单次上限（官方约 100）
_CHECKIN_USER_BATCH_SIZE = 100

# 重试参数
_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 1.0


def _retry_request(
    method: str,
    url: str,
    *,
    max_retries: int = _MAX_RETRIES,
    initial_backoff: float = _INITIAL_BACKOFF_SECONDS,
    **kwargs,
) -> httpx.Response:
    """带指数退避的 HTTP 请求包装器（E20 重试策略）。

    仅对网络异常和 HTTP 5xx 重试，业务错误不重试。
    """
    kwargs.setdefault("timeout", 15.0)
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            if method == "GET":
                resp = httpx.get(url, **kwargs)
            else:
                resp = httpx.post(url, **kwargs)

            if resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    "Server error %d" % resp.status_code,
                    request=resp.request,
                    response=resp,
                )
            return resp
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = initial_backoff * (2 ** attempt)
                logger.warning(
                    "HTTP %s %s attempt %d/%d failed (%s), retrying in %.1fs...",
                    method, url, attempt + 1, max_retries + 1, exc, wait,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "HTTP %s %s failed after %d attempts: %s",
                    method, url, max_retries + 1, exc,
                )

    raise last_exc  # type: ignore[misc]


class WeComAPIClient:
    def __init__(self) -> None:
        self.corpid = settings.WECOM_CORPID
        self.secret = settings.WECOM_SECRET
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    def get_access_token(self) -> str:
        """Fetch and cache the WeCom access token."""
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        params = {"corpid": self.corpid, "corpsecret": self.secret}

        response = _retry_request("GET", url, params=params, timeout=10.0)
        data = response.json()
        if data.get("errcode") == 0:
            self._access_token = data["access_token"]
            self._token_expires_at = now + float(data.get("expires_in", 7200)) - 200
            return self._access_token

        # Token expired mid-flight → clear cache (will be retried by caller)
        if data.get("errcode") == 42001:
            self._access_token = None
            self._token_expires_at = 0

        raise RuntimeError(
            "WeCom token fetch error: %s (code: %s)"
            % (data.get("errmsg"), data.get("errcode"))
        )

    def fetch_users(self, department_id: int = 1) -> list:
        """Fetch all employees from WeCom under the given department (recursive)."""
        token = self.get_access_token()
        url = "https://qyapi.weixin.qq.com/cgi-bin/user/list"
        params = {
            "access_token": token,
            "department_id": department_id,
            "fetch_child": 1,
        }

        try:
            response = _retry_request("GET", url, params=params)
            data = response.json()
            if data.get("errcode") == 0:
                return data.get("userlist", [])
            logger.error("Error fetching users: %s", data.get("errmsg"))
            return []
        except Exception as exc:
            logger.error("API exception in fetch_users: %s", exc)
            return []

    def fetch_punches(self, start_timestamp: int, end_timestamp: int, user_ids: list) -> list:
        """Fetch checkin logs; useridlist 按批拆分以防超限。"""
        if not user_ids:
            return []

        token = self.get_access_token()
        url = "https://qyapi.weixin.qq.com/cgi-bin/checkin/getcheckindata?access_token=%s" % token
        all_rows: list = []

        for offset in range(0, len(user_ids), _CHECKIN_USER_BATCH_SIZE):
            batch = user_ids[offset : offset + _CHECKIN_USER_BATCH_SIZE]
            payload = {
                "opencheckindatatype": 3,
                "starttime": start_timestamp,
                "endtime": end_timestamp,
                "useridlist": batch,
            }
            try:
                response = _retry_request("POST", url, json=payload)
                data = response.json()
                if data.get("errcode") == 0:
                    all_rows.extend(data.get("checkindata", []))
                else:
                    logger.error("Error fetching punches batch: %s", data.get("errmsg"))
            except Exception as exc:
                logger.error("API exception in fetch_punches: %s", exc)

        return all_rows

    def fetch_approval_ids(
        self,
        start_timestamp: int,
        end_timestamp: int,
        template_id: str | None = None,
        *,
        size: int = 100,
        max_pages: int = 20,
    ) -> list[str]:
        """按时间区间与可选模板 ID 分页拉取企微审批单号列表（/cgi-bin/oa/getapprovalinfo）。"""
        token = self.get_access_token()
        url = "https://qyapi.weixin.qq.com/cgi-bin/oa/getapprovalinfo?access_token=%s" % token
        cursor = 0
        seen: set[str] = set()
        sp_nos: list[str] = []

        for _ in range(max_pages):
            payload: dict = {
                "starttime": str(int(start_timestamp)),
                "endtime": str(int(end_timestamp)),
                "cursor": cursor,
                "size": min(max(int(size), 1), 100),
            }
            if template_id:
                payload["filters"] = [{"key": "template_id", "value": template_id}]

            try:
                response = _retry_request("POST", url, json=payload)
                data = response.json()
                if data.get("errcode") != 0:
                    logger.error(
                        "Error fetching approval ids (template=%s): %s (code=%s)",
                        template_id,
                        data.get("errmsg"),
                        data.get("errcode"),
                    )
                    break

                for sp_no in data.get("sp_no_list", []) or []:
                    if sp_no not in seen:
                        seen.add(sp_no)
                        sp_nos.append(sp_no)

                next_cursor = data.get("next_cursor")
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
            except Exception as exc:
                logger.error("API exception in fetch_approval_ids: %s", exc)
                break

        return sp_nos

    def fetch_approval_detail(self, approval_no: str) -> dict:
        """Fetch detail information for a specific approval form ID."""
        token = self.get_access_token()
        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/oa/getapprovaldetail?access_token=%s" % token
        )
        payload = {"sp_no": approval_no}

        try:
            response = _retry_request("POST", url, json=payload)
            data = response.json()
            if data.get("errcode") == 0:
                return data.get("info", {})
            logger.error("Error fetching approval %s: %s", approval_no, data.get("errmsg"))
            return {}
        except Exception as exc:
            logger.error("API exception in fetch_approval_detail: %s", exc)
            return {}

    def fetch_journal_record_list(
        self,
        start_timestamp: int,
        end_timestamp: int,
        template_id: str | None = None,
        *,
        limit: int = 100,
        max_pages: int = 20,
    ) -> list[str]:
        """官方汇报接口第一步：分页拉取汇报记录 UUID 列表（/cgi-bin/oa/journal/get_record_list）。"""
        token = self.get_access_token()
        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/oa/journal/get_record_list?access_token=%s"
            % token
        )
        cursor = 0
        seen: set[str] = set()
        uuids: list[str] = []

        for _ in range(max_pages):
            payload: dict = {
                "starttime": int(start_timestamp),
                "endtime": int(end_timestamp),
                "cursor": cursor,
                "limit": min(max(int(limit), 1), 100),
            }
            if template_id:
                payload["filters"] = [{"key": "template_id", "value": template_id}]

            try:
                response = _retry_request("POST", url, json=payload)
                data = response.json()
                if data.get("errcode") != 0:
                    logger.error(
                        "Error fetching journal record list (template=%s): %s (code=%s)",
                        template_id,
                        data.get("errmsg"),
                        data.get("errcode"),
                    )
                    break

                for uuid in data.get("journaluuid_list", []) or []:
                    if uuid not in seen:
                        seen.add(uuid)
                        uuids.append(uuid)

                if data.get("endflag") == 1:
                    break
                next_cursor = data.get("next_cursor")
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
            except Exception as exc:
                logger.error("API exception in fetch_journal_record_list: %s", exc)
                break

        return uuids

    def fetch_journal_record_detail(self, journaluuid: str) -> dict:
        """官方汇报接口第二步：按 journaluuid 拉取汇报详情（/cgi-bin/oa/journal/get_record_detail）。"""
        token = self.get_access_token()
        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/oa/journal/get_record_detail?access_token=%s"
            % token
        )
        payload = {"journaluuid": journaluuid}

        try:
            response = _retry_request("POST", url, json=payload)
            data = response.json()
            if data.get("errcode") == 0:
                return data.get("info", {})
            logger.error(
                "Error fetching journal detail %s: %s (code=%s)",
                journaluuid,
                data.get("errmsg"),
                data.get("errcode"),
            )
            return {}
        except Exception as exc:
            logger.error("API exception in fetch_journal_record_detail: %s", exc)
            return {}

    def fetch_daily_reports(
        self,
        start_timestamp: int,
        end_timestamp: int,
        template_ids: list[str] | None = None,
    ) -> list[dict]:
        """使用官方两步汇报接口批量拉取工作日报与现场技术支持工作报告详情。"""
        if template_ids is not None:
            target_templates = list(template_ids)
        elif settings.WECOM_DAILY_REPORT_TEMPLATE_ID:
            target_templates = [settings.WECOM_DAILY_REPORT_TEMPLATE_ID]
        else:
            target_templates = list(settings.WECOM_JOURNAL_TEMPLATES.values())

        if not target_templates:
            logger.warning("未配置任何企微汇报模板 ID，跳过日报拉取")
            return []

        reports: list[dict] = []
        seen_uuids: set[str] = set()

        for tpl_id in target_templates:
            uuids = self.fetch_journal_record_list(
                start_timestamp, end_timestamp, template_id=tpl_id
            )
            for uuid in uuids:
                if uuid in seen_uuids:
                    continue
                seen_uuids.add(uuid)
                detail = self.fetch_journal_record_detail(uuid)
                if not detail:
                    continue
                detail.setdefault("journal_uuid", uuid)
                detail.setdefault("template_id", tpl_id)
                reports.append(detail)

        return reports

    def fetch_vacation_corp_conf(self) -> list[dict]:
        """只读拉取企业假期类型配置（/cgi-bin/oa/vacation/getcorpconf）。"""
        token = self.get_access_token()
        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/oa/vacation/getcorpconf?access_token=%s"
            % token
        )
        try:
            response = _retry_request("POST", url, json={})
            data = response.json()
            if data.get("errcode") == 0:
                return data.get("lists", []) or []
            logger.error(
                "Error fetching vacation corp conf: %s (code=%s)",
                data.get("errmsg"),
                data.get("errcode"),
            )
            return []
        except Exception as exc:
            logger.error("API exception in fetch_vacation_corp_conf: %s", exc)
            return []

    def fetch_user_vacation_quota(self, userid: str) -> list[dict]:
        """只读拉取单个员工的假期余额列表（/cgi-bin/oa/vacation/getuservacationquota）。"""
        if not userid:
            return []
        token = self.get_access_token()
        url = (
            "https://qyapi.weixin.qq.com/cgi-bin/oa/vacation/getuservacationquota?access_token=%s"
            % token
        )
        try:
            response = _retry_request("POST", url, json={"userid": userid})
            data = response.json()
            if data.get("errcode") == 0:
                return data.get("lists", []) or []
            logger.error(
                "Error fetching vacation quota for %s: %s (code=%s)",
                userid,
                data.get("errmsg"),
                data.get("errcode"),
            )
            return []
        except Exception as exc:
            logger.error("API exception in fetch_user_vacation_quota(%s): %s", userid, exc)
            return []


wecom_client = WeComAPIClient()
