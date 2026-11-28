"""Hardware Adapter Contracts and Simulated Implementation.

IMPORTANT: These are CONTRACT DEFINITIONS for hardware adapters.
The simulated implementation is for testing and demonstration only.

To integrate actual hardware:
1. Obtain vendor SDK/API documentation
2. Implement the DemodulatorAdapter protocol
3. Perform actual hardware integration testing
4. Validate against real sensor data

NO CLAIMS ARE MADE ABOUT SUPPORTING ACTUAL HARDWARE.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable


class ChannelStatus(Enum):
    """Status of a sensor channel."""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass
class ChannelReading:
    """Reading from a single sensor channel."""
    channel_id: int
    position_m: float
    wavelength_nm: float
    wavelength_shift_pm: float
    temperature_c: float
    strain_ue: float
    status: ChannelStatus
    timestamp: datetime
    data_source: str = "synthetic"  # Always mark data source


@runtime_checkable
class DemodulatorAdapter(Protocol):
    """Protocol defining the hardware adapter interface.
    
    WARNING: This is a CONTRACT DEFINITION.
    Implementing this protocol for actual hardware requires:
    - Vendor SDK/API documentation
    - Hardware-specific communication protocols
    - Proper testing with actual devices
    
    The simulated implementation below is for development and testing only.
    """
    
    def connect(self, config: dict) -> bool:
        """Connect to the demodulator hardware.
        
        Args:
            config: Hardware-specific configuration (IP, port, etc.)
            
        Returns:
            True if connection successful, False otherwise.
        """
        ...
    
    def disconnect(self) -> None:
        """Disconnect from the hardware."""
        ...
    
    def is_connected(self) -> bool:
        """Check if connected to hardware."""
        ...
    
    def read_wavelengths(self) -> list[float]:
        """Read raw wavelength values from all channels.
        
        Returns:
            List of wavelength values in nm.
        """
        ...
    
    def read_temperatures(self) -> list[float]:
        """Read computed temperature values from all channels.
        
        Returns:
            List of temperature values in Celsius.
        """
        ...
    
    def read_all_channels(self) -> list[ChannelReading]:
        """Read complete data from all channels.
        
        Returns:
            List of ChannelReading objects with full data.
        """
        ...
    
    def get_channel_count(self) -> int:
        """Get number of available channels."""
        ...
    
    def get_channel_status(self, channel_id: int) -> ChannelStatus:
        """Get status of a specific channel."""
        ...


class SimulatedDemodulator:
    """Simulated FBG demodulator for testing and demonstration.
    
    ALL DATA GENERATED IS MARKED AS [SYNTHETIC].
    This does not represent actual hardware behavior.
    """
    
    def __init__(
        self,
        channel_count: int = 64,
        base_wavelength_nm: float = 1550.0,
        wavelength_spacing_nm: float = 0.8,
    ):
        self.channel_count = channel_count
        self.base_wavelength_nm = base_wavelength_nm
        self.wavelength_spacing_nm = wavelength_spacing_nm
        self._connected = False
        self._channel_positions: list[float] = []
        self._base_wavelengths: list[float] = []
        
    def connect(self, config: dict) -> bool:
        """Simulate connection (always succeeds for testing)."""
        self._connected = True
        
        # Initialize channel positions (simulated fiber layout)
        # Positions represent distance along fiber in meters
        self._channel_positions = [i * 0.5 for i in range(self.channel_count)]
        
        # Initialize base wavelengths
        self._base_wavelengths = [
            self.base_wavelength_nm + i * self.wavelength_spacing_nm
            for i in range(self.channel_count)
        ]
        
        return True
    
    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def read_wavelengths(self) -> list[float]:
        """Return simulated wavelength values."""
        if not self._connected:
            return []
        return self._base_wavelengths.copy()
    
    def read_temperatures(self) -> list[float]:
        """Return simulated temperature values (base values only)."""
        if not self._connected:
            return []
        # Return default temperatures - actual values come from data generator
        return [350.0] * self.channel_count
    
    def read_all_channels(self) -> list[ChannelReading]:
        """Return simulated channel readings."""
        if not self._connected:
            return []
        
        timestamp = datetime.now()
        readings = []
        
        for i in range(self.channel_count):
            readings.append(ChannelReading(
                channel_id=i,
                position_m=self._channel_positions[i],
                wavelength_nm=self._base_wavelengths[i],
                wavelength_shift_pm=0.0,  # Shift calculated by data generator
                temperature_c=350.0,  # Base temperature
                strain_ue=0.0,
                status=ChannelStatus.OK,
                timestamp=timestamp,
                data_source="synthetic",  # Simulated demodulator data
            ))
        
        return readings
    
    def get_channel_count(self) -> int:
        return self.channel_count
    
    def get_channel_status(self, channel_id: int) -> ChannelStatus:
        if not self._connected:
            return ChannelStatus.DISCONNECTED
        if 0 <= channel_id < self.channel_count:
            return ChannelStatus.OK
        return ChannelStatus.ERROR


# Type alias for adapter implementations
Adapter = DemodulatorAdapter | SimulatedDemodulator
