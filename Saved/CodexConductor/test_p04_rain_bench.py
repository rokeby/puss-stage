"""Offline harness for p04_rain_bench.py (no Unreal). Every property has a + case and a - control that must FAIL,
so each check is shown able to fail. Fake objects stand in for the Niagara reflection (UObjects by reference,
structs by copy, as the Unreal Python wrappers behave) and for the PIE / editor adapters.
Run: python Saved/CodexConductor/test_p04_rain_bench.py"""
import copy
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
import p04_rain_bench as rb  # noqa: E402
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


tmp = pathlib.Path(tempfile.mkdtemp(prefix="p04rain_"))
P = rb.params_of()
SEG = (28363585, 32683585)                        # P04 segment [measured, PSTILLS-P04-20261005-125030-rigB]
SEG_GUID = "0067B5F57142956FB5B80EA31B1210B5"
STROBE = {"label": "P04 Strobe (default, Gary to place)", "location": [2000.0, 240650.0, 60.0], "enabled": True,
          "period_seconds": 1.0, "flash_seconds": 0.04, "decay_seconds": 0.33, "phase_cycles": 0.0,
          "peak_intensity": 20000.0, "active_segment_guids": []}   # place_default_strobe_p04_record.json

# ======================= placement maths =======================
rows, flash = rb.plan_fractions(SEG, 24000, STROBE, P)
FR = [r["fraction"] for r in rows]
plan = rb.plan_tiles(FR, P)
summary = rb.check_plan(plan, FR, P)
check("+ every still's [near, far] interval is inside the tile union (%d tiles)" % len(plan["tiles"]),
      all(rb.covers(plan["tiles"], a, b) for a, b in plan["wanted"]))
check("- control: dropping the middle tile leaves an interval uncovered",
      not all(rb.covers(plan["tiles"][:3] + plan["tiles"][4:], a, b) for a, b in plan["wanted"]))
check("+ tiles do not overlap (uniform density) and stay inside x_clip",
      not rb.tiles_overlap(plan["tiles"]) and all(P["x_clip"][0] <= t["x_range"][0] and t["x_range"][1] <= P["x_clip"][1]
                                                  for t in plan["tiles"]))
check("- control: a duplicated tile is detected as overlap", rb.tiles_overlap(plan["tiles"] + plan["tiles"][:1]))
check("+ planned view coverage >= %.2f at every still (%s)" % (P["min_view_coverage"], summary["coverage"]),
      min(summary["coverage"]) >= P["min_view_coverage"])
far_pose = {"loc": [plan["tiles"][-1]["x_range"][1] + 500.0, 240000.0, 180.0], "rot": {"yaw": 0.0}, "fov_deg": 37.5}
check("- control: a camera past the last tile sees no rain (coverage 0)", rb.view_coverage(far_pose, plan["tiles"], P) == 0.0)
check("- control: check_plan refuses tiles shifted 5 m back (view_coverage or interval miss)",
      raises(lambda: rb.check_plan({"wanted": plan["wanted"], "tiles": [dict(t, center=[t["center"][0] - 500.0] + t["center"][1:],
                                                                             x_range=[t["x_range"][0] - 500.0, t["x_range"][1] - 500.0])
                                                                      for t in plan["tiles"]]}, FR, P), "tiles_miss_interval"))
check("+ rain top %.0f clears the frame top %.0f at far_cm" % (summary["rain_top_z"], summary["frame_top_needed_z"]),
      summary["rain_top_z"] >= summary["frame_top_needed_z"])
check("- control: rain_top 400 cm is refused", raises(lambda: rb.check_plan(plan, FR, dict(P, rain_top_cm=400.0)),
                                                      "rain_top_below_frame_top"))
check("+ particle budget: %d live <= %d" % (summary["live_particles"], P["max_live_particles"]),
      summary["live_particles"] <= P["max_live_particles"])
check("- control: 5x density is refused by the budget",
      raises(lambda: rb.check_plan(plan, FR, dict(P, density_per_m2_s=P["density_per_m2_s"] * 5)), "particle_budget"))
phys = rb.rain_physics(P)
check("+ lifetime = fall height / speed (%.3f s) and the drop reaches the floor at death" % phys["lifetime_s"],
      abs(phys["lifetime_s"] * P["fall_speed_cms"] - P["rain_top_cm"]) < 1e-6)
