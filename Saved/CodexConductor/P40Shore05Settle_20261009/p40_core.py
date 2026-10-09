"""Pure planning/validation helpers for P40 Shore05 placement and colour matching.

This module is deliberately importable without Unreal.  The editor-facing tool
uses the existing S3 beach height function rather than carrying a second dune
formula, and the offline harness exercises every refusal boundary here.
"""
from __future__ import annotations

import math
import os
import random
import sys
from typing import Any


HERE = os.path.dirname(os.path.abspath(__file__))
CONDUCTOR = os.path.dirname(HERE)
if CONDUCTOR not in sys.path:
    sys.path.insert(0, CONDUCTOR)

try:
    from s3_beach_v2 import DOCK_ORIGIN, sand_height  # project authority; safe offline import
except Exception as exc:  # pragma: no cover - exercised by the conductor environment
    DOCK_ORIGIN = (10921.973, 160000.0, 0.0)
    _BEACH_IMPORT_ERROR = repr(exc)

    def sand_height(_x: float, _y: float) -> float:
        raise RuntimeError("S3_BEACH_HEIGHT_UNAVAILABLE|" + _BEACH_IMPORT_ERROR)


SCHEMA = "p40_shore05_settle/1"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CLAMS = "/Game/Scenes/LS_Clams"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FIGURES = (
    "Shore01_M56", "Shore02_F52", "Shore03_M59",
    "Shore04_F55", "Shore05_M53", "Shore06_F25",
)
BP_PATHS = {f: "/Game/Metahuman/ShoreCast_20260910/SceneCharacters/BP_%s_Draped" % f for f in FIGURES}
ANIM_NAMES = {
    "Shore01_M56": "AS_Shore01_M56_shoreguy1_Full",
    "Shore02_F52": "AS_Shore02_F52_shoreguy12_Full",
    "Shore03_M59": "AS_Shore03_M59_shoreguy3_Full",
    "Shore04_F55": "AS_Shore04_F55_shoreguy4_Full",
    "Shore05_M53": "AS_Shore05_M53_shoreguy5_Full",
    "Shore06_F25": "AS_Shore06_F25_shoreguy6_Full",
}
# Calm, forward-only source spans declared by Tools/Mocap/chorus_sway_together.py.
MOTION = {
    "Shore01_M56": (5.7083, 12.0833, 0.60),
    "Shore02_F52": (4.3750, 13.2083, 0.60),
    "Shore03_M59": (1.1667, 19.1250, 0.60),
    "Shore04_F55": (71.7083, 89.5417, 0.60),
    "Shore05_M53": (18.3333, 32.3750, 0.57777778),
    "Shore06_F25": (78.1667, 91.4583, 0.60),
}
DEFAULT_FOOT_OFFSETS = {f: -35.0 for f in FIGURES}
# Existing S3FEET plan measured this source at a different evaluated pose.
DEFAULT_FOOT_OFFSETS["Shore03_M59"] = 5.7
WEAVE_MEAN_SRGB = (0.6658808661, 0.6412755957, 0.6070530256)
WEAVE_MEAN_LINEAR = (0.4400743730, 0.4071881324, 0.3630656971)
PLAYBACK = (0, 6263)
FIRST_CROWD_VISIBLE = 360


class PlanError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PlanError(message)


