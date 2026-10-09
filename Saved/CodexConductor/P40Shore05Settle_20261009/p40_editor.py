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
import re
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
TRANSFORM_CHANNELS = ("Location.X", "Location.Y", "Location.Z",
                      "Rotation.X", "Rotation.Y", "Rotation.Z",
                      "Scale.X", "Scale.Y", "Scale.Z")
OUTFIT_DIR = "/Game/Metahuman/ShoreCast_20260910/OutfitHessian"
MAP_FILE = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
CLAMS_FILE = "Content/Scenes/LS_Clams.uasset"

# Live DRY B1K found that Shore02's outfit component resolves two short-role
# slots: the shared body-shape material and a character-specific MI.  Preserve
# the character-specific material as the child MI parent, but only when the
# complete candidate set is exactly the measured pair.  Every unlisted or
# drifted ambiguity remains a refusal.
SHORT_PARENT_SELECTION_RULES = {
    "Shore02_F52": {
        "candidates": (
            "/Game/Metahuman/ShoreCast_20260910/Assembled/Common/Optional/Clothing/DefaultGarment/ClothAssets/bodyShapeB/Meshes/bodytype2_short",
            "/Game/Metahuman/ShoreCast_20260910/Assembled/Shore02_F52/MHC_Shore02_F52/Clothing/MI_WI_DefaultGarment_M_DG_bodyShapeB_Short",
        ),
        "selected": "/Game/Metahuman/ShoreCast_20260910/Assembled/Shore02_F52/MHC_Shore02_F52/Clothing/MI_WI_DefaultGarment_M_DG_bodyShapeB_Short",
        "reason": "prefer the character-specific resolved garment MI over its shared body-shape source",
    },
    "Shore04_F55": {
        "candidates": (
            "/Game/Metahuman/ShoreCast_20260910/Assembled/Common/Optional/Clothing/DefaultGarment/ClothAssets/bodyShapeB/Meshes/bodytype2_short",
            "/Game/Metahuman/ShoreCast_20260910/Assembled/Shore04_F55/MHC_Shore04_F55/Clothing/MI_WI_DefaultGarment_M_DG_bodyShapeB_Short",
        ),
        "selected": "/Game/Metahuman/ShoreCast_20260910/Assembled/Shore04_F55/MHC_Shore04_F55/Clothing/MI_WI_DefaultGarment_M_DG_bodyShapeB_Short",
        "reason": "prefer the character-specific resolved garment MI over its shared body-shape source",
    },
    "Shore06_F25": {
        "candidates": (
            "/Game/Metahuman/ShoreCast_20260910/Assembled/Common/Optional/Clothing/DefaultGarment/ClothAssets/bodyShapeB/Meshes/bodytype2_short",
            "/Game/Metahuman/ShoreCast_20260910/Assembled/Shore06_F25/MHC_Shore06_F25/Clothing/MI_WI_DefaultGarment_M_DG_bodyShapeB_Short",
        ),
        "selected": "/Game/Metahuman/ShoreCast_20260910/Assembled/Shore06_F25/MHC_Shore06_F25/Clothing/MI_WI_DefaultGarment_M_DG_bodyShapeB_Short",
        "reason": "prefer the character-specific resolved garment MI over its shared body-shape source",
    },
}

# Shore05 is the sole retained v2 live-sack template. Unlike the five v3
# shroud materials, its exact measured material exposes no WeaveTint parameter.
# Treat it as an untinted weave only for this exact figure/asset/material tuple;
# any asset drift leaves the tint unreadable and DRY remains unready.
NEUTRAL_WEAVE_TINT_RULES = {
    "Shore05_M53": {
        "asset": "/Game/Metahuman/ShoreCast_20260910/Cloth/LiveSack/CA_ShoreSack_Shore05_M53_v2",
        "material": "/Game/Metahuman/ShoreCast_20260910/Sack/Materials/MI_Sackcloth_OldGrey_Cloth_v2",
        "tint": [1.0, 1.0, 1.0, 1.0],
        "reason": "exact v2 sack material has no WeaveTint; use the neutral weave mean",
    },
}


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


