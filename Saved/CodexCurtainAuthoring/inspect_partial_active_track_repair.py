import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
INTERACTION_DIR = "/Game/InfinityStage/Interactions"
SEQUENCE_NAMES = [
    "LS_Interaction_Template",
    "LS_Opening_Curtain",
    "LS_Interaction_01_WashingTheBoy",
    "LS_Interaction_02_Turnips",
    "LS_Interaction_03_ForgetsHisName",
    "LS_Interaction_04_GetsAName",
    "LS_Interaction_05_BecomesKing",
    "LS_Closing_Curtain",
]


def object_path(value):
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def frame_value(value):
    if hasattr(value, "frame_number"):
        value = value.frame_number
    if hasattr(value, "value"):
        value = value.value
    return int(value)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world_path = object_path(editor.get_editor_world()).split(".", 1)[0]
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")

rows = []
for name in SEQUENCE_NAMES:
    path = f"{INTERACTION_DIR}/{name}"
    sequence = unreal.load_asset(path)
    bindings = list(sequence.get_bindings()) if sequence else []
    row = {"path": path, "binding_count": len(bindings), "tracks": []}
    if bindings:
        for track in bindings[0].get_tracks():
            track_row = {
                "class": track.get_class().get_name(),
                "property_name": "",
                "property_path": "",
                "sections": [],
            }
            if track_row["class"] in ("MovieSceneFloatTrack", "MovieSceneBoolTrack"):
                track_row["property_name"] = str(track.get_property_name())
                track_row["property_path"] = str(track.get_property_path())
            for section in track.get_sections():
                section_row = {
                    "range": [],
                    "channels": [],
                }
                try:
                    section_row["range"] = [
                        frame_value(section.get_start_frame()),
                        frame_value(section.get_end_frame()),
                    ]
                except Exception:
                    section_row["range"] = None
                for channel in section.get_all_channels():
                    channel_row = {
                        "class": channel.get_class().get_name(),
                        "default": bool(channel.get_default())
                        if hasattr(channel, "has_default") and channel.has_default()
                        else None,
                        "keys": [],
                    }
                    for key in channel.get_keys():
                        channel_row["keys"].append(
                            [
                                frame_value(
                                    key.get_time(
                                        unreal.MovieSceneTimeUnit.DISPLAY_RATE
                                    )
                                ),
                                key.get_value(),
                            ]
                        )
                    section_row["channels"].append(channel_row)
                track_row["sections"].append(section_row)
            row["tracks"].append(track_row)
    rows.append(row)

dirty_content = [
    str(value.get_name())
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
]
dirty_maps = [
    str(value.get_name())
    for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
]
payload = {
    "status": "ok",
    "world": world_path,
    "rows": rows,
    "dirty_content": dirty_content,
    "dirty_maps": dirty_maps,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_partial_active_track_repair.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_PARTIAL_ACTIVE_TRACK_INSPECTED"
    f"|dirty_content={len(dirty_content)}|dirty_maps={len(dirty_maps)}"
)
