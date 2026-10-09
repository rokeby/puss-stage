"""SHADOW-PLAY SPOT (5 Oct, offline-written, NEVER RUN IN UNREAL): the intense follow-spot on the curtain during the
shadow play inside Interaction I<n>, added to the Interaction sequence on top of an APPLIED curtain sleight
(curtain_sleight.py, record curtain_sleight_record_I<n>.json).

Gary, 5 Oct: "the boy cat shadow slot (whose intense spotlight is what makes the bg dark and transition possible)".

WHAT IT WRITES (the Interaction sequence asset ONLY; no level actor, no Show, no Master):
  two spawnable SpotLights in the SAME pose relative to their drapes (a matched pair, like the sleight's twin lantern):
    "Shadow Play Spot (Hangar)"  on the hangar twin drape   [play start -> hangar strike]   (seen until the cut)
    "Shadow Play Spot (Mouth)"   on the P(n+1) mouth drape  [play start -> GO HOLD -> fade] (seen from the cut on)
  WHY TWO: the sleight cut must be invisible. With one spot on the hangar curtain only, the curtain's brightness would
  drop by the spot/lantern ratio (default 16x, 4 stops) on the cut frame. The mouth spot is the spot's twin, exactly as
  curtain_sleight.py's twin lantern is the mouth lantern's twin (curtain_sleight.py:297-331) [decl].
  Position: stalls / front of house = on the drape's centre line, in front of the camera, raised `elevation_deg`, at
  `throw_cm` from the AIM POINT = the framed centre of the curtain's front fold (drape frame [front_x, 0, eye_z]; the
  shadow card's centre plane, curtain_sleight plan hangar_card.rel_drape) [decl: record].
  Pose source: the hangar drape's own transform keys IN THE SEQUENCE (curtain_sleight keys it in world space,
  curtain_sleight.py:402-416), read live and checked against the record; never composed through a hangar root pose.
  The live LANDED root is used only for the oriented inside-box guard (memory: level-saved-landed frame trap).

KEYS (Interaction display frames; I1 at 25 fps: play start 175, sleight 1250, hangar strike 1300, GO 10 HOLD 1675,
length 2183, all from the live CST markers, cross-checked against the record):
  both:   0 cd until play start, fast fade (fade_up_s, 0 = snap) to peak.
  hangar: hold to the hangar strike (after the cut, unseen), 0 the frame after; despawn after that.
  mouth:  hold through the GO HOLD (the transport rests one frame before GO, peak there), fade over fade_out_s from the
          GO frame into the drop; despawn after that.
  Nothing changes on either side within `ready_frames` of the sleight cut (same rule as curtain_sleight check 6).

Modes (globals set by shadow_play_spot_run.py):  SHADOW_PLAY_SPOT_INTERACTION 1..5, SHADOW_PLAY_SPOT_MODE
DRY|APPLY|REVERT, SHADOW_PLAY_SPOT_CONFIRM must equal "<MODE> I<n>", SHADOW_PLAY_SPOT_PARAMS dict, _RUN_ID optional.
Markers: SHADOW_PLAY_SPOT_DRY_OK / _APPLY_OK / _REVERT_OK |run=<id>|interaction=<n>|...  or SHADOW_PLAY_SPOT_STOPPED.
Never Save All, never end PIE, never reload the level, no Sequencer UI, no unreal objects in module globals.

Tiers per claim in comments: [decl] read in a file/header (cited), [prec] an in-repo precedent call (cited, whether it
ran), [meas] measured read-back (dated), [inf] inferred. DRY prints API_TABLE with the tier of every Unreal call.
Importing with no `unreal` (system Python) never touches Unreal: test_shadow_play_spot.py exercises the pure parts.
"""
import copy
import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


# =====================================================================================================================
# curtain_sleight.py definitions (the live-proven tool), loaded WITHOUT its trailing main() - the
# curtain_sleight_diag_bindings.py:9-12 pattern. Private namespace: overriding _stop / TRACK_NAME in it touches nothing
# else.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def load_sleight_lib(here=None):
    path = os.path.join(here or _here(), "curtain_sleight.py")
    with open(path, "r", encoding="utf-8") as handle:
        src = handle.read()
    cut = src.rindex("if unreal is not None:")
    ns = {"__name__": "curtain_sleight_lib_for_spot", "__file__": path}
    exec(compile(src[:cut], path, "exec"), ns)  # noqa: S102 - the conductor's own reviewed tool; definitions only
    for need in ("_snapshot", "_spawn_track", "_key_pose", "_key_float", "_census", "_read_markers", "_guid",
                 "_content_file", "_actors", "_by_label", "_one", "_ppv_rows", "_segment_hits","normalize_snapshot", "snapshot_diff",
                 "frames", "key_at", "pose_at", "bool_at", "direction", "wrap", "half_extent", "inside_hangar",
                 "parse_go_label", "MOUTH_DRAPE", "EXPECTED_WORLD", "SEQS", "ROOT_LABEL", "DOORS_RECORD", "TRACK_NAME",
                 "POSE_CHANNELS", "ROOT_TOLERANCE_CM", "ROOT_TOLERANCE_DEG"):
        if need not in ns:
            raise RuntimeError("SLEIGHT_LIB_MISSING|" + need)
    ns["SOURCE_SHA256"] = hashlib.sha256(src.encode("utf-8")).hexdigest()
    return ns


CS = load_sleight_lib()
SLEIGHT_TRACK_NAME = CS["TRACK_NAME"]                    # "CurtainSleight (Conductor)": the drape's transform track
TRACK_NAME = "ShadowPlaySpot (Conductor)"
CS["TRACK_NAME"] = TRACK_NAME                            # so CS._key_pose/_key_float name OUR tracks

SPOT_NAMES = {"hangar": "Shadow Play Spot (Hangar)", "mouth": "Shadow Play Spot (Mouth)"}
SIDES = ("hangar", "mouth")
HANGAR_DRAPE = "Sleight Hangar Drape"                    # curtain_sleight.py:86
SLEIGHT_RECORD = "curtain_sleight_record_I%d.json"
RECORD_PATTERN = "shadow_play_spot_record_I%d.json"
PLAN_PATTERN = "shadow_play_spot_plan_I%d.json"
DRY_PATTERN = "shadow_play_spot_I%d_dry.json"
BEAT_LABELS = {"play0": "CST play start", "sleight": "CST sleight", "strike": "CST hangar strike",
               "release": "CST drop"}                    # curtain_sleight.py:466-470
LEGACY_MARKERS = ("InfinityStage.BoyCatStart", "InfinityStage.HiddenChangeover", "InfinityStage.CurtainFullyDown",
                  "InfinityStage.CurtainRiseStart", "InfinityStage.CurtainFullyOpen")
MODES = ("DRY", "APPLY", "REVERT")

DEFAULTS = {
    "throw_cm": 3000.0,          # spot -> aim point (stalls / FOH, behind and above the matched camera at 1200 cm)
    "elevation_deg": 20.0,       # beam tilted down this much (FOH rake) [inf: creative, Gary]
    "azimuth_deg": 0.0,          # 0 = on the drape centre line
    "circle_diameter_cm": 360.0, # outer-cone circle on the drape (the matched frame is ~786 x 442 cm)
    "inner_ratio": 0.6,          # inner cone / outer cone: the soft edge spans the outer 40 % of the radius
    "ratio_to_lantern": 16.0,    # spot illuminance / lantern illuminance at the aim point (4 stops) [inf: Gary]
    "candela": None,             # explicit override of the computed peak (both sides)
    "hangar_gain": 1.0,          # hangar spot = mouth spot x gain (exposure compensation; see DRY EXPOSURE_*)
    "fade_up_s": 0.5,            # 0 = snap
    "fade_out_s": 1.0,           # from the GO frame
    "spawn_lead_frames": 25,     # spawned (at 0 cd) this long before the fade up
    "kelvin": None,              # None = the sleight's lantern colour (record plan.lantern.copy.kelvin)
    "source_radius_cm": 2.0,     # small source: crisp shadows of the puppets
    "radius_factor": 1.5,        # attenuation radius = throw x this
    "frame_margin_cm": 20.0,     # circle stays this far inside the matched camera frame
    "match_tol_cm": 0.5, "match_tol_deg": 0.05,
}


class PlanError(ValueError):
    pass


# =====================================================================================================================
# Pure geometry (frames carry loc, yaw and an optional pitch; pitch exists for the REST-pose control and the guard)
# =====================================================================================================================

def rot_py(v, pitch, yaw):
    """UE rotator order without roll: pitch about Y (forward (1,0,0) -> (cos p, 0, sin p)), then yaw about Z."""
    p, y = math.radians(float(pitch)), math.radians(float(yaw))
    x1 = v[0] * math.cos(p) - v[2] * math.sin(p)
    z1 = v[0] * math.sin(p) + v[2] * math.cos(p)
    y1 = v[1]
    return [x1 * math.cos(y) - y1 * math.sin(y), x1 * math.sin(y) + y1 * math.cos(y), z1]


