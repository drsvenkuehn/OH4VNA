"""Measurement orchestration service."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from skrf import Network

from ..data import CalibrationRecord, MeasurementConfig, MeasurementRecord, MetadataRepository
from .instrument_manager import InstrumentManager


class MeasurementService:
    """Coordinates sweep execution, persistence, and metadata."""

    def __init__(self, instrument_manager: InstrumentManager, repository: MetadataRepository) -> None:
        self._instrument_manager = instrument_manager
        self._repository = repository

    def run_measurement(
        self,
        config: MeasurementConfig,
        calibration: Optional[CalibrationRecord] = None,
        notes: Optional[str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> Tuple[MeasurementRecord, Network]:
        """Execute a measurement sweep and persist outputs."""

        if not self._instrument_manager.is_connected:
            raise RuntimeError("No instrument connected")

        instrument = self._instrument_manager.instrument
        if instrument is None:
            raise RuntimeError("Instrument reference is unavailable")

        instrument.configure_sweep(
            start_freq=config.start_freq,
            stop_freq=config.stop_freq,
            points=config.points,
            if_bandwidth=config.if_bandwidth,
            power=config.power,
        )
        port_count = max(config.port_count, config.source_port, config.destination_port)
        instrument.configure_ports(port_count=port_count)
        instrument.trigger_sweep()

        if not instrument.wait_for_sweep():
            raise TimeoutError("Sweep did not complete in time")

        network = instrument.get_s_parameters()

        if port_count != config.port_count:
            config = config.model_copy(update={"port_count": port_count})

        instrument_info = self._instrument_manager.get_info().get("info") or {}

        record = MeasurementRecord(
            config=config,
            instrument_info=instrument_info,
            calibration_id=calibration.id if calibration else None,
            notes=notes,
            tags=list(tags) if tags else [],
        )

        record = self._repository.save_measurement(record, network)
        return record, network

    def list_recent(self, limit: int = 25) -> List[MeasurementRecord]:
        """Return recent measurement records."""

        return self._repository.list_measurements(limit=limit)

    def load_network(self, record: MeasurementRecord) -> Network:
        """Load the network data for a stored measurement."""

        return self._repository.load_network(record)
