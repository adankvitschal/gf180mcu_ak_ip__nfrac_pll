"""Parametric octagonal DIFFERENTIAL spiral inductor generator: geometry
parameters (turns per arm, spacing, track width, inner diameter, tab
length, port spacing) -> a real 3D FDTD extraction via openEMS/CSXCAD
(same contract as inductor_loop_generator.py/inductor_spiral_generator.py)
-> the same 11 electrical parameters (l, rs, cox, rsub, csub, cs, cox_ct,
rsub_ct, csub_ct, rp_eddy, lp_eddy) that sch/inductor/inductor_spiral_diff
.sch's own 'name' tokens substitute in (that .sch is inductor_loop.sch
copied verbatim -- same pi-network template, same reasoning as loop's own
docstring for reusing it).

Why this exists alongside 'spiral'/'loop': the user asked for a layout
that actually looks like a real center-tapped differential inductor (see
the reference photo they attached) rather than 'spiral' (single winding,
no center tap) or 'loop' (single-turn rectangle, not a multi-turn
octagon).

GEOMETRY, in words (see diff_spiral_arms() for the exact math -- this is
the FOURTH topology iteration; see the module's own git history / prior
conversation turns for the three earlier rejected attempts: plain mirror
at the inner end (self-intersected), 180-degree rotation (cancelled
flux), plain mirror at the outer end with a smoothly-varying radius
(flux-correct and collision-light, but every ring looked visibly
"distorted" since its radius drifts continuously instead of staying
constant)):

The winding is a Y-shaped branch. 'ct' sits at a single point on the
OUTERMOST turn's own bottom (x=0, angle=270). TWO arms branch out from
there, each spiralling inward to its own far terminus (P1, P2) near the
center; arm B is the exact mirror image of arm A. Each arm is built from
CONSTANT-RADIUS half-turns (180-degree arcs at one fixed radius, so
every arc looks like a true, undistorted regular-octagon facet run,
fixing the "distorted rings" complaint) connected by explicit radius
STEPS at the two points where the path crosses the x=0 axis (alternating
bottom, top, bottom, top, ... as the arm spirals in) -- each step is a
short vertical segment (in the horizontal, x=0-anchored sense the user
asked for: the flanking arcs stay level/at-radius, only this one short
segment actually changes radius) that moves the winding in by
half_step = pitch/2 (so a full 360-degree turn, i.e. one bottom step AND
one top step, still loses exactly one `pitch` in radius overall, keeping
`n_turns` consistent with every earlier round -- the user's own wording
implied a full `pitch` per step, which would silently double the
winding's density per n_turns; flagged as a deliberate deviation, not
silently applied).

Both arms cross x=0 at every one of those same steps (arm A crossing
just left of it, arm B just right of it -- or vice versa), which is
exactly the self-intersection risk flagged after the previous round's
review (confirmed then to sit near the TOP crossing specifically, for
n_turns above ~1 per arm). The fix, per the user's own description: at
each crossing, ONE of the two arms' step stays on Metal5 (nothing
unusual), while the OTHER dips to Metal4, crosses under, and returns to
Metal5 -- via4 at both ends of the dip -- so the two arms' steps
physically interleave instead of colliding. Which arm dips ALTERNATES
crossing to crossing (arm A dips at even-indexed crossings, arm B at
odd-indexed ones), splitting the extra via/Metal4 resistance evenly
between the two differential sides rather than loading one of them.

All 3 terminals (P1, P2, ct) are ALSO brought out on Metal4 -- see
route_ports() -- via4 straight up from each one's own natural point on
the winding, a vertical riser down to a shared pad row at the bottom,
plus a horizontal jog for whichever terminal isn't already at its own
pad's x.

MEASUREMENT METHODOLOGY (2026-09-17/18, revised -- see spiral_diff_bringup_
_status.md project memory for the full trail): P1/P2/ct are NOT two ends of
one continuous conductor the way 'loop'/'spiral' are (there, the single
winding runs a->...->b with 'ct' just a labeled midpoint tap -- bridging a
gap between a's own pad and b's own pad with one LumpedPort really does
close the ONE real physical loop, current returning the long way around).
Here the winding is a genuine Y-branch: arm A (ct->P1) and arm B (ct->P2)
are two SEPARATE traces that meet only at ct. A single LumpedPort bridging
P1's pad directly to P2's pad (an EARLIER, now-REJECTED version of this
module) does not close that real loop at all -- it adds a brand-new,
much SHORTER artificial path in parallel with the real ct-mediated one, so
most current takes the fake shortcut instead of the real winding, AND
(since it leaves arm B's own far end open) it can never reveal mutual
coupling between the arms in the first place (an open secondary carries no
current by definition, transformer or not).

Fixed via the classical open/short-circuit transformer TEST METHOD instead,
3 separate single-port FDTD runs, selected by a required geometry["variant"]
key (build_openems_structure() raises ValueError if it's missing or
unrecognized -- deliberately no default, so the old invalid P1-to-P2 bridge
can never come back silently):
  "arm_a":   arm A ALONE (arm B genuinely absent from the geometry, not
             just left unconnected), port bridging arm A's own two real
             ends (ct-pad, P1-pad) -- exactly loop's/spiral's own single-
             continuous-2-terminal-winding methodology, just applied to one
             arm. Gives (ra, la), arm A's own end-to-end self-impedance.
             DELIBERATE REFINEMENT over this project's own earlier
             (2026-09-17) planning-session phrasing, "port cut into a gap
             in P1's own riser, ct-side left open": a LumpedPort needs two
             well-defined terminals forming a genuine closed external
             circuit -- a truly dangling, unconnected ct-side dead stub
             gives the port nothing to close the loop through (Y11 would
             then read as an open-stub's own fringe capacitance/self-
             resonance, not the arm's real self-inductance). Bringing ct's
             own riser out to its own pad and using THAT as the port's
             second terminal is the well-posed version of the same intent
             -- current still only has exactly ONE other path between the
             port's two terminals (the whole real arm A winding), so this
             is still a valid single-gap-in-an-otherwise-closed-loop
             measurement, same as loop/spiral, just with the "gap" spanning
             the pad row's own port_spacing_um instead of an adjacent few
             microns -- that distance doesn't change the methodology's
             validity, only its physical size.
  "arm_b":   mirror of "arm_a" -> (rb, lb).
  "shorted": FULL structure (both arms + interleaving, as approved), PLUS
             an added jumper trace physically shorting P2's pad to ct's pad
             (real metal, test-only -- not part of the normal 3-terminal
             device), port bridging (P1-pad, ct-pad) -- same port placement
             as "arm_a". Arm B + the jumper form a closed loop with no
             independent drive, purely mutually coupled to arm A; solving
             the resulting Za_sc(w) against (ra, la, rb, lb) from the other
             two runs gives the mutual inductance m (see pi_model_fit.py's
             fit_mutual_inductance() for the exact derivation and the
             frequency-domain math, and assert_mutual_inductance_recovers_
             synthetic() for a from-scratch numeric proof the fit itself is
             correct, independent of any real FDTD run).
Combining the 3 runs' cached Y11(f) sweeps into a final pi-model fit is NOT
done by this module's own fit_electrical_params() (a single run's em_result
only ever gives ONE variant's data -- not enough on its own) -- see
tools/gf180mcu_spiral_diff_mutual_fit.py, an offline/cache-only combiner in
the same spirit as tools/gf180mcu_inductor_refit.py.

The .sch template (inductor_spiral_diff.sch) now DIVERGES from a verbatim
inductor_loop.sch copy (unlike the earlier plan) -- confirmed with the user
2026-09-18: once a real mutual inductance is measured, a SPICE `K` coupling
statement (via a code.sym block, same convention as inductor_placeholder_
rlc.sch's own raw-SPICE injection) is added between L1/L2, driven by a new
'k_coupling' derived parameter -- see that .sch's own header comment.

No FDTD/CSXCAD run has been made against this module yet -- geometry and
save_layout_preview() are pure-Python/matplotlib and safe to exercise
immediately; build_openems_structure() follows the established contract but
is UNVALIDATED against a real FDTD run -- a structure-only (no FDTD) sanity
check via CSXCAD/mesh inspection is strongly recommended for each variant
before ever starting a real (multi-hour) run.
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
from pi_model_fit import fit_arm_self_impedance  # noqa: E402 (sys.path setup must come first)

_STACK_PATH = os.path.join(_THIS_DIR, "gf180mcu_stack.json")

# Same generic placeholder-quality constants as inductor_loop_generator.py/
# inductor_spiral_generator.py -- kept as separate literals here (not a
# shared import) so this generator stays self-contained, same convention
# loop's own docstring documents.
_PLACEHOLDER_L_HALF_H = 2.895e-9
_PLACEHOLDER_RS_HALF_OHM = 1.7645
_PLACEHOLDER_CSUB_F = 103.1e-15

# Ring-transition (crossing) 3-segment split: horizontal / 45-degree /
# horizontal, as fractions of the crossing's own total length. The
# 45-degree middle leg's ACTUAL length is pinned by how much radius the
# crossing needs to gain (see _arm_a_raw_path()'s own docstring) -- these
# fractions size the total (and hence the two horizontal legs) around
# that, not the other way around.
_TRANSITION_MID_FRAC = 0.30
_TRANSITION_END_FRAC = 0.35

# 2026-09-21: z-domain of the FDTD box (root cause of the long-standing divergence, see
# spiral_diff_bringup_status.md). The old z stack (substrate 12.9um, ~4.8um of air above Metal5,
# uniform fine z cells) made the z-PMLs sit ~3um from the metal and let waves guided in the thin
# substrate slab graze them; energy then grew exponentially, faster the wider the lateral domain
# (an identical plain Metal4 loop diverged with that stack and converged, -41 dB, with the one
# below). SUBSTRATE/AIR are TOTAL extents INCLUDING the z-PML (8 cells of ~Z_FAR_RES_UM each, i.e.
# ~30um per side). z cells are fine only within Z_NEAR_BAND_UM of the metal stack, then graded
# (ratio 1.4) up to Z_FAR_RES_UM -- fine because the wavelength in Si at 20 GHz is ~4 mm.
Z_SUBSTRATE_MIN_UM = 200.0
Z_AIR_MIN_UM = 160.0
Z_NEAR_BAND_UM = 6.0
Z_FAR_RES_UM = 4.0
# The local 5x xy refinement at the riser/ribbon jogs was a workaround that only DELAYED the
# divergence (the jogs were never the cause); off by default, kept for reference.
JOG_MESH_REFINE = False

FIELD_DUMP_NAME = "field_dump"  # fixed name openems_generator_runner.py looks for
FIELD_DUMP_NAMES = {
    "metal5": FIELD_DUMP_NAME,
    "metal4": "field_dump_metal4",
    "via4": "field_dump_via4",
    "substrate": "field_dump_substrate",
}


def load_stack(corner="tt", path=_STACK_PATH):
    """Same fields as inductor_spiral_generator.py's own load_stack()
    (metal5 + metal4 + via4, since this topology has real Metal4 routing)
    plus loop's isosub sheet-resistance field for the rsub geometry
    estimate."""
    with open(path) as f:
        stack = json.load(f)
    m5 = stack["metal5"]
    m4 = stack["metal4"]
    sub = stack["substrate"]
    return {
        "metal5_sheet_r_ohm_per_sq": m5["sheet_resistance_ohm_per_sq"][corner],
        "metal5_thickness_m": m5["thickness_m"]["value"],
        "metal5_z_start_m": m5["z_start_m"]["value"],
        "metal5_areacap_aF_per_um2": m5["areacap_to_substrate_aF_per_um2"][corner],
        "metal5_perimcap_aF_per_um": m5["perimcap_to_substrate_aF_per_um"][corner],
        "metal4_sheet_r_ohm_per_sq": m4["sheet_resistance_ohm_per_sq"][corner],
        "metal4_thickness_m": m4["thickness_m"]["value"],
        "metal4_z_start_m": m4["z_start_m"]["value"],
        "oxide_epsilon_r": stack["oxide"]["epsilon_r"],
        "substrate_epsilon_r": sub["epsilon_r"],
        "substrate_resistivity_ohm_cm": sub["resistivity_ohm_cm"]["value"],
        "substrate_isosub_sheet_r_ohm_per_sq": sub["isosub_sheet_resistance_ohm_per_sq"]["value"],
    }


def geometry_from_params(params):
    """Extracts/type-casts this topology's 6 free geometric parameters --
    the ONLY place that knows this topology's own free parameter names.
    Fails fast if n_turns isn't a whole number of half-turns (each
    half-turn is one constant-radius 180-degree arc, see
    diff_spiral_arms()'s docstring)."""
    n_turns = float(params["n_turns"])
    n_half_laps = round(n_turns * 2)
    if n_half_laps <= 0 or abs(n_turns * 2 - n_half_laps) > 1e-6:
        raise ValueError(
            f"n_turns={n_turns} must be a positive multiple of 0.5 turn "
            f"(each half-turn is one constant-radius arc between two "
            f"radius-step crossings) -- pick a value on the params.json grid.")
    return {
        "n_turns": n_turns,
        "spacing_um": float(params["spacing_um"]),
        "track_width_um": float(params["track_width_um"]),
        "inner_diameter_um": float(params["inner_diameter_um"]),
        "tab_length_um": float(params["tab_length_um"]),
        "port_spacing_um": float(params["port_spacing_um"]),
    }


