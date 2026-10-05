"""Offline harness for p03_floor.py (plain Python, no editor). Run:
    python Saved/CodexConductor/test_p03_floor.py
A fake `unreal` models Structure 03 as the 01:55 floor_dark_wet DRY measured it (straight level route from
(0, 160000, 0), 10921.97 cm, Ground on, FloorHeightCm 0, boards 5 cm, apron 400, lip -150), the slab
"Passage 03 - Floor" as the 10:34:54 P03 DRY row read it (top 0.5, MI_Floor_DarkWet, x -150 .. 11421.97 hinge,
y -27490 .. 26070), P01's slab, the S3 hangar root on the hinge, and the structure's layers (ground, grooves,
understage, forestage, stage front vanish with Ground off; gridiron, portal timbers, fence survive).
Every gate has a failing control. Exit 0 = all pass; prints P03_FLOOR_HARNESS_PASS|tests=N or _FAIL.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "p03_floor.py")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
DARKWET = "/Game/InfinityStage/RigAtmos/MI_Floor_DarkWet.MI_Floor_DarkWet"
OAK = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Oak_Hrrngbn_01_Mat_Inst_Dup.M_Oak_Hrrngbn_01_Mat_Inst_Dup"
CUBE = "/Engine/BasicShapes/Cube.Cube"
WALNUT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup.M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
S = None


# ============================================================================ fake unreal
class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


class _Q:
    def __init__(self, r):
        self._r = r

    def rotator(self):
        return Rotator(self._r.roll, self._r.pitch, self._r.yaw)


class _Xf:
    def __init__(self, t, r, s):
        self.translation, self.rotation, self.scale3d = t, _Q(r), s


class _Box:
    def __init__(self, mn, mx):
        self.min, self.max = Vector(*mn), Vector(*mx)


class _Asset:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path

    def get_bounding_box(self):
        return _Box((-50, -50, -50), (50, 50, 50))


class _Pkg:
    def __init__(self, n):
        self.n = n

    def get_name(self):
        return self.n


def _dirty():
    S.maps.add(WORLD)


class PrimitiveComponent:
    def __init__(self, name, box=None):
        self.name, self.box = name, box

    def get_name(self):
        return self.name


class InstancedStaticMeshComponent(PrimitiveComponent):
    def __init__(self, name, tags, count, box):
        super().__init__(name, box)
        self.tags, self.count = list(tags), count

    def get_editor_property(self, k):
        if k == "component_tags":
            return list(self.tags)
        raise AttributeError(k)

    def get_instance_count(self):
        return self.count


class StaticMeshComponent(PrimitiveComponent):
    def __init__(self, owner, mesh, mats):
        super().__init__("StaticMeshComponent0")
        self.owner, self.mesh, self.over = owner, mesh, list(mats)

    def get_editor_property(self, k):
        if k == "static_mesh":
            return self.mesh
        if k == "override_materials":
            return list(self.over)
        raise AttributeError(k)

    def get_world_transform(self):
        o = self.owner
        return _Xf(Vector(*o.loc), Rotator(*o.rot), Vector(*o.scale))

    def get_num_materials(self):
        return 1

    def get_materials(self):
        return [self.over[0] if self.over and self.over[0] is not None else _Asset("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")]

    def set_material(self, i, m):
        _dirty()
        if S.flags.get("material_ignored"):
            return
        while len(self.over) <= i:
            self.over.append(None)
        self.over[i] = m


class _Struct:
    def __init__(self, **kw):
        self.p = dict(kw)

    def get_editor_property(self, k):
        if k not in self.p:
            raise AttributeError(k)
        return self.p[k]

    def set_editor_property(self, k, v):
        if S.flags.get("ground_set_ignored") and k == "enabled":
            return
        self.p[k] = v


class Actor:
    def __init__(self, label, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), half=(0, 0, 0)):
        self.label, self.loc, self.rot, self.scale, self.half = label, list(loc), list(rot), list(scale), half
        self.children = []

    def get_actor_label(self):
        return self.label

    def get_actor_location(self):
        return Vector(*self.loc)

    def get_actor_rotation(self):
        return Rotator(*self.rot)

    def get_actor_scale3d(self):
        return Vector(*self.scale)

    def get_actor_bounds(self, only):
        return Vector(*self.loc), Vector(*self.half)

    def set_actor_location(self, v, sweep, tp):
        _dirty()
        self.loc = [v.x, v.y, v.z]

    def set_actor_rotation(self, r, tp):
        _dirty()
        self.rot = [r.roll, r.pitch, r.yaw]

    def set_actor_scale3d(self, v):
        _dirty()
        self.scale = [v.x, v.y, v.z]

    def modify(self):
        _dirty()

    def get_attached_actors(self):
        return list(self.children)

    def get_component_by_class(self, cls):
        return getattr(self, "smc", None) if cls is StaticMeshComponent else None


class StaticMeshActor(Actor):
    def __init__(self, label, loc, scale, mats):
        super().__init__(label, loc, (0, 0, 0), scale)
        self.smc = StaticMeshComponent(self, _Asset(CUBE), [_Asset(m) for m in mats])


class _Route:
    def __init__(self):
        self.length = S.route_len

    def get_spline_length(self):
        return S.route_len

    def get_transform_at_distance_along_spline(self, d, space, scale):
        y = 160000.0 + (S.curve * (d / S.route_len) ** 2 if S.curve else 0.0)
        z = S.route_tilt * d / S.route_len
        return _Xf(Vector(d, y, z), Rotator(0, 0, 0), Vector(1, 1, 1))


class InfinityStagePassageActor(Actor):
    def __init__(self):
        super().__init__("Passage 03 - Beach", (0, 160000, 0))
        self.wings = [PrimitiveComponent("Wing_L_%d" % i, ((1000 * i, 158800, 200), (100, 5, 200))) for i in range(4)]
        self.children = [Actor("P03 Wing Prop", (3000, 158000, 150), half=(50, 50, 150))]

    def get_editor_property(self, k):
        if k == "route":
            return _Route()
        raise AttributeError(k)

    def get_components_by_class(self, cls):
        return list(self.wings)


def _layer_boxes(ground_on):
    L = S.route_len
    out = [("StructureGridiron", ["InfinityStage.Structure", "InfinityStage.Structure.Gridiron"], 40, ((L / 2, 160000, 900), (L / 2, 1300, 10))),
           ("StructurePortalTimbers", ["InfinityStage.Structure", "InfinityStage.Structure.Portal"], 6, ((-75, 160000, 300), (80, 1000, 300))),
           ("UnderpassFence", ["InfinityStage.Structure", "InfinityStage.Structure.Underpass.Fence"], 12, ((L / 2, 160000, 150), (L / 2, 1250, 150)))]
    if ground_on:
        out += [("StructureGround", ["InfinityStage.Structure", "InfinityStage.Structure.Ground"], 900, ((L / 2, 160000, -2.5), (L / 2, 1200, 2.5))),
                ("StructureGrooves", ["InfinityStage.Structure", "InfinityStage.Structure.Grooves"], 60, ((L / 2, 160000, -2.5), (L / 2, 1100, 2.5))),
                ("StructureUnderstage", ["InfinityStage.Structure", "InfinityStage.Structure.Understage"], 11, ((L / 2, 160000, -260), (L / 2, 1200, 5))),
                ("StructureForestage", ["InfinityStage.Structure", "InfinityStage.Structure.Portal"], 50, ((-75, 160000, -2.5), (75, 600, 2.5))),
                ("StructureStageFront", ["InfinityStage.Structure", "InfinityStage.Structure.Portal"], 120, ((-400, 160000, -60), (300, 900, 60)))]
    return out


class InfinityStageStructureActor(Actor):
    def __init__(self):
        super().__init__("Infinity Stage - Structure 03", (0, 160000, 0))
        self.ground = _Struct(enabled=True, floor_height_cm=0.0, board_thickness_cm=5.0, apron_cm=400.0, cut_chariot_slots=True,
                              steel_grooves=True, understage=True, understage_depth_cm=250.0)
        self.portal = _Struct(enabled=True, forestage_depth_cm=150.0, stage_front=True, float_trough=True, offset_from_first_station_cm=0.0)
        self.passage = InfinityStagePassageActor()
        self.gen = 0
        self.comps = self._build()

    def _build(self):
        self.gen += 1
        on = self.ground.p["enabled"] or S.flags.get("materialize_ignores_ground")
        comps = []
        for name, tags, n, box in _layer_boxes(on):
            (o, e) = box
            if name == "StructureGridiron" and S.flags.get("gridiron_drift") and self.gen > 1:
                o = (o[0], o[1], o[2] + 3.0)
            comps.append(InstancedStaticMeshComponent("%s_%d" % (name, self.gen), tags, n, (o, e)))
        return comps

    def get_editor_property(self, k):
        if k == "ground":
            return copy.deepcopy(self.ground) if not S.flags.get("ground_shared") else self.ground
        if k == "portal":
            return self.portal
        if k == "passage":
            return self.passage
        raise AttributeError(k)

    def set_editor_property(self, k, v):
        _dirty()
        if k == "ground":
            self.ground = copy.deepcopy(v)

    def get_components_by_class(self, cls):
        return list(self.comps)

    def materialize_structure(self):
        if S.flags.get("materialize_fails"):
            return False
        self.comps = self._build()
        if S.flags.get("wing_drift"):
            self.passage.wings[0].box = ((0, 158800, 205), (100, 5, 200))
        if S.flags.get("foreign_dirty"):
            S.content.add("/Game/Foreign/Thing")
        return True

    def is_structure_current(self):
        return not S.flags.get("not_current")


class _World:
    def get_path_name(self):
        return WORLD + ".L_InfinityStage_V1VerticalSlice"


class UnrealEditorSubsystem:
    def get_game_world(self):
        return object() if S.pie else None

    def get_editor_world(self):
        return _World()


class EditorActorSubsystem:
    def get_all_level_actors(self):
        return list(S.actors)


class EditorLoadingAndSavingUtils:
    @staticmethod
    def get_dirty_content_packages():
        return [_Pkg(p) for p in sorted(S.content)]

    @staticmethod
    def get_dirty_map_packages():
        return [_Pkg(p) for p in sorted(S.maps)]

    @staticmethod
    def save_map(world, path):
        if S.flags.get("save_fails"):
            return False
        S.saves.append(path)
        with open(S.umap, "ab") as fh:
            fh.write(b"saved")
        S.maps.clear()
        if S.flags.get("post_save_dirty"):
            S.maps.add(WORLD)
        return True


class LevelSequenceEditorBlueprintLibrary:
    @staticmethod
    def get_current_level_sequence():
        return S.sequencer


class SystemLibrary:
    @staticmethod
    def get_component_bounds(comp):
        if comp.box is None:
            raise RuntimeError("no bounds")
        (o, e) = comp.box
        return Vector(*o), Vector(*e), 0.0


class SplineCoordinateSpace:
    WORLD = "WORLD"


class Paths:
    @staticmethod
    def project_dir():
        return S.repo

    @staticmethod
    def convert_relative_path_to_full(p):
        return p


def load_asset(p):
    return None if "Missing" in p else _Asset(p)


def get_editor_subsystem(cls):
    return cls()


def log(m):
    S.log.append(m)


def log_error(m):
    S.log.append(m)


def make_fake():
    m = types.ModuleType("unreal")
    for k, v in dict(globals()).items():
        if k in ("Vector", "Rotator", "PrimitiveComponent", "InstancedStaticMeshComponent", "StaticMeshComponent",
                 "StaticMeshActor", "InfinityStageStructureActor", "InfinityStagePassageActor", "UnrealEditorSubsystem",
                 "EditorActorSubsystem", "EditorLoadingAndSavingUtils", "LevelSequenceEditorBlueprintLibrary",
                 "SystemLibrary", "SplineCoordinateSpace", "Paths", "load_asset", "get_editor_subsystem", "log", "log_error"):
            setattr(m, k, v)
    return m


# ============================================================================ fixtures
HINGE = 11421.97


def fresh(tmp, slab_y=(-27490.0, 26070.0), slab_top=0.5, slab_mats=(DARKWET,)):
    global S
    S = types.SimpleNamespace(flags={}, pie=False, sequencer=None, content=set(), maps=set(), saves=[], log=[],
                              route_len=10921.97, route_tilt=0.0, curve=0.0, repo=tmp)
    os.makedirs(os.path.join(tmp, "Saved", "CodexConductor"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "Content", "InfinityStage", "Dev", "Maps"), exist_ok=True)
    S.umap = os.path.join(tmp, "Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
    with open(S.umap, "wb") as fh:
        fh.write(b"umap-v0")
    st = InfinityStageStructureActor()
    x0, x1 = -150.0, HINGE
    slab = StaticMeshActor("Passage 03 - Floor", ((x0 + x1) / 2, 160000 + (slab_y[0] + slab_y[1]) / 2, slab_top - 0.5),
                           ((x1 - x0) / 100, (slab_y[1] - slab_y[0]) / 100, 0.01), slab_mats)
    p01 = StaticMeshActor("Passage 01 - Opening Floor", (14567.0, 0, 0), (294.34, 200, 0.01), (DARKWET,))
    root = Actor("S3 Hangar Root", (HINGE, 160000, 0))
    S.actors = [st, st.passage, slab, p01, root]
    S.st, S.slab = st, slab
    return S


def load_tool():
    sys.modules["unreal"] = make_fake()
    spec = importlib.util.spec_from_file_location("p03_floor_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(mod, mode, confirm=True):
    a = {"mode": mode}
    if confirm and mode != "DRY":
        a["confirm"] = "%s P03FLOOR" % mode
    return mod.main(a)


def marker(prefix):
    return [l for l in S.log if l.startswith(prefix)]


def expect_fail(mod, mode, needle, confirm=True):
    try:
        run(mod, mode, confirm)
    except mod.P03FloorError:
        hit = [l for l in S.log if "P03_FLOOR_FAILED" in l and needle in l]
        assert hit, "failed, but not with %r: %s" % (needle, marker("P03_FLOOR_FAILED"))
        return
    raise AssertionError("expected failure %r, got success" % needle)


def slab_state():
    return (list(S.slab.loc), list(S.slab.scale), [m.get_path_name() if m else None for m in S.slab.smc.over])


def nothing_saved():
    assert S.saves == [], "saved %s" % S.saves


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# ============================================================================ tests
@test
def dry_ok_reports_and_mutates_nothing(mod):
    before = slab_state()
    rep = run(mod, "DRY")
    assert marker("P03_FLOOR_DRY_OK"), S.log[-1]
    assert slab_state() == before and not S.maps and not S.content
    assert rep["boards_on"] is True and rep["uncovered_now_cm"] == 0.0, rep["uncovered_now_cm"]
    assert abs(rep["plan"]["raise_cm"]) < 1e-6 and abs(rep["plan"]["x"][1] - HINGE) < 1e-6
    assert set(k.split("|")[0] for k in rep["removes"]) == {"StructureGround", "StructureGrooves", "StructureUnderstage",
                                                             "StructureForestage", "StructureStageFront"}, rep["removes"]
    assert os.path.exists(os.path.join(S.repo, "Saved", "CodexConductor", "p03_floor_dry_%s.json" % rep["run"]))


@test
def dry_route_past_hinge_refuses(mod):          # control: route + apron would floor the hangar
    S.route_len = 11500.0
    rep = run(mod, "DRY")
    assert marker("P03_FLOOR_DRY_REFUSED") and any("past the S3 hinge" in p for p in rep["problems"])


@test
def dry_narrow_slab_reports_uncovered(mod):     # the coverage report can be non-zero
    fresh(S.repo, slab_y=(-500.0, 500.0))
    rep = run(mod, "DRY")
    assert rep["uncovered_now_cm"] == 0.0 and rep["uncovered_area_now_m2"] > 100.0, rep["uncovered_area_now_m2"]
    assert rep["plan"]["y"][0] <= -1250.0 and rep["plan"]["y"][1] >= 1250.0, rep["plan"]["y"]


@test
def dry_short_slab_reports_uncovered_route(mod):
    fresh(S.repo)
    S.slab.scale[0] = 50.0                       # x -150+... now short of the route end
    S.slab.loc[0] = -150 + 2500.0
    rep = run(mod, "DRY")
    assert rep["uncovered_now_cm"] > 5000.0, rep["uncovered_now_cm"]
    assert marker("P03_FLOOR_DRY_REFUSED") and any("not on the S3 hinge" in p for p in rep["problems"])


@test
def apply_ok(mod):
    rec = run(mod, "APPLY")
    assert marker("P03_FLOOR_APPLY_OK"), S.log[-3:]
    assert S.saves == [WORLD] and not S.maps and not S.content
    assert S.st.ground.p["enabled"] is False and S.st.ground.p["floor_height_cm"] == 0.0
    assert not any(c.name.startswith(("StructureGround", "StructureForestage")) for c in S.st.comps)
    assert rec["state"] == "applied" and os.path.isdir(rec["backup"])
    assert S.slab.smc.over[0].get_path_name() == WALNUT, "walnut set explicitly, not P01's DarkWet"
    assert os.path.exists(os.path.join(rec["backup"], "L_InfinityStage_V1VerticalSlice.umap"))


@test
def apply_grows_narrow_low_oak_slab(mod):
    fresh(S.repo, slab_y=(-500.0, 500.0), slab_top=-5.0, slab_mats=(OAK,))
    run(mod, "APPLY")
    sx = S.slab.scale[1] * 100.0
    assert sx >= 2500.0 and abs(S.slab.loc[2] - 0.0) < 1e-6, (sx, S.slab.loc)
    assert S.slab.smc.over[0].get_path_name() == WALNUT


@test
def dry_reports_poke_through(mod):              # surviving portal timbers (trough/posts) cross the +0.5 top
    rep = run(mod, "DRY")
    assert any(p["layer"].startswith("StructurePortalTimbers") for p in rep["poke_through"]), rep["poke_through"]
    assert not any(p["layer"].startswith("StructureGround") for p in rep["poke_through"])


@test
def floor_material_override_and_missing(mod):
    try:
        mod.main({"mode": "APPLY", "confirm": "APPLY P03FLOOR", "floor_material": "/Game/Missing/M_X.M_X"})
        raise AssertionError("missing material accepted")
    except mod.P03FloorError:
        assert any("does not load" in l for l in S.log)
    nothing_saved()
    assert S.st.ground.p["enabled"]
    S.log.clear()
    mod.main({"mode": "APPLY", "confirm": "APPLY P03FLOOR", "floor_material": OAK})
    assert S.slab.smc.over[0].get_path_name() == OAK


@test
def apply_needs_confirm(mod):
    expect_fail(mod, "APPLY", "CONFIRM_MISSING", confirm=False)
    nothing_saved()


@test
def apply_refuses_pie(mod):
    S.pie = True
    expect_fail(mod, "APPLY", "PIE_ACTIVE")
    nothing_saved()


@test
def apply_refuses_dirty(mod):
    S.content.add("/Game/Other")
    before = slab_state()
    expect_fail(mod, "APPLY", "DIRTY_BEFORE")
    assert slab_state() == before and S.st.ground.p["enabled"]


@test
def apply_refuses_bench(mod):
    S.actors.append(Actor("ZZ_Bench"))
    expect_fail(mod, "APPLY", "BENCH_ACTORS")


@test
def apply_refuses_sequencer(mod):
    S.sequencer = object()
    expect_fail(mod, "APPLY", "SEQUENCER_OPEN")


@test
def apply_refuses_existing_record(mod):
    open(os.path.join(S.repo, "Saved", "CodexConductor", "p03_floor_record.json"), "w").write("{}")
    expect_fail(mod, "APPLY", "RECORD_EXISTS")
    assert S.st.ground.p["enabled"]


@test
def apply_refuses_two_structures(mod):
    S.actors.append(InfinityStageStructureActor())
    expect_fail(mod, "APPLY", "STRUCTURE_COUNT")


@test
def apply_refuses_missing_slab(mod):
    S.actors.remove(S.slab)
    expect_fail(mod, "APPLY", "LABEL_COUNTS")


@test
def apply_refuses_unlevel_route(mod):
    S.route_tilt = 2.0
    expect_fail(mod, "APPLY", "route not level")


@test
def apply_refuses_curved_route(mod):
    S.curve = 800.0
    expect_fail(mod, "APPLY", "ROUTE_CURVED")
    S.log.clear()
    rep = run(mod, "DRY")
    assert rep["proposed_tiles"] and all(t["tag"] == "P03Floor.Extra" for t in rep["proposed_tiles"])


@test
def apply_refuses_hinge_disagreement(mod):
    S.actors[-1].loc[0] = HINGE + 50.0
    expect_fail(mod, "APPLY", "not on the S3 hinge")


@test
def apply_refuses_raise_out_of_range(mod):
    fresh(S.repo, slab_top=-20.0)
    expect_fail(mod, "APPLY", "raise")


@test
def apply_refuses_boards_already_off(mod):
    S.st.ground.p["enabled"] = False
    expect_fail(mod, "APPLY", "BOARDS_ALREADY_OFF")


@test
def apply_ground_readback(mod):
    S.flags["ground_set_ignored"] = True
    expect_fail(mod, "APPLY", "GROUND_READBACK")
    nothing_saved()


@test
def apply_materialize_fails(mod):
    S.flags["materialize_fails"] = True
    expect_fail(mod, "APPLY", "MATERIALIZE_FAILED")
    nothing_saved()
    assert any("NOTHING SAVED" in l for l in S.log)


@test
def apply_not_current(mod):
    S.flags["not_current"] = True
    expect_fail(mod, "APPLY", "NOT_CURRENT")
    nothing_saved()


@test
def apply_surviving_layer_drift(mod):
    S.flags["gridiron_drift"] = True
    expect_fail(mod, "APPLY", "StructureGridiron")
    nothing_saved()


@test
def apply_boards_survive(mod):
    S.flags["materialize_ignores_ground"] = True
    expect_fail(mod, "APPLY", "still")
    nothing_saved()


@test
def apply_wing_drift(mod):
    S.flags["wing_drift"] = True
    expect_fail(mod, "APPLY", "Wing_L_0")
    nothing_saved()


@test
def apply_material_readback(mod):
    fresh(S.repo, slab_mats=(OAK,))
    S.flags["material_ignored"] = True
    expect_fail(mod, "APPLY", "materials")
    nothing_saved()


@test
def apply_dirty_scope(mod):
    S.flags["foreign_dirty"] = True
    expect_fail(mod, "APPLY", "DIRTY_SCOPE")
    nothing_saved()


@test
def apply_save_fails(mod):
    S.flags["save_fails"] = True
    expect_fail(mod, "APPLY", "SAVE_FAILED")


@test
def apply_post_save_dirty(mod):
    S.flags["post_save_dirty"] = True
    expect_fail(mod, "APPLY", "POST_SAVE_DIRTY")


@test
def revert_exact(mod):
    fresh(S.repo, slab_y=(-500.0, 500.0), slab_top=-5.0, slab_mats=(OAK,))
    before = slab_state()
    run(mod, "APPLY")
    assert slab_state() != before
    S.log.clear()
    S.saves.clear()
    run(mod, "REVERT")
    assert marker("P03_FLOOR_REVERT_OK"), S.log[-3:]
    got = slab_state()
    assert all(abs(a - b) < 1e-6 for a, b in zip(got[0] + got[1], before[0] + before[1])) and got[2] == before[2], (got, before)
    assert S.st.ground.p["enabled"] is True and any(c.name.startswith("StructureGround") for c in S.st.comps)
    assert S.saves == [WORLD]
    here = os.path.join(S.repo, "Saved", "CodexConductor")
    assert not os.path.exists(os.path.join(here, "p03_floor_record.json"))
    assert any(n.startswith("p03_floor_record.reverted-") for n in os.listdir(here))


@test
def revert_needs_record(mod):
    expect_fail(mod, "REVERT", "NO_RECORD")


@test
def revert_needs_confirm(mod):
    run(mod, "APPLY")
    expect_fail(mod, "REVERT", "CONFIRM_MISSING", confirm=False)


@test
def revert_refuses_applying_record(mod):
    p = os.path.join(S.repo, "Saved", "CodexConductor", "p03_floor_record.json")
    json.dump({"state": "applying"}, open(p, "w"))
    expect_fail(mod, "REVERT", "RECORD_STATE")


@test
def revert_refuses_moved_slab(mod):
    run(mod, "APPLY")
    S.slab.loc[0] += 10.0
    expect_fail(mod, "REVERT", "NOT_APPLIED_STATE")


@test
def revert_refuses_boards_on(mod):
    run(mod, "APPLY")
    S.st.ground.p["enabled"] = True
    expect_fail(mod, "REVERT", "boards are on")


@test
def revert_material_readback(mod):
    fresh(S.repo, slab_mats=(OAK,))
    run(mod, "APPLY")
    S.flags["material_ignored"] = True
    S.saves.clear()
    expect_fail(mod, "REVERT", "READBACK")
    nothing_saved()


@test
def revert_layers_not_restored(mod):
    run(mod, "APPLY")
    S.flags["gridiron_drift"] = True
    S.saves.clear()
    expect_fail(mod, "REVERT", "LAYERS_NOT_RESTORED")
    nothing_saved()


@test
def unknown_mode(mod):
    expect_fail(mod, "WIPE", "UNKNOWN_MODE")


def main():
    passed, failed = 0, []
    for fn in TESTS:
        tmp = tempfile.mkdtemp(prefix="p03floor_")
        try:
            fresh(tmp)
            mod = load_tool()
            fn(mod)
            passed += 1
        except Exception:  # noqa: BLE001
            failed.append((fn.__name__, traceback.format_exc()))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            sys.modules.pop("unreal", None)
    for n, tb in failed:
        print("FAIL", n, "\n", tb)
    if failed:
        print("P03_FLOOR_HARNESS_FAIL|passed=%d|failed=%d|%s" % (passed, len(failed), [n for n, _ in failed]))
        return 1
    print("P03_FLOOR_HARNESS_PASS|tests=%d" % passed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
