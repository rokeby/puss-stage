"""Offline harness for look_bench.py (no Unreal). Each property has a + case and a
- control that must FAIL, so the checks are shown able to fail.
Run: python Saved/CodexConductor/test_look_bench.py"""
import copy
import inspect
import json
import math
import pathlib
import re
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import look_bench as lb  # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def raises(fn, token):
    try:
        fn()
    except Exception as exc:
        return token in str(exc)
    return False


EDGE_MAT = "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master.M_Wing_CanvasEdge_Master"
MAP = "L_InfinityStage_V1VerticalSlice"


class World:
    """Shared fake: bay 3/4/5 lights, census, pool of tagged actors."""

    def __init__(self, kind):
        self.kind = kind
        self.events = []
        self.lights = {}
        for bay, x in ((3, -1000.0), (4, 0.0), (5, 1000.0)):
            for i, (lbl, typ, inten, cs, vsi) in enumerate((
                    ("LOW_SIDE_L_KEY", "spot", 900.0, True, 0.45), ("LOW_SIDE_R_FILL", "spot", 56.25, False, 0.45),
                    ("TOP_L", "spot", 0.0, False, 0.25), ("PRACTICAL_L", "point", 1300.0, False, 0.2),
                    ("FENCE_BEAM", "spot", 3000.0, False, 0.6), ("WASH", "rect", 400.0, False, 0.6))):
                lid = "/X/P04_B%d_%d" % (bay, i)
                y = 240000.0 + (-1450.0 if i % 2 == 0 else 1450.0)
                self.lights[lid] = {"label": "P04 LOOK B%02d INDUSTRIAL %s" % (bay, lbl), "type": typ,
                                    "location": (x + 40.0, y, 100.0), "intensity": inten, "visible": True,
                                    "cast_shadows": cs, "cast_volumetric_shadow": False,
                                    "volumetric_scattering_intensity": vsi}
        self.actors = {}          # label -> {"tag": bool, "on": bool, "kind", "spec", "intensity"}
        self.dirty = {"maps": [], "content": []}

    def note(self, e): self.events.append(e)
    def log(self, m): self.events.append(("log", m))
    def census(self): return copy.deepcopy(self.dirty)

    def find_lights(self, prefixes):
        return sorted(l for l, r in self.lights.items() if r["label"].startswith(tuple(prefixes))
                      or any(r["label"].startswith(p.replace("Wing", "LOOK")) for p in prefixes))

    def read_light(self, lid): return copy.deepcopy(self.lights[lid])
    def bench_actor_labels(self, prefix): return sorted(l for l in self.actors if l.startswith(prefix))
    def pool_labels(self): return sorted(l for l, a in self.actors.items() if a["tag"] and l.startswith(lb.SPAWN_PREFIX))
    def pool_state(self, label): return {"on": self.actors[label]["on"]}

    def spawn(self, spec):                      # exists so a rogue call is RECORDED, not an AttributeError
        self.events.append(("spawn", spec["label"]))
        self.actors[spec["label"]] = {"tag": True, "on": True, "kind": spec["kind"], "spec": spec}
        return spec["label"]

    def logs(self, token): return [e[1] for e in self.events if isinstance(e, tuple) and e[0] == "log" and token in e[1]]


class EditorFake(World):
    def __init__(self, pie_running=False):
        super().__init__("editor")
        self.pie_running = pie_running

    def world_kind(self): return "pie_running" if self.pie_running else "editor"
    def world_name(self): return "/Game/InfinityStage/Dev/Maps/%s.%s" % (MAP, MAP)

    def spawn_hidden(self, spec):
        self.events.append(("spawn", spec["label"]))
        self.actors[spec["label"]] = {"tag": True, "on": False, "kind": spec["kind"], "spec": None}
        if MAP not in self.dirty["maps"]:
            self.dirty["maps"].append(MAP)
        return "/Game/Maps/%s:PersistentLevel.%s" % (MAP, spec["label"])

    def destroy_pool(self, label):
        self.events.append(("destroy", label))
        self.actors.pop(label)


