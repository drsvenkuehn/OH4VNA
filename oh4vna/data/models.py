"""Metadata models used across the application."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MeasurementConfig(BaseModel):
    """Configuration parameters for a measurement sweep."""

    start_freq: float = Field(..., gt=0, description="Start frequency in Hz")
    stop_freq: float = Field(..., gt=0, description="Stop frequency in Hz")
    points: int = Field(..., ge=11, le=200001, description="Number of sweep points")
    if_bandwidth: float = Field(..., gt=0, description="IF bandwidth in Hz")
    power: float = Field(..., description="Source power in dBm")
    port_count: int = Field(2, ge=1, le=32, description="Number of active ports")
    source_port: int = Field(1, ge=1, description="Excitation port index")
    destination_port: int = Field(2, ge=1, description="Measurement port index")
    averaging: int = Field(1, ge=1, le=256, description="Number of averages per point")
    sweep_type: Literal["linear", "log", "segment"] = Field("linear")

    @property
    def s_parameter_label(self) -> str:
        """Return the selected transmission S-parameter label (e.g. S21)."""

        return f"S{self.destination_port}{self.source_port}"


class CalibrationRecord(BaseModel):
    """Metadata describing a calibration run."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    operator: str = Field(default="Unknown")
    method: Literal["SOL", "TRL", "Auto"] = Field("SOL")
    port_count: int = Field(1, ge=1, le=4)
    standards_completed: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    instrument_info: Dict[str, Any] = Field(default_factory=dict)
    calibration_kit_id: Optional[str] = Field(default=None)
    calibration_kit_name: Optional[str] = Field(default=None)
    calibration_kit_files: Dict[str, str] = Field(default_factory=dict)
    calibration_kit_serial: Optional[str] = Field(default=None)
    calibration_kit_date: Optional[str] = Field(default=None)
    metadata_path: Optional[Path] = None
    expires_at: Optional[datetime] = None

    def is_valid(self, now: Optional[datetime] = None) -> bool:
        """Return True if calibration is still considered valid."""

        current_time = now or datetime.utcnow()
        if self.expires_at:
            return current_time <= self.expires_at
        # Default validity window: 8 hours from calibration time
        return current_time <= self.timestamp + timedelta(hours=8)


class MeasurementRecord(BaseModel):
    """Metadata describing an executed measurement."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    config: MeasurementConfig
    instrument_info: Dict[str, Any] = Field(default_factory=dict)
    calibration_id: Optional[str] = None
    touchstone_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    class Config:
        json_encoders = {Path: lambda p: str(p)}
