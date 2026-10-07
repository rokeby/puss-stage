"""P06 BEE GLINTS (7 Oct): short bursts of Klara's bee swarm in P06's dark, ahead of S6 where her swarm takes over.
Offline-written, NEVER RUN IN UNREAL. Harness: test_p06_bee_glints_offline.py (system Python, + and - controls,
seeded mutations).

Gary, 7 Oct (own words): "an earlier appearance of the bees in smaller volumes" -> approved "Bees glimmer in P06's
dark". Times (~80 / 100 / 118 s), lives, scales and placement in the args are the conductor's proposal, NOT Gary's.

Tiers per claim: [decl] header/source we read (file:line), [bin] package bytes, [prec] in-repo precedent, [meas] a
record read back, [inf] inferred (why stated).

WHERE THE GLINTS LIVE (the question the brief asked)
  * A root sub-track in the MASTER is NOT safe. RebuildManagedMaster leaves it alone (it only FindTrack<>s its four
    managed track types, InfinityStageSequenceBuilderLibrary.cpp:196-605 [decl]), BUT the suite's
    InfinityStage.Editor.SavedMasterMatchesShow walks EVERY root track except Choreo tracks and counts every sub-section
    against the Show's Scene/Sequence cues (InfinityStageEditorAutomationTests.cpp:1698-1745 [decl]). One extra section
    fails "one section per Scene and Sequence cue" and its length check. Validate refuses attach "master_subtrack".
  * attach "choreo_subtrack" (RECOMMENDED): LS_P06_BeeGlints (new, ours) holds the bursts at PASSAGE-RELATIVE frames;
    ONE plain MovieSceneSubTrack is added to LS_Choreo_Passage_6 (the cueing stream's file: one additive track, needs
    their ack in args "cueing_ack"). The Choreo is nested by the rebuild at its Passage start, moved then re-ranged on
    every rebuild (cpp:330-394 [decl]); SavedMasterMatchesShow skips Choreo tracks (:1702-1705 [decl]). So a rebuild
    neither deletes nor misplaces it. The Choreo's own tracks are never touched (rebuild never edits it, :396-410).
  * attach "master_bindings" (fallback, no foreign file): the bursts are NiagaraActor spawnables bound in the Master
    root at ABSOLUTE frames. The rebuild never touches bindings (the function body has no binding code [decl]) and the
    test ignores bindings (root tracks only [decl]), so they SURVIVE - but they do NOT TRAVEL: a Scene relength before
    P06 moves P06 and leaves them behind (P06's Master start was 47949592 in p06_tail_extend_record.json and 41532952
    in passage_speed_probe_PSPEED-20261006-223036.json [meas]: it moves). DRY reports DRIFT against the record; the
    fix is REVERT + APPLY.

THE BURSTS
  * System /Game/FX/NS_BeeSwarm (Klara's; S6 glimmer precedent klara_void_s6.py:1341-1363). Its only renderer is a
    sprite renderer on /Niagara/DefaultAssets/DefaultSpriteMaterial [bin: NS_BeeSwarm.uasset strings], and that
    material's package carries MSM_Unlit + BLEND_Additive + EmissiveColor [bin: engine DefaultSpriteMaterial.uasset]:
    self-lit, so it should read in total dark [inf until PIE: exposure in the dark is unmeasured]. No User. params and
    a constant spawn rate (EFFECTS_PLAN_2026-10-07.md:55 [bin]): "smaller volume" = owner scale (ShapeLocation has
    Apply Owner Scale [bin]) x a short life; the count is rate x life [inf]. A fresh system starts EMPTY (WarmupTime
    unset, S6_VOID_PLAN.md [meas]), so each burst fills in; despawn ends it abruptly [inf, PIE].
  * Each burst = one spawnable, spawn key ON at t, OFF at t + life; constant transform (defaults, scale set: unkeyed
    scale evaluates 0 [prec curtain_sleight.py:1791]).
  * Pose: the P06 rig's GetCameraViewAtMasterFrame (BlueprintPure const, InfinityStageCameraRig.h:355-360 [decl];
    used read-only by passage_speed_probe.py:233 [prec]) gives the camera at t; its station = nearest distance on the
    Passage actor's `route` spline [prec place_p06_car_light.py:111]; the swarm sits at route(station + ahead_cm)
    (linear extrapolation past the route end, as InfinityStagePassageResizeLibrary.cpp:108-112), at camera z + up_cm.
    Guards per burst over its whole life: in front, >= min_clear_cm from the camera, inside fov_fraction of the half
    FOV across the smaller filmback side (focal from the same call, filmback from the rig), inside the dark (>= dark_from_s, p06_sunset_record
    probe: daylight 7e-5 at 52 s [meas]) and before the Passage end. FRAME_TRAP refuses a camera off its route
    (memory: the sunk REST pose put tools 35 m underground).
  * Times are seconds from the P06 compiled segment start (transport build_segments [prec passage_speed_probe.py:100]),
    the same zero as the sunset's elapsed time (P06_SUNSET_PLAN.md s1 [decl]) and the Choreo's 0:00 (cpp:330 [decl]).

STAGES (args "mode"; confirm "<MODE> P06BEEGLINTS")
  DRY     read-only -> p06_bee_glints_dry.json; P06BEEGLINTS_DRY_OK|run=..|apply_ready=..
  APPLY   record first (exclusive, fsynced), sha-checked backup, build, read back, census == expected, save ONLY the
          expected packages, post-save read back; P06BEEGLINTS_APPLY_OK
  REVERT  drift check against the record, remove only what the record names, save, delete the glints asset if
          unreferenced; P06BEEGLINTS_REVERT_OK
Never: Save All, reload a level, open/scrub Sequencer, EvaluateAtMasterFrame (it mutates the rig), GetBoundObjects,
end PIE; no unreal objects in module globals. Importing without `unreal` runs nothing.
"""
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


