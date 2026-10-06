"""BACKCLOTH LEAD FIT (6 Oct, offline-written, NEVER RUN IN UNREAL): re-fit the P04 backcloth's release to the CURRENT
Passage 04 camera, so the cloth is down before the camera walks through its line.

Gary 6 Oct ~00:30 (Docs/Conductor/GARY_PIE_NOTES_2026-10-05.md:267): "P04's back curtain falls too late"; 5 Oct (:95):
"P04 does end on a curtain but it doesn't drop now; we walk straight through it".

Tiers: [decl] read in a file/header (cited), [meas] an earlier run's read-back record (cited), [prec] an in-repo
precedent call (cited, with whether it ran), [inf] inferred (why stated).

WHY IT IS LATE
  * The section lives in LS_S4_HangarRise (motion time; 0 = Scene 4's first frame) and was fitted on 30 Sep as
    release = T_cross - 5.0 s with T_cross = -(route_len - 10450) / 250 cm/s = -0.874 s -> release -5.874 s
    [meas Saved/CodexStructure/p04_backcloth_section_record.json; the 250 cm/s constant is
    p04_backcloth_section_apply.py:45]. The S4 rise was then re-keyed to start AT that release (W0 = -5.8739)
    [meas Saved/CodexStructure/hangar_retime_record.json W0/W1].
  * 2 Oct passage_slow_walk stretched P04 42.674 -> 180.0 s, end speed 250 -> 59.27 cm/s, tail 418.47 cm over
    169447 ticks [meas passage_slow_walk_P04_apply_SW-P04-APPLY-20261002-A.json]. The release did not move (it is
    Scene-anchored), the crossing did: the camera now reaches the hang FRONT (39.4 cm before the 10450 line, 257.9 cm
    before the stop) about 4.35-4.54 s before Scene 4, only ~1.3-1.5 s after the release [inf: arithmetic on those
    records, with and without the 1 s crossing settle; test_backcloth_lead_fit.py NUMBERS]. final11 needs ~2.2 s to get
    below the 1.80 m lens [decl Docs/ChaosClothCurtain.md:482].
  * After passage_retime_to_music (P04 -> ~50.4 s, settle-compensated walk ~214 cm/s) the crossing is ~-1.71 s and the
    lead ~4.17 s with NO change here [inf: same arithmetic]; lead 5.0 again = delta ~-0.83 s. So: run the retime first, then DRY this tool; APPLY only if
    Gary wants the 5.0 s lead back exactly, or if the measured lead is under min_lead_s.

HOW THE TIMING IS ANCHORED (what any retime does to it)
  The Arrival maps Master -> Scene -> motion time from the compiled Scene segment start every call
  [decl Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageArrival.cpp:1095-1119], and plays the
  backcloth section from every Passage frame before the cut [decl :1255-1267; MovieSceneInfinityPassageTrack.cpp:241-243].
  So the release is a fixed number of seconds BEFORE SCENE 4: moving Passage 04's end moves the release rigidly; it
  does NOT follow the camera's speed. Any walk retime changes the lead; re-run this tool's DRY after every retime.

WHAT IT WRITES (APPLY): the ONE GeometryCache section of the Arrival's backcloth binding in LS_S4_HangarRise moves by
delta = (T_cross_live - lead_s) - release_now (start and end together; offsets, length, completion unchanged). Nothing
else: no Show, Master, level, Scene, actor, rise key. Saves LS_S4_HangarRise only.
  T_cross_live = the first time the LIVE Passage 04 camera (InfinityStageCameraPilotLibrary.get_passage_camera_pose,
  [prec passage_end_drape.py:897-924, capture_p1_s1_handoff.py:54-58]) reaches the hang front of the placed backcloth
  (actor frame; hang AABB = the bake's held sample, artifact chain [prec p04_backcloth_section_apply.py:84-126]).

Modes (backcloth_lead_fit_run.py <- backcloth_lead_fit_args.json; confirm "<MODE> S4"):
  DRY    read-only; backcloth_lead_fit_dry.json; BACKCLOTH_LEAD_FIT_DRY_OK|run=..|lead_now_s=..|delta_s=..
  APPLY  guards (world, no PIE, Sequencer closed, clean census, decided_by, expected_delta_s from the DRY within one
         cache frame) -> backup the rise .uasset -> exclusive fsynced record -> move the section -> read back
         (range, offsets, engine mapping held/release through the Arrival) -> census == {rise} -> save the rise only
         -> re-read -> BACKCLOTH_LEAD_FIT_APPLY_OK
  REVERT drift check (live section == the record's after) -> backup -> recorded range -> read back -> save the rise
         only -> BACKCLOTH_LEAD_FIT_REVERT_OK
Failure: BACKCLOTH_LEAD_FIT_STOPPED|run=..|reason=..  Never Save All, never end PIE, never reload the level, no
Sequencer UI, no unreal objects in module globals. Importing without `unreal` runs nothing (test_backcloth_lead_fit.py).
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


TOOL = "backcloth_lead_fit"
MARK = "BACKCLOTH_LEAD_FIT"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENE = 4                                           # the only Arrival with a backcloth (InfinityStageArrival.h:184-189)
ARRIVAL_LABEL = "S4 Arrival"
SCENE_CUE_PREFIX = "Scene 4 — "
PASSAGE_LABEL = "Passage 4"
RISE_PATH = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
ARGS_NAME = "backcloth_lead_fit_args.json"
DRY_NAME = "backcloth_lead_fit_dry.json"
RECORD_NAME = "backcloth_lead_fit_record.json"
PED_FILE = "passage_end_drape.py"
CACHE_FPS = 30.0
SHOW_TICKS_PER_S = 24000.0
GC_TRACK = "MovieSceneGeometryCacheTrack"

DEFAULTS = {
    "lead_s": 5.0,             # Gary 30 Sep "could be 2 s earlier" -> lead 5.0 (p04_backcloth_lead5_apply.py, applied)
    "min_lead_s": 2.7,         # final11 is below the 1.80 m lens 2.20 s after release (ChaosClothCurtain.md:482) + 0.5
    "max_rise_gap_s": 1.0,     # |release - rise start| above this is a WARNING (30 Sep rule "rise starts at release")
    "lens_clear_cm": 0.0,      # the crossing is when the camera reaches the hang front minus this
    "sample_step_s": 0.05,
    "span_s": 24.0,            # how far before Scene 4 the camera is sampled (must cover the release)
    "noop_tol_s": 0.5 / CACHE_FPS,
}


class PlanError(ValueError):
    pass


# =====================================================================================================================
# Pure planner (no Unreal). Geometry: yaw-only frames, UE axes (X forward, Y right, Z up).
# =====================================================================================================================

def merged(params):
    unknown = sorted(set(params or {}) - set(DEFAULTS))
    if unknown:
        raise PlanError("UNKNOWN_PARAMS: %r" % unknown)
    out = dict(DEFAULTS)
    out.update(params or {})
    return out


def local_xy(cloth, p):
    """Camera point p in the cloth actor's frame (loc, yaw); only X/Y matter for the crossing."""
    y = math.radians(float(cloth["yaw"]))
    dx, dy = float(p[0]) - float(cloth["loc"][0]), float(p[1]) - float(cloth["loc"][1])
    return [dx * math.cos(y) + dy * math.sin(y), -dx * math.sin(y) + dy * math.cos(y)]


