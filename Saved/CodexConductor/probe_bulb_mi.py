"""READ-ONLY: bulb mesh bounds + material slots + Glow MI scalar/vector params. PROBE_BULB_OK|json"""
import json
def main():
    import unreal
    out = {}
    m = unreal.load_asset("/Game/InfinityStage/Lighting/Fixtures/Meshes/SM_Bulb_A60_Frost")
    b = m.get_bounding_box()
    out["bounds"] = [round(b.max.x - b.min.x, 1), round(b.max.y - b.min.y, 1), round(b.max.z - b.min.z, 1), round(b.min.z, 1)]
    out["slots"] = [str(s.material_slot_name) + "=" + (s.material_interface.get_name() if s.material_interface else "None") for s in m.static_materials]
    mi = unreal.load_asset("/Game/InfinityStage/Lighting/Fixtures/Materials/MI_SM_Bulb_A60_Frost_Glow")
    out["mi_scalars"] = {str(p.parameter_info.name): p.parameter_value for p in mi.get_editor_property("scalar_parameter_values")}
    par = mi.get_editor_property("parent")
    out["parent"] = par.get_path_name()
    out["parent_scalars"] = [str(x) for x in unreal.MaterialEditingLibrary.get_scalar_parameter_names(par)]
    unreal.log("PROBE_BULB_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_BULB_FAILED|%r" % (exc,))