def rot_py_inv(v, pitch, yaw):
    y, p = math.radians(-float(yaw)), math.radians(-float(pitch))
    x1 = v[0] * math.cos(y) - v[1] * math.sin(y)
    y1 = v[0] * math.sin(y) + v[1] * math.cos(y)
    return [x1 * math.cos(p) - v[2] * math.sin(p), y1, x1 * math.sin(p) + v[2] * math.cos(p)]


def to_world(frame, p):
    d = rot_py(p, frame.get("pitch", 0.0), frame["yaw"])
    return [float(frame["loc"][i]) + d[i] for i in range(3)]


def to_local(frame, p):
    return rot_py_inv([float(p[i]) - float(frame["loc"][i]) for i in range(3)], frame.get("pitch", 0.0), frame["yaw"])


def compose(parent, local):
    return {"loc": to_world(parent, local["loc"]), "yaw": float(parent["yaw"]) + float(local["yaw"]),
            "pitch": float(parent.get("pitch", 0.0)) + float(local.get("pitch", 0.0))}


def angles_of(d):
    n = math.sqrt(sum(c * c for c in d))
    return math.degrees(math.asin(max(-1.0, min(1.0, d[2] / n)))), math.degrees(math.atan2(d[1], d[0]))


def frame_of_pose(pose):
    return {"loc": [float(v) for v in pose["loc"]], "yaw": float(pose["yaw"]), "pitch": float(pose.get("pitch", 0.0))}


def merged_params(params):
    unknown = sorted(set(params or {}) - set(DEFAULTS))
    if unknown:
        raise PlanError("UNKNOWN_PARAMS: %r" % unknown)
    out = dict(DEFAULTS)
    out.update(params or {})
    return out


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


# =====================================================================================================================
# Pure inputs: from the sleight record (and, live, the same fields re-read from Unreal and compared)
# =====================================================================================================================

def hangar_box(doors, n):
    """curtain_sleight.py _gather:1279-1305, pure: the landed hangar interior in the root frame [decl]."""
    rows = [r for r in doors["plan"]["scenes"] if int(r["scene"]) == n]
    if len(rows) != 1:
        raise PlanError("DOORS_ROW: scene %d" % n)
    leaf = [pc for pc in rows[0]["pieces"] if pc["role"] == "leaf"][0]
    dims = rows[0]["hangar_dimensions"]
    rec = doors["root_before"][str(n)]
    return {"half_w": float(dims["half_w"]), "height": float(dims["height"]),
            "door_face_x": float(leaf["location_cm"][0]) - float(leaf["size_cm"][0]) / 2.0,
            "floor_z": float(leaf["location_cm"][2]) - float(leaf["size_cm"][2]) / 2.0 - 0.5,
            "root_recorded": {"loc": [float(v) for v in rec["location"]], "yaw": float(rec["rotation"][2]),
                              "pitch": float(rec["rotation"][1])}}


def beats_from_markers(markers):
    """The CST beat frames + the GO marker from the sequence's own marked frames. Missing/duplicate -> PlanError."""
    beats = {}
    for key, label in BEAT_LABELS.items():
        rows = [int(f) for lab, f in markers if str(lab) == label]
        if len(rows) != 1:
            raise PlanError("BEATS_MISSING: %r found %d times" % (label, len(rows)))
        beats[key] = rows[0]
    gos = [[str(lab), int(f)] for lab, f in markers if CS["parse_go_label"](lab)]
    at_release = [g for g in gos if g[1] == beats["release"]]
    if len(at_release) != 1:
        raise PlanError("GO_MISSING_AT_DROP: GO markers %r, drop at %d" % (gos, beats["release"]))
    parsed = CS["parse_go_label"](at_release[0][0])
    # GOREL-ALL5-APPLY-1 deliberately made the release cues explicit PASS cues.
    # Gary approved exactly ``GO <number> PASS curtain``.  Keep the semantic
    # guard narrow: another PASS label at the drop is still drift and refuses.
    if parsed[2] == 0 and parsed[1] != "curtain":
        raise PlanError("GO_PASS_LABEL: %r expected 'curtain'" % at_release[0][0])
    return beats, at_release[0]


def inputs_from_record(record, doors):
    """Every planner input, from the APPLIED sleight record (+ the doors record for the box). Live mode overwrites the
    sequence-derived fields with fresh reads and compare_live() refuses on any difference."""
    plan = record["plan"]
    n = int(record["interaction"])
    fps = float(plan["fps"])
    snap = record["snapshot_after"]
    beats, go = beats_from_markers(snap["markers"])
    hk = plan["hangar_drape"]["keys"]
    pose = CS["pose_at"]
    cam_rel = plan["cam_rel_drape"]
    front_x = float(plan["lens"]["matched_focus_cm"]) + float(cam_rel["loc"][0])   # focus = front_x - cam_x (:379)
    card = plan["hangar_card"]
    card_front = float(card["rel_drape"][0]) + float(plan["params"]["card_gap_cm"]) + float(plan["params"]["card_t_cm"]) / 2.0
    lt = plan["lantern"]
    ref = plan["frames_of_reference"]
    return {
        "n": n, "fps": fps, "start": int(snap["playback"][0]), "end": int(snap["playback"][1]),
        "beats": beats, "go": go, "markers": [list(m) for m in snap["markers"]],
        "record_frames": {k: int(plan["frames"][k]) for k in ("play0", "sleight", "strike", "release")},
        "hangar_drape_at": {"play0": pose(hk, beats["play0"]), "sleight": pose(hk, beats["sleight"]),
                            "strike": pose(hk, beats["strike"])},
        "mouth_drape": {"loc": list(ref["mouth_drape_world"]["loc"]), "yaw": float(ref["mouth_drape_world"]["yaw"]),
                        "pitch": 0.0},
        "root_live": {"loc": list(ref["root"]["loc"]), "yaw": float(ref["root"]["yaw"]), "pitch": 0.0},
        "drape_local": {"loc": list(ref["drape_local"]["loc"]), "yaw": float(ref["drape_local"]["yaw"])},
        "hangar": hangar_box(doors, n),
        "front_x": front_x, "card_front_x": card_front, "eye_z": float(cam_rel["loc"][2]), "cam_rel": cam_rel,
        "focal_mm": float(plan["lens"]["matched_focal_mm"]), "filmback_mm": [float(v) for v in plan["lens"]["filmback_mm"]],
        "lantern": {"candela": float(lt["candela"]), "throw_cm": float(lt["throw_twin_cm"]),
                    "kelvin": float(lt["copy"]["kelvin"]), "label": lt["label"]},
        "ready": int(plan["params"]["ready_frames"]), "box_margin": float(plan["params"]["box_margin_cm"]),
        "sleight_run": record.get("run"), "sleight_plan_digest": record.get("plan_digest"),
    }


# =====================================================================================================================
# Pure planner
# =====================================================================================================================

