"""Generic testbench-parser helpers shared across every block (vco, top,
...) -- copied from ihp_mh_ip__cmos_vref/tb/_shared/parser_common.py (same
mh-analog-designer-lite workflow, PDK-agnostic helpers). Loaded via
analog_designer.sim.run_sim.load_parser() putting this directory on
sys.path alongside each parser's own directory."""
import re

_SI_SUFFIXES = {"": 1, "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6,
                "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}


def read_data(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append([float(x) for x in line.split()])
    return rows


def regulation_pct(values):
    """Box-method regulation: (max-min)/|nominal| * 100, nominal = midpoint of the
    swept values. abs() on the midpoint keeps this a magnitude -- without it, an
    output that's off badly enough to swing through zero across the sweep gets a
    negative nominal, which sign-flips the result into a small-looking negative
    percentage instead of the large one that swing actually represents (other
    conditions of the same brokenness, where nominal happens to stay positive,
    already report a large positive percentage for the same underlying problem)."""
    nom = abs((max(values) + min(values)) / 2)
    return (max(values) - min(values)) / nom * 100


def in_spec(value, spec):
    if "minimum" in spec and value < spec["minimum"]:
        return False
    if "maximum" in spec and value > spec["maximum"]:
        return False
    return True


def typical_min_max(runs, typical, value_of, match_keys=("corner", "temperature")):
    """{"typical","min","max"} for one metric, reduced from a flat `runs`
    list (each already tagged with its own "conditions" dict) the same way
    every parser needs now that a test reports both its nominal value and
    its worst-case spread as one metric, instead of picking just one or
    splitting into separately-named metrics.

    `typical` is run_sim.typical_conditions()'s return value -- a
    defaults-shaped dict naming the nominal value of every axis this
    project knows about, a strict superset of whatever axes THIS test
    actually varies. The match is restricted to match_keys (default
    corner+temperature, the only two outer axes any current test varies)
    and, within those, to whichever keys are actually present in a given
    run's own conditions -- a run whose test excludes an axis from its
    outer grid entirely (e.g. temperature swept internally in one run
    rather than across runs) just skips that key rather than failing to
    match on it.

    Exactly one run is expected to match. Anything else raises rather than
    silently picking a run -- a wrong pick here could corrupt a cross_block
    sizing reference (see run_sim.resolve_cross_block_metrics())."""
    matches = [
        r for r in runs
        if all(r["conditions"].get(k) == typical.get(k) for k in match_keys if k in r["conditions"])
    ]
    if len(matches) != 1:
        raise ValueError(
            f"typical_min_max: expected exactly one run matching typical conditions "
            f"{({k: typical.get(k) for k in match_keys})!r}, found {len(matches)} "
            f"among {[r['conditions'] for r in runs]!r}"
        )
    values = [value_of(r) for r in runs]
    return {"typical": value_of(matches[0]), "min": min(values), "max": max(values)}


def value_at(xs, ys, target):
    """ys[i] where xs[i] is closest to target -- the "closest sampled
    point" pick an internal-sweep test (temperature via .dc, e.g.) uses to
    read a value at one nominal point when the sweep's own sample grid may
    not land exactly on it."""
    idx = min(range(len(xs)), key=lambda i: abs(xs[i] - target))
    return ys[idx]


def mc_stats(runs, value_of):
    """{"typical", "mean", "std", "min", "max"} across a Monte Carlo sweep
    -- every run in `runs` is an independent random draw (device mismatch
    or global-process variation, see run_sim.py's mos_tt_mismatch/mos_tt_stat
    corners) at the SAME nominal conditions, varying only by which seed the
    PDK's agauss()/gauss() calls happened to draw for that particular
    ngspice process -- unlike typical_min_max()'s corner/temperature sweep,
    no single run is more "typical" than any other.

    "typical" is deliberately left None rather than faked as the mean or
    an arbitrary sample -- callers (fom.py's metrics_to_variables(), the
    GUI) already treat a None typical as "no single representative value"
    (same convention tb_vref_temp_sweep.py's own out-of-range coefficient
    metrics already use). "std" is the sample standard deviation (N-1
    denominator, the unbiased estimator) -- 0.0 for a single-run "sweep"
    rather than a division-by-zero, since a batch of exactly one sample has
    no useful spread to report but shouldn't crash callers that always
    expect a float."""
    values = [value_of(r) for r in runs]
    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    return {"typical": None, "mean": mean, "std": variance ** 0.5, "min": min(values), "max": max(values)}


def legend_if_any(ax, **kwargs):
    """ax.legend() warns and draws an empty box when nothing has a label
    (e.g. every spec bound was off-scale and got annotated as text instead)."""
    handles, _ = ax.get_legend_handles_labels()
    if handles:
        ax.legend(**kwargs)


def si_to_float(text):
    m = re.fullmatch(r"([0-9.eE+-]+)([a-zA-Z]*)", text)
    if not m or m.group(2).lower() not in _SI_SUFFIXES:
        raise ValueError(f"not a SPICE numeric literal: {text!r}")
    return float(m.group(1)) * _SI_SUFFIXES[m.group(2).lower()]


def parse_sized_devices(netlist_text):
    """Every X-instance line in an xschem-expanded netlist that carries both
    w= and l= parameters -- i.e. a sized primitive device (MOS, MiM cap,
    poly resistor, ...) as opposed to a pure subcircuit-wiring X-line (no
    w=/l=), which is skipped. Line shape: `X<name> <pin> ... <model>
    <key>=<value> ...` -- the model name is whatever token sits right
    before the first key=value pair. Returns [{"instance", "model", "w",
    "l" (meters), "m", "ng" (default 1 when absent)}, ...]."""
    devices = []
    for line in netlist_text.splitlines():
        line = line.strip()
        if not line.startswith("X"):
            continue
        tokens = line.split()
        first_param = next((i for i, t in enumerate(tokens) if "=" in t), None)
        if first_param is None or first_param < 2:
            continue
        params = {}
        for tok in tokens[first_param:]:
            if "=" not in tok:
                continue
            key, val = tok.split("=", 1)
            try:
                params[key.lower()] = si_to_float(val)
            except ValueError:
                continue
        if "w" not in params or "l" not in params:
            continue
        devices.append({
            "instance": tokens[0],
            "model": tokens[first_param - 1],
            "w": params["w"],
            "l": params["l"],
            "m": params.get("m", 1),
            "ng": params.get("ng", params.get("nf", 1)),
        })
    return devices


def estimate_area_um2(netlist_text, overhead_factor):
    """Schematic-only area proxy, no layout involved: sum(w*l*ng*m) over
    every sized device in the netlist gives raw active/plate area; ng is
    assumed to multiply like BSIM's nf (w = per-finger width) -- correct
    this if a given device model's convention differs. overhead_factor
    scales that up to approximate what wells, guard rings and routing add
    in a real placed-and-routed layout. Only meaningful for RANKING
    variations of the same topology against each other -- not a substitute
    for an actual layout's mm^2 figure."""
    devices = parse_sized_devices(netlist_text)
    active_area_um2 = sum(d["w"] * d["l"] * d["ng"] * d["m"] for d in devices) * 1e12
    return {
        "device_count": len(devices),
        "active_area_um2": active_area_um2,
        "estimated_area_um2": active_area_um2 * overhead_factor,
    }


def add_spec_bounds(ax, values, spec, orientation="y"):
    """Draw min/max spec reference lines, but only if they fall within a
    sane margin of the actual plotted data. A spec bound that's orders of
    magnitude away from the data would otherwise force the axis to stretch
    until the real curve/bars are indistinguishable from zero -- in that
    case just note it as text instead of drawing a line."""
    lo, hi = min(values), max(values)
    span = (hi - lo) or abs(hi) or 1.0
    margin = span * 0.15
    view_lo, view_hi = lo - margin, hi + margin

    line_fn = ax.axhline if orientation == "y" else ax.axvline
    styles = {"minimum": "--", "maximum": ":"}
    notes = []
    for key, style in styles.items():
        if key not in spec:
            continue
        bound = spec[key]
        if view_lo <= bound <= view_hi:
            line_fn(bound, color="black", linestyle=style, linewidth=1, label=key)
        else:
            notes.append(f"{key}: {bound} {spec.get('unit', '')} (off scale)")

    if orientation == "y":
        ax.set_ylim(view_lo, view_hi)
    else:
        ax.set_xlim(view_lo, view_hi)

    if notes:
        ax.text(
            0.02, 0.98, "\n".join(notes), transform=ax.transAxes,
            va="top", ha="left", fontsize=7,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.85, edgecolor="gray"),
        )
