"""Guarded UE 5.8 import/material tool for Job 131; authored offline.

One IMPORT execution accepts exactly one selector. Interchange pipeline settings
are supplied and read back (FbxImportUI is intentionally not used), the folder
delta must be exactly one package, transient importer state is garbage-collected,
and only that package is saved. MATERIAL handles one piece per execution. Job
149 forbids master-graph construction: MATERIAL reuses a saved parent, creates
only one MI, binds it to one mesh, and saves only those two packages.
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


def nanite_facts(mesh):
    """Read the persisted StaticMesh Nanite contract (UE 5.8 editor property)."""
    settings = mesh.get_editor_property("nanite_settings")
    return {"enabled": bool(settings.get_editor_property("enabled"))}


def enable_nanite(c, mesh):
    """Enable Nanite after Interchange import, then read it back before any save."""
    mesh.modify()
    settings = mesh.get_editor_property("nanite_settings")
    settings.set_editor_property("enabled", True)
    mesh.set_editor_property("nanite_settings", settings)
    got = nanite_facts(mesh)
    c.require(got == {"enabled": True}, "NANITE_IN_MEMORY_READBACK|%s" % got)
    return got


def master_info(u, mat):
    mel = u.MaterialEditingLibrary
    return {"path": _pkg(mat),
            "textures": sorted(str(x) for x in mel.get_texture_parameter_names(mat))}


def master_problems(info):
    problem = C.master_parameter_problem(info.get("textures", []))
    return [] if problem is None else [problem]


def load_existing_master(c, path):
    """Read-only parent selection.  Never creates, edits, recompiles or saves it."""
    eal = c.u.EditorAssetLibrary
    c.require(eal.does_asset_exist(path), "EXISTING_MASTER_REQUIRED|" + path)
    c.require(os.path.isfile(_asset_file(c.u, path)), "EXISTING_SAVED_MASTER_REQUIRED|" + path)
    mat = eal.load_asset(path)
    c.require(isinstance(mat, c.u.Material), "MASTER_CLASS|" + path)
    info = master_info(c.u, mat)
    problems = master_problems(info)
    c.require(not problems, "PREEXISTING_MASTER_INCOMPATIBLE|%s" % problems)
    return mat, info


def mi_facts(c, mi):
    mel = c.u.MaterialEditingLibrary
    return {"parent": _pkg(mi.get_editor_property("parent")),
            "textures": {parameter: _pkg(mel.get_material_instance_texture_parameter_value(mi, parameter))
                         for _, parameter in C.MI_TEXTURE_BINDINGS}}


def run_dry(c, plan, rec, values):
    guard(c, require_clean=False); before = census(c.u)
    piece = values.get("piece")
    if piece is not None:
        master, info = load_existing_master(c, values["master_path"])
        required = [C.package_for("mesh", piece)] + [C.package_for("texture", piece, kind)
                                                     for kind, _ in C.MI_TEXTURE_BINDINGS]
        missing = [path for path in required if not c.u.EditorAssetLibrary.does_asset_exist(path)]
        mi_path = C.package_for("mi", piece)
        c.require(not missing, "PIECE_IMPORTS_INCOMPLETE|%s" % missing)
        c.require(not c.u.EditorAssetLibrary.does_asset_exist(mi_path), "REFUSE_OVERWRITE|" + mi_path)
        mesh = c.u.EditorAssetLibrary.load_asset(C.package_for("mesh", piece))
        c.require(len(list(mesh.get_editor_property("static_materials"))) == 1, "MESH_SLOT_COUNT")
        c.require(census(c.u) == before, "DRY_DIRTIED")
        c.require(before == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % before)
        c.u.log("%s_MATERIAL_DRY_OK|run=%s|mutated=0|piece=%s|master=%s|texture_parameters=%s|mi=%s|dirty=0" %
                (C.MARK, c.run, piece, _pkg(master), info["textures"], mi_path))
        return
    existing = sorted(set(plan["packages"] + plan["material_packages"]) & listing(c.u))
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
        nanite = enable_nanite(c, asset)
        facts = {"kind": "mesh", "lods": int(asset.get_num_lods()), "bounds": str(asset.get_bounding_box()),
                 "pipeline": pipe, "nanite": nanite}
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
    if row["kind"] == "mesh":
        c.require(nanite_facts(saved) == {"enabled": True},
                  "NANITE_SAVED_READBACK|%s" % nanite_facts(saved))
    imported[row["selector"]] = {"run": c.run, "package": row["dest"], "source": row["source"],
                                  "sha256": C.sha256(row["source"]), "facts": facts, "backup": backup_dir}
    pending.update({"pending": None, "imported": imported,
                    "created_packages": sorted(set(pending["created_packages"] + [row["dest"]])),
                    "state": "imported" if len(imported) == len(plan["imports"]) else "importing"})
    _write(RECORD, pending)
    c.u.log("%s_IMPORT_OK|run=%s|asset=%s|one_call=1|gc=1|saved=1|dirty_after=0+0|complete=%d/%d" %
            (C.MARK, c.run, row["selector"], len(imported), len(plan["imports"])))


def run_material(c, plan, rec, values):
    guard(c, require_clean=False); c.require(rec is not None, "IMPORT_RECORD_REQUIRED")
    key = values["piece"]; mesh_path = C.package_for("mesh", key); mi_path = C.package_for("mi", key)
    eal = c.u.EditorAssetLibrary; mel = c.u.MaterialEditingLibrary
    required = [mesh_path] + [C.package_for("texture", key, row[0]) for row in C.MAP_KINDS]
    c.require(all(eal.does_asset_exist(x) for x in required), "PIECE_IMPORTS_INCOMPLETE|%s" % required)
    c.require(not eal.does_asset_exist(mi_path), "REFUSE_OVERWRITE|" + mi_path)
    master_path = values["master_path"]
    c.require(census(c.u) == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % census(c.u))
    master, info = load_existing_master(c, master_path)
    targets = [mi_path, mesh_path]
    backup_dir = backup(c, "StageFront3DMaterial", targets,
                        {"piece": key, "master": master_path, "master_parameters": info["textures"]})
    rec.update({"pending": {"run": c.run, "mode": "MATERIAL", "piece": key, "backup": backup_dir}}); _write(RECORD, rec)
    texture_paths = {parameter: C.package_for("texture", key, map_kind)
                     for map_kind, parameter in C.MI_TEXTURE_BINDINGS}
    mi = c.u.AssetToolsHelpers.get_asset_tools().create_asset(mi_path.rsplit("/", 1)[1], mi_path.rsplit("/", 1)[0],
            c.u.MaterialInstanceConstant, c.u.MaterialInstanceConstantFactoryNew())
    c.require(mi is not None, "MI_CREATE"); c.past_write = True
    mi.modify(); mel.set_material_instance_parent(mi, master)
    textures = {}
    for map_kind, parameter in C.MI_TEXTURE_BINDINGS:
        path = C.package_for("texture", key, map_kind); textures[parameter] = path
        mel.set_material_instance_texture_parameter_value(mi, parameter, eal.load_asset(path))
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
                    "master_parameters": info["textures"], "mi_readback": got,
                    "mesh_materials": bound, "backup": backup_dir}
    created = rec["created_packages"] + [mi_path]
    rec.update({"pending": None, "materials": materials, "created_packages": sorted(set(created)), "state": "materialized"})
    _write(RECORD, rec)
    c.u.log("%s_MATERIAL_OK|run=%s|piece=%s|master=%s|existing_parent=1|mi=%s|saved=%d|dirty_after=0+0" %
            (C.MARK, c.run, key, master_path, mi_path, len(save)))


def run_verify(c, plan, rec):
    guard(c); eal = c.u.EditorAssetLibrary; problems = []
    planned = {row["selector"]: row for row in plan["imports"]}
    for selector, saved_row in rec.get("imported", {}).items():
        path = saved_row["package"]; row = planned.get(selector)
        if not eal.does_asset_exist(path): problems.append("MISSING|" + path); continue
        asset = eal.load_asset(path)
        if row is None: problems.append("UNKNOWN_RECORDED_SELECTOR|" + selector)
        elif row["kind"] == "mesh" and not isinstance(asset, c.u.StaticMesh): problems.append("MESH_CLASS|" + path)
        elif row["kind"] == "mesh" and nanite_facts(asset) != {"enabled": True}:
            problems.append("NANITE_DRIFT|%s|%s" % (path, nanite_facts(asset)))
        elif row["kind"] == "texture":
            got = texture_facts(asset)
            if got["srgb"] != row["srgb"] or got["compression"] != row["compression"] or got["max_texture_size"] > 4096:
                problems.append("TEXTURE_DRIFT|%s|%s" % (path, got))
            if row["map_kind"] == "N" and got["flip_green_channel"]: problems.append("NORMAL_GREEN_FLIP|" + path)
    for key, row in rec.get("materials", {}).items():
        master = eal.load_asset(row["master"])
        if master is None: problems.append("MISSING_PARENT|" + row["master"])
        elif master_info(c.u, master)["textures"] != row["master_parameters"]:
            problems.append("MASTER_PARAMETER_DRIFT|" + key)
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
    priority = lambda p: (0 if "/MI_" in p else 1 if "/Meshes/" in p else 2, p)
    for path in sorted(ours, key=priority):
        c.require(eal.delete_asset(path), "DELETE|" + path); c.require(not eal.does_asset_exist(path), "DELETE_READBACK|" + path)
    archived = RECORD.replace(".json", ".reverted-%s.json" % c.run); os.replace(RECORD, archived)
    c.u.log("%s_IMPORT_REVERT_OK|run=%s|deleted=%d|record=%s" % (C.MARK, c.run, len(ours), archived))


def main():
    args = _read(ARGS); rec = _read(RECORD) if os.path.isfile(RECORD) else None
    mode, values = C.validate_import_args(args, rec); c = Ctx(mode); plan = C.build_plan(PROJECT)
    c.u.log("%s_IMPORT_START|run=%s|mode=%s" % (C.MARK, c.run, mode))
    if mode == "DRY": run_dry(c, plan, rec, values)
    elif mode == "IMPORT": run_import(c, plan, rec, values)
    elif mode == "MATERIAL": run_material(c, plan, rec, values)
    elif mode == "VERIFY": run_verify(c, plan, rec)
    else: run_revert(c, rec)


if __name__ != "__stage_front_3d_offline__":
    main()
