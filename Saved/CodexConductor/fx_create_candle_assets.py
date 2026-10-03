"""Create and narrowly save the approved candle's entirely new assets."""
from __future__ import annotations

import datetime
import importlib
import json
import os
import sys

import unreal


# UE's embedded interpreter survives MCP calls; never trust a Saved module cache.
_SAVED_ROOT = os.path.normcase(os.path.abspath(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())))
for _module_name, _module in list(sys.modules.items()):
    _module_file = getattr(_module, "__file__", None) or ""
    if (_module_name != "__main__" and _module_file and
            os.path.normcase(os.path.abspath(_module_file)).startswith(
                _SAVED_ROOT + os.sep)):
        sys.modules.pop(_module_name, None)
importlib.invalidate_caches()


ROOT = "/Game/Scenes/Effects"
WAX_MASTER_PATH = ROOT + "/M_FX_CandleWax"
WAX_MI_PATH = ROOT + "/MI_FX_CandleWax"
FLAME_PATH = ROOT + "/M_FX_CandleFlame"
BP_PATH = ROOT + "/BP_Effect_Candle"
TARGETS = (WAX_MASTER_PATH, WAX_MI_PATH, FLAME_PATH, BP_PATH)
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def aid(value):
    if value is None:
        return None
    return str(value.get_path_name()).split(".", 1)[0]


