"""CLI entrypoint for watermark-driven 7-template WeCom Journal sync, backfill & cold archive."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from wecom_report_agentic_analysis.schemas import (
    ALL_WECOM_TEMPLATES,
    NEW_TEMPLATE_EFFECTIVE_DATE,
    load_strategic_goals_config,
)
from wecom_report_agentic_analysis.storage import CompanyOpsStorage
from wecom_report_agentic_analysis.wecom_journal_client import WeComJournalClient

_TZ_SHANGHAI = timezone(timedelta(hours=8))


def _resolve_credentials() -> tuple[str, str]:
    corpid = (
        os.getenv("WECOM_OPS_CORP_ID")
        or os.getenv("WECOM_CORP_ID")
        or os.getenv("CORP_ID")
        or ""
    ).strip()
    secret = (
        os.getenv("WECOM_OPS_APP_SECRET")
        or os.getenv("WECOM_APP_SECRET")
        or os.getenv("WECOM_SECRET")
        or os.getenv("APP_SECRET")
        or ""
    ).strip()
    if not corpid or not secret:
        raise RuntimeError(
            "Missing WeCom credentials: set WECOM_OPS_CORP_ID and WECOM_OPS_APP_SECRET "
            "(never hardcode secrets in source code)."
        )
    return corpid, secret


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Watermark-driven sync & historical full backfill for all 7 维恩科仪 WeCom Journal templates."
    )
    parser.add_argument("--db-path", default="/opt/wechat-agent/data/app.db", help="Target SQLite path")
    parser.add_argument("--config-path", default="", help="Path to strategic_goals.json (defaults to config/)")
    parser.add_argument("--full-backfill", action="store_true", help="Force full historical backfill across all 7 templates")
    parser.add_argument("--include-legacy", action="store_true", help="Also backfill pre-2025 unregistered legacy reports")
    parser.add_argument("--start-date", default="", help="Override backfill start date YYYY-MM-DD")
    parser.add_argument("--end-date", default="", help="Inclusive end date YYYY-MM-DD (default today)")
    parser.add_argument("--overlap-days", type=int, default=7, help="Incremental overlap lookback days")
    parser.add_argument("--request-interval", type=float, default=0.12, help="Per-API-request throttle seconds")
    parser.add_argument("--export-archive", default="", help="Export cold backup .jsonl.gz to this path")
    parser.add_argument("--backup-db", default="", help="Create consistent SQLite backup snapshot at this path")
    parser.add_argument("--reparse-local", action="store_true", help="Offline re-parse stored raw_payload_json without API calls")
    parser.add_argument("--summary-only", action="store_true", help="Only print JSON summary")
    args = parser.parse_args(argv)

    cfg = load_strategic_goals_config(args.config_path or None)
    storage = CompanyOpsStorage(Path(args.db_path))
    open_tasks_before = len(storage.read_chairman_open_tasks())

    if args.reparse_local:
        reparsed = storage.reparse_stored_reports(effective_date=cfg.new_template_effective_date)
        out: dict[str, Any] = {
            "mode": "reparse_local",
            "reparsed_count": reparsed,
            "chairman_open_tasks_before": open_tasks_before,
            "chairman_open_tasks_after": len(storage.read_chairman_open_tasks()),
        }
        if args.export_archive:
            out["archive"] = storage.export_reports_archive_jsonl_gz(args.export_archive)
        if args.backup_db:
            out["db_backup"] = str(storage.backup_sqlite_snapshot(args.backup_db))
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    today = datetime.now(_TZ_SHANGHAI).date()
    end_date = args.end_date.strip() or today.isoformat()
    start_date = args.start_date.strip() or cfg.initial_backfill_start_date
    include_legacy = args.include_legacy or bool(
        (cfg.sync_and_analysis_policy.get("data_ingestion") or {}).get("include_unregistered_legacy_backfill", False)
    )

    corpid, secret = _resolve_credentials()
    client = WeComJournalClient(
        corpid,
        secret,
        timeout=15.0,
        max_retries=2,
        request_interval_sec=args.request_interval,
    )
    try:
        result = client.sync_with_watermarks(
            storage,
            templates=ALL_WECOM_TEMPLATES,
            initial_backfill_start_date=start_date,
            end_date=end_date,
            incremental_overlap_days=args.overlap_days,
            include_unregistered_legacy=include_legacy,
            force_full=args.full_backfill,
            effective_date=cfg.new_template_effective_date or NEW_TEMPLATE_EFFECTIVE_DATE,
            archive_output_path=args.export_archive or None,
        )
    finally:
        client.close()

    all_reports = storage.list_reports()
    by_template = Counter(r.template_name for r in all_reports)
    by_era = Counter(r.schema_era for r in all_reports)
    by_submitter = Counter((r.submitter_name or r.submitter_userid) for r in all_reports)
    open_tasks_after = len(storage.read_chairman_open_tasks())

    out = {
        "sync_result": result.model_dump(),
        "total_reports_in_db": len(all_reports),
        "by_template": dict(by_template),
        "by_schema_era": dict(by_era),
        "top_submitters": dict(by_submitter.most_common(20)),
        "watermarks": [w.model_dump() for w in storage.list_sync_watermarks()],
        "chairman_open_tasks_before": open_tasks_before,
        "chairman_open_tasks_after": open_tasks_after,
    }
    if args.backup_db:
        out["db_backup"] = str(storage.backup_sqlite_snapshot(args.backup_db))
    if not args.summary_only:
        sample_fields: dict[str, list[str]] = {}
        for r in all_reports:
            if r.template_name not in sample_fields and r.parsed_fields:
                sample_fields[r.template_name] = list(r.parsed_fields.keys())
        out["parsed_field_keys_by_template"] = sample_fields

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