class PieFake(World):
    """A PIE duplicate of an editor fake (pool copied, lights copied), plus edge slots."""

    def __init__(self, editor=None, kind="game"):
        super().__init__(kind)
        if editor is not None:
            self.lights = copy.deepcopy(editor.lights)
            self.actors = copy.deepcopy(editor.actors)
            self.dirty = copy.deepcopy(editor.dirty)
        self.slots = {("/PIE/Flat_A.ISM0", 3): EDGE_MAT, ("/PIE/Flat_B.ISM0", 3): EDGE_MAT}
        self.cvars = {lb.STREAM_CVAR: 0}

    def world_kind(self): return self.kind
    def world_name(self): return "/Game/InfinityStage/Dev/Maps/UEDPIE_0_%s.%s" % (MAP, MAP)

    def set_light(self, lid, field, value):
        self.events.append(("set_light", lid, field))
        self.lights[lid][field] = value

    def edge_slots(self, box):
        return [{"id": c, "slot": s, "material": m} for (c, s), m in sorted(self.slots.items())]

    def slot_material(self, cid, slot): return self.slots[(cid, slot)]

    def set_slot_material(self, cid, slot, spec):
        self.events.append(("set_slot", cid, slot))
        self.slots[(cid, slot)] = spec.get("path") or "MID(%s)" % spec["mid_parent"]

    def show_pool(self, spec):
        self.events.append(("show", spec["label"]))
        a = self.actors[spec["label"]]
        if a["kind"] != spec["kind"]:
            raise RuntimeError("LOOK_BENCH_POOL_KIND|" + spec["label"])
        a.update(on=True, spec=spec, intensity=spec.get("cd"))

    def hide_pool(self, label):
        self.events.append(("hide", label))
        self.actors[label].update(on=False, intensity=0.0)

    def set_pool_intensity(self, label, v): self.actors[label]["intensity"] = v
    def material_readback(self, label): return dict(self.actors[label]["spec"]["material"].get("scalars", {}))
    def get_cvar(self, n): return self.cvars[n]
    def set_cvar(self, n, v): self.cvars[n] = int(v)


def first_index(events, pred):
    for i, e in enumerate(events):
        if pred(e):
            return i
    return None


def is_change(e):
    return isinstance(e, tuple) and e[0] in ("set_light", "set_slot", "spawn", "show", "hide", "destroy")


def shown(fake): return sorted(l for l, a in fake.actors.items() if a["on"])


tmp = pathlib.Path(tempfile.mkdtemp(prefix="look_bench_test_"))
ALL = ("shadows", "haze", "rake", "floor_wet", "strobe", "edge")
BAYS = [{"bay": 4}]


def prepared(n=""):
    ed = EditorFake()
    rec = lb.PrepareBench(ed, tmp / ("prep%s.json" % n), BAYS, {}, "P" + str(n)).run()
    return ed, rec


# ---------------- PREPARE (editor world) ----------------
ed, prep = prepared(1)
iw = first_index(ed.events, lambda e: e == "record_written")
ic = first_index(ed.events, is_change)
check("+ PREPARE: record written (labels + census) before the first spawn", iw is not None and ic is not None and iw < ic)
disk = json.loads((tmp / "prep1.json").read_text(encoding="utf-8"))
check("+ PREPARE: record holds every label, every spawned path, census before/after, status spawned",
      disk["status"] == "spawned" and len(disk["pool"]) == len(disk["spawned"]) == len(ed.actors)
      and disk["census_before"] == {"maps": [], "content": []} and disk["dirtied_by_prepare"]["maps"] == [MAP])
check("+ PREPARE: every pool actor is ZZ_LOOKBENCH_-labelled, tagged and HIDDEN",
      ed.actors and all(l.startswith("ZZ_LOOKBENCH_") and a["tag"] and not a["on"] for l, a in ed.actors.items()))
kinds = {}
for a in ed.actors.values():
    kinds[a["kind"]] = kinds.get(a["kind"], 0) + 1
labels = set(ed.actors)
check("+ PREPARE: pool covers fog x3, lights (beam, rakes, strobe, glint, shaft), floor+5 puddles, underpass, arches, spare ties",
      kinds.get("fog") == 3 and kinds.get("point") == 1 and kinds.get("spot") == 5
      and {"ZZ_LOOKBENCH_FLOOR", "ZZ_LOOKBENCH_GLINT_BULB", "ZZ_LOOKBENCH_UP_SHAFT"} <= labels
      and sum(l.startswith("ZZ_LOOKBENCH_PUDDLE_") for l in labels) == 5
      and sum(l.startswith("ZZ_LOOKBENCH_ARCH_") for l in labels) == 3 * 2 * 6
      and sum(l.startswith("ZZ_LOOKBENCH_UP_TIE_") for l in labels) >= 11 + 10)
check("+ PREPARE: logs LOOK_BENCH_PREPARED with counts and the Don't-Save-restart marker",
      bool(ed.logs("LOOK_BENCH_PREPARED|")) and "actors=%d" % len(ed.actors) in ed.logs("LOOK_BENCH_PREPARED|")[0]
      and bool(ed.logs(lb.RESTART_MARKER)))
