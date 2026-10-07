"""Offline harness for p04_rain_pie_bench.py (no Unreal). A fake PIE world renders synthetic PNGs from its state
(spawned systems, show flags), so the whole machine runs to the verdict with a fake clock. Every verdict has its
controls: rain that renders / does not / a frozen capture (positive control must fail) / a noisy scene (negative
control must fail) / a difference that survives ShowFlag.Particles 0 (attribution must fail). Plus arm refusals,
mid-run PIE loss, cleanup, pure maths and source guards.
Run: python Saved/CodexConductor/Effects_20261007/test_p04_rain_pie_bench_offline.py"""
import ast
import json
import pathlib
import random
import re
import shutil
import struct
import sys
import tempfile
import zlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p04_rain_pie_bench as B  # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def raises(fn, token=None):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        return token is None or token in str(exc)
    return False


def write_png(path, w, h, pixel):
    raw = b"".join(b"\x00" + bytes(v for x in range(w) for v in pixel(x, y)) for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_bytes(data)


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Store:
    pass


class FakePIE:
    """Renders: base gradient; Lighting 0 -> +70; rain (if rain_renders and Particles 1, or rain_leaks) -> streaks;
    alt (if alt_renders and Particles 1) -> a blob; frozen -> every shot is the base image; noise -> random jitter."""

    def __init__(self, rain_renders=True, alt_renders=True, frozen=False, noise=0, rain_leaks=False,
                 die_after=None, bad_template=False):
        self.rain_renders, self.alt_renders, self.frozen, self.noise = rain_renders, alt_renders, frozen, noise
        self.rain_leaks, self.die_after, self.bad_template = rain_leaks, die_after, bad_template
        self.flags = {"Particles": 1, "Lighting": 1}
        self.live = {}
        self.n = 0
        self.frame = 500
        self.logs, self.errors, self.consoles = [], [], []
        self.calls = 0
        self.rng = random.Random(7)

    def world_kind(self):
        self.calls += 1
        if self.die_after is not None and self.calls > self.die_after:
            return None
        return "game"

    def world_name(self):
        return "/Game/UEDPIE_0_L_InfinityStage_V1VerticalSlice"

    def log(self, m):
        self.logs.append(m)

    def log_error(self, m):
        self.errors.append(m)

    def census(self):
        return {"maps": ["/Game/Maps/UEDPIE_0_L"], "content": []}

    def passage_segment(self, label):
        assert label == "Passage 4", label
        return 1000, 1000 + 24000 * 60

    def transport_scrub(self, frame):
        self.frame = int(frame)
        return "EInfinityTransportResult.SUCCEEDED"

    def transport_pause(self):
        pass

    def transport_frame(self):
        return self.frame

    def is_playing(self):
        return False

    def camera_pose(self, aspect, fov):
        return {"loc": [self.frame / 100.0, 240000.0, 180.0], "rot": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                "fov_deg": 37.5, "aspect": aspect}

    def _render(self, path, w, h):
        kinds = set(self.live.values())
        lit = 0 if self.frozen or self.flags["Lighting"] else 70
        rain = not self.frozen and "rain" in kinds and ((self.rain_renders and self.flags["Particles"]) or self.rain_leaks)
        alt = not self.frozen and "alt" in kinds and self.alt_renders and self.flags["Particles"]
        jitter = [self.rng.randint(-self.noise, self.noise) if self.noise else 0 for _ in range(w * h)]

        def px(x, y):
            v = 40 + (x * 60) // w + lit + jitter[y * w + x]
            if rain and x % 3 == 0:
                v += 90
            if alt and abs(x - w // 2) < w // 6 and y > h // 2:
                v += 60
            v = max(0, min(255, v))
            return (v, v, v)
        write_png(path, w, h, px)

    def console(self, cmd):
        self.consoles.append(cmd)
        m = re.match(r"ShowFlag\.(\w+) (\d)", cmd)
        if m:
            self.flags[m.group(1)] = int(m.group(2))
            return
        m = re.match(r'HighResShot (\d+)x(\d+) filename="(.+)"', cmd)
        if m:
            self._render(m.group(3), int(m.group(1)), int(m.group(2)))

    def spawn_emitter(self, template, loc, yaw, scale):
        self.n += 1
        kind = "rain" if template.endswith("Rain2") else "alt"
        path = "/Game/UEDPIE_0_L.L:PersistentLevel.WorldSettings.PSC_%d" % self.n
        self.live[path] = kind
        self.templates = getattr(self, "templates", {})
        self.templates[path] = template if not self.bad_template else "/Game/Wrong"
        return path

    def readback(self, path):
        if path not in self.live:
            return {"valid": False}
        return {"valid": True, "active": True, "template": self.templates[path]}

    def is_live(self, path):
        return path in self.live

    def destroy(self, path):
        self.live.pop(path, None)
        return True


SMALL = {"resolution": [48, 27], "probe_resolution": [24, 14], "file_min_bytes": 50, "file_stable_ticks": 2}
ARGS = {"mode": "RUN", "confirm": B.CONFIRM, "params": SMALL}


def drive(fake, args=ARGS, max_ticks=20000):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="rainpie_"))
    clock = Clock()
    run = B.arm(fake, json.loads(json.dumps(args)), out_root=tmp / "out", owner_path=tmp / "owner.json",
                ledger_path=tmp / "ledger.json", register=lambda f: "H1", unregister=lambda h: None,
                store=Store(), clock=clock)
    for _ in range(max_ticks):
        if run.get("finished"):
            break
        clock.t += 0.25
        run["_tick"]()
    ledger = json.loads((tmp / "ledger.json").read_text(encoding="utf-8"))
    manifest = json.loads((pathlib.Path(run["run_dir"]) / B.MANIFEST_NAME).read_text(encoding="utf-8"))
    shutil.rmtree(tmp, ignore_errors=True)
    return run, ledger, manifest


