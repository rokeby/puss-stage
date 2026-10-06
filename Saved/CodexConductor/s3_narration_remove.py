"""S3 NARRATION REMOVE: take the "Narration (stand-in)" track OUT of LS_DevScene_03 only, recording its exact state so
REVERT can rebuild it. 6 Oct, offline-written, NEVER RUN IN UNREAL.

Gary 6 Oct ~17:10 (conductor questionnaire, his words): S3 narration "Remove it for now" - he wants to walk through the
S3 beats before anything plays there. S1/S2 and the SoundWave SW_S3_Shore_Narration_Standin are NOT touched.

Why not the 5 Oct tool's REVERT: scene_narration_standin.py REVERT walks every Scene in its record (S1-S3) and S1's row is
stale since s1_narration_after_voices.py moved S1's section (record s1_narration_after_voices_record.json, frames
104-979 -> 5216-6091) [meas both records]. Its drift gate (scene_narration_standin.py:339-349, 856-858) would refuse on
S1 anyway; after THIS tool runs it also refuses on S3 (our track gone) - it fails safe, it cannot double-remove.

Tiers per claim: [decl] header/source we can read, [prec] in-repo precedent (cited), [meas] earlier read-back record,
[inf] inferred (why stated).
  * Track list / remove / add: MovieSceneSequenceExtensions.h:49,79,89 [decl]. remove_track's return value LIES
    [memory puss-python-api-gotchas] - judged by re-listing only.
  * Track display name / sorting order / colour tint: MovieSceneTrackExtensions.h:33,42,99,108,117,126 [decl].
  * Section range (display frames): MovieSceneSectionExtensions.h:36-81,145 [decl]. Row/active/locked/pre-post roll/
    overlap priority/colour/completion mode: MovieSceneSection.h:424-628 UFUNCTIONs [decl]. Blend type is NOT recorded
    [inf: GetBlendType returns an optional struct whose Python str carries an address, so it cannot be compared; the
    5 Oct tool never set it, so the default is expected - the .uasset backup covers it]. Audio fields:
    MovieSceneAudioSection.h:38-170 (sound, start offset, looping, play-until-finished, subtitles, attenuation) [decl].
  * Expected live shape from the 5 Oct record S3 row: one section 100-924 @24 fps, sound
    /Game/InfinityStage/Audio/ScenesAudio/Narration/SW_S3_Shore_Narration_Standin [meas
    scene_narration_standin_record.json, run NARR-20261005-143408]. A different range is a WARNING (someone moved it),
    a different sound or shape is a REFUSAL.
  * Exactness: every readable field is recorded; REVERT re-creates the track, sets every field, and requires the full
    re-read state to equal the recorded one (root track ORDER excepted - AddTrack appends; reported). Channel KEYS on the
    volume/pitch channels are recorded but NOT re-created [inf: interpolation/tangents are not round-trippable through
    the scripting key API]; REVERT refuses if any were recorded and points at the .uasset backup instead. The 5 Oct tool
    created the section with defaults (no keys) [prec scene_narration_standin.py:474-488], so none are expected.

Args s3_narration_remove_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> S3NARR", "decided_by": ...}.
Guards: no PIE/SIE; no Sequencer open on LS_DevScene_03, on the Master, or on any sequence nesting S3 (another open
sequence is a warning - the census gate still catches an evaluating Sequencer dirtying the map); census CLEAN (no dirty
content or map package) before; after the edit the ONLY dirty package must be LS_DevScene_03; saves only it; reads back
from a fresh load. APPLY: record (create-only, fsync) + .uasset backup BEFORE the edit. REVERT: drift gate (S3 must
still be exactly the recorded after-state), backup, rebuild, exact read-back.
Markers: S3NARR_DRY_OK / S3NARR_APPLY_OK / S3NARR_REVERT_OK |run=.., or S3NARR_STOPPED|run=..|reason=..
Never: Save All, level save, reload, open or scrub Sequencer, load or touch the Master, end PIE; no unreal objects in
module globals. Importing without `unreal` runs nothing (test_s3_narration_and_scene_audio.py).
"""
import datetime
import hashlib
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "s3_narration_remove"
SEQ = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"           # extend_scene_playback.py:43
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"   # scene_narration_standin.py:69
TRACK_NAME = "Narration (stand-in)"
TRACK_CLASS = "MovieSceneAudioTrack"
EXPECT_SOUND = "/Game/InfinityStage/Audio/ScenesAudio/Narration/SW_S3_Shore_Narration_Standin"
EXPECT_RANGE = [100, 924]          # [meas] scene_narration_standin_record.json scenes.3.added
RECORD_NAME = "s3_narration_remove_record.json"
ARGS_NAME = "s3_narration_remove_args.json"
CONFIRM_WORD = "S3NARR"
UNREADABLE = "<unreadable>"
# Fields compared for exactness. "index" (position in the root track list) is reported, not compared: AddTrack appends.
ORDER_ONLY_FIELDS = ("index",)


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure
# =====================================================================================================================