# - control: a prepare that spawns before writing is caught by the same ordering check
ed_bad = EditorFake()
ed_bad.spawn_hidden({"label": "ZZ_LOOKBENCH_EARLY", "kind": "spot"})
ed_bad.actors.clear(); ed_bad.dirty = {"maps": [], "content": []}
lb.PrepareBench(ed_bad, tmp / "prepbad.json", BAYS, {}, "Pbad").run()
iw2 = first_index(ed_bad.events, lambda e: e == "record_written")
ic2 = first_index(ed_bad.events, is_change)
check("- control: spawn-before-record is detected by the ordering check", not (iw2 is not None and ic2 is not None and iw2 < ic2))
check("+ PREPARE refuses while PIE is running", raises(lambda: lb.PrepareBench(EditorFake(True), tmp / "a.json", BAYS).run(),
                                                     "LOOK_BENCH_PREPARE_NEEDS_EDITOR"))
dirty_ed = EditorFake(); dirty_ed.dirty["content"].append("DA_InfinityStage_V1Show")
check("+ PREPARE refuses on a dirty census (a Don't-Save restart must lose nothing)",
      raises(lambda: lb.PrepareBench(dirty_ed, tmp / "b.json", BAYS).run(), "LOOK_BENCH_DIRTY_BEFORE_PREPARE")
      and not dirty_ed.actors)
left_ed = EditorFake()
left_ed.actors["ZZ_LOOKBENCH_RAKE_L"] = {"tag": True, "on": False, "kind": "spot", "spec": None}   # census clean
check("+ PREPARE refuses when ZZ_LOOKBENCH_ actors already exist (clean census), spawning nothing",
      raises(lambda: lb.PrepareBench(left_ed, tmp / "c.json", BAYS).run(), "LOOK_BENCH_LEFTOVERS")
      and len(left_ed.actors) == 1 and not (tmp / "c.json").exists())
check("- control: a clean editor fake prepares", not raises(lambda: lb.PrepareBench(EditorFake(), tmp / "d.json", BAYS).run(),
                                                         "LOOK_BENCH"))

# ---------------- CAPTURE (PIE world) ----------------
pie = PieFake(ed)
before = copy.deepcopy(pie.lights)
slots_before = dict(pie.slots)
b = lb.LookBench(pie, tmp / "cap1.json", {"bay": 4}, "T1")
b.read_originals(None, require_pool=True, prepare_record=prep)
b.apply(ALL, now=0.0)
iw = first_index(pie.events, lambda e: e == "record_written")
ic = first_index(pie.events, is_change)
check("+ CAPTURE: originals file written before the first change", iw is not None and ic is not None and iw < ic)
rec = json.loads((tmp / "cap1.json").read_text(encoding="utf-8"))
check("+ CAPTURE: record holds every bay light's original fields and the pool it needs",
      all(rec["lights"][l]["cast_shadows"] == before[l]["cast_shadows"] for l in rec["lights"]) and len(rec["lights"]) == 6
      and rec["pool_needed"] and set(rec["pool_needed"]) <= set(pie.pool_labels()))
check("+ CAPTURE: shadows toggle turned shadows on", sum(pie.lights[l]["cast_shadows"] for l in pie.lights if "B04" in pie.lights[l]["label"]) >= 2)
check("+ CAPTURE: edge toggle swapped both edge slots", all(v.startswith("MID(") for v in pie.slots.values()))
on = shown(pie)
check("+ CAPTURE: floor_wet shows a floor and puddles, never a second plain floor",
      "ZZ_LOOKBENCH_FLOOR" in on and sum(l.startswith("ZZ_LOOKBENCH_PUDDLE_") for l in on) == 5)
dens = [pie.actors[l]["spec"]["density"] for l in on if pie.actors[l]["kind"] == "fog"]
check("+ CAPTURE: haze densities are varied (3 distinct, thin near, thick far)", len(set(dens)) == 3 and dens == sorted(dens))
check("+ CAPTURE: path made NO spawn/destroy call", not any(isinstance(e, tuple) and e[0] in ("spawn", "destroy") for e in pie.events))


class RogueBench(lb.LookBench):
    def apply(self, toggles, now=0.0):
        super().apply(toggles, now)
        self.a.spawn({"label": "ZZ_LOOKBENCH_ROGUE", "kind": "spot"})


pie_r = PieFake(ed)
rb = RogueBench(pie_r, tmp / "capr.json", {"bay": 4}, "TR")
rb.read_originals([("rake", ("rake",))], prepare_record=prep)
rb.apply(("rake",))
check("- control: a spawn call inside the capture path is caught by the same check",
      any(isinstance(e, tuple) and e[0] == "spawn" for e in pie_r.events))
SPAWNISH = re.compile(r"spawn_actor|begin_deferred|finish_spawning|SpawnActor|\.spawn\w*\(|destroy\w*\(|EditorActorSubsystem|"
                      r"EditorLevelLibrary", re.I)
