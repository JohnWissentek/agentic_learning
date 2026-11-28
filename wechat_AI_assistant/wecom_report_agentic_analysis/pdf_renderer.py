"""Deterministic 10-page Executive Dual-Track Alert PDF Renderer (Slice D).

Renders the verified V3.0 Dual-Track Audit Report + deterministic attendance/4-window metrics
into clean executive HTML with inline vector SVG charts (zero external plotting library required)
and compiles to A4 PDF via headless Chrome/Chromium with a deterministic pure-Python fallback.
"""

from __future__ import annotations

import html
import logging
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from wecom_report_agentic_analysis.schemas import (
    DEFAULT_COMPANY_ROSTER,
    AlertSeverity,
    AlertTrack,
    DualTrackAuditReport,
    ProductLine,
    WorkFunction,
)

logger = logging.getLogger(__name__)

_JARGON_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("ops_wecom_reports", "企微汇报归档库"),
    ("ops_alignment_audits", "经营审计归档库"),
    ("ops_sync_watermarks", "同步进度记录"),
    ("ops_company_roadmap", "战略路线图"),
    ("ops_delivery_locks", "发信防重记录"),
    ("list_items", "董事长在途任务清单"),
    ("journal_uuid", "汇报原始编号"),
    ("DualTrackAuditReport", "双轨经营诊断报告"),
    ("UNALIGNED", "未归属战略支柱（常规/杂务）"),
)

_CHROME_CANDIDATES: tuple[str, ...] = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
)


def _e(text: Any) -> str:
    raw = str(text if text is not None else "")
    for bad, good in _JARGON_REPLACEMENTS:
        raw = raw.replace(bad, good)
    return html.escape(raw, quote=True)


def _coerce_report(report: Any) -> DualTrackAuditReport:
    if isinstance(report, DualTrackAuditReport):
        return report
    return DualTrackAuditReport.model_validate(report)


