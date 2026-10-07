"""S4 hangar HOLD (7 Oct, offline-written, NOT RUN). Keeps the S4 hangar LANDED for the part of Scene 4 that its rise
no longer covers. S4 was relengthed to 4890 frames (eca8a5d), but LS_DevScene_04's 'Hangar Fold' sub-section still
plays LS_S4_HangarRise over [0, 775) only.

MEASURED by the conductor (own PIE, probe_s4_sky_pie, 7 Oct):
  - S4 frame 600: walls landed, root not at REST;
  - frames 978 and 3912: walls NOT landed and root at REST (pitch -90), so her L_KK_children sky shows.
  - KEEP_STATE on the Fold section does not hold the landed pose past the section's end.

WHY NOT JUST EXTEND THE FOLD SUB-SECTION TO [0, 4890]:
  - [decl] FMovieSceneSectionParameters has no hold or clamp past the inner playback end. Its only option there is
    bCanLoop (UE_5.8 MovieScene/Public/Evaluation/MovieSceneSectionParameters.h:78-92).
  - [decl] The rise's own sections are bounded to [0, end] (Saved/CodexStructure/hangar_build.py:479-480, 492-493,
    519-520).
  - [inf] So past rise frame 775 no inner section exists and nothing evaluates; looping would replay the rise.
    The private evaluator .cpp is not installed, so this cannot be proven.

MECHANISM: in LS_DevScene_04 ONLY, give each actor that the rise moves (each MovieScene3DTransformTrack binding in
LS_S4_HangarRise) one ABSOLUTE 3D-transform section over [fold_end, scene_end).
  - Its 9 channel DEFAULTS are the rise's landed values: the value after the channel's LAST key (constant
    extrapolation [inf]), or the channel default if the channel has no keys.
  - Refused unless the fold maps the rise 1:1 from Scene frame 0 and every last key lies inside the fold.
  - The rise, the Show, the Master and the level are never touched.
  - The sections do not overlap the fold in time, so the two never blend.
  - The reveal's ADDITIVE 'Lattice Hold' on the Lattice Fly ([0, 4890]) still adds on top, as it does during the rise.

Modes (args file s4_hangar_hold_args.json, runner s4_hangar_hold_run.py):
  SURVEY: read-only. For S1..S6, each Scene's playback end vs its rise sub-section.
  DRY:    SURVEY plus the S4 plan (targets and values).
  APPLY:  confirm "APPLY S4HOLD" and decided_by. The record is written first (exclusive), then the backup of
          LS_DevScene_04, then the writes, an exact read-back, a save of ONLY LS_DevScene_04, and a second read-back.
  REVERT: confirm "REVERT S4HOLD". Removes exactly the recorded tracks, and the bindings this tool created.
Markers: S4HOLD_<MODE>_OK|run=<run>|... ; S4HOLD_STOPPED|run=<run>|reason=...
"""
import datetime
import hashlib
import json
import os
import re
import shutil

try:
    import unreal
except ImportError:  # offline harness
    unreal = None

TOOL = "s4_hangar_hold"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_%02d"
RISE = "/Game/InfinityStage/RigAtmos/LS_S%d_HangarRise"
TRACK_NAME = "S4 Hangar Hold"
BIND_PREFIX = "S4 Hangar Hold: "
CHANNELS = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z",
            "Scale.X", "Scale.Y", "Scale.Z")
RECORD = "s4_hangar_hold_record.json"


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure (offline-testable)
# =====================================================================================================================

def channel_base(name):
    """'Location.Y_183' -> 'Location.Y' (memory ue58-sequencer-read-traps)."""
    return re.sub(r"_\d+$", "", str(name))


def landed_value(keys, default):
    """keys [[tick, value]...] -> the value held after the last key (constant post-extrapolation [inf]); unkeyed ->
    default. Neither -> PlanError (the channel's value would be the actor's, unknown here)."""
    if keys:
        return float(sorted(keys, key=lambda k: k[0])[-1][1])
    if default is None:
        raise PlanError("CHANNEL_UNKEYED_NO_DEFAULT")
    return float(default)


