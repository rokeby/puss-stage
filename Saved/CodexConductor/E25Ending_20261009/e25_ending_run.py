import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import e25_ending

request = json.load(open(os.path.join(HERE, "e25_ending_request.json"), encoding="utf-8"))
args_file = request.pop("args_file")
raw = json.load(open(os.path.join(HERE, args_file), encoding="utf-8"))
raw.update(request)
e25_ending.main(raw)
