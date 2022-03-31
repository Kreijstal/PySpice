#!/usr/bin/env python3
from math import sin, pi, exp
from scipy.optimize import root
from sys import argv
from PySpice.Spice.Parser import SpiceParser
import struct
from functools import reduce
from operator import concat
import array

get_vsrc = lambda dc_vals, timestep, node_id, ngspice_id : None
get_isrc = lambda dc_vals, timestep, node_id, ngspice_id : None
send_data = lambda actual_vector_values, number_of_vectors, ngspice_id : None

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
def inflim(expr, seed, dt, mid_trans, timestep, start_time):
    if timestep == start_time:
        expr = expr.replace('x[t+dt]', 'x').replace('x[t]', 'x')
    else:
        for s in range(len(seed)):
            expr = expr.replace('x[t][%d]' % s, str(seed[s]))
        expr = expr.replace('x[t+dt]', 'x')
    expr = expr.replace('dt', str(dt)).replace('t', str(timestep))
    return expr

# process netlist expressions with function f
def process_netlist_expr(lines, f, dt, seed=[], mid_trans=False, timestep=0.0, start_time=0.0):
    for i in range(len(lines)):
        lines[i][3] = f(lines[i][3], seed, dt, mid_trans, timestep, start_time)
        if len(lines[i]) == 5 and not mid_trans:
            lines[i][4] = f(lines[i][4], seed, dt, mid_trans, timestep, start_time)
    return lines

def get_nodes(lines):
    nodes = []
    for l in lines.split("\n"):
        if l != "":
            l = l.split(" ")
            if l[1] not in nodes:
                nodes.append(l[1])
            if l[2] not in nodes:
                nodes.append(l[2])
    assert "0" in nodes
    nodes.remove("0")
    nodes = ["0"] + nodes
    assert nodes[0] == "0"
    return nodes

def kcl_prepend(s, num_nodes, branch_idx, plus):
    return "{}x[{}]".format("+" if plus else "-", num_nodes + branch_idx - 1) + s

def get_kcl_eqns(lines):
    nodes = get_nodes(lines)
    num_nodes = len(nodes)
    node_dict = dict(zip(nodes[1:], range(len(nodes[1:]))))
    num_branches = len(lines)
    kcl = [""] * (num_nodes - 1)
    lines = [n.split(" ") for n in lines.split("\n") if n != ""]
    for i in range(len(lines)):
        if lines[i][1] != "0":
            node_0 = node_dict[lines[i][1]]
            kcl[node_0-1] = kcl_prepend(kcl[node_0-1], num_nodes, i, False)
        if lines[i][2] != "0":
            node_1 = node_dict[lines[i][2]]
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
def op_pt(netlist, mid_trans=False, seed=[], dt=1.0, timestep=0.0, start_time=0.0):
    lines = [n.split(" ") for n in netlist.split("\n") if n != ""]
    lines = process_netlist_expr(lines, inflim, dt, seed, mid_trans, timestep, start_time)
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
def transient(netlist, dt, end_time, start_time, uic):
    trans_soln = []
    voltage_list = []
    timesteps = []
    for i in range(round(end_time / dt)):
        curr_timestep = (dt*i) + start_time
        if i == 0:
            [soln,num_nodes,num_branches,node_dict] = op_pt(netlist, mid_trans=(not uic), dt=dt, timestep=start_time, start_time=start_time)
        else:
            [soln,num_nodes,num_branches,node_dict] = op_pt(netlist, mid_trans=True, seed=trans_soln[len(trans_soln)-1], dt=dt, timestep=curr_timestep, start_time=start_time)
        trans_soln.append(soln)
        global send_data
        DUMMY_SPICE_ID = 0
        voltage_list = ['V({})'.format(n) for n in get_nodes(netlist) if n != "0"]
        actual_vector_values = dict(zip(voltage_list, [soln[node_dict[n]] for n in get_nodes(netlist) if n != "0"]))
        actual_vector_values['time'] = curr_timestep
        number_of_vectors = num_nodes
        timesteps.append(curr_timestep)
        send_data(actual_vector_values, number_of_vectors, DUMMY_SPICE_ID)
    return [trans_soln,voltage_list,timesteps]

def next_v_txt(node_no, nodes_arr):
    node_dict = dict(zip(nodes_arr[1:], range(len(nodes_arr[1:]))))
    if node_no == "0":
        return "0.00"
    else:
        return "x[t+dt][{}]".format(node_dict[node_no])

def curr_v_txt(node_no, nodes_arr):
    node_dict = dict(zip(nodes_arr[1:], range(len(nodes_arr[1:]))))
    if node_no == "0":
        return "0.00"
    else:
        return "x[t][{}]".format(node_dict[node_no])

