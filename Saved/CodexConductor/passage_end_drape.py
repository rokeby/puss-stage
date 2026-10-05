"""PASSAGE-END STAND-IN DRAPE (5 Oct, offline-written, NEVER RUN IN UNREAL).

Gary, 5 Oct (questionnaire, his own click; Docs/Conductor/GARY_PIE_NOTES_2026-10-05.md:37-38): "Stand-in drape falls:
the baked red velvet drape hangs at each passage end and falls as the hangar starts rising, hiding the crossing until
the painted end curtains replace it. P06 excluded."  Scope: Scenes S1-S5 (= the ends of P01-P05).

MECHANISM (why not a spawnable). Tiers: [decl] read in a header/source/record (cited), [prec] an in-repo precedent call
(cited, with whether it ran), [meas] intervention + read-back, [inf] inferred.
  * The drape must be visible DURING the Passage tail, before the Scene's first frame. A Scene-sequence spawnable cannot
    be: Sequencer evaluates a Scene's sequence only from the Scene's first frame on [decl InfinityStageArrival.h:108-111;
    meas 30 Sep "Sequencer does not evaluate before the playback start (0)", RigAndAtmosphere_Handover_2026-09-28.md:683].
    Starting it "slightly before" would mean moving the Scene's Master section start = changing the Scene's playback
    range, which this tool must never do.
  * A key in the Passage's Choreo (LS_Choreo_Passage_N) is anchored to the PASSAGE START ("Its 0:00 is the Passage
    start", Docs/Conductor/CUEING_MORNING_CHECKLIST_2026-10-05.md:6 [decl]). The fall must follow the hangar rise, which
    is anchored to the SCENE start (the rise keys live in LS_S<n>_HangarRise, nested in the Scene [decl
    Saved/CodexStructure/nest_s*_record.json]). Lengthening a Passage would slide a Choreo release away from the rise
    [inf from the two anchors]. A Choreo spawnable would also despawn at the Passage end, with the pile still in view.
  * CHOSEN: a LEVEL GeometryCacheActor at the passage end + ONE GeometryCache section in LS_S<n>_HangarRise at negative
    time, played by S<n> Arrival before the cut and by Sequencer after it. This is the Arrival's declared backcloth slot
    [decl InfinityStageArrival.h:180-189, 198-206; .cpp:1161-1182 MapTimeToAnimation, 1256-1272 TickAtThisTime every
    Passage frame], driven from every Passage frame [decl MovieSceneInfinityPassageTrack.cpp:190-198]. It is exactly
    how the P04 backcloth was integrated [prec Saved/CodexStructure/p04_backcloth_section_apply.py:203-238, applied
    30 Sep; its revert ran, p04_backcloth_section_record.json.reverted]. Gary's "we had that once already" is that cloth
    [inf].
  * RETIME: the Arrival recompiles the Show on every call and maps Master -> Scene -> motion time from the compiled
    Scene segment start [decl InfinityStageArrival.cpp:1097-1125]. The drape's section and the rise's root-pitch keys
    sit in the SAME motion sequence, so any shift of the Scene (a Passage or earlier segment growing) moves the release
    with the rise, rigidly ("retime shifts, never stretches"). No Scene, Master or Show asset is touched, so no playback
    range changes and no Master rebuild is needed; APPLY asserts the Scene and rise ranges read back unchanged.
  * The Arrival owns ONE backcloth [decl InfinityStageArrival.h:184-189]. S4's slot holds "P04 Backcloth (baked)"
    (final11, Rig/Soft goods) [decl RigAndAtmosphere_Handover_2026-09-28.md "P04 backcloth is integrated"], so S4 is
    REFUSED (BACKCLOTH_SLOT_TAKEN): P04 already has its passage-end cloth; replacing it is a separate decision.

POSE (the dock frame = the LANDED hangar root: origin at the hinge, +X into the hangar, yaw only; curtain_sleight.py
_gather [prec, applied 5 Oct]).
  The drape stands in the passage apron between the camera stop (root x = -500, measured 5 Oct
  curtain_sleight_I1_dry.json hangar.dock_local) and the hinge (x = 0). Its curtain line is placed so the WHOLE PILE
  (the bake's last checkpoint) ends hinge_margin_cm before the hinge: past the hinge there is no floor until the box
  lands (planes trimmed at the hinge, Handover "Planes trimmed"), and the near end of the box sweeps the quadrant above
  the floor beyond the hinge while it rises [inf from the -90 -> 0 root pitch about the hinge, InfinityStageArrival.cpp
  ValidateStandardShape]. Facing: the root yaw (= the route end tangent = the Entry Handoff camera yaw, all asserted).
  Floor: composed at the root (= the hinge; doors-record hinge_z is the root z) + floor_offset_cm, then CHECKED against the Passage actor's floor z
  (fit_transition_drapes.py mouth_of precedent) and the landed root from hangar_exit_doors_record.json: composing via a
  REST (pitch -90) or sunk root fails the guard (memory puss-level-saved-landed-frame-trap).

TIMING (motion time = LS_S<n>_HangarRise's own seconds; 0 = the Scene's first frame when nested at 0 with no offset).
  rise_start = the first key of the root binding's pitch channel (the Arrival's MotionBindingGuid; two-key -90 -> 0
  shape [decl InfinityStageArrival.cpp ValidateStandardShape]).   release = rise_start - lead_s (default 0).
  Section (P04 HOLD_PRE_RELEASE layout [prec p04_backcloth_section_apply.py:48-52, 157-161]):
      start = release - 1 cache frame, start_frame_offset = release_in_cache - 1 cache frame (the last pre-release
      sample; the engine clamps to it before the section), length = duration - offset (cannot loop), KeepState.
  release_in_cache and the hang/pile AABBs are read from the cache's own artifact chain (DropBake/<bake_id>.json),
  never typed (memory puss-bake-facts-from-artifact-chain).

Modes (globals set by passage_end_drape_run.py from passage_end_drape_args.json):
  PASSAGE_END_DRAPE_SCENE int 1..5, PASSAGE_END_DRAPE_MODE "DRY"|"APPLY"|"REVERT",
  PASSAGE_END_DRAPE_CONFIRM must equal "<MODE> S<n>", PASSAGE_END_DRAPE_PARAMS dict, PASSAGE_END_DRAPE_RUN_ID optional.
Markers: PASSAGE_END_DRAPE_DRY_OK / _APPLY_OK / _REVERT_OK |run=..|scene=S<n>|..., or PASSAGE_END_DRAPE_STOPPED|run=..|
reason=... Never Save All, never end PIE, never reload the level, no Sequencer UI, no unreal objects in module globals.
Touches ONLY LS_S<n>_HangarRise and the level. Importing without `unreal` runs nothing (test_passage_end_drape.py).
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


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
RISE_PATH = "/Game/InfinityStage/RigAtmos/LS_S%d_HangarRise"
GC_PATH = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"          # fit_transition_drapes.py:30
SCENES = (1, 2, 3, 4, 5)                                                 # Gary: P01-P05, P06 excluded
SCENE_CUE_PREFIX = "Scene %d — "
PASSAGE_LABEL = "Passage %d"                                             # show passage_settings label
PASSAGE_ACTOR = "Passage %02d — Fixed Wings"                             # fit_transition_drapes.py:58
ARRIVAL_LABEL = "S%d Arrival"                                            # atf_hangar_timing_apply.py:124
ROOT_LABEL = "S%d Hangar Root"
DRAPE_LABEL = "P%02d End Drape (stand-in)"
TAGS = ("PassageEndDrape", "PassageEndDrape.S%d")
FOLDER = "InfinityStage/Curtains"                                        # import_passing_bake.py:281
ENTRY_TAG = "InfinityStage.SceneEntry"                                   # builder .cpp:95; capture_p1_s1_handoff.py
DOORS_RECORD = "hangar_exit_doors_record.json"
BAKE_DIR = os.path.join("CodexSoftGoods", "DropBake")
CS_FILE = "curtain_sleight.py"
RECORD_PATTERN = "passage_end_drape_record_S%d.json"
PLAN_PATTERN = "passage_end_drape_plan_S%d.json"
DRY_PATTERN = "passage_end_drape_S%d_dry.json"
CACHE_FPS = 30.0                                                         # Soft goods' bake rate
SHOW_TICKS_PER_S = 24000.0                                               # curtain_sleight.py:92
GC_TRACK = "MovieSceneGeometryCacheTrack"
SPAWN_TRACK = "MovieSceneSpawnTrack"
REQUIRED_TESTS = "InfinityStage.Editor.SavedMasterMatchesShow,InfinityStage.Editor.SceneCutBindingsResolve"

DEFAULTS = {
    "lead_s": 0.0,                 # release = rise start - lead (Gary: "falls as the hangar starts rising")
    "max_lead_s": 1.0,             # refuse a release more than this before the rise start
    "hinge_margin_cm": 20.0,       # the pile's far edge ends this far before the hinge
    "line_x_cm": None,             # None = derived from the pile; else an explicit curtain line (root x)
    "floor_offset_cm": 0.0,        # drape floor = the hinge (root z) + this (S3 needs a recorded site decision)
    "floor_tol_cm": 10.0,          # composed floor vs the Passage actor floor and the hinge
    "back_limit_cm": 1500.0,       # nothing further than apron + this before the hinge ("at the passage end")
    "apron_cm": 500.0,             # hangar_s<N>_plan.json "apron"; dock = hinge - apron [meas I1 DRY dock_local]
    "pile_lateral_allow_cm": 150.0,  # the pile may spill this far past the hangar half width (floor level)
    "route_end_tol_cm": 60.0,      # live route end vs the dock frame (lateral / along)
    "yaw_tol_deg": 0.5,            # route end tangent / Entry camera vs the drape facing
    "entry_tol_cm": 25.0,          # Entry Handoff camera vs the Passage camera at the stop (warning only; note 6)
    "landed_after_release_s": 2.5,  # fit_transition_drapes.py:46 (estimate, [decl] as a constant)
    "clear_margin_s": 0.5,         # the camera reaches the hang front at least this long after the cloth is down
    "min_view_cm": 300.0,          # the camera is at least this far in front of the hang front at the release
    "min_eye_over_pile_cm": 30.0,  # camera eye above the pile top where the camera stops over the pile
    "root_tol_cm": 0.5, "root_tol_deg": 0.05,   # curtain_sleight.py:93-94 ROOT_NOT_LANDED
    "sample_step_s": 0.1,          # Passage camera sampling for the crossing time
}


class PlanError(ValueError):
    pass


# =====================================================================================================================
# Pure geometry (UE conventions: X forward, Y right, Z up; FRotationMatrix with roll 0)
# =====================================================================================================================

def wrap(deg):
    return (float(deg) + 180.0) % 360.0 - 180.0


def axes(pitch, yaw):
    p, y = math.radians(float(pitch)), math.radians(float(yaw))
    cp, sp, cy, sy = math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return [cp * cy, cp * sy, sp], [-sy, cy, 0.0], [-sp * cy, -sp * sy, cp]


def frame_of(loc, rot):
    """rot = [roll, pitch, yaw] (the doors-record order). Roll must be 0 (the guard checks it)."""
    return {"loc": [float(v) for v in loc], "roll": float(rot[0]), "pitch": float(rot[1]), "yaw": float(rot[2])}


def to_world(frame, p):
    x, y, z = axes(frame["pitch"], frame["yaw"])
    return [frame["loc"][i] + p[0] * x[i] + p[1] * y[i] + p[2] * z[i] for i in range(3)]


def to_local(frame, w):
    x, y, z = axes(frame["pitch"], frame["yaw"])
    d = [float(w[i]) - frame["loc"][i] for i in range(3)]
    return [sum(d[i] * a[i] for i in range(3)) for a in (x, y, z)]


def box_corners(lo, hi):
    return [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def box_in(frame_from, frame_to, lo, hi):
    """AABB, in frame_to, of a box given in frame_from (both world-anchored frames)."""
    pts = [to_local(frame_to, to_world(frame_from, c)) for c in box_corners(lo, hi)]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def interp_samples(samples, t, key):
    """Linear interpolation of passage-camera samples [(t, {...})] on field `key` (list or float)."""
    rows = sorted(samples, key=lambda r: r[0])
    if t <= rows[0][0]:
        return rows[0][1][key]
    for (ta, a), (tb, b) in zip(rows, rows[1:]):
        if ta <= t <= tb:
            u = 0.0 if tb == ta else (t - ta) / (tb - ta)
            if isinstance(a[key], list):
                return [a[key][i] + (b[key][i] - a[key][i]) * u for i in range(len(a[key]))]
            return a[key] + (b[key] - a[key]) * u
    return rows[-1][1][key]


def first_crossing(samples, frame, plane_x):
    """First time the camera's x (in `frame`) reaches plane_x, linearly interpolated; None if it never does."""
    rows = sorted(samples, key=lambda r: r[0])
    xs = [(t, to_local(frame, s["loc"])[0]) for t, s in rows]
    if xs[0][1] >= plane_x:
        return xs[0][0]
    for (ta, xa), (tb, xb) in zip(xs, xs[1:]):
        if xa < plane_x <= xb:
            return ta + (plane_x - xa) / (xb - xa) * (tb - ta)
    return None


