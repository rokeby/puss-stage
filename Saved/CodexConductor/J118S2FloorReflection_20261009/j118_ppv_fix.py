"""Held Job 118 fix: bounded persistent-level S2 PPV copied from a P01 PPV.

DRY is the default. APPLY requires ``APPLY J118S2PPV``; REVERT requires
``REVERT J118S2PPV``.  The tool never edits or saves Klara's streamed levels.
It duplicates a persistent-level PPV which affects the P01 floor, fits that duplicate around
S2 Hangar Floor 1-3 + Apron, and gives it priority above every PPV affecting those floors.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil

try:
    import unreal
except ImportError:  # offline harness imports the pure helpers
    unreal = None

MARK = "J118_S2_PPV"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
P01 = "Passage 01 - Opening Floor"
S2 = ("S2 Hangar Floor 1", "S2 Hangar Floor 2", "S2 Hangar Floor 3", "S2 Hangar Apron")
TAG = "Codex.J118.S2FloorReflectionPPV"
KLARA_PACKAGES = {
    "/Game/KK_S1_Animals/L_Animals", "/Game/L_KK_children",
    "/Game/Japanese_Alley/Maps/Japanese_Alley", "/Game/L_KK_Void",
}
COPY_FIELDS = (
    "reflection_method", "lumen_reflection_quality", "lumen_max_roughness_to_trace_reflections",
    "lumen_reflections_screen_traces", "screen_space_reflection_intensity",
    "screen_space_reflection_quality", "screen_space_reflection_max_roughness",
    "auto_exposure_method", "auto_exposure_min_brightness", "auto_exposure_max_brightness",
    "auto_exposure_bias", "auto_exposure_low_percent", "auto_exposure_high_percent",
    "auto_exposure_speed_up", "auto_exposure_speed_down",
    "local_exposure_highlight_contrast_scale", "local_exposure_shadow_contrast_scale",
)


class Refused(RuntimeError):
    pass


def target_box(bounds, xy_padding_cm, below_floor_cm, above_floor_cm):
    """Pure helper: target AABB from S2 floor AABBs."""
    if not bounds:
        raise ValueError("no floor bounds")
    lo = [min(row["min"][i] for row in bounds) for i in range(3)]
    hi = [max(row["max"][i] for row in bounds) for i in range(3)]
    floor_bottom, floor_top = lo[2], hi[2]
    lo = [lo[0] - xy_padding_cm, lo[1] - xy_padding_cm, floor_bottom - below_floor_cm]
    hi = [hi[0] + xy_padding_cm, hi[1] + xy_padding_cm, floor_top + above_floor_cm]
    return {"min": lo, "max": hi,
            "center": [(lo[i] + hi[i]) * 0.5 for i in range(3)],
            "extent": [(hi[i] - lo[i]) * 0.5 for i in range(3)]}


def scaled_actor_scale(source_scale, source_extent, target_extent):
    if any(float(value) <= 0.01 for value in source_extent):
        raise ValueError("template PPV has degenerate brush bounds")
    return [float(source_scale[i]) * float(target_extent[i]) / float(source_extent[i]) for i in range(3)]


def recentered_actor_location(source_location, source_bounds_origin, source_scale, target_scale, target_center):
    """Keep an off-centre brush's bounds centred after actor-scale changes (zero-rotation template)."""
    if any(abs(float(value)) <= 1e-9 for value in source_scale):
        raise ValueError("template PPV has zero actor scale")
    ratio = [float(target_scale[i]) / float(source_scale[i]) for i in range(3)]
    offset = [(float(source_bounds_origin[i]) - float(source_location[i])) * ratio[i] for i in range(3)]
    return [float(target_center[i]) - offset[i] for i in range(3)]


def choose_template(candidates, requested):
    """Candidates are persistent P01-containing PPV labels."""
    labels = sorted(set(str(value) for value in candidates))
    if requested:
        if labels.count(requested) != 1:
            raise ValueError("requested template is not one persistent P01 candidate")
        return requested
    if len(labels) != 1:
        raise ValueError("set template_p01_ppv_label; candidates=%r" % labels)
    return labels[0]


