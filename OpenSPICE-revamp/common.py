#!/usr/bin/env python3

def dv_format(s, n):
    return "(({})-({}))".format(v_format(s, n, trans=True, prev=False),
                                v_format(s, n, trans=True, prev=True ))

def v_format(s, n, trans=False, prev=False):
    outer = "x" if not prev else "x_prev"
    return "({}[{}])".format(outer, n.index(s)) if s != "0" else "(0.00)"

def di_format(s, n):
    return "(({})-({}))".format(i_format(s, n, trans=True, prev=False),
                                i_format(s, n, trans=True, prev=True ))

def i_format(s, n, trans=False, prev=False):
    outer = "x" if not prev else "x_prev"
    return "({}[{}])".format(outer, len(n) + int(s))
