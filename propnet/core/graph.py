"""
Module containing classes and methods for graph functionality in Propnet code.
"""

from typing import *

import networkx as nx

from propnet import logger
from propnet.models import *
from propnet.symbols import SymbolType

from propnet.core.symbols import Symbol
from propnet.core.models import AbstractModel

from enum import Enum
from collections import Counter, namedtuple

PropnetNodeType = Enum('PropnetNodeType', ['Material', 'SymbolType', 'Symbol', 'Model'])
PropnetNode = namedtuple('PropnetNode', ['node_type', 'node_value'])


class Propnet:
    """
    Class containing methods for creating and interacting with a Property Network.

    The Property Network contains a set of PropnetNode namedtuples with connections stored as directed edges between
    the nodes.

    Upon initialization a base graph is constructed consisting of all valid SymbolTypes and Models found in surrounding
    folders. These are SymbolType and Model node_types respectively. Connections are formed between the nodes based on
    given inputs and outputs of the models. At this stage the graph represents a symbolic web of properties without
    any actual input values.

    Materials and Properties / Conditions can be added at runtime using appropriate support methods. These methods
    dynamically create additional PropnetNodes and edges on the graph of Material and Symbol node_types respectively.

    Given a set of Materials and Properties / Conditions, the symbolic web of properties can be utilized to predict
    values of connected properties on demand.

    Attributes:
        graph (nx.MultiDiGraph<PropnetNode>): data structure supporting the property network.

    """

    def __init__(self):
        """
        Creates a Propnet instance, adding all valid SymbolTypes and Models found in surrounding folders.
        """

        g = nx.MultiDiGraph()

        # add all symbols to graph
        symbol_nodes = [PropnetNode(node_type=PropnetNodeType.SymbolType, node_value=symbol_type)
                        for symbol_type in SymbolType]
        g.add_nodes_from(symbol_nodes)

        # get a list of our models (except abstract base classes)
        models = [model() for model in AbstractModel.__subclasses__()
                  if not model.__module__.startswith('propnet.core')]

        # add all models to graph
        model_nodes = [PropnetNode(node_type=PropnetNodeType.Model, node_value=model)
                       for model in models]
        g.add_nodes_from(model_nodes)

        # add appropriate edges to the graph
        for model in models:

            model_node = PropnetNode(node_type=PropnetNodeType.Model, node_value=model)

            # integer idx is used to disambiguate edges when multiple exist between the same start and end nodes.
            for idx, connection in enumerate(model.connections):

                outputs, inputs = connection['outputs'], connection['inputs']

                if isinstance(outputs, str):
                    outputs = [outputs]
                if isinstance(inputs, str):
                    inputs = [inputs]

                for input in inputs:
                    symbol_type = SymbolType[model.symbol_mapping[input]]
                    input_node = PropnetNode(node_type=PropnetNodeType.SymbolType,
                                             node_value=symbol_type)
                    g.add_edge(input_node, model_node, route=idx)

                for output in outputs:
                    symbol_type = SymbolType[model.symbol_mapping[output]]
                    output_node = PropnetNode(node_type=PropnetNodeType.SymbolType,
                                              node_value=symbol_type)
                    g.add_edge(model_node, output_node, route=idx)

        self.graph = g

    def nodes_by_type(self, node_type):
        """
        Gathers all PropnetNodes of a given PropnetNodeType.

        Args:
            node_type (str): type of node that will be returned.
        Returns:
            (list<PropnetNode>) list of nodes of property types.
        """
        to_return = []
        for node in self.graph.nodes:
            if node.node_type.name == node_type:
                to_return.append(node)
        return to_return

    def add_material(self, material):
        """
        Add a material and any of its associated properties to the Propnet graph.
        Mutates the graph instance variable.

        Args:
            material (Material) Material whose information will be added to the graph.
        Returns:
            void
        """
        material.parent = self
        self.graph = nx.compose(material.graph, self.graph)

    def remove_material(self, material):
        """
        Removes a material and any of its associated properties from the Propnet graph.
        Mutates the graph instance variable.

        Args:
            material (Material) Material whose information will be removed from the graph.
        Returns:
            void
        """
        material_node = None
        for node in self.graph.nodes:
            if node.node_type != PropnetNodeType['Material']:
                continue
            if node.node_value != material:
                continue
            if material_node:
                raise ValueError("Multiple duplicate Material nodes were found - removal is ambiguous.")
            material_node = node
        if not material_node:
            raise ValueError("Material was not found.")
        to_remove = []
        for neighbor in self.graph.neighbors(material_node):
            if neighbor.node_type != PropnetNodeType['Symbol']:
                continue
            to_remove.append(neighbor)
        self.graph.remove_node(material_node)
        for node in to_remove:
            self.graph.remove_node(node)
        material_node.node_value.parent = None

    def evaluate(self, material=None, property_type=None):
        """
        Expands the graph, producing the output of models that have the appropriate inputs supplied.
        Mutates the graph instance variable.

        Optional arguments limit the scope of which models or properties are tested.
            material parameter: produces output from models only if the input properties come from the specified material.
                                mutated graph will modify the Material's graph instance as well as this graph instance.
                                mutated graph will include edges from Material to Symbol to SymbolType.
            property_type parameter: produces output from models only if the input properties are in the list.

        If no material parameter is specified, the generated SymbolNodes will be added with edges to and from
        corresponding SymbolTypeNodes specifically. No connections will be made to existing Material nodes because
        a Symbol might be derived from a combination of materials in this case. Likewise existing Material nodes' graph
        instances will not be mutated in this case.

        Args:
            material (Material): optional limit on which material's properties will be expanded (default: all materials)
            property_type (list<SymbolType>): optional limit on which Symbols will be considered as input.
        Returns:
            void
        """
        # Get existing Symbol nodes, 'active' SymbolType nodes, and 'candidate' Models.
        # Filter by provided material and property_type arguments.
        if not material:
            symbol_nodes = self.nodes_by_type('Symbol')
        else:
            material_nodes = self.nodes_by_type('Material')
            material_node = None
            for node in material_nodes:
                if node.node_value == material:
                    if material_node:
                        raise ValueError('Multiple identical materials found.')
                    material_node = node
            if not material_node:
                raise ValueError('Specified material not found.')
            symbol_nodes = []
            for node in self.graph.neighbors(material_node):
                if node.node_type == PropnetNodeType['Symbol'] and node not in symbol_nodes:
                    symbol_nodes.append(node)

        if property_type:
            c = 0
            while c < len(symbol_nodes):
                if symbol_nodes[c].node_value.type not in property_type:
                    symbol_nodes.remove(symbol_nodes[c])
                else:
                    c += 1

        active_symbol_type_nodes = set()
        for node in symbol_nodes:
            for neighbor in self.graph.neighbors(node):
                if neighbor.node_type != PropnetNodeType.SymbolType:
                    continue
                active_symbol_type_nodes.add(neighbor)
        candidate_models = set()
        for node in active_symbol_type_nodes:
            for neighbor in self.graph.neighbors(node):
                if neighbor.node_type != PropnetNodeType.Model:
                    continue
                candidate_models.add(neighbor)

        # Create fast-lookup data structure (SymbolType -> Symbol):
        lookup_dict = {}
        for node in symbol_nodes:
            if node.node_value.type not in lookup_dict:
                lookup_dict[node.node_value.type] = [node.node_value]
            else:
                lookup_dict[node.node_value.type] += [node.node_value]

        # For each candidate model, check if we have active property types to match types and assumptions.
        # If so, produce the available output properties.
        for model_node in candidate_models:
            outputs = []
            # Cache necessary data from model_node: input symbols, types, and conditions.
            model = model_node.node_value
            legend = model.symbol_mapping
            sym_inputs = model.input_symbols
            input_conditions = model.constraints

            def get_types(symbols_in, legend):
                """Converts symbols used in equations to SymbolType enum objects"""
                to_return = []
                for l in symbols_in:
                    out = []
                    for i in l:
                        out.append(SymbolType[legend[i]])
                    to_return.append(out)
                return to_return

            type_inputs = get_types(sym_inputs, legend)

            # Look through all input sets and match with all combinations from lookup_dict.
            def gen_input_dicts(symbols, candidate_props, constraint_props, level):
                """Recursively generates all possible combinations of input arguments"""
                current_level = []
                candidates = candidate_props[level]
                for candidate in candidates:
                    constraint = constraint_props.get(symbols[level])
                    if not constraint or constraint(candidate):
                        current_level.append({symbols[level]: candidate})
                if level == 0:
                    return current_level
                else:
                    others = gen_input_dicts(symbols, candidate_props, constraint_props, level-1)
                    to_return = []
                    for entry1 in current_level:
                        for entry2 in others:
                            merged_dict = {}
                            for (k, v) in entry1.items():
                                merged_dict[k] = v
                            for (k, v) in entry2.items():
                                merged_dict[k] = v
                            to_return.append(merged_dict)
                    return to_return

            # Get candidate input Symbols for the given model.
            for i in range(0, len(type_inputs)):
                candidate_properties = []
                for j in range(0, len(type_inputs[i])):
                    candidate_properties.append(lookup_dict.get(type_inputs[i][j], []))
                input_sets = gen_input_dicts(sym_inputs[i], candidate_properties, input_conditions, len(candidate_properties)-1)
                for input_set in input_sets:
                    plug_in_set = {}
                    for (k, v) in input_set.items():
                        plug_in_set[k] = v.value
                    outputs.append(model.evaluate(plug_in_set))

            # For any new outputs generated, create the appropriate SymbolNode and connections to SymbolTypeNodes
            # Mutates this graph.
            symbol_outputs = []
            for entry in outputs:
                for (k, v) in entry.items():
                    try:
                        prop_type = SymbolType[legend[k]]
                    except KeyError:
                        continue
                    symbol_outputs.append(Symbol(prop_type, v, None))
            for symbol in symbol_outputs:
                symbol_node = PropnetNode(node_type=PropnetNodeType['Symbol'], node_value=symbol)
                symbol_type_node = PropnetNode(node_type=PropnetNodeType['SymbolType'], node_value=symbol.type)
                self.graph.add_edge(symbol_node, symbol_type_node)
                if material:
                    self.graph.add_edge(material_node, symbol_node)
                    material_node.node_value.graph.add_edge(material_node.node_value.root_node, symbol_node)
                    material_node.node_value.graph.add_edge(symbol_node, symbol_type_node)

    def shortest_path(self, property_one: str, property_two: str):
        """ """
        # very easy to do with networkx, use in-built algo
        return NotImplementedError

    def populate_with_test_values(self):
        """ """
        # takes test values from the property definitions
        return NotImplementedError


    @property
    def all_models(self):
        """:return: Return a list of nodes of models."""
        return list(filter(lambda x: issubclass(x, AbstractModel), self.graph.nodes))

    @property
    def model_tags(self):
        """Collates tags present in models.
        :return: Returns list of tags

        Args:

        Returns:

        """
        all_tags = [tag for tags in self.all_models for tag in tags]
        unique_tags = sorted(list(set(all_tags)))
        return Counter(all_tags)

    def __str__(self):
        """
        Returns a full summary of the graph in terms of the SymbolTypes, Symbols, Materials, and Models
        that it contains. Connections are shown as nesting within the printout.

        Returns:
            (str) representation of this Propnet object.
        """
        summary = ["Propnet Graph", ""]
        property_type_nodes = self.nodes_by_type('SymbolType')
        summary += ["Property Types:"]
        for property_type_node in property_type_nodes:
            summary += ["\t " + property_type_node.node_value.value.display_names[0]]
            neighbors = self.graph.neighbors(property_type_node)
            for neighbor in neighbors:
                if neighbor.node_type != PropnetNodeType['Model']:
                    continue
                summary += ["\t\t " + neighbor.node_value.title]
        model_nodes = self.nodes_by_type('Model')
        summary += ["Models:"]
        for model_node in model_nodes:
            summary += ["\t " + model_node.node_value.title]
            neighbors = self.graph.neighbors(model_node)
            for neighbor in neighbors:
                if neighbor.node_type != PropnetNodeType['SymbolType']:
                    continue
                summary += ["\t\t " + neighbor.node_value.value.display_names[0]]
        materials = self.nodes_by_type('Material')
        if len(materials) != 0:
            summary += ["Materials:"]
        for material_node in materials:
            summary += ["\t " + str(material_node.node_value.id)]
            for property in filter(lambda n: n.node_type == PropnetNodeType['Symbol'],
                                   self.graph.neighbors(material_node)):
                summary += ["\t\t " + property.node_value.type.value.display_names[0] +
                            "\t:\t" + str(property.node_value.value)]
        return "\n".join(summary)
