"""Offline harness for p02_fog_bench.py (no Unreal). Every property has a + case and a - control that must FAIL,
so each check is shown able to fail. Fake-adapter pattern of test_look_bench.py / test_passage_stills.py.
Run: python Saved/CodexConductor/test_p02_fog_bench.py"""
import copy
import inspect
import json
import math
import pathlib
import re
import struct
import sys
import tempfile
import zlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import look_bench as lb  # noqa: E402
import p02_fog_bench as fb  # noqa: E402

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


def write_png(path, w, h, grey):
    grey = max(0, min(255, int(round(grey))))
    raw = b"".join(b"\x00" + bytes([grey, grey, grey]) * w for _ in range(h))

    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body) & 0xFFFFFFFF)
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                                   + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


tmp = pathlib.Path(tempfile.mkdtemp(prefix="p02fog_"))
MAP = "L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SEG = (1_000_000, 1_000_000 + 120 * fb.ps.TICKS_PER_SECOND)
PITCH = 600.0
ROUTE_LEN = 23 * PITCH
HIST = "<AutoExposureMethod.AEM_HISTOGRAM: 0>"


def bay_x(k):
    return (k - 1) * PITCH + 200.0


class Store:
    pass


class World:
    """Shared fake state: PIE lamps (P02 SCORE bays 1..23, + an office tube, + a far lamp), one height fog, two
    effect media, four post-process sources, floor + wing slots, the ZZ_P02FOG_ pool, strobe + car light."""

    def __init__(self, kind="game"):
        self.kind = kind
        self.events = []
        self.logs_, self.errors = [], []
        self.state = {}
        self.meta = {}
        self.census_ = {"maps": [MAP], "content": []}
        self.pool = {}
        self.strobes = {"/PIE/P02_Strobe": True}
        self.sweeps = {"/PIE/P02_Car": True}
        self.record_path = None
        self.violations = []
        for k in range(1, 24):
            x = bay_x(k)
            side = -1.0 if k % 2 == 0 else 1.0
            rows = [("TOP_L", (x, -360.0, 1180.0), {"roll": 0.0, "pitch": -57.0, "yaw": -90.0}, 0.35),
                    ("LOW_SIDE_L_KEY", (x + 80.0, side * 1100.0, 130.0), {"roll": 0.0, "pitch": 4.0, "yaw": -side * 72.0}, 0.8),
                    ("LOW_SIDE_R_FILL", (x + 80.0, -side * 1100.0, 150.0), {"roll": 0.0, "pitch": -2.0, "yaw": side * 72.0}, 0.55),
                    ("PRACTICAL_CLAMP", (x - 30.0, -720.0, 145.0), {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}, 0.3)]
            if k <= 13:
                rows.append(("BEAM_R", (x - 150.0, -1250.0, 140.0), {"roll": 0.0, "pitch": 11.4, "yaw": 86.2}, 2.5))
            for slot, loc, rot, vsi in rows:
                self.add_light("/PIE/P02_B%02d_%s" % (k, slot), "P02 SCORE B%02d LOOK %s" % (k, slot), loc, rot, vsi)
        self.add_light("/PIE/Tube_01", "P02 Office Tube 01", (bay_x(15) + 300.0, 0.0, 1900.0),
                       {"roll": 0.0, "pitch": -90.0, "yaw": 0.0}, 0.4)
        self.add_light("/PIE/Far_Lamp", "P05 SCORE B40 LOOK TOP_L", (60000.0, 0.0, 1180.0),
                       {"roll": 0.0, "pitch": -57.0, "yaw": 0.0}, 0.35)
        # "tubes everywhere": several rect lights on ONE Structure actor -> one row per component
        for i, k in enumerate((7, 8, 9, 14, 15, 16)):
            self.add_light("/PIE/Structure02.StructureUnderpassTubeLight_%d" % i,
                           "Infinity Stage - Structure 02/StructureUnderpassTubeLight_%d" % i,
                           (bay_x(k) + 100.0, (-1.0) ** i * 900.0, 420.0), {"roll": 0.0, "pitch": -90.0, "yaw": 0.0}, 1.0,
                           component=True)
        self.missing_api = []
        self.fog_id = "/PIE/HeightFog.Component"
        self.set_("fog", self.fog_id, "fog_density", 0.035)
        self.set_("fog", self.fog_id, "second_fog_density", 0.01)
        self.set_("fog", self.fog_id, "volumetric_fog", True)
        for mid_, loc in (("/PIE/FX_Near.Medium", (bay_x(9), 0.0, 150.0)), ("/PIE/FX_Far.Medium", (30000.0, 0.0, 150.0))):
            self.meta[mid_] = {"label": mid_.split("/")[-1], "location": loc}
            self.set_("media", mid_, "radial_fog_extinction", 0.15)
            self.set_("media", mid_, "height_fog_extinction", 0.15)
        self.pp_meta = {"/PIE/PPV_Unbound": {"kind": "ppv", "enabled": True, "unbound": True, "priority": 0.0, "weight": 1.0,
                                             "box": None},
                        "/PIE/PPV_Hangar": {"kind": "ppv", "enabled": True, "unbound": False, "priority": 5.0, "weight": 1.0,
                                            "box": ((90000.0, 0.0, 0.0), (5000.0, 5000.0, 5000.0))},
                        "/PIE/PPV_Off": {"kind": "ppv", "enabled": False, "unbound": True, "priority": 9.0, "weight": 1.0,
                                         "box": None},
                        "/PIE/CineCam.Camera": {"kind": "camera", "enabled": True, "unbound": True, "priority": 1e9,
                                                "weight": 1.0, "box": None}}
        for pid in self.pp_meta:
            unb = pid == "/PIE/PPV_Unbound"
            for f, v in (("override_auto_exposure_min_brightness", unb), ("auto_exposure_min_brightness", -8.0 if unb else 0.0),
                         ("override_auto_exposure_max_brightness", unb), ("auto_exposure_max_brightness", 4.0 if unb else 0.0),
                         ("override_auto_exposure_method", unb), ("auto_exposure_method", HIST),
                         ("override_lumen_reflection_quality", False), ("lumen_reflection_quality", 1.0),
                         ("override_lumen_reflections_screen_traces", False), ("lumen_reflections_screen_traces", True),
                         ("override_lumen_max_roughness_to_trace_reflections", False),
                         ("lumen_max_roughness_to_trace_reflections", 0.4)):
                self.set_("pp", pid, f, v)
        self.slabs = ["/PIE/Floor_%s.SMC" % n for n in ("Near", "Left", "Right", "Far")]
        for s in self.slabs:
            self.set_("mid", s, "slot0", fb.WALNUT_MAT)
        self.wings = {"/PIE/Wing_A.ISM": "/Game/Wing/MI_Front_Tex", "/PIE/Wing_B.ISM": "/Game/Wing/MI_Front_Scalar"}
        for w, m in self.wings.items():
            self.set_("mid", w, "slot0", m)
        self.scalars = {fb.WALNUT_MAT: {"Roughness_Low": 0.3, "Roughness_High": 0.8, "Tint": 1.0},
                        "/Game/Floor/MI_Slats": {"Roughness": 0.6}, "/Game/Wing/MI_Front_Tex": {},
                        "/Game/Wing/MI_Front_Scalar": {"RoughnessScale": 1.0}}
        self.p01_floor = ["/Game/InfinityStage/RigAtmos/MI_Floor_DarkWet.MI_Floor_DarkWet"]

    def add_light(self, lid, label, loc, rot, vsi, component=False):
        self.meta[lid] = {"label": label, "location": loc, "component": component}
        self.set_("light", lid, "rotation", dict(rot))
        self.set_("light", lid, "volumetric_scattering_intensity", vsi)

    def set_(self, kind, oid, field, value):
        if isinstance(value, float):                 # float UPROPERTYs store float32, like the engine
            value = struct.unpack("<f", struct.pack("<f", value))[0]
        self.state[(kind, oid, field)] = copy.deepcopy(value)

    def api_missing(self): return list(self.missing_api)
    def note(self, e): self.events.append(e)
    def log(self, m): self.logs_.append(m)
    def log_error(self, m): self.errors.append(m)
    def logs(self, token): return [m for m in self.logs_ + self.errors if token in m]
    def census(self): return copy.deepcopy(self.census_)

    def snapshot(self):
        return copy.deepcopy((self.state, {k: v["on"] for k, v in self.pool.items()}, self.strobes, self.sweeps))

    # ---- generic access
    def read(self, kind, oid, field):
        return copy.deepcopy(self.state[(kind, oid, field)])

    def write(self, kind, oid, field, value):
        self.events.append(("write", fb.key(kind, oid, field)))
        if self.record_path is not None:
            disk = json.loads(pathlib.Path(self.record_path).read_text(encoding="utf-8"))
            if fb.key(kind, oid, field) not in disk["originals"]:
                self.violations.append(fb.key(kind, oid, field))
        if kind == "mid" and isinstance(value, dict):
            value = "MID(%s)" % value["mid_parent"]
        self.set_(kind, oid, field, value)

    # ---- plan reads
    def lights(self):
        out = []
        for (kind, oid, field), _v in sorted(self.state.items()):
            if kind == "light" and field == "rotation":
                m = self.meta[oid]
                out.append({"id": oid, "label": m["label"], "location": list(m["location"]),
                            "component": m["component"],
                            "rotation": self.read("light", oid, "rotation"),
                            "volumetric_scattering_intensity": self.read("light", oid, "volumetric_scattering_intensity"),
                            "visible": True, "intensity": 100.0})
        return out

    def fogs(self):
        return [{"id": self.fog_id, "label": "HeightFog", "fog_density": self.read("fog", self.fog_id, "fog_density"),
                 "second_fog_density": self.read("fog", self.fog_id, "second_fog_density"),
                 "volumetric_fog": self.read("fog", self.fog_id, "volumetric_fog")}]

    def media(self):
        return [{"id": m, "label": self.meta[m]["label"], "location": list(self.meta[m]["location"]),
                 "radial_fog_extinction": self.read("media", m, "radial_fog_extinction"),
                 "height_fog_extinction": self.read("media", m, "height_fog_extinction")}
                for m in ("/PIE/FX_Near.Medium", "/PIE/FX_Far.Medium")]

    def pp_sources(self, cam_loc):
        rows = []
        for pid, m in self.pp_meta.items():
            contains = m["unbound"] or all(abs(c - o) <= e for c, o, e in zip(cam_loc, *m["box"]))
            fields = {f: self.read("pp", pid, f) for (k, i, f) in self.state if k == "pp" and i == pid}
            rows.append({"id": pid, "kind": m["kind"], "label": pid, "enabled": m["enabled"], "unbound": m["unbound"],
                         "priority": m["priority"], "weight": m["weight"],
                         "affects": m["enabled"] and contains and m["weight"] > 0.0, "fields": fields})
        return rows

    def floor_slots(self):
        return [{"id": s, "slot": 0, "material": self.read("mid", s, "slot0"), "label": s} for s in self.slabs]

    def floor_materials(self):
        return [self.read("mid", s, "slot0") for s in self.slabs], list(self.p01_floor)

    def floor_top_z(self, cam_loc): return 0.0

    def wing_slots(self, pose, radius, slot_name):
        return [{"id": w, "slot": 0, "material": self.read("mid", w, "slot0")} for w in sorted(self.wings)]

    def scalar_params(self, material): return dict(self.scalars.get(material, {}))

    # ---- strobes / sweeps
    def show_strobes(self): return [{"id": k, "label": k, "enabled": v} for k, v in sorted(self.strobes.items())]
    def show_strobe_enabled(self, sid): return self.strobes[sid]

    def set_show_strobe(self, sid, en):
        self.events.append(("write", "strobe|" + sid))
        self.strobes[sid] = bool(en)

    def sweep_lights(self): return [{"id": k, "label": k, "enabled": v} for k, v in sorted(self.sweeps.items())]
    def sweep_enabled(self, sid): return self.sweeps[sid]

    def set_sweep(self, sid, en):
        self.events.append(("write", "sweep|" + sid))
        self.sweeps[sid] = bool(en)

    # ---- pool
    def pool_labels(self): return sorted(self.pool)
    def pool_state(self, label): return {"on": self.pool[label]["on"]}

    def show_pool(self, spec):
        self.events.append(("show", spec["label"]))
        self.pool[spec["label"]].update(on=True, spec=spec)

    def hide_pool(self, label):
        self.events.append(("hide", label))
        self.pool[label].update(on=False)


