import logging
import sys

from pint import UnitRegistry
from io import StringIO

# module-wide logger
logger = logging.getLogger(__name__)

# log to string, useful for web view
log_stream = StringIO()
logger.addHandler(logging.StreamHandler(stream=log_stream))

# make sure we see our log messages in Jupyter
logger.addHandler(logging.StreamHandler(stream=sys.stdout))

logger.warning("Propnet is not intended for public use at this time. Unless you personally know "
               "one of its developers, you probably shouldn't be using it right now! :) "
               "Functionality might change.")

# module-wide unit registry
ureg = UnitRegistry()

# add atoms as a unit-less quantity to our unit registry, e.g. for eV/atom
ureg.define('atom = []')

# convenience imports for user
from propnet.core.symbols import Symbol
from propnet.core.graph import Propnet
from propnet.core.materials import Material