check("- control: bad speed refused", raises(lambda: rb.rain_physics(dict(P, fall_speed_cms=0.0)), "bad_speed"))
m = rb.merge_intervals([(0, 10), (12, 20), (40, 50)], 3)
check("+ merge: gaps <= merge_gap join, wider gaps stay apart", m == [(0.0, 20.0), (40.0, 50.0)])
check("- control: zero gap keeps (0,10) and (12,20) apart", len(rb.merge_intervals([(0, 10), (12, 20)], 0)) == 2)

# ======================= strobe =======================
L = rb.level_at
check("+ level_at matches the C++ LevelAt (flash 1, tail exp(-after/tau), cut at decay, phase shifts)",
      L(0.0, 1, .04, .33, 0) == 1.0 and L(0.039, 1, .04, .33, 0) == 1.0 and abs(L(0.2, 1, .04, .33, 0) - math.exp(-0.16 / (0.33 / 4.6))) < 1e-12
      and L(0.5, 1, .04, .33, 0) == 0.0 and L(0.5, 1, .04, .33, 0.5) == 1.0 and L(-0.98, 1, .04, .33, 0) == 1.0
      and L(1.0, 0.0, .04, .33, 0) == 0.0)
check("- control: ignoring the phase gives a different level", L(0.5, 1, .04, .33, 0.0) != L(0.5, 1, .04, .33, 0.5))
ff, df = flash["flash_frame"], flash["dark_frame"]
cam_flash = rb.route_x(rb.frame_to_fraction(SEG, ff), P["route"])
check("+ flash frame is mid-flash (level 1) and its dark partner is level 0, both inside the segment",
      rb.strobe_level_at_frame(ff, 24000, STROBE) == 1.0 and rb.strobe_level_at_frame(df, 24000, STROBE) == 0.0
      and SEG[0] <= ff < df <= SEG[1] - ps.END_GUARD_TICKS)
check("+ flash camera ~flash_lead_cm short of the strobe (x %.0f vs %.0f)" % (cam_flash, 2000 - P["flash_lead_cm"]),
      abs(cam_flash - (2000.0 - P["flash_lead_cm"])) <= 1.0 * 60.0)      # within one period of camera travel
fr_rows = {r["kind"]: r for r in rows}
check("+ flash / dark fractions round-trip through passage_stills.fraction_to_frame onto the same frames",
      ps.fraction_to_frame(SEG[0], SEG[1], fr_rows["flash"]["fraction"]) == ff
      and ps.fraction_to_frame(SEG[0], SEG[1], fr_rows["dark"]["fraction"]) == df)
naive = int(round(SEG[0] + (rb.route_fraction(2000 - P["flash_lead_cm"], P["route"])) * (SEG[1] - SEG[0])))
naive_off = naive + 6000                             # a quarter period later
check("- control: a frame a quarter period off the flash is not lit (the frame choice matters)",
      rb.strobe_level_at_frame(naive_off, 24000, STROBE) < 1.0)
check("- control: a strobe with no flash and no decay is never at level 1 (C++ LevelAt: flash 0 + decay 0 = dark)",
      raises(lambda: rb.flash_frames(SEG, 24000, dict(STROBE, flash_seconds=0.0, decay_seconds=0.0), P), "no_flash_frame"))
check("- control: a strobe that never goes dark is refused",
      raises(lambda: rb.flash_frames(SEG, 24000, dict(STROBE, flash_seconds=0.99, decay_seconds=5.0), P), "no_dark_frame"))
check("+ pick_strobe takes the enabled, in-band, in-segment strobe",
      rb.pick_strobe([STROBE], SEG_GUID, P) is STROBE)
check("- control: disabled / other segment / off-band / outside the route strobes are not picked",
      rb.pick_strobe([dict(STROBE, enabled=False), dict(STROBE, active_segment_guids=["DEADBEEF"]),
                      dict(STROBE, location=[2000.0, 250000.0, 60.0]), dict(STROBE, location=[20000.0, 240650.0, 60.0])],
                     SEG_GUID, P) is None)
check("+ an explicit filter holding the P04 guid is accepted",
      rb.pick_strobe([dict(STROBE, active_segment_guids=[SEG_GUID.lower()])], SEG_GUID, P) is not None)
check("- control: a show tick resolution other than passage_stills' 24000 is refused",
      raises(lambda: rb.plan_fractions(SEG, 30000, STROBE, P), "tick_resolution"))
rows_nf, flash_nf = rb.plan_fractions(SEG, 24000, None, P)
check("+ no strobe: base fractions only, flash None", flash_nf is None and len(rows_nf) == len(P["base_fractions"]))


