"""Parser for tb_startup.sch: VCO startup transient (Ikick-seeded .tran of
i_diff = v(I_p)-v(I_n), q_diff = v(Q_p)-v(Q_n)). Reduces the raw waveform to
five metrics: startup time (envelope to 90% of its own steady-state peak),
steady-state frequency (from I's own rising zero-crossings), I/Q peak-peak
amplitude, and I/Q quadrature phase error (deviation from the ideal 90
degrees between I's and Q's rising zero-crossings). A corner that never
actually breaks into oscillation reports near-zero amplitude rather than
some other error -- outputs[].minimum on the amplitude metrics is what's
meant to catch that (see tb_startup's own conditions in config.json), same
convention as every other spec-bounded metric in this project."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from parser_common import read_data, legend_if_any, typical_min_max

#: Below this peak-peak differential swing, treat the "oscillation" as
#: solver/leakage noise rather than a real startup -- keeps
#: startup_time_ns/freq_mhz/quad_error_deg from reporting nonsense envelope
#: crossings picked out of noise on a corner that never actually started.
_NOISE_FLOOR_V = 1e-3


def _rising_zero_crossings(times, values):
    """Linearly-interpolated times where `values` crosses from <=0 to >0."""
    crossings = []
    for i in range(1, len(values)):
        if values[i - 1] <= 0 < values[i]:
            frac = -values[i - 1] / (values[i] - values[i - 1])
            crossings.append(times[i - 1] + frac * (times[i] - times[i - 1]))
    return crossings


def _cycle_envelope(times, values, crossings):
    """[(cycle_end_time, peak_abs_value), ...], one point per complete cycle
    bounded by two consecutive rising zero-crossings -- the startup envelope
    tracked cycle-by-cycle instead of sample-by-sample, so a single noisy
    sample near a crossing can't be mistaken for the oscillation's own
    growing amplitude."""
    envelope = []
    j = 0
    for i in range(1, len(crossings)):
        lo, hi = crossings[i - 1], crossings[i]
        while j < len(times) and times[j] < lo:
            j += 1
        peak = 0.0
        k = j
        while k < len(times) and times[k] < hi:
            peak = max(peak, abs(values[k]))
            k += 1
        envelope.append((hi, peak))
    return envelope


def extract(data_path):
    """Raw reduction of one simulation run's .data file (time, i_diff,
    q_diff columns, see tb_startup.sch's own wrdata line). No spec
    judgement -- that's evaluate()'s job, via outputs[].minimum."""
    rows = read_data(data_path)
    times = [r[0] for r in rows]
    i_diff = [r[1] for r in rows]
    q_diff = [r[2] for r in rows]

    i_crossings = _rising_zero_crossings(times, i_diff)
    envelope = _cycle_envelope(times, i_diff, i_crossings)
    steady = [pt for pt in envelope if pt[1] >= _NOISE_FLOOR_V]

    if len(steady) < 4:
        return {
            "startup_time_ns": 0.0, "freq_mhz": 0.0,
            "i_amplitude_mv": 0.0, "q_amplitude_mv": 0.0, "quad_error_deg": 0.0,
            "times": times, "i_diff": i_diff, "q_diff": q_diff,
        }

    steady_n = max(3, len(steady) // 5)  # last ~20% of completed cycles
    steady_cycles = steady[-steady_n:]
    final_amplitude = sum(peak for _, peak in steady_cycles) / len(steady_cycles)
    window_start = steady_cycles[0][0]

    startup_time_ns = next(
        (t * 1e9 for t, peak in envelope if peak >= 0.9 * final_amplitude), 0.0,
    )

    steady_i_crossings = [t for t in i_crossings if t >= window_start]
    period_s = (
        (steady_i_crossings[-1] - steady_i_crossings[0]) / (len(steady_i_crossings) - 1)
        if len(steady_i_crossings) >= 2 else None
    )
    freq_mhz = (1 / period_s / 1e6) if period_s else 0.0

    q_crossings = _rising_zero_crossings(times, q_diff)
    steady_q_crossings = [t for t in q_crossings if t >= window_start]
    quad_error_deg = 0.0
    if period_s and steady_i_crossings and steady_q_crossings:
        t_i = steady_i_crossings[-1]
        after = [t for t in steady_q_crossings if t >= t_i]
        t_q = after[0] if after else steady_q_crossings[-1]
        quad_error_deg = ((t_q - t_i) / period_s * 360) % 360 - 90

    i_window = [v for t, v in zip(times, i_diff) if t >= window_start]
    q_window = [v for t, v in zip(times, q_diff) if t >= window_start]

    return {
        "startup_time_ns": startup_time_ns,
        "freq_mhz": freq_mhz,
        "i_amplitude_mv": (max(i_window) - min(i_window)) * 1e3,
        "q_amplitude_mv": (max(q_window) - min(q_window)) * 1e3,
        "quad_error_deg": quad_error_deg,
        "times": times, "i_diff": i_diff, "q_diff": q_diff,
    }


#: corner/temperature stay fixed for this test (see config.json's own
#: tests.vco.startup.conditions) -- vtune is the one swept outer axis, so
#: it has to join the match_keys typical_min_max() uses to pick out the
#: single "typical" run, or every vtune condition would tie on corner+
#: temperature alone and typical_min_max() would raise (see its own
#: docstring: "Exactly one run expected to match... raises rather than
#: silently picking one").
_MATCH_KEYS = ("corner", "temperature", "vtune")


def evaluate(runs, outputs, typical, plot_base=None):
    startup_spec, freq_spec, i_amp_spec, q_amp_spec, quad_spec = outputs

    def _metric(spec, key):
        result = typical_min_max(runs, typical, lambda r: r[key], match_keys=_MATCH_KEYS)
        return {
            "name": spec["description"], "unit": spec["unit"],
            "typical": result["typical"], "min": result["min"], "max": result["max"],
            "minimum": spec.get("minimum"), "maximum": spec.get("maximum"),
        }

    metrics = [
        _metric(startup_spec, "startup_time_ns"),
        _metric(freq_spec, "freq_mhz"),
        _metric(i_amp_spec, "i_amplitude_mv"),
        _metric(q_amp_spec, "q_amplitude_mv"),
        _metric(quad_spec, "quad_error_deg"),
    ]

    if plot_base and len(runs) > 1:
        _save_plot(runs, f"{plot_base}.png")

    return metrics


def _save_plot(runs, path):
    """One I/Q panel per run, stacked -- with corner/temperature fixed for
    this test, the only thing varying run-to-run is vtune (see config.json's
    own tests.vco.startup.conditions), and the whole point of sweeping it is
    SEEING whether/how the startup envelope shape changes across the tuning
    range (e.g. only some vtune values might actually break into growing
    oscillation once the varactor bias is fixed) -- a single overlaid plot
    would bury that under 2 lines per run."""
    runs = sorted(runs, key=lambda r: float(r["conditions"].get("vtune", 0)))
    fig, axes = plt.subplots(len(runs), 1, figsize=(6, 2.4 * len(runs)), sharex=True)
    if len(runs) == 1:
        axes = [axes]
    for ax, r in zip(axes, runs):
        times_ns = [t * 1e9 for t in r["times"]]
        ax.plot(times_ns, [v * 1e3 for v in r["i_diff"]], label="I (I_p-I_n)", linewidth=0.8)
        ax.plot(times_ns, [v * 1e3 for v in r["q_diff"]], label="Q (Q_p-Q_n)", linewidth=0.8, alpha=0.8)
        ax.set_ylabel("diff. out (mV)")
        ax.set_title(f"vtune={r['conditions'].get('vtune')}V", fontsize=9)
        legend_if_any(ax, fontsize=7)
    axes[-1].set_xlabel("time (ns)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
