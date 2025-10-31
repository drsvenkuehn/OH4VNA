# OH4VNA - VNA Measurement Application

A Python-based VNA measurement application that recreates SPEAG OH4VNA functionality using Streamlit frontend and scikit-rf backend.

## Features

- **Streamlit Web Interface**: Modern web-based UI for VNA measurements
- **Scikit-RF Backend**: Professional RF measurement and analysis capabilities
- **VNA Support**: Rohde & Schwarz ZVA instruments via PyVISA
- **Data Persistence**: Touchstone file format with JSON metadata
- **Development Mode**: Simulation support for offline development
- **Notebook Integration**: Jupyter notebooks for R&D and validation
- **Calibration Toolkit**: Live Smith chart monitoring with importable OSL kits (including a perfect kit)
- **Coupler Model**: Three-port OH4VNA coupler simulation cascaded into the two-port VNA so S32 workflows behave realistically without hardware
- **Kit Archiving**: Imported OSL kits land under `data/metadata/calibration_kits/<kit-id>/MCK4OH_SN####_YYYYMMDD/` for traceable serial/date management

## Architecture

- **Frontend**: Streamlit web application with real-time plotting
- **Backend Services**: Instrument management, calibration, measurement orchestration
- **Data Layer**: Touchstone files with JSON metadata indexing
- **Notebooks**: Research and development environment

## Quick Start

### Installation

```bash
# Install dependencies
pip install -e ".[dev]"

# Run in development mode (simulation)
streamlit run oh4vna/app.py

# Run with hardware (requires VNA connection)
OH4VNA_SIMULATION=false streamlit run oh4vna/app.py
```

### Configuration

Copy `configs/settings.example.yaml` to `configs/settings.yaml` and configure:
- VNA connection parameters
- Data storage paths
- Calibration kit definitions

## Project Structure

```
oh4vna/                 # Core Python package
├── instrument/         # VNA drivers and abstractions
├── services/          # Business logic services
├── data/              # Data persistence layer
└── utils/             # Shared utilities

app/                   # Streamlit application
├── pages/             # Multi-page app structure
└── components/        # Reusable UI components
 
# Verify configuration layer after dependency updates
streamlit run oh4vna/app.py --server.headless true  # ensure app still boots after config changes

notebooks/             # Jupyter notebooks for R&D
configs/              # Configuration files
tests/                # Test suite
docs/                 # Documentation
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code formatting
black .
isort .

# Type checking
mypy oh4vna/

# Start Jupyter for notebook development
jupyter lab
```

## Hardware Requirements

- Rohde & Schwarz ZVA series VNA
- VISA-compatible connection (Ethernet, USB, or GPIB)
- Python 3.9 or higher

## License

MIT License - see LICENSE file for details.