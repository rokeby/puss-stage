"""Read-only: what material each wing actually renders with, and what the masters expose.

The 18 Sept survey read only mesh default slots. The Show can override materials
per panel (FInfinityPanelDesign.MaterialOverrides) and the Passage actor applies
those to its managed ISMs, so this reads the live components as the authority.
Writes Saved/CodexWingMateriality/rendered_materials.json. Mutates nothing.
"""
import collections
import json
import os
import re

import unreal

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RELIEF_MASTER = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master"
EDGE_MASTER = "/Game/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Edge"
LEGACY_BASE = "/InterchangeAssets/Materials/FBXLegacyPhongSurfaceMaterial"
UNUSED_RELIEF_DIRS = [
    "/Game/Scenes/Wings/Passage03_ShrineToForgetting/Materials/Instances",
    "/Game/Scenes/Wings/Passage05_BirdToMountain/Materials/Instances",
]
OUT = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingMateriality", "rendered_materials.json")
MEL = unreal.MaterialEditingLibrary


def require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def pkg(v):
    if v is None:
        return None
    return v.get_path_name().split(".", 1)[0] if hasattr(v, "get_path_name") else str(v).split(".", 1)[0]


def dirty():
    return sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
                  | {pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()})


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{exc!r}"[:200]


def describe_base(mat):
    rec = {"path": pkg(mat)}
    for prop in ("blend_mode", "shading_model", "two_sided", "used_with_instanced_static_meshes",
                 "tangent_space_normal", "opacity_mask_clip_value", "dithered_lod_transition"):
        rec[prop] = str(safe(mat.get_editor_property, prop))
    rec["scalars"] = {str(n): safe(MEL.get_material_default_scalar_parameter_value, mat, n)
                      for n in safe(MEL.get_scalar_parameter_names, mat) or []}
    rec["vectors"] = {str(n): str(safe(MEL.get_material_default_vector_parameter_value, mat, n))
                      for n in safe(MEL.get_vector_parameter_names, mat) or []}
    rec["textures"] = {str(n): pkg(safe(MEL.get_material_default_texture_parameter_value, mat, n))
                       for n in safe(MEL.get_texture_parameter_names, mat) or []}
    rec["switches"] = {str(n): safe(MEL.get_material_default_static_switch_parameter_value, mat, n)
                       for n in safe(MEL.get_static_switch_parameter_names, mat) or []}
    rec["num_expressions"] = safe(MEL.get_num_material_expressions, mat)
    # Node classes, if this build exposes the expression list to Python.
    exprs = None
    for getter in ("get_material_expressions",):
        fn = getattr(MEL, getter, None)
        if fn:
            exprs = safe(fn, mat)
    if exprs is None:
        exprs = safe(mat.get_editor_property, "expressions")
    if isinstance(exprs, (list, tuple)) or hasattr(exprs, "__iter__") and not isinstance(exprs, str):
        rec["expression_classes"] = dict(collections.Counter(e.get_class().get_name() for e in exprs))
    else:
        rec["expression_classes"] = str(exprs)
    return rec


def describe_instance(mi):
    rec = {"path": pkg(mi), "parent": pkg(safe(mi.get_editor_property, "parent")),
           "base": pkg(safe(mi.get_base_material))}
    rec["scalars"] = {str(n): safe(MEL.get_material_instance_scalar_parameter_value, mi, n)
                      for n in safe(MEL.get_scalar_parameter_names, mi) or []}
    rec["textures"] = {str(n): pkg(safe(MEL.get_material_instance_texture_parameter_value, mi, n))
                       for n in safe(MEL.get_texture_parameter_names, mi) or []}
    rec["vectors"] = {str(n): str(safe(MEL.get_material_instance_vector_parameter_value, mi, n))
                      for n in safe(MEL.get_vector_parameter_names, mi) or []}
    try:
        ov = mi.get_editor_property("base_property_overrides")
        rec["override_two_sided"] = bool(ov.get_editor_property("override_two_sided"))
        rec["two_sided"] = bool(ov.get_editor_property("two_sided"))
    except Exception:  # noqa: BLE001
        pass
    return rec


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
require(world is not None, "No editor world")
require(world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD,
        f"Unexpected world {world.get_path_name()} - wrong editor/port?")
