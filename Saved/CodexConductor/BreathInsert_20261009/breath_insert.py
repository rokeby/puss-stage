"""P45 authored-breath insertion planner and guarded Unreal transaction.

The planning half of this module deliberately imports no ``unreal``.  It accepts
plain JSON snapshots and returns an exact, ordered edit list.  The live adapter
imports Unreal only when constructed; the offline harness injects a fake.

Proof boundary:
  declaration-proven -- the 13 channels and timing fields are declared in
    MovieSceneInfinityPassageTrack.h:13-43,146-209 and
    InfinityStageTypes.h:740-744,982-1001.
  measured-upstream -- the audio APPLY record supplies the exact sample delta;
    this tool re-reads and hashes that record but does not re-render audio.
  measured-offline -- test_breath_insert.py exercises the planner and fake
    transaction.  It is not saved-Unreal or rendered acceptance.
  inferred -- the planned holder ripple implements the P36 recommendation in
    Docs/Conductor/P36_BREATH_INSERT_TIME_REPORT.md:102-137.
"""

from __future__ import division

import copy
import datetime
import hashlib
import json
import math
import os
import shutil
import struct
import zlib


TOOL = "P36_BREATH"
VERSION = "2026-10-09a"
FOLDER = "BreathInsert_20261009"
PLAN_NAME = "breath_insert_plan.json"
CHANNELS = (
    "Camera.SpeedMultiplier",
    "Camera.LongitudinalOffsetCm",
    "Camera.LateralOffsetCm",
    "Camera.HeightOffsetCm",
    "Camera.PitchDegrees",
    "Camera.YawDegrees",
    "Camera.RollDegrees",
    "Camera.LookAheadDistanceCm",
    "Camera.FocalLengthMm",
    "Camera.FocusDistanceCm",
    "Wing.InwardTravelScale",
    "Wing.CycleRateScale",
    "Wing.PhaseBiasCycles",
)
PASSAGE_MANAGED_CLASSES = {
    "MovieSceneInfinityPassageTrack",
    "MovieSceneInfinitySceneTrack",
    "MovieSceneInfinityAudioTrack",
    "MovieSceneInfinityCueTrack",
}
SUBSECTION_CLASSES = {"MovieSceneSubTrack", "MovieSceneCinematicShotTrack"}
KNOWN_HOLDERS = {
    "changed_passage_channels",
    "changed_passage_pins",
    "later_passage_managed",
    "master_managed",
    "master_artist_root",
    "master_artist_binding",
    "master_camera_cut",
    "master_marker",
    "changed_choreo_track",
    "changed_choreo_marker",
    "mechanism_origin",
    "managed_music",
    "cue_at_go",
    "render_wrapper_cut",
}


class PlanError(ValueError):
    pass


