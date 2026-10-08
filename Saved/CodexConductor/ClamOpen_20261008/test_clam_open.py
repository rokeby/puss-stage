"""OFFLINE harness for clam_open.py (no Unreal).  Pure planning checks + a fake-editor run of DRY / APPLY / REVERT with
negative controls that must FAIL.  Run:  python test_clam_open.py   -> prints CLAMOPEN_HARNESS|pass=n|fail=m|total=t."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
RESULTS = []


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond)))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, info if not cond else ""))


# ---------------------------------------------------------------------------------------------------------------------
# Fake unreal
# ---------------------------------------------------------------------------------------------------------------------
class En:
    def __init__(self, name):
        self.name = name


class FT:
    def __init__(self, f, sub=0.0):
        self.frame_number = types.SimpleNamespace(value=f)
        self.sub_frame = sub


class Key:
    def __init__(self, ch, d):
        self.ch, self.d = ch, d

    def get_time(self, time_unit=None):
        return FT(self.d["frame"], self.d.get("sub", 0.0))

    def get_value(self):
        return self.d["value"]

    def get_interpolation_mode(self):
        return En(self.d["interp"])

    def get_tangent_mode(self):
        return En(self.d["tmode"])

    def get_tangent_weight_mode(self):
        return En(self.d["wmode"])

    def get_arrive_tangent(self):
        return self.d["arrive"]

    def get_leave_tangent(self):
        return self.d["leave"]

    def get_arrive_tangent_weight(self):
        return self.d["arrive_w"]

    def get_leave_tangent_weight(self):
        return self.d["leave_w"]

    def _set(self, k, v):
        self.d[k] = v
        self.ch.st.touch()

    def set_tangent_mode(self, v):
        self._set("tmode", v.name)

    def set_tangent_weight_mode(self, v):
        self._set("wmode", v.name)

    def set_arrive_tangent(self, v):
        self._set("arrive", v)

    def set_leave_tangent(self, v):
        self._set("leave", v)

    def set_arrive_tangent_weight(self, v):
        self._set("arrive_w", v)

    def set_leave_tangent_weight(self, v):
        self._set("leave_w", v)


def kd(frame, value, interp="RCIM_CUBIC", tmode="RCTM_AUTO"):
    return {"frame": frame, "sub": 0.0, "value": value, "interp": interp, "tmode": tmode, "arrive": 0.0, "leave": 0.0,
            "wmode": "RCTWM_WEIGHTED_NONE", "arrive_w": 0.0, "leave_w": 0.0}


class Channel:
    def __init__(self, st, name, keys):
        self.st, self.name, self.keys = st, name, [Key(self, k) for k in keys]

    def get_name(self):
        return self.name

    def get_keys(self):
        return list(self.keys)

    def has_default(self):
        return False

    def get_default(self):
        return 0.0

    def get_pre_infinity_extrapolation(self):
        return En("RCCE_CONSTANT")

    def get_post_infinity_extrapolation(self):
        return En("RCCE_CONSTANT")

    def add_key(self, fn, value, time_unit=None, interpolation=None, sub_frame=0.0):
        self.st.touch()
        d = kd(fn.value, float(value), "RCIM_" + interpolation.name, "RCTM_AUTO")
        k = Key(self, d)
        if fn.value in self.st.lie_frames:
            return k                       # the setter lies: returns a key, stores nothing
        self.keys.append(k)
        if self.st.side_effect is not None:
            self.st.side_effect()
        return k

    def remove_key(self, k):
        self.st.touch()
        self.keys.remove(k)

    def compute_effective_range(self):
        if self.st.eval_raises:
            raise AttributeError("compute_effective_range")
        fr = sorted(k.d["frame"] for k in self.keys)
        return ("rng", fr[0], fr[-1])

    def evaluate_keys(self, rng, rate):
        _, a, b = rng
        pts = sorted((k.d["frame"], k.d["value"]) for k in self.keys)
        out = []
        for f in range(a, b + 1):
            v = pts[-1][1]
            for (f0, v0), (f1, v1) in zip(pts, pts[1:]):
                if f0 <= f <= f1:
                    v = v0 + (v1 - v0) * (f - f0) / float(f1 - f0)
                    break
            out.append(v + self.st.eval_offset)
        return out


class Section:
    def __init__(self, chans, rng=(None, None)):
        self.chans, self.rng = chans, rng

    def get_all_channels(self):
        return list(self.chans)

    def has_start_frame(self):
        return self.rng[0] is not None

    def has_end_frame(self):
        return self.rng[1] is not None

    def get_start_frame(self):
        return self.rng[0]

    def get_end_frame(self):
        return self.rng[1]


class Cls:
    def __init__(self, n):
        self.n = n

    def get_name(self):
        return self.n


class Track:
    def __init__(self, cls, sections):
        self.cls, self.sections = cls, sections

    def get_class(self):
        return Cls(self.cls)

    def get_sections(self):
        return list(self.sections)


class Actor:
    def __init__(self, label):
        self.label = label

    def get_actor_label(self):
        return self.label

    def get_path_name(self):
        return "/Game/Map.Map:PersistentLevel.%s" % self.label.replace(" ", "_")


class Binding:
    def __init__(self, name, tracks, objs):
        self.name, self.tracks, self.objs = name, tracks, objs

    def get_display_name(self):
        return self.name

    def get_tracks(self):
        return list(self.tracks)


class Pkg:
    def __init__(self, n):
        self.n = n

    def get_name(self):
        return self.n


class Seq:
    def __init__(self, st, bindings):
        self.st, self.bindings = st, bindings

    def get_display_rate(self):
        return types.SimpleNamespace(numerator=24, denominator=1)

    def get_playback_end(self):
        return 6240

    def get_bindings(self):
        return list(self.bindings)

    def locate_bound_objects(self, b, world):
        return list(b.objs)

    def modify(self):
        self.st.touch()


class State:
    def __init__(self):
        self.dirty_content, self.dirty_map = set(), set()
        self.pie, self.seq_open, self.map_dirty_on_save, self.eval_raises = False, False, False, False
        self.lie_frames, self.side_effect, self.eval_offset = set(), None, 0.0
        self.saves, self.logs = [], []

    def touch(self):
        self.dirty_content.add(SCENE)


ORIG = {"Location.X": -0.0, "Location.Y": -47.86, "Location.Z": 30.02, "Rotation.X": -0.0, "Rotation.Y": 0.0,
        "Rotation.Z": 0.0, "Scale.X": 1.0, "Scale.Y": 1.0, "Scale.Z": 1.0}


def make_world(frames=(1080, 1440), roll_extra=None, binding=True, n_actors=1, label="S3 PearlClam Lid"):
    st = State()
    chans = []
    for b, v in ORIG.items():
        ks = [kd(f, v) for f in frames]
        if b == "Rotation.X" and roll_extra:
            ks += [kd(f, x) for f, x in roll_extra]
        chans.append(Channel(st, b + "_196", ks))
    st.chans = {c.name.rsplit("_", 1)[0]: c for c in chans}
    tr = Track("MovieScene3DTransformTrack", [Section(chans)])
    vis = Track("MovieSceneVisibilityTrack", [Section([], (744, 6240))])
    bs = [Binding("S3 Hangar Root", [], [Actor("S3 Hangar Root")])]
    if binding:
        bs.append(Binding("S3 Hangar Float Hold: S3 PearlClam Lid", [vis, tr], [Actor(label) for _ in range(n_actors)]))
    st.seq = Seq(st, bs)
    return st


def fake_unreal(st):
    u = types.ModuleType("unreal")
    world = types.SimpleNamespace(get_name=lambda: "L_InfinityStage_V1VerticalSlice")
    ed = types.SimpleNamespace(get_game_world=lambda: object() if st.pie else None, get_editor_world=lambda: world)
    u.UnrealEditorSubsystem = object
    u.get_editor_subsystem = lambda cls: ed
    u.LevelSequenceEditorBlueprintLibrary = types.SimpleNamespace(
        get_current_level_sequence=lambda: object() if st.seq_open else None)
    u.EditorLoadingAndSavingUtils = types.SimpleNamespace(
        get_dirty_content_packages=lambda: [Pkg(x) for x in sorted(st.dirty_content)],
        get_dirty_map_packages=lambda: [Pkg(x) for x in sorted(st.dirty_map)])

    def save_asset(path, only_if_is_dirty=True):
        st.saves.append(path)
        st.dirty_content.discard(path)
        if st.map_dirty_on_save:
            st.dirty_map.add(MAP)
        return True
    u.EditorAssetLibrary = types.SimpleNamespace(save_asset=save_asset)
    u.load_asset = lambda p: st.seq if p == SCENE else None
    u.MovieSceneTimeUnit = types.SimpleNamespace(DISPLAY_RATE=En("DISPLAY_RATE"))
    u.MovieSceneKeyInterpolation = types.SimpleNamespace(LINEAR=En("LINEAR"), AUTO=En("AUTO"))
    u.RichCurveTangentMode = types.SimpleNamespace(RCTM_AUTO=En("RCTM_AUTO"), RCTM_USER=En("RCTM_USER"))
    u.RichCurveTangentWeightMode = types.SimpleNamespace(RCTWM_WEIGHTED_NONE=En("RCTWM_WEIGHTED_NONE"))
    u.FrameNumber = lambda v: types.SimpleNamespace(value=int(v))
    u.log = lambda m: st.logs.append(("log", m))
    u.log_error = lambda m: st.logs.append(("err", m))
    u.log_warning = lambda m: st.logs.append(("warn", m))
    return u


def load_tool(tmp):
    sys.modules.pop("unreal", None)
    spec = importlib.util.spec_from_file_location("clam_open_offline", os.path.join(HERE, "clam_open.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.PROJECT = tmp + "/"
    m.HERE = tmp + "/Saved/CodexConductor/ClamOpen_20261008/"
    os.makedirs(m.HERE, exist_ok=True)
    src = os.path.join(tmp, m.SCENE_FILE)
    os.makedirs(os.path.dirname(src), exist_ok=True)
    with open(src, "wb") as h:
        h.write(b"fake uasset bytes")
    return m


def run(m, st, **over):
    sys.modules["unreal"] = fake_unreal(st)
    a = dict(json.load(open(os.path.join(HERE, "clam_open_args.json"), encoding="utf-8")))
    a.update(over)
    p = m.HERE + "args_test.json"
    with open(p, "w", encoding="utf-8") as h:
        json.dump(a, h)
    return m.main(p)


def roll_frames(st):
    return [k.d["frame"] for k in sorted(st.chans["Rotation.X"].keys, key=lambda k: k.d["frame"])]


def fresh():
    tmp = tempfile.mkdtemp(prefix="clamopen_")
    return tmp, load_tool(tmp)


# ---------------------------------------------------------------------------------------------------------------------
def main():
    tmp, m = fresh()
    check("import_no_unreal", "unreal" not in sys.modules)
    A = m.merged_args(json.load(open(os.path.join(HERE, "clam_open_args.json"), encoding="utf-8")))

    # ---- pure planning
    keys = m.plan_keys(A, [1080, 1440], 6240)
    check("default_first_key", keys[0] == (1446, 0.0), keys[:2])
    check("default_open_end", dict(keys).get(1746) == -80.0, dict(keys).get(1746))
    check("default_hold_to_end", keys[-1] == (6240, -80.0), keys[-1])
    check("default_count_52", len(keys) == 52, len(keys))
    check("default_plan_check", m.check_plan(keys, 80.0) == [], m.check_plan(keys, 80.0))
    check("default_step_6", all(f % 6 == 0 for f, _ in keys[:-1]) and keys[1][0] == 1452)
    for deg in (10.0, 80.0, 100.0):
        a2 = dict(A, ease="smootherstep", open_deg=deg, sample_step=1)
        k2 = m.plan_keys(a2, [1080, 1440], 6240)
        vals = [v for _, v in k2]
        check("smootherstep_monotone_%g" % deg, m.check_plan(k2, deg) == [] and vals[0] == 0.0
              and abs(vals[-1] + deg) < 1e-9 and all(b <= a + 1e-12 for a, b in zip(vals, vals[1:])))
    check("ease_endpoints", all(abs(m.ease(e, 0)) < 1e-12 and abs(m.ease(e, 1) - 1) < 1e-12 for e in m.EASES))
    check("ease_symmetric_mid", abs(m.ease("cubic-in-out", 0.5) - 0.5) < 1e-12 and abs(m.ease("smootherstep", .5) - .5) < 1e-12)
    try:
        m.plan_keys(A, [1080, 1440], 6240, (1000, 1700))
        check("section_range_refused", False)
    except m.Fail as e:
        check("section_range_refused", "PLAN_OUTSIDE_SECTION" in str(e), e)
    check("section_range_bounded_ok", len(m.plan_keys(A, [1080, 1440], 6240, (0, 6241))) == 52)
    ac = m.merged_args(dict(A, crack={"enabled": True}))
    kc = m.plan_keys(ac, [1080, 1440], 6240)
    dc = dict(kc)
    check("crack_shape", dc.get(1446) == 0.0 and dc.get(1482) == -4.0 and dc.get(1542) == -4.0 and dc.get(1746) == -80.0
          and m.check_plan(kc, 80.0) == [], [(f, v) for f, v in kc if f <= 1548])
    check("crack_pause_flat", all(v == -4.0 for f, v in kc if 1482 <= f <= 1542))
    check("crack_deg_range", any("CRACK_DEG" in e for e in m.validate_args(m.merged_args(dict(A, crack={"enabled": True, "deg": 8})))))
    check("crack_no_main", any("CRACK_LEAVES" in e for e in m.validate_args(
        m.merged_args(dict(A, crack={"enabled": True, "duration_frames": 200, "pause_frames": 200})))))
    kh = m.plan_keys(dict(A, hold_closed_until_frame=1443), [1080, 1440], 6240)
    check("hold_closed_key", kh[0] == (1443, 0.0) and kh[1] == (1446, 0.0))
    try:
        m.plan_keys(dict(A, hold_closed_until_frame=1440), [1080, 1440], 6240)
        check("hold_closed_clash_refused", False)
    except m.Fail as e:
        check("hold_closed_clash_refused", "PLAN_NOT_AFTER_EXISTING" in str(e) or "CLASH" in str(e), e)
    check("args_open_deg_low", any("OPEN_DEG_RANGE" in e for e in m.validate_args(dict(A, open_deg=5))))
    check("args_open_deg_high", any("OPEN_DEG_RANGE" in e for e in m.validate_args(dict(A, open_deg=120))))
    check("args_end_before_start", any("END_NOT_AFTER_START" in e for e in m.validate_args(dict(A, open_end_frame=1400))))
    check("args_confirm", any("CONFIRM" in e for e in m.validate_args(dict(A, mode="APPLY", confirm="APPLY"))))
    check("args_default_valid", m.validate_args(A) == [], m.validate_args(A))
    try:
        m.plan_keys(dict(A, open_start_frame=1400, open_end_frame=1700), [1080, 1440], 6240)
        check("start_inside_rise_refused", False)
    except m.Fail as e:
        check("start_inside_rise_refused", "PLAN_NOT_AFTER_EXISTING" in str(e))
    allk = [(1080, 0.0), (1440, 0.0)] + keys
    check("curve_at", m.curve_at(allk, 1200) == 0.0 and m.curve_at(allk, 1746) == -80.0 and m.curve_at(allk, 7000) == -80.0)

    # ---- fake editor: happy path
    st = make_world()
    mk = run(m, st, mode="DRY")
    check("dry_ok", mk.startswith("CLAMOPEN_DRY_OK") and "apply_ready=1" in mk and "eval=OK" in mk, mk)
    check("dry_no_mutation", st.saves == [] and st.dirty_content == set() and len(roll_frames(st)) == 2)
    mk = run(m, st, mode="APPLY", confirm="APPLY CLAMOPEN", run="T-APPLY")
    check("apply_ok", mk.startswith("CLAMOPEN_APPLY_OK|run=T-APPLY") and "keys_added=52" in mk, mk)
    check("apply_saved_scene_only", st.saves == [SCENE] and st.dirty_content == set() and st.dirty_map == set(), st.saves)
    rec = json.load(open(m.HERE + m.RECORD_FILE))
    check("apply_record_state", rec["state"] == "applied" and len(rec["channels"]) == 9
          and all(len(c["keys"]) == 2 for c in rec["channels"].values()))
    check("apply_backup", os.path.exists(os.path.join(tmp, "Backups", "PreClamOpen-T-APPLY", "LS_DevScene_03.uasset")))
    check("apply_roll_keys", roll_frames(st)[:3] == [1080, 1440, 1446] and len(roll_frames(st)) == 54)
    check("apply_others_untouched", all(len(st.chans[b].keys) == 2 for b in ORIG if b != "Rotation.X"))
    check("apply_samples", rec["eval_samples"]["4560"] == -80.0 if isinstance(next(iter(rec["eval_samples"])), str)
          else rec["eval_samples"][4560] == -80.0, rec["eval_samples"])
    mk = run(m, st, mode="APPLY", confirm="APPLY CLAMOPEN", run="T-REAPPLY")
    check("neg_reapply_refused", "CLAMOPEN_FAILED" in mk and "RECORD_EXISTS" in mk and st.saves == [SCENE], mk)
    mk = run(m, st, mode="REVERT", confirm="REVERT CLAMOPEN", run="T-REVERT")
    check("revert_ok", mk.startswith("CLAMOPEN_REVERT_OK|run=T-REVERT"), mk)
    check("revert_restored", roll_frames(st) == [1080, 1440] and st.saves == [SCENE, SCENE] and st.dirty_content == set())
    check("revert_record_renamed", os.path.exists(m.HERE + m.RECORD_FILE + ".reverted-T-REVERT")
          and not os.path.exists(m.HERE + m.RECORD_FILE))
    mk = run(m, st, mode="REVERT", confirm="REVERT CLAMOPEN")
    check("neg_revert_without_record", "NO_RECORD" in mk, mk)

    # ---- negative controls (each must FAIL)
    def neg(name, st, want, saves_expected=0, **over):
        over.setdefault("mode", "APPLY")
        over.setdefault("confirm", "%s CLAMOPEN" % over["mode"])
        mk = run(m, st, **over)
        check(name, mk.startswith("CLAMOPEN_FAILED") and want in mk and len(st.saves) == saves_expected, mk)
        return mk

    def clean():
        for f in os.listdir(m.HERE):
            if f.startswith("clam_open_record"):
                os.remove(m.HERE + f)
    neg("neg_binding_missing", make_world(binding=False), "BINDING_COUNT")
    neg("neg_two_actors", make_world(n_actors=2), "BINDING_RESOLVES")
    neg("neg_wrong_actor", make_world(label="S3 PearlClam Mantle"), "BINDING_ACTOR")
    neg("neg_unexpected_roll_keys", make_world(roll_extra=[(4560, -30.0)]), "UNEXPECTED_PATTERN")
    neg("neg_frames_not_expected", make_world(frames=(3593, 4170)), "UNEXPECTED_PATTERN")
    check("no_record_after_refusals", not os.path.exists(m.HERE + m.RECORD_FILE))
    st = make_world()
    st.lie_frames = {1596}
    neg("neg_setter_lies", st, "READBACK", run="T-LIE")
    clean()
    st = make_world()
    st.side_effect = lambda: st.chans["Location.Z"].keys[0].d.__setitem__("value", 31.0)
    neg("neg_other_channel_changed", st, "OTHER_CHANNEL", run="T-OTHER")
    clean()
    st = make_world()
    st.map_dirty_on_save = True
    neg("neg_dirty_map_after_save", st, "DIRTY_AFTER_SAVE", saves_expected=1, run="T-MAP")
    clean()
    st = make_world()
    neg("neg_open_deg_out_of_range", st, "OPEN_DEG_RANGE", open_deg=120)
    neg("neg_end_before_start", st, "END_NOT_AFTER_START", open_end_frame=1400)
    st = make_world()
    st.dirty_map.add(MAP)
    neg("neg_dirty_at_start", st, "DIRTY_AT_START")
    st = make_world()
    st.pie = True
    neg("neg_pie", st, "PIE_RUNNING")
    st = make_world()
    st.seq_open = True
    neg("neg_sequencer_open", st, "SEQUENCER_OPEN")
    neg("neg_bad_confirm", make_world(), "CONFIRM", confirm="APPLY")
    st = make_world()
    st.eval_raises = True
    neg("neg_eval_unavailable", st, "EVAL_PROBE")
    check("eval_unavailable_no_record", not os.path.exists(m.HERE + m.RECORD_FILE))
    st = make_world()
    st.eval_offset = 0.5
    neg("neg_eval_mismatch", st, "EVAL", run="T-EVAL")
    clean()
    st = make_world()

    def mid_map_dirty():
        st.dirty_map.add(MAP)
    st.side_effect = mid_map_dirty
    neg("neg_map_dirty_before_save", st, "CENSUS", run="T-CENSUS")
    clean()
    # REVERT with drift
    st = make_world()
    mk = run(m, st, mode="APPLY", confirm="APPLY CLAMOPEN", run="T-D")
    check("drift_setup_apply", mk.startswith("CLAMOPEN_APPLY_OK"), mk)
    next(k for k in st.chans["Rotation.X"].keys if k.d["frame"] == 1596).d["value"] = -10.0
    neg("neg_revert_drift", st, "DRIFT", saves_expected=1, mode="REVERT")
    st2 = make_world()
    neg("neg_revert_drift_unapplied_scene", st2, "DRIFT", mode="REVERT")
    clean()
    # live pattern at other frames accepted when expected_key_frames is null
    st = make_world(frames=(3593, 4170))
    mk = run(m, st, mode="APPLY", confirm="APPLY CLAMOPEN", run="T-ANY", expected_key_frames=None,
             open_start_frame=4176, open_end_frame=4476)
    check("any_frames_when_null", mk.startswith("CLAMOPEN_APPLY_OK") and roll_frames(st)[2] == 4176, mk)
    clean()

    shutil.rmtree(tmp, ignore_errors=True)
    n = sum(1 for _, ok in RESULTS if ok)
    print("PLAN_DEFAULT_KEYS %s" % json.dumps(keys))
    print("CLAMOPEN_HARNESS|pass=%d|fail=%d|total=%d" % (n, len(RESULTS) - n, len(RESULTS)))
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
