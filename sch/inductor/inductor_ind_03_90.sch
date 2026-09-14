v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
* "ind_03_90" topology of the "inductor" block: sky130_fd_pr__ind_03_90's
* own characterized RLC-pi equivalent (760.5pH per half, center-tapped),
* pulled directly from fossi-foundation/skywater-pdk-libs-sky130_fd_pr's
* cells/ind_03/sky130_fd_pr__ind_03_90.model.spice -- for comparing against
* the ind_05_125 placeholder currently in use, NOT a GF180MCU model either.
C {devices/iopin.sym} -300 -100 0 0 {name=p1 lab=a}
C {devices/iopin.sym} -300 -50 0 0 {name=p2 lab=b}
C {devices/iopin.sym} -300 0 0 0 {name=p3 lab=ct}
C {devices/iopin.sym} -300 50 0 0 {name=p4 lab=sub}
C {devices/code.sym} 0 -200 0 0 {name=rlc_pi
only_toplevel=false
value="
R31 net27 b r=1e-2
R26 a net23 r=1e-2
C24 net35 net27 c=8.337e-15
C25 net23 net37 c=53.8e-15
C0 net27 net31 c=53.8e-15
R1 sub net31 r=21.56
R13 net23 net35 r=50.11
R10 sub net37 r=21.56
R0 net41 net27 r=1.019
R9 net23 net39 r=1.019
L0 net39 ct l=760.5e-12
L1 ct net41 l=760.5e-12
"}
