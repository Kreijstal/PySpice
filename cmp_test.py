#!/usr/bin/env python3

import time
import os

ngspice_start_t = time.time()
os.system("ngspice circuit5_trans.cir")
ngspice_end_t = time.time()

ospice_start_t = time.time()
os.system("./OpenSPICE.py circuit4_trans.cir")
ospice_end_t = time.time()

print("ngspice exec time = {} [ms]".format((ngspice_end_t - ngspice_start_t) * 1e3))
print("OpenSPICE exec time = {} [ms]".format((ospice_end_t - ospice_start_t) * 1e3))