def _unit(dx, dy):
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def _arm_a_raw_path(n_turns, track_width_um, spacing_um, inner_diameter_um):
    """Builds arm A's own (un-mirrored, un-layer-decorated) path: returns
    (ct_xy, pts, crossing_indices). pts[0] is the first interior vertex
    after ct (NOT including ct_xy itself); crossing_indices lists the
    index (into pts) of the point where the winding ARRIVES at each
    intermediate crossing (the step itself is the edge from pts[idx] to
    pts[idx+1], radius changing by pitch/2 -- see this module's own
    docstring for why half, not a full pitch, per step).

    Each half-turn contributes 4 interior vertices at CONSTANT radius,
    offset from the crossing angles (270/90) by the same 22.5-degree
    "flat-topped/flat-sided" convention used throughout this project, so
    each arc still reads as clean octagon facets rather than a smoothly
    drifting spiral.

    Crossing shape (2026-09-17, THIRD revision -- see git history/prior
    conversation turns for the first two: a pure vertical jump, found
    visually distorted/overlapping since it packed two near-90-degree
    corners into a span of just a few um; then a single wide diagonal,
    which fixed the overlap but read as one intermediate-angle segment,
    not the clean horizontal/45-degree-only vocabulary the rest of the
    layout uses). Now an explicit 3-segment path -- horizontal, then
    EXACTLY 45 degrees, then horizontal again -- approximately 35%/30%/
    35% of the crossing's own total length. Since the horizontal legs
    contribute no vertical change at all, the ENTIRE radius step
    (`half_step`) has to come from the 45-degree middle leg alone, which
    pins its length to `half_step*sqrt(2)` -- that, not an independently
    free choice, is what actually determines the crossing's total
    length here (`half_step*sqrt(2) / 0.30`), with the horizontal legs
    sized at 35% of that total each. This is a real, deliberate change
    from the previous round's `_TRANSITION_FRAC*facet_len` sizing (which
    had no such constraint) -- the two would only coincidentally agree,
    so this round's total crossing length is generally different (and,
    for the geometries tried during review, noticeably shorter). Still
    centered on x=0 and continuing the approach vertex's own x-direction
    first, matching every earlier round's convention, so arm B's mirror
    of this same crossing still lands in the same region (required for
    the alternating-undercut interleaving, see diff_spiral_arms()'s
    docstring).

    HONEST LIMITATION, not silently glossed over: this makes the
    crossing ITSELF exactly horizontal/45-degree throughout, but the two
    short "connector" edges on either side of it (from the ring's own
    last regular vertex into the crossing, and from the crossing back
    into the next ring's first regular vertex) are NOT covered by this
    fix -- they keep whatever angle they already had (a small, few-
    degree tilt, same root cause as the ring facets' own approximate-
    not-exact alignment documented elsewhere in this module). Making
    EVERY segment in the whole layout exactly 0/45/90/135 degrees would
    need abandoning the trig-circle (r*cos/sin at fractional-degree
    angles) vertex generation entirely in favor of a Manhattan-plus-
    diagonal "taxicab" walk (fixed step directions, varying step
    lengths) -- a materially bigger rewrite than this round's ask,
    flagged here rather than attempted silently."""
    inner_radius_um = inner_diameter_um / 2
    pitch = track_width_um + spacing_um
    half_step = pitch / 2
    n_half_laps = round(n_turns * 2)
    r_outer = inner_radius_um + n_turns * pitch

    # Anchored to the TRUE first ring vertex's own y (r_outer*sin(247.5
    # degrees)), not the exact-axis r*sin(270)=-r_outer -- same fix, same
    # reason, as the ring-to-ring crossings below: those two y values
    # differ slightly, and using the exact-axis one left the ct connector
    # edge at a small real slope instead of flat.
    ct_xy = (0.0, r_outer * math.sin(math.radians(270.0 - 22.5)))

    pts = []
    crossing_indices = []
    theta_start_deg = 270.0
    r = r_outer
    for lap in range(n_half_laps):
        lap_pts = []
        for k in range(4):
            theta = math.radians(theta_start_deg - 22.5 - 45 * k)
            lap_pts.append((r * math.cos(theta), r * math.sin(theta)))
        pts.extend(lap_pts)
        theta_end_deg = theta_start_deg - 180.0
        if lap < n_half_laps - 1:
            last_x, y_end = lap_pts[-1]  # anchor to the TRUE last vertex's own y, not r*sin(90) --
            # the two differ (sin(112.5) != sin(90)), and using the
            # latter left the connector edge into the crossing at a
            # small but real slope instead of flat. Anchoring here makes
            # that connector collapse to zero vertical change, i.e.
            # exactly horizontal, and folds it into the crossing's own
            # first leg instead of being a separate sloped edge.
            r_next = r - half_step
            y_next = r_next * math.sin(math.radians(theta_end_deg - 22.5))  # true FIRST vertex of next ring's own y

            v_extent = abs(y_end - y_next)
            diag_len = v_extent * math.sqrt(2)
            total_len = diag_len / _TRANSITION_MID_FRAC
            h_len = _TRANSITION_END_FRAC * total_len
            # sign: p0 starts on the SAME side as the approach (last_x's
            # own sign), then each step moves toward and past the
            # opposite side -- p3 = -p0, symmetric about x=0. (An
            # earlier version of this had an extra stray negation on p0
            # that put it on the WRONG side of the approach, producing a
            # self-tangling crossing -- caught during this round's own
            # review, fixed here.)
            sign = math.copysign(1.0, last_x)

            p0 = (sign * (h_len + v_extent / 2), y_end)
            p1 = (p0[0] - sign * h_len, y_end)
            p2 = (p1[0] - sign * v_extent, y_next)
            p3 = (p2[0] - sign * h_len, y_next)

            pts.append(p0)
            crossing_indices.append(len(pts) - 1)
            pts.append(p1)
            pts.append(p2)
            pts.append(p3)
            r = r_next
        theta_start_deg = theta_end_deg
    return ct_xy, pts, crossing_indices


