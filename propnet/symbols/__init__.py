from typing import *
from glob import glob
from enum import Enum
from os import path
from monty.serialization import loadfn
from propnet import logger

from propnet.core.symbols import PropertyMetadata

# TODO: clean up this file, move as much to propnet.core.properties as possible
# TODO: 'symbols' is a dumb name, anyone feel free to rename

# Auto loading of all allowed properties

# Stores all loaded properties as PropertyMetadata instances in a dictionary, mapped to
# their names
property_metadata: Dict[str, PropertyMetadata] = {}

property_metadata_files: List[str] = glob(path.join(path.dirname(__file__),
                                                    '../symbols/**/*.yaml'),
                                          recursive=True)

for f in property_metadata_files:
    try:
        metadata = PropertyMetadata.from_dict(loadfn(f))
        property_metadata[metadata.name] = metadata
        if "{}.yaml".format(metadata.name) not in f:
            raise ValueError('Name/filename mismatch in {}'.format(f))
    except Exception as e:
        logger.error('Failed to parse {}, {}.'.format(path.basename(f), e))

# using property names for Enum, conventional to have all upper case
# but using all lower case here
PropertyType: Enum = Enum('PropertyType', [(k, v) for k, v in property_metadata.items()])

# Stores all loaded properties' names in a tuple in the global scope.
all_property_names: Tuple[str] = tuple(p for p in property_metadata.keys())

def get_display_name(property_name):
    """Convenience function

    Args:
      property_name: 

    Returns:

    """
    return PropertyType[property_name].value.display_names[0]