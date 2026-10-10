"""Guarded UE 5.8 import/material tool for Job 131; authored offline.

One IMPORT execution accepts exactly one selector. Interchange pipeline settings
are supplied and read back (FbxImportUI is intentionally not used), the folder
delta must be exactly one package, transient importer state is garbage-collected,
and only that package is saved. MATERIAL handles one piece per execution. It
never edits a pre-existing material: a supplied/existing master is read-only and
must match the parameter contract; otherwise a new master and MI are create-only.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import shutil


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ARGS = os.path.join(HERE, "stage_front_3d_import_args.json")
RECORD = os.path.join(HERE, "stage_front_3d_import_record.json")


def _load_core():
    spec = importlib.util.spec_from_file_location("stage_front_3d_core", os.path.join(HERE, "stage_front_3d_core.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


C = _load_core()


class ToolError(RuntimeError):
    pass


def _u():
    import unreal
    return unreal


def _pkg(value):
    text = value.get_path_name() if hasattr(value, "get_path_name") else str(value)
    if "'" in text:
        text = text.split("'", 2)[1]
    return text.split(".", 1)[0]


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, doc, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True); handle.flush(); os.fsync(handle.fileno())
    if _read(path) != json.loads(json.dumps(doc)):
        raise ToolError("JSON_READBACK|" + path)


class Ctx:
    def __init__(self, mode):
        self.u = _u(); self.mode = mode
        self.run = "SF3DI-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.past_write = False

    def require(self, condition, text):
        if not condition:
            suffix = "|NOTHING_ELSE_SAVED_USE_DONT_SAVE" if self.past_write else ""
            self.u.log_error("%s_%s_FAILED|run=%s|%s%s" % (C.MARK, self.mode, self.run, text, suffix))
            raise ToolError(text)


def census(u):
    lib = u.EditorLoadingAndSavingUtils
    names = lambda rows: sorted({_pkg(x.get_name()) for x in rows})
    return {"content": names(lib.get_dirty_content_packages()), "maps": names(lib.get_dirty_map_packages())}


def listing(u):
    eal = u.EditorAssetLibrary
    if not eal.does_directory_exist(C.DEST):
        return set()
    return {_pkg(x) for x in eal.list_assets(C.DEST, recursive=True, include_folder=False)}


def _asset_file(u, package):
    root = u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir())
    return os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + ".uasset")


def backup(c, label, packages, facts):
    root = os.path.join(PROJECT, "Backups", "Pre%s-%s" % (label, c.run))
    os.makedirs(root, exist_ok=False)
    copied = []
    for package in packages:
        source = _asset_file(c.u, package)
        if os.path.isfile(source):
            dest = os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + ".uasset")
            os.makedirs(os.path.dirname(dest), exist_ok=True); shutil.copy2(source, dest)
            c.require(os.path.getsize(source) == os.path.getsize(dest), "BACKUP_READBACK|" + package)
            copied.append({"package": package, "file": os.path.relpath(dest, root).replace("\\", "/")})
    _write(os.path.join(root, "prestate.json"), {"run": c.run, "dirty_before": census(c.u),
           "packages": packages, "copied": copied, "facts": facts}, exclusive=True)
    return root


def guard(c, require_clean=True):
    editor = c.u.get_editor_subsystem(c.u.UnrealEditorSubsystem)
    c.require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    if require_clean:
        c.require(census(c.u) == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % census(c.u))


def pipeline(c, name):
    u = c.u
    generic = u.InterchangeGenericAssetsPipeline()
    mesh = generic.get_editor_property("mesh_pipeline")
    material = generic.get_editor_property("material_pipeline")
    texture = material.get_editor_property("texture_pipeline") if material else None
    c.require(mesh is not None and material is not None, "INTERCHANGE_PIPELINE_SUBOBJECTS")
    generic.set_editor_property("asset_name", name)
    mesh.set_editor_property("import_static_meshes", True)
    material.set_editor_property("import_materials", False)
    if texture is not None:
        texture.set_editor_property("import_textures", False)
    rb = {"mesh": bool(mesh.get_editor_property("import_static_meshes")),
          "materials": bool(material.get_editor_property("import_materials")),
          "textures": None if texture is None else bool(texture.get_editor_property("import_textures")),
          "scale": float(generic.get_editor_property("import_offset_uniform_scale"))}
    c.require(rb == {"mesh": True, "materials": False, "textures": False, "scale": 1.0},
              "INTERCHANGE_READBACK|%s" % rb)
    override = u.InterchangePipelineStackOverride(); override.add_pipeline(generic)
    return override, rb


def import_one(c, row, options=None):
    before = listing(c.u)
    task = c.u.AssetImportTask()
    for key, value in (("filename", row["source"]), ("destination_path", row["dest"].rsplit("/", 1)[0]),
                       ("destination_name", row["dest"].rsplit("/", 1)[1]), ("automated", True),
                       ("replace_existing", False), ("save", False)):
        task.set_editor_property(key, value)
    if options is not None:
        task.set_editor_property("options", options)
    c.u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])  # one asset per IMPORT call
    c.past_write = True
    delta = listing(c.u) - before
    c.require(not C.import_delta_problems(row["dest"], delta),
              "%s (multi-object FBX/strays are never deleted; use Don't Save)" % C.import_delta_problems(row["dest"], delta))
    asset = c.u.EditorAssetLibrary.load_asset(row["dest"])
    c.require(asset is not None, "IMPORT_MISSING|" + row["dest"])
    return asset


def texture_facts(tex):
    return {"srgb": bool(tex.get_editor_property("srgb")),
            "compression": str(tex.get_editor_property("compression_settings")).split(".")[-1].split(":")[0].strip("<> "),
            "max_texture_size": int(tex.get_editor_property("max_texture_size")),
            "flip_green_channel": bool(tex.get_editor_property("flip_green_channel"))}


def master_info(u, mat):
    mel = u.MaterialEditingLibrary
    return {"path": _pkg(mat),
            "textures": sorted(str(x) for x in mel.get_texture_parameter_names(mat)),
            "scalars": sorted(str(x) for x in mel.get_scalar_parameter_names(mat))}


def master_problems(info):
    want_t = sorted(x[3] for x in C.MAP_KINDS)
    want_s = ["DustStrength", "PeelStrength", "SootStrength"]
    out = []
    if info.get("textures") != want_t: out.append("TEXTURE_PARAMETERS")
    if info.get("scalars") != want_s: out.append("SCALAR_PARAMETERS")
    return out


def build_master(c, path, default_textures):
    u = c.u; eal = u.EditorAssetLibrary; tools = u.AssetToolsHelpers.get_asset_tools()
    name, folder = path.rsplit("/", 1)[1], path.rsplit("/", 1)[0]
    c.require(not eal.does_asset_exist(path), "REFUSE_OVERWRITE|" + path)
    mat = tools.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    c.require(mat is not None, "MASTER_CREATE")
    c.past_write = True
    mel = u.MaterialEditingLibrary; MP = u.MaterialProperty
    nodes = {}
    for index, (_, srgb, compression, parameter) in enumerate(C.MAP_KINDS):
        node = mel.create_material_expression(mat, u.MaterialExpressionTextureSampleParameter2D, -700, -300 + index * 150)
        node.set_editor_property("parameter_name", u.Name(parameter)); nodes[parameter] = node
        node.set_editor_property("texture", eal.load_asset(default_textures[parameter]))
        sampler = "SAMPLERTYPE_COLOR" if srgb else ("SAMPLERTYPE_NORMAL" if compression == "TC_NORMALMAP" else "SAMPLERTYPE_LINEAR_COLOR")
        node.set_editor_property("sampler_type", getattr(u.MaterialSamplerType, sampler))
    scalars = {}
    for index, name in enumerate(("DustStrength", "SootStrength", "PeelStrength")):
        node = mel.create_material_expression(mat, u.MaterialExpressionScalarParameter, -300, 500 + index * 100)
        node.set_editor_property("parameter_name", u.Name(name)); node.set_editor_property("default_value", 1.0)
        scalars[name] = node
    weighted = []
    for index, (channel, scalar_name) in enumerate((("r", "DustStrength"), ("g", "SootStrength"), ("a", "PeelStrength"))):
        mask = mel.create_material_expression(mat, u.MaterialExpressionComponentMask, -420, -250 + index * 120)
        for name in ("r", "g", "b", "a"): mask.set_editor_property(name, name == channel)
        mul = mel.create_material_expression(mat, u.MaterialExpressionMultiply, -180, -250 + index * 120)
        c.require(mel.connect_material_expressions(nodes["Masks"], "RGB", mask, "Input"), "CONNECT_MASK_" + channel)
        c.require(mel.connect_material_expressions(mask, "", mul, "A"), "CONNECT_MASK_MUL_" + channel)
        c.require(mel.connect_material_expressions(scalars[scalar_name], "", mul, "B"), "CONNECT_STRENGTH_" + channel)
        weighted.append(mul)
    add1 = mel.create_material_expression(mat, u.MaterialExpressionAdd, 40, -180)
    add2 = mel.create_material_expression(mat, u.MaterialExpressionAdd, 220, -100)
    saturate = mel.create_material_expression(mat, u.MaterialExpressionSaturate, 400, -100)
    blend = mel.create_material_expression(mat, u.MaterialExpressionLinearInterpolate, 600, -220)
    c.require(mel.connect_material_expressions(weighted[0], "", add1, "A"), "CONNECT_DUST_ADD")
    c.require(mel.connect_material_expressions(weighted[1], "", add1, "B"), "CONNECT_SOOT_ADD")
    c.require(mel.connect_material_expressions(add1, "", add2, "A"), "CONNECT_AGING_ADD")
    c.require(mel.connect_material_expressions(weighted[2], "", add2, "B"), "CONNECT_PEEL_ADD")
    c.require(mel.connect_material_expressions(add2, "", saturate, "Input"), "CONNECT_SATURATE")
    c.require(mel.connect_material_expressions(nodes["BaseColorClean"], "RGB", blend, "A"), "CONNECT_CLEAN")
    c.require(mel.connect_material_expressions(nodes["BaseColorDusty"], "RGB", blend, "B"), "CONNECT_DUSTY")
    c.require(mel.connect_material_expressions(saturate, "", blend, "Alpha"), "CONNECT_BLEND_ALPHA")
    c.require(mel.connect_material_property(blend, "", MP.MP_BASE_COLOR), "CONNECT_BASE")
    c.require(mel.connect_material_property(nodes["Normal"], "RGB", MP.MP_NORMAL), "CONNECT_NORMAL")
    c.require(mel.connect_material_property(nodes["Roughness"], "R", MP.MP_ROUGHNESS), "CONNECT_ROUGHNESS")
    c.require(mel.connect_material_property(nodes["Masks"], "B", MP.MP_AMBIENT_OCCLUSION), "CONNECT_AO")
    mel.layout_material_expressions(mat); mel.recompile_material(mat)
    info = master_info(u, mat); c.require(not master_problems(info), "MASTER_READBACK|%s" % master_problems(info))
    return mat, info


def mi_facts(c, mi):
    mel = c.u.MaterialEditingLibrary
    return {"parent": _pkg(mi.get_editor_property("parent")),
            "textures": {x[3]: _pkg(mel.get_material_instance_texture_parameter_value(mi, x[3])) for x in C.MAP_KINDS},
            "scalars": {n: float(mel.get_material_instance_scalar_parameter_value(mi, n))
                        for n in ("DustStrength", "SootStrength", "PeelStrength")}}


def run_dry(c, plan, rec):
    guard(c, require_clean=False); before = census(c.u)
    existing = sorted(set(plan["packages"] + plan["material_packages"] + [C.MASTER_DEFAULT]) & listing(c.u))
    c.require(census(c.u) == before, "DRY_DIRTIED")
    c.u.log("%s_IMPORT_DRY_%s|run=%s|mutated=0|inputs=%d|missing=%s|existing=%s|dirty=%s|record=%d" %
            (C.MARK, "OK" if not plan["missing"] and not existing and before == {"content": [], "maps": []} else "REFUSED",
             c.run, len(plan["imports"]), plan["missing"], existing, before, bool(rec)))


def run_import(c, plan, rec, values):
    guard(c); row = C.find_import(plan, values["asset"])
    c.require(os.path.isfile(row["source"]), "SOURCE_MISSING|" + row["source"])
    eal = c.u.EditorAssetLibrary; c.require(not eal.does_asset_exist(row["dest"]), "REFUSE_OVERWRITE|" + row["dest"])
    imported = dict((rec or {}).get("imported", {})); c.require(row["selector"] not in imported, "ALREADY_RECORDED")
    backup_dir = backup(c, "StageFront3DImport", [row["dest"]], {"selector": row["selector"], "sha256": C.sha256(row["source"])})
    pending = dict(rec or {"schema": 1, "created_packages": [], "imported": {}, "materials": {}})
    pending.update({"state": "importing", "pending": {"run": c.run, "selector": row["selector"], "backup": backup_dir}})
    _write(RECORD, pending, exclusive=rec is None)
    options, pipe = (pipeline(c, row["dest"].rsplit("/", 1)[1]) if row["kind"] == "mesh" else (None, None))
    asset = import_one(c, row, options)
    if row["kind"] == "mesh":
        c.require(isinstance(asset, c.u.StaticMesh), "MESH_CLASS")
        facts = {"kind": "mesh", "lods": int(asset.get_num_lods()), "bounds": str(asset.get_bounding_box()), "pipeline": pipe}
    else:
        c.require(isinstance(asset, c.u.Texture2D), "TEXTURE_CLASS")
        asset.modify(); asset.set_editor_property("srgb", row["srgb"])
        asset.set_editor_property("compression_settings", getattr(c.u.TextureCompressionSettings, row["compression"]))
        asset.set_editor_property("max_texture_size", values["max_texture_size"])
        if row["map_kind"] == "N": asset.set_editor_property("flip_green_channel", False)  # source is DirectX / V down
        facts = {"kind": "texture", "settings": texture_facts(asset)}
        c.require(facts["settings"]["max_texture_size"] <= 4096 and facts["settings"]["srgb"] == row["srgb"],
                  "TEXTURE_SETTINGS|%s" % facts)
    c.u.SystemLibrary.collect_garbage()
    c.require(census(c.u) == {"content": [row["dest"]], "maps": []}, "DIRTY_SCOPE|%s" % census(c.u))
    c.require(eal.save_asset(row["dest"], only_if_is_dirty=False), "SAVE|" + row["dest"])
    c.require(census(c.u) == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|%s" % census(c.u))
    saved = eal.load_asset(row["dest"]); c.require(saved is not None, "SAVED_READBACK")
    imported[row["selector"]] = {"run": c.run, "package": row["dest"], "source": row["source"],
                                  "sha256": C.sha256(row["source"]), "facts": facts, "backup": backup_dir}
    pending.update({"pending": None, "imported": imported,
                    "created_packages": sorted(set(pending["created_packages"] + [row["dest"]])),
                    "state": "imported" if len(imported) == len(plan["imports"]) else "importing"})
    _write(RECORD, pending)
    c.u.log("%s_IMPORT_OK|run=%s|asset=%s|one_call=1|gc=1|saved=1|dirty_after=0+0|complete=%d/%d" %
            (C.MARK, c.run, row["selector"], len(imported), len(plan["imports"])))


def run_material(c, plan, rec, values):
    guard(c); c.require(rec is not None, "IMPORT_RECORD_REQUIRED")
    key = values["piece"]; mesh_path = C.package_for("mesh", key); mi_path = C.package_for("mi", key)
    eal = c.u.EditorAssetLibrary; mel = c.u.MaterialEditingLibrary
    required = [mesh_path] + [C.package_for("texture", key, row[0]) for row in C.MAP_KINDS]
    c.require(all(eal.does_asset_exist(x) for x in required), "PIECE_IMPORTS_INCOMPLETE|%s" % required)
    c.require(not eal.does_asset_exist(mi_path), "REFUSE_OVERWRITE|" + mi_path)
    master_path = values["master_path"]
    master_exists = eal.does_asset_exist(master_path)
    targets = [mi_path, mesh_path] + ([] if master_exists else [master_path])
    backup_dir = backup(c, "StageFront3DMaterial", targets, {"piece": key, "master": master_path, "existing_master": master_exists})
    rec.update({"pending": {"run": c.run, "mode": "MATERIAL", "piece": key, "backup": backup_dir}}); _write(RECORD, rec)
    texture_paths = {row[3]: C.package_for("texture", key, row[0]) for row in C.MAP_KINDS}
    if master_exists:
        master = eal.load_asset(master_path); info = master_info(c.u, master)
        c.require(not master_problems(info), "PREEXISTING_MASTER_INCOMPATIBLE|%s" % master_problems(info))
    else:
        master, info = build_master(c, master_path, texture_paths)
    mi = c.u.AssetToolsHelpers.get_asset_tools().create_asset(mi_path.rsplit("/", 1)[1], mi_path.rsplit("/", 1)[0],
            c.u.MaterialInstanceConstant, c.u.MaterialInstanceConstantFactoryNew())
    c.require(mi is not None, "MI_CREATE"); c.past_write = True
    mi.modify(); mel.set_material_instance_parent(mi, master)
    textures = {}
    for map_kind, _, _, parameter in C.MAP_KINDS:
        path = C.package_for("texture", key, map_kind); textures[parameter] = path
        mel.set_material_instance_texture_parameter_value(mi, parameter, eal.load_asset(path))
    for name, value in (("DustStrength", values["dust_strength"]), ("SootStrength", values["soot_strength"]),
                        ("PeelStrength", values["peel_strength"])):
        mel.set_material_instance_scalar_parameter_value(mi, name, value)
    mel.update_material_instance(mi); got = mi_facts(c, mi)
    c.require(got["parent"] == master_path and got["textures"] == textures, "MI_READBACK|%s" % got)
    mesh = eal.load_asset(mesh_path); slots = list(mesh.get_editor_property("static_materials"))
    c.require(len(slots) == 1, "MESH_SLOT_COUNT|%d" % len(slots))
    mesh.modify(); mesh.set_material(0, mi)
    bound = [_pkg(x.get_editor_property("material_interface")) for x in mesh.get_editor_property("static_materials")]
    c.require(bound == [mi_path], "MESH_MATERIAL_READBACK|%s" % bound)
    save = sorted(set(targets)); c.require(census(c.u) == {"content": save, "maps": []}, "DIRTY_SCOPE|%s" % census(c.u))
    for path in save: c.require(eal.save_asset(path, only_if_is_dirty=False), "SAVE|" + path)
    c.require(census(c.u) == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE")
    materials = dict(rec.get("materials", {})); materials[key] = {"run": c.run, "mi": mi_path, "master": master_path,
                    "master_created": not master_exists, "mi_readback": got, "mesh_materials": bound, "backup": backup_dir}
    created = rec["created_packages"] + [mi_path] + ([] if master_exists else [master_path])
    rec.update({"pending": None, "materials": materials, "created_packages": sorted(set(created)), "state": "materialized"})
    _write(RECORD, rec)
    c.u.log("%s_MATERIAL_OK|run=%s|piece=%s|master=%s|master_reused=%d|mi=%s|saved=%d|dirty_after=0+0" %
            (C.MARK, c.run, key, master_path, master_exists, mi_path, len(save)))


def run_verify(c, plan, rec):
    guard(c); eal = c.u.EditorAssetLibrary; problems = []
    planned = {row["selector"]: row for row in plan["imports"]}
    for selector, saved_row in rec.get("imported", {}).items():
        path = saved_row["package"]; row = planned.get(selector)
        if not eal.does_asset_exist(path): problems.append("MISSING|" + path); continue
        asset = eal.load_asset(path)
        if row is None: problems.append("UNKNOWN_RECORDED_SELECTOR|" + selector)
        elif row["kind"] == "mesh" and not isinstance(asset, c.u.StaticMesh): problems.append("MESH_CLASS|" + path)
        elif row["kind"] == "texture":
            got = texture_facts(asset)
            if got["srgb"] != row["srgb"] or got["compression"] != row["compression"] or got["max_texture_size"] > 4096:
                problems.append("TEXTURE_DRIFT|%s|%s" % (path, got))
            if row["map_kind"] == "N" and got["flip_green_channel"]: problems.append("NORMAL_GREEN_FLIP|" + path)
    for key, row in rec.get("materials", {}).items():
        if not eal.does_asset_exist(row["mi"]): problems.append("MISSING|" + row["mi"])
        elif mi_facts(c, eal.load_asset(row["mi"])) != row["mi_readback"]: problems.append("MI_DRIFT|" + key)
        mesh = eal.load_asset(C.package_for("mesh", key))
        bound = [] if mesh is None else [_pkg(x.get_editor_property("material_interface"))
                                        for x in mesh.get_editor_property("static_materials")]
        if bound != row["mesh_materials"]: problems.append("MESH_MATERIAL_DRIFT|%s|%s" % (key, bound))
    c.require(not problems, "VERIFY|%s" % problems); c.require(census(c.u) == {"content": [], "maps": []}, "VERIFY_DIRTIED")
    c.u.log("%s_IMPORT_VERIFY_OK|run=%s|imports=%d|materials=%d|dirty=0" %
            (C.MARK, c.run, len(rec.get("imported", {})), len(rec.get("materials", {}))))


def run_revert(c, rec):
    guard(c); eal = c.u.EditorAssetLibrary; ours = set(rec.get("created_packages", []))
    c.require(bool(ours), "NOTHING_RECORDED")
    for path in ours:
        refs = {_pkg(x) for x in eal.find_package_referencers_for_asset(path, False)}
        c.require(not (refs - ours), "FOREIGN_REFERENCERS|%s|%s" % (path, sorted(refs - ours)))
    backup(c, "StageFront3DRevert", sorted(ours), {"record": rec})
    priority = lambda p: (0 if "/MI_" in p else 1 if "/Meshes/" in p else 2 if p.endswith("M_StageFront_Baked_Master") else 3, p)
    for path in sorted(ours, key=priority):
        c.require(eal.delete_asset(path), "DELETE|" + path); c.require(not eal.does_asset_exist(path), "DELETE_READBACK|" + path)
    archived = RECORD.replace(".json", ".reverted-%s.json" % c.run); os.replace(RECORD, archived)
    c.u.log("%s_IMPORT_REVERT_OK|run=%s|deleted=%d|record=%s" % (C.MARK, c.run, len(ours), archived))


def main():
    args = _read(ARGS); rec = _read(RECORD) if os.path.isfile(RECORD) else None
    mode, values = C.validate_import_args(args, rec); c = Ctx(mode); plan = C.build_plan(PROJECT)
    c.u.log("%s_IMPORT_START|run=%s|mode=%s" % (C.MARK, c.run, mode))
    if mode == "DRY": run_dry(c, plan, rec)
    elif mode == "IMPORT": run_import(c, plan, rec, values)
    elif mode == "MATERIAL": run_material(c, plan, rec, values)
    elif mode == "VERIFY": run_verify(c, plan, rec)
    else: run_revert(c, rec)


if __name__ != "__stage_front_3d_offline__":
    main()
