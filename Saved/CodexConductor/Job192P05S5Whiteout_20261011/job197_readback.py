"""Read-only Job 197 verification of the applied P05 -> S5 3D whiteout."""
import json
import os
import sys

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import job192_p05_s5_whiteout as tool

run = "J192-J197-A1"
ctx = tool.find_context(run)
state = tool.snapshot(ctx)
expected = {
    "keys": [[34959360, 0.0], [34995360, 0.08], [35031360, 0.28], [35064960, 0.62],
             [35088960, 0.92], [35101440, 1.0], [35103360, 1.0], [35146560, 0.0]],
    "range_display": [36416, 36612],
    "fade_color": [1.0, 1.0, 1.0, 1.0],
    "fade_audio": False,
}
problems = []
if state["fade_track"] != expected:
    problems.append("fade_track=%r" % state["fade_track"])
if state["arrival"]["scene_cue_guid"] != tool.ZERO_GUID:
    problems.append("arrival_guid=%s" % state["arrival"]["scene_cue_guid"])
if state["media"]["s5_use_video"]:
    problems.append("S5 unexpectedly configured for video")
if state["dirty"] != {"content": [], "maps": []}:
    problems.append("dirty=%r" % state["dirty"])
if problems:
    raise RuntimeError("JOB197_WHITEOUT_READBACK_FAILED|" + "|".join(problems))
unreal.log("JOB197_WHITEOUT_READBACK_OK|run=%s|master=%s|presentation=3d|fade_keys=8|seam_amount=1|arrival_drive_disabled=1|dirty_maps=0|dirty_content=0|state=%s" %
           (run, ctx["master_path"], json.dumps(state, sort_keys=True)))
