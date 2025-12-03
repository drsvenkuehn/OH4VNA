"""Configuration management for OH4VNA."""

from pathlib import Path
from typing import Optional, Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Application settings
    debug: bool = Field(False, env="OH4VNA_DEBUG")
    simulation_mode: bool = Field(True, env="OH4VNA_SIMULATION")

    # Data storage
    data_root: Path = Field(Path("./data"), env="OH4VNA_DATA_ROOT")
    touchstone_dir: Path = Field(Path("./data/touchstone"), env="OH4VNA_TOUCHSTONE_DIR")
    metadata_dir: Path = Field(Path("./data/metadata"), env="OH4VNA_METADATA_DIR")

    # VNA settings
    vna_address: Optional[str] = Field(None, env="OH4VNA_VNA_ADDRESS")
    vna_timeout: int = Field(30000, env="OH4VNA_VNA_TIMEOUT")  # milliseconds

    # Measurement defaults
    default_start_freq: float = Field(1e6, env="OH4VNA_START_FREQ")  # 1 MHz
    default_stop_freq: float = Field(6e9, env="OH4VNA_STOP_FREQ")   # 6 GHz
    default_points: int = Field(201, env="OH4VNA_POINTS")
    default_if_bandwidth: float = Field(1000, env="OH4VNA_IF_BW")  # Hz
    default_power: float = Field(-10, env="OH4VNA_POWER")  # dBm

    # Calibration
    cal_kit_name: str = Field("Unknown", env="OH4VNA_CAL_KIT")

    # Emulator integration (optional)
    emulator_coupler_path: Optional[Path] = Field(
        default=Path("./emulator/Sprams MACP-011045_corrected/MACP-011045_02_corrected.s4p"),
        env="OH4VNA_EMULATOR_COUPLER"
    )
    emulator_downlink_gain_db: float = Field(-30.0, env="OH4VNA_EMULATOR_DL_DB")
    emulator_uplink_gain_db: float = Field(20.0, env="OH4VNA_EMULATOR_UL_DB")

    def model_post_init(self, __context: Any) -> None:
        """Ensure data directories exist."""
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.touchstone_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()