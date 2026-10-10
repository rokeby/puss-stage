"""Codex job 94: gate the P03 -> S3 arrival until the crowd is settled.

Offline-authored only.  The conductor runs this through ExecuteProjectPythonFile.

Modes / exact confirmations:
  DRY    / ``DRY P94S3ARRIVAL``
  APPLY  / ``APPLY P94S3ARRIVAL``
  REVERT / ``REVERT P94S3ARRIVAL``

The tool coordinates three existing authorities instead of creating a fourth:
LS_S3_HangarRise owns the hangar lights, LS_Clams owns the 15 crowd-copy
visibility tracks, and LS_DevScene_03 owns the fire lights/visibility.  It does
not create actors, delete bindings, rename existing bindings, or touch a map.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness imports this module.
    unreal = None


MARK = "P94_S3_ARRIVAL"
VERSION = "2026-10-10-job132"
FOLDER = "P94S3Arrival_20261009"
ROOT = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
CLAMS = "/Game/Scenes/LS_Clams"
PACKAGES = (ROOT, RISE, CLAMS)
FILES = {
    ROOT: "InfinityStage/Dev/Sequences/LS_DevScene_03.uasset",
    RISE: "InfinityStage/RigAtmos/LS_S3_HangarRise.uasset",
    CLAMS: "Scenes/LS_Clams.uasset",
}
CONFIRMS = {mode: "%s P94S3ARRIVAL" % mode for mode in ("DRY", "APPLY", "REVERT")}
DEFAULTS = {
    "crowd_copy_count": 15,
    "crowd_visible_root_frame": 360,
    "crowd_to_clams_offset": 22,
    "settle_padding_frames": 12,
    "rise_duration_frames": 72,
    "fire_labels": ["S3 Ghost Light Flame", "S3 Fire B", "S3 Fire C"],
    "fire_light_labels": ["S3 Ghost Light", "S3 Fire B Light", "S3 Fire C Light"],
    "crowd_light_labels": [
        "S3 Crowd Key A", "S3 Crowd Rim A", "S3 Crowd Key B",
        "S3 Crowd Rim B", "S3 Crowd Key C", "S3 Crowd Rim C",
    ],
    "wave_owner_prefix": "S3 WaveV3 ",
    "wave_light_count": 10,
    "wave_source_start_frame": 360,
    "wave_source_full_frame": 384,
    "unmanaged_effect_tokens": ["smoke", "haze", "fog"],
    "allowed_unmanaged_effect_labels": [],
    "value_tolerance": 0.0001,
}
RISE_FAMILIES = {
    "practical": ("S3 Practical ", 14),
    "lattice": ("S3 Lattice Glow ", 24),
    "strike": ("S3 Strike ", 6),
    "uplight": ("S3 Uplight ", 3),
    "daylight": ("S3 Daylight ", 2),
}


class Stop(RuntimeError):
    pass


class PlanError(ValueError):
    pass


def enum_token(value):
    """Normalise UE 5.8 enum strings such as '<E.V: 2>' to 'V'."""
    raw = str(getattr(value, "name", value)).strip()
    raw = raw.strip("<>")
    raw = raw.split(":", 1)[0]
    return raw.rsplit(".", 1)[-1].strip().upper()


def canonical_channel_name(value):
    """UE appends numeric suffixes to otherwise equivalent channel names."""
    return re.sub(r"(?:[_ .-]\d+)$", "", str(value or "").strip()).casefold()


def merged_params(raw):
    params = dict(DEFAULTS)
    params.update(raw or {})
    for key in ("crowd_copy_count", "crowd_visible_root_frame", "crowd_to_clams_offset",
                "settle_padding_frames", "rise_duration_frames", "wave_light_count",
                "wave_source_start_frame", "wave_source_full_frame"):
        params[key] = int(params[key])
    params["value_tolerance"] = float(params["value_tolerance"])
    if params["crowd_copy_count"] != 15:
        raise PlanError("CROWD_COPY_COUNT_MUST_MATCH_APPLIED_P21|15")
    if params["settle_padding_frames"] < 0:
        raise PlanError("SETTLE_PADDING_NEGATIVE")
    if not 24 <= params["rise_duration_frames"] <= 144:
        raise PlanError("RISE_DURATION_OUTSIDE_1_TO_6_SECONDS")
    if params["value_tolerance"] <= 0:
        raise PlanError("VALUE_TOLERANCE_NONPOSITIVE")
    params["light_rise_root_frame"] = params["crowd_visible_root_frame"] + params["settle_padding_frames"]
    params["light_full_root_frame"] = params["light_rise_root_frame"] + params["rise_duration_frames"]
    # The parent is 24 fps and the nested hangar sequence is 30 fps.
    params["light_rise_child_frame"] = root_to_child(params["light_rise_root_frame"])
    params["light_full_child_frame"] = root_to_child(params["light_full_root_frame"])
    return params


def root_to_child(frame, parent_fps=24, child_fps=30):
    value = int(frame) * int(child_fps)
    if value % int(parent_fps):
        raise PlanError("NONINTEGRAL_PARENT_CHILD_FRAME|%s" % frame)
    return value // int(parent_fps)


def retime_pairs(frames, values, start, end):
    """Plan a dark hold followed by one gentle ramp without changing values."""
    frames = [int(x) for x in frames]
    values = [float(x) for x in values]
    if len(frames) != len(values) or len(frames) not in (2, 3):
        raise PlanError("LIGHT_KEY_SHAPE|frames=%r|values=%r" % (frames, values))
    if frames != sorted(frames) or abs(values[0]) > 1.0e-4:
        raise PlanError("LIGHT_KEYS_NOT_DARK_LEADING|%r|%r" % (frames, values))
    if len(frames) == 2:
        planned = [int(start), int(end)]
    else:
        if abs(values[1]) > 1.0e-4:
            raise PlanError("LIGHT_SECOND_KEY_NOT_DARK|%r" % values)
        planned = [frames[0], int(start), int(end)]
    if len(set(planned)) != len(planned) or planned != sorted(planned):
        raise PlanError("LIGHT_RETIME_COLLISION|%r" % planned)
    return planned


def shift_from(frames, threshold, target, playback_end):
    """Delay every fire key from its first reveal while preserving key count."""
    frames = [int(x) for x in frames]
    threshold, target, playback_end = int(threshold), int(target), int(playback_end)
    if target < threshold:
        raise PlanError("FIRE_TARGET_BEFORE_SOURCE")
    delta = target - threshold
    out = [f if f < threshold else f + delta for f in frames]
    # Keys beyond playback are deliberately retained.  Dropping them would make
    # an exact REVERT impossible and could erase authored tail flicker if the
    # sequence is extended later.
    del playback_end
    return out, delta


def stretch_window(frames, old_start, old_end, new_start, new_end):
    """Move and stretch an arrival ramp; shift its later tail without deletion."""
    old_start, old_end = int(old_start), int(old_end)
    new_start, new_end = int(new_start), int(new_end)
    if not old_start < old_end or not new_start < new_end or new_start < old_start:
        raise PlanError("STRETCH_WINDOW_ORDER")
    out = []
    for frame in [int(x) for x in frames]:
        if frame < old_start:
            planned = frame
        elif frame <= old_end:
            alpha = (frame - old_start) / float(old_end - old_start)
            planned = int(round(new_start + alpha * (new_end - new_start)))
        else:
            planned = frame + (new_end - old_end)
        out.append(planned)
    if out != sorted(out) or len(set(out)) != len(out):
        raise PlanError("STRETCH_WINDOW_COLLISION|%r" % out)
    return out


def gate_values(frames, values, source_start, new_start, new_end):
    """Keep key times fixed; suppress an early curve and apply a later envelope."""
    frames = [int(x) for x in frames]
    values = [float(x) for x in values]
    if len(frames) != len(values) or not int(source_start) <= int(new_start) < int(new_end):
        raise PlanError("GATE_VALUE_SHAPE_OR_ORDER")
    out = []
    for frame, value in zip(frames, values):
        if int(source_start) <= frame < int(new_start):
            out.append(0.0)
        elif int(new_start) <= frame <= int(new_end):
            out.append(value * (frame - int(new_start)) / float(int(new_end) - int(new_start)))
        else:
            out.append(value)
    return out


def plan_wave_gate(frames, values, source_start, new_start, new_end, tolerance=1.0e-4):
    """Gate old and live late-start WaveV3 curves without inventing a binding or key.

    Older rect curves have an exact dark key at ``source_start``.  Newer warm
    side curves have one dark frame-0 anchor followed by dense lit keys late in
    the requested rise.  In that live shape, move only the dark anchor to the
    new rise start so LINEAR interpolation cannot illuminate the scene early.
    """
    frames = [int(x) for x in frames]
    values = [float(x) for x in values]
    source_start, new_start, new_end = int(source_start), int(new_start), int(new_end)
    if len(frames) != len(values) or len(frames) < 2 or frames != sorted(frames) or len(set(frames)) != len(frames):
        raise PlanError("WAVE_KEY_SHAPE|frames=%r|values=%r" % (frames[:12], values[:12]))
    if not source_start <= new_start < new_end:
        raise PlanError("WAVE_GATE_ORDER")
    planned_frames = list(frames)
    if source_start in frames:
        anchor_index = frames.index(source_start)
        if abs(values[anchor_index]) > tolerance:
            raise PlanError("WAVE_START_NOT_DARK|frame=%d|value=%s" %
                            (source_start, values[anchor_index]))
        mode = "exact_source_key"
        gate_start = source_start
    else:
        first_nonzero = next((i for i, value in enumerate(values) if abs(value) > tolerance), None)
        if first_nonzero is None:
            raise PlanError("WAVE_NO_NONZERO")
        first_nonzero_frame = frames[first_nonzero]
        anchors = [i for i in range(first_nonzero)
                   if frames[i] <= new_start and abs(values[i]) <= tolerance]
        if not anchors:
            raise PlanError("WAVE_NO_DARK_ANCHOR|frames=%r" % frames[:12])
        if first_nonzero_frame <= new_start or first_nonzero_frame > new_end:
            raise PlanError("WAVE_LATE_START_OUTSIDE_RISE|first=%d|rise=%d-%d" %
                            (first_nonzero_frame, new_start, new_end))
        anchor_index = anchors[-1]
        planned_frames[anchor_index] = new_start
        if planned_frames != sorted(planned_frames) or len(set(planned_frames)) != len(planned_frames):
            raise PlanError("WAVE_DARK_ANCHOR_COLLISION|frames=%r" % planned_frames[:12])
        mode = "retime_dark_anchor"
        gate_start = new_start
    return {"frames": planned_frames,
            "values": gate_values(planned_frames, values, gate_start, new_start, new_end),
            "source_mode": mode, "dark_anchor_before": frames[anchor_index],
            "dark_anchor_after": planned_frames[anchor_index]}


def _ue():
    if unreal is None:
        raise RuntimeError("UNREAL_MODULE_REQUIRED")
    return unreal


def _guid(value):
    # Never str(FGuid): UE 5.8 has returned an address-bearing value that changes per call.
    return str(_ue().GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def _path(value):
    try:
        return str(value.get_path_name()).split(".", 1)[0]
    except Exception:  # noqa: BLE001
        return str(value).split(".", 1)[0]


def _rate(value):
    return float(value.numerator) / float(value.denominator)


def _saved_root():
    return _ue().Paths.convert_relative_path_to_full(_ue().Paths.project_saved_dir())


def _project_root():
    return _ue().Paths.convert_relative_path_to_full(_ue().Paths.project_dir())


def _here():
    return os.path.join(_saved_root(), "CodexConductor", FOLDER)


def _record_path():
    return os.path.join(_here(), "p94_record.json")


def _plan_path(run):
    return os.path.join(_here(), "p94_plan_%s.json" % run)


def _json(path, value=None):
    if value is None:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False, default=str)
        handle.write("\n")
    os.replace(temp, path)


def _sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _files():
    return {package: os.path.join(_project_root(), "Content", *relative.split("/"))
            for package, relative in FILES.items()}


def _census():
    lib = _ue().EditorLoadingAndSavingUtils
    return {
        "content": sorted(_path(x) for x in lib.get_dirty_content_packages()),
        "maps": sorted(_path(x) for x in lib.get_dirty_map_packages()),
    }


def _stop(run, reason):
    message = "%s_STOP|run=%s|%s" % (MARK, run, reason)
    if unreal is not None:
        unreal.log_error(message)
    raise Stop(message)


def _preflight(args, mode, run):
    if CONFIRMS.get(mode) != str(args.get("confirm", "")).strip():
        _stop(run, "CONFIRM|want=%s" % CONFIRMS.get(mode))
    editor = _ue().get_editor_subsystem(_ue().UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    if _ue().LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_OPEN")
    world = editor.get_editor_world()
    if "L_InfinityStage_V1VerticalSlice" not in _path(world):
        _stop(run, "WRONG_WORLD|%s" % _path(world))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AT_START|%s" % json.dumps(_census(), sort_keys=True))
    if mode in ("DRY", "APPLY") and os.path.isfile(_record_path()):
        _stop(run, "ACTIVE_RECORD_EXISTS|%s" % _record_path())
    if mode == "REVERT" and not os.path.isfile(_record_path()):
        _stop(run, "REVERT_RECORD_MISSING")
    return world


def _load_sequences(run):
    rows = {path: _ue().load_asset(path) for path in PACKAGES}
    if any(value is None for value in rows.values()):
        _stop(run, "SEQUENCE_LOAD|%s" % [k for k, v in rows.items() if v is None])
    expected = {ROOT: 24.0, RISE: 30.0, CLAMS: 24.0}
    for path, sequence in rows.items():
        if abs(_rate(sequence.get_display_rate()) - expected[path]) > 1.0e-9:
            _stop(run, "DISPLAY_RATE|%s|%s" % (path, _rate(sequence.get_display_rate())))
    return rows


def _property_token(value):
    """Map Python None and UE's post-string NAME_None sentinel to unbound."""
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text == "None" else text


