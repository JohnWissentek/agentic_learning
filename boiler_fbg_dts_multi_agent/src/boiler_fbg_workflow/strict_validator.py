"""Strict Output Validation - No empty {} or truncated JSON allowed as VALID.

This module provides strict validation of LLM outputs:
1. JSON must parse completely (no truncation)
2. Parsed dict must have required fields
3. Empty {} is NEVER valid
4. Evidence constraints must not be violated
"""

from __future__ import annotations
import json
import re
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from boiler_fbg_workflow.v031_loader import check_evidence_violations


class OutputStatus(str, Enum):
    """Output quality status - strict definitions."""
    VALID = "VALID"  # JSON parses, has content, no violations
    TRUNCATED = "TRUNCATED"  # JSON truncated mid-stream
    PARSE_FAILED = "PARSE_FAILED"  # JSON does not parse
    EMPTY_OUTPUT = "EMPTY_OUTPUT"  # Empty or too short
    SCHEMA_FAILED = "SCHEMA_FAILED"  # Missing required fields
    EVIDENCE_VIOLATION = "EVIDENCE_VIOLATION"  # Violates evidence constraints
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Has issues but partially usable


@dataclass
class ValidationResult:
    """Result of output validation."""
    status: OutputStatus
    raw_response: str
    parsed_output: Optional[dict[str, Any]]
    parse_success: bool
    issues: list[str] = field(default_factory=list)
    evidence_violations: list[dict] = field(default_factory=list)
    finish_reason: str = "unknown"
    token_count: int = 0
    
    @property
    def is_valid(self) -> bool:
        return self.status == OutputStatus.VALID
    
    @property
    def is_usable(self) -> bool:
        """Output can be used but may need review."""
        return self.status in [OutputStatus.VALID, OutputStatus.NEEDS_REVIEW]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "parse_success": self.parse_success,
            "is_valid": self.is_valid,
            "is_usable": self.is_usable,
            "issues": self.issues,
            "evidence_violations": self.evidence_violations,
            "finish_reason": self.finish_reason,
            "token_count": self.token_count,
        }


def _detect_truncation(response: str, finish_reason: str) -> bool:
    """Detect if response was truncated."""
    # Explicit truncation from finish_reason
    if finish_reason in ["length", "max_tokens"]:
        return True
    
    # JSON appears truncated
    if "{" in response and "}" not in response:
        return True
    
    # Unbalanced braces
    open_braces = response.count("{")
    close_braces = response.count("}")
    if open_braces > close_braces:
        return True
    
    # Ends mid-string/key
    stripped = response.rstrip()
    if stripped.endswith((",", ":", '"', "'")):
        return True
    
    return False


def _try_parse_json(response: str) -> tuple[Optional[dict], str]:
    """Try to parse JSON from response, return (parsed, error_msg)."""
    # Try direct parse
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            return parsed, ""
        return None, f"解析结果不是字典: {type(parsed)}"
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON block
    patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```\s*\n(.*?)\n```',
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            try:
                text = match.group(1) if '```' in pattern else match.group(0)
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed, ""
            except (json.JSONDecodeError, IndexError):
                continue
    
    return None, "无法从响应中提取有效JSON"


def _validate_schema(
    parsed: dict[str, Any],
    required_fields: list[str],
    role: str,
) -> list[str]:
    """Validate parsed output has required fields."""
    issues = []
    
    # Empty dict is NEVER valid
    if not parsed:
        issues.append(f"{role}输出为空字典{{}}")
        return issues
    
    # Check required fields
    for field_name in required_fields:
        if field_name not in parsed:
            issues.append(f"{role}缺少必需字段: {field_name}")
        elif parsed[field_name] in [None, "", [], {}]:
            issues.append(f"{role}字段{field_name}为空值")
    
    return issues


