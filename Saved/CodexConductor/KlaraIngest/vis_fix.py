"""P26 per-scene visibility-track repair (offline-written; never run here).

The UE 5.8 visibility track binds ``AActor::bHidden`` as (``bHidden``,
``bHidden``), but its bool channel stores VISIBLE: True means shown. Older
PussStage tools instead bound ``bHiddenInGame`` and stored HIDDEN. DRY reports
only those inert tracks; APPLY changes the property and inverts every default
and key; REVERT restores the recorded property/path/defaults/keys exactly.

Input: ``vis_fix_args.json`` or a ``VIS_FIX_ARGS`` dict injected by a runner.
Required keys are mode, confirm, run, sequence, file and tag. Confirm is
``<MODE> VISFIX``. The four shipped per-scene argument files and
VIS_FIX_RUNBOOK.md are the conductor runbook.

Markers: VISFIX_DRY_OK / VISFIX_APPLY_OK / VISFIX_REVERT_OK / VISFIX_FAILED.
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
except ModuleNotFoundError:  # Offline harness.
    unreal = None


MARK = "VISFIX"
MODES = ("DRY", "APPLY", "REVERT")
OLD_PROPERTY = "bHiddenInGame"
NEW_PROPERTY = "bHidden"
HERE = os.path.dirname(os.path.abspath(__file__))


class PlanError(ValueError):
    pass


def _guid(value):
    if unreal is not None:
        try:
            return str(unreal.GuidLibrary.conv_guid_to_string(value))
        except Exception:  # noqa: BLE001 - fake harness and API fallback.
            pass
    return str(value)


def _frame(value):
    return int(value.value) if hasattr(value, "value") else int(value)


def _section_range(section):
    has_start = getattr(section, "has_start_frame", lambda: True)()
    has_end = getattr(section, "has_end_frame", lambda: True)()
    return [_frame(section.get_start_frame()) if has_start else None,
            _frame(section.get_end_frame()) if has_end else None]


def _track_state(track):
    sections = []
    for section_index, section in enumerate(track.get_sections()):
        channels = list(section.get_all_channels())
        if len(channels) != 1:
            raise PlanError("CHANNEL_COUNT|section=%d|got=%d" % (section_index, len(channels)))
        channel = channels[0]
        sections.append({
            "index": section_index,
            "range": _section_range(section),
            "default": bool(channel.get_default()) if channel.has_default() else None,
            "keys": [{"time": _frame(key.get_time().frame_number), "value": bool(key.get_value())}
                     for key in channel.get_keys()],
        })
    return {
        "property": str(track.get_property_name()),
        "path": str(track.get_property_path()),
        "display": str(track.get_display_name()),
        "sections": sections,
    }


def sequence_rows(sequence, unreal_api):
    """All visibility tracks with stable binding GUID + track-index identity."""
    rows = []
    for binding in sequence.get_bindings():
        binding_id = _guid(binding.get_id())
        binding_name = str(binding.get_display_name())
        for track_index, track in enumerate(binding.get_tracks()):
            if isinstance(track, unreal_api.MovieSceneVisibilityTrack):
                rows.append({
                    "id": "%s:%d" % (binding_id, track_index),
                    "binding_guid": binding_id,
                    "binding": binding_name,
                    "track_index": track_index,
                    "state": _track_state(track),
                    "_track": track,
                })
    return rows


def public_rows(rows):
    return [{k: v for k, v in row.items() if k != "_track"} for row in rows]


def flip_state(state):
    """OLD hidden semantics -> NEW visible semantics; pure for the harness."""
    out = json.loads(json.dumps(state))
    out["property"] = NEW_PROPERTY
    out["path"] = NEW_PROPERTY
    for section in out["sections"]:
        if section["default"] is not None:
            section["default"] = not section["default"]
        for key in section["keys"]:
            key["value"] = not key["value"]
    return out


def planned_rows(rows):
    """Only bHiddenInGame is inert. Existing bHidden and None stay untouched."""
    out = []
    for row in public_rows(rows):
        if row["state"]["property"] == OLD_PROPERTY:
            row["expected_after"] = flip_state(row["state"])
            out.append(row)
    return out


def state_diff(got, want):
    return [] if got == want else ["STATE_DIFF|got=%s|want=%s" % (got, want)]


def _set_state(track, wanted):
    """Restore recorded values rather than assuming a second inversion."""
    track.set_property_name_and_path(wanted["property"], wanted["path"])
    sections = list(track.get_sections())
    if len(sections) != len(wanted["sections"]):
        raise PlanError("SECTION_COUNT|got=%d|want=%d" % (len(sections), len(wanted["sections"])))
    for section, saved in zip(sections, wanted["sections"]):
        channels = list(section.get_all_channels())
        if len(channels) != 1:
            raise PlanError("CHANNEL_COUNT|got=%d" % len(channels))
        channel = channels[0]
        current_keys = list(channel.get_keys())
        if len(current_keys) != len(saved["keys"]):
            raise PlanError("KEY_COUNT|got=%d|want=%d" % (len(current_keys), len(saved["keys"])))
        if saved["default"] is not None:
            channel.set_default(bool(saved["default"]))
        elif channel.has_default():
            channel.remove_default()
        for key, key_saved in zip(current_keys, saved["keys"]):
            if _frame(key.get_time().frame_number) != int(key_saved["time"]):
                raise PlanError("KEY_TIME_DRIFT|got=%s|want=%s" %
                                (_frame(key.get_time().frame_number), key_saved["time"]))
            key.set_value(bool(key_saved["value"]))


def normalize_args(raw):
    allowed = {"mode", "confirm", "run", "sequence", "file", "tag"}
    extra = sorted(set(raw) - allowed)
    if extra:
        raise PlanError("UNKNOWN_ARGS|%s" % extra)
    mode = str(raw.get("mode", "DRY")).upper()
    if mode not in MODES:
        raise PlanError("MODE|%s" % mode)
    tag = str(raw.get("tag") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", tag):
        raise PlanError("TAG|%r" % tag)
    sequence = str(raw.get("sequence") or "")
    source = str(raw.get("file") or "")
    run = str(raw.get("run") or "%s-%s" % (tag, datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    if not sequence.startswith("/Game/") or not source.lower().endswith(".uasset"):
        raise PlanError("SEQUENCE_OR_FILE|%r|%r" % (sequence, source))
    if str(raw.get("confirm") or "") != "%s VISFIX" % mode:
        raise PlanError("CONFIRM|want=%r" % ("%s VISFIX" % mode))
    return {"mode": mode, "confirm": raw["confirm"], "run": run, "sequence": sequence,
            "file": source, "tag": tag}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _write_json(path, value, exclusive=False):
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    fd = os.open(path, flags)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(package.get_name() for package in lib.get_dirty_content_packages()),
            "maps": sorted(package.get_name() for package in lib.get_dirty_map_packages())}


def _require_clean(run):
    got = _census()
    if got != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AT_START|%s" % got)


def _record_path(tag):
    return os.path.join(HERE, "vis_fix_record_%s.json" % tag)


def _dry_path(tag):
    return os.path.join(HERE, "vis_fix_dry_%s.json" % tag)


def _backup(args, label):
    if not os.path.isfile(args["file"]):
        _stop(args["run"], "SOURCE_FILE_MISSING|%s" % args["file"])
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "%s-%s-%s" % (label, args["tag"], args["run"]))
    os.makedirs(folder, exist_ok=False)
    copy = os.path.join(folder, os.path.basename(args["file"]))
    shutil.copy2(args["file"], copy)
    source_sha = _sha(args["file"])
    if _sha(copy) != source_sha:
        _stop(args["run"], "BACKUP_HASH|%s" % copy)
    return {"folder": folder, "source": args["file"], "copy": copy, "sha256": source_sha}


def _live(args):
    sequence = unreal.load_asset(args["sequence"])
    if sequence is None:
        _stop(args["run"], "SEQUENCE_MISSING|%s" % args["sequence"])
    rows = sequence_rows(sequence, unreal)
    plan = planned_rows(rows)
    if not plan:
        _stop(args["run"], "NOTHING_TO_FIX|properties=%s" %
              sorted({row["state"]["property"] for row in public_rows(rows)}))
    return sequence, rows, plan


def _index(rows):
    return {row["id"]: row for row in rows}


def _assert_targets(rows, targets, state_key):
    by_id = _index(rows)
    problems = []
    for target in targets:
        current = by_id.get(target["id"])
        if current is None:
            problems.append("MISSING|%s" % target["id"])
            continue
        problems += ["%s|%s" % (target["id"], item)
                     for item in state_diff(current["state"], target[state_key])]
    return problems


def run_dry(args):
    _require_clean(args["run"])
    _sequence, rows, targets = _live(args)
    result = {"schema": 2, "tool": MARK, "mode": "DRY", "run": args["run"], "args": args,
              "targets": targets, "target_digest": _digest(targets),
              "untouched": {prop: sum(row["state"]["property"] == prop for row in rows)
                            for prop in sorted({row["state"]["property"] for row in rows})},
              "dirty": _census(), "note": "No package was changed or saved."}
    _write_json(_dry_path(args["tag"]), result)
    for row in targets:
        unreal.log("VISFIX_DRY_TRACK|run=%s|tag=%s|binding=%s|guid=%s|track=%d|ranges=%s" %
                   (args["run"], args["tag"], row["binding"], row["binding_guid"], row["track_index"],
                    [section["range"] for section in row["state"]["sections"]]))
    unreal.log("VISFIX_DRY_OK|run=%s|tag=%s|tracks=%d|untouched=%s|plan=%s" %
               (args["run"], args["tag"], len(targets), result["untouched"], _dry_path(args["tag"])))


def run_apply(args):
    _require_clean(args["run"])
    record_path = _record_path(args["tag"])
    if os.path.exists(record_path):
        _stop(args["run"], "RECORD_EXISTS|%s" % record_path)
    sequence, rows, targets = _live(args)
    dry = _load_json(_dry_path(args["tag"])) if os.path.isfile(_dry_path(args["tag"])) else None
    if not dry or dry.get("target_digest") != _digest(targets) or dry.get("args", {}).get("sequence") != args["sequence"]:
        _stop(args["run"], "MATCHING_DRY_REQUIRED|run DRY on the unchanged sequence")
    backup = _backup(args, "PreVisFix")
    record = {"schema": 2, "tool": MARK, "mode": "APPLY", "run": args["run"], "tag": args["tag"],
              "sequence": args["sequence"], "file": args["file"], "backup": backup, "applied": False,
              "written": datetime.datetime.now().isoformat(timespec="seconds"), "targets": targets}
    _write_json(record_path, record, exclusive=True)  # Record and backup both exist before the first UObject mutation.
    by_id = _index(rows)
    sequence.modify()
    for target in targets:
        _set_state(by_id[target["id"]]["_track"], target["expected_after"])
    current = sequence_rows(sequence, unreal)
    problems = _assert_targets(current, targets, "expected_after")
    census = _census()
    if census != {"content": [args["sequence"]], "maps": []}:
        problems.append("DIRTY_CENSUS|%s" % census)
    if problems:
        _stop(args["run"], "PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart|backup=%s" %
              (problems, backup["folder"]))
    if not unreal.EditorAssetLibrary.save_asset(args["sequence"], only_if_is_dirty=True):
        _stop(args["run"], "SAVE_FAILED|%s|backup=%s" % (args["sequence"], backup["folder"]))
    if _census() != {"content": [], "maps": []}:
        _stop(args["run"], "DIRTY_AFTER_SAVE|%s" % _census())
    saved = sequence_rows(unreal.load_asset(args["sequence"]), unreal)
    problems = _assert_targets(saved, targets, "expected_after")
    if problems:
        _stop(args["run"], "SAVED_READBACK|%s|recover=%s" % (problems, backup["folder"]))
    record.update({"applied": True, "saved_readback": public_rows(saved), "saved_sha256": _sha(args["file"])})
    _write_json(record_path, record)
    unreal.log("VISFIX_APPLY_OK|run=%s|tag=%s|tracks=%d|saved_only=%s|maps_saved=0|dirty=0|backup=%s" %
               (args["run"], args["tag"], len(targets), args["sequence"], backup["folder"]))


def run_revert(args):
    _require_clean(args["run"])
    record_path = _record_path(args["tag"])
    if not os.path.isfile(record_path):
        _stop(args["run"], "NO_RECORD|%s" % record_path)
    record = _load_json(record_path)
    if not record.get("applied") or record.get("sequence") != args["sequence"] or record.get("file") != args["file"]:
        _stop(args["run"], "RECORD_NOT_APPLIED_OR_ARGS_MISMATCH")
    sequence = unreal.load_asset(args["sequence"])
    rows = sequence_rows(sequence, unreal)
    targets = record["targets"]
    drift = _assert_targets(rows, targets, "expected_after")
    if drift:
        _stop(args["run"], "STATE_DRIFTED_SINCE_APPLY|%s|nothing changed" % drift)
    backup = _backup(args, "PreVisFixRevert")
    revert_path = os.path.join(HERE, "vis_fix_revert_record_%s_%s.json" % (args["tag"], args["run"]))
    _write_json(revert_path, {"schema": 2, "tool": MARK, "mode": "REVERT", "run": args["run"],
                              "apply_record": record_path, "backup": backup, "applied": False}, exclusive=True)
    by_id = _index(rows)
    sequence.modify()
    for target in targets:
        _set_state(by_id[target["id"]]["_track"], target["state"])
    restored = sequence_rows(sequence, unreal)
    problems = _assert_targets(restored, targets, "state")
    census = _census()
    if census != {"content": [args["sequence"]], "maps": []}:
        problems.append("DIRTY_CENSUS|%s" % census)
    if problems:
        _stop(args["run"], "REVERT_PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart|backup=%s" %
              (problems, backup["folder"]))
    if not unreal.EditorAssetLibrary.save_asset(args["sequence"], only_if_is_dirty=True):
        _stop(args["run"], "REVERT_SAVE_FAILED|%s" % args["sequence"])
    if _census() != {"content": [], "maps": []}:
        _stop(args["run"], "REVERT_DIRTY_AFTER_SAVE|%s" % _census())
    saved = sequence_rows(unreal.load_asset(args["sequence"]), unreal)
    problems = _assert_targets(saved, targets, "state")
    if problems:
        _stop(args["run"], "REVERT_SAVED_READBACK|%s|recover=%s" % (problems, backup["folder"]))
    archived = record_path + ".reverted-" + args["run"]
    os.rename(record_path, archived)
    _write_json(revert_path, {"schema": 2, "tool": MARK, "mode": "REVERT", "run": args["run"], "applied": True,
                              "backup": backup, "restored": len(targets), "saved_readback": public_rows(saved),
                              "archived_apply_record": archived})
    unreal.log("VISFIX_REVERT_OK|run=%s|tag=%s|tracks=%d|saved_only=%s|maps_saved=0|dirty=0|backup=%s" %
               (args["run"], args["tag"], len(targets), args["sequence"], backup["folder"]))


def _stop(run, text):
    unreal.log_error("VISFIX_FAILED|run=%s|%s" % (run, text))
    raise RuntimeError(text)


def main(raw=None):
    raw = dict(raw if raw is not None else globals().get("VIS_FIX_ARGS") or
               _load_json(os.path.join(HERE, "vis_fix_args.json")))
    run = str(raw.get("run") or "UNKNOWN")
    try:
        args = normalize_args(raw)
        run = args["run"]
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            _stop(run, "PIE_RUNNING")
        current = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
        if current is not None:
            _stop(run, "SEQUENCER_OPEN|%s" % current.get_path_name())
        {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[args["mode"]](args)
    except Exception as exc:  # noqa: BLE001
        if not isinstance(exc, RuntimeError):
            unreal.log_error("VISFIX_FAILED|run=%s|%r" % (run, exc))
        raise


if unreal is not None:
    main()