def diff_spiral_arms(n_turns, track_width_um, spacing_um, inner_diameter_um):
    """Returns (ct_xy, full_a, edge_layers_a, full_b, edge_layers_b):
    full_a/full_b are each the complete point list from ct_xy (index 0)
    to that arm's own far terminus (P1=full_a[-1], P2=full_b[-1]);
    edge_layers_a/b are parallel lists (one entry per edge, i.e.
    len(full)-1 entries) of "metal5" or "metal4", marking which
    crossings that arm routes via a Metal4 undercut -- see this module's
    own docstring for why (interleaving the two arms' otherwise-
    colliding crossings) and which arm dips at which crossing
    (alternates every crossing). Each crossing is now a 3-segment path
    (horizontal/45-degree/horizontal, see _arm_a_raw_path()'s own
    docstring) -- ALL 3 of those edges go to whichever layer that arm is
    using at that crossing, not just the middle one, so the whole
    undercut structure (not half of it) actually sits on Metal4."""
    ct_xy, pts_a, crossings = _arm_a_raw_path(n_turns, track_width_um, spacing_um, inner_diameter_um)
    full_a = [ct_xy] + pts_a
    full_b = [ct_xy] + [(-x, y) for x, y in pts_a]

    edge_layers_a = ["metal5"] * (len(full_a) - 1)
    edge_layers_b = ["metal5"] * (len(full_b) - 1)
    for j, idx in enumerate(crossings):
        edge_i0 = idx + 1  # first of the 3 crossing edges -- idx is a pts-index, full=[ct]+pts
        target = edge_layers_a if j % 2 == 0 else edge_layers_b
        for edge_i in (edge_i0, edge_i0 + 1, edge_i0 + 2):
            target[edge_i] = "metal4"
    return ct_xy, full_a, edge_layers_a, full_b, edge_layers_b


def _group_runs(points, edge_layers):
    """Splits a point list into contiguous same-layer runs (per
    edge_layers), each run sharing its boundary point with its
    neighbors -- e.g. [(metal5, [p0,p1,p2]), (metal4, [p2,p3]), (metal5,
    [p3,p4,...])]. Used by both the preview renderer and
    build_openems_structure to draw/build each layer's own geometry
    separately without re-deriving the split logic twice."""
    runs = []
    run_start = 0
    current = edge_layers[0]
    for i in range(1, len(edge_layers)):
        if edge_layers[i] != current:
            runs.append((current, points[run_start:i + 1]))
            run_start = i
            current = edge_layers[i]
    runs.append((current, points[run_start:]))
    return runs


def spiral_ribbon_polygon(centerline, width_um):
    """Single continuous ribbon polygon around a polyline centerline,
    general mitered offset at each interior vertex (works for any
    interior angle). `cos_half` is clamped away from 0 so a near-
    reversal corner gets a bounded miter instead of shooting to
    infinity."""
    n = len(centerline)
    half_w = width_um / 2

    outer, inner = [], []
    for i, p in enumerate(centerline):
        if i == 0:
            ux, uy = _unit(centerline[1][0] - p[0], centerline[1][1] - p[1])
            nx, ny = -uy, ux
        elif i == n - 1:
            ux, uy = _unit(p[0] - centerline[i - 1][0], p[1] - centerline[i - 1][1])
            nx, ny = -uy, ux
        else:
            ux0, uy0 = _unit(p[0] - centerline[i - 1][0], p[1] - centerline[i - 1][1])
            ux1, uy1 = _unit(centerline[i + 1][0] - p[0], centerline[i + 1][1] - p[1])
            n0x, n0y = -uy0, ux0
            n1x, n1y = -uy1, ux1
            mx, my = n0x + n1x, n0y + n1y
            mlen = math.hypot(mx, my)
            if mlen < 1e-6:
                nx, ny = n0x, n0y
            else:
                mx, my = mx / mlen, my / mlen
                cos_half = max(mx * n0x + my * n0y, 0.2)
                nx, ny = mx / cos_half, my / cos_half
        outer.append((p[0] + nx * half_w, p[1] + ny * half_w))
        inner.append((p[0] - nx * half_w, p[1] - ny * half_w))

    return outer + list(reversed(inner))


def _merge_close_lines(values, min_spacing):
    """Same dedup/merge as inductor_spiral_generator.py's own helper --
    duplicated per this project's self-contained-generator convention."""
    ordered = sorted(values)
    merged = [ordered[0]]
    for v in ordered[1:]:
        if v - merged[-1] >= min_spacing:
            merged.append(v)
    return merged


def mesh_resolution_um(track_width_um, spacing_um):
    """Same res_xy/port_len formula as inductor_spiral_generator.py's
    build_openems_structure()."""
    res_xy = max(min(track_width_um, spacing_um) / 2, 0.4)
    port_len = max(res_xy * 1.5, min(0.5, track_width_um / 2))
    return res_xy, port_len


