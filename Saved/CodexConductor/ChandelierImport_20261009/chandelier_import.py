"""P80 Iron3 chandelier Unreal authoring tool (prepared offline; conductor runs live).

Modes, read from ``chandelier_import_args.json``:
  DRY       read-only source/API/target/dirty census.
  IMPORT    create-only import of two FBXs and five textures, one import call each.
  MAT_CHECK read-only compatible-master search and parameter/sampler report.
  APPLY     create/reuse the aged master, create MI, bind both meshes, targeted save.
  REVERT    explicit-confirm deletion of packages recorded as created by this tool.

The source DirectX normal is imported unchanged: Unreal tangent-space normal maps
use the same green/Y-down convention. ``flip_green_channel`` is set and read back
as False. No actor, level, Show asset, Unreal process, or Blender process is touched.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import shutil


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ARGS = os.path.join(HERE, "chandelier_import_args.json")
RECORD = os.path.join(HERE, "chandelier_import_record.json")
MAT_REPORT = os.path.join(HERE, "chandelier_mat_check_latest.json")


def _load_core():
    spec = importlib.util.spec_from_file_location("p80_chandelier_core", os.path.join(HERE, "chandelier_import_core.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load_core()


class ToolError(RuntimeError):
    pass


def _u():
    import unreal  # noqa: PLC0415 - unavailable and forbidden in the offline harness
    return unreal


def _pkg(value):
    if value is None:
        return None
    text = value.get_path_name() if hasattr(value, "get_path_name") else str(value)
    if "'" in text:
        text = text.split("'", 2)[1]
    return text.split(".", 1)[0]


def _write_json(path, doc, exclusive=False):
    mode = "x" if exclusive else "w"
    with open(path, mode, encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    if json.load(open(path, encoding="utf-8")) != json.loads(json.dumps(doc)):
        raise ToolError("JSON_READBACK|" + path)


def _record():
    return json.load(open(RECORD, encoding="utf-8")) if os.path.isfile(RECORD) else None


class Ctx:
    def __init__(self, mode):
        self.u = _u()
        self.mode = mode
        self.run = "CHI-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.past_write = False

    def log(self, text):
        self.u.log(text)

    def fail(self, text):
        tail = "|NOTHING ELSE SAVED; if packages are dirty use Don't Save" if self.past_write else ""
        self.u.log_error("%s_FAILED|run=%s|mode=%s|%s%s" % (C.MARK, self.run, self.mode, text, tail))
        raise ToolError(text)

    def require(self, condition, text):
        if not condition:
            self.fail(text)


def census(u):
    lib = u.EditorLoadingAndSavingUtils
    return {"content": sorted({_pkg(p.get_name()) for p in lib.get_dirty_content_packages()}),
            "maps": sorted({_pkg(p.get_name()) for p in lib.get_dirty_map_packages()})}


def listing(u):
    eal = u.EditorAssetLibrary
    if not eal.does_directory_exist(C.DEST):
        return set()
    return {_pkg(p) for p in eal.list_assets(C.DEST, recursive=True, include_folder=False)}


def _asset_file(u, package):
    content = u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir())
    return os.path.join(content, package[len("/Game/"):].replace("/", os.sep) + ".uasset")


def _backup(c, label, packages, facts):
    root = os.path.join(PROJECT, "Backups", "Pre%s-%s" % (label, c.run))
    os.makedirs(root, exist_ok=False)
    copied = []
    for package in packages:
        src = _asset_file(c.u, package)
        if os.path.isfile(src):
            dst = os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + ".uasset")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied.append({"package": package, "file": os.path.relpath(dst, root)})
    doc = {"run": c.run, "label": label, "dirty_before": census(c.u), "packages_considered": packages,
           "copied": copied, "facts": facts}
    _write_json(os.path.join(root, "prestate.json"), doc, exclusive=True)
    return root


def _guard(c, clean=True):
    editor = c.u.get_editor_subsystem(c.u.UnrealEditorSubsystem)
    c.require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE (refused; never ends it)")
    if clean:
        c.require(census(c.u) == {"content": [], "maps": []}, "DIRTY_AT_START|%s" % census(c.u))


def _pipeline(c, asset_name):
    u = c.u
    p = u.InterchangeGenericAssetsPipeline()
    mesh = p.get_editor_property("mesh_pipeline")
    material = p.get_editor_property("material_pipeline")
    c.require(mesh is not None and material is not None, "INTERCHANGE_PIPELINE_SUBOBJECTS")
    texture = material.get_editor_property("texture_pipeline")
    p.set_editor_property("asset_name", asset_name)
    mesh.set_editor_property("import_static_meshes", True)
    material.set_editor_property("import_materials", False)
    if texture is not None:
        texture.set_editor_property("import_textures", False)
    rb = {"import_static_meshes": bool(mesh.get_editor_property("import_static_meshes")),
          "import_materials": bool(material.get_editor_property("import_materials")),
          "import_textures": None if texture is None else bool(texture.get_editor_property("import_textures")),
          "scale": float(p.get_editor_property("import_offset_uniform_scale"))}
    c.require(rb == {"import_static_meshes": True, "import_materials": False,
                     "import_textures": False, "scale": 1.0}, "INTERCHANGE_READBACK|%s" % rb)
    override = u.InterchangePipelineStackOverride()
    override.add_pipeline(p)
    return override, rb


def _import_one(c, source, dest, options=None):
    u = c.u
    before = listing(u)
    task = u.AssetImportTask()
    for key, value in (("filename", source), ("destination_path", C.DEST),
                       ("destination_name", dest.rsplit("/", 1)[-1]), ("automated", True),
                       ("replace_existing", False), ("save", False)):
        task.set_editor_property(key, value)
    if options is not None:
        task.set_editor_property("options", options)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])  # exactly one task per call
    new = listing(u) - before
    c.require(new == {dest}, "IMPORT_DELTA|want=%s|got=%s (no stray is deleted; Don't Save)" % (dest, sorted(new)))
    asset = u.EditorAssetLibrary.load_asset(dest)
    c.require(asset is not None, "IMPORT_MISSING|" + dest)
    c.past_write = True
    return asset


def _socket_names(mesh):
    # UE 5.8 protects the Sockets property; this is the measured repo precedent.
    return sorted(str(s.get_editor_property("socket_name")) for s in mesh.get_sockets_by_tag(""))


def _texture_readback(tex):
    return {"srgb": bool(tex.get_editor_property("srgb")),
            "compression": str(tex.get_editor_property("compression_settings")).split(".")[-1],
            "flip_green_channel": bool(tex.get_editor_property("flip_green_channel"))}


def _source_gate(c, plan):
    c.require(not plan["missing"], "SOURCE_SET|%s" % plan["missing"])
    c.require(not plan["manifest_problems"], "CHAIN_MANIFEST|%s" % plan["manifest_problems"])


def run_dry(c, plan, rec):
    _guard(c, clean=False)
    before = census(c.u)
    existing = sorted(p for p in plan["apply_packages"] if c.u.EditorAssetLibrary.does_asset_exist(p))
    blockers = []
    if plan["missing"]:
        blockers.append("SOURCE_SET")
    if plan["manifest_problems"]:
        blockers.append("CHAIN_MANIFEST")
    if before != {"content": [], "maps": []}:
        blockers.append("DIRTY")
    if existing:
        blockers.append("TARGETS_EXIST")
    if rec:
        blockers.append("RECORD_EXISTS")
    c.require(census(c.u) == before, "DRY_DIRTIED")
    c.log("%s_DRY_%s|run=%s|mutated=0|sources=%d|existing=%s|dirty=%s|blockers=%s"
          % (C.MARK, "OK" if not blockers else "REFUSED", c.run, len(plan["hashes"]), existing, before, blockers))


def run_import(c, plan):
    _guard(c)
    _source_gate(c, plan)
    eal = c.u.EditorAssetLibrary
    c.require(not [p for p in plan["apply_packages"] if eal.does_asset_exist(p)], "REFUSE_OVERWRITE")
    backup = _backup(c, "ChandelierImport", plan["apply_packages"], {"source_hashes": plan["hashes"]})
    facts = {"meshes": {}, "textures": {}, "pipeline": {}}
    for row in plan["meshes"]:
        options, pipe = _pipeline(c, row["name"])
        mesh = _import_one(c, row["source"], row["dest"], options)
        c.require(isinstance(mesh, c.u.StaticMesh), "MESH_CLASS|" + row["dest"])
        sockets = _socket_names(mesh)
        if row["name"] == C.BODY_NAME:
            c.require(not C.socket_problems(sockets), "SOCKETS|%s" % C.socket_problems(sockets))
        facts["meshes"][row["name"]] = {"sockets": sockets, "lods": int(mesh.get_num_lods())}
        facts["pipeline"][row["name"]] = pipe
    for row in plan["textures"]:
        tex = _import_one(c, row["matches"][0], row["dest"])
        c.require(isinstance(tex, c.u.Texture2D), "TEXTURE_CLASS|" + row["dest"])
        tex.modify()
        tex.set_editor_property("srgb", row["srgb"])
        tex.set_editor_property("compression_settings", getattr(c.u.TextureCompressionSettings, row["compression"]))
        if row["parameter"] == "NormalTexture":
            tex.set_editor_property("flip_green_channel", False)
        got = _texture_readback(tex)
        c.require(not C.texture_settings_problems(row, got), "TEXTURE_SETTINGS|%s|%s" % (row["dest"], got))
        facts["textures"][row["parameter"]] = got
    want = set(plan["imported_packages"])
    dirty = census(c.u)
    c.require(not dirty["maps"] and set(dirty["content"]) == want, "DIRTY_SCOPE|%s" % dirty)
    for path in plan["imported_packages"]:
        c.require(eal.save_asset(path, only_if_is_dirty=False), "SAVE|" + path)
    c.require(census(c.u) == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|%s" % census(c.u))
    # Saved-state read-back, after all imports/configuration are complete.
    body = eal.load_asset(C.DEST + "/" + C.BODY_NAME)
    c.require(not C.socket_problems(_socket_names(body)), "SAVED_SOCKET_READBACK")
    for row in plan["textures"]:
        got = _texture_readback(eal.load_asset(row["dest"]))
        c.require(not C.texture_settings_problems(row, got), "SAVED_TEXTURE_READBACK|%s" % row["dest"])
    doc = {"run": c.run, "state": "imported", "backup": backup, "source_hashes": plan["hashes"],
           "created_packages": list(plan["imported_packages"]), "master": None, "facts": facts}
    _write_json(RECORD, doc, exclusive=True)
    c.log("%s_IMPORT_OK|run=%s|packages=7|body_sockets=45|candles=44|chain_attach=1|normal=DirectX_no_flip|dirty_after=0+0|record=%s"
          % (C.MARK, c.run, RECORD))


def _sampler_name(tex):
    compression = str(tex.get_editor_property("compression_settings")).split(".")[-1]
    srgb = bool(tex.get_editor_property("srgb"))
    for row in C.TEXTURE_SPECS:
        if row[4] == compression and row[3] == srgb:
            return row[5]
    return "SAMPLERTYPE_COLOR" if srgb else "SAMPLERTYPE_LINEAR_COLOR"


def _master_info(u, mat):
    mel = u.MaterialEditingLibrary
    samplers = {}
    for expr in mel.get_material_expressions(mat):
        if isinstance(expr, u.MaterialExpressionTextureSampleParameter2D):
            samplers[str(expr.get_editor_property("parameter_name"))] = str(expr.get_editor_property("sampler_type"))
    return {"path": _pkg(mat), "textures": sorted(str(n) for n in mel.get_texture_parameter_names(mat)),
            "scalars": sorted(str(n) for n in mel.get_scalar_parameter_names(mat)),
            "switches": sorted(str(n) for n in mel.get_static_switch_parameter_names(mat)), "samplers": samplers}


def _master_candidates(c):
    u, eal = c.u, c.u.EditorAssetLibrary
    roots = (C.DEST, "/Game/Scenes/Props/StageFront", "/Game/InfinityStage/StageFront",
             "/Game/Scenes/Wings/PaintedSurface")
    seen, compatible, inspected = set(), [], []
    for root in roots:
        if not eal.does_directory_exist(root):
            continue
        for path in eal.list_assets(root, recursive=True, include_folder=False):
            package = _pkg(path)
            if package in seen or not package.rsplit("/", 1)[-1].startswith("M_"):
                continue
            seen.add(package)
            asset = eal.load_asset(package)
            if not isinstance(asset, u.Material):
                continue
            info = _master_info(u, asset)
            probs = C.master_contract_problems(info)
            if not probs:
                compatible.append(info)
            if any(x in set(info["textures"]) for x in ("MasksTexture", "BaseColorDusty", "BaseColorClean")):
                inspected.append({"path": package, "problems": probs})
    compatible.sort(key=lambda x: x["path"])
    return compatible, inspected


def run_mat_check(c, plan, rec):
    _guard(c, clean=False)
    before = census(c.u)
    compatible, inspected = _master_candidates(c)
    c.require(len(compatible) <= 1, "AMBIGUOUS_COMPATIBLE_MASTERS|%s" % [r["path"] for r in compatible])
    decision = compatible[0]["path"] if compatible else C.DEST + "/" + C.MASTER_NAME
    doc = {"run": c.run, "mode": "MAT_CHECK", "mutated_packages": 0, "decision": decision,
           "reuse": bool(compatible), "compatible": compatible, "inspected_related": inspected,
           "normal_convention": plan["normal_convention"], "record_state": rec["state"]}
    _write_json(MAT_REPORT, doc)
    c.require(census(c.u) == before, "MAT_CHECK_DIRTIED")
    c.log("%s_MAT_CHECK_OK|run=%s|mutated=0|master=%s|reuse=%d|report=%s"
          % (C.MARK, c.run, decision, bool(compatible), MAT_REPORT))


class _Graph:
    def __init__(self, c, mat):
        self.c, self.u, self.mat, self.mel = c, c.u, mat, c.u.MaterialEditingLibrary

    def node(self, cls, x, y, **props):
        n = self.mel.create_material_expression(self.mat, cls, x, y)
        self.c.require(n is not None, "GRAPH_NODE|%s" % cls)
        for key, value in props.items():
            n.set_editor_property(key, value)
        return n

    def link(self, source, output, target, input_name):
        ok = self.mel.connect_material_expressions(source, output, target, input_name)
        self.c.require(ok, "GRAPH_LINK|%s->%s" % (source.get_name(), target.get_name()))


def _build_master(c, plan, path):
    u, eal, mel = c.u, c.u.EditorAssetLibrary, c.u.MaterialEditingLibrary
    c.require(not eal.does_asset_exist(path), "MASTER_EXISTS|" + path)
    mat = u.AssetToolsHelpers.get_asset_tools().create_asset(path.rsplit("/", 1)[-1], C.DEST,
                                                             u.Material, u.MaterialFactoryNew())
    c.require(mat is not None, "MASTER_CREATE")
    mat.modify()
    mat.set_editor_property("blend_mode", u.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    g = _Graph(c, mat)
    samples = {}
    for i, row in enumerate(plan["textures"]):
        tex = eal.load_asset(row["dest"])
        sample = g.node(u.MaterialExpressionTextureSampleParameter2D, -1300, -500 + i * 220,
                        parameter_name=row["parameter"], texture=tex,
                        sampler_type=getattr(u.MaterialSamplerType, row["sampler"]), group="00 Textures",
                        sort_priority=i)
        samples[row["parameter"]] = sample
    scalars = {}
    for i, name in enumerate(C.SCALAR_PARAMS):
        key = {"DustStrength": "dust_strength", "SootStrength": "soot_strength", "PeelStrength": "peel_strength",
               "Metallic": "metallic", "Specular": "specular"}[name]
        scalars[name] = g.node(u.MaterialExpressionScalarParameter, -1000, 650 + i * 110,
                               parameter_name=name, default_value=float(C.DEFAULTS[key]), group="01 Aging",
                               sort_priority=i)
    custom = g.node(u.MaterialExpressionCustom, -650, -150, description="Iron3 dust soot AO peel aging",
                    code=("float dust=saturate(Mask.r*DustStrength); float soot=saturate(Mask.g*SootStrength); "
                          "float peel=saturate(Mask.a*PeelStrength); float3 c=Dusty*(1-dust*0.35)*(1-soot*0.55); "
                          "return lerp(c,float3(0.18,0.16,0.13),peel);"),
                    output_type=u.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs = []
    for name in ("Dusty", "Mask", "DustStrength", "SootStrength", "PeelStrength"):
        ci = u.CustomInput(); ci.set_editor_property("input_name", name); inputs.append(ci)
    custom.set_editor_property("inputs", inputs)
    g.link(samples["BaseColorDusty"], "RGB", custom, "Dusty")
    g.link(samples["MasksTexture"], "", custom, "Mask")
    for name in ("DustStrength", "SootStrength", "PeelStrength"):
        g.link(scalars[name], "", custom, name)
    switch = g.node(u.MaterialExpressionStaticSwitchParameter, -250, -100, parameter_name="UseClean",
                    default_value=False, group="02 Variant", sort_priority=0)
    g.link(samples["BaseColorClean"], "RGB", switch, "A")
    g.link(custom, "", switch, "B")
    MP = u.MaterialProperty
    for source, output, prop in ((switch, "", MP.MP_BASE_COLOR),
                                 (samples["NormalTexture"], "RGB", MP.MP_NORMAL),
                                 (samples["RoughnessTexture"], "R", MP.MP_ROUGHNESS),
                                 (samples["MasksTexture"], "B", MP.MP_AMBIENT_OCCLUSION),
                                 (scalars["Metallic"], "", MP.MP_METALLIC),
                                 (scalars["Specular"], "", MP.MP_SPECULAR)):
        c.require(mel.connect_material_property(source, output, prop), "GRAPH_PROPERTY|%s" % prop)
    mel.layout_material_expressions(mat)
    mel.recompile_material(mat)
    info = _master_info(u, mat)
    c.require(not C.master_contract_problems(info), "MASTER_READBACK|%s" % C.master_contract_problems(info))
    return mat, info


def _mi_readback(c, mi):
    mel = c.u.MaterialEditingLibrary
    textures = {n: _pkg(mel.get_material_instance_texture_parameter_value(mi, n)) for n in C.TEXTURE_PARAMS}
    scalars = {n: float(mel.get_material_instance_scalar_parameter_value(mi, n)) for n in C.SCALAR_PARAMS}
    switch = bool(mel.get_material_instance_static_switch_parameter_value(mi, "UseClean"))
    return {"parent": _pkg(mi.get_editor_property("parent")), "textures": textures,
            "scalars": scalars, "switches": {"UseClean": switch}}


def run_apply(c, plan, rec, values):
    _guard(c)
    eal, mel = c.u.EditorAssetLibrary, c.u.MaterialEditingLibrary
    for path in plan["imported_packages"]:
        c.require(eal.does_asset_exist(path), "IMPORTED_ASSET_MISSING|" + path)
    mi_path = C.DEST + "/" + C.MI_NAME
    c.require(not eal.does_asset_exist(mi_path), "REFUSE_OVERWRITE|" + mi_path)
    compatible, _ = _master_candidates(c)
    c.require(len(compatible) <= 1, "AMBIGUOUS_COMPATIBLE_MASTERS")
    master_path = compatible[0]["path"] if compatible else C.DEST + "/" + C.MASTER_NAME
    if not compatible:
        c.require(not eal.does_asset_exist(master_path), "REFUSE_OVERWRITE|" + master_path)
    backup = _backup(c, "ChandelierApply", plan["imported_packages"],
                     {"record_run": rec["run"], "master_decision": master_path, "values": values})
    created_now = []
    if compatible:
        master = eal.load_asset(master_path)
        info = _master_info(c.u, master)
        c.require(not C.master_contract_problems(info), "MASTER_DRIFT")
    else:
        master, info = _build_master(c, plan, master_path)
        created_now.append(master_path)
        c.past_write = True
    mi = c.u.AssetToolsHelpers.get_asset_tools().create_asset(C.MI_NAME, C.DEST,
                                                               c.u.MaterialInstanceConstant,
                                                               c.u.MaterialInstanceConstantFactoryNew())
    c.require(mi is not None, "MI_CREATE")
    created_now.append(mi_path)
    c.past_write = True
    mi.modify()
    mel.set_material_instance_parent(mi, master)
    tex_paths = {r["parameter"]: r["dest"] for r in plan["textures"]}
    for name, path in tex_paths.items():
        mel.set_material_instance_texture_parameter_value(mi, name, eal.load_asset(path))
    vals = {"DustStrength": values["dust_strength"], "SootStrength": values["soot_strength"],
            "PeelStrength": values["peel_strength"], "Metallic": values["metallic"], "Specular": values["specular"]}
    for name, value in vals.items():
        mel.set_material_instance_scalar_parameter_value(mi, name, value)
    mel.set_material_instance_static_switch_parameter_value(mi, "UseClean", values["use_clean"])
    mel.update_material_instance(mi)
    got = _mi_readback(c, mi)
    c.require(got["parent"] == master_path and got["textures"] == tex_paths, "MI_READBACK|%s" % got)
    c.require(got["switches"]["UseClean"] == values["use_clean"] and
              all(abs(got["scalars"][k] - v) <= 1e-4 for k, v in vals.items()), "MI_VALUES|%s" % got)
    mesh_rb = {}
    for name in (C.BODY_NAME, C.CHAIN_NAME):
        path = C.DEST + "/" + name
        mesh = eal.load_asset(path)
        mesh.modify()
        slots = list(mesh.get_editor_property("static_materials"))
        c.require(bool(slots), "NO_MATERIAL_SLOTS|" + path)
        for index in range(len(slots)):
            mesh.set_material(index, mi)
        bound = [_pkg(row.get_editor_property("material_interface"))
                 for row in mesh.get_editor_property("static_materials")]
        c.require(bound == [mi_path] * len(bound), "MESH_MATERIAL_READBACK|%s|%s" % (path, bound))
        mesh_rb[name] = bound
    save = set(created_now + [C.DEST + "/" + C.BODY_NAME, C.DEST + "/" + C.CHAIN_NAME])
    dirty = census(c.u)
    c.require(not dirty["maps"] and set(dirty["content"]) == save, "DIRTY_SCOPE|%s|want=%s" % (dirty, sorted(save)))
    for path in sorted(save):
        c.require(eal.save_asset(path, only_if_is_dirty=False), "SAVE|" + path)
    c.require(census(c.u) == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|%s" % census(c.u))
    got2 = _mi_readback(c, eal.load_asset(mi_path))
    c.require(got2 == got, "SAVED_MI_READBACK")
    rec.update({"state": "applied", "apply_run": c.run, "apply_backup": backup, "master": master_path,
                "master_created": master_path in created_now, "created_packages": rec["created_packages"] + created_now,
                "mi": got2, "mesh_materials": mesh_rb})
    _write_json(RECORD, rec)
    c.log("%s_APPLY_OK|run=%s|master=%s|reused=%d|mi=%s|meshes=2|saved=%d|dirty_after=0+0|record=%s"
          % (C.MARK, c.run, master_path, bool(compatible), mi_path, len(save), RECORD))


def run_revert(c, rec):
    _guard(c)
    eal = c.u.EditorAssetLibrary
    ours = set(rec["created_packages"])
    # Foreign references are a hard refusal. References among our own packages are expected.
    for path in ours:
        refs = {_pkg(p) for p in eal.find_package_referencers_for_asset(path, False)}
        c.require(not sorted(refs - ours), "FOREIGN_REFERENCERS|%s|%s" % (path, sorted(refs - ours)))
    _backup(c, "ChandelierRevert", sorted(ours), {"record": rec})
    def deletion_priority(path):
        if path.endswith("/" + C.MI_NAME):
            return 0
        if path.endswith("/" + C.BODY_NAME) or path.endswith("/" + C.CHAIN_NAME):
            return 1
        if path.endswith("/" + C.MASTER_NAME):
            return 2
        return 3  # textures, after their material users
    order = sorted(ours, key=lambda p: (deletion_priority(p), p))
    for path in order:
        c.require(eal.delete_asset(path), "DELETE|" + path)
        c.require(not eal.does_asset_exist(path), "DELETE_READBACK|" + path)
    c.require(census(c.u) == {"content": [], "maps": []}, "DIRTY_AFTER_REVERT|%s" % census(c.u))
    archived = RECORD.replace(".json", ".reverted-%s.json" % c.run)
    os.replace(RECORD, archived)
    c.log("%s_REVERT_OK|run=%s|deleted=%d|dirty_after=0+0|record=%s" % (C.MARK, c.run, len(order), archived))


def main():
    args = json.load(open(ARGS, encoding="utf-8")) if os.path.isfile(ARGS) else {"mode": "DRY"}
    rec = _record()
    try:
        mode, values = C.validate_args(args, rec.get("state") if rec else None)
    except C.PlanError as exc:
        # Import unreal only for the run-stamped failure marker.
        c = Ctx(str(args.get("mode", "DRY")).upper())
        c.fail("ARGS|" + str(exc))
    c = Ctx(mode)
    plan = C.build_plan(PROJECT)
    c.log("%s_START|run=%s|mode=%s" % (C.MARK, c.run, mode))
    try:
        if mode == "DRY":
            run_dry(c, plan, rec)
        elif mode == "IMPORT":
            run_import(c, plan)
        elif mode == "MAT_CHECK":
            run_mat_check(c, plan, rec)
        elif mode == "APPLY":
            run_apply(c, plan, rec, values)
        else:
            run_revert(c, rec)
    except ToolError:
        raise
    except Exception as exc:  # noqa: BLE001 - preserve a run-id failure marker for API surprises
        c.fail("UNEXPECTED|%s|%s" % (type(exc).__name__, exc))


if __name__ != "__p80_offline_harness__":
    main()
