#!/usr/bin/env python3

from arpeggio import ZeroOrMore, EOF, Optional, OneOrMore, RegExMatch, ParserPython, Terminal, NonTerminal

#######################################################################################

# Component Classes #

class Resistor:
    pass

class Capacitor:
    pass

class Inductor:
    pass

class VSource:
    pass

class ISource:
    pass

#######################################################################################

# Top-Level Netlist Rules #

def netlist():
    return ZeroOrMore(branch, OneOrMore(newline)), Optional([branch, ctrl])

def branch():
    # TODO: Enable behavisource and behavvsource
    return [resistor, capacitor, inductor, vsource, isource, extvsource, extisource,
            vccssource, vcvssource, ccvssource, cccssource]

def ctrl():
    return control, OneOrMore(newline), [op_pt, tran], OneOrMore(newline), end

#######################################################################################

# Control Rules #

def control():
    return RegExMatch('.control')

def op_pt():
    return RegExMatch('.op')

def tran():
    return RegExMatch('.tran'), tstep, tstop, Optional(tstart, Optional(tmax)), Optional(uic)

def tstep():
    return _float()

def tstop():
    return _float()

def tstart():
    return _float()

def tmax():
    return _float()

def uic():
    return RegExMatch("uic")

def end():
    return RegExMatch(".end")

def _float():
    return RegExMatch(r'[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)')

#######################################################################################

# Component Rules #

def inductor():
    return lcomponent, node, node, passiveValue, Optional(ic)

def capacitor():
    return ccomponent, node, node, passiveValue, Optional(ic)

def resistor():
    return rcomponent, node, node, passiveValue

def vsource():
    return vcomponent, node, node, passiveValue

def isource():
    return icomponent, node, node, passiveValue

def extvsource():
    return vcomponent, node, node, dc, zero, external

def extisource():
    return icomponent, node, node, dc, zero, external

def vccssource():
    return vccscomponent, node, node, node, node, passiveValue

def vcvssource():
    return vcvscomponent, node, node, node, node, passiveValue

def ccvssource():
    return ccvscomponent, node, node, node, node, passiveValue

def cccssource():
    return cccscomponent, node, node, node, node, passiveValue

def behavisource():
    return behavsrccomponent, node, node, iequalsbehav

def behavvsource():
    return behavsrccomponent, node, node, vequalsbehav

#######################################################################################

# Generic Branch Rules #

def node():
    return RegExMatch(r'\d+')

def passiveValue():
    return RegExMatch(r'\d+')

def stateVarValue():
    return RegExMatch(r'\d+')

def newline():
    return RegExMatch(r'\n')

def ic():
    return RegExMatch(r'ic='), stateVarValue

def dc():
    return RegExMatch(r'dc')

def zero():
    return RegExMatch(r'0')

def external():
    return RegExMatch(r'external')

def iequalsbehav():
    return RegExMatch(r'i='), behavexpr

def vequalsbehav():
    return RegExMatch(r'v='), behavexpr

def behavexpr():
    # TODO
    return RegExMatch('')

#######################################################################################

# Component Identifier Rules #

def ccomponent():
    return RegExMatch(r'C\d+')

def rcomponent():
    return RegExMatch(r'R\d+')

def lcomponent():
    return RegExMatch(r'L\d+')

def vcomponent():
    return RegExMatch(r'V\d+')

def icomponent():
    return RegExMatch(r'I\d+')

def vccscomponent():
    return RegExMatch(r'G\d+')

def vcvscomponent():
    return RegExMatch(r'E\d+')

def ccvscomponent():
    return RegExMatch(r'H\d+')

def cccscomponent():
    return RegExMatch(r'F\d+')

def behavsrccomponent():
    return RegExMatch(r'B\d+')

#######################################################################################

# Parsing Functions #

def filter_terms(ptree):
    return [_ for _ in ptree if type(_) != Terminal]

def nonterm_is_branch(nonterm):
    assert type(nonterm) == NonTerminal
    return "branch" in nonterm.name

def nonterm_is_ctrl(nonterm):
    assert type(nonterm) == NonTerminal
    return "ctrl" in nonterm.name

