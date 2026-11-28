"""Temperature Monitoring Application Prototype.

This is a standalone prototype for temperature data processing,
risk detection, and alert generation.

IMPORTANT DISCLAIMERS:
1. Hardware adapters are CONTRACT DEFINITIONS only - actual hardware
   integration requires vendor SDK/API documentation and testing.
2. All synthetic data is marked with [SYNTHETIC] tag.
3. This system provides monitoring and recommendations ONLY.
   It does NOT send control commands to boiler DCS/SIS systems.
4. No claims are made about fuel savings or actual plant measurements.
"""

from .adapters import DemodulatorAdapter, SimulatedDemodulator
from .data_generator import SyntheticDataGenerator
from .risk_detector import RiskDetector
from .quality_flags import QualityAnalyzer
from .audit_logger import AuditLogger

__all__ = [
    "DemodulatorAdapter",
    "SimulatedDemodulator",
    "SyntheticDataGenerator",
    "RiskDetector",
    "QualityAnalyzer",
    "AuditLogger",
]
