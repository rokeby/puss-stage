"""Job 171 live Unreal tool.  Authored offline; the conductor runs it in the editor.

DRY/APPLY/REVERT confirmations are exact: ``<MODE> JOB171``.  APPLY requires the
fresh DRY JSON named by ``dry_record``.  REVERT never deletes generated assets;
it restores the map and leaves owned, disconnected bindings/materials in place.
"""
import datetime
import hashlib
import importlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import job171_core as core
importlib.reload(core)

MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MAP_FILE = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
LONG_GROOM = "/Game/MetaHumans/MHC_Elder_Female/Grooms/Hair_L_Straight"
LONG_SOURCE_FACE = "/Game/MetaHumans/MHC_Elder_Female/Face/SKM_MHC_VoidWoman_FaceMesh"
MESSY_GROOM = "/Game/Metahuman/ShoreCast_20260910/Assembled/Shore06_F25/MHC_Shore06_F25/Grooms/Hair_L_StraightBangs"
MESSY_SOURCE_FACE = "/Game/Metahuman/ShoreCast_20260910/Assembled/Shore06_F25/MHC_Shore06_F25/Face/SKM_MHC_Shore06_F25_FaceMesh"
STYLE_ASSETS = {
    "straight": (LONG_GROOM, LONG_SOURCE_FACE),
    "straight_bangs": (MESSY_GROOM, MESSY_SOURCE_FACE),
}
LONG_STRAND_PARENT = "/Game/MetaHumans/MHC_Elder_Female/Grooms/MI_WI_Hair_L_Straight_Hair"
HAIR_MI = {
    "dark_brown": "/Game/InfinityStage/Generated/Job171Hair/Materials/MI_J171_Hair_DarkBrown",
    "grey": "/Game/InfinityStage/Generated/Job171Hair/Materials/MI_J171_Hair_Grey",
}
FIRE_MASTER = "/Game/InfinityStage/Generated/Job171Fire/M_J171_CoolFire"
FIRE_MI = "/Game/InfinityStage/Generated/Job171Fire/MI_J171_CoolFire"
RECORD = os.path.join(HERE, "job171_apply_record.json")


def _ue():
    import unreal
    return unreal


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj else None


def _write(path, value, exclusive=False):
    if exclusive and os.path.exists(path):
        raise RuntimeError("RECORD_EXISTS|%s" % path)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _census():
    u = _ue()
    lib = u.EditorLoadingAndSavingUtils
    return {
        "content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
        "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages()),
    }


def _guard(mode, run, confirm):
    u = _ue()
    if u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    if not world or world.get_outermost().get_name() != MAP:
        raise RuntimeError("WRONG_WORLD|%s" % (_path(world),))
    if _census() != {"content": [], "maps": []}:
        raise RuntimeError("DIRTY_AT_START|%s" % _census())
    if mode != "DRY" and confirm != "%s JOB171" % mode:
        raise RuntimeError("CONFIRM|expected=%s JOB171" % mode)
    return world


def _params(args):
    p = {
        "dark_brown": {"hairMelanin": 0.72, "WhiteAmount": 0.03, "HairRoughness": 0.58},
        "grey": {"hairMelanin": 0.30, "WhiteAmount": 0.72, "HairRoughness": 0.64},
        "fire_linear": [0.35, 0.42, 0.50, 1.0],
        "fire_temperature": 9000.0,
        "fire_emissive_compensation": 2.0,
    }
    for key in ("dark_brown", "grey"):
        p[key].update((args.get(key) or {}))
        if set(p[key]) != {"hairMelanin", "WhiteAmount", "HairRoughness"} or any(not 0.0 <= float(v) <= 1.0 for v in p[key].values()):
            raise RuntimeError("HAIR_LOOK_ARGS|%s|%s" % (key, p[key]))
    for key in ("fire_linear", "fire_temperature", "fire_emissive_compensation"):
        if key in args:
            p[key] = args[key]
    if len(p["fire_linear"]) != 4 or any(not 0.0 <= float(v) <= 4.0 for v in p["fire_linear"]):
        raise RuntimeError("FIRE_LINEAR_ARGS|%s" % p["fire_linear"])
    if not 1000.0 <= float(p["fire_temperature"]) <= 20000.0 or not 0.1 <= float(p["fire_emissive_compensation"]) <= 10.0:
        raise RuntimeError("FIRE_LOOK_ARGS|%s" % p)
    return p


