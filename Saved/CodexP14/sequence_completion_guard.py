"""P14 guarded completion-mode census/fix for six Dev Scenes and the managed Master.

Offline DRY (the mode used by this Codex run):
  python Saved/CodexP14/sequence_completion_guard.py \
    --snapshot-dir Saved/CodexP14Scan --out Docs/Conductor/P14_SEQUENCE_COMPLETION_CENSUS_2026-10-08.json

Live Unreal modes read Saved/CodexP14/sequence_completion_guard_args.json. APPLY and
REVERT require exact confirm strings, a clean editor, a record, a pre-change backup,
an exact dirty-package census, named-package saves, read-back, and a run-id marker.
No targets are supplied by default: candidate visibility choices remain Gary's.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys

try:
    import unreal  # type: ignore
except ImportError:
    unreal = None


TOOL = "p14_sequence_completion_guard"
MARK = "P14KEEP"
SCENES = {
    "S1": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01",
    "S2": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02",
    "S3": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03",
    "S4": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04",
    "S5": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_05",
    "S6": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_06",
    "MASTER": "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master",
}
TRACK_CLASSES = {"MovieSceneSubTrack", "MovieSceneVisibilityTrack", "MovieSceneSpawnTrack"}
RUN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,80}$")


class GuardError(RuntimeError):
    pass


def _enum_name(value):
    return str(getattr(value, "name", value)).split(".")[-1].upper()


def completion_name(value):
    text = _enum_name(value)
    if "KEEP_STATE" in text or "KEEPSTATE" in text:
        return "KEEP_STATE"
    if "RESTORE_STATE" in text or "RESTORESTATE" in text:
        return "RESTORE_STATE"
    if "PROJECT_DEFAULT" in text or "PROJECTDEFAULT" in text or text in ("", "NONE", "UNSPECIFIED"):
        return "PROJECT_DEFAULT"
    return text


def section_candidate(track_class, section_range, completion, playback_end):
    """Pure S3-class screen: relevant class, bounded end before playback end, non-KEEP completion."""
    if str(track_class) not in TRACK_CLASSES:
        return False
    if not section_range or len(section_range) != 2 or section_range[1] is None:
        return False
    if int(section_range[1]) >= int(playback_end):
        return False
    return completion_name(completion) != "KEEP_STATE"


def snapshot_asset(document, label):
    playback = document.get("movie", {}).get("PlaybackRange")
    if not playback or len(playback) != 2:
        raise GuardError("SNAPSHOT_PLAYBACK_RANGE|%s" % label)
    end = int(playback[1])
    rows = []
    for track in document.get("tracks", []):
        track_class = str(track.get("cls") or "")
        for section_index, section in enumerate(track.get("sections", [])):
            props = section.get("props") or {}
            eval_options = props.get("EvalOptions") or {}
            raw_completion = eval_options.get("CompletionMode", "PROJECT_DEFAULT")
            section_range = section.get("range")
            if not section_candidate(track_class, section_range, raw_completion, end):
                continue
            rows.append({
                "id": str(section.get("export") or "%s|%s|%d" % (label, track_class, section_index)),
                "owner": str(track.get("owner") or "<master>"),
                "track_class": track_class,
                "range": list(section_range),
                "completion": completion_name(raw_completion),
                "sub_sequence": props.get("SubSequence"),
            })
    return {
        "label": label,
        "file": document.get("file"),
        "sha256": document.get("sha256"),
        "playback": list(playback),
        "track_count": len(document.get("tracks", [])),
        "candidates": rows,
    }


def validate_args(args):
    errors = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        errors.append("MODE")
    run = str(args.get("run") or "")
    if not RUN_RE.match(run):
        errors.append("RUN")
    if mode in ("APPLY", "REVERT") and args.get("confirm") != "%s %s" % (mode, MARK):
        errors.append("CONFIRM")
    if mode == "APPLY" and not str(args.get("decided_by") or "").strip():
        errors.append("DECIDED_BY")
    targets = args.get("targets")
    if mode == "APPLY" and (not isinstance(targets, list) or not targets):
        errors.append("TARGETS")
    if targets is not None and (not isinstance(targets, list) or len(targets) != len(set(map(str, targets)))):
        errors.append("TARGETS_DUPLICATE_OR_TYPE")
    return errors


def choose_targets(rows, target_ids):
    by_id = {str(row["id"]): row for row in rows}
    wanted = list(map(str, target_ids or []))
    missing = sorted(set(wanted) - set(by_id))
    return [by_id[item] for item in wanted if item in by_id], missing


def readback_diff(expected, actual):
    by_id = {str(row["id"]): row for row in actual}
    diff = []
    for want in expected:
        got = by_id.get(str(want["id"]))
        if not got:
            diff.append("MISSING|%s" % want["id"])
        elif completion_name(got.get("completion")) != completion_name(want.get("completion")):
            diff.append("COMPLETION|%s|%s!=%s" % (
                want["id"], got.get("completion"), want.get("completion")))
        elif list(got.get("range") or []) != list(want.get("range") or []):
            diff.append("RANGE|%s|%s!=%s" % (want["id"], got.get("range"), want.get("range")))
    return diff


def offline_dry(snapshot_dir):
    assets = []
    names = ["LS_DevScene_%02d_sem.json" % n for n in range(1, 7)] + ["LS_InfinityStage_V1Master_sem.json"]
    for name in names:
        path = os.path.join(snapshot_dir, name)
        if not os.path.isfile(path):
            raise GuardError("SNAPSHOT_MISSING|%s" % path)
        with open(path, encoding="utf-8") as handle:
            assets.append(snapshot_asset(json.load(handle), name[:-9]))
    return {
        "schema": 1,
        "tool": TOOL,
        "mode": "DRY_OFFLINE",
        "written_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "assets": assets,
        "candidate_count": sum(len(asset["candidates"]) for asset in assets),
        "interpretation": (
            "candidate means Sub/Visibility/Spawn section ends before its sequence and is not explicit KEEP_STATE; "
            "it is a review list, not permission to change creative visibility"
        ),
    }


def _saved_dir():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexP14")


def _project_dir():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _asset_file(asset_path):
    return os.path.join(_project_dir(), "Content", *asset_path[len("/Game/"):].split("/")) + ".uasset"


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _dirty_census():
    util = unreal.EditorLoadingAndSavingUtils
    content = sorted(package.get_path_name().split(".")[0] for package in util.get_dirty_content_packages())
    maps = sorted(package.get_path_name().split(".")[0] for package in util.get_dirty_map_packages())
    return {"content": content, "maps": maps}


def _guid_text(binding):
    try:
        return unreal.GuidLibrary.conv_guid_to_string(binding.get_id())
    except Exception:
        return str(binding.get_id())


def _section_range(section):
    try:
        start = int(section.get_start_frame()) if section.has_start_frame() else None
        end = int(section.get_end_frame()) if section.has_end_frame() else None
        return [start, end]
    except Exception:
        try:
            return [int(section.get_start_frame()), int(section.get_end_frame())]
        except Exception:
            return [None, None]


def _live_rows(asset_path):
    sequence = unreal.load_asset(asset_path)
    if sequence is None:
        raise GuardError("LOAD|%s" % asset_path)
    playback = [int(sequence.get_playback_start()), int(sequence.get_playback_end())]
    rows = []

    def add_tracks(owner, binding_key, tracks):
        for track_index, track in enumerate(tracks):
            track_class = track.get_class().get_name()
            if track_class not in TRACK_CLASSES:
                continue
            for section_index, section in enumerate(track.get_sections()):
                section_range = _section_range(section)
                completion = completion_name(section.get_completion_mode())
                sid = "%s|%s|%d|%d|%s" % (
                    asset_path, binding_key, track_index, section_index, track_class)
                rows.append({
                    "id": sid,
                    "asset": asset_path,
                    "owner": owner,
                    "track_class": track_class,
                    "range": section_range,
                    "completion": completion,
                    "candidate": section_candidate(track_class, section_range, completion, playback[1]),
                    "_section": section,
                })

    add_tracks("<master>", "master", sequence.get_tracks())
    for binding in sequence.get_bindings():
        add_tracks(str(binding.get_display_name()), _guid_text(binding), binding.get_tracks())
    return sequence, playback, rows


def _live_inventory():
    assets, all_rows = [], []
    for label, path in SCENES.items():
        sequence, playback, rows = _live_rows(path)
        candidates = [dict(row, _section=None) for row in rows if row["candidate"]]
        assets.append({"label": label, "asset": path, "playback": playback, "candidates": candidates})
        all_rows.extend(rows)
    return assets, all_rows


def _completion_enum(name):
    table = {
        "KEEP_STATE": unreal.MovieSceneCompletionMode.KEEP_STATE,
        "RESTORE_STATE": unreal.MovieSceneCompletionMode.RESTORE_STATE,
        "PROJECT_DEFAULT": unreal.MovieSceneCompletionMode.PROJECT_DEFAULT,
    }
    if completion_name(name) not in table:
        raise GuardError("COMPLETION_ENUM|%s" % name)
    return table[completion_name(name)]


def _write_json(path, data, exclusive=False):
    mode = "x" if exclusive else "w"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def _backup(asset_paths, directory):
    os.makedirs(directory, exist_ok=False)
    copied = []
    for asset in asset_paths:
        source = _asset_file(asset)
        destination = os.path.join(directory, os.path.basename(source))
        shutil.copy2(source, destination)
        copied.append({"asset": asset, "source": source, "backup": destination, "sha256": _sha256(source)})
    return copied


def live_main(args):
    errors = validate_args(args)
    if errors:
        raise GuardError("ARGS|%s" % ",".join(errors))
    mode, run = args["mode"].upper(), args["run"]
    before_dirty = _dirty_census()
    assets, rows = _live_inventory()
    report = {"schema": 1, "tool": TOOL, "mode": mode, "run": run, "dirty_before": before_dirty, "assets": assets}
    out_path = os.path.join(_saved_dir(), "sequence_completion_guard_%s_%s.json" % (mode.lower(), run))
    if mode == "DRY":
        report["dirty_after"] = _dirty_census()
        if report["dirty_after"] != before_dirty:
            raise GuardError("DRY_DIRTIED_EDITOR|%s" % report["dirty_after"])
        _write_json(out_path, report)
        unreal.log("%s_DRY_OK|run=%s|candidates=%d|dirty=%s" % (
            MARK, run, sum(len(a["candidates"]) for a in assets), before_dirty))
        return
    if before_dirty != {"content": [], "maps": []}:
        raise GuardError("DIRTY_BEFORE|%s" % before_dirty)

    record_path = os.path.join(_saved_dir(), "sequence_completion_guard_record.json")
    if mode == "APPLY":
        chosen, missing = choose_targets(rows, args.get("targets"))
        if missing:
            raise GuardError("TARGETS_NOT_FOUND|%s" % missing)
        non_candidates = [row["id"] for row in chosen if not row["candidate"]]
        if non_candidates:
            raise GuardError("TARGETS_NOT_CANDIDATES|%s" % non_candidates)
        affected = sorted(set(row["asset"] for row in chosen))
        record = {
            "schema": 1, "tool": TOOL, "apply_run": run, "decided_by": args["decided_by"],
            "targets": [{k: v for k, v in row.items() if k not in ("_section", "candidate")} for row in chosen],
        }
        _write_json(record_path, record, exclusive=True)
        backup_dir = os.path.join(_project_dir(), "Backups", "PreP14KeepState-%s" % run)
    else:
        if not os.path.isfile(record_path):
            raise GuardError("RECORD_MISSING")
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        chosen, missing = choose_targets(rows, [row["id"] for row in record["targets"]])
        if missing:
            raise GuardError("RECORDED_TARGETS_NOT_FOUND|%s" % missing)
        affected = sorted(set(row["asset"] for row in chosen))
        backup_dir = os.path.join(_project_dir(), "Backups", "PreP14KeepStateRevert-%s" % run)

    report["backup"] = _backup(affected, backup_dir)
    report["affected"] = affected
    expected = []
    old_by_id = {row["id"]: row for row in record["targets"]}
    for row in chosen:
        target_completion = "KEEP_STATE" if mode == "APPLY" else old_by_id[row["id"]]["completion"]
        row["_section"].modify()
        row["_section"].set_completion_mode(_completion_enum(target_completion))
        expected.append(dict(row, completion=target_completion, _section=None))

    dirty_after_write = _dirty_census()
    if dirty_after_write != {"content": affected, "maps": []}:
        raise GuardError("DIRTY_AFTER_WRITE|got=%s|want=%s|NOTHING_SAVED" % (dirty_after_write, affected))
    _, read_rows = _live_inventory()
    diff = readback_diff(expected, read_rows)
    if diff:
        raise GuardError("READBACK_BEFORE_SAVE|%s|NOTHING_SAVED" % diff)
    for asset in affected:
        if not unreal.EditorAssetLibrary.save_asset(asset, only_if_is_dirty=False):
            raise GuardError("SAVE|%s" % asset)
    dirty_after_save = _dirty_census()
    if dirty_after_save != {"content": [], "maps": []}:
        raise GuardError("DIRTY_AFTER_SAVE|%s" % dirty_after_save)
    _, saved_rows = _live_inventory()
    saved_diff = readback_diff(expected, saved_rows)
    if saved_diff:
        raise GuardError("READBACK_AFTER_SAVE|%s" % saved_diff)
    report.update({"dirty_after_write": dirty_after_write, "dirty_after_save": dirty_after_save,
                   "readback": [{k: v for k, v in row.items() if k != "_section"} for row in expected]})
    _write_json(out_path, report)
    unreal.log("%s_%s_OK|run=%s|sections=%d|packages=%d" % (MARK, mode, run, len(chosen), len(affected)))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir")
    parser.add_argument("--out")
    ns = parser.parse_args(argv if unreal is None else [])
    if unreal is None:
        if not ns.snapshot_dir:
            raise GuardError("OFFLINE_REQUIRES_SNAPSHOT_DIR")
        result = offline_dry(ns.snapshot_dir)
        text = json.dumps(result, indent=2, sort_keys=True)
        if ns.out:
            os.makedirs(os.path.dirname(os.path.abspath(ns.out)), exist_ok=True)
            with open(ns.out, "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
        print("%s_DRY_OK|assets=%d|candidates=%d" % (MARK, len(result["assets"]), result["candidate_count"]))
        return result
    args_path = os.path.join(_saved_dir(), "sequence_completion_guard_args.json")
    with open(args_path, encoding="utf-8") as handle:
        args = json.load(handle)
    return live_main(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if unreal is not None:
            unreal.log_error("%s_FAILED|%r" % (MARK, exc))
        else:
            print("%s_FAILED|%r" % (MARK, exc), file=sys.stderr)
            raise

