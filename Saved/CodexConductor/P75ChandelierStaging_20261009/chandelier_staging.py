"""Later-live UE 5.8 DRY/APPLY/REVERT tool for P75.

The tool is offline-safe to import. Mutating runs accept exactly one part,
``opening`` or ``p06``. Each part has its own record and REVERT boundary.
P75 never spawns flames and never writes swing keys.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import math
import os
import shutil
from typing import Any, Iterable

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
ARGS_PATH = os.path.join(HERE, "chandelier_staging_args.json")
REPORT_PATH = os.path.join(HERE, "chandelier_staging_report.json")
SPEC = importlib.util.spec_from_file_location("p75_core", os.path.join(HERE, "chandelier_staging_core.py"))
CORE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CORE)

MARK = "P75_CHANDELIER"
OWNER_TAG = "P75_CHANDELIER_STAGING"
RUN_TAG_PREFIX = "P75_RUN_"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OPENING_SEQUENCE = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked"
PASSAGE_LABEL = "Passage 6"


def require(condition: Any, message: str) -> None:
    if not condition:
        raise CORE.P75Error(message)


def _read(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: str, value: Any, exclusive: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _run_id() -> str:
    return "P75CHAN-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def _active_record(part: str) -> str:
    return os.path.join(HERE, "chandelier_staging_%s_ACTIVE.json" % part)


def _asset_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value.get_path_name()) if hasattr(value, "get_path_name") else str(value)
    return text.split(".", 1)[0]


def _object_path(value: Any) -> str:
    return str(value.get_path_name()) if hasattr(value, "get_path_name") else str(value)


def _census() -> dict[str, list[str]]:
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(_asset_id(item) for item in lib.get_dirty_content_packages()),
            "maps": sorted(_asset_id(item) for item in lib.get_dirty_map_packages())}


def _require_clean(label: str) -> dict[str, list[str]]:
    got = _census()
    require(got == {"content": [], "maps": []}, label + "_DIRTY|" + json.dumps(got, sort_keys=True))
    return got


def _project_dir() -> str:
    return os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _chain_path(args: dict[str, Any]) -> str:
    relative = str(args["chain_layout_json"]).replace("/", os.sep)
    path = os.path.normpath(os.path.join(_project_dir(), relative))
    require(os.path.commonpath((_project_dir(), path)) == _project_dir(), "CHAIN_JSON_OUTSIDE_PROJECT")
    require(os.path.isfile(path), "CHAIN_JSON_MISSING|" + path)
    return path


def _package_file(package: str) -> str:
    require(package.startswith("/Game/"), "PACKAGE_OUTSIDE_GAME|" + package)
    base = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
                        package[6:].replace("/", os.sep))
    for extension in (".uasset", ".umap"):
        if os.path.isfile(base + extension):
            return os.path.normpath(base + extension)
    raise CORE.P75Error("PACKAGE_FILE_MISSING|" + package)


def _sha(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _backup(run: str, part: str, packages: Iterable[str], note: str) -> dict[str, Any]:
    root = os.path.join(_project_dir(), "Backups", "PreP75Chandelier%s-%s" % (part.title(), run))
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in packages:
        source = _package_file(package)
        relative = package[6:].replace("/", os.sep) + os.path.splitext(source)[1]
        destination = os.path.join(root, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        require(_sha(source) == _sha(destination), "BACKUP_HASH|" + package)
        rows.append({"package": package, "source": source, "backup": destination,
                     "bytes": os.path.getsize(source), "sha256": _sha(source)})
    manifest = {"run": run, "part": part, "note": note, "packages": rows}
    _write(os.path.join(root, "prechange.json"), manifest, exclusive=True)
    return {"root": root, "packages": rows}


def _guard() -> tuple[Any, Any]:
    require(unreal is not None, "UNREAL_REQUIRED")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    require(_asset_id(world) == WORLD, "WRONG_WORLD|" + str(_asset_id(world)))
    return editor, world


def _actors() -> list[Any]:
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _part_tag(part: str) -> str:
    return "P75_PART_" + part.upper()


def _actor_tags(actor: Any) -> set[str]:
    return {str(tag) for tag in actor.get_editor_property("tags")}


def _run_tag(run: str) -> str:
    return RUN_TAG_PREFIX + run


def cleanup_tag_decision(tags: Iterable[str], part: str, failed_run: str) -> dict[str, Any]:
    """Classify a live match without using its label or folder as authority."""
    values = {str(tag) for tag in tags}
    run_tags = sorted(tag for tag in values if tag.startswith(RUN_TAG_PREFIX))
    owned = OWNER_TAG in values and _part_tag(part) in values
    expected = _run_tag(failed_run)
    eligible = owned and (not run_tags or run_tags == [expected])
    reason = ("failed_run" if run_tags == [expected] else "legacy_no_run_tag" if owned and not run_tags
              else "different_or_ambiguous_run" if owned else "not_tool_owned")
    return {"eligible": eligible, "reason": reason, "run_tags": run_tags}


def _tag(actor: Any, part: str, role: str, run: str) -> None:
    actor.set_editor_property("tags", [unreal.Name(OWNER_TAG), unreal.Name(_part_tag(part)),
                                       unreal.Name("P75_ROLE_" + role), unreal.Name(_run_tag(run))])


def _find_actor(label: str) -> Any:
    hits = [actor for actor in _actors() if str(actor.get_actor_label()) == label]
    require(len(hits) == 1, "ACTOR_COUNT|%s|%d" % (label, len(hits)))
    return hits[0]


def _passage6() -> Any:
    actor = _find_actor(PASSAGE_LABEL)
    require(actor.get_editor_property("route") is not None, "P06_ROUTE_MISSING")
    return actor


def _body_transform(plan: dict[str, Any], part: str) -> Any:
    row = plan["parts"][part]
    if part == "opening":
        return unreal.Transform(unreal.Vector(*row["body_location_cm"]),
                                unreal.Rotator(*row["body_rotation_deg"]), unreal.Vector(1.0, 1.0, 1.0))
    route = _passage6().get_editor_property("route")
    transform = route.get_transform_at_distance_along_spline(
        row["hang_station_cm"], unreal.SplineCoordinateSpace.WORLD, True)
    location = transform.translation
    across = transform.rotation.rotate_vector(unreal.Vector(0.0, 1.0, 0.0))
    location = location + across * row["lateral_cm"] + unreal.Vector(0.0, 0.0, row["body_z_cm"])
    return unreal.Transform(location, transform.rotation.rotator(), unreal.Vector(1.0, 1.0, 1.0))


def _load_assets(args: dict[str, Any], parts: list[str]) -> dict[str, Any]:
    paths = {"body_mesh": args["body_mesh"], "material": args["material"]}
    paths.update({"chain_%02d" % index: path for index, path in enumerate(args["chain_meshes"])})
    if "opening" in parts:
        paths["opening_sequence"] = args.get("opening_sequence", OPENING_SEQUENCE)
    loaded = {key: unreal.load_asset(path) for key, path in paths.items()}
    for key, value in loaded.items():
        require(value is not None, "ASSET_MISSING|%s|%s" % (key, paths[key]))
    body_mesh = loaded["body_mesh"]
    candles = ["Candle_%02d" % index for index in range(100)
               if body_mesh.find_socket("Candle_%02d" % index) is not None]
    require(candles == ["Candle_%02d" % index for index in range(1, 45)], "SOCKET_COUNT_44_REQUIRED")
    require(body_mesh.find_socket("ChainAttach") is not None, "CHAIN_ATTACH_SOCKET_REQUIRED")
    require(not any(body_mesh.find_socket("SOCKET_Candle_%02d" % index) is not None for index in range(100)),
            "UNSTRIPPED_SOCKET_PREFIX")
    loaded["verified_socket_names"] = candles + ["ChainAttach"]
    return loaded


def _component_state(component: Any) -> dict[str, Any]:
    return {"hidden_in_game": bool(component.get_editor_property("hidden_in_game")),
            "cast_hidden_shadow": bool(component.get_editor_property("cast_hidden_shadow")),
            "cast_shadow": bool(component.get_editor_property("cast_shadow"))}


def _actor_state(actor: Any) -> dict[str, Any]:
    location, rotation = actor.get_actor_location(), actor.get_actor_rotation()
    scale = actor.get_actor_scale3d()
    meshes = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    lights = list(actor.get_components_by_class(unreal.LightComponent))
    try:
        folder = str(actor.get_folder_path())
    except Exception:  # noqa: BLE001 - folder is diagnostic, never an ownership guard.
        folder = ""
    return {"label": str(actor.get_actor_label()), "object_path": _object_path(actor),
            "folder": folder, "tags": sorted(_actor_tags(actor)),
            "location_cm": [float(location.x), float(location.y), float(location.z)],
            "rotation_deg": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
            "scale": [float(scale.x), float(scale.y), float(scale.z)],
            "mesh": _asset_id(meshes[0].get_editor_property("static_mesh")) if meshes else None,
            "materials": [_asset_id(value) for value in meshes[0].get_materials()] if meshes else [],
            "mesh_flags": _component_state(meshes[0]) if meshes else None,
            "light": ({"intensity": float(lights[0].get_editor_property("intensity")),
                       "cast_shadows": bool(lights[0].get_editor_property("cast_shadows"))}
                      if lights else None)}


def _part_owned_states(part: str) -> list[dict[str, Any]]:
    rows = [_actor_state(actor) for actor in _actors()
            if OWNER_TAG in _actor_tags(actor) and _part_tag(part) in _actor_tags(actor)]
    return sorted(rows, key=lambda row: row["label"])


def _cleanup_report(part: str, failed_run: str) -> dict[str, Any]:
    matches = []
    for state in _part_owned_states(part):
        decision = cleanup_tag_decision(state["tags"], part, failed_run)
        matches.append(dict(state, cleanup=decision))
    basis = {"owner_tag": OWNER_TAG, "part_tag": _part_tag(part), "part": part,
             "failed_run": failed_run, "matches": matches}
    wire = json.dumps(basis, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return dict(basis, cleanup_sha256=hashlib.sha256(wire.encode("utf-8")).hexdigest())


def _actor_states_match(recorded: list[dict[str, Any]], live: list[dict[str, Any]]) -> bool:
    """Compare saved actor state with the project's float read-back tolerances."""
    if len(recorded) != len(live):
        return False
    for before, after in zip(recorded, live):
        for key in ("label", "tags", "mesh", "materials", "mesh_flags"):
            if before.get(key) != after.get(key):
                return False
        if any(abs(float(a) - float(b)) > 0.01
               for a, b in zip(before["location_cm"], after["location_cm"])):
            return False
        if any(abs(float(a) - float(b)) > 0.001
               for a, b in zip(before["rotation_deg"], after["rotation_deg"])):
            return False
        if (before.get("light") is None) != (after.get("light") is None):
            return False
        if before.get("light"):
            if before["light"]["cast_shadows"] != after["light"]["cast_shadows"]:
                return False
            if abs(float(before["light"]["intensity"]) - float(after["light"]["intensity"])) > 0.001:
                return False
    return True


