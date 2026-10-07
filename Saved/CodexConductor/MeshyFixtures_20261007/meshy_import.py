"""Meshy fixtures IMPORT: DRY / APPLY (one fixture per call) / REVERT. Editor only, via meshy_import_run.py.

Creates, CREATE-ONLY, under /Game/InfinityStage/Lighting/Fixtures/ (the conductor's 7 Oct destination; the MeshyClean
README's Bulbs/ + RigAtmos/Lanterns destinations are superseded by that brief):
  Meshes/SM_<13 assets>, Textures/T_<asset>_{BaseColor,Normal,Roughness,Metallic}, Materials/MI_<asset>_{Glow|Lens,
  Metal[,Glass]}, and three new masters Materials/M_Fixture_{Glow,Lit,Glass} (built in the first batch, seeded with
  that batch's textures so every texture parameter default has a compatible sampler type).
Slot 0 of every mesh is an emissive MI of M_Fixture_Glow (unlit, Emissive = Colour * Intensity, NO per-instance
custom data), so a dead bulb glows faintly and the Bulb Body driver can scale "Intensity" (InfinityStageBulbBody.h:46).

MODES (args file meshy_import_args.json):
  {"mode": "DRY"}                                              read-only census + plan; prints what is left
  {"mode": "APPLY", "confirm": "APPLY MESHYIMPORT", "batch": "next"|"<asset>"}   ONE fixture per call (memory
        ue58-bulk-import-oom-crash: 3x4096^2 + 213 MIs in one call killed the editor 6 Oct). Each call: import 4
        textures + 1 FBX, diff the destination folder, delete never-saved strays, gate (LODs / bounds min+max per axis
        / slot order / Nanite off / no LOD-split assets), configure textures (sRGB, compression, max size), build the
        masters if absent, create + read back the MIs, assign + read back slots, save ONLY the new packages, require
        the dirty census unchanged, collect garbage. Run it 13 times (or until MESHYIMPORT_APPLY_OK).
  {"mode": "REVERT", "confirm": "REVERT MESHYIMPORT"}          deletes only what the record created, only if nothing
        outside that set references it and no meshy_swap record is active.
Markers: MESHYIMPORT_DRY_OK | MESHYIMPORT_BATCH_OK | MESHYIMPORT_APPLY_OK (all 13) | MESHYIMPORT_REVERT_OK, each
|run=<id>|...; any stop MESHYIMPORT_STOPPED|run=<id>|...|NOTHING SAVED (or |SAVED=<n> if a save had begun).

Proof tiers (AGENTS.md), per claim:
* declaration-proven: the import gates and settings are the MeshyClean README's (DerivedAssets/Lighting/MeshyClean/
  README.md:24-46); M_UP_TubeEmissive's custom-data multiply makes it unfit for ISM housings (meshy_common.py header).
* measured (by other runs, cited): AssetImportTask + FbxImportUI(import_materials/textures False) gave 0 strays on
  122 meshes (memory ue58-fbx-import-traps, 4 Oct); Interchange ignores FbxImportUI and splits *_LOD0/1 children
  unless an FBX LodGroup exists (same memory, 1 Oct); the LodGroup export was re-imported in Blender
  (cleanup_report.json lodgroup_readback); MaterialEditingLibrary create/connect/recompile + MI parent/scalar/vector
  setters with read-back ran live in underpass_tubes_apply.py:55-100 and fb_workflow.py:281-564.
* inferred (the first APPLY's read-back confirms or stops on each): StaticMesh.get_num_lods(), get_bounding_box(),
  nanite_settings.enabled, Texture.max_texture_size and TC_GRAYSCALE + SAMPLERTYPE_LINEAR_GRAYSCALE compiling
  together (memory ue58-python-material-authoring says this pairing is required); EditorAssetLibrary.delete_asset on a
  never-saved package; find_package_referencers_for_asset in REVERT; the beam-sign is only as good as the bounds gate
  (meshy_common.lens_sign_provable: true for all six lanterns, 1950s by 0.54 cm), and UV V orientation is NOT gated
  (README gate 5 needs a look at a capture against contact_sheet.png).
"""
from __future__ import annotations

