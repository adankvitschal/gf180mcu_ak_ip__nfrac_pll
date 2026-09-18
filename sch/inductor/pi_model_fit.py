"""Shared Y11(f) pi-model math for the generator-backed inductor topologies
(spiral/loop) and tools/gf180mcu_inductor_refit.py -- a deliberate, documented
exception to this project's usual "duplicate small constants per generator,
no bespoke cross-file coupling" convention: this is FIT LOGIC (nonlinear
optimization, resonance-window selection), not a simple literal, and letting
the generator and the offline refit tool each carry their own copy risked the
two silently drifting apart. Both now import from here.

Everything below operates on plain numpy arrays (freqs in Hz, y11 in complex
Siemens) -- no CSXCAD/openEMS/Docker dependency, same as before.
"""
import numpy as np
from scipy.optimize import least_squares


def y11_two_tap_pi_model(freqs, rs, l, cox, rsub, csub, cs):
    """Closed-form Y11(f) of the pi-model network inductor_spiral.sch/
    inductor_loop.sch implement, as of 2026-09-15 (moved verbatim from
    tools/gf180mcu_inductor_refit.py's own y11_full_pi_model() -- renamed to
    make explicit this is the TWO-substrate-tap topology (taps at 'a' and
    'b' only); see pi_model_fit.py's own module docstring / the project's
    "double-pi at 'ct'" investigation for why a third tap at 'ct' does NOT
    change this formula at all, however it's wired.

    Topology: two symmetric halves a-R(rs)-L(l)-ct and ct-L(l)-R(rs)-b, each
    with a bypass Cs(cs) directly across its own Rs+jwL, plus a
    Cox(cox)-in-series-with-[Rsub(rsub)-parallel-Csub(csub)] branch from EACH
    terminal to a shared, internally-floating 'sub' node (no third terminal
    driven in the one-port a<->b FDTD measurement this fits against).

    Derivation shortcut (confirmed numerically against a full nodal solve):
    because 'ct' connects to ONLY a and b via two EQUAL admittances (nothing
    else), KCL forces Vct = (Va+Vb)/2 regardless of element values -- and
    identically for 'sub'. That collapses the whole network to:
        Y11 = 0.5 * (Yh + Ysub)
    where Yh = 1/(rs+jwl) + jw*cs (one half's own a-ct branch admittance)
    and Ysub = 1 / (1/(jw*cox) + rsub/(1+jw*rsub*csub)) (one terminal's own
    Cox-Rsub-Csub branch admittance)."""
    w = 2 * np.pi * freqs
    yh = 1.0 / (rs + 1j * w * l) + 1j * w * cs
    z_par = rsub / (1 + 1j * w * rsub * csub)
    y_sub = 1.0 / (1.0 / (1j * w * cox) + z_par)
    return 0.5 * (yh + y_sub)


def find_resonance_hz(freqs, y11):
    """Frequency of peak |Im(Y11)| in the raw EM data -- a model-free,
    data-driven stand-in for "the resonance" (no assumption about which fit
    is right, just where the measured curve itself bends hardest)."""
    idx = int(np.argmax(np.abs(y11.imag)))
    return float(freqs[idx])


