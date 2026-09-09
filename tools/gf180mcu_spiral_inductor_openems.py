#!/usr/bin/env python3
"""
gf180mcu_spiral_inductor_openems.py -- a self-contained, didactic example of
driving openEMS (a real 3D FDTD electromagnetic field solver) to characterize
a GF180MCU planar octagonal-spiral inductor from geometry parameters alone.

No external project/package is required -- everything (the GF180MCU Metal5
stack constants, the geometry generator, the openEMS structure builder) lives
in this one file, so it can be read top to bottom and shared as a teaching
example. It only needs a Python environment with CSXCAD + openEMS's Python
bindings + numpy + matplotlib importable, e.g. the eda-env-designer:gf180mcuD
Docker image (see "HOW TO RUN" below).

--------------------------------------------------------------------------
WHAT THIS ACTUALLY SIMULATES
--------------------------------------------------------------------------
A single-turn-per-layer octagonal spiral trace on GF180MCU's Metal5 (the
thick top metal), suspended over its real oxide stack and a lossy silicon
substrate. One end ('a', the inner terminus) is driven with a 1V-equivalent
AC lumped port; the other end ('b', the outer terminus) is grounded straight
down to the substrate through a plain zero-resistance short. This is a
one-port measurement: openEMS extracts the driving-point admittance
Y11(f) = I(f)/V(f) at port 'a' across a frequency sweep, from which:

    Q(f)  = -Im(Y11) / Re(Y11)      (positive for an inductive one-port)
    SRF   = the frequency where Im(Y11) crosses from negative (inductive)
            to positive (capacitive) -- above SRF the structure no longer
            behaves as an inductor at all.

This mirrors exactly how you'd characterize a real spiral inductor on a
network analyzer: drive one port, ground the other, read back Y11(f).

--------------------------------------------------------------------------
WHY OPENEMS (AND NOT A CLOSED-FORM FORMULA) -- AND WHAT IT COSTS
--------------------------------------------------------------------------
Closed-form inductor models (Modified Wheeler, Mohan's monomial fit, the
Yue & Wong pi-model) are fast but are curve fits to OTHER people's
measurements on OTHER processes -- they don't know GF180MCU's real Metal5
sheet resistance, its real oxide thickness, or its real substrate loss.
openEMS instead solves Maxwell's equations directly on the actual 3D
geometry and the actual (as-measured-from-the-PDK, see the STACK dict
below) material stack, at the cost of a MUCH longer runtime: a full
resonance-decay run for a modest few-turn coil at up to 20 GHz bandwidth
has been observed taking on the order of ten-plus hours of wall-clock time
on an 8-core machine (1-2 million+ FDTD timesteps, most of it spent
waiting for the excited resonance to decay to the convergence criterion --
see EndCriteria below). This is normal and expected for full 3D FDTD on
an on-chip structure; it's exactly why faster (but less physically exact)
tools like ASITIC/EMX exist in the RFIC industry. Don't expect this script
to return quickly for anything but a "does this run at all" sanity check
at a very small turn count.

--------------------------------------------------------------------------
HOW TO RUN (inside the eda-env-designer:gf180mcuD container)
--------------------------------------------------------------------------
This container already has openEMS + its Python (Cython) bindings built
in, at TOOLS_INSTALL_PATH/openems (PATH/PYTHONPATH already set by the
image). Mount this script and an output directory, and cap CPU/memory so
a long-running FDTD job can never destabilize the host (openEMS's own
thread-count auto-detection ("numThreads=0 / max") does NOT reliably
respect a cgroup --cpus limit, so this script passes an EXPLICIT thread
count -- see --threads below and its use in run_and_extract()):

    docker run --rm \\
        --cpus=8 --memory=6g -e OMP_NUM_THREADS=8 \\
        -v /path/to/this/script:/work/sim.py:ro \\
        -v /path/to/output/dir:/work/out \\
        eda-env-designer:gf180mcuD \\
        python3 /work/sim.py --out /work/out --inner-radius-um 20 \\
            --turns 3 --spacing-um 2 --track-width-um 1 --threads 8

Start with a SMALL --turns (2-3) to sanity-check the whole pipeline
(geometry, meshing, ports) actually runs and produces a physically sane
Y11 (Re(Y11) > 0 everywhere -- see the sign-convention check printed at
the end) before committing hours to a design-sized geometry.

Add --preview-only to just render the layout PNG (a few seconds, no
Docker/openEMS needed beyond matplotlib) without running any FDTD at all
-- useful for iterating on the geometry parameters themselves first.
--------------------------------------------------------------------------
"""
import argparse
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ==========================================================================
# GF180MCU Metal5 / oxide / substrate stack -- every value here was read
# directly out of the real GF180MCU PDK files staged inside the
# eda-env-designer:gf180mcuD container (not from vendor documentation, and
# not a generic/literature placeholder), with the exact source cited. The
# one exception -- substrate resistivity -- genuinely IS a literature
# placeholder: open_pdks deletes the PDK's raw source tree after building
# it, so no volumetric substrate resistivity was recoverable from the
# container; revisit this before trusting an absolute (not just relative/
# comparative) Q or SRF number out of this script.
# ==========================================================================
STACK = {
    # libs.tech/magic/gf180mcuD.tech, "resist (allm5)/metal5" (typical/tt corner)
    "metal5_sheet_r_ohm_per_sq": 0.040,
    # libs.tech/klayout/tech/d25/gf180mcu.lyd25 (KLayout's real 3D stack view)
    "metal5_thickness_m": 1.1925e-6,
    "metal5_z_start_m": 5.76e-6,        # height of Metal5's underside above the substrate
    # libs.tech/magic/gf180mcuD.tech, "defaultareacap allm5 metal5" (tt corner)
    # -- cross-checked against the d25 stack height via C=eps0*epsr/height,
    # giving ~6.0 aF/um^2, within ~5% of this measured value.
    "metal5_areacap_aF_per_um2": 5.798,
    "oxide_epsilon_r": 3.9,             # SiO2 -- standard material constant
    "substrate_epsilon_r": 11.9,        # silicon -- standard material constant
    "substrate_resistivity_ohm_cm": 10.0,  # PLACEHOLDER, see module docstring
}