class EditorFake(World):
    def __init__(self, pie_running=False):
        super().__init__("editor")
        self.pie_running = pie_running
        self.census_ = {"maps": [], "content": []}

    def world_kind(self): return "pie_running" if self.pie_running else "editor"
    def world_name(self): return "/Game/InfinityStage/Dev/Maps/%s.%s" % (MAP, MAP)
    def bench_actor_labels(self, prefix): return sorted(l for l in self.pool if l.startswith(prefix))

    def spawn_hidden(self, spec):
        self.events.append(("spawn", spec["label"]))
        self.pool[spec["label"]] = {"on": False}
        if MAP not in self.census_["maps"]:
            self.census_["maps"].append(MAP)
        return "/Game/Maps/%s:PersistentLevel.%s" % (MAP, spec["label"])


class PieFake(World):
    """PIE + transport + camera + an auto-exposure picture: scene brightness from the state, auto exposure
    EV = -3 + 0.7 log2(scene / 80) clamped to the effective [min, max] (a lock pins it), displayed luma approaching
    the target with time constant tau, plus a fault-flicker (brief dips)."""

    def __init__(self, clock, prepared=True, kind="game", tau=1.0, flicker=12.0, residual_after=None,
                 slowmove=False, dirty_on_rotation=False, scrub_result="<InfinityTransportResult.SUCCEEDED: 0>",
                 old_floor=False):
        super().__init__(kind)
        if old_floor:                                    # the pre-6 Oct-11:22 P02 floor
            for s in self.slabs:
                self.set_("mid", s, "slot0", "/Game/Floor/MI_Slats")
        self.clock = clock
        if prepared:
            self.pool = {fb.PREFIX + "MIST_%d" % i: {"on": False} for i in range(4)}
        self.tau, self.flicker, self.residual_after = tau, flicker, residual_after
        self.slowmove, self.dirty_on_rotation, self.scrub_result = slowmove, dirty_on_rotation, scrub_result
        self.frame, self.playing = SEG[0] + 5000, True
        self.lum = None
        self.residual = 0.0
        self.scrubs, self.commands = [], []
        self.slow_orig = {}

    def world_kind(self): return self.kind
    def world_name(self): return "/Game/InfinityStage/Dev/Maps/UEDPIE_0_%s.%s" % (MAP, MAP)

    def passage_segment(self, label):
        if label != "Passage 2":
            raise fb.BenchRefused("no_segment", label)
        return SEG

    def transport_scrub(self, f):
        self.scrubs.append(int(f))
        if "SUCCEEDED" not in self.scrub_result:
            return self.scrub_result
        self.frame, self.playing = int(f), False
        return self.scrub_result

    def transport_pause(self): self.playing = False
    def transport_frame(self): return self.frame

    def cam_x(self):
        return (self.frame - SEG[0]) / float(SEG[1] - SEG[0]) * ROUTE_LEN

    def camera_pose(self, aspect, fov):
        return {"loc": [self.cam_x(), 0.0, 180.0], "rot": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0}, "fov_deg": 90.0,
                "fov_read": 90.0, "aspect": aspect}

    def write(self, kind, oid, field, value):
        super().write(kind, oid, field, value)
        if kind == "light" and field == "rotation" and self.dirty_on_rotation and SHOW not in self.census_["content"]:
            self.census_["content"].append(SHOW)          # simulated Show write-back
        if kind == "pp" or (kind == "light" and field == "rotation"):
            pass

    def scene(self):
        cx = self.cam_x()
        s = 40.0
        for (kind, oid, field), v in self.state.items():
            if kind == "light" and field == "volumetric_scattering_intensity" and abs(self.meta[oid]["location"][0] - cx) < 6000:
                s += 3.0 * v
            if kind == "fog" and field == "fog_density":
                s += 400.0 * v
            if kind == "media" and abs(self.meta[oid]["location"][0] - cx) < 8000:
                s += 20.0 * v
            if kind == "mid" and isinstance(v, str) and v.startswith("MID("):
                s += 2.0
            if kind == "light" and field == "rotation" and v.get("pitch") == -85.0:
                s -= 1.0
        s += 4.0 * sum(1 for p in self.pool.values() if p["on"])
        return s

    def exposure_ev(self, scene):
        lo, hi = -99.0, 99.0
        srcs = [r for r in self.pp_sources([self.cam_x(), 0.0, 180.0]) if r["affects"]]
        for r in sorted(srcs, key=lambda r: (r["kind"] == "camera", r["priority"])):
            if r["fields"]["override_auto_exposure_min_brightness"]:
                lo = r["fields"]["auto_exposure_min_brightness"]
            if r["fields"]["override_auto_exposure_max_brightness"]:
                hi = r["fields"]["auto_exposure_max_brightness"]
        return min(hi, max(lo, -3.0 + 0.7 * math.log2(scene / 80.0)))

    def target(self):
        sc = self.scene()
        return sc * 2.0 ** (-(self.exposure_ev(sc) + 3.0))

    def displayed(self):
        t = self.clock[0]
        dip = self.flicker if (t * 2.3) % 1.0 < 0.12 else 0.0
        return self.lum - dip + self.residual

    def advance(self, dt):
        if self.lum is None:
            self.lum = self.target()
        self.lum += (self.target() - self.lum) * (1.0 - math.exp(-dt / self.tau))
        if self.residual_after and any(p["on"] for p in self.pool.values()):
            self.residual = 25.0                         # a change the bench does not know about stays behind
        if self.slowmove:
            lid = "/PIE/P02_B08_LOW_SIDE_L_KEY"
            self.slow_orig.setdefault(lid, self.read("light", lid, "rotation"))
            if self.record_path is not None:
                self.state[("light", lid, "rotation")] = copy.deepcopy(self.slow_orig[lid])   # Drama slow-move

    def console(self, cmd):
        if self.kind != "game":
            raise fb.BenchRefused("pie_ended", "console")
        self.commands.append(cmd)
        m = re.search(r'filename="([^"]+)"', cmd)
        if not m:
            return
        path = m.group(1)
        if "_probes" in path:
            write_png(path, 8, 6, self.displayed())
        else:
            write_png(path, 16, 9, self.displayed())


def prepared_record(name="prep"):
    ed = EditorFake()
    d = tmp / name / "P02FOGPREP-x"
    d.mkdir(parents=True)
    fb.PrepareBench(ed, d / fb.PREPARE_RECORD_NAME, {}, "P02FOGPREP-" + name).run()
    return ed, d / fb.PREPARE_RECORD_NAME


ED, PREP = prepared_record()
TEST_P = {"file_min_bytes": 50, "settle_min_seconds": 3.0}


def run(params=None, dt=0.05, max_t=3000.0, dry=False, store=None, **kw):
    clock = [0.0]
    f = PieFake(clock, **kw)
    store = store or Store()
    reg = {}
    out_root = tmp / ("run_%d" % len(RESULTS))
    p = dict(TEST_P)
    p.update(params or {})
    f.advance(0.0)
    snap = f.snapshot()
    r = fb.arm(f, PREP, p, dry=dry, out_root=out_root, prepare_root=tmp / "nowhere", owner_path=tmp / "owner_none.json",
               walnut_record=tmp / "no_walnut.json", register=lambda fn: reg.setdefault("fn", fn) and "H",
               unregister=lambda h: reg.setdefault("unreg", h), store=store, clock=lambda: clock[0])
    f.record_path = pathlib.Path(r["run_dir"]) / fb.ORIGINALS_NAME
    mid_run = {}
    while not r.get("finished") and clock[0] < max_t:
        clock[0] += dt
        f.advance(dt)
        reg["fn"](dt)
        if not mid_run and any(isinstance(e, tuple) and e[0] == "write" and e[1].startswith("light|") for e in f.events):
            mid_run = {"strobes": dict(f.strobes), "sweeps": dict(f.sweeps)}
    return r, f, snap, mid_run


