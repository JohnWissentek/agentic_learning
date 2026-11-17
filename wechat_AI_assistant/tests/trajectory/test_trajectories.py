"""Ch.19 Trajectory Evaluation suite testing 10 canonical Chief-of-Staff scenarios."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.storage.db import Database


class _RouteAwareCompletions:
    def create(self, **kwargs):
        model = kwargs["model"]
        user_msg = kwargs["messages"][-2]["content"] if len(kwargs["messages"]) >= 2 else ""

        if model == "qwen3.8-flash":
            if "第几页" in user_msg or "是多少" in user_msg:
                payload = {"intent": "quick_query", "confidence": 0.97, "needs_deep_research": False, "summary": "查文档"}
            else:
                needs_res = "想法" in user_msg or "标准" in user_msg
                payload = {"intent": "work_triage", "confidence": 0.95, "needs_deep_research": needs_res, "summary": "分拣"}
        elif model == "qwen3.8-max":
            if "问题：" in user_msg:
                payload = {"found": True, "answer": "在《Spec.pdf》第 4 页写明系数为 0.0095。", "citations": ["Spec.pdf 第 4 页"]}
            else:
                payload = {
                    "headline": "幕僚分拣提案",
                    "executive_summary": "已完成排期与工时拆解。",
                    "actions": [{
                        "list_type": "idea" if "想法" in user_msg else "project_action",
                        "work_domain": "产品研发",
                        "project_name": "测试项目",
                        "title": "推进跟进事项",
                        "owner": "本人",
                        "planned_start_at": "2026-11-18",
                        "planned_end_at": "2026-11-20",
                        "estimated_hours": 1.0,
                        "priority": "P1",
                        "onedrive_target_dir": "01_项目归档/测试项目",
                    }],
                    "referenced_numbers": ["1.0"],
                    "citations": [],
                }
        else:
            payload = {"passed": True, "numeric_fidelity_ok": True, "schedule_reasonable": True, "issues": [], "fix_instructions": ""}

        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=20, completion_tokens=20, completion_tokens_details=None),
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False), tool_calls=None, reasoning_content=""))],
        )


@pytest.mark.parametrize(
    "case_id,user_input,expected_step",
    [
        (1, "密：不可外发的补偿参数", "guard:confidential_zero_llm"),
        (2, "看板", "shortcut:cockpit_magic_link"),
        (3, "负荷", "shortcut:workload"),
        (4, "撤销", "shortcut:undo"),
        (5, "开始 999", "shortcut:start_not_found"),
        (6, "完成 999 1.5h", "shortcut:done_not_found"),
        (7, "Spec.pdf 第几页写了补偿系数是多少", "tool:hybrid_search"),
        (8, "某个从未存在过的太空项目预算是多少", "node:quick_qa_responder"),
        (9, "我刚有个新想法，查一下2U工业机箱抗干扰标准", "tool:search_public_tech_intel"),
        (10, "把周五帕莫瑞技术协议评审安排上，大概占1小时", "node:hitl_preview_gate"),
    ],
)
def test_ten_canonical_trajectories(tmp_path, case_id, user_input, expected_step):
    settings = Settings(dashscope_api_key="sk-fakeunit1234567890abcdef", data_dir=str(tmp_path / "data"))
    db = Database(tmp_path / "app.db")
    db.insert_raw_source(
        source_type="pdf",
        external_msg_id="seed_spec",
        sender="owner",
        title="Spec.pdf",
        raw_text="规范",
        extracted_pages=[{"page": 4, "text": "补偿系数为 0.0095"}],
    )
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=_RouteAwareCompletions())))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw)
    res = eng.handle_incoming_turn(user_input, external_msg_id=f"traj_{case_id}")
    assert expected_step in res["trajectory"]
    eng.close()
