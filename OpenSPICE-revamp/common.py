#!/usr/bin/env python3

def dv_format(s):
    return "dv({})".format(s)

def v_format(s, n):
    return "(x[{}])".format(n.index(s)) if s != "0" else "(0.00)"

def di_format(s):
    return "di({})".format(s)

def i_format(s, n):
    return "(x[{}])".format(len(n) + int(s))
