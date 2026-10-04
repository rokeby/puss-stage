"""DRAFT (4 Oct, offline-written, NEVER RUN IN UNREAL): key a Scene's exit move.

Option B of Docs/Conductor/SCENE_EXIT_OPTIONS_2026-10-04.md: a hard cut to a
camera ~9 m in front of the hangar's closed exit door, a held beat, the door
leaf swings IN toward the camera on its jamb hinge, the camera walks through
the doorway at the cat's 250 cm/s into the Exit Black, and the Scene's
retained Exit hold (a copy of this camera's final pose) keeps the black until
the Interaction cuts to its stalls camera and drape.

NOT TO BE APPLIED UNTIL GARY PICKS AN OPTION.  APPLY additionally refuses
unless scene_exit_move_overrides.json carries {"decided_by": "<name>",
"option": "B"}.  There is deliberately no apply runner beside this file.

Modes (globals set by a runner, like hangar_exit_doors.py):
  SCENE_EXIT_MOVE_SCENE   int 1..6 (required)
  SCENE_EXIT_MOVE_APPLY   True -> write (sequence + level), else DRY
  SCENE_EXIT_MOVE_REVERT  True -> remove exactly what the record lists
Importing this module with no `unreal` (system Python) never touches Unreal;
the pure planner and gates below are what test_scene_exit_move.py exercises.

What APPLY writes (Scene N's own Level Sequence + the show level, nothing
else; the Master and the Show must stay clean):
  * level: one CineCameraActor "S<N> Exit Door Camera", attached to
    "S<N> Hangar Root", tags SceneExitMove / SceneExitMove.S<N>, its saved
    relative pose = the move's FINAL pose (inside the doorway, facing black).
    Its label/tags must NOT look like a handoff camera
    (InfinityStageSceneHandoffBuilder.cpp:96-109), or the builder adopts it.
  * Scene sequence: possessables for that camera (+ its CineCameraComponent)
    and for "S<N> Hangar Exit Door Leaf"; a transform track on each (keys
    every display frame, root-relative, LINEAR); a focus track on the
    component; one root camera-cut section [move_start, move_end).
  * then match_named_scene_handoffs(show, [cue_guid], 1) re-ranges the
    retained Exit to [move_end, scene_end) and copies this camera's actor
    transform into it (builder .cpp:371-445).  Entry must not move.
Gates (DRY reports them; APPLY refuses on any):
  S3_BACKDROP_BEHIND_LEAF, NESTED_CUTS_IN_WINDOW, ROOT_CUT_OVERLAP,
  RISE_OVERLAPS_WINDOW, NOT_RETAINED_EXIT, CORRIDOR_BLOCKED, ROOT_NOT_UP,
  plan-check failures (clearance, frame fill, speed, grid).
Success markers: SCENE_EXIT_MOVE_DRY_OK / _APPLY_OK / _REVERT_OK;
any refusal logs SCENE_EXIT_MOVE_STOPPED|run=..|reason=..
"""
import datetime
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
DOORS_RECORD_NAME = "hangar_exit_doors_record.json"
OVERRIDES_NAME = "scene_exit_move_overrides.json"
RECORD_PATTERN = "scene_exit_move_record_S%d.json"
HANGAR_PLAN_PATTERN = os.path.join("CodexStructure", "hangar_s%d_plan.json")
TRACK_NAME = "SceneExitMove (Conductor)"
CAMERA_LABEL_PATTERN = "S%d Exit Door Camera"
CAMERA_TAGS = ("SceneExitMove", "SceneExitMove.S%d")
LEAF_LABEL_PATTERN = "S%d Hangar Exit Door Leaf"
BLACK_LABEL_PATTERN = "S%d Hangar Exit Black"
ROOT_LABEL_PATTERN = "S%d Hangar Root"
FPS = 25.0
SHOW_TICKS_PER_S = 24000.0
# Super 35 (memory puss-camera-handover-facts: framing math uses 23.76 x 13.365;
# the filmback is not yet read from the camera itself - APPLY reads it live).
FILMBACK_MM = (23.76, 13.365)
METAL_BLACK = "M_Metal_Black_01_Mat"

DEFAULTS = {
    "option": "B",
    "seat_distance_cm": 900.0,     # seat in front of the door face
    "hold_closed_s": 1.5,          # beat on the closed, hidden door
    "door_open_s": 3.0,            # smoothstep swing
    "open_deg": 100.0,
    "hinge_side": "left",          # -Y jamb, seen from the camera
    "walk_delay_s": 1.0,           # walk starts this long after the door starts
    "speed_cm_s": 250.0,           # the Passages' preferred speed
    "ease_in_s": 1.0,
    "ease_out_s": 0.8,
    "final_gap_cm": 25.0,          # lens to Exit Black front face at the end
    "black_hold_s": 0.5,           # held black before the retained Exit hold
    "focal_mm": 35.0,
    "min_leaf_clearance_cm": 40.0,
    "frame_fill_margin_cm": 10.0,
    "s3_backdrop_cut": False,      # S3 refuses until the backdrop has a hole
}


class PlanError(ValueError):
    pass


# ----------------------------------------------------------------------------
# Pure geometry and timing (offline-tested)
# ----------------------------------------------------------------------------

def frames_from_ticks(ticks, ticks_per_s=SHOW_TICKS_PER_S, fps=FPS):
    return int(round(float(ticks) / float(ticks_per_s) * float(fps)))


