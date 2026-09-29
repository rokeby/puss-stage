"""Live undo of rebuild_v2_edge.py, WITHOUT DELETING ANYTHING.

Rewires M_StageOpeningV2_Edge's outputs back to its original 3 parameter nodes (renamed
Legacy_* by the rebuild) and restores their names. It renames the canvas Specular so the
names don't collide, and resets the Nanite flag to its original value. The canvas nodes
stay behind, inert. Never delete expressions in this asset: its nodes are rooted, and
DeleteMaterialExpression crashes the editor.
"""
import importlib.util, os
import unreal
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(os.path.dirname(__file__), "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
MEL = wm.MEL
V2EDGE = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"

wm.editor_ready()
before = wm.dirty()
snap = wm.read_json("v2_edge_original.json")
mat = unreal.EditorAssetLibrary.load_asset(V2EDGE)
by_param = {}
for e in MEL.get_material_expressions(mat):
    try:
        by_param.setdefault(str(e.get_editor_property("parameter_name")), []).append(e)
    except Exception:  # noqa: BLE001
        pass
for canvas_spec in by_param.get("Specular", []):
    canvas_spec.set_editor_property("parameter_name", "Canvas_Specular")
MP = unreal.MaterialProperty
for legacy, original, prop, out in (("Legacy_EdgeColor", "EdgeColor", MP.MP_BASE_COLOR, "RGB"),
                                    ("Legacy_Roughness", "Roughness", MP.MP_ROUGHNESS, ""),
                                    ("Legacy_Specular", "Specular", MP.MP_SPECULAR, "")):
    nodes = by_param.get(legacy, [])
    wm.require(len(nodes) == 1, f"expected one {legacy} node, found {len(nodes)}")
    nodes[0].set_editor_property("parameter_name", original)
    wm.require(MEL.connect_material_property(nodes[0], out, prop), f"rewire {original}")
mat.set_editor_property("used_with_nanite", snap["props"]["used_with_nanite"] == "True")
MEL.recompile_material(mat)
wm.require(unreal.EditorAssetLibrary.save_asset(V2EDGE, only_if_is_dirty=False), "save failed")
wm.require(set(wm.dirty()) <= set(before), f"left new dirty packages: {sorted(set(wm.dirty()) - set(before))}")
unreal.log("PUSS_WING_V2EDGE_RESTORE_SUCCESS")
