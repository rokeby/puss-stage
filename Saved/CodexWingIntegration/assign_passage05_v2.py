import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wing_integration_common

importlib.reload(wing_integration_common)
wing_integration_common.assign_passage(5)
