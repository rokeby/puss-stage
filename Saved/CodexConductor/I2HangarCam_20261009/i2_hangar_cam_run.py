"""Runner for i2_hangar_cam.py.  Executed by Unreal's project-Python tool."""
import importlib.util
import json
import os
import sys
import traceback

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "i2_hangar_cam_args.json"), "r", encoding="utf-8") as handle:
        args = json.load(handle)
    spec = importlib.util.spec_from_file_location("i2_hangar_cam", os.path.join(HERE, "i2_hangar_cam.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(args)


try:
    main()
except Exception as error:  # noqa: BLE001
    unreal.log_error("I2_HANGAR_CAM_RUNNER_ERROR|%s|%s" % (type(error).__name__, error))
    unreal.log_error(traceback.format_exc())
    raise