def survey_row(scene, playback, folds, fps):
    """playback [start, end) Scene display frames; folds [{"range": [s, e], ...}] -> row with 'short' when the rise
    sub-section ends before the Scene does."""
    row = {"scene": scene, "playback": playback, "playback_s": round((playback[1] - playback[0]) / fps, 3),
           "folds": folds}
    if not folds:
        row["verdict"] = "NO_RISE_SUBSECTION"
        return row
    end = max(int(f["range"][1]) for f in folds)
    row["fold_end"] = end
    row["uncovered_frames"] = max(0, int(playback[1]) - end)
    row["uncovered_s"] = round(row["uncovered_frames"] / fps, 3)
    row["verdict"] = "SHORT" if row["uncovered_frames"] > 0 else "COVERS"
    return row


def plan_holds(fold, scene_playback, scene_tpf, rise_end_tick, movers):
    """fold {"range": [s, e], "start_offset_tick": int, "play_rate": float}; movers [{"binding", "sections":
    [{"blend": str|None, "channels": {base: {"keys": [[tick, v]], "default": v|None}}}]}] ->
    {"range": [fold_end, scene_end], "targets": [{"binding", "values": {base: v}}]}. Refuses anything not 1:1."""
    s, e = int(fold["range"][0]), int(fold["range"][1])
    if s != 0:
        raise PlanError("FOLD_NOT_AT_ZERO|%d" % s)
    if int(fold.get("start_offset_tick", 0)) != 0:
        raise PlanError("FOLD_START_OFFSET|%s" % fold.get("start_offset_tick"))
    if abs(float(fold.get("play_rate", 1.0)) - 1.0) > 1e-9:
        raise PlanError("FOLD_PLAY_RATE|%s" % fold.get("play_rate"))
    if e * int(scene_tpf) != int(rise_end_tick):
        raise PlanError("FOLD_NOT_WHOLE_RISE|fold_end_tick=%d|rise_end_tick=%d" % (e * int(scene_tpf), rise_end_tick))
    end = int(scene_playback[1])
    if end <= e:
        raise PlanError("NOTHING_UNCOVERED|scene_end=%d|fold_end=%d" % (end, e))
    if not movers:
        raise PlanError("NO_TRANSFORM_MOVERS")
    targets, seen = [], set()
    for m in movers:
        if m["binding"] in seen:
            raise PlanError("DUPLICATE_MOVER|%s" % m["binding"])
        seen.add(m["binding"])
        if len(m["sections"]) != 1:
            raise PlanError("MOVER_SECTIONS|%s|%d" % (m["binding"], len(m["sections"])))
        sec = m["sections"][0]
        blend = (sec.get("blend") or "UNSET").upper()
        if blend not in ("ABSOLUTE", "UNSET"):          # UNSET = the transform section default, absolute [inf]
            raise PlanError("MOVER_NOT_ABSOLUTE|%s|%s" % (m["binding"], blend))
        missing = [c for c in CHANNELS if c not in sec["channels"]]
        if missing:
            raise PlanError("MOVER_CHANNELS_MISSING|%s|%s" % (m["binding"], missing))
        vals = {}
        for c in CHANNELS:
            ch = sec["channels"][c]
            late = [k for k in ch["keys"] if int(k[0]) > int(rise_end_tick)]
            if late:
                raise PlanError("KEY_AFTER_RISE_END|%s|%s|%s" % (m["binding"], c, late[:2]))
            try:
                vals[c] = landed_value(ch["keys"], ch.get("default"))
            except PlanError as exc:
                raise PlanError("%s|%s|%s" % (exc, m["binding"], c))
        targets.append({"binding": m["binding"], "values": vals})
    return {"range": [e, end], "targets": targets}


