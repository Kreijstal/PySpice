import logging
import os

from unicodedata import normalize
from PySpice.Unit.Unit import UnitValue, ZeroPower, PrefixedUnit
from PySpice.Unit.SiUnits import Tera, Giga, Mega, Kilo, Milli, Micro, Nano, Pico, Femto
from PySpice.Spice.Expressions import *
from .ElementParameter import FlagParameter
from .Netlist import (Circuit,
                      DeviceModel,
                      Library,
                      SubCircuit,
                      Comment)
from .BasicElement import (BehavioralSource,
                           BipolarJunctionTransistor,
                           Capacitor,
                           CoupledInductor,
                           CurrentSource,
                           Diode,
                           Inductor,
                           JunctionFieldEffectTransistor,
                           Mosfet,
                           Resistor,
                           SubCircuitElement,
                           VoltageControlledSwitch,
                           VoltageSource)
from .HighLevelElement import (PulseMixin,
                               SinusoidalMixin,
                               SingleFrequencyFMMixin,
                               ExponentialMixin,
                               AmplitudeModulatedMixin,
                               PatternMixin,
                               PieceWiseLinearMixin)
from .SpiceGrammar import SpiceParser as parser
from .SpiceModel import SpiceModelBuilderSemantics
from tatsu import to_python_sourcecode, to_python_model, compile
from tatsu.model import NodeWalker

_module_logger = logging.getLogger(__name__)


class ParseError(NameError):
    pass


class Statement:
    """ This class implements a statement, in fact a line in a Spice netlist. """

    @staticmethod
    def arg_to_python(x):

        if x:
            if str(x)[0].isdigit():
                return str(x)
            else:
                return "'{}'".format(x)
        else:
            return ''

    @staticmethod
    def args_to_python(*args):

        return [Statement.arg_to_python(x) for x in args]

    @staticmethod
    def kwargs_to_python(self, **kwargs):
        return Statement.join_args(*['{}={}'.format(key, self.value_to_python(value))
                                     for key, value in kwargs.items()])

    @staticmethod
    def join_args(self, *args):
        return ', '.join(args)


class DataStatement(Statement):
    """ This class implements a data definition.

    Spice syntax::

        .data name, name, ..., value, value, value, value...

    """

    ##############################################

    def __init__(self, table, **parameters):
        self._table = table
        self._parameters = parameters

    @property
    def table(self):
        """ Name of the model """
        return self._table

    ##############################################

    @property
    def names(self):
        """ Name of the model """
        return self._parameters.keys()

    ##############################################

    def __repr__(self):
        return 'Data {}'.format(Statement.kwargs_to_python(**self._parameters))

    ##############################################

    def to_python(self, netlist_name):
        kwargs = "{{{}}}".format(", ".join(["{} = ({})".format(param, ", ".join(values))
                                            for param, values in self._parameters.items]))
        return '{}.data({}, {})'.format(netlist_name, self._table, kwargs) + os.linesep

    ##############################################

    def build(self, circuit):
        circuit.data(self._table, self._parameters)


class IncludeStatement(Statement):
    """ This class implements a include definition. """

    ##############################################

    def __init__(self, parent, filename):
        self._include = filename
        root, _ = os.path.split(parent.path)
        file_name = os.path.abspath(os.path.join(root,
                                                 self._include.replace('"', '')))
        try:
            self._contents = SpiceParser(path=file_name)
        except Exception as e:
            raise FileNotFoundError("{}: ".format(parent.path) + str(e)) from e

    ##############################################

    def __str__(self):
        return self._include

    ##############################################

    def __repr__(self):
        return 'Include {}'.format(self._include)

    ##############################################

    def to_python(self, netlist_name):
        return '{}.include({})'.format(netlist_name, self._include) + os.linesep

    def contents(self):
        return self._contents


class ModelStatement(Statement):
    """ This class implements a model definition.

    Spice syntax::

        .model mname type (pname1=pval1 pname2=pval2)

    """

    ##############################################

    def __init__(self, name, device, **parameters):
        self._name = name
        self._model_type = device
        self._parameters = parameters

    ##############################################

    @property
    def name(self):
        """ Name of the model """
        return self._name

    ##############################################

    def __repr__(self):
        return 'Model {} {} {}'.format(self._name, self._model_type, self._parameters)

    ##############################################

    def to_python(self, netlist_name):
        args = self.values_to_python((self._name, self._model_type))
        kwargs = self.kwargs_to_python(self._parameters)
        return '{}.model({})'.format(netlist_name, self.join_args(args + kwargs)) + os.linesep

    ##############################################

    def build(self, circuit):
        return circuit.model(self._name, self._model_type, **self._parameters)


####################################################################################################

class ParamStatement(Statement):
    """ This class implements a param definition.

    Spice syntax::

        .param name=expr

    """

    ##############################################

    def __init__(self, **parameters):
        self._parameters = parameters

    ##############################################

    @property
    def names(self):
        """ Name of the model """
        return self._parameters.keys()

    ##############################################

    def __repr__(self):
        return 'Param {}'.format(Statement.kwargs_to_python(**self._parameters))

    ##############################################

    def to_python(self, netlist_name):
        args = self.values_to_python((self._name, self._value))
        return '{}.param({})'.format(netlist_name, self.join_args(args)) + os.linesep

    ##############################################

    def build(self, circuit):
        for key, value in self._parameters.items():
            circuit.parameter(key, value)


class ElementStatement(Statement):
    """ This class implements an element definition.

    "{ expression }" are allowed in device line.

    """

    _logger = _module_logger.getChild('Element')

    ##############################################

    def __init__(self, statement, name, *nodes, **params):
        self._statement = statement
        self._prefix = name[0]
        self._name = name[1:]
        self._nodes = nodes
        self._params = params

    ##############################################

    @property
    def name(self):
        """ Name of the element """
        return self._name

    ##############################################

    def __repr__(self):
        return 'Element {0._prefix} {0._name} {0._nodes} {0._params}'.format(self)

    ##############################################

    def translate_ground_node(self, ground):

        nodes = []
        for idx, node in enumerate(self._nodes):
            if str(node) == str(ground):
                self._node[idx] = 0

        return nodes

    ##############################################

    def to_python(self, netlist_name, ground=0):

        args = self.translate_ground_node(ground)
        args = self.values_to_python(args)
        kwargs = self.kwargs_to_python(self._dict_parameters)
        return '{}.{}({})'.format(netlist_name,
                                  self._prefix, self.join_args(args + kwargs)) + os.linesep

    def build(self, circuit, ground=0):
        return self._statement(circuit, self._name, *self._nodes, **self._params)


