"""READ-ONLY: is each S3 wave mesh's in-memory state the on-disk state? No edits, no saves."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
ROOT = "/Game/Scenes/Wings/FlatV3/Scene3/StaticMeshes/"
NAMES = ["SM_FlatV3_S3_WaveRow%d_%s" % (r, s) for r in (1, 2, 3) for s in ("A", "B")]
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
start = census()
out = {"census_start": start, "meshes": {}}
for name in NAMES:
    path = ROOT + name
    disk = os.path.normpath(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
                                         path[len("/Game/"):].replace("/", os.sep) + ".uasset"))
    mesh = unreal.EditorAssetLibrary.load_asset(path)
    pkg = mesh.get_outermost()
    lods = int(mesh.get_num_lods())
    out["meshes"][name] = {
        "package_dirty": path in start["content"],
        "disk_mtime_utc": os.path.getmtime(disk), "disk_bytes": os.path.getsize(disk),
        "num_lods": lods,
        "verts_per_lod": [int(mesh.get_num_vertices(i)) for i in range(lods)],
        "tris_lod0": int(mesh.get_num_triangles(0)) if hasattr(mesh, "get_num_triangles") else None,
        "slots": [str(m.get_editor_property("material_slot_name")) for m in mesh.get_editor_property("static_materials")],
        "bounds_extent": [round(v, 2) for v in (mesh.get_bounding_box().max - mesh.get_bounding_box().min).to_tuple()],
        "import_source": [str(f) for f in (mesh.get_editor_property("asset_import_data").extract_filenames() if mesh.get_editor_property("asset_import_data") else [])],
    }
end = census()
if end != start:
    raise RuntimeError("PROBE_CHANGED_CENSUS|" + json.dumps([start, end]))
p = os.path.join(BASE, "probe_w_inmemory_out.json"); open(p, "w").write(json.dumps(out, indent=1))
unreal.log("FLATV3_PROBE_W_OK path=%s census=%s" % (p, json.dumps(end)))
