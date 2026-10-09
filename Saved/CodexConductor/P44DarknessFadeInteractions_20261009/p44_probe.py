"""Read-only P44 census for F4, F5 and I1/I3/I4/I5.

This script never opens Sequencer, starts PIE, modifies a UObject, or saves a
package. It writes only a JSON evidence report under project Saved and proves
the exact dirty-package census is unchanged.
"""
import datetime
import hashlib
import json
import math
import os

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
S1 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
INTERACTIONS = {
    1: "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy",
    2: "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips",
    3: "/Game/InfinityStage/Interactions/LS_Interaction_03_ForgetsHisName",
    4: "/Game/InfinityStage/Interactions/LS_Interaction_04_GetsAName",
    5: "/Game/InfinityStage/Interactions/LS_Interaction_05_BecomesKing",
}
CARD_NAMES = ("Sleight Hangar Shadow Card", "Sleight Mouth Shadow Card")
SPOT_NAMES = ("Shadow Play Spot (Hangar)", "Shadow Play Spot (Mouth)")
S1_PREFIXES = ("Klara Hookin - Ours Off: ", "Klara Reveal - Hide: ")


class ProbeError(RuntimeError):
    pass


def asset_path(value):
    if value is None:
        return ""
    try:
        value = value.get_path_name()
    except Exception:  # noqa: BLE001
        pass
    return str(value).split(".", 1)[0]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def map_master_time(review_seconds, start_seconds, end_seconds, fps):
    review, start, end, rate = map(float, (review_seconds, start_seconds, end_seconds, fps))
    if rate <= 0.0:
        raise ProbeError("NONPOSITIVE_FPS")
    if not start <= review < end:
        raise ProbeError("REVIEW_OUTSIDE_SECTION")
    exact = (review - start) * rate
    return {"review_seconds": review, "section_start_seconds": start, "section_end_seconds": end,
            "scene_fps": rate, "scene_frame_exact": exact,
            "scene_frame": int(math.floor(exact + 0.5)), "rounding": "nearest_display_frame_half_up"}


def visibility_summary(rows):
    summary = {"bHidden": 0, "bHiddenInGame": 0, "None": 0, "other": 0}
    for row in rows:
        prop = str(row.get("property") or "None")
        summary[prop if prop in summary else "other"] += 1
    summary["needs_f4_apply"] = summary["bHiddenInGame"] > 0
    summary["f4_already_fixed"] = summary["bHiddenInGame"] == 0 and summary["bHidden"] > 0
    return summary


def inventory_labels(labels):
    names = list(labels)
    return {name: {"count": names.count(name), "state": "present" if names.count(name) else "missing"}
            for name in CARD_NAMES + SPOT_NAMES}


def _rate(value):
    return float(value.numerator) / float(getattr(value, "denominator", 1) or 1)


def _frame(value):
    try:
        return int(value.value)
    except Exception:  # noqa: BLE001
        return int(value)


def _range(section):
    return [_frame(section.get_start_frame()), _frame(section.get_end_frame())]


def _track_property(track):
    try:
        return str(track.get_property_name()), str(track.get_property_path())
    except Exception:  # noqa: BLE001
        return "", ""


def _guid(value):
    try:
        return unreal.GuidLibrary.conv_guid_to_string(value)
    except Exception:  # noqa: BLE001
        return str(value)


def _enum(value):
    return str(getattr(value, "name", value)).split(".")[-1].split(":")[0].strip("<> ")


def _channel(channel):
    row = {"name": str(getattr(channel, "channel_name", "")), "has_default": False, "default": None, "keys": []}
    try:
        row["has_default"] = bool(channel.has_default())
        row["default"] = channel.get_default() if row["has_default"] else None
    except Exception:  # noqa: BLE001
        pass
    for key in channel.get_keys():
        time = key.get_time(time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
        item = {"frame": _frame(time.frame_number), "sub_frame": float(time.sub_frame)}
        try:
            item["value"] = key.get_value()
        except Exception:  # noqa: BLE001
            item["value"] = None
        try:
            item["interp"] = _enum(key.get_interpolation_mode())
        except Exception:  # noqa: BLE001
            item["interp"] = None
        row["keys"].append(item)
    return row


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(asset_path(p) for p in lib.get_dirty_content_packages()),
            "maps": sorted(asset_path(p) for p in lib.get_dirty_map_packages())}


def _master_table(master):
    rows = []
    for track in master.get_tracks():
        for section in track.get_sections():
            try:
                child = section.get_sequence()
            except Exception:  # noqa: BLE001
                continue
            path = asset_path(child)
            if not path:
                continue
            rows.append({"track_class": track.get_class().get_name(), "sequence": path,
                         "start_seconds": float(section.get_start_frame_seconds()),
                         "end_seconds": float(section.get_end_frame_seconds()), "range": _range(section)})
    return sorted(rows, key=lambda row: (row["start_seconds"], row["sequence"]))