# ======================= retune engine (fake reflection) =======================
class EnumVal:
    def __init__(self, tname, name):
        self.tname, self.name = tname, name

    def __str__(self):
        return "<%s.%s>" % (self.tname, self.name)

    def __eq__(self, other):
        return isinstance(other, EnumVal) and str(other) == str(self)

    def __hash__(self):
        return hash(str(self))


def make_enum(tname, names):
    t = type(tname, (EnumVal,), {})
    for n in names:
        setattr(t, n, None)
    for n in names:
        setattr(t, n, t(tname, n))
    return t


DistMode = make_enum("NiagaraDistributionMode", ["UNIFORM_CONSTANT", "NON_UNIFORM_CONSTANT", "UNIFORM_RANGE",
                                                 "NON_UNIFORM_RANGE"])
Shape = make_enum("ENSM_ShapePrimitive", ["BOX", "SPHERE", "CYLINDER"])
VelT = make_enum("ENSM_VelocityType", ["LINEAR", "CONE", "POINT"])
SpawnT = make_enum("NiagaraStatelessSpawnInfoType", ["BURST", "RATE"])
Align = make_enum("NiagaraSpriteAlignment", ["UNALIGNED", "VELOCITY_ALIGNED", "CUSTOM_ALIGNMENT"])
Facing = make_enum("NiagaraSpriteFacingMode", ["FACE_CAMERA", "FACE_CAMERA_PLANE"])


class Vec:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return "Vec(%r)" % self.__dict__


class Obj:
    """uobject=True: returned by reference (UObject). False: a struct, copied on get/set (as Unreal Python does)."""

    def __init__(self, path, cls, props, uobject=True, lie=(), refuse=()):
        self.path, self.cls, self.props, self.uobject = path, cls, props, uobject
        self.lie, self.refuse = set(lie), set(refuse)

    def _out(self, v):
        if isinstance(v, list):
            return [x if isinstance(x, Obj) and x.uobject else copy.deepcopy(x) for x in v]
        if isinstance(v, Obj) and v.uobject:
            return v
        return copy.deepcopy(v)

    def get_editor_property(self, name):
        if name not in self.props:
            raise AttributeError("no property %s on %s" % (name, self.cls))
        return self._out(self.props[name])

    def set_editor_property(self, name, value):
        if name in self.refuse:
            raise RuntimeError("cannot set %s" % name)
        if name not in self.props:
            raise AttributeError("no property %s" % name)
        if name in self.lie:
            return                                        # setter lies: no exception, no change
        self.props[name] = self._out(value)


def fdist(v=0.0):
    return Obj("", "Dist", {"mode": DistMode.UNIFORM_RANGE, "min": v, "max": v, "channel_constants_and_ranges": [v, v]},
               uobject=False)


def vdist(n, v=0.0):
    names = ("x", "y", "z")[:n]
    mk = lambda: Vec(**{k: v for k in names})  # noqa: E731
    return Obj("", "Dist", {"mode": DistMode.UNIFORM_CONSTANT, "min": mk(), "max": mk(),
                            "channel_constants_and_ranges": [v]}, uobject=False)


def cdist():
    return Obj("", "DistColor", {"mode": DistMode.UNIFORM_CONSTANT, "values": [Vec(r=1.0, g=1.0, b=1.0, a=1.0)],
                                 "channel_constants_and_ranges": [1.0]}, uobject=False)


