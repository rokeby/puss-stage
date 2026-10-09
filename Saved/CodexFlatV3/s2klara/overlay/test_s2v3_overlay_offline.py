"""Offline harness for the S2 V3 wings overlay (8 Oct).  System Python, no Unreal.  Writes ONLY into a temp folder
(the tool's HERE/PROJECT are redirected there) plus test_s2v3_overlay_offline_report.json next to this file.

Part A  core maths / gates, each with a POSITIVE and a NEGATIVE control.
Part B  the editor tool end-to-end against a FAKE `unreal` module (sequences, bindings, tracks, sections, channels,
        keys, actors, dirty census, saves): DRY -> APPLY -> VERIFY -> VARIANT B -> VERIFY -> RESYNC (noop) -> re-ingest
        -> VERIFY (stale) -> RESYNC -> VERIFY -> REVERT (scene fingerprint == pre-APPLY), plus negative controls
        (foreign edit during APPLY, Klara level dirtied, wrong binding resolution, PIE, Sequencer open, stale DRY,
        wrong pivot offset).
Part C  static checks of the tool source (no forbidden calls, no module-level unreal objects) with a +/- control.

The fake is MY model of the UE API (names taken from precedent scripts); it proves the tool's logic and guards, not
UE behaviour.  Tier of every PASS here: measured-offline (against the fake)."""
import ast
import copy as _copy
import importlib.util
import json
import math
import os
import random
import shutil
import sys
import tempfile
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
S2K = os.path.dirname(HERE)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"name": name, "ok": bool(cond), "detail": str(detail)[:400]})
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  :: " + str(detail)[:400]))


def expect_raise(name, fn, contains):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        check(name, contains in str(exc), "raised %r" % exc)
        return
    check(name, False, "did not raise")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


C = load("s2v3_core_test", os.path.join(HERE, "s2v3_overlay_core.py"))
CENSUS = json.load(open(os.path.join(S2K, "her_wings_census.json"), encoding="utf-8"))
DECODE = json.load(open(os.path.join(S2K, "her_seq_decode.json"), encoding="utf-8"))

# her world sizes (PROPOSAL.md table [meas]): local half-widths and heights of her meshes
HER_LOCAL_BOX = {"L": [[-2.5, -212.7, 0.0], [2.5, 212.7, 1000.0]], "R": [[-2.5, -207.6, 0.0], [2.5, 207.6, 1000.0]],
                 "C": [[-2.5, -1976.0, 0.0], [2.5, 1976.0, 1000.0]]}
HER_SCALE = {"L": [1.89, 1.89, 2.25], "R": [2.25, 2.25, 2.25], "C": [0.88, 0.88, 0.88]}


def our_world_size(t):
    b, s = HER_LOCAL_BOX[t], HER_SCALE[t]
    return (b[1][1] - b[0][1]) * s[1], (b[1][2] - b[0][2]) * s[2]


def our_box(t):
    w, h = our_world_size(t)                     # V3 board: front at x=-15..-10 face, backbone pivot at y=0, y 0..W
    return [[-15.0, 0.0, 0.0], [0.0, w, h]]


def type_row(t, sign=1.0):
    w, _h = our_world_size(t)
    return {"mesh": "/Game/Scenes/Wings/FlatV3/KlaraS2/SM_S2K_%s" % t, "pivot_offset_cm": [0.0, sign * w / 2.0, 0.0],
            "rot_offset_deg": [0.0, 0.0, 180.0], "pivot_frame": "her_local_world_cm",
            "variants": {"A": {"Front": "/Game/Scenes/Wings/FlatV3/KlaraS2/MI_S2K_%s_A" % t},
                         "B": {"Front": "/Game/Scenes/Wings/FlatV3/KlaraS2/MI_S2K_%s_B" % t,
                               "Flap": "/Game/Scenes/Wings/FlatV3/KlaraS2/MI_S2K_%s_B" % t}}}


def synth_channels(label, level_yaw=-43.57, rng=None):
    """Her copy channels for one wing, shaped by her_seq_decode.json summaries (n keys, t1, v0->v1, min/max)."""
    rng = rng or random.Random(hash(label) & 0xffff)
    d = DECODE["wings"][label]
    n, t1 = d["z"]["n"], d["z"]["t1_s"]
    ticks = [int(round(i * t1 * 24000 / (n - 1))) for i in range(n)]
    out = {}
    for ch in ("x", "y", "z", "roll", "pitch"):
        s = d[ch]
        vals = []
        for i in range(n):
            f = i / (n - 1.0)
            if ch == "z":
                v = s["v0"] + (s["v1"] - s["v0"]) * (1 - (1 - f) ** 2)
            else:
                v = s["v0"] + (s["max"] - s["min"]) * 0.5 * math.sin(f * 7.0) * (1 - f)
            vals.append(round(v, 4))
        vals[-1] = s["v1"]
        out[ch] = {"keys": [[t, v, "RCIM_LINEAR"] for t, v in zip(ticks, vals)], "default": None,
                   "pre": "RCCE_CONSTANT", "post": "RCCE_CONSTANT"}
    out["yaw"] = {"keys": [[0, level_yaw, "RCIM_LINEAR"]], "default": None, "pre": "RCCE_CONSTANT",
                  "post": "RCCE_CONSTANT"}
    return out


