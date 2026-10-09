"""Q18: retarget one existing P02/P03 end drape to the ragged held cache.

OFFLINE-WRITTEN TOOL ONLY.  Run later through ExecuteProjectPythonFile after
reviewing ragged_endcurtain_swap_args.json.  DRY/APPLY/REVERT operate on one
passage at a time.  APPLY changes exactly two asset references: the existing
level actor component's geometry_cache and the one Geometry Cache section in
that passage's HangarRise sequence.  REVERT restores those two fields from the
APPLY record.

Dedupe verdict [declaration-proven]: passage_end_drape.py creates/removes the
actor and binding and refuses an existing actor/binding/backcloth slot
(Saved/CodexConductor/passage_end_drape.py:515-524,1086-1146,1205-1257).
curtain_image.py changes component material overrides only
(Saved/CodexConductor/curtain_image.py:460-509).  Neither is a config-only
retargeter, so this separate field-scoped tool is required.
"""
from __future__ import annotations

import argparse
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


MARK = "Q18_RAGGED_ENDCURTAIN"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SOURCE_CACHE = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
TARGET_CACHE = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_RaggedProscenium_P02Held"
SOURCE_FRAMES = (450, 780)
TARGET_FRAMES = (450, 1080)
GC_TRACK_CLASS = "MovieSceneGeometryCacheTrack"
PLANAR_SCALARS = (
    "PlanarMapping", "PlanarY0Cm", "PlanarWidthCm", "PlanarTopZCm",
    "PlanarHeightCm", "PlanarMinZCm",
)
ARGS_NAME = "ragged_endcurtain_swap_args.json"
PASSAGES = {
    "P02": {
        "number": 2,
        "actor": "P02 End Drape (stand-in)",
        "sequence": "/Game/InfinityStage/RigAtmos/LS_S2_HangarRise",
        "material": "/Game/InfinityStage/Curtains/Image/MI_CurtainImage_P02",
    },
    "P03": {
        "number": 3,
        "actor": "P03 End Drape (stand-in)",
        "sequence": "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise",
        "material": "/Game/InfinityStage/Curtains/Image/MI_CurtainImage_P03",
    },
}


class PlanError(ValueError):
    pass


class ToolStopped(RuntimeError):
    pass


def _enum_is(value, name):
    """UE enums may print as '<EnumType.NAME: n>' or as bare 'NAME'."""
    text = str(value).upper().strip("<> ")
    text = text.split(":")[0].strip()
    wanted = str(name).upper()
    return text == wanted or text.endswith("." + wanted)


def _enum_name(value):
    text = str(value).upper().strip("<> ")
    text = text.split(":")[0].strip()
    return text.rsplit(".", 1)[-1]


