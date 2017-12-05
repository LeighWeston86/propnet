from typing import *
from glob import glob
from enum import Enum
from os import path
from monty.serialization import loadfn
from propnet import logger

from propnet.core.properties import PropertyMetadata

# Auto loading of all allowed properties

# Stores all loaded conditions as PropertyMetadata instances in a dictionary in the global scope, mapped from
# their names.
condition_metadata: Dict[str, PropertyMetadata] = {}

condition_metadata_files: List[str] = glob(path.join(path.dirname(__file__), '../conditions/*.yaml'))

for f in condition_metadata_files:
    try:
        storing = PropertyMetadata.from_dict(loadfn(f))
        condition_metadata[storing.name] = storing
    except Exception as e:
        logger.error('Failed to parse {}, {}.'.format(path.basename(f), e))

# using condition names for Enum, conventional to have all upper case
# but using all lower case here
ConditionType: Enum = Enum('ConditionType', [(k, v) for k, v in condition_metadata.items()])

# Stores all loaded conditions' names in a tuple in the global scope.
all_condition_names: Tuple[str] = tuple(p for p in condition_metadata.keys())
