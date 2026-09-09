"""Parser for tb_yparam.sch: one-port Y11 AC sweep of the inductor block --
Q(f), self-resonant frequency (SRF), and SRF-as-max-operating-frequency.
Y11 = I(a)/V(a) with b/sub grounded, ct floating (still internally bridged
via L1/L2). Q = -Im(Y11)/Re(Y11) (sign flip: an inductive one-port has
Im(Y11) < 0, so -Im/Re is what comes out positive, matching conventional Q
sign). SRF = frequency where Im(Y11) crosses from negative (inductive) to
positive (capacitive) -- also reported as this block's max operating
frequency, since above it the structure no longer behaves as an inductor."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from parser_common import read_data, typical_min_max, legend_if_any


def extract(data_path):
    rows = read_data(data_path)
    freqs = [r[0] for r in rows]
    re = [r[1] for r in rows]
    im = [r[2] for r in rows]

    q = [(-i / r) if r else float("nan") for r, i in zip(re, im)]

    srf_hz = None
    for i in range(1, len(freqs)):
        if im[i - 1] < 0 <= im[i]:
            frac = -im[i - 1] / (im[i] - im[i - 1])
            srf_hz = freqs[i - 1] + frac * (freqs[i] - freqs[i - 1])
            break

    peak_q = max(q)
    peak_q_freq_hz = freqs[q.index(peak_q)]

    return {
        "freqs": freqs, "q": q,
        "srf_ghz": (srf_hz / 1e9) if srf_hz else None,
        "peak_q": peak_q, "peak_q_freq_ghz": peak_q_freq_hz / 1e9,
    }


def evaluate(runs, outputs, typical, plot_base=None):
    srf_spec, q_spec = outputs
    srf_result = typical_min_max(runs, typical, lambda r: r["srf_ghz"])
    q_result = typical_min_max(runs, typical, lambda r: r["peak_q"])

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
    ]


def _save_plot(runs, path):
    fig, ax = plt.subplots(figsize=(5, 3.5))
    for r in runs:
        label = f"{r['conditions'].get('corner')}/{r['conditions'].get('temperature')}C"
        ax.plot([f / 1e9 for f in r["freqs"]], r["q"], label=label)
    ax.set_xscale("log")
    ax.set_xlabel("frequency (GHz)")
    ax.set_ylabel("Q")
    legend_if_any(ax, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
