"""Offline positive and negative controls for lighting_looks_apply.py."""
from __future__ import annotations

import copy
import os
import sys

from lighting_looks_apply import (
    DRAMA_FIELDS,
    EFFECT_FIELDS,
    EFFECT_GUID_FIELDS,
    EFFECT_OBJECT_FIELDS,
    LIGHT_FIELDS,
    LIGHT_OBJECT_FIELDS,
    LightingLooksError,
    _attachment_row,
    _require_attachment_rows_equal,
    _state_differences,
    apply_plain_state,
    build_plain_plan,
    load_config,
    revert_plain_state,
    validate_config,
)


HERE = os.path.dirname(os.path.abspath(__file__))


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
        "anchor": "STATION",
        "relative_transform": FakeTransform(),
        "lighting": lighting,
        "effect": effect,
        "trigger_distance_cm": 800.0,
    }, wrapper_id)


def fixture():
    cues = []
    for bay in range(1, 9):
        attachments = []
        for light in range(1, 10):
            attachments.append({
                "guid": "P04-%03d-L%02d" % (bay, light),
                "label": "P04 Wing %03d Baseline %02d" % (bay, light),
                "kind": "Light",
                "enabled": True,
                "lighting": {"cast_shadows": light in (3, 4), "intensity": light * 10.0},
            })
        attachments.append({
            "guid": "P04-%03d-PROP" % bay,
            "label": "P04 Wing %03d Existing Gobo" % bay,
            "kind": "Prop",
            "enabled": True,
            "lighting": {"cast_shadows": False},
        })
        cues.append({
            "guid": "CUE-P04-%03d" % bay,
            "label": "P04 Wing %03d" % bay,
            "attachments": attachments,
        })
    cues.append({
        "guid": "CUE-P05-001",
        "label": "P05 Wing 001",
        "attachments": [{
            "guid": "P05-001-L01",
            "label": "P05 Sentinel",
            "kind": "Light",
            "enabled": True,
            "lighting": {"cast_shadows": True, "intensity": 99.0},
        }],
    })
    return cues


def check(name, condition, detail=""):
    if condition:
        print("PASS positive %s" % name)
        return 0
    print("FAIL positive %s: %s" % (name, detail))
    return 1


def negative(name, function, token):
    try:
        function()
    except LightingLooksError as error:
        if token in str(error):
            print("PASS negative %s: stopped as required" % name)
            return 0
        print("FAIL negative %s: wrong stop %s" % (name, error))
        return 1
    print("FAIL negative %s: invalid input accepted" % name)
    return 1