class Stop(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    if not path or not os.path.isfile(path):
        raise PlanError("JSON_MISSING|%s" % path)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n"
    if exclusive:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def close_numeric(a, b, tolerance=1.0e-4):
    return abs(float(a) - float(b)) <= tolerance


def _int(value, label):
    if isinstance(value, bool):
        raise PlanError("%s_NOT_INTEGER" % label)
    try:
        out = int(value)
    except (TypeError, ValueError):
        raise PlanError("%s_NOT_INTEGER" % label)
    if float(value) != float(out):
        raise PlanError("%s_NOT_INTEGER" % label)
    return out


def _normalise_args(raw):
    raw = copy.deepcopy(raw or {})
    required = (
        "passage_guid", "passage_offset_frame", "insert_frames", "audio_apply_record",
        "show_package", "master_package", "level_package", "choreo_package",
        "music_package", "render_wrapper_package", "rendered_sound_path", "analysis_map_path",
    )
    missing = [name for name in required if raw.get(name) in (None, "")]
    if missing:
        raise PlanError("ARGS_MISSING|%s" % ",".join(missing))
    out = raw
    out["passage_guid"] = str(out["passage_guid"]).upper().replace("-", "")
    out["passage_offset_frame"] = _int(out["passage_offset_frame"], "PASSAGE_OFFSET_FRAME")
    out["insert_frames"] = _int(out["insert_frames"], "INSERT_FRAMES")
    out["ease_frames"] = _int(out.get("ease_frames", 0), "EASE_FRAMES")
    out["look_yaw_degrees"] = float(out.get("look_yaw_degrees", 0.0))
    out["look_pitch_degrees"] = float(out.get("look_pitch_degrees", 0.0))
    out["changed_choreo_policy"] = str(out.get("changed_choreo_policy", "RIPPLE_CLASSIFIED")).upper()
    out["named_packages"] = sorted(set(str(x) for x in out.get("named_packages", []) + [
        out["show_package"], out["master_package"], out["level_package"],
        out["choreo_package"], out["music_package"], out["render_wrapper_package"],
    ]))
    if out["insert_frames"] <= 0:
        raise PlanError("INSERT_FRAMES_MUST_BE_POSITIVE")
    if out["ease_frames"] < 0:
        raise PlanError("EASE_FRAMES_MUST_BE_NONNEGATIVE")
    if out["changed_choreo_policy"] != "RIPPLE_CLASSIFIED":
        raise PlanError("CHANGED_CHOREO_POLICY|%s" % out["changed_choreo_policy"])
    if out["music_package"] != out["analysis_map_path"]:
        raise PlanError("MUSIC_PACKAGE_MUST_NAME_ANALYSIS_MAP")
    return out


def _audio_delta_ticks(record, tick_resolution):
    if record.get("tool") != "breath_audio" or record.get("mode") != "APPLY" or record.get("status") != "passed":
        raise PlanError("AUDIO_RECORD_NOT_PASSED_APPLY")
    timing = record.get("timing") or {}
    samples = _int(timing.get("output_length_delta_samples"), "AUDIO_DELTA_SAMPLES")
    rate = _int(timing.get("sample_rate_hz"), "AUDIO_SAMPLE_RATE")
    if samples <= 0 or rate <= 0:
        raise PlanError("AUDIO_DELTA_INVALID")
    exact = samples * float(tick_resolution) / rate
    rounded = int(round(exact))
    if abs(exact - rounded) > 1.0e-7:
        raise PlanError("AUDIO_DELTA_NOT_REPRESENTABLE_IN_SHOW_TICKS|%.12f" % exact)
    recorded_seconds = float(timing.get("output_length_delta_seconds", samples / float(rate)))
    if abs(recorded_seconds - samples / float(rate)) > 1.0e-9:
        raise PlanError("AUDIO_RECORD_DELTA_INCONSISTENT")
    return rounded


def _audio_wav_hash(record):
    rows = []
    for path, state in (record.get("target_after") or {}).items():
        if str(path).lower().endswith(".wav") and isinstance(state, dict) and state.get("sha256"):
            rows.append(str(state["sha256"]))
    if len(rows) != 1:
        raise PlanError("AUDIO_RECORD_WAV_HASH_COUNT|%d" % len(rows))
    return rows[0]


def _key_rows(channel):
    return [[_int(row[0], "KEY_FRAME"), float(row[1])] for row in channel]


def _shift_keys(keys, threshold, delta):
    return [[frame + (delta if frame >= threshold else 0), value] for frame, value in _key_rows(keys)]


def _set_key(keys, frame, value):
    rows = [[int(t), float(v)] for t, v in keys if int(t) != int(frame)]
    rows.append([int(frame), float(value)])
    return sorted(rows, key=lambda row: row[0])


def _ripple_section(section, threshold, delta, scope, edits):
    start, end = [_int(x, "SECTION_RANGE") for x in section["range"]]
    cls = str(section.get("class", ""))
    locator = copy.deepcopy(section.get("locator") or {})
    if end <= threshold:
        return copy.deepcopy(section)
    out = copy.deepcopy(section)
    if start >= threshold:
        out["range"] = [start + delta, end + delta]
        for channel in out.get("channels", []):
            channel["keys"] = [[t + delta, v] for t, v in _key_rows(channel.get("keys", []))]
        edits.append({"op": "move_section", "scope": scope, "locator": locator, "delta": delta})
        return out
    if cls in SUBSECTION_CLASSES or bool(section.get("is_subsection")):
        raise PlanError("STRADDLING_SUB_SECTION|%s|%s|%s" % (scope, start, end))
    out["range"] = [start, end + delta]
    for channel in out.get("channels", []):
        channel["keys"] = _shift_keys(channel.get("keys", []), threshold, delta)
    edits.append({"op": "extend_and_ripple_section", "scope": scope, "locator": locator,
                  "threshold": threshold, "delta": delta})
    return out


def _ripple_track_rows(rows, threshold, delta, scope, edits):
    output = []
    for track in rows:
        classification = str(track.get("classification", ""))
        if classification not in KNOWN_HOLDERS:
            raise PlanError("UNKNOWN_HOLDER|%s|%s" % (scope, classification or "<blank>"))
        if classification in ("master_managed", "later_passage_managed", "managed_music"):
            output.append(copy.deepcopy(track))
            continue
        changed = copy.deepcopy(track)
        changed["sections"] = [_ripple_section(section, threshold, delta, scope, edits)
                               for section in track.get("sections", [])]
        output.append(changed)
    return output


def _marker_rows(rows, threshold, delta, scope, edits):
    out = []
    labels = set()
    for marker in rows:
        row = copy.deepcopy(marker)
        label = str(row.get("label", ""))
        if not label or label in labels:
            raise PlanError("MARKER_LABEL_NOT_UNIQUE|%s|%s" % (scope, label))
        labels.add(label)
        frame = _int(row["frame"], "MARKER_FRAME")
        if frame >= threshold:
            if row.get("locked"):
                raise PlanError("LOCKED_MARKER|%s|%s" % (scope, label))
            row["frame"] = frame + delta
            edits.append({"op": "move_marker_by_label", "scope": scope, "label": label,
                          "from": frame, "to": frame + delta,
                          "delete_api": "find_marked_frame_by_label"})
        out.append(row)
    return out


def _assert_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise PlanError("SNAPSHOT_NOT_OBJECT")
    required = ("tick_resolution", "passages", "passage_sections", "master", "changed_choreo",
                "mechanism_origins", "cue_rows", "managed_music", "render_wrapper", "existing_breaths")
    missing = [key for key in required if key not in snapshot]
    if missing:
        raise PlanError("SNAPSHOT_MISSING|%s" % ",".join(missing))
    unknown = [row for row in snapshot.get("holders", []) if row.get("classification") not in KNOWN_HOLDERS]
    if unknown:
        raise PlanError("UNKNOWN_HOLDER|%s" % canonical(unknown))


def _passage(snapshot, guid):
    rows = [row for row in snapshot["passages"] if str(row.get("guid", "")).upper().replace("-", "") == guid]
    if len(rows) != 1:
        raise PlanError("PASSAGE_GUID_COUNT|%s|%d" % (guid, len(rows)))
    return rows[0]


def _containing_span(passage, absolute_f):
    rows = [row for row in passage.get("linear_spans", [])
            if int(row["start"]) <= absolute_f < int(row["end"])]
    if len(rows) != 1:
        raise PlanError("CONTAINING_SPAN_COUNT|%d" % len(rows))
    row = rows[0]
    if row.get("kind") not in ("lead_in", "interval", "tail"):
        raise PlanError("UNKNOWN_TIMING_SPAN|%s" % row.get("kind"))
    before_guid, after_guid = row.get("wing_before_guid"), row.get("wing_after_guid")
    if not before_guid or not after_guid:
        raise PlanError("BOUNDING_WING_PINS_MISSING")
    return row


def build_plan(snapshot, audio_record, raw_args):
    """Pure planner: no Unreal import and no writes."""
    args = _normalise_args(raw_args)
    _assert_snapshot(snapshot)
    tick = float(snapshot["tick_resolution"])
    d = _audio_delta_ticks(audio_record, tick)
    if d != args["insert_frames"]:
        raise PlanError("D_MISMATCH|args=%d|audio=%d" % (args["insert_frames"], d))
    passage = _passage(snapshot, args["passage_guid"])
    start, end = int(passage["start"]), int(passage["end"])
    f = start + args["passage_offset_frame"]
    if not start < f < end:
        raise PlanError("F_OUTSIDE_PASSAGE|F=%d|range=(%d,%d)" % (f, start, end))
    ease = args["ease_frames"]
    if f - ease < start or f + d + ease > end + d:
        raise PlanError("EASE_OUTSIDE_CHANGED_PASSAGE")
    for row in snapshot.get("existing_breaths", []):
        if max(f, int(row["start"])) < min(f + d, int(row["end"])):
            raise PlanError("EXISTING_BREATH_OVERLAP|%s" % canonical(row))
    span = _containing_span(passage, f)

    after = copy.deepcopy(snapshot)
    edits = []
    after_passage = _passage(after, args["passage_guid"])
    target_span = [row for row in after_passage["linear_spans"]
                   if row["kind"] == span["kind"] and row.get("index") == span.get("index")][0]
    span_seen = False
    for row in after_passage["linear_spans"]:
        is_target = row["kind"] == span["kind"] and row.get("index") == span.get("index")
        if is_target:
            row["duration"] = int(row["duration"]) + d
            row["end"] = int(row["end"]) + d
            span_seen = True
        elif span_seen:
            row["start"], row["end"] = int(row["start"]) + d, int(row["end"]) + d
    for p in after["passages"]:
        if p is after_passage:
            p["end"] = int(p["end"]) + d
        elif int(p["start"]) >= end:
            p["start"], p["end"] = int(p["start"]) + d, int(p["end"]) + d
            for later_span in p.get("linear_spans", []):
                later_span["start"] = int(later_span["start"]) + d
                later_span["end"] = int(later_span["end"]) + d
    edits.append({"op": "extend_show_timing_span", "passage_guid": args["passage_guid"],
                  "kind": span["kind"], "index": span.get("index"), "old": int(span["duration"]),
                  "new": int(span["duration"]) + d})

    section = after["passage_sections"].get(args["passage_guid"])
    if not section:
        raise PlanError("CHANGED_PASSAGE_SECTION_MISSING")
    names = set(section.get("channels", {}))
    if names != set(CHANNELS):
        raise PlanError("PASSAGE_CHANNEL_SET|missing=%s|extra=%s" %
                        (sorted(set(CHANNELS) - names), sorted(names - set(CHANNELS))))
    for name in CHANNELS:
        section["channels"][name] = _shift_keys(section["channels"][name], f, d)
        if any(int(row[0]) >= f for row in snapshot["passage_sections"][args["passage_guid"]]["channels"][name]):
            edits.append({"op": "ripple_passage_channel", "channel": name, "threshold": f, "delta": d})
    speed = section["channels"]["Camera.SpeedMultiplier"]
    yaw = section["channels"]["Camera.YawDegrees"]
    pitch = section["channels"]["Camera.PitchDegrees"]
    for frame, value in ((f - ease, 1.0), (f, 0.0), (f + d, 0.0), (f + d + ease, 1.0)):
        speed = _set_key(speed, frame, value)
    for channel, value in ((yaw, args["look_yaw_degrees"]), (pitch, args["look_pitch_degrees"])):
        for frame, keyed in ((f - ease, 0.0), (f, value), (f + d, value), (f + d + ease, 0.0)):
            replacement = _set_key(channel, frame, keyed)
            channel[:] = replacement
    section["channels"]["Camera.SpeedMultiplier"] = speed
    section["range"] = [start, end + d]
    section["pinned_passage_frames"] = sorted(set(
        int(x) + (d if start + int(x) >= f else 0) for x in section.get("pinned_passage_frames", [])))
    section["pinned_wing_cue_guids"] = sorted(set(section.get("pinned_wing_cue_guids", []) +
                                                     [span["wing_before_guid"], span["wing_after_guid"]]))
    edits += [
        {"op": "add_breath_channel_keys", "channel": "Camera.SpeedMultiplier",
         "keys": [[f - ease, 1.0], [f, 0.0], [f + d, 0.0], [f + d + ease, 1.0]]},
        {"op": "add_breath_channel_keys", "channel": "Camera.YawDegrees",
         "keys": [[f - ease, 0.0], [f, args["look_yaw_degrees"]],
                  [f + d, args["look_yaw_degrees"]], [f + d + ease, 0.0]]},
        {"op": "add_breath_channel_keys", "channel": "Camera.PitchDegrees",
         "keys": [[f - ease, 0.0], [f, args["look_pitch_degrees"]],
                  [f + d, args["look_pitch_degrees"]], [f + d + ease, 0.0]]},
        {"op": "ripple_relative_pins", "threshold": f - start, "delta": d},
        {"op": "ensure_bounding_wing_pins", "guids": [span["wing_before_guid"], span["wing_after_guid"]]},
    ]

    master = after["master"]
    master["root_tracks"] = _ripple_track_rows(master.get("root_tracks", []), f, d,
                                                  "master_root", edits)
    master["binding_tracks"] = _ripple_track_rows(master.get("binding_tracks", []), f, d,
                                                     "master_binding", edits)
    master["camera_cuts"] = [_ripple_section(row, f, d, "master_camera_cut", edits)
                              for row in master.get("camera_cuts", [])]
    master["markers"] = _marker_rows(master.get("markers", []), f, d, "master", edits)
    master["playback"] = [int(master["playback"][0]), int(master["playback"][1]) + d]
    for row in master.get("managed_sections", []):
        classification = row.get("classification")
        if classification not in ("master_managed", "later_passage_managed", "managed_music"):
            raise PlanError("UNKNOWN_HOLDER|managed_section|%s" % classification)
        rs, re = [int(x) for x in row["range"]]
        if rs == start and re == end:
            row["range"] = [rs, re + d]
        elif rs >= end:
            row["range"] = [rs + d, re + d]

    local_f = f - start
    choreo = after["changed_choreo"]
    choreo["tracks"] = _ripple_track_rows(choreo.get("tracks", []), local_f, d,
                                             "changed_choreo", edits)
    choreo["markers"] = _marker_rows(choreo.get("markers", []), local_f, d,
                                       "changed_choreo", edits)
    choreo["playback"] = [int(choreo["playback"][0]), int(choreo["playback"][1]) + d]
    edits.append({"op": "extend_choreo_playback", "package": args["choreo_package"], "delta": d})

    for row in after["mechanism_origins"]:
        if row.get("classification") != "mechanism_origin":
            raise PlanError("UNKNOWN_HOLDER|mechanism_origin|%s" % row.get("classification"))
        if row.get("explicit") and int(row["frame"]) >= f:
            old = int(row["frame"])
            row["frame"] = old + d
            edits.append({"op": "move_explicit_mechanism_origin", "cue_guid": row["cue_guid"],
                          "from": old, "to": old + d})

    for row in after["cue_rows"]:
        if row.get("classification") != "cue_at_go":
            raise PlanError("UNKNOWN_HOLDER|cue_at_go|%s" % row.get("classification"))
        if row.get("passage_guid", "").upper().replace("-", "") == args["passage_guid"]:
            for field in ("at_frame", "go_frame"):
                if row.get(field) is not None and int(row[field]) >= local_f:
                    old = int(row[field])
                    row[field] = old + d
                    edits.append({"op": "move_cue_row", "row_id": row["row_id"], "field": field,
                                  "from": old, "to": old + d})

    music = after["managed_music"]
    if music.get("classification") != "managed_music":
        raise PlanError("UNKNOWN_HOLDER|managed_music")
    validation = music.get("import_validation") or {}
    wav_hash = _audio_wav_hash(audio_record)
    wanted_import = {
        "sound": args["rendered_sound_path"], "analysis": args["analysis_map_path"],
        "audio_record_run": audio_record.get("run_id"), "rendered_wav_sha256": wav_hash,
        "analysis_source_wav_sha256": wav_hash, "stale": False,
    }
    if validation != wanted_import:
        raise PlanError("STALE_OR_MISMATCHED_MUSIC_IMPORT|got=%s|want=%s" %
                        (canonical(validation), canonical(wanted_import)))
    music["sound"] = args["rendered_sound_path"]
    music["analysis"] = args["analysis_map_path"]
    moved_music = []
    for range_row in music.get("sections", []):
        ms, me = [int(x) for x in range_row]
        if ms == start and me == end:
            range_row = [ms, me + d]
        elif ms >= end:
            range_row = [ms + d, me + d]
        moved_music.append(range_row)
    music["sections"] = moved_music
    edits.append({"op": "set_managed_music", "sound": args["rendered_sound_path"],
                  "analysis": args["analysis_map_path"], "audio_record_run": audio_record.get("run_id")})

    wrapper = after["render_wrapper"]
    wrapper["cuts"] = [_ripple_section(row, f, d, "render_wrapper_cut", edits)
                       for row in wrapper.get("cuts", [])]
    sources = wrapper.get("source_sections", [])
    if len(sources) != 1:
        raise PlanError("RENDER_WRAPPER_MASTER_SOURCE_COUNT|%d" % len(sources))
    source = sources[0]
    source_start, source_end = [int(x) for x in source["range"]]
    if not source_start <= f < source_end:
        raise PlanError("RENDER_WRAPPER_MASTER_SOURCE_DOES_NOT_COVER_F")
    source["range"] = [source_start, source_end + d]
    wrapper["playback"] = [int(wrapper["playback"][0]), int(wrapper["playback"][1]) + d]
    edits += [
        {"op": "rebuild_managed_master", "later_passage_manual_shift": False},
        {"op": "materialize_changed_passage", "passage_guid": args["passage_guid"]},
        {"op": "check_adjacent_handoffs"},
        {"op": "rebuild_render_wrapper", "package": args["render_wrapper_package"],
         "source_locator": source["locator"], "source_range": source["range"],
         "playback": wrapper["playback"]},
    ]
    after["existing_breaths"].append({"start": f, "end": f + d, "source": "speed-zero-keys"})
    return {
        "schema_version": 1, "tool": TOOL, "tool_version": VERSION,
        "passage_guid": args["passage_guid"], "passage_start": start, "passage_old_end": end,
        "F": f, "F_relative": f - start, "D": d, "ease_frames": ease,
        "bounding_wing_pins": [span["wing_before_guid"], span["wing_after_guid"]],
        "containing_span": copy.deepcopy(span), "edits": edits,
        "named_packages": args["named_packages"], "before_digest": digest(snapshot),
        "after_digest": digest(after), "after_snapshot": after,
        "audio_record": {"run_id": audio_record.get("run_id"), "sha256": None},
        "later_passage_carry": "MANAGED_REBUILD_ONLY_NO_DOUBLE_SHIFT",
        "claims": [
            {"tier": "declaration-proven", "claim": "Passage section has exactly 13 channels.",
             "cite": "Plugins/InfinityStage/Source/InfinityStage/Public/MovieSceneInfinityPassageTrack.h:13-43"},
            {"tier": "inferred", "claim": "The edit list implements the P36 insertion/ripple design.",
             "cite": "Docs/Conductor/P36_BREATH_INSERT_TIME_REPORT.md:102-137"},
            {"tier": "inferred", "claim": "Rendered and rehearsal acceptance remain open.",
             "cite": "Docs/Conductor/P36_BREATH_INSERT_TIME_REPORT.md:149-165"},
        ],
    }


def validate_readback(wanted, actual, tolerance=1.0e-4, path="$", problems=None):
    """Recursive float32-aware read-back comparison."""
    problems = [] if problems is None else problems
    if isinstance(wanted, dict):
        if not isinstance(actual, dict) or set(wanted) != set(actual):
            problems.append("KEYS|%s" % path)
        else:
            for key in sorted(wanted):
                validate_readback(wanted[key], actual[key], tolerance, path + "." + str(key), problems)
    elif isinstance(wanted, list):
        if not isinstance(actual, list) or len(wanted) != len(actual):
            problems.append("LENGTH|%s" % path)
        else:
            for index, value in enumerate(wanted):
                validate_readback(value, actual[index], tolerance, "%s[%d]" % (path, index), problems)
    elif isinstance(wanted, float):
        if not isinstance(actual, (int, float)) or not close_numeric(wanted, actual, tolerance):
            problems.append("FLOAT|%s|%r!=%r" % (path, actual, wanted))
    elif wanted != actual:
        problems.append("VALUE|%s|%r!=%r" % (path, actual, wanted))
    return problems


def _png_chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_preview(plan, root, run):
    """Dependency-free timeline PNG. Analytical evidence, never a scene render."""
    width, height = 900, 180
    pixels = [bytearray([246, 243, 235] * width) for _ in range(height)]
    start, end = plan["passage_start"], plan["passage_old_end"] + plan["D"]
    def x(frame):
        return 50 + int((frame - start) * 800.0 / max(1, end - start))
    for yy in range(65, 116):
        for xx in range(x(plan["F"]), min(width, x(plan["F"] + plan["D"]))):
            pixels[yy][3 * xx:3 * xx + 3] = bytes((65, 105, 155))
    for frame, color in ((start, (30, 30, 30)), (plan["F"], (180, 55, 45)),
                         (plan["F"] + plan["D"], (180, 55, 45)), (end, (30, 30, 30))):
        xx = max(0, min(width - 1, x(frame)))
        for yy in range(45, 135):
            pixels[yy][3 * xx:3 * xx + 3] = bytes(color)
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    data = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b"")
    path = os.path.join(root, "breath_insert_preview_%s.png" % run)
    with open(path, "wb") as handle:
        handle.write(data)
    return path


