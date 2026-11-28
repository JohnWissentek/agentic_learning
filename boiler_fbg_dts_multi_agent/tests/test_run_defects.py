"""Regression tests for RUN-01 through RUN-04 defects.

These tests verify the fixes for specific issues found in independent audit.
"""

import pytest
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestRUN01_StrictRootParse:
    """RUN-01: PM with // comments must fail parse, not silently extract inner."""
    
    # Exact negative case from audit
    PM_WITH_COMMENTS = '''```json
{
  "output_summary": {
    "文档纠正": "10项已完成",
    "工程验证": {
      "状态": "PASS"  // 这是错误的
    }
  },
  "rework_items": [
    // 需要返工的项目
    {"role": "OPT"}
  ],
  "action_plan": "继续"
}
```'''
    
    def test_pm_with_comments_must_fail_parse(self):
        """JSON with // comments must fail strict parse."""
        from boiler_fbg_workflow.strict_json_parser import strict_parse_json
        
        result = strict_parse_json(self.PM_WITH_COMMENTS)
        
        # Must NOT succeed
        assert not result.success, "PM with // comments must fail parse"
        assert result.had_js_comments, "Must detect JS comments"
    
    def test_pm_with_comments_detects_pass_anomaly(self):
        """Even on parse failure, must detect PASS semantic anomaly."""
        from boiler_fbg_workflow.strict_json_parser import strict_parse_json
        
        result = strict_parse_json(self.PM_WITH_COMMENTS)
        
        # Must detect engineering PASS anomaly
        pass_anomalies = [a for a in result.semantic_anomalies 
                         if a.anomaly_id == "engineering_pass"]
        assert len(pass_anomalies) > 0, "Must detect engineering PASS anomaly in raw"
    
    def test_no_partial_extraction_on_failure(self):
        """Failed parse must not have partial parsed output."""
        from boiler_fbg_workflow.strict_json_parser import strict_parse_json
        
        result = strict_parse_json(self.PM_WITH_COMMENTS)
        
        assert not result.success
        assert result.parsed is None, "Failed parse must not have parsed output"


class TestRUN02_SemanticAnomalies:
    """RUN-02: Fabricated data must be detected as semantic anomalies."""
    
    def test_fabricated_price_detected(self):
        """MKT虚构价格必须被检测."""
        from boiler_fbg_workflow.strict_json_parser import strict_parse_json
        
        mkt_raw = '{"market_size": "UNKNOWN", "price": "$50,000-$100,000"}'
        result = strict_parse_json(mkt_raw)
        
        price_anomalies = [a for a in result.semantic_anomalies 
                          if a.anomaly_id == "fabricated_price"]
        assert len(price_anomalies) > 0, "Must detect fabricated price"
    
    def test_fabricated_company_detected(self):
        """虚构公司名必须被检测."""
        from boiler_fbg_workflow.strict_json_parser import strict_parse_json
        
        raw = '{"competitors": ["XYZ公司", "ABC Corp"]}'
        result = strict_parse_json(raw)
        
        company_anomalies = [a for a in result.semantic_anomalies 
                            if a.anomaly_id == "fabricated_company"]
        assert len(company_anomalies) > 0, "Must detect fabricated company"
    
    def test_wavelength_sufficient_detected(self):
        """OPT声称波长预算充足必须被检测."""
        from boiler_fbg_workflow.strict_json_parser import strict_parse_json
        
        opt_raw = '{"wavelength_budget": "当前波长预算充足，满足需求"}'
        result = strict_parse_json(opt_raw)
        
        anomalies = [a for a in result.semantic_anomalies 
                     if a.anomaly_id == "wavelength_sufficient"]
        assert len(anomalies) > 0, "Must detect wavelength sufficient claim"
    
    def test_customer_testimonials_detected(self):
        """SLS虚构客户证言必须被检测."""
        from boiler_fbg_workflow.strict_json_parser import strict_parse_json
        
        sls_raw = '{"available_materials": ["Customer testimonials", "case studies"]}'
        result = strict_parse_json(sls_raw)
        
        anomalies = [a for a in result.semantic_anomalies 
                     if a.anomaly_id == "customer_testimonials"]
        assert len(anomalies) > 0, "Must detect fabricated testimonials"
    
    def test_engineering_pass_detected(self):
        """PM声称10项工程PASS必须被检测."""
        from boiler_fbg_workflow.strict_json_parser import strict_parse_json
        
        pm_raw = '{"status": "10项工程验证: PASS"}'
        result = strict_parse_json(pm_raw)
        
        anomalies = [a for a in result.semantic_anomalies 
                     if a.anomaly_id == "engineering_pass"]
        assert len(anomalies) > 0, "Must detect engineering PASS claim"


