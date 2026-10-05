"""Gary 5 Oct (16:50), Scene 3 hangar, two level-only fixes in ONE tool (DRY, then APPLY; REVERT exact).

1. BACKDROP covers the whole far wall.  "S3 Backdrop" (s3_flats_place.py, 1 Oct) was authored as a 20 x 30 m
   plane 3 cm in front of the far wall: landed world (17418.973, 160000, -5), scale 1, covering y 159000..161000
   and z -5..2995 (s3_flats_place_record.json "landed_dock_transform").  It is ATTACHED to the far-wall actor.
   hangar_exit_doors.py (3 Oct 11:40) renamed that actor "S3 Hangar Far Wall Above Exit" and set its relative
   location/scale to the 2430 cm header (hangar_exit_doors.py:971-975, _set_root_local :605-613) without
   detaching the child, so (inferred) the backdrop was squashed to z ~543..2973 and the bottom ~5.5 m of steel
   wall, with the doorway pieces, shows.  This tool puts the backdrop back at its authored WORLD transform
   (parent kept; its relative transform is recomputed by UE).  The far wall, its Left/Right/Below pieces and
   the S3.BackDoorFill patch stay; door-family actors that would still sit IN FRONT of the restored plane are
   hidden (editor + game), recorded.  Other actors in front are only listed.
2. MARBLE to full side-wall height.  The 3 Oct liners ("S3 Marble Inner Wall Left/Right", s3_walls_marble.py)
   cover z -5..600.  The marble MI exposes no UV/tiling scalar (S3_MARBLE_WET_PARAMS log line), so the liner is
   NOT stretched: n added tiles, same mesh/material/x/y/thickness, stacked from the liner top to the side-wall
   top, each tile height = span / round(span / liner height), alternate tiles mirrored in Z (vein continuity at
   the seams).  The base liners are untouched, so the hand-print table (walls_S03.json, receiving surface = the
   base liner, decal centres inside z <= 600) is unchanged and no tile is in front of any decal.

Args s3_backwall_marble_args.json:
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> S3BWM", "parts": ["backdrop", "marble"],
   "marble_mirror_alternate": true, "marble_top_z": null, "max_tile_squash": 0.15}
Markers: S3_BACKWALL_MARBLE_PLAN / _DRY_OK / _APPLY_OK / _REVERT_OK / _FAILED, all with run=<id>.
Importing without Unreal (offline harness) runs nothing.
"""
import datetime
import json
import math
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # offline harness
    unreal = None

HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
ARGS = HERE + "s3_backwall_marble_args.json"
REC = HERE + "s3_backwall_marble_record.json"
DRY_OUT = HERE + "s3_backwall_marble_dry.json"
BACKUP_ROOT = "E:/PussStage/Backups/PreS3BackwallMarble-"
HP_PLACEMENT = "E:/PussStage/DerivedAssets/FlatV3/HandPrints/placement_S03.json"

ROOT = "S3 Hangar Root"
BACKDROP = "S3 Backdrop"
FAR_WALL = "S3 Hangar Far Wall Above Exit"
SIDE_WALLS = {"L": "S3 Hangar Left Wall", "R": "S3 Hangar Right Wall"}
LINERS = {"L": "S3 Marble Inner Wall Left", "R": "S3 Marble Inner Wall Right"}
ROOF = "S3 Hangar Roof"
DOOR_FAMILY = ("S3 Hangar Exit Door Leaf", "S3 Hangar Exit Black", "S3 Hangar Far Wall Left of Exit",
               "S3 Hangar Far Wall Right of Exit", "S3 Hangar Far Wall Below Exit",
               "S3 Hangar Far Wall Exit Fill (door closed)", FAR_WALL)
