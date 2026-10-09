"""Guarded Cue Book GO-marker sync for an Unreal editor slot. THIS FILE IS NOT RUN OFFLINE.

Review location: Tools/CueBook/unreal/go_markers_sync.py. After review, copy it to
Saved/CodexCueing/go_markers_sync.py and execute it with ExecuteProjectPythonFile. It reads
Saved/CodexCueing/go_markers_sync_args.json.

Modes and exact confirms:
  DRY     no confirm; plans ADD / RELABEL / MOVE / UNCHANGED and lists orphan GO markers.
  APPLY   confirm="APPLY GO MARKERS"; MOVEs are allowed (Gary, 9 Oct); confirm_moves=false refuses them.
  REVERT  confirm="REVERT GO MARKERS" and source_run_id=<APPLY run>.

APPLY/REVERT require the expected world, no PIE, closed Sequencer, and an empty exact dirty-package census. Before
the first marker write they create an exclusive record and Backups/PreGoMarkerSync-<run> containing every sequence
that may be written plus the Master. Only those named sequence packages are saved. Marker operations use
find_marked_frame_by_label and tick-resolution *_from_sequence / *_to_sequence calls; get_marked_frames() is a
sorted copy whose index is not a safe delete index [measured precedent: Saved/CodexConductor/s3_markers_fix.py:50-56].

The timing guard fingerprints every root/binding track (class, display name, row/sort metadata), section (range,
row, sub-sequence, time scale), and channel key (tick time + value). It runs before writes, after writes, and after
save; floats compare at 1e-4. Marked frames are deliberately excluded. Any timing difference restores every backed
up .uasset on disk and stops with GO_MARKER_SYNC_STOPPED|reason=TIMING_CHANGED. Do not Save All after a stop; restart
with Don't Save so the restored disk packages replace any loaded dirty objects.

The segment contract is declaration-proven: Scene/Sequence cues own Scene.Sequence
[Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:817-822,936-959], while Passage settings own
Choreography [same file:963-980,1006-1007]. This tool never creates bindings/tracks, evaluates channels, or touches
visibility, so rule-9 possessable, evaluate_keys-range, and bHidden traps are outside its write surface.
"""
import collections
import copy
import datetime
import hashlib
import json
import math
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness imports the pure planner/guard.
    unreal = None


TOOL = "go_markers_sync"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ARGS_NAME = "go_markers_sync_args.json"
FLOAT_TOLERANCE = 1e-4
GO_RE = re.compile(r"^\s*GO\s+([0-9]+(?:\.[0-9]+)?)(?:\s+(HOLD|PASS)\b)?(?:\s+(.*))?$")
GO_FIELD_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)(?:\s+(HOLD|PASS|BREATH))?$")
TIME_FIELD_RE = re.compile(r"^[+]?(?:\d+(?:\.\d*)?|\.\d+)$")
MARKER_FIELDS = ("frame", "label", "comment", "color", "use_custom_color", "fence", "inclusive")
MARKER_DEFAULTS = {"comment": "", "color": [0.0, 0.0, 0.0, 0.0], "use_custom_color": False,
                   "fence": False, "inclusive": False}


class PlanError(Exception):
    pass


class TimingChanged(PlanError):
    pass


def parse_time(text, fps=25.0):
    raw = str(text).strip()
    fields = raw.split(":")
    if not raw or not 1 <= len(fields) <= 4 or fps <= 0.0:
        raise PlanError("BAD_AT|%r" % text)
    if any(not TIME_FIELD_RE.fullmatch(part.strip()) for part in fields):
        raise PlanError("BAD_AT|%r" % text)
    values = [float(part.strip()) for part in fields]
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return values[0] * 60.0 + values[1]
    if len(values) == 3:
        return values[0] * 3600.0 + values[1] * 60.0 + values[2]
    if values[3] >= fps:
        raise PlanError("BAD_AT_FRAME|%r|fps=%s" % (text, fps))
    return values[0] * 3600.0 + values[1] * 60.0 + values[2] + values[3] / fps


def parse_go_field(text):
    match = GO_FIELD_RE.fullmatch(str(text).strip())
    if match is None:
        raise PlanError("BAD_GO|%r|expected=<number> [HOLD|PASS]" % text)
    number, mode = match.groups()
    field = number + ((" " + mode) if mode else "")
    return number, mode, "GO " + field