def unique_template_candidate(objects, token):
    """Collapse repeated subsystem handles, but never distinct object paths."""
    raw_paths = [full_path(obj) for obj in objects]
    unique = {path: obj for path, obj in zip(raw_paths, objects)}
    require(None not in unique, "%s_PATH_NONE" % token)
    require(len(unique) == 1, "%s|raw=%d|unique=%d|paths=%s" % (
        token, len(objects), len(unique), sorted(unique)))
    path, obj = next(iter(unique.items()))
    return obj, {"raw_hit_count": len(objects), "unique_candidate_count": len(unique),
                 "candidate_paths": sorted(unique),
                 "duplicate_handles_collapsed": len(objects) - len(unique),
                 "selected_path": path}


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
    """Return the stable Sequencer channel name, never its proxy suffix.

    UE 5.8 scripting proxies are renumbered between reads (for example
    Location.X_183).  The suffix is not part of the channel identity.
    """
    raw = str(channel.get_name()).split(" (", 1)[0]
    return re.sub(r"_\d+$", "", raw)


def transform_channels(section, token):
    """Read back one transform section and enforce its exact 9-channel schema."""
    raw = list(section.get_all_channels())
    names = [channel_name(channel) for channel in raw]
    require(len(raw) == len(TRANSFORM_CHANNELS),
            "%s_COUNT|got=%d|names=%r" % (token, len(raw), names))
    require(tuple(names) == TRANSFORM_CHANNELS,
            "%s_ORDER|got=%r" % (token, names))
    require(len(set(names)) == len(names), "%s_DUPLICATE|got=%r" % (token, names))
    return dict(zip(names, raw))


def guid_text(value):
    """Serialize an FGuid by value; str(FGuid) is a changing wrapper address."""
    if unreal is not None and hasattr(unreal, "GuidLibrary"):
        converter = getattr(unreal.GuidLibrary, "conv_guid_to_string", None)
        if converter is not None:
            return converter(value)
    if hasattr(value, "export_text"):
        return value.export_text()
    raise Stop("GUID_SERIALIZATION")


def track_class(track):
    return str(track.get_class().get_name())


def add_possessable_readback(sequence, obj, token):
    """Add a binding, ignore the unreliable return, and resolve it by GUID diff."""
    before = {guid_text(binding.get_id()) for binding in sequence.get_bindings()}
    sequence.add_possessable(obj)
    created = [binding for binding in sequence.get_bindings()
               if guid_text(binding.get_id()) not in before]
    require(len(created) == 1, "%s_READBACK|new=%d" % (token, len(created)))
    return created[0]


def add_track_readback(binding, cls, class_name, token):
    before = [track for track in binding.get_tracks() if track_class(track) == class_name]
    require(not before, "%s_PREEXISTING|count=%d" % (token, len(before)))
    binding.add_track(cls)
    after = [track for track in binding.get_tracks() if track_class(track) == class_name]
    require(len(after) == 1, "%s_READBACK|count=%d" % (token, len(after)))
    return after[0]


def add_section_readback(track, token):
    before = {str(section.get_name()) for section in track.get_sections()}
    track.add_section()
    sections = list(track.get_sections())
    created = [section for section in sections if str(section.get_name()) not in before]
    require(len(created) == 1 and len(sections) == len(before) + 1,
            "%s_READBACK|before=%d|after=%d|new=%d" %
            (token, len(before), len(sections), len(created)))
    return created[0]


def channel_key_frames(channel):
    return [int(key.get_time().frame_number.value) for key in channel.get_keys()]


def value_at(sequence, channel, frame, fallback):
    if channel is None:
        return fallback
    values = list(channel.evaluate_keys(sequence.make_range(int(frame), 1), sequence.get_display_rate()))
    require(len(values) == 1, "CAMERA_CHANNEL_EVALUATION|frame=%d|count=%d" % (frame, len(values)))
    return float(values[0])


