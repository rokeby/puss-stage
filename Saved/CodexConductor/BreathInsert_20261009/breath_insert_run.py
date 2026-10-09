"""Guarded project-Python runner for P45 breath insertion."""
import importlib.util
import json
import os
import traceback

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "breath_insert_args.json"), "r", encoding="utf-8") as handle:
        args = json.load(handle)
    spec = importlib.util.spec_from_file_location("breath_insert", os.path.join(HERE, "breath_insert.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    live_spec = importlib.util.spec_from_file_location("breath_insert_live", os.path.join(HERE, "breath_insert_live.py"))
    live = importlib.util.module_from_spec(live_spec)
    live_spec.loader.exec_module(live)
    backend = module.UnrealBackend(snapshot_provider=live.snapshot_provider, edit_executor=live.edit_executor)
    module.main(args, backend=backend)


try:
    main()
except Exception as error:  # noqa: BLE001
    unreal.log_error("P36_BREATH_RUNNER_ERROR|%s|%s" % (type(error).__name__, error))
    unreal.log_error(traceback.format_exc())
    raise