# ===================================================================================================== PART A
def part_a():
    rnd = random.Random(7)
    worst = 0.0
    for _ in range(300):
        r = [rnd.uniform(-180, 180), rnd.uniform(-85, 85), rnd.uniform(-180, 180)]
        back = C.matrix_rotator(C.rot_matrix(*r))
        m1, m2 = C.rot_matrix(*r), C.rot_matrix(*back)
        worst = max(worst, max(abs(m1[i][j] - m2[i][j]) for i in range(3) for j in range(3)))
    check("A1+ rotator round trip (300 random)", worst < 1e-9, worst)
    x = C.apply_rot(C.rot_matrix(0, 0, 90), [1, 0, 0])
    check("A1+ yaw 90 maps +X to +Y (UE convention)", abs(x[0]) < 1e-12 and abs(x[1] - 1) < 1e-12, x)
    z = C.apply_rot(C.rot_matrix(0, 30, 0), [1, 0, 0])
    check("A1+ pitch +30 raises +X (nose up)", z[2] > 0.49, z)
    check("A1- a different rotator is NOT a round trip", max(abs(a - b) for a, b in zip(
        C.rot_matrix(0, 0, 90)[0], C.rot_matrix(0, 0, 91)[0])) > 1e-3)

    row = type_row("L")
    her = [100.0, 200.0, 789.0, 0.0, 0.0, -43.57]
    p = C.compose_pose(her, row)
    w = our_world_size("L")[0]
    exp = C.apply_rot(C.rot_matrix(0, 0, -43.57), [0, w / 2, 0])
    check("A2+ compose: loc = her + R_her.offset", all(abs(p[i] - (her[i] + exp[i])) < 1e-9 for i in range(3)), p)
    check("A2+ compose: yaw = her yaw + 180", C.angle_diff(p[5], -43.57 + 180) < 1e-9 and abs(p[3]) < 1e-9, p[3:])
    r0 = dict(row, rot_offset_deg=[0.0, 0.0, 0.0])
    r0b = dict(r0, pivot_frame="our_local_cm")         # (with yaw 180 the two frames coincide for a pure-Y offset)
    check("A2- our_local_cm frame gives a different location", max(abs(a - b) for a, b in zip(
        C.compose_pose(her, r0b)[:3], C.compose_pose(her, r0)[:3])) > 1.0)
    zero = dict(row, pivot_offset_cm=[0.0, 0.0, 0.0], rot_offset_deg=[0.0, 0.0, 0.0])
    tilt = [5.0, 6.0, 7.0, 3.3, -0.9, -43.57]
    check("A2+ zero offset reproduces her pose", all(abs(a - b) < 1e-9 for a, b in zip(C.compose_pose(tilt, zero), tilt)))

    ch = {"keys": [[0, 0.0, "RCIM_LINEAR"], [100, 10.0, "RCIM_CONSTANT"], [200, 20.0, "RCIM_LINEAR"]], "default": None}
    check("A3+ linear eval", abs(C.eval_channel(ch, 50) - 5.0) < 1e-12)
    check("A3+ constant segment holds", C.eval_channel(ch, 150) == 10.0)
    check("A3+ constant extrapolation", C.eval_channel(ch, -5) == 0.0 and C.eval_channel(ch, 999) == 20.0)
    cub = {"keys": [[0, 0.0, "RCIM_CUBIC"], [100, 10.0, "RCIM_LINEAR"]], "default": None}
    expect_raise("A3- cubic segment refused", lambda: C.eval_channel(cub, 50), "NONLINEAR_SOURCE_KEY")

    label = "SM_S2_ceiling_wing5"
    chans = synth_channels(label)
    kp0 = C.plan_wing_keys(chans, zero)
    same = all(abs(k[3] - C.eval_channel(chans["z"], k[0])) < 1e-9 for k in kp0["keys"])
    check("A4+ zero offset: our Z keys == her Z keys at her ticks", same and kp0["n"] == DECODE["wings"][label]["z"]["n"],
          kp0.get("n"))
    kp = C.plan_wing_keys(chans, type_row("C"))
    check("A4+ ceiling with 1976 cm half-width offset: midpoint deviation within tol", not kp["problems"],
          (kp["midpoint_dev_cm"], kp["midpoint_dev_deg"]))
    kpt = C.plan_wing_keys(chans, type_row("C"), tol_cm=1e-9, tol_deg=1e-9)
    check("A4- tolerance control: a near-zero tol refuses (deviation is measured, not assumed)",
          any(x.startswith("MIDPOINT_DEVIATION") for x in kpt["problems"]), kpt["problems"])
    kz = C.plan_wing_keys(chans, zero, copy_channels="z_only")
    restx = C.eval_channel(chans["x"], 10 ** 9)
    check("A4+ z_only holds X at her rest value", all(abs(k[1] - restx) < 1e-9 for k in kz["keys"]))
    bad = _copy.deepcopy(chans)
    bad["x"]["post"] = "RCCE_CYCLE"
    check("A4- cyclic extrapolation refused", any("EXTRAPOLATION" in x for x in C.plan_wing_keys(bad, zero)["problems"]))

    h0 = C.source_hashes(chans)
    n1 = _copy.deepcopy(chans)
    n1["z"]["keys"][5][1] += 1e-6
    check("A5+ hash stable under 1e-6 transport noise", C.source_hashes(n1) == h0)
    n2 = _copy.deepcopy(chans)
    n2["z"]["keys"][5][1] += 0.01
    check("A5- hash changes on a 0.01 cm key edit (re-ingest detectable)",
          C.source_hashes(n2)["z"] != h0["z"] and C.source_hashes(n2)["all"] != h0["all"])

    before = {"SEQ": {"a": 1}, "M/T0:MovieSceneSubTrack:Klara Hookin - Replacement Shot": {"s": 1}}
    tp = "M/T5:MovieSceneSubTrack:" + C.OVERLAY_TRACK
    after = dict(before, **{tp: {"x": 1}, tp + "/S0": {"y": 1}})
    check("A6+ only our rows new -> no violations", C.fingerprint_diff(before, after, tp) == [])
    after2 = dict(after, **{"M/T6:MovieSceneSubTrack:" + C.OVERLAY_TRACK + "2": {"z": 1}})
    check("A6- prefix collision ('...Overlay2') is a violation", len(C.fingerprint_diff(before, after2, tp)) == 1)
    after3 = dict(after, SEQ={"a": 2})
    check("A6- a changed foreign row is a violation", C.fingerprint_diff(before, after3, tp)[0]["why"] == "CHANGED")
    after4 = {k: v for k, v in after.items() if k != "SEQ"}
    check("A6- a removed row is a violation", C.fingerprint_diff(before, after4, tp)[0]["why"] == "REMOVED")

    check("A7+ exact census passes", C.census_gate({"content": ["/Game/a"], "maps": []}, ["/Game/a"]) == [])
    g = C.census_gate({"content": ["/Game/a"], "maps": [C.HER_LEVEL]}, ["/Game/a"])
    check("A7- her level dirty -> KLARA_PACKAGE_DIRTY", any(x.startswith("KLARA_PACKAGE_DIRTY") for x in g), g)
    g2 = C.census_gate({"content": ["/Game/a", "/Game/b"], "maps": []}, ["/Game/a"])
    check("A7- extra dirty content refused", any(x.startswith("CONTENT_CENSUS") for x in g2))

    man = {"meshes": [dict(type_row(t), owner="S2K_%s" % t) for t in C.TYPES]}
    args = {"types": {t: {"owner": "S2K_%s" % t} for t in C.TYPES}}
    res, probs = C.resolve_types(args, man, None)
    check("A8+ manifest resolves all three types", not probs and res["L"]["sources"]["pivot_offset_cm"].startswith(
        "manifest."), probs)
    rec = {"rows": [{"owner": "S2K_L", "pivot_offset_cm": [0, 1, 2]}]}
    res2, _p = C.resolve_types(args, man, rec)
    check("A8+ pivot record outranks the manifest", res2["L"]["pivot_offset_cm"] == [0.0, 1.0, 2.0])
    a3 = {"types": dict(args["types"], L={"owner": "S2K_L", "pivot_offset_cm": [9, 9, 9]})}
    check("A8+ args outrank both", C.resolve_types(a3, man, rec)[0]["L"]["pivot_offset_cm"] == [9.0, 9.0, 9.0])
    _r, p4 = C.resolve_types(args, None, None)
    check("A8- no manifest -> unresolved mesh + pivot for every type", sum("unresolved" in x for x in p4) == 6, p4)
    man2 = {"meshes": man["meshes"] + [dict(type_row("L"), owner="S2K_L")]}
    check("A8- two manifest entries for one owner -> ambiguous", any("ambiguous" in x for x in C.resolve_types(
        args, man2, None)[1]))

    wings = C.her_wings_from_census(CENSUS)
    check("A9+ census -> 15 wings (5 L, 5 R, 5 C)", len(wings) == 15)
    cut = dict(CENSUS, rows=[r for r in CENSUS["rows"] if r.get("label") != "SM_S2_L_Wing_Shrine3"])
    expect_raise("A9- a missing wing refuses", lambda: C.her_wings_from_census(cut), "HER_WING_COUNT")

    good = {"mode": "APPLY", "confirm": "APPLY S2V3OVERLAY", "decided_by": "x",
            "overlay_asset": "/Game/Scenes/KlaraS2V3/LS_S2_V3WingsOverlay", "types": args["types"]}
    check("A10+ valid APPLY args", C.validate_args(good) == [], C.validate_args(good))
    check("A10- wrong confirm", any(x.startswith("CONFIRM") for x in C.validate_args(dict(good, confirm="APPLY"))))
    check("A10- overlay inside her folder refused", any(x.startswith("OVERLAY_ASSET") for x in C.validate_args(
        dict(good, overlay_asset="/Game/KK_S2_Shrine/LS_X"))))
    check("A10- PIE refused", any("PIE_RUNNING" in x for x in C.check_mode(good, True, None, None)))
    check("A10- Sequencer open refused (DRY too)", any("SEQUENCER_OPEN" in x for x in C.check_mode(
        dict(good, mode="DRY"), False, "/Game/X", None)))

    al = C.box_alignment(our_box("L"), HER_LOCAL_BOX["L"], HER_SCALE["L"], type_row("L"))
    check("A11+ correct pivot: our box lands on hers (Y/Z within 0.01 cm)", al["max_yz_cm"] < 0.01, al["delta"])
    al2 = C.box_alignment(our_box("L"), HER_LOCAL_BOX["L"], HER_SCALE["L"], type_row("L", sign=-1.0))
    check("A11- wrong pivot sign: off by a full width", al2["max_yz_cm"] > 700, al2["delta"])


