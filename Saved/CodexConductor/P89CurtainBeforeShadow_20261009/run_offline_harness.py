"""Run P89's offline suite and emit a small machine-readable result."""
import json
import os
import re
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
test = os.path.join(HERE, "test_p89.py")
proc = subprocess.run([sys.executable, test], capture_output=True, text=True, check=False)
sys.stdout.write(proc.stdout)
sys.stderr.write(proc.stderr)
match = re.search(r"P89_OFFLINE_HARNESS\|pass=(\d+)\|fail=(\d+)\|total=(\d+)", proc.stdout)
result = {"passed": int(match.group(1)) if match else 0, "failed": int(match.group(2)) if match else 1,
          "total": int(match.group(3)) if match else 0, "exit_code": proc.returncode,
          "offline_only": True, "unreal_started": False, "blender_started": False}
with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=2, sort_keys=True)
    handle.write("\n")
sys.exit(1 if proc.returncode or not match else 0)