def validate_args(args):
    mode = str(args.get("mode") or "").upper()
    passage = str(args.get("passage") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise PlanError("MODE_INVALID: %r" % mode)
    if passage not in PASSAGES:
        raise PlanError("PASSAGE_INVALID: %r; use --passage P02|P03" % passage)
    wanted = "%s_RAGGED_ENDCURTAIN_%s_ONLY" % (mode, passage)
    if args.get("confirm") != wanted:
        raise PlanError("CONFIRM_MISMATCH: %r, want %r" % (args.get("confirm"), wanted))
    if mode in ("APPLY", "REVERT") and not str(args.get("decided_by") or "").strip():
        raise PlanError("DECIDED_BY_REQUIRED")
    return mode, passage


def validate_cache_frame_ranges(source_frames, target_frames):
    got_source = tuple(int(v) for v in source_frames)
    got_target = tuple(int(v) for v in target_frames)
    if got_source != SOURCE_FRAMES:
        raise PlanError("CACHE_FRAME_RANGE_SOURCE: got %r, want %r" % (got_source, SOURCE_FRAMES))
    if got_target != TARGET_FRAMES:
        raise PlanError("CACHE_FRAME_RANGE_TARGET: got %r, want %r" % (got_target, TARGET_FRAMES))
    return True


def validate_census(census, content=(), maps=()):
    got = {
        "content": sorted(census.get("content") or []),
        "maps": sorted(census.get("maps") or []),
    }
    wanted = {"content": sorted(content), "maps": sorted(maps)}
    if got != wanted:
        raise PlanError("DIRTY_CENSUS: got %r, want %r" % (got, wanted))
    return True


def build_expected(snapshot, spec, old_cache, new_cache):
    """Pure two-field mutation model used by live read-back and the harness."""
    if snapshot.get("actor_label") != spec["actor"]:
        raise PlanError("ACTOR_LABEL: got %r, want %r" % (snapshot.get("actor_label"), spec["actor"]))
    component = snapshot.get("component") or {}
    if component.get("cache") == new_cache:
        raise PlanError("NOOP_COMPONENT_ALREADY_TARGET")
    if component.get("cache") != old_cache:
        raise PlanError("COMPONENT_CACHE: got %r, want %r" % (component.get("cache"), old_cache))
    flags = {name: component.get(name) for name in ("manual_tick", "running", "looping")}
    wanted_flags = {"manual_tick": True, "running": True, "looping": False}
    if flags != wanted_flags:
        raise PlanError("COMPONENT_PLAYBACK_FLAGS: got %r, want %r" % (flags, wanted_flags))
    sections = snapshot.get("sections") or []
    if len(sections) != 1:
        raise PlanError("GC_SECTION_COUNT: got %d, want 1" % len(sections))
    if sections[0].get("asset") == new_cache:
        raise PlanError("NOOP_SECTION_ALREADY_TARGET")
    if sections[0].get("asset") != old_cache:
        raise PlanError("SECTION_CACHE: got %r, want %r" % (sections[0].get("asset"), old_cache))
    overrides = component.get("override_materials") or []
    if not overrides or any(path != spec["material"] for path in overrides):
        raise PlanError("MI_OVERRIDE_LOST: got %r, want only %s" % (overrides, spec["material"]))
    resolved = component.get("resolved_materials") or []
    if not resolved or any(path != spec["material"] for path in resolved):
        raise PlanError("MI_RESOLVED_MISMATCH: got %r, want only %s" % (resolved, spec["material"]))
    out = copy.deepcopy(snapshot)
    out["component"]["cache"] = new_cache
    out["sections"][0]["asset"] = new_cache
    return out


def build_revert_expected(snapshot, record):
    drift = snapshot_differences(snapshot, record.get("expected_after"))
    if drift:
        raise PlanError("STATE_DRIFTED_SINCE_APPLY: %r" % drift)
    before = record.get("before")
    if not before:
        raise PlanError("APPLY_RECORD_BEFORE_MISSING")
    out = copy.deepcopy(snapshot)
    out["component"]["cache"] = before["component"]["cache"]
    out["sections"][0]["asset"] = before["sections"][0]["asset"]
    return out


def _number_tolerance(path):
    joined = ".".join(path)
    if ".transform.location." in joined:
        return 0.01
    if ".transform.rotation." in joined:
        return 0.001
    if ".transform.scale." in joined:
        return 1.0e-6
    if ".planar_scalars." in joined:
        return 1.0e-4
    return 1.0e-7


def snapshot_differences(got, wanted, path=("snapshot",)):
    """Numeric read-back: cm 0.01, degrees 0.001, MI scalars 1e-4."""
    if isinstance(got, dict) and isinstance(wanted, dict):
        out = []
        if set(got) != set(wanted):
            out.append("%s keys %r != %r" % (".".join(path), sorted(got), sorted(wanted)))
            return out
        for key in sorted(got):
            out.extend(snapshot_differences(got[key], wanted[key], path + (str(key),)))
        return out
    if isinstance(got, list) and isinstance(wanted, list):
        if len(got) != len(wanted):
            return ["%s length %d != %d" % (".".join(path), len(got), len(wanted))]
        out = []
        for index, (left, right) in enumerate(zip(got, wanted)):
            out.extend(snapshot_differences(left, right, path + (str(index),)))
        return out
    if isinstance(got, (int, float)) and isinstance(wanted, (int, float)) and not isinstance(got, bool):
        if abs(float(got) - float(wanted)) > _number_tolerance(path):
            return ["%s %.9g != %.9g" % (".".join(path), got, wanted)]
        return []
    return [] if got == wanted else ["%s %r != %r" % (".".join(path), got, wanted)]


def _here():
    if unreal is not None:
        return os.path.join(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
            "CodexSoftGoods", "q18",
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


def _guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise ToolStopped(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(_pk(p.get_path_name()) for p in lib.get_dirty_content_packages()),
        "maps": sorted(_pk(p.get_path_name()) for p in lib.get_dirty_map_packages()),
    }


def _content_file(asset_path, extension):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *asset_path[len("/Game/"):].split("/")) + extension


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_exclusive(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())


def _write(path, value):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _backup(run, passage, spec, suffix=""):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "PreRaggedEndCurtainSwap-%s-%s%s" % (passage, run, suffix))
    os.makedirs(folder, exist_ok=False)
    rows = []
    for source in (_content_file(spec["sequence"], ".uasset"), _content_file(EXPECTED_WORLD, ".umap")):
        if not os.path.isfile(source):
            _stop(run, "BACKUP_SOURCE_MISSING|" + source)
        destination = os.path.join(folder, os.path.basename(source))
        shutil.copy2(source, destination)
        before, after = _sha256(source), _sha256(destination)
        if before != after:
            _stop(run, "BACKUP_HASH_MISMATCH|" + source)
        rows.append({"source": source, "backup": destination, "sha256": after})
    return {"folder": folder, "files": rows}