def route_ports(geometry):
    """Computes the 3 external pad locations (P1, P2, P3/E) and their
    Metal4 routing back up to the winding -- same shape as before: pads
    in one row at the bottom (`y_baseline`), spaced by `port_spacing_um`,
    each rising straight up in parallel to the y-height of its own
    winding terminus, then a horizontal jog to that terminus's own x,
    ending in a via4 into Metal5 (ct's jog is negligible, its terminus is
    already pinned to x=0)."""
    ct_xy, full_a, edge_layers_a, full_b, edge_layers_b = diff_spiral_arms(
        geometry["n_turns"], geometry["track_width_um"], geometry["spacing_um"], geometry["inner_diameter_um"])
    p1_xy, p2_xy = full_a[-1], full_b[-1]

    inner_radius_um = geometry["inner_diameter_um"] / 2
    r_outer = inner_radius_um + geometry["n_turns"] * (geometry["track_width_um"] + geometry["spacing_um"])
    _, port_len = mesh_resolution_um(geometry["track_width_um"], geometry["spacing_um"])
    port_spacing = geometry["port_spacing_um"]
    y_baseline = -(r_outer + port_len) - geometry["tab_length_um"]

    # Which pad (-port_spacing vs +port_spacing) goes to which terminus
    # is decided by the terminus's OWN x sign, not fixed to "P1=left,
    # P2=right" -- P1's natural terminus lands on whichever side
    # n_turns' own half-lap parity happens to put it (see
    # diff_spiral_arms()'s docstring: the arm alternates bottom/top
    # crossings, so its final x sign isn't fixed). Picking the pad
    # x-sign to MATCH each terminus's own sign keeps both jogs short and
    # non-crossing; the alternative (P1 always at -port_spacing) would
    # sometimes force both jogs to swap sides and cross each other on
    # the SAME Metal4 layer -- a real short, found by inspecting a
    # preview at n_turns=2 before this fix.
    if p1_xy[0] <= p2_xy[0]:
        p1_pad = (-port_spacing, y_baseline)
        p2_pad = (port_spacing, y_baseline)
    else:
        p1_pad = (port_spacing, y_baseline)
        p2_pad = (-port_spacing, y_baseline)
    p3_pad = (0.0, y_baseline)
    p1_jog_xy = (p1_pad[0], p1_xy[1])
    p2_jog_xy = (p2_pad[0], p2_xy[1])
    ct_jog_xy = (p3_pad[0], ct_xy[1])

    return {
        "ct_xy": ct_xy, "full_a": full_a, "edge_layers_a": edge_layers_a,
        "full_b": full_b, "edge_layers_b": edge_layers_b, "r_outer": r_outer,
        "p1_xy": p1_xy, "p2_xy": p2_xy,
        "p1_jog_xy": p1_jog_xy, "p2_jog_xy": p2_jog_xy, "ct_jog_xy": ct_jog_xy,
        "p1_pad": p1_pad, "p2_pad": p2_pad, "p3_pad": p3_pad,
    }


def _draw_axis_aligned_strip(ax, pts, width_um, **kwargs):
    """Fills a track_width-wide strip along a polyline of AXIS-ALIGNED
    segments (each consecutive pair sharing either x or y)."""
    half_w = width_um / 2
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        xlo, xhi = sorted((x0, x1))
        ylo, yhi = sorted((y0, y1))
        ax.fill([xlo - half_w, xhi + half_w, xhi + half_w, xlo - half_w],
                [ylo - half_w, ylo - half_w, yhi + half_w, yhi + half_w], **kwargs)


def save_layout_preview(geometry, path, variant=None):
    """Top-view PNG of the generated differential spiral, independent of
    CSXCAD/openEMS. Metal5 (goldenrod) drawn per contiguous run (split at
    every Metal4 undercut); Metal4 undercuts and the 3 Metal4 port traces
    both drawn steelblue/semi-transparent with via markers, so the
    "crosses under here" regions read the same way the reference photo's
    own underpasses do.

    variant=None (default): the full, approved differential structure
    (both arms, all 3 pads) -- unchanged from before variants existed.
    variant in {"arm_a", "arm_b", "shorted"}: restricts the drawing to
    exactly what build_openems_structure() would build for that same
    variant (see that function's own docstring) -- including "shorted"'s
    own test-only P2<->ct jumper -- so each of the 3 open/short-circuit-
    test runs can be visually sanity-checked before ever starting a real
    (multi-hour) FDTD run."""
    ports = route_ports(geometry)
    track_width_um = geometry["track_width_um"]
    half_w = track_width_um / 2
    ct_xy = ports["ct_xy"]

    fig, ax = plt.subplots(figsize=(6, 7))

    # The P1/P2 stub (winding terminus -> jog point) is appended onto
    # each arm's own point list here, NOT drawn as a separate box (see
    # metal4_paths/metal5_paths below for why that looked disconnected
    # -- a flat-capped rectangle butted against the ribbon's own flat
    # end cap, neither aligned with the other, instead of one mitered
    # corner). Folding it in lets _group_runs/spiral_ribbon_polygon miter
    # this joint exactly the same way every other same-layer joint in
    # the winding already is. Filtered by variant the same way
    # build_openems_structure()'s own arms_ext is.
    arms_ext = []
    if variant is None or variant in ("arm_a", "shorted"):
        arms_ext.append((ports["full_a"] + [ports["p1_jog_xy"]], ports["edge_layers_a"] + ["metal5"]))
    if variant is None or variant in ("arm_b", "shorted"):
        arms_ext.append((ports["full_b"] + [ports["p2_jog_xy"]], ports["edge_layers_b"] + ["metal5"]))
    via4_markers = []
    for full, edge_layers in arms_ext:
        for layer, run_pts in _group_runs(full, edge_layers):
            # Both layers use the general mitered ribbon here, NOT
            # _draw_axis_aligned_strip -- the crossing runs are diagonal
            # (see _arm_a_raw_path()'s docstring), and a bounding-box
            # strip drawn for a diagonal segment is wider than the real
            # trace and visibly overlaps its neighbors (found during
            # this round's own review).
            ribbon = spiral_ribbon_polygon(run_pts, track_width_um)
            if layer == "metal5":
                ax.fill(*zip(*(ribbon + [ribbon[0]])), color="goldenrod", edgecolor="darkgoldenrod",
                         linewidth=0.3, zorder=2)
            else:
                ax.fill(*zip(*(ribbon + [ribbon[0]])), color="steelblue", alpha=0.6, edgecolor="steelblue",
                         linewidth=0.3, zorder=1)
                via4_markers.extend([run_pts[0], run_pts[-1]])

    # Port risers: Metal4 for the straight vertical run only (pad up to
    # the jog point) -- the only thing left on Metal4 is a plain
    # straight line, per the user's own preference (2026-09-17). P1/P2's
    # own corner + horizontal run into the winding is now drawn as part
    # of the winding's own ribbon above (see arms_ext); ct's jog is
    # degenerate (already at x=0) so its own "corner" is zero-length --
    # still drawn explicitly here since it was never part of an arm's
    # point list to begin with.
    metal4_paths = {"E": [ports["p3_pad"], ports["ct_jog_xy"]]}
    if variant is None or variant in ("arm_a", "shorted"):
        metal4_paths["P1"] = [ports["p1_pad"], ports["p1_jog_xy"]]
    if variant is None or variant in ("arm_b", "shorted"):
        metal4_paths["P2"] = [ports["p2_pad"], ports["p2_jog_xy"]]
    if variant == "shorted":
        # Test-only jumper shorting P2's pad to ct's pad -- see
        # build_openems_structure()'s own docstring/comment for this
        # variant. Drawn in a distinct color (not steelblue/goldenrod, both
        # already used for real device metal) so it visually reads as the
        # test-only addition it is, not part of the normal 3-terminal
        # device.
        metal4_paths["jumper"] = [ports["p2_pad"], ports["p3_pad"]]
    for label, pts in metal4_paths.items():
        color = "crimson" if label == "jumper" else "steelblue"
        _draw_axis_aligned_strip(ax, pts, track_width_um, color=color, alpha=0.45,
                                  edgecolor=color, linewidth=0.3, zorder=1)
    _draw_axis_aligned_strip(ax, [ports["ct_jog_xy"], ct_xy], track_width_um, color="goldenrod",
                              edgecolor="darkgoldenrod", linewidth=0.3, zorder=2)
    via4_markers.append(ports["ct_jog_xy"])
    if variant is None or variant in ("arm_a", "shorted"):
        via4_markers.append(ports["p1_jog_xy"])
    if variant is None or variant in ("arm_b", "shorted"):
        via4_markers.append(ports["p2_jog_xy"])

    for via_xy in via4_markers:
        ax.add_patch(plt.Rectangle(
            (via_xy[0] - half_w, via_xy[1] - half_w), track_width_um, track_width_um,
            color="dimgray", zorder=3))

    inner_radius_um = geometry["inner_diameter_um"] / 2
    circle = plt.Circle((0, 0), inner_radius_um, fill=False, linestyle="--", color="gray", linewidth=0.8, zorder=4)
    ax.add_patch(circle)

    ax.plot(*ports["p1_pad"], "go", markersize=7, zorder=5, label="P1 (a)")
    ax.plot(*ports["p2_pad"], "rs", markersize=7, zorder=5, label="P2 (b)")
    ax.plot(*ports["p3_pad"], "b^", markersize=7, zorder=5, label="P3 / E (ct)")
    ax.annotate("P1", ports["p1_pad"], textcoords="offset points", xytext=(-14, -12))
    ax.annotate("P2", ports["p2_pad"], textcoords="offset points", xytext=(4, -12))
    ax.annotate("E", ports["p3_pad"], textcoords="offset points", xytext=(4, -12))

    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(
        f"spiral_diff{' [' + variant + ']' if variant else ''}: n_turns/arm={geometry['n_turns']:g}, "
        f"W={track_width_um:g}um, S={geometry['spacing_um']:g}um, "
        f"ID={geometry['inner_diameter_um']:g}um, tab={geometry['tab_length_um']:g}um, "
        f"port_spacing={geometry['port_spacing_um']:g}um", fontsize=9)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def add_field_dump(CSX, name, box, z0, z1, dump_freq_hz):
    """Same shape/reasoning as inductor_spiral_generator.py's own
    add_field_dump()."""
    dump = CSX.AddDump(name, dump_type=13, file_type=1)
    dump.AddFrequency(dump_freq_hz)
    dump.AddBox([-box, -box, z0], [box, box, z1])


