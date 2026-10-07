"""Offline harness for mi_scalars_apply.py: fake unreal, two-MI positive run + negative controls.
Run: python test_mi_scalars_apply.py -> MISCALARS_HARNESS n/n, non-zero exit on any failure."""
import copy
import json
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

A = "/Game/S3Props/PearlClam/MI_PearlClam_Mantle"
B = "/Game/S3Props/PearlClam/MI_PearlClam_Pearl_v2"
PA, PB = "/Game/S3Props/M_S3PropBreathe", "/Game/S3Props/PearlClam/M_PearlClam_Pearl_v2"
DEFAULTS = {A: {"BreathAmp": 0.0, "BreathPeriod": 5.0, "RoughnessMultiplier": 1.0},
            B: {"BreathAmp": 0.0, "BreathPeriod": 5.0, "Glow": 0.0}}
ARGS = {"mode": "APPLY", "confirm": "APPLY MISCALARS ClamBreath", "label": "ClamBreath", "targets": [
    {"mi": A, "parent": PA, "scalars": {"BreathAmp": 0.8, "BreathPeriod": 6.0},
     "ranges": {"BreathAmp": [0, 2], "BreathPeriod": [2, 20]}},
    {"mi": B, "parent": PB, "scalars": {"BreathAmp": 0.35, "BreathPeriod": 6.0},
     "ranges": {"BreathAmp": [0, 1], "BreathPeriod": [2, 20]}}]}


class Obj:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1]


class World:
    def __init__(self, root, **kw):
        self.root = root
        self.parents = {A: PA, B: PB}
        self.parents.update(kw.get("parents", {}))
        self.over = {A: {}, B: {}}
        self.dirty = set(kw.get("dirty", ()))
        self.pie = kw.get("pie", False)
        self.lie_on = kw.get("lie_on")              # MI whose setter claims success and does nothing
        self.collateral = kw.get("collateral")
        self.save_fail = kw.get("save_fail")
        self.missing = kw.get("missing", {})
        self.saved_calls, self.errors, self.logs = [], [], []

    def value(self, mi, n):
        return self.over[mi].get(n, DEFAULTS[mi][n])


def make_unreal(w):
    u = types.ModuleType("unreal")
    u._MISCALARS_FAKE = True
    u.log, u.log_error = w.logs.append, w.errors.append
    u.Paths = types.SimpleNamespace(convert_relative_path_to_full=lambda p: p, project_dir=lambda: w.root,
                                    project_saved_dir=lambda: os.path.join(w.root, "Saved"))
    ed = types.SimpleNamespace(get_game_world=lambda: object() if w.pie else None)
    u.UnrealEditorSubsystem = object
    u.get_editor_subsystem = lambda cls: ed

    class MI(Obj):
        def get_editor_property(self, name):
            assert name == "parent"
            return Obj(w.parents[self.path])

    mis = {A: MI(A), B: MI(B)}

    def setv(m, n, v):
        if w.lie_on != m.path:
            w.over[m.path][n] = v
        w.dirty.add(m.path)
        if w.collateral:
            w.dirty.add(w.collateral)
        return True

    def save(p, only_if_is_dirty=True):
        w.saved_calls.append(p)
        if w.save_fail == p:
            return False
        w.dirty.discard(p)
        return True

    u.MaterialEditingLibrary = types.SimpleNamespace(
        get_scalar_parameter_names=lambda m: [n for n in DEFAULTS[m.path] if n not in w.missing.get(m.path, ())],
        get_material_instance_scalar_parameter_value=lambda m, n: w.value(m.path, n),
        set_material_instance_scalar_parameter_value=setv, update_material_instance=lambda m: None)
    u.EditorAssetLibrary = types.SimpleNamespace(load_asset=lambda p: mis.get(p), save_asset=save)
    u.EditorLoadingAndSavingUtils = types.SimpleNamespace(get_dirty_content_packages=lambda: sorted(w.dirty))
    return u


def setup(args, **kw):
    root = tempfile.mkdtemp(prefix="mis_")
    here = os.path.join(root, "Saved", "CodexConductor", "MiScalars")
    os.makedirs(here)
    for p in (A, B):
        import mi_scalars_apply as m
        f = os.path.join(root, *m.rel_of(p))
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "wb") as fh:
            fh.write(b"uasset")
    with open(os.path.join(here, "mi_scalars_args.json"), "w", encoding="utf-8") as fh:
        json.dump(args, fh)
    w = World(root, **kw)
    sys.modules["unreal"] = make_unreal(w)
    import mi_scalars_apply as m
    return m, w, here


def set_args(here, args):
    with open(os.path.join(here, "mi_scalars_args.json"), "w", encoding="utf-8") as fh:
        json.dump(args, fh)


