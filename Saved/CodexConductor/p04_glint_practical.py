"""P04 glint practical: DRY / ADD / REMOVE. ONE bulb LIGHT + its bulb-body PROP on the P04 cue that owns Wing 009.

Gary 7 Oct ("Place a practical near it?"): a real show light that makes a specular glint on the v4-paper gallery
wing W010. Target point: passage-local (4290, 383, 200) cm. P04 passage-local == world (x, y - 240000, z)
[measured: gloss4_glint_pie_spawn.py:4, stills manifest PSTILLS-P04-20261007-000620-gloss4_base], so the target
WORLD point is (4290, 240383, 200).

What it writes. Two NEW attachments appended to the cue's WingPair attachment array:
  "P04 GLINT PRACTICAL W010"       a clone of an existing P04 practical LIGHT row of the same cue (default: the
                                   one whose label matches ^P04 SCORE B\\d{2} \\S+ PRACTICAL_L$, the lit "bare bulb
                                   on cord" of the 5 Oct scores, lighting_scores_record_P04.json plan.targets
                                   ordinal 9) with ONLY label, enabled, relative location + rotation, intensity,
                                   intensity units, attenuation, source radius, cast shadows and colour overridden;
  "P04 GLINT PRACTICAL W010_BODY"  a clone of that practical's *_BODY PROP row, ONLY label, enabled and relative
                                   location overridden (and Body.LightAttachmentGuid re-pointed at the new light
                                   when the source body was paired to the source light or follows a light).
Every other row of every cue is unchanged, bit for bit (scope check, in memory, after save and on read-back).

Relative position. The cue's attachments are in its STATION frame (X along route, Y across, Z up;
InfinityStageStructureActor.h:31-36, StationWorld = Route->GetTransformAtDistanceAlongSpline, .cpp:261-265, as
cited by rig_lamp_drop.py:19-23). The tool reads the LIVE station frame of the cue (GatherStations, the
rig_lamp_drop.py:790-803 helper), composes the pair occurrence offset (rig_lamp_drop.py:284) and inverts it to get
the relative location. It also computes the NOMINAL relative (4290 - (250 + 500*8), 383, 200) = (40, 383, 200)
(Wing N station x = 250 + 500(N-1), W&T measured station_frames) and REFUSES if the two differ by more than 5 cm.

GUID minting. Attachment GUIDs are read-only from Python; the only minting route is
UInfinityStageShowAsset::ReplicateLightAttachments (InfinityStageShowAsset.cpp:572-649: a target ordinal beyond
the target's existing light count gets FGuid::NewGuid(), :627-630). Reused EXACTLY as the live-proven scores tool
does it (lighting_scores_apply.py:2738-2814 _mutate_apply): pad a SCRATCH WingPair cue (nearest outside the
target) with blank lights (lighting_looks_apply.py:1481 _make_blank_light), replicate scratch -> target, restore
the scratch cue exactly, take the two fresh vessels at light ordinals k, k+1 (k = the target's own light count),
overwrite them (cf. _overwrite_vessel lighting_looks_apply.py:1567-1575, which checks the GUID survives), and set
the target array to its ORIGINAL attachments + the two vessels. Replicate removes the target's lights and appends
copies (.cpp:619-645), so the original array is restored from the pre-write snapshot, never from the replicate.

Proof tiers (AGENTS.md), per claim:
* declaration-proven: FInfinityCueAttachment fields are exactly AttachmentGuid, Label, Kind, bEnabled, ActorClass,
  Mesh, Anchor, RelativeTransform, Lighting, Effect, TriggerDistanceCm, Body, Mover (InfinityStageTypes.h:429-492),
  so CLONE_FIELDS below copies every field but the GUID; ReplicateLightAttachments semantics (.cpp:572-649);
  _set_pair_attachments writes with show.modify() (lighting_looks_apply.py:1292-1300); _save_narrow saves only Show
  + level (lighting_looks_apply.py:1657-1667); _backup (lighting_looks_apply.py:1616-1632); _materialize_passage
  (lighting_scores_apply.py:2879-2896); Body/Mover read helpers (lighting_scores_apply.py:879-899).
* measured (offline, 7 Oct, lighting_scores_record_P04.json): "P04 Wing 009" is bay ordinal 9, show_index 107,
  cue guid D84BDBAEDF4EE4A952894D82ECD2841F in passage 0067B5F57142956FB5B80EA31B1210B5 ("Passage 4"); its 5 Oct
  practicals are "P04 SCORE B09 MOODY PRACTICAL_L" (POINT, 1200 LUMENS, 2700 K, MI_LF_Flicker_Slow, strike-on-
  approach 650 cm, unstruck 0) + _BODY (SM_Lamp_Ceiling 0.5), and PRACTICAL_R (intensity 0, dead cage) + _BODY.
* inferred (the first live DRY must confirm; listed in the DRY report "inferred"): those rows still exist live with
  that shape; the live station frame gives (40, 383, 200) within 5 cm (i.e. the editor-world P04 frame equals the
  PIE-measured one); unreal.Text label / LinearColor colour / enum units round-trip through set_editor_property;
  the cloned light-function flicker and strike-on-approach keying (OFF until the camera is within the cloned strike
  distance) are acceptable for a glint, or Gary picks another source practical (args source_light_regex).

Args (p04_glint_practical_args.json via p04_glint_practical_run.py):
  {"mode": "DRY"|"ADD"|"REMOVE", "confirm": "<MODE> P04GLINT", "intensity_cd": 30000, ..., "ack_records": [...]}
Markers: P04GLINT_DRY_OK / P04GLINT_ADD_OK / P04GLINT_REMOVE_OK |run=<id>|...; any stop P04GLINT_STOPPED|run=<id>|...
"""
from __future__ import annotations

import ast
import copy
import datetime
import hashlib
import json
import math
import os
import re
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
SCORES_TOOL_PATH = os.path.join(HERE, "lighting_scores_apply.py")
SCORES_RECORD_P04 = os.path.join(HERE, "lighting_scores_record_P04.json")
RECORD_PATH = os.path.join(HERE, "p04_glint_practical_record.json")
VALID_MODES = ("DRY", "ADD", "REMOVE")
CONFIRM_TOKEN = "P04GLINT"
MARK = "P04GLINT"
PASSAGE_KEY = "P04"
PASSAGE_LABEL = "Passage 4"                         # lighting_scores_record_P04.json plan.passage_label (measured)
PASSAGE_ACTOR_PREFIX = "Passage 04"                 # rig_lamp_drop.py:80 PASSAGE_ACTOR_PREFIX_FMT % 4
STRUCTURE_LABEL = "Infinity Stage - Structure 04"   # rig_lamp_drop.py:79 STRUCTURE_LABEL_FMT % 4
LIGHT_LABEL = "P04 GLINT PRACTICAL W010"
BODY_LABEL = "P04 GLINT PRACTICAL W010_BODY"
ZERO_GUID = "0" * 32
CLONE_FIELDS = ("label", "kind", "enabled", "actor_class", "mesh", "anchor", "relative_transform",
                "lighting", "effect", "trigger_distance_cm", "body", "mover")   # InfinityStageTypes.h:429-492
