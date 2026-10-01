"""Blender 4.4 offline preview for the 20x30 m Scene 3 backdrop panel."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def argv_after_double_dash() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def make_material(color_path: Path, mask_path: Path, normal_path: Path) -> bpy.types.Material:
    material = bpy.data.materials.new("M_S3_Backdrop_Preview")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Metallic"].default_value = 0.0
    if "IOR Level" in shader.inputs:
        shader.inputs["IOR Level"].default_value = 0.30
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    color = nodes.new("ShaderNodeTexImage")
    color.image = bpy.data.images.load(str(color_path), check_existing=False)
    color.image.colorspace_settings.name = "sRGB"
    links.new(color.outputs["Color"], shader.inputs["Base Color"])

    mask = nodes.new("ShaderNodeTexImage")
    mask.image = bpy.data.images.load(str(mask_path), check_existing=False)
    mask.image.colorspace_settings.name = "Non-Color"
    separate_mask = nodes.new("ShaderNodeSeparateColor")
    links.new(mask.outputs["Color"], separate_mask.inputs["Color"])
    links.new(separate_mask.outputs["Blue"], shader.inputs["Roughness"])

    normal = nodes.new("ShaderNodeTexImage")
    normal.image = bpy.data.images.load(str(normal_path), check_existing=False)
    normal.image.colorspace_settings.name = "Non-Color"
    separate_normal = nodes.new("ShaderNodeSeparateColor")
    invert_green = nodes.new("ShaderNodeMath")
    invert_green.operation = "SUBTRACT"
    invert_green.inputs[0].default_value = 1.0
    combine_normal = nodes.new("ShaderNodeCombineColor")
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.inputs["Strength"].default_value = 0.32
    links.new(normal.outputs["Color"], separate_normal.inputs["Color"])
    links.new(separate_normal.outputs["Red"], combine_normal.inputs["Red"])
    links.new(separate_normal.outputs["Green"], invert_green.inputs[1])
    links.new(invert_green.outputs[0], combine_normal.inputs["Green"])
    links.new(separate_normal.outputs["Blue"], combine_normal.inputs["Blue"])
    links.new(combine_normal.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])
    return material


def make_panel(material: bpy.types.Material) -> bpy.types.Object:
    mesh = bpy.data.meshes.new("SM_S3_Backdrop_Preview_20x30m")
    vertices = [(-10.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 30.0), (-10.0, 0.0, 30.0)]
    mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for loop, uv in zip(mesh.loops, ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        uv_layer.data[loop.index].uv = uv
    panel = bpy.data.objects.new("S3_Backdrop_20x30m", mesh)
    bpy.context.collection.objects.link(panel)
    panel.data.materials.append(material)
    return panel


def make_floor() -> None:
    bpy.ops.mesh.primitive_plane_add(size=180.0, location=(0.0, 25.0, -0.025))
    floor = bpy.context.object
    floor.name = "Neutral_Grey_Floor"
    material = bpy.data.materials.new("M_Neutral_Grey_Floor")
    material.diffuse_color = (0.18, 0.205, 0.23, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (0.18, 0.205, 0.23, 1.0)
    shader.inputs["Roughness"].default_value = 0.82
    floor.data.materials.append(material)


def add_area(name: str, location: tuple[float, float, float], energy: float, size: float) -> None:
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = (0.72, 0.82, 1.0)
    light = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(light)
    light.location = location
    look_at(light, (0.0, 0.0, 14.0))


def add_sun() -> None:
    data = bpy.data.lights.new("Cool_Daylight_Sun", "SUN")
    data.energy = 2.2
    data.angle = math.radians(18.0)
    data.color = (0.75, 0.84, 1.0)
    light = bpy.data.objects.new("Cool_Daylight_Sun", data)
    bpy.context.collection.objects.link(light)
    light.location = (-20.0, -30.0, 40.0)
    look_at(light, (0.0, 0.0, 12.0))


def configure_camera() -> bpy.types.Object:
    data = bpy.data.cameras.new("Camera_50deg")
    data.sensor_fit = "HORIZONTAL"
    data.sensor_width = 36.0
    hfov = math.radians(50.0)
    data.lens = data.sensor_width / (2.0 * math.tan(hfov / 2.0))
    camera = bpy.data.objects.new("Camera_50deg", data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    return camera


def main() -> None:
    args = argv_after_double_dash()
    if len(args) != 2:
        raise SystemExit("Usage: blender ... -- preview_scene3_backdrop.py -- <backdrop-root> <preview-dir>")
    root = Path(args[0]).resolve()
    preview_dir = Path(args[1]).resolve()
    preview_dir.mkdir(parents=True, exist_ok=True)
    texture_dir = root / "textures"

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.look = "AgX - Medium High Contrast"

    world = bpy.data.worlds.new("Cool_Grey_Daylight")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.24, 0.28, 0.33, 1.0)
    background.inputs["Strength"].default_value = 0.70
    scene.world = world

    material = make_material(
        texture_dir / "T_S3_OpalBeach_Backdrop_SkinColor.png",
        texture_dir / "T_S3_OpalBeach_Backdrop_SkinMask.png",
        texture_dir / "T_S3_OpalBeach_Backdrop_SkinNormal.png",
    )
    make_panel(material)
    make_floor()
    add_sun()
    add_area("Cool_Key", (-14.0, -18.0, 34.0), 2400.0, 18.0)
    add_area("Cool_Fill", (16.0, -8.0, 20.0), 900.0, 12.0)
    camera = configure_camera()

    renders = []
    for distance in (65.0, 20.0):
        if distance == 20.0:
            camera.location = (0.0, -distance, 8.0)
            look_at(camera, (0.0, 0.0, 7.5))
        else:
            camera.location = (0.0, -distance, 15.0)
            look_at(camera, (0.0, 0.0, 15.0))
        filename = f"S3_Backdrop_preview_{int(distance)}m_50deg.png"
        scene.render.filepath = str(preview_dir / filename)
        bpy.ops.render.render(write_still=True)
        renders.append({
            "file": filename,
            "camera_distance_m": distance,
            "horizontal_fov_degrees": 50.0,
            "panel_angular_width_degrees": math.degrees(2.0 * math.atan(10.0 / distance)),
            "panel_angular_height_degrees": math.degrees(2.0 * math.atan(15.0 / distance)),
            "lighting": "two cool area lights plus cool grey world; neutral grey floor",
        })

    manifest = {
        "schema_version": 1,
        "renderer": f"Blender {bpy.app.version_string} Eevee Next",
        "panel_size_m": [20.0, 30.0],
        "material_inputs": {
            "SkinColor": "sRGB",
            "SkinMask": "Non-Color; B to Roughness",
            "SkinNormal": "Non-Color; DirectX green inverted for Blender tangent normal",
        },
        "renders": renders,
        "proof": {
            "measured": ["The offline preview renders completed and the camera/panel dimensions are recorded here."],
            "inferred": ["Cool-grey daylight and material response are approximations; Unreal stage lighting acceptance remains open."],
        },
    }
    (preview_dir / "preview_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("SCENE3_PREVIEW_OK|renders=65m,20m|hfov=50deg")


if __name__ == "__main__":
    main()
