"""Girder steel: shinier painted steel (Gary, 7 Oct: "girder metal can be shinier painted steel").

TARGET: ONE existing asset, /Game/InfinityStage/RigAtmos/Underpass/Materials/MI_UP_Steel_Green.
It is the material the six Structures' girders, laced columns and knee brackets render
(girders_v3_originals_GV3A-20261007-024125.json; underpass_rig_apply.py:33,65). The deck underside
(MI_UP_Steel_Black) and the parent M_UP_PaintedSteel are NOT touched: no graph edit, no node delete
(memory: deleting nodes on pre-existing assets crashes the editor), no level write, no recompile
(scalar overrides only; no static switches).

Parent parameters (declaration-proven in underpass_materials.py:60-66, CODE_STEEL_BASE :110-123):
  PaintRoughness 0.62  roughness of the paint (dielectric: metallic is Chip*0.3, paint stays 0)
  ChipAmount     0.80  rust chips (rough 0.88, partly metallic) breaking through the paint
  StreakAmount   0.35  rust streaks bleeding down from the rivet band
  GrimeAmount    0.35  grime darkening of the paint
"Shinier painted steel" = lower paint roughness, and fewer rough rust chips/streaks so the gloss reads
as intact paint. The values live in steel_gloss_args.json ("scalars"), so a tuning pass is an args edit.

MODES (steel_gloss_args.json "mode"): DRY (default) | APPLY | REVERT
  DRY    guards + current values (override or inherited) -> steel_gloss_dry_<run>.json; mutates nothing.
  APPLY  guards -> originals record (fsync + read-back) -> Backups/PreSteelGloss-<run>/ (.uasset copy)
         -> set scalars -> update_material_instance -> READ BACK (setters lie) -> dirty census (only the
         MI's package newly dirty) -> save_asset(MI only) -> read back again -> STEEL_GLOSS_APPLY_OK.
  REVERT restores the recorded values from steel_gloss_record.json (backup first), same gates.
Never Save All; never reloads anything; no UE objects at module level.
Markers: STEEL_GLOSS_*|run=<id>. STEEL_GLOSS_FAILED after a set: do NOT save; Don't-Save restart.
Planning functions are Unreal-free for test_steel_gloss_apply.py.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import sys

MI_PATH = "/Game/InfinityStage/RigAtmos/Underpass/Materials/MI_UP_Steel_Green"
PARENT_PATH = "/Game/InfinityStage/RigAtmos/Underpass/Materials/M_UP_PaintedSteel"
MI_REL = ("Content", "InfinityStage", "RigAtmos", "Underpass", "Materials", "MI_UP_Steel_Green.uasset")
ALLOWED = ("PaintRoughness", "ChipAmount", "StreakAmount", "GrimeAmount")
RANGES = {"PaintRoughness": (0.08, 0.9), "ChipAmount": (0.0, 1.0), "StreakAmount": (0.0, 1.0),
          "GrimeAmount": (0.0, 1.0)}
TOL = 1e-4


class GlossError(RuntimeError):
    pass


# ============================================================================ pure planning (no unreal)
def check_want(want):
    """want: {name: value}. -> problems (empty = ok)."""
    p = []
    if not want:
        p.append("no scalars requested")
    for n, v in (want or {}).items():
        if n not in ALLOWED:
            p.append(f"{n}: not an allowed parameter {ALLOWED}")
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            p.append(f"{n}: value {v!r} is not a number")
            continue
        lo, hi = RANGES[n]
        if not lo <= float(v) <= hi:
            p.append(f"{n}: {v} outside {lo}..{hi}")
    return p


def mismatch(want, got, tol=TOL):
    """-> list of 'name want/got' for every requested value not read back within tol."""
    out = []
    for n, v in want.items():
        g = got.get(n)
        if g is None or abs(float(g) - float(v)) > tol:
            out.append(f"{n} want {v} got {g}")
    return out


def dirty_problems(before, after, allowed_pkg):
    """Content packages: nothing but allowed_pkg may become dirty; allowed_pkg must be dirty after."""
    p = []
    new = sorted(set(after) - set(before))
    extra = [x for x in new if x != allowed_pkg]
    if extra:
        p.append(f"unexpected newly dirty packages {extra}")
    if allowed_pkg not in after:
        p.append(f"{allowed_pkg} not dirty after the set (nothing changed?)")
    return p


# ============================================================================ unreal side
def _u():
    import unreal  # noqa: PLC0415  (the harness injects a fake into sys.modules)
    return unreal


def _pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s.split(".")[0]


def _path(o):
    return None if o is None else o.get_path_name().split(".")[0]


class Ctx:
    def __init__(self, u, here, args):
        self.u, self.here, self.args = u, here, args
        self.mode = str(args.get("mode", "DRY")).upper()
        self.repo = os.path.normpath(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
        self.run = "SGL-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.record = os.path.join(here, "steel_gloss_record.json")
        self.mutated = False

    def log(self, msg):
        self.u.log(msg)

    def fail(self, msg):
        tail = "|NOT saved: do not save; restart the editor with Don't Save" if self.mutated else ""
        self.u.log_error(f"STEEL_GLOSS_FAILED|run={self.run}|mode={self.mode}|{msg}{tail}")
        raise GlossError(f"STEEL_GLOSS_FAILED|run={self.run}|{msg}")

    def write_json(self, name, payload):
        path = os.path.join(self.here, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        with open(path, encoding="utf-8") as fh:
            if json.load(fh) != json.loads(json.dumps(payload)):
                self.fail(f"{name} did not read back")
        return path


def dirty_content(u):
    return sorted(_pk(p) for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages())


def load(c):
    u = c.u
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        c.fail("PIE active")
    mi = u.EditorAssetLibrary.load_asset(MI_PATH)
    if mi is None:
        c.fail(f"{MI_PATH} does not load")
    if _path(mi.get_editor_property("parent")) != PARENT_PATH:
        c.fail(f"parent is {_path(mi.get_editor_property('parent'))}, expected {PARENT_PATH}")
    names = [str(n) for n in u.MaterialEditingLibrary.get_scalar_parameter_names(mi)]
    missing = [n for n in ALLOWED if n not in names]
    if missing:
        c.fail(f"parameters missing on the MI: {missing}")
    if MI_PATH in dirty_content(u):
        c.fail(f"{MI_PATH} is already dirty (someone else's unsaved change)")
    return mi


def read(c, mi, names=ALLOWED):
    mel = c.u.MaterialEditingLibrary
    return {n: float(mel.get_material_instance_scalar_parameter_value(mi, n)) for n in names}


def overridden(mi):
    """Names with an explicit override on the MI (vs inherited from the parent)."""
    out = []
    for pv in mi.get_editor_property("scalar_parameter_values") or []:
        info = pv.get_editor_property("parameter_info")
        out.append(str(info.get_editor_property("name")))
    return sorted(out)


def write_values(c, mi, want):
    mel = c.u.MaterialEditingLibrary
    c.mutated = True
    for n, v in want.items():
        mel.set_material_instance_scalar_parameter_value(mi, n, float(v))   # return value ignored: read back
    mel.update_material_instance(mi)
    bad = mismatch(want, read(c, mi, list(want)))
    if bad:
        c.fail(f"read-back after set: {bad}")


def backup(c):
    src = os.path.join(c.repo, *MI_REL)
    dst_dir = os.path.join(c.repo, "Backups", "PreSteelGloss-" + c.run[4:17])
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    if os.path.getsize(dst) != os.path.getsize(src):
        c.fail(f"backup size mismatch {dst}")
    return dst


def save_and_verify(c, mi, want, before_dirty):
    u = c.u
    after = dirty_content(u)
    prob = dirty_problems(before_dirty, after, MI_PATH)
    if prob:
        c.fail(f"dirty census: {prob}")
    if not u.EditorAssetLibrary.save_asset(MI_PATH, only_if_is_dirty=False):
        c.fail("save_asset returned False")
    if MI_PATH in dirty_content(u):
        c.fail("MI still dirty after save")
    again = u.EditorAssetLibrary.load_asset(MI_PATH)
    bad = mismatch(want, read(c, again, list(want)))
    if bad:
        c.fail(f"read-back after save: {bad}")
    return read(c, again)


def phase_dry(c):
    want = c.args.get("scalars", {})
    prob = check_want(want)
    mi = load(c)
    cur = read(c, mi)
    out = {"run": c.run, "mode": "DRY", "mi": MI_PATH, "current": cur, "overridden": overridden(mi),
           "want": want, "problems": prob, "other_dirty": dirty_content(c.u)}
    c.write_json(f"steel_gloss_dry_{c.run}.json", out)
    if prob:
        c.fail(f"args refused: {prob}")
    c.log(f"STEEL_GLOSS_DRY_OK|run={c.run}|current={json.dumps(cur)}|want={json.dumps(want)}")
    return out


def phase_apply(c):
    want = c.args.get("scalars", {})
    prob = check_want(want)
    if prob:
        c.fail(f"args refused: {prob}")
    if c.args.get("confirm") != "APPLY STEELGLOSS":
        c.fail("confirm string missing (APPLY STEELGLOSS)")
    mi = load(c)
    before = dirty_content(c.u)
    cur = read(c, mi)
    rec = {"run": c.run, "state": "applying", "mi": MI_PATH, "originals": cur, "overridden_before": overridden(mi),
           "want": want, "written": datetime.datetime.now().isoformat(timespec="seconds")}
    c.write_json("steel_gloss_record.json", rec)
    rec["backup"] = backup(c)
    write_values(c, mi, want)
    final = save_and_verify(c, mi, want, before)
    rec.update(state="applied", final=final)
    c.write_json("steel_gloss_record.json", rec)
    c.log(f"STEEL_GLOSS_APPLY_OK|run={c.run}|was={json.dumps(cur)}|now={json.dumps(final)}")
    return rec


def phase_revert(c):
    if c.args.get("confirm") != "REVERT STEELGLOSS":
        c.fail("confirm string missing (REVERT STEELGLOSS)")
    if not os.path.exists(c.record):
        c.fail("no steel_gloss_record.json")
    with open(c.record, encoding="utf-8") as fh:
        rec = json.load(fh)
    if rec.get("state") != "applied":
        c.fail(f"record state {rec.get('state')} (not applied)")
    want = rec["originals"]
    mi = load(c)
    before = dirty_content(c.u)
    bk = backup(c)
    write_values(c, mi, want)
    final = save_and_verify(c, mi, want, before)
    rec.update(state="reverted", reverted_run=c.run, revert_backup=bk, final_after_revert=final)
    c.write_json("steel_gloss_record.json", rec)
    c.log(f"STEEL_GLOSS_REVERT_OK|run={c.run}|now={json.dumps(final)}")
    return rec


def main(here=None):
    u = _u()
    here = here or os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()),
                                "CodexConductor", "SteelGloss_20261007")
    with open(os.path.join(here, "steel_gloss_args.json"), encoding="utf-8") as fh:
        args = json.load(fh)
    c = Ctx(u, here, args)
    phases = {"DRY": phase_dry, "APPLY": phase_apply, "REVERT": phase_revert}
    c.log(f"STEEL_GLOSS_START|run={c.run}|mode={c.mode}")
    if c.mode not in phases:
        c.fail(f"unknown mode {c.mode}")
    try:
        return phases[c.mode](c)
    except GlossError:
        raise
    except Exception as exc:  # an API surprise mid-phase still leaves a run-stamped failure marker
        c.fail(f"unexpected {type(exc).__name__}: {exc}")


if "unreal" in sys.modules and not getattr(sys.modules["unreal"], "_STEEL_GLOSS_FAKE", False):
    main()
