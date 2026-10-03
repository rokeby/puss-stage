"""Build, render, export and validate one production Flat V3 card in Blender 4.4.

Run only with Blender 4.4 in background/factory-startup mode.  The build mode
accepts one binary cut mask, one final height and one L/R side.  Validation mode
imports exactly one FBX into a clean factory-startup process and writes JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from socket_contract import make_socket_payload


MATERIAL_SLOTS = ["Front", "Flap", "Timber", "Edge"]
VERTEX_COLOR_NAME = "Color"
BOARD_FRONT_X = -0.150
BOARD_BACK_X = -0.132
FRAME_BACK_X = -0.040
BLOCK_BACK_X = -0.032
MEMBER_FACE_M = 0.050
EDGE_INSET_M = 0.140
MIN_FRAME_EDGE_CLEARANCE_M = 0.080
POLE_DIAMETER_M = 0.060
POLE_UNIT_BOTTOM_M = -1.0 / 11.2
POLE_UNIT_TOP_M = 10.2 / 11.2
POLE_SCALE_FOR_10M = 11.2


def blender_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--mask")
    parser.add_argument("--art")
    parser.add_argument("--skin-mask")
    parser.add_argument("--skin-normal")
    parser.add_argument("--flaps")
    parser.add_argument("--aged-texture-dir")
    parser.add_argument("--height-cm", type=float)
    parser.add_argument("--side", choices=("L", "R"))
    parser.add_argument("--name")
    parser.add_argument("--asset-name", help="Exact suffix after SM_FlatV3_; defaults to <name>_<side>")
    parser.add_argument("--mount", choices=("wing", "wave-row", "top-border"), default="wing")
    parser.add_argument("--deterministic-triangulation", action="store_true")
    parser.add_argument(
        "--triangulate-export",
        action="store_true",
        help=("Opt in to fixed final-mesh triangulation and degenerate-face removal "
              "immediately before FBX export"),
    )
    parser.add_argument("--output-dir")
    parser.add_argument("--texture-root")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--validate-fbx")
    parser.add_argument("--skin-color")
    parser.add_argument("--kind", choices=("flat", "pole", "wave"))
    parser.add_argument("--validation-out")
    parser.add_argument("--expected-height-cm", type=float)
    parser.add_argument("--minimum-width-m", type=float, default=0.0)
    parser.add_argument(
        "--skip-pole-export",
        action="store_true",
        help="Build the flat normally without replacing the shared no-LOD pole FBX",
    )
    parser.add_argument(
        "--bake-poles",
        action="store_true",
        help=("Bake a full-height copy of the shared pole profile into both card LODs at every "
              "Pole_n socket. For non-toppling interim use only; sockets remain exported."),
    )
    parser.add_argument(
        "--pole-extension-cm",
        type=float,
        default=100.0,
        help=("Opt-in baked-pole reach below the panel base in centimetres. "
              "The Flat V3 default remains 100; requires --bake-poles."),
    )
    return parser.parse_args(raw)


def require_blender_44() -> None:
    if bpy.app.version[:2] != (4, 4):
        raise RuntimeError(f"Blender 4.4 required; got {bpy.app.version_string}")
    if not bpy.app.background:
        raise RuntimeError("This generator must run headless (--background), never in the GUI")


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.curves, bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def load_mask(path: Path) -> np.ndarray:
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = map(int, image.size)
    rgba = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(rgba)
    # Blender exposes image pixels bottom row first.  The contour code below
    # deliberately uses conventional image coordinates (row zero is the top),
    # so normalise the row origin here.  Without this flip the physical cut
    # profile is vertically inverted while the texture remains upright.
    mask = np.flipud(rgba[0::4].reshape((height, width))).copy() >= 0.5
    bpy.data.images.remove(image)
    del rgba
    if not mask.any():
        raise RuntimeError(f"Mask is empty: {path}")
    return mask


def add_edge(adjacency: dict, start: tuple[int, int], end: tuple[int, int]) -> None:
    adjacency.setdefault(start, []).append(end)


def mask_loops(mask: np.ndarray) -> list[np.ndarray]:
    """Return pixel-grid boundary loops with filled cells on the left."""
    height, width = mask.shape
    adjacency: dict[tuple[int, int], list[tuple[int, int]]] = {}

    cols = np.flatnonzero(mask[0])
    for col in cols:
        add_edge(adjacency, (int(col + 1), height), (int(col), height))
    rows, cols = np.nonzero(mask[1:] & ~mask[:-1])
    for row, col in zip(rows + 1, cols):
        v = height - int(row)
        add_edge(adjacency, (int(col + 1), v), (int(col), v))

    cols = np.flatnonzero(mask[-1])
    for col in cols:
        add_edge(adjacency, (int(col), 0), (int(col + 1), 0))
    rows, cols = np.nonzero(mask[:-1] & ~mask[1:])
    for row, col in zip(rows, cols):
        v = height - int(row) - 1
        add_edge(adjacency, (int(col), v), (int(col + 1), v))

    rows = np.flatnonzero(mask[:, 0])
    for row in rows:
        top = height - int(row)
        add_edge(adjacency, (0, top), (0, top - 1))
    rows, cols = np.nonzero(mask[:, 1:] & ~mask[:, :-1])
    for row, col in zip(rows, cols + 1):
        top = height - int(row)
        add_edge(adjacency, (int(col), top), (int(col), top - 1))

    rows = np.flatnonzero(mask[:, -1])
    for row in rows:
        bottom = height - int(row) - 1
        add_edge(adjacency, (width, bottom), (width, bottom + 1))
    rows, cols = np.nonzero(mask[:, :-1] & ~mask[:, 1:])
    for row, col in zip(rows, cols):
        u = int(col) + 1
        bottom = height - int(row) - 1
        add_edge(adjacency, (u, bottom), (u, bottom + 1))

    loops: list[np.ndarray] = []
    while adjacency:
        start = next(iter(adjacency))
        current = start
        loop = [start]
        guard = 0
        while True:
            options = adjacency.get(current)
            if not options:
                raise RuntimeError(f"Open boundary at {current}")
            nxt = options.pop()
            if not options:
                del adjacency[current]
            current = nxt
            guard += 1
            if current == start:
                break
            loop.append(current)
            if guard > mask.size:
                raise RuntimeError("Boundary trace exceeded mask size")
        if len(loop) >= 4:
            loops.append(np.asarray(loop, dtype=np.float64))
    return loops


def signed_area(points: np.ndarray) -> float:
    shifted = np.roll(points, -1, axis=0)
    return 0.5 * float(np.sum(points[:, 0] * shifted[:, 1] - shifted[:, 0] * points[:, 1]))


def rdp_open(points: np.ndarray, tolerance: float) -> np.ndarray:
    if len(points) <= 2:
        return points
    start, end = points[0], points[-1]
    delta = end - start
    denom = float(np.dot(delta, delta))
    if denom == 0.0:
        distances = np.linalg.norm(points - start, axis=1)
    else:
        t = np.clip(((points - start) @ delta) / denom, 0.0, 1.0)
        projection = start + t[:, None] * delta
        distances = np.linalg.norm(points - projection, axis=1)
    index = int(np.argmax(distances))
    if distances[index] <= tolerance:
        return np.vstack((start, end))
    left = rdp_open(points[: index + 1], tolerance)
    right = rdp_open(points[index:], tolerance)
    return np.vstack((left[:-1], right))


def simplify_closed(points: np.ndarray, tolerance: float) -> np.ndarray:
    # RDP may otherwise remove the source silhouette's exact extrema.  Since
    # physical scale is derived from those extrema, that can make an exported
    # 12 m card several centimetres short.  Split the closed contour at each
    # axis extremum so all four anchors survive simplification.
    anchors = sorted({
        int(np.argmin(points[:, 0])), int(np.argmax(points[:, 0])),
        int(np.argmin(points[:, 1])), int(np.argmax(points[:, 1])),
    })
    if len(anchors) < 2:
        return points
    segments = []
    for anchor_index, start in enumerate(anchors):
        end = anchors[(anchor_index + 1) % len(anchors)]
        if end > start:
            segment = points[start:end + 1]
        else:
            segment = np.vstack((points[start:], points[:end + 1]))
        segments.append(rdp_open(segment, tolerance)[:-1])
    combined = np.vstack(segments)
    return combined if len(combined) >= 3 else points


class Silhouette:
    def __init__(self, mask: np.ndarray, height_m: float, side: str):
        self.mask = mask
        self.image_h, self.image_w = mask.shape
        raw_loops = mask_loops(mask)
        raw_loops.sort(key=lambda loop: abs(signed_area(loop)), reverse=True)
        outer = raw_loops[0]
        self.u_min = float(outer[:, 0].min())
        self.u_max = float(outer[:, 0].max())
        self.v_min = float(outer[:, 1].min())
        self.v_max = float(outer[:, 1].max())
        self.scale_m_per_px = height_m / (self.v_max - self.v_min)
        self.height_m = height_m
        self.side = side
        min_hole_area_px = (0.03 / self.scale_m_per_px) ** 2
        kept = [outer]
        for loop in raw_loops[1:]:
            if abs(signed_area(loop)) >= min_hole_area_px:
                kept.append(loop)
        tolerance_px = 0.0055 / self.scale_m_per_px
        self.pixel_loops = [simplify_closed(loop, tolerance_px) for loop in kept]
        self.physical_loops = [self.pixel_to_physical(loop) for loop in self.pixel_loops]
        self.width_m = (self.u_max - self.u_min) * self.scale_m_per_px
        segments_a = []
        segments_b = []
        for loop in self.physical_loops:
            segments_a.append(loop)
            segments_b.append(np.roll(loop, -1, axis=0))
        self.seg_a = np.vstack(segments_a)
        self.seg_b = np.vstack(segments_b)

    def pixel_to_physical(self, points: np.ndarray) -> np.ndarray:
        u = points[:, 0]
        v = points[:, 1]
        if self.side == "L":
            y = (self.u_min - u) * self.scale_m_per_px
        else:
            y = (self.u_max - u) * self.scale_m_per_px
        z = (v - self.v_min) * self.scale_m_per_px
        return np.column_stack((y, z))

    def physical_to_pixel(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        y, z = points[:, 0], points[:, 1]
        if self.side == "L":
            u = self.u_min - y / self.scale_m_per_px
        else:
            u = self.u_max - y / self.scale_m_per_px
        v = self.v_min + z / self.scale_m_per_px
        return u, v

    def inside(self, points: np.ndarray) -> np.ndarray:
        u, v = self.physical_to_pixel(points)
        cols = np.floor(u).astype(np.int64)
        rows = np.floor(self.image_h - v).astype(np.int64)
        valid = (rows >= 0) & (rows < self.image_h) & (cols >= 0) & (cols < self.image_w)
        result = np.zeros(len(points), dtype=bool)
        result[valid] = self.mask[rows[valid], cols[valid]]
        return result

    def boundary_distance(self, points: np.ndarray) -> np.ndarray:
        result = np.full(len(points), np.inf, dtype=np.float64)
        segment = self.seg_b - self.seg_a
        denom = np.sum(segment * segment, axis=1)
        for start in range(0, len(points), 128):
            sample = points[start : start + 128]
            offset = sample[:, None, :] - self.seg_a[None, :, :]
            t = np.clip(np.sum(offset * segment[None, :, :], axis=2) / denom[None, :], 0.0, 1.0)
            projection = self.seg_a[None, :, :] + t[:, :, None] * segment[None, :, :]
            distance = np.linalg.norm(sample[:, None, :] - projection, axis=2)
            result[start : start + len(sample)] = distance.min(axis=1)
        return result

    def allowed(self, points: np.ndarray, margin_m: float) -> np.ndarray:
        return self.inside(points) & (self.boundary_distance(points) >= margin_m)

    def uv0(self, y: float, z: float) -> tuple[float, float]:
        point = np.asarray([[y, z]], dtype=np.float64)
        u, v = self.physical_to_pixel(point)
        return float(u[0] / self.image_w), float(v[0] / self.image_h)

    def uv0_to_physical(self, u: float, v: float) -> tuple[float, float]:
        point = np.asarray([[u * self.image_w, v * self.image_h]], dtype=np.float64)
        y, z = self.pixel_to_physical(point)[0]
        return float(y), float(z)


def make_image_material(name: str, color_path: Path, rough_path: Path | None = None,
                        normal_dx_path: Path | None = None, ao_path: Path | None = None,
                        metallic: float = 0.0, uv_map: str = "UV0") -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Metallic"].default_value = metallic
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = uv_map

    color = nodes.new("ShaderNodeTexImage")
    color.image = bpy.data.images.load(str(color_path), check_existing=True)
    color.image.colorspace_settings.name = "sRGB"
    color.interpolation = "Linear"
    links.new(uv.outputs["UV"], color.inputs["Vector"])
    if ao_path:
        ao = nodes.new("ShaderNodeTexImage")
        ao.image = bpy.data.images.load(str(ao_path), check_existing=True)
        ao.image.colorspace_settings.name = "Non-Color"
        links.new(uv.outputs["UV"], ao.inputs["Vector"])
        multiply = nodes.new("ShaderNodeMixRGB")
        multiply.blend_type = "MULTIPLY"
        multiply.inputs[0].default_value = 1.0
        links.new(color.outputs["Color"], multiply.inputs[1])
        links.new(ao.outputs["Color"], multiply.inputs[2])
        links.new(multiply.outputs["Color"], shader.inputs["Base Color"])
    else:
        links.new(color.outputs["Color"], shader.inputs["Base Color"])

    if rough_path:
        rough = nodes.new("ShaderNodeTexImage")
        rough.image = bpy.data.images.load(str(rough_path), check_existing=True)
        rough.image.colorspace_settings.name = "Non-Color"
        links.new(uv.outputs["UV"], rough.inputs["Vector"])
        links.new(rough.outputs["Color"], shader.inputs["Roughness"])
    else:
        shader.inputs["Roughness"].default_value = 0.48

    if normal_dx_path:
        normal = nodes.new("ShaderNodeTexImage")
        normal.image = bpy.data.images.load(str(normal_dx_path), check_existing=True)
        normal.image.colorspace_settings.name = "Non-Color"
        links.new(uv.outputs["UV"], normal.inputs["Vector"])
        # Production PNG stays DirectX (+V/down after Interchange) and Unreal's
        # Flip Green remains off.  Only the Blender preview converts its green
        # channel because Blender's tangent-space normal convention is OpenGL.
        separate = nodes.new("ShaderNodeSeparateColor")
        invert_green = nodes.new("ShaderNodeMath")
        invert_green.operation = "SUBTRACT"
        invert_green.inputs[0].default_value = 1.0
        combine = nodes.new("ShaderNodeCombineColor")
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.inputs["Strength"].default_value = 0.65
        links.new(normal.outputs["Color"], separate.inputs["Color"])
        links.new(separate.outputs["Red"], combine.inputs["Red"])
        links.new(separate.outputs["Green"], invert_green.inputs[1])
        links.new(invert_green.outputs[0], combine.inputs["Green"])
        links.new(separate.outputs["Blue"], combine.inputs["Blue"])
        links.new(combine.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])
    return material


def make_skin_material(name: str, color_path: Path, mask_path: Path | None,
                       normal_path: Path | None) -> bpy.types.Material:
    material = make_image_material(name, color_path, normal_dx_path=normal_path, uv_map="UV0")
    if mask_path is not None:
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        shader = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
        if "Specular IOR Level" in shader.inputs:
            shader.inputs["Specular IOR Level"].default_value = 0.18
        uv = next(node for node in nodes if node.type == "UVMAP")
        packed = nodes.new("ShaderNodeTexImage")
        packed.image = bpy.data.images.load(str(mask_path), check_existing=True)
        packed.image.colorspace_settings.name = "Non-Color"
        separate = nodes.new("ShaderNodeSeparateColor")
        links.new(uv.outputs["UV"], packed.inputs["Vector"])
        links.new(packed.outputs["Color"], separate.inputs["Color"])
        links.new(separate.outputs["Blue"], shader.inputs["Roughness"])
    return material


def make_timber_material(texture_dir: Path, silhouette: Silhouette) -> bpy.types.Material:
    material = bpy.data.materials.new("Timber")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UV1"
    vertex = nodes.new("ShaderNodeVertexColor")
    vertex.layer_name = VERTEX_COLOR_NAME
    separate = nodes.new("ShaderNodeSeparateColor")
    links.new(vertex.outputs["Color"], separate.inputs["Color"])

    textures = []
    for index, filename in enumerate((
        "T_FlatV3_AgedSoftwood_Color.png",
        "T_FlatV3_AgedPlywood_Stencil_Color.png",
        "T_FlatV3_AgedSteel_Color.png",
    )):
        texture = nodes.new("ShaderNodeTexImage")
        texture.image = bpy.data.images.load(str(texture_dir / filename), check_existing=True)
        if index != 1:
            links.new(uv.outputs["UV"], texture.inputs["Vector"])
        textures.append(texture)
    metric = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["UV"], metric.inputs["Vector"])
    normalize_u = nodes.new("ShaderNodeMath")
    normalize_u.operation = "MULTIPLY"
    normalize_u.inputs[1].default_value = 1.0 / silhouette.width_m
    links.new(metric.outputs["X"], normalize_u.inputs[0])
    normalized_u_socket = normalize_u.outputs[0]
    if silhouette.side == "R":
        add_one = nodes.new("ShaderNodeMath")
        add_one.operation = "ADD"
        add_one.inputs[1].default_value = 1.0
        links.new(normalize_u.outputs[0], add_one.inputs[0])
        normalized_u_socket = add_one.outputs[0]
    normalize_v = nodes.new("ShaderNodeMath")
    normalize_v.operation = "MULTIPLY"
    normalize_v.inputs[1].default_value = 1.0 / silhouette.height_m
    links.new(metric.outputs["Y"], normalize_v.inputs[0])
    normalized = nodes.new("ShaderNodeCombineXYZ")
    links.new(normalized_u_socket, normalized.inputs["X"])
    links.new(normalize_v.outputs[0], normalized.inputs["Y"])
    links.new(normalized.outputs["Vector"], textures[1].inputs["Vector"])
    textures[1].extension = "EXTEND"
    twice = nodes.new("ShaderNodeMath")
    twice.operation = "MULTIPLY"
    twice.inputs[1].default_value = 2.0
    links.new(separate.outputs["Red"], twice.inputs[0])
    mix_wood = nodes.new("ShaderNodeMixRGB")
    mix_wood.blend_type = "MIX"
    links.new(twice.outputs[0], mix_wood.inputs[0])
    links.new(textures[0].outputs["Color"], mix_wood.inputs[1])
    links.new(textures[1].outputs["Color"], mix_wood.inputs[2])
    steel_factor = nodes.new("ShaderNodeMapRange")
    steel_factor.inputs[1].default_value = 0.5
    steel_factor.inputs[2].default_value = 1.0
    steel_factor.inputs[3].default_value = 0.0
    steel_factor.inputs[4].default_value = 1.0
    steel_factor.clamp = True
    links.new(separate.outputs["Red"], steel_factor.inputs[0])
    mix_steel = nodes.new("ShaderNodeMixRGB")
    links.new(steel_factor.outputs[0], mix_steel.inputs[0])
    links.new(mix_wood.outputs[0], mix_steel.inputs[1])
    links.new(textures[2].outputs["Color"], mix_steel.inputs[2])
    links.new(mix_steel.outputs[0], shader.inputs["Base Color"])
    links.new(steel_factor.outputs[0], shader.inputs["Metallic"])
    shader.inputs["Roughness"].default_value = 0.72
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def make_materials(art: Path, skin_mask: Path | None, skin_normal: Path | None,
                   aged_texture_dir: Path, silhouette: Silhouette) -> list[bpy.types.Material]:
    front = make_skin_material("Front", art, skin_mask, skin_normal)
    flap = make_skin_material("Flap", art, skin_mask, skin_normal)
    timber = make_timber_material(aged_texture_dir, silhouette)
    edge = make_image_material("Edge", aged_texture_dir / "T_FlatV3_AgedSoftwood_Color.png", uv_map="UV1")
    return [front, flap, timber, edge]


def append_slots(obj: bpy.types.Object, materials: list[bpy.types.Material]) -> None:
    obj.data.materials.clear()
    for material in materials:
        obj.data.materials.append(material)


def assign_metric_uvs(obj: bpy.types.Object, silhouette: Silhouette | None = None,
                      board: bool = False) -> None:
    mesh = obj.data
    while mesh.uv_layers:
        mesh.uv_layers.remove(mesh.uv_layers[0])
    uv0 = mesh.uv_layers.new(name="UV0")
    uv1 = mesh.uv_layers.new(name="UV1")
    for polygon in mesh.polygons:
        slot_name = obj.material_slots[polygon.material_index].material.name if obj.material_slots else "Timber"
        normal = polygon.normal
        for loop_index in polygon.loop_indices:
            co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            if board and silhouette is not None:
                uv0.data[loop_index].uv = silhouette.uv0(co.y, co.z)
            else:
                uv0.data[loop_index].uv = (co.y, co.z)
            if slot_name in ("Front", "Flap"):
                metric_uv = (-co.y, 1.0 - co.z)
            elif abs(normal.x) >= abs(normal.y) and abs(normal.x) >= abs(normal.z):
                metric_uv = (-co.y, 1.0 - co.z)
            elif abs(normal.y) >= abs(normal.z):
                metric_uv = (co.x, 1.0 - co.z)
            else:
                metric_uv = (co.x, 1.0 + co.y)
            uv1.data[loop_index].uv = metric_uv


def ensure_vertex_colors(obj: bpy.types.Object, default=(0.0, 0.0, 0.0, 1.0)) -> bpy.types.Attribute:
    mesh = obj.data
    existing = mesh.color_attributes.get(VERTEX_COLOR_NAME)
    if existing is not None:
        mesh.color_attributes.remove(existing)
    color = mesh.color_attributes.new(name=VERTEX_COLOR_NAME, type="FLOAT_COLOR", domain="CORNER")
    for item in color.data:
        item.color = default
    return color


def color_object(obj: bpy.types.Object, red: float, green: float) -> None:
    color = ensure_vertex_colors(obj)
    for item in color.data:
        item.color = (red, green, 0.0, 1.0)


def rebuild_metric_uv1(obj: bpy.types.Object) -> None:
    """Reassert UV1 after Blender's object join, which can zero flap UV data."""
    uv1 = obj.data.uv_layers.get("UV1")
    if uv1 is None:
        uv1 = obj.data.uv_layers.new(name="UV1")
    for polygon in obj.data.polygons:
        slot_name = obj.material_slots[polygon.material_index].material.name
        normal = polygon.normal
        for loop_index in polygon.loop_indices:
            co = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            if slot_name in ("Front", "Flap"):
                metric_uv = (-co.y, 1.0 - co.z)
            elif abs(normal.x) >= abs(normal.y) and abs(normal.x) >= abs(normal.z):
                metric_uv = (-co.y, 1.0 - co.z)
            elif abs(normal.y) >= abs(normal.z):
                metric_uv = (co.x, 1.0 - co.z)
            else:
                metric_uv = (co.x, 1.0 + co.y)
            uv1.data[loop_index].uv = metric_uv