def door_geometry(doors_plan_scene):
    """Door leaf, opening and Exit Black in the hangar-root frame, from one
    scene row of hangar_exit_doors_record.json["plan"]["scenes"]."""
    pieces = {piece["role"]: piece for piece in doors_plan_scene["pieces"]}
    for role in ("leaf", "black"):
        if role not in pieces:
            raise PlanError("S%s doors plan has no %s piece" % (doors_plan_scene.get("scene"), role))
    leaf, black = pieces["leaf"], pieces["black"]
    leaf_center = [float(value) for value in leaf["location_cm"]]
    leaf_size = [float(value) for value in leaf["size_cm"]]
    black_center = [float(value) for value in black["location_cm"]]
    black_size = [float(value) for value in black["size_cm"]]
    floor_z = float(doors_plan_scene.get("door_floor_root_z_cm",
                                         leaf_center[2] - leaf_size[2] / 2.0 - 0.5))
    return {
        "scene": int(doors_plan_scene["scene"]),
        "leaf_label": leaf["label"],
        "black_label": black["label"],
        "leaf_center": leaf_center,
        "leaf_size": leaf_size,
        "leaf_mesh": leaf.get("mesh"),
        "door_face_x": leaf_center[0] - leaf_size[0] / 2.0,
        "black_front_x": black_center[0] - black_size[0] / 2.0,
        "black_material": black.get("material"),
        "opening_center_y": float(doors_plan_scene.get("door_offset_y_cm", leaf_center[1])),
        "opening_half_w": black_size[1] / 2.0,
        "opening_z": [floor_z, floor_z + black_size[2]],
        "floor_z": floor_z,
        "surface_strategy": doors_plan_scene.get("surface_strategy"),
        "backdrop_crossings": list(doors_plan_scene.get("backdrop_crossings", [])),
    }


def _rotate_xy(vector, yaw_deg):
    radians = math.radians(yaw_deg)
    c, s = math.cos(radians), math.sin(radians)
    return (vector[0] * c - vector[1] * s, vector[0] * s + vector[1] * c)


def hinge_point(geom, hinge_side):
    hx, hy = geom["leaf_size"][0] / 2.0, geom["leaf_size"][1] / 2.0
    cx, cy = geom["leaf_center"][0], geom["leaf_center"][1]
    if hinge_side == "left":
        return (cx - hx, cy - hy)
    if hinge_side == "right":
        return (cx - hx, cy + hy)
    raise PlanError("hinge_side must be left or right, not %r" % hinge_side)


def leaf_yaw(theta_deg, hinge_side):
    """Inward (toward the camera, -X) is +yaw for a -Y hinge, -yaw for +Y."""
    return float(theta_deg) if hinge_side == "left" else -float(theta_deg)


def leaf_pose(geom, theta_deg, hinge_side):
    """Root-relative (location, yaw) of the leaf opened theta about its hinge."""
    hinge = hinge_point(geom, hinge_side)
    centre_from_hinge = (geom["leaf_center"][0] - hinge[0], geom["leaf_center"][1] - hinge[1])
    yaw = leaf_yaw(theta_deg, hinge_side)
    rx, ry = _rotate_xy(centre_from_hinge, yaw)
    return [hinge[0] + rx, hinge[1] + ry, geom["leaf_center"][2]], yaw


def leaf_polygon(geom, theta_deg, hinge_side):
    """The leaf's XY footprint (4 corners) at theta, root frame."""
    (cx, cy, _), yaw = leaf_pose(geom, theta_deg, hinge_side)
    hx, hy = geom["leaf_size"][0] / 2.0, geom["leaf_size"][1] / 2.0
    corners = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        rx, ry = _rotate_xy((sx * hx, sy * hy), yaw)
        corners.append((cx + rx, cy + ry))
    return corners


def point_polygon_distance(point, polygon):
    px, py = point
    inside = False
    count = len(polygon)
    for index in range(count):
        x0, y0 = polygon[index]
        x1, y1 = polygon[(index + 1) % count]
        if (y0 > py) != (y1 > py):
            cross_x = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
            if px < cross_x:
                inside = not inside
    if inside:
        return 0.0
    best = float("inf")
    for index in range(count):
        x0, y0 = polygon[index]
        x1, y1 = polygon[(index + 1) % count]
        dx, dy = x1 - x0, y1 - y0
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0.0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / length2))
        qx, qy = x0 + t * dx, y0 + t * dy
        best = min(best, math.hypot(px - qx, py - qy))
    return best


def smoothstep(u):
    u = max(0.0, min(1.0, float(u)))
    return u * u * (3.0 - 2.0 * u)


def walk_profile(distance_cm, speed, ease_in_s, ease_out_s):
    """Trapezoid: linear velocity ramp up, cruise, ramp down to rest.
    Returns (duration_s, s(t) callable)."""
    d, v = float(distance_cm), float(speed)
    a_in, a_out = float(ease_in_s), float(ease_out_s)
    if d <= 0.0 or v <= 0.0 or a_in < 0.0 or a_out < 0.0:
        raise PlanError("walk profile inputs must be positive")
    ramp = 0.5 * v * (a_in + a_out)
    if ramp > d:
        raise PlanError("walk distance %.1f cm is shorter than its ramps (%.1f cm)" % (d, ramp))
    cruise = (d - ramp) / v
    total = a_in + cruise + a_out

    def s_at(t):
        t = max(0.0, min(total, float(t)))
        if t <= a_in:
            return 0.0 if a_in == 0.0 else 0.5 * v * t * t / a_in
        s_in = 0.5 * v * a_in
        if t <= a_in + cruise:
            return s_in + v * (t - a_in)
        u = t - a_in - cruise
        return s_in + v * cruise + v * u - (0.5 * v * u * u / a_out if a_out else 0.0)

    return total, s_at


