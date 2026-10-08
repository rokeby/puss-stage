"""Offline harness for FixturesFollow (FOLLOW / SCALE / RELOCATE + glimmer config). Every positive check has a
negative control that must FAIL the same predicate, so a check that cannot fail is caught.

  python test_fixtures_follow.py     -> prints PASS/FAIL lines, FIXFOLLOW_HARNESS_OK|passed=N|failed=0 or exits 1;
                                        writes harness_result.json
"""
import copy
import json
import math
import os
import runpy
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
F = types.SimpleNamespace(**runpy.run_path(os.path.join(HERE, "fixtures_common.py"), run_name="_fc_test"))
TOOL = runpy.run_path(os.path.join(HERE, "fixtures_follow.py"), run_name="_ff_test")
TABLE = F.M.load_fixture_table(check_files=False)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), str(detail)[:300]))


def raises(fn, needle):
    try:
        fn()
    except Exception as error:  # noqa: BLE001
        return needle in str(error)
    return False


IDENT = F.xf([0, 0, 0], [0, 0, 0, 1])
LANTERN = TABLE["SM_Lantern_ParCan"]
LO, HI = LANTERN["bounds_min"], LANTERN["bounds_max"]
SIZE1 = F.M.housing_size(LANTERN, 1.0)
SIZE3 = F.M.housing_size(LANTERN, 3.0)


def light_row(guid, loc, q, enabled=True, kind="LIGHT", anchor="STATION", label="P0X SCORE B01 X TOP_L"):
    return {"guid": guid, "label": label, "kind": "<InfinityAttachmentKind.%s: 1>" % kind, "enabled": enabled,
            "anchor": "<InfinityAttachmentAnchor.%s: 0>" % anchor,
            "relative_transform": {"location": list(loc), "rotation_xyzw": list(q), "scale": [1, 1, 1]}}


# ---------------------------------------------------------------- B: FOLLOW
lw = F.xf([100, 200, 900], [0, 0, 0, 1])
pose = F.housing_pose(lw, [0, 1, 0], LO, HI, SIZE1)
check("B1 housing for a +X light: identity rotation, body centre half a length behind",
      F.dist(pose["centre"], [100 - SIZE1[0] / 2, 200, 900]) < 1e-6 and F.aim_error_deg(pose["rotation_xyzw"], [1, 0, 0]) < 1e-6)
yaw30 = F.quat_axis_angle([0, 0, 1], 30.0)
pose30 = F.housing_pose(F.xf([100, 200, 900], yaw30), [0, 1, 0], LO, HI, SIZE1)
check("B2 a yawed light yaws its housing by the same 30 deg", abs(F.aim_error_deg(pose["rotation_xyzw"], pose30["throw"]) - 30.0) < 1e-6)
down = F.quat_axis_angle([0, 1, 0], 90.0)   # X -> -Z
posev = F.housing_pose(F.xf([0, 0, 900], down), [0, 1, 0], LO, HI, SIZE1)
yv = F.quat_rotate(posev["rotation_xyzw"], [0, 1, 0])
check("B3 a straight-down light uses MakeFromXY(Throw, Across): housing Y == station across",
      abs(posev["throw"][2] + 1) < 1e-9 and F.dist(yv, [0, 1, 0]) < 1e-9, yv)
cues = [{"guid": "C1", "label": "Cue 1", "attachments": [
    light_row("L1", [0, 0, 900], [0, 0, 0, 1]), light_row("L2", [0, 300, 900], yaw30),
    light_row("L3", [0, 0, 500], [0, 0, 0, 1], enabled=False), light_row("L4", [0, 0, 500], [0, 0, 0, 1], anchor="LEFT_PANEL"),
    light_row("P1", [0, 0, 0], [0, 0, 0, 1], kind="PROP")]}]