def rebuild_front_uv0(obj: bpy.types.Object, silhouette: Silhouette) -> None:
    uv0 = obj.data.uv_layers.get("UV0")
    if uv0 is None:
        uv0 = obj.data.uv_layers.new(name="UV0")
    for polygon in obj.data.polygons:
        slot_name = obj.material_slots[polygon.material_index].material.name
        if slot_name not in ("Front", "Flap"):
            continue
        for loop_index in polygon.loop_indices:
            co = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            uv0.data[loop_index].uv = silhouette.uv0(co.y, co.z)


def deterministic_cap_tessellation(
    silhouette: Silhouette,
) -> tuple[list[Vector], list[tuple[int, int, int]], int]:
    """Tessellate a mask cap, slicing only when Blender's hole limit requires it."""
    min_hole_area_px = (0.03 / silhouette.scale_m_per_px) ** 2
    tolerance_px = 0.0055 / silhouette.scale_m_per_px
    last_failure: dict | None = None

    def contains(loop: np.ndarray, point: np.ndarray) -> bool:
        x, y = float(point[0]), float(point[1])
        x0, y0 = loop[:, 0], loop[:, 1]
        x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
        crossing = ((y0 <= y) & (y < y1)) | ((y1 <= y) & (y < y0))
        intersections = x0[crossing] + (y - y0[crossing]) * (x1[crossing] - x0[crossing]) / (y1[crossing] - y0[crossing])
        return bool(np.count_nonzero(intersections > x) % 2)

    for slice_count in (1, 2, 4, 8, 16, 32):
        all_vertices: list[Vector] = []
        all_triangles: list[tuple[int, int, int]] = []
        valid = True
        skipped_hole_area = 0.0
        accepted_cap_area = 0.0
        for slice_index in range(slice_count):
            x0 = (silhouette.image_w * slice_index) // slice_count
            x1 = (silhouette.image_w * (slice_index + 1)) // slice_count
            chunk = silhouette.mask[:, x0:x1]
            if not chunk.any():
                continue
            raw_loops = mask_loops(chunk)
            raw_loops.sort(key=lambda loop: abs(signed_area(loop)), reverse=True)
            kept_pixel_loops = []
            for loop in raw_loops:
                area = signed_area(loop)
                if area > 0.0 or abs(area) >= min_hole_area_px:
                    simplified = simplify_closed(loop, tolerance_px).copy()
                    simplified[:, 0] += x0
                    kept_pixel_loops.append(simplified)
            physical_loops = [silhouette.pixel_to_physical(loop) for loop in kept_pixel_loops]
            oriented_loops = []
            for pixel_loop, physical_loop in zip(kept_pixel_loops, physical_loops):
                wants_positive = signed_area(pixel_loop) > 0.0
                is_positive = signed_area(physical_loop) > 0.0
                oriented = physical_loop if wants_positive == is_positive else physical_loop[::-1]
                oriented_loops.append([
                    Vector((float(y), float(z), 0.0)) for y, z in oriented
                ])
            outer_indices = [i for i, loop in enumerate(kept_pixel_loops) if signed_area(loop) > 0.0]
            hole_indices = [i for i, loop in enumerate(kept_pixel_loops) if signed_area(loop) < 0.0]
            assigned_holes: set[int] = set()
            for outer_index in outer_indices:
                group_indices = [outer_index]
                for hole_index in hole_indices:
                    if hole_index not in assigned_holes and contains(kept_pixel_loops[outer_index], kept_pixel_loops[hole_index][0]):
                        group_indices.append(hole_index)
                        assigned_holes.add(hole_index)
                accepted_indices = [outer_index]
                expected_area = abs(signed_area(physical_loops[outer_index]))
                flattened = list(oriented_loops[outer_index])
                triangles = tessellate_polygon([oriented_loops[outer_index]])
                for hole_index in group_indices[1:]:
                    candidate_indices = accepted_indices + [hole_index]
                    candidate_loops = [oriented_loops[index] for index in candidate_indices]
                    candidate_flattened = [vertex for loop in candidate_loops for vertex in loop]
                    candidate_triangles = tessellate_polygon(candidate_loops)
                    candidate_expected = expected_area - abs(signed_area(physical_loops[hole_index]))
                    candidate_area = sum(
                        abs((candidate_flattened[b] - candidate_flattened[a]).cross(candidate_flattened[c] - candidate_flattened[a]).z) * 0.5
                        for a, b, c in candidate_triangles
                    )
                    tolerance = max(1.0e-5, abs(candidate_expected) * 1.0e-6)
                    if candidate_triangles and abs(candidate_area - candidate_expected) <= tolerance:
                        accepted_indices = candidate_indices
                        expected_area = candidate_expected
                        flattened = candidate_flattened
                        triangles = candidate_triangles
                    else:
                        skipped_hole_area += abs(signed_area(physical_loops[hole_index]))
                tessellated_area = sum(
                    abs((flattened[b] - flattened[a]).cross(flattened[c] - flattened[a]).z) * 0.5
                    for a, b, c in triangles
                )
                tolerance = max(1.0e-5, abs(expected_area) * 1.0e-6)
                if not triangles or abs(tessellated_area - expected_area) > tolerance:
                    last_failure = {
                        "slice_count": slice_count, "slice_index": slice_index,
                        "loops": len(accepted_indices), "triangles": len(triangles),
                        "tessellated_area": tessellated_area,
                        "expected_area": expected_area,
                    }
                    valid = False
                    break
                base = len(all_vertices)
                all_vertices.extend(flattened)
                all_triangles.extend((base + a, base + b, base + c) for a, b, c in triangles)
                accepted_cap_area += expected_area
            if not valid:
                break
            if len(assigned_holes) != len(hole_indices):
                last_failure = {
                    "slice_count": slice_count, "slice_index": slice_index,
                    "unassigned_holes": len(hole_indices) - len(assigned_holes),
                }
                valid = False
                break
        if valid and all_triangles and skipped_hole_area / max(accepted_cap_area, 1.0e-9) < 0.0005:
            return all_vertices, all_triangles, slice_count
        if valid:
            last_failure = {
                "slice_count": slice_count,
                "skipped_hole_area": skipped_hole_area,
                "accepted_cap_area": accepted_cap_area,
                "skipped_fraction": skipped_hole_area / max(accepted_cap_area, 1.0e-9),
            }
    raise RuntimeError(
        "Deterministic board tessellation failed its signed-area gate at 32 slices: "
        + json.dumps(last_failure)
    )


def enforce_board_cap_contract(obj: bpy.types.Object) -> None:
    """Restore board cap material and winding after object consolidation.

    Join/consolidate can expose a triangulated sliver with stale material or
    winding even when the source board was correct.  Only the two exact board
    planes are touched; flaps, timber, edge returns, and hardware are excluded.
    """
    for polygon in obj.data.polygons:
        xs = [obj.data.vertices[index].co.x for index in polygon.vertices]
        if (polygon.material_index == 0 and polygon.area > 1.0e-10
                and all(abs(value - BOARD_FRONT_X) < 1.0e-5 for value in xs)):
            if polygon.normal.x > -0.9:
                polygon.flip()
        elif (polygon.material_index == 2 and polygon.area > 1.0e-10
              and all(abs(value - BOARD_BACK_X) < 1.0e-5 for value in xs)):
            if polygon.normal.x < 0.9:
                polygon.flip()
    obj.data.update()


def remove_degenerate_board_cap_faces(obj: bpy.types.Object) -> int:
    """Delete exact zero-area cap faces introduced while consolidating parts.

    The deterministic board tessellator rejects tiny source triangles, but the
    object join can still expose a collinear cap triangle.  Such a face has no
    physical surface or stable normal, and FBX preserves it as a Front/Timber
    polygon that correctly fails the normal gate.  Remove only degenerate faces
    lying on the two exact board planes; frame, flap, edge and hardware geometry
    is deliberately out of scope.
    """
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    degenerate = []
    for face in mesh.faces:
        is_front_cap = face.material_index == 0 and all(
            abs(vertex.co.x - BOARD_FRONT_X) < 1.0e-5 for vertex in face.verts
        )
        is_back_cap = face.material_index == 2 and all(
            abs(vertex.co.x - BOARD_BACK_X) < 1.0e-5 for vertex in face.verts
        )
        if (is_front_cap or is_back_cap) and face.calc_area() <= 1.0e-12:
            degenerate.append(face)
    removed = len(degenerate)
    if degenerate:
        bmesh.ops.delete(mesh, geom=degenerate, context="FACES")
        mesh.to_mesh(obj.data)
        obj.data.update()
    mesh.free()
    return removed


