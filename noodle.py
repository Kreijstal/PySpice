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
            if int(l[1]) not in nodes:
                nodes.append(int(l[1]))
            if int(l[2]) not in nodes:
                nodes.append(int(l[2]))
    nodes.sort()
    # Don't allow user to skip node numbers
    for i in range(len(nodes)-1):
        assert nodes[i+1] - nodes[i] == 1
    # Don't allow user to start past node 1
    assert nodes[0] == 0
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
    fn_str = "({}) - resistance(x[{}], x[{}], x[{}])".format(ptree_node[3], ptree_node[1], ptree_node[2], num_nodes + line_idx)
    return lambda x : (eval(ptree_node[3])) - resistance(x[int(ptree_node[1])], x[int(ptree_node[2])], x[num_nodes + line_idx])

def gen_vsrc_eqn(ptree_node, line_idx):
    fn_str = "({}) - (x[{}] - x[{}])".format(ptree_node[3], ptree_node[1], ptree_node[2])
    return lambda x : (eval(ptree_node[3])) - (x[int(ptree_node[1])] - x[int(ptree_node[2])])

def gen_isrc_eqn(ptree_node, line_idx):
    fn_str = "({}) - x[{}]".format(ptree_node[3], num_nodes + line_idx)
    return lambda x : (eval(ptree_node[3])) - x[num_nodes + line_idx]

def top_lambda(x):
    y_array = []
    global num_nodes, line_idx, lambda_array
    for _l in lambda_array:
        y_array.append(_l(x))
    if len(y_array) < num_nodes + line_idx:
        y_array += [0.0] * (num_nodes + line_idx - len(y_array))
    return y_array

def solve(top_lambda):
    global num_nodes, line_idx
    x = scipy.optimize.root(top_lambda, numpy.ones(num_nodes + line_idx)).x
    for i in range(1, num_nodes):
        x[i] -= x[0]
    x[0] = 0.0
    return x

def fmt_soln(x):
    global num_nodes, line_idx
    for n in range(num_nodes):
        print("V{} = {} [V]".format(n, x[n]))
    for l in range(line_idx):
        print("I{} = {} [A]".format(l, x[num_nodes + l]))

if __name__ == "__main__":
    parser = ParserPython(root)
    with open(sys.argv[1], "r") as f:
        parse_tree = parser.parse(f.read())
        nodes = get_nodes(parse_tree)
        ind_v_srcs = get_ind_srcs(parse_tree)
        ind_i_srcs = get_ind_srcs(parse_tree, voltage = False)
        global num_vsrcs, num_isrcs, num_nodes, line_idx
        num_vsrcs = len(ind_v_srcs)
        num_isrcs = len(ind_i_srcs)
        num_nodes = len(nodes)
        lc_filter(parse_tree)
        line_idx = 0
        global lambda_array
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
        fmt_soln(solve(top_lambda))
