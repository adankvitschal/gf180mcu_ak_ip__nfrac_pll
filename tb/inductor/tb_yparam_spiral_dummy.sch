v {xschem version=3.4.5 file_version=1.2}
# Placeholder file -- the yparam_spiral test has no real xschem testbench:
# the openEMS FDTD run IS the measurement (see run_one_openems() in
# run_sim.py and tb_yparam_spiral.py's own docstring). This file exists
# only so code that unconditionally reads test_cfg["testbench"] (several
# call sites in run_sim.py, including compute_definition_hash()) doesn't
# KeyError/crash on a missing file for this test. Its content is never
# actually netlisted or simulated -- run_one_openems() ignores tb_source.