def _actors():
    u = _ue()
    rows = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    return {str(actor.get_actor_label()): actor for actor in rows}


def _hair_component(actor):
    u = _ue()
    rows = [c for c in actor.get_components_by_class(u.GroomComponent)
            if str(c.get_name()).lower() == "hair" or "hair_gen_variable" in str(c.get_name()).lower()]
    if len(rows) != 1:
        raise RuntimeError("HAIR_COMPONENT|%s|%s" % (actor.get_actor_label(), [c.get_name() for c in rows]))
    return rows[0]


def _face_mesh(actor):
    u = _ue()
    rows = [c for c in actor.get_components_by_class(u.SkeletalMeshComponent)
            if str(c.get_name()).lower() == "face"]
    if len(rows) != 1:
        raise RuntimeError("FACE_COMPONENT|%s|%s" % (actor.get_actor_label(), [c.get_name() for c in rows]))
    comp = rows[0]
    mesh = comp.get_editor_property("skeletal_mesh_asset")
    if not mesh:
        mesh = comp.get_editor_property("skeletal_mesh")
    if not mesh:
        raise RuntimeError("FACE_MESH|%s" % actor.get_actor_label())
    return mesh


def _groom_state(comp):
    groom = comp.get_editor_property("groom_asset")
    binding = comp.get_editor_property("binding_asset")
    return {
        "component": comp.get_path_name(),
        "groom": _path(groom),
        "binding": _path(binding),
        "materials": [_path(comp.get_material(i)) for i in range(comp.get_num_materials())],
    }


def _component_materials(comp):
    return [_path(comp.get_material(i)) for i in range(comp.get_num_materials())]


def _particle_template(comp):
    try:
        return comp.get_editor_property("template")
    except Exception:
        return comp.get_template()


def _niagara_params(comp):
    out = []
    try:
        store = comp.get_asset().get_exposed_parameters()
        out = sorted(str(x.get_name()) for x in store.get_parameters())
    except Exception:
        pass
    return out


def _light_state(actor):
    u = _ue()
    comp = actor.get_component_by_class(u.LightComponent)
    color = comp.get_editor_property("light_color")
    return {
        "component": comp.get_path_name(),
        "color": [int(color.r), int(color.g), int(color.b), int(color.a)],
        "temperature": float(comp.get_editor_property("temperature")),
        "use_temperature": bool(comp.get_editor_property("use_temperature")),
        "intensity": float(comp.get_editor_property("intensity")),
    }


def _inventory_assets():
    u = _ue()
    assets = []
    for root in ("/Game/MetaHumans", "/Game/Metahuman"):
        for path in u.EditorAssetLibrary.list_assets(root, recursive=True, include_folder=False):
            low = path.lower()
            if any(token in low for token in ("/grooms/", "/hair", "groom", "hair_")):
                assets.append(path.split(".")[0])
    return sorted(set(assets))