def parse_marker_label(label):
    match = GO_RE.fullmatch(str(label))
    if match is None:
        return None
    return {"number": match.group(1), "mode": match.group(2), "tail": (match.group(3) or "").strip()}


def cuebook_go_rows(payload):
    """Carry videoCue segment labels down; At without GO is valid, GO without At is refused."""
    rows, segment, seen = [], "", set()
    for ordinal, cue in enumerate(sorted(payload.get("cues") or [], key=lambda d: d.get("ord", 0)), 1):
        if str(cue.get("videoCue") or "").strip():
            segment = str(cue["videoCue"]).strip()
        at, go = str(cue.get("at") or "").strip(), str(cue.get("go") or "").strip()
        if not go:
            if at:
                parse_time(at)
            continue
        if not at:
            raise PlanError("GO_WITHOUT_AT|cue=%s" % (cue.get("key") or ordinal))
        if not segment:
            raise PlanError("GO_WITHOUT_SEGMENT|cue=%s" % (cue.get("key") or ordinal))
        number, mode, label = parse_go_field(go)
        if mode == "BREATH":
            # A breath-pause point (design 0d2ae74). The transport parser only knows HOLD/PASS, so a BREATH
            # marker would be read as a default HOLD: never written until the transport has a BREATH state.
            continue
        if number in seen:
            raise PlanError("DUPLICATE_CUEBOOK_GO|%s" % number)
        seen.add(number)
        rows.append({"cue_key": cue.get("key") or "#%d" % ordinal, "segment": segment,
                     "at": at, "seconds": parse_time(at), "number": number, "mode": mode, "label": label})
    return rows


def marker_key(marker):
    return tuple(tuple(marker[field]) if field == "color" else marker[field] for field in MARKER_FIELDS)


def go_markers(markers):
    return [dict(marker, parsed=parse_marker_label(marker["label"])) for marker in markers
            if parse_marker_label(marker["label"]) is not None]


def build_plan(desired, existing_by_sequence, confirm_moves=False):
    """Pure global-number planner. desired rows already contain sequence/frame/number/label."""
    existing_numbers, duplicate_labels = collections.defaultdict(list), []
    for sequence, markers in existing_by_sequence.items():
        labels = collections.Counter(m["label"] for m in markers)
        duplicate_labels += ["%s:%s" % (sequence, label) for label, count in labels.items() if count > 1]
        for marker in go_markers(markers):
            existing_numbers[marker["parsed"]["number"]].append((sequence, marker))
    duplicates = {number: hits for number, hits in existing_numbers.items() if len(hits) > 1}
    if duplicate_labels:
        raise PlanError("DUPLICATE_MARKER_LABEL|" + "|".join(sorted(duplicate_labels)))
    if duplicates:
        raise PlanError("DUPLICATE_EXISTING_GO|" + ",".join(sorted(duplicates)))
    actions, wanted = [], set()
    for row in desired:
        wanted.add(row["number"])
        hits = existing_numbers.get(row["number"], [])
        if not hits:
            kind, old_sequence, old_marker = "ADD", None, None
        else:
            old_sequence, old_marker = hits[0]
            if old_sequence != row["sequence"] or old_marker["frame"] != row["frame"]:
                kind = "MOVE"
            elif old_marker["label"] != row["label"]:
                kind = "RELABEL"
            else:
                kind = "UNCHANGED"
        actions.append(dict(row, action=kind, old_sequence=old_sequence,
                            old_marker={k: old_marker[k] for k in MARKER_FIELDS} if old_marker else None))
    moves = [a for a in actions if a["action"] == "MOVE"]
    if moves and confirm_moves is not True:
        raise PlanError("CONFIRM_MOVES_REQUIRED|numbers=%s" % ",".join(a["number"] for a in moves))
    orphans = []
    for number, hits in existing_numbers.items():
        if number not in wanted:
            sequence, marker = hits[0]
            orphans.append({"number": number, "sequence": sequence, "frame": marker["frame"],
                            "label": marker["label"]})
    return {"actions": actions, "orphans": sorted(orphans, key=lambda r: (r["sequence"], r["frame"], r["label"]))}


