#!/usr/bin/env python3
import numpy
import re
import scipy.optimize
import sys
import sympy

# TODO x -> dictionary mapping timestep to vector of currents and voltages
# TODO initial conditions

# Foundational functions

# Take limit of expression t -> inf
def inflim(expr, dt):
    return expr.replace('x[t+dt]', 'x').replace('x[t]', 'x')

# process netlist expressions with function f
def process_netlist_expr(lines, f, dt):
    for i in range(len(lines)):
        lines[i][3] = f(lines[i][3], dt)
        if len(lines[i]) == 5:
            lines[i][4] = f(lines[i][4], dt)
    return lines

def get_nodes(lines):
    nodes = []
    for l in lines:
        if int(l[1]) not in nodes:
            nodes.append(int(l[1]))
        if int(l[2]) not in nodes:
            nodes.append(int(l[2]))
    nodes.sort()
    for i in range(len(nodes)-1):
        assert nodes[i+1] - nodes[i] == 1
    assert nodes[0] == 0
    return nodes

def kcl_prepend(s, num_nodes, branch_idx, plus):
    return "{}x[{}]".format("+" if plus else "-", num_nodes + branch_idx - 1) + s

def get_kcl_eqns(lines):
    nodes = get_nodes(lines)
    assert nodes[0] == 0
    num_nodes = len(nodes)
    num_branches = len(lines)
    kcl = [""] * (num_nodes - 1)
    for i in range(len(lines)):
        if lines[i][1] != "0":
            kcl[int(lines[i][1])-1] = kcl_prepend(kcl[int(lines[i][1])-1], num_nodes, i, False)
        if lines[i][2] != "0":
            kcl[int(lines[i][2])-1] = kcl_prepend(kcl[int(lines[i][2])-1], num_nodes, i, True)
    return [["\"" + k + "\"" for k in kcl],num_nodes,num_branches]

def solve(fn, output_len):
    return scipy.optimize.root(fn, numpy.ones(output_len), method='broyden1').x

def fmt_soln(x, num_nodes, num_branches):
    for n in range(num_nodes - 1):
        print("V{} = {} [V]".format(n + 1, x[n]))
    for b in range(num_branches):
        print("I{} = {} [A]".format(b, x[num_nodes + b - 1]))

def make_simple(fn_str, x_len):
    for i in range(x_len - 1, -1, -1):
        exec("x_{} = sympy.symbols('x_{}')".format(i, i))
        fn_str = fn_str.replace("x[{}]".format(i), "(x_{})".format(i))
    fn_str_arr = eval(fn_str)
    for i in range(len(fn_str_arr)):
        fn_str_arr[i] = sympy.simplify(fn_str_arr[i])
    fn_str = str(fn_str_arr)
    for i in range(x_len - 1, -1, -1):
        fn_str = fn_str.replace("x_{}".format(i), "x[{}]".format(i))
    return fn_str

# Take array of expressions and initial condition expressions
# and solve op point.

# Op point
# 1) Substitute constant dt and t -> inf.
# 2) Use Broyden's to solve at a single timestep
def op_pt(netlist):
    dt = 1.0
    lines = [n.split(" ") for n in netlist.split("\n") if n != ""]
    lines = process_netlist_expr(lines, inflim, dt)
    # Note: Replace len(l) - 1 with 3 for transient nextstep function
    l_arr = [l[len(l)-1] for l in lines]
    iv_relations = l_arr
    [kcl_relations,num_nodes,num_branches] = get_kcl_eqns(lines)
    l_fn_str = "[" + ",".join([eval(s.replace('dt', str(dt))) for s in iv_relations + kcl_relations]) + "]"
    l_fn_str = make_simple(l_fn_str, len(iv_relations) + len(kcl_relations))
    l_fn = lambda x : eval(l_fn_str)
    soln = solve(l_fn, len(iv_relations) + len(kcl_relations))
    return [soln,num_nodes,num_branches]

# Transient sim
# 1) Create initial condition equations and calculate
# 2) Set x[0] to initial condition
# 3) Loop. Update t on each timestep.

if __name__ == "__main__":
    with open(sys.argv[1], "r") as txt:
        [soln,n_nodes,n_branches] = op_pt(txt.read())
        # fmt_soln(soln, n_nodes, n_branches)
