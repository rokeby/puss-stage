"""Offline harness for the S3 shore ground (no Unreal, no Blender needed).

python Saved/CodexConductor/S3Shore/test_s3_shore_offline.py
Each check is run on the shipped PARAMS (must pass) and on a broken copy (must FAIL),
so a verifier that cannot fail is caught.  Writes test_s3_shore_offline_report.json.
"""
import copy
import tempfile
import types
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s3_shore_field as F  # noqa: E402

PROJECT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MANIFEST = os.path.join(PROJECT, "DerivedAssets", "S3Shore", "SM_S3_ShoreGround_manifest.json")


# ----------------------------------------------------------------------------- BENCH_PIE mocks (no Unreal)
class _Spy:
    """Records every attribute name read on a fake unreal library (the 'no save call' check reads this)."""
    def __init__(self, spy_name, spy_log, **attrs):
        object.__setattr__(self, "_n", spy_name)
        object.__setattr__(self, "_log", spy_log)
        object.__setattr__(self, "_a", attrs)

    def __getattr__(self, k):
        self._log.append("%s.%s" % (self._n, k))
        if k in self._a:
            return self._a[k]
        raise AttributeError("%s has no %s" % (self._n, k))


def _make_fake(state):
    calls = state["calls"]

    class Obj:
        def __init__(self, path):
            self.path = path

        def get_path_name(self):
            return self.path

        def get_name(self):
            return self.path.rsplit(".", 1)[-1].rsplit("/", 1)[-1]

    class StaticMesh(Obj):
        slots = 1

    class MaterialInterface(Obj):
        pass

    class Vector:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x, self.y, self.z = float(x), float(y), float(z)

    class Rotator:
        def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
            self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)

    class Quat:
        def __init__(self, r):
            self.r = r

        def rotator(self):
            return self.r

    class Transform:
        def __init__(self, location=None, rotation=None, scale=None):
            self.translation = location or Vector()
            self.rotation = Quat(rotation or Rotator())
            self.scale3d = scale or Vector(1, 1, 1)

    class PrimitiveComponent:
        def __init__(self, name, owner):
            self.name, self.owner, self.visible, self.hidden_in_game = name, owner, True, False

        def get_name(self):
            return self.name

        def is_visible(self):
            return self.visible

        def set_visibility(self, v, prop):
            calls.append(("set_visibility", self.owner.name, v, os.path.isfile(state.get("opath", ""))))
            self.visible = bool(v)

    class SMC(PrimitiveComponent):
        def __init__(self, name, owner, mesh, mats, rel):
            super().__init__(name, owner)
            self.mesh, self.overrides, self.rel, self.mobility = mesh, list(mats), rel, "<ComponentMobility.MOVABLE: 2>"

        def get_editor_property(self, k):
            return {"static_mesh": self.mesh, "hidden_in_game": self.hidden_in_game, "mobility": self.mobility}[k]

        def set_static_mesh(self, m):
            calls.append(("set_static_mesh", m.get_path_name(), os.path.isfile(state.get("opath", ""))))
            if m is self.mesh:
                return False                                   # engine behaviour the code must tolerate
            self.mesh = m
            return True

        def get_num_materials(self):
            return self.mesh.slots

        def get_material(self, i):
            return self.overrides[i] if i < len(self.overrides) and self.overrides[i] else state["defaults"][self.mesh.path]

        def set_material(self, i, m):
            calls.append(("set_material", i, m.get_path_name() if m else None, os.path.isfile(state.get("opath", ""))))
            while len(self.overrides) <= i:
                self.overrides.append(None)
            self.overrides[i] = m

        def get_relative_transform(self):
            r = self.rel
            return Transform(Vector(*r["loc"]), Rotator(*r["rpy"]), Vector(*r["scale"]))

        def set_relative_transform(self, t, sweep, teleport):
            rr = t.rotation.rotator()
            self.rel = {"loc": [t.translation.x, t.translation.y, t.translation.z],
                        "rpy": [rr.roll, rr.pitch, rr.yaw], "scale": [t.scale3d.x, t.scale3d.y, t.scale3d.z]}

    class Actor:
        cls_name = "Actor"

        def __init__(self, world, name, label, tags=(), parent=None, loc=(0, 0, 0)):
            self.world, self.name, self.label, self.tags = world, name, label, list(tags)
            self.parent, self.loc, self.hidden, self.comps = parent, loc, False, []
            world.actors.append(self)

        def get_name(self):
            return self.name

        def get_actor_label(self):
            return self.label

        def get_path_name(self):
            return self.world.path + "." + self.name

        def get_world(self):
            return self.world

        def get_class(self):
            return types.SimpleNamespace(get_name=lambda: self.cls_name)

        def get_editor_property(self, k):
            return {"tags": list(self.tags), "hidden": self.hidden}[k]

        def set_editor_property(self, k, v):
            assert k == "tags"
            calls.append(("set_tags", self.name, [str(x) for x in v], os.path.isfile(state.get("opath", ""))))
            self.tags = [str(x) for x in v]

        def set_actor_hidden_in_game(self, v):
            calls.append(("set_actor_hidden_in_game", self.name, v, os.path.isfile(state.get("opath", ""))))
            self.hidden = bool(v)

        def get_attach_parent_actor(self):
            return self.parent

        def get_actor_location(self):
            if self.parent is not None and getattr(self, "static_mesh_component", None) is not None:
                p, r = self.parent.get_actor_location(), self.static_mesh_component.rel["loc"]
                return Vector(p.x + r[0], p.y + r[1], p.z + r[2])
            return Vector(*self.loc)

        def get_components_by_class(self, cls):
            return [c for c in self.comps if isinstance(c, cls)]

        def destroy_actor(self):
            calls.append(("destroy_actor", self.name))
            self.world.actors.remove(self)

    class StaticMeshActor(Actor):
        cls_name = "StaticMeshActor"

    class World:
        def __init__(self, path):
            self.path, self.actors, self.t = path, [], 10.0

        def get_path_name(self):
            return self.path

    names = state["names"]
    ed = types.SimpleNamespace(get_game_world=lambda: state["pie"], get_editor_world=lambda: state["editor"])
    stats = types.SimpleNamespace(get_editor_property=lambda k: state["ps"])
    fake = _Spy("unreal", names,
                Actor=Actor, StaticMeshActor=StaticMeshActor, StaticMesh=StaticMesh, MaterialInterface=MaterialInterface,
                PrimitiveComponent=PrimitiveComponent, Vector=Vector, Rotator=Rotator, Transform=Transform, Name=str,
                UnrealEditorSubsystem=object, get_editor_subsystem=lambda c: ed,
                load_asset=lambda p: state["assets"].get(p.split(".")[0]),   # PIE-safe loader (conductor 7 Oct)
                log=lambda m: state["log"].append(("log", m)), log_error=lambda m: state["log"].append(("error", m)),
                GameplayStatics=_Spy("GameplayStatics", names,
                                     get_all_actors_of_class=lambda w, c: [a for a in w.actors if isinstance(a, c)],
                                     get_real_time_seconds=lambda w: w.t),
                EditorAssetLibrary=_Spy("EditorAssetLibrary", names,
                                        does_asset_exist=lambda p: p in state["assets"],
                                        load_asset=lambda p: state["assets"].get(p.split(".")[0])),
                MaterialEditingLibrary=_Spy("MaterialEditingLibrary", names, get_statistics=lambda m: stats),
                EditorLoadingAndSavingUtils=_Spy("EditorLoadingAndSavingUtils", names,
                                                 get_dirty_content_packages=lambda: [Obj(p) for p in state["dirty"]["content"]],
                                                 get_dirty_map_packages=lambda: [Obj(p) for p in state["dirty"]["maps"]]))
    return fake, dict(World=World, Actor=Actor, StaticMeshActor=StaticMeshActor, SMC=SMC,
                      PrimitiveComponent=PrimitiveComponent, StaticMesh=StaticMesh, MaterialInterface=MaterialInterface)


