"""S4 BACKCLOTH CACHE HOLD (8 Oct 2026, offline-written; conductor runs later).

Purpose: keep ``P04 Backcloth (baked)`` on its final, down Geometry Cache sample after
the Hangar Fold ends.  The tool writes one one-frame Geometry Cache section directly
in LS_DevScene_04 and gives it KEEP_STATE.  A one-frame section avoids the looping
implied by FirstLoopStartFrameOffset; the cache time and one-frame length are arguments.

Modes and markers:
  DRY    read only -> S4BACKCLOTH_DRY_OK
  APPLY  confirm "APPLY S4BACKCLOTH" -> record + backup before mutation, exact census,
         save only LS_DevScene_04, reload/read back -> S4BACKCLOTH_APPLY_OK
  REVERT confirm "REVERT S4BACKCLOTH" -> revert backup, remove only the recorded track,
         save only LS_DevScene_04 -> S4BACKCLOTH_REVERT_OK

Declaration evidence (UE 5.8 installed headers):
  - MovieSceneGeometryCacheSection.h:20-44 exposes the cache asset, three frame
    offsets, PlayRate and bReverse; it exposes no clamp/hold switch.
  - MovieSceneSection.h:104-108 says RestoreState restores previous state; :424-435
    exposes Get/SetCompletionMode.
  - MovieSceneGeometryCacheTrack.h:23-40 declares section creation/ownership.

KEEP_STATE retaining the final decoded Geometry Cache sample is still [inferred] until
the ordered PIE probe/stills in the runbook.  No Klara level or map is ever saved.
"""
import datetime
import hashlib
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None

TOOL = "s4_backcloth_hold"
MARK = "S4BACKCLOTH"
ARGS_NAME = "s4_backcloth_hold_args.json"
RECORD_NAME = "s4_backcloth_hold_record.json"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MODES = ("DRY", "APPLY", "REVERT")


class PlanError(Exception):
    pass


def validate_args(a):
    r = []
    mode = str(a.get("mode") or "").upper()
    if mode not in MODES:
        r.append("MODE")
    if mode in ("APPLY", "REVERT") and a.get("confirm") != "%s S4BACKCLOTH" % mode:
        r.append("CONFIRM")
    if mode == "APPLY" and not str(a.get("decided_by") or "").strip():
        r.append("DECIDED_BY")
    for k in ("scene_sequence", "rise_sequence", "actor_label", "track_name", "expected_cache"):
        if not a.get(k):
            r.append("MISSING_%s" % k.upper())
    if a.get("completion") != "KEEP_STATE":
        r.append("COMPLETION_MUST_BE_KEEP_STATE")
    if int(a.get("section_frames", 0)) != 1:
        r.append("SECTION_FRAMES_MUST_BE_1")
    if float(a.get("down_cache_s", -1)) < 0:
        r.append("DOWN_CACHE_S")
    if float(a.get("end_margin_s", 0)) <= 0:
        r.append("END_MARGIN_S")
    return r


def _overlaps(a, b):
    return int(a[0]) < int(b[1]) and int(a[1]) > int(b[0])


def plan_hold(scene_range, fold_rows, duration_s, tick_resolution, args):
    """Pure plan. The authored section is one Scene display frame; KEEP_STATE is
    expected to retain its last evaluated state through ``hold_range`` [inferred]."""
    active = [f for f in fold_rows if f.get("active", True)]
    if len(active) != 1:
        raise PlanError("ACTIVE_FOLD_COUNT|%d" % len(active))
    fold = active[0]
    if int(fold["range"][0]) != 0:
        raise PlanError("FOLD_NOT_AT_ZERO|%s" % fold["range"])
    start, scene_end = int(fold["range"][1]), int(scene_range[1])
    if start >= scene_end:
        raise PlanError("NOTHING_TO_HOLD|%d>=%d" % (start, scene_end))
    margin = float(args["end_margin_s"])
    cache_s = float(duration_s) - margin
    if cache_s < float(args["down_cache_s"]):
        raise PlanError("HOLD_TIME_NOT_DOWN|%.6f<%.6f" % (cache_s, float(args["down_cache_s"])))
    if not cache_s < float(duration_s):
        raise PlanError("HOLD_TIME_NOT_BEFORE_END|%.6f|%.6f" % (cache_s, duration_s))
    off = int(round(cache_s * float(tick_resolution)))
    mapped = off / float(tick_resolution)
    if abs(mapped - cache_s) > 0.5 / float(tick_resolution) + 1e-12:
        raise PlanError("OFFSET_ROUNDING|%.9f|%.9f" % (cache_s, mapped))
    return {"scene_range": [int(scene_range[0]), scene_end], "fold": fold,
            "section_range": [start, start + 1], "hold_range": [start, scene_end],
            "cache_duration_s": float(duration_s), "hold_cache_time_s": mapped,
            "start_frame_offset_tick": off, "tick_resolution": float(tick_resolution),
            "completion": "KEEP_STATE", "play_rate": 1.0, "reverse": False,
            "end_frame_offset_tick": 0, "first_loop_start_frame_offset_tick": 0,
            "retention_tier": "inferred_until_PIE_probe"}