def validate_args(a):
    r = []
    if a.get("mode") not in ("SURVEY", "DRY", "APPLY", "REVERT"):
        r.append("MODE")
    if int(a.get("scene", 0)) != 4:
        r.append("SCENE_NOT_4 (S4-only tool)")
    if a.get("mode") in ("APPLY", "REVERT") and a.get("confirm") != "%s S4HOLD" % a.get("mode"):
        r.append("CONFIRM")
    if a.get("mode") == "APPLY" and not str(a.get("decided_by") or "").strip():
        r.append("DECIDED_BY")
    if a.get("completion") not in ("KEEP_STATE", "RESTORE_STATE"):
        r.append("COMPLETION")
    return r


def readback_diff(want, got, tol=1e-4):
    """want/got {"range": [s, e], "completion": str, "values": {c: v}, "n_keys": int}; [] when identical."""
    d = []
    if list(want["range"]) != list(got["range"]):
        d.append("range %s != %s" % (got["range"], want["range"]))
    if want["completion"] != got["completion"]:
        d.append("completion %s != %s" % (got["completion"], want["completion"]))
    if got.get("n_keys", 0) != 0:
        d.append("keys present %s" % got.get("n_keys"))
    for c in CHANNELS:
        g = got["values"].get(c)
        if g is None or abs(float(g) - float(want["values"][c])) > max(tol, 1e-6 * abs(float(want["values"][c]))):
            d.append("%s %s != %s" % (c, g, want["values"][c]))
    return d


# =====================================================================================================================
# Live (Unreal). Every unreal handle is a local (memory: UE wrappers in module globals crash the editor).
# =====================================================================================================================

def _here():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _file(path):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _stop(run, reason):
    unreal.log_error("S4HOLD_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return sorted(p.get_path_name().split(".")[0] for p in
                  list(lib.get_dirty_content_packages()) + list(lib.get_dirty_map_packages()))


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _enum(v):
    """Enum name; an OptionalMovieSceneBlendType {blend_type, is_valid} (7 Oct live, klara_reveal.py:2393) -> its
    blend_type, or 'UNSET' when is_valid is False."""
    if hasattr(v, "get_editor_property"):
        try:
            if not bool(v.get_editor_property("is_valid")):
                return "UNSET"
        except Exception:  # noqa: BLE001
            pass
        try:
            v = v.get_editor_property("blend_type")
        except Exception:  # noqa: BLE001
            pass
    return str(getattr(v, "name", v)).split(".")[-1]


def _gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def _folds(seq):
    rows = []
    for t in seq.get_tracks():
        if not isinstance(t, unreal.MovieSceneSubTrack):
            continue
        for s in t.get_sections():
            sub = s.get_sequence()
            if sub is None or "HangarRise" not in sub.get_path_name():
                continue
            p = s.get_editor_property("parameters")
            rate, rate_read = 1.0, True          # prec klara_reveal.py:1657-1662 (5.8 time-warp struct)
            try:
                ts = p.get_editor_property("time_scale")
                rate = float(ts) if isinstance(ts, (int, float)) else float(ts.get_editor_property("play_rate"))
            except Exception:  # noqa: BLE001 - reported; the tick-length gate in plan_holds still has to pass
                rate, rate_read = 1.0, False
            rows.append({"track": str(t.get_display_name()), "range": [s.get_start_frame(), s.get_end_frame()],
                         "rise": sub.get_path_name().split(".")[0], "active": bool(s.is_active()),
                         "completion": _enum(s.get_completion_mode()),
                         "start_offset_tick": int(p.get_editor_property("start_frame_offset").value),
                         "play_rate": rate, "play_rate_read": rate_read})
    return rows


def survey():
    out = []
    for n in range(1, 7):
        seq = unreal.load_asset(SCENE % n)
        if seq is None:
            out.append({"scene": n, "verdict": "NO_SCENE_SEQUENCE"})
            continue
        fps = _rate(seq.get_display_rate())
        out.append(survey_row(n, [int(seq.get_playback_start()), int(seq.get_playback_end())], _folds(seq), fps))
    return out


