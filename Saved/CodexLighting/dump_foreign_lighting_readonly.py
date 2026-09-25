"""Read-only: every sky/sun/fog/cloud actor NOT under the Infinity Stage environment, with its owning level and visibility flags."""
import json, os
import unreal
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
rows = []
for a in sub.get_all_level_actors():
    cls = a.get_class().get_name()
    label = a.get_actor_label()
    if cls not in ("DirectionalLight", "SkyLight", "SkyAtmosphere", "ExponentialHeightFog", "VolumetricCloud", "StaticMeshActor", "PostProcessVolume"): continue
    if cls == "StaticMeshActor" and "sky" not in label.lower(): continue
    if label.startswith("Infinity Stage") : continue
    rec = {"label": label, "class": cls, "folder": str(a.get_folder_path()), "level": a.get_outer().get_outer().get_path_name() if a.get_outer() else "?",
           "hidden_editor": bool(a.is_temporarily_hidden_in_editor()), "hidden_game": bool(a.get_editor_property("hidden")),
           "parent": a.get_attach_parent_actor().get_actor_label() if a.get_attach_parent_actor() else None}
    try:
        c = a.get_component_by_class(unreal.LightComponentBase)
        if c: rec["intensity"] = float(c.get_editor_property("intensity")); rec["comp_visible"] = bool(c.get_editor_property("visible")); rec["affects_world"] = bool(c.get_editor_property("affects_world"))
    except Exception: pass
    rows.append(rec)
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "foreign_lighting.json")
with open(out, "w", encoding="utf-8") as fh: json.dump(rows, fh, indent=1, default=str)
unreal.log(f"PUSS_FOREIGN_LIGHTING_SUCCESS|actors={len(rows)}")
