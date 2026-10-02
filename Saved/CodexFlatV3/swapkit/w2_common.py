"""Shared fail-closed helpers for the Scene 3 W2 wave fresh-import swap."""
import glob
import json
import math
import os
import re
import sys

import unreal


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CLEAN = {"content": [], "maps": []}
EXPECTED_SLOTS = ["Front", "Flap", "Timber", "Edge"]
PAIR_KEYS = tuple("%d_%s" % (row, half) for row in (1, 2, 3) for half in ("A", "B"))

PROJECT = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
BASE = os.path.normpath(os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexFlatV3", "swapkit"))


def project_path(value):
    value = str(value)
    return os.path.normpath(value if os.path.isabs(value) else os.path.join(PROJECT, value))


def config_path(explicit=None):
    value = explicit or globals().get("FLATV3_CONFIG") or os.environ.get("FLATV3_CONFIG")
    if not value and len(sys.argv) > 1 and str(sys.argv[1]).lower().endswith(".json"):
        value = sys.argv[1]
    if not value:
        value = os.path.join(BASE, "run_w2.json")
    return project_path(value)


def load_config(explicit=None):
    path = config_path(explicit)
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    required = {
        "schema_version", "slot", "run_id", "import_run_id", "source_root",
        "destination_root", "actor_label_prefix", "expected_actor_count",
        "probe_widths_file", "ls_devscene_03", "world", "success_marker",
        "import_success_marker",
    }
    missing = sorted(required - set(config))
    if missing:
        raise RuntimeError("W2_CONFIG_KEYS_MISSING|" + json.dumps(missing))
    if int(config["schema_version"]) != 1 or config["slot"] != "W2":
        raise RuntimeError("W2_CONFIG_IDENTITY_FAIL")
    if config["world"] != WORLD or int(config["expected_actor_count"]) != 6:
        raise RuntimeError("W2_CONFIG_SCOPE_FAIL")
    expected_source = os.path.normcase(project_path(
        "DerivedAssets/FlatV3/Overnight/flats_ext2"))
    actual_source = os.path.normcase(project_path(config["source_root"]))
    if actual_source != expected_source:
        raise RuntimeError("W2_SOURCE_ROOT_FAIL|expected=%s|actual=%s" %
                           (expected_source, actual_source))
    result = dict(config)
    result["_path"] = path
    result["source_root"] = project_path(config["source_root"])
    result["probe_widths_file"] = project_path(config["probe_widths_file"])
    return result


def artifact(config, phase, failure=False):
    suffix = "_FAILURE" if failure else ""
    run = config["import_run_id"] if phase == "import" else config["run_id"]
    return os.path.join(BASE, "w2_%s_%s%s.json" % (phase, run, suffix))


def write_report(config, phase, payload, failure=False):
    path = artifact(config, phase, failure=failure)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def read_report(config, phase):
    path = artifact(config, phase)
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
    if actual != config["world"]:
        raise RuntimeError("W2_WRONG_WORLD|expected=%s|actual=%s" % (config["world"], actual))
    if editor.get_game_world() is not None:
        raise RuntimeError("W2_PIE_OR_SIE_ACTIVE")
    current = census()
    if clean and current != CLEAN:
        raise RuntimeError("W2_DIRTY_AT_START|census=" + json.dumps(current, sort_keys=True))
    return world


def log_paths():
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_log_dir())
    return [os.path.join(root, "PussStage.log")] + sorted(
        glob.glob(os.path.join(root, "PussStage-backup-*.log")))


def log_has(text):
    for path in log_paths():
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as handle:
            if text in handle.read():
                return True
    return False


def assert_run_unused(run_id):
    hits = []
    for path in log_paths():
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as handle:
            if run_id in handle.read():
                hits.append(path)
    if hits:
        raise RuntimeError("W2_RUN_ID_ALREADY_USED|run=%s|logs=%s" %
                           (run_id, json.dumps(hits)))


def asset_path(value):
    return None if value is None else str(value.get_path_name()).split(".", 1)[0]