def fit_rsub_csub_staged(freqs, y11, rs, l, cox, cs=0.0, resonance_window_factor=2.0,
                          rsub0=1.0, csub0=1e-13):
    """Physics-informed staged extraction of ONLY rsub/csub (rs/l/cox/cs held
    fixed at their already-trustworthy values -- rs/l from the low-frequency
    Y11 slope, cox from real geometry, cs from geometry or 0 when there's no
    physical mechanism for it), restricted to the near-resonance window
    (freqs <= resonance_window_factor * find_resonance_hz(...)) rather than
    the whole sweep.

    This is the generalized form of tools/gf180mcu_inductor_refit.py's own
    full_refit()'s 6th ("--physics-informed") attempt, now callable directly
    from fit_electrical_params() instead of only via that tool's manual CLI --
    see that function's still-present docstring (kept, not deleted) for the
    full history of what was tried before landing here: blind joint
    optimization of all 6 params (attempts 1-3) was WORSE than the simple
    low-frequency-only fit in aggregate; letting cox/cs float too (attempt 5)
    "beat" the simple fit locally but produced non-identifiable values (cox
    30x off geometry, csub ~1580x off placeholder) -- fixing every param this
    one-port measurement DOESN'T plausibly constrain independently (rs, l,
    cox, cs) and leaving only rsub/csub genuinely free is what matches
    standard on-chip-inductor pi-model extraction practice (Yue & Wong 2000).

    IMPORTANT, confirmed while wiring this in (2026-09-15): when `cox` is
    small (the real geometry-based value for a modest on-chip loop, ~fF),
    `1/(jw*cox)` dominates the Cox-Rsub-Csub branch's own impedance so
    completely that rsub/csub get near-ZERO gradient and the optimizer can
    correctly converge in a single evaluation with BOTH parameters exactly
    at their seed (`rsub0`/`csub0`) -- not a bug (re-confirmed the identical
    symptom already documented for `full_refit()`'s own 6th attempt: "cox
    held at its own geometry value ... optimizer converged in exactly 1
    function evaluation ... rsub landing EXACTLY at its unchanged initial
    guess"). Because the seed can end up being the EFFECTIVE returned value
    rather than a mere convergence aid, callers should pass a physically
    reasonable `rsub0` (e.g. a geometry-based spreading-resistance estimate)
    rather than an arbitrary placeholder -- `csub0` matters far less since
    it's the parameter most starved of leverage in exactly this regime.

    Returns (rsub, csub, opt_result) -- opt_result is scipy's own
    OptimizeResult, for diagnosing a bad fit (check opt_result.success, and
    opt_result.nfev==1 as a tell that the fit never actually moved)."""
    f_res = find_resonance_hz(freqs, y11)
    max_freq_hz = resonance_window_factor * f_res
    fit_mask = freqs <= max_freq_hz
    freqs_fit, y11_fit = freqs[fit_mask], y11[fit_mask]

    lo = np.array([1e-3, 0.0])
    hi = np.array([1e6, 1e-9])
    x0 = np.clip(np.array([rsub0, csub0]), lo * 1.001, hi * 0.999)

    def residuals(x):
        rsub, csub = x
        y_model = y11_two_tap_pi_model(freqs_fit, rs, l, cox, rsub, csub, cs)
        err = (y_model - y11_fit) / np.abs(y11_fit)
        return np.concatenate([err.real, err.imag])

    # x_scale='jac': REQUIRED here too -- rsub (~ohms) and csub (~1e-13F) are
    # ~14 orders of magnitude apart, and scipy's default per-variable scaling
    # badly under-scales the tiny-magnitude variable's own gradient
    # contribution without it (confirmed in full_refit()'s own history: a
    # first physics-informed attempt without this converged in exactly 1
    # function evaluation with rsub never actually moving from its initial
    # guess).
    opt_result = least_squares(residuals, x0, bounds=(lo, hi), method="trf", x_scale="jac", max_nfev=5000)
    rsub, csub = float(opt_result.x[0]), float(opt_result.x[1])
    return rsub, csub, opt_result


