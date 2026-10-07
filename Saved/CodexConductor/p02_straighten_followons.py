"""P02 STRAIGHTEN FOLLOW-ONS: re-place what was composed against P02's OLD curved route (7 Oct, offline-written,
NEVER RUN IN UNREAL). The ROUTE_ACTORS follow-on of p02_straighten.py (FOLLOWON_TEXT, p02_straighten.py:80-81), plus
the I1 curtain-sleight keys that sit at P02's old mouth. MATCH_HANDOFFS stays its own run (match_scene*_handoff.py).
Runbook: P02_STRAIGHTEN_RUNBOOK.md. Harness: test_p02_straighten_followons_offline.py (system Python).

Tiers per claim: [decl] read in a file/header we can cite, [prec] in-repo precedent call (cited), [meas] an earlier
run's read-back (cited), [inf] inferred (why).

MODEL. Every route actor is expressed in the frame of P02's route at a STATION distance s (planar frame: position +
yaw; the route is flat, z = 0 local, every recorded point rot pitch/roll 0 [meas p02_straighten_dry_P02STR-20261006-
014311.json "spline"]), BEFORE the straighten (CAPTURE samples the OLD spline), and re-expressed at the same s on the
NEW route after it: new = F_new(s) * inverse(F_old(s)) * old. A yaw-only frame change pre-multiplies the rotator by
Rz(dyaw), so roll/pitch/scale are unchanged and yaw adds dyaw [inf: UE rotators compose yaw last, R = Rz*Ry*Rx].
Station s per POLICY:
  MOUTH    s = 0. The actor was composed against the route START frame: the stalls camera ("seated exactly as the
           Opening stalls camera sits relative to Passage 1's route start", place_transition_stalls.py:7-9 [decl]),
           the mouth lantern ("the mouth's own frame (the route's start transform)", mouth_lanterns_apply.py:5-6
           [decl]), the I1 sleight camera (pose relative to the mouth drape, curtain_sleight.py:472-473 [decl]),
           whose drape stands at route distance 0 (fit_transition_drapes.py:64-70 [decl]). All four sit BEHIND the
           mouth (local x < 0), so their nearest s is 0 anyway [inf from recorded positions; CAPTURE measures].
  STATION  s = nearest route distance, clamped to [0, compiled length]. The car light: placed in the route frame at
           spline_length * 14.5/23 (place_p02_car_light.py:56-61 [decl]).
  STAY     not moved: "S2 Pit Liner Near Wall" is the S2 hangar's own liner, laid in S2's DOCK frame
           (landscape_floors_apply.py:7-10, 77-86 [decl]) and anchor DOCK keeps the dock (p02_straighten DRY
           dock_delta.DOCK = 0 [meas]).
  HANDOFF  not moved, reported: Scene 2's Entry/Exit Handoff Cameras belong to MATCH_HANDOFFS (the builder re-takes
           them, InfinityStageCameraPilotLibrary.h:115-120 [decl]).
Under anchor DOCK the end frame is kept, so STATION actors near the dock barely move, MOUTH actors move rigidly with
the mouth (97 m, -66.5 deg [meas DRY start_delta.DOCK]).

SEQUENCE KEYS (LS_Interaction_01_WashingTheBoy), all MOUTH-station, rigid with the mouth:
  * "I1 Sleight Mouth Camera" 3D transform track "CurtainSleight (Conductor)": the sleight seat at frame 0 and the
    walk-in from the seat to Passage 2's start pose, ABSOLUTE world keys (curtain_sleight.py:556-562, 579 [decl];
    record curtain_sleight_record_I1.json: 485 keys, last = (0, 80000, 180) yaw 22.908 = P02's start view [meas]).
    Keys are LINEAR (curtain_sleight.py:1795-1797 [decl]) so a rigid map of the keys is a rigid map of the curve.
  * "Sleight Mouth Shadow Card" (spawnable) transform track: 2 absolute keys at the mouth (curtain_sleight.py:521-523).
  * "Transition Drape (baked)" (spawnable, NO transform track): its TEMPLATE root relative transform is the mouth
    frame (fit_transition_drapes.py:131-136 [decl], read the same way by curtain_sleight.py:1518-1524).
  Untouched, recorded: the S1 hangar side (S1 Sleight Hangar Camera / Sleight Hangar Drape / Sleight Hangar Shadow
  Card: S1's hangar does not move), lens float tracks, and every non-transform track.
  Why not re-run curtain_sleight REVERT/APPLY: the mouth frame it reads is the drape TEMPLATE (curtain_sleight.py:1518)
  which only fit_transition_drapes.py writes, and that tool REMOVES every cut section (curtain_sleight.py:30-31
  [decl]); the re-run would also re-plan from live gates that have moved since 5 Oct. The rigid re-key keeps the
  approved shot bit-for-bit relative to the mouth. (A retime of P02 changes its start speed: the walk-in's end speed
  then needs a RE-PLAN, see the runbook; that is a creative re-plan, not this tool.)
Never called: GetBoundObjects (crashes on open ranges), any Sequencer UI, scrubbing/opening the Master, level reload.

Modes (p02_straighten_followons_args.json or P02FOLLOW_ARGS from the runner):
  CAPTURE  read-only, BEFORE p02_straighten APPLY: old spline snapshot + 10 cm samples, per actor its pose, nearest s,
           station, the OLD route frame at the station (Unreal's own), its local pose; the I1 keys/template; a
           sequence binding scan. Writes p02_straighten_followons_capture.json (exclusive). Marker
           P02_FOLLOWONS_CAPTURE_OK.
  DRY      reads the capture + the LIVE new route (after the straighten) and prints/writes the plan. Before the
           straighten it can predict from args "predicted_route_start" (the straighten DRY preds.DOCK.route.start).
           Marker P02_FOLLOWONS_DRY_OK.
  APPLY    confirm "APPLY P02FOLLOW". Gates (no PIE, census clean, Sequencer closed, no ZZ_, straighten record saved
           with anchor DOCK and its before-spline == the capture's, live route straight, nothing moved since CAPTURE)
           -> record (exclusive, fsynced) -> Backups/PreP02Followons-<run> (.umap + I1 .uasset) -> actors -> keys ->
           template -> walk end == P02 camera start view -> census == level + I1 only -> save those -> read back ->
           census clean -> P02_FOLLOWONS_APPLY_OK.
  REVERT   confirm "REVERT P02FOLLOW": live must equal the record's after (else DRIFT, nothing written); restores
           every recorded before value; same save/read-back chain; P02_FOLLOWONS_REVERT_OK. LIFO: run it BEFORE
           p02_straighten REVERT.
Failure: P02_FOLLOWONS_FAILED|run=..|reason (NOTHING SAVED; Don't-Save restart when anything was written).
"""
import datetime
import json
import math
import os
import re
import shutil