def _make_plan(parts, params):
    u = _ue()
    actors = _actors()
    plan = {"parts": list(parts), "map": MAP}
    if "hair" in parts:
        variations = core.variation_plan(core.validate_target_labels(actors.keys()))
        rows = []
        for row in variations:
            actor = actors[row["label"]]
            comp = _hair_component(actor)
            mesh = _face_mesh(actor)
            rows.append(dict(row, actor=actor.get_path_name(), face_mesh=_path(mesh), before=_groom_state(comp),
                             target_groom=STYLE_ASSETS[row["style"]][0],
                             target_binding=core.binding_path(row["figure"], row["style"]),
                             target_material=HAIR_MI[row["palette"]]))
        plan["hair"] = {"actors": rows, "unique_bindings": sorted(set(r["target_binding"] for r in rows)),
                        "look": {"dark_brown": params["dark_brown"], "grey": params["grey"]},
                        "asset_inventory": _inventory_assets(),
                        "long_styles": {k: {"groom": v[0], "source_face": v[1]} for k, v in STYLE_ASSETS.items()}}
    if "fires" in parts:
        fire_rows = []
        for label in core.FIRE_LABELS:
            actor = actors.get(label)
            if not actor:
                raise RuntimeError("MISSING_FIRE|%s" % label)
            pc = actor.get_component_by_class(u.ParticleSystemComponent)
            nc = actor.get_component_by_class(u.NiagaraComponent)
            if bool(pc) == bool(nc):
                raise RuntimeError("FIRE_COMPONENT|%s|cascade=%s|niagara=%s" % (label, bool(pc), bool(nc)))
            comp = nc or pc
            fire_rows.append({"label": label, "actor": actor.get_path_name(),
                              "kind": "niagara" if nc else "cascade", "component": comp.get_path_name(),
                              "asset": _path(nc.get_asset() if nc else _particle_template(pc)),
                              "materials": _component_materials(comp),
                              "niagara_parameters": _niagara_params(nc) if nc else []})
        light_rows = []
        for label in core.LIGHT_LABELS:
            actor = actors.get(label)
            if not actor:
                raise RuntimeError("MISSING_LIGHT|%s" % label)
            light_rows.append(dict(label=label, actor=actor.get_path_name(), before=_light_state(actor)))
        plan["fires"] = {"emitters": fire_rows, "lights": light_rows, "target_linear": list(params["fire_linear"]),
                         "target_temperature": float(params["fire_temperature"]),
                         "emissive_compensation": float(params["fire_emissive_compensation"]), "cascade_slots": [0, 1],
                         "niagara_color_tokens": ["color", "colour", "tint"]}
    plan["fingerprint"] = core.plan_fingerprint({k: v for k, v in plan.items() if k != "fingerprint"})
    return plan


def _backup(run, packages):
    root = "E:/PussStage/Backups/PreJob171S3HairFire-%s" % run
    if os.path.exists(root):
        raise RuntimeError("BACKUP_EXISTS|%s" % root)
    os.makedirs(root)
    copied = []
    for package in packages:
        if package == MAP:
            source = MAP_FILE
            relative = "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
        elif package.startswith("/Game/"):
            relative = "Content/" + package[len("/Game/"):] + ".uasset"
            source = "E:/PussStage/" + relative
        else:
            continue
        if os.path.exists(source):
            target = os.path.join(root, relative.replace("/", os.sep))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)
            copied.append(source)
    return {"root": root, "copied": copied}


def _ensure_mi(path, parent_path, scalar_values):
    u = _ue()
    made = not u.EditorAssetLibrary.does_asset_exist(path)
    parent = u.load_asset(parent_path)
    if made:
        folder, name = path.rsplit("/", 1)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.MaterialInstanceConstant,
                                                                 u.MaterialInstanceConstantFactoryNew())
        if not mi or not parent:
            raise RuntimeError("CREATE_MI|%s|parent=%s" % (path, parent_path))
        mi.set_editor_property("parent", parent)
    else:
        mi = u.load_asset(path)
    mel = u.MaterialEditingLibrary
    names = {str(x) for x in mel.get_scalar_parameter_names(parent)}
    missing = [key for key in scalar_values if key not in names]
    if missing:
        raise RuntimeError("HAIR_PARAMETERS|parent=%s|missing=%s|available=%s" % (parent_path, missing, sorted(names)))
    for key, value in scalar_values.items():
        mel.set_material_instance_scalar_parameter_value(mi, key, float(value))
    return mi, made


