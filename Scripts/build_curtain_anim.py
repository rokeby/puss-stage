"""Build a multi-pinch, two-layer skeletal theatre curtain for Unreal.

This script is intended to run inside Blender 5.x:

    Blender -b CurtainAnim.blend --python build_curtain_anim.py

The source scene is treated as a starter only. The V2 output uses a continuous
outer contour curtain with several lift points and physics-inspired secondary
motion baked into an FBX-safe armature.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

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
BLEND_OUTPUT = OUTPUT_DIR / "CurtainAnim_TwoLayerPhysics_UE.blend"
FBX_OUTPUT = OUTPUT_DIR / "CurtainAnim_TwoLayerPhysics_UE.fbx"
PREVIEW_CLOSED = OUTPUT_DIR / "CurtainAnim_TwoLayerPhysics_preview_closed.png"
PREVIEW_OUTER = OUTPUT_DIR / "CurtainAnim_TwoLayerPhysics_preview_outer_open.png"
PREVIEW_OPEN = OUTPUT_DIR / "CurtainAnim_TwoLayerPhysics_preview_open.png"

FRAME_START = 1
FRAME_OUTER_START = 18
FRAME_OUTER_OVERSHOOT = 84
FRAME_OUTER_OPEN = 135
FRAME_INNER_START = 75
FRAME_INNER_OVERSHOOT = 198
FRAME_INNER_OPEN = 232
FRAME_END = 240

CURTAIN_TOP = 6.40
CURTAIN_BOTTOM = 0.12
HALF_WIDTH = 6.05


def clean_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.armatures,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.materials,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)

    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def make_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def relink_object(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for old_collection in list(obj.users_collection):
        old_collection.objects.unlink(obj)
    collection.objects.link(obj)


def set_input(node: bpy.types.Node, name: str, value) -> None:
    socket = node.inputs.get(name)
    if socket is not None:
        socket.default_value = value


def make_fabric_material(
    name: str,
    base_color: tuple[float, float, float, float],
    roughness: float,
    noise_scale: float,
    bump_strength: float,
    sheen: float,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (460, 0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (160, 0)
    set_input(principled, "Base Color", base_color)
    set_input(principled, "Roughness", roughness)
    set_input(principled, "Sheen Weight", sheen)
    set_input(principled, "Sheen Roughness", 0.65)

    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-470, -130)
    set_input(noise, "Scale", noise_scale)
    set_input(noise, "Detail", 3.0)
    set_input(noise, "Roughness", 0.68)

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-100, -115)
    set_input(bump, "Strength", bump_strength)
    set_input(bump, "Distance", 0.035)

    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return material


def make_simple_material(
    name: str,
    base_color: tuple[float, float, float, float],
    metallic: float = 0.0,
    roughness: float = 0.5,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = base_color
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        set_input(principled, "Base Color", base_color)
        set_input(principled, "Metallic", metallic)
        set_input(principled, "Roughness", roughness)
    return material


def create_armature(
    asset_collection: bpy.types.Collection,
    outer_columns: int,
    outer_levels: int,
    inner_columns: int,
    inner_levels: int,
) -> bpy.types.Object:
    arm_data = bpy.data.armatures.new("SK_Curtain_Skeleton")
    armature = bpy.data.objects.new("SK_Curtain", arm_data)
    asset_collection.objects.link(armature)
    armature.show_in_front = True

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    root = arm_data.edit_bones.new("root")
    root.head = (0.0, 0.0, 0.0)
    root.tail = (0.0, 0.0, 0.42)
    root.use_deform = False

    for column in range(outer_columns):
        u = column / (outer_columns - 1)
        x = -HALF_WIDTH + 2.0 * HALF_WIDTH * u
        for level in range(outer_levels):
            t = level / (outer_levels - 1)
            z = CURTAIN_TOP - t * (CURTAIN_TOP - CURTAIN_BOTTOM)
            bone = arm_data.edit_bones.new(f"OUT_C{column:02d}_L{level:02d}")
            bone.head = (x, -0.24, z)
            bone.tail = (x, -0.24, z + 0.16)
            bone.parent = root
            bone.use_connect = False

    for side_name, sign in (("L", -1.0), ("R", 1.0)):
        for column in range(inner_columns):
            s = column / (inner_columns - 1)
            x = sign * (0.025 + s * (HALF_WIDTH - 0.025))
            for level in range(inner_levels):
                t = level / (inner_levels - 1)
                z = CURTAIN_TOP - t * (CURTAIN_TOP - CURTAIN_BOTTOM)
                bone = arm_data.edit_bones.new(
                    f"IN_{side_name}_C{column:02d}_L{level:02d}"
                )
                bone.head = (x, 0.16, z)
                bone.tail = (x, 0.16, z + 0.16)
                bone.parent = root
                bone.use_connect = False

    bpy.ops.object.mode_set(mode="OBJECT")
    armature.select_set(False)
    return armature


def append_grid_weights(
    obj: bpy.types.Object,
    vertex_index: int,
    side_name: str,
    u: float,
    v: float,
    bone_columns: int,
    bone_levels: int,
    prefix: str,
) -> None:
    u_pos = max(0.0, min(bone_columns - 1.0, u * (bone_columns - 1)))
    v_pos = max(0.0, min(bone_levels - 1.0, v * (bone_levels - 1)))
    u0 = int(math.floor(u_pos))
    v0 = int(math.floor(v_pos))
    u1 = min(u0 + 1, bone_columns - 1)
    v1 = min(v0 + 1, bone_levels - 1)
    fu = u_pos - u0
    fv = v_pos - v0

    contributions = (
        (u0, v0, (1.0 - fu) * (1.0 - fv)),
        (u1, v0, fu * (1.0 - fv)),
        (u0, v1, (1.0 - fu) * fv),
        (u1, v1, fu * fv),
    )
    for column, level, weight in contributions:
        if weight <= 1.0e-6:
            continue
        group_name = f"{prefix}_{side_name}_C{column:02d}_L{level:02d}"
        group = obj.vertex_groups.get(group_name)
        if group is None:
            group = obj.vertex_groups.new(name=group_name)
        group.add([vertex_index], weight, "ADD")


def append_column_weights(
    obj: bpy.types.Object,
    vertex_index: int,
    side_name: str,
    u: float,
    bone_columns: int,
    prefix: str,
) -> None:
    u_pos = max(0.0, min(bone_columns - 1.0, u * (bone_columns - 1)))
    u0 = int(math.floor(u_pos))
    u1 = min(u0 + 1, bone_columns - 1)
    fu = u_pos - u0

    for column, weight in ((u0, 1.0 - fu), (u1, fu)):
        if weight <= 1.0e-6:
            continue
        group_name = f"{prefix}_{side_name}_C{column:02d}"
        group = obj.vertex_groups.get(group_name)
        if group is None:
            group = obj.vertex_groups.new(name=group_name)
        group.add([vertex_index], weight, "ADD")


def append_contour_weights(
    obj: bpy.types.Object,
    vertex_index: int,
    u: float,
    v: float,
    bone_columns: int,
    bone_levels: int,
) -> None:
    u_pos = max(0.0, min(bone_columns - 1.0, u * (bone_columns - 1)))
    v_pos = max(0.0, min(bone_levels - 1.0, v * (bone_levels - 1)))
    u0 = int(math.floor(u_pos))
    v0 = int(math.floor(v_pos))
    u1 = min(u0 + 1, bone_columns - 1)
    v1 = min(v0 + 1, bone_levels - 1)
    fu = u_pos - u0
    fv = v_pos - v0

    for column, level, weight in (
        (u0, v0, (1.0 - fu) * (1.0 - fv)),
        (u1, v0, fu * (1.0 - fv)),
        (u0, v1, (1.0 - fu) * fv),
        (u1, v1, fu * fv),
    ):
        if weight <= 1.0e-6:
            continue
        group_name = f"OUT_C{column:02d}_L{level:02d}"
        group = obj.vertex_groups.get(group_name)
        if group is None:
            group = obj.vertex_groups.new(name=group_name)
        group.add([vertex_index], weight, "ADD")


def create_contour_mesh(
    materials: tuple[
        bpy.types.Material,
        bpy.types.Material,
        bpy.types.Material,
    ],
    armature: bpy.types.Object,
    asset_collection: bpy.types.Collection,
    bone_columns: int,
    bone_levels: int,
) -> bpy.types.Object:
    name = "SM_Curtain_Outer_Detailed"
    columns = 129
    rows = 57
    pleat_count = 24.0
    vertices: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    faces: list[tuple[int, int, int, int]] = []

    for row in range(rows):
        v = row / (rows - 1)
        z = CURTAIN_TOP - v * (CURTAIN_TOP - CURTAIN_BOTTOM)
        for column in range(columns):
            u = column / (columns - 1)
            x = -HALF_WIDTH + 2.0 * HALF_WIDTH * u
            phase = 2.0 * math.pi * pleat_count * u
            depth_factor = 0.34 + 0.66 * math.sqrt(max(v, 0.0))
            cross_wrinkle = math.sin(7.0 * math.pi * v + 1.5 * math.sin(phase))
            diagonal_wrinkle = math.sin(
                13.0 * math.pi * v + 0.42 * phase
            )
            y = (
                -0.38
                + 0.315 * math.sin(phase) * depth_factor
                + 0.027 * cross_wrinkle * math.sin(math.pi * v)
                + 0.012 * diagonal_wrinkle * v
            )
            vertices.append((x, y, z))
            uvs.append((u, 1.0 - v))

    for row in range(rows - 1):
        for column in range(columns - 1):
            a = row * columns + column
            b = a + 1
            c = a + columns + 1
            d = a + columns
            faces.append((a, d, c, b))

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    asset_collection.objects.link(obj)

    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            uv_layer.data[loop_index].uv = uvs[vertex_index]

    obj.data.materials.append(materials[0])
    obj.data.materials.append(materials[1])
    obj.data.materials.append(materials[2])
    faces_per_row = columns - 1
    for polygon_index, polygon in enumerate(mesh.polygons):
        face_row = polygon_index // faces_per_row
        if face_row >= rows - 5:
            polygon.material_index = 2
        elif face_row >= rows - 13:
            polygon.material_index = 1
        else:
            polygon.material_index = 0
        polygon.use_smooth = True

    for row in range(rows):
        v = row / (rows - 1)
        for column in range(columns):
            u = column / (columns - 1)
            append_contour_weights(
                obj,
                row * columns + column,
                u,
                v,
                bone_columns,
                bone_levels,
            )

    obj.parent = armature
    armature_modifier = obj.modifiers.new("CurtainArmature", "ARMATURE")
    armature_modifier.object = armature
    armature_modifier.use_deform_preserve_volume = True

    subdivision = obj.modifiers.new("FabricSubdivision", "SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 1
    subdivision.render_levels = 1

    solidify = obj.modifiers.new("FabricThickness", "SOLIDIFY")
    solidify.thickness = 0.035
    solidify.offset = 0.0
    solidify.use_rim = True

    return obj


def create_panel_mesh(
    name: str,
    side_name: str,
    sign: float,
    columns: int,
    rows: int,
    y_base: float,
    pleat_count: float,
    pleat_depth: float,
    materials: tuple[bpy.types.Material, bpy.types.Material],
    armature: bpy.types.Object,
    asset_collection: bpy.types.Collection,
    bone_columns: int,
    bone_levels: int,
    prefix: str,
    outer_panel: bool,
) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    faces: list[tuple[int, int, int, int]] = []

    for row in range(rows):
        v = row / (rows - 1)
        z = CURTAIN_TOP - v * (CURTAIN_TOP - CURTAIN_BOTTOM)
        for column in range(columns):
            u = column / (columns - 1)
            x_abs = 0.025 + u * (HALF_WIDTH - 0.025)
            x = sign * x_abs
            phase = 2.0 * math.pi * pleat_count * u
            vertical_flutter = math.sin(v * math.pi * 5.0 + u * 1.7)
            depth_factor = 0.42 + 0.58 * math.sqrt(max(v, 0.0))
            y = (
                y_base
                + pleat_depth * math.sin(phase) * depth_factor
                + 0.025 * vertical_flutter * v
            )
            if outer_panel:
                y -= 0.025 * math.sin(math.pi * v) * math.cos(phase * 0.45)
            vertices.append((x, y, z))
            uvs.append((u if sign > 0 else 1.0 - u, 1.0 - v))

    for row in range(rows - 1):
        for column in range(columns - 1):
            a = row * columns + column
            b = a + 1
            c = a + columns + 1
            d = a + columns
            if sign > 0:
                faces.append((a, d, c, b))
            else:
                faces.append((a, b, c, d))

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    asset_collection.objects.link(obj)

    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            uv_layer.data[loop_index].uv = uvs[vertex_index]

    obj.data.materials.append(materials[0])
    obj.data.materials.append(materials[1])
    faces_per_row = columns - 1
    for polygon_index, polygon in enumerate(mesh.polygons):
        face_row = polygon_index // faces_per_row
        polygon.material_index = 1 if face_row >= rows - 4 else 0
        polygon.use_smooth = True

    for row in range(rows):
        v = row / (rows - 1)
        for column in range(columns):
            u = column / (columns - 1)
            vertex_index = row * columns + column
            if bone_levels > 1:
                append_grid_weights(
                    obj,
                    vertex_index,
                    side_name,
                    u,
                    v,
                    bone_columns,
                    bone_levels,
                    prefix,
                )
            else:
                append_column_weights(
                    obj,
                    vertex_index,
                    side_name,
                    u,
                    bone_columns,
                    prefix,
                )

    obj.parent = armature
    armature_modifier = obj.modifiers.new("CurtainArmature", "ARMATURE")
    armature_modifier.object = armature
    armature_modifier.use_deform_preserve_volume = True

    subdivision = obj.modifiers.new("FabricSubdivision", "SUBSURF")
    subdivision.subdivision_type = "CATMULL_CLARK"
    subdivision.levels = 1
    subdivision.render_levels = 1

    solidify = obj.modifiers.new("FabricThickness", "SOLIDIFY")
    solidify.thickness = 0.022 if outer_panel else 0.028
    solidify.offset = 0.0
    solidify.use_rim = True

    return obj


def key_pose_transform(
    pose_bone: bpy.types.PoseBone,
    frame: int,
    location: Vector,
    rotation: Vector,
) -> None:
    pose_bone.location = location
    pose_bone.rotation_mode = "XYZ"
    pose_bone.rotation_euler = rotation
    pose_bone.keyframe_insert(data_path="location", frame=frame, group=pose_bone.name)
    pose_bone.keyframe_insert(
        data_path="rotation_euler", frame=frame, group=pose_bone.name
    )


def smooth_piecewise(x: float, anchors: tuple[tuple[float, float], ...]) -> float:
    if x <= anchors[0][0]:
        return anchors[0][1]
    if x >= anchors[-1][0]:
        return anchors[-1][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if x0 <= x <= x1:
            alpha = (x - x0) / (x1 - x0)
            eased = 0.5 - 0.5 * math.cos(math.pi * alpha)
            return y0 * (1.0 - eased) + y1 * eased
    return anchors[-1][1]


def world_to_bone_local(
    pose_bone: bpy.types.PoseBone,
    location_world: Vector,
    rotation_world: Vector,
) -> tuple[Vector, Vector]:
    inverse_basis = pose_bone.bone.matrix_local.to_3x3().inverted()
    return inverse_basis @ location_world, inverse_basis @ rotation_world


def animate_armature(
    armature: bpy.types.Object,
    outer_columns: int,
    outer_levels: int,
    inner_columns: int,
    inner_levels: int,
) -> bpy.types.Action:
    action = bpy.data.actions.new("CURTAIN_TwoLayer_Physics_Open")
    armature.animation_data_create()
    armature.animation_data.action = action
    zero = Vector((0.0, 0.0, 0.0))

    bottom_profile = (
        (-HALF_WIDTH, 0.16),
        (-5.35, 0.28),
        (-4.76, 2.46),
        (-3.86, 1.20),
        (-3.08, 4.56),
        (-2.40, 3.42),
        (-1.28, 2.48),
        (0.00, 2.16),
        (1.28, 2.48),
        (2.40, 3.42),
        (3.08, 4.56),
        (3.86, 1.20),
        (4.76, 2.46),
        (5.35, 0.28),
        (HALF_WIDTH, 0.16),
    )
    pinch_specs = (
        (-4.76, 0.58, 0.30),
        (-3.08, 0.76, 0.34),
        (3.08, 0.76, 0.34),
        (4.76, 0.58, 0.30),
    )

    for column in range(outer_columns):
        u = column / (outer_columns - 1)
        x = -HALF_WIDTH + 2.0 * HALF_WIDTH * u
        target_bottom_z = smooth_piecewise(x, bottom_profile)
        lift_at_bottom = max(0.0, target_bottom_z - CURTAIN_BOTTOM)
        compression_amount = min(1.0, lift_at_bottom / 4.44)

        pinch_influences = [
            math.exp(-0.5 * ((x - pinch_x) / width) ** 2)
            for pinch_x, width, _strength in pinch_specs
        ]
        pinch_proximity = max(pinch_influences)
        swag_influence = math.exp(-0.5 * (x / 2.35) ** 2)
        fold_energy = max(
            pinch_proximity,
            0.88 * swag_influence,
            0.72 * compression_amount,
        )
        gather_x = sum(
            (pinch_x - x) * influence * strength
            for (pinch_x, _width, strength), influence in zip(
                pinch_specs, pinch_influences
            )
        )

        for level in range(outer_levels):
            t = level / (outer_levels - 1)
            pose_bone = armature.pose.bones[
                f"OUT_C{column:02d}_L{level:02d}"
            ]
            vertical_factor = t**1.30
            rest_z = CURTAIN_TOP - t * (CURTAIN_TOP - CURTAIN_BOTTOM)
            compression_exponent = 1.0 + 1.65 * compression_amount
            compressed_t = 1.0 - (1.0 - t) ** compression_exponent
            target_z = (
                CURTAIN_TOP
                + (target_bottom_z - CURTAIN_TOP) * compressed_t
            )
            target_z += (
                0.19
                * math.sin(4.0 * math.pi * t + 1.15 * math.sin(3.0 * math.pi * u))
                * fold_energy
                * math.sin(math.pi * t)
            )
            z_displacement = target_z - rest_z
            radial_fold = math.sin(
                2.0 * math.pi * (4.2 * u + 0.52 * t)
            )
            stacked_lobe = (
                (-0.39 if level % 2 == 0 else 0.035)
                * t**1.65
                * fold_energy
            )
            y_structure = (
                -0.18
                * radial_fold
                * math.sin(math.pi * t)
                * (0.32 + 0.68 * fold_energy)
                - 0.055 * math.cos(6.0 * math.pi * u) * vertical_factor
                + stacked_lobe
            )
            y_structure = max(-0.56, min(0.045, y_structure))
            open_world = Vector(
                (
                    gather_x * t**1.32,
                    y_structure,
                    z_displacement,
                )
            )
            rotation_world = Vector(
                (
                    math.radians(2.2)
                    * radial_fold
                    * math.sin(math.pi * t),
                    math.radians(5.0)
                    * math.sin(2.0 * math.pi * u)
                    * vertical_factor,
                    -math.radians(2.6)
                    * radial_fold
                    * vertical_factor,
                )
            )
            open_location, open_rotation = world_to_bone_local(
                pose_bone, open_world, rotation_world
            )

            delay = int(round((1.0 - pinch_proximity) * 7.0 + 7.0 * t))
            mid_frame = 52 + delay
            overshoot_frame = FRAME_OUTER_OVERSHOOT + delay
            rebound_frame = 103 + delay
            settle_frame = 117 + min(delay, 7)
            bounce_world = Vector(
                (
                    0.025
                    * math.sin(5.0 * math.pi * u)
                    * vertical_factor,
                    -0.11 * radial_fold * vertical_factor,
                    0.16
                    * (0.35 + 0.65 * fold_energy)
                    * vertical_factor,
                )
            )
            bounce_local, _unused = world_to_bone_local(
                pose_bone, bounce_world, zero
            )

            key_pose_transform(pose_bone, FRAME_START, zero.copy(), zero.copy())
            key_pose_transform(
                pose_bone, FRAME_OUTER_START, zero.copy(), zero.copy()
            )
            key_pose_transform(
                pose_bone,
                mid_frame,
                open_location * 0.46 - bounce_local * 0.35,
                open_rotation * 0.32,
            )
            key_pose_transform(
                pose_bone,
                overshoot_frame,
                open_location * 1.055 + bounce_local,
                open_rotation * 1.10,
            )
            key_pose_transform(
                pose_bone,
                rebound_frame,
                open_location * 0.982 - bounce_local * 0.42,
                open_rotation * 0.96,
            )
            key_pose_transform(
                pose_bone,
                settle_frame,
                open_location * 1.006 + bounce_local * 0.12,
                open_rotation * 1.015,
            )
            key_pose_transform(
                pose_bone, FRAME_OUTER_OPEN, open_location, open_rotation
            )
            key_pose_transform(
                pose_bone, FRAME_END, open_location, open_rotation
            )

    for side_name, sign in (("L", -1.0), ("R", 1.0)):
        for column in range(inner_columns):
            s = column / (inner_columns - 1)
            x_rest_abs = 0.025 + s * (HALF_WIDTH - 0.025)
            x_open_abs = 4.56 + 1.36 * s
            panel_phase = 2.0 * math.pi * s
            for level in range(inner_levels):
                t = level / (inner_levels - 1)
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
                final_location, final_rotation = world_to_bone_local(
                    pose_bone, final_world, rotation_world
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
                drag, _unused = world_to_bone_local(
                    pose_bone, drag_world, zero
                )
                ripple, _unused = world_to_bone_local(
                    pose_bone, ripple_world, zero
                )
                overshoot, _unused = world_to_bone_local(
                    pose_bone, overshoot_world, zero
                )

                delay = int(
                    round(
                        5.0 * t
                        + 4.0 * (1.0 - s)
                        + 1.5 * abs(0.5 - s)
                    )
                )
                acceleration_frame = 103 + delay
                mid_frame = 140 + delay
                near_open_frame = 174 + delay
                overshoot_frame = FRAME_INNER_OVERSHOOT + delay
                rebound_frame = 214 + min(delay, 8)
                settle_frame = 222 + min(delay, 5)

                key_pose_transform(
                    pose_bone, FRAME_START, zero.copy(), zero.copy()
                )
                key_pose_transform(
                    pose_bone, FRAME_INNER_START, zero.copy(), zero.copy()
                )
                key_pose_transform(
                    pose_bone,
                    acceleration_frame,
                    final_location * 0.18 + drag * 0.82,
                    final_rotation * 0.10,
                )
                key_pose_transform(
                    pose_bone,
                    mid_frame,
                    final_location * 0.58
                    + drag * 0.42
                    + ripple * 0.34,
                    final_rotation * 0.44,
                )
                key_pose_transform(
                    pose_bone,
                    near_open_frame,
                    final_location * 0.90 + ripple,
                    final_rotation * 0.82,
                )
                key_pose_transform(
                    pose_bone,
                    overshoot_frame,
                    final_location * 1.025 + overshoot,
                    final_rotation * 1.10,
                )
                key_pose_transform(
                    pose_bone,
                    rebound_frame,
                    final_location * 0.988 - overshoot * 0.42,
                    final_rotation * 0.965,
                )
                key_pose_transform(
                    pose_bone,
                    settle_frame,
                    final_location * 1.004 + overshoot * 0.12,
                    final_rotation * 1.008,
                )
                key_pose_transform(
                    pose_bone,
                    FRAME_INNER_OPEN,
                    final_location,
                    final_rotation,
                )
                key_pose_transform(
                    pose_bone, FRAME_END, final_location, final_rotation
                )

    if hasattr(action, "fcurves"):
        fcurves = list(action.fcurves)
    else:
        fcurves = [
            fcurve
            for layer in action.layers
            for strip in layer.strips
            for channelbag in getattr(strip, "channelbags", ())
            for fcurve in channelbag.fcurves
        ]

    for fcurve in fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"

    action.use_fake_user = True
    return action


def point_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_preview_environment(
    preview_collection: bpy.types.Collection,
) -> bpy.types.Object:
    world = bpy.data.worlds.new("CurtainPreviewWorld")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.009, 0.012, 0.020, 1.0)
        background.inputs["Strength"].default_value = 0.18
    bpy.context.scene.world = world

    camera_data = bpy.data.cameras.new("CurtainPreviewCamera")
    camera = bpy.data.objects.new("CurtainPreviewCamera", camera_data)
    preview_collection.objects.link(camera)
    camera.location = (0.0, -19.8, 4.0)
    camera.data.lens = 48.0
    point_at(camera, Vector((0.0, 0.0, 3.25)))
    bpy.context.scene.camera = camera

    light_specs = (
        ("CurtainKey", (-6.5, -7.0, 9.3), 1450.0, 5.5, (1.0, 0.72, 0.55)),
        ("CurtainFill", (6.8, -4.5, 7.3), 1050.0, 5.0, (0.46, 0.62, 1.0)),
        ("CurtainTop", (0.0, 1.8, 9.2), 1250.0, 4.0, (0.62, 0.73, 1.0)),
    )
    for name, location, energy, size, color in light_specs:
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = size
        light_data.color = color
        light = bpy.data.objects.new(name, light_data)
        preview_collection.objects.link(light)
        light.location = location
        point_at(light, Vector((0.0, 0.0, 3.0)))

    backdrop_material = make_simple_material(
        "M_Preview_Backdrop", (0.012, 0.017, 0.028, 1.0), roughness=0.82
    )

    bpy.ops.mesh.primitive_plane_add(
        size=32.0, location=(0.0, 1.7, 3.6), rotation=(math.pi / 2.0, 0.0, 0.0)
    )
    backdrop = bpy.context.object
    backdrop.name = "Preview_Backdrop"
    relink_object(backdrop, preview_collection)
    backdrop.data.materials.append(backdrop_material)

    floor_material = make_simple_material(
        "M_Preview_Floor", (0.025, 0.020, 0.021, 1.0), roughness=0.50
    )
    bpy.ops.mesh.primitive_plane_add(size=32.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.object
    floor.name = "Preview_Floor"
    relink_object(floor, preview_collection)
    floor.data.materials.append(floor_material)
    return camera


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = 30
    scene.render.fps_base = 1.0

    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"

    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        pass

    scene.timeline_markers.new("Closed", frame=FRAME_START)
    scene.timeline_markers.new("Outer Lift Begins", frame=FRAME_OUTER_START)
    scene.timeline_markers.new("Outer Lifted", frame=FRAME_OUTER_OPEN)
    scene.timeline_markers.new("Inner Traveler Begins", frame=FRAME_INNER_START)
    scene.timeline_markers.new("Fully Open", frame=FRAME_INNER_OPEN)


def render_preview(frame: int, output_path: Path) -> None:
    scene = bpy.context.scene
    scene.frame_set(frame)
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)


def export_fbx(asset_objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    for obj in asset_objects:
        obj.select_set(True)
    armature = next(obj for obj in asset_objects if obj.type == "ARMATURE")
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


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clean_scene()
    configure_scene()

    asset_collection = make_collection("CURTAIN_ASSET")
    preview_collection = make_collection("PREVIEW_ONLY")

    outer_material = make_fabric_material(
        "M_Curtain_Outer_Painted",
        (0.285, 0.335, 0.365, 1.0),
        roughness=0.72,
        noise_scale=155.0,
        bump_strength=0.19,
        sheen=0.09,
    )
    inner_material = make_fabric_material(
        "M_Curtain_Inner_Burgundy",
        (0.27, 0.012, 0.025, 1.0),
        roughness=0.50,
        noise_scale=230.0,
        bump_strength=0.20,
        sheen=0.34,
    )
    outer_band_material = make_fabric_material(
        "M_Curtain_Outer_Painted_Border",
        (0.17, 0.205, 0.235, 1.0),
        roughness=0.76,
        noise_scale=125.0,
        bump_strength=0.22,
        sheen=0.06,
    )
    trim_material = make_fabric_material(
        "M_Curtain_Woven_Trim",
        (0.29, 0.15, 0.025, 1.0),
        roughness=0.47,
        noise_scale=105.0,
        bump_strength=0.22,
        sheen=0.22,
    )

    outer_bone_columns = 19
    outer_bone_levels = 8
    inner_bone_columns = 17
    inner_bone_levels = 5
    armature = create_armature(
        asset_collection,
        outer_bone_columns,
        outer_bone_levels,
        inner_bone_columns,
        inner_bone_levels,
    )

    asset_objects: list[bpy.types.Object] = [armature]
    outer = create_contour_mesh(
        materials=(outer_material, outer_band_material, trim_material),
        armature=armature,
        asset_collection=asset_collection,
        bone_columns=outer_bone_columns,
        bone_levels=outer_bone_levels,
    )
    asset_objects.append(outer)

    for side_name, sign in (("L", -1.0), ("R", 1.0)):
        inner = create_panel_mesh(
            name=f"SM_Curtain_Inner_{side_name}",
            side_name=side_name,
            sign=sign,
            columns=47,
            rows=29,
            y_base=0.18,
            pleat_count=11.5,
            pleat_depth=0.205,
            materials=(inner_material, trim_material),
            armature=armature,
            asset_collection=asset_collection,
            bone_columns=inner_bone_columns,
            bone_levels=inner_bone_levels,
            prefix="IN",
            outer_panel=False,
        )
        asset_objects.append(inner)

    action = animate_armature(
        armature,
        outer_bone_columns,
        outer_bone_levels,
        inner_bone_columns,
        inner_bone_levels,
    )

    armature["AssetPurpose"] = (
        "Detailed two-layer curtain with independently baked fabric motion"
    )
    armature["Animation"] = (
        f"CURTAIN_TwoLayer_Physics_Open, frames {FRAME_START}-{FRAME_END}, 30 fps"
    )
    armature["UEImport"] = (
        "Import Skeletal Mesh + Animations; Morph Targets not required; "
        "animation is bone-driven."
    )
    armature["LiftPoints"] = "-4.76m, -3.08m, +3.08m, +4.76m"
    armature["Physics"] = (
        "Outer pickup compression and settling; five-tier traveler hem drag, "
        "ripples, overshoot, rebound, and damped settling"
    )

    add_preview_environment(preview_collection)
    scene = bpy.context.scene
    scene.frame_set(FRAME_START)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT), check_existing=False)

    export_fbx(asset_objects)

    render_preview(FRAME_START, PREVIEW_CLOSED)
    render_preview(FRAME_OUTER_OPEN, PREVIEW_OUTER)
    render_preview(FRAME_END, PREVIEW_OPEN)

    scene.frame_set(FRAME_START)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUTPUT), check_existing=False)

    print("CURTAIN_BUILD_COMPLETE")
    print(f"BLEND={BLEND_OUTPUT}")
    print(f"FBX={FBX_OUTPUT}")
    print(f"ACTION={action.name}")
    print(f"FRAMES={FRAME_START}-{FRAME_END}@{scene.render.fps}fps")
    print(f"ASSET_OBJECTS={[obj.name for obj in asset_objects]}")
    print(f"BONES={len(armature.data.bones)}")


if __name__ == "__main__":
    main()