def _track_property(track):
    try:
        name = track.get_property_name()
        path = track.get_property_path()
        return _property_token(name), _property_token(path)
    except Exception:  # noqa: BLE001
        return "", ""


def _binding_rows(sequence):
    rows = []
    for binding in sequence.get_bindings():
        parent = binding.get_parent()
        parent_name = str(parent.get_display_name()) if parent is not None and parent.is_valid() else ""
        rows.append({"binding": binding, "guid": _guid(binding.get_id()),
                     "name": str(binding.get_display_name()), "parent": parent_name})
    return rows


def _owner(row):
    return row["parent"] or row["name"]


def _key_frame(key):
    time = key.get_time(time_unit=_ue().MovieSceneTimeUnit.DISPLAY_RATE)
    return int(time.frame_number.value)


def _key_value(key, boolean=False):
    return bool(key.get_value()) if boolean else float(key.get_value())


def _channel_name(channel):
    return str(getattr(channel, "channel_name", ""))


def _track_snapshot(row, track, sequence, boolean=False):
    prop, path = _track_property(track)
    sections = []
    for section_index, section in enumerate(track.get_sections()):
        channels = list(section.get_all_channels())
        if len(channels) != 1:
            raise PlanError("CHANNEL_COUNT|%s|%s" % (_owner(row), len(channels)))
        channel = channels[0]
        sections.append({
            "index": section_index,
            "range": [int(section.get_start_frame()) if section.has_start_frame() else None,
                      int(section.get_end_frame()) if section.has_end_frame() else None],
            "active": bool(section.is_active()),
            "channel": _channel_name(channel),
            "channel_canonical": canonical_channel_name(_channel_name(channel)),
            "keys": [[_key_frame(key), _key_value(key, boolean)] for key in channel.get_keys()],
        })
    return {"binding_guid": row["guid"], "binding": row["name"], "owner": _owner(row),
            "track_index": list(row["binding"].get_tracks()).index(track),
            "track_class": track.get_class().get_name(), "display": str(track.get_display_name()),
            "property": prop, "path": path, "sections": sections}