class UnrealBackend(object):
    """Thin live adapter. All editor calls are confined to this injectable class.

    ``snapshot_provider`` and ``edit_executor`` are deliberately injected so the
    conductor can use the reviewed project-specific census/executor without
    allowing planning code to touch Unreal objects.  The adapter itself owns the
    required editor guards, package backup/save, rebuild and materialization.
    """
    def __init__(self, snapshot_provider=None, edit_executor=None):
        import unreal  # noqa: PLC0415 -- live-only boundary
        self.ue = unreal
        self.snapshot_provider = snapshot_provider
        self.edit_executor = edit_executor

    def log(self, text):
        self.ue.log(text)

    def stop(self, text):
        self.ue.log_error(text)

    def census(self):
        def path(value):
            text = str(value)
            return text.split(".", 1)[0]
        return {"content": sorted(path(x) for x in self.ue.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
                "maps": sorted(path(x) for x in self.ue.EditorLoadingAndSavingUtils.get_dirty_map_packages())}

    def preflight(self, args, mode):
        self.args = args
        if bool(self.ue.EditorLevelLibrary.editor_is_playing()):
            raise PlanError("PIE_OR_SIE_ACTIVE")
        current = self.ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
        if current is not None:
            raise PlanError("SEQUENCER_OPEN")
        if self.census() != {"content": [], "maps": []}:
            raise PlanError("DIRTY_CENSUS|%s" % canonical(self.census()))
        world = self.ue.get_editor_subsystem(self.ue.UnrealEditorSubsystem).get_editor_world()
        if str(world.get_path_name()).split(".", 1)[0] != args["level_package"]:
            raise PlanError("WRONG_WORLD|%s" % world.get_path_name())

    def inspect(self, args):
        if self.snapshot_provider is None:
            raise PlanError("LIVE_SNAPSHOT_PROVIDER_REQUIRED|must census all P45 holders")
        return self.snapshot_provider(self.ue, args)

    def backup(self, run, packages, prefix="PreBreathInsert"):
        project = os.path.abspath(self.ue.Paths.project_dir())
        root = os.path.join(project, "Backups", "%s-%s" % (prefix, run))
        os.makedirs(root, exist_ok=False)
        files = []
        for package in packages:
            rel = package[len("/Game/"):].split("/") if package.startswith("/Game/") else None
            if rel is None:
                raise PlanError("BACKUP_NON_GAME_PACKAGE|%s" % package)
            candidates = [os.path.join(project, "Content", *rel) + ext for ext in (".uasset", ".umap")]
            source = next((x for x in candidates if os.path.isfile(x)), None)
            if source is None:
                raise PlanError("BACKUP_SOURCE_MISSING|%s" % package)
            target = os.path.join(root, os.path.basename(source))
            shutil.copy2(source, target)
            if os.path.getsize(source) != os.path.getsize(target) or sha256_file(source) != sha256_file(target):
                raise PlanError("BACKUP_VERIFY_FAILED|%s" % package)
            files.append({"package": package, "source": source, "backup": target,
                          "bytes": os.path.getsize(target), "sha256": sha256_file(target)})
        write_json(os.path.join(root, "manifest.json"), {"run": run, "files": files}, exclusive=True)
        return {"root": root, "files": files}

    def apply(self, plan, args):
        if self.edit_executor is None:
            raise PlanError("LIVE_EDIT_EXECUTOR_REQUIRED|must execute exact P45 edit list")
        result = self.edit_executor(self.ue, plan["edits"], args)
        show = self.ue.load_asset(args["show_package"])
        master = self.ue.load_asset(args["master_package"])
        rebuilt = self.ue.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
        if not rebuilt:
            raise PlanError("REBUILD_MANAGED_MASTER_FAILED")
        world = self.ue.get_editor_subsystem(self.ue.UnrealEditorSubsystem).get_editor_world()
        actors = [a for a in self.ue.get_editor_subsystem(self.ue.EditorActorSubsystem).get_all_level_actors()
                  if isinstance(a, self.ue.InfinityStagePassageActor)]
        matched = [a for a in actors if str(a.get_editor_property("passage_guid")).replace("-", "").upper()
                   == plan["passage_guid"]]
        if len(matched) != 1 or not matched[0].materialize_passage():
            raise PlanError("MATERIALIZE_CHANGED_PASSAGE_FAILED|%d" % len(matched))
        handoffs = self.ue.InfinityStageSequenceBuilderLibrary.check_scene_handoffs(show, world)
        if not handoffs:
            raise PlanError("HANDOFF_CHECK_FAILED")
        return result

    def save(self, packages):
        census = self.census()
        dirty = sorted(set(census["content"] + census["maps"]))
        if dirty != sorted(packages):
            raise PlanError("UNEXPECTED_DIRTY_PACKAGES|got=%s|want=%s" % (dirty, sorted(packages)))
        for package in packages:
            if package == self.args["level_package"]:
                ok = self.ue.get_editor_subsystem(self.ue.LevelEditorSubsystem).save_current_level()
            else:
                ok = self.ue.EditorAssetLibrary.save_asset(package, only_if_is_dirty=True)
            if not ok:
                raise PlanError("SAVE_FAILED|%s" % package)
        if self.census() != {"content": [], "maps": []}:
            raise PlanError("DIRTY_AFTER_SAVE|%s" % canonical(self.census()))
        return list(packages)

    def revert(self, record, args):
        if self.edit_executor is None:
            raise PlanError("LIVE_EDIT_EXECUTOR_REQUIRED")
        result = self.edit_executor(self.ue, [{"op": "restore_snapshot", "snapshot": record["snapshot_before"]}], args)
        show = self.ue.load_asset(args["show_package"])
        master = self.ue.load_asset(args["master_package"])
        if not self.ue.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master):
            raise PlanError("REVERT_REBUILD_MANAGED_MASTER_FAILED")
        world = self.ue.get_editor_subsystem(self.ue.UnrealEditorSubsystem).get_editor_world()
        actors = [a for a in self.ue.get_editor_subsystem(self.ue.EditorActorSubsystem).get_all_level_actors()
                  if isinstance(a, self.ue.InfinityStagePassageActor)]
        matched = [a for a in actors if str(a.get_editor_property("passage_guid")).replace("-", "").upper()
                   == record["plan"]["passage_guid"]]
        if len(matched) != 1 or not matched[0].materialize_passage():
            raise PlanError("REVERT_MATERIALIZE_FAILED|%d" % len(matched))
        return result


