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

## Status: greenfield

This repo currently contains **infrastructure only** -- no circuit blocks
(VCO, PFD, dividers, charge pump, loop filter) exist yet, not even as
placeholders. What's here:

- `config.json` -- minimal structural skeleton (container image, dirs,
  technology limits). `blocks` and `tests` are intentionally empty.
- `sch/`, `tb/`, `tb/_shared/` -- empty directories, ready for the first
  block.
- This README.

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

## Collaborators & current focus

| Who | Focus |
| --- | --- |
| kvitschal.eel@gmail.com (this repo's primary author) | Testbenches, starting with the VCO. |
| rnxrbb (Discord) | VCO / inductor design. Proposing a quadrature LC topology, inspired by [`opensubghz`](../opensubghz)'s `half_qvco_param` cross-coupled cell pair (two cells cross-coupled over an LC tank) -- that design is in SKY130 and needs porting to GF180MCU. |
| Cheng Fei Phung | Proposing divide-by-2 and divide-by-3 divider circuits. |
| *(unassigned)* | Phase/frequency detector -- nobody has started this yet. |

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
- **VCO topology**: quadrature LC (cross-coupled, per the `opensubghz`
  reference) vs. alternatives -- not finalized, and porting from SKY130
  device/inductor models to GF180MCU is unstarted.
- **Divider chain composition**: how the proposed divide-by-2/divide-by-3
  stages combine to reach the needed division ratios is not yet defined.
- **Phase/frequency detector**: no design or even topology choice yet.
- **Voltage rails**: Chipalooza rules specify digital 3.3V / analog 5.0V as
  the operating rails; `config.json`'s `technology.mosfet_limits` currently
  reflects GF180MCU's two device flavors' absolute ratings (3.3V "lv" /
  6.0V "hv"), not yet cross-checked against the actual SPICE model validity
  ranges.
- **Repo name** (`gf180mcu_mh_ip__nfrac_pll`): follows the
  `<pdk>_<team>_ip__<block>` convention already used across the
  Chipalooza/open_pdks ecosystem (e.g. `sg13cmos5l_ocd_chipalooza`,
  `sg13cmos5l_vyges_ip__pll_rosc`) -- no rename needed.

## Layout

| Dir | Contents |
| --- | --- |
| `config.json` | Blocks, topologies, tests, profiles -- single source of truth (currently empty `blocks`/`tests`). |
| `sch/` | Topology schematics (`.sch`/`.sym`), plus each topology's own parameters right next to it (`sch/<block>/<topology>.params.json`) -- empty for now. A "generator"-backed topology (e.g. `inductor/spiral`) additionally keeps its Python generator module in the same directory (`sch/inductor/inductor_spiral_generator.py`) -- a small PDK-specific plugin (geometry math + electrical fit only, no run/CLI code) referenced from `config.json`'s `"generator"` key, same project-repo-relative-path convention as `"parser"`/`"testbench"`. |
| `tb/` | Testbenches + parsers (`tb/<block>/tb_*.py`), shared helpers in `tb/_shared/` -- empty for now. |
| `sim/` | Simulation output (gitignored, tool-regenerated). Doesn't exist yet. |
