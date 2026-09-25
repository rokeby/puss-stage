"""Upgrade the standalone traveler with denser, FBX-safe fabric motion."""

import os
from pathlib import Path
import math

import bpy
from mathutils import Vector


def _project_root() -> Path:
    """Locate the project without a hardcoded user path.

    Blender sets __file__ when run as `blender --python <script>`, which is how
    these are invoked. PUSS_PROJECT_ROOT overrides it for the text-editor case,
    where __file__ is not defined.
    """
    override = os.environ.get("PUSS_PROJECT_ROOT")
    if override:
        return Path(override)
    try:
        return Path(__file__).resolve().parents[1]
    except NameError as exc:  # pragma: no cover - Blender text editor only
        raise SystemExit(
            "Cannot locate the project. Set PUSS_PROJECT_ROOT to the PussStage folder."
        ) from exc


PROJECT_ROOT = _project_root()
OUTPUT_DIR = PROJECT_ROOT / "DerivedAssets" / "CurtainAnim"
BLEND_OUTPUT = OUTPUT_DIR / "CurtainTraveler_Physics_UE.blend"
FBX_OUTPUT = OUTPUT_DIR / "CurtainTraveler_Physics_UE.fbx"
PREVIEW_CLOSED = OUTPUT_DIR / "CurtainTraveler_Physics_preview_closed.png"
PREVIEW_MOTION = OUTPUT_DIR / "CurtainTraveler_Physics_preview_motion.png"
PREVIEW_OPEN = OUTPUT_DIR / "CurtainTraveler_Physics_preview_open.png"

FRAME_START = 1
FRAME_MOTION_START = 10
FRAME_OPEN = 170
FRAME_END = 180
FPS = 30

CURTAIN_TOP = 6.40
CURTAIN_BOTTOM = 0.12
HALF_WIDTH = 6.05
INNER_COLUMNS = 17
INNER_LEVELS = 5


def rebuild_armature(armature: bpy.types.Object) -> None:
    scene = bpy.context.scene
    scene.frame_set(FRAME_START)

    old_action = (
        armature.animation_data.action
        if armature.animation_data is not None
        else None
    )
    if armature.animation_data is not None:
        armature.animation_data.action = None
    if old_action is not None:
        bpy.data.actions.remove(old_action)

    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")

    for bone in list(armature.data.edit_bones):
        if bone.name != "root":
            armature.data.edit_bones.remove(bone)
    root = armature.data.edit_bones["root"]

    for side_name, sign in (("L", -1.0), ("R", 1.0)):
        for column in range(INNER_COLUMNS):
            s = column / (INNER_COLUMNS - 1)
            x = sign * (0.025 + s * (HALF_WIDTH - 0.025))
            for level in range(INNER_LEVELS):
                t = level / (INNER_LEVELS - 1)
                z = CURTAIN_TOP - t * (CURTAIN_TOP - CURTAIN_BOTTOM)
                bone = armature.data.edit_bones.new(
                    f"IN_{side_name}_C{column:02d}_L{level:02d}"
                )
                bone.head = (x, 0.16, z)
                bone.tail = (x, 0.16, z + 0.16)
                bone.parent = root
                bone.use_connect = False

    bpy.ops.object.mode_set(mode="OBJECT")
    armature.select_set(False)


def reweight_panel(obj: bpy.types.Object, side_name: str) -> None:
    for group in list(obj.vertex_groups):
        obj.vertex_groups.remove(group)

    groups = {
        (column, level): obj.vertex_groups.new(
            name=f"IN_{side_name}_C{column:02d}_L{level:02d}"
        )
        for column in range(INNER_COLUMNS)
        for level in range(INNER_LEVELS)
    }

    for vertex in obj.data.vertices:
        s = (abs(vertex.co.x) - 0.025) / (HALF_WIDTH - 0.025)
        s = max(0.0, min(1.0, s))
        v = (CURTAIN_TOP - vertex.co.z) / (CURTAIN_TOP - CURTAIN_BOTTOM)
        v = max(0.0, min(1.0, v))

        column_position = s * (INNER_COLUMNS - 1)
        level_position = v * (INNER_LEVELS - 1)
        c0 = int(math.floor(column_position))
        l0 = int(math.floor(level_position))
        c1 = min(c0 + 1, INNER_COLUMNS - 1)
        l1 = min(l0 + 1, INNER_LEVELS - 1)
        fc = column_position - c0
        fl = level_position - l0

        for column, level, weight in (
            (c0, l0, (1.0 - fc) * (1.0 - fl)),
            (c1, l0, fc * (1.0 - fl)),
            (c0, l1, (1.0 - fc) * fl),
            (c1, l1, fc * fl),
        ):
            if weight > 1.0e-6:
                groups[(column, level)].add(
                    [vertex.index], weight, "REPLACE"
                )