def pair_key_from_label(label):
    compact = re.sub(r"[^a-z0-9]", "", str(label).lower())
    match = re.match(r"^s3waverow([123])([ab])(?:$|.*)", compact)
    return None if match is None else "%s_%s" % (match.group(1), match.group(2).upper())


def wave_actors(config):
    actors = [actor for actor in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem).get_all_level_actors()
        if str(actor.get_actor_label()).startswith(config["actor_label_prefix"])]
    if len(actors) != int(config["expected_actor_count"]):
        raise RuntimeError("W2_ACTOR_COUNT_FAIL|expected=6|actual=%d|labels=%s" %
                           (len(actors), json.dumps(sorted(
                               str(actor.get_actor_label()) for actor in actors))))
    by_key = {}
    for actor in actors:
        key = pair_key_from_label(actor.get_actor_label())
        if key is None or key in by_key:
            raise RuntimeError("W2_ACTOR_LABEL_MAP_FAIL|label=%s|key=%s" %
                               (actor.get_actor_label(), key))
        by_key[key] = actor
    if sorted(by_key) != sorted(PAIR_KEYS):
        raise RuntimeError("W2_ACTOR_KEYS_FAIL|actual=" + json.dumps(sorted(by_key)))
    return by_key


def static_mesh_component(actor):
    component = None
    if hasattr(actor, "get_component_by_class"):
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
    if component is None and hasattr(actor, "get_components_by_class"):
        values = list(actor.get_components_by_class(unreal.StaticMeshComponent))
        component = values[0] if len(values) == 1 else None
    if component is None:
        try:
            component = actor.get_editor_property("static_mesh_component")
        except Exception:
            component = None
    if component is None:
        raise RuntimeError("W2_STATIC_MESH_COMPONENT_FAIL|actor=" + actor.get_path_name())
    return component


def component_mesh(component):
    try:
        return component.get_editor_property("static_mesh")
    except Exception:
        return component.get_static_mesh()


def set_component_mesh(component, mesh):
    # modify() first: set_static_mesh alone does not dirty the level package, so the
    # level-only save gate refused (W2 FV3W2-20261002-01, measured 2 Oct).
    owner = component.get_owner()
    if owner is not None:
        owner.modify()
    component.modify()
    # set_editor_property goes through the editor property-change path (PreEdit/
    # PostEditChange), which dirties the outer package; set_static_mesh did not
    # (FV3W2-20261002-01/-02 measured the level clean after it).
    component.set_editor_property("static_mesh", mesh)
    result = component.get_editor_property("static_mesh") == mesh
    if result is False:
        raise RuntimeError("W2_SET_STATIC_MESH_FAIL|mesh=" + asset_path(mesh))


def transform_plain(transform):
    rotation = transform.rotation.rotator()
    return {
        "location": [float(transform.translation.x), float(transform.translation.y),
                     float(transform.translation.z)],
        "rotation": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
        "scale": [float(transform.scale3d.x), float(transform.scale3d.y),
                  float(transform.scale3d.z)],
    }


def angle_delta(a, b):
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def assert_transform_close(actual, expected, tolerance=0.01, marker="W2_TRANSFORM_CHANGED"):
    current = transform_plain(actual) if not isinstance(actual, dict) else actual
    errors = []
    for name in ("location", "scale"):
        errors.extend(abs(float(a) - float(b)) for a, b in zip(current[name], expected[name]))
    errors.extend(angle_delta(a, b) for a, b in zip(current["rotation"], expected["rotation"]))
    if any((not math.isfinite(value)) or value > float(tolerance) for value in errors):
        raise RuntimeError("%s|expected=%s|actual=%s|tolerance=%g" %
                           (marker, json.dumps(expected, sort_keys=True),
                            json.dumps(current, sort_keys=True), tolerance))


def actor_record(key, actor):
    component = static_mesh_component(actor)
    return {
        "key": key,
        "label": str(actor.get_actor_label()),
        "actor_path": str(actor.get_path_name()),
        "old_mesh": asset_path(component_mesh(component)),
        "world_transform": transform_plain(actor.get_actor_transform()),
    }


