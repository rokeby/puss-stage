"""KLARA S4 v5 PREVIEW (7 Oct evening): stills of the v5 dark glide-end view BEFORE any v5 APPLY.
Gary 7 Oct ~18:00 (his own words, conductor session): "oh, in that case maybe we don't strike up, we just arrive in the
dark?" and "stills first, then apply". So klara_reveal v5 runs with strike_lights "none" (zero strikes, preroll off) and
this tool shows the glide-end framing first. Offline-written; NEVER RUN IN UNREAL by its author.

Two halves:
  OFFLINE (python klara_s4v5_preview.py [--out PATH]): preview_pose() computes, from the recorded live facts the v5
    harness uses (klara_reveal_dry_S4.json, run KLARAREVEAL-20261007-095026) and klara_reveal_s4v5_args.json, the v5
    glide-end camera pose (world loc / rot [roll, pitch, yaw] / focal / filmback), her frame-6 cut pose, and the
    Scene-4 frames of glide start / glide end / hard cut under strike_lights "none". It checks that pose against the
    LIVE level placement (klara_reveal_record_S4.json, the applied v4) and picks the LIVE PIE frames to shoot at, since
    PIE plays the live v4 state, not v5. -> klara_s4v5_preview_pose.json.
  PIE (ExecuteProjectPythonFile CodexConductor/KlaraIngest/klara_s4v5_preview.py, args klara_s4v5_preview_args.json):
    PIE-ONLY, read-only to assets and levels, never saves, never ends PIE, never touches the editor world. Phases:
      jump     pause + scrub the Master to Scene 4 start + scene_frame through the Show Root transport
               (InfinityStageShowRoot.transport.scrub_to_master_frame; Master ticks 24000/s; Scene 4 = the
               transport.segments row of type SCENE whose label starts "Scene 4"). LevelSequenceActor.get_sequence_player
               is NOT used (absent in UE 5.8 Python).
      camera   spawn a transient CineCameraActor IN THE PIE WORLD at pose_key's pose (filmback, focal, manual focus),
               optional exposure_bias_ev (camera post-process override_auto_exposure_bias + auto_exposure_bias: it
               REPLACES the volumes' bias, it does not add to it [inf: camera PP blends last at weight 1] - a FRAMING
               aid only), make it the view target (PlayerController.set_view_target_with_blend, 0 s). The previous
               view target is written to the state file BEFORE anything changes.
      shot     HighResShot 1600x900 filename=path (refuses an existing file; checks the frame and the view target).
      check    the shot file exists, is stable and >= 20 kB (HighResShot is asynchronous: run check in a later call).
      cleanup  restore the recorded view target, destroy the preview camera, read back that none is left.
    Markers: S4V5PREVIEW_OK|run=..|phase=..|... and S4V5PREVIEW_FAILED|run=..|phase=..|reason=... (log_error). A
    refusal is always FAILED, never OK. Every phase compares the dirty-package census before/after (must not change).
    No unreal objects in module globals (memory puss-mcp-python-crashes-the-editor); no Saved/ imports in the PIE path
    (memory ue58-python-stale-module-cache).
Tiers: [decl] header/source we can read, [prec] in-repo precedent, [meas] record/DRY JSON, [inf] inferred.
"""
import datetime
import hashlib
import json
import math
import os
import sys

try:
    import unreal
except ModuleNotFoundError:  # offline CLI / harness
    unreal = None

TOOL = "klara_s4v5_preview"
MARK = "S4V5PREVIEW"
ARGS_NAME = "klara_s4v5_preview_args.json"
POSE_NAME = "klara_s4v5_preview_pose.json"
STATE_NAME = "klara_s4v5_preview_state.json"
MASTER_TICKS_PER_S = 24000                          # [prec pie_jump_play.py:23, pie_exposure_bench.py:21]
CAMERA_LABEL = "S4V5 Preview Camera (PIE only)"
PHASES = ("jump", "camera", "shot", "check", "cleanup")
POSE_KEYS = ("glide_end", "her_cut")
RESOLUTION = (1600, 900)
SHOT_MIN_BYTES = 20000
LOC_TOL_CM = 0.05
ROT_TOL_DEG = 0.05
LT_TOL_CM = 0.5                                      # live level placement vs the v5 plan's (pose validity)
OFFLINE_GATE_REFUSALS = ("HER_CUT_PATHS_UNREAD", "BACKCLOTH_STATE_UNREAD")   # inputs the DRY reads live, not the pose