# ===================================================================================================== FAKE UNREAL
class Enum:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "Enum." + self.name

    def __eq__(self, o):
        return isinstance(o, Enum) and o.name == self.name

    def __hash__(self):
        return hash(self.name)


class NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FrameNumber:
    def __init__(self, value):
        self.value = int(value)


class FrameRate:
    def __init__(self, n, d=1):
        self.numerator, self.denominator = n, d


class FrameTime:
    def __init__(self, fn, sub=0.0):
        self.frame_number, self.sub_frame = fn, sub


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Rotator:
    def __init__(self, roll=0.0, pitch=0.0, yaw=0.0):
        self.roll, self.pitch, self.yaw = float(roll), float(pitch), float(yaw)


class FakeClass:
    def __init__(self, name):
        self._n = name

    def get_name(self):
        return self._n


class Obj:
    def get_class(self):
        return FakeClass(getattr(self, "_cls_name", type(self).__name__))


class World:
    def __init__(self, U, pkg):
        self.U, self.pkg, self.actors = U, pkg, []

    def get_outermost(self):
        return NS(get_name=lambda: self.pkg)


class Key:
    def __init__(self, tick, value, interp="RCIM_LINEAR"):
        self.tick, self.value, self.interp = int(tick), value, interp

    def get_time(self, time_unit=None):
        if time_unit is None or time_unit.name != "TICK_RESOLUTION":
            raise RuntimeError("fake: only TICK_RESOLUTION supported")
        return FrameTime(FrameNumber(self.tick), 0.0)

    def get_value(self):
        return self.value

    def get_interpolation_mode(self):
        return Enum(self.interp)

    def get_tangent_mode(self):
        return Enum("RCTM_AUTO")


class Channel(Obj):
    def __init__(self, sec, name, kind="double"):
        self.sec, self.channel_name, self.kind = sec, name, kind
        self.keys, self.default = [], None
        self.pre = self.post = Enum("RCCE_CONSTANT")

    def _d(self):
        self.sec._d()

    def get_name(self):
        return self.channel_name

    def get_keys(self):
        return list(self.keys)

    def add_key(self, time, new_value, sub_frame=0.0, time_unit=None, interpolation=None):
        if time_unit is None or time_unit.name != "TICK_RESOLUTION":
            raise RuntimeError("fake: tool must key in TICK_RESOLUTION")
        self.keys = [k for k in self.keys if k.tick != time.value]
        k = Key(time.value, new_value, "RCIM_LINEAR" if interpolation and interpolation.name == "LINEAR" else
                "RCIM_CUBIC")
        self.keys.append(k)
        self.keys.sort(key=lambda k: k.tick)
        self._d()
        return k

    def remove_key(self, k):
        self.keys.remove(k)
        self._d()

    def set_default(self, v):
        self.default = v
        self._d()

    def get_default(self):
        return self.default

    def has_default(self):
        return self.default is not None

    def get_pre_infinity_extrapolation(self):
        return self.pre

    def get_post_infinity_extrapolation(self):
        return self.post


class Params:
    def __init__(self, offset=0, scale=1.0):
        self.start_frame_offset, self.time_scale = offset, scale

    def export_text(self):
        return "(StartFrameOffset=(Value=%d),TimeScale=%.6f)" % (self.start_frame_offset, self.time_scale)


class Section(Obj):
    def __init__(self, track, chan_spec=()):
        self.track, self.start, self.end, self.active = track, 0, 0, True
        self.completion = Enum("KEEP_STATE")
        self.channels = [Channel(self, n, k) for n, k in chan_spec]
        self.blend = Enum("ABSOLUTE")

    def _d(self):
        self.track._d()

    def get_all_channels(self):
        return list(self.channels)

    def set_range(self, a, b):
        self.start, self.end = int(a), int(b)
        self._d()

    def get_start_frame(self):
        return self.start

    def get_end_frame(self):
        return self.end

    def has_start_frame(self):
        return True

    def has_end_frame(self):
        return True

    def is_active(self):
        return self.active

    def set_is_active(self, v):
        self.active = bool(v)
        self._d()

    def set_completion_mode(self, m):
        self.completion = m
        self._d()

    def get_completion_mode(self):
        return self.completion

    def get_blend_type(self):
        return self.blend