class TestRUN03_ArtifactPassing:
    """RUN-03: QA/PM must receive actual upstream artifacts."""
    
    def test_artifact_registry_tracks_ids(self):
        """Artifact registry must generate unique IDs."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST-001")
        
        art1 = registry.register(
            source_role="MKT",
            stage="mkt_analysis",
            raw_response='{"test": 1}',
            parsed_output={"test": 1},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        art2 = registry.register(
            source_role="OPT",
            stage="opt_analysis",
            raw_response='{"test": 2}',
            parsed_output={"test": 2},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        assert art1.artifact_id != art2.artifact_id
        assert "MKT" in art1.artifact_id
        assert "OPT" in art2.artifact_id
    
    def test_qa_receives_upstream_artifact_ids(self):
        """QA must know which artifacts it should receive."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST-001")
        
        # Register upstream artifacts
        for role in ["MKT", "OPT", "HW"]:
            registry.register(
                source_role=role,
                stage=f"{role.lower()}_analysis",
                raw_response=f'{{"role": "{role}"}}',
                parsed_output={"role": role},
                parse_success=True,
                schema_valid=True,
                validation_issues=[],
                semantic_anomalies=[],
            )
        
        # Get expected inputs for QA
        qa_inputs = registry.get_input_artifact_ids("QA")
        
        assert len(qa_inputs) >= 3, "QA must receive upstream artifacts"
        assert any("MKT" in aid for aid in qa_inputs)
        assert any("OPT" in aid for aid in qa_inputs)
        assert any("HW" in aid for aid in qa_inputs)
    
    def test_quarantined_artifacts_tracked(self):
        """Artifacts with anomalies must be quarantined."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST-001")
        
        art = registry.register(
            source_role="MKT",
            stage="mkt_analysis",
            raw_response='fabricated data',
            parsed_output=None,
            parse_success=False,
            schema_valid=False,
            validation_issues=["parse failed"],
            semantic_anomalies=[{"id": "test", "severity": "HIGH"}],
        )
        
        assert art.trust_level == "QUARANTINED"
        assert len(registry.get_quarantined()) == 1


class TestRUN04_StageSchemas:
    """RUN-04: PM and PM_REWORK must have different schemas."""
    
    def test_pm_and_pm_rework_have_different_schemas(self):
        """PM and PM_REWORK schemas must be different."""
        from boiler_fbg_workflow.stage_schemas import get_schema
        
        pm_schema = get_schema("PM")
        rework_schema = get_schema("PM_REWORK")
        
        assert pm_schema.schema_id != rework_schema.schema_id
        assert pm_schema.required_fields != rework_schema.required_fields
    
    def test_pm_schema_has_correct_fields(self):
        """PM schema must require output_summary, rework_items, action_plan."""
        from boiler_fbg_workflow.stage_schemas import get_schema
        
        pm_schema = get_schema("PM")
        
        assert "output_summary" in pm_schema.required_fields
        assert "rework_items" in pm_schema.required_fields
        assert "action_plan" in pm_schema.required_fields
    
    def test_pm_rework_schema_has_correct_fields(self):
        """PM_REWORK schema must require trigger_output, trigger_reason, etc."""
        from boiler_fbg_workflow.stage_schemas import get_schema
        
        rework_schema = get_schema("PM_REWORK")
        
        assert "trigger_output" in rework_schema.required_fields
        assert "trigger_reason" in rework_schema.required_fields
        assert "correction_actions" in rework_schema.required_fields
        assert "needs_reqa" in rework_schema.required_fields
    
    def test_pm_rework_valid_output_passes(self):
        """Valid PM_REWORK output with correct fields must pass."""
        from boiler_fbg_workflow.stage_schemas import validate_against_schema
        
        valid_output = {
            "trigger_output": "ART-001-OPT-001",
            "trigger_reason": "缺少fwhm_analysis字段",
            "correction_actions": ["补充FWHM分析"],
            "needs_reqa": True,
        }
        
        is_valid, issues = validate_against_schema(valid_output, "PM_REWORK")
        assert is_valid, f"Valid PM_REWORK output should pass: {issues}"
    
    def test_pm_rework_with_pm_fields_fails(self):
        """PM_REWORK output with PM fields must fail."""
        from boiler_fbg_workflow.stage_schemas import validate_against_schema
        
        # Using PM fields instead of PM_REWORK fields
        wrong_output = {
            "output_summary": "summary",
            "rework_items": [],
            "action_plan": "plan",
        }
        
        is_valid, issues = validate_against_schema(wrong_output, "PM_REWORK")
        assert not is_valid, "PM_REWORK with PM fields should fail"


class TestSLSRequiredDisclosures:
    """Test SLS schema requires required_disclosures field."""
    
    def test_sls_requires_required_disclosures(self):
        """SLS schema must have required_disclosures field."""
        from boiler_fbg_workflow.stage_schemas import get_schema
        
        sls_schema = get_schema("SLS")
        assert "required_disclosures" in sls_schema.required_fields
    
    def test_sls_empty_disclosures_fails(self):
        """SLS with empty required_disclosures must fail."""
        from boiler_fbg_workflow.stage_schemas import validate_against_schema
        
        output = {
            "available_materials": ["brochure"],
            "forbidden_claims": ["false claims"],
            "required_disclosures": [],  # Empty!
        }
        
        is_valid, issues = validate_against_schema(output, "SLS")
        assert not is_valid, "SLS with empty required_disclosures should fail"


class TestFINStageRisks:
    """Test FIN schema requires non-empty stage_risks."""
    
    def test_fin_empty_stage_risks_fails(self):
        """FIN with empty stage_risks must fail."""
        from boiler_fbg_workflow.stage_schemas import validate_against_schema
        
        output = {
            "funding_gaps": ["A0 UNKNOWN"],
            "stage_risks": [],  # Empty!
            "competitiveness_status": "UNVERIFIED",
        }
        
        is_valid, issues = validate_against_schema(output, "FIN")
        assert not is_valid, "FIN with empty stage_risks should fail"