class PreviewError(Exception):
    pass


# =====================================================================================================================
# Pure (offline; harness: test_klara_reveal_v5_offline.py Preview*)
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "KlaraIngest")
    return os.path.dirname(os.path.abspath(__file__))


def load_json(path):
    with open(path, "r", encoding="utf-8") as h:
        return json.load(h)


def wrap(deg):
    d = (float(deg) + 180.0) % 360.0 - 180.0
    return 180.0 if d == -180.0 else d


def keys_at(keys, frame):
    """Value of [[frame, value], ...] at frame -> (value, how). Exact key / constant outside; between keys LINEAR
    ('linear' marks it [inf]: the written keys' interpolation is the writer's, not re-read here)."""
    if not keys:
        return None, "unkeyed"
    ks = sorted([float(k[0]), k[1]] for k in keys)
    for t, v in ks:
        if t == frame:
            return v, "key"
    if frame < ks[0][0]:
        return ks[0][1], "before_first"
    if frame > ks[-1][0]:
        return ks[-1][1], "after_last"
    for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
        if t0 < frame < t1:
            if isinstance(v0, list):
                return [a + (b - a) * (frame - t0) / (t1 - t0) for a, b in zip(v0, v1)], "linear"
            return v0 + (v1 - v0) * (frame - t0) / (t1 - t0), "linear"
    return None, "unresolved"


def master_ticks(seg_start_ticks, scene_frame, scene_fps):
    """Absolute Master frame (24000 ticks/s) of a Scene frame. [inf: segment StartFrame = the Scene's frame 0, as
    pie_jump_play.py / pie_exposure_bench.py assume; declared FFrameNumber StartFrame at
    InfinityStageTransportController.h:218-219]."""
    return int(seg_start_ticks) + int(round(float(scene_frame) * MASTER_TICKS_PER_S / float(scene_fps)))


def v5_facts_from_dry(dry, args5, scene_fps=25.0):
    """The harness's v5 facts recipe (test_klara_reveal_v5_offline.v5facts) WITHOUT the bytes-read gate inputs
    (subjects, her cut curves, backcloth): the glide-end pose and the timeline under strike_lights none depend on none
    of them (subjects only choose strikers; the gate only refuses)."""
    import copy
    import klara_reveal as R
    f = copy.deepcopy(dry["facts"])
    f["reveal"] = dict(f.get("reveal") or {}, requested="strike_preroll", style="strike_preroll", why="explicit")
    f["lit"] = R.detect_lit(f, args5, scene_fps)
    R.apply_lit_values(f, f["lit"]["frame"])
    f["v5"] = {"subjects": [], "her_cuts": [], "backcloth": None}
    return f


def _f(x, n=4):
    return None if x is None else round(float(x), n)