class SubSection(Section):
    _cls_name = "MovieSceneSubSection"

    def __init__(self, track):
        super().__init__(track)
        self.sequence, self.params = None, Params()

    def get_sequence(self):
        return self.sequence

    def set_sequence(self, s):
        self.sequence = s
        self._d()

    def get_editor_property(self, n):
        assert n == "parameters"
        return Params(self.params.start_frame_offset, self.params.time_scale)

    def set_editor_property(self, n, v):
        assert n == "parameters"
        self.params = Params(v.start_frame_offset, v.time_scale)
        self._d()


TRANSFORM_CH = [("Location.X_183", "d"), ("Location.Y_183", "d"), ("Location.Z_183", "d"), ("Rotation.X_183", "d"),
                ("Rotation.Y_183", "d"), ("Rotation.Z_183", "d"), ("Scale.X_183", "d"), ("Scale.Y_183", "d"),
                ("Scale.Z_183", "d")]


class Track(Obj):
    def __init__(self, owner, cls_name):
        self.owner, self._cls_name, self.name, self.prop, self.sections = owner, cls_name, cls_name, "", []

    def _d(self):
        self.owner._d()

    def get_display_name(self):
        return self.name

    def set_display_name(self, n):
        self.name = n
        self._d()

    def get_property_name(self):
        return self.prop

    def set_property_name_and_path(self, n, p):
        self.prop = n
        self._d()

    def add_section(self):
        if self._cls_name in ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack"):
            s = SubSection(self)
        elif self._cls_name == "MovieScene3DTransformTrack":
            s = Section(self, TRANSFORM_CH)
        elif self._cls_name in ("MovieSceneVisibilityTrack", "MovieSceneSpawnTrack", "MovieSceneBoolTrack"):
            s = Section(self, [("Bool", "b")])
        else:
            s = Section(self, [("Float", "d")])
        self.sections.append(s)
        self._d()
        return s

    def remove_section(self, s):
        self.sections.remove(s)
        self._d()

    def get_sections(self):
        return list(self.sections)


TRACK_CLASSES = {}


def track_cls(name):
    if name not in TRACK_CLASSES:
        TRACK_CLASSES[name] = type(name, (Track,), {"_cls_name": name})
    return TRACK_CLASSES[name]


class Component(Obj):
    _cls_name = "StaticMeshComponent"

    def __init__(self, owner):
        self.owner = owner
        self.props = {"mobility": Enum("STATIC"), "static_mesh": None, "override_materials": [],
                      "relative_location": Vector(), "relative_rotation": Rotator(), "relative_scale3d": Vector(1, 1, 1)}

    def get_editor_property(self, n):
        return self.props[n]

    def set_editor_property(self, n, v):
        if n not in self.props:
            raise AttributeError(n)
        self.props[n] = list(v) if isinstance(v, list) else v
        if self.owner is not None:
            self.owner._d()


class Template(Obj):
    _cls_name = "StaticMeshActor"

    def __init__(self, binding):
        self.binding = binding
        self.comp = Component(self)

    def _d(self):
        self.binding._d()

    def get_editor_property(self, n):
        if n in ("static_mesh_component", "root_component"):
            return self.comp
        raise AttributeError(n)


class Binding(Obj):
    def __init__(self, seq, name, actor=None, spawnable=False):
        self.seq, self.name, self.actor, self.tracks = seq, name, actor, []
        self.guid = "%032X" % random.getrandbits(128)
        self.template = Template(self) if spawnable else None

    def _d(self):
        self.seq._d()

    def is_valid(self):
        return True

    def get_id(self):
        return self.guid

    def get_display_name(self):
        return self.name

    def set_display_name(self, n):
        self.name = n
        self._d()

    def add_track(self, cls):
        t = track_cls(cls.__name__)(self, cls.__name__)
        self.tracks.append(t)
        self._d()
        return t

    def remove_track(self, t):
        self.tracks.remove(t)
        self._d()

    def get_tracks(self):
        return list(self.tracks)

    def get_object_template(self):
        return self.template

    def get_parent(self):
        return None

    def get_child_possessables(self):
        return []


class Sequence(Obj):
    _cls_name = "LevelSequence"

    def __init__(self, U, path, fps, tick=24000, playback=(0, 100)):
        self.U, self.path, self.fps, self.tick = U, path, FrameRate(fps), FrameRate(tick)
        self.pb, self.tracks, self.bindings = list(playback), [], []

    def _d(self):
        self.U.dirty_content.add(self.path)

    def get_path_name(self):
        return "%s.%s" % (self.path, self.path.rsplit("/", 1)[-1])

    def get_name(self):
        return self.path

    def get_display_rate(self):
        return self.fps

    def get_tick_resolution(self):
        return self.tick

    def set_display_rate(self, r):
        self.fps = FrameRate(r.numerator, r.denominator)
        self._d()

    def set_tick_resolution(self, r):
        self.tick = FrameRate(r.numerator, r.denominator)
        self._d()

    def get_playback_start(self):
        return self.pb[0]

    def get_playback_end(self):
        return self.pb[1]

    def set_playback_start(self, v):
        self.pb[0] = int(v)
        self._d()

    def set_playback_end(self, v):
        self.pb[1] = int(v)
        self._d()

    def get_tracks(self):
        return list(self.tracks)

    def add_track(self, cls):
        t = track_cls(cls.__name__)(self, cls.__name__)
        self.tracks.append(t)
        self._d()
        return t

    def remove_track(self, t):
        self.tracks.remove(t)
        self._d()
        return None                                     # memory: return values lie -> the tool must re-read

    def get_bindings(self):
        return list(self.bindings)

    def add_possessable(self, actor):
        b = Binding(self, str(actor.get_actor_label()), actor=actor)
        self.bindings.append(b)
        self._d()
        self.U.calls.append(("add_possessable", self.path, actor.get_path_name()))
        return b

    def add_spawnable_from_class(self, cls):
        b = Binding(self, cls.__name__, spawnable=True)
        b.tracks.append(track_cls("MovieSceneSpawnTrack")(b, "MovieSceneSpawnTrack"))   # UE adds one itself
        self.bindings.append(b)
        self._d()
        return b

    def locate_bound_objects(self, binding, context):
        if binding.actor is not None and binding.actor in context.actors:
            return [binding.actor]
        return []


class StaticMeshActor(Obj):
    def __init__(self, U, pkg, name, label, mesh, pose, scale):
        self.U, self.pkg, self.name, self.label, self.pose, self.scale = U, pkg, name, label, pose, scale
        self.comp = Component(None)
        self.comp.props["static_mesh"] = mesh

    def get_name(self):
        return self.name

    def get_actor_label(self):
        return self.label

    def get_outermost(self):
        return NS(get_name=lambda: self.pkg)

    def get_path_name(self):
        return "%s.%s:PersistentLevel.%s" % (self.pkg, self.pkg.rsplit("/", 1)[-1], self.name)

    def get_editor_property(self, n):
        if n == "static_mesh_component":
            return self.comp
        raise AttributeError(n)

    def get_actor_location(self):
        return Vector(*self.pose[:3])

    def get_actor_rotation(self):
        return Rotator(roll=self.pose[3], pitch=self.pose[4], yaw=self.pose[5])

    def get_actor_scale3d(self):
        return Vector(*self.scale)


