"""Parser for tb_divider_funct.sch: functional divide-by-2/3 verification.
Drives clk with a sine (see config.json's tests.divider.funct.conditions --
clk_dc/clk_amp/clk_freq) and measures the block's own steady-state output
period against the input's own steady-state period, for each swept 'sw'
level. Reduces the raw waveform to five metrics: the measured ratio
(informational -- see the divider.etspc_d2d3 topology's own config.json
description for why sw=low/high isn't assumed to mean any particular ratio
up front), how far that ratio sits from its own nearest integer (the actual
functional-correctness check -- a miscounting divider shows up as a large,
non-integer ratio instead of landing near 0), the output's own duty cycle
and its deviation from the ideal 50% (cycle asymmetry matters beyond
aesthetics -- in the real PLL this divider feeds a delta-sigma-modulated
dual-modulus chain, and any duty-cycle/propagation-delay difference between
the 'sw' states shows up as a periodic disturbance synchronized with the
modulator's own pattern, i.e. a fractional-spur mechanism, not just a
funny-looking waveform), and the average VDD power drawn over the last
steady-state output period (a transient average, not a bare .op point --
see this topology's own config.json description for why a DC operating
point has no meaningful "consumption" figure for a clocked dynamic
circuit)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from parser_common import read_data, legend_if_any, typical_min_max

#: Fraction of the run discarded before measuring -- lets the E-TSPC
#: counter's own internal state settle out of whatever the .op solver left
#: it in before treating any crossing as "steady state" (same reasoning as
#: tb_startup's own steady-cycle windowing, just time-fraction-based instead
#: of amplitude-envelope-based since this is a digital divider, not a
#: growing oscillator).
_SETTLE_FRACTION = 0.5

#: How many trailing steady-state OUTPUT periods to average VDD power over
#: -- one period alone can land oddly depending on exactly where its edges
#: fall relative to the sample grid, a handful smooths that out without
#: dragging in the (irrelevant) startup transient.
_POWER_AVG_PERIODS = 5

#: How many trailing steady-state input clk periods to show in the waveform
#: plot -- the plot exists to let a human visually confirm the division
#: factor (count clk edges per out edge) and spot a broken/asymmetric
#: output, not to render the whole multi-hundred-cycle run.
_PLOT_CYCLES = 8


def _threshold_crossings(times, values, threshold, rising=True):
    """Linearly-interpolated times where `values` crosses `threshold`,
    rising (<=threshold to >threshold) or falling (>=threshold to
    <threshold)."""
    crossings = []
    for i in range(1, len(values)):
        lo, hi = values[i - 1], values[i]
        crossed = (lo <= threshold < hi) if rising else (lo >= threshold > hi)
        if crossed:
            frac = (threshold - lo) / (hi - lo)
            crossings.append(times[i - 1] + frac * (times[i] - times[i - 1]))
    return crossings


def _mean_period(crossings):
    if len(crossings) < 2:
        return None
    return (crossings[-1] - crossings[0]) / (len(crossings) - 1)


def extract(data_path):
    """Raw reduction of one simulation run's .data file (time, clk, out,
    v(vdd), vdd#branch columns, see tb_divider_funct.sch's own wrdata line).
    No spec judgement -- that's evaluate()'s job, via outputs[].maximum on
    the ratio-error metric. clk/out midpoints are each computed from their
    OWN steady-state min/max rather than assumed from 'vdd'/'clk_dc' --
    keeps this parser correct regardless of clk_amp/clk_dc/vdd, and
    independent of extract() needing to know any of those (it only ever
    sees the raw waveform)."""
    rows = read_data(data_path)
    times = [r[0] for r in rows]
    clk = [r[1] for r in rows]
    out = [r[2] for r in rows]
    vdd_v = [r[3] for r in rows]
    idd = [r[4] for r in rows]

    settle_t = times[0] + (times[-1] - times[0]) * _SETTLE_FRACTION
    steady_idx = next((i for i, t in enumerate(times) if t >= settle_t), len(times) - 1)
    steady_times = times[steady_idx:]
    steady_clk = clk[steady_idx:]
    steady_out = out[steady_idx:]

    clk_mid = (max(steady_clk) + min(steady_clk)) / 2
    out_mid = (max(steady_out) + min(steady_out)) / 2

    clk_rising = _threshold_crossings(steady_times, steady_clk, clk_mid, rising=True)
    out_rising = _threshold_crossings(steady_times, steady_out, out_mid, rising=True)
    out_falling = _threshold_crossings(steady_times, steady_out, out_mid, rising=False)

    period_in = _mean_period(clk_rising)
    period_out = _mean_period(out_rising)

    ratio = (period_out / period_in) if (period_in and period_out) else 0.0
    # ratio==0.0 means no usable period could be measured (clk or out never
    # settled into a clean steady toggle) -- report that as maximally wrong
    # rather than as a suspiciously perfect 0.0 error.
    ratio_error = abs(ratio - round(ratio)) if ratio else 1.0

    duty_pct = 0.0
    if len(out_rising) >= 2 and out_falling:
        r0 = out_rising[0]
        f0 = next((f for f in out_falling if f > r0), None)
        r1 = next((r for r in out_rising if r > r0), None)
        if f0 and r1 and r1 > r0:
            duty_pct = (f0 - r0) / (r1 - r0) * 100
    duty_error_pct = abs(duty_pct - 50) if duty_pct else 0.0

    # Average power over the last _POWER_AVG_PERIODS complete steady-state
    # OUTPUT periods -- ngspice's own sign convention has a source's branch
    # current negative while it's delivering power (current flows OUT of
    # its + terminal), hence the abs(); v(vdd)*i(vdd) rather than a flat
    # vdd*mean(i) so a non-ideal/noisy supply node is still handled
    # correctly, though for this nearly-ideal DC source the two agree.
    avg_power_uw = 0.0
    if len(out_rising) >= _POWER_AVG_PERIODS + 1:
        win_start, win_end = out_rising[-(_POWER_AVG_PERIODS + 1)], out_rising[-1]
        samples = [
            v * i for t, v, i in zip(times, vdd_v, idd) if win_start <= t <= win_end
        ]
        if samples:
            avg_power_uw = abs(sum(samples) / len(samples)) * 1e6

    return {
        "ratio": ratio, "ratio_error": ratio_error,
        "duty_pct": duty_pct, "duty_error_pct": duty_error_pct,
        "avg_power_uw": avg_power_uw,
        "times": times, "clk": clk, "out": out,
        "period_in": period_in,
    }


#: sw and clk_freq are both swept per config.json's own tests.divider.funct
#: conditions, so both have to join the match_keys typical_min_max() uses to
#: pick out the single "typical" run (same reasoning as tb_startup.py's own
#: _MATCH_KEYS -- see its docstring).
_MATCH_KEYS = ("corner", "temperature", "sw", "clk_freq")


def evaluate(runs, outputs, typical, plot_base=None):
    ratio_spec, ratio_error_spec, duty_spec, duty_error_spec, power_spec = outputs

    def _metric(spec, key):
        result = typical_min_max(runs, typical, lambda r: r[key], match_keys=_MATCH_KEYS)
        return {
            "name": spec["description"], "unit": spec["unit"],
            "typical": result["typical"], "min": result["min"], "max": result["max"],
            "minimum": spec.get("minimum"), "maximum": spec.get("maximum"),
        }

    metrics = [
        _metric(ratio_spec, "ratio"),
        _metric(ratio_error_spec, "ratio_error"),
        _metric(duty_spec, "duty_pct"),
        _metric(duty_error_spec, "duty_error_pct"),
        _metric(power_spec, "avg_power_uw"),
    ]

    if plot_base and len(runs) > 1:
        _save_plots(runs, plot_base)

    return metrics


def _save_plots(runs, plot_base):
    """One separate PNG per (sw, clk_freq) run -- a single figure with every
    run stacked as subplots got unreadable once there were more than a
    couple of conditions. Each plot only shows the last _PLOT_CYCLES input
    clk periods of steady state (not the whole multi-hundred-cycle run):
    the point of this plot is letting a human visually count clk edges per
    out edge and confirm the division factor / spot an asymmetric or broken
    output, which needs only a handful of cycles, not the full record."""
    for r in runs:
        times_ns = [t * 1e9 for t in r["times"]]
        period_in = r.get("period_in")
        t_end = r["times"][-1]
        t_start = t_end - _PLOT_CYCLES * period_in if period_in else r["times"][0]
        window = [(t, c, o) for t, c, o in zip(times_ns, r["clk"], r["out"]) if t * 1e-9 >= t_start]

        fig, ax = plt.subplots(figsize=(6, 2.4))
        ax.plot([w[0] for w in window], [w[1] for w in window], label="clk", linewidth=0.8, alpha=0.7)
        ax.plot([w[0] for w in window], [w[2] for w in window], label="out", linewidth=1.1)
        ax.set_xlabel("time (ns)")
        ax.set_ylabel("V")
        ax.set_title(
            f"sw={r['conditions'].get('sw')}V, clk_freq={r['conditions'].get('clk_freq')}Hz "
            f"(ratio={r['ratio']:.3f}, duty={r['duty_pct']:.1f}%)", fontsize=8,
        )
        legend_if_any(ax, fontsize=7)
        fig.tight_layout()
        sw = r["conditions"].get("sw", "?")
        freq = r["conditions"].get("clk_freq", "?")
        fig.savefig(f"{plot_base}_sw{sw}_f{freq}.png", dpi=150)
        plt.close(fig)
