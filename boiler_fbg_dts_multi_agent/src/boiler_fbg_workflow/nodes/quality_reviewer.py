"""Quality Reviewer (QA) node - Independent quality assurance.

Design Pattern References:
- Chapter 4 (P65-78): Reflection pattern - Adversarial critic
- Chapter 13 (P204-212): HITL pattern - Gate decisions
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from boiler_fbg_workflow.config import RuntimeDeps
from boiler_fbg_workflow.schemas import (
    GateStatus,
    IssueSeverity,
    QAIssue,
    QAReviewResult,
    StageCode,
    WorkflowState,
)


def execute_qa_review(
    state: WorkflowState,
    stage: str,
    deps: RuntimeDeps,
) -> dict[str, Any]:
    """Execute QA review for a stage.
    
    Implements Chapter 4 Reflection pattern:
    - Independent reviewer role
    - Structured issue identification
    - Evidence verification
    - Gate decision logic
    """
    run_id = state.get("run_id", "unknown")
    review_id = f"QA-{stage}-{uuid.uuid4().hex[:8]}"
    
    # Collect artifacts to review based on stage
    artifacts = _collect_stage_artifacts(state, stage)
    
    # Perform review checks
    issues = []
    
    # Check 1: Evidence completeness
    evidence_issues = _check_evidence_completeness(artifacts, stage)
    issues.extend(evidence_issues)
    
    # Check 2: Required fields
    field_issues = _check_required_fields(artifacts, stage)
    issues.extend(field_issues)
    
    # Check 3: Safety constraints
    safety_issues = _check_safety_constraints(artifacts, stage)
    issues.extend(safety_issues)
    
    # Check 4: Pending items
    pending_issues = _check_pending_items(artifacts, stage)
    issues.extend(pending_issues)
    
    # Determine gate status
    critical_count = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
    major_count = sum(1 for i in issues if i.severity == IssueSeverity.MAJOR)
    
    if critical_count > 0:
        gate_status = GateStatus.BLOCKED
        requires_hitl = False
    elif major_count > deps.settings.max_major_issues:
        gate_status = GateStatus.HOLD
        requires_hitl = True
    elif major_count > 0:
        gate_status = GateStatus.CONDITIONAL_PASS
        requires_hitl = False
    else:
        gate_status = GateStatus.PASS
        requires_hitl = False
    
    # Build review result
    review = QAReviewResult(
        review_id=review_id,
        stage=StageCode(stage) if stage in [s.value for s in StageCode] else StageCode.STAGE_0_REQUIREMENTS,
        overall_assessment=_generate_assessment(issues, gate_status),
        issues=[
            QAIssue(
                issue_id=i.issue_id,
                stage=i.stage,
                role_source=i.role_source,
                severity=i.severity,
                title=i.title,
                description=i.description,
                required_action=i.required_action,
                assigned_to=i.assigned_to,
            )
            for i in issues
        ],
        gate_status=gate_status,
        requires_hitl=requires_hitl,
        hitl_reason="存在重大问题需人工决策" if requires_hitl else "",
        artifacts_reviewed=list(artifacts.keys()),
        evidence_ids=[f"[EV-REVIEW-{review_id}]"],
    )
    
    return {
        "qa_reviews": [review.model_dump()],
        "telemetry_events": [{
            "event": "qa_review_completed",
            "stage": stage,
            "gate_status": gate_status.value,
            "issues_count": len(issues),
            "critical_count": critical_count,
            "major_count": major_count,
        }],
    }


def execute_system_testing(state: WorkflowState, deps: RuntimeDeps) -> dict[str, Any]:
    """Execute system-level testing.
    
    In simulation mode, returns template test results.
    """
    if deps.is_simulation:
        return {
            "results": [
                {
                    "test_id": "SYS-TEST-001",
                    "name": "端到端数据流测试",
                    "type": "integration",
                    "status": "passed",
                    "data_source": "synthetic",
                    "notes": "[SIMULATION] 使用合成数据验证数据流",
                },
                {
                    "test_id": "SYS-TEST-002",
                    "name": "告警逻辑测试",
                    "type": "functional",
                    "status": "passed",
                    "data_source": "synthetic",
                    "notes": "[SIMULATION] 验证超温/异常检测逻辑",
                },
                {
                    "test_id": "SYS-TEST-003",
                    "name": "安全约束验证",
                    "type": "safety",
                    "status": "passed",
                    "notes": "[SIMULATION] 验证系统无控制输出能力",
                },
            ],
        }
    
    # Live mode would execute actual tests
    return {"results": []}


class _QAIssue:
    """Internal issue representation."""
    def __init__(
        self,
        issue_id: str,
        stage: str,
        severity: IssueSeverity,
        title: str,
        description: str,
        required_action: str,
        assigned_to: str,
    ):
        from boiler_fbg_workflow.schemas import RoleCode
        self.issue_id = issue_id
        self.stage = StageCode(stage) if stage in [s.value for s in StageCode] else StageCode.STAGE_0_REQUIREMENTS
        self.role_source = RoleCode.QA
        self.severity = severity
        self.title = title
        self.description = description
        self.required_action = required_action
        self.assigned_to = RoleCode(assigned_to) if assigned_to in [r.value for r in RoleCode] else RoleCode.PM


def _collect_stage_artifacts(state: WorkflowState, stage: str) -> dict[str, Any]:
    """Collect artifacts for review based on stage."""
    artifacts = {}
    
    if stage == "stage_0_requirements":
        artifacts["market_segments"] = state.get("market_segments", [])
        artifacts["market_sizing"] = state.get("market_sizing", [])
        artifacts["competitors"] = state.get("competitors", [])
        artifacts["requirements"] = state.get("requirements", [])
    elif stage == "stage_1_concept":
        artifacts["tech_route_analysis"] = state.get("tech_route_analysis", {})
        artifacts["sensor_specs"] = state.get("sensor_specs", [])
        artifacts["system_architecture"] = state.get("system_architecture", {})
        artifacts["software_architecture"] = state.get("software_architecture", {})
    elif stage == "stage_2_detailed_design":
        artifacts["detailed_optical_design"] = state.get("detailed_optical_design", {})
        artifacts["detailed_hw_design"] = state.get("detailed_hw_design", {})
        artifacts["bom_items"] = state.get("bom_items", [])
        artifacts["cost_breakdown"] = state.get("cost_breakdown", {})
    
    return artifacts


def _check_evidence_completeness(artifacts: dict, stage: str) -> list[_QAIssue]:
    """Check that all items have evidence references."""
    issues = []
    
    for key, value in artifacts.items():
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    evidence_ids = item.get("evidence_ids", [])
                    if not evidence_ids:
                        issues.append(_QAIssue(
                            issue_id=f"EV-{stage}-{key}-{i}",
                            stage=stage,
                            severity=IssueSeverity.MINOR,
                            title=f"缺少证据引用: {key}[{i}]",
                            description=f"{key}的第{i+1}项缺少evidence_ids",
                            required_action="补充数据来源或标记为[EV-UNKNOWN]",
                            assigned_to=_get_responsible_role(key),
                        ))
                    # Check for too many UNKNOWN evidence
                    unknown_count = sum(1 for e in evidence_ids if "UNKNOWN" in e)
                    if unknown_count > 0 and unknown_count == len(evidence_ids):
                        issues.append(_QAIssue(
                            issue_id=f"EV-UNK-{stage}-{key}-{i}",
                            stage=stage,
                            severity=IssueSeverity.MAJOR,
                            title=f"全部为未验证证据: {key}[{i}]",
                            description=f"{key}的第{i+1}项所有证据都是[EV-UNKNOWN]",
                            required_action="需补充实际数据来源或标明待外部注入",
                            assigned_to=_get_responsible_role(key),
                        ))
        elif isinstance(value, dict):
            evidence_ids = value.get("evidence_ids", [])
            if not evidence_ids and key not in ["cost_breakdown"]:
                issues.append(_QAIssue(
                    issue_id=f"EV-{stage}-{key}",
                    stage=stage,
                    severity=IssueSeverity.MINOR,
                    title=f"缺少证据引用: {key}",
                    description=f"{key}缺少evidence_ids",
                    required_action="补充数据来源",
                    assigned_to=_get_responsible_role(key),
                ))
    
    return issues


def _check_required_fields(artifacts: dict, stage: str) -> list[_QAIssue]:
    """Check required fields are present and valid."""
    issues = []
    
    # Stage-specific required field checks
    if stage == "stage_0_requirements":
        if not artifacts.get("requirements"):
            issues.append(_QAIssue(
                issue_id=f"REQ-{stage}-001",
                stage=stage,
                severity=IssueSeverity.CRITICAL,
                title="缺少技术需求定义",
                description="requirements列表为空",
                required_action="定义核心技术需求",
                assigned_to="opt",
            ))
    
    elif stage == "stage_2_detailed_design":
        bom_items = artifacts.get("bom_items", [])
        pending_count = sum(1 for item in bom_items if item.get("status") == "pending_quote")
        if pending_count == len(bom_items) and bom_items:
            issues.append(_QAIssue(
                issue_id=f"BOM-{stage}-001",
                stage=stage,
                severity=IssueSeverity.MAJOR,
                title="BOM全部待报价",
                description=f"所有{len(bom_items)}项BOM都是pending_quote状态",
                required_action="启动供应商询价流程",
                assigned_to="scm",
            ))
    
    return issues


def _check_safety_constraints(artifacts: dict, stage: str) -> list[_QAIssue]:
    """Check safety-related constraints."""
    issues = []
    
    # Check software architecture for control isolation
    if stage == "stage_1_concept":
        sw_arch = artifacts.get("software_architecture", {})
        ai_constraints = sw_arch.get("ai_constraints", "")
        
        if "人工决策" not in ai_constraints and "监测" not in ai_constraints:
            issues.append(_QAIssue(
                issue_id=f"SAFETY-{stage}-001",
                stage=stage,
                severity=IssueSeverity.CRITICAL,
                title="AI约束未明确声明",
                description="软件架构未明确声明AI仅用于监测/预警，不直接控制",
                required_action="在架构中明确声明安全约束",
                assigned_to="sw",
            ))
        
        sys_arch = artifacts.get("system_architecture", {})
        if "只读" not in str(sys_arch.get("interfaces", {})):
            issues.append(_QAIssue(
                issue_id=f"SAFETY-{stage}-002",
                stage=stage,
                severity=IssueSeverity.MAJOR,
                title="DCS接口未声明只读",
                description="系统架构未明确DCS接口为只读模式",
                required_action="明确所有外部接口为只读/单向",
                assigned_to="hw",
            ))
    
    return issues


def _check_pending_items(artifacts: dict, stage: str) -> list[_QAIssue]:
    """Check for items marked as pending verification."""
    issues = []
    
    if stage == "stage_1_concept":
        sensor_specs = artifacts.get("sensor_specs", [])
        for i, spec in enumerate(sensor_specs):
            pending = spec.get("pending_verification", [])
            if "max_temperature_c" in str(pending).lower():
                issues.append(_QAIssue(
                    issue_id=f"PEND-{stage}-TEMP-{i}",
                    stage=stage,
                    severity=IssueSeverity.MAJOR,
                    title=f"高温规格待验证: 传感器{i+1}",
                    description="max_temperature_c需原厂确认",
                    required_action="获取供应商数据表确认高温工作范围",
                    assigned_to="opt",
                ))
    
    return issues


def _get_responsible_role(artifact_key: str) -> str:
    """Get responsible role for an artifact."""
    role_mapping = {
        "market_segments": "mkt",
        "market_sizing": "mkt",
        "competitors": "mkt",
        "requirements": "opt",
        "tech_route_analysis": "opt",
        "sensor_specs": "opt",
        "system_architecture": "hw",
        "software_architecture": "sw",
        "detailed_optical_design": "opt",
        "detailed_hw_design": "hw",
        "bom_items": "hw",
        "cost_breakdown": "fin",
        "supplier_analysis": "scm",
    }
    return role_mapping.get(artifact_key, "pm")


def _generate_assessment(issues: list[_QAIssue], gate_status: GateStatus) -> str:
    """Generate overall assessment text."""
    critical = sum(1 for i in issues if i.severity == IssueSeverity.CRITICAL)
    major = sum(1 for i in issues if i.severity == IssueSeverity.MAJOR)
    minor = sum(1 for i in issues if i.severity == IssueSeverity.MINOR)
    
    status_text = {
        GateStatus.PASS: "审查通过",
        GateStatus.CONDITIONAL_PASS: "条件通过",
        GateStatus.HOLD: "暂停等待人工决策",
        GateStatus.BLOCKED: "阻塞，需返工",
        GateStatus.PENDING_HITL: "等待人工审批",
    }
    
    return (
        f"{status_text.get(gate_status, '未知状态')}。"
        f"发现问题: {critical}个严重、{major}个重要、{minor}个次要。"
    )
