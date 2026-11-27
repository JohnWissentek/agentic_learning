"""CLI runner for Slice 1: seed G1-G5 roadmap & execute live alignment audit via Bailian flagship LLM."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from wecom_report_agentic_analysis.alignment_analyzer import (
    compute_deterministic_ops_metrics,
    run_alignment_audit,
    seed_default_roadmap,
)
from wecom_report_agentic_analysis.schemas import AlignmentAuditReport
from wecom_report_agentic_analysis.storage import CompanyOpsStorage

_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _make_bailian_llm_callable() -> tuple[Any, dict[str, str]]:
    api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    base_url = (
        os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ).strip()
    primary_model = (os.getenv("OPS_AUDIT_MODEL") or os.getenv("PRODUCER_MODEL") or "qwen-max").strip()
    fallback_model = (os.getenv("PRODUCER_FALLBACK_MODEL") or "qwen-max").strip()
    if not api_key:
        raise RuntimeError("Missing DASHSCOPE_API_KEY in environment.")

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180.0)
    state = {"model_used": primary_model}

    def _call_one(model_name: str, system_prompt: str, user_prompt: str) -> str:
        t0 = time.time()
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 12000,
            "response_format": {"type": "json_object"},
            "stream": True,
        }
        if any(k in model_name.lower() for k in ("qwen3", "deepseek")):
            kwargs["extra_body"] = {"enable_thinking": False}
        chunks: list[str] = []
        stream = client.chat.completions.create(**kwargs)
        for ev in stream:
            if not ev.choices:
                continue
            delta = ev.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                chunks.append(piece)
        out = "".join(chunks).strip()
        debug_path = Path("/opt/wechat-agent/tmp_cache/last_raw_llm.txt")
        if debug_path.parent.exists():
            try:
                debug_path.write_text(out, encoding="utf-8")
            except OSError:
                pass
        print(
            f"[analyze_cli] model={model_name} ok in {time.time() - t0:.1f}s ({len(out)} chars)",
            file=sys.stderr,
            flush=True,
        )
        return out

    def _call(system_prompt: str, user_prompt: str) -> str:
        candidates = [primary_model]
        if fallback_model and fallback_model not in candidates:
            candidates.append(fallback_model)
        last_exc: Exception | None = None
        for m in candidates:
            try:
                res = _call_one(m, system_prompt, user_prompt)
                state["model_used"] = m
                return res
            except Exception as exc:
                last_exc = exc
                print(
                    f"[analyze_cli] model={m} failed ({type(exc).__name__}: {exc}); trying fallback...",
                    file=sys.stderr,
                    flush=True,
                )
        raise RuntimeError(f"All Bailian models failed: {last_exc}") from last_exc

    return _call, state


def render_baseline_markdown(
    report: AlignmentAuditReport,
    *,
    metrics: dict[str, Any],
    model_used: str,
    audit_id: int,
) -> str:
    """Render a crisp, executive-ready Markdown report combining deterministic stats & LLM audit."""
    lines: list[str] = [
        f"# 维恩科仪全员企微汇报经营对齐、高成本研发审计与 AI 提效基线诊断报告",
        "",
        f"> **审计编号**：`#{audit_id}` ｜ **周期**：`{report.period_start}` 至 `{report.period_end}` ｜ "
        f"**覆盖真实汇报**：`{metrics['total_reports']}` 份（5 类全模板）｜ **战略对齐综合评分**：**`{report.alignment_score:.1f} / 100`** ｜ "
        f"**推理引擎**：`{model_used}`（100% `journal_uuid` 与 `#task_id` 客观硬校验通过）",
        "",
        "---",
        "",
        "## 一、 董事长执行摘要",
        "",
        report.executive_brief_md.strip(),
        "",
        "---",
        "",
        "## 二、 客观硬统计基线（Python 确定性核算，零估算）",
        "",
        "### 2.1 按汇报模板分布",
        "| 汇报模板 | 份数 | 占比 |",
        "| :--- | :---: | :---: |",
    ]
    total = max(1, int(metrics["total_reports"]))
    for tpl, cnt in sorted(metrics["by_template"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {tpl} | {cnt} | {cnt / total:.1%} |")

    lines.extend(
        [
            "",
            "### 2.2 全员 15 人岗位负荷与出差频次明细",
            "| 姓名 | 岗位角色 | 总汇报数 | 10分钟日报 | 现场出差天数（去重） | 现场后补 | 研发测试/返厂 | 晨会 |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
    )
    for name, info in metrics["by_staff"].items():
        lines.append(
            f"| {name} | {info['role_group']} | {info['total_reports']} | "
            f"{info['daily_10min_reports']} | {info['field_support_days']} 天 | "
            f"{info['backfill_reports']} | {info['rd_test_repair_reports']} | {info['morning_brief_reports']} |"
        )
    silent = metrics.get("silent_roster_members") or []
    lines.append(f"\n- **本周期零汇报人员**：{'、'.join(silent) if silent else '无（全员均有提交）'}")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 三、 公司 5 大战略目标（G1–G5）精力对齐度拆解",
            "",
            "| 目标编号 | 战略目标 | 预期占比 | 估算实际占比 | 对齐状态 | 核心诊断 |",
            "| :--- | :--- | :---: | :---: | :---: | :--- |",
        ]
    )
    status_cn = {
        "aligned": "✅ 对齐",
        "under_invested": "⚠️ 投入不足",
        "over_invested": "🔵 投入偏高",
        "drifting": "🔴 明显偏离",
    }
    for g in report.goal_effort_breakdown:
        lines.append(
            f"| `{g.goal_code}` | {g.goal_title} | {g.target_effort_share_pct:.0f}% | "
            f"{g.estimated_actual_share_pct:.0f}% | {status_cn.get(g.alignment_status, g.alignment_status)} | "
            f"{g.commentary} |"
        )

    if report.high_cost_rd_audit is not None:
        rd = report.high_cost_rd_audit
        lines.extend(
            [
                "",
                "---",
                "",
                f"## 四、 G5 专项穿透审计：高成本专职电路板/研发人员（{rd.engineer_name}）",
                "",
                f"- **综合定性**：**{rd.alignment_verdict}**",
                f"- **周期内汇报总数**：`{rd.total_reports_in_period}` 份",
                f"- **战略研发精力估算占比**：**`{rd.strategic_rd_share_pct:.1f}%`** ｜ **技术支持/返厂/非核心研发稀释占比**：**`{rd.support_or_non_rd_share_pct:.1f}%`**",
                f"- **主要涉及产品线**：{'、'.join(rd.main_product_lines) or '无'}",
                "- **已观测到的硬交付物**：",
                *[f"  - {d}" for d in (rd.observed_deliverables or ["（本周期汇报中未观测到明确硬交付物）"])],
                "- **精力稀释 / 偏离风险**：",
                *[f"  - {r}" for r in (rd.drift_or_dilution_risks or ["无显著偏离"])],
                f"- **董事长调配纠偏建议**：{rd.reallocation_advice}",
            ]
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 五、 碎片汇报还原出的核心具体任务（按产品线 × 职能 × 跨度）",
            "",
            "| 任务名称 | 产品线 | 职能 | 归属目标 | 跨度 | 参与人 | 提及次数 | 状态 | 核心进展摘要 |",
            "| :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :--- |",
        ]
    )
    for t in report.inferred_tasks:
        lines.append(
            f"| {t.task_name} | {t.product_line.value} | {t.work_function.value} | `{t.aligned_goal_code}` | "
            f"{t.span_days}天（{t.first_seen_date[5:]}→{t.last_seen_date[5:]}） | {'、'.join(t.participants)} | "
            f"{t.report_mentions} | {t.status} | {t.summary} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 六、 与董事长 AI 助理（list_items）双向比对雷达",
            "",
            "### 6.1 重叠与对齐推进项",
            "| 董事长任务 | 对齐状态 | 关联一线人员 | 一线最新真实进展 |",
            "| :--- | :---: | :--- | :--- |",
        ]
    )
    for ov in report.chairman_overlap_tasks:
        lines.append(
            f"| `#{ov.task_id}` {ov.task_title} | {ov.overlap_status} | {'、'.join(ov.matched_staff)} | {ov.latest_ground_progress} |"
        )

    lines.extend(
        [
            "",
            "### 6.2 董事长盲区雷达（一线在推进/冒风险，但 AI 助理遗漏的事项）",
            "| 建议纳管任务名称 | 业务域 | 建议优先级 | 涉及人员 | 遗漏原因与风险 |",
            "| :--- | :---: | :---: | :--- | :--- |",
        ]
    )
    for m in report.missed_tasks:
        lines.append(
            f"| {m.suggested_title} | {m.work_domain} | {m.priority} | {'、'.join(m.involved_staff)} | {m.reason} |"
        )

    lines.extend(
        [
            "",
            "### 6.3 挂单空转预警（董事长在途任务，但团队近期汇报未提及）",
            "| 董事长任务 | 无提及天数 | 诊断说明 |",
            "| :--- | :---: | :--- |",
        ]
    )
    for s in report.stalled_chairman_tasks:
        lines.append(f"| `#{s.task_id}` {s.task_title} | {s.days_without_report_mention} 天 | {s.diagnostic_note} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 七、 全公司人员配置与工作安排调整建议",
            "",
            "| 维度 | 目标人员/团队 | 客观观测 | 调整建议 |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )
    for rec in report.staffing_recommendations:
        lines.append(f"| {rec.scope} | {rec.target_people_or_team} | {rec.observation} | {rec.recommendation} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 八、 AI 工作流提效、质量合规管控与低效岗位替代机会清单",
            "",
            "| 类别 | 目标工作流 | 涉及岗位 | 现状痛点 | AI 工作流 + Harness 方案 | 提效/替代预期 | 优先级 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :---: |",
        ]
    )
    for ai in report.ai_transformation_opportunities:
        lines.append(
            f"| {ai.category} | {ai.target_workflow} | {'、'.join(ai.affected_roles)} | "
            f"{ai.current_pain_point} | {ai.ai_solution_and_harness} | {ai.efficiency_or_replacement_impact} | {ai.priority} |"
        )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed G1-G5 roadmap and run flagship alignment audit.")
    parser.add_argument("--db-path", default="/opt/wechat-agent/data/app.db")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    parser.add_argument("--audit-kind", default="baseline_30d", choices=["daily", "weekly", "baseline_30d"])
    parser.add_argument("--output-md", default="", help="Optional path to write rendered Markdown report")
    parser.add_argument("--output-json", default="", help="Optional path to write structured JSON report")
    args = parser.parse_args(argv)

    today = datetime.now(_TZ_SHANGHAI).date()
    end_date = args.end_date.strip() or today.isoformat()
    start_date = args.start_date.strip() or (today - timedelta(days=max(1, args.days) - 1)).isoformat()

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    storage = CompanyOpsStorage(Path(args.db_path))
    seeded = seed_default_roadmap(storage)
    reports = storage.list_reports(start_date=start_date, end_date=end_date)
    metrics = compute_deterministic_ops_metrics(reports)

    llm_callable, llm_state = _make_bailian_llm_callable()
    report, audit_id = run_alignment_audit(
        storage=storage,
        llm_callable=llm_callable,
        start_date=start_date,
        end_date=end_date,
        audit_kind=args.audit_kind,
        max_grounding_retries=2,
    )
    model_used = llm_state["model_used"]

    md_text = render_baseline_markdown(report, metrics=metrics, model_used=model_used, audit_id=audit_id)
    if args.output_md:
        out_md = Path(args.output_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(md_text, encoding="utf-8")
    if args.output_json:
        out_js = Path(args.output_json)
        out_js.parent.mkdir(parents=True, exist_ok=True)
        out_js.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "audit_id": audit_id,
                "roadmap_goals_seeded": seeded,
                "model_used": model_used,
                "reports_analyzed": len(reports),
                "alignment_score": report.alignment_score,
                "inferred_tasks_count": len(report.inferred_tasks),
                "chairman_overlap_count": len(report.chairman_overlap_tasks),
                "missed_tasks_count": len(report.missed_tasks),
                "stalled_tasks_count": len(report.stalled_chairman_tasks),
                "high_cost_rd_verdict": report.high_cost_rd_audit.alignment_verdict if report.high_cost_rd_audit else None,
                "ai_opportunities_count": len(report.ai_transformation_opportunities),
                "output_md": args.output_md,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
