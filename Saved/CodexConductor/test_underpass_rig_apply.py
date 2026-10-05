"""Offline harness for underpass_rig_apply.py (plain Python, no editor). Run:
    python Saved/CodexConductor/test_underpass_rig_apply.py
A fake `unreal` module models the Structure actor closely enough to exercise every gate:
the census, the hanging-line window (lines really are recomputed from GridTop = H + 1.5 D),
the P01/portal refusals, the prototype gate, originals-before-mutation ordering, the level
backup, dirty-scope checks, save failure, revert, and the FBX import gates (strays, LODs,
bounds/axis, sha, existing targets). Every positive test has a negative twin: a gate that
cannot fail is not a gate.
Exit code 0 = all pass. Prints UNDERPASS_RIG_HARNESS_PASS|tests=N or ..._FAIL.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
TOOL = os.path.join(HERE, "underpass_rig_apply.py")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CUBE = "/Engine/BasicShapes/Cube"


# ============================================================================ fake unreal
class V:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Box:
    def __init__(self, mn, mx):
        self.min, self.max = V(*mn), V(*mx)


class Xf:
    def __init__(self, t, s=(1, 1, 1)):
        self.translation, self.scale3d = V(*t), V(*s)


class Struct:
    """UE struct: get_editor_property of a struct returns a COPY (as UE Python does)."""

    def __init__(self, **kw):
        self.__dict__["_p"] = dict(kw)

    def get_editor_property(self, k):
        if k not in self._p:
            raise AttributeError(k)
        v = self._p[k]
        return copy.deepcopy(v) if isinstance(v, Struct) else v

    def set_editor_property(self, k, v):
        if k not in self._p:
            raise AttributeError(k)
        self._p[k] = v


class World:
    def get_path_name(self):
        return WORLD + ".L_InfinityStage_V1VerticalSlice"

    def __str__(self):  # UE prints packages as <Object '/Game/..' (0x..) Class 'Package'>
        return f"<Object '{WORLD}' (0x0) Class 'Package'>"


class Asset:
    def __init__(self, path, kind="asset"):
        self.path, self.kind = path, kind

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]

    def get_material(self, i):
        return getattr(self, "own_material", None)

    def __str__(self):
        return f"<Object '{self.path}' (0x0) Class 'Package'>"

    def __deepcopy__(self, memo):
        return self  # assets are shared objects, never copied with a struct


class FakeMesh(Asset):
    def __init__(self, path, size=(100, 100, 100), lods=1, slots=1, nanite=True):
        super().__init__(path, "mesh")
        self.size, self.lods, self.slots = size, lods, slots
        self.own_material = Asset(path + "_OwnMaterial")  # what the mesh renders with no override
        self.nanite = Struct(enabled=nanite)

    def get_bounding_box(self):
        return Box([-s / 2 for s in self.size], [s / 2 for s in self.size])

    def get_num_lods(self):
        return self.lods

    def modify(self):
        S.content_dirty.add(self.path)

    def get_editor_property(self, k):
        if k == "static_materials":
            return [object()] * self.slots
        if k == "nanite_settings":
            return copy.deepcopy(self.nanite)
        raise AttributeError(k)

    def set_editor_property(self, k, v):
        if k == "nanite_settings":
            self.nanite = v
            S.content_dirty.add(self.path)
            return
        raise AttributeError(k)


class ISM:
    def __init__(self, tag, mesh, material, xfs, name="StructureX"):
        self.tags, self.mesh, self.material, self.xfs, self.name = [tag], mesh, material, xfs, name

    def get_name(self):
        return self.name

    def get_editor_property(self, k):
        return {"component_tags": self.tags, "static_mesh": self.mesh}[k]

    def get_material(self, i):
        return self.material

    def get_instance_count(self):
        return len(self.xfs)

    def get_instance_transform(self, i, world):
        return self.xfs[i]


class Actor:
    def __init__(self, label):
        self.label = label

    def get_actor_label(self):
        return self.label


class Structure(Actor):
    """Model: N stations 500 apart at z=0; housings given by their OLD drop below the grid top."""

    def __init__(self, label, n=10, portal=False, housing_drops=(800.0, 850.0, -20.0), body_h=32.0,
                 lateral_out=(), portal_props=True):
        super().__init__(label)
        self.n = n
        self.gridiron = Struct(beam_mesh=S.assets[CUBE], material=None, beam_width_cm=26.0, beam_depth_cm=34.0,
                               section_variation=0.06, twist_degrees=0.6, cast_shadow=True, height_cm=1150.0,
                               enabled=True, overhang_cm=220.0, cross_beam_every=1)
        # portal_props: the held C++ patch (Portal.PortalMesh/PortalMaterial) is built
        self.portal = Struct(enabled=portal, portal_mesh=None, portal_material=None) if portal_props             else Struct(enabled=portal)
        self.fixtures = Struct(max_drop_cm=900.0, body_size_cm=V(45, 32, body_h))
        self.body_h = body_h
        # housing tops fixed in world space, from the drops measured against the ORIGINAL grid
        top0 = 1150.0 + 1.5 * 34.0
        self.housings = [(i * 500.0, 100.0, top0 - d - body_h / 2) for i, d in enumerate(housing_drops)]
        self.lateral_out = set(lateral_out)
        self.inject = {}
        self.current = True
        self._build()

    def _build(self):
        g = self.gridiron._p
        H, D = g["height_cm"], g["beam_depth_cm"]
        grid = []
        for i in range(self.n):
            grid.append(Xf((i * 500.0, 0.0, H)))
            if i + 1 < self.n:
                grid += [Xf((i * 500.0 + 250.0, -745.0, H + D)), Xf((i * 500.0 + 250.0, 745.0, H + D))]
        lines, bodies = [], []
        for k, (x, y, z) in enumerate(self.housings):
            bodies.append(Xf((x, y, z)))
            drop = (H + 1.5 * D) - (z + self.body_h / 2)
            if k not in self.lateral_out and 1.0 <= drop <= self.fixtures._p["max_drop_cm"]:
                lines.append(Xf((x, y, z + drop / 2), (drop / 100.0, 0.03, 0.03)))
        cube = S.assets[CUBE]
        mat = g["material"]
        self.comps = [ISM("InfinityStage.Structure.Gridiron", g["beam_mesh"], mat or cube.get_material(0), grid),
                      ISM("InfinityStage.Structure.Fixtures", cube, None, bodies)]
        if lines:
            self.comps.append(ISM("InfinityStage.Structure.Lines", cube, None, lines))
        pp = self.portal._p
        if pp["enabled"]:
            # cpp after the patch: own slot if set, else the gridiron's, independently per slot;
            # inject "portal_ignores_pin" models a build that does not honour the slots
            honour = not self.inject.get("portal_ignores_pin")
            pmesh = (honour and pp.get("portal_mesh")) or g["beam_mesh"]
            pmat = (honour and pp.get("portal_material")) or g["material"] or pmesh.get_material(0)
            self.comps.append(ISM("InfinityStage.Structure.Portal", pmesh, pmat, [Xf((-250.0, 0.0, 0.0))] * 7,
                                  name="StructurePortal_0"))
            self.comps.append(ISM("InfinityStage.Structure.Portal", cube, None, [Xf((-250.0, 0.0, 0.0))] * 5,
                                  name="StructurePortalLines_0"))
        self.c = {"station_count": self.n, "cross_beam_count": self.n, "rail_segment_count": 2 * (self.n - 1),
                  "board_count": 1000 + self.inject.get("board_delta", 0), "slot_count": 2 * self.n,
                  "groove_piece_count": 6 * self.n, "cloth_count": 0,
                  "portal_piece_count": 50 if self.portal._p["enabled"] else 0,
                  "fixture_body_count": len(bodies), "hanging_line_count": len(lines) + self.inject.get("line_delta", 0)}
        self.current = not self.inject.get("not_current", False)

    def modify(self):
        S.events.append(("modify", self.label, sorted(os.listdir(S.saved))))
        S.map_dirty = True

    def get_editor_property(self, k):
        if k == "gridiron":
            return copy.deepcopy(self.gridiron)
        if k == "portal":
            return copy.deepcopy(self.portal)
        if k == "fixtures":
            return copy.deepcopy(self.fixtures)
        if k == "managed_components":
            return list(self.comps)
        if k == "grid_half_width_cm":
            return 745.0
        return self.c[k]

    def set_editor_property(self, k, v):
        assert k in ("gridiron", "portal"), k
        setattr(self, k, v)

    def materialize_structure(self):
        if self.inject.get("materialize_false"):
            return False
        self._build()
        S.map_dirty = True
        return True

    def is_structure_current(self):
        return self.current


class _State:
    pass


S = _State()


def make_fake(repo):
    S.repo = repo
    S.saved = os.path.join(repo, "Saved", "CodexConductor")
    S.content_dirty, S.map_dirty, S.logs, S.events = set(), False, [], []
    S.pie, S.save_ok, S.import_mode = False, True, {}
    S.assets = {CUBE: FakeMesh(CUBE)}
    S.assets[CUBE + "_OwnMaterial"] = S.assets[CUBE].own_material
    S.actors = []
    u = types.ModuleType("unreal")
    u._UNDERPASS_FAKE = True
    u.Actor = Actor
    u.InfinityStageStructureActor = Structure
    u.StaticMesh = FakeMesh

    class Paths:
        @staticmethod
        def project_dir():
            return repo

        @staticmethod
        def convert_relative_path_to_full(p):
            return p

    u.Paths = Paths
    u.log = lambda m: S.logs.append(("log", m))
    u.log_error = lambda m: S.logs.append(("error", m))

    class UnrealEditorSubsystem:
        def get_editor_world(self):
            return World()

        def get_game_world(self):
            return object() if S.pie else None

    class LevelEditorSubsystem:
        def save_current_level(self):
            if not S.save_ok:
                return False
            S.map_dirty = False
            return True

    u.UnrealEditorSubsystem, u.LevelEditorSubsystem = UnrealEditorSubsystem, LevelEditorSubsystem
    u.get_editor_subsystem = lambda cls: cls()

    class EditorLoadingAndSavingUtils:
        @staticmethod
        def get_dirty_content_packages():
            return [Asset(p) for p in sorted(S.content_dirty)]

        @staticmethod
        def get_dirty_map_packages():
            return [World()] if S.map_dirty else []

    u.EditorLoadingAndSavingUtils = EditorLoadingAndSavingUtils

    class GameplayStatics:
        @staticmethod
        def get_all_actors_of_class(world, cls):
            return list(S.actors)

    u.GameplayStatics = GameplayStatics

    class EditorAssetLibrary:
        @staticmethod
        def load_asset(p):
            return S.assets.get(p.split(".")[0])

        @staticmethod
        def does_asset_exist(p):
            return p in S.assets

        @staticmethod
        def does_directory_exist(p):
            return any(a.startswith(p + "/") for a in S.assets)

        @staticmethod
        def list_assets(p, recursive, include_folder):
            return [a + "." + a.rsplit("/", 1)[-1] for a in S.assets if a.startswith(p + "/")]

        @staticmethod
        def save_asset(p, only_if_is_dirty=False):
            S.content_dirty.discard(p)
            return True

        @staticmethod
        def delete_asset(p):
            S.assets.pop(p, None)
            S.content_dirty.discard(p)
            return True

    u.EditorAssetLibrary = EditorAssetLibrary

    class Props:
        def __init__(self):
            self.p = {}

        def set_editor_property(self, k, v):
            self.p[k] = v

        def get_editor_property(self, k):
            if k == "static_mesh_import_data":
                return self.p.setdefault(k, Props())
            return self.p[k]

    u.FbxImportUI = Props
    u.AssetImportTask = Props

    class Tools:
        def import_asset_tasks(self, tasks):
            for t in tasks:
                stem = os.path.splitext(os.path.basename(t.p["filename"]))[0]
                path = t.p["destination_path"] + "/" + stem
                size = S.import_mode.get("size", {}).get(stem) or S.bounds[stem]
                S.assets[path] = FakeMesh(path, size=size, lods=S.import_mode.get("lods", 1))
                S.content_dirty.add(path)
                if S.import_mode.get("strays"):
                    stray = t.p["destination_path"] + "/M_" + stem + "_stray"
                    S.assets[stray] = Asset(stray)
                    S.content_dirty.add(stray)

    class AssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            return Tools()

    u.AssetToolsHelpers = AssetToolsHelpers
    return u


# ============================================================================ harness plumbing
def fresh(tmp, mode, structures=None, kit=True, import_ok=True):
    repo = os.path.join(tmp, "repo")
    if os.path.exists(repo):
        shutil.rmtree(repo)
    os.makedirs(os.path.join(repo, "Saved", "CodexConductor"))
    lvl = os.path.join(repo, "Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
    os.makedirs(os.path.dirname(lvl))
    with open(lvl, "wb") as fh:
        fh.write(b"fake umap " * 100)
    # the real gated kit, copied so the sha checks run against real bytes
    src = os.path.join(REPO, "DerivedAssets", "UnderpassKit")
    shutil.copytree(src, os.path.join(repo, "DerivedAssets", "UnderpassKit"))
    u = make_fake(repo)
    S.bounds = {r["name"]: r["bounds_cm"] for r in
                json.load(open(os.path.join(src, "kit_manifest.json"), encoding="utf-8"))["modules"]}
    if kit:
        for p in ("/Game/InfinityStage/RigAtmos/Underpass/Meshes/SM_UP_PlateGirder",
                  "/Game/InfinityStage/RigAtmos/Underpass/Materials/MI_UP_Steel_Green"):
            S.assets[p] = FakeMesh(p, size=(100, 40, 90)) if "SM_" in p else Asset(p)
    if import_ok:
        with open(os.path.join(S.saved, "underpass_kit_import_last.json"), "w") as fh:
            json.dump({"status": "PASS"}, fh)
    S.actors = structures if structures is not None else default_structures()
    write_mode(mode)
    sys.modules["unreal"] = u
    spec = importlib.util.spec_from_file_location("underpass_rig_apply_t", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_mode(mode):
    with open(os.path.join(S.saved, "underpass_rig_mode.json"), "w") as fh:
        json.dump(mode, fh)


def default_structures(p05_portal=False, p02_portal=False):
    return [Structure(f"Infinity Stage - Structure {i:02d}",
                      portal=(i == 1) or (i == 5 and p05_portal) or (i == 2 and p02_portal)) for i in range(1, 7)]


def by(label):
    return next(a for a in S.actors if a.get_actor_label() == label)


def markers(prefix):
    return [m for _, m in S.logs if m.startswith(prefix)]


def expect_fail(fn, needle):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        assert needle in str(exc), f"failed for the wrong reason: {exc}"
        return str(exc)
    raise AssertionError(f"expected failure containing {needle!r}")


P05 = "Infinity Stage - Structure 05"
P01 = "Infinity Stage - Structure 01"
P02 = "Infinity Stage - Structure 02"
TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# ============================================================================ tests
@test
def module_does_not_autorun_under_fake(tmp):
    fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    assert not S.logs and not S.map_dirty, "importing the tool must not run it under the fake"


@test
def pure_refusals(tmp):
    m = fresh(tmp, {"mode": "DRY"})
    # an enabled portal without the patch's properties is refused (+), with them it is pinned (-)
    assert "not built" in m.refusal_for(P01, True, False)
    assert m.refusal_for(P01, True, True) is None, "P01 applies once the portal can be pinned"
    assert "not built" in m.refusal_for(P05, True, False) and m.refusal_for(P05, True, True) is None
    assert m.refusal_for(P05, False, False) is None, "no portal, nothing to protect, patch or not"
    assert m.refusal_for("Passage 05", False, True) is not None


@test
def pure_portal_pin_plan(tmp):
    m = fresh(tmp, {"mode": "DRY"})
    grid = {"beam_mesh": CUBE, "material": None}
    live = {"mesh": CUBE, "material": CUBE + "_OwnMaterial", "slots": 1}
    null = {"enabled": True, "has_own_mesh": True, "portal_mesh": None, "portal_material": None}
    plan, why = m.plan_portal_pin(null, grid, live)
    assert why is None and plan["set"] == {"portal_mesh": CUBE, "portal_material": CUBE + "_OwnMaterial"}, (plan, why)
    assert plan["original"] == {"portal_mesh": None, "portal_material": None}
    # gridiron material set: pin that, not the mesh's own
    plan, _ = m.plan_portal_pin(null, {"beam_mesh": CUBE, "material": "/Game/MI_Timber"},
                                {**live, "material": "/Game/MI_Timber"})
    assert plan["set"]["portal_material"] == "/Game/MI_Timber"
    # multi-slot mesh with a null gridiron material: refused (+); same mesh with a gridiron material: fine (-)
    assert "slots" in m.plan_portal_pin(null, grid, {**live, "slots": 2})[1]
    assert m.plan_portal_pin(null, {"beam_mesh": CUBE, "material": "/Game/MI_Timber"},
                             {**live, "material": "/Game/MI_Timber", "slots": 2})[1] is None
    # slot reads null but the portal renders something else: unreadable pin, refused
    assert "unreadable" in m.plan_portal_pin(null, grid, {**live, "mesh": "/Game/SM_Baroque"})[1]
    # an already-pinned slot is left alone
    pinned = {**null, "portal_mesh": "/Game/SM_Baroque"}
    plan, why = m.plan_portal_pin(pinned, grid, {**live, "mesh": "/Game/SM_Baroque"})
    assert why is None and "portal_mesh" not in plan["set"], plan
    # no portal: no plan to write
    assert m.plan_portal_pin({"enabled": False}, grid, None) == ({"original": None, "set": {}, "expect": None}, None)


@test
def pure_line_window(tmp):
    m = fresh(tmp, {"mode": "DRY"})
    lo, hi, d = m.line_window(2, [800.0, 850.0], [800.0, 850.0, -20.0], 900.0, 34.0, 90.0)
    assert (lo, hi) == (1, 2) and d["lost"] == 1 and d["possible_gains"] == 1, (lo, hi, d)
    lo, hi, _ = m.line_window(2, [800.0, 850.0], [800.0, 850.0, -20.0], 900.0, 34.0, 34.0)
    assert (lo, hi) == (2, 2), "no depth change must predict no change"


@test
def dry_reports_and_mutates_nothing(tmp):
    m = fresh(tmp, {"mode": "DRY", "structures": [P05]})
    r = m.main()
    assert markers("UNDERPASS_RIG_DRY_OK") and not S.map_dirty and not S.content_dirty
    row = r["structures"][P05]
    assert row["line_window"] == [1, 2] and row["refusal"] is None and row["snapshot_check"] == "ok"
    assert r["structures"][P01]["refusal"] is None, "P01's portal is pinnable once the patch is built"
    assert r["structures"][P01]["portal_pin"]["set"] == {"portal_mesh": CUBE, "portal_material": CUBE + "_OwnMaterial"}
    # -20 cm housing already overlaps the OLD band, so it is not a new hit (negative control)
    assert row["clearance_new_band_housings"] == [], row["clearance_new_band_housings"]
    # a housing 40 cm above the old grid top: clear of the old band, inside the new one
    m = fresh(tmp, {"mode": "DRY", "structures": [P05]},
              structures=[Structure(f"Infinity Stage - Structure {i:02d}", portal=(i == 1),
                                    housing_drops=(800.0, 850.0, -20.0, -40.0)) for i in range(1, 7)])
    row = m.main()["structures"][P05]
    assert row["clearance_new_band_housings"] == [[1500, 100, 1225]], row["clearance_new_band_housings"]
    assert row["line_window"] == [1, 3], row["line_window"]


@test
def dry_refuses_dirty_editor(tmp):
    m = fresh(tmp, {"mode": "DRY", "structures": [P05]})
    S.map_dirty = True
    expect_fail(m.main, "editor dirty at start")


@test
def dry_refuses_pie_and_bench_actors(tmp):
    m = fresh(tmp, {"mode": "DRY", "structures": [P05]})
    S.pie = True
    expect_fail(m.main, "PIE active")
    m = fresh(tmp, {"mode": "DRY", "structures": [P05]})
    S.actors.append(Actor("ZZ_BenchProbe"))
    expect_fail(m.main, "bench actors")


@test
def apply_p05_happy_path(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    rec = m.main()
    s = by(P05)
    g = s.gridiron._p
    assert g["beam_mesh"].path.endswith("SM_UP_PlateGirder") and g["material"].path.endswith("MI_UP_Steel_Green")
    assert (g["beam_width_cm"], g["beam_depth_cm"], g["section_variation"], g["twist_degrees"]) == (40, 90, 0, 0)
    assert not S.map_dirty and markers("UNDERPASS_RIG_APPLY_OK") and rec["status"] == "APPLIED"
    # originals were on disk before the first modify()
    first = next(e for e in S.events if e[0] == "modify")
    assert any(f.startswith("underpass_rig_originals_") for f in first[2]), first
    # backup exists and matches
    bk = os.path.join(S.repo, rec["backup"])
    lvl = os.path.join(S.repo, "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap")
    assert hashlib.sha256(open(bk, "rb").read()).hexdigest() == hashlib.sha256(open(lvl, "rb").read()).hexdigest()
    assert "PreUnderpassP05-" in rec["backup"]
    # other structures untouched
    assert by(P02).gridiron._p["beam_depth_cm"] == 34.0
    # line changed legitimately inside the window: 850 lost, -20 gained -> still 2
    assert rec["after"][P05]["hanging_line_count"] == 2


def _p01_ready(m, extra=None):
    """Let P01 past the prototype gate, so the portal logic itself is what is tested."""
    with open(os.path.join(S.saved, "underpass_rig_applied_index.json"), "w") as fh:
        json.dump({"runs": [{"structures": [P05], "status": "APPLIED"}]}, fh)
    write_mode({"mode": "APPLY", "structures": [P01], "prototype_signed_off": True, **(extra or {})})


def _no_patch_structures():
    return [Structure(f"Infinity Stage - Structure {i:02d}", portal=(i == 1), portal_props=False)
            for i in range(1, 7)]


@test
def apply_refuses_portal_without_patch(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P01]}, structures=_no_patch_structures())
    _p01_ready(m)
    expect_fail(m.main, "not built")
    assert not S.map_dirty and by(P01).gridiron._p["beam_depth_cm"] == 34.0
    assert not [f for f in os.listdir(S.saved) if f.startswith("underpass_rig_originals_")]
    # negative control: same tree, P05 has no portal, so the missing patch does not block it
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]}, structures=_no_patch_structures())
    m.main()
    assert markers("UNDERPASS_RIG_APPLY_OK")


@test
def apply_p01_pins_the_portal_timber_then_revert_unpins(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P01]})
    _p01_ready(m)
    rec = m.main()
    s = by(P01)
    assert s.gridiron._p["beam_mesh"].path.endswith("SM_UP_PlateGirder"), "the gridiron did turn iron"
    pp = s.portal._p
    assert pp["portal_mesh"].path == CUBE and pp["portal_material"].path == CUBE + "_OwnMaterial", pp
    live = m.portal_timber_live(s)
    assert live["mesh"] == CUBE and live["material"] == CUBE + "_OwnMaterial", live
    grid = m.components_with_tag(s, "InfinityStage.Structure.Gridiron")[0]
    assert grid.mesh.path.endswith("SM_UP_PlateGirder") and grid.material.path.endswith("MI_UP_Steel_Green")
    row = rec["structures"][P01]["portal_pin"]
    assert row["original"] == {"portal_mesh": None, "portal_material": None}
    # the pins were in the originals JSON before the first modify()
    first = next(e for e in S.events if e[0] == "modify")
    orig = [f for f in first[2] if f.startswith("underpass_rig_originals_")]
    assert orig, first
    on_disk = json.load(open(os.path.join(S.saved, orig[0]), encoding="utf-8"))
    assert on_disk["structures"][P01]["portal_pin"]["set"]["portal_mesh"] == CUBE
    write_mode({"mode": "REVERT", "revert_record": orig[0]})
    m.main()
    assert s.portal._p["portal_mesh"] is None and s.portal._p["portal_material"] is None, "REVERT unpins to null"
    assert s.gridiron._p["beam_mesh"].path == CUBE and markers("UNDERPASS_RIG_REVERT_OK")
    live = m.portal_timber_live(s)
    assert live["mesh"] == CUBE and live["material"] == CUBE + "_OwnMaterial"


@test
def apply_unpinned_portal_turning_iron_is_caught(tmp):
    # negative control 1: a tool that forgot to pin -> the portal follows the girder -> refused, unsaved
    m = fresh(tmp, {"mode": "APPLY", "structures": [P01]})
    _p01_ready(m)
    real_pin = m._set_portal_pins
    m._set_portal_pins = lambda c, s, values: None
    expect_fail(m.main, "portal timber after the swap")
    s = by(P01)
    assert S.map_dirty and s.gridiron._p["beam_mesh"].path == CUBE, "originals restored, level left dirty"
    m._set_portal_pins = real_pin
    # negative control 2: pinned, but a C++ build that ignores the slots -> also caught
    m = fresh(tmp, {"mode": "APPLY", "structures": [P01]})
    _p01_ready(m)
    by(P01).inject["portal_ignores_pin"] = True
    expect_fail(m.main, "portal timber after the swap")
    assert by(P01).portal._p["portal_mesh"] is None, "refused run unpins in memory too"


@test
def apply_refuses_retired_iron_ack(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05], "portal_iron_ack": [P05]},
              structures=default_structures(p05_portal=True))
    expect_fail(m.main, "portal_iron_ack is retired")
    assert not S.map_dirty
    # control: without the key the same portal-enabled P05 applies, pinned
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05], "portal_iron_ack": []},
              structures=default_structures(p05_portal=True))
    m.main()
    assert markers("UNDERPASS_RIG_APPLY_OK") and by(P05).portal._p["portal_mesh"].path == CUBE


@test
def apply_refuses_multislot_portal_with_null_material(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P01]})
    _p01_ready(m)
    S.assets[CUBE].slots = 2
    expect_fail(m.main, "slots")
    assert not S.map_dirty and not [f for f in os.listdir(S.saved) if f.startswith("underpass_rig_originals_")]


@test
def prototype_gate(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P02]})
    expect_fail(m.main, "APPLY Structure 05 alone first")
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    m.main()
    write_mode({"mode": "APPLY", "structures": [P02]})
    expect_fail(m.main, "prototype_signed_off")
    write_mode({"mode": "APPLY", "structures": [P02, "Infinity Stage - Structure 03"], "prototype_signed_off": True})
    m.main()
    assert len(markers("UNDERPASS_RIG_APPLY_OK")) == 2


@test
def board_drift_refused_then_allowed(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    by(P05).inject["board_delta"] = 3
    expect_fail(m.main, "board_count 1000 -> 1003")
    s = by(P05)
    assert s.gridiron._p["beam_depth_cm"] == 34.0 and s.gridiron._p["beam_mesh"].path == CUBE, "originals restored"
    assert S.map_dirty, "refused run leaves the level dirty for a Don't-Save restart (never reload)"
    rec = json.load(open(os.path.join(S.saved, [f for f in os.listdir(S.saved)
                                               if f.startswith("underpass_rig_originals_")][0])))
    assert rec["status"] == "REFUSED_UNSAVED"
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05], "allow_board_drift": True})
    by(P05).inject["board_delta"] = 3
    rec = m.main()
    assert any("board_count" in f for f in rec["findings"])


@test
def lines_outside_window_refused(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    by(P05).inject["line_delta"] = 5
    expect_fail(m.main, "outside predicted")


@test
def lines_lost_inside_window_accepted(tmp):
    # only the 850 lamp: it legitimately loses its line (850 + 84 > 900); count 1 -> 0, window [0, 0]
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]},
              structures=[Structure(f"Infinity Stage - Structure {i:02d}", portal=(i == 1),
                                    housing_drops=(850.0,)) for i in range(1, 7)])
    rec = m.main()
    assert rec["after"][P05]["hanging_line_count"] == 0 and any("hanging_line_count 1 -> 0" in f for f in rec["findings"])


@test
def not_current_and_materialize_false_refused(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    by(P05).inject["not_current"] = True
    expect_fail(m.main, "IsStructureCurrent")
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    by(P05).current = False
    expect_fail(m.main, "not current before")
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    by(P05).inject["materialize_false"] = True
    expect_fail(m.main, "MaterializeStructure returned false")


@test
def save_failure_is_a_failure(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    S.save_ok = False
    expect_fail(m.main, "level save failed")
    assert not markers("UNDERPASS_RIG_APPLY_OK")


@test
def foreign_dirty_content_blocks_save(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    real = Structure.materialize_structure

    def dirty_other(self):
        S.content_dirty.add("/Game/Someone/Else")
        return real(self)
    Structure.materialize_structure = dirty_other
    try:
        expect_fail(m.main, "dirty scope")
    finally:
        Structure.materialize_structure = real


@test
def unresolved_soft_pointer_blocks_before_mutation(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    s = by(P05)
    s.comps[0].material = Asset("/Game/Some/MI_Real")  # component renders a material the snapshot can't see
    expect_fail(m.main, "not trustworthy")
    assert not S.map_dirty


@test
def missing_kit_or_import_record_refused(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]}, kit=False)
    expect_fail(m.main, "missing")
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]}, import_ok=False)
    expect_fail(m.main, "no PASS kit import record")


@test
def revert_restores(tmp):
    m = fresh(tmp, {"mode": "APPLY", "structures": [P05]})
    rec = m.main()
    name = next(f for f in os.listdir(S.saved) if f.startswith("underpass_rig_originals_"))
    write_mode({"mode": "REVERT", "revert_record": name})
    m.main()
    g = by(P05).gridiron._p
    assert g["beam_mesh"].path == CUBE and g["material"] is None and g["beam_depth_cm"] == 34.0
    assert g["section_variation"] == 0.06 and markers("UNDERPASS_RIG_REVERT_OK") and not S.map_dirty
    assert by(P05).c["hanging_line_count"] == rec["structures"][P05]["before"]["hanging_line_count"]
    expect_fail(m.main, "status REVERTED")  # a second revert of the same record is refused


@test
def import_happy_with_strays(tmp):
    m = fresh(tmp, {"mode": "IMPORT"}, kit=False, import_ok=False)
    S.import_mode = {"strays": True}
    rec = m.main()
    assert len(rec["imported"]) == 7 and len(rec["strays_deleted"]) == 7
    assert not any("_stray" in a for a in S.assets) and not S.content_dirty
    assert all(not S.assets[v["path"]].nanite._p["enabled"] for v in rec["imported"].values())
    assert markers("UNDERPASS_KIT_IMPORT_OK")


@test
def import_gates_fail(tmp):
    m = fresh(tmp, {"mode": "IMPORT"}, kit=False, import_ok=False)
    S.import_mode = {"size": {"SM_UP_PlateGirder": [90.0, 40.0, 100.0]}}  # length on Z: axis wrong
    expect_fail(m.main, "bounds")
    m = fresh(tmp, {"mode": "IMPORT"}, kit=False, import_ok=False)
    S.import_mode = {"lods": 2}
    expect_fail(m.main, "2 LODs")
    m = fresh(tmp, {"mode": "IMPORT"}, kit=True, import_ok=False)
    expect_fail(m.main, "import targets exist")
    m = fresh(tmp, {"mode": "IMPORT"}, kit=False, import_ok=False)
    fbx = os.path.join(S.repo, "DerivedAssets", "UnderpassKit", "FBX", "SM_UP_DeckBay.fbx")
    with open(fbx, "ab") as fh:
        fh.write(b"tamper")
    expect_fail(m.main, "sha256")


def main():
    results = []
    for fn in TESTS:
        tmp = tempfile.mkdtemp(prefix="uprig_")
        try:
            fn(tmp)
            results.append((fn.__name__, "PASS", ""))
        except Exception:  # noqa: BLE001
            results.append((fn.__name__, "FAIL", traceback.format_exc(limit=3)))
        finally:
            sys.modules.pop("unreal", None)
            shutil.rmtree(tmp, ignore_errors=True)
    for name, status, err in results:
        print(f"{status}  {name}")
        if err:
            print(err)
    failed = [r for r in results if r[1] != "PASS"]
    print(f"UNDERPASS_RIG_HARNESS_{'FAIL' if failed else 'PASS'}|tests={len(results)}|failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
