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

import yaml
from dotenv import dotenv_values
from openai import AsyncOpenAI
from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)

# Indicative API cost per 1M tokens (USD) & USD->CNY conversion for budget telemetry
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
    """Loaded configuration from .env files and YAML governance artifacts."""

    root_dir: Path
    siggi_corpus_dir: Path
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
    discovery_scope: dict[str, Any]

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
        env_main = dotenv_values(base / ".env") if (base / ".env").exists() else {}
        search_env = dotenv_values(base / ".env.ai_search") if (base / ".env.ai_search").exists() else {}
        llm_env = dotenv_values(base / ".env.llm") if (base / ".env.llm").exists() else {}

        def pick(*keys: str, default: str = "") -> str:
            for key in keys:
                for src in (os.environ, env_main, search_env, llm_env):
                    val = src.get(key)
                    if val is not None and str(val).strip():
                        return str(val).strip()
            return default

        def load_yaml(rel_path: str) -> dict[str, Any]:
            p = base / rel_path
            if not p.exists():
                return {}
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}

        contract = load_yaml("config/research_contract.yaml")
        discovery_scope = load_yaml("config/discovery_scope.yaml")

        raw_data_dir = pick("VF_DATA_DIR", default="data")
        data_dir = Path(raw_data_dir) if Path(raw_data_dir).is_absolute() else base / raw_data_dir

        raw_out_dir = pick("VF_DEFAULT_OUTPUT_DIR", default="../research_outputs")
        out_dir = Path(raw_out_dir) if Path(raw_out_dir).is_absolute() else (base / raw_out_dir).resolve()

        default_siggi = str(base.parents[1] / "information_from_siggi")
        raw_siggi = pick("VF_SIGGI_CORPUS_DIR", default=default_siggi)
        siggi_dir = Path(raw_siggi) if Path(raw_siggi).is_absolute() else (base / raw_siggi).resolve()

        vault_db_name = pick("VF_VAULT_DB", default="vf_ccus_evidence_vault.db")

        return cls(
            root_dir=base,
            siggi_corpus_dir=siggi_dir,
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
            fast_model=pick("VF_FAST_MODEL", "PSO_FAST_MODEL", default="qwen3.8-flash"),
            fast_fallback_model=pick("VF_FAST_FALLBACK_MODEL", "PSO_FAST_FALLBACK_MODEL", default="qwen-plus"),
            producer_model=pick("VF_PRODUCER_MODEL", "PSO_PRODUCER_MODEL", default="qwen3.8-max"),
            producer_fallback_model=pick("VF_PRODUCER_FALLBACK_MODEL", "PSO_PRODUCER_FALLBACK_MODEL", default="qwen-max"),
            critic_model=pick("VF_CRITIC_MODEL", "PSO_CRITIC_MODEL", default="deepseek-v4-pro"),
            critic_fallback_model=pick("VF_CRITIC_FALLBACK_MODEL", "PSO_CRITIC_FALLBACK_MODEL", default="qwen3.8-max"),
            max_reflection_loops=int(pick("VF_MAX_REFLECTION_LOOPS", "PSO_MAX_REFLECTION_LOOPS", default="2")),
            concurrency=int(pick("VF_CONCURRENCY", "PSO_CONCURRENCY", default="6")),
            data_dir=data_dir,
            vault_db_name=vault_db_name,
            default_output_dir=out_dir,
            contract=contract,
            discovery_scope=discovery_scope,
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


def unwrap_json_container_strings(value: Any) -> Any:
    """Recursively unwrap JSON-serialized array/object strings produced by LLMs."""
    if isinstance(value, dict):
        return {k: unwrap_json_container_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap_json_container_strings(x) for x in value]
    if isinstance(value, str):
        s = value.strip()
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, (list, dict)):
                    return unwrap_json_container_strings(parsed)
            except Exception:
                return value
    return value


class LLMClientProtocol(Protocol):
    """Protocol enabling deterministic unit/trajectory testing with mock LLMs."""

    async def complete_text(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 6000,
    ) -> str: ...

    async def complete_structured(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        schema: Type[TModel],
        temperature: float = 0.15,
        max_tokens: int = 6000,
    ) -> TModel: ...


