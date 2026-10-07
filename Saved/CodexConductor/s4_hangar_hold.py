"""Hangar HOLD for Scenes 1-4 (7 Oct). Keeps a Scene's hangar LANDED for the part of the Scene that its rise
no longer covers. Written for S4 (APPLIED S4HOLD-20261007-102817, verified in PIE); generalised the same day, offline
and NOT RUN for S1/S2/S3, to a `scene` arg in {1, 2, 3, 4} (Gary 7 Oct, own answers: "Yes, hold S2 and S3 too"; S1
"Hold it, and keep the roof on too" - the roof part belongs to klara_reveal, not here). S5 covers; S6's hangar is
hidden (fold inactive) and is refused.

NON-TRANSFORM HOLD (7 Oct evening, offline-written, NOT RUN): args "hold": "FLOAT" -> main_float (section "NON-TRANSFORM
HOLD" below): rise float tracks (PPV BlendWeight, light Intensity, ...; opt-in visibility/bool) held at their landed
value over the same [fold_end, scene_end), separate confirm/record/track names; GeometryCache tracks listed only, with
a read-only PIEPROBE mode. "hold" absent or "TRANSFORM" runs main_transform = the 4e1e703 main, verbatim.

PER-SCENE NAMES (names(n); for n=4 they are the S4 tool's original strings, so the S4 record and REVERT still work):
  confirm "<MODE> S<n>HOLD", record s<n>_hangar_hold_record.json, track "S<n> Hangar Hold", binding prefix
  "S<n> Hangar Hold: ", backup Backups/PreS<n>HangarHold-<run>, markers S<n>HOLD_*, outputs s<n>_hangar_hold_<mode>_<run>.json.

SCENE TRAPS (handled generically, because every held value is READ from LS_S<n>_HangarRise live, never assumed):
  - S3: hinge_z -120 (Saved/CodexStructure/hangar_s3_record.json hangar.hinge_z) -> the Root's held Location.Z is the
    rise's own value, whatever it is. Pit deck / liner / wave actors are attached to S3 Hangar Root and are NOT rise
    movers; the wave slides key them in LS_DevScene_03 (s3_wave_slides_apply.py:9-13) - untouched here.
  - S1: klara_reveal v3 hides "S1 Hangar Roof" over [269, 5832] with a visibility track and adds an ADDITIVE Lattice
    Hold on the Lattice Fly. This tool only ever adds ONE ABSOLUTE 3D-transform track per rise mover (Root, Roof
    Hinge, Lattice Fly - hangar_build.py:498-501); the Roof is not a mover. scene_conflicts() refuses any existing
    non-additive transform section on a mover's Scene binding that overlaps the hold; additive sections and
    non-transform tracks (visibility) are reported as coexisting, not refused.
  - [inf] Non-transform rise tracks (light intensities, S3's cast-reveal visibility in the rise) are NOT held and
    may also revert past the fold end, as the transforms did in S4; they are listed in plan.not_held_rise_tracks.

(Original S4 notes follow.)
S4 hangar HOLD (7 Oct, offline-written, NOT RUN). Keeps the S4 hangar LANDED for the part of Scene 4 that its rise
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
CHANNELS = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z",
            "Scale.X", "Scale.Y", "Scale.Z")
SCENES = (1, 2, 3, 4)             # S5 covers; S6 hangar hidden (fold inactive) - Gary 7 Oct scope
_MARK = ["S4HOLD"]                # plain str in a list (no UE wrapper); set by main() from the scene


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure (offline-testable)
# =====================================================================================================================

def names(scene):
    """Every per-scene string. names(4) reproduces the S4 tool's original constants exactly (harness-proven)."""
    n = int(scene)
    return {"mark": "S%dHOLD" % n, "track": "S%d Hangar Hold" % n, "bind_prefix": "S%d Hangar Hold: " % n,
            "record": "s%d_hangar_hold_record.json" % n, "backup_prefix": "PreS%dHangarHold-" % n,
            "out_prefix": "s%d_hangar_hold_" % n}


def _overlaps(r, hold):
    """r [s|None, e|None) vs hold [s, e): None is an open bound."""
    s, e = r
    return (s is None or int(s) < int(hold[1])) and (e is None or int(e) > int(hold[0]))


def scene_conflicts(labels, scene_rows, hold_range, own_track):
    """labels: mover actor labels; scene_rows [{"binding": name, "tracks": [{"name", "transform": bool, "sections":
    [{"range": [s, e], "blend": str|None}]}]}] read from the SCENE sequence. A binding belongs to a mover when its name
    is the label or ends with ': <label>' (prefixed bindings: klara_reveal PREFIX, ours). -> (conflicts, coexisting):
    conflicts = non-additive transform sections (not ours) overlapping the hold, which an ABSOLUTE hold would fight;
    coexisting = everything else on those bindings (additive transforms, visibility, ...), reported only."""
    conflicts, coexisting = [], []
    for row in scene_rows:
        name = str(row["binding"])
        hit = [l for l in labels if name == l or name.endswith(": " + l)]
        if not hit:
            continue
        for t in row["tracks"]:
            if str(t["name"]) == own_track:
                continue
            if not t.get("transform"):
                coexisting.append("%s/%s" % (name, t["name"]))
                continue
            for sec in t.get("sections", []):
                blend = str(sec.get("blend") or "UNSET").upper()
                tag = "%s/%s/%s/%s" % (name, t["name"], blend, list(sec["range"]))
                if blend != "ADDITIVE" and _overlaps(sec["range"], hold_range):
                    conflicts.append(tag)
                else:
                    coexisting.append(tag)
    return conflicts, coexisting

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
    if fold.get("active") is False:                      # S6: hangar hidden, its fold inactive [meas survey]
        raise PlanError("FOLD_INACTIVE")
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
    try:
        scene = int(a.get("scene"))
    except (TypeError, ValueError):
        scene = None
    if scene not in SCENES:
        r.append("SCENE_NOT_IN_%s" % (SCENES,))
    elif a.get("mode") in ("APPLY", "REVERT") and a.get("confirm") != "%s %s" % (a.get("mode"), names(scene)["mark"]):
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


def record_scene(rec):
    """Scene a record belongs to. The S4 record (S4HOLD-20261007-102817) predates the field -> 4."""
    return int(rec.get("scene", 4))


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
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (_MARK[0], run, reason))
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


def _our_tracks(b, track):
    return [t for t in b.get_tracks() if isinstance(t, unreal.MovieScene3DTransformTrack)
            and str(t.get_display_name()) == track]


def _sec_range(s):
    """[start|None, end|None]: None for an open bound."""
    st = s.get_start_frame() if s.has_start_frame() else None
    en = s.get_end_frame() if s.has_end_frame() else None
    return [st, en]


