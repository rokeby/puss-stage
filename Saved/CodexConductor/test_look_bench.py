"""Offline harness for look_bench.py (no Unreal). Each property has a + case and a
- control that must FAIL, so the checks are shown able to fail.
Run: python Saved/CodexConductor/test_look_bench.py"""
import copy
import json
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


class Fake:
    """A PIE world in miniature: bay 3/4/5 lights, two edge slots, actors, cvars."""

    def __init__(self, kind="game"):
        self.kind = kind
        self.events = []
        self.lights = {}
        for bay, x in ((3, -1000.0), (4, 0.0), (5, 1000.0)):
            for i, (lbl, typ, inten, cs, vsi) in enumerate((
                    ("LOW_SIDE_L_KEY", "spot", 900.0, True, 0.45), ("LOW_SIDE_R_FILL", "spot", 56.25, False, 0.45),
                    ("TOP_L", "spot", 0.0, False, 0.25), ("PRACTICAL_L", "point", 1300.0, False, 0.2),
                    ("FENCE_BEAM", "spot", 3000.0, False, 0.6), ("WASH", "rect", 400.0, False, 0.6))):
                lid = "/PIE/P04_B%d_%d" % (bay, i)
                y = 240000.0 + (-1450.0 if i % 2 == 0 else 1450.0)
                self.lights[lid] = {"label": "P04 LOOK B%02d INDUSTRIAL %s" % (bay, lbl), "type": typ,
                                    "location": (x + 40.0, y, 100.0), "intensity": inten, "visible": True,
                                    "cast_shadows": cs, "cast_volumetric_shadow": False,
                                    "volumetric_scattering_intensity": vsi}
        self.slots = {("/PIE/Flat_A.ISM0", 3): "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master.M_Wing_CanvasEdge_Master",
                      ("/PIE/Flat_B.ISM0", 3): "/Game/Scenes/Wings/PaintedSurface/M_Wing_CanvasEdge_Master.M_Wing_CanvasEdge_Master"}
        self.actors = {}
        self.cvars = {lb.STREAM_CVAR: 0}
        self.n = 0

    def world_kind(self): return self.kind
    def world_name(self): return "/Temp/UEDPIE_0_L_InfinityStage_V1VerticalSlice"
    def note(self, e): self.events.append(e)
    def log(self, m): self.events.append(("log", m))
    def census(self): return {"maps": [], "content": []}

    def find_lights(self, prefixes):
        return sorted(l for l, r in self.lights.items() if r["label"].startswith(tuple(prefixes))
                      or any(r["label"].startswith(p.replace("Wing", "LOOK")) for p in prefixes))

    def read_light(self, lid): return copy.deepcopy(self.lights[lid])

    def set_light(self, lid, field, value):
        self.events.append(("set_light", lid, field))
        self.lights[lid][field] = value

    def edge_slots(self, box):
        return [{"id": c, "slot": s, "material": m} for (c, s), m in sorted(self.slots.items())]

    def slot_material(self, cid, slot): return self.slots[(cid, slot)]

    def set_slot_material(self, cid, slot, spec):
        self.events.append(("set_slot", cid, slot))
        self.slots[(cid, slot)] = spec.get("path") or "MID(%s)" % spec["mid_parent"]

    def spawn(self, spec):
        self.events.append(("spawn", spec["label"]))
        self.n += 1
        h = "h%d" % self.n
        self.actors[h] = {"label": spec["label"], "spec": spec, "intensity": spec.get("cd")}
        return h

    def material_readback(self, h): return dict(self.actors[h]["spec"]["material"].get("scalars", {}))
    def set_spawn_intensity(self, h, v): self.actors[h]["intensity"] = v
    def destroy(self, h): self.actors.pop(h)
    def bench_actor_labels(self, prefix): return sorted(a["label"] for a in self.actors.values() if a["label"].startswith(prefix))
    def bench_actor_handles(self, prefix): return [h for h, a in self.actors.items() if a["label"].startswith(prefix)]
    def get_cvar(self, n): return self.cvars[n]
    def set_cvar(self, n, v): self.cvars[n] = int(v)


