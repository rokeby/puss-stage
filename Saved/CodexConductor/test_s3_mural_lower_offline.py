"""Offline harness for s3_mural_lower.py (no Unreal).  Positive cases use measured numbers from saved records
(s3_shore_live_reads.json run S3SHORE-20261007-181646; s3_backwall_marble_dry.json run S3BWM-20261005-191401 +
s3_backwall_marble_record.json target; s3_exit_door_crop_manifest.json).  Every gate has a negative control that
MUST fail.  UE's SetWorldLocation-on-an-attached-actor is SIMULATED as relative = ParentInverse(world) (inferred
engine behaviour; the live read-back re-checks it).  Exit code 0 only if every case passes.
Writes test_s3_mural_lower_offline_report.json."""
import ast
import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = load("s3ml", "s3_mural_lower.py")
assert m.unreal is None
doors = load("hed", "hangar_exit_doors.py")
assert doors.unreal is None

ROOT_TF = {"location": [11421.97275, 160000.0, -120.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
PARENT_TF = {"location": [17446.97275, 160000.0, 1665.0], "rotation": [0.0, 0.0, 0.0], "scale": [0.5, 21.0, 24.3]}
BD_WORLD = {"location": [17418.973, 160000.0, -5.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
BD_AABB = {"min": [17418.97283707932, 159000.0, -5.0], "max": [17418.973162920684, 161000.0, 2995.0]}
with open(m.CROP_MANIFEST, encoding="utf-8") as h:
    CROP_RECT = [float(v) for v in json.load(h)["leaf"]["uv_rect_left_top_right_bottom"]]

results = []


def case(name, fn):
    try:
        fn()
        results.append((name, "PASS", ""))
    except Exception as exc:  # noqa: BLE001
        results.append((name, "FAIL", "%s: %s" % (type(exc).__name__, exc)))


def expect_raise(fn, token):
    try:
        fn()
    except m.PlanError as exc:
        if token not in str(exc):
            raise AssertionError("raised, but without %r: %s" % (token, exc))
        return
    raise AssertionError("did not raise %r" % token)


def row(label, world_box, hidden=False, root=ROOT_TF, parent=None):
    return {"label": label, "hidden": hidden, "aabb_world": world_box, "aabb_local": m.box_to_local(root, world_box),
            "parent_label": parent}


def local_box(lo, hi, root=ROOT_TF):
    return {"min": m.tf_point(root, lo), "max": m.tf_point(root, hi)}


def base_state(parent_tf=PARENT_TF, root_tf=ROOT_TF):
    rel = m.tf_inv_point(parent_tf, BD_WORLD["location"])
    return {
        "root": {"label": m.ROOT, "world": copy.deepcopy(root_tf)},
        "backdrop": {"label": m.BACKDROP, "parent_label": m.FAR_WALL, "world": copy.deepcopy(BD_WORLD),
                     "relative": {"location": rel, "rotation": [0.0, 0.0, 0.0],
                                  "scale": [1.0 / s for s in parent_tf["scale"]]},
                     "aabb_world": copy.deepcopy(BD_AABB), "hidden": False, "mobility": "MOVABLE", "children": [],
                     "object_path": "PersistentLevel.StaticMeshActor_334"},
        "far_wall": dict(row(m.FAR_WALL, {"min": [17421.97275, 158950.0, 450.0], "max": [17471.97275, 161050.0, 2880.0]},
                             parent=m.ROOT), world=copy.deepcopy(parent_tf)),
        "side_walls": {m.SIDE_WALLS[0]: row(m.SIDE_WALLS[0], {"min": [11421.97275, 158950.0, -120.0],
                                                             "max": [17421.97275, 159000.0, 2880.0]}),
                       m.SIDE_WALLS[1]: row(m.SIDE_WALLS[1], {"min": [11421.97275, 161000.0, -120.0],
                                                             "max": [17421.97275, 161050.0, 2880.0]})},
        "deck": row(m.DECK, local_box([0.0, -1000.0, 95.0], [6000.0, 1000.0, 115.0])),
        "shore_ground": None,
        "roof": row(m.ROOF, {"min": [11421.97275, 158950.0, 2880.0], "max": [17471.97275, 161050.0, 2930.0]}),
        "door": {"leaf": row(m.LEAF, {"min": [17418.9, 159850.5, 0.5], "max": [17418.9, 160149.5, 449.5]}, hidden=True),
                 "black": row(m.BLACK, {"min": [17473.0, 159850.0, 0.0], "max": [17475.0, 160150.0, 450.0]}, hidden=True),
                 "fills": [row("S3 Hangar Far Wall Exit Fill (door closed)",
                               {"min": [17421.97275, 159850.0, 0.0], "max": [17471.97275, 160150.0, 450.0]})]},
        "temp_actors": [], "crop_manifest_leaf_rect": list(CROP_RECT), "overhead_near_top": []}


ARGS = {"mode": "DRY", "drop_cm": 150.0, "top_gap_policy": None, "expect_bottom_local_z": 115.0}


def simulate_set_world(state, world_loc):
    """UE SetActorLocation on an attached actor (inferred): world moves, relative = ParentInverse(world)."""
    s = copy.deepcopy(state)
    bd = s["backdrop"]
    d = [world_loc[i] - bd["world"]["location"][i] for i in range(3)]
    bd["world"]["location"] = list(world_loc)
    bd["relative"]["location"] = m.tf_inv_point(s["far_wall"]["world"], world_loc)
    bd["aabb_world"] = {k: [bd["aabb_world"][k][i] + d[i] for i in range(3)] for k in ("min", "max")}
    return s


def simulate_set_relative(state, rel):
    """UE SetActorRelativeLocation: world = Parent(relative)."""
    s = copy.deepcopy(state)
    bd = s["backdrop"]
    w = m.tf_point(s["far_wall"]["world"], rel)
    d = [w[i] - bd["world"]["location"][i] for i in range(3)]
    bd["relative"]["location"] = list(rel)
    bd["world"]["location"] = w
    bd["aabb_world"] = {k: [bd["aabb_world"][k][i] + d[i] for i in range(3)] for k in ("min", "max")}
    return s


def close(a, b, tol=1e-6):
    assert all(abs(x - y) <= tol for x, y in zip(a, b)), "%s != %s" % (a, b)


# --------------------------------------------------------------------------------------------------------- cases
def t_base_plan():
    p = m.plan_lower(base_state(), ARGS)
    close(p["target"]["world_location"], [17418.973, 160000.0, -155.0], 1e-6)
    close([p["target"]["aabb_local"]["min"][2], p["target"]["aabb_local"]["max"][2]], [-35.0, 2965.0], 1e-6)
    close([p["before"]["aabb_local"]["min"][2], p["before"]["aabb_local"]["max"][2]], [115.0, 3115.0], 1e-6)
    close(p["target"]["relative_location"], [(17418.973 - 17446.97275) / 0.5, 0.0, (-155.0 - 1665.0) / 24.3], 1e-6)
    assert abs(p["top"]["gap_cm"] - 35.0) < 1e-6 and p["top"]["bare_band_local_z"] == [2965.0, 3000.0]
    assert abs(p["top"]["max_flush_drop_cm"] - 115.0) < 1e-6 and not p["top"]["apply_allowed"]
    close(p["bottom"]["cropped_band_local_z"], [-35.0, 115.0], 1e-6)
    assert abs(p["bottom"]["below_hangar_base_cm"] - 35.0) < 1e-6
    assert p["door_mimic"]["baked_matches_now"] is True, p["door_mimic"]
    assert p["door_mimic"]["baked_matches_after"] is False
    assert abs(p["door_mimic"]["dv_shift"] + 0.05) < 1e-9, p["door_mimic"]["dv_shift"]
    assert p["door_mimic"]["action"].startswith("none")


def t_top_gap_gate():
    expect_raise(lambda: m.apply_gates(m.plan_lower(base_state(), ARGS)), "TOP_GAP_DECISION_REQUIRED")
    m.apply_gates(m.plan_lower(base_state(), dict(ARGS, top_gap_policy="accept")))
    p = m.plan_lower(base_state(), dict(ARGS, drop_cm=115.0))
    assert p["top"]["gap_cm"] == 0.0
    m.apply_gates(p)
    expect_raise(lambda: m.plan_lower(base_state(), dict(ARGS, top_gap_policy="yes")), "TOP_GAP_POLICY")


def t_roof_hidden_uses_wall_top():
    s = base_state()
    s["roof"]["hidden"] = True
    p = m.plan_lower(s, ARGS)
    assert "side-wall top" in p["top"]["cover_by"] and abs(p["top"]["gap_cm"] - 35.0) < 1e-6


def t_uv_matches_doors_tool():
    """Our mapping == hangar_exit_doors._s3_leaf_uv_rect (unrotated) before and after; before == baked manifest."""
    root_row = {"world_location_cm": ROOT_TF["location"], "world_rotation_rpy": [0, 0, 0], "world_scale": [1, 1, 1]}
    leaf_root = [6025.0, 0.0, 120.0 + 225.0]
    for z in (-5.0, -155.0):
        bd_row = {"world_location_cm": [17418.973, 160000.0, z], "world_rotation_rpy": [0, 0, 0],
                  "world_scale": [1, 1, 1]}
        theirs = doors._s3_leaf_uv_rect(root_row, bd_row, leaf_root, [299.0, 449.0])
        box = {"min": [6025.0, -149.5, 120.5], "max": [6025.0, 149.5, 569.5]}
        ours = m.leaf_uv_rect(ROOT_TF, {"location": [17418.973, 160000.0, z], "rotation": [0, 0, 0],
                                        "scale": [1, 1, 1]}, box)
        close(ours, theirs, 1e-9)
        if z == -5.0:
            close(ours, CROP_RECT, 1e-6)
        else:
            assert abs(ours[1] - CROP_RECT[1] + 0.05) < 1e-9


def t_rotated_scaled_parent():
    parent = {"location": [17446.97275, 160000.0, 1665.0], "rotation": [10.0, 20.0, 30.0], "scale": [0.5, 21.0, 24.3]}
    s = base_state(parent_tf=parent)
    close(m.tf_point(parent, s["backdrop"]["relative"]["location"]), BD_WORLD["location"], 1e-6)   # setup sanity
    p = m.plan_lower(s, ARGS)
    close(m.tf_point(parent, p["target"]["relative_location"]), p["target"]["world_location"], 1e-6)
    close(p["target"]["world_location"], [17418.973, 160000.0, -155.0], 1e-6)
    after = simulate_set_world(s, p["target"]["world_location"])
    assert m.verify_after(after, p) == [], m.verify_after(after, p)
    # NEGATIVE: naive relative drop (rel.z -= drop / parent_scale_z) is wrong under a rotated parent.
    naive = list(s["backdrop"]["relative"]["location"])
    naive[2] -= 150.0 / parent["scale"][2]
    bad = simulate_set_relative(s, naive)
    f = m.verify_after(bad, p)
    assert any(x.startswith("WORLD_LOCATION") for x in f) and "WORLD_XY_MOVED" in f, f
    # The same naive rule is CORRECT under the real (unrotated) parent: proves the control discriminates rotation.
    s0 = base_state()
    p0 = m.plan_lower(s0, ARGS)
    n0 = list(s0["backdrop"]["relative"]["location"])
    n0[2] -= 150.0 / PARENT_TF["scale"][2]
    assert m.verify_after(simulate_set_relative(s0, n0), p0) == []


def t_parent_or_root_moved_negative():
    s = base_state()
    p = m.plan_lower(s, ARGS)
    after = simulate_set_world(s, p["target"]["world_location"])
    sq = copy.deepcopy(after)
    sq["far_wall"]["world"]["scale"] = [0.5, 21.0, 20.0]
    assert "PARENT_MOVED" in m.verify_after(sq, p)
    rm = copy.deepcopy(after)
    rm["root"]["world"]["location"][2] += 1.0
    assert "ROOT_MOVED" in m.verify_after(rm, p)
    sc = copy.deepcopy(after)
    sc["backdrop"]["world"]["scale"] = [1.0, 1.0, 0.81]
    assert any(x.startswith("WORLD_SCALE_CHANGED") for x in m.verify_after(sc, p))
    un = copy.deepcopy(after)
    un["door"]["leaf"]["hidden"] = False
    assert "DOOR_UNHIDDEN" in m.verify_after(un, p)


def t_landed_root_and_guard():
    rest = {"location": [11421.97275, 160000.0, -120.0], "rotation": [0.0, -90.0, 0.0], "scale": [1.0, 1.0, 1.0]}
    expect_raise(lambda: m.plan_lower(base_state(root_tf=rest), ARGS), "ROOT_NOT_LANDED")
    sunk = {"location": [11421.97275, 160000.0, -3620.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
    expect_raise(lambda: m.plan_lower(base_state(root_tf=sunk), ARGS), "ROOT_NOT_LANDED")
    p = m.plan_lower(base_state(), ARGS)
    assert m.box_inside(p["target"]["aabb_local"], m.GUARD_LOCAL)
    # NEGATIVE: the same world box read through the REST root, or a target composed through it, is outside the guard.
    assert not m.box_inside(m.box_to_local(rest, p["target"]["aabb_world"]), m.GUARD_LOCAL)
    wrong_world = m.tf_point(rest, [5997.0, 0.0, -35.0])
    d = [wrong_world[i] - BD_WORLD["location"][i] for i in range(3)]
    wrong_box = {k: [BD_AABB[k][i] + d[i] for i in range(3)] for k in ("min", "max")}
    assert not m.box_inside(m.box_to_local(ROOT_TF, wrong_box), m.GUARD_LOCAL)
    # A drop deep enough to leave the guard refuses at plan time (MAX_DROP keeps it out of reach; patch the guard).
    old = m.GUARD_LOCAL
    try:
        m.GUARD_LOCAL = dict(old, min=[old["min"][0], old["min"][1], 0.0])
        expect_raise(lambda: m.plan_lower(base_state(), ARGS), "GUARD_LOCAL_BOX")
    finally:
        m.GUARD_LOCAL = old


def t_revert_exact():
    for parent in (PARENT_TF, {"location": PARENT_TF["location"], "rotation": [10.0, 20.0, 30.0],
                               "scale": PARENT_TF["scale"]}):
        s = base_state(parent_tf=parent)
        p = m.plan_lower(s, ARGS)
        record = json.loads(json.dumps({"plan": p}))           # through JSON, as on disk
        after = simulate_set_world(s, p["target"]["world_location"])
        m.revert_gate(after, record)
        back = simulate_set_relative(after, record["plan"]["before"]["relative"]["location"])
        assert m.verify_revert(back, record) == [], m.verify_revert(back, record)
        close(back["backdrop"]["world"]["location"], BD_WORLD["location"], 1e-6)
        # NEGATIVE: a restore 0.1 relative units off (= 2.43 cm under scale z 24.3) fails.
        off = list(record["plan"]["before"]["relative"]["location"])
        off[2] += 0.1
        assert m.verify_revert(simulate_set_relative(after, off), record) != []
        # NEGATIVE: someone moved it after APPLY -> revert refuses before writing.
        drift = simulate_set_world(after, [p["target"]["world_location"][0], p["target"]["world_location"][1],
                                           p["target"]["world_location"][2] + 1.0])
        expect_raise(lambda: m.revert_gate(drift, record), "DRIFT_SINCE_APPLY")


def t_dirty_census():
    dirty = {"content": ["/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"], "maps": []}
    expect_raise(lambda: m.gate_census(dirty, "APPLY"), "DIRTY_BEFORE")
    expect_raise(lambda: m.gate_census({"content": [], "maps": [m.WORLD]}, "REVERT"), "DIRTY_BEFORE")
    assert m.gate_census(dirty, "DRY") is False
    assert m.gate_census({"content": [], "maps": []}, "APPLY") is True


def t_check_mode():
    assert m.check_mode({"mode": "DRY"}, True) == "DRY"
    expect_raise(lambda: m.check_mode({"mode": "APPLY"}, False), "CONFIRM_MISSING")
    expect_raise(lambda: m.check_mode({"mode": "APPLY", "confirm": "APPLY S3MURAL"}, True), "ALREADY_APPLIED")
    assert m.check_mode({"mode": "APPLY", "confirm": "APPLY S3MURAL"}, False) == "APPLY"
    expect_raise(lambda: m.check_mode({"mode": "REVERT", "confirm": "REVERT S3MURAL"}, False), "NO_RECORD")
    expect_raise(lambda: m.check_mode({"mode": "SAVE"}, False), "MODE")


def t_door_visible_refuses():
    s = base_state()
    s["door"]["leaf"]["hidden"] = False
    p = m.plan_lower(s, dict(ARGS, top_gap_policy="accept"))
    assert p["door_mimic"]["action"] == "REFUSE"
    expect_raise(lambda: m.apply_gates(p), "DOOR_MIMIC_VISIBLE_RECROP_REQUIRED")


def t_bottom_crop():
    s = base_state()
    s["deck"]["hidden"] = True
    expect_raise(lambda: m.plan_lower(s, ARGS), "BOTTOM_UNCROPPED")
    s["shore_ground"] = row(m.SHORE, local_box([0.0, -1012.0, 95.0], [6012.0, 1008.0, 243.19]))  # manifest bounds
    p = m.plan_lower(s, ARGS)
    assert p["bottom"]["floor_covers"][0]["label"] == m.SHORE
    s2 = base_state()
    s2["deck"] = row(m.DECK, local_box([0.0, -1000.0, 95.0], [5900.0, 1000.0, 115.0]))   # stops short of the plane
    expect_raise(lambda: m.plan_lower(s2, ARGS), "BOTTOM_UNCROPPED")


def t_state_gates():
    s = base_state()
    low = simulate_set_world(s, [17418.973, 160000.0, -155.0])
    expect_raise(lambda: m.plan_lower(low, ARGS), "BACKDROP_NOT_AT_EXPECTED")
    for key, val, token in (("children", ["S3 Something"], "BACKDROP_HAS_CHILDREN"),
                            ("parent_label", "S3 Hangar Root", "BACKDROP_PARENT"),
                            ("mobility", "STATIC", "BACKDROP_MOBILITY")):
        t = base_state()
        t["backdrop"][key] = val
        expect_raise(lambda: m.plan_lower(t, ARGS), token)
    sq = base_state()
    sq["backdrop"]["world"]["scale"] = [1.0, 1.0, 0.81]
    expect_raise(lambda: m.plan_lower(sq, ARGS), "BACKDROP_SCALE")
    rot = base_state()
    rot["backdrop"]["world"]["rotation"] = [0.0, 0.0, 1.0]
    expect_raise(lambda: m.plan_lower(rot, ARGS), "BACKDROP_ROTATED")
    tmp = base_state()
    tmp["temp_actors"] = ["ZZ_S3MG"]
    expect_raise(lambda: m.plan_lower(tmp, ARGS), "TEMP_ACTORS_PRESENT")
    for d in (0.0, -10.0, 200.0):
        expect_raise(lambda: m.plan_lower(base_state(), dict(ARGS, drop_cm=d)), "DROP_RANGE")


def t_source_rules():
    src = open(os.path.join(HERE, "s3_mural_lower.py"), encoding="utf-8").read()
    for banned in ("reload_packages", "save_dirty_packages", "save_packages(", "save_all", "get_all_level_actors",
                   "set_actor_scale3d", "set_actor_relative_scale3d", "get_bound_objects"):
        assert banned not in src, banned
    tree = ast.parse(src)
    for node in tree.body:   # nothing runs at import; no UE object at module level
        assert not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)), ast.dump(node)[:80]
        if isinstance(node, ast.If):
            assert "main" not in ast.dump(node), "conditional main() at module level"
        if isinstance(node, ast.Assign):
            assert "unreal." not in ast.unparse(node.value), ast.unparse(node)
    runner = open(os.path.join(HERE, "s3_mural_lower_run.py"), encoding="utf-8").read()
    assert "purge_saved_module_cache.py" in runner and '["main"]()' in runner
    assert src.index("S3MURAL_RECORD|") < src.index('record["backup"] = _backup(run)') < src.index("bd.set_actor_location(")
    assert src.index("bd.set_actor_location(") < src.index("fails = verify_after(live_state(world), plan)") < \
        src.index('record["post_save_census"] = _save_level(world)')


for name, fn in sorted((k, v) for k, v in dict(globals()).items() if k.startswith("t_") and callable(v)):
    case(name, fn)

passed = sum(1 for r in results if r[1] == "PASS")
report = {"passed": passed, "failed": len(results) - passed, "cases": [list(r) for r in results]}
with open(os.path.join(HERE, "test_s3_mural_lower_offline_report.json"), "w", encoding="utf-8") as h:
    json.dump(report, h, indent=1)
for r in results:
    print("%-34s %s %s" % r)
print("S3MURAL_OFFLINE|passed=%d|failed=%d" % (passed, len(results) - passed))
sys.exit(0 if passed == len(results) else 1)