try:
    import unreal
except ImportError:  # offline harness
    unreal = None

HERE = "E:/PussStage/Saved/CodexConductor/"
ARGS_NAME = "p02_straighten_followons_args.json"
CAPTURE = HERE + "p02_straighten_followons_capture.json"
REC = HERE + "p02_straighten_followons_record.json"
STRAIGHT_REC = HERE + "p02_straighten_record.json"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
I1_SEQ = "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy"
I1_UASSET = "E:/PussStage/Content/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy.uasset"
PASSAGE_PREFIX = "Passage 02"
ROUTE_RADIUS_CM = 4000.0          # p02_straighten.py:75 (the scan that produced the ROUTE_ACTORS list)
SAMPLE_STEP_CM = 10.0
MOUTH_MAX_S_CM = 300.0            # a MOUTH actor whose nearest s exceeds this is reported (composition suspect)
TOL_CM, TOL_DEG = 0.5, 0.01
WALK_TOL_CM, WALK_TOL_DEG = 1.0, 0.05
TRACK = "CurtainSleight (Conductor)"   # curtain_sleight.py:90
POLICY = {
    "I1 Sleight Mouth Camera": "MOUTH",
    "Interaction 1 \u2014 Stalls Camera": "MOUTH",
    "S02 Mouth Lantern": "MOUTH",
    "P02 Car Light (trial, Gary to tune)": "STATION",
    "S2 Pit Liner Near Wall": "STAY",
    "Scene 2 \u2014 External Sound \u2014 Entry Handoff Camera": "HANDOFF",
    "Scene 2 \u2014 External Sound \u2014 Exit Handoff Camera": "HANDOFF",
}
SEQ_ITEMS = (("I1 Sleight Mouth Camera", "TRANSFORM_TRACK"),
             ("Sleight Mouth Shadow Card", "TRANSFORM_TRACK"),
             ("Transition Drape (baked)", "SPAWNABLE_TEMPLATE"))
SEQ_STAY = ("S1 Sleight Hangar Camera", "Sleight Hangar Drape", "Sleight Hangar Shadow Card")
MOVING = ("MOUTH", "STATION")
RUN = datetime.datetime.now().strftime("P02FOL-%Y%m%d-%H%M%S")


# ---------------------------------------------------------------- pure frame maths (harness-tested) ------------------
def wrap(deg):
    return (deg + 180.0) % 360.0 - 180.0


def _persistent_actors():
    """Only actors in the open persistent level. Klara's streamed levels (Japanese_Alley, L_Animals, L_KK_children)
    sit on/near the route and must never travel with P02 (measured 7 Oct: 198 'unclassified' route actors, all in
    /Game/Japanese_Alley/Maps/Japanese_Alley; probe_p02_unclassified_levels.py)."""
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    persistent = world.get_outermost().get_name()
    return [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if a.get_outermost().get_name() == persistent]


def xf(loc, yaw):
    return {"loc": [float(loc[0]), float(loc[1]), float(loc[2])], "yaw": float(yaw)}


def compose(parent, child):
    """parent * child for planar frames (yaw about Z, translation); z adds (p02_straighten.py:95-100)."""
    c, s = math.cos(math.radians(parent["yaw"])), math.sin(math.radians(parent["yaw"]))
    x, y, z = child["loc"]
    p = parent["loc"]
    return xf([p[0] + c * x - s * y, p[1] + s * x + c * y, p[2] + z], wrap(parent["yaw"] + child["yaw"]))


def straight_frame(start, s_cm):
    """Auto Fit's straight route: local (0,0,0) -> (L,0,0) (p02_straighten.py:118-125)."""
    return compose(start, xf([s_cm, 0.0, 0.0], 0.0))


def to_local(frame, loc):
    c, s = math.cos(math.radians(frame["yaw"])), math.sin(math.radians(frame["yaw"]))
    dx, dy = loc[0] - frame["loc"][0], loc[1] - frame["loc"][1]
    return [c * dx + s * dy, -s * dx + c * dy, loc[2] - frame["loc"][2]]


def from_local(frame, local):
    c, s = math.cos(math.radians(frame["yaw"])), math.sin(math.radians(frame["yaw"]))
    return [frame["loc"][0] + c * local[0] - s * local[1], frame["loc"][1] + s * local[0] + c * local[1],
            frame["loc"][2] + local[2]]


def dyaw(f_old, f_new):
    return wrap(f_new["yaw"] - f_old["yaw"])


def re_express_point(loc, f_old, f_new):
    return from_local(f_new, to_local(f_old, loc))


def re_express_pose(pose, f_old, f_new):
    """pose = {"loc": [x,y,z], "rot": [roll, pitch, yaw], "scale": [...]}; yaw is NOT wrapped (key continuity)."""
    out = json.loads(json.dumps(pose))
    out["loc"] = re_express_point(pose["loc"], f_old, f_new)
    out["rot"] = [pose["rot"][0], pose["rot"][1], pose["rot"][2] + dyaw(f_old, f_new)]
    return out