def confirm_ok(mode, confirm):
    return mode == "DRY" or confirm == "%s J118S2PPV" % mode


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _path(obj):
    return obj.get_path_name() if obj is not None else None


def _prop(obj, name, missing=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return missing


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name() for p in lib.get_dirty_map_packages())}


def _bounds(actor):
    origin, extent = unreal.SystemLibrary.get_actor_bounds(actor, False)
    return {"origin": [float(origin.x), float(origin.y), float(origin.z)],
            "extent": [float(extent.x), float(extent.y), float(extent.z)],
            "min": [float(origin.x - extent.x), float(origin.y - extent.y), float(origin.z - extent.z)],
            "max": [float(origin.x + extent.x), float(origin.y + extent.y), float(origin.z + extent.z)]}


def _contains(volume, point):
    if bool(_prop(volume, "unbound", False)):
        return True
    fn = getattr(volume, "encompasses_point", None)
    if fn:
        try:
            got = fn(unreal.Vector(*point), 0.0)
            return bool(got[0] if isinstance(got, tuple) else got)
        except Exception:
            pass
    b = _bounds(volume)
    return all(b["min"][i] <= point[i] <= b["max"][i] for i in range(3))


def _actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _one_label(actors, label):
    found = [actor for actor in actors if str(actor.get_actor_label()) == label]
    if len(found) != 1:
        raise Refused("ACTOR_COUNT|label=%s|count=%d" % (label, len(found)))
    return found[0]


def _snapshot_settings(volume):
    settings = _prop(volume, "settings")
    out = {}
    for name in COPY_FIELDS:
        out[name] = {"value": _plain(_prop(settings, name, "PROPERTY_UNAVAILABLE")),
                     "override": _plain(_prop(settings, "override_" + name, "PROPERTY_UNAVAILABLE"))}
    return out


def _plan(args, actors):
    floors = [_one_label(actors, label) for label in S2]
    if any(actor.get_outermost().get_name() != WORLD for actor in floors):
        raise Refused("S2_FLOOR_NOT_PERSISTENT")
    floor_bounds = [_bounds(actor) for actor in floors]
    box = target_box(floor_bounds, float(args["xy_padding_cm"]), float(args["below_floor_cm"]),
                     float(args["above_floor_cm"]))
    p01 = _one_label(actors, P01)
    p01_center = _bounds(p01)["origin"]
    ppvs = [actor for actor in actors if isinstance(actor, unreal.PostProcessVolume)]
    candidates = [str(volume.get_actor_label()) for volume in ppvs
                  if volume.get_outermost().get_name() == WORLD and _contains(volume, p01_center)]
    try:
        template_label = choose_template(candidates, str(args.get("template_p01_ppv_label", "")))
    except ValueError as exc:
        raise Refused("TEMPLATE_SELECTION|%s" % exc)
    template = _one_label(ppvs, template_label)
    if template.get_outermost().get_name() != WORLD:
        raise Refused("TEMPLATE_NOT_PERSISTENT")
    rot = template.get_actor_rotation()
    if max(abs(float(rot.roll)), abs(float(rot.pitch)), abs(float(rot.yaw))) > 0.01:
        raise Refused("TEMPLATE_ROTATED|rpy=%s" % ([rot.roll, rot.pitch, rot.yaw],))
    tb = _bounds(template)
    source_scale = list(template.get_actor_scale3d().to_tuple())
    source_location = list(template.get_actor_location().to_tuple())
    target_scale = scaled_actor_scale(source_scale, tb["extent"], box["extent"])
    target_location = recentered_actor_location(source_location, tb["origin"], source_scale,
                                                target_scale, box["center"])
    sample = box["center"]
    affecting = [volume for volume in ppvs if bool(_prop(volume, "enabled", True)) and _contains(volume, sample)]
    max_priority = max([float(_prop(volume, "priority", 0.0)) for volume in affecting] or [0.0])
    priority = max_priority + float(args["priority_margin"])
    return {
        "world": WORLD, "floors": list(S2), "target_label": str(args["target_label"]),
        "template_label": template_label, "template_path": _path(template),
        "template_bounds": tb, "template_settings": _snapshot_settings(template),
        "target_box": box, "target_actor_location": target_location,
        "target_scale": target_scale, "priority": priority,
        "s2_affecting_ppvs": [{"label": str(v.get_actor_label()), "level": v.get_outermost().get_name(),
                                "priority": float(_prop(v, "priority", 0.0)),
                                "unbound": bool(_prop(v, "unbound", False))} for v in affecting],
        "packages_allowed_to_dirty_and_save": [WORLD], "klara_packages_forbidden": sorted(KLARA_PACKAGES),
    }, template


