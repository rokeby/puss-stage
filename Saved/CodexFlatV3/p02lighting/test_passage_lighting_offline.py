"""Offline positive/negative harness. Imports neither Unreal nor Blender."""
from __future__ import annotations

import ast
import copy
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import passage_lighting_as_source as P  # noqa: E402
import passage_lighting_perf_probe as F  # noqa: E402

RESULTS = []


def check(name, condition):
    ok = bool(condition)
    RESULTS.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name)


def raises(function, token=None):
    try:
        function()
    except Exception as error:  # deliberate stop controls
        return token is None or token in str(error)
    return False


def light(label, guid, y, kind="LIGHT", rgb=(1.0, 0.4, 0.2, 1.0), shadow=False, special=False, x=200.0):
    return {"guid": guid, "label": label, "kind": kind, "enabled": True,
            "relative_transform": {"location": [x, y, 900.0],
                                   "rotation_xyzw": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
            "lighting": {"type": "SPOT", "color": list(rgb), "use_temperature": True,
                         "temperature_kelvin": 3200.0, "cast_shadows": shadow,
                         "drama": {"strike_on_approach": special, "slow_move": False,
                                   "after_pass": "HOLD"}},
            "effect": {}}


def cue(prefix, ordinal, rows):
    return {"show_index": ordinal, "guid": "%s-CUE-%02d" % (prefix, ordinal),
            "label": "%s Wing %03d" % (prefix, ordinal), "attachments": rows,
            "wing_y": [-900.0, 900.0], "tags": []}


roles = ["CROSS +Y", "CROSS -Y", "LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL",
         "TOP_L", "TOP_R", "ENTRY_TOP", "PRACTICAL_BULB"]
# Synthetic source realizes the plan's declared 414-light default. The prose
# table itself sums to 415, so live DRY remains the authority and will stop on
# any mismatch instead of silently accepting either number.
counts = [16, 14, 19, 19, 19, 19, 18, 14, 19, 19, 19, 19, 19, 19, 19, 18, 14, 19, 18, 19, 18, 19, 18]
check("fixture total is plan default 414", sum(counts) == 414)

source = []
counter = 0
for ordinal, count in enumerate(counts, 1):
    rows = []
    for local in range(count):
        role = roles[(counter + local) % len(roles)]
        # Deliberately put +Y roles on -Y and vice versa: own-side policy must repair them.
        y = -1300.0 if "+Y" in role or role.endswith("_R") else 1300.0
        rows.append(light("P01 Wing %03d %s" % (ordinal, role), "S%03d" % (counter + local), y,
                          shadow=(local % 4 == 0), x=ordinal * 250.0 + local * 8.0))
    counter += count
    source.append(cue("P01", ordinal, rows))

target = []
for ordinal in range(1, 24):
    rows = [light("P02 Wing %03d %s" % (ordinal, roles[i]), "T%02d-%02d" % (ordinal, i),
                  -1100.0 if i % 2 else 1100.0, rgb=(0.2, 0.6, 1.0, 1.0),
                  x=ordinal * 250.0 + i * 8.0) for i in range(4)]
    rows.append(light("P02 Car Moving Event", "CAR-%02d" % ordinal, 0.0, special=True))
    rows.append(light("P02 Wing Prop", "PROP-%02d" % ordinal, 0.0, kind="PROP"))
    target.append(cue("P02", ordinal, rows))

# Args and confirm gates.
defaults = P.check_args({})
check("default route P01 to P02", defaults["source_passage"] == "P01" and defaults["target_passage"] == "P02")
check("default density full", defaults["density"] == "full")
check("APPLY exact confirm accepted", P.check_args({"mode": "APPLY", "confirm": "APPLY PASSAGELIGHT",
      "expected_plan_sha256": "a" * 64})["mode"] == "APPLY")
check("negative missing confirm", raises(lambda: P.check_args({"mode": "APPLY",
      "expected_plan_sha256": "a" * 64}), "CONFIRM_MISSING"))
check("negative missing hash", raises(lambda: P.check_args({"mode": "APPLY",
      "confirm": "APPLY PASSAGELIGHT"}), "EXPECTED_PLAN_SHA256_REQUIRED"))
check("negative same source and target", raises(lambda: P.check_args({"target_passage": "P01"}),
      "SOURCE_EQUALS_TARGET"))
check("negative unknown arg", raises(lambda: P.check_args({"surprise": 1}), "ARGS_UNKNOWN"))
check("negative nonlight preservation cannot disable", raises(lambda: P.check_args({"preserve_nonlights": False}),
      "PRESERVE_NONLIGHTS_REQUIRED"))

# Full-density plan and budget gate.
full = P.build_plan(source, target, defaults)
gate = P.enforce_budgets(full, defaults)
check("full density exact 414", full["counts"]["added_lights"] == 414)
check("DRY count cap passes", gate["status"] == "DRY_COUNT_PASS" and gate["cap_added_lights"] == 414)
check("23 target rows reported", len(full["per_row_counts"]) == 23)
check("same ordinal no wrap", not full["wrapped"] and all(t["ordinal"] == t["source_ordinal"] for t in full["targets"]))
check("car/move rows retained", all(any(k["reason"].startswith("label_token:") for k in t["kept"])
                                      for t in full["targets"]))
check("nonlights retained", all(any(k["reason"] == "non_light_attachment" for k in t["kept"])
                                  for t in full["targets"]))
meshy_target = [cue("P02", 1, [light("P02 Meshy Bulb Warm", "MESHY", 500.0),
                                light("P02 Warm Dead Bulb", "DEAD", -500.0)])]
meshy_plan = P.build_plan(source[:1], meshy_target, defaults)
check("Meshy and dead-bulb rows retained", {k["row"]["guid"] for k in meshy_plan["targets"][0]["kept"]} ==
      {"MESHY", "DEAD"})
check("projected total includes retained special", full["counts"]["projected_target_lights"] == 437)
check("shadow census present", full["counts"]["shadow_casting_added"] > 0)
check("dominant fallbacks reported", full["counts"]["dominant_fallbacks"] > 0)
check("plan hash deterministic", full["plan_sha256"] == P.build_plan(source, target, defaults)["plan_sha256"])

# Own-side aim controls.
check("sided fixtures were retargeted", len(full["aim_mappings"]) > 0)
check("own-side target and lamp never cross centre",
      all(m["target"][1] * m["after_transform"]["location"][1] > 0.0 for m in full["aim_mappings"]))
check("own-side rotation changed", any(m["before_transform"]["rotation_xyzw"] !=
                                       m["after_transform"]["rotation_xyzw"] for m in full["aim_mappings"]))
preserve_args = P.check_args({"aim_policy": "preserve_source"})
preserved = P.build_plan(source, target, preserve_args)
check("preserve-source option performs no aim rewrites", preserved["aim_mappings"] == [])

# Half density is globally alternating and therefore exactly ceil(414/2).
half_args = P.check_args({"density": "half", "expected_added_lights": 207, "max_added_lights": 207})
half = P.build_plan(source, target, half_args)
P.enforce_budgets(half, half_args)
check("half density exact 207", half["counts"]["added_lights"] == 207)
check("half density touches every row", all(row["added_lights"] > 0 for row in half["per_row_counts"]))

# Negative count/policy controls.
too_low = P.check_args({"max_added_lights": 413})
check("negative configurable performance cap", raises(lambda: P.enforce_budgets(
      P.build_plan(source, target, too_low), too_low), "PERF_COUNT_CAP_EXCEEDED"))
wrong_expected = P.check_args({"expected_added_lights": 413})
check("negative expected count mismatch", raises(lambda: P.enforce_budgets(
      P.build_plan(source, target, wrong_expected), wrong_expected), "EXPECTED_ADDED_LIGHTS"))
check("negative no-wrap rejects short source", raises(lambda: P.build_plan(source[:-1], target, defaults),
      "SOURCE_BAYS_SHORT"))

# Field-scoped REVERT: unrelated bulb edit survives; our exact row is removed; old row returns.
old = light("P02 Ordinary Old", "OLD", 100.0)
managed = light("P02 P01STRUCT B01 CROSS_+Y", "NEW", 100.0)
special = light("P02 Meshy Bulb Warm Dead", "OTHER", 100.0)
target_record = {"removed": [old], "added": [{"guid": "NEW"}], "after_rows": [managed, special]}
edited_special = copy.deepcopy(special)
edited_special["lighting"]["temperature_kelvin"] = 1850.0
reverted = P.field_scoped_revert_rows([managed, edited_special], target_record)
by_guid = {row["guid"]: row for row in reverted}
check("field revert removes only managed row", "NEW" not in by_guid and "OLD" in by_guid)
check("field revert preserves unrelated warm bulb edit", by_guid["OTHER"]["lighting"]["temperature_kelvin"] == 1850.0)
drifted_managed = copy.deepcopy(managed)
drifted_managed["lighting"]["temperature_kelvin"] = 9999.0
check("negative owned-field drift blocks revert", raises(lambda: P.field_scoped_revert_rows(
      [drifted_managed, special], target_record), "REVERT_OWNED_FIELD_DRIFT"))

# Atmosphere and preview controls.
source_atmos = [{"id": "S1", "label": "P01 Beam B01", "beam": True, "ordinal": 1}]
target_atmos = [{"id": "T1", "label": "P02 Beam B01", "beam": True, "ordinal": 1},
                {"id": "T2", "label": "P02 Smoke", "beam": False, "smoke": True, "lfv": False}]
atmos = P.atmos_plan(source_atmos, target_atmos, 23, True)
check("atmos source matched and target smoke suppressed", {c["action"] for c in atmos["changes"]} ==
      {"match_beam_actor", "suppress_actor"})
check("atmos disabled is no-op", P.atmos_plan(source_atmos, target_atmos, 23, False)["changes"] == [])
check("negative missing target beam", raises(lambda: P.atmos_plan(source_atmos, target_atmos[1:], 23, True),
      "ATMOS_TARGET_BEAMS_MISSING"))

preview_path = HERE / "P02_LIGHTING_PREVIEW_OFFLINE_2026-10-09.png"
info = P.write_preview_png(str(preview_path), full, width=1000, height=560)
check("offline preview PNG written", preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") and info["bytes"] > 1000)
tmp = pathlib.Path(tempfile.mkdtemp()) / "bad.png"
tmp.write_bytes(b"not a png")
check("negative corrupt preview rejected by signature", not tmp.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

# Shipped configuration and syntax.
for name in ("passage_lighting_as_source.py", "passage_lighting_run.py",
             "passage_lighting_perf_probe.py", "test_passage_lighting_offline.py"):
    ast.parse((HERE / name).read_text(encoding="utf-8"))
check("all shipped Python parses", True)
check("negative syntax control", raises(lambda: ast.parse("def broken(:\n"), "invalid syntax"))
request = json.loads((HERE / "passage_lighting_request.json").read_text(encoding="utf-8"))
check("request routes guarded runner", request["arguments"]["arguments"]["relativeSavedPath"] ==
      "CodexFlatV3/p02lighting/passage_lighting_run.py")
perf_request = json.loads((HERE / "passage_lighting_perf_probe_request.json").read_text(encoding="utf-8"))
check("perf request routes read-only hook", perf_request["arguments"]["arguments"]["relativeSavedPath"] ==
      defaults["perf_probe"]["relative_saved_path"])
perf_args = json.loads((HERE / "passage_lighting_perf_probe_args.json").read_text(encoding="utf-8"))
check("perf summary positive control", F.summarise([16.0] * 100, perf_args)["passed"] is True)
check("perf summary negative threshold control", F.summarise([60.0] * 100, perf_args)["passed"] is False)
check("perf summary negative empty control", raises(lambda: F.summarise([], perf_args), "NO_SAMPLES"))

failed = [name for name, ok in RESULTS if not ok]
print("\nPASSAGELIGHT_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed)))
sys.exit(1 if failed else 0)
