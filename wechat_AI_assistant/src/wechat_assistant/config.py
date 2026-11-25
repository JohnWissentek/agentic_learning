"""Runtime configuration, Shanghai timezone helpers, secret leak guard, cost ledger, and DashScope LLM gateway."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Literal, TypeVar
from zoneinfo import ZoneInfo

from dotenv import dotenv_values
from openai import OpenAI
from pydantic import BaseModel

APP_TZ = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Shanghai"))


def now_local() -> datetime:
    """Return current timezone-aware datetime in `APP_TZ` (default Asia/Shanghai)."""
    return datetime.now(APP_TZ)


def today_local() -> date:
    """Return current calendar date in `APP_TZ` (default Asia/Shanghai)."""
    return now_local().date()


TierName = Literal["fast", "producer", "critic"]
TModel = TypeVar("TModel", bound=BaseModel)

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
)


class SecretLeakError(ValueError):
    """Raised when an outgoing payload, card, or log contains plaintext credentials."""


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Validated application configuration loaded from `.env` and `env/.env.*`."""

    dashscope_api_key: str
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    fast_model: str = "qwen3.8-flash"
    fast_fallback_model: str = "qwen-plus"
    producer_model: str = "qwen3.8-max"
    producer_fallback_model: str = "qwen-max"
    critic_model: str = "deepseek-v4-pro"
    critic_fallback_model: str = "qwen3.8-max"
    max_reflection_loops: int = 2

    wecom_corp_id: str = ""
    wecom_app_agent_id: str = ""
    wecom_app_secret: str = ""
    wecom_app_token: str = ""
    wecom_app_aes_key: str = ""
    wecom_app_owner_userid: str = ""
    wecom_kf_secret: str = ""
    wecom_kf_open_kfid: str = ""
    wecom_kf_url: str = ""
    owner_external_userid: str = ""

    ms_cloud_env: str = "china_21vianet"
    ms_auth_url: str = "https://login.partner.microsoftonline.cn"
    ms_graph_url: str = "https://microsoftgraph.chinacloudapi.cn/v1.0"
    ms_tenant_id: str = ""
    ms_client_id: str = ""
    ms_client_secret: str = ""
    ms_site_id: str = ""

    web_bind_host: str = "127.0.0.1"
    web_port: int = 8090
    web_public_base_url: str = "https://assistant.fire-matrix.com"
    web_access_secret: str = ""
    daily_capacity_hours: float = 6.0

    mail_enabled: bool = False
    mail_user: str = "info@wissentek.com"
    mail_auth_url: str = "https://login.microsoftonline.com"
    mail_graph_url: str = "https://graph.microsoft.com/v1.0"
    mail_tenant_id: str = ""
    mail_client_id: str = ""
    mail_client_secret: str = ""
    mail_allowlist: tuple[str, ...] = ("V&F", "Tera", "B&D")
    external_search_enabled: bool = False
    data_dir: str = "/opt/wechat-agent/data"

    @classmethod
    def load(
        cls,
        env_file: str | Path | None = None,
        *,
        require_bailian: bool = True,
        require_ms365: bool = False,
        require_wecom_secret: bool = False,
        use_os_env: bool = True,
    ) -> Settings:
        """Load configuration with fail-fast validation for required credentials."""
        values: dict[str, str] = {}
        root = Path(__file__).resolve().parents[2]
        candidates: list[Path] = []
        if env_file is not None:
            candidates.append(Path(env_file))
        else:
            for rel in ("env/.env.bailian", "env/.env.wecom", "env/.env.ms365", ".env"):
                candidates.append(root / rel)

        for path in candidates:
            if path.exists():
                for k, v in dotenv_values(path).items():
                    if k and v is not None:
                        values[k] = v

        if use_os_env:
            for k, v in os.environ.items():
                values[k] = v

        def get(key: str, default: str = "") -> str:
            return values.get(key, default).strip()

        dash_key = get("DASHSCOPE_API_KEY")
        if require_bailian and not dash_key:
            raise ValueError("Missing required credential: DASHSCOPE_API_KEY")

        ms_tenant = get("MS_TENANT_ID")
        ms_client = get("MS_CLIENT_ID")
        ms_secret = get("MS_CLIENT_SECRET")
        ms_site = get("MS_SITE_ID")
        if require_ms365 and not (ms_tenant and ms_client and ms_secret and ms_site):
            raise ValueError(
                "Missing required MS365 credentials: MS_TENANT_ID / MS_CLIENT_ID / MS_CLIENT_SECRET / MS_SITE_ID"
            )

        wecom_secret = get("WECOM_APP_SECRET") or get("WECOM_KF_SECRET")
        if require_wecom_secret and not (get("WECOM_CORP_ID") and wecom_secret):
            raise ValueError("Missing required WeCom credentials: WECOM_CORP_ID / WECOM_APP_SECRET")

        return cls(
            dashscope_api_key=dash_key,
            dashscope_base_url=get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            fast_model=get("FAST_MODEL", "qwen3.8-flash"),
            fast_fallback_model=get("FAST_FALLBACK_MODEL", "qwen-plus"),
            producer_model=get("PRODUCER_MODEL", "qwen3.8-max"),
            producer_fallback_model=get("PRODUCER_FALLBACK_MODEL", "qwen-max"),
            critic_model=get("CRITIC_MODEL", "deepseek-v4-pro"),
            critic_fallback_model=get("CRITIC_FALLBACK_MODEL", "qwen3.8-max"),
            max_reflection_loops=int(get("MAX_REFLECTION_LOOPS", "2")),
            wecom_corp_id=get("WECOM_CORP_ID"),
            wecom_app_agent_id=get("WECOM_APP_AGENT_ID"),
            wecom_app_secret=get("WECOM_APP_SECRET"),
            wecom_app_token=get("WECOM_APP_TOKEN"),
            wecom_app_aes_key=get("WECOM_APP_AES_KEY"),
            wecom_app_owner_userid=get("WECOM_APP_OWNER_USERID"),
            wecom_kf_secret=get("WECOM_KF_SECRET"),
            wecom_kf_open_kfid=get("WECOM_KF_OPEN_KFID"),
            wecom_kf_url=get("WECOM_KF_URL"),
            owner_external_userid=get("OWNER_EXTERNAL_USERID"),
            ms_cloud_env=get("MS_CLOUD_ENV", "china_21vianet"),
            ms_auth_url=get("MS_AUTH_URL", "https://login.partner.microsoftonline.cn"),
            ms_graph_url=get("MS_GRAPH_URL", "https://microsoftgraph.chinacloudapi.cn/v1.0"),
            ms_tenant_id=ms_tenant,
            ms_client_id=ms_client,
            ms_client_secret=ms_secret,
            ms_site_id=ms_site,
            web_bind_host=get("WEB_BIND_HOST", "127.0.0.1"),
            web_port=int(get("WEB_PORT", "8090")),
            web_public_base_url=get("WEB_PUBLIC_BASE_URL", "https://assistant.fire-matrix.com"),
            web_access_secret=get("WEB_ACCESS_SECRET"),
            daily_capacity_hours=float(get("DAILY_CAPACITY_HOURS", "6.0")),
            mail_enabled=_parse_bool(get("MAIL_ENABLED"), False),
            mail_user=get("MAIL_USER", "info@wissentek.com"),
            mail_auth_url=get("MAIL_AUTH_URL", "https://login.microsoftonline.com"),
            mail_graph_url=get("MAIL_GRAPH_URL", "https://graph.microsoft.com/v1.0"),
            mail_tenant_id=get("MAIL_TENANT_ID"),
            mail_client_id=get("MAIL_CLIENT_ID"),
            mail_client_secret=get("MAIL_CLIENT_SECRET"),
            mail_allowlist=tuple(
                x.strip()
                for x in get("MAIL_ALLOWLIST", "V&F,Tera,B&D").replace(";", ",").split(",")
                if x.strip()
            ),
            external_search_enabled=_parse_bool(get("EXTERNAL_SEARCH_ENABLED"), False),
            data_dir=get("DATA_DIR", "/opt/wechat-agent/data"),
        )

    def secret_values(self) -> list[str]:
        """Return non-empty secret strings (>=8 chars) for redaction & leak detection."""
        raw = [
            self.dashscope_api_key,
            self.wecom_app_secret,
            self.wecom_kf_secret,
            self.wecom_app_aes_key,
            self.wecom_app_token,
            self.ms_client_secret,
            self.mail_client_secret,
            self.web_access_secret,
        ]
        return [val for val in raw if val and len(val) >= 8]

    def model_pair(self, tier: TierName) -> tuple[str, str]:
        """Return `(primary_model, fallback_model)` for the requested tier."""
        mapping = {
            "fast": (self.fast_model, self.fast_fallback_model),
            "producer": (self.producer_model, self.producer_fallback_model),
            "critic": (self.critic_model, self.critic_fallback_model),
        }
        return mapping[tier]