TOOL = "p06_bee_glints"
MARK = "P06BEEGLINTS"
CONFIRM_WORD = "P06BEEGLINTS"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                    # klara_void_s6.py:71
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"  # klara_void_s6.py:72
ARGS_NAME = "p06_bee_glints_args.json"
DRY_NAME = "p06_bee_glints_dry.json"
RECORD_NAME = "p06_bee_glints_record.json"
MODES = ("DRY", "APPLY", "REVERT")
ATTACHES = ("choreo_subtrack", "master_bindings")
REFUSED_ATTACHES = {"master_subtrack": "fails InfinityStage.Editor.SavedMasterMatchesShow "
                                       "(InfinityStageEditorAutomationTests.cpp:1698-1745: every non-Choreo root "
                                       "sub-section is counted against the Show's Scene/Sequence cues)"}
BASES = ("route", "camera")
BINDING_PREFIX = "P06 Bee Glint "
SUBTRACK_NAME = "P06 Bee Glints (Effects)"
ROUTE_STEP_CM = 100.0
CHECK_SAMPLES = 9


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: time
# =====================================================================================================================

def secs_to_ticks(seconds, tick):
    return int(round(float(seconds) * float(tick)))


def display_frame(abs_ticks, tick, fps):
    """Nearest display frame to an absolute tick time, and its error in seconds."""
    exact = float(abs_ticks) * float(fps) / float(tick)
    frame = int(round(exact))
    return frame, abs(frame - exact) / float(fps)


def binding_name(index, burst):
    return "%s%d @%.1fs" % (BINDING_PREFIX, index + 1, float(burst["t_s"]))


def is_ours(name):
    return str(name).startswith(BINDING_PREFIX)


# =====================================================================================================================
# Pure: geometry (UE: X forward, Y right, Z up; yaw about Z in degrees)
# =====================================================================================================================

def fwd3(pitch_deg, yaw_deg):
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    return [math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)]


def right2(yaw_deg):
    y = math.radians(yaw_deg)
    return [-math.sin(y), math.cos(y), 0.0]


def sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def norm(a):
    return math.sqrt(sum(x * x for x in a))


def angle_deg(a, b):
    na, nb = norm(a), norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 180.0
    c = max(-1.0, min(1.0, sum(a[i] * b[i] for i in range(3)) / (na * nb)))
    return math.degrees(math.acos(c))


def half_fov_deg(focal_mm, sensor_mm):
    """Half the field of view across sensor_mm (the tool passes the SMALLER filmback side: a cone inside the frame)."""
    return math.degrees(math.atan(0.5 * float(sensor_mm) / float(focal_mm)))


def route_polyline(points):
    """points: [[x, y, z], ...] sampled along the route -> [(distance, [x, y, z]), ...] (cumulative chord length)."""
    out, d = [], 0.0
    for i, p in enumerate(points):
        if i:
            d += norm(sub(p, points[i - 1]))
        out.append((d, [float(c) for c in p]))
    if len(out) < 2 or out[-1][0] <= 0.0:
        raise PlanError("ROUTE_DEGENERATE: %d points" % len(out))
    return out


def route_point(poly, dist):
    """Point + yaw at distance along the polyline; LINEAR EXTRAPOLATION past either end along the end segment
    (as InfinityStagePassageResizeLibrary.cpp:108-112 extends a short route), never a clamp."""
    if dist <= poly[0][0]:
        (d0, a), (d1, b) = poly[0], poly[1]
    elif dist >= poly[-1][0]:
        (d0, a), (d1, b) = poly[-2], poly[-1]
    else:
        lo, hi = 0, len(poly) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if poly[mid][0] <= dist:
                lo = mid
            else:
                hi = mid
        (d0, a), (d1, b) = poly[lo], poly[hi]
    seg = d1 - d0
    u = (dist - d0) / seg
    p = [a[i] + (b[i] - a[i]) * u for i in range(3)]
    yaw = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    return p, yaw


def route_nearest(poly, loc):
    """Station (distance) of the nearest point on the polyline (XY), and the XY lateral offset."""
    best = None
    for (d0, a), (d1, b) in zip(poly, poly[1:]):
        ab = [b[0] - a[0], b[1] - a[1]]
        L2 = ab[0] * ab[0] + ab[1] * ab[1]
        u = 0.0 if L2 <= 0 else max(0.0, min(1.0, ((loc[0] - a[0]) * ab[0] + (loc[1] - a[1]) * ab[1]) / L2))
        q = [a[0] + ab[0] * u, a[1] + ab[1] * u]
        lat = math.hypot(loc[0] - q[0], loc[1] - q[1])
        if best is None or lat < best[1]:
            best = (d0 + (d1 - d0) * u, lat, a[2] + (b[2] - a[2]) * u)
    return best   # (station, lateral_cm, route_z)


# =====================================================================================================================
# Pure: args and plan
# =====================================================================================================================

def validate_args(args):
    r = []
    if str(args.get("mode") or "").upper() not in MODES:
        r.append("MODE_INVALID: %r" % args.get("mode"))
    att = args.get("attach")
    if att in REFUSED_ATTACHES:
        r.append("ATTACH_REFUSED: %s %s" % (att, REFUSED_ATTACHES[att]))
    elif att not in ATTACHES:
        r.append("ATTACH_INVALID: %r" % att)
    for f in ("glints_sequence", "choreo", "master", "system"):
        if not str(args.get(f) or "").startswith("/Game/"):
            r.append("%s_NOT_GAME_PATH" % f.upper())
    if args.get("glints_sequence") in (args.get("choreo"), args.get("master")):
        r.append("GLINTS_PATH_IS_AN_EXISTING_SEQUENCE")
    if not str(args.get("passage_label") or "").strip():
        r.append("PASSAGE_LABEL_MISSING")
    if args.get("basis", "route") not in BASES:
        r.append("BASIS_INVALID: %r" % args.get("basis"))
    hs = args.get("her_scale")
    if not (isinstance(hs, list) and len(hs) == 3 and all(isinstance(x, (int, float)) and x > 0 for x in hs)):
        r.append("HER_SCALE_INVALID")
    lim = args.get("limits") or {}
    for f in ("life_min_s", "life_max_s", "scale_max", "dark_from_s", "end_margin_s", "min_clear_cm", "fov_fraction",
              "max_lateral_cm", "eye_min_cm", "eye_max_cm", "sensor_width_mm_default"):
        if not isinstance(lim.get(f), (int, float)):
            r.append("LIMIT_MISSING_%s" % f.upper())
    bursts = args.get("bursts")
    if not isinstance(bursts, list) or not bursts:
        r.append("BURSTS_MISSING")
        return r
    for i, b in enumerate(bursts):
        for f in ("t_s", "life_s", "scale", "ahead_cm", "up_cm", "side_cm", "yaw_offset_deg"):
            if not isinstance(b.get(f), (int, float)):
                r.append("BURST%d_%s_INVALID" % (i + 1, f.upper()))
        if r:
            continue
        if not (lim["life_min_s"] <= b["life_s"] <= lim["life_max_s"]):
            r.append("BURST%d_LIFE_OUTSIDE_%.1f_%.1f_S" % (i + 1, lim["life_min_s"], lim["life_max_s"]))
        if not (0.0 < b["scale"] <= lim["scale_max"]):
            r.append("BURST%d_SCALE_NOT_SMALLER: %r (max %r of her swarm)" % (i + 1, b["scale"], lim["scale_max"]))
        if b["ahead_cm"] <= 0:
            r.append("BURST%d_NOT_AHEAD" % (i + 1))
    return r


