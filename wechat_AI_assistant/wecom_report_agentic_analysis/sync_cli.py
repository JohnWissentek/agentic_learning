"""CLI entrypoint for deterministic WeCom 5-template Journal sync into `ops_*` SQLite tables."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wecom_report_agentic_analysis.schemas import DEFAULT_WECOM_TEMPLATES
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
    parser = argparse.ArgumentParser(description="Sync 维恩科仪 5 WeCom Journal templates into SQLite ops_* tables.")
    parser.add_argument("--db-path", default="/opt/wechat-agent/data/app.db", help="Target SQLite path")
    parser.add_argument("--days", type=int, default=30, help="Lookback days (ignored if --start-date given)")
    parser.add_argument("--start-date", default="", help="Inclusive start date YYYY-MM-DD")
    parser.add_argument("--end-date", default="", help="Inclusive end date YYYY-MM-DD")
    parser.add_argument("--summary-only", action="store_true", help="Only print JSON summary (no sample field keys)")
    args = parser.parse_args(argv)

    today = datetime.now(_TZ_SHANGHAI).date()
    end_date = args.end_date.strip() or today.isoformat()
    start_date = args.start_date.strip() or (today - timedelta(days=max(1, args.days) - 1)).isoformat()

    corpid, secret = _resolve_credentials()
    storage = CompanyOpsStorage(Path(args.db_path))
    open_tasks_before = len(storage.read_chairman_open_tasks())

    client = WeComJournalClient(corpid, secret)
    try:
        result = client.sync_reports_to_storage(
            storage,
            start_date=start_date,
            end_date=end_date,
            templates=DEFAULT_WECOM_TEMPLATES,
        )
    finally:
        client.close()

    reports = storage.list_reports(start_date=start_date, end_date=end_date)
    by_template = Counter(r.template_name for r in reports)
    by_submitter = Counter((r.submitter_name or r.submitter_userid) for r in reports)
    open_tasks_after = len(storage.read_chairman_open_tasks())

    out: dict = {
        "sync_result": result.model_dump(),
        "total_reports_in_window": len(reports),
        "by_template": dict(by_template),
        "top_submitters": dict(by_submitter.most_common(20)),
        "chairman_open_tasks_before": open_tasks_before,
        "chairman_open_tasks_after": open_tasks_after,
    }
    if not args.summary_only:
        sample_fields_by_template: dict[str, list[str]] = {}
        for r in reports:
            if r.template_name not in sample_fields_by_template and r.parsed_fields:
                sample_fields_by_template[r.template_name] = list(r.parsed_fields.keys())
        out["parsed_field_keys_by_template"] = sample_fields_by_template

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