def y11_with_eddy_branch(freqs, rs, l, cox, rsub, csub, cs, rp_eddy, lp_eddy):
    """`y11_two_tap_pi_model()`, but with each half's own series inductor
    `l` replaced by `l` IN PARALLEL WITH an ordinary series branch
    (`rp_eddy` + jw*`lp_eddy`) -- models the winding's own eddy-current/
    skin-proximity loss (the same physical phenomenon Yue & Wong's own
    on-chip inductor model keeps as a term separate from substrate ohmic/
    capacitive loss) WITHOUT needing an explicit mutual-inductance (SPICE
    `K`) element at all.

    2026-09-15: this REPLACES an earlier version of this function that
    modeled the same phenomenon via an explicit magnetically-coupled
    shorted secondary loop (reflected impedance w^2*M^2/(R2+jwL2)). That
    version is mathematically the SAME physics -- `l ∥ (rp_eddy+jw*lp_eddy)`
    is exactly the classical Steinmetz/T-equivalent circuit representation
    of a transformer with a shorted secondary, using only ordinary
    (non-coupled) R/L elements -- and was confirmed to fit the same cached
    EM data to indistinguishable accuracy (100x50um/2um cached run: 1.10%
    RMS relative error here vs. 1.05% for the mutual-inductance version,
    both with exactly 2 free parameters). Switched to THIS form because
    it's directly realizable in inductor_loop.sch with ordinary drawn
    components (an inductor + a resistor in parallel with each of L1/L2) --
    no `code.sym`/SPICE `K` statement needed at all, simpler to draw and
    simpler to reason about.

    A simpler 1-parameter alternative (just `rp_eddy` alone, i.e. a plain
    resistor in parallel with `l`, no `lp_eddy`) was tried FIRST and
    empirically REJECTED: it only improved the full-band RMS error from
    42% to 34% (vs. this 2-parameter version's 1.1%) -- a plain R∥L
    branch's high-frequency limit is a constant RESISTANCE (its own
    reactance simply disappears), not a REDUCED-BUT-STILL-INDUCTIVE
    reactance, which is what the real EM data actually shows well above
    resonance. The extra `lp_eddy` is what gives the branch the right
    high-frequency asymptote (`l ∥ (rp_eddy+jw*lp_eddy)` -> a reduced
    effective inductance `l*lp_eddy/(l+lp_eddy)` as w->infinity, not a
    plain resistance) -- confirms this is a genuine, not superficial,
    2-degree-of-freedom requirement, consistent with the mutual-inductance
    derivation's own w^2-in-the-numerator requirement (a plain R∥L branch
    is only 1st-order, one degree short)."""
    w = 2 * np.pi * freqs
    z_branch = rp_eddy + 1j * w * lp_eddy
    z_l_parallel = (1j * w * l) * z_branch / (1j * w * l + z_branch)
    yh = 1.0 / (rs + z_l_parallel) + 1j * w * cs
    z_par = rsub / (1 + 1j * w * rsub * csub)
    y_sub = 1.0 / (1.0 / (1j * w * cox) + z_par)
    return 0.5 * (yh + y_sub)


def fit_eddy_branch(freqs, y11, rs, l, cox, rsub, csub, cs,
                     rp_eddy0=None, lp_eddy0=None, min_freq_hz=None):
    """Fits ONLY rp_eddy/lp_eddy (2 params) via nonlinear least squares,
    holding rs/l/cox/rsub/csub/cs FIXED at whatever fit_electrical_params()/
    fit_rsub_csub_staged() already produced -- isolates whether adding
    JUST this one missing phenomenon explains the residual, rather than
    re-fitting everything jointly (which would risk the same non-
    identifiability trap already documented for fit_rsub_csub_staged()).
    See y11_with_eddy_branch()'s own docstring for the physical derivation
    and why a plain 1-parameter R∥L branch (no lp_eddy) was rejected.

    `min_freq_hz` (default None = fit the WHOLE sweep): this branch is
    specifically meant to explain ABOVE-resonance behavior (it's ~0
    correction at low frequency by construction, since `l` alone dominates
    the parallel combination there) -- restricting the fit window to
    frequencies at/above roughly the primary resonance avoids the low-
    frequency points (where this term contributes ~nothing) diluting the
    residual's sensitivity to rp_eddy/lp_eddy. Left as a caller option for
    experimentation, not because it's known to matter (the default,
    whole-sweep fit already reaches ~1% RMS error on the one cached run
    tested so far).

    Seeds: `rp_eddy0` defaults to `l * 2*pi*f_res` (a reactance-scale
    guess at the data-driven resonance frequency); `lp_eddy0` defaults to
    0.5*l (order-of-magnitude guess, not a physical calculation).

    Returns (rp_eddy, lp_eddy, opt_result)."""
    if min_freq_hz is not None:
        fit_mask = freqs >= min_freq_hz
    else:
        fit_mask = np.ones(len(freqs), dtype=bool)
    freqs_fit, y11_fit = freqs[fit_mask], y11[fit_mask]

    f_res = find_resonance_hz(freqs, y11)
    # abs(l): l is a physical inductance and should never legitimately be
    # negative, but a real 2026-09-16 crash (see openems_inductor_status.md)
    # showed it CAN arrive negative when an upstream Y11 sign-convention bug
    # (now fixed in openems_generator_runner.py) feeds a bad em_result in --
    # `hi = 2*l` then went negative while `lo` stayed positive, and scipy's
    # least_squares raised ValueError("Each lower bound must be strictly
    # less than each upper bound") instead of a clear diagnostic. Guarding
    # here (not just relying on the upstream fix) means a caller passing a
    # bad `l` fails at most with a poor fit, never a hard crash.
    l_abs = abs(l)
    if rp_eddy0 is None:
        rp_eddy0 = l_abs * 2 * np.pi * f_res
    if lp_eddy0 is None:
        lp_eddy0 = 0.5 * l_abs

    lo = np.array([1e-6, 0.0])
    hi = np.array([1e6, max(2 * l_abs, 2 * lo[1] * 1.001, 1e-15)])
    x0 = np.clip(np.array([rp_eddy0, lp_eddy0]), lo * 1.001, hi * 0.999)

    def residuals(x):
        rp_eddy, lp_eddy = x
        y_model = y11_with_eddy_branch(freqs_fit, rs, l, cox, rsub, csub, cs, rp_eddy, lp_eddy)
        err = (y_model - y11_fit) / np.abs(y11_fit)
        return np.concatenate([err.real, err.imag])

    opt_result = least_squares(residuals, x0, bounds=(lo, hi), method="trf", x_scale="jac", max_nfev=5000)
    rp_eddy, lp_eddy = float(opt_result.x[0]), float(opt_result.x[1])
    return rp_eddy, lp_eddy, opt_result


