"""Queue only InfinityStage.Editor.SavedMasterMatchesShow after capture gates pass."""
import json
import importlib
import os
import sys
import traceback
import unreal

BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3"))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
import slot_b_common as c
c = importlib.reload(c)
import slot_b_revert

TEST = "InfinityStage.Editor.SavedMasterMatchesShow"
try:
    editor, world = c.assert_context(clean=True)
    captures = c.read_json("slot_b_captures_%s.json" % c.RUN)
    if captures.get("status") != "PASS" or len(captures.get("files", [])) != 6:
        raise RuntimeError("CAPTURE_REPORT_NOT_PASS")
    unreal.SystemLibrary.execute_console_command(world, "Automation RunTests " + TEST)
    unreal.log("FLATV3_B_AUTOMATION_QUEUED run=%s test=%s alone=true" % (c.RUN, TEST))
except Exception as exc:
    reason = "automation_queue:" + str(exc)
    c.write_json("slot_b_automation_%s_FAILURE.json" % c.RUN,
                 {"run": c.RUN, "status": "FAIL", "reason": reason,
                  "traceback": traceback.format_exc(), "census": c.census()})
    saved = []
    try:
        saved = slot_b_revert.revert(reason)
    except Exception as revert_exc:
        reason += "|REVERT_FAIL:" + str(revert_exc)
    c.log_release("FAIL", saved, reason)