class MaterialInterface(Obj):
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return "%s.%s" % (self.path, self.path.rsplit("/", 1)[-1])


class StaticMesh(Obj):
    def __init__(self, path, box, slots):
        self.path, self.box, self.slots = path, box, slots

    def get_path_name(self):
        return "%s.%s" % (self.path, self.path.rsplit("/", 1)[-1])

    def get_bounding_box(self):
        return NS(min=Vector(*self.box[0]), max=Vector(*self.box[1]))

    def get_editor_property(self, n):
        assert n == "static_materials"
        return [NS(get_editor_property=lambda k, s=s: s) for s in self.slots]


class FakeUnreal(types.ModuleType):
    def __init__(self, project):
        super().__init__("unreal")
        U = self
        self.project, self.assets, self.dirty_content, self.dirty_maps = project, {}, set(), set()
        self.calls, self.logs, self.saved, self.pie, self.seq_open = [], [], [], False, None
        self.world = World(self, C.WORLD)
        self.MovieSceneTimeUnit = NS(TICK_RESOLUTION=Enum("TICK_RESOLUTION"), DISPLAY_RATE=Enum("DISPLAY_RATE"))
        self.MovieSceneKeyInterpolation = NS(LINEAR=Enum("LINEAR"), AUTO=Enum("AUTO"))
        self.MovieSceneCompletionMode = NS(RESTORE_STATE=Enum("RESTORE_STATE"), KEEP_STATE=Enum("KEEP_STATE"))
        self.ComponentMobility = NS(MOVABLE=Enum("MOVABLE"), STATIC=Enum("STATIC"))
        self.FrameNumber, self.Vector, self.Rotator = FrameNumber, Vector, Rotator
        self.LevelSequence, self.MovieSceneBindingProxy = Sequence, Binding
        self.MovieSceneSection, self.StaticMeshActor, self.MaterialInterface = Section, StaticMeshActor, MaterialInterface
        for n in ("MovieSceneSubTrack", "MovieSceneVisibilityTrack", "MovieScene3DTransformTrack",
                  "MovieSceneSpawnTrack", "MovieSceneCinematicShotTrack", "MovieSceneAudioTrack",
                  "MovieSceneLevelVisibilityTrack"):
            setattr(self, n, track_cls(n))
        self.UnrealEditorSubsystem = object
        self.get_editor_subsystem = lambda cls: NS(get_game_world=lambda: object() if U.pie else None,
                                                   get_editor_world=lambda: U.world,
                                                   request_end_play=lambda: U.calls.append(("END_PIE",)))
        self.LevelSequenceEditorBlueprintLibrary = NS(get_current_level_sequence=lambda: U.seq_open)
        self.GuidLibrary = NS(conv_guid_to_string=lambda g: str(g))
        self.EditorLoadingAndSavingUtils = NS(
            get_dirty_content_packages=lambda: [NS(get_name=lambda p=p: p) for p in sorted(U.dirty_content)],
            get_dirty_map_packages=lambda: [NS(get_name=lambda p=p: p) for p in sorted(U.dirty_maps)],
            save_map=lambda *a: U.calls.append(("SAVE_MAP",)))
        self.EditorAssetLibrary = NS(does_asset_exist=lambda p: p.split(".")[0] in U.assets, save_asset=self._save)
        self.GameplayStatics = NS(get_all_actors_of_class=lambda w, cls: [a for a in w.actors if isinstance(a, cls)])
        self.MovieSceneSectionExtensions = NS(get_parent_sequence_frame=self._parent_frame)
        self.LevelSequenceFactoryNew = lambda: None
        self.AssetToolsHelpers = NS(get_asset_tools=lambda: NS(create_asset=self._create))
        self.log = lambda m: U.logs.append(("I", m))
        self.log_error = lambda m: U.logs.append(("E", m))
        self.log_warning = lambda m: U.logs.append(("W", m))
        self.load_asset = lambda p: U.assets.get(str(p).split(".")[0])

    def _save(self, path, only_if_is_dirty=False):
        p = path.split(".")[0]
        if p not in self.assets:
            return False
        self.dirty_content.discard(p)
        self.saved.append(p)
        f = os.path.join(self.project, "Content", *p[len("/Game/"):].split("/")) + ".uasset"
        os.makedirs(os.path.dirname(f), exist_ok=True)
        open(f, "w").write("saved %s" % p)
        return True

    def _create(self, name, folder, cls, factory):
        p = folder + "/" + name
        if p in self.assets:
            return None
        s = Sequence(self, p, 30)
        self.assets[p] = s
        s._d()
        return s

    def _parent_frame(self, sec, frame, parent):
        child = sec.sequence
        cf = child.fps.numerator / child.fps.denominator
        pf = parent.fps.numerator / parent.fps.denominator
        return int(math.floor(sec.start + frame / cf * pf))