def actor_bounds_width_cm(actor):
    _origin, extent = actor.get_actor_bounds(False, False)
    return 2.0 * max(float(extent.x), float(extent.y))


def ls_package(config):
    asset = unreal.EditorAssetLibrary.load_asset(config["ls_devscene_03"])
    if asset is None:
        raise RuntimeError("W2_LS_DEVSCENE_03_NOT_FOUND|path=" + config["ls_devscene_03"])
    return str(asset.get_outermost().get_name()).split(".", 1)[0]


def assert_ls_not_dirty(config, current=None):
    current = current or census()
    package = ls_package(config)
    if package in set(current["content"]) | set(current["maps"]):
        raise RuntimeError("W2_LS_DEVSCENE_03_DIRTY|package=" + package)
    return package


def assert_level_only_dirty(config):
    current = census()
    expected = {"content": [], "maps": [config["world"]]}
    if current != expected:
        raise RuntimeError("W2_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                           (json.dumps(expected, sort_keys=True),
                            json.dumps(current, sort_keys=True)))
    assert_ls_not_dirty(config, current)
    return current


def save_current_level(config):
    before = assert_level_only_dirty(config)
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("W2_LEVEL_SAVE_FAIL")
    after = census()
    if after != CLEAN:
        raise RuntimeError("W2_POST_SAVE_DIRTY|census=" + json.dumps(after, sort_keys=True))
    assert_ls_not_dirty(config, after)
    return {"before": before, "after": after, "saved_roots": [config["world"]]}


def mesh_path(config, key):
    row, half = key.split("_")
    return (config["destination_root"].rstrip("/") + "/StaticMeshes/" +
            "SM_FlatV3_S3_WaveRow%s_%s_v2" % (row, half))


def all_destination_paths(config):
    paths = []
    for key in PAIR_KEYS:
        row, half = key.split("_")
        owner = "S3_WaveRow%s_%s_v2" % (row, half)
        root = config["destination_root"].rstrip("/")
        paths.extend([
            root + "/StaticMeshes/SM_FlatV3_" + owner,
            root + "/Textures/%s/T_%s_SkinColor" % (owner, owner),
            root + "/Textures/%s/T_%s_SkinMask" % (owner, owner),
            root + "/Textures/%s/T_%s_SkinNormal" % (owner, owner),
            root + "/Textures/%s/T_%s_AgedPlywood_Stencil_Color" % (owner, owner),
            root + "/Materials/Instances/MI_FlatV3_%s_Front" % owner,
            root + "/Materials/Instances/MI_FlatV3_%s_Flap" % owner,
        ])
    return sorted(paths)


def load_probe_widths(config):
    with open(config["probe_widths_file"], encoding="utf-8") as handle:
        meshes = json.load(handle)["meshes"]
    result = {}
    for key in PAIR_KEYS:
        row, half = key.split("_")
        name = "SM_FlatV3_S3_WaveRow%s_%s" % (row, half)
        result[key] = float(meshes[name]["bounds_extent"][1])
    return result


def actor_by_path(actors, path):
    matches = [actor for actor in actors.values() if str(actor.get_path_name()) == str(path)]
    if len(matches) != 1:
        raise RuntimeError("W2_ACTOR_PATH_FAIL|path=%s|actual=%d" % (path, len(matches)))
    return matches[0]


def log_release(config, status, saved_roots, reason=None, run=None):
    run = run or config["run_id"]
    roots = sorted(set(saved_roots))
    if reason is not None:
        unreal.log_error("FLATV3_W2_FAIL run=%s reason=%s census=%s" %
                         (run, str(reason).replace("\n", "\\n"),
                          json.dumps(census(), separators=(",", ":"), sort_keys=True)))
    unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s census=%s" %
               (run, status, len(roots), json.dumps(roots, separators=(",", ":")),
                json.dumps(census(), separators=(",", ":"), sort_keys=True)))
