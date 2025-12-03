import numpy as np
import matplotlib.pyplot as plt
import skrf as rf
import os

# ------User's parameters------

N = 4          # Number of ports in the Touchstone file
X = 3          # First port to swap (1-based)
Y = 4          # Second port to swap (1-based)
in_filename = "Sprams MACP-011045\MACP-011045_17.S4P"
out_filename = "Sprams MACP-011045_corrected\MACP-011045_17_corrected.s4p"

#------Functions--------------

def reorder_network_ports(ntwk: rf.Network, new_order: list) -> rf.Network:
    """ Return a copy of `ntwk` with ports reordered according to new_order. """

    # validate
    N = ntwk.nports
    if len(new_order) != N:
        raise ValueError(f"new_order length {len(new_order)} != number of ports {N}")
    if sorted(new_order) != list(range(N)):
        raise ValueError("new_order must be a permutation of 0..N-1 (zero-based indices)")
    
    # copy network
    new_ntwk = ntwk.copy()
    
    # reorder S (shape: nfreq x N x N)
    s = new_ntwk.s  # view to underlying array
    # Use fancy indexing to permute both axes
    s_reordered = s[:, new_order][:, :, new_order]   # first reorder columns, then rows (or vice-versa)
    
    # assign back
    new_ntwk.s = s_reordered
    return new_ntwk

#------Main--------

if __name__ == "__main__":

  ntwk = rf.Network(in_filename)
  print(f"Loaded: {in_filename}  -- ports: {ntwk.nports}, freq points: {len(ntwk.frequency)}")

  new_order = list(range(N))
  new_order[X-1], new_order[Y-1] = new_order[Y-1], new_order[X-1]  # swap X and Y (1-based to 0-based
  corrected = reorder_network_ports(ntwk, new_order)

  # Save corrected file
  corrected.write_touchstone(os.path.splitext(out_filename)[0])
  print(f"Wrote corrected file: {out_filename}")