def pose_delta(a, b):
    return {"xy_cm": math.hypot(a["loc"][0] - b["loc"][0], a["loc"][1] - b["loc"][1]),
            "z_cm": a["loc"][2] - b["loc"][2], "yaw_deg": wrap(a["rot"][2] - b["rot"][2]),
            "roll_pitch_deg": max(abs(wrap(a["rot"][0] - b["rot"][0])), abs(wrap(a["rot"][1] - b["rot"][1])))}


def poses_equal(a, b, tol_cm=TOL_CM, tol_deg=TOL_DEG):
    d = pose_delta(a, b)
    return d["xy_cm"] <= tol_cm and abs(d["z_cm"]) <= tol_cm and abs(d["yaw_deg"]) <= tol_deg \
        and d["roll_pitch_deg"] <= tol_deg


def nearest_s(samples, p):
    """samples [[s, x, y], ...] ascending s along a polyline; p [x, y, ...]. XY projection onto every segment;
    returns (s, lateral_cm). Clamped to the sampled range by construction."""
    best = (float("inf"), 0.0)
    for (s0, x0, y0), (s1, x1, y1) in zip(samples, samples[1:]):
        dx, dy = x1 - x0, y1 - y0
        seg2 = dx * dx + dy * dy
        u = 0.0 if seg2 <= 0.0 else max(0.0, min(1.0, ((p[0] - x0) * dx + (p[1] - y0) * dy) / seg2))
        qx, qy = x0 + u * dx, y0 + u * dy
        d = math.hypot(p[0] - qx, p[1] - qy)
        if d < best[0]:
            best = (d, s0 + u * (s1 - s0))
    return best[1], best[0]


def station(policy, s_near, d_end):
    if policy == "MOUTH":
        return 0.0
    if policy == "STATION":
        return max(0.0, min(float(d_end), float(s_near)))
    return None


def channel_base(name):
    """'Location.Y_183' -> 'Location.Y' (memory ue58-sequencer-read-traps: channel names carry a numeric suffix)."""
    return re.sub(r"_\d+$", "", str(name))


def rekey(channels, f_old, f_new):
    """channels {"Location.X": [[frame, v], ...], ...}. X/Y mix under a yaw, so their key frames must be identical;
    Location.Z adds dz, Rotation.Z (yaw) adds dyaw UNWRAPPED (continuity), every other channel is untouched.
    Returns (new_channels, refusal or None)."""
    xs, ys = channels.get("Location.X") or [], channels.get("Location.Y") or []
    if not xs or not ys:
        return None, "NO_XY_KEYS"
    if [k[0] for k in xs] != [k[0] for k in ys]:
        return None, "XY_KEY_FRAMES_DIFFER"
    out = json.loads(json.dumps(channels))
    pts = [re_express_point([x[1], y[1], 0.0], f_old, f_new) for x, y in zip(xs, ys)]
    out["Location.X"] = [[k[0], p[0]] for k, p in zip(xs, pts)]
    out["Location.Y"] = [[k[0], p[1]] for k, p in zip(ys, pts)]
    dz = f_new["loc"][2] - f_old["loc"][2]
    if "Location.Z" in channels:
        out["Location.Z"] = [[k[0], k[1] + dz] for k in channels["Location.Z"]]
    if "Rotation.Z" in channels:
        dy = dyaw(f_old, f_new)
        out["Rotation.Z"] = [[k[0], k[1] + dy] for k in channels["Rotation.Z"]]
    return out, None


def channels_equal(a, b, tol=1.0e-4):
    if sorted(a) != sorted(b):
        return False
    for name in a:
        if len(a[name]) != len(b[name]):
            return False
        for p, q in zip(a[name], b[name]):
            if p[0] != q[0] or abs(p[1] - q[1]) > tol:
                return False
    return True


def key_pose(channels, i):
    g = lambda n, d=0.0: channels[n][i][1] if n in channels else d   # noqa: E731
    return {"loc": [g("Location.X"), g("Location.Y"), g("Location.Z")],
            "rot": [g("Rotation.X"), g("Rotation.Y"), g("Rotation.Z")], "scale": [1.0, 1.0, 1.0]}


def max_yaw_step(channels):
    ks = channels.get("Rotation.Z") or []
    return max((abs(b[1] - a[1]) for a, b in zip(ks, ks[1:])), default=0.0)


# ---------------------------------------------------------------- planning ---------------------------------------------
def plan(capture, new_frame_at):
    """capture: CAPTURE json. new_frame_at(s) -> planar frame on the NEW route. Returns the full plan as data."""
    d_end = float(capture["d_end_cm"])
    actors, warnings, refusals_ = [], [], []
    for label, row in sorted(capture["actors"].items()):
        pol = row["policy"]
        entry = {"label": label, "policy": pol, "nearest_s": row["nearest_s"], "lateral_cm": row["lateral_cm"],
                 "before": row["pose"]}
        if pol in MOVING:
            s = row["station_s"]
            f_old, f_new = row["old_frame"], new_frame_at(s)
            after = re_express_pose(row["pose"], f_old, f_new)
            after["rot"][2] = wrap(after["rot"][2])
            entry.update({"station_s": s, "old_frame": f_old, "new_frame": f_new, "after": after,
                          "move": pose_delta(after, row["pose"])})
            if pol == "MOUTH" and row["nearest_s"] > MOUTH_MAX_S_CM:
                warnings.append("MOUTH_ACTOR_FAR_FROM_MOUTH|%s|s=%.0f" % (label, row["nearest_s"]))
        else:
            entry.update({"station_s": None, "after": row["pose"], "move": None,
                          "why": "S2 hangar's own (DOCK keeps the dock)" if pol == "STAY"
                          else "MATCH_HANDOFFS owns it (match_scene1/2_handoff.py)"})
        actors.append(entry)
    seq = []
    mouth_old = capture["mouth_frame_old"]
    mouth_new = new_frame_at(0.0)
    for item in capture["sequence"]["items"]:
        e = {"binding": item["binding"], "kind": item["kind"], "station_s": 0.0}
        if item["kind"] == "TRANSFORM_TRACK":
            new, why = rekey(item["channels"], mouth_old, mouth_new)
            if why:
                refusals_.append("REKEY|%s|%s" % (item["binding"], why))
                continue
            e.update({"before": item["channels"], "after": new, "keys": len(item["channels"]["Location.X"]),
                      "yaw_step_before": max_yaw_step(item["channels"]), "yaw_step_after": max_yaw_step(new)})
        else:
            after = re_express_pose(item["pose"], mouth_old, mouth_new)
            after["rot"][2] = wrap(after["rot"][2])
            e.update({"before": item["pose"], "after": after})
        seq.append(e)
    cam = [s for s in seq if s["binding"] == "I1 Sleight Mouth Camera"]
    walk_end = key_pose(cam[0]["after"], -1) if cam else None
    if capture.get("unclassified"):
        refusals_.append("UNCLASSIFIED_ROUTE_ACTORS|" + ",".join(capture["unclassified"]))
    if capture.get("missing"):
        refusals_.append("POLICY_ACTORS_MISSING|" + ",".join(capture["missing"]))
    for b in capture["sequence"].get("foreign_transform_bindings", []):
        refusals_.append("UNHANDLED_TRANSFORM_BINDING|%s|%s" % (b["sequence"], b["binding"]))
    return {"d_end_cm": d_end, "mouth_old": mouth_old, "mouth_new": mouth_new, "actors": actors, "sequence": seq,
            "walk_end_planned": walk_end, "warnings": warnings, "refusals": refusals_}