def _ensure_binding(path, groom, target_mesh, source_path):
    u = _ue()
    if u.EditorAssetLibrary.does_asset_exist(path):
        return u.load_asset(path), False
    source = u.load_asset(source_path)
    if not source:
        raise RuntimeError("SOURCE_FACE_MISSING|%s" % source_path)
    binding = u.GroomBlueprintLibrary.create_new_groom_binding_asset_with_path(path, groom, target_mesh, 100, source, 0)
    if not binding:
        raise RuntimeError("CREATE_BINDING|%s" % path)
    return binding, True


def _ensure_fire_material(source_material, color, compensation):
    u = _ue()
    mel = u.MaterialEditingLibrary
    created = []
    if not u.EditorAssetLibrary.does_asset_exist(FIRE_MASTER):
        if not source_material:
            raise RuntimeError("FIRE_SOURCE_MATERIAL_MISSING")
        source = source_material.get_base_material() if hasattr(source_material, "get_base_material") else source_material
        master = u.EditorAssetLibrary.duplicate_asset(_path(source), FIRE_MASTER)
        if not master:
            raise RuntimeError("DUPLICATE_FIRE_MATERIAL|%s" % _path(source))
        old = mel.get_material_property_input_node(master, u.MaterialProperty.MP_EMISSIVE_COLOR)
        old_output = mel.get_material_property_input_node_output_name(master, u.MaterialProperty.MP_EMISSIVE_COLOR)
        if not old:
            raise RuntimeError("FIRE_EMISSIVE_INPUT|%s" % _path(source))
        desat = mel.create_material_expression(master, u.MaterialExpressionDesaturation, 250, 0)
        tint = mel.create_material_expression(master, u.MaterialExpressionVectorParameter, 500, 0)
        tint.set_editor_property("parameter_name", "CoolColor")
        tint.set_editor_property("default_value", u.LinearColor(*color))
        mul1 = mel.create_material_expression(master, u.MaterialExpressionMultiply, 750, 0)
        gain = mel.create_material_expression(master, u.MaterialExpressionScalarParameter, 500, 180)
        gain.set_editor_property("parameter_name", "EmissiveCompensation")
        gain.set_editor_property("default_value", float(compensation))
        mul2 = mel.create_material_expression(master, u.MaterialExpressionMultiply, 1000, 0)
        mel.connect_material_expressions(old, old_output, desat, "Input")
        mel.connect_material_expressions(desat, "", mul1, "A")
        mel.connect_material_expressions(tint, "", mul1, "B")
        mel.connect_material_expressions(mul1, "", mul2, "A")
        mel.connect_material_expressions(gain, "", mul2, "B")
        mel.connect_material_property(mul2, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
        mel.recompile_material(master)
        created.append(FIRE_MASTER)
    else:
        master = u.load_asset(FIRE_MASTER)
    if not u.EditorAssetLibrary.does_asset_exist(FIRE_MI):
        folder, name = FIRE_MI.rsplit("/", 1)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.MaterialInstanceConstant,
                                                                 u.MaterialInstanceConstantFactoryNew())
        mi.set_editor_property("parent", master)
        created.append(FIRE_MI)
    else:
        mi = u.load_asset(FIRE_MI)
    mel.set_material_instance_vector_parameter_value(mi, "CoolColor", u.LinearColor(*color))
    mel.set_material_instance_scalar_parameter_value(mi, "EmissiveCompensation", float(compensation))
    return mi, created


def _capture_state(plan):
    u = _ue()
    actors = _actors()
    state = {"hair": {}, "fires": {}, "lights": {}}
    if "hair" in plan["parts"]:
        for row in plan["hair"]["actors"]:
            state["hair"][row["label"]] = _groom_state(_hair_component(actors[row["label"]]))
    if "fires" in plan["parts"]:
        for row in plan["fires"]["emitters"]:
            actor = actors[row["label"]]
            comp = actor.get_component_by_class(u.NiagaraComponent) or actor.get_component_by_class(u.ParticleSystemComponent)
            state["fires"][row["label"]] = {"materials": _component_materials(comp)}
        for row in plan["fires"]["lights"]:
            state["lights"][row["label"]] = _light_state(actors[row["label"]])
    return state


