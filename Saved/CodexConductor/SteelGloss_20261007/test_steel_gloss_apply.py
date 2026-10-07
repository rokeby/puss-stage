"""Offline harness for steel_gloss_apply.py: fake unreal, positive run + negative controls.
Run: python test_steel_gloss_apply.py  -> prints STEEL_GLOSS_HARNESS n/n and exits non-zero on any failure."""
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PARENT = "/Game/InfinityStage/RigAtmos/Underpass/Materials/M_UP_PaintedSteel"
MI = "/Game/InfinityStage/RigAtmos/Underpass/Materials/MI_UP_Steel_Green"
DEFAULTS = {"PaintRoughness": 0.62, "ChipAmount": 0.8, "StreakAmount": 0.35, "GrimeAmount": 0.35,
            "RustRoughness": 0.88}


class Obj:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1]


class FakeMI(Obj):
    def __init__(self, world):
        super().__init__(MI)
        self.w = world

    def get_editor_property(self, name):
        if name == "parent":
            return Obj(self.w.parent)
        if name == "scalar_parameter_values":
            out = []
            for n in self.w.over:
                info = types.SimpleNamespace(get_editor_property=lambda k, n=n: n)
                out.append(types.SimpleNamespace(get_editor_property=lambda k, i=info: i))
            return out
        raise KeyError(name)


class World:
    def __init__(self, root, **kw):
        self.root, self.parent, self.pie = root, PARENT, kw.get("pie", False)
        self.over = dict(kw.get("over", {}))
        self.saved = dict(self.over)
        self.dirty = set(kw.get("dirty", ()))
        self.lie = kw.get("lie", False)            # setter claims success, changes nothing
        self.collateral = kw.get("collateral")     # another package dirtied by the set
        self.save_ok = kw.get("save_ok", True)
        self.missing = kw.get("missing", ())
        self.errors, self.logs = [], []

    def value(self, n):
        return self.over.get(n, DEFAULTS[n])


def make_unreal(w):
    u = types.ModuleType("unreal")
    u._STEEL_GLOSS_FAKE = True
    u.log = w.logs.append
    u.log_error = w.errors.append
    u.Paths = types.SimpleNamespace(convert_relative_path_to_full=lambda p: p,
                                    project_dir=lambda: w.root, project_saved_dir=lambda: os.path.join(w.root, "Saved"))
    ed = types.SimpleNamespace(get_game_world=lambda: object() if w.pie else None)
    u.UnrealEditorSubsystem = object
    u.get_editor_subsystem = lambda cls: ed
    mi = FakeMI(w)

    def setv(m, n, v):
        if not w.lie:
            w.over[n] = v
        w.dirty.add(MI)
        if w.collateral:
            w.dirty.add(w.collateral)
        return True

    def save(path, only_if_is_dirty=True):
        if not w.save_ok:
            return False
        w.saved = dict(w.over)
        w.dirty.discard(path)
        return True

    u.MaterialEditingLibrary = types.SimpleNamespace(
        get_scalar_parameter_names=lambda m: [n for n in DEFAULTS if n not in w.missing],
        get_material_instance_scalar_parameter_value=lambda m, n: w.value(n),
        set_material_instance_scalar_parameter_value=setv,
        update_material_instance=lambda m: None)
    u.EditorAssetLibrary = types.SimpleNamespace(load_asset=lambda p: mi if p == MI else None, save_asset=save)
    u.EditorLoadingAndSavingUtils = types.SimpleNamespace(get_dirty_content_packages=lambda: sorted(w.dirty))
    return u


def setup(args, **kw):
    root = tempfile.mkdtemp(prefix="sgl_")
    here = os.path.join(root, "Saved", "CodexConductor", "SteelGloss_20261007")
    os.makedirs(here)
    mdir = os.path.join(root, "Content", "InfinityStage", "RigAtmos", "Underpass", "Materials")
    os.makedirs(mdir)
    with open(os.path.join(mdir, "MI_UP_Steel_Green.uasset"), "wb") as fh:
        fh.write(b"uasset-bytes")
    with open(os.path.join(here, "steel_gloss_args.json"), "w", encoding="utf-8") as fh:
        json.dump(args, fh)
    w = World(root, **kw)
    sys.modules["unreal"] = make_unreal(w)
    import steel_gloss_apply as m
    return m, w, here


