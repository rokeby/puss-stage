"""READ-ONLY: LOD1 (and LOD0) Timber vertex-colour R of landed V3 flats, for the W2 consistency gate."""
import importlib.util, json, os, sys, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
spec = importlib.util.spec_from_file_location("p1_readonly", os.path.join(BASE, "phase1_import.py"))
src = open(os.path.join(BASE, "phase1_import.py"), encoding="utf-8").read()
# load only definitions; phase1_import has no top-level side effects beyond defs/constants (checked: main guarded)
p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
MESHES = ["/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_coventry_ruin_L_v1",
          "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/SM_FlatV3_P04_coventry_ruin_R_v1",
          "/Game/Scenes/Wings/FlatV3/Passage05/StaticMeshes/SM_FlatV3_P05_CloudRef01_L_L"]
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
start = census(); out = {"census_start": start, "meshes": {}}
for path in MESHES:
    mesh = unreal.EditorAssetLibrary.load_asset(path); rec = {}
    for lod in range(int(mesh.get_num_lods())):
        d = p1.dynamic_lod(mesh, lod)
        rec["lod%d" % lod] = {"timber_r": d["materials"]["2"]["r_range"], "timber_g": d["materials"]["2"]["g_range"]}
    out["meshes"][path] = rec
end = census()
if end != start:
    raise RuntimeError("PROBE_CHANGED_CENSUS|" + json.dumps([start, end]))
p = os.path.join(BASE, "probe_v3_timber_vc_out.json"); open(p, "w").write(json.dumps(out, indent=1))
unreal.log("FLATV3_PROBE_VC_OK path=%s census=%s" % (p, json.dumps(end)))