def burst_windows(bursts, length_s, dark_from_s, end_margin_s):
    r = []
    prev_end = None
    for i, b in enumerate(sorted(bursts, key=lambda x: x["t_s"])):
        t0, t1 = float(b["t_s"]), float(b["t_s"]) + float(b["life_s"])
        if t0 < dark_from_s:
            r.append("BURST%d_NOT_IN_THE_DARK: starts %.2f s, dark from %.2f s" % (i + 1, t0, dark_from_s))
        if t1 > length_s - end_margin_s:
            r.append("BURST%d_PAST_PASSAGE_END: ends %.2f s, P06 %.3f s - margin %.2f" % (i + 1, t1, length_s,
                                                                                          end_margin_s))
        if prev_end is not None and t0 < prev_end:
            r.append("BURST%d_OVERLAPS_PREVIOUS" % (i + 1))
        prev_end = t1
    return r


def place_burst(burst, view0, poly, basis, her_scale):
    """World pose of one burst from the camera view at its start."""
    loc0 = view0["loc"]
    if basis == "route":
        station, _lat, _rz = route_nearest(poly, loc0)
        p, yaw = route_point(poly, station + float(burst["ahead_cm"]))
        base = [p[0], p[1], loc0[2]]
    else:
        station = None
        yaw = float(view0["rot"][2])
        f = fwd3(0.0, yaw)
        base = [loc0[i] + f[i] * float(burst["ahead_cm"]) for i in range(3)]
    r = right2(yaw)
    loc = [base[0] + r[0] * burst["side_cm"], base[1] + r[1] * burst["side_cm"], base[2] + float(burst["up_cm"])]
    return {"loc": loc, "rot": [0.0, 0.0, yaw + float(burst["yaw_offset_deg"])],
            "scale": [float(s) * float(burst["scale"]) for s in her_scale], "station_cm": station, "route_yaw": yaw}


def frame_guard(view, poly, lim):
    """FRAME_TRAP: the camera must sit on its route at eye height (memory puss-level-saved-landed-frame-trap)."""
    station, lat, rz = route_nearest(poly, view["loc"])
    dz = view["loc"][2] - rz
    bad = []
    if lat > lim["max_lateral_cm"]:
        bad.append("lateral %.0f cm > %.0f" % (lat, lim["max_lateral_cm"]))
    if not (lim["eye_min_cm"] <= dz <= lim["eye_max_cm"]):
        bad.append("eye height %.0f cm outside [%.0f, %.0f]" % (dz, lim["eye_min_cm"], lim["eye_max_cm"]))
    return bad, {"station_cm": station, "lateral_cm": lat, "eye_cm": dz}


def visibility_checks(pose, views, lim, sensor_mm):
    """Over the burst's life: in front, clear of the camera, inside fov_fraction of the half FOV across the smaller filmback side."""
    rows, bad = [], []
    for v in views:
        d = sub(pose["loc"], v["loc"])
        dist = norm(d)
        ang = angle_deg(fwd3(v["rot"][1], v["rot"][2]), d)
        lim_ang = half_fov_deg(v["focal"], sensor_mm) * lim["fov_fraction"]
        rows.append({"t_s": v["t_s"], "dist_cm": round(dist, 1), "angle_deg": round(ang, 2), "limit_deg": round(lim_ang, 2)})
        if dist < lim["min_clear_cm"]:
            bad.append("TOO_CLOSE at %.2f s: %.0f cm < %.0f" % (v["t_s"], dist, lim["min_clear_cm"]))
        if ang > lim_ang:
            bad.append("OUT_OF_FRAME at %.2f s: %.1f deg > %.1f" % (v["t_s"], ang, lim_ang))
    return rows, bad


