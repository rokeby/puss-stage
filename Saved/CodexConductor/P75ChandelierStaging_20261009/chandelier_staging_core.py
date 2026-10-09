"""Pure planning and validation for P75 chandelier staging.

P75 owns chandelier bodies, the 24 separately pivoted chain-link actors, a
small number of grouped lights, and the Opening drive-by light keys. P56 owns
all flame actors; P52/P52B own every swing key.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Iterable


class P75Error(RuntimeError):
    pass


PARTS = ("opening", "p06")
BODY_MESH = "/Game/Scenes/Props/Chandelier/SM_Chandelier_Iron3"
MATERIAL = "/Game/Scenes/Props/Chandelier/MI_Chandelier_Iron3"
CHAIN_MESHES = [
    "/Game/Scenes/Props/Chandelier/Chain/ChainLink_%02d" % index
    for index in range(24)
]
OLD_ASSET_ROOT = "/Game/Scenes/Chandelier/Iron3"


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
    "parts": ["opening", "p06"],
    "confirm": "",
    "reviewed_plan_sha256": {"opening": "", "p06": ""},
    "opening_duration_s": 96.36,
    "opening_shadow_start_s": 36.18,
    "opening_shadow_peak_s": 37.68,
    "opening_shadow_end_s": 39.18,
    "opening_body_location_cm": [-400.0, 600.0, 900.0],
    "opening_body_rotation_deg": [0.0, 0.0, 0.0],
    "drive_by_light_location_cm": [-4200.0, -900.0, 850.0],
    "drive_by_target_start_cm": [0.0, 1200.0, 550.0],
    "drive_by_target_end_cm": [0.0, -1200.0, 550.0],
    "drive_by_outer_cone_deg": 34.0,
    "drive_by_color_linear": [1.0, 0.9, 0.75],
    "drive_by_soft_source_radius_cm": 15.0,
    "drive_by_peak_intensity_cd": 2500.0,
    "proscenium_plane_x_cm": 0.0,
    "chandelier_shadow_size_cm": [300.0, 220.0],
    "opening_group_light_count": 2,
    "opening_group_shadow_caster_count": 1,
    "opening_group_lights_enabled": True,
    "p06_group_light_count": 1,
    "p06_group_shadow_caster_count": 0,
    "p06_group_lights_enabled": False,
    "grouped_light_intensity_cd": 85.0,
    "grouped_light_attenuation_cm": 650.0,
    "p06_hang_station_cm": 5700.0,
    "p06_lateral_cm": 0.0,
    "p06_body_z_cm": 1050.0,
    "p06_first_chain_creak_s": 24.89,
    "p06_topple_stations_cm": [9450.0, 10450.0, 10950.0, 11450.0, 11950.0, 12450.0,
                                  15150.0, 16350.0, 17550.0, 18750.0, 19950.0, 21150.0,
                                  22350.0, 23550.0, 24750.0, 25950.0, 27250.0],
    "p06_wing_stations_cm": [250.0, 1050.0, 1950.0, 2950.0, 4050.0, 5150.0,
                               6250.0, 7350.0, 8450.0, 9450.0, 10450.0, 10950.0,
                               11450.0, 11950.0, 12450.0, 12950.0, 13450.0, 13950.0],
    "minimum_topple_clearance_cm": 1200.0,
    "minimum_wing_station_clearance_cm": 400.0,
    "new_sound": False,
}


def validate_chain_schema(raw: Any) -> dict[str, Any]:
    require(isinstance(raw, dict), "CHAIN_SCHEMA_OBJECT")
    require(raw.get("schema") == "chandelier_chain_v1", "CHAIN_SCHEMA_ID")
    require(raw.get("units") == "cm", "CHAIN_UNITS_CM")
    require(int(raw.get("count", -1)) == 24, "CHAIN_LINK_COUNT_24")
    require(_number(raw.get("length_cm"), "chain_length_cm") == 300.0, "CHAIN_LENGTH_300")
    links = raw.get("links")
    require(isinstance(links, list) and len(links) == 24, "CHAIN_LINK_ROWS_24")
    clean_links = []
    for index, row in enumerate(links):
        require(isinstance(row, dict) and int(row.get("index", -1)) == index,
                "CHAIN_LINK_INDEX_%02d" % index)
        pivot = _vec3(row.get("pivot_cm"), "chain_pivot_%02d" % index)
        length = _number(row.get("length_cm"), "chain_link_length_%02d" % index)
        require(abs(length - 12.5) <= 1.0e-6, "CHAIN_LINK_LENGTH_%02d" % index)
        expected = [0.0, 0.0, -12.5 * index]
        require(all(abs(a - b) <= 1.0e-6 for a, b in zip(pivot, expected)),
                "CHAIN_LINK_PIVOT_%02d" % index)
        clean_links.append({"index": index, "pivot_cm": pivot, "length_cm": length,
                            "mass_kg": row.get("mass_kg")})
    body = raw.get("body")
    require(isinstance(body, dict), "CHAIN_BODY_OBJECT")
    attach = _vec3(body.get("attach_cm"), "chain_body_attach")
    require(all(abs(a - b) <= 1.0e-6 for a, b in zip(attach, [0.0, 0.0, -300.0])),
            "CHAIN_BODY_ATTACH")
    return {"schema": "chandelier_chain_v1", "count": 24, "length_cm": 300.0,
            "links": clean_links, "body": {"attach_cm": attach,
            "mass_kg": body.get("mass_kg")}}


def validate_args(raw: Any) -> dict[str, Any]:
    require(isinstance(raw, dict), "ARGS_OBJECT")
    args = copy.deepcopy(DEFAULTS)
    args.update(raw)
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE")
    args["mode"] = mode
    parts = args.get("parts")
    require(isinstance(parts, list) and parts, "PARTS_NONEMPTY_LIST")
    parts = [str(value).lower() for value in parts]
    require(len(parts) == len(set(parts)), "PARTS_DUPLICATE")
    require(all(value in PARTS for value in parts), "PARTS_ALLOWED")
    require(mode == "DRY" or len(parts) == 1, "MUTATION_ONE_PART_REQUIRED")
    args["parts"] = parts
    if mode in ("APPLY", "REVERT"):
        require(args.get("confirm") == "%s P75 CHANDELIER" % mode, "CONFIRM")
    reviewed = args.get("reviewed_plan_sha256")
    require(isinstance(reviewed, dict), "REVIEWED_HASHES_OBJECT")
    args["reviewed_plan_sha256"] = {part: str(reviewed.get(part, "")) for part in PARTS}

    body_mesh = str(args.get("body_mesh", ""))
    material = str(args.get("material", ""))
    chain_meshes = [str(value) for value in args.get("chain_meshes", [])]
    all_paths = [body_mesh, material] + chain_meshes
    require(not any(path.startswith(OLD_ASSET_ROOT) for path in all_paths), "OLD_ASSET_ROOT_REFUSED")
    require(body_mesh == BODY_MESH, "PRODUCTION_BODY_MESH_REQUIRED")
    require(material == MATERIAL, "PRODUCTION_MATERIAL_REQUIRED")
    require(chain_meshes == CHAIN_MESHES, "PRODUCTION_CHAIN_MESHES_REQUIRED")
    require(str(args.get("chain_layout_json", "")).replace("\\", "/").endswith(
        "DerivedAssets/ChandelierBuild/Output/Iron3/chandelier_Iron3_chain.json"),
        "PRODUCTION_CHAIN_JSON_REQUIRED")

    for key in ("opening_duration_s", "opening_shadow_start_s", "opening_shadow_peak_s",
                "opening_shadow_end_s", "drive_by_outer_cone_deg", "drive_by_soft_source_radius_cm",
                "drive_by_peak_intensity_cd", "proscenium_plane_x_cm", "grouped_light_intensity_cd",
                "grouped_light_attenuation_cm", "p06_hang_station_cm", "p06_lateral_cm",
                "p06_body_z_cm", "p06_first_chain_creak_s", "minimum_topple_clearance_cm",
                "minimum_wing_station_clearance_cm"):
        args[key] = _number(args[key], key)
    for key in ("opening_body_location_cm", "opening_body_rotation_deg",
                "drive_by_light_location_cm", "drive_by_target_start_cm",
                "drive_by_target_end_cm", "drive_by_color_linear"):
        args[key] = _vec3(args[key], key)
    args["chandelier_shadow_size_cm"] = [
        _number(item, "chandelier_shadow_size_cm") for item in args["chandelier_shadow_size_cm"]]
    require(len(args["chandelier_shadow_size_cm"]) == 2, "SHADOW_SIZE_PAIR")
    for part in PARTS:
        count_key = part + "_group_light_count"
        caster_key = part + "_group_shadow_caster_count"
        args[count_key] = int(args[count_key])
        args[caster_key] = int(args[caster_key])
        require(args[count_key] >= 0, part.upper() + "_LIGHT_COUNT")
        require(0 <= args[caster_key] <= args[count_key], part.upper() + "_SHADOW_COUNT")
    require(0.0 <= args["opening_shadow_start_s"] < args["opening_shadow_peak_s"]
            < args["opening_shadow_end_s"] <= args["opening_duration_s"], "OPENING_SHADOW_ORDER")
    require(args.get("new_sound") is False, "SILENT_DEFAULT_REQUIRED")
    return args


def light_rows_for_part(args: dict[str, Any], part: str) -> list[dict[str, Any]]:
    rows = []
    if part == "opening":
        rows.append({"label": "P75 Opening Drive-By", "owner_part": part,
                     "cast_shadows": True, "enabled_default": False, "kind": "spot"})
    count = args[part + "_group_light_count"]
    casters = args[part + "_group_shadow_caster_count"]
    enabled = bool(args[part + "_group_lights_enabled"])
    title = "Opening" if part == "opening" else "P06"
    for index in range(count):
        rows.append({"label": "P75 %s Candle Group %02d" % (title, index + 1),
                     "owner_part": part, "cast_shadows": index < casters,
                     "enabled_default": enabled, "kind": "point"})
    return rows


def validate_global_light_guard(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    rows = list(rows)
    labels = [str(row.get("label", "")) for row in rows]
    require(all(labels) and len(labels) == len(set(labels)), "GLOBAL_LIGHT_LABELS_UNIQUE")
    light_count = len(rows)
    caster_count = sum(bool(row.get("cast_shadows")) for row in rows)
    require(light_count <= 4, "GLOBAL_GPU_LIGHT_CAP_4")
    require(caster_count <= 2, "GLOBAL_GPU_SHADOW_CAP_2")
    return {"lights": light_count, "shadow_casters": caster_count}


def projected_shadow_size(light: Iterable[float], prop: Iterable[float], plane_x: float,
                          source_size_cm: Iterable[float]) -> dict[str, float]:
    light_row, prop_row = list(light), list(prop)
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


def _labels(part: str) -> dict[str, Any]:
    title = "Opening" if part == "opening" else "P06"
    return {"body_actor_label": "P75 %s Chandelier Body" % title,
            "link_actor_labels": ["P75 %s Chain Link %02d" % (title, index) for index in range(24)]}


def build_plan(raw: Any, chain_raw: Any) -> dict[str, Any]:
    args = validate_args(raw)
    chain = validate_chain_schema(chain_raw)
    all_lights = light_rows_for_part(args, "opening") + light_rows_for_part(args, "p06")
    global_budget = validate_global_light_guard(all_lights)
    shadow = projected_shadow_size(args["drive_by_light_location_cm"], args["opening_body_location_cm"],
                                   args["proscenium_plane_x_cm"], args["chandelier_shadow_size_cm"])
    topple_clearance = minimum_clearance(args["p06_hang_station_cm"], args["p06_topple_stations_cm"])
    wing_clearance = minimum_clearance(args["p06_hang_station_cm"], args["p06_wing_stations_cm"])
    require(topple_clearance >= args["minimum_topple_clearance_cm"], "TOPPLE_ROW_OVERLAP")
    require(wing_clearance >= args["minimum_wing_station_clearance_cm"], "WING_ROW_OVERLAP")
    parts = {
        "opening": {**_labels("opening"), "hidden_in_game": True, "cast_hidden_shadow": True,
                    "body_location_cm": args["opening_body_location_cm"],
                    "body_rotation_deg": args["opening_body_rotation_deg"],
                    "lights": light_rows_for_part(args, "opening"),
                    "drive_by": {"start_s": args["opening_shadow_start_s"],
                                 "peak_s": args["opening_shadow_peak_s"],
                                 "end_s": args["opening_shadow_end_s"], "passes": 1,
                                 "target_motion": "ARC_YAW",
                                 "target_start_cm": args["drive_by_target_start_cm"],
                                 "target_end_cm": args["drive_by_target_end_cm"],
                                 "outer_cone_deg": args["drive_by_outer_cone_deg"],
                                 "color_linear": args["drive_by_color_linear"],
                                 "soft_source_radius_cm": args["drive_by_soft_source_radius_cm"],
                                 "peak_intensity_cd": args["drive_by_peak_intensity_cd"]},
                    "projected_shadow_at_peak": shadow,
                    "owned_sequence_writes": ["drive_by_intensity", "drive_by_arc_rotation"]},
        "p06": {**_labels("p06"), "hidden_in_game": False, "cast_hidden_shadow": False,
                "hang_station_cm": args["p06_hang_station_cm"], "lateral_cm": args["p06_lateral_cm"],
                "body_z_cm": args["p06_body_z_cm"],
                "first_chain_creak_s": args["p06_first_chain_creak_s"],
                "lights": light_rows_for_part(args, "p06"),
                "clearances_cm": {"nearest_topple_row": topple_clearance,
                                  "nearest_wing_station": wing_clearance},
                "owned_sequence_writes": []},
    }
    assets = {"body_mesh": args["body_mesh"], "material": args["material"],
              "chain_meshes": args["chain_meshes"], "chain_layout_json": args["chain_layout_json"]}
    forbidden = ["candle_flame_actors", "candle_visibility_keys", "swing_keys"]
    for part in PARTS:
        basis = {"schema": "p75_chandelier_staging_v2", "part": part, "part_plan": parts[part],
                 "assets": assets, "chain": chain, "global_light_budget": global_budget,
                 "forbidden_writes": forbidden}
        parts[part]["plan_sha256"] = _hash(basis)
    if args["mode"] == "APPLY":
        part = args["parts"][0]
        require(args["reviewed_plan_sha256"].get(part) == parts[part]["plan_sha256"],
                "REVIEWED_PLAN_HASH_" + part.upper())
    return {"schema": "p75_chandelier_staging_v2", "selected_parts": args["parts"],
            "parts": parts, "assets": assets, "chain": chain,
            "global_light_budget": global_budget,
            "instance_actor_labels": {part: _labels(part) for part in PARTS},
            "ownership": {"flames": "P56", "swing_keys": ["P52", "P52B"],
                          "p75_sequence_writes": "Opening drive-by light only"},
            "forbidden_writes": forbidden, "args": args}


def verify_hidden_shadow(body: dict[str, Any], links: Iterable[dict[str, Any]]) -> None:
    rows = [("BODY", body)] + [("LINK_%02d" % index, row) for index, row in enumerate(links)]
    require(len(rows) == 25, "HIDDEN_SHADOW_ASSEMBLY_COUNT")
    for name, row in rows:
        require(row.get("hidden_in_game") is True, name + "_NOT_HIDDEN")
        require(row.get("cast_hidden_shadow") is True, name + "_NO_HIDDEN_SHADOW")


def verify_no_forbidden_writes(plan: dict[str, Any]) -> None:
    require(plan.get("forbidden_writes") ==
            ["candle_flame_actors", "candle_visibility_keys", "swing_keys"],
            "FORBIDDEN_WRITE_CONTRACT")
    require(plan["parts"]["p06"]["owned_sequence_writes"] == [], "P06_SEQUENCE_WRITES_FORBIDDEN")
