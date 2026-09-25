"""H.9 camera pilot, read-only verification against the production Show.

Writes nothing. For every Passage it samples the authored camera at three
moments, solves that view back into channel values with the new pilot solver,
and requires the solution to equal the channels' current values. That checks
the solve against the real routes (turned, offset, look-ahead) without a key.

Run through the guarded MCP executor on port 8010 only after the plugin build
that contains UInfinityStageCameraPilotLibrary. Success marker:
PUSS_CAMERA_PILOT_READONLY_SUCCESS
"""

import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SAMPLE_ALPHAS = (0.1, 0.5, 0.9)
POSITION_TOLERANCE_CM = 0.01
ROTATION_TOLERANCE_DEG = 0.01


def unwrap(result, count):
    """UE Python returns out-params as a tuple, or None when a bool UFUNCTION returns false."""
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    if count == 1 and not isinstance(result, tuple):
        return (result,)
    return result


def angle_delta(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None:
    raise RuntimeError("No editor world is open")
world_path = world.get_path_name().split(".", 1)[0]
if world_path != EXPECTED_WORLD:
    raise RuntimeError(f"Unexpected editor world: {world_path}")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
if not hasattr(unreal, "InfinityStageCameraPilotLibrary"):
    raise RuntimeError("InfinityStageCameraPilotLibrary is not loaded: the H.9 build is not in this editor")

dirty_before = sorted(
    [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    + [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
)

show = unreal.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError("Show asset did not load")

library = unreal.InfinityStageCameraPilotLibrary
samples = []
failures = []
for settings in show.get_editor_property("passage_settings"):
    guid = settings.get_editor_property("passage_guid")
    label = str(settings.get_editor_property("label"))
    frame_range = unwrap(library.get_passage_frame_range(show, guid), 2)
    if frame_range is None:
        failures.append(f"{label}: no compiled frame range")
        continue
    start, end = frame_range
    for alpha in SAMPLE_ALPHAS:
        frame = int(round(start + (end - start) * alpha))
        view = unwrap(library.get_passage_camera_pose(show, guid, frame), 3)
        if view is None:
            failures.append(f"{label}@{frame}: no camera rig evaluates")
            continue
        camera_world, focal, focus = view
        solved = unwrap(library.solve_passage_camera_pose(show, guid, frame, camera_world), 5)
        if solved is None:
            failures.append(f"{label}@{frame}: solve refused")
            continue
        offset, rotation, current_offset, current_rotation, report = solved
        position_error = (offset - current_offset).length()
        rotation_error = max(
            angle_delta(rotation.pitch, current_rotation.pitch),
            angle_delta(rotation.yaw, current_rotation.yaw),
            angle_delta(rotation.roll, current_rotation.roll),
        )
        sample = {
            "passage": label,
            "frame": frame,
            "offset_cm": [offset.x, offset.y, offset.z],
            "rotation": [rotation.pitch, rotation.yaw, rotation.roll],
            "position_error_cm": position_error,
            "rotation_error_deg": rotation_error,
            "focal_mm": focal,
        }
        samples.append(sample)
        if position_error > POSITION_TOLERANCE_CM or rotation_error > ROTATION_TOLERANCE_DEG:
            failures.append(f"{label}@{frame}: solve differs by {position_error:.5f} cm / {rotation_error:.5f} deg")

dirty_after = sorted(
    [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    + [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
)
if dirty_after != dirty_before:
    failures.append(f"dirty packages changed: {sorted(set(dirty_after) - set(dirty_before))}")

payload = {
    "world": world_path,
    "samples": samples,
    "failures": failures,
    "dirty_before": dirty_before,
    "dirty_after": dirty_after,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCameraPilot",
    "verify_camera_pilot_readonly.json",
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)

if failures or not samples:
    raise RuntimeError(f"Camera pilot read-only verification failed: {failures or 'no samples'}")

max_position = max(s["position_error_cm"] for s in samples)
max_rotation = max(s["rotation_error_deg"] for s in samples)
unreal.log(
    "PUSS_CAMERA_PILOT_READONLY_SUCCESS"
    f"|world={world_path}|samples={len(samples)}"
    f"|max_pos_err_cm={max_position:.6f}|max_rot_err_deg={max_rotation:.6f}"
    f"|dirty_before={len(dirty_before)}|dirty_after={len(dirty_after)}"
)
