v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
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
C {devices/vsource.sym} -300 -100 0 0 {name=Vdd value="dc 'vdd'"}
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
.lib 'models_dir'/sm141064.spice moscap
.option TEMP='temperature'
.option warn=1
.option savecurrents
.control
save all
op
print I(Vmeas_vdd)
set wr_singlescale
wrdata 'simpath'/'filename'_'N'.data -I(Vmeas_vdd)
set filetype=ascii
write 'simpath'/'filename'_'N'.raw
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