def preview_pose(dry, args5, record=None, plan=None):
    """-> the preview pose report (see module docstring). plan: a v5 plan already built (the harness passes its
    bytes-fixture plan to prove the offline recipe gives the same pose/frames); else built here from dry."""
    import klara_reveal as R
    key = str(args5.get("scene"))
    cfg5 = R.v5_cfg(args5, key)
    if cfg5.get("strike_lights") != "none":
        raise PreviewError("PREVIEW_ARGS_NOT_DARK_ARRIVAL: strike_lights %r (this preview is the 'none' entry)"
                           % (cfg5.get("strike_lights"),))
    fps = float(dry["facts"]["fps"])
    if plan is None:
        plan = R.build_plan(v5_facts_from_dry(dry, args5, fps), args5)
    if plan.get("version") != 5:
        raise PreviewError("NOT_A_V5_PLAN: version %r refusals %s" % (plan.get("version"), plan.get("refusals")))
    tl = plan["timeline"]
    ge, hc = plan["glide_end"]["pose"], plan["poses"]["her_cut"]
    other = [r for r in plan["refusals"] if not r.startswith(OFFLINE_GATE_REFUSALS)]
    strikes = [r["label"] for r in plan.get("her_lights") or [] if r.get("strikes")]
    out = {"tool": TOOL, "source": {"dry_run": dry.get("run"), "dry_file": "klara_reveal_dry_S4.json",
                                    "args_file": "klara_reveal_s4v5_args.json",
                                    "tier": "[meas] DRY facts + [harness] pure klara_reveal v5 code; not Unreal"},
           "scene": key, "scene_fps": fps, "strike_lights": cfg5["strike_lights"],
           "preroll": (plan.get("preroll") or {}).get("mode", R.v5_preroll_mode(cfg5)),
           "n_strikes": len(strikes), "sensor_mm": list(plan["sensor_mm"]),
           "poses": {"glide_end": {"loc": [_f(v) for v in ge["loc"]], "rot_roll_pitch_yaw": [_f(v) for v in ge["rot"]],
                                   "focal_mm": _f(ge["focal"]), "focus_cm": _f(ge["focus"])},
                     "her_cut": {"loc": [_f(v) for v in hc["loc"]], "rot_roll_pitch_yaw": [_f(v) for v in hc["rot"]],
                                 "focal_mm": _f(hc["focal"]), "focus_cm": _f(hc["focus"]),
                                 "her_frame": plan["slot"]["her_frame_at_cut"]}},
           "v5_frames": {"land": tl["land"], "glide_start": tl["glide_in"][0], "glide_end": tl["glide_in"][1],
                         "cut": tl["cut"], "rest_before_cut_s": _f((tl["cut"] - tl["glide_in"][1]) / fps, 3),
                         "env_ramp": tl["crossfade"], "slot": tl["slot"], "planned_end": tl["planned_end"],
                         "seconds": {k: _f(v / fps, 3) for k, v in (("glide_start", tl["glide_in"][0]),
                                                                     ("glide_end", tl["glide_in"][1]),
                                                                     ("cut", tl["cut"]))},
                         "master_ticks_from_scene_start": {k: int(round(v * MASTER_TICKS_PER_S / fps)) for k, v in
                                                           (("glide_start", tl["glide_in"][0]),
                                                            ("glide_end", tl["glide_in"][1]), ("cut", tl["cut"]))}},
           "level_transform_v5": plan["level_transform_after"],
           "plan_refusals_offline_expected": [r for r in plan["refusals"] if r.startswith(OFFLINE_GATE_REFUSALS)],
           "plan_refusals_other": other, "plan_warnings": plan["warnings"], "glide_in": plan["glide"]["in"],
           "glide_end_sees": plan.get("glide_end_sees")}
    out["live"] = live_frames(record, plan) if record is not None else {"valid": False, "why": "NO_LIVE_RECORD"}
    out["ok"] = not other and out["live"].get("valid", False) and out["n_strikes"] == 0
    return out


def live_frames(record, plan):
    """PIE plays the LIVE (applied v4) S4, not v5. -> is the v5 world pose valid there (same level placement), and
    which live Scene-4 frames bracket the v5 dark arrival at C-1 (her lights 0, her env at her frame-6 value):
      dark  = live crossfade start: her lights 0, env 0, ceiling glows faded, bulbs hidden - DARKER than v5 at C-1
              (v5 has the env up by then); the framing still (+ a bias variant);
      env   = live cut - 1: env at her frame-6 value, but her own frame-6 lights are ALSO on (v5 holds them 0 until the
              cut) - BRIGHTER than v5 at C-1;
      her   = live cut: her frame 6 through her own camera (the show's view target) - what the hard cut lands on.
    Light/env values are evaluated from the record's written keys [meas record; 'linear' = [inf]]."""
    out = {"run": record.get("run"), "applied": bool(record.get("applied"))}
    rp = record.get("plan") or {}
    lt_live, lt5 = rp.get("level_transform_after"), plan["level_transform_after"]
    if not record.get("applied") or not lt_live or not rp.get("timeline"):
        return dict(out, valid=False, why="LIVE_RECORD_NOT_APPLIED_OR_INCOMPLETE")
    dl = [float(lt_live["loc"][i]) - float(lt5["loc"][i]) for i in range(3)]
    out["level_transform_live"] = lt_live
    out["level_delta_live_minus_v5_cm"] = [_f(v) for v in dl]
    out["valid"] = max(abs(v) for v in dl) <= LT_TOL_CM and abs(wrap(float(lt_live["yaw"]) - float(lt5["yaw"]))) < 1e-6
    if not out["valid"]:
        out["why"] = "LIVE_LEVEL_PLACEMENT_DIFFERS: the v5 world pose would be wrong in PIE by %s cm" % out[
            "level_delta_live_minus_v5_cm"]
    tl = rp["timeline"]
    frames = {"dark": int(tl["crossfade"][0]), "env": int(tl["cut"]) - 1, "her": int(tl["cut"])}
    out["timeline"] = {k: tl.get(k) for k in ("land", "glide_in", "crossfade", "cut", "slot", "hers_dark",
                                              "ours_hidden_from", "glow_fade", "rig_dark")}
    out["frames"] = frames
    states = {}
    for nm, fr in frames.items():
        lights = {}
        for r in rp.get("her_lights") or []:
            v, how = keys_at(r.get("intro_keys"), fr)
            lights[r["label"]] = {"value": _f(v), "how": how}
        env = {}
        for e in rp.get("her_env") or []:
            if e.get("intro"):
                v, how = keys_at(e["intro"], fr)
                env[e["label"]] = {"value": _f(v, 6), "how": how, "her_value": _f(e.get("target_intro"), 6)}
        glow = {}
        for h in rp.get("hangar_lights") or []:
            if h.get("action") == "fade_color" and h.get("color_keys"):
                v, how = keys_at(h["color_keys"], fr)
                glow[h["label"]] = {"rgb_max": _f(max(v[:3]) if v else None), "how": how}
        rb = (rp.get("rig_bulbs_hidden") or {}).get("range") or [None, None]
        states[nm] = {"frame": fr, "her_lights": lights, "her_env": env, "ceiling_glows": glow,
                      "her_lights_all_zero": all((x["value"] or 0.0) <= 1e-6 for x in lights.values()),
                      "env_all_zero": all((x["value"] or 0.0) <= 1e-9 for x in env.values()),
                      "bulbs_hidden": rb[0] is not None and rb[0] <= fr < rb[1]}
    out["states"] = states
    return out


