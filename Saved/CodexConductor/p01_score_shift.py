"""Guarded one-off repair for Passage 1's displaced wing score.

Modes are selected by ``P01_SCORE_MODE`` when this file is executed through
runpy.  The default is DRY; the only accepted values are DRY, APPLY, REVERT.

DRY reads the Master asset directly (it never opens or evaluates Sequencer),
prints every P01 channel key, and proves that the three wing channels admit one
constant +15 s shift.  APPLY backs up and saves only the Master.  REVERT uses
the exact before/after rows in p01_score_shift_record.json.

After APPLY or REVERT, run only InfinityStage.Editor.SavedMasterMatchesShow.
This file deliberately does not queue automation, open Unreal UI, or save a
map/Show asset.
"""

import datetime
import json
import math
import os
import shutil


MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
EXPECTED_PROJECT = os.path.normcase(os.path.normpath("E:/PussStage"))
PASSAGE_LABEL = "Passage 1"
HISTORICAL_FIRST_OFFSET_S = 0.0
EXPECTED_SHIFT_S = 15.0
TARGET_VALUES = {
    "Wing.InwardTravelScale": [0.5, 1.3, 1.0],
    "Wing.CycleRateScale": [0.6, 2.0, 1.0],
    "Wing.PhaseBiasCycles": [0.0, 1.0, 0.0],
}


class ScoreShiftError(RuntimeError):
    pass


def _finite_number(value, label):
    number = float(value)
    if not math.isfinite(number):
        raise ScoreShiftError("%s is not finite: %r" % (label, value))
    return number


def plan_score_shift(section_start_tick, tick_rate, target_channels):
    """Return an exact constant-shift plan for plain JSON-compatible rows.

    Each channel row is ``{"frame": int, "sub_frame": float, "value":
    float}``.  A score is accepted only when all three expected channels have
    three synchronized keys with the measured value arc and every channel
    independently derives the same shift.
    """
    start = int(section_start_tick)
    rate = _finite_number(tick_rate, "tick_rate")
    if rate <= 0.0:
        raise ScoreShiftError("tick_rate must be positive")
    if set(target_channels) != set(TARGET_VALUES):
        raise ScoreShiftError(
            "target channel set is %r, expected %r"
            % (sorted(target_channels), sorted(TARGET_VALUES))
        )

    normalized = {}
    deltas = []
    shared_times = None
    desired_first = start + int(round(HISTORICAL_FIRST_OFFSET_S * rate))
    for name in sorted(TARGET_VALUES):
        rows = sorted(
            [
                {
                    "frame": int(row["frame"]),
                    "sub_frame": _finite_number(row.get("sub_frame", 0.0), name + " sub_frame"),
                    "value": _finite_number(row["value"], name + " value"),
                }
                for row in target_channels[name]
            ],
            key=lambda row: (row["frame"], row["sub_frame"]),
        )
        if len(rows) != 3:
            raise ScoreShiftError("%s has %d keys, expected 3" % (name, len(rows)))
        values = [row["value"] for row in rows]
        expected_values = TARGET_VALUES[name]
        if any(abs(actual - expected) > 1.0e-6 for actual, expected in zip(values, expected_values)):
            raise ScoreShiftError(
                "%s values are %r, expected %r" % (name, values, expected_values)
            )
        times = [(row["frame"], row["sub_frame"]) for row in rows]
        if shared_times is None:
            shared_times = times
        elif times != shared_times:
            raise ScoreShiftError(
                "%s key times are %r, not the shared score times %r"
                % (name, times, shared_times)
            )
        if abs(rows[0]["sub_frame"]) > 1.0e-9:
            raise ScoreShiftError("%s first key has a non-zero sub-frame" % name)
        deltas.append(desired_first - rows[0]["frame"])
        normalized[name] = rows

    if len(set(deltas)) != 1:
        raise ScoreShiftError("score offsets are not a clean constant: %r" % deltas)
    shift_tick = deltas[0]
    shift_s = shift_tick / rate
    if abs(shift_s - EXPECTED_SHIFT_S) > 0.5 / rate:
        raise ScoreShiftError(
            "derived shift is %.9f s (%d ticks), expected +%.1f s"
            % (shift_s, shift_tick, EXPECTED_SHIFT_S)
        )

    after = {
        name: [
            {
                "frame": row["frame"] + shift_tick,
                "sub_frame": row["sub_frame"],
                "value": row["value"],
            }
            for row in rows
        ]
        for name, rows in normalized.items()
    }
    return {
        "section_start_tick": start,
        "section_start_s": start / rate,
        "historical_first_offset_s": HISTORICAL_FIRST_OFFSET_S,
        "desired_first_tick": desired_first,
        "current_first_tick": shared_times[0][0],
        "current_first_minus_section_start_s": (shared_times[0][0] - start) / rate,
        "shift_tick": shift_tick,
        "shift_s": shift_s,
        "before": normalized,
        "after": after,
    }


