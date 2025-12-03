"""Simulation VNA for development and testing."""

from __future__ import annotations

import time
from typing import Dict, Optional, List

import numpy as np
from skrf import Frequency, Network
from skrf import Circuit

from .base import VNAInterface


class _OH4VNACouplerModel:
    """Analytical three-port model of the OH4VNA directional coupler."""

    def __init__(
        self,
        return_loss_db: float = 26.0,
        direct_loss_db: float = 0.0,
        coupling_db: float = 20.0,
        leakage_db: float = 100.0,
    ) -> None:
        self._return_loss_db = return_loss_db
        self._direct_loss_db = direct_loss_db
        self._coupling_db = coupling_db
        self._leakage_db = leakage_db

    def two_port_response(self, frequency: Frequency, gamma: np.ndarray) -> np.ndarray:
        """Return 2-port S-matrix between coupler ports 2 and 3 with port 1 terminated."""

        s_matrix = self._three_port_matrix(frequency)
        denom = 1 - gamma * s_matrix[:, 0, 0]
        denom = np.where(np.abs(denom) < 1e-12, 1e-12 + 0j, denom)

        result = np.zeros((frequency.npoints, 2, 2), dtype=complex)
        result[:, 0, 0] = s_matrix[:, 1, 1] + (s_matrix[:, 1, 0] * gamma * s_matrix[:, 0, 1]) / denom
        result[:, 1, 1] = s_matrix[:, 2, 2] + (s_matrix[:, 2, 0] * gamma * s_matrix[:, 0, 2]) / denom
        result[:, 0, 1] = s_matrix[:, 1, 2] + (s_matrix[:, 1, 0] * gamma * s_matrix[:, 0, 2]) / denom
        result[:, 1, 0] = s_matrix[:, 2, 1] + (s_matrix[:, 2, 0] * gamma * s_matrix[:, 0, 1]) / denom
        return result

    def three_port_network(self, frequency: Frequency) -> Network:
        """Return the intrinsic 3-port coupler network without termination."""

        return Network(frequency=frequency, s=self._three_port_matrix(frequency), name="OH4VNA Coupler")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _three_port_matrix(self, frequency: Frequency) -> np.ndarray:
        npoints = frequency.npoints
        s_matrix = np.zeros((npoints, 3, 3), dtype=complex)

        refl_mag = 10 ** (-self._return_loss_db / 20)
        refl_phase = np.linspace(0, np.pi / 6, npoints)
        reflection = refl_mag * np.exp(1j * refl_phase)

        norm = max(frequency.f[-1], 1.0)
        direct = 10 ** (-self._direct_loss_db / 20) * np.exp(-1j * 2 * np.pi * frequency.f / norm)
        coupling = 10 ** (-self._coupling_db / 20) * np.exp(-1j * np.pi * frequency.f / norm)
        leakage = 10 ** (-self._leakage_db / 20) * np.exp(-1j * 0.25 * np.pi * frequency.f / norm)

        s_matrix[:, 0, 0] = reflection
        s_matrix[:, 1, 1] = reflection
        s_matrix[:, 2, 2] = reflection

        s_matrix[:, 0, 1] = direct
        s_matrix[:, 1, 0] = direct

        s_matrix[:, 0, 2] = coupling
        s_matrix[:, 2, 0] = coupling

        s_matrix[:, 1, 2] = leakage
        s_matrix[:, 2, 1] = leakage

        return s_matrix


