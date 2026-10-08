"""Offline harness for P12 dense handprints.  Includes positive and seeded negative controls."""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import statistics
import sys
import traceback
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hp_dense_core as core
import hp_dense_layout as layout

CONFIG = json.loads((HERE / "hp_dense_config.json").read_text(encoding="utf-8"))
TABLE = json.loads((HERE / "placement_S03_dense.json").read_text(encoding="utf-8"))
REPORT = HERE / "test_hp_dense_report.json"
CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn)); return fn
    return deco


def expect_error(fn, token):
    try:
        fn()
    except Exception as exc:
        assert token in str(exc), (token, exc)
        return
    raise AssertionError("expected " + token)


@case("default table validates; exactly 2x the 99 source-band marks")
def _():
    assert core.validate_table(TABLE)
    assert TABLE["source_band_count"] == 99 and TABLE["target_count"] == len(TABLE["decals"]) == 198


@case("positive band gate: right wall only and every rotated extent is inside")
def _():
    alo, ahi = TABLE["band"]["along_cm"]; zlo, zhi = TABLE["band"]["height_cm"]
    assert all(r["wall"] == "R" and alo <= r["along_extent_cm"][0] <= r["along_extent_cm"][1] <= ahi and
               zlo <= r["low_extent_cm"] <= r["high_extent_cm"] <= zhi for r in TABLE["decals"])


@case("negative control: one mark moved 1 cm outside the band is caught")
def _():
    bad = copy.deepcopy(TABLE); bad["decals"][0]["along_extent_cm"][0] = bad["band"]["along_cm"][0] - 1
    expect_error(lambda: core.validate_table(bad), "OUTSIDE_ALONG_BAND")


@case("determinism: same seed is canonical-identical; seed+1 differs")
def _():
    a = layout.build(CONFIG); b = layout.build(CONFIG); c = layout.build(CONFIG, seed=CONFIG["seed"] + 1)
    assert core.digest(a) == core.digest(b)
    assert core.digest(a) != core.digest(c)


@case("density argument controls the exact band count")
def _():
    d = layout.build(CONFIG, density=1.5)
    assert len(d["decals"]) == round(d["source_band_count"] * 1.5) == 148


@case("desperate vocabulary exists: pairs, scratches, drags, clusters, overlaps")
def _():
    kinds = TABLE["stats"]["by_kind"]
    assert kinds["reach_pair"] >= 40 and kinds["finger_scratch"] >= 50
    assert kinds["drag_smear"] >= 1 and kinds["cluster"] >= 20
    pairs = TABLE["decals"]
    rounded = [(round(r["along_cm"] / 10), round(r["height_cm"] / 10)) for r in pairs]
    assert len(set(rounded)) < len(rounded)  # visibly overlapping marks, not a uniform ladder


@case("finger scratches are long/thin and sit below reaching-print maxima")
def _():
    scratches = [r for r in TABLE["decals"] if r["event_kind"] == "finger_scratch"]
    assert statistics.median(max(r["size_cm"]) / max(0.01, min(r["size_cm"])) for r in scratches) > 2.5
    by_event = {}
    for r in TABLE["decals"]: by_event.setdefault(r["event"], []).append(r)
    assert all(any(p["event_kind"] == "reach_pair" and p["height_cm"] > s["height_cm"] for p in by_event[s["event"]])
               for s in scratches)


@case("upward trails have substantial rise and are not one repeated step")
def _():
    rises, gaps = [], []
    for event in sorted({r["event"] for r in TABLE["decals"]}):
        hs = sorted(r["height_cm"] for r in TABLE["decals"] if r["event"] == event and r["event_kind"] == "reach_pair")
        if len(hs) >= 4:
            rises.append(hs[-1] - hs[0]); gaps.extend(round(hs[i+1] - hs[i], 1) for i in range(len(hs)-1))
    assert len(rises) >= 4 and statistics.median(rises) > 120
    assert len(set(gaps)) > 8


