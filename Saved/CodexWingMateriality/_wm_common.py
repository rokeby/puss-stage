"""Shared helpers for the Wing materiality scripts (loaded by path inside Unreal).

Every mutating script must call editor_ready() first: Puss serves MCP on 8010 and
MHFat on 8000, and a port mix-up would otherwise edit the wrong project silently.
"""
import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OUT_DIR = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexWingMateriality",
)
MEL = unreal.MaterialEditingLibrary


def require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def pkg(v):
    if v is None:
        return None
    return v.get_path_name().split(".", 1)[0] if hasattr(v, "get_path_name") else str(v).split(".", 1)[0]


def dirty():
    return sorted({pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
                  | {pkg(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()})


def editor_ready():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None, "No editor world")
    require(world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD,
            f"Unexpected world {world.get_path_name()} - wrong editor or port?")
    require(editor.get_game_world() is None, "PIE/SIE is active")
    return editor


def write_json(name, payload):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, sort_keys=True, default=str)


def read_json(name):
    with open(os.path.join(OUT_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


def passage_actor(number):
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    found = [a for a in sub.get_all_level_actors()
             if a.get_class().get_name() == "InfinityStagePassageActor"
             and a.get_actor_label().startswith(f"Passage {number:02d}")]
    require(len(found) == 1, f"Expected one Passage {number:02d} actor, found {len(found)}")
    return found[0]


def passage_camera(number):
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rigs = [a for a in sub.get_all_level_actors()
            if a.get_class().get_name() == "InfinityStageCameraRig"
            and a.get_actor_label().startswith(f"Passage {number:02d}")]
    require(len(rigs) == 1, f"Expected one Passage {number:02d} camera rig, found {len(rigs)}")
    return rigs[0].get_editor_property("camera")


def component_for_mesh(actor, mesh_path):
    for comp in actor.get_components_by_class(unreal.InstancedStaticMeshComponent):
        if pkg(comp.get_editor_property("static_mesh")) == mesh_path:
            return comp
    raise RuntimeError(f"No managed ISM for {mesh_path} on {actor.get_actor_label()}")


def panel_view(comp, near, distance_cm, lateral_deg=25.0, lift_cm=0.0):
    """Camera location/rotation looking at the ISM instance nearest `near`.

    Stands `distance_cm` off the panel face on the side facing `near`, swung
    `lateral_deg` off the normal so relief reads under grazing light.
    """
    mesh = comp.get_editor_property("static_mesh")
    box = mesh.get_bounding_box()
    local_centre = (box.min + box.max) * 0.5
    best = None
    for i in range(comp.get_instance_count()):
        xf = comp.get_instance_transform(i, True)
        centre = unreal.MathLibrary.transform_location(xf, local_centre)
        d = (centre - near).length()
        if best is None or d < best[0]:
            best = (d, i, xf, centre)
    _, index, xf, centre = best
    normal = xf.rotation.rotate_vector(unreal.Vector(1.0, 0.0, 0.0))
    normal.normalize()
    if normal.dot(near - centre) < 0.0:
        normal = normal * -1.0
    up = unreal.Vector(0.0, 0.0, 1.0)
    side = normal.cross(up)
    if side.length() < 1e-3:
        side = unreal.Vector(1.0, 0.0, 0.0)
    side.normalize()
    a = math.radians(lateral_deg)
    offset = normal * (math.cos(a) * distance_cm) + side * (math.sin(a) * distance_cm)
    loc = centre + offset + up * lift_cm
    look = centre - loc
    rot = unreal.MathLibrary.find_look_at_rotation(loc, centre)
    return {"index": index, "centre": centre, "location": loc, "rotation": rot, "look": look}


def save_viewport(name="viewport_restore.json"):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    info = editor.get_level_viewport_camera_info()
    loc, rot = info[-2], info[-1]
    write_json(name, {"loc": [loc.x, loc.y, loc.z], "rot": [rot.roll, rot.pitch, rot.yaw]})


def restore_viewport(name="viewport_restore.json"):
    data = read_json(name)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    loc = unreal.Vector(*data["loc"])
    rot = unreal.Rotator(roll=data["rot"][0], pitch=data["rot"][1], yaw=data["rot"][2])
    editor.set_level_viewport_camera_info(loc, rot)


def shoot(name, loc, rot, w=1920, h=1080):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    editor.set_level_viewport_camera_info(loc, rot)
    unreal.AutomationLibrary.take_high_res_screenshot(w, h, name)
