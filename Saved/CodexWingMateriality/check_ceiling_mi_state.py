"""Read-only: current in-memory OpacityMask/BaseColor on the ceiling MI, and texture override list."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
wm.editor_ready()
MI = "/Game/Scenes/Wings/Passage05_BirdToMountain/Materials/Instances/MI_CloudCeilingSmall_02_C_Relief"
mi = unreal.EditorAssetLibrary.load_asset(MI)
vals = {n: wm.pkg(wm.MEL.get_material_instance_texture_parameter_value(mi, n)) for n in ("BaseColor", "OpacityMask", "Height", "Normal")}
ov = []
for p in mi.get_editor_property("texture_parameter_values"):
    info = p.get_editor_property("parameter_info")
    ov.append([str(info.get_editor_property("name")), str(info.get_editor_property("association")),
               int(info.get_editor_property("index")), wm.pkg(p.get_editor_property("parameter_value"))])
wm.write_json("ceiling_mi_state.json", {"values": vals, "overrides": ov, "dirty": wm.dirty()})
unreal.log(f"PUSS_WING_CEILING_MI_STATE|{vals['OpacityMask']}|overrides={len(ov)}")