# ======================= PREPARE (editor world) =======================
iw = next(i for i, e in enumerate(ED.events) if e == "record_written")
ic = next(i for i, e in enumerate(ED.events) if isinstance(e, tuple) and e[0] == "spawn")
check("+ PREPARE: record (labels + census) written before the first spawn", iw < ic)
prep_disk = json.loads(PREP.read_text(encoding="utf-8"))
check("+ PREPARE: 4 hidden ZZ_P02FOG_MIST_* fog volumes, status spawned, map dirtied by PREPARE only",
      prep_disk["status"] == "spawned" and sorted(ED.pool) == ["ZZ_P02FOG_MIST_%d" % i for i in range(4)]
      and not any(v["on"] for v in ED.pool.values()) and prep_disk["dirtied_by_prepare"] == {"maps": [MAP], "content": []}
      and ED.logs("P02_FOG_BENCH_PREPARE_OK|run=P02FOGPREP-prep") and ED.logs(fb.RESTART + "|run="))
ed_bad = EditorFake()
ed_bad.spawn_hidden({"label": "ZZ_P02FOG_EARLY"})
ed_bad.pool.clear(); ed_bad.census_ = {"maps": [], "content": []}
(tmp / "pb").mkdir()
fb.PrepareBench(ed_bad, tmp / "pb" / "r.json", {}, "PB").run()
iw2 = next(i for i, e in enumerate(ed_bad.events) if e == "record_written")
ic2 = next(i for i, e in enumerate(ed_bad.events) if isinstance(e, tuple) and e[0] == "spawn")
check("- control: a spawn before the record is caught by the same ordering check", not iw2 < ic2)
check("+ PREPARE refuses while PIE is running (spawns nothing)",
      raises(lambda: fb.PrepareBench(EditorFake(True), tmp / "pb" / "a.json").run(), "reason=prepare_needs_editor"))
dirty_ed = EditorFake()
dirty_ed.census_["content"].append(SHOW)
check("+ PREPARE refuses on a dirty census (a Don't-Save restart must lose nothing), spawning nothing, no record",
      raises(lambda: fb.PrepareBench(dirty_ed, tmp / "pb" / "b.json").run(), "reason=dirty_before_prepare")
      and not dirty_ed.pool and not (tmp / "pb" / "b.json").exists())
left_ed = EditorFake()
left_ed.pool["ZZ_P02FOG_MIST_0"] = {"on": False}
check("+ PREPARE refuses when ZZ_P02FOG_ actors already exist", raises(lambda: fb.PrepareBench(left_ed, tmp / "pb" / "c.json").run(),
                                                                        "reason=leftovers"))
check("- control: a clean editor prepares", not raises(lambda: fb.PrepareBench(EditorFake(), tmp / "pb" / "d.json").run(), "FAILED"))

# ======================= pure plans on the fake world =======================
W = PieFake([0.0])
POSE8 = W.camera_pose(16 / 9.0, 90.0)
POSE8["loc"] = [7 * PITCH, 0.0, 180.0]
P = dict(fb.DEFAULTS)
LIGHTS = W.lights()

check("+ nearest bay ahead at the bay-8 pose is 8; at the bay-15 pose 15",
      fb.nearest_bay_ahead(LIGHTS, POSE8) == 8 and fb.nearest_bay_ahead(LIGHTS, dict(POSE8, loc=[14 * PITCH, 0.0, 180.0])) == 15)
check("- control: looking from bay 3 the nearest bay is not 8", fb.nearest_bay_ahead(LIGHTS, dict(POSE8, loc=[2 * PITCH, 0.0, 180.0])) != 8)
rows = fb.position_rows(*SEG, P["positions"], P)
check("+ positions: bay 8 -> fraction 7/23, bay 15 -> 14/23 via passage_stills.fraction_to_frame",
      [r["name"] for r in rows] == ["bay08", "bay15"] and abs(rows[0]["fraction"] - 7 / 23.0) < 1e-12
      and rows[1]["target_frame"] == fb.ps.fraction_to_frame(*SEG, 14 / 23.0))
check("- control: two positions on one frame are refused",
      raises(lambda: fb.position_rows(*SEG, ({"name": "a", "bay": 8}, {"name": "b", "bay": 8}), P), "positions_collide"))

# A
pa = fb.plan_a(LIGHTS, POSE8, P)
near = [l for l in LIGHTS if fb.dist3(l["location"], POSE8["loc"]) <= P["a_radius_cm"]]
kept = pa["info"]["kept_beams"]
zero_ids = {o[1] for o in pa["ops"]}
check("+ A: keeps 1-2 BEAM lamps, each in view, nearest first; zeroes vsi on every other lamp within the radius "
      "(fills, practicals, TOP, office tube); nothing else changes",
      1 <= len(kept) <= 2 and all("BEAM" in k for k in kept)
      and all(o[0] == "light" and o[2] == "volumetric_scattering_intensity" and o[3] == 0.0 for o in pa["ops"])
      and zero_ids == {l["id"] for l in near if l["label"] not in kept})
check("+ A: lamps beyond a_radius_cm are untouched (the far P05 lamp, bay 20+ lamps)",
      "/PIE/Far_Lamp" not in zero_ids and not any("B2" in i and int(i.split("_B")[1][:2]) >= 20 for i in zero_ids))
back = fb.plan_a(LIGHTS, dict(POSE8, rot={"yaw": 0.0, "pitch": 80.0, "roll": 0.0}), P)
check("- control: a camera looking up at the grid sees no beam: nothing kept, A_NO_BEAM flagged",
      back["info"]["no_beam_in_view"] and not back["info"]["kept_beams"])
pa15 = fb.plan_a(LIGHTS, dict(POSE8, loc=[14 * PITCH + 3000.0, 0.0, 180.0]), P)
check("+ A at a stretch with no BEAM lamps ahead flags no_beam_in_view (P02 bays 14-23 carry none in the record)",
      pa15["info"]["no_beam_in_view"])

# B
pb = fb.plan_b(W.fogs(), W.media(), POSE8, 0.0, P)
ob = {fb.key(*o[:3]): o[3] for o in pb["ops"]}
F = pb["pool"][0]["falloff"]
check("+ B: global fog density and second-fog density x0.15; volumetric fog kept ON (LFVs reach volumetric fog only then)",
      abs(ob["fog|%s|fog_density" % W.fog_id] - W.fogs()[0]["fog_density"] * 0.15) < 1e-12
      and abs(ob["fog|%s|second_fog_density" % W.fog_id] - W.fogs()[0]["second_fog_density"] * 0.15) < 1e-12
      and abs(W.fogs()[0]["fog_density"] - 0.035) < 1e-8
      and "fog|%s|volumetric_fog" % W.fog_id not in ob)
check("+ B: the near effect medium's radial + height extinction go to 0; the far one is untouched",
      ob.get("media|/PIE/FX_Near.Medium|radial_fog_extinction") == 0.0 and ob.get("media|/PIE/FX_Near.Medium|height_fog_extinction") == 0.0
      and not any("FX_Far" in k for k in ob))
check("+ B: 4 mist volumes on the floor, ahead of the camera, uniform scale, radial 0, density 5% of floor at 150 cm",
      len(pb["pool"]) == 4 and all(s["loc"][2] == 0.0 and s["radial"] == 0.0 for s in pb["pool"])
      and [s["loc"][0] for s in pb["pool"]] == sorted(s["loc"][0] for s in pb["pool"]) and pb["pool"][0]["loc"][0] > POSE8["loc"][0]
      and abs(math.exp(-F * 150.0 / 1600.0) - 0.05) < 1e-9 and pb["pool"][0]["scale"] == 3.2)
pb_off = fb.plan_b(W.fogs(), W.media(), POSE8, 0.0, dict(P, b_volumetric="off", b_media="keep"))
check("- control: b_volumetric='off' adds the volumetric op and b_media='keep' leaves the media",
      ("fog", W.fog_id, "volumetric_fog", False) in pb_off["ops"] and not any(o[0] == "media" for o in pb_off["ops"]))

# C
pc = fb.plan_c(LIGHTS, POSE8, 8, P)
fwd, right = fb.route_axes(POSE8)


def graze_ok(o, lights, deg=12.0):
    l = next(x for x in lights if x["id"] == o[1])
    d = lb.rotator_axes(o[3]["yaw"], 0.0, 0.0)[0]
    _al, lat = fb.along_lateral(POSE8, l["location"])
    a = math.degrees(math.acos(max(-1.0, min(1.0, d[0] * fwd[0] + d[1] * fwd[1]))))
    toward_own = (d[0] * right[0] + d[1] * right[1]) * lat > 0
    return abs(a - deg) < 1e-6 and toward_own


c_ids = {o[1] for o in pc["ops"]}
c_bays = sorted({fb.lamp_bay(next(l for l in LIGHTS if l["id"] == i)["label"]) for i in c_ids})
lit_ops = [o for o in pc["ops"] if o[3]["pitch"] != P["c_dark_pitch_deg"]]
dark_ops = [o for o in pc["ops"] if o[3]["pitch"] == P["c_dark_pitch_deg"]]
check("+ C: only LOW_SIDE lamps of bays 7..12 are re-aimed (rotation only: no Show / other field op)",
      c_bays == list(range(7, 13)) and all("LOW_SIDE" in next(l for l in LIGHTS if l["id"] == i)["label"] for i in c_ids)
      and all(o[0] == "light" and o[2] == "rotation" for o in pc["ops"]))
