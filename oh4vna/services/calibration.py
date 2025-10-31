"""Calibration service handling metadata and validity tracking."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..data import CalibrationRecord, MetadataRepository


class CalibrationService:
    """Manages calibration lifecycle and persistence."""

    def __init__(self, repository: MetadataRepository, validity_hours: int = 8) -> None:
        self._repository = repository
        self._validity = timedelta(hours=validity_hours)
        self._current: Optional[CalibrationRecord] = self._repository.get_latest_calibration()

    @property
    def current(self) -> Optional[CalibrationRecord]:
        """Return the current calibration record, if any."""

        if self._current and not self._current.is_valid():
            return None
        return self._current

    def is_valid(self, port_count: int = 1) -> bool:
        """Return True if there is a calibration still within its validity window."""

        record = self.current
        if not record:
            return False
        return record.port_count >= port_count

    def record_manual_calibration(
        self,
        operator: str,
        method: str,
        port_count: int,
        standards_completed: List[str],
        instrument_info: Optional[dict] = None,
        notes: Optional[str] = None,
        calibration_kit: Optional[Dict[str, str]] = None,
    ) -> CalibrationRecord:
        """Store a manual calibration event and set it as current."""

        now = datetime.utcnow()
        record = CalibrationRecord(
            operator=operator or "Unknown",
            method=method or "SOL",
            port_count=port_count,
            standards_completed=standards_completed,
            notes=notes,
            instrument_info=instrument_info or {},
            calibration_kit_id=(calibration_kit or {}).get("id"),
            calibration_kit_name=(calibration_kit or {}).get("name"),
            calibration_kit_files=(calibration_kit or {}).get("files", {}),
            calibration_kit_serial=(calibration_kit or {}).get("serial"),
            calibration_kit_date=(calibration_kit or {}).get("calibration_date"),
            timestamp=now,
            expires_at=now + self._validity,
        )

        record = self._repository.save_calibration(record)
        self._current = record
        return record

    # ------------------------------------------------------------------
    # Calibration kits
    # ------------------------------------------------------------------
    def list_calibration_kits(self) -> List[Dict[str, str]]:
        """Return metadata for available calibration kits."""

        return self._repository.list_calibration_kits()

    def get_calibration_kit(self, kit_id: str) -> Optional[Dict[str, str]]:
        """Return metadata for a specific calibration kit."""

        return self._repository.get_calibration_kit(kit_id)

    def import_calibration_kit(
        self,
        name: str,
        touchstones: Dict[str, bytes],
        serial: str,
        calibration_date: str,
    ) -> Dict[str, str]:
        """Persist a new calibration kit and return its metadata."""

        return self._repository.import_calibration_kit(name, touchstones, serial, calibration_date)

    def refresh(self) -> Optional[CalibrationRecord]:
        """Reload the latest calibration from disk."""

        self._current = self._repository.get_latest_calibration()
        return self.current

    def recent(self, limit: int = 10) -> List[CalibrationRecord]:
        """Return recent calibration records."""

        return self._repository.list_calibrations(limit=limit)