def census():
    return {
        "content": sorted(aid(value) for value in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(aid(value) for value in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def scalar(material, name, default, x, y):
    value = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y)
    value.set_editor_property("parameter_name", name)
    value.set_editor_property("default_value", float(default))
    return value


def vector(material, name, default, x, y):
    value = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, x, y)
    value.set_editor_property("parameter_name", name)
    value.set_editor_property("default_value", unreal.LinearColor(*default))
    return value


def node(material, cls, x, y):
    return unreal.MaterialEditingLibrary.create_material_expression(material, cls, x, y)


def link(left, output_name, right, input_name):
    require(unreal.MaterialEditingLibrary.connect_material_expressions(
        left, output_name, right, input_name),
        "MATERIAL_LINK_FAILED|%s.%s->%s.%s" %
        (left.get_name(), output_name, right.get_name(), input_name))


def output(expression, output_name, prop):
    require(unreal.MaterialEditingLibrary.connect_material_property(
        expression, output_name, prop), "MATERIAL_OUTPUT_FAILED|%s" % prop)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
world = editor.get_editor_world()
require(world is not None and aid(world) == EXPECTED_WORLD,
        "WRONG_WORLD|actual=%s" % aid(world))
require(census() == {"content": [], "maps": []},
        "PRE_DIRTY|%s" % json.dumps(census(), sort_keys=True))
existing = [path for path in TARGETS if unreal.EditorAssetLibrary.does_asset_exist(path)]
require(not existing, "TARGET_ALREADY_EXISTS|%s" % ",".join(existing))

run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
backup_root = os.path.join(project, "Backups", "PreFxCandleAsset-" + run)
os.makedirs(backup_root, exist_ok=False)
manifest = {
    "run": run,
    "kind": "absent_namespace_prewrite_manifest",
    "world": aid(world),
    "dirty_before": census(),
    "targets_absent": list(TARGETS),
}
with open(os.path.join(backup_root, "manifest.json"), "x", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2, sort_keys=True)

tools = unreal.AssetToolsHelpers.get_asset_tools()
mel = unreal.MaterialEditingLibrary

# Wax: a small reusable master plus the requested off-white instance.
wax = tools.create_asset("M_FX_CandleWax", ROOT, unreal.Material,
                         unreal.MaterialFactoryNew())
require(wax is not None, "CREATE_WAX_MASTER_FAILED")
wax_color = vector(wax, "WaxColor", (0.78, 0.71, 0.59, 1.0), -420, -120)
wax_rough = scalar(wax, "WaxRoughness", 0.72, -420, 20)
wax_spec = scalar(wax, "WaxSpecular", 0.28, -420, 150)
output(wax_color, "", unreal.MaterialProperty.MP_BASE_COLOR)
output(wax_rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
output(wax_spec, "", unreal.MaterialProperty.MP_SPECULAR)
mel.recompile_material(wax)

wax_mi = tools.create_asset("MI_FX_CandleWax", ROOT,
                            unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
require(wax_mi is not None, "CREATE_WAX_MI_FAILED")
wax_mi.set_editor_property("parent", wax)
mel.set_material_instance_vector_parameter_value(
    wax_mi, "WaxColor", unreal.LinearColor(0.82, 0.76, 0.66, 1.0))
mel.set_material_instance_scalar_parameter_value(wax_mi, "WaxRoughness", 0.76)
mel.set_material_instance_scalar_parameter_value(wax_mi, "WaxSpecular", 0.24)
mel.update_material_instance(wax_mi)

# Flame: translucent unlit warm gradient, soft Fresnel edge, and gentle
# top-weighted WPO flicker driven by Time plus PerInstanceRandom.
flame = tools.create_asset("M_FX_CandleFlame", ROOT, unreal.Material,
                           unreal.MaterialFactoryNew())
require(flame is not None, "CREATE_FLAME_MATERIAL_FAILED")
flame.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
flame.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
flame.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
flame.set_editor_property("two_sided", True)

uv = node(flame, unreal.MaterialExpressionTextureCoordinate, -1300, -300)
v = node(flame, unreal.MaterialExpressionComponentMask, -1120, -300)
v.set_editor_property("r", False)
v.set_editor_property("g", True)
v.set_editor_property("b", False)
v.set_editor_property("a", False)
# UE 5.8 exposes ComponentMask's sole input as the empty graph pin.  This is
# the project-proven form used by the curtain and painted-wing builders.
link(uv, "", v, "")

warm = vector(flame, "WarmBase", (1.0, 0.075, 0.006, 1.0), -1120, -520)
hot = vector(flame, "HotCore", (1.0, 0.72, 0.22, 1.0), -1120, -420)
gradient = node(flame, unreal.MaterialExpressionLinearInterpolate, -880, -450)
link(warm, "", gradient, "A")
link(hot, "", gradient, "B")
link(v, "", gradient, "Alpha")

time = node(flame, unreal.MaterialExpressionTime, -1300, 80)
speed = scalar(flame, "FlickerSpeed", 5.3, -1300, 180)
time_speed = node(flame, unreal.MaterialExpressionMultiply, -1090, 100)
link(time, "", time_speed, "A")
link(speed, "", time_speed, "B")
random = node(flame, unreal.MaterialExpressionPerInstanceRandom, -1300, 300)
tau = node(flame, unreal.MaterialExpressionConstant, -1120, 330)
tau.set_editor_property("r", 6.283185307)
random_phase = node(flame, unreal.MaterialExpressionMultiply, -920, 300)
link(random, "", random_phase, "A")
link(tau, "", random_phase, "B")
phase = node(flame, unreal.MaterialExpressionAdd, -760, 120)
link(time_speed, "", phase, "A")
link(random_phase, "", phase, "B")
wave = node(flame, unreal.MaterialExpressionSine, -580, 120)
link(phase, "", wave, "")

flicker_depth = scalar(flame, "FlickerBrightness", 0.08, -580, 260)
brightness_delta = node(flame, unreal.MaterialExpressionMultiply, -390, 120)
link(wave, "", brightness_delta, "A")
link(flicker_depth, "", brightness_delta, "B")
one = node(flame, unreal.MaterialExpressionConstant, -390, 260)
one.set_editor_property("r", 1.0)
brightness = node(flame, unreal.MaterialExpressionAdd, -200, 150)
link(one, "", brightness, "A")
link(brightness_delta, "", brightness, "B")
emissive_strength = scalar(flame, "EmissiveStrength", 14.0, -390, -350)
emissive_base = node(flame, unreal.MaterialExpressionMultiply, -200, -430)
link(gradient, "", emissive_base, "A")
link(emissive_strength, "", emissive_base, "B")
emissive = node(flame, unreal.MaterialExpressionMultiply, 20, -360)
link(emissive_base, "", emissive, "A")
link(brightness, "", emissive, "B")
output(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

fresnel = node(flame, unreal.MaterialExpressionFresnel, -650, -120)
edge = node(flame, unreal.MaterialExpressionOneMinus, -450, -120)
# UE 5.8 exposes OneMinus's sole input as the empty graph pin, matching the
# project-proven painted-wing builder's single-input connection pattern.
link(fresnel, "", edge, "")
edge_power = scalar(flame, "SoftEdgePower", 1.45, -450, -20)
opacity = node(flame, unreal.MaterialExpressionPower, -220, -100)
link(edge, "", opacity, "Base")
link(edge_power, "", opacity, "Exp")
output(opacity, "", unreal.MaterialProperty.MP_OPACITY)

wpo_amount = scalar(flame, "WPOAmountCm", 0.32, -420, 520)
wpo_wave = node(flame, unreal.MaterialExpressionMultiply, -210, 480)
link(wave, "", wpo_wave, "A")
link(wpo_amount, "", wpo_wave, "B")
wpo_top = node(flame, unreal.MaterialExpressionMultiply, 0, 480)
link(wpo_wave, "", wpo_top, "A")
link(v, "", wpo_top, "B")
wpo_direction = node(flame, unreal.MaterialExpressionConstant3Vector, 0, 620)
wpo_direction.set_editor_property("constant", unreal.LinearColor(0.30, 0.12, 1.0, 1.0))
wpo = node(flame, unreal.MaterialExpressionMultiply, 210, 520)
link(wpo_top, "", wpo, "A")
link(wpo_direction, "", wpo, "B")
output(wpo, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
mel.recompile_material(flame)

# Blueprint subclass expected by the Effect system. The native Apparatus becomes
# the wax body; a new mesh component carries the flame, and an empty Niagara
# component preserves the system's FX-component contract without replacing the
# requested mesh flame.
bp = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(
    BP_PATH, unreal.InfinityStageEffectSource)
require(bp is not None, "CREATE_CANDLE_BLUEPRINT_FAILED")
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
lib = unreal.SubobjectDataBlueprintFunctionLibrary


def handles_by_name():
    result = {}
    for handle in sds.k2_gather_subobject_data_for_blueprint(bp):
        data = lib.get_data(handle)
        result[str(lib.get_variable_name(data))] = handle
    return result


def add_component(cls, name, parent_name="TrackingRoot"):
    handles = handles_by_name()
    parent = handles.get(parent_name) or next(iter(handles.values()))
    handle, reason = sds.add_new_subobject(unreal.AddNewSubobjectParams(
        parent_handle=parent, new_class=cls, blueprint_context=bp))
    require(lib.is_handle_valid(handle), "ADD_COMPONENT_FAILED|%s|%s" % (name, reason))
    sds.rename_subobject(handle, unreal.Text(name))
    return lib.get_associated_object(lib.get_data(handle))


flame_component = add_component(unreal.StaticMeshComponent, "Flame")
niagara_component = add_component(unreal.NiagaraComponent, "FlameFX")
flame_mesh = unreal.load_asset("/Engine/BasicShapes/Sphere")
cylinder_mesh = unreal.load_asset("/Engine/BasicShapes/Cylinder")
require(isinstance(flame_mesh, unreal.StaticMesh) and isinstance(cylinder_mesh, unreal.StaticMesh),
        "ENGINE_BASIC_MESH_LOAD_FAILED")
flame_component.set_editor_property("static_mesh", flame_mesh)
flame_component.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, 12.0))
flame_component.set_editor_property("relative_scale3d", unreal.Vector(0.03, 0.03, 0.04))
flame_component.set_material(0, flame)
flame_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
flame_component.set_editor_property("cast_shadow", False)
niagara_component.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, 12.0))
niagara_component.set_editor_property("auto_activate", False)
niagara_component.set_editor_property("visible", False)

require(unreal.BlueprintEditorLibrary.compile_blueprint(bp), "CANDLE_BLUEPRINT_COMPILE_FAILED")
generated = bp.generated_class()
require(generated is not None, "CANDLE_GENERATED_CLASS_MISSING")
cdo = unreal.get_default_object(generated)
apparatus = cdo.get_editor_property("apparatus")
require(apparatus is not None, "CANDLE_APPARATUS_MISSING")
cdo.modify()
apparatus.set_editor_property("static_mesh", cylinder_mesh)
apparatus.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, 5.0))
apparatus.set_editor_property("relative_scale3d", unreal.Vector(0.02, 0.02, 0.10))
apparatus.set_material(0, wax_mi)
apparatus.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
cdo.set_editor_property("tags", [unreal.Name("InfinityStage.Effect.Candle")])
require(unreal.BlueprintEditorLibrary.compile_blueprint(bp),
        "CANDLE_BLUEPRINT_FINAL_COMPILE_FAILED")