def revert_rows_from_plan(plan):
    """Pure helper used by the offline round-trip control."""
    return {
        name: [dict(row) for row in rows]
        for name, rows in plan["before"].items()
    }


def _guid_text(unreal, value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _asset_id(value):
    return value.get_path_name().split(".", 1)[0] if value is not None else None


def _census(unreal):
    return {
        "maps": sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        ),
        "content": sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        ),
    }


def _key_row(unreal, key, rate):
    when = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
    frame = int(when.frame_number.value)
    sub_frame = float(getattr(when, "sub_frame", 0.0))
    return {
        "frame": frame,
        "sub_frame": sub_frame,
        "seconds": (frame + sub_frame) / rate,
        "value": float(key.get_value()),
    }


def _plain_rows(rows):
    return [
        {
            "frame": int(row["frame"]),
            "sub_frame": float(row.get("sub_frame", 0.0)),
            "value": float(row["value"]),
        }
        for row in rows
    ]


def _snapshot_channels(unreal, section, rate):
    result = {}
    objects = {}
    for channel in section.get_all_channels():
        name = str(channel.get_editor_property("channel_name"))
        if name in result:
            raise ScoreShiftError("duplicate P01 channel name %r" % name)
        keys = list(channel.get_keys())
        rows = sorted(
            [_key_row(unreal, key, rate) for key in keys],
            key=lambda row: (row["frame"], row["sub_frame"]),
        )
        result[name] = rows
        objects[name] = sorted(
            keys,
            key=lambda key: (
                key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value,
                float(getattr(key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION), "sub_frame", 0.0)),
            ),
        )
    return result, objects


def _find_p01(unreal, show, master):
    rows = [
        row
        for row in show.get_editor_property("passage_settings")
        if str(row.get_editor_property("label")) == PASSAGE_LABEL
    ]
    if len(rows) != 1:
        raise ScoreShiftError("expected one %s Show row, found %d" % (PASSAGE_LABEL, len(rows)))
    wanted = _guid_text(unreal, rows[0].get_editor_property("passage_guid"))
    matches = []
    for track in master.get_tracks():
        if "InfinityPassage" not in track.get_class().get_name():
            continue
        for section in track.get_sections():
            if _guid_text(unreal, section.get_editor_property("passage_guid")) == wanted:
                matches.append(section)
    if len(matches) != 1:
        raise ScoreShiftError("expected one P01 Master section, found %d" % len(matches))
    return wanted, matches[0]


def _content_file(unreal, asset_path):
    relative = asset_path[len("/Game/"):] + ".uasset"
    return os.path.normpath(
        os.path.join(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
            relative,
        )
    )


def _backup_master(unreal, prefix, stamp):
    backup = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
        "Backups",
        prefix + stamp,
    )
    if os.path.exists(backup):
        raise ScoreShiftError("backup path already exists: %s" % backup)
    os.makedirs(backup)
    source = _content_file(unreal, MASTER)
    if not os.path.isfile(source):
        raise ScoreShiftError("Master package file is missing: %s" % source)
    shutil.copy2(source, os.path.join(backup, os.path.basename(source)))
    return backup


