#!/usr/bin/env python3

from arpeggio import ZeroOrMore, EOF, ParserPython
from arpeggio import RegExMatch
import numpy
import sys
import scipy.optimize

# https://pypi.org/project/Arpeggio/1.0/

### Parsing Functions ###

def root():
    return ZeroOrMore(element), EOF

# TODO: check
def element():
    return el, node, node, val, RegExMatch(r';')

def el():
    return RegExMatch(r'(R\d+)|(V\d+)|(L\d+)|(C\d+)')

# Only # names
def node():
    return RegExMatch(r'\d+')

# TODO: check
def val():
    return RegExMatch(r'\d*\.\d*|\d+')

### Matrix Construction Functions ###

def get_nodes(ptree):
    nodes = []
    for l in ptree:
        if str(l) != "":
            l = str(l).replace("|", "").split()
            if int(l[1]) not in nodes and int(l[1]) != 0:
                nodes.append(int(l[1]))
            if int(l[2]) not in nodes and int(l[2]) != 0:
                nodes.append(int(l[2]))
    nodes.sort()
    # Don't allow user to skip node numbers
    for i in range(len(nodes)-1):
        assert nodes[i+1] - nodes[i] == 1
    # Don't allow user to start past node 1
    assert nodes[0] == 1
    return nodes

def get_ind_srcs(ptree, voltage = True):
    ind_srcs = []
    for l in ptree:
        if str(l) != "":
            l = str(l).replace("|", "").split()
            if (l[0][0] == "V" and voltage) or (l[0][0] == "I" and not voltage):
                ind_srcs.append(int(l[0][1:]))
    ind_srcs.sort()
    for i in range(len(ind_srcs)-1):
        assert ind_srcs[i+1] - ind_srcs[i] == 1
    print("ind_srcs = {}, len(ind_srcs) = {}".format(ind_srcs, len(ind_srcs)))
    if len(ind_srcs) != 0:
        assert ind_srcs[0] == 1
    return ind_srcs

def lc_filter(ptree):
    # Inductors are considered independent sources of voltage 0
    # Capacitors are considered independent sources of current 0
    for l in ptree:
        if str(l) != "":
            if str(l).replace("|", "").split()[0][0] == "L":
                global num_vsrcs
                num_vsrcs += 1
                l[0] = "V{}".format(num_vsrcs)
                l[3] = "0"
            elif str(l).replace("|", "").split()[0][0] == "C":
                global num_isrcs
                num_isrcs += 1
                l[0] = "I{}".format(num_isrcs)
                l[3] = "0"

# Calculating functions

def resistance(vnode_A, vnode_B, ibranch):
    return (vnode_A - vnode_B) / ibranch

def gen_passive_eqn(ptree_node, line_idx):
    return lambda x : (eval(_r[3])) - resistance(x[int(_r[1])], x[int(_r[2])], x[num_nodes + line_idx])

def gen_vsrc_eqn(ptree_node, line_idx):
    return lambda x : (eval(_r[3])) - (x[int(_r[1])] - x[int(_r[2])])

def gen_isrc_eqn(ptree_node, line_idx):
    return lambda x : (eval(_r[3])) - x[num_nodes + line_idx]

if __name__ == "__main__":
    parser = ParserPython(root)
    with open(sys.argv[1], "r") as f:
        parse_tree = parser.parse(f.read())
        nodes = get_nodes(parse_tree)
        ind_v_srcs = get_ind_srcs(parse_tree)
        ind_i_srcs = get_ind_srcs(parse_tree, voltage = False)
        global num_vsrcs, num_isrcs, num_nodes
        num_vsrcs = len(ind_v_srcs)
        num_isrcs = len(ind_i_srcs)
        num_nodes = len(nodes)
        lc_filter(parse_tree)
        line_idx = 0
        lambda_array = []
        for r in parse_tree:
            _r = str(r).replace("|", "").split()
            if _r != [] and _r[0][0] == "R":
                lambda_array.append(gen_passive_eqn(_r, line_idx))
            elif _r != [] and _r[0][0] == "V":
                lambda_array.append(gen_vsrc_eqn(_r, line_idx))
            elif _r != [] and _r[0][0] == "I":
                lambda_array.append(gen_isrc_eqn(_r, line_idx))
            if _r != []:
                line_idx += 1
        top_lambda = lambda x : map(lambda y : y(x), lambda_array)
        print("len(lambda_array) = {}, len(x[0]) = {} ({})".format(len(lambda_array), len(numpy.zeros(num_nodes + line_idx)), num_nodes + line_idx))
        print(scipy.optimize.root(top_lambda, numpy.zeros(num_nodes + line_idx)))
