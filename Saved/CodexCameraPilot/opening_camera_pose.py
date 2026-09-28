"""Read-only: the camera the audience sees during the Opening. The transport claims
Passage 1's rig evaluated at P1's first frame and holds it for the whole Opening.
This computes that pose WITHOUT evaluating (moving) the rig, and tests Rig's two lamp
positions against the camera frustum. Marker: PUSS_OPENING_CAMERA_POSE"""
import json, math, os
import unreal
show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
lib = unreal.InfinityStageCameraPilotLibrary
def unwrap(r, n):
    if r is None: return None
    if isinstance(r, tuple) and len(r) == n + 1 and isinstance(r[0], bool): return r[1:] if r[0] else None
    return r
p1 = next(p for p in show.get_editor_property("passage_settings") if str(p.get_editor_property("label")) == "Passage 1")
guid = p1.get_editor_property("passage_guid")
start, end = unwrap(lib.get_passage_frame_range(show, guid), 2)
view, focal, focus = unwrap(lib.get_passage_camera_pose(show, guid, int(start)), 3)
tick = show.get_editor_property("tick_resolution"); rate = tick.numerator / tick.denominator
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rig = next(a for a in actors if a.get_class().get_name() == "InfinityStageCameraRig"
           and a.get_editor_property("passage_actor") is not None
           and unreal.GuidLibrary.conv_guid_to_string(a.get_editor_property("passage_actor").get_editor_property("passage_guid")) == unreal.GuidLibrary.conv_guid_to_string(guid))
cam = rig.get_editor_property("camera")
fb = cam.get_editor_property("filmback")
sw, sh = fb.get_editor_property("sensor_width"), fb.get_editor_property("sensor_height")
hfov = math.degrees(2 * math.atan(sw / (2 * focal))); vfov = math.degrees(2 * math.atan(sh / (2 * focal)))
loc, rot = view.translation, view.rotation.rotator()
fwd = rot.get_forward_vector(); right = rot.get_right_vector(); up = rot.get_up_vector()
def in_shot(p):
    d = unreal.Vector(p[0] - loc.x, p[1] - loc.y, p[2] - loc.z)
    z = d.dot(fwd)
    if z <= 0: return {"in_front": False, "in_shot": False, "distance_m": d.length() / 100}
    h = math.degrees(math.atan2(d.dot(right), z)); v = math.degrees(math.atan2(d.dot(up), z))
    return {"in_front": True, "in_shot": abs(h) <= hfov / 2 and abs(v) <= vfov / 2, "h_deg": h, "v_deg": v, "distance_m": d.length() / 100}
curtains = [(a.get_actor_label(), [a.get_actor_location().x, a.get_actor_location().y, a.get_actor_location().z]) for a in actors if "Curtain" in a.get_class().get_name() or "Curtain" in a.get_actor_label()]
out = {"opening_frames_s": [0.0, start / rate], "p1_start_frame": start,
       "camera_location": [loc.x, loc.y, loc.z], "camera_rotation_pyr": [rot.pitch, rot.yaw, rot.roll],
       "forward": [fwd.x, fwd.y, fwd.z], "focal_mm": focal, "focus_cm": focus, "sensor_mm": [sw, sh],
       "hfov_deg": hfov, "vfov_deg": vfov, "saved_rig_location": [rig.get_actor_location().x, rig.get_actor_location().y, rig.get_actor_location().z],
       "lamp_A_3200": in_shot((3200, -125, 650)), "lamp_B_minus300": in_shot((-300, -125, 650)), "curtain_actors": curtains}
path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexCameraPilot", "opening_camera_pose.json")
with open(path, "w", encoding="utf-8") as h: json.dump(out, h, indent=2)
unreal.log(f"PUSS_OPENING_CAMERA_POSE|loc=({loc.x:.1f},{loc.y:.1f},{loc.z:.1f})|pyr=({rot.pitch:.2f},{rot.yaw:.2f},{rot.roll:.2f})|focal={focal:.1f}|hfov={hfov:.1f}|vfov={vfov:.1f}")
