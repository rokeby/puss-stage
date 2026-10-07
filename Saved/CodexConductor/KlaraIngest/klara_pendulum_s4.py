"""KLARA PENDULUM S4 (v5, 7 Oct): turn BP_Pendulum's OWN Blueprint Tick swing OFF in the SHOW only, so only her LS keys
move it (Gary 7 Oct, conductor session), gated behind a READ-ONLY PIE probe.
Offline-written, NEVER RUN IN UNREAL by its author. Harness: test_klara_reveal_v5_offline.py (pure parts).

Evidence (S4_ENTRY_INVESTIGATION_2026-10-07.md section C): BP_Pendulum has an ENABLED ReceiveTick that calls
K2_SetRelativeRotation on its root PivotRoot every frame [bytes]; her LS keys the anchor's pitch (71 cubic keys, her
frames 191..4683) with yaw default 130 [bytes]. Which writer wins per frame is UNVERIFIED -> PROBE first.

MECHANISM (least invasive persistent route without editing her BP asset), compared:
  (a) her BP asset (bCanEverTick / graph): excluded by Gary ("her asset untouched").
  (b) the actor INSTANCE in L_KK_children (PrimaryActorTick.bStartWithTickEnabled = false, saved through
      klara_reveal's her-map guard): PrimaryActorTick is UPROPERTY(EditDefaultsOnly) [decl UE_5.8 Actor.h:317-318],
      bStartWithTickEnabled EditDefaultsOnly and bCanEverTick "only settable in defaults" [decl EngineBaseTypes.h:211-217];
      PropertyAccessUtil refuses instance edits of such properties (CannotEditInstance) [decl PropertyAccessUtil.h:40-41;
      that Python's set_editor_property goes through it is inf]. It also writes Klara's level (memory
      klara-streamed-levels-traps; a klara_copy.ps1 re-run erases it). Rejected.
  (c) CHOSEN: a Show-side Sequencer EVENT in OUR Scene sequence LS_DevScene_04: a possessable binding on the pendulum
      actor + an Event track with ONE Repeater section over [0, Scene end) calling AActor "Set Actor Tick Enabled"
      (false) - SequencerTools.create_quick_binding + create_event [decl SequencerScriptingEditor/SequencerTools.h:
      248-277], MovieSceneEventTrackExtensions.add_event_repeater_section [decl MovieSceneEventTrackExtensions.h:33],
      the section's Event UPROPERTY [decl MovieSceneEventRepeaterSection.h:30-31]. Our asset only; her BP and level
      untouched; reversible (REVERT removes the binding; the director-BP endpoint function stays inside LS_DevScene_04
      until a backup restore [inf]). A Repeater fires every evaluated frame, so transport jumps into S4 still disable it
      [inf]. Runtime: the tick stays off for the rest of the PIE session after S4 (nothing re-enables it) [inf].
  (d) C++: a Show/Scene property 'TickSuppressedActors' applied by the transport on Scene activation - needs a build;
      spec in the report, only if (c) fails its live read-back or the re-probe.

Modes (klara_pendulum_s4_run.py <- klara_pendulum_s4_args.json; one mode per run):
  PROBE  PIE only, READ ONLY (no save, no transport command, never ends PIE): arms a post-tick callback that, when the
         Master's Scene-4 time crosses each probe time (default 10 s pre-cut, 24 s in the slot past her frame 191),
         logs BP_Pendulum_C_0's location / rotation / IsActorTickEnabled on 3 CONSECUTIVE ticks with predictions
         (LS-only from the copy's keys; level placement), writes klara_pendulum_probe_S4_<run>.json, classifies
         (classify_pendulum) and logs KLARAPENDULUM_PROBE_OK|run=..|verdict=..
  DRY    editor, read only -> klara_pendulum_dry_S4.json; KLARAPENDULUM_DRY_OK|run=..|apply_ready=..
  APPLY  needs a probe file whose verdict recommends it and whose binding resolves -> backup -> record -> binding +
         event repeater -> read back -> census -> save LS_DevScene_04 -> KLARAPENDULUM_APPLY_OK|run=..; then re-PROBE
         (tick_enabled must read False in S4, rotation = her keys).
  REVERT remove our binding -> read back -> save -> KLARAPENDULUM_REVERT_OK|run=..
Never: Save All, reload a level, open/scrub Sequencer, save her levels, end PIE; no unreal objects in module globals.
"""
import datetime
import hashlib
import json
import math
import os
import shutil
import time

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None

