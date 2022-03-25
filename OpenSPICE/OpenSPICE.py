#!/usr/bin/env python3
from math import sin, pi
from scipy.optimize import root
from sys import argv
from PySpice.Spice.Parser import SpiceParser
import struct

get_vsrc = None
get_isrc = None
send_data = None

END_T = 1000.00
DT = 0.1

# TODO x -> dictionary mapping timestep to vector of currents and voltages
# TODO initial conditions

# Foundational functions

def set_get_vsrc(_get_vsrc):
    global get_vsrc
    get_vsrc = _get_vsrc

def set_get_isrc(_get_isrc):
    global get_isrc
    get_isrc = _get_isrc

def set_send_data(_send_data):
    global send_data
    send_data = _send_data

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
    for l in lines.split("\n"):
        if l != "":
            l = l.split(" ")
            if int(l[1]) not in nodes:
                nodes.append(int(l[1]))
            if int(l[2]) not in nodes:
                nodes.append(int(l[2]))
    nodes.sort()
    # for i in range(len(nodes)-1):
    #     assert nodes[i+1] - nodes[i] == 1
    assert nodes[0] == 0
    return nodes

def kcl_prepend(s, num_nodes, branch_idx, plus):
    return "{}x[{}]".format("+" if plus else "-", num_nodes + branch_idx - 1) + s

def get_kcl_eqns(lines):
    nodes = get_nodes(lines)
    assert nodes[0] == 0
    num_nodes = len(nodes)
    node_dict = dict(zip(nodes[1:], range(len(nodes[1:]))))
    num_branches = len(lines)
    kcl = [""] * (num_nodes - 1)
    lines = [n.split(" ") for n in lines.split("\n") if n != ""]
    for i in range(len(lines)):
        if lines[i][1] != "0":
            node_0 = node_dict[int(lines[i][1])]
            kcl[node_0-1] = kcl_prepend(kcl[node_0-1], num_nodes, i, False)
        if lines[i][2] != "0":
            node_1 = node_dict[int(lines[i][2])]
            kcl[node_1-1] = kcl_prepend(kcl[node_1-1], num_nodes, i, True)
    return [kcl,num_nodes,num_branches,node_dict]

def solve(fn, output_len):
    return root(fn, [1.00] * (output_len)).x

def fmt_soln(x, num_nodes, num_branches):
    for n in range(num_nodes - 1):
        print("V{} = {} [V]".format(n + 1, x[n]))
    for b in range(num_branches):
        print("I{} = {} [A]".format(b, x[num_nodes + b - 1]))

def vsrc_sub(_eqn, timestep=0.00):
    global get_vsrc
    if get_vsrc:
        DUMMY_NODE = 0
        DUMMY_SPICE_ID = 0
        dc_vals = [0.00]
        get_vsrc(dc_vals, timestep, DUMMY_NODE, DUMMY_SPICE_ID)
        _eqn = _eqn.replace("dcv", str(dc_vals[0]))
    return _eqn

def isrc_sub(_eqn, timestep=0.00):
    global get_isrc
    if get_isrc:
        DUMMY_NODE = 0
        DUMMY_SPICE_ID = 0
        dc_vals = [0.00]
        get_isrc(dc_vals, timestep, DUMMY_NODE, DUMMY_SPICE_ID)
        _eqn = _eqn.replace("dci", str(dc_vals[0]))
    return _eqn

# Take array of expressions and initial condition expressions
# and solve op point.

# Op point
# 1) Substitute constant dt and t -> inf.
# 2) Use Powell's to solve at a single timestep
def op_pt(netlist, mid_trans=False, seed=[], dt=1.0, timestep=0.0):
    lines = [n.split(" ") for n in netlist.split("\n") if n != ""]
    lines = process_netlist_expr(lines, inflim, dt, seed, mid_trans, timestep)
    # Note: Replace len(l) - 1 with 3 for transient nextstep function
    if mid_trans:
        iv_relations = [l[3] for l in lines]
    else:
        iv_relations = [l[len(l)-1] for l in lines]
    [kcl_relations,num_nodes,num_branches,node_dict] = get_kcl_eqns("\n".join([" ".join(l) for l in lines]))
    final_eqns = [isrc_sub(vsrc_sub(_eqn, timestep)) for _eqn in iv_relations + kcl_relations]
    l_fn_str = "lambda x : [" + ",".join(final_eqns) + "]"
    l_fn = eval(l_fn_str)
    soln = solve(l_fn, len(final_eqns))
    return [soln,num_nodes,num_branches,node_dict]

