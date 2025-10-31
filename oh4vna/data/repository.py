"""Persistence helpers for measurement, calibration metadata, and calibration kits."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from skrf import Frequency, Network

from ..config import settings
from .models import CalibrationRecord, MeasurementRecord


class MetadataRepository:
    """Handles storage of Touchstone files and metadata JSON."""

    def __init__(self, root_touchstone: Path | None = None, root_metadata: Path | None = None) -> None:
        self.touchstone_dir = Path(root_touchstone or settings.touchstone_dir)
        self.metadata_dir = Path(root_metadata or settings.metadata_dir)

        self._calibration_dir = self.metadata_dir / "calibrations"
        self._measurement_dir = self.metadata_dir / "measurements"
        self._calibration_kits_dir = self.metadata_dir / "calibration_kits"

        self.touchstone_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self._calibration_dir.mkdir(parents=True, exist_ok=True)
        self._measurement_dir.mkdir(parents=True, exist_ok=True)
        self._calibration_kits_dir.mkdir(parents=True, exist_ok=True)

        self._ensure_perfect_osl_kit(
            start_freq=float(settings.default_start_freq),
            stop_freq=float(settings.default_stop_freq),
            points=int(settings.default_points),
        )

    # ---------------------------------------------------------------------
    # Calibration persistence
    # ---------------------------------------------------------------------
    def save_calibration(self, record: CalibrationRecord) -> CalibrationRecord:
        """Persist calibration metadata to disk."""

        timestamp = record.timestamp.strftime("%Y%m%d_%H%M%S")
        metadata_path = self._calibration_dir / f"cal_{timestamp}_{record.id}.json"
        self._write_json(metadata_path, record.model_dump(mode="json"))
        record.metadata_path = metadata_path
        return record

    def list_calibrations(self, limit: int = 25) -> List[CalibrationRecord]:
        """Return calibration records sorted by newest first."""

        records = [
            self._read_calibration(path)
            for path in sorted(self._calibration_dir.glob("cal_*.json"), reverse=True)
        ]
        return [rec for rec in records if rec is not None][:limit]

    def get_latest_calibration(self) -> Optional[CalibrationRecord]:
        """Return the most recent calibration record if available."""

        calibrations = self.list_calibrations(limit=1)
        return calibrations[0] if calibrations else None

    # ---------------------------------------------------------------------
    # Measurement persistence
    # ---------------------------------------------------------------------
    def save_measurement(self, record: MeasurementRecord, network: Network) -> MeasurementRecord:
        """Persist measurement data and metadata."""

        timestamp = record.timestamp.strftime("%Y%m%d_%H%M%S")
        base_name = f"meas_{timestamp}_{record.id[:8]}"

        touchstone_path = Path(
            self._write_touchstone(network, self.touchstone_dir / f"{base_name}.s{network.nports}p")
        )
        metadata_path = self._measurement_dir / f"{base_name}.json"

        record.touchstone_path = touchstone_path
        record.metadata_path = metadata_path
        self._write_json(metadata_path, record.model_dump(mode="json"))
        return record

    def list_measurements(self, limit: int = 50) -> List[MeasurementRecord]:
        """Return measurement metadata sorted by newest first."""

        records = [
            self._read_measurement(path)
            for path in sorted(self._measurement_dir.glob("meas_*.json"), reverse=True)
        ]
        return [rec for rec in records if rec is not None][:limit]

    def load_measurement(self, record_id: str) -> Optional[MeasurementRecord]:
        """Load a specific measurement record by identifier."""

        for path in self._measurement_dir.glob(f"meas_*_{record_id[:8]}.json"):
            return self._read_measurement(path)
        return None

    def load_network(self, record: MeasurementRecord) -> Network:
        """Load the scikit-rf network for a measurement record."""

        if not record.touchstone_path:
            raise FileNotFoundError("Measurement record has no Touchstone path")
        return Network(str(record.touchstone_path))

    # ------------------------------------------------------------------
    # Calibration kits
    # ------------------------------------------------------------------
    def list_calibration_kits(self) -> List[Dict[str, str]]:
        """Return available calibration kits with metadata."""

        kits: List[Dict[str, str]] = []
        for kit_dir in sorted(self._calibration_kits_dir.glob("*")):
            if kit_dir.is_dir():
                metadata = self._read_kit_metadata(kit_dir)
                if metadata:
                    kits.append(metadata)
        return kits

    def get_calibration_kit(self, kit_id: str) -> Optional[Dict[str, str]]:
        """Return metadata for a specific calibration kit."""

        kit_dir = self._calibration_kits_dir / kit_id
        if not kit_dir.exists():
            return None
        return self._read_kit_metadata(kit_dir)

    def import_calibration_kit(
        self,
        name: str,
        touchstones: Dict[str, bytes],
        serial: str,
        calibration_date: str,
    ) -> Dict[str, str]:
        """Persist uploaded calibration kit touchstone files."""

        if not name.strip():
            raise ValueError("Calibration kit name is required")

        slug = self._slugify(name)
        kit_dir = self._calibration_kits_dir / slug
        kit_dir.mkdir(parents=True, exist_ok=True)

        serial_norm = self._normalise_serial(serial)
        date_norm = self._normalise_date(calibration_date)
        bundle_dir = self._bundle_directory(kit_dir, serial_norm, date_norm)
        bundle_dir.mkdir(parents=True, exist_ok=True)

        stored_files: Dict[str, str] = {}
        for standard in ("open", "short", "load"):
            payload = touchstones.get(standard)
            if payload is None:
                raise ValueError(f"Missing Touchstone file for {standard.title()}")
            target = bundle_dir / f"{standard}.s1p"
            with target.open("wb") as handle:
                handle.write(payload)

            # Validate loadable network
            Network(str(target))
            stored_files[standard] = str(target)

        metadata = {
            "id": slug,
            "name": name.strip(),
            "files": stored_files,
            "serial": serial_norm,
            "calibration_date": date_norm,
            "bundle": str(bundle_dir),
            "created_at": datetime.utcnow().isoformat(),
        }
        self._write_kit_metadata(kit_dir, metadata)
        return metadata

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=self._json_serializer)

    def _read_calibration(self, path: Path) -> Optional[CalibrationRecord]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            record = CalibrationRecord.model_validate(payload)
            record.metadata_path = path
            return record
        except Exception:
            return None

    def _read_measurement(self, path: Path) -> Optional[MeasurementRecord]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            record = MeasurementRecord.model_validate(payload)
            record.metadata_path = path
            if record.touchstone_path:
                record.touchstone_path = Path(record.touchstone_path)
            return record
        except Exception:
            return None

    def _json_serializer(self, value):  # type: ignore[no-untyped-def]
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    # ------------------------------------------------------------------
    # Calibration kit helpers
    # ------------------------------------------------------------------
    def _ensure_perfect_osl_kit(self, start_freq: float, stop_freq: float, points: int) -> None:
        """Create an ideal OSL kit for quick-start usage if missing."""

        kit_dir = self._calibration_kits_dir / "perfect-osl"
        meta_file = kit_dir / "kit.json"
        if meta_file.exists():
            existing = self._read_kit_metadata(kit_dir)
            if existing:
                bundle_path = Path(existing.get("bundle", ""))
                if bundle_path.exists() and bundle_path.is_dir() and bundle_path.parent == kit_dir:
                    return
            # if metadata is missing bundle folder, regenerate below

        kit_dir.mkdir(parents=True, exist_ok=True)

        frequency = Frequency(start=start_freq, stop=stop_freq, npoints=points, unit="Hz")
        s_shape = (frequency.npoints, 1, 1)

        open_net = Network(frequency=frequency, s=np.ones(s_shape, dtype=complex))
        short_net = Network(frequency=frequency, s=-1 * np.ones(s_shape, dtype=complex))
        load_net = Network(frequency=frequency, s=np.zeros(s_shape, dtype=complex))

        serial_norm = self._normalise_serial("0000")
        date_norm = datetime.utcnow().strftime("%Y%m%d")
        bundle_dir = self._bundle_directory(kit_dir, serial_norm, date_norm)
        bundle_dir.mkdir(parents=True, exist_ok=True)

        files = {
            "open": self._write_touchstone(open_net, bundle_dir / "open.s1p"),
            "short": self._write_touchstone(short_net, bundle_dir / "short.s1p"),
            "load": self._write_touchstone(load_net, bundle_dir / "load.s1p"),
        }

        metadata = {
            "id": "perfect-osl",
            "name": "Perfect OSL",
            "files": files,
            "serial": serial_norm,
            "calibration_date": date_norm,
            "bundle": str(bundle_dir),
            "created_at": datetime.utcnow().isoformat(),
        }
        self._write_kit_metadata(kit_dir, metadata)

    def _write_touchstone(self, network: Network, target_with_suffix: Path) -> str:
        """Write a network to a target .sNp file and return the path as string."""

        base = target_with_suffix.with_suffix("")
        network.write_touchstone(str(base))
        generated = base.with_suffix(f".s{network.nports}p")
        final_path = target_with_suffix
        if generated != final_path:
            generated.rename(final_path)
        return str(final_path)

    def _slugify(self, value: str) -> str:
        """Convert a display name into a filesystem-safe identifier."""

        slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
        slug = re.sub(r"-+", "-", slug).strip("-") or "cal-kit"
        candidate = slug
        counter = 1
        while (self._calibration_kits_dir / candidate).exists():
            candidate = f"{slug}-{counter}"
            counter += 1
        return candidate

    def _write_kit_metadata(self, kit_dir: Path, metadata: Dict[str, str]) -> None:
        meta_path = kit_dir / "kit.json"
        with meta_path.open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)

    def _read_kit_metadata(self, kit_dir: Path) -> Optional[Dict[str, str]]:
        meta_path = kit_dir / "kit.json"
        if not meta_path.exists():
            return None
        try:
            with meta_path.open("r", encoding="utf-8") as handle:
                metadata = json.load(handle)
            metadata.setdefault("id", kit_dir.name)
            metadata.setdefault("serial", "0000")
            metadata.setdefault("calibration_date", datetime.utcnow().strftime("%Y%m%d"))
            if "bundle" not in metadata:
                files = metadata.get("files", {})
                first_path = next(iter(files.values()), None)
                if first_path:
                    metadata["bundle"] = str(Path(first_path).parent)
                else:
                    metadata["bundle"] = str(kit_dir)
            return metadata
        except Exception:
            return None

    def _normalise_serial(self, serial: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]", "", serial.upper())
        if not cleaned:
            cleaned = "0000"
        if cleaned.isdigit() and len(cleaned) < 4:
            cleaned = cleaned.zfill(4)
        return cleaned

    def _normalise_date(self, date_str: str) -> str:
        digits = re.sub(r"[^0-9]", "", date_str)
        if len(digits) == 8:
            return digits
        return datetime.utcnow().strftime("%Y%m%d")

    def _bundle_directory(self, kit_dir: Path, serial: str, calibration_date: str) -> Path:
        base_name = f"MCK4OH_SN{serial}_{calibration_date}"
        candidate = kit_dir / base_name
        counter = 1
        while candidate.exists():
            candidate = kit_dir / f"{base_name}_{counter}"
            counter += 1
        return candidate