def build_emitter(module_lie=None, drop=(), gravity_refuse=False, infos=None):
    module_lie = module_lie or {}
    mods = {
        "ShapeLocation": {"shape_primitive": Shape.SPHERE, "box_surface_only": True, "box_size": vdist(3, 100.0)},
        "AddVelocity": {"velocity_type": VelT.CONE, "linear_velocity_distribution": vdist(3),
                        "linear_velocity_scale": fdist(1.0)},
        "InitializeParticle": {"lifetime_distribution": fdist(2.0), "sprite_size_distribution": vdist(2, 10.0),
                               "sprite_rotation_distribution": fdist(0.0), "color_distribution": cdist()},
        "SpriteFacingAndAlignment": {"sprite_alignment_enabled": False, "sprite_facing_enabled": True,
                                     "sprite_alignment": vdist(3)},
        "SolveVelocitiesAndForces": {},
        "GravityForce": {}, "ScaleColor": {}, "ScaleSpriteSize": {}, "Drag": {},
    }
    objs = []
    for short, props in mods.items():
        if short in drop:
            continue
        props = dict(props, module_enabled=True)
        refuse = ("module_enabled",) if (short == "GravityForce" and gravity_refuse) else ()
        objs.append(Obj("/Game/X.X:Em.%s" % short, rb.MOD + short, props, lie=module_lie.get(short, ()), refuse=refuse))
    rend = Obj("/Game/X.X:Em.Sprite", rb.SPRITE_RENDERER_CLASS, {"alignment": Align.UNALIGNED,
                                                                 "facing_mode": Facing.FACE_CAMERA_PLANE, "material": None})
    if infos is None:
        infos = [Obj("", "SpawnInfo", {"type": SpawnT.RATE, "enabled": True, "rate": fdist(60.0)}, uobject=False),
                 Obj("", "SpawnInfo", {"type": SpawnT.BURST, "enabled": True, "rate": fdist(0.0)}, uobject=False)]
    fb = Obj("", "Box", {"min": Vec(x=-100.0, y=-100.0, z=-100.0), "max": Vec(x=100.0, y=100.0, z=100.0),
                         "is_valid": True}, uobject=False)
    return Obj("/Game/X.X:Em", rb.STATELESS_EMITTER_CLASS, {"modules": objs, "renderer_properties": [rend],
                                                           "spawn_infos": infos, "fixed_bounds": fb})


class Kit:
    def name(self, o):
        return getattr(o, "path", str(o))

    def class_name(self, o):
        return o.cls

    def show(self, v):
        return repr(v)[:120]

    def color(self, r, g, b, a):
        return Vec(r=r, g=g, b=b, a=a)

    def load(self, path):
        return Obj(path, "Material", {})


spec = rb.rain_spec(P, rb.M_STREAK)
em = build_emitter()
log = []
rb.Retuner(em, Kit(), log).apply(spec)
mods = {o.cls: o for o in em.props["modules"]}
box = mods[rb.MOD + "ShapeLocation"].props["box_size"].props
vel = mods[rb.MOD + "AddVelocity"].props["linear_velocity_distribution"].props
life = mods[rb.MOD + "InitializeParticle"].props["lifetime_distribution"].props
size = mods[rb.MOD + "InitializeParticle"].props["sprite_size_distribution"].props
col = mods[rb.MOD + "InitializeParticle"].props["color_distribution"].props
rate = em.props["spawn_infos"][0].props["rate"].props
check("+ retune writes box / velocity / lifetime / streak size / colour / rate / bounds / renderer, every set read back",
      ".BOX>" in str(mods[rb.MOD + "ShapeLocation"].props["shape_primitive"])
      and [box["min"].x, box["min"].y, box["min"].z] == [P["tile_len_cm"], 2 * P["half_width_cm"], P["spawn_thickness_cm"]]
      and ".NON_UNIFORM_CONSTANT>" in str(box["mode"]) and box["channel_constants_and_ranges"] == [1800.0, 1800.0, 20.0]
      and vel["min"].z == -P["fall_speed_cms"] and abs(life["min"] - phys["lifetime_s"]) < 1e-9 and life["max"] == life["min"]
      and [size["min"].x, size["min"].y] == [P["streak_width_cm"], P["streak_length_cm"]]
      and abs(col["values"][0].a - P["color"][3]) < 1e-9 and rate["min"] == phys["rate_per_tile"]
      and em.props["spawn_infos"][1].props["enabled"] is False
      and em.props["fixed_bounds"].props["min"].z == spec["fixed_bounds"]["min"][2]
      and ".CUSTOM_ALIGNMENT>" in str(em.props["renderer_properties"][0].props["alignment"])
      and em.props["renderer_properties"][0].props["material"].path == rb.M_STREAK
      and all(r["ok"] for r in log) and len(log) >= 20)
check("+ gravity and the colour / size scalers end disabled; the four used modules end enabled",
      mods[rb.MOD + "GravityForce"].props["module_enabled"] is False and mods[rb.MOD + "ScaleColor"].props["module_enabled"] is False
      and all(mods[rb.MOD + s].props["module_enabled"] for s in ("ShapeLocation", "AddVelocity", "InitializeParticle",
                                                                 "SpriteFacingAndAlignment")))
check("- control: a setter that lies (box_size ignored) fails with readback_mismatch",
      raises(lambda: rb.Retuner(build_emitter(module_lie={"ShapeLocation": ("box_size",)}), Kit(), []).apply(spec),
             "readback_mismatch"))
