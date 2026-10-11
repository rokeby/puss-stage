"""Verify fixture-only auto-rebuild moved one P01 body, then restore the light."""

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


record = core.read_record()
passage, structure, _, _ = core.context(require_clean=False)
target, _, _ = core.find_target(passage, core.fixture_positions(structure), record["target_label"])
moved_light = core.vec(target.get_actor_location())
world_delta = [moved_light[i] - record["original_light"][i] for i in range(3)]
core.require(abs(core.distance([0.0, 0.0, 0.0], world_delta) - 50.0) <= 0.05,
             "MOVED_LIGHT_NOT_50CM|delta=%s" % world_delta)
after = core.fixture_positions(structure)
expected_body = [record["body_before"][i] + world_delta[i] for i in range(3)]
body_error = core.nearest_distance(expected_body, after)
core.require(body_error <= 0.5,
             "TARGET_BODY_NOT_MOVED|expected=%s|nearest_error=%.3f" % (expected_body, body_error))
delta = world_delta
core.commit_relative_location(target, record["original_relative"])
unreal.log("JOB185_FIXTURE_BODY_MOVED_OK|target=%s|body_delta=%.3f,%.3f,%.3f|body_error=%.3f|bodies_before=%d|bodies_after=%d|restore_queued=1|saved=0" %
           (record["target_label"], delta[0], delta[1], delta[2], body_error,
            len(record["fixture_positions_before"]), len(after)))