def validate_args(raw: dict[str, Any], record_exists: bool = False) -> dict[str, Any]:
    mode = str(raw.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "VERIFY", "REVERT"), "MODE|" + mode)
    if mode in ("APPLY", "REVERT"):
        require(raw.get("confirm") == "%s P40SHORE" % mode,
                "CONFIRM|want '%s P40SHORE'" % mode)
    if mode == "APPLY":
        require(not record_exists, "RECORD_EXISTS|REVERT first")
    if mode in ("VERIFY", "REVERT"):
        require(record_exists, "NO_RECORD")
    extra = raw.get("extra_count", 0)
    require(isinstance(extra, int) and not isinstance(extra, bool) and 0 <= extra <= 5,
            "EXTRA_COUNT|0..5 required")
    seed = raw.get("seed", 4005)
    require(isinstance(seed, int) and not isinstance(seed, bool), "SEED|int required")
    xfade = raw.get("crossfade_frames", 72)
    require(isinstance(xfade, int) and 12 <= xfade <= 120, "XFADE|12..120")
    spacing = float(raw.get("figure_clearance_cm", 115.0))
    camera = float(raw.get("camera_clearance_cm", 185.0))
    sight = float(raw.get("sightline_half_width_cm", 90.0))
    bounds = raw.get("placement_bounds_local_cm", [2450.0, 3950.0, -720.0, 780.0])
    require(isinstance(bounds, list) and len(bounds) == 4 and
            all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in bounds),
            "PLACEMENT_BOUNDS|[min_x,max_x,min_y,max_y]")
    bounds = [float(x) for x in bounds]
    require(bounds[0] < bounds[1] and bounds[2] < bounds[3], "PLACEMENT_BOUNDS|ordered")
    require(80.0 <= spacing <= 300.0, "FIGURE_CLEARANCE")
    require(100.0 <= camera <= 500.0, "CAMERA_CLEARANCE")
    require(40.0 <= sight <= 250.0, "SIGHTLINE_WIDTH")
    foot = dict(DEFAULT_FOOT_OFFSETS)
    for key, value in (raw.get("foot_offsets_cm") or {}).items():
        require(key in FIGURES and isinstance(value, (int, float)), "FOOT_OFFSET|%s" % key)
        foot[key] = float(value)
    cloth = raw.get("cloth_reset") or {}
    cloth_enabled = bool(cloth.get("enabled", False))
    acknowledge = bool(cloth.get("acknowledge_inferred_behavior", False))
    if mode == "APPLY" and cloth_enabled:
        require(acknowledge, "CLOTH_RESET_INFERRED|set acknowledge_inferred_behavior after DRY review")
    distance = float(cloth.get("teleport_distance_threshold_cm", 25.0))
    rotation = float(cloth.get("teleport_rotation_threshold_deg", 15.0))
    require(1.0 <= distance <= 300.0, "TELEPORT_DISTANCE")
    require(1.0 <= rotation <= 180.0, "TELEPORT_ROTATION")
    material = raw.get("outfit") or {}
    version = material.get("asset_version", 1)
    require(isinstance(version, int) and 1 <= version <= 99, "OUTFIT_VERSION")
    candidates = material.get("colour_parameter_candidates") or [
        "BaseColor Tint", "Base Color Tint", "BaseColor", "Base Color", "Color", "Colour", "Tint", "C_color"
    ]
    require(isinstance(candidates, list) and candidates and all(isinstance(x, str) and x for x in candidates),
            "COLOUR_PARAMETER_CANDIDATES")
    return {
        "mode": mode, "extra_count": extra, "seed": seed, "crossfade_frames": xfade,
        "figure_clearance_cm": spacing, "camera_clearance_cm": camera,
        "sightline_half_width_cm": sight, "sightline_length_cm": float(raw.get("sightline_length_cm", 1800.0)),
        "placement_bounds_local_cm": bounds,
        "candidate_count": int(raw.get("candidate_count", 256)), "foot_offsets_cm": foot,
        "cloth_reset": {"enabled": cloth_enabled, "acknowledge_inferred_behavior": acknowledge,
                        "teleport_distance_threshold_cm": distance,
                        "teleport_rotation_threshold_deg": rotation},
        "outfit": {"enabled": bool(material.get("enabled", True)), "asset_version": version,
                   "colour_parameter_candidates": candidates},
    }


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _point_segment_distance(p, a, b) -> tuple[float, float]:
    vx, vy = b[0] - a[0], b[1] - a[1]
    wx, wy = p[0] - a[0], p[1] - a[1]
    d2 = vx * vx + vy * vy
    t = 0.0 if d2 <= 1.0e-9 else max(0.0, min(1.0, (wx * vx + wy * vy) / d2))
    q = (a[0] + t * vx, a[1] + t * vy)
    return _distance(p, q), t


