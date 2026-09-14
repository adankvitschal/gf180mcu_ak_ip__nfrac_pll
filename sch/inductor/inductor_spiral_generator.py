"""Parametric octagonal-spiral inductor generator: geometry parameters
(inner radius, turns, spacing, track width) -> a real 3D FDTD extraction
via openEMS/CSXCAD, run against GF180MCU's actual Metal5/oxide stack (see
gf180mcu_stack.json) -> the 6 electrical parameters (l, rs, cox, rsub,
csub, cs) that sch/inductor/inductor_spiral.sch's own 'name' placeholder
tokens substitute in, via this project's normal materialization mechanism
(substitute_params()) -- same as every other topology, no bespoke .sch
writing here.

This is the "generator" referenced by config.json's
blocks.inductor.topologies.spiral -- dynamically loaded (by file path,
importlib.util.spec_from_file_location) from mh-analog-designer's
run_sim.py, both host-side (resolve_generator_params(), the fast
no-FDTD path used at materialization time and for GUI display) and
in-container (analog_designer_core's openems_generator_runner.py, which
does the actual FDTD run and then calls fit_electrical_params() again
with a real em_result). This module deliberately has NO run/CLI/main()
of its own -- only the two functions below that are genuinely dynamic/
project-specific (geometry -> openEMS structure, and openEMS result ->
electrical parameters); the "run this in a container, cache it, dispatch
into openEMS" mechanics live in analog_designer_core, reusable by any
future openEMS-backed generator, not just this one.

Physical simplifications (v1, documented rather than hidden):
- Single Metal5 layer only, no inner-terminal underpass/via-stack routing
  out to an external pad -- the inner terminus 'a' is contacted directly at
  its own tip, which is enough for a one-port Y11 EM characterization but
  is NOT a manufacturable layout (a real layout needs a lower-metal
  crossunder to bring 'a' out from the spiral's own center -- deferred, see
  below).
- Both ports are PLANAR/in-line -- a small box bridging directly into the
  Metal5 ribbon at each terminus (z-range z_ox_top..z_m5_top only, current
  flowing along the trace's own local direction), port 'a' driven, port 'b'
  a plain near-short (R=1e-6) -- NOT vertical stubs down to the substrate
  (an earlier version was, and that was a real, confirmed bug: a small
  point contact into the moderately lossy substrate creates ~30-40 kOhm of
  ordinary electrostatic spreading/constriction resistance on its own --
  confirmed with a standalone Laplace-equation check, no FDTD needed --
  which completely swamped the real ~ohm-scale trace resistance being
  measured. Full writeup in the openems_inductor_status.md project memory).
  Validated first on a standalone closed-loop test (single planar port,
  extracted R within 5% of the analytic expectation) before being applied
  here.
  Caveat: AddLumpedPort's box is axis-aligned, but the octagonal spiral's
  terminus tangent can point along any of 8 discrete angles -- each port's
  direction is chosen as whichever in-plane axis (x or y) the local tangent
  has the larger component along, which is only exactly aligned 2 times out
  of 8 (the other 6 are a bounded, ~45-degree-worst-case approximation, not
  the orders-of-magnitude substrate-contact artifact it replaces). A true
  arbitrary-angle port would need a CSTransform rotation on the port box --
  not implemented in this v1.
- No center tap, no differential/two-winding coupling modeled at all here
  -- this is a single continuous spiral, one-port Y11 characterization of
  its own series impedance end to end (matches how
  github.com/VolkerMuehlhaus/openems_ihp_sg13g2's run_inductor_diffport.py
  reference workflow separates concerns: differential L/Q doesn't need a
  live center-tap port in the same simulation). A genuine center-tapped,
  mutually-coupled two-half-winding structure -- needing a lower-metal
  crossunder + via to bring the tap out without shorting to the turns it
  passes under -- is a separate, deliberately deferred future extension
  (see openems_inductor_status.md's "Step 3" note). 'rsub'/'csub'/'cs' in
  the pi-model are NOT derived from this EM run at all (this one-port
  methodology has no distinct 'ct' measurement to derive 'cs' from, and
  no substrate-impedance measurement to derive 'rsub'/'csub' from) --
  they're placeholder-quality constants, clearly logged as such in
  fit_electrical_params()'s own docstring. Deriving them for real is
  next-round work, not this refactor's job.

Known open issue (as of this writing, see openems_inductor_status.md):
Q(f) extracted from the crossunder-bridged spiral topology comes out
negative and capacitance-like (unlike the simple closed-loop validation
test, which matched its analytic R within 5%) -- still under
investigation, most likely either a genuine parasitic shunt-C path through
the Metal4 crossunder/via4 dominating this small geometry's own series L,
or a second sign/axis bug specific to the crossunder-adjacent bridging
port. Don't trust this generator's absolute L/Q/SRF numbers until that's
resolved. This refactor does not touch that investigation at all -- the
exact same run/extraction logic (conjugate sign-fix included) just now
lives in analog_designer_core's openems_generator_runner.py instead of
in this module's own (now-removed) run_and_extract().
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


_STACK_PATH = os.path.join(os.path.dirname(__file__), "gf180mcu_stack.json")

# Placeholder-quality electrical constants used whenever a real EM result
# isn't available (or, for rsub/csub/cs, ALWAYS -- see fit_electrical_params()
# and the module docstring's "Physical simplifications" section for why).
# l/rs values carried over from inductor_placeholder_rlc.sch's own generic
# sky130-derived per-half defaults (2.895nH / 1.7645ohm). csub/cs reuse the
# old placeholder_rlc topology's own ind_ccross magnitude (103.1fF) as a
# plausible order-of-magnitude stand-in -- arbitrary, not derived, revisit
# when a real center-tap-aware EM methodology exists.
_PLACEHOLDER_L_HALF_H = 2.895e-9
_PLACEHOLDER_RS_HALF_OHM = 1.7645
_PLACEHOLDER_CSUB_F = 103.1e-15
_PLACEHOLDER_CS_F = 103.1e-15


def load_stack(corner="tt", path=_STACK_PATH):
    with open(path) as f:
        stack = json.load(f)
    m5 = stack["metal5"]
    sub = stack["substrate"]
    m4 = stack.get("metal4")
    via4 = stack.get("via4")
    result = {
        "metal5_sheet_r_ohm_per_sq": m5["sheet_resistance_ohm_per_sq"][corner],
        "metal5_thickness_m": m5["thickness_m"]["value"],
        "metal5_z_start_m": m5["z_start_m"]["value"],
        "metal5_areacap_aF_per_um2": m5["areacap_to_substrate_aF_per_um2"][corner],
        "oxide_epsilon_r": stack["oxide"]["epsilon_r"],
        "substrate_epsilon_r": sub["epsilon_r"],
        "substrate_resistivity_ohm_cm": sub["resistivity_ohm_cm"]["value"],
    }
    if m4 is not None:
        result["metal4_sheet_r_ohm_per_sq"] = m4["sheet_resistance_ohm_per_sq"][corner]
        result["metal4_thickness_m"] = m4["thickness_m"]["value"]
        result["metal4_z_start_m"] = m4["z_start_m"]["value"]
    if via4 is not None:
        result["via4_min_width_m"] = via4["min_width_m"]["value"]
    return result


def geometry_from_params(params):
    """Extracts/type-casts this topology's 4 free geometric parameters out
    of a raw {name: "spice-value-string-or-number"} params dict (e.g. a
    variation's own resolved free parameters, or config.json's own
    defaults) into the typed dict every other function in this module
    expects. This is the ONLY place that knows this topology's own free
    parameter names -- callers (resolve_generator_params() host-side,
    openems_generator_runner.py in-container) never hardcode them."""
    return {
        "inner_radius_um": float(params["inner_radius_um"]),
        "n_turns": int(float(params["n_turns"])),
        "track_width_um": float(params["track_width_um"]),
        "spacing_um": float(params["spacing_um"]),
    }


def octagonal_spiral_centerline(inner_radius_um, n_turns, track_width_um, spacing_um, points_per_turn=8):
    """Centerline vertices of an octagonal spiral: sample an Archimedean
    spiral r(theta) = inner_radius + pitch*theta/(2*pi) at 8 angles per
    turn -- connecting those samples with straight lines is what actually
    produces the classic faceted octagonal-spiral shape (a real circular
    spiral would need far more points per turn; 8 is what makes it
    octagonal, matching real spiral-inductor layouts).

    TODO (queued, not yet done): theta starts at 0, so every vertex sits
    exactly on an axis angle (0, 45, 90, ...deg) -- which means EVERY edge
    is a 45deg-ish diagonal chord between two such vertices, none axis-
    aligned. Phase-shifting the sample by half a step (theta0 =
    pi/points_per_turn) would instead put vertices at 22.5, 67.5, ...deg,
    making alternating edges land exactly horizontal/vertical (the
    classic flat-topped/flat-sided octagon real layouts use) -- Cartesian
    FDTD mesh lines can then anchor directly along those runs instead of
    staircasing every single edge, which should meaningfully help mesh
    efficiency/convergence. Flagged during the substrate-spreading-
    resistance debugging session (see openems_inductor_status.md);
    deliberately not implemented yet since it's independent of that bug
    fix."""
    pitch = track_width_um + spacing_um
    n_points = n_turns * points_per_turn + 1
    pts = []
    for k in range(n_points):
        theta = k * (2 * math.pi / points_per_turn)
        r = inner_radius_um + pitch * theta / (2 * math.pi)
        pts.append((r * math.cos(theta), r * math.sin(theta)))
    return pts


def _unit(dx, dy):
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def spiral_ribbon_polygon(centerline, width_um):
    """Single continuous ribbon polygon around the centerline, with a
    proper mitered offset at each interior vertex -- replaces an earlier
    v1 that offset each segment independently and extended it by width/2
    past both endpoints ('sausage-link' capsules) to force overlap at every
    joint. That worked electrically (no gaps) but left small overlapping
    corner artifacts at every one of the octagon's turns -- extra, locally
    non-uniform geometric detail sitting right where FDTD meshing was
    already most sensitive (see build_openems_structure's mesh comments on
    SmoothMeshLines' own worst-case cell-halving behavior).

    A real miter join is cheap here specifically BECAUSE every interior
    turn in this octagonal spiral is exactly 45 degrees (centerline points
    are sampled at a fixed 2*pi/8 angular step, see
    octagonal_spiral_centerline) -- so the miter length has one constant
    closed-form scale factor (1/cos(22.5 deg)) rather than needing a
    general per-corner miter solve valid for an arbitrary turn angle.
    """
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
    min_spacing to the previously kept one -- see build_openems_structure's
    mesh comment for why two independently-generated anchors landing a
    fraction of a micron apart matters (it silently becomes the FDTD's
    smallest cell, and thus its CFL-limited timestep, however coarse every
    other anchor's own spacing is)."""
    ordered = sorted(values)
    merged = [ordered[0]]
    for v in ordered[1:]:
        if v - merged[-1] >= min_spacing:
            merged.append(v)
    return merged


def crossunder_path(start_xy, target_xy, target_tangent, gap_um):
    """Straight-line route (in um) for a crossunder from `start_xy` (the
    spiral's own inner terminus 'a' -- trapped inside the winding) out to a
    point ADJACENT to `target_xy` (terminus 'b'), offset by `gap_um` along
    `target_tangent` -- i.e. continuing straight past 'b's own tip by a
    small gap, the same "gap cut into an open trace end" pattern already
    validated elsewhere in this project (the closed-loop and differential-
    hairpin diagnostic scripts), rather than landing exactly on top of 'b'.

    This is the point of the crossunder: bringing 'a' and 'b' physically
    ADJACENT (not just electrically connected) means a SINGLE small lumped
    port can bridge directly between them -- exactly how
    github.com/VolkerMuehlhaus/openems_ihp_sg13g2's run_inductor_diffport.py
    measures a real spiral inductor, instead of this generator's earlier
    two-separate-far-apart-ports approach (port 'a' driven at the spiral's
    own inner terminus, port 'b' a near-short far away at the outer one).

    gap_um should be the SAME value used as port_len for the bridging port
    itself (see build_openems_structure) -- the crossunder's exit offset
    and the port's own gap are the same physical gap, not two independent
    quantities that could accidentally disagree.

    This generator's octagonal spiral always completes a whole number of
    turns (centerline has n_turns*8+1 points sampled every 2*pi/8), so 'a'
    (the first centerline point) and 'b' (the last) land at the SAME angle
    -- the long crossunder run from start_xy to near target_xy is close to
    purely radial, passing underneath 'b' along most of its own length,
    which is fine: Metal4 is a physically separate z-layer, no shorting
    risk. The Metal4 trace's own polygon uses the overall start->exit
    direction (see add_crossunder), which won't be EXACTLY target_tangent
    if 'a' sits at a different local angle than 'b' -- a small, bounded v1
    approximation (the via4 blocks and the final port itself are unaffected
    by it; only the trace polygon's exact orientation is)."""
    exit_xy = (target_xy[0] + target_tangent[0] * gap_um, target_xy[1] + target_tangent[1] * gap_um)
    return start_xy, exit_xy


def add_crossunder(CSX, stack, unit, start_xy, exit_xy, track_width_um, z_ox_top):
    """Routes a center-tap-style connection from `start_xy` (assumed to sit
    on Metal5, e.g. the spiral's own inner terminus) out to `exit_xy`
    (outside the winding) via a Metal4 crossunder underneath the spiral's
    own turns -- Metal4 is a physically separate layer/z-range from Metal5,
    so it passes under any number of turns with no risk of shorting to them
    (that's the entire point of a crossunder; no explicit clearance check
    against the spiral geometry is needed here for that reason). Returns
    (metal5_exit_xy, tangent) -- a NEW Metal5 stub's tip at exit_xy, with
    `tangent` the crossunder's own direction there, in the same (xy, unit
    tangent) convention build_openems_structure() already uses for its
    'a'/'b' ports, so a planar port can attach there exactly the same way.

    v1 simplification (documented, not hidden): the Metal4-Metal5
    connection at each end is modeled as a SOLID conductive block spanning
    the via4 gap, not a discrete via array -- see gf180mcu_stack.json's
    via4.modeling_note for why (real per-via contact resistance data was
    ambiguous in the PDK tech file; a solid block is expected to
    UNDERESTIMATE the crossunder's own resistance somewhat, a bounded,
    documented approximation, not an orders-of-magnitude artifact like the
    substrate-contact bug this whole port mechanism was rebuilt to avoid)."""
    half_w = track_width_um / 2
    m4_z0 = stack["metal4_z_start_m"] / unit
    m4_z1 = m4_z0 + stack["metal4_thickness_m"] / unit
    m4_sigma = 1.0 / (stack["metal4_sheet_r_ohm_per_sq"] * stack["metal4_thickness_m"])

    tangent = _unit(exit_xy[0] - start_xy[0], exit_xy[1] - start_xy[1])

    metal4 = CSX.AddMaterial("metal4", kappa=m4_sigma)
    # Metal4 trace: a plain axis-independent rectangle along the start->exit
    # line (the crossunder route is a single straight radial line by
    # construction -- see crossunder_path -- so a mitered polygon like
    # spiral_ribbon_polygon's isn't needed here, there are no interior
    # turns to miter).
    nx, ny = -tangent[1], tangent[0]
    trace_poly_x = [start_xy[0] + nx * half_w, exit_xy[0] + nx * half_w,
                     exit_xy[0] - nx * half_w, start_xy[0] - nx * half_w]
    trace_poly_y = [start_xy[1] + ny * half_w, exit_xy[1] + ny * half_w,
                     exit_xy[1] - ny * half_w, start_xy[1] - ny * half_w]
    # priority=5: this trace's z-range sits ENTIRELY INSIDE the oxide
    # material's own z=[0,z_ox_top] box (a real volumetric overlap, unlike
    # metal5's -- which only ever touches the oxide at a shared z-plane,
    # never overlaps it). Without an explicit higher priority than oxide's
    # default, CSXCAD silently let the earlier-added oxide claim those
    # voxels ("Unused primitive (type: LinPoly) detected in property:
    # metal4!" at startup -- the whole crossunder trace was a no-op,
    # confirmed by inspecting the log's first ~20s before committing to a
    # full run, not discovered after hours). Matches the MSL_NotchFilter.py
    # reference example's own use of priority=10 for its PEC box for the
    # same reason.
    metal4.AddLinPoly([trace_poly_x, trace_poly_y], "z", m4_z0, m4_z1 - m4_z0, priority=5)

    # via4 blocks: solid conductive fill from Metal4's own top face up to
    # Metal5's own bottom face (z_ox_top, passed in from
    # build_openems_structure -- same value used for the spiral's own
    # Metal5 AddLinPoly's z-start) at each endpoint, square footprint (one
    # track_width per side, same overlap-guarantee reasoning as this
    # generator's port boxes).
    via4 = CSX.AddMaterial("via4", kappa=m4_sigma)  # via4 modeled with metal4's own conductivity (a solid block, not a separate tungsten-plug material -- v1 simplification, see docstring above)
    for xy in (start_xy, exit_xy):
        # priority=5: same oxide-overlap reasoning as the Metal4 trace above
        # (this box's whole z-range, m4_z1..z_ox_top, sits inside oxide's).
        via4.AddBox([xy[0] - half_w, xy[1] - half_w, m4_z1], [xy[0] + half_w, xy[1] + half_w, z_ox_top], priority=5)

    return exit_xy, tangent


# Fixed dump-property name openems_generator_runner.py looks for after
# FDTD.Run() -- openEMS writes a frequency-domain dump's output as
# "<name>.h5" inside the FDTD working directory (confirmed empirically
# with a minimal standalone probe run, not this generator's own full
# spiral -- see add_field_dump()'s own docstring for the exact HDF5
# layout found). A shared module-level constant (not a hardcoded string
# in two places) so the generator and the generic runner can't drift out
# of sync on the name.
FIELD_DUMP_NAME = "field_dump"


def add_field_dump(CSX, box, z_ox_top, z_m5_top, dump_freq_hz):
    """Adds a frequency-domain TOTAL CURRENT DENSITY dump (dump_type=13,
    file_type=1/HDF5 -- both confirmed valid via CSXCAD's own
    GetDumpType()/GetFileType() round-trip on a live CSPropDumpBox, not
    just assumed from memory) as a box spanning Metal5's own z-range
    (z_ox_top..z_m5_top), covering the full mesh footprint in x/y -- lets
    analog_designer_core's generic runner render a current-concentration
    PNG after FDTD.Run(), independent of which PDK/geometry produced the
    structure (the RENDERING code is generic; only this box's placement
    is geometry-specific, hence it lives here).

    dump_freq_hz: which frequency to accumulate the DFT at during the
    time-domain run -- build_openems_structure() passes its own Gaussian
    excitation's center frequency (f0), a reasonable single "operating
    point" snapshot; openEMS supports dumping at more than one frequency
    (AddFrequency() can be called repeatedly) if a future caller wants a
    sweep of current-density snapshots instead of just one.

    UNVERIFIED beyond the minimal probe run: confirmed the dump box/
    frequency setup and the resulting HDF5 group/dataset names
    (FieldData/FD/f0_real, FieldData/FD/f0_imag, shape (3, nz, ny, nx);
    Mesh/x, Mesh/y, Mesh/z) on a trivial single-bar structure -- NOT yet
    confirmed against this generator's own real spiral geometry (more
    mesh lines, the crossunder, an actual multi-hour run). If the real
    run's dump looks wrong/empty, check this box's z-range actually
    overlaps real z mesh lines from the spiral's own SmoothMeshLines("z", ...)
    calls in build_openems_structure() first."""
    dump = CSX.AddDump(FIELD_DUMP_NAME, dump_type=13, file_type=1)
    dump.AddFrequency(dump_freq_hz)
    dump.AddBox([-box, -box, z_ox_top], [box, box, z_m5_top])


def save_layout_preview(centerline, track_width_um, path):
    """Top-view PNG of the generated spiral, independent of CSXCAD/openEMS
    -- plotted straight from the same ribbon polygon fed to AddLinPoly, so
    it shows exactly what the FDTD solver will see. Written without needing
    QCSXCAD/AppCSXCAD (dropped from the build -- Qt4 is EOL on Rocky 8 and
    unneeded for this headless flow, see eda-env's docker/openems/install.sh)."""
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


def build_openems_structure(geometry, stack, f_max_hz, dump_field=False):
    """PDK/geometry-specific: builds the CSXCAD/openEMS structure (metal5
    spiral, metal4 crossunder + via4, oxide, substrate, mesh, one excited
    LumpedPort) and returns (FDTD, port) -- everything analog_designer_core's
    generic openems_generator_runner.py needs to call `FDTD.Run(...)` /
    `port.CalcPort(...)` itself. This function does NOT run the simulation
    or extract anything from it -- that's the generic runner's job, kept
    out of this module on purpose (see module docstring).

    dump_field=True also adds a frequency-domain current-density dump box
    (see add_field_dump()), at the excitation's own center frequency, so
    the generic runner can render a current-concentration PNG after
    FDTD.Run() -- the dump BOX itself (where, over what footprint) is
    PDK/geometry-specific, hence defined here rather than in the generic
    runner; reading the resulting HDF5 file and rendering a PNG from it is
    NOT geometry-specific, so that part lives in
    openems_generator_runner.py instead.

    Import of CSXCAD/openEMS is deferred to this function so that every
    OTHER function in this module (geometry math, save_layout_preview(),
    fit_electrical_params()'s placeholder path) stays usable even outside
    the eda-env-designer container (none of them need CSXCAD/openEMS)."""
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    unit = 1e-6  # coordinates in um, matching the geometry parameters' own unit
    inner_radius = geometry["inner_radius_um"]
    n_turns = geometry["n_turns"]
    track_width = geometry["track_width_um"]
    spacing = geometry["spacing_um"]

    centerline = octagonal_spiral_centerline(inner_radius, n_turns, track_width, spacing)
    outer_radius = inner_radius + (track_width + spacing) * n_turns
    half_w = track_width / 2
    # Shifted half_w INWARD from each raw endpoint, along the local trace
    # direction, rather than centering the port box exactly ON the tip:
    # a port box centered at a bare endpoint has HALF its (x,y) footprint
    # sitting over bare oxide (no conductor there at all), so the
    # Ampere's-law current-loop probe -- and the port's own resistor/
    # excitation element, which overwrites whatever material previously
    # occupied its box -- only ever see half a conductor. Confirmed via a
    # mesh+geometry-only plot (no FDTD run needed) on a straight test bar
    # using this same port mechanism: extracted DC resistance came out
    # ~25,000-64,000x too high (should be ~2 ohm, came out ~50-127 kOhm)
    # until the port was moved fully onto the conductor.
    a_dx, a_dy = _unit(centerline[1][0] - centerline[0][0], centerline[1][1] - centerline[0][1])
    a_xy = (centerline[0][0] + a_dx * half_w, centerline[0][1] + a_dy * half_w)
    b_dx, b_dy = _unit(centerline[-1][0] - centerline[-2][0], centerline[-1][1] - centerline[-2][1])
    b_xy = (centerline[-1][0] - b_dx * half_w, centerline[-1][1] - b_dy * half_w)

    # res_xy computed here (duplicated below, right before it's used for
    # mesh anchoring) because port_len MUST be tied to it: a first attempt
    # used a fixed port_len=0.5um independent of mesh resolution, and for
    # any geometry coarser than that (e.g. track_width=5um here gives
    # res_xy=2.5um), _merge_close_lines' own min_spacing=res_xy silently
    # merged the port's two boundary anchors into a single line -- collapsing
    # the port to zero length on the actual discretized mesh. openEMS caught
    # it cleanly ("Lumped Element with zero (snapped) length is invalid!
    # skipping", "Unused primitive", "CalcVoltageIntegral: only a 1D/line
    # integration is allowed") rather than silently giving a wrong number,
    # but it would have run for hours before saying so. Tying port_len to
    # res_xy with a safety margin (not just port_len<=res_xy) guarantees it
    # survives that same merge by construction, for any geometry.
    #
    # res_xy MUST also account for `spacing` (the gap between adjacent
    # turns), not just track_width: an earlier version used
    # max(track_width/2, 0.4) alone, which for a tightly-wound spiral where
    # spacing < track_width/2 (e.g. this generator's own default test
    # geometry, track_width=5um/spacing=2um -> res_xy=2.5um > the 2um gap
    # itself) can leave the mesh coarser than the actual gap between turns
    # -- confirmed as the likely root cause of a real instability (FDTD
    # energy diverging to literal inf/NaN over ~137k timesteps, not just a
    # wrong answer) on exactly that test geometry: a mesh cell wider than
    # the gap between two adjacent turns risks discretizing them as
    # touching/shorted, an severely unphysical structure. Using the
    # SMALLER of track_width/2 and spacing/2 guarantees the gap itself
    # gets at least one full resolution step.
    res_xy = max(min(track_width, spacing) / 2, 0.4)
    port_len = max(res_xy * 1.5, min(0.5, half_w))
    excite_v_per_m = 10.0 / (port_len * unit)

    # Bring 'a' physically ADJACENT to 'b' via a Metal4 crossunder underneath
    # the spiral's own turns, instead of leaving the two ports far apart on
    # opposite sides of the winding -- so a SINGLE small lumped port can
    # bridge directly between them (matching
    # github.com/VolkerMuehlhaus/openems_ihp_sg13g2's run_inductor_diffport.py
    # reference technique), rather than needing two separate ports (one
    # driven far away at the true inner terminus, one a near-short at the
    # outer one) the way this generator did before. gap_um=port_len: the
    # crossunder's own exit offset from 'b' IS the port's own bridging gap,
    # not two independently-chosen quantities that could disagree. See
    # crossunder_path()'s docstring for why this ends up close to purely
    # radial (this spiral always completes whole turns, so 'a' and 'b'
    # already sit at the same angle) and add_crossunder()'s for the via4/
    # Metal4 geometry itself.
    _, a_exit_xy = crossunder_path(a_xy, b_xy, (b_dx, b_dy), port_len)
    port_dir = "x" if abs(b_dx) >= abs(b_dy) else "y"
    if port_dir == "x":
        p_x0, p_x1 = sorted([b_xy[0], a_exit_xy[0]])
        p_y_mid = (b_xy[1] + a_exit_xy[1]) / 2
        port_p0_xy, port_p1_xy = (p_x0, p_y_mid - half_w), (p_x1, p_y_mid + half_w)
    else:
        p_y0, p_y1 = sorted([b_xy[1], a_exit_xy[1]])
        p_x_mid = (b_xy[0] + a_exit_xy[0]) / 2
        port_p0_xy, port_p1_xy = (p_x_mid - half_w, p_y0), (p_x_mid + half_w, p_y1)

    metal5_sigma = 1.0 / (stack["metal5_sheet_r_ohm_per_sq"] * stack["metal5_thickness_m"])
    substrate_sigma = 1.0 / (stack["substrate_resistivity_ohm_cm"] * 1e-2)
    z_ox_top = stack["metal5_z_start_m"] / unit
    z_m5_top = z_ox_top + stack["metal5_thickness_m"] / unit

    f0 = f_max_hz / 2
    fc = f_max_hz / 2
    FDTD = openEMS(EndCriteria=1e-4)
    FDTD.SetGaussExcite(f0, fc)
    FDTD.SetBoundaryCond(["PML_8", "PML_8", "PML_8", "PML_8", "PML_8", "PML_8"])

    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(unit)

    # Manual mesh: fine (fraction of track width) ONLY near the spiral's own
    # conductor -- anchored by a line at every centerline vertex's x/y, the
    # same way MSL_NotchFilter.py anchors lines at its trace edges -- then
    # SmoothMeshLines grades outward from those anchors toward the domain
    # boundary. Without anchors actually AT the geometry, SmoothMeshLines
    # has nothing nearby to refine around and (confirmed the hard way, see
    # the inductor generator plan's Phase 4 notes) ends up applying near-
    # uniform fine resolution across the WHOLE domain instead of just the
    # spiral's own annulus -- an OOM in practice, not just "slow": a first
    # attempt with only the two outer boundary lines as anchors exhausted a
    # 6GB container limit and 8 CPUs pinned at 100% before ever finishing
    # mesh setup, for a domain that should be extremely cheap by FDTD
    # standards (on-chip dimensions, geometry-limited not wavelength-limited
    # resolution -- even 20GHz's free-space lambda/20 is ~380um, far coarser
    # than the few-um features here).
    # Also merge/dedup anchors closer together than res_xy itself: an
    # octagonal spiral's own centerline (25+ points, 8 angles repeating
    # every turn at growing radius) plus each port's +-half_w corner
    # offsets easily produces two anchors a fraction of a micron apart
    # purely by coincidence. SmoothMeshLines leaves whatever gap already
    # exists between two anchors as its own single cell without
    # subdividing it further -- an unnoticed sub-0.2um gap like that was
    # the actual root cause of a first attempt's "timestep seems to be
    # very small" warning and a ~3.3e-16s CFL timestep (860k+ steps just
    # to cover the excitation pulse), even though the geometry parameters
    # themselves only called for ~0.3um resolution.
    # track_width/2 (not /3 or /4): SmoothMeshLines occasionally has to
    # close a gap between two anchors that isn't an exact multiple of
    # res_xy by inserting one extra line at the remaining half-step --
    # confirmed via a mesh-only diagnostic (no FDTD run) that this can
    # locally halve the smallest cell (e.g. 0.333um target -> a real
    # 0.167um worst-case cell), which alone roughly doubles the CFL
    # timestep's step count for the whole run. A coarser starting target
    # keeps that same worst-case halving from ever getting fine enough to
    # dominate the timestep -- a deliberate v1 accuracy/runtime trade-off,
    # not a claim that this is the final right resolution for production
    # numbers.
    # (res_xy itself computed earlier, alongside port_len -- see that comment)
    # Anchors: the bridging port's own box (port_p0_xy/port_p1_xy) -- same
    # "mesh line EXACTLY at the port's real edges" reasoning as before --
    # plus 'a' (where the crossunder's via4 drops down to Metal4) and
    # a_exit_xy (where it comes back up, right at the port's own other
    # face, already covered by port_p0_xy/port_p1_xy but listed for clarity).
    port_xs = [port_p0_xy[0], port_p1_xy[0], a_xy[0]]
    port_ys = [port_p0_xy[1], port_p1_xy[1], a_xy[1]]
    xs = _merge_close_lines([p[0] for p in centerline] + port_xs, res_xy)
    ys = _merge_close_lines([p[1] for p in centerline] + port_ys, res_xy)
    box = outer_radius + 6 * track_width
    mesh.AddLine("x", xs + [-box, box])
    mesh.AddLine("y", ys + [-box, box])
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

    metal5 = CSX.AddMaterial("metal5", kappa=metal5_sigma)
    ribbon = spiral_ribbon_polygon(centerline, track_width)
    metal5.AddLinPoly([[p[0] for p in ribbon], [p[1] for p in ribbon]], "z", z_ox_top, z_m5_top - z_ox_top)

    # Crossunder: routes 'a' (the spiral's own inner terminus, trapped
    # inside the winding) underneath all the turns via Metal4, out to
    # a_exit_xy -- physically ADJACENT to 'b' (see a_exit_xy's computation
    # above). See add_crossunder()'s own docstring for the via4/Metal4
    # geometry and its v1 simplifications.
    add_crossunder(CSX, stack, unit, a_xy, a_exit_xy, track_width, z_ox_top)

    # ONE planar (in-line) lumped port bridging directly between 'b' and
    # the crossunder's new adjacent terminal -- not two separate far-apart
    # ports (an earlier version's design) -- matching
    # github.com/VolkerMuehlhaus/openems_ihp_sg13g2's run_inductor_diffport.py
    # reference technique now that the crossunder has brought the two
    # terminals physically together. Box/direction computed earlier
    # (before the mesh section) so its anchors line up exactly with these
    # edges. z-range z_ox_top..z_m5_top only -- NOT a vertical stub down to
    # the substrate. See the module docstring's "Physical simplifications"
    # section for why (a confirmed ~30-40 kOhm substrate-contact modeling
    # artifact, eliminated by never touching the substrate at all).
    # excite scaled to a fixed ~10V-equivalent regardless of port_len
    # (division by a large-relative-to-Re(Y11) noise floor was exactly what
    # turned Re(Ydiff) into garbage on an unrelated differential-hairpin
    # test this same session; keeping the excitation well above the
    # floating-point noise floor avoids repeating that).
    port_a = FDTD.AddLumpedPort(
        1, 50, [port_p0_xy[0], port_p0_xy[1], z_ox_top], [port_p1_xy[0], port_p1_xy[1], z_m5_top],
        port_dir, excite=excite_v_per_m)

    if dump_field:
        add_field_dump(CSX, box, z_ox_top, z_m5_top, f0)

    return FDTD, port_a


def fit_electrical_params(geometry, stack, em_result=None):
    """PDK/model-specific: returns {'l', 'rs', 'cox', 'rsub', 'csub', 'cs'}
    (SI base units: H, ohm, F) -- the exact 6 names
    sch/inductor/inductor_spiral.sch's 'name' tokens substitute (each
    appearing on BOTH halves of the two-half-winding template, e.g. L1 and
    L2 both get the same 'l' -- this returns the PER-HALF value, same
    convention the old ind_l_half/ind_rs_half naming already used, so the
    template's two series inductors/resistors sum to the real total).

    em_result=None (the fast, no-FDTD path -- used by
    resolve_generator_params() at materialization time, by the GUI's live
    Parameters-panel display, and by ANALOG_DESIGNER_OPENEMS_PLACEHOLDER):
    'cox' is still computed for REAL (pure geometry x real GF180MCU
    areacap data, cheap, no FDTD needed); 'l'/'rs' fall back to this
    module's own generic placeholder constants (carried over from
    inductor_placeholder_rlc.sch's own defaults); 'rsub'/'csub'/'cs' are
    ALWAYS placeholder-quality constants in both branches (see module
    docstring's "Physical simplifications" -- this one-port EM methodology
    can't derive them for real yet, that's next-round work).

    em_result=dict (the real-FDTD path -- only ever passed by
    analog_designer_core's openems_generator_runner.py, running inside the
    container, after a real FDTD run -- same {'freqs','y11',...} shape
    this module's own build_openems_structure()+the generic runner's
    FDTD.Run()/CalcPort() produce): 'l'/'rs' are fitted from the
    low-frequency Y11 slope (Y11 ~= 1/(Rs+jwL) dominates there), same math
    as this module's own former fit_pi_model(); 'cox'/'rsub'/'csub'/'cs'
    unchanged from the placeholder branch."""
    centerline = octagonal_spiral_centerline(
        geometry["inner_radius_um"], geometry["n_turns"],
        geometry["track_width_um"], geometry["spacing_um"],
    )
    trace_length_um = sum(
        math.hypot(centerline[i + 1][0] - centerline[i][0], centerline[i + 1][1] - centerline[i][1])
        for i in range(len(centerline) - 1)
    )
    trace_area_um2 = trace_length_um * geometry["track_width_um"]
    cox_total_f = trace_area_um2 * stack["metal5_areacap_aF_per_um2"] * 1e-18

    if em_result is not None:
        import numpy as np

        freqs = em_result["freqs"]
        y11 = em_result["y11"]
        n_fit = max(3, len(freqs) // 20)  # lowest ~5% of the sweep, well below SRF
        w = 2 * np.pi * freqs[:n_fit]
        z11 = 1.0 / y11[:n_fit]
        l_half = float(np.mean(-np.imag(z11) / w)) / 2
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