def plan_exit_move(geom, eye_z_root, scene_end_frame, exit_hold_frames, params=None):
    """Return the per-frame camera and leaf keys plus a report.

    Frames are the Scene sequence's display frames (25 fps).  The move ends at
    scene_end - exit_hold so the builder's retained Exit hold follows it."""
    p = dict(DEFAULTS)
    p.update(params or {})
    fps = FPS
    seat_x = geom["door_face_x"] - float(p["seat_distance_cm"])
    final_x = geom["black_front_x"] - float(p["final_gap_cm"])
    if final_x <= geom["door_face_x"]:
        raise PlanError("final pose is not past the door face")
    y = geom["opening_center_y"]
    walk_s, s_at = walk_profile(final_x - seat_x, p["speed_cm_s"], p["ease_in_s"], p["ease_out_s"])
    # Snap beats to the display-frame grid so the first leaf key is exactly closed.
    door_start_s = round(float(p["hold_closed_s"]) * fps) / fps
    walk_start_s = door_start_s + round(float(p["walk_delay_s"]) * fps) / fps
    arrive_s = walk_start_s + walk_s
    total_s = max(arrive_s, door_start_s + float(p["door_open_s"])) + float(p["black_hold_s"])
    total_frames = int(math.ceil(total_s * fps - 1.0e-9))
    move_end = int(scene_end_frame) - int(exit_hold_frames)
    move_start = move_end - total_frames
    door_start_frame = move_start + int(round(door_start_s * fps))
    camera_keys, leaf_keys = [], []
    for frame in range(move_start, move_end + 1):
        t = (frame - move_start) / fps
        x = seat_x + s_at(t - walk_start_s) if t >= walk_start_s else seat_x
        focus = max(10.0, (geom["door_face_x"] - x) if x < geom["door_face_x"]
                    else (geom["black_front_x"] - x))
        camera_keys.append((frame, x, y, float(eye_z_root), 0.0, 0.0, 0.0,
                            float(p["focal_mm"]), focus))
        if frame >= door_start_frame:
            u = (t - door_start_s) / float(p["door_open_s"])
            theta = float(p["open_deg"]) * smoothstep(u)
            (lx, ly, lz), yaw = leaf_pose(geom, theta, p["hinge_side"])
            leaf_keys.append((frame, lx, ly, lz, 0.0, yaw, 0.0, theta))  # same layout as camera keys
    report = {
        "option": p["option"],
        "params": p,
        "seat_root_cm": [seat_x, y, float(eye_z_root)],
        "final_root_cm": [final_x, y, float(eye_z_root)],
        "walk_cm": final_x - seat_x,
        "walk_s": walk_s,
        "total_s": total_frames / fps,
        "exit_hold_frames": int(exit_hold_frames),
        "window": [move_start, move_end],
        "door_start_frame": door_start_frame,
        "scene_end_frame": int(scene_end_frame),
        "on_screen_s_including_exit_hold": (total_frames + int(exit_hold_frames)) / fps,
    }
    return {"camera_keys": camera_keys, "leaf_keys": leaf_keys, "report": report}


def frame_fill_ok(geom, camera_x, camera_y, camera_z, focal_mm, margin_cm,
                  filmback_mm=FILMBACK_MM):
    """True when the whole frame lands on the Exit Black inside the opening."""
    distance = geom["black_front_x"] - camera_x
    if distance <= 0.0:
        return False
    half_w = distance * (filmback_mm[0] / 2.0) / focal_mm
    half_h = distance * (filmback_mm[1] / 2.0) / focal_mm
    lateral = abs(camera_y - geom["opening_center_y"]) + half_w
    return (lateral <= geom["opening_half_w"] - margin_cm and
            camera_z - half_h >= geom["opening_z"][0] + margin_cm and
            camera_z + half_h <= geom["opening_z"][1] - margin_cm)


def check_plan(plan, geom, params=None):
    """Every way the plan can be wrong that is checkable offline.  [] = pass."""
    p = dict(DEFAULTS)
    p.update(params or {})
    failures = []
    cam, leaf = plan["camera_keys"], plan["leaf_keys"]
    rep = plan["report"]
    frames = [key[0] for key in cam]
    if frames != list(range(rep["window"][0], rep["window"][1] + 1)):
        failures.append("camera keys are not one per display frame across the window")
    if rep["window"][0] < 0:
        failures.append("window starts before the Scene (%d)" % rep["window"][0])
    if rep["window"][1] != rep["scene_end_frame"] - rep["exit_hold_frames"]:
        failures.append("move does not end where the retained Exit hold begins")
    if abs(cam[0][1] - rep["seat_root_cm"][0]) > 1.0e-6 or abs(cam[-1][1] - rep["final_root_cm"][0]) > 1.0e-3:
        failures.append("first/last camera key is not the seat/final pose")
    for a, b in zip(cam, cam[1:]):
        if b[1] < a[1] - 1.0e-9:
            failures.append("camera moves backwards at frame %d" % b[0])
            break
        if (b[1] - a[1]) * FPS > float(p["speed_cm_s"]) + 1.0e-6:
            failures.append("camera exceeds %.0f cm/s at frame %d" % (p["speed_cm_s"], b[0]))
            break
    for a, b, c in zip(cam, cam[1:], cam[2:]):
        accel = abs((c[1] - 2.0 * b[1] + a[1]) * FPS * FPS)
        limit = float(p["speed_cm_s"]) / min(float(p["ease_in_s"]), float(p["ease_out_s"])) + 1.0
        if accel > limit:
            failures.append("acceleration %.1f cm/s2 > %.1f at frame %d" % (accel, limit, b[0]))
            break
    if cam[-1][1] > geom["black_front_x"] - 1.0:
        failures.append("camera reaches the Exit Black")
    leaf_by_frame = {key[0]: key for key in leaf}
    if not leaf:
        failures.append("no leaf keys")
    else:
        first = leaf[0]
        if (abs(first[1] - geom["leaf_center"][0]) > 0.01 or abs(first[2] - geom["leaf_center"][1]) > 0.01
                or abs(first[5]) > 1.0e-6):
            failures.append("first leaf key is not the recorded closed pose")
        if abs(leaf[-1][7] - float(p["open_deg"])) > 1.0e-6:
            failures.append("leaf does not reach open_deg by the end of the window")
        # The hinge must stay put: every leaf key is a rigid rotation about it.
        hinge = hinge_point(geom, p["hinge_side"])
        radius = math.hypot(geom["leaf_center"][0] - hinge[0], geom["leaf_center"][1] - hinge[1])
        for key in leaf:
            if abs(math.hypot(key[1] - hinge[0], key[2] - hinge[1]) - radius) > 1.0e-6:
                failures.append("leaf key at frame %d leaves its hinge" % key[0])
                break
    min_clear = float("inf")
    for key in cam:
        theta = leaf_by_frame[key[0]][7] if key[0] in leaf_by_frame else 0.0
        clearance = point_polygon_distance((key[1], key[2]), leaf_polygon(geom, theta, p["hinge_side"]))
        min_clear = min(min_clear, clearance)
    if min_clear < float(p["min_leaf_clearance_cm"]):
        failures.append("camera passes %.1f cm from the leaf (< %.1f)" % (min_clear, p["min_leaf_clearance_cm"]))
    rep["min_leaf_clearance_cm"] = min_clear
    last = cam[-1]
    if not frame_fill_ok(geom, last[1], last[2], last[3], float(p["focal_mm"]), float(p["frame_fill_margin_cm"])):
        failures.append("final frame is not filled by the Exit Black")
    if not (geom["opening_z"][0] < last[3] < geom["opening_z"][1]):
        failures.append("eye height is outside the doorway")
    return failures


