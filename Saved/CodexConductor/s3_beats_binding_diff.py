import datetime
import json
import os

import unreal


ROOT_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
RECORD = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexConductor",
    "s3_beats_record.json",
)
MISSING = "<MISSING>"


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def section_range(section):
    return [
        int(section.get_start_frame()) if section.has_start_frame() else None,
        int(section.get_end_frame()) if section.has_end_frame() else None,
    ]


def _scalar(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return float(value)
    except Exception:
        return str(value)


def channel_row(channel):
    try:
        name = str(channel.get_name())
    except Exception:
        name = str(channel.get_editor_property("channel_name"))
    keys = []
    for key in channel.get_keys():
        time = key.get_time()
        frame = int(time.frame_number.value if hasattr(time, "frame_number") else time.value)
        keys.append([frame, _scalar(key.get_value())])
    row = {"name": name, "keys": keys}
    try:
        if channel.has_default():
            row["default"] = _scalar(channel.get_default())
    except Exception:
        pass
    return row


def track_row(track, ignore_cut_active_guid=None):
    row = {"class": track.get_class().get_name(), "name": str(track.get_display_name()), "sections": []}
    for section in track.get_sections():
        active = bool(section.is_active())
        camera_guid = None
        if isinstance(section, unreal.MovieSceneCameraCutSection):
            camera_guid = guid_text(section.get_camera_binding_id().get_editor_property("guid"))
            if camera_guid == ignore_cut_active_guid:
                active = "TARGET_IGNORED"
        row["sections"].append({
            "range": section_range(section),
            "active": active,
            "camera_guid": camera_guid,
            "channels": [channel_row(channel) for channel in section.get_all_channels()],
        })
    return row


def binding_fingerprint(sequence, only_guids=None):
    spawnables = {guid_text(binding.get_id()) for binding in sequence.get_spawnables()}
    rows = []
    for binding in sequence.get_bindings():
        identity = guid_text(binding.get_id())
        if only_guids is not None and identity not in only_guids:
            continue
        rows.append({
            "guid": identity,
            "name": str(binding.get_display_name()),
            "spawnable": identity in spawnables,
            "tracks": [track_row(track) for track in binding.get_tracks()],
        })
    return sorted(rows, key=lambda row: row["guid"])


def field_differences(before, after, field=""):
    if isinstance(before, dict) and isinstance(after, dict):
        differences = []
        for key in sorted(set(before) | set(after)):
            child = "%s.%s" % (field, key) if field else key
            if key not in before:
                differences.append((child, MISSING, after[key]))
            elif key not in after:
                differences.append((child, before[key], MISSING))
            else:
                differences.extend(field_differences(before[key], after[key], child))
        return differences
    if isinstance(before, list) and isinstance(after, list):
        differences = []
        for index in range(max(len(before), len(after))):
            child = "%s[%d]" % (field, index)
            if index >= len(before):
                differences.append((child, MISSING, after[index]))
            elif index >= len(after):
                differences.append((child, before[index], MISSING))
            else:
                differences.extend(field_differences(before[index], after[index], child))
        return differences
    return [] if before == after else [(field, before, after)]


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    with open(RECORD, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    before_rows = record["before"]["root_bindings"]
    before_by_guid = {row["guid"]: row for row in before_rows}
    root = unreal.load_asset(ROOT_PATH)
    if root is None:
        raise RuntimeError("S3_BEATS_BINDING_DIFF_FAILED|run=%s|reason=ROOT_LOAD_FAILED" % run)
    after_rows = binding_fingerprint(root, set(before_by_guid))
    after_by_guid = {row["guid"]: row for row in after_rows}
    differences = []
    for guid in sorted(set(before_by_guid) | set(after_by_guid)):
        before = before_by_guid.get(guid)
        after = after_by_guid.get(guid)
        name = (after or before or {}).get("name")
        if before is None:
            differences.append({"guid": guid, "name": name, "field": "binding", "before": MISSING, "after": after})
            continue
        if after is None:
            differences.append({"guid": guid, "name": name, "field": "binding", "before": before, "after": MISSING})
            continue
        for field, old_value, new_value in field_differences(before, after):
            differences.append({
                "guid": guid,
                "name": name,
                "field": field,
                "before": old_value,
                "after": new_value,
            })
    unreal.log("S3_BEATS_BINDING_DIFF|run=%s|%s" % (
        run,
        json.dumps(differences, separators=(",", ":"), ensure_ascii=False),
    ))


main()