def _write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    with open(path, encoding="utf-8") as handle:
        checked = json.load(handle)
    if digest(checked) != digest(value):
        raise Refused("JSON_READBACK_MISMATCH|" + path)


def _backup(here, run, stem, record=None):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    map_file = os.path.join(project, "Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
    backup = os.path.join(project, "Backups", "%s-%s" % (stem, run))
    os.makedirs(backup)
    shutil.copy2(map_file, backup)
    if record and os.path.exists(record):
        shutil.copy2(record, backup)
    return backup


def _require_context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise Refused("PIE_OR_SIE_RUNNING")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != WORLD:
        raise Refused("WRONG_WORLD|%s" % (world.get_outermost().get_name() if world else None))


def _save_level_only():
    now = _census()
    if now["content"] or now["maps"] not in ([WORLD], [WORLD.rsplit("/", 1)[-1]]):
        raise Refused("DIRTY_SCOPE_BEFORE_SAVE|%s|NOTHING_SAVED_DONT_SAVE_RESTART" % json.dumps(now))
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise Refused("LEVEL_SAVE_FAILED")
    final = _census()
    if final != {"content": [], "maps": []}:
        raise Refused("DIRTY_AFTER_SAVE|%s" % json.dumps(final))
    return final


def _apply_settings(volume, source):
    target_settings = _prop(volume, "settings")
    source_settings = _prop(source, "settings")
    for name in COPY_FIELDS:
        value = _prop(source_settings, name, "__MISSING__")
        override = _prop(source_settings, "override_" + name, "__MISSING__")
        if value != "__MISSING__":
            target_settings.set_editor_property(name, value)
        if override != "__MISSING__":
            target_settings.set_editor_property("override_" + name, override)
    volume.set_editor_property("settings", target_settings)


def _find_tagged(actors):
    return [actor for actor in actors if any(str(tag) == TAG for tag in list(_prop(actor, "tags", ()) or ()))]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    args_path = os.path.join(here, "j118_ppv_fix_args.json")
    record_path = os.path.join(here, "j118_ppv_fix_record.json")
    with open(args_path, encoding="utf-8") as handle:
        args = json.load(handle)
    mode = str(args.get("mode", "DRY")).upper()
    run = "J118S2PPV-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise Refused("BAD_MODE|" + mode)
    if not confirm_ok(mode, str(args.get("confirm", ""))):
        raise Refused("CONFIRM_REQUIRED|%s J118S2PPV" % mode)
    _require_context()
    before = _census()
    if mode != "DRY" and before != {"content": [], "maps": []}:
        raise Refused("DIRTY_AT_START|" + json.dumps(before))

    if mode == "REVERT":
        if not os.path.exists(record_path):
            raise Refused("REVERT_RECORD_MISSING")
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        if not record.get("applied") or record.get("world") != WORLD:
            raise Refused("REVERT_RECORD_CONTEXT")
        tagged = _find_tagged(_actors())
        if len(tagged) != 1 or _path(tagged[0]) != record["created_actor_path"]:
            raise Refused("REVERT_TARGET_DRIFT|count=%d" % len(tagged))
        if tagged[0].get_outermost().get_name() != WORLD:
            raise Refused("REVERT_REFUSES_KLARA_LEVEL")
        backup = _backup(here, run, "PreJ118S2PPVRevert", record_path)
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(tagged[0])
        final = _save_level_only()
        archived = record_path + ".reverted-" + run
        os.rename(record_path, archived)
        unreal.log("%s_REVERT_OK|run=%s|backup=%s|saved=%s|klara_saved=0|record=%s" %
                   (MARK, run, backup, WORLD, archived,))
        return

    actors = _actors()
    if _find_tagged(actors) or any(str(actor.get_actor_label()) == args["target_label"] for actor in actors):
        raise Refused("TARGET_ALREADY_EXISTS")
    plan, template = _plan(args, actors)
    plan["plan_digest"] = digest(plan)
    if mode == "DRY":
        after = _census()
        if before != after:
            raise Refused("DRY_DIRTIED_PACKAGES|before=%s|after=%s" % (json.dumps(before), json.dumps(after)))
        dry_path = os.path.join(here, "j118_ppv_fix_dry_%s.json" % run)
        _write_json(dry_path, {"run": run, "mode": mode, "census_before": before,
                               "census_after": after, "plan": plan}, exclusive=True)
        unreal.log("%s_DRY_OK|run=%s|mutated=0|census_before==after=1|template=%s|priority=%.3f|plan=%s" %
                   (MARK, run, plan["template_label"], plan["priority"], dry_path))
        return

    if os.path.exists(record_path):
        raise Refused("APPLY_RECORD_EXISTS")
    backup = _backup(here, run, "PreJ118S2PPV")
    record = {"schema": 1, "run": run, "world": WORLD, "backup": backup, "plan": plan,
              "created_actor_path": None, "applied": False}
    _write_json(record_path, record, exclusive=True)  # durable before first mutation
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    duplicate = subsystem.duplicate_actor(template, world, unreal.Vector(0.0, 0.0, 0.0))
    if duplicate is None:
        raise Refused("DUPLICATE_FAILED|NOTHING_SAVED_DONT_SAVE_RESTART")
    if duplicate.get_outermost().get_name() != WORLD:
        raise Refused("DUPLICATE_NOT_PERSISTENT|NOTHING_SAVED_DONT_SAVE_RESTART")
    duplicate.set_actor_label(plan["target_label"])
    duplicate.tags = list(_prop(duplicate, "tags", ()) or ()) + [unreal.Name(TAG)]
    duplicate.set_actor_location(unreal.Vector(*plan["target_actor_location"]), False, True)
    duplicate.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False)
    duplicate.set_actor_scale3d(unreal.Vector(*plan["target_scale"]))
    duplicate.set_editor_property("unbound", False)
    duplicate.set_editor_property("enabled", True)
    duplicate.set_editor_property("blend_weight", 1.0)
    duplicate.set_editor_property("priority", float(plan["priority"]))
    _apply_settings(duplicate, template)
    record["created_actor_path"] = _path(duplicate)
    _write_json(record_path, record)
    got_bounds = _bounds(duplicate)
    wanted = plan["target_box"]
    if any(abs(got_bounds["origin"][i] - wanted["center"][i]) > 2.0 or
           abs(got_bounds["extent"][i] - wanted["extent"][i]) > 5.0 for i in range(3)):
        raise Refused("BOUNDS_READBACK|got=%s|want=%s|NOTHING_SAVED_DONT_SAVE_RESTART" %
                      (json.dumps(got_bounds), json.dumps(wanted)))
    if (_snapshot_settings(duplicate) != plan["template_settings"] or
            bool(_prop(duplicate, "unbound", True)) or not bool(_prop(duplicate, "enabled", False)) or
            abs(float(_prop(duplicate, "blend_weight", 0.0)) - 1.0) > 1e-6 or
            abs(float(_prop(duplicate, "priority", 0.0)) - plan["priority"]) > 1e-4):
        raise Refused("PROPERTY_READBACK|NOTHING_SAVED_DONT_SAVE_RESTART")
    final = _save_level_only()
    record["applied"] = True
    record["post_save_census"] = final
    _write_json(record_path, record)
    unreal.log("%s_APPLY_OK|run=%s|actor=%s|template=%s|priority=%.3f|backup=%s|saved=%s|klara_saved=0|census=%s" %
               (MARK, run, record["created_actor_path"], plan["template_label"], plan["priority"], backup,
                WORLD, json.dumps(final)))


if unreal is not None:
    try:
        main()
    except Exception as exc:
        unreal.log_error("%s_FAILED|%r" % (MARK, exc))
        raise
