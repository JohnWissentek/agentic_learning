"""Regression tests for v0.2 research data changes.

These tests ensure that v0.1 incorrect conclusions cannot resurface:
1. Technica T885/T890 must NOT be recommended as primary/backup
2. "5.73 > 5 means measured bias exceeds target" must NOT appear
3. Link margin must be UNKNOWN, not calculated as 35-20.27
4. CEZB260106803 must be identified as header FBG, not water-wall
5. Wavelength start must be 1485nm not 1470nm
"""

import pytest
import json
from pathlib import Path

from boiler_fbg_workflow.research_data import (
    RESEARCH_VERSION,
    VENDOR_SPECS,
    ENGINEERING_CALCULATIONS,
    RECOMMENDED_SCENARIO,
    RISK_REGISTER,
    get_qa_gate_decision,
    get_revoked_conclusions,
)


class TestV02RevokedConclusions:
    """Regression tests: v0.1 revoked conclusions must not appear."""
    
    def test_technica_not_primary_selection(self):
        """Technica T890 must NOT be primary sensor selection."""
        t890 = VENDOR_SPECS.get("technica_t890", {})
        
        assert t890.get("v0_2_status") == "REVOKED_FROM_MAIN_SELECTION"
        assert t890.get("release_status") == "NOT_SELECTED"
        assert "REVOKED" in t890.get("source_status", "")
    
    def test_technica_not_backup_selection(self):
        """Technica T885 must NOT be backup sensor selection."""
        t885 = VENDOR_SPECS.get("technica_t885", {})
        
        assert t885.get("v0_2_status") == "REVOKED_FROM_MAIN_SELECTION"
        assert t885.get("release_status") == "NOT_SELECTED"
        assert "REVOKED" in t885.get("source_status", "")
    
    def test_recommended_scenario_technica_revoked(self):
        """Recommended scenario must show Technica as REVOKED."""
        assert "REVOKED" in RECOMMENDED_SCENARIO.get("technica_status", "")
        assert RECOMMENDED_SCENARIO.get("sensor_field_array") == "NOT_SELECTED"
    
    def test_uncertainty_not_measured_bias(self):
        """U=5.728 must NOT be described as measured bias > target.
        
        v0.1 ERROR: "5.73°C > 5°C means actual measured deviation exceeded target"
        v0.2 CORRECT: "U is uncertainty budget, guardband |e|+U≤MPE cannot accept"
        The conclusion must CLARIFY that U is not measured bias, using negation.
        """
        ub = ENGINEERING_CALCULATIONS.get("uncertainty_budget", {})
        
        # Check correct definition
        assert "uc" in str(ub.get("lab_uc_standard_k1_C", "")).lower() or ub.get("lab_uc_standard_k1_C") is not None
        assert ub.get("field_U_k2_C") == 5.728 or abs(ub.get("field_U_k2_C", 0) - 5.728) < 0.01
        
        # Check conclusion CLARIFIES that U is not measured bias (using negation)
        conclusion = ub.get("conclusion", "")
        # The correct form is "这不代表实测偏差已超过" (This does NOT mean measured bias exceeded)
        assert "不代表" in conclusion, "Conclusion must clarify U is not measured bias"
        
        # Check v0.1 error retracted
        assert "v0.1" in ub.get("v0_1_error_retracted", "").lower() or "撤销" in ub.get("v0_1_error_retracted", "")
    
    def test_link_margin_unknown(self):
        """Link margin must be UNKNOWN, not calculated as 35dB - 20.27dB."""
        opb = ENGINEERING_CALCULATIONS.get("optical_power_budget", {})
        
        assert opb.get("link_margin_dB") is None
        assert opb.get("link_margin_status") == "UNKNOWN"
        assert "UNKNOWN" in opb.get("margin_note", "")
    
    def test_wavelength_start_1485(self):
        """Wavelength start must be 1485nm, not 1470nm."""
        wb = ENGINEERING_CALCULATIONS.get("wavelength_budget", {})
        
        assert wb.get("lambda_start_nm") == 1485
        assert wb.get("centers_nm", [0])[0] == 1485.0
        assert wb.get("first_peak_worst_low_nm", 0) > 1480  # Must be above 1480
    
    def test_fisens_is_rfq_priority(self):
        """FiSens 1550 must be RFQ priority, not Technica."""
        fisens = VENDOR_SPECS.get("fisens_1550", {})
        
        assert fisens.get("v0_2_status") == "LAB_RFQ_PRIORITY"
        assert "FiSens" in RECOMMENDED_SCENARIO.get("sensor_lab_rfq_priority", "")
    
    def test_calsens_is_second_rfq(self):
        """CALSENS must be second RFQ source."""
        calsens = VENDOR_SPECS.get("calsens_ht", {})
        
        assert calsens.get("v0_2_status") == "SECOND_RFQ_SOURCE"
    
    def test_osensa_is_contrast_system(self):
        """OSENSA must be non-FBG independent contrast, not replacement."""
        osensa = VENDOR_SPECS.get("osensa_prb1000ht", {})
        
        assert osensa.get("v0_2_status") == "INDEPENDENT_NON_FBG_CONTRAST"
        assert "非FBG" in osensa.get("note", "")
    
    def test_all_revoked_conclusions_listed(self):
        """All revoked conclusions must be documented."""
        revoked = get_revoked_conclusions()
        
        assert len(revoked) >= 6
        
        revoked_ids = {r["revoked_id"] for r in revoked}
        assert "REV-001" in revoked_ids  # T890 revoked
        assert "REV-002" in revoked_ids  # T885 revoked
        assert "REV-003" in revoked_ids  # Uncertainty wording
        assert "REV-004" in revoked_ids  # Link margin
        assert "REV-005" in revoked_ids  # Wavelength
        assert "REV-006" in revoked_ids  # CEZB260106803


