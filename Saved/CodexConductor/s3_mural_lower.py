"""Gary 7 Oct (his words): "the mural image on the back wall in this scene [S3] can be lowered about 1.5m too,
cropping the lower part."  ONE level-only edit: "S3 Backdrop" moves DOWN by drop_cm (default 150) in WORLD z,
keeping its world x / y / rotation / scale.  Its bottom drop_cm then sits below the deck top (cropped by the floor).

Written 7 Oct OFFLINE (Unreal not called).  Report + evidence tiers: Docs/Conductor/S3_MURAL_LOWER_2026-10-07.md.

How the backdrop is authored (see the report for tiers):
  * StaticMeshActor "S3 Backdrop", MOVABLE, attached to "S3 Hangar Far Wall Above Exit" (a Cube scaled 0.5/21/24.3)
    which is attached to "S3 Hangar Root".  The 3 Oct far-wall rescale squashed it once (s3_backwall_marble.py:3-12);
    so this tool never touches the parent and never writes a relative SCALE.  APPLY calls set_actor_location(world)
    only; UE recomputes the relative location through the parent (parent inverse incl. its non-uniform scale), and
    the read-back checks that relative == ParentInverse(target) computed here from the live parent transform.
  * The target is composed in the LIVE "S3 Hangar Root" frame (memory: level-saved-LANDED frame trap): root-local
    location minus (0, 0, drop), mapped back through the live root.  The root must be at its LANDED pose (measured
    11421.97275 / 160000 / -120, rot 0, scale 1) or the tool refuses; the predicted backdrop box must lie inside a
    landed root-local guard box.
  * The exit-door "mimic" (hangar_exit_doors.py, strategy cropped_texture_child_mi) does NOT sample by world
    position: it is a BAKED crop (3 cropped textures + leaf mesh whose UV1 is hard-coded in backdrop metres) built for
    a backdrop bottom at world z -5 (Tools/FlatV3/build_s3_exit_door_crop.py:27, build_s3_exit_door_mesh.py:41-43).
    After a drop the leaf would show art 150 cm off (dv = drop/3000).  The leaf has been HIDDEN since Gary's "Close
    the wall" (s3_close_back_door.py, run S3DOOR-20261005-104600), so the mimic is retired and NOT re-cropped here:
    APPLY asserts leaf + black are still hidden and refuses (DOOR_MIMIC_VISIBLE_RECROP_REQUIRED) otherwise.  The new
    crop rect is written to the record for whoever re-opens the door.

Args s3_mural_lower_args.json:
  {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> S3MURAL", "drop_cm": 150.0,
   "top_gap_policy": null|"accept", "expect_bottom_local_z": 115.0, "run": optional}
  top_gap_policy: if the lowered top leaves bare far wall under the roof (measured roof underside 2880 world = local
  3000 vs. lowered top 2845 world = local 2965), APPLY refuses TOP_GAP_DECISION_REQUIRED unless "accept".  That is
  a look decision for Gary (alternative: drop_cm 115 keeps the top flush with the roof underside).
Markers (all with run=<id>): S3MURAL_PLAN, S3MURAL_DRY_OK, S3MURAL_APPLY_OK, S3MURAL_REVERT_OK, S3MURAL_FAILED.
An _OK marker is logged only after every asserted read-back and the census-exact save.
Importing this file never runs anything; the runner (s3_mural_lower_run.py) calls main().  No UE object is kept at
module level (memory puss-mcp-python-crashes-the-editor).
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

PROJECT = "E:/PussStage/"
HERE = PROJECT + "Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = PROJECT + "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
ARGS = HERE + "s3_mural_lower_args.json"
REC = HERE + "s3_mural_lower_record.json"
DRY_OUT = HERE + "s3_mural_lower_dry.json"
BACKUP_ROOT = PROJECT + "Backups/PreS3MuralLower-"
CROP_MANIFEST = PROJECT + "DerivedAssets/FlatV3/Scene3/backdrop/exit_door_crop/s3_exit_door_crop_manifest.json"

ROOT = "S3 Hangar Root"
BACKDROP = "S3 Backdrop"
FAR_WALL = "S3 Hangar Far Wall Above Exit"
ROOF = "S3 Hangar Roof"
DECK = "S3 Hangar Deck"
SHORE = "S3 Shore Ground"
SIDE_WALLS = ("S3 Hangar Left Wall", "S3 Hangar Right Wall")
LEAF = "S3 Hangar Exit Door Leaf"
BLACK = "S3 Hangar Exit Black"
FILL_TAG = "S3.BackDoorFill"

ROOT_LANDED_WORLD = (11421.97275, 160000.0, -120.0)   # measured: s3_shore_live_reads.json run S3SHORE-20261007-181646
BACKDROP_MESH_H = 3000.0                               # mesh local z 0..3000, y -1000..1000 (s3_backwall_marble_dry.json)
BACKDROP_MESH_W = 2000.0
# Landed root-local guard for the backdrop AFTER the move: plane between the deck front and the far-wall face (6000),
# side to side, bottom no deeper than 60 cm under the root origin, top under 3120.
GUARD_LOCAL = {"min": [5990.0, -1001.0, -60.0], "max": [6000.0, 1001.0, 3120.0]}
MAX_DROP_CM = 175.0
TOL_CM = 0.05
TOL_UV = 1.0e-4


class PlanError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------- pure math (UE)
def rot_matrix(rpy):
    """UE FRotationMatrix rows = world X/Y/Z axes of the rotated frame. rpy = [roll, pitch, yaw] degrees."""
    r, p, y = [math.radians(float(v)) for v in rpy]
    sr, cr, sp, cp, sy, cy = math.sin(r), math.cos(r), math.sin(p), math.cos(p), math.sin(y), math.cos(y)
    return ((cp * cy, cp * sy, sp),
            (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp),
            (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp))


def tf_point(tf, p):
    """FTransform::TransformPosition: R * (S * p) + T (UE row-vector convention)."""
    m = rot_matrix(tf["rotation"])
    s = [float(p[i]) * float(tf["scale"][i]) for i in range(3)]
    return [float(tf["location"][j]) + sum(s[i] * m[i][j] for i in range(3)) for j in range(3)]


def tf_inv_vector(tf, v):
    m = rot_matrix(tf["rotation"])
    if any(abs(float(s)) < 1e-9 for s in tf["scale"]):
        raise PlanError("ZERO_SCALE")
    local = [sum(float(v[j]) * m[i][j] for j in range(3)) for i in range(3)]
    return [local[i] / float(tf["scale"][i]) for i in range(3)]


def tf_inv_point(tf, p):
    return tf_inv_vector(tf, [float(p[i]) - float(tf["location"][i]) for i in range(3)])


def box_corners(box):
    return [[box["min"][0] if i & 1 else box["max"][0], box["min"][1] if i & 2 else box["max"][1],
             box["min"][2] if i & 4 else box["max"][2]] for i in range(8)]


def box_to_local(tf, world_box):
    pts = [tf_inv_point(tf, c) for c in box_corners(world_box)]
    return {"min": [min(p[i] for p in pts) for i in range(3)], "max": [max(p[i] for p in pts) for i in range(3)]}


def box_inside(box, guard, tol=TOL_CM):
    return all(box["min"][i] >= guard["min"][i] - tol and box["max"][i] <= guard["max"][i] + tol for i in range(3))


def near(a, b, tol):
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def leaf_uv_rect(root_tf, backdrop_tf, leaf_local_box):
    """Same mapping as hangar_exit_doors._s3_leaf_uv_rect (:182-201): the leaf's root-local Y/Z footprint, through the
    root, into backdrop mesh space; u = (y + 1000) / 2000, v = 1 - z / 3000.  Returns [u0, v_top, u1, v_bottom]."""
    x = 0.5 * (leaf_local_box["min"][0] + leaf_local_box["max"][0])
    uv = []
    for y in (leaf_local_box["min"][1], leaf_local_box["max"][1]):
        for z in (leaf_local_box["min"][2], leaf_local_box["max"][2]):
            loc = tf_inv_point(backdrop_tf, tf_point(root_tf, [x, y, z]))
            uv.append(((loc[1] + BACKDROP_MESH_W / 2.0) / BACKDROP_MESH_W, 1.0 - loc[2] / BACKDROP_MESH_H))
    return [min(u for u, _ in uv), min(v for _, v in uv), max(u for u, _ in uv), max(v for _, v in uv)]


# ------------------------------------------------------------------------------------------------- pure planning
def check_mode(args, record_exists):
    mode = str(args.get("mode", "DRY")).upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise PlanError("MODE|" + mode)
    if mode != "DRY" and args.get("confirm") != "%s S3MURAL" % mode:
        raise PlanError("CONFIRM_MISSING|need %r" % ("%s S3MURAL" % mode))
    if mode == "APPLY" and record_exists:
        raise PlanError("ALREADY_APPLIED|record exists: " + REC)
    if mode == "REVERT" and not record_exists:
        raise PlanError("NO_RECORD")
    return mode


def gate_census(census, mode):
    clean = census == {"content": [], "maps": []}
    if mode in ("APPLY", "REVERT") and not clean:
        raise PlanError("DIRTY_BEFORE|" + json.dumps(census))
    return clean


def root_is_landed(root_tf):
    return (near(root_tf["location"], ROOT_LANDED_WORLD, 1.0) and near(root_tf["rotation"], [0, 0, 0], 0.01) and
            near(root_tf["scale"], [1, 1, 1], 1e-4))


def _floor_cover(state, plane_x_local, bd_local):
    """Visible floor whose root-local x range reaches the backdrop plane: that floor crops the lowered bottom."""
    rows = []
    for key in ("deck", "shore_ground"):
        f = state.get(key)
        if not f or f.get("hidden"):
            continue
        fl = f["aabb_local"]
        if (fl["min"][0] <= plane_x_local <= fl["max"][0] + 15.0 and fl["min"][1] <= bd_local["min"][1] + 15.0 and
                fl["max"][1] >= bd_local["max"][1] - 15.0):
            rows.append({"label": f["label"], "top_local_z": fl["max"][2], "x_local": [fl["min"][0], fl["max"][0]]})
    return rows


def plan_lower(state, args):
    drop = float(args.get("drop_cm", 150.0))
    if not (0.0 < drop <= MAX_DROP_CM):
        raise PlanError("DROP_RANGE|%.3f (0, %.0f]" % (drop, MAX_DROP_CM))
    if state.get("temp_actors"):
        raise PlanError("TEMP_ACTORS_PRESENT|%s" % state["temp_actors"][:5])
    root = state["root"]["world"]
    if not root_is_landed(root):
        raise PlanError("ROOT_NOT_LANDED|%s" % json.dumps(root))
    bd = state["backdrop"]
    fails = []
    if bd["parent_label"] != FAR_WALL:
        fails.append("BACKDROP_PARENT|%s" % bd["parent_label"])
    if bd.get("mobility") != "MOVABLE":
        fails.append("BACKDROP_MOBILITY|%s" % bd.get("mobility"))
    if not near(bd["world"]["rotation"], [0, 0, 0], 0.01):
        fails.append("BACKDROP_ROTATED|%s" % bd["world"]["rotation"])
    if not near(bd["world"]["scale"], [1, 1, 1], 1e-3):
        fails.append("BACKDROP_SCALE|%s (squashed again?)" % bd["world"]["scale"])
    if bd.get("children"):
        fails.append("BACKDROP_HAS_CHILDREN|%s" % bd["children"])
    if state["far_wall"].get("parent_label") != ROOT:
        fails.append("FAR_WALL_PARENT|%s" % state["far_wall"].get("parent_label"))
    before_local = box_to_local(root, bd["aabb_world"])
    expect = float(args.get("expect_bottom_local_z", 115.0))
    if abs(before_local["min"][2] - expect) > 1.0:
        fails.append("BACKDROP_NOT_AT_EXPECTED|bottom_local=%.3f|expected=%.3f (already lowered?)"
                     % (before_local["min"][2], expect))
    if fails:
        raise PlanError(";".join(fails))

    # Compose in the LIVE root frame, then back to world; the parent turns it into a relative location.
    loc_local = tf_inv_point(root, bd["world"]["location"])
    target_local = [loc_local[0], loc_local[1], loc_local[2] - drop]
    target_world = tf_point(root, target_local)
    parent = state["far_wall"]["world"]
    predicted_relative = tf_inv_point(parent, target_world)
    delta_world = [target_world[i] - bd["world"]["location"][i] for i in range(3)]
    after_world_box = {"min": [bd["aabb_world"]["min"][i] + delta_world[i] for i in range(3)],
                       "max": [bd["aabb_world"]["max"][i] + delta_world[i] for i in range(3)]}
    after_local = box_to_local(root, after_world_box)
    if not box_inside(after_local, GUARD_LOCAL):
        raise PlanError("GUARD_LOCAL_BOX|after=%s|guard=%s" % (json.dumps(after_local), json.dumps(GUARD_LOCAL)))
    if not near(delta_world, [0.0, 0.0, -drop], TOL_CM):
        raise PlanError("NOT_A_WORLD_Z_DROP|delta=%s" % delta_world)

    # Bottom: which visible floor crops it.
    plane_x = 0.5 * (after_local["min"][0] + after_local["max"][0])
    covers = _floor_cover(state, plane_x, after_local)
    if not covers:
        raise PlanError("BOTTOM_UNCROPPED|no visible deck / shore ground reaches plane x=%.2f" % plane_x)
    floor_top = max(c["top_local_z"] for c in covers)
    bottom = {"cropped_band_local_z": [after_local["min"][2], floor_top], "floor_covers": covers,
              "below_hangar_base_cm": max(0.0, -after_local["min"][2])}

    # Top: does the lowered top leave bare far wall under the roof (or under the side-wall top if no roof)?
    walls_top = max(w["aabb_local"]["max"][2] for w in state["side_walls"].values())
    roof = state.get("roof")
    if roof and not roof.get("hidden"):
        cover_z, cover_by = roof["aabb_local"]["min"][2], ROOF + " underside"
    else:
        cover_z, cover_by = walls_top, "side-wall top (no visible roof)"
    gap = cover_z - after_local["max"][2]
    top = {"top_local_z_before": before_local["max"][2], "top_local_z_after": after_local["max"][2],
           "cover_local_z": cover_z, "cover_by": cover_by, "gap_cm": round(gap, 3) if gap > TOL_CM else 0.0,
           "bare_band_local_z": [after_local["max"][2], cover_z] if gap > TOL_CM else None,
           "max_flush_drop_cm": round(before_local["max"][2] - cover_z, 3),
           "overhead_listed_only": state.get("overhead_near_top", [])}
    policy = args.get("top_gap_policy")
    if policy not in (None, "accept"):
        raise PlanError("TOP_GAP_POLICY|%r" % policy)
    top["apply_allowed"] = top["gap_cm"] == 0.0 or policy == "accept"

    # Door mimic: baked crop.  Prove it was registered to the CURRENT backdrop, and what it would need after.
    door = state["door"]
    mimic = {"strategy": "cropped_texture_child_mi (baked; not world-sampled)", "leaf_hidden": door["leaf"]["hidden"],
             "black_hidden": door["black"]["hidden"], "fills_visible": [f["label"] for f in door["fills"]
                                                                         if not f["hidden"]]}
    leaf_local = box_to_local(root, door["leaf"]["aabb_world"])
    rect_now = leaf_uv_rect(root, bd["world"], leaf_local)
    after_tf = {"location": target_world, "rotation": bd["world"]["rotation"], "scale": bd["world"]["scale"]}
    rect_after = leaf_uv_rect(root, after_tf, leaf_local)
    baked = state.get("crop_manifest_leaf_rect")
    mimic.update({"leaf_local_box": leaf_local, "uv_rect_live_now": rect_now, "uv_rect_needed_after": rect_after,
                  "uv_rect_baked_manifest": baked,
                  "baked_matches_now": bool(baked) and near(rect_now, baked, TOL_UV),
                  "baked_matches_after": bool(baked) and near(rect_after, baked, TOL_UV),
                  "dv_shift": rect_after[1] - rect_now[1],
                  "recrop_note": "re-crop needs BACKDROP_BOTTOM_Z_CM=%.3f in Tools/FlatV3/build_s3_exit_door_crop.py:27 "
                                 "and UV1 v range shifted by %.3f m in build_s3_exit_door_mesh.py:41-43, then a "
                                 "texture + mesh reimport" % (-5.0 - drop, drop / 100.0)})
    if not (door["leaf"]["hidden"] and door["black"]["hidden"]):
        mimic["action"] = "REFUSE"
    else:
        mimic["action"] = "none: leaf + black hidden since S3DOOR-20261005-104600 (Gary 'Close the wall')"
    return {"drop_cm": drop, "root_world": root, "before": {"world": bd["world"], "relative": bd["relative"],
                                                              "aabb_world": bd["aabb_world"], "aabb_local": before_local},
            "target": {"world_location": target_world, "relative_location": predicted_relative,
                       "aabb_world": after_world_box, "aabb_local": after_local, "local_location": target_local},
            "parent_world": parent, "guard_local": GUARD_LOCAL, "bottom": bottom, "top": top, "door_mimic": mimic}


def apply_gates(plan):
    """Refusals that let DRY report but stop APPLY."""
    fails = []
    if not plan["top"]["apply_allowed"]:
        fails.append("TOP_GAP_DECISION_REQUIRED|bare far wall %.1f cm (local z %s) under %s; set top_gap_policy "
                     "'accept' or drop_cm <= %.1f" % (plan["top"]["gap_cm"], plan["top"]["bare_band_local_z"],
                                                     plan["top"]["cover_by"], plan["top"]["max_flush_drop_cm"]))
    if plan["door_mimic"]["action"] == "REFUSE":
        fails.append("DOOR_MIMIC_VISIBLE_RECROP_REQUIRED|leaf_hidden=%s|black_hidden=%s" % (
            plan["door_mimic"]["leaf_hidden"], plan["door_mimic"]["black_hidden"]))
    if fails:
        raise PlanError(";".join(fails))


def verify_after(state, plan):
    """Read-back after APPLY (also after the save, from a fresh index).  Returns failures; [] = pass."""
    f = []
    bd = state["backdrop"]
    if not near(bd["world"]["location"], plan["target"]["world_location"], TOL_CM):
        f.append("WORLD_LOCATION|%s" % bd["world"]["location"])
    if not near(bd["world"]["rotation"], plan["before"]["world"]["rotation"], 0.01):
        f.append("WORLD_ROTATION_CHANGED")
    if not near(bd["world"]["scale"], plan["before"]["world"]["scale"], 1e-4):
        f.append("WORLD_SCALE_CHANGED|%s" % bd["world"]["scale"])
    if not near(bd["relative"]["location"], plan["target"]["relative_location"], 0.01):
        f.append("RELATIVE_LOCATION|%s|want=%s" % (bd["relative"]["location"], plan["target"]["relative_location"]))
    if not (near(bd["relative"]["rotation"], plan["before"]["relative"]["rotation"], 0.01) and
            near(bd["relative"]["scale"], plan["before"]["relative"]["scale"], 1e-6)):
        f.append("RELATIVE_ROT_OR_SCALE_CHANGED")
    if bd["parent_label"] != FAR_WALL:
        f.append("PARENT|%s" % bd["parent_label"])
    if not (near(state["far_wall"]["world"]["location"], plan["parent_world"]["location"], TOL_CM) and
            near(state["far_wall"]["world"]["scale"], plan["parent_world"]["scale"], 1e-6) and
            near(state["far_wall"]["world"]["rotation"], plan["parent_world"]["rotation"], 0.001)):
        f.append("PARENT_MOVED")
    root = state["root"]["world"]
    if not (near(root["location"], plan["root_world"]["location"], TOL_CM) and
            near(root["rotation"], plan["root_world"]["rotation"], 0.001) and
            near(root["scale"], plan["root_world"]["scale"], 1e-6)):
        f.append("ROOT_MOVED")
    for side in ("min", "max"):
        if not near(bd["aabb_world"][side], plan["target"]["aabb_world"][side], TOL_CM * 2):
            f.append("AABB_%s|%s" % (side.upper(), bd["aabb_world"][side]))
    local = box_to_local(root, bd["aabb_world"])
    if not box_inside(local, GUARD_LOCAL):
        f.append("GUARD_LOCAL_BOX|%s" % json.dumps(local))
    if abs((bd["world"]["location"][0] - plan["before"]["world"]["location"][0])) > TOL_CM or \
            abs((bd["world"]["location"][1] - plan["before"]["world"]["location"][1])) > TOL_CM:
        f.append("WORLD_XY_MOVED")
    if not (state["door"]["leaf"]["hidden"] and state["door"]["black"]["hidden"]):
        f.append("DOOR_UNHIDDEN")
    return f


def verify_revert(state, record):
    f = []
    bd = state["backdrop"]
    before = record["plan"]["before"]
    if not near(bd["relative"]["location"], before["relative"]["location"], 1e-3):
        f.append("RELATIVE_LOCATION|%s|want=%s" % (bd["relative"]["location"], before["relative"]["location"]))
    if not (near(bd["relative"]["rotation"], before["relative"]["rotation"], 0.001) and
            near(bd["relative"]["scale"], before["relative"]["scale"], 1e-7)):
        f.append("RELATIVE_ROT_OR_SCALE")
    if not near(bd["world"]["location"], before["world"]["location"], TOL_CM):
        f.append("WORLD_LOCATION|%s" % bd["world"]["location"])
    if not near(bd["world"]["scale"], before["world"]["scale"], 1e-4):
        f.append("WORLD_SCALE")
    for side in ("min", "max"):
        if not near(bd["aabb_world"][side], before["aabb_world"][side], TOL_CM * 2):
            f.append("AABB_%s" % side.upper())
    if bd["parent_label"] != FAR_WALL:
        f.append("PARENT")
    return f


def revert_gate(state, record):
    """The live backdrop must still be where APPLY left it, else someone moved it since: refuse."""
    bd = state["backdrop"]
    if not near(bd["relative"]["location"], record["plan"]["target"]["relative_location"], 0.01) or \
            not near(bd["world"]["location"], record["plan"]["target"]["world_location"], TOL_CM):
        raise PlanError("DRIFT_SINCE_APPLY|live=%s" % json.dumps(bd["world"]["location"]))


# ------------------------------------------------------------------------------------------------- unreal glue
def _v(x):
    return [float(x.x), float(x.y), float(x.z)]


def _r(rot):
    return [float(rot.roll), float(rot.pitch), float(rot.yaw)]


def _box(actor):
    o, e = actor.get_actor_bounds(False)
    return {"min": [o.x - e.x, o.y - e.y, o.z - e.z], "max": [o.x + e.x, o.y + e.y, o.z + e.z]}


def _world_tf(actor):
    return {"location": _v(actor.get_actor_location()), "rotation": _r(actor.get_actor_rotation()),
            "scale": _v(actor.get_actor_scale3d())}


def _relative_tf(actor):
    rc = actor.root_component
    return {"location": _v(rc.get_editor_property("relative_location")),
            "rotation": _r(rc.get_editor_property("relative_rotation")),
            "scale": _v(rc.get_editor_property("relative_scale3d"))}


def _parent(actor):
    p = actor.get_attach_parent_actor()
    return str(p.get_actor_label()) if p else None


def _hidden(actor):
    return bool(actor.get_editor_property("hidden"))


def _path(obj):
    return str(obj.get_path_name()).split(".", 1)[0] if obj is not None else None


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def _index(world):
    out = {}
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):   # sees transient actors too
        out.setdefault(str(a.get_actor_label()), []).append(a)
    return out


def _one(index, label):
    rows = index.get(label, [])
    if len(rows) != 1:
        raise PlanError("COUNT|%s|%d" % (label, len(rows)))
    return rows[0]


def _crop_rect():
    if not os.path.isfile(CROP_MANIFEST):
        return None
    with open(CROP_MANIFEST, encoding="utf-8") as h:
        return [float(v) for v in json.load(h)["leaf"]["uv_rect_left_top_right_bottom"]]


def live_state(world):
    index = _index(world)
    root = _one(index, ROOT)
    root_tf = _world_tf(root)
    bd = _one(index, BACKDROP)
    comps = list(bd.get_components_by_class(unreal.StaticMeshComponent))
    if len(comps) != 1:
        raise PlanError("BACKDROP_COMPONENTS|%d" % len(comps))
    bd_path = bd.get_path_name()
    children = []
    for label, actors in index.items():
        for a in actors:
            p = a.get_attach_parent_actor()
            if p is not None and p.get_path_name() == bd_path:
                children.append(label)
    fw = _one(index, FAR_WALL)

    def row(label, a):
        box = _box(a)
        return {"label": label, "hidden": _hidden(a), "aabb_world": box, "aabb_local": box_to_local(root_tf, box),
                "parent_label": _parent(a)}

    state = {"root": {"label": ROOT, "world": root_tf},
             "backdrop": {"label": BACKDROP, "parent_label": _parent(bd), "world": _world_tf(bd),
                          "relative": _relative_tf(bd), "aabb_world": _box(bd), "hidden": _hidden(bd),
                          "mobility": comps[0].get_editor_property("mobility").name, "children": sorted(children),
                          "mesh": _path(comps[0].get_editor_property("static_mesh")),
                          "material": _path(comps[0].get_material(0)), "object_path": bd_path},
             "far_wall": dict(row(FAR_WALL, fw), world=_world_tf(fw)),
             "side_walls": {lbl: row(lbl, _one(index, lbl)) for lbl in SIDE_WALLS},
             "deck": row(DECK, _one(index, DECK)),
             "shore_ground": row(SHORE, _one(index, SHORE)) if index.get(SHORE) else None,
             "roof": row(ROOF, _one(index, ROOF)) if len(index.get(ROOF, [])) == 1 else None,
             "door": {"leaf": row(LEAF, _one(index, LEAF)), "black": row(BLACK, _one(index, BLACK)),
                      "fills": [row(lbl, a) for lbl, acts in index.items() for a in acts
                                if FILL_TAG in [str(t) for t in a.tags]]},
             "temp_actors": sorted(k for k in index if k.startswith("ZZ_") or "TEMP" in k.upper()),
             "crop_manifest_leaf_rect": _crop_rect(), "overhead_near_top": []}
    # Visible actors near the top of the far wall (lattice, roof rig, borders): listed only, for the top-band report.
    band = {"min": [5000.0, -1050.0, 2700.0], "max": [6050.0, 1050.0, 3300.0]}
    skip = {BACKDROP, FAR_WALL, ROOT} | set(SIDE_WALLS)
    for label, actors in index.items():
        if label in skip or not label.startswith("S3 "):
            continue
        for a in actors:
            try:
                box = box_to_local(root_tf, _box(a))
            except Exception:  # noqa: BLE001  bounds of a component-less actor; listing only
                continue
            if all(box["min"][i] < band["max"][i] and box["max"][i] > band["min"][i] for i in range(3)):
                state["overhead_near_top"].append({"label": label, "hidden": _hidden(a), "aabb_local": box})
    return state


def _write(path, value, exclusive=False):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as h:
        json.dump(value, h, indent=1)
        h.flush()
        os.fsync(h.fileno())


def _backup(run):
    backup = BACKUP_ROOT + run
    os.makedirs(backup)
    dst = os.path.join(backup, os.path.basename(UMAP))
    shutil.copy2(UMAP, dst)
    if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(UMAP):
        raise PlanError("BACKUP_MISSING|" + dst)
    return backup


def _save_level(world):
    dirty = _census()
    if dirty != {"content": [], "maps": [WORLD]}:
        raise PlanError("DIRTY_SCOPE|%s" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD):
        raise PlanError("SAVE_FAILED")
    after = _census()
    if after != {"content": [], "maps": []}:
        raise PlanError("POST_SAVE_DIRTY|" + json.dumps(after))
    return after


def run_apply(run, args, world):
    state = live_state(world)
    plan = plan_lower(state, args)
    apply_gates(plan)
    record = {"run": run, "world": WORLD, "applied": False, "saved": False, "args": args, "plan": plan,
              "backdrop_object_path": state["backdrop"]["object_path"]}
    _write(REC, record, exclusive=True)
    unreal.log("S3MURAL_RECORD|run=%s|path=%s" % (run, REC))
    record["backup"] = _backup(run)
    _write(REC, record)
    bd = _one(_index(world), BACKDROP)
    bd.modify()
    bd.set_actor_location(unreal.Vector(*plan["target"]["world_location"]), False, False)   # return value not trusted
    fails = verify_after(live_state(world), plan)
    if fails:
        raise PlanError("READBACK|" + ";".join(fails))
    record["post_save_census"] = _save_level(world)
    record["saved"] = True
    _write(REC, record)
    fails = verify_after(live_state(world), plan)                  # fresh index, after the save
    if fails:
        raise PlanError("POST_SAVE_READBACK|" + ";".join(fails))
    record["applied"] = True
    _write(REC, record)
    return {"drop_cm": plan["drop_cm"], "aabb_local_z": [plan["target"]["aabb_local"]["min"][2],
                                                          plan["target"]["aabb_local"]["max"][2]],
            "top_gap_cm": plan["top"]["gap_cm"], "backup": record["backup"]}


def run_revert(run, world):
    with open(REC, encoding="utf-8") as h:
        record = json.load(h)
    if record.get("world") != WORLD or not record.get("saved"):
        raise PlanError("RECORD_INVALID")
    state = live_state(world)
    if state["backdrop"]["object_path"] != record["backdrop_object_path"]:
        raise PlanError("OBJECT_PATH_CHANGED")
    if state["temp_actors"]:
        raise PlanError("TEMP_ACTORS_PRESENT|%s" % state["temp_actors"][:5])
    revert_gate(state, record)
    backup = _backup(run)
    rel = record["plan"]["before"]["relative"]["location"]
    bd = _one(_index(world), BACKDROP)
    bd.modify()
    bd.set_actor_relative_location(unreal.Vector(*rel), False, False)
    fails = verify_revert(live_state(world), record)
    if fails:
        raise PlanError("REVERT_READBACK|" + ";".join(fails))
    _save_level(world)
    fails = verify_revert(live_state(world), record)
    if fails:
        raise PlanError("REVERT_POST_SAVE_READBACK|" + ";".join(fails))
    os.replace(REC, REC + ".reverted-" + run)
    return {"backup": backup, "relative_location": rel}


def main():
    run = "S3MURAL-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    mode = "?"
    try:
        with open(ARGS, encoding="utf-8") as h:
            args = json.load(h)
        run = args.get("run") or run
        mode = check_mode(args, os.path.exists(REC))
        unreal.log("S3MURAL_START|run=%s|mode=%s" % (run, mode))
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if ed.get_game_world() is not None:
            raise PlanError("PIE_ACTIVE")
        world = ed.get_editor_world()
        if world is None or world.get_outermost().get_name() != WORLD:
            raise PlanError("WRONG_WORLD")
        census = _census()
        clean = gate_census(census, mode)
        if mode == "DRY":
            state = live_state(world)
            plan = plan_lower(state, args)
            try:
                apply_gates(plan)
                would = "would_apply"
            except PlanError as exc:
                would = "APPLY_WOULD_REFUSE|" + str(exc)
            _write(DRY_OUT, {"run": run, "census": census, "apply_would_refuse_dirty": not clean, "apply": would,
                             "state": state, "plan": plan})
            unreal.log("S3MURAL_PLAN|run=%s|%s" % (run, json.dumps({
                "drop_cm": plan["drop_cm"], "before_local_z": [plan["before"]["aabb_local"]["min"][2],
                                                               plan["before"]["aabb_local"]["max"][2]],
                "after_local_z": [plan["target"]["aabb_local"]["min"][2], plan["target"]["aabb_local"]["max"][2]],
                "target_world": plan["target"]["world_location"], "top": {k: plan["top"][k] for k in (
                    "gap_cm", "bare_band_local_z", "cover_by", "max_flush_drop_cm")},
                "bottom": plan["bottom"]["cropped_band_local_z"], "mimic": plan["door_mimic"]["action"],
                "mimic_baked_matches_now": plan["door_mimic"]["baked_matches_now"], "apply": would,
                "census": census})))
            unreal.log("S3MURAL_DRY_OK|run=%s|mutated=0|out=%s" % (run, DRY_OUT))
            return
        if mode == "APPLY":
            try:
                result = run_apply(run, args, world)
            except Exception:
                if os.path.exists(REC):
                    with open(REC, encoding="utf-8") as h:
                        saved = json.load(h).get("saved")
                    if not saved:
                        os.replace(REC, REC + ".failed-" + run)
                raise
        else:
            result = run_revert(run, world)
        unreal.log("S3MURAL_%s_OK|run=%s|level_saved=1|dirty_after=0+0|%s" % (mode, run, json.dumps(result)))
    except Exception as exc:  # noqa: BLE001
        census = None
        try:
            census = _census()
        except Exception:  # noqa: BLE001
            pass
        unreal.log_error("S3MURAL_FAILED|run=%s|mode=%s|%s|census=%s|%s" % (
            run, mode, str(exc).replace("\n", " "), json.dumps(census),
            "NOTHING SAVED unless an _OK marker printed; if the map is dirty: Don't-Save restart (never reload)"
            if mode in ("APPLY", "REVERT") else "DRY mutated nothing"))