def assert_ct_tap_unobservable(n_trials=5, seed=0):
    """Regression check for the "double-pi at ct is invisible to Y11" finding
    (2026-09-15 planning session): numerically confirms that adding an
    arbitrary third admittance branch Yc between 'ct' and 'sub' -- exactly
    the shape of the new cox_ct/(rsub_ct parallel csub_ct) branch added to
    inductor_loop.sch -- leaves Y11 (measured one-port, a driven, b grounded)
    UNCHANGED, for any Yc. This is a hard consequence of the a<->b mirror
    symmetry (both 'ct' and 'sub' connect to a/b only via matched pairs of
    equal admittances, so KCL forces Vct=Vsub=(Va+Vb)/2 regardless of what
    connects them to each other) -- not something that should ever need
    re-deriving by hand again; if this assertion ever fails, the topology
    changed in a way that invalidates that argument and any code relying on
    it (e.g. fit_electrical_params() NOT trying to EM-fit cox_ct/rsub_ct/
    csub_ct) needs to be revisited.

    Solves the explicit 2-node (ct, sub) nodal system for a unit drive at 'a'
    (Va=1, Vb=0): with Yh = one half's a-ct branch admittance, Ys = one
    terminal's Cox-Rsub-Csub branch admittance, Yc = the new ct-sub branch:
        (2*Yh + Yc)*Vct - Yc*Vsub = Yh
        -Yc*Vct + (2*Ys + Yc)*Vsub = Ys
    and computes Y11 = Yh*(1-Vct) + Ys*(1-Vsub), comparing against the
    existing Yc=0 closed form (0.5*(Yh+Ys)) for random complex Yh/Ys/Yc.
    Raises AssertionError if they ever disagree beyond float tolerance."""
    rng = np.random.default_rng(seed)
    for _ in range(n_trials):
        yh = rng.uniform(0.1, 10) + 1j * rng.uniform(-10, 10)
        ys = rng.uniform(0.1, 10) + 1j * rng.uniform(-10, 10)
        yc = rng.uniform(0.1, 1e4) + 1j * rng.uniform(-1e4, 1e4)

        a_mat = np.array([
            [2 * yh + yc, -yc],
            [-yc, 2 * ys + yc],
        ])
        b_vec = np.array([yh, ys])
        vct, vsub = np.linalg.solve(a_mat, b_vec)
        y11_with_yc = yh * (1 - vct) + ys * (1 - vsub)

        y11_without_yc = 0.5 * (yh + ys)

        if not np.isclose(y11_with_yc, y11_without_yc, rtol=1e-9, atol=1e-12):
            raise AssertionError(
                f"ct-tap unobservability invariant violated: yh={yh}, ys={ys}, yc={yc}, "
                f"Y11(with Yc)={y11_with_yc} != Y11(Yc=0)={y11_without_yc}"
            )


