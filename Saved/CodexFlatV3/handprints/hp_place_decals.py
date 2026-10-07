"""Spawn the S3 hand-print DecalActors from the shipped placement table.  PREPARED, NOT RUN.

READS DerivedAssets/FlatV3/HandPrints/placement_S03.json (built offline by
Tools/FlatV3/handprints/build_handprint_placement.py) and never regenerates it.

Refuses (mutating nothing) when: wrong world; PIE/SIE running; dirty census not
clean; any actor tagged HP_S03 already exists (checked with
GameplayStatics.get_all_actors_of_class, which also sees transient actors);
the table is a PLACEHOLDER table; the table's atlas hash differs from the
imported atlas (hp_import_record.json); a wall actor's live transform differs
from the one the table was built against; any material instance is missing or
the master has not compiled (0 pixel instructions); a decal would leave the
landed S3 box.

Then: backs up the level umap to Backups/PreHPS03Place-YYYYMMDD-HHMM; writes
its record BEFORE spawning; spawns one DecalActor per row, labelled
"HP_S03 <wall> <nnnn>" in folder HandPrints/S03, tagged HP_S03 and HP_S03.run.<id>,
root Movable and attached (keep world) to its wall actor so it rides the wall
hinge; sets the v3 per-element material instance MI_HP_S03_v3_<element>_F<flip> (resolved
from each row's element_id + flip; v2's DecalColor selection rendered nothing on 6 Oct),
DecalSize, SortOrder and FadeScreenSize = 0 (default 0.01 culls a 20 cm decal seen from
across the hangar; inferred second suspect for the blank 6 Oct still); reads
EVERY decal back (location 0.5 cm, axes dot 0.9999, material, size, parent,
sort order); refuses to save if any ZZ_/TEMP actor exists (same script as the
save); saves ONLY the current level; asserts the census is clean afterwards;
re-counts the tagged actors.  On any failure after spawning it destroys what it
spawned and does NOT save (the map stays dirty: close the editor with Don't Save
— hp_revert_decals.py needs a clean census, so it is for SAVED decals only).
Never reloads the open level.  Success marker only after all asserts:
  HP_S03_PLACE_SUCCESS|run=<id>|count=<n>|saved=1
HP_DRY_RUN=True in globals (hp_place_decals_dry.py) stops after the preflight.
HP_PLACE_MODE="test" in globals (hp_place_test.py) places ONLY the 2 decals of
Saved/CodexFlatV3/handprints/hp_test_plan.json, tagged HP_S03_TEST, own record and backup
prefix.  Either mode refuses while any HP_S03 or HP_S03_TEST actor exists.
HP_PLACE_MODE="clamber" (clamber/hp_place_clamber*.py, 7 Oct) places the pinned
clamber/placement_S03_clamber.json instead of placement_S03.json; same tag, labels, folder and
record as the full mode (so hp_revert_decals.py reverts it), own backup prefix; its table may
raise the landed box's max z only (to <= CLAMBER_Z_CEILING_WORLD, the marble top).  Default and
test modes are unchanged.
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
OUT_DIR = os.path.join(PROJECT_DIR, "Saved", "CodexFlatV3", "handprints")
IMPORT_RECORD = os.path.join(OUT_DIR, "hp_import_stages_record.json")
MAT = "/Game/Scenes/Scene3/HandPrints/Materials"
MASTER = MAT + "/M_HP_S03_Decal_v3"
MI_V3_DIR = MAT + "/V3"
MI_V3_PREFIX = "MI_HP_S03_v3_"
FADE_SCREEN_SIZE = 0.0
ALL_HP_TAGS = ("HP_S03", "HP_S03_TEST")
MODE = globals().get("HP_PLACE_MODE", "full")
# clamber table (Saved/CodexFlatV3/handprints/clamber/hp_clamber_layout.py); re-pin whenever it is regenerated
CLAMBER_PLACEMENT_SHA256 = "f0dd01f9d4bc2128ebdf62ba26499ae0f1f8d7b79b04884cdc7123a47e966620"
CLAMBER_Z_CEILING_WORLD = 2880.0      # marble top: s3_backwall_marble_record.json Upper 4 tiles aabb max z
if MODE == "test":
    PLACEMENT = os.path.join(OUT_DIR, "hp_test_plan.json")
    RECORD = os.path.join(OUT_DIR, "hp_place_test_record.json")
    TAG = "HP_S03_TEST"
    LABEL_PREFIX = "HP_S03_TEST "
    FOLDER = "HandPrints/S03_TEST"
    BACKUP_PREFIX = "PreHPS03Test-"
    EXPECTED_COUNT = 2
    EXPECTED_PLACEMENT_SHA256 = None
elif MODE == "clamber":
    PLACEMENT = os.path.join(OUT_DIR, "clamber", "placement_S03_clamber.json")
    EXPECTED_PLACEMENT_SHA256 = CLAMBER_PLACEMENT_SHA256
    RECORD = os.path.join(OUT_DIR, "hp_place_record.json")
    TAG = "HP_S03"
    LABEL_PREFIX = "HP_S03 "
    FOLDER = "HandPrints/S03"
    BACKUP_PREFIX = "PreHPS03Clamber-"
    EXPECTED_COUNT = None
else:
    PLACEMENT = os.path.join(HP_DIR, "placement_S03.json")
    # Gary 6 Oct "scramble" table (160-400 cm, climbs/pairs/up-diagonal drags); the 395-low table
    # is kept as placement_S03.v395_low.json.  Re-pin whenever the table is regenerated.
    EXPECTED_PLACEMENT_SHA256 = "c9fc3ef6f559415e3a4581c2af54a4323b4a1408df6a00a27bf0512136b4bfe2"
    RECORD = os.path.join(OUT_DIR, "hp_place_record.json")
    TAG = "HP_S03"
    LABEL_PREFIX = "HP_S03 "
    FOLDER = "HandPrints/S03"
    BACKUP_PREFIX = "PreHPS03Place-"
    EXPECTED_COUNT = None


def mi_v3_name(d):
    return "%s%s_F%d" % (MI_V3_PREFIX, d["element_id"], 1 if d["flip"] else 0)
POS_TOL_CM = 0.5
AXIS_DOT_MIN = 0.9999
WALL_TOL_CM = 0.5
WALL_TOL_DEG = 0.01
BOX_MARGIN_CM = 30.0


class PlaceError(RuntimeError):
    pass


def require(cond, msg):
    if not cond:
        raise PlaceError(msg)


def census():
    def names(pkgs):
        return sorted(str(p.get_path_name()).split(".", 1)[0] for p in pkgs)
    return {"maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def path_of(obj):
    return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]


def all_actors(world):
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


def tagged(world, tags=None):
    tags = set(tags or (TAG,))
    return [a for a in all_actors(world) if any(str(t) in tags for t in a.get_editor_property("tags"))]


def temp_actors(world):
    out = []
    for a in all_actors(world):
        label = str(a.get_actor_label())
        if label.startswith("ZZ_") or "TEMP" in label.upper():
            out.append(label)
    return out


def write_record(rec, exclusive=False):
    with open(RECORD, "x" if exclusive else "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())


def backup_level():
    rel = EXPECTED_WORLD[len("/Game/"):].split("/")
    src = os.path.join(PROJECT_DIR, "Content", *rel) + ".umap"
    require(os.path.isfile(src), "LEVEL_FILE_MISSING|" + src)
    dest_root = os.path.join(PROJECT_DIR, "Backups", BACKUP_PREFIX + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    require(not os.path.exists(dest_root), "BACKUP_EXISTS|" + dest_root)
    dest = os.path.join(dest_root, "Content", *rel) + ".umap"
    os.makedirs(os.path.dirname(dest))
    shutil.copy2(src, dest)
    require(sha256(src) == sha256(dest), "BACKUP_HASH_MISMATCH")
    return dest_root


def wall_matches(actor, expected):
    t = actor.get_actor_transform()
    loc = vec(t.translation)
    r = t.rotation.rotator()
    rpy = [float(r.roll), float(r.pitch), float(r.yaw)]
    dl = max(abs(a - b) for a, b in zip(loc, expected["location"]))
    dr = max(abs(((a - b) + 180.0) % 360.0 - 180.0) for a, b in zip(rpy, expected["rotation_rpy"]))
    return dl <= WALL_TOL_CM and dr <= WALL_TOL_DEG, {"location": loc, "rotation_rpy": rpy, "dl": dl, "dr": dr}


def preflight(world):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(world is not None and str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_WORLD")
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    before = census()
    require(not before["maps"] and not before["content"], "DIRTY_AT_START|" + json.dumps(before))
    require(not tagged(world, ALL_HP_TAGS), "HP_S03_OR_TEST_ACTORS_ALREADY_EXIST")
    require(not os.path.exists(RECORD), "PLACE_RECORD_EXISTS|" + RECORD)
    require(os.path.isfile(PLACEMENT), "PLACEMENT_MISSING|" + PLACEMENT)
    require(EXPECTED_PLACEMENT_SHA256 is None or sha256(PLACEMENT) == EXPECTED_PLACEMENT_SHA256,
            "PLACEMENT_SHA256_MISMATCH|" + sha256(PLACEMENT))
    with open(PLACEMENT, encoding="utf-8") as fh:
        table = json.load(fh)
    require(table.get("schema") == "hp_placement/1", "PLACEMENT_SCHEMA")
    require(table.get("placeholder") is False, "PLACEMENT_IS_PLACEHOLDER")
    require(table.get("level") == EXPECTED_WORLD, "PLACEMENT_LEVEL_MISMATCH")
    require(os.path.isfile(IMPORT_RECORD), "IMPORT_RECORD_MISSING")
    with open(IMPORT_RECORD, encoding="utf-8") as fh:
        imported = json.load(fh)
    stages = imported.get("stages", {})
    require((stages.get("textures") or {}).get("saved") is True, "TEXTURES_NOT_SAVED")
    require((stages.get("material_v3") or {}).get("verified") is True, "MATERIAL_V3_NOT_VERIFIED")
    mi_done = set((stages.get("mi_v3") or {}).get("done") or [])
    require(imported.get("atlas_sha256") == table.get("atlas_sha256"), "ATLAS_HASH_MISMATCH")
    decals = table["decals"]
    require(len(decals) > 0, "PLACEMENT_EMPTY")
    require(EXPECTED_COUNT is None or len(decals) == EXPECTED_COUNT, "TEST_PLAN_NOT_2_DECALS")
    missing = sorted({mi_v3_name(d) for d in decals} - mi_done)
    require(not missing, "MI_V3_NOT_CREATED|%d|%s" % (len(missing), json.dumps(missing[:5])))
    require(len({d["label"] for d in decals}) == len(decals), "DUPLICATE_LABELS")
    labels = {}
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        labels.setdefault(str(a.get_actor_label()), []).append(a)
    require(not any(l.startswith(LABEL_PREFIX) for l in labels), "HP_S03_LABELS_ALREADY_EXIST")
    walls_doc_path = os.path.join(HP_DIR, table["walls_file"])
    require(sha256(walls_doc_path) == table["walls_sha256"], "WALLS_FILE_CHANGED_SINCE_TABLE")
    with open(walls_doc_path, encoding="utf-8") as fh:
        walls = {w["id"]: w for w in json.load(fh)["walls"]}
    if MODE == "clamber":
        with open(walls_doc_path, encoding="utf-8") as fh:
            walls_doc = json.load(fh)
        wb, tb = walls_doc["landed_box_world_cm"], table["landed_box_world_cm"]
        require(tb["min"] == wb["min"] and tb["max"][:2] == wb["max"][:2]
                and wb["max"][2] <= tb["max"][2] <= CLAMBER_Z_CEILING_WORLD,
                "CLAMBER_BOX_NOT_WALLS_BOX_WITH_RAISED_Z|" + json.dumps(tb))
    wall_actors = {}
    for wid, w in walls.items():
        found = labels.get(w["attach_actor_label"], [])
        require(len(found) == 1, "WALL_ACTOR_COUNT|%s|%d" % (w["attach_actor_label"], len(found)))
        ok, live = wall_matches(found[0], w["actor_transform"])
        require(ok, "WALL_MOVED_SINCE_TABLE|%s|%s" % (wid, json.dumps(live)))
        wall_actors[wid] = found[0]
    master = unreal.EditorAssetLibrary.load_asset(MASTER)
    require(master is not None, "MASTER_MISSING")
    stats = unreal.MaterialEditingLibrary.get_statistics(master)
    require(int(stats.get_editor_property("num_pixel_shader_instructions")) > 0, "MASTER_NOT_COMPILED")
    for name in sorted({mi_v3_name(d) for d in decals}):
        require(unreal.EditorAssetLibrary.does_asset_exist(MI_V3_DIR + "/" + name), "MI_MISSING|" + name)
    box = table["landed_box_world_cm"]
    for d in decals:
        for i in range(3):
            require(box["min"][i] - BOX_MARGIN_CM <= d["location"][i] <= box["max"][i] + BOX_MARGIN_CM,
                    "DECAL_OUTSIDE_LANDED_BOX|" + d["label"])
    return table, decals, wall_actors


def spawn_one(d, wall, run, materials):
    loc = unreal.Vector(*d["location"])
    rot = unreal.Rotator(roll=d["rotation"]["roll"], pitch=d["rotation"]["pitch"], yaw=d["rotation"]["yaw"])
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.DecalActor, loc, rot)
    require(actor is not None, "SPAWN_FAILED|" + d["label"])
    actor.modify(); actor.set_actor_label(d["label"])
    actor.modify(); actor.set_folder_path(FOLDER)
    actor.modify(); actor.set_editor_property("tags", [unreal.Name(TAG), unreal.Name(TAG + ".run." + run)])
    comp = actor.get_editor_property("decal")
    comp.modify(); comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    comp.modify(); comp.set_decal_material(materials[mi_v3_name(d)])
    comp.modify(); comp.set_editor_property("decal_size", unreal.Vector(*d["decal_size"]))
    comp.modify(); comp.set_sort_order(int(d["sort_order"]))
    comp.modify(); comp.set_fade_screen_size(FADE_SCREEN_SIZE)
    actor.modify()
    actor.attach_to_actor(wall, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    return actor


def read_back(actor, d, wall, materials):
    comp = actor.get_editor_property("decal")
    got = vec(actor.get_actor_location())
    require(max(abs(a - b) for a, b in zip(got, d["location"])) <= POS_TOL_CM, "LOCATION_READBACK|" + d["label"])
    for name, fn in (("x", actor.get_actor_forward_vector), ("y", actor.get_actor_right_vector),
                     ("z", actor.get_actor_up_vector)):
        require(dot(vec(fn()), d["axes"][name]) >= AXIS_DOT_MIN, "AXIS_READBACK|%s|%s" % (d["label"], name))
    require(path_of(comp.get_decal_material()) == path_of(materials[mi_v3_name(d)]),
            "MATERIAL_READBACK|" + d["label"])
    size = vec(comp.get_editor_property("decal_size"))
    require(max(abs(a - b) for a, b in zip(size, d["decal_size"])) < 1e-3, "SIZE_READBACK|" + d["label"])
    require(int(comp.get_editor_property("sort_order")) == int(d["sort_order"]), "SORT_READBACK|" + d["label"])
    require(abs(float(comp.get_editor_property("fade_screen_size")) - FADE_SCREEN_SIZE) < 1e-9,
            "FADE_SCREEN_SIZE_READBACK|" + d["label"])
    require(actor.get_attach_parent_actor() == wall, "PARENT_READBACK|" + d["label"])
    require(comp.get_editor_property("mobility") == unreal.ComponentMobility.MOVABLE, "MOBILITY_READBACK|" + d["label"])
    require(str(actor.get_actor_label()) == d["label"], "LABEL_READBACK|" + d["label"])
    return {"label": d["label"], "location": got, "rotation": d["rotation"], "material": mi_v3_name(d)}


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    dry = bool(globals().get("HP_DRY_RUN"))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    spawned = []
    saved = [False]
    try:
        table, decals, wall_actors = preflight(world)
        if dry:
            require(census() == {"maps": [], "content": []}, "DRY_RUN_DIRTIED")
            unreal.log("HP_S03_PLACE_DRY_RUN_OK|run=%s|mode=%s|count=%d|mutated=0" % (run, MODE, len(decals)))
            return
        os.makedirs(OUT_DIR, exist_ok=True)
        backup = backup_level()
        record = {"run": run, "world": EXPECTED_WORLD, "backup": backup, "tag": TAG, "placement": PLACEMENT,
                  "placement_sha256": sha256(PLACEMENT), "count_planned": len(decals), "spawned": 0, "saved": False}
        write_record(record, exclusive=True)
        materials = {n: unreal.EditorAssetLibrary.load_asset(MI_V3_DIR + "/" + n)
                     for n in sorted({mi_v3_name(d) for d in decals})}
        sample = []
        with unreal.ScopedEditorTransaction("HP_S03 place decals run=" + run):
            for n, d in enumerate(decals):
                actor = spawn_one(d, wall_actors[d["wall"]], run, materials)
                spawned.append(actor)
                row = read_back(actor, d, wall_actors[d["wall"]], materials)
                if n % max(1, len(decals) // 12) == 0:
                    sample.append(row)
        record["spawned"] = len(spawned)
        write_record(record)
        require(len(tagged(world)) == len(decals), "TAGGED_COUNT_BEFORE_SAVE")
        temps = temp_actors(world)
        require(not temps, "TEMP_ACTORS_PRESENT_REFUSING_SAVE|" + json.dumps(temps[:10]))
        pre = census()
        require(pre["content"] == [] and pre["maps"] == [EXPECTED_WORLD], "CENSUS_NOT_EXACT_LEVEL|" + json.dumps(pre))
        require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
        saved[0] = True
        post = census()
        require(post == {"maps": [], "content": []}, "POST_SAVE_DIRTY|" + json.dumps(post))
        count = len(tagged(world))
        require(count == len(decals), "TAGGED_COUNT_AFTER_SAVE|%d" % count)
        record.update({"saved": True, "count_after_save": count, "sample": sample})
        write_record(record)
        unreal.log("HP_S03_PLACE_SUCCESS|run=%s|mode=%s|tag=%s|count=%d|saved=1|backup=%s"
                   % (run, MODE, TAG, count, backup))
    except Exception as exc:
        cleaned = 0
        # after a successful save the actors are real content: never destroy them here
        for actor in ([] if saved[0] else spawned):
            try:
                if unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor):
                    cleaned += 1
            except Exception:
                pass
        kind = "STOPPED" if isinstance(exc, PlaceError) else "ERROR"
        detail = str(exc) if isinstance(exc, PlaceError) else traceback.format_exc().replace("\n", "\\n")
        unreal.log_error("HP_S03_PLACE_%s|run=%s|reason=%s|spawned=%d|destroyed=%d|saved=%d|census=%s"
                         % (kind, run, detail, len(spawned), cleaned, int(saved[0]), json.dumps(census())))


main()
