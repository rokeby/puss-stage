"""Offline replica of Slot W's post-import structural gates for S3 wave FBXs.

Run with Blender 4.4 in background/factory-startup mode.  The negative root is
expected to fail the LOD1 Timber vertex-colour rule; the positive root must pass
every existing per-asset validation plus the replicated LOD/slot/UV/colour gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from io_scene_fbx.parse_fbx import parse


ASSETS = tuple(f"S3_WaveRow{row}_{half}" for row in (1, 2, 3) for half in ("A", "B"))
SLOTS = ["Front", "Flap", "Timber", "Edge"]
PIXEL_FILES = (
    "stage1_colour_key_art.png",
    "stage2_jigsaw_mask.png",
    "stage4_RealESRGAN_2x_art.png",
    "stage4_RealESRGAN_2x_jigsaw_mask.png",
)


def args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-root", required=True)
    parser.add_argument("--positive-root", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(raw)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def child(element, name: bytes):
    return next((item for item in element.elems if item.id == name), None)


def text_prop(element, default=None):
    if element is None or not element.props:
        return default
    value = element.props[0]
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value


def raw_colour_by_slot(path: Path) -> dict[str, dict[str, list[tuple[float, ...]]]]:
    root, _version = parse(str(path))
    objects = child(root, b"Objects")
    result = {}
    for geometry in objects.elems if objects else []:
        if geometry.id != b"Geometry" or len(geometry.props) < 3 or geometry.props[2] != b"Mesh":
            continue
        name = geometry.props[1].decode("utf-8", "replace").split("\x00", 1)[0]
        lod = "LOD0" if "_LOD0_" in name else "LOD1" if "_LOD1_" in name else None
        if lod is None:
            continue
        colour_layer = child(geometry, b"LayerElementColor")
        material_layer = child(geometry, b"LayerElementMaterial")
        polygon_vertices = child(geometry, b"PolygonVertexIndex")
        if colour_layer is None or material_layer is None or polygon_vertices is None:
            raise RuntimeError(f"FBX attribute layer missing in {path}: {name}")
        if (text_prop(child(colour_layer, b"MappingInformationType")) != "ByPolygonVertex" or
                text_prop(child(colour_layer, b"ReferenceInformationType")) != "IndexToDirect"):
            raise RuntimeError(f"Unsupported FBX colour mapping in {path}: {name}")
        colors_element = child(colour_layer, b"Colors")
        indices_element = child(colour_layer, b"ColorIndex")
        materials_element = child(material_layer, b"Materials")
        direct_flat = list(colors_element.props[0])
        direct = [tuple(float(channel) for channel in direct_flat[index:index + 4])
                  for index in range(0, len(direct_flat), 4)]
        colour_indices = list(indices_element.props[0])
        material_indices = list(materials_element.props[0])
        polygon_ends = [index for index, value in enumerate(polygon_vertices.props[0]) if int(value) < 0]
        if len(polygon_ends) != len(material_indices) or len(colour_indices) != len(polygon_vertices.props[0]):
            raise RuntimeError(f"FBX polygon attribute cardinality mismatch in {path}: {name}")
        by_slot = {slot: [] for slot in SLOTS}
        start = 0
        for polygon_index, end in enumerate(polygon_ends):
            material_index = int(material_indices[polygon_index])
            if material_index < 0 or material_index >= len(SLOTS):
                raise RuntimeError(f"FBX material index out of range in {path}: {material_index}")
            by_slot[SLOTS[material_index]].extend(
                direct[int(colour_indices[corner])] for corner in range(start, end + 1)
            )
            start = end + 1
        result[lod] = by_slot
    if set(result) != {"LOD0", "LOD1"}:
        raise RuntimeError(f"Expected raw LOD0/LOD1 geometries in {path}; got {sorted(result)}")
    return result


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.images):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def slope(xs: list[float], ys: list[float]) -> float:
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator <= 1.0e-12:
        raise RuntimeError("Degenerate regression input")
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def imported_gates(path: Path) -> dict:
    clear_scene()
    bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    lods = {}
    for obj in meshes:
        key = "LOD0" if "_LOD0" in obj.name else "LOD1" if "_LOD1" in obj.name else None
        if key is not None:
            if key in lods:
                raise RuntimeError(f"Duplicate {key} mesh in {path}")
            lods[key] = obj
    checks = {
        "lods": {"pass": set(lods) == {"LOD0", "LOD1"} and len(meshes) == 2,
                 "mesh_names": sorted(obj.name for obj in meshes)},
    }
    for lod_name, obj in sorted(lods.items()):
        slots = [slot.material.name if slot.material else None for slot in obj.material_slots]
        uv_layers = [layer.name for layer in obj.data.uv_layers]
        front_index = slots.index("Front") if "Front" in slots else -1
        ys, zs, us, vs = [], [], [], []
        normals = []
        uv0 = obj.data.uv_layers.get("UV0")
        if uv0 is not None and front_index >= 0:
            for polygon in obj.data.polygons:
                if polygon.material_index != front_index:
                    continue
                normals.append(tuple(float(value) for value in polygon.normal))
                for loop_index in polygon.loop_indices:
                    vertex = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
                    uv = uv0.data[loop_index].uv
                    ys.append(float(vertex.y))
                    zs.append(float(vertex.z))
                    us.append(float(uv.x))
                    vs.append(float(uv.y))
        du_dy = slope(ys, us) if ys else math.nan
        dv_dz = slope(zs, vs) if zs else math.nan
        raw_uv_pass = bool(du_dy < 0.0 and dv_dz > 0.0)
        checks[lod_name] = {
            "slots": {"pass": slots == SLOTS, "value": slots, "expected": SLOTS},
            "uv_layers": {"pass": uv_layers == ["UV0", "UV1"], "value": uv_layers},
            "front_uv_signs": {
                "pass": raw_uv_pass,
                "raw_blender_fbx": {"du_dY": du_dy, "dv_dZ": dv_dz,
                                    "expected": "du/dY < 0; dv/dZ > 0"},
                "replicated_unreal_interchange": {"du_dY": -du_dy, "dv_dZ": -dv_dz,
                                                   "expected": "du/dY > 0; dv/dZ < 0"},
            },
            "front_direction": {
                "pass": bool(normals) and all(value[0] < -0.99 and abs(value[1]) < 0.02 and abs(value[2]) < 0.02
                                              for value in normals),
                "polygon_count": len(normals),
            },
            "uv0_range": {
                "pass": bool(us) and min(us) >= -0.001 and max(us) <= 1.001 and min(vs) >= -0.001 and max(vs) <= 1.001,
                "u": [min(us), max(us)] if us else None,
                "v": [min(vs), max(vs)] if vs else None,
            },
        }
    checks["lods"]["pass"] = bool(checks["lods"]["pass"] and
                                     all(check.get("pass", False) for key, group in checks.items()
                                         if key != "lods" for check in group.values()))
    return checks


def colour_gates(path: Path) -> dict:
    raw = raw_colour_by_slot(path)
    result = {}
    for lod in ("LOD0", "LOD1"):
        by_slot = raw[lod]
        summaries = {}
        for slot, values in by_slot.items():
            summaries[slot] = {
                "corners": len(values),
                "r_range": [min(value[0] for value in values), max(value[0] for value in values)] if values else None,
                "g_range": [min(value[1] for value in values), max(value[1] for value in values)] if values else None,
            }
        timber = summaries["Timber"]
        flap = summaries["Flap"]
        if lod == "LOD0":
            passed = bool(
                flap["r_range"] is not None and flap["r_range"][0] <= 0.01 and flap["r_range"][1] >= 0.99 and
                timber["r_range"] is not None and timber["r_range"][0] <= 0.01 and timber["r_range"][1] >= 0.99 and
                timber["g_range"][1] - timber["g_range"][0] >= 0.1
            )
        else:
            passed = bool(
                flap["corners"] == 0 and timber["r_range"] is not None and
                timber["r_range"][0] >= 0.49 and timber["r_range"][1] <= 0.51
            )
        result[lod] = {"pass": passed, "slots": summaries}
    result["pass"] = all(result[lod]["pass"] for lod in ("LOD0", "LOD1"))
    return result


def validate_root(root: Path) -> dict:
    assets = {}
    for asset in ASSETS:
        folder = root / asset
        fbx = folder / f"SM_FlatV3_{asset}.fbx"
        validation = json.loads((folder / "validation.json").read_text(encoding="utf-8"))
        existing_failed = sorted(name for name, value in validation["checks"].items() if not value.get("pass"))
        imported = imported_gates(fbx)
        colours = colour_gates(fbx)
        passed = bool(not existing_failed and imported["lods"]["pass"] and colours["pass"])
        assets[asset] = {
            "pass": passed,
            "fbx": str(fbx),
            "existing_offline_validation_failed_gates": existing_failed,
            "replicated_post_import_structure": imported,
            "replicated_post_import_vertex_colours": colours,
        }
    return {"root": str(root), "pass": all(value["pass"] for value in assets.values()), "assets": assets}


def main() -> None:
    if not bpy.app.background or bpy.app.version[:2] != (4, 4):
        raise RuntimeError(f"Blender 4.4 background mode required; got {bpy.app.version_string}")
    parsed = args()
    negative_root = Path(parsed.negative_root).resolve()
    positive_root = Path(parsed.positive_root).resolve()
    negative = validate_root(negative_root)
    positive = validate_root(positive_root)
    pixel_identity = {}
    for asset in ASSETS:
        rows = {}
        for name in PIXEL_FILES:
            before = negative_root / asset / name
            after = positive_root / asset / name
            rows[name] = {
                "negative_sha256": sha256(before),
                "positive_sha256": sha256(after),
                "pass": sha256(before) == sha256(after),
            }
        pixel_identity[asset] = {"pass": all(value["pass"] for value in rows.values()), "files": rows}
    result = {
        "schema_version": 1,
        "proof_tier": "measured",
        "blender": bpy.app.version_string,
        "headless": bpy.app.background,
        "offline_only": True,
        "unreal_mcp_or_port_8010_used": False,
        "negative": negative,
        "positive": positive,
        "extension_pixels_identical": {
            "pass": all(value["pass"] for value in pixel_identity.values()),
            "assets": pixel_identity,
        },
    }
    result["pass"] = bool(not negative["pass"] and positive["pass"] and result["extension_pixels_identical"]["pass"])
    output = Path(parsed.output).resolve()
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("FLATV3_W_OFFLINE_REPLICA_" + ("PASS" if result["pass"] else "FAIL") + f" {output}")
    if not result["pass"]:
        raise RuntimeError(f"Offline W gate replica failed: {output}")


if __name__ == "__main__":
    main()
