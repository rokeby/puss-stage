"""Prove all six hangars are landed and the level save left a clean editor."""
import datetime
import json
import os
import runpy

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
)
ns = runpy.run_path(
    os.path.join(HERE, "s3_landed_preview.py"),
    init_globals={
        "HANGAR_LANDED_PREVIEW_MODE": "STATUS",
        "HANGAR_LANDED_PREVIEW_IDS": "all",
    },
)
ns["_assert_context"]()
actors, index = ns["_actor_index"]()
max_location = 0.0
max_rotation = 0.0
for scene in ns["HANGAR_IDS"]:
    plan = ns["_sequence_plan"](scene, actors, index)
    if not os.path.isfile(ns["_record_path"](scene)):
        raise RuntimeError("S%d landed-preview record is absent" % scene)
    landed = {label: plan["rows"][label]["landed"] for label in plan["mover_labels"]}
    result = ns["validate_pose_errors"](ns["_pose_error_rows"](plan, landed))
    max_location = max(max_location, float(result["location_cm"]))
    max_rotation = max(max_rotation, float(result["rotation_deg"]))
census = {
    "content": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "maps": sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
}
if census != {"content": [], "maps": []}:
    raise RuntimeError("post-save dirty census: %s" % json.dumps(census, sort_keys=True))
run = datetime.datetime.now().strftime("%H%M%S")
unreal.log(
    "CONDUCTOR_LEVEL_LANDED_SAVED|run=%s|hangars=1,2,3,4,5,6|max_err_cm=%.9f|max_err_deg=%.9f|census=%s"
    % (run, max_location, max_rotation,
       json.dumps(census, separators=(",", ":"), sort_keys=True))
)
