"""Tests for QA Findings Integration.

Verifies that real independent QA review findings (5 HIGH, 5 MEDIUM)
are correctly integrated and can be used for the Reflection Pattern.

Reference: Chapter 4 (P67-82) - Reflection Pattern
"""

import pytest
from boiler_fbg_workflow.qa_findings import (
    QA_REVIEW_METADATA,
    QA_FINDINGS_HIGH,
    QA_FINDINGS_MEDIUM,
    QA_FINDINGS_ALL,
    get_findings_summary,
    get_findings_for_reflection_prompt,
    get_pm_task_revision_input,
)


class TestQAFindingsStructure:
    """Test QA findings data structure integrity."""
    
    def test_high_severity_count(self):
        """Should have exactly 5 HIGH severity findings."""
        assert len(QA_FINDINGS_HIGH) == 5
    
    def test_medium_severity_count(self):
        """Should have exactly 5 MEDIUM severity findings."""
        assert len(QA_FINDINGS_MEDIUM) == 5
    
    def test_total_findings_count(self):
        """Should have 10 total findings."""
        assert len(QA_FINDINGS_ALL) == 10
    
    def test_review_metadata_present(self):
        """Should have review metadata with required fields."""
        assert "review_id" in QA_REVIEW_METADATA
        assert "decision" in QA_REVIEW_METADATA
        assert "top5" in QA_REVIEW_METADATA
        assert QA_REVIEW_METADATA["review_id"] == "BOILER-QA-INDEPENDENT-v0.2-20261116"
    
    def test_each_finding_has_required_fields(self):
        """Each finding should have all required fields."""
        required_fields = {"id", "severity", "title", "problem", "status"}
        for finding in QA_FINDINGS_ALL:
            for field in required_fields:
                assert field in finding, f"Finding {finding.get('id')} missing {field}"
    
    def test_high_findings_block_gate(self):
        """All HIGH findings should block the gate."""
        for finding in QA_FINDINGS_HIGH:
            workflow_impact = finding.get("workflow_impact", {})
            assert workflow_impact.get("blocks_gate") is True, \
                f"HIGH finding {finding['id']} should block gate"


class TestQA01AgingRecalibration:
    """Test QA-01: Aging recalibration requirement.
    
    老化后必须原校准系数复验 - drift pass ≠ full chain MPE pass
    """
    
    def test_qa01_exists(self):
        """QA-01 should exist in findings."""
        qa01 = next((f for f in QA_FINDINGS_ALL if f["id"] == "QA-01"), None)
        assert qa01 is not None
    
    def test_qa01_is_high_severity(self):
        """QA-01 should be HIGH severity."""
        qa01 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-01")
        assert qa01["severity"] == "HIGH"
    
    def test_qa01_addresses_aging_drift(self):
        """QA-01 should address aging/drift verification gap."""
        qa01 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-01")
        assert "漂移" in qa01["title"] or "老化" in qa01["problem"]
        assert "CAL03" in qa01["recommended_correction"]
    
    def test_qa01_requires_recalibration_test(self):
        """QA-01 should require aging recalibration test."""
        qa01 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-01")
        test_name = qa01.get("workflow_impact", {}).get("test_to_add")
        assert test_name == "test_aging_recalibration_verification"


class TestQA03MeasurandCoverage:
    """Test QA-03: Measurand coverage per sensor point.
    
    8TC不能推出64点精度 - 每点measurand和参考绑定
    """
    
    def test_qa03_exists(self):
        """QA-03 should exist in findings."""
        qa03 = next((f for f in QA_FINDINGS_ALL if f["id"] == "QA-03"), None)
        assert qa03 is not None
    
    def test_qa03_is_high_severity(self):
        """QA-03 should be HIGH severity."""
        qa03 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-03")
        assert qa03["severity"] == "HIGH"
    
    def test_qa03_addresses_8tc_to_64_gap(self):
        """QA-03 should address 8TC → 64 point coverage gap."""
        qa03 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-03")
        assert "8" in qa03["title"] or "64" in qa03["title"]
        assert "对照" in qa03["original_evidence"] or "热电偶" in qa03["original_evidence"]
    
    def test_qa03_requires_not_covered_handling(self):
        """QA-03 should require NOT_COVERED point handling."""
        qa03 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-03")
        code_impact = qa03.get("workflow_impact", {}).get("code_impact", "")
        assert "NOT_COVERED" in code_impact or "8TC" in code_impact
    
    def test_qa03_requires_measurand_test(self):
        """QA-03 should require measurand coverage test."""
        qa03 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-03")
        test_name = qa03.get("workflow_impact", {}).get("test_to_add")
        assert test_name == "test_measurand_coverage_per_sensor"