def section_range(section):
    return [int(section.get_start_frame()) if section.has_start_frame() else None,
            int(section.get_end_frame()) if section.has_end_frame() else None]


def section_covers(section, frame):
    start, end = section_range(section)
    return (start is None or start <= frame) and (end is None or frame < end)


def blend_name(section):
    raw = str(section.get_blend_type()).upper()
    if "ADDITIVE_FROM_BASE" in raw:
        raise Stop("CAMERA_BLEND_UNSUPPORTED|ADDITIVE_FROM_BASE")
    if "ADDITIVE" in raw:
        return "ADDITIVE"
    if "RELATIVE" in raw:
        return "RELATIVE"
    if "ABSOLUTE" in raw or raw in ("NONE", ""):
        return "ABSOLUTE"
    raise Stop("CAMERA_BLEND_UNSUPPORTED|%s" % raw)


def compose_camera_layers(layers, label, initial=None):
    """Compose unit-weight X/Y/Yaw layers against the spawnable's initial transform.

    MovieScene treats an exclusively additive channel as initial + additive and
    a relative channel as initial + channel value.  We deliberately continue to
    refuse multiple absolute/relative owners: reproducing their weighted/eased
    average by reading raw channels would not be an exact Sequencer evaluation.
    """
    initial = list(initial or [0.0, 0.0, 0.0])
    absolute = [row for row in layers if row[0] == "ABSOLUTE"]
    additive = [row for row in layers if row[0] == "ADDITIVE"]
    relative = [row for row in layers if row[0] == "RELATIVE"]
    owners = absolute + relative
    require(len(owners) <= 1, "CAMERA_BASE_SECTION_COUNT|%s|%d" % (label, len(owners)))
    require(len(owners) + len(additive) == len(layers), "CAMERA_BLEND_SET|%s" % label)
    if absolute:
        base = absolute[0][1]
    elif relative:
        base = [initial[i] + relative[0][1][i] for i in range(3)]
    else:
        base = initial
    return [base[i] + sum(row[1][i] for row in additive) for i in range(3)]


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
        attach_tracks = [t for t in binding.get_tracks()
                         if str(t.get_class().get_name()) == "MovieScene3DAttachTrack"]
        require(not attach_tracks, "CAMERA_ATTACHMENT_UNEVALUATED|%s|tracks=%d|raw channels are relative to a "
                "constraint parent; skip only with a separately measured world-space margin" %
                (label, len(attach_tracks)))
        if len(transform_tracks) > 1:
            raise Stop("CAMERA_TRANSFORM_TRACKS|%s|%d" % (label, len(transform_tracks)))
        section_rows = []
        if transform_tracks:
            active = [s for s in transform_tracks[0].get_sections() if s.is_active()]
            require(active, "CAMERA_TRANSFORM_ACTIVE_SECTIONS|%s|0" % label)
            for section in active:
                channels = transform_channels(section, "CAMERA_TRANSFORM_CHANNELS|%s" % label)
                section_rows.append((section, channels))
        frames = sorted(set([0] + [f for _section, channels in section_rows
                                   for key in ("Location.X", "Location.Y", "Rotation.Z")
                                   if key in channels for f in channel_key_frames(channels[key])]))
        for frame in frames:
            if section_rows:
                layers = []
                for section, channels in section_rows:
                    if not section_covers(section, frame):
                        continue
                    fallback = [base["Location.X"], base["Location.Y"], base["Rotation.Z"]] \
                        if blend_name(section) == "ABSOLUTE" else [0.0, 0.0, 0.0]
                    values = [value_at(sequence, channels.get(key), frame, fallback[i])
                              for i, key in enumerate(("Location.X", "Location.Y", "Rotation.Z"))]
                    layers.append((blend_name(section), values))
                pose = compose_camera_layers(layers, "%s|frame=%d" % (label, frame),
                                             [base["Location.X"], base["Location.Y"], base["Rotation.Z"]])
                pose_source = "spawnable_sequence_transform" if layers else "spawnable_template_initial"
            else:
                pose = [base["Location.X"], base["Location.Y"], base["Rotation.Z"]]
                pose_source = "spawnable_template_transform"
            rows.append({"label": label, "frame": frame,
                         "xy": pose[:2], "yaw_deg": pose[2],
                         "source": pose_source,
                         "active_transform_sections": len(layers) if section_rows else 0,
                         "key_counts": [{k: len(channel_key_frames(v)) for k, v in channels.items() if k in base}
                                        for _section, channels in section_rows]})
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
    obj, _audit = unique_template_candidate(objects, "TEMPLATE_COUNT|%s|%s" % (bp_path, names))
    return bp, obj


