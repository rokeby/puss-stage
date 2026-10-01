"""Retiming for the S1/S2/S3/S6 hangars, mirroring Scene 4's ten-second rise.

Dry run is the default. HANGAR_RETIME_APPLY records and backs up all four rise
assets plus the level, edits through the asset API without opening Sequencer,
verifies keys, drives, nesting and seams, and saves only those five packages.
HANGAR_RETIME_REVERT first requires the recorded applied state and restores the
recorded keys, exposure weights, drive arrays, and any exposure binding created
by apply.

plan_scene() and the builder helpers are deliberately Unreal-free for the plain
Python harness.
"""
import copy
import datetime
import json
import math
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Plain-Python planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SCENES = (1, 2, 3, 6)
EXPECTED_W0 = -5.8739
EXPECTED_W1 = 4.1261
FPS = 30.0
BUILDER_COMMITS = {1: "d64ce61", 2: "26c12fd", 3: "d64ce61", 6: "d64ce61"}

if unreal is not None:
    HERE = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexStructure",
    )
else:
    HERE = os.path.dirname(os.path.abspath(__file__))

REKEY_RECORD = os.path.join(HERE, "s4_rekey_window_record.json")
PREDRIVE_RECORD = os.path.join(HERE, "s4_predrive_author_record.json")
ARRIVALS_RECORD = os.path.join(HERE, "arrivals_record.json")
ARRIVALS_S2_RECORD = os.path.join(HERE, "arrivals_s2_record.json")
RECORD = os.path.join(HERE, "hangar_retime_record.json")

ROLE_KEYS = {
    "root_pitch",
    "roof_pitch",
    "lattice_fly_z",
    "uplights",
    "practicals",
    "glows",
    "ppv_weight",
}
INTERPOLATION = {
    "root_pitch": "AUTO",
    "roof_pitch": "AUTO",
    "lattice_fly_z": "AUTO",
    "uplights": "LINEAR",
    "practicals": "LINEAR",
    "glows": "LINEAR",
    "ppv_weight": "AUTO",
}


def _q(time_s, fps=FPS):
    return round(round(float(time_s) * float(fps)) / float(fps), 9)


def _plain_keys(keys):
    return [[float(time_s), float(value)] for time_s, value in keys]


def _expected_light_labels(scene, prefix, count):
    if prefix == "Uplight":
        return [f"S{scene} Uplight {index}" for index in range(1, count + 1)]
    if prefix == "Practical":
        return [f"S{scene} Practical {side}{index}" for index in range(1, 8) for side in ("L", "R")]
    return [f"S{scene} Lattice Glow {rail}-{bulb}" for rail in range(1, 4) for bulb in range(1, 9)]


def builder_beats_for_scene(scene, root_keys, has_roof=True, has_exposure=True, fps=FPS):
    """Exact default K=1 beats written by d64ce61/26c12fd, at display frames."""
    scene = int(scene)
    practicals = {}
    for label in _expected_light_labels(scene, "Practical", 14):
        index = int(label.rsplit("L", 1)[-1] if " Practical L" in label else label.rsplit("R", 1)[-1])
        strike = 16.5 + (index - 1) * 0.3
        practicals[label] = [[0.0, 0.0], [_q(strike, fps), 0.0], [_q(strike + 0.2, fps), 400.0]]
    uplights = {}
    for index, label in enumerate(_expected_light_labels(scene, "Uplight", 3)):
        strike = 18.0 + index * 0.15
        uplights[label] = [[0.0, 0.0], [_q(strike, fps), 0.0], [_q(strike + 0.2, fps), 10000.0]]
    glows = {
        label: [[0.0, 0.0], [4.0, 0.0], [8.0, 20.0]]
        for label in _expected_light_labels(scene, "Glow", 24)
    }
    return {
        "builder_commit": BUILDER_COMMITS[scene],
        "fps": float(fps),
        "root_pitch": _plain_keys(root_keys),
        "roof_pitch": [[0.0, -90.0], [18.5, -90.0], [24.5, 0.0]] if has_roof else None,
        "lattice_fly_z": [[0.0, 2800.0], [24.5, 2800.0], [28.5, 1200.0]],
        "uplights": uplights,
        "practicals": practicals,
        "glows": glows,
        # These historical builders created the volume actor, but not a binding/track.
        "ppv_weight": None,
        "has_exposure": bool(has_exposure),
    }


def _keys_match(got, wanted, fps=FPS, time_tolerance=None, value_tolerance=1e-3):
    if got is None or wanted is None:
        return got is None and wanted is None
    if len(got) != len(wanted):
        return False
    tolerance = 1.0 / float(fps) + 1e-9 if time_tolerance is None else float(time_tolerance)
    return all(
        abs(float(gt) - float(wt)) <= tolerance and abs(float(gv) - float(wv)) <= value_tolerance
        for (gt, gv), (wt, wv) in zip(got, wanted)
    )


def _state_mismatches(got, wanted, fps=FPS):
    bad = []
    for role in ("root_pitch", "roof_pitch", "lattice_fly_z", "ppv_weight"):
        if not _keys_match(got.get(role), wanted.get(role), fps):
            bad.append(role)
    for role in ("uplights", "practicals", "glows"):
        got_group, wanted_group = got.get(role, {}), wanted.get(role, {})
        for label in sorted(set(got_group) | set(wanted_group)):
            if not _keys_match(got_group.get(label), wanted_group.get(label), fps):
                bad.append(f"{role}:{label}")
    return bad


