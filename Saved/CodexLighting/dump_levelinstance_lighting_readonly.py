"""Read-only: lighting actors in ALL loaded levels (incl. Level Instances) via GameplayStatics, with owning level and flags."""
import json, os
import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
rows = []
for cls in (unreal.DirectionalLight, unreal.SkyLight, unreal.SkyAtmosphere, unreal.ExponentialHeightFog, unreal.VolumetricCloud, unreal.LevelInstance, unreal.StaticMeshActor):
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, cls):
        label = a.get_actor_label()
        if cls is unreal.StaticMeshActor and "sky" not in label.lower(): continue
        rec = {"label": label, "class": a.get_class().get_name(), "level": a.get_outer().get_path_name() if a.get_outer() else "?",
               "folder": str(a.get_folder_path()), "hidden_editor": bool(a.is_temporarily_hidden_in_editor()), "hidden_game": bool(a.get_editor_property("hidden"))}
        if cls is unreal.LevelInstance:
            try: rec["world_asset"] = str(a.get_editor_property("world_asset"))
            except Exception as exc: rec["world_asset"] = repr(exc)
        try:
            c = a.get_component_by_class(unreal.LightComponentBase)
            if c: rec["intensity"] = float(c.get_editor_property("intensity")); rec["affects_world"] = bool(c.get_editor_property("affects_world")); rec["comp_visible"] = bool(c.get_editor_property("visible"))
        except Exception: pass
        rows.append(rec)
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "levelinstance_lighting.json")
with open(out, "w", encoding="utf-8") as fh: json.dump(rows, fh, indent=1, default=str)
unreal.log(f"PUSS_LI_LIGHTING_SUCCESS|actors={len(rows)}")
