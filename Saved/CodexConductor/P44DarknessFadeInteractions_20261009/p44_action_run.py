"""Fresh guarded runner for one P44 item."""
import json
import os
import runpy
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    with open(os.path.join(HERE, "p44_action_args.json"), "r", encoding="utf-8") as handle:
        args = json.load(handle)
    runpy.run_path(os.path.join(HERE, "p44_action.py"), run_name="__p44_action__",
                   init_globals={"P44_ACTION_ARGS": args})
except Exception as error:  # noqa: BLE001
    unreal.log_error("P44_ACTION_RUNNER_ERROR|%s|%s" % (type(error).__name__, error))
    unreal.log_error(traceback.format_exc())
    raise
