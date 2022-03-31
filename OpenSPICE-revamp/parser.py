#!/usr/bin/env python3

from arpeggio import ZeroOrMore, EOF, Optional, OneOrMore, RegExMatch, ParserPython

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

if __name__ == "__main__":
    parser = ParserPython(netlist, ws='\t\r ')
    with open("multi_r_netlist.cir") as f:
        print(parser.parse(f.read()).tree_str())
