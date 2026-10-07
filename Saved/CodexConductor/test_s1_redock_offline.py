"""Offline harness for s1_redock.py (system Python, no Unreal). Every gate has a failing (-) control.

Fixture (the live DRY re-reads all of it):
  S1 Hangar Root (29284.0135, 0, 0), rot 0 = LANDED [meas s1_landed_preview_record.json landed_transforms, 2 Oct;
    hangar_exit_doors_record.json landed_root_transform, 3 Oct].
  Scene 1 Entry Handoff Camera (28784.01, 0, 150) [meas CodexStructure/scene_docks.json].
  New P01 end view (25184.0135, 0, 150), yaw 0 [inf: old end - 3600 cm, P01_SHORTEN_PLAN.md; the live value is read].
  Rise root channel defaults X/Y/Z = root, no keys [meas s1_landed_preview_record.json binding_channels].
  I1 hangar drape / card world keys and templates [meas curtain_sleight_record_I1.json plan.hangar_drape/hangar_card].
  P01 slab loc.x 14567.00675, scale.x 294.340135 [meas floor_dark_wet_record.json slabs.P01.xf; loc z 0.0 after it].
  Pit liners / strips [meas CodexStructure/plane_pitliner_record.json, plane_pithole_record.json].
Run: python test_s1_redock_offline.py -> S1_REDOCK_HARNESS|tests=..|checks=..|failed=..
"""
import copy
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.dirname(HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rd = _load("s1_redock")
assert rd.unreal is None, "harness must run without Unreal"


def _json(*parts):
    with open(os.path.join(SAVED, *parts), encoding="utf-8") as h:
        return json.load(h)


ARGS = _json("CodexConductor", "s1_redock_args.json")
H = ARGS["hangar"]
CHECKS = {"n": 0, "failed": []}
TESTS = []


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)


def test(fn):
    TESTS.append(fn)
    return fn


def near(a, b, tol=1e-6):
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def has(refusals, prefix):
    return any(str(r).startswith(prefix) for r in refusals)


# ---- fixture -------------------------------------------------------------------------------------------------------
ROOT_LOC = [29284.0135, 0.0, 0.0]
ROOT = {"loc": list(ROOT_LOC), "rot": [0.0, 0.0, 0.0]}
ENTRY = {"loc": [28784.01, 0.0, 150.0], "yaw": 0.0}
END_NEW = {"loc": [25184.0135, 0.0, 150.0], "yaw": 0.0}
I1 = ARGS["interaction_sequence"]
RISE = ARGS["rise_sequence"]
RISE_GUID = ARGS["rise_root_binding_guid"]
TAG = H["tag"]


def ch(x, y, z, keys=None):
    out = {n: {"default": None, "keys": []} for n in rd.CHANNELS}
    out["Location.X"]["default"], out["Location.Y"]["default"], out["Location.Z"]["default"] = x, y, z
    for n in ("Rotation.X", "Rotation.Z", "Scale.X", "Scale.Y", "Scale.Z"):
        out[n]["default"] = 1.0 if n.startswith("Scale") else 0.0
    out["Rotation.Y"]["keys"] = [[-176, -90.0], [124, 0.0]]       # the rise pitch keys [meas]
    if keys:
        for n, k in keys.items():
            out[n]["keys"] = k
    return out


def keyed(points):
    """Spawnable channels as curtain_sleight _key_pose writes them: location keys, no location defaults."""
    out = {n: {"default": None, "keys": []} for n in rd.CHANNELS}
    for n in ("Scale.X", "Scale.Y", "Scale.Z"):
        out[n]["default"] = 1.0
    for f, p in points:
        for i, n in enumerate(("Location.X", "Location.Y", "Location.Z")):
            out[n]["keys"].append([f, p[i]])
        for n in ("Rotation.X", "Rotation.Y", "Rotation.Z"):
            out[n]["keys"].append([f, 0.0])
    return out


SLEIGHT = _json("CodexConductor", "curtain_sleight_record_I1.json")
DRAPE_KEYS = [(k[0], k[1:4]) for k in SLEIGHT["plan"]["hangar_drape"]["keys"]]
CARD_KEYS = [(k[0], k[1:4]) for k in SLEIGHT["plan"]["hangar_card"]["keys"]]


def rel(p):
    return rd.add(ROOT_LOC, p)