def conflict_rows(scene_rows, label, own_track, hold_range):
    """Return overlapping Geometry Cache tracks on the actor binding, including a
    leftover track from this tool. Scene rows are plain dictionaries for the harness."""
    out = []
    for b in scene_rows:
        name = str(b.get("binding"))
        if not (name == label or name.endswith(": " + label)):
            continue
        for t in b.get("tracks") or []:
            if t.get("class") != "MovieSceneGeometryCacheTrack":
                continue
            for s in t.get("sections") or []:
                if _overlaps(s["range"], hold_range) or str(t.get("name")) == own_track:
                    out.append("%s/%s/%s" % (name, t.get("name"), s["range"]))
    return out


def readback_diff(want, got, tol=1e-6):
    out = []
    for k in ("range", "completion", "cache", "start_offset", "end_offset", "first_loop_offset", "reverse"):
        if got.get(k) != want.get(k):
            out.append("%s %r != %r" % (k, got.get(k), want.get(k)))
    if abs(float(got.get("play_rate", 0)) - float(want["play_rate"])) > tol:
        out.append("play_rate %r != %r" % (got.get("play_rate"), want["play_rate"]))
    return out


def _here():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _file(asset):
    return os.path.join(_project(), "Content", *asset[len("/Game/"):].split("/")) + ".uasset"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def _enum(v):
    return str(getattr(v, "name", v)).split(".")[-1].upper()


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _world(run):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        _stop(run, "PIE_RUNNING (this authoring tool never starts or ends PIE)")
    world = ed.get_editor_world()
    name = str(world.get_outermost().get_name()) if world is not None else None
    if name != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD|%s" % name)
    return world


def _folds(seq, rise_path):
    out = []
    for t in seq.get_tracks():
        if not isinstance(t, unreal.MovieSceneSubTrack):
            continue
        for s in t.get_sections():
            inner = s.get_sequence()
            if inner is not None and _path(inner) == rise_path:
                out.append({"track": str(t.get_display_name()), "range": [int(s.get_start_frame()), int(s.get_end_frame())],
                            "active": bool(s.is_active()), "completion": _enum(s.get_completion_mode())})
    return out


def _actors(label):
    return [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if str(a.get_actor_label()) == label]


def _binding_rows(seq):
    out = []
    for b in seq.get_bindings():
        tracks = []
        for t in b.get_tracks():
            tracks.append({"name": str(t.get_display_name()), "class": t.get_class().get_name(),
                           "sections": [{"range": [int(s.get_start_frame()), int(s.get_end_frame())]}
                                        for s in t.get_sections()]})
        out.append({"binding": str(b.get_display_name()), "guid": _gs(b.get_id()), "tracks": tracks})
    return out


def _cache_sections(seq, label):
    out = []
    for b in seq.get_bindings():
        if not (str(b.get_display_name()) == label or str(b.get_display_name()).endswith(": " + label)):
            continue
        for t in b.get_tracks():
            if not isinstance(t, unreal.MovieSceneGeometryCacheTrack):
                continue
            for s in t.get_sections():
                out.append((b, t, s))
    return out


def _params(s):
    p = s.get_editor_property("params")
    val = lambda n: p.get_editor_property(n)
    num = lambda n: int(val(n).value) if hasattr(val(n), "value") else int(val(n))
    return {"cache": _path(val("geometry_cache_asset")), "start_offset": num("start_frame_offset"),
            "end_offset": num("end_frame_offset"), "first_loop_offset": num("first_loop_start_frame_offset"),
            "play_rate": float(val("play_rate")), "reverse": bool(val("reverse"))}