def _validate_applied(plan, before, after):
    for row in plan.get("hair", {}).get("actors", []):
        got_hair = after["hair"][row["label"]]
        if got_hair["groom"] != row["target_groom"] or got_hair["binding"] != row["target_binding"]:
            raise RuntimeError("HAIR_READBACK|%s|%s" % (row["label"], got_hair))
        if not got_hair["materials"] or got_hair["materials"][0] != row["target_material"]:
            raise RuntimeError("HAIR_MATERIAL_READBACK|%s|%s" % (row["label"], got_hair["materials"]))
    for row in plan.get("fires", {}).get("emitters", []):
        got_fire = after["fires"][row["label"]]["materials"]
        if any(slot >= len(got_fire) or got_fire[slot] != FIRE_MI for slot in plan["fires"]["cascade_slots"]):
            raise RuntimeError("FIRE_MATERIAL_READBACK|%s|%s" % (row["label"], got_fire))
    for label in before["lights"]:
        got_light = after["lights"][label]
        if abs(before["lights"][label]["intensity"] - got_light["intensity"]) > 1.0e-4:
            raise RuntimeError("LIGHT_INTENSITY_CHANGED|%s" % label)
        wanted = [round(float(x) * 255.0) for x in plan["fires"]["target_linear"][:3]]
        if any(abs(a - b) > 1 for a, b in zip(got_light["color"][:3], wanted)) or abs(got_light["temperature"] - plan["fires"]["target_temperature"]) > 1.0e-4:
            raise RuntimeError("LIGHT_COLOUR_READBACK|%s|%s" % (label, got_light))


def run_dry(run, parts, args):
    _guard("DRY", run, args.get("confirm"))
    plan = _make_plan(parts, _params(args))
    out = os.path.join(HERE, "job171_dry_%s.json" % run)
    report = {"tool": core.TOOL, "tool_version": core.TOOL_VERSION, "run": run, "mode": "DRY",
              "plan": plan, "dirty_before": _census(), "dirty_after": _census(),
              "apply_confirm": "APPLY JOB171", "revert_confirm": "REVERT JOB171"}
    _write(out, report, exclusive=True)
    _ue().log("JOB171_DRY_OK|run=%s|hair=%d|fires=%d|bindings=%d|record=%s" %
              (run, len(plan.get("hair", {}).get("actors", [])), len(plan.get("fires", {}).get("emitters", [])),
               len(plan.get("hair", {}).get("unique_bindings", [])), out))
    return report


