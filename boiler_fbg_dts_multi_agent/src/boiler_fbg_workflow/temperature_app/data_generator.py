"""Synthetic Data Generator for Testing.

ALL DATA GENERATED IS MARKED AS [SYNTHETIC].
This is for testing and demonstration purposes only.
No claims are made about actual boiler behavior or measurements.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator

from boiler_fbg_workflow.schemas import TemperatureReading


@dataclass
class DataGeneratorConfig:
    """Configuration for synthetic data generation."""
    channel_count: int = 64
    base_temperature_c: float = 380.0
    temperature_variation_c: float = 50.0
    noise_amplitude_c: float = 2.0
    sample_interval_ms: int = 100
    
    # Anomaly injection probabilities (for testing detection)
    inject_over_temp_prob: float = 0.01
    inject_fast_rise_prob: float = 0.005
    inject_sensor_drift_prob: float = 0.002
    inject_data_gap_prob: float = 0.005
    
    # Strain coupling simulation
    simulate_strain: bool = True
    strain_coefficient_pm_per_c: float = 10.0


class SyntheticDataGenerator:
    """Generate synthetic FBG temperature data for testing.
    
    ALL GENERATED DATA IS MARKED AS [SYNTHETIC].
    
    Features:
    - Realistic temperature profiles with spatial and temporal variation
    - Configurable anomaly injection for testing detection algorithms
    - Strain coupling simulation for testing decoupling algorithms
    - Data quality issues (gaps, noise) for testing quality flags
    """
    
    def __init__(self, config: DataGeneratorConfig | None = None):
        self.config = config or DataGeneratorConfig()
        self._time_offset = 0.0
        self._drift_accumulator = [0.0] * self.config.channel_count
        self._last_temperatures = [self.config.base_temperature_c] * self.config.channel_count
    
    def generate_single_sample(self, timestamp: datetime | None = None) -> list[TemperatureReading]:
        """Generate a single time sample for all channels.
        
        Returns:
            List of TemperatureReading objects, all marked as synthetic.
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        readings = []
        self._time_offset += self.config.sample_interval_ms / 1000.0
        
        for ch in range(self.config.channel_count):
            # Base temperature with spatial variation (simulates water-wall profile)
            spatial_factor = math.sin(ch * math.pi / self.config.channel_count) * 0.3 + 0.7
            base_temp = self.config.base_temperature_c * spatial_factor
            
            # Temporal variation (simulates load changes)
            temporal_factor = math.sin(self._time_offset * 0.1) * 0.1 + 1.0
            
            # Add noise
            noise = random.gauss(0, self.config.noise_amplitude_c)
            
            # Calculate temperature
            temperature = base_temp * temporal_factor + noise
            
            # Inject anomalies for testing
            quality_flag = "good"
            
            if random.random() < self.config.inject_over_temp_prob:
                temperature = self.config.base_temperature_c + 150  # Over-temp
                
            if random.random() < self.config.inject_sensor_drift_prob:
                self._drift_accumulator[ch] += random.gauss(0, 0.5)
                
            temperature += self._drift_accumulator[ch]
            
            if random.random() < self.config.inject_data_gap_prob:
                quality_flag = "missing"
                temperature = float('nan')
            
            # Calculate wavelength shift (simplified FBG model)
            wavelength_shift = (temperature - self.config.base_temperature_c) * self.config.strain_coefficient_pm_per_c
            
            # Simulate strain contribution if enabled
            strain = 0.0
            if self.config.simulate_strain:
                strain = random.gauss(0, 50)  # Random strain noise in με
                wavelength_shift += strain * 1.2  # Approximate strain sensitivity
            
            self._last_temperatures[ch] = temperature
            
            readings.append(TemperatureReading(
                channel_id=ch,
                position_m=ch * 0.5,  # 0.5m spacing
                temperature_c=round(temperature, 2),
                wavelength_shift_pm=round(wavelength_shift, 2),
                strain_ue=round(strain, 2),
                timestamp=timestamp.isoformat(),
                quality_flag=quality_flag,
                data_source="synthetic",  # Marked as synthetic data
            ))
        
        return readings
    
    def generate_time_series(
        self,
        duration_seconds: float,
        start_time: datetime | None = None,
    ) -> Iterator[list[TemperatureReading]]:
        """Generate a time series of synthetic data.
        
        Args:
            duration_seconds: Total duration to generate
            start_time: Start timestamp (defaults to now)
            
        Yields:
            Lists of TemperatureReading for each time sample
        """
        if start_time is None:
            start_time = datetime.now()
        
        interval_td = timedelta(milliseconds=self.config.sample_interval_ms)
        samples = int(duration_seconds * 1000 / self.config.sample_interval_ms)
        
        for i in range(samples):
            timestamp = start_time + interval_td * i
            yield self.generate_single_sample(timestamp)
    
    def inject_fast_temperature_rise(
        self,
        channel_id: int,
        readings: list[TemperatureReading],
        rise_rate_c_per_s: float = 50.0,
    ) -> list[TemperatureReading]:
        """Inject a fast temperature rise event for testing.
        
        This simulates a sudden temperature increase that should
        trigger the fast-rise detection algorithm.
        """
        result = []
        for r in readings:
            if r.channel_id == channel_id:
                new_temp = r.temperature_c + rise_rate_c_per_s * (self.config.sample_interval_ms / 1000)
                result.append(TemperatureReading(
                    channel_id=r.channel_id,
                    position_m=r.position_m,
                    temperature_c=round(new_temp, 2),
                    wavelength_shift_pm=r.wavelength_shift_pm,
                    strain_ue=r.strain_ue,
                    timestamp=r.timestamp,
                    quality_flag=r.quality_flag,
                    data_source="synthetic",  # Injected fast rise event
                ))
            else:
                result.append(r)
        return result
    
    def inject_fiber_break(
        self,
        readings: list[TemperatureReading],
        break_position_m: float,
    ) -> list[TemperatureReading]:
        """Inject a fiber break event for testing.
        
        Channels beyond the break position will show as disconnected.
        """
        result = []
        for r in readings:
            if r.position_m > break_position_m:
                result.append(TemperatureReading(
                    channel_id=r.channel_id,
                    position_m=r.position_m,
                    temperature_c=float('nan'),
                    wavelength_shift_pm=0.0,
                    strain_ue=0.0,
                    timestamp=r.timestamp,
                    quality_flag="bad",
                    data_source="synthetic",  # Injected fiber break event
                ))
            else:
                result.append(r)
        return result
