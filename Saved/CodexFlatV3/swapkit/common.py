"""Shared guarded helpers for the passage-parameterised Flat V3 swap kit."""
import json
import math
import os
import sys

import unreal


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
CLEAN = {"content": [], "maps": []}
SAVED_ROOTS = [SHOW, WORLD]

PROJECT = os.path.normpath(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_dir()))
BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexFlatV3", "swapkit"))


def _project_path(value):
    value = str(value)
    return os.path.normpath(value if os.path.isabs(value) else os.path.join(PROJECT, value))


def config_path(explicit=None):
    value = explicit or globals().get("FLATV3_CONFIG") or os.environ.get("FLATV3_CONFIG")
    if not value and len(sys.argv) > 1 and str(sys.argv[1]).lower().endswith(".json"):
        value = sys.argv[1]
    if not value:
        raise RuntimeError("CONFIG_REQUIRED|set FLATV3_CONFIG to a run JSON")
    return _project_path(value)


def load_config(explicit=None):
    path = config_path(explicit)
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    required = {
        "schema_version", "slot", "run_id", "passage", "passage_label_prefix",
        "passage_actor_label_prefix", "mapping_file", "mapping_kind", "backup_path",
        "destination_root", "success_marker", "required_previous_marker",
    }
    missing = sorted(required - set(config))
    if missing:
        raise RuntimeError("CONFIG_KEYS_MISSING|" + json.dumps(missing))
    if int(config["schema_version"]) != 1:
        raise RuntimeError("CONFIG_SCHEMA_FAIL|actual=" + str(config["schema_version"]))
    slot = str(config["slot"])
    if not slot or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in slot):
        raise RuntimeError("CONFIG_SLOT_FAIL|actual=" + slot)
    if not str(config["passage_label_prefix"]).startswith(str(config["passage"]) + " Wing "):
        raise RuntimeError("CONFIG_PASSAGE_PREFIX_MISMATCH")
    known_failed = set(config.get("known_failed_assets", {}))
    excluded = set(config.get("excluded_new_meshes", []))
    included_failures = sorted(known_failed - excluded)
    if included_failures:
        raise RuntimeError("KNOWN_FAILED_ASSET_INCLUDED|" + json.dumps(included_failures))
    config = dict(config)
    config["_path"] = path
    config["mapping_file"] = _project_path(config["mapping_file"])
    config["backup_path"] = _project_path(config["backup_path"])
    return config


def marker(config, suffix):
    return "FLATV3_%s_%s" % (config["slot"], suffix)


def artifact(config, phase, run=None, failure=False):
    name = "swapkit_%s_%s%s.json" % (
        phase, run or config["run_id"], "_FAILURE" if failure else "")
    return os.path.join(BASE, name)