class SimulationVNA(VNAInterface):
    """Simulated two-port VNA backed by an OH4VNA coupler model."""

    def __init__(self) -> None:
        self._connected = False
        self._start_freq = 1e6  # 1 MHz
        self._stop_freq = 6e9  # 6 GHz
        self._points = 201
        self._if_bandwidth = 1000  # Hz
        self._power = -10  # dBm
        self._sweep_time = 0.5  # seconds
        self._port_count = 2

        # Default: analytical coupler. Can be overridden by emulator coupler.
        self._coupler = _OH4VNACouplerModel()
        self._emulator_coupler: Optional[Network] = None
        self._downlink_gain_db: float = -30.0
        self._uplink_gain_db: float = 20.0
        self._emu_freq_limits: Optional[tuple[float, float]] = None
        self._emu_cal_enabled: bool = True
        self._fixture: Optional[Network] = None
        self._fixture_name = "Open"

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    def connect(self, address: Optional[str] = None) -> bool:
        time.sleep(0.1)
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_info(self) -> Dict[str, str]:
        return {
            "manufacturer": "Simulated",
            "model": "VNA-SIM",
            "serial": "SIM123456",
            "firmware": "1.2.0",
            "ports": self._port_count,
            "fixture": self._fixture_name,
        }

    def preset(self) -> None:
        if not self._connected:
            raise RuntimeError("VNA not connected")

        self._start_freq = 1e6
        self._stop_freq = 6e9
        self._points = 201
        self._if_bandwidth = 1000
        self._power = -10
        self._fixture = None
        self._fixture_name = "Open"

    # ------------------------------------------------------------------
    # Sweep configuration
    # ------------------------------------------------------------------
    def configure_sweep(
        self,
        start_freq: float,
        stop_freq: float,
        points: int,
        if_bandwidth: float = 1000,
        power: float = -10,
    ) -> None:
        if not self._connected:
            raise RuntimeError("VNA not connected")

        self._start_freq = start_freq
        self._stop_freq = stop_freq
        self._points = points
        self._if_bandwidth = if_bandwidth
        self._power = power

    def configure_ports(self, port_count: int = 2) -> None:
        if not self._connected:
            raise RuntimeError("VNA not connected")

        self._port_count = 1 if port_count <= 1 else 2

    def trigger_sweep(self) -> None:
        if not self._connected:
            raise RuntimeError("VNA not connected")

    def wait_for_sweep(self, timeout: float = 30.0) -> bool:
        if not self._connected:
            raise RuntimeError("VNA not connected")

        time.sleep(min(self._sweep_time, timeout))
        return True

    def get_s_parameters(self, ports: Optional[List[int]] = None) -> Network:
        if not self._connected:
            raise RuntimeError("VNA not connected")

        frequency = Frequency(start=self._start_freq, stop=self._stop_freq, npoints=self._points, unit="Hz")
        
        # If emulator coupler is configured, build the circuit like the colleague's emulator
        if self._emulator_coupler is not None:
            coupler_net = self._emulator_coupler.interpolate(frequency)

            # Build downlink/uplink unilateral links
            def _make_link(freq: Frequency, gain_db: float, name: str) -> Network:
                mag = 10 ** (gain_db / 20.0)
                s = np.zeros((freq.npoints, 2, 2), dtype=complex)
                s[:, 1, 0] = mag
                return Network(frequency=freq, s=s, name=name)

            downlink_net = _make_link(frequency, self._downlink_gain_db, "Downlink")
            uplink_net = _make_link(frequency, self._uplink_gain_db, "Uplink")

            # Fixture defaults to Open if none
            if self._fixture is None:
                s_open = np.ones((frequency.npoints, 1, 1), dtype=complex)
                fixture_ntwk = Network(frequency=frequency, s=s_open, name="Open")
            else:
                fixture_ntwk = self._fixture.interpolate(frequency)

            # Termination for isolated port
            iso_term = Network(frequency=frequency, s=np.zeros((frequency.npoints, 1, 1), dtype=complex), name="IsoMatch")

            # External VNA ports
            p0 = Circuit.Port(frequency, z0=50, name="P0")
            p1 = Circuit.Port(frequency, z0=50, name="P1")

            circuit = Circuit([
                [(p0, 0),          (downlink_net, 0)],
                [(downlink_net, 1),(coupler_net, 0)],
                [(coupler_net, 1), (fixture_ntwk, 0)],
                [(coupler_net, 2), (uplink_net, 0)],
                [(uplink_net, 1),  (p1, 0)],
                [(coupler_net, 3), (iso_term, 0)],
            ])

            res = circuit.network
            s21 = res.s[:, 1, 0][:, None, None]
            out = Network(frequency=frequency, s=s21)
            out.name = f"Emu Meas ({self._fixture_name})"
            return out

        # Fallback: analytical coupler model
        if self._fixture is None:
            gamma = np.ones(frequency.npoints, dtype=complex)
        else:
            fixture = self._fixture.interpolate(frequency)
            gamma = fixture.s[:, 0, 0]

        s_two_port = self._coupler.two_port_response(frequency, gamma)
        network = Network(frequency=frequency, s=s_two_port)
        network.name = "Simulated Measurement"
        return network

    def get_frequency_points(self) -> np.ndarray:
        return np.linspace(self._start_freq, self._stop_freq, self._points)

    def set_calibration(self, cal_data: Optional[Dict]) -> None:
        if not self._connected:
            raise RuntimeError("VNA not connected")

    def get_port_count(self) -> int:
        return 2

    # ------------------------------------------------------------------
    # Coupler / fixture helpers
    # ------------------------------------------------------------------
    def set_fixture(self, network: Optional[Network], name: str = "Fixture") -> None:
        if network is None:
            self._fixture = None
            self._fixture_name = "Open"
            return

        self._fixture = network.copy()
        self._fixture_name = name or (network.name or "Fixture")

    def get_fixture_network(self) -> Optional[Network]:
        if self._fixture is None:
            return None
        return self._fixture.copy()

    def get_coupler_network(self) -> Network:
        frequency = Frequency(start=self._start_freq, stop=self._stop_freq, npoints=self._points, unit="Hz")
        if self._emulator_coupler is not None:
            return self._emulator_coupler.interpolate(frequency)
        return self._coupler.three_port_network(frequency)

    # ------------------------------------------------------------------
    # Emulator integration
    # ------------------------------------------------------------------
    def load_emulator_coupler(self, touchstone_path: str) -> None:
        """Load a 4-port coupler network from a Touchstone file for emulator-based simulation.

        The port mapping follows the colleague's emulator:
        0: input, 1: through, 2: coupled, 3: isolated.
        """
        self._emulator_coupler = Network(touchstone_path)
        # Cache emulator frequency limits for UI constraints
        f = self._emulator_coupler.frequency.f
        if f is not None and len(f):
            self._emu_freq_limits = (float(f.min()), float(f.max()))
        # If the file is 4-port, keep as-is; if 3-port, still usable.

    def set_emulator_link_gains(self, downlink_db: float = -30.0, uplink_db: float = 20.0) -> None:
        self._downlink_gain_db = float(downlink_db)
        self._uplink_gain_db = float(uplink_db)

    def set_emulator_calibration_enabled(self, enabled: bool = True) -> None:
        """Enable using emulator-style OSL calibration when applying calibration in simulation mode."""
        self._emu_cal_enabled = bool(enabled)

    def get_emulator_frequency_limits(self) -> Optional[tuple[float, float]]:
        """Return (min_hz, max_hz) limits from emulator coupler file for UI constraints."""
        return self._emu_freq_limits