class LibraryStatement(Statement):
    """ This class implements a library definition.

    Spice syntax::

        .LIB entry
        .ENDL [entry]

    """

    ##############################################

    def __init__(self, entry):
        self._entry = entry

        self._statements = []
        self._subcircuits = []
        self._models = []
        self._params = []

    ##############################################

    @property
    def entry(self):
        """ Name of the sub-circuit. """
        return self._entry

    @property
    def models(self):
        """ Models of the sub-circuit. """
        return self._models

    @property
    def params(self):
        """ Params of the sub-circuit. """
        return self._params

    @property
    def subcircuits(self):
        """ Subcircuits of the sub-circuit. """
        return self._subcircuits

    ##############################################

    def __repr__(self):
        text = 'LIB {}'.format(self._entry) + os.linesep
        text += os.linesep.join([repr(model) for model in self._models]) + os.linesep
        text += os.linesep.join([repr(subcircuit) for subcircuit in self._subcircuits]) + os.linesep
        text += os.linesep.join(['  ' + repr(statement) for statement in self._statements])
        return text

    ##############################################

    def __iter__(self):
        """ Return an iterator on the statements. """
        return iter(self._models + self._subcircuits + self._statements)

    ##############################################

    def append(self, statement):
        """ Append a statement to the statement's list. """
        self._statements.append(statement)

    def appendModel(self, statement):

        """ Append a model to the statement's list. """

        self._models.append(statement)

    def appendParam(self, statement):

        """ Append a param to the statement's list. """

        self._params.append(statement)

    def appendSubCircuit(self, statement):

        """ Append a model to the statement's list. """

        self._subcircuits.append(statement)

    ##############################################

    def to_python(self, ground=0):

        lib_name = 'lib_' + self._entry
        source_code = ''
        source_code += '{} = Lib({})'.format(lib_name, self._entry) + os.linesep
        source_code += SpiceParser.netlist_to_python(lib_name, self, ground)
        return source_code


class LibCallStatement(Statement):
    """ This class implements a library call statement.

    Spice syntax::

        .lib library entry

    """

    ##############################################

    def __init__(self, library, entry):
        self._library = library
        self._entry = entry

    ##############################################

    @property
    def name(self):
        """ Name of the library """
        return self._library

    ##############################################

    @property
    def entry(self):
        """ Entry in the library """
        return self._entry

    ##############################################

    def __repr__(self):
        return 'Library {} {}'.format(self._library, self._entry)

    ##############################################

    def to_python(self, netlist_name):
        args = self.values_to_python((self._name, self._model_type))
        kwargs = self.kwargs_to_python(self._parameters)
        return '{}.include({}, {})'.format(netlist_name, self._library, self._entry) + os.linesep

    ##############################################

    def build(self, circuit, libraries):
        library = libraries[self._entry]
        for statement in library._params:
            statement.build(circuit)
        for statement in library._models:
            statement.build(circuit)
        for statement in library._subcircuits:
            statement.build(circuit, parent=circuit)
        return circuit


class SubCircuitStatement(Statement):
    """ This class implements a sub-circuit definition.

    Spice syntax::

        .SUBCKT name node1 ... param1=value1 ...

    """

    ##############################################

    def __init__(self, name, *nodes, **params):

        self._name = name
        self._nodes = nodes
        self._parameters = params

        self._statements = []
        self._subcircuits = []
        self._models = []
        self._required_subcircuits = set()
        self._required_models = set()
        self._params = []

    ##############################################

    @property
    def name(self):
        """ Name of the sub-circuit. """
        return self._name

    @property
    def nodes(self):
        """ Nodes of the sub-circuit. """
        return self._nodes

    @property
    def models(self):
        """ Models of the sub-circuit. """
        return self._models

    @property
    def params(self):
        """ Params of the sub-circuit. """
        return self._params

    @property
    def subcircuits(self):
        """ Subcircuits of the sub-circuit. """
        return self._subcircuits

    ##############################################

    def __repr__(self):
        if self._parameters:
            text = 'SubCircuit {} {} Params: {}'.format(self._name, self._nodes, self._parameters) + os.linesep
        else:
            text = 'SubCircuit {} {}'.format(self._name, self._nodes) + os.linesep
        text += os.linesep.join([repr(model) for model in self._models]) + os.linesep
        text += os.linesep.join([repr(subcircuit) for subcircuit in self._subcircuits]) + os.linesep
        text += os.linesep.join(['  ' + repr(statement) for statement in self._statements])
        return text

    ##############################################

    def __iter__(self):
        """ Return an iterator on the statements. """
        return iter(self._models + self._subcircuits + self._statements)

    ##############################################

    def append(self, statement):
        """ Append a statement to the statement's list. """
        self._statements.append(statement)

    def appendModel(self, statement):

        """ Append a model to the statement's list. """

        self._models.append(statement)

    def appendParam(self, statement):

        """ Append a param to the statement's list. """

        self._params.append(statement)

    def appendSubCircuit(self, statement):

        """ Append a model to the statement's list. """

        self._subcircuits.append(statement)

    ##############################################

    def to_python(self, ground=0):

        subcircuit_name = 'subcircuit_' + self._name
        args = self.values_to_python([subcircuit_name] + self._nodes)
        source_code = ''
        source_code += '{} = SubCircuit({})'.format(subcircuit_name, self.join_args(args)) + os.linesep
        source_code += SpiceParser.netlist_to_python(subcircuit_name, self, ground)
        return source_code

    ##############################################

    def build(self, ground=0, parent=None):
        subcircuit = SubCircuit(self._name, *self._nodes, **self._parameters)
        subcircuit.parent = parent
        for statement in self._params:
            statement.build(subcircuit)
        for statement in self._models:
            model = statement.build(subcircuit)
        for statement in self._subcircuits:
            subckt = statement.build(ground, parent=subcircuit)  # Fixme: ok ???
            subcircuit.subcircuit(subckt)
        for statement in self._statements:
            if isinstance(statement, ElementStatement):
                statement.build(subcircuit, ground)
        return subcircuit


