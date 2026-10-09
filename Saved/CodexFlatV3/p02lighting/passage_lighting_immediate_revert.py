"""One-command field-scoped REVERT for the active PASSAGELIGHT APPLY record."""
import importlib.util
import json
import os

import unreal


HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                    "CodexFlatV3", "p02lighting")
RECORD_PATH = os.path.join(HERE, "passage_lighting_record.json")

with open(RECORD_PATH, encoding="utf-8") as handle:
    record = json.load(handle)

spec = importlib.util.spec_from_file_location(
    "_passage_lighting_immediate_revert",
    os.path.join(HERE, "passage_lighting_as_source.py"),
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
args = module.immediate_revert_args(record)
unreal.log("PASSAGELIGHT_IMMEDIATE_REVERT_BEGIN|apply_run=%s|field_scoped=1" % record.get("run"))
module.main(args)