def plan_spot(inputs, params):
    p = merged_params(params)
    fps, b = float(inputs["fps"]), inputs["beats"]
    fr = CS["frames"]
    if b["play0"] < int(p["spawn_lead_frames"]) + 1:
        raise PlanError("PLAY_START_TOO_EARLY: play start %d, spawn lead %d" % (b["play0"], p["spawn_lead_frames"]))
    elev, az, throw = float(p["elevation_deg"]), float(p["azimuth_deg"]), float(p["throw_cm"])
    aim_rel = [float(inputs["front_x"]), 0.0, float(inputs["eye_z"])]
    dir_rel = CS["direction"](-elev, az)                       # beam direction in the drape frame (+x = into the drape)
    loc_rel = [aim_rel[i] - throw * dir_rel[i] for i in range(3)]
    frames_world = {"hangar": frame_of_pose(inputs["hangar_drape_at"]["sleight"]), "mouth": dict(inputs["mouth_drape"])}

    # photometry: same illuminance ratio over the curtain's existing key light (the twin/mouth lantern)
    lt = inputs["lantern"]
    e_lantern = float(lt["candela"]) / (float(lt["throw_cm"]) / 100.0) ** 2   # lux at the aim point, E = I / d^2
    cos_inc = dir_rel[0]                                       # drape normal faces -x
    if cos_inc <= 0.05:
        raise PlanError("GRAZING_BEAM: cos(incidence) %.3f" % cos_inc)
    if p["candela"] is not None:
        peak = float(p["candela"])
    else:
        peak = float(p["ratio_to_lantern"]) * e_lantern * (throw / 100.0) ** 2 / cos_inc
    e_spot = peak * cos_inc / (throw / 100.0) ** 2
    peaks = {"hangar": peak * float(p["hangar_gain"]), "mouth": peak}
    outer = math.degrees(math.atan(float(p["circle_diameter_cm"]) / 2.0 / throw))
    inner = outer * float(p["inner_ratio"])

    # keys
    up0 = int(b["play0"])
    up1 = up0 + fr(p["fade_up_s"], fps)
    fade_out = max(1, fr(p["fade_out_s"], fps))               # 0 s = off on the frame after the GO

    def up_keys(pk):
        if up1 == up0:                                         # snap
            return [(0, 0.0), (up0 - 1, 0.0), (up0, pk)]
        return [(0, 0.0), (up0, 0.0), (up1, pk)]

    rel = int(b["release"])
    keys = {"hangar": up_keys(peaks["hangar"]) + [(int(b["strike"]), peaks["hangar"]), (int(b["strike"]) + 1, 0.0)],
            "mouth": up_keys(peaks["mouth"]) + [(rel, peaks["mouth"]), (rel + fade_out, 0.0)]}
    lead = up0 - int(p["spawn_lead_frames"])
    spawn = {"hangar": [(lead, True), (int(b["strike"]) + 2, False)],
             "mouth": [(lead, True), (keys["mouth"][-1][0] + 1, False)]}
    end = int(inputs["end"])
    spots = {}
    for side in SIDES:
        fw = frames_world[side]
        loc = to_world(fw, loc_rel)
        pitch, yaw = angles_of(rot_py(dir_rel, fw.get("pitch", 0.0), fw["yaw"]))
        pose = (loc[0], loc[1], loc[2], pitch, CS["wrap"](yaw), 0.0)          # (x, y, z, pitch, yaw, roll)
        spots[side] = {"name": SPOT_NAMES[side], "world": {"loc": loc, "pitch": pitch, "yaw": CS["wrap"](yaw), "roll": 0.0},
                       "transform_keys": [(0,) + pose, (end,) + pose], "intensity_keys": keys[side],
                       "spawn": spawn[side], "peak_cd": peaks[side], "aim_world": to_world(fw, aim_rel),
                       "drape_frame": fw}
    required_end = max([k[0] for s in spots.values() for k in s["intensity_keys"]]
                       + [f for s in spots.values() for f, _ in s["spawn"]])
    plan = {"n": int(inputs["n"]), "fps": fps, "end": end, "start": int(inputs["start"]), "beats": dict(b),
            "go": list(inputs["go"]), "aim_rel": aim_rel, "dir_rel": dir_rel, "loc_rel": loc_rel,
            "throw_cm": throw, "elevation_deg": elev, "azimuth_deg": az,
            "cone": {"outer_deg": outer, "inner_deg": inner, "circle_diameter_cm": float(p["circle_diameter_cm"])},
            "light": {"units": "CANDELAS", "kelvin": float(p["kelvin"] if p["kelvin"] is not None else lt["kelvin"]),
                      "cast_shadows": True, "source_radius_cm": float(p["source_radius_cm"]),
                      "attenuation_radius_cm": throw * float(p["radius_factor"])},
            "photometry": {"lantern_label": lt["label"], "lantern_cd": float(lt["candela"]),
                           "lantern_throw_cm": float(lt["throw_cm"]), "lantern_lux": e_lantern,
                           "spot_lux": e_spot, "ratio": e_spot / e_lantern, "cos_incidence": cos_inc,
                           "peak_cd": peak, "hangar_gain": float(p["hangar_gain"])},
            "up": [up0, up1], "fade_out": [rel, rel + fade_out], "spots": spots, "required_end": required_end,
            "params": p}
    plan["digest"] = digest({k: v for k, v in plan.items() if k != "digest"})
    return plan


# =====================================================================================================================
# Pure checks (each has a failing control in test_shadow_play_spot.py)
# =====================================================================================================================

def _line_distance(point, origin, direction):
    d = [point[i] - origin[i] for i in range(3)]
    t = sum(d[i] * direction[i] for i in range(3))
    return math.sqrt(max(0.0, sum(c * c for c in d) - t * t)), t


def check_spot(plan, inputs):
    p, b, fail = plan["params"], plan["beats"], []
    ready, tol_cm, tol_deg = int(inputs["ready"]), float(p["match_tol_cm"]), float(p["match_tol_deg"])
    s = int(b["sleight"])
    ka, ba = CS["key_at"], CS["bool_at"]

    # 1. beats order and room for the fades
    if not (b["play0"] < s < b["strike"] and s < b["release"]):
        fail.append("BEATS_ORDER: %r" % b)
    if plan["up"][1] + ready > s:
        fail.append("READY: the fade up ends at %d, < %d frames before the cut %d" % (plan["up"][1], ready, s))
    if b["strike"] < s + ready:
        fail.append("READY: the hangar spot goes off at %d, within %d frames after the cut" % (b["strike"], ready))

    # 2. playback range: never changes (every key and spawn edge inside [start, end])
    if plan["required_end"] > plan["end"] or plan["end"] != int(inputs["end"]) or plan["start"] != int(inputs["start"]):
        fail.append("RANGE_WOULD_CHANGE: keys reach %d, playback [%d, %d] (refuse; never lengthen)"
                    % (plan["required_end"], inputs["start"], inputs["end"]))
    if min(k[0] for sp in plan["spots"].values() for k in sp["intensity_keys"]) < plan["start"]:
        fail.append("RANGE_WOULD_CHANGE: a key before the playback start")

    # 3. key timing against the beats
    for side in SIDES:
        k, pk = plan["spots"][side]["intensity_keys"], plan["spots"][side]["peak_cd"]
        if ka(k, b["play0"] - 1, 1) != 0.0:
            fail.append("TIMING_%s: lit before the play start" % side.upper())
        if abs(ka(k, plan["up"][1], 1) - pk) > 1.0e-9:
            fail.append("TIMING_%s: not at peak at the end of the fade up (%d)" % (side.upper(), plan["up"][1]))
        if any(s - ready < kk[0] < s + ready for kk in k) or abs(ka(k, s - ready, 1) - ka(k, s + ready, 1)) > 1.0e-9 \
                or abs(ka(k, s, 1) - pk) > 1.0e-9:
            fail.append("STATE_CHANGES_ACROSS_CUT: the %s spot is not steady at peak in [%d, %d]" % (side, s - ready, s + ready))
        sp = plan["spots"][side]["spawn"]
        if any(s - ready <= f <= s + ready for f, _ in sp) or not ba(sp, s):
            fail.append("STATE_CHANGES_ACROSS_CUT: %s spot spawn edge near / not spawned at the cut" % side)
        if not ba(sp, plan["up"][0]) or ba(sp, plan["up"][0] - int(p["spawn_lead_frames"]) - 1):
            fail.append("SPAWN_%s: not spawned exactly spawn_lead_frames before the fade up" % side.upper())
        if not ba(sp, k[-1][0]):
            fail.append("SPAWN_%s: despawned before its last key %d" % (side.upper(), k[-1][0]))
    km = plan["spots"]["mouth"]["intensity_keys"]
    pm = plan["spots"]["mouth"]["peak_cd"]
    rel = int(b["release"])
    if abs(ka(km, rel - 1, 1) - pm) > 1.0e-9 or abs(ka(km, rel, 1) - pm) > 1.0e-9:
        fail.append("FADE_BEFORE_GO: the mouth spot is not at peak on the HOLD frame %d / GO frame %d" % (rel - 1, rel))
    if ka(km, plan["fade_out"][1], 1) != 0.0 or km[-1][1] != 0.0:
        fail.append("TIMING_MOUTH: not dark at the end of the fade out")
    if list(plan["go"]) != list(inputs["go"]) or plan["go"][1] != rel:
        fail.append("GO_NOT_AT_DROP: %r vs drop %d" % (plan["go"], rel))
    kh = plan["spots"]["hangar"]["intensity_keys"]
    if ka(kh, b["strike"] + 1, 1) != 0.0:
        fail.append("TIMING_HANGAR: still lit after the hangar strike")

    # 4. matched pair at the cut
    rels = {}
    for side in SIDES:
        sp = plan["spots"][side]
        fw = sp["drape_frame"]
        rels[side] = {"loc": to_local(fw, sp["world"]["loc"]),
                      "dir": rot_py_inv(CS["direction"](sp["world"]["pitch"], sp["world"]["yaw"]), fw.get("pitch", 0.0), fw["yaw"])}
    dl = max(abs(rels["hangar"]["loc"][i] - rels["mouth"]["loc"][i]) for i in range(3))
    dot = sum(rels["hangar"]["dir"][i] * rels["mouth"]["dir"][i] for i in range(3))
    da = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
    if dl > tol_cm or da > tol_deg:
        fail.append("MATCH_POSE: the two spots differ relative to their drapes by %.3f cm / %.4f deg" % (dl, da))
    ih, im = ka(kh, s, 1), ka(km, s, 1)
    if abs(ih - im * float(p["hangar_gain"])) > 1.0e-6 * max(1.0, im):
        fail.append("MATCH_INTENSITY: hangar %.3f cd vs mouth %.3f cd x gain %.3f at the cut" % (ih, im, p["hangar_gain"]))

    # 5. aim: each beam axis passes through its curtain's aim point, at the planned throw
    for side in SIDES:
        sp = plan["spots"][side]
        dist, t = _line_distance(sp["aim_world"], sp["world"]["loc"], CS["direction"](sp["world"]["pitch"], sp["world"]["yaw"]))
        if dist > 0.5 or abs(t - plan["throw_cm"]) > 0.5:
            fail.append("AIM_%s: axis misses the aim point by %.2f cm (along %.1f, throw %.1f)" % (side.upper(), dist, t, plan["throw_cm"]))
    if abs(float(inputs["front_x"]) - float(inputs["card_front_x"])) > 0.01:
        fail.append("AIM_RECORD_INCONSISTENT: front fold %.3f (lens) vs %.3f (card)" % (inputs["front_x"], inputs["card_front_x"]))

    # 6. the hangar drape: hung through the play window, on the LIVE landed root, untilted
    hd = inputs["hangar_drape_at"]
    for key in ("play0", "strike"):
        a, c = hd[key], hd["sleight"]
        if max(abs(a["loc"][i] - c["loc"][i]) for i in range(3)) > tol_cm or abs(CS["wrap"](a["yaw"] - c["yaw"])) > tol_deg:
            fail.append("DRAPE_NOT_HUNG: the hangar drape moves between %s and the cut" % key)
    fw = plan["spots"]["hangar"]["drape_frame"]
    if abs(fw.get("pitch", 0.0)) > 1.0e-3 or abs(hd["sleight"].get("roll", 0.0)) > 1.0e-3 or \
            abs(inputs["mouth_drape"].get("pitch", 0.0)) > 1.0e-3:
        fail.append("DRAPE_TILTED: hangar pitch %.3f, mouth pitch %.3f" % (fw.get("pitch", 0.0), inputs["mouth_drape"].get("pitch", 0.0)))
    on_root = compose(inputs["root_live"], inputs["drape_local"])
    dd = max(abs(on_root["loc"][i] - fw["loc"][i]) for i in range(3))
    if dd > tol_cm or abs(CS["wrap"](on_root["yaw"] - fw["yaw"])) > tol_deg or abs(on_root["pitch"] - fw.get("pitch", 0.0)) > tol_deg:
        fail.append("DRAPE_NOT_ON_LIVE_ROOT: the sequence's drape is %.1f cm from live root + recorded drape_local" % dd)

    # 7. inside-box guard (oriented: the LIVE landed root frame) + the mouth-side stalls envelope
    hb = inputs["hangar"]
    margin = float(inputs["box_margin"])
    lp = to_local(inputs["root_live"], plan["spots"]["hangar"]["world"]["loc"])
    bad = CS["inside_hangar"](lp, lp, hb, margin)
    if bad:
        fail.append("BOX: the hangar spot leaves the landed hangar on %s (root-frame %s)" % (",".join(bad), [round(v, 1) for v in lp]))
    for side in SIDES:
        sp = plan["spots"][side]
        r = to_local(sp["drape_frame"], sp["world"]["loc"])
        if r[0] > float(inputs["front_x"]) - 100.0 or r[2] < hb["floor_z"] + margin or r[2] > hb["height"] - margin \
                or abs(r[1]) > hb["half_w"] - margin:
            fail.append("STALLS_ENVELOPE_%s: spot at drape-frame %s is not in front of / above the drape floor"
                        % (side.upper(), [round(v, 1) for v in r]))
        w = sp["world"]["loc"]
        if w[2] < sp["drape_frame"]["loc"][2]:
            fail.append("BELOW_DRAPE_FLOOR_%s: world z %.1f under the drape floor %.1f" % (side.upper(), w[2], sp["drape_frame"]["loc"][2]))

    # 8. the circle sits inside the matched camera frame on the curtain (exact edge rays in the drape frame)
    cam_x = float(inputs["cam_rel"]["loc"][0])
    hw, hh = CS["half_extent"](float(inputs["front_x"]) - cam_x, float(inputs["focal_mm"]), inputs["filmback_mm"])
    outer = plan["cone"]["outer_deg"]
    fm = float(p["frame_margin_cm"])
    S = plan["loc_rel"]
    for dp, dy in ((outer, 0.0), (-outer, 0.0), (0.0, outer), (0.0, -outer)):
        d = CS["direction"](-plan["elevation_deg"] + dp, plan["azimuth_deg"] + dy)
        if d[0] <= 1.0e-6:
            fail.append("CIRCLE_OUTSIDE_FRAME: an edge ray does not reach the curtain")
            break
        t = (float(inputs["front_x"]) - S[0]) / d[0]
        y, z = S[1] + t * d[1], S[2] + t * d[2]
        if abs(y - float(inputs["cam_rel"]["loc"][1])) > hw - fm or abs(z - float(inputs["cam_rel"]["loc"][2])) > hh - fm:
            fail.append("CIRCLE_OUTSIDE_FRAME: edge at (y %.0f, z %.0f), frame half %.0f x %.0f - %.0f margin"
                        % (y, z, hw, hh, fm))
            break
    if not (0.0 < plan["cone"]["inner_deg"] < outer <= 80.0):
        fail.append("CONE: inner %.2f / outer %.2f" % (plan["cone"]["inner_deg"], outer))
    if plan["light"]["attenuation_radius_cm"] < plan["throw_cm"] * 1.05:
        fail.append("RADIUS_SHORT: attenuation %.0f < throw x 1.05" % plan["light"]["attenuation_radius_cm"])
    return fail