def plan_glints(args, seg, view_fn, route_points, rates, sensor_mm=None, choreo_end_s=None):
    """seg = {"start": abs ticks, "end": abs ticks}; view_fn(abs_ticks) -> {"loc", "rot" [roll, pitch, yaw], "focal"}
    or None; rates = {"tick": ticks/s, "fps": the target sequence display fps}. Pure."""
    lim = args["limits"]
    tick, fps = float(rates["tick"]), float(rates["fps"])
    length_s = (seg["end"] - seg["start"]) / tick
    refusals, warnings = [], []
    refusals += burst_windows(args["bursts"], length_s, lim["dark_from_s"], lim["end_margin_s"])
    if choreo_end_s is not None and args["attach"] == "choreo_subtrack":
        last = max(b["t_s"] + b["life_s"] for b in args["bursts"])
        if choreo_end_s + 1e-6 < last:
            refusals.append("CHOREO_SHORT: its playback ends %.2f s, last burst ends %.2f s (nested content past the "
                            "Choreo's end is not played, builder cpp:396-410)" % (choreo_end_s, last))
    exp = args.get("expected_length_s")
    if isinstance(exp, (int, float)) and abs(exp - length_s) > args.get("length_tol_s", 0.05):
        warnings.append("P06_LENGTH_CHANGED: live %.3f s, args %.3f s (times are kept; windows re-checked)"
                        % (length_s, exp))
    poly = route_polyline(route_points)
    sensor = float(sensor_mm or lim["sensor_width_mm_default"])
    out = []
    for i, b in enumerate(sorted(args["bursts"], key=lambda x: x["t_s"])):
        t0, t1 = float(b["t_s"]), float(b["t_s"]) + float(b["life_s"])
        views = []
        for k in range(CHECK_SAMPLES):
            t = t0 + (t1 - t0) * k / float(CHECK_SAMPLES - 1)
            v = view_fn(seg["start"] + secs_to_ticks(t, tick))
            if v is None:
                refusals.append("BURST%d_NO_CAMERA_VIEW at %.2f s" % (i + 1, t))
                break
            views.append(dict(v, t_s=round(t, 4)))
        if len(views) != CHECK_SAMPLES:
            continue
        trap, at = frame_guard(views[0], poly, lim)
        if trap:
            refusals.append("BURST%d_FRAME_TRAP: %s" % (i + 1, "; ".join(trap)))
            continue
        pose = place_burst(b, views[0], poly, args.get("basis", "route"), args["her_scale"])
        rows, bad = visibility_checks(pose, views, lim, sensor)
        refusals += ["BURST%d_%s" % (i + 1, x) for x in bad]
        rel0, rel1 = secs_to_ticks(t0, tick), secs_to_ticks(t1, tick)
        if args["attach"] == "choreo_subtrack":
            on, e0 = display_frame(rel0, tick, fps)
            off, e1 = display_frame(rel1, tick, fps)
        else:
            on, e0 = display_frame(seg["start"] + rel0, tick, fps)
            off, e1 = display_frame(seg["start"] + rel1, tick, fps)
        if off <= on:
            refusals.append("BURST%d_ZERO_FRAMES" % (i + 1))
        out.append({"index": i, "name": binding_name(i, b), "t_s": t0, "end_s": t1, "life_s": float(b["life_s"]),
                    "rel_ticks": [rel0, rel1], "frames": [on, off], "frame_err_s": round(max(e0, e1), 6),
                    "camera_at_start": {"loc": [round(x, 2) for x in views[0]["loc"]], "rot": views[0]["rot"],
                                        "focal": views[0]["focal"], "route": at},
                    "pose": pose, "checks": rows})
    if args["attach"] == "choreo_subtrack":
        span = [0, display_frame(seg["end"] - seg["start"], tick, fps)[0]]
    else:
        span = [display_frame(seg["start"], tick, fps)[0], display_frame(seg["end"], tick, fps)[0]]
    return {"attach": args["attach"], "length_s": round(length_s, 4), "segment": [seg["start"], seg["end"]],
            "rates": {"tick": tick, "fps": fps}, "span_frames": span, "sensor_mm": sensor, "bursts": out,
            "refusals": refusals, "warnings": warnings}


def drift_check(record, live_seg, tol_ticks=8):
    """master_bindings only: the recorded P06 start vs the live one (passage_speed_probe.py SECTION_READ_TOL_TICKS)."""
    if not record or not record.get("applied") or record.get("plan", {}).get("attach") != "master_bindings":
        return None
    d = int(live_seg["start"]) - int(record["plan"]["segment"][0])
    return {"recorded_start": record["plan"]["segment"][0], "live_start": live_seg["start"], "delta_ticks": d,
            "drifted": abs(d) > tol_ticks}


def live_gates(state):
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode != "DRY" and state.get("confirm") != "%s %s" % (mode, CONFIRM_WORD):
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s %s" % (mode, CONFIRM_WORD)))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("wrong_world"):
        r.append("WRONG_WORLD: %s" % state["wrong_world"])
    if state.get("sequencer_open"):
        r.append("SEQUENCER_OPEN: %s (close it; opening/scrubbing dirties the map)" % state["sequencer_open"])
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode == "APPLY":
        if not str(state.get("decided_by") or "").strip():
            r.append("NOT_DECIDED: args decided_by is empty")
        if state.get("attach") == "choreo_subtrack" and not str(state.get("cueing_ack") or "").strip():
            r.append("CUEING_ACK_MISSING: LS_Choreo_Passage_6 is the cueing stream's file")
        if state.get("record_exists"):
            r.append("RECORD_EXISTS: %s (REVERT first)" % state["record_exists"])
        if state.get("glints_exists") and state.get("attach") == "choreo_subtrack":
            r.append("GLINTS_SEQUENCE_EXISTS: %s" % state["glints_exists"])
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


def census_gate(census, want_content, want_maps):  # klara_void_s6.py:598-604 [prec]
    out = []
    if sorted(census.get("content") or []) != sorted(want_content):
        out.append("CONTENT_CENSUS: got %s want %s" % (sorted(census.get("content") or []), sorted(want_content)))
    if sorted(census.get("maps") or []) != sorted(want_maps):
        out.append("MAP_CENSUS: got %s want %s" % (sorted(census.get("maps") or []), sorted(want_maps)))
    return out


def expected_state(plan, args):
    """What the read-back must equal after APPLY (spawn keys, poses, NS asset; the sub-section for choreo)."""
    rows = []
    for b in plan["bursts"]:
        rows.append({"name": b["name"], "system": args["system"], "spawn_keys": [[b["frames"][0], True],
                                                                                  [b["frames"][1], False]],
                     "loc": [round(x, 1) for x in b["pose"]["loc"]], "rot": [round(x, 3) for x in b["pose"]["rot"]],
                     "scale": [round(x, 4) for x in b["pose"]["scale"]]})
    out = {"glints": rows}
    if plan["attach"] == "choreo_subtrack":
        out["subtrack"] = {"name": SUBTRACK_NAME, "sequence": args["glints_sequence"], "range": plan["span_frames"]}
    return out


