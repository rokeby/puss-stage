"""P42: retime P06 sunset, car light, and bee glints after P33.

Offline-authored; the conductor runs this later through p06_retime_run.py.

[declaration-proven] P33 rounds the selected 110.561125 s music interval up to a
whole Show display frame (passages_to_music.py:8-12,126-131,473-476).  This tool
therefore reads the compiled P06 length live and derives k = live / 126.001125;
it never assumes that the saved length is exactly the unrounded music interval.

[declaration-proven] The sunset clock is the P06 CelestialCycle, not Sequencer
keys (p06_sunset.py:9-18,363-387).  Scaling its cycle duration by k scales fade,
horizon, dark, and black sample times while preserving phase and azimuth.

[declaration-proven] The car clock is segment-relative seconds
(place_p06_car_light.py:1-9,31-43).  Every non-zero temporal property is scaled
so its 68.55 s midpoint remains exactly proportional.

[declaration-proven] Bee glints are P06-relative spawn keys inside
LS_P06_BeeGlints, nested in LS_Choreo_Passage_6 (p06_bee_glints.py:17-21,37-48).
Only the three owned bindings, their section ranges, the owned sequence playback
end, and the one owned sub-section range are changed.

[declaration-proven] P06 FX-set fire and motes are not show-time activated.
ActiveRadiusCm is rendered-view distance and WingBurn (not these placements) is
camera-route distance (InfinityStageEffectTypes.h:87-96,139-153;
InfinityStageEffectSource.cpp:509-527,602-625,695-731).  They are snapshotted
and proven unchanged, never retimed.

DRY/APPLY/REVERT all require exact confirm strings. APPLY/REVERT require clean
world state, close Sequencer, narrow hashed backups, an exclusive pre-change
record, exact dirty-package scope, named saves, post-save read-back, and a run-id
marker. No Master or topple package is loaded for mutation or saved.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "p06_retime"
MARK = "P06_RETIME"
MODES = ("DRY", "APPLY", "REVERT")
CONFIRMS = {mode: "%s P06 RETIME" % mode for mode in MODES}

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
GLINTS = "/Game/InfinityStage/Effects/LS_P06_BeeGlints"
CHOREO = "/Game/InfinityStage/Choreo/LS_Choreo_Passage_6"
P06_LABEL = "Passage 6"
P06_GUID = "9BFC29C45D47911FF7836BB8537230D2"
CAR_LABEL = "P06 Car Light (drive-by on the 68.55 s change)"
GLINT_PREFIX = "P06 Bee Glint "
GLINT_TRACK = "P06 Bee Glints (Effects)"
FX_LABEL_PREFIX = "P06 FX 20261008 - "

ARGS_NAME = "p06_retime_args.json"
DRY_NAME = "p06_retime_dry.json"
RECORD_NAME = "p06_retime_record.json"
SUNSET_RECORD = "p06_sunset_record.json"
CAR_RECORD = "place_p06_car_light_record.json"
BEE_RECORD = os.path.join("Effects_20261007", "p06_bee_glints_record.json")
FX_RECORD = os.path.join("P06FX_20261008", "p06_fx_set_record.json")

TEMPORAL_CAR_KEYS = (
    "start_delay_seconds",
    "travel_seconds",
    "repeat_every_seconds",
    "repeat_jitter_seconds",
    "fade_in_seconds",
    "fade_out_seconds",
)
SUNSET_KEYS = (
    "animate",
    "cycle_duration_seconds",
    "cycle_rate_multiplier",
    "entry_phase_offset_cycles",
)
OLD_P06_SECONDS = 126.001125
SELECTED_MUSIC_SECONDS = 110.561125
OLD_EVENT_SECONDS = {
    "sunset_fade": 21.851227520548868,
    "sunset_horizon": 37.0,
    "sunset_dark": 52.148772479451125,
    "sunset_black_sample": 90.0,
    "car_midpoint": 68.55,
}


class ToolError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise ToolError(str(message))


def close(a, b, tol=1.0e-6):
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=float(tol))


def scale_seconds(seconds, factor):
    return float(seconds) * float(factor)


def scale_frame(frame, factor):
    """Match the existing bee tool's nearest-display-frame policy."""
    return int(round(float(frame) * float(factor)))