check("- control: a missing required module fails with module_absent",
      raises(lambda: rb.Retuner(build_emitter(drop=("AddVelocity",)), Kit(), []).apply(spec), "module_absent"))
check("- control: gravity that cannot be disabled is fatal (MUST_DISABLE)",
      raises(lambda: rb.Retuner(build_emitter(gravity_refuse=True), Kit(), []).apply(spec), "cannot set"))
lg = []
rb.Retuner(build_emitter(drop=("Drag",)), Kit(), lg).apply(spec)
check("+ an absent OPTIONAL module (Drag) is logged as absent, not fatal",
      any(r["obj"].endswith("Drag") and r["got"] == "absent" for r in lg))
burst_only = [Obj("", "SpawnInfo", {"type": SpawnT.BURST, "enabled": True, "rate": fdist(0.0)}, uobject=False)]
e2 = build_emitter(infos=burst_only)
rb.Retuner(e2, Kit(), []).apply(spec)
check("+ a burst-only template is switched to RATE", ".RATE>" in str(e2.props["spawn_infos"][0].props["type"]))
check("- control: an emitter with no spawn info is refused",
      raises(lambda: rb.Retuner(build_emitter(infos=[]), Kit(), []).apply(spec), "no_spawn_info"))
check("- control: a vector given the wrong number of values is refused",
      raises(lambda: rb.Retuner(build_emitter(), Kit(), []).set_dist(build_emitter().props["modules"][0], "box_size",
                                                                        "NON_UNIFORM_CONSTANT", [1.0, 2.0]), "dist_dimension"))
check("+ channels_for: uniform -> one value, non-uniform -> all", rb.channels_for("UNIFORM_CONSTANT", [3]) == [3.0]
      and rb.channels_for("NON_UNIFORM_CONSTANT", [1, 2, 3]) == [1.0, 2.0, 3.0])
check("- control: uniform with 2 values / a range mode are refused",
      raises(lambda: rb.channels_for("UNIFORM_CONSTANT", [1, 2]), "uniform_needs_one_value")
      and raises(lambda: rb.channels_for("UNIFORM_RANGE", [1]), "mode_not_constant"))
sp = rb.splash_spec(dict(P, splash=True))
check("+ splash spec: floor-thin box, upward pop, short life, alignment module disabled",
      sp["modules"]["ShapeLocation"]["dists"]["box_size"][1][2] == 2.0 and sp["modules"]["AddVelocity"]["dists"]
      ["linear_velocity_distribution"][1][2] > 0 and "SpriteFacingAndAlignment" in sp["disable"])
check("+ probe_paths names every property the retune touches (and marks disable-list modules optional)",
      ("emitter", "spawn_infos") in rb.probe_paths(spec) and (rb.MOD + "ShapeLocation", "box_size") in rb.probe_paths(spec)
      and (rb.MOD + "GravityForce", "module_enabled?") in rb.probe_paths(spec))

# ======================= step guards =======================
CLEAN = {"content": [], "maps": []}
PROBE_OK = {"template": rb.TEMPLATE, "authorable": True, "missing": []}
check("+ CREATE guard passes on a clean editor with an authorable probe",
      rb.guard_create(False, CLEAN, [], PROBE_OK) is None)
check("- controls: CREATE refuses PIE / dirty census / existing asset / no probe / unauthorable probe",
      raises(lambda: rb.guard_create(True, CLEAN, [], PROBE_OK), "pie_running")
      and raises(lambda: rb.guard_create(False, {"content": ["/Game/X"], "maps": []}, [], PROBE_OK), "census_dirty")
      and raises(lambda: rb.guard_create(False, CLEAN, [rb.NS_RAIN], PROBE_OK), "asset_exists")
      and raises(lambda: rb.guard_create(False, CLEAN, [], None), "no_probe")
      and raises(lambda: rb.guard_create(False, CLEAN, [], dict(PROBE_OK, authorable=False, missing=["x.y"])),
                 "probe_not_authorable"))
CREATED = {"run": "RAIN-T", "status": "created", "created": [rb.M_STREAK, rb.NS_RAIN]}
check("+ PIE_BEGIN allows exactly the bench's own dirty packages",
      rb.guard_pie_begin(False, {"content": [rb.NS_RAIN, rb.M_STREAK], "maps": []}, CREATED) is None)
