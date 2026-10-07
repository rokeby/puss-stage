"""Swap the S3 hand-print layer: 449 stain decals (HP_S03) -> the unified GREASE layer (HP_S03G).  PREPARED, NOT RUN.

Gary 7 Oct (conductor session): "Yes, build it" -- grease sheen, NO albedo, one unified layer replacing both the
449 stain prints and the grime bench's grease decals.

Modes (wrapper globals HP_GREASE_MODE; APPLY / GREASE_REVERT also need HP_GREASE_CONFIRM = "<MODE> HPS03G"):
  DRY            every APPLY gate, mutates nothing.                   HP_S03G_DRY_OK|run=|stain=449|grease=<n>
  APPLY          ONE call, ONE transaction:
                   gates: world; no PIE; CLEAN census; no HP_S03G / HP_S03_TEST actor and no "HP_S03G " label;
                   record absent; grease table sha pinned + schema hp_grease_placement/1; walls file sha; every
                   wall actor where the table was built (0.5 cm / 0.01 deg); landed-box rule (walls box, max z
                   raised to <= 2880 only); every row's MI listed VERIFIED in hp_grease_assets_record.json and
                   present; master verified; EXACTLY the 449 stain decals of the pinned stain table (labels,
                   +-0.5 cm), all DecalActors labelled "HP_S03 ";
                   1. snapshot every stain decal (label, folder, tags, world transform, parent, material, size,
                      sort order, fade screen size, mobility) + stain_digest_before (s3_marble_tiling_apply.py
                      hp_digest formula) -> umap backup Backups/PreHPS03Grease-<run> -> record written (exclusive)
                      BEFORE any change;
                   2. destroy the 449 (asserted each), spawn the grease decals (label "HP_S03G <wall> <nnnn>",
                      folder HandPrints/S03_Grease, tags HP_S03G + HP_S03G.run.<run>, Movable, MI, DecalSize,
                      sort order, FadeScreenSize 0, attached KEEP_WORLD to the wall actor exactly as the stains
                      were), read EVERY one back;
                   3. no HP_S03 left, HP_S03G count = rows, no ZZ_/TEMP actor (same script, before the save),
                      census = exactly the level -> save_current_level -> census clean -> recount.
                 Failure BEFORE the save: spawned grease destroyed, NOTHING saved, map left dirty -> Don't-Save
                 restart (the stains come back with the discarded map; hp_revert_decals.py is NOT used, it would
                 save a stain-less level on its own).   HP_S03G_APPLY_SUCCESS|run=|removed=449|spawned=<n>|saved=1
  REVERT_DRY     every GREASE_REVERT gate, mutates nothing.
  GREASE_REVERT  record saved; HP_S03G count = record; no HP_S03 actor; stain MIs exist; CLEAN census -> umap backup
                 Backups/PreHPS03GreaseRevert-<run> -> destroy the grease decals -> re-spawn the 449 stains FROM THE
                 SNAPSHOT (same labels, folder, tags incl. the original HP_S03.run.115927, transforms, parent,
                 material, size, sort, fade, mobility) -> read every one back against the snapshot -> save level ->
                 census clean -> stain_digest_after_restore -> record archived (.reverted-<ts>).
                 Object names are new (UE assigns them); everything the tools key on is restored exactly.
                                                     HP_S03G_REVERT_SUCCESS|run=|removed=<n>|restored=449|saved=1
Never reloads the open level; never touches the Show; success markers only after every assert.
"""
import datetime
import hashlib
import json
import math
import os
import shutil
import traceback

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PROJECT_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
HP_DIR = os.path.join(PROJECT_DIR, "DerivedAssets", "FlatV3", "HandPrints")
HANDPRINTS = os.path.join(PROJECT_DIR, "Saved", "CodexFlatV3", "handprints")
OUT_DIR = os.path.join(HANDPRINTS, "grease")
TABLE = os.path.join(HANDPRINTS, "clamber", "placement_S03_grease.json")
TABLE_SHA256 = "850851ea6633e072f0b0a2b410a0c4c38fc190e38bbaa33c6adcd4c5e11fbf60"
STAIN_TABLE = os.path.join(HP_DIR, "placement_S03.json")
STAIN_TABLE_SHA256 = "c9fc3ef6f559415e3a4581c2af54a4323b4a1408df6a00a27bf0512136b4bfe2"
ASSETS_RECORD = os.path.join(OUT_DIR, "hp_grease_assets_record.json")
RECORD = os.path.join(OUT_DIR, "hp_place_grease_record.json")
MASTER = "/Game/Scenes/Scene3/HandPrints/Materials/Grease/M_HP_S03_Grease"
STAIN_TAG, STAIN_PREFIX, STAIN_COUNT = "HP_S03", "HP_S03 ", 449
TAG, LABEL_PREFIX, FOLDER = "HP_S03G", "HP_S03G ", "HandPrints/S03_Grease"
FOREIGN_TAGS = ("HP_S03_TEST",)
FADE_SCREEN_SIZE = 0.0
POS_TOL_CM, AXIS_DOT_MIN, STAIN_TABLE_TOL_CM = 0.5, 0.9999, 0.5
RESTORE_POS_TOL_CM, RESTORE_ROT_TOL_DEG = 0.05, 0.01
WALL_TOL_CM, WALL_TOL_DEG, BOX_MARGIN_CM, Z_CEILING_WORLD = 0.5, 0.01, 30.0, 2880.0
MODE = str(globals().get("HP_GREASE_MODE", "DRY")).upper()
CONFIRM = globals().get("HP_GREASE_CONFIRM")