def _root(tool_root=None):
    return os.path.abspath(tool_root or os.path.dirname(__file__))


def _stop(backend, run, reason):
    message = "%s_STOPPED|run=%s|reason=%s" % (TOOL, run, reason)
    backend.stop(message)
    raise Stop(message)


def _expected_confirm(mode, run, source_run):
    if mode == "REVERT":
        return "REVERT BREATH %s" % source_run
    return "%s BREATH %s" % (mode, run)


def _plan_from_live(args, backend):
    snapshot = backend.inspect(args)
    record = read_json(args["audio_apply_record"])
    plan = build_plan(snapshot, record, args)
    plan["audio_record"]["sha256"] = sha256_file(args["audio_apply_record"])
    return snapshot, plan


def run_dry(run, args, backend, root):
    backend.preflight(args, "DRY")
    snapshot, plan = _plan_from_live(args, backend)
    report_path = os.path.join(root, "breath_insert_dry_%s.json" % run)
    preview = write_preview(plan, root, run)
    report = {"schema_version": 1, "mode": "DRY", "run_id": run, "apply_ready": True,
              "dirty_package_census": backend.census(), "snapshot_digest": digest(snapshot),
              "plan": plan, "preview": preview,
              "proof": "measured-offline plan only; saved-Unreal and rendered acceptance open"}
    write_json(report_path, report)
    write_json(os.path.join(root, PLAN_NAME), {"run_id": run, "snapshot_digest": digest(snapshot),
                                                "plan_digest": digest(plan), "args": args,
                                                "report": report_path})
    if backend.census() != {"content": [], "maps": []}:
        _stop(backend, run, "DRY_DIRTIED|%s" % canonical(backend.census()))
    backend.log("P36_BREATH_DRY_OK|run=%s|F=%d|D=%d|edits=%d|writes=0|report=%s|preview=%s" %
                (run, plan["F"], plan["D"], len(plan["edits"]), report_path, preview))
    return report


