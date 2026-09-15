#!/usr/bin/env python3
"""
gf180mcu_inductor_refit.py -- re-fits a generator-backed inductor topology's
pi-model electrical params ('l','rs','cox','rsub','csub','cs') from an
ALREADY-CACHED openEMS Y11(f) sweep (the JSON run_one_openems()/
openems_generator_runner.py write, e.g. sim/<variation>/yparam_spiral/
corner-tt_.../result.json or the sibling <test>_0.json), WITHOUT touching
Docker/CSXCAD/openEMS at all -- fit_electrical_params()'s em_result branch
is pure numpy (see inductor_spiral_generator.py/inductor_loop_generator.py's
own docstrings), so this only needs the cached freqs/re/im arrays already on
disk. Lets you experiment with the fit (or a different Y11 sign convention)
in seconds, instead of re-running a multi-hour FDTD sim.

--------------------------------------------------------------------------
WHY THIS EXISTS
--------------------------------------------------------------------------
2026-09-15 investigation (see openems_inductor_status.md): a real FDTD run
of the 'loop' topology (100x50um/2um track) came back with Y11(f) that
looks capacitive from DC all the way to 20GHz (Im(Z11) negative, falling,
no self-resonance) -- inconsistent with a plain rectangular loop this size,
and matching the shape of the project's already-open "Q negative/
capacitive-looking" bug (previously only confirmed on the 'spiral'
topology's crossunder-bridged port). Flipping the conjugate applied to Y11
(un-doing openems_generator_runner.py's own np.conj(if_tot/uf_tot)) turns
that same cached data into a clean, monotonic, no-anomalies inductive
response (Im(Z11) rising smoothly, Q rising smoothly, no sign flips) --
strong evidence this is a sign-convention bug in the extraction, not real
substrate-dominated physics. --flip-sign below reproduces that test.

This script does NOT change openems_generator_runner.py itself (that file
lives in mh-analog-designer, out of scope here -- someone else may be
actively working on it) -- it's a read-only, cache-only diagnostic/refit
tool, same spirit as tools/gf180mcu_inductor_diag_*.py.
--------------------------------------------------------------------------
HOW TO RUN (no Docker/container needed at all)
--------------------------------------------------------------------------
  python tools/gf180mcu_inductor_refit.py \\
      --result-json sim/<variation>/yparam_spiral/corner-tt_.../result.json \\
      --out sim/<variation>/yparam_spiral/corner-tt_.../fitted.refit.json

Add --flip-sign to test the un-conjugated Y11 hypothesis instead of the
stored (conjugated) one. Add --plot-base <path prefix> to also regenerate
the Q/Z/fit-quality PNGs (reusing tb/inductor/tb_yparam_spiral.py's own
plotting functions) against whichever Y11 convention was used, so the two
hypotheses can be compared side by side without re-running anything.
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
_TB_INDUCTOR_DIR = _REPO_ROOT / "tb" / "inductor"
_TB_SHARED_DIR = _REPO_ROOT / "tb" / "_shared"

# Same discriminator tb_yparam_spiral.py's own _save_layout_plot() uses --
# each topology's geometry_from_params() has a distinct, non-overlapping
# free-parameter key set by construction.
_GENERATOR_BY_GEOMETRY_KEY = {
    "inner_radius_um": "inductor_spiral_generator.py",
    "width_um": "inductor_loop_generator.py",
}


def _load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_generator(geometry):
    for key, filename in _GENERATOR_BY_GEOMETRY_KEY.items():
        if key in geometry:
            return _load_module(_SCH_INDUCTOR_DIR / filename)
    raise ValueError(f"couldn't identify a generator for geometry keys {sorted(geometry)}")


def refit(result_json_path, corner="tt", flip_sign=False):
    """Returns (fitted_dict, geometry, freqs, y11) -- y11 is exactly what
    was fed to fit_electrical_params() (post-flip, if requested), so callers
    that also want plots can reuse it without recomputing."""
    with open(result_json_path) as f:
        cached = json.load(f)
    geometry = cached["geometry"]
    freqs = np.array(cached["freqs_hz"])
    y11 = np.array(cached["re"]) + 1j * np.array(cached["im"])
    if flip_sign:
        y11 = np.conj(y11)

    generator = _load_generator(geometry)
    stack = generator.load_stack(corner)
    fitted = generator.fit_electrical_params(geometry, stack, em_result={"freqs": freqs, "y11": y11})
    return fitted, geometry, freqs, y11


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--result-json", required=True, help="cached Y11 sweep JSON (freqs_hz/re/im/geometry keys)")
    p.add_argument("--corner", default="tt")
    p.add_argument("--flip-sign", action="store_true",
                    help="test the un-conjugated Y11 hypothesis instead of the stored (conjugated) one")
    p.add_argument("--out", help="where to write the refit params.json (default: print to stdout only)")
    p.add_argument("--plot-base", help="also (re)generate <plot-base>.png/__z.png/__fit.png via "
                                        "tb_yparam_spiral.py's own plotting functions")
    args = p.parse_args()

    fitted, geometry, freqs, y11 = refit(args.result_json, corner=args.corner, flip_sign=args.flip_sign)

    print(f"geometry: {geometry}")
    print(f"flip_sign={args.flip_sign}")
    print(json.dumps(fitted, indent=2))

    if args.out:
        with open(args.out, "w") as f:
            json.dump(fitted, f, indent=2)
        print(f"\nwrote {args.out}")

    if args.plot_base:
        sys.path.insert(0, str(_TB_INDUCTOR_DIR))
        sys.path.insert(0, str(_TB_SHARED_DIR))
        tb_yparam_spiral = _load_module(_TB_INDUCTOR_DIR / "tb_yparam_spiral.py")
        re_vals, im_vals = y11.real.tolist(), y11.imag.tolist()
        w = 2 * np.pi * freqs
        q = (-y11.imag / y11.real).tolist()
        run = {
            "freqs": freqs.tolist(), "re": re_vals, "im": im_vals, "q": q,
            "geometry": geometry, "field_png": None, "fitted": fitted,
        }
        tb_yparam_spiral._save_qf_plot([run], f"{args.plot_base}.png")
        tb_yparam_spiral._save_z_plot([run], f"{args.plot_base}__z.png")
        tb_yparam_spiral._save_fit_plot([run], f"{args.plot_base}__fit.png")
        print(f"\nplots written: {args.plot_base}.png / __z.png / __fit.png")


if __name__ == "__main__":
    main()
