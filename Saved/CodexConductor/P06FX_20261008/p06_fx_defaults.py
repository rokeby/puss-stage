"""Pure defaults and validation for the offline P06 FX tools."""
from __future__ import annotations

import copy


P06_GUID = "9BFC29C45D47911FF7836BB8537230D2"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
ROOT = "/Game/Scenes/Effects"
FIRE_SOURCE = "/Game/KK_S2_Shrine/StarterContent/Particles/P_Fire"
FIRE_NO_LIGHT = ROOT + "/Cascade/PS_Fire_NoParticleLight"
# Gary 9 Oct (conductor session): "Can you use the new fab vfx fire?" -> Stylish Fire (Niagara) replaces the Cascade P_Fire
# for FireBasket + WingBurn; the Cascade light-strip path stays for rows that still name FIRE_NO_LIGHT.
FIRE_NIAGARA = "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_1"
EFFECT_SPECS = {
    "HazePot": {"effect": "Haze", "component": "HazeFX",
                "template": "/Game/KK_S2_Shrine/StarterContent/Particles/P_Smoke", "loc": [0, 0, 90]},
    "SmokePot": {"effect": "Smoke", "component": "PlumeFX",
                 "template": "/Game/Japanese_Alley/VFX/Humo_Par", "loc": [0, 0, 90]},
    "SteamKettle": {"effect": "Steam", "component": "SteamFX",
                    "template": "/Game/KK_S2_Shrine/StarterContent/Particles/P_Steam_Lit", "loc": [0, 0, 80]},
    "FireBasket": {"effect": "Fire", "component": "FireFX", "template": FIRE_NIAGARA, "niagara": True, "loc": [0, 0, 55]},
    "WingBurn": {"effect": "WingBurn", "component": "FlameFX", "template": FIRE_NIAGARA, "niagara": True, "loc": [0, 0, 0]},
    "Motes": {"effect": "Motes", "component": "MotesFX",
              "template": "/Game/KK_S2_Shrine/StarterContent/Particles/P_Ambient_Dust", "loc": [0, 0, 0]},
}
for _name, _spec in EFFECT_SPECS.items():
    _spec["bp"] = ROOT + "/BP_Effect_" + _name

CURRENT_P06 = {
    "P06 Wing 052": {"guid": "11F403689E45D226B3298AAF16790170", "station_cm": 18750.0},
    "P06 Wing 044": {"guid": "AF6EB4EB57431F88F4BFC0957DA0E395", "station_cm": 24750.0,
                     "left_mesh": "/Game/Scenes/Wings/FlatV3/Realism/T5P/SM_FlatV3_P06_rf_26_concrete_panel_wood_L_t5p"},
    "P06 Wing 049": {"guid": "30450225EE4DB0B28CEF8FA67FD430D4", "station_cm": 25950.0},
}

BLUEPRINT_DEFAULTS = {
    "mode": "DRY",
    "confirm": "",
    "types": list(EFFECT_SPECS),
    "fire_particle_light_enabled": False,
    "allow_permanent_asset_delete": False,
}
WING_MI_DEFAULTS = {
    "mode": "DRY",
    "confirm": "",
    "cue_label": "P06 Wing 044",
    "cue_guid": CURRENT_P06["P06 Wing 044"]["guid"],
    "side": "left",
    "slots": ["Front", "Flap"],
    "child_root": ROOT + "/P06Burn",
    "name_suffix": "P06_Wing044_L_Burn_v1",
    "use_burn": True,
    "burn_preview": 0.0,
    "allow_permanent_asset_delete": False,
}
SET_DEFAULTS = {
    "mode": "DRY",
    "confirm": "",
    "include_candle": False,
    "include_smoke": False,
    "placements": [
        {"id": "motes_69_83", "type": "Motes", "cue_label": "P06 Wing 052",
         "cue_guid": CURRENT_P06["P06 Wing 052"]["guid"], "anchor": "PAIR_CENTRE",
         "location": [0.0, 0.0, 250.0], "rotation": [0.0, 0.0, 0.0],
         "output": 0.35, "active_radius_cm": 2400.0, "motes_extent_cm": [350.0, 520.0, 650.0]},
        {"id": "wingburn_87_103", "type": "WingBurn", "cue_label": "P06 Wing 044",
         "cue_guid": CURRENT_P06["P06 Wing 044"]["guid"], "anchor": "LEFT_PANEL",
         "location": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0],
         "output": 0.45, "active_radius_cm": 5000.0, "ignition_uv": [0.5, 1.0],
         "burn_start_ahead_cm": 3000.0, "burn_span_cm": 4000.0},
        {"id": "fire_late", "type": "Fire", "cue_label": "P06 Wing 049",
         "cue_guid": CURRENT_P06["P06 Wing 049"]["guid"], "anchor": "LEFT_PANEL",
         "location": [0.0, 0.0, 15.0], "rotation": [0.0, 0.0, 0.0],
         "output": 0.45, "active_radius_cm": 2200.0, "flicker_amount": 0.0},
    ],
}


