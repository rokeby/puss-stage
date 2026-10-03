"""Independent saved/live read-back for the S3 split-wave pass."""
import json
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
RECORD_PATH = "E:/PussStage/Saved/CodexConductor/s3_wave_split_record.json"
REPORT_PATH = "E:/PussStage/Saved/CodexConductor/s3_wave_split_readback.json"
TAG = "RigAtmos.S3WaveSplit"
ORIGINALS = tuple("S3 Wave Row%d %s" % (row, side) for row in (1, 2, 3) for side in ("A", "B"))
CHANNELS = ("Location.X", "Location.Y", "Location.Z",
            "Rotation.X", "Rotation.Y", "Rotation.Z", "Scale.X", "Scale.Y", "Scale.Z")
SEAM = (3480, 4200)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def package_name(value):
    return str(value.get_name()).split(".", 1)[0]


def census():
    return {"maps": sorted(package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": sorted(package_name(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def guid(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value))


def frame(value):
    if hasattr(value, "frame_number"):
        return int(value.frame_number.value)
    return int(value.value if hasattr(value, "value") else value)


def canonical(channel):
    try:
        name = str(channel.get_name())
    except Exception:
        name = str(channel.get_editor_property("channel_name"))
    name = re.sub(r"_\d+$", "", name)
    return name if name in CHANNELS else None


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
world = editor.get_editor_world()
require(world is not None and str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_WORLD")
before = census()
require(before == {"maps": [], "content": []}, "DIRTY_BEFORE|" + json.dumps(before, sort_keys=True))
require(os.path.isfile(RECORD_PATH), "RECORD_MISSING")
with open(RECORD_PATH, encoding="utf-8") as handle:
    record = json.load(handle)
plan = record.get("plan", {})
require(record.get("applied") is True and record.get("world") == EXPECTED_WORLD
        and record.get("asset") == SEQUENCE_PATH, "RECORD_CONTEXT")
require(os.path.isdir(record.get("backup", "")), "BACKUP_MISSING")
require(plan.get("piece_count") == 9 and len(plan.get("pieces", [])) == 9, "PLAN_PIECE_COUNT")
require(plan.get("worst_gap_cm") == 0.0 and plan.get("inside_box_guard") is True, "PLAN_COVERAGE")
require(plan.get("vamp_range") == list(SEAM), "PLAN_SEAM_RANGE")
require(all(float(piece.get("seam_error_cm", 1.0)) <= 0.01 for piece in plan["pieces"]), "PLAN_SEAM_ERROR")

sequence = unreal.load_asset(SEQUENCE_PATH)
require(isinstance(sequence, unreal.LevelSequence), "SEQUENCE_MISSING")
by_guid = {guid(binding.get_id()): binding for binding in sequence.get_bindings()}
actor_index = {}
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    actor_index.setdefault(str(actor.get_actor_label()), []).append(actor)

for row in record["originals"]:
    actors = actor_index.get(row["label"], [])
    require(len(actors) == 1 and str(actors[0].get_path_name()) == row["actor_path"],
            "ORIGINAL_IDENTITY|label=" + row["label"])
    component = actors[0].get_component_by_class(unreal.StaticMeshComponent)
    require(bool(actors[0].is_hidden()) and component is not None and not bool(component.is_visible()),
            "ORIGINAL_VISIBILITY|label=" + row["label"])
require({row["label"] for row in record["originals"]} == set(ORIGINALS), "ORIGINAL_SET")

piece_rows = []
for created in record["created"]:
    actors = actor_index.get(created["label"], [])
    require(len(actors) == 1 and str(actors[0].get_path_name()) == created["actor_path"],
            "PIECE_IDENTITY|label=" + created["label"])
    require(TAG in [str(value) for value in actors[0].tags], "PIECE_TAG|label=" + created["label"])
    binding = by_guid.get(created["binding_guid"])
    require(binding is not None, "PIECE_BINDING|label=" + created["label"])
    tracks = list(binding.find_tracks_by_type(unreal.MovieScene3DTransformTrack))
    require(len(tracks) == 1 and len(tracks[0].get_sections()) == 1,
            "PIECE_TRACK|label=" + created["label"])
    channels = {canonical(channel): channel for channel in tracks[0].get_sections()[0].get_all_channels()
                if canonical(channel)}
    require(set(channels) == set(CHANNELS), "PIECE_CHANNELS|label=" + created["label"])
    seam_values = {}
    key_count = None
    for name in CHANNELS[:6]:
        keys = sorted(channels[name].get_keys(), key=lambda key: frame(key.get_time()))
        frames = [frame(key.get_time()) for key in keys]
        require(SEAM[0] in frames and SEAM[1] in frames, "SEAM_KEYS|label=%s|channel=%s" % (created["label"], name))
        values = {frame(key.get_time()): float(key.get_value()) for key in keys}
        require(abs(values[SEAM[0]] - values[SEAM[1]]) <= 0.001,
                "SEAM_VALUE|label=%s|channel=%s" % (created["label"], name))
        seam_values[name] = [values[SEAM[0]], values[SEAM[1]]]
        key_count = len(keys) if key_count is None else key_count
        require(len(keys) == key_count, "KEY_COUNT_CHANNEL_DRIFT|label=" + created["label"])
    require(key_count == created["key_count"], "KEY_COUNT_RECORD|label=" + created["label"])
    piece_rows.append({"label": created["label"], "binding_guid": created["binding_guid"],
                       "key_count": key_count, "seam_values": seam_values})

require(len(piece_rows) == 9 and {row["label"] for row in piece_rows} ==
        {piece["label"] for piece in plan["pieces"]}, "LIVE_PIECE_SET")
after = census()
require(after == before, "READBACK_DIRTIED|" + json.dumps(after, sort_keys=True))
report = {"status": "saved_live_readback_verified", "backup": record["backup"],
          "pieces": piece_rows, "piece_count": 9, "original_count": 6,
          "coverage": {"worst_gap_cm": plan["worst_gap_cm"], "inside_box_guard": True,
                       "piece_width_fraction": plan["piece_width_fraction"]},
          "vamp_seam_frames": list(SEAM), "vamp_seam_equal_live_channels": True,
          "period_seconds": plan["period_seconds"], "census": after}
with open(REPORT_PATH, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
unreal.log("S3_WAVE_SPLIT_READBACK_OK|pieces=9|originals_hidden=6|coverage_worst_gap_cm=0|period_s=15|vamp_seam=3480/4200_equal|census=clean|output=%s" % REPORT_PATH)
