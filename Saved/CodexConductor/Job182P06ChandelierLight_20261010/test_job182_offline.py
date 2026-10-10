"""Offline positive/negative controls for Job 182."""
from __future__ import annotations

import copy
import json
import math
import os
import sys


HERE = os.path.dirname(__file__)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import job182_core as core


ARGS_PATH = os.path.join(HERE, "job182_args.json")
RESULT_JSON = os.path.join(HERE, "harness_result.json")
RESULT_TXT = os.path.join(HERE, "harness_result.txt")


passed = []
failed = []


def check(name, condition, control):
    row = {"name": name, "control": control, "passed": bool(condition)}
    (passed if condition else failed).append(row)


def rejects(name, mutate, expected):
    raw = copy.deepcopy(BASE)
    mutate(raw)
    try:
        core.build_proposal(raw)
    except ValueError as error:
        check(name, expected in str(error), "negative")
    else:
        check(name, False, "negative")


BASE = json.load(open(ARGS_PATH, encoding="utf-8"))
proposal = core.build_proposal(BASE)

check("+ default proposal is explicitly Gary-tunable", proposal["authority"] == "PROPOSAL_FOR_GARY_TO_TUNE",
      "positive")
check("+ eight shadowless group lights plus one fill",
      len(proposal["group_lights"]) == 8 and not any(row["cast_shadows"] for row in proposal["group_lights"])
      and proposal["iron_fill"]["cast_shadows"] is False, "positive")
check("+ groups cover all 44 sockets in 5/6-candle sectors",
      sorted(len(row["sockets"]) for row in proposal["group_lights"]) == [5, 5, 5, 5, 6, 6, 6, 6]
      and sorted(sum((row["sockets"] for row in proposal["group_lights"]), [])) == core.SOCKETS,
      "positive")
check("+ vector mean places a light at its candle-tip centroid",
      core.vector_mean([[0, 0, 0], [3, 6, 9]]) == [1.5, 3.0, 4.5], "positive")
rows = [{"socket": socket, "socket_world_cm": [float(index), 0.0, 0.0],
         "actor_world_cm": [float(index), 0.0, 0.0]}
        for index, socket in enumerate(core.SOCKETS)]
assessment = core.assess_candles(rows, 0.5)
check("+ exact socket actors pass placement assessment",
      assessment["all_at_sockets"] and assessment["max_actor_to_socket_cm"] == 0.0, "positive")
rows[-1]["actor_world_cm"] = [100.0, 0.0, 0.0]
assessment = core.assess_candles(rows, 0.5)
check("+ placement assessment identifies an offset candle",
      not assessment["all_at_sockets"] and assessment["failures"] == ["Candle_44"], "positive")
near = core.fit_distance([100.0, 100.0, 100.0], 60.0, 16.0 / 9.0, 1.1)
far = core.fit_distance([100.0, 100.0, 100.0], 60.0, 16.0 / 9.0, 1.5)
check("+ bounds-fit margin moves the review camera farther away", far > near > 0.0, "positive")
states = [{"label": "L", "tags": ["T"], "parent_label": "B", "cast_shadows": False,
           "use_temperature": True, "intensity_units": "CANDELAS",
           "intensity_cd": 1.0, "temperature_k": 2000.0,
           "attenuation_radius_cm": 200.0, "source_radius_cm": 2.0,
           "volumetric_scattering_intensity": 0.0,
           "world_location_cm": [1.0, 2.0, 3.0], "relative_location_cm": [1.0, 2.0, 3.0]}]
check("+ exact saved light read-back matches", core.actor_states_match(states, copy.deepcopy(states)), "positive")

rejects("- seven grouped lights are refused", lambda raw: raw.update(group_light_count=7), "GROUP_LIGHT_COUNT_8")
rejects("- grouped shadow caster is refused", lambda raw: raw.update(group_cast_shadows=True), "GROUP_SHADOWLESS")
rejects("- cool candle temperature is refused", lambda raw: raw.update(group_temperature_k=3000),
        "GROUP_TEMPERATURE_1900_2200")
rejects("- broad candle attenuation is refused", lambda raw: raw.update(group_attenuation_cm=500),
        "GROUP_ATTENUATION_150_300")
rejects("- strong fill is refused", lambda raw: raw.update(fill_intensity_cd=300), "FILL_LOW_INTENSITY")
rejects("- fill not below/front is refused", lambda raw: raw.update(fill_offset_local_cm=[-1, 0, 1]),
        "FILL_BELOW_FRONT")
rejects("- duplicate scan fractions are refused", lambda raw: raw.update(scan_fractions=[0.2] * 5),
        "SCAN_FRACTIONS_SORTED_UNIQUE")
rejects("- APPLY without exact confirmation is refused", lambda raw: raw.update(mode="APPLY"),
        "CONFIRM|want=" + core.APPLY_CONFIRM)
rejects("- REVERT without exact confirmation is refused", lambda raw: raw.update(mode="REVERT"),
        "CONFIRM|want=" + core.REVERT_CONFIRM)

runtime = open(os.path.join(HERE, "job182_chandelier_light.py"), encoding="utf-8").read()
check("+ source contract excludes child actors from mesh bounds",
      "get_actor_bounds(False, False)" in runtime, "positive")
check("+ source contract uses no exposure-value override",
      "override_auto_exposure" not in runtime and 'post_process_blend_weight", 0.0' in runtime,
      "positive")
check("+ APPLY binds the reviewed proposal digest",
      'args["reviewed_plan_sha256"] == proposal["plan_sha256"]' in runtime, "positive")
check("+ REVERT owns actors by exact Job 182 tags",
      "OWNER_TAG in _tags(actor)" in runtime and "destroy_actor(actor)" in runtime, "positive")

result = {"ok": not failed, "pass": len(passed), "fail": len(failed),
          "total": len(passed) + len(failed),
          "positive": sum(row["control"] == "positive" for row in passed + failed),
          "negative": sum(row["control"] == "negative" for row in passed + failed),
          "passed": passed, "failed": failed, "offline": True, "unreal": False}
with open(RESULT_JSON, "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2)
marker = "JOB182_HARNESS|PASS=%d|FAIL=%d|TOTAL=%d|POSITIVE=%d|NEGATIVE=%d|OFFLINE=1|UNREAL=0" % (
    result["pass"], result["fail"], result["total"], result["positive"], result["negative"])
with open(RESULT_TXT, "w", encoding="utf-8") as handle:
    handle.write(marker + "\n")
print(marker)
if failed:
    for row in failed:
        print("FAILED|" + row["name"])
    raise SystemExit(1)
