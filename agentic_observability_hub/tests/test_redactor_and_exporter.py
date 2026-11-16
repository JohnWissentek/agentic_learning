"""Unit tests for SecretRedactor, Dual-Stack OTel attributes, LiveStore & FastAPI Live Canvas."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from obs_hub.config import ObsHubSettings, SecretRedactor
from obs_hub.dual_exporter import DualStackTelemetryExporter, NodeSpanRecord, build_dual_span_attributes
from obs_hub.live_canvas_server import create_app


def test_secret_redactor_scrubs_keys() -> None:
    redactor = SecretRedactor(secrets=["my_super_secret_dashscope_key_12345"])
    raw = "Authorization: Bearer abcdefghijklmnopqrstuvwx | key=my_super_secret_dashscope_key_12345 | sk-1234567890abcdefghij"
    clean = redactor.redact(raw)
    assert "my_super_secret_dashscope_key_12345" not in clean
    assert "abcdefghijklmnopqrstuvwx" not in clean
    assert "sk-1234567890abcdefghij" not in clean
    assert "[REDACTED_SECRET]" in clean


def test_dual_span_attributes_contain_both_langfuse_and_phoenix_keys() -> None:
    ev = NodeSpanRecord(
        run_id="run-123",
        node_id="s0_pm",
        stage_label="Stage 0",
        role_title="Chief PM",
        span_kind="generation",
        model_name="qwen3.8-max",
        system_prompt="You are Chief PM",
        user_prompt="Plan 6 boiler tracks",
        output_text='{"tracks": 6}',
        prompt_tokens=120,
        completion_tokens=45,
    )
    attrs = build_dual_span_attributes(ev, redactor=SecretRedactor(), step_idx=1)
    assert attrs["langfuse.observation.type"] == "generation"
    assert attrs["langfuse.observation.metadata.langgraph_node"] == "s0_pm"
    assert attrs["openinference.span.kind"] == "LLM"
    assert attrs["llm.model_name"] == "qwen3.8-max"
    assert attrs["llm.token_count.prompt"] == 120


def test_live_canvas_and_sqlite_roundtrip(tmp_path: Path) -> None:
    base = Path(__file__).resolve().parents[1]
    settings = ObsHubSettings.load(base)
    settings.sqlite_path = tmp_path / "test_live.db"

    exp = DualStackTelemetryExporter(settings, redactor=SecretRedactor())
    try:
        out = exp.emit_workflow_run(
            run_id="test-run-01",
            workflow_name="BoilerSense-AI-IPD",
            engine_mode="pytest",
            events=[
                NodeSpanRecord(
                    run_id="test-run-01",
                    node_id="t3",
                    stage_label="Stage 1",
                    role_title="Optics Architect",
                    user_prompt="Check Ibsen I-MON 512",
                    output_text="Selected",
                )
            ],
            push_otlp=False,
        )
        assert out["events_count"] == 1
    finally:
        exp.close()

    app = create_app(settings)
    client = TestClient(app)
    r_topo = client.get("/api/topology")
    assert r_topo.status_code == 200
    assert len(r_topo.json()["nodes"]) >= 20

    r_runs = client.get("/api/runs")
    assert r_runs.status_code == 200
    assert r_runs.json()[0]["run_id"] == "test-run-01"

    r_detail = client.get("/api/runs/test-run-01")
    assert r_detail.status_code == 200
    assert r_detail.json()["events"][0]["node_id"] == "t3"
