"""(Measurement only; no capture.) Make the stale P1 -> S1 handoff visible: two offscreen captures, same world state.

A: Passage 1's authored camera at its last frame, as the rig evaluates it.
B: Scene 1's Entry handoff camera, the cut the audience sees next.
Also writes the exact pose and lens difference.

Read-only in effect. It refuses to run unless content and maps are clean. It
spawns a transient SceneCapture2D per shot and destroys it, then clears the map
dirty flag that spawn/destroy leaves (safe only because the map was clean
before). The stage is not scrubbed, so both shots see the same world state and
differ only by camera. Success marker: PUSS_P1_S1_HANDOFF_CAPTURED
"""

import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
EXPOSURE_BIAS = 1.0

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    raise RuntimeError("Unexpected editor world")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
dirty_before = (
    [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
)
# Measurement only: no spawning, so a dirty map does not matter here.

show = unreal.load_asset(SHOW_PATH)
library = unreal.InfinityStageCameraPilotLibrary
passage = next(p for p in show.get_editor_property("passage_settings") if str(p.get_editor_property("label")) == "Passage 1")
p1_guid = passage.get_editor_property("passage_guid")
def unwrap(result, count):
    """UE Python returns out-params as a tuple, or None when a bool UFUNCTION returns false."""
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    return result


frame_range = unwrap(library.get_passage_frame_range(show, p1_guid), 2)
if frame_range is None:
    raise RuntimeError("Passage 1 has no frame range")
p1_end = int(frame_range[1])
pose = unwrap(library.get_passage_camera_pose(show, p1_guid, p1_end), 3)
if pose is None:
    raise RuntimeError("Passage 1 camera does not evaluate at its end frame")
p1_view, p1_focal, p1_focus = pose

actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rig = next(
    a for a in actors
    if a.get_class().get_name() == "InfinityStageCameraRig"
    and a.get_editor_property("passage_actor") is not None
    and unreal.GuidLibrary.conv_guid_to_string(a.get_editor_property("passage_actor").get_editor_property("passage_guid"))
    == unreal.GuidLibrary.conv_guid_to_string(p1_guid)
)
rig_lens = rig.get_editor_property("camera")
entry = [
    a for a in actors
    if isinstance(a, unreal.CineCameraActor)
    and a.actor_has_tag("InfinityStage.SceneEntry")
    and a.get_actor_label().startswith("Scene 1 ")
]
if len(entry) != 1:
    raise RuntimeError(f"Expected one Scene 1 Entry handoff camera, found {len(entry)}")
entry = entry[0]
entry_lens = entry.get_cine_camera_component()


def horizontal_fov(lens, focal_mm):
    sensor = lens.get_editor_property("filmback").get_editor_property("sensor_width")
    return math.degrees(2.0 * math.atan(sensor / (2.0 * focal_mm)))


shots = [
    ("P1_end_authored", p1_view.translation, p1_view.rotation.rotator(), horizontal_fov(rig_lens, p1_focal)),
    ("S1_entry_handoff", entry.get_actor_location(), entry.get_actor_rotation(),
     horizontal_fov(entry_lens, entry_lens.get_editor_property("current_focal_length"))),
]


leftovers = [a.get_actor_label() for a in actors if a.get_actor_label().startswith("ZZ_TransientCapture")]
a_rot = p1_view.rotation
b_rot = entry.get_actor_transform().rotation
dot = abs(a_rot.x * b_rot.x + a_rot.y * b_rot.y + a_rot.z * b_rot.z + a_rot.w * b_rot.w)
angle_deg = math.degrees(2.0 * math.acos(min(1.0, dot)))
delta = {
    "p1_end_frame": p1_end,
    "position_delta_cm": (entry.get_actor_location() - p1_view.translation).length(),
    "rotation_delta_deg": angle_deg,
    "p1_location": [p1_view.translation.x, p1_view.translation.y, p1_view.translation.z],
    "s1_location": [entry.get_actor_location().x, entry.get_actor_location().y, entry.get_actor_location().z],
    "p1_rotation": [shots[0][2].pitch, shots[0][2].yaw, shots[0][2].roll],
    "s1_rotation": [shots[1][2].pitch, shots[1][2].yaw, shots[1][2].roll],
    "p1_focal_mm": p1_focal,
    "s1_focal_mm": entry_lens.get_editor_property("current_focal_length"),
    "p1_focus_cm": p1_focus,
    "s1_focus_cm": entry_lens.get_editor_property("focus_settings").get_editor_property("manual_focus_distance"),
    "p1_hfov_deg": shots[0][3],
    "s1_hfov_deg": shots[1][3],
    "leftover_capture_actors": leftovers,
    "dirty_packages": dirty_before,
}
out_dir = unreal.Paths.project_saved_dir() + "CodexCameraPilot/Captures/"
with open(out_dir + "p1_s1_handoff_delta.json", "w", encoding="utf-8") as handle:
    json.dump(delta, handle, indent=2)
unreal.log(
    "PUSS_P1_S1_HANDOFF_MEASURED"
    f"|pos_delta_cm={delta['position_delta_cm']:.2f}|rot_delta_deg={angle_deg:.3f}"
    f"|focal={p1_focal:.2f}->{delta['s1_focal_mm']:.2f}|focus={p1_focus:.1f}->{delta['s1_focus_cm']:.1f}"
    f"|leftovers={len(leftovers)}|dirty={len(dirty_before)}"
)
