"""Render the Flat V3 Front texture without lighting or surface shading."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_v3_flat import BOARD_FRONT_X, Silhouette, load_mask, look_at  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mask", required=True, type=Path)
    parser.add_argument("--side", required=True, choices=("L", "R"))
    parser.add_argument("--paper-off", required=True, type=Path)
    parser.add_argument("--paper-on", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-name", required=True)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args(raw)


def emission_texture_material(name: str, path: Path) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UV0"
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(path.resolve()), check_existing=True)
    texture.image.colorspace_settings.name = "sRGB"
    texture.interpolation = "Linear"
    links.new(uv.outputs["UV"], texture.inputs["Vector"])
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs[0], output.inputs[0])
    return material


def transparent_material() -> bpy.types.Material:
    material = bpy.data.materials.new("NEUTRAL_Transparent")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfTransparent")
    links.new(shader.outputs[0], output.inputs[0])
    return material


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    silhouette = Silhouette(load_mask(args.mask.resolve()), 10.0, args.side)
    camera = scene.camera
    if camera is None:
        camera_data = bpy.data.cameras.new("NeutralCamera")
        camera = bpy.data.objects.new("NeutralCamera", camera_data)
        bpy.context.collection.objects.link(camera)
        scene.camera = camera
    center_y = silhouette.width_m * 0.5 * (1.0 if args.side == "L" else -1.0)
    center = (BOARD_FRONT_X, center_y, silhouette.height_m * 0.5)
    camera.location = (BOARD_FRONT_X - 6.0, center_y, silhouette.height_m * 0.5)
    camera.data.type = "PERSP"
    camera.data.lens = 15.0
    look_at(camera, center)

    lod0 = next(obj for obj in scene.objects if obj.type == "MESH" and "_LOD0" in obj.name)
    for obj in scene.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            obj.hide_render = obj != lod0
    expected = [lod0.name]
    actual = sorted(
        obj.name for obj in scene.objects
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"} and not obj.hide_render
    )
    if actual != expected:
        raise RuntimeError(f"Neutral render object list mismatch: actual={actual}; expected={expected}")

    hidden = transparent_material()
    originals = [(slot.link, slot.material) for slot in lod0.material_slots]
    outputs = {}
    for label, texture_path in (("paper_off", args.paper_off), ("paper_on", args.paper_on)):
        front = emission_texture_material(f"NEUTRAL_{label}", texture_path)
        for slot, (_, original) in zip(lod0.material_slots, originals):
            original_name = original.name if original else ""
            slot.link = "OBJECT"
            slot.material = front if original_name == "Front" else hidden
        path = args.output_dir / f"{args.base_name}_neutral_{label}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        outputs[label] = str(path)

    for slot, (link, material) in zip(lod0.material_slots, originals):
        slot.material = material
        slot.link = link
    report = {
        "schema_version": 1,
        "blend": bpy.data.filepath,
        "side": args.side,
        "color_management": {"view_transform": "Standard", "look": "None", "exposure": 0.0, "gamma": 1.0},
        "asserted_object_list": actual,
        "renders": outputs,
    }
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("FLAT_V3_NEUTRAL_RENDER_OK")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