src = (HERE / "look_bench.py").read_text(encoding="utf-8")
pie_region = src.split("# ---- PIE ADAPTER BEGIN", 1)[1].split("# ---- PIE ADAPTER END", 1)[0]
bench_src = inspect.getsource(lb.LookBench) + inspect.getsource(lb.restore_from_record) + inspect.getsource(lb.restore_all)
check("+ source: PIE adapter region and LookBench/restore code contain no spawn/destroy/editor-actor API",
      len(pie_region) > 2000 and not SPAWNISH.search(pie_region.split("\n", 1)[1]) and not SPAWNISH.search(bench_src))
check("- control: the spawn scanner flags an injected PIE spawn",
      bool(SPAWNISH.search(pie_region + "\n        actor = actor_sub.spawn_actor_from_class(cls, loc)\n")))
CALL_MISSING = re.compile(r"GameplayStatics\.begin_deferred\w*\(")
check("+ source: the missing UE 5.8 API begin_deferred_actor_spawn_from_class appears nowhere as a call",
      not CALL_MISSING.search(src))
check("- control: that scanner flags the old call", bool(CALL_MISSING.search(
    "actor = unreal.GameplayStatics.begin_deferred_actor_spawn_from_class(world, cls, t, m, None)")))

f_miss = PieFake(ed)
f_miss.actors.pop("ZZ_LOOKBENCH_RAKE_L")
check("+ CAPTURE refuses when a prepared actor it needs is missing (before writing or changing anything)",
      raises(lambda: lb.LookBench(f_miss, tmp / "m.json", {"bay": 4}).read_originals(None, prepare_record=prep),
             "LOOK_BENCH_PREPARED_MISSING") and not (tmp / "m.json").exists() and first_index(f_miss.events, is_change) is None)
check("+ CAPTURE refuses with no pool at all (PREPARE never ran)",
      raises(lambda: lb.LookBench(PieFake(None), tmp / "n.json", {"bay": 4}).read_originals(None), "LOOK_BENCH_PREPARED_MISSING"))
check("- control: an unpooled PIE world passes when the pool is not required (PROBE)",
      not raises(lambda: lb.LookBench(PieFake(None), tmp / "o.json", {"bay": 4}).read_originals(None, require_pool=False), "LOOK_BENCH"))
f_lit = PieFake(ed)
f_lit.actors["ZZ_LOOKBENCH_STROBE"]["on"] = True
check("+ CAPTURE refuses while a pool actor is still lit (run RESTORE first)",
      raises(lambda: lb.LookBench(f_lit, tmp / "p.json", {"bay": 4}).read_originals(None, prepare_record=prep), "LOOK_BENCH_POOL_NOT_BASE"))
check("+ CAPTURE refuses outside PIE", raises(lambda: lb.LookBench(PieFake(ed, "editor"), tmp / "q.json").read_originals(None),
                                              "LOOK_BENCH_NEEDS_PIE"))
check("+ CAPTURE refuses a prepare record from another level",
      raises(lambda: lb.LookBench(PieFake(ed), tmp / "r.json", {"bay": 4}).read_originals(
          None, prepare_record=dict(prep, world="/Game/Other/L_Other.L_Other")), "LOOK_BENCH_WRONG_WORLD"))
check("+ CAPTURE/RESTORE refuse without a prepare record on disk (newest-search and explicit path)",
      raises(lambda: lb.find_prepare_record(tmp / "nowhere"), "LOOK_BENCH_NOT_PREPARED")
      and raises(lambda: lb.find_prepare_record(tmp, tmp / "missing.json"), "LOOK_BENCH_NOT_PREPARED"))
partial = dict(prep, status="partial")
(tmp / "partial.json").write_text(json.dumps(partial), encoding="utf-8")
check("+ a partial PREPARE record is refused", raises(lambda: lb.load_prepare_record(tmp / "partial.json"), "LOOK_BENCH_PREPARE_INCOMPLETE"))
check("+ same_level matches the editor map to its UEDPIE_ duplicate, not to another map",
      lb.same_level(ed.world_name(), pie.world_name()) and not lb.same_level(ed.world_name(), "/Game/Maps/UEDPIE_0_X.X"))

# ---------------- RESTORE ----------------
pie.cvars[lb.STREAM_CVAR] = 1
problems = b.restore()
check("+ restore is exact (lights, edges, pool hidden, cvar)", problems == [] and pie.lights == before and pie.slots == slots_before
      and not shown(pie) and pie.cvars[lb.STREAM_CVAR] == 0 and len(pie.pool_labels()) == len(ed.actors))
