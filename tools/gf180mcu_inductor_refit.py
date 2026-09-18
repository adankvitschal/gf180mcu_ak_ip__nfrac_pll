#!/usr/bin/env python3
"""
gf180mcu_inductor_refit.py -- re-fits a generator-backed inductor topology's
pi-model electrical params ('l','rs','cox','rsub','csub','cs') from an
ALREADY-CACHED openEMS Y11(f) sweep (the JSON run_one_openems()/
openems_generator_runner.py write, e.g. sim/<variation>/yparam_em/
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
      --result-json sim/<variation>/yparam_em/corner-tt_.../result.json \\
      --out sim/<variation>/yparam_em/corner-tt_.../fitted.refit.json

Add --flip-sign to test the un-conjugated Y11 hypothesis instead of the
stored (conjugated) one. Add --plot-base <path prefix> to also regenerate
the Q/Z/fit-quality PNGs (reusing tb/inductor/tb_yparam_em.py's own
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
from scipy.optimize import least_squares

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCH_INDUCTOR_DIR = _REPO_ROOT / "sch" / "inductor"
_TB_INDUCTOR_DIR = _REPO_ROOT / "tb" / "inductor"
_TB_SHARED_DIR = _REPO_ROOT / "tb" / "_shared"

sys.path.insert(0, str(_SCH_INDUCTOR_DIR))
from pi_model_fit import (  # noqa: E402  (path setup must come first)
    assert_ct_tap_unobservable,
    find_resonance_hz,
    y11_two_tap_pi_model,
)

# Kept under its old name for every existing call site/CLI output in this
# file -- pi_model_fit.py is the real, single source of truth now (moved
# there 2026-09-15 planning session, see that module's own docstring for
# why: this is fit LOGIC, not a simple constant, so duplicating it between
# here and the generator risked silent drift).
y11_full_pi_model = y11_two_tap_pi_model

# Same discriminator tb_yparam_em.py's own _save_layout_plot() uses --
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


def full_refit(result_json_path, corner="tt", flip_sign=False, max_freq_hz=None,
                fix_rs_l=False, fix_cox=False, fix_cs_zero=False):
    """Joint nonlinear least-squares fit of ALL 6 pi-model parameters at
    once against the cached Y11(f) sweep, using y11_full_pi_model() above --
    an alternative to fit_electrical_params()'s current low-frequency-
    slope-only Rs+jwL fit (which leaves cox as a pure-geometry estimate and
    rsub/csub/cs as fixed placeholders, never touched by any EM data).
    Returns (fitted_dict, geometry, freqs, y11, simple_fitted_dict,
    opt_result) -- freqs/y11 are always the FULL sweep (for plotting/
    comparison against the whole band, including whatever the fit was NOT
    given to see), even when max_freq_hz restricts what's actually fit
    against; simple_fitted_dict is the EXISTING fit (same em_result),
    included so callers can compare without a second cache read;
    opt_result is scipy's own OptimizeResult for diagnosing a bad fit.

    max_freq_hz=None (default): fit against the WHOLE sweep -- see the
    "HONEST RESULT" section below, this doesn't work well. max_freq_hz=<Hz>:
    fit ONLY the points at or below that frequency (see --near-resonance,
    which sets this to 2x find_resonance_hz()'s own data-driven estimate) --
    a 2026-09-15 user request to prioritize matching the behavior around
    and below the resonance peak specifically, rather than the whole
    1MHz-20GHz band including a high-frequency tail this lumped topology
    was never expected to represent well anyway (see the "Conclusion" below).

    Initial guess / bounds: rs/l seeded from the existing simple fit (a
    good low-frequency estimate to start from), cox seeded from its own
    real-geometry value (already trustworthy, no EM data needed for it),
    rsub/csub/cs seeded from the same generic placeholder constants
    fit_electrical_params() itself falls back to -- all 6 bounded to stay
    positive (and generously wide otherwise) since every one of them is a
    physical R/L/C magnitude, never legitimately negative in this model.

    Residuals are weighted by 1/|Y11_data| (relative error, both real and
    imaginary parts) -- Re(Y11) alone spans over an order of magnitude
    across a typical sweep, so raw absolute-difference weighting would let
    the low-frequency points swamp everything else.

    HONEST RESULT, not yet solved (2026-09-15, see openems_inductor_status.md
    and this session's own conversation history): this joint fit does NOT
    beat fit_electrical_params()'s existing low-frequency-slope-only fit on
    the one real dataset tested so far (100x50um/2um loop, flip-sign
    hypothesis) -- it's WORSE almost everywhere, for a marginal gain
    nowhere. Three weighting schemes were tried and none fixed it:
      1. Plain 1/|Y11| relative weight, equal per (linearly-spaced) point
         (what's used now): full-band RMS relative error ~40%, roughly
         tied with the simple fit's own ~42% -- but the simple fit ties
         that WITHOUT EVEN TRYING past its lowest ~10 points, while this
         one is actively fitting across all 201 and still can't do much
         better in aggregate, and is meaningfully WORSE specifically in the
         low-frequency window that matters most for Rs/L (16% vs. the
         simple fit's 1.6%).
      2. Log-spaced resample (to fix point-count bias toward the crowded
         high-frequency region): made it WORSE (56% full-band) -- root
         cause: interpolating onto log-spaced points invents data where
         none exists (confirmed: 28 of 60 log-spaced points below 20GHz
         fell between just the sweep's first TWO real samples, 1MHz and
         101MHz, since run_and_extract() samples freqs LINEARLY -- half the
         'data' fit there was a straight-line fabrication across a 100MHz
         gap, not real EM data).
      3. 1/f weight on the REAL points (same "equal weight per decade"
         intent, d(log f)=df/f, without inventing data): made it WORSE
         STILL (76% full-band, 82% specifically >5GHz) -- overcorrected,
         converged in 8 function evals barely past the initial guess,
         because 1/f so overwhelmingly favors the single lowest-frequency
         point that everything above a few MHz became numerically
         irrelevant to the cost.
    Conclusion so far: this doesn't look like a weighting-scheme problem at
    all -- it looks like this SPECIFIC lumped topology (two terminal-lumped
    Cox-Rsub-Csub branches to a shared floating node, see
    y11_full_pi_model()'s own docstring) may not have the right functional
    shape to represent a loop this electrically large across 1MHz-20GHz,
    REGARDLESS of how the optimization weights different frequencies --
    real distributed coupling along the whole trace length, not just two
    lumped terminal branches, may be needed. Kept as plain relative
    weighting (option 1, the least-bad of the three) since there's no
    principled reason to prefer either failed alternative over it.

    2026-09-15, 4th attempt (--near-resonance): instead of reweighting the
    WHOLE band again, just don't ask the fit to match the part nobody
    expects a 2-lumped-branch topology to get right in the first place --
    restrict the actual optimization to freqs <= max_freq_hz, still with
    plain 1/|Y11| relative weighting (the one weighting scheme that wasn't
    actively harmful) on whatever points ARE included.

    RESULT: genuinely better where it matters, but with a visible trade-off
    -- restricting to freqs<=2x the data's own resonance frequency did NOT
    beat the simple fit in aggregate RMS (20.8% vs. simple's 15.9%, even
    within the fit range), but visually the Im(Y11) resonance DIP's
    location/depth tracked far better than the simple fit's own badly-
    overshot dip -- the aggregate number was dragged down by a NEW
    Rs-accuracy trade-off (Re(Y11) came out ~20% low at DC, since the
    optimizer was free to trade Rs/L accuracy for a better resonance-region
    match). Led directly to fix_rs_l below.

    2026-09-15, 5th attempt (fix_rs_l=True, --fix-rs-l): hold rs/l FIXED at
    the simple fit's own (already-good, 1.6% low-f error) values -- don't
    let the optimizer barter away the one thing it already gets right --
    and let ONLY cox/rsub/csub/cs float, targeting the resonance region's
    shape specifically without a DC-accuracy trade-off available to spend.
    RESULT: genuinely beats the simple fit in the fit range (10.3% vs.
    15.9%), at the cost of wild (expected, accepted) extrapolation outside
    it. BUT: cox/csub/cs all landed far from their geometry/placeholder
    estimates (cox 30x, csub ~1580x, cs ~9x) -- a real curve-fit win, but
    a classic sign of parameter NON-IDENTIFIABILITY: 4 free params
    constrained by one blended resonance feature can trade off against
    each other into many similarly-good-looking combinations, not
    necessarily the physically correct one.

    2026-09-15, 6th attempt (fix_cox=True, fix_cs_zero=True, --physics-informed):
    per-element physics-informed reasoning instead of letting the optimizer
    use every element as a free knob -- 'cox' is already independently
    trustworthy (real geometry x GF180MCU areacap data, no EM fit needed at
    all, see fit_electrical_params()'s own docstring), so hold it fixed
    too, not just rs/l. 'cs' (bypass cap directly across each half's own
    Rs+Ls) has no clear physical mechanism for a SINGLE-TURN loop
    specifically (unlike a multi-turn spiral, where adjacent-turn coupling
    is a real, expected effect) -- fix it at exactly 0 rather than let it
    keep absorbing curve-fit error with no physical story behind the
    number. That leaves ONLY rsub/csub genuinely free -- the two elements
    this one-port measurement can plausibly constrain independently,
    matching standard on-chip-inductor pi-model extraction practice
    (Rs/Ls from low-f asymptote, Cox from geometry, Rsub/Csub from the
    resonance region) rather than one large blind joint optimization."""
    fitted_simple, geometry, freqs, y11 = refit(result_json_path, corner=corner, flip_sign=flip_sign)

    if max_freq_hz is not None:
        fit_mask = freqs <= max_freq_hz
    else:
        fit_mask = np.ones(len(freqs), dtype=bool)
    freqs_fit, y11_fit = freqs[fit_mask], y11[fit_mask]

    # Build the free/fixed parameter split generically: rs/l/cox/cs can each
    # independently be held fixed (at the simple fit's own value, or 0 for
    # cs) -- rsub/csub are always free, they're what this one-port
    # measurement can plausibly constrain on its own.
    names = ["rs", "l", "cox", "rsub", "csub", "cs"]
    fixed_at = {}
    if fix_rs_l:
        fixed_at["rs"] = fitted_simple["rs"]
        fixed_at["l"] = abs(fitted_simple["l"])
    if fix_cox:
        fixed_at["cox"] = fitted_simple["cox"]
    if fix_cs_zero:
        fixed_at["cs"] = 0.0
    free_names = [n for n in names if n not in fixed_at]

    all_lo = {"rs": 1e-6, "l": 1e-15, "cox": 1e-18, "rsub": 1e-3, "csub": 0.0, "cs": 0.0}
    all_hi = {"rs": 1e4, "l": 1e-6, "cox": 1e-9, "rsub": 1e6, "csub": 1e-9, "cs": 1e-9}
    x0_all = {"rs": fitted_simple["rs"], "l": abs(fitted_simple["l"]), "cox": fitted_simple["cox"],
              "rsub": fitted_simple["rsub"], "csub": fitted_simple["csub"], "cs": fitted_simple["cs"]}

    x0 = np.clip(np.array([x0_all[n] for n in free_names]),
                 np.array([all_lo[n] for n in free_names]) * 1.001,
                 np.array([all_hi[n] for n in free_names]) * 0.999)
    lo = np.array([all_lo[n] for n in free_names])
    hi = np.array([all_hi[n] for n in free_names])

    def residuals(x):
        values = dict(fixed_at)
        values.update(zip(free_names, x))
        y_model = y11_full_pi_model(freqs_fit, values["rs"], values["l"], values["cox"],
                                     values["rsub"], values["csub"], values["cs"])
        err = (y_model - y11_fit) / np.abs(y11_fit)
        return np.concatenate([err.real, err.imag])

    # x_scale='jac': REQUIRED once few enough params stay free that their
    # magnitudes can differ wildly (e.g. rsub ~ohms vs. csub ~1e-13F, 14
    # orders of magnitude apart, in --physics-informed) -- without it,
    # scipy's default per-variable scaling badly under-scales the tiny-
    # magnitude variable's own gradient contribution, and 'trf' can
    # falsely report gtol convergence after a single function evaluation
    # with that variable never actually having moved (confirmed: a first
    # attempt at fix_cox+fix_cs_zero together did exactly this, rsub
    # landing EXACTLY at its unchanged initial guess).
    opt_result = least_squares(residuals, x0, bounds=(lo, hi), method="trf", x_scale="jac", max_nfev=5000)
    values = dict(fixed_at)
    values.update(zip(free_names, opt_result.x))
    fitted_full = {n: float(values[n]) for n in names}
    return fitted_full, geometry, freqs, y11, fitted_simple, opt_result


def _save_full_fit_plot(freqs, y11, fitted_simple, fitted_full, path, max_freq_hz=None):
    """Re(Y11)/Im(Y11) vs frequency (log-x, same reasoning as
    tb_yparam_em.py's own plots -- the interesting behavior sits in the
    lowest ~5% of a typical sweep): raw EM data vs. the simple Rs+jwL-only
    fit (fit_electrical_params()'s current approach, ignores cox/rsub/
    csub/cs entirely) vs. the full 6-parameter joint pi-model fit
    (y11_full_pi_model()) -- lets you see directly whether the extra
    branches actually buy a better match across the WHOLE band, not just
    near DC. max_freq_hz (set when full_refit() was called with it, e.g.
    via --near-resonance) shades the region actually fit against -- past
    that line the full-pi curve is pure extrapolation, not fitted."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    freqs_ghz = freqs / 1e9
    w = 2 * np.pi * freqs
    y_simple = 1.0 / (2 * fitted_simple["rs"] + 1j * w * 2 * fitted_simple["l"])
    y_full = y11_full_pi_model(
        freqs, fitted_full["rs"], fitted_full["l"], fitted_full["cox"],
        fitted_full["rsub"], fitted_full["csub"], fitted_full["cs"],
    )

    fig, (ax_re, ax_im) = plt.subplots(2, 1, figsize=(5, 6), sharex=True)
    if max_freq_hz is not None:
        for ax in (ax_re, ax_im):
            ax.axvspan(freqs_ghz[0], max_freq_hz / 1e9, color="gray", alpha=0.15,
                       label="fit range" if ax is ax_re else None)
    ax_re.plot(freqs_ghz, y11.real, color="black", label="Re(Y11) EM")
    ax_re.plot(freqs_ghz, y_simple.real, "--", color="tab:blue", alpha=0.8, label="Re(Y11) Rs+jwL only")
    ax_re.plot(freqs_ghz, y_full.real, "--", color="tab:red", alpha=0.8, label="Re(Y11) full pi-model")
    ax_im.plot(freqs_ghz, y11.imag, color="black", label="Im(Y11) EM")
    ax_im.plot(freqs_ghz, y_simple.imag, "--", color="tab:blue", alpha=0.8, label="Im(Y11) Rs+jwL only")
    ax_im.plot(freqs_ghz, y_full.imag, "--", color="tab:red", alpha=0.8, label="Im(Y11) full pi-model")

    ax_im.set_xscale("log")
    ax_re.set_ylabel("Re(Y11) (S)")
    ax_im.set_ylabel("Im(Y11) (S)")
    ax_im.set_xlabel("frequency (GHz)")
    ax_re.legend(fontsize=7)
    ax_im.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check-ct-tap-invisible", action="store_true",
                    help="run pi_model_fit.py's assert_ct_tap_unobservable() regression check and exit -- "
                         "ignores every other argument (no --result-json needed, this is a pure synthetic "
                         "check that a third substrate branch at 'ct' cannot move Y11, regardless of its "
                         "own element values -- see the 2026-09-15 planning session's finding)")
    p.add_argument("--result-json", help="cached Y11 sweep JSON (freqs_hz/re/im/geometry keys)")
    p.add_argument("--corner", default="tt")
    p.add_argument("--flip-sign", action="store_true",
                    help="test the un-conjugated Y11 hypothesis instead of the stored (conjugated) one")
    p.add_argument("--out", help="where to write the refit params.json (default: print to stdout only)")
    p.add_argument("--full-fit", action="store_true",
                    help="joint nonlinear least-squares fit of all 6 pi-model params (rs/l/cox/rsub/csub/cs) "
                         "against the WHOLE sweep, via y11_full_pi_model() -- instead of the simple "
                         "low-frequency-slope-only Rs+jwL fit_electrical_params() does today")
    p.add_argument("--near-resonance", action="store_true",
                    help="with --full-fit, restrict the fit to freqs <= 2x the data's own peak-|Im(Y11)| "
                         "frequency (find_resonance_hz()) instead of the whole sweep -- prioritizes matching "
                         "the behavior around and below resonance over the high-frequency tail")
    p.add_argument("--fix-rs-l", action="store_true",
                    help="with --full-fit, hold rs/l fixed at the simple fit's own values and only let "
                         "cox/rsub/csub/cs float -- prevents the optimizer trading away DC/Rs accuracy to "
                         "buy a better resonance-region match (see full_refit()'s own docstring, 5th attempt)")
    p.add_argument("--physics-informed", action="store_true",
                    help="with --full-fit, shorthand for --fix-rs-l + also hold cox fixed at its own "
                         "geometry-based estimate + fix cs=0 (no clear physical mechanism for a single-turn "
                         "loop) -- only rsub/csub genuinely float, the two elements a one-port EM measurement "
                         "can plausibly constrain on their own (see full_refit()'s own docstring, 6th attempt)")
    p.add_argument("--plot-base", help="also (re)generate <plot-base>.png/__z.png/__fit.png via "
                                        "tb_yparam_em.py's own plotting functions (or, with --full-fit, "
                                        "<plot-base>__fullfit.png comparing EM vs. simple vs. full-model fits)")
    args = p.parse_args()

    if args.check_ct_tap_invisible:
        assert_ct_tap_unobservable()
        print("OK -- a third ct<->sub substrate branch is confirmed invisible to Y11 (see pi_model_fit.py)")
        return

    if not args.result_json:
        p.error("--result-json is required unless --check-ct-tap-invisible is given")

    if args.full_fit:
        max_freq_hz = None
        if args.near_resonance:
            _, _, freqs_peek, y11_peek = refit(args.result_json, corner=args.corner, flip_sign=args.flip_sign)
            f_res = find_resonance_hz(freqs_peek, y11_peek)
            max_freq_hz = 2 * f_res
            print(f"data-driven resonance estimate: {f_res/1e9:.3f} GHz -> fitting freqs <= {max_freq_hz/1e9:.3f} GHz")
        fix_rs_l = args.fix_rs_l or args.physics_informed
        fitted, geometry, freqs, y11, fitted_simple, opt_result = full_refit(
            args.result_json, corner=args.corner, flip_sign=args.flip_sign,
            max_freq_hz=max_freq_hz, fix_rs_l=fix_rs_l,
            fix_cox=args.physics_informed, fix_cs_zero=args.physics_informed)
        print(f"geometry: {geometry}")
        print(f"flip_sign={args.flip_sign}")
        print(f"optimizer: success={opt_result.success}, cost={opt_result.cost:.6g}, "
              f"nfev={opt_result.nfev}, status={opt_result.status} ({opt_result.message})")
        print("simple (low-f slope only) fit:")
        print(json.dumps(fitted_simple, indent=2))
        print("full pi-model (joint) fit:")
        print(json.dumps(fitted, indent=2))
    else:
        fitted, geometry, freqs, y11 = refit(args.result_json, corner=args.corner, flip_sign=args.flip_sign)
        print(f"geometry: {geometry}")
        print(f"flip_sign={args.flip_sign}")
        print(json.dumps(fitted, indent=2))

    if args.out:
        with open(args.out, "w") as f:
            json.dump(fitted, f, indent=2)
        print(f"\nwrote {args.out}")

    if args.plot_base and args.full_fit:
        _save_full_fit_plot(freqs, y11, fitted_simple, fitted, f"{args.plot_base}__fullfit.png", max_freq_hz=max_freq_hz)
        print(f"\nplot written: {args.plot_base}__fullfit.png")
    elif args.plot_base:
        sys.path.insert(0, str(_TB_INDUCTOR_DIR))
        sys.path.insert(0, str(_TB_SHARED_DIR))
        tb_yparam_em = _load_module(_TB_INDUCTOR_DIR / "tb_yparam_em.py")
        re_vals, im_vals = y11.real.tolist(), y11.imag.tolist()
        w = 2 * np.pi * freqs
        q = (-y11.imag / y11.real).tolist()
        run = {
            "freqs": freqs.tolist(), "re": re_vals, "im": im_vals, "q": q,
            "geometry": geometry, "field_png": None, "fitted": fitted,
        }
        tb_yparam_em._save_qf_plot([run], f"{args.plot_base}.png")
        tb_yparam_em._save_z_plot([run], f"{args.plot_base}__z.png")
        tb_yparam_em._save_fit_plot([run], f"{args.plot_base}__fit.png")
        print(f"\nplots written: {args.plot_base}.png / __z.png / __fit.png")


if __name__ == "__main__":
    main()
