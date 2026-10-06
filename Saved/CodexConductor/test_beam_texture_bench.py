"""Offline harness for beam_texture_bench.py + beam_texture_bench_contact_sheet.py (no Unreal). Every property has a
+ case and a - control that must FAIL, so each check is shown able to fail. Fake-adapter pattern of
test_p02_fog_bench.py. The fake PIE world renders synthetic stills of the beam (its core band, striped when the
occluder bars are shown with shadows on, mottled when the noise box is shown) so the texture metric and the contact
sheet are tested end to end. Run: python Saved/CodexConductor/test_beam_texture_bench.py"""
import copy
import inspect
import json
import math
import pathlib
import re
import struct
import sys
import tempfile
import types
import zlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import beam_texture_bench as bt  # noqa: E402
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


def write_png_rows(path, rows):
    h, w = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(max(0, min(255, int(round(v)))) for v in row for _ in range(3)) for row in rows)

    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body) & 0xFFFFFFFF)
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                                   + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


tmp = pathlib.Path(tempfile.mkdtemp(prefix="beamtex_"))
MAP = "L_InfinityStage_V1VerticalSlice"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
SEG = (1_000_000, 1_000_000 + 120 * bt.ps.TICKS_PER_SECOND)
PITCH = 600.0
ROUTE_LEN = 48 * PITCH
LAMP = (19 * PITCH - 150.0, -1250.0, 140.0)           # bay 20 station x = 19 * 600; BEAM_R at (-150, -1250, 140)
LAMP_ROT = {"roll": 0.0, "pitch": -5.0, "yaw": 76.0}   # the record's quaternion -> forward (0.241, 0.967, -0.087)
BEAM_ID = "/PIE/P01_B20_BEAM_R.LightComponent0"
BEAM_ACTOR = "/PIE/P01_B20_BEAM_R"
FOG_ID = "/PIE/HeightFog.Component"
RES = (320, 180)
TEST_P = {"file_min_bytes": 50, "settle_min_seconds": 3.0, "resolution": RES, "time_seconds": 1.0,
          "analysis_width": 160}


class Store:
    pass


def fake_log_text(marker, extra=()):
    return "\n".join(["[x] LogInit: boot", "[x] LogPython: " + marker] + list(extra)) + "\n"


class World:
    def __init__(self):
        self.events, self.logs_, self.errors = [], [], []
        self.state = {}
        self.census_ = {"maps": [MAP], "content": ["M_ZZ_BeamTex_Black", "M_ZZ_BeamTex_Breakup",
                                                   "M_ZZ_BeamTex_NoiseVolume"]}
        self.pool = {}
        self.strobes = {"/PIE/Opening_Strobe": True}
        self.sweeps = {}
        self.record_path = None
        self.violations = []
        self.missing_api = []
        self.set_("light", BEAM_ID, "cast_shadows", False)
        self.set_("light", BEAM_ID, "cast_volumetric_shadow", False)
        self.set_("fog", FOG_ID, "fog_density", 0.02)
        self.set_("fog", FOG_ID, "second_fog_density", 0.004)
        self.set_("fog", FOG_ID, "scattering_distribution", 0.2)
        for n, v in (("r.VolumetricFog.GridPixelSize", 8.0), ("r.VolumetricFog.GridSizeZ", 64.0),
                     ("r.VolumetricFog.HistoryWeight", 0.9)):
            self.set_("cvar", n, "value", v)
        self.volumetric = True
        self.beam_label = "P01 SCORE B20 P01_WARM_THEATRICAL BEAM_R"
        self.extra_beams = []

    def set_(self, kind, oid, field, value):
        if isinstance(value, float):
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

    def read(self, kind, oid, field):
        return copy.deepcopy(self.state[(kind, oid, field)])

    def write(self, kind, oid, field, value):
        self.events.append(("write", bt.key(kind, oid, field)))
        if self.record_path is not None:
            disk = json.loads(pathlib.Path(self.record_path).read_text(encoding="utf-8"))
            if bt.key(kind, oid, field) not in disk["originals"]:
                self.violations.append(bt.key(kind, oid, field))
        self.set_(kind, oid, field, value)

    def show_strobes(self): return [{"id": k, "label": k, "enabled": v} for k, v in sorted(self.strobes.items())]
    def show_strobe_enabled(self, sid): return self.strobes[sid]

    def set_show_strobe(self, sid, en):
        self.events.append(("write", "strobe|" + sid))
        self.strobes[sid] = bool(en)

    def sweep_lights(self): return []
    def sweep_enabled(self, sid): return self.sweeps[sid]
    def set_sweep(self, sid, en): self.sweeps[sid] = bool(en)

    def pool_labels(self): return sorted(self.pool)
    def pool_state(self, label): return {"on": self.pool[label]["on"]}

    def show_pool(self, spec):
        self.events.append(("show", spec["label"]))
        self.pool[spec["label"]].update(on=True, spec=spec)

    def hide_pool(self, label):
        self.events.append(("hide", label))
        self.pool[label].update(on=False)


class EditorFake(World):
    def __init__(self, pie_running=False, exist=(), bad_material=None):
        super().__init__()
        self.pie_running = pie_running
        self.census_ = {"maps": [], "content": []}
        self.exist = set(exist)
        self.bad_material = bad_material

    def world_kind(self): return "pie_running" if self.pie_running else "editor"
    def world_name(self): return "/Game/InfinityStage/Dev/Maps/%s.%s" % (MAP, MAP)
    def bench_actor_labels(self, prefix): return sorted(l for l in self.pool if l.startswith(prefix))
    def asset_exists(self, path): return path in self.exist
    def cvar_int(self, name): return 1

    def build_materials(self, p):
        out = {}
        for m in bt.BENCH_MATERIALS:
            self.events.append(("create_asset", m))
            self.census_["content"].append(m.rsplit("/", 1)[-1])
            out[m] = {"ok": m != self.bad_material, "domain": "x"}
        return out

    def spawn_hidden(self, spec):
        self.events.append(("spawn", spec["label"]))
        self.pool[spec["label"]] = {"on": False, "kind": spec["kind"]}
        if MAP not in self.census_["maps"]:
            self.census_["maps"].append(MAP)
        return "/Game/Maps/%s:PersistentLevel.%s" % (MAP, spec["label"])