def _single_channel(track, label, run):
    sections = list(track.get_sections())
    if len(sections) != 1:
        _stop(run, "SECTION_COUNT|%s|%d" % (label, len(sections)))
    channels = list(sections[0].get_all_channels())
    if len(channels) != 1:
        _stop(run, "CHANNEL_COUNT|%s|%d" % (label, len(channels)))
    return sections[0], channels[0]


def _find_track(sequence, owner, class_name, prop, run):
    found = []
    for row in _binding_rows(sequence):
        if _owner(row) != owner:
            continue
        for track in row["binding"].get_tracks():
            got_prop, got_path = _track_property(track)
            if track.get_class().get_name() == class_name and (prop is None or got_prop == prop):
                found.append((row, track, got_prop, got_path))
    if len(found) != 1:
        _stop(run, "TRACK_COUNT|%s|%s|%s|%d" % (owner, class_name, prop, len(found)))
    return found[0]


def _rise_census(sequence, params, run):
    targets, counts = [], {}
    for family, (prefix, expected) in RISE_FAMILIES.items():
        matches = []
        for row in _binding_rows(sequence):
            if not _owner(row).startswith(prefix):
                continue
            for track in row["binding"].get_tracks():
                prop, path = _track_property(track)
                if track.get_class().get_name() == "MovieSceneFloatTrack" and prop == "Intensity":
                    if path != "Intensity":
                        _stop(run, "INTENSITY_PATH|%s|%s" % (_owner(row), path))
                    section, channel = _single_channel(track, _owner(row), run)
                    keys = list(channel.get_keys())
                    frames = [_key_frame(key) for key in keys]
                    values = [_key_value(key) for key in keys]
                    planned = retime_pairs(frames, values, params["light_rise_child_frame"],
                                           params["light_full_child_frame"])
                    matches.append({"row": row, "track": track, "section": section, "channel": channel,
                                    "before": _track_snapshot(row, track, sequence), "frames": frames,
                                    "values": values, "planned_frames": planned, "family": family})
        counts[family] = len(matches)
        if len(matches) != expected:
            _stop(run, "RISE_FAMILY_COUNT|%s|got=%d|want=%d" % (family, len(matches), expected))
        targets.extend(matches)
    if len(targets) != 49:
        _stop(run, "RISE_TOTAL|got=%d|want=49" % len(targets))
    return targets, counts


