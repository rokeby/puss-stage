"""Guarded P02 industrial retexture scaffold. Import/create and mesh-slot writes only."""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import struct

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py")); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


D = _load("q3_defaults")


class ToolError(RuntimeError): pass


def require(value, message):
    if not value: raise ToolError(str(message))


def _json(path, value=None, exclusive=False):
    if value is None:
        with open(path, encoding="utf-8") as handle: return json.load(handle)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True); handle.flush(); os.fsync(handle.fileno())


def _jpeg_size(path):
    with open(path, "rb") as handle:
        if handle.read(2) != b"\xff\xd8": raise ToolError("NOT_JPEG|" + path)
        while True:
            marker = handle.read(1)
            while marker == b"\xff": marker = handle.read(1)
            if not marker: raise ToolError("JPEG_SIZE|" + path)
            length = struct.unpack(">H", handle.read(2))[0]
            if marker[0] in range(0xC0, 0xC4):
                data = handle.read(5); return struct.unpack(">HH", data[1:5])[::-1]
            handle.seek(length - 2, 1)


def source_plan(args):
    rows = []
    for key, spec in D.P02_PROFILES.items():
        for map_name in ("Color", "NormalDX", "Roughness", "AO"):
            path = os.path.join(args["source_root"], spec["folder"], spec["prefix"] + "_" + map_name + ".jpg")
            require(os.path.isfile(path), "SOURCE_MISSING|" + path)
            size = _jpeg_size(path); require(size[0] == size[1] and size[0] >= 2048 and size[0] & (size[0] - 1) == 0, "SOURCE_NOT_POT_2K|%s|%s" % (path, size))
            asset = "%s/%s_%s" % (args["texture_root"], key.title(), map_name)
            rows.append({"profile": key, "map": map_name, "source": path.replace("\\", "/"), "pixels": list(size), "asset": asset})
    return rows


def _asset_id(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj else None


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(_asset_id(x) for x in lib.get_dirty_content_packages()), "maps": sorted(_asset_id(x) for x in lib.get_dirty_map_packages())}


def _package_file(asset):
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), asset[6:].replace("/", os.sep)) + ".uasset"


def _backup(run, assets):
    root = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Backups", "PreP02IndustrialRetexture-" + run)
    os.makedirs(root, exist_ok=False); rows = []
    for asset in assets:
        src = _package_file(asset); require(os.path.isfile(src), "BACKUP_SOURCE|" + src)
        dst = os.path.join(root, asset[6:].replace("/", os.sep) + ".uasset"); os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst)
        digest = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
        require(digest(src) == digest(dst), "BACKUP_HASH|" + asset); rows.append({"asset": asset, "source": src, "backup": dst, "sha256": digest(src)})
    _json(os.path.join(root, "prechange.json"), {"run": run, "files": rows}, exclusive=True)
    return root


def _slot_rows(mesh):
    return [{"slot": str(x.get_editor_property("material_slot_name")), "material": _asset_id(x.get_editor_property("material_interface"))} for x in mesh.get_editor_property("static_materials")]


def dry(args):
    rows = source_plan(args); require(unreal is not None, "UNREAL_REQUIRED_FOR_ASSET_AUDIT")
    require(_census() == {"content": [], "maps": []}, "DIRTY_CENSUS|" + json.dumps(_census(), sort_keys=True))
    require(unreal.EditorAssetLibrary.does_asset_exist(args["master"]), "INDUSTRIAL_MASTER_MISSING|" + args["master"])
    if args["edge_winding_audit"] == "outward": require(unreal.EditorAssetLibrary.does_asset_exist(args["edge_v3"]), "EDGE_V3_MISSING|" + args["edge_v3"])
    result = {"mode": "DRY", "run": "P02IND-DRY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), "marker": "P02IND_DRY_OK", "sources": rows, "targets": [], "edge_note": "REBUILD_OUTWARD_EDGE_WALLS_BEFORE_EDGE_V3" if args["edge_winding_audit"] != "outward" else "EDGE_V3_ALLOWED"}
    for target in D.P02_TARGETS:
        mesh = unreal.load_asset(target["mesh"]); require(mesh is not None, "MESH_MISSING|" + target["mesh"])
        result["targets"].append({"mesh": target["mesh"], "before": _slot_rows(mesh), "after_profiles": target["slots"]})
    return result


def _import_texture(row):
    require(not unreal.EditorAssetLibrary.does_asset_exist(row["asset"]), "CREATE_ONLY_EXISTS|" + row["asset"])
    task = unreal.AssetImportTask(); task.set_editor_property("filename", row["source"]); task.set_editor_property("destination_path", row["asset"].rsplit("/", 1)[0]); task.set_editor_property("destination_name", row["asset"].rsplit("/", 1)[1]); task.set_editor_property("automated", True); task.set_editor_property("replace_existing", False); task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task]); tex = unreal.load_asset(row["asset"]); require(tex is not None, "IMPORT_FAILED|" + row["asset"])
    tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
    tex.set_editor_property("srgb", row["map"] == "Color")
    compression = (unreal.TextureCompressionSettings.TC_NORMALMAP if row["map"] == "NormalDX" else
                   unreal.TextureCompressionSettings.TC_GRAYSCALE if row["map"] in ("Roughness", "AO") else
                   unreal.TextureCompressionSettings.TC_DEFAULT)
    tex.set_editor_property("compression_settings", compression)
    return tex