def build_env(tmp):
    """Fake editor state: LS_DevScene_02 (hookin section, foreign bindings), the hookin copy with her 15 wing bindings,
    her 15 actors in her streamed level, our meshes + MIs, a manifest.  -> (U, args)."""
    random.seed(11)
    os.makedirs(tmp, exist_ok=True)
    U = FakeUnreal(tmp)
    scene = Sequence(U, C.SCENE_SEQ, 25, 24000, (0, 3891))
    copy = Sequence(U, C.HOOKIN_COPY, 30, 24000, (0, 4217))
    shrine = Sequence(U, "/Game/Scenes/LS_Shrine", 25)
    for s in (scene, copy, shrine):
        U.assets[s.path] = s
    shots = scene.add_track(U.MovieSceneCinematicShotTrack)
    shots.name = "Shots"
    s0 = shots.add_section()
    s0.set_range(0, 375)
    s0.sequence, s0.active = shrine, False
    hk = scene.add_track(U.MovieSceneSubTrack)
    hk.name = C.HOOKIN_TRACK
    hs = hk.add_section()
    hs.set_range(376, 3891)
    hs.sequence, hs.completion = copy, Enum("RESTORE_STATE")
    nar = scene.add_track(U.MovieSceneAudioTrack)
    nar.name = "Narration (stand-in)"
    nar.add_section().set_range(104, 1973)
    for pref, nm in ((C.EXPECTED_FOREIGN_PREFIXES[0], "Moon"), (C.EXPECTED_FOREIGN_PREFIXES[1], "SkyLight2"),
                     (C.EXPECTED_FOREIGN_PREFIXES[2], "Lattice"), (C.EXPECTED_FOREIGN_PREFIXES[3], "Ghost")):
        b = Binding(scene, pref + nm)
        scene.bindings.append(b)
        t = b.add_track(U.MovieSceneVisibilityTrack)
        t.prop = "bHidden"
        sec = t.add_section()
        sec.set_range(376, 3891)
        sec.channels[0].default = False
    other = Binding(scene, "S2 Hangar Root")
    scene.bindings.append(other)
    tt = other.add_track(U.MovieScene3DTransformTrack)
    ts = tt.add_section()
    ts.set_range(0, 3891)
    ts.channels[2].keys = [Key(0, -3300.0), Key(24000 * 4, 0.0)]
    cam = Binding(copy, "CineCameraActor")
    copy.bindings.append(cam)
    her_level = C.HER_LEVEL
    wings = C.her_wings_from_census(CENSUS)
    for w in wings:
        b = Binding(copy, w["label"])
        copy.bindings.append(b)
        tr = b.add_track(U.MovieScene3DTransformTrack)
        sec = tr.add_section()
        sec.set_range(0, 4217)
        chans = synth_channels(w["label"])
        for i, n in enumerate(C.CHANNELS):
            sec.channels[i].keys = [Key(t, v, it) for t, v, it in chans[n]["keys"]]
        for i in (6, 7, 8):
            sec.channels[i].default = 1.0
        rest = [C.eval_channel(chans[n], 10 ** 12) for n in C.CHANNELS]
        her_mesh = StaticMesh(w["mesh"].split(".")[0], HER_LOCAL_BOX[w["type"]], ["Front", "Back", "Edge"])
        U.assets[her_mesh.path] = her_mesh
        a = StaticMeshActor(U, her_level, w["actor_name"], w["label"], her_mesh, rest, HER_SCALE[w["type"]])
        U.world.actors.append(a)
    decoy = StaticMeshActor(U, C.WORLD, "StaticMeshActor_10", "SM_S2_L_Wing_Shrine2", None, [0] * 6, [1, 1, 1])
    U.world.actors.append(decoy)                         # same object name in the PERSISTENT level: must be ignored
    man = {"meshes": []}
    for t in C.TYPES:
        row = type_row(t)
        U.assets[row["mesh"]] = StaticMesh(row["mesh"], our_box(t), ["Front", "Flap", "Timber", "Edge"])
        for v in ("A", "B"):
            for mp in row["variants"][v].values():
                U.assets[mp] = MaterialInterface(mp)
        man["meshes"].append(dict(row, owner="S2K_%s" % t))
    mpath = os.path.join(tmp, "IMPORT_MANIFEST_KlaraS2.json")
    json.dump(man, open(mpath, "w"), indent=1)
    os.makedirs(os.path.join(tmp, "Content", "InfinityStage", "Dev", "Sequences"), exist_ok=True)
    open(os.path.join(tmp, "Content", "InfinityStage", "Dev", "Sequences", "LS_DevScene_02.uasset"), "w").write("x")
    U.dirty_content.clear()
    args = json.load(open(os.path.join(HERE, "s2v3_overlay_args.json"), encoding="utf-8"))
    args.update(manifest_path=mpath, decided_by="harness")
    return U, args


def tool_for(U, tmp):
    sys.modules["unreal"] = U
    T = load("s2v3_tool_test_%d" % random.getrandbits(32), os.path.join(HERE, "s2v3_overlay.py"))
    here = os.path.join(tmp, "overlay")
    os.makedirs(here, exist_ok=True)
    shutil.copy2(os.path.join(HERE, "s2v3_overlay_core.py"), here)
    T.HERE, T.PROJECT = here, tmp
    T.RECORD, T.ORIGINALS = os.path.join(here, "s2v3_overlay_record.json"), os.path.join(here, "s2v3_overlay_originals.json")
    T.CENSUS_JSON = os.path.join(S2K, "her_wings_census.json")
    return T


def run(T, U, args, mode, **kw):
    a = dict(args, mode=mode, confirm="%s %s" % (mode, C.CONFIRM_WORD), run="H-%s-%d" % (mode, len(U.logs)), **kw)
    T.S2V3OV_ARGS = a
    n0 = len(U.logs)
    try:
        T.main()
        err = None
    except Exception as exc:  # noqa: BLE001
        err = exc
    new = [m for _l, m in U.logs[n0:]]
    ok = [m for m in new if "_%s_OK|" % mode in m or "_RESYNC_NOOP|" in m]
    return a["run"], ok, new, err


def marker(new, key):
    return next((m for m in new if key in m), None)