results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ""))
    except AssertionError as exc:
        results.append((name, False, str(exc)))


def expect_fail(args, needle, **kw):
    m, w, here = setup(args, **kw)
    try:
        m.main(here)
    except m.MiError as exc:
        assert needle in str(exc), f"failed for the wrong reason: {exc}"
        assert any("MISCALARS_FAILED" in e for e in w.errors), "no failure marker"
        return w
    raise AssertionError(f"did not fail (wanted {needle})")


def with_(**patch):
    a = copy.deepcopy(ARGS)
    a.update(patch)
    return a


def t_dry():
    m, w, here = setup(with_(mode="DRY"))
    out = m.main(here)
    assert out["current"][A]["BreathAmp"] == 0.0 and w.over == {A: {}, B: {}} and not w.dirty
    assert any("MISCALARS_DRY_OK" in l for l in w.logs)


def t_round_trip():
    m, w, here = setup(ARGS)
    rec = m.main(here)
    assert w.over[A] == {"BreathAmp": 0.8, "BreathPeriod": 6.0} and w.over[B]["BreathAmp"] == 0.35, w.over
    assert not w.dirty and sorted(w.saved_calls) == sorted([A, B]) and len(rec["backup"]) == 2
    assert all(os.path.exists(b) for b in rec["backup"])
    assert "RoughnessMultiplier" not in w.over[A] and "Glow" not in w.over[B], "touched foreign params"
    set_args(here, with_(mode="APPLY"))
    try:
        m.main(here)
        raise AssertionError("second APPLY over an applied record not refused")
    except m.MiError as exc:
        assert "applied/applying" in str(exc)
    set_args(here, {"mode": "REVERT", "confirm": "REVERT MISCALARS ClamBreath", "label": "ClamBreath"})
    rec2 = m.main(here)
    assert w.value(A, "BreathAmp") == 0.0 and w.value(B, "BreathPeriod") == 5.0 and rec2["state"] == "reverted"


def t_wrong_parent_no_write():
    w = expect_fail(ARGS, "parent is", parents={B: "/Game/X/M_Other"})
    assert w.over == {A: {}, B: {}}, "wrote before refusing"


bad_range = with_(targets=[dict(ARGS["targets"][0], scalars={"BreathAmp": 4.0, "BreathPeriod": 6.0})])
no_range = with_(targets=[dict(ARGS["targets"][0], ranges={"BreathPeriod": [2, 20]})])
case("DRY reads, mutates nothing", t_dry)
case("APPLY both, re-APPLY refused, REVERT", t_round_trip)
case("-control: wrong parent refused before any write", t_wrong_parent_no_write)
case("-control: lying setter on 2nd MI caught", lambda: expect_fail(ARGS, "read-back after set", lie_on=B))
case("-control: collateral dirty caught", lambda: expect_fail(ARGS, "dirty census", collateral="/Game/Other"))
case("-control: PIE refused", lambda: expect_fail(ARGS, "PIE active", pie=True))
case("-control: pre-dirty target refused", lambda: expect_fail(ARGS, "already dirty", dirty=[B]))
case("-control: out-of-range refused", lambda: expect_fail(bad_range, "outside"))
case("-control: scalar without range refused", lambda: expect_fail(no_range, "no range"))
case("-control: bad label refused", lambda: expect_fail(with_(label="a b"), "label"))
case("-control: wrong confirm refused", lambda: expect_fail(with_(confirm="APPLY MISCALARS Other"), "confirm"))
case("-control: save False caught", lambda: expect_fail(ARGS, "returned False", save_fail=B))
case("-control: missing param refused", lambda: expect_fail(ARGS, "parameters missing", missing={A: ("BreathAmp",)}))
case("-control: duplicate target refused", lambda: expect_fail(with_(targets=[ARGS["targets"][0]] * 2), "listed twice"))
case("-control: REVERT w/o record refused",
     lambda: expect_fail({"mode": "REVERT", "confirm": "REVERT MISCALARS ClamBreath", "label": "ClamBreath"}, "no mi_scalars_record"))
def t_foreign_dirty_ok():
    m, w, here = setup(ARGS, dirty=["/Game/Map/L"])
    m.main(here)
    assert w.dirty == {"/Game/Map/L"} and "/Game/Map/L" not in w.saved_calls, "saved or cleared a foreign package"


case("pre-existing foreign dirty tolerated, never saved", t_foreign_dirty_ok)

ok = sum(1 for _, p, _ in results if p)
for n, p, why in results:
    print(("PASS " if p else "FAIL ") + n + ("" if p else f"  <- {why}"))
print(f"MISCALARS_HARNESS {ok}/{len(results)}")
sys.exit(0 if ok == len(results) else 1)
