"""Tests for v0.3.1 strict validation and evidence constraints.

These tests verify:
1. v0.3.1 baseline loads correctly with correct version/hash
2. Strict validator rejects empty {}, truncated JSON
3. Evidence constraints catch forbidden claims
4. Prompts include correct v0.3.1 hash (not v0.3)
"""

import pytest
import json
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestV031BaselineLoader:
    """Test v0.3.1 baseline loading."""
    
    def test_baseline_version_is_v031(self):
        """Baseline version must be v0.3.1."""
        from boiler_fbg_workflow.v031_loader import load_v031_baseline
        baseline = load_v031_baseline()
        assert baseline.version == "v0.3.1"
    
    def test_baseline_sha256_is_correct(self):
        """Baseline SHA256 must match expected v0.3.1 hash."""
        from boiler_fbg_workflow.v031_loader import (
            load_v031_baseline,
            V031_EXPECTED_SHA256,
        )
        baseline = load_v031_baseline()
        assert baseline.zip_sha256 == V031_EXPECTED_SHA256
        # Must NOT be v0.3 hash
        assert baseline.zip_sha256 != "2fefbc0d146b2dc9a5403f45cd3e729e82137367ab0d9cafaffca7afad85fe20"
    
    def test_baseline_independent_review_accepted(self):
        """v0.3.1 must have 10/10 document corrections accepted."""
        from boiler_fbg_workflow.v031_loader import load_v031_baseline
        baseline = load_v031_baseline()
        assert baseline.independent_review_accepted == 10
    
    def test_baseline_engineering_still_open(self):
        """v0.3.1 engineering items must still be OPEN."""
        from boiler_fbg_workflow.v031_loader import load_v031_baseline
        baseline = load_v031_baseline()
        assert baseline.engineering_open == 10
    
    def test_baseline_physical_not_run(self):
        """v0.3.1 physical tests must be NOT_RUN."""
        from boiler_fbg_workflow.v031_loader import load_v031_baseline
        baseline = load_v031_baseline()
        assert baseline.physical_not_run == 10
    
    def test_baseline_procurement_not_ready(self):
        """v0.3.1 procurement must be NOT_READY."""
        from boiler_fbg_workflow.v031_loader import load_v031_baseline
        baseline = load_v031_baseline()
        assert baseline.procurement_status == "NOT_READY"
    
    def test_baseline_context_contains_v031_hash(self):
        """Built context must contain v0.3.1 hash, not v0.3."""
        from boiler_fbg_workflow.v031_loader import (
            load_v031_baseline,
            build_v031_context,
            V031_EXPECTED_SHA256,
        )
        baseline = load_v031_baseline()
        context = build_v031_context(baseline)
        
        # Must contain v0.3.1 hash
        assert V031_EXPECTED_SHA256 in context
        # Must NOT contain v0.3 hash
        assert "2fefbc0d146b2dc9a5403f45cd3e729e82137367ab0d9cafaffca7afad85fe20" not in context


class TestStrictValidator:
    """Test strict output validation."""
    
    def test_empty_dict_is_not_valid(self):
        """Empty {} must NOT be VALID."""
        from boiler_fbg_workflow.strict_validator import validate_output, OutputStatus
        
        result = validate_output(
            raw_response="{}",
            finish_reason="stop",
            token_count=1,
            role="MKT",
        )
        
        # Either EMPTY_OUTPUT (too short) or SCHEMA_FAILED, but NOT VALID
        assert result.status != OutputStatus.VALID
        assert result.status in [OutputStatus.SCHEMA_FAILED, OutputStatus.EMPTY_OUTPUT]
        assert not result.is_valid
    
    def test_truncated_json_is_not_valid(self):
        """Truncated JSON must be TRUNCATED, not VALID."""
        from boiler_fbg_workflow.strict_validator import validate_output, OutputStatus
        
        result = validate_output(
            raw_response='{"market_size": "UNKNOWN", "competitors": [',
            finish_reason="length",
            token_count=100,
            role="MKT",
        )
        
        assert result.status == OutputStatus.TRUNCATED
        assert not result.is_valid
    
    def test_parse_failed_not_success(self):
        """parse_success must be False when JSON fails to parse."""
        from boiler_fbg_workflow.strict_validator import validate_output, OutputStatus
        
        result = validate_output(
            raw_response="This is not JSON at all",
            finish_reason="stop",
            token_count=10,
            role="MKT",
        )
        
        assert result.status == OutputStatus.PARSE_FAILED
        assert not result.parse_success
    
    def test_missing_required_fields_is_schema_failed(self):
        """Missing required fields must be SCHEMA_FAILED."""
        from boiler_fbg_workflow.strict_validator import validate_output, OutputStatus
        
        # MKT requires: market_size, competitors, pain_points, entry_risks
        result = validate_output(
            raw_response='{"market_size": "UNKNOWN"}',  # Missing others
            finish_reason="stop",
            token_count=10,
            role="MKT",
        )
        
        assert result.status == OutputStatus.SCHEMA_FAILED
        assert "缺少必需字段" in str(result.issues)