f3 = PieFake(ed)
b3 = lb.LookBench(f3, tmp / "rec3.json", {"bay": 4}, "T3")
b3.read_originals(None, prepare_record=prep)
b3.apply(("shadows",))
orig_set = f3.set_light
f3.set_light = lambda lid, field, value: None if field == "cast_shadows" else orig_set(lid, field, value)
check("- control: a lost restore write is reported by verify()", len(b3.restore()) > 0)
f3b = PieFake(ed)
b3b = lb.LookBench(f3b, tmp / "rec3b.json", {"bay": 4}, "T3b")
b3b.read_originals(None, prepare_record=prep)
b3b.apply(("haze",))
f3b.hide_pool = lambda label: None
check("- control: a pool actor left shown is reported by verify()", any("still shown" in p for p in b3b.restore()))

f4 = PieFake(ed)
b4 = lb.LookBench(f4, tmp / "rec4.json", {"bay": 4}, "T4")
b4.read_originals(None, prepare_record=prep)
b4.apply(("haze",))
b4.apply(("rake",))
check("+ switching state starts from base (haze hidden when rake applied, vsi restored)",
      not any(l.startswith("ZZ_LOOKBENCH_HAZE") for l in shown(f4)) and "ZZ_LOOKBENCH_RAKE_L" in shown(f4)
      and all(f4.lights[l]["volumetric_scattering_intensity"] == b4.record["lights"][l]["volumetric_scattering_intensity"]
              for l in b4.record["lights"]))
b4.restore()

f6 = PieFake(ed)
before6 = copy.deepcopy(f6.lights)
b6 = lb.LookBench(f6, tmp / "rec6.json", {"bay": 4}, "T6")
b6.read_originals(None, prepare_record=prep)
b6.apply(ALL)
f6.cvars[lb.STREAM_CVAR] = 1           # "editor died here": state left changed, bench object lost
del b6
n_pool = len(f6.pool_labels())
check("+ RESTORE from the record alone is exact and keeps the pool (hidden, not destroyed)",
      lb.restore_all(f6, [tmp / "rec6.json"], f6.log) == [] and f6.lights == before6 and not shown(f6)
      and len(f6.pool_labels()) == n_pool and f6.cvars[lb.STREAM_CVAR] == 0)
# two captures, the older crashed mid-state: newest-first restore leaves the oldest originals in place
f8 = PieFake(ed)
before8 = copy.deepcopy(f8.lights)
b8a = lb.LookBench(f8, tmp / "capture_A.json", {"bay": 4}, "A")
b8a.read_originals(None, prepare_record=prep)
b8a.apply(("shadows", "haze"))          # crash: never restored
b8b = lb.LookBench(f8, tmp / "capture_B.json", {"bay": 4}, "B")
for l in f8.pool_labels():
    f8.actors[l]["on"] = False          # operator hid the pool by hand; B reads the CHANGED lights as originals
b8b.read_originals(None, prepare_record=prep)
check("+ RESTORE over two records (newest first) ends on the OLDEST originals",
      lb.restore_all(f8, [tmp / "capture_A.json", tmp / "capture_B.json"], f8.log) == [] and f8.lights == before8)
check("- control: oldest-first order would leave the second capture's (changed) values",
      (lambda f: (lb.restore_from_record(f, tmp / "capture_A.json"), lb.restore_from_record(f, tmp / "capture_B.json"),
                  f.lights != before8)[2])(f8))

# ---------------- edge no-op logging ----------------
f9 = PieFake(ed)
f9.slots = {}
b9 = lb.LookBench(f9, tmp / "rec9.json", {"bay": 4}, "T9")
b9.read_originals([("edge", ("edge",)), ("base", ())], prepare_record=prep)
b9.apply(("edge",))
check("+ edge_slots=0 is logged at read and as EDGE_NOOP on the edge state",
      bool(f9.logs("edge toggle is a NO-OP")) and bool(f9.logs("LOOK_BENCH_EDGE_NOOP|"))
      and "edge_effective=False" in f9.logs("LOOK_BENCH_STATE|")[-1])
check("- control: with edge slots present there is no EDGE_NOOP and edge_effective=True",
      not pie.logs("LOOK_BENCH_EDGE_NOOP") and "edge_effective=True" in pie.logs("LOOK_BENCH_STATE|")[0])
b9.restore()

# ---------------- CLEANUP (editor, never saves) ----------------
ed_c, prep_c = prepared(2)
n_c = len(ed_c.actors)
check("+ CLEANUP deletes every tagged pool actor when only PREPARE's dirt is present",
      lb.cleanup(ed_c, tmp / "prep2.json") == n_c and not ed_c.pool_labels() and bool(ed_c.logs(lb.RESTART_MARKER)))
