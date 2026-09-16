# gf180mcu_mh_ip__nfrac_pll

Analog IP for a **fractional-N PLL** in GlobalFoundries' open **GF180MCU**
process (`gf180mcuD` variant), targeting submission to
[**Chipalooza Challenge #3**](https://opencircuitdesign.com/chipalooza/rules-3.html)
(opencircuitdesign.com / Tim Edwards), fabricated via
[wafer.space](https://wafer.space/). Designed and simulated through the
[analog-designer-core](https://github.com/moduhub/analog-designer-core)
tool: schematic capture in xschem, simulation via ngspice/Xyce/openEMS, and a
`config.json`-driven pipeline for generating/exploring parameter variations
and scoring them against design profiles -- same workflow as the sibling
`ihp_mh_ip__cmos_vref` project.

## Status: bring-up / everything here is a test

No block in this repo is finalized silicon-ready IP yet -- every schematic,
generator and testbench below is still in active bring-up, and `sim/`
(gitignored, tool-regenerated) is full of exploratory runs, not golden
results. Treat everything as work-in-progress until this note says
otherwise.

What exists so far:

- **`inductor`** -- five topologies: `placeholder_rlc`/`ind_03_90`/
  `ind_05_220` (carried-over SKY130 RLC-pi equivalents, not real GF180MCU
  models, kept only for comparison) and the real GF180MCU ones,
  `spiral` (octagonal) and `loop` (simple rectangular), both characterized
  by an openEMS 3D FDTD run and fit to a shared pi-model
  (`sch/inductor/pi_model_fit.py`). Open issue: the `spiral` topology's Q
  sign/magnitude is still under investigation.
- **`vco`** -- `quadrature_lc` (cross-coupled quadrature LC-VCO, ported
  from opensubghz's SKY130 design) and `quadrature_lc_cascode1` (cascoded
  variant, added to recover loop-gain margin against the placeholder
  inductor's Q). Both still use the `placeholder_rlc` inductor, not the
  real `spiral`/`loop` models. Startup/loop-gain closure against a real
  GF180MCU inductor is not yet confirmed.
- **`divider`** -- `etspc_d2d3`, an E-TSPC divide-by-2/3 prescaler.
  Functional simulation confirms `sw=0` gives exactly ratio 2; `sw=5.0`
  unexpectedly also measures 2 instead of the assumed 3 -- open issue.
- **`top`** -- symbol only. No PFD, charge pump, loop filter, or top-level
  testbench exists yet; the `top` tests declared in `config.json` (`op`,
  `spectral`, `lock`, `freq_range`) describe target specs, not something
  runnable today.

## GF180MCU PDK support

Requires the `eda-env` `eda-env-designer:gf180mcuD` / `eda-env-runner:gf180mcuD`
images, built from a new `PDK_FAMILY=gf180mcu PDK=gf180mcuD` target added to
the sibling [`eda-env`](../eda-env) repo's Docker setup (see that repo's
`docker-compose.yml` usage comments and `docker/open_pdks/install-gf180mcu.sh`).
The `gf180mcuD` variant is confirmed against the official Chipalooza harness
chip, [`RTimothyEdwards/gf180mcu_ocd_openframe`](https://github.com/RTimothyEdwards/gf180mcu_ocd_openframe)
(`PDK:=gf180mcuD` in its `lvs/run_lvs.sh`).

GF180MCU ships plain SPICE (BSIM4) models for **both** ngspice and Xyce
natively (`libs.tech/xyce/*.spice`, distinct from `libs.tech/ngspice/*.spice`,
both staged straight from the `gf180mcu_fd_pr` repo by `open_pdks`) -- verified
by actually running `Xyce` against `libs.tech/xyce/sm141064.spice` +
`libs.tech/xyce/design.spice` (the latter sets `fnoicor`/`sw_stat_*`/etc, and
is required -- device parameters reference those globals) in the built
`eda-env-runner:gf180mcuD` image, instantiating a single `nfet_03v3` device.

**Known gotcha (confirmed, not just suspected):** Xyce requires `.ENDL` to
repeat the name of the `.LIB` block it closes (e.g. `.ENDL NFET_03V3_STAT`),
but `sm141064.spice`'s statistical/Monte-Carlo sub-libraries (used for
mismatch/corner variation -- `*_STAT`, `*_MC`, `MIMCAP_STATISTICAL`, etc., NOT
the core deterministic device models like `nfet_03v3` itself) all close with
a bare, unnamed `.endl`, which ngspice accepts but Xyce rejects
("`.ENDL encountered without library name`"), aborting the whole simulation
(~400 accumulated errors) even though the actual device model used in the
netlist parses fine. This will bite the first real Xyce/`.HB` testbench.
Fix is mechanical (rewrite each bare `.endl` to name its enclosing `.lib`) --
same idea as this repo's sibling `eda-env`'s own `sky130_xyce_convert` step,
just much smaller in scope here; not yet done, since it belongs with the
first real Xyce testbench rather than this infrastructure pass. Also still
unconfirmed: coverage of every device flavor a given testbench will need, and
that `.HB` actually converges on a real circuit -- inductors in particular
aren't part of the BSIM/Xyce model set and need their own modeling approach
(ideal element or EM-extracted).

## Running with analog-designer-core

Simulation and parameter-variation exploration are driven by
[`analog-designer-core`](https://github.com/moduhub/analog-designer-core),
a separate tool repo. It is not vendored here -- clone it alongside this
repo and point it at this project folder.

```sh
git clone https://github.com/moduhub/analog-designer-core.git
cd analog-designer-core
pip install -r requirements.txt
```

It needs a running EDA container matching `config.json`'s
`container.image` (`eda-env-designer:gf180mcuD`). The image is published
publicly on Docker Hub as
[`akvitschal/eda-env-designer:gf180mcuD`](https://hub.docker.com/r/akvitschal/eda-env-designer);
pull and re-tag it to the name `config.json` expects:

```sh
docker pull akvitschal/eda-env-designer:gf180mcuD
docker tag akvitschal/eda-env-designer:gf180mcuD eda-env-designer:gf180mcuD
```

Then, from `analog-designer-core`:

```sh
# GUI (Tkinter): opens this repo as the active project
python -m analog_designer.gui.app /path/to/gf180mcu_ak_ip__nfrac_pll

# CLI: run every declared test for one block/topology's default variation
python -m analog_designer.sim.run_sim \
    --project-root /path/to/gf180mcu_ak_ip__nfrac_pll \
    --block inductor --topology loop
```

Omit `--block`/`--topology` to use the first one declared in
`config.json`; pass an existing name from `sim/variations.jsonl` as a
positional argument to `run_sim` to re-check a specific variation instead
of the defaults. See `analog-designer-core`'s own README for the GUI's
"Open Folder" flow and the other CLI entry points
(`gen_variations`, `manual_variation`, `check_params`, `diagnose_tb`).

## Pending decisions

- **Balanced/differential vs. single-ended signaling** across the PLL chain
  -- not decided yet. Chipalooza's rules assume single-ended by default
  ("no differential requirements stated"), and the shared test chip's pin
  budget is tight (up to 4 dedicated pins + 4 shared/multiplexed analog
  lines per project, across up to 18 projects on one die) -- going
  differential is possible but has a real pin-budget cost to weigh.
- **PLL architecture / block diagram**: overall topology (integer paths,
  fractional-N scheme, number of divider stages) not yet settled. See
  [`RTimothyEdwards/fracn_dll`](https://github.com/RTimothyEdwards/fracn_dll)
  for a fractional-N DLL reference from the same open_pdks/Chipalooza
  ecosystem, worth reviewing once this is scoped.
- **VCO topology**: quadrature LC (cross-coupled, ported from the
  `opensubghz` SKY130 reference) is implemented as `quadrature_lc`/
  `quadrature_lc_cascode1`, but still runs on the `placeholder_rlc`
  inductor rather than a real GF180MCU model, and startup/loop-gain
  closure against `spiral`/`loop` is unconfirmed -- not settled as final.
- **Divider chain composition**: `etspc_d2d3` (divide-by-2/3) exists and
  simulates, but how it chains with further stages to reach the needed
  overall division ratio is not yet defined.
- **Phase/frequency detector**: no design or even topology choice yet.
- **Voltage rails**: Chipalooza rules specify digital 3.3V / analog 5.0V as
  the operating rails; `config.json`'s `technology.mosfet_limits` currently
  reflects GF180MCU's two device flavors' absolute ratings (3.3V "lv" /
  6.0V "hv"), not yet cross-checked against the actual SPICE model validity
  ranges.
- **Repo name**: the local project folder and internal references still
  use the original `gf180mcu_mh_ip__nfrac_pll` (`<pdk>_<team>_ip__<block>`
  convention, matching `sg13cmos5l_ocd_chipalooza`-style names elsewhere in
  the Chipalooza/open_pdks ecosystem). The public GitHub repo is published
  under `gf180mcu_ak_ip__nfrac_pll` instead -- only the GitHub-facing name
  changed so far; whether to carry that into the local folder/internal
  references too is still open.

## Layout

| Dir | Contents |
| --- | --- |
| `config.json` | Blocks, topologies, tests, profiles -- single source of truth. |
| `sch/` | Topology schematics (`.sch`/`.sym`), plus each topology's own parameters right next to it (`sch/<block>/<topology>.params.json`). A "generator"-backed topology (e.g. `inductor/spiral`, `inductor/loop`) additionally keeps its Python generator module in the same directory (`sch/inductor/inductor_spiral_generator.py`) -- a small PDK-specific plugin (geometry math + electrical fit only, no run/CLI code) referenced from `config.json`'s `"generator"` key, same project-repo-relative-path convention as `"parser"`/`"testbench"`. |
| `tb/` | Testbenches + parsers (`tb/<block>/tb_*.py`), shared helpers in `tb/_shared/`. |
| `sim/` | Simulation output (gitignored, tool-regenerated) -- exploratory bring-up runs, not golden results. |