# Required fields per role
ROLE_REQUIRED_FIELDS = {
    "MKT": ["market_size", "competitors", "pain_points", "entry_risks"],
    "OPT": ["fwhm_analysis", "wavelength_budget", "uncertainty_status"],
    "HW": ["thermal_design", "link_margin_impact", "integration_risks"],
    "SW": ["blind_window_stats", "data_flow", "ai_isolation"],
    "SCM": ["available_vendors", "blocking_items", "funding_uncertainty"],
    "MFG": ["npi_blockers", "prerequisites", "test_checklist"],
    "TRN": ["training_modules", "safety_points", "certifications"],
    "FIN": ["funding_gaps", "stage_risks", "competitiveness_status"],
    "SLS": ["available_materials", "forbidden_claims", "prerequisites"],
    "QA": ["rework_required", "doc_vs_engineering", "evidence_gaps", "gate_decision"],
    "PM": ["output_summary", "rework_items", "action_plan"],
    "STR": ["current_phase", "milestones", "go_nogo_points"],
}


def validate_output(
    raw_response: str,
    finish_reason: str,
    token_count: int,
    role: str,
    check_evidence: bool = True,
) -> ValidationResult:
    """Strictly validate LLM output.
    
    RULES:
    1. Empty response → EMPTY_OUTPUT
    2. Truncated → TRUNCATED (not VALID)
    3. Parse failed → PARSE_FAILED (not VALID with {})
    4. Empty {} → SCHEMA_FAILED (never VALID)
    5. Missing required fields → SCHEMA_FAILED
    6. Evidence violations → EVIDENCE_VIOLATION
    """
    issues = []
    
    # Check empty
    if not raw_response or len(raw_response.strip()) < 5:
        return ValidationResult(
            status=OutputStatus.EMPTY_OUTPUT,
            raw_response=raw_response,
            parsed_output=None,
            parse_success=False,
            issues=["响应为空或过短"],
            finish_reason=finish_reason,
            token_count=token_count,
        )
    
    # Check truncation
    if _detect_truncation(raw_response, finish_reason):
        # Try to parse anyway
        parsed, _ = _try_parse_json(raw_response)
        return ValidationResult(
            status=OutputStatus.TRUNCATED,
            raw_response=raw_response,
            parsed_output=parsed,  # May be partial
            parse_success=False,  # Truncated is NOT success
            issues=[f"输出被截断 (finish_reason={finish_reason})"],
            finish_reason=finish_reason,
            token_count=token_count,
        )
    
    # Try to parse
    parsed, parse_error = _try_parse_json(raw_response)
    
    if parsed is None:
        return ValidationResult(
            status=OutputStatus.PARSE_FAILED,
            raw_response=raw_response,
            parsed_output=None,
            parse_success=False,
            issues=[parse_error],
            finish_reason=finish_reason,
            token_count=token_count,
        )
    
    # Validate schema (empty {} fails here)
    required = ROLE_REQUIRED_FIELDS.get(role, [])
    schema_issues = _validate_schema(parsed, required, role)
    
    if schema_issues:
        return ValidationResult(
            status=OutputStatus.SCHEMA_FAILED,
            raw_response=raw_response,
            parsed_output=parsed,
            parse_success=True,  # JSON parsed, but schema failed
            issues=schema_issues,
            finish_reason=finish_reason,
            token_count=token_count,
        )
    
    # Check evidence violations
    evidence_violations = []
    if check_evidence:
        evidence_violations = check_evidence_violations(raw_response, parsed)
    
    if evidence_violations:
        return ValidationResult(
            status=OutputStatus.EVIDENCE_VIOLATION,
            raw_response=raw_response,
            parsed_output=parsed,
            parse_success=True,
            issues=[v["finding"] for v in evidence_violations],
            evidence_violations=evidence_violations,
            finish_reason=finish_reason,
            token_count=token_count,
        )
    
    # Check for concerning patterns (NEEDS_REVIEW)
    concerning = []
    if "..." in raw_response or "等等" in raw_response:
        concerning.append("包含省略内容")
    if any(kw in raw_response for kw in ["以此类推", "类似地"]):
        concerning.append("包含泛化表述")
    
    if concerning:
        issues.extend(concerning)
        return ValidationResult(
            status=OutputStatus.NEEDS_REVIEW,
            raw_response=raw_response,
            parsed_output=parsed,
            parse_success=True,
            issues=issues,
            finish_reason=finish_reason,
            token_count=token_count,
        )
    
    # All checks passed
    return ValidationResult(
        status=OutputStatus.VALID,
        raw_response=raw_response,
        parsed_output=parsed,
        parse_success=True,
        issues=[],
        finish_reason=finish_reason,
        token_count=token_count,
    )