# Authored landed pose of the backdrop: s3_flats_place_record.json landed_dock_transform (6497, 0, -5) in the
# dock frame whose origin is s3_flats_place.py DOCK_ORIGIN (10921.973, 160000, 0), yaw 0.
BACKDROP_DESIGN = {"location": [17418.973, 160000.0, -5.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
# Its relative transform to the far-wall actor as authored (same record, relative_to_parent_for_landed_pose).
BACKDROP_DESIGN_RELATIVE = {"location": [-55.999500000005355, 0.0, -46.166666666666664],
                            "scale": [2.0, 0.047619047619047616, 0.03333333333333333]}
HP_DECAL_Z_CEILING = 600.0      # hp_place_decals.py / walls_S03.json landed_box_world_cm max z (decal centres)
TILE_TAG = "RigAtmos.S3MarbleLinerUpper"
RUN_TAG_PREFIX = "S3.BackwallMarble.run."
TILE_FOLDER = "RigAtmos/S3Marble"
CUBE_HALF = 50.0                # Engine Cube local half-extent (cm)
TOL = 0.5


class PlanError(ValueError):
    pass


# ----------------------------------------------------------------------------------------------- pure planning
def aabb_of_scaled_cube(center, scale):
    half = [abs(float(s)) * CUBE_HALF for s in scale]
    return {"min": [center[i] - half[i] for i in range(3)], "max": [center[i] + half[i] for i in range(3)]}


def aabb_from_local(local_box, location, scale):
    """Axis-aligned bounds of a mesh box under an unrotated transform (rotation is gated to zero)."""
    lo = [location[i] + min(local_box["min"][i] * scale[i], local_box["max"][i] * scale[i]) for i in range(3)]
    hi = [location[i] + max(local_box["min"][i] * scale[i], local_box["max"][i] * scale[i]) for i in range(3)]
    return {"min": lo, "max": hi}


def overlaps(a, b, axes=(0, 1, 2), slack=0.0):
    return all(a["min"][i] < b["max"][i] - slack and a["max"][i] > b["min"][i] + slack for i in axes)


def near(a, b, tol=TOL):
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def predicted_child_world(parent_world, relative):
    """Unrotated parent: child world = parent location + parent scale * relative location; scale multiplies."""
    loc = [parent_world["location"][i] + parent_world["scale"][i] * relative["location"][i] for i in range(3)]
    scl = [parent_world["scale"][i] * relative["scale"][i] for i in range(3)]
    return {"location": loc, "scale": scl}


def plan_backdrop(state):
    bd = state["backdrop"]
    wall = state["far_wall"]
    if any(abs(float(v)) > 0.01 for v in bd["world"]["rotation"]):
        raise PlanError("BACKDROP_ROTATED|%s" % bd["world"]["rotation"])
    if bd["parent_label"] != FAR_WALL:
        raise PlanError("BACKDROP_PARENT|%s" % bd["parent_label"])
    target = aabb_from_local(bd["mesh_local_box"], BACKDROP_DESIGN["location"], BACKDROP_DESIGN["scale"])
    front = wall["aabb"]["min"][0]
    plane_x = target["max"][0]
    left_face = state["side_walls"]["L"]["aabb"]["max"][1]
    right_face = state["side_walls"]["R"]["aabb"]["min"][1]
    wall_top = max(state["side_walls"][k]["aabb"]["max"][2] for k in "LR")
    floor_z = min(state["liners"][k]["aabb"]["min"][2] for k in "LR")
    fails = []
    if not (front - 10.0 <= plane_x < front):
        fails.append("TARGET_NOT_JUST_IN_FRONT|plane_x=%.3f|wall_front=%.3f" % (plane_x, front))
    if target["min"][1] > left_face + 1.0 or target["max"][1] < right_face - 1.0:
        fails.append("TARGET_NOT_SIDE_TO_SIDE|y=%s|faces=%s" % ([target["min"][1], target["max"][1]],
                                                                  [left_face, right_face]))
    if target["min"][2] > floor_z + TOL or target["max"][2] < wall_top - TOL:
        fails.append("TARGET_NOT_FLOOR_TO_TOP|z=%s|need=%s" % ([target["min"][2], target["max"][2]],
                                                                 [floor_z, wall_top]))
    if fails:
        raise PlanError(";".join(fails))
    squash = predicted_child_world(state["far_wall"]["world"], BACKDROP_DESIGN_RELATIVE)
    live = bd["world"]
    needs = not (near(live["location"], BACKDROP_DESIGN["location"]) and
                 near(live["scale"], BACKDROP_DESIGN["scale"], 1e-4))
    mechanism = ("parent_rescale_squash" if near(live["location"], squash["location"], 1.0) and
                 near(live["scale"], squash["scale"], 1e-3) else ("at_design" if not needs else "other"))
    # Anything still visible in front of the restored plane, overlapping its face.
    pokes, foreign = [], []
    face = {"min": [plane_x - 60.0, target["min"][1], target["min"][2]],
            "max": [plane_x - 0.001, target["max"][1], target["max"][2]]}
    for row in state["near_far_wall"]:
        if row["label"] == BACKDROP or row.get("hidden") or not overlaps(row["aabb"], face):
            continue
        (pokes if row["label"] in DOOR_FAMILY else foreign).append(row["label"])
    return {"needs_restore": needs, "mechanism": mechanism, "live_world": live,
            "live_aabb": bd["aabb"], "target_world": BACKDROP_DESIGN, "target_aabb": target,
            "predicted_squash_world": squash, "wall_front_x": front, "wall_top_z": wall_top,
            "side_faces_y": [left_face, right_face], "hide_door_pokes": sorted(pokes),
            "foreign_in_front_listed_only": sorted(foreign),
            "uncovered_band_z_now": [floor_z, bd["aabb"]["min"][2]] if bd["aabb"]["min"][2] > floor_z + TOL else None}


def hp_decal_boxes(table):
    """Conservative world boxes of planned hand-print decals (half extents = max of DecalSize)."""
    out = []
    for d in (table or {}).get("decals", []):
        r = max(float(v) for v in d["decal_size"])
        out.append({"label": d.get("label"), "aabb": {"min": [float(d["location"][i]) - r for i in range(3)],
                                                      "max": [float(d["location"][i]) + r for i in range(3)]}})
    return out


def plan_tiles(state, args, decals=()):
    mirror = bool(args.get("marble_mirror_alternate", True))
    max_squash = float(args.get("max_tile_squash", 0.15))
    rows, fails = [], []
    for side in "LR":
        liner = state["liners"][side]
        wall = state["side_walls"][side]
        if liner["parent_label"] != SIDE_WALLS[side]:
            fails.append("LINER_PARENT|%s|%s" % (side, liner["parent_label"]))
            continue
        if any(abs(float(v)) > 0.01 for v in liner["world"]["rotation"]):
            fails.append("LINER_ROTATED|" + side)
            continue
        base_h = abs(float(liner["world"]["scale"][2])) * 2.0 * CUBE_HALF
        base_top = liner["aabb"]["max"][2]
        top = float(args["marble_top_z"]) if args.get("marble_top_z") is not None else wall["aabb"]["max"][2]
        if top > wall["aabb"]["max"][2] + TOL:
            fails.append("TOP_ABOVE_WALL|%s|%.2f>%.2f" % (side, top, wall["aabb"]["max"][2]))
            continue
        span = top - base_top
        if span < 1.0:
            continue
        n = max(1, int(round(span / base_h)))
        tile_h = span / n
        squash = tile_h / base_h
        if abs(1.0 - squash) > max_squash:
            fails.append("TILE_SQUASH|%s|%.3f" % (side, squash))
            continue
        if base_top < HP_DECAL_Z_CEILING - 0.01:
            fails.append("TILES_WOULD_START_BELOW_HANDPRINT_CEILING|%s|%.2f" % (side, base_top))
            continue
        for k in range(1, n + 1):
            cz = base_top + (k - 0.5) * tile_h
            sz = tile_h / (2.0 * CUBE_HALF) * (-1.0 if (mirror and k % 2 == 1) else 1.0)
            loc = [liner["world"]["location"][0], liner["world"]["location"][1], cz]
            scale = [liner["world"]["scale"][0], liner["world"]["scale"][1], sz]
            box = aabb_of_scaled_cube(loc, scale)
            row = {"side": side, "label": "%s Upper %d" % (LINERS[side], k), "wall_label": SIDE_WALLS[side],
                   "location": loc, "rotation": [0.0, 0.0, 0.0], "scale": scale, "aabb": box,
                   "mirrored": sz < 0, "tile_h": tile_h, "squash": squash,
                   "mesh": liner["mesh"], "material": liner["material"]}
            if not (near([box["min"][0], box["min"][1]], [liner["aabb"]["min"][0], liner["aabb"]["min"][1]]) and
                    near([box["max"][0], box["max"][1]], [liner["aabb"]["max"][0], liner["aabb"]["max"][1]])):
                fails.append("TILE_NOT_COPLANAR|" + row["label"])
            if box["max"][2] > wall["aabb"]["max"][2] + TOL:
                fails.append("TILE_ABOVE_WALL|" + row["label"])
            for d in decals:
                if overlaps(box, d["aabb"]):
                    fails.append("TILE_HITS_DECAL|%s|%s" % (row["label"], d["label"]))
            rows.append(row)
    taken = set(state.get("labels_present", []))
    clash = [r["label"] for r in rows if r["label"] in taken]
    if clash:
        fails.append("TILE_LABELS_EXIST|" + ",".join(clash))
    if fails:
        raise PlanError(";".join(fails))
    return rows


def build_plan(state, args, decals=()):
    parts = list(args.get("parts") or ["backdrop", "marble"])
    if not parts or any(p not in ("backdrop", "marble") for p in parts):
        raise PlanError("PARTS|%s" % parts)
    plan = {"parts": parts}
    if "backdrop" in parts:
        plan["backdrop"] = plan_backdrop(state)
    if "marble" in parts:
        plan["tiles"] = plan_tiles(state, args, decals)
    return plan


def check_mode(args, record_exists):
    mode = str(args.get("mode", "DRY")).upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise PlanError("MODE|" + mode)
    if mode != "DRY" and args.get("confirm") != "%s S3BWM" % mode:
        raise PlanError("CONFIRM_MISSING")
    if mode == "APPLY" and record_exists:
        raise PlanError("ALREADY_APPLIED")
    if mode == "REVERT" and not record_exists:
        raise PlanError("NO_RECORD")
    return mode


# ------------------------------------------------------------------------------------------------- unreal glue
def _v(x):
    return [float(x.x), float(x.y), float(x.z)]


def _r(rot):
    return [float(rot.roll), float(rot.pitch), float(rot.yaw)]


def _box(actor):
    o, e = actor.get_actor_bounds(False)
    return {"min": [o.x - e.x, o.y - e.y, o.z - e.z], "max": [o.x + e.x, o.y + e.y, o.z + e.z]}


def _path(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj is not None else None


def _smc(actor):
    comps = list(actor.get_components_by_class(unreal.StaticMeshComponent))
    return comps[0] if len(comps) == 1 else None


def _world(actor):
    return {"location": _v(actor.get_actor_location()), "rotation": _r(actor.get_actor_rotation()),
            "scale": _v(actor.get_actor_scale3d())}


def _relative(actor):
    rc = actor.root_component
    return {"location": _v(rc.get_editor_property("relative_location")),
            "rotation": _r(rc.get_editor_property("relative_rotation")),
            "scale": _v(rc.get_editor_property("relative_scale3d"))}


def _parent(actor):
    p = actor.get_attach_parent_actor()
    return str(p.get_actor_label()) if p else None


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def _index():
    out = {}
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        out.setdefault(str(a.get_actor_label()), []).append(a)
    return out


def _one(index, label):
    rows = index.get(label, [])
    if len(rows) != 1:
        raise PlanError("COUNT|%s|%d" % (label, len(rows)))
    return rows[0]


def _hidden(actor):
    return bool(actor.get_editor_property("hidden"))


def live_state(index):
    bd = _one(index, BACKDROP)
    comp = _smc(bd)
    if comp is None or comp.get_editor_property("static_mesh") is None:
        raise PlanError("BACKDROP_MESH")
    mb = comp.get_editor_property("static_mesh").get_bounding_box()
    mi = comp.get_material(0)
    blend = None
    try:
        blend = str(mi.get_base_material().get_editor_property("blend_mode"))
    except Exception:
        pass
    fw = _one(index, FAR_WALL)
    state = {"backdrop": {"label": BACKDROP, "parent_label": _parent(bd), "world": _world(bd),
                          "relative": _relative(bd), "aabb": _box(bd), "hidden": _hidden(bd),
                          "mesh": _path(comp.get_editor_property("static_mesh")), "material": _path(mi),
                          "material_blend_mode": blend,
                          "mesh_local_box": {"min": _v(mb.min), "max": _v(mb.max)}},
             "far_wall": {"label": FAR_WALL, "world": _world(fw), "aabb": _box(fw), "parent_label": _parent(fw)},
             "side_walls": {}, "liners": {}, "near_far_wall": [], "near_liners": [],
             "labels_present": sorted(index)}
    for k in "LR":
        w = _one(index, SIDE_WALLS[k])
        state["side_walls"][k] = {"label": SIDE_WALLS[k], "world": _world(w), "aabb": _box(w)}
        ln = _one(index, LINERS[k])
        lc = _smc(ln)
        if lc is None:
            raise PlanError("LINER_COMPONENT|" + LINERS[k])
        state["liners"][k] = {"label": LINERS[k], "world": _world(ln), "aabb": _box(ln), "parent_label": _parent(ln),
                              "mesh": _path(lc.get_editor_property("static_mesh")), "material": _path(lc.get_material(0)),
                              "tags": [str(t) for t in ln.tags]}
    roofs = index.get(ROOF, [])
    state["roof_aabb"] = _box(roofs[0]) if len(roofs) == 1 else None
    bb = state["backdrop"]["aabb"]
    slab = {"min": [bb["min"][0] - 100.0, bb["min"][1] - 60.0, -200.0],
            "max": [state["far_wall"]["aabb"]["max"][0] + 10.0, bb["max"][1] + 60.0, 3100.0]}
    for label, actors in index.items():
        for a in actors:
            try:
                box = _box(a)
            except Exception:
                continue
            if box["max"][0] - box["min"][0] > 4000.0:   # side walls, liners, roof, rails: not far-wall candidates
                continue
            if overlaps(box, slab):
                state["near_far_wall"].append({"label": label, "class": a.get_class().get_name(), "aabb": box,
                                               "hidden": _hidden(a), "parent_label": _parent(a)})
    hp = [a for actors in index.values() for a in actors if "HP_S03" in [str(t) for t in a.tags]]
    state["hp_decals_live"] = [{"label": str(a.get_actor_label()), "aabb": _box(a)} for a in hp]
    return state


def _decals_for_gate(state):
    rows = list(state.get("hp_decals_live", []))
    if os.path.isfile(HP_PLACEMENT):
        with open(HP_PLACEMENT, encoding="utf-8") as h:
            rows += hp_decal_boxes(json.load(h))
    return rows


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as h:
        json.dump(value, h, indent=1)
        h.flush()
        os.fsync(h.fileno())


def _hide(actor, value):
    actor.modify()
    actor.set_editor_property("hidden", bool(value))
    actor.set_actor_hidden_in_game(bool(value))


def _spawn_tile(row, wall, run):
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    rot = unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0)
    a = sub.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*row["location"]), rot)
    if a is None:
        raise PlanError("SPAWN|" + row["label"])
    a.set_actor_label(row["label"])
    a.set_folder_path(TILE_FOLDER)
    a.tags = [unreal.Name(TILE_TAG), unreal.Name(RUN_TAG_PREFIX + run), unreal.Name("S3.Marble.InnerFace")]
    c = a.get_editor_property("static_mesh_component")
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_static_mesh(unreal.load_asset(row["mesh"]))
    c.set_material(0, unreal.load_asset(row["material"]))
    a.set_actor_scale3d(unreal.Vector(*row["scale"]))
    a.set_actor_location(unreal.Vector(*row["location"]), False, False)
    a.attach_to_actor(wall, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                      unreal.AttachmentRule.KEEP_WORLD, False)
    return a