def record_from_plan(p, run, backup):
    """APPLY record: every before/after value, plain numbers (REVERT uses only this)."""
    return {"run": run, "status": "started", "backup": backup,
            "actors": {a["label"]: {"before": a["before"], "after": a["after"]} for a in p["actors"]
                       if a["policy"] in MOVING},
            "sequence": {s["binding"]: {"kind": s["kind"], "before": s["before"], "after": s["after"]}
                         for s in p["sequence"]}}


def apply_model(live, rec):
    """Offline model of APPLY on a live-state dict {"actors": {label: pose}, "sequence": {binding: value}}."""
    out = json.loads(json.dumps(live))
    for label, r in rec["actors"].items():
        out["actors"][label] = json.loads(json.dumps(r["after"]))
    for b, r in rec["sequence"].items():
        out["sequence"][b] = json.loads(json.dumps(r["after"]))
    return out


def revert_model(live, rec):
    out = json.loads(json.dumps(live))
    for label, r in rec["actors"].items():
        out["actors"][label] = json.loads(json.dumps(r["before"]))
    for b, r in rec["sequence"].items():
        out["sequence"][b] = json.loads(json.dumps(r["before"]))
    return out


def drift(live, rec, side):
    """Labels/bindings whose live value differs from the record's <side> ('before' or 'after')."""
    out = []
    for label, r in rec["actors"].items():
        if label not in live["actors"] or not poses_equal(live["actors"][label], r[side]):
            out.append("actor:" + label)
    for b, r in rec["sequence"].items():
        v = live["sequence"].get(b)
        ok = v is not None and (channels_equal(v, r[side]) if r["kind"] == "TRANSFORM_TRACK"
                                else poses_equal(v, r[side], 0.01, 0.001))
        if not ok:
            out.append("seq:" + b)
    return out


# ---------------------------------------------------------------- gates ------------------------------------------------
def snap_equal(a, b, tol=1e-3):
    """p02_straighten.py:280-290 (copied: importing that module in Unreal would run its main())."""
    if a is None or b is None or len(a["points"]) != len(b["points"]) or a["closed"] != b["closed"]:
        return False
    for p, q in zip(a["points"], b["points"]):
        if p["type"] != q["type"]:
            return False
        for k in ("loc", "arrive", "leave", "rot", "scale"):
            if any(abs(x - y) > tol for x, y in zip(p[k], q[k])):
                return False
    return True


def refusals(mode, args, facts):
    out = []
    if mode not in ("CAPTURE", "DRY", "APPLY", "REVERT"):
        return ["MODE_UNKNOWN|" + mode]
    if mode in ("APPLY", "REVERT") and args.get("confirm") != "%s P02FOLLOW" % mode:
        out.append("CONFIRM_MISSING|need='%s P02FOLLOW'" % mode)
    if mode == "CAPTURE":
        if facts.get("capture_exists"):
            out.append("CAPTURE_EXISTS|delete or archive it first (it is the only copy of the old frames)")
        if facts.get("route_straight"):
            out.append("ROUTE_ALREADY_STRAIGHT|capture must precede p02_straighten APPLY")
        if facts.get("straighten_saved"):
            out.append("STRAIGHTEN_ALREADY_APPLIED")
        if facts.get("record_exists"):
            out.append("RECORD_EXISTS")
    if mode == "APPLY":
        if not facts.get("capture"):
            out.append("NO_CAPTURE")
        if facts.get("record_exists"):
            out.append("RECORD_EXISTS")
        sr = facts.get("straighten_record")
        if not sr or sr.get("status") != "saved":
            out.append("STRAIGHTEN_NOT_SAVED")
        else:
            if sr.get("anchor") != "DOCK":
                out.append("ANCHOR_NOT_DOCK|%s (STAY/clamp policies assume the dock is kept)" % sr.get("anchor"))
            if facts.get("capture") and not snap_equal(sr["before"]["spline"], facts["capture"]["spline"]):
                out.append("CAPTURE_IS_NOT_THE_STRAIGHTENED_CURVE")
        if not facts.get("route_straight"):
            out.append("ROUTE_NOT_STRAIGHT")
        if facts.get("new_route_bad"):
            out.append("NEW_ROUTE_NOT_AS_PREDICTED|" + facts["new_route_bad"])
        if facts.get("moved_since_capture"):
            out.append("MOVED_SINCE_CAPTURE|" + ",".join(facts["moved_since_capture"]))
        out.extend(facts.get("plan_refusals") or [])
    if mode == "REVERT":
        rec = facts.get("record")
        if not rec or rec.get("status") != "saved":
            out.append("NO_SAVED_RECORD")
        elif facts.get("drift_vs_after"):
            out.append("DRIFT|" + ",".join(facts["drift_vs_after"]))
    return out