def compare_live(record_inputs, live_inputs, tol_cm=0.5, tol_deg=0.05):
    """Live re-reads must equal what the sleight record says it wrote (else the sequence drifted since APPLY)."""
    fail = []
    if live_inputs["beats"] != record_inputs["record_frames"]:
        fail.append("BEATS_DRIFTED: live CST markers %r vs record %r" % (live_inputs["beats"], record_inputs["record_frames"]))
    if [live_inputs["start"], live_inputs["end"]] != [record_inputs["start"], record_inputs["end"]]:
        fail.append("RANGE_DRIFTED: live [%d, %d] vs record [%d, %d]" % (live_inputs["start"], live_inputs["end"],
                                                                        record_inputs["start"], record_inputs["end"]))
    for key in ("play0", "sleight", "strike"):
        a, b = live_inputs["hangar_drape_at"][key], record_inputs["hangar_drape_at"][key]
        if max(abs(a["loc"][i] - b["loc"][i]) for i in range(3)) > tol_cm or abs(CS["wrap"](a["yaw"] - b["yaw"])) > tol_deg:
            fail.append("DRAPE_KEYS_DRIFTED at %s: live %r vs record %r" % (key, a, b))
    a, b = live_inputs["mouth_drape"], record_inputs["mouth_drape"]
    if max(abs(a["loc"][i] - b["loc"][i]) for i in range(3)) > tol_cm or abs(CS["wrap"](a["yaw"] - b["yaw"])) > tol_deg:
        fail.append("MOUTH_DRAPE_DRIFTED: live %r vs record %r" % (a, b))
    a, b = live_inputs["root_live"], live_inputs["hangar"]["root_recorded"]
    if max(abs(a["loc"][i] - b["loc"][i]) for i in range(3)) > CS["ROOT_TOLERANCE_CM"] or \
            abs(CS["wrap"](a["yaw"] - b["yaw"])) > CS["ROOT_TOLERANCE_DEG"] or abs(a.get("pitch", 0.0) - b.get("pitch", 0.0)) > CS["ROOT_TOLERANCE_DEG"]:
        fail.append("ROOT_NOT_LANDED: live %r vs doors record %r" % (a, b))
    return fail


def exposure_summary(ppv_rows):
    """Pinned EV100 per camera from the PPV rows the DRY reads (curtain_sleight _ppv_rows). min == max = pinned."""
    out = {}
    for side, rows in ppv_rows.items():
        pinned = sorted({float(r["min_ev"]) for r in rows if r.get("enabled") and r.get("min_ev") is not None
                         and r.get("max_ev") is not None and abs(float(r["min_ev"]) - float(r["max_ev"])) < 1.0e-6})
        free = [r["ppv"] for r in rows if r.get("enabled") and (r.get("min_ev") is None or r.get("max_ev") is None
                                                                 or abs(float(r["min_ev"]) - float(r["max_ev"])) >= 1.0e-6)]
        out[side] = {"pinned_ev100": pinned, "unpinned_volumes": free}
    warnings = []
    for side, row in out.items():
        if row["pinned_ev100"]:
            warnings.append("AE_PINNED_%s: EV100 %r (min == max): the spot CANNOT drive auto-exposure down here; the "
                            "background darkens only relative to the spot under this fixed exposure" % (side.upper(), row["pinned_ev100"]))
    h, m = out.get("hangar", {}).get("pinned_ev100", []), out.get("mouth", {}).get("pinned_ev100", [])
    if h and m and h != m:
        gains = sorted({round(2.0 ** (eh - em), 4) for eh in h for em in m})
        warnings.append("EXPOSURE_MISMATCH: hangar camera EV100 %r vs mouth %r; which volume governs at equal priority "
                        "is UNCLEAR [inf]; hangar_gain candidates %r (pixel ~ L / 2^EV100 [inf]); left at 1.0 for Gary"
                        % (h, m, gains))
    return out, warnings


