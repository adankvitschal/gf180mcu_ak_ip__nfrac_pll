v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* Negative-resistance loop-gain check for the FULL quadrature core (both
* half_qvco_cell instances, coupled exactly as in the real circuit) --
* same Y11 one-port technique tb_yparam.sch already uses for the bare
* inductor (see tb_loop_gain.py). vco.sym's own I_p/I_n/Q_p/Q_n pins ARE
* the loop-coupling nodes (X1's own tank output IS X2's own injection
* input, and vice versa -- see vco_quadrature_lc.sch's own X1/X2 wiring),
* already exposed at this boundary exactly like tb_op.sch's own load caps
* already probe them -- no need to break the loop or isolate one half-cell
* by hand (an earlier attempt at that, tying I_p=I_n to a fixed rail,
* distorted M3/M4's own bias and gave a result at odds with tb_startup's
* observed decay; this version reuses the REAL closed loop instead).
*
* Vtest (floating AC source directly across I_p/I_n, one of the two
* already-exposed coupling ports) drives the one-port probe:
* y11 = i(vtest)/(v(ip)-v(in)). At the frequency where Im(y11) crosses
* zero (resonance), Re(y11) < 0 means net negative resistance --
* oscillation should grow; Re(y11) > 0 means net loss -- matches the
* decaying kick response already seen in tb_startup.
*
* Bias section (Vdd/Vtune/I0) copied verbatim from tb_op.sch's own,
* already-proven wiring -- same coordinates, so the same pin connections
* apply without re-deriving them by hand.
N -300 -150 -300 -130 {lab=vdd}
N -180 -150 -180 -130 {lab=vtune}
N 20 -30 100 -30 {lab=#net1}
N 20 -100 20 -30 {lab=#net1}
N 20 -180 20 -160 {lab=vdd}
N 240 90 240 120 {lab=GND}
C {devices/vsource.sym} -300 -100 0 0 {name=Vdd value="dc 'vco_vdd'"}
C {devices/gnd.sym} -300 -70 0 0 {name=l3 lab=GND}
C {devices/vsource.sym} -180 -100 0 0 {name=Vtune value="dc 'vtune'"}
C {devices/gnd.sym} -180 -70 0 0 {name=l4 lab=GND}
C {devices/lab_pin.sym} -180 -150 0 1 {name=l5 lab=vtune}
C {sch/vco.sym} 240 -10 0 0 {name=X1}
C {devices/lab_pin.sym} 100 -70 0 0 {name=l6 lab=vdd}
C {devices/lab_pin.sym} 100 -50 0 0 {name=l7 lab=GND}
C {devices/lab_pin.sym} 100 50 0 0 {name=l8 lab=vtune}
C {isource.sym} 20 -130 0 0 {name=I0 value='ibias'}
C {devices/lab_pin.sym} 240 120 0 0 {name=l1 lab=GND}
C {vdd.sym} -300 -150 0 0 {name=l10 lab=vdd}
C {vdd.sym} 20 -180 0 0 {name=l2 lab=vdd}
C {devices/lab_pin.sym} 360 -50 0 0 {name=l20 lab=ip}
C {devices/lab_pin.sym} 360 -30 0 0 {name=l21 lab=in}
C {devices/lab_pin.sym} 360 10 0 0 {name=l22 lab=qp}
C {devices/lab_pin.sym} 360 30 0 0 {name=l23 lab=qn}
C {devices/vsource.sym} 500 -30 0 0 {name=Vtest value="dc 0 ac 1 0"}
C {devices/lab_pin.sym} 500 -60 0 0 {name=l24 lab=ip}
C {devices/lab_pin.sym} 500 0 0 0 {name=l25 lab=in}
C {devices/code.sym} 300 -300 0 0 {name=stimuli
only_toplevel=false
value="
.include 'models_dir'/design.spice
.lib 'models_dir'/sm141064.spice 'mos_corner'
.lib 'models_dir'/sm141064.spice moscap_'mos_corner'
.option TEMP='temperature'
.option warn=1
.option rshunt=1e12
.control
save all
ac dec 100 1meg 20g
let y11 = -i(vtest) / (v(ip) - v(in))
let y11_re = real(y11)
let y11_im = imag(y11)
set wr_singlescale
wrdata 'simpath'/'filename'_'N'.data y11_re y11_im
quit
.endc
"}
