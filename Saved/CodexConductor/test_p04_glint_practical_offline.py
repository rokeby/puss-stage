"""Offline harness for p04_glint_practical.py (pure Python, no unreal). Run: python test_p04_glint_practical_offline.py

Fake Show: P04 bays Wing 008 / 009 / 010 (009 carries TOP_L, TOP_R, PRACTICAL_L + _BODY, PRACTICAL_R + _BODY in the
5 Oct record's shape) and a P03 cue outside the passage. Stations from a fake GatherStations: identity frames at
x = 250 + 500(N-1), y = 240000, plus a rotated-frame case. Every gate has a passing case and a failing control.
Prints "PASS n/FAIL m"; exits non-zero on any failure.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import math
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("p04_glint_practical", os.path.join(HERE, "p04_glint_practical.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
assert M.unreal is None, "harness must run with unreal absent"
SCORES, TOOL = M.load_modules()

RESULTS = []


def case(name):
    def wrap(fn):
        try:
            fn()
            RESULTS.append((name, True, ""))
        except Exception as error:  # noqa: BLE001
            RESULTS.append((name, False, "%s: %s\n%s" % (type(error).__name__, error, traceback.format_exc())))
        return fn
    return wrap


def refuses(reason, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as error:  # noqa: BLE001
        assert reason in str(error), "expected %s, got %s" % (reason, error)
        return str(error)
    raise AssertionError("expected refusal %s, but it passed" % reason)


# ---------------------------------------------------------------- fake Show
LIGHT = "<InfinityAttachmentKind.LIGHT: 1>"
PROP = "<InfinityAttachmentKind.PROP: 0>"
STATION = "<InfinityAttachmentAnchor.STATION: 0>"
WING_PAIR = "<InfinityCueType.WING_PAIR: 1>"
ZERO = M.ZERO_GUID
_N = [0]


def _guid():
    _N[0] += 1
    return "%032X" % (0xA000 + _N[0])


def _ext(link=ZERO, follow=False):
    return {"mover": {"enabled": False, "trigger": "ON_APPROACH", "seed": 0, "yaw_amplitude_degrees": 35.0},
            "body": {"follow_light": follow, "light_attachment_guid": link, "flicker": "STABLE", "seed": 0,
                     "intensity_parameter": "Intensity", "full_intensity": -1.0}}


def _row(label, kind, loc, intensity=1200.0, mesh=None, scale=(1.0, 1.0, 1.0), lf=None, units="LUMENS"):
    return {"guid": _guid(), "label": label, "kind": kind, "enabled": True, "actor_class": None, "mesh": mesh,
            "anchor": STATION,
            "relative_transform": {"location": [float(v) for v in loc], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0],
                                   "scale": [float(s) for s in scale]},
            "lighting": {"type": "<InfinityStageLightType.POINT: 0>", "intensity": intensity,
                         "intensity_units": "<InfinityStageLightIntensityUnits.%s: 2>" % units,
                         "color": [1.0, 0.6800000071525574, 0.3400000035762787, 1.0], "use_temperature": True,
                         "temperature_kelvin": 2700.0, "attenuation_radius_cm": 520.0, "source_radius_cm": 4.0,
                         "soft_source_radius_cm": 12.0, "cast_shadows": False, "cast_volumetric_shadow": False,
                         "light_function_material": lf,
                         "drama": {"strike_on_approach": True, "strike_distance_cm": 650.0, "strike_ramp_cm": 150.0,
                                   "unstruck_intensity_scale": 0.0, "after_pass": "<InfinityLightAfterPass.HOLD: 0>"}},
            "effect": {"type": "<InfinityStageEffectType.HAZE: 0>", "linked_light_attachment_guid": ZERO,
                       "replicated_from_attachment_guid": ZERO, "output": 0.5},
            "trigger_distance_cm": 800.0, "ext": _ext()}


def bay(n, look="MOODY", practicals=True):
    p = "P04 SCORE B%02d %s " % (n, look)
    rows = [_row(p + "TOP_L", LIGHT, (0, -360, 1180), 5000.0), _row(p + "TOP_R", LIGHT, (0, 360, 1180), 5000.0)]
    if practicals:
        rows += [_row(p + "PRACTICAL_L", LIGHT, (-20, -700, 150), lf="/Game/InfinityStage/Lighting/MI_LF_Flicker_Slow"),
                 _row(p + "PRACTICAL_L_BODY", PROP, (-20, -700, 150), mesh="/Game/KK/SM_Lamp_Ceiling", scale=(.5, .5, .5)),
                 _row(p + "PRACTICAL_R", LIGHT, (-20, 700, 115), 0.0),
                 _row(p + "PRACTICAL_R_BODY", PROP, (-20, 700, 115), mesh="/Engine/BasicShapes/Sphere")]
    return rows


IDENT = {"location": [0.0, 0.0, 0.0], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]}


def make_plain(station_shift=(0.0, 0.0, 0.0), station_quat=(0.0, 0.0, 0.0, 1.0)):
    cues, stations = [], []
    cues.append({"show_index": 50, "guid": _guid(), "label": "P03 Wing 009", "type": WING_PAIR,
                 "occurrence_offset": copy.deepcopy(IDENT), "attachments": bay(9, "P03LOOK")})
    for i, n in enumerate((8, 9, 10)):
        g = _guid()
        cues.append({"show_index": 106 + i, "guid": g, "label": "P04 Wing %03d" % n, "type": WING_PAIR,
                     "occurrence_offset": copy.deepcopy(IDENT), "attachments": bay(n, practicals=(n != 10))})
        x = 250.0 + 500.0 * (n - 1)
        world = {"location": [x, 240000.0, 0.0], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]}
        if n == 9:
            world["location"] = [world["location"][k] + station_shift[k] for k in range(3)]
            world["rotation_xyzw"] = list(station_quat)
        stations.append({"cue_guid": g, "distance_cm": x, "world": world})
    return {"cues": cues, "bay_guids": [c["guid"] for c in cues[1:]], "passage_guid": "P" * 32,
            "stations": stations}


def opts(**kw):
    a = {"mode": "DRY"}
    a.update(kw)
    return M.check_args(a)


def all_rows(plain):
    return {c["guid"]: c["attachments"] for c in plain["cues"]}


def cue_of(plain, label):
    return [c for c in plain["cues"] if c["label"] == label][0]


MINTED = ["%032X" % 0xBEEF01, "%032X" % 0xBEEF02]


# ---------------------------------------------------------------- cases
@case("plan: computed relative from the live station frame == nominal (40, 383, 200); both reported")
def _():
    plain = make_plain()
    plan = M.build_plan(plain, opts())
    f = plan["frame"]
    assert max(abs(a - b) for a, b in zip(f["relative_computed_cm"], [40.0, 383.0, 200.0])) < 1e-9, f
    assert f["relative_nominal_cm"] == [40.0, 383.0, 200.0] and f["station_x_nominal_cm"] == 4250.0
    assert plan["planned_light"]["relative_transform"]["location"] == f["relative_computed_cm"]
    assert plan["planned_body"]["relative_transform"]["location"] == f["relative_computed_cm"]
    assert plan["cue_label"] == "P04 Wing 009" and plan["source"]["light_label"] == "P04 SCORE B09 MOODY PRACTICAL_L"


@case("frame: 4 cm station shift passes and is WRITTEN as computed; 10 cm refuses FRAME_DISAGREES")
def _():
    plan = M.build_plan(make_plain(station_shift=(4.0, 0.0, 0.0)), opts())
    assert abs(plan["frame"]["relative_computed_cm"][0] - 36.0) < 1e-9
    assert abs(plan["frame"]["disagreement_cm"] - 4.0) < 1e-9
    assert plan["planned_light"]["relative_transform"]["location"][0] == plan["frame"]["relative_computed_cm"][0]
    refuses("FRAME_DISAGREES", M.build_plan, make_plain(station_shift=(10.0, 0.0, 0.0)), opts())


@case("frame: rotated station (yaw 90) inverts correctly (FTransform maths), so nominal check fails there")
def _():
    h = math.radians(90.0) / 2.0
    plain = make_plain(station_quat=(0.0, 0.0, math.sin(h), math.cos(h)))
    cue = cue_of(plain, "P04 Wing 009")
    out = M.station_relative(plain, cue, dict(opts(), max_frame_disagreement_cm=1.0e9))
    # world delta (40, 383, 200) in a frame yawed +90: local x = +383, local y = -40
    assert max(abs(a - b) for a, b in zip(out["relative_computed_cm"], [383.0, -40.0, 200.0])) < 1e-9, out
    # and composing back gives the world point
    back = M.compose({"location": out["relative_computed_cm"], "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1]},
                     out["pair_world"])["location"]
    assert max(abs(a - b) for a, b in zip(back, [4290.0, 240383.0, 200.0])) < 1e-9
    refuses("FRAME_DISAGREES", M.build_plan, plain, opts())


@case("clone: planned light differs from the source ONLY in the override paths; body ONLY in label/enabled/location")
def _():
    plain = make_plain()
    plan = M.build_plan(plain, opts())
    cue = cue_of(plain, "P04 Wing 009")
    src_l = [r for r in cue["attachments"] if r["label"].endswith("PRACTICAL_L")][0]
    src_b = [r for r in cue["attachments"] if r["label"].endswith("PRACTICAL_L_BODY")][0]
    light, body = M.realize(plan, MINTED)
    paths = {d["path"] for d in TOOL._state_differences(src_l, light)}
    allowed = {"guid", "label", "relative_transform.location[0]", "relative_transform.location[1]",
               "relative_transform.location[2]", "lighting.intensity", "lighting.intensity_units",
               "lighting.attenuation_radius_cm", "lighting.source_radius_cm", "lighting.color[1]", "lighting.color[2]"}
    assert paths <= allowed and {"guid", "label", "lighting.intensity", "lighting.intensity_units"} <= paths, paths
    assert light["lighting"]["light_function_material"] == src_l["lighting"]["light_function_material"]
    assert light["lighting"]["drama"] == src_l["lighting"]["drama"] and light["effect"] == src_l["effect"]
    assert light["guid"] == MINTED[0] and light["label"] == M.LIGHT_LABEL
    assert light["lighting"]["color"] == [1.0, 0.85, 0.65, 1.0] and light["lighting"]["intensity"] == 30000.0
    bpaths = {d["path"] for d in TOOL._state_differences(src_b, body)}
    assert bpaths <= {"guid", "label", "relative_transform.location[0]", "relative_transform.location[1]",
                      "relative_transform.location[2]"}, bpaths
    assert body["mesh"] == src_b["mesh"] and body["relative_transform"]["scale"] == [0.5, 0.5, 0.5]
    assert body["label"] == M.BODY_LABEL and body["guid"] == MINTED[1]
    assert any(w.startswith("STRIKE_ON_APPROACH_CLONED") for w in plan["warnings"])
    assert any(w.startswith("UNITS_OVERRIDDEN|LUMENS->CANDELAS") for w in plan["warnings"])


@case("body link: paired to source light -> remapped to the NEW light; zero+follow -> remap; zero inert -> keep; foreign -> refuse")
def _():
    plain = make_plain()
    cue = cue_of(plain, "P04 Wing 009")
    src_l = [r for r in cue["attachments"] if r["label"].endswith("PRACTICAL_L")][0]
    src_b = [r for r in cue["attachments"] if r["label"].endswith("PRACTICAL_L_BODY")][0]
    plan = M.build_plan(plain, opts())
    assert plan["source"]["body_link_mode"] == "KEEP"
    assert M.realize(plan, MINTED)[1]["ext"]["body"]["light_attachment_guid"] == ZERO
    src_b["ext"]["body"]["light_attachment_guid"] = src_l["guid"]
    src_b["ext"]["body"]["follow_light"] = True
    plan = M.build_plan(plain, opts())
    assert plan["source"]["body_link_mode"] == "REMAP"
    assert M.realize(plan, MINTED)[1]["ext"]["body"]["light_attachment_guid"] == MINTED[0]
    src_b["ext"]["body"]["light_attachment_guid"] = ZERO
    assert M.build_plan(plain, opts())["source"]["body_link_mode"] == "REMAP"
    top = [r for r in cue["attachments"] if r["label"].endswith("TOP_L")][0]
    src_b["ext"]["body"]["light_attachment_guid"] = top["guid"]
    refuses("SOURCE_BODY_LINKED_ELSEWHERE", M.build_plan, plain, opts())


@case("ADD model: appends exactly two rows (cloned fields) and passes scope; every other cue bit-identical")
def _():
    plain = make_plain()
    plan = M.build_plan(plain, opts())
    base = all_rows(plain)
    after = M.add_plain(base, plan, MINTED)
    cue = plan["cue_guid"]
    assert len(after[cue]) == len(base[cue]) + 2 and after[cue][:len(base[cue])] == base[cue]
    assert [r["label"] for r in after[cue][-2:]] == [M.LIGHT_LABEL, M.BODY_LABEL]
    assert all(after[g] == base[g] for g in base if g != cue)
    M.check_scope(TOOL, base, after, plan, MINTED, "after")


@case("ADD read-back tolerance: float32 colour / enum-text units / float32 quat pass; a real value error fails")
def _():
    plain = make_plain()
    plan = M.build_plan(plain, opts())
    base = all_rows(plain)
    after = M.add_plain(base, plan, MINTED)
    cue = plan["cue_guid"]
    light = after[cue][-2]
    light["lighting"]["color"] = [1.0, 0.8500000238418579, 0.6499999761581421, 1.0]
    light["lighting"]["intensity_units"] = "<InfinityStageLightIntensityUnits.CANDELAS: 1>"
    light["relative_transform"]["rotation_xyzw"] = [0.0, 0.0, 1.0e-8, 1.0]
    M.check_scope(TOOL, base, after, plan, MINTED, "after")
    bad = copy.deepcopy(after)
    bad[cue][-2]["lighting"]["intensity"] = 29999.0
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, base, bad, plan, MINTED, "after")
    bad = copy.deepcopy(after)
    bad[cue][-2]["lighting"]["intensity_units"] = "<InfinityStageLightIntensityUnits.LUMENS: 2>"
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, base, bad, plan, MINTED, "after")
    bad = copy.deepcopy(after)   # a NON-override field of the clone must match exactly
    bad[cue][-2]["lighting"]["temperature_kelvin"] = 2700.0001
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, base, bad, plan, MINTED, "after")


@case("scope: fails if any other row changes (other cue, pre-existing row in the target cue, extra/missing row, ext)")
def _():
    plain = make_plain()
    plan = M.build_plan(plain, opts())
    base = all_rows(plain)
    good = M.add_plain(base, plan, MINTED)
    other = [g for g in base if g != plan["cue_guid"]][0]
    cue = plan["cue_guid"]
    for mutate, why in (
            (lambda r: r[other][0]["lighting"].__setitem__("intensity", 1.0), "other cue intensity"),
            (lambda r: r[other][0]["ext"]["mover"].__setitem__("enabled", True), "other cue mover"),
            (lambda r: r[cue][0]["relative_transform"]["location"].__setitem__(2, 1181.0), "target pre-existing row"),
            (lambda r: r[cue].append(copy.deepcopy(r[cue][-1])), "extra row"),
            (lambda r: r[cue].pop(), "missing row"),
            (lambda r: r[cue][-1]["ext"]["body"].__setitem__("flicker", "FAIL"), "new body ext"),
            (lambda r: r[cue][-1].__setitem__("guid", MINTED[0]), "body guid")):
        bad = copy.deepcopy(good)
        mutate(bad)
        refuses("SCOPE_CHANGED", M.check_scope, TOOL, base, bad, plan, MINTED, "after")
    refuses("SCOPE_CHANGED", M.check_scope, TOOL, base, good, plan, MINTED, "before")
    M.check_scope(TOOL, base, copy.deepcopy(base), plan, [], "before")


@case("REMOVE: restores the recorded before rows bit-identical; drift (GLINT row or pre-existing row) refuses")
def _():
    plain = make_plain()
    plan = M.build_plan(plain, opts())
    base = all_rows(plain)
    after = M.add_plain(base, plan, MINTED)
    record = {"passage": "P04", "status": "saved_readback_verified", "minted_guids": list(MINTED),
              "cue_guid": plan["cue_guid"], "cue_label": plan["cue_label"], "plan": plan,
              "before_cue_rows": copy.deepcopy(base[plan["cue_guid"]]),
              "after_cue_rows": copy.deepcopy(after[plan["cue_guid"]])}
    M.check_record(record)
    restored = M.remove_plain(TOOL, after, record)
    assert M._canonical(restored) == M._canonical(base)
    assert TOOL._state_differences(base, restored) == []
    drifted = copy.deepcopy(after)
    drifted[plan["cue_guid"]][-2]["lighting"]["intensity"] = 1.0
    refuses("REMOVE_DRIFT", M.remove_plain, TOOL, drifted, record)
    drifted = copy.deepcopy(after)
    drifted[plan["cue_guid"]][0]["enabled"] = False
    refuses("REMOVE_DRIFT", M.remove_plain, TOOL, drifted, record)
    refuses("REMOVE_RECORD_STATUS", M.check_record, dict(record, status="prepared"))
    refuses("REMOVE_RECORD_GUIDS", M.check_record, dict(record, minted_guids=[MINTED[0]]))
    gone = copy.deepcopy(after)
    del gone[plan["cue_guid"]]
    refuses("REMOVE_DRIFT", M.remove_plain, TOOL, gone, record)


@case("duplicate label: either GLINT label anywhere in the Show refuses; control passes")
def _():
    for label in (M.LIGHT_LABEL, M.BODY_LABEL):
        plain = make_plain()
        cue_of(plain, "P04 Wing 008")["attachments"][0]["label"] = label
        refuses("LABEL_ALREADY_EXISTS", M.build_plan, plain, opts())
    plain = make_plain()
    plan = M.build_plan(plain, opts())
    after_plain = copy.deepcopy(plain)
    cue_of(after_plain, "P04 Wing 009")["attachments"] += M.realize(plan, MINTED)
    refuses("LABEL_ALREADY_EXISTS", M.build_plan, after_plain, opts())   # second ADD refused


@case("GUIDs: minted pair unique, valid, not colliding; each failure mode refuses")
def _():
    plain = make_plain()
    pre = [r["guid"] for c in plain["cues"] for r in c["attachments"]]
    assert len(pre) == len(set(pre))
    M.check_minted(MINTED, pre)
    refuses("MINTED_GUID_NOT_FRESH", M.check_minted, [MINTED[0], pre[3]], pre)
    refuses("MINTED_GUID_DUPLICATE", M.check_minted, [MINTED[0], MINTED[0]], pre)
    refuses("MINTED_GUID_INVALID", M.check_minted, [MINTED[0], ZERO], pre)
    refuses("MINTED_GUID_INVALID", M.check_minted, [MINTED[0], "xyz"], pre)
    refuses("MINTED_COUNT", M.check_minted, [MINTED[0]], pre)


def cpp_replicate(source_rows, target_rows, new_guid):
    """Model of UInfinityStageShowAsset::ReplicateLightAttachments (InfinityStageShowAsset.cpp:572-649)."""
    existing = [r["guid"] for r in target_rows if r["kind"] == LIGHT]
    out = [r for r in target_rows if r["kind"] != LIGHT]
    for i, src in enumerate([r for r in source_rows if r["kind"] == LIGHT]):
        copy_row = copy.deepcopy(src)
        copy_row["guid"] = existing[i] if i < len(existing) else new_guid()
        out.append(copy_row)
    return out


@case("minting model: scratch padded to k+2 lights gives FRESH GUIDs exactly at light ordinals k, k+1 (any m)")
def _():
    plain = make_plain()
    plan = M.build_plan(plain, opts())
    target = cue_of(plain, "P04 Wing 009")["attachments"]
    k = M.light_count(target)
    assert k == plan["light_count"] == 4
    assert plan["scratch"]["cue_label"] in ("P04 Wing 008", "P04 Wing 010")
    pre = {r["guid"] for c in plain["cues"] for r in c["attachments"]}
    for m in (0, 1, 2, 5, 6, 9):
        scratch = [_row("S%d" % i, LIGHT, (0, 0, 0)) for i in range(m)]
        scratch += [_row("BLANK", LIGHT, (0, 0, 0)) for _ in range(M.padding_needed(k, m))]
        counter = [0]

        def fresh():
            counter[0] += 1
            return "%032X" % (0xC0000 + 100 * m + counter[0])
        out = cpp_replicate(scratch, target, fresh)
        vessels = [r for r in out if r["kind"] == LIGHT]
        assert [v["guid"] for v in vessels[:k]] == [r["guid"] for r in target if r["kind"] == LIGHT]
        M.check_minted([vessels[k]["guid"], vessels[k + 1]["guid"]], pre)
    # control: one short of padding leaves ordinal k+1 missing
    scratch = [_row("S", LIGHT, (0, 0, 0)) for _ in range(k + 1)]
    out = cpp_replicate(scratch, target, lambda: "%032X" % 0xD1)
    assert len([r for r in out if r["kind"] == LIGHT]) < k + 2


@case("scratch choice: nearest WingPair cue, never the target, honours avoid list")
def _():
    plain = make_plain()
    target = cue_of(plain, "P04 Wing 009")
    s = M.choose_scratch(plain, target)
    assert s["label"] == "P04 Wing 008" and s["guid"] != target["guid"]
    s2 = M.choose_scratch(plain, target, [s["guid"]])
    assert s2["label"] == "P04 Wing 010"
    refuses("SCRATCH_CUE_MISSING", M.choose_scratch, plain, target, [c["guid"] for c in plain["cues"]])


@case("source lookup: zero/two matches, wrong kind, non-POINT, missing body, effect link all refuse")
def _():
    refuses("SOURCE_LIGHT_COUNT", M.build_plan, make_plain(), opts(source_light_regex=r"^NOPE$"))
    refuses("SOURCE_LIGHT_COUNT", M.build_plan, make_plain(), opts(source_light_regex=r"^P04 SCORE B09 MOODY PRACTICAL_[LR]$"))
    plain = make_plain()
    [r for r in cue_of(plain, "P04 Wing 009")["attachments"] if r["label"].endswith("PRACTICAL_L")][0]["lighting"]["type"] = "<InfinityStageLightType.SPOT: 1>"
    refuses("SOURCE_LIGHT_NOT_POINT", M.build_plan, plain, opts())
    plain = make_plain()
    [r for r in cue_of(plain, "P04 Wing 009")["attachments"] if r["label"].endswith("PRACTICAL_L_BODY")][0]["label"] = "X"
    refuses("SOURCE_BODY_COUNT", M.build_plan, plain, opts())
    plain = make_plain()
    [r for r in cue_of(plain, "P04 Wing 009")["attachments"] if r["label"].endswith("PRACTICAL_L_BODY")][0]["kind"] = LIGHT
    refuses("SOURCE_BODY_KIND", M.build_plan, plain, opts())
    plain = make_plain()
    [r for r in cue_of(plain, "P04 Wing 009")["attachments"] if r["label"].endswith("PRACTICAL_L")][0]["effect"]["linked_light_attachment_guid"] = "1" * 32
    refuses("SOURCE_EFFECT_GUID_LINK", M.build_plan, plain, opts())
    # R works when chosen explicitly
    plan = M.build_plan(make_plain(), opts(source_light_regex=r"^P04 SCORE B\d{2} \S+ PRACTICAL_R$"))
    assert plan["source"]["light_label"].endswith("PRACTICAL_R")


@case("target cue: label must resolve once inside the passage bays; GUID pin and passage pin enforced")
def _():
    plain = make_plain()
    plain["bay_guids"].remove(cue_of(plain, "P04 Wing 009")["guid"])
    refuses("TARGET_CUE_COUNT", M.build_plan, plain, opts())
    plain = make_plain()
    good = cue_of(plain, "P04 Wing 009")["guid"]
    M.build_plan(plain, opts(), {"cue_guid": good, "passage_guid": "P" * 32})
    refuses("TARGET_CUE_GUID_DRIFT", M.build_plan, plain, opts(), {"cue_guid": "F" * 32})
    refuses("TARGET_CUE_GUID_DRIFT", M.build_plan, plain, opts(expected_cue_guid="E" * 32))
    refuses("PASSAGE_GUID_DRIFT", M.build_plan, plain, opts(), {"cue_guid": good, "passage_guid": "Q" * 32})


@case("real P04 scores record pins Wing 009 to D84BDBAE... in passage 0067B5F5... (measured file)")
def _():
    pin = M.load_pin()
    assert pin == {"cue_guid": "D84BDBAEDF4EE4A952894D82ECD2841F",
                   "passage_guid": "0067B5F57142956FB5B80EA31B1210B5"}, pin


@case("args: confirm tokens, unknown keys, ranges")
def _():
    assert M.check_args({})["mode"] == "DRY"
    refuses("CONFIRM_MISSING", M.check_args, {"mode": "ADD"})
    refuses("CONFIRM_MISSING", M.check_args, {"mode": "ADD", "confirm": "REMOVE P04GLINT"})
    assert M.check_args({"mode": "ADD", "confirm": "ADD P04GLINT"})["mode"] == "ADD"
    assert M.check_args({"mode": "REMOVE", "confirm": "REMOVE P04GLINT"})["mode"] == "REMOVE"
    refuses("MODE_INVALID", M.check_args, {"mode": "APPLY"})
    refuses("ARGS_UNKNOWN", M.check_args, {"intensity": 5})
    refuses("COLOR_RANGE", M.check_args, {"color_rgb": [1.0, 2.0, 0.0]})
    refuses("ROTATION_NOT_UNIT", M.check_args, {"rotation_xyzw": [0, 0, 0, 2]})
    refuses("CAST_SHADOWS_NOT_BOOL", M.check_args, {"cast_shadows": 0})


@case("context gate: DRY ignores dirt; ADD refuses PIE / Sequencer / ZZ_ / dirty / out-of-scope allow_dirty")
def _():
    clean = {"census": {"content": [], "maps": []}}
    M.check_context({"census": {"content": ["/Game/X"], "maps": []}, "pie": True}, "DRY")
    M.check_context(clean, "ADD", (), "/Game/S", "/Game/W")
    refuses("PIE_OR_SIE_ACTIVE", M.check_context, dict(clean, pie=True), "ADD")
    refuses("SEQUENCER_IS_OPEN", M.check_context, dict(clean, sequencer_open=True), "REMOVE")
    refuses("STRAY_ZZ_ACTORS", M.check_context, dict(clean, zz_actors=["ZZ_x"]), "ADD")
    refuses("DIRTY_BEFORE", M.check_context, {"census": {"content": ["/Game/S"], "maps": []}}, "ADD", (), "/Game/S", "/Game/W")
    M.check_context({"census": {"content": ["/Game/S"], "maps": []}}, "ADD", ["/Game/S"], "/Game/S", "/Game/W")
    refuses("ALLOW_DIRTY_OUT_OF_SCOPE", M.check_context, clean, "ADD", ["/Game/Other"], "/Game/S", "/Game/W")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "rec.json")
        M.check_add_gate([], path)
        refuses("FOREIGN_ACTIVE_RECORDS_OVERLAP", M.check_add_gate, ["x.json"], path)
        open(path, "w").close()
        refuses("ACTIVE_RECORD_EXISTS", M.check_add_gate, [], path)


@case("foreign scan: active records naming the cue GUID are hits; terminal ones are not")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "CodexX")
        os.makedirs(root)
        g = "D84BDBAEDF4EE4A952894D82ECD2841F"
        with open(os.path.join(root, "a_record.json"), "w") as h:
            json.dump({"status": "saved_readback_verified", "cue": g}, h)
        with open(os.path.join(root, "b_record.json"), "w") as h:
            json.dump({"status": "reverted", "cue": g}, h)
        hits = M.scan_foreign(SCORES, [g], saved_dir=tmp)
        assert [os.path.basename(h["path"]) for h in hits] == ["a_record.json"], hits


@case("self-check: files parse; args/request json; main guard shape; no UE object at module level")
def _():
    for name in ("p04_glint_practical.py", "p04_glint_practical_run.py", "test_p04_glint_practical_offline.py"):
        with open(os.path.join(HERE, name), encoding="utf-8") as handle:
            ast.parse(handle.read())
    with open(os.path.join(HERE, "p04_glint_practical_request.json"), encoding="utf-8") as handle:
        req = json.load(handle)
    assert req["arguments"]["arguments"]["relativeSavedPath"] == "CodexConductor/p04_glint_practical_run.py"
    with open(os.path.join(HERE, "p04_glint_practical_args.json"), encoding="utf-8") as handle:
        args = M.check_args(json.load(handle))
    assert args["mode"] == "DRY" and args["source_light_regex"] == M.DEFAULTS["source_light_regex"]
    with open(os.path.join(HERE, "p04_glint_practical.py"), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    assert M._is_main_guard(tree.body[-1])
    for node in tree.body[:-1]:
        if isinstance(node, ast.Assign):
            assert "unreal." not in ast.unparse(node.value), ast.unparse(node)


def main():
    passed = sum(1 for r in RESULTS if r[1])
    failed = len(RESULTS) - passed
    for name, ok, detail in RESULTS:
        print("%s  %s" % ("PASS" if ok else "FAIL", name))
        if not ok:
            print(detail)
    plan = M.build_plan(make_plain(), opts())
    print("EVIDENCE plan: cue=%s source=%s rel=%s scratch=%s padding=%d warnings=%d"
          % (plan["cue_label"], plan["source"]["light_label"], plan["frame"]["relative_computed_cm"],
             plan["scratch"]["cue_label"], plan["scratch"]["padding"], len(plan["warnings"])))
    print("PASS %d/FAIL %d" % (passed, failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
