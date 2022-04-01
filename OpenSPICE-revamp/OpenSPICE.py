#!/usr/bin/env python3
import netlist
import eqnstr
import sys

if __name__ == "__main__":
    with open(sys.argv[1], "r") as f:
        file_txt = f.read()
        ptree = netlist.parse(file_txt)
        eqns = eqnstr.gen_eqns_top(ptree)
        print(eqns)