def _movers(rise):
    rows = []
    for b in rise.get_bindings():
        secs = []
        for t in b.get_tracks():
            if not isinstance(t, unreal.MovieScene3DTransformTrack):
                continue
            for s in t.get_sections():
                chans = {}
                for c in s.get_all_channels():
                    name = channel_base(c.channel_name if hasattr(c, "channel_name") else c.get_name())
                    keys = [[int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
                             float(k.get_value())] for k in c.get_keys()]
                    chans[name] = {"keys": keys, "default": float(c.get_default()) if c.has_default() else None}
                try:
                    blend = _enum(s.get_blend_type())
                except Exception:  # noqa: BLE001
                    blend = None
                secs.append({"blend": blend, "channels": chans})
        if secs:
            rows.append({"binding": str(b.get_display_name()), "guid": _gs(b.get_id()), "sections": secs})
    return rows


def _other_rise_tracks(rise):
    out = []
    for b in rise.get_bindings():
        for t in b.get_tracks():
            if not isinstance(t, unreal.MovieScene3DTransformTrack):
                out.append("%s/%s" % (b.get_display_name(), t.get_class().get_name()))
    return out


def _actor(label, run):
    acts = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if str(a.get_actor_label()) == label]
    if len(acts) != 1:
        _stop(run, "ACTOR_COUNT|%s|%d" % (label, len(acts)))
    return acts[0]


def _our_tracks(b):
    return [t for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)
            and str(t.get_display_name()) == TRACK_NAME]


def _read_section(s):
    vals, n = {}, 0
    for c in s.get_all_channels():
        base = channel_base(c.channel_name if hasattr(c, "channel_name") else c.get_name())
        vals[base] = float(c.get_default()) if c.has_default() else None
        n += len(list(c.get_keys()))
    return {"range": [s.get_start_frame(), s.get_end_frame()], "completion": _enum(s.get_completion_mode()),
            "values": vals, "n_keys": n, "blend": _enum(s.get_blend_type())}


def _plan(args, run):
    seq, rise = unreal.load_asset(SCENE % 4), unreal.load_asset(RISE % 4)
    if seq is None or rise is None:
        _stop(run, "ASSET_MISSING")
    folds = [f for f in _folds(seq) if f["rise"] == RISE % 4]
    if len(folds) != 1:
        _stop(run, "FOLD_COUNT|%d" % len(folds))
    scene_tpf = int(round(_rate(seq.get_tick_resolution()) / _rate(seq.get_display_rate())))
    rise_tpf = int(round(_rate(rise.get_tick_resolution()) / _rate(rise.get_display_rate())))
    rise_end_tick = int(rise.get_playback_end()) * rise_tpf - int(rise.get_playback_start()) * rise_tpf
    if int(rise.get_playback_start()) != 0:
        _stop(run, "RISE_START_NOT_ZERO|%d" % rise.get_playback_start())
    if abs(_rate(seq.get_tick_resolution()) - _rate(rise.get_tick_resolution())) > 1e-9:
        _stop(run, "TICK_RESOLUTION_DIFFERS")
    movers = _movers(rise)
    try:
        plan = plan_holds(folds[0], [int(seq.get_playback_start()), int(seq.get_playback_end())], scene_tpf,
                          rise_end_tick, movers)
    except PlanError as exc:
        _stop(run, "PLAN|%s" % exc)
    for t in plan["targets"]:
        a = _actor(t["binding"], run)
        t["actor_path"] = a.get_path_name()
        rc = a.get_editor_property("root_component")
        t["editor_relative"] = {"loc": [float(x) for x in (rc.relative_location.x, rc.relative_location.y,
                                                          rc.relative_location.z)],
                                "rot": [float(rc.relative_rotation.roll), float(rc.relative_rotation.pitch),
                                        float(rc.relative_rotation.yaw)]}
    plan["fold"] = folds[0]
    plan["rise_end_tick"] = rise_end_tick
    plan["scene_tpf"] = scene_tpf
    plan["not_held_rise_tracks"] = _other_rise_tracks(rise)
    plan["completion"] = args["completion"]
    return plan