ed_f, _ = prepared(3)
ed_f.dirty["content"].append("DA_InfinityStage_V1Show")
check("+ CLEANUP refuses on a foreign dirty package and deletes nothing",
      raises(lambda: lb.cleanup(ed_f, tmp / "prep3.json"), "LOOK_BENCH_CLEANUP_FOREIGN_DIRTY") and len(ed_f.pool_labels()) == n_c
      and not any(isinstance(e, tuple) and e[0] == "destroy" for e in ed_f.events))
ed_m, _ = prepared(4)
ed_m.dirty["maps"].append("L_SomeOtherMap")
check("+ CLEANUP refuses on a foreign dirty MAP too", raises(lambda: lb.cleanup(ed_m, tmp / "prep4.json"), "LOOK_BENCH_CLEANUP_FOREIGN_DIRTY"))
ed_p, _ = prepared(5)
ed_p.pie_running = True
check("+ CLEANUP refuses while PIE runs", raises(lambda: lb.cleanup(ed_p, tmp / "prep5.json"), "LOOK_BENCH_CLEANUP_NEEDS_EDITOR"))
ed_u, _ = prepared(6)
ed_u.actors["ZZ_LOOKBENCH_SOMEONE_ELSES"] = {"tag": False, "on": True, "kind": "mesh", "spec": None}
lb.cleanup(ed_u, tmp / "prep6.json")
check("+ CLEANUP leaves untagged ZZ_LOOKBENCH_-labelled actors alone and names them",
      "ZZ_LOOKBENCH_SOMEONE_ELSES" in ed_u.actors and "ZZ_LOOKBENCH_SOMEONE_ELSES" in ed_u.logs("LOOK_BENCH_CLEANUP_OK")[0])

# ---------------- never-save guard ----------------
SAVE = re.compile(r"save_(current_level|packages|dirty|map|asset|loaded_asset|directory|level)|EditorAssetLibrary\.save|"
                  r"save_dirty_packages|\.save\(|SavePackage|editor_save", re.I)
runners = sorted(HERE.glob("look_bench_*_run.py"))
all_src = src + "".join(r.read_text(encoding="utf-8") for r in runners)
check("+ look_bench.py and every look_bench_*_run.py contain no save call", len(runners) >= 6 and not SAVE.search(all_src))
check("- control: the scanner flags an injected save", bool(SAVE.search(src + "\nunreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)\n")))
check("+ no Unreal import at module level (UE objects only in closures)",
      not re.search(r"^import unreal", src, re.M) and not re.search(r"^from unreal", src, re.M))

# ---------------- strobe, clip, stats ----------------
ons = [lb.strobe_on(t / 100.0, 0.0, 1.0, 0.12) for t in range(300)]
rises = sum(1 for i in range(1, len(ons)) if ons[i] and not ons[i - 1])
check("+ strobe: 1 Hz gives 2 rising edges after t=0 in 3 s, 12% duty", rises == 2 and abs(sum(ons) / 300.0 - 0.12) < 0.02)
fs_ = PieFake(ed)
bs = lb.LookBench(fs_, tmp / "recs.json", {"bay": 4}, "TS")
bs.read_originals([("strobe", ("strobe",))], prepare_record=prep)
bs.apply(("strobe",), now=0.0)
bs.tick(0.05); hi = fs_.actors["ZZ_LOOKBENCH_STROBE"]["intensity"]
bs.tick(0.5); lo = fs_.actors["ZZ_LOOKBENCH_STROBE"]["intensity"]
check("+ strobe drives the PREPARED actor's intensity (on, then off)", hi == lb.DEFAULTS["strobe_cd"] and lo == 0.0)
bs.restore()
cp = lb.clip_plan(1_000_000, lb.DEFAULTS)
check("+ clip plan: 5 s at 6 fps = 30 frames, starting 4 s before the bay", cp["frames_expected"] == 30
      and cp["start"] == 1_000_000 - 4 * lb.TICKS_PER_SECOND)
check("- control: an unknown toggle is refused", raises(lambda: lb.normalise_toggles(("fog",)), "LOOK_BENCH_BAD_TOGGLE"))
fs = lb.frame_stats([0.02] * 9 + [0.05])
check("+ frame stats: mean 23 ms, one frame over 40 ms", fs["n"] == 10 and abs(fs["mean"] - 23.0) < 1e-6 and fs["over_40ms"] == 1)
check("- control: no samples gives n=0, not a fake number", lb.frame_stats([]) == {"n": 0})

# ---------------- glint ----------------
FR = {"origin": (0.0, 240000.0, 0.0), "fwd": (1.0, 0.0), "right": (0.0, 1.0), "yaw_deg": 0.0,
      "pitch_cm": 500.0, "half_width_cm": 1450.0}
