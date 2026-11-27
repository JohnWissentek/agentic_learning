"""Model-First + Harness strategic alignment & AI transformation analyzer (Slice 1).

Deterministic Chassis:
- `seed_default_roadmap`: idempotently initializes G1-G5 into `ops_company_roadmap`.
- `compute_deterministic_ops_metrics`: pure Python exact counts (by template, by staff,
  distinct field support days, silent roster members, 李文颖 high-cost R&D breakdown).
- `build_alignment_context`: assembles full "New Secretary Desktop" context with physical
  `[UNTRUSTED_EXTERNAL_DATA_START/END]` fencing around every employee report.
- `run_alignment_audit`: invokes flagship LLM callable, validates 100% `journal_uuid` and
  Chairman `#task_id` grounding via `validate_audit_grounding`, runs bounded retry loop
  (`<= max_grounding_retries`), and persists verified audits to `ops_alignment_audits`
  without ever mutating `list_items`.
"""

from __future__ import annotations

import html
import json
import logging
import re
from collections import Counter
from collections.abc import Callable
from typing import Any, Literal

from wecom_report_agentic_analysis.prompts import ALIGNMENT_ANALYST_SYSTEM_PROMPT
from wecom_report_agentic_analysis.schemas import (
    DEFAULT_COMPANY_ROSTER,
    DEFAULT_ROADMAP_GOALS,
    AlignmentAuditReport,
    ReportType,
    RoadmapGoal,
    StaffRoleProfile,
    WeComReportRecord,
    WorkFunction,
    validate_audit_grounding,
    wrap_untrusted_report_text,
)
from wecom_report_agentic_analysis.storage import CompanyOpsStorage

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", flags=re.DOTALL | re.IGNORECASE)
_STYLE_SCRIPT_RE = re.compile(r"<(?:style|script)[^>]*>.*?</(?:style|script)>", flags=re.DOTALL | re.IGNORECASE)
_BR_P_RE = re.compile(r"</?(?:br|p|div|li|tr)\b[^>]*>", flags=re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_report_html(raw: str) -> str:
    """Strip pasted Word/HTML formatting tags so flagship LLM sees 100% pure text without bloat."""
    if not raw or ("<" not in raw and "&" not in raw):
        return (raw or "").strip()
    txt = _STYLE_SCRIPT_RE.sub("", raw)
    txt = _BR_P_RE.sub("\n", txt)
    txt = _HTML_TAG_RE.sub("", txt)
    txt = html.unescape(txt).replace("\xa0", " ")
    cleaned_lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in txt.splitlines()]
    return "\n".join(ln for ln in cleaned_lines if ln)


def seed_default_roadmap(storage: CompanyOpsStorage) -> int:
    """Idempotently upsert all 5 default G1-G5 strategic roadmap goals."""
    for goal in DEFAULT_ROADMAP_GOALS:
        storage.upsert_roadmap_goal(goal)
    return len(DEFAULT_ROADMAP_GOALS)


