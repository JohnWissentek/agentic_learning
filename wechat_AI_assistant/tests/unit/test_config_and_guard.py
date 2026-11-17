"""Unit tests for Stage 1 configuration loading, secret guard, JSON repair, and LLM fallback."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from wechat_assistant.config import (
    CostLedger,
    DashScopeLLMGateway,
    SecretLeakError,
    Settings,
    assert_no_secrets_leaked,
    extract_and_repair_json,
    redact_secrets,
)
from wechat_assistant.schemas import IntentRoute


def test_settings_load_fail_fast(tmp_path):
    empty_env = tmp_path / ".env"
    empty_env.write_text("WEB_PORT=8090\n", encoding="utf-8")
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        Settings.load(env_file=empty_env, use_os_env=False)


def test_settings_load_valid(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DASHSCOPE_API_KEY=sk-testunitkey1234567890abcd\nDAILY_CAPACITY_HOURS=5.5\n",
        encoding="utf-8",
    )
    s = Settings.load(env_file=env_file, use_os_env=False)
    assert s.fast_model == "qwen3.8-flash"
    assert s.critic_model == "deepseek-v4-pro"
    assert s.daily_capacity_hours == 5.5


def test_secret_leak_guard_blocks_and_redacts():
    s = Settings(
        dashscope_api_key="sk-fakeunit1234567890abcdef",
        ms_client_secret="fakeMsSecretValue!99",
    )
    with pytest.raises(SecretLeakError):
        assert_no_secrets_leaked("token is sk-fakeunit1234567890abcdef", s)
    with pytest.raises(SecretLeakError):
        assert_no_secrets_leaked("secret=fakeMsSecretValue!99", s)

    masked = redact_secrets("key=sk-fakeunit1234567890abcdef ms=fakeMsSecretValue!99", s)
    assert "sk-fakeunit" not in masked
    assert "fakeMsSecretValue" not in masked
    assert_no_secrets_leaked("clean business summary for Q4", s)


def test_extract_and_repair_json():
    messy = """<think>Analyzing intent...</think>
    Here is the output:
    ```json
    {
      "intent": "work_triage",
      "confidence": 0.92,
      "needs_deep_research": false,
      "summary": "Review pump BOM quote",
    }
    ```
    trailing note"""
    parsed = extract_and_repair_json(messy)
    assert parsed["intent"] == "work_triage"
    assert parsed["confidence"] == 0.92


class _FakeCompletions:
    def __init__(self):
        self.calls: list[str] = []

    def create(self, **kwargs):
        model = kwargs["model"]
        self.calls.append(model)
        if model == "qwen3.8-flash":
            raise RuntimeError("transient primary error")
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=20, completion_tokens_details=None),
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"intent": "checkin", "confidence": 0.98, "needs_deep_research": false, "summary": "Mark task 1 done"}',
                        tool_calls=None,
                        reasoning_content="",
                    )
                )
            ],
        )


def test_gateway_fallback_and_cost_ledger():
    s = Settings(dashscope_api_key="sk-fakeunit1234567890abcdef")
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions()))
    ledger = CostLedger()
    gw = DashScopeLLMGateway(s, client=fake_client, ledger=ledger)

    result, rec = gw.generate_structured(
        "fast",
        [{"role": "user", "content": "完成 1 1.5h"}],
        IntentRoute,
    )
    assert result.intent == "checkin"
    assert rec.fallback_used is True
    assert rec.model == "qwen-plus"
    summary = ledger.summary()
    assert summary["calls"] == 3  # 2 primary attempts + 1 fallback success
    assert summary["failures"] == 2
    assert summary["fallbacks"] == 1
    assert summary["total_tokens"] == 32