def half_extent(distance_cm, focal_mm, filmback_mm):
    return distance_cm * filmback_mm[0] / 2.0 / focal_mm, distance_cm * filmback_mm[1] / 2.0 / focal_mm


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


# =====================================================================================================================
# Pure timing: the Scene <-> motion mapping and the GeometryCache section the engine will play
# =====================================================================================================================

def scene_to_motion(sub, scene_s):
    """InfinityStageArrival::MapOuterToInnerTime [decl Arrival.h:217-228]: inner start + offset + (outer - start) x rate."""
    return sub["inner_start_s"] + sub["start_offset_s"] + (scene_s - sub["section_start_s"]) * sub["rate"]


def motion_to_scene(sub, motion_s):
    return sub["section_start_s"] + (motion_s - sub["inner_start_s"] - sub["start_offset_s"]) / sub["rate"]


def map_time_to_animation(section, motion_s, duration_s):
    """Model of the GC section mapping for play rate 1, not reversed, not looping: before the section the engine
    clamps to the start offset (the held sample) [prec p04_backcloth_section_apply.py:48-51 + its 30 Sep read-back];
    after it, KeepState holds the end [inf]."""
    t = section["offset_s"] + (motion_s - section["start_s"])
    return max(section["offset_s"], min(duration_s, t))


def rise_start_of(keys):
    """Two-key -90 -> 0 root pitch (the Arrival's standard shape). Returns the first key time or raises."""
    if len(keys) != 2:
        raise PlanError("RISE_SHAPE: root pitch has %d keys, want 2 (-90 -> 0)" % len(keys))
    (t0, v0), (t1, v1) = sorted(keys)
    if abs(v0 + 90.0) > 1.0e-3 or abs(v1) > 1.0e-3 or not t1 > t0:
        raise PlanError("RISE_SHAPE: root pitch keys %r are not -90 -> 0" % (keys,))
    return float(t0), float(t1)


# =====================================================================================================================
# Pure planner
# =====================================================================================================================

def merged_params(params):
    unknown = sorted(set(params or {}) - set(DEFAULTS))
    if unknown:
        raise PlanError("UNKNOWN_PARAMS: %r" % unknown)
    out = dict(DEFAULTS)
    out.update(params or {})
    return out


