"""Give M_StageOpeningV2_Edge the canvas-edge look (batten core, canvas lip, fray) IN PLACE,
WITHOUT DELETING ANY EXPRESSION.

History: the first version cleared this material node by node, and
DeleteMaterialExpression hit "Assertion failed: !IsRooted()" and crashed the editor
(2026-09-28 23:17; nothing saved, the asset was untouched). This material's existing
nodes are rooted, and a Python check can't see that, so this version:
  - renames the 3 original parameters to Legacy_EdgeColor / Legacy_Roughness /
    Legacy_Specular and leaves them in place, disconnected (inert);
  - adds the canvas-edge nodes (edge_graph from build_painted_surface_master) and wires
    the material outputs to them;
  - is idempotent: if the canvas graph is already present it only rewires, adding nothing.
It's a Material used directly by the edge slot of all 75 V2 meshes (every one 10 cm,
HalfThicknessCm 5). It sets ISM and Nanite usage explicitly and saves only this asset.
Live undo: restore_v2_edge_original.py rewires the outputs back to the Legacy_ nodes.
Backup: Backups/PreV2EdgeRebuild-20260928-231623.
"""
import importlib.util, os
import unreal
here = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("_wm_common", os.path.join(here, "_wm_common.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
bspec = importlib.util.spec_from_file_location("wm_builder", os.path.join(here, "build_painted_surface_master.py"))
builder = importlib.util.module_from_spec(bspec)
builder.WM_IMPORT_ONLY = True
bspec.loader.exec_module(builder)
MEL = wm.MEL
V2EDGE = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"
LEGACY = {"EdgeColor": "Legacy_EdgeColor", "Roughness": "Legacy_Roughness", "Specular": "Legacy_Specular"}
CANVAS_DESC = "Batten core, canvas lip, fray"


def param_name(e):
    try:
        return str(e.get_editor_property("parameter_name"))
    except Exception:  # noqa: BLE001
        return None


wm.editor_ready()
before = wm.dirty()
wm.require(V2EDGE not in before, "M_StageOpeningV2_Edge is already dirty - refusing")
snap = wm.read_json("v2_edge_original.json")
wm.require(set(snap["users_half_thickness_cm"].values()) == {5.0}, "a user of this edge is not 10 cm thick")
refs = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(V2EDGE, False)]
mat = unreal.EditorAssetLibrary.load_asset(V2EDGE)
exprs = list(MEL.get_material_expressions(mat))
start_count = len(exprs)
canvas = [e for e in exprs if e.get_class().get_name() == "MaterialExpressionCustom"
          and str(e.get_editor_property("description")) == CANVAS_DESC]
MP = unreal.MaterialProperty


def group(e):
    try:
        return str(e.get_editor_property("group"))
    except Exception:  # noqa: BLE001
        return None


# Tell the nodes apart by group, not name: canvas parameters are in group "Edge", the 3
# originals have no group. Normalise names the same way on every run (fresh, re-run, or
# after restore_v2_edge_original.py, which renames the canvas Specular to Canvas_Specular).
# Renaming is safe; deleting is what crashed.
originals = [e for e in exprs if param_name(e) is not None and group(e) != "Edge"]
wm.require(len(originals) == 3, f"expected the 3 original parameters, found {[param_name(e) for e in originals]}")
for e in originals:
    base = param_name(e).replace("Legacy_", "")
    wm.require(base in LEGACY, f"unexpected original parameter {param_name(e)}")
    e.set_editor_property("parameter_name", LEGACY[base])
if canvas:
    # Idempotent re-run: rewire outputs to the existing canvas graph and add nothing.
    node = canvas[0]
    spec_nodes = [e for e in exprs if group(e) == "Edge" and param_name(e) in ("Specular", "Canvas_Specular")]
    wm.require(len(spec_nodes) == 1, f"expected exactly one canvas Specular parameter, found {len(spec_nodes)}")
    spec_nodes[0].set_editor_property("parameter_name", "Specular")
    wm.require(MEL.connect_material_property(node, "", MP.MP_BASE_COLOR), "rewire base colour")
    wm.require(MEL.connect_material_property(node, "OutRoughness", MP.MP_ROUGHNESS), "rewire roughness")
    wm.require(MEL.connect_material_property(spec_nodes[0], "", MP.MP_SPECULAR), "rewire specular")
    mat.set_editor_property("used_with_nanite", True)
    mode = "rewired"
else:
    builder.edge_graph(mat)
    mode = "added"
MEL.recompile_material(mat)
count = MEL.get_num_material_expressions(mat)
wm.require(count == start_count + (0 if canvas else 19), f"unexpected expression count {count} (from {start_count})")
wm.require(bool(mat.get_editor_property("used_with_instanced_static_meshes"))
           and bool(mat.get_editor_property("used_with_nanite")), "usage flags not set")
wm.require(unreal.EditorAssetLibrary.save_asset(V2EDGE, only_if_is_dirty=False), "save failed")
after = wm.dirty()
wm.require(set(after) <= set(before), f"Rebuild left new dirty packages: {sorted(set(after) - set(before))}")
wm.write_json("rebuild_v2_edge_result.json", {"mode": mode, "expressions": count, "referencers": refs,
                                              "dirty_after": after})
unreal.log(f"PUSS_WING_V2EDGE_REBUILD_SUCCESS|mode={mode}|expressions={count}|referencers={len(refs)}|dirty={len(after)}")
