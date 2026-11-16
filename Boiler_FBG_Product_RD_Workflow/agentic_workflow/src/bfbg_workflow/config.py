"""Runtime configuration, CostLedger, Secret Guard, and DashScope LLM Gateway."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Type, TypeVar

import httpx
import yaml
from dotenv import dotenv_values
from openai import AsyncOpenAI
from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)

DEFAULT_USD_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "qwen3.8-flash": (0.14, 0.42),
    "qwen-plus": (0.28, 0.84),
    "qwen3.8-max": (1.10, 3.30),
    "qwen-max": (1.40, 4.20),
    "deepseek-v4-pro": (1.20, 3.60),
    "deepseek-v3.2": (0.55, 1.65),
}
USD_TO_CNY = 7.20


@dataclass
class CostLedger:
    """Thread-safe in-memory telemetry for LLM token spend, search credits, and latency."""

    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    search_calls: list[dict[str, Any]] = field(default_factory=list)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_usd: float = 0.0
    total_cny: float = 0.0
    metaso_credits: int = 0
    serper_queries: int = 0

    def record_llm(
        self,
        *,
        node: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_chars: int = 0,
        latency_ms: int = 0,
        fallback_used: bool = False,
    ) -> None:
        in_rate, out_rate = DEFAULT_USD_PER_1M_TOKENS.get(model, (0.80, 2.40))
        usd = (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000.0
        cny = usd * USD_TO_CNY
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_usd += usd
        self.total_cny += cny
        self.llm_calls.append(
            {
                "node": node,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "reasoning_chars": reasoning_chars,
                "latency_ms": latency_ms,
                "fallback_used": fallback_used,
                "cost_cny": round(cny, 5),
            }
        )

    def record_search(
        self,
        *,
        kind: str,
        track_id: str,
        query: str,
        hits: int,
        credits: int = 0,
        latency_ms: int = 0,
        ok: bool = True,
    ) -> None:
        if kind.startswith("metaso"):
            self.metaso_credits += credits
        elif kind.startswith("serper"):
            self.serper_queries += 1
        self.search_calls.append(
            {
                "kind": kind,
                "track_id": track_id,
                "query": query[:140],
                "hits": hits,
                "credits": credits,
                "latency_ms": latency_ms,
                "ok": ok,
            }
        )

    def summary(self) -> dict[str, Any]:
        models_used = sorted({c["model"] for c in self.llm_calls})
        return {
            "llm_call_count": len(self.llm_calls),
            "search_call_count": len(self.search_calls),
            "models_used": models_used,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_usd": round(self.total_usd, 4),
            "total_cny": round(self.total_cny, 3),
            "metaso_credits": self.metaso_credits,
            "serper_queries": self.serper_queries,
        }


@dataclass
class WorkflowSettings:
    """Loaded configuration from .env files (with workspace sibling fallback) and YAML governance."""

    root_dir: Path
    prior_research_dir: Path
    metaso_api_key: str
    metaso_api_base: str
    serper_api_key: str
    serper_time_range: str
    jina_api_key: str
    dashscope_api_key: str
    dashscope_base_url: str
    fast_model: str
    fast_fallback_model: str
    producer_model: str
    producer_fallback_model: str
    critic_model: str
    critic_fallback_model: str
    max_reflection_loops: int
    concurrency: int
    data_dir: Path
    vault_db_name: str
    default_output_dir: Path
    contract: dict[str, Any]
    catalog: dict[str, Any]

    @property
    def default_vault_path(self) -> Path:
        return self.data_dir / self.vault_db_name

    def resolve_vault_path(self, override: str | None = None) -> Path:
        if not override:
            return self.default_vault_path
        p = Path(override)
        return p if p.is_absolute() else self.root_dir / p

    def secret_values(self) -> list[str]:
        """Return non-empty API keys strictly for automated leak-prevention assertions."""
        vals = [
            self.metaso_api_key,
            self.serper_api_key,
            self.jina_api_key,
            self.dashscope_api_key,
        ]
        return [v.strip() for v in vals if v and len(v.strip()) >= 12 and "your_" not in v]

    @classmethod
    def load(cls, root_dir: Path | None = None) -> "WorkflowSettings":
        base = root_dir or Path(__file__).resolve().parents[2]
        workspace_root = base.parents[1]

        env_sources: list[dict[str, str | None]] = [dict(os.environ)]
        candidate_env_dirs = [
            base,
            workspace_root / "CCS_projects _China" / "marketing_research_dev_agentic_workflow" / "agentic_workflow",
            workspace_root / "power_semiconductor_opportunities",
        ]
        for env_dir in candidate_env_dirs:
            for fname in (".env", ".env.ai_search", ".env.llm"):
                p = env_dir / fname
                if p.exists():
                    env_sources.append(dotenv_values(p))

        def pick(*keys: str, default: str = "") -> str:
            for key in keys:
                for src in env_sources:
                    val = src.get(key)
                    if val is not None and str(val).strip():
                        return str(val).strip()
            return default

        def load_yaml(rel_path: str) -> dict[str, Any]:
            p = base / rel_path
            if not p.exists():
                return {}
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}

        contract = load_yaml("config/product_rd_contract.yaml")
        catalog = load_yaml("config/hardware_and_market_catalog.yaml")

        raw_data_dir = pick("BFBG_DATA_DIR", default="data")
        data_dir = Path(raw_data_dir) if Path(raw_data_dir).is_absolute() else base / raw_data_dir

        raw_out_dir = pick("BFBG_DEFAULT_OUTPUT_DIR", default="../output")
        out_dir = Path(raw_out_dir) if Path(raw_out_dir).is_absolute() else (base / raw_out_dir).resolve()

        default_prior = str(workspace_root / "Boiler_FBG_Thermometry_Research")
        raw_prior = pick("BFBG_PRIOR_RESEARCH_DIR", default=default_prior)
        prior_dir = Path(raw_prior) if Path(raw_prior).is_absolute() else (base / raw_prior).resolve()

        vault_db_name = pick("BFBG_VAULT_DB", default="bfbg_evidence_vault.db")

        return cls(
            root_dir=base,
            prior_research_dir=prior_dir,
            metaso_api_key=pick("METASO_API_KEY"),
            metaso_api_base=pick("METASO_API_BASE", default="https://metaso.cn/api/v1").rstrip("/"),
            serper_api_key=pick("SERPER_API_KEY"),
            serper_time_range=pick("SERPER_TIME_RANGE", default="qdr:y"),
            jina_api_key=pick("JINA_API_KEY"),
            dashscope_api_key=pick("DASHSCOPE_API_KEY"),
            dashscope_base_url=pick(
                "DASHSCOPE_BASE_URL",
                default="https://dashscope.aliyuncs.com/compatible-mode/v1",
            ).rstrip("/"),
            fast_model=pick("BFBG_FAST_MODEL", "VF_FAST_MODEL", default="qwen3.8-flash"),
            fast_fallback_model=pick("BFBG_FAST_FALLBACK_MODEL", "VF_FAST_FALLBACK_MODEL", default="qwen-plus"),
            producer_model=pick("BFBG_PRODUCER_MODEL", "VF_PRODUCER_MODEL", default="qwen3.8-max"),
            producer_fallback_model=pick("BFBG_PRODUCER_FALLBACK_MODEL", "VF_PRODUCER_FALLBACK_MODEL", default="qwen-max"),
            critic_model=pick("BFBG_CRITIC_MODEL", "VF_CRITIC_MODEL", default="deepseek-v4-pro"),
            critic_fallback_model=pick("BFBG_CRITIC_FALLBACK_MODEL", "VF_CRITIC_FALLBACK_MODEL", default="qwen3.8-max"),
            max_reflection_loops=int(pick("BFBG_MAX_REFLECTION_LOOPS", default="2")),
            concurrency=int(pick("BFBG_CONCURRENCY", default="6")),
            data_dir=data_dir,
            vault_db_name=vault_db_name,
            default_output_dir=out_dir,
            contract=contract,
            catalog=catalog,
        )


def assert_no_secrets_leaked(text: str, settings: WorkflowSettings) -> None:
    """Verify no secret token substring appears in logs, reports, or telemetry."""
    for secret in settings.secret_values():
        if secret in text:
            raise AssertionError("Detected secret credential leak in output artifact!")


def strip_json_fences(raw: str) -> str:
    """Extract clean JSON object or array from model output."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith(("{", "[")):
        start_obj = text.find("{")
        start_arr = text.find("[")
        candidates = [idx for idx in (start_obj, start_arr) if idx != -1]
        if candidates:
            start = min(candidates)
            end = text.rfind("}" if text[start] == "{" else "]")
            if end > start:
                text = text[start : end + 1]
    return text


def repair_json_text(text: str) -> str:
    """Escape raw unescaped control chars inside JSON string literals and strip trailing commas."""
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    out: list[str] = []
    in_str = False
    escaped = False
    for ch in text:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            out.append(ch)
            in_str = not in_str
            continue
        if in_str:
            if ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def unwrap_json_container_strings(data: Any) -> Any:
    """Recursively parse nested JSON-serialized container strings inside dicts/lists."""
    if isinstance(data, dict):
        return {k: unwrap_json_container_strings(v) for k, v in data.items()}
    if isinstance(data, list):
        return [unwrap_json_container_strings(v) for v in data]
    if isinstance(data, str):
        s = data.strip()
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            try:
                return unwrap_json_container_strings(json.loads(s))
            except Exception:
                pass
    return data


class LLMGatewayProtocol(Protocol):
    """Abstract async LLM gateway allowing deterministic offline test mocking."""

    async def complete_json(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        schema: Type[TModel],
        max_tokens: int = 4096,
        temperature: float = 0.15,
    ) -> TModel: ...

    async def complete_text(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 7500,
        temperature: float = 0.25,
    ) -> str: ...


class DashScopeLLMGateway:
    """OpenAI-compatible DashScope gateway with Ch 16 tiered routing & Ch 12 fallback/repair."""

    def __init__(self, settings: WorkflowSettings, ledger: CostLedger) -> None:
        self.settings = settings
        self.ledger = ledger
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key or "missing-key",
            base_url=settings.dashscope_base_url,
            timeout=180.0,
        )

    def _model_pair(self, tier: str) -> tuple[str, str]:
        if tier == "fast":
            return self.settings.fast_model, self.settings.fast_fallback_model
        if tier == "critic":
            return self.settings.critic_model, self.settings.critic_fallback_model
        return self.settings.producer_model, self.settings.producer_fallback_model

    async def _raw_chat(
        self,
        *,
        model: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        json_mode: bool,
        fallback_used: bool,
    ) -> str:
        t0 = time.perf_counter()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }
        if "deepseek" not in model.lower():
            kwargs["temperature"] = temperature
        if json_mode and "deepseek" not in model.lower():
            kwargs["response_format"] = {"type": "json_object"}

        resp = await self.client.chat.completions.create(**kwargs)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        msg = resp.choices[0].message
        content = msg.content or ""
        reasoning = getattr(msg, "reasoning_content", "") or ""
        usage = resp.usage
        p_tok = int(getattr(usage, "prompt_tokens", 0) or 0)
        c_tok = int(getattr(usage, "completion_tokens", 0) or 0)
        self.ledger.record_llm(
            node=node,
            model=model,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            reasoning_chars=len(reasoning),
            latency_ms=latency_ms,
            fallback_used=fallback_used,
        )
        obs_url = os.environ.get("BFBG_OBS_HUB_URL", "http://127.0.0.1:8765").rstrip("/")
        if os.environ.get("BFBG_DISABLE_OBS_HUB", "") != "1":
            try:
                async with httpx.AsyncClient(timeout=1.0) as obs_c:
                    await obs_c.post(
                        f"{obs_url}/api/events",
                        json={
                            "run_id": os.environ.get("BFBG_RUN_ID", "bfbg-langgraph-live"),
                            "workflow_name": "BoilerSense-AI-LangGraph",
                            "node_id": node,
                            "stage_label": "LangGraph Live",
                            "role_title": node,
                            "span_kind": "generation",
                            "status": "DONE",
                            "model_name": model,
                            "system_prompt": system_prompt,
                            "user_prompt": user_prompt,
                            "thinking": reasoning,
                            "output_text": content,
                            "prompt_tokens": p_tok,
                            "completion_tokens": c_tok,
                            "latency_ms": latency_ms,
                        },
                    )
            except Exception:
                pass
        return content

    async def complete_json(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        schema: Type[TModel],
        max_tokens: int = 4096,
        temperature: float = 0.15,
    ) -> TModel:
        primary, fallback = self._model_pair(tier)
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        enforced_sys = (
            f"{system_prompt}\n\n"
            "CRITICAL OUTPUT CONTRACT: Return ONLY valid JSON matching the exact schema below "
            "(all lists/objects must be native JSON arrays/objects, never quoted JSON strings):\n"
            f"{schema_json}"
        )

        last_err: Exception | None = None
        for idx, model in enumerate((primary, fallback)):
            for attempt in range(2):
                try:
                    raw = await self._raw_chat(
                        model=model,
                        node=node,
                        system_prompt=enforced_sys,
                        user_prompt=user_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        json_mode=True,
                        fallback_used=(idx > 0),
                    )
                    cleaned = strip_json_fences(raw)
                    try:
                        parsed_obj = json.loads(cleaned)
                    except json.JSONDecodeError:
                        parsed_obj = json.loads(repair_json_text(cleaned))
                    parsed_obj = unwrap_json_container_strings(parsed_obj)
                    return schema.model_validate(parsed_obj)
                except Exception as exc:
                    last_err = exc
                    await asyncio.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"LLM complete_json failed on node={node}: {last_err}")

    async def complete_text(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 7500,
        temperature: float = 0.25,
    ) -> str:
        primary, fallback = self._model_pair(tier)
        last_err: Exception | None = None
        for idx, model in enumerate((primary, fallback)):
            for attempt in range(2):
                try:
                    text = await self._raw_chat(
                        model=model,
                        node=node,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        json_mode=False,
                        fallback_used=(idx > 0),
                    )
                    if text.strip():
                        return text.strip()
                except Exception as exc:
                    last_err = exc
                    await asyncio.sleep(1.0 * (attempt + 1))
        raise RuntimeError(f"LLM complete_text failed on node={node}: {last_err}")