def _crowd_census(sequence, params, run):
    found = []
    expected_frame = params["crowd_visible_root_frame"] + params["crowd_to_clams_offset"]
    for row in _binding_rows(sequence):
        if not row["name"].startswith("S3 Crowd "):
            continue
        for track in row["binding"].get_tracks():
            if track.get_class().get_name() != "MovieSceneVisibilityTrack":
                continue
            section, channel = _single_channel(track, row["name"], run)
            keys = [[_key_frame(key), bool(key.get_value())] for key in channel.get_keys()]
            shown = [frame for frame, value in keys if value]
            if shown != [expected_frame]:
                _stop(run, "CROWD_VISIBLE_FRAME|%s|got=%s|want=%d" % (row["name"], shown, expected_frame))
            prop, path = _track_property(track)
            if (prop, path) not in (("", ""), ("bHidden", "bHidden")):
                _stop(run, "CROWD_VIS_PROPERTY|%s|%s|%s" % (row["name"], prop, path))
            found.append({"row": row, "track": track, "section": section, "channel": channel,
                          "before": _track_snapshot(row, track, sequence, True),
                          "needs_bind": (prop, path) != ("bHidden", "bHidden")})
    if len(found) != params["crowd_copy_count"]:
        _stop(run, "CROWD_VIS_COUNT|got=%d|want=%d" % (len(found), params["crowd_copy_count"]))
    return found


