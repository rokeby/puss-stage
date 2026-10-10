"""Offline-importable Unreal DRY/APPLY/READBACK/REVERT tool for job 56.

APPLY creates (or verifies) one create-only child of BP_Effect_Candle, then
places one tagged child actor at each declared Candle_NN socket.  The source
candle Blueprint and Stylish Fire Niagara asset are read-only.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import re
import shutil
from typing import Any, Iterable

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
ARGS_PATH = os.path.join(HERE, "p56_chandelier_candles_args.json")
RECORD_PATH = os.path.join(HERE, "p56_chandelier_originals.json")
REPORT_PATH = os.path.join(HERE, "p56_chandelier_report.json")

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SOURCE_BP = "/Game/Scenes/Effects/BP_Effect_Candle"
CHILD_BP = "/Game/Scenes/Effects/BP_Effect_ChandelierCandle"
FIRE_NIAGARA = "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_1"
COMPONENT_NAME = "ChandelierFlameFX"
OWNER_TAG = "P56_CHANDELIER_CANDLE"
CONFIRM_TOKEN = "P56CHANDELIER"
SOCKET_RE = re.compile(r"^Candle_(\d{2,})$")

DEFAULTS = {
    "mode": "DRY",
    "confirm": "",
    "actor_label": "",
    "socket_json": "",
    "source_blueprint": SOURCE_BP,
    "child_blueprint": CHILD_BP,
    "flame_niagara": FIRE_NIAGARA,
    # Look values are deliberately args, not hidden constants (house rule 7).
    "flame_height_cm": 3.5,
    "niagara_reference_height_cm": 100.0,
    "flame_z_offset_cm": 1.75,
}


class P56Error(RuntimeError):
    pass


def require(value: Any, message: str) -> None:
    if not value:
        raise P56Error(message)


def _vec3(value: Any, field: str) -> list[float]:
    require(isinstance(value, (list, tuple)) and len(value) == 3, field + "_VEC3")
    result = [float(x) for x in value]
    require(all(abs(x) < 1.0e7 for x in result), field + "_FINITE_RANGE")
    return result


def parse_socket_document(document: Any) -> list[dict[str, Any]]:
    """Parse p55 output without depending on Blender or Unreal.

    p55 fixes socket names but not a complete envelope schema.  This accepts
    its likely flat location_cm/rotation_deg form and a transform-wrapped form,
    then normalizes to a single strict representation.
    """
    require(isinstance(document, dict), "SOCKET_DOCUMENT_OBJECT")
    raw = document.get("sockets")
    require(isinstance(raw, list) and raw, "NO_SOCKETS")
    rows = []
    for item in raw:
        require(isinstance(item, dict), "SOCKET_ROW_OBJECT")
        name = str(item.get("name", ""))
        match = SOCKET_RE.fullmatch(name)
        require(match is not None, "SOCKET_NAME|" + name)
        transform = item.get("transform", {})
        require(isinstance(transform, dict), "SOCKET_TRANSFORM|" + name)
        location = item.get("location_cm", item.get("position_cm", transform.get("location_cm")))
        rotation = item.get("rotation_deg", transform.get("rotation_deg", [0.0, 0.0, 0.0]))
        rows.append({
            "name": name,
            "index": int(match.group(1)),
            "location_cm": _vec3(location, name + "_LOCATION"),
            "rotation_deg": _vec3(rotation, name + "_ROTATION"),
        })
    rows.sort(key=lambda row: row["index"])
    require(len({row["name"] for row in rows}) == len(rows), "DUPLICATE_SOCKET")
    require([row["index"] for row in rows] == list(range(1, len(rows) + 1)),
            "SOCKET_SEQUENCE")
    return rows


def validate_args(raw: Any, source_exists: bool = True) -> dict[str, Any]:
    require(isinstance(raw, dict), "ARGS_OBJECT")
    args = copy.deepcopy(DEFAULTS)
    args.update(raw)
    args["mode"] = str(args.get("mode", "DRY")).upper()
    require(args["mode"] in ("DRY", "APPLY", "READBACK", "REVERT"), "MODE")
    label = str(args.get("actor_label", "")).strip()
    require(label and "chandelier" in label.lower(), "ACTOR_NOT_CHANDELIER|" + label)
    require(str(args.get("socket_json", "")).lower().endswith(".json"), "SOCKET_JSON_PATH")
    require(args.get("source_blueprint") == SOURCE_BP, "SOURCE_BP_MUST_BE_CANONICAL")
    require(source_exists, "SOURCE_BP_MISSING|" + SOURCE_BP)
    require(args.get("child_blueprint") == CHILD_BP, "CHILD_BP_PATH")
    require(args.get("flame_niagara") == FIRE_NIAGARA, "NIAGARA_PATH")
    height = float(args.get("flame_height_cm", 0.0))
    reference = float(args.get("niagara_reference_height_cm", 0.0))
    require(3.0 <= height <= 5.0, "FLAME_HEIGHT_CM")
    require(reference > 0.0, "NIAGARA_REFERENCE_HEIGHT_CM")
    args["flame_height_cm"] = height
    args["niagara_reference_height_cm"] = reference
    args["flame_z_offset_cm"] = float(args.get("flame_z_offset_cm", height / 2.0))
    if args["mode"] in ("APPLY", "REVERT"):
        require(args.get("confirm") == "%s %s" % (args["mode"], CONFIRM_TOKEN),
                "CONFIRM|want=%s %s" % (args["mode"], CONFIRM_TOKEN))
    return args


def build_plan(args: dict[str, Any], sockets: list[dict[str, Any]]) -> dict[str, Any]:
    require(sockets, "NO_SOCKETS")
    scale = args["flame_height_cm"] / args["niagara_reference_height_cm"]
    require(0.001 <= scale <= 1.0, "FLAME_SCALE")
    target_key = re.sub(r"[^A-Za-z0-9]+", "_", args["actor_label"]).strip("_")
    require(target_key, "ACTOR_KEY")
    rows = []
    for socket in sockets:
        rows.append({
            "socket": socket["name"],
            "actor_label": "P56_%s_%s_Flame" % (target_key, socket["name"]),
            "tags": [OWNER_TAG, "P56_TARGET_" + target_key, "P56_SOCKET_" + socket["name"]],
        })
    return {
        "target_actor": args["actor_label"],
        "source_blueprint": args["source_blueprint"],
        "child_blueprint": args["child_blueprint"],
        "niagara": args["flame_niagara"],
        "component": COMPONENT_NAME,
        "component_auto_activate": False,
        "flame_height_cm": args["flame_height_cm"],
        "flame_scale": [scale, scale, scale],
        "flame_z_offset_cm": args["flame_z_offset_cm"],
        "uses_point_light": False,
        "placements": rows,
    }


def select_revert_labels(actor_rows: Iterable[dict[str, Any]], expected_tags: Iterable[str]) -> list[str]:
    wanted = set(expected_tags)
    require(OWNER_TAG in wanted, "REVERT_OWNER_TAG_REQUIRED")
    selected = []
    for row in actor_rows:
        tags = set(str(x) for x in row.get("tags", []))
        if wanted <= tags:
            selected.append(str(row.get("label", "")))
    return sorted(x for x in selected if x)


def _read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str, value: Any, exclusive: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _run_id() -> str:
    return "P56CANDLE-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _asset_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value.get_path_name()) if hasattr(value, "get_path_name") else str(value)
    return text.split(".", 1)[0]


def _census() -> dict[str, list[str]]:
    require(unreal is not None, "UNREAL_REQUIRED")
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(_asset_id(x) for x in lib.get_dirty_content_packages()),
        "maps": sorted(_asset_id(x) for x in lib.get_dirty_map_packages()),
    }


def _require_clean(label: str) -> dict[str, list[str]]:
    got = _census()
    require(got == {"content": [], "maps": []}, label + "_DIRTY|" + json.dumps(got, sort_keys=True))
    return got


def _project_dir() -> str:
    return os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _package_file(package: str) -> str:
    require(package.startswith("/Game/"), "PACKAGE_OUTSIDE_GAME|" + package)
    base = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
                        package[len("/Game/"):].replace("/", os.sep))
    for extension in (".uasset", ".umap"):
        if os.path.isfile(base + extension):
            return os.path.normpath(base + extension)
    return os.path.normpath(base + ".uasset")


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _backup(run: str, packages: list[str], note: str) -> dict[str, Any]:
    root = os.path.join(_project_dir(), "Backups", "PreP56ChandelierCandles-" + run)
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in packages:
        source = _package_file(package)
        require(os.path.isfile(source), "BACKUP_SOURCE_MISSING|" + source)
        relative = package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(source)[1]
        destination = os.path.join(root, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        require(_sha256(source) == _sha256(destination), "BACKUP_HASH|" + package)
        rows.append({"package": package, "source": source, "backup": destination,
                     "bytes": os.path.getsize(source), "sha256": _sha256(source)})
    manifest = {"run": run, "note": note, "packages": rows}
    _write_json(os.path.join(root, "prechange.json"), manifest, exclusive=True)
    return {"root": root, "packages": rows}


def _editor_guard() -> tuple[Any, Any]:
    require(unreal is not None, "UNREAL_REQUIRED")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    require(world is not None, "EDITOR_WORLD_MISSING")
    require(_asset_id(world) == EXPECTED_WORLD,
            "WRONG_WORLD|expected=%s|actual=%s" % (EXPECTED_WORLD, _asset_id(world)))
    return editor, world


def _all_actors() -> list[Any]:
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _find_target(label: str) -> tuple[Any, Any]:
    hits = [actor for actor in _all_actors() if str(actor.get_actor_label()) == label]
    require(len(hits) == 1, "TARGET_ACTOR_COUNT|label=%s|count=%d" % (label, len(hits)))
    actor = hits[0]
    components = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    require(len(components) == 1, "TARGET_STATIC_MESH_COMPONENT_COUNT|%d" % len(components))
    return actor, components[0]


def _verify_sockets(mesh_component: Any, sockets: list[dict[str, Any]]) -> list[str]:
    found = []
    for row in sockets:
        require(bool(mesh_component.does_socket_exist(unreal.Name(row["name"]))),
                "SOCKET_NOT_ON_MESH|" + row["name"])
        found.append(row["name"])
    return found


def _subobject(bp: Any, variable: str) -> Any:
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data = lib.get_data(handle)
        if str(lib.get_variable_name(data)) == variable:
            return lib.get_object_for_blueprint(data, bp) or lib.get_associated_object(data)
    return None


def _verify_child_blueprint(args: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    bp = unreal.load_asset(args["child_blueprint"])
    require(bp is not None, "CHILD_BP_LOAD")
    generated = bp.generated_class()
    source_class = unreal.EditorAssetLibrary.load_blueprint_class(args["source_blueprint"])
    require(generated is not None and source_class is not None, "BP_CLASS_LOAD")
    # Reflected UClass objects are values, not Python types: isinstance(...,
    # source_class) raises TypeError, and BlueprintGeneratedClass does not expose
    # is_child_of in UE 5.8.  BlueprintEditorLibrary is the supported 5.8 route
    # for reading a Blueprint asset's direct parent class.
    parent_class = unreal.BlueprintEditorLibrary.get_blueprint_parent_class(bp)
    require(parent_class is not None and _asset_id(parent_class) == _asset_id(source_class),
            "CHILD_BP_PARENT")
    component = _subobject(bp, COMPONENT_NAME)
    require(isinstance(component, unreal.NiagaraComponent), "CHILD_NIAGARA_COMPONENT")
    got_scale = component.get_editor_property("relative_scale3d")
    got = {
        "parent": _asset_id(source_class),
        "niagara": _asset_id(component.get_asset()),
        "auto_activate": bool(component.get_editor_property("auto_activate")),
        "scale": [float(got_scale.x), float(got_scale.y), float(got_scale.z)],
    }
    require(got["niagara"] == args["flame_niagara"], "CHILD_NIAGARA_ASSET")
    require(got["auto_activate"] is False, "CHILD_AUTO_ACTIVATE")
    require(all(abs(a - b) <= 1.0e-4 for a, b in zip(got["scale"], plan["flame_scale"])),
            "CHILD_SCALE|" + json.dumps(got))
    return got


def _create_child_blueprint(args: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    source_class = unreal.EditorAssetLibrary.load_blueprint_class(args["source_blueprint"])
    require(source_class is not None, "SOURCE_BP_CLASS_LOAD")
    bp = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(args["child_blueprint"], source_class)
    require(bp is not None, "CHILD_BP_CREATE")
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    lib = unreal.SubobjectDataBlueprintFunctionLibrary
    handles = {str(lib.get_variable_name(lib.get_data(handle))): handle
               for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp)}
    parent = handles.get("TrackingRoot")
    require(parent is not None, "TRACKING_ROOT_MISSING")
    handle, reason = subsystem.add_new_subobject(unreal.AddNewSubobjectParams(
        parent_handle=parent, new_class=unreal.NiagaraComponent, blueprint_context=bp))
    require(lib.is_handle_valid(handle), "ADD_NIAGARA_COMPONENT|" + str(reason))
    require(subsystem.rename_subobject(handle, unreal.Text(COMPONENT_NAME)), "RENAME_NIAGARA_COMPONENT")
    component = lib.get_associated_object(lib.get_data(handle))
    system = unreal.load_asset(args["flame_niagara"])
    require(isinstance(system, unreal.NiagaraSystem), "NIAGARA_LOAD")
    component.set_asset(system)
    component.set_editor_property("auto_activate", False)
    component.set_editor_property("relative_scale3d", unreal.Vector(*plan["flame_scale"]))
    component.set_editor_property("relative_location", unreal.Vector(0.0, 0.0, plan["flame_z_offset_cm"]))
    require(unreal.BlueprintEditorLibrary.compile_blueprint(bp), "CHILD_BP_COMPILE")
    require(unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False), "CHILD_BP_SAVE")
    return _verify_child_blueprint(args, plan)


def _actor_state(actor: Any) -> dict[str, Any]:
    parent = actor.get_attach_parent_actor()
    # StaticMeshActor.get_root_component is absent from UE 5.8's generated
    # Python surface.  The reflected root_component property is available on
    # both the target mesh actor and spawned Blueprint actors.
    root_component = actor.get_editor_property("root_component")
    require(root_component is not None, "ACTOR_ROOT_COMPONENT|" + str(actor.get_actor_label()))
    component = root_component.get_attach_parent()
    return {
        "label": str(actor.get_actor_label()),
        "path": str(actor.get_path_name()),
        "tags": sorted(str(x) for x in actor.get_editor_property("tags")),
        "parent_label": str(parent.get_actor_label()) if parent else None,
        "socket": str(root_component.get_attach_socket_name()),
        "parent_component": str(component.get_name()) if component else None,
        "class": _asset_id(actor.get_class()),
    }


def _owned_states(expected_labels: Iterable[str]) -> list[dict[str, Any]]:
    wanted = set(expected_labels)
    rows = [_actor_state(actor) for actor in _all_actors()
            if str(actor.get_actor_label()) in wanted
            and OWNER_TAG in {str(x) for x in actor.get_editor_property("tags")}]
    return sorted(rows, key=lambda row: row["label"])


def _readback(args: dict[str, Any], plan: dict[str, Any], expect_present: bool) -> list[dict[str, Any]]:
    labels = [row["actor_label"] for row in plan["placements"]]
    rows = _owned_states(labels)
    if expect_present:
        require(len(rows) == len(labels), "READBACK_COUNT|%d/%d" % (len(rows), len(labels)))
        by_label = {row["label"]: row for row in rows}
        for placement in plan["placements"]:
            row = by_label[placement["actor_label"]]
            require(row["parent_label"] == args["actor_label"], "READBACK_PARENT|" + row["label"])
            require(row["socket"] == placement["socket"], "READBACK_SOCKET|" + row["label"])
            require(set(placement["tags"]) <= set(row["tags"]), "READBACK_TAGS|" + row["label"])
    else:
        require(not rows, "READBACK_REVERT_PRESENT|" + json.dumps(rows, sort_keys=True))
    return rows


def _spawn_all(args: dict[str, Any], plan: dict[str, Any], mesh_component: Any) -> list[dict[str, Any]]:
    child_class = unreal.EditorAssetLibrary.load_blueprint_class(args["child_blueprint"])
    require(child_class is not None, "CHILD_CLASS_LOAD")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    created = []
    for placement in plan["placements"]:
        actor = subsystem.spawn_actor_from_class(child_class, unreal.Vector(), unreal.Rotator())
        require(actor is not None, "SPAWN|" + placement["socket"])
        actor.set_actor_label(placement["actor_label"], mark_dirty=True)
        actor.set_editor_property("tags", [unreal.Name(tag) for tag in placement["tags"]])
        attached = actor.attach_to_component(
            mesh_component, unreal.Name(placement["socket"]),
            unreal.AttachmentRule.SNAP_TO_TARGET, unreal.AttachmentRule.SNAP_TO_TARGET,
            unreal.AttachmentRule.KEEP_RELATIVE, False)
        require(attached, "ATTACH|" + placement["socket"])
        created.append(_actor_state(actor))
    return created


def _save_level() -> None:
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "SAVE_LEVEL")
    _require_clean("POST_SAVE")


def main() -> None:
    run = _run_id()
    args_raw = _read_json(ARGS_PATH)
    source_exists = bool(unreal.EditorAssetLibrary.does_asset_exist(SOURCE_BP))
    args = validate_args(args_raw, source_exists=source_exists)
    sockets = parse_socket_document(_read_json(args["socket_json"]))
    plan = build_plan(args, sockets)
    _editor_guard()
    dirty_before = _require_clean("PRE")
    target, mesh_component = _find_target(args["actor_label"])
    found_sockets = _verify_sockets(mesh_component, sockets)
    child_exists = bool(unreal.EditorAssetLibrary.does_asset_exist(args["child_blueprint"]))
    existing = _owned_states(row["actor_label"] for row in plan["placements"])

    if args["mode"] == "DRY":
        require(_census() == dirty_before, "DRY_CHANGED_CENSUS")
        unreal.log("P56_CHANDELIER_DRY_OK|run=%s|target=%s|sockets=%s|source=%s|child=%s|niagara=%s|create_bp=%s|placements=%d|dirty=0+0" %
                   (run, args["actor_label"], ",".join(found_sockets), args["source_blueprint"],
                    args["child_blueprint"], args["flame_niagara"], str(not child_exists).lower(),
                    len(plan["placements"])))
        return

    if args["mode"] == "READBACK":
        require(os.path.isfile(RECORD_PATH), "ORIGINALS_RECORD_MISSING")
        record = _read_json(RECORD_PATH)
        state = str(record.get("status"))
        require(state in ("applied", "reverted"), "RECORD_STATUS|" + state)
        rows = _readback(args, plan, expect_present=state == "applied")
        child = _verify_child_blueprint(args, plan)
        require(_census() == dirty_before, "READBACK_CHANGED_CENSUS")
        unreal.log("P56_CHANDELIER_READBACK_OK|run=%s|state=%s|actors=%d|child_bp=1|dirty=0+0" %
                   (run, state, len(rows)))
        return

    if args["mode"] == "APPLY":
        require(not os.path.exists(RECORD_PATH), "ORIGINALS_RECORD_EXISTS")
        require(not existing, "OWNED_ACTORS_ALREADY_EXIST")
        backup = _backup(run, [EXPECTED_WORLD, SOURCE_BP, FIRE_NIAGARA],
                         "Level original plus read-only source assets before P56 APPLY.")
        record = {
            "schema": "p56_chandelier_originals_v1", "status": "prepared", "run": run,
            "args": args, "plan": plan, "backup": backup, "dirty_before": dirty_before,
            "target": _actor_state(target), "owned_actors_before": existing,
            "child_blueprint_existed_before": child_exists,
        }
        _write_json(RECORD_PATH, record, exclusive=True)  # before any Unreal mutation
        child = (_verify_child_blueprint(args, plan) if child_exists
                 else _create_child_blueprint(args, plan))
        record["child_blueprint_created"] = not child_exists
        record["child_readback"] = child
        _write_json(RECORD_PATH, record)
        require(_census() == {"content": [], "maps": []}, "DIRTY_AFTER_CHILD_SAVE|" + json.dumps(_census()))
        created = _spawn_all(args, plan, mesh_component)
        require(_census() == {"content": [], "maps": [EXPECTED_WORLD]},
                "APPLY_DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
        _save_level()
        readback = _readback(args, plan, expect_present=True)
        record.update({"status": "applied", "created": created, "readback": readback})
        _write_json(RECORD_PATH, record)
        _write_json(REPORT_PATH, {"ok": True, "run": run, "mode": "APPLY", "backup": backup,
                                  "readback": readback, "child": child, "dirty_after": _census()})
        unreal.log("P56_CHANDELIER_APPLY_OK|run=%s|target=%s|actors=%d|child_created=%s|saved=1|readback=1|dirty=0+0" %
                   (run, args["actor_label"], len(readback), str(not child_exists).lower()))
        return

    require(os.path.isfile(RECORD_PATH), "ORIGINALS_RECORD_MISSING")
    record = _read_json(RECORD_PATH)
    require(record.get("status") == "applied", "REVERT_RECORD_NOT_APPLIED")
    expected_labels = [row["actor_label"] for row in plan["placements"]]
    current = _owned_states(expected_labels)
    require(current == record.get("readback"), "REVERT_DRIFT_REFUSAL")
    backup = _backup(run, [EXPECTED_WORLD], "Saved level immediately before P56 tagged-actor REVERT.")
    selected = select_revert_labels(current, [OWNER_TAG])
    require(selected == sorted(expected_labels), "REVERT_TAG_SELECTION")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors_by_label = {str(actor.get_actor_label()): actor for actor in _all_actors()}
    for label in selected:
        require(subsystem.destroy_actor(actors_by_label[label]), "DESTROY_ACTOR|" + label)
    require(_census() == {"content": [], "maps": [EXPECTED_WORLD]},
            "REVERT_DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
    _save_level()
    _readback(args, plan, expect_present=False)
    record.update({"status": "reverted", "revert_run": run, "revert_backup": backup,
                   "reverted_actor_labels": selected,
                   "child_blueprint_preserved": True})
    _write_json(RECORD_PATH, record)
    _write_json(REPORT_PATH, {"ok": True, "run": run, "mode": "REVERT", "backup": backup,
                              "removed": selected, "child_blueprint_preserved": True,
                              "dirty_after": _census()})
    unreal.log("P56_CHANDELIER_REVERT_OK|run=%s|actors=%d|child_bp_preserved=1|saved=1|readback=1|dirty=0+0" %
               (run, len(selected)))


if unreal is not None and __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - preserve exact stopped marker for the conductor.
        unreal.log_error("P56_CHANDELIER_STOPPED|%s|do not Save All; inspect exact census" % error)
        raise