def plan_drape(inputs, params):
    """Everything APPLY writes, as data. Deterministic (digest). Independent of the absolute Master time."""
    p = merged_params(params)
    n = int(inputs["n"])
    if n not in SCENES:
        raise PlanError("OUT_OF_SCOPE: S%d (Gary: P01-P05 only, P06 excluded)" % n)
    cache = inputs["cache"]
    hang, pile = cache["hang_aabb_cm"], cache["pile_aabb_cm"]
    root_live = frame_of(inputs["root_live"]["loc"], inputs["root_live"]["rot"])

    # ---- pose: curtain line in the dock (root) frame, composed against the LIVE root
    line_x = float(p["line_x_cm"]) if p["line_x_cm"] is not None else -(float(pile["x"][1]) + float(p["hinge_margin_cm"]))
    local = [line_x, 0.0, float(p["floor_offset_cm"])]      # the root IS the hinge (doors record hinge_z = root z)
    world = to_world(root_live, local)
    drape = {"loc": world, "pitch": root_live["pitch"], "yaw": wrap(root_live["yaw"]), "roll": root_live["roll"]}

    # ---- timing (motion seconds)
    sub = inputs["rise_sub"]
    m0, m_land = rise_start_of(inputs["rise"]["root_pitch_keys"])
    rise_start_scene = motion_to_scene(sub, m0)
    release_scene = rise_start_scene - float(p["lead_s"])
    release_motion = scene_to_motion(sub, release_scene)
    frame_s = 1.0 / CACHE_FPS
    tick = float(inputs["rise"]["tick_rate"])
    in_cache, duration = float(cache["release_in_cache_s"]), float(cache["duration_s"])
    offset_ticks = int(round((in_cache - frame_s) * tick))
    offset_s = offset_ticks / tick
    start_s = release_motion - frame_s
    length_s = duration - offset_s
    section = {"start_s": start_s, "end_s": start_s + length_s, "offset_s": offset_s, "offset_ticks": offset_ticks,
               "end_offset_ticks": 0, "length_s": length_s, "completion": "KeepState", "play_rate": 1.0}

    # ---- the camera against the drape (landed frame = the guard's independent reference)
    landed = frame_of(inputs["root_landed"]["loc"], inputs["root_landed"]["rot"])
    hang_lo_l, hang_hi_l = box_in(drape, landed, [hang["x"][0], hang["y"][0], hang["z"][0]],
                                  [hang["x"][1], hang["y"][1], hang["z"][1]])
    pile_lo_l, pile_hi_l = box_in(drape, landed, [pile["x"][0], pile["y"][0], pile["z"][0]],
                                  [pile["x"][1], pile["y"][1], pile["z"][1]])
    front_x = hang_lo_l[0]
    samples = inputs["passage_camera"]
    cam_rel = interp_samples(samples, release_scene, "loc")
    cam_rel_l = to_local(landed, cam_rel)
    cam_yaw_rel = interp_samples(samples, release_scene, "yaw")
    cam_pitch_rel = interp_samples(samples, release_scene, "pitch")
    focal_rel = interp_samples(samples, release_scene, "focal")
    t_cross = first_crossing(samples, landed, front_x)
    stop = sorted(samples, key=lambda r: r[0])[-1][1]
    stop_l = to_local(landed, stop["loc"])
    landed_scene = release_scene + float(p["landed_after_release_s"])

    # ---- what the camera sees at the release (a look metric, reported; not a gate)
    film = [float(v) for v in inputs["entry_camera"]["filmback_mm"]]
    dist = front_x - cam_rel_l[0]
    coverage = {"distance_cm": dist}
    if dist > 1.0:
        hw, hh = half_extent(dist, focal_rel, film)
        cz = cam_rel_l[2] + dist * math.tan(math.radians(cam_pitch_rel))
        fy0, fy1, fz0, fz1 = cam_rel_l[1] - hw, cam_rel_l[1] + hw, cz - hh, cz + hh
        floor_l = hang_lo_l[2] - float(hang["z"][0])
        above = max(0.0, fz1 - max(fz0, floor_l))
        coverage.update({"frame_w_cm": 2 * hw, "frame_h_cm": 2 * hh,
                         "horizontal": overlap(fy0, fy1, hang_lo_l[1], hang_hi_l[1]) / (2 * hw),
                         "vertical_above_floor": (overlap(max(fz0, floor_l), fz1, hang_lo_l[2], hang_hi_l[2]) / above)
                         if above > 0 else 1.0})
        # the hangar's hinge-plane opening, projected from the camera onto the hang front plane
        h = inputs["hangar"]
        if cam_rel_l[0] < 0.0:
            s = dist / (0.0 - cam_rel_l[0])
            oy0, oy1 = [cam_rel_l[1] + (y - cam_rel_l[1]) * s for y in (-h["half_w"], h["half_w"])]
            oz0, oz1 = [cam_rel_l[2] + (z - cam_rel_l[2]) * s for z in (0.0, h["height"])]
            area = (oy1 - oy0) * (oz1 - oz0)
            coverage["crossing_hidden"] = (overlap(oy0, oy1, hang_lo_l[1], hang_hi_l[1])
                                           * overlap(oz0, oz1, hang_lo_l[2], hang_hi_l[2]) / area) if area > 0 else 0.0

    plan = {
        "n": n, "label": DRAPE_LABEL % n, "tags": [TAGS[0], TAGS[1] % n], "rise": RISE_PATH % n,
        "frame_local": local, "drape_world": drape, "line_x_cm": line_x,
        "boxes_landed": {"hang": [hang_lo_l, hang_hi_l], "pile": [pile_lo_l, pile_hi_l]},
        "timing": {"rise_start_motion_s": m0, "rise_land_motion_s": m_land, "rise_start_scene_s": rise_start_scene,
                   "release_scene_s": release_scene, "release_motion_s": release_motion,
                   "landed_scene_s": landed_scene, "camera_reaches_hang_front_scene_s": t_cross},
        "section": section, "cache": {"path": GC_PATH, "bake_id": cache.get("bake_id"), "release_in_cache_s": in_cache,
                                      "duration_s": duration},
        "camera": {"at_release_landed": cam_rel_l, "yaw_at_release": cam_yaw_rel, "focal_at_release": focal_rel,
                   "stop_landed": stop_l, "coverage_at_release": coverage},
        "params": p,
    }
    plan["digest"] = plan_digest(plan)
    return plan


def plan_digest(plan):
    body = {k: v for k, v in plan.items() if k != "digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


# =====================================================================================================================
# Pure checks: every one falsifiable; test_passage_end_drape.py runs a failing control for each
# =====================================================================================================================

def check_pose(plan, inputs):
    """The inside-box guard and the framing, judged in the LANDED frame from the doors record, against the Passage
    actor's floor: independent of the frame the pose was composed in."""
    p = plan["params"]
    fail = []
    landed = frame_of(inputs["root_landed"]["loc"], inputs["root_landed"]["rot"])
    live = inputs["root_live"]
    dl = max(abs(float(a) - float(b)) for a, b in zip(live["loc"], inputs["root_landed"]["loc"]))
    dr = max(abs(wrap(float(a) - float(b))) for a, b in zip(live["rot"], inputs["root_landed"]["rot"]))
    if dl > p["root_tol_cm"] or dr > p["root_tol_deg"]:
        fail.append("ROOT_NOT_LANDED: live root differs from the landed record by %.2f cm / %.3f deg" % (dl, dr))
    if abs(landed["roll"]) > 1.0e-3 or abs(landed["pitch"]) > 1.0e-3:
        fail.append("ROOT_TILTED: landed record roll/pitch %r" % ([landed["roll"], landed["pitch"]],))
    d = plan["drape_world"]
    if abs(d["pitch"]) > 1.0e-3 or abs(d["roll"]) > 1.0e-3:
        fail.append("DRAPE_TILTED: pitch %.3f roll %.3f (composed via a non-landed root?)" % (d["pitch"], d["roll"]))
    h = inputs["hangar"]
    if abs(float(h["hinge_z"]) - landed["loc"][2]) > p["floor_tol_cm"]:
        fail.append("HINGE_Z_MISMATCH: doors record hinge_z %.1f (world) vs landed root z %.1f" % (h["hinge_z"], landed["loc"][2]))
    hinge_z = 0.0                                            # root-relative from here on
    origin_l = to_local(landed, d["loc"])
    want_z = float(p["floor_offset_cm"])
    if abs(origin_l[2] - want_z) > p["floor_tol_cm"]:
        fail.append("BOX_Z: drape floor at %.1f cm in the landed frame, want %.1f" % (origin_l[2], want_z))
    floor_l = float(inputs["floor_z"]) - landed["loc"][2]
    if abs(origin_l[2] - floor_l) > p["floor_tol_cm"]:
        fail.append("FLOOR_MISMATCH: drape floor %.1f vs the Passage floor %.1f (landed frame); a site decision "
                    "(floor_offset_cm) is needed" % (origin_l[2], floor_l))
    x_min = -(float(p["apron_cm"]) + float(p["back_limit_cm"]))
    x_max = -float(p["hinge_margin_cm"]) + 1.0e-6
    for name, (lo, hi), half in (("hang", plan["boxes_landed"]["hang"], float(h["half_w"])),
                                 ("pile", plan["boxes_landed"]["pile"], float(h["half_w"]) + float(p["pile_lateral_allow_cm"]))):
        bad = []
        if hi[0] > x_max:
            bad.append("x_hi %.1f > %.1f (over the hinge / the rising box)" % (hi[0], x_max))
        if lo[0] < x_min:
            bad.append("x_lo %.1f < %.1f (not at the passage end)" % (lo[0], x_min))
        if lo[1] < -half or hi[1] > half:
            bad.append("|y| %.1f > %.1f" % (max(-lo[1], hi[1]), half))
        if lo[2] < hinge_z - 200.0 or hi[2] > hinge_z + float(h["height"]):
            bad.append("z [%.1f, %.1f] outside [%.1f, %.1f]" % (lo[2], hi[2], hinge_z - 200.0, hinge_z + h["height"]))
        if bad:
            fail.append("BOX_%s: %s" % (name.upper(), "; ".join(bad)))
    re_l = to_local(landed, inputs["route_end"]["loc"])
    if abs(re_l[1]) > p["route_end_tol_cm"] or abs(re_l[0] + float(p["apron_cm"])) > p["route_end_tol_cm"]:
        fail.append("ROUTE_END: live route end at (%.1f, %.1f) in the dock frame, want (%.1f, 0)"
                    % (re_l[0], re_l[1], -float(p["apron_cm"])))
    if abs(wrap(float(inputs["route_end"]["yaw"]) - d["yaw"])) > p["yaw_tol_deg"]:
        fail.append("FACING_ROUTE: route end yaw %.3f vs drape yaw %.3f" % (inputs["route_end"]["yaw"], d["yaw"]))
    ec = inputs["entry_camera"]
    if abs(wrap(float(ec["yaw"]) - d["yaw"])) > p["yaw_tol_deg"]:
        fail.append("FACING_ENTRY_CAMERA: Entry Handoff camera yaw %.3f vs drape yaw %.3f" % (ec["yaw"], d["yaw"]))
    if abs(to_local(landed, ec["loc"])[1]) > p["route_end_tol_cm"]:
        fail.append("ENTRY_CAMERA_OFF_AXIS: %.1f cm lateral" % to_local(landed, ec["loc"])[1])
    return fail


def check_timing(plan, inputs):
    p, t, s = plan["params"], plan["timing"], plan["section"]
    fail = []
    if t["release_scene_s"] > t["rise_start_scene_s"] + 1.0e-9:
        fail.append("RELEASE_AFTER_RISE: release %.4f s > rise start %.4f s (the box would rise behind a hanging "
                    "curtain)" % (t["release_scene_s"], t["rise_start_scene_s"]))
    if t["rise_start_scene_s"] - t["release_scene_s"] > float(p["max_lead_s"]) + 1.0e-9:
        fail.append("RELEASE_TOO_EARLY: %.3f s before the rise (max %.3f)" % (t["rise_start_scene_s"] - t["release_scene_s"],
                                                                         p["max_lead_s"]))
    if t["release_scene_s"] >= 0.0:
        fail.append("RELEASE_NOT_PRE_SCENE: release at Scene time %.3f s (the Arrival plays only before the cut)"
                    % t["release_scene_s"])
    dur = plan["cache"]["duration_s"]
    tick = float(inputs["rise"]["tick_rate"])
    if s["offset_ticks"] + int(round(s["length_s"] * tick)) > int(round(dur * tick)) + 1:
        fail.append("SECTION_LOOPS: offset %d + length %d ticks > cache %d" % (s["offset_ticks"], round(s["length_s"] * tick),
                                                                              round(dur * tick)))
    held = map_time_to_animation(s, s["start_s"] - 1.0, dur)
    at_rel = map_time_to_animation(s, t["release_motion_s"], dur)
    if abs(held - s["offset_s"]) > 0.5 / CACHE_FPS:
        fail.append("HELD_SAMPLE: %.4f s before the section, want %.4f" % (held, s["offset_s"]))
    if abs(at_rel - plan["cache"]["release_in_cache_s"]) > 0.5 / CACHE_FPS:
        fail.append("RELEASE_SAMPLE: cache %.4f s at the release, want %.4f" % (at_rel, plan["cache"]["release_in_cache_s"]))
    cam = plan["camera"]
    front = plan["boxes_landed"]["hang"][0][0]
    if front - cam["at_release_landed"][0] < float(p["min_view_cm"]):
        fail.append("CAMERA_NOT_BEFORE_DRAPE_AT_RELEASE: camera %.1f cm from the hang front (min %.0f)"
                    % (front - cam["at_release_landed"][0], p["min_view_cm"]))
    tc = t["camera_reaches_hang_front_scene_s"]
    if tc is not None and t["landed_scene_s"] + float(p["clear_margin_s"]) > tc:
        fail.append("CAMERA_THROUGH_FALLING_CLOTH: cloth down at %.3f s (+%.1f margin), camera at the hang front at "
                    "%.3f s" % (t["landed_scene_s"], p["clear_margin_s"], tc))
    lo, hi = plan["boxes_landed"]["pile"]
    st = cam["stop_landed"]
    if lo[0] <= st[0] <= hi[0] and lo[1] <= st[1] <= hi[1] and st[2] - hi[2] < float(p["min_eye_over_pile_cm"]):
        fail.append("CAMERA_IN_PILE: eye %.1f cm above the pile top at the stop (min %.0f)"
                    % (st[2] - hi[2], p["min_eye_over_pile_cm"]))
    return fail


def live_gates(state):
    """Refusals from the editor state. state: mode, confirm, scene, pie, sequencer_open, census, record_exists,
    record_applied, zz, slot_actor, arrival_ok, label_exists, binding_exists, spawn_tracks."""
    r = []
    mode, n = str(state.get("mode")), state.get("scene")
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % mode)
    if n not in SCENES:
        r.append("SCENE_OUT_OF_SCOPE: %r (S1-S5; P06 excluded)" % (n,))
    if state.get("confirm") != "%s S%s" % (mode, n):
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s S%s" % (mode, n)))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN (an open Sequencer evaluates and dirties the map)")
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if state.get("zz"):
        r.append("ZZ_ACTORS_PRESENT (a bench is in the level)")
    if mode in ("DRY", "APPLY"):                          # DRY reports exactly what APPLY would refuse
        if state.get("record_exists"):
            r.append("RECORD_EXISTS: REVERT first, or archive a stale record by hand")
        if state.get("slot_actor"):
            r.append("BACKCLOTH_SLOT_TAKEN: %s Arrival already drives %r (one backcloth per Arrival, "
                     "InfinityStageArrival.h:184-189)" % ("S%s" % n, state["slot_actor"]))
        if state.get("label_exists"):
            r.append("ACTOR_EXISTS: %s" % (DRAPE_LABEL % n if isinstance(n, int) else n))
        if state.get("binding_exists"):
            r.append("BINDING_EXISTS: the rise already binds the drape label (orphan of a failed run?)")
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    for why in state.get("arrival_problems", []):
        r.append("ARRIVAL: " + why)
    return r