def _set_channel_times(unreal, channel_objects, rows):
    if len(channel_objects) != len(rows):
        raise ScoreShiftError("key count changed before mutation")
    for key, row in zip(channel_objects, rows):
        key.set_time(
            unreal.FrameNumber(value=int(row["frame"])),
            float(row.get("sub_frame", 0.0)),
            unreal.MovieSceneTimeUnit.TICK_RESOLUTION,
        )


def _plain_snapshot(snapshot):
    return {name: _plain_rows(rows) for name, rows in snapshot.items()}


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def main(mode=None):
    import unreal

    selected_mode = str(mode or globals().get("P01_SCORE_MODE", "DRY")).strip().upper()
    if selected_mode not in ("DRY", "APPLY", "REVERT"):
        raise ScoreShiftError("mode must be DRY, APPLY, or REVERT")
    here = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor",
    )
    report_path = os.path.join(here, "p01_score_shift_report.json")
    record_path = os.path.join(here, "p01_score_shift_record.json")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {"ok": False, "mode": selected_mode, "master": MASTER}

    def fail(message):
        report["error"] = str(message)
        _write_json(report_path, report)
        unreal.log_error("P01_SCORE_SHIFT_STOPPED|mode=%s|%s" % (selected_mode, message))
        raise ScoreShiftError(str(message))

    try:
        project = os.path.normcase(
            os.path.normpath(
                unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
            )
        ).rstrip("\\/")
        if project != EXPECTED_PROJECT.rstrip("\\/"):
            fail("wrong project directory %s" % project)
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world is None or _asset_id(world) != EXPECTED_WORLD:
            fail("wrong editor world %s" % _asset_id(world))
        if editor.get_game_world() is not None:
            fail("PIE/SIE is active")

        dirty_before = _census(unreal)
        report["dirty_before"] = dirty_before
        if selected_mode != "DRY" and (dirty_before["maps"] or dirty_before["content"]):
            fail("mutation requires zero dirty map/content packages: %s" % json.dumps(dirty_before, sort_keys=True))

        show = unreal.load_asset(SHOW)
        master = unreal.load_asset(MASTER)
        if show is None or master is None:
            fail("Show or Master failed to load")
        tick = master.get_tick_resolution()
        rate = tick.numerator / float(tick.denominator)
        if abs(rate - 24000.0) > 1.0e-6:
            fail("Master tick rate is %.9f, expected 24000" % rate)
        passage_guid, section = _find_p01(unreal, show, master)
        section_start_s = float(section.get_start_frame_seconds())
        section_end_s = float(section.get_end_frame_seconds())
        section_start_tick = int(round(section_start_s * rate))
        before, channel_objects = _snapshot_channels(unreal, section, rate)
        target_before = {
            name: _plain_rows(before.get(name, [])) for name in sorted(TARGET_VALUES)
        }
        report.update(
            {
                "passage_guid": passage_guid,
                "tick_rate": rate,
                "section_range_s": [section_start_s, section_end_s],
                "all_channels_before": before,
            }
        )

        # The applied state intentionally has its first key at the P01 start, so
        # deriving a fresh +15 s plan from it would (correctly) refuse.  REVERT
        # validates against the recorded after snapshot instead.
        plan = None
        if selected_mode != "REVERT":
            plan = plan_score_shift(section_start_tick, rate, target_before)
            report["derivation"] = plan

        if selected_mode == "DRY":
            dirty_after = _census(unreal)
            report["dirty_after"] = dirty_after
            if dirty_after != dirty_before:
                fail("DRY changed the dirty census")
            report["ok"] = True
            _write_json(report_path, report)
            unreal.log(
                "P01_SCORE_SHIFT_DRY|shift_s=%.6f|first_minus_start_s=%.6f|channels=%s|census=%s"
                % (
                    plan["shift_s"],
                    plan["current_first_minus_section_start_s"],
                    json.dumps(before, sort_keys=True),
                    json.dumps(dirty_after, sort_keys=True),
                )
            )
            return

        if selected_mode == "APPLY":
            if os.path.exists(record_path):
                fail("apply record already exists; revert or archive it first")
            backup = _backup_master(unreal, "PreP01ScoreShift-", stamp)
            before_plain = _plain_snapshot(before)
            expected_after_all = dict(before_plain)
            expected_after_all.update(plan["after"])
            record = {
                "status": "prepared",
                "master": MASTER,
                "passage_guid": passage_guid,
                "tick_rate": rate,
                "section_range_s": [section_start_s, section_end_s],
                "shift_tick": plan["shift_tick"],
                "shift_s": plan["shift_s"],
                "backup": backup,
                "before_all_channels": before_plain,
                "after_all_channels": expected_after_all,
            }
            _write_json(record_path, record)
            for name in sorted(TARGET_VALUES):
                _set_channel_times(unreal, channel_objects[name], plan["after"][name])
            if not unreal.EditorAssetLibrary.save_loaded_asset(master, False):
                fail("save_loaded_asset returned False for the Master")
            after, _ = _snapshot_channels(unreal, section, rate)
            after_plain = _plain_snapshot(after)
            if after_plain != expected_after_all:
                fail("saved Master read-back does not match the planned all-channel snapshot")
            dirty_after = _census(unreal)
            if dirty_after["maps"] or dirty_after["content"]:
                fail("packages remain dirty after targeted Master save: %s" % json.dumps(dirty_after, sort_keys=True))
            record["status"] = "applied"
            record["applied_at"] = stamp
            _write_json(record_path, record)
            report.update({"ok": True, "backup": backup, "dirty_after": dirty_after, "all_channels_after": after})
            _write_json(report_path, report)
            unreal.log(
                "P01_SCORE_SHIFT_APPLIED|shift_s=%.6f|backup=%s|record=%s|next_test=InfinityStage.Editor.SavedMasterMatchesShow|census=%s"
                % (plan["shift_s"], backup, record_path, json.dumps(dirty_after, sort_keys=True))
            )
            return

        if not os.path.isfile(record_path):
            fail("REVERT record is absent")
        with open(record_path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        if record.get("master") != MASTER or record.get("passage_guid") != passage_guid:
            fail("REVERT record context does not match the current Master/P01")
        if abs(float(record.get("tick_rate", -1.0)) - rate) > 1.0e-6 \
                or record.get("section_range_s") != [section_start_s, section_end_s]:
            fail("REVERT record timing context does not match the current P01 section")
        current_plain = _plain_snapshot(before)
        if current_plain != record.get("after_all_channels"):
            fail("current P01 channels do not exactly match the recorded applied state")
        backup = _backup_master(unreal, "PreP01ScoreShiftRevert-", stamp)
        before_recorded = record.get("before_all_channels", {})
        for name in sorted(TARGET_VALUES):
            _set_channel_times(unreal, channel_objects[name], before_recorded[name])
        if not unreal.EditorAssetLibrary.save_loaded_asset(master, False):
            fail("save_loaded_asset returned False while reverting the Master")
        reverted, _ = _snapshot_channels(unreal, section, rate)
        reverted_plain = _plain_snapshot(reverted)
        if reverted_plain != before_recorded:
            fail("revert read-back does not match the recorded before state")
        dirty_after = _census(unreal)
        if dirty_after["maps"] or dirty_after["content"]:
            fail("packages remain dirty after revert save: %s" % json.dumps(dirty_after, sort_keys=True))
        archived = record_path + ".reverted-" + stamp
        os.rename(record_path, archived)
        report.update(
            {
                "ok": True,
                "backup": backup,
                "archived_record": archived,
                "dirty_after": dirty_after,
                "all_channels_after": reverted,
            }
        )
        _write_json(report_path, report)
        unreal.log(
            "P01_SCORE_SHIFT_REVERTED|backup=%s|record=%s|next_test=InfinityStage.Editor.SavedMasterMatchesShow|census=%s"
            % (backup, archived, json.dumps(dirty_after, sort_keys=True))
        )
    except ScoreShiftError:
        raise
    except Exception as error:  # noqa: BLE001 - Unreal must get one explicit marker
        fail(error)


if __name__ == "__main__":
    main()
