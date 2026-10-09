"""Pure planning and validation for P75 chandelier staging.

This module deliberately has no Unreal import.  The later-live tool consumes its
plan, while the offline harness exercises every creative and safety invariant.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from typing import Any, Iterable


class P75Error(RuntimeError):
    pass


def require(condition: Any, message: str) -> None:
    if not condition:
        raise P75Error(message)


def _number(value: Any, field: str) -> float:
    result = float(value)
    require(math.isfinite(result), field + "_FINITE")
    return result


def _vec3(value: Any, field: str) -> list[float]:
    require(isinstance(value, (list, tuple)) and len(value) == 3, field + "_VEC3")
    return [_number(item, field) for item in value]


def _hash(value: Any) -> str:
    wire = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(wire.encode("utf-8")).hexdigest()


DEFAULTS: dict[str, Any] = {
    "mode": "DRY",
    "confirm": "",
    "reviewed_plan_sha256": "",
    "opening_duration_s": 96.36,
    "p06_duration_s": 110.6,
    "opening_shadow_start_s": 36.18,
    "opening_shadow_peak_s": 37.68,
    "opening_shadow_end_s": 39.18,
    "opening_candle_start_s": 39.4,
    "opening_candle_step_s": 0.085,
    "opening_actor_location_cm": [-400.0, 600.0, 900.0],
    "opening_actor_rotation_deg": [0.0, 0.0, 0.0],
    "drive_by_light_location_cm": [-4200.0, -900.0, 850.0],
    "drive_by_target_start_cm": [0.0, 1200.0, 550.0],
    "drive_by_target_end_cm": [0.0, -1200.0, 550.0],
    "drive_by_outer_cone_deg": 34.0,
    "drive_by_color_linear": [1.0, 0.9, 0.75],
    "drive_by_soft_source_radius_cm": 15.0,
    "drive_by_peak_intensity_cd": 2500.0,
    "proscenium_plane_x_cm": 0.0,
    "chandelier_shadow_size_cm": [300.0, 220.0],
    "socket_count": 44,
    "candle_seed": 7501,
    "grouped_light_count": 4,
    "shadow_caster_count": 2,
    "grouped_light_intensity_cd": 85.0,
    "grouped_light_attenuation_cm": 650.0,
    "p06_hang_station_cm": 5700.0,
    "p06_lateral_cm": 0.0,
    "p06_hang_z_cm": 1050.0,
    "p06_visible_start_s": 12.0,
    "p06_candle_start_s": 12.25,
    "p06_candle_state": "lit",
    "p06_gutter_period_s": 0.7,
    "p06_first_chain_creak_s": 24.89,
    "p06_topple_stations_cm": [9450.0, 10450.0, 10950.0, 11450.0, 11950.0, 12450.0,
                                  15150.0, 16350.0, 17550.0, 18750.0, 19950.0, 21150.0,
                                  22350.0, 23550.0, 24750.0, 25950.0, 27250.0],
    "p06_wing_stations_cm": [250.0, 1050.0, 1950.0, 2950.0, 4050.0, 5150.0,
                               6250.0, 7350.0, 8450.0, 9450.0, 10450.0, 10950.0,
                               11450.0, 11950.0, 12450.0, 12950.0, 13450.0, 13950.0],
    "minimum_topple_clearance_cm": 1200.0,
    "minimum_wing_station_clearance_cm": 400.0,
    "optional_cue_kick": False,
    "new_sound": False,
}


def validate_args(raw: Any) -> dict[str, Any]:
    require(isinstance(raw, dict), "ARGS_OBJECT")
    args = copy.deepcopy(DEFAULTS)
    args.update(raw)
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE")
    args["mode"] = mode
    if mode in ("APPLY", "REVERT"):
        require(args.get("confirm") == f"{mode} P75 CHANDELIER", "CONFIRM")
    for key in ("opening_duration_s", "p06_duration_s", "opening_shadow_start_s",
                "opening_shadow_peak_s", "opening_shadow_end_s", "opening_candle_start_s",
                "opening_candle_step_s", "drive_by_outer_cone_deg",
                "drive_by_soft_source_radius_cm", "drive_by_peak_intensity_cd",
                "proscenium_plane_x_cm", "grouped_light_intensity_cd",
                "grouped_light_attenuation_cm", "p06_hang_station_cm", "p06_lateral_cm",
                "p06_hang_z_cm", "p06_visible_start_s", "p06_candle_start_s",
                "p06_first_chain_creak_s", "minimum_topple_clearance_cm",
                "minimum_wing_station_clearance_cm"):
        args[key] = _number(args[key], key)
    for key in ("opening_actor_location_cm", "opening_actor_rotation_deg",
                "drive_by_light_location_cm", "drive_by_target_start_cm",
                "drive_by_target_end_cm", "drive_by_color_linear"):
        args[key] = _vec3(args[key], key)
    args["chandelier_shadow_size_cm"] = [
        _number(item, "chandelier_shadow_size_cm") for item in args["chandelier_shadow_size_cm"]
    ]
    require(len(args["chandelier_shadow_size_cm"]) == 2, "SHADOW_SIZE_PAIR")
    args["socket_count"] = int(args["socket_count"])
    require(args["socket_count"] == 44, "SOCKET_COUNT_44_REQUIRED")
    args["grouped_light_count"] = int(args["grouped_light_count"])
    args["shadow_caster_count"] = int(args["shadow_caster_count"])
    require(0 <= args["grouped_light_count"] <= 4, "GPU_LIGHT_CAP_4")
    require(0 <= args["shadow_caster_count"] <= 2, "GPU_SHADOW_CAP_2")
    require(args["shadow_caster_count"] <= args["grouped_light_count"], "SHADOWS_EXCEED_LIGHTS")
    require(0.0 <= args["opening_shadow_start_s"] < args["opening_shadow_peak_s"]
            < args["opening_shadow_end_s"] <= args["opening_duration_s"], "OPENING_SHADOW_ORDER")
    require(args["opening_candle_start_s"] >= args["opening_shadow_end_s"], "CANDLES_BEFORE_SHADOW_END")
    candle_end = args["opening_candle_start_s"] + (args["socket_count"] - 1) * args["opening_candle_step_s"]
    require(candle_end < args["opening_duration_s"], "OPENING_CANDLES_OUTSIDE")
    require(0.0 <= args["p06_visible_start_s"] < args["p06_first_chain_creak_s"], "P06_RETURN_AFTER_CREAK")
    require(args["p06_candle_start_s"] < args["p06_first_chain_creak_s"], "P06_CANDLES_AFTER_CREAK")
    require(str(args["p06_candle_state"]) in ("lit", "guttering"), "P06_CANDLE_STATE")
    require(args.get("new_sound") is False, "SILENT_DEFAULT_REQUIRED")
    return args


def seeded_candle_order(count: int, seed: int) -> list[dict[str, Any]]:
    """Return one deterministic draw per socket; no re-draws or hidden jitter."""
    require(count > 0, "CANDLE_COUNT")
    rng = random.Random(int(seed))
    rows = [{"socket": f"Candle_{index:02d}", "draw": rng.random()} for index in range(1, count + 1)]
    return sorted(rows, key=lambda row: (row["draw"], row["socket"]))


def projected_shadow_size(light: Iterable[float], prop: Iterable[float], plane_x: float,
                          source_size_cm: Iterable[float]) -> dict[str, float]:
    light_row = list(light)
    prop_row = list(prop)
    require(len(light_row) == 3 and len(prop_row) == 3, "SHADOW_POINTS")
    source_to_prop = prop_row[0] - light_row[0]
    source_to_plane = plane_x - light_row[0]
    require(source_to_prop > 0.0 and source_to_plane > source_to_prop, "SHADOW_GEOMETRY_ORDER")
    magnification = source_to_plane / source_to_prop
    dims = list(source_size_cm)
    require(len(dims) == 2 and min(dims) > 0.0, "SHADOW_SOURCE_SIZE")
    return {"magnification": magnification, "width_cm": dims[0] * magnification,
            "height_cm": dims[1] * magnification}


def minimum_clearance(value: float, obstacles: Iterable[float]) -> float:
    rows = [abs(float(item) - float(value)) for item in obstacles]
    return min(rows) if rows else math.inf


def build_plan(raw: Any) -> dict[str, Any]:
    args = validate_args(raw)
    order = seeded_candle_order(args["socket_count"], int(args["candle_seed"]))
    ignition = []
    for ordinal, row in enumerate(order):
        ignition.append({"ordinal": ordinal, "socket": row["socket"], "draw": row["draw"],
                         "time_s": args["opening_candle_start_s"] + ordinal * args["opening_candle_step_s"]})
    shadow = projected_shadow_size(args["drive_by_light_location_cm"],
                                   args["opening_actor_location_cm"],
                                   args["proscenium_plane_x_cm"],
                                   args["chandelier_shadow_size_cm"])
    topple_clearance = minimum_clearance(args["p06_hang_station_cm"], args["p06_topple_stations_cm"])
    wing_clearance = minimum_clearance(args["p06_hang_station_cm"], args["p06_wing_stations_cm"])
    require(topple_clearance >= args["minimum_topple_clearance_cm"], "TOPPLE_ROW_OVERLAP")
    require(wing_clearance >= args["minimum_wing_station_clearance_cm"], "WING_ROW_OVERLAP")
    flicker_rng = random.Random(int(args["candle_seed"]) + 1000)
    opening_flicker = []
    time_s = args["opening_candle_start_s"]
    while time_s <= args["opening_duration_s"] + 1.0e-9:
        opening_flicker.append([time_s, 0.72 + 0.28 * flicker_rng.random()])
        time_s += 0.24
    p06_flicker = []
    time_s = args["p06_candle_start_s"]
    while time_s <= 30.0 + 1.0e-9:
        value = 1.0 if args["p06_candle_state"] == "lit" else 0.62 + 0.38 * flicker_rng.random()
        p06_flicker.append([time_s, value])
        time_s += args["p06_gutter_period_s"]
    plan: dict[str, Any] = {
        "schema": "p75_chandelier_staging_v1",
        "opening": {
            "duration_s": args["opening_duration_s"],
            "body": {"hidden_in_game": True, "cast_hidden_shadow": True,
                     "location_cm": args["opening_actor_location_cm"],
                     "rotation_deg": args["opening_actor_rotation_deg"]},
            "chain": {"hidden_in_game": True, "cast_hidden_shadow": True},
            "drive_by": {"start_s": args["opening_shadow_start_s"],
                         "peak_s": args["opening_shadow_peak_s"],
                         "end_s": args["opening_shadow_end_s"], "passes": 1,
                         "target_motion": "ARC_YAW", "target_start_cm": args["drive_by_target_start_cm"],
                         "target_end_cm": args["drive_by_target_end_cm"],
                         "outer_cone_deg": args["drive_by_outer_cone_deg"],
                         "color_linear": args["drive_by_color_linear"],
                         "soft_source_radius_cm": args["drive_by_soft_source_radius_cm"],
                         "peak_intensity_cd": args["drive_by_peak_intensity_cd"]},
            "projected_shadow_at_peak": shadow,
            "candles": ignition,
        },
        "lights": {"grouped_count": args["grouped_light_count"],
                   "shadow_casters": args["shadow_caster_count"],
                   "individual_candle_lights": 0,
                   "intensity_cd": args["grouped_light_intensity_cd"],
                   "attenuation_cm": args["grouped_light_attenuation_cm"],
                   "opening_flicker_scale_keys": opening_flicker,
                   "p06_flicker_scale_keys_0_30": p06_flicker},
        "p06": {
            "duration_s": args["p06_duration_s"], "visible": True,
            "hang_station_cm": args["p06_hang_station_cm"],
            "lateral_cm": args["p06_lateral_cm"], "hang_z_cm": args["p06_hang_z_cm"],
            "visible_start_s": args["p06_visible_start_s"],
            "candle_start_s": args["p06_candle_start_s"],
            "candle_state": args["p06_candle_state"],
            "swing_owner": "P52B_CHAIN_PENDULUM_REBUILD",
            "cue_kick": bool(args["optional_cue_kick"]), "new_sound": False,
            "first_chain_creak_s": args["p06_first_chain_creak_s"],
            "clearances_cm": {"nearest_topple_row": topple_clearance,
                              "nearest_wing_station": wing_clearance},
        },
        "dependencies": {"mesh": "Iron3", "socket_count": 44, "candles": "P56",
                         "swing": ["P52", "P52B"], "cue_kick_patch_optional": True},
        "args": args,
    }
    fingerprint_basis = copy.deepcopy(plan)
    fingerprint_basis["args"].pop("reviewed_plan_sha256", None)
    fingerprint_basis["args"].pop("confirm", None)
    fingerprint_basis["args"]["mode"] = "DRY"
    plan["plan_sha256"] = _hash(fingerprint_basis)
    if args["mode"] == "APPLY":
        require(args.get("reviewed_plan_sha256") == plan["plan_sha256"], "REVIEWED_PLAN_HASH")
    return plan


def verify_hidden_shadow(body: dict[str, Any], chain: dict[str, Any]) -> None:
    for name, row in (("BODY", body), ("CHAIN", chain)):
        require(row.get("hidden_in_game") is True, name + "_NOT_HIDDEN")
        require(row.get("cast_hidden_shadow") is True, name + "_NO_HIDDEN_SHADOW")


def verify_no_topple_overlap(station_cm: float, topple_stations_cm: Iterable[float], clearance_cm: float) -> float:
    got = minimum_clearance(station_cm, topple_stations_cm)
    require(got >= clearance_cm, "TOPPLE_ROW_OVERLAP")
    return got
