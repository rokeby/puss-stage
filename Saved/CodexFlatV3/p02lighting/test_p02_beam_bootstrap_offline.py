"""Offline +/- harness for Job 105.  Does not import or call Unreal."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p02_beam_bootstrap", HERE / "p02_beam_bootstrap.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name)


def rejects(name, fn, token):
    try:
        fn()
    except Exception as error:  # noqa: BLE001 - deliberate negative controls
        check(name, token in str(error))
    else:
        check(name, False)


# Positive argument controls.
dry = tool.check_args({})
check("positive: default mode DRY", dry["mode"] == "DRY")
check("positive: exact four fixed ordinals", dry["ordinals"] == [3, 7, 12, 20])
check("positive: fixed cap four", dry["max_actors"] == 4)
apply = tool.check_args({"mode": "APPLY", "confirm": "APPLY P02BEAMBOOTSTRAP",
                         "expected_plan_sha256": "a" * 64})
check("positive: APPLY exact confirmation", apply["mode"] == "APPLY")
revert = tool.check_args({"mode": "REVERT", "confirm": "REVERT P02BEAMBOOTSTRAP"})
check("positive: REVERT exact confirmation", revert["mode"] == "REVERT")

# Negative argument controls.
rejects("negative: args must be object", lambda: tool.check_args([]), "ARGS_NOT_OBJECT")
rejects("negative: unknown arg", lambda: tool.check_args({"surprise": 1}), "ARGS_UNKNOWN")
rejects("negative: bad mode", lambda: tool.check_args({"mode": "GO"}), "MODE_INVALID")
rejects("negative: APPLY confirmation", lambda: tool.check_args({"mode": "APPLY",
        "confirm": "APPLY PASSAGELIGHT", "expected_plan_sha256": "a" * 64}), "CONFIRM_MISSING")
rejects("negative: APPLY plan hash required", lambda: tool.check_args({"mode": "APPLY",
        "confirm": "APPLY P02BEAMBOOTSTRAP"}), "EXPECTED_PLAN_SHA256_REQUIRED")
rejects("negative: REVERT confirmation", lambda: tool.check_args({"mode": "REVERT"}), "CONFIRM_MISSING")
rejects("negative: ordinal scope cannot expand", lambda: tool.check_args({"ordinals": [3, 7, 12, 20, 21]}),
        "ORDINALS_FIXED")
rejects("negative: actor cap cannot expand", lambda: tool.check_args({"max_actors": 5}), "MAX_ACTORS_FIXED")
rejects("negative: pinned source hash cannot change", lambda: tool.check_args({
        "expected_source_record_sha256": "0" * 64}), "SOURCE_RECORD_SHA_ARG_DRIFT")

# Positive record extraction against the actual P01 APPLY record.
source_record_path = HERE.parents[1] / "CodexConductor" / "Effects_20261007" / "p01_atmos_record.json"
record = json.loads(source_record_path.read_text(encoding="utf-8"))
rows = tool.record_specs(record, [3, 7, 12, 20])
check("positive: record selects four", len(rows) == 4)
check("positive: exact source labels", [r["source_label"] for r in rows] == [
    "P01 BeamLook Noise B03", "P01 BeamLook Noise B07",
    "P01 BeamLook Noise B12", "P01 BeamLook Noise B20"])
check("positive: P02 target labels", [r["target_label"] for r in rows] == [
    "P02 BeamLook Noise B03", "P02 BeamLook Noise B07",
    "P02 BeamLook Noise B12", "P02 BeamLook Noise B20"])
check("positive: target ownership tags", all(r["target_tags"] == [
    "InfinityStage.BeamLook", "P02ATMOS", "P02BEAMBOOTSTRAP"] for r in rows))
check("positive: record material pinned", all(r["source_record_spec"]["material"] ==
      "/Game/InfinityStage/Lighting/BeamLook/M_Vol_BeamNoise" for r in rows))
check("positive: source record hash pinned", tool.C.sha256(str(source_record_path)) == tool.SOURCE_RECORD_SHA256)

# Negative record controls.
bad_status = dict(record, status="prepared")
rejects("negative: source record must be saved/read-back", lambda: tool.record_specs(bad_status, [3]),
        "SOURCE_RECORD_STATUS")
bad_passage = dict(record, passage="P02")
rejects("negative: source record must be P01", lambda: tool.record_specs(bad_passage, [3]),
        "SOURCE_RECORD_PASSAGE")
rejects("negative: missing source ordinal", lambda: tool.record_specs(record, [99]),
        "SOURCE_RECORD_ROWS_MISSING")

# Dedupe controls: empty is valid; any label/tag ownership collision refuses.
check("positive: empty target inventory", tool.target_inventory_problems([], rows) == [])
label_collision = [{"id": "A", "label": rows[0]["target_label"], "tags": []}]
check("negative: target label collision detected", len(tool.target_inventory_problems(label_collision, rows)) == 1)
tag_collision = [{"id": "B", "label": "Other", "tags": ["P02ATMOS"]}]
check("negative: P02ATMOS collision detected", len(tool.target_inventory_problems(tag_collision, rows)) == 1)
owner_collision = [{"id": "C", "label": "Other", "tags": ["P02BEAMBOOTSTRAP"]}]
check("negative: owner-tag collision detected", len(tool.target_inventory_problems(owner_collision, rows)) == 1)

# Route controls.
request = json.loads((HERE / "p02_beam_bootstrap_request.json").read_text(encoding="utf-8"))
check("positive: guarded project-Python route", request["arguments"]["arguments"]["relativeSavedPath"] ==
      "CodexFlatV3/p02lighting/p02_beam_bootstrap_run.py")
runner = (HERE / "p02_beam_bootstrap_run.py").read_text(encoding="utf-8")
check("positive: runner checks confirmation", "P02BEAMBOOTSTRAP CONFIRM_MISSING" in runner)
check("positive: runner purges cached local modules", "sys.modules.pop" in runner)
source = (HERE / "p02_beam_bootstrap.py").read_text(encoding="utf-8")
check("positive: tool blocks active PASSAGELIGHT record", "ACTIVE_PASSAGELIGHT_RECORD" in source)

print("RESULT passed=%d failed=%d total=%d" % (passed, failed, passed + failed))
raise SystemExit(1 if failed else 0)
