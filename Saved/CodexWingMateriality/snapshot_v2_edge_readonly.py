"""Read-only: record M_StageOpeningV2_Edge exactly (properties, nodes, wiring) and who uses it."""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL
PATH = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"
wm.editor_ready()
before = wm.dirty()
mat = unreal.EditorAssetLibrary.load_asset(PATH)
props = {p: str(mat.get_editor_property(p)) for p in (
    "blend_mode", "shading_model", "two_sided", "used_with_instanced_static_meshes", "used_with_nanite",
    "use_material_attributes", "opacity_mask_clip_value")}
nodes = []
for e in MEL.get_material_expressions(mat):
    r = {"class": e.get_class().get_name(), "name": e.get_name()}
    for p in ("parameter_name", "default_value", "group"):
        try:
            v = e.get_editor_property(p)
            r[p] = [v.r, v.g, v.b, v.a] if isinstance(v, unreal.LinearColor) else (str(v) if p != "default_value" else v)
        except Exception:
            pass
    nodes.append(r)
wiring = {}
for prop in ("MP_BASE_COLOR", "MP_ROUGHNESS", "MP_SPECULAR", "MP_METALLIC", "MP_NORMAL", "MP_EMISSIVE_COLOR"):
    n = MEL.get_material_property_input_node(mat, getattr(unreal.MaterialProperty, prop))
    if n:
        wiring[prop] = [n.get_name(), str(MEL.get_material_property_input_node_output_name(mat, getattr(unreal.MaterialProperty, prop)))]
users = {}
bounds = wm.read_json("mesh_bounds.json")
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        if any(wm.pkg(m) == PATH for m in comp.get_materials()):
            m = wm.pkg(comp.get_editor_property("static_mesh"))
            b = bounds[m]
            users[m] = (b[1] - b[0]) / 2.0
wm.require(wm.dirty() == before, "dirty changed")
wm.write_json("v2_edge_original.json", {"path": PATH, "props": props, "nodes": nodes, "wiring": wiring,
                                        "users_half_thickness_cm": users})
unreal.log(f"PUSS_WING_V2EDGE_SNAPSHOT_SUCCESS|nodes={len(nodes)}|users={len(users)}")