def looks_like_handoff_camera(label, tags):
    """Mirror of InfinityStageSceneHandoffBuilder.cpp:96-109 (either half)."""
    tags = set(tags)
    if "InfinityStage.SceneHandoff" in tags and (
            "InfinityStage.SceneEntry" in tags or "InfinityStage.SceneExit" in tags):
        return True
    return "Entry Handoff Camera" in label or "Exit Handoff Camera" in label


def gate_root_cuts(cuts, window_start, scene_end):
    """cuts: [{"label", "start", "end", "active", "handoff": bool}].  Any
    non-handoff cut (active OR inactive: inactive cuts still count in the
    builder's loop, memory puss-camera-handover-facts) overlapping
    [window_start, scene_end) refuses."""
    return ["%s [%d,%d) active=%s" % (cut["label"], cut["start"], cut["end"], cut["active"])
            for cut in cuts
            if not cut.get("handoff") and cut["start"] < scene_end and cut["end"] > window_start]


def gate_nested(nested_rows, window_start, scene_end):
    """nested_rows: [{"sequence", "track", "in_parent": [a, b], "active", "sub_cut_count"}].
    Nested shot cuts outrank root cuts (measured 30 Sep), so ANY active nested
    section that has camera cuts and overlaps the window refuses.  Conservative:
    the parent-to-sub frame mapping is not modelled."""
    return ["%s %s in_parent=%r cuts=%d" % (row["track"], row["sequence"], row["in_parent"], row["sub_cut_count"])
            for row in nested_rows
            if row.get("active") and row.get("sub_cut_count", 0) > 0
            and row["in_parent"][0] < scene_end and row["in_parent"][1] > window_start]


def gate_rise(sub_rows, window_start):
    """The hangar rise must be complete before the exit move starts."""
    return ["%s in_parent=%r" % (row["sequence"], row["in_parent"])
            for row in sub_rows
            if "HangarRise" in row["sequence"] and row.get("active") and row["in_parent"][1] > window_start]


def gate_scene(geom, params=None):
    p = dict(DEFAULTS)
    p.update(params or {})
    refusals, warnings = [], []
    if geom["backdrop_crossings"] and not p.get("s3_backdrop_cut"):
        refusals.append(
            "S3_BACKDROP_BEHIND_LEAF: the leaf (%s) sits 0.05 cm in front of %r, which the doors tool never "
            "cut; an opened leaf shows the same picture behind it" %
            (geom["surface_strategy"], geom["backdrop_crossings"]))
    if METAL_BLACK in str(geom.get("black_material")):
        warnings.append("EXIT_BLACK_IS_METAL: %s reads lit tan under warm light (memory puss-masking-needs-velvet); "
                        "swap to a black velvet child MI and measure before trusting the final black" %
                        geom["black_label"])
    return refusals, warnings


def build_dry_report(doors_plan_scene, eye_z_root, scene_end_frame, exit_hold_frames,
                     root_cuts, nested_rows, params=None, camera_label=None, camera_tags=()):
    geom = door_geometry(doors_plan_scene)
    plan = plan_exit_move(geom, eye_z_root, scene_end_frame, exit_hold_frames, params)
    failures = check_plan(plan, geom, params)
    refusals, warnings = gate_scene(geom, params)
    window_start = plan["report"]["window"][0]
    overlaps = gate_root_cuts(root_cuts, window_start, scene_end_frame)
    nested = gate_nested(nested_rows, window_start, scene_end_frame)
    rise = gate_rise(nested_rows, window_start)
    if overlaps:
        refusals.append("ROOT_CUT_OVERLAP: " + "; ".join(overlaps))
    if nested:
        refusals.append("NESTED_CUTS_IN_WINDOW: " + "; ".join(nested))
    if rise:
        refusals.append("RISE_OVERLAPS_WINDOW: " + "; ".join(rise))
    if camera_label and looks_like_handoff_camera(camera_label, camera_tags):
        refusals.append("CAMERA_LOOKS_LIKE_HANDOFF: " + camera_label)
    refusals.extend("PLAN_CHECK: " + text for text in failures)
    return {"geometry": geom, "plan": plan, "refusals": refusals, "warnings": warnings,
            "apply_ready": not refusals}