def build_openems_structure(geometry, stack, f_max_hz, dump_field=False):
    """PDK/geometry-specific: builds the CSXCAD/openEMS structure for
    exactly ONE of the 3 open/short-circuit-test variants (see this
    module's own docstring for the full methodology) and returns
    (FDTD, port), same 2-tuple contract every other generator in this
    project uses -- geometry["variant"] (one of "arm_a"/"arm_b"/"shorted")
    selects which one, REQUIRED, no default:
      "arm_a":   arm A alone (arm B genuinely absent), port bridging
                 (ct-pad, P1-pad).
      "arm_b":   arm B alone (arm A genuinely absent), port bridging
                 (ct-pad, P2-pad).
      "shorted": both arms present, PLUS a test-only jumper trace shorting
                 P2's pad to ct's pad, port bridging (P1-pad, ct-pad) --
                 same port placement as "arm_a", so the two are directly
                 comparable.
    There is deliberately no "differential"/generic mode any more -- an
    earlier version of this function built exactly that (one LumpedPort
    bridging P1's pad DIRECTLY to P2's pad) and it was confirmed invalid,
    see the module docstring.

    UNVALIDATED against a real FDTD run -- run a structure-only (no FDTD)
    sanity check first for each variant."""
    variant = geometry.get("variant")
    if variant not in ("arm_a", "arm_b", "shorted"):
        raise ValueError(
            f"inductor_spiral_diff_generator.build_openems_structure() requires "
            f"geometry['variant'] in {{'arm_a', 'arm_b', 'shorted'}} (got {variant!r}) -- "
            f"see this module's own docstring for why there is no default/generic "
            f"differential measurement mode any more")

    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    unit = 1e-6
    track_width_um = geometry["track_width_um"]
    spacing_um = geometry["spacing_um"]
    half_w = track_width_um / 2

    ports = route_ports(geometry)
    ct_xy = ports["ct_xy"]
    r_outer = ports["r_outer"]
    p1_pad, p2_pad, p3_pad = ports["p1_pad"], ports["p2_pad"], ports["p3_pad"]

    res_xy, port_len = mesh_resolution_um(track_width_um, spacing_um)
    excite_v_per_m = 10.0 / (port_len * unit)

    metal5_sigma = 1.0 / (stack["metal5_sheet_r_ohm_per_sq"] * stack["metal5_thickness_m"])
    metal4_sigma = 1.0 / (stack["metal4_sheet_r_ohm_per_sq"] * stack["metal4_thickness_m"])
    substrate_sigma = 1.0 / (stack["substrate_resistivity_ohm_cm"] * 1e-2)
    z_ox_top = stack["metal5_z_start_m"] / unit
    z_m5_top = z_ox_top + stack["metal5_thickness_m"] / unit
    m4_z0 = stack["metal4_z_start_m"] / unit
    m4_z1 = m4_z0 + stack["metal4_thickness_m"] / unit

    f0 = f_max_hz / 2
    fc = f_max_hz / 2
    FDTD = openEMS(EndCriteria=1e-4)
    FDTD.SetGaussExcite(f0, fc)
    FDTD.SetBoundaryCond(["PML_8"] * 6)

    CSX = ContinuousStructure()
    FDTD.SetCSX(CSX)
    mesh = CSX.GetGrid()
    mesh.SetDeltaUnit(unit)

    # Which arm(s)/risers/jumper actually get built, and which two pads the
    # single LumpedPort bridges, are both variant-dependent -- see this
    # function's own docstring. ct's own riser is present in every variant
    # (it's one of the port's own two terminals in every case).
    arms_ext = []
    all_pts = []
    port_metal4_paths = [[p3_pad, ports["ct_jog_xy"]]]
    if variant in ("arm_a", "shorted"):
        arms_ext.append((ports["full_a"] + [ports["p1_jog_xy"]], ports["edge_layers_a"] + ["metal5"]))
        port_metal4_paths.append([p1_pad, ports["p1_jog_xy"]])
        all_pts += ports["full_a"]
    if variant in ("arm_b", "shorted"):
        arms_ext.append((ports["full_b"] + [ports["p2_jog_xy"]], ports["edge_layers_b"] + ["metal5"]))
        port_metal4_paths.append([p2_pad, ports["p2_jog_xy"]])
        all_pts += ports["full_b"]
    port_metal5_paths = [
        [ports["ct_jog_xy"], ct_xy],
    ]

    # The port's own two bridged pads -- "arm_a"/"shorted" both bridge
    # (P1, ct) so the two are directly comparable (see module docstring);
    # "arm_b" mirrors onto (P2, ct).
    port_pad_0, port_pad_1 = {"arm_a": (p1_pad, p3_pad), "arm_b": (p2_pad, p3_pad),
                               "shorted": (p1_pad, p3_pad)}[variant]
    port_gap = port_len
    p_y_mid = port_pad_0[1]
    # LEFT/RIGHT by actual x, not by an assumed fixed side -- route_ports()
    # assigns each pad's x by its OWN winding terminus's sign (see that
    # function's own docstring), so which of the two bridged pads is
    # physically left/right isn't fixed.
    x_left, x_right = sorted((port_pad_0[0], port_pad_1[0]))

    # 2026-09-18 FIX: an EARLIER version let the LumpedPort itself span the
    # pads' WHOLE separation (port_spacing_um, ~12-15um here vs. loop's/
    # spiral's own ports which are only ~2*half_w, a couple microns) --
    # confirmed via a real FDTD run to DIVERGE (energy blew up to inf within
    # ~40 minutes of simulated time, see spiral_diff_bringup_status.md for
    # the full trail) -- a LumpedPort spanning many mesh cells is not the
    # small-gap-in-an-otherwise-continuous-conductor pattern loop/spiral's
    # own already-validated ports use. Fixed by bridging MOST of the
    # separation with an ordinary, WIDE (low-resistance) Metal4 jumper --
    # same "add a test-only real conductor" idea as the "shorted" variant's
    # own P2<->ct short below, just here it's needed in EVERY variant to
    # keep the port itself small -- leaving only a small `port_gap` (same
    # scale as loop's/spiral's own port span) right at the x_right end for
    # the actual LumpedPort. `bridge_width_um` is deliberately much wider
    # than track_width_um specifically to keep this test-only conductor's
    # own series resistance small relative to the arm's real Ra/Rb -- NOT
    # zero (a real, small, honestly-not-hidden approximation, same spirit
    # as this project's other geometry-based estimates), but this project
    # has no non-lumped ideal-wire primitive to make it exactly zero.
    bridge_width_um = 6 * track_width_um
    bridge_half_w = bridge_width_um / 2
    if x_right - x_left <= port_gap + 2 * half_w:
        raise ValueError(
            f"port pads are only {x_right - x_left:.3f}um apart, not enough room for a "
            f"{port_gap:.3f}um port gap plus the two {2 * half_w:.3f}um-wide port terminals -- "
            f"increase port_spacing_um")
    # 2026-09-21 FIX of a real short across the port: bridge_x1 used to be x_right - port_gap, and
    # the Metal4 bridge box ends at bridge_x1 + half_w (x_right - port_gap + half_w), while the
    # Metal4 riser of the far pad starts at x_right - half_w. With port_gap (2.25um) < 2*half_w (3um)
    # those two boxes OVERLAPPED under the port, so Metal4 was continuous below the (Metal5) port gap
    # and the port saw a ~0.04 ohm / 0.5 pH short instead of the winding (found by computing Z from
    # port_ut/port_it of the first converged run). Now the bridge's Metal4 ends exactly at the port's
    # left edge and the far riser's Metal4 starts exactly at the port's right edge, leaving the whole
    # port gap free of metal underneath; each terminal is a via4 + Metal5 cap (2*half_w square).
    bridge_x0, bridge_x1 = x_left, x_right - port_gap - 2 * half_w
    port_p0 = (bridge_x1 + half_w, p_y_mid - half_w)
    port_p1 = (x_right - half_w, p_y_mid + half_w)

    # 2026-09-18 SECOND fix, found after the bridge-width fix ABOVE still
    # diverged (confirmed via a real run, energy blew up again -- and via a
    # crossing-free n_turns=0.5 control run, which ALSO diverged, ruling out
    # the Metal4 undercut/crossing geometry as the cause): the LumpedPort
    # above was sitting on METAL4 (z=[m4_z0,m4_z1]), i.e. INSIDE the
    # modeled oxide box's own z-range (oxide spans z=[0,z_ox_top], and
    # m4_z1 < z_ox_top -- see build_openems_structure()'s own z-stack).
    # Cross-checked against BOTH already-validated ports in this project
    # (inductor_loop_generator.py's and inductor_spiral_generator.py's own
    # build_openems_structure()): both place their LumpedPort at
    # z=[z_ox_top, z_m5_top] -- METAL5's own range, ABOVE the oxide box
    # entirely, never touching it -- and inductor_spiral_generator.py's own
    # code comment explicitly warns why: a port z-range that reaches down
    # into/through the oxide/substrate region was CONFIRMED (that module's
    # own prior investigation) to produce a ~30-40 kOhm modeling artifact.
    # An ordinary Metal4 CONDUCTOR (via priority=5) embedded in oxide is
    # fine (this project's own crossunders/risers already do that,
    # everywhere) -- it's specifically the LumpedPort primitive sitting
    # there that's the problem. Fixed by tapping BOTH the bridge's own far
    # end (bridge_x1) and the far pad's own riser (x_right) up to Metal5
    # via a via4 transition each (added to via4_jog_points below), and
    # moving the port itself onto Metal5 between those two taps -- same x
    # span as before, just relocated in z. The wide bridge and pad risers
    # themselves stay on Metal4 (ordinary conductors, not ports -- no
    # reason to move those).
    wide_bridge_paths = [(bridge_x0, bridge_x1, p_y_mid)]
    port_z0, port_z1 = z_ox_top, z_m5_top
    extra_via4_points = [(bridge_x1, p_y_mid), (x_right, p_y_mid)]
    if variant == "shorted":
        # Test-only jumper, real drawn metal (not part of the normal
        # 3-terminal device) shorting P2's pad directly to ct's pad -- both
        # sit on the same y_baseline pad row (see route_ports()). Made wide
        # too (same bridge_width_um), same low-resistance reasoning as
        # above -- this is the actual "short" of the shorted-secondary test,
        # so its own resistance directly affects Za_sc's accuracy.
        x_lo, x_hi = sorted((p2_pad[0], p3_pad[0]))
        wide_bridge_paths.append((x_lo, x_hi, p2_pad[1]))

    # Metal4 covers only the straight vertical run (pad -> jog); the
    # corner and the short horizontal run over to the winding terminus
    # are Metal5 -- per the user's own preference (2026-09-17), so
    # Metal4 never bends, only the layer it's already switched to does.
    # P1/P2's own corner+stub is drawn via arms_ext above (mitered into
    # the winding ribbon, see that block's own comment); only ct's own
    # (degenerate, zero-length) stub is handled here since it was never
    # part of an arm's point list.
    port_paths = port_metal4_paths + port_metal5_paths

    # 2026-09-18: LOCAL mesh refinement right at each jog point (ct_jog_xy,
    # and whichever of p1_jog_xy/p2_jog_xy this variant builds) -- found via
    # a real time-domain E-field dump (see spiral_diff_bringup_status.md)
    # that this exact spot is where the divergence actually SEEDS: a
    # localized field concentration growing exponentially from ~timestep
    # 25000 (long before the domain-wide energy log shows anything),
    # nowhere else in the structure. Each jog point is a genuinely more
    # complex junction than anything in loop's/spiral's own validated
    # geometry: THREE separately-drawn pieces meet in only ~1-2 mesh
    # cells -- the Metal5 ribbon arriving HORIZONTALLY from the winding,
    # the Metal4 riser going VERTICALLY down to its own pad, and a via4 box
    # bridging the z-layer transition -- a sharp 90-degree conductor corner
    # AND a layer transition at the SAME point. spiral's own via4 (its
    # crossunder) never does this: both its ends are collinear (metal4
    # below, via4 middle, metal5 above, no lateral turn at the via4 at all).
    # Sharp conductor corners are a known field-singularity risk in FDTD;
    # combined with a layer transition and only ~1-2 cells of resolution,
    # this is a plausible, and now DIRECTLY OBSERVED, instability seed.
    # Fix: add extra, LOCAL-ONLY anchor lines spanning +-half_w around each
    # jog point at ~5x the global res_xy (not a global resolution change --
    # keeps cost low everywhere else). 2026-09-18 tuning history: a first
    # 3x/+-half_w attempt measurably DELAYED the divergence onset
    # (~timestep 25000 -> ~timestep 90000 at that run's OWN, coarser
    # timestep -- a real, reproducible effect, not noise) but did not
    # eliminate it. A follow-up 10x/+-2*half_w attempt was FAR healthier at
    # the same WALL-CLOCK time, but xy cells that fine (half_w/10=0.15um)
    # fell BELOW the z-mesh's own already-fine ~0.3um cells (from
    # metal5_thickness/2 smoothing), making xy -- not z -- the new global
    # CFL bottleneck: timestep dropped ~3.6x and total timesteps-to-cover-
    # the-same-excitation-pulse rose to ~1.4M, hours per run -- impractical
    # to iterate on. Settled on 5x (half_w/5=0.3um), matching rather than
    # undercutting the z-mesh's own existing finest scale, so this refinement
    # doesn't become a NEW, worse global timestep bottleneck than the one
    # the z-stack's own thin metal layers already impose.
    jog_points = [ports["ct_jog_xy"]]
    if variant in ("arm_a", "shorted"):
        jog_points.append(ports["p1_jog_xy"])
    if variant in ("arm_b", "shorted"):
        jog_points.append(ports["p2_jog_xy"])
    fine_step = half_w / 5
    fine_offsets = [k * fine_step for k in range(-5, 6)]
    jog_fine_xs = [xy[0] + d for xy in jog_points for d in fine_offsets]
    jog_fine_ys = [xy[1] + d for xy in jog_points for d in fine_offsets]

    anchor_xs = ([p[0] for p in all_pts] + [pt[0] for path in port_paths for pt in path]
                 + [port_p0[0], port_p1[0]] + [x0 for x0, x1, y in wide_bridge_paths]
                 + [x1 for x0, x1, y in wide_bridge_paths])
    anchor_ys = ([p[1] for p in all_pts] + [pt[1] for path in port_paths for pt in path]
                 + [port_p0[1], port_p1[1]]
                 + [y - bridge_half_w for x0, x1, y in wide_bridge_paths]
                 + [y + bridge_half_w for x0, x1, y in wide_bridge_paths])
    # Coarse anchors merged at the usual res_xy threshold, jog anchors
    # merged separately at their own finer threshold -- merging everything
    # together at the fine threshold would let ORDINARY (non-jog) anchors
    # that happen to fall within res_xy of each other survive un-merged
    # too, needlessly finening the mesh well beyond the jog points this is
    # actually targeting.
    xs_combined = _merge_close_lines(anchor_xs, res_xy)
    ys_combined = _merge_close_lines(anchor_ys, res_xy)
    if JOG_MESH_REFINE:
        xs_combined += _merge_close_lines(jog_fine_xs, fine_step * 0.9)
        ys_combined += _merge_close_lines(jog_fine_ys, fine_step * 0.9)
    # Final cleanup pass at a small (not res_xy-scale) threshold -- the two
    # merges above ran independently, so a coarse anchor could land just a
    # hair away from an unrelated fine anchor, producing an unintended
    # near-degenerate gap; this only removes true near-duplicates, it does
    # NOT undo the intended fine spacing around the jog points (fine_step
    # itself survives since consecutive REAL fine anchors are fine_step
    # apart, well above this threshold).
    xs = _merge_close_lines(xs_combined, fine_step * 0.3)
    ys = _merge_close_lines(ys_combined, fine_step * 0.3)
    # 2026-09-18: margin widened from a flat 6*track_width_um -- for a
    # winding whose track_width_um is a small fraction of its own r_outer
    # (typical here: e.g. 3um track on a 68um-radius winding), that flat
    # multiple gives a MUCH smaller margin-to-coil-size ratio than loop's/
    # spiral's own identical-looking "+6*track_width" formula happens to
    # give THEIR own (usually track-width-dominated) geometries -- e.g.
    # spiral's own default (20um inner radius, 5um track) margin is ~73%
    # of its own r_outer, vs. only ~26% here with the same formula. Now
    # scales with the LARGER of the two, so the margin stays a comfortable
    # fraction of the coil's own footprint regardless of how small
    # track_width_um is relative to r_outer -- prompted by a real user
    # observation that a CONVERGED 'loop' run's own substrate current-
    # density dump hadn't fully decayed to background even 15% inside the
    # domain's own edge (see spiral_diff_bringup_status.md), i.e. a
    # legitimate fidelity concern independent of this module's own open
    # divergence bug (a real FDTD test with this margin at 5x the old
    # value showed IDENTICAL divergence timing -- this change is for
    # substrate-current fidelity, not a divergence fix; don't re-litigate
    # that ruled-out hypothesis if the divergence is still open when this
    # is read).
    margin_um = max(6 * track_width_um, 0.4 * r_outer)
    box = r_outer + margin_um
    box_y = -p3_pad[1] + margin_um
    mesh.AddLine("x", xs + [-box, box])
    mesh.AddLine("y", ys + [-box_y, box])
    mesh.SmoothMeshLines("x", res_xy, ratio=1.4)
    mesh.SmoothMeshLines("y", res_xy, ratio=1.4)

    # z domain: see the Z_* constants' comment -- thick substrate + tall air (both scaled up for a
    # big coil so the z-PMLs stay >~1 coil diameter away), z mesh fine near the metal only.
    sub_thick = max(Z_SUBSTRATE_MIN_UM, 2 * r_outer + 80.0)
    air_above = max(Z_AIR_MIN_UM, 2 * r_outer + 80.0)
    mesh.AddLine("z", [-min(sub_thick, Z_NEAR_BAND_UM), 0, m4_z0, m4_z1, z_ox_top, z_m5_top,
                       z_m5_top + min(air_above, Z_NEAR_BAND_UM)])
    mesh.SmoothMeshLines("z", stack["metal5_thickness_m"] / unit / 2, ratio=1.4)
    mesh.AddLine("z", [-sub_thick, z_m5_top + air_above])
    mesh.SmoothMeshLines("z", Z_FAR_RES_UM, ratio=1.4)

    substrate = CSX.AddMaterial("substrate", epsilon=stack["substrate_epsilon_r"], kappa=substrate_sigma)
    substrate.AddBox([-box, -box_y, -sub_thick], [box, box, 0])

    oxide = CSX.AddMaterial("oxide", epsilon=stack["oxide_epsilon_r"])
    oxide.AddBox([-box, -box_y, 0], [box, box, z_ox_top])

    metal5 = CSX.AddMaterial("metal5", kappa=metal5_sigma)
    metal4 = CSX.AddMaterial("metal4", kappa=metal4_sigma)
    via4 = CSX.AddMaterial("via4", kappa=metal4_sigma)

    # arms_ext (only whichever arm(s) this variant actually builds -- see
    # above) already has each arm's own stub (winding terminus -> jog
    # point) folded onto its point list, same reasoning as
    # save_layout_preview()'s own arms_ext -- lets it get mitered into the
    # ribbon like every other same-layer joint, instead of a separately-
    # built box that only touched the ribbon at a single corner.
    for full, edge_layers in arms_ext:
        for layer, run_pts in _group_runs(full, edge_layers):
            # Both layers use the general mitered ribbon (AddLinPoly),
            # NOT an axis-aligned AddBox -- the crossing runs are
            # diagonal (see _arm_a_raw_path()'s docstring), and a
            # bounding box drawn for a diagonal segment is wider than
            # the real trace and would overlap neighboring geometry.
            ribbon = spiral_ribbon_polygon(run_pts, track_width_um)
            if layer == "metal5":
                metal5.AddLinPoly([[p[0] for p in ribbon], [p[1] for p in ribbon]], "z", z_ox_top, z_m5_top - z_ox_top)
            else:
                metal4.AddLinPoly([[p[0] for p in ribbon], [p[1] for p in ribbon]], "z", m4_z0, m4_z1 - m4_z0,
                                   priority=5)
                for xy in (run_pts[0], run_pts[-1]):
                    via4.AddBox([xy[0] - half_w, xy[1] - half_w, m4_z1], [xy[0] + half_w, xy[1] + half_w, z_ox_top],
                                 priority=5)

    # Port risers: Metal4 for the straight vertical run (priority=5,
    # sits inside oxide's own z-range, same reasoning as
    # inductor_spiral_generator.py's add_crossunder()), Metal5 for the
    # corner + short horizontal run into the winding terminus, via4 at
    # the jog point where the two meet.
    for path in port_metal4_paths:
        for (x0, y0), (x1, y1) in zip(path[:-1], path[1:]):
            xlo, xhi = sorted((x0, x1))
            ylo, yhi = sorted((y0, y1))
            metal4.AddBox([xlo - half_w, ylo - half_w, m4_z0], [xhi + half_w, yhi + half_w, m4_z1], priority=5)
    # Wide, low-resistance Metal4 bridge(s) -- see this function's own
    # docstring/comment above for why these exist (keeps the actual
    # LumpedPort small, matching loop's/spiral's own already-validated port
    # sizing) -- same z-range/priority as every other Metal4 port trace,
    # just wider in y (bridge_half_w, not half_w).
    for x0, x1, y in wide_bridge_paths:
        metal4.AddBox([x0 - half_w, y - bridge_half_w, m4_z0], [x1 + half_w, y + bridge_half_w, m4_z1], priority=5)
    for path in port_metal5_paths:
        for (x0, y0), (x1, y1) in zip(path[:-1], path[1:]):
            xlo, xhi = sorted((x0, x1))
            ylo, yhi = sorted((y0, y1))
            metal5.AddBox([xlo - half_w, ylo - half_w, z_ox_top], [xhi + half_w, yhi + half_w, z_m5_top])
    # 2026-09-18 THIRD fix -- a real DRC violation, not just an instability
    # risk: via4 at each riser/ribbon jog used to be centered exactly ON
    # the jog point with no margin at all. The Metal5 ribbon's own flat
    # end-cap sits EXACTLY at the jog point and only extends toward the
    # winding (see the earlier cross-section illustration) -- so a via4
    # symmetric around the jog point stuck out past Metal5's own edge on
    # the side AWAY from the winding, with ZERO enclosure on every edge
    # (touching, not overlapping). Confirmed against gf180mcuD.tech's own
    # via4 rules: `surround v4/m4 *m4 50 30 directional` and
    # `surround v4/m5 *m5 50 30 directional` -- both Metal4 and Metal5 must
    # enclose via4 by >=50nm on every edge. Fixed by placing via4 INSIDE
    # the actual Metal4-riser/Metal5-ribbon overlap region, inset by that
    # 50nm margin on every side, instead of centering it on the jog point.
    _VIA4_ENCLOSURE_UM = 0.05  # 50nm, gf180mcuD.tech's own via4 "surround" rules (see comment above)

    def _enclosed_jog_via_box(jog_xy, ribbon_dirs_x, margin=_VIA4_ENCLOSURE_UM):
        """Returns (x0,x1,y0,y1) for a via4 box at a riser/ribbon jog that is
        actually enclosed (by `margin`) by BOTH the Metal4 riser (symmetric
        half_w around jog_xy) and the Metal5 ribbon -- `ribbon_dirs_x` lists
        the x-direction(s) (+1/-1) the ribbon actually extends from jog_xy
        in (ct's own jog can have ribbon on BOTH sides when both arms are
        present, e.g. the 'shorted' variant; P1's/P2's own jog only ever has
        one side, toward its own winding terminus)."""
        if len(set(ribbon_dirs_x)) >= 2:
            x0, x1 = jog_xy[0] - half_w, jog_xy[0] + half_w  # ribbon on both sides -- full symmetric width is safe
        else:
            d = ribbon_dirs_x[0]
            x0, x1 = sorted((jog_xy[0], jog_xy[0] + d * half_w))
        return x0 + margin, x1 - margin, jog_xy[1] - half_w + margin, jog_xy[1] + half_w - margin

    via4_jogs = []  # list of (jog_xy, ribbon_dirs_x)
    ct_ribbon_dirs = []
    if variant in ("arm_a", "shorted"):
        ct_ribbon_dirs.append(1.0 if ports["full_a"][1][0] >= ports["ct_jog_xy"][0] else -1.0)
    if variant in ("arm_b", "shorted"):
        ct_ribbon_dirs.append(1.0 if ports["full_b"][1][0] >= ports["ct_jog_xy"][0] else -1.0)
    via4_jogs.append((ports["ct_jog_xy"], ct_ribbon_dirs))
    if variant in ("arm_a", "shorted"):
        p1_dir = 1.0 if ports["p1_xy"][0] >= ports["p1_jog_xy"][0] else -1.0
        via4_jogs.append((ports["p1_jog_xy"], [p1_dir]))
    if variant in ("arm_b", "shorted"):
        p2_dir = 1.0 if ports["p2_xy"][0] >= ports["p2_jog_xy"][0] else -1.0
        via4_jogs.append((ports["p2_jog_xy"], [p2_dir]))

    for jog_xy, ribbon_dirs in via4_jogs:
        x0, x1, y0, y1 = _enclosed_jog_via_box(jog_xy, ribbon_dirs)
        via4.AddBox([x0, y0, m4_z1], [x1, y1, z_ox_top], priority=5)
    # extra_via4_points: the 2 taps (bridge's own far end, far pad's own
    # riser) that bring the LumpedPort's own 2 terminals up onto Metal5 --
    # see this function's own "2026-09-18 SECOND fix" comment above for why.
    # 2026-09-21: each tap now has a Metal5 cap (2*half_w square) over it -- before, the port's two
    # terminals were the bare tops of the via4s with no Metal5 above them -- and the via4 is inset
    # by the same 50nm enclosure as the jog vias.
    for xy in extra_via4_points:
        via4.AddBox([xy[0] - half_w + _VIA4_ENCLOSURE_UM, xy[1] - half_w + _VIA4_ENCLOSURE_UM, m4_z1],
                    [xy[0] + half_w - _VIA4_ENCLOSURE_UM, xy[1] + half_w - _VIA4_ENCLOSURE_UM, z_ox_top], priority=5)
        metal5.AddBox([xy[0] - half_w, xy[1] - half_w, z_ox_top], [xy[0] + half_w, xy[1] + half_w, z_m5_top])

    port_a = FDTD.AddLumpedPort(
        1, 50, [port_p0[0], port_p0[1], port_z0], [port_p1[0], port_p1[1], port_z1], "x", excite=excite_v_per_m)

    if dump_field:
        # Metal5 dump covers both arms; Metal4 dump also covers every
        # undercut crossing (same z-range as the port routes) since both
        # now share that layer.
        add_field_dump(CSX, FIELD_DUMP_NAMES["metal5"], box, z_ox_top, z_m5_top, f0)
        add_field_dump(CSX, FIELD_DUMP_NAMES["metal4"], box, m4_z0, m4_z1, f0)
        add_field_dump(CSX, FIELD_DUMP_NAMES["via4"], box, m4_z1, z_ox_top, f0)
        metal5_thickness_um = stack["metal5_thickness_m"] / unit
        add_field_dump(CSX, FIELD_DUMP_NAMES["substrate"], box, -metal5_thickness_um, 0, f0)

    return FDTD, port_a