TOOL = "klara_pendulum_s4"
CONFIRM_WORD = "KLARAPENDULUM"
MODES = ("PROBE", "DRY", "APPLY", "REVERT")
ARGS_NAME = "klara_pendulum_s4_args.json"
PREFIX = "Klara Pendulum - "
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure (harness-tested)
# =====================================================================================================================

def wrap(deg):
    d = math.fmod(float(deg), 360.0)
    if d <= -180.0:
        d += 360.0
    elif d > 180.0:
        d -= 360.0
    return d


def curve_value(curve, frame):
    """Unweighted Hermite (UE cubic with stored tangents in value/tick; linear; constant), constant extrapolation;
    curve = {"tpf", "keys": [{"tick","value","interp","arrive","leave"}], "default"} (klara_reveal._ch_curve shape)."""
    ks = sorted(curve.get("keys") or [], key=lambda k: k["tick"])
    if not ks:
        return curve.get("default")
    t = float(frame) * float(curve["tpf"])
    if t <= ks[0]["tick"]:
        return float(ks[0]["value"])
    if t >= ks[-1]["tick"]:
        return float(ks[-1]["value"])
    for a, b in zip(ks, ks[1:]):
        if a["tick"] <= t <= b["tick"]:
            if a["interp"] == "constant":
                return float(a["value"]) if t < b["tick"] else float(b["value"])
            dt = float(b["tick"] - a["tick"])
            s = (t - a["tick"]) / dt
            if a["interp"] == "linear":
                return float(a["value"]) + (float(b["value"]) - float(a["value"])) * s
            s2, s3 = s * s, s * s * s
            return (2 * s3 - 3 * s2 + 1) * a["value"] + (s3 - 2 * s2 + s) * dt * a["leave"] + \
                (-2 * s3 + 3 * s2) * b["value"] + (s3 - s2) * dt * b["arrive"]
    return None


def her_frame_at(scene_frame, mapping):
    """mapping = [{"range": [s0, s1) Scene frames, "her_start": h, "ratio": her_fps/scene_fps, "what"}] (pre-roll, slot).
    -> (her frame, what) or (None, None) when no section of hers evaluates there."""
    for m in mapping:
        if int(m["range"][0]) <= scene_frame < int(m["range"][1]):
            return float(m["her_start"]) + (float(scene_frame) - float(m["range"][0])) * float(m["ratio"]), m["what"]
    return None, None


def ls_prediction(chans, her_frame):
    """chans = {"Location.X".., "Rotation.X/Y/Z" (roll, pitch, yaw)} curves -> {"loc", "rot": [roll, pitch, yaw]}."""
    v = lambda n: curve_value(chans[n], her_frame)
    return {"loc": [v("Location.X"), v("Location.Y"), v("Location.Z")],
            "rot": [v("Rotation.X"), v("Rotation.Y"), v("Rotation.Z")]}


