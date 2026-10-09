"""Runner for s3_polish.py through ExecuteProjectPythonFile."""
import importlib.util
import json
import os
import traceback

import unreal


HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "s3_polish_args.json"), "r", encoding="utf-8") as handle:
        args = json.load(handle)
    spec = importlib.util.spec_from_file_location("s3_polish", os.path.join(HERE, "s3_polish.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(args)


try:
    main()
except Exception as error:  # noqa: BLE001
    unreal.log_error("S3_POLISH_RUNNER_ERROR|%s|%s" % (type(error).__name__, error))
    unreal.log_error(traceback.format_exc())
    raise
