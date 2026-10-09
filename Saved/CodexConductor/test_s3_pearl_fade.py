"""Offline regression harness for the run-51c existing-track refusal."""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("s3_pearl_fade_offline", os.path.join(HERE, "s3_pearl_fade.py"))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

current = {
    "solid_visibility": [{"property": "bHiddenInGame", "path": "bHiddenInGame", "active_sections": 1,
                          "keys": [(1080, True), (1440, True), (tool.F0, False), (5201, True), (6176, True)]}],
    "twin_visibility": [{"property": "None", "path": "None", "active_sections": 1,
                         "keys": tool._expected_twin_vis()}],
    "material_fade": [{"class": "MovieSceneComponentMaterialTrack", "active_sections": 1,
                       "keys": tool._expected_fade()}],
}
results = []
results.append(("old existing-track guard refuses logged state", len(current["material_fade"]) != 0))
plan = tool.adoption_plan(current)
results.append(("new plan adopts exact existing tracks", plan["twin_visibility"] == "reuse" and
                plan["material_fade"] == "reuse" and plan["twin_bind_bHidden"] and plan["solid_bind_bHidden"]))
drift = {key: [dict(row) for row in value] for key, value in current.items()}
drift["twin_visibility"][0]["keys"] = [(0, False), (tool.F0, True), (tool.F1 + 1, False)]
try:
    tool.adoption_plan(drift)
    results.append(("real key drift refuses", False))
except RuntimeError as exc:
    results.append(("real key drift refuses", "TWIN_VISIBILITY_SHAPE" in str(exc)))

passed = sum(ok for _name, ok in results)
for name, ok in results:
    if not ok:
        print("FAIL|" + name)
print("S3_PEARL_FADE_HARNESS|pass=%d|fail=%d|total=%d" % (passed, len(results) - passed, len(results)))
raise SystemExit(0 if passed == len(results) else 1)