# =====================================================================================================================
# Pure gates and snapshot model
# =====================================================================================================================

def confirm_ok(mode, n, confirm):
    return mode in MODES and str(confirm or "").strip() == "%s I%d" % (mode, n)


def preflight_refusals(mode, n, state):
    """state: pie, sequencer_open, world_ok, census (dict), zz, sleight_record (dict|None), sleight_drift (list|None),
    spot_record (dict|None), confirm."""
    r = []
    if mode not in MODES:
        r.append("MODE_UNKNOWN: %r" % mode)
    if n not in CS["SEQS"]:
        r.append("INTERACTION_NOT_SET: %r" % n)
    if not confirm_ok(mode, n, state.get("confirm")):
        r.append("CONFIRM_MISMATCH: want %r, got %r" % ("%s I%d" % (mode, n), state.get("confirm")))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE: refuse (never end PIE)")
    if not state.get("world_ok", False):
        r.append("WRONG_WORLD")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN: an open Sequencer evaluates and dirties the map")
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if state.get("zz"):
        r.append("ZZ_ACTORS_PRESENT")
    sr = state.get("sleight_record")
    if not sr or not sr.get("applied") or int(sr.get("interaction", -1)) != n or sr.get("world") != CS["EXPECTED_WORLD"]:
        r.append("SLEIGHT_NOT_APPLIED: curtain_sleight_record_I%d.json missing or not applied" % n)
    spot = state.get("spot_record")
    if mode in ("DRY", "APPLY"):
        if spot is not None:
            r.append("RECORD_EXISTS: shadow_play_spot_record_I%d.json (applied=%s); REVERT first or inspect"
                     % (n, spot.get("applied")))
        elif state.get("sleight_drift"):
            r.append("SLEIGHT_DRIFTED: the Interaction differs from the sleight record's snapshot_after %r"
                     % state["sleight_drift"])
    if mode == "REVERT" and (spot is None or not spot.get("applied") or int(spot.get("interaction", -1)) != n):
        r.append("NOTHING_TO_REVERT: no applied shadow_play_spot_record_I%d.json" % n)
    return r


def apply_model(snap, plan, guids):
    """The snapshot APPLY must produce: the sleight's snapshot + two spawnables, each with exactly ONE spawn track
    (UE's auto-created one, reused), one transform track and one Intensity float track. Range unchanged."""
    out = copy.deepcopy(snap)
    span = [0, int(plan["end"]) + 1]                           # curtain_sleight section convention (:1530, :1574)
    for side in SIDES:
        name = SPOT_NAMES[side]
        out["bindings"].append({"name": name, "guid": guids[name], "parent": "",
                                "tracks": [{"class": "MovieSceneSpawnTrack", "name": "", "sections": [list(span)]},
                                           {"class": "MovieScene3DTransformTrack", "name": TRACK_NAME, "sections": [list(span)]},
                                           {"class": "MovieSceneFloatTrack", "name": TRACK_NAME, "sections": [list(span)]}]})
    return CS["normalize_snapshot"](out)


def revert_model(snap_after, created_guids):
    out = copy.deepcopy(snap_after)
    out["bindings"] = [b for b in out["bindings"] if b["guid"] not in set(created_guids)]
    return CS["normalize_snapshot"](out)


def revert_gate(live_snapshot, record):
    """REVERT refuses on drift: the live snapshot must equal what APPLY saved."""
    drift = CS["snapshot_diff"](CS["normalize_snapshot"](live_snapshot), record["snapshot_after"])
    return ["STATE_DRIFTED_SINCE_APPLY: %r (restore from %s instead)" % (drift, record.get("backup"))] if drift else []


def revert_exact(after_revert, record):
    diff = CS["snapshot_diff"](CS["normalize_snapshot"](after_revert), record["snapshot_before"])
    return ["REVERT_NOT_EXACT: %r" % diff] if diff else []


def range_readback(before, after):
    return [] if list(before) == list(after) else ["RANGE_CHANGED: playback %r -> %r" % (list(before), list(after))]


def spawn_track_count_failures(tracks, label):
    """Exactly ONE spawn track with exactly ONE section (5 Oct: a second, tool-added spawn track made
    PRESAVE_SNAPSHOT_MISMATCH on I1 [meas, curtain_sleight.py:1565-1566])."""
    st = [t for t in tracks if t.get_class().get_name() == "MovieSceneSpawnTrack"]
    if len(st) != 1:
        return ["SPAWN_TRACK_COUNT: %s has %d spawn tracks" % (label, len(st))]
    if len(list(st[0].get_sections())) != 1:
        return ["SPAWN_SECTION_COUNT: %s spawn track has %d sections" % (label, len(list(st[0].get_sections())))]
    return []


def keys_match(read, want, tol_rel=1.0e-4, label=""):
    """read/want: [(frame, value)] ; frames exact, values within tol (relative, min 1e-3 absolute)."""
    if [int(f) for f, _ in read] != [int(f) for f, _ in want]:
        return ["KEYS_%s: frames %r vs plan %r" % (label, [f for f, _ in read], [f for f, _ in want])]
    for (f, a), (_, b) in zip(read, want):
        if isinstance(b, bool):
            if bool(a) != b:
                return ["KEYS_%s: frame %d %r vs %r" % (label, f, a, b)]
        elif abs(float(a) - float(b)) > max(1.0e-3, tol_rel * abs(float(b))):
            return ["KEYS_%s: frame %d %.4f vs %.4f" % (label, f, a, b)]
    return []


def build_report(record, doors, params, live_inputs=None, ppv_rows=None):
    rec_inputs = inputs_from_record(record, doors)
    inputs = live_inputs or rec_inputs
    refusals, warnings = [], []
    if live_inputs is not None:
        refusals.extend(compare_live(rec_inputs, live_inputs))
    plan = None
    try:
        plan = plan_spot(inputs, params)
    except PlanError as exc:
        refusals.append("PLAN_REFUSED: %s" % exc)
    if plan is not None:
        refusals.extend("CHECK: " + t for t in check_spot(plan, inputs))
    if ppv_rows is not None:
        expo, w = exposure_summary(ppv_rows)
        warnings.extend(w)
    else:
        expo = None
    legacy = [m for m in inputs["markers"] if m[0] in LEGACY_MARKERS]
    if legacy:
        warnings.append("LEGACY_MARKERS: %r are from the old 20 s interaction (BoyCat window 75-375, "
                        "Docs/InfinityStageAuthoringReference.md:264) and were not re-timed by the sleight; the live "
                        "shadow-play window is CST play start -> CST drop" % legacy)
    warnings.append("INTENSITY_PATH_UNMEASURED: Intensity is keyed on the spawnable ACTOR binding with property path "
                    "'<SpotLightComponent name>.Intensity' (precedent Saved/CodexCueing/m4_capture_probe.py:74, "
                    "written, never evaluated). The template carries the peak, so if the path does not evaluate the "
                    "spot is simply ON for its spawn window. First PIE stills must show it OFF at play start - 10")
    warnings.append("HANGAR_DIM_SKIPPED: the hangar's own lights are already keyed to 0 by the sleight's fold "
                    "placeholder (S<n> Ghost Light, record plan.lights); a second Intensity track on that binding would "
                    "fight it and break curtain_sleight REVERT's drift gate. P(n+1) wing lamps reaching the mouth curtain "
                    "are Show lamps (Light Drama writes them after Sequencer, guide 3.2(d)); dim them by hand via the tag "
                    "binding (guide 3.4 step 3) if the stills need it")
    warnings.append("STACK_ORDER: after APPLY, revert THIS tool before curtain_sleight REVERT (its drift gate compares "
                    "the whole Interaction with its snapshot_after and will refuse while these spots exist)")
    warnings.append("INTENSITY_FOR_GARY: %.0f cd = %.1fx the lantern's %.3f lux at the aim point (ratio_to_lantern, "
                    "inferred, creative)" % (plan["photometry"]["peak_cd"], plan["photometry"]["ratio"],
                                              plan["photometry"]["lantern_lux"]) if plan else "INTENSITY_FOR_GARY: no plan")
    report = {"refusals": refusals, "warnings": warnings, "apply_ready": not refusals, "plan": plan,
              "plan_digest": plan["digest"] if plan else None, "exposure": expo,
              "inputs_digest": digest(inputs), "record_inputs_digest": digest(rec_inputs),
              "sleight_lib_sha256": CS["SOURCE_SHA256"]}
    return report


# =====================================================================================================================
# Unreal side. NEVER RUN YET. Every call's tier is in API_TABLE (printed by DRY).
# =====================================================================================================================