def _verify_tile(a, row):
    c = _smc(a)
    got = _box(a)
    if (_parent(a) != row["wall_label"] or not near(got["min"], row["aabb"]["min"]) or
            not near(got["max"], row["aabb"]["max"]) or _path(c.get_material(0)) != row["material"] or
            _mirrored(a) != row["mirrored"]):
        raise PlanError("TILE_READBACK|%s|%s" % (row["label"], json.dumps(got)))


def _mirrored(actor):
    """Handedness, not the z sign: a negative-scale attach may move the sign to another axis plus a 180 deg
    rotation (memory: mirrored ISM readback flips onto X), which is the same geometry."""
    s = actor.get_actor_scale3d()
    return float(s.x) * float(s.y) * float(s.z) < 0.0


def _save_level(ed):
    bad = [k for k in _index() if k.startswith("ZZ_") or "TEMP" in k.upper()]
    if bad:
        raise PlanError("TEMP_ACTORS_PRESENT|%s" % bad[:5])
    dirty = _census()
    if dirty["content"] or dirty["maps"] != [WORLD]:
        raise PlanError("DIRTY_SCOPE|%s" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        raise PlanError("SAVE_FAILED")
    if _census() != {"content": [], "maps": []}:
        raise PlanError("POST_SAVE_DIRTY|" + json.dumps(_census()))


def run_apply(run, args, ed):
    index = _index()
    state = live_state(index)
    plan = build_plan(state, args, _decals_for_gate(state))
    backup = BACKUP_ROOT + run
    record = {"run": run, "world": WORLD, "backup": backup, "applied": False, "parts": plan["parts"], "plan": plan,
              "before": {"backdrop": {"relative": state["backdrop"]["relative"], "world": state["backdrop"]["world"],
                                      "aabb": state["backdrop"]["aabb"]},
                         "hidden": {}}, "spawned": []}
    _write(REC, record, exclusive=True)
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    if not os.path.isfile(os.path.join(backup, os.path.basename(UMAP))):
        raise PlanError("BACKUP_MISSING")
    if "backdrop" in plan["parts"]:
        b = plan["backdrop"]
        for label in b["hide_door_pokes"]:
            record["before"]["hidden"][label] = False
        _write(REC, record)
        bd = _one(index, BACKDROP)
        if b["needs_restore"]:
            bd.modify()
            bd.set_actor_scale3d(unreal.Vector(*BACKDROP_DESIGN["scale"]))
            bd.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0), False)
            bd.set_actor_location(unreal.Vector(*BACKDROP_DESIGN["location"]), False, False)
        for label in b["hide_door_pokes"]:
            _hide(_one(index, label), True)
        got = _box(bd)
        if (_parent(bd) != FAR_WALL or not near(got["min"], b["target_aabb"]["min"]) or
                not near(got["max"], b["target_aabb"]["max"])):
            raise PlanError("BACKDROP_READBACK|%s" % json.dumps(got))
        if any(not _hidden(_one(index, label)) for label in b["hide_door_pokes"]):
            raise PlanError("HIDE_READBACK")
    if "marble" in plan["parts"]:
        for row in plan["tiles"]:
            a = _spawn_tile(row, _one(index, row["wall_label"]), run)
            _verify_tile(a, row)
            record["spawned"].append({"label": row["label"], "object_path": a.get_path_name(), "aabb": _box(a)})
            _write(REC, record)
    _save_level(ed)
    record["saved"] = True
    _write(REC, record)
    after = _index()                                             # read back from a fresh index, after the save
    if "backdrop" in plan["parts"]:
        got = _box(_one(after, BACKDROP))
        if not (near(got["min"], plan["backdrop"]["target_aabb"]["min"]) and
                near(got["max"], plan["backdrop"]["target_aabb"]["max"])):
            raise PlanError("POST_SAVE_BACKDROP|%s" % json.dumps(got))
    for row in plan.get("tiles", []):
        _verify_tile(_one(after, row["label"]), row)
    record["applied"] = True
    record["post_save_census"] = _census()
    _write(REC, record)
    return {"backdrop_restored": bool(plan.get("backdrop", {}).get("needs_restore")),
            "hidden": plan.get("backdrop", {}).get("hide_door_pokes", []), "tiles": len(plan.get("tiles", []))}