# ---------------------------------------------------------------- Unreal side ------------------------------------------
def stop(msg):
    unreal.log_error("P02_FOLLOWONS_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def log(tag, payload):
    unreal.log("P02_FOLLOWONS_%s|run=%s|%s" % (tag, RUN, json.dumps(payload, default=str, sort_keys=True)))


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def v3(v):
    return [float(v.x), float(v.y), float(v.z)]


def route_frame(route, s):
    t = route.get_transform_at_distance_along_spline(float(s), unreal.SplineCoordinateSpace.WORLD, False)
    r = t.rotation.rotator()
    if abs(r.pitch) > 0.01 or abs(r.roll) > 0.01:
        stop("ROUTE_NOT_PLANAR|s=%.1f|pitch=%.4f|roll=%.4f" % (s, r.pitch, r.roll))
    return xf(v3(t.translation), float(r.yaw))


def actor_pose(a):
    r = a.get_actor_rotation()
    return {"loc": v3(a.get_actor_location()), "rot": [float(r.roll), float(r.pitch), float(r.yaw)],
            "scale": v3(a.get_actor_scale3d())}


def set_actor_pose(a, pose):
    a.modify()
    a.set_actor_location_and_rotation(unreal.Vector(*pose["loc"]),
                                      unreal.Rotator(roll=pose["rot"][0], pitch=pose["rot"][1], yaw=pose["rot"][2]),
                                      False, False)


def enum_name(e):
    return getattr(e, "name", str(e))


def spline_snap(sp):
    """p02_straighten.py:385-396 (same fields, so the gate can compare with its record)."""
    L = unreal.SplineCoordinateSpace.LOCAL
    pts = []
    for i in range(sp.get_number_of_spline_points()):
        r = sp.get_rotation_at_spline_point(i, L)
        pts.append({"loc": v3(sp.get_location_at_spline_point(i, L)),
                    "arrive": v3(sp.get_arrive_tangent_at_spline_point(i, L)),
                    "leave": v3(sp.get_leave_tangent_at_spline_point(i, L)),
                    "type": enum_name(sp.get_spline_point_type(i)),
                    "rot": [float(r.roll), float(r.pitch), float(r.yaw)],
                    "scale": v3(sp.get_scale_at_spline_point(i))})
    return {"points": pts, "closed": bool(sp.is_closed_loop()), "length_cm": float(sp.get_spline_length())}


def unwrap_tuple(res):
    if isinstance(res, tuple) and res and isinstance(res[0], bool):
        return res[1:] if res[0] else None
    return res


def read_world():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    world = ed.get_editor_world()
    if not world.get_path_name().startswith(WORLD + "."):
        stop("WRONG_WORLD|" + world.get_path_name())
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():   # landscape_floors_apply.py:108
        stop("SEQUENCER_OPEN")
    show = unreal.EditorAssetLibrary.load_asset(SHOW)
    acts = _persistent_actors()
    if any(str(a.get_actor_label()).startswith("ZZ_") for a in acts):
        stop("ZZ_ACTORS_PRESENT")
    passages = [a for a in acts if a.get_class().get_name() == "InfinityStagePassageActor"
                and str(a.get_actor_label()).startswith(PASSAGE_PREFIX) and a.get_editor_property("show_asset") == show]
    rigs = [a for a in acts if a.get_class().get_name() == "InfinityStageCameraRig"
            and passages and a.get_editor_property("passage_actor") == passages[0]]
    if len(passages) != 1 or len(rigs) != 1:
        stop("COUNTS|passage=%d|rig=%d" % (len(passages), len(rigs)))
    return ed, world, show, acts, passages[0], rigs[0]


def scan_route_actors(acts, p, route, structs_rigs):
    """The p02_straighten.py:556-568 scan, verbatim in effect (so CAPTURE sees the same set)."""
    W = unreal.SplineCoordinateSpace.WORLD
    snap_len = float(route.get_spline_length())
    managed = set(p.get_editor_property("managed_attachment_actors"))
    old_pts = [route.get_location_at_distance_along_spline(snap_len * i / 40.0, W) for i in range(41)]
    out = []
    for a in acts:
        if a is p or a in structs_rigs or a in managed or a.get_attach_parent_actor() is not None:
            continue
        if a.get_class().get_name() in ("InfinityStagePassageActor", "InfinityStageStructureActor", "InfinityStageCameraRig"):
            continue
        if str(a.get_actor_label()).startswith("Passage 02 - Floor ") or \
                any(str(t).startswith("RigAtmos.Scene2") for t in a.tags):
            continue
        l = a.get_actor_location()
        if any(math.hypot(l.x - q.x, l.y - q.y) < ROUTE_RADIUS_CM for q in old_pts):
            out.append(str(a.get_actor_label()))
    return sorted(out)


def binding_by_name(seq, name, want_transform):
    hits = [b for b in seq.get_bindings() if str(b.get_display_name()) == name]
    if want_transform:
        hits = [b for b in hits if any(t.get_class().get_name() == "MovieScene3DTransformTrack"
                                       and str(t.get_display_name()) == TRACK for t in b.get_tracks())]
    if len(hits) != 1:
        stop("BINDING_COUNT|%s|%d" % (name, len(hits)))
    return hits[0]


def transform_channels(binding):
    tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"
              and str(t.get_display_name()) == TRACK]
    secs = list(tracks[0].get_sections()) if len(tracks) == 1 else []
    if len(tracks) != 1 or len(secs) != 1:
        stop("TRANSFORM_TRACK_SHAPE|%s|tracks=%d|sections=%d" % (binding.get_display_name(), len(tracks), len(secs)))
    chans = {}
    for c in secs[0].get_all_channels():
        base = channel_base(c.channel_name)
        if base in chans:
            stop("CHANNEL_DUPLICATE|%s|%s" % (binding.get_display_name(), base))
        chans[base] = c
    return chans