EFFECT_GUID_FIELDS = ("linked_light_attachment_guid", "replicated_from_attachment_guid")
LOC_TOL_CM = 1.0e-6
ROT_TOL = 1.0e-6                                     # unreal.Quat is float32 (p01_rig_pattern.py:93)
REL_TOL = 1.0e-6                                     # float32 struct floats (colour 0.85 -> 0.8500000238)
DEFAULTS = {
    "cue_label": "P04 Wing 009",
    "expected_cue_guid": None,                       # None = pin to lighting_scores_record_P04.json when present
    "target_local_cm": [4290.0, 383.0, 200.0],
    "passage_world_offset_cm": [0.0, 240000.0, 0.0],  # world = local + offset (measured, see docstring)
    "wing_number": 9,
    "station_x0_cm": 250.0,
    "station_pitch_cm": 500.0,
    "max_frame_disagreement_cm": 5.0,
    "source_light_regex": r"^P04 SCORE B\d{2} \S+ PRACTICAL_L$",
    "intensity_cd": 30000.0,
    "intensity_units": "CANDELAS",
    "attenuation_cm": 1500.0,
    "source_radius_cm": 3.0,
    "cast_shadows": False,
    "steady": False,                  # Gary 7 Oct "Dim, steady, always on": no light function, no strike-on-approach
    "color_rgb": [1.0, 0.85, 0.65],
    "rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
    "avoid_scratch_cues": [],
    "ack_records": [],
    "allow_dirty": [],
}


class P04GlintError(RuntimeError):
    """Deliberate fail-closed stop."""


def require(condition, message):
    if not condition:
        raise P04GlintError(str(message))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _enum_name(value):
    text = str(value)
    match = re.search(r"\.([A-Za-z0-9_]+)\s*:", text)
    return (match.group(1) if match else text).upper()


def report_path(mode, run, folder=None):
    return os.path.join(folder or HERE, "p04_glint_practical_report_%s_%s.json" % (mode, run))


def backup_prefix(mode):
    return "PreP04Glint%s-" % ("Add" if mode == "ADD" else "Remove")


# --------------------------------------------------------------------------
# Transform maths (FTransform semantics, positive scale) — rig_lamp_drop.py:143-201.
# --------------------------------------------------------------------------
def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _dist(a, b):
    d = _sub(a, b)
    return math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])


def quat_rotate(q, v):
    x, y, z, w = (float(c) for c in q)
    tx = 2.0 * (y * v[2] - z * v[1])
    ty = 2.0 * (z * v[0] - x * v[2])
    tz = 2.0 * (x * v[1] - y * v[0])
    return [v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx)]


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


def compose(child, parent):
    """FTransform child * parent (child expressed in parent's frame)."""
    scaled = [child["location"][i] * parent["scale"][i] for i in range(3)]
    return {"location": _add(quat_rotate(parent["rotation_xyzw"], scaled), parent["location"]),
            "rotation_xyzw": quat_mul(parent["rotation_xyzw"], child["rotation_xyzw"]),
            "scale": [child["scale"][i] * parent["scale"][i] for i in range(3)]}


def inverse_point(frame, world_point):
    """The point expressed in frame (inverse of compose for a location)."""
    q = [float(c) for c in frame["rotation_xyzw"]]
    norm = math.sqrt(sum(c * c for c in q))
    require(norm > 1.0e-9, "FRAME_QUAT_ZERO")
    conj = [-q[0] / norm, -q[1] / norm, -q[2] / norm, q[3] / norm]
    local = quat_rotate(conj, _sub(world_point, frame["location"]))
    require(all(abs(float(s)) > 1.0e-9 for s in frame["scale"]), "FRAME_SCALE_ZERO")
    return [local[i] / float(frame["scale"][i]) for i in range(3)]


def canonical_quat(q):
    """_infinity_attachment_state.py:76-81: first non-zero component positive."""
    out = [float(c) for c in q]
    for c in out:
        if c == 0.0:
            continue
        if c < 0.0:
            out = [-v for v in out]
        break
    return out


def quat_close(a, b, tol=ROT_TOL):
    d1 = max(abs(float(x) - float(y)) for x, y in zip(a, b))
    d2 = max(abs(float(x) + float(y)) for x, y in zip(a, b))
    return min(d1, d2) <= tol


# --------------------------------------------------------------------------
# Args.
# --------------------------------------------------------------------------
def _finite(value, label):
    require(not isinstance(value, bool), "%s_NOT_NUMBER|%r" % (label, value))
    number = float(value)
    require(math.isfinite(number), "%s_NOT_FINITE|%r" % (label, value))
    return number


def _vector(value, n, label):
    require(isinstance(value, (list, tuple)) and len(value) == n, "%s_SHAPE|%r" % (label, value))
    return [_finite(v, label) for v in value]


def check_args(args):
    """Normalise the args json; ADD/REMOVE need confirm '<MODE> P04GLINT'."""
    raw = dict(args or {})
    unknown = sorted(set(raw) - set(DEFAULTS) - {"mode", "confirm"})
    require(not unknown, "ARGS_UNKNOWN|%s" % unknown)
    mode = str(raw.get("mode", "DRY")).upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    if mode != "DRY":
        require(raw.get("confirm") == "%s %s" % (mode, CONFIRM_TOKEN),
                "CONFIRM_MISSING|mode=%s|need='%s %s'" % (mode, mode, CONFIRM_TOKEN))
    out = copy.deepcopy(DEFAULTS)
    out.update({k: copy.deepcopy(v) for k, v in raw.items() if k in DEFAULTS})
    out["mode"], out["confirm"] = mode, raw.get("confirm")
    out["target_local_cm"] = _vector(out["target_local_cm"], 3, "TARGET_LOCAL")
    out["passage_world_offset_cm"] = _vector(out["passage_world_offset_cm"], 3, "PASSAGE_OFFSET")
    out["color_rgb"] = _vector(out["color_rgb"], 3, "COLOR")
    require(all(0.0 <= c <= 1.0 for c in out["color_rgb"]), "COLOR_RANGE|%r" % out["color_rgb"])
    rot = _vector(out["rotation_xyzw"], 4, "ROTATION")
    norm = math.sqrt(sum(c * c for c in rot))
    require(abs(norm - 1.0) <= 1.0e-6, "ROTATION_NOT_UNIT|%r" % rot)
    out["rotation_xyzw"] = canonical_quat(rot)
    for key, low, high in (("intensity_cd", 0.0, 1.0e6), ("attenuation_cm", 1.0, 1.0e5),
                           ("source_radius_cm", 0.0, 1.0e3), ("max_frame_disagreement_cm", 0.0, 50.0),
                           ("station_x0_cm", -1.0e6, 1.0e6), ("station_pitch_cm", 1.0, 1.0e5)):
        out[key] = _finite(out[key], key.upper())
        require(low <= out[key] <= high, "%s_RANGE|%r" % (key.upper(), out[key]))
    require(isinstance(out["wing_number"], int) and not isinstance(out["wing_number"], bool)
            and out["wing_number"] >= 1, "WING_NUMBER_INVALID|%r" % (out["wing_number"],))
    require(isinstance(out["cast_shadows"], bool), "CAST_SHADOWS_NOT_BOOL")
    require(isinstance(out["steady"], bool), "STEADY_NOT_BOOL")
    require(out["intensity_units"] in ("CANDELAS", "LUMENS", "UNITLESS", "EV"), "UNITS_INVALID")
    require(isinstance(out["cue_label"], str) and out["cue_label"], "CUE_LABEL_INVALID")
    re.compile(out["source_light_regex"])
    require(out["expected_cue_guid"] is None or (isinstance(out["expected_cue_guid"], str)
                                                 and len(out["expected_cue_guid"]) == 32), "EXPECTED_CUE_GUID_INVALID")
    for key in ("avoid_scratch_cues", "ack_records", "allow_dirty"):
        require(isinstance(out[key], list) and all(isinstance(v, str) for v in out[key]), key.upper() + "_INVALID")
    return out