def _pie_scene(U, with_pie=True, assets=True, stale_tag=False):
    state = {"calls": [], "names": [], "log": [], "ps": 120, "dirty": {"content": ["/Game/ZZ_Bench/x"], "maps": []}}
    fake, K = _make_fake(state)
    cube = K["StaticMesh"]("/Engine/BasicShapes/Cube.Cube")
    oak = K["MaterialInterface"]("/Game/EnvironmentPacks/4K_WoodFlooring_Vol_01/Materials/MI_Oak.MI_Oak")
    state["defaults"] = {cube.path: oak, U.MESH: K["MaterialInterface"]("/Engine/WorldGridMaterial.WorldGridMaterial")}
    state["assets"] = {cube.path.split(".")[0]: cube, oak.path.split(".")[0]: oak}
    if assets:
        state["assets"].update({U.MESH: K["StaticMesh"](U.MESH + ".SM_S3_ShoreGround"),
                                U.MI: K["MaterialInterface"](U.MI + ".MI_S3_ShoreGround"),
                                U.MASTER: K["MaterialInterface"](U.MASTER + ".M_S3_ShoreGround")})
        state["defaults"][state["assets"][U.MESH].path] = state["defaults"].pop(U.MESH)
    W = K["World"]
    editor = W("/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.L_InfinityStage_V1VerticalSlice")
    pie = W("/Game/InfinityStage/Dev/Maps/UEDPIE_0_L_InfinityStage_V1VerticalSlice.L_InfinityStage_V1VerticalSlice")
    root = K["Actor"](pie, "Actor_Root_1", U.ROOT_LABEL, loc=(11421.97275, 160000.0, -3620.0))   # NOT landed (PIE start)
    deck = K["StaticMeshActor"](pie, "StaticMeshActor_77", U.DECK_LABEL, tags=["Hangar"], parent=root)
    deck.static_mesh_component = K["SMC"]("StaticMeshComponent0", deck, cube, [oak],
                                           {"loc": [3000.0, 0.0, 105.0], "rpy": [0.0, 0.0, 0.0], "scale": [60.0, 20.0, 0.2]})
    deck.comps = [deck.static_mesh_component]
    v2 = K["StaticMeshActor"](pie, "StaticMeshActor_88", U.V2_SAND_LABEL, parent=root)
    v2.comps = [K["PrimitiveComponent"]("StaticMeshComponent0", v2), K["PrimitiveComponent"]("Skirt", v2)]
    mg = K["StaticMeshActor"](pie, "DecalActor_ZZ1", "", tags=["ZZ_S3MG"])                       # the marble bench's
    if stale_tag:
        K["Actor"](pie, "Leftover", "", tags=[U.PIE_TAG])
    state.update(pie=pie if with_pie else None, editor=editor, deck=deck, v2=v2, mg=mg, root=root, K=K)
    return fake, state


def run_pie_cases(U):
    import glob
    import io
    out = []

    def add(case, ok, info=None):
        out.append({"case": "BENCH_PIE: " + case, "ok": bool(ok), "info": info})

    saved_unreal, saved_here = U.unreal, U.HERE
    tmp = tempfile.mkdtemp(prefix="s3shore_pie_mock_").replace("\\", "/") + "/"
    U.HERE = tmp
    mutators = ("set_static_mesh", "set_material", "set_actor_hidden_in_game", "set_visibility", "set_tags")

    def raises(fn, token):
        try:
            fn()
            return False, "no raise"
        except Exception as e:  # noqa: BLE001
            return token in str(e), str(e)[:200]

    try:
        # + apply in PIE
        fake, st = _pie_scene(U)
        U.unreal = fake
        st["opath"] = U.pie_file("originals", "T1")
        rec = U.run_bench_pie_apply("T1", {})
        smc = st["deck"].static_mesh_component
        add("+ apply: deck PIE copy -> SM_S3_ShoreGround/MI, relative identity, our tag; v2 hidden; complete",
            rec["complete"] and smc.mesh.path.startswith(U.MESH) and smc.rel["loc"] == [0.0, 0.0, 0.0]
            and smc.rel["scale"] == [1.0, 1.0, 1.0] and U.PIE_TAG in st["deck"].tags and "Hangar" in st["deck"].tags
            and st["v2"].hidden and not any(c.visible for c in st["v2"].comps), rec.get("deck_after"))
        muts = [c for c in st["calls"] if c[0] in mutators]
        flags = [c[-1] for c in muts]
        add("+ apply: originals file existed before EVERY mutation", muts and all(flags), muts[:3])
        add("+ apply: never spawns / destroys / ends PIE", not any(c[0] == "destroy_actor" for c in st["calls"])
            and not [n for n in st["names"] if ("spawn" in n.lower() or "end_play" in n.lower())
                     and n != "GameplayStatics.begin_deferred_actor_spawn_from_class"],   # hasattr probe only
            [n for n in st["names"] if "spawn" in n.lower()])
        add("+ apply: ZZ_S3MG actor untouched", st["mg"] in st["pie"].actors and st["mg"].tags == ["ZZ_S3MG"])
        # + restore (PIE live) -> exact originals, ZZ_S3MG untouched, nothing destroyed
        st["calls"].clear()
        res = U.run_bench_pie_restore("T1R", {"bench_run": "T1"})
        orig = json.load(open(U.pie_file("originals", "T1"), encoding="utf-8"))
        add("+ restore: deck/v2 back to the originals file, our tag removed, other tags kept",
            res.get("restored") and smc.mesh.path == orig["deck"]["mesh"] and smc.rel == orig["deck"]["rel"]
            and st["deck"].tags == ["Hangar"] and not st["v2"].hidden and all(c.visible for c in st["v2"].comps)
            and res["still"] == "STILL_STATE_HELD", res)
        add("+ restore: removes only OUR tag (ZZ_S3MG actor + tag untouched, nothing destroyed)",
            st["mg"] in st["pie"].actors and st["mg"].tags == ["ZZ_S3MG"]
            and not any(c[0] == "destroy_actor" for c in st["calls"])
            and not any(c[1] == st["mg"].name for c in st["calls"] if len(c) > 1), st["calls"][:4])
        res2 = U.run_bench_pie_restore("T1R2", {"bench_run": "T1"})
        add("+ restore is idempotent: second call -> NOOP already_restored", "already_restored" in str(res2.get("noop")), res2)
        all_names = list(st["names"])
        add("+ no save attribute touched on any fake library in apply/restore",
            not [n for n in all_names if "save" in n.lower()], [n for n in all_names if "save" in n.lower()])
        # - control for the spy itself
        try:
            fake.EditorAssetLibrary.save_asset
        except AttributeError:
            pass
        add("- control: the spy DOES see a save attribute access", any("save" in n.lower() for n in st["names"]))
        # - refuses without PIE (no file, no mutation)
        fake, st = _pie_scene(U, with_pie=False)
        U.unreal = fake
        ok, msg = raises(lambda: U.run_bench_pie_apply("T2", {}), "NO_PIE_WORLD")
        add("- refuses without PIE (NO_PIE_WORLD; no originals file; no mutation)",
            ok and not os.path.isfile(U.pie_file("originals", "T2")) and not [c for c in st["calls"] if c[0] in mutators], msg)
        # - refuses without the IMPORT/BUILD_MAT assets
        fake, st = _pie_scene(U, assets=False)
        U.unreal = fake
        ok, msg = raises(lambda: U.run_bench_pie_apply("T3", {}), "ASSET_MISSING")
        add("- refuses when SM/MI/master are missing", ok and not [c for c in st["calls"] if c[0] in mutators], msg)
        # - refuses on a stale tag; - refuses while the master shader is pending
        fake, st = _pie_scene(U, stale_tag=True)
        U.unreal = fake
        ok, msg = raises(lambda: U.run_bench_pie_apply("T4", {}), "STALE_BENCH_TAG_IN_PIE")
        add("- refuses when a ZZ_S3ShoreGroundBench-tagged actor already exists", ok, msg)
        fake, st = _pie_scene(U)
        st["ps"] = 0
        U.unreal = fake
        ok, msg = raises(lambda: U.run_bench_pie_apply("T5", {}), "PENDING_COMPILE")
        add("- refuses while M_S3_ShoreGround has 0 PS instructions", ok, msg)
        # - still invalid: something swapped the material back before restore -> restored, but FAILED
        fake, st = _pie_scene(U)
        U.unreal = fake
        U.run_bench_pie_apply("T6", {})
        st["deck"].static_mesh_component.overrides = [None]           # e.g. a Show recompile reset overrides
        ok, msg = raises(lambda: U.run_bench_pie_restore("T6R", {"bench_run": "T6"}), "RESTORED_BUT_STILL_INVALID")
        add("- control: lost bench state before the still is caught (restored, then FAILED)",
            ok and st["deck"].static_mesh_component.mesh.path.startswith("/Engine/BasicShapes/Cube"), msg)
        # + PIE gone -> NOOP (never OK)
        st["pie"] = None
        r = U.run_bench_pie_restore("T6R2", {"bench_run": "T6"})
        add("+ restore after PIE ended -> NOOP pie=gone", "pie=gone" in str(r.get("noop")), r)
        # - apply whose own census check fails mid-way restores itself (no restore error logged)
        fake, st = _pie_scene(U)
        U.unreal = fake
        orig_set = st["v2"].set_actor_hidden_in_game

        def dirtying(v):
            orig_set(v)
            st["dirty"]["maps"] = [U.WORLD]                            # as if the PIE edit dirtied the editor map
        st["v2"].set_actor_hidden_in_game = dirtying
        ok, msg = raises(lambda: U.run_bench_pie_apply("T7", {}), "EDITOR_PACKAGES_DIRTIED")
        st["v2"].set_actor_hidden_in_game = orig_set
        smc = st["deck"].static_mesh_component
        add("- editor map dirtied mid-apply -> FAILED and auto-restored (deck + v2), restore itself clean",
            ok and smc.mesh.path.startswith("/Engine/BasicShapes/Cube") and smc.rel["scale"] == [60.0, 20.0, 0.2]
            and U.PIE_TAG not in st["deck"].tags and not st["v2"].hidden and all(c.visible for c in st["v2"].comps)
            and not [m for k, m in st["log"] if k == "error"], msg)

        # runner control flow: refusal logs FAILED and never OK; success logs OK once
        src = open(os.path.join(HERE, "s3_shore_ground_run.py"), encoding="utf-8").read()
        src = src.replace('runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")', "pass")
        src = src.replace('g = runpy.run_path(HERE + "s3_shore_ground_ue.py")', "g = _G")
        src = src.replace('open(HERE + "s3_shore_ground_args.json", encoding="utf-8")', "_ARGS")

        def run_runner(fake, args):
            sys.modules["unreal"] = fake
            try:
                exec(compile(src, "s3_shore_ground_run.py", "exec"),
                     {"_G": vars(U), "_ARGS": io.StringIO(json.dumps(args)), "__name__": "runner"})
            finally:
                sys.modules.pop("unreal", None)

        fake, st = _pie_scene(U, with_pie=False)
        U.unreal = fake
        run_runner(fake, {"mode": "BENCH_PIE_APPLY", "confirm": "BENCH_PIE_APPLY S3SHORE", "run": "T8"})
        msgs = [m for _k, m in st["log"]]
        add("- runner: apply without PIE logs S3SHORE_FAILED (error) and NO _OK",
            any(k == "error" and m.startswith("S3SHORE_FAILED|run=T8|mode=BENCH_PIE_APPLY") and "NO_PIE_WORLD" in m
                for k, m in st["log"]) and not any("_OK|" in m for m in msgs), msgs)
        fake, st = _pie_scene(U)
        U.unreal = fake
        run_runner(fake, {"mode": "BENCH_PIE_APPLY", "confirm": "wrong", "run": "T9"})
        msgs = [m for _k, m in st["log"]]
        add("- runner: wrong confirm -> FAILED, nothing changed",
            any("CONFIRM_MISSING" in m for m in msgs) and not any("_OK|" in m for m in msgs)
            and not [c for c in st["calls"] if c[0] in mutators], msgs)
        st["log"].clear()
        run_runner(fake, {"mode": "BENCH_PIE_APPLY", "confirm": "BENCH_PIE_APPLY S3SHORE", "run": "T10"})
        run_runner(fake, {"mode": "BENCH_PIE_RESTORE", "confirm": "BENCH_PIE_RESTORE S3SHORE", "run": "T10R",
                          "bench_run": "T10"})
        run_runner(fake, {"mode": "BENCH_PIE_RESTORE", "confirm": "BENCH_PIE_RESTORE S3SHORE", "run": "T10R2",
                          "bench_run": "T10"})
        msgs = [m for _k, m in st["log"]]
        add("+ runner: apply OK -> restore OK -> second restore NOOP (one marker each, in order)",
            [m.split("|")[0] for m in msgs if "S3SHORE_BENCH_PIE_" in m and "ORIGINALS" not in m] ==
            ["S3SHORE_BENCH_PIE_APPLY_OK", "S3SHORE_BENCH_PIE_RESTORE_OK", "S3SHORE_BENCH_PIE_RESTORE_NOOP"]
            and not any(k == "error" for k, _m in st["log"]), msgs)
        run_runner(fake, {"mode": "VERIFY", "confirm": "VERIFY S3SHORE", "run": "T11"})
        msgs = [m for _k, m in st["log"]]
        add("- runner: VERIFY still refused (APPLY/REVERT enabled 7 Oct evening)",
            any("MODE_NOT_ENABLED_IN_RUNNER|VERIFY" in m for m in msgs))
    finally:
        U.unreal, U.HERE = saved_unreal, saved_here
        for f in glob.glob(tmp + "*.json"):
            os.remove(f)
        try:
            os.rmdir(tmp)
        except OSError:
            pass

    # static scan of the BENCH_PIE section (code only)
    usrc = open(os.path.join(HERE, "s3_shore_ground_ue.py"), encoding="utf-8").read()
    sec = usrc.split("# BEGIN_BENCH_PIE")[1].split("# END_BENCH_PIE")[0]
    code = "\n".join(ln.split("#")[0] for ln in sec.splitlines() if not ln.strip().startswith("#"))

    def scan(c):
        return [t for t in ("save_asset", "save_map", "save_current_level", "save_packages", "save_dirty",
                            "save_loaded", "end_play", "request_end_play", "quit_editor", "play_in_editor", "start_pie",
                            "destroy_actor", "spawn_actor", "EditorLevelLibrary", "EditorActorSubsystem",
                            "reload_packages", "load_map") if t in c]
    out.append({"case": "BENCH_PIE section: no save / PIE start-end / destroy / editor-spawn / reload call",
                "ok": not scan(code), "info": scan(code)})
    out.append({"case": "- control: the same scan flags a planted save + destroy",
                "ok": set(scan(code + "\nunreal.EditorAssetLibrary.save_asset(x)\na.destroy_actor()"))
                >= {"save_asset", "destroy_actor"}})
    return out

