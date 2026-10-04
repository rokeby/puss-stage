# RETIRED 4 Oct (Gary): superseded by lighting_scores P01 strike-on-approach ping-on. Do not run.
"""Draft P01 office-hallway ping-on authoring tool (DRY/APPLY/REVERT).

DO NOT treat this file's presence as approval to apply it.  Default mode is DRY.
Select a mode with the global ``P01_HALLWAY_MODE`` when ExecuteProjectPythonFile
runs this file.  The only accepted values are DRY, APPLY and REVERT.

Authority and mechanism (source citations are for the reviewed 3 Oct checkout):

* The Show owns cue attachments and the Master owns time/camera
  (Docs/InfinityStageSessionHandover.md:777-780).
* P01 lamps are Show-owned per-wing-pair attachments; the warmer tool writes
  them back through cue -> wing_pair -> attachments
  (Saved/CodexStructure/p01_warmer_apply.py:82-101, 176-218).
* Existing light animation binds a LightComponent into a Level Sequence and
  keys a MovieSceneFloatTrack named/path ``Intensity``
  (Saved/CodexStructure/s3_strike_apply.py:780-804 and
  Saved/CodexStructure/scene4_fold_apply.py:254-266).  This tool uses that same
  property-track mechanism on the Master because P01 has no child sequence.
* Rebuilding the managed Master updates only the managed Passage/Scene/Music
  tracks and preserves unrelated possessable tracks
  (InfinityStageSequenceBuilderLibrary.cpp:195-228, 230-364).

The timing plan uses the compiler's declared piecewise route law: each Wing
station is at its cue's PassFrame/Distance and the camera interpolates between
successive stations (InfinityStageCompiler.cpp:254-288, 380-410).  A default
600 cm look-ahead therefore means "the camera is 6 m before this bay", even
when cue intervals are not uniform.  Bay one may trigger during the Opening
walk-in by extrapolating the P01 entry slope before P01's section start.

Important limitation (inferred, not live-tested by this draft): P01 attachment
actors are materialization-owned and are destroyed/recreated by a later P01
materialize (InfinityStagePassageActor.cpp:866-892).  The Master possessables
therefore bind the CURRENT saved attachment actors.  Apply only after the last
P01 materialize; after any later P01 materialize, REVERT this record if the old
bindings still resolve, then re-APPLY.  The tool refuses missing/duplicate
identity tags and records every binding GUID for exact read-back/revert.

APPLY/REVERT:
  * require the correct project/world, PIE/SIE off and a clean package census;
  * back up Show + Master under Backups/PreP01HallwayPingOn*;
  * write/read/fsync a revert record before mutation;
  * save only Show + Master (never the level, never Save All);
  * read back every Intensity channel and changed Light Drama flag;
  * require a clean final census; and
  * queue ONLY InfinityStage.Editor.SavedMasterMatchesShow.  "Queued" is not a
    pass: the caller must read the automation result from the Unreal log.

Pure planning functions stay importable without Unreal.  The companion
``test_p01_hallway_pingon.py`` is the offline positive/negative harness.
"""

import datetime
import hashlib
import json
import math
import os
import random
import re
import shutil


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
PASSAGE_LABEL = "Passage 1"
P01_LABEL = re.compile(r"^P01 Wing \d{3}$")
TRACK_NAME = "P01 Hallway Ping-On (Codex)"
AUTOMATION_TEST = "InfinityStage.Editor.SavedMasterMatchesShow"
DEFAULT_TRIGGER_DISTANCE_M = 6.0
DEFAULT_FLICKER_MIN_S = 0.10
DEFAULT_FLICKER_MAX_S = 0.30
VALUE_TOLERANCE = 1.0e-4

DRAMA_FIELDS = (
    "strike_on_approach",
    "strike_distance_cm",
    "strike_ramp_cm",
    "ignition_stutter",
    "unstruck_intensity_scale",
    "after_pass",
    "after_pass_distance_cm",
    "decay_distance_cm",
    "slow_move",
    "pan_amplitude_degrees",
    "tilt_amplitude_degrees",
    "period_seconds",
    "phase_from_identity",
    "phase_cycles",
)


class HallwayPingError(RuntimeError):
    pass


def _finite(value, label):
    number = float(value)
    if not math.isfinite(number):
        raise HallwayPingError("%s is not finite: %r" % (label, value))
    return number


def _stable_int(text):
    return int(hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:16], 16)


def _frame(seconds, fps):
    return int(round(_finite(seconds, "seconds") * _finite(fps, "fps")))


def _invert_route_distance(target_cm, anchors, entry_speed_cm_s):
    """Invert the compiler's piecewise-linear route law.

    ``anchors`` are ``(time_seconds, distance_cm)`` rows from segment start,
    Wing PassFrames and segment end.  Negative distance belongs to the Opening
    walk-in and is extrapolated from the declared P01 entry slope.
    """
    target = _finite(target_cm, "target_cm")
    speed = _finite(entry_speed_cm_s, "entry_speed_cm_s")
    if speed <= 0.0:
        raise HallwayPingError("entry_speed_cm_s must be positive")
    rows = [(float(t), float(d)) for t, d in anchors]
    if len(rows) < 2:
        raise HallwayPingError("at least two route anchors are required")
    if any(rows[index + 1][0] <= rows[index][0] for index in range(len(rows) - 1)):
        raise HallwayPingError("route anchor times are not strictly increasing")
    if any(rows[index + 1][1] < rows[index][1] for index in range(len(rows) - 1)):
        raise HallwayPingError("route anchor distances are not monotonic")
    if target < rows[0][1]:
        return rows[0][0] + (target - rows[0][1]) / speed
    for (time_a, distance_a), (time_b, distance_b) in zip(rows, rows[1:]):
        if target <= distance_b + 1.0e-9:
            if distance_b <= distance_a + 1.0e-9:
                return time_b
            alpha = (target - distance_a) / (distance_b - distance_a)
            return time_a + (time_b - time_a) * alpha
    raise HallwayPingError(
        "trigger distance %.3f cm exceeds route end %.3f cm" % (target, rows[-1][1])
    )