def _material_row(material):
    mel = unreal.MaterialEditingLibrary
    texture = mel.get_material_instance_texture_parameter_value(material, "Image")
    return {
        "path": _pk(material),
        "image_texture": _pk(texture),
        "planar_scalars": {
            name: float(mel.get_material_instance_scalar_parameter_value(material, name))
            for name in PLANAR_SCALARS
        },
    }


def _section_row(section):
    params = section.get_editor_property("params")
    options = section.get_editor_property("eval_options")
    completion = options.get_editor_property("completion_mode")
    if not _enum_is(completion, "KEEP_STATE"):
        raise PlanError("SECTION_COMPLETION: got %s, want KEEP_STATE" % _enum_name(completion))
    row = {
        "asset": _pk(params.get_editor_property("geometry_cache_asset")),
        "range": [_ival(section.get_start_frame()), _ival(section.get_end_frame())],
        "start_frame_offset": _ival(params.get_editor_property("start_frame_offset")),
        "end_frame_offset": _ival(params.get_editor_property("end_frame_offset")),
        "play_rate": float(params.get_editor_property("play_rate")),
        "completion_mode": _enum_name(completion),
    }
    for name in ("reverse", "looping"):
        try:
            row[name] = bool(params.get_editor_property(name))
        except Exception:  # UE version/property shape: absence is recorded, never guessed.
            row[name] = None
    return row


def _load_placement_record(spec, run):
    path = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor", "passage_end_drape_record_S%d.json" % spec["number"],
    )
    if not os.path.isfile(path):
        _stop(run, "PLACEMENT_RECORD_MISSING|" + path)
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    if not record.get("applied") or int(record.get("scene", -1)) != spec["number"]:
        _stop(run, "PLACEMENT_RECORD_CONTEXT|" + path)
    return path, record


