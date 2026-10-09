"""Clear P01's obsolete float trough and the lamp housings in the old cloth collider set.

Modes come from ``p01_lip_clear_args.json`` and require the exact confirmation
``<MODE> LIPCLEAR``.  APPLY disables the two real Show attachments that produced
the only live housings in the historical 16-entry collider list, turns
Structure 01 Portal.bFloatTrough off, materializes Passage 01, refits Structure
01, and saves only the Show plus the vertical-slice level.  REVERT restores the
recorded attachment enabled states and portal flag.

Identification, with proof tier:

* declaration-proven: ``GatherFixturePlacements`` consumes enabled,
  station-anchored Show Light attachments and ``BuildFixtures`` creates one
  StructureFixtures ISM body per placement
  (InfinityStageStructureActor.cpp:136-179,1920-1987).
* declaration-proven: ``Docs/StageFrontColliders_2026-09-28.json`` names 16
  housings: two ``Station 1 float`` housings plus 14 enabled ``Lip`` housings.
  ``make_stage_front_colliders.py`` maps the station pair to sources
  (310,+/-710,25), and says the lip row is what the never-applied lip-float tool
  *will* place (lines 86-105).
* declaration-proven: the lip plan authors 16 attachments but its fixed wear
  seed leaves two dark; its apply would have written a revert record before any
  mutation (p01_lip_floats_plan_readonly.py:23-44,203-229;
  p01_lip_floats_apply.py:197-214).  This tool refuses if that record or any lip
  attachment exists.
* inferred, guarded live: therefore 14 collider entries are prediction-only,
  while the two real housings belong to ``P01 Wing 001 Float L/R``.  Before a
  write, this tool proves those two attachment anchors are at the declared
  source positions and proves exactly two fixture ISM bounds centres match the
  collider centres.  Any disagreement is a refusal, not a guess.

Every mutating run writes and fsyncs a record and makes a verified
``Backups/PreLipClear[-Revert]-<run>`` snapshot of the Show and level before the
first Unreal mutation.  The structure count guard permits only the target's
portal_piece_count and fixture_body_count to change, by exactly one trough
piece and two real housings.  All six structures must otherwise remain exact.
"""
import datetime
import hashlib
import json
import math
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness imports the pure guard functions.
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
ARGS_PATH = os.path.join(HERE, "p01_lip_clear_args.json")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
TARGET_CUE = "P01 Wing 001"
TARGET_ATTACHMENTS = ("P01 Wing 001 Float L", "P01 Wing 001 Float R")
TARGET_SOURCES = {
    "P01 Wing 001 Float L": (310.0, -710.0, 25.0),
    "P01 Wing 001 Float R": (310.0, 710.0, 25.0),
}
TARGET_HOUSING_CENTRES = ((298.8, -729.4, 23.0), (298.8, 729.4, 23.0))
LIP_LABEL_RE = re.compile(r"^P01 Wing \d{3} Lip \d{2}$")
RUN_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
MODES = ("DRY", "APPLY", "REVERT")
COUNTS = (
    "station_count", "cross_beam_count", "rail_segment_count", "board_count",
    "slot_count", "cloth_count", "fixture_body_count", "hanging_line_count",
    "portal_piece_count",
)
LIGHT_FIELDS = (
    "type", "intensity_units", "intensity", "color", "use_temperature",
    "temperature_kelvin", "attenuation_radius_cm", "inner_cone_angle_degrees",
    "outer_cone_angle_degrees", "cast_shadows", "cast_volumetric_shadow",
    "volumetric_scattering_intensity", "light_function_material",
)
HISTORICAL_COLLIDER_NAMES = (
    "Station 1 float L housing", "Station 1 float R housing",
    "Lip 01 housing", "Lip 02 housing", "Lip 03 housing", "Lip 04 housing",
    "Lip 05 housing", "Lip 07 housing", "Lip 08 housing", "Lip 09 housing",
    "Lip 10 housing", "Lip 11 housing", "Lip 12 housing", "Lip 13 housing",
    "Lip 14 housing", "Lip 15 housing",
)