def expected_markers(before, actions, sequence):
    """All marked frames expected after APPLY; non-GO markers are byte-for-structure preserved."""
    rows = [copy.deepcopy(m) for m in before]
    for action in actions:
        if action["action"] in ("MOVE", "RELABEL") and action["old_sequence"] == sequence:
            old = action["old_marker"]
            hits = [i for i, marker in enumerate(rows) if marker_key(marker) == marker_key(old)]
            if len(hits) != 1:
                raise PlanError("OLD_MARKER_IDENTITY|%s|%s" % (sequence, action["number"]))
            del rows[hits[0]]
        if action["action"] in ("ADD", "MOVE", "RELABEL") and action["sequence"] == sequence:
            target = copy.deepcopy(action.get("old_marker") or MARKER_DEFAULTS)
            target.update(frame=int(action["frame"]), label=action["label"])
            rows.append(target)
    return sorted(rows, key=marker_key)


def _float_equal(left, right, tolerance=FLOAT_TOLERANCE):
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= tolerance


def first_difference(left, right, path="root", tolerance=FLOAT_TOLERANCE):
    if isinstance(left, bool) or isinstance(right, bool):
        return None if left is right else "%s: %r != %r" % (path, left, right)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return None if _float_equal(float(left), float(right), tolerance) else "%s: %r != %r" % (path, left, right)
    if type(left) is not type(right):
        return "%s: type %s != %s" % (path, type(left).__name__, type(right).__name__)
    if isinstance(left, dict):
        if set(left) != set(right):
            return "%s: keys %r != %r" % (path, sorted(left), sorted(right))
        for key in sorted(left):
            diff = first_difference(left[key], right[key], "%s.%s" % (path, key), tolerance)
            if diff:
                return diff
        return None
    if isinstance(left, (list, tuple)):
        if len(left) != len(right):
            return "%s: length %d != %d" % (path, len(left), len(right))
        for index, pair in enumerate(zip(left, right)):
            diff = first_difference(pair[0], pair[1], "%s[%d]" % (path, index), tolerance)
            if diff:
                return diff
        return None
    return None if left == right else "%s: %r != %r" % (path, left, right)


def assert_timing_unchanged(before, after):
    diff = first_difference(before, after)
    if diff:
        raise TimingChanged(diff)


def fake_timing_fingerprint(sequence_model):
    """Harness model: markers intentionally omitted, matching the live guard's allowed surface."""
    return copy.deepcopy({"path": sequence_model["path"], "tracks": sequence_model.get("tracks", [])})


def _safe_call(obj, name, default=None, *args, **kwargs):
    try:
        return getattr(obj, name)(*args, **kwargs)
    except Exception:
        return default


def _safe_property(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def _class_name(obj):
    try:
        return str(obj.get_class().get_name())
    except Exception:
        return type(obj).__name__


def _asset_path(obj):
    if obj is None:
        return None
    try:
        return str(obj.get_path_name()).split(".")[0]
    except Exception:
        return str(obj)


def _normal(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "value") and isinstance(value.value, (bool, int, float, str)):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_normal(v) for v in value]
    for fields in (("x", "y", "z", "w"), ("r", "g", "b", "a")):
        try:
            return [float(getattr(value, field)) for field in fields]
        except Exception:
            pass
    return str(value)


def _time_row(frame_time):
    frame = _safe_property(frame_time, "frame_number", getattr(frame_time, "frame_number", None))
    sub = _safe_property(frame_time, "sub_frame", getattr(frame_time, "sub_frame", 0.0))
    return [int(getattr(frame, "value", frame)), float(sub)]


def _section_time_scale(section):
    direct = _safe_call(section, "get_time_scale", None)
    if direct is not None:
        return _normal(direct)
    params = _safe_property(section, "parameters")
    return _normal(_safe_property(params, "time_scale")) if params is not None else None


