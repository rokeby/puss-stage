"""Guarded project-Python entrypoint.  Edit request/args JSON, never this file."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
request = json.load(open(os.path.join(HERE, "p87_opening_request.json"), encoding="utf-8"))
args_name = request.pop("args_file")
request["args"] = json.load(open(os.path.join(HERE, args_name), encoding="utf-8"))

from p87_unreal_adapter import P87UnrealBackend
import p87_opening_fixes

p87_opening_fixes.P87_REQUEST = request
p87_opening_fixes.P87_BACKEND = P87UnrealBackend()
p87_opening_fixes.main()