def write_json(config, phase, value, run=None, failure=False):
    path = artifact(config, phase, run=run, failure=failure)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def read_json(config, phase, run=None):
    path = artifact(config, phase, run=run)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def census():
    def names(packages):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in packages)
    return {
        "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def assert_context(config, clean=True):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    actual = world.get_outermost().get_name() if world else None
    if actual != WORLD:
        raise RuntimeError("WRONG_WORLD|expected=%s|actual=%s" % (WORLD, actual))
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE_OR_SIE_ACTIVE")
    current = census()
    if clean and current != CLEAN:
        raise RuntimeError("DIRTY_AT_SLOT_START|census=" + json.dumps(current, sort_keys=True))
    return editor, world


def asset_path(value):
    return None if value is None else str(value.get_path_name()).split(".", 1)[0]


def transform_plain(value):
    rotation = value.rotation.rotator()
    return {
        "location": [float(value.translation.x), float(value.translation.y), float(value.translation.z)],
        "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(value.scale3d.x), float(value.scale3d.y), float(value.scale3d.z)],
    }


def transform_from_plain(value):
    return unreal.Transform(
        location=unreal.Vector(*value["location"]),
        rotation=unreal.Rotator(
            roll=value["rotation"][0], pitch=value["rotation"][1], yaw=value["rotation"][2]),
        scale=unreal.Vector(*value["scale"]))


def panel_plain(panel):
    return {
        "mesh": asset_path(panel.get_editor_property("mesh")),
        "material_overrides": [asset_path(value) for value in panel.get_editor_property("material_overrides")],
        "local_transform": transform_plain(panel.get_editor_property("local_transform")),
        "facing_policy": str(panel.get_editor_property("facing_policy")),
        "flip_image_horizontally": bool(panel.get_editor_property("flip_image_horizontally")),
    }


def frame_value(value):
    return int(value.value) if hasattr(value, "value") else int(value)


def mechanism_plain(mechanism):
    return {
        "kind": str(mechanism.get_editor_property("kind")),
        "playback_mode": str(mechanism.get_editor_property("playback_mode")),
        "phase_origin": str(mechanism.get_editor_property("phase_origin")),
        "explicit_origin_frame": frame_value(mechanism.get_editor_property("explicit_origin_frame")),
        "cycle_rate_hz": float(mechanism.get_editor_property("cycle_rate_hz")),
        "phase_offset_cycles": float(mechanism.get_editor_property("phase_offset_cycles")),
        "inward_travel_cm": float(mechanism.get_editor_property("inward_travel_cm")),
    }


def close_transform(actual, expected, tolerance=0.001):
    return all(abs(float(a) - float(b)) <= tolerance
               for key in ("location", "rotation", "scale")
               for a, b in zip(actual[key], expected[key]))


def panel_matches(actual, expected):
    expected_policy = str(expected["facing_policy"])
    policy_key = next((key for key in (
        "AUTO_BY_ROLE", "PRESERVE_ASSET", "ROTATE180_AROUND_UP")
        if key in expected_policy), expected_policy)
    return (actual["mesh"] == expected["mesh"] and
            actual["material_overrides"] == expected["material_overrides"] and
            close_transform(actual["local_transform"], expected["local_transform"]) and
            policy_key in str(actual["facing_policy"]) and
            actual["flip_image_horizontally"] == expected["flip_image_horizontally"])


def set_panel(panel, record):
    mesh_path = record["mesh"]
    mesh = None if mesh_path is None else unreal.EditorAssetLibrary.load_asset(mesh_path)
    if mesh_path is not None and not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("MESH_LOAD_FAIL|path=" + str(mesh_path))
    overrides = [None if path is None else unreal.EditorAssetLibrary.load_asset(path)
                 for path in record["material_overrides"]]
    if any(path is not None and value is None
           for path, value in zip(record["material_overrides"], overrides)):
        raise RuntimeError("MATERIAL_OVERRIDE_LOAD_FAIL")
    policies = {
        "AUTO_BY_ROLE": unreal.InfinityPanelFacingPolicy.AUTO_BY_ROLE,
        "PRESERVE_ASSET": unreal.InfinityPanelFacingPolicy.PRESERVE_ASSET,
        "ROTATE180_AROUND_UP": unreal.InfinityPanelFacingPolicy.ROTATE180_AROUND_UP,
    }
    policy = next((value for key, value in policies.items()
                   if key in record["facing_policy"]), None)
    if policy is None:
        raise RuntimeError("UNKNOWN_FACING_POLICY|" + record["facing_policy"])
    panel.set_editor_property("mesh", mesh)
    panel.set_editor_property("material_overrides", overrides)
    panel.set_editor_property("local_transform", transform_from_plain(record["local_transform"]))
    panel.set_editor_property("facing_policy", policy)
    panel.set_editor_property("flip_image_horizontally", bool(record["flip_image_horizontally"]))
    return panel


def passage_actor(config, show):
    matches = [actor for actor in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem).get_all_level_actors()
        if actor.get_class().get_name() == "InfinityStagePassageActor"
        and actor.get_actor_label().startswith(config["passage_actor_label_prefix"])
        and actor.get_editor_property("show_asset") == show]
    if len(matches) != 1:
        raise RuntimeError("PASSAGE_ACTOR_COUNT|passage=%s|actual=%d" %
                           (config["passage"], len(matches)))
    return matches[0]


def cue_guid(cue):
    return cue.get_editor_property("cue_guid").to_string()


def assert_occurrence(cue, cue_index, record, prefix, error="CUE_IDENTITY_FAIL"):
    """Require the stable occurrence identity; label is diagnostic/secondary only."""
    actual_guid = cue_guid(cue)
    actual_label = str(cue.get_editor_property("label"))
    if (int(cue_index) != int(record["cue_index"]) or
            actual_guid != record["cue_guid"] or
            actual_label != record["cue_label"] or
            not actual_label.startswith(prefix)):
        raise RuntimeError(
            "%s|expected_index=%s|actual_index=%s|expected_guid=%s|actual_guid=%s|"
            "expected_label=%s|actual_label=%s" %
            (error, record["cue_index"], cue_index, record["cue_guid"], actual_guid,
             record["cue_label"], actual_label))
    return actual_guid, actual_label


def log_has(marker_text):
    path = os.path.join(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_log_dir()), "PussStage.log")
    with open(path, encoding="utf-8", errors="replace") as handle:
        return marker_text in handle.read()


