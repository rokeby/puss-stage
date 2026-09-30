"""Author Scene 4's pre-cut light/exposure drives without opening Sequencer.

Dry run is the default. S4PREDRIVE_APPLY records and backs up the sequence and
level, re-keys only the 38 practical/glow Intensity channels and the exposure
BlendWeight channel, authors the S4 Arrival's 39 PreSceneFloatDrives, verifies
keys/drives/seams, and saves only those two packages. S4PREDRIVE_REVERT first
requires the recorded applied state, then restores the exact recorded state.

plan_keys() is deliberately Unreal-free for test_s4_predrive_plan.py.
"""
import copy
import datetime
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Plain-Python planning harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ = "/Game/InfinityStage/RigAtmos/LS_S4_HangarRise"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
ARRIVAL_LABEL = "S4 Arrival"
EXPOSURE_LABEL = "S4 Hangar Pinned Exposure"
PRACTICAL_PREFIX = "S4 Practical"
GLOW_PREFIX = "S4 Lattice Glow"

if unreal is not None:
    HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW_RECORD = os.path.join(HERE, "p04_backcloth_section_record.json")
RECORD = os.path.join(HERE, "s4_predrive_author_record.json")


def _plain_keys(keys):
    return [[float(t), float(v)] for t, v in keys]


def _close(a, b, tolerance=1e-6):
    return abs(float(a) - float(b)) <= tolerance


def _time_close(a, b):
    # Authored seconds are quantized to display-rate frames by Sequencer.
    return _close(a, b, 1.0 / 24.0 + 1e-9)


def plan_keys(before, W0, W1):
    """Validate the exact pre-state and return the complete targeted key plan."""
    W0, W1 = float(W0), float(W1)
    if not W0 < 0.0 < W1:
        raise ValueError(f"required W0 < 0 < W1, found W0={W0}, W1={W1}")
    if not isinstance(before, dict) or set(before) != {"intensity", "ppv_weight"}:
        raise ValueError("before must contain exactly intensity and ppv_weight")
    intensity = before["intensity"]
    if not isinstance(intensity, dict):
        raise ValueError("before.intensity must be an object")
    practicals = [name for name in intensity if str(name).startswith(PRACTICAL_PREFIX)]
    glows = [name for name in intensity if str(name).startswith(GLOW_PREFIX)]
    other = [name for name in intensity if name not in practicals and name not in glows]
    if len(practicals) != 14 or len(glows) != 24 or other:
        raise ValueError(
            f"expected 14 practical and 24 glow channels only; found {len(practicals)}, {len(glows)}, other={other}"
        )

    after = {"intensity": {}, "ppv_weight": [[W0, 0.0], [W1, 1.0]]}
    for label, raw_keys in sorted(intensity.items()):
        keys = _plain_keys(raw_keys)
        if len(keys) != 2:
            raise ValueError(f"{label}: expected exactly two keys, found {len(keys)}")
        full = max(value for _time_s, value in keys)
        expected = [[0.0, 0.0], [W1, full]]
        if full <= 0.0 or any(
            not _time_close(got_t, want_t) or not _close(got_v, want_v, 1e-3)
            for (got_t, got_v), (want_t, want_v) in zip(keys, expected)
        ):
            raise ValueError(f"{label}: before keys {keys!r} do not match expected {expected!r}")
        after["intensity"][str(label)] = [[W0, 0.0], [W1, float(full)]]

    ppv = _plain_keys(before["ppv_weight"])
    expected_ppv = [[0.0, 0.0], [W1, 1.0]]
    if len(ppv) != 2 or any(
        not _time_close(got_t, want_t) or not _close(got_v, want_v, 1e-3)
        for (got_t, got_v), (want_t, want_v) in zip(ppv, expected_ppv)
    ):
        raise ValueError(f"ppv_weight: before keys {ppv!r} do not match expected {expected_ppv!r}")
    return after


def fail(run, message):
    unreal.log_error(f"S4PREDRIVE_STOPPED|run={run}|{message}")
    raise RuntimeError(message)