# ==========================================================================
# Geometry: an octagonal spiral, built as one continuous "ribbon" polygon
# (not independent per-segment rectangles) with a proper mitered offset at
# each interior vertex.
# ==========================================================================
def octagonal_spiral_centerline(inner_radius_um, n_turns, track_width_um, spacing_um):
    """Centerline vertices of an octagonal spiral: sample an Archimedean
    spiral r(theta) = inner_radius + pitch*theta/(2*pi) at 8 angles per
    turn. Connecting those samples with straight lines is what actually
    produces the classic faceted octagonal-spiral shape real spiral
    inductors use -- a true circular spiral would need far more points
    per turn."""
    pitch = track_width_um + spacing_um
    n_points = n_turns * 8 + 1
    pts = []
    for k in range(n_points):
        theta = k * (2 * math.pi / 8)
        r = inner_radius_um + pitch * theta / (2 * math.pi)
        pts.append((r * math.cos(theta), r * math.sin(theta)))
    return pts


def _unit(dx, dy):
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def spiral_ribbon_polygon(centerline, width_um):
    """One continuous ribbon polygon around the centerline, with a proper
    mitered offset at each interior vertex -- NOT independently-offset,
    overlapping segment rectangles (an earlier, simpler attempt at this
    left small overlapping corner artifacts at every turn: extra, locally
    non-uniform geometric detail sitting right where FDTD meshing is
    already most sensitive to feature size).

    A real miter join is cheap here specifically because every interior
    turn in this octagonal spiral is exactly 45 degrees (centerline points
    are sampled at a fixed 2*pi/8 angular step) -- so the miter length has
    one constant closed-form scale factor (1/cos(22.5 deg)) instead of
    needing a general per-corner miter solve for an arbitrary angle."""
    n = len(centerline)
    half_w = width_um / 2
    miter_scale = 1.0 / math.cos(math.radians(22.5))

    outer, inner = [], []
    for i, p in enumerate(centerline):
        if i == 0:
            ux, uy = _unit(centerline[1][0] - p[0], centerline[1][1] - p[1])
            nx, ny, scale = -uy, ux, 1.0
        elif i == n - 1:
            ux, uy = _unit(p[0] - centerline[i - 1][0], p[1] - centerline[i - 1][1])
            nx, ny, scale = -uy, ux, 1.0
        else:
            ux0, uy0 = _unit(p[0] - centerline[i - 1][0], p[1] - centerline[i - 1][1])
            ux1, uy1 = _unit(centerline[i + 1][0] - p[0], centerline[i + 1][1] - p[1])
            n0x, n0y = -uy0, ux0
            n1x, n1y = -uy1, ux1
            nx, ny = _unit(n0x + n1x, n0y + n1y)
            scale = miter_scale
        outer.append((p[0] + nx * half_w * scale, p[1] + ny * half_w * scale))
        inner.append((p[0] - nx * half_w * scale, p[1] - ny * half_w * scale))

    return outer + list(reversed(inner))


