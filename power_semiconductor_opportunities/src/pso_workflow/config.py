"""Configuration, environment loading, cost ledger, and resilient LLM gateway.

Implements:
- Dedicated `.env.ai_search` and `.env.llm` decoupled loading
- Ch 16 Resource-Aware Optimization (3-tier routing + sequential fallback)
- Ch 12 Exception Handling (exponential backoff + JSON repair)
- Ch 19 Cost & Token Telemetry Ledger
"""

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

# Pricing in CNY per 1K tokens / per API call (Ch 16 & Ch 19 telemetry)
CNY_PRICING: dict[str, dict[str, float]] = {
    "qwen3.8-flash": {"input_1k": 0.0005, "output_1k": 0.0020},
    "qwen-plus": {"input_1k": 0.0008, "output_1k": 0.0020},
    "qwen3.8-max": {"input_1k": 0.0024, "output_1k": 0.0096},
    "qwen-max": {"input_1k": 0.0024, "output_1k": 0.0096},
    "deepseek-v4-pro": {"input_1k": 0.0040, "output_1k": 0.0160},
}
SEARCH_UNIT_COST_CNY: dict[str, float] = {
    "metaso_search": 0.050,
    "metaso_reader": 0.050,
    "serper_search": 0.007,
    "jina_reader": 0.000,
    "mock": 0.000,
}


def project_root() -> Path:
    """Resolve the root of `power_semiconductor_opportunities/`."""
    return Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = dotenv_values(path)
    return {k: v for k, v in raw.items() if k and v is not None}


@dataclass
class CostLedger:
    """Thread/async-safe cumulative cost and token tracker."""

    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    search_calls: list[dict[str, Any]] = field(default_factory=list)

    def record_llm(
        self,
        *,
        node: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_chars: int,
        latency_ms: int,
        fallback_used: bool = False,
    ) -> float:
        rates = CNY_PRICING.get(model, {"input_1k": 0.003, "output_1k": 0.010})
        cost_cny = (prompt_tokens / 1000.0) * rates["input_1k"] + (
            completion_tokens / 1000.0
        ) * rates["output_1k"]
        self.llm_calls.append(
            {
                "node": node,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "reasoning_chars": reasoning_chars,
                "latency_ms": latency_ms,
                "fallback_used": fallback_used,
                "cost_cny": round(cost_cny, 6),
            }
        )
        return cost_cny

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
    ) -> float:
        unit = SEARCH_UNIT_COST_CNY.get(kind, 0.01)
        cost_cny = unit if ok else 0.0
        self.search_calls.append(
            {
                "kind": kind,
                "track_id": track_id,
                "query": query[:120],
                "hits": hits,
                "credits": credits,
                "latency_ms": latency_ms,
                "ok": ok,
                "cost_cny": round(cost_cny, 4),
            }
        )
        return cost_cny

    def summary(self) -> dict[str, Any]:
        total_prompt = sum(c["prompt_tokens"] for c in self.llm_calls)
        total_comp = sum(c["completion_tokens"] for c in self.llm_calls)
        llm_cny = sum(c["cost_cny"] for c in self.llm_calls)
        search_cny = sum(c["cost_cny"] for c in self.search_calls)
        by_node: dict[str, dict[str, Any]] = {}
        for c in self.llm_calls:
            n = by_node.setdefault(
                c["node"], {"calls": 0, "tokens": 0, "cost_cny": 0.0}
            )
            n["calls"] += 1
            n["tokens"] += c["prompt_tokens"] + c["completion_tokens"]
            n["cost_cny"] = round(n["cost_cny"] + c["cost_cny"], 5)
        return {
            "total_llm_calls": len(self.llm_calls),
            "total_search_calls": len(self.search_calls),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_comp,
            "llm_cost_cny": round(llm_cny, 4),
            "search_cost_cny": round(search_cny, 4),
            "total_cost_cny": round(llm_cny + search_cny, 4),
            "by_node": by_node,
        }