def classify_pendulum(samples, tol_cm=5.0, tol_deg=1.0, tick_amp_deg=25.0):
    """samples = [{"window", "loc", "rot": [roll, pitch, yaw], "tick_enabled", "pred_ls": {"loc","rot"}|None,
    "pred_level": {"loc"}}]. Per sample: 'ls' (rotation = her keys), 'tick' (yaw 0 + roll 0 + |pitch| <= 25: the BP
    swing with yaw dropped [inf: MakeRotator pins not decoded]), else 'other'. Location: 'ls' / 'level' / 'other'.
    -> {"windows": {w: {"who", "where", "tick_enabled", "binding_resolves"}}, "verdict", "apply_recommended",
    "binding_resolves", "why"}."""
    win = {}
    for s in samples:
        w = win.setdefault(s["window"], {"who": [], "where": [], "tick_enabled": [], "has_ls": False})
        ls, lv = s.get("pred_ls"), s.get("pred_level")
        r = s["rot"]
        rot_ls = bool(ls) and abs(wrap(r[2] - ls["rot"][2])) <= tol_deg and abs(wrap(r[1] - ls["rot"][1])) <= tol_deg \
            and abs(wrap(r[0] - ls["rot"][0])) <= tol_deg
        tick = abs(wrap(r[2])) <= tol_deg and abs(wrap(r[0])) <= tol_deg and abs(wrap(r[1])) <= tick_amp_deg + tol_deg
        w["who"].append("ls" if rot_ls else ("tick" if tick else "other"))
        d = lambda p: math.dist(s["loc"], p["loc"]) if p else float("inf")
        w["where"].append("ls" if d(ls) <= tol_cm else ("level" if d(lv) <= tol_cm else "other"))
        w["tick_enabled"].append(bool(s.get("tick_enabled")))
        w["has_ls"] = w["has_ls"] or bool(ls)
    out = {"windows": {}}
    for k, w in sorted(win.items()):
        who = sorted(set(w["who"]))
        out["windows"][k] = {"who": who[0] if len(who) == 1 else "alternating:" + "+".join(who),
                             "where": sorted(set(w["where"])), "tick_enabled": any(w["tick_enabled"]),
                             "binding_resolves": (all(x == "ls" for x in w["where"]) if w["has_ls"] else None),
                             "n": len(w["who"])}
    rows = list(out["windows"].values())
    tick_on = any(r["tick_enabled"] for r in rows)
    tick_seen = any("tick" in r["who"] for r in rows)
    res = [r["binding_resolves"] for r in rows if r["binding_resolves"] is not None]
    out["binding_resolves"] = (all(res) if res else None)
    out["tick_enabled_any"] = tick_on
    ls_rows = [r for r in rows if r["binding_resolves"] is not None]
    if not rows:
        out.update(verdict="no_samples", apply_recommended=False, why="no samples")
    elif out["binding_resolves"] is False:
        out.update(verdict="binding_does_not_resolve", apply_recommended=False,
                   why="her LS never placed the anchor where its keys say: disabling the tick would freeze it at the "
                       "level pose -> fix the binding first")
    elif out["binding_resolves"] is None:
        out.update(verdict="no_window_inside_her_sections", apply_recommended=False,
                   why="no sample fell where her LS evaluates (probe a time inside the slot past her frame 191)")
    elif tick_on and tick_seen:
        out.update(verdict="tick_wins" if all(r["who"] == "tick" for r in ls_rows) else "tick_fights_ls",
                   apply_recommended=True, why="BP tick enabled and its signature seen")
    elif tick_on:
        out.update(verdict="ls_wins_while_tick_enabled", apply_recommended=True,
                   why="tick enabled but her keys won every sampled frame (order not guaranteed [inf])")
    else:
        out.update(verdict="tick_disabled", apply_recommended=False, why="IsActorTickEnabled False in every sample")
    return out


def validate_args(a):
    r = []
    if str(a.get("mode") or "").upper() not in MODES:
        r.append("MODE_INVALID: %r" % a.get("mode"))
    for k in ("scene_sequence", "copy", "her_level", "actor_name", "probe_times_s", "reveal_record"):
        if a.get(k) in (None, "", []):
            r.append("MISSING_%s" % k.upper())
    if "Master" in str(a.get("scene_sequence", "")):
        r.append("TARGET_IS_THE_MASTER")
    return r