# ----------------------------------------------------------------------------- APPLY / REVERT mocks (no Unreal)
def _make_editor_fake(U, state):
    """Editor-world fake: every mutation dirties the map (as the real editor does) and is logged with whether the
    record file existed at that moment (record-first check)."""
    calls = state["calls"]
    ns = types.SimpleNamespace

    def mark(name, *a):
        calls.append((name,) + a + (os.path.isfile(U.RECORD),))
        if U.WORLD not in state["dirty"]["maps"]:
            state["dirty"]["maps"].append(U.WORLD)

    class Obj:
        def __init__(self, path):
            self.path = path

        def get_path_name(self):
            return self.path

        def get_name(self):
            return self.path.rsplit(".", 1)[-1].rsplit("/", 1)[-1]

    class Pkg(Obj):
        def get_name(self):                                           # UPackage name = full long package path
            return self.path

    class StaticMesh(Obj):
        def __init__(self, path, box=None):
            super().__init__(path)
            self.box = box or {"min": [-50.0, -50.0, -50.0], "max": [50.0, 50.0, 50.0]}

    class MaterialInterface(Obj):
        pass

    class Vector:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x, self.y, self.z = float(x), float(y), float(z)

    class Rotator:
        def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
            self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)

    class Quat:
        def __init__(self, r):
            self.r = r

        def rotator(self):
            return self.r

    class Transform:
        def __init__(self, location=None, rotation=None, scale=None):
            self.translation = location or Vector()
            self.rotation = Quat(rotation or Rotator())
            self.scale3d = scale or Vector(1, 1, 1)

    class PrimitiveComponent:
        def __init__(self, name, owner):
            self.name, self.owner, self.visible, self.hidden_in_game = name, owner, True, False

        def get_name(self):
            return self.name

        def modify(self):
            calls.append(("modify", self.owner.name))

        def is_visible(self):
            return self.visible

        def get_editor_property(self, k):
            return {"hidden_in_game": self.hidden_in_game}[k]

        def set_visibility(self, v, prop):
            mark("set_visibility", self.owner.name, v)
            self.visible = bool(v)

        def set_hidden_in_game(self, v, prop):
            mark("set_hidden_in_game", self.owner.name, v)
            self.hidden_in_game = bool(v)

    class SMC(PrimitiveComponent):
        def __init__(self, name, owner, mesh=None, rel=None):
            super().__init__(name, owner)
            self.mesh, self.mats = mesh, []
            self.rel = rel or {"loc": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}
            self.mobility, self.collision = "<ComponentMobility.STATIC: 0>", "<CollisionEnabled.QUERY_AND_PHYSICS: 3>"

        def get_editor_property(self, k):
            if k in ("static_mesh", "mobility"):
                return {"static_mesh": self.mesh, "mobility": self.mobility}[k]
            return super().get_editor_property(k)

        def set_static_mesh(self, m):
            mark("set_static_mesh", self.owner.name)
            if m is self.mesh:
                return False
            self.mesh = m
            return True

        def get_material(self, i):
            return self.mats[i] if i < len(self.mats) else None

        def set_material(self, i, m):
            mark("set_material", self.owner.name)
            while len(self.mats) <= i:
                self.mats.append(None)
            self.mats[i] = m

        def set_mobility(self, m):
            mark("set_mobility", self.owner.name)
            self.mobility = m

        def set_collision_enabled(self, c):
            mark("set_collision_enabled", self.owner.name)
            self.collision = c

        def get_collision_enabled(self):
            return self.collision

        def get_relative_transform(self):
            r = self.rel
            return Transform(Vector(*r["loc"]), Rotator(*r["rpy"]), Vector(*r["scale"]))

        def set_relative_transform(self, t, sweep, teleport):
            mark("set_relative_transform", self.owner.name)
            rr = t.rotation.rotator()
            self.rel = {"loc": [t.translation.x, t.translation.y, t.translation.z],
                        "rpy": [rr.roll, rr.pitch, rr.yaw], "scale": [t.scale3d.x, t.scale3d.y, t.scale3d.z]}

    class Actor:
        def __init__(self, world, name, label, tags=(), parent=None, loc=(0.0, 0.0, 0.0)):
            self.world, self.name, self.label, self.tags = world, name, label, list(tags)
            self.parent, self.loc, self.hidden, self.comps, self.folder = parent, loc, False, [], "S3"
            self.static_mesh_component = None
            world.actors.append(self)

        def get_name(self):
            return self.name

        def get_actor_label(self):
            return self.label

        def set_actor_label(self, v):
            mark("set_actor_label", self.name)
            self.label = v

        def get_path_name(self):
            return self.world.path + ":PersistentLevel." + self.name

        def get_world(self):
            return self.world

        def get_class(self):
            return ns(get_name=lambda: type(self).__name__)

        def modify(self):
            calls.append(("modify", self.name))

        def get_editor_property(self, k):
            return {"tags": list(self.tags), "hidden": self.hidden}[k]

        def set_editor_property(self, k, v):
            assert k == "tags"
            mark("set_tags", self.name)
            self.tags = [str(x) for x in v]

        def set_actor_hidden_in_game(self, v):
            mark("set_actor_hidden_in_game", self.name, v)
            self.hidden = bool(v)

        def get_attach_parent_actor(self):
            return self.parent

        def attach_to_actor(self, parent, socket, a, b, c, weld):
            mark("attach_to_actor", self.name, a, b, c)
            self.parent = parent

        def get_folder_path(self):
            return self.folder

        def set_folder_path(self, f):
            mark("set_folder_path", self.name)
            self.folder = f

        def get_actor_location(self):
            smc = self.static_mesh_component
            if self.parent is not None and smc is not None:
                p, r = self.parent.get_actor_location(), smc.rel["loc"]
                return Vector(p.x + r[0], p.y + r[1], p.z + r[2])
            return Vector(*self.loc)

        def get_actor_rotation(self):
            return Rotator()

        def get_actor_transform(self):
            l0 = self.get_actor_location()
            return ns(inverse_transform_location=lambda v: Vector(v.x - l0.x, v.y - l0.y, v.z - l0.z))

        def get_actor_bounds(self, only_colliding):
            l0 = self.get_actor_location()
            smc = self.static_mesh_component
            b = smc.mesh.box if smc is not None and smc.mesh is not None else {"min": [0, 0, 0], "max": [0, 0, 0]}
            o = [(b["min"][i] + b["max"][i]) / 2.0 for i in range(3)]
            e = [(b["max"][i] - b["min"][i]) / 2.0 for i in range(3)]
            return Vector(l0.x + o[0], l0.y + o[1], l0.z + o[2]), Vector(*e)

        def get_components_by_class(self, cls):
            return [c for c in self.comps if isinstance(c, cls)]

    class StaticMeshActor(Actor):
        pass

    class World:
        def __init__(self, path):
            self.path, self.actors = path, []

        def get_path_name(self):
            return self.path

    # --- sequences
    class Key:
        def __init__(self, f, v):
            self.f, self.v = f, v

        def get_time(self):
            return ns(frame_number=ns(value=self.f))

        def get_value(self):
            return self.v

    class Channel:
        def __init__(self, keys=()):
            self.keys = [Key(f, v) for f, v in keys]

        def get_keys(self):
            return list(self.keys)

        def add_key(self, frame, value, time_unit=None):
            self.keys.append(Key(int(frame.value), bool(value)))

    class Section:
        def __init__(self, seq, rng=(0.0, 0.0), mode="PROJECT_DEFAULT", keys=()):
            self.seq, self.rng, self.mode, self.ch = seq, list(rng), mode, Channel(keys)

        def get_all_channels(self):
            return [self.ch]

        def get_completion_mode(self):
            return self.mode

        def set_completion_mode(self, m):
            self.mode = m

        def set_range_seconds(self, a, b):
            self.rng = [a, b]

        def get_start_frame_seconds(self):
            return self.rng[0]

        def get_end_frame_seconds(self):
            return self.rng[1]

    class MovieSceneVisibilityTrack:
        pass

    class Track:
        def __init__(self, seq, cls_name="MovieSceneVisibilityTrack"):
            self.seq, self.cls_name, self.sections = seq, cls_name, []

        def get_class(self):
            return ns(get_name=lambda: self.cls_name)

        def get_sections(self):
            return list(self.sections)

        def add_section(self):
            s = Section(self.seq)
            self.sections.append(s)
            return s

    class Binding:
        def __init__(self, seq, gid, obj, display):
            self.seq, self.gid, self.obj, self.display, self.tracks = seq, gid, obj, display, []

        def get_id(self):
            return self.gid

        def get_display_name(self):
            return self.display

        def get_tracks(self):
            return list(self.tracks)

        def is_valid(self):
            return True

        def add_track(self, cls):
            self.seq.dirty()
            t = Track(self.seq)
            self.tracks.append(t)
            return t

        def remove(self):
            self.seq.dirty()
            self.seq.bindings.remove(self)

    class LevelSequence(Obj):
        def __init__(self, path):
            super().__init__(path)
            self.bindings, self.n = [], 0

        def dirty(self):
            if self.path not in state["dirty"]["content"]:
                state["dirty"]["content"].append(self.path)

        def get_display_rate(self):
            return ns(numerator=30, denominator=1)

        def get_bindings(self):
            return list(self.bindings)

        def locate_bound_objects(self, b, world):
            return [b.obj] if b.obj is not None and b.obj in world.actors else []

        def add_possessable(self, actor):
            self.dirty()
            self.n += 1
            b = Binding(self, "GUID-NEW-%d" % self.n, actor, actor.get_actor_label())
            self.bindings.append(b)
            return b

    class EditorActorSubsystem:
        pass

    class UnrealEditorSubsystem:
        pass

    def spawn(cls, loc, rot, transient):
        state["n"] += 1
        mark("spawn_actor_from_class", "StaticMeshActor_%d" % state["n"])
        a = cls(state["editor"], "StaticMeshActor_%d" % state["n"], "StaticMeshActor", loc=(loc.x, loc.y, loc.z))
        a.static_mesh_component = SMC("StaticMeshComponent0", a)
        a.comps = [a.static_mesh_component]
        if state.get("spawn_hook"):
            state["spawn_hook"]()
        return a

    def destroy(a):
        mark("destroy_actor", a.name)
        a.world.actors.remove(a)
        return True

    def save_map(world, path):
        calls.append(("save_map", path, os.path.isfile(U.RECORD)))
        state["dirty"]["maps"] = []
        return True

    def save_asset(p, only_if_is_dirty=True):
        calls.append(("save_asset", p, os.path.isfile(U.RECORD)))
        state["dirty"]["content"] = [x for x in state["dirty"]["content"] if x != p]
        return True

    ed = ns(get_game_world=lambda: state["pie"], get_editor_world=lambda: state["editor"])
    eas = ns(spawn_actor_from_class=spawn, destroy_actor=destroy)
    fake = _Spy("unreal", state["names"],
                Actor=Actor, StaticMeshActor=StaticMeshActor, StaticMesh=StaticMesh, MaterialInterface=MaterialInterface,
                PrimitiveComponent=PrimitiveComponent, LevelSequence=LevelSequence, Vector=Vector, Rotator=Rotator,
                Transform=Transform, Name=str, UnrealEditorSubsystem=UnrealEditorSubsystem,
                EditorActorSubsystem=EditorActorSubsystem,
                get_editor_subsystem=lambda c: ed if c is UnrealEditorSubsystem else eas,
                load_asset=lambda p: state["assets"].get(p.split(".")[0]),
                log=lambda m: state["log"].append(("log", m)), log_error=lambda m: state["log"].append(("error", m)),
                ComponentMobility=ns(MOVABLE="<ComponentMobility.MOVABLE: 2>"),
                CollisionEnabled=ns(NO_COLLISION="<CollisionEnabled.NO_COLLISION: 0>"),
                AttachmentRule=ns(KEEP_RELATIVE="KEEP_RELATIVE"),
                MovieSceneVisibilityTrack=MovieSceneVisibilityTrack,
                MovieSceneCompletionMode=ns(PROJECT_DEFAULT="PROJECT_DEFAULT", KEEP_STATE="KEEP_STATE",
                                            RESTORE_STATE="RESTORE_STATE"),
                MovieSceneTimeUnit=ns(DISPLAY_RATE="DISPLAY_RATE"), FrameNumber=lambda v: ns(value=int(v)),
                GuidLibrary=ns(conv_guid_to_string=lambda g: g),
                GameplayStatics=_Spy("GameplayStatics", state["names"],
                                     get_all_actors_of_class=lambda w, c: [a for a in w.actors if isinstance(a, c)]),
                EditorAssetLibrary=_Spy("EditorAssetLibrary", state["names"],
                                        does_asset_exist=lambda p: p in state["assets"], save_asset=save_asset),
                EditorLoadingAndSavingUtils=_Spy("EditorLoadingAndSavingUtils", state["names"],
                                                 get_dirty_content_packages=lambda: [Pkg(p) for p in state["dirty"]["content"]],
                                                 get_dirty_map_packages=lambda: [Pkg(p) for p in state["dirty"]["maps"]],
                                                 save_map=save_map))
    return fake, dict(World=World, Actor=Actor, StaticMeshActor=StaticMeshActor, SMC=SMC, Binding=Binding,
                      Track=Track, Section=Section, PrimitiveComponent=PrimitiveComponent, StaticMesh=StaticMesh,
                      MaterialInterface=MaterialInterface, LevelSequence=LevelSequence)


