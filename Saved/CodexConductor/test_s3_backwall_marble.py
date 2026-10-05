"""Offline harness for s3_backwall_marble.py (no Unreal).  Positive cases use numbers from saved records
(s3_flats_place_record.json, s3_walls_marble_record.json, hangar_s3_plan.json, s3_close_back_door_record.json);
every gate has a negative control that MUST raise.  Exit code 0 only if all pass."""
import copy
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bwm", os.path.join(HERE, "s3_backwall_marble.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.unreal is None

X0 = 11421.97275            # S3 root x (hangar_exit_doorways_probe.json root world_location)
FRONT = 17421.97275         # far-wall front face (s3_close_back_door_record.json left.x[0])
MESH_LOCAL = {"min": [-0.000163, -1000.0, 0.0], "max": [0.000163, 1000.0, 3000.0]}  # 20 x 30 m plane, pivot at bottom
PARENT_NOW = {"location": [17446.97275, 160000.0, -120.0 + 570.0 + 2430.0 / 2.0], "rotation": [0, 0, 0],
              "scale": [0.5, 21.0, 24.3]}   # hangar_exit_doors.py:473-475 "above" piece, root z -120


def base_state():
    squash = m.predicted_child_world(PARENT_NOW, m.BACKDROP_DESIGN_RELATIVE)
    bd_aabb = m.aabb_from_local(MESH_LOCAL, squash["location"], squash["scale"])
    st = {
        "backdrop": {"label": m.BACKDROP, "parent_label": m.FAR_WALL, "hidden": False,
                     "world": {"location": squash["location"], "rotation": [0.0, 0.0, 0.0], "scale": squash["scale"]},
                     "aabb": bd_aabb, "mesh_local_box": MESH_LOCAL},
        "far_wall": {"label": m.FAR_WALL, "world": PARENT_NOW,
                     "aabb": {"min": [FRONT, 158950.0, 450.0], "max": [FRONT + 50.0, 161050.0, 2880.0]}},
        "side_walls": {
            "L": {"aabb": {"min": [X0, 158950.0, -120.0], "max": [X0 + 6000.0, 159000.0, 2880.0]}},
            "R": {"aabb": {"min": [X0, 161000.0, -120.0], "max": [X0 + 6000.0, 161050.0, 2880.0]}}},
        "liners": {},
        "near_far_wall": [],
        "labels_present": [m.BACKDROP, m.FAR_WALL, m.LINERS["L"], m.LINERS["R"]],
    }
    for k, y in (("L", 159000.5), ("R", 160999.5)):   # s3_walls_marble_record.json spawned rows
        st["liners"][k] = {"parent_label": m.SIDE_WALLS[k],
                           "world": {"location": [X0 + 3000.0, y, 297.5], "rotation": [0.0, 0.0, 0.0],
                                     "scale": [60.0, 0.01, 6.05]},
                           "aabb": m.aabb_of_scaled_cube([X0 + 3000.0, y, 297.5], [60.0, 0.01, 6.05]),
                           "mesh": "/Engine/BasicShapes/Cube",
                           "material": "/Game/InfinityStage/Dev/Materials/MI_S3_Marble_Heavy_Daylight"}
    return st


ARGS = {"mode": "DRY", "parts": ["backdrop", "marble"], "marble_mirror_alternate": True, "max_tile_squash": 0.15}
DECALS = [{"label": "hp%d" % i, "aabb": {"min": [X0 + 500 + 100 * i, 159001 - 8, 45 + 10 * i],
                                         "max": [X0 + 530 + 100 * i, 159001 + 8, 75 + 10 * i + 20]}} for i in range(20)]
passed, failed = [], []


def check(name, cond):
    (passed if cond else failed).append(name)


def must_raise(name, fn, token):
    try:
        fn()
    except m.PlanError as exc:
        check(name, token in str(exc))
        if token not in str(exc):
            print("  wrong refusal for", name, "->", exc)
        return
    failed.append(name + " (did not raise)")


