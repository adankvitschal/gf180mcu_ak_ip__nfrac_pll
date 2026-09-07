v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* "placeholder_rlc" topology of the "inductor" block: a fixed RLC-pi
* equivalent, carried over verbatim from opensubghz/xschem/vco_transfer_tb.sch's
* own sky130_fd_pr__ind_05_125 (2.895nH per half, center-tapped). NOT a real
* GF180MCU inductor model -- pending rnxrbb's own characterization work.
*
* Split out as its own block (rather than an inline code.sym inside
* half_qvco_cell.sch, where it lived before) for two reasons: (1) a
* .subckt defined inside one xschem sheet and instantiated from a
* DIFFERENT, deeper-nested sheet hit a real SPICE local-scoping problem
* (confirmed live: "unknown subckt" once the definition and the XL1 call
* ended up in different hierarchy levels) -- putting the RLC elements
* directly in THIS block's own body sidesteps that entirely, no nested
* .subckt needed; (2) once rnxrbb has a real characterized/EM-extracted
* model, it becomes a NEW topology here (e.g. "characterized_v1") sharing
* the same a/b/ct/sub interface -- swap by pointing sch/inductor.sym's
* consumers at that topology instead of this placeholder, without
* touching half_qvco_cell.sch at all.
C {devices/iopin.sym} -300 -100 0 0 {name=p1 lab=a}
C {devices/iopin.sym} -300 -50 0 0 {name=p2 lab=b}
C {devices/iopin.sym} -300 0 0 0 {name=p3 lab=ct}
C {devices/iopin.sym} -300 50 0 0 {name=p4 lab=sub}
C {devices/code.sym} 0 -200 0 0 {name=rlc_pi
only_toplevel=false
value="
R31 net27 b r=1e-2
R26 a net23 r=1e-2
C24 net35 net27 c=103.1e-15
C25 net23 net37 c=357e-15
C1 net27 net31 c=357e-15
R3 sub net31 r=3.67e3
R2 net41 net27 r=1.7645
R13 net23 net35 r=9.312
R10 sub net37 r=3.67e3
R9 net23 net39 r=1.7645
L1 net39 ct l=2.895e-9
L2 ct net41 l=2.895e-9
"}
