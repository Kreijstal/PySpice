#!/usr/bin/env python3

from abc import ABC, abstractmethod
from scipy.optimize import root

#################################################################

# Top-Level Classes for Strategy Pattern #

class SolverStrategy(ABC):
    @abstractmethod
    def solve_eqns(self):
        pass

class OpPtSolverStrategy(SolverStrategy):
    def __init__(self, eqns):
        self.eqns = eqns
    def solve_eqns(self):
        # https://bugs.python.org/issue4831
        ldict = locals()
        s = "y = lambda x : [" + ",".join(self.eqns) + "]"
        exec(s, globals(), ldict)
        y = ldict['y']
        return root(y, [1.00] * len(self.eqns)).x

if __name__ == "__main__":
    import netlist
    import eqnstr
    with open("op_pt_divider.cir", "r") as f:
        txt = f.read()
        n = netlist.parse(txt)
        eqn = eqnstr.gen_eqns_top(n)
        strat = OpPtSolverStrategy(eqn)
        print(strat.solve_eqns())
