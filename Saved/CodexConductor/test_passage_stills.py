"""Offline harness for passage_stills.py (no Unreal). Each property has a + case and a
- control that must FAIL, so the checks are shown able to fail.
Run: python Saved/CodexConductor/test_passage_stills.py"""
import io
import json
import pathlib
import re
import runpy
import struct
import sys
import tempfile
import tokenize
import types
import zlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import passage_stills as ps  # noqa: E402

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
    raw = b"".join(b"\x00" + bytes([grey, grey, grey]) * w for _ in range(h))
    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body) & 0xFFFFFFFF)
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    pathlib.Path(path).write_bytes(data)
    return True


tmp = pathlib.Path(tempfile.mkdtemp(prefix="pstills_"))
SEG = (30_000_000, 30_000_000 + 90 * ps.TICKS_PER_SECOND)      # a 90 s Passage


class Store:
    pass


class Fake:
    """PIE adapter fake: transport, camera, census, and a HighResShot that writes real PNGs
    (probes small, stills large) whose luma follows `self.luma(now)`."""

    def __init__(self, clock, world="game", census=None, luma=None, scrub_result="<InfinityTransportResult.SUCCEEDED: 0>",
                 drift_after=None, write_stills=True, dirty_on_scrub=False, pie_ends_at=None, still_delay=0,
                 repose_luma=None):
        self.clock, self.world = clock, world
        self._census = census or {"maps": ["/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"], "content": []}
        self.luma = luma or (lambda t: 60.0)
        self.scrub_result = scrub_result
        self.frame, self.playing = 29_000_000, True
        self.drift_after, self.write_stills, self.dirty_on_scrub = drift_after, write_stills, dirty_on_scrub
        self.pie_ends_at, self.still_delay, self.repose_luma = pie_ends_at, still_delay, repose_luma
        self.logs, self.errors, self.commands, self.scrubs, self.events = [], [], [], [], []
        self.ok_seen_with_files = None
        self.pending_stills = []

    def world_kind(self):
        if self.pie_ends_at is not None and self.clock[0] >= self.pie_ends_at:
            return None
        return "game" if self.world == "game" else None

    def world_name(self): return "/Game/InfinityStage/Dev/Maps/UEDPIE_0_L_InfinityStage_V1VerticalSlice"
    def log(self, m):
        self.logs.append(m)
        if m.startswith("PASSAGE_STILLS_OK|"):
            run_dir = pathlib.Path(m.split("|dir=")[1])
            pngs = sorted(run_dir.glob("[0-9][0-9]_f*.png"))
            self.ok_seen_with_files = len(pngs)
    def log_error(self, m): self.errors.append(m)
    def census(self): return json.loads(json.dumps(self._census))
    def passage_segment(self, label):
        if label != "Passage 5":
            raise ps.StillsRefused("no_segment", label)
        return SEG

    def transport_scrub(self, f):
        self.scrubs.append(int(f))
        self.events.append(("scrub", self.clock[0], int(f)))
        if "SUCCEEDED" not in self.scrub_result:
            return self.scrub_result
        self.frame, self.playing = int(f), False
        if self.dirty_on_scrub and "/Game/Dirtied" not in self._census["content"]:
            self._census["content"].append("/Game/Dirtied")
        return self.scrub_result

    def transport_pause(self): self.playing = False
    def transport_frame(self):
        if self.drift_after is not None and len(self.scrubs) >= self.drift_after:
            return self.frame + 2400
        return self.frame
    def is_playing(self): return self.playing

    def camera_pose(self, aspect, fov):
        x = (self.frame - SEG[0]) / ps.TICKS_PER_SECOND * 58.0
        return {"loc": [x, 240000.0, 180.0], "rot": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0}, "fov_deg": 37.5,
                "fov_read": 37.5, "aspect": aspect}

    def console(self, cmd):
        if self.world_kind() != "game":
            raise ps.StillsRefused("pie_ended", "console")
        self.commands.append(cmd)
        self.events.append(("console", self.clock[0], cmd))
        m = re.search(r'filename="([^"]+)"', cmd)
        if not m:
            return
        path = m.group(1)
        value = self.repose_luma if self.repose_luma is not None and len(self.scrubs) >= 2 else self.luma(self.clock[0])
        grey = max(0, min(255, int(round(value))))
        if "_probes" in path:
            write_png(path, 8, 6, grey)
        elif self.write_stills:
            self.pending_stills.append((self.clock[0] + self.still_delay, path, grey))

    def advance(self):
        for row in list(self.pending_stills):
            if self.clock[0] >= row[0]:
                write_png(row[1], 160, 90, row[2])     # > file_min_bytes? see below
                self.pending_stills.remove(row)


