"""Read-only census of HangarRise light Intensity keys for S1-S6."""
import importlib
import json
import math
import os
import sys

import unreal


# Purge every cached module whose source is under this project's Saved tree
# before doing any task work.  This script imports no project-local module.
SAVED_ROOT = os.path.normcase(os.path.abspath(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())))
PURGED_MODULES = []
for module_name, module in list(sys.modules.items()):
    source = getattr(module, "__file__", None)
    if source and os.path.normcase(os.path.abspath(source)).startswith(SAVED_ROOT + os.sep):
        sys.modules.pop(module_name, None)
        PURGED_MODULES.append(module_name)
importlib.invalidate_caches()
unreal.log("SAVED_MODULE_CACHE_PURGED|count=%d|modules=%s" %
           (len(PURGED_MODULES), ",".join(sorted(PURGED_MODULES))))


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE_TEMPLATE = "/Game/InfinityStage/RigAtmos/LS_S%d_HangarRise"
OUTPUT_PATH = os.path.join(SAVED_ROOT, "CodexConductor", "hangar_light_keys_probe.json")
VALUE_TOLERANCE = 1.0e-6


def census():
    return {
        "content": sorted(
            package.get_name().split(".", 1)[0]
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
        "maps": sorted(
            package.get_name().split(".", 1)[0]
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    }


def key_row(key, tick_rate):
    when = key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
    frame = int(when.frame_number.value)
    sub_frame = float(getattr(when, "sub_frame", 0.0))
    return {
        "seconds": (frame + sub_frame) / tick_rate,
        "value": float(key.get_value()),
    }


def ramp_starts(keys):
    return [
        keys[index]["seconds"]
        for index in range(len(keys) - 1)
        if abs(keys[index]["value"]) <= VALUE_TOLERANCE
        and keys[index + 1]["value"] > VALUE_TOLERANCE
    ]


def fmt_seconds(value):
    if value is None:
        return "null"
    return ("%.9f" % value).rstrip("0").rstrip(".")


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() is not None:
        raise RuntimeError("HANGAR_LIGHT_KEYS_STOPPED|reason=PIE_OR_SIE_ACTIVE")
    world_path = world.get_outermost().get_name() if world is not None else None
    if world_path != EXPECTED_WORLD:
        raise RuntimeError("HANGAR_LIGHT_KEYS_STOPPED|reason=WRONG_WORLD|actual=%s" % world_path)

    initial = census()
    expected_dirty = {"content": [], "maps": []}
    if initial != expected_dirty:
        raise RuntimeError(
            "HANGAR_LIGHT_KEYS_STOPPED|reason=UNEXPECTED_DIRTY_CENSUS|expected=%s|actual=%s" % (
                json.dumps(expected_dirty, separators=(",", ":"), sort_keys=True),
                json.dumps(initial, separators=(",", ":"), sort_keys=True)))

    hangars = []
    summary_lines = []
    for scene in range(1, 7):
        sequence_path = SEQUENCE_TEMPLATE % scene
        sequence = unreal.load_asset(sequence_path)
        if sequence is None or not isinstance(sequence, unreal.LevelSequence):
            raise RuntimeError(
                "HANGAR_LIGHT_KEYS_STOPPED|reason=SEQUENCE_MISSING|asset=%s" % sequence_path)
        tick = sequence.get_tick_resolution()
        tick_rate = float(tick.numerator) / float(tick.denominator)
        if not math.isfinite(tick_rate) or tick_rate <= 0.0:
            raise RuntimeError(
                "HANGAR_LIGHT_KEYS_STOPPED|reason=INVALID_TICK_RATE|asset=%s" % sequence_path)

        prefixes = {
            "uplight": "S%d Uplight " % scene,
            "practical": "S%d Practical " % scene,
            "glow": "S%d Lattice Glow " % scene,
        }
        if scene == 3:
            prefixes["strike"] = "S3 Strike "

        labels = {}
        families = {}
        for binding in sequence.get_bindings():
            parent = binding.get_parent()
            parent_name = str(parent.get_display_name()) if parent and parent.is_valid() else ""
            own_name = str(binding.get_display_name())
            label = next(
                (candidate for candidate in (parent_name, own_name)
                 if any(candidate.startswith(prefix) for prefix in prefixes.values())),
                None)
            if label is None:
                continue

            channels = []
            for track in binding.get_tracks():
                if (isinstance(track, unreal.MovieSceneFloatTrack)
                        and str(track.get_property_name()) == "Intensity"):
                    for section in track.get_sections():
                        channels.extend(section.get_all_channels())
            if not channels:
                continue
            if len(channels) != 1 or label in labels:
                raise RuntimeError(
                    "HANGAR_LIGHT_KEYS_STOPPED|reason=NON_UNIQUE_INTENSITY_CHANNEL|asset=%s|label=%s|channels=%d" %
                    (sequence_path, label, len(channels)))

            keys = sorted(
                list(channels[0].get_keys()),
                key=lambda key: (
                    key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value,
                    float(getattr(
                        key.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION),
                        "sub_frame", 0.0)),
                ))
            labels[label] = [key_row(key, tick_rate) for key in keys]
            families[label] = next(
                family for family, prefix in prefixes.items() if label.startswith(prefix))

        for required in ("uplight", "practical", "glow"):
            if required not in families.values():
                raise RuntimeError(
                    "HANGAR_LIGHT_KEYS_STOPPED|reason=FAMILY_MISSING|asset=%s|family=%s" %
                    (sequence_path, required))

        family_ramps = {}
        for family in prefixes:
            starts = sorted({
                start
                for label, keys in labels.items()
                if families[label] == family
                for start in ramp_starts(keys)
            })
            family_ramps[family] = starts

        uplight_strikes = family_ramps["uplight"]
        practical_first = (family_ramps["practical"][0]
                           if family_ramps["practical"] else None)
        glow_first = family_ramps["glow"][0] if family_ramps["glow"] else None
        strike_lights = sum(1 for family in families.values() if family == "strike")
        line = (
            "HANGAR_LIGHTS|S%d|uplight_strike_s=[%s]|practical_first_ramp_s=%s|"
            "glow_first_ramp_s=%s|strike_lights=%d" % (
                scene,
                ",".join(fmt_seconds(value) for value in uplight_strikes),
                fmt_seconds(practical_first),
                fmt_seconds(glow_first),
                strike_lights))
        summary_lines.append(line)
        hangars.append({
            "scene": scene,
            "asset": sequence_path,
            "tick_rate": tick_rate,
            "channels": [
                {"label": label, "family": families[label], "keys": labels[label]}
                for label in sorted(labels)
            ],
            "summary": {
                "uplight_strike_s": uplight_strikes,
                "practical_first_ramp_s": practical_first,
                "glow_first_ramp_s": glow_first,
                "strike_lights": strike_lights,
            },
            "summary_line": line,
        })

    before_output = census()
    if before_output != initial:
        raise RuntimeError(
            "HANGAR_LIGHT_KEYS_STOPPED|reason=CENSUS_CHANGED_BEFORE_OUTPUT|initial=%s|actual=%s" % (
                json.dumps(initial, separators=(",", ":"), sort_keys=True),
                json.dumps(before_output, separators=(",", ":"), sort_keys=True)))

    report = {
        "world": world_path,
        "purged_saved_modules": sorted(PURGED_MODULES),
        "initial_census": initial,
        "final_census": initial,
        "hangars": hangars,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)

    final = census()
    if final != initial:
        raise RuntimeError(
            "HANGAR_LIGHT_KEYS_STOPPED|reason=FINAL_CENSUS_CHANGED|initial=%s|actual=%s" % (
                json.dumps(initial, separators=(",", ":"), sort_keys=True),
                json.dumps(final, separators=(",", ":"), sort_keys=True)))
    for line in summary_lines:
        unreal.log(line)
    unreal.log(
        "HANGAR_LIGHT_KEYS_PROBE_OK|hangars=6|output=%s|census=%s" % (
            OUTPUT_PATH,
            json.dumps(final, separators=(",", ":"), sort_keys=True)))


main()