def crossing(samples, cloth, front_x, half_w):
    """(t, approach_sign, lateral_cm) of the first time the camera reaches the hang front from its approach side;
    t None if it never does. approach_sign = -1 when the camera comes from local -X (the hang front is hang x_lo)."""
    rows = sorted(samples, key=lambda r: r[0])
    xs = [(t, local_xy(cloth, s["loc"])) for t, s in rows]
    sign = -1.0 if xs[0][1][0] < 0.0 else 1.0
    plane = float(front_x[0] if sign < 0 else front_x[1])
    d = [(t, -sign * (p[0] - plane), p[1]) for t, p in xs]      # < 0 before the plane, from either side
    if d[0][1] >= 0.0:
        return d[0][0], sign, d[0][2]
    for (ta, a, ya), (tb, b, yb) in zip(d, d[1:]):
        if a < 0.0 <= b:
            u = (0.0 - a) / (b - a) if b != a else 0.0
            return ta + u * (tb - ta), sign, ya + u * (yb - ya)
    return None, sign, None


def section_release_motion(section, release_in_cache_s):
    """Motion time at which the section reads release_in_cache (play rate 1, not reversed, not looping)."""
    return float(section["start_s"]) + (float(release_in_cache_s) - float(section["offset_s"]))


def plan_fit(inputs, params):
    p = merged(params)
    sec, cache, sub = inputs["section"], inputs["cache"], inputs["rise_sub"]
    if abs(float(sub.get("rate", 1.0)) - 1.0) > 1.0e-9:
        raise PlanError("RATE_NOT_ONE: the rise sub-section plays at %r" % sub.get("rate"))
    to_scene = lambda m: float(sub["section_start_s"]) + (m - float(sub["inner_start_s"]) - float(sub["start_offset_s"]))
    hang = cache["hang_aabb_cm"]
    t_cross, sign, lateral = crossing(inputs["passage_camera"], inputs["cloth"],
                                      [float(hang["x"][0]) - p["lens_clear_cm"], float(hang["x"][1]) + p["lens_clear_cm"]],
                                      float(hang["y"][1]))
    rel_now_m = section_release_motion(sec, cache["release_in_cache_s"])
    rel_now = to_scene(rel_now_m)
    plan = {"lead_s": p["lead_s"], "release_now_scene_s": rel_now, "camera_cross_scene_s": t_cross,
            "approach_sign": sign, "lateral_at_cross_cm": lateral, "section_before": dict(sec),
            "rise_start_scene_s": to_scene(float(inputs["rise_start_motion_s"])),
            "passage_len_s": float(inputs["passage_len_s"]), "cache": dict(cache), "params": p}
    if t_cross is None:
        plan.update({"lead_now_s": None, "delta_s": None, "section_after": None, "release_new_scene_s": None})
        plan["digest"] = digest(plan)
        return plan
    rel_new = t_cross - float(p["lead_s"])
    delta = rel_new - rel_now
    tick = float(sec["tick_rate"])
    delta = round(delta * tick) / tick                             # whole ticks: start and end move together exactly
    after = dict(sec)
    after.update({"start_s": float(sec["start_s"]) + delta, "end_s": float(sec["end_s"]) + delta})
    plan.update({"lead_now_s": t_cross - rel_now, "delta_s": delta, "release_new_scene_s": rel_now + delta,
                 "lead_new_s": t_cross - (rel_now + delta), "section_after": after})
    plan["digest"] = digest(plan)
    return plan