def run(fractions=(0.1, 0.5, 0.9), params=None, dt=1.0 / 30.0, max_t=900.0, **kw):
    clock = [0.0]
    f = Fake(clock, **kw)
    store = Store()
    reg = {}
    out_root = tmp / ("run_%d" % len(RESULTS))
    owner = tmp / "owner_none.json"
    p = {"file_min_bytes": 50}
    p.update(params or {})
    r = ps.arm(f, "P05", list(fractions), "t", p, out_root=out_root, owner_path=owner,
               register=lambda fn: reg.setdefault("fn", fn) and "H", unregister=lambda h: reg.setdefault("unreg", h),
               store=store, clock=lambda: clock[0])
    while not r.get("finished") and clock[0] < max_t:
        clock[0] += dt
        f.advance()
        reg["fn"](dt)
    return r, f, store, reg


# ---- passage + fraction maths
check("+ passage_label: P05 -> Passage 5, p1 -> Passage 1", ps.passage_label("P05") == (5, "Passage 5")
      and ps.passage_label("p1") == (1, "Passage 1"))
check("- control: X05, P, P00, P123 refused", all(raises(lambda v=v: ps.passage_label(v), "bad_passage")
                                              for v in ("X05", "P", "P00", "P123")))
check("+ default fractions are 0.1..0.9", ps.validate_fractions(None) == [0.1, 0.3, 0.5, 0.7, 0.9])
check("- control: empty, >1, <0, bool, string, NaN, duplicates refused",
      all(raises(lambda v=v: ps.validate_fractions(v), "bad_fractions")
          for v in ([], [1.2], [-0.1], [True], "0.5", [float("nan")], [0.5, 0.5])))
s, e = SEG
check("+ fraction_to_frame: 0 -> start, 0.5 -> exact middle, 0.25 -> quarter",
      ps.fraction_to_frame(s, e, 0.0) == s and ps.fraction_to_frame(s, e, 0.5) == s + 45 * 24000
      and ps.fraction_to_frame(s, e, 0.25) == s + int(22.5 * 24000))
check("+ fraction 1.0 lands one display frame (1000 ticks) before the segment end",
      ps.fraction_to_frame(s, e, 1.0) == e - 1000 and ps.END_GUARD_TICKS == 1000)
check("- control: an unclamped 1.0 would be the end frame (the REST pose), which the clamp avoids",
      s + int(round(1.0 * (e - s))) == e and ps.fraction_to_frame(s, e, 1.0) != e)
check("- control: a segment shorter than one display frame is refused",
      raises(lambda: ps.fraction_to_frame(0, 900, 0.5), "segment_too_short"))
plan = ps.plan_stills(s, e, [0.1, 0.9], tmp)
check("+ plan_stills: paths, seconds into passage", plan[0]["path"].endswith("00_f100.png")
      and abs(plan[1]["seconds_into_passage"] - 81.0) < 1e-9)
check("- control: two fractions on the same frame refused",
      raises(lambda: ps.plan_stills(0, 2000, [0.6, 0.7], tmp), "fractions_collide"))

# ---- luma + settle copies agree with look_bench's
import look_bench as lb  # noqa: E402
write_png(tmp / "g.png", 9, 7, 77)
check("+ png_luma parity with look_bench.png_luma (grey 77)",
      abs(ps.png_luma(tmp / "g.png") - 77.0) < 1e-9 and abs(ps.png_luma(tmp / "g.png") - lb.png_luma(tmp / "g.png")) < 1e-12)