def fit_arm_self_impedance(freqs, y11, n_fit=None):
    """Low-frequency Rs+jwL slope fit of a single continuous 2-terminal
    winding's own Y11 -- same low-frequency-window convention as
    fit_electrical_params()'s l_half/rs_half (n_fit=max(3, len//20) lowest
    points), but WITHOUT the /2: this is meant for inductor_spiral_diff_
    generator.py's "arm alone" measurement (one whole arm, ct-pad to its own
    far-terminus pad, no other conductor in the structure -- see that
    module's own docstring), which really is one continuous 2-terminal
    winding end to end, same methodology as inductor_loop_generator.py's own
    single-loop fit (loop_/spiral_ 's 'l'/'rs' ARE halved because their
    single measurement spans two series L/R pairs in the .sch template; an
    arm-alone measurement here spans exactly ONE of those, so no halving).

    Returns (rs, l)."""
    if n_fit is None:
        n_fit = max(3, len(freqs) // 20)
    w = 2 * np.pi * freqs[:n_fit]
    z = 1.0 / y11[:n_fit]
    l = float(np.mean(np.imag(z) / w))
    rs = float(np.mean(np.real(z)))
    return rs, l


def fit_mutual_inductance(freqs_a, y11_a, freqs_b, y11_b, freqs_sc, y11_sc, n_fit=None):
    """Combines THREE single-port EM runs of a center-tapped differential
    inductor's two arms into (ra, la, rb, lb, m, k) -- the open/short-
    circuit transformer test method (see inductor_spiral_diff_generator.py's
    own module docstring for the full physical justification: a direct
    single-port measurement bridging the two arms' far-terminus pads
    directly is invalid for this Y-shaped 3-terminal network, since it adds
    an artificial short-cut path instead of measuring the real ct-mediated
    winding, AND can never reveal mutual coupling since an open secondary
    carries no current by definition):

    - 'arm_a' run: arm A alone (arm B genuinely absent from the geometry),
      port bridging arm A's own two ends (ct-pad, P1-pad) -> fit_arm_self_
      impedance() gives (ra, la), arm A's own end-to-end self-impedance.
    - 'arm_b' run: mirror -> (rb, lb).
    - 'shorted' run: FULL structure (both arms present), arm B's far end
      (P2) shorted to ct via an added jumper trace, port bridging (P1-pad,
      ct-pad) -- same port placement as the 'arm_a' run. Mesh analysis of
      this network (arm B + the shorting jumper form a closed loop with no
      independent drive, purely mutually coupled to arm A) gives:
          Za_sc(w) = (ra + jw*la) + w^2*m^2 / (rb + jw*lb)
      the classical short-circuit-secondary transformer result (reduces to
      the textbook jw*la*(1-k^2) approximation when ra,rb->0). Solved here
      for m^2 directly, per swept frequency point in the low-frequency
      window:
          m^2(w) = (Za_sc(w) - ra - jw*la) * (rb + jw*lb) / w^2
      which should be roughly frequency-independent if this model actually
      holds -- the spread across the fit window (see 'm2_values' in the
      returned dict) is itself a check on model validity, not hidden away.

    All three runs must share the same frequency sweep (freqs_a/freqs_b/
    freqs_sc are asserted equal, not just same length -- a mismatched sweep
    would silently misalign per-point m^2(w) below).

    Returns a dict: ra, la, rb, lb (each run's own self-impedance fit),
    m (sqrt of the low-frequency-window mean of Re(m^2) -- NOT abs()'d: a
    negative mean Re(m^2) means the 3-run model didn't hold for this data
    and is surfaced as a ValueError, not silently papered over), k (=
    m/sqrt(la*lb), NOT clamped to [0,1] -- a caller should treat k outside
    that range as a sign something upstream is wrong, same "surface it,
    don't hide it" spirit as this module's other fit functions), and
    'm2_values' (the raw per-frequency-point complex m^2(w) array actually
    averaged, for inspecting how much it varies)."""
    freqs_a = np.asarray(freqs_a)
    freqs_b = np.asarray(freqs_b)
    freqs_sc = np.asarray(freqs_sc)
    if not (np.allclose(freqs_a, freqs_b) and np.allclose(freqs_a, freqs_sc)):
        raise ValueError("fit_mutual_inductance(): the 3 runs must share the same frequency sweep")

    if n_fit is None:
        n_fit = max(3, len(freqs_a) // 20)

    ra, la = fit_arm_self_impedance(freqs_a, y11_a, n_fit=n_fit)
    rb, lb = fit_arm_self_impedance(freqs_b, y11_b, n_fit=n_fit)

    w = 2 * np.pi * freqs_sc[:n_fit]
    z_sc = 1.0 / np.asarray(y11_sc)[:n_fit]
    m2_values = (z_sc - ra - 1j * w * la) * (rb + 1j * w * lb) / w ** 2

    m2_mean_re = float(np.mean(m2_values.real))
    if m2_mean_re < 0:
        raise ValueError(
            f"fit_mutual_inductance(): mean Re(m^2)={m2_mean_re:.3g} is negative -- the "
            f"open/short-circuit-test model didn't hold for this data (ra={ra:.4g}, la={la:.4g}, "
            f"rb={rb:.4g}, lb={lb:.4g}); check the 'shorted' run's own jumper/port geometry before "
            f"trusting any of this rather than taking abs() or sqrt() of a negative number")
    m = float(np.sqrt(m2_mean_re))
    k = m / np.sqrt(la * lb)

    return {"ra": ra, "la": la, "rb": rb, "lb": lb, "m": m, "k": k, "m2_values": m2_values}


def assert_mutual_inductance_recovers_synthetic(n_trials=5, seed=0):
    """Regression check for fit_mutual_inductance()'s own derivation: builds
    a synthetic (ra, la, rb, lb, m) coupled-arm pair, computes the EXACT
    idealized Y11(f) each of the 3 real EM runs would produce if the FDTD
    structure behaved exactly like the lumped model (Y11_arm_a=1/(ra+jwla),
    Y11_arm_b=1/(rb+jwlb), Y11_shorted=1/((ra+jwla)+w^2*m^2/(rb+jwlb))), then
    confirms fit_mutual_inductance() recovers (ra, la, rb, lb, m) back out to
    near machine precision -- proves the fitting math itself is correct
    BEFORE it's ever pointed at a real (expensive, hours-long) FDTD run,
    same spirit as assert_ct_tap_unobservable() above."""
    rng = np.random.default_rng(seed)
    freqs = np.linspace(1e6, 20e9, 201)
    w = 2 * np.pi * freqs
    for _ in range(n_trials):
        ra = rng.uniform(0.5, 5.0)
        la = rng.uniform(1e-9, 5e-9)
        rb = rng.uniform(0.5, 5.0)
        lb = rng.uniform(1e-9, 5e-9)
        k_true = rng.uniform(0.05, 0.6)
        m = k_true * np.sqrt(la * lb)

        y11_a = 1.0 / (ra + 1j * w * la)
        y11_b = 1.0 / (rb + 1j * w * lb)
        z_sc = (ra + 1j * w * la) + (w ** 2) * (m ** 2) / (rb + 1j * w * lb)
        y11_sc = 1.0 / z_sc

        fitted = fit_mutual_inductance(freqs, y11_a, freqs, y11_b, freqs, y11_sc)

        for name, expected, got in (
            ("ra", ra, fitted["ra"]), ("la", la, fitted["la"]),
            ("rb", rb, fitted["rb"]), ("lb", lb, fitted["lb"]),
            ("m", m, fitted["m"]), ("k", k_true, fitted["k"]),
        ):
            if not np.isclose(expected, got, rtol=1e-6, atol=1e-15):
                raise AssertionError(
                    f"fit_mutual_inductance() failed to recover synthetic {name}: "
                    f"expected {expected!r}, got {got!r} (ra={ra},la={la},rb={rb},lb={lb},m={m})")


if __name__ == "__main__":
    assert_ct_tap_unobservable()
    print("assert_ct_tap_unobservable(): OK -- a third ct<->sub branch is confirmed invisible to Y11")
    assert_mutual_inductance_recovers_synthetic()
    print("assert_mutual_inductance_recovers_synthetic(): OK -- the 3-run open/short-circuit fit "
          "recovers synthetic ra/la/rb/lb/m/k to near machine precision")