def _merge_close_lines(values, min_spacing):
    """Sorted de-duplication that also drops any value closer than
    min_spacing to the previously kept one. Two mesh anchors landing a
    fraction of a micron apart purely by geometric coincidence (very easy
    with 25+ octagon vertices) silently becomes the FDTD's smallest cell,
    and thus its CFL-limited timestep -- however coarse every other
    anchor's own spacing is."""
    ordered = sorted(values)
    merged = [ordered[0]]
    for v in ordered[1:]:
        if v - merged[-1] >= min_spacing:
            merged.append(v)
    return merged


def save_layout_preview(centerline, track_width_um, path):
    """Top-view PNG, independent of CSXCAD/openEMS -- plotted straight
    from the same ribbon polygon fed to the FDTD structure, so it shows
    exactly what the solver will see. This container has no GUI viewer for
    CSXCAD geometry (QCSXCAD/AppCSXCAD needs Qt4, which is EOL and not
    packaged for the container's Rocky Linux 8 base, and isn't needed for
    this fully-scripted/headless workflow anyway) -- this plot is the
    practical substitute."""
    fig, ax = plt.subplots(figsize=(5, 5))
    ribbon = spiral_ribbon_polygon(centerline, track_width_um)
    ax.fill(*zip(*(ribbon + [ribbon[0]])), color="goldenrod", edgecolor="darkgoldenrod", linewidth=0.3)
    ax.plot(*centerline[0], "go", markersize=6, label="a (inner, driven)")
    ax.plot(*centerline[-1], "rs", markersize=6, label="b (outer, grounded)")
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Layout preview written to {path}")


