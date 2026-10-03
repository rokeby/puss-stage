"""Offline positive and required negative controls for fx_wingburn_test.py."""
from __future__ import annotations

import copy
import sys

from fx_wingburn_test import (
    EXPECTED_MASTER,
    TARGET_CUE_LABEL,
    linear_fit,
    wingburn_plan,
)
from _fx_authoring_common import FxToolError


def cues():
    return [
        {"kind": "WingPair", "label": "P06 Wing 031"},
        {"kind": "WingPair", "label": TARGET_CUE_LABEL},
        {"kind": "WingPair", "label": "P06 Wing 033"},
    ]


def materials():
    return [
        {"slot": "Front", "material": "/Game/Test/MI_Front",
         "parent": EXPECTED_MASTER, "has_use_burn_parameter": True, "use_burn": True},
        {"slot": "Flap", "material": "/Game/Test/MI_Flap",
         "parent": EXPECTED_MASTER, "has_use_burn_parameter": True, "use_burn": True},
        {"slot": "Timber", "material": "/Game/Test/MI_Timber",
         "parent": "/Game/Test/M_Timber", "has_use_burn_parameter": False,
         "use_burn": False},
    ]


def negative(name, function):
    try:
        function()
    except FxToolError:
        print("PASS negative %s: stopped as required" % name)
        return 0
    print("FAIL negative %s: invalid plan accepted" % name)
    return 1


def main():
    failures = 0
    plan = wingburn_plan(cues(), materials())
    slope, intercept, residual = linear_fit([-100.0, 0.0, 100.0], [1.0, 0.5, 0.0])
    if (plan["cue_index"] == 1 and plan["side"] == "right"
            and plan["ignition_uv"] == [0.5, 1.0]
            and plan["burn_start_ahead_cm"] == 3000.0
            and plan["burn_span_cm"] == 4000.0
            and abs(slope + 0.005) < 1.0e-12
            and abs(intercept - 0.5) < 1.0e-12 and residual == 0.0):
        print("PASS positive: cue/material/default/UV plan")
    else:
        print("FAIL positive: unexpected WingBurn plan")
        failures += 1

    off = copy.deepcopy(materials())
    off[0]["use_burn"] = False
    failures += negative("UseBurn off", lambda: wingburn_plan(cues(), off))
    wrong = copy.deepcopy(materials())
    wrong[1]["parent"] = "/Game/Test/WrongMaster"
    failures += negative("wrong parent", lambda: wingburn_plan(cues(), wrong))
    missing = [row for row in materials() if row["slot"] != "Flap"]
    failures += negative("missing Flap", lambda: wingburn_plan(cues(), missing))
    failures += negative("duplicate effect", lambda: wingburn_plan(cues(), materials(), True))
    failures += negative("missing cue", lambda: wingburn_plan(cues()[:1], materials()))
    failures += negative("degenerate UV", lambda: linear_fit([0.0, 0.0, 0.0],
                                                              [0.0, 0.5, 1.0]))

    if failures == 0:
        print("FX_WINGBURN_TEST_HARNESS_OK|positive=1|negative=6")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