def _binding_tracks(b):
    rows = []
    for t in b.get_tracks():
        tf = isinstance(t, unreal.MovieScene3DTransformTrack)
        secs = []
        for s in t.get_sections():
            try:
                blend = _enum(s.get_blend_type()) if tf else None
            except Exception:  # noqa: BLE001 - None -> treated as UNSET (non-additive) by scene_conflicts
                blend = None
            secs.append({"range": _sec_range(s), "blend": blend})
        rows.append({"name": str(t.get_display_name()), "transform": tf, "sections": secs})
    return rows


def _scene_rows(seq):
    return [{"binding": str(b.get_display_name()), "tracks": _binding_tracks(b)} for b in seq.get_bindings()]


def _read_section(s):
    vals, n = {}, 0
    for c in s.get_all_channels():
        base = channel_base(c.channel_name if hasattr(c, "channel_name") else c.get_name())
        vals[base] = float(c.get_default()) if c.has_default() else None
        n += len(list(c.get_keys()))
    return {"range": [s.get_start_frame(), s.get_end_frame()], "completion": _enum(s.get_completion_mode()),
            "values": vals, "n_keys": n, "blend": _enum(s.get_blend_type())}


def _plan(args, run, scene):
    seq, rise = unreal.load_asset(SCENE % scene), unreal.load_asset(RISE % scene)
    if seq is None or rise is None:
        _stop(run, "ASSET_MISSING")
    folds = [f for f in _folds(seq) if f["rise"] == RISE % scene]
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
    conflicts, coexisting = scene_conflicts([t["binding"] for t in plan["targets"]], _scene_rows(seq), plan["range"],
                                            names(scene)["track"])
    if conflicts:
        _stop(run, "SCENE_TRANSFORM_CONFLICT|%s" % conflicts)
    plan["scene"] = scene
    plan["coexisting_scene_tracks"] = coexisting
    plan["fold"] = folds[0]
    plan["rise_end_tick"] = rise_end_tick
    plan["scene_tpf"] = scene_tpf
    plan["not_held_rise_tracks"] = _other_rise_tracks(rise)
    plan["completion"] = args["completion"]
    return plan