def read_keys(chans):
    """opening_readback.py:246 form; frames are only identities here (times are never written)."""
    return {n: [[int(k.get_time().frame_number.value), float(k.get_value())] for k in c.get_keys()]
            for n, c in chans.items() if n.startswith("Location.") or n.startswith("Rotation.")}


def template_root(binding):
    root = binding.get_object_template().get_editor_property("root_component")   # curtain_sleight.py:1518-1520
    return root


def template_pose(binding):
    root = template_root(binding)
    l, r = root.get_editor_property("relative_location"), root.get_editor_property("relative_rotation")
    return {"loc": [float(l.x), float(l.y), float(l.z)], "rot": [float(r.roll), float(r.pitch), float(r.yaw)],
            "scale": [1.0, 1.0, 1.0]}


def read_sequence(seq):
    items = []
    for name, kind in SEQ_ITEMS:
        if kind == "TRANSFORM_TRACK":
            items.append({"binding": name, "kind": kind,
                          "channels": read_keys(transform_channels(binding_by_name(seq, name, True)))})
        else:
            items.append({"binding": name, "kind": kind, "pose": template_pose(binding_by_name(seq, name, False))})
    return items


def sequences_to_scan(show):
    """Every Show cue's sequence + one level of nested shots/subsequences + the Master (bindings only; never
    GetBoundObjects). Precedents: curtain_sleight.py:1484-1486 (cue sequence), :1639-1642 (nested)."""
    seen, out = set(), []

    def add(s):
        if s is not None and s.get_path_name() not in seen:
            seen.add(s.get_path_name())
            out.append(s)
    for c in show.get_editor_property("cues"):
        try:
            add(c.get_editor_property("scene").get_editor_property("sequence"))
        except Exception:  # noqa: BLE001 -- cue types without a scene struct
            pass
    add(unreal.load_asset(MASTER))
    for s in list(out):
        for tt in (unreal.MovieSceneCinematicShotTrack, unreal.MovieSceneSubTrack):
            for t in s.find_tracks_by_type(tt):
                for sec in t.get_sections():
                    add(sec.get_sequence())
    return out


def binding_scan(show, labels):
    """Bindings (any sequence) whose display name is a moved route actor. Handled: the I1 items. A foreign binding
    carrying a 3D transform track is a refusal (its keys would strand); other tracks are reported."""
    handled = {(I1_SEQ, n) for n, _ in SEQ_ITEMS}
    found, foreign = [], []
    for s in sequences_to_scan(show):
        path = s.get_path_name().split(".")[0]
        for b in s.get_bindings():
            name = str(b.get_display_name())
            if name not in labels:
                continue
            classes = sorted(t.get_class().get_name() for t in b.get_tracks())
            found.append({"sequence": path, "binding": name, "tracks": classes})
            if (path, name) not in handled and "MovieScene3DTransformTrack" in classes:
                foreign.append({"sequence": path, "binding": name})
    return found, foreign


def capture_mode(args, w):
    ed, world, show, acts, p, rig = w
    route = p.get_editor_property("route")
    straighten_rec = json.load(open(STRAIGHT_REC, encoding="utf-8")) if os.path.exists(STRAIGHT_REC) else None
    facts = {"capture_exists": os.path.exists(CAPTURE), "record_exists": os.path.exists(REC),
             "route_straight": bool(p.get_editor_property("auto_fit_straight_route")),
             "straighten_saved": bool(straighten_rec) and straighten_rec.get("status") == "saved"}
    bad = refusals("CAPTURE", args, facts)
    if bad:
        stop("REFUSED|" + "|".join(bad))
    before = census()
    W = unreal.SplineCoordinateSpace.WORLD
    snap = spline_snap(route)
    req = unwrap_tuple(p.get_route_length_status())                 # p02_straighten.py:503-504
    if not req:
        stop("COMPILED_LENGTH_UNREADABLE")
    d_end = float(req[0])
    n = int(math.floor(snap["length_cm"] / SAMPLE_STEP_CM))
    dists = [i * SAMPLE_STEP_CM for i in range(n + 1)] + [snap["length_cm"]]
    samples = []
    for s in dists:
        q = route.get_location_at_distance_along_spline(s, W)
        samples.append([s, float(q.x), float(q.y)])
    structs = [a for a in acts if a.get_class().get_name() == "InfinityStageStructureActor"
               and a.get_editor_property("passage") == p]
    scanned = scan_route_actors(acts, p, route, set(structs) | {rig})
    by = {}
    for a in acts:
        by.setdefault(str(a.get_actor_label()), []).append(a)
    actors, missing = {}, []
    for label, pol in POLICY.items():
        hits = by.get(label, [])
        if len(hits) != 1:
            missing.append("%s(x%d)" % (label, len(hits)))
            continue
        a = hits[0]
        pose = actor_pose(a)
        s_near, lat = nearest_s(samples, pose["loc"])
        q = route.find_location_closest_to_world_location(unreal.Vector(*pose["loc"]), W)
        row = {"policy": pol, "class": a.get_class().get_name(), "pose": pose, "nearest_s": s_near, "lateral_cm": lat,
               "unreal_closest_xy": [float(q.x), float(q.y)],
               "attached": a.get_attach_parent_actor() is not None}
        st = station(pol, s_near, d_end)
        if st is not None:
            row["station_s"] = st
            row["old_frame"] = route_frame(route, st)
            row["local"] = to_local(row["old_frame"], pose["loc"])
        actors[label] = row
    seq = unreal.load_asset(I1_SEQ)
    items = read_sequence(seq)
    found, foreign = binding_scan(show, {l for l, pol in POLICY.items() if pol in MOVING})
    cap = {"run": RUN, "made": datetime.datetime.now().isoformat(), "world": WORLD,
           "passage_label": str(p.get_actor_label()), "passage_actor": actor_pose(p),
           "auto_fit": facts["route_straight"], "spline": snap, "d_end_cm": d_end, "sample_step_cm": SAMPLE_STEP_CM,
           "samples": samples, "mouth_frame_old": route_frame(route, 0.0), "end_frame_old": route_frame(route, d_end),
           "actors": actors, "missing": missing, "scanned": scanned,
           "unclassified": sorted(set(scanned) - set(POLICY)),
           "sequence": {"path": I1_SEQ, "items": items, "bindings_found": found,
                        "foreign_transform_bindings": foreign},
           "census": before}
    if census() != before:
        stop("CAPTURE_DIRTIED|" + json.dumps(census()))
    with open(CAPTURE, "x", encoding="utf-8") as h:
        json.dump(cap, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())
    log("CAPTURE", {k: cap[k] for k in ("d_end_cm", "mouth_frame_old", "end_frame_old", "missing", "scanned",
                                         "unclassified")})
    unreal.log("P02_FOLLOWONS_CAPTURE_OK|run=%s|actors=%d|keys=%s|unclassified=%d|foreign=%d|path=%s"
               % (RUN, len(actors), ",".join(str(len(i["channels"]["Location.X"])) for i in items
                                              if i["kind"] == "TRANSFORM_TRACK"),
                  len(cap["unclassified"]), len(foreign), CAPTURE))


