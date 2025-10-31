# OH4VNA Project - Copilot Instructions

## Project Overview
OH4VNA is a Python-based VNA (Vector Network Analyzer) measurement application that recreates SPEAG OH4VNA functionality using modern web technologies.

### Core Architecture
- **Frontend**: Streamlit web application with Z43 corporate design system
- **Backend**: scikit-rf for RF analysis, PyVISA for instrument control
- **Target Hardware**: Rohde & Schwarz ZVA series VNA
- **Data Format**: Touchstone files with JSON metadata persistence

## Z43 Design System Compliance
**CRITICAL**: Always follow Z43 corporate design guidelines from gui.z43.swiss

### Official Color Palette (Use Exact Values)
- **S4L Blue**: `#0090D0` - Primary brand color, magnitude plots
- **SPEAG Yellow**: `#FFDD00` - Secondary accent color
- **S4L Orange**: `#FF9200` - Warning/highlight, phase plots  
- **ISO Prohibition Red**: `#9B2423` - Error states

### Design Principles
- Clean, professional typography and layout
- WCAG-compliant contrast ratios for accessibility
- CSS design tokens using custom properties
- Simple text labels in navigation (no emojis)

## Architecture Guidelines

### Services Layer Pattern
```
oh4vna/
├── instrument/     # VNA abstraction (base, R&S, simulation)
├── services/       # Business logic (instrument, calibration, measurement)
└── data/          # Models and persistence (Pydantic + repository pattern)
```

### Key Services
- **InstrumentManager**: Connection state and instrument selection
- **CalibrationService**: SOL/SOLT workflow with live Smith charts
- **MeasurementService**: Sweep orchestration and data persistence

### Professional VNA Workflow
1. **Connection**: Instrument detection and setup
2. **Calibration**: Traditional SOL/SOLT sequence with live monitoring
3. **Measurement**: Sweep configuration and execution
4. **Analysis**: Data visualization and processing

## Data Management
- **Touchstone Files**: Standard S-parameter format for measurements
- **JSON Metadata**: Timestamps, configuration, instrument info
- **Traceable Archiving**: Serial number and date-based organization
- **Kit Management**: Calibration standard definitions and history

## Development Standards

### Code Quality
- Full type hints throughout codebase
- Pydantic models for data validation
- Comprehensive error handling and logging
- Docstrings and inline documentation

### Testing Approach
- **Simulation Mode**: Built-in testing without hardware (default)
- **Hardware Mode**: Real VNA operation when available
- Mock instruments for unit testing

### Environment Setup
```bash
# Standard development setup
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run app.py
```

## Context Preservation
**Important**: See `.github/copilot-context.md` for complete conversation history and technical decisions made during initial implementation.

## Key Features Implemented
- Complete Z43 design system with official corporate colors
- Professional VNA calibration workflow (SOL/SOLT)
- Real-time Smith chart monitoring during calibration
- OH4VNA 3-port coupler analytical model integration
- Touchstone persistence with JSON metadata
- Simulation mode for offline development
- Clean services architecture for scalability

## Critical Notes
- **Z43 Compliance**: Never use generic colors - always use exact Z43 palette
- **Professional Workflow**: Maintain traditional VNA measurement sequence
- **Simulation Support**: Ensure offline development capabilities remain functional
- **Context Continuity**: Reference `.github/copilot-context.md` for implementation history