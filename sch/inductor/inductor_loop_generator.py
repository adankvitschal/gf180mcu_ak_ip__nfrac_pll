"""Parametric rectangular closed-loop inductor generator: geometry parameters
(outer width, outer height, track width) -> a real 3D FDTD extraction via
openEMS/CSXCAD, run against GF180MCU's actual Metal5/oxide stack (see
gf180mcu_stack.json) -> the 6 electrical parameters (l, rs, cox, rsub, csub,
cs) that sch/inductor/inductor_loop.sch's own 'name' placeholder tokens
substitute in, via this project's normal materialization mechanism
(substitute_params()) -- same generator contract as inductor_spiral_generator.py
(geometry_from_params/build_openems_structure/fit_electrical_params), so the
existing generic openEMS runner (analog_designer_core's
openems_generator_runner.py, out of this repo) drives this topology exactly
the same way, no runner changes needed.

Why this exists alongside inductor_spiral_generator.py: the spiral generator
is real GF180MCU geometry but still has an open, unresolved bug (Q comes out
negative/capacitive-looking on the crossunder-bridged design -- see
openems_inductor_status.md). This module formalizes the MUCH simpler
rectangular closed-loop structure already validated standalone in
tools/gf180mcu_inductor_diag_loop.py ("Step 1" in that memory file: single
planar in-line port bridging a small gap cut into one side of a closed
Metal5 ring, current returns through the loop's own remaining three sides --
no crossunder, no substrate contact anywhere) -- extracted R came out within
5% of the analytic hand estimate. Formalizing it as a real generator/topology
(instead of a one-off tools/ script) gives this project a SECOND, independent,
already-validated openEMS-backed inductor to exercise the whole materialize
-> FDTD -> pi-model-fit -> SPICE workflow against, without depending on the
spiral's still-open bug being fixed first.

Circuit model: reuses the EXACT SAME pi-network template as the spiral
topology (inductor_spiral.sch, copied verbatim to inductor_loop.sch -- two
series half-windings a-R2-L1-ct, ct-L2-R1-b, a center-tap coupling cap from
each terminal to ct, and a Cox/Rsub/Csub substrate branch per terminal) --
same 6 derived names (l, rs, cox, rsub, csub, cs), same per-half convention
(this generator's build_openems_structure() measures the loop as ONE
continuous 2-terminal winding end to end, same one-port Y11 methodology as
the spiral's own fit_electrical_params(), so 'l'/'rs' returned here are
HALF the total loop value, matching the template's two series L/R pairs
summing to the real total).

Physical simplifications (v1, same spirit as inductor_spiral_generator.py's
own documented simplifications):
- No crossunder/center-tap EM model at all -- single closed loop, one
  in-line planar port bridging a small gap cut into the top side. rsub/csub/
  cs are placeholder-quality constants, same as the spiral generator (this
  one-port methodology has no distinct center-tap measurement to derive them
  from).
- The port's z-range spans only the metal layer's own z-range
  (z_ox_top..z_m5_top), never touching the substrate directly -- the fix
  that made tools/gf180mcu_inductor_diag_loop.py's own R extraction work
  (see that script's docstring and openems_inductor_status.md's "Step 1
  RESULT: CONFIRMED" entry).
- Rectangular (not octagonal) loop: a deliberately simpler shape than the
  spiral's, on purpose -- this generator's whole point is being a simple,
  already-validated reference, not a second attempt at a realistic layout.
"""
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_THIS_DIR = os.path.dirname(__file__)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
from pi_model_fit import fit_rsub_csub_staged, fit_eddy_branch  # noqa: E402 (sys.path setup must come first)

_STACK_PATH = os.path.join(_THIS_DIR, "gf180mcu_stack.json")

# Same generic placeholder-quality constants as inductor_spiral_generator.py
# (see that module's own docstring for why) -- kept as separate literals
# here (not a shared import) so this generator stays self-contained, same
# "no bespoke cross-file coupling" spirit already documented there.
_PLACEHOLDER_L_HALF_H = 2.895e-9
_PLACEHOLDER_RS_HALF_OHM = 1.7645
_PLACEHOLDER_CSUB_F = 103.1e-15

FIELD_DUMP_NAME = "field_dump"  # fixed name openems_generator_runner.py looks for -- see inductor_spiral_generator.py's own docstring for the confirmed HDF5 layout this produces