def triangulate_export_mesh(obj: bpy.types.Object) -> dict:
    """Make final FBX topology importer-independent without changing legacy builds.

    This runs after all card parts have been consolidated.  FIXED prevents the
    quad diagonal from depending on a beauty heuristic, and EAR_CLIP gives
    n-gons a fixed local tessellation rule.  Only zero/near-zero area output
    triangles are deleted; no vertex welding is performed because coincident
    positions can carry distinct UV, normal, material, or colour seams.
    """
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    mesh.faces.ensure_lookup_table()
    before = {
        "faces": len(mesh.faces),
        "triangles": sum(max(0, len(face.verts) - 2) for face in mesh.faces),
        "quads": sum(len(face.verts) == 4 for face in mesh.faces),
        "ngons": sum(len(face.verts) > 4 for face in mesh.faces),
    }
    bmesh.ops.triangulate(
        mesh,
        faces=list(mesh.faces),
        quad_method="FIXED",
        ngon_method="EAR_CLIP",
    )
    mesh.faces.ensure_lookup_table()
    # FBX stores float32 positions.  Sub-pixel slivers below 1e-8 m2 can
    # collapse to exactly collinear vertices on re-import even when Blender's
    # in-memory double-precision area is non-zero.
    degenerate = [face for face in mesh.faces if face.calc_area() <= 1.0e-8]
    removed = len(degenerate)
    if degenerate:
        bmesh.ops.delete(mesh, geom=degenerate, context="FACES")
    mesh.faces.ensure_lookup_table()
    if any(len(face.verts) != 3 for face in mesh.faces):
        raise RuntimeError(f"Triangulated export contract left a non-triangle in {obj.name}")
    minimum_area = min((float(face.calc_area()) for face in mesh.faces), default=0.0)
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.data.update()
    obj.data.calc_loop_triangles()
    after = {
        "faces": len(obj.data.polygons),
        "triangles": len(obj.data.loop_triangles),
        "quads": sum(len(polygon.vertices) == 4 for polygon in obj.data.polygons),
        "ngons": sum(len(polygon.vertices) > 4 for polygon in obj.data.polygons),
        "minimum_area_m2": minimum_area,
    }
    return {
        "enabled": True,
        "quad_method": "FIXED",
        "ngon_method": "EAR_CLIP",
        "degenerate_area_threshold_m2": 1.0e-8,
        "removed_degenerate_faces": removed,
        "before": before,
        "after": after,
    }


def create_board(
    name: str,
    silhouette: Silhouette,
    materials: list[bpy.types.Material],
    deterministic_triangulation: bool = False,
) -> bpy.types.Object:
    if deterministic_triangulation:
        # The physical mapping reverses contour winding.  Explicitly restore
        # outer-positive / hole-negative winding before tessellation; Blender's
        # Curve cap path can otherwise retain only a fraction of a highly
        # concave chroma-key silhouette.
        flattened, triangles, cap_slice_count = deterministic_cap_tessellation(silhouette)
        if not triangles:
            raise RuntimeError("Deterministic board tessellation produced no cap triangles")
        front_vertices = [(BOARD_FRONT_X, vertex.x, vertex.y) for vertex in flattened]
        back_vertices = [(BOARD_BACK_X, vertex.x, vertex.y) for vertex in flattened]
        offset = len(flattened)
        faces: list[tuple[int, ...]] = []
        material_indices: list[int] = []
        for a, b, c in triangles:
            signed = (flattened[b] - flattened[a]).cross(flattened[c] - flattened[a]).z
            # Below 1e-8 m2 the triangle is far smaller than one source pixel
            # and FBX may import it with a zero/unstable normal.
            if abs(signed) <= 1.0e-8:
                continue
            front = (a, c, b) if signed > 0.0 else (a, b, c)
            back = (offset + a, offset + b, offset + c) if signed > 0.0 else (offset + a, offset + c, offset + b)
            faces.append(front)
            material_indices.append(0)
            faces.append(back)
            material_indices.append(2)
        side_cursor = len(front_vertices) + len(back_vertices)
        side_vertices: list[tuple[float, float, float]] = []
        for loop in silhouette.physical_loops:
            count = len(loop)
            loop_start = side_cursor + len(side_vertices)
            side_vertices.extend((BOARD_FRONT_X, float(y), float(z)) for y, z in loop)
            side_vertices.extend((BOARD_BACK_X, float(y), float(z)) for y, z in loop)
            for local_index in range(count):
                a = loop_start + local_index
                b = loop_start + ((local_index + 1) % count)
                back_a = loop_start + count + local_index
                back_b = loop_start + count + ((local_index + 1) % count)
                faces.append((a, b, back_b, back_a))
                material_indices.append(3)
        mesh = bpy.data.meshes.new(name + "_Mesh")
        mesh.from_pydata(front_vertices + back_vertices + side_vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name + "_Board", mesh)
        bpy.context.collection.objects.link(obj)
        obj["DeterministicCapSlices"] = cap_slice_count
        append_slots(obj, materials)
        for polygon, material_index in zip(obj.data.polygons, material_indices):
            polygon.material_index = material_index
        assign_metric_uvs(obj, silhouette, board=True)
        colors = ensure_vertex_colors(obj)
        for polygon in obj.data.polygons:
            slot_name = obj.material_slots[polygon.material_index].material.name
            value = (0.5, 0.37, 0.0, 1.0) if slot_name == "Timber" else (0.0, 0.0, 0.0, 1.0)
            for loop_index in polygon.loop_indices:
                colors.data[loop_index].color = value
        return obj

    curve = bpy.data.curves.new(name + "_Profile", type="CURVE")
    curve.dimensions = "2D"
    curve.resolution_u = 1
    curve.render_resolution_u = 1
    curve.fill_mode = "BOTH"
    curve.extrude = (BOARD_BACK_X - BOARD_FRONT_X) * 0.5
    curve.resolution_u = 1
    for physical in silhouette.physical_loops:
        spline = curve.splines.new("POLY")
        spline.points.add(len(physical) - 1)
        for point, (y, z) in zip(spline.points, physical):
            point.co = (z, y, 0.0, 1.0)
        spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name + "_Board", curve)
    bpy.context.collection.objects.link(obj)
    obj.rotation_euler[1] = -math.pi * 0.5
    obj.location.x = (BOARD_FRONT_X + BOARD_BACK_X) * 0.5
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj = bpy.context.object
    z_values = [float(vertex.co.z) for vertex in obj.data.vertices]
    z_min, z_max = min(z_values), max(z_values)
    if z_max - z_min <= 1.0e-9:
        raise RuntimeError("Converted board has zero vertical extent")
    height_scale = silhouette.height_m / (z_max - z_min)
    for vertex in obj.data.vertices:
        vertex.co.z = (vertex.co.z - z_min) * height_scale
    obj.data.update()
    if deterministic_triangulation:
        modifier = obj.modifiers.new(name="TopBorderDeterministicTriangulation", type="TRIANGULATE")
        modifier.quad_method = "BEAUTY"
        modifier.ngon_method = "BEAUTY"
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        # Blender's curve-to-mesh conversion can leave an isolated cap triangle
        # with winding inconsistent with its neighbours.  Flip only those
        # planar polygons; recalculating the entire extruded mesh can alter cap
        # membership around complex chroma-key contours.
        for polygon in obj.data.polygons:
            xs = [obj.data.vertices[index].co.x for index in polygon.vertices]
            if all(abs(value - BOARD_FRONT_X) < 1.0e-5 for value in xs) and polygon.normal.x > 0.0:
                polygon.flip()
            elif all(abs(value - BOARD_BACK_X) < 1.0e-5 for value in xs) and polygon.normal.x < 0.0:
                polygon.flip()
        obj.data.update()
    append_slots(obj, materials)
    for polygon in obj.data.polygons:
        if polygon.normal.x < -0.5:
            polygon.material_index = 0
        elif polygon.normal.x > 0.5:
            polygon.material_index = 2
        else:
            polygon.material_index = 3
    assign_metric_uvs(obj, silhouette, board=True)
    colors = ensure_vertex_colors(obj)
    for polygon in obj.data.polygons:
        slot_name = obj.material_slots[polygon.material_index].material.name
        value = (0.5, 0.37, 0.0, 1.0) if slot_name == "Timber" else (0.0, 0.0, 0.0, 1.0)
        for loop_index in polygon.loop_indices:
            colors.data[loop_index].color = value
    return obj


