"""Run every offline harness in P44 scope and emit one aggregate result line."""
import json
import os
import re
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROJECT = os.path.dirname(os.path.dirname(ROOT))
CASES = [
    ("p44", os.path.join(HERE, "test_p44_components.py"), r"P44_COMPONENT_HARNESS\|pass=(\d+)\|fail=(\d+)"),
    ("f4_visibility", os.path.join(ROOT, "KlaraIngest", "test_vis_fix_offline.py"),
     r"VISFIX_HARNESS\|run=(\d+)\|failures=(\d+)\|errors=(\d+)"),
    ("f5_fade", os.path.join(ROOT, "S1RigFade_20261009", "test_s1_rig_fade.py"),
     r"S1_RIG_FADE_HARNESS\|pass=(\d+)\|fail=(\d+)"),
    ("interactions", os.path.join(ROOT, "test_interaction_shadow_transition.py"),
     r"INTERACTION_SHADOW_TRANSITION_TESTS\|pass=(\d+)\|fail=(\d+)"),
]


rows = []
for name, path, pattern in CASES:
    proc = subprocess.run([sys.executable, path], cwd=PROJECT, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    match = re.search(pattern, proc.stdout)
    if match is None:
        rows.append({"name": name, "passed": 0, "failed": 1, "exit_code": proc.returncode,
                     "error": "RESULT_MARKER_MISSING"})
        continue
    nums = [int(value) for value in match.groups()]
    if name == "f4_visibility":
        passed, failed = nums[0] - nums[1] - nums[2], nums[1] + nums[2]
    else:
        passed, failed = nums[0], nums[1]
    if proc.returncode and failed == 0:
        failed = 1
    rows.append({"name": name, "passed": passed, "failed": failed, "exit_code": proc.returncode})

passed = sum(row["passed"] for row in rows)
failed = sum(row["failed"] for row in rows)
report = {"passed": passed, "failed": failed, "total": passed + failed, "suites": rows,
          "offline_only": True, "unreal_started": False, "blender_started": False}
with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2)
print("P44_OFFLINE_HARNESS|pass=%d|fail=%d|total=%d" % (passed, failed, passed + failed))
sys.exit(1 if failed else 0)