def plan_scene(before_by_role, W0, W1, builder_beats):
    """Validate a historical builder state and return the complete target state."""
    W0, W1 = float(W0), float(W1)
    if W0 >= 0.0:
        raise ValueError(f"W0 must be before the Scene cut, found {W0}")
    if W1 <= 0.0 or W1 <= W0:
        raise ValueError(f"invalid W1={W1} for W0={W0}")
    if not isinstance(before_by_role, dict):
        raise ValueError("before_by_role must be an object")
    unknown = sorted(set(before_by_role) - ROLE_KEYS)
    missing = sorted(ROLE_KEYS - set(before_by_role))
    if unknown or missing:
        raise ValueError(f"role set mismatch: unknown={unknown}, missing={missing}")
    expected = {key: copy.deepcopy(builder_beats[key]) for key in ROLE_KEYS}
    fps = float(builder_beats.get("fps", FPS))
    bad = _state_mismatches(before_by_role, expected, fps)
    if bad:
        raise ValueError("before-state does not match its historical builder/arrival state: " + ", ".join(bad))

    shift = W1 - 16.0
    after = copy.deepcopy(before_by_role)
    after["root_pitch"] = [[W0, -90.0], [W1, 0.0]]
    for role in ("roof_pitch", "lattice_fly_z"):
        if after[role] is not None:
            after[role] = [
                [float(time_s) if index == 0 else round(float(time_s) + shift, 6), float(value)]
                for index, (time_s, value) in enumerate(after[role])
            ]
    after["uplights"] = {
        label: [
            [float(time_s) if index == 0 else round(float(time_s) + shift, 6), float(value)]
            for index, (time_s, value) in enumerate(keys)
        ]
        for label, keys in before_by_role["uplights"].items()
    }
    after["practicals"] = {
        label: [[W0, 0.0], [W1, max(float(value) for _time_s, value in keys)]]
        for label, keys in before_by_role["practicals"].items()
    }
    after["glows"] = {
        label: [[W0, 0.0], [W1, max(float(value) for _time_s, value in keys)]]
        for label, keys in before_by_role["glows"].items()
    }
    after["ppv_weight"] = [[W0, 0.0], [W1, 1.0]] if builder_beats.get("has_exposure") else None
    return after


def _canonical_label(label):
    return re.sub(r"^S\d+ ", "S# ", str(label))


def canonical_state(state):
    out = copy.deepcopy(state)
    for role in ("uplights", "practicals", "glows"):
        out[role] = {_canonical_label(label): keys for label, keys in state[role].items()}
    return out


def target_state_from_records(scene, rekey, predrive, has_roof, has_exposure):
    """Combine the two S4 applied records, replacing only the scene-label prefix."""
    replace = lambda label: re.sub(r"^S4 ", f"S{scene} ", str(label))
    return {
        "root_pitch": copy.deepcopy(rekey["after"]["root_pitch"]),
        "roof_pitch": copy.deepcopy(rekey["after"]["roof_pitch"]) if has_roof else None,
        "lattice_fly_z": copy.deepcopy(rekey["after"]["lattice_fly_z"]),
        "uplights": {replace(label): copy.deepcopy(keys) for label, keys in rekey["after"]["uplights"].items()},
        "practicals": {
            replace(label): copy.deepcopy(keys)
            for label, keys in predrive["after_keys"]["intensity"].items()
            if label.startswith("S4 Practical")
        },
        "glows": {
            replace(label): copy.deepcopy(keys)
            for label, keys in predrive["after_keys"]["intensity"].items()
            if label.startswith("S4 Lattice Glow")
        },
        "ppv_weight": copy.deepcopy(predrive["after_keys"]["ppv_weight"]) if has_exposure else None,
    }