# 2026-09-15: per-layer current-density dumps -- metal5 winding + a
# near-surface substrate slice (no metal4/via4 here, this topology has no
# crossunder). Same rationale, same "not yet consumed by the runner beyond
# FIELD_DUMP_NAME" caveat as inductor_spiral_generator.py's own
# FIELD_DUMP_NAMES -- see that module's docstring for the full explanation.
FIELD_DUMP_NAMES = {
    "metal5": FIELD_DUMP_NAME,
    "substrate": "field_dump_substrate",
}


def load_stack(corner="tt", path=_STACK_PATH):
    """Same metal5/oxide/substrate fields as inductor_spiral_generator.py's
    own load_stack() -- metal4/via4 deliberately omitted, this topology has
    no crossunder. Also surfaces `substrate_isosub_sheet_r_ohm_per_sq`
    (real, GF180MCU-sourced -- 'resist (pwell,isosub)/well' in
    gf180mcuD.tech), which fit_electrical_params() uses for a physically-
    motivated rsub/rsub_ct spreading-resistance estimate (2026-09-15:
    previously loaded into gf180mcu_stack.json but never consumed anywhere --
    fit_electrical_params() used to assign the substrate's bulk resistivity
    in ohm*cm directly as rsub in ohms, a real unit-mismatch bug, see this
    module's own fit_electrical_params() docstring)."""
    with open(path) as f:
        stack = json.load(f)
    m5 = stack["metal5"]
    sub = stack["substrate"]
    return {
        "metal5_sheet_r_ohm_per_sq": m5["sheet_resistance_ohm_per_sq"][corner],
        "metal5_thickness_m": m5["thickness_m"]["value"],
        "metal5_z_start_m": m5["z_start_m"]["value"],
        "metal5_areacap_aF_per_um2": m5["areacap_to_substrate_aF_per_um2"][corner],
        "metal5_perimcap_aF_per_um": m5["perimcap_to_substrate_aF_per_um"][corner],
        "oxide_epsilon_r": stack["oxide"]["epsilon_r"],
        "substrate_epsilon_r": sub["epsilon_r"],
        "substrate_resistivity_ohm_cm": sub["resistivity_ohm_cm"]["value"],
        "substrate_isosub_sheet_r_ohm_per_sq": sub["isosub_sheet_resistance_ohm_per_sq"]["value"],
    }


def geometry_from_params(params):
    """Extracts/type-casts this topology's 3 free geometric parameters
    (simpler than the spiral's 4 -- no turns/spacing, just a single closed
    rectangular ring) out of a raw {name: "spice-value-string-or-number"}
    params dict. Same role as inductor_spiral_generator.py's own
    geometry_from_params() -- the ONLY place that knows this topology's own
    free parameter names."""
    return {
        "width_um": float(params["width_um"]),
        "height_um": float(params["height_um"]),
        "track_width_um": float(params["track_width_um"]),
    }


def loop_half_extents(width_um, height_um, track_width_um):
    """Outer/inner half-extents of the rectangular ring -- shared by
    build_openems_structure() (geometry) and fit_electrical_params()
    (centerline length), same reasoning as the spiral generator sharing
    octagonal_spiral_centerline() between its own two consumers."""
    x_out = width_um / 2
    y_out = height_um / 2
    x_in = x_out - track_width_um
    y_in = y_out - track_width_um
    return x_out, y_out, x_in, y_in


def mesh_resolution_um(track_width_um):
    """Base xy mesh resolution and the matching port gap, tied together the
    same way inductor_spiral_generator.py's build_openems_structure() ties
    res_xy/port_len: the port gap must survive _merge_close_lines-style
    dedup/SmoothMeshLines snapping (no adjacent-turn spacing constraint here
    -- a closed loop has no turns -- so track_width_um alone sets the
    scale)."""
    res_xy = max(track_width_um / 4, 0.2)
    port_gap_um = max(res_xy * 1.5, min(0.5, track_width_um / 2))
    return res_xy, port_gap_um


