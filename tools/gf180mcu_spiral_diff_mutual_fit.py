#!/usr/bin/env python3
"""
gf180mcu_spiral_diff_mutual_fit.py -- combines the 'spiral_diff' topology's 3
SEPARATE cached openEMS Y11(f) sweeps (arm_a alone, arm_b alone, full
structure with arm B shorted to ct -- the "open/short-circuit transformer
test" method, see inductor_spiral_diff_generator.py's own module docstring
for the full physical justification) into ONE final pi-model params.json,
WITHOUT touching Docker/CSXCAD/openEMS at all -- same "cache-only, seconds
not hours" spirit as tools/gf180mcu_inductor_refit.py.

--------------------------------------------------------------------------
WHY THIS EXISTS AS A SEPARATE TOOL, NOT PART OF THE GENERIC RUNNER
--------------------------------------------------------------------------
Every other generator-backed inductor topology ('spiral', 'loop') gets its
full pi-model from exactly ONE openEMS run: analog_designer_core's generic
openems_generator_runner.py calls build_openems_structure() once, gets one
Y11(f) sweep, and fit_electrical_params(geometry, stack, em_result) turns
that single sweep directly into the final params.json. 'spiral_diff' cannot
work that way -- a single-port measurement of this topology's Y-shaped
3-terminal winding cannot separate the two arms' self-inductances (la, lb)
from their mutual inductance (m) (see inductor_spiral_diff_generator.py's
own docstring for why an earlier, simpler "bridge the two arms' far pads
directly" attempt was confirmed invalid). The fix needs 3 INDEPENDENT FDTD
runs (each its own geometry['variant'], each its own call to the SAME
generic runner, each producing its own ordinary cached result.json) and a
combining step across all 3 -- this script is that combining step, kept
separate from the generic runner (out of scope here, shared across
projects, per gf180mcu_inductor_refit.py's own precedent) and separate from
inductor_spiral_diff_generator.py's own fit_electrical_params() (which only
ever sees ONE run at a time, and says so in its own docstring).

--------------------------------------------------------------------------
HOW TO RUN (no Docker/container needed at all, once the 3 runs exist)
--------------------------------------------------------------------------
  python tools/gf180mcu_spiral_diff_mutual_fit.py \\
      --arm-a-json sim/<variation>/.../arm_a/result.json \\
      --arm-b-json sim/<variation>/.../arm_b/result.json \\
      --shorted-json sim/<variation>/.../shorted/result.json \\
      --out sim/<variation>/.../fitted.combined.json

Add --plot-base <path prefix> to also render a Q/Z diagnostic plot of all 3
raw sweeps together (does NOT reuse tb_yparam_em.py's own plotting
functions -- those assume ONE run's Y11 is the device's own Y11, which
isn't true for any of these 3 variants individually).
--------------------------------------------------------------------------
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCH_INDUCTOR_DIR = _REPO_ROOT / "sch" / "inductor"

sys.path.insert(0, str(_SCH_INDUCTOR_DIR))
from pi_model_fit import fit_mutual_inductance  # noqa: E402 (path setup must come first)

# Geometry keys that must exactly match across all 3 runs (everything
# EXCEPT 'variant', which is the one key that's SUPPOSED to differ between
# them) -- a mismatch here would mean the 3 runs weren't actually of the
# same device, silently invalidating the whole combination below.
_SHARED_GEOMETRY_KEYS = (
    "n_turns", "spacing_um", "track_width_um", "inner_diameter_um", "tab_length_um", "port_spacing_um")


def _load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_cached_run(path, expected_variant):
    with open(path) as f:
        cached = json.load(f)
    geometry = cached["geometry"]
    actual_variant = geometry.get("variant")
    if actual_variant != expected_variant:
        raise ValueError(
            f"{path}: expected a {expected_variant!r} run but its own cached geometry says "
            f"variant={actual_variant!r} -- wrong file passed to --{expected_variant.replace('_', '-')}-json?")
    freqs = np.array(cached["freqs_hz"])
    y11 = np.array(cached["re"]) + 1j * np.array(cached["im"])
    return geometry, freqs, y11


def combine(arm_a_json, arm_b_json, shorted_json, corner="tt"):
    """Returns (fitted, mutual, geometry) -- fitted is the final 11-key (+
    'k_coupling') pi-model dict inductor_spiral_diff.sch's own
    substitute_params() tokens expect; mutual is fit_mutual_inductance()'s
    own raw returned dict (ra/la/rb/lb/m/k/m2_values), kept separate since
    ra/rb/la/lb individually (not just their average) are useful for
    sanity-checking the mirror-symmetry assumption (la should be close to
    lb -- see this module's own docstring); geometry is the shared 6-key
    free-geometry dict (variant stripped), for logging/plotting."""
    geom_a, freqs_a, y11_a = _load_cached_run(arm_a_json, "arm_a")
    geom_b, freqs_b, y11_b = _load_cached_run(arm_b_json, "arm_b")
    geom_sc, freqs_sc, y11_sc = _load_cached_run(shorted_json, "shorted")

    for key in _SHARED_GEOMETRY_KEYS:
        vals = {geom_a[key], geom_b[key], geom_sc[key]}
        if len(vals) != 1:
            raise ValueError(
                f"geometry mismatch across the 3 runs on {key!r}: arm_a={geom_a[key]!r}, "
                f"arm_b={geom_b[key]!r}, shorted={geom_sc[key]!r} -- these must be the SAME device, "
                f"just 3 different measurement variants, or the combination below is meaningless")
    geometry = {key: geom_a[key] for key in _SHARED_GEOMETRY_KEYS}

    mutual = fit_mutual_inductance(freqs_a, y11_a, freqs_b, y11_b, freqs_sc, y11_sc)

    if abs(mutual["la"] - mutual["lb"]) / max(mutual["la"], mutual["lb"]) > 0.1:
        print(
            f"WARNING: la={mutual['la']:.4g}H and lb={mutual['lb']:.4g}H differ by more than 10% -- "
            f"the winding is a mirror construction and expected to be close; a larger gap suggests a "
            f"meshing/geometry asymmetry worth checking before trusting this fit", file=sys.stderr)

    generator = _load_module(_SCH_INDUCTOR_DIR / "inductor_spiral_diff_generator.py")
    stack = generator.load_stack(corner)
    # em_result=None: only the geometry-based cox/rsub/csub/etc (see that
    # function's own docstring for why it can't do the real 'l'/'rs'/
    # 'k_coupling' fit itself -- that's exactly this script's job).
    fitted = generator.fit_electrical_params(geometry, stack, em_result=None)
    fitted["l"] = (mutual["la"] + mutual["lb"]) / 2
    fitted["rs"] = (mutual["ra"] + mutual["rb"]) / 2
    fitted["k_coupling"] = mutual["k"]

    return fitted, mutual, geometry


def _save_diagnostic_plot(arm_a_json, arm_b_json, shorted_json, mutual, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _, freqs_a, y11_a = _load_cached_run(arm_a_json, "arm_a")
    _, freqs_b, y11_b = _load_cached_run(arm_b_json, "arm_b")
    _, freqs_sc, y11_sc = _load_cached_run(shorted_json, "shorted")

    fig, (ax_re, ax_im) = plt.subplots(2, 1, figsize=(5, 6), sharex=True)
    for label, freqs, y11 in (("arm_a", freqs_a, y11_a), ("arm_b", freqs_b, y11_b), ("shorted", freqs_sc, y11_sc)):
        z = 1.0 / y11
        freqs_ghz = freqs / 1e9
        ax_re.plot(freqs_ghz, z.real, label=f"Re(Z) {label}")
        ax_im.plot(freqs_ghz, z.imag, label=f"Im(Z) {label}")
    ax_im.set_xscale("log")
    ax_re.set_ylabel("Re(Z) (ohm)")
    ax_im.set_ylabel("Im(Z) (ohm)")
    ax_im.set_xlabel("frequency (GHz)")
    ax_re.legend(fontsize=7)
    ax_im.legend(fontsize=7)
    ax_re.set_title(f"la={mutual['la']:.3g}H, lb={mutual['lb']:.3g}H, m={mutual['m']:.3g}H, k={mutual['k']:.3g}",
                     fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arm-a-json", required=True, help="cached result.json from the 'arm_a' variant run")
    p.add_argument("--arm-b-json", required=True, help="cached result.json from the 'arm_b' variant run")
    p.add_argument("--shorted-json", required=True, help="cached result.json from the 'shorted' variant run")
    p.add_argument("--corner", default="tt")
    p.add_argument("--out", help="where to write the combined fitted params.json (default: print to stdout only)")
    p.add_argument("--plot-base", help="also write <plot-base>__mutual.png, a Re/Im(Z) overlay of all 3 raw runs")
    args = p.parse_args()

    fitted, mutual, geometry = combine(args.arm_a_json, args.arm_b_json, args.shorted_json, corner=args.corner)

    print(f"geometry: {geometry}")
    print(f"ra={mutual['ra']:.6g} ohm, la={mutual['la']:.6g} H")
    print(f"rb={mutual['rb']:.6g} ohm, lb={mutual['lb']:.6g} H")
    print(f"m={mutual['m']:.6g} H, k={mutual['k']:.6g}")
    print("combined fitted params:")
    print(json.dumps(fitted, indent=2))

    if args.out:
        with open(args.out, "w") as f:
            json.dump(fitted, f, indent=2)
        print(f"\nwrote {args.out}")

    if args.plot_base:
        plot_path = f"{args.plot_base}__mutual.png"
        _save_diagnostic_plot(args.arm_a_json, args.arm_b_json, args.shorted_json, mutual, plot_path)
        print(f"\nplot written: {plot_path}")


if __name__ == "__main__":
    main()