API_TABLE = [
    ("UnrealEditorSubsystem.get_game_world / get_editor_world", "prec", "curtain_sleight.py:2052-2057 (APPLY_OK 5 Oct)"),
    ("LevelSequenceEditorBlueprintLibrary.get_current_level_sequence", "prec", "curtain_sleight.py:2058"),
    ("EditorLoadingAndSavingUtils.get_dirty_*_packages (CS._census)", "prec", "curtain_sleight.py:1004-1006"),
    ("CS._snapshot (bindings/tracks/sections/cuts/markers)", "meas", "curtain_sleight_record_I1.json snapshot_after (5 Oct)"),
    ("channel.get_keys / key.get_time(DISPLAY_RATE) / key.get_value", "prec",
     "opening_sequence_apply.py:333, verify_walkin_opening.py:73-77; decl MovieSceneScriptingFloat.h:33,49"),
    ("section.get_all_channels + channel_name 'Location.X'", "prec", "curtain_sleight.py:1531 (APPLY_OK)"),
    ("binding.get_object_template + root relative_location/rotation", "prec", "curtain_sleight.py:1263-1269 (DRY 5 Oct)"),
    ("seq.add_spawnable_from_class(SpotLight)", "prec",
     "curtain_sleight.py:1759 GeometryCacheActor (APPLY_OK); SpotLight class: inf; decl deprecated-but-present "
     "MovieSceneSequenceExtensions.h:433-435"),
    ("template.spot_light_component", "prec", "curtain_sleight.py:1728 (on a level SpotLight); on a template: inf"),
    ("SpotLightComponent intensity_units/intensity/use_temperature/temperature/cones/radius/cast_shadows", "prec",
     "curtain_sleight.py:1729-1736; decl SpotLightComponent.h:22-27 (Degrees; half-angle: inf), LightComponentBase.h:36-37"),
    ("PointLightComponent source_radius / soft_source_radius", "inf", "decl PointLightComponent.h:45,52"),
    ("component mobility via set_editor_property on a template", "inf", "level instances use set_mobility (curtain_sleight.py:1729)"),
    ("CS._spawn_track (reuse UE's auto spawn track)", "meas", "curtain_sleight.py:1564-1579; fix measured 5 Oct"),
    ("CS._key_pose on a spawnable", "meas", "curtain_sleight.py:1779 hangar drape (APPLY_OK)"),
    ("MovieSceneFloatTrack path '<component>.Intensity' on an ACTOR binding", "inf",
     "written by Saved/CodexCueing/m4_capture_probe.py:74, never evaluated (MORNING_SUMMARY_2026-10-04.md:146); engine "
     "default tracks bind LightComponent0 as a COMPONENT binding (BaseEditorPerProjectUserSettings.ini:935)"),
    ("binding.remove()", "inf", "decl MovieSceneBindingExtensions.h:144; curtain_sleight REVERT never ran"),
    ("EditorAssetLibrary.save_asset(only_if_is_dirty)", "prec", "curtain_sleight.py:1864 (APPLY_OK)"),
    ("CS._ppv_rows", "meas", "curtain_sleight_I1_dry.json diagnostics (5 Oct 00:39)"),
]


def _stop(run, reason):
    unreal.log_error("SHADOW_PLAY_SPOT_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


CS["_stop"] = _stop                                        # CS helpers (_one, _key_pose, _key_float) stop with OUR marker


def _load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_synced(path, data, exclusive=False):
    """exclusive=True: O_EXCL create (fails if the record exists); else atomic replace. Always flushed + fsynced."""
    text = json.dumps(data, indent=1, sort_keys=True, default=str, ensure_ascii=False)
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


def _binding_by_guid(seq, guid):
    rows = [b for b in seq.get_bindings() if CS["_guid"](b.get_id()) == guid]
    return rows[0] if len(rows) == 1 else None


def _channel_keys(channel):
    unit = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    return sorted((int(k.get_time(time_unit=unit).frame_number.value), k.get_value()) for k in channel.get_keys())


def _transform_channels(binding, track_name, run):
    tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"
              and str(t.get_display_name()) == track_name]
    if len(tracks) != 1 or len(list(tracks[0].get_sections())) != 1:
        _stop(run, "TRANSFORM_TRACK_SHAPE|%s|tracks=%d" % (binding.get_display_name(), len(tracks)))
    return {str(c.channel_name): c for c in tracks[0].get_sections()[0].get_all_channels()}


def _pose_from_channels(ch, frame):
    ka = CS["key_at"]

    def val(name):
        keys = [(f, float(v)) for f, v in _channel_keys(ch[name])]
        return ka(keys, frame, 1) if keys else float(ch[name].get_default())

    return {"loc": [val("Location.X"), val("Location.Y"), val("Location.Z")], "pitch": val("Rotation.Y"),
            "yaw": val("Rotation.Z"), "roll": val("Rotation.X")}


def _live_inputs(n, record, doors, seq, run):
    """The sequence-derived planner inputs, re-read live (the pure compare_live() refuses on any difference)."""
    li = inputs_from_record(record, doors)
    li["start"], li["end"] = int(seq.get_playback_start()), int(seq.get_playback_end())
    li["markers"] = CS["_read_markers"](seq)
    try:
        li["beats"], li["go"] = beats_from_markers(li["markers"])
    except PlanError as exc:
        _stop(run, "BEATS|%s" % exc)
    drape = _binding_by_guid(seq, record["binding_guids"][HANGAR_DRAPE])
    if drape is None or str(drape.get_display_name()) != HANGAR_DRAPE:
        _stop(run, "HANGAR_DRAPE_BINDING_MISSING")
    ch = _transform_channels(drape, SLEIGHT_TRACK_NAME, run)
    li["hangar_drape_at"] = {k: _pose_from_channels(ch, li["beats"][k]) for k in ("play0", "sleight", "strike")}
    mouths = [b for b in seq.get_bindings() if str(b.get_display_name()) == CS["MOUTH_DRAPE"]]
    if len(mouths) != 1:
        _stop(run, "MOUTH_DRAPE_COUNT|%d" % len(mouths))
    troot = mouths[0].get_object_template().get_editor_property("root_component")
    tl, tr = troot.get_editor_property("relative_location"), troot.get_editor_property("relative_rotation")
    li["mouth_drape"] = {"loc": [float(tl.x), float(tl.y), float(tl.z)], "yaw": float(tr.yaw), "pitch": float(tr.pitch)}
    root = CS["_one"](CS["_by_label"](CS["_actors"]()), CS["ROOT_LABEL"] % n, run)
    rl, rr = root.get_actor_location(), root.get_actor_rotation()
    li["root_live"] = {"loc": [float(rl.x), float(rl.y), float(rl.z)], "yaw": float(rr.yaw), "pitch": float(rr.pitch)}
    return li


def _diagnostics(plan, inputs, seq):
    actors = CS["_actors"]()
    cam = inputs["cam_rel"]["loc"]
    hcam = to_world(frame_of_pose(inputs["hangar_drape_at"]["sleight"]), cam)
    mcam = to_world(inputs["mouth_drape"], cam)
    ppv = {"hangar": CS["_ppv_rows"](actors, hcam), "mouth": CS["_ppv_rows"](actors, mcam)}
    bound = {str(b.get_display_name()) for b in seq.get_bindings()}
    near = {}
    for side in SIDES:
        centre = plan["spots"][side]["aim_world"] if plan else None
        rows = []
        for a in actors if centre else []:
            if not isinstance(a, unreal.Light):
                continue
            comp = a.get_component_by_class(unreal.LightComponent)
            try:
                radius = float(comp.get_editor_property("attenuation_radius"))
            except Exception:  # noqa: BLE001 - directional/sky lights have no radius: listed separately
                rows.append({"label": str(a.get_actor_label()), "intensity": float(comp.get_editor_property("intensity")),
                             "radius": None, "bound_in_interaction": str(a.get_actor_label()) in bound})
                continue
            loc = a.get_actor_location()
            dist = math.dist([loc.x, loc.y, loc.z], centre)
            if dist <= radius:
                rows.append({"label": str(a.get_actor_label()), "intensity": float(comp.get_editor_property("intensity")),
                             "distance_cm": round(dist, 1), "lux_if_cd_and_aimed": round(
                                 float(comp.get_editor_property("intensity")) / max(1.0e-6, (dist / 100.0) ** 2), 4),
                             "bound_in_interaction": str(a.get_actor_label()) in bound})
        near[side] = rows
        if plan:                                   # conservative world-AABB slab test (curtain_sleight _segment_hits)
            sp = plan["spots"][side]
            stop_short = to_world(sp["drape_frame"], [plan["aim_rel"][0] - 100.0, 0.0, plan["aim_rel"][2]])
            near[side + "_beam_occluders"], near[side + "_beam_unchecked"] = CS["_segment_hits"](
                actors, sp["world"]["loc"], stop_short, set())
    return ppv, near


def _api_probe():
    return {"LevelSequence.add_spawnable_from_class": hasattr(unreal.LevelSequence, "add_spawnable_from_class"),
            "SpotLight": hasattr(unreal, "SpotLight"), "SpotLightComponent": hasattr(unreal, "SpotLightComponent"),
            "MovieSceneBindingProxy.remove": hasattr(unreal.MovieSceneBindingProxy, "remove"),
            "LightUnits.CANDELAS": hasattr(unreal, "LightUnits") and hasattr(unreal.LightUnits, "CANDELAS")}


