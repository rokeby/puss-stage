"""Offline positive and required negative controls for fx_candle_s6.py."""
from __future__ import annotations

import sys

from fx_candle_s6 import (
    BASE_RELATIVE_LOCATION,
    CANDLE_LABEL,
    LIGHT_LABEL,
    SCENE6_SEQUENCE,
    _set_attachment_property,
    candle_plan,
)
from _fx_authoring_common import FxToolError


def fixture():
    return [
        {"kind": "WingPair", "label": "P06 Wing 054", "enabled": True},
        {"kind": "WingPair", "label": "P06 Wing 055", "enabled": True},
        {"kind": "Scene", "label": "Scene 6 - External Sound",
         "sequence": SCENE6_SEQUENCE, "enabled": True},
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
    plan = candle_plan(fixture(), True, ())
    if (plan["anchor_index"] == 1 and plan["scene_index"] == 2
            and plan["candle_location_cm"] == list(BASE_RELATIVE_LOCATION)
            and plan["candle_location_cm"] == [3390.0, 0.0, 110.0]
            and plan["light"]["temperature_kelvin"] == 1900.0
            and plan["light"]["attenuation_cm"] == 700.0
            and plan["light"]["cast_shadows"]
            and plan["light"]["volumetric_scattering_intensity"] == 1.0
            and plan["visual_contract"]["wax_cylinder_diameter_cm"] == 2.0
            and plan["visual_contract"]["wax_cylinder_height_cm"] == 10.0
            and plan["visual_contract"]["flame_width_cm"] == [2.0, 3.0]
            and plan["visual_contract"]["flame_height_cm"] == 4.0):
        print("PASS positive: S6 anchor and candle/light contract")
    else:
        print("FAIL positive: unexpected candle plan")
        failures += 1

    failures += negative("missing blueprint", lambda: candle_plan(fixture(), False, ()))
    failures += negative("duplicate candle", lambda: candle_plan(
        fixture(), True, (CANDLE_LABEL,)))
    failures += negative("duplicate light", lambda: candle_plan(
        fixture(), True, (LIGHT_LABEL,)))
    failures += negative("missing scene", lambda: candle_plan(fixture()[:2], True, ()))
    failures += negative("no preceding wing", lambda: candle_plan(
        [{"kind": "Scene", "label": "Scene 6", "sequence": SCENE6_SEQUENCE}],
        True, ()))
    failures += negative("direct attachment_guid assignment", lambda:
                         _set_attachment_property(
                             object(), "attachment_guid", "forbidden"))

    if failures == 0:
        print("FX_CANDLE_S6_HARNESS_OK|positive=1|negative=6")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
