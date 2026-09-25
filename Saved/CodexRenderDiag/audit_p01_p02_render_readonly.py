"""Read-only comparison of Passage 01/02 render inputs. Does not modify assets."""
import json
import os
import unreal

OUT = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexRenderDiag",
    "p01_p02_render_audit.json",
)


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def value(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if hasattr(v, "get_path_name"):
        try:
            return v.get_path_name()
        except Exception:
            pass
    return str(v)


def texture_info(tex):
    sx = sy = mips = None
    for method, key in (("blueprint_get_size_x", "sx"), ("blueprint_get_size_y", "sy"), ("get_num_mips", "mips")):
        try:
            result = getattr(tex, method)()
            if key == "sx": sx = result
            elif key == "sy": sy = result
            else: mips = result
        except Exception:
            pass
    return {
        "path": tex.get_path_name(),
        "size": [sx, sy],
        "mips": mips,
        "srgb": value(prop(tex, "srgb")),
        "compression": value(prop(tex, "compression_settings")),
        "lod_group": value(prop(tex, "lod_group")),
        "lod_bias": value(prop(tex, "lod_bias")),
        "mip_gen": value(prop(tex, "mip_gen_settings")),
        "never_stream": value(prop(tex, "never_stream")),
        "virtual_texture_streaming": value(prop(tex, "virtual_texture_streaming")),
        "filter": value(prop(tex, "filter")),
    }


def assets_under(path, class_name=None):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    data = registry.get_assets_by_path(path, recursive=True)
    result = []
    for item in data:
        asset = item.get_asset()
        if asset and (class_name is None or asset.get_class().get_name() == class_name):
            result.append(asset)
    return result


def material_info(mi):
    textures = {}
    scalars = {}
    vectors = {}
    try:
        for name in unreal.MaterialEditingLibrary.get_texture_parameter_names(mi):
            tex = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi, name)
            textures[str(name)] = texture_info(tex) if tex else None
    except Exception as exc:
        textures["error"] = repr(exc)
    try:
        for name in unreal.MaterialEditingLibrary.get_scalar_parameter_names(mi):
            scalars[str(name)] = unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(mi, name)
    except Exception as exc:
        scalars["error"] = repr(exc)
    try:
        for name in unreal.MaterialEditingLibrary.get_vector_parameter_names(mi):
            vectors[str(name)] = value(unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(mi, name))
    except Exception as exc:
        vectors["error"] = repr(exc)
    return {
        "path": mi.get_path_name(),
        "parent": value(prop(mi, "parent")),
        "textures": textures,
        "scalars": scalars,
        "vectors": vectors,
    }


def mesh_info(mesh):
    materials = []
    try:
        materials = [value(slot.material_interface) for slot in mesh.get_editor_property("static_materials")]
    except Exception:
        pass
    try:
        lods = unreal.EditorStaticMeshLibrary.get_lod_count(mesh)
    except Exception:
        lods = None
    nanite = prop(mesh, "nanite_settings")
    return {
        "path": mesh.get_path_name(),
        "lods": lods,
        "materials": materials,
        "nanite_enabled": value(prop(nanite, "enabled")) if nanite else None,
        "light_map_coordinate_index": value(prop(mesh, "light_map_coordinate_index")),
    }


roots = {
    "p01": "/Game/Scenes/Wings/AnimalsLake",
    "p02": "/Game/Scenes/Wings/Passage02_AnimalsToShrineV2",
}
report = {"roots": {}, "camera_rigs": {}, "editor_lights": {}, "game_lights": {}, "world": {}}

for key, root in roots.items():
    mis = assets_under(root + "/Materials", "MaterialInstanceConstant")
    textures = assets_under(root + "/Textures", "Texture2D")
    meshes = assets_under(root + "/StaticMeshes", "StaticMesh")
    report["roots"][key] = {
        "counts": {"materials": len(mis), "textures": len(textures), "meshes": len(meshes)},
        "materials": [material_info(mi) for mi in mis],
        "textures": [texture_info(tex) for tex in textures],
        "meshes": [mesh_info(mesh) for mesh in meshes],
    }

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
editor_actors = actor_sub.get_all_level_actors()
for actor in editor_actors:
    label = actor.get_actor_label()
    if actor.get_class().get_name() == "InfinityStageCameraRig" and ("Passage 01" in label or "Passage 02" in label):
        cam = prop(actor, "camera")
        focus = prop(cam, "focus_settings")
        loc = cam.get_world_location() if cam else None
        report["camera_rigs"][label] = {
            "location": [loc.x, loc.y, loc.z] if loc else None,
            "focal_length_mm": value(prop(cam, "current_focal_length")),
            "aperture": value(prop(cam, "current_aperture")),
            "focus_method": value(prop(focus, "focus_method")),
            "manual_focus_distance_cm": value(prop(focus, "manual_focus_distance")),
        }


def light_summary(actors):
    rows = []
    for actor in actors:
        label = actor.get_actor_label() if hasattr(actor, "get_actor_label") else actor.get_name()
        if not (label.startswith("P01 Wing") or label.startswith("P02 Wing")):
            continue
        components = actor.get_components_by_class(unreal.LightComponentBase)
        for comp in components:
            rows.append({
                "label": label,
                "class": actor.get_class().get_name(),
                "hidden": bool(prop(actor, "hidden", False)),
                "hidden_editor": bool(prop(actor, "is_temporarily_hidden_in_editor", False)),
                "visible": value(prop(comp, "visible")),
                "affects_world": value(prop(comp, "affects_world")),
                "cast_shadows": value(prop(comp, "cast_shadows")),
                "intensity": value(prop(comp, "intensity")),
                "attenuation_radius": value(prop(comp, "attenuation_radius")),
                "volumetric_scattering_intensity": value(prop(comp, "volumetric_scattering_intensity")),
            })
    result = {}
    for pfx in ("P01", "P02"):
        subset = [r for r in rows if r["label"].startswith(pfx)]
        result[pfx] = {
            "total": len(subset),
            "visible_and_not_hidden": sum(1 for r in subset if r["visible"] and not r["hidden"]),
            "shadow_casting_visible": sum(1 for r in subset if r["visible"] and r["cast_shadows"] and not r["hidden"]),
            "with_volumetric_scattering": sum(1 for r in subset if r["visible"] and not r["hidden"] and (r["volumetric_scattering_intensity"] or 0) > 0),
            "max_radius": max([r["attenuation_radius"] or 0 for r in subset], default=0),
            "sample": subset[:12],
        }
    return result


report["editor_lights"] = light_summary(editor_actors)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
editor_world = editor.get_editor_world()
game_world = editor.get_game_world()
report["world"] = {
    "editor": editor_world.get_path_name() if editor_world else None,
    "game": game_world.get_path_name() if game_world else None,
    "dirty_content": [str(x) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
    "dirty_maps": [str(x) for x in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
}
if game_world:
    game_actors = unreal.GameplayStatics.get_all_actors_of_class(game_world, unreal.Actor)
    report["game_lights"] = light_summary(game_actors)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=1, default=str)
unreal.log(
    "PUSS_P01_P02_RENDER_AUDIT_SUCCESS|"
    f"p01_tex={report['roots']['p01']['counts']['textures']}|"
    f"p02_tex={report['roots']['p02']['counts']['textures']}|"
    f"p01_lights={report['editor_lights']['P01']['visible_and_not_hidden']}|"
    f"p02_lights={report['editor_lights']['P02']['visible_and_not_hidden']}|"
    f"pie={int(game_world is not None)}"
)