def _context(n, run, mode, confirm):
    here = _here()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    sleight = _load_json(os.path.join(here, SLEIGHT_RECORD % n))
    spot = _load_json(os.path.join(here, RECORD_PATTERN % n))
    state = {"pie": editor.get_game_world() is not None,
             "world_ok": world is not None and str(world.get_outermost().get_name()) == CS["EXPECTED_WORLD"],
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": CS["_census"](), "zz": any(str(a.get_actor_label()).startswith("ZZ_") for a in CS["_actors"]()),
             "sleight_record": sleight, "spot_record": spot, "confirm": confirm}
    seq = None
    if sleight and sleight.get("applied") and not state["pie"] and state["world_ok"]:
        seq = unreal.load_asset(sleight["sequence"])
        if seq is None:
            _stop(run, "SEQUENCE_LOAD|%s" % sleight["sequence"])
        if mode != "REVERT":
            state["sleight_drift"] = CS["snapshot_diff"](CS["_snapshot"](seq, n), sleight["snapshot_after"])
    refusals = preflight_refusals(mode, n, state)
    if refusals:
        _stop(run, "REFUSED|" + " || ".join(refusals))
    doors = _load_json(os.path.join(here, CS["DOORS_RECORD"]))
    if not doors or doors.get("world") != CS["EXPECTED_WORLD"] or not doors.get("applied"):
        _stop(run, "DOORS_RECORD_CONTEXT")
    return here, sleight, spot, doors, seq


def run_dry(n, run, params, confirm):
    here, sleight, _, doors, seq = _context(n, run, "DRY", confirm)
    live = _live_inputs(n, sleight, doors, seq, run)
    rep0 = build_report(sleight, doors, params, live_inputs=live)
    ppv, near = _diagnostics(rep0["plan"], live, seq)
    report = build_report(sleight, doors, params, live_inputs=live, ppv_rows=ppv)
    for side in SIDES:
        if near.get(side + "_beam_occluders"):
            report["warnings"].append("BEAM_MAY_BE_OCCLUDED_%s (world AABB, conservative): %r"
                                      % (side.upper(), near[side + "_beam_occluders"]))
    report.update({"lights_reaching_aim": near, "api_table": [{"call": c, "tier": t, "cite": s} for c, t, s in API_TABLE],
                   "api_probe": _api_probe(), "live_inputs": live, "interaction": n, "run": run,
                   "sequence": sleight["sequence"]})
    out = os.path.join(here, DRY_PATTERN % n)
    _write_synced(out, report)
    if report["plan"] is not None:
        _write_synced(os.path.join(here, PLAN_PATTERN % n),
                      {"interaction": n, "run": run, "plan_digest": report["plan_digest"], "params": params,
                       "sleight_run": sleight.get("run"), "inputs_digest": report["inputs_digest"]})
    for row in API_TABLE:
        if row[1] == "inf":
            unreal.log("SHADOW_PLAY_SPOT_API_INFERRED|run=%s|%s|%s" % (run, row[0], row[2]))
    unreal.log("SHADOW_PLAY_SPOT_API_PROBE|run=%s|%s" % (run, json.dumps(report["api_probe"], sort_keys=True)))
    for text in report["refusals"]:
        unreal.log_warning("SHADOW_PLAY_SPOT_REFUSAL|run=%s|%s" % (run, text))
    for text in report["warnings"]:
        unreal.log("SHADOW_PLAY_SPOT_WARNING|run=%s|%s" % (run, text))
    if CS["_census"]() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(CS["_census"]()))
    plan = report["plan"] or {}
    unreal.log("SHADOW_PLAY_SPOT_DRY_OK|run=%s|interaction=%d|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|"
               "peak_cd=%s|outer_deg=%s|up=%s|hangar_off=%s|mouth_fade=%s|range=[%s,%s]|digest=%s|report=%s"
               % (run, n, int(report["apply_ready"]), len(report["refusals"]), len(report["warnings"]),
                  (plan.get("photometry") or {}).get("peak_cd"), (plan.get("cone") or {}).get("outer_deg"),
                  plan.get("up"), (plan.get("beats") or {}).get("strike"), plan.get("fade_out"),
                  live["start"], live["end"], report["plan_digest"], out))


def _make_spot(seq, sp, plan, run):
    b = seq.add_spawnable_from_class(unreal.SpotLight)
    if b is None or not b.is_valid():
        _stop(run, "SPAWNABLE_FAILED|%s|NOTHING SAVED; Don't-Save restart" % sp["name"])
    b.set_display_name(sp["name"])
    tmpl = b.get_object_template()
    comp = tmpl.get_editor_property("spot_light_component")
    if comp is None:
        _stop(run, "TEMPLATE_HAS_NO_SPOT_COMPONENT|%s|NOTHING SAVED; Don't-Save restart" % sp["name"])
    root = tmpl.get_editor_property("root_component")
    w = sp["world"]
    root.set_editor_property("relative_location", unreal.Vector(*w["loc"]))
    root.set_editor_property("relative_rotation", unreal.Rotator(roll=0.0, pitch=w["pitch"], yaw=w["yaw"]))
    lt, cone = plan["light"], plan["cone"]
    comp.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    comp.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
    comp.set_editor_property("intensity", float(sp["peak_cd"]))        # fallback if the keyed path does not evaluate
    comp.set_editor_property("use_temperature", True)
    comp.set_editor_property("temperature", float(lt["kelvin"]))
    comp.set_editor_property("outer_cone_angle", float(cone["outer_deg"]))
    comp.set_editor_property("inner_cone_angle", float(cone["inner_deg"]))
    comp.set_editor_property("attenuation_radius", float(lt["attenuation_radius_cm"]))
    comp.set_editor_property("source_radius", float(lt["source_radius_cm"]))
    comp.set_editor_property("soft_source_radius", 0.0)
    comp.set_editor_property("cast_shadows", True)
    CS["_spawn_track"](b, sp["spawn"], plan["end"])                     # reuses UE's auto-created spawn track
    bad = spawn_track_count_failures(b.get_tracks(), sp["name"])
    if bad:
        _stop(run, "%s|NOTHING SAVED; Don't-Save restart" % bad[0])
    CS["_key_pose"](b, sp["transform_keys"], plan["end"], run, sp["name"])
    CS["_key_float"](b, "Intensity", "%s.Intensity" % comp.get_name(), sp["intensity_keys"], plan["end"], run, sp["name"])
    return b, comp.get_name()


def _verify_spot(seq, guid, sp, plan, run):
    """Asserted read-back of one spot binding (keys, spawn, template). Returns failures."""
    out = []
    b = _binding_by_guid(seq, guid)
    if b is None or str(b.get_display_name()) != sp["name"]:
        return ["BINDING_MISSING: %s" % sp["name"]]
    tracks = list(b.get_tracks())
    out.extend(spawn_track_count_failures(tracks, sp["name"]))
    st = [t for t in tracks if t.get_class().get_name() == "MovieSceneSpawnTrack"]
    if st:
        out.extend(keys_match(_channel_keys(st[0].get_sections()[0].get_all_channels()[0]),
                              [(f, bool(v)) for f, v in sp["spawn"]], label="SPAWN_" + sp["name"]))
    ft = [t for t in tracks if t.get_class().get_name() == "MovieSceneFloatTrack"]
    if len(ft) != 1 or str(ft[0].get_property_name()) != "Intensity":
        out.append("INTENSITY_TRACK: %s float tracks %d" % (sp["name"], len(ft)))
    else:
        out.extend(keys_match(_channel_keys(ft[0].get_sections()[0].get_all_channels()[0]), sp["intensity_keys"],
                              label="INTENSITY_" + sp["name"]))
    ch = _transform_channels(b, TRACK_NAME, run)
    for name, idx in CS["POSE_CHANNELS"].items():
        out.extend(keys_match([(f, float(v)) for f, v in _channel_keys(ch[name])],
                              [(k[0], k[idx]) for k in sp["transform_keys"]], tol_rel=1.0e-6, label=name + "_" + sp["name"]))
    comp = b.get_object_template().get_editor_property("spot_light_component")
    want = {"intensity": sp["peak_cd"], "outer_cone_angle": plan["cone"]["outer_deg"],
            "inner_cone_angle": plan["cone"]["inner_deg"], "attenuation_radius": plan["light"]["attenuation_radius_cm"],
            "temperature": plan["light"]["kelvin"]}
    for prop, value in want.items():
        got = float(comp.get_editor_property(prop))
        if abs(got - float(value)) > 1.0e-3 * max(1.0, abs(float(value))):
            out.append("TEMPLATE_%s: %s %.4f vs %.4f" % (sp["name"], prop, got, value))
    if not bool(comp.get_editor_property("cast_shadows")):
        out.append("TEMPLATE_%s: cast_shadows off" % sp["name"])
    if comp.get_editor_property("intensity_units") != unreal.LightUnits.CANDELAS:
        out.append("TEMPLATE_%s: units %s" % (sp["name"], comp.get_editor_property("intensity_units")))
    if comp.get_editor_property("mobility") != unreal.ComponentMobility.MOVABLE:
        out.append("TEMPLATE_%s: mobility %s" % (sp["name"], comp.get_editor_property("mobility")))
    return out