def live_state(acts, seq, labels):
    by = {str(a.get_actor_label()): a for a in acts}
    out = {"actors": {l: actor_pose(by[l]) for l in labels if l in by}, "sequence": {}}
    for item in read_sequence(seq):
        out["sequence"][item["binding"]] = item["channels"] if item["kind"] == "TRANSFORM_TRACK" else item["pose"]
    return out, by


def new_route_frames(route, capture, args, straight_now):
    """Callable s -> frame on the NEW route. Live when straight (checked against the pure straight line), else the
    PREDICTED straight route from args (DRY only)."""
    if straight_now:
        start = route_frame(route, 0.0)
        bad = []
        for s in (0.0, capture["d_end_cm"] / 2.0, capture["d_end_cm"]):
            live = route_frame(route, s)
            pred = straight_frame(start, s)
            d = math.hypot(live["loc"][0] - pred["loc"][0], live["loc"][1] - pred["loc"][1])
            if d > 1.0 or abs(wrap(live["yaw"] - pred["yaw"])) > 0.01:
                bad.append("s=%.0f:%.2fcm" % (s, d))
        return (lambda s: route_frame(route, s)), (",".join(bad) or None), start
    ps = args.get("predicted_route_start")
    if not ps:
        return None, None, None
    start = xf(ps["loc"], ps["yaw"])
    return (lambda s: straight_frame(start, s)), None, start