def _fire_census(sequence, params, run):
    rows = {"visibility": [], "light": []}
    playback_end = int(sequence.get_playback_end())
    for label in params["fire_labels"]:
        row, track, prop, path = _find_track(sequence, label, "MovieSceneVisibilityTrack", "bHidden", run)
        if path != "bHidden":
            _stop(run, "FIRE_VIS_PATH|%s|%s" % (label, path))
        section, channel = _single_channel(track, label, run)
        keys = list(channel.get_keys())
        shown = [_key_frame(key) for key in keys if bool(key.get_value())]
        if len(shown) != 1:
            _stop(run, "FIRE_SHOW_KEY|%s|%s" % (label, shown))
        planned, delta = shift_from([_key_frame(key) for key in keys], shown[0],
                                    params["light_rise_root_frame"], playback_end)
        rows["visibility"].append({"row": row, "track": track, "section": section, "channel": channel,
                                   "before": _track_snapshot(row, track, sequence, True),
                                   "source_reveal": shown[0], "planned_frames": planned, "delta": delta})
    for label in params["fire_light_labels"]:
        row, track, prop, path = _find_track(sequence, label, "MovieSceneFloatTrack", "Intensity", run)
        if path != "Intensity":
            _stop(run, "FIRE_LIGHT_PATH|%s|%s" % (label, path))
        section, channel = _single_channel(track, label, run)
        keys = list(channel.get_keys())
        frames = [_key_frame(key) for key in keys]
        nonzero = [_key_frame(key) for key in keys if abs(float(key.get_value())) > params["value_tolerance"]]
        if not nonzero:
            _stop(run, "FIRE_LIGHT_NO_NONZERO|%s" % label)
        zero_before = max((f for f, key in zip(frames, keys)
                           if f <= nonzero[0] and abs(float(key.get_value())) <= params["value_tolerance"]), default=None)
        if zero_before is None:
            _stop(run, "FIRE_LIGHT_NO_DARK_KEY|%s" % label)
        planned, delta = shift_from(frames, zero_before, params["light_rise_root_frame"], playback_end)
        rows["light"].append({"row": row, "track": track, "section": section, "channel": channel,
                              "before": _track_snapshot(row, track, sequence), "source_reveal": zero_before,
                              "planned_frames": planned, "delta": delta})
    return rows


