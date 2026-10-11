"""Verify the light and fixture body returned exactly; report dirty scope."""

import json
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
passage, structure, dirty_content, dirty_maps = core.context(require_clean=False)
target, _, _ = core.find_target(passage, core.fixture_positions(structure), record["target_label"])
core.require(core.distance(core.vec(target.get_actor_location()), record["original_light"]) <= 0.01,
             "LIGHT_NOT_RESTORED")
restored = core.fixture_positions(structure)
body_error = core.nearest_distance(record["body_before"], restored)
core.require(body_error <= 0.5, "TARGET_BODY_NOT_RESTORED|nearest_error=%.3f" % body_error)
unreal.log("JOB185_FIXTURE_RESTORED_OK|target=%s|bodies=%d|body_error=%.3f|content=%s|maps=%s|saved=0" %
           (record["target_label"], len(restored), body_error,
            json.dumps(dirty_content), json.dumps(dirty_maps)))

