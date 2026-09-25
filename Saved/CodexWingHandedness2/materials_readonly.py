"""Read-only: for each wing mesh, Front/Back material paths and whether they render two-sided."""
import json, os, re
import unreal
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LABEL_RE = re.compile(r"^P\d{2} Wing \d{3}$")
def pkg(v): return v.get_path_name().split(".", 1)[0] if v is not None and hasattr(v, "get_path_name") else None
def two_sided(mat):
    info = {"two_sided": None, "base": None, "override": None}
    try:
        if isinstance(mat, unreal.MaterialInstance):
            base = mat.get_base_material(); info["base"] = pkg(base)
            info["two_sided"] = bool(base.get_editor_property("two_sided")) if base else None
            try:
                ov = mat.get_editor_property("base_property_overrides")
                if bool(ov.get_editor_property("override_two_sided")):
                    info["override"] = bool(ov.get_editor_property("two_sided")); info["two_sided"] = info["override"]
            except Exception: pass
        elif isinstance(mat, unreal.Material):
            info["two_sided"] = bool(mat.get_editor_property("two_sided")); info["base"] = pkg(mat)
    except Exception as exc:
        info["error"] = repr(exc)
    return info
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
    rec = {}
    for i, sm_mat in enumerate(sm.get_editor_property("static_materials")):
        slot = str(sm_mat.get_editor_property("material_slot_name")); mat = sm_mat.get_editor_property("material_interface")
        rec[slot] = {"material": pkg(mat), **two_sided(mat)}
    result[path] = rec
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexWingHandedness2", "materials.json")
with open(out, "w", encoding="utf-8") as fh: json.dump(result, fh, indent=1, sort_keys=True)
unreal.log(f"PUSS_WING_MATERIALS_SUCCESS|meshes={len(result)}")
