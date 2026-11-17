#!/usr/bin/env python3
"""Stage 2 Probe 1: Verify DashScope 3-tier heterogeneous models, tool calls, and Thinking output."""

from __future__ import annotations

import json
import sys

from wechat_assistant.config import DashScopeLLMGateway, Settings, assert_no_secrets_leaked
from wechat_assistant.schemas import CriticVerdict, IntentRoute, TriageProposal


def main() -> int:
    settings = Settings.load(require_bailian=True)
    gw = DashScopeLLMGateway(settings)

    # 1. Fast tier: Intent routing
    intent, rec1 = gw.generate_structured(
        "fast",
        [
            {"role": "system", "content": "你是董事长助理路由分类器。"},
            {"role": "user", "content": "帮我记一下，明后天要审完帕莫瑞技术协议并排工期，大概占我1.5小时。"},
        ],
        IntentRoute,
    )
    print(f"[PROBE-1 fast] model={rec1.model} latency={rec1.latency_ms}ms intent={intent.intent} conf={intent.confidence}")

    # 2. Producer tier: Thinking + Tool Call + Structured Proposal
    tool_called = {"count": 0}
    tools = [
        {
            "type": "function",
            "function": {
                "name": "check_workload_and_schedule",
                "description": "查询董事长未来几日已排净工时与可用容量，避免排期超载",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {"type": "string"},
                        "days": {"type": "integer"},
                    },
                    "required": ["start_date"],
                },
            },
        }
    ]

    def run_tool(name: str, args: dict) -> str:
        tool_called["count"] += 1
        return json.dumps(
            {
                "capacity_hours": 6.0,
                "days": {
                    "2026-11-18": {"booked_hours": 5.8, "status": "near_full"},
                    "2026-11-19": {"booked_hours": 2.5, "status": "available"},
                },
            },
            ensure_ascii=False,
        )

    proposal, rec2 = gw.generate_structured(
        "producer",
        [
            {"role": "system", "content": "你是董事长助理。必须先调用 check_workload_and_schedule 查负荷再给出排期建议。"},
            {"role": "user", "content": "2026-11-18起需要安排评审帕莫瑞20页技术协议，预计占我本人1.5小时，请给出建议排期决策卡。"},
        ],
        TriageProposal,
        tools=tools,
        tool_executor=run_tool,
        max_tokens=2048,
    )
    assert tool_called["count"] >= 1, "Producer failed to invoke schedule tool"
    assert len(proposal.actions) >= 1, "Producer returned empty actions"
    print(
        f"[PROBE-1 producer] model={rec2.model} latency={rec2.latency_ms}ms "
        f"tool_calls={tool_called['count']} actions={len(proposal.actions)} "
        f"start={proposal.actions[0].planned_start_at}"
    )

    # 3. Critic tier: Heterogeneous audit with deepseek-v4-pro
    verdict, rec3 = gw.generate_structured(
        "critic",
        [
            {"role": "system", "content": "你是严格核查数字保真与排期合理性的独立审计模型。"},
            {
                "role": "user",
                "content": (
                    f"原始请求：评审帕莫瑞20页技术协议，预计1.5小时；11-18已排5.8h(容量6.0h)，11-19已排2.5h。\n"
                    f"待审方案：{proposal.model_dump_json()}"
                ),
            },
        ],
        CriticVerdict,
        max_tokens=1536,
    )
    assert_no_secrets_leaked(proposal.model_dump_json() + verdict.model_dump_json(), settings)
    print(
        f"[PROBE-1 critic] model={rec3.model} latency={rec3.latency_ms}ms "
        f"passed={verdict.passed} numeric_ok={verdict.numeric_fidelity_ok} reasoning_tok={rec3.reasoning_tokens}"
    )
    print(f"[PROBE-1 ledger] {json.dumps(gw.ledger.summary())}")
    print("PROBE_01_ALL_PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"PROBE_01_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
