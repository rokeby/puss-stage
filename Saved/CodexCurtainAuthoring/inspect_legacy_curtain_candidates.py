"""Read-only identification of raw Show cues that request the legacy curtain."""

import json
import os

import unreal


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def object_path(value):
    if value is None:
        return ""
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


def package_path(value):
    return object_path(value).split(".", 1)[0]


def enum_text(value):
    try:
        return str(value.name)
    except Exception:
        return str(value)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world_path = package_path(editor.get_editor_world())
if world_path != EXPECTED_WORLD or editor.get_game_world() is not None:
    raise RuntimeError(f"Unsafe editor state: world={world_path}, game_world={editor.get_game_world()}")

dirty_content = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if dirty_content or dirty_maps:
    raise RuntimeError(f"Inspection requires clean editor: {dirty_content}/{dirty_maps}")

show = unreal.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError(f"Missing Show: {SHOW_PATH}")

rows = []
for index, cue in enumerate(show.get_editor_property("cues")):
    scene = cue.get_editor_property("scene")
    cue_type = cue.get_editor_property("type")
    mode = scene.get_editor_property("curtain_mode")
    owns = bool(scene.get_editor_property("sequence_owns_curtain"))
    if (
        cue_type != unreal.InfinityCueType.WING_PAIR
        and mode != unreal.InfinityCurtainCueMode.NONE
        and not owns
    ):
        rows.append(
            {
                "index": index,
                "enabled": bool(cue.get_editor_property("enabled")),
                "label": str(cue.get_editor_property("label")),
                "type": enum_text(cue_type),
                "curtain_mode": enum_text(mode),
                "sequence_owns_curtain": owns,
                "sequence": package_path(scene.get_editor_property("sequence")),
            }
        )

dirty_content_after = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps_after = [str(value) for value in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
if dirty_content_after or dirty_maps_after:
    raise RuntimeError(
        f"Inspection dirtied packages: {dirty_content_after}/{dirty_maps_after}"
    )

payload = {
    "status": "ok",
    "world": world_path,
    "legacy_candidates": rows,
    "candidate_count": len(rows),
    "enabled_candidate_count": sum(1 for row in rows if row["enabled"]),
    "disabled_candidate_count": sum(1 for row in rows if not row["enabled"]),
    "dirty_content_after": dirty_content_after,
    "dirty_maps_after": dirty_maps_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_legacy_curtain_candidates.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_LEGACY_CANDIDATES_INSPECTED"
    f"|candidates={len(rows)}"
    f"|enabled={payload['enabled_candidate_count']}"
    f"|disabled={payload['disabled_candidate_count']}"
    f"|dirty_content=0|dirty_maps=0"
)