def run_apply(args, run, plan, scene):
    nm = names(scene)
    here = _here()
    rec_path = os.path.join(here, nm["record"])
    if os.path.exists(rec_path):
        _stop(run, "RECORD_EXISTS (REVERT first)")
    scene_path = SCENE % scene
    census0 = _census()
    if census0:
        _stop(run, "DIRTY_BEFORE|%s" % census0)
    src = _file(scene_path)
    folder = os.path.join(_project(), "Backups", nm["backup_prefix"] + run)
    rec = {"schema": 1, "tool": TOOL, "scene": scene, "run": run, "applied": False, "decided_by": args["decided_by"],
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
            b.set_display_name(nm["bind_prefix"] + t["binding"])
        clash, _ = scene_conflicts([t["binding"]], [{"binding": t["binding"], "tracks": _binding_tracks(b)}],
                                   plan["range"], nm["track"])
        if clash:
            _stop(run, "BINDING_TRANSFORM_CONFLICT|%s|NOTHING SAVED; Don't-Save restart" % clash)
        if _our_tracks(b, nm["track"]):
            _stop(run, "TRACK_ALREADY_PRESENT|%s|NOTHING SAVED; Don't-Save restart" % t["binding"])
        tr = b.add_track(unreal.MovieScene3DTransformTrack)
        tr.set_display_name(nm["track"])
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
        tracks = _our_tracks(by[r["guid"]], nm["track"]) if r["guid"] in by else []
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
    unreal.log("%s_APPLY_OK|run=%s|range=%s|movers=%d|%s" % (nm["mark"], run, plan["range"], len(rows),
                                                             [r["binding"] for r in rows]))


def run_revert(args, run, scene):
    nm = names(scene)
    rec_path = os.path.join(_here(), nm["record"])
    if not os.path.exists(rec_path):
        _stop(run, "NO_RECORD")
    with open(rec_path, encoding="utf-8") as h:
        rec = json.load(h)
    if record_scene(rec) != scene:
        _stop(run, "RECORD_SCENE|%s!=%s" % (record_scene(rec), scene))
    if not rec.get("applied"):
        _stop(run, "RECORD_NOT_APPLIED (partial APPLY: restore the backup %s with the editor closed)" % rec.get("backup"))
    scene_path = SCENE % scene
    if _census():
        _stop(run, "DIRTY_BEFORE|%s" % _census())
    seq = unreal.load_asset(scene_path)
    by = {_gs(b.get_id()): b for b in seq.get_bindings()}
    for r in rec["bindings"]:
        b = by.get(r["guid"])
        if b is None:
            _stop(run, "BINDING_GONE|%s" % r["binding"])
        ours = _our_tracks(b, nm["track"])
        if len(ours) != 1:
            _stop(run, "OUR_TRACKS|%s|%d" % (r["binding"], len(ours)))
        b.remove_track(ours[0])  # returns None (memory): read back below
        if _our_tracks(b, nm["track"]):
            _stop(run, "REMOVE_TRACK_READBACK|%s|NOTHING SAVED; Don't-Save restart" % r["binding"])
        if r["created"]:
            if list(b.get_tracks()) or list(b.get_child_possessables()):
                _stop(run, "CREATED_BINDING_NOT_EMPTY|%s|NOTHING SAVED; Don't-Save restart" % r["binding"])
            b.remove()
    seq = unreal.load_asset(scene_path)
    left = [str(b.get_display_name()) for b in seq.get_bindings()
            if _our_tracks(b, nm["track"]) or str(b.get_display_name()).startswith(nm["bind_prefix"])]
    if left:
        _stop(run, "REVERT_LEFTOVERS|%s|NOTHING SAVED; Don't-Save restart" % left)
    if _census() != [scene_path]:
        _stop(run, "DIRTY_SET|%s|NOTHING SAVED; Don't-Save restart" % _census())
    if not unreal.EditorAssetLibrary.save_asset(scene_path, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED")
    if _census():
        _stop(run, "DIRTY_AFTER|%s" % _census())
    os.replace(rec_path, rec_path + ".reverted-" + run)
    unreal.log("%s_REVERT_OK|run=%s|removed=%d" % (nm["mark"], run, len(rec["bindings"])))


# =====================================================================================================================
# NON-TRANSFORM HOLD (args "hold": "FLOAT"; 7 Oct evening, offline-written, NOT RUN).
#
# WHY [meas, conductor's own PIE 7 Oct]: 'S3 Hangar Pinned Exposure' BlendWeight reads 1.0 at S3 +30 s and 0.0 at
# +33/40/55/78/182 s (scene_exposure_weight_read.json; s3_white_probe_S3WHITE-r*.json): past the fold end the rise's
# float tracks stop evaluating, exactly as its transforms did, and S3 renders white. The transform hold above never
# touched them (plan.not_held_rise_tracks).
#
# WHAT: for scene N, in LS_DevScene_0N ONLY, over the SAME [fold_end, scene_end) as the transform hold, one section per
# held rise track, on a Scene binding that resolves to the SAME object as the rise binding (LocateBoundObjects on both,
# compared by path), with a constant channel default = the value after the rise channel's LAST key (constant
# post-infinity extrapolation REQUIRED and read per channel, MovieSceneScriptingFloat.h GetPostInfinityExtrapolation),
# or the channel default when unkeyed. Kinds: "float" (default), opt-in "visibility"/"bool" (same rule; the bool
# channel's extrapolation is not exposed to scripting, header default RCCE_Constant MovieSceneBoolChannel.h:38 [decl],
# per-channel value [inf]). GeometryCache tracks are LISTED, never held (no declaration-proven last-frame hold:
# MovieSceneGeometryCacheSection.h:13-54 offers offsets / play rate / reverse only, the mapping body is in the absent
# private .cpp) - decide with mode PIEPROBE, see Docs/Conductor/HANGAR_HOLD_FLOAT_EXTENSION_2026-10-07.md.
#
# SEPARATE FROM THE TRANSFORM HOLD: own confirm "<MODE> S<n>FLOATHOLD", record s<n>_hangar_float_hold_record.json,
# track name "S<n> Hangar Float Hold", binding prefix "S<n> Hangar Float Hold: ", backup PreS<n>HangarFloatHold-<run>,
# markers S<n>FLOATHOLD_*. None of these match the transform hold's names, so neither REVERT sees the other's work
# (harness-proven). The transform path (hold absent or "TRANSFORM") is main_transform = the 4e1e703 main, verbatim.
# =====================================================================================================================

HOLD_KINDS_ALL = ("float", "visibility", "bool")
TRACK_KIND = {"MovieSceneFloatTrack": "float", "MovieSceneVisibilityTrack": "visibility",
              "MovieSceneBoolTrack": "bool", "MovieSceneGeometryCacheTrack": "geometry_cache"}
CONSTANT_EXTRAP = "RCCE_CONSTANT"
FLOAT_MODES = ("DRY", "APPLY", "REVERT", "PIEPROBE")


def fnames(scene):
    n = int(scene)
    return {"mark": "S%dFLOATHOLD" % n, "track": "S%d Hangar Float Hold" % n,
            "bind_prefix": "S%d Hangar Float Hold: " % n, "record": "s%d_hangar_float_hold_record.json" % n,
            "backup_prefix": "PreS%dHangarFloatHold-" % n, "out_prefix": "s%d_hangar_float_hold_" % n}


def track_kind(cls):
    return TRACK_KIND.get(str(cls), "other")


def norm_extrap(v):
    """'RichCurveExtrapolation.RCCE_CONSTANT', '<RichCurveExtrapolation.RCCE_CONSTANT: 3>', 'RCCE_Constant' ->
    'RCCE_CONSTANT'; None -> None."""
    if v is None:
        return None
    m = re.search(r"RCCE_[A-Za-z]+", str(v))
    return m.group(0).upper() if m else str(v).upper()


def target_id(row):
    return "%s/%s/%s" % (row.get("parent") or "-", row["binding"], row.get("property_path") or row["track_class"])


def held_value(kind, ch, rise_end_tick):
    """ch {"keys": [[tick, v]], "default": v|None, "post_extrap": str|None} -> (value, source, last_key_tick).
    Refuses: a last key after the fold end, a non-constant (or unread) post-extrapolation on a keyed FLOAT channel,
    an unkeyed channel with no default."""
    keys = ch.get("keys") or []
    conv = float if kind == "float" else bool
    if keys:
        last = sorted(keys, key=lambda k: int(k[0]))[-1]
        if int(last[0]) > int(rise_end_tick):
            raise PlanError("LAST_KEY_AFTER_FOLD_END|%d>%d" % (int(last[0]), int(rise_end_tick)))
        if kind == "float":
            ex = norm_extrap(ch.get("post_extrap"))
            if ex is None:
                raise PlanError("POST_EXTRAP_UNREAD")
            if ex != CONSTANT_EXTRAP:
                raise PlanError("POST_EXTRAP_NOT_CONSTANT|%s" % ex)
        return conv(last[1]), "last_key", int(last[0])
    if ch.get("default") is None:
        raise PlanError("CHANNEL_UNKEYED_NO_DEFAULT")
    return conv(ch["default"]), "default", None


def _nt_target(r, kind, rise_end_tick):
    secs = r.get("sections") or []
    if len(secs) != 1:
        raise PlanError("SECTIONS|%d" % len(secs))
    s = secs[0]
    if s.get("active") is False:
        raise PlanError("SECTION_INACTIVE")
    blend = str(s.get("blend") or "UNSET").upper()
    if kind == "float" and blend not in ("ABSOLUTE", "UNSET"):
        raise PlanError("BLEND_NOT_ABSOLUTE|%s" % blend)
    st, en = s["range_tick"]
    if en is not None and int(en) < int(rise_end_tick):
        raise PlanError("SECTION_ENDS_BEFORE_FOLD_END|%d<%d" % (int(en), int(rise_end_tick)))
    if st is not None and int(st) >= int(rise_end_tick):
        raise PlanError("SECTION_STARTS_AFTER_FOLD_END|%d" % int(st))
    chans = s.get("channels") or []
    if len(chans) != 1:
        raise PlanError("CHANNELS|%d" % len(chans))
    if kind == "float" and not r.get("property_path"):
        raise PlanError("NO_PROPERTY_PATH")
    value, source, last = held_value(kind, chans[0], rise_end_tick)
    return {"id": target_id(r), "kind": kind, "track_class": r["track_class"], "binding": r["binding"],
            "parent": r.get("parent"), "binding_guid": r.get("binding_guid"), "property_name": r.get("property_name"),
            "property_path": r.get("property_path"), "value": value, "source": source, "last_key_tick": last,
            "last_key_before_fold": last is not None and last < 0, "rise_section_tick": [st, en],
            "rise_completion": s.get("completion")}


def _meaning(kind, r, rise_end_tick):
    if kind == "geometry_cache":
        s = (r.get("sections") or [{}])
        return ("NOT HELD: no declaration-proven way to show a cache's last frame over a held range "
                "(MovieSceneGeometryCacheSection.h:13-54; mapping body in the absent private .cpp). Rise section(s): %s. "
                "Decide with PIEPROBE (report)." % [{k: x.get(k) for k in ("range_tick", "completion", "params")}
                                                     for x in s])
    if kind in HOLD_KINDS_ALL:
        try:
            t = _nt_target(r, kind, rise_end_tick)
        except PlanError as exc:
            return "NOT OPTED IN; would REFUSE: %s" % exc
        extra = (" (MovieSceneVisibilityTrack channel = bHiddenInGame: True = HIDDEN [prec klara_reveal.py:3131-3139])"
                 if kind == "visibility" else "")
        return "NOT OPTED IN; would hold %r from %s%s" % (t["value"], t["source"], extra)
    return "UNSUPPORTED track class: listed only"


def plan_nontransform(hold_range, rise_end_tick, rows, kinds):
    """rows: every NON-transform track of the rise [{"binding", "parent", "binding_guid", "track_class",
    "property_name", "property_path", "sections": [{"range_tick": [s|None, e|None], "active", "blend", "completion",
    "channels": [{"keys": [[tick, v]], "default", "post_extrap"}], "params"?}]}] -> {"range", "kinds", "targets",
    "refused", "listed"}. A refused track blocks APPLY (float_apply_gate); DRY reports everything."""
    kinds = sorted(set(kinds))
    bad = [k for k in kinds if k not in HOLD_KINDS_ALL]
    if bad or not kinds:
        raise PlanError("HOLD_KINDS|%s" % (bad or "empty"))
    targets, refused, listed, seen = [], [], [], set()
    for r in rows:
        kind = track_kind(r["track_class"])
        tid = target_id(r)
        if kind not in kinds:
            listed.append({"id": tid, "kind": kind, "track_class": r["track_class"],
                           "meaning": _meaning(kind, r, rise_end_tick)})
            continue
        if tid in seen:
            refused.append({"id": tid, "kind": kind, "reason": "DUPLICATE_TARGET"})
            continue
        seen.add(tid)
        try:
            targets.append(_nt_target(r, kind, rise_end_tick))
        except PlanError as exc:
            refused.append({"id": tid, "kind": kind, "reason": str(exc)})
    return {"range": [int(hold_range[0]), int(hold_range[1])], "kinds": kinds, "targets": targets,
            "refused": refused, "listed": listed}


def _lab(name, label):
    return str(name) == str(label) or str(name).endswith(": " + str(label))


def float_scene_conflicts(targets, scene_rows, hold_range, own_track):
    """scene_rows [{"binding", "parent": name|None, "tracks": [{"name", "class", "property_path", "sections":
    [{"range": [s|None, e|None]}]}]}] from the SCENE. A Scene binding is the target's when its own name (component
    bindings: and its parent's name) match like scene_conflicts does (label or '<prefix>: label'). -> (conflicts,
    coexisting): conflicts = a same-class same-property track overlapping the hold (two absolute float sections would
    BLEND; bools are not blendable), or OUR track already present (a leftover); coexisting = the rest, reported."""
    conflicts, coexisting = [], []
    for t in targets:
        for row in scene_rows:
            if t.get("parent"):
                hit = row.get("parent") is not None and _lab(row["parent"], t["parent"]) and \
                    str(row["binding"]) == str(t["binding"])
            else:
                hit = row.get("parent") is None and _lab(row["binding"], t["binding"])
            if not hit:
                continue
            for tr in row["tracks"]:
                tag = "%s|%s/%s/%s" % (t["id"], row["binding"], tr["name"], tr.get("class"))
                if str(tr["name"]) == own_track:
                    conflicts.append("OWN_TRACK_ALREADY_PRESENT|" + tag)
                    continue
                same = str(tr.get("class")) == str(t["track_class"]) and \
                    str(tr.get("property_path") or "") == str(t.get("property_path") or "")
                if same and any(_overlaps(sec["range"], hold_range) for sec in tr.get("sections", [])):
                    conflicts.append(tag)
                else:
                    coexisting.append(tag)
    return conflicts, coexisting


def float_apply_gate(plan):
    """[] = APPLY may proceed. Everything that DRY reports but APPLY must not write through."""
    r = []
    if not plan.get("targets"):
        r.append("NO_TARGETS")
    if plan.get("refused"):
        r.append("REFUSED_TRACKS|%d" % len(plan["refused"]))
    if plan.get("conflicts"):
        r.append("SCENE_CONFLICTS|%d" % len(plan["conflicts"]))
    if plan.get("identity_mismatch"):
        r.append("IDENTITY_MISMATCH|%d" % len(plan["identity_mismatch"]))
    return r


def validate_float_args(a):
    r = []
    mode = a.get("mode")
    if mode not in FLOAT_MODES:
        r.append("MODE")
    try:
        scene = int(a.get("scene"))
    except (TypeError, ValueError):
        scene = None
    if scene not in SCENES:
        r.append("SCENE_NOT_IN_%s" % (SCENES,))
    elif mode in ("APPLY", "REVERT") and a.get("confirm") != "%s %s" % (mode, fnames(scene)["mark"]):
        r.append("CONFIRM")
    if mode == "APPLY" and not str(a.get("decided_by") or "").strip():
        r.append("DECIDED_BY")
    if a.get("completion") not in ("KEEP_STATE", "RESTORE_STATE"):
        r.append("COMPLETION")
    kinds = a.get("hold_kinds", ["float"])
    if not isinstance(kinds, list) or not kinds or any(k not in HOLD_KINDS_ALL for k in kinds):
        r.append("HOLD_KINDS")
    if mode == "PIEPROBE":
        if a.get("probe_phase") not in ("scrub", "read"):
            r.append("PROBE_PHASE")
        elif a.get("probe_phase") == "scrub" and not isinstance(a.get("master_frame"), int):
            r.append("MASTER_FRAME")
    return r


def float_readback_diff(want, got):
    """want {"range", "completion", "value", "kind", "property_path", "display"}; got the same keys plus "n_keys",
    "blend" (float). Float channels store float32 (klara_reveal.py:2991-2992) -> tolerance max(1e-3, 1e-6*|v|)."""
    d = []
    for k in ("range", "completion", "property_path", "display"):
        if (list(want[k]) if k == "range" else want[k]) != (list(got.get(k) or []) if k == "range" else got.get(k)):
            d.append("%s %s != %s" % (k, got.get(k), want[k]))
    if got.get("n_keys", 0) != 0:
        d.append("keys present %s" % got.get("n_keys"))
    g = got.get("value")
    if want["kind"] == "float":
        if g is None or abs(float(g) - float(want["value"])) > max(1e-3, 1e-6 * abs(float(want["value"]))):
            d.append("value %s != %s" % (g, want["value"]))
        if str(got.get("blend") or "").upper() != "ABSOLUTE":
            d.append("blend %s != ABSOLUTE" % got.get("blend"))
    elif g is None or bool(g) != bool(want["value"]):
        d.append("value %s != %s" % (g, want["value"]))
    return d


def revert_order(created):
    """created [{"guid", "child": bool}] -> guids, child (component) bindings before their parents."""
    return [c["guid"] for c in created if c.get("child")] + [c["guid"] for c in created if not c.get("child")]


def _snake(prop):
    """'BlendWeight' -> 'blend_weight', 'Intensity' -> 'intensity', 'bHiddenInGame' -> 'hidden_in_game'."""
    p = re.sub(r"^b(?=[A-Z])", "", str(prop))
    return re.sub(r"(?<!^)(?=[A-Z])", "_", p).lower()


# ----- live (Unreal); every unreal handle is a local --------------------------------------------------------------

def _editor_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _parent_name(b):
    try:
        p = b.get_parent()
        return str(p.get_display_name()) if p is not None and p.is_valid() else None
    except Exception:  # noqa: BLE001
        return None


def _prop(t, getter):
    try:
        return str(getattr(t, getter)())
    except Exception:  # noqa: BLE001
        return None


def _key_val(k):
    v = k.get_value()
    return bool(v) if isinstance(v, bool) else float(v)


def _gc_params(s):
    out = {}
    try:
        p = s.get_editor_property("params")
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)}
    for f in ("geometry_cache_asset", "start_frame_offset", "end_frame_offset", "first_loop_start_frame_offset",
              "play_rate", "reverse"):
        try:
            v = p.get_editor_property(f)
            out[f] = v.get_path_name() if hasattr(v, "get_path_name") else (
                int(v.value) if hasattr(v, "value") else (float(v) if isinstance(v, float) else v))
        except Exception as exc:  # noqa: BLE001
            out[f] = "?%s" % exc
    return out