def package_census():
    return {
        "dirty_maps": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "dirty_content": sorted(
            str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        ),
    }


def keys_of(channel, fps):
    return [[k.get_time().frame_number.value / fps, float(k.get_value())] for k in channel.get_keys()]


def set_keys(channel, keys, fps, interpolation):
    for key in list(channel.get_keys()):
        channel.remove_key(key)
    for time_s, value in keys:
        channel.add_key(
            unreal.FrameNumber(int(round(float(time_s) * fps))),
            float(value),
            time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
            interpolation=interpolation,
        )


def keys_match(got, expected, fps):
    if len(got) != len(expected):
        return False
    one_frame = 1.0 / fps
    return all(
        abs(float(gt) - float(wt)) <= one_frame + 1e-9 and abs(float(gv) - float(wv)) <= 1e-3
        for (gt, gv), (wt, wv) in zip(got, expected)
    )


def interpolation_matches(channel, expected_name):
    keys = list(channel.get_keys())
    return bool(keys) and all(
        hasattr(key, "get_interpolation_mode")
        and str(key.get_interpolation_mode()).upper().endswith(expected_name)
        for key in keys
    )


def one_binding(sequence, label, run):
    found = [binding for binding in sequence.get_bindings() if str(binding.get_display_name()) == label]
    if len(found) != 1:
        fail(run, f"expected one binding {label!r}, found {len(found)}")
    return found[0]


def discover_channels(sequence, run):
    intensity = {}
    for binding in sequence.get_bindings():
        parent = binding.get_parent()
        parent_name = str(parent.get_display_name()) if parent and parent.is_valid() else None
        if not parent_name or not parent_name.startswith((PRACTICAL_PREFIX, GLOW_PREFIX)):
            continue
        found = []
        for track in binding.get_tracks():
            if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == "Intensity":
                for section in track.get_sections():
                    found.extend(section.get_all_channels())
        if len(found) != 1:
            fail(run, f"expected one Intensity channel below {parent_name}, found {len(found)}")
        if parent_name in intensity:
            fail(run, f"duplicate component binding below {parent_name}")
        intensity[parent_name] = {"binding": binding, "channel": found[0]}

    practicals = [name for name in intensity if name.startswith(PRACTICAL_PREFIX)]
    glows = [name for name in intensity if name.startswith(GLOW_PREFIX)]
    if len(practicals) != 14 or len(glows) != 24:
        fail(run, f"expected 14 practical and 24 glow channels, found {len(practicals)} and {len(glows)}")

    exposure_binding = one_binding(sequence, EXPOSURE_LABEL, run)
    exposure_channels = []
    for track in exposure_binding.get_tracks():
        if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == "BlendWeight":
            for section in track.get_sections():
                exposure_channels.extend(section.get_all_channels())
    if len(exposure_channels) != 1:
        fail(run, f"expected one BlendWeight channel on {EXPOSURE_LABEL}, found {len(exposure_channels)}")
    return intensity, exposure_binding, exposure_channels[0]


def capture_keys(intensity, exposure_channel, fps):
    return {
        "intensity": {
            label: keys_of(row["channel"], fps) for label, row in sorted(intensity.items())
        },
        "ppv_weight": keys_of(exposure_channel, fps),
    }


def key_mismatches(intensity, exposure_channel, expected, fps):
    got = capture_keys(intensity, exposure_channel, fps)
    bad = [
        f"intensity:{label}"
        for label, wanted in expected["intensity"].items()
        if label not in got["intensity"]
        or not keys_match(got["intensity"][label], wanted, fps)
        or not interpolation_matches(intensity[label]["channel"], "LINEAR")
    ]
    if not keys_match(got["ppv_weight"], expected["ppv_weight"], fps) or not interpolation_matches(
        exposure_channel, "AUTO"
    ):
        bad.append("ppv_weight")
    return bad


