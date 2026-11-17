"""LangGraph bounded cyclic Chief-of-Staff state graph, deterministic pre-guards, and HITL commit."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from wechat_assistant.config import DashScopeLLMGateway, Settings, assert_no_secrets_leaked
from wechat_assistant.context_assembler import ContextAssembler, extract_topic_tags
from wechat_assistant.nodes.critic_rules import deterministic_critic_check
from wechat_assistant.prompts.system_prompts import (
    CONVERSATIONAL_ADVISOR_PROMPT,
    CRITIC_AUDIT_PROMPT,
    FAST_ROUTER_PROMPT,
    PRODUCER_TRIAGE_PROMPT,
    QA_GROUNDED_PROMPT,
)
from wechat_assistant.schemas import ActionMutation, CriticVerdict, IntentRoute, ListType, TriageProposal
from wechat_assistant.storage.db import Database
from wechat_assistant.storage.extractors import extract_document_pages, parse_excel_quote_rows
from wechat_assistant.tools.calc_tools import analyze_excel_quote
from wechat_assistant.tools.guard import ApprovalToken, before_tool_callback
from wechat_assistant.tools.memory_tools import hybrid_search, read_doc_pages
from wechat_assistant.tools.onedrive_tools import OneDrive21VianetClient
from wechat_assistant.tools.schedule_tools import calc_business_date, check_workload_and_schedule
from wechat_assistant.tools.search_tools import search_public_tech_intel


class QAGroundedAnswer(BaseModel):
    """Structured answer from Agentic RAG citing exact filename and page."""

    found: bool
    answer: str = Field(min_length=1, max_length=1500)
    citations: list[str] = Field(default_factory=list)


class ConversationalReply(BaseModel):
    """Structured executive conversational response preserving continuous context."""

    reply: str = Field(min_length=1, max_length=1500)


class WorkflowState(TypedDict, total=False):
    thread_id: str
    raw_text: str
    sender: str
    external_msg_id: str
    attachments: list[dict[str, Any]]
    source_ids: list[int]
    intent: str
    needs_deep_research: bool
    resolved_text: str
    search_queries: list[str]
    target_item_id: int | None
    actual_hours: float | None
    dialogue_context_text: str
    workspace_context_text: str
    pending_context_text: str
    has_pending_proposal: bool
    pending_ideas_only: bool
    evidence_cards: list[dict[str, Any]]
    evidence_text: str
    schedule_snapshot: dict[str, Any]
    excel_diff: dict[str, Any] | None
    search_brief: dict[str, Any] | None
    tool_outputs_text: str
    user_correction: str
    proposal: dict[str, Any]
    critic_verdict: dict[str, Any]
    loop_count: int
    reply_text: str
    proposal_id: int | None
    trajectory: list[str]


def is_confidential_input(text: str, attachments: list[dict[str, Any]] | None = None) -> bool:
    stripped = (text or "").lstrip()
    if stripped.startswith(("密：", "密:")):
        return True
    for att in attachments or []:
        name = Path(att.get("filename") or att.get("path") or "").name
        if name.startswith(("密：", "密:")):
            return True
    return False


def format_decision_card(proposal_id: int, proposal: TriageProposal, cockpit_url: str = "") -> str:
    """Format a compact high-density Chief-of-Staff HITL preview card for WeChat."""
    lines = [f"📋 **确认 #{proposal_id}｜{proposal.headline}**", proposal.executive_summary]
    if proposal.actions:
        lines.append("\n**拟入库动作与日程跨度：**")
        for idx, act in enumerate(proposal.actions, 1):
            span = (
                act.planned_start_at
                if act.planned_start_at == act.planned_end_at
                else f"{act.planned_start_at} ~ {act.planned_end_at}"
            )
            try:
                span_days = max(1, (date.fromisoformat(act.planned_end_at[:10]) - date.fromisoformat(act.planned_start_at[:10])).days + 1)
            except ValueError:
                span_days = 1
            hr_note = f"｜指定工时 `{act.estimated_hours}h`" if act.estimated_hours and act.estimated_hours > 0 else ""
            lines.append(
                f"{idx}. `[{act.priority.value}][{act.list_type.value}]` **{act.project_name}**（{act.work_domain.value}）："
                f"{act.title}｜周期 `{span}`（{span_days}天）{hr_note}"
            )
    if proposal.overload_warning:
        lines.append(f"\n⚠️ **负荷提醒**：{proposal.overload_warning}")
    if proposal.citations:
        lines.append(f"\n📎 **证据出处**：{'; '.join(proposal.citations)}")
    lines.append("\n回复 `1` 确认落盘 ｜ `2` 仅存想法 ｜ `改：<意见>` 调整重算")
    if cockpit_url:
        lines.append(f"📊 驾驶舱：{cockpit_url}")
    return "\n".join(lines)


class ChiefOfStaffEngine:
    """End-to-end bounded workflow orchestrator binding DB, tools, OneDrive, and LangGraph."""

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
        self._turn_lock = threading.Lock()
        self.checkpointer = SqliteSaver(self._ckpt_conn)
        self.graph = self._build_graph()

    def close(self) -> None:
        self._ckpt_conn.close()

    def _record_turn_pair(
        self,
        *,
        thread_id: str,
        user_text: str,
        reply_text: str,
        intent: str,
        proposal_id: int | None = None,
    ) -> None:
        proj_names = [p["name"] for p in self.db.list_projects()]
        self.db.append_conversation_turn(
            thread_id=thread_id,
            role="user",
            content=user_text,
            intent=intent,
            topic_tags=extract_topic_tags(user_text, proj_names),
            proposal_id=proposal_id,
        )
        self.db.append_conversation_turn(
            thread_id=thread_id,
            role="assistant",
            content=reply_text,
            intent=intent,
            topic_tags=extract_topic_tags(reply_text, proj_names),
            proposal_id=proposal_id,
        )

    def _record_latest_call(self, rec) -> None:
        self.db.record_model_call(
            tier=rec.tier,
            model=rec.model,
            prompt_tokens=rec.prompt_tokens,
            completion_tokens=rec.completion_tokens,
            reasoning_tokens=rec.reasoning_tokens,
            latency_ms=rec.latency_ms,
            success=rec.success,
        )

    def _ingest_attachments_and_source(self, state: WorkflowState) -> tuple[list[int], list[list[dict[str, Any]]], str]:
        """Extract pages from incoming files and index source text before reasoning."""
        raw_text = state.get("raw_text", "")
        sender = state.get("sender", "owner")
        ext_id = state.get("external_msg_id")
        attachments = state.get("attachments") or []

        all_pages: list[dict[str, Any]] = []
        excel_tables: list[list[dict[str, Any]]] = []
        att_summaries: list[str] = []
        source_ids: list[int] = list(state.get("source_ids") or [])

        if not source_ids:
            # First extract pages from each attachment and index each file as a dedicated raw_source too
            main_id, _ = self.db.insert_raw_source(
                source_type="wechat_msg",
                external_msg_id=ext_id,
                sender=sender,
                title=(raw_text.splitlines()[0][:60] if raw_text else "微信输入"),
                raw_text=raw_text,
                is_confidential=False,
            )
            source_ids.append(main_id)

            for idx, att in enumerate(attachments):
                fpath = Path(att.get("path", ""))
                fname = att.get("filename") or fpath.name
                pages = att.get("pages")
                if pages is None and fpath.exists():
                    pages = extract_document_pages(fpath)
                    if fpath.suffix.lower() in {".xlsx", ".xlsm"}:
                        excel_tables.append(parse_excel_quote_rows(fpath))
                elif att.get("excel_rows"):
                    excel_tables.append(att["excel_rows"])
                pages = pages or []
                all_pages.extend(pages)

                att_text = "\n".join(f"[第{p.get('page', 1)}页] {p.get('text', '')}" for p in pages)
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
                    ym = date.today().strftime("%Y%m")
                    inbox_path = f"00_原件收件箱/{ym}/{fname}"
                    try:
                        res = self.onedrive.upload_bytes(inbox_path, fpath.read_bytes())
                        self.db.update_source_onedrive_paths(
                            sid, raw_path=inbox_path, web_url=res.get("webUrl", "")
                        )
                    except Exception:
                        pass

        return source_ids, excel_tables, "\n".join(att_summaries)

    # --- LangGraph nodes ---

    def _node_guardrail_router(self, state: WorkflowState) -> WorkflowState:
        traj = list(state.get("trajectory") or []) + ["node:guardrail_router"]
        raw_text = state.get("raw_text", "")
        thread_id = state.get("thread_id", "owner")
        ctx = self.context_assembler.assemble(thread_id, raw_text)
        ctx_fields: dict[str, Any] = {
            "dialogue_context_text": ctx.recent_dialogue_text,
            "workspace_context_text": ctx.workspace_snapshot_text,
            "pending_context_text": ctx.pending_proposal_text,
            "has_pending_proposal": bool(ctx.pending_proposal),
        }

        if state.get("user_correction"):
            return {
                **ctx_fields,
                "intent": "work_triage",
                "needs_deep_research": False,
                "resolved_text": state.get("user_correction", raw_text),
                "trajectory": traj,
            }

        if (
            len(raw_text.strip()) <= 6
            and raw_text.strip().lower() in {"你好", "在吗", "hi", "hello"}
            and not ctx.recent_turns
            and not ctx.pending_proposal
        ):
            return {
                **ctx_fields,
                "intent": "chitchat",
                "needs_deep_research": False,
                "reply_text": "您好，AI工作助理在线！您可以直接发送语音想法、转发聊天记录、文件，或发送 `看板` / `负荷`。",
                "trajectory": traj,
            }

        router_input = self.context_assembler.render_for_router(ctx, raw_text)
        route, rec = self.gateway.generate_structured(
            "fast",
            [
                {"role": "system", "content": FAST_ROUTER_PROMPT},
                {"role": "user", "content": router_input},
            ],
            IntentRoute,
            max_tokens=1024,
        )
        self._record_latest_call(rec)

        effective_intent = route.intent
        explicit_search_req = bool(
            re.search(r"(?:查一下|上网查|联网查|联网搜|搜一下|帮我查|查一查|查下)", raw_text)
        )
        extra_updates: dict[str, Any] = {
            "needs_deep_research": bool(route.needs_deep_research and explicit_search_req),
            "resolved_text": route.resolved_intent_text or raw_text,
            "search_queries": list(route.search_queries or []),
            "target_item_id": route.target_item_id,
            "actual_hours": route.actual_hours,
        }

        if route.intent == "ideas_only_pending":
            if ctx.pending_proposal:
                effective_intent = "confirm_pending"
                extra_updates["pending_ideas_only"] = True
            else:
                effective_intent = "conversational_chat"
        elif route.intent == "confirm_pending" and not ctx.pending_proposal:
            effective_intent = "conversational_chat"
        elif route.intent == "discard_pending" and not ctx.pending_proposal:
            effective_intent = "conversational_chat"
        elif route.intent == "revise_pending":
            if ctx.pending_proposal:
                effective_intent = "work_triage"
                extra_updates["user_correction"] = route.resolved_intent_text or raw_text
                extra_updates["raw_text"] = (
                    f"对确认卡 #{ctx.pending_proposal['id']} 原提案的调整：\n"
                    f"原方案：{json.dumps(ctx.pending_proposal['proposal'], ensure_ascii=False)}"
                )
                extra_updates["source_ids"] = list(ctx.pending_proposal.get("source_ids") or [])
                extra_updates["attachments"] = list(ctx.pending_proposal.get("pending_files") or [])
            else:
                effective_intent = "work_triage"
        elif route.intent == "chitchat" and (ctx.recent_turns or ctx.pending_proposal):
            effective_intent = "conversational_chat"

        return {
            **ctx_fields,
            **extra_updates,
            "intent": effective_intent,
            "trajectory": traj + [f"tool:fast_route={route.intent}"],
        }

    def _node_action_shortcut(self, state: WorkflowState) -> WorkflowState:
        intent = state.get("intent", "")
        thread_id = state.get("thread_id", "owner")
        raw_text = state.get("raw_text", "")
        traj = list(state.get("trajectory") or []) + [f"node:action_shortcut={intent}"]

        if intent == "confirm_pending":
            pending = self.db.get_latest_pending_proposal(thread_id)
            if not pending:
                return {"reply_text": "当前没有待确认的提案卡片。", "trajectory": traj}
            msg = self.commit_pending_proposal(pending, ideas_only=bool(state.get("pending_ideas_only")))
            return {"reply_text": msg, "trajectory": traj}

        if intent == "discard_pending":
            pending = self.db.get_latest_pending_proposal(thread_id)
            if not pending:
                return {"reply_text": "当前没有可取消的待确认卡片。", "trajectory": traj}
            self.db.cancel_pending_proposal(int(pending["id"]))
            return {"reply_text": f"🗑️ 已作废待确认卡片 #{pending['id']}，未写入任何清单。", "trajectory": traj}

        if intent == "undo":
            ok, msg = self.db.undo_last_commit()
            if ok and self.onedrive is not None:
                self.onedrive.sync_all_lists(self.db)
            return {"reply_text": ("↩️ " if ok else "ℹ️ ") + msg, "trajectory": traj}

        if intent in {"mutate_existing_item", "checkin"}:
            target_id = state.get("target_item_id")
            if target_id is None:
                m_id = re.search(r"#?(\d+)", raw_text)
                target_id = int(m_id.group(1)) if m_id else None
            if target_id is None:
                open_items = self.db.list_items(include_done=False)
                if len(open_items) == 1:
                    target_id = int(open_items[0]["id"])
            if target_id is None:
                return {
                    "reply_text": "请告诉我具体事项编号（例如 `完成 #2 1.0h`），或发送 `负荷` 查看编号列表。",
                    "trajectory": traj,
                }
            res_text = state.get("resolved_text") or raw_text
            is_start = any(k in res_text for k in ("开始", "启动", "正在做", "开工")) and not any(
                k in res_text for k in ("完成", "做完", "搞定", "结束", "闭环")
            )
            if is_start:
                item = self.db.start_item(int(target_id))
                if not item:
                    return {"reply_text": f"未找到待办编号 #{target_id}。", "trajectory": traj}
                if self.onedrive is not None:
                    self.onedrive.sync_all_lists(self.db)
                return {
                    "reply_text": f"▶️ 已记录 **#{item['id']}** 开始执行：`{item['title']}`（{item['actual_start_at']}）。",
                    "trajectory": traj,
                }
            item = self.db.complete_item(int(target_id), actual_hours=state.get("actual_hours"))
            if not item:
                return {"reply_text": f"未找到待办编号 #{target_id}。", "trajectory": traj}
            if self.onedrive is not None:
                self.onedrive.sync_all_lists(self.db)
            span_days = item.get("actual_span_days", 1)
            hrs_note = f"（指定实耗 {item['actual_hours']}h）" if (item.get("actual_hours") or 0) > 0 else ""
            return {
                "reply_text": (
                    f"✅ 已标记 **#{item['id']}** 完成：`{item['title']}`\n"
                    f"实际完成跨度：**`{span_days} 天`**{hrs_note}（已同步刷新云端 `.md`）。"
                ),
                "trajectory": traj,
            }

        return {"reply_text": "收到，请继续指示。", "trajectory": traj}

    def _node_conversational_responder(self, state: WorkflowState) -> WorkflowState:
        traj = list(state.get("trajectory") or []) + ["node:conversational_responder"]
        raw_text = state.get("raw_text", "")
        resolved = state.get("resolved_text") or raw_text
        prompt = (
            f"【近期对话流与时间间隔】\n{state.get('dialogue_context_text', '')}\n\n"
            f"【当前待确认卡片】\n{state.get('pending_context_text', '')}\n\n"
            f"【在途项目与待办快照】\n{state.get('workspace_context_text', '')}\n\n"
            f"【用户当前表达】\n{raw_text}\n（结合语境理解：{resolved}）"
        )
        ans, rec = self.gateway.generate_structured(
            "producer",
            [
                {"role": "system", "content": CONVERSATIONAL_ADVISOR_PROMPT},
                {"role": "user", "content": prompt},
            ],
            ConversationalReply,
            max_tokens=1024,
        )
        self._record_latest_call(rec)
        return {"reply_text": ans.reply, "trajectory": traj}

    def _node_quick_qa_responder(self, state: WorkflowState) -> WorkflowState:
        traj = list(state.get("trajectory") or []) + ["node:quick_qa_responder", "tool:hybrid_search"]
        query = state.get("raw_text", "")
        resolved = state.get("resolved_text") or query
        thread_id = state.get("thread_id", "owner")
        ctx = self.context_assembler.assemble(thread_id, query)
        ev_pack = self.context_assembler.retrieve_long_horizon_evidence(
            ctx,
            raw_text=query,
            resolved_text=resolved,
            search_queries=state.get("search_queries"),
        )

        ev_blocks: list[str] = []
        for h in ev_pack["doc_hits"][:3]:
            pages = read_doc_pages(self.db, h["source_id"], [h["page"]] if h["page"] else None)
            if pages:
                for p in pages[:2]:
                    ev_blocks.append(f"来源《{p['title']}》第 {p['page']} 页：\n{p['text'][:1200]}")
            else:
                ev_blocks.append(f"来源《{h['title']}》：{h['snippet']}")

        for ep in ev_pack["episodic_hits"][:4]:
            r_lbl = "董事长" if ep.get("role") == "user" else "AI助理"
            ev_blocks.append(f"[历史对话 {ep.get('created_at')}] {r_lbl}：{ep.get('content', '')[:500]}")

        for it in ev_pack["matched_items"][:5]:
            ev_blocks.append(
                f"[待办记录 #{it['id']}] [{it['status']}][{it['priority']}][{it['list_type']}] "
                f"{it['project_name']}: {it['title']} (责任人:{it['owner']}, 周期:{it['planned_start_at']}~{it['planned_end_at']}, {it['estimated_hours']}h)"
            )
        for pj in ev_pack["matched_projects"][:3]:
            ev_blocks.append(
                f"[在途项目] {pj['name']} ({pj['work_domain']}) 周期:{pj['planned_start_date']}~{pj['target_end_date']} 累计预估:{pj['total_estimated_hours']}h"
            )

        asks_about_pending = bool(
            ctx.pending_proposal
            and (
                any(k in query for k in ("为什么", "卡片", "排在", "明天", "工时", "刚才", "那张", "这张"))
                or any(k in resolved for k in ("待确认卡片", "卡片 #", "刚才"))
            )
        )
        if not ev_blocks and not asks_about_pending:
            return {
                "reply_text": "未查到相关历史记录或文档依据（为保障准确率，绝不凭猜测作答）。",
                "trajectory": traj,
            }
        if ctx.pending_proposal and (asks_about_pending or ev_pack["has_any_grounding"]):
            ev_blocks.append(ctx.pending_proposal_text)
        if ctx.recent_turns and (asks_about_pending or ev_pack["episodic_hits"]):
            ev_blocks.append(f"近期连续对话上下文：\n{ctx.recent_dialogue_text}")

        traj.append("tool:read_doc_pages")
        q_display = query if resolved == query else f"{query}（语境补全：{resolved}）"
        qa_ans, rec = self.gateway.generate_structured(
            "producer",
            [
                {"role": "system", "content": QA_GROUNDED_PROMPT},
                {"role": "user", "content": f"问题：{q_display}\n\n检索证据：\n" + "\n---\n".join(ev_blocks)},
            ],
            QAGroundedAnswer,
            max_tokens=1536,
        )
        self._record_latest_call(rec)
        if not qa_ans.found:
            reply = "未查到相关历史记录或文档依据。"
        else:
            cites = f"\n📎 出处：{'; '.join(qa_ans.citations)}" if qa_ans.citations else ""
            reply = f"{qa_ans.answer}{cites}"
        return {"reply_text": reply, "trajectory": traj}

    def _node_react_investigator(self, state: WorkflowState) -> WorkflowState:
        traj = list(state.get("trajectory") or []) + ["node:react_investigator"]
        source_ids, excel_tables, att_text = self._ingest_attachments_and_source(state)
        query_text = state.get("raw_text", "")
        resolved = state.get("resolved_text") or query_text
        ctx = self.context_assembler.assemble(state.get("thread_id", "owner"), query_text)
        ev_pack = self.context_assembler.retrieve_long_horizon_evidence(
            ctx,
            raw_text=query_text,
            resolved_text=resolved,
            search_queries=state.get("search_queries"),
            exclude_source_ids=source_ids,
        )
        traj.append("tool:hybrid_search")

        schedule = check_workload_and_schedule(
            self.db,
            start_date=date.today().isoformat(),
            needed_hours=1.0,
            days=14,
            daily_capacity=self.settings.daily_capacity_hours,
        )
        traj.append("tool:check_workload_and_schedule")

        excel_diff = None
        if len(excel_tables) >= 2:
            excel_diff = analyze_excel_quote(excel_tables[-2], excel_tables[-1])
            traj.append("tool:analyze_excel_quote")

        search_brief = None
        if state.get("needs_deep_research"):
            search_brief = search_public_tech_intel(resolved or query_text, self.settings)
            traj.append("tool:search_public_tech_intel")

        cards: list[dict[str, Any]] = []
        for h in ev_pack["doc_hits"]:
            if h["source_id"] not in source_ids:
                cards.append({
                    "source_id": str(h["source_id"]),
                    "title": h["title"],
                    "page_ref": f"第{h['page']}页",
                    "snippet": h["snippet"][:300],
                })
        for ep in ev_pack["episodic_hits"][:3]:
            cards.append({
                "source_id": f"conv_{ep['id']}",
                "title": f"跨时段历史对话 ({ep.get('created_at', '')[:16]})",
                "page_ref": ep.get("role", "user"),
                "snippet": (ep.get("content") or "")[:300],
            })
        if att_text:
            cards.append({"source_id": "incoming_att", "title": "本次附件", "page_ref": "全文提取", "snippet": att_text[:1500]})

        return {
            "source_ids": source_ids,
            "evidence_cards": cards,
            "schedule_snapshot": schedule,
            "excel_diff": excel_diff,
            "search_brief": search_brief,
            "trajectory": traj,
        }

    def _node_context_compactor(self, state: WorkflowState) -> WorkflowState:
        traj = list(state.get("trajectory") or []) + ["node:context_compactor"]
        cards = state.get("evidence_cards") or []
        ev_lines = [
            f"[{c.get('title')} | {c.get('page_ref')}] {c.get('snippet')}"
            for c in cards[:6]
        ]
        ev_text = "\n".join(ev_lines) if ev_lines else "无匹配历史文档证据。"

        tool_parts: list[str] = []
        sched = state.get("schedule_snapshot")
        if sched:
            days_summary = {
                d: f"已排{v['booked_hours']}h/上限{v['capacity']}h"
                for d, v in list(sched.get("days", {}).items())[:7]
            }
            tool_parts.append(
                f"未来7天净工时负荷：{json.dumps(days_summary, ensure_ascii=False)}；"
                f"推荐不超载起始日：{sched.get('recommended_start_date')}"
            )
        if state.get("excel_diff"):
            tool_parts.append(f"Excel精确Diff计算：{json.dumps(state['excel_diff'], ensure_ascii=False)}")
        if state.get("search_brief"):
            tool_parts.append(f"脱敏外部调研：{json.dumps(state['search_brief'], ensure_ascii=False)}")

        return {
            "evidence_text": ev_text,
            "tool_outputs_text": "\n".join(tool_parts),
            "trajectory": traj,
        }

    def _node_producer_drafter(self, state: WorkflowState) -> WorkflowState:
        traj = list(state.get("trajectory") or []) + ["node:producer_drafter"]
        raw_input = state.get("raw_text", "")
        correction = state.get("user_correction", "")
        verdict = state.get("critic_verdict") or {}
        fix_note = verdict.get("fix_instructions", "")

        today_str = date.today().isoformat()
        next_biz = calc_business_date(today_str, 1)
        traj.append("tool:calc_business_date")

        def tool_exec(name: str, args: dict[str, Any]) -> str:
            if name == "check_workload_and_schedule":
                traj.append("tool:check_workload_and_schedule_in_loop")
                res = check_workload_and_schedule(
                    self.db,
                    start_date=args.get("start_date") or today_str,
                    needed_hours=float(args.get("needed_hours", 1.0)),
                    daily_capacity=self.settings.daily_capacity_hours,
                )
                return json.dumps(res, ensure_ascii=False)
            if name == "calc_business_date":
                return calc_business_date(args.get("base_date", today_str), int(args.get("offset_days", 1)))
            return "{}"

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "check_workload_and_schedule",
                    "description": "查询每日已排净工时负荷与推荐可用日期",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string"},
                            "needed_hours": {"type": "number"},
                        },
                    },
                },
            }
        ]

        user_prompt = (
            f"今天日期：{today_str}（下一工作日 {next_biz}）\n"
            f"近期对话上下文：\n{state.get('dialogue_context_text', '')}\n\n"
            f"在途项目与待办快照：\n{state.get('workspace_context_text', '')}\n\n"
            f"用户输入：\n{raw_input}\n"
            + (f"（结合语境补全：{state.get('resolved_text')}）\n\n" if state.get("resolved_text") and state.get("resolved_text") != raw_input else "\n")
            + f"检索证据：\n{state.get('evidence_text', '')}\n\n"
            f"确定性工具事实：\n{state.get('tool_outputs_text', '')}\n"
        )
        if correction:
            user_prompt += f"\n老板人工纠偏要求（务必按此调整）：{correction}\n"
        if fix_note:
            user_prompt += f"\n审计打回整改要求：{fix_note}\n"

        proposal, rec = self.gateway.generate_structured(
            "producer",
            [
                {"role": "system", "content": PRODUCER_TRIAGE_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            TriageProposal,
            tools=tools,
            tool_executor=tool_exec,
            max_tokens=2048,
        )
        self._record_latest_call(rec)
        return {"proposal": proposal.model_dump(mode="json"), "trajectory": traj}

    def _node_heterogeneous_critic(self, state: WorkflowState) -> WorkflowState:
        traj = list(state.get("trajectory") or []) + ["node:heterogeneous_critic"]
        loop_count = int(state.get("loop_count", 0))
        proposal = TriageProposal.model_validate(state["proposal"])

        # 1. Deterministic programmatic audit first
        hard_issues = deterministic_critic_check(
            proposal,
            raw_input=state.get("raw_text", "") + "\n" + state.get("resolved_text", "") + "\n" + state.get("dialogue_context_text", ""),
            evidence_text=state.get("evidence_text", ""),
            tool_outputs_text=state.get("tool_outputs_text", "") + "\n" + state.get("workspace_context_text", ""),
        )
        if hard_issues:
            verdict = CriticVerdict(
                passed=False,
                numeric_fidelity_ok=not any("数值" in x for x in hard_issues),
                schedule_reasonable=not any("净工时" in x for x in hard_issues),
                issues=hard_issues,
                fix_instructions="; ".join(hard_issues),
            )
            return {
                "critic_verdict": verdict.model_dump(mode="json"),
                "loop_count": loop_count + 1,
                "trajectory": traj + ["critic:deterministic_reject"],
            }

        # 2. Heterogeneous deepseek-v4-pro audit
        verdict, rec = self.gateway.generate_structured(
            "critic",
            [
                {"role": "system", "content": CRITIC_AUDIT_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"原始输入：\n{state.get('raw_text', '')}\n\n"
                        f"证据与工具计算结果：\n{state.get('evidence_text', '')}\n{state.get('tool_outputs_text', '')}\n\n"
                        f"待审方案：\n{proposal.model_dump_json()}"
                    ),
                },
            ],
            CriticVerdict,
            max_tokens=1536,
        )
        self._record_latest_call(rec)
        return {
            "critic_verdict": verdict.model_dump(mode="json"),
            "loop_count": loop_count + 1,
            "trajectory": traj + [f"critic:llm_passed={verdict.passed}"],
        }

    def _node_hitl_preview_gate(self, state: WorkflowState) -> WorkflowState:
        traj = list(state.get("trajectory") or []) + ["node:hitl_preview_gate"]
        proposal_dict = state["proposal"]
        proposal = TriageProposal.model_validate(proposal_dict)
        pid = self.db.save_pending_proposal(
            thread_id=state.get("thread_id", "owner"),
            proposal_dict=proposal_dict,
            source_ids=list(state.get("source_ids") or []),
            pending_files=list(state.get("attachments") or []),
        )
        card_text = format_decision_card(pid, proposal)
        assert_no_secrets_leaked(card_text, self.settings)
        return {"proposal_id": pid, "reply_text": card_text, "trajectory": traj}

    @staticmethod
    def _route_after_router(state: WorkflowState) -> str:
        intent = state.get("intent", "work_triage")
        if intent == "chitchat":
            return "chitchat"
        if intent == "quick_query":
            return "quick_qa"
        if intent == "conversational_chat":
            return "conversational"
        if intent in {"confirm_pending", "discard_pending", "mutate_existing_item", "undo", "checkin"}:
            return "action_shortcut"
        return "work_triage"

    @staticmethod
    def _route_after_critic(state: WorkflowState, max_loops: int) -> str:
        verdict = state.get("critic_verdict") or {}
        if verdict.get("passed", False) or int(state.get("loop_count", 0)) >= max_loops:
            return "approve"
        return "revise"

    def _build_graph(self):
        builder = StateGraph(WorkflowState)
        builder.add_node("guardrail_router", self._node_guardrail_router)
        builder.add_node("quick_qa_responder", self._node_quick_qa_responder)
        builder.add_node("conversational_responder", self._node_conversational_responder)
        builder.add_node("action_shortcut", self._node_action_shortcut)
        builder.add_node("react_investigator", self._node_react_investigator)
        builder.add_node("context_compactor", self._node_context_compactor)
        builder.add_node("producer_drafter", self._node_producer_drafter)
        builder.add_node("heterogeneous_critic", self._node_heterogeneous_critic)
        builder.add_node("hitl_preview_gate", self._node_hitl_preview_gate)

        builder.set_entry_point("guardrail_router")
        builder.add_conditional_edges(
            "guardrail_router",
            self._route_after_router,
            {
                "chitchat": END,
                "quick_qa": "quick_qa_responder",
                "conversational": "conversational_responder",
                "action_shortcut": "action_shortcut",
                "work_triage": "react_investigator",
            },
        )
        builder.add_edge("quick_qa_responder", END)
        builder.add_edge("conversational_responder", END)
        builder.add_edge("action_shortcut", END)
        builder.add_edge("react_investigator", "context_compactor")
        builder.add_edge("context_compactor", "producer_drafter")
        builder.add_edge("producer_drafter", "heterogeneous_critic")
        builder.add_conditional_edges(
            "heterogeneous_critic",
            lambda st: self._route_after_critic(st, self.settings.max_reflection_loops),
            {
                "revise": "producer_drafter",
                "approve": "hitl_preview_gate",
            },
        )
        builder.add_edge("hitl_preview_gate", END)
        return builder.compile(checkpointer=self.checkpointer)

    # --- Commit & Shortcut handlers ---

    def commit_pending_proposal(self, pending: dict[str, Any], *, ideas_only: bool = False) -> str:
        """Mint ApprovalToken, pass before_tool_callback, apply atomically, and sync OneDrive."""
        proposal_id = int(pending["id"])
        proposal = TriageProposal.model_validate(pending["proposal"])
        actions = [a for a in proposal.actions if (not ideas_only or a.list_type == ListType.IDEA)]
        if not actions:
            return "当前待确认卡片中没有可落盘的想法项。"

        secret = self.settings.web_access_secret or self.settings.dashscope_api_key
        token = ApprovalToken.mint(proposal_id, secret)

        before_tool_callback(
            "propose_list_mutations",
            {"proposal_id": proposal_id, "count": len(actions)},
            approval_token=token,
            signing_secret=secret,
        )

        archived_paths: list[str] = []
        proj_urls: dict[str, str] = {}
        ymd = date.today().strftime("%Y%m%d")
        first_proj = actions[0].project_name

        if self.onedrive is not None:
            before_tool_callback(
                "organize_onedrive_files",
                {"proposal_id": proposal_id},
                approval_token=token,
                signing_secret=secret,
            )
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

            note_entry = (
                f"### {date.today().isoformat()}｜{proposal.headline}\n"
                f"- **摘要**：{proposal.executive_summary}\n"
                + "\n".join(f"- **[{a.priority.value}]** {a.title}（{a.estimated_hours}h）" for a in actions)
            )
            self.onedrive.append_project_note(first_proj, note_entry)

        commit_res = self.db.apply_proposal_atomic(
            proposal_id=proposal_id,
            actions=actions,
            source_ids=pending.get("source_ids", []),
            doc_paths=archived_paths,
            brief_summary=proposal.executive_summary,
            project_web_urls=proj_urls,
        )

        board_url = ""
        if self.onedrive is not None:
            before_tool_callback(
                "compose_markdown_brief",
                {"proposal_id": proposal_id},
                approval_token=token,
                signing_secret=secret,
            )
            urls = self.onedrive.sync_all_lists(self.db)
            board_url = urls.get("01_今日与行动待办.md", "")

        ids_str = ", ".join(f"#{i}" for i in commit_res["inserted_item_ids"])
        tail = f"\n☁️ 云端看板已刷新：{board_url}" if board_url else ""
        return (
            f"✅ **已确认落盘**（确认卡 #{proposal_id} → 新增项编号 `{ids_str}`）。\n"
            f"可用 `开始 <编号>` / `完成 <编号> 1.5h` 打卡，或 24h 内回复 `撤销` 完整回滚。{tail}"
        )

    def handle_incoming_turn(
        self,
        raw_text: str,
        *,
        sender: str = "owner",
        external_msg_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        thread_id: str = "owner",
    ) -> dict[str, Any]:
        """Unified entry point enforcing `密:` hard guard, instant commands, and LangGraph orchestration."""
        text = (raw_text or "").strip()
        atts = attachments or []

        # 1. `密:` physical zero-cloud-model hard interception (F6)
        if is_confidential_input(text, atts):
            clean_note = text.lstrip()[2:].strip() if text.lstrip().startswith(("密：", "密:")) else text
            ym = date.today().strftime("%Y%m")
            ymd = date.today().strftime("%Y%m%d")
            web_url = ""
            remote_path = ""
            sid, _ = self.db.insert_raw_source(
                source_type="confidential",
                external_msg_id=external_msg_id,
                sender=sender,
                title=f"密件_{ymd}",
                raw_text=clean_note,
                is_confidential=True,
            )
            if self.onedrive is not None:
                for att in atts:
                    fpath = Path(att.get("path", ""))
                    fname = att.get("filename") or fpath.name
                    if fpath.exists():
                        remote_path = f"04_想法与行业参考/{ymd}_密_{fname}"
                        res = self.onedrive.upload_and_cleanup_local(remote_path, fpath)
                        web_url = res.get("webUrl", "")
                if clean_note:
                    remote_path = remote_path or f"04_想法与行业参考/{ymd}_密件备忘_{sid}.md"
                    res = self.onedrive.upload_bytes(
                        f"04_想法与行业参考/{ym}_绝密直存_{sid}.md",
                        f"# 绝密直存记录 #{sid}\n\n{clean_note}\n".encode("utf-8"),
                        content_type="text/markdown; charset=utf-8",
                    )
                    web_url = web_url or res.get("webUrl", "")
                self.db.update_source_onedrive_paths(sid, archive_path=remote_path, web_url=web_url)

            msg = (
                f"🔒 **绝密直存已完成**（0 次云端大模型与外搜调用）。\n"
                f"已安全落盘本地加密库（#{sid}）与世纪互联 OneDrive 私有库。"
                + (f"\n☁️ 直达链接：{web_url}" if web_url else "")
            )
            return {"reply_text": msg, "trajectory": ["guard:confidential_zero_llm"], "confidential": True}

        # 2. Instant shortcut commands (0 LLM calls)
        if text in {"看板", "驾驶舱", "页面", "dashboard"}:
            url = self.magic_link_factory()
            reply = f"📊 **董事长项目管理驾驶舱**（5 分钟单次直开有效，微信内点击免输密码）：\n{url}"
            self._record_turn_pair(thread_id=thread_id, user_text=text, reply_text=reply, intent="shortcut:cockpit_magic_link")
            return {"reply_text": reply, "trajectory": ["shortcut:cockpit_magic_link"]}

        if text in {"负荷", "待办", "今日待办", "todo"}:
            w = self.db.get_daily_workload(days=3, daily_capacity=self.settings.daily_capacity_hours)
            items = self.db.list_items(include_done=False)[:6]
            day_lines = [
                f"- {d}: 排期 **{len(v['items'])} 项**"
                for d, v in w["days"].items()
            ]
            item_lines = [
                f"- `#{it['id']}` `[{it['priority']}]` {it['title']}（{it['planned_start_at'] or '-'}~{it['planned_end_at'] or '-'}）"
                for it in items
            ]
            reply = "📅 **近3日日程分布**：\n" + "\n".join(day_lines) + "\n\n📌 **Top 待办**：\n" + ("\n".join(item_lines) or "- 暂无")
            self._record_turn_pair(thread_id=thread_id, user_text=text, reply_text=reply, intent="shortcut:workload")
            return {"reply_text": reply, "trajectory": ["shortcut:workload"]}

        if text == "撤销":
            ok, msg = self.db.undo_last_commit()
            if ok and self.onedrive is not None:
                self.onedrive.sync_all_lists(self.db)
            reply = ("↩️ " if ok else "ℹ️ ") + msg
            self._record_turn_pair(thread_id=thread_id, user_text=text, reply_text=reply, intent="shortcut:undo")
            return {"reply_text": reply, "trajectory": ["shortcut:undo"]}

        m_start = re.match(r"^开始\s*#?(\d+)$", text)
        if m_start:
            item = self.db.start_item(int(m_start.group(1)))
            if not item:
                reply = f"未找到待办编号 #{m_start.group(1)}。"
                self._record_turn_pair(thread_id=thread_id, user_text=text, reply_text=reply, intent="shortcut:start_not_found")
                return {"reply_text": reply, "trajectory": ["shortcut:start_not_found"]}
            if self.onedrive is not None:
                self.onedrive.sync_all_lists(self.db)
            reply = f"▶️ 已记录 **#{item['id']}** 开始执行：`{item['title']}`（{item['actual_start_at']}）。"
            self._record_turn_pair(thread_id=thread_id, user_text=text, reply_text=reply, intent="shortcut:start_item")
            return {"reply_text": reply, "trajectory": ["shortcut:start_item"]}

        m_done = re.match(r"^完成\s*#?(\d+)(?:\s+(\d+(?:\.\d+)?)\s*[hH小时]?)?$", text)
        if m_done:
            hrs = float(m_done.group(2)) if m_done.group(2) else None
            item = self.db.complete_item(int(m_done.group(1)), actual_hours=hrs)
            if not item:
                reply = f"未找到待办编号 #{m_done.group(1)}。"
                self._record_turn_pair(thread_id=thread_id, user_text=text, reply_text=reply, intent="shortcut:done_not_found")
                return {"reply_text": reply, "trajectory": ["shortcut:done_not_found"]}
            if self.onedrive is not None:
                self.onedrive.sync_all_lists(self.db)
            span_days = item.get("actual_span_days", 1)
            hrs_note = f"（指定实耗 {item['actual_hours']}h）" if (hrs is not None or (item.get("actual_hours") or 0) > 0) else ""
            reply = (
                f"✅ 已标记 **#{item['id']}** 完成：`{item['title']}`\n"
                f"实际完成跨度：**`{span_days} 天`**{hrs_note}（已同步刷新云端 `.md` 与周期校准基准）。"
            )
            self._record_turn_pair(thread_id=thread_id, user_text=text, reply_text=reply, intent="shortcut:complete_item")
            return {"reply_text": reply, "trajectory": ["shortcut:complete_item"]}

        # 3. HITL Pending Proposal response (`1`, `2`, `改：...`) - survives restarts via SQLite!
        pending = self.db.get_latest_pending_proposal(thread_id)
        if pending and text in {"1", "确认", "2", "仅存想法"}:
            msg = self.commit_pending_proposal(pending, ideas_only=(text in {"2", "仅存想法"}))
            self._record_turn_pair(
                thread_id=thread_id,
                user_text=text,
                reply_text=msg,
                intent="hitl:commit_confirmed",
                proposal_id=int(pending["id"]),
            )
            return {"reply_text": msg, "trajectory": ["hitl:commit_confirmed"]}

        if pending and text.startswith(("改：", "改:")):
            corr = text[2:].strip()
            rev_state: WorkflowState = {
                "thread_id": f"{thread_id}:rev:{pending['id']}",
                "raw_text": f"对确认卡 #{pending['id']} 原提案的调整：\n原方案：{json.dumps(pending['proposal'], ensure_ascii=False)}",
                "source_ids": pending["source_ids"],
                "attachments": pending["pending_files"],
                "user_correction": corr,
                "loop_count": 0,
            }
            with self._turn_lock:
                out = self.graph.invoke(rev_state, config={"configurable": {"thread_id": rev_state["thread_id"]}})
            self._record_turn_pair(
                thread_id=thread_id,
                user_text=text,
                reply_text=out["reply_text"],
                intent="hitl:revise",
                proposal_id=out.get("proposal_id"),
            )
            return {
                "reply_text": out["reply_text"],
                "proposal_id": out.get("proposal_id"),
                "trajectory": out.get("trajectory", []),
            }

        # 4. Run full LangGraph cognitive workflow
        init_state: WorkflowState = {
            "thread_id": thread_id,
            "raw_text": text,
            "sender": sender,
            "external_msg_id": external_msg_id or "",
            "attachments": atts,
            "loop_count": 0,
            "trajectory": [],
        }
        with self._turn_lock:
            out = self.graph.invoke(init_state, config={"configurable": {"thread_id": f"{thread_id}:{external_msg_id or date.today().isoformat()}"}})
        self._record_turn_pair(
            thread_id=thread_id,
            user_text=text or f"[附件: {', '.join(a.get('filename', 'file') for a in atts)}]",
            reply_text=out["reply_text"],
            intent=out.get("intent", "work_triage"),
            proposal_id=out.get("proposal_id"),
        )
        return {
            "reply_text": out["reply_text"],
            "proposal_id": out.get("proposal_id"),
            "source_ids": out.get("source_ids", []),
            "trajectory": out.get("trajectory", []),
        }
