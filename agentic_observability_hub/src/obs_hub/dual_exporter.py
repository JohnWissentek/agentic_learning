"""Dual-Stack OpenTelemetry Fanout Exporter (Langfuse v3 + Arize Phoenix + Local Live Canvas)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from opentelemetry.trace import SpanKind, set_span_in_context
from pydantic import BaseModel, Field

from obs_hub.config import ObsHubSettings, SecretRedactor

MAX_OTEL_ATTR_CHARS = 80_000


class NodeSpanRecord(BaseModel):
    """Normalized execution event emitted by either LangGraph or Antigravity run_workflow."""

    run_id: str
    workflow_name: str = "BoilerSense-AI-IPD"
    node_id: str
    stage_label: str
    role_title: str
    span_kind: str = "generation"  # agent | generation | tool | chain
    status: str = "DONE"  # PENDING | RUNNING | DONE | RETRY | ERROR
    model_name: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    thinking: str = ""
    output_text: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    started_at_ns: int = 0
    ended_at_ns: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class LiveStore:
    """Thread-safe local SQLite store backing the :8765 Live Topology & Context Studio."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                workflow_name TEXT NOT NULL,
                trace_id_hex TEXT NOT NULL,
                engine_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                summary_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS node_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                span_id_hex TEXT NOT NULL,
                stage_label TEXT NOT NULL,
                role_title TEXT NOT NULL,
                span_kind TEXT NOT NULL,
                status TEXT NOT NULL,
                model_name TEXT NOT NULL DEFAULT '',
                system_prompt TEXT NOT NULL DEFAULT '',
                user_prompt TEXT NOT NULL DEFAULT '',
                thinking TEXT NOT NULL DEFAULT '',
                output_text TEXT NOT NULL DEFAULT '',
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                seq_order INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def upsert_run(
        self,
        *,
        run_id: str,
        workflow_name: str,
        trace_id_hex: str,
        engine_mode: str,
        status: str,
        summary: dict[str, Any] | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO runs (run_id, workflow_name, trace_id_hex, engine_mode, status, created_at, summary_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                status=excluded.status,
                trace_id_hex=excluded.trace_id_hex,
                summary_json=excluded.summary_json
            """,
            (
                run_id,
                workflow_name,
                trace_id_hex,
                engine_mode,
                status,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(summary or {}, ensure_ascii=False),
            ),
        )
        self._conn.commit()

    def clear_run_events(self, run_id: str) -> None:
        self._conn.execute("DELETE FROM node_events WHERE run_id = ?", (run_id,))
        self._conn.commit()

    def insert_event(self, ev: NodeSpanRecord, *, span_id_hex: str, seq_order: int) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO node_events (
                run_id, node_id, span_id_hex, stage_label, role_title, span_kind, status,
                model_name, system_prompt, user_prompt, thinking, output_text,
                prompt_tokens, completion_tokens, latency_ms, seq_order, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ev.run_id,
                ev.node_id,
                span_id_hex,
                ev.stage_label,
                ev.role_title,
                ev.span_kind,
                ev.status,
                ev.model_name,
                ev.system_prompt,
                ev.user_prompt,
                ev.thinking,
                ev.output_text,
                ev.prompt_tokens,
                ev.completion_tokens,
                ev.latency_ms,
                seq_order,
                json.dumps(ev.metadata, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def list_runs(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["summary"] = json.loads(d.pop("summary_json", "{}"))
            out.append(d)
        return out

    def get_run_events(self, run_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM node_events WHERE run_id = ? ORDER BY seq_order ASC, id ASC", (run_id,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
            out.append(d)
        return out


class FixedTraceIdGenerator(RandomIdGenerator):
    """Allows deterministic trace_id assignment so Langfuse, Phoenix & Live Canvas share the same ID."""

    def __init__(self, trace_id_int: int) -> None:
        super().__init__()
        self.trace_id_int = trace_id_int

    def generate_trace_id(self) -> int:
        return self.trace_id_int


def _clip(text: str, limit: int = MAX_OTEL_ATTR_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 40] + "\n... [TRUNCATED IN OTLP; FULL IN :8765]"


def build_dual_span_attributes(
    ev: NodeSpanRecord, *, redactor: SecretRedactor, step_idx: int
) -> dict[str, Any]:
    """Build unified OpenTelemetry attributes compatible with BOTH Langfuse v3 & Arize Phoenix."""
    sys_p = redactor.redact(ev.system_prompt)
    usr_p = redactor.redact(ev.user_prompt)
    think_p = redactor.redact(ev.thinking)
    out_p = redactor.redact(ev.output_text)

    combined_input = usr_p if not sys_p else f"[SYSTEM]\n{sys_p}\n\n[USER / CONTEXT]\n{usr_p}"
    oi_kind = {
        "agent": "AGENT",
        "generation": "LLM",
        "tool": "TOOL",
        "chain": "CHAIN",
    }.get(ev.span_kind.lower(), "CHAIN")
    lf_type = {
        "agent": "agent",
        "generation": "generation",
        "tool": "tool",
        "chain": "chain",
    }.get(ev.span_kind.lower(), "span")

    attrs: dict[str, Any] = {
        # Shared topology & LangGraph graph hints
        "langgraph.node": ev.node_id,
        "langgraph.step": step_idx,
        "graph.node.id": ev.node_id,
        "langfuse.observation.type": lf_type,
        "langfuse.observation.metadata.langgraph_node": ev.node_id,
        "langfuse.observation.metadata.langgraph_step": step_idx,
        "langfuse.observation.metadata.stage": ev.stage_label,
        "langfuse.observation.metadata.role": ev.role_title,
        "langfuse.observation.input": _clip(combined_input),
        "langfuse.observation.output": _clip(out_p),
        "langfuse.trace.name": f"{ev.workflow_name} ({ev.run_id})",
        # OpenInference attributes for Arize Phoenix
        "openinference.span.kind": oi_kind,
        "input.value": _clip(combined_input),
        "output.value": _clip(out_p),
        "llm.input_messages.0.message.role": "system",
        "llm.input_messages.0.message.content": _clip(sys_p or ev.role_title),
        "llm.input_messages.1.message.role": "user",
        "llm.input_messages.1.message.content": _clip(usr_p),
        "llm.output_messages.0.message.role": "assistant",
        "llm.output_messages.0.message.content": _clip(out_p),
    }
    if ev.model_name:
        attrs["gen_ai.request.model"] = ev.model_name
        attrs["langfuse.observation.model.name"] = ev.model_name
        attrs["llm.model_name"] = ev.model_name
    if ev.prompt_tokens:
        attrs["gen_ai.usage.input_tokens"] = ev.prompt_tokens
        attrs["llm.token_count.prompt"] = ev.prompt_tokens
    if ev.completion_tokens:
        attrs["gen_ai.usage.output_tokens"] = ev.completion_tokens
        attrs["llm.token_count.completion"] = ev.completion_tokens
    if think_p:
        attrs["langfuse.observation.metadata.thinking"] = _clip(think_p, 24_000)
    for k, v in ev.metadata.items():
        if isinstance(v, (str, int, float, bool)):
            attrs[f"langfuse.observation.metadata.{k}"] = v
    return attrs


class DualStackTelemetryExporter:
    """Exports identical traces simultaneously to Langfuse v3 (:3000), Arize Phoenix (:6006), and Live SQLite."""

    def __init__(self, settings: ObsHubSettings, redactor: SecretRedactor | None = None) -> None:
        self.settings = settings
        self.redactor = redactor or SecretRedactor.from_workspace(settings.workspace_root)
        self.store = LiveStore(settings.sqlite_path)

    def close(self) -> None:
        self.store.close()

    def _is_endpoint_alive(self, url: str) -> bool:
        try:
            with httpx.Client(timeout=1.5) as c:
                base = "/".join(url.split("/")[:3])
                resp = c.get(base)
                return resp.status_code < 500
        except Exception:
            return False

    def emit_workflow_run(
        self,
        *,
        run_id: str,
        workflow_name: str,
        engine_mode: str,
        events: list[NodeSpanRecord],
        summary: dict[str, Any] | None = None,
        push_otlp: bool = True,
    ) -> dict[str, Any]:
        """Persist full unclipped events to SQLite and export unified OTel trace to Scheme B & Scheme A."""
        # Deterministic 128-bit trace_id from run_id
        import hashlib

        trace_id_hex = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:32]
        trace_id_int = int(trace_id_hex, 16)

        self.store.upsert_run(
            run_id=run_id,
            workflow_name=workflow_name,
            trace_id_hex=trace_id_hex,
            engine_mode=engine_mode,
            status="DONE",
            summary=summary,
        )
        self.store.clear_run_events(run_id)

        redacted_events: list[NodeSpanRecord] = []
        for idx, ev in enumerate(events):
            clean = ev.model_copy(
                update={
                    "system_prompt": self.redactor.redact(ev.system_prompt),
                    "user_prompt": self.redactor.redact(ev.user_prompt),
                    "thinking": self.redactor.redact(ev.thinking),
                    "output_text": self.redactor.redact(ev.output_text),
                }
            )
            redacted_events.append(clean)

        otlp_results = {"langfuse": "skipped", "phoenix": "skipped"}
        span_ids: list[str] = []

        if push_otlp and redacted_events:
            resource = Resource.create(
                {
                    "service.name": workflow_name,
                    "service.version": "1.0.0",
                    "deployment.environment": "orbstack-local",
                }
            )
            provider = TracerProvider(
                resource=resource,
                id_generator=FixedTraceIdGenerator(trace_id_int),
            )
            lf_up = self._is_endpoint_alive(self.settings.langfuse_otlp_endpoint)
            ph_up = self._is_endpoint_alive(self.settings.phoenix_otlp_endpoint)

            if lf_up:
                lf_exp = OTLPSpanExporter(
                    endpoint=self.settings.langfuse_otlp_endpoint,
                    headers={"Authorization": f"Basic {self.settings.langfuse_basic_auth}"},
                    timeout=15,
                )
                provider.add_span_processor(SimpleSpanProcessor(lf_exp))
                otlp_results["langfuse"] = "exported"

            if ph_up:
                ph_exp = OTLPSpanExporter(
                    endpoint=self.settings.phoenix_otlp_endpoint,
                    timeout=15,
                )
                provider.add_span_processor(BatchSpanProcessor(ph_exp))
                otlp_results["phoenix"] = "exported"

            tracer = provider.get_tracer("obs_hub.dual_exporter")
            min_start = min(e.started_at_ns for e in redacted_events if e.started_at_ns > 0) or 1_763_260_000_000_000_000
            max_end = max(e.ended_at_ns for e in redacted_events if e.ended_at_ns > 0) or (min_start + 10_000_000_000)

            root_span = tracer.start_span(
                name=f"{workflow_name} ({run_id})",
                kind=SpanKind.INTERNAL,
                start_time=min_start,
                attributes={
                    "openinference.span.kind": "CHAIN",
                    "langfuse.trace.name": f"{workflow_name} ({run_id})",
                    "langfuse.observation.type": "chain",
                    "langfuse.observation.input": f"Run {run_id} ({engine_mode}), nodes={len(redacted_events)}",
                    "langfuse.observation.output": json.dumps(summary or {}, ensure_ascii=False),
                    "input.value": f"Run {run_id} ({engine_mode}), nodes={len(redacted_events)}",
                    "output.value": json.dumps(summary or {}, ensure_ascii=False),
                },
            )
            root_ctx = set_span_in_context(root_span)

            for idx, ev in enumerate(redacted_events):
                attrs = build_dual_span_attributes(ev, redactor=self.redactor, step_idx=idx + 1)
                s_start = ev.started_at_ns or (min_start + idx * 100_000_000)
                s_end = ev.ended_at_ns or (s_start + max(10_000_000, ev.latency_ms * 1_000_000))
                if s_end <= s_start:
                    s_end = s_start + 50_000_000
                child = tracer.start_span(
                    name=f"{ev.node_id}: {ev.role_title}",
                    context=root_ctx,
                    kind=SpanKind.CLIENT if ev.span_kind == "generation" else SpanKind.INTERNAL,
                    start_time=s_start,
                    attributes=attrs,
                )
                child.end(end_time=s_end)
                span_ids.append(f"{child.get_span_context().span_id:016x}")

            root_span.end(end_time=max(max_end, min_start + 1_000_000_000))
            provider.force_flush(timeout_millis=15_000)
            provider.shutdown()
        else:
            span_ids = [f"{idx + 1:016x}" for idx in range(len(redacted_events))]

        for idx, (ev, sid) in enumerate(zip(redacted_events, span_ids)):
            self.store.insert_event(ev, span_id_hex=sid, seq_order=idx + 1)

        return {
            "run_id": run_id,
            "trace_id_hex": trace_id_hex,
            "events_count": len(redacted_events),
            "otlp_status": otlp_results,
            "langfuse_trace_url": f"{self.settings.langfuse_web_url}/project/{self.settings.langfuse_project_id}/traces/{trace_id_hex}",
            "phoenix_url": self.settings.phoenix_web_url,
            "live_canvas_url": f"{self.settings.live_canvas_url}/?run_id={run_id}",
        }
