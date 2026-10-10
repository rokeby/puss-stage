"""Guarded Unreal editor tool for job 115; authored and tested offline only.

DRY is read-only. APPLY creates only versioned shirt child MIs, changes only
shirt-role slots on the six canonical S3 figures plus P40-tagged variants, and
saves only the new MIs and the vertical-slice map. REVERT restores recorded
slot assignments and intentionally retains the created MIs. Existing material
graphs are never edited and no nodes or assets are deleted.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sys
import traceback

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import j115_core as core  # noqa: E402

ARGS = os.path.join(HERE, "j115_args.json")
RECORD = os.path.join(HERE, "j115_apply_record.json")
DRY_OUT = os.path.join(HERE, "j115_dry_latest.json")
VERIFY_OUT = os.path.join(HERE, "j115_verify_latest.json")
DIAG = os.path.normpath(os.path.join(HERE, "..", "S3_VISUAL_DIAG_20261009.json"))


class Stop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def path_of(obj):
    return None if obj is None else str(obj.get_path_name()).split(".")[0]


def full_path(obj):
    return None if obj is None else str(obj.get_path_name())


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(x.get_name()) for x in lib.get_dirty_content_packages()),
            "maps": sorted(str(x.get_name()) for x in lib.get_dirty_map_packages())}


def clean_context(require_clean=False):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_RUNNING")
    world = editor.get_editor_world()
    require(path_of(world) == core.WORLD, "WRONG_WORLD|" + str(path_of(world)))
    if require_clean:
        require(census() == {"content": [], "maps": []}, "DIRTY_AT_START|" + json.dumps(census()))
    actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    return world, actors


def shore_id_from_class(actor):
    class_name = str(actor.get_class().get_name())
    for figure in core.FIGURES:
        if class_name == "BP_%s_Draped_C" % figure:
            return figure
    return None


def actor_scope(actors):
    inventory = []
    for actor in actors:
        figure = shore_id_from_class(actor)
        if figure:
            inventory.append({"figure": figure, "label": str(actor.get_actor_label()),
                              "path": full_path(actor), "tags": sorted(str(x) for x in (prop(actor, "tags", []) or [])),
                              "actor": actor})
    public = [{k: v for k, v in row.items() if k != "actor"} for row in inventory]
    selected_public = core.expected_actor_scope(public)
    by_path = {row["path"]: row for row in inventory}
    return [by_path[row["path"]] for row in selected_public]


def outfit_component(actor):
    hits = []
    for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        mesh = component.get_skeletal_mesh_asset()
        if mesh is not None and "_outfits" in (path_of(mesh) or "").lower():
            hits.append(component)
    unique = {full_path(component): component for component in hits}
    require(len(unique) == 1, "OUTFIT_COMPONENT_COUNT|%s|%r" %
            (actor.get_actor_label(), sorted(unique)))
    return next(iter(unique.values()))


def material_names(material):
    mel = unreal.MaterialEditingLibrary
    return {"texture": sorted(str(x) for x in mel.get_texture_parameter_names(material)),
            "vector": sorted(str(x) for x in mel.get_vector_parameter_names(material)),
            "scalar": sorted(str(x) for x in mel.get_scalar_parameter_names(material)),
            "static_switch": sorted(str(x) for x in mel.get_static_switch_parameter_names(material))}


def color_value(value):
    return [float(value.r), float(value.g), float(value.b), float(value.a)]


def parameter_readback(material, plan, switches):
    mel = unreal.MaterialEditingLibrary
    out = {"mode": plan["mode"], "static_switches": {}}
    if plan["mode"] == "textures":
        out["base_color_texture"] = path_of(mel.get_material_instance_texture_parameter_value(
            material, plan["base_color_texture"]))
        out["normal_texture"] = path_of(mel.get_material_instance_texture_parameter_value(
            material, plan["normal_texture"]))
    else:
        out["tint"] = color_value(mel.get_material_instance_vector_parameter_value(material, plan["tint_vector"]))
        out["roughness"] = float(mel.get_material_instance_scalar_parameter_value(material, plan["roughness_scalar"]))
        if plan.get("specular_scalar"):
            out["specular"] = float(mel.get_material_instance_scalar_parameter_value(material, plan["specular_scalar"]))
    for name in switches:
        out["static_switches"][name] = bool(
            mel.get_material_instance_static_switch_parameter_value(material, name))
    return out


def figure_parent_plans(scope, cfg):
    parents = {}
    assignments = []
    for row in scope:
        component = outfit_component(row["actor"])
        resolved = [path_of(component.get_material(i)) for i in range(component.get_num_materials())]
        shirt_slots = [i for i, path in enumerate(resolved) if core.classify_material(path) == "shirt"]
        require(shirt_slots, "NO_SHIRT_SLOTS|" + row["label"])
        parent_paths = sorted(set(resolved[i] for i in shirt_slots))
        require(len(parent_paths) == 1, "SHIRT_PARENT_COUNT|%s|%r" % (row["label"], parent_paths))
        parent_path = parent_paths[0]
        previous = parents.get(row["figure"])
        require(previous is None or previous["parent"] == parent_path,
                "FIGURE_PARENT_DRIFT|%s|%s|%s" % (row["figure"], (previous or {}).get("parent"), parent_path))  # message was built eagerly: None["parent"] (live DRY 10 Oct)
        if previous is None:
            parent = unreal.load_asset(parent_path)
            require(parent is not None, "PARENT_LOAD|" + parent_path)
            names = material_names(parent)
            plan = core.plan_parameter_strategy(names, cfg["parameter_candidates"])
            missing_switches = sorted(set(cfg["texture_mode_static_switches"]) - set(names["static_switch"]))
            require(not missing_switches, "STATIC_SWITCH_MISSING|%s|%r" % (row["figure"], missing_switches))
            parents[row["figure"]] = {"figure": row["figure"], "body_shape": core.BODY_SHAPE[row["figure"]],
                "parent": parent_path, "parameter_names": names, "strategy": plan,
                "child": core.child_path(row["figure"], cfg["asset_version"]), "parent_object": parent}
        assignments.append({"figure": row["figure"], "label": row["label"], "actor_path": row["path"],
                            "component": full_path(component), "slots": shirt_slots,
                            "resolved_before": resolved, "before_overrides": [path_of(x) for x in
                                (prop(component, "override_materials", []) or [])]})
    return [parents[f] for f in core.FIGURES], assignments


def source_measurement(cfg):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    path = os.path.normpath(os.path.join(project, cfg["source_png_relative"]))
    return core.texture_mean(path)


def diagnostic_gate_snapshot():
    if not os.path.isfile(DIAG):
        return {"status": "UNCLEAR", "reason": "diag-v2 JSON missing", "fix_matrix": core.diagnostic_fix_matrix()}
    data = load_json(DIAG)
    return {"status": "available_for_conductor_review", "schema": data.get("schema"),
            "result": data.get("result"), "path": DIAG, "fix_matrix": core.diagnostic_fix_matrix()}


def dry(run, cfg):
    before = census()
    _world, actors = clean_context(False)
    scope = actor_scope(actors)
    parents, assignments = figure_parent_plans(scope, cfg)
    existing = [row["child"] for row in parents if unreal.EditorAssetLibrary.does_asset_exist(row["child"])]
    problems = (["CHILD_EXISTS|" + path for path in existing] +
                ([] if before == {"content": [], "maps": []} else ["DIRTY_AT_START|" + json.dumps(before)]))
    source = source_measurement(cfg)
    after = census()
    require(before == after, "DRY_DIRTIED|before=%s after=%s" % (json.dumps(before), json.dumps(after)))
    public_parents = [{k: v for k, v in row.items() if k != "parent_object"} for row in parents]
    report = {"schema": core.SCHEMA, "run_id": run, "mode": "DRY", "apply_ready": not problems,
              "writes": 0, "problems": problems, "census_before": before, "census_after": after,
              "source_weave": source, "parents": public_parents, "assignments": assignments,
              "target_actor_count": len(assignments), "canonical_count": 6,
              "p40_variant_count": sum(core.P40_TAG in set(row.get("tags") or []) for row in scope),
              "diagnostic_gates": diagnostic_gate_snapshot(),
              "stills_plan": [
                  {"shot": "S3_B02", "compare": "before/after shirt-shroud overlap; midtone and weave continuity"},
                  {"shot": "S3_B08", "compare": "female/male body-shape pair; highlight and roughness response"},
                  {"shot": "S3_B11", "compare": "Shore05 plus every visible P40 variant; no white shirt edge"},
              ], "visual_acceptance": "required from rendered stills; readback is not visual proof"}
    write_json(DRY_OUT, report)
    unreal.log("J115SHIRTS_DRY_%s|run=%s|actors=%d|variants=%d|writes=0|report=%s" %
               ("OK" if report["apply_ready"] else "STOPPED", run, len(assignments),
                report["p40_variant_count"], DRY_OUT))
    return report


def project_path(relative):
    return os.path.normpath(os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), relative))


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup_map(run):
    root = project_path(os.path.join("Backups", "PreJ115S3Shirts-" + run))
    require(not os.path.exists(root), "BACKUP_EXISTS|" + root)
    source = project_path("Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap")
    require(os.path.isfile(source), "BACKUP_SOURCE_MISSING|" + source)
    destination = os.path.join(root, "InfinityStage", "Dev", "Maps", os.path.basename(source))
    os.makedirs(os.path.dirname(destination), exist_ok=False)
    shutil.copy2(source, destination)
    require(sha_file(source) == sha_file(destination), "BACKUP_HASH")
    return {"root": root, "files": [{"package": core.WORLD, "source": source, "backup": destination,
                                      "bytes": os.path.getsize(destination), "sha256": sha_file(destination)}]}


def create_children(parents, cfg, source):
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mel = unreal.MaterialEditingLibrary
    bc = unreal.load_asset(core.WEAVE_BC)
    normal = unreal.load_asset(core.WEAVE_N)
    require(bc is not None and normal is not None, "WEAVE_TEXTURE_LOAD")
    created = []
    for row in parents:
        require(not unreal.EditorAssetLibrary.does_asset_exist(row["child"]), "CHILD_EXISTS|" + row["child"])
        folder, name = row["child"].rsplit("/", 1)
        mi = tools.create_asset(name, folder, unreal.MaterialInstanceConstant,
                                unreal.MaterialInstanceConstantFactoryNew())
        require(mi is not None, "CHILD_CREATE|" + row["child"])
        mel.set_material_instance_parent(mi, row["parent_object"])
        plan = row["strategy"]
        if plan["mode"] == "textures":
            mel.set_material_instance_texture_parameter_value(mi, plan["base_color_texture"], bc)
            mel.set_material_instance_texture_parameter_value(mi, plan["normal_texture"], normal)
        else:
            mean = source["mean_linear"]
            mel.set_material_instance_vector_parameter_value(mi, plan["tint_vector"],
                                                              unreal.LinearColor(mean[0], mean[1], mean[2], 1.0))
            mel.set_material_instance_scalar_parameter_value(mi, plan["roughness_scalar"], cfg["fallback_roughness"])
            if plan.get("specular_scalar"):
                mel.set_material_instance_scalar_parameter_value(mi, plan["specular_scalar"], cfg["fallback_specular"])
            if plan.get("metallic_scalar"):
                mel.set_material_instance_scalar_parameter_value(mi, plan["metallic_scalar"], float(cfg.get("fallback_metallic", 0.0)))
        for switch, value in cfg["texture_mode_static_switches"].items():
            # Unreal setters may report False despite succeeding. Ignore the return and read back.
            mel.set_material_instance_static_switch_parameter_value(mi, switch, bool(value))
        mel.update_material_instance(mi)
        got = parameter_readback(mi, plan, cfg["texture_mode_static_switches"])
        if plan["mode"] == "textures":
            require(got["base_color_texture"] == core.WEAVE_BC and got["normal_texture"] == core.WEAVE_N,
                    "TEXTURE_READBACK|" + row["figure"])
        else:
            require(max(abs(got["tint"][i] - source["mean_linear"][i]) for i in range(3)) <= 1.0e-4,
                    "TINT_READBACK|" + row["figure"])
            require(abs(got["roughness"] - cfg["fallback_roughness"]) <= 1.0e-4,
                    "ROUGHNESS_READBACK|" + row["figure"])
            if plan.get("metallic_scalar"):
                m = float(unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(mi, plan["metallic_scalar"]))
                require(abs(m - float(cfg.get("fallback_metallic", 0.0))) <= 1.0e-4, "METALLIC_READBACK|" + row["figure"])
        require(got["static_switches"] == cfg["texture_mode_static_switches"],
                "STATIC_SWITCH_READBACK|" + row["figure"])
        created.append({"figure": row["figure"], "path": row["child"], "parent": row["parent"],
                        "strategy": plan, "readback": got})
    return created


def apply_assignments(scope, planned, children):
    by_path = {row["path"]: row for row in scope}
    child_by_figure = {row["figure"]: row["path"] for row in children}
    rows = []
    for plan in planned:
        live = by_path.get(plan["actor_path"])
        require(live is not None, "ACTOR_DRIFT|" + plan["actor_path"])
        component = outfit_component(live["actor"])
        resolved_before = [path_of(component.get_material(i)) for i in range(component.get_num_materials())]
        require(resolved_before == plan["resolved_before"], "SLOT_DRIFT|" + plan["label"])
        child_path = child_by_figure[plan["figure"]]
        child = unreal.load_asset(child_path)
        require(child is not None, "CHILD_LOAD|" + child_path)
        component.modify()
        for slot in plan["slots"]:
            component.set_material(slot, child)
        resolved_after = [path_of(component.get_material(i)) for i in range(component.get_num_materials())]
        require(all(resolved_after[i] == child_path for i in plan["slots"]),
                "SLOT_READBACK|" + plan["label"])
        rows.append({**plan, "child": child_path, "resolved_after": resolved_after,
                     "after_overrides": [path_of(x) for x in (prop(component, "override_materials", []) or [])]})
    return rows


def save_exact(content, world, map_expected=True):
    expected = {"content": sorted(content), "maps": [core.WORLD] if map_expected else []}
    require(census() == expected, "DIRTY_CENSUS|got=%s expected=%s|NOTHING SAVED" %
            (json.dumps(census()), json.dumps(expected)))
    for package in sorted(content):
        require(unreal.EditorAssetLibrary.save_asset(package, only_if_is_dirty=False), "SAVE_ASSET|" + package)
    if map_expected:
        require(unreal.EditorLoadingAndSavingUtils.save_map(world, core.WORLD), "SAVE_MAP")
    require(census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|" + json.dumps(census()))


def apply(run, cfg):
    world, actors = clean_context(True)
    scope = actor_scope(actors)
    parents, assignments = figure_parent_plans(scope, cfg)
    require(not any(unreal.EditorAssetLibrary.does_asset_exist(row["child"]) for row in parents),
            "CHILD_EXISTS|bump asset_version")
    source = source_measurement(cfg)
    backup = backup_map(run)
    public_parents = [{k: v for k, v in row.items() if k != "parent_object"} for row in parents]
    record = {"schema": core.SCHEMA, "run_id": run, "state": "prepared", "saved": False,
              "config": cfg, "backup": backup, "source_weave": source, "parents": public_parents,
              "planned_assignments": assignments, "created_children": [], "assignments": []}
    write_json(RECORD, record, exclusive=True)
    record["created_children"] = create_children(parents, cfg, source)
    record["assignments"] = apply_assignments(scope, assignments, record["created_children"])
    write_json(RECORD, record)
    packages = [row["path"] for row in record["created_children"]]
    save_exact(packages, world, True)
    record["state"] = "applied"; record["saved"] = True
    record["saved_packages"] = sorted(packages + [core.WORLD])
    write_json(RECORD, record)
    checked = verify(run, cfg, record, emit=False)
    require(checked["ok"], "POST_SAVE_READBACK|" + " || ".join(checked["problems"]))
    unreal.log("J115SHIRTS_APPLY_OK|run=%s|actors=%d|children=%d|packages=%s|backup=%s|dirty=0" %
               (run, len(record["assignments"]), len(packages), record["saved_packages"], backup["root"]))
    return record


def verify(run, cfg, record=None, emit=True):
    record = record or load_json(RECORD)
    _world, actors = clean_context(False)
    scope = actor_scope(actors)
    by_path = {row["path"]: row for row in scope}
    problems = []
    child_readbacks = []
    for child in record["created_children"]:
        mi = unreal.load_asset(child["path"])
        if mi is None:
            problems.append("CHILD_MISSING|" + child["path"]); continue
        got = parameter_readback(mi, child["strategy"], record["config"]["texture_mode_static_switches"])
        child_readbacks.append({"figure": child["figure"], "path": child["path"], "readback": got})
        if got != child["readback"]:
            problems.append("PARAMETER_DRIFT|" + child["figure"])
    assignment_readbacks = []
    for row in record["assignments"]:
        live = by_path.get(row["actor_path"])
        if live is None:
            problems.append("ACTOR_MISSING|" + row["label"]); continue
        component = outfit_component(live["actor"])
        resolved = [path_of(component.get_material(i)) for i in range(component.get_num_materials())]
        assignment_readbacks.append({"actor_path": row["actor_path"], "label": row["label"],
                                     "component": full_path(component), "slots": row["slots"], "resolved": resolved})
        if any(resolved[i] != row["child"] for i in row["slots"]):
            problems.append("SLOT_DRIFT|" + row["label"])
    result = {"schema": core.SCHEMA, "run_id": run, "mode": "VERIFY", "ok": not problems,
              "problems": problems, "parameter_readbacks": child_readbacks,
              "assignment_readbacks": assignment_readbacks, "dirty_census": census(),
              "visual_acceptance": "not proved; compare the recorded stills plan"}
    write_json(VERIFY_OUT, result)
    if emit:
        unreal.log("J115SHIRTS_VERIFY_%s|run=%s|actors=%d|children=%d|problems=%d|report=%s" %
                   ("OK" if result["ok"] else "FAILED", run, len(assignment_readbacks),
                    len(child_readbacks), len(problems), VERIFY_OUT))
    return result


def revert(run, cfg):
    require(census() == {"content": [], "maps": []}, "DIRTY_AT_START|" + json.dumps(census()))
    record = load_json(RECORD)
    require(record.get("state") == "applied" and record.get("saved") is True, "RECORD_NOT_APPLIED")
    require(verify(run, cfg, record, emit=False)["ok"], "STATE_DRIFT")
    world, actors = clean_context(True)
    scope = actor_scope(actors)
    by_path = {row["path"]: row for row in scope}
    backup = backup_map("REVERT-" + run)
    restored = []
    for row in record["assignments"]:
        live = by_path[row["actor_path"]]
        component = outfit_component(live["actor"])
        component.modify()
        for slot in row["slots"]:
            original = unreal.load_asset(row["resolved_before"][slot])
            require(original is not None, "ORIGINAL_LOAD|" + str(row["resolved_before"][slot]))
            component.set_material(slot, original)
        got = [path_of(component.get_material(i)) for i in range(component.get_num_materials())]
        require(all(got[i] == row["resolved_before"][i] for i in row["slots"]),
                "REVERT_SLOT_READBACK|" + row["label"])
        restored.append({"label": row["label"], "actor_path": row["actor_path"], "slots": row["slots"],
                         "resolved": got})
    save_exact([], world, True)
    record["revert"] = {"run_id": run, "backup": backup, "restored": restored,
                        "created_assets_retained": [row["path"] for row in record["created_children"]]}
    record["state"] = "reverted"
    moved = RECORD + ".reverted-" + run
    write_json(RECORD, record)
    os.replace(RECORD, moved)
    unreal.log("J115SHIRTS_REVERT_OK|run=%s|actors=%d|created_assets_retained=%d|record=%s|dirty=0" %
               (run, len(restored), len(record["created_children"]), moved))
    return record["revert"]


def main():
    run = datetime.datetime.now().strftime("J115SHIRTS-%Y%m%d-%H%M%S")
    mode = "DRY"
    try:
        raw = load_json(ARGS)
        cfg = core.validate_args(raw, os.path.isfile(RECORD))
        mode = cfg["mode"]
        unreal.log("J115SHIRTS_START|run=%s|mode=%s" % (run, mode))
        if mode == "DRY":
            return dry(run, cfg)
        if mode == "APPLY":
            return apply(run, cfg)
        if mode == "VERIFY":
            return verify(run, cfg)
        return revert(run, cfg)
    except Exception as exc:
        dirty = {}
        try:
            dirty = census()
        except Exception:
            pass
        unreal.log_error("J115SHIRTS_FAILED|run=%s|mode=%s|%s|census=%s|NOTHING SAVED unless an *_OK marker printed; Don't-Save restart if dirty|trace=%s" %
                         (run, mode, str(exc).replace("\n", " "), json.dumps(dirty),
                          traceback.format_exc().replace("\n", "\\n")))
        raise


if unreal is not None and __name__ == "<run_path>":
    main()

