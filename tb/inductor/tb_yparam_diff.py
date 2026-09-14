"""Parser for tb_yparam_diff.sch: differential Y-param AC sweep of the
inductor block -- Q(f), self-resonant frequency (SRF), and Q at the VCO's
own ~1GHz operating point. Ydiff = I(Vab)/V(a,b) with the center tap tied
to GND (the tank's own virtual ground under balanced differential drive,
same AC condition as the QVCO's cross-coupled pair actually imposes) and
sub grounded -- unlike tb_yparam.sch's one-port sweep (single-ended drive,
b grounded, ct floating), which characterizes the bare structure but not
the differential mode the tank actually operates in. Q = -Im(Ydiff)/Re(Ydiff),
same sign convention as tb_yparam.py."""
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from parser_common import read_data, typical_min_max, legend_if_any

REF_FREQ_HZ = 1e9


def extract(data_path):
    rows = read_data(data_path)
    freqs = [r[0] for r in rows]
    # Same column layout tb_yparam.py found for this project's ngspice/
    # wrdata combination: [freq, freq-again, 0.0, im, re], not [freq, re,
    # im] as the wrdata argument order alone would suggest.
    im = [r[3] for r in rows]
    re = [r[4] for r in rows]

    q = [(-i / r) if r else float("nan") for r, i in zip(re, im)]

    srf_hz = None
    for i in range(1, len(freqs)):
        if im[i - 1] < 0 <= im[i]:
            frac = -im[i - 1] / (im[i] - im[i - 1])
            srf_hz = freqs[i - 1] + frac * (freqs[i] - freqs[i - 1])
            break

    peak_q = max(q)
    peak_q_freq_hz = freqs[q.index(peak_q)]

    # Log-frequency interpolation for Q at the VCO's own operating point --
    # peak_q alone lands at this sweep's 1MHz floor for every candidate and
    # says nothing about behavior near 1GHz, which is what actually matters
    # for tank selection.
    q_ref = None
    for i in range(1, len(freqs)):
        if freqs[i - 1] <= REF_FREQ_HZ <= freqs[i]:
            lo, hi = math.log(freqs[i - 1]), math.log(freqs[i])
            frac = (math.log(REF_FREQ_HZ) - lo) / (hi - lo) if hi != lo else 0.0
            q_ref = q[i - 1] + frac * (q[i] - q[i - 1])
            break

    return {
        "freqs": freqs, "q": q,
        "srf_ghz": (srf_hz / 1e9) if srf_hz else None,
        "peak_q": peak_q, "peak_q_freq_ghz": peak_q_freq_hz / 1e9,
        "q_ref": q_ref,
    }


def evaluate(runs, outputs, typical, plot_base=None):
    srf_spec, q_spec, q_ref_spec = outputs
    # Im(Ydiff) doesn't necessarily cross zero within the swept range --
    # typical_min_max's min()/max() can't compare None, so report +inf
    # ("self-resonance is above this sweep's ceiling") instead of crashing.
    # Not plain None: print_metrics() treats typical=None as a Monte Carlo
    # mean+-std result, a different metric shape, and would KeyError
    # looking for "mean"/"std" here.
    if all(r["srf_ghz"] is None for r in runs):
        srf_result = {"typical": float("inf"), "min": float("inf"), "max": float("inf")}
    else:
        srf_result = typical_min_max(runs, typical, lambda r: r["srf_ghz"])
    q_result = typical_min_max(runs, typical, lambda r: r["peak_q"])
    q_ref_result = typical_min_max(runs, typical, lambda r: r["q_ref"])

    if plot_base and len(runs) > 1:
        _save_plot(runs, f"{plot_base}.png")

    return [
        {
            "name": srf_spec["description"], "unit": srf_spec["unit"],
            "typical": srf_result["typical"], "min": srf_result["min"], "max": srf_result["max"],
            "minimum": srf_spec.get("minimum"), "maximum": srf_spec.get("maximum"),
        },
        {
            "name": q_spec["description"], "unit": q_spec["unit"],
            "typical": q_result["typical"], "min": q_result["min"], "max": q_result["max"],
            "minimum": q_spec.get("minimum"), "maximum": q_spec.get("maximum"),
        },
        {
            "name": q_ref_spec["description"], "unit": q_ref_spec["unit"],
            "typical": q_ref_result["typical"], "min": q_ref_result["min"], "max": q_ref_result["max"],
            "minimum": q_ref_spec.get("minimum"), "maximum": q_ref_spec.get("maximum"),
        },
    ]


def _save_plot(runs, path):
    fig, ax = plt.subplots(figsize=(5, 3.5))
    for r in runs:
        label = f"{r['conditions'].get('corner')}/{r['conditions'].get('temperature')}C"
        ax.plot([f / 1e9 for f in r["freqs"]], r["q"], label=label)
    ax.set_xscale("log")
    ax.set_xlabel("frequency (GHz)")
    ax.set_ylabel("differential Q")
    legend_if_any(ax, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
