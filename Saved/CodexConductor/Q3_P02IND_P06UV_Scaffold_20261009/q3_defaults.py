"""Pure configuration and fail-closed validation for the Q3 scaffold tools."""
from __future__ import annotations

import copy


class ConfigError(ValueError):
    pass


def require(value, message):
    if not value:
        raise ConfigError(str(message))


def _mode(raw, defaults, token):
    out = copy.deepcopy(defaults)
    out.update(raw or {})
    out["mode"] = str(out.get("mode", "DRY")).upper()
    require(out["mode"] in ("DRY", "APPLY", "REVERT"), "MODE|" + out["mode"])
    if out["mode"] != "DRY":
        require(out.get("confirm") == "%s %s" % (out["mode"], token),
                "CONFIRM|want=%s %s" % (out["mode"], token))
    require(out.get("allow_permanent_asset_delete") is False, "PERMANENT_DELETE_FORBIDDEN")
    return out


P02_MESH_ROOT = "/Game/Scenes/Wings/FlatV3/Passage02/StaticMeshes"
P02_TEXTURE_ROOT = "/Game/Scenes/Wings/FlatV3/Passage02/Industrial/Textures"
P02_MI_ROOT = "/Game/Scenes/Wings/FlatV3/Passage02/Industrial/Materials"
INDUSTRIAL_MASTER = "/Game/Scenes/Wings/PaintedSurface/Industrial/M_Wing_IndustrialTiling_Master"
EDGE_V3 = "/Game/Scenes/Wings/PaintedSurface/Edge/M_Wing_Edge_v3"

P02_SOURCE_ROOT = "E:/PussStage/DerivedAssets/TextureLibrary"
P02_PROFILES = {
    "zinc": {"folder": "IndustrialZinc/WeatheredGalvanised", "prefix": "T_IndustrialZinc_WeatheredGalvanised"},
    "tarp": {"folder": "IndustrialTarp/GrimyPlastisolCanvas", "prefix": "T_IndustrialTarp_GrimyPlastisolCanvas"},
    "painted": {"folder": "IndustrialPaintedSteel/FlakingPaint", "prefix": "T_IndustrialPaintedSteel_FlakingPaint"},
}
P02_TARGETS = []
for _kind, _front in (("FenceTarp", "zinc"), ("FenceOpen", "zinc"), ("RollerShutter", "painted")):
    for _side in ("L", "R"):
        P02_TARGETS.append({
            "mesh": "%s/SM_FlatV3_P02_IND_%s_%s" % (P02_MESH_ROOT, _kind, _side),
            "slots": {"Front": _front, "Flap": "tarp", "Timber": "zinc", "Edge": "EDGE_REBUILD_REQUIRED"},
        })

P02_DEFAULTS = {
    "mode": "DRY", "confirm": "", "source_root": P02_SOURCE_ROOT,
    "texture_root": P02_TEXTURE_ROOT, "mi_root": P02_MI_ROOT,
    "master": INDUSTRIAL_MASTER, "edge_v3": EDGE_V3,
    "tile_size_cm": {"zinc": [112.0, 112.0], "tarp": [160.0, 160.0], "painted": [220.0, 220.0]},
    "edge_winding_audit": "unclear", "allow_permanent_asset_delete": False,
}


def validate_p02(raw):
    a = _mode(raw, P02_DEFAULTS, "P02IND")
    require(a["source_root"].replace("\\", "/") == P02_SOURCE_ROOT, "SOURCE_ROOT_DRIFT")
    require(a["edge_winding_audit"] in ("outward", "inward", "unclear"), "EDGE_AUDIT")
    for key in P02_PROFILES:
        span = a["tile_size_cm"].get(key)
        require(isinstance(span, list) and len(span) == 2 and min(map(float, span)) >= 25.0,
                "TILE_SIZE|" + key)
    return a


SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCAFFOLD_EXPECTED = {
    "A9E0E66B074D5EA45E23BE93ADA0F8CE": {"label": "P06 Wing 033", "left": "/Game/Scenes/Wings/StageOpeningV2/StaticMeshes/SM_SteelScaffold_01_L", "right": "/Game/Scenes/Wings/StageOpeningV2/StaticMeshes/SM_SteelScaffold_01_R"},
    "CC3403E5418809B2A1D9328EFC64C048": {"label": "P06 OLD 23 - steel_scaffold", "right": "/Game/Scenes/Wings/StageOpeningV2/StaticMeshes/SM_SteelScaffold_01_R"},
    # Gary 9 Oct (via Conductor 5): "wing 45's right side could be one of the real 3D scaffold bays" (keeper slides; mesh-only)
    "3F1CEC91DE4164DCF2F0698A885CBD14": {"label": "P06 Wing 045", "right": "/Game/Scenes/Wings/StageOpeningV2/StaticMeshes/SM_SteelScaffold_01_R"},
}
SCAFFOLD_HELD = []  # Wing 045 R released by Gary 9 Oct
SCAFFOLD_DEFAULTS = {
    "mode": "DRY", "confirm": "", "variant": "2bay",
    "fbx_2bay": "E:/PussStage/DerivedAssets/FlatV3/BlenderTest/Export/SM_FlatV3_P06_Scaffold_2Bay.fbx",
    "fbx_3bay": "E:/PussStage/DerivedAssets/FlatV3/BlenderTest/Export/SM_FlatV3_P06_Scaffold_3Bay.fbx",
    "asset_root": "/Game/Scenes/Wings/FlatV3/Passage06/Scaffold",
    "materials": {"Front": "/Game/Scenes/Wings/FlatV3/Passage06/Scaffold/Materials/MI_Scaffold_AgedSteel",
                  "Flap": "/Game/Scenes/Wings/FlatV3/Passage06/Scaffold/Materials/MI_Scaffold_NetBaked",
                  "Timber": "/Game/Scenes/Wings/FlatV3/Passage06/Scaffold/Materials/MI_Scaffold_Timber",
                  "Edge": "/Game/Scenes/Wings/FlatV3/Passage06/Scaffold/Materials/MI_Scaffold_BulbEmissive"},
    "allow_oversize_3bay": False, "replace": SCAFFOLD_EXPECTED, "held_sides": SCAFFOLD_HELD,
    "allow_permanent_asset_delete": False,
}


def validate_scaffold(raw):
    a = _mode(raw, SCAFFOLD_DEFAULTS, "P06SCAFFOLD")
    require(a["variant"] in ("2bay", "3bay"), "VARIANT")
    require(a["variant"] != "3bay" or a.get("allow_oversize_3bay") is True,
            "THREE_BAY_EXCEEDS_650CM_SLOT")
    require(a["replace"] == SCAFFOLD_EXPECTED, "TARGET_ROWS_DRIFT")
    require(a["held_sides"] == SCAFFOLD_HELD, "HELD_SIDES_DRIFT")
    active = {(guid, side) for guid, spec in a["replace"].items() for side in ("left", "right") if side in spec}
    held = {(item["guid"], item["side"]) for item in a["held_sides"]}
    require(not (active & held), "ACTIVE_HELD_OVERLAP")
    return a


EXPORT_DEFAULTS = {
    "mode": "DRY", "confirm": "", "blend": "E:/PussStage/DerivedAssets/FlatV3/BlenderTest/FlatV3_ScaffoldBay.blend",
    "output_dir": "E:/PussStage/DerivedAssets/FlatV3/BlenderTest/Export",
    "variants": [2, 3], "bay_width_cm": 280.0, "depth_cm": 150.0, "height_cm": 1000.0,
    "lod1_distance_cm": 1500.0, "net_alpha_mode": "BAKED_DARK_GAUZE",
    "origin": "FLOOR_CENTRE", "front_axis": "-X", "width_axis": "+Y", "up_axis": "+Z",
    "allow_permanent_asset_delete": False,
}


def validate_export(raw):
    a = _mode(raw, EXPORT_DEFAULTS, "P06SCAFFOLDEXPORT")
    require(a["variants"] == [2, 3], "VARIANTS")
    require(a["net_alpha_mode"] == "BAKED_DARK_GAUZE", "NET_MODE")
    require(a["origin"] == "FLOOR_CENTRE" and a["front_axis"] == "-X" and a["width_axis"] == "+Y" and a["up_axis"] == "+Z", "FRAME")
    return a