def _editor_scene(U, deck_reveal=False, scene_reveal=False):
    state = {"calls": [], "names": [], "log": [], "n": 0, "pie": None, "dirty": {"content": [], "maps": []}}
    fake, K = _make_editor_fake(U, state)
    man = json.load(open(MANIFEST, encoding="utf-8"))
    mb = man["expected_ue_local_bounds_cm"]
    b_path = U.ASSET_DIR + "/SM_S3_ShoreGround_B"
    cube = K["StaticMesh"]("/Engine/BasicShapes/Cube.Cube")
    rise, scene = K["LevelSequence"](U.RISE), K["LevelSequence"](U.SEQUENCE_PATH)
    state["assets"] = {b_path: K["StaticMesh"](b_path + ".SM_S3_ShoreGround_B", box=mb),
                       U.MESH: K["StaticMesh"](U.MESH + ".SM_S3_ShoreGround", box=mb),
                       U.APPLY_DEFAULT_MI: K["MaterialInterface"](U.APPLY_DEFAULT_MI + ".MI_S3_ShoreGround_v2"),
                       U.RISE: rise, U.SEQUENCE_PATH: scene}
    editor = K["World"](U.WORLD + ".L_InfinityStage_V1VerticalSlice")
    state["editor"] = editor
    root = K["Actor"](editor, "Actor_Root_1", U.ROOT_LABEL, loc=U.ROOT_LANDED_WORLD)
    deck = K["StaticMeshActor"](editor, "StaticMeshActor_243", U.DECK_LABEL, tags=["RigAtmos.S3Deck"], parent=root)
    deck.static_mesh_component = K["SMC"]("StaticMeshComponent0", deck, cube,
                                          {"loc": [3000.0, 0.0, -25.0], "rpy": [0.0, 0.0, 0.0], "scale": [60.0, 20.0, 0.5]})
    deck.comps = [deck.static_mesh_component]
    v2 = K["StaticMeshActor"](editor, "StaticMeshActor_88", U.V2_SAND_LABEL, parent=root)
    v2.static_mesh_component = K["SMC"]("StaticMeshComponent0", v2, cube)
    skirt = K["PrimitiveComponent"]("Skirt", v2)
    skirt.hidden_in_game = True                                       # a non-default original that must come back
    v2.comps = [v2.static_mesh_component, skirt]
    other = K["StaticMeshActor"](editor, "StaticMeshActor_4", "Clam_Pedastal")
    rb = K["Binding"](rise, "2425E62E", other, "Clam_Pedastal")
    t = K["Track"](rise)
    t.sections.append(K["Section"](rise, (0.0, 31.0), "PROJECT_DEFAULT", [(0, False), (139, True)]))
    rb.tracks.append(t)
    rise.bindings.append(rb)
    if deck_reveal:
        db = K["Binding"](rise, "DECKGUID", deck, U.DECK_LABEL)
        t2 = K["Track"](rise)
        t2.sections.append(K["Section"](rise, (0.0, 31.0), "KEEP_STATE", [(0, False), (120, True)]))
        db.tracks.append(t2)
        rise.bindings.append(db)
    if scene_reveal:
        sb = K["Binding"](scene, "SCENEGUID", None, U.DECK_LABEL)        # matched by display name
        t3 = K["Track"](scene)
        t3.sections.append(K["Section"](scene, (0.0, 10.0), "PROJECT_DEFAULT", [(0, True)]))
        sb.tracks.append(t3)
        scene.bindings.append(sb)
    state.update(root=root, deck=deck, v2=v2, rise=rise, scene=scene, K=K, b_path=b_path, other=other)
    return fake, state


