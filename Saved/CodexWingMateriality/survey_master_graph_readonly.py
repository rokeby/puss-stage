"""Read-only: how the relief master is wired, and whether the wing meshes are Nanite.

Answers three questions the rendered-material survey raised:
- which channel of the OpacityMask parameter reaches Opacity Mask (so we know what
  the 39 unassigned relief MIs pointing at BambooScaffold_01_L would do),
- the BumpOffset settings (the only depth the master has today),
- whether the master's missing ISM usage flag matters (Nanite meshes skip it).
Writes Saved/CodexWingMateriality/master_graph.json. Mutates nothing.
"""
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
OUT = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingMateriality", "master_graph.json")
MEL = unreal.MaterialEditingLibrary


def require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def pkg(v):
    return v.get_path_name().split(".", 1)[0] if v is not None and hasattr(v, "get_path_name") else None


def dirty():
    return sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
                  | {pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()})


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{exc!r}"[:200]


def node_label(node):
    if node is None or isinstance(node, str):
        return node
    rec = {"class": node.get_class().get_name(), "name": node.get_name()}
    for prop in ("parameter_name", "height_ratio", "reference_plane", "const_coordinate", "sampler_type",
                 "r", "g", "b", "a"):
        v = safe(node.get_editor_property, prop)
        if not (isinstance(v, str) and v.startswith("ERR:")):
            rec[prop] = str(v)
    return rec


def walk(node, depth=0, seen=None):
    """Upstream chain from a node, with the output pin names used."""
    seen = seen if seen is not None else set()
    if node is None or isinstance(node, str) or node.get_name() in seen or depth > 8:
        return node_label(node)
    seen.add(node.get_name())
    rec = node_label(node)
    ins = safe(MEL.get_inputs_for_material_expression, MASTER_ASSET, node)
    names = safe(MEL.get_material_expression_input_names, node)
    if isinstance(ins, (list, tuple)):
        rec["inputs"] = []
        for i, up in enumerate(ins):
            label = names[i] if isinstance(names, (list, tuple)) and i < len(names) else str(i)
            if up is None:
                continue
            out_name = safe(MEL.get_input_node_output_name_for_material_expression, node, up)
            rec["inputs"].append({"pin": str(label), "from_output": str(out_name), "node": walk(up, depth + 1, seen)})
    return rec


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
require(world is not None and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD,
        "Unexpected world - wrong editor/port?")
require(editor.get_game_world() is None, "PIE/SIE is active")
dirty_before = dirty()

MASTER_ASSET = unreal.EditorAssetLibrary.load_asset(MASTER)
require(MASTER_ASSET is not None, "Master did not load")
props = {}
for name in ("MP_BASE_COLOR", "MP_NORMAL", "MP_OPACITY_MASK", "MP_ROUGHNESS", "MP_SPECULAR",
             "MP_METALLIC", "MP_AMBIENT_OCCLUSION", "MP_EMISSIVE_COLOR", "MP_WORLD_POSITION_OFFSET",
             "MP_PIXEL_DEPTH_OFFSET"):
    prop = getattr(unreal.MaterialProperty, name, None)
    if prop is None:
        props[name] = "no such enum"
        continue
    node = safe(MEL.get_material_property_input_node, MASTER_ASSET, prop)
    out = safe(MEL.get_material_property_input_node_output_name, MASTER_ASSET, prop)
    props[name] = {"from_output": str(out), "node": walk(node)}

usage = {}
for prop in ("used_with_instanced_static_meshes", "used_with_nanite", "used_with_static_lighting",
             "automatically_set_usage_in_editor", "enable_tessellation", "is_thin_surface"):
    usage[prop] = str(safe(MASTER_ASSET.get_editor_property, prop))

# Nanite status of every mesh the live wing components render.
nanite = {}
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in actor_sub.get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        mesh = comp.get_editor_property("static_mesh")
        p = pkg(mesh)
        if p and p not in nanite:
            settings = safe(mesh.get_editor_property, "nanite_settings")
            enabled = safe(settings.get_editor_property, "enabled") if not isinstance(settings, str) else settings
            nanite[p] = str(enabled)

payload = {"master": MASTER, "properties": props, "usage": usage, "nanite": nanite,
           "dirty_before": dirty_before, "dirty_after": dirty()}
require(payload["dirty_after"] == dirty_before, f"Dirty set changed: {payload['dirty_after']}")
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=1, sort_keys=True, default=str)
unreal.log(f"PUSS_WING_MASTER_GRAPH_SUCCESS|meshes={len(nanite)}|dirty={len(dirty_before)}")
