from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
suite = unittest.defaultTestLoader.discover(str(HERE), pattern="test_chainlink_weave.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
total = result.testsRun
failures = len(result.failures)
errors = len(result.errors)
report = {
    "tests": total,
    "passed": total - failures - errors,
    "failures": failures,
    "errors": errors,
    "positive_controls": 6,
    "negative_controls": 4,
}
(HERE / "offline_harness_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(f"P57_HARNESS_RESULT|tests={total}|passed={report['passed']}|failures={failures}|errors={errors}|positive=6|negative=4")
raise SystemExit(0 if result.wasSuccessful() else 1)