def _read_section(t, s):
    return dict(_params(s), range=[int(s.get_start_frame()), int(s.get_end_frame())],
                completion=_enum(s.get_completion_mode()), track=str(t.get_display_name()), active=bool(s.is_active()))


def _api_table():
    checks = []
    for api, ok, tier in (
            ("MovieSceneGeometryCacheTrack", hasattr(unreal, "MovieSceneGeometryCacheTrack"),
             "decl MovieSceneGeometryCacheTrack.h:14-40"),
            ("MovieSceneGeometryCacheParams", hasattr(unreal, "MovieSceneGeometryCacheParams"),
             "decl MovieSceneGeometryCacheSection.h:13-44"),
            ("MovieSceneSection.set_completion_mode", hasattr(unreal.MovieSceneSection, "set_completion_mode"),
             "decl MovieSceneSection.h:424-435")):
        checks.append({"api": api, "ok": bool(ok), "tier": tier})
    return checks


def gather(args, run):
    world = _world(run)
    seq = unreal.load_asset(args["scene_sequence"])
    rise = unreal.load_asset(args["rise_sequence"])
    if seq is None or rise is None:
        raise PlanError("ASSETS|scene=%s|rise=%s" % (seq is not None, rise is not None))
    acts = _actors(args["actor_label"])
    if len(acts) != 1:
        raise PlanError("ACTOR_COUNT|%s|%d" % (args["actor_label"], len(acts)))
    actor = acts[0]
    comps = list(actor.get_components_by_class(unreal.GeometryCacheComponent))
    if len(comps) != 1:
        raise PlanError("GEOMETRY_CACHE_COMPONENT_COUNT|%d" % len(comps))
    cache = comps[0].get_editor_property("geometry_cache")
    duration = float(comps[0].get_duration())
    if _path(cache) != args["expected_cache"]:
        raise PlanError("CACHE_ASSET|%s|want=%s" % (_path(cache), args["expected_cache"]))
    source = _cache_sections(rise, args["actor_label"])
    if len(source) != 1:
        raise PlanError("SOURCE_CACHE_SECTION_COUNT|%d" % len(source))
    sb, st, ss = source[0]
    located = sorted(o.get_path_name() for o in rise.locate_bound_objects(sb, world))
    if located != [actor.get_path_name()]:
        raise PlanError("SOURCE_BINDING_RESOLVES|%s|%s" % (located, actor.get_path_name()))
    sp = _read_section(st, ss)
    if sp["cache"] != args["expected_cache"] or not sp["active"]:
        raise PlanError("SOURCE_SECTION|%s" % sp)
    plan = plan_hold([int(seq.get_playback_start()), int(seq.get_playback_end())],
                     _folds(seq, args["rise_sequence"]), duration, _rate(seq.get_tick_resolution()), args)
    plan.update(scene=args["scene_sequence"], rise=args["rise_sequence"], actor_label=args["actor_label"],
                actor_path=actor.get_path_name(), cache=args["expected_cache"], source_section=sp,
                source_binding_guid=_gs(sb.get_id()), completion=args["completion"], track_name=args["track_name"])
    plan["conflicts"] = conflict_rows(_binding_rows(seq), args["actor_label"], args["track_name"], plan["hold_range"])
    plan["api_table"] = _api_table()
    plan["apply_gate"] = (["CONFLICTS|%d" % len(plan["conflicts"])] if plan["conflicts"] else []) + \
                         (["API_MISSING"] if not all(r["ok"] for r in plan["api_table"]) else [])
    return plan, seq, actor


def _want(plan):
    return {"range": plan["section_range"], "completion": "KEEP_STATE", "cache": plan["cache"],
            "start_offset": plan["start_frame_offset_tick"], "end_offset": 0, "first_loop_offset": 0,
            "play_rate": 1.0, "reverse": False}


def _our(seq, guid, track_name):
    by = {_gs(b.get_id()): b for b in seq.get_bindings()}
    b = by.get(guid)
    tracks = [] if b is None else [t for t in b.get_tracks() if isinstance(t, unreal.MovieSceneGeometryCacheTrack)
                                   and str(t.get_display_name()) == track_name]
    return b, tracks