# --------------------------------------------------------------------------
# Plan (pure).
# --------------------------------------------------------------------------
def find_target_cue(plain, opts, pin=None):
    cues = plain["cues"]
    guids = [c["guid"] for c in cues]
    require(len(guids) == len(set(guids)), "DUPLICATE_CUE_GUID")
    bays = set(plain["bay_guids"])
    require(bays, "NO_P04_BAYS")
    hits = [c for c in cues if c["guid"] in bays and c["label"] == opts["cue_label"]]
    require(len(hits) == 1, "TARGET_CUE_COUNT|label=%s|count=%d" % (opts["cue_label"], len(hits)))
    cue = hits[0]
    require(_enum_name(cue.get("type", "WING_PAIR")) in ("WING_PAIR", "WINGPAIR"), "TARGET_NOT_WING_PAIR")
    expected = opts.get("expected_cue_guid") or (pin or {}).get("cue_guid")
    if expected:
        require(cue["guid"] == expected, "TARGET_CUE_GUID_DRIFT|live=%s|pin=%s" % (cue["guid"], expected))
    if (pin or {}).get("passage_guid") and plain.get("passage_guid"):
        require(plain["passage_guid"] == pin["passage_guid"],
                "PASSAGE_GUID_DRIFT|live=%s|pin=%s" % (plain["passage_guid"], pin["passage_guid"]))
    return cue


def find_source_pair(cue, opts):
    """(light_index, light_row, body_index, body_row) of the cloned practical; every refusal is explicit."""
    pattern = re.compile(opts["source_light_regex"])
    lights = [(i, r) for i, r in enumerate(cue["attachments"]) if pattern.match(str(r["label"]))]
    require(len(lights) == 1, "SOURCE_LIGHT_COUNT|regex=%s|count=%d|labels=%s"
            % (opts["source_light_regex"], len(lights), [r["label"] for unused, r in lights]))
    li, light = lights[0]
    bodies = [(i, r) for i, r in enumerate(cue["attachments"]) if r["label"] == light["label"] + "_BODY"]
    require(len(bodies) == 1, "SOURCE_BODY_COUNT|label=%s_BODY|count=%d" % (light["label"], len(bodies)))
    bi, body = bodies[0]
    require(_enum_name(light["kind"]) == "LIGHT", "SOURCE_LIGHT_KIND|" + str(light["kind"]))
    require(_enum_name(body["kind"]) == "PROP", "SOURCE_BODY_KIND|" + str(body["kind"]))
    require(_enum_name(light["lighting"]["type"]) == "POINT", "SOURCE_LIGHT_NOT_POINT|" + str(light["lighting"]["type"]))
    for row in (light, body):
        require(_enum_name(row["anchor"]) == "STATION", "SOURCE_ANCHOR_NOT_STATION|" + row["label"])
        require(bool(row["enabled"]), "SOURCE_DISABLED|" + row["label"])
        for name in EFFECT_GUID_FIELDS:
            require(str(row["effect"].get(name, ZERO_GUID)) == ZERO_GUID,
                    "SOURCE_EFFECT_GUID_LINK|%s|%s" % (row["label"], name))
    require(body.get("mesh"), "SOURCE_BODY_NO_MESH|" + body["label"])
    return li, light, bi, body


def body_link_mode(light, body):
    """REMAP: the clone body follows the NEW light. KEEP: inert zero link kept. Foreign links refuse."""
    ext = body.get("ext") or {}
    link = (ext.get("body") or {}).get("light_attachment_guid", ZERO_GUID)
    follow = bool((ext.get("body") or {}).get("follow_light", False))
    if link == light["guid"]:
        return "REMAP"
    require(link == ZERO_GUID, "SOURCE_BODY_LINKED_ELSEWHERE|body=%s|link=%s" % (body["label"], link))
    return "REMAP" if follow else "KEEP"


def station_relative(plain, cue, opts):
    stations = [s for s in plain["stations"] if s["cue_guid"] == cue["guid"]]
    require(len(stations) == 1, "STATION_COUNT|cue=%s|count=%d" % (cue["guid"], len(stations)))
    station = stations[0]
    pair_world = compose(cue["occurrence_offset"], station["world"])
    world = _add(opts["target_local_cm"], opts["passage_world_offset_cm"])
    computed = inverse_point(pair_world, world)
    station_x = opts["station_x0_cm"] + opts["station_pitch_cm"] * (opts["wing_number"] - 1)
    nominal = [opts["target_local_cm"][0] - station_x, opts["target_local_cm"][1], opts["target_local_cm"][2]]
    disagreement = _dist(computed, nominal)
    require(disagreement <= opts["max_frame_disagreement_cm"],
            "FRAME_DISAGREES|computed=%s|nominal=%s|dist=%.3f|max=%.1f"
            % ([round(v, 3) for v in computed], nominal, disagreement, opts["max_frame_disagreement_cm"]))
    return {"station_index": plain["stations"].index(station), "distance_cm": station.get("distance_cm"),
            "station_world": station["world"], "pair_world": pair_world, "target_world_cm": world,
            "relative_computed_cm": computed, "relative_nominal_cm": nominal,
            "disagreement_cm": disagreement, "station_x_nominal_cm": station_x}


def choose_scratch(plain, target, avoid=()):
    """Nearest WingPair cue (by show index) that is not the target and not avoided (lighting_scores_apply.py:2721)."""
    skip = set(avoid) | {target["guid"]}
    candidates = [(abs(c["show_index"] - target["show_index"]), c["show_index"], c) for c in plain["cues"]
                  if c["guid"] not in skip and _enum_name(c.get("type", "")) in ("WING_PAIR", "WINGPAIR")]
    require(candidates, "SCRATCH_CUE_MISSING")
    candidates.sort(key=lambda t: (t[0], t[1]))
    return candidates[0][2]


def light_count(rows):
    return sum(1 for r in rows if _enum_name(r["kind"]) == "LIGHT")


def padding_needed(target_lights, scratch_lights):
    """Blank lights to add to the scratch so the target gets ordinals k and k+1 (two fresh GUIDs)."""
    return max(0, target_lights + 2 - scratch_lights)


def planned_rows(light, body, rel, opts, link_mode):
    """The two new rows, guid placeholders "<MINT:LIGHT>" / "<MINT:BODY>"."""
    new_light = copy.deepcopy(light)
    new_light.update({"guid": "<MINT:LIGHT>", "label": LIGHT_LABEL, "enabled": True})
    new_light["relative_transform"]["location"] = list(rel)
    new_light["relative_transform"]["rotation_xyzw"] = list(opts["rotation_xyzw"])
    lighting = new_light["lighting"]
    lighting["intensity"] = float(opts["intensity_cd"])
    lighting["intensity_units"] = opts["intensity_units"]
    lighting["attenuation_radius_cm"] = float(opts["attenuation_cm"])
    lighting["source_radius_cm"] = float(opts["source_radius_cm"])
    lighting["cast_shadows"] = bool(opts["cast_shadows"])
    lighting["color"] = [float(c) for c in opts["color_rgb"]] + [1.0]
    if opts.get("steady"):
        lighting["light_function_material"] = None
        lighting.setdefault("drama", {})["strike_on_approach"] = False
    new_body = copy.deepcopy(body)
    new_body.update({"guid": "<MINT:BODY>", "label": BODY_LABEL, "enabled": True})
    new_body["relative_transform"]["location"] = list(rel)
    if link_mode == "REMAP":
        new_body.setdefault("ext", {}).setdefault("body", {})["light_attachment_guid"] = "<MINT:LIGHT>"
    return new_light, new_body


