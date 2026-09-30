"""Rekey Scene 4's hangar rise to the P04 backcloth's recorded five-second window.

The timing authority is p04_backcloth_section_record.json: never duplicate its
window here. Dry run is the default. S4REKEY_APPLY records the keys as found,
backs up the sequence, edits through the asset API only, verifies every changed
channel, and saves only the sequence. S4REKEY_REVERT first requires the live
keys to match the recorded applied state, then restores exactly the recorded
before keys. Sequencer is never opened. Marker: S4REKEY_*|run=<HHMMSS>.

plan_keys() is deliberately Unreal-free so test_s4_rekey_plan.py can import it
with plain Python.
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
CURRENT_LANDING_S = 16.0
ROOT_LABEL = "S4 Hangar Root"
ROOF_LABEL = "S4 Hangar Roof Hinge"
LATTICE_LABEL = "S4 Hangar Lattice Fly"
EXPOSURE_LABEL = "S4 Hangar Pinned Exposure"
PRACTICAL_PREFIX = "S4 Practical"
GLOW_PREFIX = "S4 Lattice Glow"
UPLIGHT_PREFIX = "S4 Uplight"

if unreal is not None:
    HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW_RECORD = os.path.join(HERE, "p04_backcloth_section_record.json")
RECORD = os.path.join(HERE, "s4_rekey_window_record.json")


def _plain_keys(keys):
    return [[float(t), float(v)] for t, v in keys]


def _shift_positive(keys, delta):
    return [[float(t) if float(t) == 0.0 else round(float(t) + delta, 6), float(v)] for t, v in keys]


def plan_keys(before, W0, W1):
    """Return the complete rekey plan as plain floats without importing Unreal."""
    W0, W1 = float(W0), float(W1)
    if W0 >= 0.0:
        raise ValueError("W0 must be before the Scene 4 cut")
    if W1 <= 0.0:
        raise ValueError("W1 must be after the Scene 4 cut")
    required = ("intensity", "uplights", "root_pitch", "roof_pitch", "lattice_fly_z", "ppv_weight")
    missing = [name for name in required if name not in before]
    if missing:
        raise ValueError("before is missing: " + ", ".join(missing))

    delta = W1 - CURRENT_LANDING_S
    after = copy.deepcopy(before)
    after["root_pitch"] = [[W0, -90.0], [W1, 0.0]]
    after["intensity"] = {
        str(label): [[0.0, 0.0], [W1, max(float(v) for _t, v in keys)]]
        for label, keys in before["intensity"].items()
    }
    after["uplights"] = {
        str(label): _shift_positive(_plain_keys(keys), delta)
        for label, keys in before["uplights"].items()
    }
    after["roof_pitch"] = _shift_positive(_plain_keys(before["roof_pitch"]), delta)
    after["lattice_fly_z"] = _shift_positive(_plain_keys(before["lattice_fly_z"]), delta)
    after["ppv_weight"] = [[0.0, 0.0], [W1, 1.0]]
    return after


def fail(run, message):
    unreal.log_error(f"S4REKEY_STOPPED|run={run}|{message}")
    raise RuntimeError(message)


def package_census():
    return {
        "dirty_maps": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "dirty_content": sorted(str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
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


def one_binding(seq, label, run):
    found = [binding for binding in seq.get_bindings() if str(binding.get_display_name()) == label]
    if len(found) != 1:
        fail(run, f"expected one binding {label!r}, found {len(found)}")
    return found[0]


def one_transform_channel(seq, label, index, run):
    binding = one_binding(seq, label, run)
    tracks = [track for track in binding.get_tracks() if isinstance(track, unreal.MovieScene3DTransformTrack)]
    if len(tracks) != 1 or len(tracks[0].get_sections()) != 1:
        fail(run, f"expected one transform track/section on {label}, found {len(tracks)} tracks")
    channels = list(tracks[0].get_sections()[0].get_all_channels())
    if len(channels) <= index:
        fail(run, f"{label} has {len(channels)} transform channels, needs index {index}")
    return channels[index]


def component_float_channels(seq, prefixes, property_name, run):
    out = {}
    for binding in seq.get_bindings():
        parent = binding.get_parent()
        parent_name = str(parent.get_display_name()) if parent and parent.is_valid() else None
        if not parent_name or not parent_name.startswith(prefixes):
            continue
        found = []
        for track in binding.get_tracks():
            if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == property_name:
                for section in track.get_sections():
                    found.extend(section.get_all_channels())
        if len(found) != 1:
            fail(run, f"expected one {property_name} channel below {parent_name}, found {len(found)}")
        if parent_name in out:
            fail(run, f"duplicate component binding below {parent_name}")
        out[parent_name] = found[0]
    return out


def binding_float_channel(seq, label, property_name, run):
    binding = one_binding(seq, label, run)
    found = []
    for track in binding.get_tracks():
        if isinstance(track, unreal.MovieSceneFloatTrack) and str(track.get_property_name()) == property_name:
            for section in track.get_sections():
                found.extend(section.get_all_channels())
    if len(found) != 1:
        fail(run, f"expected one {property_name} channel on {label}, found {len(found)}")
    return found[0]


def discover_channels(seq, run):
    intensity = component_float_channels(seq, (PRACTICAL_PREFIX, GLOW_PREFIX), "Intensity", run)
    uplights = component_float_channels(seq, (UPLIGHT_PREFIX,), "Intensity", run)
    if len(intensity) != 38:
        fail(run, f"expected 38 practical/glow intensity channels, found {len(intensity)}")
    if len(uplights) != 3:
        fail(run, f"expected 3 uplight intensity channels, found {len(uplights)}")
    return {
        "intensity": intensity,
        "uplights": uplights,
        "root_pitch": one_transform_channel(seq, ROOT_LABEL, 4, run),
        "roof_pitch": one_transform_channel(seq, ROOF_LABEL, 4, run),
        "lattice_fly_z": one_transform_channel(seq, LATTICE_LABEL, 2, run),
        "ppv_weight": binding_float_channel(seq, EXPOSURE_LABEL, "BlendWeight", run),
    }


def capture_keys(channels, fps):
    return {
        "intensity": {label: keys_of(channel, fps) for label, channel in sorted(channels["intensity"].items())},
        "uplights": {label: keys_of(channel, fps) for label, channel in sorted(channels["uplights"].items())},
        "root_pitch": keys_of(channels["root_pitch"], fps),
        "roof_pitch": keys_of(channels["roof_pitch"], fps),
        "lattice_fly_z": keys_of(channels["lattice_fly_z"], fps),
        "ppv_weight": keys_of(channels["ppv_weight"], fps),
    }


def channel_names(channels):
    return {
        "intensity": {label: str(channel.get_name()) for label, channel in sorted(channels["intensity"].items())},
        "uplights": {label: str(channel.get_name()) for label, channel in sorted(channels["uplights"].items())},
        "root_pitch": str(channels["root_pitch"].get_name()),
        "roof_pitch": str(channels["roof_pitch"].get_name()),
        "lattice_fly_z": str(channels["lattice_fly_z"].get_name()),
        "ppv_weight": str(channels["ppv_weight"].get_name()),
    }


def apply_key_set(channels, planned, fps):
    linear = unreal.MovieSceneKeyInterpolation.LINEAR
    auto = unreal.MovieSceneKeyInterpolation.AUTO
    for label, keys in planned["intensity"].items():
        set_keys(channels["intensity"][label], keys, fps, linear)
    for label, keys in planned["uplights"].items():
        set_keys(channels["uplights"][label], keys, fps, linear)
    set_keys(channels["root_pitch"], planned["root_pitch"], fps, auto)
    set_keys(channels["roof_pitch"], planned["roof_pitch"], fps, auto)
    set_keys(channels["lattice_fly_z"], planned["lattice_fly_z"], fps, auto)
    set_keys(channels["ppv_weight"], planned["ppv_weight"], fps, auto)


def mismatches(channels, expected, fps):
    got = capture_keys(channels, fps)
    bad = []
    for group in ("intensity", "uplights"):
        for label, wanted in expected[group].items():
            if label not in got[group] or not keys_match(got[group][label], wanted, fps):
                bad.append(f"{group}:{label}")
    for name in ("root_pitch", "roof_pitch", "lattice_fly_z", "ppv_weight"):
        if not keys_match(got[name], expected[name], fps):
            bad.append(name)
    return bad


def read_window(run):
    if not os.path.exists(WINDOW_RECORD):
        fail(run, f"missing timing authority {WINDOW_RECORD}")
    data = json.load(open(WINDOW_RECORD, encoding="utf-8"))
    plan = data.get("plan")
    if not isinstance(plan, dict):
        fail(run, "p04_backcloth_section_record.json has no plan object")
    if plan.get("lead_s") != 5.0:
        fail(run, f"expected plan.lead_s 5.0, found {plan.get('lead_s')!r}")
    W0, W1 = plan.get("cloth_release_s"), plan.get("section_end_s")
    if W0 is None or W1 is None:
        fail(run, f"timing authority is missing cloth_release_s or section_end_s: {W0!r}, {W1!r}")
    W0, W1 = float(W0), float(W1)
    if W0 >= 0.0 or W1 <= 0.0:
        fail(run, f"invalid cloth window W0={W0}, W1={W1}")
    return W0, W1


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    apply = bool(globals().get("S4REKEY_APPLY"))
    revert = bool(globals().get("S4REKEY_REVERT"))
    if apply and revert:
        fail(run, "apply and revert modes are mutually exclusive")

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or editor.get_game_world() is not None:
        fail(run, "wrong world, or PIE")
    W0, W1 = read_window(run)
    seq = unreal.load_asset(SEQ)
    if seq is None:
        fail(run, f"sequence did not load: {SEQ}")
    rate = seq.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    channels = discover_channels(seq, run)
    before = capture_keys(channels, fps)
    planned = plan_keys(before, W0, W1)
    names = channel_names(channels)
    playback = [float(seq.get_playback_start_seconds()), float(seq.get_playback_end_seconds())]
    unreal.log(
        f"S4REKEY_PLAN|run={run}|W0={W0}|W1={W1}|delta={round(W1 - CURRENT_LANDING_S, 6)}|"
        f"playback={playback}|channel_names={json.dumps(names, sort_keys=True)}|after={json.dumps(planned, sort_keys=True)}"
    )
    if not (apply or revert):
        unreal.log(f"S4REKEY_DRY_RUN_OK|run={run}|mutated=0|{json.dumps(package_census(), sort_keys=True)}")
        return

    census_before = package_census()
    if census_before["dirty_maps"] or census_before["dirty_content"]:
        fail(run, f"packages already dirty: {census_before}")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail(run, "Sequencer is open")

    if revert:
        if not os.path.exists(RECORD):
            fail(run, "revert record is absent")
        record = json.load(open(RECORD, encoding="utf-8"))
        drift = mismatches(channels, record["after"], fps)
        if drift:
            fail(run, f"revert refused: live keys do not match the recorded applied state: {drift[:8]}")
        apply_key_set(channels, record["before"], fps)
        bad = mismatches(channels, record["before"], fps)
        if bad:
            fail(run, f"revert read-back failed before save: {bad[:8]} (sequence NOT saved)")
        if [float(seq.get_playback_start_seconds()), float(seq.get_playback_end_seconds())] != record["playback_before"]:
            fail(run, "playback range changed during revert (sequence NOT saved)")
        if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
            fail(run, "sequence save failed")
        os.replace(RECORD, RECORD + ".reverted")
        unreal.log(f"S4REKEY_OK|run={run}|reverted|{json.dumps(package_census(), sort_keys=True)}")
        return

    if os.path.exists(RECORD):
        fail(run, "already applied (record exists); revert first")
    stamp = datetime.datetime.now()
    record = {
        "written": stamp.isoformat(timespec="seconds"),
        "run": run,
        "timing_source": os.path.basename(WINDOW_RECORD),
        "W0": W0,
        "W1": W1,
        "fps": fps,
        "playback_before": playback,
        "channel_names": names,
        "before": before,
        "after": planned,
    }
    with open(RECORD, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=1, sort_keys=True)
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreS4RekeyWindow-" + stamp.strftime("%Y%m%d-%H%M"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project, "Content", *SEQ[len("/Game/"):].split("/")) + ".uasset", backup)
    shutil.copy2(RECORD, backup)

    apply_key_set(channels, planned, fps)
    bad = mismatches(channels, planned, fps)
    if bad:
        fail(run, f"apply read-back failed before save: {bad[:8]} (sequence NOT saved)")
    if [float(seq.get_playback_start_seconds()), float(seq.get_playback_end_seconds())] != playback:
        fail(run, "playback range changed during apply (sequence NOT saved)")
    if not unreal.EditorAssetLibrary.save_asset(SEQ, only_if_is_dirty=False):
        fail(run, "sequence save failed")
    unreal.log(
        f"S4REKEY_OK|run={run}|applied|channels={38 + 3 + 4}|backup={backup}|"
        f"{json.dumps(package_census(), sort_keys=True)}"
    )


if unreal is not None:
    main()
