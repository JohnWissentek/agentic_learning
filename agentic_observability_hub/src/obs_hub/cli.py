"""CLI entrypoint (`obs-hub`) for Dual-Stack Observability & Live Canvas Studio."""

from __future__ import annotations

import argparse
import json

import httpx
import uvicorn
from rich.console import Console

from obs_hub.boiler_run_replayer import replay_boiler_run
from obs_hub.config import ObsHubSettings
from obs_hub.live_canvas_server import create_app

console = Console()


def _cmd_verify_stack(settings: ObsHubSettings) -> int:
    statuses: dict[str, str] = {}
    with httpx.Client(timeout=3.0) as client:
        for name, url in (
            ("Scheme B · Langfuse v3 (:3000)", f"{settings.langfuse_web_url}/api/public/health"),
            ("Scheme A1 · Arize Phoenix (:6006)", f"{settings.phoenix_web_url}/healthz"),
            ("Scheme A2 · Live Canvas (:8765)", f"{settings.live_canvas_url}/health"),
        ):
            try:
                r = client.get(url)
                statuses[name] = f"UP (HTTP {r.status_code})"
            except Exception as exc:
                statuses[name] = f"DOWN ({exc.__class__.__name__})"
    console.print_json(json.dumps(statuses, ensure_ascii=False))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="obs-hub")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_srv = sub.add_parser("serve-canvas")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8765)

    p_rep = sub.add_parser("replay-boiler")
    p_rep.add_argument("--no-otlp", action="store_true")

    sub.add_parser("verify-stack")

    args = parser.parse_args()
    settings = ObsHubSettings.load()

    if args.cmd == "serve-canvas":
        app = create_app(settings)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    elif args.cmd == "replay-boiler":
        res = replay_boiler_run(settings, push_otlp=not args.no_otlp)
        console.print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.cmd == "verify-stack":
        raise SystemExit(_cmd_verify_stack(settings))


if __name__ == "__main__":
    main()