def world_to_bone_local(
    pose_bone: bpy.types.PoseBone,
    world_vector: Vector,
) -> Vector:
    return pose_bone.bone.matrix_local.to_3x3().inverted() @ world_vector


def key_transform(
    pose_bone: bpy.types.PoseBone,
    frame: int,
    location: Vector,
    rotation: Vector,
) -> None:
    pose_bone.location = location
    pose_bone.rotation_mode = "XYZ"
    pose_bone.rotation_euler = rotation
    pose_bone.keyframe_insert(
        data_path="location", frame=frame, group=pose_bone.name
    )
    pose_bone.keyframe_insert(
        data_path="rotation_euler", frame=frame, group=pose_bone.name
    )


def action_fcurves(action: bpy.types.Action):
    if hasattr(action, "fcurves"):
        yield from action.fcurves
        return
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in getattr(strip, "channelbags", ()):
                yield from channelbag.fcurves


def animate_physics(armature: bpy.types.Object) -> bpy.types.Action:
    action = bpy.data.actions.new("CURTAIN_Traveler_Physics_Open")
    armature.animation_data_create()
    armature.animation_data.action = action
    zero = Vector((0.0, 0.0, 0.0))

    for side_name, sign in (("L", -1.0), ("R", 1.0)):
        for column in range(INNER_COLUMNS):
            s = column / (INNER_COLUMNS - 1)
            x_rest_abs = 0.025 + s * (HALF_WIDTH - 0.025)
            x_open_abs = 4.56 + 1.36 * s
            panel_phase = 2.0 * math.pi * s

            for level in range(INNER_LEVELS):
                t = level / (INNER_LEVELS - 1)
                pose_bone = armature.pose.bones[
                    f"IN_{side_name}_C{column:02d}_L{level:02d}"
                ]

                fold_depth = 0.15 + 0.23 * t
                final_world = Vector(
                    (
                        sign * (x_open_abs - x_rest_abs),
                        fold_depth * math.cos(math.pi * column)
                        + 0.055 * math.sin(panel_phase + 1.6 * t),
                        -0.075
                        * t
                        * (0.45 + 0.55 * math.sin(math.pi * s)),
                    )
                )
                rotation_world = Vector(
                    (
                        math.radians(1.8)
                        * math.sin(panel_phase + 0.8 * t)
                        * t,
                        math.radians(0.8)
                        * math.cos(panel_phase)
                        * t,
                        sign
                        * math.radians(2.8)
                        * math.sin(panel_phase)
                        * (0.25 + 0.75 * t),
                    )
                )
                final_location = world_to_bone_local(
                    pose_bone, final_world
                )
                final_rotation = world_to_bone_local(
                    pose_bone, rotation_world
                )

                drag_world = Vector(
                    (
                        -sign
                        * 0.30
                        * t
                        * (1.0 - 0.25 * s),
                        -0.13
                        * math.sin(panel_phase + 1.1 * t)
                        * t,
                        -0.16 * t,
                    )
                )
                ripple_world = Vector(
                    (
                        -sign * 0.10 * t * math.sin(math.pi * s),
                        0.18
                        * math.sin(2.0 * panel_phase + 2.4 * t)
                        * t,
                        -0.075
                        * math.cos(panel_phase + 1.7 * t)
                        * t,
                    )
                )
                overshoot_world = Vector(
                    (
                        sign * 0.13 * t,
                        0.15
                        * math.sin(panel_phase + 0.9)
                        * (0.25 + 0.75 * t),
                        0.055 * t,
                    )
                )
                drag = world_to_bone_local(pose_bone, drag_world)
                ripple = world_to_bone_local(pose_bone, ripple_world)
                overshoot = world_to_bone_local(
                    pose_bone, overshoot_world
                )

                delay = int(
                    round(
                        5.0 * t
                        + 4.0 * (1.0 - s)
                        + 1.5 * abs(0.5 - s)
                    )
                )
                acceleration_frame = 38 + delay
                mid_frame = 78 + delay
                near_open_frame = 112 + delay
                overshoot_frame = 132 + delay
                rebound_frame = 146 + min(delay, 8)
                settle_frame = 158 + min(delay, 5)

                key_transform(
                    pose_bone, FRAME_START, zero.copy(), zero.copy()
                )
                key_transform(
                    pose_bone, FRAME_MOTION_START, zero.copy(), zero.copy()
                )
                key_transform(
                    pose_bone,
                    acceleration_frame,
                    final_location * 0.18 + drag * 0.82,
                    final_rotation * 0.10,
                )
                key_transform(
                    pose_bone,
                    mid_frame,
                    final_location * 0.58 + drag * 0.42 + ripple * 0.34,
                    final_rotation * 0.44,
                )
                key_transform(
                    pose_bone,
                    near_open_frame,
                    final_location * 0.90 + ripple,
                    final_rotation * 0.82,
                )
                key_transform(
                    pose_bone,
                    overshoot_frame,
                    final_location * 1.025 + overshoot,
                    final_rotation * 1.10,
                )
                key_transform(
                    pose_bone,
                    rebound_frame,
                    final_location * 0.988 - overshoot * 0.42,
                    final_rotation * 0.965,
                )
                key_transform(
                    pose_bone,
                    settle_frame,
                    final_location * 1.004 + overshoot * 0.12,
                    final_rotation * 1.008,
                )
                key_transform(
                    pose_bone,
                    FRAME_OPEN,
                    final_location,
                    final_rotation,
                )
                key_transform(
                    pose_bone,
                    FRAME_END,
                    final_location,
                    final_rotation,
                )

    for fcurve in action_fcurves(action):
        for point in fcurve.keyframe_points:
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"

    action.use_fake_user = True
    if hasattr(action, "use_frame_range"):
        action.use_frame_range = True
        action.frame_start = FRAME_START
        action.frame_end = FRAME_END
    return action


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    for marker in list(scene.timeline_markers):
        scene.timeline_markers.remove(marker)
    scene.timeline_markers.new("Traveler Closed", frame=FRAME_START)
    scene.timeline_markers.new("Traveler Begins", frame=FRAME_MOTION_START)
    scene.timeline_markers.new("Traveler Settled", frame=FRAME_OPEN)


