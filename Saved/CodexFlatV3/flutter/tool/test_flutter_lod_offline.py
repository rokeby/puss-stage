"""Offline harness for flutter_lod.py (system Python, no Unreal): a fake `unreal` module with a small Show, meshes,
MIs, a dirty-package census and an asset registry. Every gate has a failing (-) control next to its passing (+) one.

  python test_flutter_lod_offline.py  ->  FLUTTERLOD_HARNESS|tests=..|checks=..|failed=..  (+ report JSON, exit 1 on fail)

What it CAN show (measured, offline): the tool's control flow, classification, census/save discipline, read-back
gates, rollback and field-by-field revert against a fake that behaves as modelled.
What it CANNOT show: that UE 5.8's Python API behaves like the fake - in particular that
StaticMeshEditorSubsystem.set_lod_screen_sizes rebuilds render data so get_lod_screen_sizes reads the new value,
that it dirties only the mesh package, that a removed scalar override entry falls back to the parent, and that
TSoftObjectPtr arrays/exports look as modelled. Those are checked live by the tool's own read-back gates.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import tempfile
import types

HERE = pathlib.Path(__file__).resolve().parent
REPORT = HERE / "test_flutter_lod_offline_report.json"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
BB = "/Game/Scenes/Wings/PaintedSurface/Billboard/"
INST = "/Game/Scenes/Wings/FlatV3/Mats/"
MESH = "/Game/Scenes/Wings/FlatV3/Meshes/"
GUIDS = {"Passage 1": "P1" * 16, "Passage 2": "P2" * 16, "Passage 4": "0067B5F57142956FB5B80EA31B1210B5",
         "Passage 5": "3B27C331B54325A469AE8A818B9049F9", "Passage 6": "9BFC29C45D47911FF7836BB8537230D2"}


# ===================================================================================================== fake unreal
class FakeUnreal:
    def __init__(self):
        self.ASSETS, self.DIRTY, self.MAP_DIRTY, self.SAVED, self.LOG, self.ERR = {}, set(), set(), [], [], []
        self.GC = 0
        self.faults = set()
        self.extra_refs = {}
        self.pie = False
        self.world_name = WORLD
        self.passages, self.cues = [], []
        u = self

        class Obj:
            CLS = "Object"

            def __init__(self, path):
                self._path = path
                u.ASSETS[path] = self

            def get_path_name(self):
                return self._path + "." + self._path.rsplit("/", 1)[-1]

            def get_name(self):
                return self._path.rsplit("/", 1)[-1]

            def modify(self):
                u.DIRTY.add(self._path)

        class MaterialInterface(Obj):
            pass

        class Material(MaterialInterface):
            CLS = "Material"

            def __init__(self, path, defaults, switches):
                super().__init__(path)
                self.defaults, self.switches, self.max_wpo = dict(defaults), dict(switches), 6.0

            def get_editor_property(self, name):
                return {"max_world_position_offset_displacement": self.max_wpo}[name]

        class MaterialInstance(MaterialInterface):
            pass

        class Info:
            def __init__(self, name):
                self.name = name

            def get_editor_property(self, k):
                return {"name": self.name}[k]

        class Entry:
            def __init__(self, name, value):
                self.info, self.value = Info(name), value

            def get_editor_property(self, k):
                return {"parameter_info": self.info, "parameter_value": self.value}[k]

            def set_editor_property(self, k, v):
                assert k == "parameter_value"
                self.value = v

        self.Entry = Entry

        class MaterialInstanceConstant(MaterialInstance):
            CLS = "MaterialInstanceConstant"

            def __init__(self, path, parent, scalars=None, switches=None, textures=None):
                super().__init__(path)
                self.parent = parent
                self.scalars = [Entry(k, v) for k, v in (scalars or {}).items()]
                self.switches = dict(switches or {})
                self.textures = [Entry(k, v) for k, v in (textures or {}).items()]

            def get_editor_property(self, k):
                return {"parent": self.parent, "scalar_parameter_values": list(self.scalars),
                        "vector_parameter_values": [], "texture_parameter_values": list(self.textures)}[k]

            def set_editor_property(self, k, v):
                assert k == "scalar_parameter_values"
                self.scalars = list(v)

            # helpers for the fake MEL
            def root(self):
                o = self
                while isinstance(o, MaterialInstanceConstant):
                    o = o.parent
                return o

            def eff(self, name):
                o = self
                while isinstance(o, MaterialInstanceConstant):
                    for e in o.scalars:
                        if e.info.name == name:
                            return e.value
                    o = o.parent
                return o.defaults[name]

            def eff_switch(self, name):
                o = self
                while isinstance(o, MaterialInstanceConstant):
                    if name in o.switches:
                        return o.switches[name]
                    o = o.parent
                return o.switches[name]

        class Nanite:
            def __init__(self, on):
                self.on = on

            def get_editor_property(self, k):
                return {"enabled": self.on}[k]

        class SlotRow:
            def __init__(self, name, mat):
                self.name, self.mat = name, mat

            def get_editor_property(self, k):
                return {"material_slot_name": self.name, "material_interface": self.mat}[k]

        class StaticMesh(Obj):
            CLS = "StaticMesh"

            def __init__(self, path, slots, sizes=(2.0, 0.75), lod_slots=((0, 1, 2, 3), (0, 2, 3)), nanite=False):
                super().__init__(path)
                self.rows = [SlotRow(n, m) for n, m in slots]
                self.sizes, self.lod_slots, self.nanite = list(sizes), [list(x) for x in lod_slots], nanite

            def get_editor_property(self, k):
                if k == "auto_compute_lod_screen_size":
                    raise AttributeError("not exposed")
                return {"static_materials": list(self.rows), "nanite_settings": Nanite(self.nanite)}[k]

            def get_num_lods(self):
                return len(self.sizes)

        class World(Obj):
            CLS = "World"

        for c in (Obj, MaterialInterface, Material, MaterialInstance, MaterialInstanceConstant, StaticMesh, World):
            setattr(self, c.__name__, c)

        # ---- Show
        class Panel:
            def __init__(self, mesh, overrides=(), hide_mesh=False, hide_overrides=False):
                self.mesh, self.overrides = mesh, list(overrides)
                self.hide_mesh, self.hide_overrides = hide_mesh, hide_overrides

            def get_editor_property(self, k):
                if k == "mesh":
                    return None if self.hide_mesh else self.mesh
                if k == "material_overrides":
                    return [None if self.hide_overrides else m for m in self.overrides]
                raise KeyError(k)

            def export_text(self):
                mesh = "None" if self.mesh is None else '"%s"' % self.mesh.get_path_name()
                ovr = ",".join("None" if m is None else "MaterialInstanceConstant'\"%s\"'" % m.get_path_name()
                               for m in self.overrides)
                return '(Mesh=%s,MaterialOverrides=(%s),LocalTransform=(Rotation=(X=0,Y=0,Z=0,W=1)),bCastShadow=True)' % (mesh, ovr)

        class Pair:
            def __init__(self, left, right, top=None):
                self.left, self.right, self.top = left, right, top

            def get_editor_property(self, k):
                return {"left": self.left, "right": self.right, "top": self.top or Panel(None),
                        "has_top": self.top is not None}[k]

        class Cue:
            def __init__(self, guid, label, pair, enabled=True):
                self.guid, self.label, self.pair, self.enabled = guid, label, pair, enabled

            def get_editor_property(self, k):
                return {"type": "WP", "wing_pair": self.pair, "cue_guid": self.guid, "label": self.label,
                        "enabled": self.enabled}[k]

        class Settings:
            def __init__(self, label, guid):
                self.label, self.guid = label, guid

            def get_editor_property(self, k):
                return {"label": self.label, "passage_guid": self.guid}[k]

        class Show(Obj):
            CLS = "InfinityStageShowAsset"

            def get_editor_property(self, k):
                return {"passage_settings": [Settings(l, g) for l, g, _ in u.passages], "cues": list(u.cues)}[k]

            def get_wing_pair_cue_guids_in_passage(self, g):
                return [c for l, gg, cs in u.passages if gg == g for c in cs]

        self.Panel, self.Pair, self.Cue, self.Show = Panel, Pair, Cue, Show
        self.InfinityCueType = types.SimpleNamespace(WING_PAIR="WP")
        self.GuidLibrary = types.SimpleNamespace(conv_guid_to_string=lambda g: g)

        # ---- editor
        class Pk:
            def __init__(self, p):
                self.p = p

            def get_name(self):
                return self.p

        class Outer:
            def get_name(self):
                return u.world_name

        class W:
            def get_outermost(self):
                return Outer()

        class UES:
            def get_editor_world(self):
                return W()

            def get_game_world(self):
                return object() if u.pie else None

        class SMES:
            def get_lod_screen_sizes(self, m):
                return list(m.sizes)

            def set_lod_screen_sizes(self, m, sizes):
                if "lod_lie" in u.faults:
                    return True
                if "lod_dirties_map" in u.faults:
                    u.MAP_DIRTY.add(WORLD)
                if "lod_dirties_other" in u.faults:
                    u.DIRTY.add("/Game/Other/SomethingElse")
                if len(sizes) != len(m.sizes):
                    return False
                m.sizes = list(sizes)
                u.DIRTY.add(m._path)
                return True

            def get_lod_material_slot(self, m, lod, section):
                s = m.lod_slots[lod]
                return s[section] if section < len(s) else -1

        self.UnrealEditorSubsystem, self.StaticMeshEditorSubsystem = UES, SMES
        self._subs = {UES: UES(), SMES: SMES()}
        self.get_editor_subsystem = lambda cls: u._subs[cls]
        self.EditorStaticMeshLibrary = types.SimpleNamespace(get_lod_screen_sizes=lambda m: list(m.sizes))

        def load_asset(path):
            return u.ASSETS.get(str(path).split(".", 1)[0])

        def save_asset(path, only_if_is_dirty=True):
            u.SAVED.append(path)
            u.DIRTY.discard(path)
            return True

        self.EditorAssetLibrary = types.SimpleNamespace(load_asset=load_asset, save_asset=save_asset,
                                                        does_asset_exist=lambda p: p in u.ASSETS)
        self.EditorLoadingAndSavingUtils = types.SimpleNamespace(
            get_dirty_content_packages=lambda: [Pk(p) for p in sorted(u.DIRTY)],
            get_dirty_map_packages=lambda: [Pk(p) for p in sorted(u.MAP_DIRTY)])

        def set_scalar(mi, name, value):
            if "mi_lie" in u.faults:
                return False
            for e in mi.scalars:
                if e.info.name == name:
                    e.value = value
                    return True
            mi.scalars.append(Entry(name, value))
            return True

        self.MaterialEditingLibrary = types.SimpleNamespace(
            get_scalar_parameter_names=lambda mi: sorted(mi.root().defaults),
            get_material_instance_scalar_parameter_value=lambda mi, n: mi.eff(str(n)),
            set_material_instance_scalar_parameter_value=set_scalar,
            update_material_instance=lambda mi: None,
            get_static_switch_parameter_names=lambda mi: sorted(mi.root().switches),
            get_material_instance_static_switch_parameter_value=lambda mi, n: mi.eff_switch(str(n)))

        # ---- registry (derived from the fixture + extra_refs)
        class Reg:
            def get_referencers(self, package, opts):
                out = set(u.extra_refs.get(package, []))
                for p, o in u.ASSETS.items():
                    if isinstance(o, StaticMesh) and any(r.mat is not None and r.mat._path == package for r in o.rows):
                        out.add(p)
                    if isinstance(o, MaterialInstanceConstant) and o.parent is not None and o.parent._path == package:
                        out.add(p)
                obj = u.ASSETS.get(package)
                if isinstance(obj, StaticMesh) or any(
                        package in [x._path for x in c.pair.left.overrides + c.pair.right.overrides if x] for c in u.cues):
                    out.update([SHOW, WORLD])
                return sorted(out)

            def get_assets_by_package_name(self, package):
                o = u.ASSETS.get(package)
                cls = o.CLS if o else u.extra_class.get(package, "")
                return [types.SimpleNamespace(asset_class_path=types.SimpleNamespace(asset_name=cls))] if cls else []

        self.extra_class = {}
        self.AssetRegistryHelpers = types.SimpleNamespace(get_asset_registry=lambda: Reg())

        class Opts:
            def set_editor_property(self, k, v):
                pass

        self.AssetRegistryDependencyOptions = Opts
        self.SystemLibrary = types.SimpleNamespace(collect_garbage=lambda: setattr(u, "GC", u.GC + 1))
        self.log = lambda m: u.LOG.append(m)
        self.log_error = lambda m: u.ERR.append(m)
        self.log_warning = lambda m: u.LOG.append("WARN " + m)


def fixture():
    u = FakeUnreal()
    master = u.Material(BB + "M_Billboard", {"FlutterAmpCm": 3.0, "FlutterHz": 0.7, "FlutterMaxCm": 6.0, "Other": 1.0},
                        {"Flutter": False})
    flap = u.MaterialInstanceConstant(BB + "MI_Billboard_Flap", master, switches={"Flutter": True})
    front = u.MaterialInstanceConstant(BB + "MI_Billboard_Front", master)
    timber = u.MaterialInstanceConstant(INST + "MI_Timber", master)
    edge = u.MaterialInstanceConstant(INST + "MI_Edge", master)

    def mi(name, parent=flap, **kw):
        return u.MaterialInstanceConstant(INST + name, parent, **kw)

    def mesh(name, flap_mi, **kw):
        return u.StaticMesh(MESH + name, [("Front", front), ("Flap", flap_mi), ("Timber", timber), ("Edge", edge)], **kw)

    m = {}
    m["P04_a"] = mesh("SM_FlatV3_P04_a_L", mi("MI_P04_a_Flap", scalars={"Other": 0.5},
                                              textures={"SkinColor": u.Obj("/Game/T/T_a")}))
    m["P04_b"] = mesh("SM_FlatV3_P04_b_R", mi("MI_P04_b_Flap"))
    o2 = mi("MI_P04_b_Flap_o2", scalars={"FlutterAmpCm": 3.0})          # live via MaterialOverrides
    gal = mi("MI_P04_gal_Flap")                                          # also dresses a P02 wing
    m["P06_f"] = mesh("SM_FlatV3_P06_f_L", gal)
    m["P04_old"] = mesh("SM_FlatV3_P04_old_L", mi("MI_P04_old_Flap"))    # disabled cue
    cloud = mi("MI_P05_cloud_Flap")
    m["P05_c"] = mesh("SM_FlatV3_P05_c_R", cloud)
    m["P05_d"] = mesh("SM_FlatV3_P05_d_R", cloud)
    m["P05_nan"] = mesh("SM_FlatV3_P05_nan_R", cloud, nanite=True)
    e2 = mi("MI_P05_e2_Flap")
    u.MaterialInstanceConstant(INST + "MI_P01_child", e2)                 # P01 renders a CHILD of e2
    m["P05_e2"] = mesh("SM_FlatV3_P05_e2_L", e2)
    m["P05_max4"] = mesh("SM_FlatV3_P05_max4_L", mi("MI_P05_max4_Flap", scalars={"FlutterMaxCm": 4.0}))
    m["P05_fence"] = mesh("SM_FlatV3_P05_FenceTarp_L", mi("MI_FenceTarp_Flap"))
    m["P06_e"] = mesh("SM_FlatV3_P06_e_R", mi("MI_P06_e_Flap"))
    m["P06_low"] = mesh("SM_FlatV3_P06_low_R", mi("MI_P06_low_Flap"), sizes=(2.0, 0.25))
    roller = mi("MI_P02_Roller_Flap")
    m["roller"] = mesh("SM_FlatV3_P02_IND_Roller_L", roller)
    m["bamboo"] = u.StaticMesh(MESH + "SM_BambooScaffold_01_R", [("Main", front)], lod_slots=((0,), (0,)))
    m["P02_x"] = mesh("SM_FlatV3_P02_x_L", mi("MI_P02_x_Flap"))
    m["P01_y"] = mesh("SM_FlatV3_P01_y_L", mi("MI_P01_y_Flap"))
    u.Show(SHOW)
    u.World(WORLD)
    P, Pr, Cu = u.Panel, u.Pair, u.Cue

    def cue(g, label, left, right, enabled=True):
        u.cues.append(Cu(g, label, Pr(left, right), enabled))
        return g

    p4 = [cue("C41", "P4 r1", P(m["P04_a"]), P(m["P04_b"], [None, o2], hide_overrides=True)),
          cue("C42", "P4 r2", P(m["P04_old"]), P(m["P04_a"]), enabled=False)]
    p5 = [cue("C51", "P5 r1", P(m["P05_c"]), P(m["P05_d"])),
          cue("C52", "P5 r2", P(m["P05_nan"]), P(m["P05_e2"])),
          cue("C53", "P5 r3", P(m["P05_max4"]), P(m["P05_fence"]))]
    p6 = [cue("C61", "P6 r1", P(m["P06_e"]), P(m["roller"])),
          cue("C62", "P6 r2", P(m["P06_f"], hide_mesh=True), P(m["bamboo"])),
          cue("C63", "P6 r3", P(m["P06_low"]), P(None))]
    p2 = [cue("C21", "P2 r1", P(m["roller"]), P(m["P02_x"], [None, gal]))]
    p1 = [cue("C11", "P1 r1", P(m["P01_y"], [None, u.ASSETS[INST + "MI_P01_child"]]), P(None))]
    u.passages = [("Passage 1", GUIDS["Passage 1"], p1), ("Passage 2", GUIDS["Passage 2"], p2),
                  ("Passage 4", GUIDS["Passage 4"], p4), ("Passage 5", GUIDS["Passage 5"], p5),
                  ("Passage 6", GUIDS["Passage 6"], p6)]
    u.DIRTY.add("/Game/Someone/ElsesUnsavedEdit")          # a foreign dirty package that must stay dirty and unsaved
    return u, m


# ===================================================================================================== harness
def load(name, path, extra=None):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    for k, v in (extra or {}).items():
        setattr(mod, k, v)
    spec.loader.exec_module(mod)
    return mod


TOOL = load("flutter_lod_under_test", HERE / "flutter_lod.py", {"FLUTTERLOD_IMPORT_ONLY": True})
CORE = load("flutter_lod_core_under_test", HERE / "flutter_lod_core.py")
RESULTS, CHECKS = [], {"n": 0, "failed": []}


def check(cond, what):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(what)
    RESULTS.append({"check": what, "pass": bool(cond), "tier": "measured (offline, fake unreal)"})


class Env:
    def __init__(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="flutterlod_"))
        TOOL.HERE, TOOL.PLAN, TOOL.ORIGINALS = self.dir, self.dir / "flutter_lod_plan.json", self.dir / "flutter_lod_originals_ACTIVE.json"
        self.u, self.m = fixture()

    def run(self, **args):
        a = dict(json.loads((HERE / "flutter_lod_args.json").read_text(encoding="utf-8")))
        a.update(args)
        p = self.dir / "args.json"
        p.write_text(json.dumps(a), encoding="utf-8")
        return TOOL.main(u=self.u, here=HERE, args_path=p)

    def fails(self, prefix, **args):
        try:
            self.run(**args)
        except Exception as exc:  # noqa: BLE001
            return prefix in str(exc), str(exc)[:300]
        return False, "did not fail"

    def eff(self, name, param):
        return self.u.ASSETS[INST + name].eff(param)

    def ov(self, name):
        return {e.info.name: e.value for e in self.u.ASSETS[INST + name].scalars}

    def sizes(self, key):
        return list(self.m[key].sizes)

    def restart_dont_save(self):
        """Editor restart choosing Don't Save: unsaved packages reload from disk. The fake keeps values in memory,
        so this is only faithful when the in-memory rollback restored them (asserted by the callers)."""
        self.u.DIRTY = {p for p in self.u.DIRTY if p == "/Game/Someone/ElsesUnsavedEdit"}
        self.u.MAP_DIRTY = set()

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def dry_then_confirm(env, **extra):
    plan = env.run(mode="DRY", confirm="DRY FLUTTERLOD", **extra)
    return plan, plan["apply_confirm"]


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def t_parse_export():
    mesh, ovr = CORE.parse_panel_export('(Mesh="/Game/A/SM_X.SM_X",MaterialOverrides=(None,MaterialInstanceConstant\'"/Game/M/MI_Y.MI_Y"\'),Foo=1)')
    check(mesh == "/Game/A/SM_X" and ovr == [None, "/Game/M/MI_Y"], "parse: mesh + positional overrides")
    mesh, ovr = CORE.parse_panel_export("(Mesh=None,MaterialOverrides=(),Foo=1)")
    check(mesh is None and ovr == [], "parse: empty panel")


@test
def t_dry_classification():
    env = Env()
    before = (sorted(env.u.DIRTY), sorted(env.u.MAP_DIRTY))
    plan = env.run(mode="DRY", confirm="DRY FLUTTERLOD")
    tg = {pathlib.PurePosixPath(t["path"]).name for t in plan["mi_targets"]}
    rf = {pathlib.PurePosixPath(t["path"]).name: t["reasons"] for t in plan["mi_refused"]}
    check(tg == {"MI_P04_a_Flap", "MI_P04_b_Flap_o2", "MI_P05_cloud_Flap", "MI_P06_e_Flap", "MI_P06_low_Flap"},
          "DRY: exclusive effective Flap MIs are targets (override wins over mesh default) %s" % sorted(tg))
    check("MI_P04_b_Flap" not in tg and "MI_P04_b_Flap" not in rf, "DRY: overridden mesh-default MI is not a candidate")
    check("MI_P02_Roller_Flap" in rf and "shared_outside_targets" in rf["MI_P02_Roller_Flap"][0], "DRY(-): MI used in P02 refused")
    check("MI_P04_gal_Flap" in rf, "DRY(-): per-design MI also dressing a P02 wing (override) refused")
    check("MI_P05_e2_Flap" in rf and any("P1 r1" in r for r in rf["MI_P05_e2_Flap"]), "DRY(-): MI that is PARENT of a P01 MI refused")
    check("MI_P05_max4_Flap" in rf and any("flutter_max_cm" in r for r in rf["MI_P05_max4_Flap"]), "DRY(-): FlutterMaxCm 4 refused")
    check("MI_FenceTarp_Flap" not in tg and "MI_P04_old_Flap" not in tg, "DRY: fence (regex) and disabled-cue MIs not targets")
    mt = {pathlib.PurePosixPath(t["path"]).name for t in plan["mesh_targets"]}
    check(mt == {"SM_FlatV3_P04_a_L", "SM_FlatV3_P04_b_R", "SM_FlatV3_P05_c_R", "SM_FlatV3_P05_d_R", "SM_FlatV3_P05_e2_L",
                 "SM_FlatV3_P05_max4_L", "SM_FlatV3_P06_e_R", "SM_FlatV3_P06_f_L"},
          "DRY: mesh targets (hidden soft mesh resolved from export text) %s" % sorted(mt))
    mr = {pathlib.PurePosixPath(t["path"]).name: t["reasons"] for t in plan["mesh_refused"]}
    check("SM_FlatV3_P05_nan_R" in mr and "nanite" in mr["SM_FlatV3_P05_nan_R"][0], "DRY(-): Nanite mesh refused")
    check([pathlib.PurePosixPath(t["path"]).name for t in plan["mesh_shared_skipped"]] == ["SM_FlatV3_P02_IND_Roller_L"],
          "DRY(-): mesh shared with P02 skipped without include_shared_meshes")
    check([pathlib.PurePosixPath(t["path"]).name for t in plan["mesh_already"]] == ["SM_FlatV3_P06_low_R"], "DRY: LOD1 0.25 already below 0.3")
    check(all(t["new_sizes"] == [2.0, 0.3] for t in plan["mesh_targets"]), "DRY: new sizes keep LOD0 2.0, LOD1 0.3")
    check((sorted(env.u.DIRTY), sorted(env.u.MAP_DIRTY)) == before and not env.u.SAVED, "DRY: census unchanged, nothing saved")
    check(any(l.startswith("FLATV3_FLUTTERLOD_DRY_OK|run=FLUTTERLOD-DRY-") and "confirm=APPLY FLUTTERLOD 5MI 8MESH #" in l
              for l in env.u.LOG), "DRY: marker with run id and the APPLY confirm")
    check((env.dir / "flutter_lod_plan.json").exists(), "DRY: plan written")
    check(plan["master_max_wpo_cm"] == 6.0, "DRY: master max WPO read (6)")
    env.close()


@test
def t_sharing_detector_controls():
    env = Env()
    env.u.cues[-2].pair.right.overrides = [None, None]                  # P02 no longer wears gal
    plan = env.run(mode="DRY", confirm="DRY FLUTTERLOD")
    check(any(t["path"].endswith("MI_P04_gal_Flap") for t in plan["mi_targets"]), "sharing(+): gal becomes a target once P02 stops using it")
    env.close()
    env = Env()
    env.u.extra_refs[INST + "MI_P06_e_Flap"] = ["/Game/BP/BP_Thing"]
    env.u.extra_class["/Game/BP/BP_Thing"] = "Blueprint"
    plan = env.run(mode="DRY", confirm="DRY FLUTTERLOD")
    check(any(t["path"].endswith("MI_P06_e_Flap") and "foreign_referencers" in " ".join(t["reasons"]) for t in plan["mi_refused"]),
          "registry(-): a Blueprint referencer refuses the MI")
    plan = env.run(mode="DRY", confirm="DRY FLUTTERLOD", allow_referencers=["/Game/BP/BP_Thing"])
    check(any(t["path"].endswith("MI_P06_e_Flap") for t in plan["mi_targets"]), "registry(+): allow_referencers lets it through")
    env.u.extra_refs[INST + "MI_P06_e_Flap"] = ["/Game/Maps/L_Other"]
    env.u.extra_class["/Game/Maps/L_Other"] = "World"
    plan = env.run(mode="DRY", confirm="DRY FLUTTERLOD")
    check(any(t["path"].endswith("MI_P06_e_Flap") for t in plan["mi_refused"]), "registry(-): another map refuses the MI")
    env.close()


@test
def t_apply_revert_roundtrip():
    env = Env()
    plan, confirm = dry_then_confirm(env)
    orig_b_ov = env.ov("MI_P04_b_Flap_o2")
    orig_a_ov = env.ov("MI_P04_a_Flap")
    ok, msg = env.fails("CONFIRM_MISMATCH", mode="APPLY", confirm="APPLY FLUTTERLOD wrong", decided_by="Gary 7 Oct")
    check(ok and not env.u.SAVED and not (env.dir / "flutter_lod_originals_ACTIVE.json").exists(), "APPLY(-): wrong confirm, nothing written")
    ok, msg = env.fails("NOT_DECIDED", mode="APPLY", confirm=confirm, decided_by="")
    check(ok, "APPLY(-): empty decided_by refused")
    rec = env.run(mode="APPLY", confirm=confirm, decided_by="Gary 7 Oct", mesh_batch_size=3)
    check(rec["status"] == "PASS", "APPLY(+): PASS")
    for n in ("MI_P04_a_Flap", "MI_P04_b_Flap_o2", "MI_P05_cloud_Flap", "MI_P06_e_Flap"):
        check(env.eff(n, "FlutterAmpCm") == 6.0 and env.eff(n, "FlutterHz") == 0.9 and env.eff(n, "FlutterMaxCm") == 6.0,
              "APPLY: %s Amp 6 / Hz 0.9 / Max 6" % n)
    for n in ("MI_P02_Roller_Flap", "MI_P04_gal_Flap", "MI_P05_e2_Flap", "MI_P01_child", "MI_FenceTarp_Flap"):
        check(env.eff(n, "FlutterAmpCm") == 3.0 and env.eff(n, "FlutterHz") == 0.7, "APPLY(-): shared/excluded %s untouched" % n)
    check(env.u.ASSETS[BB + "MI_Billboard_Flap"].scalars == [], "APPLY(-): library parent untouched")
    for k in ("P04_a", "P04_b", "P05_c", "P06_f"):
        check(env.sizes(k) == [2.0, 0.3], "APPLY: %s sizes [2.0, 0.3]" % k)
    for k in ("roller", "P05_nan", "P06_low", "P05_fence", "P01_y"):
        check(env.sizes(k) != [2.0, 0.3] or k == "P06_low", "APPLY(-): %s LOD untouched" % k)
    check(env.sizes("P06_low") == [2.0, 0.25], "APPLY(-): already-low mesh untouched")
    tgt = {t["path"] for t in plan["mi_targets"]} | {t["path"] for t in plan["mesh_targets"]}
    check(set(env.u.SAVED) == tgt and len(env.u.SAVED) == len(tgt), "APPLY: saved exactly the targets, once each")
    check(sorted(env.u.DIRTY) == ["/Game/Someone/ElsesUnsavedEdit"], "APPLY: foreign dirty package still dirty, unsaved")
    check(env.u.GC == 3, "APPLY: collect_garbage after each of 3 mesh batches (got %d)" % env.u.GC)
    check(any(l.startswith("FLATV3_FLUTTERLOD_APPLY_OK|run=FLUTTERLOD-APPLY-") for l in env.u.LOG), "APPLY: marker with run id")
    check(any(l.startswith("FLATV3_FLUTTERLOD_ORIGINALS_WRITTEN") for l in env.u.LOG)
          and env.u.LOG.index(next(l for l in env.u.LOG if "ORIGINALS_WRITTEN" in l)) <
          env.u.LOG.index(next(l for l in env.u.LOG if "APPLY_BATCH" in l)), "APPLY: originals logged before the first write batch")
    check(env.ov("MI_P04_a_Flap").get("Other") == 0.5, "APPLY: other override kept")
    ok, _ = env.fails("ORIGINALS_ACTIVE_EXISTS", mode="APPLY", confirm=confirm, decided_by="Gary 7 Oct")
    check(ok, "APPLY(-): second APPLY refused while originals ACTIVE")
    orig = json.loads((env.dir / "flutter_lod_originals_ACTIVE.json").read_text(encoding="utf-8"))
    ok, _ = env.fails("CONFIRM_MISMATCH", mode="REVERT", confirm="REVERT FLUTTERLOD nope")
    check(ok, "REVERT(-): wrong confirm")
    env.u.SAVED.clear()
    rec = env.run(mode="REVERT", confirm="REVERT FLUTTERLOD %s" % orig["run"])
    check(rec["status"] == "PASS", "REVERT(+): PASS")
    check(env.ov("MI_P04_b_Flap_o2") == orig_b_ov, "REVERT: originally-present override restored to 3.0 (present)")
    check(env.ov("MI_P04_a_Flap") == orig_a_ov, "REVERT: originally-absent overrides REMOVED, others kept")
    for n in ("MI_P04_a_Flap", "MI_P05_cloud_Flap", "MI_P06_e_Flap"):
        check(env.eff(n, "FlutterAmpCm") == 3.0 and env.eff(n, "FlutterHz") == 0.7, "REVERT: %s effective back to 3 / 0.7" % n)
    for k in ("P04_a", "P04_b", "P05_c", "P05_d", "P05_e2", "P05_max4", "P06_e", "P06_f"):
        check(env.sizes(k) == [2.0, 0.75], "REVERT: %s sizes back" % k)
    check(set(env.u.SAVED) == tgt, "REVERT: saved exactly the targets")
    check(not (env.dir / "flutter_lod_originals_ACTIVE.json").exists() and
          any(p.name.startswith("flutter_lod_originals_reverted_") for p in env.dir.iterdir()), "REVERT: originals archived")
    check(any(l.startswith("FLATV3_FLUTTERLOD_REVERT_OK|run=FLUTTERLOD-REVERT-") for l in env.u.LOG), "REVERT: marker")
    env.close()


@test
def t_setter_lies():
    env = Env()
    _, confirm = dry_then_confirm(env)
    env.u.faults.add("mi_lie")
    ok, msg = env.fails("MI_VALUE_READBACK_SET", mode="APPLY", confirm=confirm, decided_by="Gary")
    check(ok, "APPLY(-): lying MI setter caught by read-back (%s)" % msg[:80])
    check(not env.u.SAVED, "APPLY(-): nothing saved after MI read-back failure")
    check(any(l.startswith("FLATV3_FLUTTERLOD_FAILED|run=") for l in env.u.ERR), "APPLY(-): FAILED marker with run id")
    check('"verified": true' in msg or "verified" in msg, "APPLY(-): failure carries the rollback verdict")
    check(env.eff("MI_P04_a_Flap", "FlutterAmpCm") == 3.0, "APPLY(-): MI rollback left the original value in memory")
    env.u.faults.clear()
    orig = json.loads((env.dir / "flutter_lod_originals_ACTIVE.json").read_text(encoding="utf-8"))
    ok, _ = env.fails("TARGET_DIRTY_AT_START", mode="REVERT", confirm="REVERT FLUTTERLOD %s" % orig["run"])
    check(ok, "REVERT(-): refuses while the rolled-back targets are still dirty (restart first)")
    env.restart_dont_save()
    rec = env.run(mode="REVERT", confirm="REVERT FLUTTERLOD %s" % orig["run"])
    check(rec["status"] == "PASS" and len(rec["skipped_already_original"]) == 13 and not env.u.SAVED,
          "REVERT after a failed APPLY: all 13 skipped as already original, nothing saved")
    env.close()

    env = Env()
    _, confirm = dry_then_confirm(env)
    env.u.faults.add("lod_lie")
    ok, msg = env.fails("LOD_READBACK_SET", mode="APPLY", confirm=confirm, decided_by="Gary")
    check(ok, "APPLY(-): lying LOD setter caught by read-back")
    check(len(env.u.SAVED) == 5 and all("/Mats/" in p for p in env.u.SAVED), "APPLY(-): only the verified MI batch was saved")
    env.u.faults.clear()
    orig = json.loads((env.dir / "flutter_lod_originals_ACTIVE.json").read_text(encoding="utf-8"))
    check(orig["progress"] and orig["progress"][0]["kind"] == "mi", "originals record the saved MI batch")
    env.restart_dont_save()
    rec = env.run(mode="REVERT", confirm="REVERT FLUTTERLOD %s" % orig["run"])
    check(rec["status"] == "PASS" and env.eff("MI_P04_a_Flap", "FlutterAmpCm") == 3.0, "REVERT after partial APPLY restores the MIs")
    env.close()


@test
def t_census_guards():
    for fault, prefix in (("lod_dirties_map", "MAP_CENSUS_CHANGED"), ("lod_dirties_other", "CENSUS_GAINED_NOT_EXACTLY_TARGETS")):
        env = Env()
        _, confirm = dry_then_confirm(env)
        env.u.faults.add(fault)
        ok, msg = env.fails(prefix, mode="APPLY", confirm=confirm, decided_by="Gary")
        check(ok, "APPLY(-): %s -> %s" % (fault, prefix))
        check(not any("/Meshes/" in p for p in env.u.SAVED), "APPLY(-): no mesh saved after %s" % fault)
        check(env.sizes("P04_a") == [2.0, 0.75], "APPLY(-): failed mesh batch rolled back in memory (%s)" % fault)
        env.close()
    env = Env()
    _, confirm = dry_then_confirm(env)
    env.u.DIRTY.add(INST + "MI_P06_e_Flap")
    ok, _ = env.fails("TARGET_DIRTY_AT_START", mode="APPLY", confirm=confirm, decided_by="Gary")
    check(ok, "APPLY(-): target dirty at start refused")
    env.close()


@test
def t_drift_and_env():
    env = Env()
    _, confirm = dry_then_confirm(env)
    env.u.ASSETS[INST + "MI_P06_e_Flap"].scalars.append(env.u.Entry("FlutterAmpCm", 4.0))
    ok, _ = env.fails("CONFIRM_MISMATCH", mode="APPLY", confirm=confirm, decided_by="Gary")
    check(ok, "APPLY(-): state drift since DRY changes the token")
    env.close()
    env = Env()
    _, confirm = dry_then_confirm(env)
    env.run(mode="APPLY", confirm=confirm, decided_by="Gary")
    orig = json.loads((env.dir / "flutter_lod_originals_ACTIVE.json").read_text(encoding="utf-8"))
    for e in env.u.ASSETS[INST + "MI_P05_cloud_Flap"].scalars:
        if e.info.name == "FlutterAmpCm":
            e.value = 5.0
    env.u.SAVED.clear()
    ok, _ = env.fails("MI_DRIFT_SINCE_APPLY", mode="REVERT", confirm="REVERT FLUTTERLOD %s" % orig["run"])
    check(ok and not env.u.SAVED and env.eff("MI_P04_a_Flap", "FlutterAmpCm") == 6.0, "REVERT(-): drift refuses before writing anything")
    env.close()
    env = Env()
    env.u.pie = True
    ok, _ = env.fails("PIE_OR_SIE_ACTIVE", mode="DRY", confirm="DRY FLUTTERLOD")
    check(ok, "env(-): PIE refused")
    env.u.pie, env.u.world_name = False, "/Game/Other/L_Map"
    ok, _ = env.fails("WRONG_WORLD", mode="DRY", confirm="DRY FLUTTERLOD")
    check(ok, "env(-): wrong world refused")
    env.u.world_name = WORLD
    ok, _ = env.fails("PASSAGE_GUID_MISMATCH", mode="DRY", confirm="DRY FLUTTERLOD",
                      target_passages={"Passage 4": "00000000000000000000000000000000"})
    check(ok, "env(-): pinned passage GUID mismatch refused")
    ok, _ = env.fails("AMP_ABOVE_MAX_CM", mode="DRY", confirm="DRY FLUTTERLOD", values={"FlutterAmpCm": 7.0, "FlutterHz": 0.9})
    check(ok, "args(-): amplitude above FlutterMaxCm refused")
    ok, _ = env.fails("UNKNOWN_ARGS", mode="DRY", confirm="DRY FLUTTERLOD", include_shared_mesh=True)
    check(ok, "args(-): misspelt arg refused")
    env.close()


@test
def t_include_shared():
    env = Env()
    plan, confirm = dry_then_confirm(env, include_shared_meshes=True)
    check(any(t["path"].endswith("SM_FlatV3_P02_IND_Roller_L") for t in plan["mesh_targets"]), "include_shared(+): roller mesh targeted")
    check(not any(t["path"].endswith("MI_P02_Roller_Flap") for t in plan["mi_targets"]), "include_shared: MI sharing still refuses")
    env.run(mode="APPLY", confirm=confirm, decided_by="Gary", include_shared_meshes=True)
    check(env.sizes("roller") == [2.0, 0.3], "include_shared: roller LOD1 0.3")
    env.close()


def main():
    errors = []
    for fn in TESTS:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            import traceback
            errors.append("%s: %s" % (fn.__name__, traceback.format_exc()))
            CHECKS["failed"].append("EXCEPTION in %s: %s" % (fn.__name__, exc))
    report = {"tests": len(TESTS), "checks": CHECKS["n"], "failed": CHECKS["failed"], "errors": errors,
              "results": RESULTS, "cannot_show": __doc__.split("What it CANNOT show:")[1].strip()}
    REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    for f in CHECKS["failed"]:
        print("FAIL", f)
    for e in errors:
        print(e)
    print("FLUTTERLOD_HARNESS|tests=%d|checks=%d|failed=%d" % (len(TESTS), CHECKS["n"], len(CHECKS["failed"])))
    return 1 if CHECKS["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