def run_revert(run, ed):
    with open(REC, encoding="utf-8") as h:
        record = json.load(h)
    if record.get("world") != WORLD or not (record.get("applied") or record.get("saved")):
        raise PlanError("RECORD_INVALID")
    index = _index()
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    tiles = []
    for row in record["spawned"]:
        a = _one(index, row["label"])
        if a.get_path_name() != row["object_path"] or RUN_TAG_PREFIX + record["run"] not in [str(t) for t in a.tags]:
            raise PlanError("OWNERSHIP|" + row["label"])
        tiles.append(a)
    backup = BACKUP_ROOT + run
    os.makedirs(backup)
    shutil.copy2(UMAP, backup)
    if "backdrop" in record["parts"]:
        bd = _one(index, BACKDROP)
        rel = record["before"]["backdrop"]["relative"]
        bd.modify()
        bd.set_actor_relative_scale3d(unreal.Vector(*rel["scale"]))
        bd.set_actor_relative_rotation(unreal.Rotator(roll=rel["rotation"][0], pitch=rel["rotation"][1],
                                                      yaw=rel["rotation"][2]), False, False)
        bd.set_actor_relative_location(unreal.Vector(*rel["location"]), False, False)
        for label, was in record["before"]["hidden"].items():
            _hide(_one(index, label), was)
    for a in tiles:
        a.modify()
        if not sub.destroy_actor(a):
            raise PlanError("DESTROY|" + str(a.get_actor_label()))
    after = _index()
    if any(after.get(row["label"]) for row in record["spawned"]):
        raise PlanError("TILES_SURVIVE")
    if "backdrop" in record["parts"]:
        bd = _one(after, BACKDROP)
        if not (near(_relative(bd)["location"], rel["location"], 1e-3) and
                near(_relative(bd)["scale"], rel["scale"], 1e-6) and
                near(_box(bd)["min"], record["before"]["backdrop"]["aabb"]["min"]) and
                near(_box(bd)["max"], record["before"]["backdrop"]["aabb"]["max"])):
            raise PlanError("REVERT_BACKDROP_READBACK|%s" % json.dumps(_box(bd)))
        if any(_hidden(_one(after, k)) != v for k, v in record["before"]["hidden"].items()):
            raise PlanError("REVERT_HIDE_READBACK")
    _save_level(ed)
    os.replace(REC, REC + ".reverted-" + run)
    return {"tiles_destroyed": len(tiles), "backdrop_restored_to_before": "backdrop" in record["parts"]}


