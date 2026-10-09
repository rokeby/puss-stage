"""Offline positive and negative controls for q17/ragged_opening_swap.py."""
from __future__ import annotations

import importlib.util
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("q17_ragged_opening_swap", os.path.join(HERE, "ragged_opening_swap.py"))
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

passed = []
failed = []


def check(name, fn):
    try:
        fn()
        passed.append(name)
    except Exception as exc:  # noqa: BLE001 - harness records every failure.
        failed.append((name, repr(exc)))


def rejects(name, fn, text):
    def body():
        try:
            fn()
        except MOD.PlanError as exc:
            assert text in str(exc), (text, str(exc))
            return
        raise AssertionError("did not reject")
    check(name, body)


def opening(path=MOD.SOURCE_CACHE):
    return {
        "sequence": MOD.OPENING_SEQUENCE,
        "binding": MOD.OPENING_BINDING,
        "template_asset": path,
        "sections": [
            {"range": [0, 49], "asset": path, "start_frame_offset": 23200, "end_frame_offset": 240799, "play_rate": 1.0},
            {"range": [49, 299], "asset": path, "start_frame_offset": 23200, "end_frame_offset": 0, "play_rate": 1.0},
            {"range": [299, 375], "asset": path, "start_frame_offset": 263999, "end_frame_offset": 0, "play_rate": 1.0},
        ],
    }


def transitions(asset=MOD.SOURCE_CACHE):
    return [{"sequence": p, "binding": "Transition Drape (baked)", "range": [0, 1], "asset": asset,
             "start_frame_offset": 0, "end_frame_offset": 0, "play_rate": 1.0}
            for p in MOD.TRANSITION_SEQUENCES]


check("POS validate DRY", lambda: MOD.validate_args({"mode": "DRY", "confirm": MOD.CONFIRMS["DRY"]}))
check("POS validate APPLY", lambda: MOD.validate_args({"mode": "APPLY", "confirm": MOD.CONFIRMS["APPLY"], "decided_by": "Gary"}))
check("POS validate REVERT", lambda: MOD.validate_args({"mode": "REVERT", "confirm": MOD.CONFIRMS["REVERT"], "decided_by": "Gary"}))
check("POS swap four fields", lambda: (
    (lambda got: (
        (_ for _ in ()).throw(AssertionError(got))
        if [got["template_asset"]] + [s["asset"] for s in got["sections"]] != [MOD.TARGET_CACHE] * 4 else None
    ))(MOD.replace_opening_assets(opening(), MOD.SOURCE_CACHE, MOD.TARGET_CACHE))
))
check("POS swap preserves timing", lambda: (
    (lambda before, after: (
        (_ for _ in ()).throw(AssertionError(after))
        if [{k: v for k, v in s.items() if k != "asset"} for s in before["sections"]]
        != [{k: v for k, v in s.items() if k != "asset"} for s in after["sections"]] else None
    ))(opening(), MOD.replace_opening_assets(opening(), MOD.SOURCE_CACHE, MOD.TARGET_CACHE))
))
check("POS input unmodified", lambda: (
    (lambda src: (
        MOD.replace_opening_assets(src, MOD.SOURCE_CACHE, MOD.TARGET_CACHE),
        (_ for _ in ()).throw(AssertionError(src)) if src != opening() else None
    ))(opening())
))
check("POS transition counts", lambda: (
    (_ for _ in ()).throw(AssertionError("counts"))
    if MOD.transition_guard(transitions()) != {p: 1 for p in MOD.TRANSITION_SEQUENCES} else None
))
check("POS transition extra source row", lambda: MOD.transition_guard(transitions() + [dict(transitions()[0], binding="Sleight")]))

rejects("NEG bad mode", lambda: MOD.validate_args({"mode": "GO", "confirm": "GO"}), "MODE_INVALID")
rejects("NEG dry confirm", lambda: MOD.validate_args({"mode": "DRY", "confirm": "DRY"}), "CONFIRM_MISMATCH")
rejects("NEG apply confirm", lambda: MOD.validate_args({"mode": "APPLY", "confirm": "APPLY", "decided_by": "Gary"}), "CONFIRM_MISMATCH")
rejects("NEG revert confirm", lambda: MOD.validate_args({"mode": "REVERT", "confirm": "REVERT", "decided_by": "Gary"}), "CONFIRM_MISMATCH")
rejects("NEG apply decision", lambda: MOD.validate_args({"mode": "APPLY", "confirm": MOD.CONFIRMS["APPLY"]}), "DECIDED_BY_REQUIRED")
rejects("NEG revert decision", lambda: MOD.validate_args({"mode": "REVERT", "confirm": MOD.CONFIRMS["REVERT"]}), "DECIDED_BY_REQUIRED")
rejects("NEG template drift", lambda: MOD.replace_opening_assets(opening(MOD.TARGET_CACHE), MOD.SOURCE_CACHE, MOD.TARGET_CACHE), "OPENING_CACHE_FIELDS")
rejects("NEG section drift", lambda: (
    (lambda snap: MOD.replace_opening_assets(snap, MOD.SOURCE_CACHE, MOD.TARGET_CACHE))(
        (lambda snap: (snap["sections"][1].update(asset=MOD.TARGET_CACHE), snap)[1])(opening())
    )
), "OPENING_CACHE_FIELDS")
rejects("NEG section count", lambda: MOD.replace_opening_assets(
    (lambda snap: (snap["sections"].pop(), snap)[1])(opening()), MOD.SOURCE_CACHE, MOD.TARGET_CACHE
), "OPENING_CACHE_FIELDS")
rejects("NEG transition target", lambda: MOD.transition_guard(transitions(MOD.TARGET_CACHE)), "TRANSITION_ALREADY_USES_TARGET")
rejects("NEG transition missing sequence", lambda: MOD.transition_guard(transitions()[:-1]), "TRANSITION_SOURCE_REFERENCE_MISSING")

for name in passed:
    print("PASS|" + name)
for name, detail in failed:
    print("FAIL|%s|%s" % (name, detail))
print("Q17_OFFLINE_HARNESS|passed=%d|failed=%d|positive=8|negative=11" % (len(passed), len(failed)))
raise SystemExit(1 if failed else 0)