LIGHT_OVERRIDE_PATHS = (("label",), ("enabled",), ("relative_transform", "location"),
                        ("relative_transform", "rotation_xyzw"), ("lighting", "intensity"),
                        ("lighting", "intensity_units"), ("lighting", "attenuation_radius_cm"),
                        ("lighting", "source_radius_cm"), ("lighting", "cast_shadows"), ("lighting", "color"),
                        ("lighting", "light_function_material"), ("lighting", "drama", "strike_on_approach"))
BODY_OVERRIDE_PATHS = (("label",), ("enabled",), ("relative_transform", "location"),
                       ("ext", "body", "light_attachment_guid"))


def build_plan(plain, opts, pin=None):
    cue = find_target_cue(plain, opts, pin)
    for c in plain["cues"]:
        for row in c["attachments"]:
            require(row["label"] not in (LIGHT_LABEL, BODY_LABEL),
                    "LABEL_ALREADY_EXISTS|cue=%s|label=%s|guid=%s" % (c["label"], row["label"], row["guid"]))
    li, light, bi, body = find_source_pair(cue, opts)
    rel = station_relative(plain, cue, opts)
    link = body_link_mode(light, body)
    new_light, new_body = planned_rows(light, body, rel["relative_computed_cm"], opts, link)
    scratch = choose_scratch(plain, cue, opts.get("avoid_scratch_cues") or ())
    k, m = light_count(cue["attachments"]), light_count(scratch["attachments"])
    lighting = light["lighting"]
    warnings = []
    if bool(lighting.get("use_temperature")):
        warnings.append("USE_TEMPERATURE_CLONED|kelvin=%s|colour multiplies the temperature tint"
                        % lighting.get("temperature_kelvin"))
    if lighting.get("light_function_material"):
        warnings.append("LIGHT_FUNCTION_CLONED|" + str(lighting["light_function_material"]))
    drama = lighting.get("drama") or {}
    if bool(drama.get("strike_on_approach")):
        warnings.append("STRIKE_ON_APPROACH_CLONED|strike_cm=%s|ramp_cm=%s|unstruck_scale=%s|after_pass=%s"
                        % (drama.get("strike_distance_cm"), drama.get("strike_ramp_cm"),
                           drama.get("unstruck_intensity_scale"), drama.get("after_pass")))
    if _enum_name(lighting.get("intensity_units")) != opts["intensity_units"]:
        warnings.append("UNITS_OVERRIDDEN|%s->%s" % (_enum_name(lighting.get("intensity_units")), opts["intensity_units"]))
    if ((light.get("ext") or {}).get("mover") or {}).get("enabled"):
        warnings.append("MOVER_CLONED_ENABLED")
    return {
        "passage": PASSAGE_KEY, "passage_guid": plain.get("passage_guid"),
        "cue_guid": cue["guid"], "cue_label": cue["label"], "show_index": cue["show_index"],
        "before_count": len(cue["attachments"]), "light_count": k,
        "source": {"light_guid": light["guid"], "light_label": light["label"], "light_index": li,
                   "body_guid": body["guid"], "body_label": body["label"], "body_index": bi,
                   "light_summary": {"type": _enum_name(lighting.get("type")),
                                     "intensity": lighting.get("intensity"),
                                     "intensity_units": _enum_name(lighting.get("intensity_units")),
                                     "use_temperature": lighting.get("use_temperature"),
                                     "temperature_kelvin": lighting.get("temperature_kelvin"),
                                     "light_function_material": lighting.get("light_function_material"),
                                     "drama": drama, "location": light["relative_transform"]["location"]},
                   "body_mesh": body.get("mesh"), "body_scale": body["relative_transform"].get("scale"),
                   "body_link_mode": link},
        "frame": rel, "planned_light": new_light, "planned_body": new_body,
        "scratch": {"cue_guid": scratch["guid"], "cue_label": scratch["label"], "show_index": scratch["show_index"],
                    "light_count": m, "padding": padding_needed(k, m)},
        "overrides": {k2: opts[k2] for k2 in ("intensity_cd", "intensity_units", "attenuation_cm", "source_radius_cm",
                                              "cast_shadows", "color_rgb", "rotation_xyzw", "steady")},
        "warnings": warnings,
        "inferred": ["source rows live shape (DRY reads them)", "editor-world P04 frame == PIE-measured frame "
                     "(FRAME_DISAGREES guard)", "Text/LinearColor/enum setters round-trip (ADD read-back)",
                     "cloned flicker/strike keying acceptable for the glint (Gary)"],
    }


def realize(plan, minted):
    """Planned rows with the minted GUIDs substituted."""
    light_guid, body_guid = minted
    rows = []
    for planned in (plan["planned_light"], plan["planned_body"]):
        text = _canonical(planned).replace("<MINT:LIGHT>", light_guid).replace("<MINT:BODY>", body_guid)
        rows.append(json.loads(text))
    return rows


# --------------------------------------------------------------------------
# GUID freshness, scope guards, offline mutation model, REMOVE model.
# --------------------------------------------------------------------------
def _valid_guid(text):
    return isinstance(text, str) and re.fullmatch(r"[0-9A-F]{32}", text) is not None and text != ZERO_GUID


def check_minted(minted, preexisting):
    require(len(minted) == 2, "MINTED_COUNT|%d" % len(minted))
    require(all(_valid_guid(g) for g in minted), "MINTED_GUID_INVALID|%s" % minted)
    require(minted[0] != minted[1], "MINTED_GUID_DUPLICATE|" + minted[0])
    clash = [g for g in minted if g in set(preexisting)]
    require(not clash, "MINTED_GUID_NOT_FRESH|%s" % clash)


def _pop_path(row, path):
    node = row
    for key in path[:-1]:
        node = node.get(key) if isinstance(node, dict) else None
        if node is None:
            return None, False
    if not isinstance(node, dict) or path[-1] not in node:
        return None, False
    return node.pop(path[-1]), True


def _value_close(path, want, got):
    if path[-1] == "rotation_xyzw":
        return isinstance(got, list) and len(got) == 4 and len(want) == 4 and quat_close(want, got)
    if path[-1] == "intensity_units":
        return _enum_name(want) == _enum_name(got)
    if isinstance(want, bool) or isinstance(got, bool) or isinstance(want, str) or want is None:
        return want == got
    if isinstance(want, (list, tuple)):
        return (isinstance(got, (list, tuple)) and len(got) == len(want)
                and all(_value_close(path, a, b) for a, b in zip(want, got)))
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        tol = LOC_TOL_CM if path[-1] == "location" else REL_TOL * max(1.0, abs(float(want)))
        return abs(float(want) - float(got)) <= tol
    return want == got


def planned_differences(tool, planned, got, paths):
    """Override paths compared with float32 tolerance (enum by name); every other field exactly."""
    a, b = copy.deepcopy(planned), copy.deepcopy(got)
    out = []
    for path in paths:
        want, has_want = _pop_path(a, path)
        have, has_have = _pop_path(b, path)
        if has_want != has_have or (has_want and not _value_close(path, want, have)):
            out.append({"path": ".".join(path), "before": want, "after": have})
    return out + tool._state_differences(a, b)


def target_problems(tool, before_rows, got_rows, plan, minted):
    """[] iff got == before + exactly the two planned rows (with minted GUIDs) appended."""
    n = len(before_rows)
    if len(got_rows) != n + 2:
        return [{"problem": "ROW_COUNT", "want": n + 2, "got": len(got_rows)}]
    problems = []
    for index, (want, got) in enumerate(zip(before_rows, got_rows[:n])):
        diffs = tool._state_differences(want, got)
        if diffs:
            problems.append({"index": index, "label": want.get("label"), "differences": diffs})
    light, body = realize(plan, minted)
    for want, got, paths in ((light, got_rows[n], LIGHT_OVERRIDE_PATHS), (body, got_rows[n + 1], BODY_OVERRIDE_PATHS)):
        diffs = planned_differences(tool, want, got, paths)
        if diffs:
            problems.append({"index": "new", "label": want["label"], "differences": diffs})
    return problems


