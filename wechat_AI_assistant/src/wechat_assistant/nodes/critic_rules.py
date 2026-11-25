"""Deterministic Critic guardrails verifying schedule/effort separation and numeric fidelity."""

from __future__ import annotations

import re
from datetime import date

from wechat_assistant.schemas import ListType, TriageProposal

# Extract meaningful multi-digit numbers, decimals, percentages, or currency figures (>= 2 chars / decimal)
_NUM_PATTERN = re.compile(r"(?<!\d)(?:\d+\.\d+|\d{2,})(?:%|h|元|万元|天)?")
_UNTRUSTED_BLOCK_RE = re.compile(r"\[UNTRUSTED_EXTERNAL_DATA\].*?\[/UNTRUSTED_EXTERNAL_DATA\]", flags=re.DOTALL)
_TRUSTED_ROLE_RE = re.compile(r"chairman_role=(owner|assignee|cc_observer|approver)")
_CHAIRMAN_TOKENS = ("本人", "徐宏玮", "董事长", "老板", "chairman", "john.xu@")


def _normalize_number_token(tok: str) -> str:
    return re.sub(r"[%h元万天,]", "", tok).strip()


def _is_chairman_identity(name: str) -> bool:
    low = (name or "").strip().lower()
    if not low:
        return False
    return any(tok in low for tok in _CHAIRMAN_TOKENS)


def _extract_trusted_mail_roles(raw_input: str) -> list[str]:
    """Read chairman_role hints ONLY from trusted system sections outside `[UNTRUSTED_EXTERNAL_DATA]`."""
    trusted_only = _UNTRUSTED_BLOCK_RE.sub("", raw_input or "")
    return _TRUSTED_ROLE_RE.findall(trusted_only)


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
    trusted_mail_roles = _extract_trusted_mail_roles(raw_input)
    batch_all_cc = bool(trusted_mail_roles) and all(r == "cc_observer" for r in trusted_mail_roles)

    # 1. Check CC-observer role guardrail, date validity, non-reversed range, and effort separation
    for act in proposal.actions:
        if act.chairman_role == "cc_observer" or batch_all_cc:
            if _is_chairman_identity(act.owner) or _is_chairman_identity(act.assignee):
                issues.append(
                    f"事项「{act.title}」的邮件仅抄送董事长（cc_observer），严禁将董事长填为负责人（{act.owner}）或实施人（{act.assignee}）；"
                    "请按邮件主送/发件人填写具体负责或实施同事。"
                )

        span_days = 1
        start_raw = (act.planned_start_at or "").strip()
        end_raw = (act.planned_end_at or "").strip()
        end_is_tbd = end_raw == "" and "planned_end_at" in (act.missing_required_fields or [])
        try:
            if len(start_raw) < 10:
                raise ValueError("incomplete start date")
            d_start = date.fromisoformat(start_raw[:10])
            if end_is_tbd:
                span_days = 1
            else:
                if len(end_raw) < 10:
                    raise ValueError("incomplete end date")
                d_end = date.fromisoformat(end_raw[:10])
                if d_end < d_start:
                    issues.append(
                        f"事项「{act.title}」的计划结束日期（{end_raw}）早于开始日期（{start_raw}），请修正排期。"
                    )
                else:
                    span_days = max(1, (d_end - d_start).days + 1)
        except ValueError:
            issues.append(
                f"事项「{act.title}」的计划日期非法（{act.planned_start_at} ~ {act.planned_end_at}），"
                "请修正为合法 YYYY-MM-DD 日历日期。"
            )

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
