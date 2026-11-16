"""Configuration loader & strict workspace SecretRedactor for observability payloads."""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

# Secret keys scanned from workspace .env files so no live API credential ever hits Docker/SQLite/UI
SENSITIVE_ENV_KEYS = (
    "DASHSCOPE_API_KEY",
    "METASO_API_KEY",
    "SERPER_API_KEY",
    "JINA_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)


@dataclass
class SecretRedactor:
    """Scrubs known workspace API keys and common token patterns before telemetry emission."""

    secrets: list[str] = field(default_factory=list)

    @classmethod
    def from_workspace(cls, workspace_root: Path) -> "SecretRedactor":
        found: set[str] = set()
        for k in SENSITIVE_ENV_KEYS:
            val = os.environ.get(k, "").strip()
            if len(val) >= 12 and "your_" not in val:
                found.add(val)

        candidate_files = [
            workspace_root / ".env.tokens",
            workspace_root / "CCS_projects _China" / "marketing_research_dev_agentic_workflow" / "agentic_workflow" / ".env.ai_search",
            workspace_root / "CCS_projects _China" / "marketing_research_dev_agentic_workflow" / "agentic_workflow" / ".env.llm",
            workspace_root / "power_semiconductor_opportunities" / ".env.ai_search",
            workspace_root / "power_semiconductor_opportunities" / ".env.llm",
            workspace_root / "Boiler_FBG_Product_RD_Workflow" / "agentic_workflow" / ".env.ai_search",
            workspace_root / "Boiler_FBG_Product_RD_Workflow" / "agentic_workflow" / ".env.llm",
        ]
        for f in candidate_files:
            if not f.exists():
                continue
            vals = dotenv_values(f)
            for k in SENSITIVE_ENV_KEYS:
                v = (vals.get(k) or "").strip()
                if len(v) >= 12 and "your_" not in v:
                    found.add(v)
        return cls(secrets=sorted(found, key=len, reverse=True))

    def redact(self, text: str) -> str:
        if not text:
            return ""
        out = text
        for s in self.secrets:
            if s in out:
                out = out.replace(s, "[REDACTED_SECRET]")
        # Scrub generic sk-* / Bearer tokens
        out = re.sub(r"sk-[A-Za-z0-9_-]{18,}", "[REDACTED_SK]", out)
        out = re.sub(r"(Bearer\s+)[A-Za-z0-9._-]{18,}", r"\1[REDACTED_TOKEN]", out)
        return out


@dataclass
class ObsHubSettings:
    """Runtime settings for Dual-Stack OTel Exporter & Live Topology Server."""

    root_dir: Path
    workspace_root: Path
    data_dir: Path
    sqlite_path: Path
    langfuse_web_url: str
    langfuse_otlp_endpoint: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_project_id: str
    phoenix_web_url: str
    phoenix_otlp_endpoint: str
    live_canvas_url: str

    @property
    def langfuse_basic_auth(self) -> str:
        raw = f"{self.langfuse_public_key}:{self.langfuse_secret_key}".encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    @classmethod
    def load(cls, root_dir: Path | None = None) -> "ObsHubSettings":
        base = root_dir or Path(__file__).resolve().parents[2]
        ws_root = base.parent
        env_vals: dict[str, str | None] = {}
        for fname in ("env.observability.example", ".env"):
            p = base / fname
            if p.exists():
                env_vals.update(dotenv_values(p))

        def pick(key: str, default: str) -> str:
            val = os.environ.get(key) or env_vals.get(key)
            return str(val).strip() if val is not None and str(val).strip() else default

        data_dir = base / "data"
        return cls(
            root_dir=base,
            workspace_root=ws_root,
            data_dir=data_dir,
            sqlite_path=data_dir / "live_topology.db",
            langfuse_web_url=pick("NEXTAUTH_URL", "http://127.0.0.1:3000").rstrip("/"),
            langfuse_otlp_endpoint=pick(
                "OBS_LANGFUSE_OTLP_ENDPOINT", "http://127.0.0.1:3000/api/public/otel/v1/traces"
            ),
            langfuse_public_key=pick("LANGFUSE_INIT_PROJECT_PUBLIC_KEY", "pk-lf-boiler-local"),
            langfuse_secret_key=pick("LANGFUSE_INIT_PROJECT_SECRET_KEY", "sk-lf-boiler-local"),
            langfuse_project_id=pick("LANGFUSE_INIT_PROJECT_ID", "boiler-fbg-rd"),
            phoenix_web_url=pick("OBS_PHOENIX_WEB_URL", "http://127.0.0.1:6006").rstrip("/"),
            phoenix_otlp_endpoint=pick("OBS_PHOENIX_OTLP_ENDPOINT", "http://127.0.0.1:6006/v1/traces"),
            live_canvas_url=pick("OBS_LIVE_CANVAS_URL", "http://127.0.0.1:8765").rstrip("/"),
        )
