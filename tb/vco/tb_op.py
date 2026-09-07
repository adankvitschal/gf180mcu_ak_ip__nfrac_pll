"""Parser for tb_op.sch: VCO operating-point checks (.op only for now).

Named tb_op rather than tb_power on purpose: this is meant to grow into
the one place that folds in further operating-point-adjacent VCO checks
(e.g. a quick oscillation-frequency sanity read) as they're added, instead
of spawning a new narrowly-scoped tb_<metric>.sch per metric."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from parser_common import read_data, in_spec, add_spec_bounds, legend_if_any, typical_min_max


def extract(data_path):
    """Raw reduction of one simulation run's .data file. No spec judgement."""
    rows = read_data(data_path)
    return {"current_ua": abs(rows[-1][-1]) * 1e6}


def evaluate(runs, outputs, typical, plot_base=None):
    """runs: list of {"conditions": {...}, "current_ua": ...}, one per
    condition (temperature, corner, ...) this test was simulated at.
    Returns one named metric: {typical, min, max} across all conditions."""
    spec = outputs[0]
    result = typical_min_max(runs, typical, lambda r: r["current_ua"])

    if plot_base and len(runs) > 1:
        _save_plot(runs, spec, typical, f"{plot_base}.png")

    return [{
        "name": spec["description"],
        "typical": result["typical"], "min": result["min"], "max": result["max"],
        "unit": spec["unit"],
        "minimum": spec.get("minimum"),
        "maximum": spec.get("maximum"),
    }]


def _save_plot(runs, spec, typical, path):
    """One column per corner, same convention as
    ihp_mh_ip__cmos_vref/tb/cmos_vref/tb_vref_power.py's own plot -- see
    its docstring for the reasoning (corner drives worst-case current,
    temperature is secondary spread within each corner)."""
    corners = list(dict.fromkeys(r["conditions"].get("corner") for r in runs))
    fig, ax = plt.subplots(figsize=(max(3, len(corners) * 1.2), 3.5))
    for i, corner in enumerate(corners):
        corner_runs = [r for r in runs if r["conditions"].get("corner") == corner]
        values = [r["current_ua"] for r in corner_runs]
        lo, hi = min(values), max(values)
        mid = (lo + hi) / 2
        color = "tab:green" if in_spec(lo, spec) and in_spec(hi, spec) else "tab:red"
        ax.errorbar(
            [i], [mid], yerr=[[mid - lo], [hi - mid]],
            fmt="none", ecolor=color, elinewidth=3, capsize=6, zorder=2,
        )
        typical_run = next((r for r in corner_runs if r["conditions"].get("temperature") == typical.get("temperature")), None)
        if typical_run:
            label = f"{typical['temperature']}°C" if i == 0 else None
            ax.scatter([i], [typical_run["current_ua"]], color="black", zorder=3, label=label)
    ax.set_xticks(range(len(corners)))
    ax.set_xticklabels(corners)
    ax.set_xlim(-0.5, len(corners) - 0.5)
    add_spec_bounds(ax, [r["current_ua"] for r in runs], spec, orientation="y")
    ax.set_xlabel("corner")
    ax.set_ylabel(f"{spec['description']} ({spec['unit']})")
    legend_if_any(ax, fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
