"""Read-only: source resolution of every colour texture the live wings render, with panel size."""
import json, os
import unreal
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MEL = unreal.MaterialEditingLibrary
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w = editor.get_editor_world()
assert w is not None and w.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "Unexpected world"
assert editor.get_game_world() is None, "PIE active"
def pkg(v): return v.get_path_name().split(".", 1)[0] if v is not None else None
def dirty():
    return sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
                  | {pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()})
before = dirty()
rows, seen = [], set()
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        mesh = comp.get_editor_property("static_mesh")
        if mesh is None or pkg(mesh) in seen:
            continue
        seen.add(pkg(mesh))
        mat = comp.get_materials()[0] if comp.get_materials() else None
        tex = None
        for name in ("BaseColor", "DiffuseColorMap"):
            try:
                t = MEL.get_material_instance_texture_parameter_value(mat, name)
                if t is not None and "/Engine/" not in pkg(t):
                    tex = t; break
            except Exception:
                pass
        b = mesh.get_bounding_box()
        ext = b.max - b.min
        rec = {"mesh": pkg(mesh), "material": pkg(mat), "texture": pkg(tex),
               "bounds_cm": [round(ext.x, 1), round(ext.y, 1), round(ext.z, 1)]}
        if tex is not None:
            rec["size"] = [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()]
            try:
                rec["compression"] = str(tex.get_editor_property("compression_settings"))
                rec["max_size"] = tex.get_editor_property("max_texture_size")
                rec["lod_group"] = str(tex.get_editor_property("lod_group"))
            except Exception:
                pass
        rows.append(rec)
after = dirty()
assert after == before, f"dirty changed {after}"
with open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexWingMateriality", "texture_sizes.json"), "w") as fh:
    json.dump(rows, fh, indent=1)
unreal.log(f"PUSS_WING_TEXTURE_SIZES_SUCCESS|meshes={len(rows)}|dirty={len(before)}")
