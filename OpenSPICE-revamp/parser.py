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
    return ZeroOrMore(branch, OneOrMore(newline)), Optional(branch)

def branch():
    return [resistor, capacitor, inductor, vsource, isource]

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

#######################################################################################

# Parsing Functions #

def filter_terms(ptree):
    return [_ for _ in ptree if type(_) != Terminal]

def nonterm_is_branch(nonterm):
    assert type(nonterm) == NonTerminal
    return "branch" in nonterm.name

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
    else:
        assert False

def gen_dict(nonterm):
    if nonterm_is_branch(nonterm):
        return gen_dict_from_branch(nonterm)
    else:
        assert False

def gen_data_dicts(ptree):
    return [gen_dict(_) for _ in ptree]

def parse(txt):
    return gen_data_dicts(filter_terms(parser.parse(txt)))

#######################################################################################

if __name__ == "__main__":
    parser = ParserPython(netlist, ws='\t\r ')
    with open("isource.cir", "r") as f:
        print(parse(f.read()))
