"""Offline regression harness for the run-51c S3 orbit refusal."""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("s3_shots_fix_offline", os.path.join(HERE, "s3_shots_fix.py"))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


frames = list(range(1440, 2881, 2))
target_x = tool.ORBIT_OLD_C[0] + tool.ORBIT_D[0]
target_y = tool.ORBIT_OLD_C[1] + tool.ORBIT_D[1]
current = {
    "X": [(f, target_x + 200.0 * __import__("math").cos((f - 1440) / 1440.0 * 2.0 * __import__("math").pi)) for f in frames],
    "Y": [(f, target_y + 200.0 * __import__("math").sin((f - 1440) / 1440.0 * 2.0 * __import__("math").pi)) for f in frames],
    "Z": [(f, 195.0) for f in frames] + [(1847, 197.0), (1881, 193.0)],
}

check("old exact-721 guard refuses logged Z extras", any(len(current[a]) != 721 for a in "XYZ"))
status = tool.orbit_status(current)
check("new guard accepts current orbit as already applied", status["state"] == "already_applied", status)
check("new guard preserves diagnosis of creative Z keys", status["extra_z_frames"] == [1847, 1881], status)

drift = {axis: list(rows) for axis, rows in current.items()}
drift["X"] = drift["X"][:-1]
try:
    tool.orbit_status(drift)
    check("real XY lattice drift refuses", False)
except RuntimeError as exc:
    check("real XY lattice drift refuses", "ORBIT_XY_SHAPE" in str(exc), str(exc))

passed = sum(ok for _name, ok, _detail in RESULTS)
for name, ok, detail in RESULTS:
    if not ok:
        print("FAIL|%s|%s" % (name, detail))
print("S3_SHOTS_FIX_HARNESS|pass=%d|fail=%d|total=%d" % (passed, len(RESULTS) - passed, len(RESULTS)))
raise SystemExit(0 if passed == len(RESULTS) else 1)
