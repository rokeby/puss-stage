"""P1 Shore MetaHuman outfit guard: underwear colour plus optional shirt hiding.

Written OFFLINE 8 Oct 2026; not run in Unreal. It targets only the six placed `<id> Clam` actors in the vertical-slice
map. DRY is read-only. APPLY requires `APPLY P1OUTFIT`; REVERT requires `REVERT P1OUTFIT` and restores the exact
override-material arrays recorded by APPLY. Both write modes require an empty dirty-package census, back up the map
to Backups/PreP1MetaOutfit-<run>, save only named packages, read back, and emit a run-id marker.

Safety boundary: optimized MetaHuman body faces are removed under the DefaultGarment shirt. Therefore `hide_shirt`
defaults false and is refused unless `accept_missing_torso` is explicit. The tool can make shirt slots invisible, but
cannot invent the missing torso. Loincloth colour is safe: all material slots whose resolved material path contains
`_Short` are replaced by a simple rough coloured material instance; `_Shirt` slots are otherwise preserved.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None


PROJECT = "E:/PussStage/"
HERE = PROJECT + "Saved/CodexConductor/P1MetaFabric_20261008/"
ARGS = HERE + "p1_metahuman_outfit_args.json"
RECORD = HERE + "p1_metahuman_outfit_record.json"
DRY_OUT = HERE + "p1_metahuman_outfit_dry.json"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = PROJECT + "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
MAT_DIR = "/Game/Metahuman/ShoreCast_20260910/P1Outfit"
FIGURES = ("Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore05_M53", "Shore06_F25")
CONFIRM = "P1OUTFIT"
MODES = ("DRY", "APPLY", "REVERT")


class OutfitError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise OutfitError(message)


def path_of(obj):
    if obj is None:
        return None
    return str(obj.get_path_name()).split(".")[0]


def classify_material(path):
    """Pure slot classifier. Unknown is a refusal, not something to hide."""
    p = (path or "").lower()
    if "defaultgarment" in p and "_short" in p:
        return "short"
    if "defaultgarment" in p and "_shirt" in p:
        return "shirt"
    return "unknown"


def asset_names(version):
    suffix = "_v%d" % int(version)
    return {"loin_master": MAT_DIR + "/M_P1_Loincloth" + suffix,
            "loin_mi": MAT_DIR + "/MI_P1_Loincloth" + suffix,
            "invisible": MAT_DIR + "/M_P1_OutfitInvisible" + suffix}


def validate_args(args, record_exists=False):
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in MODES, "MODE|" + mode)
    if mode in ("APPLY", "REVERT"):
        require(args.get("confirm") == "%s %s" % (mode, CONFIRM),
                "CONFIRM_MISSING|want '%s %s'" % (mode, CONFIRM))
    figs = list(args.get("figures") or FIGURES)
    require(figs and len(set(figs)) == len(figs) and set(figs) <= set(FIGURES), "FIGURES|%r" % figs)
    version = args.get("asset_version", 1)
    require(isinstance(version, int) and not isinstance(version, bool) and 1 <= version <= 99, "VERSION|%r" % version)
    colour = args.get("loincloth_color", [0.16, 0.095, 0.055, 1.0])
    require(isinstance(colour, list) and len(colour) == 4 and
            all(isinstance(x, (int, float)) and 0.0 <= x <= 1.0 for x in colour), "COLOUR|%r" % colour)
    rough = args.get("roughness", 0.86)
    require(isinstance(rough, (int, float)) and not isinstance(rough, bool) and 0.3 <= rough <= 1.0,
            "ROUGHNESS|%r" % rough)
    hide = args.get("hide_shirt", False)
    require(isinstance(hide, bool), "HIDE_SHIRT|bool required")
    if hide:
        require(args.get("accept_missing_torso") is True,
                "MISSING_TORSO|optimized Body has no torso under shirt; set accept_missing_torso=true only after review")
    if mode == "APPLY":
        require(not record_exists, "ALREADY_APPLIED|REVERT first")
    if mode == "REVERT":
        require(record_exists, "NO_RECORD")
    return {"mode": mode, "figures": figs, "asset_version": version, "loincloth_color": [float(x) for x in colour],
            "roughness": float(rough), "hide_shirt": hide,
            "accept_missing_torso": bool(args.get("accept_missing_torso", False))}


def plan_overrides(resolved_paths, loin_path, invisible_path, hide_shirt):
    roles = [classify_material(p) for p in resolved_paths]
    require("short" in roles and "shirt" in roles, "OUTFIT_SLOTS|need DefaultGarment Short and Shirt; got %r" % roles)
    require("unknown" not in roles, "OUTFIT_SLOT_UNKNOWN|%r" % [p for p, r in zip(resolved_paths, roles) if r == "unknown"])
    target = []
    for original, role in zip(resolved_paths, roles):
        target.append(loin_path if role == "short" else (invisible_path if hide_shirt else original))
    return {"roles": roles, "target": target}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages())}


def actors(figs):
    all_actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_label = {}
    for actor in all_actors:
        by_label.setdefault(str(actor.get_actor_label()), []).append(actor)
    out = {}
    for f in figs:
        hits = by_label.get(f + " Clam", [])
        require(len(hits) == 1, "ACTOR_COUNT|%s|%d" % (f, len(hits)))
        require(str(hits[0].get_class().get_name()) == "BP_%s_Draped_C" % f,
                "ACTOR_CLASS|%s|%s" % (f, hits[0].get_class().get_name()))
        out[f] = hits[0]
    return out


def outfit_component(actor):
    hits = []
    for c in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        mesh = c.get_skeletal_mesh_asset()
        if mesh is not None and "_outfits" in path_of(mesh).lower():
            hits.append(c)
    require(len(hits) == 1, "OUTFIT_COMPONENT_COUNT|%s|%d" % (actor.get_actor_label(), len(hits)))
    return hits[0]


def component_state(c):
    mesh = c.get_skeletal_mesh_asset()
    resolved = [path_of(m) for m in c.get_materials()]
    overrides = [path_of(m) for m in (c.get_editor_property("override_materials") or [])]
    return {"component": str(c.get_name()), "mesh": path_of(mesh), "resolved": resolved, "overrides": overrides,
            "visible": bool(c.get_editor_property("visible")),
            "hidden_in_game": bool(c.get_editor_property("hidden_in_game"))}


def api_presence():
    want = (("MaterialFactoryNew", None), ("MaterialInstanceConstantFactoryNew", None),
            ("MaterialEditingLibrary", "connect_material_property"),
            ("MaterialEditingLibrary", "set_material_instance_vector_parameter_value"),
            ("EditorAssetLibrary", "save_asset"), ("SkeletalMeshComponent", "get_materials"))
    return {c + (("." + m) if m else ""): getattr(unreal, c, None) is not None and
            (m is None or hasattr(getattr(unreal, c), m)) for c, m in want}


def backup_map(run):
    folder = PROJECT + "Backups/PreP1MetaOutfit-" + run
    os.makedirs(folder)
    dst = os.path.join(folder, "L_InfinityStage_V1VerticalSlice.umap")
    shutil.copy2(UMAP, dst)
    require(sha256_file(UMAP) == sha256_file(dst), "BACKUP_HASH")
    return {"folder": folder, "files": [{"src": UMAP, "dst": dst, "bytes": os.path.getsize(dst),
                                           "sha256": sha256_file(dst)}]}


def new_asset(path, cls, factory):
    folder, name = path.rsplit("/", 1)
    obj = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, cls, factory)
    require(obj is not None and unreal.EditorAssetLibrary.does_asset_exist(path), "CREATE|" + path)
    return obj


def build_materials(names, colour, roughness):
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    for p in names.values():
        require(not eal.does_asset_exist(p), "ASSET_EXISTS|bump asset_version|" + p)

    loin = new_asset(names["loin_master"], unreal.Material, unreal.MaterialFactoryNew())
    loin.set_editor_property("used_with_skeletal_mesh", True)
    base = mel.create_material_expression(loin, unreal.MaterialExpressionVectorParameter, -500, -100)
    base.set_editor_property("parameter_name", "LoinclothColor")
    base.set_editor_property("default_value", unreal.LinearColor(*colour))
    rough = mel.create_material_expression(loin, unreal.MaterialExpressionScalarParameter, -500, 40)
    rough.set_editor_property("parameter_name", "Roughness")
    rough.set_editor_property("default_value", roughness)
    spec = mel.create_material_expression(loin, unreal.MaterialExpressionConstant, -500, 170)
    spec.set_editor_property("r", 0.22)
    require(mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR), "CONNECT|base")
    require(mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS), "CONNECT|rough")
    require(mel.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR), "CONNECT|spec")
    mel.recompile_material(loin)

    invisible = new_asset(names["invisible"], unreal.Material, unreal.MaterialFactoryNew())
    invisible.set_editor_property("used_with_skeletal_mesh", True)
    invisible.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    zero = mel.create_material_expression(invisible, unreal.MaterialExpressionConstant, -300, 0)
    zero.set_editor_property("r", 0.0)
    require(mel.connect_material_property(zero, "", unreal.MaterialProperty.MP_OPACITY_MASK), "CONNECT|opacity")
    mel.recompile_material(invisible)

    mi = new_asset(names["loin_mi"], unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(mi, loin)
    mel.set_material_instance_vector_parameter_value(mi, "LoinclothColor", unreal.LinearColor(*colour))
    mel.set_material_instance_scalar_parameter_value(mi, "Roughness", roughness)
    mel.update_material_instance(mi)
    got_c = mel.get_material_instance_vector_parameter_value(mi, "LoinclothColor")
    got_r = float(mel.get_material_instance_scalar_parameter_value(mi, "Roughness"))
    require(max(abs(a - b) for a, b in zip(colour, (got_c.r, got_c.g, got_c.b, got_c.a))) <= 1e-4,
            "MI_COLOUR_READBACK")
    require(abs(got_r - roughness) <= 1e-4, "MI_ROUGHNESS_READBACK")
    return {"loin_nodes": int(mel.get_num_material_expressions(loin)),
            "invisible_nodes": int(mel.get_num_material_expressions(invisible)),
            "colour": list(colour), "roughness": got_r}


def set_overrides(c, paths):
    mats = [unreal.load_asset(p) if p else None for p in paths]
    require(all(m is not None for m in mats), "MATERIAL_LOAD")
    c.modify()
    c.set_editor_property("override_materials", mats)
    got = [path_of(m) for m in (c.get_editor_property("override_materials") or [])]
    require(got == paths, "OVERRIDE_READBACK|got=%r want=%r" % (got, paths))
    return got


def save_exact(content, expect_map=True):
    dirty = census()
    require(sorted(dirty["content"]) == sorted(content), "DIRTY_CONTENT|got=%r want=%r" % (dirty["content"], content))
    require(dirty["maps"] == ([WORLD] if expect_map else []), "DIRTY_MAPS|%r" % dirty["maps"])
    for p in content:
        require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), "SAVE_ASSET|" + p)
    if expect_map:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        require(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD), "SAVE_MAP")
    require(census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%r" % census())
    return dirty


def run_dry(run, cfg):
    before = census()
    apis = api_presence()
    problems = ["API_MISSING|" + k for k, v in apis.items() if not v]
    names = asset_names(cfg["asset_version"])
    detail = {}
    for f, actor in actors(cfg["figures"]).items():
        st = component_state(outfit_component(actor))
        try:
            st["plan"] = plan_overrides(st["resolved"], names["loin_mi"], names["invisible"], cfg["hide_shirt"])
        except Exception as exc:
            problems.append("%s|%s" % (f, exc))
        detail[f] = st
    out = {"run": run, "mode": "DRY", "config": cfg, "assets": names, "api": apis, "figures": detail,
           "problems": problems, "census_before": before, "census_after": census(),
           "missing_torso_boundary": "declaration-proven from optimized body export; shirt hiding requires explicit acceptance"}
    require(out["census_after"] == before, "DRY_DIRTIED")
    with open(DRY_OUT, "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return {"problems": len(problems), "out": DRY_OUT}


def run_apply(run, cfg):
    require(census() == {"content": [], "maps": []}, "DIRTY_BEFORE|%r" % census())
    names = asset_names(cfg["asset_version"])
    current, plans = {}, {}
    for f, actor in actors(cfg["figures"]).items():
        st = component_state(outfit_component(actor))
        current[f] = st
        plans[f] = plan_overrides(st["resolved"], names["loin_mi"], names["invisible"], cfg["hide_shirt"])
    backup = backup_map(run)
    rec = {"run": run, "mode": "APPLY", "config": cfg, "assets": names, "before": current, "plans": plans,
           "backup": backup, "saved": False}
    with open(RECORD, "x", encoding="utf-8") as h:
        json.dump(rec, h, indent=2)
    unreal.log("P1OUTFIT_PLAN|run=%s|%s" % (run, json.dumps({"figures": cfg["figures"], "assets": names})))
    rec["material_readback"] = build_materials(names, cfg["loincloth_color"], cfg["roughness"])
    after = {}
    for f, actor in actors(cfg["figures"]).items():
        c = outfit_component(actor)
        set_overrides(c, plans[f]["target"])
        after[f] = component_state(c)
        require(after[f]["resolved"] == plans[f]["target"], "RESOLVED_READBACK|%s" % f)
    rec["saved_packages"] = save_exact(sorted(names.values()), expect_map=True)
    rec["after"] = after
    rec["saved"] = True
    with open(RECORD, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=2)
    return {"figures": len(cfg["figures"]), "record": RECORD, "backup": backup["folder"]}


def run_revert(run, cfg):
    require(census() == {"content": [], "maps": []}, "DIRTY_BEFORE|%r" % census())
    with open(RECORD, encoding="utf-8") as h:
        rec = json.load(h)
    require(rec.get("saved") is True, "RECORD_NOT_SAVED")
    require(cfg["figures"] == rec["config"]["figures"], "FIGURE_DRIFT")
    targets = actors(cfg["figures"])
    for f, actor in targets.items():
        now = component_state(outfit_component(actor))
        require(now["resolved"] == rec["plans"][f]["target"], "STATE_DRIFT|%s" % f)
    backup = backup_map(run)
    restored = {}
    for f, actor in actors(cfg["figures"]).items():
        c = outfit_component(actor)
        mats = [unreal.load_asset(p) if p else None for p in rec["before"][f]["overrides"]]
        c.modify()
        c.set_editor_property("override_materials", mats)
        restored[f] = component_state(c)
        require(restored[f]["overrides"] == rec["before"][f]["overrides"], "REVERT_READBACK|%s" % f)
    save_exact([], expect_map=True)
    moved = RECORD + ".reverted-" + run
    rec["revert"] = {"run": run, "backup": backup, "restored": restored, "created_assets_retained": list(rec["assets"].values())}
    with open(RECORD, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=2)
    os.replace(RECORD, moved)
    return {"figures": len(cfg["figures"]), "record": moved, "backup": backup["folder"],
            "created_assets_retained": True}


def main():
    run = datetime.datetime.now().strftime("P1OUTFIT-%Y%m%d-%H%M%S")
    mode = "DRY"
    try:
        with open(ARGS, encoding="utf-8") as h:
            raw = json.load(h)
        cfg = validate_args(raw, os.path.exists(RECORD))
        mode = cfg["mode"]
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        require(ed.get_game_world() is None, "PIE_ACTIVE")
        require(path_of(ed.get_editor_world()) == WORLD, "WRONG_WORLD|" + str(path_of(ed.get_editor_world())))
        unreal.log("P1OUTFIT_START|run=%s|mode=%s" % (run, mode))
        result = run_dry(run, cfg) if mode == "DRY" else (run_apply(run, cfg) if mode == "APPLY" else run_revert(run, cfg))
        unreal.log("P1OUTFIT_%s_OK|run=%s|%s" % (mode, run, json.dumps(result)))
    except Exception as exc:
        dirty = {}
        try:
            dirty = census()
        except Exception:
            pass
        unreal.log_error("P1OUTFIT_FAILED|run=%s|mode=%s|%s|census=%s|do not save; Don't-Save restart if dirty" %
                         (run, mode, str(exc).replace("\n", " "), json.dumps(dirty)))
        raise


if unreal is not None and os.environ.get("P1OUTFIT_NO_AUTORUN") != "1":
    main()