def apply_key_set(intensity, exposure_channel, planned, fps):
    for label, keys in planned["intensity"].items():
        set_keys(intensity[label]["channel"], keys, fps, unreal.MovieSceneKeyInterpolation.LINEAR)
    set_keys(exposure_channel, planned["ppv_weight"], fps, unreal.MovieSceneKeyInterpolation.AUTO)


def all_level_actors(world):
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


def one_actor(actors, label, run):
    found = [actor for actor in actors if str(actor.get_actor_label()) == label]
    if len(found) != 1:
        fail(run, f"expected one level actor {label!r}, found {len(found)}")
    return found[0]


def one_light_component(actor, label, run):
    if hasattr(actor, "get_components_by_class"):
        found = list(actor.get_components_by_class(unreal.LightComponent))
        if len(found) != 1:
            fail(run, f"expected one LightComponent on {label}, found {len(found)}")
        return found[0]
    component = actor.get_component_by_class(unreal.LightComponent)
    if component is None:
        fail(run, f"no LightComponent on {label}")
    return component


def object_path(value):
    if value is None:
        return "None"
    if hasattr(value, "get_path_name"):
        return str(value.get_path_name())
    return str(value)


def _first_editor_property(obj, candidates, run, semantic):
    for name in candidates:
        try:
            obj.get_editor_property(name)
            return name
        except Exception:
            pass
    public = sorted(name for name in dir(obj) if not name.startswith("_"))
    fail(run, f"could not discover {semantic}; dir={public}")


def discover_python_api(arrival, run):
    probe = unreal.InfinityArrivalFloatDrive()
    fields = {
        "target": _first_editor_property(probe, ("target",), run, "float-drive Target"),
        "binding_guid": _first_editor_property(
            probe, ("binding_guid", "bindingguid"), run, "float-drive BindingGuid"
        ),
        "property_name": _first_editor_property(
            probe, ("property_name", "propertyname"), run, "float-drive PropertyName"
        ),
    }
    arrival_property = _first_editor_property(
        arrival, ("pre_scene_float_drives", "prescene_float_drives"), run, "Arrival PreSceneFloatDrives"
    )
    resolve_method = next(
        (name for name in ("resolve_float_drive_at_master_frame",) if callable(getattr(arrival, name, None))), None
    )
    if resolve_method is None:
        fail(run, "could not discover ResolveFloatDriveAtMasterFrame")
    return {"struct_fields": fields, "arrival_property": arrival_property, "resolve_method": resolve_method}


def plain_drive(drive, api):
    fields = api["struct_fields"]
    return {
        "target": object_path(drive.get_editor_property(fields["target"])),
        "binding_guid": str(drive.get_editor_property(fields["binding_guid"])),
        "property_name": str(drive.get_editor_property(fields["property_name"])),
    }


def capture_drives(arrival, api):
    drives = list(arrival.get_editor_property(api["arrival_property"]))
    return {"count": len(drives), "entries": [plain_drive(drive, api) for drive in drives]}


def make_drive(target, binding_guid, property_name, api):
    fields = api["struct_fields"]
    drive = unreal.InfinityArrivalFloatDrive()
    drive.set_editor_property(fields["target"], target)
    drive.set_editor_property(fields["binding_guid"], binding_guid)
    drive.set_editor_property(fields["property_name"], property_name)
    return drive


def build_applied_drives(actors, intensity, exposure_binding, exposure_actor, api, run):
    rows = []
    for label, row in sorted(intensity.items()):
        actor = one_actor(actors, label, run)
        component = one_light_component(actor, label, run)
        rows.append(
            {
                "label": label,
                "target_object": component,
                "target": object_path(component),
                "binding_guid_object": row["binding"].get_id(),
                "binding_guid": str(row["binding"].get_id()),
                "property_name": "Intensity",
            }
        )
    rows.append(
        {
            "label": EXPOSURE_LABEL,
            "target_object": exposure_actor,
            "target": object_path(exposure_actor),
            "binding_guid_object": exposure_binding.get_id(),
            "binding_guid": str(exposure_binding.get_id()),
            "property_name": "BlendWeight",
        }
    )
    target_paths = [row["target"] for row in rows]
    binding_guids = [row["binding_guid"] for row in rows]
    if len(rows) != 39 or len(set(target_paths)) != 39 or len(set(binding_guids)) != 39:
        fail(
            run,
            f"drive matching was not one-to-one: rows={len(rows)}, targets={len(set(target_paths))}, "
            f"bindings={len(set(binding_guids))}",
        )
    structs = [
        make_drive(row["target_object"], row["binding_guid_object"], row["property_name"], api)
        for row in rows
    ]
    plain = {
        "count": len(rows),
        "entries": [
            {key: row[key] for key in ("target", "binding_guid", "property_name")} for row in rows
        ],
    }
    return rows, structs, plain


