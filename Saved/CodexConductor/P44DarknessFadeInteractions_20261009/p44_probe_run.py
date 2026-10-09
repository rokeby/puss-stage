"""Fresh guarded runner for p44_probe.py."""
import json
import os
import runpy
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    with open(os.path.join(HERE, "p44_probe_args.json"), "r", encoding="utf-8") as handle:
        args = json.load(handle)
    runpy.run_path(os.path.join(HERE, "p44_probe.py"), run_name="__p44_probe__",
                   init_globals={"P44_PROBE_ARGS": args})
except Exception as error:  # noqa: BLE001
    unreal.log_error("P44_PROBE_RUNNER_ERROR|%s|%s" % (type(error).__name__, error))
    unreal.log_error(traceback.format_exc())
    raise
