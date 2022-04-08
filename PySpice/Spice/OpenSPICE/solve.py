#!/usr/bin/env python3

from abc import ABC, abstractmethod
from scipy.optimize import root
from functools import partial

# TODO remove globals. Need a cleaner way of implementing these functions.

get_vsrc_data = None
get_isrc_data = None
send_data     = None

def set_get_vsrc(x):
    global get_vsrc_data
    get_vsrc_data = x

def set_get_isrc(x):
    global get_isrc_data
    get_isrc_data = x

def set_send_data(x):
    global send_data
    send_data = x

def get_vsrc(t):
    # TODO - support all get_vsrc_data args
    global get_vsrc_data
    voltage = [0.0]
    get_vsrc_data(voltage, t, 0, 0)
    return voltage[0]

def get_isrc(t):
    # TODO - support all get_vsrc_data args
    global get_isrc_data
    current = [0.0]
    get_isrc_data(current, t, 0, 0)
    return current[0]

#################################################################

# Top-Level Classes for Strategy Pattern #

class SolverStrategy(ABC):
    @abstractmethod
    def solve_eqns(self):
        pass

class OpPtSolverStrategy(SolverStrategy):
    def __init__(self, eqns, nodes):
        self.eqns  = eqns
        self.nodes = nodes
    def solve_eqns(self):
        # https://bugs.python.org/issue4831
        ldict = locals()
        s = "y = lambda x : [" + ",".join(self.eqns) + "]"
        exec(s, globals(), ldict)
        y = ldict['y']
        # t = 0.00
        # TODO Why does this not work?
        soln = [root(y, [1.00] * len(self.eqns)).x.tolist()]
        # TODO need more proper send_data call
        if send_data:
            send_data(dict(zip(['V({})'.format(n) for n in self.nodes] + \
                               ['i({})'.format(l) for l in range(len(self.eqns) - len(self.nodes))], soln[0])), len(soln[0]), 0)
        return soln

class TransientSolverStrategy(SolverStrategy):
    def __init__(self, eqns, ctrl, nodes):
        self.eqns  = eqns
        self.ctrl  = ctrl
        self.nodes = nodes
    def solve_eqns(self):
        # https://bugs.python.org/issue4831
        ldict = locals()
        s = "y = lambda x , x_prev , t , dt : [" + ",".join(self.eqns) + "]"
        exec(s, globals(), ldict)
        y = ldict['y']
        soln = []
        seed = []
        x_soln = [0.00] * len(self.eqns)
        t     = float(self.ctrl["tstart"])
        dt    = float(self.ctrl["tstep"])
        tstop = float(self.ctrl["tstop"])
        while t < tstop:
            _y = lambda x : partial(y, x_prev=x_soln, t=t, dt=dt)(x)
            tmp_soln = root(_y, [1.00] * len(self.eqns))
            x_soln = tmp_soln.x.tolist()
            # TODO: Replace tolerance check with value found in options
            # assert all([abs(z) < 1e-3 for z in _y(x_soln)])
            seed = [t] + x_soln
            data_dict_keys = ['time'] + ['V({})'.format(n) for n in self.nodes] + \
                                        ['i({})'.format(l) for l in range(len(self.eqns) - len(self.nodes))]
            assert len(data_dict_keys) == len(seed)
            data_dict = dict(zip(data_dict_keys, seed))
            if send_data:
                send_data(data_dict, len(seed), 0)
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
    with open("tran.cir", "r") as f:
        txt = f.read()
        n = netlist.parse(txt)
        eqn = eqnstr.gen_eqns_top(n)
        # TODO need to support multiple test types?
        strat = TransientSolverStrategy(eqn, n["ctrl"][0])
