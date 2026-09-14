v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* Note (NOT a token, avoid single-quoting bare words here --
* substitute_params()/check_unresolved() treat ANY quoted-word text as a
* substitution token, comments included): "spiral" topology of the
* "inductor" block -- a real GF180MCU octagonal spiral, characterized by
* a 3D FDTD (openEMS) run, see inductor_spiral_generator.py. Two series
* half-windings (terminal-a -- R2 -- L1 -- ct, ct -- L2 -- R1 --
* terminal-b), a center-tap coupling cap from each terminal to ct (C5/C6,
* named cs), and a substrate-coupling branch from each terminal (Cox in
* series with a parallel Rsub-and-Csub network to the sub pin) --
* C3/R3/C1 on the terminal-a side, C4/R4/C2 on the terminal-b side.
* Unlike placeholder_rlc's single code.sym text block, this is a real
* discrete-component schematic so each element renders/selects
* individually in xschem; the substitute_params() tokens are l, rs, cox,
* rsub, csub, cs, filled in from inductor_spiral_generator.py's
* fit_electrical_params() (real Cox, placeholder-quality l/rs/rsub/csub/cs
* unless a real openEMS fit has run -- see that function's own docstring).
N -200 -20 -160 -20 {lab=a}
N 80 -20 100 -20 {lab=#net1}
N 160 -20 200 -20 {lab=b}
N 200 -20 200 40 {lab=b}
N 200 100 200 120 {lab=#net2}
N -200 100 -200 120 {lab=#net3}
N -200 180 -200 200 {lab=sub}
N 200 180 200 200 {lab=sub}
N -100 -20 -80 -20 {lab=#net4}
N -20 -20 20 -20 {lab=ct}
N 200 -20 240 -20 {lab=b}
N -200 200 200 200 {lab=sub}
N -240 -20 -200 -20 {lab=a}
N -240 200 -200 200 {lab=sub}
N -200 -20 -200 40 {lab=a}
N -120 180 -120 200 {lab=sub}
N -120 110 -120 120 {lab=#net3}
N -200 110 -120 110 {lab=#net3}
N 120 110 120 120 {lab=#net2}
N 120 110 200 110 {lab=#net2}
N 120 180 120 200 {lab=sub}
N -200 -80 -200 -20 {lab=a}
N -200 -80 -120 -80 {lab=a}
N -60 -80 -0 -80 {lab=ct}
N 0 -80 -0 -20 {lab=ct}
N 0 -80 60 -80 {lab=ct}
N 120 -80 200 -80 {lab=b}
N 200 -80 200 -20 {lab=b}
N 0 -120 0 -80 {lab=ct}
C {capa-2.sym} -200 150 0 0 {name=C1
m=1
value='csub'
footprint=1206
device=polarized_capacitor}
C {capa-2.sym} 200 150 0 0 {name=C2
m=1
value='csub'
footprint=1206
device=polarized_capacitor}
C {ind.sym} -50 -20 1 0 {name=L1
m=1
value='l'
footprint=1206
device=inductor}
C {ind.sym} 50 -20 1 0 {name=L2
m=1
value='l'
footprint=1206
device=inductor}
C {res.sym} 130 -20 1 0 {name=R1
value='rs'
footprint=1206
device=resistor
m=1}
C {res.sym} -130 -20 1 0 {name=R2
value='rs'
footprint=1206
device=resistor
m=1}
C {res.sym} -120 150 2 1 {name=R3
value='rsub'
footprint=1206
device=resistor
m=1}
C {res.sym} 120 150 2 0 {name=R4
value='rsub'
footprint=1206
device=resistor
m=1}
C {iopin.sym} 0 -120 3 0 {name=p1 lab=ct}
C {iopin.sym} -240 -20 2 0 {name=p2 lab=a}
C {iopin.sym} 240 -20 0 0 {name=p3 lab=b}
C {iopin.sym} -240 200 2 0 {name=p4 lab=sub}
C {capa-2.sym} -200 70 0 0 {name=C3
m=1
value='cox'
footprint=1206
device=polarized_capacitor}
C {capa-2.sym} 200 70 0 0 {name=C4
m=1
value='cox'
footprint=1206
device=polarized_capacitor}
C {capa-2.sym} -90 -80 1 0 {name=C5
m=1
value='cs'
footprint=1206
device=polarized_capacitor}
C {capa-2.sym} 90 -80 3 1 {name=C6
m=1
value='cs'
footprint=1206
device=polarized_capacitor}