class TestV02QAGateDecision:
    """Tests for QA gate decision correctness."""
    
    def test_qa_gate_blocked(self):
        """QA gate must return BLOCKED status."""
        decision = get_qa_gate_decision()
        
        assert decision["gate_status"] == "BLOCKED"
    
    def test_qa_includes_uncertainty_clarification(self):
        """QA decision must clarify uncertainty is not measured bias."""
        decision = get_qa_gate_decision()
        
        clarification = decision.get("v0_2_clarification", "")
        assert "不确定度" in clarification or "预算" in clarification
        assert "实测偏差" in clarification or "不代表" in clarification
    
    def test_qa_includes_technica_revocation(self):
        """QA decision must mention Technica revocation."""
        decision = get_qa_gate_decision()
        
        rationale = decision.get("decision_rationale", "")
        assert "撤销" in rationale or "NOT_SELECTED" in rationale
    
    def test_qa_includes_link_margin_unknown(self):
        """QA decision must mention link margin UNKNOWN."""
        decision = get_qa_gate_decision()
        
        rationale = decision.get("decision_rationale", "")
        assert "UNKNOWN" in rationale or "链路余量" in rationale


class TestV02EvidenceIntegrity:
    """Tests for evidence data integrity."""
    
    def test_research_version_is_v02(self):
        """Research version must be v0.2."""
        assert RESEARCH_VERSION == "v0.2"
    
    def test_evidence_ledger_file_exists(self):
        """Evidence ledger JSON must exist."""
        ledger_path = Path(__file__).parent.parent / "evidence_registry" / "evidence_ledger.json"
        assert ledger_path.exists(), f"Evidence ledger not found at {ledger_path}"
    
    def test_evidence_ledger_valid_json(self):
        """Evidence ledger must be valid JSON."""
        ledger_path = Path(__file__).parent.parent / "evidence_registry" / "evidence_ledger.json"
        
        with open(ledger_path) as f:
            data = json.load(f)
        
        assert isinstance(data, list)
        assert len(data) >= 17  # v0.2 has E01-E22
    
    def test_evidence_ledger_has_v02_entries(self):
        """Evidence ledger must include v0.2 new entries E17-E22."""
        ledger_path = Path(__file__).parent.parent / "evidence_registry" / "evidence_ledger.json"
        
        with open(ledger_path) as f:
            data = json.load(f)
        
        evidence_ids = {e.get("evidence_id") for e in data}
        
        # v0.2 new entries
        assert "E17" in evidence_ids  # FiSens
        assert "E18" in evidence_ids  # CALSENS
        assert "E19" in evidence_ids  # OSENSA
        assert "E20" in evidence_ids  # CEZB260106803
        assert "E22" in evidence_ids  # Link margin UNKNOWN
    
    def test_e08_shows_technica_revoked(self):
        """E08 must show Technica revocation in v0.2."""
        ledger_path = Path(__file__).parent.parent / "evidence_registry" / "evidence_ledger.json"
        
        with open(ledger_path) as f:
            data = json.load(f)
        
        e08 = next((e for e in data if e.get("evidence_id") == "E08"), None)
        assert e08 is not None
        
        limitation = e08.get("limitation", "")
        assert "v0.2" in limitation or "撤销" in limitation or "REVOKED" in limitation.upper()
    
    def test_e12_shows_uncertainty_clarification(self):
        """E12 must show uncertainty clarification."""
        ledger_path = Path(__file__).parent.parent / "evidence_registry" / "evidence_ledger.json"
        
        with open(ledger_path) as f:
            data = json.load(f)
        
        e12 = next((e for e in data if e.get("evidence_id") == "E12"), None)
        assert e12 is not None
        
        # Must have standard uc and expanded U
        claim = e12.get("claim", "")
        limitation = e12.get("limitation", "")
        assert "uc" in claim or "U(k=2)" in claim or "标准" in claim
        assert "不代表实测" in limitation or "预算假设" in limitation


class TestNoHardcodedV01Values:
    """Ensure no hardcoded v0.1 values remain."""
    
    def test_no_1470_wavelength(self):
        """No 1470nm wavelength start."""
        wb = ENGINEERING_CALCULATIONS.get("wavelength_budget", {})
        
        centers = wb.get("centers_nm", [])
        assert 1470.0 not in centers
        assert wb.get("lambda_start_nm") != 1470
    
    def test_no_direct_margin_calculation(self):
        """No 35dB - 20.27dB = margin calculation."""
        opb = ENGINEERING_CALCULATIONS.get("optical_power_budget", {})
        
        # If margin were calculated incorrectly, it would be ~14.7dB
        margin = opb.get("link_margin_dB")
        assert margin is None or margin != pytest.approx(14.7, abs=0.5)
    
    def test_no_technica_in_selection(self):
        """No Technica as selected sensor."""
        assert "Technica" not in RECOMMENDED_SCENARIO.get("sensor_lab_rfq_priority", "")
        assert "Technica" not in RECOMMENDED_SCENARIO.get("sensor_second_rfq", "")
        assert "T890" not in RECOMMENDED_SCENARIO.get("sensor_lab_rfq_priority", "")
        assert "T885" not in RECOMMENDED_SCENARIO.get("sensor_second_rfq", "")
