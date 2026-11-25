"""4-layer Multi-Horizon Context Assembler for continuous & discontinuous WeCom dialogue."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from wechat_assistant.config import now_local
from wechat_assistant.storage.db import Database
from wechat_assistant.tools.memory_tools import hybrid_search

_ANAPHORIC_CUES = (
    "刚才",
    "上轮",
    "上次",
    "前两天",
    "那件事",
    "那个",
    "这个",
    "那张",
    "这张",
    "它们",
    "它",
    "他",
    "她",
    "为什么",
)

_STOP_TOKENS = {
    "项目",
    "问题",
    "事情",
    "东西",
    "情况",
    "预算",
    "方案",
    "时候",
    "之前",
    "前两天",
    "昨天",
    "今天",
    "刚才",
    "那个",
    "这个",
    "怎么",
    "多少",
    "什么",
    "哪些",
    "哪里",
    "是谁",
    "一下",
    "聊的",
    "说过",
    "提到",
    "请问",
    "帮我",
    "安排",
}


def _parse_ts(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _safe_json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _format_gap_label(delta_seconds: float) -> str:
    mins = max(1, int(delta_seconds // 60))
    if mins < 60:
        return f"{mins} 分钟"
    hours = round(delta_seconds / 3600.0, 1)
    if hours < 24:
        return f"{hours} 小时"
    days = round(delta_seconds / 86400.0, 1)
    return f"{days} 天"


def extract_topic_tags(text: str, known_projects: list[str] | None = None) -> list[str]:
    """Extract normalized entity & project tags for long-horizon episodic recall."""
    clean = (text or "").strip()
    if not clean:
        return []
    tags: list[str] = []
    seen: set[str] = set()

    def add_tag(tok: str) -> None:
        t = tok.strip()
        if len(t) >= 2 and t not in _STOP_TOKENS and t not in seen:
            seen.add(t)
            tags.append(t)

    for proj in known_projects or []:
        if proj and proj in clean:
            add_tag(proj)

    # Extract explicit file names, alphanumeric tokens, and clean Chinese noun runs
    for m in re.findall(r"[A-Za-z0-9_.-]{2,30}", clean):
        add_tag(m)

    cleaned_cn = clean
    for stop in _STOP_TOKENS:
        cleaned_cn = cleaned_cn.replace(stop, " ")
    for phrase in re.findall(r"[\u4e00-\u9fff]{2,14}", cleaned_cn):
        add_tag(phrase)
        # Also index 2-4 char sub-tokens for unspaced Chinese compound queries
        if len(phrase) >= 4:
            for size in (3, 4):
                for i in range(0, len(phrase) - size + 1):
                    sub = phrase[i : i + size]
                    add_tag(sub)

    return tags[:16]


@dataclass
class AssembledContext:
    recent_turns: list[dict[str, Any]] = field(default_factory=list)
    recent_turn_ids: set[int] = field(default_factory=set)
    pending_proposal: dict[str, Any] | None = None
    pending_is_fresh: bool = False
    rolling_summary_text: str = "（暂无跨天滚动摘要）"
    project_context_text: str = ""
    recent_dialogue_text: str = "（暂无近期对话记录）"
    pending_proposal_text: str = "（当前无待确认卡片）"
    workspace_snapshot_text: str = "（当前无在途项目或待办）"
    anchor_entities: list[str] = field(default_factory=list)


class ContextAssembler:
    """Builds multi-horizon prompt context across active dialogue, pending HITL cards, workspace state, and past episodes."""

    CONTINUOUS_GAP_MINUTES = 30.0
    FRESH_PENDING_MINUTES = 60.0

    def __init__(self, db: Database) -> None:
        self.db = db

    def assemble(self, thread_id: str = "owner", current_text: str = "") -> AssembledContext:
        recent_turns = self.db.get_recent_conversation_turns(thread_id=thread_id, limit=30)
        recent_ids = {int(t["id"]) for t in recent_turns}

        now_dt = now_local().replace(tzinfo=None)
        dialogue_lines: list[str] = []
        prev_dt: datetime | None = None
        for turn in recent_turns:
            cur_dt = _parse_ts(turn.get("created_at"))
            if prev_dt and cur_dt:
                gap_sec = (cur_dt - prev_dt).total_seconds()
                if gap_sec > self.CONTINUOUS_GAP_MINUTES * 60:
                    dialogue_lines.append(f"--- [时间间隔 {_format_gap_label(gap_sec)} · 跨时段对话] ---")
            role_label = "董事长" if turn.get("role") == "user" else "AI助理"
            snippet = (turn.get("content") or "").replace("\n", " ").strip()[:600]
            ts_short = (turn.get("created_at") or "")[5:16]
            dialogue_lines.append(f"[{ts_short}] {role_label}: {snippet}")
            prev_dt = cur_dt

        if prev_dt:
            tail_gap = (now_dt - prev_dt).total_seconds()
            if tail_gap > self.CONTINUOUS_GAP_MINUTES * 60:
                dialogue_lines.append(f"--- [距上一句间隔 {_format_gap_label(tail_gap)} · 请谨慎区分连续追问与全新话题] ---")

        # Extract salient anchor entities from trailing continuous episode only
        anchor_entities: list[str] = []
        seen_ent: set[str] = set()
        for idx in range(len(recent_turns) - 1, -1, -1):
            t = recent_turns[idx]
            cur_dt = _parse_ts(t.get("created_at"))
            if cur_dt and (now_dt - cur_dt).total_seconds() > self.FRESH_PENDING_MINUTES * 60:
                break
            for tag in t.get("topic_tags") or []:
                if tag not in seen_ent:
                    seen_ent.add(tag)
                    anchor_entities.append(tag)
            if len(anchor_entities) >= 6:
                break

        pending = self.db.get_latest_pending_proposal(thread_id)
        pending_fresh = False
        pending_text = "（当前无待确认卡片）"
        if pending:
            p_dt = _parse_ts(pending.get("created_at"))
            age_min = ((now_dt - p_dt).total_seconds() / 60.0) if p_dt else 0.0
            pending_fresh = age_min <= self.FRESH_PENDING_MINUTES
            prop = pending.get("proposal") or {}
            act_lines = [
                f"  - [{a.get('priority')}][{a.get('list_type')}] {a.get('project_name')}: {a.get('title')} "
                f"(负责人:{a.get('owner')}, 实施人:{a.get('assignee') or a.get('owner')}, "
                f"周期 {a.get('planned_start_at')}~{a.get('planned_end_at') or '待补齐'})"
                for a in prop.get("actions", [])[:6]
            ]
            for upd in prop.get("task_updates", [])[:6]:
                tl = upd.get("timeline_entry") or {}
                act_lines.append(
                    f"  - [归入已有任务 #{upd.get('target_task_id')}] {upd.get('target_task_title', '')}: "
                    f"{tl.get('summary', '')}"
                )
            for fyi in prop.get("fyi_notices", [])[:4]:
                act_lines.append(f"  - [抄送知会] {fyi.get('summary', '')}")
            pending_text = (
                f"待确认卡片 #{pending['id']}（生成于 {pending.get('created_at')}，距今约 {max(0, int(age_min))} 分钟，"
                f"{'仍在当前连续讨论窗口内' if pending_fresh else '已隔较长时间'}）：\n"
                f"- 标题：{prop.get('headline', '')}\n"
                f"- 摘要：{prop.get('executive_summary', '')}\n"
                + ("\n".join(act_lines) if act_lines else "  - （无明细动作）")
            )

        projects = self.db.list_projects()
        all_open_items = self.db.list_items(include_done=False)
        open_items = all_open_items[:60]
        rules = self.db.list_memory_rules()[:20]

        latest_ep = self.db.get_latest_episode_summary(thread_id)
        rolling_summary_text = (
            f"（更新于 {latest_ep['updated_at']}）{latest_ep['summary_text']}"
            if latest_ep
            else "（暂无跨天滚动摘要）"
        )

        # Cross-project auto-mount: attach project brief & open items whenever current input or recent anchors mention a project
        match_hay = (current_text or "") + " " + " ".join(anchor_entities)
        proj_cards: list[str] = []
        for p in projects:
            aliases = _safe_json_list(p.get("aliases_json"))
            names = [p["name"], *[str(a) for a in aliases if a]]
            if any(n and n in match_hay for n in names):
                p_items = [it for it in all_open_items if it.get("project_name") == p["name"]][:5]
                p_item_lines = "; ".join(f"#{it['id']}({it['status']}): {it['title']}" for it in p_items) or "暂无未完成待办"
                proj_cards.append(
                    f"- 项目【{p['name']}】（{p['work_domain']}｜周期 {p['planned_start_date'] or '-'}~{p['target_end_date'] or '-'}）："
                    f"进展={p.get('latest_brief') or '无'}｜待办=[{p_item_lines}]"
                )
                if len(proj_cards) >= 3:
                    break
        project_context_text = "\n".join(proj_cards)

        ws_parts: list[str] = []
        if projects:
            proj_strs = [f"{p['name']}({p['work_domain']})" for p in projects[:30]]
            ws_parts.append("在途项目：" + "；".join(proj_strs))
        if open_items:
            ws_parts.append(
                "未完成待办/等待项：\n"
                + "\n".join(
                    f"  - #{it['id']} [{it['priority']}][{it['list_type']}][{it['status']}] "
                    f"{it['project_name']}: {it['title']} "
                    f"(负责人:{it['owner']}, 实施人:{it.get('assignee') or it['owner']}, "
                    f"外部:{it.get('external_partner') or '无'}, "
                    f"交付物:{(it.get('deliverable') or '')[:40]}, "
                    f"阶段:{it.get('milestone_stage') or '-'}, "
                    f"周期:{it['planned_start_at']}~{it['planned_end_at'] or '待补齐'})"
                    for it in open_items
                )
            )
        if rules:
            ws_parts.append("个人习惯与周期基线：" + "；".join(r["rule_text"][:60] for r in rules[:5]))

        return AssembledContext(
            recent_turns=recent_turns,
            recent_turn_ids=recent_ids,
            pending_proposal=pending,
            pending_is_fresh=pending_fresh,
            rolling_summary_text=rolling_summary_text,
            project_context_text=project_context_text,
            recent_dialogue_text="\n".join(dialogue_lines) if dialogue_lines else "（暂无近期对话记录）",
            pending_proposal_text=pending_text,
            workspace_snapshot_text="\n".join(ws_parts) if ws_parts else "（当前无在途项目或待办）",
            anchor_entities=anchor_entities,
        )

    def render_for_router(self, ctx: AssembledContext, current_text: str) -> str:
        proj_block = f"【相关项目上下文卡】\n{ctx.project_context_text}\n\n" if ctx.project_context_text else ""
        return (
            f"【当前时间戳】{now_local().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"【跨天滚动会话摘要】\n{ctx.rolling_summary_text}\n\n"
            f"{proj_block}"
            f"【近期对话流与时间间隔】\n{ctx.recent_dialogue_text}\n\n"
            f"【当前待确认卡片】\n{ctx.pending_proposal_text}\n\n"
            f"【在途项目与待办快照】\n{ctx.workspace_snapshot_text}\n\n"
            f"【用户最新输入】\n{current_text or '（收到文件附件）'}"
        )

    def retrieve_long_horizon_evidence(
        self,
        ctx: AssembledContext,
        *,
        raw_text: str,
        resolved_text: str = "",
        search_queries: list[str] | None = None,
        exclude_source_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """Search documents (`raw_sources`), older discontinuous chat history, and open workspace items."""
        known_projects = [p["name"] for p in self.db.list_projects()]
        queries: list[str] = []
        seen_q: set[str] = set()

        def push_q(q: str) -> None:
            clean = (q or "").strip()
            if len(clean) >= 2 and clean not in seen_q:
                seen_q.add(clean)
                queries.append(clean)

        for sq in search_queries or []:
            push_q(sq)
        if resolved_text:
            push_q(resolved_text)
        push_q(raw_text)

        clean_raw = (raw_text or "").strip()
        needs_coref = len(clean_raw) <= 7 or any(cue in clean_raw for cue in _ANAPHORIC_CUES)
        if needs_coref:
            for ent in ctx.anchor_entities[:3]:
                push_q(ent)

        # Build fine-grained search tokens for unspaced Chinese episodic & document queries
        search_tokens: list[str] = []
        for q in queries:
            for tok in extract_topic_tags(q, known_projects):
                if tok not in search_tokens:
                    search_tokens.append(tok)
            if q not in search_tokens and len(q) <= 24:
                search_tokens.append(q)

        excl_src = set(exclude_source_ids or [])
        doc_hits: list[dict[str, Any]] = []
        seen_doc: set[tuple[int, Any]] = set()
        for q in [*queries[:3], *search_tokens[:4]]:
            for h in hybrid_search(self.db, q, top_k=4):
                sid = int(h["source_id"])
                if sid in excl_src:
                    continue
                key = (sid, h.get("page"))
                if key not in seen_doc:
                    seen_doc.add(key)
                    doc_hits.append(h)

        episodic_hits = self.db.search_conversation_turns(
            search_tokens,
            exclude_ids=ctx.recent_turn_ids,
            limit=8,
        )

        # Match active/all items and projects by tokens
        matched_items: list[dict[str, Any]] = []
        matched_projects: list[dict[str, Any]] = []
        tok_lowers = [t.lower() for t in search_tokens if len(t) >= 2]
        if tok_lowers:
            for proj in self.db.list_projects():
                hay = f"{proj['name']} {proj['work_domain']} {proj.get('latest_brief', '')}".lower()
                if any(t in hay for t in tok_lowers):
                    matched_projects.append(proj)
            for it in self.db.list_items(include_done=True):
                cmt_blob = " ".join(
                    c.get("content", "") if isinstance(c, dict) else str(c)
                    for c in (it.get("comments") or [])
                )
                eval_blob = " ".join(
                    c.get("content", "") if isinstance(c, dict) else str(c)
                    for c in (it.get("ceo_evaluation") or [])
                )
                hay = (
                    f"#{it['id']} {it['title']} {it['project_name']} {it['owner']} "
                    f"{it.get('assignee', '')} {it.get('external_partner', '')} "
                    f"{it.get('deliverable', '')} {it.get('milestone_stage', '')} "
                    f"{it.get('blocker_note', '')} {it['work_domain']} {cmt_blob} {eval_blob}"
                ).lower()
                if any(t in hay for t in tok_lowers):
                    matched_items.append(it)
                    if len(matched_items) >= 15:
                        break

        return {
            "doc_hits": doc_hits[:10],
            "episodic_hits": episodic_hits,
            "matched_items": matched_items,
            "matched_projects": matched_projects,
            "has_any_grounding": bool(doc_hits or episodic_hits or matched_items or matched_projects),
        }
