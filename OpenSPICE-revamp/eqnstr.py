#!/usr/bin/env python3

from components import Resistor, Capacitor, Inductor, VSource, ISource
from abc import ABC, abstractmethod
from common import v_format, i_format, dv_format, di_format

#################################################################

# Top-Level Classes for Strategy Pattern #

class EqnStrStrategy(ABC):
    @abstractmethod
    def gen_eqn_from_branch(self, _b):
        pass
    def gen_eqns(self, branch_dicts):
        return [self.gen_eqn_from_branch(_b) for _b in branch_dicts] + self.gen_kcl_eqns(branch_dicts)
    def gen_kcl_eqns(self, branch_dicts):
        nodes = sorted(set().union(*[{d["node_plus"], d["node_minus"]} for d in branch_dicts]))
        assert "0" in nodes
        nodes.remove("0")
        kcl_dict = dict(zip(nodes, [[]] * len(nodes)))
        for b in branch_dicts:
            if b["node_plus"] != "0":
                kcl_dict[b["node_plus"]].append("-({})".format(i_format(b["branch_idx"])))
            if b["node_minus"] != "0":
                kcl_dict[b["node_minus"]].append("+({})".format(i_format(b["branch_idx"])))
        return ["".join(v) for v in kcl_dict.values()]

#################################################################

# Strategies #

class EqnStrOpPtStrategy(EqnStrStrategy):
    def __init__(self):
        pass
    def gen_eqn_from_branch(self, _b):
        if   _b["component"] == Resistor:
            return "(({})-({}))-(({})*({}))".format(v_format(_b["node_plus"]),
                                                    v_format(_b["node_minus"]),
                                                    i_format(_b["branch_idx"]),
                                                             _b["value"])
        elif _b["component"] == Capacitor:
            return "(({})-({}))".format(i_format(_b["branch_idx"]), 0.00)
        elif _b["component"] == Inductor:
            return "((({})-({}))-({}))".format(v_format(_b["node_plus"]),
                                               v_format(_b["node_minus"]), 0.00)
        elif _b["component"] == VSource:
            return "((({})-({}))-({}))".format(v_format(_b["node_plus"]),
                                               v_format(_b["node_minus"]),
                                                        _b["value"])
        elif _b["component"] == ISource:
            return "(({})-({}))".format(i_format(_b["branch_idx"]),
                                                 _b["value"])
        else:
            assert False

class EqnStrTransientStrategy(EqnStrStrategy):
    def __init__(self):
        pass
    def gen_eqn_from_branch(self, _b):
        if   _b["component"] == Resistor:
            return "(({})-({}))-(({})*({}))".format(v_format(_b["node_plus"]),
                                                    v_format(_b["node_minus"]),
                                                    i_format(_b["branch_idx"]),
                                                             _b["value"])
        elif _b["component"] == Capacitor:
            return "((({})*dt)-(({})*(({})-({}))))".format(i_format(_b["branch_idx"]),
                                                             _b["value"],
                                                           dv_format(_b["node_plus"]),
                                                           dv_format(_b["node_minus"]))
        elif _b["component"] == Inductor:
            return "(((({})-({}))*dt)-(({})*(({}))))".format(v_format(_b["node_plus"]),
                                                             v_format(_b["node_minus"]),
                                                                      _b["value"],
                                                             di_format(_b["branch_idx"]))
        elif _b["component"] == VSource:
            return "((({})-({}))-({}))".format(v_format(_b["node_plus"]),
                                               v_format(_b["node_minus"]),
                                                        _b["value"])
        elif _b["component"] == ISource:
            return "(({})-({}))".format(i_format(_b["branch_idx"]),
                                                 _b["value"])
        else:
            assert False

def gen_eqns_top(parse_dict):
    # TODO need to support multiple test types?
    if   parse_dict["ctrl"][0]["test_type"] == "op_pt":
        return EqnStrOpPtStrategy().gen_eqns(parse_dict["branches"])
    elif parse_dict["ctrl"][0]["test_type"] == "tran" :
        return EqnStrTransientStrategy().gen_eqns(parse_dict["branches"])
    else:
        assert False

#################################################################

if __name__ == "__main__":
    import netlist
    with open("op_pt.cir", "r") as f:
        print(gen_eqns_top(netlist.parse(f.read())))
    with open("tran.cir", "r") as f:
        print(gen_eqns_top(netlist.parse(f.read())))