def cloth_template(figure):
    return blueprint_template(core.BP_PATHS[figure], ("ShoreHeadCloth", "ShoreHeadCloth_GEN_VARIABLE"),
                              "ChaosClothComponent")


def neutral_weave_tint_fallback(figure, asset_path, material_path, vector_parameters):
    rule = NEUTRAL_WEAVE_TINT_RULES.get(figure)
    if (rule is None or "WeaveTint" in vector_parameters or
            asset_path != rule["asset"] or material_path != rule["material"]):
        return None, None
    return list(rule["tint"]), {"rule": "explicit_exact_asset_material",
                                "asset": asset_path, "material": material_path,
                                "reason": rule["reason"]}


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
    component, audit = unique_template_candidate(hits, "OUTFIT_TEMPLATE_COUNT|%s" % figure)
    return bp, component, audit


def cloth_state(figure):
    bp, cloth = cloth_template(figure)
    material = cloth.get_material(0)
    mel = unreal.MaterialEditingLibrary
    vectors = [str(x) for x in mel.get_vector_parameter_names(material)] if material else []
    asset = cloth.get_asset() if hasattr(cloth, "get_asset") else prop(cloth, "cloth_asset")
    asset_path = path_of(asset)
    material_path = path_of(material)
    tint = None
    tint_source = None
    if material and "WeaveTint" in vectors:
        c = mel.get_material_instance_vector_parameter_value(material, "WeaveTint")
        tint = [float(c.r), float(c.g), float(c.b), float(c.a)]
        tint_source = {"rule": "material_parameter", "parameter": "WeaveTint"}
    elif material:
        tint, tint_source = neutral_weave_tint_fallback(
            figure, asset_path, material_path, vectors)
    return bp, cloth, {"figure": figure, "blueprint": core.BP_PATHS[figure], "component": full_path(cloth),
                       "asset": asset_path, "material": material_path, "weave_tint": tint,
                       "weave_tint_source": tint_source,
                       "underwear_colour_linear": core.cloth_colour(tint) if tint else None,
                       "reset": bool(prop(cloth, "reset", False)),
                       "teleport": bool(prop(cloth, "teleport", False)),
                       "teleport_distance_threshold": float(cloth.get_editor_property("teleport_distance_threshold")),
                       "teleport_rotation_threshold": float(cloth.get_editor_property("teleport_rotation_threshold")),
                       "pin_audit": "declaration-only asset path; MaxDistance collection is not exposed by component Python",
                       "pin_ready_v3_name": bool(asset and "_v3" in path_of(asset).lower())}


def classify_material(path):
    low = (path or "").lower()
    if "defaultgarment" in low and "_short" in low:
        return "short"
    if "defaultgarment" in low and "_shirt" in low:
        return "shirt"
    return "unknown"


def select_short_parent(figure, short_parents):
    candidates = tuple(sorted(set(short_parents)))
    if len(candidates) == 1:
        return candidates[0], {"rule": "unique", "candidates": list(candidates)}
    rule = SHORT_PARENT_SELECTION_RULES.get(figure)
    require(rule is not None and candidates == tuple(sorted(rule["candidates"])),
            "SHORT_PARENT_COUNT|%s|%r" % (figure, list(candidates)))
    require(rule["selected"] in candidates,
            "SHORT_PARENT_RULE_INVALID|%s|%s" % (figure, rule["selected"]))
    return rule["selected"], {"rule": "explicit_exact_candidate_set",
                              "candidates": list(candidates),
                              "selected": rule["selected"],
                              "reason": rule["reason"]}


