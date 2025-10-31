"""Rohde & Schwarz ZVA driver implementation."""

from typing import Dict, List, Optional
import time

import numpy as np
import pyvisa
from skrf import Network, Frequency

from .base import VNAInterface


class ZVA(VNAInterface):
    """Rohde & Schwarz ZVA series VNA driver."""
    
    def __init__(self):
        self._instrument = None
        self._rm = None
        self._connected = False
        self._cached_port_count = 2
        
    def connect(self, address: Optional[str] = None) -> bool:
        """Connect to ZVA instrument via VISA.
        
        Args:
            address: VISA resource string (e.g., 'TCPIP::192.168.1.100::INSTR')
        """
        if address is None:
            raise ValueError("Address required for ZVA connection")
        
        try:
            self._rm = pyvisa.ResourceManager()
            self._instrument = self._rm.open_resource(address)
            self._instrument.timeout = 30000  # 30 second timeout
            
            # Test connection with ID query
            idn = self._instrument.query("*IDN?").strip()
            if "ZVA" not in idn and "ZNB" not in idn:
                raise RuntimeError(f"Connected instrument is not a supported R&S VNA: {idn}")
            self._cached_port_count = self._query_port_count()
            
            self._connected = True
            return True
            
        except Exception as e:
            if self._instrument:
                self._instrument.close()
            if self._rm:
                self._rm.close()
            self._connected = False
            raise RuntimeError(f"Failed to connect to ZVA: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from instrument."""
        if self._instrument:
            try:
                self._instrument.close()
            except:
                pass
            self._instrument = None
        
        if self._rm:
            try:
                self._rm.close()
            except:
                pass
            self._rm = None
        
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check connection status."""
        if not self._connected or not self._instrument:
            return False
        
        try:
            # Try a simple query to verify connection
            self._instrument.query("*OPC?")
            return True
        except:
            self._connected = False
            return False
    
    def get_info(self) -> Dict[str, str]:
        """Get instrument identification."""
        if not self.is_connected():
            raise RuntimeError("VNA not connected")
        
        idn = self._instrument.query("*IDN?").strip().split(",")
        
        return {
            "manufacturer": idn[0] if len(idn) > 0 else "Unknown",
            "model": idn[1] if len(idn) > 1 else "Unknown", 
            "serial": idn[2] if len(idn) > 2 else "Unknown",
            "firmware": idn[3] if len(idn) > 3 else "Unknown",
            "ports": self._cached_port_count,
        }
    
    def preset(self) -> None:
        """Reset instrument to default state."""
        if not self.is_connected():
            raise RuntimeError("VNA not connected")
        
        self._instrument.write("*RST")
        self._instrument.write("*CLS")
        time.sleep(2)  # Allow time for reset
        self._instrument.query("*OPC?")  # Wait for operation complete
    
    def configure_sweep(
        self,
        start_freq: float,
        stop_freq: float,
        points: int,
        if_bandwidth: float = 1000,
        power: float = -10
    ) -> None:
        """Configure frequency sweep."""
        if not self.is_connected():
            raise RuntimeError("VNA not connected")
        
        # Set frequency range
        self._instrument.write(f"FREQ:STAR {start_freq}")
        self._instrument.write(f"FREQ:STOP {stop_freq}")
        
        # Set number of points
        self._instrument.write(f"SWE:POIN {points}")
        
        # Set IF bandwidth
        self._instrument.write(f"BAND {if_bandwidth}")
        
        # Set source power
        self._instrument.write(f"SOUR:POW {power}")
        
        # Wait for settings to take effect
        self._instrument.query("*OPC?")
    
    def configure_ports(self, port_count: int = 2) -> None:
        """Configure measurement ports."""
        if not self.is_connected():
            raise RuntimeError("VNA not connected")
        
        if port_count not in [1, 2, 4]:
            raise ValueError("ZVA supports 1, 2, or 4 ports")
        
        # Configure S-parameter measurement based on port count
        if port_count == 1:
            # S11 only
            self._instrument.write("CALC:PAR:DEF 'S11', 'S11'")
        elif port_count == 2:
            # Full 2-port S-parameters
            self._instrument.write("CALC:PAR:DEF 'S11', 'S11'")
            self._instrument.write("CALC:PAR:DEF 'S12', 'S12'") 
            self._instrument.write("CALC:PAR:DEF 'S21', 'S21'")
            self._instrument.write("CALC:PAR:DEF 'S22', 'S22'")
        
        self._instrument.query("*OPC?")
    
    def trigger_sweep(self) -> None:
        """Trigger single sweep."""
        if not self.is_connected():
            raise RuntimeError("VNA not connected")
        
        # Set to single sweep mode and trigger
        self._instrument.write("INIT:CONT OFF")
        self._instrument.write("INIT:IMM")
    
    def wait_for_sweep(self, timeout: float = 30.0) -> bool:
        """Wait for sweep completion.""" 
        if not self.is_connected():
            raise RuntimeError("VNA not connected")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check if sweep is complete
                status = self._instrument.query("STAT:OPER:COND?")
                if int(status) & (1 << 4) == 0:  # Bit 4 = measuring
                    return True
            except:
                pass
            
            time.sleep(0.1)
        
        return False
    
    def get_s_parameters(self, ports: Optional[List[int]] = None) -> Network:
        """Retrieve S-parameter data."""
        if not self.is_connected():
            raise RuntimeError("VNA not connected")
        
        # Get frequency points
        freq_data = self._instrument.query_ascii_values("FREQ:DATA?")
        freq = Frequency.from_f(freq_data, unit='Hz')
        
        # Determine which S-parameters to read
        if ports is None or len(ports) == 2:
            # Read full 2-port S-parameters
            s_params = ['S11', 'S12', 'S21', 'S22']
            s_shape = (2, 2)
        elif len(ports) == 1:
            # Read S11 only
            s_params = ['S11']
            s_shape = (1, 1)
        else:
            raise ValueError("Unsupported port configuration")
        
        # Read S-parameter data
        s_data = np.zeros((len(freq_data), s_shape[0], s_shape[1]), dtype=complex)
        
        for i, param in enumerate(s_params):
            # Select parameter and read complex data
            self._instrument.write(f"CALC:PAR:SEL '{param}'")
            
            # Get complex data (real and imaginary parts)
            real_data = self._instrument.query_ascii_values("CALC:DATA? REAL")
            imag_data = self._instrument.query_ascii_values("CALC:DATA? IMAG")
            
            complex_data = np.array(real_data) + 1j * np.array(imag_data)
            
            # Map to S-matrix indices
            if param == 'S11':
                s_data[:, 0, 0] = complex_data
            elif param == 'S12':
                s_data[:, 0, 1] = complex_data
            elif param == 'S21':
                s_data[:, 1, 0] = complex_data
            elif param == 'S22':
                s_data[:, 1, 1] = complex_data
        
        # Create Network object
        network = Network(frequency=freq, s=s_data)
        network.name = "ZVA Measurement"
        
        return network
    
    def get_frequency_points(self) -> np.ndarray:
        """Get current frequency points."""
        if not self.is_connected():
            raise RuntimeError("VNA not connected")
        
        return np.array(self._instrument.query_ascii_values("FREQ:DATA?"))
    
    def set_calibration(self, cal_data: Optional[Dict]) -> None:
        """Apply calibration data."""
        if not self.is_connected():
            raise RuntimeError("VNA not connected")
        
        if cal_data is None:
            # Turn off calibration
            self._instrument.write("CORR:STAT OFF")
        else:
            # In a full implementation, this would load calibration coefficients
            # For now, just ensure calibration is enabled
            self._instrument.write("CORR:STAT ON")
        
        self._instrument.query("*OPC?")

    def get_port_count(self) -> int:
        """Return available ports on the instrument."""

        if self._cached_port_count:
            return self._cached_port_count
        if not self.is_connected():
            return 2
        self._cached_port_count = self._query_port_count()
        return self._cached_port_count

    def _query_port_count(self) -> int:
        """Attempt to query number of ports, fallback to 2."""

        if not self._instrument:
            return 2

        for command in ["SYST:CONF:PORT?", "SYST:CONF:PO?", "SYST:COMM:LAN:PORT?"]:
            try:
                response = self._instrument.query(command).strip()
                if response:
                    value = int(float(response))
                    if value >= 1:
                        return value
            except Exception:
                continue
        return 2