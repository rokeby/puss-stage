import importlib.util
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "job184_s1_missed_lights.py")
PROBE = os.path.normpath(os.path.join(HERE, "..", "job184_s1_luminance_light_probe.json"))

spec = importlib.util.spec_from_file_location("job184_s1_missed_lights_test", TOOL)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS|" + name)
    else:
        failed += 1
        print("FAIL|" + name)


with open(PROBE, "r", encoding="utf-8") as handle:
    probe = json.load(handle)
frame = next(row for row in probe["frames"] if row["local_frame"] == 3880)
rows = [{"label": row["actor_label"], "intensity": row["intensity"]} for row in frame["lights"]]
selected = module.choose_labels(rows)
check("closed selection count", len(selected) == 213)
check("closed selection contains ghost", "S1 Ghost Light" in selected)
check("closed selection contains only P01 score plus ghost",
      all(label == "S1 Ghost Light" or module.P01_RE.match(label) for label in selected))
check("closed selection excludes gold swarm", not any("swarm" in label.lower() for label in selected))
check("selection digest", module.label_digest(selected) == module.EXPECTED_SELECTED_DIGEST)
check("fade timing", (module.FADE_START, module.FADE_END) == (3800, 3838))

source = open(TOOL, "r", encoding="utf-8").read()
check("no deprecated dirty API", "get_dirty_content_packages()" not in source.replace("EditorLoadingAndSavingUtils.get_dirty_content_packages()", ""))
check("no DateTime.now", "DateTime.now" not in source)
check("no actor is_hidden call", ".is_hidden(" not in source)
check("editor-world preflight", "get_game_world() is not None" in source and "get_editor_world()" in source)
check("no Save All", "save_all" not in source.lower() and "save_dirty" not in source.lower())
check("single asset authority", module.SEQ_PATH == "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01")
apply_source = source[source.index("def _run_apply"):source.index("def _run_readback")]
check("backup before mutation", apply_source.index("_backup\"](run") < apply_source.index("_add_binding("))
check("module cache purge", "del sys.modules[name]" in open(os.path.join(HERE, "job184_s1_missed_lights_run.py"), encoding="utf-8").read())
check("compile surface", re.search(r"MovieSceneFloatTrack", source) is not None)
request_path = os.path.normpath(os.path.join(HERE, "..", "job184_s1_missed_lights_request.json"))
with open(request_path, "r", encoding="utf-8") as handle:
    request = json.load(handle)
check("MCP request envelope", request.get("name") == "call_tool"
      and request.get("arguments", {}).get("tool_name") == "ExecuteProjectPythonFile"
      and request.get("arguments", {}).get("arguments", {}).get("relativeSavedPath")
      == "CodexConductor/Job184S1MissedLights_20261010/job184_s1_missed_lights_run.py")

print("JOB184_S1_MISSED_LIGHTS_HARNESS|pass=%d|fail=%d|total=%d" % (passed, failed, passed + failed))
raise SystemExit(1 if failed else 0)

