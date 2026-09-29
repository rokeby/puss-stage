"""Read-only: the kit master and its two presets exist, are wired as intended, and carry the usage flags."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL
K = "/Game/Scenes/Wings/PaintedSurface/Kit/"
wm.editor_ready()
before = wm.dirty()
m = unreal.EditorAssetLibrary.load_asset(K + "M_Kit_Surface_Master")
out = {"master": {"ism": bool(m.get_editor_property("used_with_instanced_static_meshes")),
                  "nanite": bool(m.get_editor_property("used_with_nanite")),
                  "tangent_space_normal": bool(m.get_editor_property("tangent_space_normal")),
                  "expressions": MEL.get_num_material_expressions(m)}}
for name in ("MI_Kit_WalnutPlank", "MI_Kit_SteelGroove"):
    mi = unreal.EditorAssetLibrary.load_asset(K + name)
    out[name] = {"parent": wm.pkg(mi.get_editor_property("parent")),
                 "IsMetal": MEL.get_material_instance_static_switch_parameter_value(mi, "IsMetal"),
                 "WoodColor": wm.pkg(MEL.get_material_instance_texture_parameter_value(mi, "WoodColor")),
                 "TileLengthCm": MEL.get_material_instance_scalar_parameter_value(mi, "TileLengthCm")}
wm.require(wm.dirty() == before, "dirty changed")
wm.write_json("verify_kit.json", out)
unreal.log(f"PUSS_WING_KIT_VERIFY_SUCCESS|dirty={len(before)}")
