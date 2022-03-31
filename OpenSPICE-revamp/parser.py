#!/usr/bin/env python3

from arpeggio import ZeroOrMore, EOF, Optional, OneOrMore, RegExMatch, ParserPython, Terminal, NonTerminal

#######################################################################################

class Resistor:
    pass

#######################################################################################

def netlist():
    return ZeroOrMore(branch, OneOrMore(newline)), Optional(branch)

def branch():
    return resistor

def resistor():
    return rcomponent, node, node, passiveValue

def rcomponent():
    return RegExMatch(r'R\d+')

def node():
    return RegExMatch(r'\d+')

def passiveValue():
    return RegExMatch(r'\d+')

def newline():
    return RegExMatch(r'\n')

#######################################################################################

def filter_terms(ptree):
    return [_ for _ in ptree if type(_) != Terminal]

def nonterm_is_branch(nonterm):
    assert type(nonterm) == NonTerminal
    return "branch" in nonterm.name

def gen_dict_from_branch(nonterm):
    assert nonterm_is_branch(nonterm)
    if nonterm[0].rule_name == "rcomponent":
        assert len(nonterm) == 4
        return {"component"  : Resistor,
                "node_plus"  : nonterm[1].value,
                "node_minus" : nonterm[2].value,
                "value"      : nonterm[3].value}
    else:
        assert False

def gen_dict(nonterm):
    if nonterm_is_branch(nonterm):
        return gen_dict_from_branch(nonterm)
    else:
        assert False

def gen_data_dicts(ptree):
    return [gen_dict(_) for _ in ptree]

if __name__ == "__main__":
    parser = ParserPython(netlist, ws='\t\r ')
    with open("multi_r_netlist.cir") as f:
        ptree = parser.parse(f.read()) 
        ptree = filter_terms(ptree)
        print(gen_data_dicts(ptree))
