"""Job 182 live-ready P06 chandelier inspection, lighting, review and revert.

DRY and REVIEW require owned PIE and never save. APPLY/READBACK/REVERT require
the clean editor world. No code path queries, selects, moves or deletes a swarm
actor; ownership is exact tags plus exact labels on the nine Job 182 lights.
"""
from __future__ import annotations

import hashlib
import datetime
import json
import math
import os
import re
import shutil
import sys
from typing import Any, Iterable

import unreal


HERE = os.path.dirname(__file__).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import job182_core as core  # noqa: E402


WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OWNER_TAG = "JOB182_P06_CHANDELIER_LIGHT"
RUN_TAG_PREFIX = "JOB182_RUN_"
ROLE_TAG_PREFIX = "JOB182_ROLE_"
ACTIVE_RECORD = HERE + "/job182_ACTIVE.json"
LATEST_REPORT = HERE + "/job182_latest_report.json"
SOCKET_RE = re.compile(r"Candle_(\d{2})")


def require(condition: Any, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _asset_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value.get_path_name() if hasattr(value, "get_path_name") else value)
    return text.split(".", 1)[0]


def _vec(value: Any) -> list[float]:
    return [float(value.x), float(value.y), float(value.z)]


def _rot(value: Any) -> list[float]:
    return [float(value.roll), float(value.pitch), float(value.yaw)]


def _distance(a: Any, b: Any) -> float:
    return math.sqrt((float(a.x) - float(b.x)) ** 2 +
                     (float(a.y) - float(b.y)) ** 2 +
                     (float(a.z) - float(b.z)) ** 2)