class PlaceError(RuntimeError):
    pass


def require(cond, msg):
    if not cond:
        raise PlaceError(msg)


# ------------------------------------------------------------------------------------------------ pure helpers
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hp_digest(rows):
    """IDENTICAL to s3_marble_tiling_apply.py hp_digest (object_path, parent, loc %.2f, rot %.3f, scale %.4f)."""
    keyed = sorted("%s|%s|%s|%s|%s" % (h["object_path"], h["parent_label"],
                                       ",".join("%.2f" % v for v in h["location"]),
                                       ",".join("%.3f" % v for v in h["rotation"]),
                                       ",".join("%.4f" % v for v in h["scale"])) for h in rows)
    return hashlib.sha256("\n".join(keyed).encode("utf-8")).hexdigest()


def ang(a, b):
    return abs(((a - b) + 180.0) % 360.0 - 180.0)


def box_ok(table_box, walls_box):
    return (table_box["min"] == walls_box["min"] and table_box["max"][:2] == walls_box["max"][:2]
            and walls_box["max"][2] <= table_box["max"][2] <= Z_CEILING_WORLD)


def check_confirm(mode, confirm):
    require(mode in ("DRY", "APPLY", "REVERT_DRY", "GREASE_REVERT"), "MODE|" + mode)
    if mode in ("APPLY", "GREASE_REVERT"):
        require(confirm == "%s HPS03G" % mode, "CONFIRM_MISSING|%s HPS03G" % mode)


# ------------------------------------------------------------------------------------------------ unreal glue
def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def rpy(r):
    return [float(r.roll), float(r.pitch), float(r.yaw)]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def path_of(obj):
    return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]


