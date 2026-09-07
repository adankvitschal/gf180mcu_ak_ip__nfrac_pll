# Known issues

## GF180MCU `cap_nmos_03v3` fails to parse in ngspice-47 ("Mismatch: N formal but M actual params")

**Status: unresolved, blocks any simulation using the VCO varactor (`cap_nmos_03v3`/`cap_pmos_03v3`) on ngspice.**

### Symptom

Running any testbench that instantiates `cap_nmos_03v3` (or `cap_pmos_03v3`,
`cap_nmos_03v3_b`, `cap_pmos_03v3_b`, ... -- same family) via ngspice fails
with:

```
Warning: redefinition of .subckt cap_nmos_03v3, ignored
...
Error: Mismatch: 7 formal but 3 actual params.
c_length=30u;c_width=30u;dtemp=0;cvar1=$;cvar2=$;cvar3=$;cvar4=$;
Error: Syntax error: letter [$]
Error: Undefined parameter [cvar1]
```

`cvar1`/`cvar2`/`cvar3`/`cvar4` are the varactor model's own **internal**
`.param` statements (tanh-based C-V curve coefficients), declared right
after the `.subckt` header:

```spice
.lib moscap
.subckt cap_nmos_03v3 1 2 c_length=l c_width=w dtemp=0
.param cvar1=0.002003
.param cvar2=0.00198
.param cvar3=6.25
.param cvar4=-3.9375
c_moscap 1 2 c='cap_nmos_03v3_corner*c_length*c_width*(cvar1+cvar2*tanh(cvar3*v(1,2)+cvar4))' dtemp=dtemp
.ends cap_nmos_03v3
```

ngspice appears to be miscounting these 4 internal `.param` lines as
*additional formal parameters* of the subcircuit (3 declared + 4 internal =
7 "formal"), then failing to resolve them from the call site (which only
ever passes `c_width`/`c_length`, sometimes `dtemp`).

### Minimal reproduction

Confirmed on `ngspice-47` (installed in `eda-env-designer:gf180mcuD`,
`/usr/local/share/ngspice/bin/ngspice`). Fails **even in total isolation** --
no VCO, no hierarchy, no other device present:

```spice
.include /usr/local/share/pdk/gf180mcuD/libs.tech/ngspice/design.spice
.lib /usr/local/share/pdk/gf180mcuD/libs.tech/ngspice/sm141064.spice moscap_typical
.lib /usr/local/share/pdk/gf180mcuD/libs.tech/ngspice/sm141064.spice moscap
V3 vt 0 dc 1.65
V4 d 0 dc 0.5
XC1 vt d cap_nmos_03v3 c_width=30u c_length=30u
.control
op
.endc
.end
```

A hand-written subcircuit with the exact same *shape* (header with 3
default keyword params, 4 sequential internal `.param` lines, one element)
does **NOT** reproduce the bug -- so it's specific to something in the real
PDK file's content, not the general pattern. A version using the real
formula (`tanh(...)`, referencing the external `cap_nmos_03v3_corner`
param) hits a *different* error (`Undefined parameter
[cap_nmos_03v3_corner]`, a plain scoping issue, not yet chased down)
instead of reproducing the `cvar1=$` corruption -- meaning the isolated
repro still isn't 100% faithful to whatever the real file triggers. Next
session should start by reproducing against the **actual** `sm141064.spice`
content (as done above) rather than a hand-typed stand-in.

### What's been ruled out (don't re-try these)

- **Not about our own `m=` usage.** Removing `m=` entirely from the
  `XC1`/`XC2` varactor instantiation changes nothing -- confirmed the exact
  same corruption still happens.
