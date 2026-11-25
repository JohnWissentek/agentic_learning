"""v3.0 Single-Brain Trajectory Evaluation suite testing 10 canonical Chief-of-Staff scenarios."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from wechat_assistant.config import DashScopeLLMGateway, Settings
from wechat_assistant.graph import ChiefOfStaffEngine
from wechat_assistant.storage.db import Database


class _SingleBrainCompletions:
    def create(self, **kwargs):
        user_msg = kwargs["messages"][-1]["content"] if kwargs.get("messages") else ""
        latest = user_msg.split("【本次最新输入】")[-1].strip()

        if "开始 999" in latest:
            payload = {
                "mode": "direct_ops",
                "status_changes": [{"task_id": 999, "action": "start"}],
            }
        elif "完成 999" in latest:
            payload = {
                "mode": "direct_ops",
                "status_changes": [{"task_id": 999, "action": "complete", "actual_hours": 1.5}],
            }
        elif "第几页" in latest:
            payload = {
                "mode": "reply",
                "reply_text": "在《Spec.pdf》第 4 页写明系数为 0.0095。",
            }
        elif "太空项目" in latest:
            payload = {
                "mode": "reply",
                "reply_text": "未查到相关历史记录或文档依据。",
            }
        else:
            payload = {
                "mode": "propose",
                "proposal": {
                    "headline": "幕僚分拣提案",
                    "executive_summary": "已完成排期拆解。",
                    "actions": [{
                        "list_type": "idea" if "想法" in latest else "project_action",
                        "work_domain": "产品研发",
                        "project_name": "测试项目",
                        "title": "推进跟进事项",
                        "owner": "徐宏玮",
                        "assignee": "本人",
                        "planned_start_at": "2026-11-25",
                        "planned_end_at": "2026-11-27",
                        "estimated_hours": 1.0,
                        "priority": "P1",
                        "onedrive_target_dir": "01_项目归档/测试项目",
                    }],
                    "referenced_numbers": [],
                    "citations": [],
                },
            }

        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=20, completion_tokens=20, completion_tokens_details=None),
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False), tool_calls=None, reasoning_content=""))],
        )


@pytest.mark.parametrize(
    "case_id,user_input,expected_step",
    [
        (1, "看板", "exec:open_cockpit"),
        (2, "dashboard", "exec:open_cockpit"),
        (3, "负荷", "exec:show_workload"),
        (4, "撤销", "tool:emergency_button=undo"),
        (5, "开始 999", "exec:direct_ops"),
        (6, "完成 999 1.5h", "exec:direct_ops"),
        (7, "Spec.pdf 第几页写了补偿系数是多少", "exec:reply"),
        (8, "某个从未存在过的太空项目预算是多少", "exec:reply"),
        (9, "我刚有个新想法，查一下2U工业机箱抗干扰标准", "exec:hitl_preview"),
        (10, "把周五帕莫瑞技术协议评审安排上，大概占1小时", "exec:hitl_preview"),
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
    gw = DashScopeLLMGateway(settings, client=SimpleNamespace(chat=SimpleNamespace(completions=_SingleBrainCompletions())))
    eng = ChiefOfStaffEngine(settings=settings, db=db, gateway=gw)
    res = eng.handle_incoming_turn(user_input, external_msg_id=f"traj_{case_id}")
    assert expected_step in res["trajectory"]
    eng.close()