class ConfigError(ValueError):
    pass


def require(value, message):
    if not value:
        raise ConfigError(message)


def merged(defaults, raw):
    out = copy.deepcopy(defaults)
    out.update(raw or {})
    out["mode"] = str(out.get("mode", "DRY")).upper()
    return out


def validate_mode(args, token, destructive=False):
    require(args["mode"] in ("DRY", "APPLY", "REVERT"), "MODE|" + args["mode"])
    if args["mode"] != "DRY":
        want = "%s %s" % (args["mode"], token)
        if destructive and args["mode"] == "REVERT":
            want += " DELETE CREATED ASSETS"
            require(args.get("allow_permanent_asset_delete") is True, "DELETE_ACK_FALSE")
        require(args.get("confirm") == want, "CONFIRM|want=" + want)
    return args


def validate_blueprints(raw):
    a = validate_mode(merged(BLUEPRINT_DEFAULTS, raw), "P06FXBPS", destructive=True)
    require(isinstance(a["types"], list) and a["types"], "TYPES_EMPTY")
    require(len(set(a["types"])) == len(a["types"]) and set(a["types"]) <= set(EFFECT_SPECS), "TYPES")
    require(isinstance(a["fire_particle_light_enabled"], bool), "FIRE_LIGHT_BOOL")
    return a


def validate_wing_mi(raw):
    a = validate_mode(merged(WING_MI_DEFAULTS, raw), "P06WINGBURNMI", destructive=True)
    require(a["cue_label"] in CURRENT_P06, "CUE_LABEL")
    require(a["cue_guid"] == CURRENT_P06[a["cue_label"]]["guid"], "CUE_GUID_DRIFT")
    require(a["side"] in ("left", "right"), "SIDE")
    require(a["slots"] and set(a["slots"]) <= {"Front", "Flap"}, "SLOTS")
    require(a["use_burn"] is True, "USE_BURN_MUST_BE_TRUE")
    require(abs(float(a["burn_preview"])) <= 1e-8, "BURN_PREVIEW_MUST_BE_ZERO")
    return a


def validate_set(raw):
    a = validate_mode(merged(SET_DEFAULTS, raw), "P06FXSET")
    require(a.get("include_candle") is False, "CANDLE_HELD_GARY_REMOVED_IT")
    require(a.get("include_smoke") is False, "SMOKE_HELD_NOT_IN_P06_PLAN")
    ids = [p.get("id") for p in a["placements"]]
    require(len(ids) == len(set(ids)) and all(ids), "PLACEMENT_IDS")
    for p in a["placements"]:
        require(p.get("type") in {"Motes", "WingBurn", "Fire"}, "PLACEMENT_TYPE")
        require(p.get("cue_label") in CURRENT_P06, "PLACEMENT_CUE")
        require(p.get("cue_guid") == CURRENT_P06[p["cue_label"]]["guid"], "PLACEMENT_GUID_DRIFT")
        require(float(p.get("output", -1)) >= 0.0 and float(p["output"]) <= 1.0, "OUTPUT")
        require(float(p.get("active_radius_cm", 0)) > 0.0, "ACTIVE_RADIUS")
    return a
