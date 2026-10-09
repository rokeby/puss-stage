import json
import os
import runpy
import sys

here = os.path.dirname(__file__)
if here not in sys.path:
    sys.path.insert(0, here)
args = json.load(open(os.path.join(here, "s2_envelope_args.json"), encoding="utf-8"))
runpy.run_path(os.path.join(here, "s2_envelope.py"), init_globals={"S2ENVELOPE_ARGS": args})