(tmp / "half.png").write_bytes((tmp / "g.png").read_bytes()[:30])
check("- control: half-written PNG raises", raises(lambda: ps.png_luma(tmp / "half.png"), "PASSAGE_STILLS_PNG"))
P_ = dict(ps.DEFAULTS)
cases = [([[0.5 * i, 100.0] for i in range(6)], 5.0), ([[0.5 * i, 100.0] for i in range(6)], 3.0),
         ([[0.5 * i, 100.0 + 8 * i] for i in range(8)], 6.0), ([[0.5 * i, 100.0 + 8 * i] for i in range(8)], 21.0)]
got = [ps.settle_decision(c, t, P_) for c, t in cases]
check("+ settle_decision parity with look_bench (stable, wait, wait, timeout)",
      got == ["stable", "wait", "wait", "timeout"] and got == [lb.settle_decision(c, t, lb.DEFAULTS) for c, t in cases])

# ---- refusal without PIE
clock0 = [0.0]
nf = Fake(clock0, world=None)
st0 = Store()
regd = {}
out0 = tmp / "nopie"
check("+ refusal without PIE: raises PASSAGE_STILLS_FAILED|run=...|reason=no_pie",
      raises(lambda: ps.arm(nf, "P05", [0.5], None, None, out_root=out0, owner_path=tmp / "x.json",
                            register=lambda fn: regd.setdefault("fn", fn), store=st0), "reason=no_pie"))
check("+ no-PIE refusal: FAILED marker logged with the run id, START before it, no run dir, no tick, no console",
      nf.errors and re.match(r"PASSAGE_STILLS_FAILED\|run=PSTILLS-P05-\d{8}-\d{6}\|reason=no_pie", nf.errors[0])
      and nf.logs[0].startswith("PASSAGE_STILLS_START|run=") and not out0.exists() and not regd and not nf.commands)
r_ok, f_ok, st_ok, reg_ok = run()
check("- control: the same arm with PIE present runs to OK", any(m.startswith("PASSAGE_STILLS_OK|") for m in f_ok.logs))

# ---- other refusals at arm time
st_busy = Store()
st_busy.PUSS_LOOK_BENCH_HANDLE = "h"
check("+ refused while another PUSS_*_HANDLE tick is armed",
      raises(lambda: ps.arm(Fake([0.0]), "P05", [0.5], out_root=tmp / "busy", owner_path=tmp / "x.json",
                            store=st_busy), "tick_armed"))
(tmp / "owner_on.json").write_text(json.dumps({"active": True}), encoding="utf-8")
check("+ refused while pie_recording_owner.json is active",
      raises(lambda: ps.arm(Fake([0.0]), "P05", [0.5], out_root=tmp / "own", owner_path=tmp / "owner_on.json",
                            store=Store()), "pie_owner_active"))
(tmp / "owner_off.json").write_text(json.dumps({"active": False}), encoding="utf-8")
check("- control: an inactive owner file and no handles arm fine",
      ps.arm(Fake([0.0]), "P05", [0.5], out_root=tmp / "own2", owner_path=tmp / "owner_off.json",
             store=Store())["status"] == "capturing")
check("+ wrong passage refused (no runtime segment), with run id",
      raises(lambda: ps.arm(Fake([0.0]), "P04", [0.5], out_root=tmp / "p4", owner_path=tmp / "x.json",
                            store=Store()), "|reason=no_segment"))

class Boom(Fake):
    def census(self): raise ValueError("unreal said no")
check("+ an unexpected Unreal error while arming becomes reason=arm_error (not a bare traceback)",
      raises(lambda: ps.arm(Boom([0.0]), "P05", [0.5], out_root=tmp / "boom", owner_path=tmp / "x.json",
                            store=Store()), "reason=arm_error"))

# ---- the good run
man = json.loads((pathlib.Path(r_ok["run_dir"]) / ps.MANIFEST_NAME).read_text(encoding="utf-8"))
frames = [m for m in f_ok.logs if m.startswith("PASSAGE_STILLS_FRAME|")]
check("+ good run: n FRAME markers with run id and i=0..n-1, OK marker n=3 with dir",
      [re.search(r"\|i=(\d+)\|", m).group(1) for m in frames] == ["0", "1", "2"]
      and all(("run=%s|" % r_ok["run_id"]) in m for m in frames)
      and any(m == "PASSAGE_STILLS_OK|run=%s|n=3|dir=%s" % (r_ok["run_id"], r_ok["run_dir"]) for m in f_ok.logs))