def gen_dict_from_ctrl(nonterm):
    assert nonterm_is_ctrl(nonterm)
    rule_names = [n.rule_name for n in nonterm]
    if "op_pt" in rule_names:
        return {"test_type" : "op_pt"}
    elif "tran" in rule_names:
        tran_node = nonterm[rule_names.index("tran")]
        tran_node_rule_names = [n.rule_name for n in tran_node]
        tran_d = {"test_type" : "tran",
                  "tstep"     : tran_node[1].value,
                  "tstop"     : tran_node[2].value}
        if "tstart" in tran_node_rule_names:
            tran_d["tstart"] = tran_node[3].value
            if "tmax" in tran_node_rule_names:
                tran_d["tmax"] = tran_node[4].value
                if "uic" in tran_node_rule_names:
                    tran_d["uic"] = tran_node[5].value
            else:
                if "uic" in tran_node_rule_names:
                    tran_d["uic"] = tran_node[4].value
        else:
            if "uic" in tran_node_rule_names:
                tran_d["uic"] = tran_node[3].value
        return tran_d
    else:
        assert False

def gen_dict_from_branch(nonterm):
    assert nonterm_is_branch(nonterm)
    if   nonterm[0].rule_name == "resistor":
        assert len(nonterm[0]) == 4
        return {"component"  : Resistor,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : nonterm[0][3].value}
    elif nonterm[0].rule_name == "capacitor":
        assert len(nonterm[0]) == 4 or len(nonterm[0]) == 5
        _cap = {"component"  : Capacitor,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : nonterm[0][3].value}
        if len(nonterm[0]) == 5:
            _cap["ic"] = nonterm[0][4][1].value
        return _cap
    elif nonterm[0].rule_name == "inductor":
        assert len(nonterm[0]) == 4 or len(nonterm[0]) == 5
        _ind = {"component"  : Inductor,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : nonterm[0][3].value}
        if len(nonterm[0]) == 5:
            _ind["ic"] = nonterm[0][4][1].value
        return _ind
    elif nonterm[0].rule_name == "vsource":
        assert len(nonterm[0]) == 4
        return {"component"  : VSource,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : nonterm[0][3].value}
    elif nonterm[0].rule_name == "isource":
        assert len(nonterm[0]) == 4
        return {"component"  : ISource,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : nonterm[0][3].value}
    elif nonterm[0].rule_name == "extvsource":
        assert len(nonterm[0]) == 6
        return {"component"  : VSource,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : "get_vsrc()"}
    elif nonterm[0].rule_name == "extisource":
        assert len(nonterm[0]) == 6
        return {"component"  : ISource,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : "get_isrc()"}
    elif nonterm[0].rule_name == "vccssource":
        assert len(nonterm[0]) == 6
        return {"component"  : ISource,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : linear_dep_src(nonterm[0][3].value,
                                              nonterm[0][4].value,
                                              nonterm[0][5].value,
                                              is_voltage_controlled=True)}
    elif nonterm[0].rule_name == "vcvssource":
        assert len(nonterm[0]) == 6
        return {"component"  : VSource,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : linear_dep_src(nonterm[0][3].value,
                                              nonterm[0][4].value,
                                              nonterm[0][5].value,
                                              is_voltage_controlled=True)}
    elif nonterm[0].rule_name == "ccvssource":
        assert len(nonterm[0]) == 6
        return {"component"  : VSource,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : linear_dep_src(nonterm[0][3].value,
                                              nonterm[0][4].value,
                                              nonterm[0][5].value,
                                              is_voltage_controlled=False)}
    elif nonterm[0].rule_name == "cccssource":
        assert len(nonterm[0]) == 6
        return {"component"  : ISource,
                "node_plus"  : nonterm[0][1].value,
                "node_minus" : nonterm[0][2].value,
                "value"      : linear_dep_src(nonterm[0][3].value,
                                              nonterm[0][4].value,
                                              nonterm[0][5].value,
                                              is_voltage_controlled=False)}
    else:
        assert False

def v_format(s):
    return "x['v({})']".format(s)

def i_format(s):
    return "x['i({})']".format(s)

def linear_dep_src(s_plus, s_minus, gain, is_voltage_controlled=True):
    return "(({})*(({})-({})))".format(gain, v_format(s_plus)  if is_voltage_controlled else i_format(s_plus),
                                             v_format(s_minus) if is_voltage_controlled else i_format(s_minus))

def gen_dict(nonterm):
    if nonterm_is_branch(nonterm):
        return gen_dict_from_branch(nonterm)
    elif nonterm_is_ctrl(nonterm):
        return gen_dict_from_ctrl(nonterm)
    else:
        assert False

def gen_data_dicts(ptree):
    return [gen_dict(_) for _ in ptree]

def parse(txt):
    return gen_data_dicts(filter_terms(parser.parse(txt)))

#######################################################################################

if __name__ == "__main__":
    parser = ParserPython(netlist, ws='\t\r ')
    with open("dep_sources.cir", "r") as f:
        print(parse(f.read()))