def first_index(events, pred):
    for i, e in enumerate(events):
        if pred(e):
            return i
    return None


def is_change(e):
    return isinstance(e, tuple) and e[0] in ("set_light", "set_slot", "spawn")


tmp = pathlib.Path(tempfile.mkdtemp(prefix="look_bench_test_"))
ALL = ("shadows", "haze", "rake", "floor_wet", "strobe", "edge")

# 1. originals written (and re-read) before ANY change
f = Fake()
b = lb.LookBench(f, tmp / "rec1.json", {"bay": 4}, "T1")
before = copy.deepcopy(f.lights)
slots_before = dict(f.slots)
b.prepare()
b.apply(ALL, now=0.0)
iw = first_index(f.events, lambda e: e == "record_written")
ic = first_index(f.events, is_change)
check("+ originals file written before the first change", iw is not None and ic is not None and iw < ic)
rec = json.loads((tmp / "rec1.json").read_text(encoding="utf-8"))
check("+ record holds every bay light's original fields",
      all(rec["lights"][l]["cast_shadows"] == before[l]["cast_shadows"] for l in rec["lights"]) and len(rec["lights"]) == 6)
# - control: a bench that changes first must be caught by the same ordering check
f2 = Fake()
f2.set_light("/PIE/P04_B4_1", "cast_shadows", True)
b2 = lb.LookBench(f2, tmp / "rec1b.json", {"bay": 4}, "T1b")
b2.prepare()
iw2 = first_index(f2.events, lambda e: e == "record_written")
ic2 = first_index(f2.events, is_change)
check("- control: change-before-record is detected by the ordering check", not (iw2 is not None and ic2 is not None and iw2 < ic2))
check("- control: apply refuses when the originals file is gone",
      raises(lambda: ((tmp / "rec1b.json").unlink(), b2.apply(("rake",)))[1], "LOOK_BENCH_NO_RECORD"))

# 2. toggles did something, then restore is exact
check("+ shadows toggle turned shadows on", sum(f.lights[l]["cast_shadows"] for l in f.lights if "B04" in f.lights[l]["label"]) >= 2)
check("+ edge toggle swapped both edge slots", all(v.startswith("MID(") for v in f.slots.values()))
labels = f.bench_actor_labels(lb.SPAWN_PREFIX)
check("+ every spawn carries the ZZ_LOOKBENCH_ prefix", labels and all(l.startswith("ZZ_LOOKBENCH_") for l in labels)
      and len(labels) == len(f.actors))
check("+ floor_wet spawns a floor and puddles, never a second plain floor",
      labels.count("ZZ_LOOKBENCH_FLOOR") == 1 and sum(l.startswith("ZZ_LOOKBENCH_PUDDLE_") for l in labels) == 5)
dens = [a["spec"]["density"] for a in f.actors.values() if a["spec"]["kind"] == "fog"]
check("+ haze densities are varied (3 distinct, thin near, thick far)", len(set(dens)) == 3 and dens == sorted(dens))
f.cvars[lb.STREAM_CVAR] = 1
problems = b.restore()
check("+ restore is exact (lights, edges, actors, cvar)", problems == [] and f.lights == before and f.slots == slots_before
      and not f.actors and f.cvars[lb.STREAM_CVAR] == 0)

# - control: a world that ignores one restore write must make verify() fail
f3 = Fake()
b3 = lb.LookBench(f3, tmp / "rec3.json", {"bay": 4}, "T3")
b3.prepare()
b3.apply(("shadows",))
orig_set = f3.set_light
f3.set_light = lambda lid, field, value: None if field == "cast_shadows" else orig_set(lid, field, value)
check("- control: a lost restore write is reported by verify()", len(b3.restore()) > 0)