def current_object_index(actors):
    out = {}
    for actor in actors:
        out[object_path(actor)] = actor
        if hasattr(actor, "get_components_by_class"):
            for component in actor.get_components_by_class(unreal.ActorComponent):
                out[object_path(component)] = component
    return out


def restore_drive_structs(recorded, actors, sequence, api, run):
    objects = current_object_index(actors)
    guids = {str(binding.get_id()): binding.get_id() for binding in sequence.get_bindings()}
    structs = []
    for index, row in enumerate(recorded["entries"]):
        target = None if row["target"] == "None" else objects.get(row["target"])
        guid = guids.get(row["binding_guid"])
        if (target is None and row["target"] != "None") or guid is None:
            fail(run, f"cannot restore prior drive {index}: target={row['target']!r}, guid={row['binding_guid']!r}")
        structs.append(make_drive(target, guid, row["property_name"], api))
    if len(structs) != int(recorded["count"]):
        fail(run, f"recorded prior drive count mismatch: count={recorded['count']}, entries={len(structs)}")
    return structs


def drive_state_matches(got, wanted):
    return got.get("count") == wanted.get("count") and got.get("entries") == wanted.get("entries")


def read_window(run):
    if not os.path.exists(WINDOW_RECORD):
        fail(run, f"missing timing authority {WINDOW_RECORD}")
    with open(WINDOW_RECORD, encoding="utf-8") as handle:
        data = json.load(handle)
    plan = data.get("plan")
    if not isinstance(plan, dict):
        fail(run, "p04_backcloth_section_record.json has no plan object")
    if plan.get("lead_s") != 5.0:
        fail(run, f"expected plan.lead_s 5.0, found {plan.get('lead_s')!r}")
    W0, W1 = plan.get("cloth_release_s"), plan.get("section_end_s")
    if W0 is None or W1 is None:
        fail(run, f"timing authority is missing cloth_release_s or section_end_s: {W0!r}, {W1!r}")
    W0, W1 = float(W0), float(W1)
    if not W0 < 0.0 < W1:
        fail(run, f"invalid cloth window W0={W0}, W1={W1}")
    return W0, W1


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
        fail(run, "already applied (record exists); revert first")
    if not applying and not os.path.exists(RECORD):
        fail(run, "revert record is absent")


def _resolved_float(value):
    if value is None:
        return None
    if isinstance(value, tuple):
        if len(value) == 2 and isinstance(value[0], bool):
            return float(value[1]) if value[0] else None
        if len(value) == 1:
            return float(value[0])
    return float(value)


def curve_value_at_zero(keys, interpolation):
    (W0, v0), (W1, v1) = keys
    u = (0.0 - float(W0)) / (float(W1) - float(W0))
    if interpolation == "AUTO":
        u = 3.0 * u * u - 2.0 * u * u * u
    return float(v0) + (float(v1) - float(v0)) * u


def curve_value(keys, time_s, interpolation):
    (W0, v0), (W1, v1) = keys
    u = (float(time_s) - float(W0)) / (float(W1) - float(W0))
    u = max(0.0, min(1.0, u))
    if interpolation == "AUTO":
        u = 3.0 * u * u - 2.0 * u * u * u
    return float(v0) + (float(v1) - float(v0)) * u


