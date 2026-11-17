"""Deterministic Critic guardrails verifying schedule/effort separation and numeric fidelity."""

from __future__ import annotations

import re
from datetime import date

from wechat_assistant.schemas import ListType, TriageProposal

# Extract meaningful multi-digit numbers, decimals, percentages, or currency figures (>= 2 chars / decimal)
_NUM_PATTERN = re.compile(r"(?<!\d)(?:\d+\.\d+|\d{2,})(?:%|h|元|万元|天)?")


def _normalize_number_token(tok: str) -> str:
    return re.sub(r"[%h元万天,]", "", tok).strip()


def deterministic_critic_check(
    proposal: TriageProposal,
    *,
    raw_input: str,
    evidence_text: str,
    tool_outputs_text: str,
) -> list[str]:
    """Run hard programmatic checks before or alongside heterogeneous LLM audit."""
    issues: list[str] = []
    combined_source = "\n".join((raw_input, evidence_text, tool_outputs_text)).replace(",", "")

    # 1. Check calendar duration vs net CEO effort hours separation
    for act in proposal.actions:
        try:
            d_start = date.fromisoformat(act.planned_start_at[:10])
            d_end = date.fromisoformat(act.planned_end_at[:10])
            span_days = max(1, (d_end - d_start).days + 1)
        except ValueError:
            span_days = 1

        if act.list_type == ListType.WAITING_FOR and span_days >= 3 and act.estimated_hours >= span_days * 4:
            issues.append(
                f"事项「{act.title}」为外部等待项（跨度 {span_days} 天），但预计个人净工时误填为 {act.estimated_hours}h；"
                "请只保留老板本人催办/验收的净投入小时数（通常 0.2~1.0h）。"
            )
        if act.estimated_hours > 24.0:
            issues.append(
                f"单项「{act.title}」个人净工时 {act.estimated_hours}h 过大，请拆分为可执行子任务或核实是否为日历跨度天数。"
            )

    # 2. Check numeric fidelity on explicitly referenced numbers + numbers in summary
    for ref in proposal.referenced_numbers:
        core = _normalize_number_token(str(ref))
        if len(core) >= 2 and core not in combined_source:
            issues.append(f"引用数值 `{ref}` 未出现在原文、文档证据或工具计算结果中，涉嫌无依据编造。")

    for m in _NUM_PATTERN.findall(proposal.executive_summary):
        core = _normalize_number_token(m)
        # Skip small dates like 2026 / 11 / 17 or ordinary 1-2h hour guesses in summary
        if "." in core or len(core) >= 3:
            if core not in combined_source and not core.startswith("202"):
                # Allow numbers that match estimated_hours summed from actions
                total_h = round(sum(a.estimated_hours for a in proposal.actions), 2)
                action_nums = {str(a.estimated_hours) for a in proposal.actions} | {
                    a.planned_start_at.replace("-", "") for a in proposal.actions
                } | {str(total_h), f"{total_h:.1f}"}
                if core not in action_nums and f"{float(core):.1f}" not in action_nums:
                    issues.append(f"摘要中的关键数值 `{m}` 缺乏原文或工具计算依据。")

    return issues