# --- positive: the squashed state the DRY is predicted to find
st = base_state()
plan = m.build_plan(st, ARGS, DECALS)
b = plan["backdrop"]
check("squash_predicted_z", abs(st["backdrop"]["aabb"]["min"][2] - 543.15) < 0.01 and
      abs(st["backdrop"]["aabb"]["max"][2] - 2973.15) < 0.01)
check("needs_restore", b["needs_restore"] is True)
check("mechanism_squash", b["mechanism"] == "parent_rescale_squash")
check("target_y", abs(b["target_aabb"]["min"][1] - 159000) < 0.01 and abs(b["target_aabb"]["max"][1] - 161000) < 0.01)
check("target_z", abs(b["target_aabb"]["min"][2] + 5) < 0.01 and abs(b["target_aabb"]["max"][2] - 2995) < 0.01)
check("uncovered_band", b["uncovered_band_z_now"] is not None and abs(b["uncovered_band_z_now"][1] - 543.15) < 0.01)
tiles = plan["tiles"]
check("tile_count", len(tiles) == 8)
check("tile_h_570", all(abs(t["tile_h"] - 570.0) < 1e-6 for t in tiles))
check("tiles_span", abs(min(t["aabb"]["min"][2] for t in tiles) - 600) < 1e-6 and
      abs(max(t["aabb"]["max"][2] for t in tiles) - 2880) < 1e-6)
check("mirror_alternates", [t["mirrored"] for t in tiles if t["side"] == "L"] == [True, False, True, False])
check("tile_coplanar_L", all(abs(t["aabb"]["max"][1] - 159001.0) < 1e-6 for t in tiles if t["side"] == "L"))
check("labels", tiles[0]["label"] == "S3 Marble Inner Wall Left Upper 1")
check("no_mirror_option", not any(t["mirrored"] for t in m.plan_tiles(st, dict(ARGS, marble_mirror_alternate=False))))

# --- at design: nothing to restore
st2 = base_state()
st2["backdrop"]["world"] = copy.deepcopy(m.BACKDROP_DESIGN)
st2["backdrop"]["aabb"] = m.aabb_from_local(MESH_LOCAL, m.BACKDROP_DESIGN["location"], [1, 1, 1])
b2 = m.plan_backdrop(st2)
check("at_design_noop", b2["needs_restore"] is False and b2["mechanism"] == "at_design" and b2["uncovered_band_z_now"] is None)

# --- poke-through classification
st3 = base_state()
st3["near_far_wall"] = [
    {"label": "S3 Hangar Exit Door Leaf", "hidden": False,
     "aabb": {"min": [FRONT - 3.05, 159850.5, 0.5], "max": [FRONT - 3.04, 160149.5, 449.5]}},
    {"label": "S3 Hangar Exit Black", "hidden": True,
     "aabb": {"min": [FRONT + 51, 159850, 0], "max": [FRONT + 53, 160150, 450]}},
    {"label": "S3 Uplight 2", "hidden": False, "aabb": {"min": [FRONT - 40, 159990, 0], "max": [FRONT - 20, 160010, 20]}},
    {"label": "S3 Hangar Far Wall Left of Exit", "hidden": False,
     "aabb": {"min": [FRONT, 158950, -120], "max": [FRONT + 50, 159850, 450]}},
]
b3 = m.plan_backdrop(st3)
check("leaf_poke_hidden", b3["hide_door_pokes"] == ["S3 Hangar Exit Door Leaf"])
check("foreign_listed", b3["foreign_in_front_listed_only"] == ["S3 Uplight 2"])
st3["near_far_wall"][0]["hidden"] = True
check("hidden_leaf_not_listed", m.plan_backdrop(st3)["hide_door_pokes"] == [])

# --- negative controls (each gate must be able to fail)
def mutated(fn):
    s = base_state()
    fn(s)
    return s

