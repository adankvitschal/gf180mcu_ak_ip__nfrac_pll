v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* Ported from opensubghz/xschem/bias.sch (SKY130 nfet3_01v8) to GF180MCU
* nfet_03v3. Simple diode-connected NMOS self-bias fed by a 100uA
* reference current source -- placeholder, same as the original.
C {symbols/nfet_03v3.sym} 0 100 0 0 {name=M1
L=0.28u
W="'bias_width'"
nf=1
m=1
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 20 70 0 0 {name=l1 lab=bias}
C {devices/lab_pin.sym} -20 100 0 0 {name=l2 lab=bias}
C {devices/lab_pin.sym} 20 130 0 0 {name=l3 lab=GND}
C {devices/lab_pin.sym} 20 100 0 0 {name=l4 lab=GND}
C {devices/isource.sym} -200 30 0 0 {name=I0 value=100u}
C {devices/lab_pin.sym} -200 0 0 0 {name=l5 lab=bias}
C {devices/lab_pin.sym} -200 60 0 0 {name=l6 lab=vdd}
C {devices/iopin.sym} -300 -100 0 0 {name=p1 lab=vdd}
C {devices/iopin.sym} -300 -50 0 0 {name=p2 lab=GND}
C {devices/opin.sym} -300 0 0 0 {name=p3 lab=bias}