class LipClearError(RuntimeError):
    pass


def parse_args(raw):
    if not isinstance(raw, dict):
        raise LipClearError("ARGS|expected a JSON object")
    allowed = {"mode", "confirm", "run_id", "apply_run"}
    extra = sorted(set(raw) - allowed)
    if extra:
        raise LipClearError("ARGS_UNKNOWN|%s" % extra)
    mode = str(raw.get("mode") or "").upper()
    if mode not in MODES:
        raise LipClearError("MODE|need DRY, APPLY or REVERT")
    want = "%s LIPCLEAR" % mode
    if raw.get("confirm") != want:
        raise LipClearError("CONFIRM|want %r" % want)
    run_id = str(raw.get("run_id") or "")
    if not RUN_RE.fullmatch(run_id):
        raise LipClearError("RUN_ID|need explicit [A-Za-z0-9_-]{1,80}")
    apply_run = str(raw.get("apply_run") or "")
    if mode == "REVERT":
        if not RUN_RE.fullmatch(apply_run):
            raise LipClearError("APPLY_RUN|REVERT needs the APPLY run_id")
        if apply_run == run_id:
            raise LipClearError("APPLY_RUN|REVERT needs its own run_id")
    elif apply_run:
        raise LipClearError("APPLY_RUN|only REVERT accepts apply_run")
    return {"mode": mode, "confirm": want, "run_id": run_id, "apply_run": apply_run}


def classify_historical(live_labels, lip_record_exists):
    labels = set(live_labels)
    missing = sorted(set(TARGET_ATTACHMENTS) - labels)
    lips = sorted(label for label in labels if LIP_LABEL_RE.fullmatch(label))
    problems = []
    if len(HISTORICAL_COLLIDER_NAMES) != 16:
        problems.append("COLLIDER_DECLARATION|expected 16 names")
    if missing:
        problems.append("REAL_ATTACHMENTS_MISSING|%s" % missing)
    if lips:
        problems.append("LIP_ATTACHMENTS_EXIST|%s" % lips)
    if lip_record_exists:
        problems.append("LIP_RECORD_EXISTS|offline premise no longer true")
    return {
        "historical": len(HISTORICAL_COLLIDER_NAMES),
        "real": len(TARGET_ATTACHMENTS) - len(missing),
        "prediction_only": 14 if not lips and not lip_record_exists else None,
        "lip_labels": lips,
        "problems": problems,
    }


def expected_counts(before, target_label, mode):
    direction = -1 if mode == "APPLY" else 1
    out = json.loads(json.dumps(before))
    out[target_label]["portal_piece_count"] += direction
    out[target_label]["fixture_body_count"] += 2 * direction
    return out


def count_problems(before, after, target_label, mode):
    want = expected_counts(before, target_label, mode)
    problems = []
    if set(after) != set(want):
        problems.append("STRUCTURE_LABELS|%s -> %s" % (sorted(before), sorted(after)))
        return problems
    for label in sorted(want):
        for key in ("current",) + COUNTS:
            if after[label].get(key) != want[label].get(key):
                problems.append("COUNT|%s|%s|got=%s|want=%s" %
                                (label, key, after[label].get(key), want[label].get(key)))
        if not after[label].get("current"):
            problems.append("NOT_CURRENT|%s" % label)
    return problems


def transition_problems(before, after, mode):
    applied = mode == "APPLY"
    want_portal = not applied
    want_enabled = not applied
    want_trough = 0 if applied else 1
    want_housings = 0 if applied else 2
    problems = []
    if after.get("portal_float_trough") is not want_portal:
        problems.append("PORTAL_READBACK|got=%s|want=%s" %
                        (after.get("portal_float_trough"), want_portal))
    bad_enabled = {k: v for k, v in after.get("target_enabled", {}).items() if v is not want_enabled}
    if set(after.get("target_enabled", {})) != set(TARGET_ATTACHMENTS) or bad_enabled:
        problems.append("ATTACHMENT_READBACK|%s|want=%s" %
                        (after.get("target_enabled"), want_enabled))
    if after.get("trough_instances") != want_trough:
        problems.append("TROUGH_INSTANCES|got=%s|want=%s" %
                        (after.get("trough_instances"), want_trough))
    if after.get("matched_housing_instances") != want_housings:
        problems.append("HOUSING_INSTANCES|got=%s|want=%s" %
                        (after.get("matched_housing_instances"), want_housings))
    expected_attachments = json.loads(json.dumps(before.get("cue_attachments", [])))
    for row in expected_attachments:
        if row.get("label") in TARGET_ATTACHMENTS:
            row["enabled"] = want_enabled
    if after.get("cue_attachments") != expected_attachments:
        problems.append("CUE_FINGERPRINT|non-target data changed")
    return problems