def _flicker_keys(trigger_frame, duration_frames, intensity, identity, master_start_frame):
    """Deterministic, hard-edged fluorescent catch followed by steady full."""
    trigger = int(trigger_frame)
    duration = int(duration_frames)
    full = _finite(intensity, "intensity")
    start = int(master_start_frame)
    if duration < 3:
        raise HallwayPingError("flicker duration must be at least three display frames")
    if full < 0.0:
        raise HallwayPingError("light intensity cannot be negative")
    if trigger <= start:
        raise HallwayPingError("trigger frame must follow the Master start frame")

    # A dict deliberately coalesces the start and pre-trigger zero when adjacent.
    keyed = {start: 0.0, max(start, trigger - 1): 0.0, trigger: full}
    rng = random.Random(_stable_int(identity))
    for offset in range(1, duration):
        if offset % 2:
            scale = rng.uniform(0.03, 0.24)  # failed tube catch
        else:
            scale = rng.uniform(0.58, 0.94)  # brief restrike
        keyed[trigger + offset] = full * scale
    keyed[trigger + duration] = full
    return [
        {"frame": frame_number, "value": keyed[frame_number]}
        for frame_number in sorted(keyed)
    ]


def value_at_frame(keys, frame, default=0.0):
    """Evaluate the constant-interpolation plan at one display frame."""
    value = float(default)
    for row in sorted(keys, key=lambda item: int(item["frame"])):
        if int(row["frame"]) > int(frame):
            break
        value = float(row["value"])
    return value


def plan_hallway_pingon(
    bays,
    anchors,
    entry_speed_cm_s,
    passage_end_s,
    master_start_frame,
    master_end_frame,
    fps,
    trigger_distance_cm=DEFAULT_TRIGGER_DISTANCE_M * 100.0,
    flicker_min_s=DEFAULT_FLICKER_MIN_S,
    flicker_max_s=DEFAULT_FLICKER_MAX_S,
):
    """Create a plain-JSON plan; no Unreal import or state is required."""
    rate = _finite(fps, "fps")
    before = _finite(trigger_distance_cm, "trigger_distance_cm")
    minimum = _finite(flicker_min_s, "flicker_min_s")
    maximum = _finite(flicker_max_s, "flicker_max_s")
    if rate <= 0.0 or before < 0.0:
        raise HallwayPingError("fps must be positive and trigger distance non-negative")
    if not 0.10 - 1.0e-9 <= minimum <= maximum <= 0.30 + 1.0e-9:
        raise HallwayPingError("flicker range must stay within 0.10-0.30 seconds")
    duration_min = max(3, int(math.ceil(minimum * rate - 1.0e-9)))
    duration_max = max(duration_min, int(math.floor(maximum * rate + 1.0e-9)))
    passage_end_frame = _frame(passage_end_s, rate)

    planned_bays = []
    for ordinal, bay in enumerate(bays):
        station = _finite(bay["station_cm"], "bay station")
        trigger_route_cm = station - before
        trigger_s = _invert_route_distance(trigger_route_cm, anchors, entry_speed_cm_s)
        trigger_frame = _frame(trigger_s, rate)
        duration_rng = random.Random(_stable_int("bay-duration|" + str(bay["cue_guid"])))
        duration_frames = duration_rng.randint(duration_min, duration_max)
        settle_frame = trigger_frame + duration_frames
        lights = []
        for source in bay.get("lights", []):
            intensity = _finite(source["intensity"], "light intensity")
            identity = str(source["attachment_guid"])
            lights.append(
                {
                    "attachment_guid": identity,
                    "label": str(source["label"]),
                    "intensity": intensity,
                    "keys": _flicker_keys(
                        trigger_frame, duration_frames, intensity, identity, master_start_frame
                    ),
                }
            )
        planned_bays.append(
            {
                "ordinal": ordinal,
                "cue_guid": str(bay["cue_guid"]),
                "cue_label": str(bay["cue_label"]),
                "station_cm": station,
                "pass_s": _finite(bay["pass_s"], "bay pass_s"),
                "trigger_route_cm": trigger_route_cm,
                "trigger_s": trigger_s,
                "trigger_frame": trigger_frame,
                "duration_frames": duration_frames,
                "duration_s": duration_frames / rate,
                "settle_frame": settle_frame,
                "lights": lights,
            }
        )
    plan = {
        "fps": rate,
        "trigger_distance_cm": before,
        "flicker_range_s": [minimum, maximum],
        "master_start_frame": int(master_start_frame),
        "master_end_frame": int(master_end_frame),
        "passage_end_frame": passage_end_frame,
        "anchors": [[float(t), float(d)] for t, d in anchors],
        "bays": planned_bays,
    }
    failures = validate_plan(plan)
    if failures:
        raise HallwayPingError("planned hallway failed validation: %r" % failures)
    return plan