def load_mapping(config):
    with open(config["mapping_file"], encoding="utf-8") as handle:
        doc = json.load(handle)
    kind = config["mapping_kind"]
    if kind == "kept_map":
        entries = [row for row in doc.get("entries", [])
                   if row.get("passage") == config["passage"]]
        if not entries:
            raise RuntimeError("MAPPING_PASSAGE_EMPTY|" + config["passage"])
        return {"kind": kind, "entries": entries}
    if kind == "p03_layout":
        if config["passage"] != "P03" or not doc.get("occurrences"):
            raise RuntimeError("P03_LAYOUT_CONTRACT_FAIL")
        return {"kind": kind, "families": doc["family_catalog"],
                "occurrences": doc["occurrences"]}
    if kind == "p02_layout":
        rows = doc.get("occurrences", [])
        if (config["passage"] != "P02" or len(rows) != 23 or
                [int(row.get("sequence_order", 0)) for row in rows] != list(range(1, 24))):
            raise RuntimeError("P02_LAYOUT_CONTRACT_FAIL")
        source_root = _project_path(config.get("import_plant_source_root", ""))
        if not os.path.isdir(source_root):
            raise RuntimeError("P02_VALIDATION_ROOT_MISSING|" + source_root)
        validation_by_asset = {}
        for folder_name in sorted(os.listdir(source_root)):
            folder = os.path.join(source_root, folder_name)
            status_path = os.path.join(folder, "status.json")
            validation_path = os.path.join(folder, "validation.json")
            if not os.path.isfile(status_path) or not os.path.isfile(validation_path):
                continue
            with open(status_path, encoding="utf-8") as handle:
                status = json.load(handle)
            with open(validation_path, encoding="utf-8") as handle:
                validation = json.load(handle)
            validation_by_asset[str(status["asset_name"])] = bool(validation.get("pass"))
        failed_assets = sorted(asset for asset, passed in validation_by_asset.items() if not passed)
        return {"kind": kind, "occurrences": rows,
                "validation_by_asset": validation_by_asset,
                "failed_assets": failed_assets}
    if kind == "slot_b_pools":
        if not doc.get("left_pool") or not doc.get("right_pool"):
            raise RuntimeError("SLOT_B_POOL_CONTRACT_FAIL")
        return {"kind": kind, "left_pool": doc["left_pool"],
                "right_pool": doc["right_pool"]}
    raise RuntimeError("MAPPING_KIND_FAIL|" + str(kind))


def destination_mesh(config, name):
    return config["destination_root"].rstrip("/") + "/StaticMeshes/" + name


def desired_meshes(config, mapping, label, ordinal, originals):
    """Return requested mesh values and explicit changed-side candidates."""
    result = {side: originals[side]["mesh"] for side in ("left", "right", "top")}
    requested = set()
    excluded_hits = []
    if mapping["kind"] == "slot_b_pools":
        result["left"] = mapping["left_pool"][ordinal % len(mapping["left_pool"])]
        result["right"] = mapping["right_pool"][ordinal % len(mapping["right_pool"])]
        requested.update(("left", "right"))
    elif mapping["kind"] == "kept_map":
        excluded = set(config.get("excluded_new_meshes", []))
        for entry in mapping["entries"]:
            side = {"L": "left", "R": "right", "C": "top"}.get(entry.get("side"))
            if side and originals[side]["mesh"] == entry.get("replaces"):
                if entry["new_mesh"] in excluded:
                    excluded_hits.append({"cue_label": label, "side": side,
                                          "old_mesh": entry["replaces"],
                                          "excluded_new_mesh": entry["new_mesh"]})
                else:
                    result[side] = destination_mesh(config, entry["new_mesh"])
                    requested.add(side)
    elif mapping["kind"] == "p03_layout":
        if ordinal >= len(mapping["occurrences"]):
            raise RuntimeError("P03_MAPPING_OCCURRENCE_MISSING|ordinal=" + str(ordinal))
        row = mapping["occurrences"][ordinal]
        if (int(row.get("row_index", -1)) != int(originals["cue_index"]) or
                str(row.get("label")) != label):
            raise RuntimeError("P03_MAPPING_IDENTITY_FAIL|ordinal=%d|index=%s|label=%s" %
                               (ordinal, originals["cue_index"], label))
        for short, side in (("L", "left"), ("R", "right"), ("C", "top")):
            proposal = row["proposal"][short]
            if proposal in ("existing", "keep_existing"):
                expected_name = row["existing"].get(short)
                actual_name = (originals[side]["mesh"] or "").rsplit("/", 1)[-1]
                if expected_name and actual_name != expected_name:
                    raise RuntimeError("P03_EXISTING_IDENTITY_FAIL|label=%s|side=%s|expected=%s|actual=%s" %
                                       (label, side, expected_name, actual_name))
            elif proposal == "clear":
                result[side] = None
                requested.add(side)
            else:
                family = mapping["families"].get(proposal)
                if family is None:
                    raise RuntimeError("P03_FAMILY_MISSING|" + proposal)
                result[side] = destination_mesh(config, family["asset"])
                requested.add(side)
    elif mapping["kind"] == "p02_layout":
        if ordinal >= len(mapping["occurrences"]):
            raise RuntimeError("P02_MAPPING_OCCURRENCE_MISSING|ordinal=" + str(ordinal))
        row = mapping["occurrences"][ordinal]
        if (int(row.get("sequence_order", 0)) != ordinal + 1 or
                int(row.get("saved_row_index", -1)) != int(originals["cue_index"]) or
                str(row.get("saved_label")) != label):
            raise RuntimeError("P02_MAPPING_IDENTITY_FAIL|ordinal=%d|index=%s|label=%s" %
                               (ordinal, originals["cue_index"], label))
        excluded = set(config.get("excluded_new_meshes", [])) | set(mapping["failed_assets"])
        for key, side in (("left", "left"), ("right", "right"), ("top", "top")):
            proposal = row["proposal"][key]
            asset = str(proposal["asset"])
            if asset in excluded:
                excluded_hits.append({"cue_guid": originals["cue_guid"],
                                      "cue_index": originals["cue_index"],
                                      "cue_label": label, "side": side,
                                      "old_mesh": originals[side]["mesh"],
                                      "excluded_new_mesh": asset})
                continue
            if str(proposal.get("family_class", "")).upper() == "MYSTICAL":
                result[side] = "/Game/Scenes/Wings/FlatV3/Passage04/StaticMeshes/" + asset
            else:
                result[side] = destination_mesh(config, asset)
            requested.add(side)
    else:
        raise RuntimeError("MAPPING_KIND_FAIL|" + str(mapping["kind"]))
    return result, sorted(requested), excluded_hits