def dirty_problems(census, stage):
    want = {"content": [], "maps": []}
    if stage == "pre_save":
        want = {"content": [SHOW], "maps": [WORLD]}
    if census != want:
        return ["DIRTY_%s|got=%s|want=%s" % (stage.upper(), census, want)]
    return []


def matched_centres(centres, expected=TARGET_HOUSING_CENTRES, tolerance_cm=1.0):
    used = set()
    matches = []
    for want in expected:
        candidates = []
        for index, got in enumerate(centres):
            distance = math.sqrt(sum((float(got[i]) - float(want[i])) ** 2 for i in range(3)))
            if distance <= tolerance_cm:
                candidates.append((index, distance))
        if len(candidates) != 1 or candidates[0][0] in used:
            return []
        used.add(candidates[0][0])
        matches.append({"index": candidates[0][0], "distance_cm": round(candidates[0][1], 4)})
    return matches


def stop(run_id, message):
    full = "P01_LIP_CLEAR_FAILED|run=%s|%s" % (run_id, message)
    if unreal is not None:
        unreal.log_error(full)
    raise LipClearError(full)


def package_name(package):
    text = str(package)
    return text.split("'")[1].split(".")[0] if "'" in text else text


def dirty_census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(package_name(p) for p in lib.get_dirty_content_packages()),
        "maps": sorted(package_name(p) for p in lib.get_dirty_map_packages()),
    }


