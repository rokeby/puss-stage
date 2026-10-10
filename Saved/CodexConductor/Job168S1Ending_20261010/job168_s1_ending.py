"""Job 168, stage A: fade S1 animals and retime the owned exit handoff.

Offline-authored only.  This module never opens Unreal by itself.  It changes
only LS_DevScene_01, which is PussStage-owned.  Klara's copied sequence and
L_Animals are surveyed read-only and their on-disk SHA-256 values are guarded.

The material audit is deliberately fail-closed.  A persistent MID cannot be
owned by a Level Sequence, and the three independently authored animal
materials are not proven to share a scalar wired to opacity.  Gary explicitly
allowed a scale/visibility fallback, so APPLY adds an ADDITIVE transform scale
delta (0 to -1) for three seconds and a Visibility track bound to
AActor::bHidden (channel True means visible).  Translation/rotation remain
Klara-owned and continue evaluating underneath the additive scale.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:
    unreal = None


TOOL = "JOB168_S1_ANIMALS"
VERSION = 1
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
KLARA = "/Game/InfinityStage/KlaraHookin/LS_Animals_1_S1Hangar"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
TRACK_NAME = "JOB168 Animal Scale Fade"
RECORD_NAME = "job168_animals_record.json"
PLAN_NAME = "job168_animals_apply_ready.json"
VALID_MODES = ("DRY", "APPLY", "REVERT")
SCALE_CHANNELS = ("Scale.X", "Scale.Y", "Scale.Z")


class Refusal(RuntimeError):
    pass


def stable_digest(value):
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def review_digest(report):
    """Hash only reviewable live state; DRY/APPLY mode and run ids may differ."""
    return stable_digest({key: report[key] for key in
                          ("plan", "animal_author", "material_audit", "before_digest",
                           "klara_guard", "exit_cut_before", "klara_content_past_new_wrapper_end")})


def timing_plan(args, fps=25.0):
    fade_end = int(args["animal_fade_end_frame"])
    fade_frames = int(round(float(args["animal_fade_seconds"]) * fps))
    lights_start = int(args["lights_out_start_frame"])
    lights_frames = int(round(float(args["lights_out_fade_seconds"]) * fps))
    new_end = int(args["new_end_frame"])
    exit_frames = int(args["exit_handoff_frames"])
    return {
        "fps": fps,
        "animal_fade": [fade_end - fade_frames, fade_end],
        "lights_out": [lights_start, lights_start + lights_frames],
        "exit_handoff": [new_end - exit_frames, new_end],
        "new_end": new_end,
    }


def validate_args(args):
    errors = []
    mode = str(args.get("mode") or "").upper()
    if mode not in VALID_MODES:
        errors.append("MODE_INVALID")
    if args.get("confirm") != "%s JOB168" % mode:
        errors.append("CONFIRM_MISMATCH")
    if args.get("scene_sequence") != SCENE or args.get("klara_copy") != KLARA:
        errors.append("ASSET_AUTHORITY_MISMATCH")
    labels = args.get("animal_labels")
    if not isinstance(labels, list) or len(labels) != 3 or len(set(labels)) != 3:
        errors.append("ANIMAL_LABELS_REQUIRE_THREE_UNIQUE")
    if args.get("animal_fade_strategy") != "ADDITIVE_SCALE_AND_BHIDDEN_FALLBACK":
        errors.append("UNREVIEWED_FADE_STRATEGY")
    try:
        plan = timing_plan(args)
        if plan["animal_fade"][0] < 0 or plan["animal_fade"][1] >= plan["lights_out"][0]:
            errors.append("ANIMAL_LIGHTS_ORDER")
        if plan["lights_out"][1] >= plan["exit_handoff"][0]:
            errors.append("LIGHTS_HANDOFF_OVERLAP")
        if plan["exit_handoff"][1] != plan["new_end"]:
            errors.append("HANDOFF_END_MISMATCH")
    except (KeyError, TypeError, ValueError):
        errors.append("TIMING_INVALID")
    return errors


def source_to_scene_frame(source_frame, shot_start=594, start_offset_ticks=86400,
                          source_tick=24000, source_fps=30.0, scene_fps=25.0):
    """Map a Klara-copy display frame into the outer S1 display rate."""
    offset_seconds = float(start_offset_ticks) / float(source_tick)
    source_seconds = float(source_frame) / float(source_fps)
    return float(shot_start) + (source_seconds - offset_seconds) * float(scene_fps)


def scene_to_source_frame(scene_frame, shot_start=594, start_offset_ticks=86400,
                          source_tick=24000, source_fps=30.0, scene_fps=25.0):
    offset_seconds = float(start_offset_ticks) / float(source_tick)
    source_seconds = offset_seconds + (float(scene_frame) - float(shot_start)) / float(scene_fps)
    return source_seconds * float(source_fps)


def author_verdict(rows):
    """Pure classifier used by DRY and the harness."""
    wanted = {"Pig_anim_RM", "medhue_raccoon", "RedDeer_Calf_anim_IP"}
    exits, visibility = [], []
    for row in rows:
        if row.get("owner") not in wanted:
            continue
        if row.get("class") == "MovieSceneVisibilityTrack":
            visibility.append(row)
        if row.get("class") == "MovieScene3DTransformTrack" and row.get("late_additive"):
            exits.append(row)
    return {
        "authority": "KLARA_COPY_TRANSFORM" if {r["owner"] for r in exits} == wanted and not visibility else "UNCLEAR",
        "exit_transforms": exits,
        "visibility_tracks": visibility,
    }


def _here():
    if unreal is None:
        return os.path.dirname(os.path.abspath(__file__))
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    return os.path.join(saved, "CodexConductor", "Job168S1Ending_20261010")


def _project_root():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _json_read(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise Refusal("MISSING_JSON|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_file(asset_path):
    return os.path.join(_project_root(), "Content", *asset_path[len("/Game/"):].split("/")) + ".uasset"


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(p.get_path_name() for p in lib.get_dirty_content_packages()),
        "maps": sorted(p.get_path_name() for p in lib.get_dirty_map_packages()),
    }


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _rate(value):
    return float(value.numerator) / float(value.denominator)


def _track_property(track):
    try:
        return str(track.get_property_name()), str(track.get_property_path())
    except Exception:
        return "", ""


def _channel_name(channel):
    try:
        name = str(channel.get_editor_property("channel_name"))
    except Exception:
        name = str(channel.get_name())
    return name.split("_", 1)[0]


def _key_rows(section):
    rows = {}
    for channel in section.get_all_channels():
        name = _channel_name(channel)
        keys = []
        for key in channel.get_keys():
            time = key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
            keys.append([int(time.frame_number.value), round(float(key.get_value()), 6)])
        rows[name] = keys
    return rows


def _section_range(section, seq):
    return [int(section.get_start_frame()) if section.has_start_frame() else int(seq.get_playback_start()),
            int(section.get_end_frame()) if section.has_end_frame() else int(seq.get_playback_end())]


def _bound_objects(seq, binding, world):
    try:
        return list(seq.locate_bound_objects(binding, world))
    except Exception:
        return []


def _binding_for_object(seq, obj, world):
    path = obj.get_path_name()
    hits = [b for b in seq.get_bindings()
            if path in [x.get_path_name() for x in _bound_objects(seq, b, world)]]
    if len(hits) > 1:
        raise Refusal("BINDING_AMBIGUOUS|%s|%d" % (path, len(hits)))
    return hits[0] if hits else None


def _owned_state(seq, world, labels):
    rows = []
    for binding in seq.get_bindings():
        name = str(binding.get_display_name())
        objects = _bound_objects(seq, binding, world)
        object_labels = [str(o.get_actor_label()) for o in objects if hasattr(o, "get_actor_label")]
        if name not in labels and not set(object_labels).intersection(labels):
            continue
        tracks = []
        for track in binding.get_tracks():
            display = str(track.get_display_name())
            cls = track.get_class().get_name()
            prop, path = _track_property(track)
            if display != TRACK_NAME and cls != "MovieSceneVisibilityTrack":
                continue
            sections = [{"range": _section_range(s, seq), "active": bool(s.is_active()),
                         "blend": str(s.get_blend_type()), "keys": _key_rows(s)}
                        for s in track.get_sections()]
            tracks.append({"class": cls, "display": display, "property": prop, "path": path,
                           "sections": sections})
        if tracks:
            rows.append({"guid": _guid(binding.get_id()), "name": name,
                         "objects": sorted(o.get_path_name() for o in objects), "tracks": tracks})
    return sorted(rows, key=lambda row: row["guid"])


def _root_timeline(seq):
    shots, cuts = [], []
    for track in seq.get_tracks():
        cls = track.get_class().get_name()
        for index, section in enumerate(track.get_sections()):
            row = {"track_class": cls, "section_index": index, "range": _section_range(section, seq)}
            if hasattr(section, "get_sequence"):
                child = section.get_sequence()
                row["sequence"] = "" if child is None else child.get_path_name().split(".", 1)[0]
            if "CameraCut" in cls:
                try:
                    row["camera_guid"] = _guid(section.get_camera_binding_id().get_editor_property("guid"))
                except Exception:
                    row["camera_guid"] = ""
                cuts.append(row)
            if row.get("sequence") == KLARA:
                shots.append(row)
    return {"shots": shots, "camera_cuts": cuts,
            "playback": [int(seq.get_playback_start()), int(seq.get_playback_end())]}


def _late_sequence_inventory(seq, cutoff):
    """Exhaustive direct-section/key/marker inventory at or beyond cutoff."""
    sections, keys = [], []
    owners = [("<root>", "", list(seq.get_tracks()))]
    owners.extend((str(binding.get_display_name()), _guid(binding.get_id()), list(binding.get_tracks()))
                  for binding in seq.get_bindings())
    for owner, guid, tracks in owners:
        for track_index, track in enumerate(tracks):
            cls = track.get_class().get_name()
            for section_index, section in enumerate(track.get_sections()):
                span = _section_range(section, seq)
                if span[0] >= cutoff or span[1] > cutoff:
                    sections.append({"owner": owner, "binding_guid": guid, "track_index": track_index,
                                     "section_index": section_index, "track_class": cls,
                                     "property": _track_property(track), "range": span,
                                     "relation": "starts_after" if span[0] >= cutoff else "crosses"})
                for channel_index, channel in enumerate(section.get_all_channels()):
                    for key_index, key in enumerate(channel.get_keys()):
                        time = key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
                        frame = int(time.frame_number.value)
                        if frame >= cutoff:
                            try:
                                value = key.get_value()
                                value = float(value) if isinstance(value, (int, float)) else str(value)
                            except Exception as exc:
                                value = "<unreadable:%s>" % exc
                            keys.append({"owner": owner, "binding_guid": guid, "track_index": track_index,
                                         "section_index": section_index, "channel_index": channel_index,
                                         "channel": _channel_name(channel), "key_index": key_index,
                                         "frame": frame, "value": value})
    markers = []
    for marker in seq.get_marked_frames_from_sequence(unreal.MovieSceneTimeUnit.DISPLAY_RATE):
        frame = int(marker.frame_number.value)
        if frame >= cutoff:
            markers.append({"frame": frame, "label": str(marker.label)})
    return {"cutoff_frame": cutoff, "sections": sections, "keys": keys, "markers": markers,
            "counts": {"sections": len(sections), "keys": len(keys), "markers": len(markers)}}


def _frame_value(value):
    return int(value.value) if hasattr(value, "value") else int(value)


def _shot_source_cutoff(seq, klara, shot_row, scene_cutoff):
    matches = []
    for track in seq.get_tracks():
        for section in track.get_sections():
            if not hasattr(section, "get_sequence"):
                continue
            child = section.get_sequence()
            if child is not None and child.get_path_name().split(".", 1)[0] == KLARA:
                matches.append(section)
    if len(matches) != 1:
        raise Refusal("KLARA_SHOT_MAPPING_COUNT|%d" % len(matches))
    params = matches[0].get_editor_property("parameters")
    offset = _frame_value(params.get_editor_property("start_frame_offset"))
    shot_start = int(shot_row["range"][0])
    source_frame = scene_to_source_frame(scene_cutoff, shot_start, offset,
                                         _rate(klara.get_tick_resolution()),
                                         _rate(klara.get_display_rate()), _rate(seq.get_display_rate()))
    # Keys are integral display frames; the first excluded frame is the ceiling.
    import math
    return {"scene_cutoff": scene_cutoff, "shot_start": shot_start,
            "start_offset_ticks": offset, "source_frame_exact": source_frame,
            "source_cutoff_frame": int(math.ceil(source_frame))}


def _material_audit(actors):
    rows = []
    for actor in actors:
        comp = actor.get_component_by_class(unreal.SkeletalMeshComponent)
        if comp is None:
            raise Refusal("SKELETAL_COMPONENT_MISSING|%s" % actor.get_actor_label())
        slots = []
        for index in range(int(comp.get_num_materials())):
            material = comp.get_material(index)
            try:
                scalars = sorted(str(x) for x in unreal.MaterialEditingLibrary.get_scalar_parameter_names(material))
            except Exception as exc:
                scalars = ["<unreadable:%s>" % exc]
            slots.append({"index": index, "material": None if material is None else material.get_path_name(),
                          "scalar_parameters": scalars})
        rows.append({"actor": str(actor.get_actor_label()), "component": comp.get_path_name(), "slots": slots})
    return {"strategy": "ADDITIVE_SCALE_AND_BHIDDEN_FALLBACK", "actors": rows,
            "reason": "No persistent wrapper-owned MID exists and no shared scalar is proven wired to opacity."}


def _klara_author_rows(seq):
    rows = []
    wanted = {"Pig_anim_RM", "medhue_raccoon", "RedDeer_Calf_anim_IP"}
    for binding in seq.get_bindings():
        owner = str(binding.get_display_name())
        if owner not in wanted:
            continue
        for track in binding.get_tracks():
            cls = track.get_class().get_name()
            if cls not in ("MovieScene3DTransformTrack", "MovieSceneVisibilityTrack"):
                continue
            sections = []
            late_additive = False
            for section in track.get_sections():
                section_range = _section_range(section, seq)
                blend = str(section.get_blend_type())
                keys = _key_rows(section)
                if section_range[0] >= 3300 and "ADDITIVE" in blend.upper():
                    late_additive = True
                sections.append({"range": section_range, "blend": blend, "keys": keys})
            rows.append({"owner": owner, "class": cls, "property": _track_property(track),
                         "late_additive": late_additive, "sections": sections})
    return rows


def _actors_by_label(world, labels):
    all_actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    result = []
    for label in labels:
        hits = [a for a in all_actors if str(a.get_actor_label()) == label]
        if len(hits) != 1:
            raise Refusal("ANIMAL_ACTOR_COUNT|%s|%d" % (label, len(hits)))
        result.append(hits[0])
    return result


def _preflight(args):
    errors = validate_args(args)
    if errors:
        raise Refusal("ARGS|%s" % errors)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise Refusal("PIE_RUNNING")
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise Refusal("WORLD_MISMATCH|%s" % (None if world is None else world.get_path_name()))
    if _census() != {"content": [], "maps": []}:
        raise Refusal("DIRTY_AT_START|%s" % _census())
    seq, klara = unreal.load_asset(SCENE), unreal.load_asset(KLARA)
    if seq is None or klara is None:
        raise Refusal("SEQUENCE_LOAD_FAILED")
    if abs(_rate(seq.get_display_rate()) - 25.0) > 1.0e-6:
        raise Refusal("SCENE_RATE|%s" % _rate(seq.get_display_rate()))
    return world, seq, klara


def _report(args):
    world, seq, klara = _preflight(args)
    labels = list(args["animal_labels"])
    actors = _actors_by_label(world, labels)
    klara_file = _asset_file(KLARA)
    plan = timing_plan(args)
    timeline = _root_timeline(seq)
    if len(timeline["shots"]) != 1:
        raise Refusal("KLARA_SHOT_COUNT|%d" % len(timeline["shots"]))
    cuts = sorted(timeline["camera_cuts"], key=lambda row: row["range"])
    if len(cuts) < 2:
        raise Refusal("CAMERA_CUT_COUNT|%d" % len(cuts))
    binding_names = {_guid(b.get_id()): str(b.get_display_name()) for b in seq.get_bindings()}
    exit_rows = [row for row in cuts if "Exit Handoff Camera" in binding_names.get(row["camera_guid"], "")]
    if len(exit_rows) != 1:
        raise Refusal("EXIT_HANDOFF_CUT_COUNT|%d" % len(exit_rows))
    before = {"owned": _owned_state(seq, world, labels), "timeline": timeline}
    author = author_verdict(_klara_author_rows(klara))
    if author["authority"] != "KLARA_COPY_TRANSFORM":
        raise Refusal("ANIMAL_DISAPPEARANCE_AUTHORITY|%s" % author)
    report = {
        "schema": 1, "tool": TOOL, "version": VERSION, "run": args["run_id"],
        "mode": args["mode"], "decided_by": args["decided_by"], "plan": plan,
        "animal_author": author, "material_audit": _material_audit(actors),
        "before": before, "before_digest": stable_digest(before),
        "klara_guard": {"asset": KLARA, "file": klara_file, "sha256": _sha(klara_file)},
        "exit_cut_before": exit_rows[0], "census": _census(), "apply_ready": not before["owned"],
        "claims": {
            "measured_when_run": "live sequence inventory and saved read-back",
            "inferred": "scale reduction reads as a visual fade; PIE stills remain required",
            "declaration_proven": "only the PussStage-owned S1 wrapper is save-eligible",
        },
    }
    source_cutoff = _shot_source_cutoff(seq, klara, timeline["shots"][0], plan["exit_handoff"][0])
    report["klara_content_past_new_wrapper_end"] = dict(
        source_cutoff,
        inventory=_late_sequence_inventory(klara, source_cutoff["source_cutoff_frame"]))
    if before["owned"]:
        raise Refusal("OWNED_TRACKS_ALREADY_EXIST|use REVERT or inspect drift")
    return world, seq, klara, actors, report


def _backup(run, paths, suffix=""):
    folder = os.path.join(_project_root(), "Backups", "PreJob168S1%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    rows = []
    for asset in paths:
        source = _asset_file(asset)
        target = os.path.join(folder, os.path.basename(source))
        shutil.copy2(source, target)
        if _sha(source) != _sha(target):
            raise Refusal("BACKUP_VERIFY|%s" % asset)
        rows.append({"asset": asset, "source": source, "backup": target, "sha256": _sha(target)})
    return {"root": folder, "files": rows}


def _add_animal_tracks(seq, actor, world, plan):
    binding = _binding_for_object(seq, actor, world)
    created = False
    if binding is None:
        before = {_guid(b.get_id()) for b in seq.get_bindings()}
        binding = seq.add_possessable(actor)
        created = _guid(binding.get_id()) not in before
        if created:
            binding.set_display_name("JOB168 " + str(actor.get_actor_label()))
    conflicts = [t for t in binding.get_tracks()
                 if t.get_class().get_name() in ("MovieScene3DTransformTrack", "MovieSceneVisibilityTrack")]
    if conflicts:
        raise Refusal("WRAPPER_ANIMAL_TRACK_CONFLICT|%s|%s" %
                      (actor.get_actor_label(), [t.get_class().get_name() for t in conflicts]))
    transform = binding.add_track(unreal.MovieScene3DTransformTrack)
    transform.set_display_name(TRACK_NAME)
    section = transform.add_section()
    section.set_blend_type(unreal.MovieSceneBlendType.ADDITIVE)
    section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    section.set_range(plan["animal_fade"][0], int(seq.get_playback_end()))
    channels = {_channel_name(c): c for c in section.get_all_channels()}
    if not set(SCALE_CHANNELS).issubset(channels):
        raise Refusal("TRANSFORM_SCALE_CHANNELS|%s" % sorted(channels))
    linear = unreal.MovieSceneKeyInterpolation.LINEAR
    for name in SCALE_CHANNELS:
        channels[name].set_default(0.0)
        channels[name].add_key(unreal.FrameNumber(plan["animal_fade"][0]), 0.0,
                               time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE, interpolation=linear)
        channels[name].add_key(unreal.FrameNumber(plan["animal_fade"][1]), -1.0,
                               time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE, interpolation=linear)
    for name, channel in channels.items():
        if name not in SCALE_CHANNELS:
            channel.set_default(0.0)
    visibility = binding.add_track(unreal.MovieSceneVisibilityTrack)
    visibility.set_property_name_and_path("bHidden", "bHidden")
    vis_section = visibility.add_section()
    vis_section.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
    vis_section.set_range(int(seq.get_playback_start()), int(seq.get_playback_end()))
    vis_channels = list(vis_section.get_all_channels())
    if len(vis_channels) != 1:
        raise Refusal("VISIBILITY_CHANNEL_COUNT|%s|%d" % (actor.get_actor_label(), len(vis_channels)))
    vis_channels[0].add_key(unreal.FrameNumber(int(seq.get_playback_start())), True,
                            time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    vis_channels[0].add_key(unreal.FrameNumber(plan["animal_fade"][1]), False,
                            time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    if _track_property(visibility) != ("bHidden", "bHidden"):
        raise Refusal("VISIBILITY_BINDING_READBACK|%s|%s" %
                      (actor.get_actor_label(), _track_property(visibility)))
    return {"actor": str(actor.get_actor_label()), "binding": _guid(binding.get_id()),
            "binding_created": created}


def _retime_handoff(seq, plan):
    shot_hits = []
    cut_track = None
    for track in seq.get_tracks():
        for section in track.get_sections():
            if hasattr(section, "get_sequence"):
                child = section.get_sequence()
                path = "" if child is None else child.get_path_name().split(".", 1)[0]
                if path == KLARA:
                    shot_hits.append(section)
        if "CameraCut" in track.get_class().get_name():
            if cut_track is not None:
                raise Refusal("MULTIPLE_CAMERA_CUT_TRACKS")
            cut_track = track
    if len(shot_hits) != 1 or cut_track is None:
        raise Refusal("HANDOFF_DISCOVERY|shot=%d|cut=%s" % (len(shot_hits), cut_track is not None))
    exit_start, new_end = plan["exit_handoff"]
    shot_hits[0].set_end_frame(exit_start)
    names = {_guid(b.get_id()): str(b.get_display_name()) for b in seq.get_bindings()}
    exit_hits, prior_hits = [], []
    for section in cut_track.get_sections():
        guid = _guid(section.get_camera_binding_id().get_editor_property("guid"))
        if "Exit Handoff Camera" in names.get(guid, ""):
            exit_hits.append(section)
        elif _section_range(section, seq)[0] < exit_start < _section_range(section, seq)[1]:
            prior_hits.append(section)
    if len(exit_hits) != 1 or len(prior_hits) != 1:
        raise Refusal("HANDOFF_CUT_DISCOVERY|exit=%d|prior=%d" % (len(exit_hits), len(prior_hits)))
    prior_hits[0].set_end_frame(exit_start)
    exit_hits[0].set_range(exit_start, int(seq.get_playback_end()))
    return {"shot_range": _section_range(shot_hits[0], seq),
            "prior_cut_range": _section_range(prior_hits[0], seq),
            "exit_cut_range": _section_range(exit_hits[0], seq), "planned_end": new_end}


def _remove_owned(seq, world, record):
    remove_bindings = []
    wanted = {row["binding"]: row for row in record["operations"]}
    for binding in seq.get_bindings():
        guid = _guid(binding.get_id())
        if guid not in wanted:
            continue
        for track in list(binding.get_tracks()):
            if track.get_class().get_name() == "MovieSceneVisibilityTrack" or str(track.get_display_name()) == TRACK_NAME:
                binding.remove_track(track)
        if wanted[guid]["binding_created"] and not list(binding.get_tracks()):
            remove_bindings.append(binding)
    for binding in remove_bindings:
        seq.remove_possessable(binding.get_id())


def run_dry(args):
    _world, _seq, _klara, _actors, report = _report(args)
    path = os.path.join(_here(), "job168_animals_dry_%s.json" % args["run_id"])
    _json_write(path, report)
    _json_write(os.path.join(_here(), PLAN_NAME), {"run": args["run_id"], "digest": review_digest(report),
                                                   "report": path})
    if _census() != {"content": [], "maps": []}:
        raise Refusal("DRY_DIRTIED_EDITOR")
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=1|strategy=%s|fade=%s|lights=%s|handoff=%s|end=%d|report=%s" %
               (TOOL, args["run_id"], args["animal_fade_strategy"], report["plan"]["animal_fade"],
                report["plan"]["lights_out"], report["plan"]["exit_handoff"],
                report["plan"]["new_end"], path))
    return report


def run_apply(args):
    world, seq, _klara, actors, report = _report(args)
    gate = _json_read(os.path.join(_here(), PLAN_NAME))
    if gate.get("digest") != review_digest(report):
        raise Refusal("CHANGED_SINCE_DRY")
    run = args["run_id"]
    backup = _backup(run, (SCENE,))
    transaction = os.path.join(_here(), "job168_animals_transaction_%s.json" % run)
    record = {"schema": 1, "tool": TOOL, "run": run, "applied": False,
              "written_before_mutation": True, "backup": backup, "report": report,
              "before": report["before"], "operations": []}
    _json_write(transaction, record, exclusive=True)
    seq.modify()
    for actor in actors:
        op = _add_animal_tracks(seq, actor, world, report["plan"])
        record["operations"].append(op)
        _json_write(transaction, record)
    record["handoff_after"] = _retime_handoff(seq, report["plan"])
    after = {"owned": _owned_state(seq, world, args["animal_labels"]), "timeline": _root_timeline(seq)}
    if len(after["owned"]) != 3:
        raise Refusal("OWNED_READBACK_COUNT|%d|NOTHING SAVED" % len(after["owned"]))
    for row in after["owned"]:
        vis = [t for t in row["tracks"] if t["class"] == "MovieSceneVisibilityTrack"]
        scale = [t for t in row["tracks"] if t["display"] == TRACK_NAME]
        if len(vis) != 1 or (vis[0]["property"], vis[0]["path"]) != ("bHidden", "bHidden") or len(scale) != 1:
            raise Refusal("OWNED_READBACK_SHAPE|%s|NOTHING SAVED" % row)
    record.update({"after": after, "after_digest": stable_digest(after), "applied": True})
    _json_write(transaction, record)
    if _census() != {"content": [SCENE], "maps": []}:
        raise Refusal("DIRTY_SCOPE|%s|NOTHING SAVED" % _census())
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=True):
        raise Refusal("SAVE_FAILED|%s" % SCENE)
    if _census() != {"content": [], "maps": []}:
        raise Refusal("DIRTY_AFTER_SAVE|%s" % _census())
    seq2 = unreal.load_asset(SCENE)
    saved = {"owned": _owned_state(seq2, world, args["animal_labels"]), "timeline": _root_timeline(seq2)}
    if saved != after:
        raise Refusal("SAVED_READBACK_MISMATCH|restore=%s" % backup["root"])
    if _sha(report["klara_guard"]["file"]) != report["klara_guard"]["sha256"]:
        raise Refusal("KLARA_ASSET_CHANGED|restore=%s" % backup["root"])
    record.update({"saved_readback": saved, "saved_readback_digest": stable_digest(saved),
                   "census_after": _census()})
    _json_write(os.path.join(_here(), RECORD_NAME), record, exclusive=True)
    _json_write(transaction, dict(record, transaction_complete=True))
    unreal.log("%s_APPLY_OK|run=%s|saved=%s|klara_saved=0|levels_saved=0|fade=%s|handoff=%s|backup=%s|record=%s" %
               (TOOL, run, SCENE, report["plan"]["animal_fade"], report["plan"]["exit_handoff"],
                backup["root"], os.path.join(_here(), RECORD_NAME)))
    return record


def run_revert(args):
    world, seq, _klara = _preflight(args)
    record_path = os.path.join(_here(), RECORD_NAME)
    record = _json_read(record_path)
    if not record.get("applied"):
        raise Refusal("NO_APPLIED_RECORD")
    live = {"owned": _owned_state(seq, world, args["animal_labels"]), "timeline": _root_timeline(seq)}
    if stable_digest(live) != record["saved_readback_digest"]:
        raise Refusal("APPLIED_STATE_DRIFT")
    backup = _backup(args["run_id"], (SCENE,), "Revert")
    txn_path = os.path.join(_here(), "job168_animals_revert_%s.json" % args["run_id"])
    _json_write(txn_path, {"completed": False, "backup": backup, "source_record": record_path}, exclusive=True)
    seq.modify()
    _remove_owned(seq, world, record)
    before_timeline = record["before"]["timeline"]
    # Restore the one Klara shot and every root camera cut by their stable ordered shape.
    shot_ranges = [row["range"] for row in before_timeline["shots"]]
    shot_sections = []
    cut_track = None
    for track in seq.get_tracks():
        for section in track.get_sections():
            if hasattr(section, "get_sequence"):
                child = section.get_sequence()
                if child is not None and child.get_path_name().split(".", 1)[0] == KLARA:
                    shot_sections.append(section)
        if "CameraCut" in track.get_class().get_name():
            cut_track = track
    if len(shot_sections) != len(shot_ranges) or cut_track is None:
        raise Refusal("REVERT_TIMELINE_DISCOVERY")
    for section, span in zip(shot_sections, shot_ranges):
        section.set_range(*span)
    cut_sections = list(cut_track.get_sections())
    old_cuts = before_timeline["camera_cuts"]
    if len(cut_sections) != len(old_cuts):
        raise Refusal("REVERT_CUT_COUNT")
    for section, row in zip(cut_sections, old_cuts):
        section.set_range(*row["range"])
    restored = {"owned": _owned_state(seq, world, args["animal_labels"]), "timeline": _root_timeline(seq)}
    if restored != record["before"]:
        raise Refusal("REVERT_IN_MEMORY_MISMATCH|NOTHING SAVED")
    if _census() != {"content": [SCENE], "maps": []}:
        raise Refusal("REVERT_DIRTY_SCOPE|%s" % _census())
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=True):
        raise Refusal("REVERT_SAVE_FAILED")
    saved = {"owned": _owned_state(unreal.load_asset(SCENE), world, args["animal_labels"]),
             "timeline": _root_timeline(unreal.load_asset(SCENE))}
    if saved != record["before"] or _census() != {"content": [], "maps": []}:
        raise Refusal("REVERT_SAVED_READBACK")
    archived = record_path + ".reverted-" + args["run_id"]
    os.rename(record_path, archived)
    _json_write(txn_path, {"completed": True, "backup": backup, "source_record": archived,
                           "saved_readback": saved})
    unreal.log("%s_REVERT_OK|run=%s|saved=%s|klara_saved=0|levels_saved=0|backup=%s|record=%s" %
               (TOOL, args["run_id"], SCENE, backup["root"], archived))
    return saved


def run(args):
    mode = str(args["mode"]).upper()
    return {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[mode](args)