def scope_differences(tool, base_all, live_all, plan, minted, side):
    """side 'after': target cue == before + two planned rows, every other cue bit-identical.
    side 'before': every cue (target included) bit-identical to base_all."""
    require(side in ("before", "after"), "SIDE_INVALID|" + str(side))
    if set(base_all) != set(live_all):
        return [{"cue": "*", "problem": "CUE_SET_CHANGED"}]
    problems = []
    for cue_guid in sorted(base_all):
        if side == "after" and cue_guid == plan["cue_guid"]:
            for p in target_problems(tool, base_all[cue_guid], live_all[cue_guid], plan, minted):
                problems.append(dict(p, cue=cue_guid))
            continue
        diffs = tool._state_differences(base_all[cue_guid], live_all[cue_guid])
        if diffs:
            problems.append({"cue": cue_guid, "differences": diffs[:20]})
    return problems


def check_scope(tool, base_all, live_all, plan, minted, side):
    problems = scope_differences(tool, base_all, live_all, plan, minted, side)
    require(not problems, "SCOPE_CHANGED|side=%s|count=%d|%s" % (side, len(problems), _canonical(problems)[:3000]))


def add_plain(all_rows, plan, minted):
    """Offline model of ADD."""
    result = copy.deepcopy(all_rows)
    result[plan["cue_guid"]] = copy.deepcopy(all_rows[plan["cue_guid"]]) + realize(plan, minted)
    return result


def check_record(record):
    require(record.get("passage") == PASSAGE_KEY, "RECORD_PASSAGE_MISMATCH|%s" % record.get("passage"))
    require(record.get("status") == "saved_readback_verified", "REMOVE_RECORD_STATUS|" + str(record.get("status")))
    minted = record.get("minted_guids") or []
    require(len(minted) == 2 and all(_valid_guid(g) for g in minted), "REMOVE_RECORD_GUIDS|%s" % minted)
    for key in ("cue_guid", "before_cue_rows", "after_cue_rows", "plan"):
        require(key in record, "REMOVE_RECORD_FIELD_MISSING|" + key)


def remove_drifts(tool, all_rows, record):
    """Every field of the cue that differs from the recorded after rows (the two GLINT rows included)."""
    live = all_rows.get(record["cue_guid"])
    if live is None:
        return [{"problem": "CUE_GONE", "cue": record["cue_guid"]}]
    return tool._state_differences(record["after_cue_rows"], live)


def remove_plain(tool, all_rows, record):
    """Offline model of REMOVE: drop exactly the two recorded GUIDs; result must equal the recorded before rows."""
    drifts = remove_drifts(tool, all_rows, record)
    require(not drifts, "REMOVE_DRIFT|count=%d|%s" % (len(drifts), _canonical(drifts)[:3000]))
    result = copy.deepcopy(all_rows)
    live = all_rows[record["cue_guid"]]
    minted = set(record["minted_guids"])
    kept = [row for row in live if row["guid"] not in minted]
    require(len(kept) == len(live) - 2, "REMOVE_GUID_COUNT|live=%d|kept=%d" % (len(live), len(kept)))
    diffs = tool._state_differences(record["before_cue_rows"], kept)
    require(not diffs, "REMOVE_NOT_EXACT|%s" % _canonical(diffs)[:3000])
    result[record["cue_guid"]] = kept
    return result


# --------------------------------------------------------------------------
# Context gate (pure), p01_rig_pattern.py:593.
# --------------------------------------------------------------------------
def check_context(ctx, mode, allow_dirty=(), show_path=None, world_path=None):
    require(ctx.get("project_ok", True), "WRONG_PROJECT")
    require(ctx.get("world_ok", True), "WRONG_WORLD|" + str(ctx.get("world")))
    census = ctx.get("census") or {}
    if mode == "DRY":
        return
    require(not ctx.get("pie"), "PIE_OR_SIE_ACTIVE")
    require(not ctx.get("sequencer_open"), "SEQUENCER_IS_OPEN")
    require(not ctx.get("zz_actors"), "STRAY_ZZ_ACTORS|" + ",".join(ctx.get("zz_actors") or []))
    allowed = set(allow_dirty or [])
    if show_path or world_path:
        require(allowed <= {show_path, world_path}, "ALLOW_DIRTY_OUT_OF_SCOPE|%s" % sorted(allowed))
    dirty = set(census.get("content") or []) | set(census.get("maps") or [])
    require(dirty <= allowed, "DIRTY_BEFORE|census=" + _canonical(census))


def check_add_gate(unacked, record_file=RECORD_PATH):
    require(not os.path.exists(record_file), "ACTIVE_RECORD_EXISTS|" + record_file)
    require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))


def load_pin(path=SCORES_RECORD_P04, cue_label=DEFAULTS["cue_label"]):
    """{cue_guid, passage_guid} for the cue from the P04 scores record (a drift pin), or {} if absent."""
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    plan = record.get("plan") or {}
    hits = [t for t in plan.get("targets", []) if t.get("cue_label") == cue_label]
    if len(hits) != 1:
        return {"passage_guid": plan.get("passage_guid")}
    return {"cue_guid": hits[0]["cue_guid"], "passage_guid": plan.get("passage_guid")}


# --------------------------------------------------------------------------
# Module loading — p01_rig_pattern.py:628-697 (lighting_scores_apply.py, then its load_p04_tool()).
# --------------------------------------------------------------------------
_SAFE_CALLS = {"os.path.join", "os.path.dirname", "os.path.abspath", "os.path.normcase",
               "os.path.normpath", "re.compile", "tuple", "frozenset", "set", "dict", "list",
               "_load_attachment_state"}


def _dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _dotted(node.value)
        return None if inner is None else inner + "." + node.attr
    return None


def _is_main_guard(node):
    return (isinstance(node, ast.If) and not node.orelse and len(node.body) == 1
            and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "unreal" and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value is None
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Call)
            and _dotted(node.body[0].value.func) == "main"
            and not node.body[0].value.args and not node.body[0].value.keywords)


def _top_level_ok(node, index):
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
        return True
    if isinstance(node, ast.Expr):
        return index == 0 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return node.value is None or all(_dotted(c.func) in _SAFE_CALLS
                                         for c in ast.walk(node.value) if isinstance(c, ast.Call))
    if isinstance(node, ast.Try):
        inner = list(node.body) + [s for h in node.handlers for s in h.body] + list(node.orelse) + list(node.finalbody)
        return all(isinstance(s, (ast.Import, ast.ImportFrom))
                   or (isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant)) for s in inner)
    return False


def load_without_main(path, module_name):
    with open(path, "rb") as handle:
        raw = handle.read()
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    require(tree.body and _is_main_guard(tree.body[-1])
            and sum(1 for n in tree.body if _is_main_guard(n)) == 1, "MAIN_GUARD_SHAPE|" + path)
    for index, node in enumerate(tree.body[:-1]):
        require(_top_level_ok(node, index), "TOP_LEVEL_SIDE_EFFECT|%s|line=%d" % (path, getattr(node, "lineno", -1)))
    tree.body = tree.body[:-1]
    module = types.ModuleType(module_name)
    module.__file__ = path
    exec(compile(tree, path, "exec"), module.__dict__)  # noqa: S102 - reviewed project file
    module.SOURCE_SHA256 = hashlib.sha256(raw).hexdigest()
    return module


SCORES_REQUIRED = ("load_p04_tool", "_materialize_passage", "_count_passage_actors", "scan_foreign_records",
                   "read_extensions")
