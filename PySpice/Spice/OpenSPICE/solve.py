#!/usr/bin/env python3

from abc import ABC, abstractmethod
from scipy.optimize import root
from functools import partial

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
        # t = 0.00
        return [[0.00] + root(y, [1.00] * len(self.eqns)).x]

class TransientSolverStrategy(SolverStrategy):
    def __init__(self, eqns, ctrl):
        self.eqns = eqns
        self.ctrl = ctrl
    def solve_eqns(self):
        # https://bugs.python.org/issue4831
        ldict = locals()
        s = "y = lambda x , x_prev , t , dt : [" + ",".join(self.eqns) + "]"
        exec(s, globals(), ldict)
        y = ldict['y']
        soln = []
        seed = [0.00] * len(self.eqns)
        t = float(self.ctrl["tstart"])
        dt = float(self.ctrl["tstep"])
        tstop = float(self.ctrl["tstop"])
        while t < tstop:
            _y = lambda x : partial(y, x_prev=seed, t=t, dt=dt)(x)
            seed = [t] + root(_y, [1.00] * len(self.eqns)).x
            soln.append(seed)
            t += dt
        return soln

if __name__ == "__main__":
    import netlist
    import eqnstr
    with open("op_pt_divider.cir", "r") as f:
        txt = f.read()
        n = netlist.parse(txt)
        eqn = eqnstr.gen_eqns_top(n)
        strat = OpPtSolverStrategy(eqn)
        print(strat.solve_eqns())
    with open("tran.cir", "r") as f:
        txt = f.read()
        n = netlist.parse(txt)
        eqn = eqnstr.gen_eqns_top(n)
        # TODO need to support multiple test types?
        strat = TransientSolverStrategy(eqn, n["ctrl"][0])
        print(strat.solve_eqns())