P = (3500.0, 240000.0 - 900.0, 300.0)
N = (-0.94, 0.34, 0.0)
g = lb.glint_solution(P, N, FR, lb.DEFAULTS)
ok = g["light"] is not None
if ok:
    a = lb._unit(lb._sub(g["light"], P)); c = lb._unit(lb._sub(g["camera"], P)); n = lb._unit(N)
    bis = lb._unit(lb._add(a, c))
    cross = (bis[1] * n[2] - bis[2] * n[1], bis[2] * n[0] - bis[0] * n[2], bis[0] * n[1] - bis[1] * n[0])
    mirror = max(abs(x) for x in cross) < 1e-9 and lb._dot(bis, n) > 0
    camera_on_route = abs(g["camera"][1] - 240000.0) < 1e-6 and g["camera"][0] < P[0]
else:
    mirror = camera_on_route = False
check("+ glint: light and camera are mirror images about the face normal", ok and mirror)
check("+ glint: the camera sample lies on the route line, before the face", camera_on_route)
check("+ glint: a normal given pointing away is flipped to face the camera",
      lb.glint_solution(P, (0.94, -0.34, 0.0), FR, lb.DEFAULTS)["light"] == g["light"])
edge_on = lb.glint_solution(P, (0.0, 0.0, 1.0), FR, dict(lb.DEFAULTS, glint_z_range=(40.0, 600.0)))
check("- control: a face that cannot mirror into the band returns no light, with reasons", edge_on["light"] is None
      and len(edge_on["tried"]) == len(lb.DEFAULTS["glint_cam_distances"]))
check("- control: glint without a resolved face refuses", raises(lambda: lb.plan_spawns(FR, ("glint",), lb.DEFAULTS, None),
                                                               "LOOK_BENCH_GLINT_UNRESOLVED"))
f7 = PieFake(ed)
f7.wing_face = lambda contains, frame: {"point": [frame["origin"][0] + 300.0, frame["origin"][1] - 900.0, 300.0],
                                       "normal": [-0.94, 0.34, 0.0], "mesh": "/Game/x/" + contains, "component": "c"}
before7 = copy.deepcopy(f7.lights)
b7 = lb.LookBench(f7, tmp / "rec7.json", {"bay": 4}, "T7")
b7.read_originals(None, prepare_record=prep)
check("+ glint resolved at read and recorded before any change", b7.record["glint"]["light"] is not None
      and first_index(f7.events, is_change) is None)
b7.apply(("glint", "underpass"))
lab = shown(f7)
check("+ glint shows the prepared point light + bulb at the mirror position",
      "ZZ_LOOKBENCH_GLINT" in lab and "ZZ_LOOKBENCH_GLINT_BULB" in lab
      and list(f7.actors["ZZ_LOOKBENCH_GLINT"]["spec"]["loc"]) == b7.record["glint"]["light"])
cols = [f7.actors[l]["spec"] for l in lab if l.startswith("ZZ_LOOKBENCH_UP_COLUMN_")]
check("+ underpass mock: 2 piers, 2 columns, 4 knees, 2 stringers, ties, 1 shadowed shaft; columns outside the corridor",
      sum(l.startswith("ZZ_LOOKBENCH_UP_PIER_") for l in lab) == 2 and len(cols) == 2
      and sum(l.startswith("ZZ_LOOKBENCH_UP_KNEE_") for l in lab) == 4
      and sum(l.startswith("ZZ_LOOKBENCH_UP_STRINGER_") for l in lab) == 2
      and sum(l.startswith("ZZ_LOOKBENCH_UP_TIE_") for l in lab) >= 11
      and all(abs(c["loc"][1] - b7.record["frame"]["origin"][1]) > 1450.0 for c in cols)
      and f7.actors["ZZ_LOOKBENCH_UP_SHAFT"]["spec"]["shadows"] is True)
check("+ glint + underpass restore exactly", b7.restore() == [] and f7.lights == before7 and not shown(f7))
check("+ default states include glint only when resolved, and always arch_ring_border",
      any(n == "glint" for n, _ in lb.default_states(True)) and not any("glint" in t for _, t in lb.default_states(False))
      and any(n == "arch_ring_border" for n, _ in lb.default_states(False)))

# ---------------- arch_ring_border geometry ----------------
FRA = {"origin": (1000.0, 240000.0, 0.0), "fwd": (math.cos(math.radians(-25.0)), math.sin(math.radians(-25.0))),
       "right": (-math.sin(math.radians(-25.0)), math.cos(math.radians(-25.0))), "yaw_deg": -25.0,
       "pitch_cm": 650.0, "half_width_cm": 1450.0}