def state_key(state, drop=ORDER_ONLY_FIELDS):
    """Canonical JSON of a track state without order-only fields."""
    return json.dumps({k: v for k, v in state.items() if k not in drop}, sort_keys=True)


def list_keys(states):
    return sorted(state_key(s) for s in states)


def gates(state):
    """Refusals from editor state: mode, confirm, pie, open_sequence(s), census, record_exists, record_applied,
    decided_by."""
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % state.get("mode"))
    want = "%s %s" % (mode, CONFIRM_WORD)
    if state.get("confirm") != want:
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), want))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_blocks"):
        r.append("SEQUENCER_OPEN_ON_TARGET: %s (close it: an open Sequencer evaluates and dirties)"
                 % state["sequencer_blocks"])
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode in ("DRY", "APPLY") and state.get("record_exists"):
        r.append("RECORD_EXISTS: already removed (REVERT first, or archive a stale record by hand)")
    if mode == "APPLY" and not str(state.get("decided_by") or "").strip():
        r.append("NOT_DECIDED: args decided_by is empty")
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


def plan_remove(states, expect_sound=EXPECT_SOUND, expect_range=EXPECT_RANGE):
    """states: every root track's state (list order = get_tracks order). Returns (target_state, refusals, warnings)."""
    refusals, warnings = [], []
    named = [s for s in states if s.get("name") == TRACK_NAME]
    if len(named) != 1:
        refusals.append("NARRATION_TRACK_COUNT: %d tracks named %r" % (len(named), TRACK_NAME))
        return None, refusals, warnings
    t = named[0]
    if t.get("cls") != TRACK_CLASS:
        refusals.append("NARRATION_TRACK_CLASS: %r" % t.get("cls"))
    secs = t.get("sections") or []
    if len(secs) != 1:
        refusals.append("NARRATION_SECTION_COUNT: %d" % len(secs))
        return t, refusals, warnings
    s = secs[0]
    if s.get("sound") != expect_sound:
        refusals.append("NARRATION_SOUND: %r, want %r" % (s.get("sound"), expect_sound))
    if [s.get("start"), s.get("end")] != list(expect_range):
        warnings.append("NARRATION_RANGE_MOVED: %s, 5 Oct record had %s (removed as found; recorded exactly)"
                        % ([s.get("start"), s.get("end")], list(expect_range)))
    unread = sorted(k for k, v in s.items() if v == UNREADABLE) + \
        sorted("track." + k for k, v in t.items() if v == UNREADABLE)
    if unread:
        warnings.append("FIELDS_UNREADABLE: %s (recorded as unreadable; the .uasset backup is the exact restore)" % unread)
    if any(c.get("keys") for c in _chan_list(s)):
        warnings.append("CHANNEL_KEYS_PRESENT: REVERT will refuse and point at the .uasset backup")
    if s.get("looping") is True or s.get("play_until_finished") is True:
        warnings.append("SECTION_FLAGS: looping=%r play_until_finished=%r" % (s.get("looping"), s.get("play_until_finished")))
    return t, refusals, warnings


def _chan_list(section_state):
    ch = section_state.get("channels")
    return ch if isinstance(ch, list) else []


def expected_after(states, target):
    """The root track list after removing target exactly once."""
    out, removed = [], False
    tk = state_key(target)
    for s in states:
        if not removed and state_key(s) == tk:
            removed = True
            continue
        out.append(s)
    return out


