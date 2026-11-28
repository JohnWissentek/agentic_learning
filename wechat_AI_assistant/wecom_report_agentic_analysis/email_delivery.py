"""Cyber Griffin graded alert email delivery with SQLite idempotency lock (Slice D).

Supports:
- Graded subject prefix (`🔴` / `🟡` / `🟢`) based on highest verified Alert severity.
- 30-second executive HTML email preview + attached A4 PDF report.
- Deterministic idempotency lock (`ops_delivery_locks`) preventing duplicate sends per period.
- Dry-run preview mode (renders subject/HTML without touching SMTP).
- Explicit timeouts, bounded retries, zero hardcoded secrets (all read from env).
"""

from __future__ import annotations

import html
import logging
import os
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from wecom_report_agentic_analysis.schemas import AlertSeverity, DualTrackAuditReport
from wecom_report_agentic_analysis.storage import CompanyOpsStorage

logger = logging.getLogger(__name__)


def _coerce_report(report: Any) -> DualTrackAuditReport:
    if isinstance(report, DualTrackAuditReport):
        return report
    return DualTrackAuditReport.model_validate(report)


def _esc(val: Any) -> str:
    return html.escape(str(val if val is not None else ""), quote=True)


def build_graded_alert_email(
    *,
    report: Any,
    metrics: dict[str, Any],
    report_date: str,
) -> tuple[str, str]:
    """Build `(subject, html_body)` per 06_ANALYSIS_FRAMEWORK_AND_REPORT_TEMPLATE_SPEC §6.2."""
    rep = _coerce_report(report)
    crit = [a for a in rep.alerts if a.severity == AlertSeverity.CRITICAL]
    warn = [a for a in rep.alerts if a.severity == AlertSeverity.WARNING]
    opt = [a for a in rep.alerts if a.severity == AlertSeverity.OPTIMIZATION]

    if crit:
        subject = f"【🔴 {len(crit)}项高危漏洞预警｜{len(warn)}项风险提醒】维恩科仪经营诊断周报（{report_date}）"
    elif warn:
        subject = f"【🟡 {len(warn)}项风险偏离提醒】维恩科仪经营诊断周报（{report_date}）"
    else:
        subject = f"【🟢 运行平稳｜{len(opt)}项AI提效建议】维恩科仪经营诊断周报（{report_date}）"

    rd_focus = (
        rep.high_cost_rd_audit.strategic_rd_share_pct
        if rep.high_cost_rd_audit is not None
        else float((metrics.get("high_cost_rd_metrics") or {}).get("strategic_rd_share_pct", 0.0))
    )

    top_alerts = (crit + warn + opt)[:5]
    alert_items_html = "".join(
        f"<li style='margin-bottom:8px;'>"
        f"<strong>[{'🔴高危' if a.severity == AlertSeverity.CRITICAL else ('🟡提醒' if a.severity == AlertSeverity.WARNING else '🔵提效')}·{_esc(a.track.value)}] "
        f"{_esc(a.title)}</strong><br/>"
        f"<span style='color:#475569;'>量化数据：{_esc(a.quant_data)}</span><br/>"
        f"<span style='color:#0f172a;'>建议动作：{_esc(a.recommended_action)}</span>"
        f"</li>"
        for a in top_alerts
    ) or "<li>本周期未触发高危或偏离预警，整体运行平稳。</li>"

    html_body = (
        "<!DOCTYPE html><html lang='zh-CN'><body style='font-family:PingFang SC,Microsoft YaHei,sans-serif;color:#0f172a;line-height:1.6;'>"
        f"<h2 style='color:#1e3a8a;margin-bottom:6px;'>维恩科仪双轨经营诊断与漏洞预警周报（{_esc(report_date)}）</h2>"
        f"<p style='background:#f8fafc;border:1px solid #cbd5e1;padding:10px;border-radius:6px;'>"
        f"<strong>告警概览：</strong>🔴 高危 {len(crit)} 项 ｜ 🟡 风险提醒 {len(warn)} 项 ｜ 🔵 AI 提效 {len(opt)} 项 ｜ "
        f"<strong>李文颖研发专注度：</strong>{rd_focus:.1f}% ｜ <strong>硬成果达标率：</strong>{rep.overall_hard_deliverable_pass_rate_pct:.1f}%"
        "</p>"
        f"<p><strong>30 秒总览：</strong>{_esc(rep.executive_brief_md)}</p>"
        "<h3>建议董事长优先关注与拍板的重点事项</h3>"
        f"<ol>{alert_items_html}</ol>"
        "<p style='color:#475569;font-size:12px;border-top:1px solid #e2e8f0;padding-top:8px;'>"
        "完整 10 页可视化图表、全员 15 人精确出勤硬表、轨道一汇报质量评估、轨道二目标投入总账及短号溯源附录，请查阅随信附带的 <strong>PDF 报告附件</strong>。"
        "</p></body></html>"
    )
    return (subject, html_body)