def _nested_matches(recorded: Any, live: Any, tolerance: float = 1.0e-4) -> bool:
    if isinstance(recorded, (int, float)) and isinstance(live, (int, float)):
        return abs(float(recorded) - float(live)) <= tolerance
    if type(recorded) is not type(live):
        return False
    if isinstance(recorded, dict):
        return set(recorded) == set(live) and all(
            _nested_matches(recorded[key], live[key], tolerance) for key in recorded)
    if isinstance(recorded, list):
        return len(recorded) == len(live) and all(
            _nested_matches(a, b, tolerance) for a, b in zip(recorded, live))
    return recorded == live


def _live_light_rows() -> list[dict[str, Any]]:
    rows = []
    for actor in _actors():
        if OWNER_TAG not in _actor_tags(actor):
            continue
        lights = list(actor.get_components_by_class(unreal.LightComponent))
        for component in lights:
            rows.append({"label": str(actor.get_actor_label()),
                         "cast_shadows": bool(component.get_editor_property("cast_shadows"))})
    return rows


def _verify_part_readback(plan: dict[str, Any], part: str, rows: list[dict[str, Any]]) -> None:
    labels = plan["instance_actor_labels"][part]
    by_label = {row["label"]: row for row in rows}
    require(len(by_label) == len(rows), "READBACK_LABEL_DUPLICATE")
    body = by_label.get(labels["body_actor_label"])
    require(body is not None and body["mesh"] == plan["assets"]["body_mesh"], "READBACK_BODY_MESH")
    require(plan["assets"]["material"] in body["materials"], "READBACK_BODY_MATERIAL")
    for index, label in enumerate(labels["link_actor_labels"]):
        link = by_label.get(label)
        require(link is not None and link["mesh"] == plan["assets"]["chain_meshes"][index],
                "READBACK_CHAIN_MESH_%02d" % index)
        require(plan["assets"]["material"] in link["materials"], "READBACK_CHAIN_MATERIAL_%02d" % index)
    light_rows = [row for row in rows if row["light"] is not None]
    require(len(light_rows) == len(plan["parts"][part]["lights"]), "READBACK_PART_LIGHT_COUNT")
    require(sum(row["light"]["cast_shadows"] for row in light_rows) ==
            sum(row["cast_shadows"] for row in plan["parts"][part]["lights"]),
            "READBACK_PART_SHADOW_COUNT")