def _write(path: str, value: Any, exclusive: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def _read(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _run_id() -> str:
    return "J182-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _census() -> dict[str, list[str]]:
    library = unreal.EditorAssetLibrary
    return {
        "content": sorted(_asset_id(item) for item in library.get_dirty_content_packages()),
        "maps": sorted(_asset_id(item) for item in library.get_dirty_map_packages()),
    }


def _require_clean(label: str) -> dict[str, list[str]]:
    got = _census()
    require(got == {"content": [], "maps": []}, label + "_DIRTY|" + json.dumps(got, sort_keys=True))
    return got


def _project_dir() -> str:
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()).rstrip("/\\")


def _package_file(package: str) -> str:
    require(package.startswith("/Game/"), "PACKAGE_GAME_ROOT|" + package)
    stem = os.path.join(_project_dir(), "Content", *package[6:].split("/"))
    for extension in (".umap", ".uasset"):
        path = stem + extension
        if os.path.isfile(path):
            return path
    raise RuntimeError("PACKAGE_FILE_MISSING|" + package)


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _backup(run_id: str, note: str) -> dict[str, Any]:
    root = os.path.join(_project_dir(), "Backups", "PreJob182P06ChandelierLight-" + run_id)
    os.makedirs(root, exist_ok=False)
    source = _package_file(WORLD)
    destination = os.path.join(root, *WORLD[6:].split("/")) + ".umap"
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy2(source, destination)
    require(_sha256(source) == _sha256(destination), "BACKUP_HASH")
    row = {"package": WORLD, "source": source, "backup": destination,
           "bytes": os.path.getsize(source), "sha256": _sha256(source)}
    manifest = {"run": run_id, "note": note, "packages": [row]}
    _write(os.path.join(root, "prechange.json"), manifest, exclusive=True)
    return {"root": root, "packages": [row]}


def _editor_world() -> Any:
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    require(_asset_id(world) == WORLD, "WRONG_WORLD|" + str(_asset_id(world)))
    return world


def _pie_world() -> Any:
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_game_world()
    require(world is not None, "OWNED_PIE_REQUIRED")
    # UE 5.8 returns None for get_editor_world() while PIE is active. Validate
    # the owned PIE copy directly after removing its UEDPIE_<n>_ package prefix.
    pie_id = _asset_id(world)
    source_id = re.sub(r"/UEDPIE_\d+_", "/", pie_id or "")
    require(source_id == WORLD, "WRONG_PIE_WORLD|" + str(pie_id))
    return world


def _actors_editor() -> list[Any]:
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _actors_pie(world: Any) -> list[Any]:
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


def _find_exact(actors: Iterable[Any], label: str) -> Any:
    hits = [actor for actor in actors if str(actor.get_actor_label()) == label]
    require(len(hits) == 1, "ACTOR_COUNT|%s|%d" % (label, len(hits)))
    return hits[0]


def _body_and_mesh(actors: Iterable[Any], args: dict[str, Any]) -> tuple[Any, Any]:
    body = _find_exact(actors, args["body_actor_label"])
    meshes = [component for component in body.get_components_by_class(unreal.StaticMeshComponent)
              if _asset_id(component.get_editor_property("static_mesh")) == args["body_mesh"]]
    require(len(meshes) == 1, "BODY_MESH_COMPONENT_COUNT|%d" % len(meshes))
    mesh = meshes[0]
    names = [name for name in core.SOCKETS
             if bool(mesh.does_socket_exist(unreal.Name(name)))]
    require(names == core.SOCKETS, "BODY_CANDLE_SOCKET_COUNT|%d" % len(names))
    return body, mesh


def _component_location(component: Any) -> Any:
    if hasattr(component, "get_world_location"):
        return component.get_world_location()
    return component.get_component_transform().translation


def _candle_rows(actors: list[Any], body: Any, mesh: Any, args: dict[str, Any],
                 probe_render: bool = False) -> list[dict[str, Any]]:
    by_label = {str(actor.get_actor_label()): actor for actor in actors
                if str(actor.get_actor_label()).startswith(args["candle_actor_prefix"])}
    rows = []
    for socket in core.SOCKETS:
        label = args["candle_actor_prefix"] + socket.split("_", 1)[1] + "_Flame"
        actor = by_label.get(label)
        require(actor is not None, "CANDLE_ACTOR_MISSING|" + label)
        root = actor.get_editor_property("root_component")
        require(root is not None, "CANDLE_ROOT_MISSING|" + label)
        parent = actor.get_attach_parent_actor()
        attached_socket = str(root.get_attach_socket_name())
        socket_location = mesh.get_socket_location(unreal.Name(socket))
        components = []
        for component in actor.get_components_by_class(unreal.NiagaraComponent):
            asset = _asset_id(component.get_asset())
            if str(component.get_name()) != args["flame_component_name"] or asset != args["flame_niagara"]:
                continue
            recently = None
            if probe_render:
                require(hasattr(component, "was_recently_rendered"), "NIAGARA_RENDER_PROBE_UNAVAILABLE|" + label)
                recently = bool(component.was_recently_rendered(2.0))
            registered = bool(component.is_registered()) if hasattr(component, "is_registered") else None
            components.append({
                "name": str(component.get_name()), "asset": asset,
                "world_location_cm": _vec(_component_location(component)),
                "active": bool(component.is_active()), "visible": bool(component.is_visible()),
                "registered": registered, "was_recently_rendered_2s": recently,
            })
        require(len(components) == 1, "FLAME_COMPONENT_COUNT|%s|%d" % (label, len(components)))
        rows.append({
            "socket": socket, "socket_world_cm": _vec(socket_location),
            "actor_label": label, "actor_world_cm": _vec(actor.get_actor_location()),
            "parent_label": str(parent.get_actor_label()) if parent else None,
            "attached_socket": attached_socket, "flame": components[0],
            "body_parent_ok": parent == body, "attached_socket_ok": attached_socket == socket,
        })
    assessed = core.assess_candles(rows, args["candle_socket_tolerance_cm"])
    return assessed["rows"]


def _mesh_bounds(body: Any) -> dict[str, Any]:
    # include_from_child_actors=False is the critical particle-exclusion rule.
    origin, extent = body.get_actor_bounds(False, False)
    return {"origin_cm": _vec(origin), "extent_cm": _vec(extent),
            "basis": "actor components only; include_from_child_actors=false; exact Iron3 mesh verified"}


def _camera_sample(manager: Any, controller: Any, bounds: dict[str, Any]) -> dict[str, Any]:
    location = manager.get_camera_location()
    rotation = manager.get_camera_rotation()
    fov = float(manager.get_fov_angle())
    forward = unreal.MathLibrary.get_forward_vector(rotation)
    right = unreal.MathLibrary.get_right_vector(rotation)
    up = unreal.MathLibrary.get_up_vector(rotation)
    origin = unreal.Vector(*bounds["origin_cm"])
    offset = origin - location
    depth = unreal.MathLibrary.dot_vector_vector(offset, forward)
    side = unreal.MathLibrary.dot_vector_vector(offset, right)
    vertical = unreal.MathLibrary.dot_vector_vector(offset, up)
    radius = math.sqrt(sum(value * value for value in bounds["extent_cm"]))
    aspect = 16.0 / 9.0
    half_width = max(1.0e-6, depth * math.tan(math.radians(fov) * 0.5))
    half_height = half_width / aspect
    fully_visible = (depth > radius and abs(side) + radius <= half_width and
                     abs(vertical) + radius <= half_height)
    intersects = (depth + radius > 0.0 and abs(side) <= half_width + radius and
                  abs(vertical) <= half_height + radius)
    fill = radius / max(1.0, half_height)
    score = fill - 0.25 * (abs(side) / max(1.0, half_width) +
                         abs(vertical) / max(1.0, half_height))
    target = controller.get_view_target()
    return {
        "camera_actor_label": str(target.get_actor_label()) if target else None,
        "camera_location_cm": _vec(location), "camera_rotation_deg": _rot(rotation),
        "horizontal_fov_deg": fov, "depth_cm": depth, "side_cm": side,
        "vertical_cm": vertical, "fully_visible": fully_visible,
        "intersects_view": intersects, "bounds_fill_score": fill, "selection_score": score,
    }


def _tags(actor: Any) -> set[str]:
    return {str(tag) for tag in actor.get_editor_property("tags")}


def _owned_editor() -> list[Any]:
    return [actor for actor in _actors_editor() if OWNER_TAG in _tags(actor)]


def _light_state(actor: Any) -> dict[str, Any]:
    lights = list(actor.get_components_by_class(unreal.PointLightComponent))
    require(len(lights) == 1, "POINT_COMPONENT_COUNT|" + str(actor.get_actor_label()))
    component = lights[0]
    parent = actor.get_attach_parent_actor()
    root = actor.get_editor_property("root_component")
    require(root is not None, "POINT_ROOT_COMPONENT|" + str(actor.get_actor_label()))
    world = actor.get_actor_location()
    relative = root.get_editor_property("relative_location")
    return {
        "label": str(actor.get_actor_label()), "tags": sorted(_tags(actor)),
        "parent_label": str(parent.get_actor_label()) if parent else None,
        "world_location_cm": _vec(world), "relative_location_cm": _vec(relative),
        "intensity_cd": float(component.get_editor_property("intensity")),
        "intensity_units": str(component.get_editor_property("intensity_units")).split(".")[-1].split(":")[0],
        "temperature_k": float(component.get_editor_property("temperature")),
        "attenuation_radius_cm": float(component.get_editor_property("attenuation_radius")),
        "source_radius_cm": float(component.get_editor_property("source_radius")),
        "cast_shadows": bool(component.get_editor_property("cast_shadows")),
        "use_temperature": bool(component.get_editor_property("use_temperature")),
        "volumetric_scattering_intensity": float(
            component.get_editor_property("volumetric_scattering_intensity")),
    }


def _owned_states() -> list[dict[str, Any]]:
    return sorted((_light_state(actor) for actor in _owned_editor()), key=lambda row: row["label"])


def _tag_light(actor: Any, role: str, run_id: str) -> None:
    actor.set_editor_property("tags", [unreal.Name(OWNER_TAG),
                                       unreal.Name(ROLE_TAG_PREFIX + role),
                                       unreal.Name(RUN_TAG_PREFIX + run_id)])
    actor.set_folder_path("Codex/Job182/P06Chandelier")


def _configure_light(actor: Any, row: dict[str, Any]) -> None:
    component = actor.get_editor_property("point_light_component")
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    component.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
    component.set_editor_property("intensity", row["intensity_cd"])
    component.set_editor_property("use_temperature", True)
    component.set_editor_property("temperature", row["temperature_k"])
    component.set_editor_property("attenuation_radius", row["attenuation_radius_cm"])
    component.set_editor_property("source_radius", row["source_radius_cm"])
    component.set_editor_property("cast_shadows", False)
    component.set_editor_property("volumetric_scattering_intensity", 0.0)


def _spawn_light(label: str, location: Any, body: Any, row: dict[str, Any],
                 role: str, run_id: str) -> Any:
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(unreal.PointLight, location, unreal.Rotator())
    require(actor is not None, "SPAWN_POINT|" + label)
    actor.set_actor_label(label, mark_dirty=True)
    _tag_light(actor, role, run_id)
    attached = actor.attach_to_actor(body, unreal.Name(), unreal.AttachmentRule.KEEP_WORLD,
                                     unreal.AttachmentRule.KEEP_WORLD,
                                     unreal.AttachmentRule.KEEP_WORLD, False)
    require(attached, "ATTACH_POINT|" + label)
    _configure_light(actor, row)
    return actor


def _apply_lights(body: Any, mesh: Any, proposal: dict[str, Any], args: dict[str, Any],
                  run_id: str) -> list[Any]:
    tip_by_socket = {}
    up = body.get_actor_up_vector()
    for socket in core.SOCKETS:
        tip_by_socket[socket] = mesh.get_socket_location(unreal.Name(socket)) + up * args["flame_tip_offset_cm"]
    created = []
    for index, row in enumerate(proposal["group_lights"]):
        mean = core.vector_mean([_vec(tip_by_socket[name]) for name in row["sockets"]])
        created.append(_spawn_light(row["label"], unreal.Vector(*mean), body, row,
                                    "CANDLE_GROUP_%02d" % (index + 1), run_id))
    fill = proposal["iron_fill"]
    offset = fill["offset_local_cm"]
    location = (body.get_actor_location() + body.get_actor_forward_vector() * offset[0] +
                body.get_actor_right_vector() * offset[1] + body.get_actor_up_vector() * offset[2])
    created.append(_spawn_light(fill["label"], location, body, fill, "IRON_FILL", run_id))
    return created


def _save_level() -> None:
    require(_census() == {"content": [], "maps": [WORLD]},
            "DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "SAVE_LEVEL")
    _require_clean("POST_SAVE")


def _expected_labels(proposal: dict[str, Any]) -> list[str]:
    return sorted([row["label"] for row in proposal["group_lights"]] +
                  [proposal["iron_fill"]["label"]])


def _run_editor(args: dict[str, Any], proposal: dict[str, Any], run_id: str) -> dict[str, Any]:
    _editor_world()
    dirty_before = _require_clean("PRE")
    body, mesh = _body_and_mesh(_actors_editor(), args)
    existing = _owned_states()
    expected_labels = _expected_labels(proposal)

    if args["mode"] == "READBACK":
        record = _read(ACTIVE_RECORD) if os.path.isfile(ACTIVE_RECORD) else None
        drift = None if record is None or record.get("status") != "applied" else not core.actor_states_match(
            record["readback"], existing)
        result = {"ok": True, "mode": "READBACK", "run": run_id,
                  "active_record": ACTIVE_RECORD if record else None,
                  "record_status": record.get("status") if record else None,
                  "lights": existing, "drift": drift, "dirty_after": _census()}
        require(_census() == dirty_before, "READBACK_CHANGED_CENSUS")
        _write(LATEST_REPORT, result)
        unreal.log("JOB182_CHANDELIER_LIGHT_READBACK_OK|run=%s|lights=%d|drift=%s|dirty=0+0" %
                   (run_id, len(existing), str(drift).lower()))
        return result

    if args["mode"] == "APPLY":
        require(args["reviewed_plan_sha256"] == proposal["plan_sha256"],
                "REVIEWED_PLAN_SHA256|want=" + proposal["plan_sha256"])
        require(not os.path.exists(ACTIVE_RECORD), "ACTIVE_RECORD_EXISTS")
        require(not existing, "OWNED_LIGHTS_EXIST|%d" % len(existing))
        backup = _backup(run_id, "Before nine Job 182 P06 chandelier lights; no Niagara actor is in scope.")
        record = {"schema": "job182_p06_chandelier_light_active_v1", "status": "prepared",
                  "run": run_id, "proposal": proposal, "backup": backup,
                  "dirty_before": dirty_before, "expected_labels": expected_labels}
        _write(ACTIVE_RECORD, record, exclusive=True)
        created = _apply_lights(body, mesh, proposal, args, run_id)
        require(len(created) == 9, "CREATED_LIGHT_COUNT")
        require(_census() == {"content": [], "maps": [WORLD]},
                "APPLY_DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
        record.update({"status": "created_in_memory", "created_labels": sorted(
            str(actor.get_actor_label()) for actor in created)})
        _write(ACTIVE_RECORD, record)
        _save_level()
        readback = _owned_states()
        require([row["label"] for row in readback] == expected_labels, "READBACK_LABELS")
        require(all(row["parent_label"] == args["body_actor_label"] for row in readback),
                "READBACK_PARENT")
        require(all(not row["cast_shadows"] and row["use_temperature"] and
                    row["intensity_units"] == "CANDELAS" for row in readback),
                "READBACK_LIGHT_FLAGS")
        record.update({"status": "applied", "readback": readback, "dirty_after": _census()})
        _write(ACTIVE_RECORD, record)
        result = {"ok": True, "mode": "APPLY", "run": run_id, "proposal": proposal,
                  "backup": backup, "readback": readback, "record": ACTIVE_RECORD,
                  "dirty_after": _census()}
        _write(LATEST_REPORT, result)
        unreal.log("JOB182_CHANDELIER_LIGHT_APPLY_OK|run=%s|group_lights=8|fill_lights=1|shadows=0|saved=1|readback=1|dirty=0+0|record=%s" %
                   (run_id, ACTIVE_RECORD))
        return result

    require(args["mode"] == "REVERT", "EDITOR_MODE")
    require(os.path.isfile(ACTIVE_RECORD), "ACTIVE_RECORD_MISSING")
    record = _read(ACTIVE_RECORD)
    require(record.get("status") in ("prepared", "created_in_memory", "applied"), "ACTIVE_RECORD_STATUS")
    owned = _owned_editor()
    states = _owned_states()
    labels = sorted(str(actor.get_actor_label()) for actor in owned)
    require(set(labels) <= set(record["expected_labels"]), "REVERT_LABEL_SCOPE")
    require(all(RUN_TAG_PREFIX + record["run"] in _tags(actor) for actor in owned), "REVERT_RUN_TAG")
    if record.get("status") == "applied":
        require(core.actor_states_match(record["readback"], states), "REVERT_LIGHT_DRIFT")
        require(labels == record["expected_labels"], "REVERT_LIGHT_COUNT")
    backup = _backup(run_id, "Immediately before exact-tag Job 182 light REVERT.")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in owned:
        require(subsystem.destroy_actor(actor), "DESTROY_OWNED_LIGHT|" + str(actor.get_actor_label()))
    require(_census() == {"content": [], "maps": [WORLD]},
            "REVERT_DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
    _save_level()
    require(not _owned_editor(), "REVERT_OWNED_REMAIN")
    archive = ACTIVE_RECORD.replace("_ACTIVE.json", "_REVERTED_%s.json" % run_id)
    record.update({"status": "reverted", "revert_run": run_id, "revert_backup": backup,
                   "removed_labels": labels, "dirty_after": _census()})
    _write(ACTIVE_RECORD, record)
    os.replace(ACTIVE_RECORD, archive)
    result = {"ok": True, "mode": "REVERT", "run": run_id, "removed_labels": labels,
              "backup": backup, "archive": archive, "dirty_after": _census()}
    _write(LATEST_REPORT, result)
    unreal.log("JOB182_CHANDELIER_LIGHT_REVERT_OK|run=%s|lights=%d|saved=1|readback=1|dirty=0+0|record=%s" %
               (run_id, len(labels), archive))
    return result


def _pie_context(world: Any, args: dict[str, Any]) -> dict[str, Any]:
    actors = _actors_pie(world)
    body, mesh = _body_and_mesh(actors, args)
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    require(len(roots) == 1, "SHOW_ROOT_COUNT|%d" % len(roots))
    transport, player = roots[0].transport, roots[0].sequence_player
    segments = [segment for segment in list(transport.segments) if str(segment.label) == "Passage 6"]
    require(len(segments) == 1, "P06_SEGMENT_COUNT|%d" % len(segments))
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    manager = unreal.GameplayStatics.get_player_camera_manager(world, 0)
    require(controller is not None and manager is not None, "PLAYER_CAMERA")
    review_camera = _find_exact(actors, args["review_camera_actor_label"])
    cine = review_camera.get_cine_camera_component()
    require(cine is not None, "REVIEW_CINE_COMPONENT")
    return {"actors": actors, "body": body, "mesh": mesh, "transport": transport,
            "player": player, "segment": segments[0], "controller": controller,
            "camera_manager": manager,
            "review_camera": review_camera, "review_cine": cine}


def _run_pie(args: dict[str, Any], proposal: dict[str, Any], run_id: str) -> None:
    world = _pie_world()
    dirty_before = _require_clean("PRE")
    context = _pie_context(world, args)
    transport, player = context["transport"], context["player"]
    controller, manager = context["controller"], context["camera_manager"]
    review_camera, cine = context["review_camera"], context["review_cine"]
    segment = context["segment"]
    start, end = int(segment.start_frame.value), int(segment.end_frame.value)
    frames = [start + int(round(value * (end - start - 1))) for value in args["scan_fractions"]]
    original = {
        "frame": int(transport.get_current_master_frame().value),
        "playing": bool(transport.is_transport_playing()),
        "view": controller.get_view_target(),
        "cuts": player.get_disable_camera_cuts() if hasattr(player, "get_disable_camera_cuts") else False,
        "review_location": review_camera.get_actor_location(),
        "review_rotation": review_camera.get_actor_rotation(),
        "review_focal": cine.get_editor_property("current_focal_length"),
        "review_pp_weight": cine.get_editor_property("post_process_blend_weight"),
    }
    state = {"phase": "scan_pose", "index": 0, "wait": 0, "samples": [],
             "selected": None, "done": False, "handle": None, "file_wait": 0}
    player.pause()
    if hasattr(player, "set_disable_camera_cuts"):
        player.set_disable_camera_cuts(False)

    def restore() -> None:
        review_camera.set_actor_location_and_rotation(original["review_location"], original["review_rotation"],
                                                      False, True)
        cine.set_editor_property("current_focal_length", original["review_focal"])
        cine.set_editor_property("post_process_blend_weight", original["review_pp_weight"])
        if hasattr(player, "set_disable_camera_cuts"):
            player.set_disable_camera_cuts(original["cuts"])
        controller.set_view_target_with_blend(original["view"], 0.0)
        transport.scrub_to_master_frame(unreal.FrameNumber(original["frame"]))
        player.play() if original["playing"] else player.pause()

    def finish(ok: bool, detail: str = "", result: dict[str, Any] | None = None) -> None:
        if state["done"]:
            return
        state["done"] = True
        try:
            restore()
        finally:
            unreal.unregister_slate_post_tick_callback(state["handle"])
        if ok:
            require(result is not None, "PIE_RESULT")
            require(_census() == dirty_before, "PIE_CHANGED_CENSUS")
            result["dirty_after"] = _census()
            unique = HERE + "/job182_%s_%s.json" % (args["mode"], run_id)
            _write(unique, result, exclusive=True)
            _write(LATEST_REPORT, result)
            if args["mode"] == "DRY":
                unreal.log("JOB182_CHANDELIER_LIGHT_DRY_OK|run=%s|frame=%d|mesh=Iron3|sockets=44|candles_at_sockets=44|plan=%s|mutated=0|dirty=0+0|report=%s" %
                           (run_id, result["selected_master_frame"], proposal["plan_sha256"], unique))
            else:
                unreal.log("JOB182_CHANDELIER_REVIEW_OK|run=%s|frame=%d|mesh_bounds=1|active_niagara=44|recently_rendered=44|exposure_override=0|path=%s|dirty=0+0|report=%s" %
                           (run_id, result["selected_master_frame"], args["review_output"], unique))
        else:
            unreal.log_error("JOB182_CHANDELIER_%s_STOPPED|run=%s|%s|restored=1|do not Save All" %
                             (args["mode"], run_id, detail))

    def inspect_selected(probe_render: bool) -> dict[str, Any]:
        bounds = _mesh_bounds(context["body"])
        candles = _candle_rows(context["actors"], context["body"], context["mesh"], args, probe_render)
        require(all(row["actor_at_socket"] and row["body_parent_ok"] and row["attached_socket_ok"]
                    for row in candles), "CANDLE_SOCKET_READBACK")
        result = {
            "ok": True, "mode": args["mode"], "run": run_id,
            "selected_master_frame": state["selected"]["master_frame"],
            "selected_fraction": state["selected"]["fraction"],
            "visibility_scan": state["samples"], "mesh_bounds_world": bounds,
            "candles": candles, "proposal": proposal,
            "niagara_scope": "exact 44 BP_Effect_ChandelierCandle actors; no swarm actor queried or changed",
        }
        return result

    def tick(_delta: float) -> None:
        try:
            if state["done"]:
                return
            if state["phase"] == "scan_pose":
                frame = frames[state["index"]]
                transport.scrub_to_master_frame(unreal.FrameNumber(frame))
                state.update(phase="scan_wait", wait=int(args.get("scan_settle_ticks", 3)))
                return
            if state["phase"] == "scan_wait":
                state["wait"] -= 1
                if state["wait"] > 0:
                    return
                bounds = _mesh_bounds(context["body"])
                sample = _camera_sample(manager, controller, bounds)
                sample.update(master_frame=frames[state["index"]], fraction=args["scan_fractions"][state["index"]])
                state["samples"].append(sample)
                state["index"] += 1
                if state["index"] < len(frames):
                    state["phase"] = "scan_pose"
                    return
                full = [row for row in state["samples"] if row["fully_visible"]]
                visible = full or [row for row in state["samples"] if row["intersects_view"]]
                require(bool(visible), "MESH_NOT_ONSCREEN_IN_P06_SCAN")
                state["selected"] = max(visible, key=lambda row: row["selection_score"])
                transport.scrub_to_master_frame(unreal.FrameNumber(state["selected"]["master_frame"]))
                state.update(phase="selected_wait", wait=10)
                return
            if state["phase"] == "selected_wait":
                state["wait"] -= 1
                if state["wait"] > 0:
                    return
                if args["mode"] == "DRY":
                    finish(True, result=inspect_selected(False))
                    return
                # Preserve the active passage-camera side before taking over the view.
                source = _camera_sample(manager, controller, _mesh_bounds(context["body"]))
                bounds = _mesh_bounds(context["body"])
                origin = unreal.Vector(*bounds["origin_cm"])
                source_location = unreal.Vector(*source["camera_location_cm"])
                direction = source_location - origin
                length = max(1.0, direction.length())
                direction = direction / length
                cine.set_editor_property("post_process_blend_weight", 0.0)
                horizontal_fov = float(source["horizontal_fov_deg"])
                filmback = cine.get_editor_property("filmback")
                sensor_width = float(filmback.get_editor_property("sensor_width"))
                focal = sensor_width / (2.0 * math.tan(math.radians(horizontal_fov) * 0.5))
                cine.set_editor_property("current_focal_length", focal)
                aspect = args["review_resolution"][0] / args["review_resolution"][1]
                distance = core.fit_distance(bounds["extent_cm"], horizontal_fov, aspect,
                                             args["review_margin"])
                location = origin + direction * distance
                rotation = unreal.MathLibrary.find_look_at_rotation(location, origin)
                if hasattr(player, "set_disable_camera_cuts"):
                    player.set_disable_camera_cuts(True)
                review_camera.set_actor_location_and_rotation(location, rotation, False, True)
                controller.set_view_target_with_blend(review_camera, 0.0)
                state["review_camera"] = {
                    "source_passage_camera": source,
                    "location_cm": _vec(location), "rotation_deg": _rot(rotation),
                    "horizontal_fov_deg": horizontal_fov, "focal_length_mm": focal,
                    "fit_distance_cm": distance,
                    "bounds_basis": bounds["basis"], "post_process_blend_weight": 0.0,
                    "exposure_override": False,
                }
                state.update(phase="review_settle", wait=int(args.get("review_settle_ticks", 120)))
                return
            if state["phase"] == "review_settle":
                state["wait"] -= 1
                if state["wait"] > 0:
                    return
                output = args["review_output"].replace("\\", "/")
                require(not os.path.exists(output), "REVIEW_OUTPUT_EXISTS|" + output)
                os.makedirs(os.path.dirname(output), exist_ok=True)
                width, height = args["review_resolution"]
                unreal.SystemLibrary.execute_console_command(
                    world, 'HighResShot %dx%d filename="%s"' % (width, height, output))
                state.update(phase="review_file", file_wait=600)
                return
            state["file_wait"] -= 1
            output = args["review_output"].replace("\\", "/")
            if os.path.isfile(output) and os.path.getsize(output) > 1000:
                result = inspect_selected(True)
                result["review_camera"] = state["review_camera"]
                result["review_output"] = output
                require(all(row["flame"]["active"] and row["flame"]["visible"] and
                            row["flame"]["registered"] is not False and
                            row["flame"]["was_recently_rendered_2s"]
                            for row in result["candles"]), "NIAGARA_ACTIVE_RENDERING_44")
                finish(True, result=result)
            elif state["file_wait"] <= 0:
                finish(False, "REVIEW_FILE_TIMEOUT|" + output)
        except Exception as error:  # noqa: BLE001 - exact STOP marker is part of the operator contract.
            finish(False, repr(error))

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log("JOB182_CHANDELIER_%s_ARMED|run=%s|p06_scan_samples=%d|mesh_bounds_only=1|swarm_scope=none" %
               (args["mode"], run_id, len(frames)))


def run(raw: dict[str, Any]) -> Any:
    run_id = _run_id()
    try:
        args = core.validate_args(raw)
        proposal = core.build_proposal(args)
        if args["mode"] in ("DRY", "REVIEW"):
            return _run_pie(args, proposal, run_id)
        return _run_editor(args, proposal, run_id)
    except Exception as error:  # noqa: BLE001 - retain precise conductor marker.
        unreal.log_error("JOB182_CHANDELIER_LIGHT_STOPPED|run=%s|%s|do not Save All" % (run_id, error))
        raise
