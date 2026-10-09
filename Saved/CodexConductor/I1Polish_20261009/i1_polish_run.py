import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import i1_polish

with open(os.path.join(HERE, "i1_polish_args.json"), "r", encoding="utf-8") as handle:
    i1_polish.main(json.load(handle), tool_root=HERE)