def validate_args(args):
    failures = []
    mode = str(args.get("mode") or "").upper()
    if mode not in MODES:
        failures.append("MODE_INVALID:%r" % args.get("mode"))
    if args.get("confirm") != CONFIRMS.get(mode):
        failures.append("CONFIRM_MISMATCH:got=%r want=%r" % (args.get("confirm"), CONFIRMS.get(mode)))
    if args.get("passage_label") != P06_LABEL or args.get("passage_guid") != P06_GUID:
        failures.append("P06_IDENTITY")
    if not close(args.get("old_length_s", -1), OLD_P06_SECONDS, 1.0e-6):
        failures.append("OLD_LENGTH")
    if not close(args.get("selected_music_s", -1), SELECTED_MUSIC_SECONDS, 1.0e-6):
        failures.append("SELECTED_MUSIC_LENGTH")
    if float(args.get("length_tolerance_s", -1)) <= 0.0:
        failures.append("LENGTH_TOLERANCE")
    if mode == "APPLY" and not str((args.get("review") or {}).get("plan_sha256") or ""):
        failures.append("APPLY_REQUIRES_DRY_PLAN_SHA256")
    if mode in ("APPLY", "REVERT") and not str(args.get("decided_by") or "").strip():
        failures.append("DECIDED_BY_REQUIRED")
    return failures


def stable_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def scaled_car(before, factor):
    out = dict(before)
    for key in TEMPORAL_CAR_KEYS:
        value = float(out[key])
        out[key] = scale_seconds(value, factor) if value > 0.0 else value
    return out


def scaled_bee(before, factor, new_span):
    rows = []
    for index, row in enumerate(before["bindings"]):
        copy = dict(row)
        keys = [[scale_frame(frame, factor), bool(value)] for frame, value in row["spawn_keys"]]
        copy["spawn_keys"] = keys
        copy["spawn_range"] = [0, int(new_span)]
        copy["transform_ranges"] = [[0, int(new_span)] for _ in row["transform_ranges"]]
        copy["name"] = "%s%d @%.1fs" % (GLINT_PREFIX, index + 1, keys[0][0] / float(before["fps"]))
        rows.append(copy)
    return {
        "bindings": rows,
        "fps": before["fps"],
        "tick": before["tick"],
        "playback": [0, int(new_span)],
        "subtrack_range": [0, int(new_span)],
        "protected_choreo": before["protected_choreo"],
    }


def fx_activation_classification(record):
    """Fail closed if a future record introduces a time/frame activation field."""
    if record is None:
        return {"record": "absent", "activation": "distance/view", "retime": False, "refusals": []}
    refusals = []
    if record.get("status") != "applied":
        refusals.append("FX_RECORD_STATUS:%r" % record.get("status"))
    rows = list((record.get("args") or {}).get("placements") or [])
    if not rows:
        refusals.append("FX_RECORD_PLACEMENTS_MISSING")
    else:
        types = sorted((str(r.get("cue_label")), str(r.get("type"))) for r in rows)
        required = {("P06 Wing 049", "Fire"), ("P06 Wing 052", "Motes")}
        allowed = required | {("P06 Wing 044", "WingBurn")}
        if not required.issubset(set(types)) or not set(types).issubset(allowed):
            refusals.append("FX_PLACEMENT_SET:%r" % types)
        for row in rows:
            for key in row:
                low = str(key).lower()
                if any(word in low for word in ("time", "second", "frame", "delay")):
                    refusals.append("FX_TIME_FIELD:%s.%s" % (row.get("cue_label"), key))
    return {"record": "present", "activation": "distance/view", "retime": False, "refusals": refusals}


