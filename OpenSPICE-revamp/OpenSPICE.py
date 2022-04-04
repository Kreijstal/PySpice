#!/usr/bin/env python3
import netlist
import eqnstr
import sys
import solve
import genout

def run(input_fname, output_fname):
    with open(input_fname, "r"):
        file_txt = f.read()
    ptree = netlist.parse(file_txt)
    eqns = eqnstr.gen_eqns_top(ptree)
    # TODO Support multiple test types?
    # TODO Wrap this logic in a context object
    if n["ctrl"][0]["test_type"] == "tran":
        strat = solve.TransientSolverStrategy(eqns, n["ctrl"][0])
    else:
        assert n["ctrl"][0]["test_type"] == "op_pt"
        strat = solve.OpPtSolverStrategy(eqns)
    soln = strat.solve_eqns()
    genout.gen_out_txt(output_fname, n["title"], n["ctrl"][0]["test_type"], soln, n["nodes"])

if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
