"""Offline harness for girders_v3_import.py and girders_v3_apply.py (plain Python, no editor). Run:
    python Saved/CodexConductor/Girders_20261007/test_girders_v3.py
A fake `unreal` models the import (Interchange task, strays, LOD splits, bounds, tris, UV0 via a mesh description,
slots, Nanite) and the Structure actor (Gridiron/Underpass/Portal/Fixtures/Ground structs; a re-fit that rebuilds the
gridiron/column/knee instances with FitMeshToTimber scales, and recomputes hanging lines from GridTop = H + 1.5 D).
Every positive test has a negative twin: a gate that cannot fail is not a gate.
Prints GIRDERSV3_HARNESS_PASS|tests=N or GIRDERSV3_HARNESS_FAIL; exit code 0 = pass.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Show/DA_Show"
MESH = "/Game/InfinityStage/RigAtmos/Underpass/Meshes/"
MI = "/Game/InfinityStage/RigAtmos/Underpass/Materials/MI_UP_Steel_Green"
TIMBER = "/Game/Timber/SM_Timber"
CUBE = "/Engine/BasicShapes/Cube"
V1 = {"SM_UP_LacedColumn": (500, 60, 40), "SM_UP_PlateGirder": (100, 40, 90), "SM_UP_KneeBracket": (120, 10, 120)}
V3 = {"SM_UP_LacedColumn_v3": (1880, 60, 40), "SM_UP_PlateGirder_v3": (100, 40, 90), "SM_UP_KneeBracket_v3": (120, 20, 120)}
TRIS = {"SM_UP_LacedColumn_v3": 4376, "SM_UP_PlateGirder_v3": 116, "SM_UP_KneeBracket_v3": 360}
LABELS = [f"Infinity Stage - Structure {i:02d}" for i in range(1, 7)]


# ============================================================================ fake unreal
class V:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Box:
    def __init__(self, size):
        self.min, self.max = V(*[-s / 2 for s in size]), V(*[s / 2 for s in size])


class Xf:
    def __init__(self, t, s=(1, 1, 1)):
        self.translation, self.scale3d = V(*t), V(*s)


class Struct:
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
        if S.inject.get("slot_setter_lies") and k == "material_interface":
            return
        self._p[k] = v


class Pkg:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]

    def __str__(self):
        return f"<Object '{self.path}' (0x0) Class 'Package'>"


class Asset(Pkg):
    def __deepcopy__(self, memo):
        return self


def polys_for(size, flip=False):
    """Vertical quads on the +-Y faces with UE V running DOWN (v = 1 - z/size) unless flipped."""
    out = []
    zs = (-size[2] / 2, size[2] / 2)
    for y in (-size[1] / 2, size[1] / 2):
        pts = [(-size[0] / 2, y, zs[0]), (size[0] / 2, y, zs[0]), (size[0] / 2, y, zs[1])]
        out.append([(p, (p[0] / 100.0, (p[2] / size[2] + 0.5) if flip else (0.5 - p[2] / size[2]))) for p in pts])
    out.append([((-1, -1, 0), (0, 0)), ((1, -1, 0), (1, 0)), ((1, 1, 0), (1, 1))])  # horizontal: ignored
    return out


class FakeMesh(Asset):
    def __init__(self, path, size, tris=100, lods=1, nslots=1, flip=False, nanite=True):
        super().__init__(path)
        self.size, self.tris, self.lods, self.flip = size, tris, lods, flip
        self.slots = [Struct(material_slot_name="MAT_Steel", material_interface=None) for _ in range(nslots)]
        self.nanite = Struct(enabled=nanite)

    def get_bounding_box(self):
        return Box(self.size)

    def get_num_lods(self):
        return self.lods

    def get_num_triangles(self, lod):
        return self.tris

    def modify(self):
        S.content_dirty.add(self.path)

    def get_static_mesh_description(self, lod):
        return FakeDesc(polys_for(self.size, self.flip))

    def get_editor_property(self, k):
        if k == "static_materials":
            return [copy.deepcopy(s) for s in self.slots]
        if k == "nanite_settings":
            return copy.deepcopy(self.nanite)
        raise AttributeError(k)

    def set_editor_property(self, k, v):
        if k == "nanite_settings":
            if not S.inject.get("nanite_sticks"):
                self.nanite = v
        elif k == "static_materials":
            self.slots = [copy.deepcopy(s) for s in v]
        else:
            raise AttributeError(k)
        S.content_dirty.add(self.path)


class FakeDesc:
    def __init__(self, polys):
        self.polys = polys
        self.flat = [(pi, vi) for pi, p in enumerate(polys) for vi in range(len(p))]

    def get_polygon_count(self):
        return len(self.polys)

    def get_polygon_vertex_instances(self, pid):
        return [i for i, (pi, _) in enumerate(self.flat) if pi == pid]

    def get_vertex_instance_vertex(self, vi):
        return vi

    def get_vertex_position(self, v):
        pi, k = self.flat[v]
        return V(*self.polys[pi][k][0])

    def get_vertex_instance_uv(self, vi, ch):
        pi, k = self.flat[vi]
        u, v = self.polys[pi][k][1]
        return types.SimpleNamespace(x=u, y=v)


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
    """N stations 500 apart; TOP housings hung 5 cm under the Phase A band (top 1100), plus low lamps."""

    def __init__(self, label, n=8, portal=False, pinned=True, v1_state=True):
        super().__init__(label)
        self.n, self.inject = n, {}
        a = S.assets
        self.gridiron = Struct(beam_mesh=a[MESH + "SM_UP_PlateGirder"] if v1_state else a[CUBE], material=a[MI],
                               beam_width_cm=40.0 if v1_state else 26.0, beam_depth_cm=90.0 if v1_state else 34.0,
                               height_cm=1150.0, enabled=True, section_variation=0.0, twist_degrees=0.0,
                               cross_beam_every=1)
        self.underpass = Struct(column_mesh=a[MESH + "SM_UP_LacedColumn"], knee_mesh=a[MESH + "SM_UP_KneeBracket"],
                                column_width_cm=60.0, column_depth_cm=40.0, enabled=True, columns=True, knees=True,
                                column_material=a[MI], knee_material=a[MI], column_outset_cm=60.0,
                                deck_height_cm=2000.0, pier_height_cm=120.0, pier_size_cm=140.0, knee_size_cm=120.0)
        self.portal = Struct(enabled=portal, extend_gridiron=True, portal_mesh=a[TIMBER] if (portal and pinned) else None,
                             portal_material=None)
        self.fixtures = Struct(max_drop_cm=900.0, body_size_cm=V(45, 32, 32))
        self.ground = Struct(floor_height_cm=0.0)
        self.body_h = 32.0
        # (x, y, housing top): TOP lamps at 1100 (5 cm under the 90 band), low lamps at top 500
        self.housings = [(i * 500.0, s * 360.0, 1100.0) for i in range(n) for s in (-1, 1)] + \
                        [(i * 500.0, 300.0, 500.0) for i in range(0, n, 2)]
        self.current = True
        self._build()

    def _build(self):
        g, u = self.gridiron._p, self.underpass._p
        H, D, W = g["height_cm"], g["beam_depth_cm"], g["beam_width_cm"]
        bm = g["beam_mesh"]
        if self.inject.get("section_bad"):
            W = 40.0  # a build that ignores the width (the measured gate must catch it)
        bs = bm.size
        grid = []
        for i in range(self.n):
            grid.append(Xf((i * 500.0, 0.0, H), (1490.0 / bs[0], W / bs[1], D / bs[2])))
            if i + 1 < self.n:
                grid += [Xf((i * 500.0 + 250.0, s * 745.0, H + D), (500.0 / bs[0], W / bs[1], D / bs[2])) for s in (-1, 1)]
        col_h = u["deck_height_cm"] - self.ground._p["floor_height_cm"] - u["pier_height_cm"]
        cm, km = u["column_mesh"], u["knee_mesh"]
        cols, knees = [], []
        for i in range(self.n):
            if i % 2 and i != self.n - 1:
                continue
            for s in (-1, 1):
                cols.append(Xf((i * 500.0, s * 805.0, 1060.0),
                               (col_h / cm.size[0], u["column_width_cm"] / cm.size[1], u["column_depth_cm"] / cm.size[2])))
                knees += [Xf((i * 500.0, s * 805.0, 1940.0), (1.0, 1.0, 1.0))] * (1 if i in (0, self.n - 1) else 2)
        lines, bodies = [], []
        grid_top = H + 1.5 * D
        for x, y, top in self.housings:
            z = top - self.body_h / 2
            bodies.append(Xf((x, y, z)))
            drop = grid_top - top
            if 1.0 <= drop <= self.fixtures._p["max_drop_cm"]:
                lines.append(Xf((x, y, top + drop / 2), (drop / 100.0, 0.03, 0.03)))
        cube = S.assets[CUBE]
        mat_change = self.inject.get("material_change")
        self.comps = [ISM("InfinityStage.Structure.Gridiron", bm, g["material"], grid),
                      ISM("InfinityStage.Structure.Underpass.Columns", cm, cube if mat_change else u["column_material"], cols),
                      ISM("InfinityStage.Structure.Underpass.Knees", km, u["knee_material"], knees),
                      ISM("InfinityStage.Structure.Fixtures", cube, None, bodies)]
        if lines:
            self.comps.append(ISM("InfinityStage.Structure.Lines", cube, None, lines))
        p = self.portal._p
        if p["enabled"]:
            pm = bm if (self.inject.get("portal_follows_grid") or not p["portal_mesh"]) else p["portal_mesh"]
            self.comps.append(ISM("InfinityStage.Structure.Portal", pm, None, [Xf((-250, 0, 0))] * 7, "StructurePortal_0"))
        self.c = {"station_count": self.n, "cross_beam_count": self.n, "rail_segment_count": 2 * (self.n - 1),
                  "board_count": 1000, "slot_count": 2 * self.n, "groove_piece_count": 6 * self.n, "cloth_count": 0,
                  "portal_piece_count": 50 if p["enabled"] else 0, "fixture_body_count": len(bodies),
                  "hanging_line_count": len(lines) + self.inject.get("line_delta", 0),
                  "underpass_column_count": len(cols) + self.inject.get("column_delta", 0),
                  "underpass_pier_count": len(cols), "underpass_knee_count": len(knees),
                  "underpass_deck_count": self.n - 1, "underpass_catwalk_count": 0, "underpass_tube_count": 40,
                  "underpass_tube_light_count": 8, "underpass_fence_panel_count": 30,
                  "underpass_fence_overlay_count": 9}
        self.current = not self.inject.get("not_current", False)
        if self.inject.get("dirty_show_on_build"):
            S.content_dirty.add(SHOW)

    def modify(self):
        S.events.append(("modify", self.label, sorted(os.listdir(S.here))))
        S.map_dirty = True

    def get_editor_property(self, k):
        if k in ("gridiron", "underpass", "portal", "fixtures", "ground"):
            return copy.deepcopy(getattr(self, k))
        if k == "managed_components":
            return list(self.comps)
        if k == "grid_half_width_cm":
            return 745.0
        return self.c[k]

    def set_editor_property(self, k, v):
        assert k in ("gridiron", "underpass"), k
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


def make_fake(repo, here):
    S.repo, S.here = repo, here
    S.content_dirty, S.map_dirty, S.logs, S.events, S.inject = set(), False, [], [], {}
    S.pie, S.save_ok, S.saved = False, True, []
    S.assets = {CUBE: FakeMesh(CUBE, (100, 100, 100)), MI: Asset(MI), TIMBER: FakeMesh(TIMBER, (100, 30, 30))}
    for n, size in V1.items():
        m = FakeMesh(MESH + n, size, nanite=False)
        m.slots = [Struct(material_slot_name="MAT_Steel", material_interface=S.assets[MI])]
        S.assets[MESH + n] = m
    S.actors = []
    u = types.ModuleType("unreal")
    u._GIRDERS_FAKE = True
    u.Actor, u.InfinityStageStructureActor, u.StaticMesh = Actor, Structure, FakeMesh
    u.PolygonID = lambda i: i

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

    class World:
        def get_path_name(self):
            return WORLD + ".L_InfinityStage_V1VerticalSlice"

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
            S.saved.append(WORLD)
            return True

    u.UnrealEditorSubsystem, u.LevelEditorSubsystem = UnrealEditorSubsystem, LevelEditorSubsystem
    u.get_editor_subsystem = lambda cls: cls()

    class EditorLoadingAndSavingUtils:
        @staticmethod
        def get_dirty_content_packages():
            return [Pkg(p) for p in sorted(S.content_dirty)]

        @staticmethod
        def get_dirty_map_packages():
            return [Pkg(WORLD)] if S.map_dirty else []

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
            S.saved.append(p)
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
                name = t.p["destination_name"]
                path = t.p["destination_path"] + "/" + name
                spec = S.inject.get("spec", {}).get(name, {})
                S.assets[path] = FakeMesh(path, spec.get("size", V3[name]), tris=spec.get("tris", TRIS[name]),
                                          lods=spec.get("lods", 1), nslots=spec.get("nslots", 1),
                                          flip=spec.get("flip", False))
                S.content_dirty.add(path)
                for extra in spec.get("extra", []):
                    S.assets[t.p["destination_path"] + "/" + extra] = Asset(t.p["destination_path"] + "/" + extra)
                    S.content_dirty.add(t.p["destination_path"] + "/" + extra)

    class AssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            return Tools()

    u.AssetToolsHelpers = AssetToolsHelpers
    return u


# ============================================================================ plumbing
def load(tmp, tool):
    repo = os.path.join(tmp, "repo")
    if os.path.exists(repo):
        shutil.rmtree(repo)
    here = os.path.join(tmp, "work")
    if os.path.exists(here):
        shutil.rmtree(here)
    os.makedirs(os.path.join(here, "FBX"))
    for f in ("build_manifest.json", "harness_result.json"):
        shutil.copy2(os.path.join(HERE, f), here)
    for n in V3:
        shutil.copy2(os.path.join(HERE, "FBX", n + ".fbx"), os.path.join(here, "FBX"))
    lvl = os.path.join(repo, "Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
    os.makedirs(os.path.dirname(lvl))
    with open(lvl, "wb") as fh:
        fh.write(b"fake umap " * 100)
    u = make_fake(repo, here)
    sys.modules["unreal"] = u
    spec = importlib.util.spec_from_file_location("gv3_" + tool, os.path.join(HERE, tool + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.HERE = here
    return mod


def args(name, payload):
    with open(os.path.join(S.here, name), "w") as fh:
        json.dump(payload, fh)


def markers(prefix):
    return [m for _, m in S.logs if m.startswith(prefix)]


def expect_fail(fn, needle):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        assert needle in str(exc), f"failed for the wrong reason: {exc}"
        return str(exc)
    raise AssertionError(f"expected failure containing {needle!r}")


def add_v3_assets():
    for n, size in V3.items():
        m = FakeMesh(MESH + n, size, tris=TRIS[n], nanite=False)
        m.slots = [Struct(material_slot_name="MAT_Steel", material_interface=S.assets[MI])]
        S.assets[MESH + n] = m
    with open(os.path.join(S.here, "girders_v3_import_last.json"), "w") as fh:
        json.dump({"status": "PASS"}, fh)


def six(**kw):
    S.actors = [Structure(l, portal=(l.endswith("01")), **kw) for l in LABELS]
    return {a.label: a for a in S.actors}


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# ============================================================================ import tests
@test
def imp_no_autorun(tmp):
    load(tmp, "girders_v3_import")
    assert not S.logs, "importing the tool under the fake must not run it"


@test
def imp_expected_rows_gate(tmp):
    m = load(tmp, "girders_v3_import")
    man = json.load(open(os.path.join(HERE, "build_manifest.json")))
    har = json.load(open(os.path.join(HERE, "harness_result.json")))
    rows = m.expected_rows(man, har)
    assert rows["SM_UP_LacedColumn_v3"]["bounds_cm"] == [1880.0, 60.0, 40.0] and rows["SM_UP_LacedColumn_v3"]["tris"] == 4376
    bad = copy.deepcopy(har)
    bad["negatives_failed_as_expected"] = False
    expect_fail(lambda: m.expected_rows(man, bad), "not PASS")
    bad = copy.deepcopy(har)
    bad["v3"]["SM_UP_KneeBracket_v3"]["status"] = "FAIL"
    expect_fail(lambda: m.expected_rows(man, bad), "SM_UP_KneeBracket_v3")


@test
def imp_v_sign_pure(tmp):
    m = load(tmp, "girders_v3_import")
    ok = m.v_sign(polys_for((100, 40, 90)))
    assert ok == {"down": 2, "up": 0, "ok": True}, ok
    flipped = m.v_sign(polys_for((100, 40, 90), flip=True))
    assert flipped["up"] == 2 and not flipped["ok"], flipped
    flat = m.v_sign([polys_for((100, 40, 90))[-1]])
    assert flat["down"] == 0 and not flat["ok"], "no vertical face must not pass"


@test
def imp_dry_ok_and_controls(tmp):
    m = load(tmp, "girders_v3_import")
    m.main()
    assert markers("GIRDERSV3_IMPORT_DRY_OK"), S.logs
    assert not S.content_dirty and not S.map_dirty
    # v1 UV control flipped: the check that reads v1 as V-down must be able to fail
    m = load(tmp, "girders_v3_import")
    S.assets[MESH + "SM_UP_PlateGirder"].flip = True
    expect_fail(m.main, "v1 UV control")
    # target already present
    m = load(tmp, "girders_v3_import")
    S.assets[MESH + "SM_UP_KneeBracket_v3"] = FakeMesh(MESH + "SM_UP_KneeBracket_v3", (120, 20, 120))
    expect_fail(m.main, "existing targets ['SM_UP_KneeBracket_v3']")
    # FBX bytes differ from the manifest
    m = load(tmp, "girders_v3_import")
    with open(os.path.join(S.here, "FBX", "SM_UP_PlateGirder_v3.fbx"), "ab") as fh:
        fh.write(b"x")
    expect_fail(m.main, "sha_ok")


@test
def imp_happy_and_confirm(tmp):
    m = load(tmp, "girders_v3_import")
    args("girders_v3_import_args.json", {"mode": "IMPORT"})
    expect_fail(m.main, "confirm")
    assert not any(p.endswith("_v3") for p in S.assets)
    args("girders_v3_import_args.json", {"mode": "IMPORT", "confirm": "IMPORT GIRDERSV3"})
    m.main()
    assert markers("GIRDERSV3_IMPORT_OK"), S.logs
    for n in V3:
        a = S.assets[MESH + n]
        assert a.slots[0]._p == {"material_slot_name": "MAT_Steel", "material_interface": S.assets[MI]}, a.slots[0]._p
        assert a.nanite._p["enabled"] is False
    assert sorted(S.saved) == sorted(MESH + n for n in V3), S.saved
    assert not S.content_dirty and not S.map_dirty
    last = json.load(open(os.path.join(S.here, "girders_v3_import_last.json")))
    assert last["status"] == "PASS" and set(last["imported"]) == set(V3)


def _import_fails(tmp, inject, needle):
    m = load(tmp, "girders_v3_import")
    S.inject.update(inject)
    args("girders_v3_import_args.json", {"mode": "IMPORT", "confirm": "IMPORT GIRDERSV3"})
    expect_fail(m.main, needle)
    assert not S.saved, f"nothing may be saved: {S.saved}"
    assert not any(p.endswith("_v3") for p in S.assets), "this run's never-saved assets must be deleted"
    assert not S.content_dirty, S.content_dirty
    assert not os.path.exists(os.path.join(S.here, "girders_v3_import_last.json"))


@test
def imp_axis_swap_refused(tmp):
    _import_fails(tmp, {"spec": {"SM_UP_PlateGirder_v3": {"size": (100, 90, 40)}}}, "bounds")


@test
def imp_tris_refused(tmp):
    _import_fails(tmp, {"spec": {"SM_UP_LacedColumn_v3": {"tris": 4375}}}, "tris 4375")


@test
def imp_uv_flip_refused(tmp):
    _import_fails(tmp, {"spec": {"SM_UP_KneeBracket_v3": {"flip": True}}}, "UV0 V not down")


@test
def imp_lod_split_refused(tmp):
    _import_fails(tmp, {"spec": {"SM_UP_LacedColumn_v3": {"lods": 2}}}, "2 LODs")


@test
def imp_slot_count_refused(tmp):
    _import_fails(tmp, {"spec": {"SM_UP_PlateGirder_v3": {"nslots": 2}}}, "2 slots")


@test
def imp_slot_setter_lies_refused(tmp):
    _import_fails(tmp, {"slot_setter_lies": True}, "slots read back")


@test
def imp_nanite_sticks_refused(tmp):
    _import_fails(tmp, {"nanite_sticks": True}, "Nanite still on")


@test
def imp_strays_deleted_then_pass(tmp):
    m = load(tmp, "girders_v3_import")
    S.inject["spec"] = {"SM_UP_PlateGirder_v3": {"extra": ["MAT_Steel"]}}
    args("girders_v3_import_args.json", {"mode": "IMPORT", "confirm": "IMPORT GIRDERSV3"})
    m.main()
    assert MESH + "MAT_Steel" not in S.assets and markers("GIRDERSV3_IMPORT_OK")
    assert "strays=1->0" in markers("GIRDERSV3_IMPORT_OK")[0]


@test
def imp_lod_named_stray_refused(tmp):
    m = load(tmp, "girders_v3_import")
    S.assets[MESH + "SM_UP_Old_LOD1"] = Asset(MESH + "SM_UP_Old_LOD1")  # any *_LOD* asset in the folder refuses
    args("girders_v3_import_args.json", {"mode": "IMPORT", "confirm": "IMPORT GIRDERSV3"})
    expect_fail(m.main, "LOD-split assets present")
    assert not S.saved


@test
def imp_batches_partial_then_pass(tmp):
    m = load(tmp, "girders_v3_import")
    args("girders_v3_import_args.json", {"mode": "IMPORT", "confirm": "IMPORT GIRDERSV3", "modules": ["SM_UP_PlateGirder_v3"]})
    m.main()
    assert json.load(open(os.path.join(S.here, "girders_v3_import_last.json")))["status"] == "PARTIAL"
    args("girders_v3_import_args.json", {"mode": "IMPORT", "confirm": "IMPORT GIRDERSV3",
                                         "modules": ["SM_UP_LacedColumn_v3", "SM_UP_KneeBracket_v3"]})
    m.main()
    assert json.load(open(os.path.join(S.here, "girders_v3_import_last.json")))["status"] == "PASS"
    args("girders_v3_import_args.json", {"mode": "IMPORT", "confirm": "IMPORT GIRDERSV3", "modules": ["SM_UP_Nope"]})
    expect_fail(m.main, "subset")


# ============================================================================ apply tests
@test
def app_no_autorun(tmp):
    load(tmp, "girders_v3_apply")
    assert not S.logs


@test
def app_pure_window_clearance_gap(tmp):
    m = load(tmp, "girders_v3_apply")
    lo, hi, d = m.line_window(10, [800.0, 700.0, 200.0], [], 900.0, 90.0, 180.0)
    assert d["grid_top_shift_cm"] == 135.0 and (lo, hi) == (9, 9), (lo, hi, d)  # 800+135 > 900: lost
    lo, hi, _ = m.line_window(10, [700.0], [-20.0], 900.0, 90.0, 180.0)
    assert (lo, hi) == (10, 11), "a housing above the old grid top may gain a line"
    # TOP housing top 1100 (centre 1084): clear of the 90 band, inside the 180 band
    assert m.clearance([(0, 360, 1084.0, 1150.0)], 90.0, 180.0, 32.0) == [[0, 360, 1084]]
    assert m.clearance([(0, 300, 484.0, 1150.0)], 90.0, 180.0, 32.0) == [], "low lamp must not hit"
    assert m.clearance([(0, 360, 1150.0, 1150.0)], 90.0, 180.0, 32.0) == [], "already inside the old band: not new"
    mv = m.geometry_moves({"underpass.column_outset_cm": 60.0, "underpass.deck_height_cm": 2000.0,
                           "underpass.pier_height_cm": 120.0, "gridiron.height_cm": 1150.0},
                          {"enabled": True, "extend_gridiron": True}, 0.0)
    assert mv["cross_girder_to_column_gap_cm"] == [30.0, 0.0] and mv["deck_half_span_grows_cm"] == 30.0
    assert mv["knee_shift_along_route_cm"] == 20.0 and mv["portal_carried_rails_section_cm"] == [[40.0, 90.0], [80.0, 180.0]]
    assert abs(mv["column_mesh_x_scale"][1] - 1.0) < 1e-9 and abs(mv["column_mesh_x_scale"][0] - 3.76) < 1e-9


@test
def app_dry_ok(tmp):
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    six()
    m.main()
    ok = markers("GIRDERSV3_DRY_OK")
    assert ok and "refused=[]" in ok[0], S.logs
    rows = markers("GIRDERSV3_DRY_ROW")
    assert len(rows) == 6 and all("clearance_hits=16" in r for r in rows), rows
    assert all("gap=[30.0, 0.0]" in r for r in rows)
    assert not S.map_dirty and not S.content_dirty and not S.events


@test
def app_dry_lists_refusals(tmp):
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    S.actors = [Structure(l, v1_state=not l.endswith("03")) for l in LABELS]
    m.main()
    assert "refused=['Infinity Stage - Structure 03']" in markers("GIRDERSV3_DRY_OK")[0]


def _apply(m, **extra):
    args("girders_v3_apply_args.json", {"mode": "APPLY", "confirm": "APPLY GIRDERSV3", **extra})
    return m.main()


@test
def app_happy(tmp):
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    st = six()
    rec = _apply(m)
    assert rec["status"] == "APPLIED" and markers("GIRDERSV3_APPLY_OK"), S.logs
    for s in st.values():
        g, u = s.gridiron._p, s.underpass._p
        assert g["beam_mesh"].path.endswith("_v3") and (g["beam_width_cm"], g["beam_depth_cm"]) == (80.0, 180.0)
        assert u["column_mesh"].path.endswith("_v3") and u["knee_mesh"].path.endswith("_v3")
        assert (u["column_width_cm"], u["column_depth_cm"]) == (120.0, 80.0)
        assert u["column_material"].path == MI, "materials are not written"
    # originals and the backup BEFORE the first modify
    first = S.events[0][2]
    assert any(f.startswith("girders_v3_originals_") for f in first), first
    assert os.path.isdir(os.path.join(S.repo, "Backups")) and rec["backup"].startswith("Backups/PreGirdersV3-")
    assert not S.map_dirty and S.saved == [WORLD], S.saved
    # low lamps (top 500) lose their line: 785 + 135 > 900 -> lines 20 -> 16 per structure, inside the window
    assert all(rec["after"][l]["hanging_line_count"] == 16 for l in LABELS), rec["after"]
    assert any("hanging_line_count 20 -> 16" in f for f in rec["findings"])
    assert not os.path.exists(os.path.join(S.here, "girders_v3_dry_x.json"))


def _apply_refused(tmp, inject, needle, target=None, unsaved=True):
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    st = six()
    for s in ([st[target]] if target else st.values()):
        s.inject.update(inject)
    expect_fail(lambda: _apply(m), needle)
    assert not S.saved, "nothing may be saved"
    for s in st.values():  # originals restored in memory
        assert s.gridiron._p["beam_depth_cm"] == 90.0 and s.underpass._p["column_width_cm"] == 60.0
        assert s.gridiron._p["beam_mesh"].path == MESH + "SM_UP_PlateGirder"
    recs = [f for f in os.listdir(S.here) if f.startswith("girders_v3_originals_")]
    if unsaved:
        assert recs and json.load(open(os.path.join(S.here, recs[0])))["status"] == "REFUSED_UNSAVED"
    return m


@test
def app_materialize_false_refused(tmp):
    _apply_refused(tmp, {"materialize_false": True}, "MaterializeStructure returned false", LABELS[3])


@test
def app_section_measured_refused(tmp):
    _apply_refused(tmp, {"section_bad": True}, "gridiron: section off", LABELS[4])


@test
def app_count_drift_refused(tmp):
    _apply_refused(tmp, {"column_delta": 1}, "underpass_column_count", LABELS[1])


@test
def app_material_change_refused(tmp):
    _apply_refused(tmp, {"material_change": True}, "material", LABELS[2])


@test
def app_portal_follows_grid_refused(tmp):
    _apply_refused(tmp, {"portal_follows_grid": True}, "portal renders", LABELS[0])


@test
def app_show_dirtied_refused(tmp):
    _apply_refused(tmp, {"dirty_show_on_build": True}, "only the level may be dirty", LABELS[5])


@test
def app_line_pin_refused(tmp):
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    six()
    expect_fail(lambda: _apply(m, expected_lines={LABELS[0]: 20}), "pinned expected_lines")
    assert not S.saved


@test
def app_before_write_refusals(tmp):
    # unpinned portal: refused before ANY write (no originals, no backup, level clean)
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    S.actors = [Structure(l, portal=l.endswith("01"), pinned=False) for l in LABELS]
    expect_fail(lambda: _apply(m), "portal enabled but portal_mesh is None")
    assert not S.events and not S.map_dirty and not os.path.exists(os.path.join(S.repo, "Backups"))
    # from-state differs
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    S.actors = [Structure(l, v1_state=not l.endswith("06")) for l in LABELS]
    expect_fail(lambda: _apply(m), "gridiron.beam_depth_cm: 34.0 != 90.0")
    assert not S.events
    # import record missing
    m = load(tmp, "girders_v3_apply")
    six()
    expect_fail(lambda: _apply(m), "no PASS girders_v3_import_last.json")
    # confirm missing, PIE, dirty at start
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    six()
    args("girders_v3_apply_args.json", {"mode": "APPLY"})
    expect_fail(m.main, "confirm")
    S.pie = True
    expect_fail(lambda: _apply(m), "PIE active")
    S.pie = False
    S.content_dirty.add(SHOW)
    expect_fail(lambda: _apply(m), "editor dirty at start")
    assert not S.events


@test
def app_save_fails(tmp):
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    six()
    S.save_ok = False
    expect_fail(lambda: _apply(m), "level save failed")


@test
def app_revert_exact_and_drift(tmp):
    m = load(tmp, "girders_v3_apply")
    add_v3_assets()
    st = six()
    rec = _apply(m)
    before = {l: (copy.deepcopy(s.c)) for l, s in st.items()}
    name = f"girders_v3_originals_{rec['run']}.json"
    # drift after apply: refuse before any write
    st[LABELS[2]].underpass._p["column_width_cm"] = 100.0
    n_events = len(S.events)
    args("girders_v3_apply_args.json", {"mode": "REVERT", "confirm": "REVERT GIRDERSV3", "revert_record": name})
    expect_fail(m.main, "no longer at the applied state")
    assert len(S.events) == n_events and not S.map_dirty
    st[LABELS[2]].underpass._p["column_width_cm"] = 120.0
    m.main()
    assert markers("GIRDERSV3_REVERT_OK"), S.logs
    for s in st.values():
        assert s.gridiron._p["beam_mesh"].path == MESH + "SM_UP_PlateGirder"
        assert (s.gridiron._p["beam_width_cm"], s.gridiron._p["beam_depth_cm"]) == (40.0, 90.0)
        assert (s.underpass._p["column_width_cm"], s.underpass._p["column_depth_cm"]) == (60.0, 40.0)
        assert s.c["hanging_line_count"] == 20
    assert json.load(open(os.path.join(S.here, name)))["status"] == "REVERTED"
    # a second REVERT of the same record is refused
    expect_fail(m.main, "status REVERTED")
    assert before  # (kept for debugging)


# ============================================================================ runner
def main():
    passed, failed = 0, []
    for fn in TESTS:
        tmp = tempfile.mkdtemp(prefix="gv3_")
        try:
            fn(tmp)
            passed += 1
        except Exception:  # noqa: BLE001
            failed.append((fn.__name__, traceback.format_exc()))
        finally:
            sys.modules.pop("unreal", None)
            shutil.rmtree(tmp, ignore_errors=True)
    for name, tb in failed:
        print(f"FAIL {name}\n{tb}")
    if failed:
        print(f"GIRDERSV3_HARNESS_FAIL|passed={passed}|failed={len(failed)}")
        return 1
    print(f"GIRDERSV3_HARNESS_PASS|tests={passed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