class TestQA05FWHMSpectralMask:
    """Test QA-05: FWHM is not full-spectrum guarantee.
    
    FWHM不是全谱边界保证 - 需要固件阈值配置
    """
    
    def test_qa05_exists(self):
        """QA-05 should exist in findings."""
        qa05 = next((f for f in QA_FINDINGS_ALL if f["id"] == "QA-05"), None)
        assert qa05 is not None
    
    def test_qa05_is_high_severity(self):
        """QA-05 should be HIGH severity."""
        qa05 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-05")
        assert qa05["severity"] == "HIGH"
    
    def test_qa05_addresses_fwhm_limitation(self):
        """QA-05 should address FWHM spectral limitation."""
        qa05 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-05")
        assert "FWHM" in qa05["title"]
        # Check for spectral mask (谱罩) in title or problem
        assert "谱罩" in qa05["title"] or "FWHM不是" in qa05["problem"]
    
    def test_qa05_requires_firmware_thresholds(self):
        """QA-05 should require firmware threshold specification."""
        qa05 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-05")
        code_impact = qa05.get("workflow_impact", {}).get("code_impact", "")
        assert "固件" in code_impact or "阈值" in code_impact


class TestQA08AvailabilityStats:
    """Test QA-08: Percentage availability is insufficient.
    
    百分比可用率不足 - 需要最长连续盲区统计
    """
    
    def test_qa08_exists(self):
        """QA-08 should exist in findings."""
        qa08 = next((f for f in QA_FINDINGS_ALL if f["id"] == "QA-08"), None)
        assert qa08 is not None
    
    def test_qa08_is_medium_severity(self):
        """QA-08 should be MEDIUM severity."""
        qa08 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-08")
        assert qa08["severity"] == "MEDIUM"
    
    def test_qa08_addresses_blind_window(self):
        """QA-08 should address longest blind window issue."""
        qa08 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-08")
        assert "盲区" in qa08["title"] or "失联" in qa08["problem"]
        assert "21.6min" in qa08["problem"] or "百分比" in qa08["title"]
    
    def test_qa08_requires_blind_window_test(self):
        """QA-08 should require blind window statistics test."""
        qa08 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-08")
        test_name = qa08.get("workflow_impact", {}).get("test_to_add")
        assert test_name == "test_longest_blind_window_stats"
    
    def test_qa08_code_impact_mentioned(self):
        """QA-08 should have code impact mentioned."""
        qa08 = next(f for f in QA_FINDINGS_ALL if f["id"] == "QA-08")
        code_impact = qa08.get("workflow_impact", {}).get("code_impact", "")
        assert "最长" in code_impact or "盲区" in code_impact


class TestFindingsSummary:
    """Test get_findings_summary() function."""
    
    def test_summary_has_counts(self):
        """Summary should have all count fields."""
        summary = get_findings_summary()
        assert summary["total_findings"] == 10
        assert summary["high_severity_count"] == 5
        assert summary["medium_severity_count"] == 5
    
    def test_summary_has_blocking_info(self):
        """Summary should have blocking findings info."""
        summary = get_findings_summary()
        assert summary["blocking_findings_count"] == 5
        assert "QA-01" in summary["blocking_finding_ids"]
        assert "QA-03" in summary["blocking_finding_ids"]
        assert "QA-05" in summary["blocking_finding_ids"]
    
    def test_summary_has_top5(self):
        """Summary should have top 5 priority findings."""
        summary = get_findings_summary()
        assert summary["top5_priority"] == ["QA-01", "QA-03", "QA-04", "QA-02", "QA-05"]
    
    def test_summary_has_tests_to_add(self):
        """Summary should list tests to add."""
        summary = get_findings_summary()
        assert "test_aging_recalibration_verification" in summary["tests_to_add"]
        assert "test_measurand_coverage_per_sensor" in summary["tests_to_add"]
        assert "test_longest_blind_window_stats" in summary["tests_to_add"]
    
    def test_summary_gate_is_blocked(self):
        """Summary should indicate gate is BLOCKED."""
        summary = get_findings_summary()
        assert summary["gate_status"] == "BLOCKED"