# 3. state switching is from base each time (no accumulation)
f4 = Fake()
b4 = lb.LookBench(f4, tmp / "rec4.json", {"bay": 4}, "T4")
b4.prepare()
b4.apply(("haze",))
b4.apply(("rake",))
check("+ switching state starts from base (haze actors gone when rake applied)",
      not any(l.startswith("ZZ_LOOKBENCH_HAZE") for l in f4.bench_actor_labels(lb.SPAWN_PREFIX))
      and all(f4.lights[l]["volumetric_scattering_intensity"] == b4.record["lights"][l]["volumetric_scattering_intensity"]
              for l in b4.record["lights"]))
b4.restore()

# 4. PIE only, and leftovers refuse
check("+ refuses outside a PIE game world", raises(lambda: lb.LookBench(Fake("editor"), tmp / "x.json").prepare(), "LOOK_BENCH_NEEDS_PIE"))
f5 = Fake()
f5.actors["old"] = {"label": "ZZ_LOOKBENCH_RAKE_L", "spec": {}, "intensity": 0}
check("+ refuses while ZZ_LOOKBENCH_ leftovers exist", raises(lambda: lb.LookBench(f5, tmp / "y.json").prepare(), "LOOK_BENCH_LEFTOVERS"))
check("- control: the same fake without leftovers prepares", not raises(lambda: lb.LookBench(Fake(), tmp / "z.json").prepare(), "LOOK_BENCH"))

# 5. crash recovery from the file alone
f6 = Fake()
b6 = lb.LookBench(f6, tmp / "rec6.json", {"bay": 4}, "T6")
before6 = copy.deepcopy(f6.lights)
b6.prepare()
b6.apply(ALL)
f6.cvars[lb.STREAM_CVAR] = 1           # "editor died here": state left changed, bench object lost
del b6
check("+ RESTORE from the record alone is exact", lb.restore_from_record(f6, tmp / "rec6.json") == []
      and f6.lights == before6 and not f6.actors and f6.cvars[lb.STREAM_CVAR] == 0)

# 6. never-save guard: no save API anywhere in the bench source
SAVE = re.compile(r"save_(current_level|packages|dirty|map|asset|loaded_asset|directory|level)|EditorAssetLibrary\.save|"
                  r"save_dirty_packages|\.save\(|SavePackage|editor_save", re.I)
src = (HERE / "look_bench.py").read_text(encoding="utf-8")
check("+ look_bench.py contains no save call", not SAVE.search(src))
check("- control: the scanner flags an injected save", bool(SAVE.search(src + "\nunreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)\n")))
check("+ no Unreal import at module level (UE objects only in the closure)",
      not re.search(r"^import unreal", src, re.M) and not re.search(r"^from unreal", src, re.M))

# 7. strobe ~1 Hz and clip plan
ons = [lb.strobe_on(t / 100.0, 0.0, 1.0, 0.12) for t in range(300)]
rises = sum(1 for i in range(1, len(ons)) if ons[i] and not ons[i - 1])
check("+ strobe: 1 Hz gives 2 rising edges after t=0 in 3 s, 12% duty", rises == 2 and abs(sum(ons) / 300.0 - 0.12) < 0.02)
cp = lb.clip_plan(1_000_000, lb.DEFAULTS)
check("+ clip plan: 5 s at 6 fps = 30 frames, starting 4 s before the bay", cp["frames_expected"] == 30
      and cp["start"] == 1_000_000 - 4 * lb.TICKS_PER_SECOND)
check("- control: an unknown toggle is refused", raises(lambda: lb.normalise_toggles(("fog",)), "LOOK_BENCH_BAD_TOGGLE"))

fs = lb.frame_stats([0.02] * 9 + [0.05])
check("+ frame stats: mean 23 ms, one frame over 40 ms", fs["n"] == 10 and abs(fs["mean"] - 23.0) < 1e-6 and fs["over_40ms"] == 1)
check("- control: no samples gives n=0, not a fake number", lb.frame_stats([]) == {"n": 0})

