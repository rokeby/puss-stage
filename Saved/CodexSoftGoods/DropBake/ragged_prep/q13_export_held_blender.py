"""Blender-side Q13 exporter. Invoked once by q13_ragged_ease_to_hold.py APPLY."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-abc", type=Path, required=True)
    parser.add_argument("--held-stream", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--output-abc", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--fps", type=int, required=True)
    parser.add_argument("--landing", type=int, required=True)
    parser.add_argument("--hold", type=int, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def mesh_signature(obj):
    mesh = obj.data
    return {
        "object_name": obj.name,
        "mesh_name": mesh.name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "uv_layers": [layer.name for layer in mesh.uv_layers],
        "attributes": [{"name": a.name, "domain": a.domain, "data_type": a.data_type}
                       for a in mesh.attributes],
        "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
    }


def coords(obj):
    out = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get("co", out)
    return out.reshape((-1, 3))


def evaluated_coords(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        out = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", out)
        m = np.array(evaluated.matrix_world, dtype=np.float64)
        return (out.reshape((-1, 3)).astype(np.float64) @ m[:3, :3].T + m[:3, 3]).astype(np.float32)
    finally:
        evaluated.to_mesh_clear()


def set_coords(obj, values):
    # The stream is WORLD space (the bake lifts the object by LIFT_M = 0.2 m and the ABC carries that xform);
    # write object-local coordinates so the exported xform + mesh reproduce the stream.
    m = np.array(obj.matrix_world.inverted(), dtype=np.float64)
    local = np.asarray(values, dtype=np.float64) @ m[:3, :3].T + m[:3, 3]
    obj.data.vertices.foreach_set("co", local.astype(np.float32).reshape(-1))
    obj.data.update()


def remove_object(obj):
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def import_single(path: Path):
    bpy.ops.wm.alembic_import(filepath=str(path), as_background_job=False)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one mesh in {path}, found {len(meshes)}")
    return meshes[0]


def main():
    args = arguments()
    sidecar = json.loads(args.sidecar.read_text(encoding="utf-8"))
    nverts = int(sidecar["vertices"])
    first = int(sidecar.get("first_frame", 1))
    frames = args.end - first + 1
    expected = frames * nverts * 3 * 4
    if args.held_stream.stat().st_size != expected:
        raise RuntimeError(f"Held stream size mismatch: expected {expected}, got {args.held_stream.stat().st_size}")
    stream = np.memmap(args.held_stream, dtype=np.float32, mode="r", shape=(frames, nverts, 3))
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = args.start, args.end
    scene.frame_set(args.start)
    # --factory-startup contains Cube/Camera/Light. They are not part of the source
    # Alembic and must not contaminate the imported-object census.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    source = import_single(args.source_abc)
    source_sig = mesh_signature(source)
    if source_sig["vertices"] != nverts:
        raise RuntimeError(f"Original ABC has {source_sig['vertices']} vertices, stream has {nverts}")
    original_eval = evaluated_coords(source)
    original_delta = float(np.max(np.linalg.norm(original_eval - stream[args.start-first], axis=1)))
    if original_delta > 1e-4:
        raise RuntimeError(f"Original ABC/stream vertex ordering mismatch: max delta {original_delta}")
    for modifier in list(source.modifiers):
        source.modifiers.remove(modifier)
    set_coords(source, stream[args.start-first])
    # Without modifiers the Alembic writer treats the mesh as constant and writes ONE sample (read-back was
    # 11 m off after frame 450). Animation data on the mesh datablock marks it animated, so every frame is sampled.
    source.data["q13_animated"] = 0.0
    source.data.keyframe_insert('["q13_animated"]', frame=args.start)
    source.data["q13_animated"] = 1.0
    source.data.keyframe_insert('["q13_animated"]', frame=args.end)

    def update(_scene, _depsgraph=None):
        frame = min(args.end, max(first, _scene.frame_current))
        set_coords(source, stream[frame-first])

    bpy.app.handlers.frame_change_pre.clear()
    bpy.app.handlers.frame_change_pre.append(update)
    bpy.ops.object.select_all(action="DESELECT")
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    args.output_abc.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.alembic_export(filepath=str(args.output_abc), start=args.start, end=args.end,
                              selected=True, uvs=True, normals=True, face_sets=True,
                              apply_subdiv=False, evaluation_mode="VIEWPORT")
    bpy.app.handlers.frame_change_pre.clear()
    remove_object(source)

    scene.frame_set(args.start)
    check = import_single(args.output_abc)
    output_sig = mesh_signature(check)
    errors = {}
    for frame in (args.start, args.landing, args.landing + 30, args.end):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        actual = evaluated_coords(check)
        errors[str(frame)] = float(np.max(np.linalg.norm(actual - stream[frame-first], axis=1)))
    if source_sig["object_name"] != output_sig["object_name"] or source_sig["mesh_name"] != output_sig["mesh_name"]:
        raise RuntimeError(f"Name mismatch: {source_sig} -> {output_sig}")
    if source_sig["uv_layers"] != output_sig["uv_layers"]:
        raise RuntimeError(f"UV layer mismatch: {source_sig['uv_layers']} -> {output_sig['uv_layers']}")
    if max(errors.values()) > 1e-4:
        raise RuntimeError(f"Export read-back mismatch: {errors}")
    report = {
        "schema": "pussstage.q13_blender_export.v1",
        "blender_version": bpy.app.version_string,
        "factory_startup": True,
        "process_contract": "single Blender process imported source, exported held cache, and read it back; no rendering",
        "rendering_performed": False,
        "source_signature": source_sig,
        "output_signature": output_sig,
        "source_stream_max_error_m_at_450": original_delta,
        "readback_max_error_m": errors,
        "frame_range": [args.start, args.end],
        "fps": args.fps,
        "success_marker": "Q13_BLENDER_EXPORT_READBACK_OK",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Q13_BLENDER_EXPORT_READBACK_OK")


if __name__ == "__main__":
    main()