def _send_via_cyber_griffin_smtp(
    *,
    sender: str,
    recipient: str,
    subject: str,
    html_body: str,
    attachment_path: Path,
    timeout: float = 20.0,
    max_retries: int = 2,
) -> dict[str, Any]:
    host = (os.getenv("CYBER_GRIFFIN_SMTP_HOST") or os.getenv("SMTP_HOST") or "").strip()
    port = int(os.getenv("CYBER_GRIFFIN_SMTP_PORT") or os.getenv("SMTP_PORT") or "465")
    user = (os.getenv("CYBER_GRIFFIN_SMTP_USER") or os.getenv("SMTP_USER") or sender).strip()
    password = (os.getenv("CYBER_GRIFFIN_SMTP_PASSWORD") or os.getenv("SMTP_PASSWORD") or "").strip()
    use_ssl = str(os.getenv("CYBER_GRIFFIN_SMTP_SSL", "true")).lower() in ("1", "true", "yes")

    if not host or not password:
        raise RuntimeError(
            "Missing Cyber Griffin SMTP configuration: set CYBER_GRIFFIN_SMTP_HOST and CYBER_GRIFFIN_SMTP_PASSWORD "
            "(never hardcode email credentials)."
        )

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content("请使用支持 HTML 的邮件客户端查看本经营预警周报，完整报告见附件 PDF。")
    msg.add_alternative(html_body, subtype="html")
    if attachment_path.exists():
        msg.add_attachment(
            attachment_path.read_bytes(),
            maintype="application",
            subtype="pdf",
            filename=attachment_path.name,
        )

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            if use_ssl:
                with smtplib.SMTP_SSL(host, port, timeout=timeout) as srv:
                    srv.login(user, password)
                    srv.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=timeout) as srv:
                    srv.starttls()
                    srv.login(user, password)
                    srv.send_message(msg)
            return {"ok": True, "host": host, "port": port, "attempt": attempt + 1}
        except (smtplib.SMTPException, OSError) as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(0.5 * (2**attempt))
            else:
                raise RuntimeError(f"Cyber Griffin SMTP failed after {max_retries + 1} attempts: {exc}") from exc
    raise RuntimeError(f"Cyber Griffin SMTP failed: {last_exc}")


def deliver_weekly_alert_email(
    *,
    storage: CompanyOpsStorage,
    period_key: str,
    report: Any,
    metrics: dict[str, Any],
    pdf_path: str | Path,
    report_date: str,
    dry_run: bool = False,
    smtp_sender: Any | None = None,
) -> dict[str, Any]:
    """Send graded Cyber Griffin alert email with idempotency lock and PDF attachment."""
    subject, html_body = build_graded_alert_email(
        report=report,
        metrics=metrics,
        report_date=report_date,
    )
    sender = (os.getenv("CYBER_GRIFFIN_FROM") or "cyber.griffin@palmarytech.com").strip()
    recipient = (os.getenv("CYBER_GRIFFIN_TO") or "john.xu@palmarytech.com").strip()
    pdf_p = Path(pdf_path)

    if dry_run:
        return {
            "status": "dry_run",
            "sent": False,
            "skipped": False,
            "period_key": period_key,
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "html_body": html_body,
            "pdf_path": str(pdf_p),
        }

    if storage.has_delivery_lock(period_key):
        logger.info("Weekly alert email already delivered for period_key=%s; skipping duplicate send", period_key)
        return {
            "status": "skipped_duplicate",
            "sent": False,
            "skipped": True,
            "period_key": period_key,
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "pdf_path": str(pdf_p),
        }

    if smtp_sender is not None:
        provider_res = smtp_sender(
            sender=sender,
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            attachment_path=str(pdf_p),
        )
    else:
        provider_res = _send_via_cyber_griffin_smtp(
            sender=sender,
            recipient=recipient,
            subject=subject,
            html_body=html_body,
            attachment_path=pdf_p,
        )

    storage.record_delivery_lock(
        period_key,
        subject=subject,
        recipient=recipient,
        pdf_path=str(pdf_p),
        status="sent",
    )
    return {
        "status": "sent",
        "sent": True,
        "skipped": False,
        "period_key": period_key,
        "sender": sender,
        "recipient": recipient,
        "subject": subject,
        "pdf_path": str(pdf_p),
        "provider_response": provider_res,
    }
