"""Extract the existing inner traveler as a standalone Unreal FBX asset."""

import os
from pathlib import Path

import bpy


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
BLEND_OUTPUT = OUTPUT_DIR / "CurtainTraveler_UE.blend"
FBX_OUTPUT = OUTPUT_DIR / "CurtainTraveler_UE.fbx"
PREVIEW_CLOSED = OUTPUT_DIR / "CurtainTraveler_preview_closed.png"
PREVIEW_OPEN = OUTPUT_DIR / "CurtainTraveler_preview_open.png"

SOURCE_INNER_START = 78
FRAME_OFFSET = SOURCE_INNER_START - 1
SOURCE_END = 210
FRAME_START = 1
FRAME_END = SOURCE_END - FRAME_OFFSET


def action_channelbags(action: bpy.types.Action):
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in getattr(strip, "channelbags", ()):
                yield channelbag


def trim_and_retime_action(
    action: bpy.types.Action,
) -> None:
    for channelbag in action_channelbags(action):
        for fcurve in list(channelbag.fcurves):
            if 'pose.bones["IN_' not in fcurve.data_path:
                channelbag.fcurves.remove(fcurve)
                continue

            for point in list(fcurve.keyframe_points):
                if point.co.x < SOURCE_INNER_START - 0.001:
                    fcurve.keyframe_points.remove(point)

            for point in fcurve.keyframe_points:
                point.co.x -= FRAME_OFFSET
                point.handle_left.x -= FRAME_OFFSET
                point.handle_right.x -= FRAME_OFFSET

            fcurve.update()

    action.name = "CURTAIN_Traveler_Open"
    action.use_fake_user = True
    if hasattr(action, "use_frame_range"):
        action.use_frame_range = True
        action.frame_start = FRAME_START
        action.frame_end = FRAME_END


def remove_outer_asset(armature: bpy.types.Object) -> None:
    outer = bpy.data.objects.get("SM_Curtain_Outer_MultiPinch")
    if outer is not None:
        bpy.data.objects.remove(outer, do_unlink=True)

    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in list(armature.data.edit_bones):
        if bone.name.startswith("OUT_"):
            armature.data.edit_bones.remove(bone)
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.select_set(False)


def rename_asset(
    armature: bpy.types.Object,
    inner_objects: list[bpy.types.Object],
) -> None:
    armature.name = "SK_Curtain_Traveler"
    armature.data.name = "SK_Curtain_Traveler_Skeleton"
    for obj in inner_objects:
        side = "L" if obj.name.endswith("_L") else "R"
        obj.name = f"SM_Curtain_Traveler_{side}"
        obj.data.name = f"SM_Curtain_Traveler_{side}_Mesh"

    armature["AssetPurpose"] = "Standalone two-panel inner traveler curtain"
    armature["Animation"] = (
        f"CURTAIN_Traveler_Open, frames {FRAME_START}-{FRAME_END}, 30 fps"
    )
    armature["UEImport"] = (
        "Import Skeletal Mesh + Animations; Morph Targets not required"
    )


def configure_timeline() -> None:
    scene = bpy.context.scene
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = 30
    for marker in list(scene.timeline_markers):
        scene.timeline_markers.remove(marker)
    scene.timeline_markers.new("Traveler Closed", frame=FRAME_START)
    scene.timeline_markers.new("Traveler Fully Open", frame=FRAME_END - 10)


def export_fbx(
    armature: bpy.types.Object,
    inner_objects: list[bpy.types.Object],
) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in [armature, *inner_objects]:
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
    armature = bpy.data.objects["SK_Curtain"]
    inner_objects = [
        bpy.data.objects["SM_Curtain_Inner_L"],
        bpy.data.objects["SM_Curtain_Inner_R"],
    ]
    action = armature.animation_data.action
    if action is None:
        raise RuntimeError("The source curtain armature has no active action")

    trim_and_retime_action(action)
    remove_outer_asset(armature)
    rename_asset(armature, inner_objects)
    configure_timeline()

    scene = bpy.context.scene
    scene.frame_set(FRAME_START)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT), check_existing=False)

    export_fbx(armature, inner_objects)
    render_preview(FRAME_START, PREVIEW_CLOSED)
    render_preview(FRAME_END, PREVIEW_OPEN)

    scene.frame_set(FRAME_START)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT), check_existing=False)

    print("TRAVELER_BUILD_COMPLETE")
    print(f"BLEND={BLEND_OUTPUT}")
    print(f"FBX={FBX_OUTPUT}")
    print(f"ACTION={action.name}")
    print(f"FRAMES={FRAME_START}-{FRAME_END}@{scene.render.fps}fps")
    print(f"OBJECTS={[armature.name, *[obj.name for obj in inner_objects]]}")
    print(f"BONES={len(armature.data.bones)}")


if __name__ == "__main__":
    main()