def _nt_rows(rise, tpf):
    rows = []
    for b in rise.get_bindings():
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieScene3DTransformTrack):
                continue
            cls = t.get_class().get_name()
            secs = []
            for s in t.get_sections():
                st = int(s.get_start_frame()) * tpf if s.has_start_frame() else None
                en = int(s.get_end_frame()) * tpf if s.has_end_frame() else None
                sec = {"range_tick": [st, en], "active": bool(s.is_active()),
                       "completion": _enum(s.get_completion_mode()), "channels": []}
                try:
                    sec["blend"] = _enum(s.get_blend_type())
                except Exception:  # noqa: BLE001 - bools have no blend; a float with an unreadable blend -> UNSET
                    sec["blend"] = None
                if track_kind(cls) == "geometry_cache":
                    sec["params"] = _gc_params(s)
                else:
                    for c in s.get_all_channels():
                        try:
                            ex = _enum(c.get_post_infinity_extrapolation())
                        except Exception:  # noqa: BLE001 - not exposed for bool channels
                            ex = None
                        keys = [[int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value),
                                 _key_val(k)] for k in c.get_keys()]
                        dv = c.get_default() if c.has_default() else None
                        sec["channels"].append({"keys": keys, "post_extrap": ex,
                                                "default": None if dv is None else (bool(dv) if isinstance(dv, bool)
                                                                                     else float(dv))})
                secs.append(sec)
            rows.append({"binding": str(b.get_display_name()), "parent": _parent_name(b), "binding_guid": _gs(b.get_id()),
                         "track_class": cls, "track_name": str(t.get_display_name()),
                         "property_name": _prop(t, "get_property_name"), "property_path": _prop(t, "get_property_path"),
                         "sections": secs})
    return rows


