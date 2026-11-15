"""Tests for temperature monitoring application prototype."""

import math
import pytest
from datetime import datetime

from boiler_fbg_workflow.temperature_app.adapters import (
    SimulatedDemodulator,
    ChannelStatus,
)
from boiler_fbg_workflow.temperature_app.data_generator import (
    SyntheticDataGenerator,
    DataGeneratorConfig,
)
from boiler_fbg_workflow.temperature_app.risk_detector import (
    RiskDetector,
    RiskThresholds,
)
from boiler_fbg_workflow.temperature_app.quality_flags import (
    QualityAnalyzer,
    QualityThresholds,
)
from boiler_fbg_workflow.schemas import TemperatureReading


class TestSimulatedDemodulator:
    """Tests for simulated demodulator adapter."""
    
    def test_connect_disconnect(self):
        demod = SimulatedDemodulator(channel_count=32)
        assert not demod.is_connected()
        
        assert demod.connect({})
        assert demod.is_connected()
        
        demod.disconnect()
        assert not demod.is_connected()
    
    def test_channel_count(self):
        demod = SimulatedDemodulator(channel_count=64)
        demod.connect({})
        assert demod.get_channel_count() == 64
    
    def test_read_all_channels(self):
        demod = SimulatedDemodulator(channel_count=16)
        demod.connect({})
        
        readings = demod.read_all_channels()
        assert len(readings) == 16
        
        for i, reading in enumerate(readings):
            assert reading.channel_id == i
            assert reading.status == ChannelStatus.OK
            assert "[SYNTHETIC]" in reading.data_source
    
    def test_read_without_connect(self):
        demod = SimulatedDemodulator()
        readings = demod.read_all_channels()
        assert len(readings) == 0


class TestSyntheticDataGenerator:
    """Tests for synthetic data generator."""
    
    def test_generate_single_sample(self):
        generator = SyntheticDataGenerator()
        readings = generator.generate_single_sample()
        
        assert len(readings) == 64  # Default channel count
        
        for reading in readings:
            assert "[SYNTHETIC]" in reading.data_source
            assert isinstance(reading.temperature_c, float)
    
    def test_custom_channel_count(self):
        config = DataGeneratorConfig(channel_count=32)
        generator = SyntheticDataGenerator(config)
        readings = generator.generate_single_sample()
        
        assert len(readings) == 32
    
    def test_generate_time_series(self):
        config = DataGeneratorConfig(channel_count=8, sample_interval_ms=100)
        generator = SyntheticDataGenerator(config)
        
        # Generate 1 second of data (10 samples at 100ms interval)
        samples = list(generator.generate_time_series(1.0))
        
        assert len(samples) == 10
        for sample in samples:
            assert len(sample) == 8
    
    def test_anomaly_injection(self):
        config = DataGeneratorConfig(
            channel_count=8,
            inject_over_temp_prob=0.5,  # High probability for testing
            inject_data_gap_prob=0.3,
        )
        generator = SyntheticDataGenerator(config)
        
        # Generate multiple samples
        all_readings = []
        for _ in range(100):
            all_readings.extend(generator.generate_single_sample())
        
        # Check that some anomalies were injected
        high_temps = [r for r in all_readings if r.temperature_c > 500]
        missing_data = [r for r in all_readings if r.quality_flag == "missing"]
        
        # With high probabilities, we should see some anomalies
        assert len(high_temps) > 0 or len(missing_data) > 0
    
    def test_inject_fiber_break(self):
        generator = SyntheticDataGenerator()
        readings = generator.generate_single_sample()
        
        # Inject fiber break at 10m
        broken_readings = generator.inject_fiber_break(readings, break_position_m=10.0)
        
        # Channels after 10m should be bad
        for reading in broken_readings:
            if reading.position_m > 10.0:
                assert reading.quality_flag == "bad"
                assert math.isnan(reading.temperature_c)