# ---------------------------------------------------------------------------- full runs with controls
fake = FakePIE()
run, ledger, man = drive(fake)
v = man["analysis"]["verdict"]
check("run+: rain + alt render -> passed, RENDERS / RENDERS, 3 valid stills",
      man["status"] == "passed" and v["rain"] == "RENDERS" and v["alt"] == "RENDERS" and v["valid_stills"] == 3)
check("run+: 18 full stills captured (3 stills x 6 captures)",
      sum(1 for s in man["stills"] for c in s["captures"].values() if c["phase"] == "captured") == 18)
check("run+: nothing left alive, ledger empty", not fake.live and ledger["live"] == [])
check("run+: show flags back to 1", fake.flags == {"Particles": 1, "Lighting": 1})
check("run+: OK marker carries the verdict", any(m.startswith("P04RAINPIE_OK|") and "rain=RENDERS" in m for m in fake.logs))
check("run+: luma delta reported per system", all("rain" in r["luma_delta"] for r in man["analysis"]["rows"]))
check("run+: Particles 0 hid the rain (attributable)", all(r["rain_attributable"] for r in man["analysis"]["rows"]))
check("run+: screen messages restored", "EnableAllScreenMessages" in fake.consoles)
check("run+: Master scrubbed back to the original frame", man["restore_scrub"]["frame"] == man["original_frame"])
check("run+: every spawn read back with its template", all(sp["readback"]["template"] == SMALL.get(
    "rain_template", B.DEFAULTS["rain_template"]) for s in man["stills"] for sp in s["captures"]["rain"]["spawned"]))

fake = FakePIE(rain_renders=False)
run, ledger, man = drive(fake)
v = man["analysis"]["verdict"]
check("run-: Rain2 invisible, Humo_Par visible -> rain NOT_SEEN, alt RENDERS", v["rain"] == "NOT_SEEN" and v["alt"] == "RENDERS")

fake = FakePIE(rain_renders=False, alt_renders=False)
run, ledger, man = drive(fake)
v = man["analysis"]["verdict"]
check("run-: Cascade invisible -> NOT_SEEN / NOT_SEEN with valid controls",
      v["rain"] == "NOT_SEEN" and v["alt"] == "NOT_SEEN" and v["valid_stills"] == 3)