dirty = census()
require(not dirty["maps"], "CANDLE_ASSET_DIRTIED_MAPS|%s" % json.dumps(dirty))
require(set(dirty["content"]).issubset(set(TARGETS)),
        "CANDLE_ASSET_DIRTY_SCOPE|%s" % json.dumps(dirty, sort_keys=True))
for asset in (wax, wax_mi, flame, bp):
    require(unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False),
            "ASSET_SAVE_FAILED|%s" % aid(asset))
require(census() == {"content": [], "maps": []},
        "POST_SAVE_DIRTY|%s" % json.dumps(census(), sort_keys=True))

# Reload and read back the physical contract from Blueprint subobject templates.
# SCS-added components are not reliably enumerated by get_components_by_class()
# on the generated-class CDO in this build.
rbp = unreal.load_asset(BP_PATH)
rclass = unreal.EditorAssetLibrary.load_blueprint_class(BP_PATH)
require(rbp is not None and rclass is not None, "CANDLE_BLUEPRINT_READBACK_FAILED")
meshes = []
niagara = []
for handle in sds.k2_gather_subobject_data_for_blueprint(rbp):
    data = lib.get_data(handle)
    item = lib.get_object_for_blueprint(data, rbp)
    if item is None:
        item = lib.get_associated_object(data)
    if isinstance(item, unreal.StaticMeshComponent):
        meshes.append(item)
    if isinstance(item, unreal.NiagaraComponent):
        niagara.append(item)