def candidate_rows(seed: int, count: int, bounds: list[float] | None = None) -> list[dict[str, Any]]:
    """Fixed five draws per candidate; rejection never changes later draws."""
    require(count >= 1, "CANDIDATE_COUNT")
    bounds = bounds or [2450.0, 3950.0, -720.0, 780.0]
    require(len(bounds) == 4 and bounds[0] < bounds[1] and bounds[2] < bounds[3], "PLACEMENT_BOUNDS")
    rng = random.Random(int(seed))
    rows = []
    for index in range(count):
        ux, uy, uyaw, usource, uphase = (rng.random() for _ in range(5))
        rows.append({
            "index": index,
            "local_xy_cm": [bounds[0] + ux * (bounds[1] - bounds[0]),
                            bounds[2] + uy * (bounds[3] - bounds[2])],
            "yaw_deg": -40.0 + uyaw * 80.0,
            "source": FIGURES[min(len(FIGURES) - 1, int(usource * len(FIGURES)))],
            "phase": uphase,
            "draws": [ux, uy, uyaw, usource, uphase],
        })
    return rows


def placement_violations(row: dict[str, Any], occupied_world_xy: list[tuple[float, float]],
                         cameras: list[dict[str, Any]], cfg: dict[str, Any]) -> list[str]:
    local = tuple(float(x) for x in row["local_xy_cm"])
    world = (local[0] + DOCK_ORIGIN[0], local[1] + DOCK_ORIGIN[1])
    bad = []
    if any(_distance(world, p) < cfg["figure_clearance_cm"] for p in occupied_world_xy):
        bad.append("figure_clearance")
    for camera in cameras:
        xy = tuple(camera["xy"])
        if _distance(world, xy) < cfg["camera_clearance_cm"]:
            bad.append("camera_clearance:" + camera["label"])
        yaw = math.radians(float(camera["yaw_deg"]))
        end = (xy[0] + math.cos(yaw) * cfg["sightline_length_cm"],
               xy[1] + math.sin(yaw) * cfg["sightline_length_cm"])
        distance, t = _point_segment_distance(world, xy, end)
        if 0.02 < t < 1.0 and distance < cfg["sightline_half_width_cm"]:
            bad.append("sightline:" + camera["label"])
    return sorted(set(bad))


def forward_chain(source: str, phase: float, xfade: int, start: int = PLAYBACK[0],
                  end: int = PLAYBACK[1], fps: float = 24.0) -> list[dict[str, Any]]:
    """Forward-only, overlapping sections matching the S3LOOPS2 mechanism."""
    source_in, source_out, rate = MOTION[source]
    span = source_out - source_in
    require(span > 0.0 and 0.0 <= phase < 1.0, "MOTION_INPUT")
    cursor, first, rows = int(start), True, []
    while cursor < end:
        offset = source_in + (phase * span if first else 0.0)
        duration = max(xfade + 1, int(round((source_out - offset) / rate * fps)))
        stop = min(end, cursor + duration)
        rows.append({"range": [cursor, stop], "source_in": round(offset, 6),
                     "source_out": source_out, "play_rate": rate, "reverse": False,
                     "ease_in": 0 if first else xfade,
                     "ease_out": 0 if stop == end else xfade})
        if stop >= end:
            break
        cursor, first = stop - xfade, False
        require(len(rows) <= 80, "MOTION_RUNAWAY|" + source)
    validate_chain(rows, xfade, start, end)
    return rows


def validate_chain(rows: list[dict[str, Any]], xfade: int, start: int = PLAYBACK[0],
                   end: int = PLAYBACK[1]) -> None:
    require(rows and rows[0]["range"][0] == start and rows[-1]["range"][1] == end, "MOTION_COVERAGE")
    require(all(row["range"][0] < row["range"][1] for row in rows), "MOTION_EMPTY_SECTION")
    require(all(not row["reverse"] for row in rows), "MOTION_REVERSE")
    for before, after in zip(rows, rows[1:]):
        require(before["range"][1] - after["range"][0] == xfade, "MOTION_XFADE")
        require(before["ease_out"] == xfade and after["ease_in"] == xfade, "MOTION_WEIGHT_RAMP")


