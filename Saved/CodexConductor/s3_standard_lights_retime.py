"""Retimes S3's standard-light strike ramps without opening Sequencer.

Modes are DRY (default), APPLY, and REVERT.  The tool targets only Intensity
channels whose binding/parent label begins with the family names used by
InfinityStageArrival.cpp: S3 Uplight, S3 Practical, and S3 Lattice Glow.
"""
import datetime
import json
import math
import os
import shutil

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE_PATH = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
PREFIXES = ("S3 Uplight ", "S3 Practical ", "S3 Lattice Glow ")
EXPECTED_CHANNELS = 41
TARGET_STRIKE_SECONDS = 10.0
VALUE_TOLERANCE = 1.0e-6


class RetimeError(RuntimeError):
    pass


def _asset_id(value):
    return value.get_path_name().split(".", 1)[0] if value is not None else None


def _census():
    return {
        "content": sorted(p.get_name().split(".", 1)[0]
                          for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(p.get_name().split(".", 1)[0]
                       for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def _write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def _key_row(key, tick_rate):
    when = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
    frame = int(when.frame_number.value)
    sub_frame = float(getattr(when, "sub_frame", 0.0))
    interpolation = None
    if hasattr(key, "get_interpolation_mode"):
        value = key.get_interpolation_mode()
        interpolation = value.name if hasattr(value, "name") else str(value)
    return {
        "frame": frame,
        "sub_frame": sub_frame,
        "seconds": (frame + sub_frame) / tick_rate,
        "value": float(key.get_value()),
        "interpolation": interpolation,
    }


def _plain(rows):
    return [{key: row[key] for key in ("frame", "sub_frame", "value", "interpolation")}
            for row in rows]


def _binding_label(binding):
    parent = binding.get_parent()
    parent_name = str(parent.get_display_name()) if parent and parent.is_valid() else ""
    own_name = str(binding.get_display_name())
    if parent_name.startswith(PREFIXES):
        return parent_name
    if own_name.startswith(PREFIXES):
        return own_name
    return None


def _discover(sequence, tick_rate):
    rows = {}
    objects = {}
    for binding in sequence.get_bindings():
        label = _binding_label(binding)
        if label is None:
            continue
        channels = []
        for track in binding.get_tracks():
            if not isinstance(track, unreal.MovieSceneFloatTrack) \
                    or str(track.get_property_name()) != "Intensity":
                continue
            for section in track.get_sections():
                channels.extend(section.get_all_channels())
        if not channels:
            continue
        if len(channels) != 1 or label in rows:
            raise RetimeError("%s does not have exactly one unique Intensity channel" % label)
        keys = sorted(
            list(channels[0].get_keys()),
            key=lambda key: (
                key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value,
                float(getattr(key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION),
                              "sub_frame", 0.0)),
            ),
        )
        key_rows = [_key_row(key, tick_rate) for key in keys]
        candidates = [index for index in range(len(key_rows) - 1)
                      if abs(key_rows[index]["value"]) <= VALUE_TOLERANCE
                      and key_rows[index + 1]["value"] > VALUE_TOLERANCE]
        if len(candidates) != 1:
            raise RetimeError("%s has %d zero-to-positive strike ramps: %s" %
                              (label, len(candidates), json.dumps(key_rows)))
        rows[label] = {"strike_index": candidates[0], "keys": key_rows}
        objects[label] = keys
    if len(rows) != EXPECTED_CHANNELS:
        raise RetimeError("expected %d standard-light channels, found %d: %s" %
                          (EXPECTED_CHANNELS, len(rows), ",".join(sorted(rows))))
    return rows, objects


def _build_plan(before, tick_rate):
    earliest_tick = min(
        before[label]["keys"][before[label]["strike_index"]]["frame"]
        for label in before
    )
    earliest_sub = min(
        before[label]["keys"][before[label]["strike_index"]]["sub_frame"]
        for label in before
        if before[label]["keys"][before[label]["strike_index"]]["frame"] == earliest_tick
    )
    if abs(earliest_sub) > 1.0e-9:
        raise RetimeError("earliest strike has a non-zero sub-frame: %.9f" % earliest_sub)
    target_tick = int(round(TARGET_STRIKE_SECONDS * tick_rate))
    shift_tick = target_tick - earliest_tick
    if shift_tick == 0:
        raise RetimeError("standard-light strike is already at %.4f s; no retime is required" %
                          TARGET_STRIKE_SECONDS)
    planned = {}
    for label, row in before.items():
        after = []
        for index, key in enumerate(row["keys"]):
            copy = dict(key)
            if index >= row["strike_index"]:
                copy["frame"] += shift_tick
                copy["seconds"] = (copy["frame"] + copy["sub_frame"]) / tick_rate
            after.append(copy)
        times = [(key["frame"], key["sub_frame"]) for key in after]
        if times != sorted(times) or len(times) != len(set(times)):
            raise RetimeError("%s planned times are not unique and ordered" % label)
        planned[label] = {
            "strike_index": row["strike_index"],
            "before": row["keys"],
            "after": after,
            "before_strike_s": row["keys"][row["strike_index"]]["seconds"],
            "after_strike_s": after[row["strike_index"]]["seconds"],
        }
    return {
        "target_strike_seconds": TARGET_STRIKE_SECONDS,
        "earliest_before_seconds": earliest_tick / tick_rate,
        "earliest_after_seconds": target_tick / tick_rate,
        "shift_tick": shift_tick,
        "shift_seconds": shift_tick / tick_rate,
        "channels": planned,
    }


def _set_times(key_objects, rows):
    if len(key_objects) != len(rows):
        raise RetimeError("key count changed before mutation")
    for key, row in zip(key_objects, rows):
        key.set_time(
            unreal.FrameNumber(value=int(row["frame"])),
            float(row["sub_frame"]),
            unreal.MovieSceneTimeUnit.TICK_RESOLUTION,
        )


def _snapshot_plain(discovered):
    return {label: _plain(row["keys"]) for label, row in sorted(discovered.items())}


def _backup(stamp, prefix):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", prefix + stamp)
    os.makedirs(backup, exist_ok=False)
    source = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
        SEQUENCE_PATH[len("/Game/"):].replace("/", os.sep) + ".uasset",
    )
    if not os.path.isfile(source):
        raise RetimeError("backup source is absent: " + source)
    destination = os.path.join(backup, os.path.basename(source))
    shutil.copy2(source, destination)
    if os.path.getsize(source) != os.path.getsize(destination):
        raise RetimeError("backup size mismatch")
    return backup


def main(mode=None):
    selected = str(mode or globals().get("S3_STD_LIGHTS_MODE", "DRY")).upper()
    if selected not in ("DRY", "APPLY", "REVERT"):
        raise RetimeError("mode must be DRY, APPLY, or REVERT")
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                        "CodexConductor")
    report_path = os.path.join(here, "s3_standard_lights_retime_report.json")
    record_path = os.path.join(here, "s3_standard_lights_retime_record.json")
    report = {"ok": False, "mode": selected, "run": run, "asset": SEQUENCE_PATH}

    def fail(message):
        report["error"] = str(message)
        _write_json(report_path, report)
        unreal.log_error("S3_STANDARD_LIGHTS_RETIME_STOPPED|run=%s|mode=%s|%s" %
                         (run, selected, message))
        raise RetimeError(str(message))

    try:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if editor.get_game_world() is not None:
            fail("PIE_OR_SIE_ACTIVE")
        if world is None or _asset_id(world) != EXPECTED_WORLD:
            fail("WRONG_WORLD|actual=" + str(_asset_id(world)))
        if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
            fail("SEQUENCER_IS_OPEN")
        dirty_before = _census()
        report["dirty_before"] = dirty_before
        if dirty_before != {"content": [], "maps": []}:
            fail("DIRTY_BEFORE|census=" + json.dumps(dirty_before, sort_keys=True))
        if selected == "APPLY" and os.path.exists(record_path):
            fail("APPLY_RECORD_ALREADY_EXISTS")
        if selected == "REVERT" and not os.path.isfile(record_path):
            fail("REVERT_RECORD_ABSENT")

        sequence = unreal.load_asset(SEQUENCE_PATH)
        if sequence is None:
            fail("SEQUENCE_MISSING")
        tick = sequence.get_tick_resolution()
        tick_rate = float(tick.numerator) / float(tick.denominator)
        if not math.isfinite(tick_rate) or tick_rate <= 0.0:
            fail("INVALID_TICK_RATE")
        discovered, key_objects = _discover(sequence, tick_rate)
        before_plain = _snapshot_plain(discovered)
        plan = _build_plan(discovered, tick_rate) if selected != "REVERT" else None
        report.update({"tick_rate": tick_rate, "channels_before": before_plain, "plan": plan})

        if selected == "DRY":
            dirty_after = _census()
            if dirty_after != dirty_before:
                fail("DRY_CHANGED_CENSUS|census=" + json.dumps(dirty_after, sort_keys=True))
            report.update({"ok": True, "dirty_after": dirty_after})
            _write_json(report_path, report)
            unreal.log("S3_STANDARD_LIGHTS_RETIME_DRY_OK|run=%s|channels=%d|earliest_before=%.6f|earliest_after=%.6f|shift_s=%.6f|rows=%s|census=%s" %
                       (run, len(plan["channels"]), plan["earliest_before_seconds"],
                        plan["earliest_after_seconds"], plan["shift_seconds"],
                        json.dumps(plan["channels"], separators=(",", ":"), sort_keys=True),
                        json.dumps(dirty_after, separators=(",", ":"), sort_keys=True)))
            return

        if selected == "APPLY":
            backup = _backup(run, "PreS3StdLightsRetime-")
            expected_after = {label: _plain(row["after"])
                              for label, row in sorted(plan["channels"].items())}
            record = {
                "status": "prepared", "run": run, "asset": SEQUENCE_PATH,
                "tick_rate": tick_rate, "backup": backup,
                "before": before_plain, "after": expected_after,
                "shift_tick": plan["shift_tick"], "shift_seconds": plan["shift_seconds"],
            }
            _write_json(record_path, record, exclusive=True)
            for label in sorted(plan["channels"]):
                _set_times(key_objects[label], plan["channels"][label]["after"])
            touched = _census()
            if touched != {"content": [SEQUENCE_PATH], "maps": []}:
                fail("TOUCHED_CENSUS|actual=" + json.dumps(touched, sort_keys=True))
            current, _ = _discover(sequence, tick_rate)
            if _snapshot_plain(current) != expected_after:
                fail("IN_MEMORY_READBACK_MISMATCH")
            if not unreal.EditorAssetLibrary.save_asset(SEQUENCE_PATH, only_if_is_dirty=False):
                fail("SAVE_FAILED")
            saved, _ = _discover(sequence, tick_rate)
            if _snapshot_plain(saved) != expected_after:
                fail("SAVED_READBACK_MISMATCH")
            final = _census()
            if final != {"content": [], "maps": []}:
                fail("DIRTY_AFTER_SAVE|census=" + json.dumps(final, sort_keys=True))
            record.update({"status": "applied", "applied_at": run})
            _write_json(record_path, record)
            report.update({"ok": True, "backup": backup, "dirty_touched": touched,
                           "dirty_after": final, "channels_after": expected_after})
            _write_json(report_path, report)
            unreal.log("S3_STANDARD_LIGHTS_RETIME_APPLIED|run=%s|channels=%d|target_s=%.4f|shift_s=%.6f|backup=%s|touched=%s|census=%s" %
                       (run, len(expected_after), TARGET_STRIKE_SECONDS, plan["shift_seconds"],
                        backup, json.dumps(touched, separators=(",", ":"), sort_keys=True),
                        json.dumps(final, separators=(",", ":"), sort_keys=True)))
            return

        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("status") != "applied" or record.get("asset") != SEQUENCE_PATH:
            fail("REVERT_RECORD_CONTEXT")
        if before_plain != record.get("after"):
            fail("REVERT_LIVE_STATE_MISMATCH")
        backup = _backup(run, "PreS3StdLightsRetimeRevert-")
        for label in sorted(record["before"]):
            _set_times(key_objects[label], record["before"][label])
        touched = _census()
        if touched != {"content": [SEQUENCE_PATH], "maps": []}:
            fail("REVERT_TOUCHED_CENSUS|actual=" + json.dumps(touched, sort_keys=True))
        if not unreal.EditorAssetLibrary.save_asset(SEQUENCE_PATH, only_if_is_dirty=False):
            fail("REVERT_SAVE_FAILED")
        restored, _ = _discover(sequence, tick_rate)
        if _snapshot_plain(restored) != record.get("before"):
            fail("REVERT_READBACK_MISMATCH")
        final = _census()
        if final != {"content": [], "maps": []}:
            fail("REVERT_DIRTY_AFTER_SAVE|census=" + json.dumps(final, sort_keys=True))
        archived = record_path + ".reverted-" + run
        os.rename(record_path, archived)
        report.update({"ok": True, "backup": backup, "archived_record": archived,
                       "dirty_after": final})
        _write_json(report_path, report)
        unreal.log("S3_STANDARD_LIGHTS_RETIME_REVERTED|run=%s|channels=%d|backup=%s|record=%s|census=%s" %
                   (run, len(record["before"]), backup, archived,
                    json.dumps(final, separators=(",", ":"), sort_keys=True)))
    except RetimeError:
        raise
    except Exception as error:
        fail(error)


if __name__ == "__main__":
    main()
