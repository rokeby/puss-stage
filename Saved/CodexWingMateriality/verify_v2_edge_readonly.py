"""Read-only: confirm M_StageOpeningV2_Edge is wired to the canvas graph; check the extra referencers."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL
V2EDGE = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"
wm.editor_ready()
before = wm.dirty()
mat = unreal.EditorAssetLibrary.load_asset(V2EDGE)
out = {"wiring": {}, "params": {}}
for prop in ("MP_BASE_COLOR", "MP_ROUGHNESS", "MP_SPECULAR"):
    n = MEL.get_material_property_input_node(mat, getattr(unreal.MaterialProperty, prop))
    desc = ""
    try:
        desc = str(n.get_editor_property("description"))
    except Exception:
        pass
    pname = ""
    try:
        pname = str(n.get_editor_property("parameter_name"))
    except Exception:
        pass
    out["wiring"][prop] = [n.get_class().get_name() if n else None, desc, pname]
for e in MEL.get_material_expressions(mat):
    try:
        out["params"][str(e.get_editor_property("parameter_name"))] = str(e.get_editor_property("group"))
    except Exception:
        pass
out["flags"] = [bool(mat.get_editor_property("used_with_instanced_static_meshes")), bool(mat.get_editor_property("used_with_nanite"))]
curtain = "/Game/Scenes/Wings/FireSafetyCurtain/StaticMeshes/SM_FireSafetyCurtain_01"
sm = unreal.EditorAssetLibrary.load_asset(curtain)
b = sm.get_bounding_box()
out["curtain_bounds_x"] = [b.min.x, b.max.x]
placed = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    for c in a.get_components_by_class(unreal.StaticMeshComponent):
        if wm.pkg(c.get_editor_property("static_mesh")) == curtain:
            placed.append(a.get_actor_label())
out["curtain_placed_in"] = placed
wm.require(wm.dirty() == before, "dirty changed")
wm.write_json("verify_v2_edge.json", out)
unreal.log(f"PUSS_WING_V2EDGE_VERIFY_SUCCESS|dirty={len(before)}")