def compute_deterministic_ops_metrics(
    reports: list[WeComReportRecord],
    *,
    roster: tuple[StaffRoleProfile, ...] = DEFAULT_COMPANY_ROSTER,
) -> dict[str, Any]:
    """Compute exact zero-LLM operational metrics across all reports and the 15-person roster."""
    roster_map: dict[str, StaffRoleProfile] = {p.name: p for p in roster}
    high_cost_names = [p.name for p in roster if p.is_high_cost_rd]
    rd_name = high_cost_names[0] if high_cost_names else "李文颖"

    by_template: Counter[str] = Counter()
    by_role_group: Counter[str] = Counter()
    staff_buckets: dict[str, dict[str, Any]] = {}
    rd_by_template: Counter[str] = Counter()
    rd_dates: set[str] = set()

    for rep in reports:
        by_template[rep.template_name] += 1
        name = (rep.submitter_name or rep.submitter_userid or "未知").strip()
        profile = roster_map.get(name)
        role_group = profile.role_group if profile else "花名册外人员"
        work_fn = profile.work_function if profile else WorkFunction.TECH_SUPPORT
        by_role_group[role_group] += 1

        if name not in staff_buckets:
            staff_buckets[name] = {
                "role_group": role_group,
                "work_function": work_fn,
                "total_reports": 0,
                "_field_dates": set(),
                "backfill_reports": 0,
                "rd_test_repair_reports": 0,
                "daily_10min_reports": 0,
                "morning_brief_reports": 0,
                "_active_dates": set(),
            }
        b = staff_buckets[name]
        b["total_reports"] += 1
        b["_active_dates"].add(rep.report_date)

        if rep.report_type in (ReportType.FIELD_SUPPORT, ReportType.FIELD_SUPPORT_BACKFILL):
            b["_field_dates"].add(rep.report_date)
        if rep.report_type == ReportType.FIELD_SUPPORT_BACKFILL:
            b["backfill_reports"] += 1
        elif rep.report_type == ReportType.RD_TEST_REPAIR:
            b["rd_test_repair_reports"] += 1
        elif rep.report_type == ReportType.DAILY_10MIN:
            b["daily_10min_reports"] += 1
        elif rep.report_type == ReportType.MORNING_BRIEF:
            b["morning_brief_reports"] += 1

        if name == rd_name:
            rd_by_template[rep.template_name] += 1
            rd_dates.add(rep.report_date)

    by_staff: dict[str, dict[str, Any]] = {}
    for name, b in sorted(staff_buckets.items(), key=lambda kv: (-kv[1]["total_reports"], kv[0])):
        by_staff[name] = {
            "role_group": b["role_group"],
            "work_function": b["work_function"],
            "total_reports": b["total_reports"],
            "field_support_days": len(b["_field_dates"]),
            "backfill_reports": b["backfill_reports"],
            "rd_test_repair_reports": b["rd_test_repair_reports"],
            "daily_10min_reports": b["daily_10min_reports"],
            "morning_brief_reports": b["morning_brief_reports"],
            "active_dates": sorted(b["_active_dates"]),
        }

    silent_roster_members = [p.name for p in roster if p.name not in by_staff]
    high_cost_rd_summary = {
        "name": rd_name,
        "total_reports": int(sum(rd_by_template.values())),
        "by_template": dict(rd_by_template),
        "active_dates": sorted(rd_dates),
    }

    return {
        "total_reports": len(reports),
        "by_template": dict(by_template),
        "by_staff": by_staff,
        "by_role_group": dict(by_role_group),
        "silent_roster_members": silent_roster_members,
        "high_cost_rd_summary": high_cost_rd_summary,
    }