check("+ OK was logged only when all 3 still files already existed on disk", f_ok.ok_seen_with_files == 3)
check("+ manifest: passed, each still has pose, master frame == target, settle stable, luma ~60, bytes",
      man["status"] == "passed" and all(
          st["master_frame_at_capture"] == st["target_frame"] and st["pose"]["loc"][1] == 240000.0
          and st["settle"]["verdict"] == "stable" and abs(st["luma"] - 60.0) < 1.0 and st["bytes"] > 50
          and st["exists"] for st in man["stills"]))
check("+ manifest targets are the fraction maths (0.1/0.5/0.9 of the segment)",
      [st["target_frame"] for st in man["stills"]] == [ps.fraction_to_frame(s, e, x) for x in (0.1, 0.5, 0.9)])
check("+ every still was scrubbed twice (jump + re-pose) before capture; original frame restored at the end",
      f_ok.scrubs[:-1] == [t for st in man["stills"] for t in (st["target_frame"],) * 2]
      and f_ok.scrubs[-1] == 29_000_000 and man["restore_scrub"]["landed"] == 29_000_000 and man["was_playing"])
check("+ screen messages disabled first and restored last; tick unregistered; handle removed",
      f_ok.commands[0] == "DisableAllScreenMessages" and f_ok.commands[-1] == "EnableAllScreenMessages"
      and reg_ok.get("unreg") == "H" and not hasattr(st_ok, ps.HANDLE_NAME) and man["screen_messages_restored"])
check("+ census before == after recorded (dirty MAP from conductor_pie_begin allowed when unchanged)",
      man["census_before"] == man["census_after"] and man["census_before"]["maps"])
check("+ stills are 1600x900 HighResShots without exposure override; probes 256x144",
      sum(1 for c in f_ok.commands if c.startswith("HighResShot 1600x900 ")) == 3
      and all(c.startswith(("HighResShot 256x144", "HighResShot 1600x900", "DisableAll", "EnableAll"))
              for c in f_ok.commands))
first_still = next(i for i, c in enumerate(f_ok.commands) if c.startswith("HighResShot 1600x900"))
check("+ at least settle_window probes precede the first still (settle gate actually ran)",
      sum(1 for c in f_ok.commands[:first_still] if "256x144" in c) >= ps.DEFAULTS["settle_window"])
event_names = [(kind, "probe" if "256x144" in str(value) else "still" if "1600x900" in str(value) else "other")
               for kind, _time, value in f_ok.events]
second_scrub = [i for i, row in enumerate(event_names) if row[0] == "scrub"][1]
first_full = next(i for i, row in enumerate(event_names) if row == ("console", "still"))
check("+ corrected order is PIE scrub, settle probes, final re-pose, decoded probe, full still",
      any(row == ("console", "probe") for row in event_names[:second_scrub])
      and any(row == ("console", "probe") for row in event_names[second_scrub + 1:first_full]))
r_repose, _, _, _ = run(fractions=(0.5,), repose_luma=95.0)
check("- control: post-re-pose decoded frame changing from settled luma marks capture FAILED",
      r_repose["status"] == "failed" and any(g.startswith("repose_drift") for g in r_repose["gate_failures"]))

# ---- census-dirty refusal
r_d, f_d, _s, _r = run(dirty_on_scrub=True)
check("+ census changed during the run -> FAILED reason census, no OK",
      r_d["status"] == "failed" and not any(m.startswith("PASSAGE_STILLS_OK") for m in f_d.logs)
      and any("reason=census" in m for m in f_d.errors))
check("- control: same run without the dirtying scrub passes", r_ok["status"] == "passed")

# ---- success only after files exist
r_nf, f_nf, _s, _r = run(write_stills=False, params={"file_timeout_s": 3.0})
check("+ stills never written -> capture_timeout, FAILED, no OK, missing-file problem listed",
      r_nf["status"] == "failed" and not any(m.startswith("PASSAGE_STILLS_OK") for m in f_nf.logs)
      and any("capture_timeout" in m for m in f_nf.errors) and any("missing" in p for p in r_nf["problems"]))