def outfit_template_state(figure, cfg, cloth_row):
    _, component, discovery = outfit_template(figure)
    materials = [component.get_material(i) for i in range(component.get_num_materials())]
    paths = [path_of(x) for x in materials]
    roles = [classify_material(x) for x in paths]
    require("short" in roles and "shirt" in roles and "unknown" not in roles,
            "OUTFIT_SLOTS|%s|%r" % (figure, list(zip(paths, roles))))
    short_parents = sorted(set(paths[i] for i, role in enumerate(roles) if role == "short"))
    short_parent, short_parent_selection = select_short_parent(figure, short_parents)
    parent = unreal.load_asset(short_parent)
    vectors = sorted(str(x) for x in unreal.MaterialEditingLibrary.get_vector_parameter_names(parent))
    parameter, error = None, None
    try:
        parameter = core.choose_colour_parameter(vectors, cfg["outfit"]["colour_parameter_candidates"])
    except Exception as exc:
        error = str(exc)
    child = OUTFIT_DIR + "/MI_%s_Shorts_Hessian_v%d" % (figure, cfg["outfit"]["asset_version"])
    return {"figure": figure, "component": full_path(component), "template_discovery": discovery,
            "resolved": paths, "roles": roles,
            "short_parent": short_parent, "short_parent_selection": short_parent_selection,
            "vector_parameters": vectors,
            "colour_parameter": parameter, "parameter_problem": error, "child": child,
            "target_colour_linear": cloth_row["underwear_colour_linear"]}