def load_json(path):
    with open(path, "r", encoding="utf-8") as h:
        return json.load(h)


def write_json(path, data, exclusive=False):
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        h = os.fdopen(fd, "w", encoding="utf-8")
    else:
        h = open(path + ".tmp", "w", encoding="utf-8")
    with h:
        json.dump(data, h, indent=1, sort_keys=True, default=str)
        h.flush()
        os.fsync(h.fileno())
    if not exclusive:
        os.replace(path + ".tmp", path)


def latest_probe(here):
    rows = sorted(f for f in os.listdir(here) if f.startswith("klara_pendulum_probe_S4_") and f.endswith(".json"))
    return os.path.join(here, rows[-1]) if rows else None


# =====================================================================================================================
# Live (Unreal). Every unreal handle is a local (the probe's tick callback keeps only plain Python data).
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", "KlaraIngest")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _file(path, ext):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ext


def _stop(run, reason):
    unreal.log_error("KLARAPENDULUM_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _enum_name(v):
    return str(getattr(v, "name", v)).split(".")[-1]


_INTERP = {"RCIM_CUBIC": "cubic", "RCIM_LINEAR": "linear", "RCIM_CONSTANT": "constant"}


def _pendulum_chans(copy, names):
    """Plain-data curves of the copy's pendulum binding (Location/Rotation), keys in TICKS."""
    tpf = _rate(copy.get_tick_resolution()) / _rate(copy.get_display_rate())
    hit = [b for b in copy.get_bindings() if str(b.get_display_name()) in names]
    if len(hit) != 1:
        raise PlanError("PENDULUM_BINDING_COUNT: %d for %s" % (len(hit), names))
    secs = [s for t in hit[0].get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack) for s in t.get_sections()]
    if len(secs) != 1:
        raise PlanError("PENDULUM_TRANSFORM_SECTIONS: %d" % len(secs))
    out = {}
    for c in secs[0].get_all_channels():
        nm = str(c.channel_name) if hasattr(c, "channel_name") else str(c.get_name())
        base = nm.rsplit("_", 1)[0] if nm.rsplit("_", 1)[-1].isdigit() else nm      # memory: Location.X_183
        keys = []
        for k in c.get_keys():
            keys.append({"tick": int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
                         "value": float(k.get_value()), "interp": _INTERP.get(_enum_name(k.get_interpolation_mode()),
                                                                               "cubic"),
                         "arrive": float(k.get_arrive_tangent()), "leave": float(k.get_leave_tangent())})
        out[base] = {"tpf": tpf, "keys": keys, "default": float(c.get_default()) if c.has_default() else None}
    return out


def _mapping(args):
    """Which of her frames plays at a Scene frame: the pre-roll (if applied) and the main slot, from the records."""
    here = _here()
    rec = load_json(os.path.join(here, args["reveal_record"]))
    if not rec.get("applied"):
        raise PlanError("REVEAL_NOT_APPLIED")
    pl = rec["plan"]
    ratio = 30.0 / 25.0                             # her 30 fps / Scene 25 fps [meas klara_reveal_dry_S4.json]
    m = [{"range": pl["slot"]["range"], "her_start": pl["slot"]["her_frame_at_cut"], "ratio": ratio, "what": "slot"}]
    pp = os.path.join(here, "klara_preroll_record_S4.json")
    if os.path.exists(pp) and load_json(pp).get("applied"):
        pr = load_json(pp)
        m.append({"range": pr["section"]["range"], "her_start": pr["plan"]["her_frame_start"], "ratio": ratio,
                  "what": "preroll"})
    lt = pl["level_transform_after"]["loc"]
    return m, lt