def guid_text(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def plain(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    if isinstance(value, unreal.Color):
        return [value.r, value.g, value.b, value.a]
    if isinstance(value, unreal.LinearColor):
        return [round(value.r, 6), round(value.g, 6), round(value.b, 6), round(value.a, 6)]
    if isinstance(value, unreal.Transform):
        rot = value.rotation.rotator()
        return [round(v, 5) for v in (
            value.translation.x, value.translation.y, value.translation.z,
            rot.roll, rot.pitch, rot.yaw,
            value.scale3d.x, value.scale3d.y, value.scale3d.z,
        )]
    if hasattr(value, "get_path_name"):
        return value.get_path_name()
    return str(value)


def attachment_snapshot(attachment):
    lighting = attachment.get_editor_property("lighting")
    return {
        "guid": guid_text(attachment.get_editor_property("attachment_guid")),
        "label": str(attachment.get_editor_property("label")),
        "kind": str(attachment.get_editor_property("kind")),
        "anchor": str(attachment.get_editor_property("anchor")),
        "enabled": bool(attachment.get_editor_property("enabled")),
        "relative_transform": plain(attachment.get_editor_property("relative_transform")),
        "lighting": {name: plain(lighting.get_editor_property(name)) for name in LIGHT_FIELDS},
    }


def structure_counts(structures):
    return {
        actor.get_actor_label(): {
            "current": bool(actor.is_structure_current()),
            **{name: int(actor.get_editor_property(name)) for name in COUNTS},
        }
        for actor in structures
    }


def component_boxes(component):
    mesh = component.get_editor_property("static_mesh")
    if mesh is None:
        return []
    bounds = mesh.get_bounding_box()
    boxes = []
    for index in range(component.get_instance_count()):
        transform = component.get_instance_transform(index, True)
        points = [
            unreal.MathLibrary.transform_location(transform, unreal.Vector(x, y, z))
            for x in (bounds.min.x, bounds.max.x)
            for y in (bounds.min.y, bounds.max.y)
            for z in (bounds.min.z, bounds.max.z)
        ]
        boxes.append(points)
    return boxes


def component_has_tag(component, tag):
    return tag in [str(value) for value in component.get_editor_property("component_tags")]


def fixture_centres(structure):
    centres = []
    for component in structure.get_editor_property("managed_components"):
        if not component or not component_has_tag(component, "InfinityStage.Structure.Fixtures"):
            continue
        for points in component_boxes(component):
            centres.append(tuple(round(sum(getattr(p, axis) for p in points) / len(points), 4)
                                 for axis in ("x", "y", "z")))
    return centres


def trough_instances(structure):
    portal = structure.get_editor_property("portal")
    height = float(portal.get_editor_property("trough_height_cm"))
    found = 0
    for component in structure.get_editor_property("managed_components"):
        if not component or not component_has_tag(component, "InfinityStage.Structure.Portal"):
            continue
        for points in component_boxes(component):
            z_span = max(p.z for p in points) - min(p.z for p in points)
            xy_span = math.hypot(max(p.x for p in points) - min(p.x for p in points),
                                 max(p.y for p in points) - min(p.y for p in points))
            if abs(z_span - height) < 3.0 and xy_span > 1000.0:
                found += 1
    return found


def find_context(run_id):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != WORLD:
        stop(run_id, "WRONG_WORLD")
    if editor.get_game_world() is not None:
        stop(run_id, "PIE_ACTIVE")
    initial_dirty = dirty_census()
    problems = dirty_problems(initial_dirty, "initial")
    if problems:
        stop(run_id, problems[0])
    transient_aware = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    stray = sorted(a.get_actor_label() for a in transient_aware if a.get_actor_label().startswith("ZZ_"))
    if stray:
        stop(run_id, "STRAY_ACTORS|%s" % stray)

    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = subsystem.get_all_level_actors()
    passages = [a for a in actors if isinstance(a, unreal.InfinityStagePassageActor)
                and a.get_actor_label().startswith("Passage 01")]
    structures = sorted((a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)),
                        key=lambda a: a.get_actor_label())
    if len(passages) != 1:
        stop(run_id, "PASSAGE_01_COUNT|%d" % len(passages))
    if len(structures) != 6:
        stop(run_id, "STRUCTURE_COUNT|%d" % len(structures))
    targets = [a for a in structures if a.get_editor_property("passage") == passages[0]]
    if len(targets) != 1:
        stop(run_id, "STRUCTURE_01_COUNT|%d" % len(targets))
    show = unreal.EditorAssetLibrary.load_asset(SHOW)
    if show is None:
        stop(run_id, "SHOW_MISSING")
    cues = list(show.get_editor_property("cues"))
    cue_hits = [(index, cue) for index, cue in enumerate(cues)
                if str(cue.get_editor_property("label")) == TARGET_CUE]
    if len(cue_hits) != 1:
        stop(run_id, "TARGET_CUE_COUNT|%d" % len(cue_hits))
    return {
        "editor": editor, "subsystem": subsystem, "world": world,
        "passage": passages[0], "structures": structures, "structure": targets[0],
        "show": show, "cues": cues, "cue_index": cue_hits[0][0], "cue": cue_hits[0][1],
    }


def collect_state(context, lip_record):
    # FInfinityShowCue is a value struct: refresh it from the Show after every
    # write instead of retaining the pre-write Python copy in find_context().
    cue = list(context["show"].get_editor_property("cues"))[context["cue_index"]]
    attachments = list(cue.get_editor_property("wing_pair").get_editor_property("attachments"))
    by_label = {str(a.get_editor_property("label")): a for a in attachments}
    target_enabled = {label: bool(by_label[label].get_editor_property("enabled"))
                      for label in TARGET_ATTACHMENTS if label in by_label}
    target_world = {}
    for label in TARGET_ATTACHMENTS:
        attachment = by_label.get(label)
        if attachment is None:
            continue
        # The collider source is the light source, including RelativeTransform,
        # not merely the pair/station anchor.
        transform = context["passage"].get_attachment_world_transform(
            cue.get_editor_property("cue_guid"), attachment.get_editor_property("attachment_guid"))
        if not isinstance(transform, unreal.Transform):
            target_world[label] = None
        else:
            target_world[label] = [round(transform.translation.x, 3),
                                   round(transform.translation.y, 3),
                                   round(transform.translation.z, 3)]
    live_labels = [str(a.get_editor_property("label"))
                   for show_cue in context["show"].get_editor_property("cues")
                   for a in show_cue.get_editor_property("wing_pair").get_editor_property("attachments")]
    centres = fixture_centres(context["structure"])
    matches = matched_centres(centres)
    return {
        "dirty": dirty_census(),
        "structure_label": context["structure"].get_actor_label(),
        "structures": structure_counts(context["structures"]),
        "portal_float_trough": bool(context["structure"].get_editor_property("portal").get_editor_property("float_trough")),
        "target_enabled": target_enabled,
        "target_world": target_world,
        "cue_attachments": [attachment_snapshot(a) for a in attachments],
        "historical": classify_historical(live_labels, os.path.exists(lip_record)),
        "fixture_instances": len(centres),
        "matched_housing_instances": len(matches),
        "matched_housings": matches,
        "trough_instances": trough_instances(context["structure"]),
    }


def preflight_problems(state, mode):
    problems = list(state["historical"]["problems"])
    if any(not row["current"] for row in state["structures"].values()):
        problems.append("STRUCTURES_NOT_CURRENT")
    want_applied = mode == "REVERT"
    want_portal = not want_applied
    want_enabled = not want_applied
    want_trough = 0 if want_applied else 1
    want_housings = 0 if want_applied else 2
    if state["portal_float_trough"] is not want_portal:
        problems.append("PORTAL_PRESTATE|got=%s|want=%s" % (state["portal_float_trough"], want_portal))
    if set(state["target_enabled"]) != set(TARGET_ATTACHMENTS):
        problems.append("TARGET_ATTACHMENT_COUNT|%s" % state["target_enabled"])
    elif any(value is not want_enabled for value in state["target_enabled"].values()):
        problems.append("TARGET_ENABLED_PRESTATE|got=%s|want=%s" % (state["target_enabled"], want_enabled))
    for label, expected in TARGET_SOURCES.items():
        got = state["target_world"].get(label)
        if got is None or math.dist(got, expected) > 1.0:
            problems.append("TARGET_SOURCE|%s|got=%s|want=%s+/-1cm" % (label, got, expected))
    if state["trough_instances"] != want_trough:
        problems.append("TROUGH_PRESTATE|got=%s|want=%s" % (state["trough_instances"], want_trough))
    if state["matched_housing_instances"] != want_housings:
        problems.append("HOUSING_PRESTATE|got=%s|want=%s" %
                        (state["matched_housing_instances"], want_housings))
    return problems


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_verified(path, payload):
    if os.path.exists(path):
        raise LipClearError("RECORD_EXISTS|%s" % path)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    with open(path, encoding="utf-8") as handle:
        if json.load(handle) != payload:
            raise LipClearError("RECORD_READBACK|%s" % path)


def project_files(run_id):
    root = os.path.realpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    show_file = os.path.realpath(os.path.join(root, "Content", "InfinityStage", "Dev", "DA_InfinityStage_V1Show.uasset"))
    map_file = os.path.realpath(os.path.join(root, "Content", "InfinityStage", "Dev", "Maps",
                                             "L_InfinityStage_V1VerticalSlice.umap"))
    for path in (show_file, map_file):
        if os.path.commonpath((root, path)) != root or not os.path.isfile(path):
            stop(run_id, "SOURCE_FILE|%s" % path)
    return root, show_file, map_file


def backup_and_record(args, state, kind):
    run_id = args["run_id"]
    root, show_file, map_file = project_files(run_id)
    suffix = "PreLipClear" if kind == "APPLY" else "PreLipClearRevert"
    backup = os.path.join(root, "Backups", "%s-%s" % (suffix, run_id))
    record_name = "p01_lip_clear_record_%s.json" % run_id
    if kind == "REVERT":
        record_name = "p01_lip_clear_revert_record_%s.json" % run_id
    record_path = os.path.join(HERE, record_name)
    result_path = os.path.join(HERE, "p01_lip_clear_result_%s.json" % run_id)
    if os.path.exists(record_path):
        stop(run_id, "RECORD_EXISTS|%s" % record_path)
    if os.path.exists(result_path):
        stop(run_id, "RESULT_EXISTS|%s" % result_path)
    if os.path.exists(backup):
        stop(run_id, "BACKUP_EXISTS|%s" % backup)
    os.makedirs(backup)
    copied = []
    for source in (show_file, map_file):
        destination = os.path.join(backup, os.path.basename(source))
        shutil.copy2(source, destination)
        if sha256(source) != sha256(destination):
            stop(run_id, "BACKUP_HASH|%s" % source)
        copied.append({"source": source, "backup": destination, "sha256": sha256(source),
                       "bytes": os.path.getsize(source)})
    payload = {
        "schema": 1, "written_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode": kind, "run": run_id, "apply_run": args.get("apply_run") or None,
        "world": WORLD, "show": SHOW, "backup": backup, "files": copied, "before": state,
    }
    try:
        write_verified(record_path, payload)
    except LipClearError as exc:
        stop(run_id, str(exc))
    unreal.log("P01_LIP_CLEAR_RECORD_OK|run=%s|mode=%s|record=%s|backup=%s|files=2" %
               (run_id, kind, record_path, backup))
    return record_path, backup


def set_target_state(context, enabled, float_trough):
    cues = list(context["show"].get_editor_property("cues"))
    cue = cues[context["cue_index"]]
    pair = cue.get_editor_property("wing_pair")
    attachments = list(pair.get_editor_property("attachments"))
    changed = 0
    for attachment in attachments:
        if str(attachment.get_editor_property("label")) in TARGET_ATTACHMENTS:
            attachment.set_editor_property("enabled", enabled)
            changed += 1
    if changed != 2:
        raise LipClearError("TARGET_WRITE_COUNT|%d" % changed)
    context["show"].modify()
    pair.set_editor_property("attachments", attachments)
    cue.set_editor_property("wing_pair", pair)
    cues[context["cue_index"]] = cue
    context["show"].set_editor_property("cues", cues)

    context["structure"].modify()
    portal = context["structure"].get_editor_property("portal")
    portal.set_editor_property("float_trough", float_trough)
    context["structure"].set_editor_property("portal", portal)
    if not context["passage"].materialize_passage():
        raise LipClearError("PASSAGE_MATERIALIZE")
    if not context["structure"].materialize_structure():
        raise LipClearError("STRUCTURE_MATERIALIZE")


def save_named(context, run_id):
    if not unreal.EditorAssetLibrary.save_asset(SHOW, only_if_is_dirty=False):
        stop(run_id, "SHOW_SAVE_FAILED|backup and record exist")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        stop(run_id, "LEVEL_SAVE_FAILED|Show saved; restore from record/backup")


def load_apply_record(run_id, apply_run):
    path = os.path.join(HERE, "p01_lip_clear_record_%s.json" % apply_run)
    if not os.path.isfile(path):
        stop(run_id, "APPLY_RECORD_MISSING|%s" % path)
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("mode") != "APPLY" or record.get("run") != apply_run:
        stop(run_id, "APPLY_RECORD_INVALID|%s" % path)
    return path, record


def write_result(args, record_path, backup, before, after):
    result_path = os.path.join(HERE, "p01_lip_clear_result_%s.json" % args["run_id"])
    payload = {
        "schema": 1, "written_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode": args["mode"], "run": args["run_id"], "apply_run": args.get("apply_run") or None,
        "record": record_path, "backup": backup, "before": before, "saved_readback": after,
    }
    write_verified(result_path, payload)
    return result_path


def main():
    if unreal is None:
        raise RuntimeError("p01_lip_clear.py must run inside Unreal; use test_p01_lip_clear.py offline")
    raw = json.load(open(ARGS_PATH, encoding="utf-8")) if os.path.isfile(ARGS_PATH) else {}
    tentative_run = str(raw.get("run_id") or "UNSET") if isinstance(raw, dict) else "UNSET"
    try:
        args = parse_args(raw)
    except LipClearError as exc:
        stop(tentative_run, str(exc))
    run_id = args["run_id"]
    lip_record = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexStructure", "p01_lip_floats_revert_record.json")
    context = find_context(run_id)
    before = collect_state(context, lip_record)
    problems = preflight_problems(before, args["mode"])
    if problems:
        stop(run_id, "PREFLIGHT|%s" % problems)

    unreal.log("P01_LIP_CLEAR_CENSUS|run=%s|mode=%s|historical=16|real=2|prediction_only=14"
               "|trough=%d|fixture_total=%d|matched_housings=%d|structures=%s|dirty=%s" %
               (run_id, args["mode"], before["trough_instances"], before["fixture_instances"],
                before["matched_housing_instances"], json.dumps(before["structures"], sort_keys=True),
                json.dumps(before["dirty"], sort_keys=True)))

    if args["mode"] == "DRY":
        dry_path = os.path.join(HERE, "p01_lip_clear_dry_%s.json" % run_id)
        write_verified(dry_path, {"schema": 1, "mode": "DRY", "run": run_id, "census": before})
        after_dirty = dirty_census()
        problems = dirty_problems(after_dirty, "post_save")
        if problems:
            stop(run_id, problems[0])
        unreal.log("P01_LIP_CLEAR_DRY_OK|run=%s|historical=16|real=2|prediction_only=14"
                   "|trough=1|matched_housings=2|mutated=0|dirty_after=0+0|report=%s" %
                   (run_id, dry_path))
        return

    apply_record = None
    if args["mode"] == "REVERT":
        _, apply_record = load_apply_record(run_id, args["apply_run"])
        recorded_after = expected_counts(apply_record["before"]["structures"],
                                         apply_record["before"]["structure_label"], "APPLY")
        if before["structures"] != recorded_after:
            stop(run_id, "REVERT_DRIFT|structure counts differ from APPLY post-state")

    record_path, backup = backup_and_record(args, before, args["mode"])
    enable = args["mode"] == "REVERT"
    try:
        set_target_state(context, enable, enable)
    except Exception as exc:
        stop(run_id, "MUTATION|%s|NOTHING SAVED; Don't-Save restart" % exc)

    after = collect_state(context, lip_record)
    problems = count_problems(before["structures"], after["structures"],
                              before["structure_label"], args["mode"])
    problems += transition_problems(before, after, args["mode"])
    problems += dirty_problems(after["dirty"], "pre_save")
    if problems:
        stop(run_id, "VERIFY_BEFORE_SAVE|%s|NOTHING SAVED; Don't-Save restart" % problems)

    save_named(context, run_id)
    saved = collect_state(context, lip_record)
    problems = count_problems(before["structures"], saved["structures"],
                              before["structure_label"], args["mode"])
    problems += transition_problems(before, saved, args["mode"])
    problems += dirty_problems(saved["dirty"], "post_save")
    if problems:
        stop(run_id, "SAVED_READBACK|%s|record=%s|backup=%s" % (problems, record_path, backup))
    result_path = write_result(args, record_path, backup, before, saved)
    portal_delta = saved["structures"][before["structure_label"]]["portal_piece_count"] - before["structures"][before["structure_label"]]["portal_piece_count"]
    fixture_delta = saved["structures"][before["structure_label"]]["fixture_body_count"] - before["structures"][before["structure_label"]]["fixture_body_count"]
    unreal.log("P01_LIP_CLEAR_%s_OK|run=%s|historical=16|real=2|prediction_only=14"
               "|portal_delta=%+d|fixture_delta=%+d|trough=%d|matched_housings=%d"
               "|show_saved=1|level_saved=1|dirty_after=0+0|record=%s|backup=%s|result=%s" %
               (args["mode"], run_id, portal_delta, fixture_delta, saved["trough_instances"],
                saved["matched_housing_instances"], record_path, backup, result_path))


if not globals().get("P01_LIP_CLEAR_IMPORT_ONLY"):
    main()