def build_plan(args, live, records):
    failures = []
    old_s = float(args["old_length_s"])
    new_s = float(live["p06_length_s"])
    tol = float(args["length_tolerance_s"])
    if close(new_s, old_s, tol):
        failures.append("P33_NOT_APPLIED:live_length_s=%.6f" % new_s)
    # P33 rounds upward to one 25 fps frame: accept selected <= live <= selected + 0.04 s.
    if new_s + 1.0e-6 < float(args["selected_music_s"]) or new_s > float(args["selected_music_s"]) + tol:
        failures.append("P33_LENGTH_UNEXPECTED:live=%.6f selected=%.6f tol=%.6f" % (
            new_s, float(args["selected_music_s"]), tol))
    factor = new_s / old_s
    sunset_record = records.get("sunset")
    car_record = records.get("car")
    bee_record = records.get("bee")
    if not sunset_record or not sunset_record.get("applied"):
        failures.append("SUNSET_RECORD_NOT_APPLIED")
    if not car_record or not car_record.get("applied"):
        failures.append("CAR_RECORD_MISSING_OR_INVALID")
    if not bee_record or not bee_record.get("applied"):
        failures.append("BEE_RECORD_NOT_APPLIED")

    sunset_before = dict(live.get("sunset") or {})
    sunset_after = dict(sunset_before)
    if sunset_record:
        expected_sunset = dict((sunset_record.get("after") or {}).get("cycle") or {})
        for key in SUNSET_KEYS:
            if key not in expected_sunset or key not in sunset_before:
                failures.append("SUNSET_FIELD_MISSING:%s" % key)
            elif isinstance(expected_sunset[key], bool):
                if bool(sunset_before[key]) != bool(expected_sunset[key]):
                    failures.append("SUNSET_DRIFT:%s" % key)
            elif not close(sunset_before[key], expected_sunset[key], 1.0e-5):
                failures.append("SUNSET_DRIFT:%s" % key)
        if "cycle_duration_seconds" in sunset_after:
            sunset_after["cycle_duration_seconds"] = scale_seconds(sunset_before["cycle_duration_seconds"], factor)

    car_before = dict(live.get("car") or {})
    car_after = scaled_car(car_before, factor) if car_before else {}
    if car_record:
        expected_car = dict(car_record.get("settings") or {})
        for key in TEMPORAL_CAR_KEYS:
            if key not in expected_car or key not in car_before:
                failures.append("CAR_FIELD_MISSING:%s" % key)
            elif not close(car_before[key], expected_car[key], 1.0e-5):
                failures.append("CAR_DRIFT:%s" % key)

    bee_before = live.get("bee") or {}
    new_span = int(round(new_s * float(bee_before.get("fps", 25.0))))
    bee_after = scaled_bee(bee_before, factor, new_span) if bee_before else {}
    if bee_record:
        expected_bee = bee_record.get("after") or bee_record.get("expected_after") or {}
        expected_rows = expected_bee.get("glints") or []
        live_rows = bee_before.get("bindings") or []
        if len(live_rows) != 3 or len(expected_rows) != 3:
            failures.append("BEE_BINDING_COUNT:live=%d record=%d" % (len(live_rows), len(expected_rows)))
        else:
            for index, (got, want) in enumerate(zip(live_rows, expected_rows)):
                if got.get("name") != want.get("name"):
                    failures.append("BEE_NAME_DRIFT:%d" % index)
                if got.get("spawn_keys") != want.get("spawn_keys"):
                    failures.append("BEE_KEYS_DRIFT:%d" % index)
        expected_sub = (expected_bee.get("subtrack") or {}).get("range")
        if expected_sub and list(bee_before.get("subtrack_range") or []) != list(expected_sub):
            failures.append("BEE_SUBTRACK_RANGE_DRIFT")

    fx = fx_activation_classification(records.get("fx"))
    failures.extend(fx["refusals"])
    events = {name: scale_seconds(value, factor) for name, value in OLD_EVENT_SECONDS.items()}
    events["bee_starts"] = [row["spawn_keys"][0][0] / float(bee_before.get("fps", 25.0))
                            for row in bee_after.get("bindings", [])]
    plan = {
        "schema": 1,
        "tool": TOOL,
        "old_length_s": old_s,
        "new_length_s": new_s,
        "scale": factor,
        "events": events,
        "sunset_before": sunset_before,
        "sunset_after": sunset_after,
        "car_before": car_before,
        "car_after": car_after,
        "bee_before": bee_before,
        "bee_after": bee_after,
        "fx": fx,
        "touched_packages": [SHOW, WORLD, GLINTS, CHOREO],
        "excluded_packages": ["Master", "topple chain A", "topple chain B"],
        "refusals": failures,
    }
    plan["plan_sha256"] = stable_hash({k: v for k, v in plan.items() if k != "plan_sha256"})
    return plan


