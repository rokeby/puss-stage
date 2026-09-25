"""Read-only dump: every Wing row's side/mesh/facing/flip/local transform, the Wing Library entry
per mesh, mesh bounds, and (if GeometryScript is available) a straight-edge measurement per mesh.
Saves nothing, mutates nothing."""
import collections, json, os, re
import unreal

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LABEL_RE = re.compile(r"^P(?P<passage>\d{2}) Wing (?P<ordinal>\d{3})$")

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    raise RuntimeError("Unexpected world")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE active")

def pkg(v):
    if v is None: return None
    return v.get_path_name().split(".", 1)[0] if hasattr(v, "get_path_name") else str(v).split(".", 1)[0]

def tf(t):
    try:
        loc, rot, sc = t.translation, t.rotation.rotator(), t.scale3d
        return {"loc": [round(loc.x, 3), round(loc.y, 3), round(loc.z, 3)],
                "rot": [round(rot.pitch, 3), round(rot.yaw, 3), round(rot.roll, 3)],
                "scale": [round(sc.x, 4), round(sc.y, 4), round(sc.z, 4)]}
    except Exception as exc:
        return {"error": repr(exc)}

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
if show is None: raise RuntimeError("Show did not load")

# Wing library entries
library_info = {"path": None, "entries": {}, "error": None}
try:
    lib = show.get_editor_property("wing_library")
    if lib:
        library_info["path"] = pkg(lib)
        entries = lib.get_editor_property("entries")
        for e in entries:
            mesh = None
            for name in ("mesh", "static_mesh", "asset"):
                try:
                    mesh = e.get_editor_property(name); break
                except Exception: pass
            rec = {}
            for name in ("front_axis", "placement_adjustment", "photographic_mirror_approved", "role", "display_name"):
                try:
                    v = e.get_editor_property(name)
                    rec[name] = tf(v) if isinstance(v, unreal.Transform) else str(v)
                except Exception: pass
            library_info["entries"][pkg(mesh) if mesh else f"?{len(library_info['entries'])}"] = rec
except Exception as exc:
    library_info["error"] = repr(exc)

# Rows
rows = []
unique_meshes = set()
for cue_index, cue in enumerate(show.get_editor_property("cues")):
    label = str(cue.get_editor_property("label"))
    m = LABEL_RE.match(label)
    if not m: continue
    pair = cue.get_editor_property("wing_pair")
    rec = {"index": cue_index, "label": label, "passage": int(m.group("passage")), "ordinal": int(m.group("ordinal"))}
    for side in ("left", "right"):
        p = pair.get_editor_property(side)
        mesh = pkg(p.get_editor_property("mesh"))
        unique_meshes.add(mesh)
        rec[side] = {"mesh": mesh,
                     "flip": bool(p.get_editor_property("flip_image_horizontally")),
                     "facing": str(p.get_editor_property("facing_policy")),
                     "local": tf(p.get_editor_property("local_transform"))}
    try:
        rec["has_top"] = bool(pair.get_editor_property("has_top"))
    except Exception: pass
    rows.append(rec)

# Mesh geometry: bounds + straight-edge test on the Y (width) axis
def straight_edge(mesh_path):
    out = {"bounds": None, "verts": None, "y_min_count": None, "y_max_count": None,
           "y_min_zspan": None, "y_max_zspan": None, "error": None}
    sm = unreal.EditorAssetLibrary.load_asset(mesh_path)
    if sm is None:
        out["error"] = "mesh did not load"; return out
    try:
        b = sm.get_bounding_box()
        out["bounds"] = {"min": [round(b.min.x,2), round(b.min.y,2), round(b.min.z,2)],
                         "max": [round(b.max.x,2), round(b.max.y,2), round(b.max.z,2)]}
    except Exception as exc:
        out["error"] = "bounds: " + repr(exc)
    try:
        dyn = unreal.DynamicMesh()
        opts = unreal.GeometryScriptCopyMeshFromAssetOptions()
        lod = unreal.GeometryScriptMeshReadLOD()
        res = unreal.GeometryScript_StaticMesh.copy_mesh_from_static_mesh(sm, dyn, opts, lod)
        dyn2 = res[0] if isinstance(res, tuple) else res
        vl = unreal.GeometryScriptVectorList()
        q = unreal.GeometryScript_MeshQueries.get_all_vertex_positions(dyn2, vl, False)
        vl2 = q[0] if isinstance(q, tuple) else q
        arr = unreal.GeometryScript_List.convert_vector_list_to_array(vl2)
        ys = [v.y for v in arr]; zs = [v.z for v in arr]
        if not ys: raise RuntimeError("no vertices")
        y0, y1 = min(ys), max(ys); w = max(1e-6, y1 - y0); eps = 0.005 * w
        zmin_all, zmax_all = min(zs), max(zs); h = max(1e-6, zmax_all - zmin_all)
        lo = [z for y, z in zip(ys, zs) if abs(y - y0) < eps]
        hi = [z for y, z in zip(ys, zs) if abs(y - y1) < eps]
        out.update({"verts": len(ys), "width": round(w,2), "height": round(h,2),
                    "y_min_count": len(lo), "y_max_count": len(hi),
                    "y_min_zspan": round((max(lo)-min(lo))/h, 3) if lo else 0.0,
                    "y_max_zspan": round((max(hi)-min(hi))/h, 3) if hi else 0.0})
    except Exception as exc:
        out["error"] = (out["error"] or "") + " | geom: " + repr(exc)
    return out

meshes = {m: straight_edge(m) for m in sorted(unique_meshes) if m}
payload = {"world": EXPECTED_WORLD, "row_count": len(rows), "rows": rows,
           "library": library_info, "meshes": meshes,
           "dirty_content": [pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
           "dirty_maps": [pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexWingHandedness2", "rows_dump.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=1, sort_keys=True, default=str)
geom_ok = sum(1 for m in meshes.values() if m.get("verts"))
unreal.log(f"PUSS_WING_DUMP_SUCCESS|rows={len(rows)}|meshes={len(meshes)}|geom_ok={geom_ok}|dirty={len(payload['dirty_content'])+len(payload['dirty_maps'])}")