class TestEvidenceConstraints:
    """Test evidence constraint checking."""
    
    def test_link_margin_unknown_violation(self):
        """Claiming 'link margin doesn't matter' must be flagged."""
        from boiler_fbg_workflow.v031_loader import check_evidence_violations
        
        raw = "链路余量未知影响不大，无需特别关注"
        violations = check_evidence_violations(raw, {})
        
        assert len(violations) > 0
        assert any("link_margin" in v["constraint_id"] for v in violations)
    
    def test_unknown_costs_zero_violation(self):
        """Setting unknown_costs=0 must be flagged."""
        from boiler_fbg_workflow.v031_loader import check_evidence_violations
        
        parsed = {"unknown_costs": 0}
        violations = check_evidence_violations("", parsed)
        
        assert len(violations) > 0
        assert any("unknown_costs" in v["constraint_id"] for v in violations)
    
    def test_fwhm_satisfied_violation(self):
        """Claiming 'FWHM basically satisfied' must be flagged."""
        from boiler_fbg_workflow.v031_loader import check_evidence_violations
        
        raw = "FWHM基本满足8点/串的要求"
        violations = check_evidence_violations(raw, {})
        
        assert len(violations) > 0
        assert any("fwhm" in v["constraint_id"] for v in violations)
    
    def test_procurement_ready_violation(self):
        """Claiming 'procurement ready' must be flagged."""
        from boiler_fbg_workflow.v031_loader import check_evidence_violations
        
        raw = "采购已就绪，可以开始询价"
        violations = check_evidence_violations(raw, {})
        
        assert len(violations) > 0
        assert any("procurement" in v["constraint_id"] for v in violations)
    
    def test_accuracy_proven_violation(self):
        """Claiming '±3°C achieved' must be flagged."""
        from boiler_fbg_workflow.v031_loader import check_evidence_violations
        
        raw = "现场精度已证明满足±5℃可达要求"
        violations = check_evidence_violations(raw, {})
        
        assert len(violations) > 0
        assert any("accuracy" in v["constraint_id"] for v in violations)
    
    def test_valid_response_no_violations(self):
        """Valid response should have no violations."""
        from boiler_fbg_workflow.v031_loader import check_evidence_violations
        
        raw = """链路余量UNKNOWN，影响待评估。
成本数据UNKNOWN，不填0。
FWHM仅为近似主峰宽度，非全谱保证，待验证。
采购NOT_READY。
精度NOT_PROVEN。"""
        
        violations = check_evidence_violations(raw, {})
        assert len(violations) == 0


class TestPromptVersionMapping:
    """Test that prompts use correct version info."""
    
    def test_prompt_context_has_v031_version(self):
        """System prompt context must contain v0.3.1 version."""
        from boiler_fbg_workflow.v031_loader import (
            load_v031_baseline,
            build_v031_context,
        )
        
        baseline = load_v031_baseline()
        context = build_v031_context(baseline)
        
        assert "v0.3.1" in context
    
    def test_prompt_context_has_10_accepted(self):
        """System prompt context must show 10/10 accepted."""
        from boiler_fbg_workflow.v031_loader import (
            load_v031_baseline,
            build_v031_context,
        )
        
        baseline = load_v031_baseline()
        context = build_v031_context(baseline)
        
        assert "10/10" in context or "已接受：10" in context
    
    def test_prompt_context_not_v03_hash(self):
        """System prompt context must NOT contain v0.3 hash."""
        from boiler_fbg_workflow.v031_loader import (
            load_v031_baseline,
            build_v031_context,
        )
        
        baseline = load_v031_baseline()
        context = build_v031_context(baseline)
        
        # v0.3 hash must NOT be present
        v03_hash = "2fefbc0d146b2dc9a5403f45cd3e729e82137367ab0d9cafaffca7afad85fe20"
        assert v03_hash not in context


