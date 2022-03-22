#!/usr/bin/env python3
from math import sin, pi
from scipy.optimize import root
from sys import argv

END_T = 30.00
DT = 0.01

# TODO x -> dictionary mapping timestep to vector of currents and voltages
# TODO initial conditions

# Foundational functions

# Take limit of expression t -> inf
def inflim(expr, seed, dt, mid_trans, timestep):
    if not mid_trans:
        expr = expr.replace('x[t+dt]', 'x').replace('x[t]', 'x')
    else:
        for s in range(len(seed)):
            expr = expr.replace('x[t][%d]' % s, str(seed[s]))
        expr = expr.replace('x[t+dt]', 'x')
    return expr.replace('dt', str(dt)).replace('t', str(timestep))

# process netlist expressions with function f
def process_netlist_expr(lines, f, dt, seed=[], mid_trans=False, timestep=0.0):
    for i in range(len(lines)):
        lines[i][3] = f(lines[i][3], seed, dt, mid_trans, timestep)
        if len(lines[i]) == 5 and not mid_trans:
            lines[i][4] = f(lines[i][4], seed, dt, mid_trans, timestep)
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
    return [kcl,num_nodes,num_branches]

def solve(fn, output_len):
    return root(fn, [1.00] * (output_len)).x

def fmt_soln(x, num_nodes, num_branches):
    for n in range(num_nodes - 1):
        print("V{} = {} [V]".format(n + 1, x[n]))
    for b in range(num_branches):
        print("I{} = {} [A]".format(b, x[num_nodes + b - 1]))

# Take array of expressions and initial condition expressions
# and solve op point.

# Op point
# 1) Substitute constant dt and t -> inf.
# 2) Use Broyden's to solve at a single timestep
def op_pt(netlist, mid_trans=False, seed=[], dt=1.0, timestep=0.0):
    lines = [n.split(" ") for n in netlist.split("\n") if n != ""]
    lines = process_netlist_expr(lines, inflim, dt, seed, mid_trans, timestep)
    # Note: Replace len(l) - 1 with 3 for transient nextstep function
    if mid_trans:
        iv_relations = [l[3] for l in lines]
    else:
        iv_relations = [l[len(l)-1] for l in lines]
    [kcl_relations,num_nodes,num_branches] = get_kcl_eqns(lines)
    l_fn_str = "lambda x : [" + ",".join(iv_relations + kcl_relations) + "]"
    l_fn = eval(l_fn_str)
    soln = solve(l_fn, len(iv_relations) + len(kcl_relations))
    return [soln,num_nodes,num_branches]

# Transient sim
# 1) Create initial condition equations and calculate
# 2) Set x[0] to initial condition
# 3) Loop. Update t on each timestep.
def transient(netlist):
    trans_soln = []
    for i in range(int(END_T / DT)):
        if i == 0:
            soln = op_pt(netlist)
        else:
            soln = op_pt(netlist, mid_trans=True, seed=trans_soln[len(trans_soln)-1], dt=DT, timestep=DT*i)
        trans_soln.append(soln[0])
    return trans_soln

if __name__ == "__main__":
    with open(argv[1], "r") as txt:
        # [soln,n_nodes,n_branches] = op_pt(txt.read())
        x = transient(txt.read())
        print([_x[1] for _x in x])
        # from numpy import linspace
        # import matplotlib.pyplot as plt
        # t = linspace(0.00, END_T, int(END_T / DT))
        # plt.plot(t, [_x[1] for _x in x])
        # plt.show()
        # fmt_soln(soln, n_nodes, n_branches)