def main():
    run = datetime.datetime.now().strftime("S3BWM-%Y%m%d-%H%M%S")
    mode = "DRY"
    try:
        with open(ARGS, encoding="utf-8") as h:
            args = json.load(h)
        mode = check_mode(args, os.path.exists(REC))
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = ed.get_editor_world()
        if world is None or world.get_outermost().get_name() != WORLD:
            raise PlanError("WRONG_WORLD")
        if ed.get_game_world() is not None:
            raise PlanError("PIE_ACTIVE")
        census = _census()
        if mode == "DRY":
            state = live_state(_index())
            plan = build_plan(state, args, _decals_for_gate(state))
            out = {"run": run, "census": census, "apply_would_refuse_dirty": census != {"content": [], "maps": []},
                   "state": state, "plan": plan}
            out["state"].pop("labels_present", None)
            _write(DRY_OUT, out)
            unreal.log("S3_BACKWALL_MARBLE_PLAN|run=%s|%s" % (run, json.dumps(
                {"backdrop": {k: plan["backdrop"][k] for k in ("needs_restore", "mechanism", "live_aabb",
                                                                 "target_aabb", "uncovered_band_z_now",
                                                                 "hide_door_pokes", "foreign_in_front_listed_only")}
                              if "backdrop" in plan else None,
                 "blend_mode": state["backdrop"]["material_blend_mode"],
                 "tiles": [(t["label"], round(t["aabb"]["min"][2], 2), round(t["aabb"]["max"][2], 2), t["mirrored"])
                           for t in plan.get("tiles", [])],
                 "hp_decals_live": len(state["hp_decals_live"]), "census": census})))
            if census != {"content": [], "maps": []}:
                unreal.log_warning("S3_BACKWALL_MARBLE_DRY_DIRTY|run=%s|%s" % (run, json.dumps(census)))
            unreal.log("S3_BACKWALL_MARBLE_DRY_OK|run=%s|mutated=0|out=%s" % (run, DRY_OUT))
            return
        if census != {"content": [], "maps": []}:
            raise PlanError("DIRTY_BEFORE|" + json.dumps(census))
        if mode == "APPLY":
            try:
                result = run_apply(run, args, ed)
            except Exception:
                if os.path.exists(REC):
                    rec = json.load(open(REC, encoding="utf-8"))
                    if not rec.get("saved"):
                        os.replace(REC, REC + ".failed-" + run)
                raise
        else:
            result = run_revert(run, ed)
        unreal.log("S3_BACKWALL_MARBLE_%s_OK|run=%s|level_saved=1|dirty_after=0+0|%s" % (mode, run, json.dumps(result)))
    except Exception as exc:
        unreal.log_error("S3_BACKWALL_MARBLE_FAILED|run=%s|mode=%s|%s|census=%s|%s" % (
            run, mode, str(exc).replace("\n", " "), json.dumps(_census()),
            "NOTHING SAVED unless an _OK marker printed; if the map is dirty: Don't-Save restart" if mode != "DRY"
            else "DRY mutated nothing"))
        raise


if unreal is not None:
    main()