def apply(args, run, plan, seq, actor):
    if plan["apply_gate"]:
        _stop(run, "APPLY_GATE|%s" % plan["apply_gate"])
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|%s" % _census())
    here = _here()
    rec_path = os.path.join(here, RECORD_NAME)
    if os.path.exists(rec_path):
        _stop(run, "RECORD_EXISTS (REVERT first)")
    src = _file(args["scene_sequence"])
    backup = os.path.join(_project(), "Backups", "PreS4BackclothHold-" + run)
    rec = {"schema": 1, "tool": TOOL, "run": run, "applied": False, "args": args, "plan": plan,
           "decided_by": args["decided_by"], "backup": backup, "source_sha256": _sha(src),
           "written": datetime.datetime.now().isoformat(timespec="seconds")}
    fd = os.open(rec_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1, sort_keys=True, default=str); h.flush(); os.fsync(h.fileno())
    os.makedirs(backup, exist_ok=False)
    dst = os.path.join(backup, os.path.basename(src)); shutil.copy2(src, dst); shutil.copy2(rec_path, backup)
    if _sha(dst) != rec["source_sha256"]:
        _stop(run, "BACKUP_HASH")
    before = {_gs(b.get_id()) for b in seq.get_bindings()}
    b = seq.add_possessable(actor)
    guid = _gs(b.get_id())
    created = guid not in before
    if created:
        b.set_display_name("S4 Backcloth Hold: " + args["actor_label"])
    located = sorted(o.get_path_name() for o in seq.locate_bound_objects(b, _world(run)))
    if located != [plan["actor_path"]]:
        _stop(run, "TARGET_BINDING_RESOLVES|%s|NOTHING SAVED; Don't-Save restart" % located)
    tr = b.add_track(unreal.MovieSceneGeometryCacheTrack)
    tr.set_display_name(args["track_name"])
    sec = tr.add_section()
    sec.set_range(*plan["section_range"])
    sec.set_completion_mode(unreal.MovieSceneCompletionMode.KEEP_STATE)
    p = sec.get_editor_property("params")
    p.set_editor_property("geometry_cache_asset", unreal.load_asset(plan["cache"]))
    p.set_editor_property("start_frame_offset", unreal.FrameNumber(plan["start_frame_offset_tick"]))
    p.set_editor_property("end_frame_offset", unreal.FrameNumber(0))
    p.set_editor_property("first_loop_start_frame_offset", unreal.FrameNumber(0))
    p.set_editor_property("play_rate", 1.0)
    p.set_editor_property("reverse", False)
    sec.set_editor_property("params", p)
    diff = readback_diff(_want(plan), _read_section(tr, sec))
    if diff:
        _stop(run, "READBACK|%s|NOTHING SAVED; Don't-Save restart" % diff)
    if _census() != {"content": [args["scene_sequence"]], "maps": []}:
        _stop(run, "DIRTY_SET|%s|NOTHING SAVED; Don't-Save restart" % _census())
    if not unreal.EditorAssetLibrary.save_asset(args["scene_sequence"], only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED")
    seq2 = unreal.load_asset(args["scene_sequence"])
    b2, tracks = _our(seq2, guid, args["track_name"])
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        _stop(run, "POST_SAVE_TRACKS|%d" % len(tracks))
    diff = readback_diff(_want(plan), _read_section(tracks[0], tracks[0].get_sections()[0]))
    located = [] if b2 is None else sorted(o.get_path_name() for o in seq2.locate_bound_objects(b2, _world(run)))
    if located != [plan["actor_path"]]:
        diff.append("resolves %s" % located)
    if diff or _census() != {"content": [], "maps": []}:
        _stop(run, "POST_SAVE_READBACK|%s|census=%s" % (diff, _census()))
    rec.update(applied=True, binding_guid=guid, created_binding=created, saved_sha256=_sha(src),
               applied_at=datetime.datetime.now().isoformat(timespec="seconds"))
    tmp = rec_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1, sort_keys=True, default=str); h.flush(); os.fsync(h.fileno())
    os.replace(tmp, rec_path)
    unreal.log("%s_APPLY_OK|run=%s|section=%s|cache_s=%.6f|hold=%s|backup=%s|record=%s|tier=inferred_until_PIE"
               % (MARK, run, plan["section_range"], plan["hold_cache_time_s"], plan["hold_range"], backup, rec_path))


