"""Pure planning and validation for Job 182. No Unreal imports."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable, Sequence


SOCKETS = ["Candle_%02d" % index for index in range(1, 45)]
APPLY_CONFIRM = "APPLY JOB182 CHANDELIER LIGHT"
REVERT_CONFIRM = "REVERT JOB182 CHANDELIER LIGHT"


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _number(value: Any, field: str) -> float:
    require(isinstance(value, (int, float)) and math.isfinite(float(value)), field)
    return float(value)


def _vec3(value: Any, field: str) -> list[float]:
    require(isinstance(value, list) and len(value) == 3, field)
    return [_number(item, field) for item in value]


def balanced_groups(names: Sequence[str], count: int) -> list[list[str]]:
    """Partition an already spatially ordered ring into 5/6-candle sectors."""
    require(list(sorted(names)) == SOCKETS, "SOCKET_SEQUENCE_44")
    require(count == 8, "GROUP_LIGHT_COUNT_8")
    base, extra = divmod(len(names), count)
    sizes = [base + int(index < extra) for index in range(count)]
    groups, cursor = [], 0
    for size in sizes:
        groups.append(list(names[cursor:cursor + size]))
        cursor += size
    require(cursor == 44 and sorted(sum(groups, [])) == SOCKETS, "GROUP_COVERAGE")
    require(sorted(len(group) for group in groups) == [5, 5, 5, 5, 6, 6, 6, 6],
            "GROUP_SIZE_5_OR_6")
    return groups


def vector_mean(values: Sequence[Sequence[float]]) -> list[float]:
    require(bool(values), "MEAN_EMPTY")
    require(all(len(row) == 3 for row in values), "MEAN_VEC3")
    return [sum(float(row[axis]) for row in values) / len(values) for axis in range(3)]


def validate_args(raw: Any) -> dict[str, Any]:
    require(isinstance(raw, dict), "ARGS_OBJECT")
    args = dict(raw)
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "READBACK", "REVIEW", "REVERT"), "MODE")
    args["mode"] = mode
    require(str(args.get("body_actor_label", "")).strip(), "BODY_ACTOR_LABEL")
    require(str(args.get("body_mesh", "")).startswith("/Game/"), "BODY_MESH")
    require(str(args.get("candle_actor_prefix", "")).strip(), "CANDLE_ACTOR_PREFIX")
    require(str(args.get("flame_component_name", "")).strip(), "FLAME_COMPONENT_NAME")
    require(str(args.get("flame_niagara", "")).startswith("/Game/"), "FLAME_NIAGARA")
    require(str(args.get("review_camera_actor_label", "")).strip(), "REVIEW_CAMERA_LABEL")
    require(str(args.get("review_output", "")).lower().endswith(".png"), "REVIEW_OUTPUT_PNG")

    args["group_light_count"] = int(args.get("group_light_count", 0))
    require(args["group_light_count"] == 8, "GROUP_LIGHT_COUNT_8")
    args["group_intensity_cd"] = _number(args.get("group_intensity_cd"), "GROUP_INTENSITY")
    args["group_temperature_k"] = _number(args.get("group_temperature_k"), "GROUP_TEMPERATURE")
    args["group_attenuation_cm"] = _number(args.get("group_attenuation_cm"), "GROUP_ATTENUATION")
    args["group_source_radius_cm"] = _number(args.get("group_source_radius_cm"), "GROUP_SOURCE_RADIUS")
    require(0.0 < args["group_intensity_cd"] <= 1000.0, "GROUP_INTENSITY_RANGE")
    require(1900.0 <= args["group_temperature_k"] <= 2200.0, "GROUP_TEMPERATURE_1900_2200")
    require(150.0 <= args["group_attenuation_cm"] <= 300.0, "GROUP_ATTENUATION_150_300")
    require(0.0 <= args["group_source_radius_cm"] <= 50.0, "GROUP_SOURCE_RADIUS_RANGE")
    require(args.get("group_cast_shadows") is False, "GROUP_SHADOWLESS")

    args["fill_intensity_cd"] = _number(args.get("fill_intensity_cd"), "FILL_INTENSITY")
    args["fill_temperature_k"] = _number(args.get("fill_temperature_k"), "FILL_TEMPERATURE")
    args["fill_attenuation_cm"] = _number(args.get("fill_attenuation_cm"), "FILL_ATTENUATION")
    args["fill_source_radius_cm"] = _number(args.get("fill_source_radius_cm"), "FILL_SOURCE_RADIUS")
    args["fill_offset_local_cm"] = _vec3(args.get("fill_offset_local_cm"), "FILL_OFFSET")
    require(0.0 < args["fill_intensity_cd"] < args["group_intensity_cd"], "FILL_LOW_INTENSITY")
    require(1900.0 <= args["fill_temperature_k"] <= 2200.0, "FILL_TEMPERATURE_1900_2200")
    require(150.0 <= args["fill_attenuation_cm"] <= 300.0, "FILL_ATTENUATION_150_300")
    require(0.0 <= args["fill_source_radius_cm"] <= 100.0, "FILL_SOURCE_RADIUS_RANGE")
    require(args["fill_offset_local_cm"][0] > 0.0 and args["fill_offset_local_cm"][2] < 0.0,
            "FILL_BELOW_FRONT")
    require(args.get("fill_cast_shadows") is False, "FILL_SHADOWLESS")

    args["flame_tip_offset_cm"] = _number(args.get("flame_tip_offset_cm"), "FLAME_TIP_OFFSET")
    args["candle_socket_tolerance_cm"] = _number(
        args.get("candle_socket_tolerance_cm"), "CANDLE_SOCKET_TOLERANCE")
    require(0.0 <= args["flame_tip_offset_cm"] <= 10.0, "FLAME_TIP_OFFSET_RANGE")
    require(0.0 < args["candle_socket_tolerance_cm"] <= 2.0, "CANDLE_SOCKET_TOLERANCE_RANGE")

    args["scan_fractions"] = [_number(value, "SCAN_FRACTION") for value in args.get("scan_fractions", [])]
    require(len(args["scan_fractions"]) >= 5, "SCAN_FRACTIONS_MIN_5")
    require(args["scan_fractions"] == sorted(set(args["scan_fractions"])), "SCAN_FRACTIONS_SORTED_UNIQUE")
    require(all(0.0 < value < 1.0 for value in args["scan_fractions"]), "SCAN_FRACTION_RANGE")
    args["review_margin"] = _number(args.get("review_margin"), "REVIEW_MARGIN")
    require(1.05 <= args["review_margin"] <= 2.0, "REVIEW_MARGIN_RANGE")
    resolution = args.get("review_resolution")
    require(isinstance(resolution, list) and len(resolution) == 2, "REVIEW_RESOLUTION")
    args["review_resolution"] = [int(resolution[0]), int(resolution[1])]
    require(all(320 <= value <= 7680 for value in args["review_resolution"]), "REVIEW_RESOLUTION_RANGE")

    if mode == "APPLY":
        require(args.get("confirm") == APPLY_CONFIRM, "CONFIRM|want=" + APPLY_CONFIRM)
        require(len(str(args.get("reviewed_plan_sha256", ""))) == 64, "REVIEWED_PLAN_SHA256")
    elif mode == "REVERT":
        require(args.get("confirm") == REVERT_CONFIRM, "CONFIRM|want=" + REVERT_CONFIRM)
    return args


def build_proposal(raw: Any) -> dict[str, Any]:
    args = validate_args(raw)
    groups = balanced_groups(SOCKETS, args["group_light_count"])
    proposal = {
        "schema": "job182_p06_chandelier_light_proposal_v1",
        "authority": "PROPOSAL_FOR_GARY_TO_TUNE",
        "body_actor_label": args["body_actor_label"],
        "body_mesh": args["body_mesh"],
        "flame": {
            "actor_prefix": args["candle_actor_prefix"],
            "component_name": args["flame_component_name"],
            "niagara": args["flame_niagara"],
            "tip_offset_cm": args["flame_tip_offset_cm"],
            "socket_tolerance_cm": args["candle_socket_tolerance_cm"],
        },
        "group_lights": [{
            "label": "JOB182 P06 Candle Light %02d" % (index + 1),
            "sockets": group,
            "placement": "MEAN_OF_FLAME_TIPS",
            "intensity_units": "CANDELAS",
            "intensity_cd": args["group_intensity_cd"],
            "temperature_k": args["group_temperature_k"],
            "attenuation_radius_cm": args["group_attenuation_cm"],
            "source_radius_cm": args["group_source_radius_cm"],
            "cast_shadows": False,
            "volumetric_scattering_intensity": 0.0,
        } for index, group in enumerate(groups)],
        "iron_fill": {
            "label": "JOB182 P06 Iron Fill",
            "placement": "BODY_LOCAL_BELOW_FRONT",
            "intensity_units": "CANDELAS",
            "offset_local_cm": args["fill_offset_local_cm"],
            "intensity_cd": args["fill_intensity_cd"],
            "temperature_k": args["fill_temperature_k"],
            "attenuation_radius_cm": args["fill_attenuation_cm"],
            "source_radius_cm": args["fill_source_radius_cm"],
            "cast_shadows": False,
            "volumetric_scattering_intensity": 0.0,
        },
        "review": {
            "camera_side": "ACTIVE_P06_PASSAGE_CAMERA_SIDE",
            "framing_basis": "BODY_MESH_BOUNDS_EXCLUDING_CHILD_ACTORS_AND_PARTICLES",
            "margin": args["review_margin"],
            "resolution": args["review_resolution"],
            "exposure_override": False,
        },
    }
    wire = json.dumps(proposal, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    proposal["plan_sha256"] = hashlib.sha256(wire.encode("utf-8")).hexdigest()
    return proposal


def distance(a: Sequence[float], b: Sequence[float]) -> float:
    require(len(a) == 3 and len(b) == 3, "DISTANCE_VEC3")
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def assess_candles(rows: Iterable[dict[str, Any]], tolerance_cm: float) -> dict[str, Any]:
    items = sorted(list(rows), key=lambda row: row["socket"])
    require([row["socket"] for row in items] == SOCKETS, "CANDLE_SOCKET_ROWS_44")
    failures = []
    for row in items:
        delta = distance(row["socket_world_cm"], row["actor_world_cm"])
        row["actor_to_socket_cm"] = delta
        row["actor_at_socket"] = delta <= tolerance_cm
        if not row["actor_at_socket"]:
            failures.append(row["socket"])
    return {"rows": items, "all_at_sockets": not failures, "failures": failures,
            "max_actor_to_socket_cm": max(row["actor_to_socket_cm"] for row in items)}


def fit_distance(bounds_extent: Sequence[float], horizontal_fov_deg: float,
                 aspect: float, margin: float) -> float:
    require(len(bounds_extent) == 3, "BOUNDS_EXTENT_VEC3")
    require(1.0 < horizontal_fov_deg < 179.0, "HORIZONTAL_FOV")
    require(aspect > 0.0, "ASPECT")
    radius = math.sqrt(sum(float(value) ** 2 for value in bounds_extent))
    half_h = math.radians(horizontal_fov_deg) * 0.5
    half_v = math.atan(math.tan(half_h) / aspect)
    return radius * margin / math.sin(min(half_h, half_v))


def actor_states_match(recorded: Sequence[dict[str, Any]], live: Sequence[dict[str, Any]]) -> bool:
    if len(recorded) != len(live):
        return False
    keys = ("label", "tags", "parent_label", "cast_shadows", "use_temperature", "intensity_units")
    numeric = ("intensity_cd", "temperature_k", "attenuation_radius_cm", "source_radius_cm",
               "volumetric_scattering_intensity")
    for before, after in zip(recorded, live):
        if any(before.get(key) != after.get(key) for key in keys):
            return False
        if any(abs(float(before.get(key, 0.0)) - float(after.get(key, 0.0))) > 1.0e-3
               for key in numeric):
            return False
        for key, tolerance in (("world_location_cm", 0.01), ("relative_location_cm", 0.01)):
            if any(abs(float(a) - float(b)) > tolerance
                   for a, b in zip(before.get(key, []), after.get(key, []))):
                return False
    return True
