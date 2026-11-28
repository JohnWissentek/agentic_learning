"""Slice 2 黑盒契约测试：企微假期配置/余额拉取与逾期堆积审计（只告警不自动扣减）。"""
from __future__ import annotations

import pytest

from attendance_audit_integration.config import settings
from attendance_audit_integration.wecom_api import WeComAPIClient


class _FakeResp:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


@pytest.mark.unit
class TestWeComVacationReadAPI:
    def test_fetch_vacation_corp_conf_and_user_quota(self, monkeypatch):
        client = WeComAPIClient()
        monkeypatch.setattr(client, "get_access_token", lambda: "tok_vac")

        called: list[str] = []

        def fake_retry(method, url, **kwargs):
            called.append(url)
            if "/oa/vacation/getcorpconf" in url:
                return _FakeResp(
                    {
                        "errcode": 0,
                        "lists": [
                            {"id": 1, "name": "年假", "expire_rule": {"type": 4}},
                            {"id": 4, "name": "调休假", "expire_rule": {"type": 4}},
                        ],
                    }
                )
            if "/oa/vacation/getuservacationquota" in url:
                return _FakeResp(
                    {
                        "errcode": 0,
                        "lists": [
                            {"id": 1, "vacationname": "年假", "leftduration": 58 * 3600},
                            {"id": 4, "vacationname": "调休假", "leftduration": int(219.5 * 3600)},
                        ],
                    }
                )
            raise AssertionError(f"Unexpected url: {url}")

        monkeypatch.setattr("attendance_audit_integration.wecom_api._retry_request", fake_retry)

        conf = client.fetch_vacation_corp_conf()
        quota = client.fetch_user_vacation_quota("WangXu")

        assert len(conf) == 2
        assert conf[1]["id"] == 4
        assert len(quota) == 2
        assert any("/oa/vacation/getcorpconf" in u for u in called)
        assert any("/oa/vacation/getuservacationquota" in u for u in called)


@pytest.mark.unit
class TestVacationAnomalyAnalysis:
    def test_extract_hours_handles_leftduration_and_balance_in_seconds(self):
        from attendance_audit_integration.services.vacation_audit import (
            extract_hours_by_vacation_id,
        )

        raw_lists = [
            {"id": 1, "leftduration": 28800, "quota": 57600, "used": 28800},
            {"id": 4, "balance": int(219.5 * 3600), "quota": int(230 * 3600), "used": int(10.5 * 3600)},
        ]
        parsed = extract_hours_by_vacation_id(raw_lists)
        assert parsed[1]["remaining_hours"] == 8.0
        assert parsed[4]["remaining_hours"] == 219.5
        assert parsed[4]["granted_hours"] == 230.0
        assert parsed[4]["used_hours"] == 10.5

    def test_analyze_detects_comp_backlog_annual_high_leaver_and_permanent_expiry(self):
        from attendance_audit_integration.services.vacation_audit import (
            analyze_vacation_anomalies,
        )

        quotas = [
            {
                "wecom_userid": "WangXu",
                "name": "王旭",
                "status": "active",
                "annual_hours": 58.0,
                "comp_hours": 219.5,
                "sick_hours": 0.0,
            },
            {
                "wecom_userid": "ShiZhiTong",
                "name": "石志同",
                "status": "active",
                "annual_hours": 10.0,
                "comp_hours": 64.7,
                "sick_hours": 0.0,
            },
            {
                "wecom_userid": "XuHongWei",
                "name": "徐宏玮",
                "status": "active",
                "annual_hours": 120.0,
                "comp_hours": 0.0,
                "sick_hours": 0.0,
            },
            {
                "wecom_userid": "LiuYe",
                "name": "刘页",
                "status": "inactive",
                "annual_hours": 0.0,
                "comp_hours": 61.5,
                "sick_hours": 24.0,
            },
        ]
        corp_conf = [
            {"id": 1, "name": "年假", "quota_attr": {"type": 2}, "expire_rule": {"type": 4}},
            {"id": 3, "name": "病假", "quota_attr": {"type": 2}, "expire_rule": {"type": 4}},
            {"id": 4, "name": "调休假", "quota_attr": {"type": 2}, "expire_rule": {"type": 4}},
        ]

        report = analyze_vacation_anomalies(quotas, corp_conf)

        # 调休堆积按小时降序，且不含考核排除名单
        assert [x["name"] for x in report["comp_backlog"]] == ["王旭", "石志同"]
        # 年假超 40h 不含免考核白名单徐宏玮
        assert [x["name"] for x in report["annual_high"]] == ["王旭"]
        # 离职人员残留余额被检出
        assert [x["name"] for x in report["leaver_residuals"]] == ["刘页"]
        # 在职全员病假余额 0 且为限额模式
        assert report["zero_sick_limit_risk"] is True
        # 检出永久有效（无自动清零）的假期类型
        assert set(report["permanent_expiry_types"]) == {"年假", "病假", "调休假"}

    def test_run_vacation_balance_audit_sends_comp_backlog_only_to_pm_not_employee(self, monkeypatch):
        from attendance_audit_integration.services import vacation_audit

        sent_emails: list[dict] = []

        class _FakeCur:
            def execute(self, sql, params=None):
                self._sql = sql

            def fetchall(self):
                if "FROM employees" in self._sql:
                    return [
                        {"wecom_userid": "WangXu", "name": "王旭", "email": "wangxu@palmarytech.com", "status": "active"},
                        {"wecom_userid": "LiuYe", "name": "刘页", "email": "liuye@palmarytech.com", "status": "inactive"},
                    ]
                return []

            def close(self):
                pass

        class _FakeConn:
            def cursor(self, cursor_factory=None):
                return _FakeCur()

            def commit(self):
                pass

            def rollback(self):
                pass

            def close(self):
                pass

        monkeypatch.setattr(vacation_audit, "get_db_connection", lambda: _FakeConn())
        monkeypatch.setattr(
            vacation_audit.wecom_client,
            "fetch_vacation_corp_conf",
            lambda: [{"id": 4, "name": "调休假", "expire_rule": {"type": 4}}],
        )
        monkeypatch.setattr(
            vacation_audit.wecom_client,
            "fetch_user_vacation_quota",
            lambda uid: (
                [
                    {"id": 1, "leftduration": 58 * 3600},
                    {"id": 4, "leftduration": int(219.5 * 3600)},
                ]
                if uid == "WangXu"
                else [{"id": 4, "leftduration": int(61.5 * 3600)}]
            ),
        )
        monkeypatch.setattr(
            vacation_audit.mail_sender,
            "send_html_email",
            lambda **kwargs: sent_emails.append(kwargs) or True,
        )

        result = vacation_audit.run_vacation_balance_audit(send_email=True)
        assert result["synced_employees"] == 2
        assert len(result["anomalies"]["comp_backlog"]) == 1
        assert len(result["anomalies"]["leaver_residuals"]) == 1

        # F11 红线：调休堆积邮件仅发 PM + F11_CC，严禁发或抄送被催员工本人
        pm_mails = [m for m in sent_emails if "调休" in m["subject"]]
        assert len(pm_mails) == 1
        assert pm_mails[0]["to_email"] == settings.PM_EMAILS[0]
        assert "wangxu@palmarytech.com" not in ([pm_mails[0]["to_email"]] + (pm_mails[0].get("cc_list") or []))
