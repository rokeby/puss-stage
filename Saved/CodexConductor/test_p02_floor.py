"""Offline harness for p02_floor.py (plain Python, no editor). Run:
    python Saved/CodexConductor/test_p02_floor.py
A fake `unreal` models Structure 02 from the 6 Oct 01:43 p02_straighten DRY (p02_straighten_dry_P02STR-20261006-014311.json):
the CURVED route (actor (0, 80000, 0), the 3 recorded spline points + tangents evaluated as cubic Hermite, 13582.6 cm),
Ground on with FloorHeightCm 0, the four walnut slabs at their recorded transforms with top +0.5 (p02_floor_walnut
target_top), the S2 dock from hangar_s2_record.json, board / groove / understage / forestage / stage-front instances laid
along the route, and surviving gridiron / fixtures / portal / fence layers. Instance transforms are real per instance;
cached component bounds can be made STALE (all-zero after a rebuild) to replay the 6 Oct 01:47 P03 false alarm.
Every gate has a failing control. Exit 0 = all pass; prints P02_FLOOR_HARNESS_PASS|tests=N or _FAIL.
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
TOOL = os.path.join(HERE, "p02_floor.py")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
DARKWET = "/Game/InfinityStage/RigAtmos/MI_Floor_DarkWet.MI_Floor_DarkWet"
CUBE = "/Engine/BasicShapes/Cube.Cube"
WALNUT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup.M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
ACTOR_LOC = (0.0, 80000.0, 0.0)
# p02_straighten_dry_P02STR-20261006-014311.json "spline" (route-local; route_rel = identity)
SPLINE = [((0.0, 0.0), (6953.233881010924, 2938.26708984375), (6953.233881010924, 2938.26708984375)),
          ((6953.233881010924, 2938.26708984375), (8638.178583159362, 512.9417419433594), (8638.178583159362, 512.9417419433594)),
          ((11857.834499999999, 0.0), (0.0, 0.0), (0.0, 0.0))]
SLAB_ROWS = {  # same DRY "slabs" (loc z 0 = top 0.5 after P02FL-20261005-103517)
    "Passage 02 - Floor Near": ((5996.18, 95225.6, 0.0), (270.7546, 712.5424, 0.01)),
    "Passage 02 - Floor Left": ((16774.87, 54867.19, 0.0), (441.7878, 276.336, 0.01)),
    "Passage 02 - Floor Right": ((42141.55, 81530.42, 0.0), (441.7878, 412.7064, 0.01)),
    "Passage 02 - Floor Far": ((31094.52, 61936.41, 0.0), (331.7478, 23.5, 0.01)),
}
SLAB_YAW = -43.57249832153321
DOCK = {"loc": [10742.232211654631, 81299.0241181779, 180.0], "yaw": -43.57251940082824}
S = None


# ============================================================================ route polyline
def _herm(p0, m0, p1, m1, t):
    h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
    h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    return tuple(h00 * a + h10 * b + h01 * c + h11 * d for a, b, c, d in zip(p0, m0, p1, m1))


def _polyline():
    pts = []
    for i in range(len(SPLINE) - 1):
        for k in range(400):
            pts.append(_herm(SPLINE[i][0], SPLINE[i][2], SPLINE[i + 1][0], SPLINE[i + 1][1], k / 400.0))
    pts.append(SPLINE[-1][0])
    pts = [(x + ACTOR_LOC[0], y + ACTOR_LOC[1]) for x, y in pts]
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    return pts, cum


POLY, CUM = _polyline()
ROUTE_LEN = CUM[-1]


def route_at(d):
    """(x, y, yaw) at distance d; extrapolates along the end tangents outside 0..L."""
    if d <= 0.0:
        i = 0
    elif d >= ROUTE_LEN:
        i = len(POLY) - 2
    else:
        lo, hi = 0, len(CUM) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if CUM[mid] <= d else (lo, mid)
        i = lo
    (x0, y0), (x1, y1) = POLY[i], POLY[i + 1]
    seg = max(1e-9, CUM[i + 1] - CUM[i])
    t = (d - CUM[i]) / seg
    return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, math.degrees(math.atan2(y1 - y0, x1 - x0))


def lane_pts(d0, d1, step, offsets, z):
    out, d = [], d0
    while d <= d1 + 1e-6:
        x, y, yaw = route_at(d)
        nx, ny = -math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
        out += [(x + nx * o, y + ny * o, z) for o in offsets]
        d += step
    return out


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
    def __init__(self, name, tags, pts, gen):
        super().__init__(name)
        self.tags, self.pts, self.gen = list(tags), list(pts), gen

    def get_editor_property(self, k):
        if k == "component_tags":
            return list(self.tags)
        raise AttributeError(k)

    def get_instance_count(self):
        return len(self.pts)

    def get_instance_transform(self, i, world):
        if S.flags.get("no_instance_api"):
            raise AttributeError("get_instance_transform")
        return _Xf(Vector(*self.pts[i]), Rotator(), Vector(1, 1, 1))


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
        if S.flags.get("ground_height_drift") and k == "enabled":
            self.p["floor_height_cm"] = 5.0
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

    def modify(self):
        _dirty()

    def get_attached_actors(self):
        return list(self.children)

    def get_component_by_class(self, cls):
        return getattr(self, "smc", None) if cls is StaticMeshComponent else None


class StaticMeshActor(Actor):
    def __init__(self, label, loc, scale, mats):
        super().__init__(label, loc, (0, 0, SLAB_YAW), scale)
        self.smc = StaticMeshComponent(self, _Asset(CUBE), [_Asset(m) for m in mats])


class _Route:
    def get_spline_length(self):
        return ROUTE_LEN

    def get_transform_at_distance_along_spline(self, d, space, scale):
        x, y, yaw = route_at(d)
        return _Xf(Vector(x, y, S.route_tilt * d / ROUTE_LEN), Rotator(0, 0, yaw), Vector(1, 1, 1))


class InfinityStagePassageActor(Actor):
    def __init__(self):
        super().__init__("Passage 02 - External Sound", ACTOR_LOC)
        self.wings = [PrimitiveComponent("Wing_L_%d" % i, ((1000 * i, 78800, 200), (100, 5, 200))) for i in range(4)]
        self.children = [Actor("P02 Wing Prop", (3000, 78000, 150), half=(50, 50, 150))]

    def get_editor_property(self, k):
        if k == "route":
            return _Route()
        raise AttributeError(k)

    def get_components_by_class(self, cls):
        return list(self.wings)


def _layers(ground_on):
    L = ROUTE_LEN
    T = "InfinityStage.Structure"
    out = [("StructureGridiron", [T, T + ".Gridiron"], lane_pts(0, L, 1000, (-1300, 1300), 900.0)),
           ("StructureFixtures", [T, T + ".Fixtures"], lane_pts(0, L, 1500, (-1250, 1250), 600.0)),
           ("StructurePortal", [T, T + ".Portal"], lane_pts(-75, -75, 1, (-1000, 1000), 0.0) + lane_pts(-75, -75, 1, (-1000, 1000), 600.0)),
           ("UnderpassFence", [T, T + ".Underpass.Fence"], lane_pts(0, L, 1000, (-1250, 1250), 150.0))]
    if ground_on:
        out += [("StructureGround", [T, T + ".Ground"], lane_pts(0, L, 400, S.ground_lanes, -2.5)),
                ("StructureGrooves", [T, T + ".Grooves"], lane_pts(0, L, 800, (-900, 900), -2.5)),
                ("StructureUnderstage", [T, T + ".Understage"], lane_pts(0, L, 1200, (0,), -260.0)),
                ("StructureForestage", [T, T + ".Portal"], lane_pts(-75, -75, 1, (-600, -300, 0, 300, 600), -2.5)),
                ("StructureStageFront", [T, T + ".Portal"], lane_pts(-400, -400, 1, (-900, -300, 300, 900), -60.0))]
    return out


class InfinityStageStructureActor(Actor):
    def __init__(self):
        super().__init__("Infinity Stage - Structure 02", ACTOR_LOC)
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
        for name, tags, pts in _layers(on):
            if name == "StructureGridiron" and S.flags.get("gridiron_drift") and self.gen > 1:
                pts = [(x, y, z + 3.0) for x, y, z in pts]
            if name == "StructureFixtures" and S.flags.get("fixtures_blank") and self.gen > 1:
                pts = []
            comps.append(InstancedStaticMeshComponent("%s_%d" % (name, self.gen), tags, pts, self.gen))
        return comps

    def get_editor_property(self, k):
        if k == "ground":
            return copy.deepcopy(self.ground)
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
            self.passage.wings[0].box = ((0, 78800, 205), (100, 5, 200))
        if S.flags.get("materialize_moves_slab"):
            S.slabs["Passage 02 - Floor Far"].loc[0] += 5.0
        if S.flags.get("materialize_rematerials_slab"):
            S.slabs["Passage 02 - Floor Left"].smc.over[0] = _Asset(DARKWET)
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
        if S.flags.get("post_save_ground_on"):
            S.st.ground.p["enabled"] = True
        return True


class LevelSequenceEditorBlueprintLibrary:
    @staticmethod
    def get_current_level_sequence():
        return S.sequencer


class SystemLibrary:
    @staticmethod
    def get_component_bounds(comp):
        """Cached bounds. ISMs re-created by a materialize read ALL-ZERO when stale_cached_bounds is set (the 6 Oct 01:47
        P03 observation); otherwise the true origin AABB."""
        if isinstance(comp, InstancedStaticMeshComponent):
            if S.flags.get("stale_cached_bounds") and comp.gen > 1:
                return Vector(), Vector(), 0.0
            if not comp.pts:
                return Vector(), Vector(), 0.0
            lo = [min(p[i] for p in comp.pts) for i in range(3)]
            hi = [max(p[i] for p in comp.pts) for i in range(3)]
            return Vector(*[(a + b) / 2 for a, b in zip(lo, hi)]), Vector(*[(b - a) / 2 for a, b in zip(lo, hi)]), 0.0
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
    for k in ("Vector", "Rotator", "PrimitiveComponent", "InstancedStaticMeshComponent", "StaticMeshComponent",
              "StaticMeshActor", "InfinityStageStructureActor", "InfinityStagePassageActor", "UnrealEditorSubsystem",
              "EditorActorSubsystem", "EditorLoadingAndSavingUtils", "LevelSequenceEditorBlueprintLibrary",
              "SystemLibrary", "SplineCoordinateSpace", "Paths", "load_asset", "get_editor_subsystem", "log", "log_error"):
        setattr(m, k, globals()[k])
    return m


# ============================================================================ fixtures
def fresh(tmp, mats=WALNUT):
    global S
    S = types.SimpleNamespace(flags={}, pie=False, sequencer=None, content=set(), maps=set(), saves=[], log=[],
                              route_tilt=0.0, repo=tmp, ground_lanes=(-1100, -700, -300, 300, 700, 1100))
    os.makedirs(os.path.join(tmp, "Saved", "CodexConductor"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "Saved", "CodexStructure"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "Content", "InfinityStage", "Dev", "Maps"), exist_ok=True)
    json.dump({"dock": DOCK}, open(os.path.join(tmp, "Saved", "CodexStructure", "hangar_s2_record.json"), "w"))
    S.umap = os.path.join(tmp, "Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
    with open(S.umap, "wb") as fh:
        fh.write(b"umap-v0")
    st = InfinityStageStructureActor()
    S.slabs = {l: StaticMeshActor(l, loc, sc, (mats,)) for l, (loc, sc) in SLAB_ROWS.items()}
    S.actors = [st, st.passage] + list(S.slabs.values()) + [Actor("Passage 01 - Opening Floor")]
    S.st = st
    return S


def load_tool():
    sys.modules["unreal"] = make_fake()
    spec = importlib.util.spec_from_file_location("p02_floor_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(mod, mode, confirm=True):
    a = {"mode": mode}
    if confirm and mode != "DRY":
        a["confirm"] = "%s P02FLOOR" % mode
    return mod.main(a)


def marker(prefix):
    return [l for l in S.log if l.startswith(prefix)]


def expect_fail(mod, mode, needle, confirm=True):
    try:
        run(mod, mode, confirm)
    except mod.P02FloorError:
        hit = [l for l in S.log if "P02_FLOOR_FAILED" in l and needle in l]
        assert hit, "failed, but not with %r: %s" % (needle, marker("P02_FLOOR_FAILED"))
        return
    raise AssertionError("expected failure %r, got success" % needle)


def slabs_state():
    return {l: (list(a.loc), list(a.rot), list(a.scale), [m.get_path_name() if m else None for m in a.smc.over])
            for l, a in S.slabs.items()}


def nothing_saved():
    assert S.saves == [], "saved %s" % S.saves


def straighten_record():
    p = os.path.join(S.repo, "Saved", "CodexConductor", "p02_straighten_record.json")
    json.dump({"run": "P02STR-x", "status": "saved", "floor_step": True}, open(p, "w"))


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# ============================================================================ tests
@test
def fixture_route_matches_recorded_length(mod):    # the fake route is the recorded spline (13582.59 cm)
    assert abs(ROUTE_LEN - 13582.59) < 1.0, ROUTE_LEN


@test
def dry_ok_curved_route_no_gaps_pit_reported(mod):
    before = slabs_state()
    rep = run(mod, "DRY")
    assert marker("P02_FLOOR_DRY_OK"), [l for l in S.log if "DRY_" in l][-1]
    assert slabs_state() == before and not S.maps and not S.content
    assert rep["boards_on"] is True and rep["coverage"]["gaps"] == 0, rep["coverage"]
    assert rep["coverage"]["pit"] > 0, "the route tail / boards inside the S2 pit are reported as PIT"
    assert rep["pit"] and abs(rep["pit"]["x0"] - 500.0) < 1.0 and abs(rep["pit"]["half_y"] - 1175.0) < 1.0, rep["pit"]
    assert set(k.split("|")[0] for k in rep["removes"]) == {"StructureGround", "StructureGrooves", "StructureUnderstage",
                                                             "StructureForestage", "StructureStageFront"}, rep["removes"]
    assert all(abs(v["top"] - 0.5) < 1e-6 for v in rep["slabs"].values())
    assert not rep["proposed_fits_report_only"]
    assert os.path.exists(os.path.join(S.repo, "Saved", "CodexConductor", "p02_floor_dry_%s.json" % rep["run"]))


@test
def dry_reports_poke_through(mod):              # the portal timbers cross the slab top
    rep = run(mod, "DRY")
    assert any(p["layer"].startswith("StructurePortal|") for p in rep["poke_through"]), rep["poke_through"]
    assert not any(p["layer"].startswith("StructureGround") for p in rep["poke_through"])


@test
def dry_gap_outside_pit_refuses_and_proposes(mod):   # control: shrink Near -> boards uncovered outside the pit
    S.slabs["Passage 02 - Floor Near"].scale[1] = 200.0
    before = slabs_state()
    rep = run(mod, "DRY")
    assert marker("P02_FLOOR_DRY_REFUSED") and rep["coverage"]["gaps"] > 0
    assert any(p.startswith("COVERAGE_GAPS") for p in rep["problems"])
    assert "Passage 02 - Floor Near" in rep["proposed_fits_report_only"], rep["proposed_fits_report_only"]
    assert slabs_state() == before


@test
def apply_refuses_gap(mod):
    S.slabs["Passage 02 - Floor Near"].scale[1] = 200.0
    before = slabs_state()
    expect_fail(mod, "APPLY", "COVERAGE_GAPS")
    assert slabs_state() == before and S.st.ground.p["enabled"]
    nothing_saved()


@test
def wide_boards_outside_slabs_are_gaps(mod):     # control: board lanes beyond every slab edge
    S.ground_lanes = (-1100, 1100, 90000)
    S.st.comps = S.st._build()
    rep = run(mod, "DRY")
    assert rep["coverage"]["gaps"] > 0 and marker("P02_FLOOR_DRY_REFUSED")


@test
def hangar_record_missing_refuses(mod):
    os.remove(os.path.join(S.repo, "Saved", "CodexStructure", "hangar_s2_record.json"))
    rep = run(mod, "DRY")
    assert any("hangar dock unreadable" in p for p in rep["problems"]) and rep["coverage"]["gaps"] > 0


@test
def apply_ok(mod):
    before = slabs_state()
    rec = run(mod, "APPLY")
    assert marker("P02_FLOOR_APPLY_OK"), S.log[-3:]
    assert S.saves == [WORLD] and not S.maps and not S.content
    assert S.st.ground.p["enabled"] is False and S.st.ground.p["floor_height_cm"] == 0.0
    assert not any(c.name.startswith(("StructureGround", "StructureForestage", "StructureStageFront")) for c in S.st.comps)
    assert slabs_state() == before, "slabs untouched: no move, no rescale, walnut kept"
    assert rec["state"] == "applied" and os.path.isdir(rec["backup"])
    assert os.path.exists(os.path.join(rec["backup"], "L_InfinityStage_V1VerticalSlice.umap"))
    assert all(m.startswith("P02_FLOOR_") and "run=P02FLOOR-" in m for m in S.log)


@test
def apply_ok_with_stale_cached_bounds(mod):     # the 01:47 false alarm: cached Bounds all-zero after rebuild -> PASSES now
    S.flags["stale_cached_bounds"] = True
    run(mod, "APPLY")
    assert marker("P02_FLOOR_APPLY_OK"), S.log[-3:]


@test
def control_cached_bounds_would_false_alarm(mod):   # proves the stale fixture bites: the old cached-only read fails
    S.flags["stale_cached_bounds"] = True

    def cached_only(u, comp, pts=None):
        o, e, _ = u.SystemLibrary.get_component_bounds(comp)
        return (o.x, o.y, o.z), (e.x, e.y, e.z)
    mod.comp_bounds = cached_only
    expect_fail(mod, "APPLY", "LAYERS_WINGS_OR_SLABS_CHANGED")
    nothing_saved()


@test
def stale_bounds_still_catch_real_drift(mod):   # instance transforms see a real 3 cm gridiron move
    S.flags["stale_cached_bounds"] = True
    S.flags["gridiron_drift"] = True
    expect_fail(mod, "APPLY", "StructureGridiron")
    nothing_saved()


@test
def stale_bounds_still_catch_blanked_layer(mod):  # 01:47 suspicion, real version: Fixtures blanked -> refuses
    S.flags["stale_cached_bounds"] = True
    S.flags["fixtures_blank"] = True
    expect_fail(mod, "APPLY", "StructureFixtures")
    nothing_saved()


@test
def apply_needs_confirm(mod):
    expect_fail(mod, "APPLY", "CONFIRM_MISSING", confirm=False)
    nothing_saved()


@test
def apply_refuses_straighten_record(mod):
    straighten_record()
    expect_fail(mod, "APPLY", "STRAIGHTEN_RECORD_ACTIVE")
    assert S.st.ground.p["enabled"]
    nothing_saved()
    S.log.clear()
    rep = run(mod, "DRY")
    assert any("STRAIGHTEN_RECORD_ACTIVE" in b for b in rep["live_blockers"]) and marker("P02_FLOOR_DRY_REFUSED")


@test
def revert_refuses_straighten_record(mod):
    run(mod, "APPLY")
    straighten_record()
    S.saves.clear()
    expect_fail(mod, "REVERT", "STRAIGHTEN_RECORD_ACTIVE")
    assert S.st.ground.p["enabled"] is False
    nothing_saved()


@test
def apply_refuses_pie(mod):
    S.pie = True
    expect_fail(mod, "APPLY", "PIE_ACTIVE")
    nothing_saved()


@test
def apply_refuses_dirty(mod):
    S.content.add("/Game/Other")
    expect_fail(mod, "APPLY", "DIRTY_BEFORE")
    assert S.st.ground.p["enabled"]


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
    open(os.path.join(S.repo, "Saved", "CodexConductor", "p02_floor_record.json"), "w").write("{}")
    expect_fail(mod, "APPLY", "RECORD_EXISTS")
    assert S.st.ground.p["enabled"]


@test
def apply_refuses_two_structures(mod):
    S.actors.append(InfinityStageStructureActor())
    expect_fail(mod, "APPLY", "STRUCTURE_COUNT")


@test
def apply_refuses_missing_slab(mod):
    S.actors.remove(S.slabs["Passage 02 - Floor Far"])
    expect_fail(mod, "APPLY", "LABEL_COUNTS")


@test
def apply_refuses_unlevel_route(mod):
    S.route_tilt = 2.0
    expect_fail(mod, "APPLY", "route not level")


@test
def apply_refuses_not_walnut(mod):              # walnut state is asserted, never re-set
    S.slabs["Passage 02 - Floor Right"].smc.over[0] = _Asset(DARKWET)
    expect_fail(mod, "APPLY", "not walnut")
    assert S.slabs["Passage 02 - Floor Right"].smc.over[0].get_path_name() == DARKWET
    nothing_saved()


@test
def apply_refuses_slab_off_height(mod):          # slabs are not raised by this tool
    S.slabs["Passage 02 - Floor Left"].loc[2] = -5.5
    expect_fail(mod, "APPLY", "does not move slabs")
    assert S.slabs["Passage 02 - Floor Left"].loc[2] == -5.5


@test
def apply_refuses_boards_already_off(mod):
    S.st.ground.p["enabled"] = False
    S.st.comps = S.st._build()
    expect_fail(mod, "APPLY", "BOARDS_ALREADY_OFF")


@test
def apply_ground_readback(mod):
    S.flags["ground_set_ignored"] = True
    expect_fail(mod, "APPLY", "GROUND_READBACK")
    nothing_saved()
    assert any("NOTHING SAVED" in l for l in S.log)


@test
def apply_floor_height_must_be_kept(mod):
    S.flags["ground_height_drift"] = True
    expect_fail(mod, "APPLY", "GROUND_READBACK")
    nothing_saved()


@test
def apply_materialize_fails(mod):
    S.flags["materialize_fails"] = True
    expect_fail(mod, "APPLY", "MATERIALIZE_FAILED")
    nothing_saved()


@test
def apply_not_current(mod):
    S.flags["not_current"] = True
    expect_fail(mod, "APPLY", "NOT_CURRENT")
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
def apply_slab_moved_by_materialize(mod):
    S.flags["materialize_moves_slab"] = True
    expect_fail(mod, "APPLY", "Floor Far transform")
    nothing_saved()


@test
def apply_slab_rematerialled_by_materialize(mod):
    S.flags["materialize_rematerials_slab"] = True
    expect_fail(mod, "APPLY", "Floor Left materials")
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
def apply_post_save_ground_readback(mod):
    S.flags["post_save_ground_on"] = True
    expect_fail(mod, "APPLY", "POST_SAVE_GROUND_READBACK")


@test
def revert_exact(mod):
    before = slabs_state()
    g0 = dict(S.st.ground.p)
    names0 = sorted(c.name.rsplit("_", 1)[0] for c in S.st.comps)
    run(mod, "APPLY")
    S.log.clear()
    S.saves.clear()
    run(mod, "REVERT")
    assert marker("P02_FLOOR_REVERT_OK"), S.log[-3:]
    assert S.st.ground.p == g0 and sorted(c.name.rsplit("_", 1)[0] for c in S.st.comps) == names0
    assert slabs_state() == before and S.saves == [WORLD]
    here = os.path.join(S.repo, "Saved", "CodexConductor")
    assert not os.path.exists(os.path.join(here, "p02_floor_record.json"))
    assert any(n.startswith("p02_floor_record.reverted-") for n in os.listdir(here))


@test
def revert_exact_with_stale_cached_bounds(mod):
    run(mod, "APPLY")
    S.flags["stale_cached_bounds"] = True
    S.log.clear()
    run(mod, "REVERT")
    assert marker("P02_FLOOR_REVERT_OK"), S.log[-3:]


@test
def revert_needs_record(mod):
    expect_fail(mod, "REVERT", "NO_RECORD")


@test
def revert_needs_confirm(mod):
    run(mod, "APPLY")
    expect_fail(mod, "REVERT", "CONFIRM_MISSING", confirm=False)


@test
def revert_refuses_applying_record(mod):
    p = os.path.join(S.repo, "Saved", "CodexConductor", "p02_floor_record.json")
    json.dump({"state": "applying"}, open(p, "w"))
    expect_fail(mod, "REVERT", "RECORD_STATE")


@test
def revert_refuses_moved_slab(mod):
    run(mod, "APPLY")
    S.slabs["Passage 02 - Floor Near"].loc[0] += 10.0
    expect_fail(mod, "REVERT", "NOT_APPLIED_STATE")


@test
def revert_refuses_boards_on(mod):
    run(mod, "APPLY")
    S.st.ground.p["enabled"] = True
    expect_fail(mod, "REVERT", "boards are on")


@test
def revert_layers_not_restored(mod):
    run(mod, "APPLY")
    S.flags["gridiron_drift"] = True
    S.saves.clear()
    expect_fail(mod, "REVERT", "LAYERS_NOT_RESTORED")
    nothing_saved()


@test
def revert_ground_readback(mod):
    run(mod, "APPLY")
    S.flags["ground_set_ignored"] = True
    S.saves.clear()
    expect_fail(mod, "REVERT", "GROUND_READBACK")
    nothing_saved()


@test
def unknown_mode(mod):
    expect_fail(mod, "WIPE", "UNKNOWN_MODE")


def main():
    passed, failed = 0, []
    for fn in TESTS:
        tmp = tempfile.mkdtemp(prefix="p02floor_")
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
        print("P02_FLOOR_HARNESS_FAIL|passed=%d|failed=%d|%s" % (passed, len(failed), [n for n, _ in failed]))
        return 1
    print("P02_FLOOR_HARNESS_PASS|tests=%d" % passed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