def call_sequence(pose, run_prefix="S4V5PREVIEW"):
    """The conductor's exact sequence of args (one MCP call each, same request file)."""
    lv = (pose.get("live") or {}).get("frames") or {}
    shots = os.path.join(_here(), "S4V5Preview").replace("\\", "/")
    seq = []
    for tag, fr, ev, pk in (("dark_true", lv.get("dark"), None, "glide_end"),
                            ("dark_plus6ev", lv.get("dark"), 6.0, "glide_end"),
                            ("env_true", lv.get("env"), None, "glide_end")):
        run = "%s-%s" % (run_prefix, tag)
        base = {"run": run, "segment": "Scene 4", "scene_frame": fr, "scene_fps": pose["scene_fps"],
                "pose_file": POSE_NAME, "pose_key": pk, "exposure_bias_ev": ev, "expect_view": "preview",
                "path": "%s/s4v5_glide_end_f%s_%s.png" % (shots, fr, tag), "disable_performance_mode": False}
        seq += [dict(base, phase="jump"), dict(base, phase="jump"), dict(base, phase="camera"),
                dict(base, phase="shot"), dict(base, phase="check"), dict(base, phase="cleanup")]
    run = "%s-her_f6" % run_prefix
    base = {"run": run, "segment": "Scene 4", "scene_frame": lv.get("her"), "scene_fps": pose["scene_fps"],
            "pose_file": POSE_NAME, "pose_key": None, "exposure_bias_ev": None, "expect_view": "show",
            "path": "%s/s4v5_her_frame6_f%s.png" % (shots, lv.get("her")), "disable_performance_mode": False}
    seq += [dict(base, phase="jump"), dict(base, phase="jump"), dict(base, phase="shot"), dict(base, phase="check")]
    return seq