def validate_plan(plan):
    """Falsifiable plan controls used by both DRY and the offline harness."""
    failures = []
    bays = list(plan.get("bays", []))
    route_order = [float(bay["station_cm"]) for bay in bays]
    trigger_order = [int(bay["trigger_frame"]) for bay in bays]
    if route_order != sorted(route_order) or any(
        trigger_order[index + 1] <= trigger_order[index]
        for index in range(len(trigger_order) - 1)
    ):
        failures.append("route-order")
    end_frame = int(plan["passage_end_frame"])
    for bay in bays:
        trigger = int(bay["trigger_frame"])
        if not 0.10 - 1.0e-9 <= float(bay["duration_s"]) <= 0.30 + 1.0e-9:
            failures.append("flicker-range:%s" % bay["cue_label"])
        if int(bay["settle_frame"]) > end_frame:
            failures.append("settles-after-end:%s" % bay["cue_label"])
        for light in bay.get("lights", []):
            keys = list(light["keys"])
            early = [
                row for row in keys
                if int(row["frame"]) < trigger and abs(float(row["value"])) > VALUE_TOLERANCE
            ]
            if early or abs(value_at_frame(keys, trigger - 1)) > VALUE_TOLERANCE:
                failures.append("pretrigger:%s" % light["attachment_guid"])
            full = float(light["intensity"])
            if abs(value_at_frame(keys, end_frame) - full) > VALUE_TOLERANCE:
                failures.append("not-on-by-end:%s" % light["attachment_guid"])
    return sorted(set(failures))


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def main(mode=None):
    import unreal

    selected_mode = str(mode or globals().get("P01_HALLWAY_MODE", "DRY")).strip().upper()
    if selected_mode not in ("DRY", "APPLY", "REVERT"):
        raise HallwayPingError("mode must be DRY, APPLY or REVERT")
    trigger_distance_m = _finite(
        globals().get("P01_HALLWAY_TRIGGER_DISTANCE_M", DEFAULT_TRIGGER_DISTANCE_M),
        "P01_HALLWAY_TRIGGER_DISTANCE_M",
    )
    flicker_min_s = _finite(
        globals().get("P01_HALLWAY_FLICKER_MIN_S", DEFAULT_FLICKER_MIN_S),
        "P01_HALLWAY_FLICKER_MIN_S",
    )
    flicker_max_s = _finite(
        globals().get("P01_HALLWAY_FLICKER_MAX_S", DEFAULT_FLICKER_MAX_S),
        "P01_HALLWAY_FLICKER_MAX_S",
    )
    queue_test = bool(globals().get("P01_HALLWAY_QUEUE_SAVED_MASTER_TEST", True))
    run = str(globals().get(
        "P01_HALLWAY_RUN_ID", datetime.datetime.now().strftime("P01PING-%Y%m%d-%H%M%S")
    ))

    saved_root = os.path.normpath(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    )
    here = os.path.join(saved_root, "CodexConductor")
    report_path = os.path.join(here, "p01_hallway_pingon_report.json")
    record_path = os.path.join(here, "p01_hallway_pingon_record.json")
    report = {"ok": False, "run": run, "mode": selected_mode}

    def fail(message):
        report["error"] = str(message)
        _write_json(report_path, report)
        marker = "P01_HALLWAY_PINGON_STOPPED|run=%s|mode=%s|%s" % (
            run, selected_mode, message
        )
        unreal.log_error(marker)
        raise HallwayPingError(marker)

    def guid_text(value):
        return unreal.GuidLibrary.conv_guid_to_string(value)

    def guid_digits(value):
        return guid_text(value).replace("-", "").lower()

    def asset_id(value):
        return value.get_path_name().split(".", 1)[0] if value is not None else None

    def package_id(package):
        getter = getattr(package, "get_name", None) or getattr(package, "get_path_name")
        return str(getter()).split(".", 1)[0]

    def census():
        return {
            "content": sorted(package_id(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(package_id(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        }

    def enum_or_scalar(value):
        if hasattr(value, "name"):
            return str(value.name)
        if isinstance(value, (bool, int, str)) or value is None:
            return value
        if isinstance(value, float):
            return round(value, 9)
        return str(value)

    def drama_snapshot(drama):
        return {name: enum_or_scalar(drama.get_editor_property(name)) for name in DRAMA_FIELDS}

    def content_file(asset_path):
        if not asset_path.startswith("/Game/"):
            fail("non-/Game asset path cannot be backed up: %s" % asset_path)
        return os.path.normpath(os.path.join(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
            asset_path[len("/Game/"):] + ".uasset",
        ))

    def make_backup(prefix):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        root = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
        backup = os.path.join(root, "Backups", prefix + stamp)
        if os.path.exists(backup):
            fail("backup already exists: %s" % backup)
        os.makedirs(backup)
        files = []
        for asset_path in (SHOW_PATH, MASTER_PATH):
            source = content_file(asset_path)
            if not os.path.isfile(source):
                fail("package file missing: %s" % source)
            destination = os.path.join(backup, os.path.basename(source))
            shutil.copy2(source, destination)
            if os.path.getsize(destination) != os.path.getsize(source) or _sha256(destination) != _sha256(source):
                fail("backup verification failed: %s" % source)
            files.append({
                "asset": asset_path,
                "source": source,
                "backup": destination,
                "bytes": os.path.getsize(source),
                "sha256": _sha256(source),
            })
        return {"directory": backup, "files": files}

    def key_rows(channel):
        rows = []
        for key in channel.get_keys():
            when = key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
            rows.append({
                "frame": int(when.frame_number.value),
                "value": round(float(key.get_value()), 6),
            })
        return sorted(rows, key=lambda row: row["frame"])

    def named_tracks(master):
        found = []
        for binding in master.get_bindings():
            for track in binding.get_tracks():
                if str(track.get_display_name()) == TRACK_NAME:
                    found.append((binding, track))
        return found

    def binding_guid_map(master):
        return {guid_text(binding.get_id()): binding for binding in master.get_bindings()}

    def intensity_track_snapshot(binding):
        tracks = [
            track for track in binding.get_tracks()
            if str(track.get_display_name()) == TRACK_NAME
            and isinstance(track, unreal.MovieSceneFloatTrack)
            and str(track.get_property_name()) == "Intensity"
        ]
        if len(tracks) != 1:
            fail("binding %s has %d owned Intensity tracks" % (binding.get_display_name(), len(tracks)))
        sections = list(tracks[0].get_sections())
        if len(sections) != 1:
            fail("owned Intensity track has %d sections" % len(sections))
        channels = list(sections[0].get_all_channels())
        if len(channels) != 1:
            fail("owned Intensity section has %d channels" % len(channels))
        channel = channels[0]
        return tracks[0], {
            "default": float(channel.get_default()) if channel.has_default() else None,
            "keys": key_rows(channel),
        }

    try:
        project = os.path.normcase(os.path.normpath(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        )).rstrip("\\/")
        if project != EXPECTED_PROJECT.rstrip("\\/"):
            fail("wrong project directory %s" % project)
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world is None or asset_id(world) != EXPECTED_WORLD:
            fail("wrong editor world %s" % asset_id(world))
        if editor.get_game_world() is not None:
            fail("PIE/SIE is active")
        before_census = census()
        report["census_before"] = before_census
        if selected_mode != "DRY" and (before_census["content"] or before_census["maps"]):
            fail("mutation requires zero dirty packages: %s" % json.dumps(before_census, sort_keys=True))

        show = unreal.load_asset(SHOW_PATH)
        master = unreal.load_asset(MASTER_PATH)
        if show is None or master is None:
            fail("Show or Master failed to load")
        show_tick = show.get_editor_property("tick_resolution")
        tick_rate = float(show_tick.numerator) / float(show_tick.denominator)
        master_tick = master.get_tick_resolution()
        master_tick_rate = float(master_tick.numerator) / float(master_tick.denominator)
        display = master.get_display_rate()
        fps = float(display.numerator) / float(display.denominator)
        if abs(tick_rate - master_tick_rate) > 1.0e-6:
            fail("Show/Master tick rates differ: %.6f vs %.6f" % (tick_rate, master_tick_rate))
        if fps < 29.9:
            fail("Master display rate %.6f cannot represent a 0.10 s flicker with three frames" % fps)

        passage_rows = [
            row for row in show.get_editor_property("passage_settings")
            if str(row.get_editor_property("label")) == PASSAGE_LABEL
        ]
        if len(passage_rows) != 1:
            fail("expected one %s passage row, found %d" % (PASSAGE_LABEL, len(passage_rows)))
        settings = passage_rows[0]
        passage_guid = settings.get_editor_property("passage_guid")
        passage_guid_text = guid_text(passage_guid)

        section_matches = []
        for track in master.get_tracks():
            if "InfinityPassage" not in track.get_class().get_name():
                continue
            for section in track.get_sections():
                if guid_text(section.get_editor_property("passage_guid")) == passage_guid_text:
                    section_matches.append(section)
        if len(section_matches) != 1:
            fail("expected one P01 managed Master section, found %d" % len(section_matches))
        passage_section = section_matches[0]
        section_start_s = float(passage_section.get_start_frame_seconds())
        section_end_s = float(passage_section.get_end_frame_seconds())
        passage_channels = {
            str(channel.get_editor_property("channel_name")): channel
            for channel in passage_section.get_all_channels()
        }
        for name, wanted in (("Camera.SpeedMultiplier", 1.0), ("Camera.LongitudinalOffsetCm", 0.0)):
            channel = passage_channels.get(name)
            if channel is None:
                fail("P01 section is missing %s" % name)
            keys = list(channel.get_keys())
            default = float(channel.get_default()) if channel.has_default() else wanted
            if keys or abs(default - wanted) > 1.0e-6:
                fail("%s is authored (keys=%d default=%.6f); route inversion needs extension" % (name, len(keys), default))

        cues = list(show.get_editor_property("cues"))
        first_guid = guid_text(settings.get_editor_property("first_cue_guid"))
        last_guid = guid_text(settings.get_editor_property("last_cue_guid"))
        first_indexes = [i for i, cue in enumerate(cues) if guid_text(cue.get_editor_property("cue_guid")) == first_guid]
        last_indexes = [i for i, cue in enumerate(cues) if guid_text(cue.get_editor_property("cue_guid")) == last_guid]
        if len(first_indexes) != 1 or len(last_indexes) != 1 or first_indexes[0] > last_indexes[0]:
            fail("P01 first/last cue span is invalid")
        span = cues[first_indexes[0]:last_indexes[0] + 1]
        if len(span) < 2 or any(
            not cue.get_editor_property("enabled")
            or "WING_PAIR" not in str(cue.get_editor_property("type")).upper()
            or not P01_LABEL.match(str(cue.get_editor_property("label")))
            for cue in span
        ):
            fail("P01 span contains disabled/non-Wing/non-P01 rows")

        segment_start_tick = int(round(section_start_s * tick_rate))
        segment_end_tick = int(round(section_end_s * tick_rate))
        lead_frames = int(settings.get_editor_property("lead_in_frames").value)
        tail_frames = int(settings.get_editor_property("tail_frames").value)
        station_tick = segment_start_tick + lead_frames
        station_cm = float(settings.get_editor_property("lead_in_distance_cm"))
        bays = []
        show_lights = {}
        disabled_lights = 0
        for ordinal, cue in enumerate(span):
            cue_guid = cue.get_editor_property("cue_guid")
            cue_guid_text = guid_text(cue_guid)
            cue_label = str(cue.get_editor_property("label"))
            pair = cue.get_editor_property("wing_pair")
            bay_lights = []
            attachments = list(pair.get_editor_property("attachments"))
            for attachment in attachments:
                if attachment.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT:
                    continue
                if not bool(attachment.get_editor_property("enabled")):
                    disabled_lights += 1
                    continue
                attachment_guid = attachment.get_editor_property("attachment_guid")
                attachment_guid_text = guid_text(attachment_guid)
                if attachment_guid_text in show_lights:
                    fail("duplicate enabled P01 attachment GUID %s" % attachment_guid_text)
                lighting = attachment.get_editor_property("lighting")
                intensity = float(lighting.get_editor_property("intensity"))
                row = {
                    "cue_guid": cue_guid_text,
                    "cue_label": cue_label,
                    "attachment_guid": attachment_guid_text,
                    "attachment_digits": guid_digits(attachment_guid),
                    "label": str(attachment.get_editor_property("label")),
                    "intensity": intensity,
                    "drama_before": drama_snapshot(lighting.get_editor_property("drama")),
                    "cue_index": first_indexes[0] + ordinal,
                }
                row["drama_after"] = dict(row["drama_before"])
                row["drama_after"]["strike_on_approach"] = False
                show_lights[attachment_guid_text] = row
                bay_lights.append(row)
            bays.append({
                "cue_guid": cue_guid_text,
                "cue_label": cue_label,
                "station_cm": station_cm,
                "pass_s": station_tick / tick_rate,
                "lights": bay_lights,
            })
            if ordinal + 1 < len(span):
                interval = int(pair.get_editor_property("interval_to_next").value)
                gap = float(pair.get_editor_property("gap_to_next_cm"))
                if interval <= 0 or gap <= 0.0:
                    fail("%s has non-positive interval/gap" % cue_label)
                station_tick += interval
                station_cm += gap
        expected_end_tick = station_tick + tail_frames
        if abs(expected_end_tick - segment_end_tick) > 1:
            fail("P01 Show end tick %d does not match Master end %d" % (expected_end_tick, segment_end_tick))
        total_distance_cm = station_cm + float(settings.get_editor_property("tail_distance_cm"))
        anchors = [(section_start_s, 0.0)] + [
            (float(bay["pass_s"]), float(bay["station_cm"])) for bay in bays
        ]
        if anchors[-1][0] < section_end_s - 1.0e-9:
            anchors.append((section_end_s, total_distance_cm))
        elif abs(anchors[-1][0] - section_end_s) <= 1.0e-9:
            anchors[-1] = (section_end_s, total_distance_cm)
        else:
            fail("last P01 pass is after the Master section end")
        if lead_frames > 0 and float(settings.get_editor_property("lead_in_distance_cm")) > 0.0:
            entry_speed = float(settings.get_editor_property("lead_in_distance_cm")) / (lead_frames / tick_rate)
        else:
            entry_speed = float(settings.get_editor_property("preferred_camera_speed_cm_per_second"))

        master_start = int(master.get_playback_start())
        master_end = int(master.get_playback_end())
        plan = plan_hallway_pingon(
            bays=bays,
            anchors=anchors,
            entry_speed_cm_s=entry_speed,
            passage_end_s=section_end_s,
            master_start_frame=master_start,
            master_end_frame=master_end,
            fps=fps,
            trigger_distance_cm=trigger_distance_m * 100.0,
            flicker_min_s=flicker_min_s,
            flicker_max_s=flicker_max_s,
        )
        planned_lights = {
            light["attachment_guid"]: light
            for bay in plan["bays"] for light in bay["lights"]
        }
        if set(planned_lights) != set(show_lights) or not planned_lights:
            fail("planned light census does not equal the enabled Show-light census")

        actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        passages = [
            actor for actor in actor_subsystem.get_all_level_actors()
            if isinstance(actor, unreal.InfinityStagePassageActor)
            and guid_text(actor.get_editor_property("passage_guid")) == passage_guid_text
            and asset_id(actor.get_editor_property("show_asset")) == SHOW_PATH
        ]
        if len(passages) != 1:
            fail("expected one materialized P01 actor, found %d" % len(passages))
        passage_actor = passages[0]
        actor_by_attachment = {}
        prefix = "infinitystage.attachment."
        for actor in passage_actor.get_editor_property("managed_attachment_actors"):
            for tag in actor.get_editor_property("tags"):
                text = str(tag).lower()
                if not text.startswith(prefix) or "|" not in text:
                    continue
                _cue_digits, attachment_digits = text[len(prefix):].split("|", 1)
                key = attachment_digits
                if key in actor_by_attachment:
                    fail("duplicate materialized attachment identity %s" % key)
                actor_by_attachment[key] = actor
        components = {}
        for attachment_guid, row in show_lights.items():
            actor = actor_by_attachment.get(row["attachment_digits"])
            if actor is None:
                fail("enabled light is not materialized: %s %s" % (row["cue_label"], row["label"]))
            component = actor.get_component_by_class(unreal.LightComponent)
            if component is None:
                fail("materialized light actor has no LightComponent: %s" % actor.get_actor_label())
            path = component.get_path_name()
            if path in components:
                fail("duplicate materialized LightComponent path %s" % path)
            if abs(float(component.get_editor_property("intensity")) - float(row["intensity"])) > 0.01:
                fail("editor light intensity differs from Show for %s" % row["label"])
            components[path] = {
                "component": component,
                "actor": actor,
                "attachment_guid": attachment_guid,
            }
        if len(components) != len(show_lights):
            fail("component census %d != Show lights %d" % (len(components), len(show_lights)))

        existing_by_object = {}
        for binding in master.get_bindings():
            for bound in master.locate_bound_objects(binding, world):
                existing_by_object.setdefault(bound.get_path_name(), []).append(binding)
        binding_preflight = {}
        for path, row in components.items():
            bindings = existing_by_object.get(path, [])
            if len(bindings) > 1:
                fail("component %s has %d existing Master bindings" % (path, len(bindings)))
            binding = bindings[0] if bindings else None
            if binding is not None:
                conflicts = [
                    track for track in binding.get_tracks()
                    if isinstance(track, unreal.MovieSceneFloatTrack)
                    and str(track.get_property_name()) == "Intensity"
                ]
                if conflicts and selected_mode != "REVERT":
                    fail("component already has an Intensity track: %s" % path)
            binding_preflight[path] = binding

        existing_owned = named_tracks(master)
        report.update({
            "show": SHOW_PATH,
            "master": MASTER_PATH,
            "passage_guid": passage_guid_text,
            "section_range_s": [section_start_s, section_end_s],
            "tick_rate": tick_rate,
            "fps": fps,
            "entry_speed_cm_s": entry_speed,
            "bays": len(bays),
            "enabled_lights": len(show_lights),
            "disabled_lights_untouched": disabled_lights,
            "preexisting_strike_writers": sum(
                1 for row in show_lights.values() if row["drama_before"]["strike_on_approach"]
            ),
            "preexisting_component_bindings_reused": sum(1 for value in binding_preflight.values() if value is not None),
            "owned_tracks_before": len(existing_owned),
            "plan": plan,
        })

        if selected_mode == "DRY":
            if existing_owned:
                fail("owned tracks already exist; run REVERT with its record")
            after_census = census()
            report["census_after"] = after_census
            if after_census != before_census:
                fail("DRY changed package census")
            report["ok"] = True
            _write_json(report_path, report)
            unreal.log(
                "P01_HALLWAY_PINGON_DRY_OK|run=%s|bays=%d|lights=%d|trigger_m=%.3f|"
                "first_trigger_s=%.3f|last_trigger_s=%.3f|flicker_s=%.3f-%.3f|"
                "mutated=0|census=%s" % (
                    run, len(bays), len(show_lights), trigger_distance_m,
                    plan["bays"][0]["trigger_s"], plan["bays"][-1]["trigger_s"],
                    flicker_min_s, flicker_max_s,
                    json.dumps(after_census, separators=(",", ":"), sort_keys=True),
                )
            )
            return

        if selected_mode == "APPLY":
            if os.path.exists(record_path):
                fail("apply record already exists; REVERT or archive it first")
            if existing_owned:
                fail("owned tracks already exist; REVERT first")
            backup = make_backup("PreP01HallwayPingOn-")
            record = {
                "status": "prepared",
                "run": run,
                "show": SHOW_PATH,
                "master": MASTER_PATH,
                "passage_guid": passage_guid_text,
                "track_name": TRACK_NAME,
                "backup": backup,
                "config": {
                    "trigger_distance_m": trigger_distance_m,
                    "flicker_min_s": flicker_min_s,
                    "flicker_max_s": flicker_max_s,
                    "fps": fps,
                },
                "show_lights": show_lights,
                "plan": plan,
                "bindings": [],
            }
            _write_json(record_path, record)
            reread = json.load(open(record_path, encoding="utf-8"))
            if reread.get("status") != "prepared" or len(reread.get("show_lights", {})) != len(show_lights):
                fail("prepared revert record did not read back completely")

            # One writer per lamp: generic Sequencer Intensity owns brightness,
            # while any Light Drama slow-move remains free to own aim only.
            changed_drama = 0
            updated_cues = list(cues)
            for cue_index in range(first_indexes[0], last_indexes[0] + 1):
                cue = updated_cues[cue_index]
                pair = cue.get_editor_property("wing_pair")
                attachments = list(pair.get_editor_property("attachments"))
                for attachment_index, attachment in enumerate(attachments):
                    attachment_guid = guid_text(attachment.get_editor_property("attachment_guid"))
                    row = show_lights.get(attachment_guid)
                    if row is None:
                        continue
                    lighting = attachment.get_editor_property("lighting")
                    drama = lighting.get_editor_property("drama")
                    if bool(drama.get_editor_property("strike_on_approach")):
                        drama.set_editor_property("strike_on_approach", False)
                        lighting.set_editor_property("drama", drama)
                        attachment.set_editor_property("lighting", lighting)
                        attachments[attachment_index] = attachment
                        changed_drama += 1
                pair.set_editor_property("attachments", attachments)
                cue.set_editor_property("wing_pair", pair)
                updated_cues[cue_index] = cue
            show.set_editor_property("cues", updated_cues)

            for path in sorted(components):
                component = components[path]["component"]
                attachment_guid = components[path]["attachment_guid"]
                planned = planned_lights[attachment_guid]
                binding = binding_preflight[path]
                created = binding is None
                if created:
                    binding = master.add_possessable(component)
                    if binding is None or not binding.is_valid():
                        fail("could not add component possessable: %s" % path)
                    binding.set_display_name("P01 Ping | %s | %s" % (
                        show_lights[attachment_guid]["cue_label"],
                        show_lights[attachment_guid]["label"],
                    ))
                track = binding.add_track(unreal.MovieSceneFloatTrack)
                if track is None:
                    fail("could not add Intensity track: %s" % path)
                track.set_property_name_and_path("Intensity", "Intensity")
                track.set_display_name(TRACK_NAME)
                section = track.add_section()
                if section is None:
                    fail("could not add Intensity section: %s" % path)
                section.set_range(master_start, master_end + 1)
                channels = list(section.get_all_channels())
                if len(channels) != 1:
                    fail("Intensity track produced %d channels: %s" % (len(channels), path))
                channel = channels[0]
                channel.set_default(0.0)
                for key in planned["keys"]:
                    made = channel.add_key(
                        unreal.FrameNumber(int(key["frame"])),
                        float(key["value"]),
                        time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                        interpolation=unreal.MovieSceneKeyInterpolation.CONSTANT,
                    )
                    if made is None:
                        fail("add_key returned None: %s frame %s" % (path, key["frame"]))
                binding_row = {
                    "binding_guid": guid_text(binding.get_id()),
                    "created_binding": created,
                    "component_path": path,
                    "attachment_guid": attachment_guid,
                    "expected_track": {
                        "default": 0.0,
                        "keys": [
                            {"frame": int(key["frame"]), "value": round(float(key["value"]), 6)}
                            for key in planned["keys"]
                        ],
                    },
                }
                record["bindings"].append(binding_row)
            record["changed_drama"] = changed_drama
            _write_json(record_path, record)

            allowed_content = {SHOW_PATH, MASTER_PATH}
            dirty_before_save = census()
            if set(dirty_before_save["content"]) - allowed_content or dirty_before_save["maps"]:
                fail("out-of-scope dirty packages before save: %s" % json.dumps(dirty_before_save, sort_keys=True))
            if not unreal.EditorAssetLibrary.save_loaded_asset(show, False):
                fail("targeted Show save failed")
            if not unreal.EditorAssetLibrary.save_loaded_asset(master, False):
                fail("targeted Master save failed")

            # Saved read-back from the loaded assets: exact channels + drama.
            current_bindings = binding_guid_map(master)
            for binding_row in record["bindings"]:
                binding = current_bindings.get(binding_row["binding_guid"])
                if binding is None:
                    fail("saved binding missing: %s" % binding_row["binding_guid"])
                _track, snapshot = intensity_track_snapshot(binding)
                if snapshot != binding_row["expected_track"]:
                    fail("saved Intensity read-back differs: %s" % binding_row["component_path"])
            current_show = {}
            for cue in show.get_editor_property("cues"):
                for attachment in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
                    attachment_guid = guid_text(attachment.get_editor_property("attachment_guid"))
                    if attachment_guid in show_lights:
                        current_show[attachment_guid] = drama_snapshot(
                            attachment.get_editor_property("lighting").get_editor_property("drama")
                        )
            for attachment_guid, row in show_lights.items():
                if current_show.get(attachment_guid) != row["drama_after"]:
                    fail("saved Show drama read-back differs: %s" % attachment_guid)
            after_census = census()
            if after_census != {"content": [], "maps": []}:
                fail("dirty packages remain after targeted saves: %s" % json.dumps(after_census, sort_keys=True))
            record["status"] = "applied"
            record["applied_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            _write_json(record_path, record)
            if queue_test:
                unreal.SystemLibrary.execute_console_command(world, "Automation RunTests " + AUTOMATION_TEST)
            report.update({
                "ok": True,
                "backup": backup,
                "record": record_path,
                "changed_drama": changed_drama,
                "bindings": len(record["bindings"]),
                "census_after": after_census,
                "saved_master_matches_show": "QUEUED_NOT_PASSED" if queue_test else "NOT_QUEUED",
            })
            _write_json(report_path, report)
            unreal.log(
                "P01_HALLWAY_PINGON_APPLIED|run=%s|bays=%d|lights=%d|bindings=%d|"
                "drama_writers_disabled=%d|show_saved=1|master_saved=1|readback=1|"
                "SavedMasterMatchesShow=%s|backup=%s|census=%s" % (
                    run, len(bays), len(show_lights), len(record["bindings"]), changed_drama,
                    "QUEUED_NOT_PASSED" if queue_test else "NOT_QUEUED",
                    backup["directory"], json.dumps(after_census, separators=(",", ":"), sort_keys=True),
                )
            )
            return

        # REVERT -----------------------------------------------------------------
        if not os.path.isfile(record_path):
            fail("REVERT record is absent")
        record = json.load(open(record_path, encoding="utf-8"))
        if record.get("status") != "applied" or record.get("show") != SHOW_PATH \
                or record.get("master") != MASTER_PATH or record.get("track_name") != TRACK_NAME:
            fail("REVERT record is not an applied record for this tool")
        if record.get("passage_guid") != passage_guid_text:
            fail("REVERT record P01 identity differs from the current Show")
        if len(record.get("bindings", [])) != len(show_lights):
            fail("REVERT record/current light census differs")
        current_bindings = binding_guid_map(master)
        for binding_row in record["bindings"]:
            binding = current_bindings.get(binding_row["binding_guid"])
            if binding is None:
                fail("REVERT binding missing: %s" % binding_row["binding_guid"])
            _track, snapshot = intensity_track_snapshot(binding)
            if snapshot != binding_row["expected_track"]:
                fail("REVERT refuses modified Intensity track: %s" % binding_row["component_path"])
        for attachment_guid, row in record["show_lights"].items():
            current = show_lights.get(attachment_guid)
            if current is None or current["drama_before"] != row["drama_after"]:
                # show_lights.drama_before is the current snapshot in REVERT mode.
                fail("REVERT refuses modified Show drama: %s" % attachment_guid)
        backup = make_backup("PreP01HallwayPingOnRevert-")

        # Restore Show drama exactly where APPLY changed its writer flag.
        updated_cues = list(cues)
        recorded_lights = record["show_lights"]
        restored_drama = 0
        for cue_index in range(first_indexes[0], last_indexes[0] + 1):
            cue = updated_cues[cue_index]
            pair = cue.get_editor_property("wing_pair")
            attachments = list(pair.get_editor_property("attachments"))
            for attachment_index, attachment in enumerate(attachments):
                attachment_guid = guid_text(attachment.get_editor_property("attachment_guid"))
                recorded = recorded_lights.get(attachment_guid)
                if recorded is None:
                    continue
                wanted = bool(recorded["drama_before"]["strike_on_approach"])
                lighting = attachment.get_editor_property("lighting")
                drama = lighting.get_editor_property("drama")
                if bool(drama.get_editor_property("strike_on_approach")) != wanted:
                    drama.set_editor_property("strike_on_approach", wanted)
                    lighting.set_editor_property("drama", drama)
                    attachment.set_editor_property("lighting", lighting)
                    attachments[attachment_index] = attachment
                    restored_drama += 1
            pair.set_editor_property("attachments", attachments)
            cue.set_editor_property("wing_pair", pair)
            updated_cues[cue_index] = cue
        show.set_editor_property("cues", updated_cues)

        # Remove exactly the owned track, or the whole binding when APPLY made it.
        for binding_row in record["bindings"]:
            binding = current_bindings[binding_row["binding_guid"]]
            track, _snapshot = intensity_track_snapshot(binding)
            if binding_row["created_binding"]:
                binding.remove()
            elif not binding.remove_track(track):
                fail("REVERT could not remove owned track: %s" % binding_row["component_path"])
        if named_tracks(master):
            fail("owned tracks remain before REVERT save")

        allowed_content = {SHOW_PATH, MASTER_PATH}
        dirty_before_save = census()
        if set(dirty_before_save["content"]) - allowed_content or dirty_before_save["maps"]:
            fail("out-of-scope dirty packages before REVERT save: %s" % json.dumps(dirty_before_save, sort_keys=True))
        if not unreal.EditorAssetLibrary.save_loaded_asset(show, False):
            fail("targeted Show REVERT save failed")
        if not unreal.EditorAssetLibrary.save_loaded_asset(master, False):
            fail("targeted Master REVERT save failed")
        if named_tracks(master):
            fail("owned tracks remain after REVERT save")
        current_show = {}
        for cue in show.get_editor_property("cues"):
            for attachment in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
                attachment_guid = guid_text(attachment.get_editor_property("attachment_guid"))
                if attachment_guid in recorded_lights:
                    current_show[attachment_guid] = drama_snapshot(
                        attachment.get_editor_property("lighting").get_editor_property("drama")
                    )
        for attachment_guid, row in recorded_lights.items():
            if current_show.get(attachment_guid) != row["drama_before"]:
                fail("REVERT Show read-back differs: %s" % attachment_guid)
        after_census = census()
        if after_census != {"content": [], "maps": []}:
            fail("dirty packages remain after REVERT saves: %s" % json.dumps(after_census, sort_keys=True))
        archived = record_path + ".reverted-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        os.rename(record_path, archived)
        if queue_test:
            unreal.SystemLibrary.execute_console_command(world, "Automation RunTests " + AUTOMATION_TEST)
        report.update({
            "ok": True,
            "backup": backup,
            "archived_record": archived,
            "restored_drama": restored_drama,
            "census_after": after_census,
            "saved_master_matches_show": "QUEUED_NOT_PASSED" if queue_test else "NOT_QUEUED",
        })
        _write_json(report_path, report)
        unreal.log(
            "P01_HALLWAY_PINGON_REVERTED|run=%s|lights=%d|bindings_removed=%d|"
            "drama_writers_restored=%d|show_saved=1|master_saved=1|readback=1|"
            "SavedMasterMatchesShow=%s|backup=%s|record=%s|census=%s" % (
                run, len(recorded_lights), len(record["bindings"]), restored_drama,
                "QUEUED_NOT_PASSED" if queue_test else "NOT_QUEUED",
                backup["directory"], archived,
                json.dumps(after_census, separators=(",", ":"), sort_keys=True),
            )
        )
    except HallwayPingError:
        raise
    except Exception as error:  # noqa: BLE001 - Unreal needs one domain marker
        fail(error)


if __name__ == "__main__":
    main()
