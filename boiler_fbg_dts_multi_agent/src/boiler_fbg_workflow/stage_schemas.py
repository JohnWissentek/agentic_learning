"""Stage-Specific Schemas - Each stage has its own contract.

RUN-04 Fix: PM and PM_REWORK have different schemas.
Prompt and validator must use the same schema.
"""

from __future__ import annotations
from typing import Any
from dataclasses import dataclass


@dataclass
class StageSchema:
    """Schema definition for a stage."""
    schema_id: str
    schema_version: str
    required_fields: list[str]
    field_types: dict[str, type]
    description: str


# Schema registry - version controlled
STAGE_SCHEMAS = {
    "TEST": StageSchema(
        schema_id="TEST_v1",
        schema_version="1.0.0",
        required_fields=["test", "version"],
        field_types={"test": str, "version": str},
        description="测试样本schema",
    ),
    
    "MKT": StageSchema(
        schema_id="MKT_v1",
        schema_version="1.0.0",
        required_fields=["market_size", "competitors", "pain_points", "entry_risks"],
        field_types={
            "market_size": str,
            "competitors": (list, str),
            "pain_points": (list, str),
            "entry_risks": (list, str),
        },
        description="市场分析schema - 所有事实需source_id",
    ),
    
    "OPT": StageSchema(
        schema_id="OPT_v1",
        schema_version="1.0.0",
        required_fields=["fwhm_analysis", "wavelength_budget", "uncertainty_status"],
        field_types={
            "fwhm_analysis": str,
            "wavelength_budget": str,
            "uncertainty_status": str,
        },
        description="光学/热工分析schema",
    ),
    
    "HW": StageSchema(
        schema_id="HW_v1",
        schema_version="1.0.0",
        required_fields=["thermal_design", "link_margin_impact", "integration_risks"],
        field_types={
            "thermal_design": str,
            "link_margin_impact": str,
            "integration_risks": (list, str),
        },
        description="硬件设计schema",
    ),
    
    "SW": StageSchema(
        schema_id="SW_v1",
        schema_version="1.0.0",
        required_fields=["blind_window_stats", "data_flow", "ai_isolation"],
        field_types={
            "blind_window_stats": str,
            "data_flow": str,
            "ai_isolation": str,
        },
        description="软件架构schema",
    ),
    
    "SCM": StageSchema(
        schema_id="SCM_v1",
        schema_version="1.0.0",
        required_fields=["available_vendors", "blocking_items", "funding_uncertainty"],
        field_types={
            "available_vendors": (list, str),
            "blocking_items": (list, str),
            "funding_uncertainty": str,
        },
        description="供应链分析schema",
    ),
    
    "MFG": StageSchema(
        schema_id="MFG_v1",
        schema_version="1.0.0",
        required_fields=["npi_blockers", "prerequisites", "test_checklist"],
        field_types={
            "npi_blockers": (list, str),
            "prerequisites": (list, str),
            "test_checklist": (list, str),
        },
        description="NPI就绪schema",
    ),
    
    "TRN": StageSchema(
        schema_id="TRN_v1",
        schema_version="1.0.0",
        required_fields=["training_modules", "safety_points", "certifications"],
        field_types={
            "training_modules": (list, str),
            "safety_points": (list, str),
            "certifications": (list, str),
        },
        description="培训需求schema",
    ),
    
    "FIN": StageSchema(
        schema_id="FIN_v1",
        schema_version="1.0.0",
        required_fields=["funding_gaps", "stage_risks", "competitiveness_status"],
        field_types={
            "funding_gaps": (list, str),
            "stage_risks": (list, str),
            "competitiveness_status": str,
        },
        description="财务分析schema - stage_risks不可为空列表",
    ),
    
    "SLS": StageSchema(
        schema_id="SLS_v1",
        schema_version="1.0.0",
        required_fields=["available_materials", "forbidden_claims", "required_disclosures"],
        field_types={
            "available_materials": (list, str),
            "forbidden_claims": (list, str),
            "required_disclosures": (list, str),  # RUN-02: 真实限制应在这里
        },
        description="销售策略schema - required_disclosures必须包含真实限制",
    ),
    
    "QA": StageSchema(
        schema_id="QA_v1",
        schema_version="1.0.0",
        required_fields=["rework_required", "doc_vs_engineering", "evidence_gaps", "gate_decision"],
        field_types={
            "rework_required": list,
            "doc_vs_engineering": str,
            "evidence_gaps": (list, str),
            "gate_decision": str,
        },
        description="质量审查schema",
    ),
    
    # RUN-04 Fix: PM and PM_REWORK have DIFFERENT schemas
    "PM": StageSchema(
        schema_id="PM_SYNTHESIS_v1",
        schema_version="1.0.0",
        required_fields=["output_summary", "rework_items", "action_plan"],
        field_types={
            "output_summary": (dict, str),
            "rework_items": list,
            "action_plan": str,
        },
        description="PM综合schema",
    ),
    
    "PM_REWORK": StageSchema(
        schema_id="PM_REWORK_v1",
        schema_version="1.0.0",
        required_fields=["trigger_output", "trigger_reason", "correction_actions", "needs_reqa"],
        field_types={
            "trigger_output": str,
            "trigger_reason": str,
            "correction_actions": (list, str),
            "needs_reqa": bool,
        },
        description="PM返工schema - 与PM不同！",
    ),
    
    "STR": StageSchema(
        schema_id="STR_v1",
        schema_version="1.0.0",
        required_fields=["current_phase", "milestones", "go_nogo_points"],
        field_types={
            "current_phase": str,
            "milestones": (list, str),
            "go_nogo_points": (list, str),
        },
        description="战略分析schema",
    ),
}


def get_schema(stage: str) -> StageSchema:
    """Get schema for stage."""
    if stage not in STAGE_SCHEMAS:
        raise ValueError(f"Unknown stage: {stage}. Available: {list(STAGE_SCHEMAS.keys())}")
    return STAGE_SCHEMAS[stage]


def validate_against_schema(
    parsed: dict[str, Any],
    stage: str,
) -> tuple[bool, list[str]]:
    """Validate parsed output against stage schema.
    
    Returns (is_valid, issues)
    """
    schema = get_schema(stage)
    issues = []
    
    # Check required fields
    for field in schema.required_fields:
        if field not in parsed:
            issues.append(f"[{schema.schema_id}] 缺少必需字段: {field}")
        elif parsed[field] is None:
            issues.append(f"[{schema.schema_id}] 字段{field}为null")
        elif isinstance(parsed[field], list) and len(parsed[field]) == 0:
            # Empty list for certain fields is a problem
            if field in ["stage_risks", "required_disclosures"]:
                issues.append(f"[{schema.schema_id}] 字段{field}不可为空列表")
    
    is_valid = len(issues) == 0
    return is_valid, issues


def get_schema_prompt_hint(stage: str) -> str:
    """Get schema hint for prompt."""
    schema = get_schema(stage)
    fields = ", ".join(schema.required_fields)
    return f"用JSON格式回答，必须包含以下字段: {fields}"
