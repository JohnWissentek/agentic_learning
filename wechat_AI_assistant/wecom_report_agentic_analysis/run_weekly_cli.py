"""Production headless CLI runner for V3.0 Weekly Dual-Track Alert Workflow (Slice D).

Runs cleanly without LangGraph Studio or observability dashboards (`OBS_HUB_ENABLED=false` default):
  sync (watermark full/incremental) -> 4-horizon metrics -> flagship brain (<=18 steps)
  -> independent Red-Team critic -> grounding verify -> 10-page A4 PDF -> Cyber Griffin email.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wecom_report_agentic_analysis.graph import build_wecom_ops_graph
from wecom_report_agentic_analysis.schemas import load_strategic_goals_config

_TZ_SHANGHAI = timezone(timedelta(hours=8))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run 维恩科仪 V3.0 Dual-Track Weekly Alert & Executive PDF Workflow (Headless)."
    )
    parser.add_argument("--db-path", default="/opt/wechat-agent/data/app.db", help="SQLite database path")
    parser.add_argument("--config-path", default="", help="Path to strategic_goals.json")
    parser.add_argument("--anchor-date", default="", help="Anchor date YYYY-MM-DD (default today Asia/Shanghai)")
    parser.add_argument("--window-days", type=int, default=30, help="Primary evaluation window days")
    parser.add_argument("--audit-kind", default="weekly", choices=["weekly", "monthly", "baseline_30d"])
    parser.add_argument("--skip-sync", action="store_true", help="Skip WeCom API sync and analyze local DB directly")
    parser.add_argument("--dry-run", action="store_true", help="Render PDF & email preview without sending real email")
    parser.add_argument("--output-pdf", default="", help="Custom output PDF path")
    args = parser.parse_args(argv)

    os.environ.setdefault("OBS_HUB_ENABLED", "false")
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    cfg = load_strategic_goals_config(args.config_path or None)
    anchor_date = args.anchor_date.strip() or datetime.now(_TZ_SHANGHAI).date().isoformat()
    out_pdf = args.output_pdf.strip() or str(
        Path(__file__).resolve().parent
        / "reports"
        / f"维恩科仪经营漏洞预警与战略诊断周报_{anchor_date.replace('-', '')}.pdf"
    )

    graph = build_wecom_ops_graph()
    result = graph.invoke(
        {
            "db_path": args.db_path,
            "config_path": args.config_path,
            "anchor_date": anchor_date,
            "window_days": args.window_days,
            "audit_kind": args.audit_kind,
            "skip_sync": args.skip_sync,
            "dry_run": args.dry_run,
            "output_pdf_path": out_pdf,
            "max_investigation_steps": cfg.max_investigation_steps,
            "max_verification_retries": cfg.max_verification_retries,
        }
    )

    summary = {
        "final_status": result.get("final_status"),
        "anchor_date": anchor_date,
        "window_report_count": result.get("window_report_count", 0),
        "investigation_steps": result.get("investigation_steps", 0),
        "verification_passed": result.get("verification_passed"),
        "verification_degraded": result.get("verification_degraded"),
        "audit_id": result.get("audit_id"),
        "pdf_result": result.get("pdf_result"),
        "delivery_result": {
            k: v for k, v in (result.get("delivery_result") or {}).items() if k != "html_body"
        },
        "sync_error": result.get("sync_error", ""),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("final_status") in ("completed", "empty_window") else 1


if __name__ == "__main__":
    raise SystemExit(main())