- **Not the automatic "M-multiplier hierarchy" ngspice feature**
  (`Warning: m=xx on .subckt line will override multiplier m hierarchy!`,
  seen because GF180MCU's own `nfet_03v3`/`pfet_03v3` declare native `m=`).
  Confirmed by reproducing the bug with **zero** `nfet_03v3`/`m=` anywhere
  in the netlist at all (see minimal repro above) -- `cap_nmos_03v3` alone
  is enough.
- **Not `ngbehavior` compatibility mode.** Tried `.options
  ngbehavior=spice3` (inline) and `set ngbehavior=spice3` (via
  `.spiceinit`) -- no change. Also tried matching the team's own working
  `eda-env/docker/user_config/home/spice.rc` exactly (`set
  num_threads=16`, `set ngbehavior=hsa`, `set ng_nomodcheck`) -- also no
  change, byte-identical error. `ng_nomodcheck` specifically (which
  disables some ngspice model-consistency checking) was the most promising
  lead and it did nothing either.
- **Not a `.lib` section-selection gap** (unlike two OTHER real bugs found
  and fixed this session, see below) -- `moscap_typical` (correction
  coefficients) and `moscap` (the actual subckt bodies) are both being
  loaded; the subckt content that ngspice reports IS the real one, just
  miscounted.

### Suggested next steps

1. Reproduce against the real file (not a hand-typed stand-in) as the
   starting point, per above.
2. Check whether this is a **known upstream ngspice bug** (search
   ngspice's own bug tracker / mailing list for "Mismatch formal actual
   params" or similar, and specifically for GF180MCU + ngspice reports --
   the GF180MCU open-source community may have already hit and worked
   around this).
3. Check whether a **newer ngspice release** than 47 fixes it (would mean
   bumping `NGSPICE_VERSION` in `eda-env/docker/Dockerfile` -- currently
   pinned to `ngspice-47`, itself a recent bump from a dead `ngspice-46`
   SourceForge link, see that Dockerfile's own comment).
4. If neither pans out quickly: this is *only* a placeholder varactor
   anyway (see `sch/vco/half_qvco_cell.sch`'s own header comment) -- consider
   swapping to a different GF180MCU capacitor primitive that doesn't hit
   this parsing bug (e.g. a plain `cap_mim_*` MiM cap with no tuning, just
   to unblock `.op`/`.tran` current-consumption characterization of the
   rest of the VCO while a real varactor choice is worked out separately),
   rather than continuing to chase this specific device.

### Everything else in the VCO/inductor chain is confirmed working

For context, these are the OTHER bugs found and fixed in the same
debugging session (all independently verified by running real `ngspice`
against the real, materialized hierarchy -- see git history for exact
diffs):

1. `cap_nmos_03v3`/`cap_pmos_03v3` etc. live in a separate `.lib moscap` /
   `.lib moscap_<corner>` section, not pulled in by `.lib sm141064.spice
   <corner>` alone -- fixed by adding both explicitly in
   `tb/vco/tb_op.sch`'s stimuli block.
2. ngspice's own "too few parameters for subcircuit type vco" -- fixed by
   adding an `m=1` default parameter to `sch/vco.sym` and
   `sch/vco/half_qvco_cell.sym`'s own `K{}` `format`/`template` (an
   ngspice automatic-multiplier-hierarchy requirement once ANY subckt in
   the deck, like `nfet_03v3`, declares native `m=`).
3. The inductor's inline placeholder RLC `.subckt` broke with "unknown
   subckt" once nested two hierarchy levels away from its own definition
   (SPICE local-`.subckt` scoping) -- fixed by promoting it to its own
   real block (`sch/inductor.sym` + `sch/inductor/inductor_placeholder_rlc.sch`,
   wired into `config.json`'s `blocks.vco.topologies.quadrature_lc.sub_blocks`)
   with the RLC elements directly in that block's own top-level body
   (no nested subckt at all -- sidesteps the scoping problem entirely).
4. `nfet_03v3_noia`/`sw_stat_mismatch`/etc (design.spice's own globals)
   were "undefined" -- fixed by using `.include 'models_dir'/design.spice`
   instead of `.lib 'models_dir'/design.spice` (that file has no
   `.lib`/`.endl` wrapper around its top-level `.param` statements, so
   `.lib file` with no section name was being misinterpreted as "look for
   a section literally named `design.spice`", never actually loading the
   file's content).

`mh-analog-designer-lite` and `mh-analog-designer` (pro)'s own
`run_sim.py` were also patched this session to recognize the `gf180mcu`
PDK family at all (paths without `/models`, no Xyce plugin, GF180MCU's own
corner-section names) -- unrelated to this specific bug, but necessary for
any of the above to run through the real tool instead of a manual `xschem`
+ `ngspice` test loop.