check("+ C: lit layers graze 12 deg off the route toward their OWN side's wing; dark layers aim at the floor (-85)",
      lit_ops and dark_ops and all(graze_ok(o, LIGHTS) for o in lit_ops))
lit_b = sorted({fb.lamp_bay(next(l for l in LIGHTS if l["id"] == o[1])["label"]) for o in lit_ops})
dark_b = sorted({fb.lamp_bay(next(l for l in LIGHTS if l["id"] == o[1])["label"]) for o in dark_ops})
check("+ C: light and dark alternate in depth (bays 7,9,11 lit; 8,10,12 dark)", lit_b == [7, 9, 11] and dark_b == [8, 10, 12])
authored = [("light", o[1], "rotation", next(l for l in LIGHTS if l["id"] == o[1])["rotation"]) for o in lit_ops]
check("- control: the authored face-on aims (yaw +-72) fail the same graze check", not any(graze_ok(o, LIGHTS) for o in authored))
check("- control: c_direction='back' points the lit lamps toward the camera (graze check vs fwd fails)",
      not any(graze_ok(o, LIGHTS) for o in fb.plan_c(LIGHTS, POSE8, 8, dict(P, c_direction="back"))["ops"]
              if o[3]["pitch"] != P["c_dark_pitch_deg"]))

# D
SRC = W.pp_sources(POSE8["loc"])
pd_ = fb.plan_d(SRC, -2.5)
d_ids = {o[1] for o in pd_}
expo = fb.effective_exposure(SRC)
check("+ D: min = max = EV (+ override flags) on every source that affects the camera (unbound PPV + camera), "
      "not on a bounded PPV elsewhere or a disabled one",
      d_ids == {"/PIE/PPV_Unbound", "/PIE/CineCam.Camera"} and len(pd_) == 8
      and all(o[3] == -2.5 for o in pd_ if o[2].startswith("auto_")) and all(o[3] is True for o in pd_ if o[2].startswith("override_")))
check("+ D: the fake base is auto (min -8, max 4, histogram): not locked, not manual", not expo["locked"] and not expo["manual"]
      and expo["min"] == -8.0 and expo["max"] == 4.0)
locked_src = copy.deepcopy(SRC)
locked_src[0]["fields"].update(auto_exposure_min_brightness=-3.0, auto_exposure_max_brightness=-3.0)
check("- control: min == max is reported as already locked", fb.effective_exposure(locked_src)["locked"])
check("+ bisect_ev: too bright raises the floor, too dark lowers the ceiling",
      fb.bisect_ev(-8.0, 4.0, -2.0, 100.0, 80.0) == (-2.0, 4.0) and fb.bisect_ev(-8.0, 4.0, -2.0, 60.0, 80.0) == (-8.0, -2.0))

# E
scal = {m: W.scalar_params(m) for m in (fb.WALNUT_MAT, "/Game/Wing/MI_Front_Tex", "/Game/Wing/MI_Front_Scalar")}
pe = fb.plan_e(SRC, W.floor_slots(), W.wing_slots(POSE8, 4000.0, "Front"), scal, P)
pp_ops = [o for o in pe["ops"] if o[0] == "pp"]
mid_ops = [o for o in pe["ops"] if o[0] == "mid"]
check("+ E: Lumen reflection quality 2 / screen traces / max roughness 0.6 with override flags, on affecting sources only",
      {o[1] for o in pp_ops} == {"/PIE/PPV_Unbound", "/PIE/CineCam.Camera"} and len(pp_ops) == 12
      and ("pp", "/PIE/PPV_Unbound", "lumen_max_roughness_to_trace_reflections", 0.6) in pp_ops)
check("+ E: walnut floor MIDs scale only the 'rough' scalars (Roughness_Low 0.3, Roughness_High 0.8 x0.35; Tint "
      "untouched) on all 4 slabs; the texture-only wing is a logged no-op, the scalar wing gets a MID",
      len([o for o in mid_ops if "Floor" in o[1]]) == 4
      and all(o[3]["scalars"] == {"Roughness_Low": 0.3 * 0.35, "Roughness_High": 0.8 * 0.35} and
              o[3]["mid_parent"] == fb.WALNUT_MAT for o in mid_ops if "Floor" in o[1])
      and pe["info"]["wing_noop"] == 1 and pe["info"]["wing_mids"] == 1)
check("- control: a token no scalar holds makes the floor a no-op (E_FLOOR_NOOP path)",
      fb.plan_e(SRC, W.floor_slots(), [], scal, dict(P, e_rough_token="zzz"))["info"]["floor_mids"] == 0)

# ALL / base
plans = {"A": pa, "B": pb, "C": pc, "E": pe, "D_sources": SRC}
all_ops, all_pool = fb.variant_plan("ALL", plans, -2.5)
union = set()
for v in "ABCDE":
    union |= {fb.key(*o[:3]) for o in fb.variant_plan(v, plans, -2.5)[0]}
check("+ ALL = exactly the union of A..E (no key lost, none added), with B's mist; base has no op",
      {fb.key(*o[:3]) for o in all_ops} == union and len(all_pool) == 4 and fb.variant_plan("base", plans, -2.5) == ([], []))
bad_plans = dict(plans, C={"ops": [("light", pa["ops"][0][1], "volumetric_scattering_intensity", 9.0)], "pool": [], "info": {}})
check("- control: two variants writing different values to one key are refused in ALL",
      raises(lambda: fb.variant_plan("ALL", bad_plans, -2.5), "P02_FOG_BENCH_CONFLICT"))

# ======================= variant ordering + base-return logic =======================
EXPECT = [("jump",), ("repose",), ("settle", "base_ref"), ("plan",), ("shoot", "base"), ("dcal",)]
for v in ("A", "B", "C", "D", "E", "ALL"):
    EXPECT += [("settle", "base_return"), ("apply", v), ("settle", "state"), ("hold", v), ("shoot", v)]
EXPECT.append(("settle", "base_return_final"))
check("+ order: base, D calibration, then A B C D E ALL, each after a base return, a final base return",
      fb.position_tasks(fb.ORDER, True) == EXPECT)


def ordering_ok(tasks):
    """Every apply follows a base return since the last change; base is shot before any change; ends on base."""
    clean, changed_any = True, False
    for t in tasks:
        if t[0] in ("apply", "dcal", "dcal_step"):
            if t[0] == "apply" and not clean:
                return False
            clean, changed_any = False, True
        if t == ("settle", "base_return") or t == ("settle", "base_return_final"):
            clean = True
        if t == ("shoot", "base") and changed_any:
            return False
    return clean


check("+ ordering checker accepts the planned order", ordering_ok(fb.position_tasks(fb.ORDER, True)))
broken = [t for t in fb.position_tasks(fb.ORDER, True)]
broken.remove(("settle", "base_return"))
check("- control: dropping one base return is caught", not ordering_ok(broken))
check("- control: no final base return is caught", not ordering_ok(fb.position_tasks(fb.ORDER, True)[:-1]))
check("+ dry run plans only: jump, repose, base settle, plan, base shot",
      fb.position_tasks(fb.ORDER, True, dry=True) == EXPECT[:5])

# ======================= robust gates =======================
Pg = dict(fb.DEFAULTS)
flick = [[0.5 * i, 88.0 - (12.0 if i % 7 == 3 else 0.0)] for i in range(12)]
check("+ robust settle: a stationary flicker (fault dips) is 'stable'", fb.robust_settle(flick, 6.0, Pg) == "stable")
check("- control: look_bench's strict gate on the same samples never settles (why the gate is robust here)",
      lb.settle_decision(flick, 6.0, lb.DEFAULTS) == "wait" and lb.settle_decision(flick, 30.0, lb.DEFAULTS) == "timeout")
drift = [[0.5 * i, 60.0 + 4.0 * i] for i in range(12)]
check("- control: a picture still adapting is never 'stable' (wait, then timeout)",
      fb.robust_settle(drift, 6.0, Pg) == "wait" and fb.robust_settle(drift, 30.0, Pg) == "timeout")
ref = fb.stats([88, 88, 76, 88, 88, 88])
check("+ base return: same picture with flicker passes", fb.base_return_ok(fb.stats([88, 76, 88, 88, 88, 87]), ref, Pg)[0])
check("- control: a picture left 25 brighter fails", not fb.base_return_ok(fb.stats([113, 101, 113, 113, 113, 112]), ref, Pg)[0])

# ======================= bench: originals, apply, restore =======================
Wb = PieFake([0.0])
Wb.record_path = None
before = Wb.snapshot()
bb = fb.FogBench(Wb, tmp / "bench1.json", {}, "P02FOG-T1")
bb.read_globals(Wb.census(), {"run": "x"})
ops_all, pool_all = fb.variant_plan("ALL", plans, -2.5)
check("- control: apply before the keys are recorded is refused (originals first)",
      raises(lambda: bb.apply("ALL", ops_all, pool_all), "P02_FOG_BENCH_NOT_RECORDED"))
bb.record_keys(fb.all_keys(plans), "bay08", {"x": 1})
Wb.record_path = tmp / "bench1.json"
bb.neutralise()
bb.apply("ALL", ops_all, pool_all)
check("+ apply ALL: every op key was on disk before its write (no violation)", not Wb.violations and len(ops_all) > 100)
check("+ apply ALL changed the world (lights, fog, media, pp, mids, pool, strobe + car off)",
      Wb.snapshot() != before and Wb.strobes["/PIE/P02_Strobe"] is False and Wb.sweeps["/PIE/P02_Car"] is False
      and sum(v["on"] for v in Wb.pool.values()) == 4)
check("+ restore is exact: verify() == [] and the whole fake world equals its pre-bench snapshot",
      bb.restore() == [] and Wb.snapshot() == before)
