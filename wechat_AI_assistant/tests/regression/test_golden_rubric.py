"""Ch.19 Golden Regression Rubric checks for splitting, duration/effort separation, and numeric fidelity."""

from __future__ import annotations

import json

from wechat_assistant.nodes.critic_rules import deterministic_critic_check
from wechat_assistant.schemas import ActionMutation, ListType, PriorityLevel, TriageProposal, WorkDomain
from wechat_assistant.storage.db import Database
from wechat_assistant.tools.calc_tools import analyze_excel_quote


def test_golden_rubric_multi_item_split_and_effort_separation(tmp_path):
    db = Database(tmp_path / "golden.db")
    proposal = TriageProposal(
        headline="高温探头延期应对 + 备选厂商询价",
        executive_summary="原交期 11-25 顺延 14 天至 12-09；今日安排 1.0h 联系备选厂商确认现货。",
        actions=[
            ActionMutation(
                list_type=ListType.WAITING_FOR,
                work_domain=WorkDomain.SUPPLY_CHAIN,
                project_name="热电锅炉交付",
                title="等待原供应商高温探头交货",
                owner="王总",
                planned_start_at="2026-11-17",
                planned_end_at="2026-12-09",
                estimated_hours=0.2,  # Separate waiting calendar span vs follow-up effort!
                priority=PriorityLevel.P1,
            ),
            ActionMutation(
                list_type=ListType.PROJECT_ACTION,
                work_domain=WorkDomain.SUPPLY_CHAIN,
                project_name="热电锅炉交付",
                title="联系苏州光电确认备选探头现货与加急交期",
                owner="本人",
                planned_start_at="2026-11-17",
                planned_end_at="2026-11-20",
                estimated_hours=1.0,
                priority=PriorityLevel.P0,
            ),
        ],
        referenced_numbers=["14", "1.0", "0.2"],
    )
    issues = deterministic_critic_check(
        proposal,
        raw_input="高温探头往后推14天到12-09，原交期11-25，联系苏州光电约1.0小时，跟进0.2小时",
        evidence_text="",
        tool_outputs_text="",
    )
    assert issues == []

    res = db.apply_proposal_atomic(
        proposal_id=None,
        actions=proposal.actions,
        source_ids=[],
        doc_paths=[],
    )
    assert len(res["inserted_item_ids"]) == 2
    # Workload uses 1.2h total CEO net hours, NEVER 22 calendar waiting days!
    wl = db.get_daily_workload(start_date="2026-11-17", days=1, daily_capacity=6.0)
    assert wl["days"]["2026-11-17"]["booked_hours"] == 1.2


def test_golden_rubric_excel_fidelity_and_critic():
    old_rows = [{"物料": "A1探头", "单价": 800, "数量": 5, "小计": 4000}]
    new_rows = [{"物料": "A1探头", "单价": 850, "数量": 5, "小计": 4250}]
    diff = analyze_excel_quote(old_rows, new_rows)
    proposal = TriageProposal(
        headline="报价单核对",
        executive_summary="A1探头单价由 800 调至 850，总价增加 250。",
        actions=[],
        referenced_numbers=["800", "850", "250"],
    )
    issues = deterministic_critic_check(
        proposal,
        raw_input="请帮我对比两份报价单",
        evidence_text="",
        tool_outputs_text=json.dumps(diff, ensure_ascii=False),
    )
    assert issues == []