def save_layout_preview(geometry, path):
    """Top-view PNG of the generated loop, independent of CSXCAD/openEMS --
    plotted straight from the same box geometry fed to build_openems_structure()'s
    metal5.AddBox() calls, so it shows exactly what the FDTD solver will
    see. Same role/reasoning as inductor_spiral_generator.py's own
    save_layout_preview(), just a simpler shape."""
    width_um, height_um, track_width_um = geometry["width_um"], geometry["height_um"], geometry["track_width_um"]
    x_out, y_out, x_in, y_in = loop_half_extents(width_um, height_um, track_width_um)
    _, port_gap_um = mesh_resolution_um(track_width_um)
    half_gap = port_gap_um / 2

    fig, ax = plt.subplots(figsize=(5, 5))
    for (bx0, by0, bx1, by1) in [
        (-x_out, y_in, -half_gap, y_out),   # top-left of gap
        (half_gap, y_in, x_out, y_out),     # top-right of gap
        (-x_out, -y_out, x_out, -y_in),     # bottom arm
        (-x_out, -y_out, -x_in, y_out),     # left arm
        (x_in, -y_out, x_out, y_out),       # right arm
    ]:
        ax.fill([bx0, bx1, bx1, bx0], [by0, by0, by1, by1], color="goldenrod", edgecolor="darkgoldenrod", linewidth=0.3)
    ax.plot(-half_gap, (y_in + y_out) / 2, "go", markersize=6, label="a (port -)")
    ax.plot(half_gap, (y_in + y_out) / 2, "rs", markersize=6, label="b (port +)")
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def add_field_dump(CSX, name, box, z0, z1, dump_freq_hz):
    """Frequency-domain total-current-density dump, same API/shape as
    inductor_spiral_generator.py's own add_field_dump() (see that
    function's docstring for the confirmed HDF5 layout and for why z1-z0
    should stay thin, comparable to one physical layer's own thickness) --
    duplicated here (not imported) since the dump box's footprint is
    geometry-specific, same reasoning that module gives for keeping it
    PDK/geometry-local. Generic over `name`/`z0`/`z1` so callers below can
    use it for both the metal5 winding and a substrate slice, each landing
    as an independently-named '<name>.h5'."""
    dump = CSX.AddDump(name, dump_type=13, file_type=1)
    dump.AddFrequency(dump_freq_hz)
    dump.AddBox([-box, -box, z0], [box, box, z1])