# Transient sim
# 1) Create initial condition equations and calculate
# 2) Set x[0] to initial condition
# 3) Loop. Update t on each timestep.
def transient(netlist):
    trans_soln = []
    voltage_list = []
    timesteps = []
    for i in range(int(END_T / DT)):
        if i == 0:
            [soln,num_nodes,num_branches,node_dict] = op_pt(netlist)
        else:
            [soln,num_nodes,num_branches,node_dict] = op_pt(netlist, mid_trans=True, seed=trans_soln[len(trans_soln)-1], dt=DT, timestep=DT*i)
        trans_soln.append(soln)
        global send_data
        DUMMY_SPICE_ID = 0
        voltage_list = ['V({})'.format(n) for n in get_nodes(netlist) if n != 0]
        actual_vector_values = dict(zip(voltage_list, [soln[node_dict[n]] for n in get_nodes(netlist) if n != 0]))
        actual_vector_values['time'] = DT*i
        number_of_vectors = num_nodes
        timesteps.append(DT*i)
        send_data(actual_vector_values, number_of_vectors, DUMMY_SPICE_ID)
    return [trans_soln,voltage_list,timesteps]

def next_v_txt(node_no, nodes_arr):
    node_dict = dict(zip(nodes_arr[1:], range(len(nodes_arr[1:]))))
    if node_no == "0":
        return "0.00"
    else:
        return "x[t+dt][{}]".format(node_dict[int(node_no)])

def curr_v_txt(node_no, nodes_arr):
    node_dict = dict(zip(nodes_arr[1:], range(len(nodes_arr[1:]))))
    if node_no == "0":
        return "0.00"
    else:
        return "x[t][{}]".format(node_dict[int(node_no)])

def next_i_txt(branch_no, num_nodes):
    return "x[t+dt][{}]".format(num_nodes - 1 + branch_no)

def curr_i_txt(branch_no, num_nodes):
    return "x[t][{}]".format(num_nodes - 1 + branch_no)

def filter_voltages(input_str, nodes_arr):
    for node in nodes_arr:
        input_str = input_str.replace("v({})".format(node), next_v_txt(str(node), nodes_arr))
    return input_str

def netlist_translate(netlist_txt, nodes_arr):
    new_netlist_txt = ""
    line_count = 0
    for line in netlist_txt.split("\n"):
        if line != "":
            _line = line.split(" ")
            if line[0] == "R":
                # Resistor
                _line[3] = "({}-{})-(({})*({}))".format(next_v_txt(_line[1], nodes_arr),
                                                        next_v_txt(_line[2], nodes_arr),
                                                        next_i_txt(line_count, len(nodes_arr)), _line[3].replace("Ohm", ""))
            elif line[0] == "V":
                # Voltage source
                _line[3] = _line[3].replace('dc', 'dcv')
                _line[3] = "({}-{})-({})".format(next_v_txt(_line[1], nodes_arr),
                                                 next_v_txt(_line[2], nodes_arr), _line[3].replace("V", ""))
                if len(_line) == 6 and _line[5] == "external":
                    del _line[5]
                    del _line[4]
                assert len(_line) != 6
            elif line[0] == "I":
                # Current source
                _line[3] = _line[3].replace('dc', 'dci')
                _line[3] = "({}-{})-({})".format(next_i_txt(line_count, len(nodes_arr)), curr_i_txt(line_count, len(nodes_arr)), _line[3].replace("A", ""))
                if len(_line) == 6 and _line[5] == "external":
                    del _line[5]
                    del _line[4]
                assert len(_line) != 6
            elif line[0] == "L":
                # Inductor
                _line[3] = "(({}-{})*dt)-(({})*(({})-({}))) (({})-({}))".format(next_v_txt(line[1], nodes_arr),
                                                                                next_v_txt(line[2], nodes_arr),
                                                                                _line[3].replace("H", ""),
                                                                                next_i_txt(line_count, len(nodes_arr)),
                                                                                curr_i_txt(line_count, len(nodes_arr)),
                                                                                curr_v_txt(line[1], nodes_arr),
                                                                                curr_v_txt(line[2], nodes_arr))
            elif line[0] == "C":
                # Capacitor
                _line[3] = "({}*dt)-(({})*(({}-{})-({}-{})))".format(next_i_txt(line_count, len(nodes_arr)),
                                                                     _line[3].replace("F", ""),
                                                                     next_v_txt(_line[1], nodes_arr),
                                                                     next_v_txt(_line[2], nodes_arr),
                                                                     curr_v_txt(_line[1], nodes_arr),
                                                                     curr_v_txt(_line[2], nodes_arr))
                if len(_line) == 5:
                    _line[4] = "({}-{})-{}".format(curr_v_txt(_line[1], nodes_arr),
                                                   curr_v_txt(_line[2], nodes_arr), _line[4].replace("ic=","").replace("V",""))
            elif line[0] == "B":
                # Behavioral sources
                if _line[3][0] == "i":
                    # Behavioral current source
                    _line[3] = "({})-({})".format(next_i_txt(line_count, len(nodes_arr)),
                                                  filter_voltages(_line[3], nodes_arr).replace("i=",""))
                elif _line[3][0] == "v":
                    # Behavioral voltage source
                    _line[3] = "({})-({})".format(next_v_txt(line_count, len(nodes_arr)),
                                                  filter_voltages(_line[3], nodes_arr).replace("v=",""))
                else:
                    assert False
            elif line[0] == "E":
                # Linear voltage-controlled voltage source
                _line = [_line[0], _line[1], _line[2], "({}-{})-({}*({}-{}))".format(next_v_txt(_line[1], nodes_arr),
                                                                                     next_v_txt(_line[2], nodes_arr),
                                                                                     _line[5], next_v_txt(_line[3], nodes_arr),
                                                                                     next_v_txt(_line[4], nodes_arr))]
            else:
                assert False
            next_line = " ".join(_line) + "\n"
            print(next_line)
            new_netlist_txt += next_line
            line_count += 1
    return new_netlist_txt