r_sl, f_sl, _s, _r = run(still_delay=2.0)
check("- control: a still written 2 s late (async HighResShot) still passes", r_sl["status"] == "passed")


class Vanish(Fake):
    def log(self, m):
        super().log(m)
        if m.startswith("PASSAGE_STILLS_FRAME|") and "|i=2|" in m:
            pathlib.Path(m.split("|path=")[1]).unlink()


clock_v = [0.0]
fv = Vanish(clock_v)
regv = {}
rv = ps.arm(fv, "P05", [0.1, 0.5, 0.9], None, {"file_min_bytes": 50}, out_root=tmp / "vanish",
            owner_path=tmp / "x.json", register=lambda fn: regv.setdefault("fn", fn) and "H",
            unregister=lambda h: None, store=Store(), clock=lambda: clock_v[0])
while not rv.get("finished") and clock_v[0] < 900:
    clock_v[0] += 1 / 30.0
    fv.advance()
    regv["fn"](1 / 30.0)
check("+ a still deleted after its FRAME marker -> final existence check FAILS the run (no OK)",
      rv["status"] == "failed" and not any(m.startswith("PASSAGE_STILLS_OK") for m in fv.logs)
      and any("missing" in p for p in rv["problems"]))

# ---- settle gate
r_wob, f_wob, _s, _r = run(fractions=(0.5,), luma=lambda t: 60.0 + 40.0 * ((int(t * 2)) % 2))
check("+ a picture that never settles -> settle gate failure, FAILED, still captured and listed",
      r_wob["status"] == "failed" and r_wob["stills"][0]["settle"]["verdict"] == "timeout"
      and any(g.startswith("settle") for g in r_wob["gate_failures"]) and r_wob["stills"][0]["exists"])
r_ramp, f_ramp, _s, _r = run(fractions=(0.5,), luma=lambda t: min(120.0, 20.0 + 25.0 * t))
check("- control: a picture that ramps then holds (auto exposure) settles and passes",
      r_ramp["status"] == "passed" and r_ramp["stills"][0]["settle"]["seconds"] >= 4.0
      and abs(r_ramp["stills"][0]["luma"] - 120.0) < 1.0)

# ---- post-capture drift gate
def late_change(t):                  # settles ~4.1 s, still issued then, file lands 2 s later
    return 60.0 if t < 5.0 else 140.0
r_pc, f_pc, _s, _r = run(fractions=(0.5,), luma=late_change, still_delay=2.0)
check("+ picture changes between settle and the post-capture probe -> post_capture_drift gate FAILS",
      r_pc["status"] == "failed" and any(g.startswith("post_capture_drift") for g in r_pc["gate_failures"])
      and r_pc["stills"][0]["settle"]["verdict"] == "stable")

# ---- frame drift gate (stale / moving transport)
r_fd, f_fd, _s, _r = run(fractions=(0.5,), drift_after=2)
check("+ transport not on target at capture -> frame gate FAILS", r_fd["status"] == "failed"
      and any(g.startswith("frame") for g in r_fd["gate_failures"]))

# ---- scrub refused
r_sr, f_sr, _s, _r = run(scrub_result="<InfinityTransportResult.UNSAFE_EXTERNAL_CLOCK: 4>")
check("+ scrub refused (performance interlock) -> FAILED reason scrub_refused, no still requested",
      r_sr["status"] == "failed" and any("reason=scrub_refused" in m for m in f_sr.errors)
      and not any("1600x900" in c for c in f_sr.commands) and f_sr.commands[-1] == "EnableAllScreenMessages")

# ---- PIE ends mid-run
r_pe, f_pe, _s, _r = run(pie_ends_at=8.0)
check("+ PIE ending mid-run -> FAILED reason pie_ended, no OK, no console after the end",
      r_pe["status"] == "failed" and any("reason=pie_ended" in m for m in f_pe.errors)
      and not any(m.startswith("PASSAGE_STILLS_OK") for m in f_pe.logs)
      and r_pe["restore_scrub"] == {"skipped": "PIE gone"})
check("- control: the tick is inert after finish (calling it again issues nothing)",
      (lambda n: (_r["fn"](0.1), len(f_pe.commands) == n)[1])(len(f_pe.commands)))

