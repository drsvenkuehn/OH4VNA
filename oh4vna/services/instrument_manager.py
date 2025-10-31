"""Instrument management service."""

from typing import Optional, Dict, Any
import logging

from ..config import settings
from ..instrument import VNAInterface, SimulationVNA, ZVA
from skrf import Network

logger = logging.getLogger(__name__)


class InstrumentManager:
    """Manages VNA instrument connections and operations."""
    
    def __init__(self):
        self._instrument: Optional[VNAInterface] = None
        self._instrument_info: Optional[Dict[str, str]] = None
    
    @property
    def instrument(self) -> Optional[VNAInterface]:
        """Get current instrument instance."""
        return self._instrument
    
    @property 
    def is_connected(self) -> bool:
        """Check if instrument is connected."""
        return self._instrument is not None and self._instrument.is_connected()
    
    def connect(self, instrument_type: str = "auto", address: Optional[str] = None) -> bool:
        """Connect to VNA instrument.
        
        Args:
            instrument_type: 'zva', 'simulation', or 'auto'
            address: VISA address for real instruments
            
        Returns:
            True if connection successful
        """
        # Disconnect existing connection
        if self._instrument:
            self.disconnect()
        
        # Determine instrument type
        if instrument_type == "auto":
            if settings.simulation_mode:
                instrument_type = "simulation"
            else:
                instrument_type = "zva"  # Default to ZVA
        
        # Create appropriate instrument instance
        try:
            if instrument_type == "simulation":
                self._instrument = SimulationVNA()
                success = self._instrument.connect()
                connect_address = "SIMULATION"
            elif instrument_type == "zva":
                self._instrument = ZVA()
                connect_address = address or settings.vna_address
                if not connect_address:
                    raise ValueError("VNA address required for ZVA connection")
                success = self._instrument.connect(connect_address)
            else:
                raise ValueError(f"Unknown instrument type: {instrument_type}")
            
            if success:
                info = self._instrument.get_info() or {}
                info.setdefault("manufacturer", info.get("manufacturer", "Unknown"))
                info.setdefault("model", info.get("model", instrument_type.upper()))
                info["address"] = connect_address
                try:
                    info["ports"] = self._instrument.get_port_count()
                except Exception:
                    info.setdefault("ports", 2)
                self._instrument_info = info
                logger.info(
                    "Connected to %s %s",
                    self._instrument_info.get("manufacturer", "Unknown"),
                    self._instrument_info.get("model", instrument_type.upper()),
                )
                return True
            else:
                self._instrument = None
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to instrument: {e}")
            self._instrument = None
            self._instrument_info = None
            raise
    
    def disconnect(self) -> None:
        """Disconnect from instrument."""
        if self._instrument:
            try:
                self._instrument.disconnect()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self._instrument = None
                self._instrument_info = None
    
    def get_info(self) -> Dict[str, Any]:
        """Get instrument information and status."""
        return {
            "connected": self.is_connected,
            "info": self._instrument_info,
            "simulation_mode": settings.simulation_mode
        }

    def get_port_count(self) -> int:
        """Return the number of ports available on the current instrument."""

        if self._instrument and self.is_connected:
            try:
                return self._instrument.get_port_count()
            except Exception:
                pass
        if self._instrument_info and "ports" in self._instrument_info:
            try:
                return int(self._instrument_info["ports"])
            except Exception:
                pass
        return 2
    
    def preset_instrument(self) -> None:
        """Reset instrument to default state."""
        if not self.is_connected:
            raise RuntimeError("No instrument connected")
        
        self._instrument.preset()
    
    def configure_measurement(
        self,
        start_freq: float,
        stop_freq: float, 
        points: int,
        if_bandwidth: float = 1000,
        power: float = -10,
        port_count: int = 2
    ) -> None:
        """Configure measurement parameters."""
        if not self.is_connected:
            raise RuntimeError("No instrument connected")
        
        self._instrument.configure_sweep(
            start_freq=start_freq,
            stop_freq=stop_freq,
            points=points,
            if_bandwidth=if_bandwidth,
            power=power
        )
        requested_ports = max(1, port_count)
        try:
            available_ports = self._instrument.get_port_count()
        except Exception:
            available_ports = requested_ports

        self._instrument.configure_ports(port_count=min(requested_ports, available_ports))

    def set_simulation_fixture(self, network: Optional[Network], name: str = "Fixture") -> None:
        """Attach a 1-port network to the simulated coupler."""

        if isinstance(self._instrument, SimulationVNA):
            self._instrument.set_fixture(network, name=name)
            info = self._instrument.get_info()
            if self._instrument_info is None:
                self._instrument_info = info
            else:
                for key, value in info.items():
                    if key == "address":
                        continue
                    self._instrument_info[key] = value