def _normalize_attendance_rows(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    raw = metrics.get("staff_attendance")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        expected_cnt = int(metrics.get("expected_workday_count") or len(metrics.get("expected_workdays") or []) or 0)
        rows: list[dict[str, Any]] = []
        for name, info in raw.items():
            wf = info.get("work_function", "")
            wf_val = wf.value if hasattr(wf, "value") else str(wf)
            eff_days = int(info.get("valid_reported_workdays", 0))
            missed = info.get("missed_workdays") or []
            missed_cnt = len(missed) if isinstance(missed, list) else int(missed)
            rate = round(eff_days / expected_cnt * 100.0, 1) if expected_cnt > 0 else 100.0
            rows.append(
                {
                    "name": name,
                    "role_group": info.get("role_group", ""),
                    "work_function": wf_val,
                    "expected_workdays": expected_cnt,
                    "effective_report_days": eff_days,
                    "on_time_days": int(info.get("on_time_reports", eff_days)),
                    "late_backfill_count": int(info.get("late_backfill_reports", 0)),
                    "field_trip_days": int(info.get("field_support_days", 0)),
                    "unsubmitted_workdays": missed_cnt,
                    "total_reports": int(info.get("total_reports", 0)),
                    "submission_rate_pct": rate,
                    "zero_report_flag": int(info.get("total_reports", 0)) == 0,
                }
            )
        return rows
    # Fallback skeleton from roster
    return [
        {
            "name": p.name,
            "role_group": p.role_group,
            "work_function": p.work_function.value,
            "expected_workdays": 0,
            "effective_report_days": 0,
            "on_time_days": 0,
            "late_backfill_count": 0,
            "field_trip_days": 0,
            "unsubmitted_workdays": 0,
            "total_reports": 0,
            "submission_rate_pct": 0.0,
            "zero_report_flag": True,
        }
        for p in DEFAULT_COMPANY_ROSTER
    ]


def _render_goal_effort_svg(report: DualTrackAuditReport) -> str:
    """Pure inline vector SVG stacked horizontal bar chart for Track 2 Goal Effort Ledger."""
    items = report.goal_effort_ledger[:8]
    if not items:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="680" height="72" viewBox="0 0 680 72">'
            '<rect x="0" y="0" width="680" height="72" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>'
            '<text x="340" y="40" text-anchor="middle" font-size="13" fill="#64748b">暂无已量化目标投入明细</text>'
            "</svg>"
        )
    row_h = 34
    top_pad = 36
    height = top_pad + len(items) * row_h + 26
    bar_x = 220
    bar_max_w = 380
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="680" height="{height}" viewBox="0 0 680 {height}">',
        '<rect x="0" y="0" width="680" height="100%" rx="8" fill="#f8fafc" stroke="#e2e8f0"/>',
        '<text x="16" y="22" font-size="12" font-weight="bold" fill="#0f172a">各战略目标精力构成：有效战略推进（蓝） vs 存量维保/救火（红）</text>',
    ]
    for idx, g in enumerate(items):
        y = top_pad + idx * row_h
        label = (g.goal_title or g.goal_code)[:16]
        eff_pct = max(0.0, min(100.0, float(g.effective_strategic_share_pct)))
        ff_pct = max(0.0, min(100.0 - eff_pct, float(g.firefighting_or_maintenance_share_pct)))
        eff_w = round(bar_max_w * eff_pct / 100.0, 1)
        ff_w = round(bar_max_w * ff_pct / 100.0, 1)
        parts.append(f'<text x="16" y="{y + 16}" font-size="11" fill="#1e293b">{_e(label)}</text>')
        parts.append(f'<rect x="{bar_x}" y="{y + 4}" width="{bar_max_w}" height="16" rx="3" fill="#e2e8f0"/>')
        if eff_w > 0:
            parts.append(f'<rect x="{bar_x}" y="{y + 4}" width="{eff_w}" height="16" rx="3" fill="#2563eb"/>')
        if ff_w > 0:
            parts.append(f'<rect x="{bar_x + eff_w}" y="{y + 4}" width="{ff_w}" height="16" rx="2" fill="#dc2626"/>')
        parts.append(
            f'<text x="{bar_x + bar_max_w + 8}" y="{y + 16}" font-size="11" fill="#334155">'
            f'{eff_pct:.0f}%+{ff_pct:.0f}%</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _render_rd_focus_svg(strategic_pct: float, non_rd_pct: float, floor_pct: float = 75.0) -> str:
    """Inline vector SVG split bar for high-cost R&D focus vs 75% redline."""
    s_pct = max(0.0, min(100.0, float(strategic_pct)))
    n_pct = max(0.0, min(100.0 - s_pct, float(non_rd_pct)))
    bar_w = 560.0
    s_w = round(bar_w * s_pct / 100.0, 1)
    n_w = round(bar_w * n_pct / 100.0, 1)
    redline_x = round(40.0 + bar_w * (floor_pct / 100.0), 1)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="82" viewBox="0 0 640 82">'
        '<rect x="0" y="0" width="640" height="82" rx="8" fill="#fff7ed" stroke="#fed7aa"/>'
        '<text x="40" y="22" font-size="12" font-weight="bold" fill="#7c2d12">'
        f'高成本核心研发精力结构：战略核心研发 {s_pct:.1f}% vs 返厂/售后/杂务稀释 {n_pct:.1f}%（目标红线 ≥ {floor_pct:.0f}%）</text>'
        f'<rect x="40" y="34" width="{bar_w}" height="22" rx="4" fill="#e2e8f0"/>'
        f'<rect x="40" y="34" width="{s_w}" height="22" rx="4" fill="#16a34a"/>'
        f'<rect x="{40 + s_w}" y="34" width="{n_w}" height="22" rx="2" fill="#dc2626"/>'
        f'<line x1="{redline_x}" y1="28" x2="{redline_x}" y2="62" stroke="#0f172a" stroke-width="2" stroke-dasharray="4 3"/>'
        f'<text x="{redline_x}" y="74" text-anchor="middle" font-size="10" fill="#0f172a">{floor_pct:.0f}% 红线</text>'
        "</svg>"
    )


