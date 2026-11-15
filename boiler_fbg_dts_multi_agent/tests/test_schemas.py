"""Tests for data schemas."""

import pytest
from pydantic import ValidationError

from boiler_fbg_workflow.schemas import (
    EvidenceRecord,
    EvidenceType,
    MarketSizingResult,
    TechnicalRequirement,
    FBGSensorSpec,
    BOMItem,
    CostBreakdown,
    QAIssue,
    QAReviewResult,
    GateStatus,
    IssueSeverity,
    StageCode,
    RoleCode,
    TemperatureReading,
    TemperatureAlert,
)


class TestEvidenceRecord:
    """Tests for EvidenceRecord schema."""
    
    def test_valid_evidence_record(self):
        record = EvidenceRecord(
            ev_id="[EV-LIT-001]",
            ev_type=EvidenceType.LITERATURE,
            title="Test Paper",
            source="IEEE",
        )
        assert record.ev_id == "[EV-LIT-001]"
        assert record.status == "PENDING_VERIFICATION"
    
    def test_invalid_evidence_id_format(self):
        with pytest.raises(ValidationError):
            EvidenceRecord(
                ev_id="invalid-format",
                ev_type=EvidenceType.LITERATURE,
                title="Test",
                source="Test",
            )


class TestMarketSizingResult:
    """Tests for MarketSizingResult schema."""
    
    def test_valid_market_sizing(self):
        result = MarketSizingResult(
            segment_id="SEG-001",
            horizon="2026-2028",
            tam_units=100,
            tam_cny_wan=10000.0,
            sam_units=40,
            sam_cny_wan=4000.0,
            som_units=10,
            som_cny_wan=1000.0,
            assumptions="Test assumptions",
        )
        assert result.calc_tag == "[MKT-CALC]"
        assert result.tam_units == 100
    
    def test_negative_values_rejected(self):
        with pytest.raises(ValidationError):
            MarketSizingResult(
                segment_id="SEG-001",
                horizon="2026-2028",
                tam_units=-100,  # Negative not allowed
                tam_cny_wan=10000.0,
                sam_units=40,
                sam_cny_wan=4000.0,
                som_units=10,
                som_cny_wan=1000.0,
                assumptions="Test",
            )


class TestFBGSensorSpec:
    """Tests for FBGSensorSpec schema."""
    
    def test_default_pending_verification(self):
        spec = FBGSensorSpec(
            spec_id="FBG-001",
            max_temperature_c=600.0,
            long_term_drift_c_year=0.5,
        )
        assert "[PENDING]" in spec.vendor
        assert len(spec.pending_verification) > 0
    
    def test_wavelength_range(self):
        # Valid wavelength
        spec = FBGSensorSpec(
            spec_id="FBG-001", 
            wavelength_nm=1550.0,
            max_temperature_c=600.0,
            long_term_drift_c_year=0.5,
        )
        assert spec.wavelength_nm == 1550.0
        
        # Invalid wavelength (out of range)
        with pytest.raises(ValidationError):
            FBGSensorSpec(
                spec_id="FBG-001", 
                wavelength_nm=500.0,
                max_temperature_c=600.0,
                long_term_drift_c_year=0.5,
            )


class TestCostBreakdown:
    """Tests for CostBreakdown schema."""
    
    def test_auto_compute_total(self):
        breakdown = CostBreakdown(
            tier="mvp_prototype",
            hardware_cost_cny=50000.0,
            software_cost_cny=30000.0,
            integration_cost_cny=10000.0,
            testing_cost_cny=10000.0,
            contingency_pct=20.0,
            total_cost_cny=0.0,  # Will be computed
        )
        # Total should be (50000 + 30000 + 10000 + 10000) * 1.2 = 120000
        assert breakdown.total_cost_cny == 120000.0


class TestQAReviewResult:
    """Tests for QAReviewResult schema."""
    
    def test_issue_counts(self):
        review = QAReviewResult(
            review_id="QA-001",
            stage=StageCode.STAGE_0_REQUIREMENTS,
            overall_assessment="Test review",
            issues=[
                QAIssue(
                    issue_id="ISS-001",
                    stage=StageCode.STAGE_0_REQUIREMENTS,
                    role_source=RoleCode.QA,
                    severity=IssueSeverity.CRITICAL,
                    title="Critical issue",
                    description="Test",
                    required_action="Fix it",
                    assigned_to=RoleCode.PM,
                ),
                QAIssue(
                    issue_id="ISS-002",
                    stage=StageCode.STAGE_0_REQUIREMENTS,
                    role_source=RoleCode.QA,
                    severity=IssueSeverity.MAJOR,
                    title="Major issue",
                    description="Test",
                    required_action="Fix it",
                    assigned_to=RoleCode.MKT,
                ),
            ],
            gate_status=GateStatus.BLOCKED,
        )
        assert review.critical_count == 1
        assert review.major_count == 1


class TestTemperatureReading:
    """Tests for TemperatureReading schema."""
    
    def test_valid_reading(self):
        reading = TemperatureReading(
            channel_id=0,
            position_m=0.5,
            temperature_c=380.0,
            timestamp="2026-11-15T12:00:00",
        )
        assert reading.quality_flag == "good"
        assert reading.data_source == "synthetic"
    
    def test_quality_flags(self):
        for flag in ["good", "suspect", "bad", "missing"]:
            reading = TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=350.0,
                timestamp="2026-11-15T12:00:00",
                quality_flag=flag,
            )
            assert reading.quality_flag == flag


class TestTemperatureAlert:
    """Tests for TemperatureAlert schema."""
    
    def test_valid_alert(self):
        alert = TemperatureAlert(
            alert_id="ALERT-001",
            alert_type="over_temp",
            severity="warning",
            current_value=485.0,
            threshold_value=480.0,
            message="Over temperature warning",
            recommended_action="Check cooling",
            timestamp="2026-11-15T12:00:00",
        )
        assert alert.acknowledged is False
        assert alert.ack_by == ""