class CircuitStatement(Statement):
    """ This class implements a circuit definition.

    Spice syntax::

        Title ...

    """

    ##############################################

    def __init__(self, title, path):
        if path is not None:
            self._path = str(path)
        else:
            self._path = os.getcwd()

        self._title = str(title)

        self._library_calls = []
        self._statements = []
        self._libraries = {}
        self._subcircuits = []
        self._models = []
        self._required_subcircuits = set()
        self._required_models = set()
        self._params = []
        self._data = {}

    ##############################################

    @property
    def path(self):
        """ Path of the circuit. """
        return self._path

    @property
    def title(self):
        """ Title of the circuit. """
        return self._title

    @property
    def name(self):
        """ Name of the circuit. """
        return self._title

    @property
    def libraries(self):
        """ Libraries. """
        return self._libraries

    @property
    def models(self):
        """ Models of the circuit. """
        return self._models

    @property
    def subcircuits(self):
        """ Subcircuits of the circuit. """
        return self._subcircuits

    @property
    def params(self):
        """ Parameters of the circuit. """
        return self._params

    ##############################################

    def __repr__(self):

        text = 'Library {}'.format(self._title) + os.linesep
        text += os.linesep.join([repr(library) for library in self._libraries]) + os.linesep
        text += os.linesep.join([repr(model) for model in self._models]) + os.linesep
        text += os.linesep.join([repr(subcircuit) for subcircuit in self._subcircuits]) + os.linesep
        text += os.linesep.join(['  ' + repr(statement) for statement in self._statements])
        return text

    ##############################################

    def __iter__(self):

        """ Return an iterator on the statements. """

        return iter(self._libraries, self._models + self._subcircuits + self._statements)

    ##############################################

    def append(self, statement):

        """ Append a statement to the statement's list. """

        self._statements.append(statement)

    def appendData(self, statement):

        """ Append a model to the statement's list. """

        self._data[statement.table] = statement

    def appendLibrary(self, statement):

        """ Append a library to the statement's list. """

        self._libraries[statement.entry] = statement

    def appendLibraryCall(self, statement):

        """ Append a library to the statement's list. """

        self._library_calls.append(statement)

    def appendModel(self, statement):

        """ Append a model to the statement's list. """

        self._models.append(statement)

    def appendParam(self, statement):

        """ Append a param to the statement's list. """

        self._params.append(statement)

    def appendSubCircuit(self, statement):

        """ Append a model to the statement's list. """

        self._subcircuits.append(statement)

    ##############################################

    def to_python(self, ground=0):

        circuit_title = self._title
        source_code = ''
        source_code += '{} = Circuit({})'.format(circuit_title) + os.linesep
        source_code += SpiceParser.netlist_to_python(circuit_title, self, ground)
        return source_code

    ##############################################

    def build(self, ground=0):
        circuit = Circuit(self._title)
        for statement in self._library_calls:
            statement.build(circuit, self._libraries)
        for statement in self._params:
            statement.build(circuit)
        for statement in self._models:
            statement.build(circuit)
        for statement in self._subcircuits:
            subckt = statement.build(ground, parent=circuit)  # Fixme: ok ???
            circuit.subcircuit(subckt)
        for statement in self._statements:
            if isinstance(statement, ElementStatement):
                statement.build(circuit, ground)
        return circuit


####################################################################################################

