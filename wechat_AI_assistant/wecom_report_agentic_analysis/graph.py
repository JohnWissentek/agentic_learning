"""LangGraph V3.0 Dual-Track & Independent Red-Team Alert Workflow (Slice C).

Strictly aligns with:
- docs/06_ANALYSIS_FRAMEWORK_AND_REPORT_TEMPLATE_SPEC.md (V3.0)
- diagrams/04_WORKFLOW_AUDIT_AND_UML25_ARCHITECTURE.drawio (OMG UML 2.5)
- Production Headless Mode default (`OBS_HUB_ENABLED=false`); Debug Studio via `langgraph.json`.

Stages:
  Stage 1 (Deterministic): check_watermark_and_sync -> assemble_desktop_context
  Stage 2 (Flagship Brain): flagship_brain_investigate <-> readonly_tools (<= max_investigation_steps)
                            -> flagship_brain_synthesize
  Stage 3 (Scheme B Red-Team): redteam_critic -> verify_and_grade_alerts (<= max_verification_retries,
                               with minor unverified degradation rather than silent drop)
  Stage 4 (Deterministic Commit): archive_render_and_deliver
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from wecom_report_agentic_analysis.alignment_analyzer import (
    _parse_llm_json_payload,
    _strip_report_html,
    build_dual_track_desktop_context,
    compute_v3_dual_track_metrics,
)
from wecom_report_agentic_analysis.email_delivery import deliver_weekly_alert_email
from wecom_report_agentic_analysis.pdf_renderer import render_executive_pdf
from wecom_report_agentic_analysis.prompts import (
    MAIN_BRAIN_INVESTIGATE_SYSTEM_PROMPT,
    MAIN_BRAIN_SYNTHESIZE_SYSTEM_PROMPT,
    REDTEAM_CRITIC_SYSTEM_PROMPT,
)
from wecom_report_agentic_analysis.schemas import (
    ALL_WECOM_TEMPLATES,
    ROSTER_BY_NAME,
    DualTrackAuditReport,
    load_strategic_goals_config,
    validate_dual_track_grounding,
    wrap_untrusted_report_text,
)
from wecom_report_agentic_analysis.storage import CompanyOpsStorage

logger = logging.getLogger(__name__)
_TZ_SHANGHAI = timezone(timedelta(hours=8))


class WeComOpsGraphState(TypedDict, total=False):
    """Shared blackboard state passed across all 4 stages of the LangGraph StateGraph."""

    db_path: str
    config_path: str
    anchor_date: str
    window_days: int
    audit_kind: str
    skip_sync: bool
    dry_run: bool
    output_pdf_path: str
    max_investigation_steps: int
    max_verification_retries: int

    # Stage 1 outputs
    sync_summary: dict[str, Any]
    sync_error: str
    window_report_count: int
    desktop_context: str
    short_ref_to_uuid: dict[str, str]
    short_ref_index: list[dict[str, Any]]
    valid_chairman_task_ids: list[int]
    v3_metrics: dict[str, Any]
    active_goal_tiers: list[str]
    skipped_empty_goal_tiers: list[str]

    # Stage 2 outputs (ReAct loop + synthesis)
    investigation_steps: int
    investigation_notes: list[str]
    pending_tool_calls: list[dict[str, Any]]
    initial_draft_json: dict[str, Any]

    # Stage 3 outputs (Red-Team Critic + Verification)
    verification_retries: int
    verification_errors: list[str]
    redteam_report_json: dict[str, Any]
    verified_report_json: dict[str, Any]
    verification_passed: bool
    verification_degraded: bool
    degraded_notes: list[str]

    # Stage 4 outputs
    audit_id: int
    pdf_result: dict[str, Any]
    delivery_result: dict[str, Any]
    final_status: str


def build_readonly_investigation_tools(
    storage: CompanyOpsStorage,
    *,
    chairman_open_tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Callable[..., Any]]:
    """Build the 4 strictly read-only investigation tools for Stage 2 ReAct drilldown."""

    def query_past_audits(limit: int = 5) -> list[dict[str, Any]]:
        audits = storage.list_alignment_audits(limit=max(1, min(int(limit), 20)))
        return [
            {
                "audit_id": a["id"],
                "audit_kind": a["audit_kind"],
                "period_start": a["period_start"],
                "period_end": a["period_end"],
                "alignment_score": a["alignment_score"],
                "reports_analyzed_count": a["reports_analyzed_count"],
                "executive_brief_md": str(a.get("executive_brief_md") or "")[:600],
            }
            for a in audits
        ]

    def search_historical_reports(
        staff_name: str | None = None,
        keyword: str | None = None,
        report_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        rows = storage.search_reports_readonly(
            staff_name=staff_name,
            keyword=keyword,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            limit=max(1, min(int(limit), 30)),
        )
        out: list[dict[str, Any]] = []
        for rep in rows:
            raw_body = _strip_report_html(rep.plain_text or "")
            fenced = wrap_untrusted_report_text(raw_body, label=f"HIST_{rep.journal_uuid}")
            out.append(
                {
                    "journal_uuid": rep.journal_uuid,
                    "work_date": rep.work_date or rep.report_date,
                    "submitter_name": rep.submitter_name or rep.submitter_userid,
                    "template_name": rep.template_name,
                    "schema_era": rep.schema_era,
                    "fenced_content": fenced,
                }
            )
        return out

    def inspect_staff_and_chairman_tasks(
        staff_name: str | None = None,
        task_id: int | None = None,
    ) -> dict[str, Any]:
        open_tasks = chairman_open_tasks if chairman_open_tasks is not None else storage.read_chairman_open_tasks()
        # Defensive read-only filter ensuring done tasks are never exposed
        active_tasks = [t for t in open_tasks if str(t.get("status") or "").lower() != "done"]
        if task_id is not None:
            matched_tasks = [t for t in active_tasks if int(t.get("id", -1)) == int(task_id)]
        elif staff_name:
            matched_tasks = [
                t
                for t in active_tasks
                if staff_name in str(t.get("owner") or "")
                or staff_name in str(t.get("assignee") or "")
                or staff_name in str(t.get("title") or "")
            ]
        else:
            matched_tasks = active_tasks

        staff_profile = None
        recent_staff_reports: list[dict[str, Any]] = []
        if staff_name:
            prof = ROSTER_BY_NAME.get(staff_name)
            if prof:
                staff_profile = {
                    "name": prof.name,
                    "role_group": prof.role_group,
                    "work_function": prof.work_function.value,
                    "is_high_cost_rd": prof.is_high_cost_rd,
                }
            recs = storage.search_reports_readonly(staff_name=staff_name, limit=10)
            for rep in recs:
                recent_staff_reports.append(
                    {
                        "journal_uuid": rep.journal_uuid,
                        "work_date": rep.work_date or rep.report_date,
                        "template_name": rep.template_name,
                        "fenced_content": wrap_untrusted_report_text(
                            _strip_report_html(rep.plain_text or "")[:500],
                            label=f"STAFF_{rep.journal_uuid}",
                        ),
                    }
                )
        return {
            "staff_profile": staff_profile,
            "recent_staff_reports": recent_staff_reports,
            "chairman_open_tasks": matched_tasks,
        }

    def calculate_date_span_and_ratio(
        start_date: str,
        end_date: str,
        numerator: float = 0.0,
        denominator: float = 0.0,
    ) -> dict[str, Any]:
        d1 = date.fromisoformat(str(start_date)[:10])
        d2 = date.fromisoformat(str(end_date)[:10])
        span_days = max(1, (d2 - d1).days + 1) if d2 >= d1 else 0
        ratio_pct = round(float(numerator) / float(denominator) * 100.0, 2) if float(denominator) != 0.0 else 0.0
        return {
            "start_date": d1.isoformat(),
            "end_date": d2.isoformat(),
            "span_days": span_days,
            "numerator": float(numerator),
            "denominator": float(denominator),
            "ratio_pct": ratio_pct,
        }

    return {
        "query_past_audits": query_past_audits,
        "search_historical_reports": search_historical_reports,
        "inspect_staff_and_chairman_tasks": inspect_staff_and_chairman_tasks,
        "calculate_date_span_and_ratio": calculate_date_span_and_ratio,
    }


def _make_default_bailian_json_caller(model_env_key: str, default_model: str) -> Callable[[str, str], str]:
    from openai import OpenAI

    api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    base_url = (os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
    model_name = (os.getenv(model_env_key) or os.getenv("PRODUCER_MODEL") or default_model).strip()
    if not api_key:
        raise RuntimeError("Missing DASHSCOPE_API_KEY in environment for live LLM execution.")

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180.0)

    def _call(sys_prompt: str, user_prompt: str) -> str:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=14000,
            response_format={"type": "json_object"},
        )
        return (resp.choices[0].message.content or "").strip()

    return _call


def _default_sync_runner(storage: CompanyOpsStorage, cfg: Any, anchor_date: str) -> dict[str, Any]:
    from wecom_report_agentic_analysis.wecom_journal_client import WeComJournalClient

    corpid = (os.getenv("WECOM_OPS_CORP_ID") or os.getenv("WECOM_CORP_ID") or "").strip()
    secret = (os.getenv("WECOM_OPS_APP_SECRET") or os.getenv("WECOM_APP_SECRET") or "").strip()
    if not corpid or not secret:
        raise RuntimeError("Missing WECOM_OPS_CORP_ID / WECOM_OPS_APP_SECRET for live sync.")
    client = WeComJournalClient(corpid, secret, timeout=15.0, max_retries=2, request_interval_sec=0.12)
    try:
        res = client.sync_with_watermarks(
            storage,
            templates=ALL_WECOM_TEMPLATES,
            initial_backfill_start_date=cfg.initial_backfill_start_date,
            end_date=anchor_date,
            effective_date=cfg.new_template_effective_date,
        )
        return res.model_dump()
    finally:
        client.close()


def build_wecom_ops_graph(
    *,
    storage: CompanyOpsStorage | None = None,
    brain_investigate_fn: Callable[[str, str, int], dict[str, Any]] | None = None,
    brain_synthesize_fn: Callable[[str, str], dict[str, Any] | str] | None = None,
    redteam_critic_fn: Callable[[str, str], dict[str, Any] | str] | None = None,
    sync_runner_fn: Callable[..., dict[str, Any]] | None = None,
    smtp_sender: Any | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Compile the 4-stage LangGraph StateGraph (works both headless and in LangGraph Studio)."""

    def _get_storage(state: WeComOpsGraphState) -> CompanyOpsStorage:
        if storage is not None:
            return storage
        db_p = state.get("db_path") or "/opt/wechat-agent/data/app.db"
        return CompanyOpsStorage(Path(db_p))

    def _get_cfg(state: WeComOpsGraphState) -> Any:
        return load_strategic_goals_config(state.get("config_path") or None)

    def node_check_watermark_and_sync(state: WeComOpsGraphState) -> dict[str, Any]:
        anchor = state.get("anchor_date") or datetime.now(_TZ_SHANGHAI).date().isoformat()
        if state.get("skip_sync", False):
            return {"anchor_date": anchor, "sync_summary": {"skipped": True}, "sync_error": ""}
        st = _get_storage(state)
        cfg = _get_cfg(state)
        try:
            runner = sync_runner_fn or _default_sync_runner
            summary = runner(st, cfg, anchor)
            return {"anchor_date": anchor, "sync_summary": summary, "sync_error": ""}
        except Exception as exc:
            logger.error("Stage 1 sync failed: %s", exc)
            return {"anchor_date": anchor, "sync_error": str(exc), "final_status": "sync_failed"}

    def route_after_sync(state: WeComOpsGraphState) -> str:
        if state.get("sync_error"):
            return END
        return "assemble_desktop_context"

    def node_assemble_desktop_context(state: WeComOpsGraphState) -> dict[str, Any]:
        st = _get_storage(state)
        cfg = _get_cfg(state)
        anchor = state.get("anchor_date") or datetime.now(_TZ_SHANGHAI).date().isoformat()
        window_days = int(state.get("window_days") or 30)
        anchor_d = date.fromisoformat(anchor[:10])
        win_start = (anchor_d - timedelta(days=max(1, window_days) - 1)).isoformat()

        all_reports = st.list_reports(end_date=anchor)
        v3_metrics = compute_v3_dual_track_metrics(
            all_reports,
            anchor_date=anchor,
            window_days=window_days,
            effective_date=cfg.new_template_effective_date,
        )
        window_reports = [
            r for r in all_reports if win_start <= (r.work_date or r.report_date) <= anchor
        ]
        if not window_reports:
            return {
                "window_report_count": 0,
                "v3_metrics": v3_metrics,
                "active_goal_tiers": cfg.active_tiers(),
                "skipped_empty_goal_tiers": cfg.empty_tiers(),
                "final_status": "empty_window",
            }

        chairman_open = st.read_chairman_open_tasks()
        past_audits = st.list_alignment_audits(limit=5)
        desktop_prompt, short_ref_to_uuid, short_ref_index = build_dual_track_desktop_context(
            window_reports=window_reports,
            goals_config=cfg,
            chairman_open_tasks=chairman_open,
            v3_metrics=v3_metrics,
            period_start=win_start,
            period_end=anchor,
            past_audit_summaries=past_audits,
        )
        valid_task_ids = [int(t["id"]) for t in chairman_open if t.get("id") is not None]
        return {
            "window_report_count": len(window_reports),
            "desktop_context": desktop_prompt,
            "short_ref_to_uuid": short_ref_to_uuid,
            "short_ref_index": short_ref_index,
            "valid_chairman_task_ids": valid_task_ids,
            "v3_metrics": v3_metrics,
            "active_goal_tiers": cfg.active_tiers(),
            "skipped_empty_goal_tiers": cfg.empty_tiers(),
            "investigation_steps": 0,
            "investigation_notes": [],
            "pending_tool_calls": [],
            "verification_retries": 0,
            "verification_errors": [],
            "max_investigation_steps": int(state.get("max_investigation_steps") or cfg.max_investigation_steps),
            "max_verification_retries": int(state.get("max_verification_retries") or cfg.max_verification_retries),
        }

    def route_after_desktop(state: WeComOpsGraphState) -> str:
        if int(state.get("window_report_count") or 0) <= 0:
            return END
        return "flagship_brain_investigate"

    def node_flagship_brain_investigate(state: WeComOpsGraphState) -> dict[str, Any]:
        step = int(state.get("investigation_steps") or 0)
        max_steps = int(state.get("max_investigation_steps") or 18)
        notes = list(state.get("investigation_notes") or [])

        if step >= max_steps:
            return {"pending_tool_calls": []}

        prompt = state.get("desktop_context", "")
        if notes:
            prompt += "\n\n## 已完成的只读查证记录\n" + "\n".join(notes)

        if brain_investigate_fn is not None:
            decision = brain_investigate_fn(MAIN_BRAIN_INVESTIGATE_SYSTEM_PROMPT, prompt, step)
        else:
            caller = _make_default_bailian_json_caller("OPS_AUDIT_MODEL", "qwen-max")
            raw = caller(
                MAIN_BRAIN_INVESTIGATE_SYSTEM_PROMPT
                + '\n请仅输出 JSON: {"done": true/false, "tool_calls": [{"name": "...", "args": {...}}], "note": "..."}',
                prompt,
            )
            decision = _parse_llm_json_payload(raw)

        note_txt = str(decision.get("note") or "").strip()
        if note_txt:
            notes.append(f"[研判轮次 {step + 1}] {note_txt}")

        done = bool(decision.get("done", True))
        tool_calls = list(decision.get("tool_calls") or [])
        if done or not tool_calls:
            return {"pending_tool_calls": [], "investigation_notes": notes}
        return {"pending_tool_calls": tool_calls, "investigation_notes": notes}

    def route_after_investigate(state: WeComOpsGraphState) -> str:
        step = int(state.get("investigation_steps") or 0)
        max_steps = int(state.get("max_investigation_steps") or 18)
        if state.get("pending_tool_calls") and step < max_steps:
            return "readonly_tools"
        return "flagship_brain_synthesize"

    def node_readonly_tools(state: WeComOpsGraphState) -> dict[str, Any]:
        st = _get_storage(state)
        tools = build_readonly_investigation_tools(st)
        step = int(state.get("investigation_steps") or 0)
        notes = list(state.get("investigation_notes") or [])

        for tc in state.get("pending_tool_calls") or []:
            name = str(tc.get("name") or "").strip()
            args = dict(tc.get("args") or {})
            if name not in tools:
                notes.append(f"[工具拒绝] 未在白名单内的只读工具: {name}")
                continue
            try:
                res = tools[name](**args)
                notes.append(f"[只读工具 {name} 结果] {json.dumps(res, ensure_ascii=False, default=str)}")
            except Exception as exc:
                notes.append(f"[只读工具 {name} 异常] {exc}")

        return {
            "investigation_steps": step + 1,
            "investigation_notes": notes,
            "pending_tool_calls": [],
        }

    def route_after_tools(state: WeComOpsGraphState) -> str:
        step = int(state.get("investigation_steps") or 0)
        max_steps = int(state.get("max_investigation_steps") or 18)
        if step < max_steps:
            return "flagship_brain_investigate"
        return "flagship_brain_synthesize"

    def node_flagship_brain_synthesize(state: WeComOpsGraphState) -> dict[str, Any]:
        notes = state.get("investigation_notes") or []
        prompt = state.get("desktop_context", "")
        if notes:
            prompt += "\n\n## 阶段二只读翻查核实记录\n" + "\n".join(notes)

        if brain_synthesize_fn is not None:
            raw = brain_synthesize_fn(MAIN_BRAIN_SYNTHESIZE_SYSTEM_PROMPT, prompt)
        else:
            caller = _make_default_bailian_json_caller("OPS_AUDIT_MODEL", "qwen-max")
            raw = caller(MAIN_BRAIN_SYNTHESIZE_SYSTEM_PROMPT, prompt)

        draft_dict = _parse_llm_json_payload(raw)
        return {"initial_draft_json": draft_dict}

    def node_redteam_critic(state: WeComOpsGraphState) -> dict[str, Any]:
        notes = state.get("investigation_notes") or []
        draft_json = state.get("initial_draft_json") or {}
        ver_errors = state.get("verification_errors") or []

        # 100% shared evidence: raw desktop + investigation notes + flagship initial draft (zero telephone-game loss)
        parts = [
            state.get("desktop_context", ""),
            "\n\n## 阶段二只读翻查核实记录（100% 共享原件）\n" + ("\n".join(notes) if notes else "（无额外翻查记录）"),
            "\n\n## 阶段二旗舰主脑双轨诊断初稿（供独立红队核账挑刺）\n```json\n"
            + json.dumps(draft_json, ensure_ascii=False, indent=2)
            + "\n```",
        ]
        if ver_errors:
            parts.append(
                "\n\n## 【客观证据核验打回纠偏清单 — 请逐条精确修正】\n"
                + "\n".join(f"- {e}" for e in ver_errors)
            )
        redteam_prompt = "\n".join(parts)

        if redteam_critic_fn is not None:
            raw = redteam_critic_fn(REDTEAM_CRITIC_SYSTEM_PROMPT, redteam_prompt)
        else:
            caller = _make_default_bailian_json_caller("CRITIC_MODEL", "qwen-max")
            raw = caller(REDTEAM_CRITIC_SYSTEM_PROMPT, redteam_prompt)

        parsed = _parse_llm_json_payload(raw)
        return {"redteam_report_json": parsed}

    def node_verify_and_grade_alerts(state: WeComOpsGraphState) -> dict[str, Any]:
        retries = int(state.get("verification_retries") or 0)
        max_retries = int(state.get("max_verification_retries") or 2)
        short_ref_to_uuid = dict(state.get("short_ref_to_uuid") or {})
        valid_task_ids = set(state.get("valid_chairman_task_ids") or [])
        raw_rt = state.get("redteam_report_json") or {}

        try:
            parsed_report = DualTrackAuditReport.model_validate(raw_rt)
        except Exception as exc:
            err_msg = f"双轨报告 JSON/Schema 校验失败: {exc}"
            if retries < max_retries:
                return {
                    "verification_passed": False,
                    "verification_degraded": False,
                    "verification_retries": retries + 1,
                    "verification_errors": [err_msg],
                }
            return {
                "verification_passed": False,
                "verification_degraded": False,
                "verification_errors": [err_msg],
                "final_status": "verification_failed",
            }

        strict_check = validate_dual_track_grounding(
            parsed_report,
            short_ref_to_uuid=short_ref_to_uuid,
            valid_chairman_task_ids=valid_task_ids,
            allow_degrade_minor=False,
        )
        if strict_check.passed and strict_check.hydrated_report is not None:
            return {
                "verification_passed": True,
                "verification_degraded": False,
                "verification_errors": [],
                "degraded_notes": [],
                "verified_report_json": strict_check.hydrated_report.model_dump(mode="json"),
            }

        if retries < max_retries:
            return {
                "verification_passed": False,
                "verification_degraded": False,
                "verification_retries": retries + 1,
                "verification_errors": strict_check.failures,
            }

        # Retries exhausted: try graceful degradation for minor unverified alerts without blocking delivery
        degraded_check = validate_dual_track_grounding(
            parsed_report,
            short_ref_to_uuid=short_ref_to_uuid,
            valid_chairman_task_ids=valid_task_ids,
            allow_degrade_minor=True,
        )
        if degraded_check.passed and degraded_check.hydrated_report is not None:
            return {
                "verification_passed": True,
                "verification_degraded": True,
                "verification_errors": [],
                "degraded_notes": degraded_check.degraded_notes,
                "verified_report_json": degraded_check.hydrated_report.model_dump(mode="json"),
            }

        return {
            "verification_passed": False,
            "verification_degraded": False,
            "verification_errors": degraded_check.failures,
            "final_status": "verification_failed",
        }

    def route_after_verify(state: WeComOpsGraphState) -> str:
        if state.get("verification_passed"):
            return "archive_render_and_deliver"
        if state.get("final_status") == "verification_failed":
            return END
        return "redteam_critic"

    def node_archive_render_and_deliver(state: WeComOpsGraphState) -> dict[str, Any]:
        st = _get_storage(state)
        cfg = _get_cfg(state)
        anchor = state.get("anchor_date") or datetime.now(_TZ_SHANGHAI).date().isoformat()
        report_obj = DualTrackAuditReport.model_validate(state["verified_report_json"])

        audit_id = st.save_alignment_audit(
            report_obj,
            reports_analyzed_count=int(state.get("window_report_count") or 0),
        )

        default_pdf = (
            Path(__file__).resolve().parent
            / "reports"
            / f"维恩科仪经营漏洞预警与战略诊断周报_{anchor.replace('-', '')}.pdf"
        )
        pdf_target = Path(state.get("output_pdf_path") or default_pdf)
        pdf_meta = render_executive_pdf(
            report=report_obj,
            metrics=state.get("v3_metrics") or {},
            output_pdf_path=pdf_target,
            short_ref_index=state.get("short_ref_index") or [],
            config_meta={
                "company_name": str((cfg.company or {}).get("name") or "维恩科仪"),
                "new_template_effective_date": cfg.new_template_effective_date,
            },
            also_save_html=False,
        )

        iso_year, iso_week, _ = date.fromisoformat(anchor[:10]).isocalendar()
        period_key = f"{report_obj.audit_kind}-{iso_year}-W{iso_week:02d}-{anchor}"
        delivery_res = deliver_weekly_alert_email(
            storage=st,
            period_key=period_key,
            report=report_obj,
            metrics=state.get("v3_metrics") or {},
            pdf_path=pdf_target,
            report_date=anchor,
            dry_run=bool(state.get("dry_run", False)),
            smtp_sender=smtp_sender,
        )
        return {
            "audit_id": audit_id,
            "pdf_result": pdf_meta,
            "delivery_result": delivery_res,
            "final_status": "completed",
        }

    sg = StateGraph(WeComOpsGraphState)
    sg.add_node("check_watermark_and_sync", node_check_watermark_and_sync)
    sg.add_node("assemble_desktop_context", node_assemble_desktop_context)
    sg.add_node("flagship_brain_investigate", node_flagship_brain_investigate)
    sg.add_node("readonly_tools", node_readonly_tools)
    sg.add_node("flagship_brain_synthesize", node_flagship_brain_synthesize)
    sg.add_node("redteam_critic", node_redteam_critic)
    sg.add_node("verify_and_grade_alerts", node_verify_and_grade_alerts)
    sg.add_node("archive_render_and_deliver", node_archive_render_and_deliver)

    sg.add_edge(START, "check_watermark_and_sync")
    sg.add_conditional_edges(
        "check_watermark_and_sync",
        route_after_sync,
        {"assemble_desktop_context": "assemble_desktop_context", END: END},
    )
    sg.add_conditional_edges(
        "assemble_desktop_context",
        route_after_desktop,
        {"flagship_brain_investigate": "flagship_brain_investigate", END: END},
    )
    sg.add_conditional_edges(
        "flagship_brain_investigate",
        route_after_investigate,
        {"readonly_tools": "readonly_tools", "flagship_brain_synthesize": "flagship_brain_synthesize"},
    )
    sg.add_conditional_edges(
        "readonly_tools",
        route_after_tools,
        {"flagship_brain_investigate": "flagship_brain_investigate", "flagship_brain_synthesize": "flagship_brain_synthesize"},
    )
    sg.add_edge("flagship_brain_synthesize", "redteam_critic")
    sg.add_edge("redteam_critic", "verify_and_grade_alerts")
    sg.add_conditional_edges(
        "verify_and_grade_alerts",
        route_after_verify,
        {
            "archive_render_and_deliver": "archive_render_and_deliver",
            "redteam_critic": "redteam_critic",
            END: END,
        },
    )
    sg.add_edge("archive_render_and_deliver", END)

    return sg.compile(checkpointer=checkpointer)