# ----------------------------------------------------------------------------
# Unreal side (DRAFT: every call below has a cited precedent in this repo but
# this file has never executed in the editor)
# ----------------------------------------------------------------------------

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _load_json(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise PlanError("missing " + path)
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _stop(run, reason):
    unreal.log_error("SCENE_EXIT_MOVE_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    def names(values):
        return sorted(str(value.get_name()).split(".", 1)[0] for value in values)
    return {"content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _actors_by_label():
    index = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        index.setdefault(str(actor.get_actor_label()), []).append(actor)
    return index


def _one(index, label, run):
    rows = index.get(label, [])
    if len(rows) != 1:
        _stop(run, "ACTOR_COUNT|label=%s|count=%d" % (label, len(rows)))
    return rows[0]


def _scene_cue(show, n, run):
    label = "Scene %d — External Sound" % n
    cues = [cue for cue in show.get_editor_property("cues")
            if str(cue.get_editor_property("label")) == label and cue.get_editor_property("enabled")]
    if len(cues) != 1:
        _stop(run, "SCENE_CUE_COUNT|label=%s|count=%d" % (label, len(cues)))
    return cues[0], label


def _section_span(section, start, end):
    a = section.get_start_frame() if section.has_start_frame() else start
    b = section.get_end_frame() if section.has_end_frame() else end
    return int(a), int(b)


def _root_cut_rows(sequence, world_index_by_guid):
    start, end = sequence.get_playback_start(), sequence.get_playback_end()
    rows = []
    for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for section in track.get_sections():
            guid = _guid(section.get_camera_binding_id().get_editor_property("guid"))
            name = world_index_by_guid.get(guid, "?" + guid)
            a, b = _section_span(section, start, end)
            rows.append({"label": name, "guid": guid, "start": a, "end": b,
                         "active": bool(section.is_active()),
                         "handoff": ("Entry Handoff Camera" in name or "Exit Handoff Camera" in name)})
    return rows


def _nested_rows(sequence):
    start, end = sequence.get_playback_start(), sequence.get_playback_end()
    rows = []
    for track_type in (unreal.MovieSceneCinematicShotTrack, unreal.MovieSceneSubTrack):
        for track in sequence.find_tracks_by_type(track_type):
            for section in track.get_sections():
                sub = section.get_sequence()
                if sub is None:
                    continue
                cuts = [cut for cut_track in sub.find_tracks_by_type(unreal.MovieSceneCameraCutTrack)
                        for cut in cut_track.get_sections() if cut.is_active()]
                rows.append({"track": track.get_class().get_name(),
                             "sequence": sub.get_path_name().split(".")[0],
                             "in_parent": list(_section_span(section, start, end)),
                             "active": bool(section.is_active()), "sub_cut_count": len(cuts)})
    return rows


def _binding_names(sequence):
    return {_guid(binding.get_id()): str(binding.get_display_name()) for binding in sequence.get_bindings()}


def _content_file(path, ext=".uasset"):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ext


def _cut_gaps(sequence):
    start, end = sequence.get_playback_start(), sequence.get_playback_end()
    spans = sorted(_section_span(section, start, end)
                   for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack)
                   for section in track.get_sections() if section.is_active())
    gaps, cursor, overlaps = [], start, []
    for a, b in spans:
        if a > cursor:
            gaps.append([cursor, a])
        if a < cursor:
            overlaps.append([a, min(b, cursor)])
        cursor = max(cursor, b)
    if cursor < end:
        gaps.append([cursor, end])
    return gaps, overlaps


def _gather(n, run):
    """Everything DRY needs, read-only."""
    here = _here()
    doors = _load_json(os.path.join(here, DOORS_RECORD_NAME))
    if doors.get("world") != EXPECTED_WORLD or not doors.get("applied"):
        _stop(run, "DOORS_RECORD_CONTEXT")
    rows = [row for row in doors["plan"]["scenes"] if int(row["scene"]) == n]
    if len(rows) != 1:
        _stop(run, "DOORS_PLAN_ROW_COUNT|scene=%d" % n)
    hangar_plan = _load_json(os.path.join(os.path.dirname(here), HANGAR_PLAN_PATTERN % n))
    index = _actors_by_label()
    root = _one(index, ROOT_LABEL_PATTERN % n, run)
    rel = root.root_component.get_editor_property("relative_rotation")
    if abs(float(rel.pitch)) > 0.05 or abs(float(rel.roll)) > 0.05:
        _stop(run, "ROOT_NOT_UP|scene=%d|pitch=%.3f|roll=%.3f" % (n, rel.pitch, rel.roll))
    leaf = _one(index, LEAF_LABEL_PATTERN % n, run)
    if leaf.get_attach_parent_actor() != root:
        _stop(run, "LEAF_NOT_ON_ROOT|scene=%d" % n)
    leaf_rel = list(leaf.root_component.get_editor_property("relative_location").to_tuple())
    geom_check = door_geometry(rows[0])
    if max(abs(a - b) for a, b in zip(leaf_rel, geom_check["leaf_center"])) > 0.1:
        _stop(run, "LEAF_MOVED_SINCE_DOORS_RECORD|scene=%d|now=%r" % (n, leaf_rel))
    # Eye height: the dock (Passage end camera) height in the root frame.
    dock_z = float(hangar_plan["dock"]["loc"][2])
    eye_z_root = dock_z - float(root.get_actor_location().z)
    show = unreal.load_asset(SHOW_PATH)
    cue, cue_label = _scene_cue(show, n, run)
    scene = cue.get_editor_property("scene")
    sequence = scene.get_editor_property("sequence")
    if sequence is None:
        _stop(run, "SCENE_HAS_NO_SEQUENCE|scene=%d" % n)
    rate = sequence.get_display_rate()
    if abs(rate.numerator / float(rate.denominator) - FPS) > 1.0e-6:
        _stop(run, "SCENE_FPS|scene=%d" % n)
    hold_ticks = scene.get_editor_property("exit_handoff_hold_frames").value
    exit_cams = index.get("%s — Exit Handoff Camera" % cue_label, [])
    if len(exit_cams) != 1 or not exit_cams[0].actor_has_tag("InfinityStage.SceneRetainedHold"):
        _stop(run, "NOT_RETAINED_EXIT|scene=%d" % n)
    names = _binding_names(sequence)
    return {
        "doors_row": rows[0], "eye_z_root": eye_z_root, "show": show, "cue": cue,
        "cue_label": cue_label, "sequence": sequence, "root": root, "leaf": leaf,
        "scene_end": int(sequence.get_playback_end()),
        "exit_hold_frames": frames_from_ticks(hold_ticks),
        "root_cuts": _root_cut_rows(sequence, names),
        "nested": _nested_rows(sequence),
        "exit_camera": exit_cams[0],
    }


def _corridor_blockers(n, root, plan):
    """Actors whose bounds cross the seat->final corridor (120 cm wide, eye
    +-110 cm), in the root frame.  Hangar pieces and the giant conservative
    Structure/Passage AABBs are listed separately, not refused."""
    seat, final = plan["report"]["seat_root_cm"], plan["report"]["final_root_cm"]
    x0, x1 = seat[0], final[0]
    y0, y1 = seat[1] - 60.0, seat[1] + 60.0
    z0, z1 = seat[2] - 110.0, seat[2] + 110.0
    root_xf = root.get_actor_transform()
    blockers, unchecked = [], []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        label = str(actor.get_actor_label())
        if label.startswith("S%d Hangar" % n) or label.startswith("S%d Exit Door Camera" % n):
            continue
        origin, extent = actor.get_actor_bounds(False)
        corners = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    world = unreal.Vector(origin.x + sx * extent.x, origin.y + sy * extent.y,
                                          origin.z + sz * extent.z)
                    local = unreal.MathLibrary.inverse_transform_location(root_xf, world)
                    corners.append((local.x, local.y, local.z))
        lo = [min(c[i] for c in corners) for i in range(3)]
        hi = [max(c[i] for c in corners) for i in range(3)]
        if hi[0] < x0 or lo[0] > x1 or hi[1] < y0 or lo[1] > y1 or hi[2] < z0 or lo[2] > z1:
            continue
        if (hi[0] - lo[0]) > 20000.0 or (hi[1] - lo[1]) > 20000.0:
            unchecked.append(label)
        else:
            blockers.append(label)
    return blockers, unchecked


def _backup(n, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "PreSceneExitMoveS%d-%s" % (n, run))
    os.makedirs(folder, exist_ok=False)
    return folder


def _copy_into(folder, sources, run):
    copied = []
    for source in sources:
        if not os.path.isfile(source):
            _stop(run, "BACKUP_SOURCE_MISSING|" + source)
        target = os.path.join(folder, os.path.basename(source))
        shutil.copy2(source, target)
        if os.path.getsize(target) != os.path.getsize(source):
            _stop(run, "BACKUP_SIZE_MISMATCH|" + source)
        copied.append(target)
    return copied


def _key_channels(section, keys, mapping, run, label):
    channels = {str(channel.channel_name): channel for channel in section.get_all_channels()}
    missing = sorted(set(mapping) - set(channels))
    if missing:
        _stop(run, "CHANNELS_MISSING|%s|%r" % (label, missing))
    for key in keys:
        for name, index in mapping.items():
            made = channels[name].add_key(unreal.FrameNumber(int(key[0])), float(key[index]),
                                          time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                          interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
            if made is None:
                _stop(run, "ADD_KEY_NONE|%s|%s|%d" % (label, name, key[0]))
    return channels


# Channel names are as in key_walkin_i1_p02.py:313-316; memory
# ue58-sequencer-read-traps warns they can carry suffixes (Location.Y_183), so
# APPLY refuses on a missing name rather than guessing.
# Key tuples: (frame, x, y, z, pitch, yaw, roll, focal|theta, focus).
# Rotation.X = roll, .Y = pitch, .Z = yaw (key_walkin_i1_p02.py:313-316).
POSE_CHANNELS = {"Location.X": 1, "Location.Y": 2, "Location.Z": 3,
                 "Rotation.X": 6, "Rotation.Y": 4, "Rotation.Z": 5}


def apply_move(n, gathered, dry, params, run):
    sequence, root, leaf = gathered["sequence"], gathered["root"], gathered["leaf"]
    camera_label = CAMERA_LABEL_PATTERN % n
    tags = [CAMERA_TAGS[0], CAMERA_TAGS[1] % n]
    dry_report = build_dry_report(gathered["doors_row"], gathered["eye_z_root"], gathered["scene_end"],
                                  gathered["exit_hold_frames"], gathered["root_cuts"], gathered["nested"],
                                  params, camera_label, tags)
    plan = dry_report["plan"]
    blockers, unchecked = _corridor_blockers(n, root, plan)
    dry_report["corridor"] = {"blockers": blockers, "unchecked_large": unchecked}
    if blockers:
        dry_report["refusals"].append("CORRIDOR_BLOCKED: %r" % blockers)
        dry_report["apply_ready"] = False
    if camera_label in _actors_by_label():
        dry_report["refusals"].append("CAMERA_EXISTS: %s (revert first)" % camera_label)
        dry_report["apply_ready"] = False
    bound_names = set(_binding_names(sequence).values())
    for label in (camera_label, str(leaf.get_actor_label())):
        if label in bound_names:
            # REVERT removes the leaf binding whole, so it must be ours alone.
            dry_report["refusals"].append("ALREADY_BOUND_IN_SCENE: %s" % label)
            dry_report["apply_ready"] = False
    out = os.path.join(_here(), "scene_exit_move_S%d_dry.json" % n)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump({k: v for k, v in dry_report.items()}, handle, indent=1, default=str)
    if dry:
        if _census() != {"content": [], "maps": []}:
            _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
        unreal.log("SCENE_EXIT_MOVE_DRY_OK|run=%s|scene=%d|mutated=0|apply_ready=%d|window=%r|refusals=%d|warnings=%d|report=%s"
                   % (run, n, int(dry_report["apply_ready"]), plan["report"]["window"],
                      len(dry_report["refusals"]), len(dry_report["warnings"]), out))
        return
    overrides = _load_json(os.path.join(_here(), OVERRIDES_NAME), required=False)
    if not overrides.get("decided_by") or overrides.get("option") != "B":
        _stop(run, "NOT_DECIDED|overrides need decided_by and option=B (Gary's pick)")
    if not dry_report["apply_ready"]:
        _stop(run, "REFUSED|" + " || ".join(dry_report["refusals"]))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|" + json.dumps(_census()))
    seq_path = sequence.get_path_name().split(".")[0]
    backup = _backup(n, run)
    copied = _copy_into(backup, [_content_file(seq_path), _content_file(EXPECTED_WORLD, ".umap"),
                                 _content_file(SHOW_PATH)], run)
    exit_cam = gathered["exit_camera"]
    record = {"schema_version": 1, "run": run, "scene": n, "world": EXPECTED_WORLD,
              "sequence": seq_path, "cue_guid": _guid(gathered["cue"].get_editor_property("cue_guid")),
              "backup": backup, "backup_files": copied, "applied": False,
              "plan_report": plan["report"], "root_cuts_before": gathered["root_cuts"],
              "exit_camera_before": {"location": list(exit_cam.get_actor_location().to_tuple()),
                                     "rotation": [exit_cam.get_actor_rotation().roll,
                                                  exit_cam.get_actor_rotation().pitch,
                                                  exit_cam.get_actor_rotation().yaw]}}
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)

    # 1. The camera actor, attached to the root, saved at the FINAL pose.
    final = plan["camera_keys"][-1]
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    camera = subsystem.spawn_actor_from_class(unreal.CineCameraActor, root.get_actor_location(),
                                              root.get_actor_rotation(), False)
    camera.set_actor_label(camera_label)
    camera.tags = [unreal.Name(tag) for tag in tags]
    camera.attach_to_actor(root, unreal.Name("None"), unreal.AttachmentRule.KEEP_WORLD,
                           unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    camera.set_actor_relative_location(unreal.Vector(final[1], final[2], final[3]), False, True)
    camera.set_actor_relative_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False, True)
    component = camera.get_cine_camera_component()
    component.set_editor_property("current_focal_length", float(final[7]))
    focus = component.get_editor_property("focus_settings")
    focus.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    focus.set_editor_property("manual_focus_distance", float(final[8]))
    component.set_editor_property("focus_settings", focus)

    # 2. Bindings and keys in the Scene sequence.
    cam_binding = sequence.add_possessable(camera)
    comp_binding = sequence.add_possessable(component)
    comp_binding.set_parent(cam_binding)
    leaf_binding = sequence.add_possessable(leaf)
    start, end = plan["report"]["window"][0], gathered["scene_end"]
    cam_track = cam_binding.add_track(unreal.MovieScene3DTransformTrack)
    cam_track.set_display_name(TRACK_NAME)
    cam_section = cam_track.add_section()
    cam_section.set_range(start, end)
    _key_channels(cam_section, plan["camera_keys"], POSE_CHANNELS, run, "camera")
    leaf_track = leaf_binding.add_track(unreal.MovieScene3DTransformTrack)
    leaf_track.set_display_name(TRACK_NAME)
    leaf_section = leaf_track.add_section()
    leaf_section.set_range(plan["report"]["door_start_frame"], end)
    leaf_channels = _key_channels(leaf_section, plan["leaf_keys"], POSE_CHANNELS, run, "leaf")
    leaf_scale = leaf.root_component.get_editor_property("relative_scale3d")
    for name, value in (("Scale.X", leaf_scale.x), ("Scale.Y", leaf_scale.y), ("Scale.Z", leaf_scale.z)):
        if name not in leaf_channels:
            _stop(run, "CHANNELS_MISSING|leaf|" + name)
        leaf_channels[name].set_default(float(value))
    focus_track = comp_binding.add_track(unreal.MovieSceneFloatTrack)
    focus_track.set_property_name_and_path(unreal.Name("ManualFocusDistance"), "FocusSettings.ManualFocusDistance")
    focus_track.set_display_name(TRACK_NAME)
    focus_section = focus_track.add_section()
    focus_section.set_range(start, end)
    focus_channels = list(focus_section.get_all_channels())
    if len(focus_channels) != 1:
        _stop(run, "FOCUS_CHANNELS|%d" % len(focus_channels))
    for key in plan["camera_keys"]:
        focus_channels[0].add_key(unreal.FrameNumber(int(key[0])), float(key[8]),
                                  time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE,
                                  interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
    cut_tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    if len(cut_tracks) != 1:
        _stop(run, "CUT_TRACK_COUNT|%d" % len(cut_tracks))
    cut = cut_tracks[0].add_section()
    cut.set_camera_binding_id(sequence.get_binding_id(cam_binding))
    cut.set_range(start, plan["report"]["window"][1])  # ONE call; [a, b)
    record.update({"camera_label": camera_label,
                   "camera_binding_guid": _guid(cam_binding.get_id()),
                   "component_binding_guid": _guid(comp_binding.get_id()),
                   "leaf_binding_guid": _guid(leaf_binding.get_id()),
                   "cut_range": [start, plan["report"]["window"][1]]})
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)

    # 3. The builder's own rematch re-ranges the retained Exit after this cut.
    entry_label = "%s — Entry Handoff Camera" % gathered["cue_label"]
    entry = _one(_actors_by_label(), entry_label, run)
    entry_before = entry.get_actor_location()
    result = unreal.InfinityStageCameraPilotLibrary.match_named_scene_handoffs(
        gathered["show"], [gathered["cue"].get_editor_property("cue_guid")], 1)
    matched, match_report = result if isinstance(result, tuple) else (result, "")
    if not matched:
        _stop(run, "MATCH_FAILED|NOTHING SAVED; Don't-Save restart|" + str(match_report))
    if (entry.get_actor_location() - entry_before).length() > 0.5:
        _stop(run, "ENTRY_MOVED_ON_MATCH|NOTHING SAVED; Don't-Save restart")
    world_final = camera.get_actor_location()
    if (exit_cam.get_actor_location() - world_final).length() > 1.0:
        _stop(run, "EXIT_HOLD_NOT_FINAL_POSE|NOTHING SAVED; Don't-Save restart")
    gaps, overlaps = _cut_gaps(sequence)
    if gaps or overlaps:
        _stop(run, "CUT_COVERAGE|gaps=%r|overlaps=%r|NOTHING SAVED" % (gaps, overlaps))
    census = _census()
    expected = {"content": sorted([seq_path]), "maps": [EXPECTED_WORLD]}
    if census != expected:
        _stop(run, "UNEXPECTED_DIRTY|%s|NOTHING SAVED" % json.dumps(census))

    # 4. Save exactly the sequence and the level, then read back.
    if not unreal.EditorAssetLibrary.save_loaded_asset(sequence, False):
        _stop(run, "SEQUENCE_SAVE_FAILED")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        _stop(run, "LEVEL_SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|" + json.dumps(_census()))
    names = _binding_names(sequence)
    for key in ("camera_binding_guid", "component_binding_guid", "leaf_binding_guid"):
        if record[key] not in names:
            _stop(run, "READBACK_BINDING_MISSING|" + key)
    for section, keys, label in ((cam_section, plan["camera_keys"], "camera"),
                                 (leaf_section, plan["leaf_keys"], "leaf")):
        channels = {str(channel.channel_name): channel for channel in section.get_all_channels()}
        for name, index in POSE_CHANNELS.items():
            read = list(channels[name].get_keys())
            if len(read) != len(keys) or abs(float(read[-1].get_value()) - float(keys[-1][index])) > 1.0e-3:
                _stop(run, "READBACK_KEYS|%s|%s" % (label, name))
    cut_rows = _root_cut_rows(sequence, names)
    exit_rows = [row for row in cut_rows if "Exit Handoff Camera" in row["label"]]
    if len(exit_rows) != 1 or exit_rows[0]["start"] != plan["report"]["window"][1]:
        _stop(run, "READBACK_EXIT_RANGE|%r" % exit_rows)
    record.update({"applied": True, "root_cuts_after": cut_rows, "census_after": _census()})
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
    unreal.log("SCENE_EXIT_MOVE_APPLY_OK|run=%s|scene=%d|window=%r|backup=%s|record=%s|tests_required_singly="
               "InfinityStage.Editor.SceneCutBindingsResolve,InfinityStage.Editor.SavedMasterMatchesShow"
               % (run, n, plan["report"]["window"], backup, record_path))


def revert_move(n, run):
    record_path = os.path.join(_here(), RECORD_PATTERN % n)
    record = _load_json(record_path)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or int(record["scene"]) != n:
        _stop(run, "REVERT_RECORD_CONTEXT")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|" + json.dumps(_census()))
    sequence = unreal.load_asset(record["sequence"])
    show = unreal.load_asset(SHOW_PATH)
    cue, cue_label = _scene_cue(show, n, run)
    if _guid(cue.get_editor_property("cue_guid")) != record["cue_guid"]:
        _stop(run, "CUE_GUID_CHANGED")
    names = _binding_names(sequence)
    wanted = {record[key] for key in ("camera_binding_guid", "component_binding_guid", "leaf_binding_guid")}
    if not wanted <= set(names):
        _stop(run, "RECORDED_BINDINGS_MISSING|%r" % sorted(wanted - set(names)))
    backup = _backup(n, run + "-revert")
    _copy_into(backup, [_content_file(record["sequence"]), _content_file(EXPECTED_WORLD, ".umap")], run)
    removed_cut = 0
    for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for section in list(track.get_sections()):
            if _guid(section.get_camera_binding_id().get_editor_property("guid")) == record["camera_binding_guid"]:
                track.remove_section(section)
                removed_cut += 1
    if removed_cut != 1:
        _stop(run, "REVERT_CUT_COUNT|%d|NOTHING SAVED" % removed_cut)
    leaf_guid = record["leaf_binding_guid"]
    for binding in sequence.get_bindings():
        if _guid(binding.get_id()) == leaf_guid:
            # The leaf binding is ours alone (APPLY created it); remove it whole.
            binding.remove()
    for binding in sequence.get_bindings():
        if _guid(binding.get_id()) == record["component_binding_guid"]:
            binding.remove()
    for binding in sequence.get_bindings():
        if _guid(binding.get_id()) == record["camera_binding_guid"]:
            binding.remove()
    index = _actors_by_label()
    camera = _one(index, record["camera_label"], run)
    if not camera.actor_has_tag(CAMERA_TAGS[1] % n):
        _stop(run, "REVERT_CAMERA_TAG|NOTHING SAVED")
    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(camera)
    result = unreal.InfinityStageCameraPilotLibrary.match_named_scene_handoffs(show, [cue.get_editor_property("cue_guid")], 1)
    matched = result[0] if isinstance(result, tuple) else result
    if not matched:
        _stop(run, "REVERT_MATCH_FAILED|NOTHING SAVED; Don't-Save restart")
    gaps, overlaps = _cut_gaps(sequence)
    if gaps or overlaps:
        _stop(run, "REVERT_CUT_COVERAGE|gaps=%r|overlaps=%r|NOTHING SAVED" % (gaps, overlaps))
    after = _root_cut_rows(sequence, _binding_names(sequence))
    before = [{k: row[k] for k in ("label", "start", "end", "active")} for row in record["root_cuts_before"]]
    now = [{k: row[k] for k in ("label", "start", "end", "active")} for row in after]
    if sorted(now, key=json.dumps) != sorted(before, key=json.dumps):
        _stop(run, "REVERT_CUTS_DIFFER_FROM_RECORD|before=%r|now=%r|NOTHING SAVED" % (before, now))
    if not unreal.EditorAssetLibrary.save_loaded_asset(sequence, False):
        _stop(run, "SEQUENCE_SAVE_FAILED")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        _stop(run, "LEVEL_SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|" + json.dumps(_census()))
    if record["camera_label"] in _actors_by_label():
        _stop(run, "REVERT_CAMERA_REMAINS")
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("SCENE_EXIT_MOVE_REVERT_OK|run=%s|scene=%d|backup=%s|record=%s" % (run, n, backup, archived))


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    n = int(globals().get("SCENE_EXIT_MOVE_SCENE", 0))
    apply = bool(globals().get("SCENE_EXIT_MOVE_APPLY"))
    revert = bool(globals().get("SCENE_EXIT_MOVE_REVERT"))
    if not 1 <= n <= 6:
        _stop(run, "SCENE_NOT_SET")
    if apply and revert:
        _stop(run, "APPLY_AND_REVERT_BOTH_SET")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_IS_OPEN")  # an open Sequencer evaluates and dirties the map
    if revert:
        revert_move(n, run)
        return
    try:
        gathered = _gather(n, run)
        overrides = _load_json(os.path.join(_here(), OVERRIDES_NAME), required=False)
        params = {k: v for k, v in overrides.get("params", {}).items() if k in DEFAULTS}
        apply_move(n, gathered, not apply, params, run)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