# 8. glint: mirror law and failure cases
import math as _m
FR = {"origin": (0.0, 240000.0, 0.0), "fwd": (1.0, 0.0), "right": (0.0, 1.0), "yaw_deg": 0.0,
      "pitch_cm": 500.0, "half_width_cm": 1450.0}
P = (3500.0, 240000.0 - 900.0, 300.0)          # a right-side flat face, 9 m off the lane
N = (-0.94, 0.34, 0.0)                         # faces the approaching camera, toed in
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
check("+ glint: light and camera are mirror images about the face normal (angle in = angle out)", ok and mirror)
check("+ glint: the camera sample lies on the route line, before the face", camera_on_route)
check("+ glint: a normal given pointing away is flipped to face the camera",
      lb.glint_solution(P, (0.94, -0.34, 0.0), FR, lb.DEFAULTS)["light"] == g["light"])
edge_on = lb.glint_solution(P, (0.0, 0.0, 1.0), FR, dict(lb.DEFAULTS, glint_z_range=(40.0, 600.0)))
check("- control: a face that cannot mirror into the band returns no light, with reasons", edge_on["light"] is None
      and len(edge_on["tried"]) == len(lb.DEFAULTS["glint_cam_distances"]))
check("- control: glint without a resolved face refuses", raises(lambda: lb.plan_spawns(FR, ("glint",), lb.DEFAULTS, None),
                                                               "LOOK_BENCH_GLINT_UNRESOLVED"))

f7 = Fake()
f7.wing_face = lambda contains, frame: {"point": [frame["origin"][0] + 300.0, frame["origin"][1] - 900.0, 300.0],
                                       "normal": [-0.94, 0.34, 0.0], "mesh": "/Game/x/" + contains, "component": "c"}
b7 = lb.LookBench(f7, tmp / "rec7.json", {"bay": 4}, "T7")
before7 = copy.deepcopy(f7.lights)
b7.prepare()
check("+ glint resolved at prepare and recorded before any change", b7.record["glint"]["light"] is not None
      and first_index(f7.events, is_change) is None)
b7.apply(("glint", "underpass"))
lab = f7.bench_actor_labels(lb.SPAWN_PREFIX)
check("+ glint spawns one point light + bulb", "ZZ_LOOKBENCH_GLINT" in lab and "ZZ_LOOKBENCH_GLINT_BULB" in lab)
cols = [a["spec"] for a in f7.actors.values() if a["label"].startswith("ZZ_LOOKBENCH_UP_COLUMN_")]
check("+ underpass mock: 2 piers, 2 columns, 4 knees, 2 stringers, ties, 1 shadowed shaft; columns outside the corridor",
      sum(l.startswith("ZZ_LOOKBENCH_UP_PIER_") for l in lab) == 2 and len(cols) == 2
      and sum(l.startswith("ZZ_LOOKBENCH_UP_KNEE_") for l in lab) == 4
      and sum(l.startswith("ZZ_LOOKBENCH_UP_STRINGER_") for l in lab) == 2
      and sum(l.startswith("ZZ_LOOKBENCH_UP_TIE_") for l in lab) >= 11
      and all(abs(c["loc"][1] - b7.record["frame"]["origin"][1]) > 1450.0 for c in cols)
      and [a["spec"]["shadows"] for a in f7.actors.values() if a["label"] == "ZZ_LOOKBENCH_UP_SHAFT"] == [True])
check("+ glint + underpass restore exactly", b7.restore() == [] and f7.lights == before7 and not f7.actors)
check("+ default states include glint only when resolved", any(n == "glint" for n, _ in lb.default_states(True))
      and not any("glint" in t for _, t in lb.default_states(False)))


failed = [n for n, ok in RESULTS if not ok]
print("\nLOOK_BENCH_HARNESS %d/%d %s" % (len(RESULTS) - len(failed), len(RESULTS), "OK" if not failed else "FAILED"))
sys.exit(1 if failed else 0)
