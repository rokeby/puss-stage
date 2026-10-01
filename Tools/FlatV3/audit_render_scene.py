"""Audit a saved Flat V3 Blender scene with object/material isolation renders.

Run with Blender 4.4 in background mode after opening the .blend.  This tool is
diagnostic evidence: it does not save the scene it inspects.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_v3_flat import BOARD_FRONT_X, Silhouette, load_mask, look_at  # noqa: E402


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-name", required=True)
    parser.add_argument("--mask", required=True, type=Path)
    parser.add_argument("--side", required=True, choices=("L", "R"))
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=16)
    return parser.parse_args(raw)


def configure_scene(samples: int) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    scene.view_settings.look = "AgX - Medium Low Contrast"
    scene.view_settings.exposure = 0.5


def ensure_head_on_camera(silhouette: Silhouette) -> bpy.types.Object:
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None:
        data = bpy.data.cameras.new("AuditCamera")
        camera = bpy.data.objects.new("AuditCamera", data)
        bpy.context.collection.objects.link(camera)
        scene.camera = camera
    center_y = silhouette.width_m * 0.5 * (1.0 if silhouette.side == "L" else -1.0)
    center = (BOARD_FRONT_X, center_y, silhouette.height_m * 0.5)
    camera.location = (BOARD_FRONT_X - 6.0, center_y, silhouette.height_m * 0.5)
    camera.data.type = "PERSP"
    camera.data.lens = 15.0
    look_at(camera, center)
    return camera


def renderable_object_names() -> list[str]:
    return sorted(
        obj.name for obj in bpy.context.scene.objects
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"} and not obj.hide_render
    )


def set_only_meshes(names: set[str]) -> None:
    for obj in bpy.context.scene.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            obj.hide_render = obj.name not in names


def render(path: Path) -> np.ndarray:
    scene = bpy.context.scene
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    image = bpy.data.images.load(str(path), check_existing=False)
    rgba = np.empty(image.size[0] * image.size[1] * 4, dtype=np.float32)
    image.pixels.foreach_get(rgba)
    alpha = rgba[3::4].reshape((image.size[1], image.size[0])).copy()
    bpy.data.images.remove(image)
    return alpha


def transparent_material() -> bpy.types.Material:
    material = bpy.data.materials.new("AUDIT_Transparent")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfTransparent")
    links.new(shader.outputs[0], output.inputs[0])
    return material


def white_material() -> bpy.types.Material:
    material = bpy.data.materials.new("AUDIT_White")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeEmission")
    shader.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    shader.inputs["Strength"].default_value = 1.0
    links.new(shader.outputs[0], output.inputs[0])
    return material


def isolate_material(obj: bpy.types.Object, material_name: str, target: bpy.types.Material,
                     hidden: bpy.types.Material) -> list[tuple[str, bpy.types.Material | None]]:
    saved = []
    for slot in obj.material_slots:
        saved.append((slot.link, slot.material))
        original_name = slot.material.name if slot.material else ""
        slot.link = "OBJECT"
        slot.material = target if original_name == material_name else hidden
    return saved


def restore_slots(obj: bpy.types.Object, saved: list[tuple[str, bpy.types.Material | None]]) -> None:
    for slot, (link, material) in zip(obj.material_slots, saved):
        slot.material = material
        slot.link = link


def create_expected_mask_plane(mask_path: Path, silhouette: Silhouette,
                               hidden: bpy.types.Material) -> bpy.types.Object:
    if silhouette.side == "L":
        y0 = (0.0 - silhouette.u_min) * silhouette.scale_m_per_px
        y1 = (silhouette.image_w - silhouette.u_min) * silhouette.scale_m_per_px
    else:
        y0 = (0.0 - silhouette.u_max) * silhouette.scale_m_per_px
        y1 = (silhouette.image_w - silhouette.u_max) * silhouette.scale_m_per_px
    z0 = (0.0 - silhouette.v_min) * silhouette.scale_m_per_px
    z1 = (silhouette.image_h - silhouette.v_min) * silhouette.scale_m_per_px
    mesh = bpy.data.meshes.new("AUDIT_ExpectedMask_Mesh")
    mesh.from_pydata(
        [(BOARD_FRONT_X - 0.002, y0, z0), (BOARD_FRONT_X - 0.002, y1, z0),
         (BOARD_FRONT_X - 0.002, y1, z1), (BOARD_FRONT_X - 0.002, y0, z1)],
        [], [(0, 1, 2, 3)],
    )
    uv = mesh.uv_layers.new(name="UV0")
    for loop, coord in zip(mesh.polygons[0].loop_indices, ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop].uv = coord
    obj = bpy.data.objects.new("AUDIT_ExpectedMask", mesh)
    bpy.context.collection.objects.link(obj)

    material = bpy.data.materials.new("AUDIT_ExpectedMask_Material")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    mix = nodes.new("ShaderNodeMixShader")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(mask_path.resolve()), check_existing=True)
    texture.image.colorspace_settings.name = "Non-Color"
    texture.interpolation = "Closest"
    threshold = nodes.new("ShaderNodeMath")
    threshold.operation = "GREATER_THAN"
    threshold.inputs[1].default_value = 0.5
    links.new(texture.outputs["Color"], threshold.inputs[0])
    links.new(threshold.outputs[0], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs[0])
    obj.data.materials.append(material)
    return obj


def mask_metrics(actual_alpha: np.ndarray, expected_alpha: np.ndarray) -> dict:
    actual = actual_alpha >= 0.5
    expected = expected_alpha >= 0.5
    intersection = int(np.count_nonzero(actual & expected))
    union = int(np.count_nonzero(actual | expected))
    iou = intersection / max(union, 1)
    return {
        "actual_pixels": int(np.count_nonzero(actual)),
        "expected_pixels": int(np.count_nonzero(expected)),
        "intersection_pixels": intersection,
        "union_pixels": union,
        "iou": round(float(iou), 8),
        "required_iou_strictly_greater_than": 0.98,
        "pass": bool(iou > 0.98),
    }


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    configure_scene(args.samples)
    silhouette = Silhouette(load_mask(args.mask.resolve()), 10.0, args.side)
    ensure_head_on_camera(silhouette)
    initial = renderable_object_names()
    meshes = sorted(
        (obj for obj in bpy.context.scene.objects if obj.type == "MESH" and not obj.name.startswith("AUDIT_")),
        key=lambda obj: obj.name,
    )
    lod0 = next((obj for obj in meshes if "_LOD0" in obj.name), None)
    if lod0 is None:
        raise RuntimeError("No LOD0 mesh found")

    passes: dict[str, dict] = {}
    for obj in meshes:
        set_only_meshes({obj.name})
        alpha = render(args.output_dir / f"{args.base_name}_isolate_object_{obj.name}.png")
        passes[f"object:{obj.name}"] = {"alpha_pixels": int(np.count_nonzero(alpha >= 0.5))}

    hidden = transparent_material()
    white = white_material()
    front_visual_alpha = None
    front_silhouette_alpha = None
    for material_name in ("Front", "Flap", "Timber", "Edge"):
        set_only_meshes({lod0.name})
        original = next((slot.material for slot in lod0.material_slots if slot.material and slot.material.name == material_name), None)
        if original is None:
            continue
        saved = isolate_material(lod0, material_name, original, hidden)
        alpha = render(args.output_dir / f"{args.base_name}_isolate_material_{material_name}.png")
        passes[f"material:{material_name}"] = {"alpha_pixels": int(np.count_nonzero(alpha >= 0.5))}
        if material_name == "Front":
            front_visual_alpha = alpha
        restore_slots(lod0, saved)

        saved = isolate_material(lod0, material_name, white, hidden)
        alpha_white = render(args.output_dir / f"{args.base_name}_silhouette_{material_name}.png")
        if material_name == "Front":
            front_silhouette_alpha = alpha_white
        restore_slots(lod0, saved)

    expected = create_expected_mask_plane(args.mask.resolve(), silhouette, hidden)
    set_only_meshes({expected.name})
    expected_alpha = render(args.output_dir / f"{args.base_name}_silhouette_expected_cut_mask.png")
    if front_silhouette_alpha is None:
        raise RuntimeError("Front material pass was not rendered")
    metrics = mask_metrics(front_silhouette_alpha, expected_alpha)

    report = {
        "schema_version": 1,
        "blend": bpy.data.filepath,
        "mask": str(args.mask.resolve()),
        "side": args.side,
        "initial_renderable_object_list": initial,
        "object_presence": {
            "lod0": [obj.name for obj in meshes if "_LOD0" in obj.name],
            "lod1": [obj.name for obj in meshes if "_LOD1" in obj.name],
            "right_flat": [obj.name for obj in meshes if "_R_" in obj.name],
            "unclassified_meshes": [obj.name for obj in meshes if not any(token in obj.name for token in ("_LOD0", "_LOD1", "Pole_", "Floor_", "Groove"))],
        },
        "passes": passes,
        "front_silhouette_match": metrics,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("FLAT_V3_SCENE_AUDIT_OK")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