pl = F.follow_placements(cues, {"C1": IDENT}, {"C1": [0, 1, 0]})
check("B4 placements = enabled STATION lights only (disabled, panel-anchored and props skipped)", [p["guid"] for p in pl] == ["L1", "L2"])
check("B4- control: counting the disabled light would differ", len(pl) != 3)
live_ok = [F.housing_pose(p["light_world"], p["across"], LO, HI, SIZE1) for p in pl]
plan_ok = F.follow_plan(pl, live_ok, (LO, HI), SIZE1)
check("B5- control: housings already on their lights are NOT stale", plan_ok["stale"] == 0, plan_ok["stale"])
cues2 = copy.deepcopy(cues)
cues2[0]["attachments"][0]["relative_transform"]["rotation_xyzw"] = F.quat_axis_angle([0, 1, 0], 25.0)
pl2 = F.follow_placements(cues2, {"C1": IDENT}, {"C1": [0, 1, 0]})
plan_st = F.follow_plan(pl2, live_ok, (LO, HI), SIZE1)
check("B5 a light Gary re-aimed (25 deg tilt) reads stale, the other does not",
      plan_st["stale"] == 1 and plan_st["lights"][0]["stale"] and abs(plan_st["lights"][0]["aim_error_deg"] - 25.0) < 1e-3,
      plan_st["lights"][0])
plan_cnt = F.follow_plan(pl2, live_ok[:1], (LO, HI), SIZE1)
check("B6 an ISM count mismatch is reported, not compared by index", plan_cnt["count_matches"] is False and plan_cnt["stale"] == 0)
mir_a = F.xf([5, 6, 7], [0, 0, 0, 1], [-1, 1, 1])
mir_b = F.xf([5, 6, 7], F.quat_axis_angle([0, 0, 1], 180.0), [1, -1, 1])
check("B7 corner_gap: the same matrix decomposed two ways compares equal (ISM mirror readback)", F.corner_gap(mir_a, mir_b, LO, HI) < 1e-6)
check("B7- control: a genuinely different transform does not", F.corner_gap(mir_a, F.xf([5, 6, 7], [0, 0, 0, 1]), LO, HI) > 1.0)
# measured consistency with the swap's live read-back: the Python GatherFixturePlacements count equals the live
# fixture_body_count recorded by meshy_swap APPLY for passages whose snapshot covers every bay
for p in ("P01", "P02", "P03", "P05"):
    cs, meta = F.snapshot_passage(p)
    rec = json.load(open(os.path.join(F.MESHY_DIR, "meshy_swap_record_%s.json" % p), encoding="utf-8"))
    n = len(F.follow_placements(cs, {c["guid"]: IDENT for c in cs}, {c["guid"]: [0, 1, 0] for c in cs}))
    check("B8 %s placements (%d) == live housings after the swap (%d)" % (p, n, rec["structure_after"]["fixture_body_count"]),
          n == rec["structure_after"]["fixture_body_count"])
MS = TOOL["load_meshy_swap"]()
check("B9 meshy_swap helpers load without running main()/count_cli()", callable(MS._write_structure) and MS.C is not None)
src = open(TOOL["MESHY_SWAP_PATH"], encoding="utf-8").read()
with tempfile.TemporaryDirectory() as tmp:
    bad = os.path.join(tmp, "meshy_swap_bad.py")
    with open(bad, "w", encoding="utf-8") as h:
        h.write(src.replace("\ndef load_common():", "\nprint('side effect')\n\ndef load_common():", 1))
    check("B9- control: a copy with an extra top-level call is refused", raises(lambda: TOOL["load_meshy_swap"](bad), "TOP_LEVEL_EXPR"))
TOOL["check_args"].__globals__["F"] = F
check("B10 FOLLOW REVERT is refused with the reason", raises(lambda: TOOL["check_args"]({"op": "FOLLOW", "mode": "REVERT",
      "passage": "P01", "confirm": "REVERT FIXFOLLOW FOLLOW P01"}), "FOLLOW_REVERT_NOT_APPLICABLE"))
