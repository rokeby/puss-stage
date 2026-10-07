"""Scalar overrides on EXISTING material instances, nothing else (generalised from SteelGloss_20261007/steel_gloss_apply.py).

First use (Gary, 7 Oct): "the clam's mantle inners should pulsate gently, slightly moving the pearl too" ->
MI_PearlClam_Mantle + MI_PearlClam_Pearl_v2 BreathAmp/BreathPeriod (the breathing WPO already in their masters,
S3Millstone/s3_props_ue.py:721-722, default BreathAmp 0 = off; same Time + period = in phase).

ARGS (mi_scalars_args.json): {"mode": DRY|APPLY|REVERT, "confirm": "...", "label": "<run family, [A-Za-z0-9_]>",
  "targets": [{"mi": "/Game/...", "parent": "/Game/... (exact, gated)", "scalars": {name: value},
               "ranges": {name: [lo, hi]}}]}   every scalar needs a range; names must exist on the MI.
MODES
  DRY    guards + current values -> mi_scalars_dry_<label>_<run>.json; mutates nothing.
  APPLY  confirm "APPLY MISCALARS <label>". Guards -> record mi_scalars_record_<label>.json (fsync + read-back;
         refuses while an "applied" record exists) -> Backups/PreMiScalars-<label>-<stamp>/ (.uasset copies) ->
         set -> update_material_instance -> READ BACK (setters lie) -> dirty census (only the target MIs newly
         dirty) -> save_asset each MI -> read back after save -> MISCALARS_APPLY_OK.
  REVERT confirm "REVERT MISCALARS <label>": the recorded originals, same gates.
No graph edit, no level/Show write, never Save All, no UE objects at module level, refuses PIE.
Markers MISCALARS_*|run=<id>|label=<label>. MISCALARS_FAILED after a set: do NOT save; Don't-Save restart.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import sys

TOL = 1e-4


class MiError(RuntimeError):
    pass


# ============================================================================ pure planning (no unreal)
def check_args(args):
    p = []
    label = args.get("label", "")
    if not re.fullmatch(r"[A-Za-z0-9_]{1,40}", str(label)):
        p.append(f"label {label!r} must be [A-Za-z0-9_]{{1,40}}")
    targets = args.get("targets") or []
    if not targets:
        p.append("no targets")
    seen = set()
    for t in targets:
        mi = t.get("mi", "")
        if not str(mi).startswith("/Game/"):
            p.append(f"target mi {mi!r} not under /Game/")
        if mi in seen:
            p.append(f"{mi} listed twice")
        seen.add(mi)
        if not str(t.get("parent", "")).startswith("/Game/"):
            p.append(f"{mi}: parent missing")
        sc, rg = t.get("scalars") or {}, t.get("ranges") or {}
        if not sc:
            p.append(f"{mi}: no scalars")
        for n, v in sc.items():
            if n not in rg:
                p.append(f"{mi}.{n}: no range")
                continue
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                p.append(f"{mi}.{n}: {v!r} not a number")
                continue
            lo, hi = rg[n]
            if not float(lo) <= float(v) <= float(hi):
                p.append(f"{mi}.{n}: {v} outside {lo}..{hi}")
    return p


def mismatch(want, got, tol=TOL):
    return [f"{n} want {v} got {got.get(n)}" for n, v in want.items()
            if got.get(n) is None or abs(float(got[n]) - float(v)) > tol]


def dirty_problems(before, after, allowed):
    p = []
    extra = [x for x in sorted(set(after) - set(before)) if x not in allowed]
    if extra:
        p.append(f"unexpected newly dirty packages {extra}")
    missing = [a for a in allowed if a not in after]
    if missing:
        p.append(f"not dirty after the set (nothing changed?): {missing}")
    return p


def rel_of(mi_path):
    """/Game/A/B/MI_X -> ("Content", "A", "B", "MI_X.uasset")"""
    parts = mi_path[len("/Game/"):].split("/")
    return ("Content", *parts[:-1], parts[-1] + ".uasset")


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
        self.label = str(args.get("label", ""))
        self.repo = os.path.normpath(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()))
        self.stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run = "MIS-" + self.stamp
        self.record = os.path.join(here, f"mi_scalars_record_{self.label}.json")
        self.mutated = False

    def log(self, msg):
        self.u.log(msg)

    def fail(self, msg):
        tail = "|NOT saved: do not save; restart the editor with Don't Save" if self.mutated else ""
        self.u.log_error(f"MISCALARS_FAILED|run={self.run}|label={self.label}|mode={self.mode}|{msg}{tail}")
        raise MiError(f"MISCALARS_FAILED|run={self.run}|{msg}")

    def write_json(self, path, payload):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        with open(path, encoding="utf-8") as fh:
            if json.load(fh) != json.loads(json.dumps(payload)):
                self.fail(f"{os.path.basename(path)} did not read back")
        return path


def dirty_content(u):
    return sorted(_pk(p) for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages())


def load_all(c, targets):
    u = c.u
    if u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world() is not None:
        c.fail("PIE active")
    dirty = dirty_content(u)
    out = {}
    for t in targets:
        mi = u.EditorAssetLibrary.load_asset(t["mi"])
        if mi is None:
            c.fail(f"{t['mi']} does not load")
        par = _path(mi.get_editor_property("parent"))
        if par != t["parent"]:
            c.fail(f"{t['mi']}: parent is {par}, expected {t['parent']}")
        names = [str(n) for n in u.MaterialEditingLibrary.get_scalar_parameter_names(mi)]
        missing = [n for n in t["scalars"] if n not in names]
        if missing:
            c.fail(f"{t['mi']}: parameters missing {missing}")
        if t["mi"] in dirty:
            c.fail(f"{t['mi']} is already dirty (someone else's unsaved change)")
        out[t["mi"]] = mi
    return out


def read(c, mi, names):
    mel = c.u.MaterialEditingLibrary
    return {n: float(mel.get_material_instance_scalar_parameter_value(mi, n)) for n in names}


def backup(c):
    d = os.path.join(c.repo, "Backups", f"PreMiScalars-{c.label}-{c.stamp[:13]}")
    os.makedirs(d, exist_ok=True)
    out = []
    for t in c.args["targets"]:
        src = os.path.join(c.repo, *rel_of(t["mi"]))
        dst = os.path.join(d, os.path.basename(src))
        shutil.copy2(src, dst)
        if os.path.getsize(dst) != os.path.getsize(src):
            c.fail(f"backup size mismatch {dst}")
        out.append(dst)
    return out


def write_and_save(c, mis, wants, before):
    """wants: {mi_path: {name: value}}. Set all, read back, census, save each, read back again."""
    u, mel = c.u, c.u.MaterialEditingLibrary
    c.mutated = True
    for p, want in wants.items():
        for n, v in want.items():
            mel.set_material_instance_scalar_parameter_value(mis[p], n, float(v))   # return ignored: read back
        mel.update_material_instance(mis[p])
        bad = mismatch(want, read(c, mis[p], list(want)))
        if bad:
            c.fail(f"{p}: read-back after set: {bad}")
    prob = dirty_problems(before, dirty_content(u), list(wants))
    if prob:
        c.fail(f"dirty census: {prob}")
    final = {}
    for p, want in wants.items():
        if not u.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            c.fail(f"save_asset({p}) returned False")
        again = u.EditorAssetLibrary.load_asset(p)
        bad = mismatch(want, read(c, again, list(want)))
        if bad:
            c.fail(f"{p}: read-back after save: {bad}")
        final[p] = read(c, again, list(want))
    still = [p for p in wants if p in dirty_content(u)]
    if still:
        c.fail(f"still dirty after save: {still}")
    return final


def phase_dry(c):
    prob = check_args(c.args)
    if prob:
        c.fail(f"args refused: {prob}")
    mis = load_all(c, c.args["targets"])
    cur = {t["mi"]: read(c, mis[t["mi"]], list(t["scalars"])) for t in c.args["targets"]}
    out = {"run": c.run, "label": c.label, "mode": "DRY", "current": cur,
           "want": {t["mi"]: t["scalars"] for t in c.args["targets"]}, "other_dirty": dirty_content(c.u)}
    c.write_json(os.path.join(c.here, f"mi_scalars_dry_{c.label}_{c.run}.json"), out)
    c.log(f"MISCALARS_DRY_OK|run={c.run}|label={c.label}|current={json.dumps(cur)}")
    return out


def phase_apply(c):
    prob = check_args(c.args)
    if prob:
        c.fail(f"args refused: {prob}")
    if c.args.get("confirm") != f"APPLY MISCALARS {c.label}":
        c.fail(f"confirm string missing (APPLY MISCALARS {c.label})")
    if os.path.exists(c.record):
        with open(c.record, encoding="utf-8") as fh:
            if json.load(fh).get("state") in ("applying", "applied"):
                c.fail(f"{os.path.basename(c.record)} is applied/applying: REVERT or retire it first")
    mis = load_all(c, c.args["targets"])
    before = dirty_content(c.u)
    wants = {t["mi"]: t["scalars"] for t in c.args["targets"]}
    orig = {p: read(c, mis[p], list(w)) for p, w in wants.items()}
    rec = {"run": c.run, "label": c.label, "state": "applying", "originals": orig, "want": wants,
           "parents": {t["mi"]: t["parent"] for t in c.args["targets"]},
           "written": datetime.datetime.now().isoformat(timespec="seconds")}
    c.write_json(c.record, rec)
    rec["backup"] = backup(c)
    final = write_and_save(c, mis, wants, before)
    rec.update(state="applied", final=final)
    c.write_json(c.record, rec)
    c.log(f"MISCALARS_APPLY_OK|run={c.run}|label={c.label}|was={json.dumps(orig)}|now={json.dumps(final)}")
    return rec


def phase_revert(c):
    if c.args.get("confirm") != f"REVERT MISCALARS {c.label}":
        c.fail(f"confirm string missing (REVERT MISCALARS {c.label})")
    if not os.path.exists(c.record):
        c.fail(f"no {os.path.basename(c.record)}")
    with open(c.record, encoding="utf-8") as fh:
        rec = json.load(fh)
    if rec.get("state") != "applied":
        c.fail(f"record state {rec.get('state')} (not applied)")
    targets = [{"mi": p, "parent": rec["parents"][p], "scalars": v} for p, v in rec["originals"].items()]
    c.args = dict(c.args, targets=targets)
    mis = load_all(c, targets)
    before = dirty_content(c.u)
    bk = backup(c)
    final = write_and_save(c, mis, rec["originals"], before)
    rec.update(state="reverted", reverted_run=c.run, revert_backup=bk, final_after_revert=final)
    c.write_json(c.record, rec)
    c.log(f"MISCALARS_REVERT_OK|run={c.run}|label={c.label}|now={json.dumps(final)}")
    return rec


def main(here=None):
    u = _u()
    here = here or os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()),
                                "CodexConductor", "MiScalars")
    with open(os.path.join(here, "mi_scalars_args.json"), encoding="utf-8") as fh:
        args = json.load(fh)
    c = Ctx(u, here, args)
    phases = {"DRY": phase_dry, "APPLY": phase_apply, "REVERT": phase_revert}
    c.log(f"MISCALARS_START|run={c.run}|label={c.label}|mode={c.mode}")
    if c.mode not in phases:
        c.fail(f"unknown mode {c.mode}")
    try:
        return phases[c.mode](c)
    except MiError:
        raise
    except Exception as exc:  # an API surprise mid-phase still leaves a run-stamped failure marker
        c.fail(f"unexpected {type(exc).__name__}: {exc}")


if "unreal" in sys.modules and not getattr(sys.modules["unreal"], "_MISCALARS_FAKE", False):
    main()