def build_executive_report_html(
    *,
    report: Any,
    metrics: dict[str, Any],
    short_ref_index: list[dict[str, Any]] | None = None,
    config_meta: dict[str, Any] | None = None,
) -> str:
    """Render the complete 10-section A4 executive dual-track alert report as standalone HTML+SVG."""
    rep = _coerce_report(report)
    meta = config_meta or {}
    company = str(meta.get("company_name") or "维恩科仪")
    eff_date = str(meta.get("new_template_effective_date") or metrics.get("effective_date") or "2026-11-28")

    crit_alerts = [a for a in rep.alerts if a.severity == AlertSeverity.CRITICAL]
    warn_alerts = [a for a in rep.alerts if a.severity == AlertSeverity.WARNING]
    opt_alerts = [a for a in rep.alerts if a.severity == AlertSeverity.OPTIMIZATION]

    rd_focus = (
        rep.high_cost_rd_audit.strategic_rd_share_pct
        if rep.high_cost_rd_audit is not None
        else float((metrics.get("high_cost_rd_metrics") or {}).get("strategic_rd_share_pct", 0.0))
    )
    rd_non = (
        rep.high_cost_rd_audit.support_or_non_rd_share_pct
        if rep.high_cost_rd_audit is not None
        else float((metrics.get("high_cost_rd_metrics") or {}).get("support_or_non_rd_share_pct", 0.0))
    )

    attendance_rows = _normalize_attendance_rows(metrics)
    leave_disclaimer = str(
        metrics.get("leave_disclaimer") or "未提交工作日（未扣除请假/倒休，需结合考勤与晨会核对）"
    )
    tier_cn_map = {"long_term": "长期目标", "annual": "年度目标", "quarterly": "季度目标", "monthly": "月度目标"}
    skipped_cn = "、".join(tier_cn_map.get(t, t) for t in rep.skipped_empty_goal_tiers)

    def _alert_card(a: Any) -> str:
        badge_cls = "crit" if a.severity == AlertSeverity.CRITICAL else ("warn" if a.severity == AlertSeverity.WARNING else "opt")
        icon = "🔴" if a.severity == AlertSeverity.CRITICAL else ("🟡" if a.severity == AlertSeverity.WARNING else "🔵")
        gray_tag = " 【存疑已标灰】" if a.verification_status == "degraded_unverified" else ""
        return (
            f'<div class="alert-card {badge_cls}">'
            f'<div class="alert-head">{icon} <strong>[{_e(a.track.value)}] {_e(a.title)}</strong>'
            f'<span class="tag">{_e(a.category)}{gray_tag}</span></div>'
            f'<div class="alert-body"><b>量化实据：</b>{_e(a.quant_data)}<br/>'
            f'<b>建议董事长拍板指令：</b>{_e(a.recommended_action)}</div>'
            "</div>"
        )

    strat_alerts_html = "".join(_alert_card(a) for a in rep.alerts if a.track == AlertTrack.STRATEGIC) or "<p>本周期战略轨暂无新增告警。</p>"
    qual_alerts_html = "".join(_alert_card(a) for a in rep.alerts if a.track == AlertTrack.QUALITY) or "<p>本周期质量轨暂无新增告警。</p>"

    # Template distribution
    tpl_counts = metrics.get("by_template") or metrics.get("template_counts") or {}
    tpl_rows_html = "".join(
        f"<tr><td>{_e(k)}</td><td>{int(v)}</td></tr>"
        for k, v in tpl_counts.items()
    )

    # 15-person attendance rows
    att_rows_html = "".join(
        "<tr>"
        f"<td><strong>{_e(r['name'])}</strong></td>"
        f"<td>{_e(r.get('role_group', ''))}</td>"
        f"<td>{int(r.get('total_reports', 0))}</td>"
        f"<td>{int(r.get('expected_workdays', 0))}</td>"
        f"<td>{int(r.get('effective_report_days', 0))}</td>"
        f"<td>{int(r.get('field_trip_days', 0))}</td>"
        f"<td>{int(r.get('late_backfill_count', 0))}</td>"
        f"<td>{int(r.get('unsubmitted_workdays', 0))}</td>"
        "</tr>"
        for r in attendance_rows
    )

    # Track 1 quality metrics + staff matrix
    tq = metrics.get("template_quality_metrics") or metrics.get("track1_quality_metrics") or {}
    staff_qual_html = "".join(
        "<tr>"
        f"<td><strong>{_e(s.staff_name)}</strong></td>"
        f"<td>{_e(s.role_group)}</td>"
        f"<td>{_e(s.sop_compliance)}</td>"
        f"<td>{_e(s.traceability_and_archiving)}</td>"
        f"<td>{_e(s.tangible_deliverables)}</td>"
        f"<td>{_e(s.value_closure)}</td>"
        f"<td>{'⚠️ 是' if s.hollow_report_flag else '否'}</td>"
        f"<td>{_e(s.benchmark_highlight or s.commentary)}</td>"
        "</tr>"
        for s in rep.staff_quality_matrix
    ) or "<tr><td colspan='8'>本期为旧模板过渡基线，新模板生效后自动生成全员四维灯号。</td></tr>"

    # Track 2 goal ledger table
    goal_rows_html = "".join(
        "<tr>"
        f"<td><strong>{_e(g.goal_title)}</strong></td>"
        f"<td>{g.contributor_count}人（{_e('、'.join(g.contributors))}）</td>"
        f"<td>{g.estimated_person_days:.1f} 人·天 / {g.total_effort_share_pct:.1f}%</td>"
        f"<td>有效 {g.effective_strategic_share_pct:.1f}% ｜ 维保救火 {g.firefighting_or_maintenance_share_pct:.1f}%</td>"
        f"<td>{_e('；'.join(g.observed_hard_deliverables) or '暂无明确硬产出')}</td>"
        f"<td>{_e(g.trajectory_verdict.value)}</td>"
        "</tr>"
        for g in rep.goal_effort_ledger
    )

    # Four horizon trends summary
    horizons_raw = metrics.get("four_horizon_trends")
    if isinstance(horizons_raw, list):
        horizon_rows_html = "".join(
            f"<tr><td>{_e(h.get('horizon', ''))}</td><td>{int(h.get('total_reports', 0))}</td>"
            f"<td>{h.get('rd_focus_pct', '-')} %</td><td>{h.get('firefighting_pct', '-')} %</td></tr>"
            for h in horizons_raw
        )
    else:
        rtm = metrics.get("rolling_trend_matrix") or {}
        h_labels = {
            "rolling_1m": "近 1 个月",
            "rolling_1q": "近 1 个季度",
            "rolling_1y": "近 1 年",
            "long_term_all": "全量长期",
        }
        horizon_rows_html = "".join(
            f"<tr><td>{lbl}</td><td>{int((rtm.get(k) or {}).get('total_reports', 0))}</td>"
            f"<td>{int((rtm.get(k) or {}).get('active_staff_count', 0))} 人</td>"
            f"<td>现场 {int((rtm.get(k) or {}).get('field_reports_count', 0))} / 研发测试 {int((rtm.get(k) or {}).get('rd_test_repair_count', 0))}</td></tr>"
            for k, lbl in h_labels.items()
        )

    # 8x7 matrix counts from inferred_tasks
    pl_fn_counter: Counter[tuple[str, str]] = Counter()
    for t in rep.inferred_tasks:
        pl_fn_counter[(t.product_line.value, t.work_function.value)] += 1
    matrix_rows_html = "".join(
        "<tr>"
        f"<td><strong>{_e(pl.value)}</strong></td>"
        + "".join(f"<td>{pl_fn_counter.get((pl.value, fn.value), 0) or '·'}</td>" for fn in WorkFunction)
        + "</tr>"
        for pl in ProductLine
    )

    tasks_rows_html = "".join(
        "<tr>"
        f"<td><strong>{_e(t.task_name)}</strong></td>"
        f"<td>{_e(t.product_line.value)}</td>"
        f"<td>{_e(t.work_function.value)}</td>"
        f"<td>{_e('、'.join(tag.value for tag in t.transformation_tags) or '常规')}</td>"
        f"<td>{_e(t.aligned_goal_code)}</td>"
        f"<td>{t.span_days} 天</td>"
        f"<td>{_e('、'.join(t.participants))}</td>"
        f"<td>{_e(t.status)}</td>"
        f"<td>{_e(t.summary)}</td>"
        "</tr>"
        for t in rep.inferred_tasks
    )

    # Chairman bidirectional radar
    overlap_html = "".join(
        f"<tr><td>#{ov.task_id} {_e(ov.task_title)}</td><td>{_e(ov.overlap_status)}</td>"
        f"<td>{_e('、'.join(ov.matched_staff))}</td><td>{_e(ov.latest_ground_progress)}</td></tr>"
        for ov in rep.chairman_overlap_tasks
    ) or "<tr><td colspan='4'>暂无重叠推进项记录。</td></tr>"
    missed_html = "".join(
        f"<tr><td>{_e(m.suggested_title)}</td><td>{_e(m.work_domain)}</td><td>{_e(m.priority)}</td>"
        f"<td>{_e('、'.join(m.involved_staff))}</td><td>{_e(m.reason)}</td></tr>"
        for m in rep.missed_tasks
    ) or "<tr><td colspan='5'>本期未发现显著盲区遗漏项。</td></tr>"
    stalled_html = "".join(
        f"<tr><td>#{s.task_id} {_e(s.task_title)}</td><td>{s.days_without_report_mention} 天</td><td>{_e(s.diagnostic_note)}</td></tr>"
        for s in rep.stalled_chairman_tasks
    ) or "<tr><td colspan='3'>暂无挂单空转预警。</td></tr>"

    # Staffing & AI opportunities
    staffing_html = "".join(
        f"<tr><td>{_e(r.scope)}</td><td>{_e(r.target_people_or_team)}</td>"
        f"<td>{_e(r.observation)}</td><td>{_e(r.recommendation)}</td></tr>"
        for r in rep.staffing_recommendations
    ) or "<tr><td colspan='4'>暂无新增人员调整建议。</td></tr>"
    ai_html = "".join(
        f"<tr><td>{_e(a.category)}</td><td>{_e(a.target_workflow)}</td><td>{_e('、'.join(a.affected_roles))}</td>"
        f"<td>{_e(a.current_pain_point)}</td><td>{_e(a.ai_solution_and_harness)}</td>"
        f"<td>{_e(a.efficiency_or_replacement_impact)}</td><td>{_e(a.priority)}</td></tr>"
        for a in rep.ai_transformation_opportunities
    ) or "<tr><td colspan='7'>暂无新增 AI 提效机会项。</td></tr>"

    # Appendix traceability table (short refs only, never raw UUIDs)
    refs_list = short_ref_index or []
    ref_rows_html = "".join(
        "<tr>"
        f"<td><strong>{_e(item.get('ref') or item.get('short_ref') or '')}</strong></td>"
        f"<td>{_e(item.get('work_date') or item.get('report_date') or '')}</td>"
        f"<td>{_e(item.get('submitter_name') or '')}</td>"
        f"<td>{_e(item.get('template_name') or '')}</td>"
        f"<td>{_e(item.get('summary') or item.get('excerpt') or '')}</td>"
        "</tr>"
        for item in refs_list[:60]
    ) or "<tr><td colspan='5'>本期无引证索引明细。</td></tr>"

    degraded_html = (
        '<div class="notice"><strong>系统降级核验说明：</strong><ul>'
        + "".join(f"<li>{_e(n)}</li>" for n in rep.degraded_notes)
        + "</ul></div>"
        if rep.degraded_notes
        else ""
    )

    lt_summary_html = "".join(f"<li>{_e(line)}</li>" for line in rep.long_term_transformation_summary) or "<li>本期暂无长期转型专项变动记录。</li>"

    rd = rep.high_cost_rd_audit
    rd_section_html = (
        f"<p><b>综合定性：</b>{_e(rd.alignment_verdict)} ｜ <b>周期汇报：</b>{rd.total_reports_in_period} 份 ｜ "
        f"<b>涉及产品线：</b>{_e('、'.join(rd.main_product_lines) or '无')}</p>"
        f"<p><b>已观测硬交付物：</b>{_e('；'.join(rd.observed_deliverables) or '暂无')}</p>"
        f"<p><b>稀释源头风险：</b>{_e('；'.join(rd.drift_or_dilution_risks) or '无显著稀释')}</p>"
        f"<p><b>下周隔离与排期硬建议：</b>{_e(rd.reallocation_advice)}</p>"
        if rd is not None
        else "<p>本周期暂无高成本核心研发专项记录。</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{_e(company)}经营漏洞预警与战略诊断周报（{_e(rep.period_start)} ~ {_e(rep.period_end)}）</title>
<style>
  @page {{ size: A4; margin: 14mm 14mm; }}
  body {{ font-family: "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif; color: #0f172a; font-size: 11px; line-height: 1.55; margin: 0; padding: 18px; }}
  h1 {{ font-size: 20px; color: #0f172a; border-bottom: 2.5px solid #1e3a8a; padding-bottom: 8px; margin-bottom: 8px; }}
  h2 {{ font-size: 14px; color: #1e3a8a; border-left: 4px solid #2563eb; padding-left: 8px; margin-top: 18px; margin-bottom: 8px; }}
  h3 {{ font-size: 12px; color: #334155; margin-top: 10px; margin-bottom: 6px; }}
  .meta {{ color: #475569; font-size: 10.5px; margin-bottom: 12px; }}
  .kpi-grid {{ display: flex; gap: 8px; margin: 10px 0 14px 0; }}
  .kpi {{ flex: 1; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 10px; text-align: center; }}
  .kpi .num {{ font-size: 17px; font-weight: bold; color: #0f172a; }}
  .kpi.crit .num {{ color: #dc2626; }}
  .kpi.warn .num {{ color: #d97706; }}
  .kpi.opt .num {{ color: #2563eb; }}
  .alert-card {{ border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; border-left: 4px solid #64748b; background: #f8fafc; }}
  .alert-card.crit {{ border-left-color: #dc2626; background: #fef2f2; }}
  .alert-card.warn {{ border-left-color: #d97706; background: #fffbeb; }}
  .alert-card.opt {{ border-left-color: #2563eb; background: #eff6ff; }}
  .alert-head {{ margin-bottom: 4px; }}
  .tag {{ display: inline-block; margin-left: 8px; font-size: 9.5px; background: #e2e8f0; color: #334155; border-radius: 4px; padding: 1px 6px; }}
  .notice {{ background: #f1f5f9; border: 1px dashed #94a3b8; border-radius: 6px; padding: 8px 10px; margin: 8px 0; color: #334155; font-size: 10.5px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 12px 0; font-size: 10px; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 5px 6px; text-align: left; vertical-align: top; }}
  th {{ background: #eff6ff; color: #1e3a8a; font-weight: bold; }}
  .page-break {{ page-break-before: always; }}
</style>
</head>
<body>
  <!-- 第 1 页：封面页眉 + 双轨 Alert 告警台与董事长决断清单 -->
  <section class="page">
    <h1>{_e(company)}「双轨制」经营漏洞预警与战略诊断周报</h1>
    <div class="meta">分析周期：{_e(rep.period_start)} 至 {_e(rep.period_end)} ｜ 综合战略对齐评分：<strong>{rep.alignment_score:.1f} / 100</strong> ｜ 新模板生效基准日：{_e(eff_date)}（仅供董事长私密审阅）</div>
    <div class="kpi-grid">
      <div class="kpi crit"><div class="num">🔴 {len(crit_alerts)}</div><div>高危漏洞告警</div></div>
      <div class="kpi warn"><div class="num">🟡 {len(warn_alerts)}</div><div>风险偏离提醒</div></div>
      <div class="kpi opt"><div class="num">🔵 {len(opt_alerts)}</div><div>AI 与提效提示</div></div>
      <div class="kpi"><div class="num">{rep.overall_hard_deliverable_pass_rate_pct:.1f}%</div><div>轨一：汇报硬成果达标率</div></div>
      <div class="kpi"><div class="num">{rd_focus:.1f}%</div><div>轨二：李文颖研发专注度</div></div>
    </div>
    <div class="notice"><strong>董事长执行摘要：</strong>{_e(rep.executive_brief_md)}</div>
    <h2>置顶双轨 Alert 告警台与董事长决断清单</h2>
    <h3>【战略轨】漏洞告警与拍板指令</h3>
    {strat_alerts_html}
    <h3>【质量轨】汇报质量与 SOP 留痕预警</h3>
    {qual_alerts_html}
    {degraded_html}
  </section>

  <!-- 第 2 页：一、全员 15 人精确出勤、提交率与出差硬统计 -->
  <section class="page page-break">
    <h2>一、全员 15 人精确出勤、提交率与出差硬统计（100% 确定性底盘核算）</h2>
    <div class="notice">考勤口径说明：已自动剔除周末与中国法定节假日（含调休补班日）；次日上午 12:00 前补交计按时；驻场每日报告/结项综合报告/财务保密简报自动计入当日有效汇报。<strong>{_e(leave_disclaimer)}</strong>。</div>
    <h3>1.1 全公司 7 类汇报模板提交分布</h3>
    <table><thead><tr><th>汇报模板</th><th>本周期提交份数</th></tr></thead><tbody>{tpl_rows_html}</tbody></table>
    <h3>1.2 全员 15 人出勤、出差与未提交工作日明细</h3>
    <table>
      <thead><tr><th>姓名</th><th>岗位角色</th><th>总汇报</th><th>应出勤日</th><th>有效汇报日</th><th>出差现场天</th><th>延迟补交</th><th>未提交工作日（未扣除请假/倒休）</th></tr></thead>
      <tbody>{att_rows_html}</tbody>
    </table>
  </section>

  <!-- 第 3 页：二、【轨道一】现代项目管理与汇报质量评估 -->
  <section class="page page-break">
    <h2>二、【轨道一】现代项目管理与汇报质量评估（SOP × 留痕 × 硬成果 × 收益）</h2>
    <div class="notice">新旧模板时代分界：{_e(eff_date)} 之前的老模板历史汇报共 {int(tq.get('legacy_v1_exempt_count', tq.get('legacy_exempt_reports_count', 0)))} 份，仅作基线参考免于新字段苛责；新模板生效后汇报共 {int(tq.get('upgraded_v2_count', tq.get('upgraded_reports_count', 0)))} 份。同日研发测试引用简写及合规在途报备均自动豁免不计空心水文。</div>
    <h3>2.1 全员汇报质量四维红黄绿灯与标杆/纠偏清单</h3>
    <table>
      <thead><tr><th>姓名</th><th>岗位</th><th>SOP 遵循</th><th>沟通与文档存档</th><th>硬成果与沉淀</th><th>价值闭环</th><th>空心流水账</th><th>标杆亮点 / 纠偏评语</th></tr></thead>
      <tbody>{staff_qual_html}</tbody>
    </table>
  </section>

  <!-- 第 4 页：三、【轨道二】各目标「时间、精力与产出」量化总账 × 四期演进 -->
  <section class="page page-break">
    <h2>三、【轨道二】各目标「时间、精力与产出」量化总账 × 四期演进</h2>
    <div class="notice">已激活目标层：{_e('、'.join(tier_cn_map.get(t, t) for t in rep.active_goal_tiers))}。{f'以下目标层级暂未设定（{skipped_cn}），后续在战略配置文件补充后自动启用对比，本次绝不编造。' if skipped_cn else ''}</div>
    {_render_goal_effort_svg(rep)}
    <h3>3.1 已配置战略目标投入与硬产出总账</h3>
    <table>
      <thead><tr><th>战略目标</th><th>投入人数与名单</th><th>投入人·天 / 占比</th><th>有效推进 vs 维保救火拆分</th><th>已观测硬交付物</th><th>四期演进判定</th></tr></thead>
      <tbody>{goal_rows_html}</tbody>
    </table>
    <p><strong>未归属任何战略目标的杂务/内耗黑洞池：</strong>约 {rep.unaligned_overhead_person_days:.1f} 人·天（占全公司精力 {rep.unaligned_overhead_pool_pct:.1f}%）。</p>
    <h3>3.2 四期滚动演进对比（近 1 月 / 近 1 季 / 近 1 年 / 全量长期）</h3>
    <table><thead><tr><th>滚动周期</th><th>涵盖汇报篇数</th><th>活跃人数 / 研发专注度</th><th>结构对比</th></tr></thead><tbody>{horizon_rows_html}</tbody></table>
  </section>

  <!-- 第 5 页：四、【轨道二】长期终局转型专项雷达 -->
  <section class="page page-break">
    <h2>四、【轨道二】长期终局转型专项雷达（国产化 / 轻资产制造 / 渠道赋能 / 出海）</h2>
    <ul>{lt_summary_html}</ul>
  </section>

  <!-- 第 6 页：五、【轨道二】高成本核心研发专项穿透审计（李文颖） -->
  <section class="page page-break">
    <h2>五、【轨道二】高成本核心研发专项穿透审计（李文颖）</h2>
    {_render_rd_focus_svg(rd_focus, rd_non, 75.0)}
    {rd_section_html}
  </section>

  <!-- 第 7 页：六、【轨道二】8×7 业务投入矩阵与核心还原任务 -->
  <section class="page page-break">
    <h2>六、【轨道二】8×7 业务投入矩阵与核心还原任务总表</h2>
    <h3>6.1 产品线 × 7 大职能投入分布矩阵</h3>
    <table>
      <thead><tr><th>产品线 \\ 职能</th>{''.join(f'<th>{_e(fn.value)}</th>' for fn in WorkFunction)}</tr></thead>
      <tbody>{matrix_rows_html}</tbody>
    </table>
    <h3>6.2 Top 核心还原任务明细</h3>
    <table>
      <thead><tr><th>任务名称</th><th>产品线</th><th>职能</th><th>转型标签</th><th>归属目标</th><th>跨度</th><th>参与人</th><th>状态</th><th>关键进展</th></tr></thead>
      <tbody>{tasks_rows_html}</tbody>
    </table>
  </section>

  <!-- 第 8 页：七、【轨道二】董事长重点任务双向对齐雷达 -->
  <section class="page page-break">
    <h2>七、【轨道二】董事长重点任务双向对齐雷达</h2>
    <h3>7.1 高度对齐推进项</h3>
    <table><thead><tr><th>董事长任务</th><th>对齐状态</th><th>关联一线人员</th><th>一线最新进展</th></tr></thead><tbody>{overlap_html}</tbody></table>
    <h3>7.2 董事长盲区雷达（建议纳管的高风险/高耗能事项）</h3>
    <table><thead><tr><th>建议纳管任务</th><th>业务域</th><th>优先级</th><th>涉及人员</th><th>遗漏原因与风险</th></tr></thead><tbody>{missed_html}</tbody></table>
    <h3>7.3 挂单空转预警（在途任务连续多日零提及）</h3>
    <table><thead><tr><th>董事长任务</th><th>无提及天数</th><th>停滞诊断说明</th></tr></thead><tbody>{stalled_html}</tbody></table>
  </section>

  <!-- 第 9 页：八、人员配置调优与 AI 提效 / 岗位替代行动清单 -->
  <section class="page page-break">
    <h2>八、人员配置调优与 AI 提效 / 岗位替代行动清单</h2>
    <h3>8.1 人员负荷分流与岗位配置调优（严守 ≤20 人精干红线）</h3>
    <table><thead><tr><th>维度</th><th>目标人员/团队</th><th>客观观测</th><th>可执行调整建议</th></tr></thead><tbody>{staffing_html}</tbody></table>
    <h3>8.2 AI 提效、质量门禁与低效岗位替代（4 维度）</h3>
    <table><thead><tr><th>类别</th><th>目标工作流</th><th>涉及岗位</th><th>现状痛点</th><th>AI 与门禁方案</th><th>预期收益/释放空间</th><th>优先级</th></tr></thead><tbody>{ai_html}</tbody></table>
  </section>

  <!-- 第 10 页（附录）：双轨全量 Alert 索引、汇报短号溯源表与系统核验说明 -->
  <section class="page page-break">
    <h2>附录：双轨全量 Alert 索引、汇报短号溯源表与系统核验说明</h2>
    <p>本次审计依据确定性底盘核验了全部引证短编号与董事长在途任务编号；财务保密模板数据严格隔离于董事长私密审计链路内。</p>
    <table>
      <thead><tr><th>溯源短号</th><th>工作日</th><th>提交人</th><th>汇报模板</th><th>关键摘要</th></tr></thead>
      <tbody>{ref_rows_html}</tbody>
    </table>
  </section>
</body>
</html>"""


def _find_headless_chrome() -> str | None:
    for cand in _CHROME_CANDIDATES:
        p = Path(cand)
        if p.is_absolute():
            if p.exists():
                return str(p)
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


def _write_fallback_valid_pdf(output_pdf: Path, *, title: str, summary_lines: list[str]) -> None:
    """Pure-Python deterministic valid PDF-1.4 writer used when no headless Chrome is present."""
    safe_lines = [re.sub(r"[^\x20-\x7e]", " ", ln).strip() for ln in [title, *summary_lines]]
    safe_lines = [ln for ln in safe_lines if ln][:40] or ["Wissentek Dual-Track Weekly Executive Report"]

    def _pdf_esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream_cmds = ["BT", "/F1 11 Tf", "48 780 Td", "15 TL"]
    for idx, ln in enumerate(safe_lines):
        prefix = "" if idx == 0 else "T* "
        stream_cmds.append(f"{prefix}({_pdf_esc(ln[:90])}) Tj")
    stream_cmds.append("ET")
    stream_bytes = ("\n".join(stream_cmds) + "\n").encode("latin-1", errors="ignore")
    # Pad comment safely so PDF meets structural completeness & readability
    stream_bytes += b"% Wissentek Executive Dual-Track Report PDF Fallback\n" * 8

    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"5 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii") + stream_bytes + b"endstream\nendobj\n",
    ]
    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = [0]
    for obj in objects:
        offsets.append(len(buf))
        buf.extend(obj)
    xref_pos = len(buf)
    buf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    buf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    buf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    output_pdf.write_bytes(bytes(buf))


def render_executive_pdf(
    *,
    report: Any,
    metrics: dict[str, Any],
    output_pdf_path: str | Path,
    short_ref_index: list[dict[str, Any]] | None = None,
    config_meta: dict[str, Any] | None = None,
    also_save_html: bool = False,
) -> dict[str, Any]:
    """Render and save A4 PDF report to `output_pdf_path`; return rendering metadata."""
    rep = _coerce_report(report)
    pdf_path = Path(output_pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    html_doc = build_executive_report_html(
        report=rep,
        metrics=metrics,
        short_ref_index=short_ref_index,
        config_meta=config_meta,
    )
    html_saved_path = ""
    if also_save_html:
        html_out = pdf_path.with_suffix(".html")
        html_out.write_text(html_doc, encoding="utf-8")
        html_saved_path = str(html_out)

    renderer_used = "fallback_pdf14"
    chrome_bin = _find_headless_chrome()
    if chrome_bin:
        with tempfile.TemporaryDirectory() as td:
            tmp_html = Path(td) / "report.html"
            tmp_html.write_text(html_doc, encoding="utf-8")
            try:
                proc = subprocess.run(
                    [
                        chrome_bin,
                        "--headless=new",
                        "--disable-gpu",
                        "--no-sandbox",
                        "--print-to-pdf-no-header",
                        f"--print-to-pdf={pdf_path.resolve()}",
                        tmp_html.resolve().as_uri(),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=35,
                )
                if proc.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 500:
                    renderer_used = "headless_chrome"
            except (subprocess.SubprocessError, OSError) as exc:
                logger.warning("Headless Chrome PDF render failed (%s); falling back to pure-Python PDF", exc)

    if renderer_used != "headless_chrome":
        _write_fallback_valid_pdf(
            pdf_path,
            title=f"Wissentek Dual-Track Weekly Alert Report ({rep.period_start} to {rep.period_end})",
            summary_lines=[
                f"Alignment Score: {rep.alignment_score:.1f}/100 | Hard Deliverable Pass Rate: {rep.overall_hard_deliverable_pass_rate_pct:.1f}%",
                f"Alerts: {len(rep.alerts)} total",
                f"Active Tiers: {', '.join(rep.active_goal_tiers)}",
            ],
        )

    return {
        "pdf_path": str(pdf_path),
        "html_path": html_saved_path,
        "renderer": renderer_used,
        "size_bytes": pdf_path.stat().st_size,
    }
