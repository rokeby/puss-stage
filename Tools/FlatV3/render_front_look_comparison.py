"""Render the rejected and corrected Front lighting/material configurations."""

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
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-name", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=64)
    return parser.parse_args(raw)


def transparent_material() -> bpy.types.Material:
    material = bpy.data.materials.new("LOOK_Transparent")
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
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.cycles.samples = args.samples

    silhouette = Silhouette(load_mask(args.mask.resolve()), 10.0, args.side)
    center_y = silhouette.width_m * 0.5 * (1.0 if args.side == "L" else -1.0)
    center = (BOARD_FRONT_X, center_y, silhouette.height_m * 0.5)
    camera = scene.camera
    camera.location = (BOARD_FRONT_X - 6.0, center_y, silhouette.height_m * 0.5)
    camera.data.type = "PERSP"
    camera.data.lens = 15.0
    look_at(camera, center)

    lod0 = next(obj for obj in scene.objects if obj.type == "MESH" and "_LOD0" in obj.name)
    for obj in scene.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            obj.hide_render = obj != lod0
    hidden = transparent_material()
    originals = [(slot.link, slot.material) for slot in lod0.material_slots]
    front = next(material for _, material in originals if material and material.name == "Front")
    for slot, (_, original) in zip(lod0.material_slots, originals):
        slot.link = "OBJECT"
        slot.material = front if original and original.name == "Front" else hidden
    shader = next(node for node in front.node_tree.nodes if node.type == "BSDF_PRINCIPLED")

    variants = {
        "rejected_look": {
            "look": "AgX - Medium Low Contrast", "exposure": 0.5, "ior_level": 0.5,
            "lights": {"Warm_Raking_Key": 520.0, "Warm_Soft_Front": 700.0, "Warm_Top_Edge": 160.0, "Very_Low_Fill": 65.0},
        },
        "final_look": {
            "look": "AgX - Medium High Contrast", "exposure": 0.75, "ior_level": 0.18,
            "lights": {"Warm_Raking_Key": 380.0, "Warm_Soft_Front": 360.0, "Warm_Top_Edge": 100.0, "Very_Low_Fill": 35.0},
            "colors": {
                "Warm_Raking_Key": [1.0, 0.80, 0.68], "Warm_Soft_Front": [1.0, 0.93, 0.86],
                "Warm_Top_Edge": [1.0, 0.86, 0.74], "Very_Low_Fill": [0.35, 0.40, 0.50],
            },
        },
    }
    outputs = {}
    default_colors = {
        "Warm_Raking_Key": (1.0, 0.68, 0.42), "Warm_Soft_Front": (1.0, 0.86, 0.72),
        "Warm_Top_Edge": (1.0, 0.78, 0.55), "Very_Low_Fill": (0.23, 0.30, 0.45),
    }
    for label, settings in variants.items():
        scene.view_settings.look = settings["look"]
        scene.view_settings.exposure = settings["exposure"]
        shader.inputs["Specular IOR Level"].default_value = settings["ior_level"]
        for light_name, energy in settings["lights"].items():
            bpy.data.lights[light_name].energy = energy
            bpy.data.lights[light_name].color = settings.get("colors", default_colors)[light_name]
        path = args.output_dir / f"{args.base_name}_{label}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        outputs[label] = str(path)

    for slot, (link, material) in zip(lod0.material_slots, originals):
        slot.material = material
        slot.link = link
    report = {"schema_version": 1, "blend": bpy.data.filepath, "asserted_object_list": [lod0.name], "variants": variants, "renders": outputs}
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("FLAT_V3_LOOK_COMPARISON_OK")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
