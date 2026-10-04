"""READ-ONLY P04 bay-3 line traces for W&T (TUNE 4 add-on, specs/LIGHTING_LOOKS_P04_TUNE1.md:93-96).

Runs INSIDE the owned tune-4 recording PIE. It never begins or ends PIE, never
pauses, scrubs or plays the transport, never quits the editor and writes no
asset or level: it only registers a post-tick callback that waits for the
first PIE tick at or after Master frame 25,433,910 (LightingLooks
20261003_213320 bay-3 frame), then traces from the player camera through
screen pixels (900,300) and (1100,300) of a 1280x720 view on the Visibility
channel and writes Saved/CodexConductor/p04_bay3_trace.json.

Ownership pattern: lighting_looks_begin_owned_play.py / lighting_looks_p04_driver.py
(owner flag Saved/CodexConductor/pie_recording_owner.json must be active for
the run named by lighting_looks_current_run.json). Arm it before or during
that run's PIE; if ownership drops or the frame has already passed it stops
without tracing.

Declared limits, checked and logged per run:
* Wing panels default to Collision=NoCollision (InfinityStageTypes.h:621); a
  Visibility trace then passes through the wing and reports what is behind.
  The Show's own Collision setting for the bay-3 panels is logged.
* A line trace hits collision geometry, not a masked material's opacity, so a
  tarp hole does not let a trace through.
* Pixels are deprojected from the camera manager's POV with a 1280x720 aspect
  (primary), and cross-checked with GameplayStatics.deproject_screen_to_world
  at the live viewport size (scaled pixel); both rays are logged.
"""
import builtins
import datetime
import json
import math
import pathlib
import time
import traceback

import unreal

BASE = pathlib.Path("E:/PussStage/Saved/CodexConductor")
CURRENT = BASE / "lighting_looks_current_run.json"
OWNER = BASE / "pie_recording_owner.json"
OUT = BASE / "p04_bay3_trace.json"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HANDLE_NAME = "PUSS_P04_BAY3_TRACE_HANDLE"
STATE_NAME = "PUSS_P04_BAY3_TRACE_STATE"
TARGET_FRAME = 25433910
VIEW = (1280, 720)
PIXELS = ((900, 300), (1100, 300))
TRACE_LENGTH_CM = 100000.0
BAY3_CUE_GUID = "A6F398A47249E3A73AF4EAA286F6886C"
P04_FIRST_CUE_GUID = "75FD539B104815DC315DBB85D6E69939"
TIMEOUT_S = 900.0
ATTACHMENT_TAG = "InfinityStage.Attachment."


def guid_text(value):
    return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()


def vec(value):
    return [float(value.x), float(value.y), float(value.z)]


def path_of(value):
    if value is None:
        return None
    getter = getattr(value, "get_path_name", None)
    return str(getter()) if callable(getter) else str(value)


def owner_matches():
    current = json.loads(CURRENT.read_text(encoding="utf-8"))
    owner = json.loads(OWNER.read_text(encoding="utf-8"))
    return (bool(owner.get("active")) and owner.get("run_dir") == current.get("run_dir"),
            current, owner)


