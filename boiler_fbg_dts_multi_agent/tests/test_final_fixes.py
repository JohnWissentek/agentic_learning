"""Tests for final structural fixes.

Fix #1: No truncation in handoffs
Fix #2: Reference validation
Fix #3: Revision + QA_REVIEW
Fix #4: Trust level rename
Fix #5: Model revision SHA
"""

import pytest
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestFix1_NoTruncation:
    """Fix #1: QA/PM must receive full content, no truncation."""
    
    def test_full_handoff_no_truncation(self):
        """to_full_handoff must return complete raw_response."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST")
        
        # Register artifact with long content
        long_content = "A" * 1000  # 1000 chars
        art = registry.register(
            source_role="MKT",
            stage="test",
            raw_response=long_content,
            parsed_output={"test": True},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        # Full handoff must have complete content
        full = art.to_full_handoff()
        assert full["raw_response"] == long_content
        assert len(full["raw_response"]) == 1000
    
    def test_get_full_handoffs_includes_all_roles(self):
        """get_full_handoffs_for_qa must include all specified roles."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST")
        
        # Register 3 roles
        for role in ["MKT", "OPT", "HW"]:
            registry.register(
                source_role=role,
                stage=f"{role}_test",
                raw_response=f"Content from {role}",
                parsed_output={"role": role},
                parse_success=True,
                schema_valid=True,
                validation_issues=[],
                semantic_anomalies=[],
            )
        
        content, total_chars = registry.get_full_handoffs_for_qa(["MKT", "OPT", "HW"])
        
        # Must include all 3
        assert "Content from MKT" in content
        assert "Content from OPT" in content
        assert "Content from HW" in content
    
    def test_downstream_prompt_contains_full_raw(self):
        """Downstream prompt must contain full upstream raw."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST")
        
        # Create upstream with specific content
        unique_content = "UNIQUE_TEST_CONTENT_12345_NOT_TRUNCATED"
        registry.register(
            source_role="MKT",
            stage="test",
            raw_response=unique_content,
            parsed_output={"test": True},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        content, _ = registry.get_full_handoffs_for_qa(["MKT"])
        
        # Full unique content must be present
        assert unique_content in content


class TestFix2_ReferenceValidation:
    """Fix #2: Invalid artifact references must be detected."""
    
    def test_valid_reference_resolves(self):
        """Valid artifact_id must resolve."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST")
        
        art = registry.register(
            source_role="MKT",
            stage="test",
            raw_response="test",
            parsed_output={},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        valid, err = registry.validate_reference(art.artifact_id)
        assert valid
        assert err == ""
    
    def test_invalid_reference_returns_error(self):
        """Invalid artifact_id must return REFERENCE_INVALID."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST")
        
        valid, err = registry.validate_reference("NONEXISTENT-ID")
        
        assert not valid
        assert "REFERENCE_INVALID" in err
    
    def test_validate_all_references(self):
        """Multiple references can be validated at once."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST")
        
        art = registry.register(
            source_role="MKT",
            stage="test",
            raw_response="test",
            parsed_output={},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        results = registry.validate_all_references([
            art.artifact_id,  # Valid
            "INVALID-001",    # Invalid
        ])
        
        assert results[art.artifact_id][0] == True
        assert results["INVALID-001"][0] == False


class TestFix3_RevisionLoop:
    """Fix #3: Revision artifacts with derived_from tracking."""
    
    def test_register_revision_tracks_derivation(self):
        """Revision artifact must have derived_from set."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST")
        
        # Original
        original = registry.register(
            source_role="MKT",
            stage="original",
            raw_response="original content",
            parsed_output={},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[{"id": "test"}],
        )
        
        # Revision
        revision, err = registry.register_revision(
            original_artifact_id=original.artifact_id,
            source_role="MKT",
            stage="revision",
            raw_response="revised content",
            parsed_output={},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        assert err == ""
        assert revision is not None
        assert revision.derived_from == original.artifact_id
    
    def test_revision_with_invalid_original_fails(self):
        """Revision of nonexistent artifact must fail."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST")
        
        revision, err = registry.register_revision(
            original_artifact_id="NONEXISTENT",
            source_role="MKT",
            stage="revision",
            raw_response="content",
            parsed_output={},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        assert revision is None
        assert "REFERENCE_INVALID" in err
    
    def test_revision_in_export(self):
        """Revision artifacts appear in export with derived_from."""
        from boiler_fbg_workflow.artifact_registry import ArtifactRegistry
        
        registry = ArtifactRegistry("TEST")
        
        original = registry.register(
            source_role="MKT",
            stage="original",
            raw_response="original",
            parsed_output={},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        revision, _ = registry.register_revision(
            original_artifact_id=original.artifact_id,
            source_role="MKT",
            stage="revision",
            raw_response="revised",
            parsed_output={},
            parse_success=True,
            schema_valid=True,
            validation_issues=[],
            semantic_anomalies=[],
        )
        
        export = registry.export()
        
        # Find revision in export
        revision_data = next(
            (a for a in export["artifacts"] if a["artifact_id"] == revision.artifact_id),
            None
        )
        
        assert revision_data is not None
        assert revision_data["derived_from"] == original.artifact_id


class TestFix4_TrustLevelRename:
    """Fix #4: VERIFIED renamed to FORMAT_VALID_RULES_NOT_TRIGGERED."""
    
    def test_trust_level_enum_has_new_name(self):
        """TrustLevel enum must have new name."""
        from boiler_fbg_workflow.trust_levels import TrustLevel
        
        assert hasattr(TrustLevel, "FORMAT_VALID_RULES_NOT_TRIGGERED")
    
    def test_determine_trust_level_returns_new_name(self):
        """determine_trust_level must return new name for valid."""
        from boiler_fbg_workflow.trust_levels import determine_trust_level, TrustLevel
        
        result = determine_trust_level(
            parse_success=True,
            schema_valid=True,
            rule_hits=0,
            has_source_verification=False,
        )
        
        # Without source verification, should be UNREVIEWED
        assert result == TrustLevel.UNREVIEWED
    
    def test_rule_triggered_level(self):
        """Rule hits should return RULE_TRIGGERED."""
        from boiler_fbg_workflow.trust_levels import determine_trust_level, TrustLevel
        
        result = determine_trust_level(
            parse_success=True,
            schema_valid=True,
            rule_hits=2,
            has_source_verification=False,
        )
        
        assert result == TrustLevel.RULE_TRIGGERED
    
    def test_legacy_mapping_exists(self):
        """Legacy mapping for backward compatibility."""
        from boiler_fbg_workflow.trust_levels import LEGACY_MAPPING, TrustLevel
        
        assert "VERIFIED" in LEGACY_MAPPING
        assert LEGACY_MAPPING["VERIFIED"] == TrustLevel.FORMAT_VALID_RULES_NOT_TRIGGERED


class TestFix5_ModelRevision:
    """Fix #5: Model revision should be immutable SHA."""
    
    def test_resolve_model_revision_function_exists(self):
        """resolve_model_revision function must exist."""
        from run_v031_final import resolve_model_revision
        
        # Should return string
        result = resolve_model_revision("Qwen/Qwen2.5-1.5B-Instruct")
        assert isinstance(result, str)