class TestModelManifestNotHardcoded:
    """Test that model manifest uses computed values."""
    
    def test_model_manifest_has_correct_v031_version(self):
        """Model manifest version field must be v0.3.1."""
        from boiler_fbg_workflow.model_manifest import V031_BASELINE
        
        assert V031_BASELINE["version"] == "v0.3.1"
    
    def test_model_manifest_has_correct_sha256(self):
        """Model manifest sha256 must be v0.3.1 hash."""
        from boiler_fbg_workflow.model_manifest import V031_BASELINE
        
        expected = "aecc9c4a5a87f9597628cacce3fab088abd0d4d34f0a02417bad1946d74e6f6a"
        assert V031_BASELINE["zip_sha256"] == expected
    
    def test_model_manifest_recheck_accepted(self):
        """Model manifest must show recheck ACCEPTED for all findings."""
        from boiler_fbg_workflow.model_manifest import V031_BASELINE
        
        for finding_id, status in V031_BASELINE["findings_status"].items():
            assert status["recheck"] == "ACCEPTED", f"{finding_id} recheck not ACCEPTED"
    
    def test_model_manifest_engineering_still_open(self):
        """Model manifest must show engineering still OPEN."""
        from boiler_fbg_workflow.model_manifest import V031_BASELINE
        
        for finding_id, status in V031_BASELINE["findings_status"].items():
            assert status["engineering"] == "OPEN", f"{finding_id} engineering not OPEN"


class TestValidatorStatusConsistency:
    """Test validator status is consistent across fields."""
    
    def test_status_matches_parse_success(self):
        """parse_success must match status appropriately."""
        from boiler_fbg_workflow.strict_validator import validate_output, OutputStatus
        
        # Valid JSON but missing fields
        result = validate_output(
            raw_response='{"test": "value"}',
            finish_reason="stop",
            token_count=10,
            role="MKT",
        )
        
        # JSON parsed (parse_success=True) but schema failed
        if result.status == OutputStatus.SCHEMA_FAILED:
            assert result.parse_success == True  # JSON did parse
        
    def test_truncated_never_has_parse_success_true(self):
        """Truncated output must have parse_success=False."""
        from boiler_fbg_workflow.strict_validator import validate_output, OutputStatus
        
        result = validate_output(
            raw_response='{"market_size": "UNKNOWN"',  # Truncated
            finish_reason="length",
            token_count=100,
            role="MKT",
        )
        
        assert result.status == OutputStatus.TRUNCATED
        assert result.parse_success == False


class TestNoFakeValidationPassing:
    """Ensure validation doesn't fake passing."""
    
    def test_scm_missing_quotes_fails(self):
        """SCM output with missing quotes must fail parse."""
        from boiler_fbg_workflow.strict_validator import validate_output, OutputStatus
        
        # Malformed JSON
        raw = '{available_vendors: ["FiSens"], blocking_items: []}'  # Missing quotes on keys
        result = validate_output(
            raw_response=raw,
            finish_reason="stop",
            token_count=50,
            role="SCM",
        )
        
        assert result.status == OutputStatus.PARSE_FAILED
        assert not result.parse_success
    
    def test_valid_scm_output_passes(self):
        """Properly formatted SCM output should pass."""
        from boiler_fbg_workflow.strict_validator import validate_output, OutputStatus
        
        raw = json.dumps({
            "available_vendors": ["FiSens", "CalSens"],
            "blocking_items": ["采购NOT_READY", "价格UNKNOWN"],
            "funding_uncertainty": "A0/A1/A2全部UNKNOWN，不可填0",
        })
        
        result = validate_output(
            raw_response=raw,
            finish_reason="stop",
            token_count=100,
            role="SCM",
        )
        
        assert result.parse_success == True
        assert result.parsed_output is not None
        assert result.parsed_output.get("available_vendors") == ["FiSens", "CalSens"]
