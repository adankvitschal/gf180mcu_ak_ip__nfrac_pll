v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
N -120 -10 -120 30 {
lab=m3source}
N 120 -10 120 30 {
lab=m4source}
N -120 170 -120 190 {
lab=cm0}
N 120 170 120 190 {
lab=cm0}
N -70 320 -40 320 {
lab=nbias1}
N -190 -40 -160 -40 {
lab=I_n}
N 0 350 0 380 {
lab=vss}
N 0 190 0 210 {
lab=cm0}
N -120 190 120 190 {
lab=cm0}
N -150 -170 -120 -170 {
lab=Q_p}
N 120 -170 150 -170 {
lab=Q_n}
N 160 -40 190 -40 {
lab=I_p}
N -80 60 -40 60 {
lab=Q_n}
N -40 60 60 -90 {
lab=Q_n}
N 60 -90 120 -90 {
lab=Q_n}
N 40 60 80 60 {
lab=Q_p}
N -60 -90 40 60 {
lab=Q_p}
N -120 -90 -60 -90 {
lab=Q_p}
N -120 -170 -80 -170 {
lab=Q_p}
N 80 -170 120 -170 {
lab=Q_n}
N 0 270 0 290 {
lab=#net1}
N -120 90 -120 110 {
lab=#net2}
N 120 90 120 110 {
lab=#net3}
N 120 -190 120 -70 {
lab=Q_n}
N -120 -190 -120 -70 {
lab=Q_p}
N 0 -290 0 -270 {
lab=gnd}
N 0 -380 0 -350 {
lab=vdd}
N -120 -330 -60 -330 {
lab=#net4}
N 60 -330 120 -330 {
lab=#net5}
N 120 -330 120 -250 {
lab=#net5}
N -120 -330 -120 -250 {
lab=#net4}
N -20 -170 20 -170 {
lab=vtune}
N 0 -190 0 -170 {
lab=vtune}
N -460 -40 -380 -40 {lab=SUB}
C {symbols/cap_nmos_03v3.sym} 50 -170 3 0 {name=C1
W="'capvar_width'"
L="'capvar_length'"
m="'capvar_mult'"
model=cap_nmos_03v3
spiceprefix=X
}
C {symbols/cap_nmos_03v3.sym} -50 -170 1 0 {name=C2
W="'capvar_width'"
L="'capvar_length'"
m="'capvar_mult'"
model=cap_nmos_03v3
spiceprefix=X
}
C {sch/inductor.sym} 0 -330 2 0 {name=XL1}
C {devices/iopin.sym} -460 -40 0 1 {name=p2 lab=SUB}
C {devices/iopin.sym} 0 -380 0 0 {name=p9 lab=vdd}
C {devices/iopin.sym} 0 380 0 0 {name=p10 lab=vss}
C {devices/ipin.sym} -190 -40 0 0 {name=p11 lab=I_n}
C {devices/ipin.sym} -70 320 0 0 {name=p12 lab=nbias1}
C {devices/opin.sym} -150 -170 0 1 {name=p13 lab=Q_p}
C {devices/opin.sym} 150 -170 0 0 {name=p14 lab=Q_n}
C {devices/ipin.sym} 190 -40 0 1 {name=p15 lab=I_p}
C {devices/ipin.sym} 0 -190 3 1 {name=p16 lab=vtune}
C {devices/lab_pin.sym} -120 190 0 0 {name=l30 sig_type=std_logic lab=cm0}
C {devices/lab_pin.sym} -120 10 0 0 {name=l31 sig_type=std_logic lab=m3source}
C {devices/lab_pin.sym} 120 10 0 1 {name=l32 sig_type=std_logic lab=m4source}
C {devices/lab_pin.sym} 0 -270 0 0 {name=l33 sig_type=std_logic lab=SUB}
C {symbols/nfet3_03v3.sym} -20 320 0 0 {name=M5
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
C {ammeter.sym} 0 240 0 0 {name=Vmeas1 savecurrent=true spice_ignore=0}
C {ammeter.sym} -120 140 0 0 {name=Vmeas2a savecurrent=true spice_ignore=0}
C {ammeter.sym} 120 140 0 0 {name=Vmeas2b savecurrent=true spice_ignore=0}
C {ammeter.sym} -120 -220 0 0 {name=Vmeas3a savecurrent=true spice_ignore=0}
C {ammeter.sym} 120 -220 0 0 {name=Vmeas3b savecurrent=true spice_ignore=0}
C {symbols/nfet3_03v3.sym} -100 60 0 1 {name=M1
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
C {symbols/nfet3_03v3.sym} 100 60 0 0 {name=M2
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
