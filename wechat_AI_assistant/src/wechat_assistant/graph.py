"""v3.0 Single-Brain Flagship Agent (Model-First, Plan A) over a 3-node LangGraph & minimal safety chassis.

Architecture:
1. `context_intake` (Deterministic Chassis): assemble full workspace/dialogue/pending context,
   inject deterministic Calendar Anchor Table (yesterday/today+weekday/this week/next week),
   and handle minimal instant offline emergency buttons (`1`/`2`/`0`/`撤销`/`看板`/`负荷`/exact shortcuts).
2. `flagship_brain` (Single Frontier LLM `qwen3.8-max`, 0 fast router / 0 second critic LLM):
   native OpenAI tool calling (`search_archive`, `read_doc_pages`, `check_workload_and_schedule`,
   `calc_business_date`) producing a unified `AgentDecision` JSON (supporting 1-step revise+commit
   and compound multi-task direct operations). Runs minimal 3-rule `objective_proposal_guard`
   with at most 1 self-correction retry if an objective violation (invalid date / Outlook CC leak) occurs.
3. `action_executor` (Deterministic Safe Chassis): enforces `ApprovalToken`, SQLite atomic commits
   with 24h undo snapshots, Outlook `conversationId` auto-backfill & `source_channel` tagging,
   concise WeCom card rendering (zero internal jargon), and zero-secret-leak guardrails.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import uuid
import weakref
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from wechat_assistant.config import DashScopeLLMGateway, Settings, assert_no_secrets_leaked, redact_secrets, today_local
from wechat_assistant.context_assembler import ContextAssembler, extract_topic_tags
from wechat_assistant.nodes.critic_rules import objective_proposal_guard
from wechat_assistant.prompts.system_prompts import EPISODE_SUMMARY_PROMPT, FLAGSHIP_BRAIN_PROMPT
from wechat_assistant.schemas import (
    ActionMutation,
    AgentDecision,
    ListType,
    TaskFieldUpdate,
    TaskNoteAppend,
    TaskStatusChange,
    TriageProposal,
)
from wechat_assistant.storage.db import Database
from wechat_assistant.storage.extractors import extract_document_pages
from wechat_assistant.tools.guard import ApprovalToken, before_tool_callback
from wechat_assistant.tools.memory_tools import hybrid_search, read_doc_pages
from wechat_assistant.tools.onedrive_tools import OneDrive21VianetClient
from wechat_assistant.tools.schedule_tools import calc_business_date, check_workload_and_schedule

logger = logging.getLogger("uvicorn.error")


class EpisodeSummary(BaseModel):
    """Semantic rolling cross-day summary produced asynchronously."""

    summary: str = Field(min_length=10, max_length=1200)


class WorkflowState(TypedDict, total=False):
    thread_id: str
    raw_text: str
    sender: str
    external_msg_id: str
    attachments: list[dict[str, Any]]
    source_ids: list[int]
    ingested_att_text: str
    calendar_anchor_text: str
    rolling_summary_text: str
    project_context_text: str
    dialogue_context_text: str
    workspace_context_text: str
    pending_context_text: str
    has_pending_proposal: bool
    evidence_text: str
    tool_outputs_text: str
    force_work_triage: bool
    emergency_decision: dict[str, Any] | None
    decision: dict[str, Any]
    guard_issues: list[str]
    guard_fix_note: str
    loop_count: int
    proposal_id: int | None
    reply_text: str
    intent: str
    trajectory: list[str]


_WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def build_calendar_anchor_text(today: date | None = None) -> str:
    """Build deterministic calendar fact table so relative dates ('昨天'/'本周五'/'下周三') are 100% exact."""
    d = today or today_local()
    yesterday = d - timedelta(days=1)
    tomorrow = d + timedelta(days=1)
    this_monday = d - timedelta(days=d.weekday())
    next_monday = this_monday + timedelta(days=7)

    this_week = "、".join(
        f"本{_WEEKDAY_CN[i]}={(this_monday + timedelta(days=i)).isoformat()}"
        for i in range(7)
    )
    next_week = "、".join(
        f"下{_WEEKDAY_CN[i]}={(next_monday + timedelta(days=i)).isoformat()}"
        for i in range(7)
    )
    next_biz = calc_business_date(d.isoformat(), 1)
    return (
        f"昨天={yesterday.isoformat()}（{_WEEKDAY_CN[yesterday.weekday()]}）｜"
        f"今天={d.isoformat()}（{_WEEKDAY_CN[d.weekday()]}）｜"
        f"明天={tomorrow.isoformat()}（{_WEEKDAY_CN[tomorrow.weekday()]}）｜"
        f"下一工作日={next_biz}\n"
        f"本周日历：{this_week}\n"
        f"下周日历：{next_week}"
    )


_MISSING_FIELD_LABELS: dict[str, str] = {
    "project_name": "归属项目",
    "deliverable": "目标与交付成果",
    "owner": "负责人",
    "assignee": "实施人",
    "planned_end_at": "目标截止时间",
}

_CHANNEL_LABELS: dict[str, str] = {
    "mail_in": "邮件",
    "mail_out": "邮件",
    "wechat": "微信",
    "web": "驾驶舱",
}

_SYSTEM_CITATION_NOISE = (
    "用户输入",
    "微信消息",
    "审计",
    "整改",
    "工具输出",
    "check_workload",
    "calc_business_date",
    "日历锚点",
)


def _short_ts(ts: str) -> str:
    clean = (ts or "").strip()
    if len(clean) >= 16 and clean[4:5] == "-" and clean[7:8] == "-":
        return clean[5:16]
    return clean


def _format_party_flow(from_party: str, to_party: str, cc_parties: list[str] | None = None) -> str:
    base = f"{from_party}→{to_party}" if (from_party and to_party) else (from_party or to_party or "")
    cc = [c.strip() for c in (cc_parties or []) if c and c.strip()]
    if cc and base:
        return f"{base}(抄送:{','.join(cc)})"
    if cc:
        return f"抄送:{','.join(cc)}"
    return base


def _filter_real_citations(citations: list[str] | None) -> list[str]:
    """Keep only genuine document/email citations, stripping internal system noise."""
    real: list[str] = []
    for raw in citations or []:
        c = str(raw or "").strip()
        if not c:
            continue
        low = c.lower()
        if any(noise.lower() in low for noise in _SYSTEM_CITATION_NOISE):
            continue
        if c not in real:
            real.append(c)
    return real


def format_decision_card(
    proposal_id: int,
    proposal: TriageProposal,
    cockpit_url: str = "",
    critic_issues: list[str] | None = None,
    *,
    is_mail_batch: bool = False,
) -> str:
    """Format a clean, concise v3.0 flat independent task-card HITL preview for WeChat."""
    clean_headline = re.sub(
        r"^(?:确认\s*#?\d*\s*[｜|:\-：]\s*)+",
        "",
        (proposal.headline or "").strip(),
    ).strip() or (proposal.headline or "").strip()

    lines = [f"📋 确认 #{proposal_id}｜{clean_headline}"]
    is_single_simple_task = (
        len(proposal.actions) == 1
        and not proposal.task_updates
        and not proposal.fyi_notices
    )
    # Hide repetitive prose summary on single-task WeChat cards; keep on multi-item / mail batches
    if proposal.executive_summary and (is_mail_batch or not is_single_simple_task):
        lines.append(proposal.executive_summary)

    missing_summary: list[str] = []
    if proposal.actions:
        lines.append("\n【一、拟新建独立任务卡】")
        for idx, act in enumerate(proposal.actions, 1):
            owner_str = (act.owner or "本人").strip() or "本人"
            raw_assignee = (act.assignee or "").strip()
            if raw_assignee:
                assignee_str = raw_assignee
            elif "assignee" in (act.missing_required_fields or []) or (is_mail_batch and act.chairman_role == "cc_observer"):
                assignee_str = "【待补齐】"
            else:
                assignee_str = owner_str
            ext_str = (act.external_partner or "").strip() or "无"
            deliverable_str = (act.deliverable or "").strip() or act.title
            stage_str = (act.milestone_stage or "已启动").strip()
            start_str = (act.planned_start_at or "").strip() or "-"
            end_str = (act.planned_end_at or "").strip()
            if end_str:
                try:
                    span_days = max(1, (date.fromisoformat(end_str[:10]) - date.fromisoformat(start_str[:10])).days + 1)
                    sched_str = f"开始 {start_str} → 目标截止：{end_str}（{span_days}天）"
                except ValueError:
                    sched_str = f"开始 {start_str} → 目标截止：{end_str}"
            else:
                sched_str = f"开始 {start_str} → 目标截止：【待补齐】"
            hr_note = f"｜指定工时 {act.estimated_hours}h" if act.estimated_hours and act.estimated_hours > 0 else ""

            lines.append(
                f"▸ 新任务 {idx}：{act.title}"
                f"（归属：{act.project_name} / {act.work_domain.value}｜{act.priority.value}）"
            )
            lines.append(f"  1）目标与交付成果：{deliverable_str}")
            if act.timeline:
                lines.append(f"  2）当前进度与往来沟通：{stage_str}")
                for entry in act.timeline[-3:]:
                    ch_label = _CHANNEL_LABELS.get(entry.channel, "沟通")
                    who = _format_party_flow(entry.from_party, entry.to_party, entry.cc_parties)
                    meta_parts = [p for p in (_short_ts(entry.timestamp), ch_label, who) if p]
                    lines.append(f"     - [{'｜'.join(meta_parts)}] {entry.summary}")
            else:
                lines.append(f"  2）当前进度与往来沟通：{stage_str}")
            lines.append(
                f"  3）责任分工：负责人：{owner_str} ｜ 实施人：{assignee_str} ｜ 外部协作：{ext_str}"
            )
            lines.append(f"  4）时间排期：{sched_str}{hr_note}")
            blocker_txt = (act.blocker_note or "").strip()
            files_txt = ", ".join(act.linked_files) if act.linked_files else ""
            has_conv = bool(act.mail_conversation_ids)
            if blocker_txt or files_txt or has_conv:
                tail_parts = [blocker_txt or "无"]
                if files_txt:
                    tail_parts.append(f"档案：{files_txt}")
                if has_conv:
                    tail_parts.append("会话已自动绑定")
                lines.append(f"  5）卡点与关联档案：{' ｜ '.join(tail_parts)}")
            if act.comments:
                cmt_txt = "；".join(c.content for c in act.comments[-2:])
                lines.append(f"  6）补充备注（Comments）：{cmt_txt}")
            if act.ceo_evaluation:
                ev_txt = act.ceo_evaluation[-1].content
                lines.append(f"  7）CEO 评价：{ev_txt}")

            if act.missing_required_fields:
                labels = [_MISSING_FIELD_LABELS.get(f, f) for f in act.missing_required_fields]
                missing_summary.append(f"- 新任务 {idx} 缺少：{'、'.join(labels)}")

    if proposal.task_updates:
        lines.append("\n【二、拟追加到已有在途任务的往来沟通】")
        for upd in proposal.task_updates:
            tl = upd.timeline_entry
            title_part = f"《{upd.target_task_title}》" if upd.target_task_title else ""
            ch_label = _CHANNEL_LABELS.get(tl.channel, "沟通")
            who = _format_party_flow(tl.from_party, tl.to_party, tl.cc_parties)
            meta_parts = [p for p in (_short_ts(tl.timestamp), ch_label, who) if p]
            stage_note = f"（状态更新：{upd.milestone_stage_update}）" if upd.milestone_stage_update else ""
            lines.append(f"- 归入 任务 #{upd.target_task_id}{title_part}：")
            lines.append(f"  ↳ [{'｜'.join(meta_parts)}] {tl.summary}{stage_note}")

    if proposal.fyi_notices:
        lines.append("\n【三、纯知会与团队进展同步】")
        for fyi in proposal.fyi_notices:
            who = _format_party_flow(fyi.from_party, fyi.to_party)
            meta_parts = [p for p in (_short_ts(fyi.timestamp), "抄送知会", who) if p]
            lines.append(f"- [{'｜'.join(meta_parts)}] {fyi.summary}")

    if missing_summary:
        lines.append("\n⚠️ 缺失必填提示：\n" + "\n".join(missing_summary))
    if proposal.overload_warning:
        lines.append(f"\n⚠️ 负荷提醒：{proposal.overload_warning}")
    if critic_issues:
        clean_issues = [str(x).strip() for x in critic_issues if str(x).strip()]
        if clean_issues:
            lines.append(f"\n⚠️ 审计待人工复核点：{'；'.join(clean_issues)}")
    real_citations = _filter_real_citations(proposal.citations)
    if real_citations:
        lines.append(f"\n📎 证据出处：{'; '.join(real_citations)}")
    lines.append("\n👉 回复 1 确认落盘 ｜ 2 仅存想法 ｜ 0 作废 ｜ 或直接回复自然语言补全/调整（如“截止暂定本周五，确认落盘”）")
    if cockpit_url:
        lines.append(f"📊 驾驶舱：{cockpit_url}")
    return "\n".join(lines)


def _format_pure_fyi_message(proposal: TriageProposal) -> str:
    """Format a read-only pure-FYI mail/message summary without creating a blocking pending card."""
    clean_headline = re.sub(
        r"^(?:确认\s*#?\d*\s*[｜|:\-：]\s*)+",
        "",
        (proposal.headline or "").strip(),
    ).strip() or "团队进展与抄送知会"
    lines = [f"📌 {clean_headline}（纯知会，不建任务卡）"]
    if proposal.fyi_notices:
        lines.append("\n【纯知会与团队进展同步】")
        for fyi in proposal.fyi_notices:
            who = _format_party_flow(fyi.from_party, fyi.to_party)
            meta_parts = [p for p in (_short_ts(fyi.timestamp), "抄送知会", who) if p]
            lines.append(f"- [{'｜'.join(meta_parts)}] {fyi.summary}")
    elif proposal.executive_summary:
        lines.append(proposal.executive_summary)
    return "\n".join(lines)


_UNTRUSTED_DATA_BLOCK_RE = re.compile(
    r"\[UNTRUSTED_EXTERNAL_DATA\].*?\[/UNTRUSTED_EXTERNAL_DATA\]",
    flags=re.DOTALL | re.IGNORECASE,
)
_TRUSTED_META_BLOCK_RE = re.compile(
    r"\[SYSTEM_TRUSTED_MAIL_META\](.*?)\[/SYSTEM_TRUSTED_MAIL_META\]",
    flags=re.DOTALL | re.IGNORECASE,
)


def _extract_trusted_mail_conv_map(raw_text: str) -> tuple[dict[str, str], list[str]]:
    """Parse `MAIL-k -> conversationId` ONLY from trusted system metadata blocks outside untrusted content."""
    ref_map: dict[str, str] = {}
    ordered_convs: list[str] = []
    trusted_only = _UNTRUSTED_DATA_BLOCK_RE.sub("", raw_text or "")
    for block in _TRUSTED_META_BLOCK_RE.findall(trusted_only):
        m_ref = re.search(r"邮件编号：(MAIL-\d+)", block)
        m_cid = re.search(r"会话号\(conversationId\)：(\S+)", block)
        if m_cid:
            cid = m_cid.group(1).strip()
            if cid:
                if cid not in ordered_convs:
                    ordered_convs.append(cid)
                if m_ref:
                    ref_map[m_ref.group(1).strip()] = cid
    return ref_map, ordered_convs


def _backfill_mail_conversation_ids(proposal: TriageProposal, raw_text: str) -> TriageProposal:
    """Deterministically resolve `MAIL-k` refs and backfill real Graph `conversationId` onto mail actions."""
    ref_map, ordered_convs = _extract_trusted_mail_conv_map(raw_text)
    if not ordered_convs:
        return proposal

    for idx, act in enumerate(proposal.actions):
        resolved_cids: list[str] = []
        for raw_cid in list(act.mail_conversation_ids or []):
            clean = str(raw_cid or "").strip()
            mapped = ref_map.get(clean, clean)
            if mapped and mapped not in resolved_cids:
                resolved_cids.append(mapped)
        for tl in act.timeline or []:
            raw_tl_cid = str(tl.mail_conversation_id or "").strip()
            if raw_tl_cid:
                mapped_tl = ref_map.get(raw_tl_cid, raw_tl_cid)
                tl.mail_conversation_id = mapped_tl
                if mapped_tl and mapped_tl not in resolved_cids:
                    resolved_cids.append(mapped_tl)
        if not resolved_cids:
            if len(ordered_convs) == 1:
                resolved_cids.append(ordered_convs[0])
            elif len(proposal.actions) == 1:
                resolved_cids.extend(ordered_convs)
            elif idx < len(ordered_convs):
                resolved_cids.append(ordered_convs[idx])
        act.mail_conversation_ids = resolved_cids

    for upd in proposal.task_updates or []:
        raw_tl_cid = str(upd.timeline_entry.mail_conversation_id or "").strip()
        if raw_tl_cid in ref_map:
            upd.timeline_entry.mail_conversation_id = ref_map[raw_tl_cid]
        elif not raw_tl_cid and len(ordered_convs) == 1:
            upd.timeline_entry.mail_conversation_id = ordered_convs[0]

    return proposal


_COCKPIT_EXACT = {"看板", "驾驶舱", "页面", "dashboard"}
_WORKLOAD_EXACT = {"负荷", "待办", "今日待办", "todo"}


def _emergency_button_decision(raw_text: str, pending: dict[str, Any] | None) -> tuple[AgentDecision, str] | None:
    """Pure single-button offline emergency controls (Model-First: ZERO natural-language regexes).

    Guarantees exact control buttons (`1`/`2`/`0`/`撤销`/`看板`/`负荷`) keep working instantly
    with 0 LLM calls even during full DashScope 503 outages.
    All natural Chinese utterances, relative dates, `#ID` notes/updates/check-ins, and compound
    instructions go straight to the flagship LLM brain (`qwen3.8-max`).
    """
    text = (raw_text or "").strip()
    if not text:
        return None
    low = text.lower()

    if text in _COCKPIT_EXACT or low == "dashboard":
        return AgentDecision(mode="open_cockpit"), "open_cockpit"
    if text in _WORKLOAD_EXACT or low == "todo":
        return AgentDecision(mode="show_workload"), "show_workload"
    if text == "撤销":
        return AgentDecision(mode="direct_ops", undo_last=True), "undo"
    if pending and text in {"1", "确认"}:
        return AgentDecision(mode="confirm_pending"), "confirm_pending"
    if pending and text in {"2", "仅存想法"}:
        return AgentDecision(mode="confirm_pending", ideas_only=True), "confirm_pending"
    if pending and text in {"0", "取消", "放弃", "作废"}:
        return AgentDecision(mode="discard_pending"), "discard_pending"

    return None


class ChiefOfStaffEngine:
    """v3.0 Single-Brain Flagship Agent orchestrating DB, tools, OneDrive, and a 3-node LangGraph."""

    semantic_summaries: bool = True
    background_summaries: bool = True

    def __init__(
        self,
        *,
        settings: Settings,
        db: Database,
        gateway: DashScopeLLMGateway,
        onedrive: OneDrive21VianetClient | None = None,
        checkpoints_path: str | Path | None = None,
        magic_link_factory: Callable[[], str] | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        self.gateway = gateway
        self.onedrive = onedrive
        self.context_assembler = ContextAssembler(self.db)
        self.magic_link_factory = magic_link_factory or (lambda: settings.web_public_base_url)

        ckpt_file = Path(checkpoints_path or Path(db.db_path).parent / "checkpoints.db")
        ckpt_file.parent.mkdir(parents=True, exist_ok=True)
        self._ckpt_conn = sqlite3.connect(str(ckpt_file), check_same_thread=False)
        self._ckpt_finalizer = weakref.finalize(self, self._ckpt_conn.close)
        self._turn_lock = threading.RLock()
        self._progress_cb: Callable[[str], None] | None = None
        self.checkpointer = SqliteSaver(self._ckpt_conn)
        self.graph = self._build_graph()

    def close(self) -> None:
        """Close the internal SQLite checkpointer connection cleanly."""
        self._ckpt_finalizer()

    def _emit_progress(self, stage_label: str) -> None:
        cb = self._progress_cb
        if cb is not None:
            try:
                cb(stage_label)
            except Exception as exc:
                logger.warning("Progress callback error: %s", type(exc).__name__)

    @staticmethod
    def _cleanup_pending_files(pending_files: list[dict[str, Any]]) -> None:
        for pf in pending_files or []:
            raw_path = str(pf.get("path") or "").strip()
            if not raw_path:
                continue
            try:
                p = Path(raw_path)
                if p.exists() and p.is_file():
                    p.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Failed to cleanup tmp attachment %s: %s", raw_path, type(exc).__name__)

    def _record_latest_call(self, rec: Any) -> None:
        self.db.record_model_call(
            tier=rec.tier,
            model=rec.model,
            prompt_tokens=rec.prompt_tokens,
            completion_tokens=rec.completion_tokens,
            reasoning_tokens=rec.reasoning_tokens,
            latency_ms=rec.latency_ms,
            success=rec.success,
        )

    def _safe_sync_onedrive(self) -> tuple[bool, str]:
        if self.onedrive is None:
            return True, ""
        try:
            urls = self.onedrive.sync_all_lists(self.db)
            return True, urls.get("01_今日与行动待办.md", "")
        except Exception as exc:
            logger.warning(
                "OneDrive board sync error: %s",
                redact_secrets(f"{type(exc).__name__}: {exc}", self.settings),
            )
            return False, ""

    def _ingest_attachments_and_source(self, state: WorkflowState) -> tuple[list[int], str]:
        raw_text = state.get("raw_text", "")
        sender = state.get("sender", "owner")
        ext_id = state.get("external_msg_id") or None
        source_ids: list[int] = []
        att_summaries: list[str] = []

        if raw_text.strip():
            sid, _ = self.db.insert_raw_source(
                source_type="wechat_text",
                external_msg_id=ext_id,
                sender=sender,
                title=raw_text.strip()[:48],
                raw_text=raw_text,
            )
            source_ids.append(sid)

        for idx, att in enumerate(state.get("attachments") or []):
            fpath = Path(att["path"])
            fname = att.get("filename") or fpath.name
            pages = extract_document_pages(fpath)
            att_text = "\n".join(f"[第{p['page']}页] {p['text']}" for p in pages)
            att_summaries.append(f"附件《{fname}》（共{len(pages)}页）：{att_text[:1000]}")
            att_msg_id = f"{ext_id}:att:{idx}" if ext_id else None
            sid, _ = self.db.insert_raw_source(
                source_type=fpath.suffix.lstrip(".") or "file",
                external_msg_id=att_msg_id,
                sender=sender,
                title=fname,
                raw_text=att_text[:4000],
                extracted_pages=pages,
            )
            source_ids.append(sid)

            if self.onedrive is not None and fpath.exists():
                ym = today_local().strftime("%Y%m")
                inbox_path = f"00_原件收件箱/{ym}/{fname}"
                try:
                    res = self.onedrive.upload_bytes(inbox_path, fpath.read_bytes())
                    self.db.update_source_onedrive_paths(sid, raw_path=inbox_path, web_url=res.get("webUrl", ""))
                except Exception as exc:
                    logger.warning(
                        "OneDrive raw inbox backup failed for %s: %s",
                        fname,
                        redact_secrets(f"{type(exc).__name__}: {exc}", self.settings),
                    )

        return source_ids, "\n".join(att_summaries)

    # --- Rolling episodic memory ---

    def _record_turn_pair(
        self,
        *,
        thread_id: str,
        user_text: str,
        reply_text: str,
        intent: str,
        proposal_id: int | None = None,
    ) -> None:
        known_projects = [p["name"] for p in self.db.list_projects()]
        u_tags = extract_topic_tags(user_text, known_projects)
        a_tags = extract_topic_tags(reply_text, known_projects)
        if user_text:
            self.db.append_conversation_turn(
                thread_id=thread_id,
                role="user",
                content=user_text,
                intent=intent,
                topic_tags=u_tags,
                proposal_id=proposal_id,
            )
        if reply_text:
            self.db.append_conversation_turn(
                thread_id=thread_id,
                role="assistant",
                content=reply_text,
                intent=intent,
                topic_tags=a_tags,
                proposal_id=proposal_id,
            )
        self._maybe_refresh_episode_summary(thread_id)

    def _maybe_refresh_episode_summary(self, thread_id: str) -> None:
        latest = self.db.get_latest_episode_summary(thread_id)
        last_id = int(latest["last_turn_id"]) if latest else 0
        delta_turns = self.db.get_turns_since(thread_id, after_id=last_id, limit=24)
        if len(delta_turns) < 8:
            return
        max_id = max(int(t["id"]) for t in delta_turns)
        prev_text = latest["summary_text"] if latest else ""

        lines: list[str] = [prev_text] if prev_text else []
        for t in delta_turns:
            if t.get("role") == "user" and len((t.get("content") or "").strip()) >= 4:
                lines.append(f"[{t['created_at']}] 董事长：{(t['content'] or '').strip()[:120]}")
        fallback_summary = "\n".join(lines[-12:])[:1000] or "近期已持续进行项目与待办沟通。"
        self.db.upsert_episode_summary(thread_id, fallback_summary, max_id)

        if not self.semantic_summaries:
            return

        def _upgrade_semantically() -> None:
            try:
                dialogue_blob = "\n".join(
                    f"[{t['created_at']}] {'董事长' if t['role'] == 'user' else 'AI助理'}：{(t['content'] or '').strip()[:240]}"
                    for t in delta_turns
                )
                ans, rec = self.gateway.generate_structured(
                    "fast",
                    [
                        {"role": "system", "content": EPISODE_SUMMARY_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"【上一版滚动摘要】\n{prev_text or '（无）'}\n\n"
                                f"【新增对话（共 {len(delta_turns)} 条）】\n{dialogue_blob}"
                            ),
                        },
                    ],
                    EpisodeSummary,
                    max_tokens=800,
                )
                self._record_latest_call(rec)
                if ans.summary.strip():
                    self.db.upsert_episode_summary(thread_id, ans.summary.strip(), max_id)
            except Exception as exc:
                logger.warning("Semantic episode summary fallback kept: %s", type(exc).__name__)

        if self.background_summaries:
            threading.Thread(target=_upgrade_semantically, daemon=True).start()
        else:
            _upgrade_semantically()

    # --- Node 1: Context Intake & Minimal Emergency Button Bypass ---

    def _node_context_intake(self, state: WorkflowState) -> WorkflowState:
        self._emit_progress("1/3 正在装配完整上下文与日历事实")
        traj = list(state.get("trajectory") or []) + ["node:context_intake"]
        raw_text = state.get("raw_text", "")
        thread_id = state.get("thread_id", "owner")
        ctx = self.context_assembler.assemble(thread_id, raw_text)
        calendar_text = build_calendar_anchor_text(today_local())

        base_fields: dict[str, Any] = {
            "calendar_anchor_text": calendar_text,
            "rolling_summary_text": ctx.rolling_summary_text,
            "project_context_text": ctx.project_context_text,
            "dialogue_context_text": ctx.recent_dialogue_text,
            "workspace_context_text": ctx.workspace_snapshot_text,
            "pending_context_text": ctx.pending_proposal_text,
            "has_pending_proposal": bool(ctx.pending_proposal),
        }

        # Bypass LLM ONLY for exact offline single-button controls (unless force_work_triage)
        if not state.get("force_work_triage") and not (state.get("attachments") or []):
            emergency = _emergency_button_decision(raw_text, ctx.pending_proposal)
            if emergency is not None:
                dec, intent_lbl = emergency
                return {
                    **base_fields,
                    "emergency_decision": dec.model_dump(mode="json"),
                    "decision": dec.model_dump(mode="json"),
                    "intent": intent_lbl,
                    "guard_issues": [],
                    "trajectory": traj + [f"tool:emergency_button={intent_lbl}"],
                }

        # Pre-gather lightweight workload snapshot + long-horizon evidence so the flagship brain has full facts
        today_str = today_local().isoformat()
        sched = check_workload_and_schedule(self.db, start_date=today_str)
        ev_pack = self.context_assembler.retrieve_long_horizon_evidence(
            ctx,
            raw_text=raw_text,
            resolved_text=raw_text,
            exclude_source_ids=list(state.get("source_ids") or []),
        )
        ev_blocks: list[str] = []
        for h in ev_pack["doc_hits"][:4]:
            ev_blocks.append(f"文档《{h['title']}》第{h.get('page') or '?'}页：{h['snippet']}")
        for ep in ev_pack["episodic_hits"][:4]:
            r_lbl = "董事长" if ep.get("role") == "user" else "AI助理"
            ev_blocks.append(f"[历史对话 {ep.get('created_at')}] {r_lbl}：{(ep.get('content') or '')[:260]}")
        if state.get("ingested_att_text"):
            ev_blocks.append(f"本次附件提取内容：\n{state['ingested_att_text'][:2200]}")

        tool_facts = f"近期排期密度（check_workload_and_schedule）：{json.dumps(sched, ensure_ascii=False)}"
        return {
            **base_fields,
            "emergency_decision": None,
            "evidence_text": "\n".join(ev_blocks) if ev_blocks else "（无额外历史附件命中）",
            "tool_outputs_text": tool_facts,
            "guard_issues": [],
            "guard_fix_note": "",
            "trajectory": traj,
        }

    # --- Node 2: Single Flagship Brain (`qwen3.8-max` + Native Tool Calling + 3-Rule Objective Guard) ---

    def _node_flagship_brain(self, state: WorkflowState) -> WorkflowState:
        loop_count = int(state.get("loop_count", 0))
        self._emit_progress(f"2/3 正在由旗舰大脑综合分析与决策（第 {loop_count + 1} 轮）")
        traj = list(state.get("trajectory") or []) + ["node:flagship_brain"]

        raw_input = state.get("raw_text", "")
        sender_str = (state.get("sender") or "owner").strip()
        is_mail_origin = sender_str.lower().startswith("mail:") or "[SYSTEM_TRUSTED_MAIL_META]" in _UNTRUSTED_DATA_BLOCK_RE.sub("", raw_input)
        today_str = today_local().isoformat()
        next_biz = calc_business_date(today_str, 1)
        calendar_text = state.get("calendar_anchor_text") or build_calendar_anchor_text(today_local())
        extra_tool_notes: list[str] = []

        def tool_exec(name: str, args: dict[str, Any]) -> str:
            if name == "search_archive":
                q = str(args.get("query") or "").strip()
                if not q:
                    return json.dumps({"documents": [], "conversations": []}, ensure_ascii=False)
                doc_hits = hybrid_search(self.db, q, top_k=5)
                tokens = extract_topic_tags(q) or [q]
                conv_hits = self.db.search_conversation_turns(tokens, limit=5)
                compact_conv = [
                    {
                        "created_at": c.get("created_at", ""),
                        "role": "董事长" if c.get("role") == "user" else "AI助理",
                        "content": (c.get("content") or "")[:300],
                    }
                    for c in conv_hits
                ]
                traj.append("tool:search_archive")
                out_json = json.dumps(
                    {"documents": doc_hits, "conversations": compact_conv},
                    ensure_ascii=False,
                )
                if len(out_json) > 4000:
                    out_json = out_json[:3980] + "...\"}"
                extra_tool_notes.append(f"search_archive({q}): {out_json[:1200]}")
                return out_json
            if name == "read_doc_pages":
                raw_sid = args.get("source_id")
                try:
                    sid = int(raw_sid)
                    if sid <= 0:
                        raise ValueError("source_id must be positive")
                except (TypeError, ValueError):
                    return json.dumps(
                        {"error": f"无效的 source_id 参数：{raw_sid!r}，请传入正整数文档编号。"},
                        ensure_ascii=False,
                    )
                pages_arg = args.get("pages")
                page_nums: list[int] | None = None
                if isinstance(pages_arg, list):
                    valid_nums: list[int] = []
                    for p in pages_arg:
                        try:
                            valid_nums.append(int(p))
                        except (TypeError, ValueError):
                            continue
                    page_nums = valid_nums[:5] if valid_nums else None
                pages = read_doc_pages(self.db, sid, page_nums)[:5]
                budget = 5600
                trimmed_pages: list[dict[str, Any]] = []
                used = 0
                for pg in pages:
                    txt = str(pg.get("text") or "")
                    remain = max(0, budget - used)
                    if remain <= 0:
                        break
                    sliced = txt[:remain]
                    trimmed_pages.append({"page": pg.get("page"), "text": sliced})
                    used += len(sliced)
                traj.append("tool:read_doc_pages")
                out_json = json.dumps(trimmed_pages, ensure_ascii=False)
                if len(out_json) > 6000:
                    out_json = out_json[:5950] + '"}]'
                extra_tool_notes.append(f"read_doc_pages({sid}): {out_json[:1500]}")
                return out_json
            if name == "check_workload_and_schedule":
                sd = str(args.get("start_date") or today_str)
                try:
                    date.fromisoformat(sd[:10])
                except ValueError:
                    sd = today_str
                res = check_workload_and_schedule(self.db, start_date=sd)
                traj.append("tool:check_workload_and_schedule")
                return json.dumps(res, ensure_ascii=False)
            if name == "calc_business_date":
                base_d = str(args.get("base_date") or today_str)
                try:
                    offset = int(args.get("offset_days", 1))
                except (TypeError, ValueError):
                    offset = 1
                try:
                    ans = calc_business_date(base_d, offset)
                except ValueError:
                    ans = next_biz
                traj.append("tool:calc_business_date")
                extra_tool_notes.append(f"calc_business_date({base_d}, {offset})={ans}")
                return ans
            return "{}"

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_archive",
                    "description": "按关键词检索历史上传的 PDF/Word/Excel 文档页码及摘要",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "检索关键词"}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_doc_pages",
                    "description": "读取指定文档 source_id 的精确页码全文，用于核对参数、报价与条款",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_id": {"type": "integer"},
                            "pages": {"type": "array", "items": {"type": "integer"}},
                        },
                        "required": ["source_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_workload_and_schedule",
                    "description": "查询从 start_date 起每日已排期任务数、P0 数量与是否拥挤",
                    "parameters": {
                        "type": "object",
                        "properties": {"start_date": {"type": "string", "description": "YYYY-MM-DD"}},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calc_business_date",
                    "description": "从 base_date 起按工作日（周一至周五）推算 offset_days 个工作日后的 YYYY-MM-DD",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "offset_days": {"type": "integer"},
                        },
                        "required": ["base_date", "offset_days"],
                    },
                },
            },
        ]

        channel_hint = "Outlook 整点邮件批次" if is_mail_origin else "董事长个人微信直接发送"
        dialogue_ctx = (state.get("dialogue_context_text") or "")[-12000:]
        workspace_ctx = (state.get("workspace_context_text") or "")[:10000]
        evidence_ctx = (state.get("evidence_text") or "")[:6000]
        user_prompt = (
            f"【通道来源】{channel_hint}\n\n"
            f"【确定性日历锚点表（推算相对日期务必以此为准）】\n{calendar_text}\n\n"
            f"【跨天滚动会话摘要】\n{state.get('rolling_summary_text', '')}\n\n"
            + (f"【相关项目上下文卡】\n{state.get('project_context_text')}\n\n" if state.get("project_context_text") else "")
            + f"【近期真实对话流】\n{dialogue_ctx}\n\n"
            f"【当前待确认卡片】\n{state.get('pending_context_text', '')}\n\n"
            f"【在途项目与全部未完成任务快照】\n{workspace_ctx}\n\n"
            f"【自动预检索档案证据】\n{evidence_ctx}\n\n"
            f"【排期密度事实】\n{state.get('tool_outputs_text', '')}\n\n"
            f"【本次最新输入】\n{raw_input}\n"
        )
        if state.get("force_work_triage"):
            user_prompt += "\n（本轮为 Outlook 邮件批次汇总：请输出 mode='propose' 并严格按邮件头角色推断与会话串线规则生成 proposal。）\n"
        if state.get("guard_fix_note"):
            user_prompt += f"\n【客观硬校验修正提示（请安静修正字段，绝不要在输出文本里提及本提示）】\n{state['guard_fix_note']}\n"

        decision, rec = self.gateway.generate_structured(
            "producer",
            [
                {"role": "system", "content": FLAGSHIP_BRAIN_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            AgentDecision,
            tools=tools,
            tool_executor=tool_exec,
            max_tokens=2048,
        )
        self._record_latest_call(rec)

        guard_issues: list[str] = []
        if decision.mode == "propose" and decision.proposal is not None:
            prop = _backfill_mail_conversation_ids(decision.proposal, raw_input)
            for act in prop.actions:
                if is_mail_origin:
                    act.source_channel = "outlook"
                else:
                    if not act.source_channel:
                        act.source_channel = "wechat"
                    # WeChat delegation from Chairman is never an Outlook CC-observer
                    if act.chairman_role == "cc_observer":
                        act.chairman_role = "owner"
            decision.proposal = prop

            guard_issues = objective_proposal_guard(
                prop,
                raw_input=raw_input,
                is_mail_origin=is_mail_origin,
            )
            if guard_issues:
                traj.append("guard:objective_reject")

        return {
            "decision": decision.model_dump(mode="json"),
            "guard_issues": guard_issues,
            "guard_fix_note": "; ".join(guard_issues) if guard_issues else "",
            "loop_count": loop_count + 1,
            "intent": decision.mode,
            "trajectory": traj,
        }

    # --- Node 3: Deterministic Safe Execution Chassis ---

    def _execute_direct_ops(self, decision: AgentDecision) -> str:
        results: list[str] = []
        mutated = False

        if decision.undo_last:
            ok, msg = self.db.undo_last_commit()
            if ok:
                mutated = True
            results.append(("↩️ " if ok else "ℹ️ ") + msg)

        for upd in decision.field_updates:
            existing = self.db.get_item(int(upd.task_id))
            if not existing:
                results.append(f"⚠️ 未找到任务编号 #{upd.task_id}")
                continue
            patch: dict[str, Any] = {}
            raw_dump = upd.model_dump(mode="json", exclude={"task_id"}, exclude_none=True)
            invalid_msg = ""
            if "planned_end_at" in raw_dump:
                val = str(raw_dump["planned_end_at"] or "").strip()
                if val:
                    try:
                        if len(val) < 10:
                            raise ValueError("short")
                        d_end = date.fromisoformat(val[:10])
                        ps_raw = str(raw_dump.get("planned_start_at") or existing.get("planned_start_at") or "").strip()
                        if ps_raw:
                            d_start = date.fromisoformat(ps_raw[:10])
                            if d_end < d_start:
                                invalid_msg = f"⚠️ 任务 #{upd.task_id} 目标截止日期 {val[:10]} 早于开始日期 {ps_raw[:10]}，未修改"
                        raw_dump["planned_end_at"] = d_end.isoformat()
                    except ValueError:
                        invalid_msg = f"⚠️ 任务 #{upd.task_id} 日期格式非法（{val}），未修改"
            if "planned_start_at" in raw_dump and not invalid_msg:
                val_s = str(raw_dump["planned_start_at"] or "").strip()
                if val_s:
                    try:
                        if len(val_s) < 10:
                            raise ValueError("short")
                        raw_dump["planned_start_at"] = date.fromisoformat(val_s[:10]).isoformat()
                    except ValueError:
                        invalid_msg = f"⚠️ 任务 #{upd.task_id} 开始日期格式非法（{val_s}），未修改"
            if invalid_msg:
                results.append(invalid_msg)
                continue
            patch.update(raw_dump)
            if patch:
                updated = self.db.update_item_fields(int(upd.task_id), patch)
                if updated:
                    mutated = True
                    field_labels = {
                        "planned_end_at": "目标截止",
                        "planned_start_at": "开始日期",
                        "assignee": "实施人",
                        "owner": "负责人",
                        "external_partner": "外部协作",
                        "deliverable": "交付成果",
                        "milestone_stage": "当前阶段",
                        "blocker_note": "卡点",
                        "priority": "优先级",
                        "project_name": "归属项目",
                    }
                    changes_txt = "、".join(f"{field_labels.get(k, k)}→{v or '【待补齐】'}" for k, v in patch.items())
                    results.append(f"✏️ 已更新任务 #{upd.task_id}《{updated['title']}》：{changes_txt}")

        for note in decision.note_appends:
            clean_content = (note.content or "").strip()
            if not clean_content:
                results.append(f"⚠️ 请补充要记录给 #{note.task_id} 的具体内容，本次未写入空白记录。")
                continue
            if note.kind == "ceo_evaluation":
                item = self.db.append_task_ceo_evaluation(int(note.task_id), clean_content)
                if not item:
                    results.append(f"⚠️ 未找到任务编号 #{note.task_id}")
                else:
                    mutated = True
                    results.append(f"💬 已为 #{note.task_id}《{item['title']}》记录 CEO 评价：{clean_content}")
            elif note.kind == "comment":
                item = self.db.append_task_comment(int(note.task_id), clean_content)
                if not item:
                    results.append(f"⚠️ 未找到任务编号 #{note.task_id}")
                else:
                    mutated = True
                    results.append(f"📝 已为 #{note.task_id}《{item['title']}》追加补充备注：{clean_content}")
            else:
                entry = self.db.append_task_timeline(
                    int(note.task_id),
                    summary=clean_content,
                    channel="wechat",
                    from_party="徐宏玮",
                )
                if not entry:
                    results.append(f"⚠️ 未找到任务编号 #{note.task_id}")
                else:
                    mutated = True
                    results.append(f"📌 已为 #{note.task_id} 追加进展时间轴：[{_short_ts(entry['timestamp'])}] {clean_content}")

        for st in decision.status_changes:
            if st.action == "start":
                item = self.db.start_item(int(st.task_id))
                if not item:
                    results.append(f"⚠️ 未找到待办编号 #{st.task_id}")
                else:
                    mutated = True
                    results.append(f"▶️ 已记录 #{item['id']} 已开始：{item['title']}（{item['actual_start_at']}）")
            else:
                item = self.db.complete_item(int(st.task_id), actual_hours=st.actual_hours)
                if not item:
                    results.append(f"⚠️ 未找到待办编号 #{st.task_id}")
                else:
                    mutated = True
                    span_days = item.get("actual_span_days", 1)
                    hrs_note = f"（指定实耗 {item['actual_hours']}h）" if (item.get("actual_hours") or 0) > 0 else ""
                    results.append(f"✅ 已完成 #{item['id']}：{item['title']}（实际完成跨度 {span_days} 天{hrs_note}）")

        for tid in decision.view_timeline_ids:
            existing = self.db.get_item(int(tid))
            if not existing:
                results.append(f"未找到任务编号 #{tid}（当前不存在该任务）。")
                continue
            tl = existing.get("timeline") or []
            if not tl:
                results.append(f"任务 #{tid}《{existing['title']}》暂无沟通与进展记录。")
                continue
            tl_lines = [f"🗂️ 任务 #{tid}《{existing['title']}》完整沟通与进展时间轴（共 {len(tl)} 条）："]
            ch_map = {"wechat": "微信", "mail_in": "收件", "mail_out": "发件", "web": "驾驶舱"}
            for e in tl:
                ch_lbl = ch_map.get(e.get("channel", "wechat"), e.get("channel", ""))
                who = _format_party_flow(e.get("from_party", ""), e.get("to_party", ""), e.get("cc_parties"))
                who_part = f"｜{who}" if who else ""
                tl_lines.append(f"- [{_short_ts(e.get('timestamp', ''))}｜{ch_lbl}{who_part}] {e.get('summary', '')}")
            results.append("\n".join(tl_lines))

        if mutated:
            od_ok, _ = self._safe_sync_onedrive()
            if not od_ok:
                results.append("（本地已保存，云端 OneDrive 同步稍后重试）")

        if results:
            return "\n".join(results)
        return decision.reply_text or "已处理完成。"

    def _node_action_executor(self, state: WorkflowState) -> WorkflowState:
        self._emit_progress("3/3 正在执行操作并整理回复")
        traj = list(state.get("trajectory") or []) + ["node:action_executor"]
        thread_id = state.get("thread_id", "owner")
        raw_input = state.get("raw_text", "")
        sender_str = (state.get("sender") or "owner").strip().lower()
        is_mail_origin = sender_str.startswith("mail:") or "[SYSTEM_TRUSTED_MAIL_META]" in _UNTRUSTED_DATA_BLOCK_RE.sub("", raw_input)
        decision = AgentDecision.model_validate(state.get("decision") or {"mode": "reply", "reply_text": "收到。"})
        guard_issues = list(state.get("guard_issues") or [])

        if decision.mode == "open_cockpit":
            url = self.magic_link_factory()
            reply = (
                "📊 董事长项目管理驾驶舱（固定访问链接，首次用微信 6 位验证码登录后本机长期免密直开）：\n"
                f"{url}"
            )
            assert_no_secrets_leaked(reply, self.settings)
            return {"reply_text": reply, "proposal_id": None, "trajectory": traj + ["exec:open_cockpit"]}

        if decision.mode == "show_workload":
            w = self.db.get_daily_workload(days=3, daily_capacity=self.settings.daily_capacity_hours)
            items = self.db.list_items(include_done=False)[:6]
            day_lines = [f"- {d}: 排期 {len(v['items'])} 项" for d, v in w["days"].items()]
            item_lines = [
                f"- #{it['id']} [{it['priority']}] {it['title']}（{it['planned_start_at'] or '-'}~{it['planned_end_at'] or '待补齐'}）"
                for it in items
            ]
            reply = "📅 近3日日程分布：\n" + "\n".join(day_lines) + "\n\n📌 Top 待办：\n" + ("\n".join(item_lines) or "- 暂无")
            assert_no_secrets_leaked(reply, self.settings)
            return {"reply_text": reply, "proposal_id": None, "trajectory": traj + ["exec:show_workload"]}

        if decision.mode == "confirm_pending":
            pending = self.db.get_latest_pending_proposal(thread_id)
            if not pending:
                return {"reply_text": "当前没有待确认的提案卡片。", "proposal_id": None, "trajectory": traj + ["exec:confirm_pending"]}
            msg = self.commit_pending_proposal(pending, ideas_only=bool(decision.ideas_only))
            assert_no_secrets_leaked(msg, self.settings)
            return {"reply_text": msg, "proposal_id": None, "trajectory": traj + ["exec:confirm_pending"]}

        if decision.mode == "discard_pending":
            pending = self.db.get_latest_pending_proposal(thread_id)
            if not pending:
                return {"reply_text": "当前没有可作废的待确认卡片。", "proposal_id": None, "trajectory": traj + ["exec:discard_pending"]}
            self.db.cancel_pending_proposal(int(pending["id"]))
            self._cleanup_pending_files(pending.get("pending_files") or [])
            msg = f"🗑️ 已作废待确认卡片 #{pending['id']}，未写入任何清单。"
            assert_no_secrets_leaked(msg, self.settings)
            return {
                "reply_text": msg,
                "proposal_id": None,
                "trajectory": traj + ["exec:discard_pending"],
            }

        if decision.mode == "direct_ops":
            reply = self._execute_direct_ops(decision)
            assert_no_secrets_leaked(reply, self.settings)
            return {"reply_text": reply, "proposal_id": None, "trajectory": traj + ["exec:direct_ops"]}

        if decision.mode == "propose" and decision.proposal is not None:
            proposal = decision.proposal
            # Pure FYI (no new actions and no existing task updates) -> never create a blocking pending card
            if not proposal.actions and not proposal.task_updates:
                fyi_text = _format_pure_fyi_message(proposal)
                assert_no_secrets_leaked(fyi_text, self.settings)
                return {
                    "proposal_id": None,
                    "reply_text": fyi_text,
                    "trajectory": traj + ["exec:pure_fyi_no_card"],
                }

            # Carry over attachments/source_ids when revising an existing pending proposal
            existing_pending = self.db.get_latest_pending_proposal(thread_id)
            merged_source_ids = list(state.get("source_ids") or [])
            merged_files = list(state.get("attachments") or [])
            if existing_pending and not is_mail_origin:
                for sid in existing_pending.get("source_ids") or []:
                    if sid not in merged_source_ids:
                        merged_source_ids.append(sid)
                if not merged_files:
                    merged_files = list(existing_pending.get("pending_files") or [])

            # Safety invariant: NEVER commit if objective chassis guard still reports issues!
            if decision.confirm_and_commit and guard_issues:
                err_text = (
                    "⚠️ 检测到排期或角色异常，为保障数据准确已拦截落盘：\n"
                    + "\n".join(f"- {x}" for x in guard_issues)
                    + "\n请修正后再确认落盘。"
                )
                assert_no_secrets_leaked(err_text, self.settings)
                return {
                    "proposal_id": None,
                    "reply_text": err_text,
                    "trajectory": traj + ["exec:blocked_dirty_commit"],
                }

            pid = self.db.save_pending_proposal(
                thread_id=thread_id,
                proposal_dict=proposal.model_dump(mode="json"),
                source_ids=merged_source_ids,
                pending_files=merged_files,
            )

            if decision.confirm_and_commit and not guard_issues:
                fresh_pending = self.db.get_latest_pending_proposal(thread_id)
                assert fresh_pending is not None
                msg = self.commit_pending_proposal(fresh_pending, ideas_only=bool(decision.ideas_only))
                assert_no_secrets_leaked(msg, self.settings)
                return {
                    "proposal_id": pid,
                    "reply_text": msg,
                    "trajectory": traj + ["exec:one_step_commit"],
                }

            card_text = format_decision_card(
                pid,
                proposal,
                critic_issues=guard_issues or None,
                is_mail_batch=is_mail_origin,
            )
            assert_no_secrets_leaked(card_text, self.settings)
            return {
                "proposal_id": pid,
                "reply_text": card_text,
                "trajectory": traj + ["exec:hitl_preview"],
            }

        # Default: direct reply (Q&A / conversation / clarification)
        reply = (decision.reply_text or "").strip() or "收到，请继续指示。"
        assert_no_secrets_leaked(reply, self.settings)
        return {"reply_text": reply, "proposal_id": None, "trajectory": traj + ["exec:reply"]}

    # --- Graph wiring (Ultra-Clean 3-Node StateGraph) ---

    @staticmethod
    def _route_after_intake(state: WorkflowState) -> str:
        if state.get("emergency_decision") is not None:
            return "execute"
        return "brain"

    @staticmethod
    def _route_after_brain(state: WorkflowState, max_loops: int) -> str:
        issues = state.get("guard_issues") or []
        if issues and int(state.get("loop_count", 0)) < max_loops:
            return "retry"
        return "execute"

    def _build_graph(self):
        builder = StateGraph(WorkflowState)
        builder.add_node("context_intake", self._node_context_intake)
        builder.add_node("flagship_brain", self._node_flagship_brain)
        builder.add_node("action_executor", self._node_action_executor)

        builder.set_entry_point("context_intake")
        builder.add_conditional_edges(
            "context_intake",
            self._route_after_intake,
            {"execute": "action_executor", "brain": "flagship_brain"},
        )
        builder.add_conditional_edges(
            "flagship_brain",
            lambda st: self._route_after_brain(st, self.settings.max_reflection_loops),
            {"retry": "flagship_brain", "execute": "action_executor"},
        )
        builder.add_edge("action_executor", END)
        return builder.compile(checkpointer=self.checkpointer)

    # --- Atomic HITL Commit ---

    def commit_pending_proposal(self, pending: dict[str, Any], *, ideas_only: bool = False) -> str:
        """Mint ApprovalToken, pass before_tool_callback, commit SQLite atomically FIRST, then sync OneDrive."""
        proposal_id = int(pending["id"])
        proposal = TriageProposal.model_validate(pending["proposal"])
        task_updates = list(proposal.task_updates or [])
        if not proposal.actions and not task_updates:
            self.db.cancel_pending_proposal(proposal_id)
            self._cleanup_pending_files(pending.get("pending_files") or [])
            return f"ℹ️ 确认卡 #{proposal_id} 不含可执行动作，已自动关闭，不会阻塞后续处理。"

        actions = [a for a in proposal.actions if (not ideas_only or a.list_type == ListType.IDEA)]
        if ideas_only and not actions:
            return (
                f"ℹ️ 确认卡 #{proposal_id} 没有想法项（0 条想法），未写入任何清单。\n"
                "如需全量落盘请回复 1，如需作废请回复 0。"
            )
        effective_updates = [] if ideas_only else task_updates

        secret = self.settings.web_access_secret or self.settings.dashscope_api_key
        token = ApprovalToken.mint(proposal_id, secret)

        before_tool_callback(
            "propose_list_mutations",
            {"proposal_id": proposal_id, "count": len(actions) + len(effective_updates)},
            approval_token=token,
            signing_secret=secret,
        )

        commit_res = self.db.apply_proposal_atomic(
            proposal_id=proposal_id,
            actions=actions,
            task_updates=effective_updates,
            source_ids=pending.get("source_ids", []),
            doc_paths=[],
            brief_summary=proposal.executive_summary,
            project_web_urls={},
        )
        if commit_res.get("already_processed"):
            return f"ℹ️ 确认卡 #{proposal_id} 已确认或已失效，未重复落盘。"

        archived_paths: list[str] = []
        proj_urls: dict[str, str] = {}
        ymd = today_local().strftime("%Y%m%d")
        first_proj = actions[0].project_name if actions else "日常事务"
        onedrive_failed = False

        if self.onedrive is not None:
            before_tool_callback(
                "organize_onedrive_files",
                {"proposal_id": proposal_id},
                approval_token=token,
                signing_secret=secret,
            )
            before_tool_callback(
                "compose_markdown_brief",
                {"proposal_id": proposal_id},
                approval_token=token,
                signing_secret=secret,
            )
            try:
                for pf in pending.get("pending_files", []):
                    fpath = Path(pf.get("path", ""))
                    fname = pf.get("filename") or fpath.name
                    if fpath.exists():
                        safe_proj = first_proj.replace("/", "_")
                        target_path = f"01_项目归档/{safe_proj}/{ymd}_{safe_proj}_{fname}"
                        res = self.onedrive.upload_and_cleanup_local(target_path, fpath)
                        archived_paths.append(target_path)
                        if res.get("webUrl"):
                            proj_urls[first_proj] = res["webUrl"]

                if actions:
                    note_entry = (
                        f"### {today_local().isoformat()}｜{proposal.headline}\n"
                        f"- **摘要**：{proposal.executive_summary}\n"
                        + "\n".join(f"- **[{a.priority.value}]** {a.title}（{a.estimated_hours}h）" for a in actions)
                    )
                    self.onedrive.append_project_note(first_proj, note_entry)
                if archived_paths or proj_urls:
                    self.db.update_items_onedrive_docs(
                        commit_res["inserted_item_ids"],
                        archived_paths,
                        proj_urls,
                    )
            except Exception as exc:
                onedrive_failed = True
                logger.warning(
                    "OneDrive archive sync error during commit: %s",
                    redact_secrets(f"{type(exc).__name__}: {exc}", self.settings),
                )

        board_url = ""
        if self.onedrive is not None:
            od_ok, board_url = self._safe_sync_onedrive()
            if not od_ok:
                onedrive_failed = True

        inserted_ids = commit_res.get("inserted_item_ids") or []
        updated_ids = commit_res.get("updated_item_ids") or []
        ids_str = ", ".join(f"#{i}" for i in inserted_ids)
        upd_str = ", ".join(f"#{i}" for i in updated_ids)
        if board_url:
            tail = f"\n☁️ 云端看板已刷新：{board_url}"
        elif onedrive_failed:
            tail = "\n⚠️ 本地数据库已安全落盘（云端 OneDrive 同步暂遇网络波动，恢复后将自动刷新）。"
        else:
            tail = ""

        summary_parts: list[str] = []
        if ids_str:
            summary_parts.append(f"新增项编号 {ids_str}")
        if upd_str:
            summary_parts.append(f"已更新已有任务 {upd_str} 时间轴与进展")
        summary_str = "；".join(summary_parts) or "已落盘"
        return (
            f"✅ 已确认落盘（确认卡 #{proposal_id} → {summary_str}）。\n"
            f"可用「完成 #编号」闭环，或 24h 内回复「撤销」完整回滚。{tail}"
        )

    # --- Public Entry Point ---

    def handle_incoming_turn(
        self,
        raw_text: str,
        *,
        sender: str = "owner",
        external_msg_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        thread_id: str = "owner",
        progress_callback: Callable[[str], None] | None = None,
        force_work_triage: bool = False,
    ) -> dict[str, Any]:
        """Unified thread-safe turn entry point."""
        text = (raw_text or "").strip()
        atts = attachments or []
        with self._turn_lock:
            prev_cb = self._progress_cb
            self._progress_cb = progress_callback
            try:
                return self._handle_incoming_turn_inner(
                    text=text,
                    sender=sender,
                    external_msg_id=external_msg_id,
                    atts=atts,
                    thread_id=thread_id,
                    force_work_triage=force_work_triage,
                )
            finally:
                self._progress_cb = prev_cb

    def _handle_incoming_turn_inner(
        self,
        *,
        text: str,
        sender: str,
        external_msg_id: str | None,
        atts: list[dict[str, Any]],
        thread_id: str,
        force_work_triage: bool = False,
    ) -> dict[str, Any]:
        if not text and not atts:
            return {
                "reply_text": "您好，收到空白消息，请直接发送文字、语音、附件，或回复 看板 / 负荷。",
                "proposal_id": None,
                "source_ids": [],
                "trajectory": ["short_circuit:empty_input"],
            }

        init_state: WorkflowState = {
            "thread_id": thread_id,
            "raw_text": text,
            "sender": sender,
            "external_msg_id": external_msg_id or "",
            "attachments": atts,
            "source_ids": [],
            "ingested_att_text": "",
            "calendar_anchor_text": "",
            "evidence_text": "",
            "tool_outputs_text": "",
            "force_work_triage": force_work_triage,
            "emergency_decision": None,
            "decision": {},
            "guard_issues": [],
            "guard_fix_note": "",
            "loop_count": 0,
            "proposal_id": None,
            "reply_text": "",
            "intent": "",
            "trajectory": [],
        }
        run_thread_id = f"{thread_id}:{external_msg_id or uuid.uuid4().hex}"
        with self._turn_lock:
            try:
                if atts:
                    ingested_ids, ingested_text = self._ingest_attachments_and_source(init_state)
                    init_state["source_ids"] = ingested_ids
                    init_state["ingested_att_text"] = ingested_text
                out = self.graph.invoke(
                    init_state,
                    config={"configurable": {"thread_id": run_thread_id}},
                )
            except Exception as exc:
                user_line = (
                    "[Outlook 邮件批次触发分拣]"
                    if (sender or "").strip().lower().startswith("mail:")
                    else (text or f"[附件: {', '.join(a.get('filename', 'file') for a in atts)}]")
                )
                fallback = (
                    f"⚠️ 刚才处理这条消息时遇到临时异常（{type(exc).__name__}），本次没有生成待办或改动任何数据。\n"
                    "你的原话已记入对话记录，稍后发「继续」或重新发送即可接着处理。"
                )
                try:
                    self._record_turn_pair(
                        thread_id=thread_id,
                        user_text=user_line,
                        reply_text=fallback,
                        intent=f"error:{type(exc).__name__}",
                    )
                except Exception as db_exc:
                    logger.error("Failed to persist fallback turn: %s", type(db_exc).__name__)
                    fallback = (
                        f"⚠️ 刚才处理这条消息时遇到临时异常（{type(exc).__name__}），本次没有生成待办或改动任何数据。\n"
                        "请稍后重新发送。"
                    )
                return {
                    "reply_text": fallback,
                    "proposal_id": None,
                    "source_ids": [],
                    "trajectory": [f"error:{type(exc).__name__}"],
                }

        recorded_user_text = (
            "[Outlook 邮件批次触发分拣]"
            if (sender or "").strip().lower().startswith("mail:")
            else (text or f"[附件: {', '.join(a.get('filename', 'file') for a in atts)}]")
        )
        self._record_turn_pair(
            thread_id=thread_id,
            user_text=recorded_user_text,
            reply_text=out["reply_text"],
            intent=out.get("intent", "reply"),
            proposal_id=out.get("proposal_id"),
        )
        return {
            "reply_text": out["reply_text"],
            "proposal_id": out.get("proposal_id"),
            "source_ids": out.get("source_ids", []),
            "trajectory": out.get("trajectory", []),
        }