def run_apply(run, parts, args):
    _guard("APPLY", run, args.get("confirm"))
    if os.path.exists(RECORD):
        raise RuntimeError("APPLY_RECORD_EXISTS|%s" % RECORD)
    dry_path = args.get("dry_record")
    if not dry_path or not os.path.exists(dry_path):
        raise RuntimeError("DRY_RECORD_REQUIRED")
    dry = _read(dry_path)
    plan = _make_plan(parts, _params(args))
    if dry.get("plan", {}).get("fingerprint") != plan["fingerprint"]:
        raise RuntimeError("DRY_DRIFT|expected=%s|live=%s" % (dry.get("plan", {}).get("fingerprint"), plan["fingerprint"]))
    backup_packages = [MAP]
    if "hair" in parts:
        backup_packages.extend(HAIR_MI.values())
        backup_packages.extend(plan["hair"]["unique_bindings"])
    if "fires" in parts:
        backup_packages.extend([FIRE_MASTER, FIRE_MI])
    backup = _backup(run, sorted(set(backup_packages)))
    before = _capture_state(plan)
    record = {"tool": core.TOOL, "tool_version": core.TOOL_VERSION, "run": run, "parts": parts,
              "plan": plan, "state_before": before, "backup": backup, "created_assets": [], "applied": False}
    _write(RECORD, record, exclusive=True)
    u = _ue()
    actors = _actors()
    created = []
    if "hair" in parts:
        grooms = {style: u.load_asset(paths[0]) for style, paths in STYLE_ASSETS.items()}
        if any(not value for value in grooms.values()):
            raise RuntimeError("LONG_GROOM_MISSING|%s" % {k: bool(v) for k, v in grooms.items()})
        dark, made = _ensure_mi(HAIR_MI["dark_brown"], LONG_STRAND_PARENT, plan["hair"]["look"]["dark_brown"])
        if made: created.append(HAIR_MI["dark_brown"])
        grey, made = _ensure_mi(HAIR_MI["grey"], LONG_STRAND_PARENT, plan["hair"]["look"]["grey"])
        if made: created.append(HAIR_MI["grey"])
        bindings = {}
        for row in plan["hair"]["actors"]:
            key = (row["figure"], row["style"])
            if key in bindings:
                continue
            binding, made = _ensure_binding(row["target_binding"], grooms[row["style"]],
                                            _face_mesh(actors[row["label"]]), STYLE_ASSETS[row["style"]][1])
            bindings[key] = binding
            if made: created.append(row["target_binding"])
        for row in plan["hair"]["actors"]:
            actor = actors[row["label"]]
            comp = _hair_component(actor)
            actor.modify(); comp.modify()
            comp.set_groom_asset(grooms[row["style"]], bindings[(row["figure"], row["style"])], True)
            comp.set_material(0, grey if row["palette"] == "grey" else dark)
    if "fires" in parts:
        unsupported = [row["label"] for row in plan["fires"]["emitters"] if row["kind"] != "cascade"]
        if unsupported:
            raise RuntimeError("NIAGARA_APPLY_UNSUPPORTED_UNTIL_REVERSIBLE_PARAMETER_READBACK|%s" % unsupported)
        first_cascade = next((row for row in plan["fires"]["emitters"] if row["kind"] == "cascade"), None)
        cool_mi = None
        if first_cascade:
            first_actor = actors[first_cascade["label"]]
            first_comp = first_actor.get_component_by_class(u.ParticleSystemComponent)
            source = first_comp.get_material(plan["fires"]["cascade_slots"][0])
            cool_mi, made = _ensure_fire_material(source, plan["fires"]["target_linear"],
                                                   plan["fires"]["emissive_compensation"])
            created.extend(made)
        for row in plan["fires"]["emitters"]:
            actor = actors[row["label"]]
            comp = actor.get_component_by_class(u.NiagaraComponent) or actor.get_component_by_class(u.ParticleSystemComponent)
            actor.modify(); comp.modify()
            if row["kind"] == "cascade":
                for slot in plan["fires"]["cascade_slots"]:
                    if slot >= comp.get_num_materials():
                        raise RuntimeError("CASCADE_SLOT|%s|slot=%d|count=%d" % (row["label"], slot, comp.get_num_materials()))
                    comp.set_material(slot, cool_mi)
        for row in plan["fires"]["lights"]:
            actor = actors[row["label"]]
            comp = actor.get_component_by_class(u.LightComponent)
            actor.modify(); comp.modify()
            comp.set_light_color(u.LinearColor(*plan["fires"]["target_linear"]), False)
            comp.set_editor_property("use_temperature", True)
            comp.set_editor_property("temperature", plan["fires"]["target_temperature"])
    record["created_assets"] = sorted(set(created))
    allowed_content = sorted(set(record["created_assets"] + (list(HAIR_MI.values()) if "hair" in parts else []) +
                                 ([FIRE_MI] if "fires" in parts else [])))
    got = _census()
    if got["maps"] != [MAP] or any(path not in allowed_content for path in got["content"]):
        raise RuntimeError("DIRTY_SCOPE|got=%s|allowed_content=%s|NOTHING SAVED; Don't-Save restart; backup=%s" %
                           (got, allowed_content, backup["root"]))
    record["dirty_presave"] = got
    presave = _capture_state(plan)
    _validate_applied(plan, before, presave)
    record["state_presave"] = presave
    for path in allowed_content:
        if not u.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            raise RuntimeError("SAVE_ASSET|%s" % path)
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level():
        raise RuntimeError("SAVE_MAP|%s" % MAP)
    if _census() != {"content": [], "maps": []}:
        raise RuntimeError("DIRTY_AFTER_SAVE|%s" % _census())
    after = _capture_state(plan)
    _validate_applied(plan, before, after)
    record.update({"state_after": after, "created_assets": sorted(set(created)), "saved_assets": allowed_content,
                   "applied": True})
    _write(RECORD, record)
    u.log("JOB171_APPLY_OK|run=%s|hair=%d|fires=%d|assets=%d|backup=%s|record=%s" %
          (run, len(after["hair"]), len(after["fires"]), len(allowed_content), backup["root"], RECORD))
    return record