check("- controls: PIE_BEGIN refuses a foreign dirty package / a dirty map / an unfinished create",
      raises(lambda: rb.guard_pie_begin(False, {"content": [rb.NS_RAIN, "/Game/Other"], "maps": []}, CREATED),
             "foreign_dirty_content")
      and raises(lambda: rb.guard_pie_begin(False, {"content": [], "maps": ["/Game/Map"]}, CREATED), "map_dirty")
      and raises(lambda: rb.guard_pie_begin(False, CLEAN, dict(CREATED, status="creating")), "no_create"))
check("+ SETUP guard passes in PIE with nothing live", rb.guard_setup("game", CREATED, [], []) is None)
check("- controls: SETUP refuses no PIE / already set up / an armed tick",
      raises(lambda: rb.guard_setup(None, CREATED, [], []), "no_pie")
      and raises(lambda: rb.guard_setup("game", CREATED, ["/x"], []), "already_set_up")
      and raises(lambda: rb.guard_setup("game", CREATED, [], ["PUSS_X_HANDLE"]), "tick_armed"))
SETUP_REC = {"status": "set_up", "spawned": [{"path": "/a"}, {"path": "/b"}]}
check("+ STILLS guard passes when the live components equal the record", rb.guard_stills("game", SETUP_REC, ["/b", "/a"], []) is None)
check("- control: STILLS refuses when a component vanished", raises(lambda: rb.guard_stills("game", SETUP_REC, ["/a"], []),
                                                                     "components_changed"))
check("+ TEARDOWN deletes only bench-created ZZ_ assets", rb.guard_teardown(False, CREATED) == [rb.M_STREAK, rb.NS_RAIN])
check("- controls: TEARDOWN refuses in PIE and refuses a forged foreign path in the record",
      raises(lambda: rb.guard_teardown(True, CREATED), "pie_running")
      and raises(lambda: rb.guard_teardown(False, dict(CREATED, created=["/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"])),
                 "refuse_delete_foreign")
      and raises(lambda: rb.guard_teardown(False, dict(CREATED, created=["/Game/InfinityStage/Bench/NS_Keep"])),
                 "refuse_delete_foreign"))


# ======================= flows with fake adapters =======================
class FakePie:
    def __init__(self, dirty_on_spawn=False, fail_destroy=False):
        self.events, self.live, self.n = [], [], 0
        self.dirty_on_spawn, self.fail_destroy = dirty_on_spawn, fail_destroy
        self.c = {"content": [rb.NS_RAIN, rb.M_STREAK], "maps": []}

    def world_kind(self):
        return "game"

    def world_name(self):
        return "/Game/Maps/UEDPIE_0_L"

    def census(self):
        return copy.deepcopy(self.c)

    def armed_handles(self):
        return []

    def segment(self, passage):
        return {"label": "Passage 4", "start": SEG[0], "end": SEG[1], "guid": SEG_GUID}

    def tick_resolution(self):
        return 24000

    def strobes(self):
        return [copy.deepcopy(STROBE)]

    def live_component_paths(self):
        return list(self.live)

    def spawn(self, system, loc):
        self.events.append("spawn")
        self.n += 1
        path = "/Game/Maps/UEDPIE_0_L.L:PersistentLevel.WorldSettings.NiagaraComponent_%d" % self.n
        self.live.append(path)
        if self.dirty_on_spawn:
            self.c["maps"] = ["/Game/Maps/L"]
        return path

    def destroy(self, path):
        if self.fail_destroy:
            return False
        if path in self.live:
            self.live.remove(path)
        return True


rec_path = tmp / "setup.json"
orig_write = rb.write_record
order = []


def spy_write(path, data, log=print):
    order.append(("write", len(data.get("spawned", [])) if isinstance(data, dict) else None))
    return orig_write(path, data, lambda *_: None)


rb.write_record = spy_write
fp = FakePie()
_orig_spawn = fp.spawn
fp.spawn = lambda s, l: (order.append(("spawn", None)), _orig_spawn(s, l))[1]
srec = rb.flow_setup(fp, P, CREATED, "RAIN-T", log=lambda *_: None, record_path=rec_path)
first_spawn = order.index(("spawn", None))
check("+ SETUP writes the record (spawned=[]) BEFORE the first spawn, then one row per component",
      ("write", 0) in order[:first_spawn] and len(srec["spawned"]) == len(srec["plan"]["tiles"]) and srec["status"] == "set_up"
      and json.loads(rec_path.read_text())["status"] == "set_up")
