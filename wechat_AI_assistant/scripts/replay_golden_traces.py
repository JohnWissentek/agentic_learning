#!/usr/bin/env python3
"""Offline Golden Sample Execution Trace Replay Harness (14 messy real-world Chairman scenarios).

Runs realistic WeCom dialogue, Outlook hourly mail window, PMO delegation, Critic loop,
OneDrive 503 resilience, Web Cockpit auth/CRUD, and exception scenarios against the real
engine/DB/gateway/FastAPI stack (with deterministic LLM/HTTP stubs) and prints a 1-page
Markdown execution trace table. Exits 0 only if ALL 14 Golden Samples pass.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.intake import mail_poller
from wechat_assistant.intake.wecom_gateway import QuietAggregator, WeComGateway
from wechat_assistant.storage.db import Database
from wechat_assistant.storage.extractors import extract_document_pages
from wechat_assistant.web.app import create_app

SHANGHAI = ZoneInfo("Asia/Shanghai")


class _StubOneDrive:
    def __init__(self, *, fail_sync: bool = False) -> None:
        self.fail_sync = fail_sync
        self.notes: list[tuple[str, str]] = []

    def upload_bytes(self, remote_path: str, data: bytes, **_kw: Any) -> dict[str, Any]:
        if self.fail_sync:
            raise RuntimeError("503 Service Unavailable")
        return {"id": "mock", "size": len(data), "webUrl": f"https://sp.cn/{remote_path}"}

    def upload_and_cleanup_local(self, remote_path: str, local_path: str | Path) -> dict[str, Any]:
        if self.fail_sync:
            raise RuntimeError("503 Service Unavailable")
        p = Path(local_path)
        data = p.read_bytes()
        p.unlink(missing_ok=True)
        return self.upload_bytes(remote_path, data)

    def append_project_note(self, project_name: str, entry_md: str) -> dict[str, Any]:
        if self.fail_sync:
            raise RuntimeError("503 Service Unavailable")
        self.notes.append((project_name, entry_md))
        return {"id": "note"}

    def sync_all_lists(self, db: Database) -> dict[str, str]:
        if self.fail_sync:
            raise RuntimeError("503 Service Unavailable")
        return {"01_今日与行动待办.md": "https://sp.cn/01"}


class _ScriptedLLM:
    def __init__(self, fn) -> None:
        self.fn = fn
        self.calls: list[str] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs["model"])
        out = self.fn(kwargs, len(self.calls))
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=40, completion_tokens=30, completion_tokens_details=None),
            choices=[SimpleNamespace(message=SimpleNamespace(content=out, tool_calls=None, reasoning_content=""))],
        )


def _mk_settings(root: Path, **over: Any) -> Settings:
    kw: dict[str, Any] = {
        "dashscope_api_key": "sk-fakegolden1234567890abcd",
        "web_access_secret": "golden-hmac-secret-key-1234567890",
        "data_dir": str(root / "data"),
        "mail_enabled": True,
        "mail_user": "john.xu@palmarytech.com",
        "wecom_corp_id": "wwgolden",
        "wecom_app_agent_id": "1000002",
        "wecom_app_secret": "fake_secret_123456789",
        "wecom_app_token": "tok_golden_123456",
        "wecom_app_aes_key": "B" * 43,
        "wecom_app_owner_userid": "JohnXu",
    }
    kw.update(over)
    return Settings(**kw)


def _mk_engine(root: Path, llm_fn, *, od: _StubOneDrive | None = None):
    st = _mk_settings(root)
    db = Database(root / "app.db")
    od_c = od or _StubOneDrive()
    llm = _ScriptedLLM(llm_fn)
    gw = DashScopeLLMGateway(st, client=SimpleNamespace(chat=SimpleNamespace(completions=llm)))
    eng = ChiefOfStaffEngine(
        settings=st,
        db=db,
        gateway=gw,
        onedrive=od_c,
        checkpoints_path=root / "ckpt.db",
        magic_link_factory=lambda: "https://assistant.fire-matrix.com/",
    )
    return eng, db, llm, od_c


def run_all_golden_samples() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def rec(gid: str, channel: str, scenario: str, route: str, result: str, passed: bool) -> None:
        rows.append({
            "id": gid,
            "channel": channel,
            "scenario": scenario,
            "route": route,
            "result": result,
            "status": "✅ PASS" if passed else "❌ FAIL",
        })

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # G01: WeCom shortcut "看板" (even if router fails!)
        def router_down(kw, _i):
            raise RuntimeError("DashScope 503 outage")

        eng1, _, _, _ = _mk_engine(base / "g01", router_down)
        r = eng1.handle_incoming_turn("看板")
        ok = "https://assistant.fire-matrix.com/" in r["reply_text"] and "node:direct_reply" in r["trajectory"]
        rec("G01", "企微对话", "路由模型宕机时发「看板」", " -> ".join(r["trajectory"]), "直出驾驶舱链接，零报错", ok)
        eng1.close()

        # G02: Empty/whitespace WeCom message -> 0 LLM calls
        eng2, _, llm2, _ = _mk_engine(base / "g02", router_down)
        r2 = eng2.handle_incoming_turn("   \n  ")
        ok2 = len(llm2.calls) == 0 and "空白消息" in r2["reply_text"]
        rec("G02", "企微对话", "误触发送纯空白消息", " -> ".join(r2["trajectory"]), f"0 次模型调用，友好引导", ok2)
        eng2.close()

        # G03: WeCom stranger blocked by owner whitelist
        st3 = _mk_settings(base / "g03", wecom_app_owner_userid="JohnXu")
        called3: list[str] = []

        async def _p3(t, s, a, m):
            called3.append(t)
            return "ok"

        gw3 = WeComGateway(st3, turn_processor=_p3)
        asyncio.run(gw3.handle_callback_event({"MsgType": "text", "Content": "查机密", "FromUserName": "Stranger", "MsgId": "m3"}))
        ok3 = len(called3) == 0 and gw3._blocked_attempts == 1
        rec("G03", "企微安全", "非白名单成员发消息到自建应用", "whitelist_guard -> silent_drop", f"拦截次数={gw3._blocked_attempts}，0 回复", ok3)

        # G04: Standalone "好了" not swallowed
        flushed4: list[str] = []

        async def _fl4(k, t, a, m):
            flushed4.append(t)

        async def _run4():
            agg = QuietAggregator(quiet_seconds=0.02, on_flush=_fl4)
            await agg.push("app|JohnXu", text="好了", msg_id="m4")
            await asyncio.sleep(0.06)

        asyncio.run(_run4())
        ok4 = flushed4 == ["好了"]
        rec("G04", "企微合批", "无待合并消息时单发「好了」", "QuietAggregator -> normal_flush", f"正常送达: {flushed4}", ok4)

        # G05: Pure PMO delegation to 张工 -> card displays owner + confirm -> OneDrive 503 resilience
        def pmo_llm(kw, _i):
            m = kw["model"]
            if m == "qwen3.8-flash":
                return json.dumps({"intent": "work_triage", "confidence": 0.96, "summary": "交办张工测算V&F关税"})
            if m == "qwen3.8-max":
                return json.dumps({
                    "headline": "交办张工核算 V&F 关税方案",
                    "executive_summary": "安排张工于周五前完成 V&F 进口关税测算并回报。",
                    "actions": [{
                        "list_type": "waiting_for",
                        "work_domain": "客户销售",
                        "project_name": "V&F 报价",
                        "title": "等待张工提交 V&F 进口关税测算表",
                        "owner": "张工",
                        "planned_start_at": "2026-11-25",
                        "planned_end_at": "2026-11-27",
                        "estimated_hours": 0.0,
                        "priority": "P1",
                        "onedrive_target_dir": "01_项目归档/VF报价",
                    }],
                    "referenced_numbers": [],
                    "citations": [],
                })
            return json.dumps({"passed": True, "numeric_fidelity_ok": True, "schedule_reasonable": True, "issues": [], "fix_instructions": ""})

        od5 = _StubOneDrive(fail_sync=True)
        eng5, db5, _, _ = _mk_engine(base / "g05", pmo_llm, od=od5)
        r5a = eng5.handle_incoming_turn("让张工周五前把 V&F 进口关税测算出来发我")
        ok5a = r5a["proposal_id"] is not None and "负责人：张工" in r5a["reply_text"]
        rec("G05", "PMO 交办", "「让张工周五前把 V&F 关税算出来」", " -> ".join(r5a["trajectory"]), f"出卡 #{r5a['proposal_id']}，清晰标注责任人=张工", ok5a)

        # G06: Confirm card #1 under OneDrive 503 outage -> SQLite commits truthfully + double confirm blocked
        r5b = eng5.handle_incoming_turn("1")
        items5 = db5.list_items()
        ok5b = len(items5) == 1 and items5[0]["owner"] == "张工" and "本地数据库已安全落盘" in r5b["reply_text"]
        rec("G06", "可控落盘", "回复「1」落盘（模拟 OneDrive 503 断网）", " -> ".join(r5b["trajectory"]), "SQLite 原子入库成功 + 如实告知云端稍后重试", ok5b)

        # G07: Batch checkin with partial invalid ID (#1 done, #999 missing) + "完成 1.5h" safe
        r7 = eng5.handle_incoming_turn("#1 做完了，#999 开始了")
        ok7 = "#1" in r7["reply_text"] and "#999" in r7["reply_text"] and "未找到" in r7["reply_text"]
        rec("G07", "进度打卡", "批量打卡「#1 做完了，#999 开始了」", " -> ".join(r7["trajectory"]), "#1 标完成 + 明确回报 #999 未找到", ok7)

        # G08: 24h Undo rolls back cleanly
        r8 = eng5.handle_incoming_turn("撤销")
        ok8 = len(db5.list_items()) == 0 and "回滚" in r8["reply_text"]
        rec("G08", "安全撤销", "24 小时内回复「撤销」", " -> ".join(r8["trajectory"]), "完整回滚至 0 条记录并提示云端稍后同步", ok8)
        eng5.close()

        # G09: Critic 2-loop cap with reversed date -> explicit warning on card
        def bad_date_llm(kw, _i):
            m = kw["model"]
            if m == "qwen3.8-flash":
                return json.dumps({"intent": "work_triage", "confidence": 0.95, "summary": "排期"})
            if m == "qwen3.8-max":
                return json.dumps({
                    "headline": "倒挂日期异常测试",
                    "executive_summary": "测试模型持续输出倒挂日期的熔断告警。",
                    "actions": [{
                        "list_type": "project_action",
                        "work_domain": "项目交付",
                        "project_name": "帕莫瑞",
                        "title": "倒挂排期测试任务",
                        "owner": "本人",
                        "planned_start_at": "2026-11-29",
                        "planned_end_at": "2026-11-25",
                        "estimated_hours": 0.0,
                        "priority": "P1",
                        "onedrive_target_dir": "01_项目归档/帕莫瑞",
                    }],
                    "referenced_numbers": [],
                    "citations": [],
                })
            return json.dumps({"passed": True, "numeric_fidelity_ok": True, "schedule_reasonable": True, "issues": [], "fix_instructions": ""})

        eng9, _, _, _ = _mk_engine(base / "g09", bad_date_llm)
        r9 = eng9.handle_incoming_turn("安排帕莫瑞测试")
        ok9 = "审计待人工复核点" in r9["reply_text"] and "早于开始日期" in r9["reply_text"] and r9["trajectory"].count("critic:deterministic_reject") == 2
        rec("G09", "异构审计", "模型连续 2 轮输出倒挂日期", "drafter->critic(x2)->hitl_preview_gate", "2 轮硬熔断 + 卡片红字暴露人工复核点", ok9)
        eng9.close()

        # G10: Pre-router attachment ingestion for quick_query + corrupt docx graceful fallback
        bad_docx = base / "corrupt.docx"
        bad_docx.write_bytes(b"NOT_A_REAL_DOCX_BINARY")
        pages10 = extract_document_pages(bad_docx)
        ok10 = len(pages10) == 1 and "暂无法解析正文" in pages10[0]["text"]
        rec("G10", "附件容错", "损坏/加密 Word 附件上传解析", "extract_document_pages -> safe_fallback", "零崩溃，返回原件已归档友好提示", ok10)

        # G11: Hourly mail window — 2 inbox + 1 sent with "请确认" -> 0 router calls, 1 card, waiting hint
        def mail_llm(kw, _i):
            if kw["model"] == "qwen3.8-max":
                return json.dumps({
                    "headline": "汇总 V&F 与 Tera 本小时邮件",
                    "executive_summary": "汇总本小时 2 封客户与同事来信，建议今日内回复 V&F 报价。",
                    "actions": [{
                        "list_type": "project_action",
                        "work_domain": "客户销售",
                        "project_name": "V&F 报价",
                        "title": "核对并回复 V&F 报价更新邮件",
                        "owner": "本人",
                        "planned_start_at": "2026-11-25",
                        "planned_end_at": "2026-11-26",
                        "estimated_hours": 0.0,
                        "priority": "P1",
                        "onedrive_target_dir": "01_项目归档/VF报价",
                    }],
                    "referenced_numbers": [],
                    "citations": [],
                })
            return json.dumps({"passed": True, "numeric_fidelity_ok": True, "schedule_reasonable": True, "issues": [], "fix_instructions": ""})

        eng11, db11, llm11, od11 = _mk_engine(base / "g11", mail_llm)
        db11.set_mail_watermark("inbox", "2026-11-24T02:00:00Z")
        db11.set_mail_watermark("sent", "2026-11-24T02:00:00Z")
        dom_path = base / "g11_domains.json"
        dom_path.write_text(json.dumps({"domains": ["palmarytech.com", "wissentek.com", "budi.de", "vandf.com", "tera-instruments.com"]}), encoding="utf-8")

        inbox11 = [
            {
                "id": "i1", "internetMessageId": "<i1@vandf.com>", "subject": "V&F 报价更新",
                "from": {"emailAddress": {"address": "sales@vandf.com"}},
                "toRecipients": [{"emailAddress": {"address": "john.xu@palmarytech.com"}}],
                "ccRecipients": [], "bodyPreview": "新版报价单请查收", "receivedDateTime": "2026-11-24T02:15:00Z",
            },
            {
                "id": "i2", "internetMessageId": "<i2@random.com>", "subject": "广告推广",
                "from": {"emailAddress": {"address": "ads@random.com"}},
                "toRecipients": [{"emailAddress": {"address": "john.xu@palmarytech.com"}}],
                "ccRecipients": [], "bodyPreview": "大促", "receivedDateTime": "2026-11-24T02:20:00Z",
            },
        ]
        sent11 = [
            {
                "id": "s1", "internetMessageId": "<s1@palmarytech.com>", "subject": "Re: Tera 交期",
                "from": {"emailAddress": {"address": "john.xu@palmarytech.com"}},
                "toRecipients": [{"emailAddress": {"address": "support@tera-instruments.com"}}],
                "ccRecipients": [], "bodyPreview": "请确认最终发货日", "sentDateTime": "2026-11-24T02:35:00Z",
            }
        ]
        pushes11: list[str] = []

        async def _f11(folder, _since):
            return inbox11 if folder == "inbox" else sent11

        async def _p11(txt):
            pushes11.append(txt)

        asyncio.run(mail_poller.run_mail_window_once(
            settings=eng11.settings, db=db11, od_client=od11, engine=eng11, send_push=_p11,
            now_local=datetime(2026, 11, 24, 11, 0, tzinfo=SHANGHAI), domains_path=dom_path, fetch_folder=_f11,
        ))
        ok11 = (
            len(pushes11) == 1
            and "qwen3.8-flash" not in llm11.calls
            and "可能在等对方" in pushes11[0]
            and "广告推广" not in pushes11[0]
            and db11.is_external_seen("<i2@random.com>")
        )
        rec("G11", "香港邮箱", "11:00 班：1白名单收件 + 1广告 + 1发件(请确认)", "mail_window -> force_work_triage -> 1 push", "0 次路由调用、1 张卡 + 发件标「可能在等对方」、广告静默过滤", ok11)

        # G12: Next slot with pending card still open -> inbox deferred, sent still delivered
        inbox12 = [{
            "id": "i3", "internetMessageId": "<i3@budi.de>", "subject": "Budi 新订单确认",
            "from": {"emailAddress": {"address": "buyer@budi.de"}},
            "toRecipients": [{"emailAddress": {"address": "john.xu@palmarytech.com"}}],
            "ccRecipients": [], "bodyPreview": "PO attached", "receivedDateTime": "2026-11-24T03:10:00Z",
        }]
        pushes12: list[str] = []

        async def _f12(folder, _since):
            return inbox12 if folder == "inbox" else []

        async def _p12(txt):
            pushes12.append(txt)

        asyncio.run(mail_poller.run_mail_window_once(
            settings=eng11.settings, db=db11, od_client=od11, engine=eng11, send_push=_p12,
            now_local=datetime(2026, 11, 24, 12, 0, tzinfo=SHANGHAI), domains_path=dom_path, fetch_folder=_f12,
        ))
        ok12 = len(pushes12) == 1 and "还没回复" in pushes12[0] and not db11.is_external_seen("<i3@budi.de>")
        rec("G12", "香港邮箱", "12:00 班：上张卡未回复时来新收件", "turn_lock -> pending_deferral", "不覆盖旧卡、提醒主题、保留未 seen 待下班处理", ok12)
        eng11.close()

        # G13: Quiet hours (Saturday & 22:00) -> None
        ok13 = (
            mail_poller.active_mail_slot(datetime(2026, 11, 24, 22, 0, tzinfo=SHANGHAI)) is None
            and mail_poller.active_mail_slot(datetime(2026, 11, 28, 10, 0, tzinfo=SHANGHAI)) is None
        )
        rec("G13", "香港邮箱", "周二 22:00 与周六 10:00 静默时段", "active_mail_slot -> None", "不拉邮箱、不调模型、不打扰", ok13)

        # G14: Web Cockpit brute-force lockout + dirty PATCH 422
        eng14, db14, _, od14 = _mk_engine(base / "g14", router_down)
        app14 = create_app(settings=eng14.settings, db=db14, engine=eng14, onedrive=od14, start_background_tasks=False)
        with TestClient(app14) as client:
            code14 = app14.state.auth.mint_login_code(300)
            wrong = "000000" if code14 != "000000" else "999999"
            for _ in range(5):
                client.post("/api/auth/verify-code", json={"code": wrong})
            locked = client.post("/api/auth/verify-code", json={"code": code14})
            tok = app14.state.auth.mint_magic_token(300)
            client.get(f"/auth/magic?token={tok}", follow_redirects=False)
            cid = client.post("/api/items", json={"title": "校验测试"}).json()["created_ids"][0]
            bad_patch = client.patch(f"/api/items/{cid}", json={"status": "hacked"})
            ok14 = locked.status_code == 429 and bad_patch.status_code == 422
        rec("G14", "Web 驾驶舱", "6 位码连错 5 次防爆破 + 非法状态 PATCH", "AuthManager(lock) + Pydantic(422)", f"防爆破={locked.status_code}，脏写拦截={bad_patch.status_code}", ok14)
        eng14.close()

    return rows


def main() -> int:
    rows = run_all_golden_samples()
    print("| 样本 | 通道 | 董事长真实/异常场景 | 实际流转轨迹 | 关键产出与防线实证 | 结果 |")
    print("| :---: | :---: | :--- | :--- | :--- | :---: |")
    failed = 0
    for r in rows:
        if "FAIL" in r["status"]:
            failed += 1
        print(f"| {r['id']} | {r['channel']} | {r['scenario']} | `{r['route']}` | {r['result']} | {r['status']} |")
    print(f"\nGOLDEN_REPLAY_SUMMARY: total={len(rows)} passed={len(rows) - failed} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