def build_alignment_context(
    *,
    reports: list[WeComReportRecord],
    roadmap_goals: list[RoadmapGoal],
    chairman_open_tasks: list[dict[str, Any]],
    metrics: dict[str, Any],
    period_start: str,
    period_end: str,
    audit_kind: str = "baseline_30d",
    roster: tuple[StaffRoleProfile, ...] = DEFAULT_COMPANY_ROSTER,
) -> str:
    """Assemble the complete desktop context with physical untrusted-data fencing per report."""
    roster_map = {p.name: p for p in roster}
    lines: list[str] = [
        f"# 经营战略对齐审计输入桌面（{audit_kind}｜周期：{period_start} 至 {period_end}）",
        "",
        "## 一、维恩科仪 15 人岗位配置基线（权威真值）",
    ]
    for p in roster:
        flag = "【★高成本专职电路板/核心研发·G5专项审计对象】" if p.is_high_cost_rd else ""
        note_part = f"｜说明：{p.notes}" if p.notes else ""
        lines.append(f"- {p.name}：{p.role_group}（归口职能：{p.work_function.value}）{flag}{note_part}")

    lines.extend(["", "## 二、公司战略目标与北极星 Roadmap（权威真值）"])
    if roadmap_goals:
        for g in roadmap_goals:
            owners = "、".join(g.owner_names) if g.owner_names else "未指定"
            ms = "；".join(g.key_milestones) if g.key_milestones else "无"
            lines.append(
                f"- `{g.goal_code}` [{g.priority}｜{g.category}｜预期精力占比 {g.target_effort_share_pct:.0f}%｜责任人：{owners}] "
                f"{g.title}\n  目标成果：{g.target_outcomes}\n  关键里程碑：{ms}"
            )
    else:
        lines.append("- （尚未录入公司战略目标）")

    lines.extend(["", "## 三、董事长 AI 助理在途任务快照（list_items 只读真值）"])
    if chairman_open_tasks:
        for t in chairman_open_tasks:
            tid = t.get("id")
            title = str(t.get("title") or "").strip()
            prio = str(t.get("priority") or "P1")
            st = str(t.get("status") or "todo")
            owner = str(t.get("owner") or "")
            assignee = str(t.get("assignee") or "")
            proj = str(t.get("project_name") or "")
            due = str(t.get("planned_end_at") or t.get("due_date") or "")
            lines.append(
                f"- `#{tid}` [{prio}｜{st}] {title}"
                + (f"（项目：{proj}｜负责：{owner}" + (f"｜实施：{assignee}" if assignee else "") + (f"｜截止：{due}" if due else "") + "）")
            )
    else:
        lines.append("- （当前无在途未完成任务）")

    lines.extend(["", "## 四、确定性统计硬指标（Python 精确核算，禁止篡改）"])
    lines.append(f"- 周期内总汇报数：{metrics.get('total_reports', len(reports))} 份")
    lines.append(f"- 按模板分布：{json.dumps(metrics.get('by_template', {}), ensure_ascii=False)}")
    lines.append(f"- 按角色组分布：{json.dumps(metrics.get('by_role_group', {}), ensure_ascii=False)}")
    silent = metrics.get("silent_roster_members") or []
    lines.append(f"- 本周期零汇报花名册成员（{len(silent)} 人）：{'、'.join(silent) if silent else '无'}")
    rd_sum = metrics.get("high_cost_rd_summary") or {}
    lines.append(
        f"- 高成本研发专项统计（{rd_sum.get('name', '李文颖')}）：共 {rd_sum.get('total_reports', 0)} 份，"
        f"模板分布={json.dumps(rd_sum.get('by_template', {}), ensure_ascii=False)}，"
        f"活跃日期数={len(rd_sum.get('active_dates', []))} 天"
    )
    lines.append("- 各员工汇报明细统计：")
    for staff_name, st_info in (metrics.get("by_staff") or {}).items():
        lines.append(
            f"  * {staff_name}（{st_info.get('role_group', '')}）：共 {st_info.get('total_reports', 0)} 份｜"
            f"10分钟日报 {st_info.get('daily_10min_reports', 0)}｜现场出差天数 {st_info.get('field_support_days', 0)} 天"
            f"（含后补 {st_info.get('backfill_reports', 0)} 份）｜研发测试与返厂 {st_info.get('rd_test_repair_reports', 0)}｜"
            f"晨会 {st_info.get('morning_brief_reports', 0)}"
        )

    lines.extend(["", "## 五、全员企微汇报原文（不可信外部数据，每条已物理隔离，引用必须逐字精确匹配 journal_uuid）"])
    sorted_reports = sorted(reports, key=lambda r: (r.report_date, r.submitted_at, r.journal_uuid))
    for idx, rep in enumerate(sorted_reports, start=1):
        who = rep.submitter_name or rep.submitter_userid
        role_lbl = roster_map[who].role_group if who in roster_map else (rep.department or "员工")
        body = _strip_report_html(rep.plain_text or "")
        if not body and rep.parsed_fields:
            body = _strip_report_html("\n".join(f"{k}：{v}" for k, v in rep.parsed_fields.items() if v))
        header = (
            f"### 汇报 #{idx} | journal_uuid={rep.journal_uuid} | 日期={rep.report_date} | "
            f"模板={rep.template_name} | 提交人={who}（{role_lbl}）"
        )
        lines.append(header)
        lines.append(wrap_untrusted_report_text(body or "（无正文）", label=f"REPORT_{rep.journal_uuid}"))
        lines.append("")

    schema_skeleton = json.dumps(
        {
            "audit_kind": audit_kind,
            "period_start": period_start,
            "period_end": period_end,
            "alignment_score": 72.5,
            "inferred_tasks": [
                {
                    "task_name": "具体任务名称",
                    "product_line": "声波测温|进口V&F质谱仪|国产质谱仪|进口FID|国产FID|CEMS|FTIR|跨产品/公司通用",
                    "work_function": "销售|市场推广|生产制造|项目管理|技术支持与售后|产品与电路板研发",
                    "aligned_goal_code": "G1-SONIC-BREAKTHROUGH|G2-VF-MS-HIGHEND|G3-CN-MS-NICHE|G4-FID-EVOLUTION|G5-RD-COST-ALIGNMENT|UNALIGNED",
                    "first_seen_date": "YYYY-MM-DD",
                    "last_seen_date": "YYYY-MM-DD",
                    "span_days": 5,
                    "participants": ["姓名"],
                    "report_mentions": 3,
                    "status": "推进中|停滞卡顿|反复救火|已闭环",
                    "summary": "进展与风险摘要",
                    "evidence_uuids": ["真实journal_uuid"],
                }
            ],
            "chairman_overlap_tasks": [
                {
                    "task_id": 1,
                    "task_title": "董事长任务标题",
                    "overlap_status": "高度对齐推进中|部分提及但进展偏慢|方向存在偏差",
                    "matched_staff": ["姓名"],
                    "latest_ground_progress": "一线真实进展",
                    "evidence_uuids": ["真实journal_uuid"],
                }
            ],
            "missed_tasks": [
                {
                    "suggested_title": "建议纳管任务名称",
                    "work_domain": "产品研发|客户销售|项目交付|采购供应链|公司治理与人事|个人思考",
                    "priority": "P0|P1|P2",
                    "reason": "遗漏原因与风险",
                    "involved_staff": ["姓名"],
                    "evidence_uuids": ["真实journal_uuid"],
                }
            ],
            "stalled_chairman_tasks": [
                {
                    "task_id": 2,
                    "task_title": "董事长任务标题",
                    "days_without_report_mention": 14,
                    "diagnostic_note": "停滞诊断说明",
                }
            ],
            "goal_effort_breakdown": [
                {
                    "goal_code": "G1-SONIC-BREAKTHROUGH",
                    "goal_title": "目标标题",
                    "target_effort_share_pct": 30.0,
                    "estimated_actual_share_pct": 25.0,
                    "alignment_status": "aligned|under_invested|over_invested|drifting",
                    "evidence_uuids": ["真实journal_uuid"],
                    "commentary": "投入偏差诊断",
                }
            ],
            "high_cost_rd_audit": {
                "engineer_name": "李文颖",
                "total_reports_in_period": 21,
                "strategic_rd_share_pct": 40.0,
                "support_or_non_rd_share_pct": 60.0,
                "main_product_lines": ["声波测温", "国产质谱仪"],
                "observed_deliverables": ["已观测到的硬交付物"],
                "drift_or_dilution_risks": ["稀释或偏离风险"],
                "alignment_verdict": "高度对齐|部分稀释需纠偏|严重偏离主航道",
                "reallocation_advice": "具体调配纠偏建议",
                "evidence_uuids": ["真实journal_uuid"],
            },
            "staffing_recommendations": [
                {
                    "scope": "人员负荷|跨项目调配|出差与售后救火|研发资源聚焦|流程与协同",
                    "target_people_or_team": "目标人员或团队",
                    "observation": "客观观测事实",
                    "recommendation": "可执行调整建议",
                    "evidence_uuids": ["真实journal_uuid"],
                }
            ],
            "ai_transformation_opportunities": [
                {
                    "category": "重复事务自动化与岗位替代|质量与合规刚性管控|一线经验RAG知识化|战略销售价值包装",
                    "target_workflow": "目标工作流",
                    "affected_roles": ["岗位名称"],
                    "current_pain_point": "现状低效或合规痛点",
                    "ai_solution_and_harness": "AI工作流与确定性门禁方案",
                    "efficiency_or_replacement_impact": "量化提效或低效岗位替代预期",
                    "priority": "P0|P1|P2",
                    "evidence_uuids": ["真实journal_uuid"],
                }
            ],
            "executive_brief_md": "600-1200字直白高密度董事长总结（Markdown，禁止暴露内部表名/代码术语）",
        },
        ensure_ascii=False,
        indent=2,
    )
    schema_hint = (
        "## 六、输出格式硬要求（所有键名与枚举值必须 100% 逐字匹配下方 JSON 模板，严禁自造键名）\n"
        "- **必须保持高密度精炼（总 JSON 严控在 6,000–9,000 字符内，防止超长截断）**：\n"
        "  * `inferred_tasks` 精炼提炼最核心的 10–12 项具体任务（每条 `summary` ≤ 80 字，`evidence_uuids` 给 1–2 条最具代表性的真实 UUID）；\n"
        "  * `missed_tasks` 提炼 5–7 项；`staffing_recommendations` 提炼 4–5 条；`ai_transformation_opportunities` 覆盖全部 4 类共 4–5 条；`goal_effort_breakdown` 完整覆盖 G1–G5 全部 5 项；\n"
        "  * `executive_brief_md` 控制在 400–700 字，**严禁在任何中文值内使用英文半角双引号 `\"`**（请一律用中文引号 `「」` 或 `“”`），并用 `\\n` 表示换行。\n"
        "- 严禁编造任何未在上文出现的 `journal_uuid` 或董事长 `#task_id`！\n"
        f"```json\n{schema_skeleton}\n```"
    )
    lines.append(schema_hint)
    return "\n".join(lines)


