#!/usr/bin/env python3
"""
gf180mcu_inductor_diag_loop.py -- follow-up diagnostic to
gf180mcu_inductor_diag_bar.py and gf180mcu_substrate_spreading_check.py:
tests whether an IN-PLANE (planar) port, bridging a small gap cut directly
into a closed Metal5 loop, gives a physically sane extracted resistance --
with NO vertical contact to the substrate anywhere in the structure.

--------------------------------------------------------------------------
WHY THIS STRUCTURE
--------------------------------------------------------------------------
diag_bar.py's ports dropped vertically through the oxide to the substrate
surface at each end, using the (moderately lossy, 10 ohm*cm) substrate as
the return-current path -- standalone modeling confirmed
(substrate_spreading_check.py) that two ~1um x 1um point contacts into
that substrate create ~30-40 kOhm of ordinary spreading/constriction
resistance on their own, fully explaining the ~25,000x-58,000x extracted-R
bug seen in every earlier fix attempt. That's not an FDTD/CSXCAD bug --
it's the WRONG port topology for what we actually want to measure, and
it's also not how the real center-tapped differential VCO tank inductor
this project is building toward will be excited: its center tap goes to
VCC (AC ground), never to the substrate directly, and the two differential
terminals are excited in-plane, in series with the winding metal itself.

This script tests the minimal version of that idea: a single closed
rectangular Metal5 loop (no differential/center-tap complexity yet -- see
the project's openems_inductor_status.md for that queued next step), with
ONE small gap cut into it, bridged by a single in-line LumpedPort (current
flows along the metal's own length, direction='x', not vertically). The
port's box sits entirely within the metal layer's own z-range -- it never
touches oxide-bottom or substrate at all. Current has nowhere to go but
around the loop through more metal, so Y11 = I/V at DC should read the
loop's real sheet-resistance-derived resistance (order 1-10 ohm), not a
substrate-contact artifact.

--------------------------------------------------------------------------
HOW TO RUN
--------------------------------------------------------------------------
Same container/invocation pattern as gf180mcu_inductor_diag_bar.py (see
its docstring for the docker run -d + docker exec gotcha with this image).
--structure-only builds the geometry/mesh and dumps diagnostic plots
without running FDTD (seconds). Drop it to run the full sweep.
--------------------------------------------------------------------------
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

WIDTH_UM = 1.0                # loop trace width, same as diag_bar's bar
X_OUT_UM = 20.0                # outer half-extent in x
Y_OUT_UM = 5.0                 # outer half-extent in y
PORT_GAP_UM = 0.5              # gap cut into the top arm for the port
SHEET_R_OHM_PER_SQ = 0.040     # GF180MCU Metal5, tt corner
THICKNESS_M = 1.1925e-6
Z_OX_TOP_UM = 5.76             # unchanged from diag_bar.py -- still real GF180MCU stack height

X_IN_UM = X_OUT_UM - WIDTH_UM
Y_IN_UM = Y_OUT_UM - WIDTH_UM


def build_structure(f_max_hz, end_criteria):
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    unit = 1e-6
    sigma = 1.0 / (SHEET_R_OHM_PER_SQ * THICKNESS_M)
    z_ox_top = Z_OX_TOP_UM
    z_m5_top = z_ox_top + THICKNESS_M / unit
    half_gap = PORT_GAP_UM / 2

    FDTD = openEMS(EndCriteria=end_criteria)
    FDTD.SetGaussExcite(f_max_hz / 2, f_max_hz / 2)
    FDTD.SetBoundaryCond(["PML_8"] * 6)

    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(unit)

    res = 0.4
    box = X_OUT_UM + 10
    mesh.AddLine("x", [-X_OUT_UM, -X_IN_UM, -half_gap, half_gap, X_IN_UM, X_OUT_UM, -box, box])
    mesh.AddLine("y", [-Y_OUT_UM, -Y_IN_UM, Y_IN_UM, Y_OUT_UM, -box, box])
    mesh.SmoothMeshLines("x", res, ratio=1.4)
    mesh.SmoothMeshLines("y", res, ratio=1.4)

    sub_thick = 40.0
    mesh.AddLine("z", [-sub_thick, 0, z_ox_top, z_m5_top, z_m5_top + 40])
    mesh.SmoothMeshLines("z", THICKNESS_M / unit / 2, ratio=1.4)

    substrate_sigma = 1.0 / (10.0 * 1e-2)
    substrate = CSX.AddMaterial("substrate", epsilon=11.9, kappa=substrate_sigma)
    substrate.AddBox([-box, -box, -sub_thick], [box, box, 0])
    oxide = CSX.AddMaterial("oxide", epsilon=3.9)
    oxide.AddBox([-box, -box, 0], [box, box, z_ox_top])

    # Closed rectangular Metal5 loop (a "picture frame") -- top arm split
    # in two around the port gap, the other three sides solid. Every box
    # lives entirely in z=[z_ox_top, z_m5_top]; nothing here ever reaches
    # z_ox_top's lower face or the substrate.
    metal5 = CSX.AddMaterial("metal5", kappa=sigma)
    metal5.AddBox([-X_OUT_UM, Y_IN_UM, z_ox_top], [-half_gap, Y_OUT_UM, z_m5_top])   # top-left of gap
    metal5.AddBox([half_gap, Y_IN_UM, z_ox_top], [X_OUT_UM, Y_OUT_UM, z_m5_top])     # top-right of gap
    metal5.AddBox([-X_OUT_UM, -Y_OUT_UM, z_ox_top], [X_OUT_UM, -Y_IN_UM, z_m5_top])  # bottom arm
    metal5.AddBox([-X_OUT_UM, -Y_OUT_UM, z_ox_top], [-X_IN_UM, Y_OUT_UM, z_m5_top])  # left arm
    metal5.AddBox([X_IN_UM, -Y_OUT_UM, z_ox_top], [X_OUT_UM, Y_OUT_UM, z_m5_top])    # right arm

    # In-line planar port: bridges the gap cut into the top arm, current
    # flows along x (the trace's own direction) -- NOT vertically. Both
    # of the port's caps land on real metal (the two arm halves either
    # side of the gap), so the loop it closes is entirely within the
    # metal itself; the substrate below is just passive lossy background,
    # never a forced current path.
    excite_v_per_m = 10.0 / (PORT_GAP_UM * unit)
    port = FDTD.AddLumpedPort(
        1, 50, [-half_gap, Y_IN_UM, z_ox_top], [half_gap, Y_OUT_UM, z_m5_top], "x", excite=excite_v_per_m)

    centerline_len_um = 2 * (2 * X_OUT_UM - WIDTH_UM - PORT_GAP_UM) + 2 * (2 * Y_OUT_UM - WIDTH_UM)
    # rough perimeter at the ring's mid-width centerline, minus the port gap; ignores the
    # well-known ~0.56-square correction for sharp right-angle corners -- an approximate
    # sanity-check reference, same spirit as diag_bar.py's expected_R, not a precise formula.
    geom_info = {
        "z_ox_top": z_ox_top, "z_m5_top": z_m5_top, "box": box, "sub_thick": sub_thick,
        "expected_R": SHEET_R_OHM_PER_SQ * centerline_len_um / WIDTH_UM,
        "sigma": sigma,
    }
    return FDTD, CSX, mesh, port, geom_info


def save_structure_plots(mesh, geom, out_dir):
    import numpy as np

    xs = np.array(mesh.GetLines("x"))
    ys = np.array(mesh.GetLines("y"))

    fig, ax = plt.subplots(figsize=(7, 7))
    for (x0, y0, x1, y1) in [
        (-X_OUT_UM, Y_IN_UM, -PORT_GAP_UM / 2, Y_OUT_UM),
        (PORT_GAP_UM / 2, Y_IN_UM, X_OUT_UM, Y_OUT_UM),
        (-X_OUT_UM, -Y_OUT_UM, X_OUT_UM, -Y_IN_UM),
        (-X_OUT_UM, -Y_OUT_UM, -X_IN_UM, Y_OUT_UM),
        (X_IN_UM, -Y_OUT_UM, X_OUT_UM, Y_OUT_UM),
    ]:
        ax.add_patch(patches.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                        facecolor="goldenrod", edgecolor="darkgoldenrod", alpha=0.8))
    ax.add_patch(patches.Rectangle((-PORT_GAP_UM / 2, Y_IN_UM), PORT_GAP_UM, WIDTH_UM,
                                    facecolor="none", edgecolor="green", linewidth=2, label="port (in-line, x)"))
    for x in xs:
        ax.axvline(x, color="gray", linewidth=0.2, alpha=0.5)
    for y in ys:
        ax.axhline(y, color="gray", linewidth=0.2, alpha=0.5)
    ax.set_xlim(-X_OUT_UM - 3, X_OUT_UM + 3)
    ax.set_ylim(-Y_OUT_UM - 3, Y_OUT_UM + 3)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title("Closed loop, top view (XY), with resolved mesh lines")
    ax.legend(fontsize=8, loc="lower center")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "loop_mesh_xy.png"), dpi=150)
    plt.close(fig)

    # zoomed view right at the port gap -- the thing we actually need to check
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.add_patch(patches.Rectangle((-X_OUT_UM, Y_IN_UM), X_OUT_UM - PORT_GAP_UM / 2, WIDTH_UM,
                                    facecolor="goldenrod", edgecolor="darkgoldenrod", alpha=0.8))
    ax.add_patch(patches.Rectangle((PORT_GAP_UM / 2, Y_IN_UM), X_OUT_UM - PORT_GAP_UM / 2, WIDTH_UM,
                                    facecolor="goldenrod", edgecolor="darkgoldenrod", alpha=0.8))
    ax.add_patch(patches.Rectangle((-PORT_GAP_UM / 2, Y_IN_UM), PORT_GAP_UM, WIDTH_UM,
                                    facecolor="none", edgecolor="green", linewidth=2, hatch="//", label="port box"))
    near = (xs >= -3) & (xs <= 3)
    for x in xs[near]:
        ax.axvline(x, color="gray", linewidth=0.4, alpha=0.6)
    for y in ys[(ys >= Y_IN_UM - 1) & (ys <= Y_OUT_UM + 1)]:
        ax.axhline(y, color="gray", linewidth=0.4, alpha=0.6)
    ax.set_xlim(-3, 3)
    ax.set_ylim(Y_IN_UM - 1, Y_OUT_UM + 1)
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title("Port gap close-up, with mesh lines")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "loop_mesh_port_gap.png"), dpi=150)
    plt.close(fig)

    n_cells = (len(xs) - 1) * (len(ys) - 1)
    print(f"Mesh lines: x={len(xs)} y={len(ys)}  (xy cells ~{n_cells:.3e}, z from diag_bar-style layering)")
    print(f"Structure/mesh diagnostic plots written to {out_dir}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--f-max", type=float, default=40e9)
    p.add_argument("--end-criteria", type=float, default=1e-2)
    p.add_argument("--n-freq", type=int, default=51)
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--structure-only", action="store_true")
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)

    FDTD, CSX, mesh, port, geom = build_structure(args.f_max, args.end_criteria)
    print(f"Approx. expected DC resistance of the loop (centerline length / sheet R, "
          f"no corner correction): {geom['expected_R']:.4f} ohm")
    save_structure_plots(mesh, geom, args.out)

    if args.structure_only:
        return

    import numpy as np
    sim_path = os.path.join(args.out, "openems_sim")
    FDTD.Run(sim_path, cleanup=True, numThreads=args.threads)

    freqs = np.linspace(1e6, args.f_max, args.n_freq)
    port.CalcPort(sim_path, freqs, ref_impedance=50)
    y11 = np.conj(port.if_tot / port.uf_tot)
    re, im = np.real(y11), np.imag(y11)

    lines = [f"Approx. expected DC resistance: {geom['expected_R']:.4f} ohm (no corner correction)",
             "\nf(GHz)  Re(Y11)  1/Re=R_extracted(ohm)  Im(Y11)"]
    for i in range(0, len(freqs), 5):
        lines.append(f"{freqs[i] / 1e9:.3f}  {re[i]:.5e}  {1 / re[i]:.4f}  {im[i]:.5e}")
    lines.append(f"\nExtracted R at lowest freq = {1 / re[0]:.4f} ohm  "
                  f"(ratio to rough expected: {(1 / re[0]) / geom['expected_R']:.2f}x)")
    report = "\n".join(lines)
    print(report, flush=True)
    with open(os.path.join(args.out, "results.txt"), "w") as f:
        f.write(report + "\n")


if __name__ == "__main__":
    main()