def build_placement_plan(cfg: dict[str, Any], occupied_world_xy: list[tuple[float, float]],
                         cameras: list[dict[str, Any]]) -> dict[str, Any]:
    require(cameras, "CAMERAS_UNREADABLE")
    wanted = 1 + cfg["extra_count"]
    rows, rejected = [], []
    occupied = list(occupied_world_xy)
    for candidate in candidate_rows(cfg["seed"], cfg["candidate_count"],
                                    cfg["placement_bounds_local_cm"]):
        violations = placement_violations(candidate, occupied, cameras, cfg)
        if violations:
            rejected.append({"index": candidate["index"], "violations": violations})
            continue
        slot = len(rows)
        source = "Shore05_M53" if slot == 0 else candidate["source"]
        local = candidate["local_xy_cm"]
        surface = float(sand_height(local[0], local[1]))
        foot_offset = float(cfg["foot_offsets_cm"][source])
        world = [local[0] + DOCK_ORIGIN[0], local[1] + DOCK_ORIGIN[1],
                 surface - 2.0 - foot_offset]
        label = "Shore05_M53 Clam" if slot == 0 else "P40 Shore Variant %02d (%s)" % (slot, source)
        rows.append({"slot": slot, "label": label, "source": source, "blueprint": BP_PATHS[source],
                     "animation_name": ANIM_NAMES[source], "local_xy_cm": local, "world_xyz_cm": world,
                     "yaw_deg": candidate["yaw_deg"], "surface_z_cm": surface,
                     "foot_offset_cm": foot_offset, "foot_embed_cm": 2.0,
                     "foot_tier": "measured only after sequence pose probe; planned from S3FEET-compatible offset",
                     "candidate_index": candidate["index"], "draws": candidate["draws"],
                     "motion": forward_chain(source, candidate["phase"], cfg["crossfade_frames"]),
                     "shroud_seed_key": source})
        occupied.append((world[0], world[1]))
        if len(rows) == wanted:
            break
    require(len(rows) == wanted, "FREE_SPOTS|wanted=%d got=%d" % (wanted, len(rows)))
    return {"schema": SCHEMA, "seed": cfg["seed"], "placements": rows,
            "rejected_count": len(rejected), "rejected_first_20": rejected[:20],
            "camera_samples": cameras, "occupied_count": len(occupied_world_xy)}


def srgb_to_linear(value: float) -> float:
    value = float(value)
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def cloth_colour(weave_tint: list[float] | tuple[float, ...],
                 mean_linear: tuple[float, float, float] = WEAVE_MEAN_LINEAR) -> list[float]:
    require(len(weave_tint) >= 3, "WEAVE_TINT")
    out = [max(0.0, min(1.0, float(weave_tint[i]) * mean_linear[i])) for i in range(3)]
    return out + [1.0]


def choose_colour_parameter(available: list[str], candidates: list[str]) -> str:
    by_norm = {"".join(ch.lower() for ch in name if ch.isalnum()): name for name in available}
    hits = []
    for candidate in candidates:
        hit = by_norm.get("".join(ch.lower() for ch in candidate if ch.isalnum()))
        if hit and hit not in hits:
            hits.append(hit)
    require(len(hits) == 1, "COLOUR_PARAMETER|available=%r candidates=%r hits=%r" %
            (available, candidates, hits))
    return hits[0]


def stills_plan() -> list[dict[str, Any]]:
    return [
        {"scene_seconds": 0.0, "purpose": "transport entry/reset baseline; figures should be off camera"},
        {"scene_seconds": 5.0, "purpose": "mid warm-up; inspect cloth energy only"},
        {"scene_seconds": 14.5, "purpose": "last pre-crowd frame; cloth must be settled"},
        {"scene_seconds": 15.0, "purpose": "first B-shot/crowd-visible frame; no reset pop"},
        {"scene_seconds": 35.7, "purpose": "B02 cut; Shore05 and underwear colour"},
        {"scene_seconds": 64.2, "purpose": "B07 close movement; no forward-loop whip"},
        {"scene_seconds": 117.8, "purpose": "late B06 crowd; long-run cloth stability"},
        {"scene_seconds": 189.1, "purpose": "B08 close; colour and pin clearance"},
        {"scene_seconds": 238.0, "purpose": "B12/end; accumulated simulation stability"},
    ]
