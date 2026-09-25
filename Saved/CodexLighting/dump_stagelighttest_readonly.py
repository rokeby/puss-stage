"""Read-only: every actor under the Stagelighttest outliner folder, with transforms, meshes, parenting and light settings."""
import json, os
import unreal
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem); world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "unexpected world"
assert ed.get_game_world() is None, "PIE active"
def pkg(v): return v.get_path_name().split(".", 1)[0] if v is not None and hasattr(v, "get_path_name") else None
def vec(v): return [round(v.x, 2), round(v.y, 2), round(v.z, 2)]
def rot(r): return [round(r.pitch, 3), round(r.yaw, 3), round(r.roll, 3)]
def props(o, names):
    out = {}
    for n in names:
        try:
            v = o.get_editor_property(n)
            if isinstance(v, (unreal.LinearColor,)): v = [round(v.r,3), round(v.g,3), round(v.b,3)]
            elif isinstance(v, unreal.Color): v = [v.r, v.g, v.b]
            elif isinstance(v, unreal.Vector): v = vec(v)
            elif not isinstance(v, (int, float, bool, str)) and v is not None: v = str(v)
            out[n] = v
        except Exception: pass
    return out
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = []
for a in sub.get_all_level_actors():
    folder = str(a.get_folder_path())
    if not folder.startswith("Stagelighttest"): continue
    rec = {"label": a.get_actor_label(), "class": a.get_class().get_name(), "folder": folder,
           "loc": vec(a.get_actor_location()), "rot": rot(a.get_actor_rotation()), "scale": vec(a.get_actor_scale3d()),
           "parent": a.get_attach_parent_actor().get_actor_label() if a.get_attach_parent_actor() else None,
           "hidden_game": bool(a.get_editor_property("hidden")), "hidden_editor": bool(a.is_temporarily_hidden_in_editor())}
    smc = a.get_component_by_class(unreal.StaticMeshComponent)
    if smc and not isinstance(a, unreal.Light):
        rec["mesh"] = pkg(smc.get_editor_property("static_mesh"))
        try:
            b = a.get_actor_bounds(True); rec["bounds_origin"] = vec(b[0]); rec["bounds_extent"] = vec(b[1])
        except Exception: pass
    lc = a.get_component_by_class(unreal.LightComponent)
    if lc:
        rec["light"] = props(lc, ["intensity", "intensity_units", "light_color", "temperature", "use_temperature", "attenuation_radius",
                                  "inner_cone_angle", "outer_cone_angle", "source_radius", "soft_source_radius", "source_length",
                                  "source_width", "source_height", "barn_door_angle", "barn_door_length", "cast_shadows", "mobility",
                                  "indirect_lighting_intensity", "volumetric_scattering_intensity", "specular_scale", "affects_world",
                                  "lighting_channels", "ies_texture", "use_ies_brightness", "ies_brightness_scale", "light_function_material"])
        rec["light"]["visible"] = bool(lc.get_editor_property("visible"))
    actors.append(rec)
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "stagelighttest_dump.json")
with open(out, "w", encoding="utf-8") as fh: json.dump(actors, fh, indent=1, default=str)
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"PUSS_STAGELIGHTTEST_DUMP_SUCCESS|actors={len(actors)}|dirty={dirty}")