def state_matches(got, want):
    """Numeric read-back with explicit tolerances; never hashes rounded floats."""
    def deep_equal(left, right):
        if isinstance(left, bool) or isinstance(right, bool):
            return left == right
        if isinstance(left, float) or isinstance(right, float):
            return isinstance(left, (int, float)) and isinstance(right, (int, float)) and close(left, right, 0.01)
        if isinstance(left, dict) and isinstance(right, dict):
            return left.keys() == right.keys() and all(deep_equal(left[key], right[key]) for key in left)
        if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
            return len(left) == len(right) and all(deep_equal(a, b) for a, b in zip(left, right))
        return left == right

    failures = []
    for group in ("sunset", "car"):
        a, b = got.get(group) or {}, want.get(group) or {}
        if sorted(a) != sorted(b):
            failures.append("%s_FIELDS" % group.upper())
            continue
        for key in a:
            if isinstance(a[key], (int, float)) and not isinstance(a[key], bool):
                if not close(a[key], b[key], 1.0e-4):
                    failures.append("%s.%s" % (group, key))
            elif a[key] != b[key]:
                failures.append("%s.%s" % (group, key))
    if not deep_equal(got.get("bee"), want.get("bee")):
        failures.append("BEE")
    if not deep_equal(got.get("fx"), want.get("fx")):
        failures.append("FX")
    return failures


# ---------------------------------------------------------------------------------------------------------------------
# Unreal-only transport
# ---------------------------------------------------------------------------------------------------------------------


def _here():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")


def _project():
    return os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def _rate(value):
    return float(value.numerator) / float(value.denominator)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(_path(p) for p in lib.get_dirty_content_packages()),
        "maps": sorted(_path(p) for p in lib.get_dirty_map_packages()),
    }


def _package_file(package):
    require(package.startswith("/Game/"), "PACKAGE_OUTSIDE_GAME:" + package)
    base = os.path.join(_project(), "Content", *package[len("/Game/"):].split("/"))
    for ext in (".uasset", ".umap"):
        if os.path.isfile(base + ext):
            return base + ext
    raise ToolError("PACKAGE_FILE_MISSING:" + package)