def part_b():
    tmp = tempfile.mkdtemp(prefix="s2v3ov_")
    try:
        U, args = build_env(tmp)
        T = tool_for(U, tmp)
        scene = U.assets[C.SCENE_SEQ]
        fp_orig = T._fingerprint(T._core(), scene)

        r, ok, new, err = run(T, U, args, "DRY")
        dry = marker(new, "_DRY_OK|")
        check("B1+ DRY ok, apply_ready, mutated=0, census clean", dry and "apply_ready=True" in dry and
              not U.dirty_content and not U.dirty_maps, new[-3:] if not dry else dry)
        dry_name = "s2v3_overlay_dry_%s.json" % r
        dj = json.load(open(os.path.join(T.HERE, dry_name), encoding="utf-8"))
        check("B1+ DRY records 15 source key hashes (z + all)", sum(1 for w in dj["wings"] if w.get("source_hashes", {})
                                                                    .get("z")) == 15)
        check("B1+ DRY: persistent-level decoy with the same object name ignored", all(
            w["her_actor_path"].startswith(C.HER_LEVEL) for w in dj["wings"]))
        check("B1+ DRY: box alignment within 0.01 cm for all 15", max(w["box_alignment"]["max_yz_cm"]
                                                                      for w in dj["wings"]) < 0.01)

        U.pie = True
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        check("B2- PIE running: APPLY refused, PIE NOT ended", err and "PIE_RUNNING" in str(err) and
              ("END_PIE",) not in U.calls and not U.dirty_content, err)
        U.pie = False
        U.seq_open = scene
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        check("B2- Sequencer open: refused", err and "SEQUENCER_OPEN" in str(err) and not U.dirty_content, err)
        U.seq_open = None

        a_bad = _copy.deepcopy(args)
        a_bad["variant"] = "B"
        r2, ok, new, err = run(T, U, a_bad, "APPLY", dry_report=dry_name)
        check("B2- plan changed since DRY (variant) refused before any write", err and "PLAN_CHANGED_SINCE_DRY" in str(
            err) and not U.dirty_content and not os.path.exists(T.RECORD), err)

        # negative control: a foreign edit slipped into the APPLY path must be caught by the fingerprint, nothing saved
        orig_add_hide = T._add_hide

        def evil_hide(Cm, ov, actor, rng):
            scene.bindings[-1].tracks[0].sections[0].channels[2].keys[1].value = 1.0   # 'S2 Hangar Root' Z key
            return orig_add_hide(Cm, ov, actor, rng)
        T._add_hide = evil_hide
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        T._add_hide = orig_add_hide
        check("B3- foreign edit during APPLY -> FINGERPRINT_VIOLATIONS, nothing saved, record -> .failed",
              err and "FINGERPRINT_VIOLATIONS" in str(err) and not U.saved and not os.path.exists(T.RECORD) and
              os.path.exists(T.RECORD + ".failed-" + r2), err)

        # rebuild (Don't-Save restart)
        U, args = build_env(tmp + "_2")
        T = tool_for(U, tmp + "_2")
        scene = U.assets[C.SCENE_SEQ]
        r, ok, new, err = run(T, U, args, "DRY")
        dry_name = "s2v3_overlay_dry_%s.json" % r
        orig_poss = Sequence.add_possessable

        def dirty_her(self, actor):
            U.dirty_maps.add(C.HER_LEVEL)
            return orig_poss(self, actor)
        Sequence.add_possessable = dirty_her
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        Sequence.add_possessable = orig_poss
        check("B4- Klara level dirtied during APPLY -> KLARA_PACKAGE_DIRTY, nothing saved",
              err and "KLARA_PACKAGE_DIRTY" in str(err) and not U.saved, err)

        U, args = build_env(tmp + "_3")
        T = tool_for(U, tmp + "_3")
        scene = U.assets[C.SCENE_SEQ]
        fp_orig = T._fingerprint(T._core(), scene)
        r, ok, new, err = run(T, U, args, "DRY")
        dry_name = "s2v3_overlay_dry_%s.json" % r
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report=dry_name)
        check("B5+ APPLY ok", bool(ok) and err is None, (err, new[-2:]))
        check("B5+ APPLY saved exactly [overlay, LS_DevScene_02] in that order, census clean",
              U.saved == [args["overlay_asset"], C.SCENE_SEQ] and not U.dirty_content and not U.dirty_maps, U.saved)
        check("B5+ APPLY never saved a map / her packages", ("SAVE_MAP",) not in U.calls and
              not any(C.is_klara_package(p) for p in U.saved))
        check("B5+ originals written BEFORE the backup (marker logged)", marker(new, "_ORIGINALS|") is not None)
        ov = U.assets[args["overlay_asset"]]
        tr = [t for t in scene.tracks if t.name == C.OVERLAY_TRACK]
        check("B5+ our track: 1 section, [376,3891), params == hookin's, seq == overlay",
              len(tr) == 1 and [tr[0].sections[0].start, tr[0].sections[0].end] == [376, 3891] and
              tr[0].sections[0].sequence is ov)
        hides = [b for b in ov.bindings if b.name.startswith(C.HIDE_PREFIX)]
        check("B5+ 15 hide bindings, bHidden, default False (=hidden), RESTORE_STATE",
              len(hides) == 15 and all(b.tracks[0].prop == "bHidden" and b.tracks[0].sections[0].channels[0].default
                                       is False and b.tracks[0].sections[0].completion.name == "RESTORE_STATE"
                                       for b in hides))
        ours = [b for b in ov.bindings if b.name.startswith(C.OURS_PREFIX)]
        spawn_ok = all(len([t for t in b.tracks if t._cls_name == "MovieSceneSpawnTrack"]) == 1 for b in ours)
        check("B5+ 15 spawnables, one spawn track each (UE's own reused), mobility MOVABLE, scale 1",
              len(ours) == 15 and spawn_ok and all(b.template.comp.props["mobility"].name == "MOVABLE" and
                                                   b.template.comp.props["relative_scale3d"].x == 1.0 for b in ours))
        lw = next(b for b in ours if b.name.endswith("SM_S2_L_Wing_Shrine2"))
        zch = [t for t in lw.tracks if t._cls_name == "MovieScene3DTransformTrack"][0].sections[0].channels[2]
        her_b = next(b for b in U.assets[C.HOOKIN_COPY].bindings if b.name == "SM_S2_L_Wing_Shrine2")
        her_z = her_b.tracks[0].sections[0].channels[2]
        check("B5+ our Z keys at her ticks; Z = hers (pivot offset is horizontal)",
              [k.tick for k in zch.keys] == [k.tick for k in her_z.keys] and
              max(abs(a.value - b.value) for a, b in zip(zch.keys, her_z.keys)) < 1e-6)
        mats = lw.template.comp.props["override_materials"]
        check("B5+ variant A: slot 0 (Front) = MI_A, other slots None (mesh defaults)",
              mats[0].path.endswith("MI_S2K_L_A") and mats[1:] == [None, None, None], mats)
        fp_now = T._fingerprint(T._core(), scene)
        check("B5+ LS_DevScene_02: every pre-existing row unchanged", T._core().fingerprint_diff(
            fp_orig, fp_now, T._core().our_track_prefix(fp_now)[0]) == [])

        r3, ok, new, err = run(T, U, args, "VERIFY")
        check("B6+ VERIFY ok after APPLY (a later call)", bool(ok) and err is None, (err, new[-2:]))
        hides[3].actor = U.world.actors[0] if U.world.actors[0] is not hides[3].actor else U.world.actors[1]
        r3, ok, new, err = run(T, U, args, "VERIFY")
        check("B6- VERIFY fails when a hide binding resolves to the wrong actor", marker(new, "_VERIFY_FAILED|") and
              "HIDE_RESOLVES" in marker(new, "_VERIFY_FAILED|"), new[-2:])
        hides[3].actor = next(a for a in U.world.actors if a.label == hides[3].name[len(C.HIDE_PREFIX):]
                              and a.pkg == C.HER_LEVEL)

        r4, ok, new, err = run(T, U, args, "VARIANT", variant="B")
        mats = lw.template.comp.props["override_materials"]
        check("B7+ VARIANT B: only the overlay saved; Front+Flap = MI_B",
              bool(ok) and U.saved[-1] == args["overlay_asset"] and mats[0].path.endswith("MI_S2K_L_B") and
              mats[1].path.endswith("MI_S2K_L_B") and mats[2:] == [None, None], (err, mats))
        r5, ok, new, err = run(T, U, args, "VERIFY", variant="B")
        check("B7+ VERIFY ok after VARIANT B", bool(ok) and err is None, (err, new[-2:]))

        nsave = len(U.saved)
        r6, ok, new, err = run(T, U, args, "RESYNC", variant="B")
        check("B8+ RESYNC with unchanged source -> NOOP, nothing saved", marker(new, "_RESYNC_NOOP|") and
              len(U.saved) == nsave, (err, new[-2:]))
        her_z.keys[10].value += 37.0                    # simulate a re-ingest that changed her keys (saved on disk)
        r7, ok, new, err = run(T, U, args, "VERIFY", variant="B")
        f = marker(new, "_VERIFY_FAILED|")
        check("B8- VERIFY detects changed source keys (SOURCE_KEYS_CHANGED)", f and "SOURCE_KEYS_CHANGED" in json.dumps(
            json.load(open(os.path.join(T.HERE, "s2v3_overlay_verify_%s.json" % r7), encoding="utf-8"))["problems"]), f)
        r8, ok, new, err = run(T, U, args, "RESYNC", variant="B")
        check("B8+ RESYNC re-copies the changed wing only and saves only the overlay",
              marker(new, "_RESYNC_OK|") and "SM_S2_L_Wing_Shrine2" in marker(new, "_RESYNC_OK|") and
              U.saved[-1] == args["overlay_asset"] and abs(zch.keys[10].value - her_z.keys[10].value) < 1e-6,
              (err, new[-2:]))
        r9, ok, new, err = run(T, U, args, "VERIFY", variant="B")
        check("B8+ VERIFY ok after RESYNC", bool(ok) and err is None, (err, new[-3:]))

        r10, ok, new, err = run(T, U, args, "REVERT")
        fp_back = T._fingerprint(T._core(), scene)
        check("B9+ REVERT: LS_DevScene_02 fingerprint == pre-APPLY exactly; only LS_DevScene_02 saved",
              bool(ok) and T._core().fingerprint_diff(fp_orig, fp_back) == [] and U.saved[-1] == C.SCENE_SEQ and
              not U.dirty_content, (err, T._core().fingerprint_diff(fp_orig, fp_back)[:2]))
        check("B9+ REVERT keeps the overlay asset (unreferenced) and renames the record",
              args["overlay_asset"] in U.assets and os.path.exists(T.RECORD + ".reverted-" + r10))
        r11, ok, new, err = run(T, U, args, "REVERT")
        check("B9- second REVERT refused (no applied record)", err and "NO_APPLIED_RECORD" in str(err), err)

        # wrong pivot offset in the manifest -> DRY refuses (box alignment), APPLY cannot start
        U, args = build_env(tmp + "_4")
        T = tool_for(U, tmp + "_4")
        man = json.load(open(args["manifest_path"]))
        man["meshes"][0]["pivot_offset_cm"][1] *= -1
        json.dump(man, open(args["manifest_path"], "w"))
        r, ok, new, err = run(T, U, args, "DRY")
        dj = json.load(open(os.path.join(T.HERE, "s2v3_overlay_dry_%s.json" % r), encoding="utf-8"))
        check("B10- wrong pivot sign -> DRY apply_ready False with BOX_ALIGN refusals for that type",
              not dj["apply_ready"] and sum(x.startswith("BOX_ALIGN") for x in dj["refusals"]) == 5, dj["refusals"][:2])
        r2, ok, new, err = run(T, U, args, "APPLY", dry_report="s2v3_overlay_dry_%s.json" % r)
        check("B10- ... and APPLY refuses (PLAN_REFUSED), nothing dirty", err and "PLAN_REFUSED" in str(err) and
              not U.dirty_content, err)
        # manifest absent -> DRY reports unresolved types, not a crash
        os.remove(args["manifest_path"])
        r, ok, new, err = run(T, U, args, "DRY")
        dj = json.load(open(os.path.join(T.HERE, "s2v3_overlay_dry_%s.json" % r), encoding="utf-8"))
        check("B11- no manifest: DRY completes, apply_ready False, unresolved mesh/pivot named",
              marker(new, "_DRY_OK|") and not dj["apply_ready"] and any("unresolved" in x for x in dj["refusals"]),
              (err, dj["refusals"][:3]))
    except Exception:  # noqa: BLE001
        check("B harness crashed", False, traceback.format_exc())
    finally:
        sys.modules.pop("unreal", None)
        for d in (tmp, tmp + "_2", tmp + "_3", tmp + "_4"):
            shutil.rmtree(d, ignore_errors=True)