def blueprint_component_rows(figure):
    """Read the generated component templates that a future spawn will inherit."""
    bp = unreal.load_asset(core.BP_PATHS[figure])
    require(bp is not None, "BP_MISSING|" + core.BP_PATHS[figure])
    subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    rows = []
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(bp):
        obj = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(
            unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
        if obj is not None:
            rows.append({"name": str(obj.get_name()), "class": str(obj.get_class().get_name()),
                         "path": full_path(obj)})
    return rows


def actor_outfit_preflight(actor):
    component = actor_outfit_component(actor)
    resolved = [path_of(component.get_material(i)) for i in range(component.get_num_materials())]
    slots = [i for i, path in enumerate(resolved) if classify_material(path) == "short"]
    require(slots, "NO_SHORT_SLOTS|" + str(actor.get_actor_label()))
    return {"label": str(actor.get_actor_label()), "actor_path": full_path(actor),
            "component": full_path(component), "short_slots": slots, "resolved": resolved}


def transform_schema_preflight(sequence):
    """Prove the UE 5.8 transform section channel count/order without editing."""
    inspected = []
    valid = []
    for binding in sequence.get_bindings():
        for track in binding.get_tracks():
            if track_class(track) != "MovieScene3DTransformTrack":
                continue
            for section in track.get_sections():
                raw = list(section.get_all_channels())
                names = [channel_name(channel) for channel in raw]
                row = {"binding": str(binding.get_display_name()), "count": len(raw), "order": names}
                inspected.append(row)
                if len(raw) == len(TRANSFORM_CHANNELS) and tuple(names) == TRANSFORM_CHANNELS:
                    valid.append(row)
    require(valid, "PREFLIGHT_TRANSFORM_SCHEMA|inspected=%r" % inspected)
    return {"expected_count": len(TRANSFORM_CHANNELS), "expected_order": list(TRANSFORM_CHANNELS),
            "representative": valid[0], "sections_inspected": len(inspected)}


def apply_preflight(world, actors, clams, placement, cloth_rows, outfit_rows, cfg):
    """Run every non-mutating APPLY refusal while still in the DRY phase."""
    problems = []
    blueprint_rows = []
    animations = {}
    try:
        transform_schema = transform_schema_preflight(clams)
    except Exception as exc:  # recorded as a DRY refusal, never discovered after mutation
        transform_schema = None
        problems.append("PREFLIGHT_TRANSFORM_SCHEMA|%s" % exc)
    by_figure = {row["figure"]: row for row in outfit_rows}
    for row in placement["placements"]:
        figure = row["source"]
        try:
            cls = unreal.EditorAssetLibrary.load_blueprint_class(row["blueprint"])
            require(cls is not None, "BLUEPRINT_CLASS|" + row["blueprint"])
            components = blueprint_component_rows(figure)
            bodies = [item for item in components
                      if item["class"] == "SkeletalMeshComponent" and item["name"] in ("Body", "Body_GEN_VARIABLE")]
            cloth = [item for item in components if item["class"] == "ChaosClothComponent"]
            require(len(bodies) == 1, "PREFLIGHT_BODY_COMPONENT|%s|%d" % (figure, len(bodies)))
            require(len(cloth) == 1, "PREFLIGHT_CLOTH_COMPONENT|%s|%d" % (figure, len(cloth)))
            require(figure in by_figure and "short" in by_figure[figure]["roles"],
                    "PREFLIGHT_OUTFIT_TEMPLATE|" + figure)
            blueprint_rows.append({"figure": figure, "blueprint": row["blueprint"],
                                   "body": bodies[0], "cloth": cloth[0]})
            if row["animation_name"] not in animations:
                animation = find_animation(row["animation_name"])
                animations[row["animation_name"]] = {"path": path_of(animation),
                                                       "length_seconds": float(animation.get_play_length())}
        except Exception as exc:
            problems.append("PREFLIGHT_PLACEMENT|%s|%s" % (row["label"], exc))
    outfit_actors = []
    if cfg["outfit"]["enabled"]:
        for row in outfit_rows:
            if unreal.EditorAssetLibrary.does_asset_exist(row["child"]):
                problems.append("OUTFIT_CHILD_EXISTS|" + row["child"])
        for actor in actors:
            if shore_id_from_class(actor) in core.FIGURES:
                try:
                    outfit_actors.append(actor_outfit_preflight(actor))
                except Exception as exc:
                    problems.append("PREFLIGHT_OUTFIT_ACTOR|%s|%s" %
                                    (str(actor.get_actor_label()), exc))
    backup_packages = [core.WORLD, core.CLAMS]
    if cfg["cloth_reset"]["enabled"]:
        backup_packages += sorted(core.BP_PATHS.values())
    backup_files = []
    for package in backup_packages:
        extension = ".umap" if package == core.WORLD else ".uasset"
        filename = package_file(package, extension)
        if not os.path.isfile(filename):
            problems.append("BACKUP_SOURCE_MISSING|" + filename)
        else:
            backup_files.append({"package": package, "file": filename, "bytes": os.path.getsize(filename)})
    return {"ready": not problems, "problems": problems, "transform_schema": transform_schema,
            "blueprints": blueprint_rows, "animations": animations,
            "existing_outfit_actors": outfit_actors, "backup_files": backup_files,
            "world": path_of(world), "cloth_templates": len(cloth_rows)}


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
    preflight = apply_preflight(world, actors, clams, placement, cloth, outfit, cfg)
    shore05 = [row for row in inventory if row["label"] == "Shore05_M53 Clam"]
    problems = []
    if shore05:
        problems.append("SHORE05_ALREADY_PLACED|count=%d" % len(shore05))
    if any(row["weave_tint"] is None for row in cloth):
        problems.append("WEAVE_TINT_UNREADABLE")
    if cfg["outfit"]["enabled"]:
        problems += ["OUTFIT_PARAMETER|%s|%s" % (row["figure"], row["parameter_problem"])
                     for row in outfit if row["parameter_problem"]]
    problems += preflight["problems"]
    problems += ["CLOTH_PIN_UNVERIFIED|%s|%s" % (row["figure"], row["asset"])
                 for row in cloth if not row["pin_ready_v3_name"]]
    return {"world": world, "actors": actors, "scene": scene, "clams": clams,
            "inventory": inventory, "placement": placement, "cloth": cloth, "outfit": outfit,
            "apply_preflight": preflight, "problems": problems, "census": census()}


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
              "apply_preflight": facts["apply_preflight"],
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
    section = add_section_readback(track, "ANIMATION_SECTION")
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
    track = add_track_readback(binding, unreal.MovieScene3DTransformTrack,
                               "MovieScene3DTransformTrack", "TRANSFORM_TRACK")
    section = add_section_readback(track, "TRANSFORM_SECTION"); section.set_range(*core.PLAYBACK)
    loc, rot, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
    wanted = {"Location.X": loc.x, "Location.Y": loc.y, "Location.Z": loc.z,
              "Rotation.X": rot.roll, "Rotation.Y": rot.pitch, "Rotation.Z": rot.yaw,
              "Scale.X": scale.x, "Scale.Y": scale.y, "Scale.Z": scale.z}
    channels = transform_channels(section, "TRANSFORM_CHANNELS")
    for name, value in wanted.items():
        channels[name].set_default(float(value))
    return str(track.get_name())


def add_visibility(binding):
    track = add_track_readback(binding, unreal.MovieSceneVisibilityTrack,
                               "MovieSceneVisibilityTrack", "VISIBILITY_TRACK")
    track.set_property_name_and_path("bHidden", "bHidden")
    section = add_section_readback(track, "VISIBILITY_SECTION"); section.set_range(*core.PLAYBACK)
    channels = list(section.get_all_channels())
    require(len(channels) == 1, "VISIBILITY_CHANNELS")
    # UE visibility bool channels store VISIBLE, despite binding AActor::bHidden.
    channels[0].add_key(unreal.FrameNumber(0), False, time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    channels[0].add_key(unreal.FrameNumber(core.FIRST_CROWD_VISIBLE), True,
                        time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return str(track.get_name())


def spawn_placements(world, clams, plan, run, inputs):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    created = []
    for row in plan["placements"]:
        cls = inputs["classes"][row["label"]]
        xyz = row["world_xyz_cm"]
        actor = subsystem.spawn_actor_from_class(cls, unreal.Vector(*xyz),
                                                 unreal.Rotator(roll=0.0, pitch=0.0, yaw=float(row["yaw_deg"])))
        require(actor is not None, "SPAWN|" + row["label"])
        actor.set_actor_label(row["label"])
        actor.set_editor_property("tags", list(prop(actor, "tags", [])) +
                                  [unreal.Name(TAG), unreal.Name("P40.Source." + row["source"])])
        actor_binding = add_possessable_readback(clams, actor, "ACTOR_BINDING|" + row["label"])
        actor_binding.set_display_name(row["label"])
        transform_track = add_transform(actor_binding, actor)
        visibility_track = add_visibility(actor_binding)
        bodies = [c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                  if str(c.get_name()) == "Body"]
        require(len(bodies) == 1, "BODY_COMPONENT|%s|%d" % (row["label"], len(bodies)))
        body_binding = add_possessable_readback(clams, bodies[0], "BODY_BINDING|" + row["label"])
        body_binding.set_display_name(row["label"] + "/Body")
        body_binding.set_parent(actor_binding)
        animation_track = add_track_readback(body_binding, unreal.MovieSceneSkeletalAnimationTrack,
                                             "MovieSceneSkeletalAnimationTrack", "ANIMATION_TRACK")
        animation_track.set_display_name("P40 Forward Loops " + run)
        animation = inputs["animations"][row["animation_name"]]
        sections = [add_animation(animation_track, clams, animation, item) for item in row["motion"]]
        cloth = [c for c in actor.get_components_by_class(unreal.ActorComponent)
                 if str(c.get_class().get_name()) == "ChaosClothComponent"]
        require(len(cloth) == 1, "CLOTH_COMPONENT|%s|%d" % (row["label"], len(cloth)))
        created.append({"label": row["label"], "source": row["source"], "actor_path": full_path(actor),
                        "actor_binding": guid_text(actor_binding.get_id()),
                        "body_binding": guid_text(body_binding.get_id()),
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
        cloth.set_editor_property("teleport_distance_threshold", cfg["cloth_reset"]["teleport_distance_threshold_cm"])
        cloth.set_editor_property("teleport_rotation_threshold", cfg["cloth_reset"]["teleport_rotation_threshold_deg"])
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
        _, _, after = cloth_state(figure)
        require(after["reset"] is False and after["teleport"] is False, "CLOTH_RESET_READBACK|" + figure)
        rows.append({"figure": figure, "before": before, "after": after})
    return rows


def create_outfit_children(cfg, outfit_rows, inputs):
    tools = unreal.AssetToolsHelpers.get_asset_tools(); mel = unreal.MaterialEditingLibrary
    created = []
    for row in outfit_rows:
        require(not unreal.EditorAssetLibrary.does_asset_exist(row["child"]), "OUTFIT_CHILD_EXISTS|" + row["child"])
        folder, name = row["child"].rsplit("/", 1)
        mi = tools.create_asset(name, folder, unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
        require(mi is not None, "OUTFIT_CHILD_CREATE|" + row["child"])
        parent = inputs["outfit_parents"][row["figure"]]
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


def prepare_mutation_inputs(facts, cfg):
    """Resolve every loadable dependency before the first Unreal mutation."""
    classes = {}
    animations = {}
    parents = {}
    for row in facts["placement"]["placements"]:
        cls = unreal.EditorAssetLibrary.load_blueprint_class(row["blueprint"])
        require(cls is not None, "BLUEPRINT_CLASS|" + row["blueprint"])
        classes[row["label"]] = cls
        if row["animation_name"] not in animations:
            animations[row["animation_name"]] = find_animation(row["animation_name"])
    if cfg["outfit"]["enabled"]:
        for row in facts["outfit"]:
            require(not unreal.EditorAssetLibrary.does_asset_exist(row["child"]),
                    "OUTFIT_CHILD_EXISTS|" + row["child"])
            parent = unreal.load_asset(row["short_parent"])
            require(parent is not None, "OUTFIT_PARENT_LOAD|" + row["short_parent"])
            parents[row["figure"]] = parent
    return {"classes": classes, "animations": animations, "outfit_parents": parents}


def apply(run, cfg):
    facts = current_facts(cfg, require_clean=True)
    hard = [x for x in facts["problems"] if not x.startswith("CLOTH_PIN_UNVERIFIED")]
    require(not hard, "DRY_PROBLEMS|" + " || ".join(hard))
    require(facts["apply_preflight"]["ready"], "APPLY_PREFLIGHT")
    inputs = prepare_mutation_inputs(facts, cfg)
    bp_packages = sorted(core.BP_PATHS.values()) if cfg["cloth_reset"]["enabled"] else []
    backup_row = backup(run, bp_packages)
    record = {"schema": core.SCHEMA, "run_id": run, "state": "applying", "config": cfg,
              "backup": backup_row, "placement_plan": facts["placement"],
              "apply_preflight": facts["apply_preflight"], "cloth": [],
              "outfit_children": [], "outfit_assignments": [], "created": [], "saved": False}
    write_json(RECORD, record, exclusive=True)
    world, clams = facts["world"], facts["clams"]
    record["created"] = spawn_placements(world, clams, facts["placement"], run, inputs)
    if cfg["cloth_reset"]["enabled"]:
        record["cloth"] = cloth_apply(cfg)
    if cfg["outfit"]["enabled"]:
        record["outfit_children"] = create_outfit_children(cfg, facts["outfit"], inputs)
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
    hits = [b for b in sequence.get_bindings() if guid_text(b.get_id()) == guid]
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
        cloth.set_editor_property("teleport_distance_threshold", before["teleport_distance_threshold"])
        cloth.set_editor_property("teleport_rotation_threshold", before["teleport_rotation_threshold"])
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
