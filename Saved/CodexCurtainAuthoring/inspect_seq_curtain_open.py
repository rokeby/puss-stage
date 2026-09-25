import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE_PATH = "/Game/Seq_CurtainOpen"


def object_path(value):
    if value is None:
        return ""
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def editor_property(value, name):
    try:
        result = value.get_editor_property(name)
        return object_path(result) if hasattr(result, "get_path_name") else str(result)
    except Exception as exc:
        return f"<unavailable: {exc}>"


def frame_number(value):
    try:
        return int(value.value)
    except Exception:
        try:
            return int(value)
        except Exception:
            return str(value)


def safe_frame(section, method_name):
    try:
        return frame_number(getattr(section, method_name)())
    except Exception as exc:
        return f"<unbounded: {exc}>"


def key_row(key):
    row = {}
    for label, method in (("time", "get_time"), ("value", "get_value")):
        try:
            value = getattr(key, method)()
            row[label] = frame_number(value) if label == "time" else str(value)
        except Exception as exc:
            row[f"{label}_error"] = str(exc)
    return row


def channel_row(channel):
    row = {"class": channel.get_class().get_name()}
    try:
        row["keys"] = [key_row(key) for key in channel.get_keys()]
    except Exception as exc:
        row["keys_error"] = str(exc)
    return row


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
world_path = object_path(world).split(".", 1)[0]
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")

dirty_content = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if dirty_content or dirty_maps:
    raise RuntimeError(f"Inspection requires a clean editor: content={dirty_content}, maps={dirty_maps}")

sequence = unreal.load_asset(SEQUENCE_PATH)
if not sequence:
    raise RuntimeError(f"Missing sequence: {SEQUENCE_PATH}")

bindings = []
for binding in sequence.get_bindings():
    binding_row = {
        "name": binding.get_name(),
        "resolved_objects": [],
        "tracks": [],
    }
    try:
        binding_id = binding.get_id()
        binding_row["resolved_objects"] = [
            object_path(value) for value in sequence.locate_bound_objects(binding_id, world)
        ]
    except Exception as exc:
        binding_row["resolve_error"] = str(exc)
    for track in binding.get_tracks():
        track_row = {
            "class": track.get_class().get_name(),
            "display_name": str(track.get_display_name()),
            "sections": [],
        }
        for section in track.get_sections():
            section_row = {
                "class": section.get_class().get_name(),
                "start_frame": safe_frame(section, "get_start_frame"),
                "end_frame": safe_frame(section, "get_end_frame"),
                "channels": [],
            }
            try:
                section_row["channels"] = [channel_row(channel) for channel in section.get_channels()]
            except Exception as exc:
                section_row["channels_error"] = str(exc)
            for property_name in (
                "params",
                "animation",
                "play_rate",
                "reverse",
                "start_offset",
                "end_offset",
                "first_loop_start_frame_offset",
            ):
                section_row[property_name] = editor_property(section, property_name)
            track_row["sections"].append(section_row)
        binding_row["tracks"].append(track_row)
    bindings.append(binding_row)

payload = {
    "status": "ok",
    "world": world_path,
    "sequence": SEQUENCE_PATH,
    "bindings": bindings,
    "dirty_content": dirty_content,
    "dirty_maps": dirty_maps,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_seq_curtain_open.json",
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_OPEN_INSPECT_SUCCESS"
    f"|bindings={len(bindings)}|dirty_content=0|dirty_maps=0"
)
