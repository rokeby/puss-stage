"""GOBO SPOT (8 Oct 2026, offline-written, NEVER RUN IN UNREAL): size the twin Shadow Play SpotLights for the
animated gobo (animated_gobo.py, worktree E:/PussStage_gobo, branch gobo-fixes 23b8e32) so the flipbook cell lands
on the Interaction curtain at a chosen width.

WHAT IT WRITES (APPLY/REVERT only): seven properties on the SpotLightComponent of the two SPAWNABLE TEMPLATES named
exactly "Shadow Play Spot (Hangar)" and "Shadow Play Spot (Mouth)" inside ONE Interaction LevelSequence, identical on
both twins: outer_cone_angle, inner_cone_angle, source_radius, soft_source_radius, source_length,
light_function_fade_distance, attenuation_radius.  Nothing else: no keys, no tracks, no level, no Show, no Master.
A property that is driven by a track on either twin is NOT written on either twin and is reported (KEYED).

Modes: DRY (read-only), APPLY (confirm "APPLY GOBOSPOT <CIRCUMSCRIBED|INSCRIBED>"), REVERT (confirm "REVERT GOBOSPOT").
Markers: GOBOSPOT_DRY_OK / GOBOSPOT_APPLY_OK / GOBOSPOT_REVERT_OK |run=<id>|...   or   GOBOSPOT_STOPPED|run=<id>|...
Module globals hold no Unreal objects.  Never Save All, never ends PIE, never reloads the level, no Sequencer UI.

THE MATHS (tiers: [decl] read in an engine header/shader, cited; [bin] installed DLL strings; [prec] in-repo call
precedent; [inf] inferred, not verifiable offline):
  * A spot light function gets UV = LightVector.xy / (LightVector.z * tan(outer)) * 0.5 + 0.5  [decl]
    Shaders/Private/LightFunctionCommon.ush:45-50 (deferred) and LightFunctionAtlas/LightFunctionAtlasCommon.usf:110-115
    (atlas path, Slot.TanOuterAngle).  So UV 0..1 spans exactly +-tan(outer) on both perpendicular axes: the square
    flipbook cell CIRCUMSCRIBES the circular cone (the lit disc is inscribed in the cell).  At distance D the cell
    side is 2*D*tan(outer) measured perpendicular to the beam.  This resolves the earlier UNCLEAR.
  * Variant CIRCUMSCRIBED: half = atan((W/2)/D).  Cell side = W; the cone disc (diameter W) cuts the cell corners
    (about 21.5 % of the cell area is outside the cone).  Uses the full atlas resolution.
  * Variant INSCRIBED: half = atan((W/2*sqrt2)/D).  The cone disc covers a W x W square, but the UV cell itself is
    W*sqrt2 wide, so the flipbook IMAGE is W*sqrt2 unless animated_gobo's material Scale = 1/sqrt2 = 0.7071
    (animated_gobo.py CODE_UV: p = (UV-0.5)/Scale+0.5 [prec, never run]).  The margin outside the image then shows
    the atlas gutter colour (saturate clamp) [inf].
  * Light-function fade is a CAMERA distance, not a light distance: alpha = saturate((F - ViewDistance)/(0.2 F)) with
    ViewDistance = camera -> shaded point [decl] LightFunctionAtlasCommon.usf:80-86, LightFunctionPixelShader.usf:51,
    66-68; LightComponent.h:229-234 (Fade Distance).  The gobo is untouched only while camera distance <= 0.8 F.  The
    plan is F = max(D + 200, camera_distance / 0.8 + 200).
  * Atlas slot resolution: header default 32 px [decl] Renderer/Private/LightFunctionAtlas.h:127-131; runtime cvar
    r.LightFunctionAtlas.SlotResolution exists [bin] UnrealEditor-Renderer.dll strings (help text "The resolution of
    each atlas slot" sits next to it; which string belongs to which name is adjacency-inferred [inf]).  DRY reads it.
  * Cone angles are half-angles in degrees [decl] SpotLightComponent.h:22-27 (UIMax 80); "half" itself [inf, matches
    shadow_play_spot.py's circle maths that ran 6 Oct].  outer/inner are NOT interp (cannot be keyed); SourceRadius,
    SoftSourceRadius, SourceLength [decl] PointLightComponent.h:44-59 and AttenuationRadius [decl]
    LocalLightComponent.h:45-46 ARE interp, so the keyed check matters for them.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import os
import re
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness / system Python.
    unreal = None


MARK = "GOBOSPOT"
FOLDER = "GoboSpot_20261008"
ARGS_NAME = "gobo_spot_args.json"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # animated_gobo.py:61
DEFAULT_SEQUENCE = "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips"
DEFAULT_LABELS = ["Shadow Play Spot (Hangar)", "Shadow Play Spot (Mouth)"]        # shadow_play_spot record I2
DEFAULT_CAMERA_PATTERNS = ["Sleight Hangar Camera", "Sleight Mouth Camera"]       # curtain_sleight bindings
MODES = ("DRY", "APPLY", "REVERT")
VARIANTS = ("CIRCUMSCRIBED", "INSCRIBED")
VARIANT_FACTOR = {"CIRCUMSCRIBED": 1.0, "INSCRIBED": math.sqrt(2.0)}
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CHANNEL_RE = re.compile(r"^(Location|Rotation|Scale)\.([XYZ])(_\d+)?$")   # suffixes: memory ue58-sequencer-read-traps
FLOAT_TOL = 1.0e-3
TWIN_TOL = 0.05
FADE_VIEW_FRACTION = 0.8          # LightFunctionAtlasCommon.usf:84: full LF while ViewDistance <= 0.8 F
FADE_MARGIN_CM = 200.0
ATT_MARGIN_CM = 300.0
INNER_GAP_DEG = 1.0

WRITE_PROPS = ("outer_cone_angle", "inner_cone_angle", "source_radius", "soft_source_radius", "source_length",
               "light_function_fade_distance", "attenuation_radius")
FLOAT_READ_PROPS = WRITE_PROPS + ("intensity", "disabled_brightness")
OTHER_READ_PROPS = ("cast_shadows", "intensity_units", "light_function_material")
# Python name -> UPROPERTY name, for matching property tracks (MovieScenePropertyTrackExtensions.h:42,51 [decl]).
PROPERTY_NAMES = {
    "outer_cone_angle": "OuterConeAngle", "inner_cone_angle": "InnerConeAngle", "source_radius": "SourceRadius",
    "soft_source_radius": "SoftSourceRadius", "source_length": "SourceLength",
    "light_function_fade_distance": "LightFunctionFadeDistance", "attenuation_radius": "AttenuationRadius",
    "intensity": "Intensity", "disabled_brightness": "DisabledBrightness",
}
CVARS = (
    ("r.LightFunctionAtlas", "int"), ("r.Deferred.UsesLightFunctionAtlas", "int"),
    ("r.VolumetricFog.LightFunction", "int"), ("r.VolumetricFog.UsesLightFunctionAtlas", "int"),
    ("r.Lumen.UsesLightFunctionAtlas", "int"), ("r.LightFunctionAtlas.SlotResolution", "int"),
    ("r.LightFunctionAtlas.Size", "int"), ("r.LightFunctionQuality", "float"), ("r.MegaLights.LightFunctions", "int"),
)


class PlanError(ValueError):
    pass


# =====================================================================================================================
# Pure layer (no Unreal).  The harness drives all of it.
# =====================================================================================================================

def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
                          .encode("utf-8")).hexdigest()


def _asset_path(value) -> str:
    return str(value).split(".", 1)[0]


def _r(value, nd=4):
    return None if value is None else round(float(value), nd)


def confirm_text(mode, variant=None):
    if mode == "APPLY":
        return "APPLY GOBOSPOT %s" % (variant or "<VARIANT>")
    if mode == "REVERT":
        return "REVERT GOBOSPOT"
    return "DRY GOBOSPOT"


def normalized_args(raw: dict) -> dict:
    allowed = {"mode", "confirm", "run_id", "variant", "world", "sequence", "light_labels", "curtain_patterns",
               "target_width_cm", "frame_start", "frame_end", "sample_step", "gc_local_boxes", "camera_patterns",
               "camera_distance_cm", "note"}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise PlanError("UNKNOWN_ARGS|%s" % unknown)
    mode = str(raw.get("mode", "DRY")).upper()
    if mode not in MODES:
        raise PlanError("MODE|%s" % mode)
    run_id = str(raw.get("run_id") or "")
    if not RUN_ID_RE.match(run_id):
        raise PlanError("RUN_ID|need explicit [A-Za-z0-9_-]{1,64}; APPLY uses the DRY run_id|%r" % run_id)
    variant = raw.get("variant")
    variant = str(variant).upper() if variant else None
    if mode == "APPLY" and variant not in VARIANTS:
        raise PlanError("VARIANT|APPLY needs variant in %s|%r" % (VARIANTS, variant))
    labels = [str(v).strip() for v in (raw.get("light_labels") or DEFAULT_LABELS)]
    if len(labels) != 2 or len(set(labels)) != 2 or not all(labels):
        raise PlanError("LIGHT_LABELS|need exactly two distinct twin labels|%r" % labels)
    patterns = [str(v) for v in (raw.get("curtain_patterns") or ["Curtain"])]
    if not patterns or not all(patterns):
        raise PlanError("CURTAIN_PATTERNS|need non-empty substrings")
    start, end = int(raw.get("frame_start", 175)), int(raw.get("frame_end", 250))
    step = int(raw.get("sample_step", 1))
    if start < 0 or end < start or step < 1:
        raise PlanError("FRAME_RANGE|need 0 <= start <= end, step >= 1|%d,%d,%d" % (start, end, step))
    width = raw.get("target_width_cm")
    if width is not None and not float(width) > 0.0:
        raise PlanError("TARGET_WIDTH|must be > 0|%r" % width)
    cam = raw.get("camera_distance_cm")
    if cam is not None and not float(cam) > 0.0:
        raise PlanError("CAMERA_DISTANCE|must be > 0|%r" % cam)
    boxes = {}
    for path, box in (raw.get("gc_local_boxes") or {}).items():
        try:
            boxes[_asset_path(path)] = {"lo": [float(box[a][0]) for a in "xyz"], "hi": [float(box[a][1]) for a in "xyz"]}
        except (KeyError, TypeError, IndexError, ValueError):
            raise PlanError("GC_LOCAL_BOX|%s needs {x:[lo,hi],y:[..],z:[..]} in cm" % path)
    sequence = _asset_path(raw.get("sequence", DEFAULT_SEQUENCE))
    if not sequence.startswith("/Game/"):
        raise PlanError("SEQUENCE_PATH|%s" % sequence)
    return {"mode": mode, "confirm": raw.get("confirm"), "run_id": run_id, "variant": variant,
            "world": _asset_path(raw.get("world", EXPECTED_WORLD)), "sequence": sequence, "light_labels": labels,
            "curtain_patterns": patterns, "target_width_cm": None if width is None else float(width),
            "frame_start": start, "frame_end": end, "sample_step": step, "gc_local_boxes": boxes,
            "camera_patterns": [str(v) for v in (raw.get("camera_patterns") or DEFAULT_CAMERA_PATTERNS)],
            "camera_distance_cm": None if cam is None else float(cam)}


def sample_frames(args):
    frames = list(range(args["frame_start"], args["frame_end"] + 1, args["sample_step"]))
    if frames[-1] != args["frame_end"]:
        frames.append(args["frame_end"])
    return frames


# ---- vectors ---------------------------------------------------------------------------------------------------------

def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _add(a, b, s=1.0):
    return [a[0] + s * b[0], a[1] + s * b[1], a[2] + s * b[2]]


def rot_axes(pitch, yaw, roll):
    """UE FRotationMatrix axes (X forward, Y right, Z up) [inf: standard UE convention; matches shadow_play_spot's
    aim maths, which the 6 Oct APPLY placed on the record's aim point]."""
    p, y, r = math.radians(pitch), math.radians(yaw), math.radians(roll)
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    x = [cp * cy, cp * sy, sp]
    yv = [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp]
    z = [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp]
    return x, yv, z


# ---- keys -------------------------------------------------------------------------------------------------------------

def interp_keys(keys, frame, default=None):
    """Linear between keys, held outside.  Exact for the dense/linear keys the Conductor tools write; a cubic
    tangent between sparse keys is NOT modelled [inf]."""
    keys = sorted(keys)
    if not keys:
        return default
    if frame <= keys[0][0]:
        return float(keys[0][1])
    if frame >= keys[-1][0]:
        return float(keys[-1][1])
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= frame <= f1:
            return float(v0) if f1 == f0 else float(v0) + (float(v1) - float(v0)) * (frame - f0) / float(f1 - f0)
    return float(keys[-1][1])


def step_keys(keys, frame, default):
    """Bool channel (spawn track): last key at or before the frame, else the default."""
    out = default
    for f, v in sorted(keys):
        if f <= frame:
            out = bool(v)
    return bool(out)


def pose_at(pose_src, frame):
    """pose_src: {"static": pose} or {"channels": {"Location.X": {"keys": [...], "default": v}, ...}, "base": pose}."""
    if "channels" not in pose_src:
        return copy.deepcopy(pose_src["static"])
    base, ch = pose_src["base"], pose_src["channels"]

    def val(group, axis, fallback):
        row = ch.get("%s.%s" % (group, axis))
        if row is None:
            return fallback
        return interp_keys(row.get("keys") or [], frame, row.get("default", fallback))

    return {"loc": [val("Location", a, base["loc"][i]) for i, a in enumerate("XYZ")],
            "roll": val("Rotation", "X", base["roll"]), "pitch": val("Rotation", "Y", base["pitch"]),
            "yaw": val("Rotation", "Z", base["yaw"]),
            "scale": [val("Scale", a, base.get("scale", [1.0, 1.0, 1.0])[i]) for i, a in enumerate("XYZ")]}


# ---- geometry ---------------------------------------------------------------------------------------------------------

def box_at(cand, pose):
    """Oriented box: pose + local box scaled by the pose scale."""
    scale = pose.get("scale") or [1.0, 1.0, 1.0]
    lo, hi = [], []
    for i in range(3):
        a, b = cand["local"]["lo"][i] * scale[i], cand["local"]["hi"][i] * scale[i]
        lo.append(min(a, b))
        hi.append(max(a, b))
    return {"loc": list(pose["loc"]), "pitch": pose.get("pitch", 0.0), "yaw": pose.get("yaw", 0.0),
            "roll": pose.get("roll", 0.0), "lo": lo, "hi": hi}


def ray_box(origin, direction, box):
    """Ray (t >= 0) against an oriented box.  Returns None, {"inside": True}, or the entry hit."""
    axes = rot_axes(box["pitch"], box["yaw"], box["roll"])
    rel = _sub(origin, box["loc"])
    o = [_dot(rel, ax) for ax in axes]
    d = [_dot(direction, ax) for ax in axes]
    tmin, tmax, enter, sign = 0.0, float("inf"), None, 0
    for i in range(3):
        lo, hi = box["lo"][i], box["hi"][i]
        if abs(d[i]) < 1.0e-12:
            if o[i] < lo or o[i] > hi:
                return None
            continue
        t1, t2 = (lo - o[i]) / d[i], (hi - o[i]) / d[i]
        tn, tf = min(t1, t2), max(t1, t2)
        if tn > tmin:
            tmin, enter, sign = tn, i, (-1 if t1 < t2 else 1)
        tmax = min(tmax, tf)
        if tmin > tmax:
            return None
    if enter is None:
        return {"inside": True}
    normal = [sign * c for c in axes[enter]]
    others = [i for i in range(3) if i != enter]
    # width axis = the in-face axis that is more horizontal in world; height = the other
    others.sort(key=lambda i: abs(axes[i][2]))
    w_ax, h_ax = others
    point = _add(origin, direction, tmin)
    local = [_dot(_sub(point, box["loc"]), ax) for ax in axes]
    cos_i = min(1.0, abs(_dot(direction, normal)))
    return {"t": tmin, "point": point, "normal": normal, "face_axis": enter, "width_axis": w_ax, "height_axis": h_ax,
            "width_cm": box["hi"][w_ax] - box["lo"][w_ax], "height_cm": box["hi"][h_ax] - box["lo"][h_ax],
            "incidence_deg": math.degrees(math.acos(cos_i)), "local": local}


def footprint(spot_pose, half_deg, box, hit):
    """Where the UV cell corners (and the cone disc) land on the hit face's plane, in the face's width/height axes.
    Corners are the rays X + (+-tan)Y + (+-tan)Z of the light frame (LightFunctionAtlasCommon.usf:113 [decl]);
    which of Y/Z is U vs V does not change a square's size [inf]."""
    x, y, z = rot_axes(spot_pose["pitch"], spot_pose["yaw"], spot_pose["roll"])
    axes = rot_axes(box["pitch"], box["yaw"], box["roll"])
    wa, ha = axes[hit["width_axis"]], axes[hit["height_axis"]]
    tan = math.tan(math.radians(half_deg))
    origin, n, p0 = spot_pose["loc"], hit["normal"], hit["point"]

    def land(dirn):
        den = _dot(dirn, n)
        if abs(den) < 1.0e-12:
            return None
        t = _dot(_sub(p0, origin), n) / den
        if t <= 0.0:
            return None
        p = _add(origin, dirn, t)
        rel = _sub(p, box["loc"])
        return [_dot(rel, wa), _dot(rel, ha)]

    def bbox(points, name):
        if any(p is None for p in points):
            return {name + "_unbounded": True}
        ws, hs = [p[0] for p in points], [p[1] for p in points]
        inside = (min(ws) >= box["lo"][hit["width_axis"]] - 1.0e-6 and max(ws) <= box["hi"][hit["width_axis"]] + 1.0e-6
                  and min(hs) >= box["lo"][hit["height_axis"]] - 1.0e-6 and max(hs) <= box["hi"][hit["height_axis"]] + 1.0e-6)
        return {name + "_width_cm": max(ws) - min(ws), name + "_height_cm": max(hs) - min(hs), name + "_inside_face": inside}

    corners = [land(_add(_add(x, y, su * tan), z, sv * tan)) for su in (-1, 1) for sv in (-1, 1)]
    disc = [land(_add(_add(x, y, tan * math.cos(a)), z, tan * math.sin(a)))
            for a in [2.0 * math.pi * k / 72.0 for k in range(72)]]
    out = bbox(corners, "cell")
    out.update(bbox(disc, "disc"))
    return out


def trace_twin(spot_pose, candidates, frame):
    """Nearest curtain hit plus any nearer non-curtain hits, at one frame."""
    direction = rot_axes(spot_pose["pitch"], spot_pose["yaw"], spot_pose["roll"])[0]
    rows = []
    for cand in candidates:
        if cand.get("local") is None:
            continue
        if not cand_present(cand, frame):
            continue
        box = box_at(cand, pose_at(cand["pose"], frame))
        hit = ray_box(spot_pose["loc"], direction, box)
        if hit is None:
            continue
        if hit.get("inside"):
            rows.append({"label": cand["label"], "inside": True, "is_curtain": cand["is_curtain"]})
            continue
        rows.append({"label": cand["label"], "is_curtain": cand["is_curtain"], "hit": hit, "box": box})
    hits = sorted((r for r in rows if not r.get("inside")), key=lambda r: r["hit"]["t"])
    curtains = [r for r in hits if r["is_curtain"]]
    curtain = curtains[0] if curtains else None
    nearer = [r for r in hits if not r["is_curtain"] and curtain is not None and r["hit"]["t"] < curtain["hit"]["t"]]
    inside = [r["label"] for r in rows if r.get("inside")]
    return curtain, nearer, inside


def cand_present(cand, frame):
    spawn = cand.get("spawn")
    if not spawn:
        return True
    return step_keys(spawn.get("keys") or [], frame, bool(spawn.get("default", False)))


# ---- plan -------------------------------------------------------------------------------------------------------------

def variant_props(variant, d_cm, w_cm, fade_floor_cm, att_current_max):
    half = math.degrees(math.atan((w_cm / 2.0) * VARIANT_FACTOR[variant] / d_cm))
    return {
        "outer_cone_angle": half,
        "inner_cone_angle": max(0.0, half - INNER_GAP_DEG),
        "source_radius": 0.0, "soft_source_radius": 0.0, "source_length": 0.0,
        "light_function_fade_distance": max(d_cm + FADE_MARGIN_CM, fade_floor_cm or 0.0),
        "attenuation_radius": max(d_cm + ATT_MARGIN_CM, att_current_max or 0.0),
    }


def keyed_props(live):
    """Write-set properties driven by a track on EITHER twin (skipped on both, so the twins stay identical)."""
    out = set()
    for spot in live["spots"].values():
        for row in spot.get("keyed") or []:
            if row["prop"] in WRITE_PROPS:
                out.add(row["prop"])
    return sorted(out)


def write_set(plan_props, keyed):
    return {k: float(v) for k, v in plan_props.items() if k in WRITE_PROPS and k not in keyed}


def build_report(args, live):
    """Everything DRY decides, from a plain `live` dict (read by _read_live, or synthetic in the harness)."""
    refusals, flags = [], []
    if live.get("pie"):
        refusals.append("PIE_OR_SIE_ACTIVE")
    if live.get("sequencer_open"):
        refusals.append("SEQUENCER_IS_OPEN|%s" % live["sequencer_open"])
    if live.get("world") != args["world"]:
        refusals.append("WRONG_WORLD|%s" % live.get("world"))
    if live.get("census") != {"content": [], "maps": []}:
        refusals.append("DIRTY_CENSUS|%s" % live.get("census"))
    if live.get("record_exists"):
        refusals.append("RECORD_EXISTS|%s|REVERT first" % live.get("record_path"))
    frames = list(live["frames"])
    twins = {}
    for label in args["light_labels"]:
        spot = live["spots"].get(label) or {"count": 0}
        if spot.get("count") != 1:
            refusals.append("LIGHT_LABEL_COUNT|%s|%s" % (label, spot.get("count", 0)))
            continue
        if not spot.get("is_spot"):
            refusals.append("NOT_SPOTLIGHT_TEMPLATE|%s" % label)
            continue
        if spot.get("pose_unusable"):
            refusals.append("SPOT_POSE_UNUSABLE|%s|%s" % (label, spot["pose_unusable"]))
            continue
        absent = [f for f in frames if not cand_present(spot, f)]
        if absent:
            flags.append("SPOT_NOT_SPAWNED|%s|frames=%s" % (label, _span(absent)))
        per_frame, missed, nearer_all, inside_all = {}, [], {}, set()
        for frame in frames:
            pose = pose_at(spot["pose"], frame)
            curtain, nearer, inside = trace_twin(pose, live["candidates"], frame)
            inside_all.update(inside)
            if curtain is None:
                missed.append(frame)
                continue
            h = curtain["hit"]
            per_frame[frame] = {"pose": pose, "curtain": curtain["label"], "d": h["t"], "width": h["width_cm"],
                                "height": h["height_cm"], "incidence": h["incidence_deg"], "point": h["point"],
                                "box": curtain["box"], "hit": h}
            for r in nearer:
                nearer_all.setdefault(r["label"], {"min_d": r["hit"]["t"], "width_cm": r["hit"]["width_cm"],
                                                   "height_cm": r["hit"]["height_cm"]})
        if missed:
            refusals.append("CURTAIN_NOT_HIT|%s|frames=%s" % (label, _span(missed)))
        if inside_all:
            flags.append("SPOT_INSIDE_BOX|%s|%s" % (label, sorted(inside_all)))
        if nearer_all:
            flags.append("NEARER_SURFACE|%s|%s" % (label, sorted(nearer_all)))
        twins[label] = {"per_frame": per_frame, "nearer": nearer_all, "missed": missed}
    report = {"run": args["run_id"], "mode": "DRY", "args": _plain_args(args), "frames": [frames[0], frames[-1]],
              "refusals": refusals, "flags": flags, "cvars": live.get("cvars"), "keyed": {}, "twins": {},
              "originals": {k: (v or {}).get("props") for k, v in live["spots"].items()}, "plan": None}
    for label, spot in live["spots"].items():
        report["keyed"][label] = spot.get("keyed") or []
        units = str((spot.get("props") or {}).get("intensity_units", ""))
        if units and "CANDELA" not in units.upper():
            flags.append("INTENSITY_UNITS|%s|%s|a cone change alters curtain illuminance [inf]" % (label, units))
    if len(twins) != 2 or any(not t["per_frame"] for t in twins.values()):
        report["apply_ready"] = False
        return _finish(report)

    summary = {}
    for label, t in twins.items():
        pf = t["per_frame"]
        ds = [row["d"] for row in pf.values()]
        ref_frame = max(pf, key=lambda f: pf[f]["d"])
        ref = pf[ref_frame]
        summary[label] = {"d_min_cm": min(ds), "d_max_cm": max(ds), "ref_frame": ref_frame, "curtain": ref["curtain"],
                          "curtain_width_cm": ref["width"], "curtain_height_cm": ref["height"],
                          "incidence_deg": ref["incidence"], "hit_point": ref["point"],
                          "spot_pose": ref["pose"], "moves": _moves(pf)}
        if max(ds) > 0 and (max(ds) - min(ds)) / max(ds) > TWIN_TOL:
            flags.append("D_VARIES_OVER_RANGE|%s|%.1f..%.1f" % (label, min(ds), max(ds)))
    la, lb = args["light_labels"]
    da, db = summary[la]["d_max_cm"], summary[lb]["d_max_cm"]
    d = max(da, db)
    twin_diff = abs(da - db) / d
    if twin_diff > TWIN_TOL:
        flags.append("TWIN_DISTANCE_DIFF|%s=%.1f|%s=%.1f|%.1f%%" % (la, da, lb, db, 100.0 * twin_diff))
    wa, wb = summary[la]["curtain_width_cm"], summary[lb]["curtain_width_cm"]
    if abs(wa - wb) / max(wa, wb) > TWIN_TOL:
        flags.append("TWIN_CURTAIN_WIDTH_DIFF|%s=%.1f|%s=%.1f" % (la, wa, lb, wb))
    w_source = "target_width_cm" if args["target_width_cm"] else "0.9 x min curtain width"
    w = args["target_width_cm"] or 0.9 * min(wa, wb)

    cam = camera_distance(args, live, twins)
    fade_floor = cam["max_cm"] / FADE_VIEW_FRACTION + FADE_MARGIN_CM if cam["max_cm"] else None
    if not cam["max_cm"]:
        flags.append("CAMERA_DISTANCE_UNKNOWN|fade = D+200 only; pass camera_distance_cm")
    att_now = max(float((live["spots"][l]["props"] or {}).get("attenuation_radius") or 0.0) for l in args["light_labels"])
    keyed = keyed_props(live)
    for prop in keyed:
        flags.append("KEYED_NOT_WRITTEN|%s" % prop)
    origs = [live["spots"][l]["props"] for l in args["light_labels"]]
    differ = [p for p in WRITE_PROPS if abs(float(origs[0].get(p) or 0) - float(origs[1].get(p) or 0)) > FLOAT_TOL]
    if differ:
        flags.append("TWIN_ORIGINALS_DIFFER|%s" % differ)
    variants = {}
    for variant in VARIANTS:
        props = variant_props(variant, d, w, fade_floor, att_now)
        fits = {}
        for label in args["light_labels"]:
            worst = {"cell_inside_face": True, "disc_inside_face": True}
            sample = None
            for frame, row in sorted(twins[label]["per_frame"].items()):
                fp = footprint(row["pose"], props["outer_cone_angle"], row["box"], row["hit"])
                worst["cell_inside_face"] &= bool(fp.get("cell_inside_face", False))
                worst["disc_inside_face"] &= bool(fp.get("disc_inside_face", False))
                if frame == summary[label]["ref_frame"]:
                    sample = fp
            fits[label] = dict(worst, at_ref_frame={k: _r(v, 2) if isinstance(v, float) else v
                                                   for k, v in (sample or {}).items()})
        for prop in ("light_function_fade_distance",):
            for label in args["light_labels"]:
                now = float(live["spots"][label]["props"].get(prop) or 0.0)
                if props[prop] < now - FLOAT_TOL:
                    flags.append("FADE_LOWERS_CURRENT|%s|%s|%.0f->%.0f" % (variant, label, now, props[prop]))
        variants[variant] = {
            "props": {k: _r(v, 6) for k, v in props.items()}, "write": {k: _r(v, 6) for k, v in write_set(props, keyed).items()},
            "keyed_skipped": keyed,
            "cell_side_perp_cm": 2.0 * d * math.tan(math.radians(props["outer_cone_angle"])),
            "disc_diameter_perp_cm": 2.0 * d * math.tan(math.radians(props["outer_cone_angle"])),
            "gobo_scale_for_image_W": 1.0 if variant == "CIRCUMSCRIBED" else _r(1.0 / math.sqrt(2.0), 6),
            "cone_clips_cell_corners": variant == "CIRCUMSCRIBED",
            "cm_per_slot_px": {str(px): _r(2.0 * d * math.tan(math.radians(props["outer_cone_angle"])) / px, 3)
                               for px in sorted({32, int(_slot_px(live) or 32)})},
            "fits_on_curtain": fits,
        }
    plan = {"d_cm": d, "d_source": "max over twins of max over sampled frames", "w_cm": w, "w_source": w_source,
            "twin_distance_diff": twin_diff, "camera": cam, "fade_floor_cm": fade_floor, "attenuation_now_max_cm": att_now,
            "variants": variants, "twins": summary, "keyed_skipped": keyed}
    report["plan"] = plan
    report["apply_ready"] = not refusals
    return _finish(report)


def _slot_px(live):
    value = (live.get("cvars") or {}).get("r.LightFunctionAtlas.SlotResolution")
    try:
        return int(value) if value and int(value) > 0 else None
    except (TypeError, ValueError):
        return None


def _moves(per_frame):
    poses = [row["pose"] for _, row in sorted(per_frame.items())]
    first = poses[0]
    return any(max(abs(a - b) for a, b in zip(p["loc"], first["loc"])) > 0.01 or
               abs(p["pitch"] - first["pitch"]) > 1e-3 or abs(p["yaw"] - first["yaw"]) > 1e-3 for p in poses)


def camera_distance(args, live, twins):
    """Largest camera -> curtain-hit distance over the range, each camera assigned to its nearer twin."""
    if args.get("camera_distance_cm"):
        return {"max_cm": float(args["camera_distance_cm"]), "source": "arg camera_distance_cm", "rows": []}
    rows, best = [], 0.0
    for cam in live.get("cameras") or []:
        if cam.get("unusable"):
            rows.append({"label": cam["label"], "unusable": cam["unusable"]})
            continue
        worst = 0.0
        for frame in live["frames"]:
            loc = pose_at(cam["pose"], frame)["loc"]
            ds = [math.dist(loc, t["per_frame"][frame]["point"]) for t in twins.values() if frame in t["per_frame"]]
            if ds:
                worst = max(worst, min(ds))
        rows.append({"label": cam["label"], "max_cm": worst})
        best = max(best, worst)
    return {"max_cm": best or None, "source": "camera bindings (transform tracks, world space)" if best else None,
            "rows": rows}


def _span(frames):
    return "%d..%d(%d)" % (frames[0], frames[-1], len(frames)) if frames else "-"


def _plain_args(args):
    """Args that shape the plan (mode/variant/confirm excluded so DRY and APPLY digests can match)."""
    return {k: v for k, v in args.items() if k not in ("confirm", "mode", "variant")}


def _finish(report):
    """Digest over the decisions an APPLY must find unchanged: originals, keyed set and the variant write sets."""
    plan = report.get("plan") or {}
    report["plan_digest"] = _digest({
        "originals": _round_tree(report.get("originals")),
        "keyed": {k: sorted(r["prop"] for r in v) for k, v in (report.get("keyed") or {}).items()},
        "variants": {k: v["write"] for k, v in (plan.get("variants") or {}).items()},
        "d": _r(plan.get("d_cm"), 2), "w": _r(plan.get("w_cm"), 2), "args": _round_tree(report.get("args")),
    })
    return report


def _round_tree(value):
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {k: _round_tree(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round_tree(v) for v in value]
    return value


def readback_failures(got: dict, want: dict, label=""):
    out = []
    for prop, value in want.items():
        g = got.get(prop)
        if isinstance(value, float) or isinstance(value, int) and not isinstance(value, bool):
            if g is None or abs(float(g) - float(value)) > FLOAT_TOL * max(1.0, abs(float(value))):
                out.append("READBACK|%s|%s|got=%r|want=%r" % (label, prop, g, value))
        elif g != value:
            out.append("READBACK|%s|%s|got=%r|want=%r" % (label, prop, g, value))
    return out


def exact_census(census, package):
    want = {"content": [package], "maps": []}
    got = {"content": sorted(census.get("content") or []), "maps": sorted(census.get("maps") or [])}
    return [] if got == want else ["CENSUS_SCOPE|got=%s|want=%s" % (got, want)]


# =====================================================================================================================
# Unreal transport.  NEVER RUN YET.  The harness drives it with a fake `unreal`; every call's tier is in API_TABLE.
# =====================================================================================================================

API_TABLE = [
    ("LevelSequence.get_bindings / binding.get_display_name / get_object_template", "prec",
     "animated_gobo.py:437-453 (never run); shadow_play_spot.py:776,899 (ran 6 Oct, record applied=True)"),
    ("template.spot_light_component / root_component relative_location|rotation|scale3d", "prec",
     "shadow_play_spot.py:776-778,950; interaction_curtain_probe.py:204-210 (ran 6 Oct, JSON read-back)"),
    ("template.geometry_cache_component.geometry_cache", "prec", "interaction_curtain_probe.py:212-215 (ran 6 Oct)"),
    ("template.static_mesh_component.static_mesh.get_bounding_box()", "decl+inf",
     "StaticMesh.h:2203-2204 BlueprintPure; .min/.max on FBox in Python: inf"),
    ("binding.get_tracks / track class name / section.get_all_channels / channel_name", "prec",
     "shadow_play_spot.py:741-745 (ran)"),
    ("key.get_time(time_unit=DISPLAY_RATE).frame_number.value / key.get_value / channel.get_default", "prec",
     "shadow_play_spot.py:735-737,753 (ran)"),
    ("track.get_property_name / get_property_path", "decl+prec",
     "MovieScenePropertyTrackExtensions.h:42,51; shadow_play_spot.py:943"),
    ("binding.get_parent / GuidLibrary.conv_guid_to_string", "prec", "curtain_sleight.py:1264-1265,1332-1334 (ran)"),
    ("EditorActorSubsystem.get_all_level_actors / actor.get_actor_bounds(False) -> (origin, extent)", "prec",
     "curtain_sleight.py:1273-1274,1418,1444 (ran)"),
    ("SystemLibrary.get_console_variable_int_value|float_value", "decl+inf",
     "KismetSystemLibrary.h:622,631; Python name SystemLibrary: inf"),
    ("component.set_editor_property(<7 props>) on a template, after modify()", "inf",
     "shadow_play_spot.py:910-916 set cones/radius on a FRESH template (ran); writes on an existing template: inf; "
     "light_function_fade_distance / source_length / soft_source_radius setters: decl LightComponent.h:233, "
     "PointLightComponent.h:52,59"),
    ("EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)", "prec", "animated_gobo.py:843; curtain_sleight.py:1864"),
    ("EditorLoadingAndSavingUtils.get_dirty_content_packages|map_packages", "prec", "animated_gobo.py:425-429"),
]


def _here():
    if unreal is None:
        return os.path.dirname(os.path.abspath(__file__))
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        "CodexConductor", FOLDER)


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def record_path(sequence):
    return os.path.join(_here(), "gobo_spot_record_%s.json" % sequence.rsplit("/", 1)[1])


def dry_path(run):
    return os.path.join(_here(), "gobo_spot_dry_%s.json" % run)


def _stop(run, text):
    message = "%s_STOPPED|run=%s|%s" % (MARK, run, text)
    if unreal is not None:
        unreal.log_error(message)
    raise RuntimeError(message)


def _load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(value, indent=1, sort_keys=True, default=str, ensure_ascii=False)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _census():
    return {"content": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _content_file(asset_path):
    return os.path.join(_project(), "Content", *asset_path[len("/Game/"):].split("/")) + ".uasset"


def _guid(binding):
    return str(unreal.GuidLibrary.conv_guid_to_string(binding.get_id()))


def _path_of(obj):
    return _asset_path(obj.get_path_name()) if obj is not None else None


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _channel_rows(section):
    out = {}
    for ch in section.get_all_channels():
        m = CHANNEL_RE.match(str(ch.channel_name))
        if not m:
            continue
        unit = unreal.MovieSceneTimeUnit.DISPLAY_RATE
        keys = []
        for k in ch.get_keys():
            t = k.get_time(time_unit=unit)
            keys.append([int(t.frame_number.value) + float(getattr(t, "sub_frame", 0.0) or 0.0), float(k.get_value())])
        try:
            default = float(ch.get_default())
        except Exception:  # noqa: BLE001 - no default set: fall back to the template pose
            default = None
        row = {"keys": keys}
        if default is not None:
            row["default"] = default
        out["%s.%s" % (m.group(1), m.group(2))] = row
    return out


def _template_pose(template):
    root = template.get_editor_property("root_component")
    loc, rot = root.get_editor_property("relative_location"), root.get_editor_property("relative_rotation")
    scale = root.get_editor_property("relative_scale3d")
    return {"loc": _vec(loc), "pitch": float(rot.pitch), "yaw": float(rot.yaw), "roll": float(rot.roll),
            "scale": _vec(scale) if scale is not None else [1.0, 1.0, 1.0]}


def _binding_pose(binding, template):
    """World pose source: the binding's own 3D transform track if any (Conductor tools key world space, no parent:
    curtain_sleight.py:402-416 [decl comment]); else the template root.  An attach track makes it UNUSABLE."""
    base = _template_pose(template)
    tracks = list(binding.get_tracks())
    names = [t.get_class().get_name() for t in tracks]
    if any("Attach" in n for n in names):
        return None, "ATTACHED (pose is parent-relative)"
    xf = [t for t in tracks if t.get_class().get_name() == "MovieScene3DTransformTrack"]
    if not xf:
        return {"static": base}, "template"
    if len(xf) != 1 or len(list(xf[0].get_sections())) != 1:
        return None, "TRANSFORM_TRACK_SHAPE|tracks=%d" % len(xf)
    return {"channels": _channel_rows(list(xf[0].get_sections())[0]), "base": base}, \
        "track:%s" % xf[0].get_display_name()


def _spawn_row(binding):
    for t in binding.get_tracks():
        if t.get_class().get_name() == "MovieSceneSpawnTrack":
            sections = list(t.get_sections())
            if not sections:
                return None
            ch = list(sections[0].get_all_channels())[0]
            unit = unreal.MovieSceneTimeUnit.DISPLAY_RATE
            keys = [[int(k.get_time(time_unit=unit).frame_number.value), bool(k.get_value())] for k in ch.get_keys()]
            try:
                default = bool(ch.get_default())
            except Exception:  # noqa: BLE001
                default = False
            return {"keys": keys, "default": default}
    return None


def _spot_component(template):
    if template is None or not isinstance(template, unreal.SpotLight):
        return None
    return template.get_editor_property("spot_light_component")


def _read_props(comp):
    out = {}
    for prop in FLOAT_READ_PROPS:
        out[prop] = float(comp.get_editor_property(prop))
    out["cast_shadows"] = bool(comp.get_editor_property("cast_shadows"))
    out["intensity_units"] = str(comp.get_editor_property("intensity_units"))
    out["light_function_material"] = _path_of(comp.get_editor_property("light_function_material"))
    return out


def _keyed_rows(seq, binding):
    """Property tracks on the spot binding or on any child (component) binding of it."""
    me = _guid(binding)
    owners = [binding]
    for b in seq.get_bindings():
        parent = b.get_parent()
        if parent is not None and parent.is_valid() and _guid(parent) == me:
            owners.append(b)
    rows = []
    reverse = {v: k for k, v in PROPERTY_NAMES.items()}
    for owner in owners:
        for t in owner.get_tracks():
            if not hasattr(t, "get_property_name"):
                continue
            name = str(t.get_property_name())
            path = str(t.get_property_path()) if hasattr(t, "get_property_path") else name
            prop = reverse.get(name) or reverse.get(path.rsplit(".", 1)[-1])
            if prop is None:
                continue
            nkeys = 0
            for s in t.get_sections():
                for ch in s.get_all_channels():
                    nkeys += len(list(ch.get_keys()))
            rows.append({"prop": prop, "property_name": name, "property_path": path,
                         "binding": str(owner.get_display_name()), "track_class": t.get_class().get_name(),
                         "keys": nkeys})
    return rows


def _template_local_box(template, gc_boxes):
    """(local box, how) for a spawnable template: static mesh bounds, or a GC box from args (no GC bounds API)."""
    try:
        smc = template.get_editor_property("static_mesh_component")
    except Exception:  # noqa: BLE001 - not a StaticMeshActor
        smc = None
    if smc is not None:
        mesh = smc.get_editor_property("static_mesh")
        if mesh is not None:
            box = mesh.get_bounding_box()
            return {"lo": _vec(box.min), "hi": _vec(box.max)}, "mesh:%s" % _path_of(mesh), _path_of(mesh)
    try:
        gcc = template.get_editor_property("geometry_cache_component")
    except Exception:  # noqa: BLE001
        gcc = None
    if gcc is not None:
        gc = _path_of(gcc.get_editor_property("geometry_cache"))
        if gc in gc_boxes:
            return gc_boxes[gc], "gc_box_arg:%s" % gc, gc
        return None, "GC_BOX_UNKNOWN|%s|pass gc_local_boxes" % gc, gc
    return None, "NO_GEOMETRY", None


def _matches(patterns, *texts):
    return any(p.lower() in str(t).lower() for p in patterns for t in texts if t)


def _read_candidates(seq, args, spot_labels):
    out = []
    for b in seq.get_bindings():
        label = str(b.get_display_name())
        if label in spot_labels:
            continue
        template = b.get_object_template()
        if template is None:
            continue
        local, how, asset = _template_local_box(template, args["gc_local_boxes"])
        is_curtain = _matches(args["curtain_patterns"], label, asset)
        if local is None and not is_curtain:
            continue
        pose, src = _binding_pose(b, template)
        row = {"label": label, "source": "spawnable", "is_curtain": is_curtain, "geometry": how, "asset": asset,
               "pose_source": src, "spawn": _spawn_row(b)}
        if local is None or pose is None:
            row.update({"local": None, "unmeasurable": how if local is None else src})
        else:
            row.update({"local": local, "pose": pose})
        out.append(row)
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        label = str(actor.get_actor_label())
        mesh = None
        try:
            smc = actor.get_component_by_class(unreal.StaticMeshComponent)
            mesh = _path_of(smc.get_editor_property("static_mesh")) if smc is not None else None
        except Exception:  # noqa: BLE001
            mesh = None
        if not _matches(args["curtain_patterns"], label, mesh):
            continue
        origin, extent = actor.get_actor_bounds(False)
        o, e = _vec(origin), _vec(extent)
        out.append({"label": label, "source": "level_actor(world AABB)", "is_curtain": True, "asset": mesh,
                    "geometry": "aabb", "pose_source": "aabb", "spawn": None,
                    "local": {"lo": [-v for v in e], "hi": list(e)},
                    "pose": {"static": {"loc": o, "pitch": 0.0, "yaw": 0.0, "roll": 0.0, "scale": [1.0, 1.0, 1.0]}}})
    return out


def _read_cameras(seq, args):
    out = []
    for b in seq.get_bindings():
        label = str(b.get_display_name())
        if "/" in label or not _matches(args["camera_patterns"], label):
            continue
        template = b.get_object_template()
        if template is None:
            out.append({"label": label, "unusable": "POSSESSABLE (no template)"})
            continue
        pose, src = _binding_pose(b, template)
        out.append({"label": label, "pose": pose, "pose_source": src} if pose else {"label": label, "unusable": src})
    return out


def _read_cvars():
    out = {}
    lib = unreal.SystemLibrary
    for name, kind in CVARS:
        try:
            out[name] = (lib.get_console_variable_float_value(name) if kind == "float"
                         else lib.get_console_variable_int_value(name))
        except Exception as exc:  # noqa: BLE001 - absent cvar: report, never fail DRY
            out[name] = "ERROR:%s" % exc
    return out


def _spots(seq, labels):
    """label -> list of (binding, component); component None if the template is not a SpotLight."""
    by = {label: [] for label in labels}
    for b in seq.get_bindings():
        label = str(b.get_display_name())
        if label in by:
            by[label].append((b, _spot_component(b.get_object_template())))
    return by


def _read_live(args, seq):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    current = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    live = {"pie": editor.get_game_world() is not None,
            "sequencer_open": _path_of(current) if current is not None else None,
            "world": str(world.get_outermost().get_name()) if world is not None else None,
            "census": _census(), "record_path": record_path(args["sequence"]),
            "record_exists": os.path.isfile(record_path(args["sequence"])),
            "frames": sample_frames(args), "spots": {}, "cvars": _read_cvars()}
    for label, rows in _spots(seq, args["light_labels"]).items():
        spot = {"count": len(rows)}
        if len(rows) == 1:
            binding, comp = rows[0]
            spot["is_spot"] = comp is not None
            if comp is not None:
                pose, src = _binding_pose(binding, binding.get_object_template())
                spot.update({"props": _read_props(comp), "pose": pose, "pose_source": src,
                             "pose_unusable": None if pose else src, "keyed": _keyed_rows(seq, binding),
                             "spawn": _spawn_row(binding), "guid": _guid(binding)})
        live["spots"][label] = spot
    live["candidates"] = _read_candidates(seq, args, set(args["light_labels"]))
    live["cameras"] = _read_cameras(seq, args)
    return live


def _load_sequence(args, run):
    seq = unreal.load_asset(args["sequence"])
    if seq is None or not isinstance(seq, unreal.LevelSequence):
        _stop(run, "SEQUENCE_MISSING|%s" % args["sequence"])
    return seq


def _live_report(args, run):
    seq = _load_sequence(args, run)
    live = _read_live(args, seq)
    return seq, live, build_report(args, live)


def _dry_summary(report):
    plan = report.get("plan") or {}
    parts = []
    for name, v in (plan.get("variants") or {}).items():
        fits = all(f["cell_inside_face"] for f in v["fits_on_curtain"].values())
        parts.append("%s=outer:%.3f,inner:%.3f,fade:%.0f,att:%.0f,cell_fits:%d" % (
            name, v["props"]["outer_cone_angle"], v["props"]["inner_cone_angle"],
            v["props"]["light_function_fade_distance"], v["props"]["attenuation_radius"], int(fits)))
    return "|".join(parts)


def run_dry(args, run):
    _, live, report = _live_report(args, run)
    report["api_table"] = [{"call": c, "tier": t, "cite": s} for c, t, s in API_TABLE]
    report["candidates"] = [{k: v for k, v in c.items() if k != "pose"} for c in live["candidates"]]
    report["cameras"] = [{k: v for k, v in c.items() if k != "pose"} for c in live["cameras"]]
    report["live_flags"] = {k: live[k] for k in ("pie", "sequencer_open", "world", "census", "record_exists")}
    _write_json(dry_path(run), report)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%s" % _census())
    plan = report.get("plan") or {}
    for text in report["refusals"]:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, text))
    for text in report["flags"]:
        unreal.log_warning("%s_FLAG|run=%s|%s" % (MARK, run, text))
    unreal.log("%s_CVARS|run=%s|%s" % (MARK, run, json.dumps(report["cvars"], sort_keys=True)))
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|flags=%d|D=%s|W=%s|keyed=%s|%s|digest=%s|report=%s" % (
        MARK, run, int(report["apply_ready"]), len(report["refusals"]), len(report["flags"]),
        _r(plan.get("d_cm"), 1), _r(plan.get("w_cm"), 1), ",".join(plan.get("keyed_skipped") or []) or "none",
        _dry_summary(report), report["plan_digest"][:16], dry_path(run)))


