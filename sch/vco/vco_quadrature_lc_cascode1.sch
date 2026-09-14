v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
L 4 -520 -240 -520 240 {}
L 4 -520 240 720 240 {}
L 4 720 -220 720 240 {}
L 4 -540 -220 720 -220 {}
N 600 -30 600 180 {lab=Q_p}
N -180 180 600 180 {lab=Q_p}
N -180 -30 -180 180 {lab=Q_p}
N 600 -30 650 -30 {lab=Q_p}
N 590 30 590 170 {lab=#net1}
N -170 170 590 170 {lab=#net1}
N -170 30 -170 170 {lab=#net1}
N 200 -80 200 -30 {lab=I_p}
N 200 30 200 80 {lab=I_n}
N -420 80 -340 80 {lab=nbias1}
N -340 80 -340 130 {lab=nbias1}
N -380 130 -340 130 {lab=nbias1}
N -420 160 -420 180 {lab=vss}
N -340 130 -320 130 {lab=nbias1}
N -540 -100 -480 -100 {lab=vtune}
N -540 -140 -480 -140 {lab=vdd}
N -540 -120 -480 -120 {lab=vss}
N 40 130 40 220 {lab=SUB}
N 40 220 440 220 {lab=SUB}
N 440 130 440 220 {lab=SUB}
N 220 280 240 280 {lab=SUB}
N 240 220 240 280 {lab=SUB}
N -420 -40 -420 0 {lab=nbias2}
N -420 60 -420 110 {lab=nbias1}
N 120 -30 280 -30 {lab=I_p}
N 120 30 280 30 {lab=I_n}
N 520 -30 600 -30 {lab=Q_p}
N 520 30 590 30 {lab=#net1}
N -180 -30 -120 -30 {lab=Q_p}
N -170 30 -120 30 {lab=#net1}
N -380 30 -340 30 {lab=nbias2}
N -340 -40 -340 30 {lab=nbias2}
N -420 -40 -340 -40 {lab=nbias2}
N -340 30 -320 30 {lab=nbias2}
N -450 -40 -420 -40 {lab=nbias2}
N -540 -40 -510 -40 {lab=ibias}
C {devices/lab_pin.sym} -40 -160 1 0 {name=l1 lab=vdd}
C {devices/lab_pin.sym} -10 -160 1 0 {name=l2 lab=vss}
C {devices/lab_pin.sym} 20 -160 1 0 {name=l3 lab=nbias1}
C {devices/lab_pin.sym} -480 -100 2 0 {name=l8 lab=vtune}
C {devices/lab_pin.sym} 380 130 0 0 {name=l16 lab=vtune}
C {devices/iopin.sym} -540 -140 0 1 {name=p1 lab=vdd}
C {devices/iopin.sym} -540 -120 0 1 {name=p2 lab=vss}
C {devices/ipin.sym} -540 -100 0 0 {name=p3 lab=vtune}
C {devices/opin.sym} 200 -80 0 0 {name=p4 lab=I_p}
C {devices/opin.sym} 200 80 0 0 {name=p5 lab=I_n}
C {devices/opin.sym} 650 -30 0 0 {name=p6 lab=Q_p}
C {devices/opin.sym} 650 30 0 0 {name=p7 lab=Q_n}
C {symbols/nfet3_03v3.sym} -400 130 0 1 {name=M1
L='nbias1_length'
W='nbias1_width'
body=SUB
nf='m1_fingers'
m=1
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 360 -160 1 0 {name=l9 lab=vdd}
C {devices/lab_pin.sym} 390 -160 1 0 {name=l10 lab=vss}
C {devices/lab_pin.sym} -420 180 0 1 {name=l4 lab=vss}
C {devices/lab_pin.sym} -480 -140 2 0 {name=l5 lab=vdd}
C {devices/lab_pin.sym} -480 -120 2 0 {name=l6 lab=vss}
C {devices/lab_pin.sym} 50 -160 1 0 {name=l7 lab=nbias2}
C {devices/ipin.sym} -540 -40 0 0 {name=p8 lab=ibias}
C {devices/lab_pin.sym} 420 -160 1 0 {name=l11 lab=nbias1}
C {devices/lab_pin.sym} -20 130 0 0 {name=l12 lab=vtune}
C {devices/iopin.sym} 220 280 0 1 {name=p9 lab=SUB}
C {symbols/nfet3_03v3.sym} -400 30 0 1 {name=M2
L='nbias2_length_matched'
W='nbias2_width'
body=SUB
nf='m2_fingers'
m=1
model=nfet_03v3
spiceprefix=X
}
C {sch/vco/half_qvco_cascode_pair.sym} 0 0 0 0 {name=X1
m1m2_width='m1m2_width'
m1m2_length='m1m2_length'
m1m2_fingers='m1m2_fingers'
m1m2_mult='m1m2_mult'
m3m4_width='m3m4_width'
m3m4_length='m3m4_length'
m3m4_fingers='m3m4_fingers'
m3m4_mult='m3m4_mult'
m5_width='m5_width_matched'
m5_length='m5_length_matched'
m5_fingers='m5_fingers'
m5_mult='m5_mult'
m6m7_width='m6m7_width'
m6m7_length='m6m7_length'
m6m7_fingers='m6m7_fingers'
m6m7_mult='m6m7_mult'
capvar_width='capvar_width'
capvar_length='capvar_length'
capvar_mult='capvar_mult'
}
C {sch/vco/half_qvco_cascode_pair.sym} 400 0 0 0 {name=X2
m1m2_width='m1m2_width'
m1m2_length='m1m2_length'
m1m2_fingers='m1m2_fingers'
m1m2_mult='m1m2_mult'
m3m4_width='m3m4_width'
m3m4_length='m3m4_length'
m3m4_fingers='m3m4_fingers'
m3m4_mult='m3m4_mult'
m5_width='m5_width_matched'
m5_length='m5_length_matched'
m5_fingers='m5_fingers'
m5_mult='m5_mult'
m6m7_width='m6m7_width'
m6m7_length='m6m7_length'
m6m7_fingers='m6m7_fingers'
m6m7_mult='m6m7_mult'
capvar_width='capvar_width'
capvar_length='capvar_length'
capvar_mult='capvar_mult'
}
C {devices/lab_pin.sym} 450 -160 1 0 {name=l13 lab=nbias2}
C {devices/lab_pin.sym} -320 130 2 0 {name=l14 lab=nbias1}
C {devices/lab_pin.sym} -320 30 2 0 {name=l15 lab=nbias2}
C {ammeter.sym} -480 -40 3 0 {name=Vmeas_bias savecurrent=true spice_ignore=0}