def _parse_llm_json_payload(raw_output: dict[str, Any] | str) -> dict[str, Any]:
    """Parse structured JSON returned by `llm_callable` (supports dict, raw JSON, or ```json``` fence)."""
    if isinstance(raw_output, dict):
        return raw_output
    text = str(raw_output or "").strip()
    if not text:
        raise ValueError("LLM returned empty output for AlignmentAuditReport")
    match = _JSON_FENCE_RE.search(text)
    candidate = match.group(1).strip() if match else text
    candidate = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", candidate)
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    try:
        parsed = json.loads(candidate, strict=False)
    except json.JSONDecodeError as exc:
        first_brace = candidate.find("{")
        last_brace = candidate.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            sliced = re.sub(r",\s*([}\]])", r"\1", candidate[first_brace : last_brace + 1])
            try:
                parsed = json.loads(sliced, strict=False)
            except json.JSONDecodeError as exc2:
                ctx_snip = sliced[max(0, exc2.pos - 80) : exc2.pos + 80].replace("\n", "\\n")
                raise ValueError(f"{exc2} | near: {ctx_snip!r}") from exc2
        else:
            ctx_snip = candidate[max(0, exc.pos - 80) : exc.pos + 80].replace("\n", "\\n")
            raise ValueError(f"{exc} | near: {ctx_snip!r}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object for AlignmentAuditReport, got {type(parsed).__name__}")
    return parsed