def verify_seams(arrival, api, drive_rows, live_keys, W0, show, run):
    transport = unreal.new_object(unreal.InfinityStageTransportController)
    transport.build_segments(show)
    starts_by_scene = {
        str(segment.get_editor_property("label")).split()[1]: segment.get_editor_property("start_frame").value
        for segment in transport.get_editor_property("segments")
        if str(segment.get_editor_property("label")).startswith("Scene ")
    }
    del transport
    if "4" not in starts_by_scene:
        fail(run, f"Scene 4 segment absent; found scenes={sorted(starts_by_scene)}")
    scene_start = starts_by_scene["4"]
    master_time = unreal.FrameTime(
        frame_number=unreal.FrameNumber(int(scene_start) - 1),
        sub_frame=0.0,
    )
    sample_labels = [
        next(label for label in sorted(live_keys["intensity"]) if label.startswith(PRACTICAL_PREFIX)),
        next(label for label in sorted(live_keys["intensity"]) if label.startswith(GLOW_PREFIX)),
        EXPOSURE_LABEL,
    ]
    seam = {}
    for label in sample_labels:
        index = next(i for i, row in enumerate(drive_rows) if row["label"] == label)
        resolved = _resolved_float(getattr(arrival, api["resolve_method"])(show, master_time, index))
        keys = live_keys["ppv_weight"] if label == EXPOSURE_LABEL else live_keys["intensity"][label]
        interpolation = "AUTO" if label == EXPOSURE_LABEL else "LINEAR"
        at_zero = curve_value_at_zero(keys, interpolation)
        early = curve_value(keys, W0 + 1.0, interpolation)
        full = max(value for _time_s, value in keys)
        if resolved is None or abs(resolved - at_zero) > 1e-2:
            fail(run, f"seam mismatch for {label}: Arrival={resolved!r}, channel_at_0={at_zero}")
        if not early < full * 0.5:
            fail(run, f"early ramp is not clearly below full for {label}: at_W0_plus_1={early}, full={full}")
        seam[label] = {
            "drive_index": index,
            "arrival_last_tick": resolved,
            "channel_at_0": at_zero,
            "at_W0_plus_1": early,
            "full": full,
        }
    return {"scene_start_frame": scene_start, "samples": seam}