require(editor.get_game_world() is None, "PIE/SIE is active")
dirty_before = dirty()

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, "Show did not load")

# 1. Show panels: overrides and flips, per mesh.
label_re = re.compile(r"^P(?P<p>\d{2}) Wing \d{3}$")
show_panels = collections.defaultdict(lambda: {"occurrences": 0, "flipped": 0, "overrides": collections.Counter(),
                                               "passages": collections.Counter(), "roles": collections.Counter()})
for cue in show.get_editor_property("cues"):
    m = label_re.match(str(cue.get_editor_property("label")))
    if not m:
        continue
    pair = cue.get_editor_property("wing_pair")
    sides = ["left", "right"] + (["top"] if pair.get_editor_property("has_top") else [])
    for side in sides:
        panel = pair.get_editor_property(side)
        mesh = pkg(panel.get_editor_property("mesh"))
        if not mesh:
            continue
        rec = show_panels[mesh]
        rec["occurrences"] += 1
        rec["passages"]["P" + m.group("p")] += 1
        rec["roles"][side] += 1
        rec["flipped"] += int(bool(panel.get_editor_property("flip_image_horizontally")))
        ov = tuple(pkg(x) for x in panel.get_editor_property("material_overrides"))
        rec["overrides"][json.dumps(ov)] += 1

# 2. Live managed ISMs: the materials actually rendered.
components = []
actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for actor in actor_sub.get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        if "InfinityStage.Managed" not in [str(t) for t in comp.get_editor_property("component_tags")]:
            continue
        mesh = comp.get_editor_property("static_mesh")
        components.append({
            "actor": actor.get_actor_label(),
            "mesh": pkg(mesh),
            "instances": comp.get_instance_count(),
            "rendered": [pkg(x) for x in comp.get_materials()],
            "num_custom_data_floats": safe(comp.get_editor_property, "num_custom_data_floats"),
        })

# 3. Distinct rendered materials, classified by base.
rendered = sorted({m for c in components for m in c["rendered"] if m})
by_base = collections.Counter()
instances = {}
for path in rendered:
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if isinstance(asset, unreal.MaterialInstance):
        d = describe_instance(asset)
        instances[path] = d
        by_base[d["base"]] += 1
    else:
        by_base[path] += 1

# 4. Relief MIs that exist on disk but may be unused.
unused_relief = {}
for folder in UNUSED_RELIEF_DIRS:
    for path in unreal.EditorAssetLibrary.list_assets(folder, recursive=False):
        p = path.split(".", 1)[0]
        asset = unreal.EditorAssetLibrary.load_asset(p)
        if isinstance(asset, unreal.MaterialInstance):
            d = describe_instance(asset)
            d["rendered_anywhere"] = p in rendered
            unused_relief[p] = d

payload = {
    "world": EXPECTED_WORLD,
    "dirty_before": dirty_before,
    "show_panels": {k: {**v, "overrides": dict(v["overrides"]), "passages": dict(v["passages"]),
                        "roles": dict(v["roles"])} for k, v in sorted(show_panels.items())},
    "components": components,
    "rendered_by_base": dict(by_base),
    "rendered_instances": instances,
    "masters": {p: describe_base(unreal.EditorAssetLibrary.load_asset(p))
                for p in (RELIEF_MASTER, EDGE_MASTER, LEGACY_BASE)},
    "unused_relief_candidates": unused_relief,
}
payload["dirty_after"] = dirty()
require(payload["dirty_after"] == dirty_before, f"Dirty set changed: {payload['dirty_after']}")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=1, sort_keys=True, default=str)
unreal.log(f"PUSS_WING_RENDERED_MATERIALS_SUCCESS|components={len(components)}|rendered={len(rendered)}"
           f"|dirty={len(dirty_before)}")
