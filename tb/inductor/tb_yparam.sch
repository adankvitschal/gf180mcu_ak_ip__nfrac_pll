v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* One-port Y11 characterization of the inductor block's chosen topology:
* drive 'a' with a 1V AC source (net vin_node), ground 'b' and 'sub', leave
* 'ct' floating (it stays internally bridged to both half-windings via
* L1/L2 -- same differential path the QVCO tank actually uses, just
* single-ended-driven here for a clean Y11 measurement). See tb_yparam.py
* for Q = -Im(Y11)/Re(Y11) and SRF extraction from the resulting
* frequency/y11_re/y11_im columns.
*
* NOTE: sch/inductor.sym is a real hierarchical xschem subcircuit -- its
* internal pin names (a/b/ct/sub) are NOT visible as v(a) etc. from this
* top-level .control block. Reference this TB's own net label (vin_node)
* instead, same pitfall documented in inductor_placeholder_rlc.sch.
N 60 -50 60 -30 {lab=vin_node}
N 140 0 140 0 {lab=vin_node}
N 260 0 260 0 {lab=GND}
N 200 -40 200 -40 {lab=GND}
C {sch/inductor.sym} 200 0 0 0 {name=X1}
C {devices/lab_pin.sym} 140 0 0 0 {name=l1 lab=vin_node}
C {devices/lab_pin.sym} 260 0 0 0 {name=l2 lab=GND}
C {devices/lab_pin.sym} 200 -40 0 0 {name=l3 lab=GND}
C {devices/vsource.sym} 60 0 0 0 {name=Vin value="dc 0 ac 1 0"}
C {devices/gnd.sym} 60 30 0 0 {name=l4 lab=GND}
C {devices/lab_pin.sym} 60 -50 0 1 {name=l5 lab=vin_node}
C {devices/code.sym} 300 -300 0 0 {name=stimuli
only_toplevel=false
value="
.include 'models_dir'/design.spice
.option TEMP='temperature'
.option warn=1
.control
save all
ac dec 100 1meg 20g
let y11 = i(vin)/v(vin_node)
let y11_re = real(y11)
let y11_im = imag(y11)
set wr_singlescale
wrdata 'simpath'/'filename'_'N'.data frequency y11_re y11_im
quit
.endc
"}