check("B10- control: APPLY without the exact confirm is refused", raises(lambda: TOOL["check_args"]({"op": "SCALE", "mode": "APPLY",
      "passage": "P01", "plan_sha256": "0" * 64}), "CONFIRM_MISSING"))

# ---------------------------------------------------------------- C: SCALE
cs, meta = F.snapshot_passage("P03")
h = meta["meshy_housing"]
sp = F.scale_plan("P03", cs, TABLE, meta["derived_index"], {"lantern": h["lantern"], "body_size_cm": h["body_size_cm"]}, F.SCALE_DEFAULTS)
rows = {r["guid"]: r for c in cs for r in c["attachments"]}
worst, worst_bad = 0.0, 0.0
for t in sp["targets"]:
    for c in t["changes"]:
        before = rows[c["guid"]]["relative_transform"]
        fx = TABLE[c["variant"]]
        g0 = F.glass_centre_world(before, fx)
        g1 = F.glass_centre_world(c["after"]["relative_transform"], fx)
        worst = max(worst, F.dist(g0, g1))
        naive = dict(before, scale=c["after"]["relative_transform"]["scale"])
        worst_bad = max(worst_bad, F.dist(g0, F.glass_centre_world(naive, fx)))
check("C1 every bulb scales about its glass centre (glass stays put, <= 1e-3 cm)", sp["counts"]["bulbs"] == 21 and worst < 1e-3, worst)
check("C1- control: scaling about the pivot would move the glass > 10 cm", worst_bad > 10.0, worst_bad)
check("C2 bulbs 3.2 -> 9.6", all(c["scale_after"] == 9.6 for t in sp["targets"] for c in t["changes"]))
check("C3 housing body size x3 and the lens offset x3",
      sp["housing"]["body_size_after"] == F.M.housing_size(TABLE[h["lantern"]], 3.0)
      and all(abs(a - 3 * b) < 0.01 for a, b in zip(sp["housing"]["lens_offset_after_cm"], sp["housing"]["lens_offset_before_cm"])),
      sp["housing"])
check("C4- control: a second SCALE on a 3x structure is refused (no double apply)",
      raises(lambda: F.scale_plan("P03", cs, TABLE, meta["derived_index"], {"lantern": h["lantern"],
             "body_size_cm": sp["housing"]["body_size_after"]}, F.SCALE_DEFAULTS), "HOUSING_SCALE_UNEXPECTED"))
cs_wrong = copy.deepcopy(cs)
for c in cs_wrong:
    for r in c["attachments"]:
        if r["guid"] == sp["targets"][0]["changes"][0]["guid"]:
            r["relative_transform"]["scale"] = [9.6, 9.6, 9.6]
sp_w = F.scale_plan("P03", cs_wrong, TABLE, meta["derived_index"], {"lantern": h["lantern"], "body_size_cm": h["body_size_cm"]}, F.SCALE_DEFAULTS)
check("C5- control: a bulb not at the expected 3.2 is refused, not rescaled", sp_w["counts"]["refused"] == 1 and sp_w["counts"]["bulbs"] == 20)
grid = {"height_cm": 1150.0, "beam_depth_cm": 180.0, "beam_width_cm": 80.0, "half_width_cm": 1350.0}
boxes = F.grid_boxes(IDENT, grid, F.xf([600, 0, 0], [0, 0, 0, 1]))
up_light = F.xf([0, 300, 1150], [0, 0, 0, 1])
box_hit = F.obb_from_fit(F.housing_pose(up_light, [0, 1, 0], LO, HI, SIZE3), LO, HI)
box_far = F.obb_from_fit(F.housing_pose(F.xf([300, 300, 600], [0, 0, 0, 1]), [0, 1, 0], LO, HI, SIZE3), LO, HI)
check("C6 a housing at crossbeam height interpenetrates it", F.obb_overlap(box_hit, boxes[0]["box"]))
check("C6- control: one 5.5 m below and between stations does not", not any(F.obb_overlap(box_far, b["box"]) for b in boxes))
check("C7 rails are built at +-half width, one depth up", len(boxes) == 3 and abs(boxes[1]["box"]["centre"][2] - 1330.0) < 1e-6
      and abs(abs(boxes[1]["box"]["centre"][1]) - 1350.0) < 1e-6)