import copy
import datetime
import json
import os
import runpy
import types

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # offline harness import
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))
COMMON_PATH = os.path.join(HERE, "meshy_common.py")
RECORD_PATH = os.path.join(HERE, "meshy_import_record.json")
MARK = "MESHYIMPORT"
CONFIRM_TOKEN = "MESHYIMPORT"
VALID_MODES = ("DRY", "APPLY", "REVERT")
SWAP_RECORD_GLOB_PREFIX = "meshy_swap_record_"
DEFAULTS = {
    "batch": "next",
    "bulb_glow": {"colour": [1.0, 0.62, 0.30], "intensity": 1.5},    # lighting_scores BODY_DIM_INTENSITY = 1.5
    "lens_glow": {"colour": [1.0, 0.85, 0.65], "intensity": 0.6},
    "glass": {"opacity": 0.22, "roughness": 0.06, "tint": [1.0, 1.0, 1.0]},
    "max_texture_size": {"bulb": 1024, "housing": 2048},
    "ack_records": [],
}


def load_common():
    return types.SimpleNamespace(**runpy.run_path(COMMON_PATH, run_name="_meshy_common_for_import"))


C = None   # set in main()/tests: never a UE object, only the pure namespace


def require(condition, message):
    C.require(condition, message)


def check_args(raw, common):
    raw = dict(raw or {})
    unknown = sorted(set(raw) - set(DEFAULTS) - {"mode", "confirm"})
    common.require(not unknown, "ARGS_UNKNOWN|%s" % unknown)
    mode = str(raw.get("mode", "DRY")).upper()
    common.require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    if mode in ("APPLY", "REVERT"):
        common.require(raw.get("confirm") == "%s %s" % (mode, CONFIRM_TOKEN),
                       "CONFIRM_MISSING|need='%s %s'" % (mode, CONFIRM_TOKEN))
    out = copy.deepcopy(DEFAULTS)
    out.update({k: copy.deepcopy(v) for k, v in raw.items() if k in DEFAULTS})
    out["mode"], out["confirm"] = mode, raw.get("confirm")
    common.require(out["batch"] == "next" or out["batch"] in common.IMPORT_ORDER, "BATCH_INVALID|%s" % out["batch"])
    for key in ("bulb_glow", "lens_glow"):
        g = out[key]
        common.require(isinstance(g, dict) and len(g.get("colour", [])) == 3
                       and all(0.0 <= float(c) <= 1.0 for c in g["colour"]) and 0.0 <= float(g["intensity"]) <= 50.0,
                       "GLOW_ARGS|" + key)
    common.require(0.0 < float(out["glass"]["opacity"]) <= 1.0, "GLASS_OPACITY")
    for cls in ("bulb", "housing"):
        common.require(out["max_texture_size"][cls] in (256, 512, 1024, 2048, 4096), "MAX_TEXTURE_SIZE|" + cls)
    common.require(isinstance(out["ack_records"], list), "ACK_RECORDS_INVALID")
    return out


def next_batch(record, order):
    done = set((record or {}).get("fixtures", {}))
    return next((name for name in order if name not in done), None)


def master_specs(common):
    """What each master must contain (read back after build)."""
    return {
        common.MASTERS["glow"]: {"shading": "MSM_UNLIT", "blend": None, "params": {"Colour": "vector", "Intensity": "scalar"},
                                 "terminals": ("MP_EMISSIVE_COLOR",)},
        common.MASTERS["lit"]: {"shading": None, "blend": None, "params": {k: "texture" for k in common.TEXTURE_KINDS},
                                "terminals": ("MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS", "MP_METALLIC")},
        common.MASTERS["glass"]: {"shading": None, "blend": "BLEND_TRANSLUCENT",
                                  "params": {"BaseColor": "texture", "Tint": "vector", "Opacity": "scalar",
                                             "Roughness": "scalar"},
                                  "terminals": ("MP_BASE_COLOR", "MP_OPACITY", "MP_ROUGHNESS")},
    }


