"""Parser for the spiral topology's EM-extracted Y11(f) -- reads the JSON
`run_one_openems` writes as its data_file (NOT ngspice wrdata output; this
test has no .sch testbench at all, the openEMS FDTD run IS the
measurement -- see run_sim.py's run_one_openems() and
analog_designer_core's openems_generator_runner.py, which runs inside the
container and calls inductor_spiral_generator.py's
build_openems_structure()/fit_electrical_params()). Same Q/SRF definitions
as tb_yparam.py (Q = -Im(Y11)/Re(Y11), SRF = Im(Y11) zero-crossing) so EM
and SPICE-placeholder results stay directly comparable."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from parser_common import typical_min_max, legend_if_any

_SCH_INDUCTOR_DIR = Path(__file__).resolve().parents[2] / "sch" / "inductor"
# This test/parser is shared across every generator-backed inductor
# topology (not spiral-specific despite the filename -- see
# openems_inductor_status.md's 2026-09-14 refactor entry), so the layout
# preview needs to load whichever topology's own generator produced the
# cached geometry. There's no generator-path field in the cache itself (see
# extract()), so the generator module is picked by which free-geometry keys
# are present -- each topology's geometry_from_params() has a distinct,
# non-overlapping key set by construction (spiral: inner_radius_um/n_turns/
# track_width_um/spacing_um; loop: width_um/height_um/track_width_um).
_GENERATOR_BY_GEOMETRY_KEY = {
    "inner_radius_um": "inductor_spiral_generator.py",
    "width_um": "inductor_loop_generator.py",
}


def _load_generator(filename):
    """Dynamically loads a generator module by file path (same pattern
    run_sim.py's own load_parser()/_load_generator_module() use) -- this
    parser runs on the HOST (not in the eda-env-designer container), so
    only each generator's pure-Python geometry/preview functions are ever
    called from here, never build_openems_structure() (needs CSXCAD/
    openEMS, container-only)."""
    path = _SCH_INDUCTOR_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract(data_path):
    data_path = Path(data_path)
    with open(data_path) as f:
        cached = json.load(f)
    # run_one_openems() writes an optional "<data_path stem>__field.png"
    # sibling file next to data_path itself whenever a real FDTD run
    # produced a field dump (never in placeholder mode, and best-effort
    # even in a real run -- see render_field_dump()'s own docstring) --
    # None here just means "no field PNG for this run", not an error.
    field_png = data_path.with_name(f"{data_path.stem}__field.png")
    # 2026-09-15: run_one_openems() also copies out one "<stem>__field_<label>.png"
    # sibling per entry in the generator's own FIELD_DUMP_NAMES dict (e.g.
    # metal5/metal4/via4/substrate -- see inductor_spiral_generator.py's own
    # FIELD_DUMP_NAMES docstring), best-effort same as field_png above --
    # glob rather than a fixed label list so this doesn't need updating
    # every time a generator's own dump set changes.
    field_pngs = {
        p.stem.rsplit("__field_", 1)[1]: p
        for p in data_path.parent.glob(f"{data_path.stem}__field_*.png")
    }
    # run_one_openems() writes the generator's fitted pi-model params
    # ('l'/'rs'/'cox'/'rsub'/'csub'/'cs') to a fixed "fitted.params.json" in
    # the SAME directory as data_path (that's the --out path passed to
    # openems_generator_runner.py -- confirmed against a live run's actual
    # command line, not assumed) -- read it here (best-effort: absent for
    # older cached runs or if only --cache-out was ever produced) so
    # evaluate() can compare the fitted lumped model against the raw EM
    # sweep for a fit-quality plot.
    fitted_path = data_path.with_name("fitted.params.json")
    fitted = None
    if fitted_path.exists():
        with open(fitted_path) as f:
            fitted = json.load(f)
    return {
        "freqs": cached["freqs_hz"], "q": cached["q"],
        "re": cached["re"], "im": cached["im"],
        "srf_ghz": cached["srf_ghz"], "peak_q": cached["peak_q"],
        "peak_q_freq_ghz": cached["peak_q_freq_ghz"],
        "geometry": cached.get("geometry"),
        "field_png": field_png if field_png.exists() else None,
        "field_pngs": field_pngs,
        "fitted": fitted,
    }


def evaluate(runs, outputs, typical, plot_base=None):
    srf_spec, q_spec = outputs
    # Single condition (corner=tt only, see config.json) -- an EM run costs
    # hours, sweeping corner/temperature the way ngspice tests do isn't
    # viable, so `runs` here always has exactly one entry. typical_min_max
    # still works fine with one run (typical=min=max=that run's value).
    if all(r["srf_ghz"] is None for r in runs):
        srf_result = {"typical": float("inf"), "min": float("inf"), "max": float("inf")}
    else:
        srf_result = typical_min_max(runs, typical, lambda r: r["srf_ghz"])
    q_result = typical_min_max(runs, typical, lambda r: r["peak_q"])

    if plot_base:
        _save_qf_plot(runs, f"{plot_base}.png")
        _save_z_plot(runs, f"{plot_base}__z.png")
        _save_fit_plot(runs, f"{plot_base}__fit.png")
        _save_layout_plot(runs, f"{plot_base}__layout.png")
        _save_field_plot(runs, f"{plot_base}__field.png")
        _save_extra_field_plots(runs, plot_base)

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


def _save_qf_plot(runs, path):
    # Also overlays Q(f) implied by the fitted series-Rs+jwL model alone
    # (same Rs_total=2*fitted['rs']/L_total=2*fitted['l'] reconstruction as
    # _save_fit_plot(), same per-half-undoing reasoning -- see that
    # function's own docstring) whenever fitted.params.json was found, so
    # this plot answers "does the lumped model's own Q match the simulated
    # Q" directly, not just Re/Im(Y11) shape agreement.
    fig, ax = plt.subplots(figsize=(5, 3.5))
    for r in runs:
        freqs = np.array(r["freqs"])
        freqs_ghz = freqs / 1e9
        ax.plot(freqs_ghz, r["q"], label="EM (openEMS)")
        fitted = r.get("fitted")
        if fitted:
            rs_total = 2 * fitted["rs"]
            l_total = 2 * fitted["l"]
            w = 2 * np.pi * freqs
            y_model = 1.0 / (rs_total + 1j * w * l_total)
            q_model = -y_model.imag / y_model.real
            ax.plot(freqs_ghz, q_model, "--", label="Rs+jwL fit")
    ax.set_xscale("log")
    ax.set_xlabel("frequency (GHz)")
    ax.set_ylabel("Q")
    legend_if_any(ax, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_z_plot(runs, path):
    """Z11(f) = 1/Y11(f) -- Re/Im on separate y-axes since they can differ
    by orders of magnitude across the sweep (Re(Z11) starts near Rs and
    falls with skin-effect-like behavior, Im(Z11) ~ w*L grows roughly
    linearly for a well-behaved inductor). Same Q/Y11 sign convention as
    _save_qf_plot -- no extra conjugation here, this is a pure 1/Y11 of
    whatever's already in the cache."""
    fig, ax_re = plt.subplots(figsize=(5, 3.5))
    ax_im = ax_re.twinx()
    for r in runs:
        y = np.array(r["re"]) + 1j * np.array(r["im"])
        z = 1.0 / y
        freqs_ghz = [f / 1e9 for f in r["freqs"]]
        ax_re.plot(freqs_ghz, z.real, color="tab:blue", label="Re(Z11)")
        ax_im.plot(freqs_ghz, z.imag, color="tab:orange", label="Im(Z11)")
    ax_re.set_xscale("log")
    ax_re.set_xlabel("frequency (GHz)")
    ax_re.set_ylabel("Re(Z11) (ohm)", color="tab:blue")
    ax_im.set_ylabel("Im(Z11) (ohm)", color="tab:orange")
    ax_re.tick_params(axis="y", labelcolor="tab:blue")
    ax_im.tick_params(axis="y", labelcolor="tab:orange")
    ax_re.axhline(0, color="gray", linewidth=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_fit_plot(runs, path):
    """Overlays the raw EM-extracted Y11(f) against the Y11(f) implied by
    the fitted series-Rs+jwL model alone (Rs_total=2*fitted['rs'],
    L_total=2*fitted['l'] -- fitted.params.json stores PER-HALF values, see
    inductor_spiral_generator.py's/inductor_loop_generator.py's own
    fit_electrical_params() docstring; x2 undoes that split since the raw
    Y11 here was measured across the WHOLE one-port winding, not half of
    it). Shades the low-frequency window fit_electrical_params() actually
    averaged over (its own n_fit = max(3, len(freqs)//20) lowest points) --
    everything outside that shaded band is the model EXTRAPOLATING, not
    fitted, so a visible divergence there is expected/normal, not
    necessarily a bug; a divergence INSIDE the shaded band would mean the
    fit itself is bad."""
    fitted = runs[0].get("fitted")
    if not fitted:
        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.text(0.5, 0.5, "fit-quality plot:\nno fitted.params.json for this run", ha="center", va="center", fontsize=8)
        ax.axis("off")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return

    rs_total = 2 * fitted["rs"]
    l_total = 2 * fitted["l"]

    fig, (ax_re, ax_im) = plt.subplots(2, 1, figsize=(5, 6), sharex=True)
    for r in runs:
        freqs = np.array(r["freqs"])
        freqs_ghz = freqs / 1e9
        y_em = np.array(r["re"]) + 1j * np.array(r["im"])
        w = 2 * np.pi * freqs
        y_model = 1.0 / (rs_total + 1j * w * l_total)

        n_fit = max(3, len(freqs) // 20)
        for ax in (ax_re, ax_im):
            ax.axvspan(freqs_ghz[0], freqs_ghz[n_fit - 1], color="gray", alpha=0.15,
                       label="fit window" if ax is ax_re else None)
        ax_re.plot(freqs_ghz, y_em.real, color="tab:blue", label="Re(Y11) EM")
        ax_re.plot(freqs_ghz, y_model.real, "--", color="tab:blue", alpha=0.7, label="Re(Y11) Rs+jwL fit")
        ax_im.plot(freqs_ghz, y_em.imag, color="tab:orange", label="Im(Y11) EM")
        ax_im.plot(freqs_ghz, y_model.imag, "--", color="tab:orange", alpha=0.7, label="Im(Y11) Rs+jwL fit")

    ax_im.set_xscale("log")  # sharex=True propagates this to ax_re too
    ax_re.set_ylabel("Re(Y11) (S)")
    ax_im.set_ylabel("Im(Y11) (S)")
    ax_im.set_xlabel("frequency (GHz)")
    legend_if_any(ax_re, fontsize=7)
    legend_if_any(ax_im, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_layout_plot(runs, path):
    # Regenerated on the HOST from the cached geometry (extract()'s own
    # "geometry" key, written by run_one_openems()/openems_generator_runner.py
    # alongside the Y11 sweep) via the matching generator's own pure-Python
    # geometry/save_layout_preview() functions (see _GENERATOR_BY_GEOMETRY_KEY
    # above for how "matching" is picked) -- no CSXCAD/openEMS needed for
    # this, so it works even for a cached (already computed) result without
    # touching the container again.
    geometry = runs[0].get("geometry")
    generator_file = None
    if geometry:
        for key, filename in _GENERATOR_BY_GEOMETRY_KEY.items():
            if key in geometry:
                generator_file = filename
                break
    if not geometry or generator_file is None:
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.text(0.5, 0.5, "layout preview:\nno cached geometry for this run", ha="center", va="center", fontsize=8)
        ax.axis("off")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return
    generator = _load_generator(generator_file)
    if generator_file == "inductor_loop_generator.py":
        generator.save_layout_preview(geometry, str(path))
    else:
        centerline = generator.octagonal_spiral_centerline(
            geometry["inner_radius_um"], geometry["n_turns"],
            geometry["track_width_um"], geometry["spacing_um"],
        )
        generator.save_layout_preview(centerline, geometry["track_width_um"], str(path))


def _save_field_plot(runs, path):
    # The actual current-density-concentration PNG is rendered INSIDE the
    # container by openems_generator_runner.py's render_field_dump()
    # (needs h5py against the openEMS-written HDF5 dump -- not available
    # on this host, confirmed) right after a real FDTD run, then cached by
    # run_one_openems() as a "<data-file>__field.png" sibling next to the
    # Y11 JSON; extract() already resolved that into runs[i]["field_png"].
    # This function's only job is to copy it into place -- never available
    # in ANALOG_DESIGNER_OPENEMS_PLACEHOLDER mode (no real FDTD ran) or
    # before the field dump/render pipeline has been validated against a
    # real spiral run (see add_field_dump()'s own docstring in
    # inductor_spiral_generator.py for what's confirmed vs. not yet).
    field_png = runs[0].get("field_png")
    if field_png is None:
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.text(
            0.5, 0.5, "current density / field dump:\nnot available for this run\n"
            "(placeholder mode, or the dump/render step failed --\nsee openems_run.log)",
            ha="center", va="center", fontsize=8,
        )
        ax.axis("off")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return
    with open(field_png, "rb") as src, open(path, "wb") as dst:
        dst.write(src.read())


def _save_extra_field_plots(runs, plot_base):
    """Copies out one '<plot_base>__field_<label>.png' per per-layer dump
    extract() found (runs[0]['field_pngs'], e.g. metal5/metal4/via4/
    substrate -- see the generator's own FIELD_DUMP_NAMES) -- same
    "globs test*.png, no GUI code needed" convention every other plot here
    already relies on, so each layer shows up as its own automatic tab.
    Unlike _save_field_plot(), no placeholder is written for a missing
    label -- these are purely additive extras (absent entirely for older
    cached runs, placeholder-mode runs, or topologies with fewer layers
    like 'loop'), not a fixed slot that always needs SOME image."""
    for label, src_path in runs[0].get("field_pngs", {}).items():
        with open(src_path, "rb") as src, open(f"{plot_base}__field_{label}.png", "wb") as dst:
            dst.write(src.read())