def live_timing_fingerprint(sequence):
    """No evaluation and no bound-object lookup: serialized sequence structure only."""
    hosts = [("root", track) for track in sequence.get_tracks()]
    for binding in sequence.get_bindings():
        bid = str(binding.get_id())
        host = "binding:%s:%s" % (bid, str(binding.get_display_name()))
        hosts.extend((host, track) for track in binding.get_tracks())
    tracks = []
    for host, track in hosts:
        track_row = {"host": host, "class": _class_name(track), "display_name": str(track.get_display_name()),
                     "row": _normal(_safe_call(track, "get_row_index", None)),
                     "sorting_order": _normal(_safe_call(track, "get_sorting_order", None)), "sections": []}
        for section_index, section in enumerate(track.get_sections()):
            sub = _safe_call(section, "get_sequence", None)
            section_row = {
                "index": section_index, "class": _class_name(section), "row": int(section.get_row_index()),
                "range": [bool(section.has_start_frame()), int(section.get_start_frame()) if section.has_start_frame() else None,
                          bool(section.has_end_frame()), int(section.get_end_frame()) if section.has_end_frame() else None],
                "sub_sequence": _asset_path(sub), "time_scale": _section_time_scale(section), "channels": []}
            for channel_index, channel in enumerate(section.get_all_channels()):
                keys = []
                for key in channel.get_keys():
                    when = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
                    keys.append({"time": _time_row(when), "value": _normal(key.get_value())})
                section_row["channels"].append({
                    "index": channel_index, "class": _class_name(channel), "name": str(channel.get_name()),
                    "default": _normal(_safe_call(channel, "get_default", None)), "keys": keys})
            track_row["sections"].append(section_row)
        tracks.append(track_row)
    return {"path": _asset_path(sequence), "display_rate": [sequence.get_display_rate().numerator,
                                                               sequence.get_display_rate().denominator],
            "tick_resolution": [sequence.get_tick_resolution().numerator, sequence.get_tick_resolution().denominator],
            "tracks": tracks}


def _state_dir():
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) if unreal else os.getcwd()
    return os.path.join(root, "CodexCueing")


def _project_dir():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()) if unreal else os.getcwd()


def _content_file(asset_path):
    return os.path.join(_project_dir(), "Content", *asset_path[len("/Game/"):].split("/")) + ".uasset"


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _census_empty(census):
    return not census["content"] and not census["maps"]


def _stop(run, reason):
    unreal.log_error("GO_MARKER_SYNC_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _record_path(run):
    return os.path.join(_state_dir(), "go_markers_sync_record_%s.json" % run)


def _write_exclusive(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, ensure_ascii=False)


def _rewrite_record(path, data):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, ensure_ascii=False)
    os.replace(temp, path)