WANT = {"PaintRoughness": 0.3, "ChipAmount": 0.45, "StreakAmount": 0.2, "GrimeAmount": 0.25}
APPLY = {"mode": "APPLY", "confirm": "APPLY STEELGLOSS", "scalars": WANT}
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
    except m.GlossError as exc:
        assert needle in str(exc), f"failed for the wrong reason: {exc}"
        assert any("STEEL_GLOSS_FAILED" in e for e in w.errors), "no failure marker logged"
        return m, w, here
    raise AssertionError(f"did not fail (wanted {needle})")


def t_dry():
    m, w, here = setup({"mode": "DRY", "scalars": WANT})
    out = m.main(here)
    assert out["current"]["PaintRoughness"] == 0.62 and w.over == {} and not w.dirty, "DRY mutated"
    assert any("STEEL_GLOSS_DRY_OK" in l for l in w.logs)


def t_apply_revert():
    m, w, here = setup(APPLY)
    rec = m.main(here)
    assert w.saved == WANT and not w.dirty, (w.saved, w.dirty)
    assert rec["originals"]["PaintRoughness"] == 0.62 and rec["state"] == "applied"
    assert os.path.exists(rec["backup"]), "no backup"
    assert any("STEEL_GLOSS_APPLY_OK" in l for l in w.logs)
    with open(os.path.join(here, "steel_gloss_args.json"), "w", encoding="utf-8") as fh:
        json.dump({"mode": "REVERT", "confirm": "REVERT STEELGLOSS"}, fh)
    rec2 = m.main(here)
    assert all(abs(w.value(n) - DEFAULTS[n]) < 1e-9 for n in WANT) and rec2["state"] == "reverted"


def t_untouched_params():
    m, w, here = setup(APPLY)
    m.main(here)
    assert "RustRoughness" not in w.over, "touched a parameter outside the request"


case("DRY reads, mutates nothing", t_dry)
case("APPLY then REVERT round-trip", t_apply_revert)
case("APPLY writes only requested params", t_untouched_params)
case("-control: lying setter caught", lambda: expect_fail(APPLY, "read-back after set", lie=True))
case("-control: collateral dirty caught", lambda: expect_fail(APPLY, "dirty census", collateral="/Game/Other"))
case("-control: PIE refused", lambda: expect_fail(APPLY, "PIE active", pie=True))
case("-control: pre-dirty MI refused", lambda: expect_fail(APPLY, "already dirty", dirty=[MI]))
case("-control: out-of-range refused", lambda: expect_fail(dict(APPLY, scalars={"PaintRoughness": 0.01}), "outside"))
case("-control: foreign param refused", lambda: expect_fail(dict(APPLY, scalars={"RustRoughness": 0.2}), "not an allowed"))
case("-control: no confirm refused", lambda: expect_fail(dict(APPLY, confirm=""), "confirm"))
case("-control: save False caught", lambda: expect_fail(APPLY, "save_asset returned False", save_ok=False))
case("-control: missing param refused", lambda: expect_fail(APPLY, "parameters missing", missing=("ChipAmount",)))
case("-control: REVERT w/o record refused", lambda: expect_fail({"mode": "REVERT", "confirm": "REVERT STEELGLOSS"}, "no steel_gloss_record"))


def t_wrong_parent():
    m, w, here = setup(APPLY)
    w.parent = "/Game/Other/M_X"
    try:
        m.main(here)
    except m.GlossError as exc:
        assert "parent is" in str(exc)
        assert w.over == {}, "mutated before refusing"
        return
    raise AssertionError("wrong parent not refused")


case("-control: wrong parent refused before any write", t_wrong_parent)

ok = sum(1 for _, p, _ in results if p)
for n, p, why in results:
    print(("PASS " if p else "FAIL ") + n + ("" if p else f"  <- {why}"))
print(f"STEEL_GLOSS_HARNESS {ok}/{len(results)}")
sys.exit(0 if ok == len(results) else 1)
