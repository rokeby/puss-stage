"""Offline harness for floor_dark_wet_apply.py (plain Python, no editor). Run:
    python Saved/CodexConductor/test_floor_dark_wet_apply.py
A fake `unreal` module models the level as the records describe it (five structures with straight
routes at z 0, boards FloorHeightCm 0 / 5 cm, the four slabs at top -5 trimmed lip->hinge, P02's four
rotated pieces, pit strips, the S4 hangar root / camera / apron, the walnut parent MI) closely enough
to exercise every gate. Every positive test has a negative twin: a gate that cannot fail is not a gate.
Exit 0 = all pass. Prints FLOOR_DW_HARNESS_PASS|tests=N or FLOOR_DW_HARNESS_FAIL.
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
TOOL = os.path.join(HERE, "floor_dark_wet_apply.py")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
CUBE = "/Engine/BasicShapes/Cube"
MI_PATH = "/Game/InfinityStage/RigAtmos/MI_Floor_DarkWet"
PARENT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
WALNUT, OAK = PARENT, "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/M_Oak_Hrrngbn_01_Mat_Inst_Dup"
VERSAILLES = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Versailles_Mat_Dup"
S = None  # the fake world state, rebuilt per test


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


class LinearColor:
    def __init__(self, r=0.0, g=0.0, b=0.0, a=1.0):
        self.r, self.g, self.b, self.a = float(r), float(g), float(b), float(a)


class Name(str):
    pass


class _Box:
    def __init__(self, mn, mx):
        self.min, self.max = Vector(*mn), Vector(*mx)


class _Pkg:
    def __init__(self, p):
        self.p = p

    def __str__(self):
        return f"<Object '{self.p}' (0x0) Class 'Package'>"


class _Asset:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]


class _Mesh(_Asset):
    def get_bounding_box(self):
        return _Box((-50, -50, -50), (50, 50, 50))


class MaterialInstanceConstant(_Asset):
    def __init__(self, path, parent=None, scalars=None, vectors=None, switches=None, names=None):
        super().__init__(path)
        self.parent, self.scalars, self.vectors, self.switches = parent, dict(scalars or {}), dict(vectors or {}), dict(switches or {})
        self.names = names

    def get_editor_property(self, k):
        if k == "parent":
            return self.parent
        raise AttributeError(k)

    def lookup(self, kind, n):
        m = self
        while m is not None:
            d = getattr(m, kind)
            if n in d:
                return d[n]
            m = m.parent
        return None


class MaterialInstanceConstantFactoryNew:
    pass


def _mut(what):
    """Every change to the level or content goes through here."""
    if S.first_change is None:
        S.first_change = {"what": what, "record_existed": os.path.exists(S.record_path),
                          "originals_existed": any(f.startswith("floor_dark_wet_originals_") for f in os.listdir(S.here))}
    S.changes.append(what)
    hook = S.inject.pop("on_first_change", None)
    if hook:
        hook()


class StaticMeshComponent:
    def __init__(self, owner, mesh=None, overrides=None):
        self.owner, self.mesh, self.overrides = owner, mesh, list(overrides or [])
        self.mobility, self.profile, self.catfloor = "STATIC", "BlockAll", "ECR_BLOCK"

    def get_editor_property(self, k):
        if k == "static_mesh":
            return self.mesh
        if k == "override_materials":
            return list(self.overrides)
        if k == "mobility":
            return self.mobility
        raise AttributeError(k)

    def get_world_transform(self):
        o = self.owner
        return _Xf(Vector(*o.loc), Rotator(*o.rot), Vector(*o.scale))

    def get_num_materials(self):
        return 1

    def get_material(self, i):
        return self.overrides[i] if i < len(self.overrides) and self.overrides[i] is not None else S.assets["/Engine/BasicShapeMaterial"]

    def set_material(self, i, m):
        _mut(f"set_material {self.owner.label}")
        S.maps_dirty.add(WORLD)
        while len(self.overrides) <= i:
            self.overrides.append(None)
        self.overrides[i] = m

    def set_static_mesh(self, m):
        _mut("set_static_mesh")
        self.mesh = m
        return True

    def set_mobility(self, m):
        self.mobility = m

    def get_collision_profile_name(self):
        return self.profile

    def set_collision_profile_name(self, n):
        self.profile = n

    def get_collision_response_to_channel(self, ch):
        return self.catfloor

    def set_collision_response_to_channel(self, ch, r):
        self.catfloor = r


class Actor:
    def __init__(self, label, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), bounds=None, tags=()):
        self.label, self.loc, self.rot, self.scale = label, list(map(float, loc)), list(map(float, rot)), list(map(float, scale))
        self._bounds, self.tags, self.parent, self.children, self.folder = bounds, [Name(t) for t in tags], None, [], "Infinity Stage/Floors"

    def get_actor_label(self):
        return self.label

    def set_actor_label(self, l):
        _mut("label")
        self.label = l

    def get_actor_location(self):
        return Vector(*self.loc)

    def get_actor_rotation(self):
        return Rotator(*self.rot)

    def get_actor_scale3d(self):
        return Vector(*self.scale)

    def _dirty(self, what):
        _mut(f"{what} {self.label}")
        S.maps_dirty.add(WORLD)

    def set_actor_location(self, v, sweep, teleport):
        self._dirty("loc")
        self.loc = [v.x, v.y, v.z]

    def set_actor_rotation(self, r, teleport):
        self._dirty("rot")
        self.rot = [r.roll, r.pitch, r.yaw]

    def set_actor_scale3d(self, v):
        self._dirty("scale")
        self.scale = [v.x, v.y, v.z]

    def modify(self):
        S.maps_dirty.add(WORLD)

    def get_actor_bounds(self, only_colliding):
        if self._bounds:
            (x0, y0, z0), (x1, y1, z1) = self._bounds
            return Vector((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), Vector((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)
        return Vector(*self.loc), Vector(0, 0, 0)

    def get_attach_parent_actor(self):
        return self.parent

    def get_attached_actors(self):
        return list(self.children)

    def get_editor_property(self, k):
        if k == "tags":
            return list(self.tags)
        raise AttributeError(k)

    def set_editor_property(self, k, v):
        if k == "tags":
            self.tags = list(v)
            return
        raise AttributeError(k)

    def get_folder_path(self):
        return self.folder

    def set_folder_path(self, f):
        self.folder = f


class StaticMeshActor(Actor):
    def __init__(self, label, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), mesh=None, mats=(), tags=()):
        super().__init__(label, loc, rot, scale, tags=tags)
        self.static_mesh_component = StaticMeshComponent(self, mesh, list(mats))

    def get_actor_bounds(self, only_colliding):
        if self.static_mesh_component.mesh is None:
            return Vector(*self.loc), Vector(0, 0, 0)
        c, s = math.cos(math.radians(self.rot[2])), math.sin(math.radians(self.rot[2]))
        hx, hy, hz = 50 * self.scale[0], 50 * self.scale[1], 50 * self.scale[2]
        ex, ey = abs(c) * hx + abs(s) * hy, abs(s) * hx + abs(c) * hy
        return Vector(*self.loc), Vector(ex, ey, hz)


class CameraActor(Actor):
    pass


class PostProcessVolume(Actor):
    pass


class _Struct:
    def __init__(self, **kw):
        self._p = dict(kw)

    def get_editor_property(self, k):
        if k not in self._p:
            raise AttributeError(k)
        return self._p[k]


class _Route:
    def __init__(self, origin, length, zfn=None):
        self.origin, self.length, self.zfn = origin, length, zfn

    def get_spline_length(self):
        return self.length

    def get_transform_at_distance_along_spline(self, d, space, use_scale):
        z = self.origin[2] + (self.zfn(d) if self.zfn else 0.0)
        return _Xf(Vector(self.origin[0] + d, self.origin[1], z), Rotator(0, 0, 0), Vector(1, 1, 1))


class InfinityStageStructureActor(Actor):
    def __init__(self, label, origin, length, floor_height=0.0, thick=5.0, forestage=150.0):
        super().__init__(label, origin, bounds=((origin[0] - 300, origin[1] - 1300, -265), (origin[0] + length, origin[1] + 1300, 2209)))
        self.route = _Route(origin, length)
        self.ground = _Struct(floor_height_cm=floor_height, board_thickness_cm=thick, enabled=True)
        self.portal = _Struct(forestage_depth_cm=forestage)

    def get_editor_property(self, k):
        if k == "passage":
            return _Struct(route=self.route)
        if k == "ground":
            return self.ground
        if k == "portal":
            return self.portal
        return super().get_editor_property(k)


class _World:
    def get_path_name(self):
        return WORLD + ".L_InfinityStage_V1VerticalSlice"


def _editor_subsystem(cls):
    return cls()


class UnrealEditorSubsystem:
    def get_game_world(self):
        return object() if S.pie else None

    def get_editor_world(self):
        return _World()


class EditorActorSubsystem:
    def get_all_level_actors(self):
        return [a for a in S.actors if not a.label.startswith("ZZ_")]

    def spawn_actor_from_class(self, cls, loc, rot):
        _mut("spawn")
        S.maps_dirty.add(WORLD)
        a = cls("StaticMeshActor", (loc.x, loc.y, loc.z), (rot.roll, rot.pitch, rot.yaw))
        S.actors.append(a)
        return a

    def destroy_actor(self, a):
        _mut(f"destroy {a.label}")
        S.maps_dirty.add(WORLD)
        S.actors.remove(a)
        return True


class LevelEditorSubsystem:
    def save_current_level(self):
        if S.inject.get("level_save_fails"):
            return False
        S.saves.append(WORLD)
        with open(S.umap, "ab") as fh:
            fh.write(b"saved")
        S.maps_dirty.discard(WORLD)
        return True


class EditorLoadingAndSavingUtils:
    @staticmethod
    def get_dirty_content_packages():
        return [_Pkg(p) for p in sorted(S.content_dirty)]

    @staticmethod
    def get_dirty_map_packages():
        return [_Pkg(p) for p in sorted(S.maps_dirty)]


class LevelSequenceEditorBlueprintLibrary:
    @staticmethod
    def get_current_level_sequence():
        return object() if S.sequencer else None


class GameplayStatics:
    @staticmethod
    def get_all_actors_of_class(world, cls):
        return list(S.actors)


class EditorAssetLibrary:
    @staticmethod
    def does_asset_exist(p):
        return p in S.assets

    @staticmethod
    def save_asset(p, only_if_is_dirty=True):
        S.saves.append(p)
        rel = p[len("/Game/"):].split("/")
        f = os.path.join(S.repo, "Content", *rel) + ".uasset"
        os.makedirs(os.path.dirname(f), exist_ok=True)
        open(f, "wb").write(b"mi")
        S.content_dirty.discard(p)
        return True


class _AssetTools:
    def create_asset(self, name, folder, cls, factory):
        _mut("create_asset")
        p = f"{folder}/{name}"
        mi = MaterialInstanceConstant(p)
        S.assets[p] = mi
        S.content_dirty.add(p)
        return mi


class AssetToolsHelpers:
    @staticmethod
    def get_asset_tools():
        return _AssetTools()


def load_asset(p):
    return S.assets.get(p.split(".")[0]) if p else None


class MaterialEditingLibrary:
    @staticmethod
    def get_scalar_parameter_names(m):
        return [Name(n) for n in m.names["scalar"]]

    @staticmethod
    def get_vector_parameter_names(m):
        return [Name(n) for n in m.names["vector"]]

    @staticmethod
    def get_static_switch_parameter_names(m):
        return [Name(n) for n in m.names["switch"]]

    @staticmethod
    def get_material_instance_scalar_parameter_value(mi, n, association=None):
        return mi.lookup("scalars", n) or 0.0

    @staticmethod
    def get_material_instance_vector_parameter_value(mi, n, association=None):
        v = mi.lookup("vectors", n) or (0, 0, 0, 0)
        return LinearColor(*v)

    @staticmethod
    def get_material_instance_static_switch_parameter_value(mi, n, association=None):
        return bool(mi.lookup("switches", n))

    @staticmethod
    def _set(mi, kind, n, v):
        if S.inject.get("setter_noop_true"):
            return True
        getattr(mi, kind)[n] = v
        S.content_dirty.add(mi.path)
        return not S.inject.get("setter_lies_false")

    @staticmethod
    def set_material_instance_scalar_parameter_value(mi, n, v, association=None):
        return MaterialEditingLibrary._set(mi, "scalars", n, float(v))

    @staticmethod
    def set_material_instance_vector_parameter_value(mi, n, v, association=None):
        return MaterialEditingLibrary._set(mi, "vectors", n, (v.r, v.g, v.b, v.a))

    @staticmethod
    def set_material_instance_static_switch_parameter_value(mi, n, v, association=None):
        return MaterialEditingLibrary._set(mi, "switches", n, bool(v))

    @staticmethod
    def set_material_instance_parent(mi, p):
        mi.parent = p
        S.content_dirty.add(mi.path)
        return True

    @staticmethod
    def update_material_instance(mi):
        return None


class Paths:
    @staticmethod
    def project_dir():
        return S.repo

    @staticmethod
    def project_saved_dir():
        return os.path.join(S.repo, "Saved")

    @staticmethod
    def convert_relative_path_to_full(p):
        return p


def get_editor_subsystem(cls):
    return cls()


def make_fake():
    m = types.ModuleType("unreal")
    for k, v in dict(globals()).items():
        if isinstance(v, type) or k in ("load_asset", "get_editor_subsystem"):
            setattr(m, k, v)
    m.Actor = Actor
    m.SplineCoordinateSpace = types.SimpleNamespace(WORLD="WORLD")
    m.CollisionChannel = types.SimpleNamespace(ECC_GAME_TRACE_CHANNEL1="CatFloor")
    m.log = lambda msg: S.logs.append(("log", msg))
    m.log_error = lambda msg: S.logs.append(("error", msg))
    m.log_warning = lambda msg: S.logs.append(("warn", msg))
    m._FLOOR_DW_FAKE = True
    return m


# ============================================================================ the fake level
ORIGINS = {"01": (0.0, 0.0, 0.0), "03": (0.0, 160000.0, 0.0), "04": (0.0, 240000.0, 0.0),
           "05": (0.0, 320000.0, 0.0), "06": (0.0, 400000.0, 0.0)}
LENGTHS = {"01": 28784.0, "03": 10922.0, "04": 10668.47, "05": 46590.9, "06": 27640.3}
SLAB_SPECS = {"P01": ("Passage 01 - Opening Floor", "01", (-150.0, 29284.01), (-10000.0, 10000.0), WALNUT),
              "P03": ("Passage 03 - Floor", "03", (-150.0, 11421.97), (-27490.0, 26070.0), OAK),
              "P05": ("Passage 05 - Floor (oak)", "05", (-150.0, 47090.90), (-9690.02, 10309.98), OAK),
              "P06": ("Passage 01 - Opening Floor2", "06", (-150.0, 28140.28), (-10514.21, 9485.79), VERSAILLES)}


def slab(label, n, x, y, mat, top=-5.0, thick=1.0, yaw=0.0):
    o = ORIGINS[n]
    loc = ((x[0] + x[1]) / 2 + o[0], (y[0] + y[1]) / 2 + o[1], top - thick / 2)
    return StaticMeshActor(label, loc, (0, 0, yaw), ((x[1] - x[0]) / 100, (y[1] - y[0]) / 100, thick / 100),
                           S.assets[CUBE], [S.assets[mat]])


def fresh(tmp, **kw):
    global S
    S = types.SimpleNamespace(actors=[], assets={}, content_dirty=set(), maps_dirty=set(), saves=[], logs=[], changes=[],
                              first_change=None, inject={}, pie=False, sequencer=False)
    S.repo = tmp
    S.here = os.path.join(tmp, "Saved", "CodexConductor")
    S.record_path = os.path.join(S.here, "floor_dark_wet_record.json")
    os.makedirs(S.here, exist_ok=True)
    os.makedirs(os.path.join(tmp, "Saved", "CodexStructure"), exist_ok=True)
    json.dump({"hangar": {"apron": 500.0}}, open(os.path.join(tmp, "Saved", "CodexStructure", "hangar_s4_plan.json"), "w"))
    S.umap = os.path.join(tmp, "Content", "InfinityStage", "Dev", "Maps", "L_InfinityStage_V1VerticalSlice.umap")
    os.makedirs(os.path.dirname(S.umap), exist_ok=True)
    open(S.umap, "wb").write(b"level-v1")
    S.assets[CUBE] = _Mesh(CUBE)
    S.assets["/Engine/BasicShapeMaterial"] = _Asset("/Engine/BasicShapeMaterial")
    S.assets[OAK] = _Asset(OAK)
    S.assets[VERSAILLES] = _Asset(VERSAILLES)
    S.assets[PARENT] = MaterialInstanceConstant(
        PARENT, scalars={"Roughness_Low": 0.3, "Roughness_High": 0.7, "Roughness_Add_Grunge": 0.1},
        vectors={f"Color_Wood_0{i}": (0.5, 0.4, 0.3, 1.0) for i in range(1, 5)}, switches={"Grunge ON": False},
        names={"scalar": ["Roughness_Low", "Roughness_High", "Roughness_Add_Grunge", "Roughness_Contrast"],
               "vector": [f"Color_Wood_0{i}" for i in range(1, 5)] + ["Color_Grunge"], "switch": ["Grunge ON"]})
    for n, o in ORIGINS.items():
        S.actors.append(InfinityStageStructureActor(f"Infinity Stage - Structure {n}", o, LENGTHS[n],
                                                    floor_height=kw.get("floor_height", 0.0)))
    for key, (label, n, x, y, mat) in SLAB_SPECS.items():
        S.actors.append(slab(label, n, x, y, mat))
    for i, lab in enumerate(("Near", "Left", "Right", "Far")):
        a = StaticMeshActor(f"Passage 02 - Floor {lab}", (6000.0 + 9000 * i, 95000.0 - 9000 * i, -5.5), (0, 0, -43.5725),
                            (270.0, 410.0, 0.01), S.assets[CUBE], [S.assets[WALNUT]])
        S.actors.append(a)
    S.actors.append(slab("Passage 01 - Opening Floor - Pit Strip Left", "01", (29284.01, 69149.96), (-10000.0, -1175.0), WALNUT))
    S.actors.append(slab("Passage 03 - Floor - S3 Pit Strip Far", "03", (11421.97, 45144.0), (-1175.0, 1175.0), OAK))
    hinge = 10668.47 + 500.0
    S.actors.append(Actor("S4 Hangar Root", (hinge, 240000.0, 0.0)))
    S.actors.append(CameraActor("Scene 4 — External Sound — Entry Handoff Camera", (10668.47, 240000.0, 180.0)))
    S.actors.append(Actor("S4 Hangar Apron", (10918.47, 240000.0, -10.0),
                          bounds=((10668.47, 239000.0, -20.0), (hinge, 241000.0, 0.0))))
    S.actors.append(Actor("Wing standing on the boards", (5000, 400, 300), bounds=((4990, 300, 0.0), (5010, 500, 600))))
    S.actors.append(Actor("Lamp in the house", (-1000, 0, -100), bounds=((-1010, -10, -119), (-990, 10, -80))))
    return S


def load_tool():
    sys.modules["unreal"] = make_fake()
    spec = importlib.util.spec_from_file_location("floor_dark_wet_apply_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def by(label):
    hits = [a for a in S.actors if a.label == label]
    assert len(hits) == 1, (label, len(hits))
    return hits[0]


def top_of(a):
    return a.loc[2] + 50 * a.scale[2]


def run(mod, mode, ack=None):
    try:
        return True, mod.main(mode, ack), ""
    except mod.FloorError as exc:
        return False, None, str(exc)


def snapshot():
    return {a.label: (list(a.loc), list(a.rot), list(a.scale),
                      [m.path if m else None for m in a.static_mesh_component.overrides] if isinstance(a, StaticMeshActor) else None)
            for a in S.actors}


def logs_with(s):
    return [m for _, m in S.logs if s in m]


# ============================================================================ tests
TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def dry_clean_ok(mod):
    ok, rep, err = run(mod, "DRY")
    assert ok, err
    assert logs_with("FLOOR_DW_DRY_OK|") and "apply_ready=1" in logs_with("FLOOR_DW_DRY_OK|")[0]
    assert not S.changes and not S.saves and not os.path.exists(S.record_path)
    for k in ("P01", "P03", "P05", "P06"):
        assert abs(rep["slabs"][k]["target_top"] - 0.5) < 1e-9 and abs(rep["slabs"][k]["raise_cm"] - 5.5) < 1e-6
    q = rep["p04"]
    assert abs(q["x"][0] + 150) < 1e-6 and abs(q["x"][1] - 11168.47) < 1e-6 and abs(q["top"] - 0.5) < 1e-9
    assert rep["structures"]["P01"]["board_bottom"] == -5.0
    assert any(f.startswith("floor_dark_wet_dry_") for f in os.listdir(S.here))


@test
def dry_top_drift_refuses(mod):
    a = by("Passage 01 - Opening Floor")
    a.loc[2] += 1.0            # top -4.0: outside +-0.5
    ok, _, err = run(mod, "DRY")
    assert not ok and "P01: top -4.00" in err and not S.changes


@test
def dry_top_small_drift_passes(mod):           # twin
    by("Passage 01 - Opening Floor").loc[2] += 0.4
    ok, rep, err = run(mod, "DRY")
    assert ok, err
    assert abs(rep["slabs"]["P01"]["raise_cm"] - 5.1) < 1e-6


@test
def dry_extent_drift_refuses(mod):
    a = by("Passage 05 - Floor (oak)")
    a.scale[0] += 0.04          # far end +2 cm, near end -2 cm
    ok, _, err = run(mod, "DRY")
    assert not ok and "P05: xmax" in err


@test
def dry_extent_within_tol_passes(mod):         # twin
    by("Passage 05 - Floor (oak)").scale[0] += 0.012
    ok, _, err = run(mod, "DRY")
    assert ok, err


@test
def dry_duplicate_label_refuses(mod):
    S.actors.append(slab("Passage 03 - Floor", "03", (-150.0, 11421.97), (-27490.0, 26070.0), OAK))
    ok, _, err = run(mod, "DRY")
    assert not ok and "matches 2 actors" in err


@test
def board_top_follows_floor_height(mod):
    fresh(S.repo, floor_height=2.0)
    ok, rep, err = run(mod, "DRY")
    assert ok, err
    assert abs(rep["slabs"]["P03"]["target_top"] - 2.5) < 1e-9 and abs(rep["p04"]["top"] - 2.5) < 1e-9


@test
def unlevel_route_refuses(mod):                # twin
    by("Infinity Stage - Structure 05").route.zfn = lambda d: d / 10000.0
    ok, _, err = run(mod, "DRY")
    assert not ok and "route not level" in err


@test
def apply_ok_saves_only_level_and_mi(mod):
    before = snapshot()
    ok, rec, err = run(mod, "APPLY")
    assert ok, err
    assert S.saves == [MI_PATH, WORLD], S.saves
    assert S.first_change["record_existed"] and S.first_change["originals_existed"], S.first_change
    for k, (label, *_r) in SLAB_SPECS.items():
        a = by(label)
        assert abs(top_of(a) - 0.5) < 1e-6 and a.static_mesh_component.overrides[0].path == MI_PATH
        assert a.loc[:2] == before[label][0][:2] and a.scale == before[label][2]
    p4 = by("Passage 04 - Floor (dark wet)")
    assert "RigAtmos.FloorDarkWet" in p4.tags and abs(top_of(p4) - 0.5) < 1e-6
    assert abs((p4.loc[0] - 50 * p4.scale[0]) + 150) < 1e-6 and abs((p4.loc[0] + 50 * p4.scale[0]) - 11168.47) < 1e-6
    for lab in [l for l in before if l.startswith("Passage 02")]:
        assert snapshot()[lab] == before[lab]
    for lab in ("Passage 01 - Opening Floor - Pit Strip Left", "Passage 03 - Floor - S3 Pit Strip Far"):
        assert snapshot()[lab] == before[lab]
    mi = S.assets[MI_PATH]
    assert mi.parent is S.assets[PARENT] and mi.scalars["Roughness_Low"] == 0.02 and mi.switches == {"Grunge ON": True}
    assert abs(mi.vectors["Color_Wood_01"][0] - 0.175) < 1e-9 and mi.vectors["Color_Wood_01"][3] == 1.0
    r = json.load(open(S.record_path))
    assert r["state"] == "applied" and r["mi_created"] is True
    assert os.path.exists(os.path.join(r["backup"], "L_InfinityStage_V1VerticalSlice.umap"))
    assert logs_with("FLOOR_DW_APPLY_OK|") and not S.content_dirty and not S.maps_dirty


@test
def originals_written_before_any_change(mod):  # twin: originals write fails -> nothing changed
    orig = mod.Ctx.write_json

    def boom(self, path, payload):
        if "floor_dark_wet_record" in path:
            self.fail("simulated originals write failure")
        return orig(self, path, payload)
    mod.Ctx.write_json = boom
    try:
        ok, _, err = run(mod, "APPLY")
    finally:
        mod.Ctx.write_json = orig
    assert not ok and "simulated" in err and not S.changes and not S.saves and MI_PATH not in S.assets


@test
def p02_change_mid_apply_is_caught(mod):
    def nudge():
        by("Passage 02 - Floor Left").loc[0] += 0.5
    S.inject["on_first_change"] = nudge
    ok, _, err = run(mod, "APPLY")
    assert not ok and "P02 changed: Passage 02 - Floor Left" in err and not S.saves


@test
def foreign_dirty_mid_apply_refuses_save(mod):
    def dirty_other():
        S.content_dirty.add("/Game/Someone/Else")
    S.inject["on_first_change"] = dirty_other
    ok, _, err = run(mod, "APPLY")
    assert not ok and "content dirty" in err and not S.saves


@test
def dirty_at_start_refuses(mod):               # twin, before any change
    S.maps_dirty.add(WORLD)
    ok, _, err = run(mod, "APPLY")
    assert not ok and "editor dirty" in err and not S.changes


@test
def pie_refuses(mod):
    S.pie = True
    for mode in ("DRY", "APPLY", "REVERT"):
        ok, _, err = run(mod, mode)
        assert not ok and "PIE" in err
    assert not S.changes


@test
def bench_actor_refuses(mod):
    S.actors.append(Actor("ZZ_TEMP_Probe", (0, 0, 0)))
    ok, _, err = run(mod, "APPLY")
    assert not ok and "bench actors" in err and not S.changes
    ok, _, err = run(mod, "DRY")
    assert not ok and "bench actors" in err


@test
def sequencer_open_refuses(mod):
    S.sequencer = True
    ok, _, err = run(mod, "APPLY")
    assert not ok and "Sequencer" in err and not S.changes


@test
def setter_returning_false_still_passes(mod):
    S.inject["setter_lies_false"] = True
    ok, _, err = run(mod, "APPLY")
    assert ok, err


@test
def setter_noop_is_caught_before_level(mod):   # twin
    S.inject["setter_noop_true"] = True
    ok, _, err = run(mod, "APPLY")
    assert not ok and "MI read-back" in err and not S.saves
    assert not [c for c in S.changes if c not in ("create_asset",)], S.changes   # the level untouched


@test
def hinge_disagreement_refuses(mod):
    by("S4 Hangar Root").loc[0] += 5.0
    ok, _, err = run(mod, "DRY")
    assert not ok and "disagrees with root" in err


@test
def hinge_small_offset_passes(mod):            # twin
    by("S4 Hangar Root").loc[0] += 0.5
    ok, rep, err = run(mod, "DRY")
    assert ok, err
    assert abs(rep["p04"]["x"][1] - 11168.97) < 1e-6


@test
def hinge_needs_two_witnesses(mod):
    S.actors.remove(by("Scene 4 — External Sound — Entry Handoff Camera"))
    S.actors.remove(by("S4 Hangar Apron"))
    os.remove(os.path.join(S.repo, "Saved", "CodexStructure", "hangar_s4_plan.json"))
    ok, _, err = run(mod, "DRY")
    assert not ok and "fewer than two" in err


@test
def buried_actor_refuses_unless_acked(mod):
    S.actors.append(Actor("Crate on the old floor", (3000, 8000, 20), bounds=((2950, 7950, -5.0), (3050, 8050, 45))))
    ok, _, err = run(mod, "DRY")
    assert not ok and "would bury 1" in err and "Crate on the old floor" in err
    ok, _, err = run(mod, "APPLY", ["Something else"])
    assert not ok and not S.changes
    ok, _, err = run(mod, "APPLY", ["Crate on the old floor"])
    assert ok, err


@test
def second_apply_refused(mod):
    assert run(mod, "APPLY")[0]
    n = len(S.changes)
    ok, _, err = run(mod, "APPLY")
    assert not ok and len(S.changes) == n and ("already exists" in err or "REVERT first" in err)


@test
def revert_is_exact(mod):
    before = snapshot()
    assert run(mod, "APPLY")[0]
    S.saves.clear()
    ok, _, err = run(mod, "REVERT")
    assert ok, err
    assert snapshot() == before, "revert not exact"
    assert not [a for a in S.actors if a.label == "Passage 04 - Floor (dark wet)"]
    assert MI_PATH in S.assets and S.saves == [WORLD]
    assert not os.path.exists(S.record_path) and any(".reverted-" in f for f in os.listdir(S.here))
    assert logs_with("FLOOR_DW_REVERT_OK|")


@test
def revert_refuses_on_drift(mod):              # twin
    assert run(mod, "APPLY")[0]
    by("Passage 03 - Floor").loc[2] += 1.0
    n, s = len(S.changes), list(S.saves)
    ok, _, err = run(mod, "REVERT")
    assert not ok and "P03: not in the applied state" in err and len(S.changes) == n and S.saves == s


@test
def revert_refuses_untagged_p04(mod):
    assert run(mod, "APPLY")[0]
    by("Passage 04 - Floor (dark wet)").tags = []
    n = len(S.changes)
    ok, _, err = run(mod, "REVERT")
    assert not ok and "tagged" in err and len(S.changes) == n


@test
def revert_without_record_refuses(mod):
    ok, _, err = run(mod, "REVERT")
    assert not ok and "NOTHING TO REVERT" in err and not S.changes


@test
def reapply_reuses_existing_mi_and_saves_level_only(mod):
    assert run(mod, "APPLY")[0]
    assert run(mod, "REVERT")[0]
    S.saves.clear()
    ok, _, err = run(mod, "APPLY")
    assert ok, err
    assert S.saves == [WORLD], S.saves


@test
def existing_mi_that_differs_refuses(mod):     # twin
    S.assets[MI_PATH] = MaterialInstanceConstant(MI_PATH, parent=S.assets[PARENT], scalars={"Roughness_Low": 0.5})
    ok, _, err = run(mod, "APPLY")
    assert not ok and "differs" in err
    ok, _, err = run(mod, "DRY")
    assert not ok and "already exists and differs" in err
    assert not [c for c in S.changes if c != "create_asset"] and not S.saves


@test
def level_save_failure_leaves_applying_record(mod):
    S.inject["level_save_fails"] = True
    ok, _, err = run(mod, "APPLY")
    assert not ok and "level save failed" in err and WORLD not in S.saves
    assert json.load(open(S.record_path))["state"] == "applying"


@test
def stale_applying_record_archived_when_live_matches(mod):
    S.inject["level_save_fails"] = True
    assert not run(mod, "APPLY")[0]
    # Don't-Save restart: rebuild the level as it was on disk, keep Saved/ files
    keep = {f: open(os.path.join(S.here, f), "rb").read() for f in os.listdir(S.here)}
    fresh(S.repo)
    for f, b in keep.items():
        open(os.path.join(S.here, f), "wb").write(b)
    ok, _, err = run(mod, "APPLY")
    assert ok, err
    assert any(".stale-" in f for f in os.listdir(S.here)) and logs_with("FLOOR_DW_STALE_RECORD_ARCHIVED")


@test
def stale_applying_record_refused_when_live_differs(mod):   # twin
    S.inject["level_save_fails"] = True
    assert not run(mod, "APPLY")[0]          # in-memory level still mutated (no restart)
    S.maps_dirty.clear()                      # even if someone clears the dirty flag
    S.inject.pop("level_save_fails")
    n = len(S.changes)
    ok, _, err = run(mod, "APPLY")
    assert not ok and len(S.changes) == n


@test
def p04_already_present_refuses(mod):
    S.actors.append(StaticMeshActor("Passage 04 - Floor (dark wet)", (5500, 240000, 0), mesh=S.assets[CUBE]))
    ok, _, err = run(mod, "DRY")
    assert not ok and "P04: slab already exists" in err


@test
def p02_never_targeted(mod):
    with open(TOOL, encoding="utf-8") as fh:
        src = fh.read()
    tgt = src.split("SLABS = {", 1)[1].split("\n}\n", 1)[0]
    assert "Passage 02" not in tgt
    assert run(mod, "APPLY")[0]
    assert not [c for c in S.changes if "Passage 02" in c], S.changes


def main():
    passed, failed = 0, []
    mod = load_tool()
    for t in TESTS:
        tmp = tempfile.mkdtemp(prefix="fdw_")
        try:
            fresh(tmp)
            t(mod)
            passed += 1
            print(f"PASS {t.__name__}")
        except Exception:
            failed.append(t.__name__)
            print(f"FAIL {t.__name__}\n{traceback.format_exc()}")
            if S is not None:
                print("  last logs:", [m for _, m in S.logs][-3:])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if failed:
        print(f"FLOOR_DW_HARNESS_FAIL|passed={passed}|failed={failed}")
        return 1
    print(f"FLOOR_DW_HARNESS_PASS|tests={passed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
