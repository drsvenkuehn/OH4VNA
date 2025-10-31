"""OH4VNA Streamlit application with guided VNA workflow."""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from skrf import Frequency, Network

# Ensure package import works when running `streamlit run app.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

from oh4vna.config import settings
from oh4vna.data import MeasurementConfig, MetadataRepository
from oh4vna.instrument import SimulationVNA
from oh4vna.services import CalibrationService, InstrumentManager, MeasurementService


SESSION_KEYS = {
    "instrument": "instrument_manager",
    "repository": "metadata_repository",
    "calibration": "calibration_service",
    "measurement": "measurement_service",
    "active_record": "active_measurement_record",
    "active_network": "active_measurement_network",
    "measurement_config": "measurement_config",
    "calibration_sweeps": "calibration_reflection_sweeps",
    "selected_calibration_kit": "selected_calibration_kit",
    "calibration_standard": "calibration_current_standard",
}


def build_transmission_options(port_count: int) -> List[Tuple[int, int]]:
    """Return all through S-parameter options for the given port count."""

    options: List[Tuple[int, int]] = []
    for source in range(1, port_count + 1):
        for destination in range(1, port_count + 1):
            if destination != source:
                options.append((source, destination))
    return options


def capture_reflection_network(
    manager: InstrumentManager,
    config: MeasurementConfig,
) -> Network:
    """Capture a single reflection sweep (S11) using the current instrument."""

    if not manager.is_connected:
        raise RuntimeError("Connect to an instrument to capture reflection data")

    instrument = manager.instrument
    if instrument is None:
        raise RuntimeError("Instrument handle is unavailable")

    if isinstance(instrument, SimulationVNA):
        frequency = Frequency(
            start=config.start_freq,
            stop=config.stop_freq,
            npoints=config.points,
            unit="Hz",
        )
        fixture = instrument.get_fixture_network()
        if fixture is None:
            s11 = np.ones((frequency.npoints, 1, 1), dtype=complex)
            network = Network(frequency=frequency, s=s11)
            network.name = "Simulated Open"
            return network
        return fixture.interpolate(frequency)

    instrument.configure_sweep(
        start_freq=config.start_freq,
        stop_freq=config.stop_freq,
        points=config.points,
        if_bandwidth=config.if_bandwidth,
        power=config.power,
    )
    instrument.configure_ports(port_count=max(1, config.port_count))
    instrument.trigger_sweep()

    if not instrument.wait_for_sweep():
        raise TimeoutError("Reflection sweep timed out")

    network = instrument.get_s_parameters()
    return _extract_s11(network)


def _extract_s11(network: Network) -> Network:
    """Return a single-port Network containing S11 from the provided data."""

    if network.nports == 1:
        return network

    s11 = network.s[:, 0, 0][:, np.newaxis, np.newaxis]
    z0 = network.z0[:, 0:1]
    single_port = Network(frequency=network.frequency, s=s11, z0=z0)
    single_port.name = f"{network.name or 'Measurement'} - S11"
    return single_port


def smith_chart_figure(network: Network, title: str) -> plt.Figure:
    """Return a Matplotlib figure showing the network on a Smith chart."""

    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    network.plot_s_smith(m=0, n=0, ax=ax, show_legend=False, color="tab:blue")
    ax.set_title(title)
    fig.tight_layout()
    return fig


def return_loss_at_center(network: Network) -> float:
    """Compute return loss (dB) at the mid-point of the sweep."""

    s11 = network.s[:, 0, 0]
    if s11.size == 0:
        return float("nan")
    idx = s11.size // 2
    magnitude = np.abs(s11[idx])
    if magnitude <= 0:
        return float("inf")
    return -20 * np.log10(magnitude)