@dataclass
class WorkflowSettings:
    """Resolved settings combining `.env`, `.env.ai_search`, `.env.llm`, and YAML configs."""

    root_dir: Path
    metaso_api_key: str = ""
    metaso_api_base: str = "https://metaso.cn/api/v1"
    serper_api_key: str = ""
    serper_time_range: str = "qdr:y"
    tavily_api_key: str = ""
    exa_api_key: str = ""
    perplexity_api_key: str = ""
    firecrawl_api_key: str = ""
    jina_api_key: str = ""

    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    fast_model: str = "qwen3.8-flash"
    fast_fallback_model: str = "qwen-plus"
    producer_model: str = "qwen3.8-max"
    producer_fallback_model: str = "qwen-max"
    critic_model: str = "deepseek-v4-pro"
    critic_fallback_model: str = "qwen3.8-max"

    max_reflection_loops: int = 2
    concurrency: int = 6
    data_dir: Path = field(default_factory=lambda: Path("data"))
    default_output_dir: Path = field(default_factory=lambda: Path("outputs/power_semiconductor_online_testing_2026_2036"))

    contract: dict[str, Any] = field(default_factory=dict)
    taxonomy: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | None = None) -> "WorkflowSettings":
        root_dir = (root or project_root()).resolve()
        base_env = _load_env_file(root_dir / ".env")
        search_file = os.environ.get(
            "PSO_ENV_SEARCH_FILE", base_env.get("PSO_ENV_SEARCH_FILE", ".env.ai_search")
        )
        llm_file = os.environ.get(
            "PSO_ENV_LLM_FILE", base_env.get("PSO_ENV_LLM_FILE", ".env.llm")
        )
        search_env = _load_env_file(root_dir / search_file)
        llm_env = _load_env_file(root_dir / llm_file)

        def pick(key: str, default: str = "") -> str:
            return (
                os.environ.get(key)
                or search_env.get(key)
                or llm_env.get(key)
                or base_env.get(key)
                or default
            ).strip()

        contract_path = root_dir / "config" / "research_contract.yaml"
        taxonomy_path = root_dir / "config" / "domain_taxonomy.yaml"
        contract = (
            yaml.safe_load(contract_path.read_text(encoding="utf-8"))
            if contract_path.exists()
            else {}
        )
        taxonomy = (
            yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
            if taxonomy_path.exists()
            else {}
        )

        data_dir = Path(pick("PSO_DATA_DIR", "data"))
        if not data_dir.is_absolute():
            data_dir = root_dir / data_dir
        out_dir = Path(pick("PSO_DEFAULT_OUTPUT_DIR", "outputs/power_semiconductor_online_testing_2026_2036"))
        if not out_dir.is_absolute():
            out_dir = root_dir / out_dir

        return cls(
            root_dir=root_dir,
            metaso_api_key=pick("METASO_API_KEY"),
            metaso_api_base=pick("METASO_API_BASE", "https://metaso.cn/api/v1").rstrip("/"),
            serper_api_key=pick("SERPER_API_KEY"),
            serper_time_range=pick("SERPER_TIME_RANGE", "qdr:y"),
            tavily_api_key=pick("TAVILY_API_KEY"),
            exa_api_key=pick("EXA_API_KEY"),
            perplexity_api_key=pick("PERPLEXITY_API_KEY"),
            firecrawl_api_key=pick("FIRECRAWL_API_KEY"),
            jina_api_key=pick("JINA_API_KEY"),
            dashscope_api_key=pick("DASHSCOPE_API_KEY") or pick("OPENAI_API_KEY"),
            dashscope_base_url=pick(
                "OPENAI_BASE_URL",
                pick("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            ).rstrip("/"),
            fast_model=pick("PSO_FAST_MODEL", "qwen3.8-flash"),
            fast_fallback_model=pick("PSO_FAST_FALLBACK_MODEL", "qwen-plus"),
            producer_model=pick("PSO_PRODUCER_MODEL", "qwen3.8-max"),
            producer_fallback_model=pick("PSO_PRODUCER_FALLBACK_MODEL", "qwen-max"),
            critic_model=pick("PSO_CRITIC_MODEL", "deepseek-v4-pro"),
            critic_fallback_model=pick("PSO_CRITIC_FALLBACK_MODEL", "qwen3.8-max"),
            max_reflection_loops=int(pick("PSO_MAX_REFLECTION_LOOPS", "2")),
            concurrency=int(pick("PSO_CONCURRENCY", "6")),
            data_dir=data_dir,
            default_output_dir=out_dir,
            contract=contract or {},
            taxonomy=taxonomy or {},
        )


def strip_json_fences(raw: str) -> str:
    """Extract clean JSON object or array from model output."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    # Locate outer JSON delimiters if conversational prose precedes/follows
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
        # Ensure deepseek reasoning models have ample token budget so `content` isn't empty
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
                # Append repair hint on retry
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