fake = FakePIE(frozen=True)
run, ledger, man = drive(fake)
v = man["analysis"]["verdict"]
check("control+: frozen capture fails the positive control -> INVALID, not NOT_SEEN",
      v["rain"] == "INVALID" and v["valid_stills"] == 0
      and all(any("positive_control_failed" in p for p in r["problems"]) for r in man["analysis"]["rows"]))

fake = FakePIE(noise=30)
run, ledger, man = drive(fake)
v = man["analysis"]["verdict"]
check("control-: a non-static scene fails the noise floor -> INVALID",
      v["rain"] == "INVALID" and all(any("scene_not_static" in p for p in r["problems"]) for r in man["analysis"]["rows"]))

fake = FakePIE(rain_leaks=True)
run, ledger, man = drive(fake)
v = man["analysis"]["verdict"]
check("control-: a difference that survives ShowFlag.Particles 0 is not called rain -> UNCLEAR",
      v["rain"] == "UNCLEAR" and v["alt"] == "RENDERS")

fake = FakePIE(die_after=60)
run, ledger, man = drive(fake)
check("pie-loss: PIE gone mid-run -> FAILED pie_ended, finish still ran",
      man["status"] == "failed" and any("reason=pie_ended" in e for e in fake.errors) and run.get("finished"))

fake = FakePIE(bad_template=True)
run, ledger, man = drive(fake)
check("spawn-: wrong template on read-back -> FAILED, nothing left alive",
      man["status"] == "failed" and not fake.live and ledger["live"] == [])

# ---------------------------------------------------------------------------- arm refusals
tmp = pathlib.Path(tempfile.mkdtemp(prefix="rainpie_arm_"))


def arm_with(args=ARGS, fake=None, store=None, owner=False, ledger_live=False):
    fake = fake or FakePIE()
    owner_path, ledger_path = tmp / "owner.json", tmp / "ledger.json"
    owner_path.write_text(json.dumps({"active": owner}), encoding="utf-8")
    ledger_path.write_text(json.dumps({"run": "x", "live": [{"kind": "rain", "path": "p"}] if ledger_live else []}),
                           encoding="utf-8")
    return B.arm(fake, json.loads(json.dumps(args)), out_root=tmp / "out", owner_path=owner_path,
                 ledger_path=ledger_path, store=store or Store(), clock=Clock())


check("arm-: no confirm", raises(lambda: arm_with(dict(ARGS, confirm=None)), "confirm_missing"))
check("arm-: ledger not empty (TEARDOWN first)", raises(lambda: arm_with(ledger_live=True), "ledger_not_empty"))
check("arm-: active PIE owner file", raises(lambda: arm_with(owner=True), "pie_owner_active"))
st = Store()
st.PUSS_PASSAGE_STILLS_HANDLE = 1
check("arm-: another PUSS tick armed", raises(lambda: arm_with(store=st), "tick_armed"))
check("arm-: no PIE", raises(lambda: arm_with(fake=FakePIE(die_after=0)), "no_pie"))
check("arm-: controls removed", raises(lambda: arm_with(dict(ARGS, params=dict(SMALL, captures=["off_a", "rain"]))),
                                       "controls_removed"))
check("arm-: unknown param", raises(lambda: arm_with(dict(ARGS, params={"rain_count": 4})), "bad_param"))
check("arm+: a clean arm returns a run", arm_with()["status"] == "capturing")
shutil.rmtree(tmp, ignore_errors=True)

# teardown
tmp = pathlib.Path(tempfile.mkdtemp(prefix="rainpie_td_"))
fk = FakePIE()
p1 = fk.spawn_emitter("/Game/Japanese_Alley/VFX/Rain2", [0, 0, 0], 0, 1)
(tmp / "l.json").write_text(json.dumps({"run": "r", "live": [{"kind": "rain", "path": p1}]}), encoding="utf-8")
fk.flags["Particles"] = 0
check("teardown+: destroys ledger entries, restores flags, empties ledger",
      B.teardown(fk, ledger_path=tmp / "l.json") and not fk.live and fk.flags["Particles"] == 1
      and json.loads((tmp / "l.json").read_text())["live"] == [])