def assert_no_secrets_leaked(text: str, settings: Settings | None = None) -> None:
    """Raise `SecretLeakError` if text contains API keys or configured secret values."""
    if not text:
        return
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise SecretLeakError("Detected credential pattern in output")
    if settings is not None:
        for secret in settings.secret_values():
            if secret in text:
                raise SecretLeakError("Detected configured secret value in output")


def redact_secrets(text: str, settings: Settings | None = None) -> str:
    """Replace known credentials and key patterns in logs with `[REDACTED]`."""
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED_KEY]", out)
    if settings is not None:
        for secret in settings.secret_values():
            out = out.replace(secret, "[REDACTED]")
    return out


def extract_and_repair_json(raw: str) -> dict[str, Any]:
    """Strip thinking tags/fences and repair minor JSON formatting glitches from LLM output."""
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    first_brace = cleaned.find("{")
    if first_brace > 0:
        cleaned = cleaned[first_brace:]

    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    try:
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("Top-level JSON must be an object")
        return parsed
    except json.JSONDecodeError:
        last_brace = cleaned.rfind("}")
        if last_brace != -1:
            sliced = re.sub(r",\s*([}\]])", r"\1", cleaned[: last_brace + 1])
            parsed = json.loads(sliced)
            if isinstance(parsed, dict):
                return parsed
        raise