def range_gate(before, after):
    """Scene and rise playback ranges must read back unchanged (no Master rebuild is ever needed)."""
    out = []
    for key in sorted(set(before) | set(after)):
        if list(before.get(key) or []) != list(after.get(key) or []):
            out.append("RANGE_CHANGED: %s %r -> %r" % (key, before.get(key), after.get(key)))
    return out


def track_ops(classes, wanted):
    """Reuse a track UE may have auto-created (curtain_sleight.py:1564-1568; a second tool-added spawn track cost a
    restart, 5 Oct) instead of adding a duplicate. Returns (reuse_index or None, indices to remove, add?)."""
    hits = [i for i, c in enumerate(classes) if c == wanted]
    if hits:
        return hits[0], hits[1:], False
    return None, [], True


def track_failures(classes):
    """The drape binding (a possessable) must carry exactly one GC track and no spawn track."""
    out = []
    if classes.count(GC_TRACK) != 1:
        out.append("GC_TRACK_COUNT: %d" % classes.count(GC_TRACK))
    if classes.count(SPAWN_TRACK):
        out.append("SPAWN_TRACK_ON_POSSESSABLE: %d" % classes.count(SPAWN_TRACK))
    other = [c for c in classes if c not in (GC_TRACK, SPAWN_TRACK)]
    if other:
        out.append("UNEXPECTED_TRACKS: %r" % other)
    return out


# =====================================================================================================================
# Pure snapshot model (apply/revert exactness and drift). Shape = curtain_sleight's plus arrival/drape/ranges keys.
# =====================================================================================================================

def drape_row(loc, yaw):
    return [round(float(v), 1) for v in loc] + [round(float(yaw), 2)]


def apply_model(before, plan, guid, gc_row, cs, placed_row=None):
    """placed_row: the actor's read-back pose (APPLY has already guarded it within 1 cm of the plan)."""
    out = copy.deepcopy(before)
    out["bindings"].append({"name": plan["label"], "guid": guid, "parent": "",
                            "tracks": [{"class": GC_TRACK, "name": "", "sections": [list(gc_row)]}]})
    out["level_labels"] = sorted(out["level_labels"] + [plan["label"]])
    out["arrival"] = {"backcloth_actor": plan["label"], "backcloth_guid": guid}
    out["drape_actors"] = dict(out.get("drape_actors") or {})
    out["drape_actors"][plan["label"]] = placed_row or drape_row(plan["drape_world"]["loc"], plan["drape_world"]["yaw"])
    return cs["normalize_snapshot"](out)


def revert_model(after, record, cs):
    out = copy.deepcopy(after)
    guid = record["binding_guid"]
    out["bindings"] = [b for b in out["bindings"] if b["guid"] != guid]
    out["level_labels"] = sorted(l for l in out["level_labels"] if l != record["plan"]["label"])
    out["arrival"] = copy.deepcopy(record["snapshot_before"]["arrival"])
    out["drape_actors"] = {k: v for k, v in (out.get("drape_actors") or {}).items() if k != record["plan"]["label"]}
    return cs["normalize_snapshot"](out)


def drift(live, record, cs):
    """REVERT refuses unless the live state is exactly what APPLY left."""
    return cs["snapshot_diff"](cs["normalize_snapshot"](live), cs["normalize_snapshot"](record["snapshot_after"]))


def build_report(inputs, params, state):
    refusals = live_gates(state)
    warnings = []
    report = {"inputs_digest": hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]}
    try:
        plan = plan_drape(inputs, params)
    except PlanError as exc:
        refusals.append("PLAN_REFUSED: %s" % exc)
        report.update({"refusals": refusals, "warnings": warnings, "apply_ready": False, "plan": None})
        return report
    refusals.extend("CHECK: " + x for x in check_pose(plan, inputs) + check_timing(plan, inputs))
    cov = plan["camera"]["coverage_at_release"]
    if cov.get("horizontal", 1.0) < 1.0:
        warnings.append("FRAME_NOT_SPANNED_AT_RELEASE: the drape covers %.0f%% of the frame width (look call)"
                        % (100 * cov["horizontal"]))
    if cov.get("crossing_hidden", 1.0) < 1.0:
        warnings.append("CROSSING_PARTLY_VISIBLE_AT_RELEASE: %.0f%% of the hinge opening is behind the drape"
                        % (100 * cov["crossing_hidden"]))
    ec, stop = inputs["entry_camera"], plan["camera"]["stop_landed"]
    landed = frame_of(inputs["root_landed"]["loc"], inputs["root_landed"]["rot"])
    gap = max(abs(a - b) for a, b in zip(to_local(landed, ec["loc"]), stop))
    if gap > plan["params"]["entry_tol_cm"]:
        warnings.append("ENTRY_VS_PASSAGE_STOP: Entry Handoff camera %.1f cm from the Passage camera at the stop "
                        "(Gary note 6, the crossing snap; not this tool's to fix)" % gap)
    warnings.extend(inputs.get("warnings", []))
    report.update({"refusals": refusals, "warnings": warnings, "apply_ready": not refusals, "plan": plan,
                   "plan_digest": plan["digest"]})
    return report


# =====================================================================================================================
# Unreal side. Every call carries its tier; DRY prints the table. NEVER RUN YET.
# =====================================================================================================================