def run_probe(args, run):
    """PIE, READ ONLY. Arms a post-tick callback; returns at once (the callback logs the result later)."""
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is None:
        _stop(run, "PROBE_NEEDS_PIE (start S4 in PIE first; this never starts or ends PIE)")
    copy = unreal.load_asset(args["copy"])
    chans = _pendulum_chans(copy, set(args.get("binding_names") or ["Pendulum", "Pendulum_Anchor"]))
    copy = None
    mapping, lt = _mapping(args)
    rel = [float(x) for x in args["level_relative_loc"]]
    pred_level = {"loc": [rel[i] + float(lt[i]) for i in range(3)]}
    times = sorted(float(t) for t in args["probe_times_s"])
    st = {"handle": None, "samples": [], "pending": list(times), "burst": 0, "window": None, "t0": time.time(),
          "out": os.path.join(_here(), "klara_pendulum_probe_S4_%s.json" % run), "done": False}

    def finish(status):
        if st["done"]:
            return
        st["done"] = True
        try:
            unreal.unregister_slate_post_tick_callback(st["handle"])
        except Exception:  # noqa: BLE001
            pass
        verdict = classify_pendulum(st["samples"])
        write_json(st["out"], {"tool": TOOL, "run": run, "status": status, "samples": st["samples"],
                               "verdict": verdict, "mapping": mapping, "pred_level": pred_level, "args": args})
        unreal.log("KLARAPENDULUM_PROBE_%s|run=%s|verdict=%s|apply_recommended=%s|binding_resolves=%s|file=%s"
                   % ("OK" if status == "complete" else "ABORTED", run, verdict.get("verdict"),
                      verdict.get("apply_recommended"), verdict.get("binding_resolves"), st["out"]))

    def scene_frame(world):
        # Conductor 7 Oct: LevelSequenceActor has no get_sequence_player() in UE 5.8 Python [meas: AttributeError,
        # KLARAPENDULUM-20261007-133444]. Use the Show Root transport (Master ticks, 24000/s) and the Scene 4 segment
        # start, as scene_stills.py's PIE adapter does; return Scene-4 frames at 25 fps.
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
        if len(roots) != 1:
            return None, "SHOW_ROOTS_%d" % len(roots)
        tr = roots[0].transport
        segs = [g for g in list(tr.segments) if g.type == unreal.InfinityCueType.SCENE
                and (str(g.label) == "Scene 4" or str(g.label).startswith("Scene 4 "))]
        if len(segs) != 1:
            return None, "S4_SEGMENTS_%d" % len(segs)
        mf = float(tr.get_current_master_frame().value)
        return (mf - float(segs[0].start_frame.value)) / 24000.0 * 25.0, None

    def tick(_dt):
        try:
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if world is None:
                return finish("pie_ended")
            if time.time() - st["t0"] > float(args.get("timeout_s", 600.0)):
                return finish("timeout")
            sf, err = scene_frame(world)
            if sf is None:
                unreal.log_warning("KLARAPENDULUM_PROBE_NO_TIME|run=%s|%s" % (run, err))
                return finish("no_time:" + err)
            if st["burst"] == 0:
                if not st["pending"] or sf / 25.0 < st["pending"][0]:
                    return None
                st["window"] = "t%.0fs" % st["pending"].pop(0)
                st["burst"] = 3
            hits = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                    if args["actor_name"] in str(a.get_name())]
            if len(hits) != 1:
                return finish("actor_count_%d" % len(hits))
            a = hits[0]
            loc, rot = a.get_actor_location(), a.get_actor_rotation()
            hf, what = her_frame_at(int(math.floor(sf)), mapping)
            s = {"window": st["window"], "scene_frame": sf, "her_frame": hf, "her_section": what,
                 "loc": [float(loc.x), float(loc.y), float(loc.z)],
                 "rot": [float(rot.roll), float(rot.pitch), float(rot.yaw)],
                 "tick_enabled": bool(a.is_actor_tick_enabled()),
                 "pred_ls": ls_prediction(chans, hf) if hf is not None else None, "pred_level": pred_level}
            a = None
            hits = None
            st["samples"].append(s)
            unreal.log("KLARAPENDULUM_PROBE_SAMPLE|run=%s|%s" % (run, json.dumps(s)))
            st["burst"] -= 1
            if st["burst"] == 0 and not st["pending"]:
                finish("complete")
        except Exception as exc:  # noqa: BLE001 - a probe never raises into Slate; it stops itself
            unreal.log_error("KLARAPENDULUM_PROBE_ERROR|run=%s|%s: %s" % (run, type(exc).__name__, exc))
            finish("error")
        return None

    st["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log("KLARAPENDULUM_PROBE_ARMED|run=%s|times_s=%s|mapping=%s|file=%s|read-only: no save, no transport command"
               % (run, times, mapping, st["out"]))