def fit_electrical_params(geometry, stack, em_result=None):
    """PDK/model-specific.

    em_result=None (the fast/placeholder materialize path -- see
    inductor_loop_generator.py's own docstring for the same split):
    returns the same 11 keys as inductor_loop_generator.py's own
    fit_electrical_params(), PLUS 'k_coupling' (see inductor_spiral_diff
    .sch's own header comment for the new SPICE K element it drives) fixed
    at 0.0 -- no real EM mutual-inductance measurement is available on
    this path, so no coupling is assumed, same "honest, not fabricated"
    convention as rp_eddy=1e9 (effectively open) below. Uses the SUM of
    both arms' own lengths (edge lengths summed regardless of which layer
    they're on -- a reasonable simplification for this estimate, since
    Metal4's own sheet resistance, not accounted for separately here, is
    close in order of magnitude to Metal5's) in place of loop's
    rectangular-perimeter estimate.

    em_result=dict (a REAL single FDTD run's Y11(f) -- always exactly ONE
    of the 3 open/short-circuit-test variants, see this module's own
    docstring): does NOT attempt the full 11-key fit here -- a single
    variant's Y11 alone cannot separate la/lb/m any more than it could
    before this methodology existed (that's the whole reason there are 3
    runs, not 1). Instead returns a small, clearly-labeled per-run
    diagnostic dict {'variant', 'rs_arm', 'l_arm'} (the low-frequency
    Rs+jwL slope of THIS run's own Y11, via pi_model_fit.
    fit_arm_self_impedance() -- for 'arm_a'/'arm_b' this IS the arm's real
    self-impedance; for 'shorted' it's only an "effective" slope of Za_sc,
    not a true series R+L, since Za_sc's own frequency dependence isn't a
    simple pole -- kept anyway as a quick per-run sanity number, not a
    final result). The real combined 11-key (+ m/k) fit across all 3
    cached runs is done by tools/gf180mcu_spiral_diff_mutual_fit.py (an
    offline/cache-only combiner, same spirit as tools/
    gf180mcu_inductor_refit.py), which calls pi_model_fit.
    fit_mutual_inductance() directly against all 3 runs' raw cached Y11(f)
    -- NOT via this function -- then calls this SAME function again with
    em_result=None to get the geometry-only cox/rsub/etc, and overrides
    just 'l'/'rs'/'k_coupling' with the real fitted values.

    UNVALIDATED beyond geometry/unit-consistency review."""
    ct_xy, full_a, _edge_layers_a, full_b, _edge_layers_b = diff_spiral_arms(
        geometry["n_turns"], geometry["track_width_um"], geometry["spacing_um"], geometry["inner_diameter_um"])
    track_width_um = geometry["track_width_um"]

    def path_length(pts):
        return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))

    centerline_len_um = path_length(full_a) + path_length(full_b)
    trace_area_um2 = centerline_len_um * track_width_um
    trace_perimeter_um = 2 * centerline_len_um
    cox_total_f = (trace_area_um2 * stack["metal5_areacap_aF_per_um2"]
                   + trace_perimeter_um * stack["metal5_perimcap_aF_per_um"]) * 1e-18

    isosub_rsh = stack["substrate_isosub_sheet_r_ohm_per_sq"]
    rsub_geom = 4 * isosub_rsh * track_width_um / centerline_len_um
    rsub_ct_geom = 2 * isosub_rsh * track_width_um / centerline_len_um

    if em_result is not None:
        variant = geometry.get("variant")
        if variant not in ("arm_a", "arm_b", "shorted"):
            raise ValueError(
                f"fit_electrical_params(): em_result was given but geometry['variant'] is "
                f"{variant!r}, not one of 'arm_a'/'arm_b'/'shorted' -- a single FDTD run's Y11 is "
                f"always exactly one of the 3 open/short-circuit-test variants, see this "
                f"function's own docstring for why there is no other valid single-run em_result")
        rs_arm, l_arm = fit_arm_self_impedance(em_result["freqs"], em_result["y11"])
        return {"variant": variant, "rs_arm": rs_arm, "l_arm": l_arm}

    l_half = _PLACEHOLDER_L_HALF_H
    rs_half = _PLACEHOLDER_RS_HALF_OHM
    rsub = rsub_geom
    csub = _PLACEHOLDER_CSUB_F
    rp_eddy = 1e9
    lp_eddy = l_half

    return {
        "l": l_half,
        "rs": rs_half,
        "cox": cox_total_f / 4,
        "rsub": rsub,
        "csub": csub,
        "cs": _PLACEHOLDER_CSUB_F,
        "cox_ct": cox_total_f / 2,
        "rsub_ct": rsub_ct_geom,
        "csub_ct": 2 * csub,
        "rp_eddy": rp_eddy,
        "lp_eddy": lp_eddy,
        # No real EM mutual-inductance measurement on this (em_result=None)
        # path -- see this function's own docstring. Overridden by
        # tools/gf180mcu_spiral_diff_mutual_fit.py once a real 3-run fit
        # exists.
        "k_coupling": 0.0,
    }