def _backup(run, suffix=""):
    folder = os.path.join(_project(), "Backups", "PreP06Retime%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    rows = []
    for package in (SHOW, WORLD, GLINTS, CHOREO):
        source = _package_file(package)
        relative = os.path.relpath(source, os.path.join(_project(), "Content"))
        target = os.path.join(folder, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target)
        require(_sha256(source) == _sha256(target), "BACKUP_HASH:" + package)
        rows.append({"package": package, "source": source, "backup": target,
                     "bytes": os.path.getsize(source), "sha256": _sha256(source)})
    _write_json(os.path.join(folder, "prechange.json"), {"run": run, "packages": rows}, exclusive=True)
    return {"root": folder, "packages": rows}


def _segments(show):
    transport = unreal.new_object(unreal.InfinityStageTransportController)
    transport.build_segments(show)
    return [{"label": str(s.get_editor_property("label")),
             "start": int(s.get_editor_property("start_frame").value),
             "end": int(s.get_editor_property("end_frame").value)}
            for s in transport.get_editor_property("segments")]


def _p06_length(show):
    hits = [row for row in _segments(show) if row["label"] == P06_LABEL]
    require(len(hits) == 1, "P06_SEGMENT_COUNT:%d" % len(hits))
    tick = _rate(show.get_editor_property("tick_resolution"))
    return (hits[0]["end"] - hits[0]["start"]) / tick


def _sunset_state(show):
    hits = [p for p in show.get_editor_property("passage_settings")
            if str(p.get_editor_property("label")) == P06_LABEL
            and _guid(p.get_editor_property("passage_guid")) == P06_GUID]
    require(len(hits) == 1, "P06_SETTINGS_COUNT:%d" % len(hits))
    cycle = hits[0].get_editor_property("celestial_cycle")
    return {key: (bool(cycle.get_editor_property(key)) if key == "animate"
                  else float(cycle.get_editor_property(key))) for key in SUNSET_KEYS}


def _write_sunset(show, values):
    rows = list(show.get_editor_property("passage_settings"))
    hits = [i for i, p in enumerate(rows) if str(p.get_editor_property("label")) == P06_LABEL
            and _guid(p.get_editor_property("passage_guid")) == P06_GUID]
    require(len(hits) == 1, "P06_SETTINGS_COUNT:%d" % len(hits))
    row = rows[hits[0]]
    cycle = row.get_editor_property("celestial_cycle")
    for key in SUNSET_KEYS:
        cycle.set_editor_property(key, bool(values[key]) if key == "animate" else float(values[key]))
    row.set_editor_property("celestial_cycle", cycle)
    rows[hits[0]] = row
    show.modify()
    show.set_editor_property("passage_settings", rows)


def _car_actor():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    hits = [actor for actor in actors if str(actor.get_actor_label()) == CAR_LABEL]
    require(len(hits) == 1, "CAR_ACTOR_COUNT:%d" % len(hits))
    return hits[0]


def _car_state(actor):
    return {key: float(actor.get_editor_property(key)) for key in TEMPORAL_CAR_KEYS}


def _write_car(actor, values):
    actor.modify()
    for key in TEMPORAL_CAR_KEYS:
        actor.set_editor_property(key, float(values[key]))


def _channel_name(channel):
    if hasattr(channel, "channel_name"):
        return str(channel.channel_name)
    try:
        return str(channel.get_editor_property("channel_name"))
    except Exception:  # noqa: BLE001 - UE wrapper variations.
        return str(channel.get_name())


def _protected_choreo(choreo):
    rows = []
    for track in choreo.get_tracks():
        name = str(track.get_display_name())
        sequences = [_path(section.get_sequence()) for section in track.get_sections()
                     if track.get_class().get_name() == "MovieSceneSubTrack"]
        if track.get_class().get_name() == "MovieSceneSubTrack" and name == GLINT_TRACK and sequences == [GLINTS]:
            continue
        sections = []
        for section in track.get_sections():
            item = {"start": int(section.get_start_frame()) if section.has_start_frame() else None,
                    "end": int(section.get_end_frame()) if section.has_end_frame() else None,
                    "channels": []}
            for channel in section.get_all_channels():
                keys = []
                try:
                    for key in channel.get_keys():
                        keys.append([int(key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                                         .frame_number.value), str(key.get_value())])
                except Exception:  # noqa: BLE001 - census unknown channels without guessing.
                    keys = ["UNREADABLE"]
                item["channels"].append([_channel_name(channel), keys])
            sections.append(item)
        rows.append({"class": track.get_class().get_name(), "name": name, "sections": sections})
    return rows


def _bee_objects():
    glints = unreal.load_asset(GLINTS)
    choreo = unreal.load_asset(CHOREO)
    require(glints is not None and choreo is not None, "BEE_ASSET_LOAD")
    bindings = sorted([b for b in glints.get_bindings() if str(b.get_display_name()).startswith(GLINT_PREFIX)],
                      key=lambda b: str(b.get_display_name()))
    require(len(bindings) == 3, "BEE_BINDING_COUNT:%d" % len(bindings))
    subtracks = []
    for track in choreo.get_tracks():
        if track.get_class().get_name() != "MovieSceneSubTrack":
            continue
        sections = list(track.get_sections())
        if (str(track.get_display_name()) == GLINT_TRACK and len(sections) == 1
                and _path(sections[0].get_sequence()) == GLINTS):
            subtracks.append((track, sections[0]))
    require(len(subtracks) == 1, "BEE_SUBTRACK_COUNT:%d" % len(subtracks))
    return glints, choreo, bindings, subtracks[0][1]


def _bee_state(glints, choreo, bindings, subsection):
    rows = []
    for binding in bindings:
        spawn_tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"]
        transform_tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
        require(len(spawn_tracks) == 1 and len(spawn_tracks[0].get_sections()) == 1,
                "BEE_SPAWN_STRUCTURE:" + str(binding.get_display_name()))
        spawn_section = spawn_tracks[0].get_sections()[0]
        channels = list(spawn_section.get_all_channels())
        require(len(channels) == 1, "BEE_SPAWN_CHANNEL_COUNT")
        keys = [[int(key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE).frame_number.value),
                 bool(key.get_value())] for key in channels[0].get_keys()]
        defaults = []
        ranges = []
        for track in transform_tracks:
            for section in track.get_sections():
                ranges.append([int(section.get_start_frame()), int(section.get_end_frame())])
                defaults.append([[_channel_name(channel), float(channel.get_default())]
                                 for channel in section.get_all_channels()])
        rows.append({"name": str(binding.get_display_name()), "spawn_keys": keys,
                     "spawn_range": [int(spawn_section.get_start_frame()), int(spawn_section.get_end_frame())],
                     "transform_ranges": ranges, "transform_defaults": defaults})
    return {"bindings": rows, "fps": _rate(glints.get_display_rate()), "tick": _rate(glints.get_tick_resolution()),
            "playback": [int(glints.get_playback_start()), int(glints.get_playback_end())],
            "subtrack_range": [int(subsection.get_start_frame()), int(subsection.get_end_frame())],
            "protected_choreo": _protected_choreo(choreo)}


