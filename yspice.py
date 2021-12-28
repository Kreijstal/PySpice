#!/usr/bin/env python3

from arpeggio import ZeroOrMore, EOF, ParserPython
from arpeggio import RegExMatch
import numpy
import sys

# https://pypi.org/project/Arpeggio/1.0/

### Parsing Functions ###

def root():
    return ZeroOrMore(element), EOF

# TODO: check
def element():
    return el, node, node, val, RegExMatch(r';')

def el():
    return RegExMatch(r'(R\d+)|(V\d+)')

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
    return nodes

if __name__ == "__main__":
    parser = ParserPython(root)
    with open(sys.argv[1], "r") as f:
        parse_tree = parser.parse(f.read())
        nodes = get_nodes(parse_tree)
        G_matrix = numpy.zeros([len(nodes), len(nodes)])
        for r in parse_tree:
            _r = str(r).replace("|", "").split()
            if _r != [] and _r[0][0] == "R":
                if int(_r[1]) != 0 and int(_r[2]) != 0:
                    G_matrix[int(_r[1]) - 1][int(_r[2]) - 1] = -1.00 / float(_r[3])
                    G_matrix[int(_r[2]) - 1][int(_r[1]) - 1] = -1.00 / float(_r[3])
                if int(_r[1]) != 0:
                    G_matrix[int(_r[1]) - 1][int(_r[1]) - 1] += 1.00 / float(_r[3])
                if int(_r[2]) != 0:
                    G_matrix[int(_r[2]) - 1][int(_r[2]) - 1] += 1.00 / float(_r[3])
        print(G_matrix)