must_raise("rotated_backdrop", lambda: m.plan_backdrop(mutated(lambda s: s["backdrop"]["world"].__setitem__("rotation", [0, 0, 90]))), "BACKDROP_ROTATED")
must_raise("parent_changed", lambda: m.plan_backdrop(mutated(lambda s: s["backdrop"].__setitem__("parent_label", "S3 Hangar Root"))), "BACKDROP_PARENT")
must_raise("wall_taller_than_backdrop", lambda: m.plan_backdrop(mutated(lambda s: s["side_walls"]["L"]["aabb"]["max"].__setitem__(2, 3100.0))), "TARGET_NOT_FLOOR_TO_TOP")
must_raise("wall_moved_back", lambda: m.plan_backdrop(mutated(lambda s: s["far_wall"]["aabb"]["min"].__setitem__(0, FRONT + 20))), "TARGET_NOT_JUST_IN_FRONT")
must_raise("wall_moved_forward", lambda: m.plan_backdrop(mutated(lambda s: s["far_wall"]["aabb"]["min"].__setitem__(0, FRONT - 5))), "TARGET_NOT_JUST_IN_FRONT")
must_raise("hangar_wider", lambda: m.plan_backdrop(mutated(lambda s: s["side_walls"]["R"]["aabb"]["min"].__setitem__(1, 161100.0))), "TARGET_NOT_SIDE_TO_SIDE")
must_raise("label_clash", lambda: m.plan_tiles(mutated(lambda s: s["labels_present"].append("S3 Marble Inner Wall Right Upper 2")), ARGS), "TILE_LABELS_EXIST")
must_raise("decal_on_tile", lambda: m.plan_tiles(base_state(), ARGS, DECALS + [{"label": "high", "aabb": {"min": [X0 + 900, 158995, 640], "max": [X0 + 930, 159010, 680]}}]), "TILE_HITS_DECAL")
must_raise("squash_limit", lambda: m.plan_tiles(base_state(), dict(ARGS, max_tile_squash=0.01)), "TILE_SQUASH")
must_raise("top_above_wall", lambda: m.plan_tiles(base_state(), dict(ARGS, marble_top_z=3000.0)), "TOP_ABOVE_WALL")
must_raise("liner_lowered", lambda: m.plan_tiles(mutated(lambda s: s["liners"]["L"]["aabb"]["max"].__setitem__(2, 400.0)), ARGS), "TILES_WOULD_START_BELOW_HANDPRINT_CEILING")
must_raise("liner_reparented", lambda: m.plan_tiles(mutated(lambda s: s["liners"]["R"].__setitem__("parent_label", "S3 Hangar Root")), ARGS), "LINER_PARENT")
must_raise("liner_rotated", lambda: m.plan_tiles(mutated(lambda s: s["liners"]["L"]["world"].__setitem__("rotation", [0, 0, 1])), ARGS), "LINER_ROTATED")
must_raise("bad_parts", lambda: m.build_plan(base_state(), dict(ARGS, parts=["wall"])), "PARTS")
must_raise("confirm_missing", lambda: m.check_mode({"mode": "APPLY"}, False), "CONFIRM_MISSING")
must_raise("apply_twice", lambda: m.check_mode({"mode": "APPLY", "confirm": "APPLY S3BWM"}, True), "ALREADY_APPLIED")
must_raise("revert_no_record", lambda: m.check_mode({"mode": "REVERT", "confirm": "REVERT S3BWM"}, False), "NO_RECORD")
must_raise("bad_mode", lambda: m.check_mode({"mode": "SAVEALL"}, False), "MODE")
check("dry_default", m.check_mode({}, True) == "DRY")

# --- mirrored handedness helper is sign-product based (memory: mirrored readback flips onto X)
class _S:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z
class _A:
    def __init__(self, s):
        self.s = s
    def get_actor_scale3d(self):
        return self.s
check("mirror_z", m._mirrored(_A(_S(60, 0.01, -5.7))) is True)
check("mirror_moved_to_x", m._mirrored(_A(_S(-60, 0.01, 5.7))) is True)
check("not_mirrored", m._mirrored(_A(_S(60, 0.01, 5.7))) is False)

print("S3BWM_HARNESS|passed=%d|failed=%d" % (len(passed), len(failed)))
for f in failed:
    print("  FAIL", f)
sys.exit(1 if failed else 0)