def backup_files(stamp, project, record_path):
    backup = os.path.join(project, "Backups", "PreS4Predrive-" + stamp.strftime("%Y%m%d-%H%M"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *SEQ[len("/Game/"):].split("/")) + ".uasset", backup)
    shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
    shutil.copy2(record_path, backup)
    return backup


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S4PREDRIVE_APPLY"))
    revert = bool(globals().get("S4PREDRIVE_REVERT"))
    if apply and revert:
        fail(run, "apply and revert modes are mutually exclusive")

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or editor.get_game_world() is not None:
        fail(run, "wrong world, or PIE")
    W0, W1 = read_window(run)
    sequence = unreal.load_asset(SEQ)
    show = unreal.load_asset(SHOW)
    if sequence is None or show is None:
        fail(run, f"required asset missing: sequence={sequence is not None}, show={show is not None}")
    rate = sequence.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    playback = [float(sequence.get_playback_start_seconds()), float(sequence.get_playback_end_seconds())]
    intensity, exposure_binding, exposure_channel = discover_channels(sequence, run)
    actors = all_level_actors(world)
    arrival = one_actor(actors, ARRIVAL_LABEL, run)
    if not isinstance(arrival, unreal.InfinityStageArrival):
        fail(run, f"{ARRIVAL_LABEL} is not an InfinityStageArrival")
    exposure_actor = one_actor(actors, EXPOSURE_LABEL, run)
    api = discover_python_api(arrival, run)
    before = capture_keys(intensity, exposure_channel, fps)
    drive_rows, applied_structs, applied_plain = build_applied_drives(
        actors, intensity, exposure_binding, exposure_actor, api, run
    )
    current_drives = capture_drives(arrival, api)
    if revert:
        assert_write_guards(editor, world, run, applying=False)
        with open(RECORD, encoding="utf-8") as handle:
            record = json.load(handle)
        planned = record["after_keys"]
        prior_drives = record["before_drives"]
    else:
        try:
            planned = plan_keys(before, W0, W1)
        except ValueError as exc:
            fail(run, f"key precondition failed: {exc}")
        prior_drives = current_drives
    unreal.log(
        f"S4PREDRIVE_PLAN|run={run}|W0={W0}|W1={W1}|fps={fps}|playback={playback}|"
        f"python_api={json.dumps(api, sort_keys=True)}|before_drives={json.dumps(prior_drives, sort_keys=True)}|"
        f"after_keys={json.dumps(planned, sort_keys=True)}|after_drives={json.dumps(applied_plain, sort_keys=True)}"
    )
    if not (apply or revert):
        unreal.log(f"S4PREDRIVE_DRY_RUN_OK|run={run}|mutated=0|{json.dumps(package_census(), sort_keys=True)}")
        return

    if apply:
        assert_write_guards(editor, world, run, applying=True)

    if revert:
        bad = key_mismatches(intensity, exposure_channel, record["after_keys"], fps)
        if bad or not drive_state_matches(current_drives, record["after_drives"]):
            fail(run, f"revert refused: applied state drifted; keys={bad[:8]}, drives={current_drives}")
        restored_structs = restore_drive_structs(record["before_drives"], actors, sequence, api, run)
        apply_key_set(intensity, exposure_channel, record["before_keys"], fps)
        arrival.set_editor_property(api["arrival_property"], restored_structs)
        bad = key_mismatches(intensity, exposure_channel, record["before_keys"], fps)
        restored_drives = capture_drives(arrival, api)
        if bad or not drive_state_matches(restored_drives, record["before_drives"]):
            fail(run, f"revert read-back failed before save: keys={bad[:8]}, drives={restored_drives}")
        if [float(sequence.get_playback_start_seconds()), float(sequence.get_playback_end_seconds())] != record["playback_before"]:
            fail(run, "playback range changed during revert (nothing saved)")
        if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
            fail(run, "sequence save failed")
        if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
            fail(run, "level save failed")
        os.replace(RECORD, RECORD + ".reverted")
        unreal.log(f"S4PREDRIVE_OK|run={run}|reverted|{json.dumps(package_census(), sort_keys=True)}")
        return

    stamp = datetime.datetime.now()
    record = {
        "written": stamp.isoformat(timespec="seconds"),
        "run": run,
        "timing_source": os.path.basename(WINDOW_RECORD),
        "W0": W0,
        "W1": W1,
        "fps": fps,
        "playback_before": playback,
        "python_api": api,
        "before_keys": copy.deepcopy(before),
        "after_keys": copy.deepcopy(planned),
        "before_drives": copy.deepcopy(prior_drives),
        "after_drives": copy.deepcopy(applied_plain),
    }
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = backup_files(stamp, project, RECORD)

    apply_key_set(intensity, exposure_channel, planned, fps)
    arrival.set_editor_property(api["arrival_property"], applied_structs)
    bad = key_mismatches(intensity, exposure_channel, planned, fps)
    got_drives = capture_drives(arrival, api)
    if bad or not drive_state_matches(got_drives, applied_plain):
        fail(run, f"apply read-back failed before save: keys={bad[:8]}, drives={got_drives}")
    if [float(sequence.get_playback_start_seconds()), float(sequence.get_playback_end_seconds())] != playback:
        fail(run, "playback range changed during apply (nothing saved)")
    live_keys = capture_keys(intensity, exposure_channel, fps)
    seam = verify_seams(arrival, api, drive_rows, live_keys, W0, show, run)
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        fail(run, "sequence save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail(run, "level save failed")
    unreal.log(
        f"S4PREDRIVE_OK|run={run}|applied|channels=39|drives=39|backup={backup}|"
        f"seam={json.dumps(seam, sort_keys=True)}|{json.dumps(package_census(), sort_keys=True)}"
    )


if unreal is not None:
    main()
