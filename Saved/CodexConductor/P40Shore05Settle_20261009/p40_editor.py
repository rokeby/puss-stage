"""Guarded conductor-run editor tool for P40; written and tested offline only.

DRY plans one mandatory Shore05 plus 0..5 seeded variants, reads live B-shot
camera transform keys, audits the six cloth templates and outfit parameters, and
writes a report without changing Unreal state. APPLY/REVERT require confirm
strings, a clean exact census, a pre-change record and Backups/PreP40Shore-<run>.
Only the level, LS_Clams, opted-in BP templates, and newly-created outfit MI
children are saved. Existing material masters are never edited or deleted.

Cloth limitation: UE 5.8 exposes teleport/reset and thresholds but no component
warm-up/pre-roll property.  The optional template policy is therefore OFF by
default and needs an explicit acknowledgement that reset-on-auto-teleport is an
inferred behavior. It is not represented as proof of a settled first frame.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil
import sys
import traceback

try:
    import unreal
except ModuleNotFoundError:  # offline harness imports safely
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p40_core as core  # noqa: E402

ARGS = os.path.join(HERE, "p40_args.json")
RECORD = os.path.join(HERE, "p40_apply_record.json")
DRY_OUT = os.path.join(HERE, "p40_dry_latest.json")
VERIFY_OUT = os.path.join(HERE, "p40_verify_latest.json")
TAG = "P40.ShoreFigure"
OUTFIT_DIR = "/Game/Metahuman/ShoreCast_20260910/OutfitHessian"
MAP_FILE = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
CLAMS_FILE = "Content/Scenes/LS_Clams.uasset"


class Stop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")


def path_of(obj):
    if obj is None:
        return None
    return str(obj.get_path_name()).split(".", 1)[0]


def full_path(obj):
    return None if obj is None else str(obj.get_path_name())


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def clean_context(require_clean):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(ed.get_game_world() is None, "PIE_OR_SIE_RUNNING")
    world = ed.get_editor_world()
    require(path_of(world) == core.WORLD, "WRONG_WORLD|%s" % path_of(world))
    if require_clean:
        require(census() == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % json.dumps(census()))
    actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    return world, actors


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def project_path(relative):
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.normpath(os.path.join(root, relative))


def package_file(package, extension):
    return project_path(os.path.join("Content", package[len("/Game/"):].replace("/", os.sep) + extension))


def backup(run, bp_packages):
    root = project_path(os.path.join("Backups", "PreP40Shore-" + run))
    require(not os.path.exists(root), "BACKUP_EXISTS|" + root)
    os.makedirs(root)
    sources = [(core.WORLD, package_file(core.WORLD, ".umap")),
               (core.CLAMS, package_file(core.CLAMS, ".uasset"))]
    sources += [(p, package_file(p, ".uasset")) for p in bp_packages]
    rows = []
    for package, src in sources:
        require(os.path.isfile(src), "BACKUP_SOURCE_MISSING|" + src)
        dst = os.path.join(root, os.path.relpath(src, project_path("Content")))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        require(sha_file(src) == sha_file(dst), "BACKUP_HASH|" + package)
        rows.append({"package": package, "source": src, "backup": dst,
                     "bytes": os.path.getsize(dst), "sha256": sha_file(dst)})
    return {"root": root, "files": rows}


def actor_index(actors):
    out = {}
    for actor in actors:
        out.setdefault(str(actor.get_actor_label()), []).append(actor)
    return out


def shore_id_from_class(actor):
    name = str(actor.get_class().get_name())
    for figure in core.FIGURES:
        if name == "BP_%s_Draped_C" % figure:
            return figure
    return None


def actor_inventory(actors):
    rows = []
    for actor in actors:
        figure = shore_id_from_class(actor)
        if figure or TAG in {str(x) for x in prop(actor, "tags", [])} or str(actor.get_actor_label()).startswith("S3 Crowd"):
            loc = actor.get_actor_location()
            rows.append({"label": str(actor.get_actor_label()), "figure": figure,
                         "class": str(actor.get_class().get_name()), "path": full_path(actor),
                         "location": [float(loc.x), float(loc.y), float(loc.z)]})
    return rows


def channel_name(channel):
    return str(channel.get_name()).split(" (", 1)[0]


def channel_key_frames(channel):
    return [int(key.get_time().frame_number.value) for key in channel.get_keys()]


def value_at(sequence, channel, frame, fallback):
    if channel is None:
        return fallback
    values = list(channel.evaluate_keys(sequence.make_range(int(frame), 1), sequence.get_display_rate()))
    require(len(values) == 1, "CAMERA_CHANNEL_EVALUATION|frame=%d|count=%d" % (frame, len(values)))
    return float(values[0])


def camera_samples(sequence):
    """Read all B-shot spawnable templates and every keyed transform time."""
    rows = []
    labels = []
    for binding in sequence.get_spawnables():
        label = str(binding.get_display_name())
        if not label.startswith("S3 Shot B"):
            continue
        labels.append(label)
        template = binding.get_object_template()
        require(template is not None and isinstance(template, unreal.CineCameraActor),
                "CAMERA_TEMPLATE|" + label)
        root = template.get_editor_property("root_component")
        loc = root.get_editor_property("relative_location")
        rotation = root.get_editor_property("relative_rotation")
        base = {"Location.X": float(loc.x), "Location.Y": float(loc.y), "Rotation.Z": float(rotation.yaw)}
        transform_tracks = [t for t in binding.get_tracks()
                            if str(t.get_class().get_name()) == "MovieScene3DTransformTrack"]
        if len(transform_tracks) > 1:
            raise Stop("CAMERA_TRANSFORM_TRACKS|%s|%d" % (label, len(transform_tracks)))
        channels = {}
        if transform_tracks:
            active = [s for s in transform_tracks[0].get_sections() if s.is_active()]
            require(len(active) == 1, "CAMERA_TRANSFORM_SECTIONS|%s|%d" % (label, len(active)))
            channels = {channel_name(c): c for c in active[0].get_all_channels()}
        frames = sorted(set([0] + [f for key in ("Location.X", "Location.Y", "Rotation.Z")
                                   if key in channels for f in channel_key_frames(channels[key])]))
        for frame in frames:
            rows.append({"label": label, "frame": frame,
                         "xy": [value_at(sequence, channels.get("Location.X"), frame, base["Location.X"]),
                                value_at(sequence, channels.get("Location.Y"), frame, base["Location.Y"])],
                         "yaw_deg": value_at(sequence, channels.get("Rotation.Z"), frame, base["Rotation.Z"]),
                         "source": "spawnable_sequence_transform" if transform_tracks else "spawnable_template_transform",
                         "key_counts": {k: len(channel_key_frames(v)) for k, v in channels.items() if k in base}})
    expected = ["S3 Shot B%02d" % number for number in range(2, 13)]
    require(sorted(labels) == expected, "B_SHOT_CAMERA_CENSUS|%r" % sorted(labels))
    return rows


def blueprint_template(bp_path, names, class_name=None):
    bp = unreal.load_asset(bp_path)
    require(bp is not None, "BP_MISSING|" + bp_path)
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    objects = []
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        data = unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle)
        obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(data)
        if obj is not None and str(obj.get_name()) in names:
            if class_name is None or str(obj.get_class().get_name()) == class_name:
                objects.append(obj)
    unique = {full_path(obj): obj for obj in objects}
    require(len(unique) == 1, "TEMPLATE_COUNT|%s|%s|%d" % (bp_path, names, len(unique)))
    return bp, next(iter(unique.values()))


def cloth_template(figure):
    return blueprint_template(core.BP_PATHS[figure], ("ShoreHeadCloth", "ShoreHeadCloth_GEN_VARIABLE"),
                              "ChaosClothComponent")


def outfit_template(figure):
    bp = unreal.load_asset(core.BP_PATHS[figure])
    require(bp is not None, "BP_MISSING|" + core.BP_PATHS[figure])
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    hits = []
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(
            unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
        if obj is None or not isinstance(obj, unreal.SkeletalMeshComponent):
            continue
        mesh = obj.get_skeletal_mesh_asset()
        if mesh is not None and "_outfits" in path_of(mesh).lower():
            hits.append(obj)
    require(len(hits) == 1, "OUTFIT_TEMPLATE_COUNT|%s|%d" % (figure, len(hits)))
    return bp, hits[0]


def cloth_state(figure):
    bp, cloth = cloth_template(figure)
    material = cloth.get_material(0)
    mel = unreal.MaterialEditingLibrary
    vectors = [str(x) for x in mel.get_vector_parameter_names(material)] if material else []
    tint = None
    if material and "WeaveTint" in vectors:
        c = mel.get_material_instance_vector_parameter_value(material, "WeaveTint")
        tint = [float(c.r), float(c.g), float(c.b), float(c.a)]
    asset = cloth.get_asset() if hasattr(cloth, "get_asset") else prop(cloth, "cloth_asset")
    return bp, cloth, {"figure": figure, "blueprint": core.BP_PATHS[figure], "component": full_path(cloth),
                       "asset": path_of(asset), "material": path_of(material), "weave_tint": tint,
                       "underwear_colour_linear": core.cloth_colour(tint) if tint else None,
                       "reset": bool(prop(cloth, "reset", False)),
                       "teleport": bool(prop(cloth, "teleport", False)),
                       "teleport_distance_threshold": float(cloth.get_teleport_distance_threshold()),
                       "teleport_rotation_threshold": float(cloth.get_teleport_rotation_threshold()),
                       "pin_audit": "declaration-only asset path; MaxDistance collection is not exposed by component Python",
                       "pin_ready_v3_name": bool(asset and "_v3" in path_of(asset).lower())}


def classify_material(path):
    low = (path or "").lower()
    if "defaultgarment" in low and "_short" in low:
        return "short"
    if "defaultgarment" in low and "_shirt" in low:
        return "shirt"
    return "unknown"


def outfit_template_state(figure, cfg, cloth_row):
    _, component = outfit_template(figure)
    materials = [component.get_material(i) for i in range(component.get_num_materials())]
    paths = [path_of(x) for x in materials]
    roles = [classify_material(x) for x in paths]
    require("short" in roles and "shirt" in roles and "unknown" not in roles,
            "OUTFIT_SLOTS|%s|%r" % (figure, list(zip(paths, roles))))
    short_parents = sorted(set(paths[i] for i, role in enumerate(roles) if role == "short"))
    require(len(short_parents) == 1, "SHORT_PARENT_COUNT|%s|%r" % (figure, short_parents))
    parent = unreal.load_asset(short_parents[0])
    vectors = sorted(str(x) for x in unreal.MaterialEditingLibrary.get_vector_parameter_names(parent))
    parameter, error = None, None
    try:
        parameter = core.choose_colour_parameter(vectors, cfg["outfit"]["colour_parameter_candidates"])
    except Exception as exc:
        error = str(exc)
    child = OUTFIT_DIR + "/MI_%s_Shorts_Hessian_v%d" % (figure, cfg["outfit"]["asset_version"])
    return {"figure": figure, "component": full_path(component), "resolved": paths, "roles": roles,
            "short_parent": short_parents[0], "vector_parameters": vectors,
            "colour_parameter": parameter, "parameter_problem": error, "child": child,
            "target_colour_linear": cloth_row["underwear_colour_linear"]}


def current_facts(cfg, require_clean=False):
    world, actors = clean_context(require_clean)
    scene = unreal.load_asset(core.SCENE)
    clams = unreal.load_asset(core.CLAMS)
    require(scene is not None and clams is not None, "SEQUENCE_LOAD")
    inventory = actor_inventory(actors)
    cameras = camera_samples(scene)
    occupied = [(row["location"][0], row["location"][1]) for row in inventory]
    placement = core.build_placement_plan(cfg, occupied, cameras)
    cloth = []
    outfit = []
    for figure in core.FIGURES:
        _, _, row = cloth_state(figure)
        cloth.append(row)
        outfit.append(outfit_template_state(figure, cfg, row))
    shore05 = [row for row in inventory if row["label"] == "Shore05_M53 Clam"]
    problems = []
    if shore05:
        problems.append("SHORE05_ALREADY_PLACED|count=%d" % len(shore05))
    if any(row["weave_tint"] is None for row in cloth):
        problems.append("WEAVE_TINT_UNREADABLE")
    if cfg["outfit"]["enabled"]:
        problems += ["OUTFIT_PARAMETER|%s|%s" % (row["figure"], row["parameter_problem"])
                     for row in outfit if row["parameter_problem"]]
    problems += ["CLOTH_PIN_UNVERIFIED|%s|%s" % (row["figure"], row["asset"])
                 for row in cloth if not row["pin_ready_v3_name"]]
    return {"world": world, "actors": actors, "scene": scene, "clams": clams,
            "inventory": inventory, "placement": placement, "cloth": cloth, "outfit": outfit,
            "problems": problems, "census": census()}


def dry(run, cfg):
    before = census()
    facts = current_facts(cfg, require_clean=False)
    after = census()
    require(before == after, "DRY_DIRTIED|before=%s after=%s" % (before, after))
    hard = [x for x in facts["problems"] if not x.startswith("CLOTH_PIN_UNVERIFIED")]
    report = {"schema": core.SCHEMA, "run_id": run, "mode": "DRY", "config": cfg,
              "apply_ready": not hard and before == {"content": [], "maps": []},
              "problems": facts["problems"], "placement": facts["placement"],
              "cloth_templates": facts["cloth"], "outfit": facts["outfit"],
              "actor_inventory": facts["inventory"], "stills_plan": core.stills_plan(),
              "weave_texture": {"path": "ShroudHessian_20261008/T_Shroud_Weave_BC.png",
                                "pixels": 4194304, "srgb_mean": core.WEAVE_MEAN_SRGB,
                                "linear_mean": core.WEAVE_MEAN_LINEAR,
                                "method": "measured offline mean after 25% luma-preserving desaturation"},
              "cloth_boundary": {"tier": "declaration-proven API, behavior inferred",
                                  "warmup_property": None,
                                  "first_crowd_visible_frame": core.FIRST_CROWD_VISIBLE,
                                  "note": "No UChaosClothComponent warm-up/pre-roll property exists in the installed 5.8 header. Whole-scene playback gives 15 s before the first B-shot; direct jumps need MRQ/transport pre-roll and rendered proof."},
              "dirty_before": before, "dirty_after": after}
    write_json(DRY_OUT, report)
    unreal.log("P40SHORE_DRY_OK|run=%s|apply_ready=%d|placements=%d|extras=%d|problems=%d|writes=0|dirty_unchanged=1|report=%s" %
               (run, int(report["apply_ready"]), len(facts["placement"]["placements"]), cfg["extra_count"],
                len(facts["problems"]), DRY_OUT))
    return report


def find_animation(name):
    paths = unreal.EditorAssetLibrary.list_assets("/Game/Metahuman/ShoreCast_20260910", recursive=True,
                                                  include_folder=False)
    hits = [str(path).split(".", 1)[0] for path in paths
            if str(path).split(".")[-1] == name or str(path).split("/")[-1].split(".")[0] == name]
    hits = sorted(set(hits))
    require(len(hits) == 1, "ANIMATION_ASSET|%s|hits=%r" % (name, hits))
    asset = unreal.load_asset(hits[0])
    require(asset is not None, "ANIMATION_LOAD|" + hits[0])
    return asset


def set_play_rate(params, rate):
    value = params.get_editor_property("play_rate")
    if hasattr(value, "set_fixed_play_rate"):
        value.set_fixed_play_rate(float(rate)); params.set_editor_property("play_rate", value)
    else:
        params.set_editor_property("play_rate", float(rate))


def weight_channel(section):
    hits = [c for c in section.get_all_channels() if str(c.get_name()).startswith("Weight")]
    require(len(hits) == 1, "WEIGHT_CHANNEL|%d" % len(hits))
    return hits[0]


def add_animation(track, sequence, animation, row):
    section = track.add_section()
    params = section.get_editor_property("params")
    params.set_editor_property("animation", animation)
    tick = sequence.get_tick_resolution(); tick_rate = float(tick.numerator) / float(tick.denominator)
    params.set_editor_property("start_frame_offset", unreal.FrameNumber(int(round(row["source_in"] * tick_rate))))
    params.set_editor_property("end_frame_offset", unreal.FrameNumber(int(round(max(0.0, animation.get_play_length() - row["source_out"]) * tick_rate))))
    params.set_editor_property("first_loop_start_frame_offset", unreal.FrameNumber(0))
    try:
        params.set_editor_property("reverse", False)
    except Exception:
        params.set_editor_property("b_reverse", False)
    set_play_rate(params, row["play_rate"])
    section.set_editor_property("params", params); section.set_range(*row["range"])
    channel = weight_channel(section)
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    if row["ease_in"]:
        channel.add_key(unreal.FrameNumber(row["range"][0]), 0.0, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
        channel.add_key(unreal.FrameNumber(row["range"][0] + row["ease_in"]), 1.0, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    if row["ease_out"]:
        channel.add_key(unreal.FrameNumber(row["range"][1] - row["ease_out"]), 1.0, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
        channel.add_key(unreal.FrameNumber(row["range"][1]), 0.0, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    if not row["ease_in"] and not row["ease_out"]:
        channel.set_default(1.0)
    return str(section.get_name())


def add_transform(binding, actor):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section(); section.set_range(*core.PLAYBACK)
    loc, rot, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
    wanted = {"Location.X": loc.x, "Location.Y": loc.y, "Location.Z": loc.z,
              "Rotation.X": rot.roll, "Rotation.Y": rot.pitch, "Rotation.Z": rot.yaw,
              "Scale.X": scale.x, "Scale.Y": scale.y, "Scale.Z": scale.z}
    channels = {channel_name(c): c for c in section.get_all_channels()}
    require(set(wanted) <= set(channels), "TRANSFORM_CHANNELS")
    for name, value in wanted.items():
        channels[name].set_default(float(value))
    return str(track.get_name())


def add_visibility(binding):
    track = binding.add_track(unreal.MovieSceneVisibilityTrack)
    track.set_property_name_and_path("bHidden", "bHidden")
    section = track.add_section(); section.set_range(*core.PLAYBACK)
    channels = list(section.get_all_channels())
    require(len(channels) == 1, "VISIBILITY_CHANNELS")
    # UE visibility bool channels store VISIBLE, despite binding AActor::bHidden.
    channels[0].add_key(unreal.FrameNumber(0), False, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    channels[0].add_key(unreal.FrameNumber(core.FIRST_CROWD_VISIBLE), True,
                        time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return str(track.get_name())


def spawn_placements(world, clams, plan, run):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    created = []
    for row in plan["placements"]:
        cls = unreal.EditorAssetLibrary.load_blueprint_class(row["blueprint"])
        require(cls is not None, "BLUEPRINT_CLASS|" + row["blueprint"])
        xyz = row["world_xyz_cm"]
        actor = subsystem.spawn_actor_from_class(cls, unreal.Vector(*xyz),
                                                 unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(row["yaw_deg"])))
        require(actor is not None, "SPAWN|" + row["label"])
        actor.set_actor_label(row["label"])
        actor.set_editor_property("tags", list(prop(actor, "tags", [])) +
                                  [unreal.Name(TAG), unreal.Name("P40.Source." + row["source"])])
        actor_binding = clams.add_possessable(actor); actor_binding.set_display_name(row["label"])
        transform_track = add_transform(actor_binding, actor)
        visibility_track = add_visibility(actor_binding)
        bodies = [c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                  if str(c.get_name()) == "Body"]
        require(len(bodies) == 1, "BODY_COMPONENT|%s|%d" % (row["label"], len(bodies)))
        body_binding = clams.add_possessable(bodies[0]); body_binding.set_display_name(row["label"] + "/Body")
        body_binding.set_parent(actor_binding)
        animation_track = body_binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
        animation_track.set_display_name("P40 Forward Loops " + run)
        animation = find_animation(row["animation_name"])
        sections = [add_animation(animation_track, clams, animation, item) for item in row["motion"]]
        cloth = [c for c in actor.get_components_by_class(unreal.ActorComponent)
                 if str(c.get_class().get_name()) == "ChaosClothComponent"]
        require(len(cloth) == 1, "CLOTH_COMPONENT|%s|%d" % (row["label"], len(cloth)))
        created.append({"label": row["label"], "source": row["source"], "actor_path": full_path(actor),
                        "actor_binding": actor_binding.get_id().export_text(),
                        "body_binding": body_binding.get_id().export_text(),
                        "transform_track": transform_track, "visibility_track": visibility_track,
                        "animation_track": str(animation_track.get_name()), "sections": sections,
                        "cloth_material": path_of(cloth[0].get_material(0)), "world_xyz_cm": xyz})
    return created


def cloth_apply(cfg):
    rows = []
    for figure in core.FIGURES:
        bp, cloth, before = cloth_state(figure)
        cloth.modify()
        # Persistent bTeleport/bReset would run every update (and reset requires
        # teleport); leave both disabled.  Only the automatic jump thresholds
        # are a safe template policy.  They do not prove warm-up or rest.
        cloth.set_editor_property("teleport", False)
        cloth.set_editor_property("reset", False)
        cloth.set_teleport_distance_threshold(cfg["cloth_reset"]["teleport_distance_threshold_cm"])
        cloth.set_teleport_rotation_threshold(cfg["cloth_reset"]["teleport_rotation_threshold_deg"])
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        _, _, after = cloth_state(figure)
        require(after["reset"] is False and after["teleport"] is False, "CLOTH_RESET_READBACK|" + figure)
        rows.append({"figure": figure, "before": before, "after": after})
    return rows


def create_outfit_children(cfg, outfit_rows):
    tools = unreal.AssetToolsHelpers.get_asset_tools(); mel = unreal.MaterialEditingLibrary
    created = []
    for row in outfit_rows:
        require(not unreal.EditorAssetLibrary.does_asset_exist(row["child"]), "OUTFIT_CHILD_EXISTS|" + row["child"])
        folder, name = row["child"].rsplit("/", 1)
        mi = tools.create_asset(name, folder, unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
        require(mi is not None, "OUTFIT_CHILD_CREATE|" + row["child"])
        parent = unreal.load_asset(row["short_parent"])
        require(parent is not None, "OUTFIT_PARENT_LOAD|" + row["short_parent"])
        mel.set_material_instance_parent(mi, parent)
        c = row["target_colour_linear"]
        mel.set_material_instance_vector_parameter_value(mi, row["colour_parameter"], unreal.LinearColor(*c))
        mel.update_material_instance(mi)
        got = mel.get_material_instance_vector_parameter_value(mi, row["colour_parameter"])
        values = [float(got.r), float(got.g), float(got.b), float(got.a)]
        require(max(abs(values[i] - c[i]) for i in range(4)) <= 1.0e-4,
                "OUTFIT_COLOUR_READBACK|" + row["figure"])
        created.append({"figure": row["figure"], "path": row["child"], "parent": row["short_parent"],
                        "parameter": row["colour_parameter"], "colour_linear": c, "readback": values})
    return created


def actor_outfit_component(actor):
    hits = []
    for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        mesh = component.get_skeletal_mesh_asset()
        if mesh is not None and "_outfits" in path_of(mesh).lower():
            hits.append(component)
    require(len(hits) == 1, "ACTOR_OUTFIT_COMPONENT|%s|%d" % (actor.get_actor_label(), len(hits)))
    return hits[0]


def raw_overrides(component):
    return [path_of(x) for x in (prop(component, "override_materials", []) or [])]


def apply_outfits(actors, children):
    by_figure = {row["figure"]: row for row in children}
    rows = []
    for actor in actors:
        figure = shore_id_from_class(actor)
        if figure not in by_figure:
            continue
        component = actor_outfit_component(actor)
        before = raw_overrides(component)
        resolved_before = [path_of(component.get_material(i)) for i in range(component.get_num_materials())]
        slots = [i for i, path in enumerate(resolved_before) if classify_material(path) == "short"]
        require(slots, "NO_SHORT_SLOTS|" + str(actor.get_actor_label()))
        child = unreal.load_asset(by_figure[figure]["path"])
        require(child is not None, "OUTFIT_CHILD_LOAD|" + by_figure[figure]["path"])
        component.modify()
        for index in slots:
            component.set_material(index, child)  # SetMaterial refreshes resolved/render state; raw array assignment did not.
        resolved_after = [path_of(component.get_material(i)) for i in range(component.get_num_materials())]
        require(all(resolved_after[i] == by_figure[figure]["path"] for i in slots),
                "OUTFIT_RESOLVED_READBACK|" + str(actor.get_actor_label()))
        rows.append({"label": str(actor.get_actor_label()), "actor_path": full_path(actor), "figure": figure,
                     "component": full_path(component), "before_overrides": before,
                     "resolved_before": resolved_before, "slots": slots,
                     "child": by_figure[figure]["path"], "resolved_after": resolved_after,
                     "after_overrides": raw_overrides(component)})
    require(rows, "NO_OUTFIT_ACTORS")
    return rows


def save_exact(content_packages, world):
    expected = {"content": sorted(content_packages), "maps": [core.WORLD]}
    got = census()
    require(got == expected, "DIRTY_CENSUS|got=%s expected=%s|NOTHING SAVED; Don't-Save restart" %
            (json.dumps(got), json.dumps(expected)))
    for package in sorted(content_packages):
        require(unreal.EditorAssetLibrary.save_asset(package, only_if_is_dirty=False), "SAVE_ASSET|" + package)
    require(unreal.EditorLoadingAndSavingUtils.save_map(world, core.WORLD), "SAVE_MAP")
    require(census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % json.dumps(census()))


def apply(run, cfg):
    facts = current_facts(cfg, require_clean=True)
    hard = [x for x in facts["problems"] if not x.startswith("CLOTH_PIN_UNVERIFIED")]
    require(not hard, "DRY_PROBLEMS|" + " || ".join(hard))
    bp_packages = sorted(core.BP_PATHS.values()) if cfg["cloth_reset"]["enabled"] else []
    backup_row = backup(run, bp_packages)
    record = {"schema": core.SCHEMA, "run_id": run, "state": "applying", "config": cfg,
              "backup": backup_row, "placement_plan": facts["placement"], "cloth": [],
              "outfit_children": [], "outfit_assignments": [], "created": [], "saved": False}
    write_json(RECORD, record, exclusive=True)
    world, clams = facts["world"], facts["clams"]
    record["created"] = spawn_placements(world, clams, facts["placement"], run)
    if cfg["cloth_reset"]["enabled"]:
        record["cloth"] = cloth_apply(cfg)
    if cfg["outfit"]["enabled"]:
        record["outfit_children"] = create_outfit_children(cfg, facts["outfit"])
        # Include newly spawned actors in the assignment pass.
        live_actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
        record["outfit_assignments"] = apply_outfits(live_actors, record["outfit_children"])
    write_json(RECORD, record)
    content = [core.CLAMS] + bp_packages + [row["path"] for row in record["outfit_children"]]
    save_exact(content, world)
    record["saved"] = True; record["state"] = "applied"; record["saved_packages"] = sorted(content + [core.WORLD])
    write_json(RECORD, record)
    verify_row = verify(run, cfg, record_override=record, emit=False)
    require(verify_row["ok"], "POST_SAVE_READBACK|" + " || ".join(verify_row["problems"]))
    unreal.log("P40SHORE_APPLY_OK|run=%s|placed=%d|extras=%d|outfit_actors=%d|cloth_templates=%d|packages=%s|backup=%s|dirty=0" %
               (run, len(record["created"]), cfg["extra_count"], len(record["outfit_assignments"]),
                len(record["cloth"]), sorted(content + [core.WORLD]), backup_row["root"]))
    return record


def binding_by_guid(sequence, guid):
    hits = [b for b in sequence.get_bindings() if b.get_id().export_text() == guid]
    return hits[0] if len(hits) == 1 else None


def verify(run, cfg, record_override=None, emit=True):
    record = record_override or load_json(RECORD)
    world, actors = clean_context(require_clean=False)
    clams = unreal.load_asset(core.CLAMS)
    by_label = actor_index(actors)
    problems = []
    for row in record["created"]:
        hits = by_label.get(row["label"], [])
        if len(hits) != 1:
            problems.append("ACTOR_COUNT|%s|%d" % (row["label"], len(hits)))
            continue
        if TAG not in {str(x) for x in prop(hits[0], "tags", [])}:
            problems.append("ACTOR_TAG|" + row["label"])
        for guid in (row["actor_binding"], row["body_binding"]):
            if binding_by_guid(clams, guid) is None:
                problems.append("BINDING|" + guid)
    for row in record.get("cloth", []):
        _, _, now = cloth_state(row["figure"])
        expected = row["after"]
        for key in ("reset", "teleport", "teleport_distance_threshold", "teleport_rotation_threshold"):
            if abs(float(now[key]) - float(expected[key])) > 1.0e-4:
                problems.append("CLOTH_DRIFT|%s|%s" % (row["figure"], key))
    for row in record.get("outfit_assignments", []):
        hits = [a for a in actors if full_path(a) == row["actor_path"]]
        if len(hits) != 1:
            problems.append("OUTFIT_ACTOR|" + row["label"]); continue
        comp = actor_outfit_component(hits[0])
        if any(path_of(comp.get_material(i)) != row["child"] for i in row["slots"]):
            problems.append("OUTFIT_DRIFT|" + row["label"])
    result = {"schema": core.SCHEMA, "run_id": run, "mode": "VERIFY", "ok": not problems,
              "problems": problems, "placed": len(record["created"]),
              "outfit_actors": len(record.get("outfit_assignments", [])),
              "cloth_templates": len(record.get("cloth", [])), "dirty_census": census()}
    write_json(VERIFY_OUT, result)
    if emit:
        unreal.log("P40SHORE_VERIFY_%s|run=%s|placed=%d|problems=%d|report=%s" %
                   ("OK" if result["ok"] else "FAILED", run, result["placed"], len(problems), VERIFY_OUT))
    return result


def restore_overrides(component, paths):
    materials = [unreal.load_asset(path) if path else None for path in paths]
    component.modify(); component.set_editor_property("override_materials", materials)
    require(raw_overrides(component) == paths, "REVERT_OVERRIDE_READBACK|" + full_path(component))


def revert(run, cfg):
    require(census() == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % json.dumps(census()))
    record = load_json(RECORD)
    require(record.get("state") == "applied" and record.get("saved") is True, "RECORD_NOT_APPLIED")
    check = verify(run, cfg, record_override=record, emit=False)
    require(check["ok"], "STATE_DRIFT|" + " || ".join(check["problems"]))
    world, actors = clean_context(require_clean=True)
    bp_packages = sorted(core.BP_PATHS.values()) if record.get("cloth") else []
    revert_backup = backup("REVERT-" + run, bp_packages)
    by_path = {full_path(actor): actor for actor in actors}
    for row in record.get("outfit_assignments", []):
        actor = by_path.get(row["actor_path"])
        if actor is not None and row["label"] not in {x["label"] for x in record["created"]}:
            restore_overrides(actor_outfit_component(actor), row["before_overrides"])
    for row in record.get("cloth", []):
        bp, cloth = cloth_template(row["figure"])
        before = row["before"]
        cloth.modify(); cloth.set_editor_property("reset", before["reset"]); cloth.set_editor_property("teleport", before["teleport"])
        cloth.set_teleport_distance_threshold(before["teleport_distance_threshold"])
        cloth.set_teleport_rotation_threshold(before["teleport_rotation_threshold"])
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    clams = unreal.load_asset(core.CLAMS)
    for row in reversed(record["created"]):
        for guid in (row["body_binding"], row["actor_binding"]):
            binding = binding_by_guid(clams, guid)
            require(binding is not None, "REVERT_BINDING|" + guid)
            binding.remove()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    current = actor_index(list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)))
    for row in record["created"]:
        hits = current.get(row["label"], [])
        require(len(hits) == 1 and TAG in {str(x) for x in prop(hits[0], "tags", [])},
                "REVERT_ACTOR_OWNERSHIP|" + row["label"])
        result = subsystem.destroy_actor(hits[0])
        require(result is not False, "REVERT_DESTROY|" + row["label"])
    content = [core.CLAMS] + bp_packages
    save_exact(content, world)
    record["state"] = "reverted"; record["revert"] = {"run_id": run, "backup": revert_backup,
                                                         "retained_outfit_children": [x["path"] for x in record.get("outfit_children", [])]}
    write_json(RECORD, record)
    archived = RECORD + ".reverted-" + run
    os.replace(RECORD, archived)
    unreal.log("P40SHORE_REVERT_OK|run=%s|actors_removed=%d|outfit_children_retained=%d|packages=%s|backup=%s|record=%s|dirty=0" %
               (run, len(record["created"]), len(record.get("outfit_children", [])),
                sorted(content + [core.WORLD]), revert_backup["root"], archived))
    return record


def main():
    run = datetime.datetime.now().strftime("P40SHORE-%Y%m%d-%H%M%S")
    mode = "DRY"
    try:
        raw = load_json(ARGS)
        cfg = core.validate_args(raw, os.path.isfile(RECORD))
        mode = cfg["mode"]
        unreal.log("P40SHORE_START|run=%s|mode=%s" % (run, mode))
        if mode == "DRY":
            return dry(run, cfg)
        if mode == "APPLY":
            return apply(run, cfg)
        if mode == "VERIFY":
            return verify(run, cfg)
        return revert(run, cfg)
    except Exception as exc:
        dirty = {}
        try:
            dirty = census()
        except Exception:
            pass
        unreal.log_error("P40SHORE_FAILED|run=%s|mode=%s|%s|census=%s|NOTHING SAVED unless an *_OK marker printed; Don't-Save restart if dirty|trace=%s" %
                         (run, mode, str(exc).replace("\n", " "), json.dumps(dirty),
                          traceback.format_exc().replace("\n", "\\n")))
        raise


if unreal is not None and __name__ == "<run_path>":
    main()