def validate_args(a):
    r = []
    if not str(a.get("run") or ""):
        r.append("RUN_MISSING")
    if a.get("phase") not in PHASES:
        r.append("PHASE_INVALID: %r" % a.get("phase"))
    if a.get("phase") == "jump":
        if not isinstance(a.get("scene_frame"), int) or a["scene_frame"] < 0:
            r.append("SCENE_FRAME_INVALID: %r" % a.get("scene_frame"))
        if not str(a.get("segment") or ""):
            r.append("SEGMENT_MISSING")
    if a.get("phase") in ("jump", "shot") and not (isinstance(a.get("scene_fps"), (int, float)) and a["scene_fps"] > 0):
        r.append("SCENE_FPS_INVALID: %r" % a.get("scene_fps"))
    if a.get("phase") == "camera":
        if a.get("pose_key") not in POSE_KEYS:
            r.append("POSE_KEY_INVALID: %r" % a.get("pose_key"))
        ev = a.get("exposure_bias_ev")
        if ev is not None and not (isinstance(ev, (int, float)) and -15.0 <= ev <= 15.0):
            r.append("EXPOSURE_BIAS_INVALID: %r" % ev)
    if a.get("phase") in ("shot", "check"):
        p = str(a.get("path") or "")
        if not p.lower().endswith(".png") or not os.path.isabs(p):
            r.append("PATH_INVALID: %r (absolute .png)" % p)
    if a.get("phase") == "shot" and a.get("expect_view") not in ("preview", "show"):
        r.append("EXPECT_VIEW_INVALID: %r" % a.get("expect_view"))
    return r


def cli(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    here = _here()
    out = os.path.join(here, POSE_NAME)
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    sys.path.insert(0, here)
    dry = load_json(os.path.join(here, "klara_reveal_dry_S4.json"))
    args5 = load_json(os.path.join(here, "klara_reveal_s4v5_args.json"))
    recp = os.path.join(here, "klara_reveal_record_S4.json")
    pose = preview_pose(dry, args5, load_json(recp) if os.path.exists(recp) else None)
    pose["call_sequence"] = call_sequence(pose, datetime.datetime.now().strftime("S4V5PREVIEW-%Y%m%d-%H%M"))
    with open(out, "w", encoding="utf-8", newline="\n") as h:
        json.dump(pose, h, indent=1, sort_keys=True)
    ge, hc, fr, lv = pose["poses"]["glide_end"], pose["poses"]["her_cut"], pose["v5_frames"], pose["live"]
    print("S4V5 preview pose (offline, [meas] DRY %s + pure v5 code)" % pose["source"]["dry_run"])
    print("  glide_end  loc %s rot[r,p,y] %s focal %s mm filmback %s" % (ge["loc"], ge["rot_roll_pitch_yaw"],
                                                                           ge["focal_mm"], pose["sensor_mm"]))
    print("  her_cut    loc %s rot[r,p,y] %s focal %s mm (her frame %s)" % (hc["loc"], hc["rot_roll_pitch_yaw"],
                                                                               hc["focal_mm"], hc["her_frame"]))
    print("  v5 (strike_lights %s, preroll %s, strikes %d): glide %d -> %d, cut %d (rest %.2f s), env ramp %s"
          % (pose["strike_lights"], pose["preroll"], pose["n_strikes"], fr["glide_start"], fr["glide_end"], fr["cut"],
             fr["rest_before_cut_s"], fr["env_ramp"]))
    print("  live (PIE plays %s): pose valid %s; shoot dark %s / env %s / her %s" % (
        lv.get("run"), lv.get("valid"), (lv.get("frames") or {}).get("dark"), (lv.get("frames") or {}).get("env"),
        (lv.get("frames") or {}).get("her")))
    print("  refusals other than the offline gate inputs: %s" % pose["plan_refusals_other"])
    print("  ok=%s -> %s" % (pose["ok"], out))
    return 0 if pose["ok"] else 1


# =====================================================================================================================
# PIE (Unreal). Every unreal handle is a local; nothing is kept between calls except plain JSON on disk.
# =====================================================================================================================

def _ok(run, phase, extra=""):
    unreal.log("%s_OK|run=%s|phase=%s%s" % (MARK, run, phase, ("|" + extra) if extra else ""))


def _fail(run, phase, reason):
    unreal.log_error("%s_FAILED|run=%s|phase=%s|reason=%s" % (MARK, run, phase, reason))


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as h:
        json.dump(data, h, indent=1, sort_keys=True, default=str)
    os.replace(tmp, path)


def _root(world):
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    if len(roots) != 1:
        raise PreviewError("SHOW_ROOTS_%d" % len(roots))
    return roots[0]


def _segment(root, label):
    segs = [s for s in list(root.transport.segments) if s.type == unreal.InfinityCueType.SCENE
            and (str(s.label) == label or str(s.label).startswith(label + " "))]
    if len(segs) != 1:
        raise PreviewError("SEGMENTS_%d for %r" % (len(segs), label))
    s = segs[0]
    return {"label": str(s.label), "start": int(s.start_frame.value), "end": int(s.end_frame.value)}


def _preview_cameras(world):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CineCameraActor)
            if str(a.get_actor_label()) == CAMERA_LABEL]