def run_apply(n, run, params, confirm):
    here, sleight, _, doors, seq = _context(n, run, "APPLY", confirm)
    live = _live_inputs(n, sleight, doors, seq, run)
    report = build_report(sleight, doors, params, live_inputs=live)
    if report["refusals"]:
        _stop(run, "REFUSED|" + " || ".join(report["refusals"]))
    plan = report["plan"]
    pf = _load_json(os.path.join(here, PLAN_PATTERN % n)) or {}
    if pf.get("plan_digest") != plan["digest"] or pf.get("sleight_run") != sleight.get("run"):
        _stop(run, "PLAN_CHANGED_SINCE_DRY|dry=%s|now=%s|rerun DRY" % (pf.get("plan_digest"), plan["digest"]))
    seq_path = sleight["sequence"]

    # 0. backup (the sequence only: the only package this tool writes), then the exclusive record, BEFORE mutating
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreShadowPlaySpot-I%d-%s" % (n, run))
    os.makedirs(backup, exist_ok=False)
    src = CS["_content_file"](seq_path)
    dst = os.path.join(backup, os.path.basename(src))
    shutil.copy2(src, dst)
    if os.path.getsize(dst) != os.path.getsize(src):
        _stop(run, "BACKUP_SIZE_MISMATCH|" + src)
    snap0 = CS["_snapshot"](seq, n)
    range0 = [int(seq.get_playback_start()), int(seq.get_playback_end())]
    record_path = os.path.join(here, RECORD_PATTERN % n)
    record = {"schema_version": 1, "run": run, "interaction": n, "sequence": seq_path, "world": CS["EXPECTED_WORLD"],
              "applied": False, "backup": backup, "backup_files": [dst], "plan": plan, "plan_digest": plan["digest"],
              "snapshot_before": snap0, "range_before": range0, "sleight_run": sleight.get("run"),
              "sleight_plan_digest": sleight.get("plan_digest"), "params": params}
    try:
        _write_synced(record_path, record, exclusive=True)
    except FileExistsError:
        _stop(run, "RECORD_EXISTS|%s|nothing mutated" % record_path)

    # 1. mutate: two spawnables
    seq.modify()
    created, comp_names = {}, {}
    for side in SIDES:
        sp = plan["spots"][side]
        b, cname = _make_spot(seq, sp, plan, run)
        created[sp["name"]], comp_names[sp["name"]] = CS["_guid"](b.get_id()), cname
    record.update({"binding_guids": created, "created_binding_guids": sorted(created.values()),
                   "component_names": comp_names})
    _write_synced(record_path, record)

    # 2. read-back BEFORE save (asserted)
    problems = range_readback(range0, [int(seq.get_playback_start()), int(seq.get_playback_end())])
    expected = apply_model(snap0, plan, created)
    diff = CS["snapshot_diff"](CS["_snapshot"](seq, n), expected)
    if diff:
        problems.append("PRESAVE_SNAPSHOT_MISMATCH %r" % diff)
    for side in SIDES:
        sp = plan["spots"][side]
        problems.extend(_verify_spot(seq, created[sp["name"]], sp, plan, run))
    census = CS["_census"]()
    if census != {"content": [seq_path], "maps": []}:
        problems.append("UNEXPECTED_DIRTY %s" % json.dumps(census))
    if problems:
        _stop(run, "PRESAVE_READBACK|%r|NOTHING SAVED; Don't-Save restart; record %s stays applied=false"
              % (problems, record_path))

    # 3. narrow save: the sequence asset ONLY
    if not bool(unreal.EditorAssetLibrary.save_asset(seq_path, only_if_is_dirty=True)):
        _stop(run, "SAVE_FAILED|%s" % seq_path)

    # 4. read-back after save (asserted)
    problems = []
    if CS["_census"]() != {"content": [], "maps": []}:
        problems.append("dirty after save %r" % CS["_census"]())
    seq = unreal.load_asset(seq_path)
    snap1 = CS["_snapshot"](seq, n)
    diff = CS["snapshot_diff"](snap1, expected)
    if diff:
        problems.append("snapshot %r" % diff)
    problems.extend(range_readback(range0, [int(seq.get_playback_start()), int(seq.get_playback_end())]))
    for side in SIDES:
        sp = plan["spots"][side]
        problems.extend(_verify_spot(seq, created[sp["name"]], sp, plan, run))
    if problems:
        _stop(run, "READBACK_FAILED_AFTER_SAVE|%r|restore from %s" % (problems, backup))
    record.update({"applied": True, "snapshot_after": snap1})
    _write_synced(record_path, record)
    unreal.log("SHADOW_PLAY_SPOT_APPLY_OK|run=%s|interaction=%d|peak_cd=%.1f|hangar_gain=%.3f|outer_deg=%.3f|"
               "up=%d-%d|hangar_off=%d|mouth_fade=%d-%d|range=[%d,%d]|saved=%s|backup=%s|record=%s"
               % (run, n, plan["photometry"]["peak_cd"], plan["photometry"]["hangar_gain"], plan["cone"]["outer_deg"],
                  plan["up"][0], plan["up"][1], plan["beats"]["strike"] + 1, plan["fade_out"][0], plan["fade_out"][1],
                  range0[0], range0[1], seq_path, backup, record_path))


def run_revert(n, run, confirm):
    here, _, record, _, seq = _context(n, run, "REVERT", confirm)
    if record.get("world") != CS["EXPECTED_WORLD"] or record.get("sequence") is None:
        _stop(run, "REVERT_RECORD_CONTEXT")
    seq = unreal.load_asset(record["sequence"])
    bad = revert_gate(CS["_snapshot"](seq, n), record)
    if bad:
        _stop(run, bad[0])
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreShadowPlaySpot-I%d-%s-revert" % (n, run))
    os.makedirs(backup, exist_ok=False)
    src = CS["_content_file"](record["sequence"])
    shutil.copy2(src, os.path.join(backup, os.path.basename(src)))
    range0 = [int(seq.get_playback_start()), int(seq.get_playback_end())]
    seq.modify()
    for name, guid in sorted(record["binding_guids"].items()):
        b = _binding_by_guid(seq, guid)
        if b is None:
            _stop(run, "REVERT_BINDING_GONE|%s|NOTHING SAVED; Don't-Save restart" % name)
        b.remove()                                                       # [inf] see API_TABLE
    left = [g for g in record["created_binding_guids"] if _binding_by_guid(seq, g) is not None]
    if left:
        _stop(run, "BINDINGS_SURVIVED|%r|NOTHING SAVED; Don't-Save restart" % left)
    problems = revert_exact(CS["_snapshot"](seq, n), record)
    problems.extend(range_readback(range0, [int(seq.get_playback_start()), int(seq.get_playback_end())]))
    problems.extend(range_readback(record["range_before"], range0))
    if CS["_census"]() != {"content": [record["sequence"]], "maps": []}:
        problems.append("UNEXPECTED_DIRTY %s" % json.dumps(CS["_census"]()))
    if problems:
        _stop(run, "REVERT_PRESAVE|%r|NOTHING SAVED; Don't-Save restart" % problems)
    if not bool(unreal.EditorAssetLibrary.save_asset(record["sequence"], only_if_is_dirty=True)):
        _stop(run, "SAVE_FAILED|%s" % record["sequence"])
    seq = unreal.load_asset(record["sequence"])
    problems = revert_exact(CS["_snapshot"](seq, n), record)
    if CS["_census"]() != {"content": [], "maps": []}:
        problems.append("dirty after save %r" % CS["_census"]())
    if problems:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (problems, record["backup"]))
    record_path = os.path.join(here, RECORD_PATTERN % n)
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("SHADOW_PLAY_SPOT_REVERT_OK|run=%s|interaction=%d|removed=%d|range=[%d,%d]|backup=%s|record=%s"
               % (run, n, len(record["created_binding_guids"]), range0[0], range0[1], backup, archived))


def main():
    g = globals()
    run = str(g.get("SHADOW_PLAY_SPOT_RUN_ID") or datetime.datetime.now().strftime("SPS-%Y%m%d-%H%M%S"))
    n = int(g.get("SHADOW_PLAY_SPOT_INTERACTION", 0))
    mode = str(g.get("SHADOW_PLAY_SPOT_MODE", "DRY")).upper()
    confirm = g.get("SHADOW_PLAY_SPOT_CONFIRM")
    params = dict(g.get("SHADOW_PLAY_SPOT_PARAMS") or {})
    if not confirm_ok(mode, n, confirm):
        _stop(run, "CONFIRM_MISMATCH|want '%s I%s'|got %r" % (mode, n, confirm))
    try:
        merged_params(params)
        if mode == "DRY":
            run_dry(n, run, params, confirm)
        elif mode == "APPLY":
            run_apply(n, run, params, confirm)
        else:
            run_revert(n, run, confirm)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
