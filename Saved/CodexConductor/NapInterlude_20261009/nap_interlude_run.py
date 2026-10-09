"""Project-Python entry point for P79.  Reads the mode file beside this script."""
import json
import os
import sys

HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import nap_interlude

with open(os.path.join(HERE, "nap_interlude_args.json"), "r", encoding="utf-8") as handle:
    nap_interlude.main(json.load(handle))

