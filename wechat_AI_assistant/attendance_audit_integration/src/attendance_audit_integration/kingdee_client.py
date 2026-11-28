"""金蝶云星空 Web API 只读客户端（F15；PRD v0.5 §4.2-12）。

- 仅封装 LoginByAppSecret（登录）与 ExecuteBillQuery（单据查询）两个只读能力；
- 严禁增加 Save / Audit / Delete 等写接口（交叉审计只读，不回写金蝶）；
- 凭证来自 .env（KINGDEE_*）；缺失时 is_configured() 为 False，调用方降级跳过。
"""
from __future__ import annotations

import json

import httpx

from attendance_audit_integration.config import settings
from attendance_audit_integration.logger import get_logger

logger = get_logger(__name__)

_LOGIN_PATH = "/Kingdee.BOS.WebApi.ServicesStub.AuthService.LoginByAppSecret.common.kdsvc"
_QUERY_PATH = "/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery.common.kdsvc"
_LCID_ZH_CN = 2052
_REQUEST_TIMEOUT_SECONDS = 30.0


class KingdeeAuthError(RuntimeError):
    """金蝶登录失败。"""


class KingdeeQueryError(RuntimeError):
    """金蝶单据查询失败。"""


class KingdeeClient:
    """会话式只读客户端；login() 成功后复用 Cookie 会话。"""

    def __init__(self) -> None:
        self._http = httpx.Client(
            base_url=settings.KINGDEE_BASE_URL, timeout=_REQUEST_TIMEOUT_SECONDS
        )
        self._is_logged_in = False

    @staticmethod
    def is_configured() -> bool:
        return all(
            [
                settings.KINGDEE_BASE_URL,
                settings.KINGDEE_ACCT_ID,
                settings.KINGDEE_USERNAME,
                settings.KINGDEE_APP_ID,
                settings.KINGDEE_APP_SECRET,
            ]
        )

    def login(self) -> None:
        """LoginByAppSecret 换取会话；失败抛 KingdeeAuthError。"""
        response = self._http.post(
            _LOGIN_PATH,
            json={
                "acctID": settings.KINGDEE_ACCT_ID,
                "username": settings.KINGDEE_USERNAME,
                "appid": settings.KINGDEE_APP_ID,
                "appsecret": settings.KINGDEE_APP_SECRET,
                "lcid": _LCID_ZH_CN,
            },
        )
        response.raise_for_status()
        login_result = response.json()
        # 金蝶登录返回 LoginResultType==1 表示成功
        if login_result.get("LoginResultType") != 1:
            raise KingdeeAuthError(
                "金蝶登录失败: %s" % login_result.get("Message", login_result)
            )
        self._is_logged_in = True
        logger.info("金蝶云星空登录成功（只读会话）")

    def query_expense_bills(
        self, filter_string: str, field_keys: str, limit: int = 2000
    ) -> list[list]:
        """ExecuteBillQuery 只读查询报销单，返回按 field_keys 顺序的行列表。

        FormId 来自 KINGDEE_EXPENSE_FORM_ID（默认 ER_ExpenseRequest，须按
        企业真实账套元数据确认，见伪代码注意事项）。
        """
        if not self._is_logged_in:
            raise KingdeeAuthError("未登录金蝶会话，先调用 login()")

        response = self._http.post(
            _QUERY_PATH,
            json={
                "data": {
                    "FormId": settings.KINGDEE_EXPENSE_FORM_ID,
                    "FieldKeys": field_keys,
                    "FilterString": filter_string,
                    "TopRowCount": limit,
                }
            },
        )
        response.raise_for_status()
        rows = response.json()
        # 查询失败时金蝶返回带 Result.ResponseStatus 的对象而非行数组
        if isinstance(rows, dict):
            raise KingdeeQueryError("金蝶查询失败: %s" % json.dumps(rows, ensure_ascii=False))
        return rows

    def close(self) -> None:
        self._http.close()
