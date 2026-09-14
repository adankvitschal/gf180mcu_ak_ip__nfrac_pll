v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N -120 110 -120 150 {
lab=#net1}
N 120 110 120 150 {
lab=#net2}
N -120 290 -120 310 {
lab=cm0}
N 120 290 120 310 {
lab=cm0}
N -70 440 -40 440 {
lab=nbias1}
N -190 -40 -160 -40 {
lab=I_n}
N 0 470 0 500 {
lab=vss}
N 0 310 0 330 {
lab=cm0}
N -120 310 120 310 {
lab=cm0}
N -150 -170 -120 -170 {
lab=Q_p}
N 120 -170 150 -170 {
lab=Q_n}
N 160 -40 190 -40 {
lab=I_p}
N -80 180 -40 180 {
lab=Q_n}
N 60 -90 120 -90 {
lab=Q_n}
N 40 180 80 180 {
lab=Q_p}
N -120 -90 -60 -90 {
lab=Q_p}
N -120 -170 -80 -170 {
lab=Q_p}
N 80 -170 120 -170 {
lab=Q_n}
N 0 390 0 410 {
lab=#net3}
N -120 210 -120 230 {
lab=#net4}
N 120 210 120 230 {
lab=#net5}
N 120 -190 120 -70 {
lab=Q_n}
N -120 -190 -120 -70 {
lab=Q_p}
N 0 -290 0 -270 {
lab=SUB}
N 0 -380 0 -350 {
lab=vdd}
N -120 -330 -60 -330 {
lab=#net6}
N 60 -330 120 -330 {
lab=#net7}
N 120 -330 120 -250 {
lab=#net7}
N -120 -330 -120 -250 {
lab=#net6}
N -20 -170 20 -170 {
lab=vtune}
N 0 -190 0 -170 {
lab=vtune}
N -460 -40 -380 -40 {lab=SUB}
N 120 -10 120 50 {lab=m4source}
N -120 -10 -120 50 {lab=m3source}
N -160 80 80 80 {lab=nbias2}
N -200 80 -160 80 {lab=nbias2}
N -60 -90 40 180 {lab=Q_p}
N -40 180 60 -90 {lab=Q_n}
C {sch/inductor.sym} 0 -330 2 0 {name=XL1}
C {devices/iopin.sym} -460 -40 0 1 {name=p2 lab=SUB}
C {devices/iopin.sym} 0 -380 0 0 {name=p9 lab=vdd}
C {devices/iopin.sym} 0 500 0 0 {name=p10 lab=vss}
C {devices/ipin.sym} -190 -40 0 0 {name=p11 lab=I_n}
C {devices/ipin.sym} -70 440 0 0 {name=p12 lab=nbias1}
C {devices/opin.sym} -150 -170 0 1 {name=p13 lab=Q_p}
C {devices/opin.sym} 150 -170 0 0 {name=p14 lab=Q_n}
C {devices/ipin.sym} 190 -40 0 1 {name=p15 lab=I_p}
C {devices/ipin.sym} 0 -190 3 1 {name=p16 lab=vtune}
C {devices/lab_pin.sym} -120 310 0 0 {name=l30 sig_type=std_logic lab=cm0}
C {devices/lab_pin.sym} -120 10 0 0 {name=l31 sig_type=std_logic lab=m3source}
C {devices/lab_pin.sym} 120 10 0 1 {name=l32 sig_type=std_logic lab=m4source}
C {devices/lab_pin.sym} 0 -270 0 0 {name=l33 sig_type=std_logic lab=SUB}
C {symbols/nfet3_03v3.sym} -20 440 0 0 {name=M5
L='m5_length'
W='m5_width'
body=SUB
nf='m5_fingers'
m='m5_mult'
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X}
C {ammeter.sym} 0 360 0 0 {name=Vmeas1 savecurrent=true spice_ignore=0}
C {ammeter.sym} -120 260 0 0 {name=Vmeas2a savecurrent=true spice_ignore=0}
C {ammeter.sym} 120 260 0 0 {name=Vmeas2b savecurrent=true spice_ignore=0}
C {ammeter.sym} -120 -220 0 0 {name=Vmeas3a savecurrent=true spice_ignore=0}
C {ammeter.sym} 120 -220 0 0 {name=Vmeas3b savecurrent=true spice_ignore=0}
C {symbols/nfet3_03v3.sym} -100 180 0 1 {name=M1
L='m1m2_length'
W='m1m2_width'
body=SUB
nf='m1m2_fingers'
m='m1m2_mult'
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X}
C {symbols/nfet3_03v3.sym} 100 180 0 0 {name=M2
L='m1m2_length'
W='m1m2_width'
body=SUB
nf='m1m2_fingers'
m='m1m2_mult'
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X}
C {symbols/nfet3_03v3.sym} -140 -40 0 0 {name=M3
L='m3m4_length'
W='m3m4_width'
body=SUB
nf='m3m4_fingers'
m='m3m4_mult'
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X}
C {symbols/nfet3_03v3.sym} 140 -40 0 1 {name=M4
L='m3m4_length'
W='m3m4_width'
body=SUB
nf='m3m4_fingers'
m='m3m4_mult'
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X}
C {devices/lab_pin.sym} -380 -40 0 1 {name=l1 sig_type=std_logic lab=SUB}
C {symbols/cap_pmos_03v3.sym} 50 -170 1 0 {name=C1
W='capvar_width'
L='capvar_length'
m='capvar_mult'
model=cap_pmos_03v3
spiceprefix=X}
C {symbols/cap_pmos_03v3.sym} -50 -170 3 1 {name=C3
W='capvar_width'
L='capvar_length'
m='capvar_mult'
model=cap_pmos_03v3
spiceprefix=X}
C {symbols/nfet3_03v3.sym} -140 80 0 0 {name=M6
L='m6m7_length'
W='m6m7_width'
body=SUB
nf='m6m7_fingers'
m='m6m7_mult'
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X}
C {symbols/nfet3_03v3.sym} 100 80 0 0 {name=M7
L='m6m7_length'
W='m6m7_width'
body=SUB
nf='m6m7_fingers'
m='m6m7_mult'
ad="'int((nf+1)/2) * W/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (W/nf + 0.18u)'"
as="'int((nf+2)/2) * W/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (W/nf + 0.18u)'"
nrd="'0.18u / W'" nrs="'0.18u / W'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X}
C {devices/ipin.sym} -200 80 0 0 {name=p1 lab=nbias2}
