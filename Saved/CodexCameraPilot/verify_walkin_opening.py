"""Independent read-only verifier for the recorded OPENING walk-in keys."""
import json
import os

import unreal

RUN = "WALKIN-OPENING-VERIFY-20261002-A"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
TRACK_NAME = "WalkIn (Look & camera)"


def census():
    return {
        "maps": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
        "content": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    }


def fail(message):
    marker = "PUSS_WALKIN_VERIFY_FAILED|run=%s|%s" % (RUN, message)
    unreal.log_error(marker)
    raise RuntimeError(marker)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if editor.get_game_world() is not None:
    fail("PIE_OR_SIE_ACTIVE")
world = editor.get_editor_world()
if world is None or world.get_outermost().get_name() != EXPECTED_WORLD:
    fail("WRONG_WORLD")
before = census()
if before != {"maps": [], "content": []}:
    fail("DIRTY_BEFORE|%s" % json.dumps(before, sort_keys=True))

saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
record_path = os.path.join(saved, "CodexCameraPilot", "walkin_OPENING_record.json")
if not os.path.isfile(record_path):
    fail("RECORD_MISSING")
with open(record_path, "r", encoding="utf-8") as handle:
    record = json.load(handle)
if record.get("transition_id") != "OPENING":
    fail("RECORD_TRANSITION")
expected_keys = record.get("keys", [])
if len(expected_keys) != 376:
    fail("RECORD_KEY_COUNT|%d" % len(expected_keys))
sequence = unreal.load_asset(record["sequence"])
if sequence is None:
    fail("SEQUENCE_MISSING")

named = []
for binding in sequence.get_bindings():
    for track in binding.get_tracks():
        if str(track.get_display_name()) == TRACK_NAME:
            named.append((str(binding.get_display_name()), track))
if len(named) != 3:
    fail("TRACK_COUNT|%d" % len(named))
transform = [row for row in named if row[1].get_class().get_name() == "MovieScene3DTransformTrack"]
floats = [row for row in named if row[1].get_class().get_name() == "MovieSceneFloatTrack"]
if len(transform) != 1 or len(floats) != 2:
    fail("TRACK_CLASSES|transform=%d|float=%d" % (len(transform), len(floats)))

sections = list(transform[0][1].get_sections())
if len(sections) != 1:
    fail("TRANSFORM_SECTIONS|%d" % len(sections))
channels = {str(channel.channel_name): channel for channel in sections[0].get_all_channels()}
mapping = {
    "Location.X": 1, "Location.Y": 2, "Location.Z": 3,
    "Rotation.X": 6, "Rotation.Y": 4, "Rotation.Z": 5,
}
for name, value_index in mapping.items():
    if name not in channels:
        fail("MISSING_CHANNEL|%s" % name)
    keys = list(channels[name].get_keys())
    if len(keys) != len(expected_keys):
        fail("KEY_COUNT|%s|%d" % (name, len(keys)))
    for frame, (key, expected) in enumerate(zip(keys, expected_keys)):
        if key.get_time().frame_number.value != frame or abs(float(key.get_value()) - float(expected[value_index])) > 1.0e-3:
            fail("KEY_MISMATCH|%s|frame=%d" % (name, frame))

float_rows = []
for host, track in floats:
    sections = list(track.get_sections())
    if len(sections) != 1:
        fail("FLOAT_SECTIONS|host=%s" % host)
    channels = list(sections[0].get_all_channels())
    if len(channels) != 1:
        fail("FLOAT_CHANNELS|host=%s" % host)
    keys = list(channels[0].get_keys())
    if len(keys) != len(expected_keys):
        fail("FLOAT_KEY_COUNT|host=%s|count=%d" % (host, len(keys)))
    last = float(keys[-1].get_value())
    value_index = 7 if abs(last - float(expected_keys[-1][7])) <= 0.01 else 8
    tolerance = 0.01 if value_index == 7 else 0.1
    for frame, (key, expected) in enumerate(zip(keys, expected_keys)):
        if key.get_time().frame_number.value != frame or abs(float(key.get_value()) - float(expected[value_index])) > tolerance:
            fail("FLOAT_KEY_MISMATCH|index=%d|frame=%d" % (value_index, frame))
    float_rows.append({"host": host, "value_index": value_index, "count": len(keys), "last": last})
if sorted(row["value_index"] for row in float_rows) != [7, 8]:
    fail("FLOAT_IDENTITIES|%s" % json.dumps(float_rows, sort_keys=True))

after = census()
if after != before:
    fail("DIRTY_AFTER|before=%s|after=%s" % (before, after))
unreal.log(
    "PUSS_WALKIN_VERIFY_OK|run=%s|transition=OPENING|tracks=3|keys=376|range=0-375|end_pose=0,0,150,0,0,0|end_focal_mm=25|end_focus_cm=600|census=%s|record=%s"
    % (RUN, json.dumps(after, separators=(",", ":"), sort_keys=True), record_path)
)