def _s1_visibility(seq):
    rows = []
    for binding in seq.get_bindings():
        label = str(binding.get_display_name())
        for track in binding.get_tracks():
            if track.get_class().get_name() != "MovieSceneVisibilityTrack":
                continue
            prop, path = _track_property(track)
            rows.append({"binding": label, "guid": _guid(binding.get_id()), "property": prop,
                         "property_path": path, "is_p44_prefix": label.startswith(S1_PREFIXES),
                         "sections": [{"range": _range(section),
                                       "active": bool(section.is_active()),
                                       "channels": [_channel(c) for c in section.get_all_channels()]}
                                      for section in track.get_sections()]})
    return rows


def _light_function(binding):
    try:
        template = binding.get_object_template()
        component = template.get_editor_property("spot_light_component")
        return asset_path(component.get_editor_property("light_function_material")) or None
    except Exception as error:  # noqa: BLE001
        return "UNREADABLE:%s" % type(error).__name__


def _interaction(seq, number):
    bindings = list(seq.get_bindings())
    labels = [str(binding.get_display_name()) for binding in bindings]
    detail = inventory_labels(labels)
    for name in SPOT_NAMES:
        hits = [binding for binding in bindings if str(binding.get_display_name()) == name]
        if len(hits) == 1:
            detail[name]["light_function_material"] = _light_function(hits[0])
    return {"interaction": number, "sequence": INTERACTIONS[number], "display_rate": _rate(seq.get_display_rate()),
            "playback": [_frame(seq.get_playback_start()), _frame(seq.get_playback_end())],
            "inventory": detail, "binding_count": len(bindings)}


def run(args):
    if unreal is None:
        raise ProbeError("UNREAL_REQUIRED")
    confirm = str(args.get("confirm") or "")
    run_id = str(args.get("run_id") or datetime.datetime.now().strftime("P44PROBE-%Y%m%d-%H%M%S"))
    if confirm != "PROBE P44":
        raise ProbeError("CONFIRM_MISMATCH")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        raise ProbeError("PIE_OR_SIE_ACTIVE")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise ProbeError("SEQUENCER_IS_OPEN")
    world = editor.get_editor_world()
    if world is None or asset_path(world.get_outermost()) != EXPECTED_WORLD:
        raise ProbeError("WRONG_WORLD|%s" % (asset_path(world.get_outermost()) if world else "None"))
    before = _census()
    if before != {"content": [], "maps": []}:
        raise ProbeError("DIRTY_CENSUS|%r" % before)
    master = unreal.load_asset(MASTER)
    s1 = unreal.load_asset(S1)
    if master is None or s1 is None:
        raise ProbeError("SEQUENCE_LOAD_FAILED")
    table = _master_table(master)
    s1_rows = [row for row in table if row["sequence"] == S1]
    if len(s1_rows) != 1:
        raise ProbeError("S1_MASTER_SECTION_COUNT|%d" % len(s1_rows))
    clock = map_master_time(args.get("review_time_seconds", 224.0), s1_rows[0]["start_seconds"],
                            s1_rows[0]["end_seconds"], _rate(s1.get_display_rate()))
    visibility = _s1_visibility(s1)
    interactions = []
    for number in (1, 2, 3, 4, 5):
        seq = unreal.load_asset(INTERACTIONS[number])
        if seq is None:
            raise ProbeError("INTERACTION_LOAD_FAILED|I%d" % number)
        interactions.append(_interaction(seq, number))
    after = _census()
    if after != before:
        raise ProbeError("PROBE_DIRTIED|before=%r|after=%r" % (before, after))
    report = {"schema_version": 1, "tool": "P44_PROBE", "run": run_id, "mutated": False,
              "dirty_before": before, "dirty_after": after, "master_section_table": table,
              "f5_master_mapping": clock, "f4_visibility_tracks": visibility,
              "f4_summary": visibility_summary(visibility), "interactions": interactions,
              "claims": [
                  {"tier": "measured", "claim": "This report is a live read-only sequence census.",
                   "cite": "this JSON; dirty_before equals dirty_after"},
                  {"tier": "inferred", "claim": "Track structure does not prove rendered darkness or gobo appearance.",
                   "cite": "rendered review remains required"}]}
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "p44_probe_%s.json" % run_id)
    with open(path + ".tmp", "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, default=str)
    os.replace(path + ".tmp", path)
    unreal.log("P44_PROBE_OK|run=%s|mutated=0|dirty=0|s1_frame=%d|f4_inert=%d|report=%s" %
               (run_id, clock["scene_frame"], report["f4_summary"]["bHiddenInGame"], path))
    return report


if unreal is not None:
    run(dict(globals().get("P44_PROBE_ARGS") or {}))