@dataclass
class ModelCallRecord:
    """Single model invocation telemetry record."""

    tier: TierName
    model: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    latency_ms: int
    success: bool
    fallback_used: bool = False


@dataclass
class CostLedger:
    """Thread-safe accumulator for multi-tier token usage and latency tracking."""

    records: list[ModelCallRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, item: ModelCallRecord) -> None:
        with self._lock:
            self.records.append(item)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            total_prompt = sum(r.prompt_tokens for r in self.records)
            total_completion = sum(r.completion_tokens for r in self.records)
            total_reasoning = sum(r.reasoning_tokens for r in self.records)
            return {
                "calls": len(self.records),
                "failures": sum(1 for r in self.records if not r.success),
                "fallbacks": sum(1 for r in self.records if r.fallback_used),
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "reasoning_tokens": total_reasoning,
                "total_tokens": total_prompt + total_completion,
            }


class DashScopeLLMGateway:
    """Unified gateway routing `fast`, `producer`, and `critic` tiers with automatic fallback."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
        ledger: CostLedger | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            timeout=90.0,
        )
        self.ledger = ledger or CostLedger()

    def _invoke_once(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None,
        tool_executor: Callable[[str, dict[str, Any]], str] | None,
        max_tokens: int,
        temperature: float,
        enable_thinking: bool = False,
    ) -> tuple[str, int, int, int, str]:
        history = list(messages)
        prompt_tok = comp_tok = reason_tok = 0
        reasoning_text = ""
        max_rounds = 5

        for round_idx in range(max_rounds):
            is_final_round = round_idx == max_rounds - 1
            if is_final_round and tools and round_idx > 0:
                history.append({
                    "role": "user",
                    "content": "工具查询轮次已达上限，请立即基于已获取的工具结果输出最终严格 JSON 对象，不要再调用工具。",
                })
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": history,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if not enable_thinking and any(k in model.lower() for k in ("qwen3", "deepseek")):
                kwargs["extra_body"] = {"enable_thinking": False}
            if tools and not is_final_round:
                kwargs["tools"] = tools

            resp = self.client.chat.completions.create(**kwargs)
            usage = getattr(resp, "usage", None)
            if usage is not None:
                prompt_tok += int(getattr(usage, "prompt_tokens", 0) or 0)
                comp_tok += int(getattr(usage, "completion_tokens", 0) or 0)
                details = getattr(usage, "completion_tokens_details", None)
                if details is not None:
                    reason_tok += int(getattr(details, "reasoning_tokens", 0) or 0)

            msg = resp.choices[0].message
            rc = getattr(msg, "reasoning_content", None) or ""
            if rc:
                reasoning_text = rc

            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls and tool_executor is not None and not is_final_round:
                history.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })
                for tc in tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                        if not isinstance(args, dict):
                            args = {}
                    except json.JSONDecodeError:
                        args = {}
                    try:
                        result = tool_executor(tc.function.name, args)
                    except Exception as tool_exc:
                        result = json.dumps(
                            {"error": f"工具执行异常: {type(tool_exc).__name__}"},
                            ensure_ascii=False,
                        )
                    assert_no_secrets_leaked(result, self.settings)
                    history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                continue

            content = msg.content or ""
            assert_no_secrets_leaked(content, self.settings)
            return content, prompt_tok, comp_tok, reason_tok, reasoning_text

        raise RuntimeError(f"Exceeded max tool rounds for model={model}")

    def generate_structured(
        self,
        tier: TierName,
        messages: list[dict[str, Any]],
        response_model: type[TModel],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], str] | None = None,
        max_tokens: int = 1536,
        temperature: float = 0.2,
    ) -> tuple[TModel, ModelCallRecord]:
        """Invoke primary tier model with backoff & automatic fallback to backup model."""
        primary, fallback = self.settings.model_pair(tier)
        use_thinking = tier == "critic" and os.environ.get("ENABLE_CRITIC_THINKING", "false").lower() == "true"
        effective_max_tokens = max(max_tokens, 4096) if use_thinking else max_tokens
        schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        schema_instruction = (
            "\n\n【严格 JSON 输出契约】请严格只输出一个符合以下 JSON Schema 的 JSON 对象，不要包含额外解释文本：\n"
            f"{schema_json}"
        )
        # Keep system role strictly at index 0 (never append trailing system after user)
        enriched_messages = [dict(m) for m in messages]
        if enriched_messages and enriched_messages[0].get("role") == "system":
            enriched_messages[0]["content"] = str(enriched_messages[0].get("content") or "") + schema_instruction
        else:
            enriched_messages.insert(0, {"role": "system", "content": schema_instruction.strip()})

        last_exc: Exception | None = None
        candidates = [(primary, False), (fallback, True)] if fallback and fallback != primary else [(primary, False)]
        for model, is_fallback in candidates:
            for attempt in range(2):
                start = time.monotonic()
                try:
                    raw, pt, ct, rt, _ = self._invoke_once(
                        model,
                        enriched_messages,
                        tools=tools,
                        tool_executor=tool_executor,
                        max_tokens=effective_max_tokens,
                        temperature=temperature,
                        enable_thinking=use_thinking,
                    )
                    parsed = response_model.model_validate(extract_and_repair_json(raw))
                    rec = ModelCallRecord(
                        tier=tier,
                        model=model,
                        prompt_tokens=pt,
                        completion_tokens=ct,
                        reasoning_tokens=rt,
                        latency_ms=int((time.monotonic() - start) * 1000),
                        success=True,
                        fallback_used=is_fallback,
                    )
                    self.ledger.record(rec)
                    return parsed, rec
                except Exception as exc:
                    last_exc = exc
                    self.ledger.record(
                        ModelCallRecord(
                            tier=tier,
                            model=model,
                            prompt_tokens=0,
                            completion_tokens=0,
                            reasoning_tokens=0,
                            latency_ms=int((time.monotonic() - start) * 1000),
                            success=False,
                            fallback_used=is_fallback,
                        )
                    )
                    if attempt == 0:
                        time.sleep(0.5)

        raise RuntimeError(f"All models failed for tier={tier}: {type(last_exc).__name__ if last_exc else 'unknown'}")
