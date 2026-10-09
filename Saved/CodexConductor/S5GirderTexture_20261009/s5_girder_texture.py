"""Job 98: guarded S5 girder/hangar surface pass (DRY/APPLY/REVERT).

Offline-authored; the conductor runs this later through ExecuteProjectPythonFile.

Deduplication decision: reuse the existing create-only M_UP_PaintedSteel graph.  It
already owns rust/chip/grime/rivet-normal logic, so this tool creates only two child
MIs and never edits or deletes a node on any pre-existing asset.

Scope:
* Structure 05: Gridiron.Material, Underpass.ColumnMaterial, Underpass.KneeMaterial.
* S5 hangar lattice StaticMeshActors whose labels are exactly
  ``S5 Hangar Lattice Beam NN`` or ``S5 Hangar Lattice Rail N``.
* No light, fog, exposure, camera, sequence, mesh or transform property is written.

APPLY writes an originals record and a verified Backups/PreS5GirderTexture-* copy of
the level before mutation, saves only the two new MIs and the named level, then reads
all assignments back.  REVERT restores assignments and intentionally retains the
created MIs: project policy forbids permanent deletion without separate approval.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import sys

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None

HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = "s5_girder_texture_args.json"
RECORD = "s5_girder_texture_record.json"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
WORLD_REL = os.path.join("Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
STRUCTURE_LABEL = "Infinity Stage - Structure 05"
PARENT = "/Game/InfinityStage/RigAtmos/Underpass/Materials/M_UP_PaintedSteel"
MI_ROOT = "/Game/InfinityStage/RigAtmos/Underpass/Materials/S5Surface"
MI_RIG = MI_ROOT + "/MI_S5_Girder_Rig"
MI_HANGAR = MI_ROOT + "/MI_S5_Girder_Hangar"
TARGET_MIS = (MI_RIG, MI_HANGAR)
HANGAR_RE = re.compile(r"^S5 Hangar Lattice (Beam \d{2}|Rail \d+)$")
STRUCT_FIELDS = (("gridiron", "material"), ("underpass", "column_material"),
                 ("underpass", "knee_material"))
COMP_TAGS = {"grid": "InfinityStage.Structure.Gridiron",
             "columns": "InfinityStage.Structure.Underpass.Columns",
             "knees": "InfinityStage.Structure.Underpass.Knees"}
RIG_SCALARS = {"RustTileM": 0.70, "ChipTileM": 0.95, "ChipThreshold": 0.52,
               "ChipAmount": 1.0, "StreakAmount": 0.55, "PaintRoughness": 0.48,
               "RustRoughness": 0.88, "GrimeAmount": 0.62, "RustNormalStrength": 0.90,
               "RivetHeight": 0.85}
HANGAR_SCALARS = {"RustTileM": 0.10, "ChipTileM": 0.14, "ChipThreshold": 0.54,
                  "ChipAmount": 0.90, "StreakAmount": 0.40, "PaintRoughness": 0.52,
                  "RustRoughness": 0.88, "GrimeAmount": 0.55, "RustNormalStrength": 0.85,
                  "RivetHeight": 0.75}
VECTORS = {"PaintColor": (0.032, 0.055, 0.035), "BandColor": (0.010, 0.011, 0.010),
           "RustColor": (0.22, 0.075, 0.025)}
TOL = 1e-4


class ToolError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise ToolError(str(message))


def validate_args(args):
    out = dict(args)
    out["mode"] = str(out.get("mode", "DRY")).upper()
    require(out["mode"] in ("DRY", "APPLY", "REVERT"), "MODE|DRY/APPLY/REVERT required")
    if out["mode"] != "DRY":
        require(out.get("confirm") == out["mode"] + " S5GIRDERTEXTURE",
                "CONFIRM|%s S5GIRDERTEXTURE required" % out["mode"])
    out.setdefault("rig_scalars", dict(RIG_SCALARS))
    out.setdefault("hangar_scalars", dict(HANGAR_SCALARS))
    out.setdefault("vectors", {k: list(v) for k, v in VECTORS.items()})
    for group, defaults in (("rig_scalars", RIG_SCALARS), ("hangar_scalars", HANGAR_SCALARS)):
        require(set(out[group]) == set(defaults), "%s_KEYS|%s" % (group, sorted(out[group])))
        for name, value in out[group].items():
            require(isinstance(value, (int, float)) and not isinstance(value, bool), "%s.%s_NUMBER" % (group, name))
            require(0.0 <= float(value) <= (4.0 if name.endswith("TileM") else 1.0),
                    "%s.%s_RANGE|%s" % (group, name, value))
    require(set(out["vectors"]) == set(VECTORS), "VECTOR_KEYS|%s" % sorted(out["vectors"]))
    for name, rgb in out["vectors"].items():
        require(isinstance(rgb, list) and len(rgb) == 3 and all(isinstance(x, (int, float)) for x in rgb),
                "VECTOR_RGB|%s|%s" % (name, rgb))
        require(all(0.0 <= float(x) <= 1.0 for x in rgb), "VECTOR_RANGE|%s|%s" % (name, rgb))
    return out


def select_hangar_labels(labels):
    """Pure selector: exact labels only; similarly named walls/practicals never enter scope."""
    return sorted(x for x in labels if HANGAR_RE.fullmatch(x))


def selection_problems(labels):
    chosen = select_hangar_labels(labels)
    kinds = {"beam": sum(" Beam " in x for x in chosen), "rail": sum(" Rail " in x for x in chosen)}
    problems = []
    if not kinds["beam"]:
        problems.append("no S5 lattice beams")
    if not kinds["rail"]:
        problems.append("no S5 lattice rails")
    return chosen, kinds, problems


def assignment_mismatch(want, got):
    return sorted(k for k, v in want.items() if got.get(k) != v)


def scalar_mismatch(want, got, tol=TOL):
    return sorted(k for k, v in want.items() if k not in got or abs(float(got[k]) - float(v)) > tol)


def dirty_problems(content, maps, allowed_content, world=WORLD):
    problems = []
    extra_c = sorted(set(content) - set(allowed_content))
    if extra_c:
        problems.append("unexpected content dirty: %s" % extra_c)
    if sorted(maps) != [world]:
        problems.append("dirty maps %s != [%s]" % (sorted(maps), world))
    return problems


def _json(path, value=None, exclusive=False):
    if value is None:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    with open(path, encoding="utf-8") as handle:
        require(json.load(handle) == json.loads(json.dumps(value)), "JSON_READBACK|" + path)


def _asset_id(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj else None


def _pk(value):
    text = str(value)
    return text.split("'")[1].split(".")[0] if "'" in text else text.split(".")[0]


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(_pk(x) for x in lib.get_dirty_content_packages()),
            "maps": sorted(_pk(x) for x in lib.get_dirty_map_packages())}


def world_and_actors():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(ed.get_game_world() is None, "PIE_ACTIVE")
    world = ed.get_editor_world()
    require(world is not None and _asset_id(world) == WORLD,
            "WORLD|%s" % (_asset_id(world) if world else None))
    require(census() == {"content": [], "maps": []}, "DIRTY_START|" + json.dumps(census()))
    return world, list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def find_targets(actors):
    structures = [a for a in actors if a.get_actor_label() == STRUCTURE_LABEL]
    require(len(structures) == 1 and isinstance(structures[0], unreal.InfinityStageStructureActor),
            "STRUCTURE05|expected one InfinityStageStructureActor, found %d" % len(structures))
    by_label = {a.get_actor_label(): a for a in actors}
    labels, kinds, problems = selection_problems(list(by_label))
    raw_selected = [a.get_actor_label() for a in actors if HANGAR_RE.fullmatch(a.get_actor_label())]
    require(len(raw_selected) == len(set(raw_selected)), "HANGAR_DUPLICATE_LABELS|" + json.dumps(raw_selected))
    require(not problems, "HANGAR_CENSUS|" + "; ".join(problems))
    hangar = []
    for label in labels:
        actor = by_label[label]
        comps = list(actor.get_components_by_class(unreal.StaticMeshComponent))
        require(len(comps) == 1, "HANGAR_COMPONENTS|%s|%d" % (label, len(comps)))
        require(int(comps[0].get_num_materials()) == 1, "HANGAR_SLOTS|%s|%d" % (label, comps[0].get_num_materials()))
        hangar.append((actor, comps[0]))
    return structures[0], hangar, kinds


def struct_assignments(structure):
    out = {}
    for group, field in STRUCT_FIELDS:
        out[group + "." + field] = _asset_id(structure.get_editor_property(group).get_editor_property(field))
    return out


def component_rows(hangar):
    rows = []
    for actor, comp in hangar:
        mesh = comp.get_editor_property("static_mesh")
        rows.append({"label": actor.get_actor_label(), "actor": actor.get_path_name(),
                     "component": comp.get_path_name(), "mesh": _asset_id(mesh),
                     "material": _asset_id(comp.get_material(0)),
                     "slots": int(comp.get_num_materials())})
    return sorted(rows, key=lambda x: x["label"])


def managed_rows(structure):
    out = {}
    managed = [x for x in structure.get_editor_property("managed_components") if x]
    for name, tag in COMP_TAGS.items():
        comps = [x for x in managed if tag in [str(t) for t in x.get_editor_property("component_tags")]]
        require(len(comps) == 1, "MANAGED_COMPONENT|%s|%d" % (name, len(comps)))
        comp = comps[0]
        out[name] = {"component": comp.get_path_name(), "mesh": _asset_id(comp.get_editor_property("static_mesh")),
                     "material": _asset_id(comp.get_material(0)),
                     "instances": int(comp.get_instance_count())}
    return out


def inventory(structure, hangar, kinds):
    return {"structure": STRUCTURE_LABEL, "structure_fields": struct_assignments(structure),
            "managed": managed_rows(structure), "hangar_counts": kinds,
            "hangar_lattice": component_rows(hangar)}


def make_mi(path, scalars, vectors):
    require(not unreal.EditorAssetLibrary.does_asset_exist(path), "CREATE_ONLY_EXISTS|" + path)
    parent = unreal.EditorAssetLibrary.load_asset(PARENT)
    require(parent is not None, "PARENT_MISSING|" + PARENT)
    mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        path.rsplit("/", 1)[1], path.rsplit("/", 1)[0], unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew())
    require(mi is not None, "MI_CREATE|" + path)
    mel = unreal.MaterialEditingLibrary
    mi.modify()
    mel.set_material_instance_parent(mi, parent)
    require(_asset_id(mi.get_editor_property("parent")) == PARENT, "MI_PARENT_READBACK|" + path)
    names = {str(x) for x in mel.get_scalar_parameter_names(mi)}
    require(set(scalars) <= names, "MI_SCALARS_MISSING|%s|%s" % (path, sorted(set(scalars) - names)))
    for name, value in scalars.items():
        mel.set_material_instance_scalar_parameter_value(mi, name, float(value))
    for name, rgb in vectors.items():
        mel.set_material_instance_vector_parameter_value(mi, name, unreal.LinearColor(*rgb, 1.0))
    mel.update_material_instance(mi)
    got = {n: float(mel.get_material_instance_scalar_parameter_value(mi, n)) for n in scalars}
    require(not scalar_mismatch(scalars, got), "MI_SCALAR_READBACK|%s|%s" % (path, got))
    got_v = {n: mel.get_material_instance_vector_parameter_value(mi, n) for n in vectors}
    bad_v = [n for n, rgb in vectors.items()
             if any(abs(float(a) - float(b)) > TOL for a, b in zip(
                 (got_v[n].r, got_v[n].g, got_v[n].b), rgb))]
    require(not bad_v, "MI_VECTOR_READBACK|%s|%s" % (path, bad_v))
    return mi


def set_structure_materials(structure, material):
    structure.modify()
    for group, field in STRUCT_FIELDS:
        value = structure.get_editor_property(group)
        value.set_editor_property(field, material)
        structure.set_editor_property(group, value)
    require(not assignment_mismatch({g + "." + f: _asset_id(material) for g, f in STRUCT_FIELDS},
                                    struct_assignments(structure)), "STRUCT_SET_READBACK")
    require(structure.materialize_structure(), "MATERIALIZE_STRUCTURE_FALSE")


def set_hangar_materials(hangar, by_label):
    for actor, comp in hangar:
        label = actor.get_actor_label()
        path = by_label[label] if isinstance(by_label, dict) else by_label
        material = unreal.EditorAssetLibrary.load_asset(path) if isinstance(path, str) else path
        require(material is not None, "MATERIAL_LOAD|%s|%s" % (label, path))
        actor.modify(); comp.modify(); comp.set_material(0, material)
        require(_asset_id(comp.get_material(0)) == _asset_id(material), "HANGAR_SET_READBACK|" + label)


def write_structure_paths(structure, paths):
    structure.modify()
    for group, field in STRUCT_FIELDS:
        path = paths[group + "." + field]
        asset = unreal.EditorAssetLibrary.load_asset(path) if path else None
        require(path is None or asset is not None, "ORIGINAL_LOAD|" + str(path))
        value = structure.get_editor_property(group)
        value.set_editor_property(field, asset)
        structure.set_editor_property(group, value)
    require(not assignment_mismatch(paths, struct_assignments(structure)), "STRUCT_RESTORE_READBACK")
    require(structure.materialize_structure(), "MATERIALIZE_REVERT_FALSE")


def backup_level(run):
    repo = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    src = os.path.join(repo, WORLD_REL)
    require(os.path.isfile(src), "BACKUP_SOURCE|" + src)
    root = os.path.join(repo, "Backups", "PreS5GirderTexture-" + run.split("-", 1)[1])
    dst = os.path.join(root, WORLD_REL)
    os.makedirs(os.path.dirname(dst), exist_ok=False)
    shutil.copy2(src, dst)
    digest = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    require(digest(src) == digest(dst), "BACKUP_HASH|" + dst)
    _json(os.path.join(root, "prechange.json"), {"run": run, "source": src, "backup": dst,
                                                 "sha256": digest(src)}, exclusive=True)
    return dst


def save_and_readback(run, allowed_content, want_struct, want_hangar):
    now = census()
    require(not dirty_problems(now["content"], now["maps"], allowed_content),
            "DIRTY_SCOPE|" + json.dumps(now, sort_keys=True))
    for path in allowed_content:
        require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), "SAVE_ASSET|" + path)
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "SAVE_LEVEL")
    require(census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|" + json.dumps(census()))
    _, actors = world_and_actors()
    structure, hangar, kinds = find_targets(actors)
    got_s = struct_assignments(structure)
    got_h = {x["label"]: x["material"] for x in component_rows(hangar)}
    require(not assignment_mismatch(want_struct, got_s), "SAVED_STRUCT_READBACK|" + json.dumps(got_s))
    require(not assignment_mismatch(want_hangar, got_h), "SAVED_HANGAR_READBACK|" + json.dumps(got_h))
    require(bool(structure.is_structure_current()), "STRUCTURE_NOT_CURRENT_AFTER_SAVE")
    return inventory(structure, hangar, kinds)


def dry(args):
    _, actors = world_and_actors()
    structure, hangar, kinds = find_targets(actors)
    existing = [p for p in TARGET_MIS if unreal.EditorAssetLibrary.does_asset_exist(p)]
    active = os.path.isfile(os.path.join(HERE, RECORD))
    require(not existing and not active, "CREATE_ONLY_OCCUPIED|assets=%s|record=%s" % (existing, active))
    inv = inventory(structure, hangar, kinds)
    run = "S5GT-DRY-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    result = {"run": run, "mode": "DRY", "marker": "S5_GIRDER_TEXTURE_DRY_OK",
              "parent": PARENT, "create": list(TARGET_MIS), "inventory": inv,
              "look_values": {"rig_scalars": args["rig_scalars"], "hangar_scalars": args["hangar_scalars"],
                              "vectors": args["vectors"]},
              "writes": {"fog": False, "brightness": False, "lighting": False,
                         "sequence": False, "meshes": False, "transforms": False}}
    _json(os.path.join(HERE, "s5_girder_texture_dry_%s.json" % run), result)
    unreal.log("S5_GIRDER_TEXTURE_DRY_OK|run=%s|rig=%s|beams=%d|rails=%d" %
               (run, json.dumps(inv["managed"], sort_keys=True), kinds["beam"], kinds["rail"]))
    return result


def apply(args):
    require(not os.path.exists(os.path.join(HERE, RECORD)), "ACTIVE_RECORD_EXISTS")
    _, actors = world_and_actors()
    structure, hangar, kinds = find_targets(actors)
    require(not [p for p in TARGET_MIS if unreal.EditorAssetLibrary.does_asset_exist(p)], "CREATE_ONLY_EXISTS")
    before = inventory(structure, hangar, kinds)
    require(all(x["material"] for x in before["hangar_lattice"]), "HANGAR_ORIGINAL_MATERIAL_NULL")
    run = "S5GT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    record = {"run": run, "state": "ORIGINALS_WRITTEN", "world": WORLD, "parent": PARENT,
              "look_values": {"rig_scalars": args["rig_scalars"], "hangar_scalars": args["hangar_scalars"],
                              "vectors": args["vectors"]},
              "created": list(TARGET_MIS), "before": before,
              "hangar_originals": {x["label"]: x["material"] for x in before["hangar_lattice"]}}
    _json(os.path.join(HERE, RECORD), record, exclusive=True)
    record["backup"] = backup_level(run)
    _json(os.path.join(HERE, RECORD), record)
    mutated = False
    try:
        rig_mi = make_mi(MI_RIG, args["rig_scalars"], args["vectors"])
        hangar_mi = make_mi(MI_HANGAR, args["hangar_scalars"], args["vectors"])
        mutated = True
        set_structure_materials(structure, rig_mi)
        set_hangar_materials(hangar, hangar_mi)
        want_s = {g + "." + f: MI_RIG for g, f in STRUCT_FIELDS}
        want_h = {actor.get_actor_label(): MI_HANGAR for actor, _ in hangar}
        after = save_and_readback(run, list(TARGET_MIS), want_s, want_h)
    except Exception as exc:
        record.update(state="REFUSED_UNSAVED", error="%s: %s" % (type(exc).__name__, exc))
        _json(os.path.join(HERE, RECORD), record)
        unreal.log_error("S5_GIRDER_TEXTURE_FAILED|run=%s|NOT SAVED; Don't-Save restart|required=%s" % (run, mutated))
        raise
    record.update(state="APPLIED", after=after)
    _json(os.path.join(HERE, RECORD), record)
    unreal.log("S5_GIRDER_TEXTURE_APPLY_OK|run=%s|structure=3 fields|beams=%d|rails=%d|dirty_after=0+0" %
               (run, kinds["beam"], kinds["rail"]))
    return record


def revert(args):
    path = os.path.join(HERE, RECORD)
    require(os.path.isfile(path), "NO_ACTIVE_RECORD")
    record = _json(path)
    require(record.get("state") == "APPLIED", "RECORD_STATE|" + str(record.get("state")))
    _, actors = world_and_actors()
    structure, hangar, kinds = find_targets(actors)
    want_applied_s = {g + "." + f: MI_RIG for g, f in STRUCT_FIELDS}
    want_applied_h = {actor.get_actor_label(): MI_HANGAR for actor, _ in hangar}
    require(not assignment_mismatch(want_applied_s, struct_assignments(structure)), "APPLIED_STRUCT_DRIFT")
    require(not assignment_mismatch(want_applied_h, {x["label"]: x["material"] for x in component_rows(hangar)}),
            "APPLIED_HANGAR_DRIFT")
    run = "S5GT-REVERT-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_level(run)
    write_structure_paths(structure, record["before"]["structure_fields"])
    set_hangar_materials(hangar, record["hangar_originals"])
    after = save_and_readback(run, [], record["before"]["structure_fields"], record["hangar_originals"])
    record.update(state="REVERTED", revert_run=run, revert_backup=backup, after_revert=after,
                  created_assets_retained=list(TARGET_MIS))
    archived = path + ".reverted-" + run
    _json(path, record)
    os.replace(path, archived)
    result = {"run": run, "mode": "REVERT", "marker": "S5_GIRDER_TEXTURE_REVERT_OK",
              "record": archived, "created_assets_retained": list(TARGET_MIS), "readback": after}
    _json(os.path.join(HERE, "s5_girder_texture_revert_%s.json" % run), result)
    unreal.log("S5_GIRDER_TEXTURE_REVERT_OK|run=%s|assets_retained=2|dirty_after=0+0" % run)
    return result


def main():
    require(unreal is not None, "UNREAL_REQUIRED")
    args = validate_args(_json(os.path.join(HERE, ARGS)))
    unreal.log("S5_GIRDER_TEXTURE_START|mode=%s" % args["mode"])
    result = {"DRY": dry, "APPLY": apply, "REVERT": revert}[args["mode"]](args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__" or ("unreal" in sys.modules and not getattr(sys.modules.get("unreal"), "_S5GT_FAKE", False)):
    main()
