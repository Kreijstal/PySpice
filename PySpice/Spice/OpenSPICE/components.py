#!/usr/bin/env python3

from abc import ABC, abstractmethod
from .common import v_format, i_format, dv_format, di_format

class Component(ABC):
    @staticmethod
    @abstractmethod
    def op_pt_eqn(branch, node):
        pass
    @staticmethod
    @abstractmethod
    def trans_eqn(branch, node):
        pass

class Resistor(Component):
    @staticmethod
    def op_pt_eqn(branch, node):
        return "(({})-({}))-(({})*({}))".format(v_format(branch["node_plus"],  node),
                                                v_format(branch["node_minus"], node),
                                                i_format(branch["branch_idx"], node),
                                                         branch["value"])
    @staticmethod
    def trans_eqn(branch, node):
        return "(({})-({}))-(({})*({}))".format(v_format(branch["node_plus"],  node, trans=True),
                                                v_format(branch["node_minus"], node, trans=True),
                                                i_format(branch["branch_idx"], node, trans=True),
                                                         branch["value"])

class Capacitor:
    @staticmethod
    def op_pt_eqn(branch, node):
        return "(({})-({}))".format(i_format(_b["branch_idx"], _n), 0.00)
    @staticmethod
    def trans_eqn(branch, node):
        if "ic" in branch.keys():
            # TODO: modify to support nonzero start times
            prefix = "((({})-({}))-({})) if t == 0.00 else ".format(v_format(branch["node_plus"],  node, trans=True),
                                                                    v_format(branch["node_minus"], node, trans=True),
                                                                             branch["ic"])
        else:
            prefix = ""
        return prefix + "((({})*dt)-(({})*(({})-({}))))".format(i_format(branch["branch_idx"], node, trans=True),
                                                                         branch["value"],
                                                               dv_format(branch["node_plus"],  node),
                                                               dv_format(branch["node_minus"], node))

class Inductor:
    @staticmethod
    def op_pt_eqn(branch, node):
        return "((({})-({}))-({}))".format(v_format(branch["node_plus"],  node),
                                           v_format(branch["node_minus"], node), 0.00)
    @staticmethod
    def trans_eqn(branch, node):
        if "ic" in _b.keys():
            # TODO: modify to support nonzero start times
            prefix = "(({})-({})) if t == 0.00 else ".format(i_format(branch["branch_idx"], node, trans=True),
                                                                      branch["ic"])
        else:
            prefix = ""
        return prefix + "(((({})-({}))*dt)-(({})*(({}))))".format(v_format(branch["node_plus"],  node, trans=True),
                                                                  v_format(branch["node_minus"], node, trans=True),
                                                                           branch["value"],
                                                                 di_format(branch["branch_idx"], node))

class VSource:
    @staticmethod
    def op_pt_eqn(branch, node):
        return "((({})-({}))-({}))".format(v_format(branch["node_plus"],  node),
                                           v_format(branch["node_minus"], node),
                                                    branch["value"])
    @staticmethod
    def trans_eqn(branch, node):
        return "((({})-({}))-({}))".format(v_format(branch["node_plus"],  node, trans=True),
                                           v_format(branch["node_minus"], node, trans=True),
                                                    branch["value"])

class ISource:
    @staticmethod
    def op_pt_eqn(branch, node):
        return "(({})-({}))".format(i_format(branch["branch_idx"], node),
                                             branch["value"])
    @staticmethod
    def trans_eqn(branch, node):
        return "(({})-({}))".format(i_format(branch["branch_idx"], node, trans=True),
                                             branch["value"])
