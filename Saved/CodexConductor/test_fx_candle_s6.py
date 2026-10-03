"""Offline positive and required negative controls for fx_candle_s6.py."""
from __future__ import annotations

import sys

from fx_candle_s6 import (
    BASE_RELATIVE_LOCATION,
    CANDLE_LABEL,
    DRAMA_FIELDS,
    EFFECT_FIELDS,
    EFFECT_GUID_FIELDS,
    EFFECT_OBJECT_FIELDS,
    LIGHT_FIELDS,
    LIGHT_LABEL,
    LIGHT_OBJECT_FIELDS,
    SCENE6_SEQUENCE,
    _attachment_state,
    _set_attachment_property,
    _state_differences,
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


class FakeVector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class FakeQuat(FakeVector):
    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        super().__init__(x, y, z)
        self.w = w


class FakeTransform:
    def __init__(self):
        self.translation = FakeVector()
        self.rotation = FakeQuat()
        self.scale3d = FakeVector(1.0, 1.0, 1.0)


class FakeStruct:
    """Same properties, deliberately different unstable wrapper text."""
    def __init__(self, properties, wrapper_id):
        self.properties = properties
        self.wrapper_id = wrapper_id

    def get_editor_property(self, name):
        return self.properties[name]

    def __str__(self):
        return "<FakeStruct wrapper=0x%s>" % self.wrapper_id


def fake_nested(fields, wrapper_id, guid_fields=(), object_fields=()):
    properties = {}
    for name in fields:
        if name in guid_fields:
            properties[name] = "00000000000000000000000000000000"
        elif name in object_fields:
            properties[name] = None
        else:
            properties[name] = 0.0
    return FakeStruct(properties, wrapper_id)


def fake_attachment(wrapper_id):
    drama = fake_nested(DRAMA_FIELDS, wrapper_id + "-drama")
    lighting = fake_nested(
        LIGHT_FIELDS, wrapper_id + "-lighting", object_fields=LIGHT_OBJECT_FIELDS)
    lighting.properties["drama"] = drama
    effect = fake_nested(
        EFFECT_FIELDS, wrapper_id + "-effect",
        guid_fields=EFFECT_GUID_FIELDS, object_fields=EFFECT_OBJECT_FIELDS)
    return FakeStruct({
        "attachment_guid": "11111111111111111111111111111111",
        "label": "Existing scratch lamp",
        "kind": "LIGHT",
        "enabled": True,
        "actor_class": None,
        "mesh": None,
        "anchor": "PAIR_CENTRE",
        "relative_transform": FakeTransform(),
        "lighting": lighting,
        "effect": effect,
        "trigger_distance_cm": 800.0,
    }, wrapper_id)


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

    # Regression for APPLY 20261003-035138: before/after nested Unreal struct
    # wrappers had different identities, although the backup and post-failure
    # autosave payloads were equal.  Their real fields must compare equal, and a
    # genuine field change must still fail the semantic guard.
    before = fake_attachment("before")
    after = fake_attachment("after")
    unstable_repr_equal = (
        str(before.get_editor_property("lighting")) ==
        str(after.get_editor_property("lighting"))
        or str(before.get_editor_property("effect")) ==
        str(after.get_editor_property("effect"))
    )
    if unstable_repr_equal:
        print("FAIL regression setup: wrapper reprs unexpectedly equal")
        failures += 1
    elif _attachment_state(before) != _attachment_state(after):
        print("FAIL regression: wrapper identity leaked into semantic state")
        failures += 1
    else:
        after.get_editor_property("lighting").properties["intensity"] = 1.0
        differences = _state_differences(
            [_attachment_state(before)], [_attachment_state(after)])
        if [row["path"] for row in differences] != ["[0].lighting.intensity"]:
            print("FAIL regression: real lighting change was not isolated")
            failures += 1
        else:
            print("PASS regression: unstable struct repr ignored; real field rejected")

    if failures == 0:
        print("FX_CANDLE_S6_HARNESS_OK|positive=1|negative=6|regression=1")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