def _scene_nt_rows(seq):
    rows = []
    for b in seq.get_bindings():
        tracks = []
        for t in b.get_tracks():
            tracks.append({"name": str(t.get_display_name()), "class": t.get_class().get_name(),
                           "property_path": _prop(t, "get_property_path"),
                           "sections": [{"range": _sec_range(s)} for s in t.get_sections()]})
        rows.append({"binding": str(b.get_display_name()), "parent": _parent_name(b), "guid": _gs(b.get_id()),
                     "tracks": tracks})
    return rows


def _resolve(t):
    """-> (object, None) or (None, reason). Never stops: DRY reports, APPLY stops via _target_object."""
    label = t["parent"] or t["binding"]
    acts = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if str(a.get_actor_label()) == label]
    if len(acts) != 1:
        return None, "ACTOR_COUNT|%s|%d" % (label, len(acts))
    if not t["parent"]:
        return acts[0], None
    comps = [c for c in acts[0].get_components_by_class(unreal.ActorComponent) if str(c.get_name()) == t["binding"]]
    if len(comps) != 1:
        return None, "COMPONENT_COUNT|%s|%d" % (t["id"], len(comps))
    return comps[0], None


def _target_object(t, run):
    obj, why = _resolve(t)
    if obj is None:
        _stop(run, "RESOLVE|%s|%s" % (t["id"], why))
    return obj


def _located(seq, b, world):
    return sorted(o.get_path_name() for o in seq.locate_bound_objects(b, world))   # prec opening_sequence_apply.py:330


def _float_plan(args, run, scene):
    base = _plan(args, run, scene)                      # read-only; the SAME fold gates and range as the transform hold
    nm = fnames(scene)
    seq, rise = unreal.load_asset(SCENE % scene), unreal.load_asset(RISE % scene)
    rise_tpf = int(round(_rate(rise.get_tick_resolution()) / _rate(rise.get_display_rate())))
    rows = _nt_rows(rise, rise_tpf)
    try:
        plan = plan_nontransform(base["range"], base["rise_end_tick"], rows, args.get("hold_kinds", ["float"]))
    except PlanError as exc:
        _stop(run, "PLAN|%s" % exc)
    world = _editor_world()
    by = {_gs(b.get_id()): b for b in rise.get_bindings()}
    mism = []
    for t in plan["targets"]:
        obj, why = _resolve(t)
        if obj is None:
            mism.append("%s|%s" % (t["id"], why))
            continue
        t["object_path"] = obj.get_path_name()
        t["rise_located"] = _located(rise, by[t["binding_guid"]], world)
        if t["rise_located"] != [t["object_path"]]:
            mism.append("%s|rise=%s|level=%s" % (t["id"], t["rise_located"], t["object_path"]))
    plan["identity_mismatch"] = mism
    plan["conflicts"], plan["coexisting_scene_tracks"] = float_scene_conflicts(
        plan["targets"], _scene_nt_rows(seq), plan["range"], nm["track"])
    plan.update({"scene": scene, "fold": base["fold"], "rise_end_tick": base["rise_end_tick"],
                 "scene_tpf": base["scene_tpf"], "rise_tpf": rise_tpf, "completion": args["completion"],
                 "transform_hold_record_present": os.path.exists(os.path.join(_here(), names(scene)["record"]))})
    plan["apply_gate"] = float_apply_gate(plan)
    return plan