class TestRiskDetector:
    """Tests for risk detection algorithms."""
    
    @pytest.fixture
    def detector(self):
        thresholds = RiskThresholds(
            over_temp_warning_c=450.0,
            over_temp_alarm_c=480.0,
            over_temp_critical_c=500.0,
            fast_rise_warning_rate=10.0,
            fast_rise_alarm_rate=20.0,
        )
        return RiskDetector(thresholds)
    
    def test_no_alerts_for_normal_data(self, detector):
        readings = [
            TemperatureReading(
                channel_id=i,
                position_m=i * 0.5,
                temperature_c=380.0,
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
            for i in range(8)
        ]
        
        alerts = detector.analyze(readings)
        
        # No alerts for normal temperatures
        over_temp_alerts = [a for a in alerts if a.alert_type == "over_temp"]
        assert len(over_temp_alerts) == 0
    
    def test_over_temp_warning(self, detector):
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=460.0,  # Above warning threshold
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
        ]
        
        alerts = detector.analyze(readings)
        
        over_temp = [a for a in alerts if a.alert_type == "over_temp"]
        assert len(over_temp) == 1
        assert over_temp[0].severity == "warning"
    
    def test_over_temp_critical(self, detector):
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=520.0,  # Above critical threshold
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
        ]
        
        alerts = detector.analyze(readings)
        
        critical = [a for a in alerts if a.severity == "critical"]
        assert len(critical) == 1
    
    def test_gradient_detection(self, detector):
        # Create readings with high gradient between adjacent channels
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=350.0,
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            ),
            TemperatureReading(
                channel_id=1,
                position_m=0.5,  # 0.5m apart
                temperature_c=450.0,  # 100°C difference = 200°C/m gradient
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            ),
        ]
        
        alerts = detector.analyze(readings)
        
        gradient_alerts = [a for a in alerts if a.alert_type == "gradient_high"]
        assert len(gradient_alerts) > 0
    
    def test_recommended_action_present(self, detector):
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=510.0,
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
        ]
        
        alerts = detector.analyze(readings)
        
        for alert in alerts:
            assert alert.recommended_action
            assert "建议" in alert.recommended_action


class TestQualityAnalyzer:
    """Tests for quality analysis."""
    
    @pytest.fixture
    def analyzer(self):
        return QualityAnalyzer()
    
    def test_good_quality_data(self, analyzer):
        readings = [
            TemperatureReading(
                channel_id=i,
                position_m=i * 0.5,
                temperature_c=380.0,
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
            for i in range(8)
        ]
        
        flagged, alerts = analyzer.analyze(readings)
        
        # All should be good
        assert all(r.quality_flag == "good" for r in flagged)
    
    def test_detect_missing_data(self, analyzer):
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=float('nan'),  # Missing data
                timestamp=datetime.now().isoformat(),
                quality_flag="missing",
                data_source="[SYNTHETIC]",
            )
        ]
        
        flagged, alerts = analyzer.analyze(readings)
        
        assert flagged[0].quality_flag in ("bad", "missing")
    
    def test_signal_loss_alert(self, analyzer):
        # Create readings where most are bad
        readings = [
            TemperatureReading(
                channel_id=i,
                position_m=i * 0.5,
                temperature_c=float('nan') if i > 1 else 380.0,
                timestamp=datetime.now().isoformat(),
                quality_flag="bad" if i > 1 else "good",
                data_source="[SYNTHETIC]",
            )
            for i in range(10)
        ]
        
        _, alerts = analyzer.analyze(readings)
        
        signal_loss = [a for a in alerts if a.alert_type == "signal_loss"]
        assert len(signal_loss) > 0
    
    def test_out_of_range_flagged(self, analyzer):
        readings = [
            TemperatureReading(
                channel_id=0,
                position_m=0.0,
                temperature_c=900.0,  # Above max valid range
                timestamp=datetime.now().isoformat(),
                data_source="[SYNTHETIC]",
            )
        ]
        
        flagged, _ = analyzer.analyze(readings)
        
        assert flagged[0].quality_flag == "suspect"
    
    def test_quality_summary(self, analyzer):
        readings = [
            TemperatureReading(
                channel_id=i,
                position_m=i * 0.5,
                temperature_c=380.0,
                timestamp=datetime.now().isoformat(),
                quality_flag="good" if i < 8 else "bad",
                data_source="[SYNTHETIC]",
            )
            for i in range(10)
        ]
        
        flagged, _ = analyzer.analyze(readings)
        summary = analyzer.get_quality_summary(flagged)
        
        assert summary["total_channels"] == 10
        assert "quality_distribution" in summary
