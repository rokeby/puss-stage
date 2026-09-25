"""In-memory (this editor session): silence exterior lighting inside loaded Level Instances so PIE matches the editor.
Sets sun/skylight AffectsWorld off + hidden in game, hides atmosphere/fog/cloud/sky-sphere in game. Not persisted."""
import json, os
import unreal
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
done = []
for cls in (unreal.DirectionalLight, unreal.SkyLight, unreal.SkyAtmosphere, unreal.ExponentialHeightFog, unreal.VolumetricCloud, unreal.StaticMeshActor):
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, cls):
        label = a.get_actor_label(); level = a.get_outer().get_path_name() if a.get_outer() else ""
        if "_LevelInstance_" not in level: continue
        if cls is unreal.StaticMeshActor and "sky" not in label.lower(): continue
        a.set_actor_hidden_in_game(True)
        try:
            c = a.get_component_by_class(unreal.LightComponentBase)
            if c:
                c.set_editor_property("affects_world", False)
        except Exception: pass
        try:
            for comp in a.get_components_by_class(unreal.SceneComponent): comp.set_visibility(False, True)
        except Exception: pass
        done.append({"label": label, "level": level.split("/")[-1][:60]})
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "suppress_foreign_sky_result.json")
with open(out, "w", encoding="utf-8") as fh: json.dump(done, fh, indent=1)
unreal.log(f"FOREIGN_SKY_SUPPRESSED_SESSION|actors={len(done)}|persisted=0")
