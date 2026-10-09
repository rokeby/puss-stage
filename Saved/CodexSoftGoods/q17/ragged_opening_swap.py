"""Q17: swap ONLY the Opening's baked curtain cache to the ragged held cache.

Run through ExecuteProjectPythonFile after editing ragged_opening_swap_args.json.
Modes are DRY, APPLY and REVERT.  APPLY/REVERT are confirm-gated, back up the
single Level Sequence package before mutation, require an exact dirty-package
census, save only that sequence, and read every changed field back.

This deliberately does not touch the five Interaction sequences.  Their
geometry-cache rows are fingerprinted before and after APPLY and against the
APPLY record during REVERT.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


MARK = "Q17_RAGGED_OPENING"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OPENING_SEQUENCE = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked"
OPENING_BINDING = "Opening Drape (baked)"
SOURCE_CACHE = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
TARGET_CACHE = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_RaggedProscenium_P02Held"
EXPECTED_MI = "/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop"
TRANSITION_SEQUENCES = tuple(
    "/Game/InfinityStage/Interactions/" + name
    for name in (
        "LS_Interaction_01_WashingTheBoy",
        "LS_Interaction_02_Turnips",
        "LS_Interaction_03_ForgetsHisName",
        "LS_Interaction_04_GetsAName",
        "LS_Interaction_05_BecomesKing",
    )
)
GC_TRACK_CLASS = "MovieSceneGeometryCacheTrack"
ARGS_NAME = "ragged_opening_swap_args.json"
RECORD_NAME = "opening_ragged_swap_record.json"
CONFIRMS = {
    "DRY": "DRY_RAGGED_OPENING_ONLY",
    "APPLY": "APPLY_RAGGED_OPENING_ONLY",
    "REVERT": "REVERT_RAGGED_OPENING_ONLY",
}


class PlanError(ValueError):
    pass


class ToolStopped(RuntimeError):
    pass


def validate_args(args):
    mode = str(args.get("mode") or "").upper()
    if mode not in CONFIRMS:
        raise PlanError("MODE_INVALID: %r" % mode)
    if args.get("confirm") != CONFIRMS[mode]:
        raise PlanError("CONFIRM_MISMATCH: %r, want %r" % (args.get("confirm"), CONFIRMS[mode]))
    if mode in ("APPLY", "REVERT") and not str(args.get("decided_by") or "").strip():
        raise PlanError("DECIDED_BY_REQUIRED")
    return mode


def replace_opening_assets(snapshot, old_path, new_path):
    """Pure model used by the live read-back and the offline +/- harness."""
    out = copy.deepcopy(snapshot)
    fields = [out.get("template_asset")] + [s.get("asset") for s in out.get("sections", [])]
    if len(fields) != 4 or any(p != old_path for p in fields):
        raise PlanError("OPENING_CACHE_FIELDS: got %r, want four %s fields" % (fields, old_path))
    out["template_asset"] = new_path
    for section in out["sections"]:
        section["asset"] = new_path
    return out


def transition_guard(rows, forbidden=TARGET_CACHE):
    by_sequence = {p: 0 for p in TRANSITION_SEQUENCES}
    for row in rows:
        if row.get("asset") == forbidden:
            raise PlanError("TRANSITION_ALREADY_USES_TARGET: %s" % row.get("sequence"))
        if row.get("sequence") in by_sequence and row.get("asset") == SOURCE_CACHE:
            by_sequence[row["sequence"]] += 1
    missing = [p for p, count in by_sequence.items() if count == 0]
    if missing:
        raise PlanError("TRANSITION_SOURCE_REFERENCE_MISSING: %r" % missing)
    return by_sequence


def _here():
    if unreal is not None:
        return os.path.join(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
            "CodexSoftGoods", "q17",
        )
    return os.path.dirname(os.path.abspath(__file__))


def _pk(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        value = value.get_path_name()
    return str(value).split(".")[0]


def _ival(value):
    return int(value.value) if hasattr(value, "value") else int(value)


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise ToolStopped(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(_pk(p.get_path_name()) for p in lib.get_dirty_content_packages()),
        "maps": sorted(_pk(p.get_path_name()) for p in lib.get_dirty_map_packages()),
    }


def _content_file(asset_path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *asset_path[len("/Game/"):].split("/")) + ".uasset"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _write_exclusive(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1)
        handle.flush()
        os.fsync(handle.fileno())


def _write(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1)
        handle.flush()
        os.fsync(handle.fileno())


def _backup(run, prefix):
    src = _content_file(OPENING_SEQUENCE)
    if not os.path.isfile(src):
        _stop(run, "SEQUENCE_FILE_MISSING|" + src)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "%s-%s" % (prefix, run))
    os.makedirs(folder, exist_ok=False)
    dst = os.path.join(folder, os.path.basename(src))
    shutil.copy2(src, dst)
    if _sha256(src) != _sha256(dst):
        _stop(run, "BACKUP_HASH_MISMATCH|" + folder)
    return {"folder": folder, "source": src, "backup": dst, "sha256": _sha256(dst)}


def _section_row(section):
    params = section.get_editor_property("params")
    asset = params.get_editor_property("geometry_cache_asset")
    return {
        "range": [_ival(section.get_start_frame()), _ival(section.get_end_frame())],
        "asset": _pk(asset),
        "start_frame_offset": _ival(params.get_editor_property("start_frame_offset")),
        "end_frame_offset": _ival(params.get_editor_property("end_frame_offset")),
        "play_rate": float(params.get_editor_property("play_rate")),
    }


def _opening_snapshot(seq, run):
    bindings = [b for b in seq.get_bindings() if str(b.get_display_name()) == OPENING_BINDING]
    if len(bindings) != 1:
        _stop(run, "OPENING_BINDING_COUNT|%d" % len(bindings))
    binding = bindings[0]
    tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == GC_TRACK_CLASS]
    if len(tracks) != 1:
        _stop(run, "OPENING_GC_TRACK_COUNT|%d" % len(tracks))
    sections = sorted(list(tracks[0].get_sections()), key=lambda s: _ival(s.get_start_frame()))
    if len(sections) != 3:
        _stop(run, "OPENING_GC_SECTION_COUNT|%d" % len(sections))
    template = binding.get_object_template()
    if template is None or template.get_class().get_name() != "GeometryCacheActor":
        _stop(run, "OPENING_TEMPLATE_CLASS|%s" % (template.get_class().get_name() if template else None))
    comp = template.get_editor_property("geometry_cache_component")
    return {
        "snapshot": {
            "sequence": OPENING_SEQUENCE,
            "binding": OPENING_BINDING,
            "template_asset": _pk(comp.get_editor_property("geometry_cache")),
            "sections": [_section_row(s) for s in sections],
        },
        "sequence": seq,
        "binding": binding,
        "component": comp,
        "sections": sections,
    }


def _transition_snapshot(run):
    rows = []
    for path in TRANSITION_SEQUENCES:
        seq = unreal.load_asset(path)
        if seq is None:
            _stop(run, "TRANSITION_SEQUENCE_MISSING|" + path)
        for binding in seq.get_bindings():
            for track in binding.get_tracks():
                if track.get_class().get_name() != GC_TRACK_CLASS:
                    continue
                for section in track.get_sections():
                    row = _section_row(section)
                    row.update({"sequence": path, "binding": str(binding.get_display_name())})
                    rows.append(row)
    rows.sort(key=lambda r: (r["sequence"], r["binding"], r["range"]))
    try:
        transition_guard(rows)
    except PlanError as exc:
        _stop(run, str(exc))
    return rows


def _set_assets(ctx, cache):
    ctx["sequence"].modify()
    ctx["component"].set_editor_property("geometry_cache", cache)
    for section in ctx["sections"]:
        params = section.get_editor_property("params")
        params.set_editor_property("geometry_cache_asset", cache)
        section.set_editor_property("params", params)


def _preflight(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    if world is None or _pk(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD|%s" % (_pk(world.get_outermost().get_name()) if world else None))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_CENSUS|" + json.dumps(_census()))
    source, target = unreal.load_asset(SOURCE_CACHE), unreal.load_asset(TARGET_CACHE)
    if source is None or target is None:
        _stop(run, "CACHE_MISSING|source=%s|target=%s" % (source is not None, target is not None))
    for cache, label, frames in ((source, "source", (450, 780)), (target, "target", (450, 1080))):
        if not isinstance(cache, unreal.GeometryCache):
            _stop(run, "CACHE_CLASS|%s|%s" % (label, cache.get_class().get_name()))
        got_frames = (int(cache.get_editor_property("start_frame")), int(cache.get_editor_property("end_frame")))
        if got_frames != frames:
            _stop(run, "CACHE_FRAME_RANGE|%s|got=%r|want=%r" % (label, got_frames, frames))
        materials = [_pk(m) for m in list(cache.get_editor_property("materials"))]
        if not materials or any(path != EXPECTED_MI for path in materials):
            _stop(run, "CACHE_MATERIALS|%s|got=%r|want=%s" % (label, materials, EXPECTED_MI))
    sidecar_path = os.path.join(os.path.dirname(_here()), "q16", "ragged_proscenium_p02_held_import_record.json")
    if not os.path.isfile(sidecar_path):
        _stop(run, "Q16_SIDECAR_MISSING|" + sidecar_path)
    with open(sidecar_path, encoding="utf-8") as handle:
        sidecar = json.load(handle)
    facts = sidecar.get("record_fields") or {}
    if (facts.get("show_start"), facts.get("frames"), facts.get("release_frame")) != (450, 1080, 480):
        _stop(run, "Q16_SIDECAR_FACTS|got=%r|want=(450,1080,480)" %
              ((facts.get("show_start"), facts.get("frames"), facts.get("release_frame")),))
    seq = unreal.load_asset(OPENING_SEQUENCE)
    if seq is None:
        _stop(run, "OPENING_SEQUENCE_MISSING")
    return source, target, seq


def _dry(run, args, seq):
    ctx = _opening_snapshot(seq, run)
    try:
        after = replace_opening_assets(ctx["snapshot"], SOURCE_CACHE, TARGET_CACHE)
    except PlanError as exc:
        _stop(run, str(exc))
    transitions = _transition_snapshot(run)
    report = {
        "schema": "pussstage.q17.ragged_opening_swap.dry.v1",
        "run": run,
        "mode": "DRY",
        "mutated": False,
        "decided_by": args.get("decided_by"),
        "census": _census(),
        "before": ctx["snapshot"],
        "planned_after": after,
        "transition_rows_unchanged": transitions,
        "save_scope": [OPENING_SEQUENCE],
    }
    path = os.path.join(_here(), "opening_ragged_swap_dry_%s.json" % re.sub(r"[^A-Za-z0-9_.-]", "_", run))
    _write(path, report)
    unreal.log("%s_DRY_OK|run=%s|mutated=0|opening_fields=4|transition_rows=%d|save_scope=%s|report=%s"
               % (MARK, run, len(transitions), OPENING_SEQUENCE, path))


def _apply(run, args, target, seq):
    record_path = os.path.join(_here(), RECORD_NAME)
    if os.path.exists(record_path):
        _stop(run, "RECORD_EXISTS|%s|REVERT first" % record_path)
    ctx = _opening_snapshot(seq, run)
    try:
        expected = replace_opening_assets(ctx["snapshot"], SOURCE_CACHE, TARGET_CACHE)
    except PlanError as exc:
        _stop(run, str(exc))
    transitions = _transition_snapshot(run)
    backup = _backup(run, "PreRaggedOpeningSwap")
    record = {
        "schema": "pussstage.q17.ragged_opening_swap.record.v1",
        "state": "prepared",
        "run": run,
        "mode": "APPLY",
        "decided_by": args.get("decided_by"),
        "backup": backup,
        "census_before": _census(),
        "before": ctx["snapshot"],
        "expected_after": expected,
        "transition_rows_before": transitions,
        "save_scope": [OPENING_SEQUENCE],
    }
    _write_exclusive(record_path, record)  # Record and backup both exist before the first mutation.
    _set_assets(ctx, target)
    got = _opening_snapshot(seq, run)["snapshot"]
    if got != expected:
        _stop(run, "PRESAVE_READBACK|got=%s|want=%s|backup=%s" % (json.dumps(got), json.dumps(expected), backup["folder"]))
    if _transition_snapshot(run) != transitions:
        _stop(run, "TRANSITIONS_CHANGED_PRESAVE|backup=" + backup["folder"])
    census = _census()
    if census != {"content": [OPENING_SEQUENCE], "maps": []}:
        _stop(run, "DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart|backup=%s" % (json.dumps(census), backup["folder"]))
    saved = bool(unreal.EditorAssetLibrary.save_asset(OPENING_SEQUENCE, only_if_is_dirty=True))
    final_census = _census()
    got_saved = _opening_snapshot(unreal.load_asset(OPENING_SEQUENCE), run)["snapshot"]
    transitions_saved = _transition_snapshot(run)
    if not saved or final_census != {"content": [], "maps": []} or got_saved != expected or transitions_saved != transitions:
        _stop(run, "POSTSAVE_READBACK|saved=%s|census=%s|opening_ok=%s|transitions_ok=%s|backup=%s"
              % (saved, json.dumps(final_census), got_saved == expected, transitions_saved == transitions, backup["folder"]))
    record.update({"state": "applied", "saved": {OPENING_SEQUENCE: saved}, "census_after": final_census,
                   "read_back": got_saved, "transition_rows_after": transitions_saved})
    _write(record_path, record)
    unreal.log("%s_APPLY_OK|run=%s|opening_fields=4|transition_rows_unchanged=%d|saved=%s|dirty_final=0|backup=%s|record=%s"
               % (MARK, run, len(transitions), OPENING_SEQUENCE, backup["folder"], record_path))


def _revert(run, args, source, seq):
    record_path = os.path.join(_here(), RECORD_NAME)
    if not os.path.isfile(record_path):
        _stop(run, "APPLY_RECORD_MISSING|" + record_path)
    with open(record_path, encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("state") != "applied" or record.get("expected_after") is None or record.get("before") is None:
        _stop(run, "APPLY_RECORD_NOT_APPLIED")
    ctx = _opening_snapshot(seq, run)
    if ctx["snapshot"] != record["expected_after"]:
        _stop(run, "OPENING_DRIFT_SINCE_APPLY")
    transitions = _transition_snapshot(run)
    if transitions != record.get("transition_rows_after"):
        _stop(run, "TRANSITIONS_DRIFT_SINCE_APPLY")
    backup = _backup(run, "PreRaggedOpeningSwapRevert")
    revert_path = os.path.join(_here(), "opening_ragged_swap_revert_%s.json" % re.sub(r"[^A-Za-z0-9_.-]", "_", run))
    revert_record = {
        "schema": "pussstage.q17.ragged_opening_swap.revert.v1",
        "state": "prepared",
        "run": run,
        "mode": "REVERT",
        "decided_by": args.get("decided_by"),
        "apply_record": record_path,
        "backup": backup,
        "census_before": _census(),
        "restore": record["before"],
        "transition_rows_before": transitions,
        "save_scope": [OPENING_SEQUENCE],
    }
    _write_exclusive(revert_path, revert_record)
    _set_assets(ctx, source)
    got = _opening_snapshot(seq, run)["snapshot"]
    if got != record["before"] or _transition_snapshot(run) != transitions:
        _stop(run, "REVERT_PRESAVE_READBACK|opening_ok=%s|transitions_ok=%s|backup=%s"
              % (got == record["before"], _transition_snapshot(run) == transitions, backup["folder"]))
    census = _census()
    if census != {"content": [OPENING_SEQUENCE], "maps": []}:
        _stop(run, "REVERT_DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart|backup=%s" % (json.dumps(census), backup["folder"]))
    saved = bool(unreal.EditorAssetLibrary.save_asset(OPENING_SEQUENCE, only_if_is_dirty=True))
    final_census = _census()
    got_saved = _opening_snapshot(unreal.load_asset(OPENING_SEQUENCE), run)["snapshot"]
    transitions_saved = _transition_snapshot(run)
    if not saved or final_census != {"content": [], "maps": []} or got_saved != record["before"] or transitions_saved != transitions:
        _stop(run, "REVERT_POSTSAVE_READBACK|saved=%s|census=%s|opening_ok=%s|transitions_ok=%s|backup=%s"
              % (saved, json.dumps(final_census), got_saved == record["before"], transitions_saved == transitions, backup["folder"]))
    revert_record.update({"state": "reverted", "saved": {OPENING_SEQUENCE: saved}, "census_after": final_census,
                          "read_back": got_saved, "transition_rows_after": transitions_saved})
    _write(revert_path, revert_record)
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("%s_REVERT_OK|run=%s|opening_fields=4|transition_rows_unchanged=%d|saved=%s|dirty_final=0|backup=%s|record=%s|apply_record=%s"
               % (MARK, run, len(transitions), OPENING_SEQUENCE, backup["folder"], revert_path, archived))


def main():
    run = "Q17-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    args_path = os.path.join(_here(), ARGS_NAME)
    with open(args_path, encoding="utf-8") as handle:
        args = json.load(handle)
    run = str(args.get("run_id") or run)
    try:
        mode = validate_args(args)
    except PlanError as exc:
        _stop(run, "ARGS|" + str(exc))
    source, target, seq = _preflight(run)
    if mode == "DRY":
        _dry(run, args, seq)
    elif mode == "APPLY":
        _apply(run, args, target, seq)
    else:
        _revert(run, args, source, seq)


if unreal is not None:
    try:
        main()
    except ToolStopped:
        raise
    except Exception as exc:
        unreal.log_error("%s_STOPPED|run=UNCAUGHT|reason=%s" % (MARK, exc))
        raise