# ---- source scan: forbidden operations and module globals
src = (HERE / "passage_stills.py").read_text(encoding="utf-8")
names = {t.string for t in tokenize.generate_tokens(io.StringIO(src).readline) if t.type == tokenize.NAME}
forbidden = {"save_package", "save_packages", "save_dirty_packages", "save_current_level", "save_map",
             "save_asset", "save_loaded_asset", "editor_request_end_play", "request_end_play", "end_play",
             "quit_editor", "spawn_actor_from_class", "spawn_actor_from_object", "destroy_actor", "load_level",
             "load_map", "new_level", "set_editor_property", "set_actor_location", "set_actor_rotation",
             "set_play_rate", "play_forward_to_boundary", "set_actor_hidden_in_game"}
check("+ source scan: no save / end-PIE / quit / spawn / destroy / level-load / property-write / actor-move names",
      not (names & forbidden))
check("- control: the scan sees a forbidden name when one is present",
      "editor_request_end_play" in {t.string for t in tokenize.generate_tokens(
          io.StringIO("x.editor_request_end_play()\n").readline) if t.type == tokenize.NAME})
top_import = [l for l in src.splitlines() if re.match(r"^(import|from)\s+unreal\b", l)]
check("+ no module-level `import unreal` (UE wrappers only inside functions)", not top_import)
check("+ importing the module ran nothing (no main without STILLS_PASSAGE)", "STILLS_PASSAGE" not in vars(ps))

# ---- run wrapper + request envelope
calls = []
fake_runpy = types.SimpleNamespace(run_path=lambda path, init_globals=None: calls.append((path, init_globals)))
real_run_path = runpy.run_path
args_path = HERE / "passage_stills_args.json"
wrap_dir = tmp / "wrap"
wrap_dir.mkdir()
(wrap_dir / "passage_stills_args.json").write_text(json.dumps({"passage": "P03", "fractions": [0.2, 0.8]}),
                                                   encoding="utf-8")
wrap_src = (HERE / "passage_stills_run.py").read_text(encoding="utf-8")
check("- control: the wrapper reads its args from the fixed CodexConductor path (so the redirect below is real)",
      'HERE = "E:/PussStage/Saved/CodexConductor/"' in wrap_src)
wrap_src = wrap_src.replace('HERE = "E:/PussStage/Saved/CodexConductor/"', 'HERE = %r' % (wrap_dir.as_posix() + "/"))
try:
    runpy.run_path = fake_runpy.run_path
    exec(compile(wrap_src, "passage_stills_run.py", "exec"), {"__name__": "__main__"})
finally:
    runpy.run_path = real_run_path
check("+ run wrapper: purges Saved modules, then runs passage_stills.py with the args as init_globals",
      len(calls) == 2 and calls[0][0].endswith("purge_saved_module_cache.py")
      and calls[1][0].endswith("passage_stills.py")
      and calls[1][1]["STILLS_PASSAGE"] == "P03" and calls[1][1]["STILLS_FRACTIONS"] == [0.2, 0.8])
check("- control: wrapper refuses args without a passage",
      raises(lambda: exec(compile(wrap_src.replace('args = json.load(handle)', 'args = {}'), "w", "exec"),
                          {"__name__": "__main__"}), "bad_args"))
req = json.loads((HERE / "passage_stills_request.json").read_text(encoding="utf-8"))
ref = json.loads((HERE / "purge_saved_module_cache_request.json").read_text(encoding="utf-8"))
ref["arguments"]["arguments"]["relativeSavedPath"] = "CodexConductor/passage_stills_run.py"
check("+ request JSON = the purge request envelope with relativeSavedPath CodexConductor/passage_stills_run.py",
      req == ref)
default_args = json.loads(args_path.read_text(encoding="utf-8"))
check("+ shipped operational args have a valid passage and valid fractions",
      bool(ps.passage_label(default_args["passage"])) and
      ps.validate_fractions(default_args.get("fractions")) == default_args.get("fractions"))

failed = [n for n, ok in RESULTS if not ok]
print("\nPASSAGE_STILLS_HARNESS %d/%d %s" % (len(RESULTS) - len(failed), len(RESULTS), "OK" if not failed else "FAILED"))
sys.exit(1 if failed else 0)