def _spawn_mesh(label: str, mesh: Any, material: Any, transform: Any, hidden: bool,
                hidden_shadow: bool, part: str, role: str, run: str) -> Any:
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, transform.translation, transform.rotation.rotator())
    require(actor is not None, "SPAWN_MESH|" + label)
    actor.set_actor_label(label, mark_dirty=True)
    _tag(actor, part, role, run)
    component = actor.get_editor_property("static_mesh_component")
    component.set_editor_property("static_mesh", mesh)
    component.set_material(0, material)
    component.set_editor_property("hidden_in_game", hidden)
    component.set_editor_property("cast_shadow", True)
    component.set_editor_property("cast_hidden_shadow", hidden_shadow)
    component.set_collision_profile_name("NoCollision")
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return actor


def _spawn_assembly(plan: dict[str, Any], assets: dict[str, Any], part: str, run: str) -> tuple[Any, list[Any]]:
    row, labels = plan["parts"][part], plan["instance_actor_labels"][part]
    body_transform = _body_transform(plan, part)
    body = _spawn_mesh(labels["body_actor_label"], assets["body_mesh"], assets["material"], body_transform,
                       row["hidden_in_game"], row["cast_hidden_shadow"], part, "BODY", run)
    component = body.get_editor_property("static_mesh_component")
    socket_transform = component.get_socket_transform(unreal.Name("ChainAttach"),
                                                       unreal.RelativeTransformSpace.RTS_WORLD)
    rotation = body.get_actor_rotation()
    rotation_q = rotation.quaternion()  # UE 5.8: Rotator has no rotate_vector (live APPLY 9 Oct); Quat does
    attach_offset = rotation_q.rotate_vector(unreal.Vector(*plan["chain"]["body"]["attach_cm"]))
    top = socket_transform.translation - attach_offset
    links = []
    for link in plan["chain"]["links"]:
        index = link["index"]
        location = top + rotation_q.rotate_vector(unreal.Vector(*link["pivot_cm"]))
        transform = unreal.Transform(location, rotation, unreal.Vector(1.0, 1.0, 1.0))
        links.append(_spawn_mesh(labels["link_actor_labels"][index], assets["chain_%02d" % index],
                                 assets["material"], transform, row["hidden_in_game"],
                                  row["cast_hidden_shadow"], part, "CHAIN_LINK_%02d" % index, run))
    require(len(links) == 24, "CHAIN_ASSEMBLY_COUNT_24")
    return body, links


