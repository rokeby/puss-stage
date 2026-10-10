"""Offline regression harness for the run-51c existing-track refusal."""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("s3_pearl_fade_offline", os.path.join(HERE, "s3_pearl_fade.py"))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

current = {
    "solid_visibility": [{"property": "bHiddenInGame", "path": "bHiddenInGame", "active_sections": 1,
                          "keys": [(1080, True), (1440, True), (tool.LEGACY_F0, False), (5201, True), (6176, True)]}],
    "twin_visibility": [{"property": "None", "path": "None", "active_sections": 1,
                         "keys": tool._expected_twin_vis(tool.LEGACY_F0)}],
    "material_fade": [{"class": "MovieSceneComponentMaterialTrack", "active_sections": 1,
                       "keys": tool._expected_fade(tool.LEGACY_F0)}],
}
results = []
results.append(("two-second fade ends at retained vanish frame",
                tool.F1 == 5040 and tool.F1 - tool.F0 == 48 and tool.FADE_SECONDS == 2))
results.append(("old existing-track guard refuses logged state", len(current["material_fade"]) != 0))
plan = tool.adoption_plan(current)
results.append(("new plan adopts exact existing tracks", plan["twin_visibility"] == "reuse" and
                plan["material_fade"] == "reuse" and plan["twin_bind_bHidden"] and plan["solid_bind_bHidden"] and
                plan["twin_retime_legacy"] and plan["material_retime_legacy"] and plan["solid_remove_legacy_f0"]))
after = tool.expected_state_after(current)
results.append(("post-edit state is exact before save",
                after["solid_visibility"][0]["property"] == "bHidden" and
                (tool.LEGACY_F0, False) not in after["solid_visibility"][0]["keys"] and
                (tool.F0, False) in after["solid_visibility"][0]["keys"] and
                after["twin_visibility"][0]["keys"] == tool._expected_twin_vis() and
                after["material_fade"][0]["keys"] == tool._expected_fade()))
source = open(os.path.join(HERE, "s3_pearl_fade.py"), encoding="utf-8").read()
results.append(("UE 5.8 key removal uses channel API before in-memory gate",
                "vch.remove_key(key)" in source and "key.remove()" not in source and
                source.index("IN_MEMORY_VERIFY") < source.index("EditorAssetLibrary.save_asset")))
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