def finish(state, status, error=None):
    state["status"] = status
    state["finished_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
    if error:
        state["errors"].append(error)
    OUT.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    handle = getattr(builtins, HANDLE_NAME, None)
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        delattr(builtins, HANDLE_NAME)
    marker = "P04_BAY3_TRACE_OK" if status == "traced" else "P04_BAY3_TRACE_STOPPED"
    unreal.log("%s|run=%s|status=%s|hits=%d|frame=%s|out=%s" % (
        marker, state["run_id"], status,
        sum(1 for row in state["traces"] if row.get("hit")),
        state.get("actual_frame"), OUT.as_posix()))


def manual_ray(location, rotation, fov_deg, pixel):
    """Pinhole ray for pixel centre on a VIEW-sized image; UE fov is horizontal."""
    ndc_x = (pixel[0] + 0.5) / VIEW[0] * 2.0 - 1.0
    ndc_y = 1.0 - (pixel[1] + 0.5) / VIEW[1] * 2.0
    tan_h = math.tan(math.radians(fov_deg) / 2.0)
    tan_v = tan_h * VIEW[1] / VIEW[0]
    forward = vec(unreal.MathLibrary.get_forward_vector(rotation))
    right = vec(unreal.MathLibrary.get_right_vector(rotation))
    up = vec(unreal.MathLibrary.get_up_vector(rotation))
    direction = [forward[i] + ndc_x * tan_h * right[i] + ndc_y * tan_v * up[i] for i in range(3)]
    norm = math.sqrt(sum(v * v for v in direction))
    return [v / norm for v in direction]


def deproject_ray(controller, pixel):
    try:
        size = controller.get_viewport_size()
        width, height = (int(size[0]), int(size[1])) if isinstance(size, tuple) else (0, 0)
        scaled = unreal.Vector2D(pixel[0] * width / VIEW[0], pixel[1] * height / VIEW[1])
        result = unreal.GameplayStatics.deproject_screen_to_world(controller, scaled)
        vectors = [item for item in (result if isinstance(result, tuple) else (result,))
                   if hasattr(item, "x") and hasattr(item, "z")]
        return {"viewport": [width, height], "scaled_pixel": [scaled.x, scaled.y],
                "raw": str(result),
                "direction": vec(vectors[-1]) if len(vectors) >= 2 else None}
    except Exception as error:  # noqa: BLE001 - cross-check only.
        return {"error": "%s: %s" % (type(error).__name__, error)}


def hit_fields(result):
    """Unwrap line_trace_single's HitResult across wrapper variants (order: BreakHitResult)."""
    hit = None
    for item in (result if isinstance(result, tuple) else (result,)):
        if item is not None and item.__class__.__name__ == "HitResult":
            hit = item
    if hit is None:
        return None, str(result)
    parts = hit.to_tuple()
    names = ("blocking_hit", "initial_overlap", "time", "distance", "location",
             "impact_point", "normal", "impact_normal", "phys_mat", "hit_actor",
             "hit_component", "hit_bone_name", "bone_name", "hit_item",
             "element_index", "face_index", "trace_start", "trace_end")
    return dict(zip(names, parts)), str(hit)


def show_index_by_guid(show):
    return {guid_text(cue.get_editor_property("cue_guid")): (index, cue)
            for index, cue in enumerate(show.get_editor_property("cues"))}


def p04_span(show, cues_by_guid):
    rows = [row for row in show.get_editor_property("passage_settings")
            if guid_text(row.get_editor_property("first_cue_guid")) == P04_FIRST_CUE_GUID]
    if len(rows) != 1:
        return []
    first = cues_by_guid[P04_FIRST_CUE_GUID][0]
    last = cues_by_guid[guid_text(rows[0].get_editor_property("last_cue_guid"))][0]
    return [guid for guid, (index, unused) in cues_by_guid.items() if first <= index <= last]


def resolve_cue(actor, mesh_path, show, cues_by_guid, span):
    tags = [str(tag) for tag in actor.get_editor_property("tags")] if actor else []
    for tag in tags:
        if tag.startswith(ATTACHMENT_TAG):
            cue_guid, attachment_guid = tag[len(ATTACHMENT_TAG):].split("|", 1)
            index = cues_by_guid.get(cue_guid, (None, None))[0]
            return {"method": "declaration: attachment actor tag "
                              "(InfinityStagePassageActor.cpp:967-970)",
                    "cue_guid": cue_guid, "cue_index": index,
                    "attachment_guid": attachment_guid}
    if not mesh_path:
        return {"method": "unresolved: no attachment tag and no mesh"}
    candidates = []
    for guid in span:
        index, cue = cues_by_guid[guid]
        pair = cue.get_editor_property("wing_pair")
        for side in ("left", "right"):
            panel_mesh = path_of(pair.get_editor_property(side).get_editor_property("mesh"))
            if panel_mesh and panel_mesh.split(".", 1)[0] == mesh_path.split(".", 1)[0]:
                candidates.append({"cue_guid": guid, "cue_index": index, "side": side,
                                   "label": str(cue.get_editor_property("label"))})
    return {"method": "inferred: P04 cues whose wing panel uses the hit mesh "
                      "(ISM instance-to-cue map is not exposed to Python)",
            "candidates": candidates}


def describe_hit(fields, show, cues_by_guid, span):
    actor = fields.get("hit_actor")
    component = fields.get("hit_component")
    mesh = None
    material0 = None
    collision = None
    if component is not None:
        static_mesh = getattr(component, "static_mesh", None)
        if static_mesh is None:
            try:
                static_mesh = component.get_editor_property("static_mesh")
            except Exception:  # noqa: BLE001 - not a mesh component.
                static_mesh = None
        mesh = path_of(static_mesh)
        try:
            material0 = path_of(component.get_material(0))
        except Exception as error:  # noqa: BLE001
            material0 = "ERR %s" % type(error).__name__
        try:
            collision = str(component.get_collision_enabled())
        except Exception:  # noqa: BLE001
            collision = None
    return {
        "hit": bool(fields.get("blocking_hit")),
        "distance_cm": float(fields.get("distance") or 0.0),
        "impact_point": vec(fields["impact_point"]) if fields.get("impact_point") else None,
        "actor_label": actor.get_actor_label() if actor else None,
        "actor_class": actor.get_class().get_name() if actor else None,
        "actor_tags": [str(tag) for tag in actor.get_editor_property("tags")] if actor else [],
        "component": component.get_name() if component else None,
        "component_class": component.get_class().get_name() if component else None,
        "component_collision": collision,
        "static_mesh": mesh,
        "material_slot0": material0,
        "hit_item": fields.get("hit_item"),
        "element_index": fields.get("element_index"),
        "face_index": fields.get("face_index"),
        "cue": resolve_cue(actor, mesh, show, cues_by_guid, span),
    }


def trace_now(world, state, frame):
    show = unreal.load_asset(SHOW_PATH)
    cues_by_guid = show_index_by_guid(show)
    span = p04_span(show, cues_by_guid)
    bay3_index, bay3 = cues_by_guid[BAY3_CUE_GUID]
    pair = bay3.get_editor_property("wing_pair")
    state["bay3_cue"] = {
        "guid": BAY3_CUE_GUID, "index": bay3_index, "label": str(bay3.get_editor_property("label")),
        "panel_collision": {side: str(pair.get_editor_property(side).get_editor_property("collision"))
                            for side in ("left", "right")},
        "panel_mesh": {side: path_of(pair.get_editor_property(side).get_editor_property("mesh"))
                       for side in ("left", "right")},
    }
    manager = unreal.GameplayStatics.get_player_camera_manager(world, 0)
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    location = manager.get_camera_location()
    rotation = manager.get_camera_rotation()
    fov = float(manager.get_fov_angle())
    state["actual_frame"] = frame
    state["error_frames"] = frame - TARGET_FRAME
    state["camera"] = {"location": vec(location),
                       "rotation_pyr": [float(rotation.pitch), float(rotation.yaw), float(rotation.roll)],
                       "fov_deg": fov,
                       "view_target": controller.get_view_target().get_actor_label()
                       if controller and controller.get_view_target() else None}
    for pixel in PIXELS:
        direction = manual_ray(location, rotation, fov, pixel)
        start = location
        end = unreal.Vector(location.x + direction[0] * TRACE_LENGTH_CM,
                            location.y + direction[1] * TRACE_LENGTH_CM,
                            location.z + direction[2] * TRACE_LENGTH_CM)
        result = unreal.SystemLibrary.line_trace_single(
            world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
            unreal.DrawDebugTrace.NONE, True)
        fields, raw = hit_fields(result)
        row = {"pixel": list(pixel), "view": list(VIEW), "channel": "Visibility (TraceTypeQuery1)",
               "ray_direction": direction, "deproject_cross_check": deproject_ray(controller, pixel),
               "raw": raw}
        if fields is None:
            row["hit"] = False
        else:
            row.update(describe_hit(fields, show, cues_by_guid, span))
        state["traces"].append(row)


def tick(_delta):
    state = getattr(builtins, STATE_NAME)
    if state.get("inside"):
        return
    state["inside"] = True
    try:
        if time.monotonic() - state["armed_monotonic"] > TIMEOUT_S:
            finish(state, "timed_out_no_trace")
            return
        matches, current, unused_owner = owner_matches()
        del unused_owner
        if not matches or current.get("run_id") != state["run_id"]:
            finish(state, "ownership_lost_no_trace")
            return
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if world is None:
            if state["pie_seen"]:
                finish(state, "pie_ended_before_target_no_trace")
            return
        state["pie_seen"] = True
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
        if len(roots) != 1 or not roots[0].transport:
            return
        frame = int(roots[0].transport.get_current_master_frame().value)
        if state["first_frame_seen"] is None:
            state["first_frame_seen"] = frame
            if frame > TARGET_FRAME:
                finish(state, "armed_after_target_no_trace")
                return
        if frame < TARGET_FRAME:
            return
        trace_now(world, state, frame)
        finish(state, "traced")
    except Exception:  # noqa: BLE001 - record and stop; never touch PIE.
        finish(state, "failed", traceback.format_exc())
    finally:
        state["inside"] = False


if hasattr(builtins, HANDLE_NAME):
    raise RuntimeError("a P04 bay-3 trace callback is already registered")
matches_now, current_now, owner_now = owner_matches()
if not matches_now:
    raise RuntimeError("owned recording PIE is not armed for the current run; refusing to arm the trace")
STATE = {
    "status": "armed",
    "read_only": True,
    "run_id": current_now["run_id"],
    "run_dir": current_now["run_dir"],
    "target_frame": TARGET_FRAME,
    "target_source": "LightingLooks 20261003_213320 bay-3 frame (spec :93-96)",
    "armed_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    "armed_monotonic": time.monotonic(),
    "pie_seen": False,
    "first_frame_seen": None,
    "traces": [],
    "errors": [],
    "inside": False,
}
setattr(builtins, STATE_NAME, STATE)
setattr(builtins, HANDLE_NAME, unreal.register_slate_post_tick_callback(tick))
unreal.log("P04_BAY3_TRACE_ARMED|run=%s|target=%d|pixels=%s|view=%dx%d" %
           (STATE["run_id"], TARGET_FRAME, PIXELS, VIEW[0], VIEW[1]))