Wv = PieFake([0.0])
Wv.write("light", "/PIE/Tube_01", "volumetric_scattering_intensity", 0.0)
Wv.record_path = tmp / "bench1.json"
Wv.write("light", "/PIE/Not_Recorded", "volumetric_scattering_intensity", 0.0)
check("- control: the write-before-record detector flags an unrecorded key", Wv.violations == ["light|/PIE/Not_Recorded|volumetric_scattering_intensity"])
Wl = PieFake([0.0])
bl = fb.FogBench(Wl, tmp / "bench2.json", {}, "P02FOG-T2")
bl.read_globals(Wl.census(), None)
bl.record_keys(fb.all_keys(plans))
bl.apply("ALL", ops_all, pool_all)
orig_write = Wl.write
Wl.write = lambda k, o, f, v: None if (k == "fog" and f == "fog_density") else orig_write(k, o, f, v)
check("- control: a lost restore write is reported by verify()", any("fog_density" in x for x in bl.restore()))
Wl.write = orig_write
bl.apply("B", *fb.variant_plan("B", plans, None))
Wl.hide_pool = lambda label: None
check("- control: a mist volume left shown is reported", any("pool still shown" in x for x in bl.restore()))
Wr = PieFake([0.0])
before_r = Wr.snapshot()
br = fb.FogBench(Wr, tmp / "bench3.json", {}, "P02FOG-T3")
br.read_globals(Wr.census(), None)
br.record_keys(fb.all_keys(plans))
br.neutralise()
br.apply("ALL", ops_all, pool_all)
del br                                                  # "editor died here"
check("+ RESTORE from the record alone is exact (lights, fog, media, pp, mids, pool, strobe, car)",
      fb.restore_all(Wr, [tmp / "bench3.json"], Wr.log) == [] and Wr.snapshot() == before_r)
check("+ rotation compare: 0.0005 deg is the same aim (rotator round trip); - control: 0.01 deg is not",
      fb.same_value("rotation", {"roll": 0, "pitch": 4.0, "yaw": 72.0}, {"roll": 0, "pitch": 4.0005, "yaw": 72.0}, 1e-3)
      and not fb.same_value("rotation", {"roll": 0, "pitch": 4.0, "yaw": 72.0}, {"roll": 0, "pitch": 4.01, "yaw": 72.0}, 1e-3))
f32 = struct.unpack("<f", struct.pack("<f", 0.6))[0]
check("+ float compare: 0.6 written, float32 0.6000000238 read back is the same value; - control: 0.601 is not, "
      "and True != 1.0", fb.same_value("lumen_max_roughness_to_trace_reflections", 0.6, f32, 1e-3)
      and not fb.same_value("x", 0.6, 0.601, 1e-3) and not fb.same_value("x", True, 1.0, 1e-3))
check("+ angle wrap: yaw 179.9995 equals -180", fb.same_value("rotation", {"roll": 0, "pitch": 0, "yaw": 179.9995},
                                                              {"roll": 0, "pitch": 0, "yaw": -180.0}, 1e-3))

# ======================= full CAPTURE runs on the fake =======================
r1, f1, snap1, mid1 = run()
man = json.loads((pathlib.Path(r1["run_dir"]) / fb.MANIFEST_NAME).read_text(encoding="utf-8"))
ok_lines = f1.logs("P02_FOG_BENCH_CAPTURE_OK|")
check("+ run: CAPTURE_OK|run=P02FOG-... logged, status passed, no gate failure, no error",
      ok_lines and re.match(r"P02_FOG_BENCH_CAPTURE_OK\|run=P02FOG-\d{8}-\d{6}\|", ok_lines[0])
      and man["status"] == "passed" and not man["gate_failures"] and not man["errors"])
stills = [s for pos in man["positions"] for v in pos["shots"].values() for s in v["stills"]]
check("+ run: 2 positions x 7 variants x 3 stills = 42 PNGs on disk, in P02FogBench/<run>/<pos>/<variant>_<i>.png",
      len(stills) == 42 and all(pathlib.Path(s["path"]).is_file() for s in stills)
      and {pathlib.Path(s["path"]).parent.name for s in stills} == {"bay08", "bay15"})
check("+ run: the whole fake world is back to its pre-run snapshot (restore exact), census unchanged",
      f1.snapshot() == snap1 and man["census_after"] == man["census_before"])
check("+ run: originals of every key were on disk before its write (both positions)", not f1.violations)
check("+ run: show strobe and car light were OFF during the variants and restored after",
      mid1 == {"strobes": {"/PIE/P02_Strobe": False}, "sweeps": {"/PIE/P02_Car": False}}
      and f1.strobes["/PIE/P02_Strobe"] is True and f1.sweeps["/PIE/P02_Car"] is True)
tl = [tuple(t[1:]) for t in man["task_log"]]
per_pos = {}
for t in man["task_log"]:
    per_pos.setdefault(t[0], []).append(tuple(t[1:]))
check("+ run: executed order per position obeys base-first / base-return-between / base-final (dcal expanded)",
      set(per_pos) == {"bay08", "bay15"} and all(ordering_ok(v) for v in per_pos.values())
      and [t for t in per_pos["bay08"] if t[0] == "apply"] == [("apply", v) for v in ("A", "B", "C", "D", "E", "ALL")])
brs = [b for pos in man["positions"] for b in pos["base_returns"]]
check("+ run: 7 base returns per position (after dcal and each variant), all within the flicker-tolerant gate",
      len(brs) == 14 and all(b["ok"] for b in brs))
truth = [f1.exposure_ev.__func__ for _ in (0,)]
ev_err = []
for pos in man["positions"]:
    f1.frame = pos["target_frame"]
    sc = f1.scene()
    ev_err.append(abs(pos["ev"] - (-3.0 + 0.7 * math.log2(sc / 80.0))))
check("+ D calibration: the bisected EV matches the auto exposure the base settled at (|err| < 0.1 EV)",
      all(e < 0.1 for e in ev_err) and all(len(p["dcal"]["iters"]) >= 3 for p in man["positions"]))
check("+ markers carry the run id: START, ANNOUNCE, PLAN, BASE_RETURN, STILL, CAPTURE_OK, NEEDS_DONT_SAVE_RESTART",
      all(any(m.startswith("P02_FOG_BENCH_%s|run=%s" % (t, r1["run_id"])) for m in f1.logs_)
          for t in ("START", "ANNOUNCE", "PLAN", "BASE_RETURN", "STILL", "CAPTURE_OK", "NEEDS_DONT_SAVE_RESTART")))
check("+ walnut: the default fake floor is the walnut MIC -> applied, no E_BEFORE_WALNUT, manifest records it",
      not f1.logs("E_BEFORE_WALNUT") and man["walnut"]["applied"] is True and man["walnut"]["p02"] == [fb.WALNUT_MAT])
rW, fW, _s, _m = run(params={"walnut_policy": "warn"}, old_floor=True)
mW = json.loads((pathlib.Path(rW["run_dir"]) / fb.MANIFEST_NAME).read_text(encoding="utf-8"))
check("+ walnut warn on the old floor: E_BEFORE_WALNUT logged with the floor's material, manifest applied=False",
      fW.logs("P02_FOG_BENCH_E_BEFORE_WALNUT|run=%s|P02 floor slots /Game/Floor/MI_Slats" % rW["run_id"])
      and mW["walnut"]["applied"] is False and mW["status"] == "passed")

rD, fD, _s, _m = run(params={"d_cal_iters": 1, "d_ev_clamp": (-8.0, 0.0)})
errD = []
for pos in json.loads((pathlib.Path(rD["run_dir"]) / fb.MANIFEST_NAME).read_text(encoding="utf-8"))["positions"]:
    fD.frame = pos["target_frame"]
    errD.append(abs(pos["ev"] - (-3.0 + 0.7 * math.log2(fD.scene() / 80.0))))
check("- control: one bisection step lands far from the base EV (> 0.5 EV) and fails the calibration gate",
      max(errD) > 0.5 and fD.logs("P02_FOG_BENCH_FAILED|run=") and fD.logs("dcal"))

rL, fL, _s, _m = run(params={})
check("+ (repeat run passes too: no state leaks between runs)", fL.logs("P02_FOG_BENCH_CAPTURE_OK|"))

clockL = [0.0]
fLk = PieFake(clockL)
fLk.state[("pp", "/PIE/PPV_Unbound", "auto_exposure_min_brightness")] = -3.0
fLk.state[("pp", "/PIE/PPV_Unbound", "auto_exposure_max_brightness")] = -3.0
regL = {}
rLk = fb.arm(fLk, PREP, TEST_P, out_root=tmp / "locked", prepare_root=tmp / "nowhere", owner_path=tmp / "o.json",
             walnut_record=tmp / "w.json", register=lambda fn: regL.setdefault("fn", fn) and "H", unregister=lambda h: None,
             store=Store(), clock=lambda: clockL[0])
while not rLk.get("finished") and clockL[0] < 3000:
    clockL[0] += 0.05
    fLk.advance(0.05)
    regL["fn"](0.05)
mLk = json.loads((pathlib.Path(rLk["run_dir"]) / fb.MANIFEST_NAME).read_text(encoding="utf-8"))
check("+ D with an already-locked base (min = max = -3): D_ALREADY_LOCKED, no calibration steps, D re-pins -3",
      fLk.logs("P02_FOG_BENCH_D_ALREADY_LOCKED|run=") and all(p["ev"] == -3.0 and not p["dcal"]["iters"] for p in mLk["positions"])
      and not any(t[1] == "dcal_step" for t in mLk["task_log"]) and mLk["status"] == "passed")

rR, fR, snapR, _m = run(residual_after="B")
mR = json.loads((pathlib.Path(rR["run_dir"]) / fb.MANIFEST_NAME).read_text(encoding="utf-8"))
check("- control: a change that leaves the picture 25 brighter after B is caught (BASE_RETURN ok=False -> FAILED)",
      any(not b["ok"] for p in mR["positions"] for b in p["base_returns"]) and mR["status"] == "failed"
      and fR.logs("P02_FOG_BENCH_FAILED|run=%s|reason=base_return" % rR["run_id"]))

