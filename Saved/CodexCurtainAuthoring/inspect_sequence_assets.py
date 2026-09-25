import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQUENCE_PATHS = [
    "/Game/Seq_CurtainOpen",
    "/Game/InfinityStage/Interactions/LS_Interaction_Template",
    "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy",
]


def object_path(value):
    if value is None:
        return ""
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def safe_call(value, method_name, default=None):
    try:
        return getattr(value, method_name)()
    except Exception:
        return default


def section_row(section):
    row = {
        "class": section.get_class().get_name(),
    }
    for label, method_name in (
        ("start_frame", "get_start_frame"),
        ("end_frame", "get_end_frame"),
        ("inclusive_start", "get_inclusive_start_frame"),
        ("exclusive_end", "get_exclusive_end_frame"),
    ):
        value = safe_call(section, method_name)
        if value is not None:
            try:
                row[label] = int(value.value)
            except Exception:
                try:
                    row[label] = int(value)
                except Exception:
                    row[label] = str(value)
    try:
        row["sequence"] = object_path(section.get_sequence())
    except Exception:
        pass
    try:
        row["export_text"] = section.export_text()[:4000]
    except Exception as exc:
        row["export_error"] = str(exc)
    return row


def track_row(track):
    row = {
        "class": track.get_class().get_name(),
        "display_name": str(safe_call(track, "get_display_name", "")),
        "sections": [],
    }
    try:
        row["sections"] = [section_row(section) for section in track.get_sections()]
    except Exception as exc:
        row["section_error"] = str(exc)
    return row


def sequence_row(path):
    sequence = unreal.load_asset(path)
    row = {"path": path, "loaded": sequence is not None}
    if sequence is None:
        return row
    row["object_path"] = object_path(sequence)
    row["class"] = sequence.get_class().get_name()
    row["playback_start"] = safe_call(sequence, "get_playback_start")
    row["playback_end"] = safe_call(sequence, "get_playback_end")
    row["display_rate"] = str(safe_call(sequence, "get_display_rate", ""))
    row["tick_resolution"] = str(safe_call(sequence, "get_tick_resolution", ""))
    row["master_tracks"] = [track_row(track) for track in safe_call(sequence, "get_tracks", [])]
    bindings = []
    for binding in safe_call(sequence, "get_bindings", []):
        binding_row = {
            "name": str(safe_call(binding, "get_name", "")),
            "display_name": str(safe_call(binding, "get_display_name", "")),
            "id": str(safe_call(binding, "get_id", "")),
            "tracks": [track_row(track) for track in safe_call(binding, "get_tracks", [])],
        }
        bindings.append(binding_row)
    row["bindings"] = bindings
    for key, method_name in (("spawnables", "get_spawnables"), ("possessables", "get_possessables")):
        values = safe_call(sequence, method_name)
        if values is not None:
            row[key] = [
                {
                    "name": str(safe_call(value, "get_name", "")),
                    "display_name": str(safe_call(value, "get_display_name", "")),
                    "id": str(safe_call(value, "get_id", "")),
                }
                for value in values
            ]
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

registry = unreal.AssetRegistryHelpers.get_asset_registry()
registry.wait_for_completion()
asset_rows = []
for data in registry.get_all_assets():
    package_name = str(data.package_name)
    lower = package_name.lower()
    if "curtain" not in lower and "interstitial" not in lower:
        continue
    try:
        class_name = str(data.asset_class_path.asset_name)
    except Exception:
        class_name = str(data.asset_class)
    tags = {}
    try:
        tags = {str(key): str(value) for key, value in data.tags_and_values.items()}
    except Exception:
        pass
    asset_rows.append(
        {
            "package_name": package_name,
            "asset_name": str(data.asset_name),
            "class": class_name,
            "tags": tags,
        }
    )

level_actors = []
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    label = actor.get_actor_label()
    path = object_path(actor)
    lower = f"{label} {path}".lower()
    if any(term in lower for term in ("curtain", "boy", "cat")):
        level_actors.append(
            {
                "label": label,
                "path": path,
                "class": actor.get_class().get_name(),
                "transform": str(actor.get_actor_transform()),
            }
        )

payload = {
    "status": "ok",
    "world": world_path,
    "assets": sorted(asset_rows, key=lambda row: row["package_name"].lower()),
    "sequences": [sequence_row(path) for path in SEQUENCE_PATHS],
    "level_actors": level_actors,
    "dirty_content": dirty_content,
    "dirty_maps": dirty_maps,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_sequence_assets.json",
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_SEQUENCE_INSPECT_SUCCESS"
    f"|assets={len(asset_rows)}|sequences={len(payload['sequences'])}"
    f"|level_actors={len(level_actors)}|dirty_content=0|dirty_maps=0"
)

