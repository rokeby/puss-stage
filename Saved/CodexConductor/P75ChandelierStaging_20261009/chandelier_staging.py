"""Later-live UE 5.8 DRY/APPLY/REVERT tool for P75.

The file is safe to import offline.  It creates no assets: it reuses the Iron3
meshes and the P56 candle Blueprint, owns only tagged level actors and named
Sequencer tracks, and saves only the level plus the two named sequences.
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
ACTIVE_RECORD = os.path.join(HERE, "chandelier_staging_ACTIVE.json")
REPORT_PATH = os.path.join(HERE, "chandelier_staging_report.json")
SPEC = importlib.util.spec_from_file_location("p75_core", os.path.join(HERE, "chandelier_staging_core.py"))
CORE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CORE)

MARK = "P75_CHANDELIER"
OWNER_TAG = "P75_CHANDELIER_STAGING"
OPENING_SEQUENCE = "/Game/InfinityStage/Interactions/LS_Opening_Curtain_Baked"
P06_SEQUENCE = "/Game/InfinityStage/Choreo/LS_Choreo_Passage_6"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PASSAGE_LABEL = "Passage 6"
TRACK_PREFIX = "P75 Chandelier [OWNED]"


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


def _asset_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value.get_path_name()) if hasattr(value, "get_path_name") else str(value)
    return text.split(".", 1)[0]


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


def _backup(run: str, packages: Iterable[str], note: str) -> dict[str, Any]:
    root = os.path.join(_project_dir(), "Backups", "PreP75Chandelier-" + run)
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
    manifest = {"run": run, "note": note, "packages": rows}
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


def _find_actor(label: str) -> Any:
    hits = [actor for actor in _actors() if str(actor.get_actor_label()) == label]
    require(len(hits) == 1, "ACTOR_COUNT|%s|%d" % (label, len(hits)))
    return hits[0]


def _passage6() -> Any:
    actor = _find_actor(PASSAGE_LABEL)
    route = actor.get_editor_property("route")
    require(route is not None, "P06_ROUTE_MISSING")
    return actor


def _route_transform(plan: dict[str, Any]) -> Any:
    route = _passage6().get_editor_property("route")
    transform = route.get_transform_at_distance_along_spline(
        plan["p06"]["hang_station_cm"], unreal.SplineCoordinateSpace.WORLD, True)
    location = transform.translation
    across = transform.rotation.rotate_vector(unreal.Vector(0.0, 1.0, 0.0))
    location = location + across * plan["p06"]["lateral_cm"] + unreal.Vector(0.0, 0.0, plan["p06"]["hang_z_cm"])
    return unreal.Transform(location, transform.rotation.rotator(), unreal.Vector(1.0, 1.0, 1.0))


def _load_assets(args: dict[str, Any]) -> dict[str, Any]:
    paths = {"body_mesh": args["body_mesh"], "chain_mesh": args["chain_mesh"],
             "candle_blueprint": args["candle_blueprint"],
             "opening_sequence": args.get("opening_sequence", OPENING_SEQUENCE),
             "p06_sequence": args.get("p06_sequence", P06_SEQUENCE)}
    loaded = {key: unreal.load_asset(path) for key, path in paths.items()}
    for key, value in loaded.items():
        require(value is not None, "ASSET_MISSING|%s|%s" % (key, paths[key]))
    return loaded


def _component_state(component: Any) -> dict[str, Any]:
    return {"hidden_in_game": bool(component.get_editor_property("hidden_in_game")),
            "cast_hidden_shadow": bool(component.get_editor_property("cast_hidden_shadow")),
            "cast_shadow": bool(component.get_editor_property("cast_shadow"))}


def _actor_state(actor: Any) -> dict[str, Any]:
    location = actor.get_actor_location()
    rotation = actor.get_actor_rotation()
    meshes = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    lights = list(actor.get_components_by_class(unreal.LightComponent))
    return {"label": str(actor.get_actor_label()),
            "tags": sorted(str(tag) for tag in actor.get_editor_property("tags")),
            "location_cm": [float(location.x), float(location.y), float(location.z)],
            "rotation_deg": [float(rotation.roll), float(rotation.pitch), float(rotation.yaw)],
            "mesh": _asset_id(meshes[0].get_editor_property("static_mesh")) if meshes else None,
            "mesh_flags": _component_state(meshes[0]) if meshes else None,
            "light": ({"intensity": float(lights[0].get_editor_property("intensity")),
                       "cast_shadows": bool(lights[0].get_editor_property("cast_shadows"))}
                      if lights else None)}


def _owned_states() -> list[dict[str, Any]]:
    rows = [_actor_state(actor) for actor in _actors()
            if OWNER_TAG in {str(tag) for tag in actor.get_editor_property("tags")}]
    return sorted(rows, key=lambda row: row["label"])


def _tag(actor: Any, role: str) -> None:
    actor.set_editor_property("tags", [unreal.Name(OWNER_TAG), unreal.Name("P75_ROLE_" + role)])


def _spawn_mesh(label: str, mesh: Any, transform: Any, hidden: bool, hidden_shadow: bool, role: str) -> Any:
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, transform.translation, transform.rotation.rotator())
    require(actor is not None, "SPAWN_MESH|" + label)
    actor.set_actor_label(label, mark_dirty=True)
    _tag(actor, role)
    component = actor.get_editor_property("static_mesh_component")
    component.set_editor_property("static_mesh", mesh)
    component.set_editor_property("hidden_in_game", hidden)
    component.set_editor_property("cast_shadow", True)
    component.set_editor_property("cast_hidden_shadow", hidden_shadow)
    component.set_collision_profile_name("NoCollision")
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    return actor


def _spawn_spot(label: str, plan: dict[str, Any]) -> Any:
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    row = plan["opening"]["drive_by"]
    location = unreal.Vector(*plan["args"]["drive_by_light_location_cm"])
    actor = subsystem.spawn_actor_from_class(unreal.SpotLight, location, unreal.Rotator())
    require(actor is not None, "SPAWN_DRIVE_BY")
    actor.set_actor_label(label, mark_dirty=True)
    _tag(actor, "OPENING_DRIVE_BY")
    component = actor.get_editor_property("spot_light_component")
    component.set_editor_property("intensity", 0.0)
    component.set_editor_property("outer_cone_angle", row["outer_cone_deg"])
    component.set_editor_property("soft_source_radius", row["soft_source_radius_cm"])
    component.set_editor_property("cast_shadows", True)
    component.set_light_color(unreal.LinearColor(*row["color_linear"], 1.0), True)
    actor.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(location, unreal.Vector(*row["target_start_cm"])), False)
    return actor


def _spawn_point(label: str, parent: Any, index: int, plan: dict[str, Any]) -> Any:
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(unreal.PointLight, parent.get_actor_location(), unreal.Rotator())
    require(actor is not None, "SPAWN_POINT|" + label)
    actor.set_actor_label(label, mark_dirty=True)
    _tag(actor, "GROUP_LIGHT_%02d" % index)
    angle = math.tau * index / max(1, plan["lights"]["grouped_count"])
    actor.attach_to_actor(parent, unreal.Name(), unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    actor.set_actor_relative_location(unreal.Vector(85.0 * math.cos(angle), 85.0 * math.sin(angle), -15.0), False, False)
    component = actor.get_editor_property("point_light_component")
    component.set_editor_property("intensity", plan["lights"]["intensity_cd"])
    component.set_editor_property("attenuation_radius", plan["lights"]["attenuation_cm"])
    component.set_editor_property("cast_shadows", index < plan["lights"]["shadow_casters"])
    return actor


def _socket_name(component: Any, index: int) -> str:
    candidates = ("Candle_%02d" % index, "SOCKET_Candle_%02d" % index)
    hits = [name for name in candidates if component.does_socket_exist(unreal.Name(name))]
    require(len(hits) == 1, "SOCKET_LOOKUP|%02d|%s" % (index, hits))
    return hits[0]


def _spawn_candles(parent: Any, candle_class: Any, prefix: str, count: int) -> list[Any]:
    mesh_component = parent.get_editor_property("static_mesh_component")
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rows = []
    for index in range(1, count + 1):
        socket = _socket_name(mesh_component, index)
        actor = subsystem.spawn_actor_from_class(candle_class, parent.get_actor_location(), unreal.Rotator())
        require(actor is not None, "SPAWN_CANDLE|" + socket)
        actor.set_actor_label("P75_%s_Candle_%02d" % (prefix, index), mark_dirty=True)
        _tag(actor, "%s_CANDLE_%02d" % (prefix, index))
        require(actor.attach_to_component(mesh_component, unreal.Name(socket),
                                          unreal.AttachmentRule.SNAP_TO_TARGET,
                                          unreal.AttachmentRule.SNAP_TO_TARGET,
                                          unreal.AttachmentRule.KEEP_RELATIVE, False), "ATTACH_CANDLE|" + socket)
        rows.append(actor)
    return rows


def _binding_for(sequence: Any, actor: Any, label_override: str | None = None) -> tuple[Any, bool]:
    label = label_override or (str(actor.get_actor_label()) if hasattr(actor, "get_actor_label")
                               else TRACK_PREFIX + " Component " + str(actor.get_name()))
    hits = [binding for binding in sequence.get_bindings() if str(binding.get_display_name()) == label]
    require(len(hits) <= 1, "DUPLICATE_BINDING|" + label)
    if hits:
        return hits[0], False
    binding = sequence.add_possessable(actor)
    require(binding is not None, "ADD_POSSESSABLE|" + label)
    binding.set_display_name(label)
    return binding, True


def _owned_tracks(binding: Any) -> list[Any]:
    return [track for track in binding.get_tracks()
            if str(track.get_display_name()).startswith(TRACK_PREFIX)]


def _visibility_track(sequence: Any, actor: Any, keys: list[tuple[float, bool]], duration_s: float,
                      role: str) -> dict[str, Any]:
    binding, created = _binding_for(sequence, actor)
    require(not _owned_tracks(binding), "OWNED_TRACK_EXISTS|" + str(actor.get_actor_label()))
    track = binding.add_track(unreal.MovieSceneVisibilityTrack)
    track.set_property_name_and_path("bHidden", "bHidden")
    track.set_display_name("%s %s Visibility" % (TRACK_PREFIX, role))
    section = track.add_section()
    section.set_range_seconds(0.0, duration_s)
    channels = list(section.get_channels())
    require(len(channels) == 1, "VISIBILITY_CHANNEL_COUNT")
    for seconds, visible in keys:
        channels[0].add_key(unreal.FrameNumber(round(seconds * 25.0)), bool(visible))
    return {"actor": str(actor.get_actor_label()), "role": role, "binding_created": created,
            "property": ["bHidden", "bHidden"], "visible_keys": keys}


def _float_track(sequence: Any, component: Any, property_name: str, keys: list[tuple[float, float]],
                 duration_s: float, role: str) -> dict[str, Any]:
    binding, created = _binding_for(sequence, component, TRACK_PREFIX + " Component " + role)
    require(not _owned_tracks(binding), "OWNED_COMPONENT_TRACK_EXISTS|" + role)
    track = binding.add_track(unreal.MovieSceneFloatTrack)
    track.set_property_name_and_path(property_name, property_name)
    track.set_display_name("%s %s" % (TRACK_PREFIX, role))
    section = track.add_section()
    section.set_range_seconds(0.0, duration_s)
    channels = list(section.get_channels())
    require(len(channels) == 1, "FLOAT_CHANNEL_COUNT|" + role)
    for seconds, value in keys:
        channels[0].add_key(unreal.FrameNumber(round(seconds * 25.0)), float(value))
    return {"role": role, "binding_created": created, "keys": keys}


def _rotation_track(sequence: Any, actor: Any, timed_rotations: list[tuple[float, Any]],
                    duration_s: float, role: str) -> dict[str, Any]:
    binding, created = _binding_for(sequence, actor)
    require(not _owned_tracks(binding), "OWNED_ROTATION_TRACK_EXISTS|" + role)
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    track.set_display_name("%s %s Arc Rotation" % (TRACK_PREFIX, role))
    section = track.add_section()
    section.set_range_seconds(0.0, duration_s)
    channels = {str(channel.get_name()).lower(): channel for channel in section.get_channels()}

    def pick(*needles: str) -> Any:
        hits = [channel for name, channel in channels.items() if any(needle in name for needle in needles)]
        require(len(hits) == 1, "ROTATION_CHANNEL|%s|%s" % (needles, sorted(channels)))
        return hits[0]

    roll_channel = pick("rotation.x", "roll")
    pitch_channel = pick("rotation.y", "pitch")
    yaw_channel = pick("rotation.z", "yaw")
    rows = []
    for seconds, rotation in timed_rotations:
        frame = unreal.FrameNumber(round(seconds * 25.0))
        roll_channel.add_key(frame, float(rotation.roll))
        pitch_channel.add_key(frame, float(rotation.pitch))
        yaw_channel.add_key(frame, float(rotation.yaw))
        rows.append([seconds, float(rotation.roll), float(rotation.pitch), float(rotation.yaw)])
    return {"role": role, "binding_created": created, "rotation_keys": rows}


def _track_state(sequence: Any) -> list[dict[str, Any]]:
    rows = []
    for binding in sequence.get_bindings():
        for track in binding.get_tracks():
            name = str(track.get_display_name())
            if name.startswith(TRACK_PREFIX):
                rows.append({"binding": str(binding.get_display_name()), "track": name,
                             "class": track.get_class().get_name(),
                             "sections": len(track.get_sections())})
    return sorted(rows, key=lambda row: (row["binding"], row["track"]))


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


def _remove_owned_tracks(sequence: Any) -> int:
    removed = 0
    for binding in sequence.get_bindings():
        for track in list(binding.get_tracks()):
            if str(track.get_display_name()).startswith(TRACK_PREFIX):
                binding.remove_track(track)
                removed += 1
    return removed


def run(raw: dict[str, Any]) -> dict[str, Any]:
    run_id = _run_id()
    plan = CORE.build_plan(raw)
    args = plan["args"]
    _guard()
    dirty_before = _require_clean("PRE")
    assets = _load_assets(raw)
    packages = [WORLD, args.get("opening_sequence", OPENING_SEQUENCE), args.get("p06_sequence", P06_SEQUENCE)]
    existing = _owned_states()
    dry = {"ok": True, "run": run_id, "mode": args["mode"], "plan": plan,
           "packages": packages, "existing_owned": existing, "dirty_before": dirty_before,
           "live_checks": {"assets": sorted(assets), "world": WORLD,
                           "p06_route": _asset_id(_passage6())}}
    if args["mode"] == "DRY":
        require(_census() == dirty_before, "DRY_CHANGED_CENSUS")
        path = os.path.join(HERE, "chandelier_staging_DRY_%s.json" % run_id)
        _write(path, dry)
        unreal.log("%s_DRY_OK|run=%s|plan=%s|opening_shadow=%.2f-%.2f|candles=44|lights=%d|casters=%d|p06_station=%.1f|topple_clearance=%.1f|dirty=0+0|mutated=0" %
                   (MARK, run_id, plan["plan_sha256"], plan["opening"]["drive_by"]["start_s"],
                    plan["opening"]["drive_by"]["end_s"], plan["lights"]["grouped_count"],
                    plan["lights"]["shadow_casters"], plan["p06"]["hang_station_cm"],
                    plan["p06"]["clearances_cm"]["nearest_topple_row"]))
        return dry

    if args["mode"] == "APPLY":
        require(not os.path.exists(ACTIVE_RECORD), "ACTIVE_RECORD_EXISTS")
        require(not existing, "OWNED_ACTORS_EXIST")
        backup = _backup(run_id, packages, "Before P75 body, chain, light, candle and sequence staging.")
        record = {"schema": "p75_chandelier_active_v1", "status": "prepared", "run": run_id,
                  "plan": plan, "packages": packages, "backup": backup, "dirty_before": dirty_before}
        _write(ACTIVE_RECORD, record, exclusive=True)  # disk record before the first Unreal mutation
        opening_transform = unreal.Transform(unreal.Vector(*plan["opening"]["body"]["location_cm"]),
                                             unreal.Rotator(*plan["opening"]["body"]["rotation_deg"]),
                                             unreal.Vector(1.0, 1.0, 1.0))
        opening_body = _spawn_mesh("P75 Opening Chandelier", assets["body_mesh"], opening_transform, True, True, "OPENING_BODY")
        opening_chain = _spawn_mesh("P75 Opening Chandelier Chain", assets["chain_mesh"], opening_transform, True, True, "OPENING_CHAIN")
        p06_transform = _route_transform(plan)
        p06_body = _spawn_mesh("P75 P06 Chandelier", assets["body_mesh"], p06_transform, False, False, "P06_BODY")
        p06_chain = _spawn_mesh("P75 P06 Chandelier Chain", assets["chain_mesh"], p06_transform, False, False, "P06_CHAIN")
        candle_class = assets["candle_blueprint"].generated_class()
        require(candle_class is not None, "CANDLE_CLASS")
        opening_candles = _spawn_candles(opening_body, candle_class, "Opening", 44)
        p06_candles = _spawn_candles(p06_body, candle_class, "P06", 44)
        drive_by = _spawn_spot("P75 Opening Drive-By", plan)
        group_lights = [_spawn_point("P75 Opening Candle Group %02d" % (index + 1), opening_body, index, plan)
                        for index in range(plan["lights"]["grouped_count"])]
        p06_group_lights = [_spawn_point("P75 P06 Candle Group %02d" % (index + 1), p06_body, index, plan)
                            for index in range(plan["lights"]["grouped_count"])]
        opening_tracks = []
        intensity_keys = [(plan["opening"]["drive_by"]["start_s"], 0.0),
                          (plan["opening"]["drive_by"]["peak_s"], plan["opening"]["drive_by"]["peak_intensity_cd"]),
                          (plan["opening"]["drive_by"]["end_s"], 0.0)]
        opening_tracks.append(_float_track(assets["opening_sequence"], drive_by.get_editor_property("spot_light_component"),
                                           "Intensity", intensity_keys, plan["opening"]["duration_s"], "DriveBy Intensity"))
        drive_location = unreal.Vector(*plan["args"]["drive_by_light_location_cm"])
        target_start = unreal.Vector(*plan["opening"]["drive_by"]["target_start_cm"])
        target_end = unreal.Vector(*plan["opening"]["drive_by"]["target_end_cm"])
        target_mid = (target_start + target_end) * 0.5
        opening_tracks.append(_rotation_track(
            assets["opening_sequence"], drive_by,
            [(plan["opening"]["drive_by"]["start_s"], unreal.MathLibrary.find_look_at_rotation(drive_location, target_start)),
             (plan["opening"]["drive_by"]["peak_s"], unreal.MathLibrary.find_look_at_rotation(drive_location, target_mid)),
             (plan["opening"]["drive_by"]["end_s"], unreal.MathLibrary.find_look_at_rotation(drive_location, target_end))],
            plan["opening"]["duration_s"], "DriveBy"))
        opening_light_keys = [(0.0, 0.0), (plan["opening"]["candles"][0]["time_s"], 0.0)]
        opening_light_keys.extend((time_s, scale * plan["lights"]["intensity_cd"])
                                  for time_s, scale in plan["lights"]["opening_flicker_scale_keys"])
        for index, light in enumerate(group_lights, 1):
            opening_tracks.append(_float_track(assets["opening_sequence"], light.get_editor_property("point_light_component"),
                                               "Intensity", opening_light_keys, plan["opening"]["duration_s"],
                                               "Opening Group %02d Intensity" % index))
        candle_by_socket = {int(str(actor.get_actor_label())[-2:]): actor for actor in opening_candles}
        for row in plan["opening"]["candles"]:
            index = int(row["socket"].split("_")[-1])
            opening_tracks.append(_visibility_track(assets["opening_sequence"], candle_by_socket[index],
                                                     [(0.0, False), (row["time_s"], True)],
                                                     plan["opening"]["duration_s"], "Opening Candle %02d" % index))
        p06_tracks = []
        for actor, role in ((p06_body, "P06 Body"), (p06_chain, "P06 Chain")):
            p06_tracks.append(_visibility_track(assets["p06_sequence"], actor,
                                                [(0.0, False), (plan["p06"]["visible_start_s"], True)],
                                                plan["p06"]["duration_s"], role))
        for index, actor in enumerate(p06_candles, 1):
            p06_tracks.append(_visibility_track(assets["p06_sequence"], actor,
                                                [(0.0, False), (plan["p06"]["candle_start_s"], True)],
                                                plan["p06"]["duration_s"], "P06 Candle %02d" % index))
        p06_light_keys = [(0.0, 0.0), (plan["p06"]["candle_start_s"], 0.0)]
        p06_light_keys.extend((time_s, scale * plan["lights"]["intensity_cd"])
                              for time_s, scale in plan["lights"]["p06_flicker_scale_keys_0_30"])
        for index, light in enumerate(p06_group_lights, 1):
            p06_tracks.append(_float_track(assets["p06_sequence"], light.get_editor_property("point_light_component"),
                                           "Intensity", p06_light_keys, plan["p06"]["duration_s"],
                                           "P06 Group %02d Intensity" % index))
        expected_content = sorted([packages[1], packages[2]])
        require(_census() == {"content": expected_content, "maps": [WORLD]},
                "APPLY_DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
        _save_named(packages)
        readback = {"actors": _owned_states(), "opening_tracks": _track_state(assets["opening_sequence"]),
                    "p06_tracks": _track_state(assets["p06_sequence"])}
        require(len(readback["actors"]) == 4 + 44 + 44 + 1 + len(group_lights) + len(p06_group_lights),
                "READBACK_ACTOR_COUNT")
        CORE.verify_hidden_shadow(_actor_state(opening_body)["mesh_flags"], _actor_state(opening_chain)["mesh_flags"])
        record.update({"status": "applied", "readback": readback, "opening_tracks_written": opening_tracks,
                       "p06_tracks_written": p06_tracks})
        _write(ACTIVE_RECORD, record)
        result = {"ok": True, "mode": "APPLY", "run": run_id, "plan_sha256": plan["plan_sha256"],
                  "backup": backup, "readback": readback, "dirty_after": _census()}
        _write(REPORT_PATH, result)
        unreal.log("%s_APPLY_OK|run=%s|actors=%d|opening_tracks=%d|p06_tracks=%d|saved=3|readback=1|dirty=0+0" %
                   (MARK, run_id, len(readback["actors"]), len(readback["opening_tracks"]), len(readback["p06_tracks"])))
        return result

    require(os.path.isfile(ACTIVE_RECORD), "ACTIVE_RECORD_MISSING")
    record = _read(ACTIVE_RECORD)
    require(record.get("status") == "applied", "ACTIVE_RECORD_STATUS")
    require(_owned_states() == record["readback"]["actors"], "REVERT_ACTOR_DRIFT")
    require(_track_state(assets["opening_sequence"]) == record["readback"]["opening_tracks"], "REVERT_OPENING_TRACK_DRIFT")
    require(_track_state(assets["p06_sequence"]) == record["readback"]["p06_tracks"], "REVERT_P06_TRACK_DRIFT")
    backup = _backup(run_id, packages, "Immediately before P75 tagged actor and owned track revert.")
    removed_tracks = _remove_owned_tracks(assets["opening_sequence"]) + _remove_owned_tracks(assets["p06_sequence"])
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    owned = [actor for actor in _actors() if OWNER_TAG in {str(tag) for tag in actor.get_editor_property("tags")}]
    for actor in owned:
        require(subsystem.destroy_actor(actor), "DESTROY_ACTOR|" + str(actor.get_actor_label()))
    require(_census() == {"content": sorted([packages[1], packages[2]]), "maps": [WORLD]},
            "REVERT_DIRTY_SCOPE|" + json.dumps(_census(), sort_keys=True))
    _save_named(packages)
    require(not _owned_states(), "REVERT_ACTORS_REMAIN")
    require(not _track_state(assets["opening_sequence"]) and not _track_state(assets["p06_sequence"]),
            "REVERT_TRACKS_REMAIN")
    archive = ACTIVE_RECORD.replace("_ACTIVE.json", "_REVERTED_%s.json" % run_id)
    record.update({"status": "reverted", "revert_run": run_id, "revert_backup": backup,
                   "removed_actors": len(owned), "removed_tracks": removed_tracks})
    _write(ACTIVE_RECORD, record)
    os.replace(ACTIVE_RECORD, archive)
    result = {"ok": True, "mode": "REVERT", "run": run_id, "removed_actors": len(owned),
              "removed_tracks": removed_tracks, "archive": archive, "dirty_after": _census()}
    _write(REPORT_PATH, result)
    unreal.log("%s_REVERT_OK|run=%s|actors=%d|tracks=%d|saved=3|readback=1|dirty=0+0" %
               (MARK, run_id, len(owned), removed_tracks))
    return result


if unreal is not None and __name__ == "__main__":
    try:
        run(_read(ARGS_PATH))
    except Exception as error:  # noqa: BLE001 - preserve exact stop reason for the conductor.
        unreal.log_error("%s_STOPPED|%s|do not Save All; inspect exact census" % (MARK, error))
        raise
