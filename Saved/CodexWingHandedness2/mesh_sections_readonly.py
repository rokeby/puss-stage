"""Read-only: per material section, the slot name and mean normal X (which way the Front face points)."""
import json, os, re
import unreal
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LABEL_RE = re.compile(r"^P\d{2} Wing \d{3}$")
def pkg(v): return v.get_path_name().split(".", 1)[0] if v is not None and hasattr(v, "get_path_name") else None
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
meshes = set()
for cue in show.get_editor_property("cues"):
    if not LABEL_RE.match(str(cue.get_editor_property("label"))): continue
    pair = cue.get_editor_property("wing_pair")
    for side in ("left", "right"):
        m = pkg(pair.get_editor_property(side).get_editor_property("mesh"))
        if m: meshes.add(m)
result = {}
for path in sorted(meshes):
    sm = unreal.EditorAssetLibrary.load_asset(path)
    rec = {"sections": [], "error": None}
    try:
        mats = sm.get_editor_property("static_materials")
        for s in range(sm.get_num_sections(0)):
            r = unreal.ProceduralMeshLibrary.get_section_from_static_mesh(sm, 0, s)
            v, nrm = r[0], r[2]
            n = len(nrm)
            mx = sum(x.x for x in nrm)/n if n else None
            my = sum(x.y for x in nrm)/n if n else None
            slot = str(mats[s].get_editor_property("material_slot_name")) if s < len(mats) else "?"
            mat = mats[s].get_editor_property("material_interface") if s < len(mats) else None
            rec["sections"].append({"index": s, "slot": slot, "material": pkg(mat), "verts": len(v),
                                    "mean_nx": round(mx, 3) if mx is not None else None,
                                    "mean_ny": round(my, 3) if my is not None else None})
    except Exception as exc:
        rec["error"] = repr(exc)
    result[path] = rec
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexWingHandedness2", "mesh_sections.json")
with open(out, "w", encoding="utf-8") as fh: json.dump(result, fh, indent=1, sort_keys=True)
unreal.log(f"PUSS_WING_SECTIONS_SUCCESS|meshes={len(result)}|errors={sum(1 for r in result.values() if r['error'])}")