check("teardown-: no PIE", raises(lambda: B.teardown(FakePIE(die_after=0), ledger_path=tmp / "l.json"), "no_pie"))
shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------------------- pure
check("transition: rain->off destroys then restores the flag",
      B.transition({"spawn": "rain", "flags": {"Particles": 0}}, B.OFF_STATE) == [("destroy", "rain"), ("flag", "Particles", 1)])
check("transition: off->alt spawns only", B.transition(B.OFF_STATE, B.want_state("alt")) == [("spawn", "alt")])
check("transition: rain->rain_noparticles keeps the emitters", B.transition(B.want_state("rain"), B.want_state(
    "rain_noparticles")) == [("flag", "Particles", 0)])
pose0 = {"loc": [0.0, 0.0, 180.0], "rot": {"yaw": 0.0, "pitch": 0.0}, "fov_deg": 40.0}
pose90 = {"loc": [0.0, 0.0, 180.0], "rot": {"yaw": 90.0, "pitch": 0.0}, "fov_deg": 40.0}
pt = B.world_points(pose0, [[600.0, 100.0, 250.0]])[0]
check("frame: yaw 0 -> forward +X, right +Y", [round(x, 6) for x in pt] == [600.0, 100.0, 430.0])
pt = B.world_points(pose90, [[600.0, 100.0, 0.0]])[0]
check("frame: yaw 90 -> forward +Y, right -X", [round(x, 6) for x in pt] == [-100.0, 600.0, 180.0])
check("view+: a point dead ahead", B.in_view(pose0, [1000.0, 0.0, 180.0], 16 / 9))
check("view-: a point behind", not B.in_view(pose0, [-1000.0, 0.0, 180.0], 16 / 9))
check("view-: a point far off to the side", not B.in_view(pose0, [1000.0, 2000.0, 180.0], 16 / 9))
check("census: UEDPIE packages ignored, real ones kept", B.census_filtered(
    {"maps": ["/Game/UEDPIE_0_L", "/Game/Maps/L"], "content": []}) == {"maps": ["/Game/Maps/L"], "content": []})
tmp = pathlib.Path(tempfile.mkdtemp(prefix="rainpie_png_"))
write_png(tmp / "a.png", 8, 4, lambda x, y: (10, 20, 30))
write_png(tmp / "b.png", 8, 4, lambda x, y: (12, 20, 30))
check("mad: (2,0,0) per pixel -> 2/3", abs(B.mean_abs_diff(tmp / "a.png", tmp / "b.png") - 2.0 / 3.0) < 1e-9)
check("mad -control: identical -> 0", B.mean_abs_diff(tmp / "a.png", tmp / "a.png") == 0.0)
shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------------------- source guards
src = (HERE / "p04_rain_pie_bench.py").read_text(encoding="utf-8")
tree = ast.parse(src)
names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
    n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
banned = {"editor_request_end_play", "request_end_play", "end_play", "editor_request_begin_play", "quit_editor",
          "save_asset", "save_current_level", "save_dirty_packages", "save_packages", "load_level", "load_map",
          "spawn_actor", "spawn_actor_from_class", "begin_deferred_actor_spawn_from_class", "delete_asset"}
check("guard: no PIE begin/end, quit, save, level load, actor spawn or asset delete", not (banned & names))
check("guard -control: the scan sees the emitter spawn", "spawn_emitter_at_location" in names)
check("guard: no Unreal call at module level (crash memory)",
      not [n for n in tree.body if isinstance(n, (ast.Assign, ast.Expr)) and "unreal." in ast.unparse(n)])
check("guard: ledger intent written before the spawn call", src.index("self._ledger_write(live + [intent])")
      < src.index("path = self.a.spawn_emitter("))

failed = [n for n, ok in RESULTS if not ok]
print("\n%d/%d passed" % (len(RESULTS) - len(failed), len(RESULTS)))
sys.exit(1 if failed else 0)