rS, fS, _s, _m = run(slowmove=True)
mS = json.loads((pathlib.Path(rS["run_dir"]) / fb.MANIFEST_NAME).read_text(encoding="utf-8"))
check("+ hold check: a lamp re-aimed back by a slow-move (Light Drama) during C is reported HELD ok=False, run FAILED",
      fS.logs("P02_FOG_BENCH_HELD|run=%s|pos=bay08|variant=C|ok=False" % rS["run_id"]) and mS["status"] == "failed")
check("- control: without the slow-move every HELD line is ok=True", all("ok=True" in m for m in f1.logs("P02_FOG_BENCH_HELD|")))

rC, fC, _s, _m = run(dirty_on_rotation=True)
check("+ census gate: a Show write-back during C (Show dirtied) fails the run with a census problem",
      fC.logs("P02_FOG_BENCH_FAILED|run=%s|reason=census" % rC["run_id"]))
check("- control: the clean run's census is unchanged", man["census_after"] == man["census_before"])

rP, fP, _s, _m = run(params={"positions": ({"name": "bay08", "bay": 8, "fraction": 2 / 23.0},
                                           {"name": "bay15", "bay": 15})})
check("+ position gate: a position whose camera sees bay 3 (not ~8) is a gate failure",
      fP.logs("P02_FOG_BENCH_GATE|run=%s|position bay08 nearest_bay=3" % rP["run_id"]))
check("- control: the default positions log nearest_bay=8 and 15", f1.logs("|pos=bay08|target_bay=8|nearest_bay=8|")
      and f1.logs("|pos=bay15|target_bay=15|nearest_bay=15|"))

rY, fY, snapY, _m = run(dry=True)
mY = json.loads((pathlib.Path(rY["run_dir"]) / fb.MANIFEST_NAME).read_text(encoding="utf-8"))
check("+ dry run: plans + base stills only, no property write at all, passes",
      mY["status"] == "passed" and not [e for e in fY.events if isinstance(e, tuple) and e[0] == "write"
                                        and not e[1].startswith(("strobe|", "sweep|"))]
      and len([s for p in mY["positions"] for v in p["shots"].values() for s in v["stills"]]) == 6)

# ======================= refusals at CAPTURE arm =======================


def arm_only(f, store=None, prep=PREP, params=None, owner=None, walnut=None, out=None):
    out = out or tmp / ("arm_%d" % len(RESULTS))
    return fb.arm(f, prep, dict(TEST_P, **(params or {})), out_root=out, prepare_root=tmp / "nowhere",
                  owner_path=owner or tmp / "o.json", walnut_record=walnut or tmp / "w.json",
                  register=lambda fn: "H", unregister=lambda h: None, store=store or Store(), clock=lambda: 0.0)


nopie = PieFake([0.0], kind=None)
out_np = tmp / "nopie_out"
check("+ CAPTURE refuses without PIE: FAILED|run=P02FOG-...|reason=no_pie, no run dir, no write",
      raises(lambda: arm_only(nopie, out=out_np), "reason=no_pie") and not out_np.exists()
      and re.match(r"P02_FOG_BENCH_FAILED\|run=P02FOG-\d{8}-\d{6}\|reason=no_pie", nopie.errors[0])
      and not [e for e in nopie.events if isinstance(e, tuple)])
check("+ CAPTURE refuses with the pool missing (PREPARE not run before PIE)",
      raises(lambda: arm_only(PieFake([0.0], prepared=False)), "reason=pool_missing"))
lit_f = PieFake([0.0])
lit_f.pool["ZZ_P02FOG_MIST_1"]["on"] = True
check("+ CAPTURE refuses while a pool volume is still shown (RESTORE first)", raises(lambda: arm_only(lit_f), "reason=pool_not_base"))
armed = Store()
armed.PUSS_PASSAGE_STILLS_HANDLE = "H"
check("+ CAPTURE refuses while another PUSS_* tick is armed", raises(lambda: arm_only(PieFake([0.0]), store=armed), "reason=tick_armed"))
(tmp / "owner_on.json").write_text('{"active": true}', encoding="utf-8")
check("+ CAPTURE refuses with an active pie_recording_owner.json",
      raises(lambda: arm_only(PieFake([0.0]), owner=tmp / "owner_on.json"), "reason=pie_owner_active"))
other = dict(prep_disk, world="/Game/Other/L_Other.L_Other")
(tmp / "other.json").write_text(json.dumps(other), encoding="utf-8")
check("+ CAPTURE refuses a PREPARE record from another level", raises(lambda: arm_only(PieFake([0.0]), prep=tmp / "other.json"),
                                                                      "reason=wrong_world"))
check("+ CAPTURE refuses with no PREPARE record", raises(lambda: arm_only(PieFake([0.0]), prep=tmp / "missing.json"),
                                                         "reason=not_prepared"))
partial = dict(prep_disk, status="partial")
(tmp / "partial.json").write_text(json.dumps(partial), encoding="utf-8")
check("+ CAPTURE refuses a partial PREPARE", raises(lambda: arm_only(PieFake([0.0]), prep=tmp / "partial.json"), "reason=prepare_incomplete"))
check("+ walnut_policy=require (the default) refuses while the P02 floor is not the walnut MIC",
      raises(lambda: arm_only(PieFake([0.0], old_floor=True)), "reason=walnut_not_applied"))
same = PieFake([0.0], old_floor=True)
same.p01_floor = ["/Game/Floor/MI_Slats"]
check("+ the 6 Oct false positive is gone: P02 == P01's slab material (both DarkWet then) is NOT walnut",
      raises(lambda: arm_only(same), "reason=walnut_not_applied")
      and fb.walnut_state(["/X/DarkWet"] * 4, ["/X/DarkWet"], True)["applied"] is False)
wal = PieFake([0.0])
check("- control: with the walnut applied, require arms and no E_BEFORE_WALNUT is logged",
      not raises(lambda: arm_only(wal), "FAILED") and not wal.logs("E_BEFORE_WALNUT"))
check("+ CAPTURE refuses a variant list that does not start with base",
      raises(lambda: arm_only(PieFake([0.0]), params={"variants": ("A", "base")}), "reason=bad_variants"))
check("- control: a clean PIE fake arms", not raises(lambda: arm_only(PieFake([0.0])), "FAILED"))

# ======================= the REAL PIE adapter on a strict fake `unreal` =======================
# Only names the UE 5.8 headers declare as UFUNCTION / UPROPERTY exist on these classes (cited in p02_fog_bench.py);
# anything else raises AttributeError exactly as the live binding did on 6 Oct.
import types  # noqa: E402