def _root_arrival_light_census(sequence, params, run):
    """Six crowd lights and ten WaveV3 rects that currently begin at frame 360."""
    result = {"crowd": [], "waves": []}
    for label in params["crowd_light_labels"]:
        row, track, _prop, path = _find_track(sequence, label, "MovieSceneFloatTrack", "Intensity", run)
        if path != "Intensity":
            _stop(run, "CROWD_LIGHT_PATH|%s|%s" % (label, path))
        section, channel = _single_channel(track, label, run)
        keys = list(channel.get_keys())
        frames = [_key_frame(key) for key in keys]
        values = [float(key.get_value()) for key in keys]
        first_nonzero_index = next((i for i, value in enumerate(values)
                                    if abs(value) > params["value_tolerance"]), None)
        if first_nonzero_index is None or first_nonzero_index == 0:
            _stop(run, "CROWD_LIGHT_RAMP|%s" % label)
        zero_index = first_nonzero_index - 1
        if frames[zero_index] != params["crowd_visible_root_frame"] or abs(values[zero_index]) > params["value_tolerance"]:
            _stop(run, "CROWD_LIGHT_START|%s|%s|%s" % (label, frames[zero_index], values[zero_index]))
        planned = list(frames)
        planned[zero_index] = params["light_rise_root_frame"]
        planned[first_nonzero_index] = params["light_full_root_frame"]
        if planned != sorted(planned) or len(set(planned)) != len(planned):
            _stop(run, "CROWD_LIGHT_COLLISION|%s|%s" % (label, planned))
        result["crowd"].append({"row": row, "track": track, "section": section, "channel": channel,
                                "before": _track_snapshot(row, track, sequence), "frames": frames,
                                "planned_frames": planned})
    wave_hits = []
    for row in _binding_rows(sequence):
        if not _owner(row).startswith(params["wave_owner_prefix"]):
            continue
        for track in row["binding"].get_tracks():
            prop, path = _track_property(track)
            if track.get_class().get_name() != "MovieSceneFloatTrack" or prop != "Intensity":
                continue
            if path != "Intensity":
                _stop(run, "WAVE_LIGHT_PATH|%s|%s" % (_owner(row), path))
            section, channel = _single_channel(track, _owner(row), run)
            keys = list(channel.get_keys())
            frames = [_key_frame(key) for key in keys]
            values = [float(key.get_value()) for key in keys]
            try:
                wave_plan = plan_wave_gate(frames, values, params["wave_source_start_frame"],
                                           params["light_rise_root_frame"], params["light_full_root_frame"],
                                           params["value_tolerance"])
            except PlanError as exc:
                _stop(run, "%s|%s" % (exc, _owner(row)))
            wave_hits.append({"row": row, "track": track, "section": section, "channel": channel,
                              "before": _track_snapshot(row, track, sequence), "frames": frames,
                              "planned_frames": wave_plan["frames"], "planned_values": wave_plan["values"],
                              "source_mode": wave_plan["source_mode"],
                              "dark_anchor_before": wave_plan["dark_anchor_before"],
                              "dark_anchor_after": wave_plan["dark_anchor_after"]})
    if len(wave_hits) != params["wave_light_count"]:
        _stop(run, "WAVE_LIGHT_COUNT|got=%d|want=%d" % (len(wave_hits), params["wave_light_count"]))
    result["waves"] = wave_hits
    return result


def _effect_census(world, params):
    tokens = tuple(str(x).casefold() for x in params["unmanaged_effect_tokens"])
    allowed = set(str(x) for x in params["allowed_unmanaged_effect_labels"])
    fire = set(params["fire_labels"])
    found = []
    actors = _ue().get_editor_subsystem(_ue().EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        label = str(actor.get_actor_label())
        low = label.casefold()
        if label in fire:
            continue
        if ("s3" in low or "p03" in low) and any(token in low for token in tokens):
            found.append(label)
    found = sorted(set(found))
    return {"candidates": found, "allowed": sorted(allowed),
            "unexpected": sorted(set(found) - allowed), "world": _path(world)}


def _public(target):
    return {k: v for k, v in target.items() if k not in ("row", "track", "section", "channel")}


def _build_plan(sequences, world, params, run):
    rise, counts = _rise_census(sequences[RISE], params, run)
    crowd = _crowd_census(sequences[CLAMS], params, run)
    fires = _fire_census(sequences[ROOT], params, run)
    root_lights = _root_arrival_light_census(sequences[ROOT], params, run)
    effects = _effect_census(world, params)
    return {
        "schema": "p94_s3_arrival_plan/1", "tool_version": VERSION, "run": run,
        "params": params, "dirty_before": _census(), "rise_counts": counts,
        "rise": [_public(x) for x in rise], "crowd": [_public(x) for x in crowd],
        "fires": {key: [_public(x) for x in value] for key, value in fires.items()},
        "root_arrival_lights": {key: [_public(x) for x in value] for key, value in root_lights.items()},
        "effect_census": effects,
        "timeline": {
            "crowd_copies_visible": params["crowd_visible_root_frame"],
            "total_darkness_through": params["light_rise_root_frame"] - 1,
            "light_rise": [params["light_rise_root_frame"], params["light_full_root_frame"]],
        },
        "claims": [
            {"tier": "measured", "claim": "DRY reads 49 hangar light channels, 15 crowd visibility tracks, and fire visibility/intensity keys from the loaded assets."},
            {"tier": "inferred", "claim": "Holding all enumerated sources dark until the crowd copy reveal plus the settle pad removes the visible pop; rendered acceptance remains Gary's."},
        ],
    }, rise, crowd, fires, root_lights


def _backup(run):
    target = os.path.join(_project_root(), "Backups", "PreP94S3Arrival-%s" % run)
    if os.path.exists(target):
        _stop(run, "BACKUP_EXISTS|%s" % target)
    os.makedirs(target)
    for package, source in _files().items():
        if not os.path.isfile(source):
            _stop(run, "SOURCE_FILE_MISSING|%s|%s" % (package, source))
        shutil.copy2(source, os.path.join(target, os.path.basename(source)))
    return target


def _set_times(channel, planned, run, label):
    keys = list(channel.get_keys())
    if len(planned) != len(keys):
        _stop(run, "PLANNED_KEY_COUNT|%s|got=%d|want=%d" % (label, len(planned), len(keys)))
    for key, frame in zip(keys, planned):
        key.set_time(_ue().FrameNumber(int(frame)), 0.0, _ue().MovieSceneTimeUnit.DISPLAY_RATE)


def _locate(sequence, operation, run):
    bindings = {row["guid"]: row for row in _binding_rows(sequence)}
    row = bindings.get(operation["binding_guid"])
    if row is None:
        _stop(run, "BINDING_GUID_MISSING|%s" % operation["binding_guid"])
    tracks = list(row["binding"].get_tracks())
    index = int(operation["track_index"])
    if index >= len(tracks):
        _stop(run, "TRACK_INDEX_MISSING|%s|%d" % (row["name"], index))
    track = tracks[index]
    if track.get_class().get_name() != operation["track_class"]:
        _stop(run, "TRACK_CLASS_DRIFT|%s" % row["name"])
    section, channel = _single_channel(track, row["name"], run)
    return row, track, section, channel


def _operation(package, target, planned_frames=None, bind_visibility=False):
    before = target["before"]
    return {"package": package, "binding_guid": before["binding_guid"],
            "binding": before["binding"], "track_index": before["track_index"],
            "track_class": before["track_class"], "property_before": before["property"],
            "path_before": before["path"], "keys_before": before["sections"][0]["keys"],
            "planned_frames": list(planned_frames or [x[0] for x in before["sections"][0]["keys"]]),
            "planned_values": target.get("planned_values"),
            "bind_visibility": bool(bind_visibility)}


def _save(packages, sequences, run):
    expected = {"content": sorted(packages), "maps": []}
    got = _census()
    if got != expected:
        _stop(run, "EXACT_DIRTY_CENSUS|got=%s|want=%s" %
              (json.dumps(got, sort_keys=True), json.dumps(expected, sort_keys=True)))
    for package in sorted(packages):
        if not _ue().EditorAssetLibrary.save_asset(package, only_if_is_dirty=False):
            _stop(run, "TARGETED_SAVE_FAILED|%s" % package)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census(), sort_keys=True))
    return {package: _sha(_files()[package]) for package in packages}