def apply_or_dry(mode, args, w):
    ed, world, show, acts, p, rig = w
    route = p.get_editor_property("route")
    if not os.path.exists(CAPTURE):
        stop("NO_CAPTURE")
    capture = json.load(open(CAPTURE, encoding="utf-8"))
    straight_now = bool(p.get_editor_property("auto_fit_straight_route")) and \
        route.get_number_of_spline_points() == 2
    frame_at, new_bad, start = new_route_frames(route, capture, args, straight_now)
    if frame_at is None:
        stop("ROUTE_NOT_STRAIGHT_AND_NO_PREDICTION|run p02_straighten APPLY first, or give predicted_route_start")
    pl = plan(capture, frame_at)
    seq = unreal.load_asset(I1_SEQ)
    labels = [a["label"] for a in pl["actors"] if a["policy"] in MOVING]
    live, by = live_state(acts, seq, labels)
    moved = [l for l in labels if l not in live["actors"]
             or not poses_equal(live["actors"][l], capture["actors"][l]["pose"])]
    moved += ["seq:" + i["binding"] for i in capture["sequence"]["items"]
              if not (channels_equal(live["sequence"][i["binding"]], i["channels"]) if i["kind"] == "TRANSFORM_TRACK"
                      else poses_equal(live["sequence"][i["binding"]], i["pose"], 0.01, 0.001))]
    straighten_rec = json.load(open(STRAIGHT_REC, encoding="utf-8")) if os.path.exists(STRAIGHT_REC) else None
    # Measured target for the walk end: P02's camera start view (p02_straighten.py:493-495, 519; the straighten DRY
    # ran this read with a clean census after it [meas DRY census]).
    guid = p.get_editor_property("passage_guid")
    fr = unwrap_tuple(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, guid))
    cam_start = None
    if fr and straight_now:
        t = unwrap_tuple(rig.get_camera_view_at_master_frame(unreal.FrameNumber(int(fr[0]))))
        t = next((x for x in (t if isinstance(t, tuple) else (t,)) if isinstance(x, unreal.Transform)), None)
        if t is not None:
            r = t.rotation.rotator()
            cam_start = {"loc": v3(t.translation), "rot": [float(r.roll), float(r.pitch), float(r.yaw)],
                         "scale": [1.0, 1.0, 1.0]}
    walk_vs_cam = pose_delta(pl["walk_end_planned"], cam_start) if (cam_start and pl["walk_end_planned"]) else None
    facts = {"capture": capture, "record_exists": os.path.exists(REC), "straighten_record": straighten_rec,
             "route_straight": straight_now, "new_route_bad": new_bad, "moved_since_capture": moved,
             "plan_refusals": pl["refusals"]}
    report = {"run": RUN, "mode": mode, "route_source": "LIVE" if straight_now else "PREDICTED", "new_start": start,
              "plan": pl, "walk_end_vs_p02_camera_start": walk_vs_cam, "moved_since_capture": moved,
              "census": census()}
    for a in pl["actors"]:
        log("ACTOR", {k: a.get(k) for k in ("label", "policy", "nearest_s", "station_s", "move", "why")})
    for s in pl["sequence"]:
        log("SEQ", {k: s.get(k) for k in ("binding", "kind", "keys", "yaw_step_before", "yaw_step_after")})
    if mode == "DRY":
        report["refusals_if_apply"] = refusals("APPLY", dict(args, confirm="APPLY P02FOLLOW"), facts)
        path = HERE + "p02_straighten_followons_dry_%s.json" % RUN
        with open(path, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        if census() != report["census"]:
            stop("DRY_DIRTIED|" + json.dumps(census()))
        unreal.log("P02_FOLLOWONS_DRY_OK|run=%s|route=%s|moving=%d|refusals_if_apply=%d|walk_vs_cam=%s|report=%s"
                   % (RUN, report["route_source"], len(labels), len(report["refusals_if_apply"]),
                      json.dumps(walk_vs_cam), path))
        return
    bad = refusals("APPLY", args, facts)
    if bad:
        stop("REFUSED|" + "|".join(bad))
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    if walk_vs_cam is None or walk_vs_cam["xy_cm"] > WALK_TOL_CM or abs(walk_vs_cam["z_cm"]) > WALK_TOL_CM \
            or abs(walk_vs_cam["yaw_deg"]) > WALK_TOL_DEG:
        stop("WALK_END_VS_CAMERA_START|%s" % json.dumps(walk_vs_cam))
    backup = "E:/PussStage/Backups/PreP02Followons-" + RUN
    rec = record_from_plan(pl, RUN, backup)
    write_record(rec, exclusive=True)
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    shutil.copy2(I1_UASSET, backup)
    write_values(by, seq, rec, "after")
    finish(ed, world, by, seq, rec, "after", "APPLY")


def write_values(by, seq, rec, side):
    for label, r in rec["actors"].items():
        set_actor_pose(by[label], r[side])
        if not poses_equal(actor_pose(by[label]), r[side]):
            stop("ACTOR_READBACK|%s|NOTHING SAVED; Don't-Save restart" % label)
    seq.modify()
    for name, r in rec["sequence"].items():
        if r["kind"] == "TRANSFORM_TRACK":
            chans = transform_channels(binding_by_name(seq, name, True))
            for cname, rows in r[side].items():
                keys = list(chans[cname].get_keys())
                if [int(k.get_time().frame_number.value) for k in keys] != [row[0] for row in rows]:
                    stop("KEY_FRAMES_CHANGED|%s|%s|NOTHING SAVED; Don't-Save restart" % (name, cname))
                for k, row in zip(keys, rows):
                    k.set_value(float(row[1]))                    # repair_curtain_staging.py:305 [prec]
            if not channels_equal(read_keys(chans), r[side]):
                stop("KEY_READBACK|%s|NOTHING SAVED; Don't-Save restart" % name)
        else:
            root = template_root(binding_by_name(seq, name, False))
            pose = r[side]
            root.set_editor_property("relative_location", unreal.Vector(*pose["loc"]))   # fit_transition_drapes:135
            root.set_editor_property("relative_rotation",
                                     unreal.Rotator(roll=pose["rot"][0], pitch=pose["rot"][1], yaw=pose["rot"][2]))
            if not poses_equal(template_pose(binding_by_name(seq, name, False)), pose, 0.01, 0.001):
                stop("TEMPLATE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % name)


def finish(ed, world, by, seq, rec, side, mode):
    dirty = census()
    if set(dirty["content"]) - {I1_SEQ} or dirty["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if I1_SEQ in dirty["content"] and not unreal.EditorAssetLibrary.save_asset(I1_SEQ, only_if_is_dirty=True):
        stop("SEQ_SAVE_FAILED")
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        stop("LEVEL_SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    live, _ = live_state(_persistent_actors(),
                         unreal.load_asset(I1_SEQ), list(rec["actors"]))
    off = drift(live, rec, side)
    if off:
        stop("POST_SAVE_READBACK|" + ",".join(off))
    if mode == "APPLY":
        rec.update({"status": "saved", "saved_census": dirty})
        write_record(rec, exclusive=False)
    else:
        os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("P02_FOLLOWONS_%s_OK|run=%s|actors=%d|seq_items=%d|seq_saved=%d|level_saved=1|readback=1|dirty_after=0+0"
               % (mode, RUN, len(rec["actors"]), len(rec["sequence"]), int(I1_SEQ in dirty["content"])))


def revert_mode(args, w):
    ed, world, show, acts, p, rig = w
    rec = json.load(open(REC, encoding="utf-8")) if os.path.exists(REC) else None
    facts = {"record": rec}
    if rec and rec.get("status") == "saved":
        live, by = live_state(acts, unreal.load_asset(I1_SEQ), list(rec["actors"]))
        facts["drift_vs_after"] = drift(live, rec, "after")
    bad = refusals("REVERT", args, facts)
    if bad:
        stop("REFUSED|" + "|".join(bad))
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    backup = "E:/PussStage/Backups/PreP02FollowonsRevert-" + RUN
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    shutil.copy2(I1_UASSET, backup)
    seq = unreal.load_asset(I1_SEQ)
    write_values(by, seq, rec, "before")
    finish(ed, world, by, seq, rec, "before", "REVERT")


def write_record(obj, exclusive):
    with open(REC, "x" if exclusive else "w", encoding="utf-8") as h:
        json.dump(obj, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())


def main():
    args = globals().get("P02FOLLOW_ARGS")
    if args is None:
        args = json.load(open(HERE + ARGS_NAME, encoding="utf-8"))
    mode = str(args.get("mode", "DRY")).upper()
    if mode not in ("CAPTURE", "DRY", "APPLY", "REVERT"):
        stop("MODE_UNKNOWN|" + mode)
    w = read_world()
    if mode == "CAPTURE":
        capture_mode(args, w)
    elif mode in ("DRY", "APPLY"):
        apply_or_dry(mode, args, w)
    else:
        revert_mode(args, w)


if unreal is not None:
    main()