def create_box_member(name: str, p0: tuple[float, float], p1: tuple[float, float],
                      face_width: float, x_front: float, x_back: float,
                      materials: list[bpy.types.Material], material_index: int,
                      vc_red: float = 0.0, vc_green: float = 0.0) -> bpy.types.Object:
    y0, z0 = p0
    y1, z1 = p1
    direction = Vector((0.0, y1 - y0, z1 - z0))
    length = direction.length
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=((x_front + x_back) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (abs(x_back - x_front), face_width, length)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(direction.normalized())
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    append_slots(obj, materials)
    for polygon in obj.data.polygons:
        polygon.material_index = material_index
    assign_metric_uvs(obj)
    color_object(obj, vc_red, vc_green)
    return obj


def create_triangle_block(name: str, center: tuple[float, float], size: float,
                          materials: list[bpy.types.Material]) -> bpy.types.Object:
    y, z = center
    yz = [(y - size * 0.5, z - size * 0.5), (y + size * 0.5, z - size * 0.5), (y - size * 0.5, z + size * 0.5)]
    verts = [(FRAME_BACK_X, a, b) for a, b in yz] + [(BLOCK_BACK_X, a, b) for a, b in yz]
    faces = [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    append_slots(obj, materials)
    for polygon in mesh.polygons:
        polygon.material_index = 2
    assign_metric_uvs(obj)
    color_object(obj, 0.5, 0.61)
    return obj


def boolean_runs(values: np.ndarray) -> list[tuple[int, int]]:
    padded = np.concatenate(([False], values, [False])).astype(np.int8)
    transitions = np.diff(padded)
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1) - 1
    return list(zip(starts.tolist(), ends.tolist()))


def longest_vertical(silhouette: Silhouette, y_values: np.ndarray,
                     margin: float) -> tuple[float, float, float]:
    z_values = np.arange(0.0, silhouette.height_m + 0.0001, 0.025)
    best = None
    half_width = MEMBER_FACE_M * 0.5
    edge_margin = max(0.0, margin - half_width)
    for y in y_values:
        # Validate the full member strip, not only a centreline with an
        # approximate distance allowance. Pixel-mask membership can differ on
        # the two stile edges around small internal cutouts even when the
        # centreline has ample distance from the simplified vector boundary.
        points = np.vstack([
            np.column_stack((np.full_like(z_values, y), z_values)),
            np.column_stack((np.full_like(z_values, y - half_width), z_values)),
            np.column_stack((np.full_like(z_values, y + half_width), z_values)),
        ])
        allowed = silhouette.allowed(points, edge_margin).reshape(3, len(z_values)).all(axis=0)
        for start, end in boolean_runs(allowed):
            length = z_values[end] - z_values[start]
            candidate = (length, float(y), float(z_values[start]), float(z_values[end]))
            if best is None or candidate > best:
                best = candidate
    if best is None or best[0] < 0.30:
        raise RuntimeError("Could not find a viable vertical stile run")
    return best[1], best[2], best[3]


def member_samples(p0: tuple[float, float], p1: tuple[float, float], width: float) -> np.ndarray:
    a = np.asarray(p0, dtype=np.float64)
    b = np.asarray(p1, dtype=np.float64)
    delta = b - a
    length = float(np.linalg.norm(delta))
    count = max(2, int(math.ceil(length / 0.02)) + 1)
    t = np.linspace(0.0, 1.0, count)
    center = a[None, :] + t[:, None] * delta[None, :]
    normal = np.asarray((-delta[1], delta[0]), dtype=np.float64) / max(length, 1e-9)
    return np.vstack((center, center + normal * width * 0.5, center - normal * width * 0.5))


def member_random(name: str) -> float:
    return 0.08 + 0.84 * ((sum((index + 1) * ord(char) for index, char in enumerate(name)) % 997) / 996.0)


def build_frame(
    silhouette: Silhouette,
    materials: list[bpy.types.Material],
    shallow: bool = False,
    top_border: bool = False,
) -> tuple[list[bpy.types.Object], list[dict], list[float], dict]:
    objects: list[bpy.types.Object] = []
    members: list[dict] = []
    # FBX/Interchange reflects Blender Y. Author L on -Y and R on +Y so the
    # imported Unreal mesh satisfies L +Y / R -Y with zero actor rotation.
    sign = -1.0 if silhouette.side == "L" else 1.0
    inward = np.linspace(0.10, max(0.11, silhouette.width_m * 0.34), 22) * sign
    stile_search_mode = "backbone_third"
    try:
        pole_stiles = [longest_vertical(
            silhouette, inward, EDGE_INSET_M + MEMBER_FACE_M * 0.5
        )]
    except RuntimeError:
        # Narrow offstage stakes (for example a tied pyre bundle) can be too
        # thin for a 5 cm stile plus the full 8 cm reveal. Search the entire
        # silhouette for a genuinely inset run before giving up; this keeps the
        # frame hidden without relaxing the containment gate.
        full_width = np.linspace(0.10, max(0.11, silhouette.width_m - 0.10), 64) * sign
        try:
            pole_stiles = [longest_vertical(
                silhouette, full_width, EDGE_INSET_M + MEMBER_FACE_M * 0.5
            )]
            stile_search_mode = "full_width_fallback"
        except RuntimeError:
            if not shallow:
                raise
            # A 1.2 m rolling crest can contain no 30 cm vertical run with the full
            # 8 cm reveal. Wave rows are explicitly rail/toggle frames with no pole
            # or socket contract, so keep their valid horizontal subframe instead
            # of inventing an out-of-silhouette stile.
            pole_stiles = []
            stile_search_mode = "shallow_no_stile"
    pole_count = 2 if pole_stiles and silhouette.width_m > 4.0 else len(pole_stiles)
    if pole_count == 2:
        second_band = np.linspace(silhouette.width_m * 0.48, silhouette.width_m * 0.82, 24) * sign
        try:
            pole_stiles.append(longest_vertical(
                silhouette, second_band, EDGE_INSET_M + MEMBER_FACE_M * 0.5
            ))
        except RuntimeError:
            # Sparse tree/candelabrum silhouettes can be physically wide but
            # contain no second continuous 30 cm run. Keep the measured first
            # stile and let the unchanged rail/brace and containment gates prove
            # the smaller valid frame instead of inventing off-board timber.
            stile_search_mode += "+single_stile_sparse_second_band"

    backbone_y = sign * (EDGE_INSET_M + MEMBER_FACE_M * 0.5)
    backbone = (backbone_y, EDGE_INSET_M + MEMBER_FACE_M * 0.5,
                silhouette.height_m - EDGE_INSET_M - MEMBER_FACE_M * 0.5)
    backbone_samples = member_samples((backbone[0], backbone[1]), (backbone[0], backbone[2]), MEMBER_FACE_M)
    stiles = [backbone] + pole_stiles if silhouette.allowed(backbone_samples, EDGE_INSET_M).all() else pole_stiles

    for index, (y, z0, z1) in enumerate(stiles, start=1):
        label = "BackboneStile" if (y, z0, z1) == backbone else "PoleStile"
        obj = create_box_member(f"Frame_{label}_{index}", (y, z0), (y, z1), MEMBER_FACE_M,
                                BOARD_BACK_X, FRAME_BACK_X, materials, 2,
                                0.0, member_random(f"{label}_{index}"))
        objects.append(obj)
        members.append({"kind": "stile", "name": obj.name, "p0": [y, z0], "p1": [y, z1], "width_m": MEMBER_FACE_M})

    rail_records = []
    rail_scan_best = {"length_m": 0.0, "height_m": None}
    y_min = -silhouette.width_m if silhouette.side == "L" else 0.0
    y_max = 0.0 if silhouette.side == "L" else silhouette.width_m
    y_values = np.arange(y_min, y_max + 0.0001, 0.02)
    shallow_rail_start = EDGE_INSET_M + MEMBER_FACE_M * 0.5
    rail_heights = (
        np.arange(1.5, silhouette.height_m, 1.5)
        if top_border else
        np.arange(
            shallow_rail_start,
            max(shallow_rail_start + 0.001, silhouette.height_m - shallow_rail_start),
            0.05,
        ) if shallow else
        np.arange(1.5, silhouette.height_m, 1.5)
    )
    for rail_z in rail_heights:
        points = np.column_stack((y_values, np.full_like(y_values, rail_z)))
        allowed = silhouette.allowed(points, EDGE_INSET_M + MEMBER_FACE_M * 0.5)
        for run_index, (start, end) in enumerate(boolean_runs(allowed), start=1):
            y0, y1 = float(y_values[start]), float(y_values[end])
            if abs(y1 - y0) > rail_scan_best["length_m"]:
                rail_scan_best = {"length_m": abs(y1 - y0), "height_m": float(rail_z)}
            minimum_rail_length_m = 0.18 if shallow else 0.30
            if abs(y1 - y0) < minimum_rail_length_m:
                continue
            endpoint_inset = min(0.03, max(0.0, (abs(y1 - y0) - minimum_rail_length_m) * 0.25))
            direction = 1.0 if y1 >= y0 else -1.0
            y0 += direction * endpoint_inset
            y1 -= direction * endpoint_inset
            # Centreline scans can bridge a narrow see-through hole above or
            # below the line. Validate the complete 5 cm member strip before
            # creating it; invalid sub-runs are omitted, never accepted by
            # weakening the final 8 cm containment gate.
            rail_samples = member_samples((y0, rail_z), (y1, rail_z), MEMBER_FACE_M)
            if not silhouette.allowed(rail_samples, EDGE_INSET_M).all():
                continue
            # A shallow, pole-free wave has neither a pole nor a full-height
            # stile to carry the hardware ID.  Put that required ID on its
            # first valid rail while retaining the usual timber ID on all
            # remaining rails.  The high green value also preserves the
            # required per-asset variation range on these very small frames.
            is_shallow_hardware_id = shallow and not rail_records
            vc_red = 1.0 if is_shallow_hardware_id else 0.0
            vc_green = 0.8 if is_shallow_hardware_id else member_random(f"Rail_{rail_z}_{run_index}")
            obj = create_box_member(f"Frame_Rail_{int(round(rail_z * 100)):04d}_{run_index}",
                                    (y0, rail_z), (y1, rail_z), MEMBER_FACE_M,
                                    BOARD_BACK_X, FRAME_BACK_X, materials, 2,
                                    vc_red, vc_green)
            objects.append(obj)
            record = {"kind": "rail", "name": obj.name, "p0": [y0, rail_z], "p1": [y1, rail_z], "width_m": MEMBER_FACE_M}
            members.append(record)
            rail_records.append(record)

    # Half-bay toggles give the back a readable rhythm at 6-10 m while each
    # member remains the specified 5 x 10 cm section.
    toggle_heights = (
        np.arange(0.75, silhouette.height_m, 1.5)
        if top_border else
        np.arange(0.375, max(0.376, silhouette.height_m - 0.19), 0.35)
        if shallow else
        np.arange(0.75, silhouette.height_m, 1.5)
    )
    for toggle_z in toggle_heights:
        points = np.column_stack((y_values, np.full_like(y_values, toggle_z)))
        allowed = silhouette.allowed(points, EDGE_INSET_M + MEMBER_FACE_M * 0.5)
        for run_index, (start, end) in enumerate(boolean_runs(allowed), start=1):
            y0, y1 = float(y_values[start]), float(y_values[end])
            if abs(y1 - y0) < 0.45:
                continue
            endpoint_inset = min(0.03, max(0.0, (abs(y1 - y0) - 0.45) * 0.25))
            direction = 1.0 if y1 >= y0 else -1.0
            y0 += direction * endpoint_inset
            y1 -= direction * endpoint_inset
            toggle_samples = member_samples((y0, toggle_z), (y1, toggle_z), MEMBER_FACE_M)
            if not silhouette.allowed(toggle_samples, EDGE_INSET_M).all():
                continue
            obj = create_box_member(f"Frame_Toggle_{int(round(toggle_z * 100)):04d}_{run_index}",
                                    (y0, toggle_z), (y1, toggle_z), MEMBER_FACE_M,
                                    BOARD_BACK_X, FRAME_BACK_X, materials, 2,
                                    0.0, member_random(f"Toggle_{toggle_z}_{run_index}"))
            objects.append(obj)
            members.append({"kind": "toggle", "name": obj.name, "p0": [y0, toggle_z], "p1": [y1, toggle_z], "width_m": MEMBER_FACE_M})

    brace = None
    # Wave rows use the shallow rail/toggle frame declared by their mount. A
    # full diagonal cannot remain inset beneath a 1.2-2.6 m rolling crest and
    # is not part of the sea-row contract.
    if silhouette.width_m > 3.0:
        if shallow:
            brace_heights = ()
        else:
            # Try the established show-scale braces first, then search the
            # actual silhouette at half-metre intervals. Irregular 8 m clouds
            # can have no valid path at the four legacy endpoint heights even
            # though a fully inset diagonal exists elsewhere.
            legacy_heights = ((1.5, 6.0), (1.5, 4.5), (3.0, 7.5), (3.0, 6.0))
            levels = np.arange(0.5, max(0.51, silhouette.height_m - 0.25), 0.5)
            searched_heights = [
                (float(z0), float(z1))
                for z0 in levels
                for z1 in levels
                if z1 - z0 >= 1.5
            ]
            brace_heights = tuple(dict.fromkeys(legacy_heights + tuple(searched_heights)))
        for z0, z1 in brace_heights:
            if z1 <= z0 + MEMBER_FACE_M:
                continue
            low = np.column_stack((y_values, np.full_like(y_values, z0)))
            high = np.column_stack((y_values, np.full_like(y_values, z1)))
            low_y = y_values[silhouette.allowed(low, EDGE_INSET_M + MEMBER_FACE_M * 0.75)][::8]
            high_y = y_values[silhouette.allowed(high, EDGE_INSET_M + MEMBER_FACE_M * 0.75)][::8]
            candidates = []
            for a in low_y:
                for b in high_y:
                    if abs(float(b - a)) >= min(3.0, silhouette.width_m * 0.42):
                        candidates.append((abs(float(b - a)), float(a), float(b)))
            for _, a, b in sorted(candidates, reverse=True):
                samples = member_samples((a, z0), (b, z1), MEMBER_FACE_M)
                if silhouette.allowed(samples, EDGE_INSET_M).all():
                    obj = create_box_member("Frame_Diagonal_1", (a, z0), (b, z1), MEMBER_FACE_M,
                                            BOARD_BACK_X, FRAME_BACK_X, materials, 2,
                                            0.0, member_random("Diagonal_1"))
                    objects.append(obj)
                    brace = {"kind": "diagonal", "name": obj.name, "p0": [a, z0], "p1": [b, z1], "width_m": MEMBER_FACE_M}
                    members.append(brace)
                    break
            if brace:
                break
        if brace is None and not shallow:
            has_toggle = any(member["kind"] == "toggle" for member in members)
            if stiles and rail_records and has_toggle:
                # A sparse tree/candelabrum can be wider than 3 m while leaving
                # no continuous diagonal corridor. Retain its measured
                # stile/rail/toggle frame; the unchanged containment audit still
                # rejects any timber that escapes the board silhouette.
                stile_search_mode += "+sparse_rail_toggle_no_diagonal"
            else:
                raise RuntimeError("Panel exceeds 300 cm but no inset-safe diagonal brace could be placed")

    block_count = 0
    for stile_y, z0, z1 in stiles:
        for rail in rail_records:
            rz = rail["p0"][1]
            lo, hi = sorted((rail["p0"][0], rail["p1"][0]))
            if z0 + 0.18 < rz < z1 - 0.18 and lo + 0.18 < stile_y < hi - 0.18:
                corners = np.asarray([
                    [stile_y - 0.15, rz - 0.15], [stile_y + 0.15, rz - 0.15],
                    [stile_y - 0.15, rz + 0.15]
                ])
                if silhouette.allowed(corners, EDGE_INSET_M).all():
                    block_count += 1
                    block = create_triangle_block(f"Ply_CornerBlock_{block_count}", (stile_y, rz), 0.30, materials)
                    color_object(block, 0.5, member_random(block.name))
                    objects.append(block)
                    members.append({"kind": "corner_block", "name": block.name, "center": [stile_y, rz], "size_m": 0.30})
                if block_count >= 6:
                    break
        if block_count >= 6:
            break

    for index, (y, z0, z1) in enumerate(pole_stiles, start=1):
        preferred_z = min(max(z0 + 0.35, 0.35), z1 - 0.20)
        candidates = [preferred_z]
        candidates.extend(float(value) for value in np.arange(z0 + 0.20, z1 - 0.19, 0.10))
        plate_z = next((value for value in candidates
                        if silhouette.allowed(
                            member_samples((y, value - 0.10), (y, value + 0.10), 0.12),
                            MIN_FRAME_EDGE_CLEARANCE_M,
                        ).all()), None)
        if plate_z is None:
            raise RuntimeError(f"No inset-safe clamp plate position for pole stile {index}")
        plate = create_box_member(f"Hardware_ClampPlate_{index}", (y, plate_z - 0.10), (y, plate_z + 0.10),
                                  0.12, BOARD_BACK_X, BOARD_BACK_X + 0.006, materials, 2,
                                  1.0, member_random(f"Clamp_{index}"))
        objects.append(plate)
        members.append({"kind": "hardware_plate", "name": plate.name, "p0": [y, plate_z - 0.10], "p1": [y, plate_z + 0.10], "width_m": 0.12})

    sample_sets = []
    member_sample_sets = []
    for member in members:
        if "p0" in member:
            samples = member_samples(tuple(member["p0"]), tuple(member["p1"]), float(member["width_m"]))
        elif member["kind"] == "corner_block":
            y, z = member["center"]
            s = member["size_m"] * 0.5
            samples = np.asarray([[y - s, z - s], [y + s, z - s], [y - s, z + s], [y, z]])
        else:
            continue
        sample_sets.append(samples)
        member_sample_sets.append((member["name"], samples))
    if not sample_sets:
        raise RuntimeError(f"No inset-safe frame members could be placed; best rail: {rail_scan_best}")
    tested = np.vstack(sample_sets)
    inside = silhouette.inside(tested)
    distances = silhouette.boundary_distance(tested)
    offending_members = []
    for name, samples in member_sample_sets:
        member_inside = silhouette.inside(samples)
        member_distances = silhouette.boundary_distance(samples)
        if not member_inside.all() or member_distances.min() < MIN_FRAME_EDGE_CLEARANCE_M - 0.0005:
            offending_members.append({
                "name": name,
                "outside_outline_samples": int((~member_inside).sum()),
                "minimum_edge_clearance_cm": round(float(member_distances.min()) * 100.0, 4),
            })
    visibility = {
        "stile_search_mode": stile_search_mode,
        "tested_projection_samples": int(len(tested)),
        "outside_outline_samples": int((~inside).sum()),
        "minimum_edge_clearance_cm": round(float(distances.min()) * 100.0, 4),
        "required_edge_clearance_cm": MIN_FRAME_EDGE_CLEARANCE_M * 100.0,
        "offending_members": offending_members,
        "pass": bool(inside.all() and distances.min() >= MIN_FRAME_EDGE_CLEARANCE_M - 0.0005),
    }
    if not visibility["pass"]:
        raise RuntimeError(f"Head-on frame containment failed: {visibility}")
    return objects, members, [float(stile[0]) for stile in pole_stiles], visibility


def create_flaps(path: Path, silhouette: Silhouette,
                 materials: list[bpy.types.Material]) -> tuple[list[bpy.types.Object], list[dict]]:
    descriptors = json.loads(path.read_text(encoding="utf-8"))["flaps"]
    objects = []
    records = []
    for descriptor in descriptors:
        u0, v0, u1, v1 = descriptor["uv_bounds_bottom_left"]
        horizontal = descriptor["orientation"] == "horizontal"
        curl_m = float(descriptor["curl_cm"]) / 100.0
        outline = descriptor.get("outline_uv_bottom_left")
        if outline and len(outline) >= 5:
            uv_values = [(float(u), float(v)) for u, v in outline]
            axis_values = [value[1] if horizontal else value[0] for value in uv_values]
            axis_min, axis_max = min(axis_values), max(axis_values)
            signed = 0.5 * sum(
                uv_values[index][0] * uv_values[(index + 1) % len(uv_values)][1]
                - uv_values[(index + 1) % len(uv_values)][0] * uv_values[index][1]
                for index in range(len(uv_values))
            )
            # UV0 U now decreases along Blender +Y.  That reflection means a
            # counter-clockwise UV outline becomes clockwise in physical Y/Z
            # and therefore faces the review camera (-X).
            if signed < 0.0:
                uv_values.reverse()
            weights = []
            vertices = []
            for u, v in uv_values:
                axis_value = v if horizontal else u
                raw_weight = (axis_value - axis_min) / max(axis_max - axis_min, 1e-6)
                # Irregular OpenCV contours contain collinear extremum points
                # that FBX triangulation may discard. Give both ends saturated
                # bands so retained triangle corners still carry the documented
                # 0.0 hinge and 1.0 free weights after re-import.
                weight = (raw_weight - 0.18) / 0.52
                weight = float(np.clip(weight, 0.0, 1.0))
                y, z = silhouette.uv0_to_physical(u, v)
                x = BOARD_FRONT_X - 0.001 - math.sin(weight * math.pi * 0.5) * curl_m
                vertices.append((x, y, z))
                weights.append(weight)
            faces = [tuple(range(len(vertices)))]
        else:
            # Compatibility path for older descriptors.  New production skins
            # carry the measured component outline and never use this rectangle.
            along_steps, across_steps = 7, 5
            vertices = []
            uv_values = []
            weights = []
            for along in range(along_steps + 1):
                s = along / along_steps
                for across in range(across_steps + 1):
                    t = across / across_steps
                    phase = 1.7 * len(objects) + along * 1.31
                    left_inset = (0.035 + 0.085 * (0.5 + 0.5 * math.sin(phase))) * s
                    right_inset = (0.035 + 0.085 * (0.5 + 0.5 * math.cos(phase * 1.19))) * s
                    if horizontal:
                        u = u0 + (u1 - u0) * (left_inset + t * (1.0 - left_inset - right_inset))
                        free_rag = (0.14 * math.sin((t * 5.0 + len(objects)) * 2.1)) * (s ** 4)
                        v = v0 + (v1 - v0) * np.clip(s + free_rag, 0.0, 1.0)
                    else:
                        v = v0 + (v1 - v0) * (left_inset + t * (1.0 - left_inset - right_inset))
                        free_rag = (0.14 * math.sin((t * 5.0 + len(objects)) * 2.1)) * (s ** 4)
                        u = u0 + (u1 - u0) * np.clip(s + free_rag, 0.0, 1.0)
                    y, z = silhouette.uv0_to_physical(u, v)
                    x = BOARD_FRONT_X - 0.001 - math.sin(s * math.pi * 0.5) * curl_m
                    vertices.append((x, y, z))
                    uv_values.append((u, v))
                    weights.append(s)
            faces = []
            row = across_steps + 1
            for along in range(along_steps):
                for across in range(across_steps):
                    a = along * row + across
                    b, c, d = a + 1, a + row + 1, a + row
                    faces.append((a, b, c, d))
        mesh = bpy.data.meshes.new(descriptor["name"] + "_Mesh")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(descriptor["name"], mesh)
        bpy.context.collection.objects.link(obj)
        append_slots(obj, materials)
        for polygon in mesh.polygons:
            polygon.material_index = 1
        uv0 = mesh.uv_layers.new(name="UV0")
        uv1 = mesh.uv_layers.new(name="UV1")
        colors = mesh.color_attributes.new(name=VERTEX_COLOR_NAME, type="FLOAT_COLOR", domain="CORNER")
        for polygon in mesh.polygons:
            for loop_index in polygon.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                u, v = uv_values[vertex_index]
                y = vertices[vertex_index][1]
                z = vertices[vertex_index][2]
                uv0.data[loop_index].uv = (u, v)
                uv1.data[loop_index].uv = (y, z)
                colors.data[loop_index].color = (weights[vertex_index], 0.0, 0.0, 1.0)
        objects.append(obj)
        mesh.calc_loop_triangles()
        records.append({**descriptor, "vertices": len(vertices), "triangles": len(mesh.loop_triangles), "hinge_weight": 0.0, "free_weight": 1.0})
    if not (3 <= len(objects) <= 6):
        raise RuntimeError(f"Flat contract requires 3-6 flaps; got {len(objects)}")
    return objects, records


def consolidate_flat(name: str, board: bpy.types.Object, parts: list[bpy.types.Object],
                     materials: list[bpy.types.Material]) -> tuple[bpy.types.Object, dict]:
    source_counts = {"board": sum(len(obj.data.loop_triangles) for obj in [])}
    all_objects = [board] + parts
    counts = {}
    for obj in all_objects:
        obj.data.calc_loop_triangles()
        if obj is board:
            key = "profile_board"
        elif "_Flap_" in obj.name:
            key = "flaps"
        elif obj.name.startswith("Frame_"):
            key = "timber_frame"
        elif obj.name.startswith("Ply_"):
            key = "ply_corner_blocks"
        else:
            key = "flat_hardware"
        counts[key] = counts.get(key, 0) + len(obj.data.loop_triangles)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in all_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = board
    bpy.ops.object.join()
    flat = bpy.context.object
    flat.name = name
    face_names = []
    for polygon in flat.data.polygons:
        slot = flat.material_slots[polygon.material_index]
        face_names.append(slot.material.name if slot.material else "Timber")
    append_slots(flat, materials)
    lookup = {material_name: index for index, material_name in enumerate(MATERIAL_SLOTS)}
    for polygon, material_name in zip(flat.data.polygons, face_names):
        polygon.material_index = lookup.get(material_name, 2)
    rebuild_metric_uv1(flat)
    if [slot.material.name for slot in flat.material_slots] != MATERIAL_SLOTS:
        raise RuntimeError("Flat material-slot consolidation failed")
    if [layer.name for layer in flat.data.uv_layers] != ["UV0", "UV1"]:
        raise RuntimeError(f"Unexpected flat UV layers: {[layer.name for layer in flat.data.uv_layers]}")
    flat.data.calc_loop_triangles()
    counts["flat_total"] = len(flat.data.loop_triangles)
    return flat, counts


def create_socket(name: str, location: tuple[float, float, float], rotation: Matrix | None = None) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = 0.18
    obj.location = location
    if rotation is not None:
        obj.rotation_euler = rotation.to_euler()
    return obj


def create_sockets(side: str, silhouette: Silhouette, pole_y: list[float]) -> list[bpy.types.Object]:
    sockets = []
    for index, y in enumerate(pole_y, start=1):
        sockets.append(create_socket(f"SOCKET_Pole_{index}", (0.0, y, 0.0)))
    hinge_rotation = Matrix.Rotation(math.pi * 0.5, 3, "Z")
    pivot_rotation = Matrix.Rotation(-math.pi * 0.5, 3, "Y")
    sockets.append(create_socket("SOCKET_Hinge", (0.0, 0.0, 0.0), hinge_rotation))
    sockets.append(create_socket("SOCKET_Pivot", (0.0, (silhouette.width_m * 0.5) * (-1 if side == "L" else 1), silhouette.height_m * 0.5), pivot_rotation))
    return sockets


def unreal_socket_sidecar(asset_name: str, side: str, silhouette: Silhouette,
                          pole_y: list[float]) -> dict:
    """Return the UE-local sockets that correspond to the exported FBX empties.

    UE Interchange reflects FBX Y on import.  Locations therefore negate the
    Blender Y value.  The hinge's +90 degree Blender Z rotation becomes -90
    degrees of UE yaw; the pivot's -90 degree Blender Y rotation becomes +90
    degrees of UE pitch.  Pole sockets have identity rotation.
    """
    return make_socket_payload(
        asset=asset_name,
        side=side,
        mount="wing",
        height_cm=silhouette.height_m * 100.0,
        width_m=silhouette.width_m,
        pole_positions_y_m=pole_y,
    )


def create_stencil(side: str, silhouette: Silhouette, material: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.object.text_add()
    text = bpy.context.object
    text.name = f"DECAL_PUSS_P02_{side}01"
    text.data.body = f"PUSS \u00b7 P02 \u00b7 {side}01"
    text.data.align_x = "CENTER"
    text.data.align_y = "CENTER"
    text.data.size = 0.18
    text.data.extrude = 0.0003
    text.data.materials.append(material)
    basis = Matrix(((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
    text.rotation_euler = basis.to_euler()
    text.location = (BOARD_BACK_X + 0.001, (silhouette.width_m * 0.35) * (-1 if side == "L" else 1), min(2.2, silhouette.height_m * 0.28))
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    text = bpy.context.object
    text.data.calc_loop_triangles()
    return text


def create_pole(materials: list[bpy.types.Material]) -> bpy.types.Object:
    center_z = (POLE_UNIT_BOTTOM_M + POLE_UNIT_TOP_M) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=POLE_DIAMETER_M * 0.5,
                                       depth=POLE_UNIT_TOP_M - POLE_UNIT_BOTTOM_M,
                                       location=(0.0, 0.0, center_z))
    shaft = bpy.context.object
    shaft.name = "SM_FlatV3_Pole_Shaft"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.034, minor_radius=0.004,
                                    major_segments=32, minor_segments=8, location=(0.0, 0.0, 0.050))
    collar = bpy.context.object
    collar.name = "SM_FlatV3_Pole_ClampCollar"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for obj in (shaft, collar):
        append_slots(obj, materials)
        for polygon in obj.data.polygons:
            polygon.material_index = 2
        assign_metric_uvs(obj)
        color_object(obj, 1.0, member_random(obj.name))
    bpy.ops.object.select_all(action="DESELECT")
    shaft.select_set(True)
    collar.select_set(True)
    bpy.context.view_layer.objects.active = shaft
    bpy.ops.object.join()
    pole = bpy.context.object
    pole.name = "SM_FlatV3_Pole"
    append_slots(pole, materials)
    for polygon in pole.data.polygons:
        polygon.material_index = 2
    assign_metric_uvs(pole)
    color_object(pole, 1.0, member_random(pole.name))
    pole.data.calc_loop_triangles()
    return pole


def create_baked_poles(pole_y: list[float], height_m: float,
                       materials: list[bpy.types.Material], lod_label: str,
                       extension_cm: float = 100.0) -> tuple[list[bpy.types.Object], list[dict]]:
    """Create deterministic, joined-card copies of the shared pole profile.

    The shared pole is authored as a one-metre module whose normalized bounds
    retain the 10 m pilot proportions. Scaling and translating that exact mesh
    gives every baked pole the requested foot and a top 0.2 m above the card.
    """
    bottom_m = -float(extension_cm) / 100.0
    top_m = height_m + 0.2
    span_m = top_m - bottom_m
    translation_z = bottom_m - POLE_UNIT_BOTTOM_M * span_m
    poles = []
    records = []
    for index, y in enumerate(pole_y, start=1):
        pole = create_pole(materials)
        pole.name = f"BakedPole_{lod_label}_{index}"
        pole.location = (0.0, y, translation_z)
        pole.scale.z = span_m
        bpy.ops.object.select_all(action="DESELECT")
        pole.select_set(True)
        bpy.context.view_layer.objects.active = pole
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        pole.data.calc_loop_triangles()
        poles.append(pole)
        records.append({
            "name": pole.name,
            "socket": f"SOCKET_Pole_{index}",
            "axis_m": [0.0, float(y)],
            "bottom_z_m": bottom_m,
            "top_z_m": top_m,
            "shaft_diameter_m": POLE_DIAMETER_M,
            "material_slot": "Timber",
            "vertex_colour_red": 1.0,
            "triangles": len(pole.data.loop_triangles),
        })
    return poles, records


def create_floor_and_groove(width_m: float, side: str, materials: list[bpy.types.Material]) -> list[bpy.types.Object]:
    floor_mat = bpy.data.materials.new("RenderFloor")
    floor_mat.diffuse_color = (0.055, 0.035, 0.020, 1.0)
    groove_mat = bpy.data.materials.new("RenderGroove")
    groove_mat.diffuse_color = (0.015, 0.018, 0.020, 1.0)
    objs = []
    y_center = width_m * 0.5 * (-1 if side == "L" else 1)
    for name, x_center in (("Floor_Front", -2.04), ("Floor_Back", 2.04)):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x_center, y_center, -0.04))
        obj = bpy.context.object
        obj.name = name
        obj.dimensions = (4.0, width_m + 2.0, 0.08)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj.data.materials.append(floor_mat)
        objs.append(obj)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, y_center, -0.16))
    groove = bpy.context.object
    groove.name = "Dummy_8cm_Groove"
    groove.dimensions = (0.08, width_m + 2.0, 0.12)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    groove.data.materials.append(groove_mat)
    objs.append(groove)
    return objs