@case("Gary dried-blood core is the selected parameter set")
def _():
    p = TABLE["material"]["dark_parameters"]
    assert TABLE["material"]["dark_preset"] == "dried_blood_core"
    assert p["color_linear"] == [0.155, 0.007, 0.005, 1.0] and p["strength"] == 0.55
    assert p["lo"] == 0.45 and p["hi"] == 0.75


@case("dark MI worklist is unique and covers every used sheen MI")
def _():
    work = TABLE["dark_mi_worklist"]
    assert len(work) == TABLE["stats"]["distinct_sheen_mis"] == 32
    assert len({w["dark"] for w in work}) == len(work)
    assert {w["sheen"] for w in work} == set(TABLE["mi_used"])


@case("random-draw lint: no source line draws twice")
def _():
    text = (HERE / "hp_dense_layout.py").read_text(encoding="utf-8")
    bad = [(n, line) for n, line in enumerate(text.splitlines(), 1) if line.count("rng.random()") > 1]
    assert not bad, bad


@case("preview positive control: all three PNGs exist with expected dimensions")
def _():
    for name, size in (("p12_b06_old.png", (1200, 650)), ("p12_b06_new.png", (1200, 650)),
                       ("p12_b06_old_vs_new.png", (2400, 650))):
        with Image.open(HERE / "previews" / name) as im: assert im.size == size


@case("fake world positive control: apply makes twins and revert is lossless")
def _():
    old = [{"tag": "HP_S03G", "label": "g", "x": 1}, {"tag": "HP_S03T", "label": "t", "x": 2}]
    snap, dense = core.simulate_apply(old, TABLE["decals"][:3])
    assert len(dense) == 6 and {x["tag"] for x in dense} == {"HP_S03D", "HP_S03D_CORE"}
    assert core.simulate_revert(snap, dense) == old


@case("fake world negative control: foreign source and foreign dense actors refuse")
def _():
    expect_error(lambda: core.simulate_apply([{"tag": "FOREIGN"}], TABLE["decals"][:1]), "FOREIGN")
    expect_error(lambda: core.simulate_revert([], [{"tag": "FOREIGN"}]), "FOREIGN_DENSE")


@case("destructive confirm strings are exact")
def _():
    for mode in ("ASSET_APPLY", "APPLY", "REVERT"):
        expect_error(lambda mode=mode: core.check_confirm(mode, "wrong"), "CONFIRM_MISSING")
        core.check_confirm(mode, core.confirm_text(mode))


@case("editor static safety: full modes, backups, census, named saves, no forbidden calls")
def _():
    text = (HERE / "hp_dense_editor.py").read_text(encoding="utf-8")
    for token in core.MODES: assert '"%s"' % token in text
    for token in ("PreP12HandprintMaterials-", "PreP12Handprints-", "PreP12HandprintsRevert-",
                  "DIRTY_AT_START", "CENSUS_NOT_EXACT_LEVEL", "save_loaded_asset", "save_current_level"):
        assert token in text
    lowered = text.lower()
    for forbidden in ("save_all", "delete_asset", "editor_request_end_play", "quit_editor", "load_map"):
        assert forbidden not in lowered


@case("success markers follow save and post-save assertions")
def _():
    text = (HERE / "hp_dense_editor.py").read_text(encoding="utf-8")
    assert text.index("P12_DENSE_APPLY_SUCCESS") > text.index("save_level(world")
    assert text.index("P12_DENSE_REVERT_SUCCESS") > text.index("REVERT_POST_SAVE_DIRTY")
    assert text.index("P12_DENSE_ASSET_VERIFY_SUCCESS") > text.index("ASSET_VERIFY_DIRTIED")


def main():
    results = []
    for name, fn in CASES:
        try:
            fn(); results.append({"name": name, "ok": True}); print("ok - " + name)
        except Exception as exc:
            results.append({"name": name, "ok": False, "error": repr(exc), "trace": traceback.format_exc()})
            print("NOT OK - %s: %r" % (name, exc))
    failed = sum(not r["ok"] for r in results)
    REPORT.write_text(json.dumps({"schema": "hp_dense_test/1", "ran": len(results), "fail": failed,
                                  "results": results}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("P12_DENSE_TESTS|ran=%d|fail=%d" % (len(results), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
