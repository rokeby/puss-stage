"""READ-ONLY: bounds of the two pre-pilot P04 Wing 011 meshes, so S4 can restore the pre-pilot inner edges."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
start = census()
orig = json.load(open(os.path.join(BASE, "phase2_originals_FV3PILOT-20261001-02.json")))
out = {"census_start": start, "cue_index": orig["cue_index"], "cue_label": orig["cue_label"], "sides": {}}
for side in ("left", "right"):
    rec = orig[side]
    mesh = unreal.EditorAssetLibrary.load_asset(rec["mesh"])
    box = mesh.get_bounding_box()
    out["sides"][side] = {"mesh": rec["mesh"], "facing_policy": rec["facing_policy"],
                          "local_transform": rec["local_transform"],
                          "mesh_min": [box.min.x, box.min.y, box.min.z], "mesh_max": [box.max.x, box.max.y, box.max.z]}
end = census()
if end != start:
    raise RuntimeError("PROBE_CHANGED_CENSUS|" + json.dumps([start, end]))
p = os.path.join(BASE, "probe_wing011_prepilot_out.json"); open(p, "w").write(json.dumps(out, indent=1))
unreal.log("FLATV3_PROBE_W011_OK path=%s census=%s" % (p, json.dumps(end)))
