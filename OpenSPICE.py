#!/usr/bin/env python3
from sympy import *

# Foundational functions

# Take limit of expression t -> inf
def inflim(expr, dt):
    t = symbols('t')
    return limit(eval(expr.replace('dt', str(dt))), t, oo, '+')

# Take array of expressions and initial condition expressions
# and solve op point.

# Op point
# 1) Substitute constant dt and t -> inf.
# 2) Use Broyden's to solve at a single timestep

# Transient sim
# 1) Create initial condition equations and calculate
# 2) Set x[0] to initial condition
# 3) Loop. Update t on each timestep.

if __name__ == "__main__":
    dt = 0.1
    print("--- Begin: limit test suite ---")
    assert inflim('exp(-t)', dt) == 0.00
    assert inflim('exp(-t+dt)', dt) == 0.00
    assert inflim('exp(-t)*dt', dt) == 0.00
    print("--- End: limit test suite ---")