# ==========================================================================
# The openEMS/CSXCAD structure itself.
# ==========================================================================
def build_structure(geometry, f_max_hz):
    """Builds and returns (FDTD, port_a). Imports CSXCAD/openEMS only
    inside this function so the geometry/preview functions above stay
    usable even without openEMS installed (e.g. for --preview-only)."""
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    unit = 1e-6  # every coordinate below is in micrometers
    inner_radius = geometry["inner_radius_um"]
    n_turns = geometry["n_turns"]
    track_width = geometry["track_width_um"]
    spacing = geometry["spacing_um"]

    centerline = octagonal_spiral_centerline(inner_radius, n_turns, track_width, spacing)
    outer_radius = inner_radius + (track_width + spacing) * n_turns
    half_w = track_width / 2
    a_xy, b_xy = centerline[0], centerline[-1]

    # Conductivity from real GF180MCU data: sigma = 1 / (sheet_R * thickness).
    metal5_sigma = 1.0 / (STACK["metal5_sheet_r_ohm_per_sq"] * STACK["metal5_thickness_m"])
    substrate_sigma = 1.0 / (STACK["substrate_resistivity_ohm_cm"] * 1e-2)
    z_ox_top = STACK["metal5_z_start_m"] / unit
    z_m5_top = z_ox_top + STACK["metal5_thickness_m"] / unit

    f0 = f_max_hz / 2
    fc = f_max_hz / 2
    FDTD = openEMS(EndCriteria=1e-4)
    FDTD.SetGaussExcite(f0, fc)
    FDTD.SetBoundaryCond(["PML_8"] * 6)  # absorbing on all 6 box faces -- an open-space structure, not a cavity

    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(unit)

    # Manual mesh: fine resolution ONLY near the spiral's own conductor --
    # anchored by a line at every centerline vertex's x/y (plus each
    # port's own footprint corners), then SmoothMeshLines grades outward
    # toward the domain boundary. Skipping this and only anchoring the two
    # outer boundary lines is NOT just slower -- confirmed the hard way,
    # it applies near-uniform fine resolution across the WHOLE domain
    # instead of just the spiral's own annulus, exhausting a 6GB container
    # limit before ever finishing mesh setup, for a domain that should be
    # extremely cheap by FDTD standards (on-chip dimensions are
    # geometry-limited, not wavelength-limited: even 20GHz's free-space
    # lambda/20 is ~380um, far coarser than the few-um features here).
    res_xy = max(track_width / 2, 0.4)
    port_xs = [a_xy[0] - half_w, a_xy[0] + half_w, b_xy[0] - half_w, b_xy[0] + half_w]
    port_ys = [a_xy[1] - half_w, a_xy[1] + half_w, b_xy[1] - half_w, b_xy[1] + half_w]
    xs = _merge_close_lines([p[0] for p in centerline] + port_xs, res_xy)
    ys = _merge_close_lines([p[1] for p in centerline] + port_ys, res_xy)
    box = outer_radius + 6 * track_width
    mesh.AddLine("x", xs + [-box, box])
    mesh.AddLine("y", ys + [-box, box])
    mesh.SmoothMeshLines("x", res_xy, ratio=1.4)
    mesh.SmoothMeshLines("y", res_xy, ratio=1.4)

    sub_thick = 6 * (z_m5_top - z_ox_top) + z_ox_top
    mesh.AddLine("z", [-sub_thick, 0, z_ox_top, z_m5_top])
    mesh.SmoothMeshLines("z", STACK["metal5_thickness_m"] / unit / 2, ratio=1.4)
    air_above = 4 * (z_m5_top - z_ox_top)
    mesh.AddLine("z", [z_m5_top + air_above])
    mesh.SmoothMeshLines("z", res_xy, ratio=1.4)

    substrate = CSX.AddMaterial("substrate", epsilon=STACK["substrate_epsilon_r"], kappa=substrate_sigma)
    substrate.AddBox([-box, -box, -sub_thick], [box, box, 0])

    oxide = CSX.AddMaterial("oxide", epsilon=STACK["oxide_epsilon_r"])
    oxide.AddBox([-box, -box, 0], [box, box, z_ox_top])

    metal5 = CSX.AddMaterial("metal5", kappa=metal5_sigma)
    ribbon = spiral_ribbon_polygon(centerline, track_width)
    metal5.AddLinPoly([[p[0] for p in ribbon], [p[1] for p in ribbon]], "z", z_ox_top, z_m5_top - z_ox_top)

    # Both ports are vertical stubs straight down from the Metal5 trace,
    # through the oxide, to the substrate surface -- 'a' is driven, 'b' is
    # a plain R=0 short (a pure metal bridge, not an excitation), letting
    # the lossy substrate itself carry the real return current path rather
    # than an idealized ground tie. Each gets a small SQUARE footprint
    # (one track_width per side), not a mathematical zero-area point: a
    # zero-area port risks not being recognized as "overlapping" the metal
    # at all (confirmed against thliebig/openEMS-Project discussion #158
    # -- CSXCAD silently drops a non-overlapping excitation box, so you
    # simulate a fully unexcited structure and get zero-signal-everywhere
    # nonsense out, with only an easy-to-miss "Unused primitive" warning
    # as a clue).
    port_a = FDTD.AddLumpedPort(
        1, 50, [a_xy[0] - half_w, a_xy[1] - half_w, 0], [a_xy[0] + half_w, a_xy[1] + half_w, z_m5_top], "z", excite=1)
    FDTD.AddLumpedPort(
        2, 0, [b_xy[0] - half_w, b_xy[1] - half_w, 0], [b_xy[0] + half_w, b_xy[1] + half_w, z_m5_top], "z", excite=0)

    return FDTD, port_a


