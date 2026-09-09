"""Parser for tb_loop_gain.sch: negative-resistance loop-gain check on the
VCO's own closed I_p/I_n coupling loop (see tb_loop_gain.sch's own header
comment for the measurement technique -- same Y11 one-port method
tb_yparam.py already uses for the bare inductor, applied here to the full
active core+tank instead). Resonance is where Im(Y11) crosses zero;
Re(Y11) there is the margin: negative means net negative resistance
(oscillation should grow), positive means net loss (matches a decaying
tb_startup kick response, no sustained oscillation)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from parser_common import read_data, typical_min_max, legend_if_any


def extract(data_path):
    rows = read_data(data_path)
    freqs = [r[0] for r in rows]
    re = [r[1] for r in rows]
    im = [r[2] for r in rows]

    resonance_hz = None
    margin_s = None
    for i in range(1, len(freqs)):
        if im[i - 1] < 0 <= im[i]:
            frac = -im[i - 1] / (im[i] - im[i - 1])
            resonance_hz = freqs[i - 1] + frac * (freqs[i] - freqs[i - 1])
            margin_s = re[i - 1] + frac * (re[i] - re[i - 1])
            break

    return {
        "freqs": freqs, "re": re, "im": im,
        "resonance_ghz": (resonance_hz / 1e9) if resonance_hz else None,
        "margin_ms": (margin_s * 1e3) if margin_s is not None else None,
    }


def evaluate(runs, outputs, typical, plot_base=None):
    freq_spec, margin_spec = outputs
    freq_result = typical_min_max(runs, typical, lambda r: r["resonance_ghz"])
    margin_result = typical_min_max(runs, typical, lambda r: r["margin_ms"])

    if plot_base and len(runs) > 1:
        _save_plot(runs, f"{plot_base}.png")

    return [
        {
            "name": freq_spec["description"], "unit": freq_spec["unit"],
            "typical": freq_result["typical"], "min": freq_result["min"], "max": freq_result["max"],
            "minimum": freq_spec.get("minimum"), "maximum": freq_spec.get("maximum"),
        },
        {
            "name": margin_spec["description"], "unit": margin_spec["unit"],
            "typical": margin_result["typical"], "min": margin_result["min"], "max": margin_result["max"],
            "minimum": margin_spec.get("minimum"), "maximum": margin_spec.get("maximum"),
        },
    ]


def _save_plot(runs, path):
    """Both Y11 components, not just Re(Y11) -- the oscillation criterion
    needs BOTH: Im(Y11)=0 locates the resonance (dotted vertical lines,
    one per corner), and the black dot on the Re(Y11) panel is Re(Y11)
    evaluated AT that same resonance -- the actual margin (below the zero
    line = net negative resistance = should grow; above = net loss, matches
    a decaying tb_startup kick). A plot of Re(Y11) alone (the previous
    version of this function) shows the loss magnitude but not WHERE the
    resonance the criterion is judged at actually falls."""
    fig, (ax_im, ax_re) = plt.subplots(2, 1, figsize=(5, 5.5), sharex=True)
    for r in runs:
        label = f"{r['conditions'].get('corner')}/{r['conditions'].get('temperature')}C"
        freqs_ghz = [f / 1e9 for f in r["freqs"]]
        ax_im.plot(freqs_ghz, [v * 1e3 for v in r["im"]], label=label)
        ax_re.plot(freqs_ghz, [v * 1e3 for v in r["re"]], label=label)
        if r["resonance_ghz"] is not None:
            ax_im.axvline(r["resonance_ghz"], color="gray", linestyle=":", linewidth=0.7)
            ax_re.axvline(r["resonance_ghz"], color="gray", linestyle=":", linewidth=0.7)
            ax_re.scatter([r["resonance_ghz"]], [r["margin_ms"]], color="black", zorder=3, s=15)

    ax_im.axhline(0, color="black", linewidth=0.8)
    ax_im.set_xscale("log")
    ax_im.set_ylabel("Im(Y11) (mS)")
    ax_im.set_title("resonance: Im(Y11) = 0 (dotted)", fontsize=9)

    ax_re.axhline(0, color="black", linewidth=0.8)
    ax_re.set_xlabel("frequency (GHz)")
    ax_re.set_ylabel("Re(Y11) (mS)")
    ax_re.set_title("margin at resonance (dots): <0 grows, >0 decays", fontsize=9)
    legend_if_any(ax_re, fontsize=6)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
