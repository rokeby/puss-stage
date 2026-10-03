"""Read BP_Effect_Candle through its Blueprint subobject templates.

This is read-only.  Components added through the Blueprint SCS are not reliably
enumerated by Actor.get_components_by_class() on the generated-class CDO.
"""
import json
import os

import unreal


BP_PATH = "/Game/Scenes/Effects/BP_Effect_Candle"
WAX_MI = "/Game/Scenes/Effects/MI_FX_CandleWax"
FLAME_MATERIAL = "/Game/Scenes/Effects/M_FX_CandleFlame"


def asset_id(value):
    if value is None:
        return None
    return str(value.get_path_name()).split(".", 1)[0]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def vector(value):
    return [float(value.x), float(value.y), float(value.z)]


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
world = editor.get_editor_world()
require(asset_id(world) == "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice",
        "WRONG_WORLD|actual=%s" % asset_id(world))
before = {
    "content": sorted(asset_id(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "maps": sorted(asset_id(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
}
require(before == {"content": [], "maps": []},
        "PREFLIGHT_DIRTY|" + json.dumps(before, sort_keys=True))

bp = unreal.EditorAssetLibrary.load_asset(BP_PATH)
require(bp is not None, "CANDLE_BLUEPRINT_MISSING")
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
lib = unreal.SubobjectDataBlueprintFunctionLibrary
rows = []
for handle in sds.k2_gather_subobject_data_for_blueprint(bp):
    data = lib.get_data(handle)
    obj = lib.get_object_for_blueprint(data, bp)
    if obj is None:
        obj = lib.get_associated_object(data)
    if obj is None:
        continue
    row = {
        "variable": str(lib.get_variable_name(data)),
        "object": obj.get_name(),
        "class": obj.get_class().get_name(),
    }
    if isinstance(obj, unreal.SceneComponent):
        row["relative_location"] = vector(obj.get_editor_property("relative_location"))
        row["relative_scale3d"] = vector(obj.get_editor_property("relative_scale3d"))
    if isinstance(obj, unreal.StaticMeshComponent):
        row.update({
            "mesh": asset_id(obj.get_editor_property("static_mesh")),
            "materials": [asset_id(value) for value in obj.get_materials()],
            "cast_shadow": bool(obj.get_editor_property("cast_shadow")),
            "collision_enabled": str(obj.get_collision_enabled()),
        })
    if isinstance(obj, unreal.NiagaraComponent):
        row.update({
            "auto_activate": bool(obj.get_editor_property("auto_activate")),
            "visible": bool(obj.get_editor_property("visible")),
        })
    rows.append(row)

by_name = {row["variable"]: row for row in rows}
wax = by_name.get("Apparatus")
flame = by_name.get("Flame")
flame_fx = by_name.get("FlameFX")
require(wax is not None, "CANDLE_WAX_SUBOBJECT_MISSING")
require(flame is not None, "CANDLE_FLAME_SUBOBJECT_MISSING")
require(flame_fx is not None, "CANDLE_NIAGARA_SUBOBJECT_MISSING")
require(wax["class"] == "StaticMeshComponent", "CANDLE_WAX_CLASS|" + wax["class"])
require(wax["mesh"] == "/Engine/BasicShapes/Cylinder", "CANDLE_WAX_MESH|" + str(wax["mesh"]))
require(wax["materials"] and wax["materials"][0] == WAX_MI,
        "CANDLE_WAX_MATERIAL|" + json.dumps(wax["materials"]))
require(wax["relative_location"] == [0.0, 0.0, 5.0],
        "CANDLE_WAX_LOCATION|" + json.dumps(wax["relative_location"]))
require(wax["relative_scale3d"] == [0.02, 0.02, 0.1],
        "CANDLE_WAX_SCALE|" + json.dumps(wax["relative_scale3d"]))
require(flame["class"] == "StaticMeshComponent", "CANDLE_FLAME_CLASS|" + flame["class"])
require(flame["mesh"] == "/Engine/BasicShapes/Sphere", "CANDLE_FLAME_MESH|" + str(flame["mesh"]))
require(flame["materials"] and flame["materials"][0] == FLAME_MATERIAL,
        "CANDLE_FLAME_MATERIAL|" + json.dumps(flame["materials"]))
require(flame["relative_location"] == [0.0, 0.0, 12.0],
        "CANDLE_FLAME_LOCATION|" + json.dumps(flame["relative_location"]))
require(flame["relative_scale3d"] == [0.03, 0.03, 0.04],
        "CANDLE_FLAME_SCALE|" + json.dumps(flame["relative_scale3d"]))
require(not flame["cast_shadow"], "CANDLE_FLAME_CASTS_SHADOW")
require(flame_fx["class"] == "NiagaraComponent", "CANDLE_NIAGARA_CLASS|" + flame_fx["class"])
require(not flame_fx["auto_activate"] and not flame_fx["visible"],
        "CANDLE_NIAGARA_PLACEHOLDER_ACTIVE")

after = {
    "content": sorted(asset_id(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "maps": sorted(asset_id(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
}
require(after == before, "READBACK_CHANGED_CENSUS|" + json.dumps(after, sort_keys=True))
report = {
    "ok": True,
    "blueprint": BP_PATH,
    "subobjects": rows,
    "wax": wax,
    "flame": flame,
    "flame_fx": flame_fx,
    "light_ownership": "Show attachment; authored and verified by fx_candle_s6.py",
    "census": after,
}
path = os.path.join(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_saved_dir()), "CodexConductor", "fx_candle_blueprint_readback.json")
with open(path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
unreal.log("FX_CANDLE_BLUEPRINT_READBACK_OK|wax=2x10cm|flame=3x4cm|niagara=1|light=show_owned|census=%s" %
           json.dumps(after, separators=(",", ":")))
