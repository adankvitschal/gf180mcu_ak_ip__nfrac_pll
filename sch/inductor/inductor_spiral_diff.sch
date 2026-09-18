v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* "spiral_diff" topology of the "inductor" block: same two-tap pi-network
* template as inductor_loop.sch/inductor_spiral.sch (a-R2-L1-ct,
* ct-L2-R1-b, per-terminal Cox-Rsub-Csub substrate branches, a third
* substrate tap at 'ct', an eddy-current/skin-proximity R-L branch in
* parallel with each of L1/L2 -- see inductor_loop.sch's own generator,
* inductor_loop_generator.py's fit_electrical_params(), for the full
* derivation of every one of those, all reused verbatim here), PLUS one
* new element this template doesn't have: a SPICE `K` mutual-coupling
* statement between L1 (arm A, ct->a) and L2 (arm B, ct->b), added
* 2026-09-18 per explicit user confirmation once inductor_spiral_diff_
* generator.py's own 3-run open/short-circuit-test methodology (see that
* module's docstring) gives a REAL measured mutual inductance between the
* two arms -- unlike 'loop'/'spiral', whose own single continuous winding
* has no second, magnetically distinct arm to couple to, 'spiral_diff' is
* a genuine Y-branch of two separate wound arms sharing node 'ct', so a
* real mutual-coupling term is physically meaningful here in a way it
* isn't for those topologies.
*
* 'k_coupling' (dimensionless, [-1, 1], SPICE K/L1/L2 convention) is a new
* derived_parameters.generator entry, fixed at 0.0 (no coupling assumed)
* on the fast/placeholder materialize path (em_result=None -- see
* inductor_spiral_diff_generator.py's fit_electrical_params()) and
* overridden with a real fitted value only after running the 3-run EM
* methodology through tools/gf180mcu_spiral_diff_mutual_fit.py.
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
N 280 110 280 120 {lab=#net2}
N 200 110 280 110 {lab=#net2}
N 280 180 280 200 {lab=sub}
N -200 -80 -200 -20 {lab=a}
N -200 -80 -120 -80 {lab=a}
N -60 -80 -0 -80 {lab=ct}
N 0 -80 -0 -20 {lab=ct}
N 0 -80 60 -80 {lab=ct}
N 120 -80 200 -80 {lab=b}
N 200 -80 200 -20 {lab=b}
N 0 -120 0 -80 {lab=ct}
N 0 -20 0 40 {lab=ct}
N 0 100 0 120 {lab=#net5}
N 0 110 80 110 {lab=#net5}
N 80 110 80 120 {lab=#net5}
N 0 180 0 200 {lab=sub}
N 80 180 80 200 {lab=sub}
N 200 200 280 200 {lab=sub}
N -90 -20 -90 -140 {lab=#net4}
N -90 -140 -125 -140 {lab=#net4}
N -15 -20 -15 -140 {lab=ct}
N -15 -140 -5 -140 {lab=ct}
N 15 -20 15 -140 {lab=ct}
N 15 -140 5 -140 {lab=ct}
N 90 -20 90 -140 {lab=#net1}
N 90 -140 125 -140 {lab=#net1}
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
C {res.sym} 280 150 2 1 {name=R4
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
C {capa-2.sym} 0 70 0 0 {name=C7
m=1
value='cox_ct'
footprint=1206
device=polarized_capacitor}
C {capa-2.sym} 0 150 0 0 {name=C8
m=1
value='csub_ct'
footprint=1206
device=polarized_capacitor}
C {res.sym} 80 150 2 1 {name=R5
value='rsub_ct'
footprint=1206
device=resistor
m=1}
C {res.sym} -95 -140 1 0 {name=Rp_eddy1
value='rp_eddy'
footprint=1206
device=resistor
m=1}
C {ind.sym} -35 -140 1 0 {name=Lp_eddy1
m=1
value='lp_eddy'
footprint=1206
device=inductor}
C {res.sym} 35 -140 1 0 {name=Rp_eddy2
value='rp_eddy'
footprint=1206
device=resistor
m=1}
C {ind.sym} 95 -140 1 0 {name=Lp_eddy2
m=1
value='lp_eddy'
footprint=1206
device=inductor}
C {devices/code.sym} 0 -260 0 0 {name=k_stmt
only_toplevel=false
value="
K1 L1 L2 'k_coupling'
"}