def write_record_exclusive(path, data):           # klara_void_s6.py:607-612 [prec]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):                     # klara_void_s6.py:615-621 [prec]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load_record(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "Effects_20261007")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _file(path):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _gs(guid):
    return unreal.GuidLibrary.conv_guid_to_string(guid)   # memory: str(Guid) carries an address


def _sequencer_open():
    cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    return _path(cur) if cur is not None else None


def _backup(run, files):                           # klara_void_s6.py:696-711 [prec]
    folder = os.path.join(_project(), "Backups", "PreP06BeeGlints-%s" % run)
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for src in files:
        if not os.path.isfile(src):
            _stop(run, "BACKUP_SOURCE_MISSING|" + src)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _api_table():
    rows = []

    def probe(api, tier, fn):
        try:
            res = fn()
            rows.append({"api": api, "tier": tier, "ok": bool(res), "result": repr(res)[:160]})
        except Exception as exc:  # noqa: BLE001 - a probe failure is a finding
            rows.append({"api": api, "tier": tier, "ok": False, "result": "%s: %s" % (type(exc).__name__, exc)})

    u = unreal
    probe("InfinityStageCameraRig.get_camera_view_at_master_frame", "decl InfinityStageCameraRig.h:355-360; prec "
          "passage_speed_probe.py:233", lambda: hasattr(u.InfinityStageCameraRig, "get_camera_view_at_master_frame"))
    probe("LevelSequence.add_spawnable_from_class", "decl MovieSceneSequenceExtensions.h:435; prec "
          "klara_void_s6.py:1343", lambda: hasattr(u.LevelSequence, "add_spawnable_from_class"))
    probe("NiagaraComponent.set_asset", "prec klara_void_s6.py:1351 (DRY-probed there, not yet run)",
          lambda: hasattr(u.NiagaraComponent, "set_asset"))
    probe("MovieSceneSpawnTrack", "prec klara_void_s6.py:1114", lambda: hasattr(u, "MovieSceneSpawnTrack"))
    probe("MovieSceneSubTrack", "prec CodexCameraPilot/key_scene4_score.py:148", lambda: hasattr(u, "MovieSceneSubTrack"))
    probe("LevelSequence.remove_track", "decl MovieSceneSequenceExtensions.h:89 (return value LIES: read back)",
          lambda: hasattr(u.LevelSequence, "remove_track"))
    probe("LevelSequence.set_playback_end", "decl MovieSceneSequenceExtensions.h:228",
          lambda: hasattr(u.LevelSequence, "set_playback_end"))
    probe("LevelSequenceFactoryNew", "prec CodexCueing/choreo_tool.py:180", lambda: hasattr(u, "LevelSequenceFactoryNew"))
    probe("MovieSceneTimeUnit.DISPLAY_RATE", "prec klara_void_s6.py:1125",
          lambda: repr(u.MovieSceneTimeUnit.DISPLAY_RATE))
    return rows


def _segment(show, label):
    tr = unreal.new_object(unreal.InfinityStageTransportController)   # transient, never saved [prec probe:100-104]
    tr.build_segments(show)
    hits = [{"label": str(s.get_editor_property("label")), "start": int(s.get_editor_property("start_frame").value),
             "end": int(s.get_editor_property("end_frame").value)} for s in tr.get_editor_property("segments")
            if str(s.get_editor_property("label")) == label]
    return hits


def _passage_guid(show, label):
    rows = [p for p in show.get_editor_property("passage_settings") if str(p.get_editor_property("label")) == label]
    return [_gs(p.get_editor_property("passage_guid")) for p in rows]


def _p06_actors(show, guid):
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    pa = []
    for a in actors:
        if a.get_class().get_name() == "InfinityStagePassageActor":
            try:
                if _gs(a.get_editor_property("passage_guid")) == guid and a.get_editor_property("show_asset") == show:
                    pa.append(a)
            except Exception:  # noqa: BLE001
                continue
    rigs = [a for a in actors if a.get_class().get_name() == "InfinityStageCameraRig" and pa
            and a.get_editor_property("passage_actor") == pa[0]]
    return pa, rigs


def _view_fn(rig):
    def view(abs_ticks):
        res = rig.get_camera_view_at_master_frame(unreal.FrameNumber(int(abs_ticks)))
        if isinstance(res, tuple):                 # out-params come back as a tuple [prec p02_straighten.py:432-441]
            if res and isinstance(res[0], bool):
                if not res[0]:
                    return None
                res = res[1:]
            xf = next((r for r in res if isinstance(r, unreal.Transform)), None)
            floats = [float(r) for r in res if isinstance(r, float)]
        else:
            xf, floats = (res if isinstance(res, unreal.Transform) else None), []
        if xf is None:
            return None
        rot = xf.rotation.rotator()
        return {"loc": [float(xf.translation.x), float(xf.translation.y), float(xf.translation.z)],
                "rot": [float(rot.roll), float(rot.pitch), float(rot.yaw)],
                "focal": floats[0] if floats and floats[0] > 1.0 else 35.0}
    return view


def _route_points(passage_actor):
    route = passage_actor.get_editor_property("route")      # prec place_p06_car_light.py:111
    W = unreal.SplineCoordinateSpace.WORLD
    L = float(route.get_spline_length())
    n = max(2, int(math.ceil(L / ROUTE_STEP_CM)) + 1)
    pts = []
    for i in range(n):
        p = route.get_location_at_distance_along_spline(L * i / float(n - 1), W)
        pts.append([float(p.x), float(p.y), float(p.z)])
    return pts, L


def _sensor_mm(rig):
    try:
        cc = rig.get_component_by_class(unreal.CineCameraComponent)
        fb = cc.get_editor_property("filmback")
        return min(float(fb.get_editor_property("sensor_width")), float(fb.get_editor_property("sensor_height")))
    except Exception:  # noqa: BLE001 - falls back to limits.sensor_width_mm_default, reported
        return None


