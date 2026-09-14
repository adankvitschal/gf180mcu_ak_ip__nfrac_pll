"""Standalone (no CSXCAD/openEMS/scipy needed) DC finite-difference check:
does the resistance between two small contacts dropped into the resistive
GF180MCU substrate -- the exact topology diag_bar.py's two LumpedPorts use
to reach ground -- explain the ~25,000x-58,000x extracted-resistance bug by
itself, via ordinary spreading/constriction resistance into a moderately
lossy substrate? This is a pure electrostatics (Laplace) problem, solved
with vectorized-numpy Jacobi relaxation -- no FDTD, no openEMS, runs in
seconds/minutes on the host.

Geometry mirrors diag_bar.py's substrate exactly: two 1um x 1um contacts on
the top surface of a rho=0.1 ohm*m (10 ohm*cm) substrate slab, 40um thick,
domain +-35um laterally, separated by 49um center-to-center (matching the
bar's port_a_x=-24.5, port_b_x=+24.5). All outer faces insulating (PML in
the real FDTD run isn't a DC ground -- it just absorbs outgoing waves, so
for a DC/near-DC current-spreading picture the domain is effectively an
isolated resistive block with no other ground path, same as here).
Exploits y-mirror symmetry (contacts and domain are both symmetric about
y=0) to halve the grid.
"""
import time
import numpy as np

RHO_OHM_M = 0.1          # 10 ohm*cm, from diag_bar.py's substrate_sigma
CONTACT_HALF_UM = 0.5    # half_w in diag_bar.py (1um x 1um contact)
GAP_HALF_UM = 24.5        # port_a_x magnitude in diag_bar.py
BOX_UM = 35.0             # diag_bar.py's box = length/2 + 10
SUB_THICK_UM = 40.0       # diag_bar.py's sub_thick


def solve(cell_um, max_iter=40000, tol=1e-7, verbose=True):
    nx = int(round(2 * BOX_UM / cell_um))
    ny = int(round(BOX_UM / cell_um))       # half domain (mirror at y=0)
    nz = int(round(SUB_THICK_UM / cell_um))  # index 0 = top (z=0 surface), increasing = deeper

    x = (np.arange(nx) + 0.5) * cell_um - BOX_UM
    y = (np.arange(ny) + 0.5) * cell_um

    V = np.zeros((nx, ny, nz))

    contact_a_x = np.abs(x - (-GAP_HALF_UM)) <= CONTACT_HALF_UM
    contact_b_x = np.abs(x - (GAP_HALF_UM)) <= CONTACT_HALF_UM
    y_in_contact = y <= CONTACT_HALF_UM

    maskA = np.zeros((nx, ny), dtype=bool)
    maskA[contact_a_x, :] = y_in_contact
    maskB = np.zeros((nx, ny), dtype=bool)
    maskB[contact_b_x, :] = y_in_contact

    V[maskA, 0] = 1.0
    V[maskB, 0] = 0.0
    fixed = np.zeros_like(V, dtype=bool)
    fixed[maskA, 0] = True
    fixed[maskB, 0] = True

    t0 = time.time()
    for it in range(max_iter):
        Vp = np.pad(V, 1, mode="edge")  # 'edge' padding == zero-flux (insulating) on ALL 6 faces,
        # including the y=0 mirror boundary (ghost = own value => zero gradient, i.e. mirror symmetry)
        lap = (Vp[2:, 1:-1, 1:-1] + Vp[:-2, 1:-1, 1:-1] +
               Vp[1:-1, 2:, 1:-1] + Vp[1:-1, :-2, 1:-1] +
               Vp[1:-1, 1:-1, 2:] + Vp[1:-1, 1:-1, :-2]) / 6.0
        lap[fixed] = V[fixed]
        diff = np.max(np.abs(lap - V))
        V = lap
        if verbose and it % 2000 == 0:
            print(f"  cell={cell_um}um it={it} max|dV|={diff:.3e} ({time.time()-t0:.1f}s)", flush=True)
        if diff < tol:
            break

    # Total current out of contact A: sum conductance*(V_center - V_neighbor) across
    # ALL 6 faces of every contact-A cell (lateral leakage into the top surface
    # counts too, not just the straight-down direction) -- contact-to-contact
    # faces contribute zero automatically (equal V there).
    dx_m = cell_um * 1e-6
    sigma = 1.0 / RHO_OHM_M
    g = sigma * dx_m  # sigma*Area/Length = sigma*dx^2/dx = sigma*dx for a cubic cell

    Vp = np.pad(V, 1, mode="edge")
    flux = (
        (V - Vp[2:, 1:-1, 1:-1]) + (V - Vp[:-2, 1:-1, 1:-1]) +
        (V - Vp[1:-1, 2:, 1:-1]) + (V - Vp[1:-1, :-2, 1:-1]) +
        (V - Vp[1:-1, 1:-1, 2:]) + (V - Vp[1:-1, 1:-1, :-2])
    ) * g
    I_half = float(np.sum(flux[maskA, 0]))
    I_full = 2 * I_half  # mirror domain -> double for the real full-y geometry
    R = 1.0 / I_full
    n_cells = nx * ny * nz
    print(f"cell={cell_um}um: grid={nx}x{ny}(half)x{nz}={n_cells} cells, "
          f"{it+1} iterations, {time.time()-t0:.1f}s -> R = {R:.1f} ohm")
    return R


if __name__ == "__main__":
    print(f"Analytic single-contact estimate (rho/(4a), a=equiv. circular radius of "
          f"a {2*CONTACT_HALF_UM}x{2*CONTACT_HALF_UM}um square contact, infinite half-space):")
    a_m = (2 * CONTACT_HALF_UM * 1e-6) / np.sqrt(np.pi)
    r_single = RHO_OHM_M / (4 * a_m)
    print(f"  R_single_contact = {r_single:.1f} ohm  ->  R_two_contacts (series, far apart) ~ {2*r_single:.1f} ohm\n")

    for cell_um in (1.0, 0.5):
        solve(cell_um)