def next_i_txt(branch_no, num_nodes):
    return "x[t+dt][{}]".format(num_nodes - 1 + branch_no)

def curr_i_txt(branch_no, num_nodes):
    return "x[t][{}]".format(num_nodes - 1 + branch_no)

def filter_voltages(input_str, nodes_arr):
    for node in nodes_arr:
        input_str = input_str.replace("v({})".format(node), next_v_txt(str(node), nodes_arr))
    return input_str

def paranth_split(x):
    in_par = False
    _x = ""
    for _c in range(len(x)):
        if x[_c] == "(":
            in_par = True
            _x += x[_c]
        elif x[_c] == ")":
            in_par = False
            _x += x[_c]
        elif in_par and x[_c] == " ":
            _x += ","
        else:
            _x += x[_c]
    return _x

def filter_sin(txt):
    # txt is expected to be of the form SIN(X,X,X,X,X,X)
    interior = txt[txt.find("(")+1:][:-1]
    assert "SIN(" + interior + ")" == txt
    param_list = interior.split(",")
    param_names = ["(V0)", "(VA)", "(FREQ)", "(TD)", "(THETA)", "(PHASE)"]
    assert len(param_list) <= len(param_names)
    assert len(param_list) >= 2
    if len(param_list) < len(param_names):
        sub_dict = {}
        for i in range(len(param_list)):
            sub_dict[param_names[i]] = param_list[i].replace("Hz","")\
                                                    .replace("s","")\
                                                    .replace("V","")\
                                                    .replace("k","e3")\
                                                    .replace("u","e-6")\
                                                    .replace("m","e-3")
        if len(param_list) <= 5:
            sub_dict[param_names[5]] = str(0.0)
        if len(param_list) <= 4:
            sub_dict[param_names[4]] = str(0.0)
        if len(param_list) <= 3:
            sub_dict[param_names[3]] = str(0.0)
        if len(param_list) <= 2:
            sub_dict[param_names[2]] = str(1.0 / END_T)
    else:
        sub_dict = dict(zip(param_names, param_list))
    cond0 = "0<=t<(TD)"
    cond1 = "t>=(TD)"
    state0 = "((V0))"
    state1 = "((V0))+((VA)*exp(-(t-((TD)))*((THETA)))*sin(2*pi*((FREQ))*(t-(TD))+((PHASE))))"
    for l in param_names:
        cond0  = cond0 .replace(l, sub_dict[l])
        cond1  = cond1 .replace(l, sub_dict[l])
        state0 = state0.replace(l, sub_dict[l])
        state1 = state1.replace(l, sub_dict[l])
    interior = "((({})*({}))+(({})*({})))".format(cond0,state0,cond1,state1)
    return "sin(" + interior + ")"

def filter_pulse(txt, end_time, dt):
    # txt is expected to be of the form SIN(X,X,X,X,X,X)
    interior = txt[txt.find("(")+1:][:-1]
    assert "PULSE(" + interior + ")" == txt
    param_list = interior.split(",")
    param_names = ["(V1)", "(V2)", "(TD)", "(TR)", "(TF)", "(PW)", "(PER)", "(PHASE)"]
    assert len(param_list) <= len(param_names)
    assert len(param_list) >= 2
    if len(param_list) < len(param_names):
        sub_dict = {}
        for i in range(len(param_list)):
            sub_dict[param_names[i]] = param_list[i].replace("Hz","")\
                                                    .replace("s","")\
                                                    .replace("V","")\
                                                    .replace("k","e3")\
                                                    .replace("u","e-6")\
                                                    .replace("m","e-3")
        if len(param_list) <= 8:
            sub_dict[param_names[7]] = str(0.0)
        if len(param_list) <= 7:
            sub_dict[param_names[6]] = str(end_time)
        if len(param_list) <= 6:
            sub_dict[param_names[5]] = str(end_time)
        if len(param_list) <= 5:
            sub_dict[param_names[4]] = str(dt)
        if len(param_list) <= 4:
            sub_dict[param_names[3]] = str(dt)
        if len(param_list) <= 3:
            sub_dict[param_names[2]] = str(0.0)
    else:
        sub_dict = dict(zip(param_names, param_list))
    cond0 = "t<=((TD))"
    cond1 = "((TD))<t<=(((TD))+((TR)))"
    cond2 = "(((TD))+((TR)))<t<=(((TD))+((TR))+((PW)))"
    cond3 = "(((TD))+((TR))+((PW)))<t<=(((TD))+((TR))+((PW))+((TF)))"
    cond4 = "(((TD))+((TR))+((PW))+((TF)))<t"
    state0 = "((V1))"
    state1 = "(((((V2))-((V1)))*t)+((((TR))+((TD)))*((V1)))-(((TD))*((V2))))/((TR))" if sub_dict["(TR)"] != str(0) else str(0)
    state2 = "((V2))"
    state3 = "(((((V1))-((V2)))*t)+(((V2))*((TF)))-((((V1))-((V2)))*(((TD))+((TR))+((PW)))))/((TF))" if sub_dict["(TF)"] != str(0) else str(0)
    state4 = "((V1))"
    for l in param_names:
        cond0 = cond0.replace(l, sub_dict[l])
        cond1 = cond1.replace(l, sub_dict[l])
        cond2 = cond2.replace(l, sub_dict[l])
        cond3 = cond3.replace(l, sub_dict[l])
        cond4 = cond4.replace(l, sub_dict[l])
        state0 = state0.replace(l, sub_dict[l])
        state1 = state1.replace(l, sub_dict[l])
        state2 = state2.replace(l, sub_dict[l])
        state3 = state3.replace(l, sub_dict[l])
        state4 = state4.replace(l, sub_dict[l])
    interior = "(({})*({}))+(({})*({}))+(({})*({}))+(({})*({}))+(({})*({}))".format(
            cond0,state0,cond1,state1,cond2,state2,cond3,state3,cond4,state4)
    return "(" + interior + ")"