# ---------------------------------------------------------------- D: RELOCATE (+ glimmer)
plans = {}
for p in F.PASSAGES:
    cs_p, meta_p = F.snapshot_passage(p)
    plans[p] = (cs_p, meta_p, F.relocate_plan(p, cs_p, TABLE, meta_p["derived_index"], F.RELOCATE_DEFAULTS))
cs1, meta1, rp1 = plans["P01"]
check("D1 deterministic: the same inputs give the same plan sha",
      F.plan_sha(rp1) == F.plan_sha(F.relocate_plan("P01", cs1, TABLE, meta1["derived_index"], F.RELOCATE_DEFAULTS)))
o2 = copy.deepcopy(F.RELOCATE_DEFAULTS)
o2["seed"] = "other"
check("D1- control: another seed gives another plan", F.plan_sha(rp1) != F.plan_sha(F.relocate_plan("P01", cs1, TABLE, meta1["derived_index"], o2)))
allbad = {p: F.relocate_checks(v[2], TABLE) for p, v in plans.items()}
check("D2 every passage: lane clear, inside the lateral max, cords from cap to crossbeam underside, vertical",
      all(not b for b in allbad.values()), allbad)
bad_plan = copy.deepcopy(rp1)
for t in bad_plan["targets"]:
    for c in t["changes"]:
        if c["what"].startswith("BULB_"):
            c["glass"][1] = 20.0
            break
    else:
        continue
    break
check("D2- control: a bulb moved into the camera lane is caught", any(b[0] == "LATERAL" for b in F.relocate_checks(bad_plan, TABLE)))
rest_err, rest_bad = 0.0, 0.0
for p, (cs_p, meta_p, rp) in plans.items():
    for t in rp["targets"]:
        for c in t["changes"]:
            if "GROUND" not in c["what"]:
                continue
            fx = TABLE[c["variant"]]
            tr = c["after"]["relative_transform"]
            zmin = min(F.xf_point(tr, k)[2] for k in F.bounds_corners(fx["bounds_min"], fx["bounds_max"]))
            rest_err = max(rest_err, abs(zmin - c["glass"][2]))
            wrong = dict(tr, rotation_xyzw=[0, 0, 0, 1])
            rest_bad = max(rest_bad, abs(min(F.xf_point(wrong, k)[2] for k in F.bounds_corners(fx["bounds_min"], fx["bounds_max"])) - c["glass"][2]))
check("D3 every ground bulb rests its lowest bound corner on the floor (<= 1e-3 cm)", rest_err < 1e-3, rest_err)
check("D3- control: the same location with the hanging rotation would not rest", rest_bad > 1.0, rest_bad)
check("D4 working practicals stay in their lanterns: P02 12 (800 lm PRACTICAL_R), P01 1 (300 lm)",
      plans["P02"][2]["counts"]["working"] == 12 and plans["P01"][2]["counts"]["working"] == 1)
o3 = copy.deepcopy(F.RELOCATE_DEFAULTS)
o3["working_lumens"] = 10000.0
check("D4- control: with the threshold lifted they would be relocated",
      F.relocate_plan("P02", plans["P02"][0], TABLE, plans["P02"][1]["derived_index"], o3)["counts"]["working"] == 0)


def lights_left(cs_p, rp, regex):
    after = F.expected_after({c["guid"]: c["attachments"] for c in cs_p}, rp)
    return sum(1 for rows_ in after.values() for r in rows_
               if F.is_kind(r, "LIGHT") and r["enabled"] and regex.search(r["label"]))


glim_total = {p: sum(1 for c in v[0] for r in c["attachments"] if F.is_kind(r, "LIGHT") and F.GLIMMER_LIGHT_RE.search(r["label"]))
              for p, v in plans.items()}