def run_and_extract(geometry, sim_path, f_max_hz, n_freq, num_threads):
    """Runs the FDTD structure and returns {freqs, y11, q, srf_ghz,
    peak_q, peak_q_freq_ghz}."""
    import numpy as np

    FDTD, port_a = build_structure(geometry, f_max_hz)
    # numThreads=0 ("max", openEMS's own Run() default) has been observed
    # pinning a SINGLE core during the actual timestepping engine despite
    # the earlier operator-SETUP phase correctly using every core -- CPU
    # auto-detection inside a cgroup --cpus-limited container is
    # unreliable (a known class of OpenMP/hwloc issue). Pass the thread
    # count explicitly instead of trusting "max" to mean anything useful.
    FDTD.Run(sim_path, cleanup=True, numThreads=num_threads)

    freqs = np.linspace(1e6, f_max_hz, n_freq)
    port_a.CalcPort(sim_path, freqs, ref_impedance=50)
    # Conjugated: confirmed on a real converged run (EndCriteria reached,
    # -40dB energy decay) that openEMS's DFT uses the opposite time
    # convention (exp(+jwt), the physics/EM community's usual choice) from
    # the exp(-jwt) circuit-theory convention this script's Q/SRF formulas
    # assume. Un-conjugated, Re(Y11) was correctly positive everywhere
    # (passivity held) but Im(Y11) was POSITIVE across the ENTIRE swept
    # range -- i.e. an always-capacitive-looking impedance already at
    # 1 MHz, unphysical for a structure this overwhelmingly inductive.
    # Conjugating flips only Im (Re/passivity unaffected) and gives the
    # expected smoothly-rising, always-positive Q(f).
    y11 = np.conj(port_a.if_tot / port_a.uf_tot)

    re, im = np.real(y11), np.imag(y11)
    # A passive one-port's Re(Y11) must be positive at every frequency --
    # if it comes out negative here, the port current-direction sign
    # convention has flipped somewhere (an easy, well-known gotcha); the
    # fix is negating y11 itself, not each derived quantity separately.
    if (re < 0).any():
        print("WARNING: Re(Y11) went negative somewhere -- check the port current sign convention.")
    q = -im / re  # sign flip: an inductive one-port has Im(Y11) < 0, so -Im/Re comes out positive

    srf_hz = None
    for i in range(1, len(freqs)):
        if im[i - 1] < 0 <= im[i]:
            frac = -im[i - 1] / (im[i] - im[i - 1])
            srf_hz = freqs[i - 1] + frac * (freqs[i] - freqs[i - 1])
            break

    peak_idx = int(np.argmax(q))
    return {
        "freqs": freqs, "y11": y11, "q": q,
        "srf_ghz": (srf_hz / 1e9) if srf_hz else None,
        "peak_q": float(q[peak_idx]), "peak_q_freq_ghz": float(freqs[peak_idx] / 1e9),
    }


def save_qf_plot(result, path):
    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.plot(result["freqs"] / 1e9, result["q"])
    if result["srf_ghz"] is not None:
        ax.axvline(result["srf_ghz"], color="black", linestyle="--", linewidth=1, label=f"SRF = {result['srf_ghz']:.2f} GHz")
    ax.axvline(
        result["peak_q_freq_ghz"], color="tab:red", linestyle=":", linewidth=1,
        label=f"peak Q = {result['peak_q']:.1f} @ {result['peak_q_freq_ghz']:.2f} GHz",
    )
    ax.set_xlabel("frequency (GHz)")
    ax.set_ylabel("Q")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Q(f) plot written to {path}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inner-radius-um", type=float, required=True)
    p.add_argument("--turns", type=int, required=True)
    p.add_argument("--spacing-um", type=float, required=True)
    p.add_argument("--track-width-um", type=float, required=True)
    p.add_argument("--out", required=True, help="Output directory for the preview PNG, Q(f) plot, and openEMS working files")
    p.add_argument("--f-max", type=float, default=20e9, help="Highest frequency of interest, Hz (default 20 GHz)")
    p.add_argument("--n-freq", type=int, default=201, help="Number of frequency points in the Y11(f)/Q(f) sweep")
    p.add_argument("--threads", type=int, default=8, help="Explicit FDTD engine thread count (see module docstring on why this can't be left to 'auto')")
    p.add_argument("--preview-only", action="store_true", help="Only render the layout PNG, skip the (many-hour) FDTD run entirely")
    args = p.parse_args()

    geometry = {
        "inner_radius_um": args.inner_radius_um, "n_turns": args.turns,
        "spacing_um": args.spacing_um, "track_width_um": args.track_width_um,
    }
    os.makedirs(args.out, exist_ok=True)

    centerline = octagonal_spiral_centerline(
        geometry["inner_radius_um"], geometry["n_turns"], geometry["track_width_um"], geometry["spacing_um"])
    save_layout_preview(centerline, geometry["track_width_um"], os.path.join(args.out, "layout_preview.png"))

    if args.preview_only:
        return

    print("Starting the FDTD run -- this is the many-hour part. See the module")
    print("docstring's 'WHY OPENEMS' section for why, and watch this container's")
    print("stdout for openEMS's own periodic '[@ Ht Mm Ss] Timestep: ...' progress lines.")
    sim_path = os.path.join(args.out, "openems_sim")
    result = run_and_extract(geometry, sim_path, args.f_max, args.n_freq, args.threads)

    print(f"\nSRF = {result['srf_ghz']:.3f} GHz" if result["srf_ghz"] else "\nSRF: not found in this frequency sweep")
    print(f"Peak Q = {result['peak_q']:.2f} @ {result['peak_q_freq_ghz']:.3f} GHz")
    save_qf_plot(result, os.path.join(args.out, "q_vs_freq.png"))


if __name__ == "__main__":
    main()
