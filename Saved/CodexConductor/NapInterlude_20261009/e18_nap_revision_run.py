"""Guarded ExecuteProjectPythonFile entry point for Job 97 / E18."""
import os
import sys

HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import e18_nap_revision
from e18_nap_revision_settings import RAW

e18_nap_revision.main(RAW)
