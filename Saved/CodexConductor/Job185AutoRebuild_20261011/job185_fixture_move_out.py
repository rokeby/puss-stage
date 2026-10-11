"""Move one P01 attachment light +50 cm on world X; save nothing."""

import os
import sys

import unreal

HERE = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
    "Job185AutoRebuild_20261011",
)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import job185_fixture_probe_common as core


passage, structure, _, _ = core.context(require_clean=True)
before = core.fixture_positions(structure)
target, body_before, nearest_xy = core.find_target(passage, before)
original = core.vec(target.get_actor_location())
original_relative = core.relative_location(target)
record = {
    "job": 185,
    "target_label": target.get_actor_label(),
    "original_light": original,
    "original_relative": original_relative,
    "moved_relative": [original_relative[0] + 50.0, original_relative[1], original_relative[2]],
    "body_before": body_before,
    "fixture_positions_before": before,
    "nearest_xy_cm": nearest_xy,
}
core.write_record(record)
core.commit_relative_location(target, record["moved_relative"])
world_delta = [core.vec(target.get_actor_location())[i] - original[i] for i in range(3)]
core.require(abs(core.distance([0.0, 0.0, 0.0], world_delta) - 50.0) <= 0.05,
             "WORLD_MOVE_NOT_50CM|delta=%s" % world_delta)
unreal.log("JOB185_FIXTURE_MOVE_OUT_OK|target=%s|delta_x=50.0|bodies=%d|saved=0" %
           (record["target_label"], len(before)))