def _actor_by_path(world, path):
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        if str(a.get_path_name()) == path:
            return a
    return None


def phase_jump(a, run, world):
    root = _root(world)
    seg = _segment(root, a["segment"])
    target = master_ticks(seg["start"], a["scene_frame"], a["scene_fps"])
    if not seg["start"] <= target < seg["end"]:
        raise PreviewError("FRAME_OUTSIDE_SEGMENT: %d not in [%d, %d)" % (target, seg["start"], seg["end"]))
    st_path = os.path.join(_here(), STATE_NAME)
    st = load_json(st_path) if os.path.exists(st_path) else {}
    if a.get("disable_performance_mode"):
        before = bool(root.transport.get_editor_property("performance_mode"))
        if st.get("run") != run or "performance_mode_before" not in st:
            st = dict(st if st.get("run") == run else {}, run=run, performance_mode_before=before)
            _write_json(st_path, st)                       # original first, then change (bench-originals rule)
        root.transport.set_editor_property("performance_mode", False)
        if root.transport.get_editor_property("performance_mode"):
            raise PreviewError("PERFORMANCE_MODE_STILL_ON")
    root.sequence_player.pause()
    res = root.transport.scrub_to_master_frame(unreal.FrameNumber(target))
    if res != unreal.InfinityTransportResult.SUCCEEDED:
        raise PreviewError("SCRUB_%s (UNSAFE_EXTERNAL_CLOCK = the performance interlock: set disable_performance_mode "
                           "true, cleanup restores it)" % (res,))
    now = int(root.transport.get_current_master_frame().value)
    if now != target:
        raise PreviewError("FRAME_READBACK: %d want %d" % (now, target))
    playing = bool(root.sequence_player.is_playing())
    if playing:
        raise PreviewError("STILL_PLAYING_AFTER_PAUSE")
    return "segment=%s|segment_start=%d|scene_frame=%d|master=%d|paused=1" % (seg["label"], seg["start"],
                                                                              a["scene_frame"], target)