def revert(args, run):
    rec_path = os.path.join(_here(), RECORD_NAME)
    if not os.path.exists(rec_path):
        _stop(run, "NO_RECORD")
    with open(rec_path, encoding="utf-8") as h:
        rec = json.load(h)
    if not rec.get("applied") or rec.get("tool") != TOOL:
        _stop(run, "RECORD_NOT_APPLIED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|%s" % _census())
    seq = unreal.load_asset(args["scene_sequence"])
    b, tracks = _our(seq, rec["binding_guid"], args["track_name"])
    if b is None or len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        _stop(run, "STATE_DRIFTED|binding=%s|tracks=%d" % (b is not None, len(tracks)))
    diff = readback_diff(_want(rec["plan"]), _read_section(tracks[0], tracks[0].get_sections()[0]))
    if diff:
        _stop(run, "STATE_DRIFTED|%s" % diff)
    src = _file(args["scene_sequence"])
    backup = os.path.join(_project(), "Backups", "PreS4BackclothHoldRevert-" + run)
    os.makedirs(backup, exist_ok=False)
    dst = os.path.join(backup, os.path.basename(src))
    shutil.copy2(src, dst)
    shutil.copy2(rec_path, backup)
    if _sha(dst) != _sha(src):
        _stop(run, "REVERT_BACKUP_HASH")
    b.remove_track(tracks[0])
    if _our(seq, rec["binding_guid"], args["track_name"])[1]:
        _stop(run, "REMOVE_TRACK_READBACK|NOTHING SAVED; Don't-Save restart")
    removed_binding = False
    if rec.get("created_binding"):
        if list(b.get_tracks()) or list(b.get_child_possessables()):
            _stop(run, "CREATED_BINDING_NOT_EMPTY|NOTHING SAVED; Don't-Save restart")
        b.remove(); removed_binding = True
    if _census() != {"content": [args["scene_sequence"]], "maps": []}:
        _stop(run, "DIRTY_SET|%s|NOTHING SAVED; Don't-Save restart" % _census())
    if not unreal.EditorAssetLibrary.save_asset(args["scene_sequence"], only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED")
    seq2 = unreal.load_asset(args["scene_sequence"])
    _b2, left = _our(seq2, rec["binding_guid"], args["track_name"])
    if left or _census() != {"content": [], "maps": []}:
        _stop(run, "POST_SAVE_LEFTOVER|tracks=%d|census=%s" % (len(left), _census()))
    os.rename(rec_path, rec_path + ".reverted-" + run)
    unreal.log("%s_REVERT_OK|run=%s|track=%s|binding_removed=%d|backup=%s" %
               (MARK, run, args["track_name"], int(removed_binding), backup))


def main(args=None):
    args = args or globals().get("S4BACKCLOTH_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), encoding="utf-8") as h:
            args = json.load(h)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("S4BACKCLOTH-%Y%m%d-%H%M%S"))
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|%s" % bad)
    world = _world(run)
    cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    if str(args["mode"]).upper() in ("APPLY", "REVERT") and cur is not None:
        _stop(run, "SEQUENCER_OPEN|%s" % _path(cur))
    if str(args["mode"]).upper() == "REVERT":
        return revert(args, run)
    try:
        plan, seq, actor = gather(args, run)
    except PlanError as exc:
        return _stop(run, "PLAN|%s" % exc)
    report = {"tool": TOOL, "run": run, "args": args, "plan": plan, "census": _census()}
    out = os.path.join(_here(), "s4_backcloth_hold_dry_%s.json" % run)
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, sort_keys=True, default=str)
    if str(args["mode"]).upper() == "APPLY":
        return apply(args, run, plan, seq, actor)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|%s" % _census())
    unreal.log("%s_DRY_OK|run=%s|apply_ready=%d|section=%s|cache_s=%.6f|hold=%s|conflicts=%d|report=%s"
               % (MARK, run, int(not plan["apply_gate"]), plan["section_range"], plan["hold_cache_time_s"],
                  plan["hold_range"], len(plan["conflicts"]), out))


if unreal is not None and not getattr(unreal, "_PUSS_FAKE", False):
    main()
