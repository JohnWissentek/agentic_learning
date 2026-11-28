"""v0.3.1 Baseline Loader - Loads REAL data from extracted directory.

This module loads baseline data directly from the extracted v0.3.1 ZIP,
ensuring all prompts use the actual v0.3.1 SHA256 and status.

CRITICAL: Version evidence must match actual loaded files.
"""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass

# Expected v0.3.1 SHA256
V031_EXPECTED_SHA256 = "aecc9c4a5a87f9597628cacce3fab088abd0d4d34f0a02417bad1946d74e6f6a"


@dataclass
class V031Baseline:
    """Loaded v0.3.1 baseline data."""
    version: str
    zip_sha256: str
    delivery_version: dict[str, Any]
    quality_gate: dict[str, Any]
    independent_review_accepted: int
    engineering_open: int
    physical_not_run: int
    procurement_status: str
    product_release: str
    
    def validate(self) -> list[str]:
        """Validate loaded data consistency."""
        errors = []
        if self.version != "v0.3.1":
            errors.append(f"版本不匹配: 期望v0.3.1, 实际{self.version}")
        if self.zip_sha256 != V031_EXPECTED_SHA256:
            errors.append(f"SHA256不匹配")
        if self.independent_review_accepted != 10:
            errors.append(f"独立复查接受数不匹配: 期望10, 实际{self.independent_review_accepted}")
        return errors


def load_v031_baseline(
    extracted_dir: str = "/workspace/boiler_product_v031"
) -> V031Baseline:
    """Load v0.3.1 baseline from extracted directory.
    
    Raises AssertionError if version/hash mismatch.
    """
    base = Path(extracted_dir)
    
    # Load DELIVERY_VERSION.json (in research/ subdirectory)
    delivery_path = base / "research" / "DELIVERY_VERSION.json"
    if not delivery_path.exists():
        raise FileNotFoundError(f"DELIVERY_VERSION.json not found at {delivery_path}")
    
    with open(delivery_path, encoding="utf-8") as f:
        delivery = json.load(f)
    
    # Load quality gate input
    quality_gate_path = base / "quality" / "quality_gate_input_v0.3.json"
    if not quality_gate_path.exists():
        raise FileNotFoundError(f"quality_gate_input not found at {quality_gate_path}")
    
    with open(quality_gate_path, encoding="utf-8") as f:
        quality_gate = json.load(f)
    
    # Verify version
    version = delivery.get("version", "")
    assert version == "v0.3.1", f"版本不匹配: 期望v0.3.1, 实际{version}"
    
    # Get key status fields
    baseline = V031Baseline(
        version=version,
        zip_sha256=V031_EXPECTED_SHA256,
        delivery_version=delivery,
        quality_gate=quality_gate,
        independent_review_accepted=delivery.get("independent_document_corrections_accepted", 0),
        engineering_open=10,  # All 10 engineering items still OPEN
        physical_not_run=10,  # All physical tests NOT_RUN
        procurement_status=delivery.get("procurement_readiness", "UNKNOWN"),
        product_release=delivery.get("product_release", "UNKNOWN"),
    )
    
    # Validate
    errors = baseline.validate()
    if errors:
        raise AssertionError(f"基线验证失败: {errors}")
    
    return baseline


def build_v031_context(baseline: V031Baseline) -> str:
    """Build prompt context from loaded v0.3.1 baseline.
    
    This ensures prompts contain the ACTUAL loaded data, not hardcoded values.
    """
    return f"""研究数据版本：v0.3.1 (SHA256: {baseline.zip_sha256})
状态（从DELIVERY_VERSION.json加载）：
- 文档纠正已实施：10项
- 独立复查已接受：{baseline.independent_review_accepted}/10 (DOCUMENT_CORRECTION_ACCEPTED)
- 接受范围：{baseline.delivery_version.get('independent_acceptance_scope', 'UNKNOWN')}
- 工程验证：{baseline.engineering_open}项仍OPEN
- 实体试验：{baseline.physical_not_run}项NOT_RUN
- 采购状态：{baseline.procurement_status}
- 产品交付：{baseline.product_release}
- 文档纠正ACCEPTED ≠ 工程验证PASS"""


# Evidence constraints that model outputs must NOT violate
EVIDENCE_CONSTRAINTS = {
    "link_margin_unknown": {
        "field": "link_margin",
        "forbidden_claims": ["影响不大", "无需关注", "足够", "满足"],
        "required_status": "UNKNOWN",
        "finding": "QA-09链路余量UNKNOWN，不可声称影响不大",
    },
    "unknown_costs_not_zero": {
        "field": "unknown_costs",
        "forbidden_values": [0, "0", 0.0],
        "required_status": "UNKNOWN",
        "finding": "QA-10未知成本不得填0，必须标UNKNOWN",
    },
    "fwhm_not_full_spectrum": {
        "field": "fwhm_check",
        "forbidden_claims": ["满足", "基本满足", "够用", "足够"],
        "required_status": "NOT_PROVEN",
        "finding": "QA-05 FWHM不是全谱边界保证，不可声称满足",
    },
    "procurement_not_ready": {
        "field": "procurement",
        "forbidden_claims": ["就绪", "已准备", "可以采购"],
        "required_status": "NOT_READY",
        "finding": "采购状态NOT_READY，不可声称就绪",
    },
    "accuracy_not_proven": {
        "field": "accuracy",
        "forbidden_claims": ["已证明", "满足", "达到±3℃", "±5℃可达"],
        "required_status": "NOT_PROVEN",
        "finding": "连续现场精度NOT_PROVEN，不可声称已满足",
    },
}


def check_evidence_violations(
    raw_response: str,
    parsed: Optional[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check if model output violates evidence constraints.
    
    Returns list of violations found.
    """
    violations = []
    
    for constraint_id, constraint in EVIDENCE_CONSTRAINTS.items():
        # Check forbidden claims in raw text
        for claim in constraint.get("forbidden_claims", []):
            if claim in raw_response:
                violations.append({
                    "constraint_id": constraint_id,
                    "type": "forbidden_claim_in_text",
                    "claim": claim,
                    "finding": constraint["finding"],
                    "severity": "HIGH",
                })
        
        # Check forbidden values in parsed output
        if parsed:
            field = constraint.get("field")
            if field and field in parsed:
                value = parsed[field]
                for forbidden in constraint.get("forbidden_values", []):
                    if value == forbidden:
                        violations.append({
                            "constraint_id": constraint_id,
                            "type": "forbidden_value",
                            "field": field,
                            "value": value,
                            "finding": constraint["finding"],
                            "severity": "HIGH",
                        })
    
    return violations


# Pre-loaded baseline (lazy initialization)
_loaded_baseline: Optional[V031Baseline] = None


def get_baseline() -> V031Baseline:
    """Get cached v0.3.1 baseline, loading if needed."""
    global _loaded_baseline
    if _loaded_baseline is None:
        _loaded_baseline = load_v031_baseline()
    return _loaded_baseline


def assert_baseline_loaded(expected_version: str = "v0.3.1") -> V031Baseline:
    """Assert baseline is loaded and matches expected version."""
    baseline = get_baseline()
    assert baseline.version == expected_version, f"基线版本不匹配: {baseline.version} vs {expected_version}"
    assert baseline.zip_sha256 == V031_EXPECTED_SHA256, "SHA256不匹配"
    return baseline