def _our_nt_tracks(b, cls, track, path):
    """OUR track of this class AND property path (two held properties may share one binding)."""
    return [t for t in b.get_tracks() if t.get_class().get_name() == cls and str(t.get_display_name()) == track
            and _prop(t, "get_property_path") == path]


def _read_nt_section(t, s, kind):
    ch = list(s.get_all_channels())
    out = {"range": [s.get_start_frame(), s.get_end_frame()], "completion": _enum(s.get_completion_mode()),
           "property_path": _prop(t, "get_property_path"), "display": str(t.get_display_name()),
           "n_channels": len(ch), "n_keys": sum(len(list(c.get_keys())) for c in ch),
           "value": (ch[0].get_default() if ch and ch[0].has_default() else None)}
    if kind == "float":
        out["blend"] = _enum(s.get_blend_type())
    return out


def _want(t, plan, nm, path):
    return {"range": plan["range"], "completion": plan["completion"], "value": t["value"], "kind": t["kind"],
            "property_path": path, "display": nm["track"]}


def run_apply_float(args, run, plan, scene):
    nm = fnames(scene)
    if plan["apply_gate"]:
        _stop(run, "APPLY_GATE|%s" % plan["apply_gate"])
    here = _here()
    rec_path = os.path.join(here, nm["record"])
    if os.path.exists(rec_path):
        _stop(run, "RECORD_EXISTS (REVERT first)")
    scene_path = SCENE % scene
    census0 = _census()
    if census0:
        _stop(run, "DIRTY_BEFORE|%s" % census0)
    src = _file(scene_path)
    folder = os.path.join(_project(), "Backups", nm["backup_prefix"] + run)
    rec = {"schema": 1, "tool": TOOL, "hold": "FLOAT", "scene": scene, "run": run, "applied": False,
           "decided_by": args["decided_by"], "plan": plan, "backup": folder, "source_sha256": _sha(src),
           "written": datetime.datetime.now().isoformat()}
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
    world = _editor_world()
    gs_before = {_gs(b.get_id()) for b in seq.get_bindings()}
    mode = getattr(unreal.MovieSceneCompletionMode, args["completion"])
    rows, created, created_set, added = [], [], set(), set()      # added: (binding guid, property path) written now
    ns = " NOTHING SAVED; Don't-Save restart"
    for t in plan["targets"]:
        obj = _target_object(t, run)
        if obj.get_path_name() != t["object_path"]:
            _stop(run, "OBJECT_MOVED|%s|%s" % (t["id"], ns))
        b = seq.add_possessable(obj)
        g = _gs(b.get_id())
        if g not in gs_before and g not in created_set:
            created_set.add(g)
            created.append({"guid": g, "child": bool(t["parent"]), "name": str(b.get_display_name())})
            if not t["parent"]:
                b.set_display_name(nm["bind_prefix"] + t["binding"])
        if t["parent"]:
            pg = _gs(b.get_parent().get_id()) if _parent_name(b) is not None else None
            if pg is None:
                _stop(run, "COMPONENT_BINDING_UNPARENTED|%s|%s" % (t["id"], ns))
            if pg not in gs_before and pg not in created_set:
                created_set.add(pg)
                p = b.get_parent()
                p.set_display_name(nm["bind_prefix"] + t["parent"])
                created.append({"guid": pg, "child": False, "name": str(p.get_display_name())})
        loc = _located(seq, b, world)
        if loc != [t["object_path"]]:
            _stop(run, "SCENE_BINDING_RESOLVES|%s|%s|%s" % (t["id"], loc, ns))
        row = {"binding": str(b.get_display_name()), "parent": _parent_name(b), "guid": g,
               "tracks": [{"name": str(x.get_display_name()), "class": x.get_class().get_name(),
                           "property_path": _prop(x, "get_property_path"),
                           "sections": [{"range": _sec_range(s)} for s in x.get_sections()]} for x in b.get_tracks()
                          if not (str(x.get_display_name()) == nm["track"]
                                  and (g, _prop(x, "get_property_path")) in added)]}
        clash, _ = float_scene_conflicts([t], [row], plan["range"], nm["track"])
        if clash:
            _stop(run, "BINDING_CONFLICT|%s|%s" % (clash, ns))
        tr = b.add_track(getattr(unreal, t["track_class"]))
        if t["kind"] in ("float", "bool"):
            tr.set_property_name_and_path(unreal.Name(t["property_name"]), t["property_path"])
        elif str(tr.get_property_name()) in ("None", ""):               # prec klara_reveal.py:3131-3135
            tr.set_property_name_and_path("bHiddenInGame", "bHiddenInGame")
        tr.set_display_name(nm["track"])
        s = tr.add_section()
        s.set_range(int(plan["range"][0]), int(plan["range"][1]))
        s.set_completion_mode(mode)
        if t["kind"] == "float":
            s.set_blend_type(unreal.MovieSceneBlendType.ABSOLUTE)
        ch = list(s.get_all_channels())
        if len(ch) != 1:
            _stop(run, "NEW_CHANNELS|%s|%d|%s" % (t["id"], len(ch), ns))
        ch[0].set_default(float(t["value"]) if t["kind"] == "float" else bool(t["value"]))
        got = _read_nt_section(tr, s, t["kind"])
        d = float_readback_diff(_want(t, plan, nm, t["property_path"] if t["kind"] != "visibility"
                                      else got["property_path"]), got)
        if t["kind"] == "visibility" and got["property_path"] != "bHiddenInGame":
            d.append("visibility property %s" % got["property_path"])
        if d:
            _stop(run, "READBACK|%s|%s|%s" % (t["id"], d, ns))
        added.add((g, got["property_path"]))
        rows.append({"id": t["id"], "guid": g, "track_class": t["track_class"], "kind": t["kind"],
                     "property_path": got["property_path"], "value": t["value"]})
    census1 = _census()
    if census1 != [scene_path]:
        _stop(run, "DIRTY_SET|%s|%s" % (census1, ns))
    if not unreal.EditorAssetLibrary.save_asset(scene_path, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED")
    seq = unreal.load_asset(scene_path)
    by = {_gs(b.get_id()): b for b in seq.get_bindings()}
    tmap = {t["id"]: t for t in plan["targets"]}
    for r in rows:
        b = by.get(r["guid"])
        tracks = _our_nt_tracks(b, r["track_class"], nm["track"], r["property_path"]) if b is not None else []
        if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
            _stop(run, "POST_SAVE_TRACKS|%s" % r["id"])
        got = _read_nt_section(tracks[0], tracks[0].get_sections()[0], r["kind"])
        d = float_readback_diff(_want(tmap[r["id"]], plan, nm, r["property_path"]), got)
        loc = _located(seq, b, _editor_world())
        if loc != [tmap[r["id"]]["object_path"]]:
            d.append("resolves %s" % loc)
        if d:
            _stop(run, "POST_SAVE_READBACK|%s|%s" % (r["id"], d))
    if _census():
        _stop(run, "DIRTY_AFTER|%s" % _census())
    rec.update({"applied": True, "rows": rows, "created_bindings": created,
                "applied_at": datetime.datetime.now().isoformat(), "saved_sha256": _sha(src)})
    tmp = rec_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1, default=str)
    os.replace(tmp, rec_path)
    unreal.log("%s_APPLY_OK|run=%s|range=%s|held=%d|created_bindings=%d|kinds=%s" % (
        nm["mark"], run, plan["range"], len(rows), len(created), plan["kinds"]))


