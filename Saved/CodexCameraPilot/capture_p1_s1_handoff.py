"""Make the stale P1 -> S1 handoff visible: two offscreen captures, same world state.

A: Passage 1's authored camera at its last frame, as the rig evaluates it.
B: Scene 1's Entry handoff camera, the cut the audience sees next.
Also writes the exact pose and lens difference.

Writes no authored data, but it is NOT dirty-free. Spawning and destroying the
SceneCapture2D actors marks the level dirty with no net change, and UE 5.8's
Python does not expose Package.set_dirty_flag, so the flag cannot be cleared
from here (first run 2026-09-26 00:38 hit exactly that). It refuses to start
unless content and maps are clean, so any dirty map afterwards is known to be
this spawn/destroy only; measure_p1_s1_handoff.py confirms no capture actor is
left. Tell whoever holds the build gate before running it. The stage is not
scrubbed, so both shots see the same world state and differ only by camera.
Success marker: PUSS_P1_S1_HANDOFF_CAPTURED
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
if dirty_before:
    raise RuntimeError(f"Refusing: packages already dirty, clearing the map flag could hide real edits: {dirty_before}")

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

out_dir = unreal.Paths.project_saved_dir() + "CodexCameraPilot/Captures/"
os.makedirs(out_dir, exist_ok=True)
target = unreal.RenderingLibrary.create_render_target2d(world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB)
written = {}
for name, location, rotation, fov in shots:
    capture = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SceneCapture2D, location, rotation)
    try:
        capture.set_actor_label("ZZ_TransientCapture")
        component = capture.capture_component2d
        component.set_editor_property("texture_target", target)
        component.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR)
        component.set_editor_property("fov_angle", fov)
        component.set_editor_property("capture_every_frame", False)
        component.set_editor_property("capture_on_movement", False)
        post = component.get_editor_property("post_process_settings")
        post.set_editor_property("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL)
        post.set_editor_property("override_auto_exposure_method", True)
        post.set_editor_property("auto_exposure_bias", EXPOSURE_BIAS)
        post.set_editor_property("override_auto_exposure_bias", True)
        component.set_editor_property("post_process_settings", post)
        component.capture_scene()
        unreal.RenderingLibrary.export_render_target(world, target, out_dir, name + ".png")
        path = out_dir + name + ".png"
        written[name] = os.path.getsize(path) if os.path.exists(path) else 0
    finally:
        unreal.EditorLevelLibrary.destroy_actor(capture)

dirty_after = (
    [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
)

a_rot = p1_view.rotation
b_rot = entry.get_actor_transform().rotation
dot = abs(a_rot.x * b_rot.x + a_rot.y * b_rot.y + a_rot.z * b_rot.z + a_rot.w * b_rot.w)
angle_deg = math.degrees(2.0 * math.acos(min(1.0, dot)))
delta = {
    "p1_end_frame": int(p1_end),
    "position_delta_cm": (entry.get_actor_location() - p1_view.translation).length(),
    "rotation_delta_deg": angle_deg,
    "p1_rotation": [shots[0][2].pitch, shots[0][2].yaw, shots[0][2].roll],
    "s1_rotation": [shots[1][2].pitch, shots[1][2].yaw, shots[1][2].roll],
    "p1_focal_mm": p1_focal,
    "s1_focal_mm": entry_lens.get_editor_property("current_focal_length"),
    "p1_focus_cm": p1_focus,
    "s1_focus_cm": entry_lens.get_editor_property("focus_settings").get_editor_property("manual_focus_distance"),
    "p1_hfov_deg": shots[0][3],
    "s1_hfov_deg": shots[1][3],
    "images": written,
    "dirty_after": dirty_after,
    "note": "Same world state for both shots; the stage was not scrubbed. The images differ only by camera.",
}
with open(out_dir + "p1_s1_handoff_delta.json", "w", encoding="utf-8") as handle:
    json.dump(delta, handle, indent=2)
if not all(written.values()):
    raise RuntimeError(f"Capture incomplete: images={written}")
if [d for d in dirty_after if not d.startswith("/Game/InfinityStage/Dev/Maps/")]:
    raise RuntimeError(f"Capture dirtied content, not just the map: {dirty_after}")
unreal.log(
    "PUSS_P1_S1_HANDOFF_CAPTURED"
    f"|pos_delta_cm={delta['position_delta_cm']:.2f}|rot_delta_deg={angle_deg:.3f}"
    f"|focal={p1_focal:.2f}->{delta['s1_focal_mm']:.2f}|focus={p1_focus:.1f}->{delta['s1_focus_cm']:.1f}"
    f"|images={json.dumps(written)}|map_dirtied_by_capture={int(bool(dirty_after))}"
)
