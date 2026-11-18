"""Risk Detection Algorithms for Temperature Monitoring.

IMPORTANT: This system provides RECOMMENDATIONS ONLY.
It does NOT send control commands to boiler DCS/SIS systems.
All alerts require human acknowledgment before any action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import math

from boiler_fbg_workflow.schemas import TemperatureAlert, TemperatureReading


@dataclass
class RiskThresholds:
    """Configurable risk detection thresholds."""
    # Absolute temperature limits
    over_temp_warning_c: float = 480.0
    over_temp_alarm_c: float = 520.0
    over_temp_critical_c: float = 550.0
    
    # Rate of change limits (°C per second)
    fast_rise_warning_rate: float = 10.0
    fast_rise_alarm_rate: float = 20.0
    
    # Spatial gradient limits (°C per meter)
    gradient_warning: float = 50.0
    gradient_alarm: float = 100.0
    
    # Drift detection (cumulative deviation over window)
    drift_window_samples: int = 100
    drift_threshold_c: float = 5.0


@dataclass
class ChannelHistory:
    """Historical data for a single channel."""
    temperatures: list[float] = field(default_factory=list)
    timestamps: list[str] = field(default_factory=list)
    max_history: int = 1000
    
    def add(self, temp: float, ts: str) -> None:
        self.temperatures.append(temp)
        self.timestamps.append(ts)
        if len(self.temperatures) > self.max_history:
            self.temperatures.pop(0)
            self.timestamps.pop(0)
    
    def get_rate_of_change(self, window: int = 10) -> float:
        """Calculate rate of change in °C/s over recent window."""
        if len(self.temperatures) < 2:
            return 0.0
        
        recent = self.temperatures[-min(window, len(self.temperatures)):]
        if len(recent) < 2:
            return 0.0
        
        # Assume fixed sample interval (simplified)
        return (recent[-1] - recent[0]) / (len(recent) * 0.1)  # 100ms interval
    
    def get_drift(self, window: int = 100) -> float:
        """Calculate cumulative drift from mean over window."""
        if len(self.temperatures) < window:
            return 0.0
        
        recent = self.temperatures[-window:]
        mean = sum(recent) / len(recent)
        return recent[-1] - mean


class RiskDetector:
    """Temperature risk detection engine.
    
    SAFETY DISCLAIMER:
    - This system provides monitoring and warnings ONLY
    - It does NOT send control commands to boiler systems
    - All alerts are RECOMMENDATIONS requiring human verification
    - Do not rely on this system as a safety interlock
    """
    
    def __init__(self, thresholds: RiskThresholds | None = None):
        self.thresholds = thresholds or RiskThresholds()
        self.channel_history: dict[int, ChannelHistory] = {}
        self._alert_counter = 0
    
    def _generate_alert_id(self) -> str:
        self._alert_counter += 1
        return f"ALERT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._alert_counter:04d}"
    
    def analyze(self, readings: list[TemperatureReading]) -> list[TemperatureAlert]:
        """Analyze temperature readings and generate alerts.
        
        Args:
            readings: List of current temperature readings
            
        Returns:
            List of alerts (may be empty if no issues detected)
        """
        alerts = []
        timestamp = datetime.now().isoformat()
        
        for reading in readings:
            # Skip invalid readings
            if reading.quality_flag in ("bad", "missing"):
                continue
            if math.isnan(reading.temperature_c):
                continue
            
            # Update history
            if reading.channel_id not in self.channel_history:
                self.channel_history[reading.channel_id] = ChannelHistory()
            self.channel_history[reading.channel_id].add(
                reading.temperature_c,
                reading.timestamp,
            )
            
            # Check 1: Over-temperature
            alerts.extend(self._check_over_temp(reading, timestamp))
            
            # Check 2: Fast temperature rise
            alerts.extend(self._check_fast_rise(reading, timestamp))
            
            # Check 3: Drift detection
            alerts.extend(self._check_drift(reading, timestamp))
        
        # Check 4: Spatial gradient (needs all readings)
        alerts.extend(self._check_gradient(readings, timestamp))
        
        return alerts
    
    def _check_over_temp(
        self,
        reading: TemperatureReading,
        timestamp: str,
    ) -> list[TemperatureAlert]:
        """Check for over-temperature conditions."""
        alerts = []
        temp = reading.temperature_c
        
        if temp >= self.thresholds.over_temp_critical_c:
            alerts.append(TemperatureAlert(
                alert_id=self._generate_alert_id(),
                alert_type="over_temp",
                severity="critical",
                channel_id=reading.channel_id,
                position_m=reading.position_m,
                current_value=temp,
                threshold_value=self.thresholds.over_temp_critical_c,
                message=f"严重超温！通道{reading.channel_id}温度{temp:.1f}°C超过临界阈值{self.thresholds.over_temp_critical_c}°C",
                recommended_action="建议：立即检查该区域水冷壁，确认冷却水流量和压力。此为建议，需人工确认后操作。",
                timestamp=timestamp,
            ))
        elif temp >= self.thresholds.over_temp_alarm_c:
            alerts.append(TemperatureAlert(
                alert_id=self._generate_alert_id(),
                alert_type="over_temp",
                severity="alarm",
                channel_id=reading.channel_id,
                position_m=reading.position_m,
                current_value=temp,
                threshold_value=self.thresholds.over_temp_alarm_c,
                message=f"超温报警！通道{reading.channel_id}温度{temp:.1f}°C超过报警阈值{self.thresholds.over_temp_alarm_c}°C",
                recommended_action="建议：检查该区域工况，关注温度趋势。此为建议，需人工评估。",
                timestamp=timestamp,
            ))
        elif temp >= self.thresholds.over_temp_warning_c:
            alerts.append(TemperatureAlert(
                alert_id=self._generate_alert_id(),
                alert_type="over_temp",
                severity="warning",
                channel_id=reading.channel_id,
                position_m=reading.position_m,
                current_value=temp,
                threshold_value=self.thresholds.over_temp_warning_c,
                message=f"超温预警！通道{reading.channel_id}温度{temp:.1f}°C接近预警阈值{self.thresholds.over_temp_warning_c}°C",
                recommended_action="建议：持续关注温度变化趋势。此为提示信息。",
                timestamp=timestamp,
            ))
        
        return alerts
    
    def _check_fast_rise(
        self,
        reading: TemperatureReading,
        timestamp: str,
    ) -> list[TemperatureAlert]:
        """Check for fast temperature rise."""
        alerts = []
        
        history = self.channel_history.get(reading.channel_id)
        if not history:
            return alerts
        
        rate = history.get_rate_of_change(window=10)
        
        if rate >= self.thresholds.fast_rise_alarm_rate:
            alerts.append(TemperatureAlert(
                alert_id=self._generate_alert_id(),
                alert_type="temp_rise_fast",
                severity="alarm",
                channel_id=reading.channel_id,
                position_m=reading.position_m,
                current_value=rate,
                threshold_value=self.thresholds.fast_rise_alarm_rate,
                message=f"温度快速上升！通道{reading.channel_id}温升速率{rate:.1f}°C/s超过报警阈值",
                recommended_action="建议：检查燃烧工况和冷却系统。此为建议，需人工确认。",
                timestamp=timestamp,
            ))
        elif rate >= self.thresholds.fast_rise_warning_rate:
            alerts.append(TemperatureAlert(
                alert_id=self._generate_alert_id(),
                alert_type="temp_rise_fast",
                severity="warning",
                channel_id=reading.channel_id,
                position_m=reading.position_m,
                current_value=rate,
                threshold_value=self.thresholds.fast_rise_warning_rate,
                message=f"温度上升较快！通道{reading.channel_id}温升速率{rate:.1f}°C/s",
                recommended_action="建议：关注温度变化趋势。此为提示信息。",
                timestamp=timestamp,
            ))
        
        return alerts
    
    def _check_drift(
        self,
        reading: TemperatureReading,
        timestamp: str,
    ) -> list[TemperatureAlert]:
        """Check for sensor drift."""
        alerts = []
        
        history = self.channel_history.get(reading.channel_id)
        if not history:
            return alerts
        
        drift = history.get_drift(window=self.thresholds.drift_window_samples)
        
        if abs(drift) >= self.thresholds.drift_threshold_c:
            alerts.append(TemperatureAlert(
                alert_id=self._generate_alert_id(),
                alert_type="sensor_drift",
                severity="warning",
                channel_id=reading.channel_id,
                position_m=reading.position_m,
                current_value=drift,
                threshold_value=self.thresholds.drift_threshold_c,
                message=f"可能存在传感器漂移！通道{reading.channel_id}累计偏差{drift:.2f}°C",
                recommended_action="建议：在下次维护时校验该传感器。此为提示信息。",
                timestamp=timestamp,
            ))
        
        return alerts
    
    def _check_gradient(
        self,
        readings: list[TemperatureReading],
        timestamp: str,
    ) -> list[TemperatureAlert]:
        """Check for abnormal spatial temperature gradients."""
        alerts = []
        
        # Sort by position
        valid_readings = [
            r for r in readings 
            if r.quality_flag not in ("bad", "missing") and not math.isnan(r.temperature_c)
        ]
        valid_readings.sort(key=lambda r: r.position_m)
        
        for i in range(len(valid_readings) - 1):
            r1, r2 = valid_readings[i], valid_readings[i + 1]
            distance = r2.position_m - r1.position_m
            
            if distance <= 0:
                continue
            
            gradient = abs(r2.temperature_c - r1.temperature_c) / distance
            
            if gradient >= self.thresholds.gradient_alarm:
                alerts.append(TemperatureAlert(
                    alert_id=self._generate_alert_id(),
                    alert_type="gradient_high",
                    severity="alarm",
                    channel_id=r1.channel_id,
                    position_m=r1.position_m,
                    current_value=gradient,
                    threshold_value=self.thresholds.gradient_alarm,
                    message=f"温度梯度异常！位置{r1.position_m:.1f}m-{r2.position_m:.1f}m梯度{gradient:.1f}°C/m",
                    recommended_action="建议：检查该区域是否存在局部过热或冷却不均。此为建议，需人工确认。",
                    timestamp=timestamp,
                ))
            elif gradient >= self.thresholds.gradient_warning:
                alerts.append(TemperatureAlert(
                    alert_id=self._generate_alert_id(),
                    alert_type="gradient_high",
                    severity="warning",
                    channel_id=r1.channel_id,
                    position_m=r1.position_m,
                    current_value=gradient,
                    threshold_value=self.thresholds.gradient_warning,
                    message=f"温度梯度较大！位置{r1.position_m:.1f}m-{r2.position_m:.1f}m梯度{gradient:.1f}°C/m",
                    recommended_action="建议：关注该区域温度分布。此为提示信息。",
                    timestamp=timestamp,
                ))
        
        return alerts
    
    def get_statistics(self) -> dict[str, Any]:
        """Get detector statistics."""
        return {
            "channels_tracked": len(self.channel_history),
            "alerts_generated": self._alert_counter,
            "thresholds": {
                "over_temp_critical_c": self.thresholds.over_temp_critical_c,
                "fast_rise_alarm_rate": self.thresholds.fast_rise_alarm_rate,
                "gradient_alarm": self.thresholds.gradient_alarm,
            },
        }