rb.write_record = lambda *a, **k: (_ for _ in ()).throw(OSError("disk full"))
fp_fail = FakePie()
check("- control: a record that cannot be written stops SETUP before any spawn",
      raises(lambda: rb.flow_setup(fp_fail, P, CREATED, "RAIN-T", log=lambda *_: None, record_path=tmp / "x.json"),
             "disk full") and fp_fail.n == 0)
rb.write_record = orig_write
check("- control: a spawn that dirties the editor census fails SETUP (census_changed)",
      raises(lambda: rb.flow_setup(FakePie(dirty_on_spawn=True), P, CREATED, "RAIN-T", log=lambda *_: None,
                                   record_path=tmp / "s2.json"), "census_changed"))
out = rb.flow_teardown_pie(fp, srec, "RAIN-T", log=lambda *_: None, record_path=rec_path)
check("+ TEARDOWN_PIE destroys every recorded component and leaves none", not out["left"] and len(out["destroyed"]) == len(srec["spawned"]))
fp2 = FakePie(fail_destroy=True)
fp2.live = ["/p/NiagaraComponent_1"]
check("- control: a component that will not die fails TEARDOWN_PIE (components_left)",
      raises(lambda: rb.flow_teardown_pie(fp2, {"spawned": [{"path": "/p/NiagaraComponent_1"}]}, "RAIN-T",
                                          log=lambda *_: None, record_path=tmp / "s3.json"), "components_left"))


class FakeEd:
    def __init__(self, delete_ok=True, pie=False):
        self.assets = {rb.NS_RAIN, rb.M_STREAK}
        self.delete_ok, self.pie, self.deleted = delete_ok, pie, []

    def pie_running(self):
        return self.pie

    def census(self):
        return {"content": sorted(self.assets), "maps": []}

    def live_component_paths(self):
        return []

    def destroy(self, path):
        return True

    def asset_exists(self, path):
        return path in self.assets

    def delete_asset(self, path):
        self.deleted.append(path)
        if self.delete_ok:
            self.assets.discard(path)
        return self.delete_ok


fe = FakeEd()
trec = rb.flow_teardown(fe, dict(CREATED), P, "RAIN-T", log=lambda *_: None, record_path=tmp / "td.json")
check("+ TEARDOWN deletes the systems before the material and ends clean",
      trec["status"] == "clean" and fe.deleted == [rb.NS_RAIN, rb.M_STREAK])
trec2 = rb.flow_teardown(FakeEd(delete_ok=False), dict(CREATED), P, "RAIN-T", log=lambda *_: None,
                         record_path=tmp / "td2.json")
check("- control: a failed delete ends NEEDS_DONT_SAVE_RESTART, not clean",
      trec2["status"] == "needs_dont_save_restart" and trec2["delete_failed"])


# ======================= VERIFY =======================
def write_png(path, w, h, grey, stripe=None):
    rows_ = []
    for y in range(h):
        line = bytearray()
        for x in range(w):
            g = stripe if (stripe is not None and x % 4 == 0) else grey
            line += bytes([g, g, g])
        rows_.append(b"\x00" + bytes(line))

    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body) & 0xFFFFFFFF)
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                                   + chunk(b"IDAT", zlib.compress(b"".join(rows_))) + chunk(b"IEND", b""))


def build_runs(rain_stripe=200, flash_luma=60.0, cam_dy=0.0):
    man = {}
    for label in ("rain", "norain"):
        d = tmp / ("run_" + label + "_%d_%d" % (rain_stripe, int(flash_luma)))
        stills = []
        for i, r in enumerate(srec["stills_plan"]):
            path = d / ("%02d.png" % i)
            write_png(path, 16, 8, 40, rain_stripe if label == "rain" else None)
            luma = flash_luma if r["kind"] == "flash" else 40.0
            stills.append({"i": i, "fraction": r["fraction"], "path": path.as_posix(), "luma": luma,
                           "master_frame_at_capture": r["target_frame"],
                           "pose": {"loc": [rb.route_x(r["fraction"], P["route"]), 240000.0 + cam_dy, 180.0],
                                    "rot": {"yaw": 0.0}, "fov_deg": 37.497}})
        man[d.as_posix()] = {"status": "passed", "stills": stills}
        srec.setdefault("stills_runs", {})[label] = d.as_posix()
    return man


man = build_runs()
ok, rep = rb.verify(srec, P, manifest_loader=lambda d: man[d])
check("+ VERIFY passes: route poses, coverage of the ACTUAL views, rain visible, flash brighter (%d checks)" % len(rep["checks"]),
      ok and len(rep["checks"]) >= 4 * len(srec["stills_plan"]))