def _backup(run, paths):
    folder = os.path.join(_project_dir(), "Backups", "PreGoMarkerSync-%s" % run)
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for asset in sorted(set(paths)):
        source = _content_file(asset)
        destination = os.path.join(folder, *asset[len("/Game/"):].split("/")) + ".uasset"
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        if _sha256(source) != _sha256(destination):
            raise PlanError("BACKUP_HASH_MISMATCH|%s" % asset)
        manifest.append({"asset": asset, "source": source, "backup": destination,
                         "sha256": _sha256(destination)})
    manifest_path = os.path.join(folder, "manifest.json")
    with open(manifest_path, "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1, sort_keys=True)
    return folder, manifest


def _restore_backup(manifest):
    restored = []
    for row in manifest:
        if _sha256(row["backup"]) != row["sha256"]:
            raise PlanError("RESTORE_BACKUP_HASH_MISMATCH|%s" % row["asset"])
        shutil.copy2(row["backup"], row["source"])
        if _sha256(row["source"]) != row["sha256"]:
            raise PlanError("RESTORE_READBACK_FAILED|%s" % row["asset"])
        restored.append(row["asset"])
    return restored


def _loaded(value):
    if value is not None and hasattr(value, "load_synchronous"):
        value = value.load_synchronous()
    return value


def _kind(value):
    text = str(value).split(".")[-1].lower()
    if "wing" in text:
        return "passage"
    if "sequence" in text:
        return "interaction"
    if "scene" in text:
        return "scene"
    return text


def _segment_sequences(show, aliases):
    """Exact labels and ordinal P/S/I codes only; user aliases are explicit, never guessed."""
    entries = []
    for ordinal, settings in enumerate(show.get_editor_property("passage_settings"), 1):
        entries.append({"kind": "passage", "code": "P%d" % ordinal, "label": str(settings.get_editor_property("label")),
                        "sequence": _loaded(settings.get_editor_property("choreography"))})
    counts = {"scene": 0, "interaction": 0}
    for cue in show.get_editor_property("cues"):
        kind = _kind(cue.get_editor_property("type"))
        if kind not in counts:
            continue
        counts[kind] += 1
        prefix = "S" if kind == "scene" else "I"
        scene = cue.get_editor_property("scene")
        entries.append({"kind": kind, "code": "%s%d" % (prefix, counts[kind]),
                        "label": str(cue.get_editor_property("label")),
                        "sequence": _loaded(scene.get_editor_property("sequence"))})
    lookup = collections.defaultdict(list)
    for entry in entries:
        lookup[entry["code"].casefold()].append(entry)
        lookup[entry["label"].strip().casefold()].append(entry)
    resolved = {}
    for source, target in aliases.items():
        hits = lookup[str(target).strip().casefold()]
        if len(hits) != 1:
            raise PlanError("SEGMENT_ALIAS_TARGET|%s=>%s|hits=%d" % (source, target, len(hits)))
        resolved[str(source).strip().casefold()] = hits[0]
    return entries, lookup, resolved


def _resolve_rows(show, cue_rows, aliases):
    entries, lookup, alias_lookup = _segment_sequences(show, aliases)
    out = []
    for row in cue_rows:
        key = row["segment"].strip().casefold()
        hits = [alias_lookup[key]] if key in alias_lookup else lookup[key]
        if len(hits) != 1:
            raise PlanError("SEGMENT_REFUSED|%s|hits=%d" % (row["segment"], len(hits)))
        entry = hits[0]
        sequence = entry["sequence"]
        if sequence is None:
            raise PlanError("SEGMENT_HAS_NO_OWN_SEQUENCE|%s|%s" % (row["segment"], entry["kind"]))
        tick = sequence.get_tick_resolution()
        tick_rate = float(tick.numerator) / float(tick.denominator)
        start_s = float(sequence.get_playback_start_seconds())
        end_s = float(sequence.get_playback_end_seconds())
        at_s = row["seconds"]
        if at_s < 0.0 or start_s + at_s > end_s + 1e-9:
            raise PlanError("AT_OUTSIDE_SEQUENCE|%s|at=%s|range=%s..%s" %
                            (row["cue_key"], at_s, start_s, end_s))
        out.append(dict(row, sequence=_asset_path(sequence), frame=int(round((start_s + at_s) * tick_rate)),
                        sequence_kind=entry["kind"], sequence_object=sequence))
    paths = [row["sequence"] for row in out]
    if len(set(paths)) != len(set(row["segment"].casefold() for row in out)):
        raise PlanError("SEQUENCE_SHARED_BY_SEGMENTS|refused")
    return entries, out


class _LiveMarkers:
    def __init__(self, sequence):
        self.sequence = sequence
        self.ext = unreal.MovieSceneSequenceExtensions
        self.unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION

    @staticmethod
    def _property(marker, name, default):
        try:
            return marker.get_editor_property(name)
        except Exception:
            return default

    def list(self):
        rows = []
        for marker in self.ext.get_marked_frames_from_sequence(self.sequence, self.unit):
            color = self._property(marker, "custom_color", None)
            rows.append({
                "frame": int(marker.get_editor_property("frame_number").value),
                "label": str(marker.get_editor_property("label")),
                "comment": str(self._property(marker, "comment", "") or ""),
                "color": [float(color.r), float(color.g), float(color.b), float(color.a)] if color else [0.0] * 4,
                "use_custom_color": bool(self._property(marker, "use_custom_color", False)),
                "fence": bool(self._property(marker, "is_determinism_fence", False)),
                "inclusive": bool(self._property(marker, "is_inclusive_time", False)),
            })
        return rows

    def delete(self, marker):
        index = self.ext.find_marked_frame_by_label(self.sequence, marker["label"])
        if index < 0:
            raise PlanError("MARKER_NOT_FOUND|%s" % marker["label"])
        self.ext.delete_marked_frame(self.sequence, index)

    def add(self, marker):
        value = unreal.MovieSceneMarkedFrame()
        value.set_editor_property("frame_number", unreal.FrameNumber(int(marker["frame"])))
        value.set_editor_property("label", marker["label"])
        if marker.get("comment"):
            value.set_editor_property("comment", marker["comment"])
        if marker.get("use_custom_color"):
            value.set_editor_property("use_custom_color", True)
            value.set_editor_property("custom_color", unreal.LinearColor(*marker["color"]))
        if marker.get("fence"):
            value.set_editor_property("is_determinism_fence", True)
        if marker.get("inclusive"):
            value.set_editor_property("is_inclusive_time", True)
        self.ext.add_marked_frame_to_sequence(self.sequence, value, self.unit)


def _gather(args, confirm_moves=None):
    with open(os.path.join(_project_dir(), args["cuebook_json"]), encoding="utf-8") as handle:
        payload = json.load(handle)
    cue_rows = cuebook_go_rows(payload)
    show = unreal.load_asset(SHOW_PATH)
    master = unreal.load_asset(MASTER_PATH)
    if show is None or master is None:
        raise PlanError("SHOW_OR_MASTER_LOAD_FAILED")
    entries, desired = _resolve_rows(show, cue_rows, args.get("segment_map") or {})
    sequences = {_asset_path(entry["sequence"]): entry["sequence"] for entry in entries if entry["sequence"] is not None}
    existing = {path: _LiveMarkers(seq).list() for path, seq in sequences.items()}
    if confirm_moves is None:
        # Gary, 9 Oct: "the cue book can move go points" -> moves allowed unless args say confirm_moves: false.
        confirm_moves = args.get("confirm_moves", True) is not False
    plan = build_plan([{k: v for k, v in row.items() if k != "sequence_object"} for row in desired], existing,
                      confirm_moves)
    touched = sorted(set(a["sequence"] for a in plan["actions"] if a["action"] != "UNCHANGED") |
                     set(a["old_sequence"] for a in plan["actions"] if a["action"] == "MOVE"))
    locked = [path for path in touched if sequences[path].are_marked_frames_locked()]
    if locked:
        raise PlanError("MARKERS_LOCKED|%s" % locked)
    plan.update({"desired": [{k: v for k, v in row.items() if k != "sequence_object"} for row in desired],
                 "touched": touched})
    objects = dict(sequences)
    objects[MASTER_PATH] = master
    return plan, objects


def _fingerprints(objects, paths):
    return {path: live_timing_fingerprint(objects[path]) for path in sorted(paths)}


def _guard(before, objects, paths):
    after = _fingerprints(objects, paths)
    assert_timing_unchanged(before, after)
    return after


def _log_plan(run, plan):
    for action in plan["actions"]:
        unreal.log("GO_MARKER_SYNC_PLAN|run=%s|%s|go=%s|segment=%s|sequence=%s|frame=%s|old_sequence=%s|old_frame=%s" %
                   (run, action["action"], action["number"], action["segment"], action["sequence"], action["frame"],
                    action.get("old_sequence"), (action.get("old_marker") or {}).get("frame")))
    for orphan in plan["orphans"]:
        unreal.log_warning("GO_MARKER_SYNC_ORPHAN|run=%s|go=%s|sequence=%s|frame=%s|label=%s|action=LIST_ONLY" %
                           (run, orphan["number"], orphan["sequence"], orphan["frame"], orphan["label"]))


def _apply_actions(plan, objects):
    before = {path: _LiveMarkers(objects[path]).list() for path in plan["touched"]}
    expected = {path: expected_markers(before[path], plan["actions"], path) for path in plan["touched"]}
    for action in plan["actions"]:
        if action["action"] in ("MOVE", "RELABEL"):
            _LiveMarkers(objects[action["old_sequence"]]).delete(action["old_marker"])
        if action["action"] in ("ADD", "MOVE", "RELABEL"):
            target = copy.deepcopy(action.get("old_marker") or MARKER_DEFAULTS)
            target.update(frame=action["frame"], label=action["label"])
            _LiveMarkers(objects[action["sequence"]]).add(target)
    for path in plan["touched"]:
        got = sorted(_LiveMarkers(objects[path]).list(), key=marker_key)
        if got != expected[path]:
            raise PlanError("MARKER_READBACK|%s" % path)
    return before, expected


def _save_only(paths):
    census = _census()
    if census["maps"] or set(census["content"]) != set(paths):
        raise PlanError("DIRTY_CENSUS_BEFORE_SAVE|got=%s|want=%s" % (census, paths))
    for path in paths:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise PlanError("SAVE_FAILED|%s" % path)
    after = _census()
    if not _census_empty(after):
        raise PlanError("DIRTY_AFTER_SAVE|%s" % after)


def run_dry(args, run):
    plan, _objects = _gather(args, confirm_moves=True)  # DRY must list MOVE; only APPLY requires confirmation.
    _log_plan(run, plan)
    path = os.path.join(_state_dir(), "go_markers_sync_dry_%s.json" % run)
    _write_exclusive(path, {"tool": TOOL, "run": run, "mode": "DRY", "census": _census(), **plan})
    counts = collections.Counter(a["action"] for a in plan["actions"])
    unreal.log("GO_MARKER_SYNC_DRY_OK|run=%s|ADD=%d|RELABEL=%d|MOVE=%d|UNCHANGED=%d|orphans=%d|report=%s" %
               (run, counts["ADD"], counts["RELABEL"], counts["MOVE"], counts["UNCHANGED"], len(plan["orphans"]), path))


def run_apply(args, run):
    if args.get("confirm") != "APPLY GO MARKERS":
        raise PlanError("CONFIRM_REQUIRED|APPLY GO MARKERS")
    plan, objects = _gather(args)
    _log_plan(run, plan)
    gathered_census = _census()
    if not _census_empty(gathered_census):
        raise PlanError("DIRTY_AFTER_GATHER|%s" % gathered_census)
    if not plan["touched"]:
        unreal.log("GO_MARKER_SYNC_APPLY_OK|run=%s|changes=0|orphans=%d|saved=[]" % (run, len(plan["orphans"])))
        return
    protected = sorted(set(plan["touched"] + [MASTER_PATH]))
    timing_before = _fingerprints(objects, protected)
    fingerprint_census = _census()
    if not _census_empty(fingerprint_census):
        raise PlanError("DIRTY_AFTER_FINGERPRINT|%s" % fingerprint_census)
    record_path = _record_path(run)
    record = {"tool": TOOL, "run": run, "mode": "APPLY", "applied": False, "args": args, "plan": plan,
              "protected": protected, "timing_before": timing_before, "census_before": _census()}
    _write_exclusive(record_path, record)
    backup, manifest = _backup(run, protected)
    record["backup"] = backup
    record["manifest"] = manifest
    _rewrite_record(record_path, record)
    try:
        markers_before, expected = _apply_actions(plan, objects)
        _guard(timing_before, objects, protected)
        _save_only(plan["touched"])
        _guard(timing_before, objects, protected)
        for path in plan["touched"]:
            if sorted(_LiveMarkers(unreal.load_asset(path)).list(), key=marker_key) != expected[path]:
                raise PlanError("SAVED_MARKER_READBACK|%s" % path)
    except TimingChanged as error:
        restored = _restore_backup(manifest)
        _stop(run, "TIMING_CHANGED|%s|restored=%s|restart=DontSave" % (error, restored))
    except Exception as error:
        restored = _restore_backup(manifest)
        _stop(run, "APPLY_FAILED|%s|restored=%s|restart=DontSave" % (error, restored))
    record.update({"applied": True, "markers_before": markers_before, "markers_after": expected,
                   "census_after": _census()})
    _rewrite_record(record_path, record)
    unreal.log("GO_MARKER_SYNC_APPLY_OK|run=%s|changes=%d|saved=%s|backup=%s|record=%s" %
               (run, len([a for a in plan["actions"] if a["action"] != "UNCHANGED"]), plan["touched"], backup,
                record_path))


def _replace_go_set(adapter, current, target):
    current_go, target_go = go_markers(current), go_markers(target)
    current_keys = collections.Counter(marker_key({k: m[k] for k in MARKER_FIELDS}) for m in current_go)
    target_keys = collections.Counter(marker_key({k: m[k] for k in MARKER_FIELDS}) for m in target_go)
    for marker in current_go:
        plain = {k: marker[k] for k in MARKER_FIELDS}
        key = marker_key(plain)
        if current_keys[key] > target_keys[key]:
            adapter.delete(plain)
            current_keys[key] -= 1
    for marker in target_go:
        plain = {k: marker[k] for k in MARKER_FIELDS}
        key = marker_key(plain)
        if target_keys[key] > current_keys[key]:
            adapter.add(plain)
            current_keys[key] += 1


def run_revert(args, run):
    if args.get("confirm") != "REVERT GO MARKERS":
        raise PlanError("CONFIRM_REQUIRED|REVERT GO MARKERS")
    source = str(args.get("source_run_id") or "").strip()
    if not source:
        raise PlanError("SOURCE_RUN_REQUIRED")
    source_path = _record_path(source)
    with open(source_path, encoding="utf-8") as handle:
        record = json.load(handle)
    if not record.get("applied"):
        raise PlanError("SOURCE_RECORD_NOT_APPLIED|%s" % source)
    paths = record["plan"]["touched"]
    objects = {path: unreal.load_asset(path) for path in record["protected"]}
    if any(obj is None for obj in objects.values()):
        raise PlanError("REVERT_ASSET_LOAD_FAILED")
    for path in paths:
        current = sorted(_LiveMarkers(objects[path]).list(), key=marker_key)
        applied = sorted(record["markers_after"][path], key=marker_key)
        if current != applied:
            raise PlanError("REVERT_DRIFT|%s" % path)
    timing_before = _fingerprints(objects, record["protected"])
    fingerprint_census = _census()
    if not _census_empty(fingerprint_census):
        raise PlanError("DIRTY_AFTER_REVERT_FINGERPRINT|%s" % fingerprint_census)
    backup, manifest = _backup(run, record["protected"])
    revert_record = {"tool": TOOL, "run": run, "mode": "REVERT", "source_run": source, "applied": False,
                     "backup": backup, "manifest": manifest, "protected": record["protected"], "touched": paths}
    revert_path = _record_path(run)
    _write_exclusive(revert_path, revert_record)
    try:
        for path in paths:
            adapter = _LiveMarkers(objects[path])
            _replace_go_set(adapter, adapter.list(), record["markers_before"][path])
        _guard(timing_before, objects, record["protected"])
        _save_only(paths)
        _guard(timing_before, objects, record["protected"])
        for path in paths:
            got = sorted(_LiveMarkers(unreal.load_asset(path)).list(), key=marker_key)
            if got != sorted(record["markers_before"][path], key=marker_key):
                raise PlanError("REVERT_SAVED_READBACK|%s" % path)
    except TimingChanged as error:
        restored = _restore_backup(manifest)
        _stop(run, "TIMING_CHANGED|%s|restored=%s|restart=DontSave" % (error, restored))
    except Exception as error:
        restored = _restore_backup(manifest)
        _stop(run, "REVERT_FAILED|%s|restored=%s|restart=DontSave" % (error, restored))
    revert_record.update({"applied": True, "census_after": _census()})
    _rewrite_record(revert_path, revert_record)
    archived = source_path + ".reverted-" + run
    os.replace(source_path, archived)
    unreal.log("GO_MARKER_SYNC_REVERT_OK|run=%s|source_run=%s|saved=%s|backup=%s|record=%s" %
               (run, source, paths, backup, revert_path))


def validate_args(args):
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise PlanError("MODE_REQUIRED|DRY|APPLY|REVERT")
    run = str(args.get("run_id") or datetime.datetime.now().strftime("GOMS-%Y%m%d-%H%M%S"))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run):
        raise PlanError("BAD_RUN_ID|%r" % run)
    if mode != "REVERT" and not str(args.get("cuebook_json") or "").strip():
        raise PlanError("CUEBOOK_JSON_REQUIRED")
    return mode, run


def main():
    args = globals().get("GO_MARKER_SYNC_ARGS")
    if args is None:
        with open(os.path.join(_state_dir(), ARGS_NAME), encoding="utf-8") as handle:
            args = json.load(handle)
    mode, run = validate_args(args)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    world_name = str(world.get_outermost().get_name()) if world is not None else None
    state = {"world": world_name, "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": _census()}
    if state["world"] != EXPECTED_WORLD or state["pie"] or state["sequencer_open"]:
        _stop(run, "EDITOR_GATE|%s" % state)
    if mode in ("APPLY", "REVERT") and not _census_empty(state["census"]):
        _stop(run, "DIRTY_AT_START|%s" % state["census"])
    try:
        if mode == "DRY":
            run_dry(args, run)
        elif mode == "APPLY":
            run_apply(args, run)
        else:
            run_revert(args, run)
    except PlanError as error:
        _stop(run, "PLAN_REFUSED|%s" % error)
    except Exception as error:
        _stop(run, "UNEXPECTED|%r" % (error,))


if unreal is not None:
    main()
