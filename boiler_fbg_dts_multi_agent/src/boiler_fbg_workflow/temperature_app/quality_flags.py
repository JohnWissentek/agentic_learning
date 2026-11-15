"""Data Quality Analysis for FBG/DTS Measurements.

Detects data quality issues including:
- Missing data points (gaps)
- Signal loss / fiber breaks
- Sensor drift
- Noise anomalies
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
import math

from boiler_fbg_workflow.schemas import TemperatureAlert, TemperatureReading


@dataclass
class QualityThresholds:
    """Quality analysis thresholds."""
    # Gap detection
    max_consecutive_missing: int = 5
    
    # Signal loss detection
    min_valid_channels_pct: float = 0.8  # 80% channels must be valid
    
    # Noise detection
    noise_std_threshold_c: float = 10.0
    noise_window_samples: int = 20
    
    # Value range check
    min_valid_temp_c: float = 0.0
    max_valid_temp_c: float = 800.0


class QualityAnalyzer:
    """Analyze data quality and generate quality flags.
    
    Detects issues like:
    - Data gaps (missing samples)
    - Fiber breaks (multiple consecutive channels lost)
    - Signal loss
    - Excessive noise
    - Out-of-range values
    """
    
    def __init__(self, thresholds: QualityThresholds | None = None):
        self.thresholds = thresholds or QualityThresholds()
        self._missing_counts: dict[int, int] = {}
        self._value_history: dict[int, list[float]] = {}
        self._alert_counter = 0
    
    def _generate_alert_id(self) -> str:
        self._alert_counter += 1
        return f"QUAL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._alert_counter:04d}"
    
    def analyze(self, readings: list[TemperatureReading]) -> tuple[list[TemperatureReading], list[TemperatureAlert]]:
        """Analyze readings and apply quality flags.
        
        Args:
            readings: Input temperature readings
            
        Returns:
            Tuple of (updated readings with quality flags, generated alerts)
        """
        alerts = []
        timestamp = datetime.now().isoformat()
        updated_readings = []
        
        # Count valid vs invalid channels
        valid_count = 0
        total_count = len(readings)
        
        for reading in readings:
            new_flag = self._analyze_single(reading)
            
            # Update reading with new quality flag
            updated = TemperatureReading(
                channel_id=reading.channel_id,
                position_m=reading.position_m,
                temperature_c=reading.temperature_c,
                wavelength_shift_pm=reading.wavelength_shift_pm,
                strain_ue=reading.strain_ue,
                timestamp=reading.timestamp,
                quality_flag=new_flag,
                data_source=reading.data_source,
            )
            updated_readings.append(updated)
            
            if new_flag == "good":
                valid_count += 1
        
        # Check for global signal loss
        if total_count > 0:
            valid_pct = valid_count / total_count
            if valid_pct < self.thresholds.min_valid_channels_pct:
                alerts.append(TemperatureAlert(
                    alert_id=self._generate_alert_id(),
                    alert_type="signal_loss",
                    severity="critical",
                    channel_id=None,
                    position_m=None,
                    current_value=valid_pct * 100,
                    threshold_value=self.thresholds.min_valid_channels_pct * 100,
                    message=f"严重信号丢失！仅{valid_pct*100:.1f}%通道有效数据",
                    recommended_action="建议：检查光纤连接和解调仪状态。此为建议，需人工确认。",
                    timestamp=timestamp,
                ))
        
        # Check for fiber break pattern (consecutive missing channels)
        alerts.extend(self._check_fiber_break(updated_readings, timestamp))
        
        # Check for data gaps
        alerts.extend(self._check_data_gaps(timestamp))
        
        return updated_readings, alerts
    
    def _analyze_single(self, reading: TemperatureReading) -> str:
        """Analyze a single reading and return quality flag."""
        channel_id = reading.channel_id
        
        # Initialize tracking
        if channel_id not in self._missing_counts:
            self._missing_counts[channel_id] = 0
        if channel_id not in self._value_history:
            self._value_history[channel_id] = []
        
        # Check for missing/bad data
        if reading.quality_flag in ("bad", "missing"):
            self._missing_counts[channel_id] += 1
            return "bad"
        
        if math.isnan(reading.temperature_c):
            self._missing_counts[channel_id] += 1
            return "missing"
        
        # Reset missing count
        self._missing_counts[channel_id] = 0
        
        # Check value range
        if not (self.thresholds.min_valid_temp_c <= reading.temperature_c <= self.thresholds.max_valid_temp_c):
            return "suspect"
        
        # Update history and check noise
        history = self._value_history[channel_id]
        history.append(reading.temperature_c)
        if len(history) > self.thresholds.noise_window_samples:
            history.pop(0)
        
        # Check for excessive noise
        if len(history) >= self.thresholds.noise_window_samples:
            mean = sum(history) / len(history)
            variance = sum((x - mean) ** 2 for x in history) / len(history)
            std = math.sqrt(variance)
            
            if std > self.thresholds.noise_std_threshold_c:
                return "suspect"
        
        return "good"
    
    def _check_fiber_break(
        self,
        readings: list[TemperatureReading],
        timestamp: str,
    ) -> list[TemperatureAlert]:
        """Check for fiber break pattern."""
        alerts = []
        
        # Sort by position
        sorted_readings = sorted(readings, key=lambda r: r.position_m)
        
        consecutive_bad = 0
        first_bad_position = None
        
        for reading in sorted_readings:
            if reading.quality_flag in ("bad", "missing"):
                if consecutive_bad == 0:
                    first_bad_position = reading.position_m
                consecutive_bad += 1
            else:
                consecutive_bad = 0
                first_bad_position = None
        
        # If trailing channels are all bad, likely fiber break
        if consecutive_bad >= 5 and first_bad_position is not None:
            alerts.append(TemperatureAlert(
                alert_id=self._generate_alert_id(),
                alert_type="fiber_break",
                severity="critical",
                channel_id=None,
                position_m=first_bad_position,
                current_value=consecutive_bad,
                threshold_value=5.0,
                message=f"可能存在光纤断裂！位置{first_bad_position:.1f}m后{consecutive_bad}个通道无信号",
                recommended_action="建议：检查光纤线路，确认断点位置。此为建议，需人工确认。",
                timestamp=timestamp,
            ))
        
        return alerts
    
    def _check_data_gaps(self, timestamp: str) -> list[TemperatureAlert]:
        """Check for persistent data gaps."""
        alerts = []
        
        for channel_id, count in self._missing_counts.items():
            if count >= self.thresholds.max_consecutive_missing:
                alerts.append(TemperatureAlert(
                    alert_id=self._generate_alert_id(),
                    alert_type="data_gap",
                    severity="warning",
                    channel_id=channel_id,
                    position_m=channel_id * 0.5,  # Approximate
                    current_value=count,
                    threshold_value=self.thresholds.max_consecutive_missing,
                    message=f"数据缺失！通道{channel_id}连续{count}个采样点无效",
                    recommended_action="建议：检查该传感器连接状态。此为提示信息。",
                    timestamp=timestamp,
                ))
        
        return alerts
    
    def get_quality_summary(self, readings: list[TemperatureReading]) -> dict[str, Any]:
        """Get summary of data quality."""
        quality_counts = {"good": 0, "suspect": 0, "bad": 0, "missing": 0}
        
        for r in readings:
            flag = r.quality_flag
            if flag in quality_counts:
                quality_counts[flag] += 1
            else:
                quality_counts["suspect"] += 1
        
        total = len(readings)
        return {
            "total_channels": total,
            "quality_distribution": quality_counts,
            "good_percentage": quality_counts["good"] / total * 100 if total > 0 else 0,
            "channels_with_gaps": sum(1 for c, count in self._missing_counts.items() if count > 0),
        }