def export_fbx(
    armature: bpy.types.Object,
    panels: list[bpy.types.Object],
) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in [armature, *panels]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature

    bpy.ops.export_scene.fbx(
        filepath=str(FBX_OUTPUT),
        check_existing=False,
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        use_mesh_modifiers=True,
        use_mesh_modifiers_render=True,
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Y",
        axis_up="Z",
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        add_leaf_bones=False,
        use_armature_deform_only=True,
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=True,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        path_mode="AUTO",
        embed_textures=False,
        use_tspace=True,
    )


def render_preview(frame: int, path: Path) -> None:
    scene = bpy.context.scene
    scene.frame_set(frame)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    armature = bpy.data.objects["SK_Curtain_Traveler"]
    panels = [
        bpy.data.objects["SM_Curtain_Traveler_L"],
        bpy.data.objects["SM_Curtain_Traveler_R"],
    ]

    rebuild_armature(armature)
    reweight_panel(panels[0], "L")
    reweight_panel(panels[1], "R")
    action = animate_physics(armature)

    armature.name = "SK_Curtain_Traveler_Physics"
    armature.data.name = "SK_Curtain_Traveler_Physics_Skeleton"
    armature["AssetPurpose"] = (
        "Traveler curtain with FBX-baked secondary fabric motion"
    )
    armature["Animation"] = (
        f"{action.name}, frames {FRAME_START}-{FRAME_END}, {FPS} fps"
    )
    armature["Physics"] = (
        "Five vertical tiers; track lead; hem drag; traveling ripple; "
        "overshoot; rebound; damped settling"
    )

    configure_scene()
    scene = bpy.context.scene
    scene.frame_set(FRAME_START)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT), check_existing=False)

    export_fbx(armature, panels)
    render_preview(FRAME_START, PREVIEW_CLOSED)
    render_preview(112, PREVIEW_MOTION)
    render_preview(FRAME_END, PREVIEW_OPEN)

    scene.frame_set(FRAME_START)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT), check_existing=False)

    print("TRAVELER_PHYSICS_BUILD_COMPLETE")
    print(f"BLEND={BLEND_OUTPUT}")
    print(f"FBX={FBX_OUTPUT}")
    print(f"ACTION={action.name}")
    print(f"FRAMES={FRAME_START}-{FRAME_END}@{FPS}fps")
    print(f"BONES={len(armature.data.bones)}")


if __name__ == "__main__":
    main()