TOOL_EXTRA_REQUIRED = ("S", "_state_differences", "_guid_text", "_write_json", "_read_json", "_dirty_census",
                       "_backup", "_save_narrow", "_pair_attachments", "_set_pair_attachments", "_attachment_rows",
                       "_make_blank_light", "_is_light", "_enum_member", "SHOW_PATH", "EXPECTED_WORLD",
                       "EXPECTED_PROJECT", "_asset_id")


def load_modules():
    scores = load_without_main(SCORES_TOOL_PATH, "_lighting_scores_for_p04_glint")
    missing = [n for n in SCORES_REQUIRED if not callable(getattr(scores, n, None))]
    require(not missing, "SCORES_API_DRIFT|" + ",".join(missing))
    tool = scores.load_p04_tool()
    missing = [n for n in TOOL_EXTRA_REQUIRED if not hasattr(tool, n)]
    require(not missing, "P04_TOOL_API_DRIFT|" + ",".join(missing))
    return scores, tool


def scan_foreign(scores, guids, saved_dir=None):
    saved = saved_dir or os.path.dirname(HERE)
    roots = [os.path.join(saved, n) for n in sorted(os.listdir(saved)) if n.startswith("Codex")]
    return scores.scan_foreign_records(roots, guids, exclude=[RECORD_PATH])


# --------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a global.
# --------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _ctx_facts(tool):
    project = os.path.normcase(os.path.normpath(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))).rstrip("\\/")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if world is not None else []
    return {"project_ok": project == tool.EXPECTED_PROJECT.rstrip("\\/"),
            "world": tool._asset_id(world) if world is not None else None,
            "world_ok": world is not None and tool._asset_id(world) == tool.EXPECTED_WORLD,
            "pie": editor.get_game_world() is not None,
            "sequencer_open": library is not None and library.get_current_level_sequence() is not None,
            "census": tool._dirty_census(),
            "zz_actors": sorted(a.get_actor_label() for a in actors if a.get_actor_label().startswith("ZZ_"))}


def _rows(scores, tool, attachments):
    """attachment_state rows (_infinity_attachment_state.py:104-129) + Body/Mover (lighting_scores_apply.py:879)."""
    out = []
    for attachment, row in zip(attachments, tool._attachment_rows(attachments)):
        row["ext"] = scores.read_extensions(tool, attachment)
        out.append(row)
    return out


def _find_structure(show):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    found = [a for a in subsystem.get_all_level_actors()
             if a.get_class().get_name() == "InfinityStageStructureActor" and a.get_actor_label() == STRUCTURE_LABEL]
    require(len(found) == 1, "STRUCTURE_COUNT|label=%s|count=%d" % (STRUCTURE_LABEL, len(found)))
    passage = found[0].get_editor_property("passage")
    require(passage is not None and passage.get_actor_label().startswith(PASSAGE_ACTOR_PREFIX),
            "STRUCTURE_PASSAGE_WRONG")
    require(passage.get_editor_property("show_asset") == show, "STRUCTURE_SHOW_WRONG")
    return found[0]


def _stations(tool, structure):
    """Live station frames: the C++ GatherStations (rig_lamp_drop.py:790-803)."""
    result = structure.gather_stations()
    if isinstance(result, tuple) and len(result) == 3:
        ok, stations, error = result
        require(bool(ok), "GATHER_STATIONS_FAILED|" + str(error))
    elif isinstance(result, tuple) and len(result) == 2:
        stations, error = result
    else:
        stations, error = result, ""
    require(stations is not None and len(list(stations)) > 0, "GATHER_STATIONS_EMPTY|" + str(error))
    return [{"cue_guid": tool._guid_text(s.get_editor_property("cue_guid")),
             "distance_cm": float(s.get_editor_property("distance_cm")),
             "world": tool.S._transform_state(s.get_editor_property("station_world"))} for s in stations]


def _passage_guid(tool, show):
    rows = [s for s in show.get_editor_property("passage_settings")
            if str(s.get_editor_property("label")) == PASSAGE_LABEL]
    require(len(rows) == 1, "PASSAGE_ROW_COUNT|label=%s|count=%d" % (PASSAGE_LABEL, len(rows)))
    value = rows[0].get_editor_property("passage_guid")
    return value, tool._guid_text(value)


def _runtime_plain(scores, tool, show, structure=None):
    cues = []
    for index, cue in enumerate(show.get_editor_property("cues")):
        pair = cue.get_editor_property("wing_pair")
        cues.append({"show_index": index, "guid": tool._guid_text(cue.get_editor_property("cue_guid")),
                     "label": str(cue.get_editor_property("label")), "type": str(cue.get_editor_property("type")),
                     "occurrence_offset": tool.S._transform_state(pair.get_editor_property("occurrence_offset")),
                     "attachments": _rows(scores, tool, tool._pair_attachments(cue))})
    value, guid = _passage_guid(tool, show)
    bays = [tool._guid_text(g) for g in show.get_wing_pair_cue_guids_in_passage(value)]
    return {"cues": cues, "bay_guids": bays, "passage_guid": guid,
            "stations": _stations(tool, structure) if structure is not None else []}


def _all_rows(plain):
    return {cue["guid"]: cue["attachments"] for cue in plain["cues"]}


def _export_hash(show, skip_cue_guid, tool):
    """Export text of every cue except the target + every PassageSettings row (p01_rig_pattern.py:754)."""
    texts = []
    for cue in show.get_editor_property("cues"):
        if tool._guid_text(cue.get_editor_property("cue_guid")) == skip_cue_guid:
            continue
        texts.append(str(cue.export_text()))
    for row in show.get_editor_property("passage_settings"):
        texts.append(str(row.export_text()))
    return _sha256_text("\n".join(texts))


def _cue_index(tool, show, cue_guid, label):
    cues = list(show.get_editor_property("cues"))
    hits = [i for i, c in enumerate(cues) if tool._guid_text(c.get_editor_property("cue_guid")) == cue_guid]
    require(len(hits) == 1, "CUE_RESOLVE|guid=%s|count=%d" % (cue_guid, len(hits)))
    require(str(cues[hits[0]].get_editor_property("label")) == label, "CUE_LABEL_DRIFT|" + cue_guid)
    return hits[0], cues


def _author(tool, vessel, source, plan, which, light_vessel=None):
    """Copy every field but the GUID from source, then the named overrides only."""
    minted = tool._guid_text(vessel.get_editor_property("attachment_guid"))
    for name in CLONE_FIELDS:
        vessel.set_editor_property(name, source.get_editor_property(name))
    planned = plan["planned_light"] if which == "light" else plan["planned_body"]
    vessel.set_editor_property("label", unreal.Text(planned["label"]))
    vessel.set_editor_property("enabled", True)
    loc = planned["relative_transform"]["location"]
    transform = vessel.get_editor_property("relative_transform")
    transform.set_editor_property("translation", unreal.Vector(float(loc[0]), float(loc[1]), float(loc[2])))
    if which == "light":
        rot = planned["relative_transform"]["rotation_xyzw"]
        transform.set_editor_property("rotation", unreal.Quat(float(rot[0]), float(rot[1]), float(rot[2]),
                                                              float(rot[3])))
    vessel.set_editor_property("relative_transform", transform)
    if which == "light":
        o = plan["overrides"]
        settings = vessel.get_editor_property("lighting")
        settings.set_editor_property("intensity_units", tool._enum_member(
            unreal.InfinityStageLightIntensityUnits, o["intensity_units"]))
        settings.set_editor_property("intensity", float(o["intensity_cd"]))
        settings.set_editor_property("attenuation_radius_cm", float(o["attenuation_cm"]))
        settings.set_editor_property("source_radius_cm", float(o["source_radius_cm"]))
        settings.set_editor_property("cast_shadows", bool(o["cast_shadows"]))
        rgb = o["color_rgb"]
        settings.set_editor_property("color", unreal.LinearColor(float(rgb[0]), float(rgb[1]), float(rgb[2]), 1.0))
        if o.get("steady"):
            settings.set_editor_property("light_function_material", None)
            drama = settings.get_editor_property("drama")
            drama.set_editor_property("strike_on_approach", False)
            settings.set_editor_property("drama", drama)
        vessel.set_editor_property("lighting", settings)
    elif plan["source"]["body_link_mode"] == "REMAP":
        body = vessel.get_editor_property("body")
        body.set_editor_property("light_attachment_guid", light_vessel.get_editor_property("attachment_guid"))
        vessel.set_editor_property("body", body)
    require(tool._guid_text(vessel.get_editor_property("attachment_guid")) == minted, "MINTED_GUID_CHANGED|" + which)
    return vessel


