"""Guarded UE editor tool for P12 B06-only dense handprints.  The conductor runs this later; never import offline.

Modes (HP_DENSE_MODE):
  ASSET_DRY / ASSET_APPLY / ASSET_VERIFY
      Build <=16 child MIs per APPLY under GreaseDense.  They copy the existing tint crop/flip parameters and override
      only TintColor/TintStrength/TintLo/TintHi from the placement table.  APPLY needs
      "APPLY P12 DENSE MATERIALS".  Creation markers say NOT_YET_VERIFIED; a later ASSET_VERIFY call is mandatory.
  DRY / APPLY / REVERT_DRY / REVERT
      Replace the saved HP_S03G sheen layer and optional HP_S03T colour twins with B06-only HP_S03D sheen plus
      HP_S03D_CORE BaseColor-only twins. APPLY needs "APPLY P12 DENSE HANDPRINTS". REVERT needs
      "REVERT P12 DENSE HANDPRINTS" and restores every snapshotted actor field.  Dense material assets are retained,
      unreferenced, on REVERT; nothing is permanently deleted.

Every mutating mode requires a clean exact census, creates a Backups/PreP12...-<run> snapshot and a record before
the first mutation, saves only named MI packages or the current level, reads back, and prints success only after the
asserted post-save read-back.  Never Save All, reload, end PIE, stop, quit, or touch the Show asset.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sys
import traceback

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import hp_dense_core as core

EXPECTED_WORLD = core.LEVEL
PROJECT_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
TABLE = os.path.join(HERE, "placement_S03_dense.json")
TABLE_SHA256 = "8b698816532de024cbc7b3017f8681c4e1581747a32c9244ece465d843320ab4"
SOURCE_TABLE = os.path.join(os.path.dirname(HERE), "clamber", "placement_S03_grease.json")
ASSET_RECORD = os.path.join(HERE, "hp_dense_asset_record.json")
PLACE_RECORD = os.path.join(HERE, "hp_dense_place_record.json")
MODE = str(globals().get("HP_DENSE_MODE", "DRY")).upper()
CONFIRM = globals().get("HP_DENSE_CONFIRM")
RUN = str(globals().get("HP_DENSE_RUN") or datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
MI_BATCH_MAX = 16
POS_TOL_CM, AXIS_DOT_MIN = 0.05, 0.9999
SOURCE_TAGS = ("HP_S03G", "HP_S03T")
DENSE_TAGS = ("HP_S03D", "HP_S03D_CORE")
DENSE_FOLDERS = {"HP_S03D": "HandPrints/S03_Dense", "HP_S03D_CORE": "HandPrints/S03_DenseCore"}


class ToolError(RuntimeError):
    pass


def require(cond, message):
    if not cond:
        raise ToolError(message)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as fh:
        json.dump(value, fh, indent=1, sort_keys=True)
        fh.flush(); os.fsync(fh.fileno())


def load_table():
    require(os.path.isfile(TABLE), "TABLE_MISSING")
    require(sha256(TABLE) == TABLE_SHA256, "TABLE_SHA256_MISMATCH")
    with open(TABLE, encoding="utf-8") as fh:
        table = json.load(fh)
    core.validate_table(table)
    return table


def path_of(obj):
    return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def rpy(r):
    return [float(r.roll), float(r.pitch), float(r.yaw)]


def ang(a, b):
    return abs(((a - b) + 180.0) % 360.0 - 180.0)


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def census():
    def names(packages):
        return sorted(str(p.get_path_name()).split(".", 1)[0] for p in packages)
    return {"maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def world_checked(clean=True):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None and str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_WORLD")
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    if clean:
        require(census() == {"maps": [], "content": []}, "DIRTY_AT_START|" + json.dumps(census()))
    return world


def all_actors(world):
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


def tagged(world, tag):
    return [a for a in all_actors(world) if tag in [str(t) for t in a.get_editor_property("tags")]]


def temp_actors(world):
    return [str(a.get_actor_label()) for a in all_actors(world)
            if str(a.get_actor_label()).startswith("ZZ_") or "TEMP" in str(a.get_actor_label()).upper()]


def label_index(world):
    out = {}
    for actor in all_actors(world):
        out.setdefault(str(actor.get_actor_label()), []).append(actor)
    return out


def decal_comp(actor):
    return actor.get_editor_property("decal")


def snapshot(actor):
    comp = decal_comp(actor)
    parent = actor.get_attach_parent_actor()
    return {"label": str(actor.get_actor_label()), "folder": str(actor.get_folder_path()),
            "tags": [str(t) for t in actor.get_editor_property("tags")],
            "location": vec(actor.get_actor_location()), "rotation": rpy(actor.get_actor_rotation()),
            "scale": vec(actor.get_actor_scale3d()),
            "parent_label": str(parent.get_actor_label()) if parent else None,
            "material": path_of(comp.get_decal_material()), "decal_size": vec(comp.get_editor_property("decal_size")),
            "sort_order": int(comp.get_editor_property("sort_order")),
            "fade_screen_size": float(comp.get_editor_property("fade_screen_size")),
            "mobility": str(comp.get_editor_property("mobility")), "object_path": actor.get_path_name()}


def restore_diff(actor, expected):
    got = snapshot(actor); bad = []
    for key in ("label", "folder", "tags", "parent_label", "material", "sort_order", "mobility"):
        if got[key] != expected[key]: bad.append(key)
    if max(abs(a - b) for a, b in zip(got["location"], expected["location"])) > POS_TOL_CM: bad.append("location")
    if max(ang(a, b) for a, b in zip(got["rotation"], expected["rotation"])) > 0.01: bad.append("rotation")
    if max(abs(a - b) for a, b in zip(got["scale"], expected["scale"])) > 1e-4: bad.append("scale")
    if max(abs(a - b) for a, b in zip(got["decal_size"], expected["decal_size"])) > 1e-3: bad.append("decal_size")
    if abs(got["fade_screen_size"] - expected["fade_screen_size"]) > 1e-9: bad.append("fade")
    return bad


def level_file():
    return os.path.join(PROJECT_DIR, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap"


def backup_level(prefix):
    src = level_file(); require(os.path.isfile(src), "LEVEL_FILE_MISSING")
    root = os.path.join(PROJECT_DIR, "Backups", prefix + RUN)
    require(not os.path.exists(root), "BACKUP_EXISTS|" + root)
    dst = os.path.join(root, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap"
    os.makedirs(os.path.dirname(dst)); shutil.copy2(src, dst)
    require(sha256(src) == sha256(dst), "BACKUP_HASH_MISMATCH")
    return root


def backup_materials(table):
    rel = table["material"]["dark_dir"][len("/Game/"):]
    src = os.path.join(PROJECT_DIR, "Content", *rel.split("/"))
    root = os.path.join(PROJECT_DIR, "Backups", "PreP12HandprintMaterials-" + RUN)
    require(not os.path.exists(root), "BACKUP_EXISTS|" + root)
    os.makedirs(root)
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(root, "Content", *rel.split("/")))
    write_json(os.path.join(root, "manifest.json"), {"run": RUN, "source": src,
                                                      "source_existed": os.path.isdir(src), "table": TABLE,
                                                      "table_sha256": TABLE_SHA256})
    return root


# --------------------------------------------------------------------------------------------- material modes
def asset_items(table):
    m = table["material"]
    out = []
    for item in table["dark_mi_worklist"]:
        out.append(dict(item, source_path=m["source_tint_dir"] + "/" + item["source_tint"],
                        dark_path=m["dark_dir"] + "/" + item["dark"]))
    return out


def asset_dry(table):
    world_checked()
    m = table["material"]
    require(unreal.EditorAssetLibrary.does_asset_exist(m["dark_master"]), "DARK_MASTER_MISSING")
    items = asset_items(table)
    missing = [i["source_tint"] for i in items if not unreal.EditorAssetLibrary.does_asset_exist(i["source_path"])]
    require(not missing, "SOURCE_TINT_MI_MISSING|" + json.dumps(missing[:5]))
    existing = [i["dark"] for i in items if unreal.EditorAssetLibrary.does_asset_exist(i["dark_path"])]
    if existing:
        require(os.path.isfile(ASSET_RECORD), "DARK_MI_EXISTS_UNRECORDED|" + json.dumps(existing[:5]))
    require(census() == {"maps": [], "content": []}, "ASSET_DRY_DIRTIED")
    unreal.log("P12_DENSE_ASSET_DRY_OK|run=%s|planned=%d|existing=%d|mutated=0" % (RUN, len(items), len(existing)))


def asset_apply(table):
    core.check_confirm(MODE, CONFIRM)
    world_checked()
    m = table["material"]; items = asset_items(table)
    if os.path.isfile(ASSET_RECORD):
        with open(ASSET_RECORD, encoding="utf-8") as fh: rec = json.load(fh)
        require(rec["table_sha256"] == TABLE_SHA256, "ASSET_RECORD_TABLE_CHANGED")
    else:
        backup = backup_materials(table)
        rec = {"schema": "hp_dense_assets/1", "table": TABLE, "table_sha256": TABLE_SHA256,
               "backup": backup, "created": [], "batches": [], "verified": False}
        write_json(ASSET_RECORD, rec, exclusive=True)  # before first create
    done = set(rec["created"])
    batch = [i for i in items if i["dark"] not in done][:MI_BATCH_MAX]
    if not batch:
        require(census() == {"maps": [], "content": []}, "ASSET_NOTHING_DIRTY")
        unreal.log("P12_DENSE_ASSET_NOTHING_TO_DO|run=%s|done=%d" % (RUN, len(done))); return
    for item in batch:
        require(not unreal.EditorAssetLibrary.does_asset_exist(item["dark_path"]),
                "DARK_MI_EXISTS_UNRECORDED|" + item["dark"])
    master = unreal.load_asset(m["dark_master"]); require(master is not None, "DARK_MASTER_LOAD")
    mel = unreal.MaterialEditingLibrary
    params = m["dark_parameters"]
    created = []
    for item in batch:
        source = unreal.load_asset(item["source_path"]); require(source is not None, "SOURCE_LOAD|" + item["source_tint"])
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            item["dark"], m["dark_dir"], unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        require(mi is not None, "CREATE_FAILED|" + item["dark"])
        mel.set_material_instance_parent(mi, master)
        for key in ("AtlasU0", "AtlasV0", "AtlasUSize", "AtlasVSize", "FlipU"):
            value = float(mel.get_material_instance_scalar_parameter_value(source, key))
            mel.set_material_instance_scalar_parameter_value(mi, key, value)
        mel.set_material_instance_scalar_parameter_value(mi, "TintStrength", float(params["strength"]))
        mel.set_material_instance_scalar_parameter_value(mi, "TintLo", float(params["lo"]))
        mel.set_material_instance_scalar_parameter_value(mi, "TintHi", float(params["hi"]))
        color = params["color_linear"]
        mel.set_material_instance_vector_parameter_value(mi, "TintColor", unreal.LinearColor(*color))
        mel.update_material_instance(mi)
        require(unreal.EditorAssetLibrary.save_loaded_asset(mi, only_if_is_dirty=False), "MI_SAVE|" + item["dark"])
        created.append(item["dark"])
    require(census() == {"maps": [], "content": []}, "ASSET_POST_SAVE_DIRTY|" + json.dumps(census()))
    rec["created"] = sorted(done | set(created)); rec["verified"] = False
    rec["batches"].append({"run": RUN, "names": created})
    write_json(ASSET_RECORD, rec)
    unreal.SystemLibrary.collect_garbage()
    unreal.log("P12_DENSE_ASSET_BUILT|run=%s|created=%d|done=%d|remaining=%d|NOT_YET_VERIFIED" %
               (RUN, len(created), len(rec["created"]), len(items) - len(rec["created"])))


def asset_verify(table):
    world_checked()
    require(os.path.isfile(ASSET_RECORD), "ASSET_RECORD_MISSING")
    with open(ASSET_RECORD, encoding="utf-8") as fh: rec = json.load(fh)
    require(all(b["run"] != RUN for b in rec["batches"]), "SAME_CALL_AS_ASSET_APPLY")
    items = asset_items(table); require(set(rec["created"]) == {i["dark"] for i in items}, "ASSETS_INCOMPLETE")
    m = table["material"]; params = m["dark_parameters"]; mel = unreal.MaterialEditingLibrary; bad = []
    for item in items:
        mi = unreal.load_asset(item["dark_path"])
        if not isinstance(mi, unreal.MaterialInstanceConstant): bad.append("CLASS|" + item["dark"]); continue
        if path_of(mi.get_editor_property("parent")) != m["dark_master"]: bad.append("PARENT|" + item["dark"])
        for key, expected in (("TintStrength", params["strength"]), ("TintLo", params["lo"]), ("TintHi", params["hi"])):
            got = float(mel.get_material_instance_scalar_parameter_value(mi, key))
            if abs(got - expected) > 1e-4: bad.append("PARAM|%s|%s" % (item["dark"], key))
        c = mel.get_material_instance_vector_parameter_value(mi, "TintColor")
        if max(abs(a-b) for a,b in zip((float(c.r), float(c.g), float(c.b), float(c.a)), params["color_linear"])) > 1e-4:
            bad.append("COLOR|" + item["dark"])
    require(not bad, "ASSET_VERIFY|" + json.dumps(bad[:8]))
    require(census() == {"maps": [], "content": []}, "ASSET_VERIFY_DIRTIED")
    rec.update({"verified": True, "verify_run": RUN, "verified_count": len(items)})
    write_json(ASSET_RECORD, rec)
    unreal.log("P12_DENSE_ASSET_VERIFY_SUCCESS|run=%s|verified=%d|preset=%s" %
               (RUN, len(items), m["dark_preset"]))


# --------------------------------------------------------------------------------------------------- level modes
def source_layer(world, table):
    with open(SOURCE_TABLE, encoding="utf-8") as fh: source = json.load(fh)
    grease = sorted(tagged(world, "HP_S03G"), key=lambda a: str(a.get_actor_label()))
    tint = sorted(tagged(world, "HP_S03T"), key=lambda a: str(a.get_actor_label()))
    expected = {r["label"]: r for r in source["decals"]}
    require(len(grease) == len(expected), "SOURCE_GREASE_COUNT|%d|%d" % (len(grease), len(expected)))
    require(len(tint) in (0, len(expected)), "SOURCE_TINT_COUNT|%d" % len(tint))
    for actor in grease:
        label = str(actor.get_actor_label())
        require(isinstance(actor, unreal.DecalActor) and label in expected, "SOURCE_GREASE_FOREIGN|" + label)
        delta = max(abs(a-b) for a,b in zip(vec(actor.get_actor_location()), expected[label]["location"]))
        require(delta <= 0.5, "SOURCE_GREASE_MOVED|%s|%.3f" % (label, delta))
    return grease, tint


def level_gates(world, table, reverting=False):
    require(census() == {"maps": [], "content": []}, "DIRTY_AT_START|" + json.dumps(census()))
    require(not temp_actors(world), "TEMP_ACTORS_PRESENT|" + json.dumps(temp_actors(world)[:10]))
    if reverting:
        require(os.path.isfile(PLACE_RECORD), "PLACE_RECORD_MISSING")
        require(not any(tagged(world, t) for t in SOURCE_TAGS), "SOURCE_LAYER_PRESENT_DURING_REVERT")
        for tag in DENSE_TAGS:
            require(len(tagged(world, tag)) == len(table["decals"]), "DENSE_COUNT|%s|%d" % (tag, len(tagged(world, tag))))
        return
    require(not os.path.exists(PLACE_RECORD), "PLACE_RECORD_EXISTS")
    require(not any(tagged(world, t) for t in DENSE_TAGS), "DENSE_LAYER_ALREADY_PRESENT")
    require(os.path.isfile(ASSET_RECORD), "ASSET_RECORD_MISSING")
    with open(ASSET_RECORD, encoding="utf-8") as fh: arec = json.load(fh)
    require(arec.get("verified") is True and arec.get("table_sha256") == TABLE_SHA256, "ASSETS_NOT_VERIFIED")
    return source_layer(world, table)


def spawn_row(row, wall, table, run, core_layer):
    material = table["material"]
    name = row["dark_material_instance"] if core_layer else row["material_instance"]
    path = (material["dark_dir"] if core_layer else material["sheen_dir"]) + "/" + name
    mat = unreal.load_asset(path); require(mat is not None, "MATERIAL_LOAD|" + path)
    rot = row["rotation"]
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        unreal.DecalActor, unreal.Vector(*row["location"]),
        unreal.Rotator(roll=rot["roll"], pitch=rot["pitch"], yaw=rot["yaw"]))
    require(actor is not None, "SPAWN_FAILED|" + row["label"])
    tag = "HP_S03D_CORE" if core_layer else "HP_S03D"
    label = row["core_label"] if core_layer else row["label"]
    actor.modify(); actor.set_actor_label(label)
    actor.modify(); actor.set_folder_path(DENSE_FOLDERS[tag])
    actor.modify(); actor.set_editor_property("tags", [unreal.Name(tag), unreal.Name(tag + ".run." + run)])
    comp = decal_comp(actor); comp.modify(); comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    comp.modify(); comp.set_decal_material(mat)
    comp.modify(); comp.set_editor_property("decal_size", unreal.Vector(*row["decal_size"]))
    comp.modify(); comp.set_sort_order(int(row["sort_order"]) + (2 if core_layer else 0))
    comp.modify(); comp.set_fade_screen_size(0.0)
    actor.modify(); actor.attach_to_actor(wall, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD,
                                          unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    # Immediate actor/component read-back is safe; materials were verified in a separate call.
    require(max(abs(a-b) for a,b in zip(vec(actor.get_actor_location()), row["location"])) <= POS_TOL_CM,
            "LOCATION_READBACK|" + label)
    for axis, fn in (("x", actor.get_actor_forward_vector), ("y", actor.get_actor_right_vector), ("z", actor.get_actor_up_vector)):
        require(dot(vec(fn()), row["axes"][axis]) >= AXIS_DOT_MIN, "AXIS_READBACK|%s|%s" % (label, axis))
    require(path_of(comp.get_decal_material()) == path, "MATERIAL_READBACK|" + label)
    require(actor.get_attach_parent_actor() == wall, "PARENT_READBACK|" + label)
    return actor


def restore_actor(value, parents):
    rot = value["rotation"]
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        unreal.DecalActor, unreal.Vector(*value["location"]), unreal.Rotator(roll=rot[0], pitch=rot[1], yaw=rot[2]))
    require(actor is not None, "RESTORE_SPAWN|" + value["label"])
    actor.modify(); actor.set_actor_label(value["label"])
    actor.modify(); actor.set_folder_path(value["folder"])
    actor.modify(); actor.set_editor_property("tags", [unreal.Name(t) for t in value["tags"]])
    actor.modify(); actor.set_actor_scale3d(unreal.Vector(*value["scale"]))
    comp = decal_comp(actor); mat = unreal.load_asset(value["material"]); require(mat is not None, "RESTORE_MAT")
    comp.modify(); comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    comp.modify(); comp.set_decal_material(mat)
    comp.modify(); comp.set_editor_property("decal_size", unreal.Vector(*value["decal_size"]))
    comp.modify(); comp.set_sort_order(value["sort_order"]); comp.modify(); comp.set_fade_screen_size(value["fade_screen_size"])
    if value["parent_label"]:
        require(value["parent_label"] in parents and len(parents[value["parent_label"]]) == 1, "RESTORE_PARENT")
        actor.modify(); actor.attach_to_actor(parents[value["parent_label"]][0], unreal.Name(""),
                                              unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                                              unreal.AttachmentRule.KEEP_WORLD, False)
    return actor


def save_level(world, present_tags, count_each, absent_tags):
    for tag in absent_tags: require(not tagged(world, tag), "SURVIVOR|" + tag)
    for tag in present_tags: require(len(tagged(world, tag)) == count_each, "COUNT_BEFORE_SAVE|" + tag)
    require(not temp_actors(world), "TEMP_ACTORS_REFUSING_SAVE")
    before = census()
    require(before == {"maps": [EXPECTED_WORLD], "content": []}, "CENSUS_NOT_EXACT_LEVEL|" + json.dumps(before))
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
    require(census() == {"maps": [], "content": []}, "POST_SAVE_DIRTY|" + json.dumps(census()))


def do_apply(world, table, dry):
    grease, tint = level_gates(world, table)
    rows = table["decals"]
    if dry:
        require(census() == {"maps": [], "content": []}, "DRY_DIRTIED")
        unreal.log("P12_DENSE_DRY_OK|run=%s|source_grease=%d|source_tint=%d|marks=%d|spawn=%d|mutated=0" %
                   (RUN, len(grease), len(tint), len(rows), len(rows) * 2)); return
    core.check_confirm(MODE, CONFIRM)
    snapshot_rows = sorted([snapshot(a) for a in grease + tint], key=lambda s: s["label"])
    backup = backup_level("PreP12Handprints-")
    rec = {"schema": "hp_dense_place/1", "run": RUN, "table": TABLE, "table_sha256": TABLE_SHA256,
           "backup": backup, "source_snapshot": snapshot_rows, "source_grease": len(grease),
           "source_tint": len(tint), "planned_marks": len(rows), "saved": False}
    write_json(PLACE_RECORD, rec, exclusive=True)  # before first actor mutation
    idx = label_index(world); right = idx.get("S3 Hangar Right Wall", [])
    require(len(right) == 1, "RIGHT_WALL_COUNT|%d" % len(right)); wall = right[0]
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); made = []; saved = False
    try:
        with unreal.ScopedEditorTransaction("P12 dense B06 handprints run=" + RUN):
            for actor in grease + tint:
                actor.modify(); require(sub.destroy_actor(actor), "DESTROY_SOURCE|" + str(actor.get_actor_label()))
            for row in rows:
                made.append(spawn_row(row, wall, table, RUN, False))
                made.append(spawn_row(row, wall, table, RUN, True))
        rec["spawned"] = len(made); write_json(PLACE_RECORD, rec)
        save_level(world, DENSE_TAGS, len(rows), SOURCE_TAGS); saved = True
        for tag in DENSE_TAGS: require(len(tagged(world, tag)) == len(rows), "POST_SAVE_COUNT|" + tag)
        rec.update({"saved": True, "saved_run": RUN}); write_json(PLACE_RECORD, rec)
        unreal.log("P12_DENSE_APPLY_SUCCESS|run=%s|removed=%d|marks=%d|spawned=%d|saved=1|backup=%s" %
                   (RUN, len(snapshot_rows), len(rows), len(made), backup))
    except Exception:
        if not saved:
            rec.update({"failed": True, "needs": "DONT_SAVE_RESTART"}); write_json(PLACE_RECORD, rec)
        raise


def do_revert(world, table, dry):
    level_gates(world, table, reverting=True)
    with open(PLACE_RECORD, encoding="utf-8") as fh: rec = json.load(fh)
    require(rec.get("saved") is True and rec.get("table_sha256") == TABLE_SHA256, "RECORD_NOT_SAVED_APPLY")
    if dry:
        require(census() == {"maps": [], "content": []}, "REVERT_DRY_DIRTIED")
        unreal.log("P12_DENSE_REVERT_DRY_OK|run=%s|dense=%d|restore=%d|mutated=0" %
                   (RUN, len(table["decals"]) * 2, len(rec["source_snapshot"]))); return
    core.check_confirm(MODE, CONFIRM)
    backup = backup_level("PreP12HandprintsRevert-")
    rec.update({"revert_started": True, "revert_run": RUN, "revert_backup": backup})
    write_json(PLACE_RECORD, rec)  # record + backup both exist before the first destroy
    parents = label_index(world); dense = tagged(world, "HP_S03D") + tagged(world, "HP_S03D_CORE")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem); restored = []; saved = False
    try:
        with unreal.ScopedEditorTransaction("P12 dense handprints revert run=" + RUN):
            for actor in dense:
                actor.modify(); require(sub.destroy_actor(actor), "DESTROY_DENSE|" + str(actor.get_actor_label()))
            for value in rec["source_snapshot"]:
                actor = restore_actor(value, parents); restored.append(actor)
                require(not restore_diff(actor, value), "RESTORE_READBACK|%s|%s" %
                        (value["label"], json.dumps(restore_diff(actor, value))))
        for tag in DENSE_TAGS: require(not tagged(world, tag), "DENSE_SURVIVOR|" + tag)
        require(len(tagged(world, "HP_S03G")) == rec["source_grease"], "RESTORE_GREASE_COUNT")
        require(len(tagged(world, "HP_S03T")) == rec["source_tint"], "RESTORE_TINT_COUNT")
        require(not temp_actors(world), "TEMP_ACTORS_REFUSING_SAVE")
        require(census() == {"maps": [EXPECTED_WORLD], "content": []}, "REVERT_CENSUS|" + json.dumps(census()))
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "REVERT_SAVE_FAILED")
        saved = True; require(census() == {"maps": [], "content": []}, "REVERT_POST_SAVE_DIRTY")
        rec.update({"reverted": True, "revert_run": RUN, "revert_backup": backup}); write_json(PLACE_RECORD, rec)
        archived = PLACE_RECORD + ".reverted-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        os.replace(PLACE_RECORD, archived)
        unreal.log("P12_DENSE_REVERT_SUCCESS|run=%s|removed=%d|restored=%d|saved=1|backup=%s|record=%s" %
                   (RUN, len(dense), len(restored), backup, archived))
    except Exception:
        if not saved:
            rec.update({"revert_failed": True, "needs": "DONT_SAVE_RESTART"}); write_json(PLACE_RECORD, rec)
        raise


def main():
    try:
        core.check_confirm(MODE, CONFIRM)
        table = load_table()
        if MODE == "ASSET_DRY": asset_dry(table)
        elif MODE == "ASSET_APPLY": asset_apply(table)
        elif MODE == "ASSET_VERIFY": asset_verify(table)
        elif MODE in ("DRY", "APPLY", "REVERT_DRY", "REVERT"):
            world = world_checked()
            if MODE in ("DRY", "APPLY"): do_apply(world, table, MODE == "DRY")
            else: do_revert(world, table, MODE == "REVERT_DRY")
        else:
            raise ToolError("MODE|" + MODE)
    except ToolError as exc:
        unreal.log_error("P12_DENSE_STOPPED|run=%s|mode=%s|reason=%s|census=%s" %
                         (RUN, MODE, exc, json.dumps(census())))
    except Exception as exc:
        unreal.log_error("P12_DENSE_ERROR|run=%s|mode=%s|reason=%r|trace=%s|census=%s" %
                         (RUN, MODE, exc, traceback.format_exc(), json.dumps(census())))


main()
