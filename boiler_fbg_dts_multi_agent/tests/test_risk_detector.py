"""Additional tests for risk detector edge cases."""

import pytest
from datetime import datetime

from boiler_fbg_workflow.temperature_app.risk_detector import (
    RiskDetector,
    RiskThresholds,
    ChannelHistory,
)
from boiler_fbg_workflow.schemas import TemperatureReading


class TestChannelHistory:
    """Tests for channel history tracking."""
    
    def test_history_limit(self):
        history = ChannelHistory(max_history=10)
        
        for i in range(20):
            history.add(float(i), f"t{i}")
        
        assert len(history.temperatures) == 10
        assert history.temperatures[0] == 10.0  # First 10 were dropped
    
    def test_rate_of_change_calculation(self):
        history = ChannelHistory()
        
        # Add increasing temperatures (10°C each, 100ms apart = 100°C/s)
        for i in range(10):
            history.add(350.0 + i * 10, f"t{i}")
        
        rate = history.get_rate_of_change(window=10)
        
        # Rate should be approximately 100°C/s (simplified calculation)
        assert rate > 0  # Temperature increasing
    
    def test_drift_calculation(self):
        history = ChannelHistory()
        
        # Add constant values
        for i in range(100):
            history.add(350.0, f"t{i}")
        
        drift = history.get_drift(window=100)
        assert abs(drift) < 0.01  # No drift for constant values
        
        # Add a shifted value
        history.add(360.0, "t100")
        drift = history.get_drift(window=100)
        assert drift > 0  # Positive drift


class TestRiskDetectorEdgeCases:
    """Edge case tests for risk detector."""
    
    @pytest.fixture
    def detector(self):
        return RiskDetector()
    
    def test_empty_readings(self, detector):
        alerts = detector.analyze([])
        assert len(alerts) == 0
    
    def test_nan_temperature_ignored(self, detector):
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=float('nan'),
                timestamp=datetime.now().isoformat(),
                quality_flag="missing",
                data_source="[SYNTHETIC]",
            )
        ]
        
        alerts = detector.analyze(readings)
        
        # NaN should be skipped, no over-temp alert
        over_temp = [a for a in alerts if a.alert_type == "over_temp"]
        assert len(over_temp) == 0
    
    def test_bad_quality_skipped(self, detector):
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=600.0,  # Would trigger alert if not bad quality
                timestamp=datetime.now().isoformat(),
                quality_flag="bad",
                data_source="[SYNTHETIC]",
            )
        ]
        
        alerts = detector.analyze(readings)
        
        # Bad quality readings should be skipped
        over_temp = [a for a in alerts if a.alert_type == "over_temp"]
        assert len(over_temp) == 0
    
    def test_gradient_needs_multiple_channels(self, detector):
        # Single channel - no gradient possible
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=350.0,
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
        ]
        
        alerts = detector.analyze(readings)
        
        gradient_alerts = [a for a in alerts if a.alert_type == "gradient_high"]
        assert len(gradient_alerts) == 0
    
    def test_statistics_tracking(self, detector):
        readings = [
            TemperatureReading(
                channel_id=i,
                position_m=i * 0.5,
                temperature_c=350.0 + i * 10,
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
            for i in range(8)
        ]
        
        detector.analyze(readings)
        stats = detector.get_statistics()
        
        assert stats["channels_tracked"] == 8


class TestAlertMessage:
    """Tests for alert message content."""
    
    def test_message_contains_channel_info(self):
        detector = RiskDetector()
        
        readings = [
            TemperatureReading(
                channel_id=5,
                position_m=2.5,
                temperature_c=550.0,
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
        ]
        
        alerts = detector.analyze(readings)
        
        assert len(alerts) > 0
        assert "通道5" in alerts[0].message or "5" in alerts[0].message
    
    def test_recommended_action_is_advisory(self):
        detector = RiskDetector()
        
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=550.0,
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
        ]
        
        alerts = detector.analyze(readings)
        
        for alert in alerts:
            # All actions should be advisory, not commands
            assert "建议" in alert.recommended_action
            # Should mention human confirmation
            assert "人工" in alert.recommended_action or "确认" in alert.recommended_action