def filter_dot_statements(contents_txt):
    del_lines = []
    contents_txt_arr = contents_txt.split("\n")
    for line_idx in range(len(contents_txt_arr)):
        if contents_txt_arr[line_idx] != "":
            if contents_txt_arr[line_idx][0] == ".":
                del_lines = [line_idx] + del_lines
    for line_idx in del_lines:
        del contents_txt_arr[line_idx]
    return "\n".join(contents_txt_arr)

def spice_input(input_filename, output_filename):
    # sp = SpiceParser(source=spice_txt)
    # print(sp)
    # dump raw file for op point sim
    with open(input_filename, "r") as netlist_file:
        netlist_file_contents = netlist_file.read()
        netlist_file_contents = filter_dot_statements(netlist_file_contents)
        nodes_arr = get_nodes(netlist_file_contents)
        _netlist = netlist_translate(netlist_file_contents, nodes_arr)
        [soln,voltage_list,timesteps] = transient(_netlist)
        assert len(soln) == len(timesteps)
        with open(output_filename, "w") as spice_raw_file:
            spice_raw_file_txt  = "Title: MyCircuit\n"
            spice_raw_file_txt += "Date: Thu Jun 11 23:17:40  2020\n"
            spice_raw_file_txt += "Plotname: Transient Analysis\n"
            spice_raw_file_txt += "Flags: real\n"
            spice_raw_file_txt += "No. Variables: {}\n".format(len(voltage_list))
            spice_raw_file_txt += "No. Points: {}\n".format(len(soln))
            spice_raw_file_txt += "Variables:\n"
            spice_raw_file_txt += "\t0\ttime\ttime\n"
            spice_raw_file_txt += "\n".join(["\t{}\t{}\tvoltage".format(1+i,v) for i,v in enumerate(voltage_list)])
            spice_raw_file_txt += "Binary:\n"
            format_float = lambda x : hex(struct.unpack('<Q', struct.pack('<d', x))[0]).replace('0x', '')
            for j in range(len(soln)):
                s = soln[j]
                spice_raw_file_txt += "".join([str(timesteps[j])] + [format_float(v) for i,v in enumerate(s) if i < len(voltage_list)]) + "\n"
            spice_raw_file.write(spice_raw_file_txt)

if __name__ == "__main__":
    print("argv[1] = {}, argv[2] = {}, argv[3] = {}".format(argv[1], argv[2], argv[3]))
    with open(argv[1], "r") as txt:
        # spice_input(txt.read())
        spice_input(argv[3])
        # x = transient(txt.read())
        # print([_x[1] for _x in x])
        # from numpy import linspace
        # import matplotlib.pyplot as plt
        # t = linspace(0.00, END_T, int(END_T / DT))
        # plt.plot(t, [_x[1] for _x in x])
        # plt.show()