def facts(**over):
    rows = [
        {"path": "A/Root", "label": "S1 Hangar Root", "class": "StaticMeshActor", "parent": None, "tags": [TAG],
         "loc": list(ROOT_LOC), "rot": [0, 0, 0], "scale": [1, 1, 1]},
        {"path": "A/Apron", "label": "S1 Hangar Apron", "class": "StaticMeshActor", "parent": None,
         "tags": [TAG, "RigAtmos.Scene1Apron"], "loc": [29034.0135, 0.0, -10.0], "rot": [0, 0, 0], "scale": [5, 20, .2]},
        {"path": "A/PPV", "label": "S1 Hangar Pinned Exposure", "class": "PostProcessVolume", "parent": None,
         "tags": [TAG], "loc": [31934.0135, 0.0, 1500.0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
        {"path": "A/Arrival", "label": "S1 Arrival", "class": "InfinityStageArrival", "parent": None,
         "tags": [TAG, "RigAtmos.Arrival"], "loc": list(ROOT_LOC), "rot": [0, 0, 0], "scale": [1, 1, 1]},
        {"path": "A/FarWall", "label": "S1 Hangar Far Wall Above Exit", "class": "StaticMeshActor", "parent": "A/Root",
         "parent_label": "S1 Hangar Root", "tags": [TAG], "loc": rel([6025.0, 0.0, 1725.0]), "rot": [0, 0, 0],
         "scale": [1, 1, 1]},
        {"path": "A/RoofHinge", "label": "S1 Hangar Roof Hinge", "class": "StaticMeshActor", "parent": "A/Root",
         "parent_label": "S1 Hangar Root", "tags": [TAG], "loc": rel([6000.0, 0.0, 3000.0]), "rot": [0, 0, 0],
         "scale": [1, 1, 1]},
        {"path": "A/Roof", "label": "S1 Hangar Roof", "class": "StaticMeshActor", "parent": "A/RoofHinge",
         "parent_label": "S1 Hangar Roof Hinge", "tags": [TAG], "loc": rel([3000.0, 0.0, 3000.0]), "rot": [0, 0, 0],
         "scale": [1, 1, 1]},
        {"path": "A/Fly", "label": "S1 Hangar Lattice Fly", "class": "StaticMeshActor", "parent": "A/Root",
         "parent_label": "S1 Hangar Root", "tags": [TAG], "loc": rel([3000.0, 0.0, 1200.0]), "rot": [0, 0, 0],
         "scale": [1, 1, 1]},
        {"path": "A/Leaf", "label": "S1 Hangar Exit Door Leaf", "class": "StaticMeshActor", "parent": "A/Root",
         "parent_label": "S1 Hangar Root", "tags": [], "loc": rel([6024.95, 0.0, 225.0]), "rot": [0, 0, 0],
         "scale": [1, 1, 1]},
        {"path": "A/HCam", "label": "S1 Sleight Hangar Camera", "class": "CineCameraActor", "parent": "A/Root",
         "parent_label": "S1 Hangar Root", "tags": ["CurtainSleight", "CurtainSleight.I1"],
         "loc": rel([-500.0, 0.0, 150.0]), "rot": [0, 0, 0], "scale": [1, 1, 1]},
        {"path": "A/Lantern", "label": "S1 Sleight Twin Lantern", "class": "SpotLight", "parent": "A/Root",
         "parent_label": "S1 Hangar Root", "tags": ["CurtainSleight.I1"], "loc": rel([4405.85, -970.2, 357.08]),
         "rot": [0, 0, 0], "scale": [1, 1, 1]},
        {"path": "A/Slab", "label": "Passage 01 - Opening Floor", "class": "StaticMeshActor", "parent": None, "tags": [],
         "loc": [14567.00675, 0.0, 0.0], "rot": [0, 0, 0], "scale": [294.340135, 200.0, 0.01]},
        {"path": "A/Entry", "label": "Scene 1 — External Sound — Entry Handoff Camera",
         "class": "CineCameraActor", "parent": None, "tags": ["InfinityStage.SceneHandoff", "InfinityStage.SceneEntry"],
         "loc": list(ENTRY["loc"]), "rot": [0, 0, 0], "scale": [1, 1, 1]},
        {"path": "A/Struct", "label": "Infinity Stage - Structure 01", "class": "InfinityStageStructureActor",
         "parent": None, "tags": [], "loc": [27000.0, 0.0, 0.0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
        {"path": "A/Managed", "label": "P01 Wing 042 Lamp", "class": "SpotLight", "parent": None, "tags": [],
         "loc": [24800.0, 300.0, 400.0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
        {"path": "A/Far", "label": "Somewhere Else", "class": "StaticMeshActor", "parent": None, "tags": [],
         "loc": [0.0, 80000.0, 0.0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
    ]
    liners = _json("CodexStructure", "plane_pitliner_record.json")["plan"][0]["pieces"]
    for pc in liners:
        rows.append({"path": "A/" + pc["label"], "label": pc["label"], "class": "StaticMeshActor", "parent": None,
                     "tags": [], "loc": [sum(pc["x"]) / 2, sum(pc["y"]) / 2, sum(pc["z"]) / 2], "rot": [0, 0, 0],
                     "scale": [1, 1, 1]})
    for st in _json("CodexStructure", "plane_pithole_record.json")["plan"][0]["strips"]:
        rows.append({"path": "A/" + st["label"], "label": st["label"], "class": "StaticMeshActor", "parent": None,
                     "tags": [], "loc": [sum(st["x"]) / 2, sum(st["y"]) / 2, -5.5], "rot": [0, 0, 0],
                     "scale": [1, 1, 1]})
    drape_t = {"loc": list(DRAPE_KEYS[0][1])}
    card_t = {"loc": list(CARD_KEYS[0][1])}
    bindings = [
        {"sequence": RISE, "binding": "S1 Hangar Root", "guid": RISE_GUID, "kind": "possessable", "bound": ["A/Root"],
         "has_transform": True, "sections": 1, "channels": ch(*ROOT_LOC), "template": None, "template_loc": None},
        {"sequence": RISE, "binding": "S1 Hangar Roof Hinge", "guid": "R2", "kind": "possessable",
         "bound": ["A/RoofHinge"], "has_transform": True, "sections": 1, "channels": ch(6000.0, 0.0, 3000.0),
         "template": None, "template_loc": None},
        {"sequence": RISE, "binding": "S1 Hangar Pinned Exposure", "guid": "R3", "kind": "possessable",
         "bound": ["A/PPV"], "has_transform": False, "sections": 0, "channels": None, "template": None,
         "template_loc": None},
        {"sequence": I1, "binding": "Sleight Hangar Drape", "guid": "I1D", "kind": "spawnable", "bound": [],
         "has_transform": True, "sections": 1, "channels": keyed(DRAPE_KEYS), "template": drape_t,
         "template_loc": drape_t["loc"], "track": "CurtainSleight (Conductor)"},
        {"sequence": I1, "binding": "Sleight Hangar Shadow Card", "guid": "I1C", "kind": "spawnable", "bound": [],
         "has_transform": True, "sections": 1, "channels": keyed(CARD_KEYS), "template": card_t,
         "template_loc": card_t["loc"], "track": "CurtainSleight (Conductor)"},
        {"sequence": I1, "binding": "S1 Sleight Hangar Camera", "guid": "I1H", "kind": "possessable",
         "bound": ["A/HCam"], "has_transform": True, "sections": 1, "channels": keyed([(0, [-500.0, 0.0, 150.0])]),
         "template": None, "template_loc": None},
        {"sequence": I1, "binding": "Sleight Mouth Shadow Card", "guid": "I1M", "kind": "spawnable", "bound": [],
         "has_transform": True, "sections": 1, "channels": keyed([(75, [-42.8, 80000.0, 2480.0])]),
         "template": {"loc": [-42.8, 80000.0, 2480.0]}, "template_loc": [-42.8, 80000.0, 2480.0]},
    ]
    f = {"end_view": copy.deepcopy(END_NEW), "root": copy.deepcopy(ROOT), "root_pitch": 0.0,
         "entry_cam": copy.deepcopy(ENTRY), "rows": rows, "passage_owned": ["A/Managed"], "bindings": bindings,
         "removed_cm": 3600.0, "slab": {"loc": [14567.00675, 0.0, 0.0], "rot": [0, 0, 0],
                                        "scale": [294.340135, 200.0, 0.01]},
         "conflicts": {k: False for k in rd.STATE_FILES}}
    f.update(over)
    return f


# ---- tests ---------------------------------------------------------------------------------------------------------
@test
def t_frames():
    d = rd.dock_from_root(ROOT_LOC, 0.0, 500.0, 0.0)
    check(near(d["loc"], [28784.0135, 0.0, 0.0]), "+ dock = root - apron (yaw 0)")
    check(near(rd.root_from_dock(d, 500.0, 0.0), ROOT_LOC), "+ root_from_dock round trip")
    d90 = rd.dock_from_root([100.0, 200.0, 0.0], 90.0, 500.0, 0.0)
    check(near(d90["loc"], [100.0, -300.0, 0.0], 1e-9), "+ yaw 90: dock is 500 cm back along +y heading")
    check(near(rd.root_from_dock(d90, 500.0, 0.0), [100.0, 200.0, 0.0], 1e-9), "+ yaw 90 round trip")
    check(not near(rd.dock_from_root(ROOT_LOC, 0.0, 400.0, 0.0)["loc"], [28784.0135, 0.0, 0.0]),
          "- wrong apron gives a different dock (the apron number matters)")
    p = [123.0, -45.0, 6.0]
    fr = rd.xf([10.0, 20.0, 0.0], 37.0)
    check(near(rd.from_local(fr, rd.to_local(fr, p)), p, 1e-9), "+ to_local/from_local inverse")


@test
def t_solve_delta():
    tol = {"deg": 0.01, "z_cm": 1.0}
    sol, r = rd.solve_delta(END_NEW, ROOT, ENTRY, H, tol)
    check(not r, "+ straight shorten solves cleanly: %r" % r)
    check(near(sol["delta"], [-3600.0, 0.0, 0.0], 1e-6), "+ delta = -3600 x: %r" % sol["delta"])
    check(near(sol["new_root"], [25684.0135, 0.0, 0.0], 1e-6), "+ new root 25684.0135")
    check(near(sol["new_dock"]["loc"][:2], [25184.0135, 0.0], 1e-6), "+ new dock 25184.0135")
    check(sol["entry_cam_vs_old_dock_xy_cm"] < 0.01, "+ the live entry camera sits on the dock derived from the root")
    ev = dict(END_NEW, yaw=0.5)
    check(has(rd.solve_delta(ev, ROOT, ENTRY, H, tol)[1], "YAW_CHANGE"), "- a heading change refuses")
    ev = {"loc": [25184.0135, 0.0, 152.0], "yaw": 0.0}
    check(has(rd.solve_delta(ev, ROOT, ENTRY, H, tol)[1], "END_VIEW_HEIGHT_CHANGED"), "- a height change refuses")
    check(has(rd.solve_delta(END_NEW, {"loc": ROOT_LOC, "rot": [1.0, 0.0, 0.0]}, ENTRY, H, tol)[1],
              "ROOT_ROLL_NONZERO"), "- a rolled root refuses")
    # rotated dock (S2-like yaw): pure translation along the heading still solves
    yaw = -43.57
    root = {"loc": [1000.0, 2000.0, 0.0], "rot": [0.0, 0.0, yaw]}
    od = rd.dock_from_root(root["loc"], yaw, 500.0, 0.0)
    nd = rd.from_local(od, [-3600.0, 0.0, 150.0])
    s2, r2 = rd.solve_delta({"loc": nd, "yaw": yaw}, root, {"loc": od["loc"][:2] + [150.0], "yaw": yaw}, H, tol)
    check(not r2 and near(s2["delta"][:2], rd.predicted_delta(3600.0, yaw)[:2], 1e-6),
          "+ rotated dock: delta = -3600 along the heading")


@test
def t_delta_gates():
    check(rd.delta_gates([-3600.0, 0.0, 0.0], 3600.0, 0.0, 5.0) == [], "+ delta matches the shorten")
    check(rd.delta_gates([-3604.9, 0.0, 0.0], 3600.0, 0.0, 5.0) == [], "+ 4.9 cm inside tolerance")
    check(has(rd.delta_gates([-3605.1, 0.0, 0.0], 3600.0, 0.0, 5.0), "DELTA_NOT_AS_SHORTEN"), "- 5.1 cm refuses")
    check(has(rd.delta_gates([3600.0, 0.0, 0.0], 3600.0, 0.0, 5.0), "DELTA_NOT_AS_SHORTEN"), "- wrong sign refuses")
    check(has(rd.delta_gates([-3600.0, 40.0, 0.0], 3600.0, 0.0, 5.0), "DELTA_NOT_AS_SHORTEN"), "- lateral drift refuses")
    check(has(rd.delta_gates([0.2, 0.0, 0.0], 3600.0, 0.0, 5.0), "NOTHING_TO_MOVE"), "- zero delta (already docked)")
    check(has(rd.delta_gates([-3600.0, 0.0, 0.0], None, 0.0, 5.0), "SHORTEN_RECORD_MISSING"), "- no shorten record")


@test
def t_trim_slab():
    slab = {"loc": [14567.00675, 0.0, 0.0], "rot": [0.0, 0.0, 0.0], "scale": [294.340135, 200.0, 0.01]}
    t, r = rd.trim_slab(slab, ROOT_LOC, [-3600.0, 0.0, 0.0], 0.0)
    check(not r, "+ slab trims: %r" % r)
    check(abs(t["near_x"] + 150.0) < 1e-6, "+ near edge -150 kept")
    check(abs(t["far_x_after"] - 25684.0135) < 1e-6, "+ far edge = new hinge")
    check(abs(t["after"]["scale"][0] - 258.340135) < 1e-9 and abs(t["after"]["loc"][0] - 12767.00675) < 1e-6,
          "+ scale.x 258.340135, loc.x 12767.00675: %r" % t["after"])
    check(t["after"]["scale"][1:] == [200.0, 0.01] and t["after"]["loc"][1:] == [0.0, 0.0], "+ y/z untouched")
    check(slab["scale"][0] == 294.340135, "+ input not mutated")
    check(has(rd.trim_slab(dict(slab, loc=[14000.0, 0.0, 0.0]), ROOT_LOC, [-3600.0, 0, 0], 0.0)[1],
              "SLAB_FAR_EDGE_NOT_AT_HINGE"), "- a slab that does not end at the hinge refuses")
    check(has(rd.trim_slab(dict(slab, rot=[0.0, 0.0, 5.0]), ROOT_LOC, [-3600.0, 0, 0], 0.0)[1], "SLAB_ROTATED"),
          "- rotated slab refuses")
    check(has(rd.trim_slab(slab, ROOT_LOC, [-3600.0, 10.0, 0], 0.0)[1], "SLAB_TRIM_NEEDS_AXIS_ALIGNED"),
          "- off-axis delta refuses")
    check(has(rd.trim_slab(slab, ROOT_LOC, [-29400.0, 0.0, 0], 0.0)[1], "SLAB_WOULD_VANISH"), "- vanishing slab refuses")


@test
def t_channels():
    c = ch(*ROOT_LOC)
    s = rd.shift_channels(c, [-3600.0, 0.0, 0.0])
    check(abs(s["Location.X"]["default"] - 25684.0135) < 1e-9, "+ X default shifted")
    check(s["Rotation.Y"] == c["Rotation.Y"], "+ pitch keys untouched")
    check(c["Location.X"]["default"] == ROOT_LOC[0], "+ input not mutated")
    k = keyed(DRAPE_KEYS)
    sk = rd.shift_channels(k, [-3600.0, 0.0, 0.0])
    check([x[0] for x in sk["Location.X"]["keys"]] == [x[0] for x in k["Location.X"]["keys"]], "+ key times kept")
    check(all(abs(a[1] - b[1] + 3600.0) < 1e-9 for a, b in zip(sk["Location.X"]["keys"], k["Location.X"]["keys"])),
          "+ every X key -3600")
    check(sk["Location.Z"]["keys"] == k["Location.Z"]["keys"], "+ Z keys unchanged (dz 0)")
    check(rd.channels_equal(s, s) and not rd.channels_equal(s, c), "+/- channels_equal")
    bad = copy.deepcopy(c)
    del bad["Location.Y"]
    try:
        rd.shift_channels(bad, [1.0, 0, 0])
        check(False, "- missing channel must raise")
    except rd.PlanError:
        check(True, "- missing channel raises")
    check(rd.channel_base("Location.Y_183") == "Location.Y" and rd.channel_base("Location.Y") == "Location.Y",
          "+ suffixed channel names")


@test
def t_closure():
    f = facts()
    top, carried, r = rd.move_closure(f["rows"], TAG, ARGS["extra_move_labels"])
    labels = lambda ps: sorted(x["label"] for x in f["rows"] if x["path"] in ps)   # noqa: E731
    check(not r, "+ closure clean: %r" % r)
    check(set(labels(top)) == {"S1 Hangar Root", "S1 Hangar Apron", "S1 Hangar Pinned Exposure", "S1 Arrival"}
          | set(ARGS["extra_move_labels"]), "+ top-level = root/apron/PPV/Arrival + 8 pit pieces: %r" % labels(top))
    check("S1 Hangar Roof" in labels(carried) and "S1 Sleight Hangar Camera" in labels(carried)
          and "S1 Hangar Exit Door Leaf" in labels(carried), "+ grandchildren and untagged attached pieces carried")
    check("Passage 01 - Opening Floor" not in labels(top) + labels(carried), "+ the slab is not moved (trimmed)")
    t2, c2, r2 = rd.move_closure(f["rows"], TAG, ARGS["extra_move_labels"] + ["No Such Actor"])
    check(has(r2, "EXTRA_LABEL_COUNT"), "- a missing extra label refuses")
    rows = copy.deepcopy(f["rows"])
    rows.append({"path": "A/Hook", "label": "Hook", "class": "Actor", "parent": None, "tags": [], "loc": [0, 0, 0]})
    for x in rows:
        if x["label"] == "S1 Hangar Apron":
            x["parent"] = "A/Hook"
    check(has(rd.move_closure(rows, TAG, [])[2], "SEED_ATTACHED_OUTSIDE_SET"), "- a seed attached outside refuses")


@test
def t_region():
    f = facts()
    top, carried, _ = rd.move_closure(f["rows"], TAG, ARGS["extra_move_labels"])
    od = rd.dock_from_root(ROOT_LOC, 0.0, 500.0, 0.0)
    box = rd.region_box(ARGS["region"], 3600.0)
    reg = rd.classify_region(f["rows"], set(top) | set(carried), ARGS["trim_slab_label"], {"A/Managed"}, "Scene 1 ",
                             [], od, box)
    names = lambda k: [x["label"] for x in reg[k]]   # noqa: E731
    check(names("PASSAGE_OWNED") == ["Infinity Stage - Structure 01", "P01 Wing 042 Lamp"], "+ passage-owned listed")
    check(len(names("REGENERATED")) == 1 and "Entry Handoff" in names("REGENERATED")[0], "+ handoff camera regenerated")
    check(names("TRIM") == ["Passage 01 - Opening Floor"] and not reg["UNKNOWN"], "+ slab TRIM, no unknowns")
    check("Somewhere Else" not in json.dumps(reg), "+ actors outside the window ignored")
    rows = f["rows"] + [{"path": "A/U", "label": "P01 End Lantern", "class": "SpotLight", "parent": None, "tags": [],
                         "loc": [27500.0, 0.0, 300.0]}]
    reg2 = rd.classify_region(rows, set(top) | set(carried), ARGS["trim_slab_label"], {"A/Managed"}, "Scene 1 ", [], od,
                              box)
    check([x["label"] for x in reg2["UNKNOWN"]] == ["P01 End Lantern"], "- an unknown actor near the end is UNKNOWN")
    reg3 = rd.classify_region(rows, set(top) | set(carried), ARGS["trim_slab_label"], {"A/Managed"}, "Scene 1 ",
                              ["P01 End Lantern"], od, box)
    check([x["label"] for x in reg3["ACKED"]] == ["P01 End Lantern"] and not reg3["UNKNOWN"], "+ ack moves it to ACKED")
    check(rd.in_box(od, [24200.0, 0.0, 0.0], box) and not rd.in_box(od, [24100.0, 0.0, 0.0], box),
          "+/- window starts 1000 cm before the NEW end (24184)")


@test
def t_bindings():
    f = facts()
    top, carried, _ = rd.move_closure(f["rows"], TAG, ARGS["extra_move_labels"])
    od = rd.dock_from_root(ROOT_LOC, 0.0, 500.0, 0.0)
    hb = {"x0": 400.0, "x1": 8000.0, "half_y": 2500.0, "z0": -7000.0, "z1": 6000.0}
    c = rd.classify_bindings(f["bindings"], top, carried, (RISE, RISE_GUID), ARGS["handled_spawnables"], [], od, hb)
    check([b["binding"] for b in c["REKEY_ROOT"]] == ["S1 Hangar Root"], "+ rise root re-keyed")
    check(sorted(b["binding"] for b in c["REKEY_SPAWNABLE"]) == ["Sleight Hangar Drape", "Sleight Hangar Shadow Card"],
          "+ the two I1 hangar spawnables re-keyed")
    check(sorted(b["binding"] for b in c["RELATIVE_OK"]) == ["S1 Hangar Roof Hinge", "S1 Sleight Hangar Camera"],
          "+ attached bindings ride free")
    check([b["binding"] for b in c["INFO"]] == ["S1 Hangar Pinned Exposure"] and not c["REFUSE"],
          "+ PPV blend track informational, nothing refused")
    check("Sleight Mouth Shadow Card" not in json.dumps(c), "+ lane-2 mouth card ignored")
    b2 = f["bindings"] + [{"sequence": "/Game/X", "binding": "S1 Hangar Apron", "guid": "X1", "kind": "possessable",
                           "bound": ["A/Apron"], "has_transform": True, "sections": 1, "channels": ch(0, 0, 0)}]
    c2 = rd.classify_bindings(b2, top, carried, (RISE, RISE_GUID), ARGS["handled_spawnables"], [], od, hb)
    check(any("FOREIGN_WORLD_TRANSFORM" in b["why"] for b in c2["REFUSE"]), "- foreign world transform refuses")
    c2a = rd.classify_bindings(b2, top, carried, (RISE, RISE_GUID), ARGS["handled_spawnables"],
                               [{"sequence": "/Game/X", "binding": "S1 Hangar Apron"}], od, hb)
    check(not c2a["REFUSE"] and [b["binding"] for b in c2a["ACKED"]] == ["S1 Hangar Apron"], "+ ...unless acked")
    b3 = f["bindings"] + [{"sequence": "/Game/Animals", "binding": "Cow", "guid": "X2", "kind": "spawnable",
                           "bound": [], "has_transform": True, "sections": 1,
                           "channels": keyed([(0, [31000.0, 200.0, 0.0])]), "template_loc": [31000.0, 200.0, 0.0]}]
    c3 = rd.classify_bindings(b3, top, carried, (RISE, RISE_GUID), ARGS["handled_spawnables"], [], od, hb)
    check(any("SPAWNABLE_IN_OLD_HANGAR_UNHANDLED" in b["why"] for b in c3["REFUSE"]), "- unhandled spawnable refuses")
    # A double APPLY is stopped by RECORD_EXISTS and NOTHING_TO_MOVE (delta from the LIVE root); a 36 m shift of a point
    # deep in a 60 m box stays inside the old box, so this gate only catches a handled binding that is elsewhere.
    moved = copy.deepcopy(f["bindings"])
    for b in moved:
        if b["binding"] == "Sleight Hangar Drape":
            b["channels"] = rd.shift_channels(b["channels"], [0.0, 80000.0, 0])
            b["template_loc"] = rd.add(b["template_loc"], [0.0, 80000.0, 0])
    c4 = rd.classify_bindings(moved, top, carried, (RISE, RISE_GUID), ARGS["handled_spawnables"], [], od, hb)
    check(any("NOT_IN_OLD_HANGAR" in b["why"] for b in c4["REFUSE"]), "- a handled spawnable elsewhere refuses")


@test
def t_spawnable_template():
    k = keyed(DRAPE_KEYS)
    sp, r = rd.spawnable_plan("D", k, {"loc": list(DRAPE_KEYS[0][1])}, [-3600.0, 0.0, 0.0])
    check(not r and near(sp["template_after"]["loc"], rd.add(DRAPE_KEYS[0][1], [-3600.0, 0, 0])),
          "+ template follows key 0")
    check(has(rd.spawnable_plan("D", k, {"loc": [0.0, 0.0, 0.0]}, [-3600.0, 0, 0])[1], "TEMPLATE_NOT_AT_FIRST_KEY"),
          "- template elsewhere refuses (unknown composition)")
    check(has(rd.spawnable_plan("D", k, None, [-3600.0, 0, 0])[1], "TEMPLATE_NOT_AT_FIRST_KEY"), "- no template refuses")


@test
def t_landed_guard():
    hb = dict(H, height_cm=H["height_cm"] + 1600.0)
    new_root = rd.xf([25684.0135, 0.0, 0.0], 0.0)
    drape_new = rd.add(DRAPE_KEYS[0][1], [-3600.0, 0.0, 0.0])
    check(rd.inside_hangar(new_root, drape_new, hb, 50.0), "+ shifted drape inside the NEW landed box")
    wrong_sign = rd.add(DRAPE_KEYS[0][1], [3600.0, 0.0, 0.0])
    check(not rd.inside_hangar(new_root, wrong_sign, hb, 50.0), "- a wrong-sign shift lands outside the new box")
    local = rd.to_local(rd.xf(ROOT_LOC, 0.0), DRAPE_KEYS[0][1])
    sunk = rd.rest_pose_point(new_root, local)
    check(sunk[2] < -3000.0 and not rd.inside_hangar(new_root, sunk, hb, 50.0),
          "- composing through the REST root puts it ~%.0f m underground and the guard fails" % (sunk[2] / 100.0))
    f = facts(root_pitch=-90.0)
    check(has(rd.build_plan(f, ARGS)["refusals"], "ROOT_NOT_LANDED"), "- a hanging root refuses")
    f = facts()
    for x in f["rows"]:
        if x["label"] == "S1 Hangar Lattice Fly":
            x["loc"] = rel([3000.0, 0.0, -3300.0])            # a piece where the sunk-pose trap would put it
    check(has(rd.build_plan(f, ARGS)["refusals"], "HANGAR_PIECE_OUTSIDE_LANDED_BOX"), "- a sunk piece refuses")


@test
def t_build_plan():
    p = rd.build_plan(facts(), ARGS)
    check(p["refusals"] == [], "+ fixture plan clean: %r" % p["refusals"])
    check(not p["predicted"] and near(p["solution"]["delta"], [-3600.0, 0.0, 0.0]), "+ live delta")
    check(len(p["moves"]) == 12, "+ 12 top-level moves (4 hangar + 8 pit): %d" % len(p["moves"]))
    check(all(near(m["after"], rd.add(m["before"], [-3600.0, 0, 0])) for m in p["moves"] + p["carried"]),
          "+ every moved/carried actor = before + delta")
    check(len(p["rekeys"]) == 3 and {x["kind"] for x in p["rekeys"]} == {"ROOT", "SPAWNABLE"}, "+ 3 re-keys")
    root = [x for x in p["rekeys"] if x["kind"] == "ROOT"][0]
    check(abs(root["after"]["Location.X"]["default"] - 25684.0135) < 1e-9, "+ rise default 25684.0135")
    check(near(p["klara_dock_for_args"]["loc"], [25184.0135, 0.0, 150.0]), "+ Klara dock for her args")
    check(abs(p["trim"]["after"]["scale"][0] - 258.340135) < 1e-9, "+ slab trim in plan")
    e = p["expected_for_apply_args"]
    check(e["rekey_spawnables"] == ["Sleight Hangar Drape", "Sleight Hangar Shadow Card"] and len(e["top"]) == 12,
          "+ expected_for_apply_args")
    check(rd.expected_refusals(p, e, "APPLY") == [], "+ expected matches itself")
    check(has(rd.expected_refusals(p, dict(e, delta=[-3500.0, 0, 0]), "APPLY"), "DELTA_CHANGED_SINCE_DRY"),
          "- delta changed since DRY")
    check(has(rd.expected_refusals(p, dict(e, top=e["top"][1:]), "APPLY"), "TOP_CHANGED_SINCE_DRY"),
          "- move set changed since DRY")
    # predicted (before the shorten): live end view still on the old dock
    pp = rd.build_plan(facts(end_view={"loc": [28784.0135, 0.0, 150.0], "yaw": 0.0}, removed_cm=None), ARGS)
    check(pp["predicted"] and near(pp["solution"]["delta"], [-3600.0, 0, 0]) and has(pp["refusals"], "PREDICTED_ONLY"),
          "- before the shorten: predicted only, not appliable")
    check(len(pp["moves"]) == 12, "+ predicted DRY still lists the full move set")
    pz = rd.build_plan(facts(end_view={"loc": [28784.0135, 0.0, 150.0], "yaw": 0.0}), ARGS)
    check(has(pz["refusals"], "NOTHING_TO_MOVE"), "- shorten applied but end unmoved (or already re-docked)")
    f = facts()
    f["rows"].append({"path": "A/U", "label": "P01 End Lantern", "class": "SpotLight", "parent": None, "tags": [],
                      "loc": [27500.0, 0.0, 300.0], "rot": [0, 0, 0], "scale": [1, 1, 1]})
    check(has(rd.build_plan(f, ARGS)["refusals"], "REGION_UNKNOWN_NOT_MOVED"), "- an unknown neighbour refuses")
    check(not rd.build_plan(f, dict(ARGS, leave_in_place=["P01 End Lantern"]))["refusals"], "+ ...acked: clean")
    check(not rd.build_plan(f, dict(ARGS, extra_move_labels=ARGS["extra_move_labels"] + ["P01 End Lantern"]))[
        "refusals"], "+ ...or moved: clean")
    c = facts(conflicts=dict({k: False for k in rd.STATE_FILES}, klara_stream=True))
    check(has(rd.build_plan(c, ARGS)["refusals"], "CONFLICT_KLARA_STREAM_APPLIED"), "- Klara hook-in applied refuses")
    f = facts()
    f["bindings"][0]["channels"] = ch(29000.0, 0.0, 0.0)
    check(has(rd.build_plan(f, ARGS)["refusals"], "RISE_ROOT_DEFAULT_NOT_LIVE_ROOT"), "- rise default != live root")
    f = facts()
    f["bindings"] = [b for b in f["bindings"] if b["binding"] != "Sleight Hangar Shadow Card"]
    check(has(rd.build_plan(f, ARGS)["refusals"], "HANDLED_SPAWNABLE_NOT_FOUND"), "- a handled binding missing refuses")
    f = facts()
    f["bindings"][0]["sections"] = 2
    check(has(rd.build_plan(f, ARGS)["refusals"], "RISE_ROOT_SECTIONS"), "- two rise sections refuse")
    try:
        rd.build_plan(facts(end_view=None), ARGS)
        check(False, "- no end view must raise")
    except rd.PlanError:
        check(True, "- no end view raises")


@test
def t_readback():
    p = rd.build_plan(facts(), ARGS)
    live = {"actors": {m["path"]: m["after"] for m in p["moves"] + p["carried"]},
            "slab": {"loc": p["trim"]["after"]["loc"], "scale": p["trim"]["after"]["scale"]},
            "channels": {(x["sequence"], x["guid"]): x["after"] for x in p["rekeys"]},
            "templates": {(x["sequence"], x["guid"]): x["template_after"] for x in p["rekeys"] if x["kind"] == "SPAWNABLE"}}
    check(rd.readback_failures(p, live, "after") == [], "+ exact after reads back")
    check(rd.readback_failures(p, live, "before") != [], "- after state is not the before state")
    off = copy.deepcopy(live)
    k = p["moves"][0]["path"]
    off["actors"][k] = rd.add(off["actors"][k], [0.1, 0, 0])
    check(has(rd.readback_failures(p, off, "after"), "ACTOR_AFTER"), "- 0.1 cm actor error fails")
    off = copy.deepcopy(live)
    key = (p["rekeys"][0]["sequence"], p["rekeys"][0]["guid"])
    off["channels"][key] = p["rekeys"][0]["before"]
    check(has(rd.readback_failures(p, off, "after"), "CHANNELS_AFTER"), "- un-shifted channels fail")
    off = copy.deepcopy(live)
    off["slab"]["scale"] = p["trim"]["before"]["scale"]
    check(has(rd.readback_failures(p, off, "after"), "SLAB_AFTER"), "- untrimmed slab fails")
    rb = {"a": [1.0, 2.0, 3.0]}
    check(rd.rel_failures(rb, {"a": [1.0, 2.0, 3.0]}) == [] and rd.rel_failures(rb, {"a": [1.0, 2.0, 3.2]}) != [],
          "+/- root-relative invariance")


@test
def t_gates():
    check(rd.match_gate({"loc": [25184.0135, 0.0, 150.0], "yaw": 0.0}, [25184.0135, 0.0, 150.0], 0.0) == [],
          "+ entry camera on the new seat")
    check(has(rd.match_gate({"loc": [28784.01, 0.0, 150.0], "yaw": 0.0}, [25184.0135, 0.0, 150.0], 0.0),
              "ENTRY_CAMERA_NOT_ON_NEW_SEAT"), "- camera still on the old seat")
    check(has(rd.match_gate(None, [0, 0, 0], 0.0), "ENTRY_CAMERA_UNREADABLE"), "- unreadable camera")
    s = {"segments": [1], "managed": {"a": 1}, "keys": {}, "artist": [], "markers": []}
    check(rd.no_change_gate(s, copy.deepcopy(s)) == [], "+ rebuild no-change")
    check(has(rd.no_change_gate(s, dict(s, managed={"a": 2})), "REBUILD_CHANGED_MANAGED"), "- rebuild moved a section")
    allowed = [RISE, I1]
    check(rd.census_gate({"content": [RISE], "maps": [rd.EXPECTED_WORLD]}, allowed) == [], "+ census subset")
    check(has(rd.census_gate({"content": ["/Game/Other"], "maps": []}, allowed), "UNEXPECTED_DIRTY"), "- foreign dirt")
    check(has(rd.census_gate({"content": [], "maps": ["/Game/OtherMap"]}, allowed), "MAP_DIRTY"), "- other map dirty")
    base = {"mode": "APPLY", "confirm": "APPLY S1REDOCK", "census": {"content": [], "maps": []},
            "shorten_applied": True, "conflicts": {}}
    check(rd.live_gates(base) == [], "+ APPLY gates clean")
    for key, val, want in (("confirm", "DRY S1REDOCK", "CONFIRM_MISMATCH"), ("pie", True, "PIE_OR_SIE"),
                           ("sequencer_open", True, "SEQUENCER_IS_OPEN"), ("zz_actors", ["ZZ_x"], "ZZ_ACTORS"),
                           ("census", {"content": ["/Game/X"], "maps": []}, "DIRTY_CENSUS"),
                           ("record_exists", True, "RECORD_EXISTS"), ("shorten_applied", False, "P01_SHORTEN_NOT"),
                           ("conflicts", {"klara_seq": True}, "CONFLICTING_RECORDS")):
        check(has(rd.live_gates(dict(base, **{key: val})), want), "- live gate %s" % want)
    check(has(rd.live_gates({"mode": "REVERT", "confirm": "REVERT S1REDOCK", "census": {}}), "NO_APPLIED_RECORD"),
          "- REVERT without a record")


@test
def t_args():
    check(rd.validate_args(ARGS) == [], "+ shipped args valid for DRY: %r" % rd.validate_args(ARGS))
    a = dict(ARGS, mode="APPLY", confirm="APPLY S1REDOCK")
    check(has(rd.validate_args(a), "NOT_APPROVED") and has(rd.validate_args(a), "EXPECTED_DELTA_MISSING"),
          "- APPLY needs approval and the DRY's expected")
    check(has(rd.validate_args(dict(ARGS, scene=2)), "SCENE_INVALID"), "- S1 only")
    check(has(rd.validate_args(dict(ARGS, rise_root_binding_guid="x")), "RISE_ROOT_BINDING_GUID_INVALID"), "- bad guid")
    check(ARGS["mode"] == "DRY" and ARGS["expected"] is None and not ARGS["approved_by"], "+ shipped args are DRY")


@test
def t_records_agree():
    """The args' identities against the measured records (if a record moves, the harness says so)."""
    arr = _json("CodexStructure", "arrivals_record.json")
    s1 = [s for s in arr["scenes"] if int(s["scene"]) == 1][0]
    check(s1["binding"] == RISE_GUID and s1["rise"] == RISE and s1["root"] == H["root_label"], "+ rise binding guid")
    check(SLEIGHT["applied"] and SLEIGHT["plan"]["hangar_camera"]["attached_to"] == H["root_label"],
          "+ I1 hangar camera is root-attached (rides free)")
    check(all(b["binding"] in SLEIGHT["binding_guids"] for b in ARGS["handled_spawnables"]),
          "+ handled spawnable names exist in the I1 record")
    check(abs(SLEIGHT["plan"]["frames_of_reference"]["root"]["loc"][0] - ROOT_LOC[0]) < 1e-6, "+ I1 root = fixture")
    lp = _json("CodexConductor", "s1_landed_preview_record.json")
    check(near(lp["landed_transforms"]["S1 Hangar Root"]["location"], ROOT_LOC) and
          near(lp["rest_transforms"]["S1 Hangar Root"]["location"], ROOT_LOC), "+ rest/landed root LOCATION equal")
    ch_x = [c for c in lp["binding_channels"]["S1 Hangar Root"] if c["property"] == "Location.X"][0]
    check(ch_x["source"].startswith("channel default"), "+ rise root X is a default, not keyed [meas]")
    dw = _json("CodexConductor", "floor_dark_wet_record.json")["slabs"]["P01"]["xf"]
    check(abs(dw["loc"][0] + 50.0 * dw["scale"][0] - 29284.0135) < 0.01, "+ the slab's far edge is the hinge [meas]")
    hs = _json("CodexStructure", "hangar_s1_record.json")["hangar"]
    check(all(abs(hs[k] - H[k + "_cm"]) < 1e-9 for k in ("apron", "depth", "half_w", "height", "wall_t", "floor_t")),
          "+ hangar dims = hangar_s1_record.json")
    doors = _json("CodexConductor", "hangar_exit_doors_record.json")
    row = [r for r in doors["plan"]["scenes"] if int(r["scene"]) == 1][0]
    check(row["piece_coordinate_frame"] == "hangar_root", "+ exit doors composed in the root frame (ride free)")


def main():
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - counted as a failure
            CHECKS["failed"].append("%s raised %r" % (fn.__name__, exc))
    for f in CHECKS["failed"]:
        print("FAIL:", f)
    print("S1_REDOCK_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