def strict_unreal(drop=(), view_target=True):
    U = types.SimpleNamespace()
    logs = {"log": [], "warn": [], "err": []}

    class Vector:
        def __init__(self, x=0.0, y=0.0, z=0.0): self.x, self.y, self.z = float(x), float(y), float(z)

    class Rotator:
        def __init__(self, roll=0.0, pitch=0.0, yaw=0.0): self.roll, self.pitch, self.yaw = roll, pitch, yaw

    class Obj:
        def __init__(self, path, **props): self._path, self._props = path, dict(props)
        def get_path_name(self): return self._path
        def get_name(self): return self._path.rsplit(".", 1)[-1]
        def get_editor_property(self, n): return self._props[n]
        def set_editor_property(self, n, v, notify_mode=None): self._props[n] = v

    class Actor(Obj):
        def __init__(self, path, label, comps=(), loc=(0, 0, 0), **props):
            super().__init__(path, **props)
            self._label, self._comps, self._loc, self._rot = label, list(comps), Vector(*loc), Rotator()
        def get_actor_label(self): return self._label
        def actor_has_tag(self, t): return False
        def get_component_by_class(self, cls): return next((c for c in self._comps if isinstance(c, cls)), None)
        def get_components_by_class(self, cls): return [c for c in self._comps if isinstance(c, cls)]
        def get_actor_location(self): return self._loc
        def get_actor_rotation(self): return self._rot
        def set_actor_rotation(self, r, teleport): self._rot = r; return True
        def get_actor_bounds(self, only_colliding): return self._props["_bounds"]
        def set_actor_location_and_rotation(self, *a): return True
        def set_actor_scale3d(self, v): pass
        def set_actor_hidden_in_game(self, h): pass

    class ActorComponent(Obj):
        pass

    class SceneComponent(ActorComponent):
        def get_world_location(self): return Vector(*self._props.get("_loc", (0, 0, 0)))
        def get_world_rotation(self): return Rotator(*self._props.get("_rot", (0, 0, 0)))
        def is_visible(self): return True
        def set_visibility(self, v, p): pass

    class PrimitiveComponent(SceneComponent):
        def get_material(self, i): return None
        def get_num_materials(self): return 0
        def get_material_index(self, n): return -1
        def set_material(self, i, m): pass

    class MeshComponent(PrimitiveComponent):
        def get_materials(self): return []

    class StaticMeshComponent(MeshComponent): pass
    class CameraComponent(SceneComponent): pass
    class CineCameraComponent(CameraComponent): pass

    class LightComponent(SceneComponent):
        def set_volumetric_scattering_intensity(self, v): self._props["volumetric_scattering_intensity"] = float(v)

    class LocalLightComponent(LightComponent): pass
    class RectLightComponent(LocalLightComponent): pass

    class ExponentialHeightFogComponent(SceneComponent):
        def set_fog_density(self, v): pass
        def set_second_fog_density(self, v): pass
        def set_volumetric_fog(self, v): pass

    class LocalFogVolumeComponent(SceneComponent):
        def set_radial_fog_extinction(self, v): pass
        def set_height_fog_extinction(self, v): pass
        def set_height_fog_falloff(self, v): pass
        def set_height_fog_offset(self, v): pass
        def set_fog_phase_g(self, v): pass

    class PostProcessVolume(Actor): pass          # AVolume::EncompassesPoint has no UFUNCTION (Volume.h:52)
    class StaticMeshActor(Actor): pass
    class ExponentialHeightFog(Actor): pass
    class CineCameraActor(Actor): pass
    class InfinityStageShowRoot(Actor): pass

    class Controller(Actor):                       # Controller.h:252-253 UFUNCTION GetViewTarget
        def get_view_target(self): return self._props["_vt"]

    class PlayerController(Controller): pass

    class PlayerCameraManager(Actor):              # PlayerCameraManager.h:559: GetViewTarget is NOT a UFUNCTION
        def get_camera_location(self): return Vector(100.0, 0.0, 180.0)
        def get_camera_rotation(self): return Rotator()
        def get_fov_angle(self): return 37.5

    class Material(Obj): pass
    class MaterialInstance(Obj): pass

    class MaterialInstanceConstant(MaterialInstance):
        def get_scalar_parameter_value(self, n): return self._props["_scalars"][n]

    class MaterialInstanceDynamic(MaterialInstance):
        def get_scalar_parameter_value(self, n): return self._props["_scalars"][n]
        def set_scalar_parameter_value(self, n, v): self._props["_scalars"][n] = v

    class PPS(Obj): pass

    fields = {f: 0.0 for f in fb.PP_EXPOSURE + fb.PP_READ_ONLY + tuple(fb.E_PP_OVERRIDE.values()) + tuple(fb.E_PP_OVERRIDE)}
    world = Obj("/Game/Maps/UEDPIE_0_L.L")
    cam_comp = CineCameraComponent("/PIE/CineCam.CameraComponent", post_process_settings=PPS("pps", **fields),
                                   post_process_blend_weight=1.0)
    cine = CineCameraActor("/PIE/CineCam", "P02 Camera", [cam_comp])
    ppv_in = PostProcessVolume("/PIE/PPV_In", "PPV In", enabled=True, unbound=False, priority=1.0, blend_weight=1.0,
                               settings=PPS("s1", **fields), _bounds=(Vector(100, 0, 0), Vector(500, 500, 500)))
    ppv_out = PostProcessVolume("/PIE/PPV_Out", "PPV Out", enabled=True, unbound=False, priority=2.0, blend_weight=1.0,
                                settings=PPS("s2", **fields), _bounds=(Vector(90000, 0, 0), Vector(500, 500, 500)))
    lamp_c = RectLightComponent("/PIE/Lamp.Light", volumetric_scattering_intensity=0.8, intensity=10.0)
    lamp = Actor("/PIE/Lamp", "P02 SCORE B08 LOOK TOP_L", [lamp_c], loc=(400, 0, 1100))
    tubes = [RectLightComponent("/PIE/Structure02.StructureUnderpassTubeLight_%d" % i, volumetric_scattering_intensity=1.0,
                                intensity=1500.0, _loc=(300 * i, 900, 420)) for i in range(3)]
    structure = Actor("/PIE/Structure02", "Infinity Stage - Structure 02", tubes)
    pc = PlayerController("/PIE/PC", "PC", _vt=cine if view_target else None)
    pcm = PlayerCameraManager("/PIE/PCM", "PCM")
    actors = [cine, ppv_in, ppv_out, lamp, structure, pc, pcm]
    mic = MaterialInstanceConstant(fb.WALNUT_MAT, _scalars={"Roughness_Low": 0.3, "Roughness_High": 0.8})
    plain_mi = MaterialInstance("/Game/X/MI_Plain")
    objects = {o.get_path_name(): o for o in actors + [lamp_c, cam_comp, mic, plain_mi] + tubes}

    class GameplayStatics:
        @staticmethod
        def get_all_actors_of_class(w, cls): return [a for a in actors if isinstance(a, cls)]
        @staticmethod
        def get_player_controller(w, i): return pc
        @staticmethod
        def get_player_camera_manager(w, i): return pcm

    class SystemLibrary:
        @staticmethod
        def execute_console_command(w, c): pass
        @staticmethod
        def get_component_bounds(c): return Vector(), Vector(), 0.0
        @staticmethod
        def get_console_variable_float_value(n): return 0.0

    class MaterialEditingLibrary:
        @staticmethod
        def get_scalar_parameter_names(m): return list(m._props.get("_scalars", {"Roughness": 0.5}))
        @staticmethod
        def get_material_default_scalar_parameter_value(m, n): return 0.5

    class MaterialLibrary:
        @staticmethod
        def create_dynamic_material_instance(w, parent): return MaterialInstanceDynamic("/Transient/MID", _scalars={})

    class Editor:
        def get_game_world(self): return world

    class EditorLoadingAndSavingUtils:
        @staticmethod
        def get_dirty_map_packages(): return []
        @staticmethod
        def get_dirty_content_packages(): return []

    for name, val in dict(locals()).items():
        if isinstance(val, type):
            setattr(U, name, val)
    U.Name = str
    U.PropertyAccessChangeNotifyMode = types.SimpleNamespace(NEVER="NEVER")
    U.UnrealEditorSubsystem = object
    U.get_editor_subsystem = lambda cls: Editor()
    U.find_object = lambda outer, path: objects.get(path)
    U.load_object = lambda outer, path: objects.get(path)
    U.log = logs["log"].append
    U.log_warning = logs["warn"].append
    U.log_error = logs["err"].append
    U._logs = logs
    for dotted in drop:                              # remove a binding to prove the preflight sees it
        cls, attr = dotted.split(".")
        delattr(getattr(U, cls), attr)
    return U


SU = strict_unreal()
SA = fb.make_pie_adapter(SU)
pcm_live = SU.GameplayStatics.get_player_camera_manager(None, 0)
try:
    pcm_live.get_view_target()
    old_raised = False
except AttributeError as exc:
    old_raised = "get_view_target" in str(exc)
check("- control: the 6 Oct call (PlayerCameraManager.get_view_target) raises AttributeError on the strict fake, as "
      "it did live (PlayerCameraManager.h:559 is not a UFUNCTION)", old_raised)
src = SA.pp_sources([100.0, 0.0, 180.0])
cam_rows = [r for r in src if r["kind"] == "camera"]
check("+ fixed pp_sources: the camera row comes from PlayerController.get_view_target -> the CineCamera's "
      "CameraComponent (subclass found by get_component_by_class), weight read, affects",
      len(cam_rows) == 1 and cam_rows[0]["id"] == "/PIE/CineCam.CameraComponent" and cam_rows[0]["label"] == "P02 Camera"
      and cam_rows[0]["affects"] and set(cam_rows[0]["fields"]) >= set(fb.PP_EXPOSURE))
ppv = {r["id"]: r for r in src if r["kind"] == "ppv"}
check("+ pp_sources: with no encompasses_point binding the bounds box decides: PPV_In affects, PPV_Out does not",
      ppv["/PIE/PPV_In"]["affects"] and not ppv["/PIE/PPV_Out"]["affects"])
check("- control: a controller with no view target refuses (no_view_target), never a silent camera-less plan",
      raises(lambda: fb.make_pie_adapter(strict_unreal(view_target=False)).pp_sources([0.0, 0.0, 0.0]),
             "reason=no_view_target"))
check("+ api_missing: the strict fake exposes every binding in PIE_API (nothing missing)", SA.api_missing() == [])
gone = fb.make_pie_adapter(strict_unreal(drop=("Controller.get_view_target", "LocalFogVolumeComponent.set_fog_phase_g")))
check("- control: dropping Controller.get_view_target and LocalFogVolumeComponent.set_fog_phase_g is reported",
      gone.api_missing() == ["Controller.get_view_target", "LocalFogVolumeComponent.set_fog_phase_g"])
f_api = PieFake([0.0])
f_api.missing_api = ["Controller.get_view_target"]
out_api = tmp / "api_out"
check("+ arm refuses on a missing binding (reason=api_missing) before any write, run dir, or strobe change",
      raises(lambda: arm_only(f_api, out=out_api), "reason=api_missing|Controller.get_view_target")
      and not out_api.exists() and not [e for e in f_api.events if isinstance(e, tuple)])
f_pre = PieFake([0.0])


def _boom(loc):
    raise AttributeError("'PlayerCameraManager' object has no attribute 'get_view_target'")


f_pre.pp_sources = _boom
out_pre = tmp / "pre_out"
check("+ read preflight: the 6 Oct failure mode (a read raising AttributeError) now refuses at arm with nothing "
      "changed (no run dir, no write, strobes untouched)",
      raises(lambda: arm_only(f_pre, out=out_pre), "reason=arm_error|AttributeError") and not out_pre.exists()
      and not [e for e in f_pre.events if isinstance(e, tuple)] and f_pre.strobes["/PIE/P02_Strobe"] is True)
wal2 = PieFake([0.0])
check("- control: a clean fake passes the preflight and logs PREFLIGHT with the camera PP row",
      not raises(lambda: arm_only(wal2), "FAILED") and any('"pp_camera": 1' in m for m in wal2.logs("P02_FOG_BENCH_PREFLIGHT|")))

# tubes through the real adapter
rows_l = SA.lights()
comp_rows = [r for r in rows_l if r["component"]]
check("+ lights(): the lamp actor (1 light) is one actor row; the Structure's 3 tube rect lights are 3 component rows "
      "(before 6 Oct the multi-light actor was skipped)",
      [r["id"] for r in rows_l if not r["component"]] == ["/PIE/Lamp"] and len(comp_rows) == 3
      and all(r["label"].startswith("Infinity Stage - Structure 02/StructureUnderpassTubeLight_") for r in comp_rows))
tid = comp_rows[0]["id"]
SA.write("light", tid, "volumetric_scattering_intensity", 0.0)
check("+ a tube component's scattering is written and read back through the component",
      SA.read("light", tid, "volumetric_scattering_intensity") == 0.0
      and SA.read("light", "/PIE/Lamp", "volumetric_scattering_intensity") == 0.8)
