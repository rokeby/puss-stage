"""Pure planning helpers for Job 99.  No Unreal import is permitted here."""
from __future__ import annotations

import hashlib
import json
import math
import re


class P99Error(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise P99Error(message)


def enum_name(value):
    """UE 5.8 may stringify enums as NAME, Type.NAME, or <Type.NAME: n>."""
    text = str(value).strip().strip("<>")
    text = text.split(":", 1)[0]
    return text.rsplit(".", 1)[-1].upper()


def guid32(value):
    """UE 5.8 FGuid strings vary; compare their 32 hex digits only."""
    chars = "".join(re.findall(r"[0-9a-fA-F]", str(value))).upper()
    require(len(chars) == 32, "GUID_NORMALIZE|%r|%s" % (value, chars))
    return chars


def stable_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sun_pitch_for_elevation(elevation_deg):
    """Matches InfinityStageCelestialRig.cpp:461 for the setting half."""
    elevation = float(elevation_deg)
    require(-2.0 <= elevation <= 15.0, "SUN_ELEVATION_RANGE|-2..15")
    return -180.0 + elevation


def direction_uv(camera_forward, camera_right, camera_up, direction, hfov_deg, aspect):
    """Project an infinite direction into normalized camera coordinates."""
    def dot(a, b):
        return sum(float(x) * float(y) for x, y in zip(a, b))
    f = dot(direction, camera_forward)
    r = dot(direction, camera_right)
    u = dot(direction, camera_up)
    vfov = math.degrees(2.0 * math.atan(math.tan(math.radians(float(hfov_deg)) / 2.0) / float(aspect)))
    h_angle = math.degrees(math.atan2(r, f))
    v_angle = math.degrees(math.atan2(u, math.hypot(f, r)))
    return {"forward_dot": f, "horizontal_deg": h_angle, "vertical_deg": v_angle,
            "uv": [0.5 + h_angle / float(hfov_deg), 0.5 - v_angle / vfov],
            "hfov_deg": float(hfov_deg), "vfov_deg": vfov,
            "inside": f > 0.0 and abs(h_angle) <= float(hfov_deg) / 2.0 and abs(v_angle) <= vfov / 2.0}


def classify_provenance(label, component, mesh, tags, record_hits, structure_instance=None):
    text = " ".join([str(label), str(component), str(mesh), " ".join(map(str, tags))]).lower()
    if structure_instance is not None:
        return {"tool": "MeshyFixtures meshy_swap P06 + InfinityStageStructureActor::BuildFixtures",
                "confidence": "declaration-proven when instance mapping succeeds",
                "reason": "StructureFixtures ISM; instance order is Station then enabled Station LIGHT attachment"}
    rules = [
        ("puss", "puss_shadow_spot.py", "Puss follow/shadow light"),
        ("p75", "P75 chandelier staging", "P75 owner tag/label"),
        ("p30", "opening_lighting_p13.py / Job 30+43", "P30 owner tag/label"),
        ("facade par", "opening_lighting_p13.py / Job 30+43", "facade PAR label"),
        ("uplight", "P01FloorPracticals ADD_UPLIGHTS / Job 35", "uplight label"),
        ("floor practical", "P01FloorPracticals tool", "floor practical label"),
        ("scaffold", "Q3 P06 UV/scaffold tooling", "scaffold label"),
        ("fx_", "P06 effects tooling", "FX owner tag/label"),
    ]
    for needle, tool, reason in rules:
        if needle in text:
            return {"tool": tool, "confidence": "inferred from live label/tag", "reason": reason,
                    "record_hits": record_hits}
    if record_hits:
        return {"tool": record_hits[0]["tool"], "confidence": "measured by record token match",
                "reason": "live identity token appears in record", "record_hits": record_hits}
    return {"tool": "UNCLEAR", "confidence": "unclear", "reason": "no known owner tag or record token matched",
            "record_hits": []}


def validate_args(raw):
    args = dict(raw)
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "REVERT"), "MODE")
    args["mode"] = mode
    args.setdefault("master_sequence", "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master")
    args.setdefault("passage_label", "Passage 6")
    args.setdefault("passage_actor_prefix", "Passage 06")
    args.setdefault("sun_actor_label", "Infinity Stage - Dusk Sun")
    args.setdefault("sky_actor_label", "Job126 P06 SkyAtmosphere")
    args.setdefault("create_sky_if_missing", True)
    args.setdefault("sun_action", "SHOW_ATMOSPHERE_P06")
    args.setdefault("sun_source_angle_deg", 1.22)
    args.setdefault("arrival_window_s", 6.0)
    args.setdefault("obstruction_action", "UNSET")
    args.setdefault("obstruction_actor_labels", [])
    require(args["obstruction_action"] in ("UNSET", "HIDE_ACTORS_P06"), "OBSTRUCTION_ACTION")
    require(args["sun_action"] in ("DIAGNOSE_ONLY", "SHOW_ATMOSPHERE_P06"), "SUN_ACTION")
    require(args["passage_label"] == "Passage 6", "PASSAGE_SCOPE")
    require(args["passage_actor_prefix"] == "Passage 06", "PASSAGE_ACTOR_SCOPE")
    require(isinstance(args["obstruction_actor_labels"], list), "OBSTRUCTION_ACTOR_LABELS")
    if mode == "APPLY":
        require(args.get("confirm") == "APPLY JOB126 P06 ARRIVAL SUN", "APPLY_CONFIRM")
        require(args.get("dry_report") and len(str(args.get("dry_report_sha256", ""))) == 64,
                "DRY_REPORT_REQUIRED")
        require(args.get("pie_probe_report") and len(str(args.get("pie_probe_report_sha256", ""))) == 64,
                "PIE_PROBE_REPORT_REQUIRED")
        require(args["obstruction_action"] != "UNSET", "CHOOSE_OBSTRUCTION_ACTION")
        require(args["obstruction_actor_labels"] and
                len(args["obstruction_actor_labels"]) == len(set(args["obstruction_actor_labels"])),
                "OBSTRUCTION_ACTOR_LABELS")
    if mode == "REVERT":
        require(args.get("confirm") == "REVERT JOB126 P06 ARRIVAL SUN", "REVERT_CONFIRM")
    for key, lo, hi in (("sun_source_angle_deg", 0.05, 10.0), ("arrival_window_s", 0.1, 30.0)):
        require(lo <= float(args[key]) <= hi, "%s_RANGE" % key.upper())
    return args


def plan_summary(args, dry):
    selected = dry.get("selected_obstruction") or {}
    return {"schema": "job126_plan_v1", "master_sequence": args["master_sequence"],
            "passage_label": args["passage_label"],
            "obstruction": {"action": args["obstruction_action"], "selected": selected,
                            "actor_labels": args.get("obstruction_actor_labels")},
            "sun": {"actor_label": args["sun_actor_label"], "sky_actor_label": args["sky_actor_label"],
                    "create_sky_if_missing": bool(args["create_sky_if_missing"]),
                    "action": args["sun_action"],
                    "source_angle_deg": float(args["sun_source_angle_deg"])}}