# ===================================================================================================== PART C
FORBIDDEN = ("save_map", "save_dirty_packages", "save_packages", "reload_packages", "get_bound_objects",
             "delete_asset", "request_end_play", "end_play_map", "save_all", "load_map", "open_level_sequence",
             "set_current_time", "play_in_editor")


def static_problems(src):
    tree = ast.parse(src)
    probs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN:
            probs.append("FORBIDDEN:%s@%d" % (node.attr, node.lineno))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for sub in ast.walk(node.value if node.value is not None else node):
                if isinstance(sub, ast.Name) and sub.id == "unreal":
                    probs.append("MODULE_LEVEL_UNREAL@%d" % node.lineno)
                    break
    return probs


def part_c():
    src = open(os.path.join(HERE, "s2v3_overlay.py"), encoding="utf-8").read()
    p = static_problems(src)
    check("C1+ tool: no forbidden calls, no module-level unreal objects", p == [], p)
    bad = src + "\nX = unreal.load_asset('/Game/x')\ndef f():\n    unreal.EditorLoadingAndSavingUtils.save_map(1, 2)\n"
    p2 = static_problems(bad)
    check("C1- checker flags an injected save_map and a module-level unreal object",
          any(x.startswith("FORBIDDEN:save_map") for x in p2) and any(x.startswith("MODULE_LEVEL") for x in p2), p2)
    core = open(os.path.join(HERE, "s2v3_overlay_core.py"), encoding="utf-8").read()
    check("C2+ core imports no unreal", "import unreal" not in core)
    run_src = open(os.path.join(HERE, "s2v3_overlay_run.py"), encoding="utf-8").read()
    check("C3+ runner purges the Saved module cache before running the tool",
          run_src.index("runpy.run_path(\"E:/PussStage/Saved/CodexConductor/purge_saved_module_cache.py") < run_src.rindex("s2v3_overlay.py"))
    req = json.load(open(os.path.join(HERE, "s2v3_overlay_request.json")))
    a = req["arguments"]
    check("C3+ request: MCPBlueprintsGenerator toolset / ExecuteProjectPythonFile / runner path",
          a["toolset_name"] == "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset" and
          a["tool_name"] == "ExecuteProjectPythonFile" and
          a["arguments"]["relativeSavedPath"] == "CodexFlatV3/s2klara/overlay/s2v3_overlay_run.py")


def main():
    for part in (part_a, part_b, part_c):
        try:
            part()
        except Exception:  # noqa: BLE001
            check("%s crashed" % part.__name__, False, traceback.format_exc())
    n_ok = sum(r["ok"] for r in RESULTS)
    out = {"passed": n_ok, "failed": len(RESULTS) - n_ok, "results": RESULTS,
           "tier": "measured-offline against a FAKE unreal module; UE behaviour itself is not proven here"}
    json.dump(out, open(os.path.join(HERE, "test_s2v3_overlay_offline_report.json"), "w"), indent=1)
    print("TOTAL %d passed, %d failed" % (n_ok, len(RESULTS) - n_ok))
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
