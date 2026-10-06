"""Offline harness for fence_stack_750.py (plain Python, no editor). Run:
    python Saved/CodexConductor/test_fence_stack_750.py
A fake `unreal` models the six structures as the 6 Oct logs measured them: only Structure 05 has a fence (276 panels
live; here 2 sides x 12 tiles, Native, FenceHeightCm 300, the short FenceBay kit 302.676 cm tall, B/C tarp overlays,
D door gap), all six have tubes with fence-top rows (raise 15) and tube lights (1500 lm), glow 0.15. Its
materialize_structure emulates the FS patch's C++ independently of the tool's plan_stack (Stack rows, cut top row,
doors only on row 0, ground row = the unstacked stream, fence-top tubes on the built top) and can be told to misbehave.
get_component_bounds raises: the tool must read instance transforms only.
Every gate has a failing control. Exit 0 = all pass; prints FENCE750_HARNESS_PASS|tests=N or _FAIL.
"""
from __future__ import annotations

import hashlib
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
TOOL = os.path.join(HERE, "fence_stack_750.py")
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SM = "/Game/InfinityStage/RigAtmos/FenceBay/StaticMeshes/"
KIT_Z = 302.67633056640625
S = None


# ============================================================================ fake unreal
class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Quat:
    def __init__(self, x, y, z, w):
        self.x, self.y, self.z, self.w = x, y, z, w


class Transform:
    def __init__(self, loc, quat, scale):
        self.translation, self.rotation, self.scale3d = Vector(*loc), Quat(*quat), Vector(*scale)


class _Box:
    def __init__(self, mn, mx):
        self.min, self.max = Vector(*mn), Vector(*mx)


class Mesh:
    def __init__(self, path, zmax=KIT_Z, zmin=0.0):
        self.path, self.zmax, self.zmin = path, zmax, zmin

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]

    def get_bounding_box(self):
        return _Box((-168, -9, self.zmin), (168, 9, self.zmax))


def _dirty():
    S.maps.add(WORLD)


class _Struct:
    def __init__(self, **kw):
        self.p = dict(kw)

    def get_editor_property(self, k):
        if k not in self.p:
            raise AttributeError(k)
        return self.p[k]

    def set_editor_property(self, k, v):
        if k not in self.p:
            raise AttributeError(k)
        if S.flags.get("setter_lies") == k:
            return
        self.p[k] = v

    def copy(self):
        c = _Struct(**self.p)
        for k, v in c.p.items():
            if isinstance(v, _Struct):
                c.p[k] = v.copy()
        return c


class _Enum:
    def __init__(self, name, value):
        self.name, self.value = name, value

    def __repr__(self):
        return "<InfinityFenceHeightMode.%s: %d>" % (self.name, self.value)

    __str__ = __repr__

    def __eq__(self, other):
        return isinstance(other, _Enum) and other.name == self.name

    def __hash__(self):
        return hash(self.name)


class InfinityFenceHeightMode:
    NATIVE = _Enum("NATIVE", 0)
    FIT = _Enum("FIT", 1)
    STACK = _Enum("STACK", 2)


class InstancedStaticMeshComponent:
    def __init__(self, name, tags, mesh, xfs):
        self.name, self.tags, self.mesh, self.xfs = name, list(tags), mesh, list(xfs)

    def get_name(self):
        return self.name

    def get_editor_property(self, k):
        if k == "component_tags":
            return list(self.tags)
        if k == "static_mesh":
            return self.mesh
        raise AttributeError(k)

    def get_instance_count(self):
        return len(self.xfs)

    def get_instance_transform(self, i, world):
        assert world is True
        loc, quat, scale = self.xfs[i]
        return Transform(loc, quat, scale)


class RectLightComponent:
    def __init__(self, loc, intensity):
        self.loc, self.intensity = loc, intensity

    def get_editor_property(self, k):
        if k == "component_tags":
            return ["InfinityStage.Structure.Underpass.TubeLights"]
        if k == "intensity":
            return self.intensity
        raise AttributeError(k)

    def get_world_location(self):
        return Vector(*self.loc)


def _h(*parts):
    return int(hashlib.md5(repr(parts).encode()).hexdigest()[:8], 16) / float(1 << 32)