def _snapshot(tool, show, plan):
    """Struct copies of the target and scratch arrays taken BEFORE any write (the rollback source)."""
    ti, cues = _cue_index(tool, show, plan["cue_guid"], plan["cue_label"])
    si, unused = _cue_index(tool, show, plan["scratch"]["cue_guid"], plan["scratch"]["cue_label"])
    require(ti == plan["show_index"] and si == plan["scratch"]["show_index"], "SHOW_INDEX_DRIFT")
    return {"ti": ti, "si": si, "target": tool._pair_attachments(cues[ti]), "scratch": tool._pair_attachments(cues[si])}


def _rollback(tool, show, snap):
    tool._set_pair_attachments(show, snap["si"], snap["scratch"])
    tool._set_pair_attachments(show, snap["ti"], snap["target"])


def _mint_and_author(scores, tool, show, plan, snap):
    """Scratch-pair GUID minting exactly as lighting_scores_apply.py:2738-2814; returns [light_guid, body_guid].
    The caller rolls back from snap on ANY exception (here or in its own checks)."""
    ti, si = snap["ti"], snap["si"]
    target_original, scratch_original = snap["target"], snap["scratch"]
    cues = list(show.get_editor_property("cues"))
    scratch_before = _rows(scores, tool, scratch_original)
    target_lights = [tool._guid_text(a.get_editor_property("attachment_guid")) for a in target_original
                     if tool._is_light(a)]
    k, m = len(target_lights), sum(1 for a in scratch_original if tool._is_light(a))
    require(k == plan["light_count"] and m == plan["scratch"]["light_count"],
            "LIGHT_COUNT_DRIFT|target=%d/%d|scratch=%d/%d" % (k, plan["light_count"], m, plan["scratch"]["light_count"]))
    preexisting = {tool._guid_text(a.get_editor_property("attachment_guid"))
                   for cue in cues for a in tool._pair_attachments(cue)}
    by_guid = {tool._guid_text(a.get_editor_property("attachment_guid")): a for a in target_original}
    source_light, source_body = by_guid.get(plan["source"]["light_guid"]), by_guid.get(plan["source"]["body_guid"])
    require(source_light is not None and source_body is not None, "SOURCE_ROWS_GONE")
    padding = padding_needed(k, m)
    tool._set_pair_attachments(show, si, scratch_original + [tool._make_blank_light() for _ in range(padding)])
    fresh = list(show.get_editor_property("cues"))
    changed = show.replicate_light_attachments(fresh[si].get_editor_property("cue_guid"),
                                               [fresh[ti].get_editor_property("cue_guid")])
    require(int(changed) == 1, "REPLICATION_TARGET_COUNT|%s" % changed)
    tool._set_pair_attachments(show, si, scratch_original)
    restored = _rows(scores, tool, tool._pair_attachments(list(show.get_editor_property("cues"))[si]))
    diffs = tool._state_differences(scratch_before, restored)
    require(not diffs, "SCRATCH_NOT_RESTORED_EXACTLY|%s" % _canonical(diffs)[:2000])
    replicated = tool._pair_attachments(list(show.get_editor_property("cues"))[ti])
    vessels = [a for a in replicated if tool._is_light(a)]
    require(len(vessels) >= k + 2, "MINTED_SLOT_COUNT|need=%d|actual=%d" % (k + 2, len(vessels)))
    kept = [tool._guid_text(v.get_editor_property("attachment_guid")) for v in vessels[:k]]
    require(kept == target_lights, "REPLICATE_DID_NOT_KEEP_LIGHT_GUIDS")
    light_vessel, body_vessel = vessels[k], vessels[k + 1]
    minted = [tool._guid_text(light_vessel.get_editor_property("attachment_guid")),
              tool._guid_text(body_vessel.get_editor_property("attachment_guid"))]
    check_minted(minted, preexisting)
    _author(tool, light_vessel, source_light, plan, "light")
    _author(tool, body_vessel, source_body, plan, "body", light_vessel)
    tool._set_pair_attachments(show, ti, target_original + [light_vessel, body_vessel])
    return minted


