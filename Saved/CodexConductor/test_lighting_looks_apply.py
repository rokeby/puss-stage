"""Offline positive and negative controls for lighting_looks_apply.py (tune 4).

Every positive has a negative that must stop for the stated reason. The fence
fixture is built from W&T's own contract (fb_contract.planned_props) so the
props the tool must find are the ones the fence workflow will write.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import sys

from lighting_looks_apply import (
    BEAM_SOCKET,
    BEAM_VARIANTS,
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
    load_fence_model,
    ppv_change_gate,
    require_outside_unchanged,
    require_socket_hosts,
    revert_plain_state,
    validate_config,
)


HERE = os.path.dirname(os.path.abspath(__file__))
FENCE_DIR = os.path.normpath(os.path.join(HERE, "..", "CodexFlatV3", "fence"))
P04_EXTRA = ["C0FFEE0000000000000000000000A407", "C0FFEE0000000000000000000000A408"]
P03_FIRST = "B0B0B0B0000000000000000000000301"
P05_FIRST = "D0D0D0D0000000000000000000000501"
P05_DUP = "D0D0D0D0000000000000000000000502"


def _load_fb_contract():
    spec = importlib.util.spec_from_file_location(
        "fb_contract", os.path.join(FENCE_DIR, "fb_contract.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _light(guid, label, casts):
    return {"guid": guid, "label": label, "kind": "Light", "enabled": True,
            "lighting": {"cast_shadows": casts, "intensity": 10.0}}


def fixture(config, with_fence=True, extra_casters=31):
    """Plain Show: P03 cue, a P05 cue that REUSES label 'P04 Wing 003' placed
    BEFORE the P04 span (a first-label-match lookup would pick it), the eight
    P04 cues keyed by real GUIDs, and the P05 sentinel."""
    guids = [row["cue_guid"] for row in config["bay_plan"]] + P04_EXTRA
    cues = [{"guid": P03_FIRST, "label": "P03 Wing 001",
             "attachments": [_light("P03-L01", "P03 lamp", True)]},
            {"guid": P05_DUP, "label": "P04 Wing 003",
             "attachments": [_light("P05-DUP-L01", "P05 reused-label lamp", True)]}]
    for ordinal, guid in enumerate(guids, start=1):
        attachments = []
        for light in range(1, 10):
            attachments.append(_light("%s-L%02d" % (guid, light),
                                      "P04 Wing %03d Baseline %02d" % (ordinal, light),
                                      light in (3, 4)))
        attachments.append({"guid": "%s-GOBO" % guid, "label": "gobo", "kind": "Prop",
                            "enabled": True, "lighting": {"cast_shadows": False}})
        cues.append({"guid": guid, "label": "P04 Wing %03d" % ordinal,
                     "attachments": attachments, "occurrence_offset_identity": True})
    # Non-target P04 casters so the P04 total matches the recorded 43.
    for index in range(extra_casters - 4):
        cues[-1]["attachments"].append(_light("EXTRA-%02d" % index, "extra %d" % index, True))
    cues.append({"guid": P05_FIRST, "label": "P05 Wing 001",
                 "attachments": [_light("P05-001-L01", "P05 Sentinel", True)]})
    if with_fence:
        contract = _load_fb_contract()
        plan = json.load(open(os.path.join(FENCE_DIR, "run_fence_p04_plan.json"), encoding="utf-8"))
        by_guid = {cue["guid"]: cue for cue in cues}
        for number, prop in enumerate(contract.planned_props(plan)):
            by_guid[prop["cue_guid"]]["attachments"].append({
                "guid": "FENCE-%03d" % number, "label": prop["label"], "kind": "Prop",
                "enabled": True, "mesh": prop["mesh"],
                "relative_location_cm": list(prop["relative_location_cm"]),
                "relative_yaw_deg": float(prop["rotation_deg"][2]),
                "lighting": {"cast_shadows": False}})
    return cues


def passages():
    return [{"first": P03_FIRST, "last": P03_FIRST},
            {"first": "75FD539B104815DC315DBB85D6E69939", "last": P04_EXTRA[-1]},
            {"first": P05_FIRST, "last": P05_FIRST}]


def rows_by_guid(cues):
    return {cue["guid"]: cue["attachments"] for cue in cues}


COUNTS = {"positive": 0, "negative": 0}


def check(name, condition, detail=""):
    COUNTS["positive"] += 1
    if condition:
        print("PASS positive %s" % name)
        return 0
    print("FAIL positive %s: %s" % (name, detail))
    return 1


def negative(name, function, token):
    COUNTS["negative"] += 1
    try:
        function()
    except LightingLooksError as error:
        if token in str(error):
            print("PASS negative %s: stopped as required (%s)" % (name, token))
            return 0
        print("FAIL negative %s: wrong stop %s" % (name, error))
        return 1
    print("FAIL negative %s: invalid input accepted" % name)
    return 1


def independent_socket(plan_json, sidecar, side, post_index, socket, station_x):
    """Recompute a socket position from the raw plan + sidecar, not via the tool."""
    post = next(row for row in plan_json["posts"]
                if row["side"] == side and row["post_index"] == post_index)
    sock = next(row for row in sidecar["sockets"] if row["name"] == socket)
    yaw = math.radians(post["passage_local_transform_cm"]["rotation_deg"][2])
    x, y, z = sock["relative_location_cm"]
    px, py, pz = post["passage_local_transform_cm"]["location"]
    return [px + math.cos(yaw) * x - math.sin(yaw) * y - station_x,
            py + math.sin(yaw) * x + math.cos(yaw) * y, pz + z]


def main():
    failures = 0
    config = load_config(os.path.join(HERE, "lighting_looks.json"))
    fence = load_fence_model(config, HERE)
    plan_json = json.load(open(fence["plan_path"], encoding="utf-8"))
    sidecar = json.load(open(fence["sidecar_path"], encoding="utf-8"))
    before = fixture(config)
    after, record, plan = apply_plain_state(config, before, passages(), copy.deepcopy(fence))
    targets = plan["targets"]
    fixtures = [row for target in targets for row in target["fixtures"]]
    lights = [row for row in fixtures if row["authored_kind"] == "LIGHT"]
    beams = [row for row in lights if row["role"] == "FENCE_BEAM"]
    flares = [row for row in lights if row["role"] == "FLARE_SWEEP"]

    # ---- identity: GUID only, duplicate label present
    failures += check(
        "guid_identity_with_duplicate_label_cue_first",
        [(row["show_index"], row["cue_guid"]) for row in targets]
        == [(index + 2, row["cue_guid"]) for index, row in enumerate(config["bay_plan"])]
        and after[1] == before[1],
        repr([(row["show_index"], row["cue_guid"][:8]) for row in targets]))
    failures += check(
        "p04_span_by_guid",
        plan["p04_span_guids"] == [row["cue_guid"] for row in config["bay_plan"]] + P04_EXTRA)

    # ---- counts and budget
    failures += check(
        "fixture_counts",
        plan["fixture_count"] == 57 and plan["light_fixture_count"] == 45
        and plan["practical_prop_count"] == 12 and len(beams) == 4 and len(flares) == 1,
        "%s %s %s %d %d" % (plan["fixture_count"], plan["light_fixture_count"],
                            plan["practical_prop_count"], len(beams), len(flares)))
    failures += check(
        "shadow_budget_swap_not_add",
        plan["shadow"] == {"p04_before": 43, "p04_after": 43, "target_before": 12,
                           "target_after": 12, "cap": 43, "budget_ok": True}
        and all(target["new_shadow_casters"] <= 2 for target in targets),
        repr(plan["shadow"]))
    failures += check(
        "casters_only_low_side_or_beam",
        all(not row.get("cast_shadows") or row["role"] in ("LOW_SIDE", "FENCE_BEAM")
            for row in lights))

    # ---- beams: Back socket, torn/half bays, independent geometry
    station = fence["station_x"]
    beam_geometry_ok = True
    for beam in beams:
        host = beam["socket_host"]
        side = "left" if host["post"][0] == "L" else "right"
        expected = independent_socket(plan_json, sidecar, side, int(host["post"][1:]),
                                      BEAM_SOCKET, station[beam["socket_host"]["host_cue_guid"]])
        beam_geometry_ok &= max(abs(a - b) for a, b in
                                zip(expected, beam["transform"]["location_cm"])) < 1.0e-6
    failures += check(
        "beams_from_back_sockets_in_torn_half_bays",
        len(beams) == 4 and beam_geometry_ok
        and all(row["socket_host"]["socket"] == BEAM_SOCKET for row in beams)
        and all(row["fence_bay"]["variant"] in BEAM_VARIANTS for row in beams)
        and len({row["socket_host"]["host_cue_guid"] for row in beams}) == 4,
        repr([(row["label"], row["fence_bay"], row["socket_host"]["socket"]) for row in beams]))
    eligible = [bay for bay in fence["bays"] if bay["variant"] in BEAM_VARIANTS]
    again = build_plain_plan(config, fixture(config), passages(), copy.deepcopy(fence))
    failures += check(
        "beams_intermittent_seeded_deterministic_not_every_bay",
        len(eligible) == 8 and len(beams) < len(eligible)
        and all(row["drama"]["after_pass"] == "EXTINGUISH"
                and 450.0 <= row["drama"]["strike_distance_cm"] <= 1100.0
                and 0.5 <= row["drama"]["ignition_stutter"] <= 0.95
                and row["volumetric_scattering"] > 0.0 for row in beams)
        and len({row["drama"]["strike_distance_cm"] for row in beams}) == 4
        and [r["label"] for r in again["targets"][0]["fixtures"]] ==
            [r["label"] for r in targets[0]["fixtures"]]
        and [r.get("drama") for t in again["targets"] for r in t["fixtures"]] ==
            [r.get("drama") for r in fixtures],
        repr([row["drama"] for row in beams]))

    # ---- socket hosting after the move
    structure = set(config["tune4"]["structure_hosted_roles"])
    used = [(row["socket_host"]["post"], row["socket_host"]["socket"])
            for row in lights if row["role"] not in structure]
    low_ok = all(row["socket_host"]["socket"] in ("SOCKET_Low_01", "SOCKET_Low_02")
                 for row in lights if row["role"] == "LOW_SIDE")
    lamp_ok = all(row["socket_host"]["socket"].startswith("SOCKET_Lamp_")
                  for row in lights if row["role"] == "PRACTICAL")
    bodies_ok = all(row["transform"]["location_cm"] ==
                    next(light for light in target["fixtures"]
                         if light["slot"] == row["paired_slot"])["transform"]["location_cm"]
                    for target in targets for row in target["fixtures"]
                    if row["authored_kind"] == "PROP")
    first_low = next(row for row in lights if row["role"] == "LOW_SIDE")
    low_expected = independent_socket(
        plan_json, sidecar, "left" if first_low["socket_host"]["post"][0] == "L" else "right",
        int(first_low["socket_host"]["post"][1:]), first_low["socket_host"]["socket"],
        station[first_low["socket_host"]["host_cue_guid"]])
    try:
        require_socket_hosts(config, targets)
        hosts_ok = True
    except LightingLooksError as error:
        hosts_ok = False
        print("  detail:", error)
    failures += check(
        "no_light_without_socket_host_after_move",
        hosts_ok and low_ok and lamp_ok and bodies_ok and len(used) == len(set(used))
        and max(abs(a - b) for a, b in zip(low_expected, first_low["transform"]["location_cm"])) < 1e-6
        and all(row["role"] in structure or row.get("socket_host") for row in lights),
        "hosts=%s low=%s lamp=%s bodies=%s unique=%s" % (
            hosts_ok, low_ok, lamp_ok, bodies_ok, len(used) == len(set(used))))
    flare = flares[0]
    failures += check(
        "one_flare_sweep_on_top_socket_brief_no_shadow",
        flare["socket_host"]["socket"] == "SOCKET_Top" and not flare["cast_shadows"]
        and flare["drama"]["slow_move"] is True and flare["drama"]["after_pass"] == "EXTINGUISH"
        and flare["transform"]["rotation_rpy_deg"][1] < 0.0)

    # ---- scope guards
    try:
        require_outside_unchanged(rows_by_guid(before), rows_by_guid(after),
                                  plan["target_cue_guids"])
        outside_ok = True
    except LightingLooksError:
        outside_ok = False
    failures += check("outside_target_hash_unchanged", outside_ok)
    fence_before = {att["guid"]: att for cue in before for att in cue["attachments"]
                    if str(att["guid"]).startswith("FENCE-")}
    fence_after = {att["guid"]: att for cue in after for att in cue["attachments"]
                   if str(att["guid"]).startswith("FENCE-")}
    failures += check("fence_props_untouched", fence_before == fence_after and len(fence_before) == 47,
                      str(len(fence_before)))
    failures += check(
        "old_lights_off",
        all(not att["enabled"] for target in targets
            for att in next(c for c in after if c["guid"] == target["cue_guid"])["attachments"][:9]))
    failures += check("revert_exact", revert_plain_state(after, record) == before)

    # ---- look values carried from tune 3d (non-moved roles)
    bay5_accent = next(row for row in targets[4]["fixtures"] if row["slot"] == "BEAM_R")
    bay6_accent = next(row for row in targets[5]["fixtures"] if row["slot"] == "BEAM_R")
    failures += check(
        "tune3d_accents_unchanged_by_tune4",
        bay5_accent["color_rgb_linear"] == [1.0, 0.0, 0.35]
        and bay6_accent["color_rgb_linear"] == [0.0, 0.7, 1.0]
        and bay5_accent["intensity"] == 30000.0 and bay6_accent["intensity"] == 29700.0
        and bay5_accent["transform"]["location_cm"] == [900.0, 967.491, 300.0]
        and bay6_accent["transform"]["location_cm"] == [900.0, -1012.222, 300.0]
        and not bay5_accent.get("socket_host"))
    failures += check("ppv_gate_allows_with_flag", ppv_change_gate(True, {"lens_flare_intensity": 0.35}))

    # ---- wrapper regression (unchanged)
    scratch_before = fake_attachment("before")
    scratch_after = fake_attachment("after")
    before_rows = [_attachment_row(scratch_before)]
    after_rows = [_attachment_row(scratch_after)]
    try:
        _require_attachment_rows_equal(after_rows, before_rows, "HARNESS_WRAPPER_FALSE_DIFFERENCE")
        wrapper_case_ok = str(scratch_before.get_editor_property("lighting")) != \
            str(scratch_after.get_editor_property("lighting"))
    except LightingLooksError:
        wrapper_case_ok = False
    failures += check("unstable_wrapper_repr_ignored", wrapper_case_ok)
    scratch_after.get_editor_property("effect").properties["flicker_amount"] = 1.0
    changed_rows = [_attachment_row(scratch_after)]
    differences = _state_differences(before_rows, changed_rows)
    try:
        _require_attachment_rows_equal(changed_rows, before_rows, "HARNESS_REAL_FIELD_CHANGE")
        real_change_rejected = False
    except LightingLooksError as error:
        real_change_rejected = ([row["path"] for row in differences] == ["[0].effect.flicker_amount"]
                                and "[0].effect.flicker_amount" in str(error))
    failures += check("real_field_change_rejected", real_change_rejected)

    # ================= negatives
    def plan_with(cues, cfg=None, rows=None, fence_model=None):
        return build_plain_plan(cfg or config, cues, rows or passages(),
                                copy.deepcopy(fence if fence_model is None else fence_model))

    failures += negative("fence_props_missing", lambda: plan_with(fixture(config, with_fence=False)),
                         "FENCE_PROPS_MISSING")
    moved = fixture(config)
    next(att for cue in moved for att in cue["attachments"]
         if att.get("label") == "FV3FB_LEFT_P04_post")["relative_location_cm"][0] += 50.0
    failures += negative("fence_post_moved_50cm", lambda: plan_with(moved), "FENCE_PROPS_MISSING")
    no_tarp = fixture(config)
    for cue in no_tarp:
        cue["attachments"] = [att for att in cue["attachments"]
                              if att.get("label") != "FV3FB_LEFT_B08_tarp"]
    failures += negative("torn_half_bay_tarp_missing", lambda: plan_with(no_tarp), "FENCE_PROPS_MISSING")
    failures += negative("fence_inputs_absent",
                         lambda: build_plain_plan(config, fixture(config), passages(), None),
                         "FENCE_INPUTS_REQUIRED")
    offset = fixture(config)
    offset[2]["occurrence_offset_identity"] = False
    failures += negative("post_anchor_occurrence_offset", lambda: plan_with(offset),
                         "FENCE_ANCHOR_OCCURRENCE_OFFSET_NOT_IDENTITY")

    unhosted = copy.deepcopy(targets)
    next(row for row in unhosted[0]["fixtures"] if row["role"] == "LOW_SIDE").pop("socket_host")
    failures += negative("light_without_socket_host",
                         lambda: require_socket_hosts(config, unhosted), "LIGHT_WITHOUT_SOCKET_HOST")
    off_socket = copy.deepcopy(targets)
    next(row for row in off_socket[1]["fixtures"]
         if row["role"] == "PRACTICAL")["transform"]["location_cm"][2] += 30.0
    failures += negative("light_not_at_its_socket",
                         lambda: require_socket_hosts(config, off_socket), "LIGHT_NOT_AT_SOCKET")
    low_beam = copy.deepcopy(targets)
    next(row for t in low_beam for row in t["fixtures"]
         if row["role"] == "FENCE_BEAM")["socket_host"]["socket"] = "SOCKET_Low_01"
    failures += negative("beam_not_from_back_socket",
                         lambda: require_socket_hosts(config, low_beam), "BEAM_NOT_FROM_BACK_SOCKET")
    full_beam = copy.deepcopy(targets)
    next(row for t in full_beam for row in t["fixtures"]
         if row["role"] == "FENCE_BEAM")["fence_bay"]["variant"] = "tarp_full"
    failures += negative("beam_in_full_tarp_bay",
                         lambda: require_socket_hosts(config, full_beam), "BEAM_NOT_IN_TORN_OR_HALF_BAY")
    bad_socket = copy.deepcopy(config)
    bad_socket["tune4"]["beams"]["socket"] = "SOCKET_Low_01"
    failures += negative("config_beam_socket_not_back", lambda: validate_config(bad_socket),
                         "BEAM_SOCKET_NOT_BACK")
    bad_variant = copy.deepcopy(config)
    bad_variant["tune4"]["beams"]["eligible_variants"] = ["tarp_torn", "tarp_full"]
    failures += negative("config_beam_variant_full", lambda: validate_config(bad_variant),
                         "BEAM_VARIANT_NOT_TORN_OR_HALF")

    touched = copy.deepcopy(after)
    touched[-1]["attachments"][0]["enabled"] = False
    failures += negative("outside_target_hash_changed",
                         lambda: require_outside_unchanged(rows_by_guid(before), rows_by_guid(touched),
                                                           plan["target_cue_guids"]),
                         "OUTSIDE_TARGET_SCOPE_CHANGED")

    no_guid = copy.deepcopy(config)
    no_guid["bay_plan"][2].pop("cue_guid")
    failures += negative("label_keyed_config_refused", lambda: validate_config(no_guid),
                         "BAY_CUE_GUID_MISSING")
    renamed = fixture(config)
    next(cue for cue in renamed if cue["guid"] == config["bay_plan"][2]["cue_guid"])["label"] = "P04 Wing 003b"
    failures += negative("no_label_fallback_when_guid_label_drifts",
                         lambda: plan_with(renamed), "TARGET_LABEL_MISMATCH")
    gone = [cue for cue in fixture(config) if cue["guid"] != config["bay_plan"][5]["cue_guid"]]
    failures += negative("missing_target_guid", lambda: plan_with(gone), "TARGET_CUE_GUID_ABSENT")
    failures += negative("p04_passage_row_missing",
                         lambda: build_plain_plan(config, fixture(config), passages()[:1] + passages()[2:],
                                                  copy.deepcopy(fence)),
                         "P04_PASSAGE_ROW_COUNT")

    over_cap = fixture(config, extra_casters=32)
    failures += negative("shadow_cap_43", lambda: plan_with(over_cap), "SHADOW_CAP_EXCEEDED")
    insufficient = fixture(config)
    for cue in insufficient[2:8]:
        for attachment in cue["attachments"]:
            if attachment["kind"] == "Light":
                attachment["lighting"]["cast_shadows"] = False
    failures += negative("shadow_budget_exceeded", lambda: plan_with(insufficient),
                         "SHADOW_BUDGET_EXCEEDED")
    duplicate_guid = fixture(config)
    duplicate_guid[3]["attachments"][0]["guid"] = duplicate_guid[2]["attachments"][0]["guid"]
    failures += negative("duplicate_attachment_guid", lambda: plan_with(duplicate_guid),
                         "ATTACHMENT_GUIDS_INVALID_OR_DUPLICATE")
    already = fixture(config)
    already[2]["attachments"].append(_light("ALREADY", "P04 LOOK B01 MOODY TOP_L", False))
    failures += negative("prototype_already_present", lambda: plan_with(already),
                         "PROTOTYPE_ALREADY_PRESENT")
    failures += negative("ppv_change_without_flag",
                         lambda: ppv_change_gate(False, {"lens_flare_intensity": 0.35}),
                         "PPV_CHANGE_NOT_ALLOWED")
    bad_caster = copy.deepcopy(config)
    bad_caster["looks"]["MOODY"]["instruments"][0]["cast_shadows"] = True
    failures += negative("non_side_shadow_caster", lambda: validate_config(bad_caster),
                         "NON_SIDE_SHADOW_CASTER")
    bad_ramp = copy.deepcopy(config)
    bad_ramp["distance_keying"]["ramp_distance_cm"] = 149.0
    failures += negative("ramp_not_1_5m", lambda: validate_config(bad_ramp), "RAMP_NOT_150_CM")

    if failures == 0:
        print("LIGHTING_LOOKS_HARNESS_OK|tune=4|positive=%d|negative=%d|attachments=57|lights=45|"
              "beams=4/8_eligible|flare=1|shadow=43->43|cap=43|fence_plan=%s|plan_sha=%s" %
              (COUNTS["positive"], COUNTS["negative"],
               fence["plan_run_id"], fence["plan_sha256"][:12]))
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