API_TABLE = [
    ("curtain_sleight.py defs (_census/_guid/_track_rows/_read_markers/normalize_snapshot/snapshot_diff)", "prec",
     "curtain_sleight.py, applied live 5 Oct (record_I1 applied=True); loaded as curtain_sleight_diag_bindings.py does"),
    ("UnrealEditorSubsystem.get_game_world/get_editor_world; get_current_level_sequence", "prec", "curtain_sleight.py:2052-2059"),
    ("Show cues label/cue_guid/scene.sequence", "prec", "curtain_sleight.py:1219-1233"),
    ("InfinityStageArrival props scene_cue_guid/motion_sequence/motion_binding_guid/backcloth_actor/backcloth_binding_guid",
     "prec", "atf_hangar_timing_apply.py:129; p04_backcloth_section_apply.py:190-191, 218-219 (applied+reverted 30 Sep)"),
    ("rise binding transform track channel[4] keys get_time(TICK_RESOLUTION)", "prec",
     "hangar_retime_apply.py:328 (channel 4 = pitch, ran 1 Oct); hangar_light_keys_probe.py:44"),
    ("Scene sub-track sections get_sequence/get_start_frame_seconds/parameters.start_frame_offset", "prec",
     "probe_master_scene_sections.py:22-36 (ran; time_scale is an unreadable TimeWarpVariant -> rate checked by the engine)"),
    ("Passage route get_spline_length / location+tangent at distance (WORLD)", "prec",
     "fit_transition_drapes.py:69-70 (applied 30 Sep); p04_backcloth_section_apply.py:148"),
    ("InfinityStageCameraPilotLibrary.get_passage_frame_range/get_passage_camera_pose", "prec", "capture_p1_s1_handoff.py:54-58"),
    ("InfinityStageTransportController.build_segments + segments start_frame", "prec", "p04_backcloth_section_apply.py:230-232"),
    ("Arrival.resolve_rotation_at_master_frame / resolve_backcloth_time_at_master_frame (no side effects)", "prec",
     "p04_backcloth_section_apply.py:234 (backcloth, ran 30 Sep); rotation: decl InfinityStageArrival.h:176-178"),
    ("GC asset asset_import_data.get_first_filename/start_frame/end_frame", "prec", "curtain_sleight.py:1120-1140"),
    ("EditorActorSubsystem.spawn_actor_from_class(GeometryCacheActor) + label/folder/tags", "prec",
     "import_passing_bake.py:276-282 (placed P04 Backcloth)"),
    ("geometry_cache_component geometry_cache/manual_tick/running/looping", "prec", "import_passing_bake.py:283-287"),
    ("rise.add_possessable(level actor) + set_display_name", "prec", "p04_backcloth_section_apply.py:203"),
    ("binding.add_track(MovieSceneGeometryCacheTrack).add_section + params + set_range_seconds + eval_options KEEP_STATE",
     "prec", "p04_backcloth_section_apply.py:204-217"),
    ("section.get_start_frame_seconds/get_end_frame_seconds", "prec", "p04_backcloth_section_apply.py:222"),
    ("binding.remove()", "prec", "p04_backcloth_section_apply.py:187-189 (P04 revert ran: record .reverted)"),
    ("EditorActorSubsystem.destroy_actor", "prec", "curtain_sleight.py:2007 (ran? UNCLEAR: no CST revert yet); opening_sequence_apply.py:787"),
    ("EditorAssetLibrary.save_asset / EditorLoadingAndSavingUtils.save_map", "prec", "curtain_sleight.py:1864-1865 (ran 5 Oct)"),
    ("component.get_duration()", "prec", "p04_backcloth_section_apply.py:155"),
]


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _saved():
    return os.path.dirname(_here())


def load_cs(here=None):
    """curtain_sleight.py definitions only, main() not run (curtain_sleight_diag_bindings.py:10-14 [prec])."""
    path = os.path.join(here or _here(), CS_FILE)
    with open(path, "r", encoding="utf-8") as handle:
        src = handle.read()
    cut = src.rindex("if unreal is not None:")
    ns = {"__name__": "curtain_sleight_lib_for_end_drape", "__file__": path}
    exec(compile(src[:cut], path, "exec"), ns)  # noqa: S102 - the conductor's reviewed, live-proven project file
    for need in ("normalize_snapshot", "snapshot_diff", "_track_rows", "_read_markers", "_guid", "_census", "_content_file"):
        if need not in ns:
            raise PlanError("CS_LIB_MISSING: " + need)
    return ns


def _load_json(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise PlanError("missing " + path)
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)