def _write_bee(glints, bindings, subsection, values):
    glints.modify()
    for binding, wanted in zip(bindings, values["bindings"]):
        binding.set_display_name(wanted["name"])
        spawn = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieSceneSpawnTrack"][0]
        section = spawn.get_sections()[0]
        section.set_range(*wanted["spawn_range"])
        keys = list(section.get_all_channels()[0].get_keys())
        require(len(keys) == len(wanted["spawn_keys"]), "BEE_KEY_COUNT_DURING_WRITE")
        for key, pair in zip(keys, wanted["spawn_keys"]):
            require(bool(key.get_value()) == bool(pair[1]), "BEE_KEY_VALUE_DRIFT_DURING_WRITE")
            key.set_time(unreal.FrameNumber(value=int(pair[0])), 0.0,
                         unreal.MovieSceneTimeUnit.DISPLAY_RATE)
        transform_sections = [s for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"
                              for s in t.get_sections()]
        require(len(transform_sections) == len(wanted["transform_ranges"]), "BEE_TRANSFORM_SECTION_COUNT")
        for section, rng in zip(transform_sections, wanted["transform_ranges"]):
            section.set_range(*rng)
    glints.set_playback_start(int(values["playback"][0]))
    glints.set_playback_end(int(values["playback"][1]))
    subsection.set_range(*values["subtrack_range"])


def _fx_snapshot(show):
    rows = []
    for cue in show.get_editor_property("cues"):
        pair = cue.get_editor_property("wing_pair")
        for item in pair.get_editor_property("attachments"):
            label = str(item.get_editor_property("label"))
            if not label.startswith(FX_LABEL_PREFIX):
                continue
            settings = item.get_editor_property("effect")
            rows.append({"cue": str(cue.get_editor_property("label")), "label": label,
                         "guid": _guid(item.get_editor_property("attachment_guid")),
                         "enabled": bool(item.get_editor_property("enabled")),
                         "type": str(settings.get_editor_property("type")),
                         "active_radius_cm": float(settings.get_editor_property("active_radius_cm")),
                         "burn_start_ahead_cm": float(settings.get_editor_property("burn_start_ahead_cm")),
                         "burn_span_cm": float(settings.get_editor_property("burn_span_cm"))})
    return sorted(rows, key=lambda row: (row["cue"], row["label"], row["guid"]))


def _records():
    root = _here()
    paths = {"sunset": SUNSET_RECORD, "car": CAR_RECORD, "bee": BEE_RECORD, "fx": FX_RECORD}
    return {name: (_read_json(os.path.join(root, relative)) if os.path.isfile(os.path.join(root, relative)) else None)
            for name, relative in paths.items()}


def _live():
    show = unreal.load_asset(SHOW)
    require(show is not None, "SHOW_LOAD")
    car = _car_actor()
    glints, choreo, bindings, subsection = _bee_objects()
    return {"show": show, "car_actor": car, "glints": glints, "choreo": choreo,
            "bindings": bindings, "subsection": subsection,
            "plain": {"p06_length_s": _p06_length(show), "sunset": _sunset_state(show),
                      "car": _car_state(car), "bee": _bee_state(glints, choreo, bindings, subsection),
                      "fx": _fx_snapshot(show)}}