def _pendulum_actor(world, args):
    for lv in unreal.EditorLevelUtils.get_levels(world):
        if lv.get_outer() is not None and _path(lv.get_outer()) == args["her_level"]:
            acts = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
                    if a.get_level() == lv and str(a.get_name()) == args["actor_name"]]
            if len(acts) != 1:
                raise PlanError("PENDULUM_ACTOR_COUNT: %d" % len(acts))
            return acts[0]
    raise PlanError("HER_LEVEL_NOT_LOADED: %s" % args["her_level"])


def _ours(seq):
    return [b for b in seq.get_bindings() if str(b.get_display_name()).startswith(PREFIX)]


def _api_table():
    rows = []

    def probe(api, tier, fn):
        try:
            res = fn()
            rows.append({"api": api, "tier": tier, "ok": bool(res), "result": repr(res)[:160]})
        except Exception as exc:  # noqa: BLE001
            rows.append({"api": api, "tier": tier, "ok": False, "result": "%s: %s" % (type(exc).__name__, exc)})

    u = unreal
    probe("SequencerTools.create_quick_binding / create_event / is_event_endpoint_valid",
          "decl SequencerTools.h:248-277", lambda: [hasattr(u.SequencerTools, n) for n in
                                                   ("create_quick_binding", "create_event", "is_event_endpoint_valid")])
    probe("MovieSceneEventTrackExtensions.add_event_repeater_section", "decl MovieSceneEventTrackExtensions.h:33",
          lambda: hasattr(u.MovieSceneEventTrackExtensions, "add_event_repeater_section"))
    probe("MovieSceneEventTrack / MovieSceneEventRepeaterSection", "decl MovieSceneEventRepeaterSection.h:30-31",
          lambda: [hasattr(u, "MovieSceneEventTrack"), hasattr(u, "MovieSceneEventRepeaterSection")])
    probe("Actor.is_actor_tick_enabled / set_actor_tick_enabled", "inf (AActor UFUNCTIONs)",
          lambda: [hasattr(u.Actor, "is_actor_tick_enabled"), hasattr(u.Actor, "set_actor_tick_enabled")])
    probe("register_slate_post_tick_callback (PROBE)", "inf", lambda: hasattr(u, "register_slate_post_tick_callback"))
    return rows


def _probe_gate(args):
    pf = args.get("probe_file") or latest_probe(_here())
    if not pf or not os.path.exists(pf if os.path.isabs(pf) else os.path.join(_here(), pf)):
        return None, ["NO_PROBE: run PROBE in PIE first (Gary: gate the tick change behind the read-only probe)"]
    pf = pf if os.path.isabs(pf) else os.path.join(_here(), pf)
    v = load_json(pf).get("verdict") or {}
    r = []
    if load_json(pf).get("status") != "complete":
        r.append("PROBE_INCOMPLETE: %s" % load_json(pf).get("status"))
    if not v.get("apply_recommended"):
        r.append("PROBE_SAYS_NOT_NEEDED_OR_UNSAFE: %s (%s)" % (v.get("verdict"), v.get("why")))
    return pf, r


