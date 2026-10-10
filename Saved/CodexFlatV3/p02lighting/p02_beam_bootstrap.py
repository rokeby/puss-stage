"""Job 105: create the four P02 BeamLook vessels required by PASSAGELIGHT.

Offline-authored; the conductor runs this later.  DRY/APPLY/REVERT only.
The P01 atmosphere APPLY record selects B03/B07/B12/B20.  Their live actors
must retain the record-owned identity/material, then their current
P01-passage-relative state is cloned onto four new P02-owned StaticMeshActors.
No Show data is changed.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import re

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
ARGS_PATH = os.path.join(HERE, "p02_beam_bootstrap_args.json")
RECORD_PATH = os.path.join(HERE, "p02_beam_bootstrap_record.json")
LIGHTING_RECORD_PATH = os.path.join(HERE, "passage_lighting_record.json")
SOURCE_RECORD_REL = os.path.join("CodexConductor", "Effects_20261007", "p01_atmos_record.json")
SOURCE_RECORD_SHA256 = "50acccad802aeb0070768449bbc8174c641e7a40fe1f3ea2709b134a96f2eaed"
MARK = "P02BEAMBOOTSTRAP"
SOURCE_TAG = "P01ATMOS"
TARGET_TAG = "P02ATMOS"
BEAM_TAG = "InfinityStage.BeamLook"
OWNER_TAG = MARK
SOURCE_PASSAGE = 1
TARGET_PASSAGE = 2
DEFAULT_ORDINALS = [3, 7, 12, 20]
FLOAT_TOL = 1.0e-3


def _load_common():
    path = os.path.join(HERE, "_fx_authoring_common.py")
    spec = importlib.util.spec_from_file_location("_p02beam_common", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load_common()


class BeamBootstrapError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise BeamBootstrapError(str(message))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def state_hash(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def check_args(raw):
    require(isinstance(raw, dict), "ARGS_NOT_OBJECT")
    allowed = {"mode", "confirm", "expected_plan_sha256", "ordinals", "max_actors",
               "expected_source_record_sha256"}
    require(not (set(raw) - allowed), "ARGS_UNKNOWN|" + ",".join(sorted(set(raw) - allowed)))
    out = {
        "mode": "DRY", "confirm": "", "expected_plan_sha256": "",
        "ordinals": list(DEFAULT_ORDINALS), "max_actors": 4,
        "expected_source_record_sha256": SOURCE_RECORD_SHA256,
    }
    out.update(copy.deepcopy(raw))
    out["mode"] = str(out["mode"]).upper()
    require(out["mode"] in ("DRY", "APPLY", "REVERT"), "MODE_INVALID|" + out["mode"])
    if out["mode"] != "DRY":
        require(out["confirm"] == "%s %s" % (out["mode"], MARK),
                "CONFIRM_MISSING|want=%s %s" % (out["mode"], MARK))
    if out["mode"] == "APPLY":
        require(re.fullmatch(r"[0-9a-f]{64}", str(out["expected_plan_sha256"])),
                "EXPECTED_PLAN_SHA256_REQUIRED")
    require(out["ordinals"] == DEFAULT_ORDINALS,
            "ORDINALS_FIXED|want=%s|got=%s" % (DEFAULT_ORDINALS, out["ordinals"]))
    require(out["max_actors"] == 4, "MAX_ACTORS_FIXED|want=4")
    require(out["expected_source_record_sha256"] == SOURCE_RECORD_SHA256,
            "SOURCE_RECORD_SHA_ARG_DRIFT")
    return out


def source_record_path():
    require(unreal is not None, "UNREAL_REQUIRED")
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    return os.path.normpath(os.path.join(root, SOURCE_RECORD_REL))


def record_specs(record, ordinals):
    require(record.get("passage") == "P01", "SOURCE_RECORD_PASSAGE")
    require(record.get("status") == "saved_readback_verified", "SOURCE_RECORD_STATUS")
    noise = record.get("plan", {}).get("noise", [])
    by_ordinal = {}
    for row in noise:
        hit = re.fullmatch(r"P01 BeamLook Noise B(\d+)", str(row.get("label", "")))
        if hit:
            by_ordinal[int(hit.group(1))] = row
    missing = [n for n in ordinals if n not in by_ordinal]
    require(not missing, "SOURCE_RECORD_ROWS_MISSING|" + canonical(missing))
    rows = []
    for ordinal in ordinals:
        source = copy.deepcopy(by_ordinal[ordinal])
        require(source.get("kind") == "noise", "SOURCE_KIND|B%02d" % ordinal)
        require(source.get("tags") == [BEAM_TAG, SOURCE_TAG], "SOURCE_TAGS|B%02d" % ordinal)
        require(source.get("material") == "/Game/InfinityStage/Lighting/BeamLook/M_Vol_BeamNoise",
                "SOURCE_MATERIAL|B%02d" % ordinal)
        rows.append({
            "ordinal": ordinal,
            "source_label": source["label"],
            "target_label": "P02 BeamLook Noise B%02d" % ordinal,
            "source_record_spec": source,
            "target_tags": [BEAM_TAG, TARGET_TAG, OWNER_TAG],
        })
    return rows


def target_inventory_problems(inventory, planned_rows):
    labels = {row["target_label"] for row in planned_rows}
    problems = []
    for row in inventory:
        tags = set(row.get("tags", []))
        if row.get("label") in labels or TARGET_TAG in tags or OWNER_TAG in tags:
            problems.append({"label": row.get("label"), "tags": sorted(tags), "id": row.get("id")})
    return sorted(problems, key=lambda row: (str(row["label"]), str(row["id"])))


def _tags(actor):
    return sorted(str(x) for x in actor.tags)


def _asset(value):
    return C.asset_id(value)


def _plain_transform(transform):
    rotation = transform.rotation
    return {
        "location": [float(transform.translation.x), float(transform.translation.y), float(transform.translation.z)],
        "rotation_xyzw": [float(rotation.x), float(rotation.y), float(rotation.z), float(rotation.w)],
        "scale": [float(transform.scale3d.x), float(transform.scale3d.y), float(transform.scale3d.z)],
    }


def _actor_plain(actor, passage):
    rel = unreal.MathLibrary.make_relative_transform(actor.get_actor_transform(), passage.get_actor_transform())
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    return {
        "id": str(actor.get_path_name()), "label": actor.get_actor_label(), "tags": _tags(actor),
        "class": str(actor.get_class().get_path_name()), "relative_transform": _plain_transform(rel),
        "attached_to_passage": actor.get_attach_parent_actor() == passage,
        "hidden_game": bool(actor.get_editor_property("hidden")),
        "collision": bool(actor.get_actor_enable_collision()),
        "static_mesh": _asset(comp.get_editor_property("static_mesh")) if comp else None,
        "materials": [_asset(x) for x in comp.get_materials()] if comp else [],
        "visible": bool(comp.is_visible()) if comp else None,
        "cast_shadow": bool(comp.get_editor_property("cast_shadow")) if comp else None,
        "mobility": str(comp.get_editor_property("mobility")) if comp else None,
    }


def _all_actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _inventory():
    return [{"id": str(a.get_path_name()), "label": a.get_actor_label(), "tags": _tags(a)} for a in _all_actors()]


def _find_unique(label, required_tags):
    hits = [a for a in _all_actors() if a.get_actor_label() == label and set(required_tags).issubset(set(_tags(a)))]
    require(len(hits) == 1, "ACTOR_RESOLVE|label=%s|count=%d" % (label, len(hits)))
    return hits[0]


def _near(a, b, tolerance=FLOAT_TOL):
    return abs(float(a) - float(b)) <= tolerance


def _verify_source_record(actor, spec):
    """Verify stable record ownership; report world drift without rejecting parent motion."""
    loc = actor.get_actor_location()
    rot = actor.get_actor_rotation()
    scale = actor.get_actor_scale3d()
    got_loc = [float(loc.x), float(loc.y), float(loc.z)]
    got_rot = {"pitch": float(rot.pitch), "roll": float(rot.roll), "yaw": float(rot.yaw)}
    require(set(spec["tags"]).issubset(set(_tags(actor))), "SOURCE_RECORD_TAG_DRIFT|" + spec["label"])
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    require(comp is not None, "SOURCE_STATIC_MESH_COMPONENT_MISSING|" + spec["label"])
    require(_asset(comp.get_material(0)) == spec["material"], "SOURCE_RECORD_MATERIAL_DRIFT|" + spec["label"])
    return {
        "record_world": {"location": spec["loc"], "rotation": spec["rot"], "scale": spec["scale"]},
        "live_world": {"location": got_loc, "rotation": got_rot,
                       "scale": [float(scale.x), float(scale.y), float(scale.z)]},
        "world_matches_record": (
            all(_near(x, y, 0.02) for x, y in zip(got_loc, spec["loc"]))
            and all(_near(got_rot[k], spec["rot"][k], 0.02) for k in ("pitch", "roll", "yaw"))
            and all(_near(x, y, 0.001) for x, y in zip([scale.x, scale.y, scale.z], spec["scale"]))
        ),
        "note": "world drift is reported, not rejected; attached parent motion can change world while relative stays valid",
    }


def _plan(show, args):
    path = source_record_path()
    require(os.path.isfile(path), "SOURCE_RECORD_MISSING|" + path)
    digest = C.sha256(path)
    require(digest == args["expected_source_record_sha256"],
            "SOURCE_RECORD_SHA_DRIFT|got=%s|want=%s" % (digest, args["expected_source_record_sha256"]))
    record = C.load_json(path)
    rows = record_specs(record, args["ordinals"])
    source_passage = C.find_passage_actor(unreal, show, SOURCE_PASSAGE)
    target_passage = C.find_passage_actor(unreal, show, TARGET_PASSAGE)
    problems = target_inventory_problems(_inventory(), rows)
    require(not problems, "TARGET_BEAMS_ALREADY_EXIST|" + canonical(problems))
    for row in rows:
        source_actor = _find_unique(row["source_label"], [BEAM_TAG, SOURCE_TAG])
        record_comparison = _verify_source_record(source_actor, row["source_record_spec"])
        source_plain = _actor_plain(source_actor, source_passage)
        require(source_plain["attached_to_passage"], "SOURCE_NOT_ATTACHED|" + row["source_label"])
        desired = copy.deepcopy(source_plain)
        desired.update({"id": None, "label": row["target_label"], "tags": row["target_tags"],
                        "attached_to_passage": True})
        row["source_live"] = source_plain
        row["source_record_world_comparison"] = record_comparison
        row["target_desired"] = desired
    plan = {"source_record": path, "source_record_sha256": digest, "source_record_run": record.get("run"),
            "source_passage": "P01", "target_passage": "P02", "count": len(rows), "rows": rows}
    plan["plan_sha256"] = state_hash(plan)
    return plan, source_passage, target_passage


def _make_transform(row):
    transform = unreal.Transform()
    transform.set_editor_property("translation", unreal.Vector(*row["location"]))
    transform.set_editor_property("rotation", unreal.Quat(*row["rotation_xyzw"]))
    transform.set_editor_property("scale3d", unreal.Vector(*row["scale"]))
    return transform


def _spawn(row, target_passage):
    desired = row["target_desired"]
    world = unreal.MathLibrary.compose_transforms(_make_transform(desired["relative_transform"]),
                                                   target_passage.get_actor_transform())
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        unreal.StaticMeshActor, world.translation, world.rotator())
    require(actor is not None, "SPAWN_FAILED|" + desired["label"])
    actor.modify()
    actor.set_actor_label(desired["label"], False)
    actor.set_editor_property("tags", [unreal.Name(t) for t in desired["tags"]])
    actor.set_actor_enable_collision(False)
    actor.set_actor_hidden_in_game(desired["hidden_game"])
    comp = actor.get_component_by_class(unreal.StaticMeshComponent)
    comp.modify()
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    actor.set_actor_transform(world, False, True)
    mesh = unreal.load_asset(desired["static_mesh"])
    require(mesh is not None, "MESH_MISSING|" + str(desired["static_mesh"]))
    comp.set_static_mesh(mesh)
    for index, material_path in enumerate(desired["materials"]):
        material = unreal.load_asset(material_path)
        require(material is not None, "MATERIAL_MISSING|" + str(material_path))
        comp.set_material(index, material)
    comp.set_visibility(desired["visible"], True)
    comp.set_cast_shadow(desired["cast_shadow"])
    actor.attach_to_actor(target_passage, "", unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    require(actor.get_attach_parent_actor() == target_passage, "ATTACH_FAILED|" + desired["label"])
    return actor


def _owned_rows(target_passage, planned):
    rows = []
    labels = {r["target_label"] for r in planned}
    for actor in _all_actors():
        if actor.get_actor_label() in labels and {BEAM_TAG, TARGET_TAG, OWNER_TAG}.issubset(set(_tags(actor))):
            rows.append(_actor_plain(actor, target_passage))
    return sorted(rows, key=lambda row: row["label"])


def _state_differences(before, after, path=""):
    out = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            out.extend(_state_differences(before.get(key), after.get(key), path + "." + key))
    elif isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        for i, (left, right) in enumerate(zip(before, after)):
            out.extend(_state_differences(left, right, "%s[%d]" % (path, i)))
    elif isinstance(before, (int, float)) and isinstance(after, (int, float)) and not isinstance(before, bool):
        if not _near(before, after, 1.0e-3):
            out.append({"path": path, "before": before, "after": after})
    elif before != after:
        out.append({"path": path, "before": before, "after": after})
    return out


def _verify_rows(actual, plan):
    expected = [copy.deepcopy(row["target_desired"]) for row in plan["rows"]]
    for row in expected:
        row.pop("id", None)
    stripped = []
    for row in actual:
        row = copy.deepcopy(row)
        row.pop("id", None)
        stripped.append(row)
    diff = _state_differences(expected, stripped)
    require(not diff, "TARGET_READBACK_MISMATCH|" + canonical(diff[:12]))


def _save_level_only():
    census = C.dirty_census(unreal)
    expected = {"content": [], "maps": [C.EXPECTED_WORLD]}
    require(census == expected, "DIRTY_SCOPE|got=%s|want=%s" % (canonical(census), canonical(expected)))
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
    C.require_clean(unreal, "POST_SAVE")


def _report_path(mode, run):
    return os.path.join(HERE, "p02_beam_bootstrap_report_%s_%s.json" % (mode, run))


def _context():
    _editor, world = C.editor_context(unreal)
    clean = C.require_clean(unreal, "PRE_RUN")
    show = unreal.EditorAssetLibrary.load_asset(C.SHOW_PATH)
    require(show is not None, "SHOW_MISSING")
    return world, show, clean


def _revert(args, run, report, show):
    require(not os.path.exists(LIGHTING_RECORD_PATH),
            "ACTIVE_PASSAGELIGHT_RECORD|REVERT PASSAGELIGHT before bootstrap")
    require(os.path.isfile(RECORD_PATH), "REVERT_RECORD_MISSING")
    record = C.load_json(RECORD_PATH)
    require(record.get("status") == "saved_readback_verified", "REVERT_RECORD_STATUS")
    plan = record["plan"]
    target_passage = C.find_passage_actor(unreal, show, TARGET_PASSAGE)
    current = _owned_rows(target_passage, plan["rows"])
    _verify_rows(current, plan)
    backup = C.backup_packages(unreal, "PreP02BeamBootstrapRevert-", run, [C.EXPECTED_WORLD])
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for row in current:
        actor = _find_unique(row["label"], [BEAM_TAG, TARGET_TAG, OWNER_TAG])
        require(subsystem.destroy_actor(actor), "DESTROY_FAILED|" + row["label"])
    require(not _owned_rows(target_passage, plan["rows"]), "REVERT_ACTORS_REMAIN")
    _save_level_only()
    archived = C.archive_record(RECORD_PATH, run)
    report.update({"ok": True, "backup": backup, "record_archived": archived,
                   "destroyed": len(current), "dirty_after": C.dirty_census(unreal)})
    C.write_json(_report_path("REVERT", run), report)
    unreal.log("%s_REVERT_OK|run=%s|destroyed=%d|level_saved=1|readback=1|record=%s" %
               (MARK, run, len(current), archived))
    return report


def _run(args):
    require(unreal is not None, "UNREAL_REQUIRED")
    run = C.stamp_now()
    report = {"ok": False, "mode": args["mode"], "run": run, "args": args,
              "proof": "offline-authored; live results are measured only after conductor execution"}
    try:
        _world, show, dirty_before = _context()
        report["dirty_before"] = dirty_before
        if args["mode"] == "REVERT":
            return _revert(args, run, report, show)
        plan, _source_passage, target_passage = _plan(show, args)
        report["plan"] = plan
        if args["mode"] == "DRY":
            require(C.dirty_census(unreal) == dirty_before, "DRY_CHANGED_CENSUS")
            report.update({"ok": True, "mutated": False, "dirty_after": C.dirty_census(unreal)})
            C.write_json(_report_path("DRY", run), report)
            unreal.log("%s_DRY_OK|run=%s|count=%d|source_record_run=%s|plan_sha256=%s|mutated=0|census_equal=1" %
                       (MARK, run, plan["count"], plan["source_record_run"], plan["plan_sha256"]))
            return report
        require(args["expected_plan_sha256"] == plan["plan_sha256"],
                "PLAN_DRIFT|dry=%s|live=%s" % (args["expected_plan_sha256"], plan["plan_sha256"]))
        require(not os.path.exists(LIGHTING_RECORD_PATH),
                "ACTIVE_PASSAGELIGHT_RECORD|bootstrap must precede PASSAGELIGHT APPLY")
        require(not os.path.exists(RECORD_PATH), "ACTIVE_RECORD_EXISTS")
        backup = C.backup_packages(unreal, "PreP02BeamBootstrap-", run, [C.EXPECTED_WORLD])
        record = {"schema_version": 1, "status": "prepared", "run": run, "args": args,
                  "plan": plan, "backup": backup, "spawned": {}}
        C.write_json(RECORD_PATH, record, exclusive=True)
        try:
            for row in plan["rows"]:
                actor = _spawn(row, target_passage)
                record["spawned"][row["target_label"]] = str(actor.get_path_name())
                C.write_json(RECORD_PATH, record)
            actual = _owned_rows(target_passage, plan["rows"])
            _verify_rows(actual, plan)
        except Exception:
            subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            for actor in _all_actors():
                if OWNER_TAG in _tags(actor):
                    subsystem.destroy_actor(actor)
            record["status"] = "failed_rolled_back_in_memory"
            C.write_json(RECORD_PATH, record)
            os.rename(RECORD_PATH, RECORD_PATH + ".failed-" + run)
            raise
        record.update({"status": "mutated_verified", "readback_before_save": actual})
        C.write_json(RECORD_PATH, record)
        _save_level_only()
        saved = _owned_rows(target_passage, plan["rows"])
        _verify_rows(saved, plan)
        record.update({"status": "saved_readback_verified", "saved_readback": saved,
                       "saved_census": C.dirty_census(unreal)})
        C.write_json(RECORD_PATH, record)
        report.update({"ok": True, "backup": backup, "record": RECORD_PATH,
                       "created": len(saved), "dirty_after": C.dirty_census(unreal)})
        C.write_json(_report_path("APPLY", run), report)
        unreal.log("%s_APPLY_OK|run=%s|created=%d|level_saved=1|show_saved=0|readback=1|record=%s|NEXT=PASSAGELIGHT_DRY" %
                   (MARK, run, len(saved), RECORD_PATH))
        return report
    except Exception as error:
        report["error"] = "%s: %s" % (type(error).__name__, error)
        try:
            report["census_at_stop"] = C.dirty_census(unreal)
        except Exception:
            pass
        C.write_json(_report_path(args["mode"] + "_STOPPED", run), report)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|%s|census=%s|if dirty: Don't-Save restart" %
                         (MARK, run, args["mode"], report["error"], report.get("census_at_stop")))
        raise


def main(raw=None):
    if raw is None:
        raw = C.load_json(ARGS_PATH) if os.path.isfile(ARGS_PATH) else {}
    return _run(check_args(raw))


if unreal is not None and __name__ in ("__main__", "__p02_beam_bootstrap_runner__"):
    main(globals().get("P02_BEAM_BOOTSTRAP_ARGS"))