def _spawn_spot(plan: dict[str, Any], run: str) -> Any:
    row = plan["parts"]["opening"]["drive_by"]
    location = unreal.Vector(*plan["args"]["drive_by_light_location_cm"])
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        unreal.SpotLight, location, unreal.Rotator())
    require(actor is not None, "SPAWN_DRIVE_BY")
    actor.set_actor_label("P75 Opening Drive-By", mark_dirty=True)
    _tag(actor, "opening", "DRIVE_BY", run)
    component = actor.get_editor_property("spot_light_component")
    component.set_editor_property("intensity", 0.0)
    component.set_editor_property("outer_cone_angle", row["outer_cone_deg"])
    component.set_editor_property("soft_source_radius", row["soft_source_radius_cm"])
    component.set_editor_property("cast_shadows", True)
    component.set_light_color(unreal.LinearColor(*row["color_linear"], 1.0), True)
    actor.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(
        location, unreal.Vector(*row["target_start_cm"])), False)
    return actor


def _spawn_group_lights(plan: dict[str, Any], part: str, body: Any, run: str) -> list[Any]:
    rows = [row for row in plan["parts"][part]["lights"] if row["kind"] == "point"]
    actors = []
    for index, row in enumerate(rows):
        actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
            unreal.PointLight, body.get_actor_location(), unreal.Rotator())
        require(actor is not None, "SPAWN_POINT|" + row["label"])
        actor.set_actor_label(row["label"], mark_dirty=True)
        _tag(actor, part, "GROUP_LIGHT_%02d" % (index + 1), run)
        angle = math.tau * index / max(1, len(rows))
        actor.attach_to_actor(body, unreal.Name(), unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
        actor.set_actor_relative_location(unreal.Vector(85.0 * math.cos(angle),
                                                        85.0 * math.sin(angle), -15.0), False, False)
        component = actor.get_editor_property("point_light_component")
        intensity = plan["args"]["grouped_light_intensity_cd"] if row["enabled_default"] else 0.0
        component.set_editor_property("intensity", intensity)
        component.set_editor_property("attenuation_radius", plan["args"]["grouped_light_attenuation_cm"])
        component.set_editor_property("cast_shadows", row["cast_shadows"])
        actors.append(actor)
    return actors


def _bindings_for(sequence: Any, obj: Any, world: Any) -> list[Any]:
    target = _object_path(obj)
    hits = []
    for binding in sequence.get_bindings():
        try:
            if any(_object_path(value) == target for value in sequence.locate_bound_objects(binding, world)):
                hits.append(binding)
        except Exception:
            pass
    return hits


def _binding_for(sequence: Any, obj: Any, world: Any, label: str) -> tuple[Any, bool]:
    hits = _bindings_for(sequence, obj, world)
    require(len(hits) <= 1, "TARGET_BINDING_COUNT|%s|%d" % (label, len(hits)))
    if hits:
        return hits[0], False
    binding = sequence.add_possessable(obj)
    require(binding is not None, "ADD_POSSESSABLE|" + label)
    binding.set_display_name(label)
    return binding, True


def _track_prefix(part: str) -> str:
    return "P75 Chandelier %s [OWNED]" % part.title()


def _owned_tracks(binding: Any, part: str) -> list[Any]:
    return [track for track in binding.get_tracks()
            if str(track.get_display_name()).startswith(_track_prefix(part))]


def _float_track(sequence: Any, component: Any, world: Any, keys: list[tuple[float, float]],
                 duration_s: float) -> dict[str, Any]:
    binding, created = _binding_for(sequence, component, world, "P75 Opening Drive-By Component")
    require(not _owned_tracks(binding, "opening"), "OWNED_COMPONENT_TRACK_EXISTS")
    track = binding.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path("Intensity", "Intensity")
    track.set_display_name(_track_prefix("opening") + " DriveBy Intensity")
    section = track.add_section()
    section.set_range_seconds(0.0, duration_s)
    channels = list(section.get_channels())
    require(len(channels) == 1, "FLOAT_CHANNEL_COUNT")
    for seconds, value in keys:
        channels[0].add_key(unreal.FrameNumber(round(seconds * 25.0)), float(value))
    return {"binding_created": created, "keys": keys}


def _rotation_track(sequence: Any, actor: Any, world: Any, timed_rotations: list[tuple[float, Any]],
                    duration_s: float) -> dict[str, Any]:
    binding, created = _binding_for(sequence, actor, world, str(actor.get_actor_label()))
    require(not _owned_tracks(binding, "opening"), "OWNED_ROTATION_TRACK_EXISTS")
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    track.set_display_name(_track_prefix("opening") + " DriveBy Arc Rotation")
    section = track.add_section()
    section.set_range_seconds(0.0, duration_s)
    channels = {str(channel.get_name()).lower(): channel for channel in section.get_channels()}

    def pick(*needles: str) -> Any:
        hits = [channel for name, channel in channels.items() if any(needle in name for needle in needles)]
        require(len(hits) == 1, "ROTATION_CHANNEL|%s|%s" % (needles, sorted(channels)))
        return hits[0]

    roll_channel, pitch_channel, yaw_channel = (pick("rotation.x", "roll"),
                                                  pick("rotation.y", "pitch"),
                                                  pick("rotation.z", "yaw"))
    rows = []
    for seconds, rotation in timed_rotations:
        frame = unreal.FrameNumber(round(seconds * 25.0))
        roll_channel.add_key(frame, float(rotation.roll))
        pitch_channel.add_key(frame, float(rotation.pitch))
        yaw_channel.add_key(frame, float(rotation.yaw))
        rows.append([seconds, float(rotation.roll), float(rotation.pitch), float(rotation.yaw)])
    return {"binding_created": created, "rotation_keys": rows}


def _key_value(key: Any) -> Any:
    value = key.get_value()
    try:
        return float(value)
    except (TypeError, ValueError):
        return bool(value) if isinstance(value, bool) else str(value)


def _track_state(sequence: Any, part: str) -> list[dict[str, Any]]:
    rows = []
    for binding in sequence.get_bindings():
        for track in binding.get_tracks():
            name = str(track.get_display_name())
            if not name.startswith(_track_prefix(part)):
                continue
            sections = []
            for section in track.get_sections():
                channels = []
                for channel in section.get_channels():
                    keys = [[int(key.get_time().frame_number.value), _key_value(key)] for key in channel.get_keys()]
                    channels.append({"name": str(channel.get_name()), "keys": keys})
                sections.append(channels)
            rows.append({"binding": str(binding.get_display_name()), "track": name,
                         "class": track.get_class().get_name(), "sections": sections})
    return sorted(rows, key=lambda row: (row["binding"], row["track"]))


def _remove_owned_tracks(sequence: Any, part: str) -> int:
    removed = 0
    for binding in sequence.get_bindings():
        for track in list(binding.get_tracks()):
            if str(track.get_display_name()).startswith(_track_prefix(part)):
                binding.remove_track(track)
                removed += 1
    return removed


def _packages(part: str, args: dict[str, Any]) -> list[str]:
    return [WORLD, args.get("opening_sequence", OPENING_SEQUENCE)] if part == "opening" else [WORLD]


def _expected_dirty(part: str, args: dict[str, Any]) -> dict[str, list[str]]:
    content = [args.get("opening_sequence", OPENING_SEQUENCE)] if part == "opening" else []
    return {"content": content, "maps": [WORLD]}


def _save_named(packages: Iterable[str]) -> None:
    packages = list(packages)
    require(set(_census()["content"]) <= set(packages), "DIRTY_CONTENT_SCOPE|" + json.dumps(_census()))
    require(set(_census()["maps"]) <= {WORLD}, "DIRTY_MAP_SCOPE|" + json.dumps(_census()))
    for package in packages:
        if package != WORLD:
            require(unreal.EditorAssetLibrary.save_asset(package, only_if_is_dirty=False), "SAVE|" + package)
    if WORLD in packages:
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "SAVE_LEVEL")
    _require_clean("POST_SAVE")