def run_apply_cases(U):
    import glob
    import io
    import shutil as _sh
    out = []

    def add(case, ok, info=None):
        out.append({"case": "APPLY: " + case, "ok": bool(ok), "info": info})

    def raises(fn, token):
        try:
            fn()
            return False, "no raise"
        except Exception as e:  # noqa: BLE001
            return token in str(e), str(e)[:240]

    saved = {k: getattr(U, k) for k in ("unreal", "RECORD", "UMAP", "RISE_UASSET", "BACKUP_ROOT")}
    tmp = tempfile.mkdtemp(prefix="s3shore_apply_mock_").replace("\\", "/") + "/"
    for name in ("L_InfinityStage_V1VerticalSlice.umap", "LS_S3_HangarRise.uasset"):
        with open(tmp + name, "wb") as h:
            h.write(name.encode() * 50)
    U.RECORD, U.UMAP, U.RISE_UASSET = tmp + "s3_shore_ground_record.json", tmp + "L_InfinityStage_V1VerticalSlice.umap", \
        tmp + "LS_S3_HangarRise.uasset"
    U.BACKUP_ROOT = tmp + "Backups/PreS3ShoreGround-"
    args_b = {"mesh_name": "SM_S3_ShoreGround_B"}
    muts = ("spawn_actor_from_class", "set_visibility", "set_hidden_in_game", "set_actor_hidden_in_game",
            "set_static_mesh", "set_material", "attach_to_actor", "destroy_actor", "set_tags")

    def snap(st):
        return {k: U._hide_state(st[k]) for k in ("deck", "v2")}

    try:
        # + APPLY (deck has no reveal track)
        fake, st = _editor_scene(U)
        U.unreal = fake
        before = snap(st)
        res = U.run_apply("A1", args_b)
        g = [a for a in st["editor"].actors if a.label == U.ACTOR_LABEL]
        smc = g[0].static_mesh_component if g else None
        rec = json.load(open(U.RECORD, encoding="utf-8"))
        add("+ apply: 'S3 Shore Ground' on the root at relative identity, mesh _B, MI v2, tag, MOVABLE, no collision",
            len(g) == 1 and g[0].parent is st["root"] and smc.rel == U.IDENTITY_REL
            and smc.mesh is st["assets"][st["b_path"]] and smc.mats[0] is st["assets"][U.APPLY_DEFAULT_MI]
            and g[0].tags == [U.TAG] and "MOVABLE" in smc.mobility and "NO_COLLISION" in smc.collision
            and not g[0].hidden and res["reveal_guid"] is None and not res["float_hold_reapply_needed"], res)
        add("+ apply: deck + v2 sand hidden (actor + every component off + hidden in game); census clean; record "
            "saved+applied; backup umap+rise+record",
            all(st[k].hidden and all(not c.visible and c.hidden_in_game for c in st[k].comps) for k in ("deck", "v2"))
            and st["dirty"] == {"content": [], "maps": []} and rec["saved"] and rec["applied"]
            and sorted(os.listdir(U.BACKUP_ROOT + "A1")) == sorted(["L_InfinityStage_V1VerticalSlice.umap",
                                                                     "LS_S3_HangarRise.uasset",
                                                                     "s3_shore_ground_record.json"]), rec.get("backup"))
        m = [c for c in st["calls"] if c[0] in muts]
        saves = [c for c in st["calls"] if c[0] in ("save_map", "save_asset")]
        add("+ apply: record existed before EVERY mutation; exactly one save (the map), no sequence saved",
            m and all(c[-1] for c in m) and [c[0] for c in saves] == ["save_map"], saves)
        # + REVERT exact
        r = U.run_revert("A1R", {})
        add("+ revert: actor destroyed, deck/v2 flags EXACTLY as before (incl. Skirt hidden_in_game), census clean, "
            "record -> .reverted",
            snap(st) == before and not [a for a in st["editor"].actors if a.label == U.ACTOR_LABEL]
            and st["dirty"] == {"content": [], "maps": []} and not os.path.isfile(U.RECORD)
            and os.path.isfile(U.RECORD + ".reverted-A1R") and st["v2"].comps[1].hidden_in_game, r)
        # - dirty census refused, nothing written
        fake, st = _editor_scene(U)
        st["dirty"]["content"] = ["/Game/Klara/SomeLevel"]
        U.unreal = fake
        ok, msg = raises(lambda: U.run_apply("A2", args_b), "DIRTY_EDITOR")
        add("- apply refuses on a dirty census (no record, no mutation)",
            ok and not os.path.isfile(U.RECORD) and not [c for c in st["calls"] if c[0] in muts], msg)
        fake, st = _editor_scene(U)
        U.unreal = fake
        st["dirty"]["maps"] = [U.WORLD]
        ok, msg = raises(lambda: U.run_revert("A2R", {}), "DIRTY_EDITOR")
        add("- revert refuses on a dirty census", ok, msg)
        # - existing record refused, record untouched
        fake, st = _editor_scene(U)
        U.unreal = fake
        with open(U.RECORD, "w", encoding="utf-8") as h:
            h.write('{"run": "OLD"}')
        ok, msg = raises(lambda: U.run_apply("A3", args_b), "RECORD_EXISTS")
        add("- apply refuses when s3_shore_ground_record.json exists (file untouched, no mutation)",
            ok and open(U.RECORD, encoding="utf-8").read() == '{"run": "OLD"}'
            and not [c for c in st["calls"] if c[0] in muts], msg)
        os.remove(U.RECORD)
        # - missing mesh refused (IMPORT not run)
        fake, st = _editor_scene(U)
        del st["assets"][st["b_path"]]
        U.unreal = fake
        ok, msg = raises(lambda: U.run_apply("A4", args_b), "MESH_MISSING")
        add("- apply refuses when SM_S3_ShoreGround_B is missing", ok and not os.path.isfile(U.RECORD), msg)
        # + deck reveal mirrored (RISE copy), RISE saved, float hold flagged; revert removes the binding
        fake, st = _editor_scene(U, deck_reveal=True)
        U.unreal = fake
        n0 = len(st["rise"].bindings)
        before = snap(st)
        res = U.run_apply("A5", args_b)
        g = [a for a in st["editor"].actors if a.label == U.ACTOR_LABEL][0]
        nb = [b for b in st["rise"].bindings if b.obj is g]
        keys = [[k.f, k.v] for k in nb[0].tracks[0].sections[0].ch.keys] if nb else None
        saves = [c[:2] for c in st["calls"] if c[0] in ("save_map", "save_asset")]
        add("+ deck reveal: copied to the new actor (keys/mode), actor hidden in game, rise + map saved, float hold flagged",
            len(nb) == 1 and keys == [[0, False], [120, True]] and nb[0].tracks[0].sections[0].mode == "KEEP_STATE"
            and g.hidden and res["float_hold_reapply_needed"] and ("save_asset", U.RISE) in saves
            and ("save_map", U.WORLD) in saves and st["dirty"] == {"content": [], "maps": []}, saves)
        r = U.run_revert("A5R", {})
        add("+ revert after a reveal copy: binding removed, pedestal + deck bindings kept, flags exact",
            len(st["rise"].bindings) == n0 and not [b for b in st["rise"].bindings if b.obj is g]
            and snap(st) == before and "reveal_removed" in r["done"], r)
        # - deck revealed only in LS_DevScene_03 -> refused before anything
        fake, st = _editor_scene(U, scene_reveal=True)
        U.unreal = fake
        ok, msg = raises(lambda: U.run_apply("A6", args_b), "DECK_REVEAL_IN_SCENE_SEQUENCE_UNSUPPORTED")
        add("- deck visibility track in LS_DevScene_03 -> refused (no record, no mutation)",
            ok and not os.path.isfile(U.RECORD) and not [c for c in st["calls"] if c[0] in muts], msg)
        # - a foreign package dirtied mid-apply -> DIRTY_SCOPE, auto-undo, no live record
        fake, st = _editor_scene(U)
        U.unreal = fake
        before = snap(st)
        st["spawn_hook"] = lambda: st["dirty"]["content"].append("/Game/Klara/AlleyLevel")
        ok, msg = raises(lambda: U.run_apply("A7", args_b), "DIRTY_SCOPE")
        failed = U.RECORD + ".failed-A7"
        frec = json.load(open(failed, encoding="utf-8")) if os.path.isfile(failed) else {}
        add("- foreign package dirtied mid-apply -> DIRTY_SCOPE, nothing saved, auto-undo (actor gone, flags exact), "
            "record -> .failed",
            ok and not [c for c in st["calls"] if c[0] in ("save_map", "save_asset")] and snap(st) == before
            and not [a for a in st["editor"].actors if a.label == U.ACTOR_LABEL] and not os.path.isfile(U.RECORD)
            and "actor_destroyed" in frec.get("auto_undo", []), msg)
        # - revert refuses on drift (someone re-showed the deck) before mutating
        fake, st = _editor_scene(U)
        U.unreal = fake
        U.run_apply("A8", args_b)
        st["deck"].static_mesh_component.visible = True
        st["calls"].clear()
        ok, msg = raises(lambda: U.run_revert("A8R", {}), "READBACK_HIDDEN")
        add("- revert refuses on drift since APPLY (no mutation, actor kept)",
            ok and not [c for c in st["calls"] if c[0] in muts]
            and [a for a in st["editor"].actors if a.label == U.ACTOR_LABEL], msg)
        os.remove(U.RECORD)
        # - refuses in PIE
        fake, st = _editor_scene(U)
        st["pie"] = st["K"]["World"]("/Game/UEDPIE_0_x")
        U.unreal = fake
        ok, msg = raises(lambda: U.run_apply("A9", args_b), "PIE_ACTIVE")
        add("- apply refuses while PIE runs", ok and not os.path.isfile(U.RECORD), msg)
        # mesh_name: default unchanged; B; bad names refused
        add("+ mesh_name default unchanged (SM_S3_ShoreGround, v1 path, v1 import record path)",
            U.mesh_name_of({}) == "SM_S3_ShoreGround" and U.mesh_path_of({}) == U.MESH
            and U.mesh_path_of({"mesh_name": None}) == U.MESH
            and U.import_record_path(U.mesh_name_of({})) == U.RECORD + ".import")
        add("+ mesh_name B -> new asset path + its own import record",
            U.mesh_path_of(args_b) == U.ASSET_DIR + "/SM_S3_ShoreGround_B"
            and U.import_record_path("SM_S3_ShoreGround_B") == U.RECORD + ".import-SM_S3_ShoreGround_B")
        ok, msg = raises(lambda: U.mesh_name_of({"mesh_name": "../SM_S3_ShoreGround"}), "MESH_NAME")
        add("- mesh_name with a path / foreign prefix refused", ok, msg)
        # IMPORT gates (before any import task): existing _B refused; dirty census refused
        fake, st = _editor_scene(U)
        U.unreal = fake
        ok, msg = raises(lambda: U.run_import("I1", args_b), "MESH_EXISTS|" + st["b_path"])
        add("- IMPORT mesh_name=_B refuses when _B already exists (create-only, never reimport)",
            ok and "unreal.AssetImportTask" not in st["names"], msg)
        fake, st = _editor_scene(U)
        st["dirty"]["maps"] = [U.WORLD]
        U.unreal = fake
        ok, msg = raises(lambda: U.run_import("I2", args_b), "DIRTY_EDITOR")
        add("- IMPORT refuses on a dirty census", ok and "unreal.AssetImportTask" not in st["names"], msg)

        # runner: APPLY/REVERT markers
        src = open(os.path.join(HERE, "s3_shore_ground_run.py"), encoding="utf-8").read()
        src = src.replace('runpy.run_path("E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py")', "pass")
        src = src.replace('g = runpy.run_path(HERE + "s3_shore_ground_ue.py")', "g = _G")
        src = src.replace('open(HERE + "s3_shore_ground_args.json", encoding="utf-8")', "_ARGS")

        def run_runner(fake, args):
            sys.modules["unreal"] = fake
            try:
                exec(compile(src, "s3_shore_ground_run.py", "exec"),
                     {"_G": vars(U), "_ARGS": io.StringIO(json.dumps(args)), "__name__": "runner"})
            finally:
                sys.modules.pop("unreal", None)

        fake, st = _editor_scene(U)
        U.unreal = fake
        run_runner(fake, dict(args_b, mode="APPLY", confirm="APPLY", run="R1"))
        msgs = [mm for _k, mm in st["log"]]
        add("- runner: APPLY with the wrong confirm -> FAILED, no record, no mutation",
            any("CONFIRM_MISSING" in mm for mm in msgs) and not any("_OK|" in mm for mm in msgs)
            and not os.path.isfile(U.RECORD) and not [c for c in st["calls"] if c[0] in muts], msgs)
        st["log"].clear()
        run_runner(fake, dict(args_b, mode="APPLY", confirm="APPLY S3SHORE", run="R2"))
        run_runner(fake, {"mode": "REVERT", "confirm": "REVERT S3SHORE", "run": "R2R"})
        run_runner(fake, {"mode": "VERIFY", "confirm": "VERIFY S3SHORE", "run": "R3"})
        msgs = [mm for _k, mm in st["log"]]
        heads = [mm.split("|")[0] for mm in msgs if mm.startswith("S3SHORE_") and not mm.startswith(("S3SHORE_START",
                                                                                                         "S3SHORE_RECORD"))]
        add("+ runner: APPLY_OK -> REVERT_OK (once each, in order), then VERIFY refused",
            heads == ["S3SHORE_APPLY_OK", "S3SHORE_REVERT_OK", "S3SHORE_FAILED"]
            and "MODE_NOT_ENABLED_IN_RUNNER|VERIFY" in msgs[-1]
            and "mesh=" + st["b_path"] in [mm for mm in msgs if mm.startswith("S3SHORE_APPLY_OK")][0], heads)
    finally:
        for k, v in saved.items():
            setattr(U, k, v)
        _sh.rmtree(tmp, ignore_errors=True)
    # static scan of the APPLY section
    usrc = open(os.path.join(HERE, "s3_shore_ground_ue.py"), encoding="utf-8").read()
    sec = usrc.split("# BEGIN_APPLY")[1].split("# END_APPLY")[0]
    code = "\n".join(ln.split("#")[0] for ln in sec.splitlines() if not ln.strip().startswith("#"))

    def scan(c):
        return [t for t in ("EditorAssetLibrary.load_asset", "reload_packages", "load_map", "save_current_level",
                            "save_dirty", "save_packages", "reimport", "replace_existing", "import_asset_tasks",
                            "get_bound_objects", "end_play", "quit_editor") if t in c]
    out.append({"case": "APPLY section: no EditorAssetLibrary.load_asset / reload / Save-All / reimport / "
                        "GetBoundObjects / PIE end", "ok": not scan(code), "info": scan(code)})
    out.append({"case": "- control: the same scan flags planted calls",
                "ok": set(scan(code + "\nunreal.EditorAssetLibrary.load_asset(p)\nx.reimport()"))
                >= {"EditorAssetLibrary.load_asset", "reimport"}})
    return out