def revert_supported(target):
    """None, or a reason REVERT cannot rebuild the track exactly via the API."""
    for s in target.get("sections") or []:
        if s.get("channels") == UNREADABLE:
            return "SECTION_CHANNELS_UNREADABLE: restore from the .uasset backup instead"
        if any(c.get("keys") for c in _chan_list(s)):
            return "CHANNEL_KEYS_RECORDED: restore %s from the .uasset backup instead" % SEQ
        for k, v in s.items():
            if v == UNREADABLE:
                return "SECTION_FIELD_UNREADABLE_%s: restore from the .uasset backup instead" % k
    return None


def remove_exact(seq, record):
    """seq: adapter with list_states(), remove_named(name). Returns failures (empty = exact)."""
    before = seq.list_states()
    if list_keys(before) != list_keys(record["before"]):
        return ["STATE_CHANGED_SINCE_PLAN"]
    seq.remove_named(TRACK_NAME)
    after = seq.list_states()
    if list_keys(after) != list_keys(record["after"]):
        return ["REMOVE_NOT_EXACT: %d tracks, want %d" % (len(after), len(record["after"]))]
    return []


def restore_exact(seq, record):
    """Drift gate, then rebuild the recorded track. Returns (failures, warnings)."""
    live = seq.list_states()
    if list_keys(live) != list_keys(record["after"]):
        return ["STATE_DRIFTED_SINCE_APPLY: S3 root tracks are not the recorded after-state (restore from %s)"
                % record.get("backup")], []
    why = revert_supported(record["target"])
    if why:
        return [why], []
    seq.restore(record["target"])
    final = seq.list_states()
    failures, warnings = [], []
    if list_keys(final) != list_keys(record["before"]):
        failures.append("RESTORE_NOT_EXACT: %s" % sorted(set(list_keys(final)) ^ set(list_keys(record["before"])))[:2])
    mine = [s for s in final if s.get("name") == TRACK_NAME]
    if len(mine) == 1 and mine[0].get("index") != record["target"].get("index"):
        warnings.append("TRACK_ORDER: restored at root index %s, was %s (AddTrack appends; UI order follows "
                        "sorting_order, which is restored)" % (mine[0].get("index"), record["target"].get("index")))
    return failures, warnings


def census_gate(census, expected_content):
    out = []
    got, want = sorted(census.get("content") or []), sorted(expected_content)
    if got != want:
        out.append("TOUCHED_CENSUS: extra=%s missing=%s" % (sorted(set(got) - set(want)), sorted(set(want) - set(got))))
    if census.get("maps"):
        out.append("MAP_DIRTY: %s" % census["maps"])
    return out


def write_record_exclusive(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):
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
# Live (Unreal) side. Every unreal handle is a local or an adapter attribute.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    if unreal is not None:
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.dirname(os.path.dirname(_here()))