def _glints_state(seq):
    """Our bindings in seq: name, NS asset, spawn keys (display frames), constant pose."""
    rows = []
    for b in seq.get_bindings():
        name = str(b.get_display_name())
        if not is_ours(name):
            continue
        row = {"name": name, "system": None, "spawn_keys": [], "loc": None, "rot": None, "scale": None}
        try:
            nc = b.get_object_template().get_editor_property("niagara_component")
            row["system"] = _path(nc.get_asset())
        except Exception:  # noqa: BLE001
            pass
        for t in b.get_tracks():
            cls = t.get_class().get_name()
            for s in t.get_sections():
                chans = list(s.get_all_channels())
                if cls == "MovieSceneSpawnTrack" and chans:
                    row["spawn_keys"] = [[int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                                              .frame_number.value), bool(k.get_value())] for k in chans[0].get_keys()]
                elif cls == "MovieScene3DTransformTrack":
                    d = {}
                    for c in chans:
                        nm = str(c.channel_name if hasattr(c, "channel_name") else c.get_name())
                        d[nm.rsplit("_", 1)[0] if nm.rsplit("_", 1)[-1].isdigit() else nm] = float(c.get_default())
                    row["loc"] = [round(d.get("Location." + a, float("nan")), 1) for a in "XYZ"]
                    row["rot"] = [round(d.get("Rotation." + a, float("nan")), 3) for a in "XYZ"]
                    row["scale"] = [round(d.get("Scale." + a, float("nan")), 4) for a in "XYZ"]
        rows.append(row)
    rows.sort(key=lambda r: r["name"])
    return rows


def _subtrack_state(choreo, glints_path):
    rows = []
    for t in choreo.get_tracks():
        if t.get_class().get_name() != "MovieSceneSubTrack":
            continue
        for s in t.get_sections():
            if _path(s.get_sequence()) == glints_path or str(t.get_display_name()) == SUBTRACK_NAME:
                rows.append({"name": str(t.get_display_name()), "sequence": _path(s.get_sequence()),
                             "range": [int(s.get_start_frame()), int(s.get_end_frame())]})
    return rows


def _choreo_summary(choreo):
    return {"tracks": sorted("%s|%s|%d" % (t.get_class().get_name(), t.get_display_name(), len(t.get_sections()))
                             for t in choreo.get_tracks()),
            "bindings": len(choreo.get_bindings()),
            "playback": [float(choreo.get_playback_start_seconds()), float(choreo.get_playback_end_seconds())],
            "fps": _rate(choreo.get_display_rate()), "tick": _rate(choreo.get_tick_resolution())}


def _facts(args):
    show = unreal.load_asset(SHOW_PATH)
    master = unreal.load_asset(args["master"])
    choreo = unreal.load_asset(args["choreo"])
    if show is None or master is None or choreo is None:
        raise PlanError("LOAD: show=%s master=%s choreo=%s" % (show is not None, master is not None, choreo is not None))
    segs = _segment(show, args["passage_label"])
    guids = _passage_guid(show, args["passage_label"])
    if len(segs) != 1 or len(guids) != 1:
        raise PlanError("P06_NOT_UNIQUE: segments=%d settings=%d" % (len(segs), len(guids)))
    if args.get("passage_guid") and guids[0] != args["passage_guid"]:
        raise PlanError("P06_GUID: live %s args %s" % (guids[0], args["passage_guid"]))
    pa, rigs = _p06_actors(show, guids[0])
    if len(pa) != 1 or len(rigs) != 1:
        raise PlanError("P06_ACTORS: passage=%d rigs=%d" % (len(pa), len(rigs)))
    pts, route_len = _route_points(pa[0])
    target = choreo if args["attach"] == "choreo_subtrack" else master
    master_tick = _rate(master.get_tick_resolution())
    return {"show": show, "master": master, "choreo": choreo, "seg": segs[0], "guid": guids[0], "passage_actor": pa[0],
            "rig": rigs[0], "route_points": pts, "route_len": route_len,
            "rates": {"tick": master_tick, "fps": _rate(target.get_display_rate())},
            "target_tick": _rate(target.get_tick_resolution()), "sensor_mm": _sensor_mm(rigs[0]),
            "choreo_summary": _choreo_summary(choreo)}


def _plan(args, f):
    plan = plan_glints(args, f["seg"], _view_fn(f["rig"]), f["route_points"], f["rates"], f["sensor_mm"],
                       f["choreo_summary"]["playback"][1] if args["attach"] == "choreo_subtrack" else None)
    if args["attach"] == "choreo_subtrack" and abs(f["choreo_summary"]["tick"] - f["rates"]["tick"]) > 1e-6:
        plan["warnings"].append("CHOREO_TICK %.0f != Master %.0f (frames are display frames; still exact)"
                                % (f["choreo_summary"]["tick"], f["rates"]["tick"]))
    return plan


def run_dry(args, run, world):
    census0 = _census()
    report = {"tool": TOOL, "run": run, "mode": "DRY", "args": args, "api_table": _api_table()}
    f = _facts(args)
    plan = _plan(args, f)
    loads = {p: unreal.EditorAssetLibrary.does_asset_exist(p) for p in (args["system"],)}
    rpath = os.path.join(_here(), RECORD_NAME)
    rec = load_record(rpath) if os.path.exists(rpath) else None
    report.update(segment=f["seg"], passage_guid=f["guid"], rig=str(f["rig"].get_actor_label()),
                  passage_actor=str(f["passage_actor"].get_actor_label()), route_len_cm=f["route_len"],
                  sensor_mm_live=f["sensor_mm"], choreo=f["choreo_summary"], plan=plan, loads=loads,
                  master_ours=[r["name"] for r in _glints_state(f["master"])],
                  choreo_subtrack=_subtrack_state(f["choreo"], args["glints_sequence"]),
                  glints_exists=unreal.EditorAssetLibrary.does_asset_exist(args["glints_sequence"]),
                  applied_record=bool(rec and rec.get("applied")), drift=drift_check(rec, f["seg"]),
                  expected_after=expected_state(plan, args))
    blockers = list(plan["refusals"])
    if not all(loads.values()):
        blockers.append("ASSET_MISSING %s" % loads)
    if [r for r in report["api_table"] if not r["ok"]]:
        blockers.append("API_TABLE")
    if not rec and (report["master_ours"] or report["choreo_subtrack"]):
        blockers.append("FOREIGN_GLINTS_PRESENT without a record")
    report["census_before"], report["census_after"] = census0, _census()
    if report["census_after"] != census0:
        blockers.append("DRY_DIRTIED %s" % report["census_after"])
    report["blockers"] = blockers
    report["apply_ready"] = not blockers and not report["applied_record"]
    path = os.path.join(_here(), DRY_NAME)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str)
    unreal.log("%s_DRY_OK|run=%s|apply_ready=%d|attach=%s|p06=%s|bursts=%s|blockers=%d|drift=%s|json=%s"
               % (MARK, run, int(report["apply_ready"]), args["attach"], f["seg"],
                  [(b["t_s"], b["frames"], [round(x) for x in b["pose"]["loc"]]) for b in plan["bursts"]],
                  len(blockers), report["drift"], path))