class TestFindingsForReflection:
    """Test get_findings_for_reflection_prompt() function."""
    
    def test_reflection_prompt_contains_review_id(self):
        """Reflection prompt should contain review ID."""
        prompt = get_findings_for_reflection_prompt()
        assert "BOILER-QA-INDEPENDENT-v0.2-20261116" in prompt
    
    def test_reflection_prompt_contains_top5(self):
        """Reflection prompt should contain TOP 5 section."""
        prompt = get_findings_for_reflection_prompt()
        assert "TOP 5" in prompt
        assert "QA-01" in prompt
        assert "QA-03" in prompt
    
    def test_reflection_prompt_contains_high_findings(self):
        """Reflection prompt should contain HIGH severity findings."""
        prompt = get_findings_for_reflection_prompt()
        assert "HIGH" in prompt
        assert "5项" in prompt or "5个" in prompt or "(5" in prompt


class TestPMTaskRevisionInput:
    """Test get_pm_task_revision_input() function."""
    
    def test_revision_input_has_actions(self):
        """Revision input should have high priority actions."""
        input_data = get_pm_task_revision_input()
        assert "high_priority_actions" in input_data
        assert len(input_data["high_priority_actions"]) > 0
    
    def test_revision_input_has_tests(self):
        """Revision input should list tests to implement."""
        input_data = get_pm_task_revision_input()
        assert "tests_to_implement" in input_data
        assert len(input_data["tests_to_implement"]) == 6
    
    def test_revision_actions_include_blocking_items(self):
        """Revision actions should include blocking items."""
        input_data = get_pm_task_revision_input()
        action_ids = [a["finding_id"] for a in input_data["high_priority_actions"]]
        assert "QA-01" in action_ids
        assert "QA-03" in action_ids
        assert "QA-05" in action_ids
        assert "QA-08" in action_ids
    
    def test_revision_gate_is_blocked(self):
        """Revision input should indicate gate is BLOCKED."""
        input_data = get_pm_task_revision_input()
        assert input_data["gate_status"] == "BLOCKED"
        assert input_data["revision_required"] is True


class TestTop5Priority:
    """Test TOP 5 priority findings as specified by QA."""
    
    def test_top5_order_matches_qa_specification(self):
        """TOP 5 order should match QA specification."""
        expected_top5 = ["QA-01", "QA-03", "QA-04", "QA-02", "QA-05"]
        assert QA_REVIEW_METADATA["top5"] == expected_top5
    
    def test_top5_are_all_high_severity(self):
        """TOP 5 should all be HIGH severity."""
        top5_ids = QA_REVIEW_METADATA["top5"]
        for finding_id in top5_ids:
            finding = next(f for f in QA_FINDINGS_ALL if f["id"] == finding_id)
            assert finding["severity"] == "HIGH", \
                f"TOP 5 finding {finding_id} should be HIGH severity"


class TestGuardrailConstraints:
    """Test guardrail constraints on QA findings."""
    
    def test_all_findings_are_open(self):
        """All findings should have status OPEN."""
        for finding in QA_FINDINGS_ALL:
            assert finding["status"] == "OPEN", \
                f"Finding {finding['id']} should be OPEN"
    
    def test_all_physical_tests_not_run(self):
        """All physical test statuses should be NOT_RUN."""
        for finding in QA_FINDINGS_ALL:
            if "physical_test_status" in finding:
                assert finding["physical_test_status"] == "NOT_RUN", \
                    f"Finding {finding['id']} physical test should be NOT_RUN"
    
    def test_gate_decision_cannot_be_pass(self):
        """QA gate decision must not be PASS."""
        summary = get_findings_summary()
        assert summary["gate_status"] != "PASS"
        assert summary["gate_status"] == "BLOCKED"
    
    def test_procurement_not_ready(self):
        """Procurement decision should be NOT_READY."""
        assert QA_REVIEW_METADATA["decision"]["procurement"] == "NOT_READY"
    
    def test_product_release_not_ready(self):
        """Product release should be NOT_READY."""
        assert QA_REVIEW_METADATA["decision"]["product_release"] == "NOT_READY"