def run_apply(args, run, plan):
    here = _here()
    rec_path = os.path.join(here, RECORD)
    if os.path.exists(rec_path):
        _stop(run, "RECORD_EXISTS (REVERT first)")
    scene_path = SCENE % 4
    census0 = _census()
    if census0:
        _stop(run, "DIRTY_BEFORE|%s" % census0)
    src = _file(scene_path)
    folder = os.path.join(_project(), "Backups", "PreS4HangarHold-%s" % run)
    rec = {"schema": 1, "tool": TOOL, "run": run, "applied": False, "decided_by": args["decided_by"],
           "plan": plan, "backup": folder, "source_sha256": _sha(src), "written": datetime.datetime.now().isoformat()}
    fd = os.open(rec_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())
    os.makedirs(folder, exist_ok=False)
    dst = os.path.join(folder, os.path.basename(src))
    shutil.copy2(src, dst)
    if _sha(dst) != rec["source_sha256"]:
        _stop(run, "BACKUP_HASH")
    shutil.copy2(rec_path, folder)
    seq = unreal.load_asset(scene_path)
    gs_before = {_gs(b.get_id()) for b in seq.get_bindings()}
    mode = getattr(unreal.MovieSceneCompletionMode, args["completion"])
    rows = []
    for t in plan["targets"]:
        actor = _actor(t["binding"], run)
        b = seq.add_possessable(actor)
        g = _gs(b.get_id())
        created = g not in gs_before
        if created:
            b.set_display_name(BIND_PREFIX + t["binding"])
        if _our_tracks(b):
            _stop(run, "TRACK_ALREADY_PRESENT|%s|NOTHING SAVED; Don't-Save restart" % t["binding"])
        tr = b.add_track(unreal.MovieScene3DTransformTrack)
        tr.set_display_name(TRACK_NAME)
        s = tr.add_section()
        s.set_range(int(plan["range"][0]), int(plan["range"][1]))
        s.set_completion_mode(mode)
        s.set_blend_type(unreal.MovieSceneBlendType.ABSOLUTE)          # prec klara_reveal.py:2353 (ADDITIVE)
        for c in s.get_all_channels():
            base = channel_base(c.channel_name if hasattr(c, "channel_name") else c.get_name())
            c.set_default(float(t["values"][base]))
        got = _read_section(s)
        diff = readback_diff({"range": plan["range"], "completion": args["completion"], "values": t["values"]}, got)
        if diff or got["blend"].upper() != "ABSOLUTE":
            _stop(run, "READBACK|%s|%s|%s|NOTHING SAVED; Don't-Save restart" % (t["binding"], diff, got["blend"]))
        rows.append({"binding": t["binding"], "guid": g, "created": created})
    census1 = _census()
    if census1 != [scene_path]:
        _stop(run, "DIRTY_SET|%s|NOTHING SAVED; Don't-Save restart" % census1)
    if not unreal.EditorAssetLibrary.save_asset(scene_path, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED")
    seq = unreal.load_asset(scene_path)
    by = {_gs(b.get_id()): b for b in seq.get_bindings()}
    for r, t in zip(rows, plan["targets"]):
        tracks = _our_tracks(by[r["guid"]]) if r["guid"] in by else []
        if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
            _stop(run, "POST_SAVE_TRACKS|%s" % t["binding"])
        d = readback_diff({"range": plan["range"], "completion": args["completion"], "values": t["values"]},
                          _read_section(tracks[0].get_sections()[0]))
        if d:
            _stop(run, "POST_SAVE_READBACK|%s|%s" % (t["binding"], d))
    if _census():
        _stop(run, "DIRTY_AFTER|%s" % _census())
    rec.update({"applied": True, "bindings": rows, "applied_at": datetime.datetime.now().isoformat(),
                "saved_sha256": _sha(src)})
    tmp = rec_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1, default=str)
    os.replace(tmp, rec_path)
    unreal.log("S4HOLD_APPLY_OK|run=%s|range=%s|movers=%d|%s" % (run, plan["range"], len(rows),
                                                                 [r["binding"] for r in rows]))