def mi_plan(fixture, args, common):
    """{mi path: {"parent", "vectors", "scalars", "textures"}} for one fixture, slot order = fixture slot order."""
    name, out = fixture["name"], {}
    tex = fixture["texture_assets"]
    glow = args["bulb_glow"] if fixture["class"] == "bulb" else args["lens_glow"]
    glow_key = "Glow" if fixture["class"] == "bulb" else "Lens"
    out[fixture["mis"][glow_key]] = {"parent": common.MASTERS["glow"], "vectors": {"Colour": list(glow["colour"])},
                                     "scalars": {"Intensity": float(glow["intensity"])}, "textures": {}}
    out[fixture["mis"]["Metal"]] = {"parent": common.MASTERS["lit"], "vectors": {}, "scalars": {},
                                    "textures": {k: tex[k] for k in common.TEXTURE_KINDS}}
    if "Glass" in fixture["mis"]:
        out[fixture["mis"]["Glass"]] = {"parent": common.MASTERS["glass"], "vectors": {"Tint": list(args["glass"]["tint"])},
                                        "scalars": {"Opacity": float(args["glass"]["opacity"]),
                                                    "Roughness": float(args["glass"]["roughness"])},
                                        "textures": {"BaseColor": tex["BaseColor"]}}
    slots = [fixture["mis"][glow_key], fixture["mis"]["Metal"]] + ([fixture["mis"]["Glass"]] if "Glass" in fixture["mis"] else [])
    common.require(len(slots) == len(fixture["slots"]), "MI_SLOT_COUNT|" + name)
    return out, slots


def texture_settings(kind):
    """(srgb, compression enum name): README import settings (Normal = normal map, Roughness/Metallic linear)."""
    return {"BaseColor": (True, "TC_DEFAULT"), "Normal": (False, "TC_NORMALMAP"),
            "Roughness": (False, "TC_GRAYSCALE"), "Metallic": (False, "TC_GRAYSCALE")}[kind]


# --------------------------------------------------------------------------------------------------------------
# Unreal runtime (never executed offline). No UE object is kept in a global.
# --------------------------------------------------------------------------------------------------------------
def _log(text):
    unreal.log(text)


def _aid(value):
    if value is None:
        return None
    if hasattr(value, "get_path_name"):
        return str(value.get_path_name()).split(".", 1)[0]
    return str(value).split(".", 1)[0]


def _census():
    return {"content": sorted(_aid(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(_aid(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _ctx():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    project = os.path.normcase(os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())))
    return {"project": project, "project_ok": project.rstrip("\\/") == os.path.normcase(os.path.normpath("E:/PussStage")),
            "pie": editor.get_game_world() is not None, "census": _census()}


def _package_file(path):
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    return os.path.join(content, path[len("/Game/"):].replace("/", os.sep) + ".uasset")


def _list(folder):
    eal = unreal.EditorAssetLibrary
    if not eal.does_directory_exist(folder):
        return set()
    return {_aid(p) for p in eal.list_assets(folder, recursive=True, include_folder=False)}


def _same(actual, expected):
    if isinstance(expected, float):
        return abs(float(actual) - expected) <= 1.0e-5 * max(1.0, abs(expected))
    if isinstance(expected, bool):
        return bool(actual) is expected
    return str(actual) == str(expected) or C.enum_name(actual) == C.enum_name(expected)


def _set_readback(obj, name, value, label):
    obj.modify()
    obj.set_editor_property(name, value)
    got = obj.get_editor_property(name)
    require(_same(got, value), "PROPERTY_READBACK|%s.%s|got=%s|want=%s" % (label, name, got, value))


def _fbx_options(housing):
    options = unreal.FbxImportUI()
    for name, value in (("import_mesh", True), ("import_as_skeletal", False), ("import_materials", False),
                        ("import_textures", False), ("import_animations", False)):
        options.set_editor_property(name, value)
    static = options.get_editor_property("static_mesh_import_data")
    static.set_editor_property("combine_meshes", False)
    if housing:
        static.set_editor_property("import_mesh_lods", True)
    return options


def _import(files, dest, options=None):
    tasks = []
    for path in files:
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", path)
        task.set_editor_property("destination_path", dest)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", False)
        task.set_editor_property("save", False)
        if options is not None:
            task.set_editor_property("options", options)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    return sorted({_aid(p) for t in tasks for p in t.get_editor_property("imported_object_paths")})


def _new_asset(path, cls, factory):
    require(not unreal.EditorAssetLibrary.does_asset_exist(path), "TARGET_EXISTS|" + path)
    folder, name = path.rsplit("/", 1)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, cls, factory)
    require(asset is not None and isinstance(asset, cls), "CREATE_FAILED|" + path)
    return asset


def _configure_texture(path, kind, max_size):
    tex = unreal.EditorAssetLibrary.load_asset(path)
    require(isinstance(tex, unreal.Texture2D), "TEXTURE_CLASS|" + path)
    srgb, compression = texture_settings(kind)
    _set_readback(tex, "srgb", srgb, path)
    _set_readback(tex, "compression_settings", getattr(unreal.TextureCompressionSettings, compression), path)
    _set_readback(tex, "max_texture_size", int(max_size), path)
    return {"srgb": srgb, "compression": compression, "max_texture_size": int(max_size)}


def _node(material, cls, x, y, **props):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, cls, x, y)
    require(node is not None, "NODE_CREATE|%s" % cls)
    for name, value in props.items():
        node.set_editor_property(name, value)
        require(_same(node.get_editor_property(name), value) or name == "texture",
                "NODE_PROPERTY|%s.%s" % (node.get_name(), name))
    return node


def _link(a, out, b, pin):
    require(unreal.MaterialEditingLibrary.connect_material_expressions(a, out, b, pin),
            "CONNECT|%s.%s>%s.%s" % (a.get_name(), out, b.get_name(), pin))


def _terminal(material, node, out, prop_name, wired):
    prop = getattr(unreal.MaterialProperty, prop_name)
    require(unreal.MaterialEditingLibrary.connect_material_property(node, out, prop), "TERMINAL|" + prop_name)
    wired[prop_name] = node.get_name()


def _finish_master(material, wired, spec, path):
    mel = unreal.MaterialEditingLibrary
    result = mel.recompile_material(material)
    errors = [str(e) for e in (result or [])] if isinstance(result, (list, tuple)) else []
    require(not errors, "MASTER_COMPILE_ERRORS|%s|%s" % (path, errors))
    for prop_name in spec["terminals"]:
        node = mel.get_material_property_input_node(material, getattr(unreal.MaterialProperty, prop_name))
        require(node is not None and node.get_name() == wired[prop_name], "MASTER_TERMINAL_READBACK|%s|%s" % (path, prop_name))
    require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), "SAVE_FAILED|" + path)
    return {"terminals": dict(wired), "compile_errors_returned": errors}