require(len(meshes) >= 2 and len(niagara) >= 1, "CANDLE_COMPONENT_READBACK_FAILED")
report = {
    "ok": True,
    "run": run,
    "backup": backup_root,
    "assets": list(TARGETS),
    "blueprint_parent": aid(rclass.get_super_class()),
    "static_mesh_components": [{
        "name": item.get_name(),
        "mesh": aid(item.get_editor_property("static_mesh")),
        "location": [float(item.get_editor_property("relative_location").x),
                     float(item.get_editor_property("relative_location").y),
                     float(item.get_editor_property("relative_location").z)],
        "scale": [float(item.get_editor_property("relative_scale3d").x),
                  float(item.get_editor_property("relative_scale3d").y),
                  float(item.get_editor_property("relative_scale3d").z)],
        "materials": [aid(value) for value in item.get_materials()],
    } for item in meshes],
    "niagara_components": len(niagara),
    "census": census(),
}
output_path = os.path.join(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_saved_dir()), "CodexConductor", "fx_create_candle_assets_report.json")
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
unreal.log("FX_CANDLE_ASSETS_CREATED|assets=4|wax=2x10cm|flame=3x4cm|unlit=1|wpo=1|niagara=%d|backup=%s|census=%s" %
           (len(niagara), backup_root, json.dumps(census(), separators=(",", ":"))))
