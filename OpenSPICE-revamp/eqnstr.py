#!/usr/bin/env python3

from components import Resistor, Capacitor, Inductor, VSource, ISource
from abc import ABC, abstractmethod

class EqnStrContext:
    def __init__(self, strategy):
        self.strategy = strategy
    def execute_strategy(self, parser_output_dict):
        return self.strategy.do_operation(parser_output_dict)

class EqnStrStrategy(ABC):
    @abstractmethod
    def do_operation(self, parser_output_dict):
        pass