def _guards(mode, record_path):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    failures = []
    if editor.get_game_world() is not None:
        failures.append("PIE_OR_SIE_ACTIVE")
    if world is None or _path(world) != WORLD:
        failures.append("WRONG_WORLD:%r" % _path(world))
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        failures.append("SEQUENCER_OPEN")
    if _census() != {"content": [], "maps": []}:
        failures.append("DIRTY_BEFORE:" + json.dumps(_census(), sort_keys=True))
    if mode == "APPLY" and os.path.exists(record_path):
        failures.append("RECORD_EXISTS")
    if mode == "REVERT" and not os.path.exists(record_path):
        failures.append("RECORD_MISSING")
    return failures


def _expected_plain(plan, which):
    return {"sunset": plan["sunset_" + which], "car": plan["car_" + which],
            "bee": plan["bee_" + which]}


def _apply_values(live, values):
    _write_sunset(live["show"], values["sunset"])
    _write_car(live["car_actor"], values["car"])
    _write_bee(live["glints"], live["bindings"], live["subsection"], values["bee"])


def _read_semantic():
    live = _live()
    return {"sunset": live["plain"]["sunset"], "car": live["plain"]["car"],
            "bee": live["plain"]["bee"], "fx": live["plain"]["fx"]}


def _dirty_gate():
    want = {"content": sorted([SHOW, GLINTS, CHOREO]), "maps": [WORLD]}
    got = _census()
    require(got == want, "DIRTY_SCOPE:got=%s want=%s" % (json.dumps(got), json.dumps(want)))


def _save_named(live):
    for package, asset in ((SHOW, live["show"]), (GLINTS, live["glints"]), (CHOREO, live["choreo"])):
        require(unreal.EditorAssetLibrary.save_loaded_asset(asset, False), "SAVE_FAILED:" + package)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    require(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD), "SAVE_FAILED:" + WORLD)
    require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY:" + json.dumps(_census()))


def run_dry(args, run):
    before_census = _census()
    live = _live()
    records = _records()
    plan = build_plan(args, live["plain"], records)
    report = {"run": run, "mode": "DRY", "args": args, "plan": plan,
              "live_fx_unchanged": live["plain"]["fx"],
              "records_present": {key: value is not None for key, value in records.items()},
              "census_before": before_census, "census_after": _census()}
    require(before_census == _census(), "DRY_DIRTIED_PACKAGES")
    _write_json(os.path.join(_here(), DRY_NAME), report)
    unreal.log("%s_DRY_OK|run=%s|apply_ready=%d|refusals=%d|old_s=%.6f|new_s=%.6f|k=%.9f|dusk_s=%.6f|wt_slam_s=%.6f|fx=distance_view|mutated=0|plan_sha256=%s" % (
        MARK, run, int(not plan["refusals"]), len(plan["refusals"]), plan["old_length_s"],
        plan["new_length_s"], plan["scale"], plan["events"]["sunset_horizon"],
        plan["events"]["sunset_horizon"], plan["plan_sha256"]))
    for refusal in plan["refusals"]:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, refusal))