def run_revert_float(args, run, scene):
    nm = fnames(scene)
    rec_path = os.path.join(_here(), nm["record"])
    if not os.path.exists(rec_path):
        _stop(run, "NO_RECORD")
    with open(rec_path, encoding="utf-8") as h:
        rec = json.load(h)
    if rec.get("hold") != "FLOAT" or record_scene(rec) != scene:
        _stop(run, "RECORD_KIND_OR_SCENE|%s|%s" % (rec.get("hold"), rec.get("scene")))
    if not rec.get("applied"):
        _stop(run, "RECORD_NOT_APPLIED (partial APPLY: restore the backup %s with the editor closed)" % rec.get("backup"))
    scene_path = SCENE % scene
    if _census():
        _stop(run, "DIRTY_BEFORE|%s" % _census())
    ns = " NOTHING SAVED; Don't-Save restart"
    seq = unreal.load_asset(scene_path)
    by = {_gs(b.get_id()): b for b in seq.get_bindings()}
    for r in rec["rows"]:
        b = by.get(r["guid"])
        if b is None:
            _stop(run, "BINDING_GONE|%s" % r["id"])
        ours = _our_nt_tracks(b, r["track_class"], nm["track"], r["property_path"])
        if len(ours) != 1:
            _stop(run, "OUR_TRACKS|%s|%d" % (r["id"], len(ours)))
        b.remove_track(ours[0])                                  # returns None (memory): read back
        if _our_nt_tracks(b, r["track_class"], nm["track"], r["property_path"]):
            _stop(run, "REMOVE_TRACK_READBACK|%s|%s" % (r["id"], ns))
    removed = 0
    for g in revert_order(rec.get("created_bindings", [])):
        b = {_gs(x.get_id()): x for x in seq.get_bindings()}.get(g)
        if b is None:
            _stop(run, "CREATED_BINDING_GONE|%s|%s" % (g, ns))
        if list(b.get_tracks()) or list(b.get_child_possessables()):
            _stop(run, "CREATED_BINDING_NOT_EMPTY|%s|%s" % (g, ns))
        b.remove()
        removed += 1
    seq = unreal.load_asset(scene_path)
    gl = {_gs(b.get_id()) for b in seq.get_bindings()}
    left = [g for g in revert_order(rec.get("created_bindings", [])) if g in gl]
    left += [str(b.get_display_name()) for b in seq.get_bindings()
             if any(str(t.get_display_name()) == nm["track"] for t in b.get_tracks())]
    if left:
        _stop(run, "REVERT_LEFTOVERS|%s|%s" % (left, ns))
    if _census() != [scene_path]:
        _stop(run, "DIRTY_SET|%s|%s" % (_census(), ns))
    if not unreal.EditorAssetLibrary.save_asset(scene_path, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED")
    if _census():
        _stop(run, "DIRTY_AFTER|%s" % _census())
    os.replace(rec_path, rec_path + ".reverted-" + run)
    unreal.log("%s_REVERT_OK|run=%s|tracks=%d|bindings=%d" % (nm["mark"], run, len(rec["rows"]), removed))


def run_pieprobe(args, run, scene):
    """READ-ONLY, inside the conductor's OWN PIE (never starts or ends it; no asset/level write). Two calls, because a
    GeometryCache frame decodes asynchronously (memory ue58-geometrycache-sequencer-traps): phase "scrub" pauses and
    scrubs the PIE transport to master_frame (prec s3_white_probe.py:27-38); phase "read" (a LATER call) reads every
    rise GeometryCache actor's component state and every float target's live value."""
    nm = fnames(scene)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        _stop(run, "NO_PIE (start PIE first; this probe never starts or ends it)")
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    if len(roots) != 1:
        _stop(run, "SHOW_ROOTS|%d" % len(roots))
    root = roots[0]
    if args["probe_phase"] == "scrub":
        root.sequence_player.pause()
        res = root.transport.scrub_to_master_frame(unreal.FrameNumber(int(args["master_frame"])))
        if res != unreal.InfinityTransportResult.SUCCEEDED:
            _stop(run, "SCRUB|%s" % res)
        landed = int(root.transport.get_current_master_frame().value)
        if landed != int(args["master_frame"]):
            _stop(run, "SCRUB_LANDED|%d" % landed)
        unreal.log("%s_PIEPROBE_OK|run=%s|phase=scrub|master=%d" % (nm["mark"], run, landed))
        return
    rise = unreal.load_asset(RISE % scene)
    rise_tpf = int(round(_rate(rise.get_tick_resolution()) / _rate(rise.get_display_rate())))
    rows = _nt_rows(rise, rise_tpf)
    master = int(root.transport.get_current_master_frame().value)
    out = {"run": run, "scene": scene, "master_frame": master, "args": args, "gc": [], "float": []}
    if args.get("segment_start_master") is not None and args.get("ticks_per_frame"):
        out["scene_frame"] = round((master - int(args["segment_start_master"])) / float(args["ticks_per_frame"]), 2)
    by_label = {}
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        by_label.setdefault(str(a.get_actor_label()), []).append(a)
    for r in rows:
        label = r["parent"] or r["binding"]
        acts = by_label.get(label, [])
        kind = track_kind(r["track_class"])
        if kind == "geometry_cache":
            row = {"label": label, "actors": len(acts), "rise_sections": [{k: s.get(k) for k in
                                                                         ("range_tick", "completion", "params")}
                                                                        for s in r["sections"]]}
            if len(acts) == 1:
                c = acts[0].get_component_by_class(unreal.GeometryCacheComponent)
                o, e = acts[0].get_actor_bounds(False)
                for k, f in (("anim_time", lambda: float(c.get_animation_time())),
                             ("elapsed", lambda: float(c.get_elapsed_time())),
                             ("duration", lambda: float(c.get_duration())), ("playing", lambda: bool(c.is_playing())),
                             ("looping", lambda: bool(c.is_looping())),
                             ("running", lambda: bool(c.get_editor_property("running"))),
                             ("manual_tick", lambda: bool(c.get_editor_property("manual_tick")))):
                    try:
                        row[k] = f()
                    except Exception as exc:  # noqa: BLE001 - reported, never guessed
                        row[k] = "?%s" % exc
                row.update({"bounds_origin": [float(o.x), float(o.y), float(o.z)],
                            "bounds_extent": [float(e.x), float(e.y), float(e.z)]})
                row["at_last_sample"] = (isinstance(row["duration"], float) and isinstance(row["anim_time"], float)
                                         and row["duration"] > 0 and row["anim_time"] >= row["duration"] - 0.1)
            out["gc"].append(row)
        elif kind == "float" and len(acts) == 1:
            obj = acts[0]
            if r["parent"]:
                cs = [c for c in obj.get_components_by_class(unreal.ActorComponent) if str(c.get_name()) == r["binding"]]
                obj = cs[0] if len(cs) == 1 else None
            val = None
            if obj is not None and r["property_name"]:
                try:
                    val = float(obj.get_editor_property(_snake(r["property_name"])))
                except Exception as exc:  # noqa: BLE001
                    val = "?%s" % exc
            out["float"].append({"id": target_id(r), "value": val})
    path = os.path.join(_here(), "%spieprobe_%s.json" % (nm["out_prefix"], run))
    with open(path, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1, default=str)
    unreal.log("%s_PIEPROBE_OK|run=%s|phase=read|master=%d|scene_frame=%s|gc=%s|%s" % (
        nm["mark"], run, master, out.get("scene_frame"),
        [(g["label"], g.get("anim_time"), g.get("duration"), g.get("manual_tick"))
         for g in out["gc"]], path))


def main_float(args):
    try:
        scene = int(args.get("scene"))
    except (TypeError, ValueError):
        scene = None
    _MARK[0] = fnames(scene)["mark"] if scene in SCENES else "HANGARFLOATHOLD"
    run = args.get("run_id") or _MARK[0] + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bad = validate_float_args(args)
    if bad:
        _stop(run, "ARGS|%s" % bad)
    nm = fnames(scene)
    if args["mode"] == "PIEPROBE":
        run_pieprobe(args, run, scene)
        return
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if args["mode"] in ("APPLY", "REVERT"):
        if ed.get_game_world() is not None:
            _stop(run, "PIE_RUNNING (edits are editor-world; never end PIE from here)")
        cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
        if cur is not None:
            _stop(run, "SEQUENCER_OPEN|%s" % cur.get_path_name())
    if args["mode"] == "REVERT":
        run_revert_float(args, run, scene)
        return
    out = {"run": run, "hold": "FLOAT", "plan": _float_plan(args, run, scene)}
    path = os.path.join(_here(), "%s%s_%s.json" % (nm["out_prefix"], args["mode"].lower(), run))
    with open(path, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1, default=str)
    p = out["plan"]
    if args["mode"] == "APPLY":
        run_apply_float(args, run, p, scene)
        return
    unreal.log("%s_DRY_OK|run=%s|range=%s|held=%d|refused=%d|listed=%d|conflicts=%d|identity_mismatch=%d|gate=%s|%s" % (
        nm["mark"], run, p["range"], len(p["targets"]), len(p["refused"]), len(p["listed"]), len(p["conflicts"]),
        len(p["identity_mismatch"]), p["apply_gate"], path))
    for t in p["targets"]:                                     # DRY prints every held track and value
        unreal.log("%s_DRY_TARGET|run=%s|%s|%s|value=%r|from=%s" % (nm["mark"], run, t["id"], t["kind"], t["value"],
                                                                      t["source"]))
    for t in p["refused"]:
        unreal.log_warning("%s_DRY_REFUSED|run=%s|%s|%s" % (nm["mark"], run, t["id"], t["reason"]))
    for t in p["listed"]:
        unreal.log("%s_DRY_LISTED|run=%s|%s|%s|%s" % (nm["mark"], run, t["id"], t["kind"], t["meaning"]))


def main_transform(args):
    try:
        scene = int(args.get("scene"))
    except (TypeError, ValueError):
        scene = None
    _MARK[0] = names(scene)["mark"] if scene in SCENES else "HANGARHOLD"
    run = args.get("run_id") or _MARK[0] + "-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|%s" % bad)
    nm = names(scene)
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if args["mode"] in ("APPLY", "REVERT"):
        if ed.get_game_world() is not None:
            _stop(run, "PIE_RUNNING (edits are editor-world; never end PIE from here)")
        cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
        if cur is not None:
            _stop(run, "SEQUENCER_OPEN|%s" % cur.get_path_name())
    if args["mode"] == "REVERT":
        run_revert(args, run, scene)
        return
    sv = survey()
    out = {"run": run, "survey": sv}
    if args["mode"] != "SURVEY":
        out["plan"] = _plan(args, run, scene)
    path = os.path.join(_here(), "%s%s_%s.json" % (nm["out_prefix"], args["mode"].lower(), run))
    with open(path, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1, default=str)
    short = ["S%s:%s" % (r["scene"], r.get("uncovered_s")) for r in sv if r.get("verdict") == "SHORT"]
    if args["mode"] == "APPLY":
        run_apply(args, run, out["plan"], scene)
        return
    unreal.log("%s_%s_OK|run=%s|short=%s|plan=%s|%s" % (
        nm["mark"], args["mode"], run, short,
        None if "plan" not in out else {"range": out["plan"]["range"],
                                        "movers": [t["binding"] for t in out["plan"]["targets"]]}, path))


def main(args):
    """Dispatch. "hold" absent or "TRANSFORM" -> main_transform (the 4e1e703 main, verbatim; harness-proven).
    "FLOAT" -> main_float (non-transform holds, separate record)."""
    if str(args.get("hold") or "TRANSFORM").upper() == "FLOAT":
        main_float(args)
        return
    main_transform(args)


if unreal is not None and "S4HOLD_ARGS" in globals():
    main(globals()["S4HOLD_ARGS"])