def run():
    fp = F.load_footprint()
    results = []

    def case(name, params=None, footprint=None, expect_fail=None):
        p = params or F.PARAMS
        f = footprint or fp
        fails, _ = F.checks(f, p)
        if expect_fail is None:
            ok = not fails
        else:
            ok = any(x.startswith(expect_fail) for x in fails)
        results.append({"case": name, "ok": ok, "failures": fails[:6]})

    case("shipped params pass")
    sets = F.PARAMS["height_set"]
    p = copy.deepcopy(F.PARAMS); p["height_sets"][sets]["print_line_cm"] = 180.0
    case("NEG drift over the (proposed) print line", p, expect_fail="DRIFT_HITS_PRINTS")
    p = copy.deepcopy(F.PARAMS); p["constraints"]["door_corridor_halfwidth_cm"] = 0.0; p["dune"]["door_taper_cm"] = 1.0
    case("NEG door blocked", p, expect_fail="DOOR_GAP_BLOCKED")
    p = copy.deepcopy(F.PARAMS); p["wave_notch"] = False
    case("NEG wave notch off -> drifts/relief under the flats detected", p, expect_fail="WAVE_BASE_NOT_FLUSH")
    # realism (+ shipped passes above; each - control must trip its own check)
    p = copy.deepcopy(F.PARAMS); p["triangle_clamp"] = False; p["final_repose_deg"] = 40.0; p["dune"]["repose_deg"] = 40.0
    case("NEG slip faces over the angle of repose (clamp off, 40 deg talus)", p, expect_fail="SLOPE_OVER_REPOSE")
    p = copy.deepcopy(F.PARAMS); p["wind_ripple"]["height_cm"] = [0.0, 0.0]
    case("NEG wind ripples removed", p, expect_fail="RIPPLES_ABSENT")
    p = copy.deepcopy(F.PARAMS); p["dune"]["steps"] = 0
    case("NEG no wind transport (talus only) -> no lee/windward asymmetry", p, expect_fail="NO_WIND_ASYMMETRY")
    p = copy.deepcopy(F.PARAMS); p["wind_ripple"]["mode"] = "regular"
    case("NEG regular single-sinusoid ripples (the 7 Oct field) -> too regular", p, expect_fail="RIPPLES_TOO_REGULAR")
    p = copy.deepcopy(F.PARAMS)
    p["fine"].update(sand_blur_passes=0, ripples_before_talus=True); p["final_talus_passes"] = 60
    p["dune"]["repose_deg"] = 31.0; p["dune"]["repose_jitter_deg"] = 2.0
    case("NEG the 7 Oct pipeline (no de-terrace blur, ripples before talus) -> terracing", p, expect_fail="TERRACING")
    p = copy.deepcopy(F.PARAMS)
    p["fine"].update(fill_pools_under_sand=False, pools_avoid_sand=False); p["sheet"]["hollow_soft"] = False
    case("NEG the 17:04 field (pools printed into dunes, punched sheet hollows) -> pits on dunes", p,
         expect_fail="PITS_ON_DUNES")
    p = copy.deepcopy(F.PARAMS); p["millstone_seat"] = False
    case("NEG millstone seat not built -> seat not level", p, expect_fail="SEAT_NOT_LEVEL")
    # determinism: two fresh computations byte-identical; a seed change is seen
    import numpy as _np
    F._CACHE.clear()
    g1 = F.grid_sha256(F.build_grid(fp))
    F._CACHE.clear()
    g2 = F.grid_sha256(F.build_grid(fp))
    results.append({"case": "+ determinism: two fresh field builds byte-identical", "ok": g1 == g2, "sha": g1})
    p = copy.deepcopy(F.PARAMS); p["seed"] = p["seed"] + 1
    results.append({"case": "- control: a seed change changes the grid hash", "ok": F.grid_sha256(F.build_grid(fp, p)) != g1})
    # standing-stone proposal: built on THIS field, every keep-out clear, never floating, hole reads from the main cam
    sp = os.path.join(HERE, "standing_stones_proposal.json")
    if os.path.isfile(sp):
        st = json.load(open(sp, encoding="utf-8"))
        ok = st["field_grid_sha256"] == g1 and len(st["placements"]) == 3 and all(r["keepouts_ok"] for r in st["report"])             and all(r["stone_buried_below_low_side_cm"] > 0 for r in st["report"])             and any(r["main_camera"]["hole_in_frame"] and abs(r["main_camera"]["hole_axis_off_view_ray_deg"]) < 35
                    for r in st["report"])             and all(row["prop"] == "HoledStandingStone" and row["xy_root_local"] and "burial_cm" in row
                    for row in st["placements"])
        results.append({"case": "standing stones: on this field, keep-outs clear, buried on the low side, hole reads "
                                "from the main camera", "ok": ok,
                        "info": [(r["label"], r["keepouts_ok"], r["main_camera"]["hole_in_frame"]) for r in st["report"]]})
    else:
        results.append({"case": "standing stones proposal present", "ok": False})
    # height sets for the hand-print stream
    hs_path = F.HEIGHT_SETS_JSON
    if os.path.isfile(hs_path):
        hs = json.load(open(hs_path, encoding="utf-8"))
        ok = hs["recommended"] == F.PARAMS["height_set"] and set(hs["sets"]) == {"A", "B", "C"}
        rows = {}
        for k, v in hs["sets"].items():
            rows[k] = [v["measured_wall_max_cm"]["all"], v["min_print_line_cm_above_floor_top"]]
            ok = ok and not v["checks_failures"] and v["min_print_line_cm_above_floor_top"] <= F.PARAMS["height_sets"][k]["print_line_cm"]                 and abs(v["measured_wall_max_cm"]["all"] - v["target_wall_max_cm"]) <= 0.1 * v["target_wall_max_cm"]
        cur = F.height_set_summary(fp, F.PARAMS, F.build_grid(fp))
        ok = ok and cur["measured_wall_max_cm"] == hs["sets"][F.PARAMS["height_set"]]["measured_wall_max_cm"]
        results.append({"case": "height-set JSON: A/B/C clean, within 10% of target, print lines consistent, matches field",
                        "ok": ok, "info": rows})
    else:
        results.append({"case": "height-set JSON present", "ok": False})
    # Gary 7 Oct: cast area re-sculpted, no v2 preservation, no pads.
    def cast_absent(params):
        _, rep = F.checks(fp, params)
        # <= 0.2: a level seat / thin sheet can coincide with v2 heights by chance; preservation gives ~1.0
        return rep["cast_area_vs_v2"]["fraction_within_0p5cm_of_v2"] <= 0.2, rep["cast_area_vs_v2"]
    ok, info = cast_absent(F.PARAMS)
    results.append({"case": "+ v2 cast preservation ABSENT in shipped field", "ok": ok and not F.PARAMS["preserve_v2_cast"]
                    and not F.PARAMS["use_pads"], "info": info})
    p = copy.deepcopy(F.PARAMS); p["preserve_v2_cast"] = True; p["use_pads"] = True
    ok, info = cast_absent(p)
    results.append({"case": "- control: old preservation switched on IS detected", "ok": not ok, "info": info})

    # seat report: real report + synthetic controls
    import numpy as np
    import s3_shore_seat_report as SR
    grid = F.build_grid(fp)
    surf = SR.Surface(grid)
    box = {"min": [3000.0, -100.0, 0.0], "max": [3060.0, -40.0, 50.0]}
    X, Y = np.meshgrid(np.linspace(3000, 3060, 13), np.linspace(-100, -40, 13), indexing="ij")
    Z = surf(X, Y)
    synth = [{"label": "SYN float", "kind": "synthetic", "base_local_z": float(Z.max()) + 10.0, "aabb": box},
             {"label": "SYN buried", "kind": "synthetic", "base_local_z": float(Z.min()) - 10.0, "aabb": box},
             {"label": "SYN ok", "kind": "synthetic", "base_local_z": float(Z.mean()) + 0.5, "aabb": box}]
    got = {r["label"]: r["verdict"] for r in SR.seat_rows(synth, surf)}
    results.append({"case": "- control: synthetic floating object flagged FLOATING", "ok": got["SYN float"] == "FLOATING"})
    results.append({"case": "- control: synthetic buried object flagged BURIED", "ok": got["SYN buried"] == "BURIED"})
    results.append({"case": "+ control: synthetic seated object OK", "ok": got["SYN ok"] == "OK"})
    rep = SR.build(grid=grid)
    rows = {r["label"]: r for r in rep["rows"]}
    results.append({"case": "seat report from LIVE reads (run, 15 objects, Shore03 foot 130.454 local = 10.45 dock)",
                    "ok": rep["live_reads_run"] == "S3SHORE-20261007-181646" and len(rows) == 15
                    and abs(rows["Shore03_M59 Clam"]["base_local_z"] - 130.454) < 0.01, "counts": rep["counts"]})
    p = copy.deepcopy(F.PARAMS); p["camera_min_vertical_clearance_cm"] = 500.0
    case("NEG camera clearance", p, expect_fail="CAMERA_LOW")

    # editor script (offline-checkable parts)
    import ast
    import s3_shore_ground_ue as U
    results.append({"case": "+ material graph spec has no problems", "ok": not U.graph_problems(), "info": U.graph_problems()})
    saved_edges = list(U.EDGES)
    try:
        U.EDGES[:] = [e for e in U.EDGES if not (e[2] == "SH_Base" and e[3] == "WetD")]
        results.append({"case": "- control: dropping an edge is detected", "ok": bool(U.graph_problems()),
                        "info": U.graph_problems()})
    finally:
        U.EDGES[:] = saved_edges
    src = open(os.path.join(HERE, "s3_shore_ground_run.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    consts = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("ENABLED", "REFUSED"):
            consts[node.targets[0].id] = ast.literal_eval(node.value)
    en, rf = consts.get("ENABLED", {}), consts.get("REFUSED", ())
    ok = (set(en) == {"DRY", "IMPORT", "BUILD_MAT", "BENCH", "BENCH_RESTORE", "BENCH_PIE_APPLY", "BENCH_PIE_RESTORE",
                      "APPLY", "REVERT"}
          and en["DRY"] is None
          and all(en[m] == m + " S3SHORE" for m in en if m != "DRY")
          and set(rf) >= {"VERIFY"} and not (set(rf) & set(en)))
    results.append({"case": "runner: IMPORT/BUILD_MAT/BENCH(+RESTORE)/BENCH_PIE_*/APPLY/REVERT need '<MODE> S3SHORE'; "
                            "VERIFY refused",
                    "ok": ok, "info": {"enabled": en, "refused": rf}})
    results.extend(run_pie_cases(U))
    results.extend(run_apply_cases(U))
    results.append({"case": "runner: no save call in BENCH path",
                    "ok": all(k not in open(os.path.join(HERE, "s3_shore_ground_ue.py"), encoding="utf-8").read()
                              .split("def run_bench(")[1].split("def run_bench_restore(")[0]
                              for k in ("save_asset", "save_map", "save_current_level", "save_packages"))})

    # manifest (built artefact) gates
    if os.path.isfile(MANIFEST):
        m = json.load(open(MANIFEST, encoding="utf-8"))
        b = m["expected_ue_local_bounds_cm"]
        results.append({"case": "manifest bounds asymmetric in Y (mirror detectable)",
                        "ok": abs(b["min"][1] + 1012.0) < 0.5 and abs(b["max"][1] - 1008.0) < 0.5, "bounds": b})
        results.append({"case": "manifest footprint hash matches current footprint",
                        "ok": m["footprint_sha256"] == __import__("hashlib").sha256(
                            open(F.FOOTPRINT, "rb").read()).hexdigest()})
        results.append({"case": "fbx exists and hash matches manifest",
                        "ok": os.path.isfile(m["fbx"]) and __import__("hashlib").sha256(
                            open(m["fbx"], "rb").read()).hexdigest() == m["fbx_sha256"]})
        results.append({"case": "manifest built with no field failures", "ok": not m["checks_failures"]})
        # the Blender build (its own numpy) and this harness must compute the SAME grid
        npy = os.path.join(PROJECT, "DerivedAssets", "S3Shore", "SM_S3_ShoreGround_grid_h.npy")
        if os.path.isfile(npy):
            hb = _np.load(npy)
            ho = F.build_grid(fp)["h"]
            diff = float(_np.abs(hb - ho).max()) if hb.shape == ho.shape else 1e9
        else:
            diff = 1e9
        results.append({"case": "Blender-built heights == harness heights (max |dh| <= 0.05 cm; exact sha reported)",
                        "ok": diff <= 0.05 and m.get("height_set") == F.PARAMS["height_set"],
                        "info": {"blender_numpy": m.get("blender_numpy"), "max_abs_dh_cm": diff,
                                 "sha_equal": m.get("grid_sha256") == g1}})
        seat = (m.get("checks") or {}).get("millstone_seat")
        results.append({"case": "manifest records the millstone seat (level within its radius)",
                        "ok": bool(seat) and seat["range_within_radius_cm"] <= 1.0, "info": seat})
        det_p = os.path.join(PROJECT, "DerivedAssets", "S3Shore", "SM_S3_ShoreGround_determinism_log.json")
        det = json.load(open(det_p, encoding="utf-8")) if os.path.isfile(det_p) else []
        def same_build(pair, fbx_sha):
            return (len(pair) == 2 and pair[0]["params_sha256"] == pair[1]["params_sha256"]
                    and pair[0]["fbx_sha256"] == pair[1]["fbx_sha256"] == fbx_sha)
        last = det[-2:]
        results.append({"case": "+ determinism: the last two Blender builds of the same params wrote byte-identical FBX",
                        "ok": same_build(last, m["fbx_sha256"]), "info": last})
        tampered = copy.deepcopy(last)
        if tampered:
            tampered[-1]["fbx_sha256"] = "0" * 64
        results.append({"case": "- control: a differing FBX hash in the log is caught",
                        "ok": not same_build(tampered, m["fbx_sha256"])})
    else:
        results.append({"case": "manifest present", "ok": False})
    report = {"passed": sum(r["ok"] for r in results), "total": len(results), "results": results}
    with open(os.path.join(HERE, "test_s3_shore_offline_report.json"), "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1)
    print("S3SHORE_OFFLINE %d/%d" % (report["passed"], report["total"]))
    for r in results:
        print(("PASS " if r["ok"] else "FAIL ") + r["case"])
    return report["passed"] == report["total"]


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