def run_apply(args, run, record_path):
    live = _live()
    records = _records()
    plan = build_plan(args, live["plain"], records)
    require(not plan["refusals"], "PLAN_REFUSED:" + " || ".join(plan["refusals"]))
    require((args.get("review") or {}).get("plan_sha256") == plan["plan_sha256"], "PLAN_SHA256_CHANGED")
    backup = _backup(run)
    record = {"schema": 1, "tool": TOOL, "run": run, "mode": "APPLY", "applied": False,
              "decided_by": args["decided_by"], "backup": backup, "plan": plan,
              "before": _expected_plain(plan, "before"), "after": _expected_plain(plan, "after"),
              "fx_before": live["plain"]["fx"]}
    _write_json(record_path, record, exclusive=True)
    _apply_values(live, record["after"])
    got = _read_semantic()
    want = dict(record["after"], fx=record["fx_before"])
    require(not state_matches(got, want), "PRE_SAVE_READBACK:" + repr(state_matches(got, want)))
    _dirty_gate()
    _save_named(live)
    got = _read_semantic()
    require(not state_matches(got, want), "POST_SAVE_READBACK:" + repr(state_matches(got, want)))
    record["applied"] = True
    record["post_save"] = got
    record["dirty_after"] = _census()
    _write_json(record_path, record)
    unreal.log("%s_APPLY_OK|run=%s|old_s=%.6f|new_s=%.6f|k=%.9f|dusk_s=%.6f|wt_slam_s=%.6f|car_s=%.6f|bee_s=%s|fx=distance_view_unchanged|saved=%s|backup=%s|dirty_after=0+0" % (
        MARK, run, plan["old_length_s"], plan["new_length_s"], plan["scale"],
        plan["events"]["sunset_horizon"], plan["events"]["sunset_horizon"], plan["events"]["car_midpoint"],
        ",".join("%.3f" % x for x in plan["events"]["bee_starts"]),
        ",".join(plan["touched_packages"]), backup["root"]))


def run_revert(args, run, record_path):
    record = _read_json(record_path)
    require(record.get("tool") == TOOL and record.get("applied"), "REVERT_RECORD_CONTEXT")
    live = _live()
    current = {"sunset": live["plain"]["sunset"], "car": live["plain"]["car"],
               "bee": live["plain"]["bee"], "fx": live["plain"]["fx"]}
    want_current = dict(record["after"], fx=record["fx_before"])
    require(not state_matches(current, want_current), "STATE_DRIFTED:" + repr(state_matches(current, want_current)))
    backup = _backup(run, "Revert")
    attempt_path = os.path.join(_here(), "p06_retime_revert_record_%s.json" % run)
    attempt = {"schema": 1, "tool": TOOL, "run": run, "mode": "REVERT", "complete": False,
               "source_record": record_path, "backup": backup, "before_revert": current}
    _write_json(attempt_path, attempt, exclusive=True)
    _apply_values(live, record["before"])
    got = _read_semantic()
    want = dict(record["before"], fx=record["fx_before"])
    require(not state_matches(got, want), "REVERT_PRE_SAVE_READBACK:" + repr(state_matches(got, want)))
    _dirty_gate()
    _save_named(live)
    got = _read_semantic()
    require(not state_matches(got, want), "REVERT_POST_SAVE_READBACK:" + repr(state_matches(got, want)))
    attempt.update({"complete": True, "after_revert": got, "dirty_after": _census()})
    _write_json(attempt_path, attempt)
    archived = record_path + ".reverted-" + run
    os.replace(record_path, archived)
    unreal.log("%s_REVERT_OK|run=%s|restored_old_s=%.6f|saved=%s|backup=%s|record=%s|dirty_after=0+0" % (
        MARK, run, record["plan"]["old_length_s"], ",".join(record["plan"]["touched_packages"]),
        backup["root"], archived))


def main():
    args = globals().get("P06_RETIME_ARGS")
    if args is None:
        args = _read_json(os.path.join(_here(), ARGS_NAME))
    run = str(args.get("run_id") or datetime.datetime.now().strftime("P42-%Y%m%d-%H%M%S"))
    failures = validate_args(args)
    if failures:
        raise ToolError("ARGS:" + " || ".join(failures))
    mode = str(args["mode"]).upper()
    record_path = os.path.join(_here(), RECORD_NAME)
    failures = _guards(mode, record_path)
    if failures:
        raise ToolError("REFUSED:" + " || ".join(failures))
    unreal.log("%s_START|run=%s|mode=%s" % (MARK, run, mode))
    {"DRY": lambda: run_dry(args, run),
     "APPLY": lambda: run_apply(args, run, record_path),
     "REVERT": lambda: run_revert(args, run, record_path)}[mode]()


if unreal is not None and not globals().get("P06_RETIME_IMPORT_ONLY"):
    try:
        main()
    except Exception as error:  # noqa: BLE001 - Unreal log must preserve exact refusal.
        run = str((globals().get("P06_RETIME_ARGS") or {}).get("run_id") or "unknown")
        unreal.log_error("%s_STOPPED|run=%s|%s|do not Save All; inspect exact census" % (MARK, run, error))
        raise