def run_revert(args, run):
    rec_path = os.path.join(_here(), RECORD)
    if not os.path.exists(rec_path):
        _stop(run, "NO_RECORD")
    with open(rec_path, encoding="utf-8") as h:
        rec = json.load(h)
    if not rec.get("applied"):
        _stop(run, "RECORD_NOT_APPLIED (partial APPLY: restore the backup %s with the editor closed)" % rec.get("backup"))
    scene_path = SCENE % 4
    if _census():
        _stop(run, "DIRTY_BEFORE|%s" % _census())
    seq = unreal.load_asset(scene_path)
    by = {_gs(b.get_id()): b for b in seq.get_bindings()}
    for r in rec["bindings"]:
        b = by.get(r["guid"])
        if b is None:
            _stop(run, "BINDING_GONE|%s" % r["binding"])
        ours = _our_tracks(b)
        if len(ours) != 1:
            _stop(run, "OUR_TRACKS|%s|%d" % (r["binding"], len(ours)))
        b.remove_track(ours[0])  # returns None (memory): read back below
        if _our_tracks(b):
            _stop(run, "REMOVE_TRACK_READBACK|%s|NOTHING SAVED; Don't-Save restart" % r["binding"])
        if r["created"]:
            if list(b.get_tracks()) or list(b.get_child_possessables()):
                _stop(run, "CREATED_BINDING_NOT_EMPTY|%s|NOTHING SAVED; Don't-Save restart" % r["binding"])
            b.remove()
    seq = unreal.load_asset(scene_path)
    left = [str(b.get_display_name()) for b in seq.get_bindings()
            if _our_tracks(b) or str(b.get_display_name()).startswith(BIND_PREFIX)]
    if left:
        _stop(run, "REVERT_LEFTOVERS|%s|NOTHING SAVED; Don't-Save restart" % left)
    if _census() != [scene_path]:
        _stop(run, "DIRTY_SET|%s|NOTHING SAVED; Don't-Save restart" % _census())
    if not unreal.EditorAssetLibrary.save_asset(scene_path, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED")
    if _census():
        _stop(run, "DIRTY_AFTER|%s" % _census())
    os.replace(rec_path, rec_path + ".reverted-" + run)
    unreal.log("S4HOLD_REVERT_OK|run=%s|removed=%d" % (run, len(rec["bindings"])))


def main(args):
    run = args.get("run_id") or "S4HOLD-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|%s" % bad)
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if args["mode"] in ("APPLY", "REVERT"):
        if ed.get_game_world() is not None:
            _stop(run, "PIE_RUNNING (edits are editor-world; never end PIE from here)")
        cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
        if cur is not None:
            _stop(run, "SEQUENCER_OPEN|%s" % cur.get_path_name())
    if args["mode"] == "REVERT":
        run_revert(args, run)
        return
    sv = survey()
    out = {"run": run, "survey": sv}
    if args["mode"] != "SURVEY":
        out["plan"] = _plan(args, run)
    path = os.path.join(_here(), "s4_hangar_hold_%s_%s.json" % (args["mode"].lower(), run))
    with open(path, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1, default=str)
    short = ["S%s:%s" % (r["scene"], r.get("uncovered_s")) for r in sv if r.get("verdict") == "SHORT"]
    if args["mode"] == "APPLY":
        run_apply(args, run, out["plan"])
        return
    unreal.log("S4HOLD_%s_OK|run=%s|short=%s|plan=%s|%s" % (
        args["mode"], run, short,
        None if "plan" not in out else {"range": out["plan"]["range"],
                                        "movers": [t["binding"] for t in out["plan"]["targets"]]}, path))


if unreal is not None and "S4HOLD_ARGS" in globals():
    main(globals()["S4HOLD_ARGS"])