check("D5 no enabled PRACTICAL_GLIMMER light remains in any passage after the plan",
      all(lights_left(v[0], v[2], F.GLIMMER_LIGHT_RE) == 0 for v in plans.values()) and sum(glim_total.values()) == 32, glim_total)
o4 = copy.deepcopy(F.RELOCATE_DEFAULTS)
o4["glimmer"] = "OFF"
check("D5- control: glimmer OFF leaves them", lights_left(plans["P05"][0], F.relocate_plan("P05", plans["P05"][0], TABLE,
      plans["P05"][1]["derived_index"], o4), F.GLIMMER_LIGHT_RE) == 14)
spots_ok = all(c["glass"] == g["spot"] for v in plans.values() for g in v[2]["glimmers"] for t in v[2]["targets"]
               for c in t["changes"] if c["guid"] == g["body_guid"])
check("D6 each glimmer body becomes a bare Meshy bulb with its glass ON the old glimmer spot", spots_ok
      and all(F.is_fixture_bulb_mesh(c["after"]["mesh"]) for v in plans.values() for t in v[2]["targets"] for c in t["changes"]
              if c["what"] == "GLIMMER_TO_BULB_HANG"))
before1 = {c["guid"]: c["attachments"] for c in cs1}
want1 = F.expected_after(before1, rp1)
check("D7 scope: the planned rows are exactly what changes", not F.scope_problems(want1, want1))
extra = copy.deepcopy(want1)
victim = next(g for g in extra if g not in {t["cue_guid"] for t in rp1["targets"]} or True)
extra[victim][0] = dict(extra[victim][0], enabled=not extra[victim][0]["enabled"])
check("D7- control: one extra row change is caught", len(F.scope_problems(want1, extra)) == 1)
record = {"before_rows": {t["cue_guid"]: before1[t["cue_guid"]] for t in rp1["targets"]},
          "after_rows": {t["cue_guid"]: want1[t["cue_guid"]] for t in rp1["targets"]}}
check("D8 revert model returns every target cue to its before rows", not F.scope_problems(before1, F.revert_model(record, want1)))
check("D8- control: a revert over a drifted cue is refused", raises(lambda: F.revert_model(record, extra), "REVERT_DRIFT"))
n_before = len(F.follow_placements(cs1, {c["guid"]: IDENT for c in cs1}, {c["guid"]: [0, 1, 0] for c in cs1}))
cs1_after = [dict(c, attachments=want1[c["guid"]]) for c in cs1]
n_after = len(F.follow_placements(cs1_after, {c["guid"]: IDENT for c in cs1}, {c["guid"]: [0, 1, 0] for c in cs1}))
removed = sum(1 for t in rp1["targets"] for c in t["changes"] if c["what"] in ("LIGHT_DISABLED", "CORD_FROM_RETIRED_LIGHT", "GLIMMER_LIGHT_TO_CORD"))
check("D9 housings removed == retired lights (%d -> %d, %d retired)" % (n_before, n_after, removed), n_before - n_after == removed)

moved_bulbs = [c for v in plans.values() for t in v[2]["targets"] for c in t["changes"]
               if c["what"].startswith(("BULB_", "GLIMMER_TO_BULB_"))]
check("D10 glow mode: every relocated bulb gets emissive control plus its own dim point light",
      moved_bulbs and all(c["after"]["ext"]["body"]["follow_light"]
                          and c["after"]["ext"]["body"]["emit_point_light"]
                          and c["after"]["ext"]["body"]["point_light_lumens"] == F.RELOCATE_DEFAULTS["point_light_lumens"]
                          for c in moved_bulbs))
no_glow = copy.deepcopy(F.RELOCATE_DEFAULTS)
no_glow["glow_mode"] = "OFF"
no_glow_plan = F.relocate_plan("P01", cs1, TABLE, meta1["derived_index"], no_glow)
check("D10- control: glow OFF does not author a bulb-owned point light",
      all("emit_point_light" not in ((c["after"].get("ext") or {}).get("body") or {})
          for t in no_glow_plan["targets"] for c in t["changes"] if c["what"].startswith(("BULB_", "GLIMMER_TO_BULB_"))))
