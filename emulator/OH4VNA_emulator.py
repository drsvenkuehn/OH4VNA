
"""
OH4VNA_emulator.py

Assumptions:
 - Coupler port mapping:
     Port 1 = Input
     Port 2 = Output
     Port 3 = Coupled
     Port 4 = Isolated
 - Uses a real coupler touchstone file if supplied (path COUPLER_S4P)
"""
import numpy as np
import skrf as rf
import matplotlib.pyplot as plt
import pandas as pd

# ---------- USER CONFIG ----------

USE_CALIBRATION = True   # Set to True to enable OSL calibration
path_coupler = "Sprams MACP-011045_corrected\MACP-011045_02_corrected.s4p"
amp_gain_db = 20
dl_loss_db = -30
#ideal_coupler
fstart = 5e6      
fstop = 1500e6    
coupling_db = 23 
mydut = 6   # Select DUT example (1 to 6)

# ------DUT Examples----------
df = pd.read_csv("dut_gamma_arrays.csv")
match mydut:
    case 1:
        # DUT 1 — Mild reflection (|Γ| = 0.5, phase = –60° × 2)
        theta_rad = np.deg2rad(60)
        gamma_dut = 0.5 * np.exp(-1j * 2 * theta_rad)
    case 2:
        #DUT 2 — Strong reflection, inverted (|Γ| = 0.9, phase = +45° × 2)
        theta_rad = np.deg2rad(45)
        gamma_dut = -0.9 * np.exp(-1j * 2 * theta_rad)
    case 3: 
        #DUT 3 — Low reflection (|Γ| = 0.2, phase = 120° × 2)
        theta_rad = np.deg2rad(120)
        gamma_dut = 0.2 * np.exp(-1j * 2 * theta_rad)
    case 4:
        #DUT 4 — mild-dispersion DUT
        gamma_dut = df["gammaA_real"].values + 1j * df["gammaA_imag"].values
    case 5:
        #DUT 5 — strong phase-rotation DUT
        gamma_dut = df["gammaB_real"].values + 1j * df["gammaB_imag"].values
    case 6:
        #DUT 6 — weak reflection with long delay
        gamma_dut = df["gammaC_real"].values + 1j * df["gammaC_imag"].values
    case _:
        raise ValueError("Invalid \"mydut\" value. Must be 1 to 6.")


# ---------- Definition Loading ----------
def create_link(frequency, gain_db, name="Link"):
    """
    Creates a unilateral 2-port network
    """
    ntwk = rf.Network(frequency=frequency, name=name)
    
    mag = 10**(gain_db / 20.0)
    s_matrix = np.zeros((len(frequency), 2, 2), dtype=complex)
    s_matrix[:, 1, 0] = mag  # S21 (Port 1 -> Port 2)
    
    ntwk.s = s_matrix
    return ntwk

def load_coupler(filename):
    try:
        # try loading the real coupler file
        coupler = rf.Network(filename)
        print("Loaded coupler file:", filename)
        return coupler

    except Exception as e:
        print("Could not load coupler file:", filename)
        print("Reason:", e)
        print("→ Using IDEAL coupler instead.")

        # Create an ideal 4-port coupler with specified coupling
        freq = rf.Frequency(fstart, fstop, 300, 'MHz')
        N = len(freq)
        s = np.zeros((N, 4, 4), dtype=complex)

        C = 10 ** (-coupling_db/20) 
        D = 10 ** (-30/20)   # directivity

        # Ports: 0 = input  1 = through   2 = coupled    3 = isolated

        for i in range(N):
            s[i] = np.array([
                [0,     1,     C,     D],
                [1,     0,     D,     C],
                [C,     D,     0,     1],
                [D,     C,     1,     0]
            ])

        ideal = rf.Network(frequency=freq, s=s, name="ideal_coupler")
        return ideal

def create_ideal_1port(freq, reflection_coeff, name):
    if np.isscalar(reflection_coeff):
        gamma = np.full(len(freq), reflection_coeff, dtype=complex)
    else:
        gamma = np.asarray(reflection_coeff)

    # 1-port only
    s = gamma[:, None, None]   # (N,1,1)
    return rf.Network(frequency=freq, s=s, z0=50, name=name)