def _make_mi(args, profile, textures):
    path = "%s/MI_P02_IND_%s" % (args["mi_root"], profile.title()); require(not unreal.EditorAssetLibrary.does_asset_exist(path), "CREATE_ONLY_EXISTS|" + path)
    factory = unreal.MaterialInstanceConstantFactoryNew(); mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(path.rsplit("/", 1)[1], path.rsplit("/", 1)[0], unreal.MaterialInstanceConstant, factory); require(mi is not None, "MI_CREATE|" + path)
    mi.set_editor_property("parent", unreal.load_asset(args["master"])); lib = unreal.MaterialEditingLibrary
    for map_name, parameter in (("Color", "BaseColorTexture"), ("NormalDX", "NormalTexture"), ("Roughness", "RoughnessTexture"), ("AO", "AOTexture")):
        require(lib.set_material_instance_texture_parameter_value(mi, parameter, textures[(profile, map_name)]), "MI_PARAM|%s|%s" % (path, parameter))
    spans = args["tile_size_cm"][profile]
    require(lib.set_material_instance_scalar_parameter_value(mi, "TileSizeCmU", float(spans[0])), "MI_TILE_U|" + path)
    require(lib.set_material_instance_scalar_parameter_value(mi, "TileSizeCmV", float(spans[1])), "MI_TILE_V|" + path)
    return mi


def apply(args):
    plan = dry(args); run = "P02IND-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"); record_path = os.path.join(HERE, "p02_industrial_record.json")
    require(not os.path.exists(record_path), "ACTIVE_RECORD_EXISTS|" + record_path)
    backup = _backup(run, [x["mesh"] for x in D.P02_TARGETS])
    record = {"run": run, "args": args, "backup": backup, "targets": plan["targets"], "created": []}; _json(record_path, record, exclusive=True)
    textures = {}
    for row in plan["sources"]:
        textures[(row["profile"], row["map"])] = _import_texture(row); record["created"].append(row["asset"]); _json(record_path, record)
    mis = {}
    for profile in D.P02_PROFILES:
        mis[profile] = _make_mi(args, profile, textures); record["created"].append(_asset_id(mis[profile])); _json(record_path, record)
    edge = unreal.load_asset(args["edge_v3"]) if args["edge_winding_audit"] == "outward" else None
    for target in D.P02_TARGETS:
        mesh = unreal.load_asset(target["mesh"]); mats = list(mesh.get_editor_property("static_materials"))
        for item in mats:
            slot = str(item.get_editor_property("material_slot_name")); profile = target["slots"].get(slot)
            if profile and profile != "EDGE_REBUILD_REQUIRED": item.set_editor_property("material_interface", edge if profile == "EDGE_V3" else mis[profile])
        mesh.set_editor_property("static_materials", mats)
    expected = sorted(record["created"] + [x["mesh"] for x in D.P02_TARGETS]); got = _census(); require(set(got["content"]) <= set(expected) and not got["maps"], "DIRTY_SCOPE|" + json.dumps(got))
    for asset in expected: require(unreal.EditorAssetLibrary.save_asset(asset, only_if_is_dirty=False), "SAVE|" + asset)
    require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY")
    after = [{"mesh": t["mesh"], "slots": _slot_rows(unreal.load_asset(t["mesh"]))} for t in D.P02_TARGETS]
    report = {"mode": "APPLY", "run": run, "backup": backup, "created": record["created"], "readback": after, "edge_note": plan["edge_note"], "census_after": _census(), "marker": "P02IND_APPLY_OK"}; _json(os.path.join(HERE, "p02_industrial_report.json"), report); unreal.log("P02IND_APPLY_OK|run=" + run); return report


def revert(args):
    require(unreal is not None, "UNREAL_REQUIRED"); require(_census() == {"content": [], "maps": []}, "DIRTY_CENSUS")
    path = os.path.join(HERE, "p02_industrial_record.json"); require(os.path.isfile(path), "NO_ACTIVE_RECORD"); record = _json(path); run = "P02IND-REVERT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"); _backup(run, [x["mesh"] for x in D.P02_TARGETS])
    for target in record["targets"]:
        mesh = unreal.load_asset(target["mesh"]); by_slot = {x["slot"]: x["material"] for x in target["before"]}; mats = list(mesh.get_editor_property("static_materials"))
        for item in mats:
            slot = str(item.get_editor_property("material_slot_name")); require(slot in by_slot, "SLOT_DRIFT|" + slot); item.set_editor_property("material_interface", unreal.load_asset(by_slot[slot]))
        mesh.set_editor_property("static_materials", mats); require(unreal.EditorAssetLibrary.save_asset(target["mesh"], only_if_is_dirty=False), "SAVE_REVERT")
    # Created assets are intentionally retained: project policy forbids permanent deletion without a new explicit request.
    archived = path + ".reverted-" + run; os.replace(path, archived); report = {"mode": "REVERT", "run": run, "created_assets_retained": record["created"], "record": archived, "census_after": _census(), "marker": "P02IND_REVERT_OK"}; _json(os.path.join(HERE, "p02_industrial_revert_report.json"), report); unreal.log("P02IND_REVERT_OK|run=" + run); return report


def main():
    args = D.validate_p02(_json(os.path.join(HERE, "p02_industrial_args.json")))
    result = dry(args) if args["mode"] == "DRY" else apply(args) if args["mode"] == "APPLY" else revert(args)
    if unreal is not None: unreal.log("%s|run=%s" % (result["marker"], result["run"]))
    print(json.dumps(result, indent=2, sort_keys=True)); return result


if __name__ == "__main__": main()