def write_record_exclusive(path, data):
    """Create-only (refuses if it exists), flushed and fsynced BEFORE any mutation."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _stop(run, reason):
    unreal.log_error("PASSAGE_END_DRAPE_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _unwrap(result, count):
    """UE Python: out-params as a tuple, or None when a bool UFUNCTION returns false (capture_p1_s1_handoff.py:46-52)."""
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return (result[1:] if count > 1 else result[1]) if result[0] else None
    return result


def _master_time(ticks):
    return unreal.FrameTime(frame_number=unreal.FrameNumber(int(round(ticks))), sub_frame=0.0)


def _bake_facts(cache, run):
    """Release, hang (held sample) and pile (last checkpoint) from the cache's own artifact chain
    (curtain_sleight.py:1120-1140; p04_backcloth_section_apply.py:84-126). Axis map [inf, curtain_sleight.py:1134-1135]:
    Unreal X = bake y, Unreal Y = +/- bake x (sign unrecorded: hang uses the INNER symmetric range, pile the OUTER)."""
    src = os.path.basename(cache.get_editor_property("asset_import_data").get_first_filename())
    stem = GC_PATH.split("/")[-1] + "_"
    if not (src.startswith(stem) and src.endswith(".abc")):
        _stop(run, "BAKE_UNTRACEABLE|source=%s" % src)
    bake_id = src[len(stem):-4]
    bake = _load_json(os.path.join(_saved(), BAKE_DIR, bake_id + ".json"))
    if bake.get("release_frame") is None or bake.get("show_start") is None:
        _stop(run, "BAKE_HAS_NO_RELEASE|%s" % bake_id)
    in_cache = (int(bake["release_frame"]) - int(bake["show_start"])) / CACHE_FPS
    held = int(bake["show_start"]) + int(round((in_cache - 1.0 / CACHE_FPS) * CACHE_FPS))
    cps = bake.get("checkpoints", {})
    if str(held) not in cps:
        _stop(run, "HOLD_SAMPLE_HAS_NO_CHECKPOINT|bake=%s|sample=%d" % (bake_id, held))
    last = max(int(k) for k in cps)
    a, b = cps[str(held)]["aabb_m"], cps[str(last)]["aabb_m"]
    yi = min(abs(a["x"][0]), abs(a["x"][1]))
    yo = max(abs(b["x"][0]), abs(b["x"][1]))
    duration = (float(cache.get_editor_property("end_frame")) - float(cache.get_editor_property("start_frame"))) / CACHE_FPS
    warn = []
    end_bake_frame = int(bake["show_start"]) + int(round(duration * CACHE_FPS))
    if last < end_bake_frame - 2:
        warn.append("PILE_CHECKPOINT_EARLY: pile AABB from bake frame %d, cache ends at %d" % (last, end_bake_frame))
    return {"bake_id": bake_id, "release_in_cache_s": in_cache, "duration_s": duration, "held_sample": held,
            "pile_sample": last,
            "hang_aabb_cm": {"x": [a["y"][0] * 100.0, a["y"][1] * 100.0], "y": [-yi * 100.0, yi * 100.0],
                             "z": [a["z"][0] * 100.0, a["z"][1] * 100.0]},
            "pile_aabb_cm": {"x": [b["y"][0] * 100.0, b["y"][1] * 100.0], "y": [-yo * 100.0, yo * 100.0],
                             "z": [b["z"][0] * 100.0, b["z"][1] * 100.0]}}, warn


def _rot_list(rot):
    return [float(rot.roll), float(rot.pitch), float(rot.yaw)]


def _gather(n, run, cs):
    """Every live fact the planner needs, as plain data, plus a dict of unreal handles (locals only)."""
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    index = {}
    for a in actors:
        index.setdefault(str(a.get_actor_label()), []).append(a)

    def one(label):
        rows = index.get(label, [])
        if len(rows) != 1:
            _stop(run, "ACTOR_COUNT|label=%s|count=%d" % (label, len(rows)))
        return rows[0]

    warnings, arrival_problems = [], []
    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")).startswith(SCENE_CUE_PREFIX % n) and c.get_editor_property("enabled")]
    if len(cues) != 1:
        _stop(run, "SCENE_CUE_COUNT|S%d|%d" % (n, len(cues)))
    cue_guid = cs["_guid"](cues[0].get_editor_property("cue_guid"))
    scene_seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
    scene_path = scene_seq.get_path_name().split(".")[0]
    scene_range = [int(scene_seq.get_playback_start()), int(scene_seq.get_playback_end())]

    arrival = one(ARRIVAL_LABEL % n)
    motion = arrival.get_editor_property("motion_sequence")
    motion_path = motion.get_path_name().split(".")[0] if motion else None
    if motion_path != RISE_PATH % n:
        arrival_problems.append("motion_sequence %s != %s" % (motion_path, RISE_PATH % n))
    if cs["_guid"](arrival.get_editor_property("scene_cue_guid")) != cue_guid:
        arrival_problems.append("scene_cue_guid != the Scene cue %s" % cue_guid)
    if not hasattr(arrival, "resolve_backcloth_time_at_master_frame"):
        arrival_problems.append("G2 backcloth API missing in this build")
    slot = arrival.get_editor_property("backcloth_actor")
    slot_label = str(slot.get_actor_label()) if slot is not None else ""
    slot_guid = cs["_guid"](arrival.get_editor_property("backcloth_binding_guid"))

    rise = unreal.load_asset(RISE_PATH % n)
    tick = rise.get_tick_resolution()
    tick_rate = tick.numerator / float(tick.denominator)
    rate = rise.get_display_rate()
    rise_fps = rate.numerator / float(rate.denominator)
    rise_range = [int(rise.get_playback_start()), int(rise.get_playback_end())]
    root_guid = cs["_guid"](arrival.get_editor_property("motion_binding_guid"))
    roots = [b for b in rise.get_bindings() if cs["_guid"](b.get_id()) == root_guid]
    if len(roots) != 1:
        _stop(run, "ROOT_BINDING|S%d|%d" % (n, len(roots)))
    chans = []
    for track in roots[0].get_tracks():
        if isinstance(track, unreal.MovieScene3DTransformTrack):
            for section in track.get_sections():
                cs_ = list(section.get_all_channels())
                if len(cs_) > 4:
                    chans.append(cs_[4])                          # pitch (hangar_retime_apply.py:328)
    if len(chans) != 1:
        _stop(run, "ROOT_PITCH_CHANNEL|S%d|%d" % (n, len(chans)))
    pitch_keys = []
    for key in chans[0].get_keys():
        when = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
        pitch_keys.append([(int(when.frame_number.value) + float(getattr(when, "sub_frame", 0.0))) / tick_rate,
                           float(key.get_value())])

    subs = []
    for tt in (unreal.MovieSceneSubTrack, unreal.MovieSceneCinematicShotTrack):
        for t in scene_seq.find_tracks_by_type(tt):
            for s in t.get_sections():
                sq = s.get_sequence()
                if sq is not None and sq.get_path_name().split(".")[0] == RISE_PATH % n:
                    subs.append(s)
    if len(subs) != 1:
        _stop(run, "RISE_NOT_NESTED_ONCE|S%d|%d (the Arrival needs exactly one sub-section)" % (n, len(subs)))
    prm = subs[0].get_editor_property("parameters")
    rise_sub = {"section_start_s": float(subs[0].get_start_frame_seconds()),
                "start_offset_s": int(prm.get_editor_property("start_frame_offset").value) / tick_rate,
                "inner_start_s": rise_range[0] / rise_fps, "rate": 1.0}   # rate [inf]: engine cross-check below

    root = one(ROOT_LABEL % n)
    rl, rr = root.get_actor_location(), root.get_actor_rotation()
    doors = _load_json(os.path.join(_here(), DOORS_RECORD))
    if doors.get("world") != EXPECTED_WORLD or not doors.get("applied"):
        _stop(run, "DOORS_RECORD_CONTEXT")
    rec = doors["root_before"][str(n)]
    rows = [r for r in doors["plan"]["scenes"] if int(r["scene"]) == n]
    if len(rows) != 1:
        _stop(run, "DOORS_ROW|S%d" % n)
    dims = rows[0]["hangar_dimensions"]

    passage = one(PASSAGE_ACTOR % n)
    route = passage.get_editor_property("route")
    if not route:
        _stop(run, "PASSAGE_HAS_NO_ROUTE|%s" % (PASSAGE_ACTOR % n))
    length = route.get_spline_length()
    rend = route.get_location_at_distance_along_spline(length, unreal.SplineCoordinateSpace.WORLD)
    rtan = route.get_tangent_at_distance_along_spline(length, unreal.SplineCoordinateSpace.WORLD)
    floor_z = float(passage.get_actor_location().z)

    psets = [ps for ps in show.get_editor_property("passage_settings")
             if str(ps.get_editor_property("label")) == PASSAGE_LABEL % n]
    if len(psets) != 1:
        _stop(run, "PASSAGE_SETTINGS|%d" % len(psets))
    pguid = psets[0].get_editor_property("passage_guid")
    lib = unreal.InfinityStageCameraPilotLibrary
    fr = _unwrap(lib.get_passage_frame_range(show, pguid), 2)
    if fr is None:
        _stop(run, "PASSAGE_FRAME_RANGE")
    end_tick = int(fr[1])
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = [s for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")) == str(cues[0].get_editor_property("label"))]
    scene_start_tick = int(segs[0].get_editor_property("start_frame").value) if len(segs) == 1 else None
    del tr
    if scene_start_tick is None:
        _stop(run, "SCENE_SEGMENT_NOT_FOUND")
    if abs(scene_start_tick - end_tick) > 1:
        warnings.append("PASSAGE_END_NOT_SCENE_START: passage end tick %d, Scene start %d" % (end_tick, scene_start_tick))

    m0 = min(k[0] for k in pitch_keys) if pitch_keys else 0.0
    span = max(12.0, -motion_to_scene(rise_sub, m0) + 4.0)
    step = float(DEFAULTS["sample_step_s"])
    samples = []
    for i in range(int(round(span / step)) + 1):
        t = -span + i * step
        pose = _unwrap(lib.get_passage_camera_pose(show, pguid, int(round(scene_start_tick + t * SHOW_TICKS_PER_S)) - (1 if i == int(round(span / step)) else 0)), 3)
        if pose is None:
            continue
        view, focal, _ = pose
        loc, rot = view.translation, view.rotation.rotator()
        samples.append([round(t, 4), {"loc": [float(loc.x), float(loc.y), float(loc.z)], "yaw": float(rot.yaw),
                                      "pitch": float(rot.pitch), "focal": float(focal)}])
    if len(samples) < 10:
        _stop(run, "PASSAGE_CAMERA_SAMPLES|%d" % len(samples))

    entry = [a for a in actors if isinstance(a, unreal.CineCameraActor) and a.actor_has_tag(ENTRY_TAG)
             and str(a.get_actor_label()).startswith("Scene %d " % n)]
    if len(entry) != 1:
        _stop(run, "ENTRY_CAMERA_COUNT|S%d|%d" % (n, len(entry)))
    el, er = entry[0].get_actor_location(), entry[0].get_actor_rotation()
    comp = entry[0].get_cine_camera_component()
    fb = comp.get_editor_property("filmback")
    entry_camera = {"label": str(entry[0].get_actor_label()), "loc": [float(el.x), float(el.y), float(el.z)],
                    "yaw": float(er.yaw), "pitch": float(er.pitch), "focal_mm": float(comp.get_editor_property("current_focal_length")),
                    "filmback_mm": [float(fb.get_editor_property("sensor_width")), float(fb.get_editor_property("sensor_height"))]}

    cache = unreal.load_asset(GC_PATH)
    if cache is None:
        _stop(run, "CACHE_MISSING")
    cache_facts, w = _bake_facts(cache, run)
    warnings.extend(w)

    # the engine's own mapping of the rise start (rate, offsets): rest just before it, moving 1 s after
    if pitch_keys:
        t0 = motion_to_scene(rise_sub, m0)
        before = _unwrap(arrival.resolve_rotation_at_master_frame(show, _master_time(scene_start_tick + (t0 - 2.0 / rise_fps) * SHOW_TICKS_PER_S)), 1)
        after = _unwrap(arrival.resolve_rotation_at_master_frame(show, _master_time(scene_start_tick + (t0 + 1.0) * SHOW_TICKS_PER_S)), 1)
        if before is None or after is None:
            arrival_problems.append("resolve_rotation_at_master_frame returned nothing around the rise start")
        elif abs(float(before.pitch) + 90.0) > 1.0e-3 or float(after.pitch) < -90.0 + 1.0e-3:
            arrival_problems.append("MAPPING_MISMATCH: engine pitch %.4f just before / %.4f 1 s after the keyed rise start"
                                    % (before.pitch, after.pitch))
    label = DRAPE_LABEL % n
    inputs = {
        "n": n, "cue_guid": cue_guid, "scene_sequence": scene_path, "scene_range": scene_range, "rise_range": rise_range,
        "scene_start_tick": scene_start_tick,
        "root_live": {"loc": [float(rl.x), float(rl.y), float(rl.z)], "rot": _rot_list(rr)},
        "root_landed": {"loc": [float(v) for v in rec["location"]], "rot": [float(v) for v in rec["rotation"]]},
        "hangar": {"half_w": float(dims["half_w"]), "height": float(dims["height"]), "depth": float(dims["depth"]),
                   "hinge_z": float(dims.get("hinge_z", 0.0))},
        "route_end": {"loc": [float(rend.x), float(rend.y), float(rend.z)], "yaw": math.degrees(math.atan2(rtan.y, rtan.x))},
        "floor_z": floor_z, "entry_camera": entry_camera, "passage_camera": samples,
        "rise": {"root_pitch_keys": pitch_keys, "tick_rate": tick_rate, "fps": rise_fps},
        "rise_sub": rise_sub, "cache": cache_facts, "warnings": warnings,
    }
    state = {"slot_actor": slot_label or (slot_guid if slot_guid.strip("0") else ""),
             "arrival_problems": arrival_problems,
             "label_exists": label in index,
             "binding_exists": any(str(b.get_display_name()) == label for b in rise.get_bindings()),
             "zz": any(lab.startswith("ZZ_") for lab in index)}
    handles = {"show": show, "arrival": arrival, "rise": rise, "scene_seq": scene_seq, "cache": cache, "index": index}
    return inputs, state, handles


def _snapshot(rise, arrival, n, cs, scene_seq):
    start, end = rise.get_playback_start(), rise.get_playback_end()
    bindings = []
    for b in rise.get_bindings():
        parent = b.get_parent()
        bindings.append({"name": str(b.get_display_name()), "guid": cs["_guid"](b.get_id()),
                         "parent": cs["_guid"](parent.get_id()) if parent is not None and parent.is_valid() else "",
                         "tracks": cs["_track_rows"](b.get_tracks(), start, end)})
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    mine = [a for a in actors if a.actor_has_tag(TAGS[1] % n)]
    slot = arrival.get_editor_property("backcloth_actor")
    drapes = {}
    for a in mine:
        l, r = a.get_actor_location(), a.get_actor_rotation()
        drapes[str(a.get_actor_label())] = drape_row([l.x, l.y, l.z], r.yaw)
    return cs["normalize_snapshot"]({
        "playback": [int(start), int(end)], "bindings": bindings,
        "root_tracks": cs["_track_rows"](list(rise.get_tracks()), start, end), "cuts": [],
        "markers": cs["_read_markers"](rise), "level_labels": sorted(drapes),
        "arrival": {"backcloth_actor": str(slot.get_actor_label()) if slot is not None else "",
                    "backcloth_guid": cs["_guid"](arrival.get_editor_property("backcloth_binding_guid"))},
        "drape_actors": drapes,
        "ranges": {"scene": [int(scene_seq.get_playback_start()), int(scene_seq.get_playback_end())],
                   "rise": [int(start), int(end)]}})


def _backup(run, n, suffix, cs):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "PrePassageEndDrape-S%d-%s%s" % (n, run, suffix))
    os.makedirs(folder, exist_ok=False)
    rows = []
    for src in (cs["_content_file"](RISE_PATH % n), cs["_content_file"](EXPECTED_WORLD, ".umap")):
        if not os.path.isfile(src):
            _stop(run, "BACKUP_SOURCE_MISSING|" + src)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        rows.append({"source": src, "backup": dst, "sha256": digest[1]})
    return folder, rows


def _api_probe():
    return {"GeometryCacheActor": hasattr(unreal, "GeometryCacheActor"),
            "MovieSceneGeometryCacheTrack": hasattr(unreal, "MovieSceneGeometryCacheTrack"),
            "MovieSceneSection.set_range_seconds": hasattr(unreal.MovieSceneSection, "set_range_seconds"),
            "MovieSceneBindingProxy.remove": hasattr(unreal.MovieSceneBindingProxy, "remove"),
            "InfinityStageArrival.resolve_backcloth_time_at_master_frame":
                hasattr(unreal.InfinityStageArrival, "resolve_backcloth_time_at_master_frame")}


def run_dry(n, run, params, cs, base_state):
    inputs, state, h = _gather(n, run, cs)
    state.update(base_state)
    state["record_exists"] = os.path.exists(os.path.join(_here(), RECORD_PATTERN % n))
    report = build_report(inputs, params, state)
    report["api_table"] = [{"call": c, "tier": t, "cite": s} for c, t, s in API_TABLE]
    report["api_probe"] = _api_probe()
    report["inputs"] = inputs
    report["state"] = state
    out = os.path.join(_here(), DRY_PATTERN % n)
    _write_json(out, report)
    if report.get("plan") is not None:
        _write_json(os.path.join(_here(), PLAN_PATTERN % n),
                    {"scene": n, "run": run, "plan_digest": report["plan_digest"], "inputs_digest": report["inputs_digest"],
                     "params": params, "cue_guid": inputs["cue_guid"]})
    for text in report["refusals"]:
        unreal.log_warning("PASSAGE_END_DRAPE_REFUSAL|run=%s|%s" % (run, text))
    for text in report["warnings"]:
        unreal.log("PASSAGE_END_DRAPE_WARNING|run=%s|%s" % (run, text))
    if cs["_census"]() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(cs["_census"]()))
    plan = report.get("plan") or {}
    t = plan.get("timing") or {}
    unreal.log("PASSAGE_END_DRAPE_DRY_OK|run=%s|scene=S%d|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|"
               "rise_start_scene_s=%s|release_scene_s=%s|line_x_cm=%s|digest=%s|report=%s"
               % (run, n, int(report["apply_ready"]), len(report["refusals"]), len(report["warnings"]),
                  t.get("rise_start_scene_s"), t.get("release_scene_s"), plan.get("line_x_cm"), report.get("plan_digest"), out))


def run_apply(n, run, params, cs, base_state):
    inputs, state, h = _gather(n, run, cs)
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    state.update(base_state)
    state["record_exists"] = os.path.exists(record_path)
    report = build_report(inputs, params, state)
    if report["refusals"]:
        _stop(run, "REFUSED|" + " || ".join(report["refusals"]))
    plan = report["plan"]
    plan_file = _load_json(os.path.join(_here(), PLAN_PATTERN % n), required=False)
    if plan_file.get("plan_digest") != plan["digest"] or plan_file.get("cue_guid") != inputs["cue_guid"]:
        _stop(run, "PLAN_CHANGED_SINCE_DRY|dry=%s|now=%s|rerun DRY" % (plan_file.get("plan_digest"), plan["digest"]))
    rise, arrival, show, scene_seq, cache = h["rise"], h["arrival"], h["show"], h["scene_seq"], h["cache"]
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()

    # 0. backups + exclusive fsynced record, BEFORE any mutation
    backup, rows = _backup(run, n, "", cs)
    snap0 = _snapshot(rise, arrival, n, cs, scene_seq)
    record = {"schema_version": 1, "run": run, "scene": n, "world": EXPECTED_WORLD, "rise": RISE_PATH % n,
              "cue_guid": inputs["cue_guid"], "backup": backup, "backup_files": rows, "applied": False,
              "plan_digest": plan["digest"], "plan": plan, "snapshot_before": snap0,
              "decided_by": base_state.get("decided_by")}
    try:
        write_record_exclusive(record_path, record)
    except FileExistsError:
        _stop(run, "RECORD_EXISTS|%s" % record_path)

    # 1. the level actor (world pose composed against the LIVE landed root; guarded below on what was placed)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    d = plan["drape_world"]
    rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(d["yaw"]))
    actor = sub.spawn_actor_from_class(unreal.GeometryCacheActor, unreal.Vector(*d["loc"]), rot)
    if actor is None:
        _stop(run, "SPAWN_FAILED|NOTHING SAVED; Don't-Save restart")
    actor.set_actor_label(plan["label"])
    actor.set_folder_path(FOLDER)
    actor.tags = [unreal.Name(t) for t in plan["tags"]]
    actor.set_actor_location(unreal.Vector(*d["loc"]), False, False)
    actor.set_actor_rotation(rot, False)
    comp = actor.get_editor_property("geometry_cache_component")
    comp.set_editor_property("geometry_cache", cache)
    comp.set_editor_property("manual_tick", True)      # never auto-plays (import_passing_bake.py:285)
    comp.set_editor_property("running", True)          # running=False freezes frame 0
    comp.set_editor_property("looping", False)
    al, ar = actor.get_actor_location(), actor.get_actor_rotation()
    placed = dict(plan)
    placed["drape_world"] = {"loc": [al.x, al.y, al.z], "pitch": float(ar.pitch), "yaw": float(ar.yaw), "roll": float(ar.roll)}
    lo_hang = plan["boxes_landed"]["hang"]
    hang = inputs["cache"]["hang_aabb_cm"]
    pile = inputs["cache"]["pile_aabb_cm"]
    landed = frame_of(inputs["root_landed"]["loc"], inputs["root_landed"]["rot"])
    placed["boxes_landed"] = {
        "hang": list(box_in(placed["drape_world"], landed, [hang["x"][0], hang["y"][0], hang["z"][0]], [hang["x"][1], hang["y"][1], hang["z"][1]])),
        "pile": list(box_in(placed["drape_world"], landed, [pile["x"][0], pile["y"][0], pile["z"][0]], [pile["x"][1], pile["y"][1], pile["z"][1]]))}
    bad = check_pose(placed, inputs)
    if bad or max(abs(placed["boxes_landed"]["hang"][0][i] - lo_hang[0][i]) for i in range(3)) > 1.0:
        _stop(run, "PLACED_OUTSIDE_GUARD|%r|NOTHING SAVED; Don't-Save restart" % bad)
    dur_live = float(comp.get_duration())
    if abs(dur_live - plan["cache"]["duration_s"]) > 1.0 / CACHE_FPS:
        _stop(run, "DURATION_MISMATCH|component %.4f vs plan %.4f|NOTHING SAVED; Don't-Save restart" % (dur_live, plan["cache"]["duration_s"]))

    # 2. the rise: one possessable, one GC track (reuse, never duplicate), one section
    rise.modify()
    binding = rise.add_possessable(actor)
    if binding is None or not binding.is_valid():
        _stop(run, "ADD_POSSESSABLE|NOTHING SAVED; Don't-Save restart")
    binding.set_display_name(plan["label"])
    tracks = list(binding.get_tracks())
    reuse, remove, add = track_ops([t.get_class().get_name() for t in tracks], GC_TRACK)
    for i in remove:
        binding.remove_track(tracks[i])                   # returns None: judged by re-listing below
    gt = binding.add_track(unreal.MovieSceneGeometryCacheTrack) if add else tracks[reuse]
    for old in list(gt.get_sections()):
        gt.remove_section(old)
    sec = gt.add_section()
    s = plan["section"]
    prm = sec.get_editor_property("params")
    prm.set_editor_property("geometry_cache_asset", cache)
    prm.set_editor_property("play_rate", 1.0)
    prm.set_editor_property("start_frame_offset", unreal.FrameNumber(int(s["offset_ticks"])))
    prm.set_editor_property("end_frame_offset", unreal.FrameNumber(0))
    sec.set_editor_property("params", prm)
    sec.set_range_seconds(float(s["start_s"]), float(s["end_s"]))
    ev = sec.get_editor_property("eval_options")
    ev.set_editor_property("completion_mode", unreal.MovieSceneCompletionMode.KEEP_STATE)
    sec.set_editor_property("eval_options", ev)
    arrival.set_editor_property("backcloth_actor", actor)
    arrival.set_editor_property("backcloth_binding_guid", binding.get_id())
    guid = cs["_guid"](binding.get_id())
    record.update({"binding_guid": guid})
    update_record(record_path, record)

    # 3. read-back BEFORE saving (UE return values are not trusted)
    problems = []
    tf = track_failures([t.get_class().get_name() for t in binding.get_tracks()])
    problems.extend(tf)
    tick = float(inputs["rise"]["tick_rate"])
    got = (float(sec.get_start_frame_seconds()), float(sec.get_end_frame_seconds()))
    if abs(got[0] - s["start_s"]) > 1.5 / tick or abs(got[1] - s["end_s"]) > 1.5 / tick:
        problems.append("SECTION_RANGE %r want [%.6f, %.6f]" % (got, s["start_s"], s["end_s"]))
    prm2 = sec.get_editor_property("params")
    if int(prm2.get_editor_property("start_frame_offset").value) != int(s["offset_ticks"]):
        problems.append("SECTION_OFFSET %r" % prm2.get_editor_property("start_frame_offset").value)
    gc_row = cs["_gc_row"](sec)
    expected = apply_model(snap0, plan, guid, gc_row, cs, drape_row([al.x, al.y, al.z], ar.yaw))
    snap1 = _snapshot(rise, arrival, n, cs, scene_seq)
    problems.extend("SNAPSHOT " + x for x in cs["snapshot_diff"](snap1, expected))
    problems.extend(range_gate(snap0["ranges"], snap1["ranges"]))
    st = inputs["scene_start_tick"]
    t = plan["timing"]

    def cache_at(scene_s):
        return _unwrap(arrival.resolve_backcloth_time_at_master_frame(show, _master_time(st + scene_s * SHOW_TICKS_PER_S), dur_live), 1)

    held = cache_at(motion_to_scene(inputs["rise_sub"], s["start_s"]) - 1.0)
    at_rel = cache_at(t["release_scene_s"])
    if held is None or at_rel is None or abs(held - s["offset_s"]) > 0.5 / CACHE_FPS \
            or abs(at_rel - plan["cache"]["release_in_cache_s"]) > 0.5 / CACHE_FPS:
        problems.append("ARRIVAL_MAPPING held=%r (want %.4f) release=%r (want %.4f)"
                        % (held, s["offset_s"], at_rel, plan["cache"]["release_in_cache_s"]))
    census = cs["_census"]()
    if census != {"content": [RISE_PATH % n], "maps": [EXPECTED_WORLD]}:
        problems.append("UNEXPECTED_DIRTY %s" % json.dumps(census))
    if problems:
        _stop(run, "PRESAVE_READBACK|%r|NOTHING SAVED; Don't-Save restart; backup %s" % (problems, backup))

    # 4. narrow saves, then read-back again
    saves = {RISE_PATH % n: bool(unreal.EditorAssetLibrary.save_asset(RISE_PATH % n, only_if_is_dirty=True)),
             EXPECTED_WORLD: bool(unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD))}
    if not all(saves.values()):
        _stop(run, "SAVE_FAILED|%r" % saves)
    post = []
    if cs["_census"]() != {"content": [], "maps": []}:
        post.append("dirty after save %r" % cs["_census"]())
    snap2 = _snapshot(unreal.load_asset(RISE_PATH % n), arrival, n, cs, scene_seq)
    post.extend(cs["snapshot_diff"](snap2, expected))
    if post:
        _stop(run, "READBACK_FAILED_AFTER_SAVE|%r|restore from %s" % (post, backup))
    record.update({"applied": True, "snapshot_after": snap2, "saves": saves, "gc_row": gc_row})
    update_record(record_path, record)
    unreal.log("PASSAGE_END_DRAPE_APPLY_OK|run=%s|scene=S%d|label=%s|binding=%s|release_scene_s=%.4f|rise_start_scene_s=%.4f|"
               "section=[%.4f,%.4f)|backup=%s|record=%s|ranges_unchanged=1|tests_required_singly=%s"
               % (run, n, plan["label"], guid, t["release_scene_s"], t["rise_start_scene_s"], s["start_s"], s["end_s"],
                  backup, record_path, REQUIRED_TESTS))


def run_revert(n, run, cs):
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    record = _load_json(record_path)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or int(record["scene"]) != n:
        _stop(run, "REVERT_RECORD_CONTEXT")
    rise = unreal.load_asset(record["rise"])
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    arrivals = [a for a in actors if str(a.get_actor_label()) == ARRIVAL_LABEL % n]
    if len(arrivals) != 1:
        _stop(run, "ARRIVAL_COUNT|%d" % len(arrivals))
    arrival = arrivals[0]
    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues") if cs["_guid"](c.get_editor_property("cue_guid")) == record["cue_guid"]]
    if len(cues) != 1:
        _stop(run, "CUE_GUID_NOT_FOUND")
    scene_seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
    live = _snapshot(rise, arrival, n, cs, scene_seq)
    dd = drift(live, record, cs)
    if dd:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%r (restore from %s instead)" % (dd, record["backup"]))
    backup, rows = _backup(run, n, "-revert", cs)
    rise.modify()
    for b in list(rise.get_bindings()):
        if cs["_guid"](b.get_id()) == record["binding_guid"]:
            b.remove()
    arrival.set_editor_property("backcloth_actor", None)
    arrival.set_editor_property("backcloth_binding_guid", unreal.Guid())
    mine = [a for a in actors if str(a.get_actor_label()) == record["plan"]["label"]]
    if len(mine) != 1 or not mine[0].actor_has_tag(TAGS[1] % n):
        _stop(run, "REVERT_ACTOR|%d|NOTHING SAVED; Don't-Save restart" % len(mine))
    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(mine[0])
    after = _snapshot(rise, arrival, n, cs, scene_seq)
    want = revert_model(record["snapshot_after"], record, cs)
    diff = cs["snapshot_diff"](after, want) + cs["snapshot_diff"](after, cs["normalize_snapshot"](record["snapshot_before"]))
    diff += range_gate(record["snapshot_before"]["ranges"], after["ranges"])
    census = cs["_census"]()
    if census != {"content": [record["rise"]], "maps": [EXPECTED_WORLD]}:
        diff.append("UNEXPECTED_DIRTY %s" % json.dumps(census))
    if diff:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart" % diff)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    saves = {record["rise"]: bool(unreal.EditorAssetLibrary.save_asset(record["rise"], only_if_is_dirty=True)),
             EXPECTED_WORLD: bool(unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD))}
    if not all(saves.values()):
        _stop(run, "SAVE_FAILED|%r" % saves)
    final = _snapshot(unreal.load_asset(record["rise"]), arrival, n, cs, scene_seq)
    diff = cs["snapshot_diff"](final, cs["normalize_snapshot"](record["snapshot_before"]))
    if diff or cs["_census"]() != {"content": [], "maps": []}:
        _stop(run, "REVERT_READBACK|%r|census=%r|restore from %s" % (diff, cs["_census"](), record["backup"]))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("PASSAGE_END_DRAPE_REVERT_OK|run=%s|scene=S%d|backup=%s|record=%s|tests_required_singly=%s"
               % (run, n, backup, archived, REQUIRED_TESTS))


def main():
    run = str(globals().get("PASSAGE_END_DRAPE_RUN_ID") or datetime.datetime.now().strftime("PED-%Y%m%d-%H%M%S"))
    n = globals().get("PASSAGE_END_DRAPE_SCENE")
    mode = str(globals().get("PASSAGE_END_DRAPE_MODE") or "DRY").upper()
    params = dict(globals().get("PASSAGE_END_DRAPE_PARAMS") or {})
    cs = load_cs()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    base = {"mode": mode, "scene": n, "confirm": globals().get("PASSAGE_END_DRAPE_CONFIRM"),
            "pie": editor.get_game_world() is not None,
            "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
            "census": cs["_census"](), "decided_by": globals().get("PASSAGE_END_DRAPE_DECIDED_BY"),
            "record_applied": bool(_load_json(os.path.join(_here(), RECORD_PATTERN % n), required=False).get("applied"))
            if n in SCENES else False}
    early = live_gates(base)                               # PIE / Sequencer / census / confirm before touching anything
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
    if mode == "APPLY" and not str(base.get("decided_by") or "").strip():
        early.append("NOT_DECIDED: args decided_by is empty")
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        if mode == "REVERT":
            run_revert(n, run, cs)
        elif mode == "APPLY":
            run_apply(n, run, params, cs, base)
        else:
            run_dry(n, run, params, cs, base)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