check("- control: re-aiming a component light is refused (C only aims lamp actors)",
      raises(lambda: SA.write("light", tid, "rotation", {"roll": 0, "pitch": 0, "yaw": 0}), "LIGHT_COMPONENT_ROTATION"))
check("+ scalar_params: the walnut MIC's Roughness_Low / Roughness_High via MIC.get_scalar_parameter_value",
      SA.scalar_params(fb.WALNUT_MAT) == {"Roughness_Low": 0.3, "Roughness_High": 0.8})
check("- control: a material class with no scalar getter UFUNCTION is refused (logged, {}), not guessed",
      SA.scalar_params("/Game/X/MI_Plain") == {} and any("SCALARS_UNREAD" in m for m in SU._logs["warn"]))

# tubes in the plans (fake world)
tube_ids = {l["id"] for l in LIGHTS if l["component"]}
near_tubes = {l["id"] for l in LIGHTS if l["component"] and fb.dist3(l["location"], POSE8["loc"]) <= P["a_radius_cm"]}
check("+ A zeroes the scattering of every tube light within the radius (component rows)",
      near_tubes and near_tubes <= zero_ids and pa["info"]["zeroed_components"] == len(near_tubes))
check("+ C never re-aims a tube light, even one labelled like a LOW_SIDE score lamp",
      not (tube_ids & c_ids) and not fb.plan_c([dict(l, label="P02 SCORE B08 LOOK LOW_SIDE_X") for l in LIGHTS
                                                 if l["component"]], POSE8, 8, P)["ops"])
check("- control: the same relabelled rows WITHOUT the component flag would be re-aimed",
      fb.plan_c([dict(l, label="P02 SCORE B08 LOOK LOW_SIDE_X", component=False) for l in LIGHTS if l["component"]],
                POSE8, 8, P)["ops"])

# settle trend: last night's measured base_ref window
LAST = [[0.234, 28.563], [0.734, 29.489], [1.797, 29.727], [2.859, 30.664], [3.922, 31.621], [4.969, 32.484]]
check("+ settle trend: the 6 Oct bay08 base_ref (28.6 -> 32.5 in a line, drift %.2f) now WAITS" % fb.window_drift(LAST),
      fb.robust_settle(LAST, 4.97, Pg) == "wait" and fb.window_drift(LAST) > 3.0)
check("- control: the half-median test alone (settle_trend False) called it stable, as it did live",
      fb.robust_settle(LAST, 4.97, dict(Pg, settle_trend=False)) == "stable")
check("+ settle trend keeps the stationary flicker stable (dips do not tilt a Theil-Sen slope)",
      abs(fb.window_drift(flick[-6:])) < 1.0 and fb.robust_settle(flick, 6.0, Pg) == "stable")

# RESTORE scope + stale PREPARE
sr = tmp / "sessions"
for name in ("P02FOGPREP-20261006-064231", "P02FOGPREP-20261006-200000"):
    (sr / "_prepare" / name).mkdir(parents=True)
    (sr / "_prepare" / name / fb.PREPARE_RECORD_NAME).write_text(
        json.dumps(dict(prep_disk, run=name)), encoding="utf-8")
for run_name, prep_run in (("P02FOG-20261006-064243", "P02FOGPREP-20261006-064231"),
                           ("P02FOG-20261006-200100", "P02FOGPREP-20261006-200000")):
    (sr / run_name).mkdir()
    (sr / run_name / fb.ORIGINALS_NAME).write_text(json.dumps({"prepare_run": prep_run}), encoding="utf-8")
got_sr = [pp.parent.name for pp in fb.session_records(sr, sr / "_prepare")]
check("+ RESTORE default records: only captures armed on the NEWEST PREPARE (tonight), never last night's",
      got_sr == ["P02FOG-20261006-200100"])
check("- control: the old glob would have restored last night's record too (written LAST, so it would win)",
      len(sorted(sr.glob("P02FOG-*/" + fb.ORIGINALS_NAME))) == 2)
old_prep = sr / "_prepare" / "P02FOGPREP-20261006-064231" / fb.PREPARE_RECORD_NAME
new_prep = sr / "_prepare" / "P02FOGPREP-20261006-200000" / fb.PREPARE_RECORD_NAME


def _arm_prep(prep, out):
    return fb.arm(PieFake([0.0]), prep, TEST_P, out_root=out, prepare_root=sr / "_prepare", owner_path=tmp / "o.json",
                  walnut_record=tmp / "w.json", register=lambda fn: "H", unregister=lambda h: None, store=Store(),
                  clock=lambda: 0.0)


check("+ CAPTURE refuses an explicit PREPARE record that is not the newest (stale_prepare; args pinned last night's)",
      raises(lambda: _arm_prep(old_prep, tmp / "stale_a"), "reason=stale_prepare"))
check("- control: the newest PREPARE record arms", not raises(lambda: _arm_prep(new_prep, tmp / "stale_b"), "FAILED"))
args_disk = json.loads((HERE / "p02_fog_bench_args.json").read_text(encoding="utf-8"))
check("+ p02_fog_bench_args.json no longer pins a PREPARE record (newest is found)", args_disk.get("prepare_record") is None)

# ======================= source scans =======================
SAVE = re.compile(r"save_(current_level|packages|dirty|map|asset|loaded_asset|directory|level)|EditorAssetLibrary\.save|"
                  r"save_dirty_packages|\.save\(|SavePackage|editor_save|save_map", re.I)
OURS = sorted(HERE.glob("p02_fog_bench*.py"))
bench_src = (HERE / "p02_fog_bench.py").read_text(encoding="utf-8")
sheet_src = (HERE / "p02_fog_bench_contact_sheet.py").read_text(encoding="utf-8")
unreal_src = "".join(p.read_text(encoding="utf-8") for p in OURS if p.name != "p02_fog_bench_contact_sheet.py")
check("+ no save call anywhere in p02_fog_bench.py or its run scripts (%d files)" % (len(OURS) - 1),
      len(OURS) >= 5 and not SAVE.search(unreal_src))
check("- control: the scanner flags an injected save", bool(SAVE.search(unreal_src + "\nunreal.EditorLoadingAndSavingUtils.save_map(w, p)\n")))
check("+ the contact sheet only saves its own PNG (sheet.save) and never imports unreal",
      [m.group(0) for m in SAVE.finditer(sheet_src)] == [".save("] and "import unreal" not in sheet_src)
SPAWN = re.compile(r"spawn_actor|begin_deferred|finish_spawning|SpawnActor|\.spawn\w*\(|destroy\w*\(|EditorActorSubsystem|"
                   r"EditorLevelLibrary", re.I)
pie_region = bench_src.split("# ---- PIE ADAPTER BEGIN", 1)[1].split("# ---- PIE ADAPTER END", 1)[0]
engine_free = "".join(inspect.getsource(x) for x in (fb.FogBench, fb.FogMachine, fb.restore_from_record, fb.restore_all, fb.arm))
check("+ PIE adapter region and the engine-free bench / machine / restore / arm contain no spawn / destroy / editor-actor API",
      len(pie_region) > 5000 and not SPAWN.search(pie_region.split("\n", 1)[1]) and not SPAWN.search(engine_free))
check("- control: the spawn scanner flags an injected PIE spawn",
      bool(SPAWN.search(pie_region + "\n        a = actor_sub.spawn_actor_from_class(cls, loc)\n")))
check("+ no Unreal import at module level (UE objects only in closures)",
      not re.search(r"^import unreal", bench_src, re.M) and not re.search(r"^from unreal", bench_src, re.M))
check("+ C never touches the Show asset: no Show / load_asset / cue access in the PIE write paths or the plans",
      "load_asset" not in bench_src and "ShowAsset" not in pie_region and "passage_settings" not in bench_src)

# ======================= contact sheet =======================
import p02_fog_bench_contact_sheet as cs  # noqa: E402
sheet = cs.build_sheet(r1["run_dir"], thumb_w=160)
check("+ contact sheet: 2 rows x 7 tiles, each labelled with its variant letter, a pick per tile, no missing",
      len(sheet["tiles"]) == 14 and [t["letter"] for t in sheet["tiles"][:7]] == list(fb.ORDER)
      and all(t["pick"] for t in sheet["tiles"]) and not sheet["missing"] and pathlib.Path(sheet["sheet"]).is_file())
pk = cs.pick_still
d3 = tmp / "pick"
for i, g in enumerate((90, 60, 88)):
    write_png(d3 / ("s%d.png" % i), 8, 6, g)
idx, lumas, med = pk([d3 / ("s%d.png" % i) for i in range(3)])
check("+ pick: the still nearest the median luma (88 of 90/60/88), not the flicker dip", idx == 2 and abs(med - 88.0) < 1e-6)
sheetW = cs.build_sheet(rW["run_dir"], thumb_w=160)
check("+ tile notes: E ran before the walnut is written on E and ALL tiles of the old-floor run",
      all("E ran BEFORE the walnut floor" in t["notes"] for t in sheetW["tiles"] if t["variant"] in ("E", "ALL")))
check("- control: the walnut run's tiles carry no such note",
      not any("E ran BEFORE the walnut floor" in t["notes"] for t in sheet["tiles"]))
gone = pathlib.Path(r1["run_dir"]) / "bay15" / "C_0.png"
for pth in pathlib.Path(r1["run_dir"]).glob("bay15/C_*.png"):
    pth.unlink()
sheet2 = cs.build_sheet(r1["run_dir"], thumb_w=160)
check("- control: deleting a shot's stills makes that tile MISSING", sheet2["missing"] == ["bay15/C"])

failed = [n for n, ok in RESULTS if not ok]
print("\nP02_FOG_BENCH_HARNESS %d/%d %s" % (len(RESULTS) - len(failed), len(RESULTS), "OK" if not failed else "FAILED"))
sys.exit(1 if failed else 0)