def _cpp_plan(intended, row, cut):
    """Independent restatement of PlanFenceStack (the harness must not reuse the tool's own)."""
    if not cut:
        n = max(1, int(intended / row + 0.5))
        return n, row, n * row
    n = int(intended // row)
    rest = intended - n * row
    if n == 0:
        return 1, intended, intended
    if rest >= 0.25 * row:
        return n + 1, rest, n * row + rest
    return n, row, n * row


class InfinityStageStructureActor:
    TILES = 12

    def __init__(self, n, fenced):
        self.n, self.label = n, "Infinity Stage - Structure 0%d" % n
        variants = {}
        for k, mesh, w, ov, gro in (("fence_variant_a", "SM_FenceBay_short_open", 0.6, None, False),
                                    ("fence_variant_b", "SM_FenceBay_short_open", 0.2, "SM_FenceTarp_short_half", False),
                                    ("fence_variant_c", "SM_FenceBay_short_open", 0.15, "SM_FenceTarp_short_torn", False),
                                    ("fence_variant_d", "SM_FenceBay_short_door_gap", 0.05, None, True)):
            p = dict(mesh=Mesh(SM + mesh) if fenced else None, weight=w,
                     overlay_mesh=Mesh(SM + ov, 140.0, 26.0) if (ov and fenced) else None)
            if not S.flags.get("build_missing"):
                p["ground_row_only"] = gro
            variants[k] = _Struct(**p)
        up = dict(enabled=True, fence=fenced, fence_height_mode=InfinityFenceHeightMode.NATIVE, fence_height_cm=300.0,
                  fence_base_cm=0.0, fence_inset_cm=75.0, fence_both_sides=True, fence_cast_shadow=True,
                  column_outset_cm=60.0, deck_height_cm=2000.0, tubes=True, tube_fence_top_rows=True,
                  tube_fence_top_raise_cm=15.0, tube_diameter_cm=5.0, tube_lights=True, tube_light_cast_shadow=False,
                  tube_blink_fraction=0.2, tube_glow_level=0.15, tube_light_intensity=1500.0, fence_seed=0, **variants)
        if not S.flags.get("build_missing"):
            up["fence_stack_cut_top_row"] = True
        self.p = {"underpass": _Struct(**up), "gridiron": _Struct(height_cm=1150.0, beam_depth_cm=90.0),
                  "ground": _Struct(floor_height_cm=0.0), "grid_half_width_cm": 1349.14 + 10 * n}
        if not S.flags.get("build_missing"):
            self.p.update(underpass_fence_row_count=0, underpass_fence_stack_top_cm=0.0)
        self.gen = 0
        self._build()

    # -- actor API
    def get_actor_label(self):
        return self.label

    def get_editor_property(self, k):
        u = self.p["underpass"]
        counts = {"underpass_fence_panel_count": sum(len(c.xfs) for c in self.comps if any(t.startswith("InfinityStage.Structure.Underpass.Fence.") for t in c.tags)),
                  "underpass_fence_overlay_count": sum(len(c.xfs) for c in self.comps if any(t.startswith("InfinityStage.Structure.Underpass.FenceOverlay.") for t in c.tags)),
                  "underpass_tube_count": sum(len(c.xfs) for c in self.comps if "InfinityStage.Structure.Underpass.Tubes" in c.tags),
                  "underpass_tube_light_count": len(self.lights)}
        if k in counts:
            return counts[k]
        if k not in self.p:
            raise AttributeError(k)
        v = self.p[k]
        return v.copy() if isinstance(v, _Struct) else v

    def set_editor_property(self, k, v):
        _dirty()
        self.p[k] = v.copy() if isinstance(v, _Struct) else v

    def modify(self):
        _dirty()

    def get_components_by_class(self, cls):
        if cls is RectLightComponent:
            return list(self.lights)
        return list(self.comps)

    def materialize_structure(self):
        _dirty()
        if S.flags.get("materialize_fails"):
            return False
        self._build()
        return True

    def is_structure_current(self):
        return not S.flags.get("not_current")

    # -- the emulated C++
    def _build(self):
        self.gen += 1
        u = self.p["underpass"].p
        f = S.flags if self.gen > 1 else {}
        half = self.p["grid_half_width_cm"]
        fence_line = half + u["column_outset_cm"] - u["fence_inset_cm"]
        corner = half + u["column_outset_cm"] - 45.0
        floor = self.p["ground"].p["floor_height_cm"]
        base = floor + u["fence_base_cm"]
        names = "ABCD"
        vs = [u["fence_variant_" + c.lower()].p for c in names]
        built = [v["mesh"] is not None and v["weight"] > 0 for v in vs]
        stack = u["fence_height_mode"] == InfinityFenceHeightMode.STACK and not f.get("ignore_stack")
        row_cm = max([v["mesh"].zmax - v["mesh"].zmin for v, b in zip(vs, built) if b] or [0.0])
        fence_on = u["enabled"] and u["fence"] and row_cm > 0
        rows, top_row, top = 1, row_cm, max(1.0, u["fence_height_cm"])
        if stack and fence_on:
            rows, top_row, top = _cpp_plan(max(1.0, u["fence_height_cm"]), row_cm, u.get("fence_stack_cut_top_row", True))
        self.p["underpass_fence_row_count"] = (rows + (1 if f.get("cpp_rows_mismatch") else 0)) if (stack and fence_on) else 0
        self.p["underpass_fence_stack_top_cm"] = top if (stack and fence_on) else 0.0
        panels = {c: [] for c in names}
        if fence_on:
            for side in (-1, 1):
                quat = (0.0, 0.0, 0.0, 1.0) if side < 0 else (0.0, 0.0, 1.0, 0.0)
                for tile in range(self.TILES):
                    for r in range(rows):
                        pool = [i for i in range(4) if built[i] and (r == 0 or not vs[i].get("ground_row_only"))]
                        roll = _h(self.n, side, tile, r, u["fence_seed"], f.get("reroll_ground") and r == 0)
                        tot = sum(vs[i]["weight"] for i in pool)
                        acc, pick = 0.0, pool[-1]
                        for i in pool:
                            acc += vs[i]["weight"] / tot
                            if roll < acc:
                                pick = i
                                break
                        if f.get("door_above") and r > 0 and tile == 3:
                            pick = 3
                        h = top_row if (stack and r == rows - 1) else row_cm
                        sz = h / row_cm
                        z = base + r * row_cm - vs[pick]["mesh"].zmin * sz
                        panels[names[pick]].append(((168.0 + 336.0 * tile, side * fence_line, z), quat, (1.0, 1.0, sz)))
        comps = [InstancedStaticMeshComponent("StructureGridiron_%d" % self.gen, ["InfinityStage.Structure", "InfinityStage.Structure.Gridiron"],
                                              Mesh("/Engine/BasicShapes/Cube"),
                                              [((300.0 * i, 0.0, 1150.0 + (3.0 if f.get("other_drift") else 0.0)), (0, 0, 0, 1), (1, 27, 0.9)) for i in range(20)])]
        for c in names:
            if panels[c]:
                v = vs[names.index(c)]
                comps.append(InstancedStaticMeshComponent("StructureUnderpassFence%s_%d" % (c, self.gen),
                                                          ["InfinityStage.Structure", "InfinityStage.Structure.Underpass.Fence",
                                                           "InfinityStage.Structure.Underpass.Fence." + c], v["mesh"], panels[c]))
                if v["overlay_mesh"] is not None:
                    comps.append(InstancedStaticMeshComponent("StructureUnderpassFenceOverlay%s_%d" % (c, self.gen),
                                                              ["InfinityStage.Structure", "InfinityStage.Structure.Underpass.Fence",
                                                               "InfinityStage.Structure.Underpass.FenceOverlay." + c], v["overlay_mesh"], panels[c]))
        tubes, lights = [], []
        if u["enabled"] and u["tubes"]:
            fence_top = base + (top if (stack and fence_on) else max(1.0, u["fence_height_cm"])) + u["tube_fence_top_raise_cm"]
            if f.get("tube_wrong_dz"):
                fence_top += 7.0
            lines = [(-60.0, 1970.0), (60.0, 1970.0), (-corner, 1970.0), (corner, 1970.0)]
            if u["tube_fence_top_rows"]:
                lines += [(-fence_line, fence_top), (fence_line, fence_top)]
            for li, (y, z) in enumerate(lines):
                for i in range(16):
                    tubes.append(((125.0 + 250.0 * i, y, z), (0.0, 0.7071, 0.0, 0.7071), (0.05, 0.05, 1.5)))
                    if li >= 4 and i % 4 == 1:
                        inten = 1500.0 if f.get("light_intensity_stale") else u["tube_light_intensity"]
                        lights.append(RectLightComponent((125.0 + 250.0 * i, y, z), inten))
        comps.append(InstancedStaticMeshComponent("StructureUnderpassTubes_%d" % self.gen,
                                                  ["InfinityStage.Structure", "InfinityStage.Structure.Underpass.Tubes"],
                                                  Mesh("/Engine/BasicShapes/Cylinder", 50.0, -50.0), tubes))
        self.comps, self.lights = comps, lights


class _Pkg:
    def __init__(self, n):
        self.n = n

    def get_name(self):
        return self.n


class EditorLoadingAndSavingUtils:
    @staticmethod
    def get_dirty_content_packages():
        return [_Pkg(n) for n in sorted(S.content)]

    @staticmethod
    def get_dirty_map_packages():
        return [_Pkg(n) for n in sorted(S.maps)]

    @staticmethod
    def save_map(world, path):
        if S.flags.get("extra_dirty_content"):
            return False
        S.saves += 1
        with open(S.umap, "ab") as fh:
            fh.write(b"saved%d" % S.saves)
        S.maps.clear()
        return True


class _World:
    def get_path_name(self):
        return WORLD + ".L_InfinityStage_V1VerticalSlice"


class UnrealEditorSubsystem:
    def get_game_world(self):
        return object() if S.flags.get("pie") else None

    def get_editor_world(self):
        return _World()


class _Label:
    def __init__(self, label):
        self.label = label

    def get_actor_label(self):
        return self.label


class EditorActorSubsystem:
    def get_all_level_actors(self):
        extra = [_Label("ZZ_bench")] if S.flags.get("bench") else []
        return list(S.structures) + extra


class LevelSequenceEditorBlueprintLibrary:
    @staticmethod
    def get_current_level_sequence():
        return object() if S.flags.get("sequencer") else None


class SystemLibrary:
    @staticmethod
    def get_component_bounds(comp):
        S.bounds_calls += 1
        raise AssertionError("get_component_bounds must not be used (cached bounds read zero after a materialize)")


class Paths:
    @staticmethod
    def project_dir():
        return S.repo + "/"

    @staticmethod
    def project_saved_dir():
        return S.repo + "/Saved/"

    @staticmethod
    def convert_relative_path_to_full(p):
        return p


def make_unreal():
    m = types.ModuleType("unreal")
    for k, v in dict(Vector=Vector, InfinityStageStructureActor=InfinityStageStructureActor,
                     InstancedStaticMeshComponent=InstancedStaticMeshComponent, RectLightComponent=RectLightComponent,
                     EditorLoadingAndSavingUtils=EditorLoadingAndSavingUtils, UnrealEditorSubsystem=UnrealEditorSubsystem,
                     EditorActorSubsystem=EditorActorSubsystem, SystemLibrary=SystemLibrary, Paths=Paths,
                     LevelSequenceEditorBlueprintLibrary=LevelSequenceEditorBlueprintLibrary).items():
        setattr(m, k, v)

    class _Modes:
        NATIVE = InfinityFenceHeightMode.NATIVE
        FIT = InfinityFenceHeightMode.FIT
    if not S.flags.get("build_missing"):
        _Modes.STACK = InfinityFenceHeightMode.STACK
    m.InfinityFenceHeightMode = _Modes
    m.get_editor_subsystem = lambda cls: cls()
    m.log = lambda msg: S.logs.append(("I", msg))
    m.log_error = lambda msg: S.logs.append(("E", msg))
    return m


# ============================================================================ harness
class State:
    def __init__(self, flags=None):
        self.flags = dict(flags or {})
        self.content, self.maps = set(), set()
        self.logs, self.saves, self.bounds_calls = [], 0, 0
        self.repo = tempfile.mkdtemp(prefix="fence750_")
        os.makedirs(os.path.join(self.repo, "Saved", "CodexConductor"))
        os.makedirs(os.path.join(self.repo, "Backups"))
        mapdir = os.path.join(self.repo, "Content", "InfinityStage", "Dev", "Maps")
        os.makedirs(mapdir)
        self.umap = os.path.join(mapdir, "L_InfinityStage_V1VerticalSlice.umap")
        with open(self.umap, "wb") as fh:
            fh.write(b"umap-v0")
        lamp = {"after_target_rows": {"g%d" % i: {"relative_transform": {"location": [0.0, s * 360.0, 1052.2]}}
                                      for i, s in enumerate((-1, 1))}}
        json.dump(lamp, open(os.path.join(self.repo, "Saved", "CodexConductor", "rig_lamp_drop_record_P05.json"), "w"))
        self.structures = []


def setup(flags=None):
    global S
    S = State(flags)
    build_flags, S.flags = S.flags, {k: v for k, v in S.flags.items() if k in ("build_missing",)}
    S.structures = [InfinityStageStructureActor(n, n == 5) for n in range(1, 7)]
    S.flags = build_flags
    sys.modules["unreal"] = make_unreal()
    spec = importlib.util.spec_from_file_location("fence_stack_750_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(mod, **args):
    try:
        return mod.main(args), None
    except mod.Fence750Error as exc:
        return None, str(exc)


def markers(prefix):
    return [m for _, m in S.logs if m.startswith(prefix)]


def umap_bytes():
    return open(S.umap, "rb").read()


def apply_args(**kw):
    a = {"mode": "APPLY", "confirm": "APPLY FENCE750"}
    a.update(kw)
    return a


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


@test
def t_plan_stack_matches_the_cpp_tests():
    mod = setup()
    p = mod.plan_stack(750.0, KIT_Z, True)
    check(p["rows"] == 3 and abs(p["top_row_cm"] - (750 - 2 * KIT_Z)) < 1e-9 and abs(p["top_cm"] - 750) < 1e-9, p)
    w = mod.plan_stack(750.0, KIT_Z, False)
    check(w["rows"] == 2 and abs(w["top_cm"] - 2 * KIT_Z) < 1e-9 and w["top_row_cm"] == w["row_cm"], w)
    check(mod.plan_stack(610.0, KIT_Z, True)["rows"] == 2, "610: sliver dropped")
    lo = mod.plan_stack(200.0, KIT_Z, True)
    check(lo["rows"] == 1 and lo["top_cm"] == 200.0, lo)
    ex = mod.plan_stack(900.0, 300.0, True)
    check(ex["rows"] == 3 and ex["top_cm"] == 900.0, ex)
    check(mod.plan_stack(250.0, 100.0, False)["rows"] == 3 and mod.plan_stack(240.0, 100.0, False)["rows"] == 2, "round")
    for i in range(1, 400):
        for cut in (True, False):
            a = mod.plan_stack(i * 3.7, 97.3, cut)
            b = _cpp_plan(i * 3.7, 97.3, cut)
            check(a["rows"] == b[0] and abs(a["top_cm"] - b[2]) < 1e-9, (i, cut, a, b))


@test
def t_enum_name():
    mod = setup()
    for v in ("<InfinityFenceHeightMode.NATIVE: 0>", "InfinityFenceHeightMode.STACK", "fit", InfinityFenceHeightMode.STACK):
        check(mod.enum_name(v) in ("NATIVE", "STACK", "FIT"), v)


@test
def t_dry_reads_and_mutates_nothing():
    mod = setup()
    before = umap_bytes()
    rep, err = run(mod, mode="DRY")
    check(err is None, err)
    check(markers("FENCE750_DRY_OK"), S.logs[-3:])
    check(not S.maps and not S.content and umap_bytes() == before, "DRY dirtied")
    r5 = rep["rows"]["Infinity Stage - Structure 05"]
    check(r5["pred"]["plan"]["rows"] == 3 and abs(r5["pred"]["tube_dz_cm"] - 450.0) < 1e-6, r5["pred"])
    check(r5["clearance"]["fence_to_girder_cm"] == 355.0 and r5["clearance"]["top_lamps"]["tube_to_lamp_vertical_cm"] == 287.2,
          r5["clearance"])
    r1 = rep["rows"]["Infinity Stage - Structure 01"]
    check(r1["pred"]["plan"] is None and abs(r1["pred"]["tube_dz_cm"] - 450.0) < 1e-6, "fence-less: tubes still rise to 750")
    check(rep["cars"]["P02"]["beam_meets"] == "no fence in this Passage", rep["cars"])
    check(S.bounds_calls == 0, "bounds used")
    check(os.path.exists(os.path.join(S.repo, "Saved", "CodexConductor", "fence_stack_750_dry_%s.json" % rep["run"])), "report")


@test
def t_build_missing_refuses_before_any_write():
    mod = setup({"build_missing": True})
    rep, err = run(mod, mode="DRY")
    check(err is None and markers("FENCE750_DRY_REFUSED") and "BUILD_MISSING_FS" in markers("FENCE750_DRY_REFUSED")[0], S.logs[-2:])
    before = umap_bytes()
    _, err = run(mod, **apply_args())
    check(err and "BUILD_MISSING_FS" in err, err)
    check(not os.path.exists(os.path.join(S.repo, "Saved", "CodexConductor", "fence_stack_750_record.json")), "record written")
    check(os.listdir(os.path.join(S.repo, "Backups")) == [] and umap_bytes() == before and not S.maps, "touched")


@test
def t_apply_happy_path():
    mod = setup()
    before = umap_bytes()
    rec, err = run(mod, **apply_args())
    check(err is None, err)
    check(markers("FENCE750_APPLY_OK"), S.logs[-3:])
    check(rec["state"] == "applied" and umap_bytes() != before and not S.maps, "not saved")
    check(len(os.listdir(os.path.join(S.repo, "Backups"))) == 1, "backup")
    for s in S.structures:
        u = s.p["underpass"].p
        check(u["fence_height_mode"] == InfinityFenceHeightMode.STACK and u["fence_height_cm"] == 750.0, s.label)
        check(abs(u["tube_glow_level"] - 0.07) < 1e-9 and abs(u["tube_light_intensity"] - 375.0) < 1e-9, s.label)
        check(all(abs(l.intensity - 375.0) < 1e-9 for l in s.lights) and s.lights, "lights")
    b5 = rec["built"]["Infinity Stage - Structure 05"]
    check(b5["panels"] == 3 * 24 and b5["rows"] == 3 and b5["tubes_moved"] == 32, b5)
    check(rec["built"]["Infinity Stage - Structure 01"]["panels"] == 0, "fence-less built panels")
    check(S.bounds_calls == 0, "bounds used")
    rec2 = json.load(open(os.path.join(S.repo, "Saved", "CodexConductor", "fence_stack_750_record.json")))
    check(rec2["before"]["Infinity Stage - Structure 05"]["tube_light_intensity"] == 1500.0
          and rec2["before"]["Infinity Stage - Structure 05"]["fence_height_mode"] == "NATIVE", rec2["before"])


@test
def t_apply_whole_rows():
    mod = setup()
    rec, err = run(mod, **apply_args(top_row="whole"))
    check(err is None, err)
    b5 = rec["built"]["Infinity Stage - Structure 05"]
    check(b5["rows"] == 2 and b5["panels"] == 48, b5)
    check(abs(rec["pred"]["Infinity Stage - Structure 05"]["tube_dz_cm"] - (2 * KIT_Z - 300.0)) < 1e-6, "dz")


@test
def t_guards():
    for flags, args, want in (({}, {"mode": "APPLY"}, "CONFIRM_MISSING"),
                              ({}, {"mode": "APPLY", "confirm": "APPLY P05"}, "CONFIRM_MISSING"),
                              ({"pie": True}, apply_args(), "PIE_ACTIVE"),
                              ({"bench": True}, apply_args(), "BENCH_ACTORS"),
                              ({"sequencer": True}, apply_args(), "SEQUENCER_OPEN"),
                              ({}, apply_args(top_row="half"), "TOP_ROW"),
                              ({}, {"mode": "BOGUS"}, "UNKNOWN_MODE")):
        mod = setup(flags)
        before = umap_bytes()
        _, err = run(mod, **args)
        check(err and want in err, (flags, args, err))
        check(umap_bytes() == before and os.listdir(os.path.join(S.repo, "Backups")) == [], "touched on %s" % want)
    mod = setup()
    S.content.add("/Game/Other")
    _, err = run(mod, **apply_args())
    check(err and "DIRTY_BEFORE" in err, err)


@test
def t_record_exists_and_already_stack():
    mod = setup()
    _, err = run(mod, **apply_args())
    check(err is None, err)
    _, err = run(mod, **apply_args())
    check(err and "RECORD_EXISTS" in err, err)
    mod = setup()
    S.structures[2].p["underpass"].p["fence_height_mode"] = InfinityFenceHeightMode.STACK
    _, err = run(mod, **apply_args())
    check(err and "ALREADY_STACK" in err, err)


@test
def t_faults_after_backup_save_nothing():
    for flag, want in (("ignore_stack", "LAYERS"), ("reroll_ground", "re-rolled"), ("door_above", "a door (D)"),
                       ("other_drift", "instances moved"), ("tube_wrong_dz", "want +0 or +"),
                       ("light_intensity_stale", "tube lights not at"), ("cpp_rows_mismatch", "C++ plan rows"),
                       ("materialize_fails", "MATERIALIZE_FAILED"), ("not_current", "NOT_CURRENT"),
                       ("extra_dirty_content", "SAVE_FAILED")):
        mod = setup({flag: True})
        before = umap_bytes()
        _, err = run(mod, **apply_args())
        check(err and want in err, (flag, err))
        errs = [m for k, m in S.logs if k == "E"]
        check(errs and "NOTHING SAVED" in errs[-1], (flag, errs[-1:]))
        check(umap_bytes() == before and S.saves == 0, "saved on %s" % flag)
    mod = setup({"setter_lies": "tube_glow_level"})
    _, err = run(mod, **apply_args())
    check(err and "READBACK" in err and "tube_glow_level" in err, err)


@test
def t_revert_restores():
    mod = setup()
    snap0 = {s.label: (json.dumps(s.p["underpass"].p, default=str), [c.xfs for c in s.comps if "Gridiron" not in c.name],
                       [(l.loc, l.intensity) for l in s.lights]) for s in S.structures}
    _, err = run(mod, **apply_args())
    check(err is None, err)
    _, err = run(mod, mode="REVERT", confirm="REVERT FENCE750")
    check(err is None, err)
    check(markers("FENCE750_REVERT_OK"), S.logs[-3:])
    for s in S.structures:
        u = s.p["underpass"].p
        check(u["fence_height_mode"] == InfinityFenceHeightMode.NATIVE and u["fence_height_cm"] == 300.0
              and u["tube_glow_level"] == 0.15 and u["tube_light_intensity"] == 1500.0, (s.label, u))
        check([c.xfs for c in s.comps if "Gridiron" not in c.name] == snap0[s.label][1], "layers %s" % s.label)
        check([(l.loc, l.intensity) for l in s.lights] == snap0[s.label][2], "lights %s" % s.label)
    here = os.path.join(S.repo, "Saved", "CodexConductor")
    check(not os.path.exists(os.path.join(here, "fence_stack_750_record.json"))
          and any(n.startswith("fence_stack_750_record.reverted-") for n in os.listdir(here)), "record not renamed")


@test
def t_revert_refusals():
    mod = setup()
    _, err = run(mod, mode="REVERT", confirm="REVERT FENCE750")
    check(err and "NO_RECORD" in err, err)
    mod = setup()
    _, err = run(mod, **apply_args())
    check(err is None, err)
    S.structures[0].p["underpass"].p["tube_glow_level"] = 0.5
    _, err = run(mod, mode="REVERT", confirm="REVERT FENCE750")
    check(err and "NOT_APPLIED_STATE" in err, err)


@test
def t_checkers_have_failing_controls():
    mod = setup()
    a = [{"loc": [0.0, 0.0, 0.0], "quat": [0, 0, 0, 1], "scale": [1, 1, 1], "minz": 0.0, "variant": "A"}]
    plan = mod.plan_stack(750.0, KIT_Z, True)
    good = [dict(a[0]), dict(a[0], loc=[0.0, 0.0, KIT_Z]),
            dict(a[0], loc=[0.0, 0.0, 2 * KIT_Z], scale=[1, 1, (750 - 2 * KIT_Z) / KIT_Z])]
    check(mod.check_fence(a, good, plan) == [], mod.check_fence(a, good, plan))
    bad_scale = good[:2] + [dict(good[2], scale=[1, 1, 1])]
    check(mod.check_fence(a, bad_scale, plan), "unscaled top row passed")
    dup = good[:2] + [dict(good[1])]
    check(mod.check_fence(a, dup, plan), "duplicate row passed")
    check(mod.check_moved(a, [dict(a[0], loc=[0, 0, 10.0])], 10.0, "t")[1] == 1, "moved")
    check(mod.check_moved(a, [dict(a[0], loc=[0, 0, 11.0])], 10.0, "t")[0], "wrong dz passed")


def main():
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception:  # noqa: BLE001
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
        finally:
            if S is not None and S.repo and os.path.isdir(S.repo):
                shutil.rmtree(S.repo, ignore_errors=True)
    print("FENCE750_HARNESS_%s|tests=%d|failed=%d" % ("PASS" if not failed else "FAIL", len(TESTS), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