class PieFake(World):
    """PIE + transport + camera on a straight route (+X, y 0, z 90, yaw 0, fov 90). The bay-20 BEAM_R strikes at
    650 cm ahead (ramp 150) and holds. Probes: grey PNGs of a picture luma that eases (tau) to a target. Stills:
    the beam's core band drawn into a 320x180 frame, striped by the occluder bars when shadows are on, mottled by
    the noise box."""

    def __init__(self, clock, prepared=True, kind="game", tau=0.5, occlusion="clear", residual_after=None,
                 reapply_shadows=False, cvars=None, scrub_result="<InfinityTransportResult.SUCCEEDED: 0>",
                 control_hit=True):
        super().__init__()
        self.clock, self.kind, self.tau = clock, kind, tau
        if prepared:
            self.pool = {lab: {"on": False} for lab in bt.pool_labels_needed(dict(bt.DEFAULTS))}
        self.occlusion, self.residual_after, self.reapply_shadows = occlusion, residual_after, reapply_shadows
        self.scrub_result, self.control_hit = scrub_result, control_hit
        for n, v in (cvars or {}).items():
            self.set_("cvar", n, "value", v)
        self.frame, self.playing = SEG[0] + 5000, True
        self.lum, self.residual = None, 0.0
        self.scrubs, self.commands = [], []

    def world_kind(self): return self.kind
    def world_name(self): return "/Game/InfinityStage/Dev/Maps/UEDPIE_0_%s.%s" % (MAP, MAP)

    def passage_segment(self, label):
        if label != "Passage 1":
            raise bt.BenchRefused("no_segment", label)
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
        return {"loc": [self.cam_x(), 0.0, 90.0], "rot": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0}, "fov_deg": 90.0,
                "fov_read": 90.0, "aspect": aspect}

    def intensity(self):
        ahead = LAMP[0] - self.cam_x()
        return 3500.0 * min(1.0, max(0.0, (650.0 - ahead) / 150.0))

    def beam_rows(self, regex):
        rows = []
        for i, label in enumerate([self.beam_label] + self.extra_beams):
            if re.search(regex, label):
                rows.append({"id": BEAM_ID if i == 0 else BEAM_ID + str(i), "actor_id": BEAM_ACTOR, "label": label,
                             "location": list(LAMP), "rotation": dict(LAMP_ROT), "outer_cone_deg": 7.0,
                             "attenuation_cm": 2600.0, "intensity": self.intensity(),
                             "cast_shadows": self.read("light", BEAM_ID, "cast_shadows"),
                             "cast_volumetric_shadow": self.read("light", BEAM_ID, "cast_volumetric_shadow"),
                             "volumetric_scattering_intensity": 6.0, "spot": True, "visible": True})
        return rows

    def fogs(self):
        return [{"id": FOG_ID, "label": "HeightFog", "fog_density": self.read("fog", FOG_ID, "fog_density"),
                 "second_fog_density": self.read("fog", FOG_ID, "second_fog_density"),
                 "volumetric_fog": self.volumetric,
                 "scattering_distribution": self.read("fog", FOG_ID, "scattering_distribution")}]

    def cvar(self, name):
        if name == "r.VolumetricFog":
            return 1.0
        return self.read("cvar", name, "value") if ("cvar", name, "value") in self.state else None

    def trace(self, start, end, ignore=None):
        if abs(start[0] - self.cam_x()) < 1e-6 and start[1] == 0.0:          # the camera's control trace
            return {"dist": 90.0, "label": "Passage 01 - Opening Floor", "component": "SMC"} \
                if (self.control_hit and end[2] < start[2] - 50.0) else None
        if self.occlusion == "clear":
            return None
        if self.occlusion == "blocked":
            return {"dist": 400.0, "label": "Passage 01", "component": "Wing_020_L"}
        # partial: rays leaning up (end z above the axis end) are cut by the pierced wing's lower edge
        return {"dist": 420.0, "label": "Passage 01", "component": "Wing_020_L"} if end[2] > 30.0 else None

    def meshes_near(self, center, radius, max_rows, max_extent):
        return [{"label": "Passage 01", "component": "P01_Wing_020_L", "center": [LAMP[0] + 250.0, -1150.0, 300.0],
                 "extent": [40.0, 160.0, 300.0]},
                {"label": "Infinity Stage - Structure 01", "component": "Gridiron", "center": [LAMP[0], -900.0,
                                                                                               1200.0],
                 "extent": [300.0, 300.0, 40.0]}]

    def exposure_info(self):
        return [{"label": "PPV Show", "auto_exposure_min_brightness": -3.0, "auto_exposure_max_brightness": -3.0}]

    # ---- picture
    def target(self):
        fog = self.read("fog", FOG_ID, "fog_density") / 0.02
        s = 40.0 + 6.0 * fog + self.intensity() / 3500.0 * 8.0
        s += 3.0 * sum(1 for p in self.pool.values() if p["on"])
        return s

    def displayed(self):
        return self.lum + self.residual

    def advance(self, dt):
        if self.lum is None:
            self.lum = self.target()
        self.lum += (self.target() - self.lum) * (1.0 - math.exp(-dt / self.tau))
        if self.residual_after and any(p["on"] for k, p in self.pool.items() if "NOISEBOX" in k):
            self.residual = 25.0
        if self.reapply_shadows and self.record_path is not None:
            self.state[("light", BEAM_ID, "cast_shadows")] = False          # a Show re-materialise

    def render(self, w, h):
        pose = self.camera_pose(w / float(h), 90.0)
        beam = self.beam_rows(bt.beam_regex(dict(bt.DEFAULTS)))[0]
        spec = bt.mask_spec(pose, beam, dict(bt.DEFAULTS, mask_core=1.0), w, h)
        mask = bt.mask_grid(spec, w, h)
        fog = self.read("fog", FOG_ID, "fog_density") / 0.02
        sd = self.read("fog", FOG_ID, "scattering_distribution")
        level = 110.0 * (self.intensity() / 3500.0) * (0.7 + 0.3 * fog) * (0.8 if sd > 0.5 else 1.0)
        bars = self.read("light", BEAM_ID, "cast_volumetric_shadow") and any(
            p["on"] for k, p in self.pool.items() if "_BAR_" in k)
        noise = any(p["on"] for k, p in self.pool.items() if "NOISEBOX" in k)
        rows = []
        for j in range(h):
            row = []
            for i in range(w):
                v = 25.0 + 10.0 * j / float(h)
                if mask[j][i]:
                    b = level * (0.85 + 0.15 * i / float(w))
                    if bars:
                        b *= 0.35 if (j // 3) % 2 else 1.0
                    if noise:
                        b *= 0.55 + 0.45 * ((math.sin((i // 4) * 12.9898 + (j // 4) * 78.233) * 43758.5453) % 1.0)
                    v += b
                row.append(v)
            rows.append(row)
        return rows

    def console(self, cmd):
        if self.kind != "game":
            raise bt.BenchRefused("pie_ended", "console")
        self.commands.append(cmd)
        m = re.search(r'filename="([^"]+)"', cmd)
        if not m:
            return
        path = m.group(1)
        if "_probes" in path:
            g = self.displayed()
            write_png_rows(path, [[g] * 8 for _ in range(6)])
        else:
            write_png_rows(path, self.render(*RES))


def prepared_record(name="prep", marker_in_log=True):
    ed = EditorFake()
    d = tmp / name / "BEAMTEXPREP-x"
    d.mkdir(parents=True)
    rec = bt.PrepareBench(ed, d / bt.PREPARE_RECORD_NAME, {}, "BEAMTEXPREP-" + name).run()
    return ed, d / bt.PREPARE_RECORD_NAME, rec


ED, PREP, PREP_REC = prepared_record()
LOG = tmp / "PussStage.log"
LOG.write_text(fake_log_text(PREP_REC["marker"]), encoding="utf-8")


def run(params=None, dt=0.05, max_t=4000.0, dry=False, store=None, log_path=LOG, **kw):
    clock = [0.0]
    f = PieFake(clock, **kw)
    store = store or Store()
    reg = {}
    out_root = tmp / ("run_%d" % len(RESULTS))
    p = dict(TEST_P)
    p.update(params or {})
    f.advance(0.0)
    snap = f.snapshot()
    r = bt.arm(f, PREP, p, dry=dry, out_root=out_root, prepare_root=tmp / "nowhere", owner_path=tmp / "owner.json",
               log_path=log_path, register=lambda fn: reg.setdefault("fn", fn) and "H",
               unregister=lambda h: reg.setdefault("unreg", h), store=store, clock=lambda: clock[0])
    f.record_path = pathlib.Path(r["run_dir"]) / bt.ORIGINALS_NAME
    mid = {}
    while not r.get("finished") and clock[0] < max_t:
        clock[0] += dt
        f.advance(dt)
        reg["fn"](dt)
        if not mid and any(isinstance(e, tuple) and e[0] == "write" and e[1].startswith("light|") for e in f.events):
            mid = {"strobes": dict(f.strobes)}
    return r, f, snap, mid


def manifest(r):
    return json.loads((pathlib.Path(r["run_dir"]) / bt.MANIFEST_NAME).read_text(encoding="utf-8"))


# ======================= PREPARE (editor world) =======================
iw = next(i for i, e in enumerate(ED.events) if e == "record_written")
ic = next(i for i, e in enumerate(ED.events) if isinstance(e, tuple) and e[0] in ("create_asset", "spawn"))
check("+ PREPARE: record (labels, planned materials, census) written before the first asset or spawn", iw < ic)
prep_disk = json.loads(PREP.read_text(encoding="utf-8"))
want_pool = bt.pool_labels_needed(dict(bt.DEFAULTS))
check("+ PREPARE: %d hidden ZZ_BEAMTEX_ actors (4 bars, breakup, noise box, 6 clumps), 3 materials, status spawned, "
      "markers PREPARE_OK + NEEDS_DONT_SAVE_RESTART" % len(want_pool),
      prep_disk["status"] == "spawned" and sorted(ED.pool) == sorted(want_pool) and len(want_pool) == 12
      and not any(v["on"] for v in ED.pool.values()) and sorted(prep_disk["materials"]) == sorted(bt.BENCH_MATERIALS)
      and ED.logs("BEAM_TEXTURE_BENCH_PREPARE_OK|run=BEAMTEXPREP-prep") and ED.logs(bt.RESTART + "|run="))
check("+ PREPARE: the compile-scan marker is logged before the first material is created and is in the record",
      ED.logs(prep_disk["marker"]) and prep_disk["marker"].startswith("BEAM_TEXTURE_BENCH_PREPARE_MATERIALS|run="))
check("+ PREPARE: dirtied_by_prepare = the map + the three new material packages, nothing else",
      prep_disk["dirtied_by_prepare"] == {"maps": [MAP], "content": sorted(m.rsplit("/", 1)[-1] for m in bt.BENCH_MATERIALS)})
ed_bad = EditorFake()
ed_bad.spawn_hidden({"label": "ZZ_BEAMTEX_EARLY", "kind": "mesh"})
ed_bad.pool.clear()
ed_bad.census_ = {"maps": [], "content": []}
(tmp / "pb").mkdir()
bt.PrepareBench(ed_bad, tmp / "pb" / "r.json", {}, "PB").run()
iw2 = next(i for i, e in enumerate(ed_bad.events) if e == "record_written")
ic2 = next(i for i, e in enumerate(ed_bad.events) if isinstance(e, tuple) and e[0] in ("create_asset", "spawn"))
check("- control: a spawn before the record is caught by the same ordering check", not iw2 < ic2)
check("+ PREPARE refuses while PIE is running", raises(lambda: bt.PrepareBench(EditorFake(True), tmp / "pb" / "a.json").run(),
                                                       "reason=prepare_needs_editor"))
dirty_ed = EditorFake()
dirty_ed.census_["content"].append("DA_InfinityStage_V1Show")
check("+ PREPARE refuses on a dirty census (a Don't-Save restart must lose nothing): no record, no asset, no spawn",
      raises(lambda: bt.PrepareBench(dirty_ed, tmp / "pb" / "b.json").run(), "reason=dirty_before_prepare")
      and not dirty_ed.pool and not (tmp / "pb" / "b.json").exists()
      and not [e for e in dirty_ed.events if isinstance(e, tuple)])
left_ed = EditorFake()
left_ed.pool["ZZ_BEAMTEX_BAR_0"] = {"on": False}
check("+ PREPARE refuses when ZZ_BEAMTEX_ actors already exist", raises(lambda: bt.PrepareBench(left_ed, tmp / "pb" / "c.json").run(),
                                                                         "reason=leftovers"))
ex_ed = EditorFake(exist=(bt.MAT_NOISE,))
check("+ PREPARE is create-only: refuses when a bench material already exists (nothing created)",
      raises(lambda: bt.PrepareBench(ex_ed, tmp / "pb" / "d.json").run(), "reason=bench_assets_exist")
      and not [e for e in ex_ed.events if isinstance(e, tuple)])
api_ed = EditorFake()
api_ed.missing_api = ["MaterialProperty.MP_SUBSURFACE_COLOR"]
check("+ PREPARE refuses on a missing editor binding before anything", raises(
    lambda: bt.PrepareBench(api_ed, tmp / "pb" / "e.json").run(), "reason=api_missing|MaterialProperty.MP_SUBSURFACE_COLOR"))
check("- control: a material whose read-back is not ok fails PREPARE (prepare_verify)",
      raises(lambda: bt.PrepareBench(EditorFake(bad_material=bt.MAT_NOISE), tmp / "pb" / "f.json").run(),
             "reason=prepare_verify"))
check("- control: a clean editor prepares", not raises(lambda: bt.PrepareBench(EditorFake(), tmp / "pb" / "g.json").run(), "FAILED"))

# ======================= pure geometry =======================
P = dict(bt.DEFAULTS)
U = bt.beam_axis(LAMP_ROT)
check("+ beam axis of the bay-20 BEAM_R (yaw 76, pitch -5) = (0.241, 0.967, -0.087), the record's quaternion",
      all(abs(a - b) < 1e-3 for a, b in zip(U, (0.2410, 0.9666, -0.0872))))
POSE = {"loc": [LAMP[0] - 250.0, 0.0, 90.0], "rot": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0}, "fov_deg": 90.0,
        "aspect": 16 / 9.0}
cross = bt.route_crossing(POSE, LAMP, U)
check("+ route crossing: the beam reaches the route line ~1293 cm from the lamp (1250 / 0.967)", abs(cross - 1250.0 / U[1]) < 1e-6)
check("- control: a beam parallel to the route never crosses it",
      bt.route_crossing(POSE, LAMP, bt.beam_axis({"roll": 0.0, "pitch": 0.0, "yaw": 0.0})) is None)
check("+ ahead_of: lamp 250 cm in front of the camera", abs(bt.ahead_of(POSE, LAMP) - 250.0) < 1e-9)
pz = lb.rotator_axes(**{k: bt.rot_plane_facing(U)[k] for k in ("yaw", "pitch", "roll")})[2]
px = lb.rotator_axes(**{k: bt.rot_from_axis(U)[k] for k in ("yaw", "pitch", "roll")})[0]
check("+ the breakup plane's +Z faces along the beam; the noise box's +X runs along it",
      all(abs(a - b) < 1e-9 for a, b in zip(pz, U)) and all(abs(a - b) < 1e-9 for a, b in zip(px, U)))
check("- control: rot_from_axis does NOT point the plane normal (+Z) along the beam",
      not all(abs(a - b) < 1e-3 for a, b in zip(lb.rotator_axes(**{k: bt.rot_from_axis(U)[k] for k in ("yaw", "pitch", "roll")})[2], U)))
BEAM = {"id": BEAM_ID, "actor_id": BEAM_ACTOR, "label": "x", "location": list(LAMP), "rotation": LAMP_ROT,
        "outer_cone_deg": 7.0, "attenuation_cm": 2600.0, "intensity": 3500.0, "cast_shadows": False,
        "cast_volumetric_shadow": False}
bars, geo = bt.bar_specs(BEAM, P)
r200 = 200.0 * math.tan(math.radians(7.0))
ok_bars = len(bars) == 4
for s in bars:
    ax = lb.rotator_axes(s["rot"]["yaw"], s["rot"]["pitch"], s["rot"]["roll"])[0]
    off = bt.vsub(s["loc"], bt.vadd(LAMP, bt.vmul(U, 200.0)))
    ok_bars = ok_bars and abs(ax[2]) < 1e-9 and abs(bt.vdot(ax, U)) < 1e-9 and abs(bt.vdot(off, U)) < 1e-6 \
        and math.sqrt(bt.vdot(off, off)) < r200
check("+ bars: 4 rods, long axis horizontal and perpendicular to the beam, centred 200 cm out, stacked across the "
      "cone (inside its 24.6 cm radius), duty < 1 (gaps let light through)",
      ok_bars and 0.0 < geo["duty"] < 1.0 and abs(geo["cone_radius_cm"] - r200) < 1e-9)
zs = sorted(s["loc"][2] for s in bars)
check("+ bars stack in height (horizontal slits -> horizontal light sheets, seen edge-on from the route)",
      zs[-1] - zs[0] > 20.0)
rays = bt.cone_rays(BEAM, P, 1300.0)
angs = [math.degrees(math.acos(max(-1.0, min(1.0, bt.vdot(bt.vunit(bt.vsub(e, LAMP)), U))))) for _s, e in rays]
check("+ trace fan: 13 rays (centre + 2 rings of 6), all inside the 7 deg cone, starting 30 cm out",
      len(rays) == 13 and max(angs) <= 7.0 + 1e-6 and abs(math.dist(rays[0][0], LAMP) - 30.0) < 1e-6)
ctl = {"dist": 90.0, "label": "floor"}
hit = {"dist": 400.0, "label": "Passage 01"}
check("+ occlusion: 0/13 clear, 6/13 partial, 13/13 blocked, no control hit = blind",
      bt.classify_occlusion([None] * 13, ctl, P)["verdict"] == "clear"
      and bt.classify_occlusion([hit] * 6 + [None] * 7, ctl, P)["verdict"] == "partial"
      and bt.classify_occlusion([hit] * 13, ctl, P)["verdict"] == "blocked"
      and bt.classify_occlusion([None] * 13, None, P)["verdict"] == "blind")
check("- control: one blocked ray in 13 (7.7 %) is NOT 'clear'", bt.classify_occlusion([hit] + [None] * 12, ctl, P)["verdict"] != "clear")
check("+ occluder policy auto: shown for clear/blind, not for partial/blocked; always / never override",
      bt.occluder_needed({"verdict": "clear"}, P) and bt.occluder_needed({"verdict": "blind"}, P)
      and not bt.occluder_needed({"verdict": "partial"}, P) and not bt.occluder_needed({"verdict": "blocked"}, P)
      and bt.occluder_needed({"verdict": "partial"}, dict(P, a_occluder_policy="always"))
      and not bt.occluder_needed({"verdict": "clear"}, dict(P, a_occluder_policy="never")))
WINGS = PieFake([0.0]).meshes_near(LAMP, 900.0, 40, 3000.0)
adv_c = bt.behind_wing_advice(bt.classify_occlusion([None] * 13, ctl, P), WINGS, BEAM, cross, P)
adv_b = bt.behind_wing_advice(bt.classify_occlusion([hit] * 13, ctl, P), WINGS, BEAM, cross, P)
adv_p = bt.behind_wing_advice(bt.classify_occlusion([hit] * 6 + [None] * 7, ctl, P), WINGS, BEAM, cross, P)
check("+ behind-wing advice: clear -> move the lamp behind the nearest wing (named, 150 cm behind its centre); "
      "blocked -> needs moving in front; partial -> no move",
      adv_c["needs_move"] and "Wing_020_L" in adv_c["candidate"] and len(adv_c["move_lamp_to"]) == 3
      and adv_b["needs_move"] and "in front" in adv_b["advice"] and adv_p["needs_move"] is False)
check("- control: with no wing-like mesh near, clear gives no candidate",
      "candidate" not in bt.behind_wing_advice({"verdict": "clear", "labels": []}, WINGS[1:], BEAM, cross, P))

# ======================= the noise volume material (Python mirror of the HLSL) =======================
NP = dict(P)
samples = [bt.noise3_reference((37.3 * i, 91.7 * (i % 7), 13.1 * (i % 5)), 0.0, NP) for i in range(400)]
lo, hi = NP["b_extinction_peak"] * NP["b_noise_floor"], NP["b_extinction_peak"]
mu = sum(samples) / len(samples)
sd = math.sqrt(sum((s - mu) ** 2 for s in samples) / len(samples))
check("+ noise extinction stays in [floor x peak, peak] = [%.3f, %.3f] 1/m and varies (std %.3f > 0.03)" % (lo, hi, sd),
      min(samples) >= lo - 1e-9 and max(samples) <= hi + 1e-9 and sd > 0.03)
check("- control: contrast 0 flattens the field (std 0): the variance check can fail",
      len({round(bt.noise3_reference((37.3 * i, 11.0, 5.0), 0.0, dict(NP, b_noise_contrast=0.0)), 12) for i in range(50)}) == 1)
cell = NP["b_noise_cm"]
jumps = [abs(bt.noise3_reference((k * cell - 1e-3, 5.0, 7.0), 0.0, NP) - bt.noise3_reference((k * cell + 1e-3, 5.0, 7.0), 0.0, NP))
         for k in range(-3, 4)] + [abs(bt.noise3_reference((289.0 * cell - 1e-3, 3.0, 3.0), 0.0, NP)
                                       - bt.noise3_reference((289.0 * cell + 1e-3, 3.0, 3.0), 0.0, NP))]
check("+ noise is continuous across cell borders and at the 289 wrap (max jump %.5f)" % max(jumps), max(jumps) < 1e-3)


def broken(wp):           # the marble bug (wrap BEFORE +1) lifted to 3D, on the first octave only
    q = [x / cell for x in wp]
    c0 = [math.floor(x) for x in q]
    c0w = [x - 289.0 * math.floor(x / 289.0) for x in c0]
    c1 = [x + 1.0 for x in c0w]
    f = [q[i] - c0[i] for i in range(3)]
    u = [x * x * (3 - 2 * x) for x in f]
    a, b = bt._h3(c0w), bt._h3((c1[0], c0w[1], c0w[2]))
    return a + (b - a) * u[0]


check("- control: wrapping before +1 tears the field at the 289 wrap (jump > 1e-3)",
      abs(broken((289.0 * cell - 1e-3, 0.0, 0.0)) - broken((289.0 * cell + 1e-3, 0.0, 0.0))) > 1e-3)
code = bt.CODE_NOISE3
check("+ HLSL and its Python mirror share the constants (hash 127.1/311.7/74.7, 43758.5453, lacunarity 2.03, octave "
      "offsets, 289 wrap per corner, gain 0.5) and every input pin is used",
      all(t in code for t in ("127.1, 311.7, 74.7", "43758.5453", "2.03", "17.1, 5.3, 11.7", "289.0 * floor(c0",
                              "289.0 * floor(c1", "amp *= 0.5", "o < 3"))
      and all(re.search(r"\b%s\b" % n, code) for n in bt.NOISE_INPUTS) and set(bt.NOISE_PARAMS) <= set(bt.NOISE_INPUTS))
check("- control: the pin check catches a pin the code does not use",
      not all(re.search(r"\b%s\b" % n, code) for n in bt.NOISE_INPUTS + ["Unused"]))
check("+ breakup threshold code uses its three pins", all(re.search(r"\b%s\b" % n, bt.CODE_BREAKUP) for n in ("X", "Thr", "Contrast")))

# ======================= D targets =======================
brief = bt.d_cvar_targets({"r.VolumetricFog.GridPixelSize": 8.0, "r.VolumetricFog.GridSizeZ": 64.0,
                           "r.VolumetricFog.HistoryWeight": 0.9}, P)
check("+ D at the brief's base (8 / 64 / 0.9): targets 4 / 128 / 0.6, nothing escalated",
      [brief[n]["target"] for n in sorted(brief)] == [4.0, 128.0, 0.6] and not any(t["escalated"] for t in brief.values()))
live = bt.d_cvar_targets({"r.VolumetricFog.GridPixelSize": 4.0, "r.VolumetricFog.GridSizeZ": 128.0,
                          "r.VolumetricFog.HistoryWeight": 0.9}, P)
check("+ D at tonight's measured base (Cine: 4 / 128): escalates to 2 / 256 and says so",
      live["r.VolumetricFog.GridPixelSize"]["target"] == 2.0 and live["r.VolumetricFog.GridSizeZ"]["target"] == 256.0
      and live["r.VolumetricFog.GridPixelSize"]["escalated"] and not live["r.VolumetricFog.HistoryWeight"]["escalated"])
noesc = bt.d_cvar_targets({"r.VolumetricFog.GridPixelSize": 4.0, "r.VolumetricFog.GridSizeZ": 128.0,
                           "r.VolumetricFog.HistoryWeight": 0.9}, dict(P, d_escalate=False))
check("- control: d_escalate False leaves those two as no-ops (no op emitted)",
      noesc["r.VolumetricFog.GridPixelSize"]["noop"] and noesc["r.VolumetricFog.GridSizeZ"]["noop"]
      and len(bt.plan_d([], {k: v["live"] for k, v in noesc.items()}, dict(P, d_escalate=False))["ops"]) == 1)

# ======================= locate =======================
def ahead_at(f):
    return LAMP[0] - f * ROUTE_LEN


ok_loc = True
iters = []
for target in (450.0, 250.0, 50.0):
    s = [(19 / 48.0, ahead_at(19 / 48.0))]
    for _ in range(20):
        nxt, done, best = bt.locate_next(s, target, P, 48)
        if done:
            break
        s.append((nxt, ahead_at(nxt)))
    iters.append(len(s))
    ok_loc = ok_loc and done and abs(best[1] - target) <= P["locate_tol_cm"]
check("+ locate: from the bay guess, the secant finds ahead 450 / 250 / 50 cm within 60 cm (%s scrubs)" % iters,
      ok_loc and max(iters) <= 4)
s1 = [(19 / 48.0, ahead_at(19 / 48.0))]
nxt, done, best = bt.locate_next(s1, 450.0, dict(P, locate_max_iter=1), 48)
check("- control: one scrub allowed -> done without reaching the target (gate fails)", done and abs(best[1] - 450.0) > 60.0)
nxt2, _d, _b = bt.locate_next([(0.5, 900.0), (0.52, 1200.0)], 450.0, P, 48)
check("+ locate: a non-monotonic pair falls back to a fixed forward step (camera behind the lamp moves forward)",
      nxt2 > 0.52)

# ======================= mask + texture metric =======================
spec = bt.mask_spec(POSE, BEAM, P, 320, 180)
frac = bt.mask_fraction(bt.mask_grid(spec, 160, 90))
check("+ mask: at 250 cm ahead the beam core covers %.1f %% of the frame (>= 0.4 %%)" % (100 * frac),
      frac >= P["mask_min_frac"] and spec["s0"] == 260.0)
away = dict(POSE, rot={"yaw": 180.0, "pitch": 0.0, "roll": 0.0})
check("- control: a camera looking back down the route sees no beam (fraction 0)",
      bt.mask_fraction(bt.mask_grid(bt.mask_spec(away, BEAM, P, 320, 180), 160, 90)) == 0.0)


def synth(kind, level=110.0):
    w, h = 160, 90
    m = bt.mask_grid(spec, w, h)
    rows = []
    for j in range(h):
        row = []
        for i in range(w):
            v = 25.0
            if m[j][i]:
                b = level * (0.85 + 0.15 * i / w)
                if kind == "stripes":
                    b *= 0.35 if (j // 2) % 2 else 1.0
                row.append(v + b)
            else:
                row.append(v)
        rows.append(row)
    return rows, m


base_rows, M = synth("smooth")
base_m = bt.texture_metric(base_rows, M, 3)
str_m = bt.texture_metric(synth("stripes")[0], M, 3)
dark_m = bt.texture_metric(synth("stripes", level=8.0)[0], M, 3)
check("+ texture: a striped beam has more high-pass texture than the smooth base (hp_rel %.3f vs %.3f) -> TEXTURED"
      % (str_m["hp_rel"], base_m["hp_rel"]), bt.texture_verdict(base_m, str_m, P)["textured"] is True)
check("- control (the failing base): base vs itself is ratio 1.00, NOT textured",
      bt.texture_verdict(base_m, base_m, P)["textured"] is False and abs(bt.texture_verdict(base_m, base_m, P)["ratio"] - 1.0) < 1e-9)
check("- control: stripes on a beam left at 7 % brightness are 'beam lost', not texture",
      bt.texture_verdict(base_m, dark_m, P)["why"] == "beam lost")
grad = [[25.0 + (140.0 * i / 160 if M[j][i] else 0.0) for i in range(160)] for j in range(90)]
check("- control: a slow gradient along the beam (falloff) is not counted as texture (high-pass)",
      bt.texture_verdict(base_m, bt.texture_metric(grad, M, 3), P)["textured"] is False)

# ======================= plans, ALL, ordering =======================
F0 = PieFake([0.0])
fogs0 = F0.fogs()
occ_clear = bt.classify_occlusion([None] * 13, ctl, P)
plans = {"A": bt.plan_a(BEAM, occ_clear, P), "B": bt.plan_b(POSE, BEAM, fogs0, P), "BL": bt.plan_bl(POSE, BEAM, fogs0, P),
         "D": bt.plan_d(fogs0, {"r.VolumetricFog.GridPixelSize": 8.0, "r.VolumetricFog.GridSizeZ": 64.0,
                                "r.VolumetricFog.HistoryWeight": 0.9}, P)}
check("+ A: shadows + volumetric shadow on the beam only; 4 bars shown when clear",
      plans["A"]["ops"] == [("light", BEAM_ID, "cast_shadows", True), ("light", BEAM_ID, "cast_volumetric_shadow", True)]
      and [s["label"] for s in plans["A"]["pool"]] == ["ZZ_BEAMTEX_BAR_%d" % k for k in range(4)])
check("+ A with a_occluder breakup shows the single breakup plane instead",
      [s["label"] for s in bt.plan_a(BEAM, occ_clear, dict(P, a_occluder="breakup"))["pool"]] == ["ZZ_BEAMTEX_BREAKUP"])
check("- control: A with the beam already cut by a wing (partial) shows no occluder",
      not bt.plan_a(BEAM, bt.classify_occlusion([hit] * 6 + [None] * 7, ctl, P), P)["pool"])
ob = {bt.key(*o[:3]): o[3] for o in plans["B"]["ops"]}
nb = plans["B"]["pool"][0]
nb_x = lb.rotator_axes(nb["rot"]["yaw"], nb["rot"]["pitch"], nb["rot"]["roll"])[0]
check("+ B: fog x0.75 (density and second density) + the noise box along the beam from s0 to s1",
      abs(ob["fog|%s|fog_density" % FOG_ID] - fogs0[0]["fog_density"] * 0.75) < 1e-12
      and abs(ob["fog|%s|second_fog_density" % FOG_ID] - fogs0[0]["second_fog_density"] * 0.75) < 1e-12
      and nb["label"] == "ZZ_BEAMTEX_NOISEBOX" and all(abs(a - b) < 1e-9 for a, b in zip(nb_x, U))
      and abs(nb["scale"][0] * 100.0 - (spec["s1"] - spec["s0"])) < 1e-6)
cl = plans["BL"]["pool"]
check("+ BL: 6 LFV clumps strung along the beam, radii and densities varied inside their ranges, deterministic",
      len(cl) == 6 and len({round(c["scale"], 6) for c in cl}) == 6
      and all(P["bl_ext_min"] <= c["radial"] <= P["bl_ext_max"] for c in cl)
      and cl == bt.plan_bl(POSE, BEAM, fogs0, P)["pool"])
all_ops, all_pool = bt.variant_plan("ALL", plans)
union = set()
for v in ("A", "B", "D"):
    union |= {bt.key(*o[:3]) for o in bt.variant_plan(v, plans)[0]}
check("+ ALL = exactly A + B + D (keys and pool), base has nothing",
      {bt.key(*o[:3]) for o in all_ops} == union and len(all_pool) == 5 and bt.variant_plan("base", plans) == ([], []))
bad_plans = dict(plans, D=dict(plans["D"], ops=plans["D"]["ops"] + [("fog", FOG_ID, "fog_density", 9.0)]))
check("- control: two parts writing different values to one key are refused in ALL",
      raises(lambda: bt.variant_plan("ALL", bad_plans), "BEAM_TEXTURE_BENCH_CONFLICT"))
EXPECT = [("locate",), ("repose",), ("settle", "base_ref"), ("plan",), ("time", "base"), ("shoot", "base")]
for i, v in enumerate(("A", "B", "D", "ALL")):
    EXPECT += ([("settle", "base_return")] if i else []) + [("apply", v), ("settle", "state"), ("hold", v), ("time", v),
                                                             ("shoot", v)]
EXPECT.append(("settle", "base_return_final"))
check("+ order: base first, then A B D ALL each after a base return (none needed before the first), final base return",
      bt.position_tasks(bt.DEFAULT_VARIANTS) == EXPECT)


def ordering_ok(tasks):
    clean = True
    changed = False
    for t in tasks:
        if t[0] == "apply":
            if not clean:
                return False
            clean, changed = False, True
        if t[0] == "settle" and t[1].startswith("base_return"):
            clean = True
        if t == ("shoot", "base") and changed:
            return False
    return clean


check("+ ordering checker accepts the plan", ordering_ok(bt.position_tasks(bt.DEFAULT_VARIANTS)))
brk = bt.position_tasks(bt.DEFAULT_VARIANTS)
brk.remove(("settle", "base_return"))
check("- control: dropping a base return / the final one is caught",
      not ordering_ok(brk) and not ordering_ok(bt.position_tasks(bt.DEFAULT_VARIANTS)[:-1]))

# ======================= bench: originals, apply, restore =======================
Wb = PieFake([0.0])
before = Wb.snapshot()
bb = bt.BeamBench(Wb, tmp / "bench1.json", {}, "BEAMTEX-T1")
bb.read_globals(Wb.census(), {"run": "x"})
check("- control: apply before the keys are recorded is refused (originals first)",
      raises(lambda: bb.apply("ALL", all_ops, all_pool), "BEAM_TEXTURE_BENCH_NOT_RECORDED"))
bb.record_keys(bt.all_keys(plans), "a250", {"x": 1})
Wb.record_path = tmp / "bench1.json"
bb.neutralise()
bb.apply("ALL", all_ops, all_pool)
check("+ apply ALL: every key on disk before its write; world changed (shadows on, fog, scattering, cvars, pool, strobe off)",
      not Wb.violations and Wb.read("light", BEAM_ID, "cast_volumetric_shadow") is True
      and Wb.read("cvar", "r.VolumetricFog.GridPixelSize", "value") == 4.0 and sum(v["on"] for v in Wb.pool.values()) == 5
      and Wb.strobes["/PIE/Opening_Strobe"] is False)
check("+ restore is exact: verify() == [] and the whole fake world equals its pre-bench snapshot",
      bb.restore() == [] and Wb.snapshot() == before)
Wl = PieFake([0.0])
bl = bt.BeamBench(Wl, tmp / "bench2.json", {}, "BEAMTEX-T2")
bl.read_globals(Wl.census(), None)
bl.record_keys(bt.all_keys(plans))
bl.apply("ALL", all_ops, all_pool)
orig_write = Wl.write
Wl.write = lambda k, o, f, v: None if k == "cvar" else orig_write(k, o, f, v)
check("- control: a lost cvar restore is reported by verify()", any("cvar|" in x for x in bl.restore()))
Wl.write = orig_write
bl.apply("B", *bt.variant_plan("B", plans))
Wl.hide_pool = lambda label: None
check("- control: a noise box left shown is reported", any("pool still shown" in x for x in bl.restore()))
Wr = PieFake([0.0])
before_r = Wr.snapshot()
br = bt.BeamBench(Wr, tmp / "bench3.json", {}, "BEAMTEX-T3")
br.read_globals(Wr.census(), None)
br.record_keys(bt.all_keys(plans))
br.neutralise()
br.apply("ALL", all_ops, all_pool)
del br
check("+ RESTORE from the record alone is exact (shadow flags, fog, scattering, cvars, pool, strobe)",
      bt.restore_all(Wr, [tmp / "bench3.json"], Wr.log) == [] and Wr.snapshot() == before_r)

# ======================= full CAPTURE runs on the fake =======================
r1, f1, snap1, mid1 = run()
m1 = manifest(r1)
check("+ run: CAPTURE_OK|run=BEAMTEX-... logged, status passed, no gate failure, no error",
      f1.logs("BEAM_TEXTURE_BENCH_CAPTURE_OK|run=" + r1["run_id"]) and m1["status"] == "passed"
      and not m1["gate_failures"] and not m1["errors"])
stills = [s for pos in m1["positions"] for v in pos["shots"].values() for s in v["stills"]]
check("+ run: 3 positions x 5 variants x 3 stills = 45 PNGs in BeamTextureBench/<run>/<pos>/<variant>_<i>.png",
      len(stills) == 45 and all(pathlib.Path(s["path"]).is_file() for s in stills)
      and {pathlib.Path(s["path"]).parent.name for s in stills} == {"a450", "a250", "a050"})
check("+ run: the fake world is back to its pre-run snapshot, census unchanged, originals on disk before every write",
      f1.snapshot() == snap1 and m1["census_after"] == m1["census_before"] and not f1.violations)
check("+ run: the Opening strobe was OFF during the variants and restored after",
      mid1 == {"strobes": {"/PIE/Opening_Strobe": False}} and f1.strobes["/PIE/Opening_Strobe"] is True)
locs = {p["name"]: p for p in m1["positions"]}
check("+ locate: every position within 60 cm of its target (%s), frames advance a450 < a250 < a050" % {
    k: round(v["ahead_found_cm"]) for k, v in locs.items()},
      all(abs(v["ahead_found_cm"] - v["ahead_cm"]) <= 60.0 for v in locs.values())
      and locs["a450"]["target_frame"] < locs["a250"]["target_frame"] < locs["a050"]["target_frame"])
check("+ every position: beam struck (intensity >= 1 cd), core mask in shot, occlusion 'clear' -> 4 bars",
      all(p["plan"]["struck"] and p["plan"]["mask_frac"] >= 0.004 and p["plan"]["occlusion"]["verdict"] == "clear"
          and p["plan"]["A"]["occluder"] == "bars" for p in m1["positions"]))
check("+ timings: base and every variant have an editor frame-time window (n > 0) at every position",
      all(set(p["timings"]) == set(bt.DEFAULT_VARIANTS) and all(t["n"] > 0 for t in p["timings"].values())
          for p in m1["positions"]))
per_pos = {}
for t in m1["task_log"]:
    per_pos.setdefault(t[0], []).append(tuple(t[1:]))
check("+ executed order per position obeys base-first / base-return-between / base-final",
      set(per_pos) == {"a450", "a250", "a050"} and all(ordering_ok(v) for v in per_pos.values()))
check("+ markers carry the run id: START ANNOUNCE LOCATE PLAN OCCLUSION TIME STILL CAPTURE_OK NEEDS_DONT_SAVE_RESTART",
      all(any(m.startswith("BEAM_TEXTURE_BENCH_%s|run=%s" % (t, r1["run_id"])) for m in f1.logs_)
          for t in ("START", "ANNOUNCE", "LOCATE", "PLAN", "OCCLUSION", "TIME", "STILL", "CAPTURE_OK",
                    "NEEDS_DONT_SAVE_RESTART")))
dp = m1["positions"][0]["plan"]["D"]
check("+ D at the fake brief base (8 / 64 / 0.9) is not escalated; the manifest records cvars and scattering_was 0.2",
      not dp["escalated"] and abs(dp["scattering_was"][0] - 0.2) < 1e-6)

r2, f2, _s, _m = run(cvars={"r.VolumetricFog.GridPixelSize": 4.0, "r.VolumetricFog.GridSizeZ": 128.0})
m2 = manifest(r2)
check("+ D at tonight's measured base (4 / 128): escalated to 2 / 256 in the plan, applied and restored",
      sorted(m2["positions"][0]["plan"]["D"]["escalated"]) == ["r.VolumetricFog.GridPixelSize", "r.VolumetricFog.GridSizeZ"]
      and m2["status"] == "passed" and f2.read("cvar", "r.VolumetricFog.GridPixelSize", "value") == 4.0)
r3, f3, _s, _m = run(occlusion="partial")
m3 = manifest(r3)
check("+ a pierced wing in the beam (partial): A shows no occluder, verdict + advice in the plan",
      all(p["plan"]["occlusion"]["verdict"] == "partial" and p["plan"]["A"]["occluder"] is None
          and p["plan"]["behind_wing"]["needs_move"] is False for p in m3["positions"]) and m3["status"] == "passed")
r4, f4, _s, _m = run(occlusion="blocked")
check("+ a wing fully in front (blocked): the advice says the light needs moving",
      all(p["plan"]["behind_wing"]["needs_move"] for p in manifest(r4)["positions"])
      and f4.logs("|verdict=blocked|"))
r5, f5, _s, _m = run(control_hit=False)
check("+ traces blind (control trace hits nothing): verdict blind, occluder shown anyway (auto)",
      all(p["plan"]["occlusion"]["verdict"] == "blind" and p["plan"]["A"]["occluder"] == "bars"
          for p in manifest(r5)["positions"]))
rU, fU, _s, _m = run(params={"positions": ({"name": "far", "ahead_cm": 1200.0},)})
check("- control: a position before the strike (lamp 12 m ahead) fails the struck gate (FAILED, reason unstruck)",
      fU.logs("BEAM_TEXTURE_BENCH_FAILED|run=%s|reason=unstruck" % rU["run_id"]))
rH, fH, _s, _m = run(reapply_shadows=True)
check("+ hold check: a Show re-apply that resets cast_shadows during A is HELD ok=False -> FAILED",
      fH.logs("BEAM_TEXTURE_BENCH_HELD|run=%s|pos=a450|variant=A|ok=False" % rH["run_id"]) and manifest(rH)["status"] == "failed")
check("- control: without it every HELD line is ok=True", all("ok=True" in m for m in f1.logs("BEAM_TEXTURE_BENCH_HELD|")))
rR, fR, _s, _m = run(residual_after="B")
check("- control: a picture left 25 brighter after B fails the base return (FAILED)",
      fR.logs("BEAM_TEXTURE_BENCH_FAILED|run=%s|reason=base_return" % rR["run_id"]))
rY, fY, _s, _m = run(dry=True)
mY = manifest(rY)
check("+ dry run: locate + plans + base stills only (9), no property write, passes",
      mY["status"] == "passed" and not [e for e in fY.events if isinstance(e, tuple) and e[0] == "write"
                                        and not e[1].startswith("strobe|")]
      and len([s for p in mY["positions"] for v in p["shots"].values() for s in v["stills"]]) == 9)
rL, fL, _s, _m = run(params={"variants": ("base", "A", "B", "BL", "D", "ALL")})
check("+ optional BL variant runs too (6 variants x 3 positions x 3 = 54 stills), passes",
      manifest(rL)["status"] == "passed" and len([s for p in manifest(rL)["positions"] for v in p["shots"].values()
                                                  for s in v["stills"]]) == 54)


# ======================= refusals at CAPTURE arm =======================
def arm_only(f, store=None, prep=PREP, params=None, owner=None, out=None, log_path=LOG, prepare_root=None):
    out = out or tmp / ("arm_%d" % len(RESULTS))
    return bt.arm(f, prep, dict(TEST_P, **(params or {})), out_root=out, prepare_root=prepare_root or tmp / "nowhere",
                  owner_path=owner or tmp / "o.json", log_path=log_path, register=lambda fn: "H",
                  unregister=lambda h: None, store=store or Store(), clock=lambda: 0.0)


nopie = PieFake([0.0], kind=None)
out_np = tmp / "nopie_out"
check("+ CAPTURE refuses without PIE: FAILED|run=BEAMTEX-...|reason=no_pie, no run dir, no write",
      raises(lambda: arm_only(nopie, out=out_np), "reason=no_pie") and not out_np.exists()
      and re.match(r"BEAM_TEXTURE_BENCH_FAILED\|run=BEAMTEX-\d{8}-\d{6}\|reason=no_pie", nopie.errors[0]))
check("+ refuses with the pool missing (PREPARE not run before PIE)",
      raises(lambda: arm_only(PieFake([0.0], prepared=False)), "reason=pool_missing"))
lit_f = PieFake([0.0])
lit_f.pool["ZZ_BEAMTEX_NOISEBOX"]["on"] = True
check("+ refuses while a pool actor is still shown", raises(lambda: arm_only(lit_f), "reason=pool_not_base"))
armed = Store()
armed.PUSS_PASSAGE_STILLS_HANDLE = "H"
check("+ refuses while another PUSS_* tick is armed", raises(lambda: arm_only(PieFake([0.0]), store=armed), "reason=tick_armed"))
(tmp / "owner_on.json").write_text('{"active": true}', encoding="utf-8")
check("+ refuses with an active pie_recording_owner.json",
      raises(lambda: arm_only(PieFake([0.0]), owner=tmp / "owner_on.json"), "reason=pie_owner_active"))
(tmp / "other.json").write_text(json.dumps(dict(prep_disk, world="/Game/Other/L_Other.L_Other")), encoding="utf-8")
check("+ refuses a PREPARE record from another level", raises(lambda: arm_only(PieFake([0.0]), prep=tmp / "other.json"), "reason=wrong_world"))
check("+ refuses with no PREPARE record", raises(lambda: arm_only(PieFake([0.0]), prep=tmp / "missing.json"), "reason=not_prepared"))
(tmp / "partial.json").write_text(json.dumps(dict(prep_disk, status="partial")), encoding="utf-8")
check("+ refuses a partial PREPARE", raises(lambda: arm_only(PieFake([0.0]), prep=tmp / "partial.json"), "reason=prepare_incomplete"))
check("+ refuses variants not starting with base / repeated",
      raises(lambda: arm_only(PieFake([0.0]), params={"variants": ("A", "base")}), "reason=bad_variants")
      and raises(lambda: arm_only(PieFake([0.0]), params={"variants": ("base", "A", "A")}), "reason=bad_variants"))
fa = PieFake([0.0])
fa.missing_api = ["LightComponentBase.set_cast_volumetric_shadow"]
out_api = tmp / "api_out"
check("+ refuses on a missing binding before any write or run dir (api_missing)",
      raises(lambda: arm_only(fa, out=out_api), "reason=api_missing|LightComponentBase.set_cast_volumetric_shadow")
      and not out_api.exists() and not [e for e in fa.events if isinstance(e, tuple)] and fa.strobes["/PIE/Opening_Strobe"])
two = PieFake([0.0])
two.extra_beams = ["P01 SCORE B20 COPY BEAM_R"]
check("+ refuses when the beam is ambiguous (2 lights match) or absent",
      raises(lambda: arm_only(two), "reason=beam_not_found|2 lights")
      and raises(lambda: arm_only(PieFake([0.0]), params={"bay": 19}), "reason=beam_not_found|0 lights"))
novf = PieFake([0.0])
novf.volumetric = False
check("+ refuses when no height fog has volumetric fog on (no beam to texture)", raises(lambda: arm_only(novf), "reason=no_volumetric_fog"))
bad_log = tmp / "bad.log"
bad_log.write_text(fake_log_text(PREP_REC["marker"], ["[x] LogMaterial: Error: [SM6] M_ZZ_BeamTex_NoiseVolume failed to compile"]),
                   encoding="utf-8")
check("+ refuses when the noise material failed to compile after PREPARE (log scan)",
      raises(lambda: arm_only(PieFake([0.0]), log_path=bad_log), "reason=material_compile_failed|" + bt.MAT_NOISE))
old_log = tmp / "old.log"
old_log.write_text("[x] LogMaterial: Error: M_ZZ_BeamTex_NoiseVolume failed to compile\n" + fake_log_text(PREP_REC["marker"]),
                   encoding="utf-8")
check("- control: an error line from before the PREPARE marker is ignored (arms)",
      not raises(lambda: arm_only(PieFake([0.0]), log_path=old_log), "FAILED"))
check("+ refuses when the PREPARE marker is not in the log (cannot judge the materials)",
      raises(lambda: arm_only(PieFake([0.0]), log_path=tmp / "nolog.log"), "reason=compile_unknown"))
check("- control: base + D only needs no bench material: arms without the marker",
      not raises(lambda: arm_only(PieFake([0.0]), log_path=tmp / "nolog.log", params={"variants": ("base", "D")}), "FAILED"))
sr = tmp / "sessions"
for name in ("BEAMTEXPREP-20261006-180000", "BEAMTEXPREP-20261006-190000"):
    (sr / "_prepare" / name).mkdir(parents=True)
    (sr / "_prepare" / name / bt.PREPARE_RECORD_NAME).write_text(json.dumps(dict(prep_disk, run=name)), encoding="utf-8")
for run_name, prep_run in (("BEAMTEX-20261006-180100", "BEAMTEXPREP-20261006-180000"),
                           ("BEAMTEX-20261006-190100", "BEAMTEXPREP-20261006-190000")):
    (sr / run_name).mkdir()
    (sr / run_name / bt.ORIGINALS_NAME).write_text(json.dumps({"prepare_run": prep_run}), encoding="utf-8")
check("+ RESTORE default records: only captures armed on the NEWEST PREPARE",
      [x.parent.name for x in bt.session_records(sr, sr / "_prepare")] == ["BEAMTEX-20261006-190100"])
check("+ refuses an explicit PREPARE record that is not the newest (stale_prepare)",
      raises(lambda: arm_only(PieFake([0.0]), prep=sr / "_prepare" / "BEAMTEXPREP-20261006-180000" / bt.PREPARE_RECORD_NAME,
                              prepare_root=sr / "_prepare"), "reason=stale_prepare"))
check("- control: a clean PIE fake arms", not raises(lambda: arm_only(PieFake([0.0])), "FAILED"))
args_disk = json.loads((HERE / "beam_texture_bench_args.json").read_text(encoding="utf-8"))
check("+ beam_texture_bench_args.json pins no PREPARE record and runs the full default", args_disk == {
    "dry": False, "params": {}, "prepare_record": None})


# ======================= the REAL PIE adapter on a strict fake `unreal` =======================
def strict_unreal(drop=()):
    U_ = types.SimpleNamespace()
    logs = {"log": [], "err": [], "cmd": []}

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
        def __init__(self, path, label, comps=(), **props):
            super().__init__(path, **props)
            self._label, self._comps = label, list(comps)
            for c in self._comps:
                c._owner = self
        def get_actor_label(self): return self._label
        def actor_has_tag(self, t): return False
        def get_component_by_class(self, cls): return next((c for c in self._comps if isinstance(c, cls)), None)
        def get_components_by_class(self, cls): return [c for c in self._comps if isinstance(c, cls)]
        def get_actor_location(self): return Vector()
        def set_actor_location_and_rotation(self, *a): return True
        def set_actor_scale3d(self, v): pass
        def set_actor_hidden_in_game(self, h): pass

    class ActorComponent(Obj):
        def get_owner(self): return getattr(self, "_owner", None)

    class SceneComponent(ActorComponent):
        def get_world_location(self): return Vector(*self._props.get("_loc", (0, 0, 0)))
        def get_world_rotation(self): return Rotator(*self._props.get("_rot", (0, 0, 0)))
        def is_visible(self): return True
        def set_visibility(self, v, p): pass

    class PrimitiveComponent(SceneComponent): pass
    class StaticMeshComponent(PrimitiveComponent): pass

    class LightComponentBase(SceneComponent):
        def set_cast_shadows(self, v): self._props["cast_shadows"] = bool(v)
        def set_cast_volumetric_shadow(self, v): self._props["cast_volumetric_shadow"] = bool(v)

    class LightComponent(LightComponentBase): pass
    class LocalLightComponent(LightComponent): pass
    class SpotLightComponent(LocalLightComponent): pass

    class SecondFog(Obj): pass

    class ExponentialHeightFogComponent(SceneComponent):
        def set_fog_density(self, v): self._props["fog_density"] = float(v)
        def set_second_fog_density(self, v): self._props["second_fog_data"]._props["fog_density"] = float(v)
        def set_volumetric_fog_scattering_distribution(self, v):
            self._props["volumetric_fog_scattering_distribution"] = float(v)

    class LocalFogVolumeComponent(SceneComponent):
        def set_radial_fog_extinction(self, v): pass
        def set_height_fog_extinction(self, v): pass
        def set_height_fog_falloff(self, v): pass
        def set_height_fog_offset(self, v): pass
        def set_fog_phase_g(self, v): pass

    class StaticMeshActor(Actor): pass
    class ExponentialHeightFog(Actor): pass
    class LocalFogVolume(Actor): pass
    class PostProcessVolume(Actor): pass
    class InfinityStageShowRoot(Actor): pass

    class PlayerCameraManager(Actor):
        def get_camera_location(self): return Vector(LAMP[0] - 250.0, 0.0, 90.0)
        def get_camera_rotation(self): return Rotator()
        def get_fov_angle(self): return 90.0

    class HitResult:
        def __init__(self, fields): self._f = fields
        def to_tuple(self): return self._f

    beam_c = SpotLightComponent(BEAM_ID, _loc=LAMP, _rot=(0.0, -5.0, 76.0), outer_cone_angle=7.0,
                                attenuation_radius=2600.0, intensity=3500.0, cast_shadows=False,
                                cast_volumetric_shadow=False, volumetric_scattering_intensity=6.0)
    beam_a = Actor(BEAM_ACTOR, "P01 SCORE B20 P01_WARM_THEATRICAL BEAM_R", [beam_c])
    other_c = SpotLightComponent("/PIE/B19.L", outer_cone_angle=7.0, attenuation_radius=2600.0, intensity=1.0,
                                 cast_shadows=False, cast_volumetric_shadow=False, volumetric_scattering_intensity=6.0)
    other = Actor("/PIE/B19", "P01 SCORE B19 P01_WARM_THEATRICAL BEAM_R", [other_c])
    fog_c = ExponentialHeightFogComponent(FOG_ID, fog_density=0.02, second_fog_data=SecondFog("sfd", fog_density=0.004),
                                          enable_volumetric_fog=True, volumetric_fog_scattering_distribution=0.2)
    fog_a = ExponentialHeightFog("/PIE/HeightFog", "HeightFog", [fog_c])
    wing_c = StaticMeshComponent("/PIE/Passage01.Wing_020_L")
    wing = Actor("/PIE/Passage01", "Passage 01", [wing_c])
    pcm = PlayerCameraManager("/PIE/PCM", "PCM")
    actors = [beam_a, other, fog_a, wing, pcm]
    objects = {o.get_path_name(): o for o in actors + [beam_c, fog_c, wing_c, other_c]}
    cvars = {"r.VolumetricFog.GridPixelSize": 4.0}
    world = Obj("/Game/Maps/UEDPIE_0_L.L")

    class GameplayStatics:
        @staticmethod
        def get_all_actors_of_class(w, cls): return [a for a in actors if isinstance(a, cls)]
        @staticmethod
        def get_player_camera_manager(w, i): return pcm

    class SystemLibrary:
        @staticmethod
        def execute_console_command(w, c):
            logs["cmd"].append(c)
            n, v = c.split(" ", 1)
            cvars[n] = float(v)
        @staticmethod
        def get_console_variable_float_value(n): return cvars.get(n, 0.0)
        @staticmethod
        def get_component_bounds(c): return Vector(LAMP[0] + 250.0, -1150.0, 300.0), Vector(40.0, 160.0, 300.0), 340.0
        @staticmethod
        def line_trace_single(w, s, e, ch, cx, ign, dbg, self_):
            if beam_a not in ign:
                return (True, HitResult([True, False, 0.01, 1.0, None, None, None, None, None, beam_a, beam_c]))
            return (True, HitResult([True, False, 0.3, 420.0, None, None, None, None, None, wing, wing_c]))

    class Editor:
        def get_game_world(self): return world

    class EditorLoadingAndSavingUtils:
        @staticmethod
        def get_dirty_map_packages(): return []
        @staticmethod
        def get_dirty_content_packages(): return []

    for name, val in dict(locals()).items():
        if isinstance(val, type):
            setattr(U_, name, val)
    U_.Name = str
    U_.PropertyAccessChangeNotifyMode = types.SimpleNamespace(NEVER="NEVER")
    U_.TraceTypeQuery = types.SimpleNamespace(TRACE_TYPE_QUERY1=1)
    U_.DrawDebugTrace = types.SimpleNamespace(NONE=0)
    U_.UnrealEditorSubsystem = object
    U_.get_editor_subsystem = lambda cls: Editor()
    U_.find_object = lambda outer, path: objects.get(path)
    U_.log = logs["log"].append
    U_.log_error = logs["err"].append
    U_._logs, U_._cvars = logs, cvars
    for dotted in drop:
        cls, attr = dotted.split(".")
        delattr(getattr(U_, cls), attr)
    return U_


SU = strict_unreal()
SA = bt.make_pie_adapter(SU)
rows_s = SA.beam_rows(bt.beam_regex(dict(bt.DEFAULTS)))
check("+ real adapter: beam_rows finds exactly the bay-20 BEAM_R component (not bay 19) with cone, attenuation, "
      "intensity and both shadow flags", len(rows_s) == 1 and rows_s[0]["id"] == BEAM_ID and rows_s[0]["outer_cone_deg"] == 7.0
      and rows_s[0]["attenuation_cm"] == 2600.0 and rows_s[0]["cast_volumetric_shadow"] is False and rows_s[0]["spot"])
SA.write("light", BEAM_ID, "cast_shadows", True)
SA.write("light", BEAM_ID, "cast_volumetric_shadow", True)
check("+ real adapter: shadow flags go through SetCastShadows / SetCastVolumetricShadow and read back",
      SA.read("light", BEAM_ID, "cast_shadows") is True and SA.read("light", BEAM_ID, "cast_volumetric_shadow") is True)
check("- control: any other light field is refused, never guessed",
      raises(lambda: SA.write("light", BEAM_ID, "intensity", 1.0), "LIGHT_FIELD"))
SA.write("fog", FOG_ID, "second_fog_density", 0.001)
SA.write("fog", FOG_ID, "scattering_distribution", 0.7)
check("+ real adapter: second fog density and scattering distribution written via their setters and read back",
      abs(SA.read("fog", FOG_ID, "second_fog_density") - 0.001) < 1e-12 and SA.read("fog", FOG_ID, "scattering_distribution") == 0.7)
SA.write("cvar", "r.VolumetricFog.GridSizeZ", "value", 256.0)
SA.write("cvar", "r.VolumetricFog.HistoryWeight", "value", 0.6)
check("+ real adapter: cvars set by console command ('r.VolumetricFog.GridSizeZ 256', '... 0.6') and read back",
      "r.VolumetricFog.GridSizeZ 256" in SU._logs["cmd"] and "r.VolumetricFog.HistoryWeight 0.6" in SU._logs["cmd"]
      and SA.read("cvar", "r.VolumetricFog.GridSizeZ", "value") == 256.0)
h_ok = SA.trace(LAMP, (LAMP[0], 0.0, 0.0), BEAM_ACTOR)
h_self = SA.trace(LAMP, (LAMP[0], 0.0, 0.0), None)
check("+ real adapter: a trace ignoring the lamp reports the wing hit (label, component, distance) via to_tuple()",
      h_ok == {"dist": 420.0, "label": "Passage 01", "component": "Wing_020_L"})
check("- control: without ignoring the lamp the trace stops on the lamp itself (why the lamp is ignored)",
      h_self["label"].endswith("BEAM_R"))
mn = SA.meshes_near(LAMP, 900.0, 10, 3000.0)
check("+ real adapter: meshes_near returns the wing component with its bounds", mn and mn[0]["component"] == "Wing_020_L")
check("+ api_missing: nothing missing on the strict fake; dropping SetCastVolumetricShadow is reported",
      SA.api_missing() == [] and bt.make_pie_adapter(strict_unreal(drop=("LightComponentBase.set_cast_volumetric_shadow",)))
      .api_missing() == ["LightComponentBase.set_cast_volumetric_shadow"])

# ======================= source scans =======================
SAVE = re.compile(r"save_(current_level|packages|dirty|map|asset|loaded_asset|directory|level)|EditorAssetLibrary\.save|"
                  r"save_dirty_packages|\.save\(|SavePackage|editor_save|save_map", re.I)
OURS = sorted(HERE.glob("beam_texture_bench*.py"))
bench_src = (HERE / "beam_texture_bench.py").read_text(encoding="utf-8")
sheet_src = (HERE / "beam_texture_bench_contact_sheet.py").read_text(encoding="utf-8")
unreal_src = "".join(x.read_text(encoding="utf-8") for x in OURS if x.name != "beam_texture_bench_contact_sheet.py")
check("+ no save call in beam_texture_bench.py or its run scripts (%d files)" % (len(OURS) - 1),
      len(OURS) >= 5 and not SAVE.search(unreal_src))
check("- control: the scanner flags an injected save", bool(SAVE.search(unreal_src + "\nunreal.EditorAssetLibrary.save_asset(p)\n")))
check("+ the contact sheet only saves its own PNG and never imports unreal",
      [m.group(0) for m in SAVE.finditer(sheet_src)] == [".save("] and "import unreal" not in sheet_src)
SPAWN = re.compile(r"spawn_actor|begin_deferred|finish_spawning|SpawnActor|\.spawn\w*\(|destroy\w*\(|EditorActorSubsystem|"
                   r"EditorLevelLibrary|create_asset|create_material", re.I)
pie_region = bench_src.split("# ---- PIE ADAPTER BEGIN", 1)[1].split("# ---- PIE ADAPTER END", 1)[0]
engine_free = "".join(inspect.getsource(x) for x in (bt.BeamBench, bt.BeamMachine, bt.restore_from_record, bt.restore_all,
                                                     bt.arm))
check("+ PIE adapter and the engine-free bench / machine / restore / arm contain no spawn / destroy / asset creation",
      len(pie_region) > 5000 and not SPAWN.search(pie_region.split("\n", 1)[1]) and not SPAWN.search(engine_free))
check("- control: the scanner flags an injected PIE spawn",
      bool(SPAWN.search(pie_region + "\n        a = actor_sub.spawn_actor_from_class(cls, loc)\n")))
check("+ create-only materials: no expression or asset is ever deleted, no existing material is loaded for editing",
      not re.search(r"delete_material_expression|delete_all_material_expressions|delete_asset|delete_loaded_asset",
                    bench_src) and "ASSET_EXISTS" in bench_src)
check("+ no Unreal import at module level (UE objects only in closures)",
      not re.search(r"^import unreal", bench_src, re.M) and not re.search(r"^from unreal", bench_src, re.M))
check("+ no exposure write: the bench never touches post-process settings (show exposure)",
      not re.search(r"set_editor_property\(\"settings\"|post_process_settings\"\s*,", bench_src))

# ======================= contact sheet =======================
import beam_texture_bench_contact_sheet as cs  # noqa: E402
sheet = cs.build_sheet(r1["run_dir"], thumb_w=160)
tiles = {(t["position"], t["variant"]): t for t in sheet["tiles"]}
check("+ contact sheet: 3 rows x 5 tiles, a pick per tile, no missing, PNG on disk",
      len(sheet["tiles"]) == 15 and all(t["pick"] for t in sheet["tiles"]) and not sheet["missing"]
      and pathlib.Path(sheet["sheet"]).is_file())
check("+ metric end to end: A (bars + shadows), B (noise box) and ALL read TEXTURED at every position",
      all(tiles[(pn, v)]["verdict"]["textured"] is True for pn in ("a450", "a250", "a050") for v in ("A", "B", "ALL")))
check("- control: base (vs itself) and D (finer grid, no new structure in the fake) are NOT textured",
      all(tiles[(pn, v)]["verdict"]["textured"] is False for pn in ("a450", "a250", "a050") for v in ("base", "D")))
check("+ the sheet carries frame times and the occlusion note on A tiles",
      all(tiles[(pn, "A")]["timing"]["n"] > 0 and any("occl clear" in n for n in tiles[(pn, "A")]["notes"])
          for pn in ("a450", "a250", "a050")))
for pth in pathlib.Path(r1["run_dir"]).glob("a050/B_*.png"):
    pth.unlink()
check("- control: deleting a shot's stills makes that tile MISSING", cs.build_sheet(r1["run_dir"], thumb_w=160)["missing"] == ["a050/B"])

failed = [n for n, ok in RESULTS if not ok]
print("\nBEAM_TEXTURE_BENCH_HARNESS %d/%d %s" % (len(RESULTS) - len(failed), len(RESULTS), "OK" if not failed else "FAILED"))
sys.exit(1 if failed else 0)