def export_selection(path: Path, objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={"MESH", "EMPTY"},
        apply_scale_options="FBX_SCALE_UNITS", axis_forward="-X", axis_up="Z",
        bake_space_transform=False, add_leaf_bones=False, path_mode="AUTO",
        use_custom_props=True,
    )


def create_lod_group(flat_name: str, lod0: bpy.types.Object, lod1: bpy.types.Object) -> bpy.types.Object:
    """Create the FBX LodGroup hierarchy consumed by Unreal Interchange."""
    group = bpy.data.objects.new(flat_name + "_LODGroup", None)
    bpy.context.collection.objects.link(group)
    group["fbx_type"] = "LodGroup"
    group["LODOrder"] = "LOD0,LOD1"
    for child in (lod0, lod1):
        child.parent = group
    return group


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_cycles(samples: int) -> dict:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    chosen = []
    cycles = bpy.context.preferences.addons.get("cycles")
    if cycles:
        preferences = cycles.preferences
        for backend in ("OPTIX", "CUDA"):
            try:
                preferences.compute_device_type = backend
                preferences.get_devices()
                devices = [device for device in preferences.devices if device.type == backend]
                if devices:
                    for device in preferences.devices:
                        device.use = device in devices
                    chosen = [device.name for device in devices]
                    break
            except Exception:
                continue
    if not chosen:
        raise RuntimeError("Cycles GPU requested but no OPTIX/CUDA device was available")
    scene.render.engine = "CYCLES"
    scene.cycles.device = "GPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.004, 0.005, 0.007)
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.75
    return {"backend": preferences.compute_device_type, "devices": chosen, "samples": samples}


def add_area_light(name: str, location: tuple[float, float, float], target: tuple[float, float, float], energy: float, size: float) -> None:
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = "RECTANGLE"
    data.size = size
    data.size_y = size * 1.8
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)


def renderable_scene_objects() -> list[str]:
    return sorted(
        obj.name for obj in bpy.context.scene.objects
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"} and not obj.hide_render
    )


def assert_render_object_list(expected_objects: list[bpy.types.Object], label: str) -> list[str]:
    expected = sorted(obj.name for obj in expected_objects)
    for obj in bpy.context.scene.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            obj.hide_render = obj.name not in expected
    actual = renderable_scene_objects()
    if actual != expected:
        raise RuntimeError(f"Render {label} object list mismatch: actual={actual}; expected={expected}")
    return actual


def render_views(output_dir: Path, base_name: str, side: str, silhouette: Silhouette,
                 flap_records: list[dict], samples: int,
                 expected_objects: list[bpy.types.Object]) -> dict:
    gpu = configure_cycles(samples)
    center_y = silhouette.width_m * 0.5 * (-1 if side == "L" else 1)
    center = (BOARD_FRONT_X, center_y, silhouette.height_m * 0.5)
    sign = -1.0 if side == "L" else 1.0
    add_area_light(
        "Warm_Raking_Key",
        (-2.35, center_y - sign * (silhouette.width_m * 0.72 + 1.0), 7.2),
        center,
        380.0,
        4.5,
    )
    bpy.data.lights["Warm_Raking_Key"].color = (1.0, 0.80, 0.68)
    add_area_light("Warm_Soft_Front", (-5.8, center_y, 5.9), center, 360.0, 9.0)
    bpy.data.lights["Warm_Soft_Front"].color = (1.0, 0.93, 0.86)
    add_area_light("Warm_Top_Edge", (-0.9, center_y + sign * 5.0, 11.3), (BOARD_FRONT_X, center_y, 6.6), 100.0, 3.0)
    bpy.data.lights["Warm_Top_Edge"].color = (1.0, 0.86, 0.74)
    add_area_light("Very_Low_Fill", (-1.8, center_y + sign * 4.5, 3.8), center, 35.0, 4.0)
    bpy.data.lights["Very_Low_Fill"].color = (0.35, 0.40, 0.50)

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    flap_bounds = flap_records[0]["uv_bounds_bottom_left"]
    flap_u = (flap_bounds[0] + flap_bounds[2]) * 0.5
    flap_v = (flap_bounds[1] + flap_bounds[3]) * 0.5
    flap_y, flap_z = silhouette.uv0_to_physical(flap_u, flap_v)
    flap_target = (BOARD_FRONT_X - 0.02, flap_y, flap_z)
    grazing_y = center_y + (-5.196 if side == "L" else 5.196)
    views = {
        "head_on_6m": {"loc": (BOARD_FRONT_X - 6.0, center_y, silhouette.height_m * 0.5), "target": center, "lens": 15.0},
        "front_head_on_poles": {"loc": (BOARD_FRONT_X - 9.0, center_y, 4.6), "target": (BOARD_FRONT_X, center_y, 4.6), "lens": 20.0},
        "front_three_quarter_poles": {"loc": (BOARD_FRONT_X - 8.0, center_y - sign * 5.0, 4.6), "target": (BOARD_FRONT_X, center_y, 4.6), "lens": 20.0},
        "peel_closeup_1m": {"loc": (flap_target[0] - 0.96, flap_target[1] + (-0.28 if side == "L" else 0.28), flap_target[2] + 0.06), "target": flap_target, "lens": 48.0},
        "grazing_30deg": {"loc": (BOARD_FRONT_X - 3.0, grazing_y, silhouette.height_m * 0.53), "target": center, "lens": 30.0},
        "back_three_quarter_2m": {"loc": (BOARD_BACK_X + 1.65, center_y - (-1.1 if side == "L" else 1.1), 2.0), "target": (BOARD_BACK_X, center_y, 2.0), "lens": 28.0},
        "back_head_on": {"loc": (BOARD_BACK_X + 6.0, center_y, silhouette.height_m * 0.5), "target": (BOARD_BACK_X, center_y, silhouette.height_m * 0.5), "lens": 15.0},
    }
    outputs = {}
    object_lists = {}
    for label, settings in views.items():
        camera.location = settings["loc"]
        look_at(camera, settings["target"])
        camera.data.type = "PERSP"
        camera.data.lens = settings["lens"]
        path = output_dir / f"{base_name}_{label}.png"
        object_lists[label] = assert_render_object_list(expected_objects, label)
        bpy.context.scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        outputs[label] = str(path)
    return {"cycles_gpu": gpu, "renders": outputs, "asserted_object_lists": object_lists}