def build_openems_structure(geometry, stack, f_max_hz, dump_field=False):
    """PDK/geometry-specific: builds the CSXCAD/openEMS structure (a closed
    rectangular Metal5 loop with a single gap bridged by one in-line
    LumpedPort, oxide, substrate, mesh) and returns (FDTD, port) --
    everything analog_designer_core's generic openems_generator_runner.py
    needs to call FDTD.Run()/port.CalcPort() itself. Ported directly from
    tools/gf180mcu_inductor_diag_loop.py's own build_structure() (already
    FDTD-validated there, R within 5% of the analytic estimate), just
    parametrized on width_um/height_um/track_width_um instead of that
    script's module-level constants.

    Import of CSXCAD/openEMS deferred to this function, same reasoning as
    inductor_spiral_generator.py's own build_openems_structure()."""
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    unit = 1e-6
    width_um = geometry["width_um"]
    height_um = geometry["height_um"]
    track_width_um = geometry["track_width_um"]

    x_out, y_out, x_in, y_in = loop_half_extents(width_um, height_um, track_width_um)
    res_xy, port_gap_um = mesh_resolution_um(track_width_um)
    half_gap = port_gap_um / 2

    metal5_sigma = 1.0 / (stack["metal5_sheet_r_ohm_per_sq"] * stack["metal5_thickness_m"])
    substrate_sigma = 1.0 / (stack["substrate_resistivity_ohm_cm"] * 1e-2)
    z_ox_top = stack["metal5_z_start_m"] / unit
    z_m5_top = z_ox_top + stack["metal5_thickness_m"] / unit

    f0 = f_max_hz / 2
    fc = f_max_hz / 2
    FDTD = openEMS(EndCriteria=1e-4)
    FDTD.SetGaussExcite(f0, fc)
    FDTD.SetBoundaryCond(["PML_8"] * 6)

    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(unit)

    box = x_out + 6 * track_width_um
    mesh.AddLine("x", [-x_out, -x_in, -half_gap, half_gap, x_in, x_out, -box, box])
    mesh.AddLine("y", [-y_out, -y_in, y_in, y_out, -box, box])
    mesh.SmoothMeshLines("x", res_xy, ratio=1.4)
    mesh.SmoothMeshLines("y", res_xy, ratio=1.4)

    sub_thick = 6 * (z_m5_top - z_ox_top) + z_ox_top  # a few skin/stack-heights of substrate; PML absorbs beyond it
    mesh.AddLine("z", [-sub_thick, 0, z_ox_top, z_m5_top])
    mesh.SmoothMeshLines("z", stack["metal5_thickness_m"] / unit / 2, ratio=1.4)
    air_above = 4 * (z_m5_top - z_ox_top)
    mesh.AddLine("z", [z_m5_top + air_above])
    mesh.SmoothMeshLines("z", res_xy, ratio=1.4)

    substrate = CSX.AddMaterial("substrate", epsilon=stack["substrate_epsilon_r"], kappa=substrate_sigma)
    substrate.AddBox([-box, -box, -sub_thick], [box, box, 0])

    oxide = CSX.AddMaterial("oxide", epsilon=stack["oxide_epsilon_r"])
    oxide.AddBox([-box, -box, 0], [box, box, z_ox_top])

    # Closed rectangular Metal5 loop ("picture frame") -- top arm split in
    # two around the port gap, the other three sides solid. Every box's xy
    # footprint overlaps its neighbor at each corner by construction (e.g.
    # the left-arm box spans the FULL y range, not just -y_in..y_in) --
    # deliberately, per openems_inductor_status.md's "general lesson":
    # touching-only box boundaries at a junction are not safe in the Yee
    # grid, always overlap by a margin. This exact corner-overlap pattern
    # is the one already validated in tools/gf180mcu_inductor_diag_loop.py.
    metal5 = CSX.AddMaterial("metal5", kappa=metal5_sigma)
    metal5.AddBox([-x_out, y_in, z_ox_top], [-half_gap, y_out, z_m5_top])   # top-left of gap
    metal5.AddBox([half_gap, y_in, z_ox_top], [x_out, y_out, z_m5_top])     # top-right of gap
    metal5.AddBox([-x_out, -y_out, z_ox_top], [x_out, -y_in, z_m5_top])    # bottom arm
    metal5.AddBox([-x_out, -y_out, z_ox_top], [-x_in, y_out, z_m5_top])    # left arm
    metal5.AddBox([x_in, -y_out, z_ox_top], [x_out, y_out, z_m5_top])      # right arm

    # In-line planar port bridging the gap, current flows along x (the
    # trace's own direction) -- z-range z_ox_top..z_m5_top only, never
    # touching the substrate. excite scaled to a fixed ~10V-equivalent
    # regardless of port_gap, same reasoning as inductor_spiral_generator.py's
    # own excite_v_per_m (keeps excitation well above the float noise floor).
    excite_v_per_m = 10.0 / (port_gap_um * unit)
    port_a = FDTD.AddLumpedPort(
        1, 50, [-half_gap, y_in, z_ox_top], [half_gap, y_out, z_m5_top], "x", excite=excite_v_per_m)

    if dump_field:
        add_field_dump(CSX, FIELD_DUMP_NAMES["metal5"], box, z_ox_top, z_m5_top, f0)
        # Thin near-surface substrate slice (metal5's own thickness scale,
        # right below z=0) rather than the full sub_thick depth -- see
        # add_field_dump()'s own docstring for why a deep box would blur
        # away exactly the near-surface concentration this is meant to show.
        metal5_thickness_um = stack["metal5_thickness_m"] / unit
        add_field_dump(CSX, FIELD_DUMP_NAMES["substrate"], box, -metal5_thickness_um, 0, f0)

    return FDTD, port_a