def _record_path(root, source_run):
    return os.path.join(root, "breath_insert_record_%s.json" % source_run)


def run_apply(run, args, backend, root):
    backend.preflight(args, "APPLY")
    snapshot, plan = _plan_from_live(args, backend)
    dry = read_json(os.path.join(root, PLAN_NAME))
    if dry.get("snapshot_digest") != digest(snapshot) or dry.get("plan_digest") != digest(plan):
        _stop(backend, run, "CHANGED_SINCE_DRY|rerun DRY")
    record_path = _record_path(root, run)
    if os.path.exists(record_path):
        _stop(backend, run, "RECORD_EXISTS|%s" % record_path)
    backup = backend.backup(run, plan["named_packages"])
    record = {"schema_version": 1, "tool": TOOL, "run_id": run, "status": "prepared",
              "args": args, "backup": backup, "plan": plan, "snapshot_before": snapshot,
              "snapshot_before_digest": digest(snapshot)}
    write_json(record_path, record, exclusive=True)  # record exists before first mutation
    backend.apply(plan, args)
    presave = backend.inspect(args)
    problems = validate_readback(plan["after_snapshot"], presave)
    expected_dirty = sorted(plan["named_packages"])
    census = backend.census()
    if problems or sorted(set(census["content"] + census["maps"])) != expected_dirty:
        _stop(backend, run, "PRESAVE_READBACK|problems=%s|census=%s|NOTHING SAVED; Don't-Save restart; backup=%s" %
              (problems[:20], canonical(census), backup["root"]))
    saves = backend.save(plan["named_packages"])
    final = backend.inspect(args)
    problems = validate_readback(plan["after_snapshot"], final)
    if problems or backend.census() != {"content": [], "maps": []}:
        _stop(backend, run, "POSTSAVE_READBACK|%s|restore=%s" % (problems[:20], backup["root"]))
    record.update({"status": "saved_readback_verified", "snapshot_after": final,
                   "snapshot_after_digest": digest(final), "saved": saves,
                   "dirty_package_census_after": backend.census()})
    write_json(record_path, record)
    backend.log("P36_BREATH_APPLY_OK|run=%s|F=%d|D=%d|later_carry=rebuild_only|saved=%s|backup=%s|record=%s" %
                (run, plan["F"], plan["D"], ",".join(saves), backup["root"], record_path))
    return record