def object_triangles(obj: bpy.types.Object) -> int:
    if obj.type != "MESH":
        return 0
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def panel_geometry_contract(objects: list[bpy.types.Object]) -> dict:
    """Fingerprint card art/frame geometry before baked poles are joined.

    The contract deliberately excludes baked poles.  It records the triangulated
    surface, UV0 and UV1 independently so a pole-only variant can prove that its
    panel triangles and both UV channels are byte-for-byte deterministic.
    """
    triangle_rows = []
    uv0_rows = []
    uv1_rows = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        mesh = obj.data
        mesh.calc_loop_triangles()
        uv0 = mesh.uv_layers.get("UV0")
        uv1 = mesh.uv_layers.get("UV1")
        for triangle in mesh.loop_triangles:
            polygon = mesh.polygons[triangle.polygon_index]
            slot = (obj.material_slots[polygon.material_index].material.name
                    if 0 <= polygon.material_index < len(obj.material_slots)
                    and obj.material_slots[polygon.material_index].material else "")
            positions = []
            tex0 = []
            tex1 = []
            for loop_index in triangle.loops:
                vertex_index = mesh.loops[loop_index].vertex_index
                co = obj.matrix_world @ mesh.vertices[vertex_index].co
                positions.append([round(float(value), 8) for value in co])
                tex0.append([round(float(value), 8) for value in uv0.data[loop_index].uv]
                            if uv0 is not None else None)
                tex1.append([round(float(value), 8) for value in uv1.data[loop_index].uv]
                            if uv1 is not None else None)
            # Preserve winding but remove the arbitrary choice of first corner.
            rotations = [positions[index:] + positions[:index] for index in range(3)]
            first = min(range(3), key=lambda index: rotations[index])
            positions = rotations[first]
            tex0 = tex0[first:] + tex0[:first]
            tex1 = tex1[first:] + tex1[:first]
            triangle_rows.append([slot, positions])
            uv0_rows.append([slot, positions, tex0])
            uv1_rows.append([slot, positions, tex1])
    triangle_rows.sort()
    uv0_rows.sort()
    uv1_rows.sort()

    def digest(rows: list) -> str:
        payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return {
        "triangle_count": len(triangle_rows),
        "triangles_sha256": digest(triangle_rows),
        "uv0_sha256": digest(uv0_rows),
        "uv1_sha256": digest(uv1_rows),
        "scope": "profile board, flaps, frame and hardware; baked poles excluded",
    }