def _live_context(passage, run):
    spec = PASSAGES[passage]
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    matches = [actor for actor in actors if str(actor.get_actor_label()) == spec["actor"]]
    if len(matches) != 1:
        _stop(run, "ACTOR_LABEL_COUNT|%s|%d" % (spec["actor"], len(matches)))
    actor = matches[0]
    component = actor.get_component_by_class(unreal.GeometryCacheComponent)
    if component is None:
        _stop(run, "ACTOR_NOT_GEOMETRY_CACHE|" + spec["actor"])
    sequence = unreal.load_asset(spec["sequence"])
    if sequence is None:
        _stop(run, "SEQUENCE_MISSING|" + spec["sequence"])
    record_path, placement_record = _load_placement_record(spec, run)
    wanted_guid = str(placement_record.get("binding_guid") or "").replace("-", "").upper()
    bindings = [binding for binding in sequence.get_bindings() if _guid(binding.get_id()) == wanted_guid]
    if len(bindings) != 1:
        _stop(run, "BINDING_GUID_COUNT|%s|%d" % (wanted_guid, len(bindings)))
    binding = bindings[0]
    if str(binding.get_display_name()) != spec["actor"]:
        _stop(run, "BINDING_LABEL|got=%s|want=%s" % (binding.get_display_name(), spec["actor"]))
    tracks = [track for track in binding.get_tracks() if track.get_class().get_name() == GC_TRACK_CLASS]
    if len(tracks) != 1:
        _stop(run, "GC_TRACK_COUNT|%d" % len(tracks))
    sections = list(tracks[0].get_sections())
    if len(sections) != 1:
        _stop(run, "GC_SECTION_COUNT|%d" % len(sections))
    return {
        "spec": spec,
        "actor": actor,
        "component": component,
        "sequence": sequence,
        "binding": binding,
        "section": sections[0],
        "placement_record": record_path,
    }


def _snapshot(context):
    actor, component = context["actor"], context["component"]
    location, rotation, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
    overrides = list(component.get_editor_property("override_materials") or [])
    override_paths = [_pk(value) for value in overrides]
    slots = int(component.get_num_materials())
    resolved = [_pk(component.get_material(index)) for index in range(slots)]
    material_rows = [_material_row(value) for value in overrides if value is not None]
    return {
        "actor_label": str(actor.get_actor_label()),
        "actor_path": str(actor.get_path_name()),
        "transform": {
            "location": [float(location.x), float(location.y), float(location.z)],
            "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
            "scale": [float(scale.x), float(scale.y), float(scale.z)],
        },
        "component": {
            "cache": _pk(component.get_editor_property("geometry_cache")),
            "manual_tick": bool(component.get_editor_property("manual_tick")),
            "running": bool(component.get_editor_property("running")),
            "looping": bool(component.get_editor_property("looping")),
            "override_materials": override_paths,
            "resolved_materials": resolved,
            "material_parameters": material_rows,
        },
        "sequence": context["spec"]["sequence"],
        "binding_guid": _guid(context["binding"].get_id()),
        "binding_label": str(context["binding"].get_display_name()),
        "sections": [_section_row(context["section"])],
    }


def _set_two_fields(context, cache):
    context["actor"].modify()
    context["sequence"].modify()
    context["component"].set_editor_property("geometry_cache", cache)
    params = context["section"].get_editor_property("params")
    params.set_editor_property("geometry_cache_asset", cache)
    context["section"].set_editor_property("params", params)