def census():
    def names(pkgs):
        return sorted(str(p.get_path_name()).split(".", 1)[0] for p in pkgs)
    return {"maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def all_actors(world):
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


def tagged(world, tag):
    return [a for a in all_actors(world) if tag in [str(t) for t in a.get_editor_property("tags")]]


def temp_actors(world):
    return [str(a.get_actor_label()) for a in all_actors(world)
            if str(a.get_actor_label()).startswith("ZZ_") or "TEMP" in str(a.get_actor_label()).upper()]


def labels_index():
    out = {}
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        out.setdefault(str(a.get_actor_label()), []).append(a)
    return out


def write_record(rec, exclusive=False):
    with open(RECORD, "x" if exclusive else "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())


def backup_level(prefix, run):
    rel = EXPECTED_WORLD[len("/Game/"):].split("/")
    src = os.path.join(PROJECT_DIR, "Content", *rel) + ".umap"
    require(os.path.isfile(src), "LEVEL_FILE_MISSING|" + src)
    root = os.path.join(PROJECT_DIR, "Backups", prefix + run)
    require(not os.path.exists(root), "BACKUP_EXISTS|" + root)
    dest = os.path.join(root, "Content", *rel) + ".umap"
    os.makedirs(os.path.dirname(dest))
    shutil.copy2(src, dest)
    require(sha256(src) == sha256(dest), "BACKUP_HASH_MISMATCH")
    return root


def decal_comp(actor):
    return actor.get_editor_property("decal")


def digest_row(a):
    p = a.get_attach_parent_actor()
    return {"object_path": a.get_path_name(), "parent_label": str(p.get_actor_label()) if p else None,
            "location": vec(a.get_actor_location()), "rotation": rpy(a.get_actor_rotation()),
            "scale": vec(a.get_actor_scale3d())}


def snapshot(a):
    c = decal_comp(a)
    p = a.get_attach_parent_actor()
    return {"label": str(a.get_actor_label()), "folder": str(a.get_folder_path()),
            "tags": [str(t) for t in a.get_editor_property("tags")],
            "location": vec(a.get_actor_location()), "rotation": rpy(a.get_actor_rotation()),
            "scale": vec(a.get_actor_scale3d()), "parent_label": str(p.get_actor_label()) if p else None,
            "material": path_of(c.get_decal_material()), "decal_size": vec(c.get_editor_property("decal_size")),
            "sort_order": int(c.get_editor_property("sort_order")),
            "fade_screen_size": float(c.get_editor_property("fade_screen_size")),
            "mobility": str(c.get_editor_property("mobility")), "object_path": a.get_path_name()}


def wall_actors_for(table, idx):
    with open(os.path.join(HP_DIR, table["walls_file"]), encoding="utf-8") as fh:
        walls_doc = json.load(fh)
    require(sha256(os.path.join(HP_DIR, table["walls_file"])) == table["walls_sha256"], "WALLS_FILE_CHANGED")
    require(box_ok(table["landed_box_world_cm"], walls_doc["landed_box_world_cm"]), "BOX_NOT_WALLS_BOX_WITH_RAISED_Z")
    out = {}
    for w in walls_doc["walls"]:
        found = idx.get(w["attach_actor_label"], [])
        require(len(found) == 1, "WALL_ACTOR_COUNT|%s|%d" % (w["attach_actor_label"], len(found)))
        t = found[0].get_actor_transform()
        dl = max(abs(a - b) for a, b in zip(vec(t.translation), w["actor_transform"]["location"]))
        dr = max(ang(a, b) for a, b in zip(rpy(t.rotation.rotator()), w["actor_transform"]["rotation_rpy"]))
        require(dl <= WALL_TOL_CM and dr <= WALL_TOL_DEG, "WALL_MOVED_SINCE_TABLE|%s|%.3f|%.4f" % (w["id"], dl, dr))
        out[w["id"]] = found[0]
    return out


def base_gates(world):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(world is not None and str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_WORLD")
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    before = census()
    require(not before["maps"] and not before["content"], "DIRTY_AT_START|" + json.dumps(before))
    for t in FOREIGN_TAGS:
        require(not tagged(world, t), "FOREIGN_TAG_PRESENT|" + t)


def apply_gates(world):
    base_gates(world)
    require(not tagged(world, TAG), "HP_S03G_ALREADY_EXIST")
    require(not os.path.exists(RECORD), "RECORD_EXISTS|" + RECORD)
    require(os.path.isfile(TABLE) and sha256(TABLE) == TABLE_SHA256, "GREASE_TABLE_SHA256_MISMATCH")
    with open(TABLE, encoding="utf-8") as fh:
        table = json.load(fh)
    require(table.get("schema") == "hp_grease_placement/1", "GREASE_TABLE_SCHEMA")
    require(table.get("placeholder") is False and table.get("level") == EXPECTED_WORLD, "GREASE_TABLE_LEVEL")
    rows = table["decals"]
    require(rows and len({r["label"] for r in rows}) == len(rows), "GREASE_LABELS")
    require(all(r["label"].startswith(LABEL_PREFIX) for r in rows), "GREASE_LABEL_PREFIX")
    idx = labels_index()
    require(not any(l.startswith(LABEL_PREFIX) for l in idx), "HP_S03G_LABELS_EXIST")
    with open(ASSETS_RECORD, encoding="utf-8") as fh:
        arec = json.load(fh)["stages"]
    require((arec.get("master") or {}).get("verified") is True, "MASTER_NOT_VERIFIED")
    require((arec.get("mi") or {}).get("verified") is True, "MIS_NOT_VERIFIED")
    mi_dir = table["material"]["mi_dir"]
    need = sorted({r["material_instance"] for r in rows})
    require(set(need) <= set(arec["mi"]["done"]), "MI_NOT_IN_VERIFIED_SET|%s" % sorted(set(need) - set(arec["mi"]["done"]))[:5])
    for n in need:
        require(unreal.EditorAssetLibrary.does_asset_exist(mi_dir + "/" + n), "MI_MISSING|" + n)
    box = table["landed_box_world_cm"]
    for r in rows:
        require(all(box["min"][i] - BOX_MARGIN_CM <= r["location"][i] <= box["max"][i] + BOX_MARGIN_CM for i in range(3)),
                "DECAL_OUTSIDE_LANDED_BOX|" + r["label"])
    walls = wall_actors_for(table, idx)
    # the stain layer must be EXACTLY the pinned 449 (the snapshot is what GREASE_REVERT restores)
    require(sha256(STAIN_TABLE) == STAIN_TABLE_SHA256, "STAIN_TABLE_SHA256_MISMATCH")
    with open(STAIN_TABLE, encoding="utf-8") as fh:
        stain_rows = {d["label"]: d for d in json.load(fh)["decals"]}
    stains = tagged(world, STAIN_TAG)
    require(len(stains) == STAIN_COUNT == len(stain_rows), "STAIN_COUNT|%d" % len(stains))
    for a in stains:
        lab = str(a.get_actor_label())
        require(isinstance(a, unreal.DecalActor) and lab.startswith(STAIN_PREFIX), "STAIN_NOT_OWNED|" + lab)
        require(lab in stain_rows, "STAIN_NOT_IN_TABLE|" + lab)
        d = max(abs(x - y) for x, y in zip(vec(a.get_actor_location()), stain_rows[lab]["location"]))
        require(d <= STAIN_TABLE_TOL_CM, "STAIN_MOVED|%s|%.3f" % (lab, d))
    require(len({str(a.get_actor_label()) for a in stains}) == STAIN_COUNT, "STAIN_DUP_LABELS")
    return table, rows, walls, stains


def spawn_grease(r, wall, run, mats):
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        unreal.DecalActor, unreal.Vector(*r["location"]),
        unreal.Rotator(roll=r["rotation"]["roll"], pitch=r["rotation"]["pitch"], yaw=r["rotation"]["yaw"]))
    require(actor is not None, "SPAWN_FAILED|" + r["label"])
    actor.modify(); actor.set_actor_label(r["label"])
    actor.modify(); actor.set_folder_path(FOLDER)
    actor.modify(); actor.set_editor_property("tags", [unreal.Name(TAG), unreal.Name(TAG + ".run." + run)])
    c = decal_comp(actor)
    c.modify(); c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.modify(); c.set_decal_material(mats[r["material_instance"]])
    c.modify(); c.set_editor_property("decal_size", unreal.Vector(*r["decal_size"]))
    c.modify(); c.set_sort_order(int(r["sort_order"]))
    c.modify(); c.set_fade_screen_size(FADE_SCREEN_SIZE)
    actor.modify()
    actor.attach_to_actor(wall, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, False)
    return actor


def read_back_grease(actor, r, wall, mats):
    c = decal_comp(actor)
    got = vec(actor.get_actor_location())
    require(max(abs(a - b) for a, b in zip(got, r["location"])) <= POS_TOL_CM, "LOCATION_READBACK|" + r["label"])
    for name, fn in (("x", actor.get_actor_forward_vector), ("y", actor.get_actor_right_vector),
                     ("z", actor.get_actor_up_vector)):
        require(dot(vec(fn()), r["axes"][name]) >= AXIS_DOT_MIN, "AXIS_READBACK|%s|%s" % (r["label"], name))
    require(path_of(c.get_decal_material()) == path_of(mats[r["material_instance"]]), "MATERIAL_READBACK|" + r["label"])
    require(max(abs(a - b) for a, b in zip(vec(c.get_editor_property("decal_size")), r["decal_size"])) < 1e-3,
            "SIZE_READBACK|" + r["label"])
    require(int(c.get_editor_property("sort_order")) == int(r["sort_order"]), "SORT_READBACK|" + r["label"])
    require(abs(float(c.get_editor_property("fade_screen_size")) - FADE_SCREEN_SIZE) < 1e-9, "FADE_READBACK|" + r["label"])
    require(actor.get_attach_parent_actor() == wall, "PARENT_READBACK|" + r["label"])
    require(c.get_editor_property("mobility") == unreal.ComponentMobility.MOVABLE, "MOBILITY_READBACK|" + r["label"])
    require(str(actor.get_actor_label()) == r["label"], "LABEL_READBACK|" + r["label"])


def restore_stain(s, parents):
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        unreal.DecalActor, unreal.Vector(*s["location"]),
        unreal.Rotator(roll=s["rotation"][0], pitch=s["rotation"][1], yaw=s["rotation"][2]))
    require(actor is not None, "RESTORE_SPAWN_FAILED|" + s["label"])
    actor.modify(); actor.set_actor_label(s["label"])
    actor.modify(); actor.set_folder_path(s["folder"])
    actor.modify(); actor.set_editor_property("tags", [unreal.Name(t) for t in s["tags"]])
    actor.modify(); actor.set_actor_scale3d(unreal.Vector(*s["scale"]))
    c = decal_comp(actor)
    mat = unreal.load_asset(s["material"])
    require(mat is not None, "RESTORE_MATERIAL_MISSING|" + str(s["material"]))
    c.modify(); c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.modify(); c.set_decal_material(mat)
    c.modify(); c.set_editor_property("decal_size", unreal.Vector(*s["decal_size"]))
    c.modify(); c.set_sort_order(int(s["sort_order"]))
    c.modify(); c.set_fade_screen_size(float(s["fade_screen_size"]))
    if s["parent_label"]:
        actor.modify()
        actor.attach_to_actor(parents[s["parent_label"]], unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    return actor


def restore_diffs(actor, s):
    """Fields of the live re-spawned actor that differ from the snapshot (empty = exact)."""
    g = snapshot(actor)
    out = []
    for k in ("label", "folder", "tags", "parent_label", "material", "sort_order", "mobility"):
        if g[k] != s[k]:
            out.append(k)
    if max(abs(a - b) for a, b in zip(g["location"], s["location"])) > RESTORE_POS_TOL_CM:
        out.append("location")
    if max(ang(a, b) for a, b in zip(g["rotation"], s["rotation"])) > RESTORE_ROT_TOL_DEG:
        out.append("rotation")
    if max(abs(a - b) for a, b in zip(g["scale"], s["scale"])) > 1e-4:
        out.append("scale")
    if max(abs(a - b) for a, b in zip(g["decal_size"], s["decal_size"])) > 1e-3:
        out.append("decal_size")
    if abs(g["fade_screen_size"] - s["fade_screen_size"]) > 1e-9:
        out.append("fade_screen_size")
    return out


def save_level_gated(world, expect_tag, expect_n, absent_tag):
    require(not tagged(world, absent_tag), "SURVIVORS|" + absent_tag)
    require(len(tagged(world, expect_tag)) == expect_n, "COUNT_BEFORE_SAVE|%s" % expect_tag)
    temps = temp_actors(world)
    require(not temps, "TEMP_ACTORS_PRESENT_REFUSING_SAVE|" + json.dumps(temps[:10]))
    pre = census()
    require(pre["content"] == [] and pre["maps"] == [EXPECTED_WORLD], "CENSUS_NOT_EXACT_LEVEL|" + json.dumps(pre))
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")


# ------------------------------------------------------------------------------------------------ modes
def do_apply(world, run, dry):
    table, rows, walls, stains = apply_gates(world)
    if dry:
        require(census() == {"maps": [], "content": []}, "DRY_RUN_DIRTIED")
        unreal.log("HP_S03G_DRY_OK|run=%s|stain=%d|grease=%d|mis=%d|mutated=0"
                   % (run, len(stains), len(rows), len({r["material_instance"] for r in rows})))
        return
    snap = sorted((snapshot(a) for a in stains), key=lambda s: s["label"])
    stain_digest = hp_digest([digest_row(a) for a in stains])
    backup = backup_level("PreHPS03Grease-", run)
    rec = {"run": run, "mode": "APPLY", "world": EXPECTED_WORLD, "backup": backup, "table": TABLE,
           "table_sha256": TABLE_SHA256, "stain_table_sha256": STAIN_TABLE_SHA256, "stain_snapshot": snap,
           "stain_digest_before": stain_digest, "count_planned": len(rows), "removed": 0, "spawned": 0,
           "saved": False}
    write_record(rec, exclusive=True)
    mats = {n: unreal.load_asset(table["material"]["mi_dir"] + "/" + n) for n in sorted({r["material_instance"] for r in rows})}
    require(all(m is not None for m in mats.values()), "MI_LOAD")
    spawned, saved = [], [False]
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    try:
        with unreal.ScopedEditorTransaction("HP_S03G swap stains -> grease run=" + run):
            for a in stains:
                lab = str(a.get_actor_label())
                a.modify()
                require(sub.destroy_actor(a), "DESTROY_FAILED|" + lab)
            stains = None
            rec["removed"] = STAIN_COUNT
            sample = []
            for n, r in enumerate(rows):
                actor = spawn_grease(r, walls[r["wall"]], run, mats)
                spawned.append(actor)
                read_back_grease(actor, r, walls[r["wall"]], mats)
                if n % max(1, len(rows) // 12) == 0:
                    sample.append({"label": r["label"], "location": vec(actor.get_actor_location()),
                                   "material": r["material_instance"]})
        rec["spawned"] = len(spawned)
        write_record(rec)
        save_level_gated(world, TAG, len(rows), STAIN_TAG)
        saved[0] = True
        post = census()
        require(post == {"maps": [], "content": []}, "POST_SAVE_DIRTY|" + json.dumps(post))
        count = len(tagged(world, TAG))
        require(count == len(rows) and not tagged(world, STAIN_TAG), "COUNT_AFTER_SAVE|%d" % count)
        rec.update({"saved": True, "count_after_save": count, "sample": sample,
                    "grease_digest_after": hp_digest([digest_row(a) for a in tagged(world, TAG)])})
        write_record(rec)
        unreal.log("HP_S03G_APPLY_SUCCESS|run=%s|removed=%d|spawned=%d|saved=1|backup=%s"
                   % (run, STAIN_COUNT, count, backup))
    except Exception:
        if not saved[0]:
            for a in spawned:
                try:
                    sub.destroy_actor(a)
                except Exception:
                    pass
            rec.update({"failed": True, "needs": "DONT_SAVE_RESTART (stains return with the discarded map)"})
            write_record(rec)
            os.replace(RECORD, RECORD + ".failed-" + run)
        raise


def do_revert(world, run, dry):
    base_gates(world)
    require(os.path.isfile(RECORD), "NO_RECORD")
    with open(RECORD, encoding="utf-8") as fh:
        rec = json.load(fh)
    require(rec.get("saved") is True and rec.get("mode") == "APPLY", "RECORD_NOT_SAVED_APPLY")
    grease = tagged(world, TAG)
    require(len(grease) == rec["count_after_save"], "GREASE_COUNT|%d" % len(grease))
    for a in grease:
        require(isinstance(a, unreal.DecalActor) and str(a.get_actor_label()).startswith(LABEL_PREFIX),
                "GREASE_NOT_OWNED|" + str(a.get_actor_label()))
    require(not tagged(world, STAIN_TAG), "STAIN_ALREADY_PRESENT")
    snap = rec["stain_snapshot"]
    require(len(snap) == STAIN_COUNT, "SNAPSHOT_COUNT")
    idx = labels_index()
    parents = {}
    for p in sorted({s["parent_label"] for s in snap if s["parent_label"]}):
        found = idx.get(p, [])
        require(len(found) == 1, "PARENT_COUNT|%s|%d" % (p, len(found)))
        parents[p] = found[0]
    for m in sorted({s["material"] for s in snap}):
        require(unreal.EditorAssetLibrary.does_asset_exist(m), "STAIN_MI_MISSING|" + str(m))
    require(not any(l.startswith(STAIN_PREFIX) for l in idx), "STAIN_LABELS_PRESENT")
    if dry:
        require(census() == {"maps": [], "content": []}, "DRY_RUN_DIRTIED")
        unreal.log("HP_S03G_REVERT_DRY_OK|run=%s|grease=%d|restore=%d|mutated=0" % (run, len(grease), len(snap)))
        return
    backup = backup_level("PreHPS03GreaseRevert-", run)
    rec.update({"revert_run": run, "revert_backup": backup, "revert_started": True})
    write_record(rec)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    restored, saved = [], [False]
    try:
        with unreal.ScopedEditorTransaction("HP_S03G revert grease -> stains run=" + run):
            n = len(grease)
            for a in grease:
                a.modify()
                require(sub.destroy_actor(a), "DESTROY_FAILED|" + str(a.get_actor_label()))
            grease = None
            for s in snap:
                actor = restore_stain(s, parents)
                restored.append(actor)
                diffs = restore_diffs(actor, s)
                require(not diffs, "RESTORE_READBACK|%s|%s" % (s["label"], diffs))
        save_level_gated(world, STAIN_TAG, STAIN_COUNT, TAG)
        saved[0] = True
        post = census()
        require(post == {"maps": [], "content": []}, "POST_SAVE_DIRTY|" + json.dumps(post))
        stains = tagged(world, STAIN_TAG)
        require(len(stains) == STAIN_COUNT and not tagged(world, TAG), "COUNT_AFTER_SAVE")
        rec.update({"reverted": True, "stain_digest_after_restore": hp_digest([digest_row(a) for a in stains]),
                    "revert_saved": True, "removed_grease": n})
        write_record(rec)
        archived = RECORD + ".reverted-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        os.replace(RECORD, archived)
        unreal.log("HP_S03G_REVERT_SUCCESS|run=%s|removed=%d|restored=%d|saved=1|backup=%s|record=%s"
                   % (run, n, STAIN_COUNT, backup, archived))
    except Exception:
        if not saved[0]:
            for a in restored:
                try:
                    sub.destroy_actor(a)
                except Exception:
                    pass
            rec.update({"revert_failed": True, "needs": "DONT_SAVE_RESTART (grease returns with the discarded map)"})
            write_record(rec)
        raise


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    try:
        check_confirm(MODE, CONFIRM)
        if MODE in ("DRY", "APPLY"):
            do_apply(world, run, MODE == "DRY")
        else:
            do_revert(world, run, MODE == "REVERT_DRY")
    except Exception as exc:
        kind = "STOPPED" if isinstance(exc, PlaceError) else "ERROR"
        detail = str(exc) if isinstance(exc, PlaceError) else traceback.format_exc().replace("\n", "\\n")
        unreal.log_error("HP_S03G_%s|run=%s|mode=%s|reason=%s|census=%s|NEEDS_DONT_SAVE_RESTART_IF_MAP_DIRTY"
                         % (kind, run, MODE, detail, json.dumps(census())))


main()
