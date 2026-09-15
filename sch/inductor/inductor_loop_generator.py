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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


_STACK_PATH = os.path.join(os.path.dirname(__file__), "gf180mcu_stack.json")

# Same generic placeholder-quality constants as inductor_spiral_generator.py
# (see that module's own docstring for why) -- kept as separate literals
# here (not a shared import) so this generator stays self-contained, same
# "no bespoke cross-file coupling" spirit already documented there.
_PLACEHOLDER_L_HALF_H = 2.895e-9
_PLACEHOLDER_RS_HALF_OHM = 1.7645
_PLACEHOLDER_CSUB_F = 103.1e-15
_PLACEHOLDER_CS_F = 103.1e-15

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
    no crossunder."""
    with open(path) as f:
        stack = json.load(f)
    m5 = stack["metal5"]
    sub = stack["substrate"]
    return {
        "metal5_sheet_r_ohm_per_sq": m5["sheet_resistance_ohm_per_sq"][corner],
        "metal5_thickness_m": m5["thickness_m"]["value"],
        "metal5_z_start_m": m5["z_start_m"]["value"],
        "metal5_areacap_aF_per_um2": m5["areacap_to_substrate_aF_per_um2"][corner],
        "oxide_epsilon_r": stack["oxide"]["epsilon_r"],
        "substrate_epsilon_r": sub["epsilon_r"],
        "substrate_resistivity_ohm_cm": sub["resistivity_ohm_cm"]["value"],
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
    """PDK/model-specific: returns {'l', 'rs', 'cox', 'rsub', 'csub', 'cs'}
    (SI base units: H, ohm, F) -- same 6 names, same per-half convention, and
    same em_result=None (fast placeholder path) vs em_result=dict (real-FDTD
    path, low-frequency Y11 slope fit) split as
    inductor_spiral_generator.py's own fit_electrical_params() -- see that
    function's docstring for the full rationale, identical here."""
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
    cox_total_f = trace_area_um2 * stack["metal5_areacap_aF_per_um2"] * 1e-18

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
    else:
        l_half = _PLACEHOLDER_L_HALF_H
        rs_half = _PLACEHOLDER_RS_HALF_OHM

    return {
        "l": l_half,
        "rs": rs_half,
        "cox": cox_total_f / 2,
        "rsub": stack["substrate_resistivity_ohm_cm"],  # placeholder-quality, see gf180mcu_stack.json
        "csub": _PLACEHOLDER_CSUB_F,
        "cs": _PLACEHOLDER_CS_F,
    }
