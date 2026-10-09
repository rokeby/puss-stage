"""Guarded conductor-run Unreal tool for P38; never execute in offline work.

Operations (args.operation): ground_probe, ground_fix, handprints, lid_probe,
lid, spoiler.  Mutating operations support DRY/APPLY/VERIFY/REVERT as relevant.
All APPLY/REVERT paths require an exact clean start census, create a record and
Backups/PreP38...-<run> before the first mutation, save only named packages,
read back, and emit a run-id success marker.  No Save All and no asset deletion.
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
except ModuleNotFoundError:  # Offline harness imports this file safely.
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p38_core as core  # noqa: E402

ARGS_PATH = os.path.join(HERE, "p38_args.json")
GROUND_PROBE_PATH = os.path.join(HERE, "s3_ground_probe_latest.json")
TAG_HP = "P38.S3Handprints"
FOLDER_HP = "InfinityStage/S3/P38Handprints"
FLOAT_TOL = 1.0e-4


class Stop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def path_of(obj):
    if obj is None:
        return None
    text = str(obj.get_path_name())
    return text.split(".", 1)[0]


def vec(value):
    return [round(float(value.x), 6), round(float(value.y), 6), round(float(value.z), 6)]


def rot(value):
    return [round(float(value.roll), 6), round(float(value.pitch), 6), round(float(value.yaw), 6)]


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def world_and_actors(require_clean=True):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(ed.get_game_world() is None, "PIE_OR_SIE_RUNNING")
    world = ed.get_editor_world()
    require(world is not None and path_of(world) == core.WORLD, "WRONG_WORLD|%s" % path_of(world))
    if require_clean:
        require(census() == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % json.dumps(census()))
    actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    return world, actors


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def require_census(content=(), maps=()):
    got = census()
    expected = {"content": sorted(content), "maps": sorted(maps)}
    require(got == expected, "DIRTY_CENSUS|got=%s|expected=%s" % (json.dumps(got), json.dumps(expected)))


def content_filename(package, extension):
    rel = package[len("/Game/"):].replace("/", os.sep) + extension
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), rel)


def backup_packages(prefix, run, packages):
    root = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
                        "Backups", "%s%s" % (prefix, run))
    require(not os.path.exists(root), "BACKUP_EXISTS|%s" % root)
    os.makedirs(root)
    rows = []
    for package, extension in packages:
        src = content_filename(package, extension)
        require(os.path.isfile(src), "BACKUP_SOURCE_MISSING|%s" % src)
        rel = os.path.relpath(src, unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()))
        dst = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        rows.append({"package": package, "source": src, "backup": dst, "bytes": os.path.getsize(src),
                     "sha256": sha_file(src)})
    return {"root": root, "packages": rows}


def record_path(operation):
    return os.path.join(HERE, "p38_%s_record.json" % operation)


def dry_path(operation, run):
    return os.path.join(HERE, "p38_%s_dry_%s.json" % (operation, run))


def actor_by_label(actors, label):
    rows = [a for a in actors if str(a.get_actor_label()) == label]
    require(len(rows) == 1, "ACTOR_COUNT|%s|%d" % (label, len(rows)))
    return rows[0]


def actor_bounds(actor):
    centre, extent = actor.get_actor_bounds(False)
    return {"label": str(actor.get_actor_label()), "centre": vec(centre), "extent": vec(extent)}


def components(actor, cls):
    try:
        return list(actor.get_components_by_class(cls))
    except Exception:
        return []


def material_two_sided(material):
    if material is None:
        return None
    override = prop(material, "base_property_overrides")
    if override is not None and bool(prop(override, "override_two_sided", False)):
        return bool(prop(override, "two_sided", False))
    base = material
    try:
        base = material.get_base_material()
    except Exception:
        pass
    value = prop(base, "two_sided")
    return None if value is None else bool(value)


def sample_mesh_normals(component, max_samples=32):
    """Read representative LOD0 triangle/polygon normals without mutating the mesh."""
    mesh = prop(component, "static_mesh")
    if mesh is None:
        return [], "static mesh missing"
    try:
        desc = mesh.get_static_mesh_description(0)
        require(desc is not None, "MESH_DESCRIPTION_MISSING")
        count = int(desc.get_polygon_count())
        step = max(1, count // max_samples)
        transform = component.get_component_transform()
        rows = []
        for index in range(0, count, step):
            polygon = unreal.PolygonID(index)
            method = getattr(desc, "get_polygon_vertex_instances", None) or getattr(desc, "get_polygon_perimeter_vertex_instances", None)
            require(method is not None, "NO_POLYGON_VERTEX_INSTANCE_API")
            perimeter = list(method(polygon))
            if len(perimeter) < 3:
                continue
            points = [desc.get_vertex_position(desc.get_vertex_instance_vertex(vi)) for vi in perimeter[:3]]
            ab = points[1] - points[0]; ac = points[2] - points[0]
            local = ab.cross(ac).normal()
            if hasattr(transform, "transform_vector_no_scale"):
                normal = transform.transform_vector_no_scale(local).normal()
            else:
                normal = transform.transform_vector(local).normal()
            rows.append({"polygon": index, "local_normal": vec(local), "world_normal": vec(normal),
                         "world_normal_z": float(normal.z), "tier": "measured mesh-description winding"})
            if len(rows) >= max_samples:
                break
        return rows, None if rows else "no polygons sampled"
    except Exception as exc:
        return [], repr(exc)


def trace_dune_surface(world, dune, x, y, actors_to_ignore=()):
    start = unreal.Vector(float(x), float(y), 10000.0)
    end = unreal.Vector(float(x), float(y), -10000.0)
    try:
        hit = unreal.SystemLibrary.line_trace_single(
            world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False,
            list(actors_to_ignore), unreal.DrawDebugTrace.NONE, True)
        if hit and bool(hit[0]):
            result = hit[1]
            hit_actor = prop(result, "hit_actor")
            location = prop(result, "impact_point") or prop(result, "location")
            if hit_actor == dune and location is not None:
                return {"z_cm": float(location.z), "method": "line_trace_dune", "tier": "measured"}
    except Exception as exc:
        trace_error = repr(exc)
    else:
        trace_error = "no dune collision hit"
    bounds = actor_bounds(dune)
    return {"z_cm": bounds["centre"][2] + bounds["extent"][2], "method": "dune_bounds_top",
            "tier": "inferred", "limitation": trace_error}


def light_row(world, dune, actor):
    comps = components(actor, unreal.LightComponent)
    require(len(comps) == 1, "LIGHT_COMPONENT_COUNT|%s|%d" % (actor.get_actor_label(), len(comps)))
    comp = comps[0]
    loc = vec(actor.get_actor_location())
    surface = trace_dune_surface(world, dune, loc[0], loc[1], [actor])
    names = ("cast_shadows", "cast_dynamic_shadows", "contact_shadow_length", "shadow_bias",
             "shadow_slope_bias", "source_radius", "soft_source_radius", "attenuation_radius")
    row = {"label": str(actor.get_actor_label()), "location": loc, "surface_z_cm": surface["z_cm"],
           "surface_method": surface["method"], "surface_tier": surface["tier"],
           "surface_limitation": surface.get("limitation")}
    for name in names:
        value = prop(comp, name)
        if value is not None:
            row[name] = bool(value) if isinstance(value, bool) else float(value)
    return row


def figure_rows(world, dune, actors):
    out = []
    for actor in actors:
        label = str(actor.get_actor_label())
        tags = {str(x) for x in prop(actor, "tags", [])}
        if "P21.S3Crowd" not in tags and not label.startswith("S3 Crowd") and not label.startswith("Shore"):
            continue
        skels = components(actor, unreal.SkeletalMeshComponent)
        if not skels:
            continue
        samples = []
        for comp in skels:
            try:
                count = int(comp.get_num_bones())
            except Exception:
                count = 0
            for index in range(count):
                name = str(comp.get_bone_name(index))
                if not any(token in name.lower() for token in ("foot", "ball", "toe", "ankle")):
                    continue
                try:
                    p = comp.get_bone_location(name, unreal.BoneSpaces.WORLD_SPACE)
                    samples.append({"bone": name, "location": vec(p)})
                except Exception:
                    pass
        row = {"label": label, "foot_samples": samples, "sequence_evaluated": False,
               "tier": "inferred", "limitation": "current editor pose only; no Sequencer scrub/evaluation"}
        if samples:
            foot = min(samples, key=lambda x: x["location"][2])
            surf = trace_dune_surface(world, dune, foot["location"][0], foot["location"][1], [actor])
            row.update({"lowest_foot": foot, "surface_z_cm": surf["z_cm"], "surface_method": surf["method"],
                        "foot_gap_cm": foot["location"][2] - surf["z_cm"]})
        out.append(row)
    return out


def run_ground_probe(args, run):
    world, actors = world_and_actors(require_clean=False)
    dune = actor_by_label(actors, args["ground"]["dune_label"])
    sms = components(dune, unreal.StaticMeshComponent)
    require(len(sms) == 1, "DUNE_STATIC_MESH_COMPONENT_COUNT|%d" % len(sms))
    comp = sms[0]
    mats = []
    for index in range(int(comp.get_num_materials())):
        material = comp.get_material(index)
        mats.append({"slot": index, "path": path_of(material), "two_sided": material_two_sided(material)})
    normal_samples, normal_limitation = sample_mesh_normals(comp)
    flags = {"cast_shadow": prop(comp, "cast_shadow"), "cast_dynamic_shadow": prop(comp, "cast_dynamic_shadow")}
    lights = [light_row(world, dune, actor_by_label(actors, label)) for label in args["ground"]["fire_light_labels"]]
    observation = {
        "schema": core.SCHEMA, "operation": "ground_probe", "run_id": run, "world": core.WORLD,
        "tier": "measured live read-only except fields explicitly marked inferred/unclear",
        "dune": {"label": str(dune.get_actor_label()), "bounds": actor_bounds(dune), "mobility": str(prop(comp, "mobility")),
                 "shadow_flags": flags,
                 "receive_shadow_note": "StaticMeshComponent has no independent receive-shadow flag; material/normal evidence is reported separately",
                 "materials": mats, "normal_samples": normal_samples,
                 "normal_limitation": normal_limitation},
        "lights": lights, "figures": figure_rows(world, dune, actors), "dirty_census": census(),
    }
    observation["ranking"] = core.rank_ground_candidates(observation, args["ground"].get("thresholds"))
    write_json(GROUND_PROBE_PATH, observation)
    require(census() == observation["dirty_census"], "PROBE_MUTATED_DIRTY_STATE")
    unreal.log("P38_GROUND_PROBE_OK|run=%s|verdict=%s|lights=%d|figures=%d|dirty_unchanged=1|path=%s" %
               (run, observation["ranking"]["verdict"], len(lights), len(observation["figures"]), GROUND_PROBE_PATH))


def set_light_z(actor, lift):
    before = vec(actor.get_actor_location())
    actor.modify()
    actor.set_actor_location(actor.get_actor_location() + unreal.Vector(0.0, 0.0, float(lift)), False, False)
    return {"label": str(actor.get_actor_label()), "before": before, "after": vec(actor.get_actor_location())}


def set_shadow_bias(actor, target):
    comp = components(actor, unreal.LightComponent)[0]
    before = float(prop(comp, "shadow_bias"))
    comp.modify(); comp.set_editor_property("shadow_bias", float(target))
    return {"label": str(actor.get_actor_label()), "before": before, "after": float(prop(comp, "shadow_bias"))}


def prepare_two_sided_child(dune, run, args):
    comp = components(dune, unreal.StaticMeshComponent)[0]
    slot = int(args["ground_fix"].get("material_slot", 0))
    parent = comp.get_material(slot)
    require(parent is not None, "DUNE_PARENT_MATERIAL_MISSING")
    directory = args["ground_fix"]["new_mi_dir"]
    name = "MI_P38_S3DuneTwoSided_%s" % run.replace("-", "_")
    path = directory + "/" + name
    require(not unreal.EditorAssetLibrary.does_asset_exist(path), "TARGET_MI_EXISTS|%s" % path)
    mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, directory, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    require(mi is not None, "MI_CREATE_FAILED")
    unreal.MaterialEditingLibrary.set_material_instance_parent(mi, parent)
    overrides = prop(mi, "base_property_overrides")
    require(overrides is not None, "MI_BASE_OVERRIDES_UNAVAILABLE")
    overrides.set_editor_property("override_two_sided", True)
    overrides.set_editor_property("two_sided", True)
    mi.set_editor_property("base_property_overrides", overrides)
    unreal.MaterialEditingLibrary.update_material_instance(mi)
    require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), "MI_SAVE_FAILED")
    return {"slot": slot, "parent": path_of(parent), "child": path}


def verify_ground_state(rec, actors):
    kind = rec["kind"]
    if kind == "light_z_lift":
        for row in rec["changes"]:
            got = vec(actor_by_label(actors, row["label"]).get_actor_location())
            require(max(abs(a-b) for a,b in zip(got, row["after"])) <= 0.01, "VERIFY_LIGHT_Z|%s" % row["label"])
    elif kind == "shadow_bias":
        for row in rec["changes"]:
            comp = components(actor_by_label(actors, row["label"]), unreal.LightComponent)[0]
            require(abs(float(prop(comp, "shadow_bias")) - row["after"]) <= FLOAT_TOL, "VERIFY_BIAS|%s" % row["label"])
    elif kind == "material_two_sided_child":
        dune = actor_by_label(actors, rec["dune_label"])
        mi = unreal.load_asset(rec["material"]["child"])
        require(mi is not None and material_two_sided(mi) is True, "VERIFY_TWO_SIDED_MI")
        require(path_of(components(dune, unreal.StaticMeshComponent)[0].get_material(rec["material"]["slot"])) == rec["material"]["child"],
                "VERIFY_DUNE_MI_ASSIGNMENT")


def run_ground_fix(args, run, mode):
    probe = load_json(GROUND_PROBE_PATH)
    kind = args["ground_fix"]["kind"]
    core.ground_fix_from_probe(probe, kind)
    proved = {row["candidate"] for row in probe["ranking"]["candidates"] if row["verdict"] == "PROVED"}
    if kind == "light_z_lift":
        requested_labels = list(args["ground_fix"].get("light_labels") or [])
        require(requested_labels, "GROUND_LIGHT_LABELS_REQUIRED_FROM_PROBE")
        require(all("light_origin:" + label in proved for label in requested_labels),
                "GROUND_LIGHT_LABEL_NOT_PROVED|%s" % requested_labels)
    world, actors = world_and_actors(require_clean=(mode != "VERIFY"))
    rec_path = record_path("ground_fix")
    if mode == "DRY":
        report = {"run_id": run, "operation": "ground_fix", "mode": mode, "kind": kind,
                  "probe_run": probe["run_id"], "proved_gate": True, "params": args["ground_fix"], "mutated": False}
        write_json(dry_path("ground_fix", run), report)
        unreal.log("P38_GROUND_FIX_DRY_OK|run=%s|kind=%s|probe=%s|mutated=0" % (run, kind, probe["run_id"]))
        return
    if mode == "VERIFY":
        rec = load_json(rec_path)
        require(rec.get("saved") is True and rec["apply_run"] != run, "GROUND_FIX_NOT_SAVED_OR_SAME_CALL")
        verify_ground_state(rec, actors)
        require_census()
        rec["verified"] = True; rec["verify_run"] = run
        write_json(rec_path, rec)
        unreal.log("P38_GROUND_FIX_VERIFY_OK|run=%s|kind=%s|saved_readback=1|dirty=0" % (run, rec["kind"]))
        return
    if mode == "APPLY":
        require(not os.path.exists(rec_path), "RECORD_EXISTS")
        backup = backup_packages("PreP38GroundFix-", run, [(core.WORLD, ".umap")])
        rec = {"schema": core.SCHEMA, "operation": "ground_fix", "kind": kind, "apply_run": run,
               "probe_run": probe["run_id"], "backup": backup, "saved": False, "verified": False,
               "dune_label": args["ground"]["dune_label"], "changes": []}
        write_json(rec_path, rec, exclusive=True)
        if kind == "light_z_lift":
            labels = args["ground_fix"]["light_labels"]
            rec["changes"] = [set_light_z(actor_by_label(actors, label), args["ground_fix"]["light_z_lift_cm"]) for label in labels]
        elif kind == "shadow_bias":
            labels = args["ground_fix"].get("light_labels") or args["ground"]["fire_light_labels"]
            rec["changes"] = [set_shadow_bias(actor_by_label(actors, label), args["ground_fix"]["shadow_bias"]) for label in labels]
        elif kind == "material_two_sided_child":
            dune = actor_by_label(actors, args["ground"]["dune_label"])
            rec["material"] = prepare_two_sided_child(dune, run, args)
            comp = components(dune, unreal.StaticMeshComponent)[0]
            comp.modify(); comp.set_material(rec["material"]["slot"], unreal.load_asset(rec["material"]["child"]))
        write_json(rec_path, rec)
        require_census(maps=[core.WORLD])
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
        require_census()
        rec["saved"] = True; write_json(rec_path, rec)
        unreal.log("P38_GROUND_FIX_APPLY_PENDING_VERIFY|run=%s|kind=%s|saved=1|dirty=0|record=%s" % (run, kind, rec_path))
        return
    if mode == "REVERT":
        rec = load_json(rec_path)
        require(rec.get("saved") is True, "NO_SAVED_APPLY")
        backup = backup_packages("PreP38GroundFixRevert-", run, [(core.WORLD, ".umap")])
        rec["revert_backup"] = backup; rec["revert_run"] = run; write_json(rec_path, rec)
        if rec["kind"] == "light_z_lift":
            for row in rec["changes"]:
                actor = actor_by_label(actors, row["label"]); actor.modify()
                actor.set_actor_location(unreal.Vector(*row["before"]), False, False)
        elif rec["kind"] == "shadow_bias":
            for row in rec["changes"]:
                comp = components(actor_by_label(actors, row["label"]), unreal.LightComponent)[0]
                comp.modify(); comp.set_editor_property("shadow_bias", row["before"])
        else:
            dune = actor_by_label(actors, rec["dune_label"]); comp = components(dune, unreal.StaticMeshComponent)[0]
            parent = unreal.load_asset(rec["material"]["parent"])
            require(parent is not None, "PARENT_MATERIAL_MISSING")
            comp.modify(); comp.set_material(rec["material"]["slot"], parent)
            rec["retained_unreferenced_asset"] = rec["material"]["child"]
        require_census(maps=[core.WORLD])
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
        require_census(); rec["reverted"] = True; write_json(rec_path, rec)
        unreal.log("P38_GROUND_FIX_REVERT_OK|run=%s|kind=%s|saved=1|dirty=0|retained_assets=%d" %
                   (run, rec["kind"], 1 if rec.get("retained_unreferenced_asset") else 0))


def sequence_binding(seq, display_name):
    rows = [b for b in seq.get_bindings() if str(b.get_display_name()) == display_name]
    require(len(rows) == 1, "BINDING_COUNT|%s|%d" % (display_name, len(rows)))
    return rows[0]


def transform_channel(binding, index):
    tracks = [t for t in binding.get_tracks() if t.get_class().get_name() == "MovieScene3DTransformTrack"]
    require(len(tracks) == 1, "TRANSFORM_TRACK_COUNT|%s|%d" % (binding.get_display_name(), len(tracks)))
    sections = list(tracks[0].get_sections())
    require(len(sections) == 1, "TRANSFORM_SECTION_COUNT|%s|%d" % (binding.get_display_name(), len(sections)))
    channels = list(sections[0].get_all_channels())
    require(len(channels) > index, "TRANSFORM_CHANNEL_COUNT|%d" % len(channels))
    return channels[index]


def key_rows(channel):
    return [(int(k.get_time().frame_number.value), float(k.get_value())) for k in channel.get_keys()]


def camera_points(seq, label):
    binding = sequence_binding(seq, label)
    channels = [transform_channel(binding, i) for i in range(3)]
    rows = [key_rows(c) for c in channels]
    require(all(rows) and len({len(r) for r in rows}) == 1, "CAMERA_TRANSLATION_KEYS_MISMATCH")
    require(all([t for t, _ in r] == [t for t, _ in rows[0]] for r in rows[1:]), "CAMERA_KEY_TIMES_MISMATCH")
    return [[rows[0][i][1], rows[1][i][1], rows[2][i][1]] for i in range(len(rows[0]))]


def wall_tangent(points):
    delta = [points[-1][0] - points[0][0], points[-1][1] - points[0][1], 0.0]
    return list(core.unit(delta))


def hp_tagged(actors, tag):
    return [a for a in actors if tag in {str(x) for x in prop(a, "tags", [])}]


def hp_source_rows(actors, wall_labels, tangent):
    tint = {str(a.get_actor_label()): a for a in hp_tagged(actors, "HP_S03T")}
    rows, source_actors = [], {}
    for actor in hp_tagged(actors, "HP_S03G"):
        require(isinstance(actor, unreal.DecalActor), "HP_SOURCE_NOT_DECAL|%s" % actor.get_actor_label())
        parent = actor.get_attach_parent_actor()
        label = str(actor.get_actor_label())
        parent_label = str(parent.get_actor_label()) if parent else None
        if parent_label not in wall_labels:
            continue
        component = prop(actor, "decal")
        suffix = label[len("HP_S03G"):]
        twin_label = "HP_S03T" + suffix
        rows.append({"label": label, "wall_label": parent_label, "location": vec(actor.get_actor_location()),
                     "rotation": rot(actor.get_actor_rotation()), "scale": vec(actor.get_actor_scale3d()),
                     "wall_tangent": tangent, "material": path_of(component.get_decal_material()),
                     "decal_size": vec(prop(component, "decal_size")),
                     "fade_screen_size": float(prop(component, "fade_screen_size", 0.0)),
                     "sort_order": int(prop(component, "sort_order", 0)),
                     "twin_label": twin_label if twin_label in tint else None})
        source_actors[label] = actor
        if twin_label in tint:
            source_actors[twin_label] = tint[twin_label]
    return rows, source_actors


def write_topdown_png(path, walls, points, existing, additions, size=(1200, 600)):
    """Dependency-free analytical PNG used both in Unreal DRY and offline."""
    import struct
    import zlib
    width, height = size
    all_xy = [[w["centre"][0] - w["extent"][0], w["centre"][1] - w["extent"][1]] for w in walls]
    all_xy += [[w["centre"][0] + w["extent"][0], w["centre"][1] + w["extent"][1]] for w in walls]
    all_xy += [[p[0], p[1]] for p in points]
    xs, ys = [p[0] for p in all_xy], [p[1] for p in all_xy]
    pad = 80.0; xmin, xmax = min(xs)-pad, max(xs)+pad; ymin, ymax = min(ys)-pad, max(ys)+pad
    pixels = bytearray([248, 246, 240] * width * height)
    def xy(p):
        x = int((p[0]-xmin) / max(1.0, xmax-xmin) * (width-1))
        y = height-1-int((p[1]-ymin) / max(1.0, ymax-ymin) * (height-1))
        return x, y
    def dot_at(p, colour, radius):
        x, y = xy(p)
        for dy in range(-radius, radius+1):
            for dx in range(-radius, radius+1):
                if dx*dx+dy*dy <= radius*radius and 0 <= x+dx < width and 0 <= y+dy < height:
                    i = ((y+dy)*width+(x+dx))*3; pixels[i:i+3] = bytes(colour)
    for wall in walls:
        c, e = wall["centre"], wall["extent"]
        steps = 600
        for i in range(steps+1):
            u = i/float(steps)
            dot_at((c[0]-e[0]+2*e[0]*u, c[1]-e[1]+2*e[1]*u), (70,70,70), 1)
    for row in existing: dot_at(row["location"], (50,100,190), 1)
    for row in additions: dot_at(row["location"], (215,65,45), 2)
    for p in points: dot_at(p, (20,20,20), 4)
    raw = b"".join(b"\x00" + bytes(pixels[y*width*3:(y+1)*width*3]) for y in range(height))
    def chunk(kind, data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB",width,height,8,2,0,0,0)) + \
          chunk(b"IDAT", zlib.compress(raw,9)) + chunk(b"IEND", b"")
    with open(path, "wb") as handle: handle.write(png)


def spawn_clone(source, label, location, rotation, tag, run):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = subsystem.spawn_actor_from_class(
        unreal.DecalActor, unreal.Vector(*location),
        unreal.Rotator(roll=rotation[0], pitch=rotation[1], yaw=rotation[2]))
    require(actor is not None, "HP_SPAWN_FAILED|%s" % label)
    actor.modify(); actor.set_actor_label(label); actor.set_folder_path(FOLDER_HP)
    actor.set_editor_property("tags", [unreal.Name(tag), unreal.Name("P38.run.%s" % run)])
    actor.set_actor_scale3d(source.get_actor_scale3d())
    src = prop(source, "decal"); dst = prop(actor, "decal")
    dst.modify(); dst.set_mobility(unreal.ComponentMobility.MOVABLE)
    dst.set_decal_material(src.get_decal_material())
    dst.set_editor_property("decal_size", prop(src, "decal_size"))
    dst.set_sort_order(int(prop(src, "sort_order", 0)))
    dst.set_fade_screen_size(float(prop(src, "fade_screen_size", 0.0)))
    parent = source.get_attach_parent_actor()
    if parent:
        actor.attach_to_actor(parent, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    return actor


def handprint_plan(args, actors):
    seq = unreal.load_asset(core.SCENE); require(seq is not None, "SCENE_MISSING")
    points = camera_points(seq, args["handprints"]["camera_binding"])
    walls = [actor_bounds(a) for a in actors if str(a.get_actor_label()) in args["handprints"]["wall_labels"]]
    selection = core.select_camera_wall(points, walls, args["handprints"]["max_camera_wall_distance_cm"],
                                        args["handprints"]["min_wall_margin_cm"])
    tangent = wall_tangent(points)
    rows, source_actors = hp_source_rows(actors, set(args["handprints"]["wall_labels"]), tangent)
    plan = core.plan_handprint_additions(rows, selection["selected"], args["handprints"]["increase_fraction"],
                                        args["handprints"]["seed"], args["handprints"]["tangent_jitter_cm"],
                                        args["handprints"]["vertical_jitter_cm"])
    plan.update({"wall_selection": selection, "camera_points": points, "walls": walls,
                 "existing_rows": [r for r in rows if r["wall_label"] == selection["selected"]],
                 "twin_layer_complete": all(r.get("twin_label") for r in rows)})
    return plan, source_actors


def run_handprints(args, run, mode):
    world, actors = world_and_actors()
    rec_path = record_path("handprints")
    if mode in ("DRY", "APPLY"):
        require(not hp_tagged(actors, TAG_HP), "P38_HANDPRINTS_ALREADY_PRESENT")
        plan, source = handprint_plan(args, actors)
    if mode == "DRY":
        preview = os.path.join(HERE, "handprints_topdown_%s.png" % run)
        write_topdown_png(preview, plan["walls"], plan["camera_points"], plan["existing_rows"], plan["additions"])
        report = {k:v for k,v in plan.items() if k != "existing_rows"}
        report.update({"schema": core.SCHEMA, "run_id": run, "mode": mode, "preview": preview, "mutated": False})
        write_json(dry_path("handprints", run), report)
        require_census()
        unreal.log("P38_HANDPRINTS_DRY_OK|run=%s|wall=%s|current=%d|add=%d|fraction=%.3f|preview=%s|mutated=0" %
                   (run, plan["wall_selection"]["selected"], plan["source_count"], plan["target_additions"],
                    plan["fraction"], preview))
        return
    if mode == "APPLY":
        require(not os.path.exists(rec_path), "RECORD_EXISTS")
        backup = backup_packages("PreP38Handprints-", run, [(core.WORLD, ".umap")])
        rec = {"schema": core.SCHEMA, "operation": "handprints", "apply_run": run, "backup": backup,
               "plan_digest": plan["plan_digest"], "selected_wall": plan["wall_selection"]["selected"],
               "source_count": plan["source_count"], "target_additions": plan["target_additions"],
               "spawn_labels": [], "saved": False}
        write_json(rec_path, rec, exclusive=True)
        spawned = []
        for row in plan["additions"]:
            base = source[row["source_label"]]
            label = "P38 HP G %04d" % row["index"]
            spawned.append(spawn_clone(base, label, row["location"], row["rotation"], TAG_HP, run)); rec["spawn_labels"].append(label)
            if row.get("source_twin_label"):
                twin = source[row["source_twin_label"]]
                tlabel = "P38 HP T %04d" % row["index"]
                spawned.append(spawn_clone(twin, tlabel, row["location"], row["rotation"], TAG_HP, run)); rec["spawn_labels"].append(tlabel)
        rec["spawned"] = len(spawned); write_json(rec_path, rec)
        require(len(hp_tagged(actors + spawned, TAG_HP)) == len(spawned), "HP_COUNT_BEFORE_SAVE")
        require_census(maps=[core.WORLD])
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
        require_census()
        _, actors2 = world_and_actors()
        got = sorted(str(a.get_actor_label()) for a in hp_tagged(actors2, TAG_HP))
        require(got == sorted(rec["spawn_labels"]), "HP_READBACK_LABELS")
        rec["saved"] = True; rec["readback_count"] = len(got); write_json(rec_path, rec)
        unreal.log("P38_HANDPRINTS_APPLY_OK|run=%s|wall=%s|current=%d|added_marks=%d|spawned=%d|saved=1|dirty=0" %
                   (run, rec["selected_wall"], rec["source_count"], rec["target_additions"], rec["spawned"]))
        return
    if mode == "VERIFY":
        rec = load_json(rec_path); require(rec.get("saved") is True and rec["apply_run"] != run, "HP_NOT_SAVED_OR_SAME_CALL")
        got = sorted(str(a.get_actor_label()) for a in hp_tagged(actors, TAG_HP))
        require(got == sorted(rec["spawn_labels"]), "HP_VERIFY_LABELS")
        require_census(); rec["verified"] = True; rec["verify_run"] = run; write_json(rec_path, rec)
        unreal.log("P38_HANDPRINTS_VERIFY_OK|run=%s|spawned=%d|saved_readback=1|dirty=0" % (run, len(got)))
        return
    if mode == "REVERT":
        rec = load_json(rec_path); require(rec.get("saved") is True, "NO_SAVED_APPLY")
        owned = hp_tagged(actors, TAG_HP)
        require(sorted(str(a.get_actor_label()) for a in owned) == sorted(rec["spawn_labels"]), "HP_REVERT_DRIFT")
        rec["revert_backup"] = backup_packages("PreP38HandprintsRevert-", run, [(core.WORLD, ".umap")])
        rec["revert_run"] = run; write_json(rec_path, rec)
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for actor in owned:
            actor.modify(); require(subsystem.destroy_actor(actor), "HP_DESTROY_FAILED")
        require_census(maps=[core.WORLD])
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
        require_census(); _, actors2 = world_and_actors(); require(not hp_tagged(actors2, TAG_HP), "HP_AFTER_REVERT")
        rec["reverted"] = True; write_json(rec_path, rec)
        unreal.log("P38_HANDPRINTS_REVERT_OK|run=%s|removed=%d|saved=1|dirty=0" % (run, len(owned)))


def smoke_rows(actors, roof_bounds):
    out = []
    rc, re = roof_bounds["centre"], roof_bounds["extent"]
    for actor in actors:
        label = str(actor.get_actor_label())
        if not any(token in label.lower() for token in ("smoke", "haze", "fog")):
            continue
        b = actor_bounds(actor); c = b["centre"]
        inside_xy = abs(c[0]-rc[0]) <= re[0]+b["extent"][0] and abs(c[1]-rc[1]) <= re[1]+b["extent"][1]
        hidden_editor = bool(actor.is_hidden_ed()); hidden_game = bool(prop(actor,"hidden",False))
        out.append({"label": label, "hidden_in_editor": hidden_editor, "hidden_in_game": hidden_game,
                    "bounds": b, "overlaps_roof_xy": inside_xy,
                    "potentially_visible_through_gap": inside_xy and not hidden_editor and not hidden_game,
                    "tier": "measured geometry/flags; rendered visibility unproved"})
    return out


def visibility_snapshot(binding):
    rows = []
    for track in binding.get_tracks():
        if track.get_class().get_name() != "MovieSceneVisibilityTrack":
            continue
        sections = []
        for section in track.get_sections():
            channels = []
            for channel in section.get_all_channels():
                default = None
                try:
                    default = bool(channel.get_default()) if channel.has_default() else None
                except Exception:
                    pass
                channels.append({"default": default,
                                 "keys": [(int(k.get_time().frame_number.value), bool(k.get_value())) for k in channel.get_keys()]})
            sections.append({"range": [int(section.get_start_frame()), int(section.get_end_frame())], "channels": channels})
        rows.append({"class": "MovieSceneVisibilityTrack", "property": track_property(track), "sections": sections})
    return rows


def lid_snapshot(args, actors):
    seq = unreal.load_asset(core.RISE); require(seq is not None, "RISE_MISSING")
    binding = sequence_binding(seq, args["lid"]["roof_binding"])
    channel = transform_channel(binding, int(args["lid"]["rotation_channel_index"]))
    keys = key_rows(channel)
    plan = core.lid_closed_plan(keys, args["lid"].get("closed_value_deg"))
    roof = actor_by_label(actors, args["lid"]["roof_actor_label"])
    arrival = actor_by_label(actors, args["lid"]["arrival_actor_label"])
    drives = []
    for drive in list(prop(arrival, "additional_initial_transform_drives", [])):
        target = prop(drive, "target")
        drives.append({"target": str(target.get_actor_label()) if target else None,
                       "binding_guid": str(prop(drive, "binding_guid"))})
    context_keys = {}
    for label, index in (("S3 Hangar Root", 4), ("S3 Hangar Lattice Fly", 2)):
        try:
            context_keys[label] = key_rows(transform_channel(sequence_binding(seq, label), index))
        except Exception as exc:
            context_keys[label] = {"unclear": repr(exc)}
    return seq, channel, {"keys": keys, "plan": plan, "roof_bounds": actor_bounds(roof),
                          "roof_actor_hidden_in_editor": bool(roof.is_hidden_ed()),
                          "roof_actor_hidden_in_game": bool(prop(roof, "hidden", False)),
                          "roof_visibility_tracks": visibility_snapshot(binding),
                          "rise_context_keys": context_keys, "arrival_drives": drives,
                          "smoke_actors": smoke_rows(actors, actor_bounds(roof))}


def run_lid_probe(args, run):
    _, actors = world_and_actors(require_clean=False)
    _, _, snap = lid_snapshot(args, actors)
    report = {"schema": core.SCHEMA, "operation": "lid_probe", "run_id": run, "world": core.WORLD,
              "rise": core.RISE, "tier": "measured saved/editor read-only; rendered gap remains inferred", **snap,
              "dirty_census": census()}
    path = os.path.join(HERE, "p38_lid_probe_latest.json"); write_json(path, report)
    unreal.log("P38_LID_PROBE_OK|run=%s|keys=%d|smoke=%d|closed=%s|path=%s" %
               (run, len(snap["keys"]), len(snap["smoke_actors"]), snap["plan"]["closed_value"], path))


def run_lid(args, run, mode):
    _, actors = world_and_actors()
    seq, channel, snap = lid_snapshot(args, actors)
    rec_path = record_path("lid")
    if mode == "DRY":
        report = {"schema": core.SCHEMA, "operation": "lid", "run_id": run, "mode": mode, **snap, "mutated": False}
        write_json(dry_path("lid", run), report)
        unreal.log("P38_LID_DRY_OK|run=%s|keys=%d|closed=%s|smoke=%d|mutated=0" %
                   (run, len(snap["keys"]), snap["plan"]["closed_value"], len(snap["smoke_actors"])))
        return
    if mode == "APPLY":
        require(not os.path.exists(rec_path), "RECORD_EXISTS")
        backup = backup_packages("PreP38Lid-", run, [(core.RISE, ".uasset")])
        rec = {"schema": core.SCHEMA, "operation": "lid", "apply_run": run, "backup": backup,
               "before": snap["plan"]["before"], "after": snap["plan"]["after"], "saved": False}
        write_json(rec_path, rec, exclusive=True)
        keys = list(channel.get_keys()); require(len(keys) == len(rec["after"]), "LID_KEY_COUNT_DRIFT")
        for key, expected, after in zip(keys, rec["before"], rec["after"]):
            require(int(key.get_time().frame_number.value) == expected[0] and abs(float(key.get_value())-expected[1]) <= FLOAT_TOL,
                    "LID_KEY_DRIFT")
            key.set_value(after[1])
        require_census(content=[core.RISE])
        require(unreal.EditorAssetLibrary.save_asset(core.RISE, only_if_is_dirty=False), "RISE_SAVE_FAILED")
        require_census()
        got = key_rows(transform_channel(sequence_binding(unreal.load_asset(core.RISE), args["lid"]["roof_binding"]),
                                         int(args["lid"]["rotation_channel_index"])))
        require(all(a[0] == b[0] and abs(a[1]-b[1]) <= FLOAT_TOL for a,b in zip(got, rec["after"])), "LID_READBACK")
        rec["saved"] = True; rec["readback"] = got; write_json(rec_path, rec)
        unreal.log("P38_LID_APPLY_OK|run=%s|keys=%d|closed=%s|saved=1|dirty=0" % (run, len(got), got[0][1]))
        return
    if mode == "VERIFY":
        rec = load_json(rec_path); require(rec.get("saved") is True and rec["apply_run"] != run, "LID_NOT_SAVED_OR_SAME_CALL")
        got = key_rows(channel); require(len(got) == len(rec["after"]), "LID_VERIFY_COUNT")
        require(all(a[0] == b[0] and abs(a[1]-b[1]) <= FLOAT_TOL for a,b in zip(got, rec["after"])), "LID_VERIFY")
        require_census(); rec["verified"] = True; rec["verify_run"] = run; write_json(rec_path, rec)
        unreal.log("P38_LID_VERIFY_OK|run=%s|keys=%d|saved_readback=1|dirty=0" % (run, len(got)))
        return
    if mode == "REVERT":
        rec = load_json(rec_path); require(rec.get("saved") is True, "NO_SAVED_APPLY")
        got = key_rows(channel); require(all(a[0] == b[0] and abs(a[1]-b[1]) <= FLOAT_TOL for a,b in zip(got,rec["after"])), "LID_REVERT_DRIFT")
        rec["revert_backup"] = backup_packages("PreP38LidRevert-", run, [(core.RISE, ".uasset")]); rec["revert_run"] = run
        write_json(rec_path, rec)
        for key, before in zip(channel.get_keys(), rec["before"]): key.set_value(before[1])
        require_census(content=[core.RISE]); require(unreal.EditorAssetLibrary.save_asset(core.RISE, only_if_is_dirty=False), "RISE_SAVE_FAILED")
        require_census(); rec["reverted"] = True; write_json(rec_path, rec)
        unreal.log("P38_LID_REVERT_OK|run=%s|keys=%d|saved=1|dirty=0" % (run, len(rec["before"])))


def track_property(track):
    try:
        return str(track.get_property_name()), str(track.get_property_path())
    except Exception:
        return str(prop(track, "property_name", "")), str(prop(track, "property_path", ""))


def visibility_track(binding):
    rows = []
    for track in binding.get_tracks():
        if track.get_class().get_name() != "MovieSceneVisibilityTrack":
            continue
        name, path = track_property(track)
        if name == "bHidden" and path == "bHidden": rows.append(track)
    require(len(rows) <= 1, "MULTIPLE_BHIDDEN_TRACKS|%s" % binding.get_display_name())
    return rows[0] if rows else None


def active_visibility_channel(track, frame):
    rows = []
    for section in track.get_sections():
        if int(section.get_start_frame()) <= int(frame) < int(section.get_end_frame()):
            channels = list(section.get_all_channels())
            require(len(channels) == 1, "VISIBILITY_CHANNEL_COUNT|%d" % len(channels))
            rows.append((section, channels[0]))
    require(len(rows) == 1, "VISIBILITY_ACTIVE_SECTION_COUNT|%d" % len(rows))
    return rows[0]


def channel_bool_rows(channel):
    return [(int(k.get_time().frame_number.value), bool(k.get_value())) for k in channel.get_keys()]


def replace_bool_rows(channel, rows):
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    for frame, value in rows:
        require(channel.add_key(unreal.FrameNumber(int(frame)), bool(value),
                                time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE) is not None,
                "VISIBILITY_ADD_KEY_FAILED|%s" % frame)


def evaluate_visibility(track, seq, frame):
    _, channel = active_visibility_channel(track, frame)
    values = list(channel.evaluate_keys(seq.make_range(int(frame), 1), seq.get_display_rate()))
    require(len(values) == 1, "VISIBILITY_EVALUATE_COUNT|%d" % len(values))
    return bool(values[0])


def spoiler_candidates(actors, args):
    out = []
    for actor in actors:
        label = str(actor.get_actor_label())
        if not label.startswith(args["spoiler"]["label_prefix"]): continue
        has_light = bool(components(actor, unreal.LightComponent))
        practical = args["spoiler"]["include_practical_bulbs"] and "PRACTICAL_BULB" in label and not label.endswith(("_BODY","_CAP"))
        if has_light or practical:
            out.append(actor)
    require(out, "SPOILER_NO_CANDIDATES")
    return sorted(out, key=lambda a: str(a.get_actor_label()))


def guid_text(binding):
    guid = binding.get_id()
    return guid.export_text() if hasattr(guid, "export_text") else str(guid)


def binding_by_guid(seq, guid):
    rows = [b for b in seq.get_bindings() if guid_text(b) == guid]
    require(len(rows) == 1, "BINDING_GUID_COUNT|%s|%d" % (guid, len(rows)))
    return rows[0]


def find_or_plan_binding(seq, world, actor):
    want = actor.get_path_name()
    label = str(actor.get_actor_label())
    rows = []
    for binding in seq.get_bindings():
        try:
            resolved = [obj.get_path_name() for obj in seq.locate_bound_objects(binding, world)]
        except Exception:
            resolved = []
        if want in resolved:
            rows.append(binding)
    require(len(rows) <= 1, "SPOILER_BINDING_AMBIGUOUS|%s|%d" % (actor.get_actor_label(), len(rows)))
    if rows:
        return rows[0], False
    return None, True


def playback_frames(seq):
    return int(seq.get_playback_start()), int(seq.get_playback_end())


def run_spoiler(args, run, mode):
    world, actors = world_and_actors()
    seq = unreal.load_asset(core.SCENE); require(seq is not None, "SCENE_MISSING")
    start, end = playback_frames(seq)
    fps = float(seq.get_display_rate().numerator) / float(seq.get_display_rate().denominator)
    cut = start + int(round(float(args["spoiler"]["cut_seconds"]) * fps))
    vis_keys = core.spoiler_keys(start, end, cut)
    candidates = spoiler_candidates(actors, args)
    discovered = []
    for actor in candidates:
        binding, create = find_or_plan_binding(seq, world, actor)
        track = visibility_track(binding) if binding else None
        visible = evaluate_visibility(track, seq, cut) if track else not bool(prop(actor, "hidden", False))
        discovered.append({"label": str(actor.get_actor_label()), "create_binding": create,
                           "binding_guid": guid_text(binding) if binding else None,
                           "existing_visibility_track": track is not None,
                           "evaluates_visible_at_cut": visible})
    planned = [row for row in discovered if row["evaluates_visible_at_cut"]]
    target_labels = {row["label"] for row in planned}
    target_actors = [actor for actor in candidates if str(actor.get_actor_label()) in target_labels]
    rec_path = record_path("spoiler")
    if mode == "DRY":
        report = {"schema": core.SCHEMA, "operation": "spoiler", "run_id": run, "mode": mode,
                  "display_fps": fps, "playback": [start,end], "cut_frame": cut, "cut_seconds": args["spoiler"]["cut_seconds"],
                  "property_name": "bHidden", "property_path": "bHidden", "bool_semantics": "VISIBLE: True=shown False=hidden",
                  "keys": vis_keys, "discovered": discovered, "targets": planned, "mutated": False}
        write_json(dry_path("spoiler", run), report)
        unreal.log("P38_SPOILER_DRY_OK|run=%s|actors=%d|cut_frame=%d|seconds=%.3f|bHidden_visible_semantics=1|mutated=0" %
                   (run, len(planned), cut, args["spoiler"]["cut_seconds"]))
        return
    if mode == "APPLY":
        require(not os.path.exists(rec_path), "RECORD_EXISTS")
        backup = backup_packages("PreP38Spoiler-", run, [(core.SCENE, ".uasset")])
        rec = {"schema": core.SCHEMA, "operation": "spoiler", "apply_run": run, "backup": backup,
               "cut_frame": cut, "keys": vis_keys, "planned_labels": sorted(target_labels), "rows": [], "saved": False}
        write_json(rec_path, rec, exclusive=True)
        for actor, row in zip(target_actors, planned):
            if row["create_binding"]:
                existing_guids = {guid_text(item) for item in seq.get_bindings()}
                binding = seq.add_possessable(actor)
                require(guid_text(binding) not in existing_guids,
                        "ADD_POSSESSABLE_RETURNED_EXISTING|%s|REFUSE_RENAME" % row["label"])
                binding.set_display_name(row["label"])
            else:
                binding = binding_by_guid(seq, row["binding_guid"])
            track = visibility_track(binding)
            if track is None:
                rec_row = {"label": row["label"], "binding_guid": guid_text(binding),
                           "created_binding": row["create_binding"], "created_track": True,
                           "before_keys": None}
                rec["rows"].append(rec_row); write_json(rec_path, rec)
                track = binding.add_track(unreal.MovieSceneVisibilityTrack)
                track.set_property_name_and_path("bHidden", "bHidden")
                require(track_property(track) == ("bHidden", "bHidden"), "SPOILER_VISIBILITY_BINDING|%s" % row["label"])
                section = track.add_section(); section.set_range(start, end)
                channel = section.get_all_channels()[0]
                replace_bool_rows(channel, vis_keys)
            else:
                section, channel = active_visibility_channel(track, cut)
                before_keys = channel_bool_rows(channel)
                after_keys = [(t,v) for t,v in before_keys if t != cut] + [(cut,False)]
                after_keys.sort()
                rec_row = {"label": row["label"], "binding_guid": guid_text(binding),
                           "created_binding": False, "created_track": False,
                           "section_name": str(section.get_name()), "before_keys": before_keys}
                rec["rows"].append(rec_row); write_json(rec_path, rec)
                replace_bool_rows(channel, after_keys)
            rec_row["after_keys"] = channel_bool_rows(channel); write_json(rec_path, rec)
        require_census(content=[core.SCENE]); require(unreal.EditorAssetLibrary.save_asset(core.SCENE, only_if_is_dirty=False), "SCENE_SAVE_FAILED")
        require_census()
        seq2 = unreal.load_asset(core.SCENE)
        for row in rec["rows"]:
            binding = binding_by_guid(seq2, row["binding_guid"]); track = visibility_track(binding); require(track is not None, "SPOILER_TRACK_READBACK")
            require(evaluate_visibility(track, seq2, cut) is False, "SPOILER_CUT_STILL_VISIBLE|%s" % row["label"])
            _, channel = active_visibility_channel(track, cut); got = channel_bool_rows(channel)
            require(got == [tuple(x) for x in row["after_keys"]], "SPOILER_KEYS_READBACK|%s|%s" % (row["label"], got))
        rec["saved"] = True; rec["readback_count"] = len(rec["rows"]); write_json(rec_path, rec)
        unreal.log("P38_SPOILER_APPLY_OK|run=%s|actors=%d|cut_frame=%d|saved=1|dirty=0" % (run,len(rec["rows"]),cut))
        return
    if mode == "VERIFY":
        rec = load_json(rec_path); require(rec.get("saved") is True and rec["apply_run"] != run, "SPOILER_NOT_SAVED_OR_SAME_CALL")
        for row in rec["rows"]:
            track = visibility_track(binding_by_guid(seq,row["binding_guid"])); require(track is not None,"SPOILER_VERIFY_TRACK")
            require(evaluate_visibility(track,seq,rec["cut_frame"]) is False,"SPOILER_VERIFY_VISIBLE|%s"%row["label"])
            _, channel = active_visibility_channel(track,rec["cut_frame"]); got = channel_bool_rows(channel)
            require(got == [tuple(x) for x in row["after_keys"]], "SPOILER_VERIFY_KEYS|%s" % row["label"])
        require_census(); rec["verified"] = True; rec["verify_run"] = run; write_json(rec_path,rec)
        unreal.log("P38_SPOILER_VERIFY_OK|run=%s|actors=%d|saved_readback=1|dirty=0" % (run,len(rec["rows"])))
        return
    if mode == "REVERT":
        rec = load_json(rec_path); require(rec.get("saved") is True,"NO_SAVED_APPLY")
        rec["revert_backup"] = backup_packages("PreP38SpoilerRevert-",run,[(core.SCENE,".uasset")]); rec["revert_run"] = run
        write_json(rec_path,rec)
        for row in rec["rows"]:
            binding = binding_by_guid(seq,row["binding_guid"]); track = visibility_track(binding); require(track is not None,"SPOILER_REVERT_DRIFT")
            if row["created_binding"]: binding.remove()
            elif row["created_track"]: binding.remove_track(track)
            else:
                _, channel = active_visibility_channel(track,rec["cut_frame"])
                require(channel_bool_rows(channel) == [tuple(x) for x in row["after_keys"]],"SPOILER_REVERT_KEY_DRIFT")
                replace_bool_rows(channel,row["before_keys"])
        require_census(content=[core.SCENE]); require(unreal.EditorAssetLibrary.save_asset(core.SCENE,only_if_is_dirty=False),"SCENE_SAVE_FAILED")
        require_census(); rec["reverted"] = True; write_json(rec_path,rec)
        unreal.log("P38_SPOILER_REVERT_OK|run=%s|actors=%d|saved=1|dirty=0" % (run,len(rec["rows"])))


def main():
    require(unreal is not None, "UNREAL_REQUIRED")
    args = load_json(ARGS_PATH)
    operation = str(args["operation"]); mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or datetime.datetime.now().strftime("P38-%Y%m%d-%H%M%S"))
    core.require_confirm(operation, mode, args.get("confirm"))
    dispatch = {"ground_probe": lambda: run_ground_probe(args,run),
                "ground_fix": lambda: run_ground_fix(args,run,mode),
                "handprints": lambda: run_handprints(args,run,mode),
                "lid_probe": lambda: run_lid_probe(args,run),
                "lid": lambda: run_lid(args,run,mode),
                "spoiler": lambda: run_spoiler(args,run,mode)}
    require(operation in dispatch, "OPERATION|%s" % operation)
    dispatch[operation]()


if unreal is not None and __name__ in ("__main__", "<run_path>"):
    try:
        main()
    except (Stop, core.P38Error) as exc:
        unreal.log_error("P38_STOPPED|reason=%s|census=%s|NEEDS_DONT_SAVE_RESTART_IF_DIRTY" % (exc,json.dumps(census())))
    except Exception:
        unreal.log_error("P38_ERROR|traceback=%s|census=%s|NEEDS_DONT_SAVE_RESTART_IF_DIRTY" %
                         (traceback.format_exc().replace("\n","\\n"),json.dumps(census())))
