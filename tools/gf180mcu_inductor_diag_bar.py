#!/usr/bin/env python3
"""
gf180mcu_inductor_diag_bar.py -- fast diagnostic companion to
sch/inductor/inductor_spiral_generator.py: a straight Metal5 bar with a KNOWN
analytic DC resistance, built with the EXACT same port/material/mesh
mechanism as the spiral generator, to isolate whether a Y11-magnitude bug
lives in the shared port/measurement code or in the spiral geometry itself.
A full spiral FDTD run costs 10+ hours; this bar (same mesh density, far
fewer cells) costs minutes, so it's the cheap way to test port/mesh changes.

--------------------------------------------------------------------------
BACKGROUND -- why this script exists
--------------------------------------------------------------------------
Across several fix attempts (port xy-position, the R=1e-6 "short" port
workaround, V/m excitation scaling, and stopping the port's z-range at the
oxide/metal interface instead of spanning through the metal) the extracted
DC resistance stayed ~25,000x-58,000x too high on this bar -- a real,
still-unresolved bug. See gf180mcu_mh_ip__nfrac_pll's project memory
(openems_inductor_status.md) for the full history.

--------------------------------------------------------------------------
--structure-only: inspect before spending hours on another blind fix
--------------------------------------------------------------------------
Building the CSX geometry and mesh (SmoothMeshLines et al.) costs seconds;
only FDTD.Run()'s actual time-stepping is expensive. --structure-only builds
the structure, dumps the resolved mesh lines and a couple of diagnostic
plots (top view + mesh, vertical cross-section through the driven port
showing exactly which layer its z-range touches, and per-axis mesh line
density), and exits WITHOUT running any FDTD -- so the port/mesh geometry
can be checked visually against what's actually intended, in seconds,
instead of guessing blind and waiting hours to find out.

--------------------------------------------------------------------------
HOW TO RUN (inside the eda-env-designer:gf180mcuD container)
--------------------------------------------------------------------------
    docker run --rm --cpus=8 --memory=6g -e OMP_NUM_THREADS=8 \\
        -v /path/to/this/script:/work/sim.py:ro \\
        -v /path/to/output/dir:/work/out \\
        eda-env-designer:gf180mcuD \\
        python3 /work/sim.py --out /work/out --structure-only

Drop --structure-only to also run the (minutes-long, not hours -- this is a
small bar, not a multi-turn spiral) FDTD sweep and extract Y11(f).
--------------------------------------------------------------------------
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

LENGTH_UM = 50.0
WIDTH_UM = 1.0
SHEET_R_OHM_PER_SQ = 0.040   # GF180MCU Metal5, tt corner
THICKNESS_M = 1.1925e-6
Z_OX_TOP_UM = 5.76           # height of Metal5's underside above the substrate


def build_structure(f_max_hz, end_criteria):
    """Builds and returns (FDTD, CSX, mesh, port_a, geom_info). Imports
    CSXCAD/openEMS only here so this stays importable (e.g. for unit
    testing the geometry math) without those packages installed."""
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    unit = 1e-6
    sigma = 1.0 / (SHEET_R_OHM_PER_SQ * THICKNESS_M)
    z_ox_top = Z_OX_TOP_UM
    z_m5_top = z_ox_top + THICKNESS_M / unit
    half_w = WIDTH_UM / 2

    FDTD = openEMS(EndCriteria=end_criteria)
    FDTD.SetGaussExcite(f_max_hz / 2, f_max_hz / 2)
    FDTD.SetBoundaryCond(["PML_8"] * 6)

    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(unit)

    # Ports shifted INWARD by half_w so their entire (x,y) footprint sits on
    # real metal, not straddling the bar's bare endpoint.
    port_a_x = -LENGTH_UM / 2 + half_w
    port_b_x = LENGTH_UM / 2 - half_w

    res = 0.4
    box = LENGTH_UM / 2 + 10
    mesh.AddLine("x", [-LENGTH_UM / 2, port_a_x - half_w, port_a_x + half_w,
                        port_b_x - half_w, port_b_x + half_w, LENGTH_UM / 2, -box, box])
    mesh.AddLine("y", [-half_w, half_w, -box, box])
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

    metal5 = CSX.AddMaterial("metal5", kappa=sigma)
    metal5.AddBox([-LENGTH_UM / 2, -half_w, z_ox_top], [LENGTH_UM / 2, half_w, z_m5_top])

    # Port z-range stops at z_ox_top (the oxide/metal interface), relying on
    # LumpedPort's default caps=True end-cap to contact the metal above,
    # instead of the port's own resistor element occupying the metal's
    # volume (per thliebig/openEMS-Project discussion #162).
    excite_v_per_m = 10.0 / (z_ox_top * unit)
    port_a = FDTD.AddLumpedPort(
        1, 50, [port_a_x - half_w, -half_w, 0], [port_a_x + half_w, half_w, z_ox_top], "z", excite=excite_v_per_m)
    FDTD.AddLumpedPort(
        2, 1e-6, [port_b_x - half_w, -half_w, 0], [port_b_x + half_w, half_w, z_ox_top], "z", excite=0)

    geom_info = {
        "half_w": half_w, "port_a_x": port_a_x, "port_b_x": port_b_x,
        "z_ox_top": z_ox_top, "z_m5_top": z_m5_top, "box": box, "sub_thick": sub_thick,
        "expected_R": LENGTH_UM * unit / (sigma * WIDTH_UM * unit * THICKNESS_M),
        "sigma": sigma,
    }
    return FDTD, CSX, mesh, port_a, geom_info


def save_structure_plots(mesh, geom, out_dir):
    """Dumps the resolved mesh (post-SmoothMeshLines) and the structure it
    was built for -- top view and a vertical cross-section through the
    driven port -- WITHOUT running any FDTD. Cheap (seconds): only the
    time-stepping in FDTD.Run() is expensive, not building the mesh."""
    import numpy as np

    xs = np.array(mesh.GetLines("x"))
    ys = np.array(mesh.GetLines("y"))
    zs = np.array(mesh.GetLines("z"))
    half_w, z_ox_top, z_m5_top = geom["half_w"], geom["z_ox_top"], geom["z_m5_top"]
    port_a_x, port_b_x = geom["port_a_x"], geom["port_b_x"]

    # --- top view (XY): bar + both ports + x/y mesh lines, zoomed near the bar ---
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.add_patch(patches.Rectangle((-LENGTH_UM / 2, -half_w), LENGTH_UM, WIDTH_UM,
                                    facecolor="goldenrod", edgecolor="darkgoldenrod", alpha=0.7, label="metal5 bar"))
    ax.add_patch(patches.Rectangle((port_a_x - half_w, -half_w), 2 * half_w, 2 * half_w,
                                    facecolor="none", edgecolor="green", linewidth=2, label="port a (driven)"))
    ax.add_patch(patches.Rectangle((port_b_x - half_w, -half_w), 2 * half_w, 2 * half_w,
                                    facecolor="none", edgecolor="red", linewidth=2, label="port b (short)"))
    for x in xs:
        ax.axvline(x, color="gray", linewidth=0.3, alpha=0.6)
    for y in ys:
        ax.axhline(y, color="gray", linewidth=0.3, alpha=0.6)
    ax.set_xlim(-LENGTH_UM / 2 - 5, LENGTH_UM / 2 + 5)
    ax.set_ylim(-4, 4)
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title("Top view (XY) with resolved mesh lines")
    ax.legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "mesh_xy.png"), dpi=150)
    plt.close(fig)

    # --- vertical cross-section (XZ) through port a: this is the view that
    # directly shows whether the port's z-range (0..z_ox_top) actually stops
    # short of the metal layer (z_ox_top..z_m5_top) as intended, or overlaps
    # it -- the exact question behind every port-z fix attempt so far. ---
    fig, ax = plt.subplots(figsize=(7, 5))
    x_lo, x_hi = port_a_x - 6, port_a_x + 6
    ax.add_patch(patches.Rectangle((x_lo, -geom["sub_thick"]), x_hi - x_lo, geom["sub_thick"],
                                    facecolor="dimgray", alpha=0.4, label="substrate"))
    ax.add_patch(patches.Rectangle((x_lo, 0), x_hi - x_lo, z_ox_top,
                                    facecolor="lightsteelblue", alpha=0.5, label="oxide"))
    ax.add_patch(patches.Rectangle((-LENGTH_UM / 2, z_ox_top), LENGTH_UM, z_m5_top - z_ox_top,
                                    facecolor="goldenrod", edgecolor="darkgoldenrod", alpha=0.8, label="metal5"))
    ax.add_patch(patches.Rectangle((port_a_x - half_w, 0), 2 * half_w, z_ox_top,
                                    facecolor="none", edgecolor="green", linewidth=2, hatch="//", label="port a box (z=0..z_ox_top)"))
    for x in xs[(xs >= x_lo) & (xs <= x_hi)]:
        ax.axvline(x, color="gray", linewidth=0.3, alpha=0.6)
    for z in zs[(zs >= -5) & (zs <= z_m5_top + 5)]:
        ax.axhline(z, color="gray", linewidth=0.3, alpha=0.6)
    ax.axhline(z_ox_top, color="black", linestyle="--", linewidth=1)
    ax.axhline(z_m5_top, color="black", linestyle="--", linewidth=1)
    ax.text(x_hi, z_ox_top, f" z_ox_top={z_ox_top:.3f}", va="center", fontsize=7)
    ax.text(x_hi, z_m5_top, f" z_m5_top={z_m5_top:.3f}", va="center", fontsize=7)
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(-5, z_m5_top + 5)
    ax.set_xlabel("x (um)")
    ax.set_ylabel("z (um)")
    ax.set_title("Vertical cross-section through port a (y=0), with mesh lines")
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "mesh_xz_port_a.png"), dpi=150)
    plt.close(fig)

    # --- per-axis mesh line density: flags near-coincident lines, which
    # force the FDTD's CFL-limited timestep down regardless of how coarse
    # every other line's spacing is (the likely cause of the recurring
    # "the timestep seems to be very small" warning in the run logs). ---
    fig, axes = plt.subplots(3, 1, figsize=(9, 5), sharex=False)
    for ax, name, lines in zip(axes, ["x", "y", "z"], [xs, ys, zs]):
        ax.plot(lines, np.zeros_like(lines), "|", markersize=20, color="tab:blue")
        min_gap = float(np.min(np.diff(np.sort(lines))))
        ax.set_title(f"{name}: {len(lines)} lines, min spacing = {min_gap:.5f} um", fontsize=9)
        ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "mesh_line_density.png"), dpi=150)
    plt.close(fig)

    n_cells = (len(xs) - 1) * (len(ys) - 1) * (len(zs) - 1)
    summary = (
        f"Mesh lines: x={len(xs)} y={len(ys)} z={len(zs)}  (~{n_cells:.3e} cells)\n"
        f"Min spacing: x={np.min(np.diff(np.sort(xs))):.5f}  y={np.min(np.diff(np.sort(ys))):.5f}  "
        f"z={np.min(np.diff(np.sort(zs))):.5f}  (um)\n"
    )
    with open(os.path.join(out_dir, "structure_summary.txt"), "w") as f:
        f.write(summary)
    print(summary)
    print(f"Structure/mesh diagnostic plots written to {out_dir}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, help="Output directory for plots and (unless --structure-only) openEMS working files")
    p.add_argument("--f-max", type=float, default=40e9, help="Highest frequency of interest, Hz (default 40 GHz)")
    p.add_argument("--end-criteria", type=float, default=1e-2, help="openEMS EndCriteria -- 1e-2 (magnitude sanity check) by default, not 1e-4 (precision)")
    p.add_argument("--n-freq", type=int, default=51)
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--structure-only", action="store_true", help="Build the structure/mesh, dump diagnostic plots, and exit -- skip the FDTD run entirely")
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)

    FDTD, CSX, mesh, port_a, geom = build_structure(args.f_max, args.end_criteria)
    print(f"Expected DC resistance of the bar: {geom['expected_R']:.4f} ohm (sigma={geom['sigma']:.4e} S/m)")
    save_structure_plots(mesh, geom, args.out)

    if args.structure_only:
        return

    import numpy as np
    sim_path = os.path.join(args.out, "openems_sim")
    FDTD.Run(sim_path, cleanup=True, numThreads=args.threads)

    freqs = np.linspace(1e6, args.f_max, args.n_freq)
    port_a.CalcPort(sim_path, freqs, ref_impedance=50)
    # Conjugated: openEMS's DFT uses the opposite time convention from the
    # exp(-jwt) circuit-theory convention Q/SRF formulas assume elsewhere in
    # this project -- see sch/inductor/inductor_spiral_generator.py.
    y11 = np.conj(port_a.if_tot / port_a.uf_tot)
    re, im = np.real(y11), np.imag(y11)

    lines = [f"Expected DC resistance of the bar: {geom['expected_R']:.4f} ohm (sigma={geom['sigma']:.4e} S/m)",
             "\nf(GHz)  Re(Y11)  1/Re=R_extracted(ohm)  Im(Y11)"]
    for i in range(0, len(freqs), 5):
        lines.append(f"{freqs[i] / 1e9:.3f}  {re[i]:.5e}  {1 / re[i]:.4f}  {im[i]:.5e}")
    lines.append(f"\nExpected R = {geom['expected_R']:.4f} ohm")
    lines.append(f"Extracted R at lowest freq = {1 / re[0]:.4f} ohm  (ratio to expected: {(1 / re[0]) / geom['expected_R']:.2f}x)")
    report = "\n".join(lines)
    print(report, flush=True)
    with open(os.path.join(args.out, "results.txt"), "w") as f:
        f.write(report + "\n")


if __name__ == "__main__":
    main()
