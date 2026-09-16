v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* Functional divide-by-2/3 testbench: clk is a pure sine (parametrized DC
* level/amplitude/frequency, see config.json's tests.divider.funct.conditions
* -- clk_dc/clk_amp/clk_freq), standing in for the VCO's own sinusoidal
* output driving this block directly. en is tied straight to vdd (block
* always enabled for this test -- enable/disable behavior isn't this test's
* concern). sw is a swept DC level selecting between the block's two
* modulus-control states; tb_divider_funct.py measures which ratio each
* level actually produces rather than assuming div2/div3 from the level
* alone (see the divider.etspc_d2d3 topology's own config.json description).
N -300 -150 -300 -130 {lab=vdd}
N -180 -150 -180 -130 {lab=clk}
N -60 -150 -60 -130 {lab=sw}
C {devices/vsource.sym} -300 -100 0 0 {name=Vdd value="dc 'vdd'"}
C {devices/gnd.sym} -300 -70 0 0 {name=l3 lab=GND}
C {devices/vsource.sym} -180 -100 0 0 {name=Vclk value="dc 'clk_dc' sin('clk_dc' 'clk_amp' 'clk_freq' 0 0 0)"}
C {devices/gnd.sym} -180 -70 0 0 {name=l4 lab=GND}
C {devices/vsource.sym} -60 -100 0 0 {name=Vsw value="dc 'sw'"}
C {devices/gnd.sym} -60 -70 0 0 {name=l5 lab=GND}
C {devices/lab_pin.sym} -300 -150 0 1 {name=l1 lab=vdd}
C {devices/lab_pin.sym} -180 -150 0 1 {name=l2 lab=clk}
C {devices/lab_pin.sym} -60 -150 0 1 {name=l6 lab=sw}
C {sch/divider.sym} 240 -10 0 0 {name=X1}
C {devices/lab_pin.sym} 100 -70 0 0 {name=l7 lab=vdd}
C {devices/lab_pin.sym} 100 -50 0 0 {name=l8 lab=GND}
C {devices/lab_pin.sym} 100 -30 0 0 {name=l9 lab=clk}
C {devices/lab_pin.sym} 100 -10 0 0 {name=l10 lab=vdd}
C {devices/lab_pin.sym} 100 10 0 0 {name=l11 lab=sw}
N 360 -30 400 -30 {lab=out}
N 400 -30 400 -10 {lab=out}
N 400 50 400 80 {lab=GND}
C {devices/lab_pin.sym} 360 -30 0 0 {name=l13 lab=out}
C {capa.sym} 400 20 0 0 {name=C1
m=1
value='cload'
footprint=1206
device="ceramic capacitor"}
C {devices/gnd.sym} 400 80 0 0 {name=l12 lab=GND}
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
tran 5p 200n
set wr_singlescale
wrdata 'simpath'/'filename'_'N'.data v(clk) v(out) v(vdd) vdd#branch
quit
.endc
"}