def phase_camera(a, run, world):
    pose_all = load_json(os.path.join(_here(), a.get("pose_file") or POSE_NAME))
    if not (pose_all.get("live") or {}).get("valid"):
        raise PreviewError("POSE_NOT_VALID_LIVE: %s" % (pose_all.get("live") or {}).get("why"))
    pose = pose_all["poses"][a["pose_key"]]
    if _preview_cameras(world):
        raise PreviewError("CAMERA_EXISTS: run cleanup first")
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    if pc is None:
        raise PreviewError("NO_PLAYER_CONTROLLER")
    prev = pc.get_view_target()
    st_path = os.path.join(_here(), STATE_NAME)
    st = load_json(st_path) if os.path.exists(st_path) else {}
    st = dict(st if st.get("run") == run else {}, run=run, phase="camera_spawning",
              restore_view_target_path=str(prev.get_path_name()) if prev is not None else None,
              restore_view_target_label=str(prev.get_actor_label()) if prev is not None else None,
              world=str(world.get_path_name()), utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    _write_json(st_path, st)                               # originals on disk BEFORE anything changes
    rot = pose["rot_roll_pitch_yaw"]
    tf = unreal.Transform(location=unreal.Vector(*pose["loc"]),
                          rotation=unreal.Rotator(roll=rot[0], pitch=rot[1], yaw=rot[2]))
    cam = unreal.GameplayStatics.begin_deferred_actor_spawn_from_class(
        world, unreal.CineCameraActor, tf, unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None)
    cam = unreal.GameplayStatics.finish_spawning_actor(cam, tf)     # [prec st_pie_stills_driver.py:451-458]
    if cam is None or str(cam.get_world().get_path_name()) != str(world.get_path_name()):
        raise PreviewError("CAMERA_NOT_IN_PIE_WORLD")
    ed_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if ed_world is not None and str(cam.get_world().get_path_name()) == str(ed_world.get_path_name()):
        raise PreviewError("CAMERA_IN_EDITOR_WORLD")
    cam.set_actor_label(CAMERA_LABEL, False)
    comp = cam.get_cine_camera_component()
    fb = comp.get_editor_property("filmback")              # [prec klara_reveal.py APPLY glide camera]
    fb.set_editor_property("sensor_width", float(pose_all["sensor_mm"][0]))
    fb.set_editor_property("sensor_height", float(pose_all["sensor_mm"][1]))
    comp.set_editor_property("filmback", fb)
    comp.set_current_focal_length(float(pose["focal_mm"]))
    fs = comp.get_editor_property("focus_settings")
    fs.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    fs.set_editor_property("manual_focus_distance", float(pose["focus_cm"]))
    comp.set_editor_property("focus_settings", fs)
    ev = a.get("exposure_bias_ev")
    if ev is not None:
        pp = comp.get_editor_property("post_process_settings")
        pp.set_editor_property("override_auto_exposure_bias", True)
        pp.set_editor_property("auto_exposure_bias", float(ev))
        comp.set_editor_property("post_process_settings", pp)
        comp.set_editor_property("post_process_blend_weight", 1.0)
    pc.set_view_target_with_blend(cam, 0.0)
    # read back every value set (return values are not trusted: memory puss-python-api-gotchas)
    loc, r = cam.get_actor_location(), cam.get_actor_rotation()
    dl = max(abs(float(loc.x) - pose["loc"][0]), abs(float(loc.y) - pose["loc"][1]), abs(float(loc.z) - pose["loc"][2]))
    dr = max(abs(wrap(float(r.roll) - rot[0])), abs(wrap(float(r.pitch) - rot[1])), abs(wrap(float(r.yaw) - rot[2])))
    fb2 = comp.get_editor_property("filmback")
    pp2 = comp.get_editor_property("post_process_settings")
    rb = {"loc_err_cm": dl, "rot_err_deg": dr, "focal": float(comp.get_editor_property("current_focal_length")),
          "sensor": [float(fb2.get_editor_property("sensor_width")), float(fb2.get_editor_property("sensor_height"))],
          "focus": float(comp.get_editor_property("focus_settings").get_editor_property("manual_focus_distance")),
          "bias_override": bool(pp2.get_editor_property("override_auto_exposure_bias")),
          "bias": float(pp2.get_editor_property("auto_exposure_bias"))}
    vt = pc.get_view_target()
    rb["view_target"] = str(vt.get_path_name()) if vt is not None else None
    st.update(phase="camera_set", camera_path=str(cam.get_path_name()), readback=rb, exposure_bias_ev=ev,
              pose_key=a["pose_key"])
    _write_json(st_path, st)
    bad = []
    if dl > LOC_TOL_CM or dr > ROT_TOL_DEG:
        bad.append("POSE_READBACK loc %.3f cm rot %.3f deg" % (dl, dr))
    if abs(rb["focal"] - float(pose["focal_mm"])) > 1e-3:
        bad.append("FOCAL_READBACK %.4f" % rb["focal"])
    if max(abs(rb["sensor"][i] - float(pose_all["sensor_mm"][i])) for i in range(2)) > 1e-3:
        bad.append("FILMBACK_READBACK %s" % rb["sensor"])
    if ev is not None and (not rb["bias_override"] or abs(rb["bias"] - float(ev)) > 1e-3):
        bad.append("BIAS_READBACK %s %.3f" % (rb["bias_override"], rb["bias"]))
    if ev is None and rb["bias_override"]:
        bad.append("BIAS_OVERRIDE_ON_FOR_TRUE_EXPOSURE")
    if rb["view_target"] != str(cam.get_path_name()):
        bad.append("VIEW_TARGET_READBACK %s" % rb["view_target"])
    if bad:
        raise PreviewError("READBACK|" + " ; ".join(bad) + " (camera left for cleanup)")
    return "pose=%s|loc=%s|rot=%s|focal=%.2f|ev=%s|restore=%s" % (a["pose_key"], pose["loc"], rot, rb["focal"], ev,
                                                                 st["restore_view_target_label"])


def phase_shot(a, run, world):
    path = a["path"]
    if os.path.exists(path):
        raise PreviewError("OUTPUT_EXISTS: %s (stale file would fake the check)" % path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    root = _root(world)
    if root.sequence_player.is_playing():
        raise PreviewError("PLAYING (run jump first: the shot must be at a paused frame)")
    now = int(root.transport.get_current_master_frame().value)
    seg = _segment(root, a.get("segment") or "Scene 4")
    want = master_ticks(seg["start"], a["scene_frame"], a["scene_fps"]) if a.get("scene_frame") is not None else now
    if now != want:
        raise PreviewError("FRAME_MOVED: master %d, want %d" % (now, want))
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    vt = pc.get_view_target() if pc is not None else None
    vlabel = str(vt.get_actor_label()) if vt is not None else None
    if a["expect_view"] == "preview" and vlabel != CAMERA_LABEL:
        raise PreviewError("VIEW_TARGET_NOT_PREVIEW: %s" % vlabel)
    if a["expect_view"] == "show" and (vt is None or vlabel == CAMERA_LABEL or _preview_cameras(world)):
        raise PreviewError("VIEW_TARGET_NOT_SHOW: %s (cleanup the preview camera first)" % vlabel)
    unreal.SystemLibrary.execute_console_command(world, 'HighResShot %dx%d filename="%s"' % (
        RESOLUTION[0], RESOLUTION[1], path.replace("\\", "/")))
    return "issued=1|master=%d|view=%s|path=%s|next=check (a later call)" % (now, vlabel, path)


def phase_check(a, run, world):
    path = a["path"]
    if not os.path.isfile(path):
        raise PreviewError("NOT_WRITTEN: %s" % path)
    n = os.path.getsize(path)
    if n < SHOT_MIN_BYTES:
        raise PreviewError("TOO_SMALL: %d bytes" % n)
    with open(path, "rb") as h:
        sha = hashlib.sha256(h.read()).hexdigest()
    return "bytes=%d|sha256=%s|path=%s" % (n, sha, path)


def phase_cleanup(a, run, world):
    st_path = os.path.join(_here(), STATE_NAME)
    st = load_json(st_path) if os.path.exists(st_path) else {}
    bad = []
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    restored = None
    if st.get("restore_view_target_path"):
        prev = _actor_by_path(world, st["restore_view_target_path"])
        if prev is None:
            bad.append("RESTORE_TARGET_GONE %s" % st["restore_view_target_path"])
        elif pc is not None:
            pc.set_view_target_with_blend(prev, 0.0)
            vt = pc.get_view_target()
            restored = str(vt.get_path_name()) if vt is not None else None
            if restored != st["restore_view_target_path"]:
                bad.append("RESTORE_READBACK %s" % restored)
    for c in _preview_cameras(world):
        c.destroy_actor()
    left = len(_preview_cameras(world))
    if left:
        bad.append("CAMERAS_LEFT %d" % left)
    if "performance_mode_before" in st and st.get("run") == run:
        root = _root(world)
        root.transport.set_editor_property("performance_mode", bool(st["performance_mode_before"]))
        if bool(root.transport.get_editor_property("performance_mode")) != bool(st["performance_mode_before"]):
            bad.append("PERFORMANCE_MODE_RESTORE")
    st.update(phase="cleaned" if not bad else "cleanup_failed", cleanup_errors=bad, restored_view_target=restored)
    _write_json(st_path, st)
    if bad:
        raise PreviewError("CLEANUP|" + " ; ".join(bad))
    return "cameras_left=0|view_target=%s" % restored


def main():
    a = globals().get("S4V5PREVIEW_ARGS") or load_json(os.path.join(_here(), ARGS_NAME))
    run, phase = str(a.get("run") or "NO_RUN"), str(a.get("phase"))
    bad = validate_args(a)
    if bad:
        _fail(run, phase, "ARGS|" + " || ".join(bad))
        return
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_game_world()
    if world is None:
        _fail(run, phase, "NO_PIE (this tool is PIE-only; it never starts or ends PIE)")
        return
    before = _census()
    try:
        extra = {"jump": phase_jump, "camera": phase_camera, "shot": phase_shot, "check": phase_check,
                 "cleanup": phase_cleanup}[phase](a, run, world)
    except PreviewError as exc:
        _fail(run, phase, str(exc))
        return
    after = _census()
    if after != before:
        _fail(run, phase, "CENSUS_CHANGED|before=%s|after=%s" % (json.dumps(before), json.dumps(after)))
        return
    _ok(run, phase, extra)


if unreal is not None:
    try:
        main()
    except Exception as exc:                               # never OK on an exception
        unreal.log_error("%s_FAILED|run=?|phase=?|reason=EXC|%r" % (MARK, exc))
elif __name__ == "__main__":
    sys.exit(cli())