def run_alignment_audit(
    *,
    storage: CompanyOpsStorage,
    llm_callable: Callable[[str, str], dict[str, Any] | str],
    start_date: str,
    end_date: str,
    audit_kind: Literal["daily", "weekly", "baseline_30d"] = "baseline_30d",
    max_grounding_retries: int = 2,
) -> tuple[AlignmentAuditReport, int]:
    """Execute Model-First alignment audit with deterministic grounding verification & bounded retries."""
    reports = storage.list_reports(start_date=start_date, end_date=end_date)
    if not reports:
        raise ValueError(f"时间窗口 {start_date} ~ {end_date} 内没有任何企微汇报记录，无法执行对齐审计。")

    roadmap_goals = storage.list_roadmap_goals(active_only=True)
    chairman_open_tasks = storage.read_chairman_open_tasks()
    metrics = compute_deterministic_ops_metrics(reports)

    base_user_prompt = build_alignment_context(
        reports=reports,
        roadmap_goals=roadmap_goals,
        chairman_open_tasks=chairman_open_tasks,
        metrics=metrics,
        period_start=start_date,
        period_end=end_date,
        audit_kind=audit_kind,
    )

    valid_uuids = {r.journal_uuid for r in reports}
    valid_task_ids = {int(t["id"]) for t in chairman_open_tasks if t.get("id") is not None}

    max_attempts = 1 + max(0, int(max_grounding_retries))
    last_errors: list[str] = []
    current_user_prompt = base_user_prompt

    for attempt in range(1, max_attempts + 1):
        raw_resp = llm_callable(ALIGNMENT_ANALYST_SYSTEM_PROMPT, current_user_prompt)
        try:
            parsed_dict = _parse_llm_json_payload(raw_resp)
            report = AlignmentAuditReport.model_validate(parsed_dict)
        except Exception as exc:
            last_errors = [f"JSON/Schema 解析校验失败: {exc}"]
            logger.warning("Alignment audit attempt %d/%d schema failed: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                current_user_prompt = (
                    base_user_prompt
                    + "\n\n【客观硬校验打回（请严格修正后重新输出完整 JSON）】\n"
                    + "\n".join(f"- {e}" for e in last_errors)
                )
                continue
            break

        grounding_failures = validate_audit_grounding(
            report,
            valid_journal_uuids=valid_uuids,
            valid_chairman_task_ids=valid_task_ids,
        )
        if not grounding_failures:
            audit_id = storage.save_alignment_audit(report, reports_analyzed_count=len(reports))
            return report, audit_id

        last_errors = grounding_failures
        logger.warning(
            "Alignment audit attempt %d/%d grounding failed (%d errors): %s",
            attempt,
            max_attempts,
            len(grounding_failures),
            grounding_failures[:3],
        )
        if attempt < max_attempts:
            current_user_prompt = (
                base_user_prompt
                + "\n\n【客观溯源硬校验未通过（严禁编造任何 UUID 或任务 ID，请逐条修正后重新输出完整 JSON）】\n"
                + "\n".join(f"- {err}" for err in grounding_failures)
                + f"\n合法董事长在途 task_id 仅限：{sorted(valid_task_ids)}"
            )

    raise RuntimeError(
        f"对齐审计在 {max_attempts} 次尝试后仍未通过客观溯源硬校验，已熔断且未落盘脏数据："
        + "；".join(last_errors)
    )