def run_dry(args, run, world):
    seq = unreal.load_asset(args["scene_sequence"])
    refusals = []
    try:
        actor = _pendulum_actor(world, args)
        facts = {"actor": str(actor.get_name()), "label": str(actor.get_actor_label()),
                 "tick_enabled_editor": bool(actor.is_actor_tick_enabled())}
        actor = None
    except PlanError as exc:
        facts = {}
        refusals.append(str(exc))
    if _ours(seq):
        refusals.append("ALREADY_BOUND: %s" % [str(b.get_display_name()) for b in _ours(seq)])
    pf, pr = _probe_gate(args)
    refusals += pr
    api = _api_table()
    refusals += ["API_MISSING: %s" % r["api"] for r in api if not r["ok"] and "PROBE" not in r["api"]]
    rep = {"tool": TOOL, "run": run, "args": args, "facts": facts, "probe_file": pf, "api_table": api,
           "refusals": refusals, "apply_ready": not refusals, "scene_end": int(seq.get_playback_end())}
    out = os.path.join(_here(), "klara_pendulum_dry_S4.json")
    write_json(out, rep)
    for r in api:
        unreal.log("KLARAPENDULUM_API|run=%s|ok=%d|%s|%s|%s" % (run, int(r["ok"]), r["api"], r["tier"], r["result"]))
    for r in refusals:
        unreal.log_warning("KLARAPENDULUM_REFUSAL|run=%s|%s" % (run, r))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("KLARAPENDULUM_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|report=%s"
               % (run, int(not refusals), len(refusals), out))


