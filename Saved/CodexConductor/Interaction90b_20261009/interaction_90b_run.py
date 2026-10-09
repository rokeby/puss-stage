import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import interaction_90b

with open(os.path.join(HERE, "interaction_90b_args.json"), "r", encoding="utf-8") as handle:
    interaction_90b.main(json.load(handle), root=HERE)
