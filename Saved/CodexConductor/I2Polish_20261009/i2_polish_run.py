import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import i2_polish

with open(os.path.join(HERE, "i2_polish_args.json"), "r", encoding="utf-8") as handle:
    ARGS = json.load(handle)

i2_polish.main(ARGS, tool_root=HERE)
