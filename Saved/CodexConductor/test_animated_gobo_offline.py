"""Offline positive/negative harness for P6 animated_gobo.py.

Run from the project root:
    python Saved/CodexConductor/test_animated_gobo_offline.py

No Unreal import is required and no project asset is touched.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import animated_gobo as ag  # noqa: E402


RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def raises(name, code, fn):
    try:
        fn()
        check(name, False, "did not raise")
    except ag.PlanError as exc:
        check(name, code in str(exc), str(exc))


OUT = ROOT / "Tools" / "ShadowGobo" / "P6_TestBird"
MANIFEST = OUT / "manifest.json"
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
ATLAS = OUT / manifest["atlas"]["file"]

RAW = {
    "mode": "DRY", "confirm": "DRY ANIMATED_GOBO", "run_id": "HARNESS",
    "sequence": "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips",
    "light_labels": ["Shadow Play Spot (Hangar)", "Shadow Play Spot (Mouth)"],
    "atlas_png": str(ATLAS), "manifest": str(MANIFEST),
    "mi_path": "/Game/InfinityStage/Lighting/Gobo/MI_ShadowGobo_P6_TestBird",
    "texture_path": "/Game/InfinityStage/Lighting/Gobo/T_Gobo_P6_TestBird_6x4",
    "frame_start": 175, "frame_end": 250,
}
ARGS = ag.normalized_args(RAW)
PLAN = ag.plan_from_args(ARGS)

# A. Test flipbook artifact.
image = Image.open(ATLAS)
check("A01 atlas is 2048 square", image.size == (2048, 2048), image.size)
check("A02 manifest has 24 frames", PLAN["atlas"]["frames"] == 24, PLAN["atlas"])
check("A03 manifest grid is 6x4", (PLAN["atlas"]["cols"], PLAN["atlas"]["rows"]) == (6, 4), PLAN["atlas"])
check("A04 playback is 3 seconds at 8 fps", manifest["take"]["duration_s"] == 3.0 and manifest["take"]["fps"] == 8.0)
check("A05 atlas SHA-256 is verified by planner", len(PLAN["atlas_sha256"]) == 64)
cell, gutter = PLAN["atlas"]["cell_px"], PLAN["atlas"]["gutter_px"]
pixels = image.load()
centres = [pixels[(i % 6) * cell + cell // 2, (i // 6) * cell + cell // 2] for i in range(24)]
check("A06 every used cell contains the black bird", all(v < 128 for v in centres), centres)
check("A07 contact and animated preview ship", (OUT / "contact.png").is_file() and (OUT / "preview.gif").is_file())
check("A08 gutter is non-zero and fits cell", 0 < gutter * 2 < cell, (gutter, cell))

# B. Pure plan and negative controls.
check("B01 frame keys map range to frame 0..23", PLAN["frame_keys"] == [[175, 0.0], [250, 23.0]], PLAN["frame_keys"])
check("B02 plan creates exactly master/MPC/texture/MI", PLAN["created_assets"] == [ag.MASTER, ag.MPC, RAW["texture_path"], RAW["mi_path"]])
check("B03 look defaults are Gary-tunable args", all(k in PLAN["params"] for k in ("BlurUV", "Softness", "Contrast", "Depth", "Scale", "FlipU", "FlipV")))
check("B04 planning is deterministic", ag.plan_from_args(ARGS)["digest"] == PLAN["digest"])
check("B05 DRY confirm exact", ag.confirm_ok("DRY", "DRY ANIMATED_GOBO") and not ag.confirm_ok("DRY", "APPLY ANIMATED_GOBO"))
check("B06 destructive REVERT confirm is explicit", ag.confirm_text("REVERT") == "REVERT ANIMATED_GOBO DELETE CREATED ASSETS")
raises("B07 -control empty labels", "LIGHT_LABELS", lambda: ag.normalized_args(dict(RAW, light_labels=[])))
raises("B08 -control duplicate labels", "LIGHT_LABELS", lambda: ag.normalized_args(dict(RAW, light_labels=["A", "A"])))
raises("B09 -control reversed frame range", "FRAME_RANGE", lambda: ag.normalized_args(dict(RAW, frame_start=250, frame_end=175)))
raises("B10 -control MI outside create-only root", "MI_PATH", lambda: ag.normalized_args(dict(RAW, mi_path="/Game/X/MI_Bad")))
raises("B11 -control texture outside create-only root", "TEXTURE_PATH", lambda: ag.normalized_args(dict(RAW, texture_path="/Game/X/T_Bad")))
raises("B12 -control unknown look parameter", "UNKNOWN_PARAMS", lambda: ag.normalized_args(dict(RAW, params={"BlurMagic": 1})))
raises("B13 -control invalid softness", "LOOK_PARAMS", lambda: ag.plan_from_args(ag.normalized_args(dict(RAW, params={"Softness": 0.8}))))
raises("B13b -control blur exceeds cell gutter", "LOOK_PARAMS", lambda: ag.plan_from_args(ag.normalized_args(dict(RAW, params={"BlurUV": 0.02}))))
raises("B14 -control missing atlas", "ATLAS_MISSING", lambda: ag.normalized_args(dict(RAW, atlas_png=str(OUT / "missing.png"))))

# C. Preflight positive and every important refusal.
CLEAN = {"pie": False, "sequencer_open": False, "world_ok": True,
         "census": {"content": [], "maps": []},
         "label_counts": {label: 1 for label in ARGS["light_labels"]},
         "record_exists": False, "existing_targets": [], "playback": [0, 2183]}
check("C01 positive DRY preflight", ag.preflight_refusals("DRY", ARGS, CLEAN, PLAN) == [])
cases = [
    ("PIE", {"pie": True}, "PIE_OR_SIE_ACTIVE"),
    ("Sequencer open", {"sequencer_open": True}, "SEQUENCER_IS_OPEN"),
    ("wrong world", {"world_ok": False}, "WRONG_WORLD"),
    ("dirty content", {"census": {"content": ["/Game/X"], "maps": []}}, "DIRTY_CENSUS"),
    ("dirty map", {"census": {"content": [], "maps": ["/Game/M"]}}, "DIRTY_CENSUS"),
    ("missing label", {"label_counts": dict(CLEAN["label_counts"], **{"Shadow Play Spot (Mouth)": 0})}, "LIGHT_LABEL_COUNT"),
    ("duplicate label", {"label_counts": dict(CLEAN["label_counts"], **{"Shadow Play Spot (Mouth)": 2})}, "LIGHT_LABEL_COUNT"),
    ("existing create target", {"existing_targets": [ag.MASTER]}, "CREATE_ONLY_TARGET_EXISTS"),
    ("existing record", {"record_exists": True}, "RECORD_EXISTS"),
    ("keys outside playback", {"playback": [200, 220]}, "KEYS_OUTSIDE_PLAYBACK"),
]
for label, delta, code in cases:
    state = copy.deepcopy(CLEAN)
    state.update(delta)
    got = ag.preflight_refusals("DRY", ARGS, state, PLAN)
    check("C -control %s" % label, any(code in row for row in got), got)
bad_confirm = dict(ARGS, confirm="APPLY ANIMATED_GOBO")
check("C12 -control confirm mismatch", any("CONFIRM_MISMATCH" in row for row in ag.preflight_refusals("DRY", bad_confirm, CLEAN, PLAN)))
verify_state = dict(CLEAN, record_exists=True, existing_targets=PLAN["created_assets"])
check("C13 VERIFY allows its recorded assets to exist", ag.preflight_refusals("VERIFY", dict(ARGS, confirm="VERIFY ANIMATED_GOBO"), verify_state, PLAN) == [])
check("C14 -control VERIFY without record", any("NOTHING_TO_VERIFY" in r for r in ag.preflight_refusals(
    "VERIFY", dict(ARGS, confirm="VERIFY ANIMATED_GOBO"), CLEAN, PLAN)))

# D. State model, exact read-back, and revert drift controls.
BEFORE = {"playback": [0, 2183], "lights": {label: None for label in ARGS["light_labels"]}, "track": None}
AFTER = ag.apply_model(BEFORE, PLAN)
RECORD = {"snapshot_before": BEFORE, "snapshot_after": AFTER}
check("D01 apply model assigns MI to both spots", all(AFTER["lights"][v] == PLAN["mi"] for v in ARGS["light_labels"]))
check("D02 apply model adds one named Frame track", AFTER["track"]["name"] == ag.TRACK_NAME and AFTER["track"]["keys"] == PLAN["frame_keys"])
check("D03 exact APPLY snapshot passes", ag.snapshot_diff(AFTER, RECORD["snapshot_after"]) == [])
check("D04 exact REVERT restores before", ag.revert_model(AFTER, RECORD) == BEFORE)
drift = copy.deepcopy(AFTER)
drift["track"]["keys"][1][1] = 22.5
check("D05 -control keyed frame drift is detected", bool(ag.snapshot_diff(drift, RECORD["snapshot_after"])))
drift = copy.deepcopy(AFTER)
drift["lights"][ARGS["light_labels"][0]] = "/Game/X/MI_HandEdit"
check("D06 -control light-function drift is detected", bool(ag.snapshot_diff(drift, RECORD["snapshot_after"])))
check("D07 exact dirty census passes", ag.exact_dirty({"content": PLAN["created_assets"] + [PLAN["sequence"]], "maps": []},
                                                       PLAN["created_assets"] + [PLAN["sequence"]]) == [])
check("D08 -control unexpected dirty package fails", bool(ag.exact_dirty(
    {"content": PLAN["created_assets"] + [PLAN["sequence"], "/Game/Other"], "maps": []},
    PLAN["created_assets"] + [PLAN["sequence"]])))
check("D09 -control dirty map fails", bool(ag.exact_dirty(
    {"content": PLAN["created_assets"] + [PLAN["sequence"]], "maps": ["/Game/Map"]},
    PLAN["created_assets"] + [PLAN["sequence"]])))

# E. Static safety contract: cheap but catches accidental erosion of house rules.
source = (HERE / "animated_gobo.py").read_text(encoding="utf-8")
runner = (HERE / "animated_gobo_run.py").read_text(encoding="utf-8")
check("E01 never deletes existing material expressions", "delete_all_material_expressions" not in source)
check("E02 never Save All/save_directory", "save_directory" not in source and "save_all" not in source.lower())
check("E03 all four operational modes ship", all(('"%s"' % mode) in source for mode in ag.MODES))
check("E04 record is exclusive before mutation", "_write_json(record_path, record, exclusive=True)" in source and
      source.index("_write_json(record_path, record, exclusive=True)") < source.index("# Mutation begins"))
check("E05 APPLY requires independent VERIFY", "APPLY_OK_PENDING_VERIFY" in source and "def run_verify" in source)
check("E06 success marker is generated from MARK", '"%s_SUCCESS|run=%s' in source)
check("E07 revert backs up before delete", source.index("PreAnimatedGoboRevert") < source.index("delete_asset(path)"))
check("E08 runner purges Saved module cache", "sys.modules.pop" in runner and "runpy.run_path" in runner)
check("E09 offline import did not load Unreal", ag.unreal is None)
check("E10 revert refuses external referencers before delete", source.index("REVERT_EXTERNAL_REFERENCERS") < source.index("delete_asset(path)"))
check("E11 existing make_gobo_flipbook manifest names are accepted", all(name in source for name in
      ("GoboCols", "GoboRows", "GoboFrames", "GoboGutterUV", "GoboCellUV")))

passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = [(name, detail) for name, ok, detail in RESULTS if not ok]
(OUT / "offline_harness_report.json").write_text(json.dumps({
    "marker": "ANIMATED_GOBO_HARNESS", "passed": passed, "failed": len(failed),
    "results": [{"name": name, "pass": ok, "detail": detail} for name, ok, detail in RESULTS],
}, indent=2, default=str) + "\n", encoding="utf-8")
for name, detail in failed:
    print("FAIL", name, str(detail)[:500])
print("ANIMATED_GOBO_HARNESS|pass=%d|fail=%d" % (passed, len(failed)))
sys.exit(1 if failed else 0)
