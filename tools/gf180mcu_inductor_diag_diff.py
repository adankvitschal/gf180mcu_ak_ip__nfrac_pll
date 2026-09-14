#!/usr/bin/env python3
"""
gf180mcu_inductor_diag_diff.py -- Step 2 of the planar-port validation ladder
(after gf180mcu_inductor_diag_loop.py confirmed a single planar port on a
closed loop gives a physically sane R, 3.9949 ohm extracted vs. 3.8 ohm
hand-estimate). This tests the actual TARGET topology: a differential,
center-tapped winding -- two coupled half-windings (a 'hairpin': two
parallel arms joined by a U-turn), with the center tap (CT) coming off the
U-turn's midpoint, held near a local reference (R=1e-6, undriven -- 'tied
to VCC/AC ground'), and the two open ends (A, B) driven differentially
(excite = +V / -V in the SAME run -- odd-mode excitation, matching exactly
how tb/inductor/tb_yparam_diff.sch already does it in SPICE: drive a/b
differentially, tie ct to GND).

All THREE ports are planar/in-line (direction 'x', bridging a gap or an
open trace end) -- none touch the substrate. The two arms run parallel and
close together specifically so they share real magnetic flux (mutual
inductance) under differential drive, same physical mechanism a real
center-tapped VCO tank inductor relies on.

Y_diff = I_A / (V_A - V_B), mirroring tb_yparam_diff.py's Ydiff =
i(vab)/(v(vin_p)-v(vin_n)) so the eventual EM vs. SPICE-placeholder
comparison is apples-to-apples.

Same --structure-only / container invocation pattern as
gf180mcu_inductor_diag_bar.py and gf180mcu_inductor_diag_loop.py.
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

WIDTH_UM = 1.0
ARM_LEN_UM = 20.0          # each arm spans x=[-ARM_LEN_UM, 0]
Y_IN_UM = 4.0               # arm_top y=[Y_IN,Y_OUT], arm_bottom y=[-Y_OUT,-Y_IN]
Y_OUT_UM = 5.0
TURN_X0_UM = 0.0            # U-turn connector x=[TURN_X0,TURN_X1]
TURN_X1_UM = 1.0
TAP_LEN_UM = 1.0            # CT stub extends from the turn's midpoint to x=TURN_X1+TAP_LEN --
# shortened from 4.0: a matched-vs-unmatched R (1e-6 vs 50) made NO difference to the persistent
# high-Q ringing (confirmed: identical global energy trace both times, even though the CT port's
# own local current data did differ) -- the real fix is removing the resonant cavity itself, not
# guessing its unknown characteristic impedance. A much shorter stub pushes any standing-wave
# resonance far higher in frequency (less within/near our swept band, less efficiently excited by
# the Gaussian pulse), closer to how the real layout will look anyway (tap exits close to the
# junction via a crossunder, not a long dangling arm).
PORT_GAP_UM = 0.5           # port box size at each of the 3 terminals
SHEET_R_OHM_PER_SQ = 0.040
THICKNESS_M = 1.1925e-6
Z_OX_TOP_UM = 5.76


def build_structure(f_max_hz, end_criteria):
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

    a_x0, a_x1 = -ARM_LEN_UM, -ARM_LEN_UM + PORT_GAP_UM   # port A box
    b_x0, b_x1 = -ARM_LEN_UM, -ARM_LEN_UM + PORT_GAP_UM   # port B box (same x-range, other arm)
    tap_x1 = TURN_X1_UM + TAP_LEN_UM
    ct_x0, ct_x1 = tap_x1 - PORT_GAP_UM, tap_x1            # port CT box, at the stub's open tip

    res = 0.4
    box = ARM_LEN_UM + 10
    mesh.AddLine("x", [a_x1, TURN_X0_UM, TURN_X1_UM, ct_x0, ct_x1, -box, box])
    mesh.AddLine("y", [-Y_OUT_UM, -Y_IN_UM, -half_w, half_w, Y_IN_UM, Y_OUT_UM, -box, box])
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

    # Two parallel arms (real mutual coupling under differential drive) +
    # a U-turn connecting them + a perpendicular tap stub off the turn's
    # midpoint. Every box lives in z=[z_ox_top, z_m5_top] only -- nothing
    # here ever touches the substrate.
    # Every junction OVERLAPS its neighbor by a small margin (not just
    # touching at a shared face) -- touching-only boundaries risk not
    # actually connecting in the Yee-grid discretization (confirmed the
    # hard way: the first version of this script, with exactly-touching
    # boxes at x=0/x=TURN_X1, gave ~1e-15 A currents -- 11 orders of
    # magnitude too small, with the arms essentially floating, only
    # weakly capacitively coupled to the turn). Same safe pattern
    # gf180mcu_inductor_diag_loop.py already used successfully.
    ov = 0.2
    metal5 = CSX.AddMaterial("metal5", kappa=sigma)
    metal5.AddBox([a_x1, Y_IN_UM, z_ox_top], [ov, Y_OUT_UM, z_m5_top])                       # arm_top (A side)
    metal5.AddBox([b_x1, -Y_OUT_UM, z_ox_top], [ov, -Y_IN_UM, z_m5_top])                     # arm_bottom (B side)
    metal5.AddBox([TURN_X0_UM - ov, -Y_OUT_UM, z_ox_top], [TURN_X1_UM, Y_OUT_UM, z_m5_top])  # U-turn
    metal5.AddBox([TURN_X1_UM - ov, -half_w, z_ox_top], [ct_x0, half_w, z_m5_top])           # CT tap stub

    # Port A, B: open trace ends (nothing beyond a_x0/b_x0) -- same pattern
    # as a dipole/monopole antenna feed: LumpedPort's caps=True gives each
    # its own end-cap even with metal on only the inward side. Driven
    # differentially (+V / -V) in the SAME run = odd-mode excitation.
    excite_v_per_m = 10.0 / (PORT_GAP_UM * unit)
    port_a = FDTD.AddLumpedPort(
        1, 50, [a_x0, Y_IN_UM, z_ox_top], [a_x1, Y_OUT_UM, z_m5_top], "x", excite=excite_v_per_m)
    port_b = FDTD.AddLumpedPort(
        2, 50, [b_x0, -Y_OUT_UM, z_ox_top], [b_x1, -Y_IN_UM, z_m5_top], "x", excite=-excite_v_per_m)
    # Port CT: open stub tip, R=50 (matched, same as A/B) -- NOT a near-
    # short. R=1e-6 here (first attempt) turned this stub into an almost
    # ideal shorted-stub resonator: energy rang up and down across at
    # least 4 cycles over ~1h50m, each peak HIGHER than the last (1.2e-9
    # -> 5.6e-9 -> 2.0e-6 -> still climbing when stopped), never settling
    # -- a real, reproducible high-Q parasitic resonance, not convergence
    # noise. R=1e-6 never actually grounded CT to anything external
    # anyway (it only shorts the stub to ITSELF -- there's no separate
    # conductor on its far side to short TO, unlike port b's original
    # role in diag_bar.py, which shorted metal to a genuinely separate
    # substrate conductor). A matched 50-ohm termination damps the stub
    # instead of letting it ring, and shouldn't materially change Y_diff
    # since negligible current should reach CT under ideal odd-mode drive.
    FDTD.AddLumpedPort(
        3, 50, [ct_x0, -half_w, z_ox_top], [ct_x1, half_w, z_m5_top], "x", excite=0)

    path_len_um = 2 * (a_x1 - a_x0 + (0 - a_x1)) + (Y_OUT_UM - (-Y_OUT_UM))
    # rough A-to-B metal path length (through both arms + across the turn), no corner
    # correction -- same approximate-reference spirit as diag_loop.py's expected_R.
    geom_info = {
        "z_ox_top": z_ox_top, "z_m5_top": z_m5_top, "box": box, "sub_thick": sub_thick,
        "expected_R_diff": SHEET_R_OHM_PER_SQ * path_len_um / WIDTH_UM,
        "sigma": sigma, "a_x0": a_x0, "a_x1": a_x1, "b_x0": b_x0, "b_x1": b_x1,
        "ct_x0": ct_x0, "ct_x1": ct_x1,
    }
    return FDTD, CSX, mesh, port_a, port_b, geom_info


def save_structure_plots(mesh, geom, out_dir):
    import numpy as np

    xs = np.array(mesh.GetLines("x"))
    ys = np.array(mesh.GetLines("y"))
    half_w = WIDTH_UM / 2

    fig, ax = plt.subplots(figsize=(8, 6))
    for (x0, y0, x1, y1) in [
        (geom["a_x1"], Y_IN_UM, 0, Y_OUT_UM),
        (geom["b_x1"], -Y_OUT_UM, 0, -Y_IN_UM),
        (TURN_X0_UM, -Y_OUT_UM, TURN_X1_UM, Y_OUT_UM),
        (TURN_X1_UM, -half_w, geom["ct_x0"], half_w),
    ]:
        ax.add_patch(patches.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                        facecolor="goldenrod", edgecolor="darkgoldenrod", alpha=0.8))
    for (x0, y0, x1, y1), color, label in [
        ((geom["a_x0"], Y_IN_UM, geom["a_x1"], Y_OUT_UM), "green", "port A (+V)"),
        ((geom["b_x0"], -Y_OUT_UM, geom["b_x1"], -Y_IN_UM), "blue", "port B (-V)"),
        ((geom["ct_x0"], -half_w, geom["ct_x1"], half_w), "red", "port CT (R=50, matched)"),
    ]:
        ax.add_patch(patches.Rectangle((x0, y0), x1 - x0, y1 - y0,
                                        facecolor="none", edgecolor=color, linewidth=2, label=label))
    for x in xs:
        ax.axvline(x, color="gray", linewidth=0.2, alpha=0.5)
    for y in ys:
        ax.axhline(y, color="gray", linewidth=0.2, alpha=0.5)
    ax.set_xlim(geom["a_x0"] - 2, geom["ct_x1"] + 2)
    ax.set_ylim(-Y_OUT_UM - 2, Y_OUT_UM + 2)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title("Differential hairpin + center tap, top view (XY), with mesh")
    ax.legend(fontsize=8, loc="lower center", ncol=3)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "diff_mesh_xy.png"), dpi=150)
    plt.close(fig)

    # Vertical cross-sections (XZ) through each port -- shows the actual
    # stack (substrate/oxide/metal5) and confirms each port's box sits
    # entirely within the metal layer's own z-range (z_ox_top..z_m5_top),
    # never dipping into oxide or touching the substrate below -- same
    # style as gf180mcu_inductor_diag_bar.py's mesh_xz_port_a.png, but all
    # 3 ports here are in-line/planar, not vertical vias, so the port box
    # should appear as a thin vertical strip fully inside the metal band.
    zs = np.array(mesh.GetLines("z"))
    z_ox_top, z_m5_top, sub_thick = geom["z_ox_top"], geom["z_m5_top"], geom["sub_thick"]

    def save_xz_cross_section(x_lo, x_hi, port_x0, port_x1, port_label, port_color, fname):
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.add_patch(patches.Rectangle((x_lo, -sub_thick), x_hi - x_lo, sub_thick,
                                        facecolor="dimgray", alpha=0.4, label="substrate"))
        ax.add_patch(patches.Rectangle((x_lo, 0), x_hi - x_lo, z_ox_top,
                                        facecolor="lightsteelblue", alpha=0.5, label="oxide"))
        ax.add_patch(patches.Rectangle((x_lo, z_ox_top), x_hi - x_lo, z_m5_top - z_ox_top,
                                        facecolor="goldenrod", edgecolor="darkgoldenrod", alpha=0.8, label="metal5"))
        ax.add_patch(patches.Rectangle((port_x0, z_ox_top), port_x1 - port_x0, z_m5_top - z_ox_top,
                                        facecolor="none", edgecolor=port_color, linewidth=2, hatch="//",
                                        label=f"{port_label} box (in-line, full metal thickness)"))
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
        ax.set_title(f"Vertical cross-section through {port_label}, with mesh lines")
        ax.legend(fontsize=7, loc="upper left")
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, fname), dpi=150)
        plt.close(fig)

    save_xz_cross_section(geom["a_x0"] - 3, geom["a_x0"] + 6, geom["a_x0"], geom["a_x1"],
                           "port A", "green", "diff_mesh_xz_port_a.png")
    save_xz_cross_section(geom["b_x0"] - 3, geom["b_x0"] + 6, geom["b_x0"], geom["b_x1"],
                           "port B", "blue", "diff_mesh_xz_port_b.png")
    save_xz_cross_section(geom["ct_x0"] - 6, geom["ct_x1"] + 3, geom["ct_x0"], geom["ct_x1"],
                           "port CT", "red", "diff_mesh_xz_port_ct.png")

    n_cells = (len(xs) - 1) * (len(ys) - 1)
    print(f"Mesh lines: x={len(xs)} y={len(ys)} (xy cells ~{n_cells:.3e})")
    print(f"Structure/mesh diagnostic plots written to {out_dir}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True)
    p.add_argument("--f-max", type=float, default=40e9)
    p.add_argument("--end-criteria", type=float, default=1e-4)  # -40dB, not -20dB: the first
    # attempt's energy curve had a non-monotonic double-hump (partial decay, a NEW higher
    # peak, then final decay) and stopped right after barely crossing -20dB -- tighter margin
    # to be safe, even though the actual bug turned out to be geometry connectivity, not this.
    p.add_argument("--n-freq", type=int, default=51)
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--structure-only", action="store_true")
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)

    FDTD, CSX, mesh, port_a, port_b, geom = build_structure(args.f_max, args.end_criteria)
    print(f"Approx. expected differential DC resistance (A-to-B path / sheet R, "
          f"no corner correction): {geom['expected_R_diff']:.4f} ohm")
    save_structure_plots(mesh, geom, args.out)

    if args.structure_only:
        return

    import numpy as np
    sim_path = os.path.join(args.out, "openems_sim")
    FDTD.Run(sim_path, cleanup=True, numThreads=args.threads)

    freqs = np.linspace(1e6, args.f_max, args.n_freq)
    port_a.CalcPort(sim_path, freqs, ref_impedance=50)
    port_b.CalcPort(sim_path, freqs, ref_impedance=50)
    y_diff = np.conj(port_a.if_tot / (port_a.uf_tot - port_b.uf_tot))
    re, im = np.real(y_diff), np.imag(y_diff)

    lines = [f"Approx. expected differential DC resistance: {geom['expected_R_diff']:.4f} ohm (no corner correction)",
             "\nf(GHz)  Re(Ydiff)  1/Re=Rdiff_extracted(ohm)  Im(Ydiff)"]
    for i in range(0, len(freqs), 5):
        lines.append(f"{freqs[i] / 1e9:.3f}  {re[i]:.5e}  {1 / re[i]:.4f}  {im[i]:.5e}")
    lines.append(f"\nExtracted Rdiff at lowest freq = {1 / re[0]:.4f} ohm  "
                  f"(ratio to rough expected: {(1 / re[0]) / geom['expected_R_diff']:.2f}x)")
    report = "\n".join(lines)
    print(report, flush=True)
    with open(os.path.join(args.out, "results.txt"), "w") as f:
        f.write(report + "\n")


if __name__ == "__main__":
    main()
