"""Make the haze read: flatten the vertical falloff, thicken the medium, and let the
dim stage lights actually scatter. Applies to the editor world and, if PIE is up, to
the play world too so the change is visible immediately. No save."""
import json, os, unreal
EXPECTED_WORLD = "L_InfinityStage_V1VerticalSlice"
DENSITY = float(os.environ.get("PUSS_FOG_DENSITY", "0.09"))
FALLOFF = float(os.environ.get("PUSS_FOG_FALLOFF", "0.05"))
EXTINCTION = float(os.environ.get("PUSS_FOG_EXTINCTION", "1.6"))
SCATTER = float(os.environ.get("PUSS_LIGHT_SCATTER", "5.0"))
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
worlds = []
ew = ed.get_editor_world()
assert ew and EXPECTED_WORLD in ew.get_path_name(), "wrong project"
worlds.append(("editor", ew))
gw = ed.get_game_world()
if gw is not None:
    worlds.append(("pie", gw))
report = {}
for tag, w in worlds:
    fogs = [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.ExponentialHeightFog)
            if a.get_actor_label().startswith("Infinity Stage")]
    lights = [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Light) if " Wing " in a.get_actor_label()]
    for f in fogs:
        c = f.get_component_by_class(unreal.ExponentialHeightFogComponent)
        f.modify()
        c.set_editor_property("enable_volumetric_fog", True)
        c.set_editor_property("fog_density", DENSITY)
        # A 0.34 falloff thins the fog fast with height, so the upper corridor and
        # the gridiron space above the wings had almost no medium to light.
        c.set_editor_property("fog_height_falloff", FALLOFF)
        c.set_editor_property("volumetric_fog_extinction_scale", EXTINCTION)
        c.set_editor_property("volumetric_fog_distance", 30000.0)
        c.set_editor_property("volumetric_fog_scattering_distribution", 0.55)
    touched = 0
    for a in lights:
        lc = a.get_component_by_class(unreal.LightComponent)
        if lc:
            # The fixtures are 2-4 candelas; at scattering 1.0 they put almost
            # nothing into the medium. This is a fog-only multiplier - surface
            # lighting is unchanged.
            lc.set_editor_property("volumetric_scattering_intensity", SCATTER)
            touched += 1
    report[tag] = {"fogs": len(fogs), "lights": touched,
                   "fog_z": [round(f.get_actor_location().z) for f in fogs]}
json.dump({"density": DENSITY, "falloff": FALLOFF, "extinction": EXTINCTION, "scatter": SCATTER, "worlds": report},
          open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "haze_pass.json"), "w"), indent=1)
unreal.log(f"HAZE_PASS|density={DENSITY}|falloff={FALLOFF}|extinction={EXTINCTION}|scatter={SCATTER}|{report}|saved=0")