def main():
    failures = 0
    config = load_config(os.path.join(HERE, "lighting_looks.json"))
    before = fixture()
    after, record, plan = apply_plain_state(config, before)

    failures += check(
        "fixture_counts",
        plan["fixture_count"] == 34
        and [row["fixture_count"] for row in plan["targets"]] == [6, 6, 6, 6, 5, 5],
        repr([row["fixture_count"] for row in plan["targets"]]),
    )
    failures += check(
        "look_assignment",
        [row["look"] for row in plan["targets"]]
        == ["MOODY", "MOODY", "INDUSTRIAL", "INDUSTRIAL", "THEATRICAL", "THEATRICAL"],
    )
    failures += check(
        "fresh_identity",
        [(row["show_index"], row["cue_guid"]) for row in plan["targets"]]
        == [(index, "CUE-P04-%03d" % (index + 1)) for index in range(6)],
    )
    failures += check(
        "shadow_budget",
        plan["shadow"] == {
            "p04_before": 16,
            "p04_after": 16,
            "target_before": 12,
            "target_after": 12,
            "budget_ok": True,
        },
        repr(plan["shadow"]),
    )
    failures += check(
        "old_lights_off",
        all(not attachment["enabled"]
            for cue in after[:6]
            for attachment in cue["attachments"][:9]),
    )
    failures += check(
        "non_light_gobos_preserved",
        all(cue["attachments"][9] == before[index]["attachments"][9]
            for index, cue in enumerate(after[:6])),
    )
    failures += check(
        "only_low_side_casts",
        all(not fixture_row["cast_shadows"] or fixture_row["role"] == "LOW_SIDE"
            for target in plan["targets"] for fixture_row in target["fixtures"]),
    )
    bay1_key = next(row for row in plan["targets"][0]["fixtures"]
                    if row["slot"] == "LOW_SIDE_L_KEY")
    bay2_key = next(row for row in plan["targets"][1]["fixtures"]
                    if row["slot"] == "LOW_SIDE_L_KEY")
    failures += check(
        "bay_level_scale",
        bay1_key["intensity"] == 160.0 and bay2_key["intensity"] == 56.0,
        "%s %s" % (bay1_key["intensity"], bay2_key["intensity"]),
    )
    failures += check(
        "outside_bays_untouched",
        after[6:] == before[6:],
    )
    restored = revert_plain_state(after, record)
    failures += check("revert_exact", restored == before)

    # Regression for APPLY 20261003-120646: semantically identical nested
    # wrappers have unstable str() values. The actual restore guard must accept
    # that round-trip but continue rejecting any real field change.
    scratch_before = fake_attachment("before")
    scratch_after = fake_attachment("after")
    before_rows = [_attachment_row(scratch_before)]
    after_rows = [_attachment_row(scratch_after)]
    try:
        _require_attachment_rows_equal(
            after_rows, before_rows, "HARNESS_WRAPPER_FALSE_DIFFERENCE")
        wrapper_case_ok = (
            str(scratch_before.get_editor_property("lighting")) !=
            str(scratch_after.get_editor_property("lighting"))
            and str(scratch_before.get_editor_property("effect")) !=
            str(scratch_after.get_editor_property("effect"))
        )
    except LightingLooksError:
        wrapper_case_ok = False
    failures += check("unstable_wrapper_repr_ignored", wrapper_case_ok)

    scratch_after.get_editor_property("effect").properties["flicker_amount"] = 1.0
    changed_rows = [_attachment_row(scratch_after)]
    differences = _state_differences(before_rows, changed_rows)
    try:
        _require_attachment_rows_equal(
            changed_rows, before_rows, "HARNESS_REAL_FIELD_CHANGE")
        real_change_rejected = False
    except LightingLooksError as error:
        real_change_rejected = (
            [row["path"] for row in differences] == ["[0].effect.flicker_amount"]
            and "HARNESS_REAL_FIELD_CHANGE" in str(error)
            and "[0].effect.flicker_amount" in str(error)
        )
    failures += check("real_field_change_rejected", real_change_rejected)

    insufficient = fixture()
    for cue in insufficient[:6]:
        for attachment in cue["attachments"]:
            if attachment["kind"] == "Light":
                attachment["lighting"]["cast_shadows"] = False
    failures += negative(
        "shadow_budget_exceeded",
        lambda: build_plain_plan(config, insufficient),
        "SHADOW_BUDGET_EXCEEDED",
    )

    missing = fixture()
    missing.pop(5)
    failures += negative(
        "missing_target_bay",
        lambda: build_plain_plan(config, missing),
        "TARGET_CUE_COUNT",
    )

    duplicate_guid = fixture()
    duplicate_guid[1]["attachments"][0]["guid"] = duplicate_guid[0]["attachments"][0]["guid"]
    failures += negative(
        "duplicate_attachment_guid",
        lambda: build_plain_plan(config, duplicate_guid),
        "ATTACHMENT_GUIDS_INVALID_OR_DUPLICATE",
    )

    already = fixture()
    already[0]["attachments"].append({
        "guid": "ALREADY-PRESENT",
        "label": "P04 LOOK B01 MOODY TOP_L",
        "kind": "Light",
        "enabled": True,
        "lighting": {"cast_shadows": False},
    })
    failures += negative(
        "prototype_already_present",
        lambda: build_plain_plan(config, already),
        "PROTOTYPE_ALREADY_PRESENT",
    )

    bad_caster = copy.deepcopy(config)
    bad_caster["looks"]["MOODY"]["instruments"][0]["cast_shadows"] = True
    failures += negative(
        "non_side_shadow_caster",
        lambda: validate_config(bad_caster),
        "NON_SIDE_SHADOW_CASTER",
    )

    bad_ramp = copy.deepcopy(config)
    bad_ramp["distance_keying"]["ramp_distance_cm"] = 149.0
    failures += negative(
        "ramp_not_1_5m",
        lambda: validate_config(bad_ramp),
        "RAMP_NOT_150_CM",
    )

    if failures == 0:
        print("LIGHTING_LOOKS_HARNESS_OK|positive=12|negative=6|fixtures=34|shadow=16->16|revert_exact=1|wrapper_regression=1|real_diff_guard=1")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