def _verify_operations(sequences, operations, forward, run):
    problems = []
    for operation in operations:
        _row, track, _section, channel = _locate(sequences[operation["package"]], operation, run)
        frames = [_key_frame(key) for key in channel.get_keys()]
        expected = operation["planned_frames"] if forward else [x[0] for x in operation["keys_before"]]
        if frames != expected:
            problems.append("FRAMES|%s|got=%s|want=%s" % (operation["binding"], frames, expected))
        values = [key.get_value() for key in channel.get_keys()]
        wanted_values = (operation.get("planned_values") if forward and operation.get("planned_values") is not None
                         else [row[1] for row in operation["keys_before"]])
        if len(values) != len(wanted_values) or any(
                (bool(got) != bool(want) if isinstance(want, bool)
                 else abs(float(got) - float(want)) > DEFAULTS["value_tolerance"])
                for got, want in zip(values, wanted_values)):
            problems.append("VALUES|%s|got=%s|want=%s" %
                            (operation["binding"], values[:8], wanted_values[:8]))
        prop, path = _track_property(track)
        wanted_prop = "bHidden" if forward and operation["bind_visibility"] else operation["property_before"]
        wanted_path = "bHidden" if forward and operation["bind_visibility"] else operation["path_before"]
        if (prop, path) != (wanted_prop, wanted_path):
            problems.append("PROPERTY|%s|got=%s/%s|want=%s/%s" %
                            (operation["binding"], prop, path, wanted_prop, wanted_path))
    if problems:
        _stop(run, "READBACK|%s" % problems[:8])


