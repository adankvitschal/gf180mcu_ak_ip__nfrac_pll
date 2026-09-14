v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* Same stimuli as tb_op.sch (Vdd/Vtune/ibias/X1/load caps), swapped for a
* .tran startup transient instead of .op. Ikick (see stimuli block below)
* is a short current pulse on net5 (I_p) at t=0 -- ngspice's own .tran (no
* uic) op-point solve of this cross-coupled core is exactly symmetric on
* paper, and a purely symmetric starting point never breaks into
* oscillation on its own in a deterministic solver; the kick is what
* actually starts it, same role real device mismatch/noise plays in
* silicon. uic itself is deliberately NOT used -- it would zero every
* non-explicitly-'.ic'd node including the bias network, an unrealistic
* start point compared to letting ngspice's own op solver find the real
* bias first and kicking only the tank. Edges are 20p, not much faster --
* a 1p edge forces the transient's adaptive timestep control down to
* sub-fs to resolve it, which stalls the whole 100n run; 20p is still fast
* (broadband) relative to the tank's own ~ns-scale period but doesn't
* fight the timestep controller.
*
* tstop=8n, not the originally-intended 100n: at the current sizing the
* kick just decays (confirmed by tb_loop_gain -- Re(Y11) > 0 everywhere,
* no net negative resistance), and once the envelope decays into the
* solver's own numerical noise floor the LTE step control pathologically
* stalls trying to resolve noise, not real dynamics -- one run took 3+
* hours of CPU past that point without finishing, and even a 10n target
* didn't reliably finish in one docker-container lifetime (got to 9.77n
* and was still crawling). 8n comfortably captures the full decay envelope
* today, well short of where it starts crawling. Once the design actually
* has positive margin, extend tstop back out to see real growth + several
* steady-state cycles -- growth (unlike this decay-to-noise-floor case)
* shouldn't hit the same pathological stall, since the signal never drops
* to the numerical noise floor once it's growing.
N -300 -150 -300 -130 {lab=vdd}
N -180 -150 -180 -130 {lab=vtune}
N 20 -30 100 -30 {lab=#net1}
N 20 -100 20 -30 {lab=#net1}
N 240 90 240 120 {lab=GND}
N 20 -180 20 -160 {lab=vdd}
N 440 120 440 140 {lab=GND}
N 440 140 620 140 {lab=GND}
N 620 120 620 140 {lab=GND}
N 560 120 560 140 {lab=GND}
N 500 120 500 140 {lab=GND}
N 530 140 530 160 {lab=GND}
N 440 30 440 60 {lab=#net2}
N 360 30 440 30 {lab=#net2}
N 360 10 500 10 {lab=#net3}
N 500 10 500 60 {lab=#net3}
N 360 -30 560 -30 {lab=#net4}
N 560 -30 560 60 {lab=#net4}
N 360 -50 620 -50 {lab=#net5}
N 620 -50 620 60 {lab=#net5}
C {devices/vsource.sym} -300 -100 0 0 {name=Vdd value="dc 'vco_vdd'"}
C {devices/gnd.sym} -300 -70 0 0 {name=l3 lab=GND}
C {devices/vsource.sym} -180 -100 0 0 {name=Vtune value="dc 'vtune'"}
C {devices/gnd.sym} -180 -70 0 0 {name=l4 lab=GND}
C {devices/lab_pin.sym} -180 -150 0 1 {name=l5 lab=vtune}
C {sch/vco.sym} 240 -10 0 0 {name=X1}
C {devices/lab_pin.sym} 100 -70 0 0 {name=l6 lab=vdd}
C {devices/lab_pin.sym} 100 -50 0 0 {name=l7 lab=GND}
C {devices/lab_pin.sym} 100 50 0 0 {name=l8 lab=vtune}
C {devices/code.sym} 300 -300 0 0 {name=stimuli
only_toplevel=false
value="
.include 'models_dir'/design.spice
.lib 'models_dir'/sm141064.spice 'mos_corner'
.lib 'models_dir'/sm141064.spice moscap_'mos_corner'
.option TEMP='temperature'
.option warn=1
.option rshunt=1e12
.option gmin=1e-6
Ikick net5 GND pulse(0 1u 0 20p 20p 20p 1)
.control
save all
tran 5p 8n
let i_diff = v(net5) - v(net4)
let q_diff = v(net3) - v(net2)
set wr_singlescale
wrdata 'simpath'/'filename'_'N'.data i_diff q_diff
quit
.endc
"}
C {isource.sym} 20 -130 0 0 {name=I0 value='ibias'}
C {devices/lab_pin.sym} 240 120 0 0 {name=l1 lab=GND}
C {vdd.sym} -300 -150 0 0 {name=l10 lab=vdd}
C {vdd.sym} 20 -180 0 0 {name=l2 lab=vdd}
C {capa.sym} 440 90 0 0 {name=C1
m=1
value='cload'
footprint=1206
device="ceramic capacitor"}
C {capa.sym} 500 90 0 0 {name=C2
m=1
value='cload'
footprint=1206
device="ceramic capacitor"}
C {capa.sym} 560 90 0 0 {name=C3
m=1
value='cload'
footprint=1206
device="ceramic capacitor"}
C {capa.sym} 620 90 0 0 {name=C4
m=1
value='cload'
footprint=1206
device="ceramic capacitor"}
C {devices/gnd.sym} 530 160 0 0 {name=l9 lab=GND}