def _preflight(passage, run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    if world is None or _pk(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD|%s" % (_pk(world.get_outermost().get_name()) if world else None))
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_OPEN|never open or scrub Master")
    try:
        validate_census(_census())
    except PlanError as exc:
        _stop(run, str(exc))
    spec = PASSAGES[passage]
    if "klara" in EXPECTED_WORLD.lower() or "klara" in spec["sequence"].lower():
        _stop(run, "KLARA_LEVEL_SAVE_FORBIDDEN")
    source, target = unreal.load_asset(SOURCE_CACHE), unreal.load_asset(TARGET_CACHE)
    if source is None or target is None:
        _stop(run, "CACHE_MISSING|source=%s|target=%s" % (source is not None, target is not None))
    if not isinstance(source, unreal.GeometryCache) or not isinstance(target, unreal.GeometryCache):
        _stop(run, "CACHE_CLASS")
    try:
        validate_cache_frame_ranges(
            (source.get_editor_property("start_frame"), source.get_editor_property("end_frame")),
            (target.get_editor_property("start_frame"), target.get_editor_property("end_frame")),
        )
    except PlanError as exc:
        _stop(run, str(exc))
    return world, source, target, _live_context(passage, run)


def _record_path(passage):
    return os.path.join(_here(), "ragged_endcurtain_swap_record_%s.json" % passage)


def _dry(run, args, passage, context):
    before = _snapshot(context)
    try:
        planned = build_expected(before, context["spec"], SOURCE_CACHE, TARGET_CACHE)
    except PlanError as exc:
        _stop(run, str(exc))
    report = {
        "schema": "pussstage.q18.ragged_endcurtain_swap.dry.v1",
        "run": run,
        "mode": "DRY",
        "passage": passage,
        "mutated": False,
        "decided_by": args.get("decided_by"),
        "census": _census(),
        "before": before,
        "planned_after": planned,
        "save_scope": [context["spec"]["sequence"], EXPECTED_WORLD],
        "placement_record": context["placement_record"],
    }
    path = os.path.join(_here(), "ragged_endcurtain_swap_dry_%s_%s.json" %
                        (passage, re.sub(r"[^A-Za-z0-9_.-]", "_", run)))
    _write(path, report)
    try:
        validate_census(_census())
    except PlanError as exc:
        _stop(run, "DRY_DIRTIED|" + str(exc))
    section = before["sections"][0]
    unreal.log(
        "%s_DRY_OK|run=%s|passage=%s|mutated=0|actor_cache=%s|overrides=%s|section_asset=%s|"
        "section_range=%s|start_offset=%s|save_scope=%s,%s|report=%s"
        % (MARK, run, passage, before["component"]["cache"], before["component"]["override_materials"],
           section["asset"], section["range"], section["start_frame_offset"], context["spec"]["sequence"],
           EXPECTED_WORLD, path)
    )


def _apply(run, args, passage, world, target, context):
    record_path = _record_path(passage)
    if os.path.exists(record_path):
        _stop(run, "RECORD_EXISTS|%s|REVERT first" % record_path)
    before = _snapshot(context)
    try:
        expected = build_expected(before, context["spec"], SOURCE_CACHE, TARGET_CACHE)
    except PlanError as exc:
        _stop(run, str(exc))
    backup = _backup(run, passage, context["spec"])
    record = {
        "schema": "pussstage.q18.ragged_endcurtain_swap.record.v1",
        "state": "prepared",
        "run": run,
        "mode": "APPLY",
        "passage": passage,
        "decided_by": args.get("decided_by"),
        "backup": backup,
        "census_before": _census(),
        "before": before,
        "expected_after": expected,
        "save_scope": [context["spec"]["sequence"], EXPECTED_WORLD],
        "placement_record": context["placement_record"],
    }
    _write_exclusive(record_path, record)  # Backup + durable record exist before mutation.
    _set_two_fields(context, target)
    got = _snapshot(context)
    differences = snapshot_differences(got, expected)
    try:
        validate_census(_census(), [context["spec"]["sequence"]], [EXPECTED_WORLD])
    except PlanError as exc:
        differences.append(str(exc))
    if differences:
        _stop(run, "PRESAVE_READBACK|%r|NOTHING SAVED; Don't-Save restart|backup=%s" %
              (differences, backup["folder"]))
    saves = {
        context["spec"]["sequence"]: bool(unreal.EditorAssetLibrary.save_asset(
            context["spec"]["sequence"], only_if_is_dirty=True)),
        EXPECTED_WORLD: bool(unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD)),
    }
    post_context = _live_context(passage, run)
    read_back = _snapshot(post_context)
    final_census = _census()
    differences = snapshot_differences(read_back, expected)
    if not all(saves.values()) or differences or final_census != {"content": [], "maps": []}:
        _stop(run, "POSTSAVE_READBACK|saves=%r|diff=%r|census=%r|backup=%s" %
              (saves, differences, final_census, backup["folder"]))
    record.update({"state": "applied", "saves": saves, "read_back": read_back, "census_after": final_census})
    _write(record_path, record)
    unreal.log(
        "%s_APPLY_OK|run=%s|passage=%s|fields=2|actor=%s|sequence=%s|dirty_final=0|backup=%s|record=%s"
        % (MARK, run, passage, context["spec"]["actor"], context["spec"]["sequence"], backup["folder"], record_path)
    )


def _revert(run, args, passage, world, source, context):
    record_path = _record_path(passage)
    if not os.path.isfile(record_path):
        _stop(run, "APPLY_RECORD_MISSING|" + record_path)
    with open(record_path, encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("state") != "applied" or record.get("passage") != passage:
        _stop(run, "APPLY_RECORD_CONTEXT")
    live = _snapshot(context)
    try:
        expected = build_revert_expected(live, record)
    except PlanError as exc:
        _stop(run, str(exc))
    if expected["component"]["cache"] != _pk(source) or expected["sections"][0]["asset"] != _pk(source):
        _stop(run, "REVERT_SOURCE_NOT_CURRENT_CANONICAL")
    backup = _backup(run, passage, context["spec"], suffix="-revert")
    revert_path = os.path.join(
        _here(), "ragged_endcurtain_swap_revert_%s_%s.json" %
        (passage, re.sub(r"[^A-Za-z0-9_.-]", "_", run)),
    )
    revert_record = {
        "schema": "pussstage.q18.ragged_endcurtain_swap.revert.v1",
        "state": "prepared",
        "run": run,
        "mode": "REVERT",
        "passage": passage,
        "decided_by": args.get("decided_by"),
        "apply_record": record_path,
        "backup": backup,
        "before_revert": live,
        "restore": expected,
        "save_scope": [context["spec"]["sequence"], EXPECTED_WORLD],
    }
    _write_exclusive(revert_path, revert_record)
    _set_two_fields(context, source)
    got = _snapshot(context)
    differences = snapshot_differences(got, expected)
    try:
        validate_census(_census(), [context["spec"]["sequence"]], [EXPECTED_WORLD])
    except PlanError as exc:
        differences.append(str(exc))
    if differences:
        _stop(run, "REVERT_PRESAVE_READBACK|%r|NOTHING SAVED; Don't-Save restart|backup=%s" %
              (differences, backup["folder"]))
    saves = {
        context["spec"]["sequence"]: bool(unreal.EditorAssetLibrary.save_asset(
            context["spec"]["sequence"], only_if_is_dirty=True)),
        EXPECTED_WORLD: bool(unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD)),
    }
    read_back = _snapshot(_live_context(passage, run))
    final_census = _census()
    differences = snapshot_differences(read_back, expected)
    if not all(saves.values()) or differences or final_census != {"content": [], "maps": []}:
        _stop(run, "REVERT_POSTSAVE_READBACK|saves=%r|diff=%r|census=%r|backup=%s" %
              (saves, differences, final_census, backup["folder"]))
    revert_record.update({"state": "reverted", "saves": saves, "read_back": read_back,
                          "census_after": final_census})
    _write(revert_path, revert_record)
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log(
        "%s_REVERT_OK|run=%s|passage=%s|fields=2|actor=%s|sequence=%s|dirty_final=0|backup=%s|record=%s|apply_record=%s"
        % (MARK, run, passage, context["spec"]["actor"], context["spec"]["sequence"], backup["folder"],
           revert_path, archived)
    )


def _load_args():
    with open(os.path.join(_here(), ARGS_NAME), encoding="utf-8") as handle:
        args = json.load(handle)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--passage", choices=sorted(PASSAGES))
    parsed, _unknown = parser.parse_known_args()
    if parsed.passage:
        args["passage"] = parsed.passage
    return args


def main():
    args = _load_args()
    run = str(args.get("run_id") or "Q18-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    try:
        mode, passage = validate_args(args)
    except PlanError as exc:
        _stop(run, "ARGS|" + str(exc))
    world, source, target, context = _preflight(passage, run)
    if mode == "DRY":
        _dry(run, args, passage, context)
    elif mode == "APPLY":
        _apply(run, args, passage, world, target, context)
    else:
        _revert(run, args, passage, world, source, context)


if unreal is not None:
    try:
        main()
    except ToolStopped:
        raise
    except Exception as exc:
        unreal.log_error("%s_STOPPED|run=UNCAUGHT|reason=%s" % (MARK, exc))
        raise