def _const_transform(b, pose, rng, run, label):   # klara_void_s6.py:1093-1111 [prec]
    tr = b.add_track(unreal.MovieScene3DTransformTrack)
    if tr is None:
        _stop(run, "ADD_TRANSFORM_TRACK|%s|NOTHING SAVED; Don't-Save restart" % label)
    s = tr.add_section()
    s.set_range(int(rng[0]), int(rng[1]))
    cm = {}
    for c in s.get_all_channels():
        nm = str(c.channel_name if hasattr(c, "channel_name") else c.get_name())
        cm[nm.rsplit("_", 1)[0] if nm.rsplit("_", 1)[-1].isdigit() else nm] = c
    vals = {"Location.X": pose["loc"][0], "Location.Y": pose["loc"][1], "Location.Z": pose["loc"][2],
            "Rotation.X": pose["rot"][0], "Rotation.Y": pose["rot"][1], "Rotation.Z": pose["rot"][2],
            "Scale.X": pose["scale"][0], "Scale.Y": pose["scale"][1], "Scale.Z": pose["scale"][2]}
    for n, v in vals.items():
        if n not in cm:
            _stop(run, "CHANNEL_MISSING|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, n))
        cm[n].set_default(float(v))
        if abs(float(cm[n].get_default()) - float(v)) > 1e-3 * max(1.0, abs(v)):
            _stop(run, "CONST_POSE_READBACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (label, n))


def _spawn_track(b, rng, keys):                   # klara_void_s6.py:1114-1127 [prec]
    existing = [t for t in b.get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"]
    st = existing[0] if existing else b.add_track(unreal.MovieSceneSpawnTrack)
    for extra in existing[1:]:
        b.remove_track(extra)
    for old in list(st.get_sections()):
        st.remove_section(old)
    ss = st.add_section()
    ss.set_range(int(rng[0]), int(rng[1]))
    ch = ss.get_all_channels()[0]
    ch.set_default(False)
    for frame, value in keys:
        ch.add_key(unreal.FrameNumber(int(frame)), bool(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)


def _build_bursts(seq, plan, args, run):
    ns = unreal.load_asset(args["system"])
    if ns is None:
        _stop(run, "SYSTEM_LOAD|%s|NOTHING SAVED; Don't-Save restart" % args["system"])
    for bp in plan["bursts"]:
        b = seq.add_spawnable_from_class(unreal.NiagaraActor)
        if b is None or not b.is_valid():
            _stop(run, "SPAWNABLE|%s|NOTHING SAVED; Don't-Save restart" % bp["name"])
        b.set_display_name(bp["name"])
        nc = b.get_object_template().get_editor_property("niagara_component")
        if nc is None:
            _stop(run, "TEMPLATE|%s|NOTHING SAVED; Don't-Save restart" % bp["name"])
        nc.set_asset(ns)
        _spawn_track(b, plan["span_frames"], [(bp["frames"][0], True), (bp["frames"][1], False)])
        _const_transform(b, bp["pose"], plan["span_frames"], run, bp["name"])


def _after_state(args, plan):
    target = args["glints_sequence"] if plan["attach"] == "choreo_subtrack" else args["master"]
    out = {"glints": [{k: r[k] for k in ("name", "system", "spawn_keys", "loc", "rot", "scale")}
                      for r in _glints_state(unreal.load_asset(target))]}
    if plan["attach"] == "choreo_subtrack":
        st = _subtrack_state(unreal.load_asset(args["choreo"]), args["glints_sequence"])
        out["subtrack"] = st[0] if len(st) == 1 else st
    return out


def _close(a, b):
    """Read-back compare: exact for names/keys/paths/ints; floats (rows already rounded) within 0.11."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= 0.11
    return a == b


def run_apply(args, run, world):
    f = _facts(args)
    plan = _plan(args, f)
    if plan["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(plan["refusals"]))
    choreo_mode = plan["attach"] == "choreo_subtrack"
    if _glints_state(f["master"]) or _subtrack_state(f["choreo"], args["glints_sequence"]):
        _stop(run, "GLINTS_ALREADY_PRESENT|nothing changed")
    rpath = os.path.join(_here(), RECORD_NAME)
    edited = args["choreo"] if choreo_mode else args["master"]
    backup = _backup(run, [_file(edited)])
    want = expected_state(plan, args)
    rec = {"schema": 1, "tool": TOOL, "run": run, "mode": "APPLY", "backup": backup, "applied": False,
           "decided_by": args.get("decided_by"), "cueing_ack": args.get("cueing_ack"),
           "written": datetime.datetime.now().isoformat(timespec="seconds"), "args": args, "plan": plan,
           "created": None, "before": {"choreo": f["choreo_summary"], "master_ours": [],
                                       "choreo_subtrack": []}, "expected_after": want}
    write_record_exclusive(rpath, rec)
    if choreo_mode:
        folder, name = args["glints_sequence"].rsplit("/", 1)
        seq = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, unreal.LevelSequence,
                                                                      unreal.LevelSequenceFactoryNew())
        if seq is None:
            _stop(run, "CREATE_FAILED|%s" % args["glints_sequence"])
        rec["created"] = args["glints_sequence"]
        update_record(rpath, rec)
        seq.set_tick_resolution(f["choreo"].get_tick_resolution())     # prec choreo_tool.py:183-184
        seq.set_display_rate(f["choreo"].get_display_rate())
        seq.set_playback_start(0)
        seq.set_playback_end(int(plan["span_frames"][1]))
        _build_bursts(seq, plan, args, run)
        st = f["choreo"].add_track(unreal.MovieSceneSubTrack)          # prec key_scene4_score.py:148-152
        st.set_display_name(SUBTRACK_NAME)
        sec = st.add_section()
        sec.set_sequence(seq)
        sec.set_range(int(plan["span_frames"][0]), int(plan["span_frames"][1]))
        want_dirty = [args["choreo"], args["glints_sequence"]]
    else:
        _build_bursts(f["master"], plan, args, run)
        want_dirty = [args["master"]]
    after = _after_state(args, plan)
    if not _close(after, want):
        _stop(run, "APPLY_READBACK|got %s|NOTHING SAVED; Don't-Save restart (backup %s)"
              % (json.dumps(after, default=str)[:700], backup))
    if choreo_mode and _choreo_summary(f["choreo"])["tracks"] != sorted(
            f["choreo_summary"]["tracks"] + ["MovieSceneSubTrack|%s|1" % SUBTRACK_NAME]):
        _stop(run, "CHOREO_OTHER_TRACKS_CHANGED|NOTHING SAVED; Don't-Save restart (backup %s)" % backup)
    gate = census_gate(_census(), want_dirty, [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (gate, backup))
    for pth in ([args["glints_sequence"]] if choreo_mode else []) + [edited]:
        if not unreal.EditorAssetLibrary.save_asset(pth, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % pth)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    after2 = _after_state(args, plan)
    if not _close(after2, want):
        _stop(run, "POST_SAVE_READBACK|%s" % json.dumps(after2, default=str)[:700])
    rec.update(applied=True, after=after2)
    update_record(rpath, rec)
    unreal.log("%s_APPLY_OK|run=%s|attach=%s|bursts=%s|saved=%s|backup=%s|record=%s"
               % (MARK, run, plan["attach"], [(b["t_s"], b["frames"]) for b in plan["bursts"]],
                  ([args["glints_sequence"]] if choreo_mode else []) + [edited], backup, rpath))


def run_revert(args, run, world):
    rpath = os.path.join(_here(), RECORD_NAME)
    rec = load_record(rpath)
    plan, a = rec["plan"], rec["args"]
    choreo_mode = plan["attach"] == "choreo_subtrack"
    live = _after_state(a, plan)
    if not _close(live, rec["expected_after"]):
        _stop(run, "STATE_DRIFTED|live %s|nothing changed" % json.dumps(live, default=str)[:600])
    if choreo_mode:
        choreo = unreal.load_asset(a["choreo"])
        mine = [t for t in choreo.get_tracks() if t.get_class().get_name() == "MovieSceneSubTrack"
                and str(t.get_display_name()) == SUBTRACK_NAME
                and [_path(s.get_sequence()) for s in t.get_sections()] == [a["glints_sequence"]]]
        if len(mine) != 1:
            _stop(run, "SUBTRACK_NOT_UNIQUE|%d|nothing changed" % len(mine))
        choreo.remove_track(mine[0])                   # return value lies (memory): read back below
        if _subtrack_state(choreo, a["glints_sequence"]) or _choreo_summary(choreo)["tracks"] != \
                rec["before"]["choreo"]["tracks"]:
            _stop(run, "REVERT_READBACK|NOTHING SAVED; Don't-Save restart")
        want_dirty, save = [a["choreo"]], a["choreo"]
    else:
        master = unreal.load_asset(a["master"])
        for b in [x for x in master.get_bindings() if is_ours(x.get_display_name())]:
            b.remove()                                 # prec klara_void_s6.py:1484-1486
        if _glints_state(master):
            _stop(run, "REVERT_READBACK|NOTHING SAVED; Don't-Save restart")
        want_dirty, save = [a["master"]], a["master"]
    gate = census_gate(_census(), want_dirty, [])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % gate)
    if not unreal.EditorAssetLibrary.save_asset(save, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|%s" % save)
    deleted = []
    c = rec.get("created")
    if c and unreal.EditorAssetLibrary.does_asset_exist(c):
        refs = [str(x) for x in unreal.EditorAssetLibrary.find_package_referencers_for_asset(c, False)]
        if refs:
            unreal.log_warning("%s_GLINTS_KEPT|run=%s|%s|referenced by %s" % (MARK, run, c, refs))
        elif unreal.EditorAssetLibrary.delete_asset(c) and not unreal.EditorAssetLibrary.does_asset_exist(c):
            deleted.append(c)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_REVERT|%s" % json.dumps(_census()))
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("%s_REVERT_OK|run=%s|attach=%s|saved=%s|deleted=%s" % (MARK, run, plan["attach"], save, deleted))


def main():
    args = globals().get("P06BEEGLINTS_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("P06BEEGLINTS-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie = editor.get_game_world() is not None
    world = None if pie else editor.get_editor_world()
    wname = str(world.get_outermost().get_name()) if world is not None else None
    rpath = os.path.join(_here(), RECORD_NAME)
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": pie, "attach": args.get("attach"),
             "cueing_ack": args.get("cueing_ack"),
             "wrong_world": None if wname == EXPECTED_WORLD else str(wname),
             "sequencer_open": None if pie else _sequencer_open(), "census": _census(),
             "decided_by": args.get("decided_by"), "record_exists": rpath if os.path.exists(rpath) else None,
             "record_applied": os.path.exists(rpath) and bool(load_record(rpath).get("applied")),
             "glints_exists": args["glints_sequence"] if unreal.EditorAssetLibrary.does_asset_exist(
                 args["glints_sequence"]) else None}
    early = live_gates(state)
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[mode](args, run, world)
    except PlanError as exc:
        _stop(run, "PLAN|" + str(exc))


if unreal is not None and __name__ != "__p06_bee_glints_import__":
    main()
