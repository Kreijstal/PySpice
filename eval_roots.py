#!/usr/bin/env python3

import scipy.optimize

def roots_from_txt(behav_txt):
    return scipy.optimize.root(eval("lambda x : " + behav_txt), [0.0], method = 'lm').x[0]

if __name__ == "__main__":
    print(roots_from_txt("(x[0] ** 2.0) - 1"))