def digest(plan):
    body = {k: v for k, v in plan.items() if k != "digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def check_plan(plan, mode="DRY"):
    """(refusals, warnings). Every refusal has a failing control in test_backcloth_lead_fit.py."""
    p, ref, warn = plan["params"], [], []
    if plan["camera_cross_scene_s"] is None:
        ref.append("CAMERA_NEVER_REACHES_CLOTH: the Passage camera never reaches the hang front (not in its path?)")
        return ref, warn
    if abs(float(plan["lateral_at_cross_cm"])) > float(plan["cache"]["hang_aabb_cm"]["y"][1]):
        ref.append("CAMERA_PASSES_BESIDE_CLOTH: %.1f cm lateral at the crossing (half width %.1f)"
                   % (plan["lateral_at_cross_cm"], plan["cache"]["hang_aabb_cm"]["y"][1]))
    if plan["camera_cross_scene_s"] >= 0.0:
        ref.append("CROSSING_NOT_PRE_SCENE: %.3f s (the Arrival plays the cloth only before Scene 4)"
                   % plan["camera_cross_scene_s"])
    if float(p["lead_s"]) < float(p["min_lead_s"]):
        ref.append("LEAD_BELOW_MIN: lead_s %.2f < min_lead_s %.2f (the cloth would still be above the lens)"
                   % (p["lead_s"], p["min_lead_s"]))
    rel_new = plan["release_new_scene_s"]
    if rel_new <= -float(plan["passage_len_s"]) + 1.0:
        ref.append("RELEASE_BEFORE_PASSAGE: release %.3f s, Passage 04 is %.3f s long" % (rel_new, plan["passage_len_s"]))
    sa = plan["section_after"]
    if sa["start_s"] - (sa["end_s"] - sa["start_s"]) < -float(plan["passage_len_s"]) - 60.0:
        ref.append("SECTION_ABSURD: %r" % sa)
    if abs(float(plan["delta_s"])) <= float(p["noop_tol_s"]):
        (ref if mode == "APPLY" else warn).append("NOOP: the release is already at crossing - %.2f s (delta %.4f s)"
                                                  % (p["lead_s"], plan["delta_s"]))
    gap = rel_new - plan["rise_start_scene_s"]
    if abs(gap) > float(p["max_rise_gap_s"]):
        warn.append("RELEASE_VS_RISE: the cloth releases %.2f s %s the hangar starts rising (30 Sep rule: rise starts at "
                    "the release); the rise is NOT moved by this tool (look call)"
                    % (abs(gap), "before" if gap < 0 else "after"))
    if plan["lead_now_s"] is not None and plan["lead_now_s"] < float(p["min_lead_s"]):
        warn.append("LEAD_NOW_SHORT: today the camera reaches the cloth %.2f s after the release (min %.2f): the "
                    "'walk straight through it' Gary saw" % (plan["lead_now_s"], p["min_lead_s"]))
    return ref, warn


def apply_gate(plan, args_expected):
    """APPLY must reproduce the DRY Gary/the conductor approved: same delta within one cache frame."""
    if args_expected is None:
        return ["EXPECTED_MISSING: copy expected_delta_s from the DRY into the args"]
    if abs(float(args_expected) - float(plan["delta_s"])) > 1.0 / CACHE_FPS:
        return ["PLAN_CHANGED_SINCE_DRY: expected %.4f s, now %.4f s (re-run DRY)" % (float(args_expected), plan["delta_s"])]
    return []


def section_matches(live, want, tick_rate, tol_ticks=1.5):
    out = []
    for k in ("start_s", "end_s"):
        if abs(float(live[k]) - float(want[k])) > tol_ticks / float(tick_rate):
            out.append("%s %.6f want %.6f" % (k, live[k], want[k]))
    for k in ("offset_ticks", "end_offset_ticks"):
        if int(live[k]) != int(want[k]):
            out.append("%s %d want %d" % (k, live[k], want[k]))
    return out


# =====================================================================================================================
# Unreal side
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def load_ped(here=None):
    """passage_end_drape.py definitions only (its main() not run), as passage_end_drape.load_cs loads curtain_sleight."""
    path = os.path.join(here or _here(), PED_FILE)
    with open(path, "r", encoding="utf-8") as handle:
        src = handle.read()
    cut = src.rindex("if unreal is not None:")
    ns = {"__name__": "ped_lib_for_backcloth_lead_fit", "__file__": path}
    exec(compile(src[:cut], path, "exec"), ns)  # noqa: S102 - reviewed project file, definitions only
    return ns


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _section_row(sec, tick_rate):
    prm = sec.get_editor_property("params")
    return {"start_s": float(sec.get_start_frame_seconds()), "end_s": float(sec.get_end_frame_seconds()),
            "offset_ticks": int(prm.get_editor_property("start_frame_offset").value),
            "offset_s": int(prm.get_editor_property("start_frame_offset").value) / tick_rate,
            "end_offset_ticks": int(prm.get_editor_property("end_frame_offset").value), "tick_rate": tick_rate,
            "completion": str(sec.get_editor_property("eval_options").get_editor_property("completion_mode"))}


def _bake_facts(cache, run):
    """Release and the held sample's AABB from the cache's own artifact chain (memory puss-bake-facts-from-artifact-
    chain; p04_backcloth_section_apply.py:84-126 [prec, ran 30 Sep]). Axis: UE X = bake y, UE Y = bake x."""
    files = list(cache.get_editor_property("asset_import_data").extract_filenames())
    stem = os.path.splitext(os.path.basename(files[0]))[0] if files else ""
    prefix = cache.get_name() + "_"
    if not stem.startswith(prefix):
        _stop(run, "BAKE_UNTRACEABLE|source=%s" % stem)
    bake_id = stem[len(prefix):]
    path = os.path.join(os.path.dirname(_here()), "CodexSoftGoods", "DropBake", bake_id + ".json")
    with open(path, "r", encoding="utf-8") as handle:
        bake = json.load(handle)
    if bake.get("release_frame") is None or bake.get("show_start") is None:
        _stop(run, "BAKE_HAS_NO_RELEASE|%s" % bake_id)
    in_cache = (int(bake["release_frame"]) - int(bake["show_start"])) / CACHE_FPS
    held = str(int(bake["release_frame"]) - 1)
    a = (bake.get("checkpoints") or {}).get(held, {}).get("aabb_m")
    if not a:
        _stop(run, "HOLD_SAMPLE_HAS_NO_CHECKPOINT|%s|%s" % (bake_id, held))
    yi = min(abs(a["x"][0]), abs(a["x"][1]))
    return {"bake_id": bake_id, "release_in_cache_s": in_cache, "held_sample": int(held),
            "hang_aabb_cm": {"x": [a["y"][0] * 100.0, a["y"][1] * 100.0], "y": [-yi * 100.0, yi * 100.0],
                             "z": [a["z"][0] * 100.0, a["z"][1] * 100.0]}}


def _gather(run, ped, cs, params):
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    arrivals = [a for a in actors if str(a.get_actor_label()) == ARRIVAL_LABEL]
    if len(arrivals) != 1:
        _stop(run, "ARRIVAL_COUNT|%d" % len(arrivals))
    arrival = arrivals[0]
    cloth = arrival.get_editor_property("backcloth_actor")
    guid = cs["_guid"](arrival.get_editor_property("backcloth_binding_guid"))
    if cloth is None or not guid.strip("0"):
        _stop(run, "NO_BACKCLOTH_ON_S4_ARRIVAL")
    rise = arrival.get_editor_property("motion_sequence")
    if rise is None or rise.get_path_name().split(".")[0] != RISE_PATH:
        _stop(run, "MOTION_SEQUENCE|%s" % (rise.get_path_name() if rise else None))
    tick = rise.get_tick_resolution()
    tick_rate = tick.numerator / float(tick.denominator)
    rate = rise.get_display_rate()
    rise_fps = rate.numerator / float(rate.denominator)
    binds = [b for b in rise.get_bindings() if cs["_guid"](b.get_id()) == guid]
    if len(binds) != 1:
        _stop(run, "BACKCLOTH_BINDING|%d" % len(binds))
    gts = [t for t in binds[0].get_tracks() if t.get_class().get_name() == GC_TRACK]
    secs = list(gts[0].get_sections()) if len(gts) == 1 else []
    if len(gts) != 1 or len(secs) != 1:
        _stop(run, "GC_TRACK_OR_SECTION_COUNT|tracks=%d|sections=%d" % (len(gts), len(secs)))
    section = _section_row(secs[0], tick_rate)
    comp = cloth.get_component_by_class(unreal.GeometryCacheComponent)
    cache_asset = comp.get_editor_property("geometry_cache")
    cache = _bake_facts(cache_asset, run)
    cache["duration_s"] = float(comp.get_duration())

    root_guid = cs["_guid"](arrival.get_editor_property("motion_binding_guid"))
    roots = [b for b in rise.get_bindings() if cs["_guid"](b.get_id()) == root_guid]
    pitch = []
    for track in (roots[0].get_tracks() if len(roots) == 1 else []):
        if isinstance(track, unreal.MovieScene3DTransformTrack):
            for s in track.get_sections():
                ch = list(s.get_all_channels())
                if len(ch) > 4:                                   # channel 4 = pitch (hangar_retime_apply.py:328)
                    for key in ch[4].get_keys():
                        when = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
                        pitch.append([int(when.frame_number.value) / tick_rate, float(key.get_value())])
    rise_start_motion, _ = ped["rise_start_of"](pitch)

    show = unreal.load_asset(SHOW_PATH)
    cues = [c for c in show.get_editor_property("cues")
            if str(c.get_editor_property("label")).startswith(SCENE_CUE_PREFIX) and c.get_editor_property("enabled")]
    if len(cues) != 1:
        _stop(run, "SCENE_CUE_COUNT|%d" % len(cues))
    scene_seq = cues[0].get_editor_property("scene").get_editor_property("sequence")
    subs = []
    for tt in (unreal.MovieSceneSubTrack, unreal.MovieSceneCinematicShotTrack):
        for t in scene_seq.find_tracks_by_type(tt):
            subs.extend(s for s in t.get_sections() if s.get_sequence() is not None
                        and s.get_sequence().get_path_name().split(".")[0] == RISE_PATH)
    if len(subs) != 1:
        _stop(run, "RISE_NOT_NESTED_ONCE|%d" % len(subs))
    prm = subs[0].get_editor_property("parameters")
    rise_sub = {"section_start_s": float(subs[0].get_start_frame_seconds()),
                "start_offset_s": int(prm.get_editor_property("start_frame_offset").value) / tick_rate,
                "inner_start_s": int(rise.get_playback_start()) / rise_fps, "rate": 1.0}

    psets = [ps for ps in show.get_editor_property("passage_settings") if str(ps.get_editor_property("label")) == PASSAGE_LABEL]
    if len(psets) != 1:
        _stop(run, "PASSAGE_SETTINGS|%d" % len(psets))
    pguid = psets[0].get_editor_property("passage_guid")
    lib = unreal.InfinityStageCameraPilotLibrary
    fr = ped["_unwrap"](lib.get_passage_frame_range(show, pguid), 2)
    if fr is None:
        _stop(run, "PASSAGE_FRAME_RANGE")
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = [s for s in tr.get_editor_property("segments") if str(s.get_editor_property("label")) == str(cues[0].get_editor_property("label"))]
    scene_start_tick = int(segs[0].get_editor_property("start_frame").value) if len(segs) == 1 else None
    del tr
    if scene_start_tick is None:
        _stop(run, "SCENE_SEGMENT_NOT_FOUND")
    if abs(scene_start_tick - int(fr[1])) > 1:
        _stop(run, "PASSAGE_END_NOT_SCENE_START|%d|%d" % (int(fr[1]), scene_start_tick))
    passage_len_s = (int(fr[1]) - int(fr[0])) / SHOW_TICKS_PER_S
    span = min(float(params["span_s"]), passage_len_s)
    step = float(params["sample_step_s"])
    samples = []
    n = int(round(span / step))
    for i in range(n + 1):
        t = -span + i * step
        tick_at = int(round(scene_start_tick + t * SHOW_TICKS_PER_S)) - (1 if i == n else 0)
        pose = ped["_unwrap"](lib.get_passage_camera_pose(show, pguid, tick_at), 3)
        if pose is not None:
            loc = pose[0].translation
            samples.append([round(t, 4), {"loc": [float(loc.x), float(loc.y), float(loc.z)]}])
    if len(samples) < 10:
        _stop(run, "PASSAGE_CAMERA_SAMPLES|%d" % len(samples))
    cl, cr = cloth.get_actor_location(), cloth.get_actor_rotation()
    inputs = {"section": section, "cache": cache, "rise_sub": rise_sub, "rise_start_motion_s": rise_start_motion,
              "passage_camera": samples, "passage_len_s": passage_len_s, "scene_start_tick": scene_start_tick,
              "cloth": {"label": str(cloth.get_actor_label()), "loc": [float(cl.x), float(cl.y), float(cl.z)],
                        "yaw": float(cr.yaw), "pitch": float(cr.pitch), "roll": float(cr.roll)},
              "binding_guid": guid}
    return inputs, {"show": show, "arrival": arrival, "rise": rise, "section": secs[0], "comp": comp}


def _engine_check(h, inputs, want_section, release_scene_s, ped):
    """Through the Arrival (the production evaluator): 1 s before the section the held sample, at the release the
    release sample [prec p04_backcloth_section_apply.py:234-238, ran 30 Sep]."""
    dur = inputs["cache"]["duration_s"]
    st = inputs["scene_start_tick"]
    sub = inputs["rise_sub"]
    to_scene = lambda m: float(sub["section_start_s"]) + (m - float(sub["inner_start_s"]) - float(sub["start_offset_s"]))
    at = lambda s: ped["_unwrap"](h["arrival"].resolve_backcloth_time_at_master_frame(
        h["show"], ped["_master_time"](st + s * SHOW_TICKS_PER_S), dur), 1)
    held = at(to_scene(want_section["start_s"]) - 1.0)
    rel = at(release_scene_s)
    bad = []
    if held is None or abs(held - want_section["offset_ticks"] / want_section["tick_rate"]) > 0.5 / CACHE_FPS:
        bad.append("HELD %r" % held)
    if rel is None or abs(rel - inputs["cache"]["release_in_cache_s"]) > 0.5 / CACHE_FPS:
        bad.append("RELEASE %r" % rel)
    return bad, {"held": held, "at_release": rel}


def main():
    here = _here()
    run = datetime.datetime.now().strftime("BLF-%Y%m%d-%H%M%S")
    ped = load_ped(here)
    cs = ped["load_cs"](here)
    with open(os.path.join(here, ARGS_NAME), "r", encoding="utf-8") as handle:
        args = json.load(handle)
    run = str(args.get("run_id") or run)
    mode = str(args.get("mode") or "DRY").upper()
    params = merged(args.get("params") or {})
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    early = []
    if mode not in ("DRY", "APPLY", "REVERT"):
        early.append("MODE_INVALID")
    if args.get("confirm") != "%s S4" % mode:
        early.append("CONFIRM_MISMATCH: want %r" % ("%s S4" % mode))
    if editor.get_game_world() is not None:
        early.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        early.append("SEQUENCER_IS_OPEN")
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
    census0 = cs["_census"]()
    if census0 != {"content": [], "maps": []}:
        early.append("DIRTY_CENSUS: %s" % json.dumps(census0))
    if mode in ("APPLY", "REVERT") and not str(args.get("decided_by") or "").strip():
        early.append("NOT_DECIDED: args decided_by is empty")
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    record_path = os.path.join(here, RECORD_NAME)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())

    if mode == "REVERT":
        rec = json.load(open(record_path, encoding="utf-8"))
        if not rec.get("applied"):
            _stop(run, "NO_APPLIED_RECORD")
        inputs, h = _gather(run, ped, cs, params)
        live = _section_row(h["section"], inputs["section"]["tick_rate"])
        drift = section_matches(live, rec["section_after"], live["tick_rate"])
        if drift:
            _stop(run, "STATE_DRIFTED_SINCE_APPLY|%r|restore from %s instead" % (drift, rec["backup"]))
        backup = os.path.join(project, "Backups", "PreBackclothLeadFitRevert-" + run)
        os.makedirs(backup, exist_ok=False)
        shutil.copy2(cs["_content_file"](RISE_PATH), backup)
        before = rec["section_before"]
        h["rise"].modify()
        h["section"].set_range_seconds(float(before["start_s"]), float(before["end_s"]))
        live = _section_row(h["section"], before["tick_rate"])
        bad = section_matches(live, before, before["tick_rate"])
        bad += _engine_check(h, inputs, before, rec["plan"]["release_now_scene_s"], ped)[0]
        if cs["_census"]() != {"content": [RISE_PATH], "maps": []}:
            bad.append("UNEXPECTED_DIRTY %s" % json.dumps(cs["_census"]()))
        if bad:
            _stop(run, "REVERT_READBACK|%r|NOTHING SAVED; Don't-Save restart" % bad)
        if not unreal.EditorAssetLibrary.save_asset(RISE_PATH, only_if_is_dirty=True):
            _stop(run, "SAVE_FAILED")
        if cs["_census"]() != {"content": [], "maps": []}:
            _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(cs["_census"]()))
        os.rename(record_path, record_path + ".reverted-" + run)
        unreal.log("%s_REVERT_OK|run=%s|section=[%.4f,%.4f)|backup=%s" % (MARK, run, before["start_s"], before["end_s"], backup))
        return

    inputs, h = _gather(run, ped, cs, params)
    plan = plan_fit(inputs, params)
    refusals, warnings = check_plan(plan, mode)
    if mode == "DRY":
        report = {"run": run, "plan": plan, "refusals": refusals, "warnings": warnings, "inputs": inputs,
                  "expected_for_apply_args": {"expected_delta_s": plan.get("delta_s")}}
        with open(os.path.join(here, DRY_NAME), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, sort_keys=True, default=str)
        for r in refusals:
            unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, r))
        for w in warnings:
            unreal.log("%s_WARNING|run=%s|%s" % (MARK, run, w))
        if cs["_census"]() != {"content": [], "maps": []}:
            _stop(run, "DRY_DIRTIED|%s" % json.dumps(cs["_census"]()))
        unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|release_now=%s|cross=%s|lead_now_s=%s|delta_s=%s|"
                   "release_new=%s|rise_start=%s|digest=%s" % (MARK, run, int(not refusals), plan["release_now_scene_s"],
                   plan["camera_cross_scene_s"], plan["lead_now_s"], plan["delta_s"], plan.get("release_new_scene_s"),
                   plan["rise_start_scene_s"], plan["digest"]))
        return

    # APPLY
    refusals += apply_gate(plan, args.get("expected_delta_s"))
    if os.path.exists(record_path):
        refusals.append("RECORD_EXISTS: REVERT first")
    if refusals:
        _stop(run, "REFUSED|" + " || ".join(refusals))
    backup = os.path.join(project, "Backups", "PreBackclothLeadFit-" + run)
    os.makedirs(backup, exist_ok=False)
    src = cs["_content_file"](RISE_PATH)
    shutil.copy2(src, backup)
    record = {"run": run, "world": EXPECTED_WORLD, "rise": RISE_PATH, "binding_guid": inputs["binding_guid"],
              "backup": backup, "applied": False, "plan": plan, "section_before": inputs["section"],
              "section_after": plan["section_after"], "decided_by": args.get("decided_by"), "warnings": warnings}
    ped["write_record_exclusive"](record_path, record)
    sa = plan["section_after"]
    h["rise"].modify()
    h["section"].set_range_seconds(float(sa["start_s"]), float(sa["end_s"]))
    live = _section_row(h["section"], sa["tick_rate"])
    bad = section_matches(live, sa, sa["tick_rate"])
    eng_bad, eng = _engine_check(h, inputs, sa, plan["release_new_scene_s"], ped)
    bad += eng_bad
    if cs["_census"]() != {"content": [RISE_PATH], "maps": []}:
        bad.append("UNEXPECTED_DIRTY %s" % json.dumps(cs["_census"]()))
    if bad:
        _stop(run, "PRESAVE_READBACK|%r|NOTHING SAVED; Don't-Save restart; record %s stays applied=false" % (bad, record_path))
    if not unreal.EditorAssetLibrary.save_asset(RISE_PATH, only_if_is_dirty=True):
        _stop(run, "SAVE_FAILED")
    if cs["_census"]() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(cs["_census"]()))
    reread = _section_row(h["section"], sa["tick_rate"])
    if section_matches(reread, sa, sa["tick_rate"]):
        _stop(run, "READBACK_AFTER_SAVE|restore from %s" % backup)
    record.update({"applied": True, "engine_readback": eng, "section_live_after": reread})
    ped["update_record"](record_path, record)
    unreal.log("%s_APPLY_OK|run=%s|delta_s=%.4f|release=%.4f|cross=%.4f|lead=%.3f|held=%s|at_release=%s|backup=%s|record=%s"
               % (MARK, run, plan["delta_s"], plan["release_new_scene_s"], plan["camera_cross_scene_s"],
                  plan["lead_new_s"], eng["held"], eng["at_release"], backup, record_path))


def _main_guarded():
    try:
        main()
    except ValueError as exc:                   # this tool's and passage_end_drape's PlanError (both ValueError)
        _stop(datetime.datetime.now().strftime("BLF-%Y%m%d-%H%M%S"), "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    _main_guarded()