if unreal is not None:
    def fail(run, message):
        unreal.log_error(f"HANGAR_RETIME_STOPPED|run={run}|{message}")
        raise RuntimeError(message)


    def package_census():
        return {
            "dirty_maps": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "dirty_content": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        }


    def all_level_actors(world):
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


    def one_actor(actors, label, run, required=True):
        found = [actor for actor in actors if str(actor.get_actor_label()) == label]
        if len(found) != (1 if required else 0) and not (not required and len(found) == 1):
            fail(run, f"expected {'zero or one' if not required else 'one'} level actor {label!r}, found {len(found)}")
        return found[0] if found else None


    def guid_text(guid):
        return str(unreal.GuidLibrary.conv_guid_to_string(guid))


    def object_path(value):
        return "None" if value is None else str(value.get_path_name()) if hasattr(value, "get_path_name") else str(value)


    def keys_of(channel, fps):
        return [[key.get_time().frame_number.value / fps, float(key.get_value())] for key in channel.get_keys()]


    def interpolation_matches(channel, expected):
        wanted = {"LINEAR": "RCIM_LINEAR", "AUTO": "RCIM_CUBIC"}[expected]
        keys = list(channel.get_keys())
        return bool(keys) and all(key.get_interpolation_mode().name == wanted for key in keys)


    def set_keys(channel, keys, fps, interpolation):
        for key in list(channel.get_keys()):
            channel.remove_key(key)
        mode = getattr(unreal.MovieSceneKeyInterpolation, interpolation)
        for time_s, value in keys:
            channel.add_key(
                unreal.FrameNumber(int(round(float(time_s) * fps))),
                float(value),
                time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                interpolation=mode,
            )


    def _one_track_channel(binding, track_class, property_name, channel_index, run):
        found = []
        for track in binding.get_tracks():
            if isinstance(track, track_class) and (property_name is None or str(track.get_property_name()) == property_name):
                for section in track.get_sections():
                    channels = list(section.get_all_channels())
                    if len(channels) > channel_index:
                        found.append(channels[channel_index])
        if len(found) != 1:
            fail(run, f"expected one {property_name or track_class.__name__} channel on {binding.get_display_name()}, found {len(found)}")
        return found[0]


    def discover_sequence(sequence, scene, run, allow_missing_exposure=True):
        labels = {
            "root": f"S{scene} Hangar Root",
            "roof": f"S{scene} Hangar Roof Hinge",
            "lattice": f"S{scene} Hangar Lattice Fly",
            "exposure": f"S{scene} Hangar Pinned Exposure",
        }
        direct = {}
        child = {"uplights": {}, "practicals": {}, "glows": {}}
        unknown = []
        bindings = list(sequence.get_bindings())
        for binding in bindings:
            label = str(binding.get_display_name())
            parent = binding.get_parent()
            parent_label = str(parent.get_display_name()) if parent and parent.is_valid() else None
            if label in labels.values():
                direct[label] = binding
                continue
            if label.startswith((f"S{scene} Uplight ", f"S{scene} Practical ", f"S{scene} Lattice Glow ")):
                # Auto-created actor parent binding; its child owns the property track.
                direct[label] = binding
                continue
            if parent_label and parent_label.startswith(f"S{scene} Uplight "):
                child["uplights"][parent_label] = (binding, _one_track_channel(binding, unreal.MovieSceneFloatTrack, "Intensity", 0, run))
                continue
            if parent_label and parent_label.startswith(f"S{scene} Practical "):
                child["practicals"][parent_label] = (binding, _one_track_channel(binding, unreal.MovieSceneFloatTrack, "Intensity", 0, run))
                continue
            if parent_label and parent_label.startswith(f"S{scene} Lattice Glow "):
                child["glows"][parent_label] = (binding, _one_track_channel(binding, unreal.MovieSceneFloatTrack, "Intensity", 0, run))
                continue
            unknown.append({"label": label, "parent": parent_label, "guid": guid_text(binding.get_id())})
        required_direct = [labels["root"], labels["lattice"]]
        if scene != 6:
            required_direct.append(labels["roof"])
        missing = [label for label in required_direct if label not in direct]
        if missing:
            fail(run, f"S{scene}: required bindings absent: {missing}")
        channels = {
            "root_pitch": _one_track_channel(direct[labels["root"]], unreal.MovieScene3DTransformTrack, None, 4, run),
            "roof_pitch": None if scene == 6 else _one_track_channel(direct[labels["roof"]], unreal.MovieScene3DTransformTrack, None, 4, run),
            "lattice_fly_z": _one_track_channel(direct[labels["lattice"]], unreal.MovieScene3DTransformTrack, None, 2, run),
            "uplights": child["uplights"],
            "practicals": child["practicals"],
            "glows": child["glows"],
            "ppv_weight": None,
        }
        exposure_binding = direct.get(labels["exposure"])
        if exposure_binding is not None:
            channels["ppv_weight"] = _one_track_channel(exposure_binding, unreal.MovieSceneFloatTrack, "BlendWeight", 0, run)
        elif not allow_missing_exposure:
            fail(run, f"S{scene}: exposure binding absent")
        return {"channels": channels, "unknown": unknown, "exposure_binding": exposure_binding, "bindings": bindings}


    def capture_state(discovery, fps):
        channels = discovery["channels"]
        return {
            "root_pitch": keys_of(channels["root_pitch"], fps),
            "roof_pitch": None if channels["roof_pitch"] is None else keys_of(channels["roof_pitch"], fps),
            "lattice_fly_z": keys_of(channels["lattice_fly_z"], fps),
            "uplights": {label: keys_of(row[1], fps) for label, row in sorted(channels["uplights"].items())},
            "practicals": {label: keys_of(row[1], fps) for label, row in sorted(channels["practicals"].items())},
            "glows": {label: keys_of(row[1], fps) for label, row in sorted(channels["glows"].items())},
            "ppv_weight": None if channels["ppv_weight"] is None else keys_of(channels["ppv_weight"], fps),
        }


    def interpolation_mismatches(discovery):
        bad = []
        channels = discovery["channels"]
        for role in ("root_pitch", "roof_pitch", "lattice_fly_z", "ppv_weight"):
            channel = channels[role]
            if channel is not None and not interpolation_matches(channel, INTERPOLATION[role]):
                bad.append(role)
        for role in ("uplights", "practicals", "glows"):
            for label, (_binding, channel) in channels[role].items():
                if not interpolation_matches(channel, INTERPOLATION[role]):
                    bad.append(f"{role}:{label}")
        return bad


    def apply_state(discovery, state, fps):
        channels = discovery["channels"]
        for role in ("root_pitch", "roof_pitch", "lattice_fly_z", "ppv_weight"):
            if channels[role] is not None and state[role] is not None:
                set_keys(channels[role], state[role], fps, INTERPOLATION[role])
        for role in ("uplights", "practicals", "glows"):
            for label, keys in state[role].items():
                set_keys(channels[role][label][1], keys, fps, INTERPOLATION[role])


    def section_ranges(sequence):
        rows = []
        for binding in sequence.get_bindings():
            for track_index, track in enumerate(binding.get_tracks()):
                for section_index, section in enumerate(track.get_sections()):
                    rows.append({
                        "binding": guid_text(binding.get_id()),
                        "track_index": track_index,
                        "track_class": track.get_class().get_name(),
                        "section_index": section_index,
                        "start_s": float(section.get_start_frame_seconds()) if section.has_start_frame() else None,
                        "end_s": float(section.get_end_frame_seconds()) if section.has_end_frame() else None,
                    })
        return rows


    def section_ranges_match(current, original, exact=False):
        def indexed(rows):
            return {
                (row["binding"], row["track_index"], row["track_class"], row["section_index"]):
                    (row["start_s"], row["end_s"])
                for row in rows
            }
        got, wanted = indexed(current), indexed(original)
        if exact and set(got) != set(wanted):
            return False
        return all(key in got and got[key] == value for key, value in wanted.items())


    def _first_editor_property(obj, candidates, run, semantic):
        for name in candidates:
            try:
                obj.get_editor_property(name)
                return name
            except Exception:
                pass
        fail(run, f"could not discover {semantic}")


    def discover_drive_api(arrival, run):
        probe = unreal.InfinityArrivalFloatDrive()
        return {
            "target": _first_editor_property(probe, ("target",), run, "float-drive Target"),
            "binding_guid": _first_editor_property(probe, ("binding_guid", "bindingguid"), run, "float-drive BindingGuid"),
            "property_name": _first_editor_property(probe, ("property_name", "propertyname"), run, "float-drive PropertyName"),
            "arrival_property": _first_editor_property(arrival, ("pre_scene_float_drives", "prescene_float_drives"), run, "Arrival PreSceneFloatDrives"),
        }


    def plain_drive(drive, api):
        return {
            "target": object_path(drive.get_editor_property(api["target"])),
            "binding_guid": guid_text(drive.get_editor_property(api["binding_guid"])),
            "property_name": str(drive.get_editor_property(api["property_name"])),
        }


    def capture_drives(arrival, api):
        entries = [plain_drive(drive, api) for drive in arrival.get_editor_property(api["arrival_property"])]
        return {"count": len(entries), "entries": entries}


    def make_drive(target, binding_guid, property_name, api):
        drive = unreal.InfinityArrivalFloatDrive()
        drive.set_editor_property(api["target"], target)
        drive.set_editor_property(api["binding_guid"], binding_guid)
        drive.set_editor_property(api["property_name"], property_name)
        return drive


    def one_light_component(actor, label, run):
        found = list(actor.get_components_by_class(unreal.LightComponent))
        if len(found) != 1:
            fail(run, f"expected one LightComponent on {label}, found {len(found)}")
        return found[0]


    def build_drives(scene, actors, discovery, exposure_actor, api, run):
        rows = []
        for role in ("practicals", "glows"):
            for label, (binding, _channel) in sorted(discovery["channels"][role].items()):
                actor = one_actor(actors, label, run)
                component = one_light_component(actor, label, run)
                rows.append({
                    "label": label,
                    "target_object": component,
                    "target": object_path(component),
                    "binding_guid_object": binding.get_id(),
                    "binding_guid": guid_text(binding.get_id()),
                    "property_name": "Intensity",
                })
        if exposure_actor is not None:
            binding = discovery["exposure_binding"]
            if binding is None:
                fail(run, f"S{scene}: exposure binding absent while building drives")
            rows.append({
                "label": f"S{scene} Hangar Pinned Exposure",
                "target_object": exposure_actor,
                "target": object_path(exposure_actor),
                "binding_guid_object": binding.get_id(),
                "binding_guid": guid_text(binding.get_id()),
                "property_name": "BlendWeight",
            })
        targets = [row["target"] for row in rows]
        guids = [row["binding_guid"] for row in rows]
        if len(set(targets)) != len(rows) or len(set(guids)) != len(rows):
            fail(run, f"S{scene}: drive matching is not one-to-one")
        structs = [make_drive(row["target_object"], row["binding_guid_object"], row["property_name"], api) for row in rows]
        plain = {"count": len(rows), "entries": [{k: row[k] for k in ("target", "binding_guid", "property_name")} for row in rows]}
        return rows, structs, plain


    def restore_drive_structs(recorded, actors, sequence, api, run):
        objects = {}
        for actor in actors:
            objects[object_path(actor)] = actor
            for component in actor.get_components_by_class(unreal.ActorComponent):
                objects[object_path(component)] = component
        guids = {guid_text(binding.get_id()): binding.get_id() for binding in sequence.get_bindings()}
        structs = []
        for index, row in enumerate(recorded["entries"]):
            target = None if row["target"] == "None" else objects.get(row["target"])
            guid = guids.get(row["binding_guid"])
            if (target is None and row["target"] != "None") or guid is None:
                fail(run, f"cannot restore prior drive {index}: {row}")
            structs.append(make_drive(target, guid, row["property_name"], api))
        if len(structs) != int(recorded["count"]):
            fail(run, "recorded prior drive count does not match its entries")
        return structs


    def add_exposure_channel(sequence, exposure_actor, playback, run):
        binding = sequence.add_possessable(exposure_actor)
        if binding is None:
            fail(run, f"could not add exposure possessable for {exposure_actor.get_actor_label()}")
        track = binding.add_track(unreal.MovieSceneFloatTrack)
        track.set_property_name_and_path("BlendWeight", "BlendWeight")
        section = track.add_section()
        section.set_range_seconds(float(playback[0]), float(playback[1]))
        channels = list(section.get_all_channels())
        if len(channels) != 1:
            fail(run, f"new exposure track has {len(channels)} channels")
        return binding, channels[0]


    def remove_binding(sequence, binding, run):
        extensions = getattr(unreal, "MovieSceneBindingExtensions", None)
        if extensions is None or not hasattr(extensions, "remove"):
            fail(run, "MovieSceneBindingExtensions.remove is unavailable")
        extensions.remove(binding)


    def read_json(path, run):
        if not os.path.exists(path):
            fail(run, f"required record absent: {path}")
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)


    def arrival_root_keys(run):
        rows = read_json(ARRIVALS_RECORD, run).get("scenes", []) + read_json(ARRIVALS_S2_RECORD, run).get("scenes", [])
        by_scene = {int(row["scene"]): row["keys_new"] for row in rows}
        missing = [scene for scene in SCENES if scene not in by_scene]
        if missing:
            fail(run, f"arrival records are missing scenes {missing}")
        return by_scene


    def verify_window_records(rekey, predrive, run):
        values = (float(rekey.get("W0")), float(rekey.get("W1")))
        if abs(values[0] - EXPECTED_W0) > 1e-3 or abs(values[1] - EXPECTED_W1) > 1e-3:
            fail(run, f"S4 rekey record window drifted: {values}")
        if abs(float(predrive.get("W0")) - values[0]) > 1e-6 or abs(float(predrive.get("W1")) - values[1]) > 1e-6:
            fail(run, "S4 rekey and predrive records disagree on W0/W1")
        return values


    def assert_write_guards(editor, world, run, applying):
        census = package_census()
        if census["dirty_maps"] or census["dirty_content"]:
            fail(run, f"packages already dirty: {census}")
        if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
            fail(run, "Sequencer is open")
        temps = sorted(
            str(actor.get_actor_label())
            for actor in all_level_actors(world)
            if str(actor.get_actor_label()).startswith(("ZZ_", "TEMP_"))
            or str(actor.get_name()).startswith(("ZZ_", "TEMP_"))
        )
        if temps:
            fail(run, f"temporary actors present: {temps}")
        if applying and os.path.exists(RECORD):
            fail(run, "record already exists; revert first")
        if not applying and not os.path.exists(RECORD):
            fail(run, "revert record is absent")


    def nest_rows(scene_sequence, rise_path):
        rows = []
        for track in scene_sequence.get_tracks():
            if not isinstance(track, unreal.MovieSceneSubTrack):
                continue
            for section in track.get_sections():
                child = section.get_sequence()
                rows.append({
                    "track": str(track.get_display_name()),
                    "child": child.get_path_name().split(".")[0] if child else None,
                    "start_s": float(section.get_start_frame_seconds()),
                    "end_s": float(section.get_end_frame_seconds()),
                    "is_rise": bool(child and child.get_path_name().split(".")[0] == rise_path),
                })
        return rows


    def curve_value(keys, time_s, interpolation):
        (start, v0), (end, v1) = keys
        u = max(0.0, min(1.0, (float(time_s) - float(start)) / (float(end) - float(start))))
        if interpolation == "AUTO":
            u = 3.0 * u * u - 2.0 * u * u * u
        return float(v0) + (float(v1) - float(v0)) * u


    def resolved_float(value):
        if value is None:
            return None
        if isinstance(value, tuple):
            if len(value) == 2 and isinstance(value[0], bool):
                return float(value[1]) if value[0] else None
            if len(value) == 1:
                return float(value[0])
        return float(value)


    def scene_starts(show, run):
        transport = unreal.new_object(unreal.InfinityStageTransportController)
        transport.build_segments(show)
        out = {
            int(str(segment.get_editor_property("label")).split()[1]): segment.get_editor_property("start_frame").value
            for segment in transport.get_editor_property("segments")
            if str(segment.get_editor_property("label")).startswith("Scene ")
        }
        del transport
        missing = [scene for scene in SCENES if scene not in out]
        if missing:
            fail(run, f"compiled Show is missing scene starts {missing}")
        return out


    def verify_seam(scene, arrival, drive_rows, state, W0, show, start_frame, run):
        if scene not in (1, 3):
            return None
        master_time = unreal.FrameTime(frame_number=unreal.FrameNumber(int(start_frame) - 1), sub_frame=0.0)
        labels = [
            next(label for label in sorted(state["practicals"])),
            next(label for label in sorted(state["glows"])),
        ]
        report = {}
        for label in labels:
            index = next(index for index, row in enumerate(drive_rows) if row["label"] == label)
            value = resolved_float(arrival.resolve_float_drive_at_master_frame(show, master_time, index))
            keys = state["practicals"].get(label) or state["glows"].get(label)
            at_zero = curve_value(keys, 0.0, "LINEAR")
            early = curve_value(keys, W0 + 1.0, "LINEAR")
            full = max(v for _t, v in keys)
            if value is None or abs(value - at_zero) > 1e-2:
                fail(run, f"S{scene} seam mismatch for {label}: Arrival={value}, channel_at_0={at_zero}")
            if not early < full * 0.5:
                fail(run, f"S{scene} {label} is not clearly below full at W0+1: {early}/{full}")
            report[label] = {"drive_index": index, "arrival_last_tick": value, "channel_at_0": at_zero, "at_W0_plus_1": early, "full": full}
        return report


    def log_channel_rows(run, scene, before, expected_before, after, s4_target, discovery):
        for role in ("root_pitch", "roof_pitch", "lattice_fly_z", "ppv_weight"):
            if before[role] is None and after[role] is None:
                continue
            before_status = "MATCH" if _keys_match(before[role], expected_before[role], FPS) else "MISMATCH"
            target_status = "MATCH" if _keys_match(after[role], s4_target[role], FPS) else "MISMATCH"
            unreal.log(
                f"HANGAR_RETIME_CHANNEL|run={run}|S{scene}|role={role}|before={before_status}|plan_vs_s4={target_status}|"
                f"action={'CREATE' if before[role] is None else 'REKEY'}|before_keys={json.dumps(before[role])}|"
                f"expected_before={json.dumps(expected_before[role])}|plan={json.dumps(after[role])}|s4={json.dumps(s4_target[role])}"
            )
        for role in ("uplights", "practicals", "glows"):
            labels = sorted(set(before[role]) | set(expected_before[role]) | set(after[role]) | set(s4_target[role]))
            for label in labels:
                before_status = "MATCH" if _keys_match(before[role].get(label), expected_before[role].get(label), FPS) else "MISMATCH"
                target_status = "MATCH" if _keys_match(after[role].get(label), s4_target[role].get(label), FPS) else "MISMATCH"
                interp_ok = label in discovery["channels"][role] and interpolation_matches(discovery["channels"][role][label][1], INTERPOLATION[role])
                unreal.log(
                    f"HANGAR_RETIME_CHANNEL|run={run}|S{scene}|role={role}|label={label}|before={before_status}|"
                    f"interpolation={'MATCH' if interp_ok else 'MISMATCH'}|plan_vs_s4={target_status}|"
                    f"before_keys={json.dumps(before[role].get(label))}|expected_before={json.dumps(expected_before[role].get(label))}|"
                    f"plan={json.dumps(after[role].get(label))}|s4={json.dumps(s4_target[role].get(label))}"
                )


    def backup_files(stamp, project, record_path):
        backup = os.path.join(project, "Backups", "PreHangarRetime-" + stamp.strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=False)
        disk = lambda path, ext: os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ext
        shutil.copy2(disk(EXPECTED_WORLD, ".umap"), backup)
        for scene in SCENES:
            shutil.copy2(disk(f"/Game/InfinityStage/RigAtmos/LS_S{scene}_HangarRise", ".uasset"), backup)
        shutil.copy2(record_path, backup)
        return backup


    def expected_dirty_set():
        return {
            "dirty_maps": [EXPECTED_WORLD],
            "dirty_content": sorted(f"/Game/InfinityStage/RigAtmos/LS_S{scene}_HangarRise" for scene in SCENES),
        }


    def main():
        run = datetime.datetime.now().strftime("%H%M%S")
        apply = bool(globals().get("HANGAR_RETIME_APPLY"))
        revert = bool(globals().get("HANGAR_RETIME_REVERT"))
        if apply and revert:
            fail(run, "apply and revert modes are mutually exclusive")

        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or editor.get_game_world() is not None:
            fail(run, "wrong world, or PIE")
        rekey = read_json(REKEY_RECORD, run)
        predrive = read_json(PREDRIVE_RECORD, run)
        W0, W1 = verify_window_records(rekey, predrive, run)
        roots = arrival_root_keys(run)
        actors = all_level_actors(world)
        show = unreal.load_asset(SHOW)
        if show is None:
            fail(run, f"Show asset missing: {SHOW}")
        starts = scene_starts(show, run)

        sequences = {}
        discoveries = {}
        befores = {}
        plans = {}
        targets = {}
        builders = {}
        actors_by_scene = {}
        arrivals = {}
        drive_apis = {}
        drives_before = {}
        nests = {}
        precondition_bad = []
        for scene in SCENES:
            path = f"/Game/InfinityStage/RigAtmos/LS_S{scene}_HangarRise"
            sequence = unreal.load_asset(path)
            if sequence is None:
                fail(run, f"S{scene}: rise sequence missing: {path}")
            if abs(float(sequence.get_playback_end_seconds()) - float(sequence.get_playback_start_seconds()) - 31.0) > 1.0 / FPS:
                fail(run, f"S{scene}: rise playback is not 31 seconds")
            fps = sequence.get_display_rate().numerator / float(sequence.get_display_rate().denominator)
            if abs(fps - FPS) > 1e-6:
                fail(run, f"S{scene}: expected 30 fps, found {fps}")
            discovery = discover_sequence(sequence, scene, run, allow_missing_exposure=True)
            exposure = one_actor(actors, f"S{scene} Hangar Pinned Exposure", run, required=False)
            has_exposure = exposure is not None
            if scene == 3 and has_exposure:
                fail(run, "S3 unexpectedly has a pinned exposure actor")
            if scene != 3 and not has_exposure:
                fail(run, f"S{scene}: pinned exposure actor is absent")
            before = capture_state(discovery, fps)
            builder = builder_beats_for_scene(scene, roots[scene], has_roof=scene != 6, has_exposure=has_exposure, fps=fps)
            try:
                planned = plan_scene(before, W0, W1, builder)
            except ValueError as exc:
                planned = None
                precondition_bad.append(f"S{scene}:{exc}")
            target = target_state_from_records(scene, rekey, predrive, scene != 6, has_exposure)
            if planned is not None:
                precondition_bad.extend(f"S{scene}:target:{item}" for item in _state_mismatches(planned, target, fps))
            precondition_bad.extend(f"S{scene}:unknown:{row}" for row in discovery["unknown"])
            precondition_bad.extend(f"S{scene}:interpolation:{item}" for item in interpolation_mismatches(discovery))
            scene_sequence = unreal.load_asset(f"/Game/InfinityStage/Dev/Sequences/LS_DevScene_0{scene}")
            if scene_sequence is None:
                fail(run, f"S{scene}: scene sequence missing")
            nest = nest_rows(scene_sequence, path)
            too_long = [row for row in nest if row["is_rise"] and row["end_s"] - row["start_s"] > 31.0 + 1.0 / FPS]  # only the rise nest; scene content (LS_Clams etc.) is longer by design
            if too_long:
                precondition_bad.append(f"S{scene}:nest section outlives 31 s rise:{too_long}")
            arrival = one_actor(actors, f"S{scene} Arrival", run)
            if not isinstance(arrival, unreal.InfinityStageArrival):
                fail(run, f"S{scene} Arrival is not InfinityStageArrival")
            api = discover_drive_api(arrival, run)
            # Resolve every level target one-to-one before any record, backup,
            # binding, key, or actor property is written.
            target_paths = []
            binding_guids = []
            for role in ("practicals", "glows"):
                for label, (binding, _channel) in sorted(discovery["channels"][role].items()):
                    target_paths.append(object_path(one_light_component(one_actor(actors, label, run), label, run)))
                    binding_guids.append(guid_text(binding.get_id()))
            if exposure is not None:
                target_paths.append(object_path(exposure))
            if len(set(target_paths)) != len(target_paths) or len(set(binding_guids)) != len(binding_guids):
                precondition_bad.append(f"S{scene}:drive targets or existing binding GUIDs are not one-to-one")
            if exposure is not None and discovery["exposure_binding"] is None:
                extensions = getattr(unreal, "MovieSceneBindingExtensions", None)
                if extensions is None or not hasattr(extensions, "remove"):
                    precondition_bad.append(f"S{scene}:MovieSceneBindingExtensions.remove is unavailable for revert")
            sequences[scene], discoveries[scene], befores[scene] = sequence, discovery, before
            plans[scene], targets[scene], builders[scene] = planned, target, builder
            actors_by_scene[scene] = {"exposure": exposure}
            arrivals[scene], drive_apis[scene] = arrival, api
            drives_before[scene] = capture_drives(arrival, api)
            nests[scene] = nest

        # S4 is read live, role for role, and must itself agree with its two applied records.
        s4 = unreal.load_asset("/Game/InfinityStage/RigAtmos/LS_S4_HangarRise")
        if s4 is None:
            fail(run, "S4 target sequence is missing")
        s4_discovery = discover_sequence(s4, 4, run, allow_missing_exposure=False)
        s4_state = capture_state(s4_discovery, FPS)
        s4_target = target_state_from_records(4, rekey, predrive, True, True)
        s4_bad = _state_mismatches(s4_state, s4_target, FPS) + interpolation_mismatches(s4_discovery)
        for role in ("root_pitch", "roof_pitch", "lattice_fly_z", "ppv_weight"):
            unreal.log(f"HANGAR_RETIME_S4_TARGET|run={run}|role={role}|record={'MATCH' if role not in s4_bad else 'MISMATCH'}|keys={json.dumps(s4_state[role])}")
        for role in ("uplights", "practicals", "glows"):
            for label, keys in sorted(s4_state[role].items()):
                key = f"{role}:{label}"
                unreal.log(f"HANGAR_RETIME_S4_TARGET|run={run}|role={role}|label={label}|record={'MATCH' if key not in s4_bad else 'MISMATCH'}|keys={json.dumps(keys)}")
        if s4_bad:
            fail(run, f"live S4 differs from its applied records: {s4_bad[:12]}")

        for scene in SCENES:
            if plans[scene] is not None:
                log_channel_rows(run, scene, befores[scene], {key: builders[scene][key] for key in ROLE_KEYS}, plans[scene], targets[scene], discoveries[scene])
            for row in discoveries[scene]["unknown"]:
                unreal.log(f"HANGAR_RETIME_CHANNEL|run={run}|S{scene}|role=UNKNOWN|before=MISMATCH|binding={json.dumps(row, sort_keys=True)}")
            unreal.log(f"HANGAR_RETIME_NEST|run={run}|S{scene}|sections={json.dumps(nests[scene], sort_keys=True)}")

        if not (apply or revert):
            marker = "HANGAR_RETIME_DRY_RUN_OK" if not precondition_bad else "HANGAR_RETIME_DRY_RUN_MISMATCH"
            unreal.log(f"{marker}|run={run}|mutated=0|issues={json.dumps(precondition_bad)}|{json.dumps(package_census(), sort_keys=True)}")
            return

        assert_write_guards(editor, world, run, applying=apply)
        if apply and precondition_bad:
            fail(run, f"apply preconditions failed: {precondition_bad[:12]}")

        if revert:
            record = read_json(RECORD, run)
            if sorted(int(scene) for scene in record.get("scenes", {})) != list(SCENES):
                fail(run, f"record scene set/order is not {SCENES}")
            # Gate every restoration on the complete applied state.
            for scene in SCENES:
                row = record["scenes"][str(scene)]
                if discoveries[scene]["unknown"]:
                    fail(run, f"S{scene}: unknown binding before revert")
                bad = _state_mismatches(befores[scene], row["after_keys"], FPS) + interpolation_mismatches(discoveries[scene])
                if bad:
                    fail(run, f"S{scene}: applied key state drifted: {bad[:10]}")
                if capture_drives(arrivals[scene], drive_apis[scene]) != row["after_drives"]:
                    fail(run, f"S{scene}: applied drives drifted")
                exposure = actors_by_scene[scene]["exposure"]
                if exposure is not None and abs(float(exposure.get_editor_property("blend_weight")) - float(row["blend_weight_after"])) > 1e-6:
                    fail(run, f"S{scene}: saved BlendWeight drifted")
                playback = [float(sequences[scene].get_playback_start_seconds()), float(sequences[scene].get_playback_end_seconds())]
                if playback != row["playback_before"]:
                    fail(run, f"S{scene}: playback range drifted")
                if not section_ranges_match(section_ranges(sequences[scene]), row["section_ranges_before"]):
                    fail(run, f"S{scene}: an original section range drifted")
                scene_sequence = unreal.load_asset(f"/Game/InfinityStage/Dev/Sequences/LS_DevScene_0{scene}")
                if nest_rows(scene_sequence, row["sequence"]) != row["nest_sections"]:
                    fail(run, f"S{scene}: nest sections drifted")
            # Reconstruct prior drive arrays before removing any created binding.
            prior_structs = {
                scene: restore_drive_structs(record["scenes"][str(scene)]["before_drives"], actors, sequences[scene], drive_apis[scene], run)
                for scene in SCENES
            }
            for scene in SCENES:
                row = record["scenes"][str(scene)]
                discovery = discoveries[scene]
                apply_state(discovery, row["before_keys"], FPS)
                arrivals[scene].set_editor_property(drive_apis[scene]["arrival_property"], prior_structs[scene])
                exposure = actors_by_scene[scene]["exposure"]
                if exposure is not None:
                    exposure.set_editor_property("blend_weight", float(row["blend_weight_before"]))
                if row["created_exposure_binding"]:
                    remove_binding(sequences[scene], discovery["exposure_binding"], run)
            # Fresh discovery proves the exact recorded before state before save.
            for scene in SCENES:
                row = record["scenes"][str(scene)]
                fresh = discover_sequence(sequences[scene], scene, run, allow_missing_exposure=True)
                got = capture_state(fresh, FPS)
                bad = _state_mismatches(got, row["before_keys"], FPS) + interpolation_mismatches(fresh)
                if bad or capture_drives(arrivals[scene], drive_apis[scene]) != row["before_drives"]:
                    fail(run, f"S{scene}: revert read-back failed: {bad[:10]}")
                exposure = actors_by_scene[scene]["exposure"]
                if exposure is not None and abs(float(exposure.get_editor_property("blend_weight")) - float(row["blend_weight_before"])) > 1e-6:
                    fail(run, f"S{scene}: BlendWeight revert read-back failed")
                if row["created_exposure_binding"] and fresh["exposure_binding"] is not None:
                    fail(run, f"S{scene}: created exposure binding survived revert")
                if not section_ranges_match(section_ranges(sequences[scene]), row["section_ranges_before"], exact=True):
                    fail(run, f"S{scene}: an original section range changed during revert")
                scene_sequence = unreal.load_asset(f"/Game/InfinityStage/Dev/Sequences/LS_DevScene_0{scene}")
                if nest_rows(scene_sequence, row["sequence"]) != row["nest_sections"]:
                    fail(run, f"S{scene}: nest sections changed during revert")
            if package_census() != expected_dirty_set():
                fail(run, f"unexpected dirty set before revert save: {package_census()}")
            for scene in SCENES:
                if not unreal.EditorAssetLibrary.save_asset(f"/Game/InfinityStage/RigAtmos/LS_S{scene}_HangarRise", only_if_is_dirty=False):
                    fail(run, f"S{scene}: sequence save failed")
            if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
                fail(run, "level save failed")
            os.replace(RECORD, RECORD + ".reverted")
            unreal.log(f"HANGAR_RETIME_DONE|run={run}|reverted|scenes=1,2,3,6|{json.dumps(package_census(), sort_keys=True)}")
            return

        stamp = datetime.datetime.now()
        record = {
            "written": stamp.isoformat(timespec="seconds"),
            "run": run,
            "W0": W0,
            "W1": W1,
            "target_records": [os.path.basename(REKEY_RECORD), os.path.basename(PREDRIVE_RECORD)],
            "scenes": {},
        }
        for scene in SCENES:
            sequence = sequences[scene]
            exposure = actors_by_scene[scene]["exposure"]
            record["scenes"][str(scene)] = {
                "builder_commit": BUILDER_COMMITS[scene],
                "sequence": f"/Game/InfinityStage/RigAtmos/LS_S{scene}_HangarRise",
                "playback_before": [float(sequence.get_playback_start_seconds()), float(sequence.get_playback_end_seconds())],
                "section_ranges_before": section_ranges(sequence),
                "before_keys": copy.deepcopy(befores[scene]),
                "after_keys": copy.deepcopy(plans[scene]),
                "before_drives": copy.deepcopy(drives_before[scene]),
                "after_drives": None,
                "blend_weight_before": None if exposure is None else float(exposure.get_editor_property("blend_weight")),
                "blend_weight_after": None if exposure is None else 0.0,
                "created_exposure_binding": bool(exposure is not None and discoveries[scene]["exposure_binding"] is None),
                "nest_sections": nests[scene],
            }
        with open(RECORD, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = backup_files(stamp, project, RECORD)

        drive_rows_by_scene = {}
        for scene in SCENES:
            discovery = discoveries[scene]
            exposure = actors_by_scene[scene]["exposure"]
            if exposure is not None and discovery["exposure_binding"] is None:
                binding, channel = add_exposure_channel(
                    sequences[scene], exposure, record["scenes"][str(scene)]["playback_before"], run
                )
                discovery["exposure_binding"] = binding
                discovery["channels"]["ppv_weight"] = channel
            apply_state(discovery, plans[scene], FPS)
            if exposure is not None:
                exposure.set_editor_property("blend_weight", 0.0)
            rows, structs, plain = build_drives(scene, actors, discovery, exposure, drive_apis[scene], run)
            arrivals[scene].set_editor_property(drive_apis[scene]["arrival_property"], structs)
            drive_rows_by_scene[scene] = rows
            record["scenes"][str(scene)]["after_drives"] = plain
        with open(RECORD, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
        # The first backup copy proves a record existed before Unreal mutation;
        # refresh only that copy now that the newly created binding GUIDs/drives
        # are known, so the backup also contains the complete revert authority.
        shutil.copy2(RECORD, os.path.join(backup, os.path.basename(RECORD)))

        seams = {}
        s4_pitch_zero = curve_value(s4_state["root_pitch"], 0.0, "AUTO")
        for scene in SCENES:
            sequence = sequences[scene]
            discovery = discoveries[scene]
            got = capture_state(discovery, FPS)
            bad = _state_mismatches(got, plans[scene], FPS) + interpolation_mismatches(discovery)
            if bad:
                fail(run, f"S{scene}: apply key read-back failed: {bad[:10]}")
            if capture_drives(arrivals[scene], drive_apis[scene]) != record["scenes"][str(scene)]["after_drives"]:
                fail(run, f"S{scene}: drive read-back failed")
            exposure = actors_by_scene[scene]["exposure"]
            if exposure is not None and abs(float(exposure.get_editor_property("blend_weight"))) > 1e-6:
                fail(run, f"S{scene}: saved BlendWeight is not zero")
            playback = [float(sequence.get_playback_start_seconds()), float(sequence.get_playback_end_seconds())]
            if playback != record["scenes"][str(scene)]["playback_before"]:
                fail(run, f"S{scene}: playback range changed")
            original_ranges = record["scenes"][str(scene)]["section_ranges_before"]
            current_ranges = section_ranges(sequence)
            if not section_ranges_match(current_ranges, original_ranges):
                fail(run, f"S{scene}: an original section range changed")
            scene_sequence = unreal.load_asset(f"/Game/InfinityStage/Dev/Sequences/LS_DevScene_0{scene}")
            if nest_rows(scene_sequence, record["scenes"][str(scene)]["sequence"]) != record["scenes"][str(scene)]["nest_sections"]:
                fail(run, f"S{scene}: nest sections changed")
            pitch_zero = curve_value(got["root_pitch"], 0.0, "AUTO")
            if abs(pitch_zero - s4_pitch_zero) > 0.05 or abs(pitch_zero + 33.42) > 0.05:
                fail(run, f"S{scene}: root pitch at scene zero is {pitch_zero:.4f}, S4={s4_pitch_zero:.4f}")
            seams[str(scene)] = verify_seam(scene, arrivals[scene], drive_rows_by_scene[scene], got, W0, show, starts[scene], run)
        if package_census() != expected_dirty_set():
            fail(run, f"unexpected dirty set before apply save: {package_census()}")
        for scene in SCENES:
            if not unreal.EditorAssetLibrary.save_asset(f"/Game/InfinityStage/RigAtmos/LS_S{scene}_HangarRise", only_if_is_dirty=False):
                fail(run, f"S{scene}: sequence save failed")
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            fail(run, "level save failed")
        unreal.log(
            f"HANGAR_RETIME_DONE|run={run}|applied|scenes=1,2,3,6|backup={backup}|"
            f"seams={json.dumps(seams, sort_keys=True)}|{json.dumps(package_census(), sort_keys=True)}"
        )


    main()