def _materialize(scores, show):
    require(scores._count_passage_actors(show, PASSAGE_ACTOR_PREFIX) == 1, "PASSAGE_ACTOR_COUNT|" + PASSAGE_ACTOR_PREFIX)
    materialized = scores._materialize_passage(show, PASSAGE_ACTOR_PREFIX)
    require(materialized.get("structure") == STRUCTURE_LABEL, "STRUCTURE_NOT_REFIT|%s" % materialized)
    return materialized


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = args["mode"]
    report = {"ok": False, "mode": mode, "run": run, "args": args, "saved": False}
    tool = None
    try:
        scores, tool = load_modules()
        report["sources"] = {"scores_sha256": scores.SOURCE_SHA256, "p04_tool_sha256": tool.SCORES_SOURCE_SHA256}
        ctx = _ctx_facts(tool)
        report["context"] = ctx
        check_context(ctx, mode, args["allow_dirty"], tool.SHOW_PATH, tool.EXPECTED_WORLD)
        census_before = ctx["census"]
        pin = load_pin(cue_label=args["cue_label"])
        report["pin"] = pin
        show = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        require(show is not None, "SHOW_ASSET_MISSING")

        if mode in ("DRY", "ADD"):
            structure = _find_structure(show)
            plain = _runtime_plain(scores, tool, show, structure)
            before_all = _all_rows(plain)
            plan = build_plan(plain, args, pin)
            fake = ["%032X" % 0xF1, "%032X" % 0xF2]
            check_scope(tool, before_all, add_plain(before_all, plan, fake), plan, fake, "after")  # model self-check
            texts_hash = _export_hash(show, plan["cue_guid"], tool)
            foreign = scan_foreign(scores, [plan["cue_guid"]])
            unacked = sorted({h["path"] for h in foreign} - set(args["ack_records"]))
            report.update({"plan": plan, "foreign_records": foreign, "unacknowledged_foreign_records": unacked,
                           "active_record": RECORD_PATH if os.path.exists(RECORD_PATH) else None})
            frame = plan["frame"]
            if mode == "DRY":
                census_after = tool._dirty_census()
                require(census_after == census_before, "DRY_CENSUS_CHANGED|before=%s|after=%s"
                        % (_canonical(census_before), _canonical(census_after)))
                again = _all_rows(_runtime_plain(scores, tool, show))
                require(_canonical(again) == _canonical(before_all), "DRY_SHOW_ROWS_CHANGED")
                report.update({"ok": True, "mutated": False, "census_after": census_after})
                path = report_path(mode, run)
                tool._write_json(path, report)
                for w in plan["warnings"]:
                    _log("%s_WARNING|run=%s|%s" % (MARK, run, w))
                _log("%s_DRY_OK|run=%s|cue=%s|guid=%s|source=%s|rel_computed=%s|rel_nominal=%s|disagree_cm=%.3f"
                     "|scratch=%s|padding=%d|warnings=%d|foreign=%d|unacked=%d|active_record=%d|census_equal=1"
                     "|mutated=0|report=%s"
                     % (MARK, run, plan["cue_label"], plan["cue_guid"], plan["source"]["light_label"],
                        [round(v, 3) for v in frame["relative_computed_cm"]], frame["relative_nominal_cm"],
                        frame["disagreement_cm"], plan["scratch"]["cue_label"], plan["scratch"]["padding"],
                        len(plan["warnings"]), len(foreign), len(unacked), int(report["active_record"] is not None),
                        path))
                return report

            check_add_gate(unacked)
            backup = tool._backup(backup_prefix(mode), run)
            record = {"schema_version": 1, "status": "prepared", "run": run, "passage": PASSAGE_KEY,
                      "backup": backup, "args": args, "plan": plan, "cue_guid": plan["cue_guid"],
                      "cue_label": plan["cue_label"], "export_hash_before": texts_hash,
                      "before_cue_rows": before_all[plan["cue_guid"]], "minted_guids": [],
                      "acknowledged_records": list(args["ack_records"])}
            tool._write_json(RECORD_PATH, record, exclusive=True)   # fsynced before any mutation
            _log("%s_RECORD_WRITTEN|run=%s|path=%s" % (MARK, run, RECORD_PATH))
            snap = _snapshot(tool, show, plan)
            try:
                minted = _mint_and_author(scores, tool, show, plan, snap)
                record["minted_guids"] = minted
                after_all = _all_rows(_runtime_plain(scores, tool, show))
                check_scope(tool, before_all, after_all, plan, minted, "after")
                require(_export_hash(show, plan["cue_guid"], tool) == texts_hash, "EXPORT_OUTSIDE_SCOPE_CHANGED")
            except Exception:
                _rollback(tool, show, snap)
                restored = _all_rows(_runtime_plain(scores, tool, show))
                check_scope(tool, before_all, restored, plan, [], "before")
                record["status"] = "failed_rolled_back_in_memory"
                tool._write_json(RECORD_PATH, record)
                os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
                raise
            record.update({"status": "mutated_verified", "after_cue_rows": after_all[plan["cue_guid"]]})
            tool._write_json(RECORD_PATH, record)
            _log("%s_MINTED|run=%s|light=%s|body=%s" % (MARK, run, minted[0], minted[1]))
            materialized = _materialize(scores, show)
            tool._save_narrow()
            report["saved"] = True
            readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
            read_all = _all_rows(_runtime_plain(scores, tool, readback))
            check_scope(tool, before_all, read_all, plan, minted, "after")
            require(_export_hash(readback, plan["cue_guid"], tool) == texts_hash, "READBACK_EXPORT_OUTSIDE_SCOPE_CHANGED")
            record.update({"status": "saved_readback_verified", "materialized": materialized,
                           "after_cue_rows": read_all[plan["cue_guid"]], "saved_census": tool._dirty_census()})
            tool._write_json(RECORD_PATH, record)
            report.update({"ok": True, "backup": backup, "record": RECORD_PATH, "materialized": materialized,
                           "minted_guids": minted})
            tool._write_json(report_path(mode, run), report)
            _log("%s_ADD_OK|run=%s|cue=%s|light=%s|body=%s|rel=%s|show_saved=1|level_saved=1|readback=1|record=%s"
                 % (MARK, run, plan["cue_label"], minted[0], minted[1],
                    [round(v, 3) for v in frame["relative_computed_cm"]], RECORD_PATH))
            return report

        # REMOVE
        require(os.path.isfile(RECORD_PATH), "REMOVE_RECORD_ABSENT|" + RECORD_PATH)
        record = tool._read_json(RECORD_PATH)
        check_record(record)
        plain = _runtime_plain(scores, tool, show)
        before_all = _all_rows(plain)
        drifts = remove_drifts(tool, before_all, record)
        report["remove_drifts"] = drifts
        require(not drifts, "REMOVE_DRIFT|count=%d|%s" % (len(drifts), _canonical(drifts)[:3000]))
        model = remove_plain(tool, before_all, record)
        foreign = scan_foreign(scores, [record["cue_guid"]] + list(record["minted_guids"]))
        unacked = sorted({h["path"] for h in foreign} - set(args["ack_records"]))
        report.update({"foreign_records": foreign, "unacknowledged_foreign_records": unacked})
        require(not unacked, "FOREIGN_ACTIVE_RECORDS_OVERLAP|" + ";".join(unacked))
        texts_hash = _export_hash(show, record["cue_guid"], tool)
        backup = tool._backup(backup_prefix(mode), run)
        index, cues = _cue_index(tool, show, record["cue_guid"], record["cue_label"])
        original = tool._pair_attachments(cues[index])
        minted = set(record["minted_guids"])
        try:
            kept = [a for a in original if tool._guid_text(a.get_editor_property("attachment_guid")) not in minted]
            require(len(kept) == len(original) - 2, "REMOVE_GUID_COUNT|live=%d|kept=%d" % (len(original), len(kept)))
            tool._set_pair_attachments(show, index, kept)
            after_all = _all_rows(_runtime_plain(scores, tool, show))
            diffs = tool._state_differences(model, after_all)
            require(not diffs, "REMOVE_MODEL_MISMATCH|%s" % _canonical(diffs)[:3000])
            require(_export_hash(show, record["cue_guid"], tool) == texts_hash, "REMOVE_EXPORT_OUTSIDE_SCOPE_CHANGED")
        except Exception:
            tool._set_pair_attachments(show, index, original)
            raise
        materialized = _materialize(scores, show)
        tool._save_narrow()
        report["saved"] = True
        readback = unreal.EditorAssetLibrary.load_asset(tool.SHOW_PATH)
        read_all = _all_rows(_runtime_plain(scores, tool, readback))
        diffs = tool._state_differences(model, read_all)
        require(not diffs, "REMOVE_READBACK_MISMATCH|%s" % _canonical(diffs)[:3000])
        require(_export_hash(readback, record["cue_guid"], tool) == texts_hash, "REMOVE_READBACK_EXPORT_CHANGED")
        archived = RECORD_PATH + ".removed-" + run
        record["status"] = "reverted"
        tool._write_json(RECORD_PATH, record)
        os.rename(RECORD_PATH, archived)
        report.update({"ok": True, "backup": backup, "record_archived": archived, "materialized": materialized})
        tool._write_json(report_path(mode, run), report)
        _log("%s_REMOVE_OK|run=%s|cue=%s|removed=%s|show_saved=1|level_saved=1|readback=1|archived=%s"
             % (MARK, run, record["cue_label"], ",".join(record["minted_guids"]), archived))
        return report
    except Exception as error:  # noqa: BLE001 - a report and a marker for every stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        if tool is not None:
            try:
                report["census"] = tool._dirty_census()
            except Exception:  # noqa: BLE001
                pass
        with open(report_path(mode, run), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, default=str)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|saved=%d|%s%s"
                         % (MARK, run, mode, int(report["saved"]), report["error"][:1500],
                            "" if report["saved"] else "|NOTHING SAVED"))
        raise


def main():
    require(unreal is not None, "UNREAL_REQUIRED")
    try:
        args = check_args(globals().get("P04GLINT_ARGS"))
    except Exception as error:  # noqa: BLE001 - args refusals get the same stop marker
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    return _run(args)


if unreal is not None:
    main()
