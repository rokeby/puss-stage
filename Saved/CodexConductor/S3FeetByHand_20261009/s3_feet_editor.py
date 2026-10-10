"""Guarded Unreal-side S3 feet transfer; authored and tested offline only.

DRY/SNAPSHOT/CAPTURE never open, play, or scrub Sequencer. APPLY/REVERT mutate
only transform channels on the exact resolved bindings and, for spawnables, the
binding template. The map is never saved: Gary's hand-positioned level actors
remain a disposable measurement pose while the owning sequence becomes authority.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sys
import traceback

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import s3_feet_core as core  # noqa: E402

ARGS = os.path.join(HERE, "s3_feet_args.json")
DRY_OUT = os.path.join(HERE, "s3_feet_dry_latest.json")
SNAPSHOT = os.path.join(HERE, "s3_feet_snapshot.json")
CAPTURE = os.path.join(HERE, "s3_feet_capture.json")
RECORD = os.path.join(HERE, "s3_feet_apply_record.json")
READBACK = os.path.join(HERE, "s3_feet_readback.json")


def require(condition, message):
    core.require(condition, message)


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")


def run_id():
    return "S3FEET-%s" % datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def path_of(obj):
    if obj is None:
        return None
    return str(obj.get_path_name()).split(".", 1)[0]


def full_path(obj):
    return None if obj is None else str(obj.get_path_name())


def package_name(obj):
    return path_of(obj)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(package_name(x) for x in lib.get_dirty_content_packages()),
            "maps": sorted(package_name(x) for x in lib.get_dirty_map_packages())}


def context(require_clean=False):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(ed.get_game_world() is None, "PIE_OR_SIE_RUNNING")
    world = ed.get_editor_world()
    require(path_of(world) == core.WORLD, "WRONG_WORLD|%s" % path_of(world))
    if require_clean:
        require(census() == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % json.dumps(census()))
    actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    return world, actors


def xyz(value):
    return [float(value.x), float(value.y), float(value.z)]


def transform_of(actor):
    return {"location": xyz(actor.get_actor_location()),
            "rotation": [float(actor.get_actor_rotation().roll),
                         float(actor.get_actor_rotation().pitch),
                         float(actor.get_actor_rotation().yaw)],
            "scale": xyz(actor.get_actor_scale3d())}


def actor_rows(actors):
    rows = []
    for actor in actors:
        path = full_path(actor)
        if path:
            rows.append({"path": path, "label": str(actor.get_actor_label()),
                         "class": str(actor.get_class().get_name()),
                         "transform": transform_of(actor)})
    return sorted(rows, key=lambda row: row["path"])


def target_actors(actors, cfg):
    by_label = {}
    for actor in actors:
        label = str(actor.get_actor_label())
        if core.is_target_label(label, cfg["include_p40_variants"], cfg.get("extra_target_labels", [])):
            by_label.setdefault(label, []).append(actor)
    core.validate_target_labels(list(by_label), cfg["include_p40_variants"], cfg.get("extra_target_labels", []))
    for label, hits in by_label.items():
        require(len(hits) == 1, "TARGET_ACTOR_COUNT|%s|%d" % (label, len(hits)))
    return {label: hits[0] for label, hits in by_label.items()}


def guid_text(value):
    converter = getattr(unreal.GuidLibrary, "conv_guid_to_string", None)
    require(converter is not None, "GUID_CONVERTER")
    return converter(value)


def class_name(obj):
    return str(obj.get_class().get_name())


def blend_name(section):
    text = str(section.get_blend_type()).upper()
    if "ADDITIVE" in text:
        return "ADDITIVE"
    if "RELATIVE" in text:
        return "RELATIVE"
    if "ABSOLUTE" in text or text in ("NONE", ""):
        return "ABSOLUTE"
    return text


def key_frame(key):
    try:
        time = key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    except TypeError:
        time = key.get_time()
    return int(time.frame_number.value)


def channel_state(channel):
    keys = [{"frame": key_frame(key), "value": float(key.get_value())}
            for key in channel.get_keys()]
    has_default = bool(channel.has_default()) if hasattr(channel, "has_default") else True
    return {"raw_name": str(channel.get_name()), "keys": keys,
            "has_default": has_default,
            "default": float(channel.get_default()) if has_default else None}


def transform_sections(binding):
    rows = []
    for ti, track in enumerate(binding.get_tracks()):
        if class_name(track) != "MovieScene3DTransformTrack":
            continue
        for si, section in enumerate(track.get_sections()):
            raw_channels = list(section.get_all_channels())
            names = [core.channel_base(channel.get_name()) for channel in raw_channels]
            require(len(raw_channels) == len(core.TRANSFORM_CHANNELS),
                    "TRANSFORM_CHANNEL_COUNT|%s|%r" % (binding.get_display_name(), names))
            require(tuple(names) == core.TRANSFORM_CHANNELS,
                    "TRANSFORM_CHANNEL_ORDER|%s|%r" % (binding.get_display_name(), names))
            channels = {name: channel_state(channel) for name, channel in zip(names, raw_channels)}
            row = {"track_index": ti, "section_index": si,
                   "track_name": str(track.get_name()), "section_name": str(section.get_name()),
                   "blend_type": blend_name(section), "channels": channels}
            require(row["blend_type"] in ("ABSOLUTE", "ADDITIVE"),  # 10 Oct live: LS_Clams Shore sections are ADDITIVE; a uniform key offset is still exact
                    "NON_ABSOLUTE_SECTION|%s|%s" % (binding.get_display_name(), row["blend_type"]))
            rows.append(row)
    require(rows, "NO_TRANSFORM_SECTIONS|" + str(binding.get_display_name()))
    return rows


def template_label(template):
    try:
        return str(template.get_actor_label())
    except Exception:
        return None


def sequence_tree(root):
    out = []
    seen = set()

    def walk(sequence, ancestry):
        seq_path = path_of(sequence)
        require(seq_path not in ancestry, "SEQUENCE_CYCLE|" + seq_path)
        if seq_path in seen:
            return
        seen.add(seq_path)
        out.append(sequence)
        next_ancestry = set(ancestry) | {seq_path}
        for track in sequence.get_tracks():
            if class_name(track) not in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
                continue
            for section in track.get_sections():
                getter = getattr(section, "get_sequence", None)
                child = getter() if getter else None
                if child is not None:
                    walk(child, next_ancestry)

    walk(root, set())
    return out


def binding_kind(sequence, binding):
    wanted = guid_text(binding.get_id())
    spawn = {guid_text(x.get_id()) for x in sequence.get_spawnables()}
    possess = {guid_text(x.get_id()) for x in sequence.get_possessables()}
    require((wanted in spawn) ^ (wanted in possess), "BINDING_KIND|" + wanted)
    return "spawnable" if wanted in spawn else "possessable"


def inspect_binding(sequence, binding):
    kind = binding_kind(sequence, binding)
    template = binding.get_object_template() if kind == "spawnable" else None
    row = {"sequence_path": path_of(sequence), "binding_guid": guid_text(binding.get_id()),
           "binding_display_name": str(binding.get_display_name()), "kind": kind,
           "template_path": full_path(template),
           "template_transform": transform_of(template) if template is not None else None,
           "transform_sections": transform_sections(binding)}
    row["structure_hash"] = core.stable_hash(core.structural_binding(row))
    return row


def resolve_bindings(root, targets):
    candidates = []
    for sequence in sequence_tree(root):
        for binding in sequence.get_bindings():
            display = str(binding.get_display_name())
            kind = binding_kind(sequence, binding)
            template = binding.get_object_template() if kind == "spawnable" else None
            candidates.append((sequence, binding, {display, template_label(template)} - {None}))
    resolved = {}
    used = set()
    for label in sorted(targets):
        aliases = set(core.binding_aliases(label))
        hits = [(seq, binding) for seq, binding, names in candidates if aliases & names]
        require(len(hits) == 1, "TARGET_BINDING_COUNT|%s|%d|aliases=%r" % (label, len(hits), sorted(aliases)))
        seq, binding = hits[0]
        identity = (path_of(seq), guid_text(binding.get_id()))
        require(identity not in used, "BINDING_REUSED|%s|%r" % (label, identity))
        used.add(identity)
        resolved[label] = inspect_binding(seq, binding)
    return resolved


def inventory(cfg, require_clean=False):
    world, actors = context(require_clean=require_clean)
    targets = target_actors(actors, cfg)
    root = unreal.load_asset(core.ROOT_SEQUENCE)
    require(root is not None, "ROOT_SEQUENCE_LOAD")
    bindings = resolve_bindings(root, targets)
    rows = []
    for label in sorted(targets):
        rows.append({"label": label, "actor_path": full_path(targets[label]),
                     "actor_transform": transform_of(targets[label]),
                     "binding": bindings[label]})
    return world, actors, rows


def all_actor_map(rows):
    return {row["path"]: row for row in rows}


def verify_non_target_actors(snapshot, current, target_paths):
    before = all_actor_map(snapshot)
    after = all_actor_map(current)
    require(set(before) == set(after), "ACTOR_SET_DRIFT")
    for path in sorted(set(before) - set(target_paths)):
        require(before[path]["label"] == after[path]["label"] and before[path]["class"] == after[path]["class"],
                "NON_TARGET_IDENTITY_DRIFT|" + path)
        require(core.transform_near(before[path]["transform"], after[path]["transform"]),
                "NON_TARGET_TRANSFORM_DRIFT|" + path)


def assert_binding_near(expected, actual, tolerance, rotation_tolerance=None, compare_template=True):
    rotation_tolerance = tolerance if rotation_tolerance is None else rotation_tolerance
    require(core.structural_binding(expected) == core.structural_binding(actual),
            "BINDING_STRUCTURE_DRIFT|%s" % expected["binding_guid"])
    for es, got in zip(expected["transform_sections"], actual["transform_sections"]):
        for name in core.TRANSFORM_CHANNELS:
            ec, gc = es["channels"][name], got["channels"][name]
            require(ec["has_default"] == gc["has_default"] and len(ec["keys"]) == len(gc["keys"]),
                    "CHANNEL_SHAPE_DRIFT|%s|%s" % (expected["binding_guid"], name))
            channel_tolerance = rotation_tolerance if name in core.ROTATION else tolerance
            if ec["has_default"]:
                require(core.near(ec["default"], gc["default"], channel_tolerance),
                        "DEFAULT_READBACK|%s|%s" % (expected["binding_guid"], name))
            for ek, gk in zip(ec["keys"], gc["keys"]):
                require(ek["frame"] == gk["frame"] and core.near(ek["value"], gk["value"], channel_tolerance),
                        "KEY_READBACK|%s|%s|%s" % (expected["binding_guid"], name, ek["frame"]))
    if compare_template and expected["kind"] == "spawnable":
        require(core.transform_near(expected["template_transform"], actual["template_transform"],
                                    loc_tol=tolerance, rot_tol=rotation_tolerance),
                "TEMPLATE_READBACK|" + expected["binding_guid"])


def dry(cfg):
    before = census()
    _world, _actors, targets = inventory(cfg, require_clean=False)
    after = census()
    require(before == after, "DRY_DIRTIED")
    report = {"schema": core.SCHEMA, "mode": "DRY", "run_id": run_id(),
              "targets": targets, "dirty_before": before, "dirty_after": after,
              "writes": 0, "map_save_required": False,
              "note": "No Sequencer UI, player, evaluation, play, or scrub is used."}
    write_json(DRY_OUT, report)
    unreal.log("S3_FEET_DRY_OK|run=%s|targets=%d|writes=0|dirty_unchanged=1|report=%s" %
               (report["run_id"], len(targets), DRY_OUT))
    return report


def snapshot(cfg):
    before = census()
    require(before == {"content": [], "maps": []}, "SNAPSHOT_REQUIRES_CLEAN|%s" % json.dumps(before))
    _world, actors, targets = inventory(cfg, require_clean=True)
    after = census()
    require(after == before, "SNAPSHOT_DIRTIED")
    report = {"schema": core.SCHEMA, "mode": "SNAPSHOT", "run_id": run_id(),
              "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "config": cfg, "targets": targets, "all_actors": actor_rows(actors),
              "dirty_before": before, "dirty_after": after,
              "map_save_required": False, "writes": 0}
    report["snapshot_hash"] = core.stable_hash(report)
    write_json(SNAPSHOT, report)
    unreal.log("S3_FEET_SNAPSHOT_OK|run=%s|targets=%d|writes=0|dirty_unchanged=1|output=%s" %
               (report["run_id"], len(targets), SNAPSHOT))
    return report


def capture(cfg):
    require(os.path.isfile(SNAPSHOT), "SNAPSHOT_MISSING")
    snap = load_json(SNAPSHOT)
    # The 9 Oct v1 snapshot is the pre-hand-pose evidence for Crowd 15. It has
    # the complete actor census and binding state needed by v2; do not force a
    # new snapshot after Gary's move and thereby erase the baseline.
    require(snap.get("schema") in core.CAPTURE_COMPATIBLE_SNAPSHOT_SCHEMAS and
            snap.get("mode") == "SNAPSHOT", "SNAPSHOT_SCHEMA")
    before = census()
    _world, actors, targets = inventory(cfg, require_clean=False)
    current = {row["label"]: row for row in targets}
    prior = {row["label"]: json.loads(json.dumps(row)) for row in snap["targets"]}
    if snap.get("schema") != core.SCHEMA:
        # The v1 snapshot predates the already-saved 9 Oct feet pass. Prove its
        # known applied record is exactly what is live, then use that saved
        # binding state as the new curve baseline while retaining the snapshot's
        # pre-hand actor transforms (including Crowd 15 in all_actors).
        require(os.path.isfile(RECORD), "LEGACY_SNAPSHOT_APPLY_RECORD_MISSING")
        previous = load_json(RECORD)
        require(previous.get("state") == "applied" and previous.get("saved") is True,
                "LEGACY_SNAPSHOT_RECORD_NOT_APPLIED")
        previous_targets = {row["label"]: row for row in previous.get("targets", [])}
        for label, old in prior.items():
            require(label in current and label in previous_targets,
                    "LEGACY_SNAPSHOT_REBASE_TARGET|" + label)
            expected = previous_targets[label]["expected"]
            assert_binding_near(expected, current[label]["binding"],
                                cfg["readback_tolerance_cm"], cfg["readback_tolerance_deg"])
            old["binding"] = json.loads(json.dumps(current[label]["binding"]))
    # 10 Oct: crowd copies Gary also moved (extra_target_labels) were not snapshot targets. Their pre-move pose is the
    # snapshot's all_actors row; their binding is taken from now (hand moves cannot rewrite keys; asserted below).
    by_path = {row["path"]: row for row in snap["all_actors"]}
    for label in cfg.get("extra_target_labels", []):
        if label in current and label not in prior:
            old_row = by_path.get(current[label]["actor_path"])
            require(old_row is not None, "EXTRA_TARGET_NOT_IN_SNAPSHOT|" + label)
            prior[label] = dict(current[label], actor_transform=old_row["transform"])
    require(set(current) == set(prior), "TARGET_SET_DRIFT")
    target_paths = [row["actor_path"] for row in targets]
    verify_non_target_actors(snap["all_actors"], actor_rows(actors), target_paths)
    rows = []
    owners = set()
    has_possessable = False
    for label in sorted(prior):
        old, now = prior[label], current[label]
        require(old["actor_path"] == now["actor_path"], "TARGET_PATH_DRIFT|" + label)
        require(core.structural_binding(old["binding"]) == core.structural_binding(now["binding"]),
                "BINDING_STRUCTURE_DRIFT|" + label)
        # Hand moves must not have rewritten the existing transform curves.
        assert_binding_near(old["binding"], now["binding"], cfg["readback_tolerance_cm"],
                            cfg["readback_tolerance_deg"],
                            compare_template=False)
        delta = core.capture_delta(old["actor_transform"], now["actor_transform"], cfg, label)
        owners.add(old["binding"]["sequence_path"])
        has_possessable = has_possessable or old["binding"]["kind"] == "possessable"
        rows.append({"label": label, "actor_path": old["actor_path"],
                     "snapshot_transform": old["actor_transform"],
                     "captured_transform": now["actor_transform"],
                     "delta": delta, "binding_before": old["binding"],
                     "binding_at_capture": now["binding"]})
    allowed_content = sorted(owners)
    require(not (set(before["content"]) - owners), "UNRELATED_DIRTY_CONTENT|%r" % before["content"])
    require(not (set(before["maps"]) - {core.WORLD}), "UNRELATED_DIRTY_MAP|%r" % before["maps"])
    if has_possessable:
        require(before["maps"] == [core.WORLD], "POSSESSABLE_MOVES_MUST_DIRTY_ONLY_MAP|%r" % before["maps"])
    after = census()
    require(after == before, "CAPTURE_DIRTIED")
    report = {"schema": core.SCHEMA, "mode": "CAPTURE", "run_id": snap["run_id"],
              "snapshot_hash": snap["snapshot_hash"], "config": cfg, "targets": rows,
              "owning_sequences": sorted(owners), "allowed_dirty_content": allowed_content,
              "dirty_before": before, "dirty_after": after, "writes": 0,
              "map_save_required": False,
              "map_discard_required_after_apply": bool(before["maps"])}
    report["capture_hash"] = core.stable_hash(report)
    write_json(CAPTURE, report)
    unreal.log("S3_FEET_CAPTURE_OK|run=%s|targets=%d|apply_xy=%d|allow_yaw=%d|max_delta_cm=%.3f|writes=0|dirty_unchanged=1|output=%s" %
               (report["run_id"], len(rows), int(cfg["apply_xy"]), int(cfg["allow_yaw"]),
                max(abs(x) for row in rows for x in row["delta"]["reported_location_delta_cm"]), CAPTURE))
    return report


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def project_path(relative):
    root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.normpath(os.path.join(root, relative))


def asset_file(asset_path):
    return project_path(os.path.join("Content", asset_path[len("/Game/"):].replace("/", os.sep) + ".uasset"))


def backup_assets(prefix, run, owners):
    root = project_path(os.path.join("Backups", "%s-%s" % (prefix, run)))
    require(not os.path.exists(root), "BACKUP_EXISTS|" + root)
    os.makedirs(root)
    rows = []
    for owner in sorted(owners):
        source = asset_file(owner)
        require(os.path.isfile(source), "BACKUP_SOURCE_MISSING|" + source)
        destination = os.path.join(root, os.path.relpath(source, project_path("Content")))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        require(sha_file(source) == sha_file(destination), "BACKUP_HASH|" + owner)
        rows.append({"asset": owner, "source": source, "backup": destination,
                     "bytes": os.path.getsize(destination), "sha256": sha_file(destination)})
    return {"root": root, "files": rows}


def find_binding(sequence_path, guid):
    sequence = unreal.load_asset(sequence_path)
    require(sequence is not None, "SEQUENCE_LOAD|" + sequence_path)
    hits = [binding for binding in sequence.get_bindings() if guid_text(binding.get_id()) == guid]
    require(len(hits) == 1, "BINDING_GUID_COUNT|%s|%d" % (guid, len(hits)))
    return sequence, hits[0]


def section_objects(binding, section_row):
    tracks = list(binding.get_tracks())
    require(section_row["track_index"] < len(tracks), "TRACK_INDEX")
    track = tracks[section_row["track_index"]]
    sections = list(track.get_sections())
    require(section_row["section_index"] < len(sections), "SECTION_INDEX")
    section = sections[section_row["section_index"]]
    require(str(track.get_name()) == section_row["track_name"] and str(section.get_name()) == section_row["section_name"],
            "SECTION_IDENTITY_DRIFT")
    channels = {}
    for channel in section.get_all_channels():
        channels[core.channel_base(channel.get_name())] = channel
    require(set(channels) == set(core.TRANSFORM_CHANNELS), "CHANNEL_SET_DRIFT")
    return track, section, channels


def write_binding_state(binding, saved, template_transform):
    for section_row in saved["transform_sections"]:
        _track, _section, channels = section_objects(binding, section_row)
        for name in core.LOCATION + (core.ROTATION[2],):
            channel = channels[name]
            state = section_row["channels"][name]
            keys = list(channel.get_keys())
            require(len(keys) == len(state["keys"]), "KEY_COUNT_DRIFT|" + name)
            if keys:
                for key, row in zip(keys, state["keys"]):
                    require(key_frame(key) == row["frame"], "KEY_FRAME_DRIFT|" + name)
                    key.set_value(float(row["value"]))
            else:
                require(state["has_default"], "MISSING_SAVED_DEFAULT|" + name)
                channel.set_default(float(state["default"]))
    if saved["kind"] == "spawnable":
        template = binding.get_object_template()
        require(template is not None and template_transform is not None, "SPAWNABLE_TEMPLATE_WRITE")
        template.modify()
        loc, rot = template_transform["location"], template_transform["rotation"]
        template.set_actor_location_and_rotation(
            unreal.Vector(float(loc[0]), float(loc[1]), float(loc[2])),
            unreal.Rotator(roll=float(rot[0]), pitch=float(rot[1]), yaw=float(rot[2])),
            False, False)
    return True


def current_binding(saved):
    sequence, binding = find_binding(saved["sequence_path"], saved["binding_guid"])
    return sequence, binding, inspect_binding(sequence, binding)


def save_only_sequences(owners, expected_maps):
    dirty = census()
    require(dirty == {"content": sorted(owners), "maps": sorted(expected_maps)},
            "DIRTY_CENSUS_BEFORE_SAVE|got=%s expected_content=%r expected_maps=%r" %
            (json.dumps(dirty), sorted(owners), sorted(expected_maps)))
    for owner in sorted(owners):
        require(unreal.EditorAssetLibrary.save_asset(owner, only_if_is_dirty=False), "SAVE_SEQUENCE|" + owner)
    require(census() == {"content": [], "maps": sorted(expected_maps)},
            "DIRTY_CENSUS_AFTER_SAVE|%s" % json.dumps(census()))


def apply(cfg):
    require(cfg["confirm"] == "APPLY S3 FEET", "APPLY_CONFIRM")
    require(os.path.isfile(CAPTURE), "CAPTURE_MISSING")
    cap = load_json(CAPTURE)
    require(cap.get("schema") == core.SCHEMA and cap.get("mode") == "CAPTURE", "CAPTURE_SCHEMA")
    require(bool(cfg["apply_xy"]) == bool(cap["config"]["apply_xy"]), "APPLY_XY_CHANGED_AFTER_CAPTURE")
    require(bool(cfg["allow_yaw"]) == bool(cap["config"]["allow_yaw"]), "ALLOW_YAW_CHANGED_AFTER_CAPTURE")
    require(census() == cap["dirty_after"], "STATE_DIRTY_DRIFT|%s" % json.dumps(census()))
    _world, _actors, live_rows = inventory(cfg, require_clean=False)
    live = {row["label"]: row for row in live_rows}
    for row in cap["targets"]:
        require(row["label"] in live and row["actor_path"] == live[row["label"]]["actor_path"],
                "ACTOR_DRIFT|" + row["label"])
        require(core.transform_near(row["captured_transform"], live[row["label"]]["actor_transform"]),
                "HAND_POSE_DRIFT|" + row["label"])
        assert_binding_near(row["binding_at_capture"], live[row["label"]]["binding"],
                            cfg["readback_tolerance_cm"], cfg["readback_tolerance_deg"])
    owners = cap["owning_sequences"]
    backup = backup_assets("PreS3Feet", cap["run_id"], owners)
    planned = []
    for row in cap["targets"]:
        expected = core.make_expected_binding(row["binding_at_capture"],
                                              row["delta"]["applied_location_delta_cm"],
                                              row["delta"]["applied_yaw_delta_deg"])
        if expected["kind"] == "spawnable":
            # A viewport edit can already have written into the live spawnable template.
            # Base the persistent template pose on SNAPSHOT + delta so it is never doubled.
            expected_from_snapshot = core.make_expected_binding(
                row["binding_before"], row["delta"]["applied_location_delta_cm"],
                row["delta"]["applied_yaw_delta_deg"])
            expected["template_transform"] = expected_from_snapshot["template_transform"]
        planned.append({"label": row["label"], "old": row["binding_before"], "expected": expected,
                        "delta": row["delta"]})
    record = {"schema": core.SCHEMA, "mode": "APPLY", "run_id": cap["run_id"],
              "state": "applying", "capture_hash": cap["capture_hash"], "config": cfg,
              "backup": backup, "targets": planned, "owning_sequences": owners,
              "map_dirty_census": cap["dirty_after"]["maps"], "saved": False,
              "map_save_required": False, "map_discard_required": bool(cap["dirty_after"]["maps"])}
    write_json(RECORD, record)
    for row in record["targets"]:
        _sequence, binding = find_binding(row["old"]["sequence_path"], row["old"]["binding_guid"])
        write_binding_state(binding, row["expected"], row["expected"].get("template_transform"))
    readback = []
    for row in record["targets"]:
        _sequence, _binding, got = current_binding(row["old"])
        assert_binding_near(row["expected"], got, cfg["readback_tolerance_cm"], cfg["readback_tolerance_deg"])
        readback.append({"label": row["label"], "binding": got})
    save_only_sequences(owners, cap["dirty_after"]["maps"])
    # Read again after the targeted save; this is saved-state readback, not visual proof.
    saved_readback = []
    for row in record["targets"]:
        _sequence, _binding, got = current_binding(row["old"])
        assert_binding_near(row["expected"], got, cfg["readback_tolerance_cm"], cfg["readback_tolerance_deg"])
        saved_readback.append({"label": row["label"], "binding": got})
    record["state"] = "applied"; record["saved"] = True; record["readback"] = saved_readback
    write_json(RECORD, record); write_json(READBACK, {"schema": core.SCHEMA, "mode": "APPLY_READBACK",
                                                       "run_id": cap["run_id"], "targets": saved_readback})
    unreal.log("S3_FEET_APPLY_OK|run=%s|targets=%d|sequences=%s|map_saved=0|map_discard_required=%d|readback=1|backup=%s" %
               (cap["run_id"], len(planned), owners, int(record["map_discard_required"]), backup["root"]))
    return record


def revert(cfg):
    require(cfg["confirm"] == "REVERT S3 FEET", "REVERT_CONFIRM")
    require(os.path.isfile(RECORD), "APPLY_RECORD_MISSING")
    record = load_json(RECORD)
    require(record.get("schema") == core.SCHEMA and record.get("state") == "applied" and record.get("saved") is True,
            "RECORD_NOT_APPLIED")
    now = census()
    require(now["content"] == [] and (now["maps"] == [] or now["maps"] == record["map_dirty_census"]),
            "REVERT_DIRTY_CENSUS|%s" % json.dumps(now))
    for row in record["targets"]:
        _sequence, _binding, got = current_binding(row["old"])
        assert_binding_near(row["expected"], got, cfg["readback_tolerance_cm"], cfg["readback_tolerance_deg"])
    backup = backup_assets("PreS3FeetRevert", record["run_id"], record["owning_sequences"])
    record["revert_backup"] = backup; record["state"] = "reverting"; write_json(RECORD, record)
    for row in record["targets"]:
        _sequence, binding = find_binding(row["old"]["sequence_path"], row["old"]["binding_guid"])
        write_binding_state(binding, row["old"], row["old"].get("template_transform"))
    for row in record["targets"]:
        _sequence, _binding, got = current_binding(row["old"])
        assert_binding_near(row["old"], got, cfg["readback_tolerance_cm"], cfg["readback_tolerance_deg"])
    save_only_sequences(record["owning_sequences"], now["maps"])
    restored = []
    for row in record["targets"]:
        _sequence, _binding, got = current_binding(row["old"])
        assert_binding_near(row["old"], got, cfg["readback_tolerance_cm"], cfg["readback_tolerance_deg"])
        restored.append({"label": row["label"], "binding": got})
    record["state"] = "reverted"; record["reverted"] = True; record["revert_readback"] = restored
    write_json(RECORD, record); write_json(READBACK, {"schema": core.SCHEMA, "mode": "REVERT_READBACK",
                                                       "run_id": record["run_id"], "targets": restored})
    unreal.log("S3_FEET_REVERT_OK|run=%s|targets=%d|sequences=%s|map_saved=0|dirty_maps=%s|readback=1|backup=%s" %
               (record["run_id"], len(restored), record["owning_sequences"], now["maps"], backup["root"]))
    return record


def main():
    require(unreal is not None, "UNREAL_REQUIRED")
    cfg = core.validate_config(load_json(ARGS))
    if cfg["mode"] == "DRY":
        return dry(cfg)
    if cfg["mode"] == "SNAPSHOT":
        return snapshot(cfg)
    if cfg["mode"] == "CAPTURE":
        return capture(cfg)
    if cfg["mode"] == "APPLY":
        return apply(cfg)
    return revert(cfg)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if unreal is not None:
            unreal.log_error("S3_FEET_FAILED|%s|trace=%s" % (exc, traceback.format_exc().replace("\n", " <NL> ")))
        raise
