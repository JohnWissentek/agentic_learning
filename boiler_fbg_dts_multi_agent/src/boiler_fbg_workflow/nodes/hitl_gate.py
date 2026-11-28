"""Human-in-the-Loop (HITL) gate node.

Design Pattern Reference:
- Chapter 13 (P204-212): Human-in-the-Loop pattern
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from boiler_fbg_workflow.config import RuntimeDeps
from boiler_fbg_workflow.schemas import HITLDecision, WorkflowState


def execute_hitl_gate(
    state: WorkflowState,
    gate_type: str,
    deps: RuntimeDeps,
) -> dict[str, Any]:
    """Execute HITL gate - request human decision.
    
    In simulation mode, auto-approves with disclaimer.
    In live mode, would interrupt workflow for human input.
    
    Reference: Chapter 13 (P204-212)
    - Strategic integration of human judgment
    - Approval checkpoints for high-risk decisions
    - Escalation policies
    """
    run_id = state.get("run_id", "unknown")
    decision_id = f"HITL-{gate_type}-{uuid.uuid4().hex[:8]}"
    
    # Determine stage from gate type
    stage_mapping = {
        "requirement_approval": "stage_0_requirements",
        "design_approval": "stage_1_concept",
        "procurement_approval": "stage_2_detailed_design",
        "test_approval": "stage_4_testing",
        "launch_approval": "stage_5_production",
    }
    stage = stage_mapping.get(gate_type, "unknown")
    
    # Get context for decision
    context = _build_decision_context(state, gate_type)
    
    if deps.is_simulation:
        # Auto-approve in simulation with clear marking
        decision = HITLDecision(
            decision_id=decision_id,
            stage=stage,
            gate_type=gate_type,
            request_summary=context["summary"],
            options_presented=["approve", "reject", "defer", "modify"],
            decision="approve",
            decision_rationale=(
                "[SIMULATION] 模拟模式自动批准。"
                "实际运行时，此处需人工审核并做出决策。"
                "人工操作员应审查以下内容后决定：\n"
                f"{context['review_items']}"
            ),
            decided_by="[SIMULATION_AUTO]",
            conditions=[
                "实际运行需人工确认",
                "所有[EV-UNKNOWN]证据需验证后方可进入下一阶段",
            ],
            evidence_ids=[f"[EV-SYNTH-HITL-{decision_id}]"],
        )
    else:
        # Live mode: create pending decision
        # In a real system, this would interrupt and wait for human input
        decision = HITLDecision(
            decision_id=decision_id,
            stage=stage,
            gate_type=gate_type,
            request_summary=context["summary"],
            options_presented=["approve", "reject", "defer", "modify"],
            decision="defer",  # Default to defer until human decides
            decision_rationale="等待人工决策",
            decided_by="[PENDING_HUMAN_INPUT]",
            conditions=[],
            evidence_ids=[],
        )
    
    return {
        "hitl_decisions": [decision.model_dump()],
        "telemetry_events": [{
            "event": "hitl_gate_executed",
            "gate_type": gate_type,
            "decision": decision.decision,
            "mode": state.get("mode", "unknown"),
            "timestamp": datetime.now().isoformat(),
        }],
    }


def _build_decision_context(state: WorkflowState, gate_type: str) -> dict[str, str]:
    """Build context information for HITL decision."""
    
    contexts = {
        "requirement_approval": {
            "summary": "需求分析与市场研究阶段完成，请审核并批准进入概念设计阶段",
            "review_items": "\n".join([
                "1. 市场细分定义是否合理",
                "2. 市场规模计算假设是否可接受",
                "3. 竞品分析是否充分",
                "4. 技术需求是否完整",
                "5. 推荐首发场景是否合适",
            ]),
        },
        "design_approval": {
            "summary": "概念设计阶段完成，请审核并批准进入详细设计阶段",
            "review_items": "\n".join([
                "1. 技术路线选择（FBG/DTS）是否合理",
                "2. 传感器规格是否满足需求",
                "3. 系统架构是否可行",
                "4. 安全约束是否明确",
                "5. 待验证技术项是否可接受",
            ]),
        },
        "procurement_approval": {
            "summary": "详细设计阶段完成，请审核BOM并批准启动采购",
            "review_items": "\n".join([
                "1. BOM清单是否完整",
                "2. 供应商选择是否合理",
                "3. 成本预算是否可接受",
                "4. 交期是否满足项目计划",
                "5. 是否有HOLD项需要放行",
            ]),
        },
        "test_approval": {
            "summary": "系统测试阶段完成，请审核测试结果并批准进入生产导入",
            "review_items": "\n".join([
                "1. 测试覆盖是否充分",
                "2. 测试结果是否达标",
                "3. 遗留问题是否可接受",
                "4. 安全验证是否通过",
                "5. 是否准备好进入生产",
            ]),
        },
        "launch_approval": {
            "summary": "生产导入阶段完成，请审核并批准产品上市",
            "review_items": "\n".join([
                "1. 生产准备是否就绪",
                "2. 培训材料是否完整",
                "3. 销售工具是否就绪",
                "4. 营销策略是否明确",
                "5. 风险登记是否已审核",
            ]),
        },
    }
    
    return contexts.get(gate_type, {
        "summary": f"请审核 {gate_type} 并做出决策",
        "review_items": "详细审核项待定义",
    })
