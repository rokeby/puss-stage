"""Job 191: live DRY/APPLY/REVERT for nested subsection range defects.

The tool mirrors InfinityStage.Editor.NestedSequencesFitTheirParents from the
saved Master. It changes only start/end range metadata on currently offending
active subsections. It never moves keys, changes offsets, changes playback
ranges, rebuilds Master, or saves a KlaraHookin package.

Markers: JOB191_NESTED_DRY_OK, JOB191_NESTED_APPLY_OK,
JOB191_NESTED_REVERT_OK, JOB191_NESTED_FAILED.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib
import json
import os
import pathlib
import shutil
import sys

import unreal


HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import nested_repair_core as core
importlib.reload(core)

ARGS = HERE / "nested_sequence_args.json"
RECORDS = HERE / "records"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"


def fail(run, message):
    unreal.log_error("JOB191_NESTED_FAILED|run=%s|%s" % (run, message))
    raise RuntimeError(message)


def package_name(value):
    return str(value.get_path_name()).split(".", 1)[0]


def dirty_census():
    return {
        "content": sorted(str(p.get_name()).split(".", 1)[0] for p in
                          unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(str(p.get_name()).split(".", 1)[0] for p in
                       unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def rate_value(rate):
    return float(rate.numerator) / float(rate.denominator)


def frame_value(value):
    return int(value.value if hasattr(value, "value") else value)


def fixed_rate(section):
    params = section.get_editor_property("parameters")
    warp = params.get_editor_property("time_scale")
    return float(unreal.MovieSceneTimeWarpExtensions.conv_time_warp_variant_to_play_rate(warp))


def offset_ticks(section, name):
    params = section.get_editor_property("parameters")
    return frame_value(params.get_editor_property(name))


def section_rows(master):
    rows = []
    visited = set()

    def walk(parent):
        parent_path = package_name(parent)
        if parent_path in visited:
            return
        visited.add(parent_path)
        parent_display = rate_value(parent.get_display_rate())
        for track_index, track in enumerate(parent.get_tracks()):
            for section_index, section in enumerate(track.get_sections()):
                get_sequence = getattr(section, "get_sequence", None)
                child = get_sequence() if callable(get_sequence) else None
                if child is None or not section.is_active() or not section.has_start_frame() or not section.has_end_frame():
                    continue
                child_path = package_name(child)
                rows.append({
                    "parent_path": parent_path,
                    "parent_name": str(parent.get_name()),
                    "parent_playback": [int(parent.get_playback_start()), int(parent.get_playback_end())],
                    "parent_display_fps": parent_display,
                    "section_path": str(section.get_path_name()),
                    "track_path": str(track.get_path_name()),
                    "track_index": track_index,
                    "section_index": section_index,
                    "section_range": [int(section.get_start_frame()), int(section.get_end_frame())],
                    "child_path": child_path,
                    "child_name": str(child.get_name()),
                    "child_playback": [int(child.get_playback_start()), int(child.get_playback_end())],
                    "child_display_fps": rate_value(child.get_display_rate()),
                    "child_tick_fps": rate_value(child.get_tick_resolution()),
                    "time_scale": fixed_rate(section),
                    "start_offset_ticks": offset_ticks(section, "start_frame_offset"),
                    "end_offset_ticks": offset_ticks(section, "end_frame_offset"),
                })
                walk(child)
    walk(master)
    return rows


def live_plan():
    master = unreal.load_asset(MASTER)
    if master is None:
        raise RuntimeError("saved Master did not resolve")
    return core.build_plan(section_rows(master))


def section_map(master):
    result = {}
    visited = set()

    def walk(parent):
        path = package_name(parent)
        if path in visited:
            return
        visited.add(path)
        for track in parent.get_tracks():
            for section in track.get_sections():
                getter = getattr(section, "get_sequence", None)
                child = getter() if callable(getter) else None
                if child is not None:
                    result[str(section.get_path_name())] = section
                    walk(child)
    walk(master)
    return result


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_file(package):
    root = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()))
    return root / (package[len("/Game/"):].replace("/", os.sep) + ".uasset")


def backup_packages(run, packages, prefix):
    project = pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    directory = project / "Backups" / ("%s-%s-%s" % (prefix, run, stamp))
    directory.mkdir(parents=True, exist_ok=False)
    files = []
    for package in sorted(set(packages)):
        if "/KlaraHookin/" in package:
            raise RuntimeError("refusing to back up or save Klara package %s" % package)
        source = package_file(package)
        target = directory / (package.strip("/").replace("/", "__") + ".uasset")
        shutil.copy2(source, target)
        if source.stat().st_size != target.stat().st_size or sha256(source) != sha256(target):
            raise RuntimeError("backup verification failed for %s" % package)
        files.append({"package": package, "source": source.as_posix(), "backup": target.as_posix(),
                      "bytes": target.stat().st_size, "sha256": sha256(target)})
    return {"directory": directory.as_posix(), "files": files}


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def replace(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def assert_environment(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        fail(run, "PIE/SIE is active")
    world = editor.get_editor_world()
    if world is None or package_name(world) != EXPECTED_WORLD:
        fail(run, "wrong editor world %r" % (package_name(world) if world else None))
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        fail(run, "close Sequencer before authoring")
    census = dirty_census()
    if census["content"] or census["maps"]:
        fail(run, "requires zero dirty packages: %r" % census)
    return census


def save_readback(run, packages, expected_ranges):
    for package in sorted(set(packages)):
        if "/KlaraHookin/" in package:
            fail(run, "Klara package entered save set: %s" % package)
        asset = unreal.load_asset(package)
        if asset is None or not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
            fail(run, "targeted save failed: %s" % package)
    census = dirty_census()
    if census["content"] or census["maps"]:
        fail(run, "dirty packages remain after targeted save: %r" % census)
    master = unreal.load_asset(MASTER)
    mapped = section_map(master)
    for path, wanted in expected_ranges.items():
        section = mapped.get(path)
        got = [int(section.get_start_frame()), int(section.get_end_frame())] if section else None
        if got != list(wanted):
            fail(run, "section read-back mismatch %s: %r != %r" % (path, got, wanted))
    return live_plan(), census


def main():
    args = json.loads(ARGS.read_text(encoding="utf-8"))
    mode, run = core.validate_args(args)
    before_dirty = assert_environment(run)
    plan = live_plan()
    RECORDS.mkdir(parents=True, exist_ok=True)

    if mode == "DRY":
        path = RECORDS / ("job191_nested_%s_dry.json" % run)
        report = {"schema": 1, "mode": mode, "run": run, "writes": 0,
                  "dirty_before": before_dirty, "plan": plan,
                  "simulated_test_passes": core.simulated_test_passes(plan)}
        write_new(path, report)
        unreal.log("JOB191_NESTED_DRY_OK|run=%s|checked=%d|offenders=%d|repairs=%d|klara_skips=%d|blocked=%d|plan_sha256=%s|record=%s" %
                   (run, plan["sections_checked"], plan["offender_count"], plan["repair_count"],
                    plan["skipped_klara_count"], plan["blocked_count"], plan["plan_sha256"], path.as_posix()))
        return

    master = unreal.load_asset(MASTER)
    mapped = section_map(master)
    if mode == "APPLY":
        if args["plan_sha256"] != plan["plan_sha256"]:
            fail(run, "DRY plan digest is stale: live=%s args=%s" % (plan["plan_sha256"], args["plan_sha256"]))
        if plan["offender_count"] < 1:
            fail(run, "no current offender; nothing to apply")
        if plan["skipped_klara_count"] or plan["blocked_count"] or plan["repair_count"] != plan["offender_count"]:
            fail(run, "not every offender has a screen-invariant non-Klara range repair")
        packages = sorted({row["parent_path"] for row in plan["repairs"]})
        backup = backup_packages(run, packages, "PreJob191NestedRepair")
        path = RECORDS / ("job191_nested_%s_apply.json" % run)
        record = {"schema": 1, "status": "PREPARED_BEFORE_MUTATION", "mode": mode, "run": run,
                  "plan": plan, "dirty_before": before_dirty, "backup": backup,
                  "save_packages": packages}
        write_new(path, record)
        expected = {}
        for row in plan["repairs"]:
            section = mapped.get(row["section_path"])
            if section is None:
                fail(run, "section vanished after planning: %s" % row["section_path"])
            section.modify()
            section.set_range(int(row["new_range"][0]), int(row["new_range"][1]))
            expected[row["section_path"]] = row["new_range"]
        after_plan, dirty_after = save_readback(run, packages, expected)
        if after_plan["offender_count"] != 0:
            fail(run, "nested invariant is still red after read-back: %r" % after_plan["offenders"])
        record.update(status="APPLIED_AND_READ_BACK", after_plan=after_plan, dirty_after=dirty_after)
        replace(path, record)
        unreal.log("JOB191_NESTED_APPLY_OK|run=%s|sections=%d|saved=%s|record=%s|backup=%s" %
                   (run, len(expected), ",".join(packages), path.as_posix(), backup["directory"]))
        return

    source_path = pathlib.Path(str(args["record"]))
    if not source_path.is_absolute():
        source_path = HERE / source_path
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source.get("status") != "APPLIED_AND_READ_BACK" or not source.get("plan", {}).get("repairs"):
        fail(run, "record is not a complete Job 191 APPLY record")
    repairs = source["plan"]["repairs"]
    packages = sorted({row["parent_path"] for row in repairs})
    backup = backup_packages(run, packages, "PreJob191NestedRevert")
    path = RECORDS / ("job191_nested_%s_revert.json" % run)
    record = {"schema": 1, "status": "PREPARED_BEFORE_MUTATION", "mode": mode, "run": run,
              "source_record": source_path.as_posix(), "dirty_before": before_dirty,
              "backup": backup, "save_packages": packages}
    write_new(path, record)
    expected = {}
    for row in repairs:
        section = mapped.get(row["section_path"])
        if section is None:
            fail(run, "recorded section no longer resolves: %s" % row["section_path"])
        current = [int(section.get_start_frame()), int(section.get_end_frame())]
        if current != list(row["new_range"]):
            fail(run, "refusing to overwrite drifted section %s: %r" % (row["section_path"], current))
        section.modify()
        section.set_range(int(row["section_range"][0]), int(row["section_range"][1]))
        expected[row["section_path"]] = row["section_range"]
    after_plan, dirty_after = save_readback(run, packages, expected)
    record.update(status="REVERTED_AND_READ_BACK", after_plan=after_plan, dirty_after=dirty_after)
    replace(path, record)
    unreal.log("JOB191_NESTED_REVERT_OK|run=%s|sections=%d|saved=%s|record=%s|backup=%s" %
               (run, len(expected), ",".join(packages), path.as_posix(), backup["directory"]))


try:
    main()
except Exception as exc:
    if "JOB191_NESTED_FAILED|" not in str(exc):
        unreal.log_error("JOB191_NESTED_FAILED|%r" % (exc,))
    raise