def _apply(sequences, plan, rise, crowd, fires, root_lights, run):
    if plan["effect_census"]["unexpected"]:
        _stop(run, "UNMANAGED_SMOKE_HAZE_FOG|populate allowed_unmanaged_effect_labels after DRY|%s" %
              plan["effect_census"]["unexpected"])
    record = {"schema": "p94_s3_arrival_record/1", "tool_version": VERSION, "run": run,
              "state": "preparing", "plan": plan, "operations": [], "dirty_before": _census()}
    # Record and backup exist before the first mutation.
    _json(_record_path(), record)
    record["backup"] = _backup(run)
    record["sha_before"] = {package: _sha(path) for package, path in _files().items()}
    _json(_record_path(), record)
    operations = []
    for target in rise:
        operations.append(_operation(RISE, target, target["planned_frames"]))
    for target in crowd:
        if target["needs_bind"]:
            operations.append(_operation(CLAMS, target, bind_visibility=True))
    for values in fires.values():
        for target in values:
            operations.append(_operation(ROOT, target, target["planned_frames"]))
    for values in root_lights.values():
        for target in values:
            operations.append(_operation(ROOT, target, target["planned_frames"]))
    record["operations"] = operations
    record["state"] = "mutating"
    _json(_record_path(), record)
    for package in sorted(set(operation["package"] for operation in operations)):
        sequences[package].modify()
    for operation in operations:
        _row, track, _section, channel = _locate(sequences[operation["package"]], operation, run)
        if operation["bind_visibility"]:
            track.set_property_name_and_path("bHidden", "bHidden")
        _set_times(channel, operation["planned_frames"], run, operation["binding"])
        if operation.get("planned_values") is not None:
            keys = list(channel.get_keys())
            if len(keys) != len(operation["planned_values"]):
                _stop(run, "PLANNED_VALUE_COUNT|%s" % operation["binding"])
            for key, value in zip(keys, operation["planned_values"]):
                key.set_value(float(value))
    changed = sorted(set(operation["package"] for operation in operations))
    hashes = _save(changed, sequences, run)
    _verify_operations(sequences, operations, True, run)
    record.update({"state": "applied", "packages_saved": changed, "sha_after": hashes,
                   "dirty_after": _census()})
    _json(_record_path(), record)
    _ue().log("P94_S3_ARRIVAL_APPLY_OK|run=%s|rise=49|crowd_vis=%d|fire_ops=%d|crowd_lights=6|wave_lights=10|packages=%s|backup=%s|dirty=0" %
              (run, sum(1 for x in crowd if x["needs_bind"]),
               len(fires["visibility"]) + len(fires["light"]), changed, record["backup"]))


def _revert(sequences, record, run):
    if record.get("state") != "applied":
        _stop(run, "RECORD_NOT_APPLIED|%s" % record.get("state"))
    operations = record["operations"]
    for package in sorted(set(operation["package"] for operation in operations)):
        sequences[package].modify()
    for operation in operations:
        _row, track, _section, channel = _locate(sequences[operation["package"]], operation, run)
        keys = list(channel.get_keys())
        before = operation["keys_before"]
        if len(keys) != len(before):
            _stop(run, "REVERT_KEY_COUNT|%s|got=%d|want=%d" %
                  (operation["binding"], len(keys), len(before)))
        for key, (frame, value) in zip(keys, before):
            key.set_time(_ue().FrameNumber(int(frame)), 0.0, _ue().MovieSceneTimeUnit.DISPLAY_RATE)
            key.set_value(value)
        if operation["bind_visibility"]:
            track.set_property_name_and_path(operation["property_before"], operation["path_before"])
    changed = sorted(set(operation["package"] for operation in operations))
    hashes = _save(changed, sequences, run)
    _verify_operations(sequences, operations, False, run)
    record.update({"state": "reverted", "revert_run": run, "sha_reverted": hashes,
                   "dirty_after_revert": _census()})
    archived = _record_path() + ".reverted-" + run
    _json(_record_path(), record)
    os.replace(_record_path(), archived)
    _ue().log("P94_S3_ARRIVAL_REVERT_OK|run=%s|operations=%d|packages=%s|record=%s|dirty=0" %
              (run, len(operations), changed, archived))


def main(injected=None):
    args_path = os.path.join(_here(), "p94_args.json")
    args = dict(injected or _json(args_path))
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run") or "P94-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    if mode not in CONFIRMS:
        _stop(run, "MODE|%s" % mode)
    world = _preflight(args, mode, run)
    sequences = _load_sequences(run)
    if mode == "REVERT":
        _revert(sequences, _json(_record_path()), run)
        return
    params = merged_params(args.get("params", {}))
    plan, rise, crowd, fires, root_lights = _build_plan(sequences, world, params, run)
    path = _plan_path(run)
    _json(path, plan)
    if mode == "DRY":
        if _census() != {"content": [], "maps": []}:
            _stop(run, "DRY_MUTATED|%s" % json.dumps(_census(), sort_keys=True))
        _ue().log("P94_S3_ARRIVAL_DRY_OK|run=%s|rise=49|crowd=15|fire_visibility=%d|fire_lights=%d|crowd_lights=6|wave_lights=10|unmanaged=%d|writes=0|dirty=0|plan=%s" %
                  (run, len(fires["visibility"]), len(fires["light"]),
                   len(plan["effect_census"]["unexpected"]), path))
        return
    _apply(sequences, plan, rise, crowd, fires, root_lights, run)


if __name__ == "__main__" or unreal is not None:
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        if unreal is not None:
            unreal.log_error("P94_S3_ARRIVAL_FAILED|%s: %s" % (type(exc).__name__, exc))
        else:
            raise
