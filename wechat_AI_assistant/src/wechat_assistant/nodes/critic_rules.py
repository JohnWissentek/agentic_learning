"""v3.0 Pure Objective Chassis Guardrails (Model-First, zero false-positive substring policing).

Enforces strictly 3 objective invariants on proposed task mutations:
1. Outlook-only `cc_observer` channel lock: ONLY when `is_mail_origin` is True (or trusted
   `[SYSTEM_TRUSTED_MAIL_META]` blocks outside `[UNTRUSTED_EXTERNAL_DATA]` indicate mail context)
   and the Chairman is only CC'd, never allow Chairman to be assigned as owner or assignee.
   NEVER fires on WeChat delegations, even if chat history mentions `cc_observer`.
2. Valid Gregorian ISO calendar dates (`YYYY-MM-DD`), non-reversed ranges (`end >= start`),
   and explicit TBD support (`planned_end_at == ""` with `"planned_end_at"` in `missing_required_fields`).
3. Objective effort-hours sanity: prevents conflating multi-day external waiting spans as full
   personal workdays (`WAITING_FOR` >= 3 days with `estimated_hours >= span_days * 4`) and caps
   single-task personal net effort at `<= 24.0h`.

Strictly NO literal-substring number policing on derived/summarized figures or dates.
"""

from __future__ import annotations

import re
from datetime import date

from wechat_assistant.schemas import ListType, TriageProposal

_UNTRUSTED_BLOCK_RE = re.compile(
    r"\[UNTRUSTED_EXTERNAL_DATA\].*?\[/UNTRUSTED_EXTERNAL_DATA\]",
    flags=re.DOTALL | re.IGNORECASE,
)
_TRUSTED_META_BLOCK_RE = re.compile(
    r"\[SYSTEM_TRUSTED_MAIL_META\](.*?)\[/SYSTEM_TRUSTED_MAIL_META\]",
    flags=re.DOTALL | re.IGNORECASE,
)
_TRUSTED_ROLE_RE = re.compile(r"chairman_role=(owner|assignee|cc_observer|approver)")
_CHAIRMAN_TOKENS = ("本人", "徐宏玮", "董事长", "老板", "chairman", "john.xu@")


def _is_chairman_identity(name: str) -> bool:
    low = (name or "").strip().lower()
    if not low:
        return False
    return any(tok in low for tok in _CHAIRMAN_TOKENS)


def _extract_trusted_mail_roles(raw_input: str, *, strict_meta_only: bool = False) -> list[str]:
    """Read `chairman_role` hints ONLY from trusted metadata outside `[UNTRUSTED_EXTERNAL_DATA]` blocks."""
    trusted_only = _UNTRUSTED_BLOCK_RE.sub("", raw_input or "")
    meta_blocks = _TRUSTED_META_BLOCK_RE.findall(trusted_only)
    if meta_blocks:
        roles: list[str] = []
        for block in meta_blocks:
            roles.extend(_TRUSTED_ROLE_RE.findall(block))
        return roles
    if strict_meta_only:
        return []
    # Backward compat for direct unit tests passing trusted prefix + [UNTRUSTED_EXTERNAL_DATA] without meta wrapper
    if _UNTRUSTED_BLOCK_RE.search(raw_input or ""):
        return _TRUSTED_ROLE_RE.findall(trusted_only)
    return []


def objective_proposal_guard(
    proposal: TriageProposal,
    *,
    raw_input: str,
    evidence_text: str = "",
    tool_outputs_text: str = "",
    is_mail_origin: bool | None = None,
) -> list[str]:
    """Run minimal, pure-objective chassis checks before preview or commit."""
    del evidence_text, tool_outputs_text  # intentionally unused: zero literal-substring policing
    issues: list[str] = []

    if is_mail_origin is False:
        is_mail_context = False
        trusted_mail_roles: list[str] = []
    elif is_mail_origin is True:
        is_mail_context = True
        trusted_mail_roles = _extract_trusted_mail_roles(raw_input, strict_meta_only=True)
    else:
        trusted_only = _UNTRUSTED_BLOCK_RE.sub("", raw_input or "")
        trusted_mail_roles = _extract_trusted_mail_roles(raw_input, strict_meta_only=False)
        is_mail_context = bool(
            _TRUSTED_META_BLOCK_RE.search(trusted_only)
            or _UNTRUSTED_BLOCK_RE.search(raw_input or "")
        )
    batch_all_cc = bool(trusted_mail_roles) and all(r == "cc_observer" for r in trusted_mail_roles)

    for act in proposal.actions:
        # 1. Outlook-only CC-observer channel lock
        if is_mail_context and (batch_all_cc or act.chairman_role == "cc_observer"):
            if _is_chairman_identity(act.owner) or _is_chairman_identity(act.assignee):
                issues.append(
                    f"事项「{act.title}」的邮件仅抄送董事长（cc_observer），严禁将董事长填为负责人（{act.owner}）或实施人（{act.assignee}）；"
                    "请按邮件主送/发件人填写具体负责或实施同事。"
                )

        # 2. Valid Gregorian ISO calendar dates & non-reversed range
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

        # 3. Objective effort-hours sanity
        if act.list_type == ListType.WAITING_FOR and span_days >= 3 and act.estimated_hours >= span_days * 4:
            issues.append(
                f"事项「{act.title}」为外部等待项（跨度 {span_days} 天），但预计个人净工时误填为 {act.estimated_hours}h；"
                "请只保留老板本人催办/验收的净投入小时数（通常 0.2~1.0h）。"
            )
        if act.estimated_hours > 24.0:
            issues.append(
                f"单项「{act.title}」个人净工时 {act.estimated_hours}h 过大，请拆分为可执行子任务或核实是否为日历跨度天数。"
            )

    return issues


# Backward-compatible alias for legacy imports
deterministic_critic_check = objective_proposal_guard
