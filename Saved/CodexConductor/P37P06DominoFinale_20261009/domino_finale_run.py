"""Execute domino_finale_apply.py through ExecuteProjectPythonFile."""
import json
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "domino_finale_live_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)
runpy.run_path(os.path.join(HERE, "domino_finale_apply.py"), init_globals={"P37_DOMINO_ARGS": ARGS})
