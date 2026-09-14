v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* Differential Y-param characterization of the inductor block's chosen
* topology -- matches how the QVCO's cross-coupled pair actually drives
* the tank (differentially across a/b), unlike tb_yparam.sch's one-port
* single-ended sweep (a driven, b grounded). Pin ct is tied to GND here
* instead of left floating: in balanced differential operation the center
* tap sits at the tank's virtual ground (equal and opposite swing on each
* half), same AC condition as tying it directly to ground for a
* differential-mode-only measurement. Pin sub grounded as before.
*
* Vab floats directly between vin_p/vin_n (not referenced to GND), so
* i(vab) is the differential-mode current and Ydiff = i(vab)/v(vin_p,vin_n)
* is the tank's own differential one-port admittance -- same Q = -Im/Re
* convention as tb_yparam.py, see tb_yparam_diff.py.
*
* NOTE: sch/inductor.sym is a real hierarchical xschem subcircuit -- its
* internal pin names (a/b/ct/sub) are NOT visible as v(a) etc. from this
* top-level .control block. Reference this TB's own net labels
* (vin_p/vin_n) instead, same pitfall documented in tb_yparam.sch.
N 60 -50 60 -30 {lab=vin_p}
N 140 0 140 0 {lab=vin_p}
N 260 0 260 0 {lab=vin_n}
N 200 -40 200 -40 {lab=GND}
N 200 20 200 20 {lab=GND}
C {sch/inductor.sym} 200 0 0 0 {name=X1}
C {devices/lab_pin.sym} 140 0 0 0 {name=l1 lab=vin_p}
C {devices/lab_pin.sym} 260 0 0 0 {name=l2 lab=vin_n}
C {devices/lab_pin.sym} 200 -40 0 0 {name=l3 lab=GND}
C {devices/lab_pin.sym} 200 20 0 0 {name=l6 lab=GND}
C {devices/vsource.sym} 60 0 0 0 {name=Vab value="dc 0 ac 1 0"}
C {devices/lab_pin.sym} 60 30 0 0 {name=l4 lab=vin_n}
C {devices/lab_pin.sym} 60 -50 0 1 {name=l5 lab=vin_p}
C {devices/code.sym} 300 -300 0 0 {name=stimuli
only_toplevel=false
value="
.include 'models_dir'/design.spice
.option TEMP='temperature'
.option warn=1
.control
save all
ac dec 100 1meg 20g
let ydiff = i(vab)/(v(vin_p)-v(vin_n))
let ydiff_re = real(ydiff)
let ydiff_im = imag(ydiff)
set wr_singlescale
wrdata 'simpath'/'filename'_'N'.data frequency ydiff_re ydiff_im
quit
.endc
"}