def planned_panel(mesh_path, y=0.0):
    return {"mesh": mesh_path, "material_overrides": [],
            "local_transform": {"location": [0.0, float(y), 0.0],
                                "rotation": [0.0, 0.0, 0.0],
                                "scale": [1.0, 1.0, 1.0]},
            "facing_policy": "PRESERVE_ASSET", "flip_image_horizontally": False}


def box_points(mesh):
    box = mesh.get_bounding_box()
    return [unreal.Vector(x, y, z) for x in (box.min.x, box.max.x)
            for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]


def side_bounds(panel_record, library_by_mesh):
    mesh_path = panel_record["mesh"]
    if mesh_path is None:
        raise RuntimeError("OLD_MESH_IS_NONE")
    mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("OLD_MESH_LOAD_FAIL|path=" + str(mesh_path))
    points = box_points(mesh)
    if panel_record["flip_image_horizontally"]:
        points = [unreal.Vector(point.x, -point.y, point.z) for point in points]
    entry = library_by_mesh.get(mesh_path)
    rotate = "ROTATE180_AROUND_UP" in panel_record["facing_policy"]
    placement_applied = False
    front_axis = None
    if entry is not None:
        front_axis = str(entry.get_editor_property("front_axis"))
        if "AUTO_BY_ROLE" in panel_record["facing_policy"]:
            rotate = "NEGATIVE_X" in front_axis.upper()
        placement = entry.get_editor_property("placement_adjustment")
        scale = placement.scale3d
        mirrored = float(scale.x * scale.y * scale.z) < 0.0
        if not mirrored or bool(entry.get_editor_property("photographic_mirror_approved")):
            points = [placement.transform_location(point) for point in points]
            placement_applied = True
    if rotate:
        rotation = unreal.Transform(rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=180.0))
        points = [rotation.transform_location(point) for point in points]
    local = transform_from_plain(panel_record["local_transform"])
    points = [local.transform_location(point) for point in points]
    ys = [float(point.y) for point in points]
    return {"min_y_cm": min(ys), "max_y_cm": max(ys),
            "facing": {"front_axis": front_axis, "rotate_180": rotate,
                       "placement_adjustment_applied": placement_applied}}


def saved_roots_for_run(config, run, current_phase_roots=None):
    roots = set(current_phase_roots or [])
    for phase in ("apply", "revert"):
        path = artifact(config, phase, run=run)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                roots.update(json.load(handle).get("saved_roots", []))
    return sorted(roots)


def log_release(config, status, saved_roots, reason=None, run=None, artifact_run=None):
    release_run = run or config["run_id"]
    roots = saved_roots_for_run(config, artifact_run or release_run, saved_roots)
    current = census()
    if reason is not None:
        unreal.log_error("%s run=%s reason=%s census=%s" %
                         (marker(config, "FAIL"), release_run,
                          str(reason).replace("\n", "\\n"),
                          json.dumps(current, separators=(",", ":"), sort_keys=True)))
    unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s census=%s" %
               (release_run, status, len(roots), json.dumps(roots, separators=(",", ":")),
                json.dumps(current, separators=(",", ":"), sort_keys=True)))