man2 = build_runs(rain_stripe=40)
ok2, rep2 = rb.verify(srec, P, manifest_loader=lambda d: man2[d])
check("- control: identical rain / norain images fail 'rain visible'", not ok2 and any("rain visible" in x for x in rep2["problems"]))
man3 = build_runs(flash_luma=40.0)
ok3, rep3 = rb.verify(srec, P, manifest_loader=lambda d: man3[d])
check("- control: a flash still no brighter than its dark partner fails", not ok3 and any("brighter" in x for x in rep3["problems"]))
man4 = build_runs(cam_dy=900.0)
ok4, rep4 = rb.verify(srec, P, manifest_loader=lambda d: man4[d])
check("- control: a camera 9 m off the route fails the route check", not ok4 and any("route" in x for x in rep4["problems"]))
srec_nr = dict(srec, stills_runs={"rain": srec["stills_runs"]["rain"]})
ok5, rep5 = rb.verify(srec_nr, P, manifest_loader=lambda d: man[d])
check("- control: no norain run fails while require_norain is set", not ok5)
check("+ ...and passes with require_norain False", rb.verify(srec_nr, dict(P, require_norain=False), manifest_loader=lambda d: man[d])[0])
srec["stills_runs"] = {}

# ======================= source scans =======================
OURS = [HERE / "p04_rain_bench.py", HERE / "p04_rain_bench_run.py"]
src = "".join(p.read_text(encoding="utf-8") for p in OURS)
code = re.sub(r'"""[\s\S]*?"""', "", src)                        # docstrings may NAME forbidden APIs
code = "\n".join(line.split("#", 1)[0] for line in code.splitlines())
SAVE = re.compile(r"save_(current_level|packages|dirty|map|asset|loaded_asset|directory|level)|EditorAssetLibrary\.save|"
                  r"save_dirty_packages|\.save\(|SavePackage|editor_save|save_map", re.I)
check("+ no save call anywhere in the bench or its runner", not SAVE.search(code))
check("- control: the scanner flags an injected save", bool(SAVE.search(code + "\nunreal.EditorAssetLibrary.save_asset(p)\n")))
ACTOR = re.compile(r"spawn_actor|begin_deferred|finish_spawning|EditorActorSubsystem|EditorLevelLibrary|destroy_actor", re.I)
check("+ no actor spawn / destroy API (the only spawn is NiagaraFunctionLibrary.spawn_system_at_location)",
      not ACTOR.search(code) and code.count("spawn_system_at_location(") == 1)
check("- control: the scanner flags an injected actor spawn", bool(ACTOR.search(code + "\nsub.spawn_actor_from_class(c, l)\n")))
PIE_END = re.compile(r"end_play|request_end|quit_editor|load_level|reload|new_level|open_level", re.I)
check("+ the bench never ends PIE, quits, loads or reloads a level", not PIE_END.search(code))
check("- control: the scanner flags an injected end-play", bool(PIE_END.search(code + "\nles.editor_request_end_play()\n")))
check("+ no Unreal import at module level (UE objects only inside functions)",
      not re.search(r"^import unreal|^from unreal", src, re.M))
markers = re.findall(r'"%s_([A-Z_]+?)\|run=' % "%s", src)
mk = set(re.findall(r'%s_(\w+?_OK|\w+_ARMED|\w+_REQUESTED|NEEDS_DONT_SAVE_RESTART|FAILED)\|run=', src.replace('" % (MARK', '')))
lines = [ln for ln in src.splitlines() if re.search(r'"%s_[A-Z_]+\|', ln)]
check("+ every %s_* marker line carries run=" % rb.MARK, lines and all("run=" in ln or "path=" in ln for ln in lines))
check("- control: a marker without run= is caught",
      not all("run=" in ln or "path=" in ln for ln in lines + ['log("%s_SETUP_OK|tiles=%d" % (MARK, n))']))
check("+ every mode named in MODES has a dispatcher entry",
      all(("\"%s\"" % m) in src.split("def main()", 1)[1] for m in rb.MODES))

failed = [n for n, ok_ in RESULTS if not ok_]
print("\nP04_RAIN_BENCH_HARNESS %d/%d %s" % (len(RESULTS) - len(failed), len(RESULTS), "OK" if not failed else "FAILED"))
sys.exit(1 if failed else 0)
