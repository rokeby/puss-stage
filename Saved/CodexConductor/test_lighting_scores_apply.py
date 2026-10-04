"""Offline +/- controls for lighting_scores_apply.py (no Unreal, no Show, no writes
outside a temp dir). Run:  python test_lighting_scores_apply.py

The synthetic Show reconstructs the 29 Sep census (pair counts from
Saved/CodexStructure/passage_lighting_survey.json, caster arithmetic from
Docs/Conductor/LIGHTING_TALK_PREP_2026-10-03.md) plus the live P04 prototype
record's GUIDs. It is a MODEL: the summary numbers it prints are inferred, not a
read of the live Show. Every check below has a negative control that must fail.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lighting_scores_apply as L  # noqa: E402  (unreal is None offline -> main() not run)

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS" if condition else "FAIL", name, ("  | " + detail) if detail else ""))


def expect_error(name, fn, needle):
    try:
        fn()
    except Exception as error:  # noqa: BLE001
        text = "%s: %s" % (type(error).__name__, error)
        check(name, needle in text, text[:160])
        return
    check(name, False, "no error raised (expected %s)" % needle)


def guid(*parts):
    return hashlib.md5("|".join(str(p) for p in parts).encode()).hexdigest().upper()


# ---------------------------------------------------------------- synthetic Show
PAIRS = {"P01": 48, "P02": 23, "P03": 21, "P04": 21, "P05": 93, "P06": 55}
STANDARD = ["Cross +Y", "Cross -Y", "Entry Fwd +Y", "Entry Fwd -Y", "Entry High +Y",
            "Entry High -Y", "Entry Top", "Low +Y", "Low -Y"]
P02_STANDARD = ["Cross +Y", "Cross -Y", "Entry Top", "Low +Y", "Low -Y"]


def light(cue_label, name, casts, enabled=True, cue_guid=""):
    return {"guid": guid(cue_guid, name), "label": "%s %s" % (cue_label, name), "kind": "Light",
            "enabled": enabled, "lighting": {"cast_shadows": casts}}


def bay_attachments(passage, ordinal, cue_label, cue_guid):
    rows = []
    std = P02_STANDARD if passage == "P02" else STANDARD
    for name in std:
        if passage == "P01":
            casts = name in ("Entry Top", "Entry Fwd +Y")
        elif passage == "P02":
            casts = name in ("Cross +Y", "Cross -Y", "Entry Top")
        elif passage == "P03" or passage == "P05":
            casts = False
        else:  # P04, P06
            casts = name in ("Entry Top", "Entry Fwd +Y")
        rows.append(light(cue_label, name, casts, cue_guid=cue_guid))
    rows.append(light(cue_label, "Top Down", False, enabled=False, cue_guid=cue_guid))
    if passage == "P01":
        rows.append(light(cue_label, "Float L", False, cue_guid=cue_guid))
        rows.append(light(cue_label, "Float R", False, cue_guid=cue_guid))
        if ordinal == 41:  # the praised blink IS Entry High -Y (made a caster here)
            for row in rows:
                if row["label"].endswith(" Entry High -Y"):
                    row["lighting"]["cast_shadows"] = True
        if ordinal == 1:
            rows.append(light(cue_label, "House L", True, cue_guid=cue_guid))
            rows.append(light(cue_label, "House R", True, cue_guid=cue_guid))
    if passage == "P03":
        # 15 L + 18 R + 14 Slash + 6 Back = 53 casters spread over 21 bays
        if ordinal <= 15:
            rows.append(light(cue_label, "Rig L", True, cue_guid=cue_guid))
        if ordinal <= 18:
            rows.append(light(cue_label, "Rig R", True, cue_guid=cue_guid))
        if ordinal % 3 != 0 or ordinal == 21:
            pass
        if ordinal in (1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 16, 18, 19, 20):
            rows.append(light(cue_label, "Rig Slash", True, cue_guid=cue_guid))
        if ordinal in (3, 6, 9, 12, 15, 21):
            rows.append(light(cue_label, "Rig Back", True, cue_guid=cue_guid))
    blink = {"P02": [19], "P03": [17], "P04": [17], "P05": [7, 8], "P06": [44]}.get(passage, [])
    if ordinal in blink:
        rows.append(light(cue_label, "Blink Spot", True, cue_guid=cue_guid))
        rows.append({"guid": guid(cue_guid, "gobo"), "label": cue_label + " Blink Gobo", "kind": "Prop",
                     "enabled": True, "lighting": {"cast_shadows": False}})
    return rows


def build_show(scores, prototype="APPLIED"):
    cues = [{"guid": guid("opening"), "label": "Opening - Curtain", "type": "SEQUENCE", "attachments": []}]
    passages = []
    p04_pins = scores["passages"]["P04"]["pinned_cue_guids"]
    for passage in sorted(PAIRS):
        first = last = None
        for ordinal in range(1, PAIRS[passage] + 1):
            number = ((ordinal - 1) % 8) + 1 if passage == "P05" else ordinal  # P05 reuses labels
            label = "%s Wing %03d" % (passage, number)
            cue_guid = p04_pins.get(str(ordinal)) if passage == "P04" else None
            cue_guid = cue_guid or guid(passage, ordinal)
            cues.append({"guid": cue_guid, "label": label, "type": "WING_PAIR",
                         "attachments": bay_attachments(passage, ordinal, label, cue_guid)})
            first = first or cue_guid
            last = cue_guid
            if passage == "P03" and ordinal == 10:  # a non-WingPair row INSIDE a range
                cues.append({"guid": guid("p03-seq"), "label": "P03 Wing 010 sting", "type": "SEQUENCE",
                             "attachments": []})
        passages.append({"label": "Passage %d" % int(passage[1:]), "guid": guid("passage", passage),
                         "first_cue_guid": first, "last_cue_guid": last})
        cues.append({"guid": guid("scene", passage), "label": "Scene %d" % int(passage[1:]),
                     "type": "SCENE", "attachments": []})
    # Decoy: a WingPair OUTSIDE every passage range that reuses a P05 label.
    cues.append({"guid": guid("decoy"), "label": "P05 Wing 003", "type": "WING_PAIR",
                 "attachments": bay_attachments("P05", 3, "P05 Wing 003", guid("decoy"))})
    record = None
    if prototype in ("APPLIED", "LABELS_ONLY"):
        pins = [p04_pins[str(i)] for i in range(1, 7)]
        by_guid = {c["guid"]: c for c in cues}
        for i, cue_guid in enumerate(pins, 1):
            cue = by_guid[cue_guid]
            for att in cue["attachments"]:
                if att["kind"] == "Light":
                    att["enabled"] = False
            for slot in ("LOW_SIDE_A", "LOW_SIDE_B"):
                cue["attachments"].append({"guid": guid("proto", i, slot), "label": "P04 LOOK B%02d X %s" % (i, slot),
                                           "kind": "Light", "enabled": True, "lighting": {"cast_shadows": True}})
        if prototype == "APPLIED":
            record = {"status": "saved_readback_verified", "plan": {"target_cue_guids": sorted(pins)}}
    return cues, passages, record


# ---------------------------------------------------------------- setup
TOOL = L.load_p04_tool()
SCORES = L.load_scores()
BASE, BASE_INFO = L.load_base_looks(SCORES)
LOOKS = L.resolve_looks(SCORES, BASE)


def plan_for(passage, scores=None, prototype="APPLIED", cues=None, passages=None, record="default",
             absent=None):
    scores = scores or SCORES
    looks = L.resolve_looks(scores, BASE)
    built_cues, built_passages, built_record = build_show(scores, prototype)
    return L.build_score_plan(TOOL, scores, looks, passage, passages or built_passages, cues or built_cues,
                              built_record if record == "default" else record, absent)


print("== 1. loader: P04 tool imported without running its main()")
check("+ real P04 tool loads, API intact, expand_bay callable",
      callable(getattr(TOOL, "expand_bay", None)), "sha256=" + TOOL.SCORES_SOURCE_SHA256[:16])
temp = tempfile.mkdtemp(prefix="scores_harness_")
try:
    source = open(L.P04_TOOL_PATH, encoding="utf-8").read()
    sentinel = os.path.join(temp, "main_ran.txt")
    armed = source.replace("def main(mode=None):\n",
                           "def main(mode=None):\n    open(%r, 'w').write('ran')\n    return None\n" % sentinel, 1)
    armed_path = os.path.join(temp, "armed_tool.py")
    open(armed_path, "w", encoding="utf-8").write(armed)
    stub = types.ModuleType("unreal")
    saved_unreal = sys.modules.get("unreal")
    sys.modules["unreal"] = stub
    try:
        L.load_p04_tool(armed_path, "_armed_via_loader")
        check("+ loader with a live `unreal` module does NOT run main()", not os.path.exists(sentinel))
        namespace = {"__name__": "_armed_plain", "__file__": armed_path}
        exec(compile(armed, armed_path, "exec"), namespace)
        check("- control: a plain exec with `unreal` present DOES run main() (hazard is real)",
              os.path.exists(sentinel))
    finally:
        if saved_unreal is None:
            sys.modules.pop("unreal", None)
        else:
            sys.modules["unreal"] = saved_unreal
    extra = source.replace("\ndef main(mode=None):", "\nprint('side effect')\n\ndef main(mode=None):", 1)
    extra_path = os.path.join(temp, "extra_tool.py")
    open(extra_path, "w", encoding="utf-8").write(extra)
    expect_error("- loader refuses an extra top-level call", lambda: L.load_p04_tool(extra_path, "_x"),
                 "P04_TOOL_TOP_LEVEL_SIDE_EFFECT")
    drift = source.replace("def expand_bay(config, bay_row):", "def expand_bay(config, bay_row, extra=None):", 1)
    drift_path = os.path.join(temp, "drift_tool.py")
    open(drift_path, "w", encoding="utf-8").write(drift)
    expect_error("- loader refuses API drift (expand_bay signature)", lambda: L.load_p04_tool(drift_path, "_y"),
                 "P04_TOOL_API_DRIFT")
    noguard = source.rstrip()[: -len("if unreal is not None:\n    main()")]
    noguard_path = os.path.join(temp, "noguard_tool.py")
    open(noguard_path, "w", encoding="utf-8").write(noguard + "\nmain()\n")
    expect_error("- loader refuses an unguarded main()", lambda: L.load_p04_tool(noguard_path, "_z"),
                 "P04_TOOL_MAIN_GUARD_SHAPE")
finally:
    shutil.rmtree(temp, ignore_errors=True)

print("\n== 2. GUID-keyed resolution with a duplicate-label fixture (P05)")
cues, passages, record = build_show(SCORES)
p05 = plan_for("P05")
in_range = {c["guid"] for c in cues if c["label"].startswith("P05 Wing") and c["guid"] != guid("decoy")}
check("+ P05 plan targets exactly the 93 in-range GUIDs", set(p05["target_cue_guids"]) == in_range,
      "targets=%d" % len(p05["target_cue_guids"]))
check("+ decoy WingPair with a reused P05 label is untouched", guid("decoy") not in p05["target_cue_guids"])
naive = [sum(1 for c in cues if c["label"] == "P05 Wing %03d" % (((i - 1) % 8) + 1)) for i in range(1, 94)]
check("- control: label-keyed lookup is ambiguous in this fixture (would mis-target)",
      all(n > 1 for n in naive), "min matches per label=%d" % min(naive))
p03 = plan_for("P03")
check("+ non-WingPair row inside P03's range is skipped (21 bays)", p03["bay_count"] == 21)
bad = copy.deepcopy(cues)
for c in bad:
    if c["guid"] == guid("p03-seq"):
        c["type"] = "WING_PAIR"
expect_error("- control: same row as a WingPair -> BAY_COUNT_DRIFT", lambda: plan_for("P03", cues=bad), "BAY_COUNT_DRIFT")
swapped = copy.deepcopy(cues)
i1 = next(i for i, c in enumerate(swapped) if c["guid"] == SCORES["passages"]["P04"]["pinned_cue_guids"]["2"])
swapped[i1], swapped[i1 + 1] = swapped[i1 + 1], swapped[i1]
expect_error("- control: reordered P04 bays -> PINNED_GUID_DRIFT", lambda: plan_for("P04", cues=swapped),
             "PINNED_GUID_DRIFT")

print("\n== 3. outside-target hash guard")
for key in sorted(PAIRS):
    plan = plan_for(key)
    after, rec = L.apply_plain_state(plan, cues)
    before_hash = L.plain_outside_hash(TOOL, cues, plan["target_cue_guids"])
    check("+ %s apply leaves every non-target cue byte-identical" % key,
          L.plain_outside_hash(TOOL, after, plan["target_cue_guids"]) == before_hash)
plan = plan_for("P02")
after, rec = L.apply_plain_state(plan, cues)
tampered = copy.deepcopy(after)
next(c for c in tampered if c["label"] == "P03 Wing 001")["attachments"][0]["enabled"] = False
check("- control: one changed attachment in another passage changes the outside hash",
      L.plain_outside_hash(TOOL, tampered, plan["target_cue_guids"])
      != L.plain_outside_hash(TOOL, cues, plan["target_cue_guids"]))

print("\n== 4. per-passage shadow budget (swap, don't add)")
SUMMARY = {}
for key in sorted(PAIRS):
    plan = plan_for(key)
    after, rec = L.apply_plain_state(plan, cues)
    measured_after = L.passage_casters(TOOL, after, plan["bay_guids"])
    s = plan["shadow"]
    check("+ %s casters after <= before and the model agrees" % key,
          s["passage_after"] <= s["passage_before"] and measured_after == s["passage_after"],
          "before=%d after=%d (retained %d)" % (s["passage_before"], s["passage_after"], s["retained_casters"]))
    SUMMARY[key] = plan
over = copy.deepcopy(SCORES)
over["passages"]["P05"]["shadow_policy"] = "ALL"
check("+ P05 variants are shadowless by data too (policy ALL alone stays in budget)",
      plan_for("P05", scores=over)["shadow"]["passage_after"] == 2)
for name in ("P05_COOL_THEATRICAL", "P05_SOFT_POOL"):
    for slot in over["variants"][name]["instrument_overrides"].values():
        slot.pop("cast_shadows", None)
expect_error("- control: P05 with kit casters ON exceeds its 2-caster budget",
             lambda: plan_for("P05", scores=over), "SHADOW_BUDGET_EXCEEDED")
over = copy.deepcopy(SCORES)
over["passages"]["P03"]["retain"].append({"scope": "passage", "label_suffix": " Rig Back", "expected_count": 6})
expect_error("- control: P03 also retaining the 6 Rig Back casters exceeds 54",
             lambda: plan_for("P03", scores=over), "SHADOW_BUDGET_EXCEEDED")

print("\n== 5. revert is exact")
for key in sorted(PAIRS):
    plan = plan_for(key)
    after, rec = L.apply_plain_state(plan, cues)
    restored = L.revert_plain_state(after, rec)
    check("+ %s apply -> revert restores the Show exactly" % key, L._canonical(restored) == L._canonical(cues))
plan = plan_for("P06")
after, rec = L.apply_plain_state(plan, cues)
drifted = copy.deepcopy(after)
target = next(c for c in drifted if c["guid"] == plan["targets"][0]["cue_guid"])
target["attachments"][-1]["enabled"] = False
expect_error("- control: a hand-edited added fixture blocks revert", lambda: L.revert_plain_state(drifted, rec),
             "REVERT_CURRENT_STATE_DRIFT")
expect_error("- control: re-planning on the applied Show refuses (score already present)",
             lambda: L.build_score_plan(TOOL, SCORES, LOOKS, "P06", passages, after, record), "SCORE_ALREADY_PRESENT")

print("\n== 6. P06 failing gold decays monotonically to dark")
rows = L.validate_scores(SCORES, LOOKS, TOOL)["P06"]["rows"]
seg = [r for r in rows if 13 <= r["ordinal"] <= 55]
mono = all(b["output"][u] <= a["output"][u] for a, b in zip(seg, seg[1:]) for u in L.UNITS)
check("+ P06 bays 13-55: per-bay output non-increasing (cd and lm), ends at zero",
      mono and not L._is_lit(seg[-1]["output"]),
      "bay13=%.0fcd/%.0flm  bay33=%.0fcd/%.0flm  bay55=0" % (seg[0]["output"]["CANDELAS"], seg[0]["output"]["LUMENS"],
                                                             seg[20]["output"]["CANDELAS"], seg[20]["output"]["LUMENS"]))
lit = [r for r in seg if L._is_lit(r["output"])]
check("+ P06 ignition stutter rises while lamps still emit",
      all(b["stutter"] >= a["stutter"] for a, b in zip(lit, lit[1:])),
      "%.2f -> %.2f" % (lit[0]["stutter"], lit[-1]["stutter"]))
bad = copy.deepcopy(SCORES)
bad["passages"]["P06"]["segments"][2]["cycle"][0]["look"] = "GAP"
expect_error("- control: a glimmering GAP as the last bay breaks the monotone-to-dark rule",
             lambda: L.validate_scores(bad, LOOKS, TOOL), "NOT_MONOTONE_DARK")
bad = copy.deepcopy(SCORES)
bad["passages"]["P06"]["segments"][1]["level_to"] = 0.95
expect_error("- control: a failing segment that brightens is refused",
             lambda: L.validate_scores(bad, LOOKS, TOOL), "FAILING_LEVEL_NOT_DECAYING")
bad = copy.deepcopy(SCORES)
bad["passages"]["P06"]["segments"][1]["slot_failures"] = []
bad["passages"]["P06"]["segments"][2]["cycle"][0]["look"] = "P06_GRAND_GOLD"
expect_error("- control: no circuit failures + a lit last bay is refused",
             lambda: L.validate_scores(bad, LOOKS, TOOL), "NOT_MONOTONE_DARK")

print("\n== 7. P04 prototype bays 1-6 are owned by lighting_looks_apply.py")
p04 = plan_for("P04")
check("+ APPLIED prototype -> bays 1-6 skipped, 15 targets",
      [s["bay"] for s in p04["skipped"]] == [1, 2, 3, 4, 5, 6] and len(p04["targets"]) == 15)
after, rec = L.apply_plain_state(p04, cues)
pins = set(SCORES["passages"]["P04"]["pinned_cue_guids"].values())
check("+ prototype cues untouched by the P04 score apply",
      all(L._canonical(a) == L._canonical(b) for a, b in zip(after, cues) if a["guid"] in pins))
expect_error("- control: labels present but no record -> MIXED refused", lambda: plan_for("P04", prototype="LABELS_ONLY"),
             "PROTOTYPE_STATE_MIXED")
expect_error("- control: prototype absent -> refused by default", lambda: plan_for("P04", prototype="ABSENT"),
             "PROTOTYPE_ABSENT")
fallback = plan_for("P04", prototype="ABSENT", absent="AUTHOR_FALLBACK")
check("+ absent + AUTHOR_FALLBACK -> all 21 bays authored from the score", len(fallback["targets"]) == 21)

print("\n== 8. retained lamps")
p01 = plan_for("P01")
after, rec = L.apply_plain_state(p01, cues)
w41 = next(c for c in after if c["label"] == "P01 Wing 041")
blink = next(a for a in w41["attachments"] if a["label"].endswith(" Entry High -Y"))
others = [a for a in w41["attachments"] if a["kind"] == "Light" and not a["label"].startswith("P01 SCORE")
          and a is not blink]
check("+ P01 Wing 041 blink stays enabled; its siblings are disabled", blink["enabled"] and not any(a["enabled"] for a in others))
bad = copy.deepcopy(SCORES)
bad["passages"]["P05"]["retain"][0]["expected_count"] = 3
expect_error("- control: retain count mismatch is refused", lambda: plan_for("P05", scores=bad), "RETAIN_COUNT")

print("\n== 9. foreign active-record interlock")
temp = tempfile.mkdtemp(prefix="scores_records_")
try:
    target_guid = p05["target_cue_guids"][0]
    dashed = "%s-%s-%s-%s" % (target_guid[:8], target_guid[8:16], target_guid[16:24], target_guid[24:])
    os.makedirs(os.path.join(temp, "CodexX"))
    json.dump({"status": "saved_readback_verified", "cue": dashed.lower()},
              open(os.path.join(temp, "CodexX", "swap_record.json"), "w"))
    json.dump({"status": "saved", "cue": target_guid}, open(os.path.join(temp, "CodexX", "old_record.json.reverted-1"), "w"))
    json.dump({"status": "reverted", "cue": target_guid}, open(os.path.join(temp, "CodexX", "done_record.json"), "w"))
    json.dump({"status": "saved", "cue": "0" * 32}, open(os.path.join(temp, "CodexX", "other_record.json"), "w"))
    hits = L.scan_foreign_records([temp], p05["target_cue_guids"])
    check("+ active record naming a target GUID (dashed, lower-case) is found",
          [os.path.basename(h["path"]) for h in hits] == ["swap_record.json"], str([h["path"][-20:] for h in hits]))
    check("- control: archived, reverted and unrelated records are not flagged", len(hits) == 1)
finally:
    shutil.rmtree(temp, ignore_errors=True)

print("\n== 10. score-shape rules")
bad = copy.deepcopy(SCORES)
bad["passages"]["P02"]["segments"][0]["cycle"][0]["look"] = "WASH"
expect_error("- control: WASH in a score is refused", lambda: L.validate_scores(bad, LOOKS, TOOL), "FORBIDDEN_LOOK")
bad = copy.deepcopy(SCORES)
bad["passages"]["P05"]["segments"][0]["cycle"][4]["look"] = "P05_SOFT_POOL"
expect_error("- control: removing P05's phrase gap gives a washed-out run", lambda: L.validate_scores(bad, LOOKS, TOOL),
             "WASHED_OUT_RUN")
bad = copy.deepcopy(SCORES)
bad["passages"]["P03"]["segments"][1]["bays"] = [8, 21]
expect_error("- control: an uncovered bay is refused", lambda: L.validate_scores(bad, LOOKS, TOOL), "BAYS_UNCOVERED")
p01_rows = {t["ordinal"]: t for t in p01["targets"]}
strikes = [p01_rows[i]["fixtures"][0]["distance_keying"]["strike_distance_cm"] for i in range(3, 13)]
check("+ P01 ping cascade: strike distance grows 650 -> 4700 cm across bays 3-12 (runs ahead of camera)",
      strikes == [650.0 + 450.0 * i for i in range(10)], "%s" % strikes[:3])

print("\n== summary (MODEL census, inferred; DRY on the live Show is the measurement)")
print("passage bays targets skipped fixtures lights props disabled retained casters_before->after")
for key, plan in sorted(SUMMARY.items()):
    print("%s %4d %7d %7d %8d %6d %5d %8d %8d %4d -> %d" % (
        key, plan["bay_count"], len(plan["targets"]), len(plan["skipped"]), plan["fixture_count"],
        plan["light_fixture_count"], plan["practical_prop_count"], plan["existing_lights_disabled"],
        len(plan["retained"]), plan["shadow"]["passage_before"], plan["shadow"]["passage_after"]))
failed = [name for name, ok, unused in RESULTS if not ok]
print("\n%d checks, %d passed, %d failed" % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
sys.exit(1 if failed else 0)