def build(args: argparse.Namespace) -> None:
    if not all((args.mask, args.art, args.skin_mask, args.skin_normal, args.flaps,
                args.height_cm, args.side, args.name, args.output_dir,
                args.texture_root, args.aged_texture_dir)):
        raise RuntimeError("Build mode requires mask, three skin inputs, flaps, dimensions, output and texture roots")
    clear_scene()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    mask = load_mask(Path(args.mask).resolve())
    silhouette = Silhouette(mask, args.height_cm / 100.0, args.side)
    is_wave_row = args.mount == "wave-row"
    is_top_border = args.mount == "top-border"
    is_pole_free_mount = is_wave_row or is_top_border
    if args.pole_extension_cm <= 0.0:
        raise RuntimeError("--pole-extension-cm must be positive")
    if abs(args.pole_extension_cm - 100.0) > 1.0e-6 and not args.bake_poles:
        raise RuntimeError("--pole-extension-cm requires --bake-poles")
    materials = make_materials(
        Path(args.art).resolve(), Path(args.skin_mask).resolve(),
        Path(args.skin_normal).resolve(), Path(args.aged_texture_dir).resolve(), silhouette)
    asset_suffix = args.asset_name or f"{args.name}_{args.side}"
    flat_name = f"SM_FlatV3_{asset_suffix}"
    deterministic_triangulation = is_top_border or args.deterministic_triangulation
    board = create_board(
        flat_name + "_LOD0", silhouette, materials,
        deterministic_triangulation=deterministic_triangulation,
    )
    lod1 = create_board(
        flat_name + "_LOD1", silhouette, materials,
        deterministic_triangulation=deterministic_triangulation,
    )
    lod1.name = flat_name + "_LOD1"
    flap_objects, flap_records = create_flaps(Path(args.flaps).resolve(), silhouette, materials)
    parts, members, pole_y, visibility = build_frame(
        silhouette, materials, shallow=is_pole_free_mount, top_border=is_top_border
    )
    panel_contract = panel_geometry_contract([board, *flap_objects, *parts])
    lod1_panel_contract = panel_geometry_contract([lod1])
    if args.bake_poles and is_pole_free_mount:
        raise RuntimeError("--bake-poles is valid only for wing-mounted flats")
    baked_lod0, baked_pole_records = (create_baked_poles(
        pole_y, silhouette.height_m, materials, "LOD0", args.pole_extension_cm)
                                      if args.bake_poles else ([], []))
    baked_lod1, _ = (create_baked_poles(
        pole_y, silhouette.height_m, materials, "LOD1", args.pole_extension_cm)
                     if args.bake_poles else ([], []))
    flat, triangle_counts = consolidate_flat(flat_name + "_LOD0", board, flap_objects + parts + baked_lod0, materials)
    if baked_lod1:
        lod1, lod1_counts = consolidate_flat(flat_name + "_LOD1", lod1, baked_lod1, materials)
    else:
        lod1_counts = {"flat_total": object_triangles(lod1)}
    removed_degenerate_caps = {
        "lod0": remove_degenerate_board_cap_faces(flat),
        "lod1": remove_degenerate_board_cap_faces(lod1),
    }
    for key in ("profile_board", "flat_total"):
        if key in triangle_counts:
            triangle_counts[key] -= removed_degenerate_caps["lod0"]
        if key in lod1_counts:
            lod1_counts[key] -= removed_degenerate_caps["lod1"]
    enforce_board_cap_contract(flat)
    enforce_board_cap_contract(lod1)
    rebuild_front_uv0(flat, silhouette)
    export_topology = None
    if args.triangulate_export:
        export_topology = {
            "lod0": triangulate_export_mesh(flat),
            "lod1": triangulate_export_mesh(lod1),
        }
        triangle_counts["flat_total"] = object_triangles(flat)
        lod1_counts["flat_total"] = object_triangles(lod1)
    flat["FrontAxis"] = "-X"
    flat["PlacementContract"] = ("Origin=BottomCentre; Scale=1" if is_pole_free_mount else
                                 "Origin=PoleLineX_BackboneY_FloorZ; Scale=1")
    flat["Side"] = args.side
    flat["Mount"] = args.mount
    flat["TriangulatedExport"] = bool(args.triangulate_export)
    lod1["TriangulatedExport"] = bool(args.triangulate_export)
    flat["BakedPoles"] = bool(args.bake_poles)
    flat["PoleCount"] = len(pole_y)
    flat["FrameStileSearchMode"] = visibility["stile_search_mode"]
    pole_foot_z_m = -float(args.pole_extension_cm) / 100.0
    flat["PoleFootZM"] = pole_foot_z_m if args.bake_poles else 0.0
    flat["PoleTopZM"] = silhouette.height_m + 0.2 if args.bake_poles else 0.0
    lod1["BakedPoles"] = bool(args.bake_poles)
    lod1["PoleCount"] = len(pole_y)
    lod1["FrameStileSearchMode"] = visibility["stile_search_mode"]
    lod1["PoleFootZM"] = pole_foot_z_m if args.bake_poles else 0.0
    lod1["PoleTopZM"] = silhouette.height_m + 0.2 if args.bake_poles else 0.0
    flat["LODContract"] = ("LOD0 board flaps frame hardware baked poles" if args.bake_poles else
                           "LOD0 board flaps frame hardware")
    lod1["LODContract"] = ("LOD1 board plus baked poles; no frame hardware flaps" if args.bake_poles else
                           "LOD1 board only; no frame hardware flaps")
    centre_offset_m = ((-silhouette.width_m * 0.5 if args.side == "L" else silhouette.width_m * 0.5)
                       if is_pole_free_mount else 0.0)
    if is_pole_free_mount:
        for mesh in (flat, lod1):
            for vertex in mesh.data.vertices:
                vertex.co.y -= centre_offset_m
            rebuild_metric_uv1(mesh)
            mesh.data.update()
    for mesh in (flat, lod1):
        mesh["UV0ImageWidth"] = silhouette.image_w
        mesh["UV0ImageHeight"] = silhouette.image_h
        mesh["UV0UMin"] = silhouette.u_min
        mesh["UV0UMax"] = silhouette.u_max
        mesh["UV0VMin"] = silhouette.v_min
        mesh["UV0MetresPerPixel"] = silhouette.scale_m_per_px
        mesh["UV0Side"] = args.side
        mesh["UV0CentreOffsetM"] = centre_offset_m
    lod_group = create_lod_group(flat_name, flat, lod1)
    sockets = [] if is_pole_free_mount else create_sockets(args.side, silhouette, pole_y)
    lod1_triangles = object_triangles(lod1)

    pole = None
    pole_triangles = 0
    pole_fbx = None
    if not is_pole_free_mount:
        pole = create_pole(materials)
        pole_triangles = object_triangles(pole)
        pole_fbx = output_dir / "SM_FlatV3_Pole.fbx"
        if args.skip_pole_export and not pole_fbx.is_file():
            raise RuntimeError(f"Cannot skip missing shared pole FBX: {pole_fbx}")
        if not args.skip_pole_export:
            export_selection(pole_fbx, [pole])
        pole.hide_render = True
        pole.hide_set(True)

    pole_instances = []
    if pole is not None and not args.bake_poles:
        for index, y in enumerate(pole_y, start=1):
            instance = bpy.data.objects.new(f"Pole_{args.side}_{index}", pole.data)
            bpy.context.collection.objects.link(instance)
            instance.location = (0.0, y, 0.0)
            instance.scale.z = POLE_SCALE_FOR_10M if abs(args.height_cm - 1000.0) < 0.01 else (args.height_cm / 100.0 + 1.2)
            pole_instances.append(instance)

    floor = [] if is_pole_free_mount else create_floor_and_groove(silhouette.width_m, args.side, materials)
    flat_fbx = output_dir / f"{flat_name}.fbx"
    export_selection(flat_fbx, [lod_group, flat, lod1] + sockets)
    socket_sidecar = output_dir / f"sockets_{flat_name}.json"
    socket_payload = make_socket_payload(
        asset=flat_name,
        side=args.side,
        mount=args.mount,
        height_cm=silhouette.height_m * 100.0,
        width_m=silhouette.width_m,
        pole_positions_y_m=pole_y,
        pole_extension_cm=args.pole_extension_cm if args.bake_poles else None,
    )
    socket_sidecar.write_text(json.dumps(socket_payload, indent=2) + "\n", encoding="utf-8")
    lod1.hide_render = True

    # Preserve the authored scene as the reusable source.  Review renders below
    # use a fresh import of the just-written FBX, so an export-time UV change is
    # visible instead of being hidden by the in-memory authoring mesh.
    blend_path = output_dir / f"{args.name}_{args.side}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    render_result = None
    if args.render:
        flat.name = flat.name + "_AuthoringSource"
        flat.hide_render = True
        before_import = set(bpy.context.scene.objects)
        bpy.ops.import_scene.fbx(filepath=str(flat_fbx), use_custom_normals=True)
        imported = [obj for obj in bpy.context.scene.objects if obj not in before_import]
        imported_meshes = [obj for obj in imported if obj.type == "MESH"]
        imported_lod0 = [obj for obj in imported_meshes if obj.name.startswith(flat_name + "_LOD0")]
        imported_lod1 = [obj for obj in imported_meshes if obj.name.startswith(flat_name + "_LOD1")]
        if len(imported_lod0) != 1:
            raise RuntimeError(f"Preview re-import expected one LOD0; got {[obj.name for obj in imported_meshes]}")
        preview_flat = imported_lod0[0]
        for imported_mesh in imported_lod1:
            imported_mesh.hide_render = True
        expected_render_objects = [preview_flat, *pole_instances, *floor]
        render_result = render_views(
            output_dir, f"{args.name}_{args.side}", args.side, silhouette,
            flap_records, args.samples, expected_render_objects,
        )
        render_result["mesh_source"] = str(flat_fbx)
        render_result["mesh_source_contract"] = "fresh Blender FBX re-import; direct UV0 sampling with no 1-v"
    manifest = {
        "schema_version": 2,
        "blender": bpy.app.version_string,
        "headless": bpy.app.background,
        "name": args.name,
        "side": args.side,
        "mount": args.mount,
        "inputs": {"mask": str(Path(args.mask).resolve()), "art": str(Path(args.art).resolve()), "skin_mask": str(Path(args.skin_mask).resolve()), "skin_normal": str(Path(args.skin_normal).resolve()), "flaps": str(Path(args.flaps).resolve()), "height_cm": args.height_cm},
        "dimensions_m": {"height": silhouette.height_m, "width": silhouette.width_m, "flat_depth": BLOCK_BACK_X - BOARD_FRONT_X},
        "placement": {"origin_m": [0.0, 0.0, 0.0], "origin_contract": "bottom-centre" if is_pole_free_mount else "pole-line/backbone/floor", "front_axis": "-X", "backbone_y_m": None if is_pole_free_mount else 0.0, "floor_z_m": 0.0, "front_face_x_m": BOARD_FRONT_X},
        "mask": {"pixel_size": [silhouette.image_w, silhouette.image_h], "outer_vertices": len(silhouette.pixel_loops[0]), "hole_count": len(silhouette.pixel_loops) - 1, "metres_per_pixel": silhouette.scale_m_per_px},
        "pole_positions_y_m": pole_y,
        "baked_poles": {
            "enabled": bool(args.bake_poles),
            "extension_below_panel_cm": float(args.pole_extension_cm) if args.bake_poles else 0.0,
            "bottom_z_m": pole_foot_z_m if args.bake_poles else 0.0,
            "top_z_m": silhouette.height_m + 0.2 if args.bake_poles else 0.0,
            "interim_non_toppling_only": bool(args.bake_poles),
            "lods": ["LOD0", "LOD1"] if args.bake_poles else [],
            "records": baked_pole_records,
            "shared_pole_fbx_unchanged_when_skip_pole_export": bool(args.skip_pole_export),
        },
        "sockets": [socket.name for socket in sockets],
        "frame_members": members,
        "flaps": flap_records,
        "head_on_frame_visibility": visibility,
        "removed_degenerate_board_cap_faces": removed_degenerate_caps,
        "art_panel_geometry_contract": {
            "lod0": panel_contract,
            "lod1": lod1_panel_contract,
        },
        "triangulated_export": export_topology or {"enabled": False},
        "triangle_counts": {**triangle_counts, "lod1_total": lod1_triangles,
                            "lod1_board_without_baked_poles": lod1_counts.get("profile_board", lod1_counts.get("flat_total")),
                            "shared_pole": pole_triangles},
        "material_slots": MATERIAL_SLOTS,
        "uv_layers": [layer.name for layer in flat.data.uv_layers],
        "vertex_colour_contract": {"layer": VERTEX_COLOR_NAME, "Flap.R": "flutter weight; 0 hinge to 1 free", "Timber.R": "0 softwood; 0.5 ply; 1 steel", "Timber.G": "deterministic per-member variation"},
        "lods": {
            "mechanism": "FBX LodGroup NodeAttribute",
            "group": lod_group.name,
            "children_in_order": [flat.name, lod1.name],
            "LOD0": flat.name,
            "LOD1": lod1.name,
            "LOD1_excludes": ["frame", "hardware", "flaps"],
            "LOD1_keeps": ["board", "baked_poles"] if args.bake_poles else ["board"],
        },
        "outputs": {
            "flat_fbx": str(flat_fbx),
            "socket_json": str(socket_sidecar),
            "pole_fbx": str(pole_fbx) if pole_fbx else None,
            "pole_exported_this_run": bool(pole_fbx and not args.skip_pole_export),
            "blend": str(blend_path),
        },
        "render": render_result,
    }
    (output_dir / f"{args.name}_{args.side}_build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("FLAT_V3_BUILD_OK " + json.dumps({"side": args.side, "flat": str(flat_fbx), "visibility": visibility, "triangles": manifest["triangle_counts"]}), flush=True)


def transformed_bounds(obj: bpy.types.Object) -> tuple[np.ndarray, np.ndarray]:
    coords = np.asarray([tuple(obj.matrix_world @ vertex.co) for vertex in obj.data.vertices], dtype=np.float64)
    return coords.min(axis=0), coords.max(axis=0)


def vertex_color_layer(obj: bpy.types.Object):
    layers = obj.data.color_attributes
    return layers.get(VERTEX_COLOR_NAME) or (layers[0] if len(layers) else None)


def material_bounds(obj: bpy.types.Object, slots: list[str], slot_name: str) -> tuple[np.ndarray, np.ndarray] | None:
    points = []
    for polygon in obj.data.polygons:
        if not (0 <= polygon.material_index < len(slots)) or slots[polygon.material_index] != slot_name:
            continue
        for vertex_index in polygon.vertices:
            points.append(tuple(obj.matrix_world @ obj.data.vertices[vertex_index].co))
    if not points:
        return None
    values = np.asarray(points, dtype=np.float64)
    return values.min(axis=0), values.max(axis=0)


def validate_baked_poles(obj: bpy.types.Object, slots: list[str], socket_objects: dict[str, bpy.types.Object],
                         expected_height_m: float, expected_bottom_m: float) -> dict:
    layer = vertex_color_layer(obj)
    timber_index = slots.index("Timber") if "Timber" in slots else -1
    pole_sockets = sorted(name for name in socket_objects if name.startswith("SOCKET_Pole_"))
    details = {}
    passed = bool(layer is not None and timber_index >= 0 and pole_sockets)
    for socket_name in pole_sockets:
        socket = socket_objects[socket_name]
        socket_location = socket.matrix_world.translation
        samples = []
        red_values = []
        for polygon in obj.data.polygons:
            if polygon.material_index != timber_index:
                continue
            for loop_index in polygon.loop_indices:
                co = obj.matrix_world @ obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
                red = float(layer.data[loop_index].color[0]) if layer is not None else -1.0
                if red >= 0.97 and abs(float(co.x)) <= 0.05 and abs(float(co.y - socket_location.y)) <= 0.05:
                    samples.append((float(co.x), float(co.y), float(co.z)))
                    red_values.append(red)
        if samples:
            unique = np.unique(np.asarray(samples, dtype=np.float64), axis=0)
            lower = unique.min(axis=0)
            upper = unique.max(axis=0)
            axis_x = float((lower[0] + upper[0]) * 0.5)
            axis_y = float((lower[1] + upper[1]) * 0.5)
            detail_pass = bool(
                abs(float(lower[2]) - expected_bottom_m) <= 0.002
                and float(upper[2]) >= expected_height_m + 0.19
                and abs(axis_x - float(socket_location.x)) <= 0.002
                and abs(axis_y - float(socket_location.y)) <= 0.002
                and min(red_values) >= 0.97
            )
            details[socket_name] = {
                "pass": detail_pass,
                "socket_location_m": list(map(float, socket_location)),
                "pole_axis_m": [axis_x, axis_y],
                "bounds_min_z_m": float(lower[2]),
                "bounds_max_z_m": float(upper[2]),
                "required_min_z_m": expected_bottom_m,
                "required_top_above_m": expected_height_m,
                "timber_vc_red_range": [min(red_values), max(red_values)],
                "sample_count": len(unique),
            }
        else:
            detail_pass = False
            details[socket_name] = {"pass": False, "reason": "no Timber VC.R=1 pole geometry on socket axis"}
        passed = passed and detail_pass
    return {"pass": bool(passed), "details": details, "lod": obj.name}


def validate_metric_uv1(obj: bpy.types.Object, slots: list[str], *, interchange_precompensated: bool = True) -> dict:
    uv = obj.data.uv_layers.get("UV1")
    if uv is None:
        return {"pass": False, "reason": "UV1 missing"}
    maximum_error = 0.0
    worst = None
    samples = 0
    for polygon in obj.data.polygons:
        slot = slots[polygon.material_index] if 0 <= polygon.material_index < len(slots) else None
        for loop_index in polygon.loop_indices:
            co = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            actual = np.asarray(uv.data[loop_index].uv, dtype=np.float64)
            if not interchange_precompensated:
                options = [np.asarray((co.y, co.z)), np.asarray((co.x, co.z)), np.asarray((co.x, co.y))]
            elif slot in ("Front", "Flap"):
                options = [np.asarray((-co.y, 1.0 - co.z), dtype=np.float64)]
            else:
                options = [np.asarray((-co.y, 1.0 - co.z)), np.asarray((co.x, 1.0 - co.z)), np.asarray((co.x, 1.0 + co.y))]
            error = min(float(np.linalg.norm(actual - option)) for option in options)
            if error > maximum_error:
                maximum_error = error
                worst = {"slot": slot, "actual": actual.tolist(), "vertex_m": [float(co.x), float(co.y), float(co.z)], "options": [option.tolist() for option in options]}
            samples += 1
    return {"pass": maximum_error <= 0.0015 and samples > 0, "maximum_error_m": maximum_error, "samples": samples, "worst": worst}


def validate_front_uv0(obj: bpy.types.Object, slots: list[str]) -> dict:
    uv = obj.data.uv_layers.get("UV0")
    if uv is None:
        return {"pass": False, "reason": "UV0 missing"}
    required_props = ("UV0ImageWidth", "UV0ImageHeight", "UV0UMin", "UV0UMax", "UV0VMin", "UV0MetresPerPixel", "UV0Side")
    missing_props = [name for name in required_props if name not in obj]
    if missing_props:
        return {"pass": False, "reason": "UV0 source-registration metadata missing", "missing": missing_props}
    image_w = float(obj["UV0ImageWidth"])
    image_h = float(obj["UV0ImageHeight"])
    u_min = float(obj["UV0UMin"])
    u_max = float(obj["UV0UMax"])
    v_min = float(obj["UV0VMin"])
    metres_per_pixel = float(obj["UV0MetresPerPixel"])
    side = str(obj["UV0Side"])
    centre_offset_m = float(obj.get("UV0CentreOffsetM", 0.0))
    maximum_error = 0.0
    samples = 0
    flap_samples = 0
    for polygon in obj.data.polygons:
        slot = slots[polygon.material_index] if 0 <= polygon.material_index < len(slots) else None
        if slot not in ("Front", "Flap"):
            continue
        for loop_index in polygon.loop_indices:
            co = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            source_u = ((u_min - (co.y + centre_offset_m) / metres_per_pixel) if side == "L" else
                        (u_max - (co.y + centre_offset_m) / metres_per_pixel))
            source_v = v_min + co.z / metres_per_pixel
            expected = np.asarray((source_u / image_w, source_v / image_h))
            actual = np.asarray(uv.data[loop_index].uv)
            maximum_error = max(maximum_error, float(np.linalg.norm(actual - expected)))
            samples += 1
            flap_samples += int(slot == "Flap")
    return {
        "pass": maximum_error <= 0.00001 and flap_samples > 0,
        "maximum_error": maximum_error,
        "samples": samples,
        "flap_samples": flap_samples,
        "mapping": "source mask pixel registration",
    }


def linear_uv_slope(obj: bpy.types.Object, slots: list[str], slot_name: str, uv_component: int,
                    coordinate_component: int) -> dict:
    """Fit one UV component against one imported mesh coordinate."""
    uv = obj.data.uv_layers.get("UV0")
    if uv is None or slot_name not in slots:
        return {"pass": False, "reason": f"UV0 or {slot_name} slot missing"}
    slot_index = slots.index(slot_name)
    unique = set()
    for polygon in obj.data.polygons:
        if polygon.material_index != slot_index:
            continue
        for loop_index in polygon.loop_indices:
            vertex_index = obj.data.loops[loop_index].vertex_index
            co = obj.data.vertices[vertex_index].co
            value = uv.data[loop_index].uv[uv_component]
            unique.add((vertex_index, round(float(co[coordinate_component]), 9), round(float(value), 9)))
    samples = sorted(unique)
    if len(samples) < 2:
        return {"pass": False, "reason": "insufficient distinct vertex/UV samples", "samples": len(samples)}
    values = np.asarray([(sample[1], sample[2]) for sample in samples], dtype=np.float64)
    design = np.column_stack((values[:, 0], np.ones(len(values))))
    slope, intercept = np.linalg.lstsq(design, values[:, 1], rcond=None)[0]
    predicted = design @ np.asarray((slope, intercept))
    residual = float(np.sum((values[:, 1] - predicted) ** 2))
    total = float(np.sum((values[:, 1] - values[:, 1].mean()) ** 2))
    r_squared = 1.0 if total <= 1.0e-24 and residual <= 1.0e-24 else (1.0 - residual / total if total > 0.0 else 0.0)
    return {
        "pass": bool(slope < 0.0 if coordinate_component == 1 else slope > 0.0),
        "samples": len(samples),
        "slope_per_m": float(slope),
        "slope_per_cm": float(slope) / 100.0,
        "intercept": float(intercept),
        "r_squared": float(r_squared),
        "raw_fbx_contract": "du/dY < 0" if coordinate_component == 1 else "dv/dZ > 0",
    }


def validate_uv0_axis_contract(obj: bpy.types.Object, slots: list[str]) -> dict:
    sections = {}
    for slot_name in ("Front", "Flap"):
        sections[slot_name] = {
            "du_dY": linear_uv_slope(obj, slots, slot_name, 0, 1),
            "dv_dZ": linear_uv_slope(obj, slots, slot_name, 1, 2),
        }
        sections[slot_name]["pass"] = all(check["pass"] for check in sections[slot_name].values())
    return {
        "pass": all(section["pass"] for section in sections.values()),
        "sections": sections,
        "raw_fbx_export_contract": "Flat V3 U decreases along Blender +Y to precompensate Interchange Y reflection; legacy-matching V increases bottom-to-top along +Z",
        "expected_unreal_interchange": "du/dY > 0 and dv/dZ < 0 after Interchange axis/UV conversion",
    }


def validate_front_texture_coverage(
    obj: bpy.types.Object,
    slots: list[str],
    skin_color_path: Path,
) -> dict:
    """Rasterise exported Front UV0 onto SkinColor and count background texels.

    Boundary edges are recovered from the imported FBX Front polygons, then an
    even/odd scanline fill evaluates every covered SkinColor texel centre.  This
    catches a mesh/paint silhouette mismatch that UV-coordinate checks cannot.
    """
    uv = obj.data.uv_layers.get("UV0")
    if uv is None:
        return {"pass": False, "reason": "UV0 missing"}
    if not skin_color_path.exists():
        return {"pass": False, "reason": f"SkinColor missing: {skin_color_path}"}
    front_index = slots.index("Front") if "Front" in slots else -1
    if front_index < 0:
        return {"pass": False, "reason": "Front slot missing"}

    front_uv_polygons: list[np.ndarray] = []
    for polygon in obj.data.polygons:
        if polygon.material_index != front_index:
            continue
        front_uv_polygons.append(np.asarray([
            tuple(float(value) for value in uv.data[loop_index].uv)
            for loop_index in polygon.loop_indices
        ], dtype=np.float64))
    if not front_uv_polygons:
        return {"pass": False, "reason": "No Front UV polygons recovered"}

    image = bpy.data.images.load(str(skin_color_path), check_existing=False)
    image.colorspace_settings.name = "sRGB"
    width, height = map(int, image.size)
    rgba = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(rgba)
    # Blender exposes file pixels bottom row first, which already matches UV
    # v=0.  Keep that row order; flipping it reintroduces the rejected mismatch.
    rgba = rgba.reshape((height, width, 4))
    bpy.data.images.remove(image)

    # Rasterise the exported Front polygons themselves.  This directly tests
    # geometry coverage and is not sensitive to duplicated FBX vertices or
    # sub-pixel drift when matching shared triangulation edges.
    row_intervals: list[list[tuple[int, int]]] = [[] for _ in range(height)]
    for polygon_uv in front_uv_polygons:
        u0, v0 = polygon_uv[:, 0], polygon_uv[:, 1]
        u1, v1 = np.roll(u0, -1), np.roll(v0, -1)
        first_row = max(0, int(math.ceil(float(v0.min()) * height - 0.5)))
        last_row = min(height - 1, int(math.floor(float(v0.max()) * height - 0.5)))
        for row in range(first_row, last_row + 1):
            v = (row + 0.5) / height
            crossing = ((v0 <= v) & (v < v1)) | ((v1 <= v) & (v < v0))
            if not np.any(crossing):
                continue
            intersections = u0[crossing] + (
                (v - v0[crossing]) * (u1[crossing] - u0[crossing]) /
                (v1[crossing] - v0[crossing])
            )
            intersections.sort()
            for pair in range(0, len(intersections) - 1, 2):
                first = max(0, int(math.ceil(intersections[pair] * width - 0.5)))
                last = min(width - 1, int(math.floor(intersections[pair + 1] * width - 0.5)))
                if last >= first:
                    row_intervals[row].append((first, last))

    covered_samples = []
    covered = 0
    for row, intervals in enumerate(row_intervals):
        if not intervals:
            continue
        intervals.sort()
        merged = []
        start, end = intervals[0]
        for next_start, next_end in intervals[1:]:
            if next_start <= end + 1:
                end = max(end, next_end)
            else:
                merged.append((start, end))
                start, end = next_start, next_end
        merged.append((start, end))
        for start, end in merged:
            covered_samples.append(rgba[row, start:end + 1])
            covered += end - start + 1
    samples = np.concatenate(covered_samples, axis=0) if covered_samples else np.empty((0, 4), dtype=np.float32)
    threshold_linear = 0.002
    is_alpha_masked = samples[:, 3] <= 0.5 if covered else np.zeros(0, dtype=bool)
    is_near_black = np.max(samples[:, :3], axis=1) <= threshold_linear if covered else np.zeros(0, dtype=bool)
    is_background = is_alpha_masked | is_near_black
    alpha_masked = int(np.count_nonzero(is_alpha_masked))
    near_black = int(np.count_nonzero(is_near_black))
    background = int(np.count_nonzero(is_background))
    fraction = background / max(covered, 1)
    return {
        "pass": bool(covered > 0 and fraction < 0.001),
        "skin_color": str(skin_color_path),
        "texture_size_px": [width, height],
        "front_texels": covered,
        "background_texels": background,
        "background_fraction": fraction,
        "background_percent": fraction * 100.0,
        "required_fraction_less_than": 0.001,
        "near_black_texels": near_black,
        "alpha_masked_texels": alpha_masked,
        "near_black_threshold_linear": threshold_linear,
        "rasterisation": "imported FBX Front polygons through UV0 directly onto SkinColor texel centres",
    }


def validate_vertex_contract(obj: bpy.types.Object, slots: list[str], require_all_timber_ids: bool) -> dict:
    layer = vertex_color_layer(obj)
    if layer is None:
        return {"pass": False, "reason": "no vertex-colour layer"}
    values = {name: [] for name in MATERIAL_SLOTS}
    for polygon in obj.data.polygons:
        slot = slots[polygon.material_index] if 0 <= polygon.material_index < len(slots) else None
        if slot not in values:
            continue
        for loop_index in polygon.loop_indices:
            values[slot].append(tuple(float(v) for v in layer.data[loop_index].color))
    flap_red = [value[0] for value in values["Flap"]]
    timber_red = [value[0] for value in values["Timber"]]
    timber_green = [value[1] for value in values["Timber"]]
    has_ids = True
    if require_all_timber_ids:
        has_ids = all(any(abs(value - target) <= 0.03 for value in timber_red) for target in (0.0, 0.5, 1.0))
    checks = {
        "layer": layer.name,
        "flap_range": [min(flap_red), max(flap_red)] if flap_red else None,
        "timber_red_range": [min(timber_red), max(timber_red)] if timber_red else None,
        "timber_green_range": [min(timber_green), max(timber_green)] if timber_green else None,
        "timber_ids_present": has_ids,
    }
    flap_ok = (not flap_red) or (min(flap_red) <= 0.02 and max(flap_red) >= 0.98)
    green_ok = bool(timber_green) and (max(timber_green) - min(timber_green) >= (0.20 if require_all_timber_ids else 0.0))
    checks["pass"] = bool(flap_ok and has_ids and green_ok)
    return checks


def validate_triangulated_export(*objects: bpy.types.Object | None) -> dict:
    present = [obj for obj in objects if obj is not None]
    enabled = bool(present) and all(bool(obj.get("TriangulatedExport", False)) for obj in present)
    if not enabled:
        return {"pass": True, "enabled": False, "contract": "legacy export; triangle-only gate not requested"}
    lods = {}
    passed = len(present) == len(objects)
    for obj in present:
        obj.data.calc_loop_triangles()
        arities: dict[str, int] = {}
        degenerate = []
        for polygon in obj.data.polygons:
            key = str(len(polygon.vertices))
            arities[key] = arities.get(key, 0) + 1
            if polygon.area <= 1.0e-12:
                degenerate.append(polygon.index)
        row_pass = bool(
            obj.data.polygons
            and all(len(polygon.vertices) == 3 for polygon in obj.data.polygons)
            and not degenerate
            and len(obj.data.polygons) == len(obj.data.loop_triangles)
        )
        passed = passed and row_pass
        lods[obj.name] = {
            "pass": row_pass,
            "polygon_arity": arities,
            "polygons": len(obj.data.polygons),
            "loop_triangles": len(obj.data.loop_triangles),
            "degenerate_polygon_indices": degenerate,
            "degenerate_area_threshold_m2": 1.0e-12,
        }
    return {
        "pass": bool(passed),
        "enabled": True,
        "quad_method": "FIXED",
        "ngon_method": "EAR_CLIP",
        "lods": lods,
    }


def fbx_node_name(value) -> str:
    if not isinstance(value, bytes):
        return str(value)
    return value.split(b"\x00\x01", 1)[0].decode("utf-8", errors="replace")


def inspect_fbx_lod_group(path: Path, flat_name: str) -> dict:
    """Inspect the binary FBX hierarchy without relying on Blender's scene import."""
    from io_scene_fbx import parse_fbx

    root, version = parse_fbx.parse(str(path))
    objects = next((elem for elem in root.elems if elem.id == b"Objects"), None)
    connections = next((elem for elem in root.elems if elem.id == b"Connections"), None)
    if objects is None or connections is None:
        return {"pass": False, "reason": "FBX is missing Objects or Connections", "fbx_version": version}

    models = {
        int(elem.props[0]): {
            "name": fbx_node_name(elem.props[1]),
            "type": fbx_node_name(elem.props[2]),
        }
        for elem in objects.elems
        if elem.id == b"Model" and len(elem.props) >= 3
    }
    lod_attributes = {
        int(elem.props[0]): {
            "name": fbx_node_name(elem.props[1]),
            "type": fbx_node_name(elem.props[2]),
        }
        for elem in objects.elems
        if elem.id == b"NodeAttribute" and len(elem.props) >= 3 and elem.props[2] == b"LodGroup"
    }
    oo_connections = [
        (int(elem.props[1]), int(elem.props[2]))
        for elem in connections.elems
        if elem.id == b"C" and len(elem.props) >= 3 and elem.props[0] == b"OO"
    ]
    group_model_ids = [dst for src, dst in oo_connections if src in lod_attributes and dst in models]
    expected_group = flat_name + "_LODGroup"
    expected_children = [flat_name + "_LOD0", flat_name + "_LOD1"]
    matching_group_ids = [group_id for group_id in group_model_ids if models[group_id]["name"] == expected_group]
    group_id = matching_group_ids[0] if len(matching_group_ids) == 1 else None
    child_ids = [src for src, dst in oo_connections if group_id is not None and dst == group_id and src in models]
    children = [models[child_id] for child_id in child_ids]
    child_names = [child["name"] for child in children]
    child_types = [child["type"] for child in children]
    passed = bool(
        len(lod_attributes) == 1
        and len(matching_group_ids) == 1
        and child_names == expected_children
        and child_types == ["Mesh", "Mesh"]
    )
    return {
        "pass": passed,
        "offline_tier": "MEASURED",
        "unreal_tier": "INFERRED until UE 5.8 Interchange read-back",
        "fbx_version": version,
        "mechanism": "FBX LodGroup NodeAttribute",
        "expected_group": expected_group,
        "lod_group_attributes": list(lod_attributes.values()),
        "group_model": models.get(group_id) if group_id is not None else None,
        "children_in_connection_order": children,
        "expected_children_in_order": expected_children,
    }


def validate(args: argparse.Namespace) -> None:
    clear_scene()
    path = Path(args.validate_fbx).resolve()
    bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
    result = {
        "schema_version": 1,
        "blender": bpy.app.version_string,
        "factory_startup_process": True,
        "fbx": str(path),
        "kind": args.kind,
        "checks": {},
    }
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    empties = [obj for obj in bpy.context.scene.objects if obj.type == "EMPTY"]
    if args.kind == "pole":
        candidates = [obj for obj in meshes if obj.name.startswith("SM_FlatV3_Pole")]
        pole = candidates[0] if candidates else (meshes[0] if meshes else None)
        if pole is None:
            raise RuntimeError("No pole mesh imported")
        lower, upper = transformed_bounds(pole)
        dims = upper - lower
        pole.data.calc_loop_triangles()
        slots = [slot.material.name if slot.material else None for slot in pole.material_slots]
        result["checks"] = {
            "name": {"pass": pole.name.startswith("SM_FlatV3_Pole"), "value": pole.name},
            "unit_height": {"pass": abs(float(dims[2]) - 1.0) <= 0.002, "measured_m": float(dims[2]), "expected_m": 1.0},
            "diameter": {"pass": 0.05 <= float(max(dims[0], dims[1])) <= 0.081, "measured_m": float(max(dims[0], dims[1])), "shaft_target_m": POLE_DIAMETER_M},
            "origin": {"pass": pole.location.length <= 0.001, "location_m": list(map(float, pole.location))},
            "uv0_uv1": {"pass": [uv.name for uv in pole.data.uv_layers] == ["UV0", "UV1"], "value": [uv.name for uv in pole.data.uv_layers]},
            "material_slots_exact": {"pass": slots == MATERIAL_SLOTS, "value": slots, "expected": MATERIAL_SLOTS},
            # Pole UV1 is authored by assign_metric_uvs(), the same
            # Interchange-precompensated metre mapping used when copies are
            # baked and joined into a flat. Validate the schema that is
            # actually authored instead of the obsolete unreflected box map.
            "uv1_metres_box_mapped": validate_metric_uv1(pole, slots, interchange_precompensated=True),
            "vertex_colours": validate_vertex_contract(pole, slots, False),
        }
        result["triangle_counts"] = {"pole": len(pole.data.loop_triangles)}
        result["dimensions_m"] = list(map(float, dims))
    else:
        if not args.skin_color:
            raise RuntimeError("Flat validation requires --skin-color for Front coverage")
        raw_lod_group = inspect_fbx_lod_group(path, path.stem)
        candidates = [obj for obj in meshes if obj.name.startswith("SM_FlatV3_") and not obj.name.startswith("SM_FlatV3_Pole")]
        lod0_candidates = [obj for obj in candidates if "_LOD0" in obj.name]
        lod1_candidates = [obj for obj in candidates if "_LOD1" in obj.name]
        flat = lod0_candidates[0] if lod0_candidates else (max(candidates, key=lambda obj: len(obj.data.polygons)) if candidates else None)
        lod1 = lod1_candidates[0] if lod1_candidates else None
        if flat is None:
            raise RuntimeError("No Flat V3 mesh imported")
        lower, upper = transformed_bounds(flat)
        dims = upper - lower
        expected_h = (args.expected_height_cm or 1000.0) / 100.0
        slots = [slot.material.name if slot.material else None for slot in flat.material_slots]
        uv_names = [uv.name for uv in flat.data.uv_layers]
        lod1_slots = [slot.material.name if slot.material else None for slot in lod1.material_slots] if lod1 else []
        lod1_uv_names = [uv.name for uv in lod1.data.uv_layers] if lod1 else []
        socket_objects = {obj.name: obj for obj in empties if obj.name.startswith("SOCKET_")}
        socket_names = sorted(socket_objects)
        is_wave_row = args.kind == "wave"
        baked_poles = bool(flat.get("BakedPoles", False))
        expected_pole_bottom_m = float(flat.get("PoleFootZM", -1.0 if baked_poles else 0.0))
        required_sockets = set() if is_wave_row else {"SOCKET_Pole_1", "SOCKET_Hinge", "SOCKET_Pivot"}
        sparse_single_pole = "single_stile_sparse_second_band" in str(flat.get("FrameStileSearchMode", ""))
        if not is_wave_row and float(dims[1]) > 4.0 and not sparse_single_pole:
            required_sockets.add("SOCKET_Pole_2")
        side = str(flat.get("Side", "L" if "_L_LOD0" in flat.name else "R"))
        direction_pass = ((abs(float(lower[1] + upper[1])) <= 0.01 and abs(float(lower[2])) <= 0.01)
                          if is_wave_row else
                           ((side == "L" and upper[1] <= 0.01 and lower[1] < -0.1) or
                            (side == "R" and lower[1] >= -0.01 and upper[1] > 0.1)))
        front_index = slots.index("Front") if "Front" in slots else -1
        normal_matrix = flat.matrix_world.to_3x3().inverted().transposed()
        front_normals = [normal_matrix @ polygon.normal for polygon in flat.data.polygons if polygon.material_index == front_index]
        front_negative = sum(normal.x < -0.9 for normal in front_normals)
        socket_contract_details = {}
        socket_contract_pass = required_sockets.issubset(socket_objects)
        for socket_name in sorted(required_sockets):
            socket = socket_objects.get(socket_name)
            if socket is None:
                socket_contract_details[socket_name] = {"pass": False, "reason": "missing"}
                continue
            location = socket.matrix_world.translation
            local_x_world = (socket.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
            if socket_name.startswith("SOCKET_Pole_"):
                contract_ok = abs(float(location.x)) <= 0.001 and abs(float(location.z)) <= 0.001
                expected_axis = "unconstrained"
            elif socket_name == "SOCKET_Hinge":
                contract_ok = abs(float(location.x)) <= 0.001 and abs(float(location.z)) <= 0.001 and abs(float(local_x_world.y)) >= 0.999
                expected_axis = "local +X along base-edge Y"
            else:
                contract_ok = abs(float(location.x)) <= 0.001 and float(local_x_world.z) >= 0.999
                expected_axis = "local +X upward +Z"
            socket_contract_pass = socket_contract_pass and contract_ok
            socket_contract_details[socket_name] = {
                "pass": bool(contract_ok),
                "location_m": list(map(float, location)),
                "local_x_world": list(map(float, local_x_world)),
                "expected_axis": expected_axis,
            }
        flat.data.calc_loop_triangles()
        if lod1:
            lod1.data.calc_loop_triangles()
        front_bounds = material_bounds(flat, slots, "Front")
        card_height = float(front_bounds[1][2] - front_bounds[0][2]) if front_bounds else 0.0
        baked_lod0_check = (validate_baked_poles(
            flat, slots, socket_objects, expected_h, expected_pole_bottom_m)
                            if baked_poles else {"pass": True, "enabled": False})
        baked_lod1_check = (validate_baked_poles(
            lod1, lod1_slots, socket_objects, expected_h, expected_pole_bottom_m)
                            if baked_poles and lod1 else {"pass": not baked_poles, "enabled": False})
        triangles_by_slot = {name: 0 for name in MATERIAL_SLOTS}
        for triangle in flat.data.loop_triangles:
            index = flat.data.polygons[triangle.polygon_index].material_index
            if 0 <= index < len(slots) and slots[index] in triangles_by_slot:
                triangles_by_slot[slots[index]] += 1
        result["checks"] = {
            "fbx_lod_group": raw_lod_group,
            "height": {"pass": abs(card_height - expected_h) <= 0.01, "measured_card_m": card_height, "expected_m": expected_h},
            "depth_about_12cm": ({"pass": 0.190 <= float(dims[0]) <= 0.210, "measured_m": float(dims[0]), "contract": "card plus baked pole collar"}
                                 if baked_poles else
                                 {"pass": 0.115 <= float(dims[0]) <= 0.130, "measured_m": float(dims[0]), "contract": "card only"}),
            "bounds_min_z": ({"pass": abs(float(lower[2]) - expected_pole_bottom_m) <= 0.002, "measured_m": float(lower[2]), "expected_m": expected_pole_bottom_m}
                             if baked_poles else
                             {"pass": abs(float(lower[2])) <= 0.01, "measured_m": float(lower[2]), "expected_m": 0.0}),
            "material_slots_exact": {"pass": slots == MATERIAL_SLOTS, "value": slots, "expected": MATERIAL_SLOTS},
            "uv0_uv1": {"pass": uv_names == ["UV0", "UV1"], "value": uv_names},
            "uv1_metres_all_slots": validate_metric_uv1(flat, slots),
            "front_flap_uv0_registration": validate_front_uv0(flat, slots),
            "front_flap_uv0_axis_contract": validate_uv0_axis_contract(flat, slots),
            "front_skincolor_background_coverage": validate_front_texture_coverage(flat, slots, Path(args.skin_color).resolve()),
            "vertex_colour_contract": validate_vertex_contract(flat, slots, True),
            "triangulated_export": validate_triangulated_export(flat, lod1),
            "lod1_present": {"pass": lod1 is not None, "value": lod1.name if lod1 else None},
            "lod1_slots_exact": {"pass": lod1 is not None and lod1_slots == MATERIAL_SLOTS, "value": lod1_slots, "expected": MATERIAL_SLOTS},
            "lod1_uv0_uv1": {"pass": lod1 is not None and lod1_uv_names == ["UV0", "UV1"], "value": lod1_uv_names},
            "lod1_uv1_metres_all_slots": validate_metric_uv1(lod1, lod1_slots) if lod1 else {"pass": False, "reason": "missing"},
            "lod1_vertex_colours": validate_vertex_contract(lod1, lod1_slots, False) if lod1 else {"pass": False, "reason": "missing"},
            "lod1_without_frame_hardware": {"pass": lod1 is not None and len(lod1.data.loop_triangles) < len(flat.data.loop_triangles) and ((baked_poles and "board plus baked poles" in str(lod1.get("LODContract", ""))) or (not baked_poles and "board only" in str(lod1.get("LODContract", "")))), "lod0_triangles": len(flat.data.loop_triangles), "lod1_triangles": len(lod1.data.loop_triangles) if lod1 else None, "contract": str(lod1.get("LODContract", "")) if lod1 else None},
            "baked_poles_lod0": baked_lod0_check,
            "baked_poles_lod1": baked_lod1_check,
            "socket_contract": ({"pass": not socket_names, "value": socket_names, "required": [], "contract": "no Pole/Hinge/Pivot sockets"}
                                if is_wave_row else
                                {"pass": bool(socket_contract_pass), "details": socket_contract_details}),
            "origin": {"pass": flat.location.length <= 0.001, "location_m": list(map(float, flat.location))},
            "front_faces_negative_x": {"pass": bool(front_normals) and front_negative == len(front_normals), "front_face_count": len(front_normals), "negative_x_count": front_negative},
            ("bottom_centre_origin" if is_wave_row else "side_extension"): {"pass": bool(direction_pass), "side": side, "y_bounds_m": [float(lower[1]), float(upper[1])], "z_min_m": float(lower[2])},
            "minimum_width": {"pass": float(dims[1]) + 0.001 >= float(args.minimum_width_m), "measured_m": float(dims[1]), "required_min_m": float(args.minimum_width_m)},
            "scale_one": {"pass": all(abs(float(value) - 1.0) <= 0.001 for value in flat.scale), "value": list(map(float, flat.scale))},
        }
        result["dimensions_m"] = list(map(float, dims))
        result["bounds_m"] = {"min": list(map(float, lower)), "max": list(map(float, upper))}
        result["triangle_counts_by_material"] = triangles_by_slot
        result["triangle_counts"] = {"lod0": len(flat.data.loop_triangles), "lod1": len(lod1.data.loop_triangles) if lod1 else None, "unexpected_meshes": sum(object_triangles(obj) for obj in meshes if obj not in (flat, lod1))}
    result["pass"] = all(bool(check.get("pass")) for check in result["checks"].values())
    out = Path(args.validation_out).resolve()
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("FLAT_V3_VALIDATION_" + ("PASS" if result["pass"] else "FAIL") + " " + json.dumps(result["checks"]), flush=True)
    if not result["pass"]:
        raise RuntimeError(f"FBX validation failed: {out}")


def main() -> None:
    require_blender_44()
    args = blender_args()
    if args.validate_fbx:
        if not args.kind or not args.validation_out:
            raise RuntimeError("Validation mode requires --kind and --validation-out")
        validate(args)
    else:
        build(args)


if __name__ == "__main__":
    main()
