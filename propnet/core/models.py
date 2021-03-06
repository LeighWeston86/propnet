"""
Module containing classes and methods for Model functionality in Propnet code.
"""

# typing information, for type hinting only
from typing import *

import math

from abc import ABCMeta, abstractmethod
from functools import wraps
from os.path import dirname, join, isfile
from hashlib import sha256

from ruamel.yaml import safe_load
from monty.serialization import loadfn

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr

from propnet.symbols import DEFAULT_SYMBOL_TYPES
from propnet import logger
from propnet import ureg

# TODO: add pint integration
# TODO: decide on interface for conditions, assumptions etc.
# TODO: decide on interface for multiple-material models.


def load_metadata(path):
    """
    Loads the .yaml file at the given path, returning a dictionary of .yaml contents.
    Custom model data at the end of the .yaml file is loaded in under the key "description".

    Args:
        path (str): valid file path to a .yaml file to be loaded.
    Returns:
        (dict<str,id>) representation of .yaml contents.
    """
    with open(path, 'r') as f:
        metadata = f.read()

    metadata = metadata.split('---')

    markdown = metadata[2]
    metadata = safe_load(metadata[1])
    metadata['description'] = markdown

    return metadata


class AbstractModel(metaclass=ABCMeta):
    """
    Baseclass for all models appearing in Propnet.

    Class contains a pointer to a metadata dictionary that stores all associated information about the model. Accessor
    methods are provided for accessing individual components of the dictionary. In general this dictionary should
    contain the following:
        (str) title -> (str) human-readable title for the model
        (str) tags -> (list<str>) list of categories applicable to the model.
        (str) references -> (list<str>) list of informational links explaining / supporting the model
        (str) symbol_mapping -> (dict<str,str>) keys are symbols used in equations of the model,
                                                values are SymbolType enum values (SymbolType.name field)
        (str) connections -> (list<dict<str,list<str>>>)
                                                Forms the list of outputs that can be generated from different sets of
                                                inputs. The outer list contains dictionaries. These dictionaries contain
                                                two keys: "inputs" and "outputs". Each key maps to a list of symbol
                                                strings that serve as the list of input / output property types required
                                                for evaluation by the model.
        (str) equations -> (list<str>) OPTIONAL, set of equations that establish the model.
                                       Evaluate method may be overridden in lieu of providing equations.
        (str) description -> (str) markdown-formatted text further describing / explaining the model.

    The following methods may be overridden for custom model behavior:
        constraints () -> dict<str,lambda(Symbol)->bool>
            Returns a dictionary mapping symbol to a lambda function that takes in a Symbol object and returns a bool
            indicating whether that Symbol meets all necessary conditions for validity.
        plug_in (dict<str,id>) -> dict<str,id>
            Given a dictionary specifying a value for a set of input symbols, returns the predicted value of the model
            for those inputs.

    Thus, in full generality, a model requires a .yaml file to specify appropriate parameters along with a .py file to
    specify any method overrides. Each model thus corresponds to two files with the same name, and an equivalently-named
    class in the .py file inheriting from AbstractModel. While this class is termed 'abstract', it contains no pure
    virtual methods (borrowing terms from C++) -- instead abstract is used to force the user to subclass.

    At runtime, all models' associated .py files are loaded in and a class object is created for each Model. These
    class objects' __init__ methods must be called to produce a Model object via instantiation. Upon instantiation,
    associated metadata for the models is loaded on demand (lazy loading) and the .yaml file metadata is read in only
    at this time. Such instantiation is performed automatically in

    Attributes:
        _metadata (dict<str,id>): stores the .yaml dictionary contents specified upon instantiation.
        unit_mapping (dict<str,Pint.unit>): mapping from symbols used in the model to their corresponding units.
    """

    def __init__(self, metadata=None, symbol_types=None):
        """
        Constructs a Model object with the provided metadata.

        If the metadata is None, it attempts to load in the
        appropriate .yaml file at this time.
        Such a .yaml file must have a name equal to the class name.

        Args:
            metadata (dict<str,id>): metadata defining the model.
        """

        symbol_types = symbol_types or DEFAULT_SYMBOL_TYPES

        if not metadata:
            try:
                # try loading from local file, see /models/ for examples
                path = '{}/../models/{}.yaml'.format(dirname(__file__), self.__class__.__name__)
                metadata = load_metadata(path)
            except Exception as e:
                print(e)
                metadata = {}

        self._metadata = metadata

        # retrieve units for each symbol
        self.unit_mapping = {}
        for symbol, name in self.symbol_mapping.items():
            try:
                self.unit_mapping[symbol] = symbol_types[name].units
            except Exception as e:
                raise ValueError('Please check your property names in your symbol mapping, '
                                 'for property {} and model {}, are they all valid? '
                                 'Exception: {}'
                                 .format(name, self.__class__.__name__, e))

    # constraint_symbols, meets_constraints, plug_in, and evaluate methods are optional overrides in extending classes
    @property
    def constraint_symbols(self):
        """
        Returns a set of symbols.
        These symbols are those whose value needs to be evaluated to determine if the model can be evaluated under the
        current conditions.
        Returns: ({str})
        """
        return []

    def check_constraints(self, constraint_inputs):
        """
        Returns a dictionary mapping symbol to a lambda function that takes in a Symbol object and returns a bool
        indicating whether that Symbol meets all necessary conditions for validity.

        Args:
            constraint_inputs (dict<str, float>): Mapping from string symbol to symbol value
        Returns:
            (bool): bool stating whether the constraints of the model are met.
        """
        return True

    def evaluate(self, symbol_values):
        """
        Given a set of symbol_values, performs error checking to see if the input symbol_values represents a valid input
        set based on the self.connections() method. If so, it returns a dictionary representing the value of plug_in
        applied to the inputs. The dictionary contains a "successful" key representing if plug_in was successful.

        Args:
            symbol_values (dict<str,float>): Mapping from string symbol to float value, giving inputs.
        Returns:
            (dict<str,float>), mapping from string symbol to float value giving result of applying the model to the
                               given inputs. Additionally contains a "successful" key -> bool pair.
        """

        # strip units from input
        for symbol in symbol_values:
            if type(symbol_values[symbol]) == ureg.Quantity:
                symbol_values[symbol] = float(symbol_values[symbol].to(self.unit_mapping[symbol]).magnitude)

        available_symbols = set(symbol_values.keys())

        # check we support this combination of inputs
        available_inputs = [len(set(possible_input_symbols) - available_symbols) == 0
                            for possible_input_symbols in self.input_symbols]
        if not any(available_inputs):
            return {
                'successful': False,
                'message': "The {} model cannot generate any outputs for these inputs: {}".format(
                    self.name, available_symbols)
            }
        try:
            # evaluate is allowed to fail
            out = self.plug_in(symbol_values)
            out['successful'] = True
        except Exception as e:
            return {
                'successful': False,
                'message': str(e)
            }

        # add units to output
        for key in out:
            if key == 'successful':
                continue
            out[key] = ureg.Quantity(out[key], self.unit_mapping[key])

        return out

    def plug_in(self, symbol_values):
        """
        Given a set of symbol_values, plugs the values into the model and returns a dictionary of outputs representing
        the result of plugging in the symbol_values. symbol_values must contain a valid set of inputs as indicated in
        the connections method.

        Args:
            symbol_values (dict<str,float>): Mapping from string symbol to float value, giving inputs.
        Returns:
            (dict<str,float>) mapping from string symbol to float value giving result of applying the model to the
                              given inputs.
        """
        # Define sympy equations for the model
        if not self.equations:
            raise ValueError('Please implement the _evaluate '
                             'method for the {} model.'.format(self.name))
        eqns = [parse_expr(eq) for eq in self.equations]
        eqns = [eqn.subs(symbol_values) for eqn in eqns]
        # Generate outputs from the sympy equations.
        possible_outputs = set()
        for eqn in eqns:
            possible_outputs = possible_outputs.union(eqn.free_symbols)
        outputs = {}
        for possible_output in possible_outputs:
            solutions = sp.nonlinsolve(eqns, possible_output)
            # taking first solution only, and only asking for one output symbol
            # so know length of output tuple for solutions will be 1
            solution = list(solutions)[0][0]
            if not isinstance(solution, sp.EmptySet):
                outputs[str(possible_output)] = sp.N(solution)
        return outputs

    # Suite of getter methods returning appropriate model data.
    @property
    def name(self):
        """
        Returns:
            (str): Name of model
        """
        return self.__class__.__name__

    @property
    def title(self):
        """
        Returns:
            (str): Title of model
        """
        return self._metadata.get('title', 'undefined')

    @property
    def tags(self):
        """
        Returns:
            (list<str>): List of tags associated with the model
        """
        return self._metadata.get('tags', [])

    @property
    def description(self):
        """
        Returns:
            (str): Description of model as Markdown string """
        return self._metadata.get('description', '')

    @property
    def symbol_mapping(self):
        """
        A mapping of a symbol named used within the model to the canonical symbol name, e.g. {"E": "youngs_modulus"}
        keys are symbols used in the model; values are SymbolType enum values (SymbolType.name field)

        Returns:
            (dict<str,str>): symbol mapping dictionary
        """
        return self._metadata.get('symbol_mapping', {})

    @property
    def connections(self):
        """
        Forms the list of outputs that can be generated from different sets of inputs. The outer list contains
        dictionaries. These dictionaries contain two keys: "inputs" and "outputs". Each key maps to a list of symbol
        strings that serve as the list of input / output property types required for evaluation by the model.

        Returns:
             (list<dict<str,list<str>>>): List of connections
        """
        return self._metadata.get('connections', [])

    @property
    def input_symbols(self):
        """
        Returns:
            (list<str>): all sets of input symbols for the model
        """
        return [d['inputs'] for d in self.connections]

    @property
    def output_symbols(self):
        """
        Returns:
            (list<str>): all sets of output symbols for the model
        """
        return [d['outputs'] for d in self.connections]

    @property
    def equations(self):
        """
        Returns:
            (list<str>): equations that define the model
        """
        return self._metadata.get('equations', [])

    @property
    def references(self):
        """
        References for a model. When defining a model, these should be given as a list of strings with either the
        prefix "url:" or "doi:", and a formatted BibTeX string will be generated

        Returns:
            (list<str>): list of BibTeX strings
        """

        refs = self._metadata.get('references', [])

        return refs

    def __hash__(self):
        """
        A unique model hash, SHA256 hash of the model class name.

        :return (str): 4-digit hex string
        """
        return int.from_bytes(sha256(self.__class__.__name__.encode('utf-8')).digest(), 'big')

    @property
    def model_id(self):
        """
        A unique model identifier, function of model class name.

        :return (str): 4-digit hex string
        """
        return sha256(self.__class__.__name__.encode('utf-8')).hexdigest()[0:4]

    def __eq__(self, other):
        return self.model_id == getattr(other, "model_id", None)

    def __repr__(self):
        return self.name

    def __str__(self):
        return "{} [{}]".format(self._metadata['title'], self.model_id)

    def test(self, test_file=None):
        """

        Args:
            test_file: path to file containing test data

        Returns: False if tests fail or no test data supplied,
        True if tests pass.

        """

        if not test_file:
            test_file = join(dirname(__file__), '../models/test_data/{}.json'
                             .format(self.__class__.__name__))
            if not isfile(test_file):
                return False

        test_data = loadfn(test_file)
        for d in test_data:
            try:
                model_outputs = self.plug_in(d['inputs'])
                for k, v in d['outputs'].items():
                    if not math.isclose(model_outputs[k], v):
                        return False
            except Exception as e:
                print(e)
                print('Testing {} raised an exception.'.format(self.__class__.__name__))
                return False

        return True