def run_apply(args, run, world):
    if not str(args.get("decided_by") or "").strip():
        _stop(run, "NOT_DECIDED")
    if args.get("confirm") != "APPLY %s" % CONFIRM_WORD:
        _stop(run, "CONFIRM_MISMATCH")
    pf, pr = _probe_gate(args)
    if pr:
        _stop(run, "PROBE_GATE|" + " || ".join(pr))
    seq = unreal.load_asset(args["scene_sequence"])
    if _ours(seq):
        _stop(run, "ALREADY_BOUND")
    rpath = os.path.join(_here(), "klara_pendulum_record_S4.json")
    folder = os.path.join(_project(), "Backups", "PreKlaraPendulum-S4-%s" % run)
    os.makedirs(folder, exist_ok=False)
    src = _file(args["scene_sequence"], ".uasset")
    dst = os.path.join(folder, os.path.basename(src))
    shutil.copy2(src, dst)
    if hashlib.sha256(open(src, "rb").read()).hexdigest() != hashlib.sha256(open(dst, "rb").read()).hexdigest():
        _stop(run, "BACKUP_HASH")
    end = int(seq.get_playback_end())
    rec = {"tool": TOOL, "run": run, "applied": False, "backup": folder, "probe_file": pf, "args": args,
           "decided_by": args.get("decided_by"), "range": [0, end],
           "written": datetime.datetime.now().isoformat(timespec="seconds")}
    write_json(rpath, rec, exclusive=True)
    actor = _pendulum_actor(world, args)
    gs = unreal.GuidLibrary.conv_guid_to_string
    before = {gs(b.get_id()) for b in seq.get_bindings()}
    b = seq.add_possessable(actor)
    if gs(b.get_id()) in before:
        _stop(run, "PENDULUM_ALREADY_BOUND_BY_SOMEONE|%s|NOTHING SAVED; Don't-Save restart" % b.get_display_name())
    b.set_display_name(PREFIX + "Tick Off: " + str(actor.get_actor_label()))
    trk = b.add_track(unreal.MovieSceneEventTrack)
    trk.set_display_name(PREFIX + "Tick Off")
    sec = unreal.MovieSceneEventTrackExtensions.add_event_repeater_section(trk)
    sec.set_range(0, end)
    ep = unreal.SequencerTools.create_quick_binding(seq, actor, args.get("function", "Set Actor Tick Enabled"), False)
    if not unreal.SequencerTools.is_event_endpoint_valid(ep):
        _stop(run, "ENDPOINT_INVALID|NOTHING SAVED; Don't-Save restart")
    ev = unreal.SequencerTools.create_event(seq, sec, ep, [str(args.get("payload", "False"))])
    sec.set_editor_property("event", ev)
    actor = None
    got = [b2 for b2 in _ours(seq)]
    tr = [t for t in got[0].get_tracks()] if len(got) == 1 else []
    secs = [s for t in tr for s in t.get_sections()]
    if len(got) != 1 or len(tr) != 1 or len(secs) != 1 or \
            [int(secs[0].get_start_frame()), int(secs[0].get_end_frame())] != [0, end] or \
            secs[0].get_class().get_name() != "MovieSceneEventRepeaterSection":
        _stop(run, "EVENT_READBACK|bindings %d tracks %d sections %d|NOTHING SAVED; Don't-Save restart"
              % (len(got), len(tr), len(secs)))
    c = _census()
    if c["content"] != [args["scene_sequence"]] or c["maps"]:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s)" % (json.dumps(c), folder))
    if not unreal.EditorAssetLibrary.save_asset(args["scene_sequence"], only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    rec.update(applied=True, binding=str(got[0].get_display_name()), binding_guid=gs(got[0].get_id()))
    write_json(rpath, rec)
    unreal.log("KLARAPENDULUM_APPLY_OK|run=%s|binding=%s|range=[0,%d]|backup=%s|next=rebuild_managed_master + "
               "SavedMasterMatchesShow, then PROBE again in PIE (tick_enabled must read False in S4)"
               % (run, rec["binding"], end, folder))


def run_revert(args, run, world):
    rpath = os.path.join(_here(), "klara_pendulum_record_S4.json")
    rec = load_json(rpath)
    if not rec.get("applied"):
        _stop(run, "NO_APPLIED_RECORD")
    seq = unreal.load_asset(args["scene_sequence"])
    gs = unreal.GuidLibrary.conv_guid_to_string
    ours = _ours(seq)
    if [gs(b.get_id()) for b in ours] != [rec["binding_guid"]]:
        _stop(run, "STATE_DRIFTED|%s|nothing changed" % [str(b.get_display_name()) for b in ours])
    folder = os.path.join(_project(), "Backups", "PreKlaraPendulumRevert-S4-%s" % run)
    os.makedirs(folder, exist_ok=False)
    shutil.copy2(_file(args["scene_sequence"], ".uasset"), folder)
    ours[0].remove()                                                      # prec klara_hookin.py:1282
    if _ours(seq):
        _stop(run, "REMOVE_READBACK|NOTHING SAVED; Don't-Save restart")
    c = _census()
    if c["content"] != [args["scene_sequence"]] or c["maps"]:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(c))
    if not unreal.EditorAssetLibrary.save_asset(args["scene_sequence"], only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE")
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("KLARAPENDULUM_REVERT_OK|run=%s|removed=%s|note=the director-BP endpoint stays in %s until a backup "
               "restore (%s)" % (run, rec["binding"], args["scene_sequence"], rec["backup"]))


def main():
    args = globals().get("KLARAPENDULUM_ARGS")
    if args is None:
        args = load_json(os.path.join(_here(), ARGS_NAME))
    run = str(args.get("run_id") or datetime.datetime.now().strftime("KLARAPENDULUM-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    pie = ed.get_game_world() is not None
    try:
        if mode == "PROBE":
            return run_probe(args, run)
        if pie:
            _stop(run, "PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
        world = ed.get_editor_world()
        if str(world.get_outermost().get_name()) != EXPECTED_WORLD:
            _stop(run, "WRONG_WORLD")
        if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
            _stop(run, "SEQUENCER_OPEN (close it; opening/scrubbing dirties the map)")
        if _census() != {"content": [], "maps": []}:
            _stop(run, "DIRTY_CENSUS|%s" % json.dumps(_census()))
        {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[mode](args, run, world)
    except PlanError as exc:
        _stop(run, "PLAN|" + str(exc))


if unreal is not None:
    main()