def _stop(run, reason):
    unreal.log_error("S3NARR_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():   # scene_narration_standin.py:423-427 [prec]
    return {"content": sorted(p.get_path_name().split(".")[0]
                              for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0]
                           for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _content_file(path):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _try(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001 - recorded as unreadable, never guessed
        return UNREADABLE


def _color(c):
    return [int(c.r), int(c.g), int(c.b), int(c.a)]


def _mk_color(rgba):
    """Keywords, never positional: FColor's member order is platform-dependent (BGRA on Windows) [decl Color.h]."""
    r, g, b, a = [int(x) for x in rgba]
    return unreal.Color(r=r, g=g, b=b, a=a)


def _enum(v):
    return str(getattr(v, "name", v))


class _LiveSeq(object):
    def __init__(self, seq):
        self.seq = seq

    @staticmethod
    def _channels(s):
        out = []
        for ch in s.get_all_channels():
            name = str(ch.channel_name) if hasattr(ch, "channel_name") else str(ch.get_name())
            row = {"name": name.split("_")[0] if name[-1:].isdigit() else name,
                   "has_default": _try(lambda: bool(ch.has_default())),
                   "default": _try(lambda: float(ch.get_default()) if ch.has_default() else None),
                   "keys": _try(lambda: [[int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
                                               .frame_number.value), float(k.get_value())] for k in ch.get_keys()])}
            out.append(row)
        return sorted(out, key=lambda r: r["name"])

    def _section_state(self, s):
        st = {"start": int(s.get_start_frame()) if s.has_start_frame() else None,
              "end": int(s.get_end_frame()) if s.has_end_frame() else None,
              "cls": s.get_class().get_name(),
              "row_index": _try(lambda: int(s.get_row_index())),
              "is_active": _try(lambda: bool(s.is_active())),
              "is_locked": _try(lambda: bool(s.is_locked())),
              "pre_roll": _try(lambda: int(s.get_pre_roll_frames())),
              "post_roll": _try(lambda: int(s.get_post_roll_frames())),
              "overlap_priority": _try(lambda: int(s.get_overlap_priority())),
              "completion_mode": _try(lambda: _enum(s.get_completion_mode())),
              "color_tint": _try(lambda: _color(s.get_color_tint())),
              "channels": _try(lambda: self._channels(s))}
        if isinstance(s, unreal.MovieSceneAudioSection):
            st.update({"sound": _path(s.get_sound()),
                       "start_offset": _try(lambda: int(s.get_start_offset().value)),
                       "looping": _try(lambda: bool(s.get_looping())),
                       "play_until_finished": _try(lambda: bool(s.get_play_until_finished())),
                       "suppress_subtitles": _try(lambda: bool(s.get_suppress_subtitles())),
                       "override_attenuation": _try(lambda: bool(s.get_override_attenuation())),
                       "attenuation": _try(lambda: _path(s.get_attenuation_settings()))})
        return st

    def _rows(self):
        rows = []
        for i, t in enumerate(self.seq.get_tracks()):
            rows.append((t, {"index": i, "cls": t.get_class().get_name(), "name": str(t.get_display_name()),
                             "sorting_order": _try(lambda: int(t.get_sorting_order())),
                             "color_tint": _try(lambda: _color(t.get_color_tint())),
                             "sections": [self._section_state(s) for s in t.get_sections()]}))
        return rows

    def list_states(self):
        return [r[1] for r in self._rows()]

    def remove_named(self, name):
        hits = [t for t, row in self._rows() if row["name"] == name]
        if len(hits) != 1:
            raise RuntimeError("REMOVE_TARGET_COUNT: %d" % len(hits))
        self.seq.remove_track(hits[0])      # return value ignored on purpose; the caller re-lists

    def restore(self, target):
        track = self.seq.add_track(unreal.MovieSceneAudioTrack)
        if track is None:
            raise RuntimeError("ADD_TRACK_NONE")
        track.set_display_name(target["name"])
        if target.get("sorting_order") != UNREADABLE:
            track.set_sorting_order(int(target["sorting_order"]))
        if target.get("color_tint") != UNREADABLE:
            track.set_color_tint(_mk_color(target["color_tint"]))
        for st in target["sections"]:
            s = track.add_section()
            if s is None:
                raise RuntimeError("ADD_SECTION_NONE")
            sound = unreal.load_asset(st["sound"]) if st.get("sound") else None
            if st.get("sound") and not isinstance(sound, unreal.SoundBase):
                raise RuntimeError("SOUND_NOT_LOADED: %s" % st["sound"])
            if sound is not None:
                s.set_sound(sound)
            s.set_range(int(st["start"]), int(st["end"]))
            s.set_row_index(int(st["row_index"]))
            s.set_start_offset(unreal.FrameNumber(int(st["start_offset"])))
            s.set_looping(bool(st["looping"]))
            s.set_play_until_finished(bool(st["play_until_finished"]))
            s.set_suppress_subtitles(bool(st["suppress_subtitles"]))
            s.set_override_attenuation(bool(st["override_attenuation"]))
            if st.get("attenuation"):
                s.set_attenuation_settings(unreal.load_asset(st["attenuation"]))
            s.set_pre_roll_frames(int(st["pre_roll"]))
            s.set_post_roll_frames(int(st["post_roll"]))
            s.set_overlap_priority(int(st["overlap_priority"]))
            mode = getattr(unreal.MovieSceneCompletionMode, str(st["completion_mode"]), None)
            if mode is None:
                raise RuntimeError("COMPLETION_MODE_UNKNOWN: %r" % st["completion_mode"])
            s.set_completion_mode(mode)
            s.set_color_tint(_mk_color(st["color_tint"]))
            for ch in s.get_all_channels():
                name = str(ch.channel_name) if hasattr(ch, "channel_name") else str(ch.get_name())
                name = name.split("_")[0] if name[-1:].isdigit() else name
                rec = [c for c in st["channels"] if c["name"] == name]
                if len(rec) == 1 and rec[0]["has_default"] is True and rec[0]["default"] is not None:
                    ch.set_default(float(rec[0]["default"]))
            s.set_is_active(bool(st["is_active"]))
            s.set_is_locked(bool(st["is_locked"]))       # last: a locked section refuses later edits in the UI


def _sequencer_blocks(seq_path):
    """Open Sequencer on S3, the Master, or a sequence nesting S3 (depth 3) -> blocking text; other -> warning."""
    cur = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    if cur is None:
        return None, None
    cp = _path(cur)
    if cp in (seq_path, MASTER):
        return cp, None

    def nests(s, depth):
        if s is None or depth > 3:
            return False
        for t in s.get_tracks():
            if not isinstance(t, unreal.MovieSceneSubTrack):
                continue
            for sec in t.get_sections():
                child = sec.get_sequence()
                if _path(child) == seq_path or nests(child, depth + 1):
                    return True
        return False
    if nests(cur, 0):
        return "%s (nests %s)" % (cp, seq_path), None
    return None, "SEQUENCER_OPEN_OTHER: %s (not S3; the census gate still guards the map)" % cp


def _backup(run, suffix):
    folder = os.path.join(_project(), "Backups", "PreS3NarrationRemove-%s%s" % (run, suffix))
    os.makedirs(folder, exist_ok=False)
    src = _content_file(SEQ)
    if not os.path.isfile(src):
        _stop(run, "BACKUP_SOURCE_MISSING|" + src)
    dst = os.path.join(folder, os.path.basename(src))
    shutil.copy2(src, dst)
    digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
    if digest[0] != digest[1]:
        _stop(run, "BACKUP_HASH_MISMATCH|" + src)
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": [{"asset": SEQ, "source": src, "backup": dst, "sha256": digest[1]}]}, handle,
                  indent=1)
    return folder


def _save_and_reread(run, want_states):
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|%s" % SEQ)
    live = _LiveSeq(unreal.load_asset(SEQ)).list_states()
    bad = []
    if list_keys(live) != list_keys(want_states):
        bad.append("READBACK_TRACKS")
    if _census() != {"content": [], "maps": []}:
        bad.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    return live, bad


def main():
    g = globals()
    args = g.get("S3NARR_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("S3NARR-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    record_path = os.path.join(_here(), RECORD_NAME)
    applied = os.path.exists(record_path) and bool(load_record(record_path).get("applied"))
    block, seq_warn = _sequencer_blocks(SEQ)
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_blocks": block, "census": _census(), "record_exists": os.path.exists(record_path),
             "record_applied": applied, "decided_by": args.get("decided_by")}
    early = gates(state)
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    seq = unreal.load_asset(SEQ)
    if seq is None:
        _stop(run, "SEQ_MISSING")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "LOADING_DIRTIED|" + json.dumps(_census()))
    adapter = _LiveSeq(seq)
    if mode == "REVERT":
        record = load_record(record_path)
        if record.get("sequence") != SEQ or not record.get("applied"):
            _stop(run, "REVERT_RECORD_CONTEXT")
        why = revert_supported(record["target"])
        if why:
            _stop(run, "REVERT_UNSUPPORTED|" + why)
        if list_keys(adapter.list_states()) != list_keys(record["after"]):
            _stop(run, "STATE_DRIFTED_SINCE_APPLY|restore from %s instead" % record["backup"])
        backup = _backup(run, "-revert")
        pb = [int(seq.get_playback_start()), int(seq.get_playback_end())]
        seq.modify()
        try:
            fails, warns = restore_exact(adapter, record)
        except Exception as exc:   # noqa: BLE001
            fails, warns = ["RESTORE_RAISED: %r" % exc], []
        if [int(seq.get_playback_start()), int(seq.get_playback_end())] != pb:
            fails.append("PLAYBACK_RANGE_CHANGED")
        fails += census_gate(_census(), [SEQ])
        if fails:
            _stop(run, "REVERT_GATES|%r|NOTHING SAVED; Don't-Save restart, then restore %s" % (fails[:6], record["backup"]))
        _live, bad = _save_and_reread(run, record["before"])
        if bad:
            _stop(run, "REVERT_READBACK|%r|restore from %s" % (bad, record["backup"]))
        archived = record_path + ".reverted-" + run
        os.rename(record_path, archived)
        for w in warns:
            unreal.log("S3NARR_WARNING|run=%s|%s" % (run, w))
        unreal.log("S3NARR_REVERT_OK|run=%s|restored=%s|frames=%d-%d|saved=LS_DevScene_03|backup=%s|record=%s"
                   % (run, TRACK_NAME, record["target"]["sections"][0]["start"], record["target"]["sections"][0]["end"],
                      backup, archived))
        return
    before = adapter.list_states()
    target, refusals, warnings = plan_remove(before, args.get("expect_sound") or EXPECT_SOUND,
                                             args.get("expect_range") or EXPECT_RANGE)
    if seq_warn:
        warnings.append(seq_warn)
    for w in warnings:
        unreal.log("S3NARR_WARNING|run=%s|%s" % (run, w))
    for r in refusals:
        unreal.log_warning("S3NARR_REFUSAL|run=%s|%s" % (run, r))
    if mode == "DRY":
        if _census() != {"content": [], "maps": []}:
            _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
        unreal.log("S3NARR_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|target=%s|revert_supported=%s"
                   % (run, int(not refusals), len(refusals), len(warnings),
                      json.dumps(target, sort_keys=True) if target else None,
                      "yes" if target and not revert_supported(target) else "no"))
        return
    if refusals:
        _stop(run, "PLAN_REFUSED|" + " || ".join(refusals))
    after_want = expected_after(before, target)
    backup = _backup(run, "")
    record = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "sequence": SEQ, "backup": backup,
              "decided_by": args.get("decided_by"), "applied": False, "target": target, "before": before,
              "after": after_want, "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())],
              "warnings": warnings, "revert_supported": revert_supported(target) or "yes",
              "written": datetime.datetime.now().isoformat(timespec="seconds"),
              "note": "S1/S2 and SW_S3_Shore_Narration_Standin untouched; the 5 Oct record is left as is (stale)."}
    write_record_exclusive(record_path, record)
    seq.modify()
    try:
        fails = remove_exact(adapter, record)
    except Exception as exc:   # noqa: BLE001
        fails = ["REMOVE_RAISED: %r" % exc]
    if [int(seq.get_playback_start()), int(seq.get_playback_end())] != record["playback"]:
        fails.append("PLAYBACK_RANGE_CHANGED")
    fails += census_gate(_census(), [SEQ])
    if fails:
        restored = "not_needed"
        if not any(st.get("name") == TRACK_NAME for st in adapter.list_states()):
            try:                                            # in memory only, so a later stray save keeps the track
                adapter.restore(target)
                restored = "exact" if list_keys(adapter.list_states()) == list_keys(before) else "INEXACT"
            except Exception as exc:   # noqa: BLE001
                restored = "RAISED %r" % exc
        update_record(record_path, dict(record, failed=fails, in_memory_restore=restored))
        os.rename(record_path, record_path + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|in_memory_restore=%s|NOTHING SAVED; Don't-Save restart (backup %s)"
              % (fails[:6], restored, backup))
    record["applied"] = True          # flips before the save: a failed save leaves a record REVERT can act on
    update_record(record_path, record)
    _live, bad = _save_and_reread(run, after_want)
    if bad:
        record["post_save_readback_failed"] = bad
        update_record(record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|record kept (REVERT, or restore %s)" % (bad, backup))
    sec = target["sections"][0]
    unreal.log("S3NARR_APPLY_OK|run=%s|removed=%s|was_frames=%d-%d|sound=%s|saved=LS_DevScene_03|backup=%s|record=%s"
               % (run, TRACK_NAME, sec["start"], sec["end"], sec.get("sound"), backup, record_path))


if unreal is not None:
    main()