class SpiceModelWalker(NodeWalker):

    def __init__(self, filename):
        self._path = filename
        self._root = None
        self._present = None
        self._context = []
        self._scales = (Tera(), Giga(), Mega(), Kilo(), Milli(), Micro(), Nano(), Pico(), Femto())
        self._suffix = dict([(normalize("NFKD", unit.prefix).lower(), PrefixedUnit(power=unit))
                             for unit in self._scales] +
                            [(normalize("NFKD", unit.spice_prefix).lower(), PrefixedUnit(power=unit))
                             for unit in self._scales
                             if unit.spice_prefix is not None]
                            )
        self._functions = {"abs": Abs,
                           "agauss": AGauss,
                           "acos": ACos,
                           "acosh": ACosh,
                           "arctan": ATan,
                           "asin": ASin,
                           "asinh": ASinh,
                           "atan": ATan,
                           "atan2": ATan2,
                           "atanh": ATanh,
                           "aunif": AUnif,
                           "ceil": Ceil,
                           "cos": Cos,
                           "cosh": Cosh,
                           "db": Db,
                           "ddt": Ddt,
                           "ddx": Ddx,
                           "exp": Exp,
                           "ln": Ln,
                           "log": Ln,
                           "log10": Log10,
                           "floor": Floor,
                           "gauss": Gauss,
                           "i": I,
                           "if": If,
                           "img": Img,
                           "int": Int,
                           "limit": Limit,
                           "m": M,
                           "max": Max,
                           "min": Min,
                           "nint": NInt,
                           "ph": Ph,
                           "pow": Pow,
                           "pwr": Pow,
                           "pwrs": Pwrs,
                           "r": Re,
                           "rand": Rand,
                           "re": Re,
                           "sdt": Sdt,
                           "sgn": Sgn,
                           "sign": Sign,
                           "sin": Sin,
                           "sinh": Sinh,
                           "sqrt": Sqrt,
                           "stp": Stp,
                           "tan": Tan,
                           "tanh": Tanh,
                           "unif": Unif,
                           "uramp": URamp,
                           "v": V
                           }
        self._relational = {
            "<": LT,
            "<=": LE,
            "==": EQ,
            "!=": NE,
            ">=": GE,
            ">": GT
        }

    def walk_Circuit(self, node):
        if self._root is None:
            self._root = CircuitStatement(
                self.walk(node.title),
                self._path
            )
            self._present = self._root
        else:
            raise ValueError('Circuit already created: {}'.format(self._path))

        self.walk(node.lines)
        if len(self._context) != 0:
            raise ParseError("Not closed hierarchy: {}".format(self._path))
        return self._root

    def walk_BJT(self, node):
        device = self.walk(node.dev)
        args = self.walk(node.args)
        l_args = len(args)
        kwargs = {}
        collector = self.walk(node.collector)
        base = self.walk(node.base)
        emitter = self.walk(node.emitter)
        nodes = [
            collector,
            base,
            emitter
        ]
        substrate = None
        if node.substrate is not None:
            substrate = node.substrate
            nodes.append(substrate)
        area = None
        if node.area is not None:
            area = self.walk(node.area)
        if l_args == 0:
            raise ValueError("The device {} has no model".format(node.dev))
        elif l_args == 1:
            model_name = args[0]
        elif l_args == 2:
            if area is None:
                try:
                    area = SpiceModelWalker._to_number(args[1])
                    kwargs["area"] = area
                    model_name = args[0]
                except ValueError:
                    pass
            if area is None:
                thermal = args[0]
                nodes.append(thermal)
                model_name = args[1]
        elif l_args == 3:
            if area is None:
                try:
                    area = SpiceModelWalker._to_number(args[2])
                    kwargs["area"] = area
                    model_name = args[1]
                    thermal = args[0]
                    nodes.append(thermal)
                except ValueError:
                    pass
            if area is None and substrate is None:
                substrate = args[0]
                nodes.append(substrate)
                thermal = args[1]
                nodes.append(thermal)
                model_name = args[2]
            else:
                raise ValueError("Present device not compatible with BJT definition: {}".format(node.dev))
        else:
            raise ValueError("Present device not compatible with BJT definition: {}".format(node.dev))

        if node.parameters is not None:
            parameters = self.walk(node.parameters)
            kwargs.update(parameters)

        kwargs["model"] = model_name
        self._present._required_models.add(model_name.lower())

        self._present.append(
            ElementStatement(
                BipolarJunctionTransistor,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_SubstrateNode(self, node):
        return node.substrate

    def walk_Capacitor(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.model is not None:
            model_name = self.walk(node.model)
            kwargs['model'] = model_name
            self._present._required_models.add(model_name.lower())
        value = None
        if node.value is not None:
            value = self.walk(node.value)
            kwargs['capacitance'] = value
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
            kwargs.update(parameters)
        if value is None:
            if 'c' in kwargs:
                value = kwargs.pop('c')
                kwargs['capacitance'] = value
            elif 'C' in kwargs:
                value = kwargs.pop('C')
                kwargs['capacitance'] = value


        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                Capacitor,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_CurrentControlledCurrentSource(self, node):
        device = self.walk(node.dev)
        if (node.controller is None and node.dev is None and
                node.gain is None):
            raise ValueError("Device {} not properly defined".format(node.dev))
        if node.controller is not None:
            controller = self.walk(node.controller)
            kwargs = {"I": controller}
        else:
            value = self.walk(node.gain)
            kwargs = {"I": I(device)*value}

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                BehavioralSource,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_CurrentControlledVoltageSource(self, node):
        device = self.walk(node.dev)
        if (node.controller is None and node.dev is None and
                node.gain is None):
            raise ValueError("Device {} not properly defined".format(node.dev))
        if node.controller is not None:
            controller = self.walk(node.controller)
            kwargs = {"V": controller}
        else:
            value = self.walk(node.transresistance)
            kwargs = {"V": I(device)*value}

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                BehavioralSource,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_CurrentSource(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.dc_value is not None:
            kwargs['dc_value'] = self.walk(node.dc_value)
        if node.ac_magnitude is not None:
            kwargs['ac_magnitude'] = self.walk(node.ac_magnitude)
        if node.ac_phase is not None:
            kwargs['ac_phase'] = self.walk(node.ac_phase)
        if node.transient is not None:
            kwargs['transient'] = self.walk(node.transient)

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                CurrentSource,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_Diode(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.model is None:
            raise ValueError("The device {} has no model".format(node.dev))
        else:
            model_name = self.walk(node.model)
            kwargs['model'] = model_name
            self._present._required_models.add(model_name.lower())
        if node.area is not None:
            area = self.walk(node.area)
            kwargs['area'] = area

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                Diode,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_Inductor(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.model is not None:
            model_name = self.walk(node.model)
            kwargs['model'] = model_name
            self._present._required_models.add(model_name.lower())
        value = None
        if node.value is not None:
            value = self.walk(node.value)
            kwargs['inductance'] = value
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
            kwargs.update(parameters)
        if value is None:
            if 'l' in kwargs:
                value = kwargs.pop('l')
                kwargs['inductance'] = value
            elif 'L' in kwargs:
                value = kwargs.pop('L')
                kwargs['inductance'] = value

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                Inductor,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_JFET(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.model is None:
            raise ValueError("The device {} has no model".format(node.dev))
        else:
            model_name = self.walk(node.model)
            kwargs["model"] = model_name
            self._present._required_models.add(model_name.lower())
        if node.area is not None:
            area = self.walk(node.area)
            kwargs["area"] = area
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
            kwargs.update(parameters)

        drain = self.walk(node.drain)
        gate = self.walk(node.gate)
        source = self.walk(node.source)
        nodes = [
            drain,
            gate,
            source
        ]
        self._present.append(
            ElementStatement(
                JunctionFieldEffectTransistor,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_MOSFET(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.model is None:
            raise ValueError("The device {} has no model".format(node.dev))
        else:
            model_name = self.walk(node.model)
            kwargs["model"] = model_name
            self._present._required_models.add(model_name.lower())
        if node.param is not None:
            if isinstance(node.param, list):
                # The separators are not taken into account
                for parameter in node.param:
                    if isinstance(parameter, list):
                        kwargs[parameter[0]] = self.walk(parameter[2][::2])
                    else:
                        kwargs.update(self.walk(parameter))
            else:
                kwargs.update(self.walk(node.param))
        drain = self.walk(node.drain)
        gate = self.walk(node.gate)
        source = self.walk(node.source)
        bulk = self.walk(node.bulk)
        nodes = [
            drain,
            gate,
            source,
            bulk
        ]
        self._present.append(
            ElementStatement(
                Mosfet,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_MutualInductor(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.model is not None:
            model_name = self.walk(node.model)
            kwargs['model'] = model_name
            self._present._required_models.add(model_name.lower())
        inductors = self.walk(node.inductor)
        if len(inductors) != 2:
            raise ParseError("Presently, only two inductors are allowed.")
        inductor1 = inductors[0]
        inductor2 = inductors[1]
        coupling_factor = self.walk(node.value)
        kwargs["inductor1"] = inductor1
        kwargs["inductor2"] = inductor2
        kwargs["coupling_factor"] = coupling_factor

        self._present.append(
            ElementStatement(
                CoupledInductor,
                device,
                **kwargs
            )
        )

    def walk_NonLinearDependentSource(self, node):
        device = self.walk(node.dev)
        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        expr = self.walk(node.expr)
        kwargs = {}
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
            kwargs.update(parameters)
        if node.magnitude == "V":
            kwargs["voltage_expression"] = expr
        else:
            kwargs["current_expression"] = expr

        self._present.append(
            ElementStatement(
                BehavioralSource,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_Resistor(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.model is not None:
            model_name = self.walk(node.model)
            kwargs['model'] = model_name
            self._present._required_models.add(model_name.lower())
        value = None
        if node.value is not None:
            value = self.walk(node.value)
            kwargs['resistance'] = value
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
            kwargs.update(parameters)
        if value is None:
            if 'r' in kwargs:
                value = kwargs.pop('r')
                kwargs['resistance'] = value
            elif 'R' in kwargs:
                value = kwargs.pop('R')
                kwargs['resistance'] = value

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                Resistor,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_Subcircuit(self, node):
        device = self.walk(node.dev)
        node_node = self.walk(node.node)
        if node.params is not None:
            subcircuit_name = node_node[-2]
            nodes = node_node[:-2]
        else:
            subcircuit_name = node_node[-1]
            nodes = node_node[:-1]
        kwargs = {}
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
            kwargs.update(parameters)
        self._present._required_subcircuits.add(subcircuit_name.lower())
        self._present.append(
            ElementStatement(
                SubCircuitElement,
                device,
                subcircuit_name,
                *nodes,
                **kwargs
            )
        )

    def walk_Switch(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.model is not None:
            model_name = self.walk(node.model)
            kwargs['model'] = model_name
            self._present._required_models.add(model_name.lower())
        if node.initial_state is not None:
            kwargs['initial_state'] = node.initial_state

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        if node.control_p is not None:
            if node.control_n is not None:
                control_p = self.walk(node.control_p)
                control_n = self.walk(node.control_n)
                nodes = (
                    positive,
                    negative,
                    control_p,
                    control_n
                )
            else:
                raise ValueError("Only one control node defined")
        else:
            if node.control_n is None:
                nodes = (
                    positive,
                    negative
                )
        self._present.append(
            ElementStatement(
                VoltageControlledSwitch,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_VoltageControlledCurrentSource(self, node):
        device = self.walk(node.dev)
        if (node.controller is None and node.control_positive is None and
                node.control_negative is None and node.transconductance is None):
            raise ValueError("Device {} not properly defined".format(node.dev))
        if node.controller is not None:
            controller = self.walk(node.controller)
            kwargs = {"I": controller}
        else:
            value = self.walk(node.transconductance)
            kwargs = {"I": V(node.control_positive, node.control_negative) * value}

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                BehavioralSource,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_VoltageControlledVoltageSource(self, node):
        device = self.walk(node.dev)
        if (node.controller is None and node.control_positive is None and
                node.control_negative is None and node.gain is None):
            raise ValueError("Device {} not properly defined".format(node.dev))
        if node.controller is not None:
            controller = self.walk(node.controller)
            kwargs = {"V": controller}
        else:
            value = self.walk(node.gain)
            kwargs = {"V": V(node.control_positive, node.control_negative) * value}

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                BehavioralSource,
                device,
                *nodes,
                **kwargs
            )
        )

    def walk_VoltageSource(self, node):
        device = self.walk(node.dev)
        kwargs = {}
        if node.dc_value is not None:
            kwargs['dc_value'] = self.walk(node.dc_value)
        if node.ac_magnitude is not None:
            kwargs['ac_magnitude'] = self.walk(node.ac_magnitude)
        if node.ac_phase is not None:
            kwargs['ac_phase'] = self.walk(node.ac_phase)
        if node.transient is not None:
            kwargs['transient'] = self.walk(node.transient)

        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        nodes = (
            positive,
            negative
        )
        self._present.append(
            ElementStatement(
                VoltageSource,
                device,
                *nodes,
                **kwargs
            )
        )


    def walk_ControlVoltagePoly(self, node):
        controllers = self.walk(node.value)
        positive = self.walk(node.positive)
        negative = self.walk(node.negative)
        if len(positive) < controllers or len(negative) < controllers:
            raise ValueError(
                "The number of control nodes is smaller than the expected controllers: {}".format(controllers))

        ctrl_pos = positive[:controllers]
        ctrl_neg = negative[:controllers]

        values = []
        if len(positive) > controllers:
            if isinstance(positive, list):
                values_pos = positive[controllers:]
            else:
                values_pos = [positive]
            if isinstance(negative, list):
                values_neg = negative[controllers:]
            else:
                values_neg = [negative]
            values += [SpiceModelWalker._to_number(val)
                       for pair in zip(values_pos, values_neg)
                       for val in pair]
        if node.coefficient:
            coefficients = self.walk(node.coefficient)
            if isinstance(coefficients, list):
                values.extend(coefficients)
            else:
                values.append(coefficients)
        result = ['v(%s,%s)' % nodes
                  for nodes in zip(ctrl_pos,
                                   ctrl_neg)]
        result += [str(value) for value in values]
        parameters = ' '.join(result)
        return '{ POLY (%d) %s }' % (controllers, parameters)

    def walk_ControlCurrentPoly(self, node):
        controllers = self.walk(node.value)
        if len(node.device) < controllers:
            raise ValueError(
                "The number of control nodes is smaller than the expected controllers: {}".format(controllers))

        ctrl_dev = node.device[:controllers]

        values = []
        if node.coefficient:
            coefficients = self.walk(node.coefficient)
            if isinstance(coefficients, list):
                values.extend(coefficients)
            else:
                values.append(coefficients)
        data = [self.walk(dev) for dev in ctrl_dev] + [str(value) for value in values]
        parameters = ' '.join(data)
        return '{ POLY (%d) %s }' % (controllers, parameters)

    def walk_ControlTable(self, node):
        return Table(self.walk(node.expr),
                     list(zip(self.walk(node.input),
                              self.walk(node.output))))

    def walk_ControlValue(self, node):
        return self.walk(node.expression)

    def walk_TransientSpecification(self, node):
        return self.walk(node.ast)

    def walk_TransientPulse(self, node):
        parameters = dict([(key, value)
                           for value, key in zip(self.walk(node.ast),
                                                 ("initial_value",
                                                  "pulsed_value",
                                                  "delay_time",
                                                  "rise_time",
                                                  "fall_time",
                                                  "pulse_width",
                                                  "period",
                                                  "phase"))])
        return PulseMixin, parameters

    def walk_PulseArguments(self, node):
        v1 = self.walk(node.v1)
        value = []
        if node.value is not None:
            value = self.walk(node.value)
        return [v1] + value

    def walk_TransientPWL(self, node):
        values = self.walk(node.ast)

        return PieceWiseLinearMixin, values

    def walk_PWLArguments(self, node):
        t = self.walk(node.t)
        value = self.walk(node.value)
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
        return (t, value), parameters

    def walk_PWLFileArguments(self, node):
        filename = self.walk(node.filename)
        parameters = {}
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
        return filename, parameters

    def walk_TransientSin(self, node):
        parameters = dict([(key, value)
                           for value, key in zip(self.walk(node.ast),
                                                 ("offset",
                                                  "amplitude",
                                                  "frequency",
                                                  "delay",
                                                  "damping_factor"))])
        return SinusoidalMixin, parameters

    def walk_SinArguments(self, node):
        v0 = self.walk(node.v0)
        va = self.walk(node.va)
        freq = self.walk(node.freq)
        value = []
        if node.value is not None:
            value = self.walk(node.value)
        if isinstance(value, list):
            return [v0, va, freq] + value
        else:
            return [v0, va, freq, value]

    def walk_TransientPat(self, node):
        parameters = dict([(key, value)
                           for value, key in zip(self.walk(node.ast),
                                                 ("high_value",
                                                  "low_value",
                                                  "delay_time",
                                                  "rise_time",
                                                  "fall_time",
                                                  "bit_period",
                                                  "bit_pattern",
                                                  "repeat"))])
        return PatternMixin, parameters

    def walk_PatArguments(self, node):
        vhi = self.walk(node.vhi)
        vlo = self.walk(node.vlo)
        td = self.walk(node.td)
        tr = self.walk(node.tr)
        tf = self.walk(node.tf)
        tsample = self.walk(node.tsample)
        data = self.walk(node.data)
        repeat = False
        if node.repeat is not None:
            repeat = (node.repeat == '1')
        return [vhi, vlo, td, tr, tf, tsample, data, repeat]

    def walk_ACCmd(self, node):
        return node.text

    def walk_DataCmd(self, node):
        table = node.table
        names = node.name
        values = self.walk(node.value)
        if len(values) % len(names) != 0:
            raise ValueError("The number of elements per parameter do not match (line: {})".format(node.line))
        parameters = dict([(name, [value for value in values[idx::len(names)]])
                           for idx, name in enumerate(names)])
        self._root.appendData(
            DataStatement(
                table,
                **parameters
            )
        )

    def walk_DCCmd(self, node):
        return node.text

    def walk_IncludeCmd(self, node):
        filename = self.walk(node.filename)
        self._present.append(
            IncludeStatement(
                self._root,
                filename
            )
        )

    def walk_ICCmd(self, node):
        return node.text

    def walk_ModelCmd(self, node):
        name = self.walk(node.name)
        device = node.type
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
        else:
            parameters = {}

        self._present.appendModel(
            ModelStatement(
                name,
                device,
                **parameters
            )
        )

    def walk_ModelName(self, node):
        return node.name

    def walk_ParamCmd(self, node):
        if node.parameters is not None:
            parameters = self.walk(node.parameters)
        else:
            parameters = {}

        self._present.appendParam(
            ParamStatement(**parameters)
        )

    def walk_LibCmd(self, node):
        if node.block is not None:
            self.walk(node.block)
        else:
            self.walk(node.call)

    def walk_LibBlock(self, node):
        entries = node.entry
        if len(entries) == 2:
            if entries[0] != entries[1]:
                raise NameError(
                    'Begin and end library entries differ: {} != {}'.format(*entries))
            entries = entries[0]
        library = LibraryStatement(entries)
        self._context.append(self._present)
        self._present = library
        self.walk(node.lines)
        tmp = self._context.pop()
        tmp.appendLibrary(self._present)
        self._present = tmp

    def walk_LibCall(self, node):
        entries = node.entry
        if len(entries) == 2:
            if entries[0] != entries[1]:
                raise NameError(
                    'Begin and end library entries differ: {} != {}'.format(*entries))
            entries = entries[0]
        filename = self.walk(node.filename)
        self._present.appendLibraryCall(
              LibCallStatement(filename, entries)
        )

    def walk_SimulatorCmd(self, node):
        return node.simulator

    def walk_SubcktCmd(self, node):
        name = self.walk(node.name)
        if isinstance(name, list) and len(name) == 2:
            if name[0] != name[1]:
                raise NameError(
                    'Begin and end library entries differ (file:{}, line:{}): {} != {}'.format(self._path, node.parseinfo.line,
                                                                                 *name))
            name = name[0]
        nodes = self.walk(node.node)
        parameters = None
        if node.parameters is not None:
            parameters = self.walk(node.parameters)

        if nodes is None:
            if parameters is None:
                subckt = SubCircuitStatement(name)
            else:
                subckt = SubCircuitStatement(name, **parameters)
        else:
            if parameters is None:
                subckt = SubCircuitStatement(name, *nodes)
            else:
                subckt = SubCircuitStatement(name, *nodes, **parameters)
        self._context.append(self._present)
        self._present = subckt
        self.walk(node.lines)
        tmp = self._context.pop()
        tmp.appendSubCircuit(self._present)
        self._present = tmp

    def walk_TitleCmd(self, node):
        if id(self._root) == id(self._present):
            self._root._title = self.walk(node.title)
        else:
            raise SyntaxError(".Title command can only be used in the root circuit.")
        return self._root

    def walk_Lines(self, node):
        self.walk(node.ast)

    def walk_CircuitLine(self, node):
        self.walk(node.ast)

    def walk_NetlistLines(self, node):
        self.walk(node.ast)

    def walk_NetlistLine(self, node):
        self.walk(node.ast)

    def walk_Parameters(self, node):
        if isinstance(node.ast, list):
            result = {}
            # The separators are not taken into account
            for parameter in self.walk(node.ast[::2]):
                result.update(parameter)
        else:
            result = self.walk(node.ast)
        return result

    def walk_Parameter(self, node):
        value = self.walk(node.value)
        return {node.name: value}

    def walk_GenericExpression(self, node):
        if node.value is None:
            return self.walk(node.braced)
        else:
            return self.walk(node.value)

    def walk_BracedExpression(self, node):
        return self.walk(node.ast)

    def walk_Ternary(self, node):
        t = self.walk(node.t)
        x = self.walk(node.x)
        y = self.walk(node.y)
        return self._functions["if"](t, x, y)

    def walk_Conditional(self, node):
        return self.walk(node.expr)

    def walk_And(self, node):
        left = self.walk(node.left)
        if node.right is None:
            return left
        else:
            right = node.right
            return And(left, right)

    def walk_Not(self, node):
        operator = self.walk(node.operator)
        if node.op is None:
            return operator
        else:
            return Not(operator)

    def walk_Or(self, node):
        left = self.walk(node.left)
        if node.right is None:
            return left
        else:
            right = node.right
            return Or(left, right)

    def walk_Xor(self, node):
        left = self.walk(node.left)
        if node.right is None:
            return left
        else:
            right = node.right
            return Xor(left, right)

    def walk_Relational(self, node):
        if node.factor is None:
            left = self.walk(node.left)
            right = self.walk(node.right)
            return self._relational[node.op](left, right)
        else:
            return self.walk(node.factor)

    def walk_ConditionalFactor(self, node):
        if node.boolean is None:
            self.walk(node.expr)
        else:
            return node.boolean.lower == "true"

    def walk_Expression(self, node):
        if node.term is None:
            return self.walk(node.ternary)
        else:
            return self.walk(node.term)

    def walk_Functional(self, node):
        return self.walk(node.ast)

    def walk_Functions(self, node):
        l_func = node.func.lower()
        function = self._functions[l_func]
        if function.nargs == 0:
            return function()
        elif l_func == 'v':
            nodes = self.walk(node.node)
            if isinstance(nodes, list):
                return function(*nodes)
            else:
                return function(nodes)
        elif l_func == 'i':
            device = self.walk(node.device)
            return function(device)
        elif function.nargs == 1:
            x = self.walk(node.x)
            return function(x)
        elif l_func == 'limit':
            x = self.walk(node.x)
            y = self.walk(node.y)
            z = self.walk(node.z)
            return function(x, y, z)
        elif l_func == 'atan2':
            x = self.walk(node.x)
            y = self.walk(node.y)
            return function(y, x)
        elif l_func in ('aunif', 'unif'):
            mu = self.walk(node.mu)
            alpha = self.walk(node.alpha)
            return function(mu, alpha)
        elif l_func == "ddx":
            f = node.f
            x = self.walk(node.x)
            return function(Symbol(f), x)
        elif function.nargs == 2:
            x = self.walk(node.x)
            y = self.walk(node.y)
            return function(x, y)
        elif l_func == "if":
            t = self.walk(node.t)
            x = self.walk(node.x)
            y = self.walk(node.y)
            return function(t, x, y)
        elif l_func == "limit":
            x = self.walk(node.x)
            y = self.walk(node.y)
            z = self.walk(node.z)
            return function(x, y, z)
        elif l_func in ('agauss', 'gauss'):
            mu = self.walk(node.mu)
            alpha = self.walk(node.alpha)
            n = self.walk(node.n)
            return function(mu, alpha, n)
        else:
            raise NotImplementedError("Function: {}".format(node.func));

    def walk_Term(self, node):
        return self.walk(node.ast)

    def walk_AddSub(self, node):
        lhs = self.walk(node.left)
        if node.right is not None:
            rhs = self.walk(node.right)
            if node.op == "+":
                return Add(lhs, rhs)
            else:
                return Sub(lhs, rhs)
        else:
            return lhs

    def walk_ProdDivMod(self, node):
        lhs = self.walk(node.left)
        if node.right is not None:
            rhs = self.walk(node.right)
            if node.op == "*":
                return Mul(lhs, rhs)
            elif node.op == "/":
                return Div(lhs, rhs)
            else:
                return Mod(lhs, rhs)
        else:
            return lhs

    def walk_Sign(self, node):
        operator = self.walk(node.operator)
        if node.op is not None:
            if node.op == "-":
                return Neg(operator)
            else:
                return Pos(operator)
        else:
            return operator

    def walk_Exponential(self, node):
        lhs = self.walk(node.left)
        if node.right is not None:
            rhs = self.walk(node.right)
            return Power(lhs, rhs)
        else:
            return lhs

    def walk_Factor(self, node):
        return self.walk(node.ast)

    def walk_Variable(self, node):
        if node.variable is None:
            return self.walk(node.factor)
        else:
            return Symbol(node.variable)

    def walk_Value(self, node):
        real = 0.0
        if node.real is not None:
            real = self.walk(node.real)
        imag = None
        if node.imag is not None:
            imag = self.walk(node.imag)
        if imag is None:
            return SpiceModelWalker._to_number(real)
        else:
            return complex(float(real), float(imag))

    def walk_ImagValue(self, node):
        return self.walk(node.value)

    def walk_RealValue(self, node):
        return self.walk(node.value)

    def walk_NumberScale(self, node):
        value = self.walk(node.value)
        scale = node.scale
        if scale is not None:
            scale = normalize("NFKD", scale).lower()
            result = UnitValue(self._suffix[scale], value)
        else:
            result = UnitValue(PrefixedUnit(ZeroPower()), value)
        return result

    def walk_Float(self, node):
        value = SpiceModelWalker._to_number(node.ast)
        return value

    def walk_Int(self, node):
        value = int(node.ast)
        return value

    def walk_Comment(self, node):
        # TODO implement comments on devices
        return

    def walk_Separator(self, node):
        if node.comment is not None:
            return self.walk(node.comment)

    def walk_Device(self, node):
        # Conversion of controlled devices to the B device names
        if node.ast[0] in ("E", "F", "G", "H"):
            return "B" + node.ast
        else:
            return node.ast

    def walk_Command(self, node):
        return self.walk(node.ast)

    def walk_NetlistCmds(self, node):
        return self.walk(node.ast)

    def walk_TableFile(self, node):
        filename = self.walk(node.filename)
        return TableFile(filename)

    def walk_NetNode(self, node):
        return node.node

    def walk_Filename(self, node):
        return node.ast

    def walk_BinaryPattern(self, node):
        return ''.join(node.pattern)

    def walk_list(self, node):
        return [self.walk(element) for element in node]

    def walk_closure(self, node):
        return ''.join(node)

    def walk_object(self, node):
        raise ParseError("No walker defined for the node: {}".format(node))

    @staticmethod
    def _to_number(value):
        if isinstance(value, UnitValue):
            newValue = int(value)
            if value == newValue:
                return value
            else:
                return float(value)
        try:
            return int(value)
        except ValueError:
            return float(value)

class SpiceParser:
    """ This class parse a Spice netlist file and build a syntax tree.

    Public Attributes:

      :attr:`circuit`

      :attr:`models`

      :attr:`subcircuits`

    """

    _logger = _module_logger.getChild('SpiceParser')

    ##############################################

    def __init__(self, path=None, source=None, library=False):
        # Fixme: empty source

        self._path = path
        self._root = None
        self._present = None
        self._context = []

        if path is not None:
            with open(str(path), 'rb') as f:
                raw_code = f.read().decode('utf-8')
        elif source is not None:
            raw_code = source
        else:
            raise ValueError("No path or source")

        self._parser = parser(whitespace='', semantics=SpiceModelBuilderSemantics())

        try:
            self._model = self._parser.parse(raw_code)
        except Exception as e:
            if path is not None:
                raise ParseError("{}: ".format(path) + str(e)) from e
            else:
                raise ParseError(str(e)) from e

        if path is None:
            self._path = os.getcwd()
        self._walker = SpiceModelWalker(self._path)
        self._circuit = self._walker.walk(self._model)
        if library:
            self._circuit._required_models = {model.name.lower()
                                              for model in self._circuit._models}
            self._circuit._required_subcircuits = {subckt.name.lower()
                                                   for subckt in self._circuit._subcircuits}
        try:
            SpiceParser._check_models(self._circuit)
            SpiceParser._sort_subcircuits(self._circuit)
        except Exception as e:
            raise ParseError("{}: ".format(self._path) + str(e)) from e

    @staticmethod
    def _regenerate():
        from PySpice.Spice import __file__ as spice_file
        location = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(spice_file)))
        grammar_file = os.path.join(location, "spicegrammar.ebnf")
        with open(grammar_file, "r") as grammar_ifile:
            grammar = grammar_ifile.read();
        with open(grammar_file, "w") as grammar_ofile:
            model = compile(str(grammar))
            grammar_ofile.write(str(model))
        python_file = os.path.join(location, "SpiceGrammar.py")
        python_grammar = to_python_sourcecode(grammar)
        with open(python_file, 'w') as grammar_ofile:
            grammar_ofile.write(python_grammar)
        python_model = to_python_model(grammar)
        model_file = os.path.join(location, "SpiceModel.py")
        with open(model_file, 'w') as model_ofile:
            model_ofile.write(python_model)

    @staticmethod
    def _check_models(circuit, available_models=set()):
        p_available_models = {model.lower() for model in available_models}
        p_available_models.update([model.name.lower() for model in circuit._models])
        for subcircuit in circuit._subcircuits:
            SpiceParser._check_models(subcircuit, p_available_models)
        for model in circuit._required_models:
            if model not in p_available_models:
                raise ValueError("Model (%s) not available in (%s)" % (model, circuit.name))

    @staticmethod
    def _sort_subcircuits(circuit, available_subcircuits=set()):
        p_available_subcircuits = {subckt.lower() for subckt in available_subcircuits}
        names = [subcircuit.name.lower() for subcircuit in circuit._subcircuits]
        p_available_subcircuits.update(names)
        dependencies = dict()
        for subcircuit in circuit._subcircuits:
            required = SpiceParser._sort_subcircuits(subcircuit, p_available_subcircuits)
            dependencies[subcircuit] = required
        for subcircuit in circuit._required_subcircuits:
            if subcircuit not in p_available_subcircuits:
                raise ValueError("Subcircuit (%s) not available in (%s)" % (subcircuit, circuit.name))
        items = sorted(dependencies.items(), key=lambda item: len(item[1]))
        result = list()
        result_names = list()
        previous = len(items) + 1
        while 0 < len(items) < previous:
            previous = len(items)
            remove = list()
            for item in items:
                subckt, depends = item
                for name in depends:
                    if name not in result_names:
                        break
                else:
                    result.append(subckt)
                    result_names.append(subckt.name.lower())
                    remove.append(item)
            for item in remove:
                items.remove(item)
        if len(items) > 0:
            raise ValueError("Crossed dependencies (%s)" % [(key.name, value) for key, value in items])
        circuit._subcircuits = result
        return circuit._required_subcircuits - set(names)


    @property
    def circuit(self):
        """ Circuit statements. """
        return self._circuit

    @property
    def models(self):
        """ Models of the sub-circuit. """
        return self._circuit.models

    @property
    def subcircuits(self):
        """ Subcircuits of the sub-circuit. """
        return self._circuit.subcircuits

    @property
    def parameters(self):
        """ Subcircuits of the sub-circuit. """
        return self._circuit.params

    ##############################################

    def is_only_subcircuit(self):
        return bool(not self._circuit and self.subcircuits)

    ##############################################

    def is_only_model(self):
        return bool(not self.circuit and not self.subcircuits and self.models)

    ##############################################

    @staticmethod
    def _build_circuit(circuit, statements, ground):

        for statement in statements:
            if isinstance(statement, IncludeStatement):
                circuit.include(str(statement))

        for statement in statements:
            if isinstance(statement, ElementStatement):
                statement.build(circuit, ground)
            elif isinstance(statement, ModelStatement):
                statement.build(circuit)
            elif isinstance(statement, SubCircuitStatement):
                subcircuit = statement.build(ground)  # Fixme: ok ???
                circuit.subcircuit(subcircuit)

    ##############################################

    def build_circuit(self, ground=0):

        """Build a :class:`Circuit` instance.

        Use the *ground* parameter to specify the node which must be translated to 0 (SPICE ground node).

        """

        # circuit = Circuit(str(self._title))
        circuit = self._circuit.build(str(ground))
        return circuit

    ##############################################

    @staticmethod
    def netlist_to_python(netlist_name, statements, ground=0):

        source_code = ''
        for statement in statements:
            if isinstance(statement, ElementStatement):
                source_code += statement.to_python(netlist_name, ground)
            elif isinstance(statement, LibraryStatement):
                source_code += statement.to_python(netlist_name)
            elif isinstance(statement, ModelStatement):
                source_code += statement.to_python(netlist_name)
            elif isinstance(statement, SubCircuitStatement):
                source_code += statement.to_python(netlist_name)
            elif isinstance(statement, IncludeStatement):
                source_code += statement.to_python(netlist_name)
        return source_code

    ##############################################

    def to_python_code(self, ground=0):

        ground = str(ground)

        source_code = ''

        if self.circuit:
            source_code += "circuit = Circuit('{}')".format(self._title) + os.linesep
        source_code += self.netlist_to_python('circuit', self._statements, ground)

        return source_code