def netlist_translate(netlist_txt, nodes_arr, end_time, dt):
    new_netlist_txt = ""
    line_count = 0
    for line in netlist_txt.split("\n"):
        if line != "":
            _line = line.split(" ")
            if line[0] == "R":
                # Resistor
                _line[3] = _line[3].replace("Ohm", "")
                _line[3] = _line[3].replace("k","e3")
                _line[3] = _line[3].replace("u","e-6")
                _line[3] = _line[3].replace("m","e-3")
                _line[3] = "({}-{})-(({})*({}))".format(next_v_txt(_line[1], nodes_arr),
                                                        next_v_txt(_line[2], nodes_arr),
                                                        next_i_txt(line_count, len(nodes_arr)), _line[3])
            elif line[0] == "V":
                # Voltage source
                _line[3] = _line[3].replace("V", "")
                _line[3] = _line[3].replace("k","e3")
                _line[3] = _line[3].replace("u","e-6")
                _line[3] = _line[3].replace("m","e-3")
                _line[3] = _line[3].replace('dc', 'dcv')
                if len(_line) == 8:
                    if "SIN" in _line[7]:
                        dc_offset = _line[4].replace("V","")
                        ac_amplitude = _line[6].replace("V","")
                        _line[3] = "({})*({})+({})".format(ac_amplitude, filter_sin(_line[7]), dc_offset)
                    else:
                        assert False
                    _line = _line[:4]
                elif len(_line) == 6:
                    if "PULSE" in _line[5]:
                        dc_offset = _line[4].replace("V","")
                        _line[3] = "({})+({})".format(filter_pulse(_line[5], end_time, dt), dc_offset)
                        _line = _line[:4]
                _line[3] = "({}-{})-({})".format(next_v_txt(_line[1], nodes_arr),
                                                 next_v_txt(_line[2], nodes_arr), _line[3])
                if len(_line) == 6 and _line[5] == "external":
                    del _line[5]
                    del _line[4]
                assert len(_line) != 6
            elif line[0] == "I":
                # Current source
                _line[3] = _line[3].replace("A", "")
                _line[3] = _line[3].replace("k","e3")
                _line[3] = _line[3].replace("u","e-6")
                _line[3] = _line[3].replace("m","e-3")
                _line[3] = _line[3].replace('dc', 'dci')
                _line[3] = "({})-({})".format(next_i_txt(line_count, len(nodes_arr)),
                                              _line[3])
                if len(_line) == 6 and _line[5] == "external":
                    del _line[5]
                    del _line[4]
                assert len(_line) != 6
            elif line[0] == "L":
                # Inductor
                _line[3] = _line[3].replace("H","")
                _line[3] = _line[3].replace("k","e3")
                _line[3] = _line[3].replace("u","e-6")
                _line[3] = _line[3].replace("m","e-3")
                _line[3] = "(({}-{})*dt)-(({})*(({})-({}))) (({})-({}))".format(next_v_txt(_line[1], nodes_arr),
                                                                                next_v_txt(_line[2], nodes_arr),
                                                                                _line[3],
                                                                                next_i_txt(line_count, len(nodes_arr)),
                                                                                curr_i_txt(line_count, len(nodes_arr)),
                                                                                curr_v_txt(_line[1], nodes_arr),
                                                                                curr_v_txt(_line[2], nodes_arr))
            elif line[0] == "C":
                # Capacitor
                _line[3] = _line[3].replace("F", "")
                _line[3] = _line[3].replace("k","e3")
                _line[3] = _line[3].replace("u","e-6")
                _line[3] = _line[3].replace("m","e-3")
                _line[3] = "({}*dt)-(({})*(({}-{})-({}-{})))".format(next_i_txt(line_count, len(nodes_arr)),
                                                                     _line[3],
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

def get_sim_type(netlist_file_contents):
    lines = netlist_file_contents.split("\n")
    for l in lines:
        if ".tran" in l:
            return "transient"
    return "op_pt"

def get_tran_params(netlist_file_contents):
    lines = netlist_file_contents.split("\n")
    for l in lines:
        if ".tran" in l:
            _l = l.split(" ")
            assert _l[0] == ".tran"
            assert len(_l) >= 3
            assert len(_l) <= 6
            dt = float(_l[1].replace("u", "e-6").replace("s", ""))
            end_time = float(_l[2].replace("m", "e-3").replace("s", ""))
            if len(_l) > 3 and _l[3] != "uic":
                start_time = float(_l[3].replace("s", ""))
            else:
                start_time = 0.00
            # TODO: tmax is never used since variable time-stepping not
            # currently supported.
            if len(_l) > 4 and _l[4] != "uic":
                tmax = float(_l[4].replace("s", ""))
            else:
                tmax = 0.00
            if _l[len(_l)-1] == "uic":
                uic = True
            else:
                uic = False
            return [dt, end_time, start_time, tmax, uic]
    assert False


def pack_arr(a):
    return array.array('d', a).tobytes()

def _spice_input(input_filename, output_filename):
    with open(input_filename, "r") as netlist_file:
        netlist_file_contents = netlist_file.read()
        sim_type = get_sim_type(netlist_file_contents)
        dt = 0.00
        end_time = 0.00
        start_time = 0.00
        tmax = 0.00
        uic = False
        if sim_type == "transient":
            [dt, end_time, start_time, tmax, uic] = get_tran_params(netlist_file_contents)
        netlist_file_contents = filter_dot_statements(netlist_file_contents)
        netlist_file_contents = "\n".join([paranth_split(n) for n in netlist_file_contents.split("\n") if n != ''])
        nodes_arr = get_nodes(netlist_file_contents)
        _netlist = netlist_translate(netlist_file_contents, nodes_arr, end_time, dt)
        if sim_type == "transient":
            assert start_time < end_time
            [soln,voltage_list,timesteps] = transient(_netlist, dt, end_time, start_time, uic)
            assert len(soln) == len(timesteps)
        elif sim_type == "op_pt":
            [soln,num_nodes,num_branches,node_dict] = op_pt(_netlist)
            voltage_list = ['V({})'.format(n) for n in get_nodes(_netlist) if n != "0"]
        else:
            assert False
        with open(output_filename, "w") as spice_raw_file:
            spice_raw_file_txt  = "Title: MyCircuit\n"
            spice_raw_file_txt += "Date: Thu Jun 11 23:17:40  2020\n"
            if sim_type == "transient":
                spice_raw_file_txt += "Plotname: Transient Analysis\n"
            elif sim_type == "op_pt":
                spice_raw_file_txt += "Plotname: Operating Point\n"
            spice_raw_file_txt += "Flags: real\n"
            if sim_type == "transient":
                spice_raw_file_txt += "No. Variables: {}\n".format(1 + len(voltage_list))
                spice_raw_file_txt += "No. Points: {}\n".format(len(soln))
            elif sim_type == "op_pt":
                spice_raw_file_txt += "No. Variables: {}\n".format(len(voltage_list))
                spice_raw_file_txt += "No. Points: {}\n".format(1)
            spice_raw_file_txt += "Variables:\n"
            if sim_type == "transient":
                spice_raw_file_txt += "\t0\ttime\ttime\n"
                spice_raw_file_txt += "".join(["\t{}\t{}\tvoltage\n".format(1+i,v) for i,v in enumerate(voltage_list)])
            elif sim_type == "op_pt":
                spice_raw_file_txt += "".join(["\t{}\t{}\tvoltage\n".format(i,v) for i,v in enumerate(voltage_list)])
            spice_raw_file_txt += "Binary:\n"
            spice_raw_file.write(spice_raw_file_txt)
        with open(output_filename,"ab") as spice_raw_file:
            if sim_type == "transient":
                for j in range(len(soln)):
                    s = soln[j]
                    numbers = [timesteps[j]] + [v for i,v in enumerate(s) if i < len(voltage_list)]
                    raw_data_arr = pack_arr(numbers)
                    spice_raw_file.write(raw_data_arr)
            elif sim_type == "op_pt":
                packed_arr = pack_arr([v for i,v in enumerate(soln) if i < len(voltage_list)])
                spice_raw_file.write(packed_arr)
            else:
                assert False