def _cleanup_owned_actors(part: str, failed_run: str, expected_paths: set[str]) -> int:
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    candidates = []
    for actor in _actors():
        tags = _actor_tags(actor)
        if OWNER_TAG not in tags or _part_tag(part) not in tags:
            continue
        decision = cleanup_tag_decision(tags, part, failed_run)
        require(decision["eligible"], "CLEAN_FOREIGN_RUN|%s|%s" %
                (_object_path(actor), ",".join(decision["run_tags"])))
        candidates.append(actor)
    require({_object_path(actor) for actor in candidates} == expected_paths, "CLEAN_MATCH_SET_DRIFT")
    for actor in candidates:
        require(subsystem.destroy_actor(actor), "CLEAN_DESTROY_ACTOR|" + _object_path(actor))
    return len(candidates)


def _apply_opening_tracks(plan: dict[str, Any], sequence: Any, drive_by: Any, world: Any) -> list[dict[str, Any]]:
    row = plan["parts"]["opening"]["drive_by"]
    intensity = [(row["start_s"], 0.0), (row["peak_s"], row["peak_intensity_cd"]), (row["end_s"], 0.0)]
    written = [_float_track(sequence, drive_by.get_editor_property("spot_light_component"), world,
                            intensity, plan["args"]["opening_duration_s"])]
    location = unreal.Vector(*plan["args"]["drive_by_light_location_cm"])
    start, end = unreal.Vector(*row["target_start_cm"]), unreal.Vector(*row["target_end_cm"])
    middle = (start + end) * 0.5
    written.append(_rotation_track(sequence, drive_by, world,
        [(row["start_s"], unreal.MathLibrary.find_look_at_rotation(location, start)),
         (row["peak_s"], unreal.MathLibrary.find_look_at_rotation(location, middle)),
         (row["end_s"], unreal.MathLibrary.find_look_at_rotation(location, end))],
        plan["args"]["opening_duration_s"]))
    return written