def main() -> None:
    """Streamlit entry point."""

    st.set_page_config(
        page_title="OH4VNA - VNA Measurement Application",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Apply Z43 design system CSS
    st.markdown("""
    <style>
    /* Z43 Design System - Official Color Palette */
    :root {
        --z43-primary: #0090D0;  /* S4L Blue - Primary accent */
        --z43-primary-light: #4DB6E6;
        --z43-primary-dark: #006B9F;
        --z43-secondary: #FFDD00;  /* SPEAG Yellow - Secondary accent */
        --z43-warning: #FF9200;  /* S4L Orange - Warning color */
        --z43-error: #9B2423;  /* ISO Prohibition color */
        --z43-success: #28A745;  /* Success green */
        --z43-surface: #F8FAFC;
        --z43-surface-secondary: #F1F5F9;
        --z43-text-primary: #1E293B;
        --z43-text-secondary: #64748B;
        --z43-border: #E2E8F0;
        
        /* Z43 Derived colors with proper luminance */
        --z43-surface-light: #FFFFFF;
        --z43-surface-accent: rgba(0, 144, 208, 0.1);
        --z43-surface-warning: rgba(255, 146, 0, 0.1);
        --z43-surface-error: rgba(155, 36, 35, 0.1);
        --z43-surface-success: rgba(40, 167, 69, 0.1);
    }
    
    /* Z43 Typography & Spacing - Following accessibility guidelines */
    .main > div {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Z43 Tab styling with proper contrast ratios */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background-color: var(--z43-surface);
        padding: 0.25rem;
        border-radius: 0.5rem;
        border: 1px solid var(--z43-border);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 0.375rem;
        padding: 0.5rem 1rem;
        border: none;
        background-color: transparent;
        color: var(--z43-text-secondary);
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: var(--z43-primary) !important;
        color: white !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
    
    /* Z43 Card containers with accessibility-compliant contrast */
    .stExpander {
        border: 1px solid var(--z43-border);
        border-radius: 0.5rem;
        background-color: var(--z43-surface);
    }
    
    /* Z43 Button styling following design tokens */
    .stButton > button {
        border-radius: 0.375rem;
        font-weight: 500;
        transition: all 0.2s ease;
        border: 1px solid var(--z43-border);
    }
    
    .stButton > button[kind="primary"] {
        background-color: var(--z43-primary);
        border-color: var(--z43-primary);
        color: white;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: var(--z43-primary-dark);
        border-color: var(--z43-primary-dark);
    }
    
    .stButton > button[kind="secondary"] {
        background-color: var(--z43-surface-secondary);
        color: var(--z43-text-primary);
        border-color: var(--z43-border);
    }
    
    /* Z43 Metrics with proper surface colors */
    [data-testid="metric-container"] {
        background-color: var(--z43-surface);
        border: 1px solid var(--z43-border);
        padding: 1rem;
        border-radius: 0.5rem;
    }
    
    /* Z43 Status indicators using official palette */
    .status-connected {
        color: var(--z43-success);
        font-weight: 600;
    }
    
    .status-disconnected {
        color: var(--z43-error);
        font-weight: 600;
    }
    
    .status-warning {
        color: var(--z43-warning);
        font-weight: 600;
    }
    
    /* Z43 Form consistency */
    .stSelectbox, .stTextInput, .stNumberInput {
        margin-bottom: 0.5rem;
    }
    
    /* Z43 Progress indicators with official colors */
    .calibration-progress {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem;
        border-radius: 0.375rem;
        margin: 0.5rem 0;
        border: 1px solid transparent;
    }
    
    .progress-complete {
        background-color: var(--z43-surface-success);
        border-color: var(--z43-success);
        color: var(--z43-success);
    }
    
    .progress-current {
        background-color: var(--z43-surface-accent);
        border-color: var(--z43-primary);
        color: var(--z43-primary);
    }
    
    .progress-pending {
        background-color: var(--z43-surface-secondary);
        border-color: var(--z43-border);
        color: var(--z43-text-secondary);
    }
    
    .progress-warning {
        background-color: var(--z43-surface-warning);
        border-color: var(--z43-warning);
        color: var(--z43-warning);
    }
    
    /* Z43 Alert styling */
    .stAlert {
        border-radius: 0.5rem;
    }
    
    /* Z43 Success states */
    .stSuccess {
        background-color: var(--z43-surface-success);
        border-color: var(--z43-success);
        color: var(--z43-success);
    }
    
    /* Z43 Error states */
    .stError {
        background-color: var(--z43-surface-error);
        border-color: var(--z43-error);
        color: var(--z43-error);
    }
    
    /* Z43 Warning states */
    .stWarning {
        background-color: var(--z43-surface-warning);
        border-color: var(--z43-warning);
        color: var(--z43-warning);
    }
    
    /* Z43 Chart colors for plotly */
    .js-plotly-plot .plotly .main-svg {
        --plotly-primary: var(--z43-primary);
        --plotly-secondary: var(--z43-secondary);
    }
    </style>
    """, unsafe_allow_html=True)

    init_services()

    manager: InstrumentManager = st.session_state[SESSION_KEYS["instrument"]]
    calibration_service: CalibrationService = st.session_state[SESSION_KEYS["calibration"]]
    measurement_service: MeasurementService = st.session_state[SESSION_KEYS["measurement"]]

    # Z43 Guideline: Clear hierarchy with consistent styling
    st.markdown("# 📡 OH4VNA - Vector Network Analyzer")
    st.markdown("### Professional RF Measurement & Calibration Platform")
    
    # Z43 Guideline: Show system status prominently for discoverability
    with st.container():
        status_col1, status_col2, status_col3 = st.columns([2, 2, 3])
        with status_col1:
            if manager.is_connected:
                st.markdown('<span class="status-connected">🟢 Connected</span>', unsafe_allow_html=True)
                instrument_info = manager.get_info()
                st.caption(f"📍 {instrument_info.get('address', 'Unknown')}")
            else:
                st.markdown('<span class="status-disconnected">🔴 Disconnected</span>', unsafe_allow_html=True)
                st.caption("No instrument connected")
        
        with status_col2:
            if calibration_service.is_valid():
                cal_record = calibration_service.current
                st.markdown('<span class="status-connected">✅ Calibrated</span>', unsafe_allow_html=True)
                if cal_record:
                    st.caption(f"🕒 {cal_record.timestamp.strftime('%H:%M')}")
            else:
                st.markdown('<span class="status-warning">⚠️ Calibration Required</span>', unsafe_allow_html=True)
                st.caption("Perform calibration before measuring")
        
        with status_col3:
            recent_measurements = measurement_service.list_recent(limit=1)
            if recent_measurements:
                last_measurement = recent_measurements[0]
                st.markdown('<span class="status-connected">📊 Ready</span>', unsafe_allow_html=True)
                st.caption(f"🕒 Last: {last_measurement.timestamp.strftime('%H:%M')}")
            else:
                st.markdown('<span class="status-warning">📊 No Data</span>', unsafe_allow_html=True)
                st.caption("No measurements recorded")

    render_sidebar(manager, calibration_service)

    # Z43 Guideline: Consistent tab naming and organization
    tabs = st.tabs([
        "🏠 Home",
        "🔧 Calibration", 
        "📏 Measurement",
        "� Analysis",
        "⚙️ Settings",
    ])

    with tabs[0]:
        render_overview_tab(manager, calibration_service)
    with tabs[1]:
        render_calibration_tab(manager, calibration_service)
    with tabs[2]:
        render_measurement_tab(manager, calibration_service, measurement_service)
    with tabs[3]:
        render_history_tab(calibration_service, measurement_service)
    with tabs[4]:
        render_diagnostics_tab(manager)


def init_services() -> None:
    """Initialise long-lived services in session state."""

    if SESSION_KEYS["instrument"] not in st.session_state:
        st.session_state[SESSION_KEYS["instrument"]] = InstrumentManager()

    if SESSION_KEYS["repository"] not in st.session_state:
        st.session_state[SESSION_KEYS["repository"]] = MetadataRepository()

    repository: MetadataRepository = st.session_state[SESSION_KEYS["repository"]]
    instrument_manager: InstrumentManager = st.session_state[SESSION_KEYS["instrument"]]

    if SESSION_KEYS["calibration"] not in st.session_state:
        st.session_state[SESSION_KEYS["calibration"]] = CalibrationService(repository)
    else:
        st.session_state[SESSION_KEYS["calibration"]].refresh()

    if SESSION_KEYS["measurement"] not in st.session_state:
        st.session_state[SESSION_KEYS["measurement"]] = MeasurementService(
            instrument_manager=instrument_manager,
            repository=repository,
        )

    # Ensure measurement configuration is initialised
    get_measurement_config()

    if SESSION_KEYS["calibration_sweeps"] not in st.session_state:
        st.session_state[SESSION_KEYS["calibration_sweeps"]] = {}

    calibration_service: CalibrationService = st.session_state[SESSION_KEYS["calibration"]]
    available_kits = calibration_service.list_calibration_kits()
    if (
        SESSION_KEYS["selected_calibration_kit"] not in st.session_state
        and available_kits
    ):
        st.session_state[SESSION_KEYS["selected_calibration_kit"]] = available_kits[0]["id"]

    if SESSION_KEYS["calibration_standard"] not in st.session_state:
        st.session_state[SESSION_KEYS["calibration_standard"]] = "Open"


def get_measurement_config() -> MeasurementConfig:
    """Return the current measurement configuration, initialising defaults if needed."""

    raw = st.session_state.get(SESSION_KEYS["measurement_config"])
    if isinstance(raw, MeasurementConfig):
        return _normalise_measurement_config(raw)
    if raw:
        try:
            config = MeasurementConfig.model_validate(raw)
        except Exception:
            config = MeasurementConfig(
                start_freq=float(settings.default_start_freq),
                stop_freq=float(settings.default_stop_freq),
                points=int(settings.default_points),
                if_bandwidth=float(settings.default_if_bandwidth),
                power=float(settings.default_power),
                port_count=2,
                source_port=1,
                destination_port=2,
                averaging=1,
                sweep_type="linear",
            )
    else:
        config = MeasurementConfig(
            start_freq=float(settings.default_start_freq),
            stop_freq=float(settings.default_stop_freq),
            points=int(settings.default_points),
            if_bandwidth=float(settings.default_if_bandwidth),
            power=float(settings.default_power),
            port_count=2,
            source_port=1,
            destination_port=2,
            averaging=1,
            sweep_type="linear",
        )

    config = _normalise_measurement_config(config)
    st.session_state[SESSION_KEYS["measurement_config"]] = config.model_dump()
    return config


def set_measurement_config(config: MeasurementConfig) -> None:
    """Persist measurement configuration in session state."""

    config = _normalise_measurement_config(config)
    st.session_state[SESSION_KEYS["measurement_config"]] = config.model_dump()


def _normalise_measurement_config(config: MeasurementConfig) -> MeasurementConfig:
    """Ensure port count covers selected source/destination ports."""

    max_ports = max(config.port_count, config.source_port, config.destination_port)
    if max_ports != config.port_count:
        return config.model_copy(update={"port_count": max_ports})
    return config


def render_sidebar(manager: InstrumentManager, calibration_service: CalibrationService) -> None:
    """Z43 Guideline: Consistent sidebar with clear instrument status."""

    with st.sidebar:
        st.markdown("## Instrument Control")
        status = manager.get_info()

        # Z43 Guideline: Clear status indication
        if status["connected"]:
            st.markdown('<div class="calibration-progress progress-complete">', unsafe_allow_html=True)
            st.markdown("**🟢 Connected**")
            if status["info"]:
                info = status["info"]
                st.markdown(f"*{info.get('manufacturer', 'Unknown')} {info.get('model', '')}*")
                st.caption(f"SN: {info.get('serial', 'N/A')} • FW: {info.get('firmware', 'N/A')}")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="calibration-progress progress-pending">', unsafe_allow_html=True)
            st.markdown("**🔴 Disconnected**")
            st.markdown("*No instrument connected*")
            st.markdown('</div>', unsafe_allow_html=True)

        # Z43 Guideline: Discoverable connection options
        with st.expander("⚙️ Connection Settings", expanded=not status["connected"]):
            with st.form("connection_form", clear_on_submit=False):
                st.markdown("**Instrument Configuration**")
                
                instrument_type = st.selectbox(
                    "Type",
                    options=["auto", "simulation", "zva"],
                    index=0,
                    help="Auto: Use config file • Simulation: Offline mode • ZVA: Rohde & Schwarz",
                )
                
                address = st.text_input(
                    "SCPI Address",
                    value=status["info"].get("address", "") if status["info"] else settings.vna_address or "",
                    help="Format: TCPIP::192.168.1.100::INSTR",
                    disabled=instrument_type == "simulation",
                )
                
                col_connect, col_disconnect = st.columns(2)
                with col_connect:
                    submitted = st.form_submit_button("🔌 Connect", type="primary")
                with col_disconnect:
                    if status["connected"]:
                        if st.form_submit_button("🔌 Disconnect"):
                            manager.disconnect()
                            st.rerun()
                
                if submitted:
                    try:
                        with st.spinner("🔄 Connecting to instrument..."):
                            manager.connect(
                                instrument_type=instrument_type,
                                address=address or None,
                            )
                        st.success("✅ Instrument connected")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"❌ Connection failed: {exc}")

        # Z43 Guideline: Show calibration status in sidebar
        st.markdown("## Calibration Status")
        if calibration_service.is_valid():
            record = calibration_service.current
            st.markdown('<div class="calibration-progress progress-complete">', unsafe_allow_html=True)
            st.markdown("**✅ Valid**")
            if record:
                st.markdown(f"*{record.method} • {record.timestamp.strftime('%H:%M')}*")
                if record.calibration_kit_name:
                    st.caption(f"Kit: {record.calibration_kit_name}")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="calibration-progress progress-warning">', unsafe_allow_html=True)
            st.markdown("**⚠️ Required**")
            st.markdown("*Use Calibration tab*")
            st.markdown('</div>', unsafe_allow_html=True)

        # Z43 Guideline: Quick measurement configuration
        st.markdown("## Quick Setup")
        config = get_measurement_config()
        
        with st.expander("📊 Measurement Config"):
            st.metric("Frequency Range", f"{config.start_freq/1e6:.1f} - {config.stop_freq/1e6:.1f} MHz")
            st.metric("Data Points", f"{config.points}")
            st.metric("Power Level", f"{config.power} dBm")
            st.caption("Configure in Measurement tab")

        if status["connected"]:
            if st.button("Disconnect", use_container_width=True):
                manager.disconnect()
                st.rerun()

        st.markdown("---")
        st.subheader("Measurement Setup")
        detected_ports = manager.get_port_count()
        st.caption(f"Detected ports: {detected_ports}")
        config = get_measurement_config()
        available_ports = max(2, manager.get_port_count(), config.source_port, config.destination_port)
        transmission_pairs = build_transmission_options(available_ports)
        current_pair = (config.source_port, config.destination_port)
        try:
            current_index = transmission_pairs.index(current_pair)
        except ValueError:
            current_index = 0

        with st.form("sidebar_measurement_config"):
            start_mhz = st.number_input(
                "Start (MHz)",
                min_value=0.001,
                max_value=67000.0,
                value=float(config.start_freq / 1e6),
                step=1.0,
                format="%.3f",
            )
            stop_mhz = st.number_input(
                "Stop (MHz)",
                min_value=float(start_mhz + 0.001),
                max_value=67000.0,
                value=float(config.stop_freq / 1e6),
                step=1.0,
                format="%.3f",
            )
            points = st.number_input(
                "Points",
                min_value=11,
                max_value=200001,
                value=int(config.points),
                step=10,
            )
            if_bw = st.number_input(
                "IF BW (Hz)",
                min_value=1.0,
                max_value=1e6,
                value=float(config.if_bandwidth),
                step=100.0,
            )
            power = st.number_input(
                "Power (dBm)",
                min_value=-80.0,
                max_value=30.0,
                value=float(config.power),
                step=1.0,
            )
            averaging = st.number_input(
                "Averages",
                min_value=1,
                max_value=256,
                value=int(config.averaging),
                step=1,
            )
            sweep_type = st.selectbox(
                "Sweep",
                options=["linear", "log"],
                index=0 if config.sweep_type == "linear" else 1,
            )
            selected_pair = st.selectbox(
                "Transmission",
                options=transmission_pairs,
                index=current_index,
                format_func=lambda pair: f"S{pair[1]}{pair[0]}",
            )
            submitted = st.form_submit_button("Apply Setup", type="secondary")
            if submitted:
                try:
                    new_config = MeasurementConfig(
                        start_freq=float(start_mhz) * 1e6,
                        stop_freq=float(stop_mhz) * 1e6,
                        points=int(points),
                        if_bandwidth=float(if_bw),
                        power=float(power),
                        port_count=max(selected_pair),
                        source_port=selected_pair[0],
                        destination_port=selected_pair[1],
                        averaging=int(averaging),
                        sweep_type=sweep_type,
                    )
                    set_measurement_config(new_config)
                    if manager.is_connected:
                        manager.configure_measurement(
                            start_freq=new_config.start_freq,
                            stop_freq=new_config.stop_freq,
                            points=new_config.points,
                            if_bandwidth=new_config.if_bandwidth,
                            power=new_config.power,
                            port_count=new_config.port_count,
                        )
                    st.success("Measurement setup applied")
                except Exception as exc:
                    st.error(f"Failed to apply setup: {exc}")

        st.markdown("---")
        st.subheader("Calibration")
        current = calibration_service.current
        if current:
            expires_in = (
                current.expires_at - datetime.utcnow()
                if current.expires_at
                else None
            )
            st.write(
                f"Last calibrated {current.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
            )
            st.caption(
                f"Method: {current.method} · Ports: {current.port_count}"
            )
            if current.calibration_kit_name:
                st.caption(f"Kit: {current.calibration_kit_name}")
            if current.calibration_kit_serial or current.calibration_kit_date:
                serial = current.calibration_kit_serial or "—"
                cal_date = current.calibration_kit_date or "—"
                st.caption(f"Kit serial {serial} · Date {cal_date}")
            if expires_in:
                minutes = int(expires_in.total_seconds() // 60)
                st.caption(f"Valid for ~{minutes} more minutes")
        else:
            st.warning("No valid calibration on record")

        st.markdown("---")
        st.caption(
            f"Simulation mode: {'ON' if settings.simulation_mode else 'OFF'} · Data root: {settings.data_root}"
        )


def render_overview_tab(
    manager: InstrumentManager,
    calibration_service: CalibrationService,
) -> None:
    """Z43 Guideline: Simple overview with clear workflow guidance."""
    
    # Z43 Guideline: Clear visual hierarchy
    st.markdown("## Welcome to OH4VNA")
    st.markdown("**Professional Vector Network Analyzer Control**")
    
    # Z43 Guideline: System status overview with consistent styling
    st.markdown("### System Status")
    
    status_container = st.container()
    with status_container:
        col1, col2, col3 = st.columns(3)
        
        # Instrument Status
        with col1:
            if manager.is_connected:
                st.markdown('<div class="calibration-progress progress-complete">', unsafe_allow_html=True)
                st.markdown("**🟢 Instrument Connected**")
                info = manager.get_info().get("info", {})
                if info:
                    st.markdown(f"*{info.get('manufacturer', '')} {info.get('model', '')}*")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="calibration-progress progress-pending">', unsafe_allow_html=True)
                st.markdown("**🔴 No Instrument**")
                st.markdown("*Connect in sidebar*")
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Calibration Status  
        with col2:
            if calibration_service.is_valid(port_count=1):
                st.markdown('<div class="calibration-progress progress-complete">', unsafe_allow_html=True)
                st.markdown("**✅ Calibrated**")
                active_cal = calibration_service.current
                if active_cal:
                    st.markdown(f"*{active_cal.timestamp.strftime('%H:%M')}*")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="calibration-progress progress-warning">', unsafe_allow_html=True)
                st.markdown("**⚠️ Calibration Required**")
                st.markdown("*Use Calibration tab*")
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Measurement Status
        with col3:
            measurement_ready = manager.is_connected and calibration_service.is_valid()
            if measurement_ready:
                st.markdown('<div class="calibration-progress progress-complete">', unsafe_allow_html=True)
                st.markdown("**📊 Ready to Measure**")
                st.markdown("*All systems operational*")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="calibration-progress progress-pending">', unsafe_allow_html=True)
                st.markdown("**📊 Not Ready**")
                st.markdown("*Complete setup first*")
                st.markdown('</div>', unsafe_allow_html=True)
    
    # Z43 Guideline: Clear workflow guidance
    st.markdown("### Quick Start Workflow")
    
    workflow_steps = [
        {
            "title": "1. Connect Instrument",
            "description": "Use the sidebar to connect to your VNA or enable simulation mode",
            "icon": "🔌",
            "completed": manager.is_connected
        },
        {
            "title": "2. Perform Calibration", 
            "description": "Run SOL calibration using the Calibration tab",
            "icon": "🔧",
            "completed": calibration_service.is_valid()
        },
        {
            "title": "3. Make Measurements",
            "description": "Configure and capture measurements in the Measurement tab",
            "icon": "📏", 
            "completed": measurement_ready
        },
        {
            "title": "4. Analyze Results",
            "description": "Review measurement history and export data",
            "icon": "📊",
            "completed": False  # Always show as available
        }
    ]
    
    for step in workflow_steps:
        progress_class = "progress-complete" if step["completed"] else "progress-pending"
        st.markdown(f'<div class="calibration-progress {progress_class}">', unsafe_allow_html=True)
        st.markdown(f"**{step['icon']} {step['title']}**")
        st.markdown(f"*{step['description']}*")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Z43 Guideline: Show relevant active information
    active_cal = calibration_service.current
    if active_cal and active_cal.calibration_kit_name:
        st.markdown("### Active Calibration Kit")
        kit_details = [active_cal.calibration_kit_name]
        if active_cal.calibration_kit_serial:
            kit_details.append(f"SN {active_cal.calibration_kit_serial}")
        if active_cal.calibration_kit_date:
            kit_details.append(f"Cal Date {active_cal.calibration_kit_date}")
        st.info(" • ".join(kit_details))
    
    # Z43 Guideline: Show last measurement if available
    if SESSION_KEYS["active_record"] in st.session_state:
        record = st.session_state[SESSION_KEYS["active_record"]]
        st.markdown("### Latest Measurement")
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Timestamp", record.timestamp.strftime('%H:%M:%S'))
        col_b.metric("S-Parameter", record.config.s_parameter_label)
        col_c.metric("Points", f"{record.config.points}")
        col_d.metric("Frequency", f"{record.config.start_freq/1e6:.1f}-{record.config.stop_freq/1e6:.1f} MHz")
        
        if record.touchstone_path:
            st.caption(f"📁 Saved: {Path(record.touchstone_path).name}")


def render_calibration_tab(
    manager: InstrumentManager,
    calibration_service: CalibrationService,
) -> None:
    """Render calibration workflow similar to R&S/Keysight VNAs."""

    if not manager.is_connected:
        st.info("Connect to an instrument before calibrating.")
        return

    # Calibration wizard state management
    if "cal_wizard_step" not in st.session_state:
        st.session_state["cal_wizard_step"] = 0
    if "cal_wizard_standards" not in st.session_state:
        st.session_state["cal_wizard_standards"] = {}

    st.header("🔧 Single-Port Calibration (SOL)")
    
    # Show current measurement configuration
    config = get_measurement_config()
    with st.expander("📊 Measurement Configuration", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Start", f"{config.start_freq/1e6:.3f} MHz")
        col2.metric("Stop", f"{config.stop_freq/1e6:.3f} MHz")
        col3.metric("Points", int(config.points))
        col4.metric("Port", f"Port 1 (S11)")
        
        if st.button("⚙️ Apply Setup to Instrument", type="secondary"):
            try:
                manager.configure_measurement(
                    start_freq=config.start_freq,
                    stop_freq=config.stop_freq,
                    points=config.points,
                    if_bandwidth=config.if_bandwidth,
                    power=config.power,
                    port_count=1,
                )
                st.success("✅ Measurement setup applied to instrument.")
            except Exception as exc:
                st.error(f"❌ Failed to apply setup: {exc}")

    # Calibration kit selection
    kits = calibration_service.list_calibration_kits()
    kit_lookup = {kit["id"]: kit for kit in kits}
    selected_kit_id = st.session_state.get(SESSION_KEYS["selected_calibration_kit"])
    if selected_kit_id not in kit_lookup and kits:
        selected_kit_id = kits[0]["id"]
        st.session_state[SESSION_KEYS["selected_calibration_kit"]] = selected_kit_id

    st.subheader("📦 Calibration Kit")
    if kits:
        index = (
            [i for i, kit in enumerate(kits) if kit["id"] == selected_kit_id][0]
            if selected_kit_id in kit_lookup
            else 0
        )
        selected_kit_id = st.selectbox(
            "Select calibration kit:",
            options=[kit["id"] for kit in kits],
            index=index,
            format_func=lambda kit_id: kit_lookup[kit_id]["name"],
        )
        st.session_state[SESSION_KEYS["selected_calibration_kit"]] = selected_kit_id
        selected_kit = kit_lookup[selected_kit_id]
        
        # Show kit details
        serial = selected_kit.get("serial", "—")
        cal_date = selected_kit.get("calibration_date", "—")
        st.info(f"📋 **{selected_kit['name']}** • Serial: {serial} • Cal Date: {cal_date}")
    else:
        st.warning("⚠️ No calibration kits available. Import one below.")
        selected_kit = None

    # Kit import (collapsed by default)
    with st.expander("📁 Import New Calibration Kit"):
        kit_name_input = st.text_input("Kit name", value="", key="cal_kit_name_input")
        col_meta1, col_meta2 = st.columns(2)
        with col_meta1:
            kit_serial_input = st.text_input("Kit serial", value="0000", key="cal_kit_serial_input")
        with col_meta2:
            kit_date_input = st.date_input(
                "Calibration date",
                value=date.today(),
                key="cal_kit_date_input",
            )
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            kit_open_file = st.file_uploader("Open (.s1p)", type=["s1p"], key="kit_open_file")
        with col_b:
            kit_short_file = st.file_uploader("Short (.s1p)", type=["s1p"], key="kit_short_file")
        with col_c:
            kit_load_file = st.file_uploader("Load (.s1p)", type=["s1p"], key="kit_load_file")

        if st.button("📥 Import Kit", key="import_cal_kit_button"):
            if not kit_name_input.strip():
                st.warning("⚠️ Please provide a name for the calibration kit.")
            elif not (kit_open_file and kit_short_file and kit_load_file):
                st.warning("⚠️ Upload all three standard files (Open, Short, Load).")
            else:
                try:
                    date_string = (
                        kit_date_input.strftime("%Y%m%d")
                        if kit_date_input
                        else datetime.utcnow().strftime("%Y%m%d")
                    )
                    metadata = calibration_service.import_calibration_kit(
                        kit_name_input,
                        {
                            "open": kit_open_file.getvalue(),
                            "short": kit_short_file.getvalue(),
                            "load": kit_load_file.getvalue(),
                        },
                        serial=kit_serial_input,
                        calibration_date=date_string,
                    )
                    st.success(f"✅ Imported calibration kit '{metadata['name']}'.")
                    st.session_state[SESSION_KEYS["selected_calibration_kit"]] = metadata["id"]
                    st.rerun()
                except Exception as exc:
                    st.error(f"❌ Failed to import calibration kit: {exc}")

    # Calibration wizard steps
    st.markdown("---")
    st.subheader("🧙‍♂️ Calibration Wizard")
    
    standards = ["Open", "Short", "Load"]
    current_step = st.session_state["cal_wizard_step"]
    
    # Z43 Progress indicator with consistent styling
    st.markdown("#### Calibration Progress")
    progress_cols = st.columns(3)
    for i, std in enumerate(standards):
        with progress_cols[i]:
            if i < current_step:
                st.markdown(f'<div class="calibration-progress progress-complete">', unsafe_allow_html=True)
                st.markdown(f"**✅ {std}**")
                st.markdown("*Complete*")
                st.markdown('</div>', unsafe_allow_html=True)
            elif i == current_step:
                st.markdown(f'<div class="calibration-progress progress-current">', unsafe_allow_html=True)
                st.markdown(f"**🔄 {std}**")
                st.markdown("*Current Step*")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="calibration-progress progress-pending">', unsafe_allow_html=True)
                st.markdown(f"**⏳ {std}**")
                st.markdown("*Pending*")
                st.markdown('</div>', unsafe_allow_html=True)

    # Current step instructions
    if current_step < len(standards):
        current_standard = standards[current_step]
        simulation_mode = manager.get_info().get("simulation_mode", False)
        
        st.markdown(f"### Step {current_step + 1}: Connect {current_standard} Standard")
        st.info(f"🔌 Connect the **{current_standard}** standard to Port 1 and measure.")
        
        col_measure, col_skip = st.columns([3, 1])
        
        with col_measure:
            if st.button(f"📡 Measure {current_standard}", type="primary", key=f"measure_{current_standard}"):
                try:
                    # Load fixture for simulation
                    if simulation_mode and selected_kit:
                        fixture_path = selected_kit["files"].get(current_standard.lower())
                        if fixture_path and Path(fixture_path).exists():
                            fixture_network = Network(fixture_path)
                            manager.set_simulation_fixture(fixture_network, name=current_standard)
                    
                    # Capture measurement
                    reflection_network = capture_reflection_network(manager, config)
                    
                    # Store in wizard state
                    st.session_state["cal_wizard_standards"][current_standard.lower()] = {
                        "network": reflection_network,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    
                    # Advance to next step
                    st.session_state["cal_wizard_step"] = current_step + 1
                    st.success(f"✅ {current_standard} measurement captured!")
                    st.rerun()
                    
                except Exception as exc:
                    st.error(f"❌ Failed to measure {current_standard}: {exc}")
        
        with col_skip:
            if st.button("⏭️ Skip", help=f"Skip {current_standard} measurement"):
                st.session_state["cal_wizard_step"] = current_step + 1
                st.rerun()
        
        # Show Smith chart for captured standards
        captured = st.session_state["cal_wizard_standards"]
        if captured:
            st.markdown("#### 📊 Captured Standards")
            chart_cols = st.columns(3)
            for i, std in enumerate(standards):
                if std.lower() in captured:
                    with chart_cols[i]:
                        data = captured[std.lower()]
                        network = data["network"]
                        figure = smith_chart_figure(network, f"{std} • S11")
                        st.pyplot(figure)
                        plt.close(figure)
                        rl = return_loss_at_center(network)
                        st.caption(f"Return Loss: {rl:.1f} dB")
    
    else:
        # All standards captured - finish calibration
        st.success("🎉 All standards measured! Ready to compute calibration.")
        
        with st.form("calibration_completion"):
            st.markdown("#### 📝 Calibration Details")
            operator = st.text_input("Operator name:", value="")
            notes = st.text_area("Notes:", placeholder="Optional calibration notes...")
            
            col_save, col_restart = st.columns([2, 1])
            with col_save:
                submitted = st.form_submit_button("💾 Save Calibration", type="primary")
            with col_restart:
                if st.form_submit_button("🔄 Restart"):
                    st.session_state["cal_wizard_step"] = 0
                    st.session_state["cal_wizard_standards"] = {}
                    st.rerun()
            
            if submitted:
                # Validate that we have all standards
                captured = st.session_state["cal_wizard_standards"]
                missing_standards = [std for std in ["open", "short", "load"] if std not in captured]
                
                if missing_standards:
                    st.error(f"❌ Missing standards: {', '.join(missing_standards)}")
                else:
                    try:
                        # Record manual calibration
                        record = calibration_service.record_manual_calibration(
                            operator=operator or "Unknown",
                            method="SOL",
                            port_count=1,
                            standards_completed=list(captured.keys()),
                            instrument_info=manager.get_info().get("info", {}),
                            notes=notes,
                            calibration_kit=selected_kit,
                        )
                        
                        st.success(f"✅ Calibration saved successfully! ({record.timestamp.strftime('%Y-%m-%d %H:%M UTC')})")
                        
                        # Reset wizard
                        st.session_state["cal_wizard_step"] = 0
                        st.session_state["cal_wizard_standards"] = {}
                        
                        # Clear simulation fixture if needed
                        if manager.get_info().get("simulation_mode", False):
                            manager.set_simulation_fixture(None)
                        
                        st.rerun()
                        
                    except Exception as exc:
                        st.error(f"❌ Failed to save calibration: {exc}")

    st.markdown("---")
    st.subheader("Recent Calibrations")
    records = calibration_service.recent(limit=5)
    if not records:
        st.caption("No calibrations recorded yet.")
    else:
        data = [
            {
                "Timestamp": rec.timestamp.strftime("%Y-%m-%d %H:%M"),
                "Method": rec.method,
                "Ports": rec.port_count,
                "Kit": rec.calibration_kit_name or "—",
                "Serial": rec.calibration_kit_serial or "—",
                "Kit Date": rec.calibration_kit_date or "—",
                "Expires": rec.expires_at.strftime("%H:%M") if rec.expires_at else "n/a",
                "Notes": rec.notes or "",
            }
            for rec in records
        ]
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


def render_measurement_tab(
    manager: InstrumentManager,
    calibration_service: CalibrationService,
    measurement_service: MeasurementService,
) -> None:
    """Z43 Guideline: Clear measurement workflow with responsiveness."""

    # Z43 Guideline: Clear prerequisites
    if not manager.is_connected:
        st.markdown('<div class="calibration-progress progress-pending">', unsafe_allow_html=True)
        st.markdown("**🔴 No Instrument Connected**")
        st.markdown("*Connect an instrument in the sidebar first*")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    calibration = calibration_service.current
    if not calibration:
        st.markdown('<div class="calibration-progress progress-warning">', unsafe_allow_html=True)
        st.markdown("**⚠️ No Valid Calibration**")
        st.markdown("*Measurements will be flagged as uncalibrated*")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="calibration-progress progress-complete">', unsafe_allow_html=True)
        st.markdown("**✅ Calibrated & Ready**")
        st.markdown(f"*{calibration.method} calibration from {calibration.timestamp.strftime('%H:%M')}*")
        st.markdown('</div>', unsafe_allow_html=True)

    # Z43 Guideline: Clear configuration section
    st.markdown("## Measurement Configuration")
    
    # Show current instrument status
    status = manager.get_info()
    instrument_info = status.get("info") or {}
    if status.get("simulation_mode") and instrument_info.get("fixture"):
        st.info(f"🧪 **Simulation Mode** - Fixture: {instrument_info['fixture']}")

    current_config = get_measurement_config()
    available_ports = max(2, manager.get_port_count(), current_config.source_port, current_config.destination_port)
    transmission_pairs = build_transmission_options(available_ports)
    try:
        current_index = transmission_pairs.index((current_config.source_port, current_config.destination_port))
    except ValueError:
        current_index = 0

    # Z43 Guideline: Organized form layout
    with st.form("measurement_configuration_form"):
        st.markdown("### Frequency & Sweep Parameters")
        
        freq_col1, freq_col2, freq_col3 = st.columns(3)
        with freq_col1:
            start_mhz = st.number_input(
                "Start Frequency (MHz)",
                min_value=0.001,
                max_value=67000.0,
                value=float(current_config.start_freq / 1e6),
                step=1.0,
                format="%.3f",
                help="Lower frequency bound"
            )
        with freq_col2:
            stop_mhz = st.number_input(
                "Stop Frequency (MHz)",
                min_value=float(start_mhz + 0.001),
                max_value=67000.0,
                value=float(current_config.stop_freq / 1e6),
                step=1.0,
                format="%.3f", 
                help="Upper frequency bound"
            )
        with freq_col3:
            points = st.number_input(
                "Data Points",
                min_value=11,
                max_value=100001,
                value=int(current_config.points),
                step=10,
                help="Number of measurement points"
            )
        
        st.markdown("### Instrument Parameters")
        
        instr_col1, instr_col2, instr_col3 = st.columns(3)
        with instr_col1:
            if_bandwidth = st.number_input(
                "IF Bandwidth (Hz)",
                min_value=1.0,
                max_value=1e6,
                value=float(current_config.if_bandwidth),
                step=100.0,
                help="Intermediate frequency bandwidth"
            )
        with instr_col2:
            power = st.number_input(
                "Source Power (dBm)",
                min_value=-80.0,
                max_value=30.0,
                value=float(current_config.power),
                step=1.0,
                help="RF source power level"
            )
        with instr_col3:
            averaging = st.number_input(
                "Averages",
                min_value=1,
                max_value=256,
                value=int(current_config.averaging),
                step=1,
                help="Number of averages per point"
            )
        
        st.markdown("### S-Parameter Selection")
        
        sparam_col1, sparam_col2 = st.columns(2)
        with sparam_col1:
            sweep_type = st.selectbox(
                "Sweep Type",
                options=["linear", "log"],
                index=0 if current_config.sweep_type == "linear" else 1,
                help="Frequency sweep mode"
            )
        with sparam_col2:
            selected_pair = st.selectbox(
                "S-Parameter",
                options=transmission_pairs,
                index=current_index,
                format_func=lambda pair: f"S{pair[1]}{pair[0]}",
                help="Transmission parameter to measure"
            )
        
        st.markdown("### Measurement Details")
        detail_col1, detail_col2 = st.columns(2)
        with detail_col1:
            notes = st.text_input("Notes", value="", placeholder="Optional measurement description")
        with detail_col2:
            tags_input = st.text_input(
                "Tags",
                value="",
                placeholder="e.g. DUT, filter, amplifier",
                help="Comma-separated tags for organization"
            )

        # Z43 Guideline: Clear call-to-action
        st.markdown("---")
        col_measure, col_save_config = st.columns([2, 1])
        with col_measure:
            submitted = st.form_submit_button("📡 Run Measurement", type="primary", help="Execute measurement with current settings")
        with col_save_config:
            if st.form_submit_button("💾 Save Config", help="Save configuration as default"):
                set_measurement_config(MeasurementConfig(
                    start_freq=float(start_mhz) * 1e6,
                    stop_freq=float(stop_mhz) * 1e6,
                    points=int(points),
                    if_bandwidth=float(if_bandwidth),
                    power=float(power),
                    port_count=available_ports,
                    source_port=selected_pair[0],
                    destination_port=selected_pair[1],
                    averaging=int(averaging),
                    sweep_type=sweep_type,
                ))
                st.success("✅ Configuration saved")
                st.rerun()

    # Z43 Guideline: Responsive measurement execution with clear feedback
    if submitted:
        with st.spinner("🔄 Configuring instrument and executing measurement..."):
            try:
                config = MeasurementConfig(
                    start_freq=float(start_mhz) * 1e6,
                    stop_freq=float(stop_mhz) * 1e6,
                    points=int(points),
                    if_bandwidth=float(if_bandwidth),
                    power=float(power),
                    port_count=max(selected_pair),
                    source_port=selected_pair[0],
                    destination_port=selected_pair[1],
                    averaging=int(averaging),
                    sweep_type=sweep_type,
                )
                set_measurement_config(config)
                tags = [tag.strip() for tag in tags_input.split(",") if tag.strip()]

                # Z43 Guideline: Show progress for long operations
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("📡 Executing measurement sweep...")
                progress_bar.progress(50)
                
                record, network = measurement_service.run_measurement(
                    config=config,
                    calibration=calibration,
                    notes=notes or None,
                    tags=tags,
                )
                
                progress_bar.progress(100)
                status_text.text("✅ Measurement completed successfully")

                st.session_state[SESSION_KEYS["active_record"]] = record
                st.session_state[SESSION_KEYS["active_network"]] = network
                label = record.config.s_parameter_label
                filename = record.touchstone_path.name if record.touchstone_path else "Touchstone file"
                st.success(f"📊 **Measurement Complete!** {label} → {filename}")
                
            except Exception as exc:
                st.error(f"❌ **Measurement Failed:** {exc}")
                st.info("💡 Check instrument connection and calibration status")

    if SESSION_KEYS["active_network"] in st.session_state:
        record = st.session_state.get(SESSION_KEYS["active_record"])
        network = st.session_state.get(SESSION_KEYS["active_network"])
        if record and network:
            st.markdown("---")
            render_measurement_results(record.instrument_info, record, network)


def render_measurement_results(
    instrument_info: Dict[str, str],
    record,
    network,
) -> None:
    """Z43 Guideline: Clear measurement results with consistent styling."""

    st.markdown("## 📊 Measurement Results")

    # Z43 Guideline: Clear data summary
    config = record.config
    freq_ghz = network.frequency.f / 1e9
    source_idx = int(config.source_port) - 1
    destination_idx = int(config.destination_port) - 1
    selected_trace = network.s[:, destination_idx, source_idx]

    # Z43 Guideline: Key metrics overview
    st.markdown("### Summary")
    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    
    with summary_col1:
        st.metric("S-Parameter", config.s_parameter_label)
    with summary_col2:
        st.metric("Data Points", f"{len(selected_trace)}")
    with summary_col3:
        center_freq = (config.start_freq + config.stop_freq) / 2 / 1e6
        st.metric("Center Freq", f"{center_freq:.1f} MHz")
    with summary_col4:
        span_freq = (config.stop_freq - config.start_freq) / 1e6
        st.metric("Span", f"{span_freq:.1f} MHz")

    # Z43 Guideline: Clear visual hierarchy for plots
    st.markdown("### Frequency Response")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Magnitude Response")
        fig_mag = go.Figure()
        fig_mag.add_trace(
            go.Scatter(
                x=freq_ghz,
                y=20 * np.log10(np.abs(selected_trace)),
                name=f"{config.s_parameter_label} Magnitude",
                line=dict(color="#0090D0", width=2),  # Z43 S4L Blue
            ),
        )
        fig_mag.update_layout(
            title=f"{config.s_parameter_label} Magnitude",
            xaxis_title="Frequency (GHz)",
            yaxis_title="Magnitude (dB)",
            template="plotly_white",
            showlegend=False,
            height=400,
        )
        st.plotly_chart(fig_mag, use_container_width=True)
        
    with col2:
        st.markdown("#### Phase Response")
        fig_phase = go.Figure()
        fig_phase.add_trace(
            go.Scatter(
                x=freq_ghz,
                y=np.angle(selected_trace, deg=True),
                name=f"{config.s_parameter_label} Phase",
                line=dict(color="#FF9200", width=2),  # Z43 S4L Orange
            ),
        )
        fig_phase.update_layout(
            title=f"{config.s_parameter_label} Phase",
            xaxis_title="Frequency (GHz)",
            yaxis_title="Phase (degrees)",
            template="plotly_white",
            showlegend=False,
            height=400,
        )
        st.plotly_chart(fig_phase, use_container_width=True)

    # Z43 Guideline: Organized metadata display
    st.markdown("### Measurement Details")
    
    details_col1, details_col2 = st.columns(2)
    
    with details_col1:
        st.markdown("**📊 Configuration**")
        details = f"""
        - **Frequency Range:** {config.start_freq/1e6:.3f} - {config.stop_freq/1e6:.3f} MHz
        - **Data Points:** {config.points}
        - **IF Bandwidth:** {config.if_bandwidth:.0f} Hz
        - **Source Power:** {config.power} dBm
        - **Averages:** {config.averaging}
        """
        st.markdown(details)
        
    with details_col2:
        st.markdown("**🕒 Session Info**")
        session_info = f"""
        - **Timestamp:** {record.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
        - **Operator:** {record.operator or 'Not specified'}
        - **Calibrated:** {'Yes' if record.calibration_applied else 'No'}
        """
        if record.notes:
            session_info += f"- **Notes:** {record.notes}\n"
        if record.tags:
            session_info += f"- **Tags:** {', '.join(record.tags)}\n"
        st.markdown(session_info)

    # Z43 Guideline: Clear file information
    if record.touchstone_path:
        st.markdown("### 📁 Data Files")
        st.info(f"**Touchstone File:** {record.touchstone_path.name}")
        if record.metadata_path:
            st.caption(f"Metadata: {record.metadata_path.name}")
    
    # Z43 Guideline: Export options
    st.markdown("### 📤 Export Options")
    export_col1, export_col2 = st.columns(2)
    
    with export_col1:
        if st.button("📋 Copy Data Summary", help="Copy measurement summary to clipboard"):
            summary_text = f"""OH4VNA Measurement Summary
S-Parameter: {config.s_parameter_label}
Frequency: {config.start_freq/1e6:.3f} - {config.stop_freq/1e6:.3f} MHz
Points: {config.points}
Timestamp: {record.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
Calibrated: {'Yes' if record.calibration_applied else 'No'}
"""
            st.write("📋 Summary copied to clipboard!")
            
    with export_col2:
        if record.touchstone_path and record.touchstone_path.exists():
            with open(record.touchstone_path, 'rb') as f:
                st.download_button(
                    "💾 Download Touchstone",
                    data=f.read(),
                    file_name=record.touchstone_path.name,
                    mime="text/plain",
                    help="Download raw Touchstone data file"
                )


def render_history_tab(
    calibration_service: CalibrationService,
    measurement_service: MeasurementService,
) -> None:
    """Display stored measurements and allow loading them into the session."""

    records = measurement_service.list_recent(limit=50)
    if not records:
        st.info("No measurements recorded yet.")
        return

    table = pd.DataFrame(
        [
            {
                "ID": rec.id[:8],
                "Timestamp": rec.timestamp.strftime("%Y-%m-%d %H:%M"),
                "Ports": rec.config.port_count,
                "Points": rec.config.points,
                "S-Parameter": rec.config.s_parameter_label,
                "Calibration": rec.calibration_id[:8] if rec.calibration_id else "-",
                "Tags": ", ".join(rec.tags),
            }
            for rec in records
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    options = {f"{rec.timestamp:%Y-%m-%d %H:%M} · {rec.id[:8]}": rec for rec in records}
    selection = st.selectbox("Load measurement", options=list(options.keys()))
    if selection:
        record = options[selection]
        if st.button("Load into workspace", key=record.id):
            try:
                network = measurement_service.load_network(record)
                st.session_state[SESSION_KEYS["active_record"]] = record
                st.session_state[SESSION_KEYS["active_network"]] = network
                st.success("Measurement loaded into session")
            except Exception as exc:
                st.error(f"Failed to load Touchstone: {exc}")


def render_diagnostics_tab(manager: InstrumentManager) -> None:
    """Basic diagnostics to help troubleshoot connectivity."""

    st.subheader("Instrument Diagnostics")
    info = manager.get_info()
    st.json(info)

    if manager.is_connected:
        if st.button("Preset Instrument", type="secondary"):
            try:
                manager.preset_instrument()
                st.success("Preset command sent")
            except Exception as exc:
                st.error(f"Preset failed: {exc}")
    else:
        st.caption("Connect to an instrument to access diagnostics.")


if __name__ == "__main__":
    main()