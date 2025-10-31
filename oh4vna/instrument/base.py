"""Abstract base class for VNA instruments."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

import numpy as np
from skrf import Network


class VNAInterface(ABC):
    """Abstract interface for VNA instruments."""
    
    @abstractmethod
    def connect(self, address: Optional[str] = None) -> bool:
        """Connect to the VNA instrument.
        
        Args:
            address: VISA resource string or None for auto-detection
            
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the VNA instrument."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if instrument is connected."""
        pass
    
    @abstractmethod
    def get_info(self) -> Dict[str, str]:
        """Get instrument identification information.
        
        Returns:
            Dictionary with manufacturer, model, serial, firmware keys
        """
        pass
    
    @abstractmethod
    def preset(self) -> None:
        """Reset instrument to default state."""
        pass
    
    @abstractmethod
    def configure_sweep(
        self,
        start_freq: float,
        stop_freq: float,
        points: int,
        if_bandwidth: float = 1000,
        power: float = -10
    ) -> None:
        """Configure frequency sweep parameters.
        
        Args:
            start_freq: Start frequency in Hz
            stop_freq: Stop frequency in Hz
            points: Number of measurement points
            if_bandwidth: IF bandwidth in Hz
            power: Source power in dBm
        """
        pass
    
    @abstractmethod
    def configure_ports(self, port_count: int = 2) -> None:
        """Configure number of ports for measurement.
        
        Args:
            port_count: Number of ports (1 or 2)
        """
        pass
    
    @abstractmethod
    def trigger_sweep(self) -> None:
        """Trigger a single sweep measurement."""
        pass
    
    @abstractmethod
    def wait_for_sweep(self, timeout: float = 30.0) -> bool:
        """Wait for sweep to complete.
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            True if sweep completed within timeout
        """
        pass
    
    @abstractmethod
    def get_s_parameters(self, ports: Optional[List[int]] = None) -> Network:
        """Retrieve S-parameter data as scikit-rf Network.
        
        Args:
            ports: List of port numbers to measure, or None for all
            
        Returns:
            scikit-rf Network object with S-parameter data
        """
        pass
    
    @abstractmethod
    def get_frequency_points(self) -> np.ndarray:
        """Get current frequency points.
        
        Returns:
            Array of frequency points in Hz
        """
        pass
    
    @abstractmethod
    def set_calibration(self, cal_data: Optional[Dict]) -> None:
        """Apply calibration data.
        
        Args:
            cal_data: Calibration coefficients or None to disable
        """
        pass

    @abstractmethod
    def get_port_count(self) -> int:
        """Return the number of available ports on the instrument."""
        pass