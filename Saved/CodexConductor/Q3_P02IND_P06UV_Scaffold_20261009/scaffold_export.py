"""Dormant Blender headless exporter for the baked P06 scaffold source. Do not run in this scaffold task."""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _defaults():
    spec = importlib.util.spec_from_file_location("q3_defaults", os.path.join(HERE, "q3_defaults.py")); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def _args(argv):
    parser = argparse.ArgumentParser(); parser.add_argument("--mode", default="DRY"); parser.add_argument("--confirm", default=""); parser.add_argument("--allow-permanent-asset-delete", action="store_true")
    raw = vars(parser.parse_args(argv)); raw["allow_permanent_asset_delete"] = raw.pop("allow_permanent_asset_delete")
    return _defaults().validate_export(raw)


def _require(value, message):
    if not value: raise RuntimeError(message)


def _paths(cfg):
    return [os.path.join(cfg["output_dir"], "SM_FlatV3_P06_Scaffold_%dBay.fbx" % n) for n in cfg["variants"]]


def _baked_maps(cfg):
    root = os.path.join(os.path.dirname(cfg["blend"]), "ScaffoldBake")
    return [os.path.join(root, "T_Scaffold_%s.png" % name) for name in ("BaseColor", "Normal", "Roughness", "NetOpacity")]


def dry(cfg, bpy):
    _require(bpy.app.background, "BACKGROUND_MODE_REQUIRED")
    _require(os.path.normcase(os.path.abspath(bpy.data.filepath)) == os.path.normcase(os.path.abspath(cfg["blend"])), "WRONG_BLEND")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    _require(meshes, "NO_MESH_OBJECTS")
    return {"mode": "DRY", "run": "P06SCAFFOLDEXPORT-DRY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), "marker": "P06SCAFFOLDEXPORT_DRY_OK", "blend": cfg["blend"], "mesh_objects": len(meshes), "baked_maps": [{"path": p, "exists": os.path.isfile(p)} for p in _baked_maps(cfg)],
            "outputs": _paths(cfg), "frame": {"front": "-X", "width": "+Y", "up": "+Z", "origin": "floor centre"},
            "material_slots": {"Front": "aged steel + housings", "Flap": "baked dark gauze", "Timber": "boards", "Edge": "bulb emissive"},
            "lights_excluded": True, "lod1_distance_cm": cfg["lod1_distance_cm"]}


def _variant_objects(bpy, bays, cfg):
    half = bays * cfg["bay_width_cm"] * 0.5 + 1.0
    selected = []
    for source in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        # Source is a centred three-bay assembly; retain members whose world-Y origin is inside the requested width.
        if abs(float(source.matrix_world.translation.y)) <= half:
            dup = source.copy(); dup.data = source.data.copy(); bpy.context.collection.objects.link(dup); selected.append(dup)
    _require(selected, "VARIANT_EMPTY|%d" % bays)
    return selected


def _canonicalize_materials(bpy, objects):
    canonical = {name: bpy.data.materials.get(name) or bpy.data.materials.new(name) for name in ("Front", "Flap", "Timber", "Edge")}
    for obj in objects:
        for slot in obj.material_slots:
            source = (slot.material.name if slot.material else "").lower()
            if "net" in source and "hem" not in source: target = "Flap"
            elif "timber" in source or "toe" in source: target = "Timber"
            elif "bulb" in source or "emiss" in source: target = "Edge"
            else: target = "Front"
            slot.material = canonical[target]


def _export_variant(bpy, bays, cfg, output):
    selected = _variant_objects(bpy, bays, cfg)
    _canonicalize_materials(bpy, selected)
    for o in bpy.context.selected_objects: o.select_set(False)
    for o in selected: o.select_set(True)
    bpy.context.view_layer.objects.active = selected[0]
    # Exported source already carries the four baked-material assignments. LOD1 is produced as a separate decimated duplicate.
    bpy.ops.object.duplicate(); lod1 = list(bpy.context.selected_objects)
    for o in lod1:
        o.name = "SM_FlatV3_P06_Scaffold_%dBay_LOD1_%s" % (bays, o.name)
        mod = o.modifiers.new("LOD1_Decimate", "DECIMATE"); mod.ratio = 0.35
    all_export = selected + lod1
    for o in bpy.context.selected_objects: o.select_set(False)
    for o in all_export: o.select_set(True)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=output, use_selection=True, axis_forward="-X", axis_up="Z", apply_unit_scale=True, bake_space_transform=False, add_leaf_bones=False, use_mesh_modifiers=True, mesh_smooth_type="FACE", path_mode="COPY", embed_textures=False)
    return {"bay_count": bays, "width_cm": bays * cfg["bay_width_cm"], "fbx": output, "bytes": os.path.getsize(output), "lod0_objects": len(selected), "lod1_objects": len(lod1)}


def apply(cfg, bpy):
    plan = dry(cfg, bpy); missing = [x["path"] for x in plan["baked_maps"] if not x["exists"]]; _require(not missing, "RUN_HEADLESS_BAKE_FIRST|" + json.dumps(missing))
    for path in _paths(cfg): _require(not os.path.exists(path), "CREATE_ONLY_OUTPUT_EXISTS|" + path)
    run = "P06SCAFFOLDEXPORT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    record = os.path.join(HERE, "scaffold_export_record.json"); _require(not os.path.exists(record), "ACTIVE_RECORD_EXISTS")
    with open(record, "x", encoding="utf-8") as handle: json.dump({"run": run, "args": cfg, "planned_outputs": _paths(cfg)}, handle, indent=2)
    rows = [_export_variant(bpy, bays, cfg, output) for bays, output in zip(cfg["variants"], _paths(cfg))]
    report = {"mode": "APPLY", "run": run, "exports": rows, "source_blend_saved": False, "marker": "P06SCAFFOLDEXPORT_APPLY_OK"}
    with open(os.path.join(HERE, "scaffold_export_report.json"), "w", encoding="utf-8") as handle: json.dump(report, handle, indent=2)
    print(report["marker"] + "|run=" + run); return report


def revert(cfg, _bpy):
    record = os.path.join(HERE, "scaffold_export_record.json"); _require(os.path.isfile(record), "NO_ACTIVE_RECORD")
    run = "P06SCAFFOLDEXPORT-REVERT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    retired = os.path.join(os.path.dirname(cfg["blend"]), "Backups", "PreP06ScaffoldExportRevert-" + run, "retired_outputs"); os.makedirs(retired, exist_ok=False); moved = []
    for path in _paths(cfg):
        if os.path.isfile(path):
            dest = os.path.join(retired, os.path.basename(path)); shutil.move(path, dest); moved.append(dest)
    archived = record + ".reverted-" + run; os.replace(record, archived)
    result = {"mode": "REVERT", "run": run, "recoverable_outputs": moved, "record": archived, "marker": "P06SCAFFOLDEXPORT_REVERT_OK"}; print(result["marker"] + "|run=" + run); return result


def main(argv=None):
    argv = argv if argv is not None else (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    cfg = _args(argv); import bpy  # type: ignore
    result = dry(cfg, bpy) if cfg["mode"] == "DRY" else apply(cfg, bpy) if cfg["mode"] == "APPLY" else revert(cfg, bpy)
    print("%s|run=%s" % (result["marker"], result["run"])); return result


if __name__ == "__main__": main()