def _build_masters(fixture, needed):
    """CREATE-ONLY. needed: master paths to create now. Texture defaults come from this fixture's own textures."""
    made = {}
    specs = master_specs(C)
    tex = {k: unreal.EditorAssetLibrary.load_asset(fixture["texture_assets"][k]) for k in C.TEXTURE_KINDS}
    for path in needed:
        material = _new_asset(path, unreal.Material, unreal.MaterialFactoryNew())
        _set_readback(material, "used_with_instanced_static_meshes", True, path)
        wired = {}
        if path == C.MASTERS["glow"]:
            _set_readback(material, "shading_model", unreal.MaterialShadingModel.MSM_UNLIT, path)
            col = _node(material, unreal.MaterialExpressionVectorParameter, -600, 0, parameter_name="Colour",
                        default_value=unreal.LinearColor(1.0, 0.62, 0.30, 1.0))
            inten = _node(material, unreal.MaterialExpressionScalarParameter, -600, 200, parameter_name="Intensity",
                          default_value=1.0)
            mul = _node(material, unreal.MaterialExpressionMultiply, -300, 100)
            _link(col, "", mul, "A")
            _link(inten, "", mul, "B")
            _terminal(material, mul, "", "MP_EMISSIVE_COLOR", wired)
        elif path == C.MASTERS["lit"]:
            samplers = {"BaseColor": "SAMPLERTYPE_COLOR", "Normal": "SAMPLERTYPE_NORMAL",
                        "Roughness": "SAMPLERTYPE_LINEAR_GRAYSCALE", "Metallic": "SAMPLERTYPE_LINEAR_GRAYSCALE"}
            nodes = {}
            for i, kind in enumerate(C.TEXTURE_KINDS):
                nodes[kind] = _node(material, unreal.MaterialExpressionTextureSampleParameter2D, -700, -300 + 260 * i,
                                    parameter_name=kind, texture=tex[kind],
                                    sampler_type=getattr(unreal.MaterialSamplerType, samplers[kind]))
            _terminal(material, nodes["BaseColor"], "RGB", "MP_BASE_COLOR", wired)
            _terminal(material, nodes["Normal"], "RGB", "MP_NORMAL", wired)
            _terminal(material, nodes["Roughness"], "R", "MP_ROUGHNESS", wired)
            _terminal(material, nodes["Metallic"], "R", "MP_METALLIC", wired)
        elif path == C.MASTERS["glass"]:
            _set_readback(material, "blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT, path)
            base = _node(material, unreal.MaterialExpressionTextureSampleParameter2D, -700, -200,
                         parameter_name="BaseColor", texture=tex["BaseColor"],
                         sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
            tint = _node(material, unreal.MaterialExpressionVectorParameter, -700, 100, parameter_name="Tint",
                         default_value=unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
            mul = _node(material, unreal.MaterialExpressionMultiply, -400, -100)
            _link(base, "RGB", mul, "A")
            _link(tint, "", mul, "B")
            opacity = _node(material, unreal.MaterialExpressionScalarParameter, -400, 150, parameter_name="Opacity",
                            default_value=0.22)
            rough = _node(material, unreal.MaterialExpressionScalarParameter, -400, 300, parameter_name="Roughness",
                          default_value=0.06)
            _terminal(material, mul, "", "MP_BASE_COLOR", wired)
            _terminal(material, opacity, "", "MP_OPACITY", wired)
            _terminal(material, rough, "", "MP_ROUGHNESS", wired)
        made[path] = _finish_master(material, wired, specs[path], path)
    return made


def _create_mi(path, spec):
    mel = unreal.MaterialEditingLibrary
    mi = _new_asset(path, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    parent = unreal.EditorAssetLibrary.load_asset(spec["parent"])
    require(parent is not None, "MI_PARENT_MISSING|" + spec["parent"])
    mi.modify()
    mel.set_material_instance_parent(mi, parent)
    require(_aid(mi.get_editor_property("parent")) == spec["parent"], "MI_PARENT_READBACK|" + path)
    got = {"vectors": {}, "scalars": {}, "textures": {}}
    for name, rgb in spec["vectors"].items():
        mel.set_material_instance_vector_parameter_value(mi, name, unreal.LinearColor(*(list(rgb) + [1.0])))
        value = mel.get_material_instance_vector_parameter_value(mi, name)
        got["vectors"][name] = [value.r, value.g, value.b]
        require(all(abs(a - b) <= 1.0e-4 for a, b in zip(got["vectors"][name], rgb)), "MI_VECTOR_READBACK|%s|%s" % (path, name))
    for name, value in spec["scalars"].items():
        mel.set_material_instance_scalar_parameter_value(mi, name, float(value))   # return value unreliable: read back
        got["scalars"][name] = float(mel.get_material_instance_scalar_parameter_value(mi, name))
        require(abs(got["scalars"][name] - value) <= 1.0e-4, "MI_SCALAR_READBACK|%s|%s" % (path, name))
    for name, texture_path in spec["textures"].items():
        mel.set_material_instance_texture_parameter_value(mi, name, unreal.EditorAssetLibrary.load_asset(texture_path))
        got["textures"][name] = _aid(mel.get_material_instance_texture_parameter_value(mi, name))
        require(got["textures"][name] == texture_path, "MI_TEXTURE_READBACK|%s|%s" % (path, name))
    mel.update_material_instance(mi)
    return got


def _mesh_readback(path):
    mesh = unreal.EditorAssetLibrary.load_asset(path)
    if mesh is None:
        return {"class": None}
    box = mesh.get_bounding_box()
    nanite = mesh.get_editor_property("nanite_settings")
    return {"class": type(mesh).__name__, "num_lods": int(mesh.get_num_lods()),
            "bounds_min": [float(box.min.x), float(box.min.y), float(box.min.z)],
            "bounds_max": [float(box.max.x), float(box.max.y), float(box.max.z)],
            "slot_names": [str(s.get_editor_property("material_slot_name"))
                           for s in mesh.get_editor_property("static_materials")],
            "slot_materials": [_aid(s.get_editor_property("material_interface"))
                               for s in mesh.get_editor_property("static_materials")],
            "nanite_enabled": bool(nanite.get_editor_property("enabled"))}


def _nanite_off(path):
    mesh = unreal.EditorAssetLibrary.load_asset(path)
    nanite = mesh.get_editor_property("nanite_settings")
    if bool(nanite.get_editor_property("enabled")):
        nanite.set_editor_property("enabled", False)
        mesh.modify()
        mesh.set_editor_property("nanite_settings", nanite)
    require(not bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")), "NANITE_READBACK|" + path)


def _assign_slots(path, slot_mis):
    mesh = unreal.EditorAssetLibrary.load_asset(path)
    mesh.modify()
    for index, mi in enumerate(slot_mis):
        mesh.set_material(index, unreal.EditorAssetLibrary.load_asset(mi))
    got = [_aid(s.get_editor_property("material_interface")) for s in mesh.get_editor_property("static_materials")]
    require(got == list(slot_mis), "SLOT_MATERIAL_READBACK|%s|got=%s" % (path, got))
    return got


def _delete_unsaved(paths):
    deleted, kept = [], []
    for path in paths:
        if os.path.exists(_package_file(path)):
            kept.append(path)
            continue
        if unreal.EditorAssetLibrary.does_asset_exist(path) and unreal.EditorAssetLibrary.delete_asset(path):
            deleted.append(path)
        else:
            kept.append(path)
    return deleted, kept


def _read_record():
    if not os.path.isfile(RECORD_PATH):
        return None
    with open(RECORD_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _write_record(record, exclusive=False):
    with open(RECORD_PATH, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def _report(mode, run, report):
    path = os.path.join(HERE, "meshy_import_report_%s_%s.json" % (mode, run))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, default=str)
    return path


def _active_swap_records():
    out = []
    for name in sorted(os.listdir(HERE)):
        if name.startswith(SWAP_RECORD_GLOB_PREFIX) and name.endswith(".json"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                status = str(json.load(handle).get("status", ""))
            if status not in ("reverted", "failed_rolled_back_in_memory"):
                out.append(name)
    return out


def _import_one(args, table, record, run, report):
    name = args["batch"] if args["batch"] != "next" else next_batch(record, C.IMPORT_ORDER)
    require(name is not None, "NOTHING_LEFT_TO_IMPORT")
    require(name not in (record or {}).get("fixtures", {}), "ALREADY_IMPORTED|" + name)
    fixture = table[name]
    mis, slot_mis = mi_plan(fixture, args, C)
    masters_needed = [p for p in C.MASTERS.values() if not unreal.EditorAssetLibrary.does_asset_exist(p)]
    if "Glass" not in fixture["mis"]:
        masters_needed = [p for p in masters_needed if p != C.MASTERS["glass"]]
    for parent in {spec["parent"] for spec in mis.values()}:
        require(parent in masters_needed or unreal.EditorAssetLibrary.does_asset_exist(parent), "MASTER_ABSENT|" + parent)
    planned = C.planned_assets(fixture) + masters_needed
    clash = [p for p in planned if unreal.EditorAssetLibrary.does_asset_exist(p)]
    require(not clash, "TARGET_EXISTS|%s" % clash)
    report["batch"] = name
    census_before = _census()
    before = _list(C.DEST_ROOT)
    created = []
    batch = {"run": run, "planned": planned}
    if record is None:
        record = {"schema_version": 1, "status": "importing", "first_run": run, "dest_root": C.DEST_ROOT,
                  "args": args, "fixtures": {}, "masters": {}, "created_all": []}
        _write_record(record, exclusive=True)
        _log("%s_RECORD_WRITTEN|run=%s|path=%s" % (MARK, run, RECORD_PATH))
    saved = []
    try:
        imported_tex = _import([fixture["textures"][k] for k in C.TEXTURE_KINDS], C.TEX_DIR)
        imported_mesh = _import([fixture["fbx"]], C.MESH_DIR, _fbx_options(fixture["class"] == "housing"))
        after = _list(C.DEST_ROOT)
        new = sorted(after - before)
        created = list(new)
        expected = sorted([fixture["mesh"]] + [fixture["texture_assets"][k] for k in C.TEXTURE_KINDS])
        strays = sorted(set(new) - set(expected))
        missing = sorted(set(expected) - set(new))
        batch.update({"imported": sorted(imported_tex + imported_mesh), "new_assets": new, "strays": strays})
        outside = sorted(set(_census()["content"]) - set(census_before["content"]) - set(after))
        require(not outside, "IMPORT_DIRTIED_OUTSIDE_DEST|%s" % outside)
        require(not missing, "IMPORT_MISSING|%s" % missing)
        lod_split = [p for p in strays if p.rsplit("/", 1)[-1].startswith(name + "_LOD")]
        deleted, kept = _delete_unsaved(strays)
        batch.update({"strays_deleted": deleted, "strays_kept": kept})
        require(not kept, "STRAYS_NOT_DELETED|%s" % kept)
        created = [p for p in created if p not in deleted]
        _nanite_off(fixture["mesh"])
        rb = _mesh_readback(fixture["mesh"])
        rb["new_assets"] = new
        fails = C.check_import_readback(fixture, rb) + (["LOD_SPLIT|%s" % lod_split] if lod_split else [])
        batch["readback"] = rb
        require(not fails, "IMPORT_GATES|%s|%s" % (name, ";".join(fails)))
        batch["textures"] = {k: _configure_texture(fixture["texture_assets"][k], k,
                                                   args["max_texture_size"][fixture["class"]])
                             for k in C.TEXTURE_KINDS}
        # masters (each saved inside _finish_master: listed as created + saved immediately)
        built = _build_masters(fixture, masters_needed)
        created += list(built)
        saved += list(built)
        batch["masters_built"] = built
        batch["mis"] = {}
        for path, spec in sorted(mis.items()):
            batch["mis"][path] = _create_mi(path, spec)
            created.append(path)
        batch["slots"] = _assign_slots(fixture["mesh"], slot_mis)
        final = _mesh_readback(fixture["mesh"])
        final["new_assets"] = new
        fails = C.check_import_readback(fixture, final)
        require(not fails and final["slot_materials"] == slot_mis, "FINAL_READBACK|%s|%s" % (name, ";".join(fails)))
        for path in sorted(set(created) - set(saved)):
            require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), "SAVE_FAILED|" + path)
            saved.append(path)
        census_after = _census()
        require(census_after == census_before, "CENSUS_CHANGED|before=%s|after=%s" % (C.canonical(census_before),
                                                                                    C.canonical(census_after)))
    except Exception:
        if not saved:
            deleted, kept = _delete_unsaved(sorted(set(created)))
            report["rolled_back_unsaved"] = {"deleted": deleted, "kept": kept}
        else:
            batch["status"] = "failed_after_partial_save"
            batch["saved"] = saved
            record.setdefault("failed_batches", []).append(batch)
            record["created_all"] = sorted(set(record["created_all"]) | set(saved))
            _write_record(record)
        report["saved_count"] = len(saved)
        raise
    batch.update({"status": "saved_readback_verified", "created": sorted(created), "saved": sorted(saved)})
    record["fixtures"][name] = batch
    record["masters"].update(batch.get("masters_built", {}))
    record["created_all"] = sorted(set(record["created_all"]) | set(created))
    left = next_batch(record, C.IMPORT_ORDER)
    if left is None:
        record["status"] = "saved_readback_verified"
    _write_record(record)
    unreal.SystemLibrary.collect_garbage()
    report.update({"ok": True, "asset": name, "created": sorted(created), "remaining": left})
    rb = batch["readback"]
    _log("%s_BATCH_OK|run=%s|asset=%s|lods=%d|bounds_ok=1|slots=%s|strays_deleted=%d|saved=%d|remaining=%s|report=%s"
         % (MARK, run, name, rb["num_lods"], len(slot_mis), len(batch["strays_deleted"]), len(saved), left,
            _report("APPLY", run, report)))
    if left is None:
        _log("%s_APPLY_OK|run=%s|assets=%d|created=%d|record=%s" % (MARK, run, len(record["fixtures"]),
                                                                    len(record["created_all"]), RECORD_PATH))
    return report


def _revert(record, run, report):
    require(record is not None, "REVERT_RECORD_ABSENT|" + RECORD_PATH)
    active = _active_swap_records()
    require(not active, "SWAP_RECORDS_ACTIVE|%s" % active)
    created = set(record["created_all"])
    for batch in record["fixtures"].values():
        created |= set(batch.get("created", []))
    order = sorted(created, key=lambda p: (0 if "/Meshes/" in p else 1 if "/MI_" in p else 2 if "/M_Fixture_" in p else 3, p))
    external = {}
    for path in order:
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            continue
        refs = [_aid(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)]
        outside = sorted(set(refs) - created)
        if outside:
            external[path] = outside
    require(not external, "REFERENCED_FROM_OUTSIDE|%s" % C.canonical(external)[:2000])
    census_before = _census()
    deleted = []
    for path in order:
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            require(unreal.EditorAssetLibrary.delete_asset(path), "DELETE_FAILED|" + path)
            deleted.append(path)
        require(not unreal.EditorAssetLibrary.does_asset_exist(path), "DELETE_READBACK|" + path)
    require(_census() == census_before, "REVERT_CENSUS_CHANGED")
    record["status"] = "reverted"
    record["reverted_run"] = run
    _write_record(record)
    archived = RECORD_PATH + ".reverted-" + run
    os.rename(RECORD_PATH, archived)
    report.update({"ok": True, "deleted": deleted, "archived": archived})
    _log("%s_REVERT_OK|run=%s|deleted=%d|archived=%s|report=%s" % (MARK, run, len(deleted), archived,
                                                                   _report("REVERT", run, report)))
    return report


def _run(args):
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report = {"ok": False, "mode": args["mode"], "run": run, "args": args}
    try:
        table = C.load_fixture_table()
        ctx = _ctx()
        report["context"] = ctx
        require(ctx["project_ok"], "WRONG_PROJECT|" + ctx["project"])
        require(not ctx["pie"], "PIE_OR_SIE_ACTIVE")
        record = _read_record()
        if args["mode"] == "DRY":
            status = {}
            for name in C.IMPORT_ORDER:
                exists = [p for p in C.planned_assets(table[name]) if unreal.EditorAssetLibrary.does_asset_exist(p)]
                status[name] = {"recorded": name in (record or {}).get("fixtures", {}), "existing": exists,
                                "lens_sign_provable": C.lens_sign_provable(table[name]) if table[name]["class"] == "housing" else None}
            unrecorded = {n: s["existing"] for n, s in status.items() if s["existing"] and not s["recorded"]}
            masters = {p: unreal.EditorAssetLibrary.does_asset_exist(p) for p in C.MASTERS.values()}
            require(_census() == ctx["census"], "DRY_CENSUS_CHANGED")
            report.update({"ok": not unrecorded, "status": status, "masters_exist": masters,
                           "unrecorded_existing": unrecorded, "next": next_batch(record, C.IMPORT_ORDER),
                           "record": RECORD_PATH if record else None, "mutated": False})
            path = _report("DRY", run, report)
            require(not unrecorded, "UNRECORDED_TARGETS_EXIST|%s|report=%s" % (C.canonical(unrecorded)[:1500], path))
            _log("%s_DRY_OK|run=%s|done=%d|next=%s|masters=%s|census_dirty=%d|mutated=0|report=%s"
                 % (MARK, run, len((record or {}).get("fixtures", {})), report["next"],
                    sum(masters.values()), len(ctx["census"]["content"]) + len(ctx["census"]["maps"]), path))
            return report
        if args["mode"] == "APPLY":
            if record is not None:
                require(record.get("status") == "importing", "RECORD_STATUS|%s" % record.get("status"))
            return _import_one(args, table, record, run, report)
        return _revert(record, run, report)
    except Exception as error:  # noqa: BLE001 - one report + marker per stop
        report["error"] = "%s: %s" % (type(error).__name__, error)
        path = _report(args["mode"], run, report)
        unreal.log_error("%s_STOPPED|run=%s|mode=%s|%s|%s|report=%s"
                         % (MARK, run, args["mode"], report["error"][:1500],
                            "SAVED=%d" % report["saved_count"] if report.get("saved_count") else "NOTHING SAVED", path))
        raise


def main():
    global C
    C = load_common()
    require(unreal is not None, "UNREAL_REQUIRED")
    try:
        args = check_args(globals().get("MESHYIMPORT_ARGS"), C)
    except Exception as error:  # noqa: BLE001
        unreal.log_error("%s_STOPPED|run=none|ARGS|%s: %s|NOTHING SAVED" % (MARK, type(error).__name__, error))
        raise
    return _run(args)


if unreal is not None:
    main()