arches = lb.arch_specs(FRA, lb.DEFAULTS)
prof = lb.pointed_arch_profile(1450.0, lb.DEFAULTS["arch_spring_z_cm"], lb.DEFAULTS["arch_radius_factor"] * 2900.0, 6)


def to_bay(frame, v):    # world vector -> (along, lateral, up)
    return (v[0] * frame["fwd"][0] + v[1] * frame["fwd"][1], v[0] * frame["right"][0] + v[1] * frame["right"][1], v[2])


def inner_edge_ok(spec, frame, flip=False):
    roll = -spec["roll"] if flip else spec["roll"]
    _x, y, z = lb.rotator_axes(spec["yaw"], 0.0, roll)
    yb, zb = to_bay(frame, y), to_bay(frame, z)
    ox, oy, _ = frame["origin"]
    c = to_bay(frame, (spec["loc"][0] - ox, spec["loc"][1] - oy, spec["loc"][2]))
    half_len = (spec["scale"][1] * 100.0 - lb.DEFAULTS["arch_overlap_cm"]) / 2.0
    half_band = spec["scale"][2] * 100.0 / 2.0
    want = [tuple(p) for p in spec["arch"]["inner"]]
    for sb in (1.0, -1.0):
        ends = []
        for sl in (-1.0, 1.0):
            ends.append((c[1] + sl * half_len * yb[1] + sb * half_band * zb[1], c[2] + sl * half_len * yb[2] + sb * half_band * zb[2]))
        for e in (ends, ends[::-1]):
            if all(math.hypot(e[i][0] - want[i][0], e[i][1] - want[i][1]) < 1e-6 for i in range(2)):
                return abs(yb[0]) < 1e-9 and abs(zb[0]) < 1e-9        # band lies in the plane facing the route
    return False


check("+ arch: 3 arches x 2 sides x 6 segments, all ZZ_LOOKBENCH_ boxes",
      len(arches) == 36 and all(s["label"].startswith("ZZ_LOOKBENCH_ARCH_") and s["kind"] == "mesh" for s in arches))
check("+ arch: pointed, symmetric, springs at +-half span, apex on the centre line above the springing",
      abs(prof["L"][0][0] + 1450.0) < 1e-6 and abs(prof["R"][0][0] - 1450.0) < 1e-6
      and prof["L"][-1] == (0.0, prof["L"][-1][1]) and abs(prof["L"][-1][1] - prof["R"][-1][1]) < 1e-9
      and prof["apex_z"] > lb.DEFAULTS["arch_spring_z_cm"] + 1450.0 * 0.9
      and all(abs(math.hypot(y - prof["centres"]["L"][0], z - prof["centres"]["L"][1]) - prof["radius"]) < 1e-6 for y, z in prof["L"]))
check("- control: R below the half span is refused (not an arch)",
      raises(lambda: lb.pointed_arch_profile(1450.0, 500.0, 1000.0, 6), "LOOK_BENCH_ARCH_RADIUS"))
check("+ arch: each box's inner edge lies exactly on its intrados chord, band in the plane facing the camera "
      "(axes from FRotationTranslationMatrix)", all(inner_edge_ok(s, FRA) for s in arches))
check("- control: the same check fails with the roll sign flipped", not all(inner_edge_ok(s, FRA, flip=True) for s in arches))
along = sorted({round(s["arch"]["dx"], 6) for s in arches})
centres = [sum(to_bay(FRA, (s["loc"][0] - 1000.0, s["loc"][1] - 240000.0, 0))[0] for s in arches if s["arch"]["index"] == i) / 12.0
           for i in range(3)]
check("+ arch: instances recede at 500 cm bay spacing along the route",
      along == [0.0, 500.0, 1000.0] and all(abs(centres[i] - 500.0 * i) < 1e-6 for i in range(3)))
fa = PieFake(ed)
ba = lb.LookBench(fa, tmp / "reca.json", {"bay": 4}, "TA")
ba.read_originals([("base", ()), ("arch_ring_border", ("arch_ring_border",))], prepare_record=prep)
before_a = copy.deepcopy(fa.lights)
ba.apply(("arch_ring_border",))
arch_labels = sorted(s["label"] for s in lb.arch_specs(ba._frame(), ba.p))
check("+ arch_ring_border state shows exactly the 36 prepared arch proxies, nothing else, lights untouched",
      len(arch_labels) == 36 and shown(fa) == arch_labels and fa.lights == before_a)
check("+ arch restore exact", ba.restore() == [] and not shown(fa))

failed = [n for n, ok in RESULTS if not ok]
print("\nLOOK_BENCH_HARNESS %d/%d %s" % (len(RESULTS) - len(failed), len(RESULTS), "OK" if not failed else "FAILED"))
sys.exit(1 if failed else 0)