def _load_object(path):
    return _ue().load_object(None, path)


def run_revert(run, parts, args):
    del parts
    _guard("REVERT", run, args.get("confirm"))
    if not os.path.exists(RECORD):
        raise RuntimeError("NO_APPLY_RECORD")
    rec = _read(RECORD)
    if not rec.get("applied") or rec.get("tool_version") != core.TOOL_VERSION:
        raise RuntimeError("RECORD_CONTEXT")
    live = _capture_state(rec["plan"])
    drift = core.numeric_diff(rec["state_after"], live)
    if drift:
        raise RuntimeError("STATE_DRIFTED_SINCE_APPLY|%s" % drift[:20])
    backup = _backup(run + "-Revert", [MAP])
    u = _ue()
    actors = _actors()
    before = rec["state_before"]
    for row in rec["plan"].get("hair", {}).get("actors", []):
        comp = _hair_component(actors[row["label"]])
        old = before["hair"][row["label"]]
        comp.modify()
        comp.set_groom_asset(u.load_asset(old["groom"]) if old["groom"] else None,
                             u.load_asset(old["binding"]) if old["binding"] else None, True)
        for index, path in enumerate(old["materials"]):
            comp.set_material(index, u.load_asset(path) if path else None)
    for row in rec["plan"].get("fires", {}).get("emitters", []):
        actor = actors[row["label"]]
        comp = actor.get_component_by_class(u.NiagaraComponent) or actor.get_component_by_class(u.ParticleSystemComponent)
        comp.modify()
        for index, path in enumerate(before["fires"][row["label"]]["materials"]):
            comp.set_material(index, u.load_asset(path) if path else None)
    for row in rec["plan"].get("fires", {}).get("lights", []):
        old = before["lights"][row["label"]]
        comp = actors[row["label"]].get_component_by_class(u.LightComponent)
        comp.modify()
        comp.set_editor_property("light_color", u.Color(*old["color"]))
        comp.set_editor_property("temperature", old["temperature"])
        comp.set_editor_property("use_temperature", old["use_temperature"])
        comp.set_editor_property("intensity", old["intensity"])
    if _census() != {"content": [], "maps": [MAP]}:
        raise RuntimeError("REVERT_DIRTY_SCOPE|%s|NOTHING SAVED; backup=%s" % (_census(), backup["root"]))
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level() or _census() != {"content": [], "maps": []}:
        raise RuntimeError("REVERT_SAVE|%s" % _census())
    restored = _capture_state(rec["plan"])
    drift = core.numeric_diff(before, restored)
    if drift:
        raise RuntimeError("REVERT_READBACK|%s" % drift[:20])
    archived = RECORD + ".reverted-" + run
    os.rename(RECORD, archived)
    u.log("JOB171_REVERT_OK|run=%s|assets_retained=%d|backup=%s|record=%s" %
          (run, len(rec.get("created_assets", [])), backup["root"], archived))
    return {"record": archived, "backup": backup, "assets_retained": rec.get("created_assets", [])}


def main(args):
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or datetime.datetime.now().strftime("J171-%Y%m%d-%H%M%S"))
    parts = core.selected_parts(args.get("parts"))
    fn = {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}.get(mode)
    if not fn:
        raise RuntimeError("MODE|%s" % mode)
    return fn(run, parts, args)