def run_revert(run, source_run, args, backend, root):
    backend.preflight(args, "REVERT")
    path = _record_path(root, source_run)
    record = read_json(path)
    if record.get("status") != "saved_readback_verified" or record.get("run_id") != source_run:
        _stop(backend, run, "REVERT_RECORD_CONTEXT")
    current = backend.inspect(args)
    if validate_readback(record["snapshot_after"], current):
        _stop(backend, run, "STATE_DRIFTED_SINCE_APPLY|restore=%s" % record["backup"]["root"])
    backup = backend.backup(run, record["plan"]["named_packages"], "PreBreathInsertRevert")
    txn = os.path.join(root, "breath_insert_revert_%s.json" % run)
    write_json(txn, {"status": "prepared", "run_id": run, "source_run_id": source_run,
                     "backup": backup}, exclusive=True)
    backend.revert(record, args)
    before_save = backend.inspect(args)
    problems = validate_readback(record["snapshot_before"], before_save)
    census = backend.census()
    expected = sorted(record["plan"]["named_packages"])
    if problems or sorted(set(census["content"] + census["maps"])) != expected:
        _stop(backend, run, "REVERT_PRESAVE|%s|NOTHING SAVED; Don't-Save restart" % problems[:20])
    saves = backend.save(record["plan"]["named_packages"])
    final = backend.inspect(args)
    problems = validate_readback(record["snapshot_before"], final)
    if problems or backend.census() != {"content": [], "maps": []}:
        _stop(backend, run, "REVERT_POSTSAVE|%s|restore=%s" % (problems[:20], backup["root"]))
    archived = path + ".reverted-" + run
    os.rename(path, archived)
    write_json(txn, {"status": "saved_readback_verified", "run_id": run, "source_run_id": source_run,
                     "backup": backup, "archived_record": archived, "saved": saves})
    backend.log("P36_BREATH_REVERT_OK|run=%s|source=%s|exact=1|saved=%s|backup=%s|record=%s" %
                (run, source_run, ",".join(saves), backup["root"], archived))
    return {"archived_record": archived, "backup": backup, "saved": saves}


def main(raw, backend=None, tool_root=None):
    raw = copy.deepcopy(raw or {})
    mode = str(raw.get("mode", "DRY")).upper()
    run = str(raw.get("run_id") or datetime.datetime.now().strftime("BREATH-%Y%m%d-%H%M%S"))
    source_run = str(raw.get("source_run_id") or "")
    backend = backend or UnrealBackend()
    root = _root(tool_root)
    try:
        expected = _expected_confirm(mode, run, source_run)
        if str(raw.get("confirm", "")) != expected:
            _stop(backend, run, "CONFIRM_MISMATCH|want=%r|got=%r" % (expected, raw.get("confirm")))
        args = _normalise_args(raw.get("params") or {})
        if mode == "DRY":
            return run_dry(run, args, backend, root)
        if mode == "APPLY":
            return run_apply(run, args, backend, root)
        if mode == "REVERT":
            if not source_run:
                _stop(backend, run, "SOURCE_RUN_REQUIRED")
            return run_revert(run, source_run, args, backend, root)
        _stop(backend, run, "MODE|%s" % mode)
    except PlanError as error:
        _stop(backend, run, "PLAN_REFUSED|%s" % error)