def _all_props(seq, labels, run):
    out = {}
    for label, rows in _spots(seq, labels).items():
        if len(rows) != 1 or rows[0][1] is None:
            _stop(run, "LIGHT_LABEL_COUNT|%s|%d" % (label, len(rows)))
        out[label] = _read_props(rows[0][1])
    return out


def _write_props(seq, labels, values, run):
    seq.modify()
    for label, rows in _spots(seq, labels).items():
        comp = rows[0][1]
        comp.modify()
        for prop, value in values[label].items():
            comp.set_editor_property(prop, float(value))


def _restore_in_memory(seq, labels, originals, props):
    try:
        _write_props(seq, labels, {l: {p: originals[l][p] for p in props} for l in labels}, "restore")
    except Exception:  # noqa: BLE001 - best effort before the stop; the stop message says Don't-Save restart
        pass


def run_apply(args, run):
    seq, live, report = _live_report(args, run)
    variant = args["variant"]
    refusals = list(report["refusals"])
    dry = _load_json(dry_path(run)) or {}
    if dry.get("plan_digest") != report["plan_digest"] or not dry.get("apply_ready"):
        refusals.append("DRY_NOT_CURRENT|rerun DRY with identical args and this run_id")
    if refusals:
        _stop(run, "REFUSED|" + " || ".join(refusals))
    plan = report["plan"]
    writes = {k: float(v) for k, v in plan["variants"][variant]["write"].items()}
    labels = list(args["light_labels"])
    if not writes:
        _stop(run, "NOTHING_TO_WRITE|every property is keyed")
    before = _all_props(seq, labels, run)
    rp = record_path(args["sequence"])
    backup = os.path.join(_project(), "Backups", "PreGoboSpot-%s" % run)
    os.makedirs(backup, exist_ok=False)
    src = _content_file(args["sequence"])
    dst = os.path.join(backup, os.path.basename(src))
    shutil.copy2(src, dst)
    if os.path.getsize(dst) != os.path.getsize(src):
        _stop(run, "BACKUP_SIZE|%s" % dst)
    record = {"schema_version": 1, "run": run, "sequence": args["sequence"], "labels": labels, "variant": variant,
              "applied": False, "backup": backup, "backup_files": [dst], "before": before, "writes": writes,
              "keyed_skipped": plan["keyed_skipped"], "plan_digest": report["plan_digest"], "plan": plan,
              "guids": {l: live["spots"][l].get("guid") for l in labels},
              "at": datetime.datetime.now().isoformat(timespec="seconds")}
    try:
        _write_json(rp, record, exclusive=True)
    except FileExistsError:
        _stop(run, "RECORD_EXISTS|%s|nothing mutated" % rp)

    # ---- mutation begins only after backup + exclusive record
    _write_props(seq, labels, {l: writes for l in labels}, run)
    after = _all_props(seq, labels, run)
    problems = []
    for label in labels:
        problems.extend(readback_failures(after[label], writes, label))
        untouched = {k: v for k, v in before[label].items() if k not in writes}
        problems.extend(readback_failures(after[label], untouched, label + "(untouched)"))
    problems.extend(exact_census(_census(), args["sequence"]))
    if problems:
        _restore_in_memory(seq, labels, before, list(writes))
        _stop(run, "PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; record %s stays applied=false" % (problems, rp))
    if not unreal.EditorAssetLibrary.save_asset(args["sequence"], only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|%s|restore from %s" % (args["sequence"], backup))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "POSTSAVE_CENSUS|%s" % _census())
    seq2 = _load_sequence(args, run)
    again = _all_props(seq2, labels, run)
    problems = []
    for label in labels:
        problems.extend(readback_failures(again[label], dict(before[label], **writes), label + "(postsave)"))
    if problems:
        _stop(run, "POSTSAVE_READBACK|%s|record applied=false; REVERT will refuse; restore from %s" % (problems, backup))
    record.update({"applied": True, "after": again, "saved_bytes": os.path.getsize(src)})
    _write_json(rp, record)
    unreal.log("%s_APPLY_OK|run=%s|variant=%s|sequence=%s|lights=%d|written=%s|keyed_skipped=%s|outer=%.4f|backup=%s|record=%s" % (
        MARK, run, variant, args["sequence"], len(labels), ",".join(sorted(writes)),
        ",".join(plan["keyed_skipped"]) or "none", writes.get("outer_cone_angle", float("nan")), backup, rp))


def revert_drift(current: dict, record: dict) -> list:
    """Only the properties this tool wrote must still hold the applied values.  Other tools may legitimately change
    the rest in between (animated_gobo APPLY sets light_function_material on the same templates)."""
    out = []
    for label in record["labels"]:
        want = {p: record["after"][label][p] for p in record["writes"]}
        out.extend(readback_failures(current.get(label) or {}, want, label + "(drift)"))
    return out


def run_revert(args, run):
    rp = record_path(args["sequence"])
    record = _load_json(rp)
    if not record:
        _stop(run, "NOTHING_TO_REVERT|%s" % rp)
    if not record.get("applied"):
        _stop(run, "RECORD_NOT_APPLIED|%s|an APPLY stopped mid-way: restore by hand from %s" % (rp, record.get("backup")))
    if record["sequence"] != args["sequence"]:
        _stop(run, "RECORD_SEQUENCE_MISMATCH|%s" % record["sequence"])
    seq = _load_sequence(args, run)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    refusals = []
    if editor.get_game_world() is not None:
        refusals.append("PIE_OR_SIE_ACTIVE")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        refusals.append("SEQUENCER_IS_OPEN")
    if world is None or str(world.get_outermost().get_name()) != args["world"]:
        refusals.append("WRONG_WORLD")
    if _census() != {"content": [], "maps": []}:
        refusals.append("DIRTY_CENSUS|%s" % _census())
    if refusals:
        _stop(run, "REFUSED|" + " || ".join(refusals))
    labels = record["labels"]
    current = _all_props(seq, labels, run)
    drift = revert_drift(current, record)
    if drift:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%s|nothing changed" % drift)
    restore = {l: {p: record["before"][l][p] for p in record["writes"]} for l in labels}
    backup = os.path.join(_project(), "Backups", "PreGoboSpotRevert-%s" % run)
    os.makedirs(backup, exist_ok=False)
    src = _content_file(args["sequence"])
    shutil.copy2(src, os.path.join(backup, os.path.basename(src)))
    _write_props(seq, labels, restore, run)
    problems = []
    now = _all_props(seq, labels, run)
    expect = {l: dict(current[l], **restore[l]) for l in labels}      # restored writes; everything else unchanged
    for label in labels:
        problems.extend(readback_failures(now[label], expect[label], label))
    problems.extend(exact_census(_census(), args["sequence"]))
    if problems:
        _stop(run, "REVERT_PRESAVE|%s|NOTHING SAVED; Don't-Save restart" % problems)
    if not unreal.EditorAssetLibrary.save_asset(args["sequence"], only_if_is_dirty=False):
        _stop(run, "REVERT_SAVE_FAILED|%s" % args["sequence"])
    again = _all_props(_load_sequence(args, run), labels, run)
    problems = []
    for label in labels:
        problems.extend(readback_failures(again[label], expect[label], label + "(postsave)"))
    if problems or _census() != {"content": [], "maps": []}:
        _stop(run, "REVERT_POSTSAVE|%s|census=%s" % (problems, _census()))
    archived = rp + ".reverted-" + run
    os.rename(rp, archived)
    unreal.log("%s_REVERT_OK|run=%s|apply_run=%s|sequence=%s|restored=%s|backup=%s|record=%s" % (
        MARK, run, record["run"], args["sequence"], ",".join(sorted(record["writes"])), backup, archived))


def main(raw=None):
    if raw is None:
        raw = globals().get("GOBO_SPOT_ARGS")
    if raw is None:
        raw = _load_json(os.path.join(_here(), ARGS_NAME)) or {}
    raw = dict(raw)
    run = str(raw.get("run_id") or "UNSET")
    try:
        args = normalized_args(raw)
        want = confirm_text(args["mode"], args["variant"])
        if str(args.get("confirm") or "") != want:
            _stop(run, "CONFIRM_MISMATCH|want %r|got %r" % (want, args.get("confirm")))
        if args["mode"] == "DRY":
            run_dry(args, run)
        elif args["mode"] == "APPLY":
            run_apply(args, run)
        else:
            run_revert(args, run)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|%s" % exc)


if unreal is not None:
    main()