def fit_electrical_params(geometry, stack, em_result=None):
    """PDK/model-specific: returns {'l', 'rs', 'cox', 'rsub', 'csub', 'cs',
    'cox_ct', 'rsub_ct', 'csub_ct', 'rp_eddy', 'lp_eddy'} (SI base units:
    H, ohm, F) -- the first 6 are the original per-half/per-terminal names
    (same em_result=None fast-placeholder-path vs em_result=dict
    real-FDTD-path split as inductor_spiral_generator.py's own
    fit_electrical_params()); the next 3 are the third substrate tap added
    at the 'ct' node (2026-09-15 planning session, "double-pi"
    investigation -- see inductor_loop.sch's own header comment); the last
    2 are an ordinary (no mutual inductance) eddy-current/skin-proximity
    loss branch (2026-09-15, same-day follow-up -- see (f) below and
    pi_model_fit.py's y11_with_eddy_branch()/fit_eddy_branch()
    docstrings). 2026-09-15 rewrite, replacing several real, previously-
    latent issues (not just adding new names):

    1. `rsub` used to be `stack["substrate_resistivity_ohm_cm"]` (10.0)
       assigned DIRECTLY as ohms -- a real unit-mismatch bug (Ω·cm literal
       used as Ω). Now a real (if approximate) geometry-based spreading-
       resistance estimate, using `substrate_isosub_sheet_r_ohm_per_sq`
       (3250 Ω/sq, real GF180MCU value, previously loaded into
       gf180mcu_stack.json but never consumed anywhere) -- see (a) below.
       This is now the FALLBACK value (em_result=None) instead of a bare,
       physically-meaningless literal.
    2. `rsub`/`csub` used to be either a fixed literal (rsub) or a fixed
       placeholder constant (csub) UNCONDITIONALLY, even when a real EM
       Y11 sweep was available -- never actually fit to it. Now, when
       em_result is given, both are extracted via a physics-informed staged
       fit (pi_model_fit.fit_rsub_csub_staged(): rs/l/cox/cs held fixed at
       their own already-trustworthy values, only rsub/csub float, near the
       data-driven resonance -- matches standard Yue & Wong-style on-chip
       inductor extraction practice, and is what this project's own
       tools/gf180mcu_inductor_refit.py already validated as the most
       defensible of 6 fitting strategies tried). See (d) below.
    3. `cs` (center-tap bypass cap) is fixed at exactly 0.0 for this
       topology, dropping `_PLACEHOLDER_CS_F` entirely -- `cs` represents
       adjacent-turn crossover coupling, which has no physical mechanism for
       a single-turn rectangular loop (unlike the multi-turn `spiral`
       topology, which keeps a real placeholder pending its own real
       formula). See (e) below.
    4. `cox` is now split 3 ways (1/4, 1/4, 1/2) instead of 2 ways (1/2,
       1/2) -- trapezoidal area weighting once a third tap exists at 'ct'
       (each outer terminal 'owns' half a winding-half's worth of trace
       area, the 'ct' node owns both adjoining halves' near sides). This is
       a real VALUE CHANGE for `cox` (was cox_total_f/2, now cox_total_f/4)
       for any already-materialized params.json with real EM-fitted values
       -- re-materialization needed, not just a docs update. See (b) below.
    5. NEW: `rp_eddy`/`lp_eddy` model an eddy-current/skin-proximity loss
       branch -- an ordinary series R+L placed IN PARALLEL with each
       half's own `l` (no mutual inductance/SPICE `K` element needed; this
       is the classical T-equivalent-circuit representation of a
       shorted-secondary transformer, written with plain components) -- a
       DIFFERENT physical mechanism from the purely electrostatic
       Cox-Rsub-Csub branch, which has no way to represent it at all.
       Experimentally confirmed (2026-09-15) to explain a real,
       previously-unexplained feature in cached EM data: Im(Y11) dipping
       at resonance then only PARTIALLY recovering (not crossing back
       through zero) as frequency keeps rising -- full-band RMS relative
       error against the 100x50um/2um cached run dropped from ~42%
       (without this branch) to ~1.1% (with it), fit with only 2 new free
       parameters. A simpler 1-parameter alternative (plain resistor in
       parallel with `l`, no extra inductor) was tried and empirically
       rejected -- only reached 34% RMS error, since a plain R∥L branch's
       high-frequency limit is a constant resistance, not the reduced-
       but-still-inductive reactance the real data shows. See (f) below.

    IMPORTANT CAVEAT on `cox_ct`/`rsub_ct`/`csub_ct` (see inductor_loop.sch's
    own header comment and pi_model_fit.assert_ct_tap_unobservable()): this
    third branch sits exactly on the a<->b mirror-symmetry line, so it is
    mathematically INVISIBLE to the one-port Y11 measurement this function
    fits against -- no value of cox_ct/rsub_ct/csub_ct can move Y11 at all.
    They are therefore NEVER EM-fit (there is nothing in the data that could
    constrain them) -- `cox_ct` is a real geometry-based estimate (same
    quality as `cox`), `rsub_ct` a real geometry-based spreading-resistance
    estimate (same formula family as `rsub`, see (a)), and `csub_ct` is
    propagated from whatever `csub` the staged fit (or placeholder) already
    produced, scaled by the same 2x area ratio as `cox_ct`/`rsub`. Their only
    purpose is physical fidelity for the real VCO tank's substrate-noise-
    coupling path (there, 'ct' and 'sub' are NOT floating: ct->vdd,
    sub->SUB, see sch/vco/half_qvco_cell.sch) -- they do not, and cannot,
    improve this generator's own EM curve fit (that invariance is specific
    to 'sub' ALSO floating, exactly this function's own em_result
    convention). tb/inductor/tb_yparam.sch's one-port ngspice test grounds
    'sub' directly instead (see its own header comment) while leaving 'ct'
    floating -- a DIFFERENT boundary condition where the new branch is NOT
    invisible: confirmed via a real ngspice run (sim/_pi_ct_manual_check/),
    Y11 shifts by a small, physically-expected amount there (negligible at
    low frequency, growing to a few percent of the low-frequency |Y11|
    scale by 20GHz for a 100x50um/2um test geometry) -- expect tb_yparam's
    own Q/SRF numbers to shift slightly after this change, not stay bit-
    identical."""
    width_um = geometry["width_um"]
    height_um = geometry["height_um"]
    track_width_um = geometry["track_width_um"]
    _, port_gap_um = mesh_resolution_um(track_width_um)

    # Centerline perimeter (mid-trace), minus the port gap -- same rough
    # estimate (no sharp-corner correction) tools/gf180mcu_inductor_diag_loop.py
    # itself uses for its own expected_R sanity check, confirmed within 5%
    # of the real FDTD-extracted result there.
    centerline_len_um = 2 * (width_um - track_width_um - port_gap_um) + 2 * (height_um - track_width_um)
    trace_area_um2 = centerline_len_um * track_width_um
    # 2026-09-15: added the fringe/edge-field term -- an area-only estimate
    # underestimates cox for a narrow trace like this (confirmed: for this
    # topology's own default 40x10um/1um geometry, the fringe term below
    # comes out several times LARGER than the area term, not a minor
    # correction). Uses GF180MCU's own real per-perimeter-length coefficient
    # (metal5_perimcap_aF_per_um, see gf180mcu_stack.json) the same way
    # magic's own parasitic extractor combines the two terms: C = area*
    # areacap + perimeter*perimcap (gf180mcuD.tech's own section header
    # documents this exact formula). `trace_perimeter_um` approximates the
    # ribbon's perimeter as its two long edges (2x centerline length),
    # ignoring the small port-end caps and exact corner geometry -- same
    # "no sharp-corner correction" honesty level `centerline_len_um` itself
    # already carries.
    trace_perimeter_um = 2 * centerline_len_um
    cox_total_f = (trace_area_um2 * stack["metal5_areacap_aF_per_um2"]
                   + trace_perimeter_um * stack["metal5_perimcap_aF_per_um"]) * 1e-18

    # (a) rsub/rsub_ct: an "ohms-per-square" spreading-resistance analogy --
    # treat each tap's own footprint (a share of the trace's area, same
    # weighting as (b)'s cox split below) as a strip of width track_width_um
    # and length equal to that share of the centerline, through the real
    # GF180MCU isolation-substrate sheet resistance. This is a deliberately
    # rough geometric approximation (no literature-cited exact spreading-
    # resistance formula derived here), same honesty level this module's own
    # cox estimate already carries -- but it is at least dimensionally
    # correct and geometry-scaled, unlike the unit-mismatched literal it
    # replaces. Each OUTER terminal is attributed 1/4 of the trace (matching
    # cox's own new split, see (b)), so it gets 4x the sheet resistance of a
    # single full-length square; 'ct' is attributed 1/2 (2x), i.e. half of
    # rsub_per_terminal.
    isosub_rsh = stack["substrate_isosub_sheet_r_ohm_per_sq"]
    rsub_geom = 4 * isosub_rsh * track_width_um / centerline_len_um
    rsub_ct_geom = 2 * isosub_rsh * track_width_um / centerline_len_um

    if em_result is not None:
        import numpy as np

        freqs = em_result["freqs"]
        y11 = em_result["y11"]
        n_fit = max(3, len(freqs) // 20)  # lowest ~5% of the sweep, well below SRF
        w = 2 * np.pi * freqs[:n_fit]
        z11 = 1.0 / y11[:n_fit]
        # For a physical series inductor, Z11 = Rs + jwL, so Im(Z11) = +wL
        # (NOT -wL -- an earlier version of this formula, ported verbatim
        # from inductor_spiral_generator.py, had a spurious leading minus
        # here that inverted the sign of every EM-fitted 'l', magnitude
        # correct but sign backwards; confirmed against both a clean
        # synthetic Rs+jwL sweep and a real FDTD loop run, see
        # openems_inductor_status.md's 2026-09-15 entry).
        l_half = float(np.mean(np.imag(z11) / w)) / 2
        rs_half = float(np.mean(np.real(z11))) / 2

        # (d) rsub/csub staged fit -- see this function's own docstring
        # point 2. Seeded from the geometry-based rsub_geom estimate (not an
        # arbitrary literal) since fit_rsub_csub_staged() can converge with
        # rsub/csub UNCHANGED from their seed when cox is too small to give
        # the resonance region any real leverage over them (a real,
        # confirmed-in-practice non-identifiability regime, not a bug -- see
        # that function's own docstring).
        rsub, csub, _opt_result = fit_rsub_csub_staged(
            freqs, y11, rs=rs_half, l=l_half, cox=cox_total_f / 4, cs=0.0,
            rsub0=rsub_geom, csub0=_PLACEHOLDER_CSUB_F)

        # (f) eddy-current/skin-proximity loss branch -- see this
        # function's own docstring point 5 and pi_model_fit.py's
        # y11_with_eddy_branch()/fit_eddy_branch() docstrings for the full
        # derivation (an ordinary series R+L branch in PARALLEL with each
        # half's own `l`, no mutual inductance/SPICE `K` needed -- this is
        # exactly the classical T-equivalent circuit of a shorted-secondary
        # transformer, written with plain components). Experimentally
        # confirmed (2026-09-15 conversation) to explain the post-resonance
        # Im(Y11) "recovery" the electrostatic Cox-Rsub-Csub branch alone
        # cannot -- full-band RMS relative error dropped from ~42% to
        # ~1.1% on the 100x50um/2um cached run once this branch was added,
        # fit against the SAME rs/l/cox/rsub/csub/cs already established
        # above (only rp_eddy/lp_eddy float here).
        rp_eddy, lp_eddy, _opt_result_eddy = fit_eddy_branch(
            freqs, y11, rs=rs_half, l=l_half, cox=cox_total_f / 4, rsub=rsub, csub=csub, cs=0.0)
    else:
        l_half = _PLACEHOLDER_L_HALF_H
        rs_half = _PLACEHOLDER_RS_HALF_OHM
        rsub = rsub_geom
        csub = _PLACEHOLDER_CSUB_F
        # No real EM data to fit rp_eddy/lp_eddy from at all -- rp_eddy set
        # huge (effectively an open circuit at any swept frequency) makes
        # the parallel branch's own lp_eddy value irrelevant (an
        # open-circuited branch in parallel with `l` can't affect Y11 no
        # matter what its own inductance is), so this is an honest "no
        # eddy effect modeled yet" placeholder, not a fabricated guess.
        rp_eddy = 1e9
        lp_eddy = l_half

    return {
        "l": l_half,
        "rs": rs_half,
        # (b) cox 3-way trapezoidal split: each outer terminal 'owns' 1/4 of
        # the trace's total oxide-coupling area, 'ct' owns the other 1/2
        # (both adjoining halves' near sides) -- was a straight 1/2-1/2
        # split before 'ct' had its own tap at all.
        "cox": cox_total_f / 4,
        "rsub": rsub,
        "csub": csub,
        # (e) no physical adjacent-turn coupling mechanism for a single-turn
        # loop -- see this function's own docstring point 3.
        "cs": 0.0,
        "cox_ct": cox_total_f / 2,
        "rsub_ct": rsub_ct_geom,
        # csub_ct is NOT independently EM-fittable (see docstring) --
        # propagated from the fitted/placeholder outer csub by the same 2x
        # area ratio as cox_ct/rsub_ct above.
        "csub_ct": 2 * csub,
        "rp_eddy": rp_eddy,
        "lp_eddy": lp_eddy,
    }
