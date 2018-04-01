import unittest
from propnet.core.symbols import *

# these are properties distributed with Propnet as
# yaml files in the properties folder
from propnet.symbols import DEFAULT_SYMBOL_TYPES

class PropertiesTest(unittest.TestCase):

    def test_property_metadata(self):

        sample_symbol_type_dict = {
            'name': 'youngs_modulus',
            'units': [1.0, [["gigapascal", 1.0]]],
            'display_names': ["Young's modulus", "Elastic modulus"],
            'display_symbols': ["E"],
            'dimension': 1,
            'comment': ""
        }

        sample_symbol_type = SymbolType(
            name='youngs_modulus',
            units= [1.0, [["gigapascal", 1.0]]], #ureg.parse_expression("GPa"),
            display_names=["Young's modulus", "Elastic modulus"],
            display_symbols=["E"],
            dimension=1,
            comment=""
        )

        self.assertEqual(sample_symbol_type,
                         SymbolType.from_dict(sample_symbol_type_dict))

    def test_all_properties(self):

        self.assertEqual(str(DEFAULT_SYMBOL_TYPES['density'].value.units),
                         '1.0 gram / centimeter ** 3')