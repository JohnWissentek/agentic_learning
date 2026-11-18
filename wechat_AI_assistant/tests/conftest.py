"""Shared pytest fixtures."""

import pytest

from wechat_assistant.graph import ChiefOfStaffEngine


@pytest.fixture(autouse=True)
def _disable_semantic_summaries(monkeypatch):
    """Keep scripted LLM call sequences deterministic: no background summary calls in tests.

    Tests that exercise the semantic summary re-enable it on their own engine instance.
    """
    monkeypatch.setattr(ChiefOfStaffEngine, "semantic_summaries", False)
    yield