def run(raw: dict[str, Any]) -> dict[str, Any]:
    run_id = _run_id()
    validated = CORE.validate_args(raw)
    _guard_result, world = _guard()
    dirty_before = _require_clean("PRE")
    args, parts = validated, validated["parts"]

    if args["mode"] in ("ADOPT_OR_CLEAN", "CLEAN"):
        part, failed_run = parts[0], args["cleanup_failed_run_id"]
        cleanup = _cleanup_report(part, failed_run)
        if args["mode"] == "ADOPT_OR_CLEAN":
            result = {"ok": True, "run": run_id, "mode": "ADOPT_OR_CLEAN", "mutated": False,
                      "query": "tags contain exact %s and %s; label/folder are diagnostic only" %
                               (OWNER_TAG, _part_tag(part)),
                      "cleanup": cleanup, "dirty_before": dirty_before}
            path = os.path.join(HERE, "chandelier_staging_ADOPT_OR_CLEAN_%s.json" % run_id)
            _write(path, result, exclusive=True)
            require(_census() == dirty_before, "ADOPT_OR_CLEAN_CHANGED_CENSUS")
            unreal.log("%s_ADOPT_OR_CLEAN_DRY_OK|run=%s|part=%s|matches=%d|eligible=%d|cleanup_sha256=%s|mutated=0|dirty=0+0|report=%s" %
                       (MARK, run_id, part, len(cleanup["matches"]),
                        sum(int(row["cleanup"]["eligible"]) for row in cleanup["matches"]),
                        cleanup["cleanup_sha256"], path))
            return result

        require(cleanup["matches"], "CLEAN_NO_MATCHES|" + part)
        require(all(row["cleanup"]["eligible"] for row in cleanup["matches"]),
                "CLEAN_HAS_FOREIGN_RUN|" + json.dumps(cleanup["matches"], sort_keys=True))
        require(args["reviewed_cleanup_sha256"] == cleanup["cleanup_sha256"],
                "REVIEWED_CLEANUP_HASH|expected=" + cleanup["cleanup_sha256"])
        require(not os.path.exists(_active_record(part)), "ACTIVE_RECORD_EXISTS|" + part)
        record_path = os.path.join(HERE, "chandelier_staging_cleanup_%s.json" % run_id)
        backup = _backup(run_id, part + "Cleanup", [WORLD],
                         "Before deleting only failed-run or legacy untagged P75-owned %s actors." % part)
        record = {"schema": "p75_chandelier_cleanup_v1", "status": "prepared", "run": run_id,
                  "failed_run": failed_run, "part": part, "cleanup_sha256": cleanup["cleanup_sha256"],
                  "before": cleanup, "backup": backup, "packages": [WORLD], "dirty_before": dirty_before}
        _write(record_path, record, exclusive=True)
        expected_paths = {row["object_path"] for row in cleanup["matches"]}
        removed = _cleanup_owned_actors(part, failed_run, expected_paths)
        presave = _cleanup_report(part, failed_run)
        require(not presave["matches"], "CLEAN_PRESAVE_ACTORS_REMAIN")
        require(_census() == {"content": [], "maps": [WORLD]},
                "CLEAN_DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
        record.update({"status": "cleaned_in_memory", "removed_actors": removed,
                       "presave_readback": presave})
        _write(record_path, record)
        _save_named([WORLD])
        post = _cleanup_report(part, failed_run)
        require(not post["matches"], "CLEAN_POSTSAVE_ACTORS_REMAIN")
        record.update({"status": "saved_readback_verified", "postsave_readback": post,
                       "dirty_after": _census()})
        _write(record_path, record)
        result = {"ok": True, "run": run_id, "mode": "CLEAN", "part": part,
                  "removed_actors": removed, "backup": backup, "record": record_path,
                  "dirty_after": _census()}
        _write(REPORT_PATH, result)
        unreal.log("%s_CLEAN_OK|run=%s|failed_run=%s|part=%s|actors=%d|saved=1|readback=1|dirty=0+0|backup=%s|record=%s" %
                   (MARK, run_id, failed_run, part, removed, backup["root"], record_path))
        return result

    chain_path = _chain_path(validated)
    chain_raw = _read(chain_path)
    plan = CORE.build_plan(raw, chain_raw)
    args, parts = plan["args"], plan["selected_parts"]
    assets = _load_assets(args, parts)
    existing_global = _live_light_rows()
    missing_parts = [part for part in parts if not _part_owned_states(part)]
    candidate = [row for part in missing_parts for row in plan["parts"][part]["lights"]]
    live_global_budget = CORE.validate_global_light_guard(existing_global + candidate)

    if args["mode"] == "DRY":
        require(_census() == dirty_before, "DRY_CHANGED_CENSUS")
        result = {"ok": True, "run": run_id, "mode": "DRY", "plan": plan,
                  "chain_json": chain_path, "verified_socket_names": assets["verified_socket_names"],
                  "existing_owned": {part: _part_owned_states(part) for part in CORE.PARTS},
                  "live_global_budget_with_candidates": live_global_budget,
                  "dirty_before": dirty_before}
        path = os.path.join(HERE, "chandelier_staging_DRY_%s.json" % run_id)
        _write(path, result)
        hashes = ",".join("%s:%s" % (part, plan["parts"][part]["plan_sha256"]) for part in parts)
        unreal.log("%s_DRY_OK|run=%s|parts=%s|plans=%s|global_lights=%d|global_casters=%d|links=24|flames=0|swing_keys=0|dirty=0+0|mutated=0" %
                   (MARK, run_id, ",".join(parts), hashes, live_global_budget["lights"],
                    live_global_budget["shadow_casters"]))
        return result

    part = parts[0]
    record_path = _active_record(part)
    packages = _packages(part, args)
    sequence = assets.get("opening_sequence")
    if args["mode"] == "APPLY":
        require(not os.path.exists(record_path), "ACTIVE_RECORD_EXISTS|" + part)
        require(not _part_owned_states(part), "OWNED_ACTORS_EXIST|" + part)
        backup = _backup(run_id, part, packages, "Before P75 %s body, 24 chain links, lights and owned drive-by tracks." % part)
        record = {"schema": "p75_chandelier_part_active_v2", "status": "prepared", "part": part,
                  "run": run_id, "part_plan_sha256": plan["parts"][part]["plan_sha256"],
                  "plan": plan, "packages": packages, "backup": backup, "dirty_before": dirty_before}
        _write(record_path, record, exclusive=True)
        body, links = _spawn_assembly(plan, assets, part, run_id)
        lights = _spawn_group_lights(plan, part, body, run_id)
        tracks_written = []
        if part == "opening":
            drive_by = _spawn_spot(plan, run_id)
            lights.append(drive_by)
            tracks_written = _apply_opening_tracks(plan, sequence, drive_by, world)
            CORE.verify_hidden_shadow(_actor_state(body)["mesh_flags"],
                                      [_actor_state(actor)["mesh_flags"] for actor in links])
        CORE.validate_global_light_guard(_live_light_rows())
        require(_census() == _expected_dirty(part, args),
                "APPLY_DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
        _save_named(packages)
        readback = {"actors": _part_owned_states(part),
                    "tracks": _track_state(sequence, part) if part == "opening" else []}
        expected_actors = 25 + len(plan["parts"][part]["lights"])
        require(len(readback["actors"]) == expected_actors, "READBACK_ACTOR_COUNT")
        require(len(readback["tracks"]) == (2 if part == "opening" else 0), "READBACK_TRACK_COUNT")
        _verify_part_readback(plan, part, readback["actors"])
        record.update({"status": "applied", "readback": readback,
                       "tracks_written": tracks_written,
                       "instance_actor_labels": plan["instance_actor_labels"][part]})
        _write(record_path, record)
        result = {"ok": True, "mode": "APPLY", "part": part, "run": run_id,
                  "part_plan_sha256": plan["parts"][part]["plan_sha256"], "backup": backup,
                  "readback": readback, "global_light_budget": CORE.validate_global_light_guard(_live_light_rows()),
                  "dirty_after": _census(), "record": record_path}
        _write(REPORT_PATH, result)
        unreal.log("%s_APPLY_OK|run=%s|part=%s|actors=%d|tracks=%d|global_lights=%d|global_casters=%d|flames=0|swing_keys=0|saved=%d|readback=1|dirty=0+0|record=%s" %
                   (MARK, run_id, part, len(readback["actors"]), len(readback["tracks"]),
                    result["global_light_budget"]["lights"], result["global_light_budget"]["shadow_casters"],
                    len(packages), record_path))
        return result

    require(os.path.isfile(record_path), "ACTIVE_RECORD_MISSING|" + part)
    record = _read(record_path)
    require(record.get("status") == "applied" and record.get("part") == part, "ACTIVE_RECORD_STATUS")
    require(_actor_states_match(record["readback"]["actors"], _part_owned_states(part)),
            "REVERT_ACTOR_DRIFT|" + part)
    if part == "opening":
        require(_nested_matches(record["readback"]["tracks"], _track_state(sequence, part)),
                "REVERT_TRACK_DRIFT|opening")
    backup = _backup(run_id, part, packages, "Immediately before P75 %s isolated REVERT." % part)
    removed_tracks = _remove_owned_tracks(sequence, part) if part == "opening" else 0
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    owned = [actor for actor in _actors()
             if OWNER_TAG in _actor_tags(actor) and _part_tag(part) in _actor_tags(actor)]
    for actor in owned:
        require(subsystem.destroy_actor(actor), "DESTROY_ACTOR|" + str(actor.get_actor_label()))
    require(_census() == _expected_dirty(part, args),
            "REVERT_DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
    _save_named(packages)
    require(not _part_owned_states(part), "REVERT_ACTORS_REMAIN|" + part)
    require(part != "opening" or not _track_state(sequence, part), "REVERT_TRACKS_REMAIN|opening")
    archive = record_path.replace("_ACTIVE.json", "_REVERTED_%s.json" % run_id)
    record.update({"status": "reverted", "revert_run": run_id, "revert_backup": backup,
                   "removed_actors": len(owned), "removed_tracks": removed_tracks})
    _write(record_path, record)
    os.replace(record_path, archive)
    result = {"ok": True, "mode": "REVERT", "part": part, "run": run_id,
              "removed_actors": len(owned), "removed_tracks": removed_tracks,
              "archive": archive, "global_light_budget": CORE.validate_global_light_guard(_live_light_rows()),
              "dirty_after": _census()}
    _write(REPORT_PATH, result)
    unreal.log("%s_REVERT_OK|run=%s|part=%s|actors=%d|tracks=%d|global_lights=%d|global_casters=%d|saved=%d|readback=1|dirty=0+0|record=%s" %
               (MARK, run_id, part, len(owned), removed_tracks,
                result["global_light_budget"]["lights"], result["global_light_budget"]["shadow_casters"],
                len(packages), archive))
    return result


if unreal is not None and __name__ == "__main__":
    try:
        run(_read(ARGS_PATH))
    except Exception as error:  # noqa: BLE001 - preserve exact stop reason for the conductor.
        unreal.log_error("%s_STOPPED|%s|do not Save All; inspect exact census" % (MARK, error))
        raise