def measure_dut(freq, dut):

    # External ports (VNA ports)
    P0 = rf.Circuit.Port(freq, z0=50, name="P0")   #  port 1
    P1 = rf.Circuit.Port(freq, z0=50, name="P1")   #  port 2

    # Termination for ISO port
    termination = rf.Network(
        frequency=freq,
        s=np.zeros((len(freq), 1, 1), dtype=complex),
        z0=50,
        name="IsoMatch"
    )

    # Build circuit
    circuit = rf.Circuit([
        [(P0, 0),          (downlink_net, 0)],   # VNA→Downlink
        [(downlink_net, 1),(coupler_net, 0)],    # Downlink→Coupler IN
        [(coupler_net, 1), (dut, 0)],            # Coupler THRU → DUT
        [(coupler_net, 2), (uplink_net, 0)],     # Coupler COUPLED → Uplink
        [(uplink_net, 1),  (P1, 0)],             # Uplink → VNA Port 2
        [(coupler_net, 3), (termination, 0)]     # ISO → matched load
    ])

    # Result is a 2-port network
    res = circuit.network

    # Extract VNA S21 (P1←P0)
    meas = rf.Network(frequency=freq, name=f"Meas_{dut.name}")
    meas.s = res.s[:, 1, 0][:, None, None]

    return meas

# ---------- Main ----------
if __name__ == "__main__":

    coupler_net = load_coupler(path_coupler)
    freq = coupler_net.frequency
    print(len(freq), "frequency points loaded.")

    downlink_net = create_link(freq, gain_db=dl_loss_db, name="Downlink")
    uplink_net = create_link(freq, gain_db=amp_gain_db, name="Uplink")
    S_open = np.ones((len(freq),1,1), dtype=complex)
    C_open = rf.Network(frequency=freq, s=S_open, name="Open")
    S_short = -np.ones((len(freq),1,1), dtype=complex)
    C_short = rf.Network(frequency=freq, s=S_short, name="Short")
    S_load = np.zeros((len(freq),1,1), dtype=complex)
    C_load = rf.Network(frequency=freq, s=S_load, name="Load")
    dut_antenna = create_ideal_1port(freq, gamma_dut, "DUT_Antenna")

    print("--- Simulating Measurements ---")

    meas_open  = measure_dut(freq,C_open)
    meas_short = measure_dut(freq,C_short)
    meas_load  = measure_dut(freq,C_load)
    meas_dut   = measure_dut(freq,dut_antenna)
    
    print("Measurements Complete.")
    
    #Perform Calibration

    if USE_CALIBRATION:
        print("Running OSL calibration...")
        cal = rf.OnePort(
            ideals=[C_open, C_short, C_load],
            measured=[meas_open, meas_short, meas_load],
            name="Optical_System_Cal"
        )
        cal.run()

        dut_corrected = cal.apply_cal(meas_dut)
        dut_corrected.name = "Calibrated_Antenna"
    else:
        print("Calibration DISABLED → using raw measurement.")
        dut_corrected = meas_dut.copy()
        dut_corrected.name = "Uncalibrated_Antenna"

    print("Calibration Complete.")
    

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Plot 1: Raw System Response (Magnitude)
    # Note: The total loop gain/loss is approx. -30dB (Downlink) - 23dB (Coupling) + 20dB (Uplink) = -33dB
    ax1.set_title("Raw Receiver Signal (Coupled S21)")
    meas_open.plot_s_db(ax=ax1, label="Meas Open")
    meas_short.plot_s_db(ax=ax1, label="Meas Short")
    meas_load.plot_s_db(ax=ax1, label="Meas Load")
    meas_dut.plot_s_db(ax=ax1, label="Meas DUT")
    ax1.grid(True)
    
    # Plot 2: Calibrated DUT vs Ideal
    ax2.set_title("Calibrated DUT S11 (Smith Chart)")
    dut_corrected.plot_s_smith(m=0, n=0, ax=ax2, label='Calibrated', marker='o', markersize=4, linestyle='None')
    dut_antenna.plot_s_smith(m=0, n=0, ax=ax2, label='Ideal', marker='x', markersize=6, linestyle='None')    
    ax2.grid(True)
    
    plt.tight_layout()
    plt.show()

