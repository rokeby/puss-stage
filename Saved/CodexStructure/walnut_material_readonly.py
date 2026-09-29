"""Read-only: the walnut slab's material, its parent, the parameters that set
its scale, and whether its parent is flagged for instanced meshes (the boards
are instanced). Mutates nothing."""
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "walnut_material.json")
MEL = unreal.MaterialEditingLibrary
rep = {}
for path in ("/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup",
             "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst",
             "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Strp_02_Mat_Inst"):
    mi = unreal.EditorAssetLibrary.load_asset(path)
    if not mi:
        rep[path] = "missing"
        continue
    parent = mi.get_editor_property("parent")
    r = {"class": mi.get_class().get_name(), "parent": parent.get_path_name() if parent else None, "scalars": {}, "textures": {}}
    for n in MEL.get_scalar_parameter_names(mi):
        r["scalars"][str(n)] = MEL.get_material_instance_scalar_parameter_value(mi, n)
    for n in MEL.get_texture_parameter_names(mi):
        t = MEL.get_material_instance_texture_parameter_value(mi, n)
        r["textures"][str(n)] = t.get_path_name() if t else None
    base = mi.get_base_material()
    r["base"] = base.get_path_name() if base else None
    for flag in ("used_with_instanced_static_meshes", "used_with_static_lighting"):
        try:
            r[flag] = bool(base.get_editor_property(flag))
        except Exception as exc:
            r[flag] = f"unreadable: {exc}"
    rep[path] = r
json.dump(rep, open(OUT, "w"), indent=1)
unreal.log(f"WALNUT_MATERIAL_OK|{json.dumps(rep)[:1500]}|mutated=0")
