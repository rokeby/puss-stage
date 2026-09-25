import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main():
    args = parse_args()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(args.fbx.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one mesh, found {len(meshes)}")
    obj = meshes[0]

    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    minimum = Vector(tuple(min(corner[index] for corner in corners) for index in range(3)))
    maximum = Vector(tuple(max(corner[index] for corner in corners) for index in range(3)))
    centre = (minimum + maximum) * 0.5

    camera_data = bpy.data.cameras.new("CleanExportPreviewCamera")
    camera = bpy.data.objects.new("CleanExportPreviewCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = Vector((maximum.x + 20.0, centre.y, centre.z))
    camera.rotation_euler = (centre - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(maximum.z - minimum.z, maximum.y - minimum.y) * 1.08

    light_data = bpy.data.lights.new("CleanExportPreviewLight", "AREA")
    light = bpy.data.objects.new("CleanExportPreviewLight", light_data)
    bpy.context.collection.objects.link(light)
    light.location = camera.location
    light.rotation_euler = camera.rotation_euler
    light_data.energy = 1400.0
    light_data.shape = "DISK"
    light_data.size = 10.0

    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = str(args.output.resolve())
    scene.world.color = (0.2, 0.2, 0.2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    print(f"CLEAN_FBX_PREVIEW_SUCCESS|{args.output.resolve()}")


main()