class DashScopeLLMGateway:
    """Tiered OpenAI-compatible LLM client with Ch 16 sequential fallback & Ch 12 retries."""

    def __init__(self, settings: WorkflowSettings, ledger: CostLedger) -> None:
        self.settings = settings
        self.ledger = ledger
        self._client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            timeout=300.0,
            max_retries=1,
        )

    def _model_pair(self, tier: str) -> tuple[str, str]:
        if tier == "fast":
            return self.settings.fast_model, self.settings.fast_fallback_model
        if tier == "critic":
            return self.settings.critic_model, self.settings.critic_fallback_model
        return self.settings.producer_model, self.settings.producer_fallback_model

    async def _raw_call(
        self,
        *,
        model: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        fallback_used: bool,
    ) -> str:
        m_low = model.lower()
        effective_max = max(max_tokens, 8192) if "deepseek" in m_low else max_tokens
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": effective_max,
        }
        if "deepseek-r1" not in m_low and "deepseek-v4" not in m_low:
            kwargs["temperature"] = temperature
        if json_mode and "deepseek-v4" not in m_low:
            kwargs["response_format"] = {"type": "json_object"}
        if "qwen3" in m_low:
            kwargs["extra_body"] = {"enable_thinking": False}
        elif "deepseek-v4" in m_low or "deepseek-r1" in m_low:
            kwargs["extra_body"] = {"thinking_budget": 1536}

        t0 = time.perf_counter()
        resp = await self._client.chat.completions.create(**kwargs)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        msg = resp.choices[0].message
        content = (msg.content or "").strip()
        reasoning_text = getattr(msg, "reasoning_content", None) or ""
        usage = resp.usage
        self.ledger.record_llm(
            node=node,
            model=model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            reasoning_chars=len(reasoning_text),
            latency_ms=latency_ms,
            fallback_used=fallback_used,
        )
        if not content:
            raise ValueError(f"Model {model} returned empty content (reasoning={len(reasoning_text)} chars)")
        return content

    async def complete_text(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.25,
        max_tokens: int = 6000,
    ) -> str:
        primary, fallback = self._model_pair(tier)
        models = [(primary, False), (primary, False), (fallback, True)]
        last_err: Exception | None = None
        for idx, (model, is_fb) in enumerate(models):
            try:
                return await self._raw_call(
                    model=model,
                    node=node,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=False,
                    fallback_used=is_fb,
                )
            except Exception as exc:
                last_err = exc
                await asyncio.sleep(min(2.0 * (idx + 1), 6.0))
        raise RuntimeError(f"All LLM attempts failed in node={node}: {last_err}")

    async def complete_structured(
        self,
        *,
        tier: str,
        node: str,
        system_prompt: str,
        user_prompt: str,
        schema: Type[TModel],
        temperature: float = 0.15,
        max_tokens: int = 6000,
    ) -> TModel:
        primary, fallback = self._model_pair(tier)
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        augmented_user = (
            f"{user_prompt}\n\n"
            f"IMPORTANT: Output ONLY valid JSON conforming strictly to this Pydantic JSON Schema "
            f"(no extra commentary outside JSON):\n```json\n{schema_json}\n```"
        )
        attempts = [(primary, False), (primary, False), (fallback, True)]
        last_err: Exception | None = None
        for idx, (model, is_fb) in enumerate(attempts):
            try:
                raw = await self._raw_call(
                    model=model,
                    node=node,
                    system_prompt=system_prompt,
                    user_prompt=augmented_user,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=True,
                    fallback_used=is_fb,
                )
                cleaned = strip_json_fences(raw)
                try:
                    return schema.model_validate_json(cleaned)
                except Exception:
                    raw_obj = json.loads(cleaned)
                    coerced = unwrap_json_container_strings(raw_obj)
                    return schema.model_validate(coerced)
            except Exception as exc:
                last_err = exc
                err_short = str(exc)[:900]
                augmented_user = (
                    f"{user_prompt}\n\n"
                    f"Previous output failed schema validation with error: {err_short}\n"
                    f"Ensure all array and object fields are real JSON arrays/objects (never quoted strings), "
                    f"and output ONLY valid JSON matching:\n{schema_json}"
                )
                await asyncio.sleep(min(1.5 * (idx + 1), 5.0))
        raise RuntimeError(
            f"Structured output parsing failed in node={node} ({schema.__name__}): {last_err}"
        )