check("D11 cord sway: every hanging bulb links to its own cord; ground bulbs stay static",
      all(bool(c["after"]["ext"]["body"]["swing_on_cord"]) == ("HANG" in c["what"])
          and ("HANG" not in c["what"] or c["after"]["ext"]["body"]["cord_attachment_guid"] == c["cord_guid"])
          for c in moved_bulbs))
static_opts = copy.deepcopy(F.RELOCATE_DEFAULTS)
static_opts["cord_sway_mode"] = "STATIC"
static_plan = F.relocate_plan("P01", cs1, TABLE, meta1["derived_index"], static_opts)
check("D11- control: STATIC leaves every hanging bulb unswayed",
      not any(c["after"]["ext"]["body"].get("swing_on_cord") for t in static_plan["targets"] for c in t["changes"]
              if c["what"].startswith(("BULB_", "GLIMMER_TO_BULB_"))))
bad_link = copy.deepcopy(rp1)
bad_hang = next(c for t in bad_link["targets"] for c in t["changes"] if "HANG" in c["what"])
bad_hang["after"]["ext"]["body"]["cord_attachment_guid"] = "F" * 32
check("D12- control: a bulb linked to the wrong cord is caught",
      any(b[0] == "CORD_LINK" for b in F.relocate_checks(bad_link, TABLE)))
TOOL["_require_body_readback"].__globals__["F"] = F
TOOL["_require_body_readback"](want1, copy.deepcopy(want1), "harness")
check("D13 Body extension read-back accepts the exact planned glow/sway values", True)
bad_body_read = copy.deepcopy(want1)
victim_cue = next(t["cue_guid"] for t in rp1["targets"] for c in t["changes"] if c["what"].startswith("BULB_"))
victim_guid = next(c["guid"] for t in rp1["targets"] for c in t["changes"] if c["what"].startswith("BULB_"))
next(r for r in bad_body_read[victim_cue] if r["guid"] == victim_guid)["ext"]["body"]["point_light_lumens"] += 1.0
check("D13- control: a point-light setter/read-back lie is caught",
      raises(lambda: TOOL["_require_body_readback"](want1, bad_body_read, "harness"), "BODY_READBACK"))

# ---------------------------------------------------------------- E: scores config
scores = json.load(open(os.path.join(F.CONDUCTOR, "lighting_scores.json"), encoding="utf-8"))
new, removed_slots = F.scores_without_glimmer(scores)
slots = [i["slot"] for look in new["local_looks"].values() for i in look.get("instruments", [])]
check("E1 the edited config has no PRACTICAL_GLIMMER instrument and GAP keeps its PRACTICAL_DEAD",
      "PRACTICAL_GLIMMER" not in slots and "PRACTICAL_DEAD" in slots and removed_slots == {"GAP": ["PRACTICAL_GLIMMER"]})
check("E1- control: the live config still has it (this harness does not edit it)",
      any(i["slot"] == "PRACTICAL_GLIMMER" for look in scores["local_looks"].values() for i in look.get("instruments", [])))
check("E2 idempotent: a second pass removes nothing", F.scores_without_glimmer(new)[1] == {})

passed = sum(1 for r in RESULTS if r[1])
failed = [r for r in RESULTS if not r[1]]
for name, ok, detail in RESULTS:
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  :: " + detail))
with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
    json.dump({"passed": passed, "failed": [r[0] for r in failed], "checks": [{"name": r[0], "ok": r[1]} for r in RESULTS]},
              handle, indent=1)
if failed:
    print("FIXFOLLOW_HARNESS_FAILED|passed=%d|failed=%d" % (passed, len(failed)))
    sys.exit(1)
print("FIXFOLLOW_HARNESS_OK|passed=%d|failed=0" % passed)
