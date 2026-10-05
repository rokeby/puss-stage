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
PAIRS = {"P01": 48, "P02": 23, "P03": 21, "P04": 21, "P05": 93, "P06": 64}
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
# 5 Oct: P03 now keeps side lights in 4 bays only (23 casters), so the control runs on the pre-5-Oct P03 score
over = json.load(open(os.path.join(HERE, "lighting_scores.json.bak-20261005-preP02relight"), encoding="utf-8"))
over["passages"]["P03"]["retain"].append({"scope": "passage", "label_suffix": " Rig Back", "expected_count": 6})
expect_error("- control: pre-5-Oct P03 score also retaining the 6 Rig Back casters exceeds 54",
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
seg = [r for r in rows if 13 <= r["ordinal"] <= 64]
mono = all(b["output"][u] <= a["output"][u] for a, b in zip(seg, seg[1:]) for u in L.UNITS)
check("+ P06 bays 13-64: per-bay output non-increasing (cd and lm), ends at zero",
      mono and not L._is_lit(seg[-1]["output"]),
      "bay13=%.0fcd/%.0flm  bay33=%.0fcd/%.0flm  bay64=0" % (seg[0]["output"]["CANDELAS"], seg[0]["output"]["LUMENS"],
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

print("\n== 11. P06 bays 2-10 yield to lighting_events black mode (Gary 4 Oct), keyed to the 64-cue layout")
# 5 Oct: the live score is rescored to 64 (W&T interleave). Control: the legacy 55-bay score on a 55-cue Show
# keeps the yield DORMANT and plans all 55 bays.
legacy = copy.deepcopy(SCORES)
l6 = legacy["passages"]["P06"]
l6["expected_bay_count"] = 55
l6["segments"][1]["bays"] = [13, 54]
l6["segments"][2]["bays"] = [55, 55]
l6["max_consecutive_lit_exempt"] = [[13, 55]]
l6["monotone_dark_segment"] = [13, 55]
saved_pairs = dict(PAIRS)
PAIRS["P06"] = 55
try:
    cues55, passages55, unused55 = build_show(legacy)
    p06_55 = plan_for("P06", scores=legacy, cues=cues55, passages=passages55)
finally:
    PAIRS.clear()
    PAIRS.update(saved_pairs)
check("+ control: at 55 cues (legacy score) the yield is DORMANT (55 targets, 0 skipped)",
      p06_55["yield_to_events"]["state"] == "DORMANT" and len(p06_55["targets"]) == 55 and not p06_55["skipped"])
rescored = copy.deepcopy(SCORES)
saved_pairs = dict(PAIRS)
PAIRS["P06"] = 64
try:
    cues64, passages64, record64 = build_show(rescored)
    p06_64 = plan_for("P06", scores=rescored, cues=cues64, passages=passages64)
    yielded_guids = [guid("P06", o) for o in range(2, 11)]
    check("+ at 64 cues the yield is ACTIVE: bays 2-10 skipped (owner events), 55 targets",
          p06_64["yield_to_events"]["state"] == "ACTIVE"
          and [s["bay"] for s in p06_64["skipped"]] == list(range(2, 11))
          and all(s["owner"] == "lighting_events_apply.py black_mode" for s in p06_64["skipped"])
          and len(p06_64["targets"]) == 55 and not set(yielded_guids) & set(p06_64["target_cue_guids"]))
    after64, unused = L.apply_plain_state(p06_64, cues64)
    by_before = {c["guid"]: c for c in cues64}
    check("+ yielded cues are byte-identical after the P06 score apply (their lights stay as found)",
          all(L._canonical(c) == L._canonical(by_before[c["guid"]]) for c in after64 if c["guid"] in yielded_guids))
    s = p06_64["shadow"]
    check("+ P06 (64) budget still holds with the yield", s["passage_after"] <= s["passage_before"],
          "before=%d after=%d" % (s["passage_before"], s["passage_after"]))
    no_yield = copy.deepcopy(rescored)
    del no_yield["passages"]["P06"]["yield_to_events"]
    plain64 = plan_for("P06", scores=no_yield, cues=cues64, passages=passages64)
    check("- control: without the yield block the same 64-cue plan DOES target bays 2-10",
          set(yielded_guids) <= set(plain64["target_cue_guids"]) and not plain64["skipped"])
    bad = copy.deepcopy(rescored)
    bad["passages"]["P06"]["retain"].append({"scope": "bay", "bay": 5, "label_suffix": " Entry Top", "expected_count": 1})
    expect_error("- control: a per-bay retain on a yielded bay is refused (scores cannot reach events' bays)",
                 lambda: plan_for("P06", scores=bad, cues=cues64, passages=passages64), "RETAIN_BAY_NOT_TARGET")
finally:
    PAIRS.clear()
    PAIRS.update(saved_pairs)
bad = copy.deepcopy(SCORES)
bad["passages"]["P06"]["yield_to_events"]["bays"] = [2, 70]
expect_error("- control: a yield range beyond its layout is refused", lambda: L.validate_scores(bad, LOOKS, TOOL),
             "BAD_YIELD")

print("\n== 12. P01 house warmers are owned by the Opening tool (Gary 4 Oct: off for the Opening ONLY, on in P01)")
p01h = plan_for("P01")
after_h, unused = L.apply_plain_state(p01h, cues)
w01 = next(c for c in after_h if c["label"] == "P01 Wing 001")
house = {a["label"]: a["enabled"] for a in w01["attachments"] if a["label"].endswith((" House L", " House R"))}
siblings = [a for a in w01["attachments"] if a["kind"] == "Light" and not a["label"].startswith("P01 SCORE")
            and a["label"] not in house]
check("+ P01 Wing 001 House L/R stay enabled after the P01 score apply; their VOID-bay siblings are disabled",
      house == {"P01 Wing 001 House L": True, "P01 Wing 001 House R": True} and bool(siblings)
      and not any(a["enabled"] for a in siblings), str(house))
check("+ the plan reports both as foreign-owned by opening_sequence_apply.py",
      sorted(r["label"] for r in p01h["foreign_owned"]) == ["P01 Wing 001 House L", "P01 Wing 001 House R"]
      and all(r["owner"] == "opening_sequence_apply.py" for r in p01h["foreign_owned"]))
before_h = next(c for c in cues if c["label"] == "P01 Wing 001")
house_before = [a for a in before_h["attachments"] if a["label"] in house]
house_after = [a for a in w01["attachments"] if a["label"] in house]
check("+ the warmers' attachment rows are byte-identical after apply (never edited, not just left enabled)",
      len(house_before) == 2 and L._canonical(house_after) == L._canonical(house_before))
old = copy.deepcopy(SCORES)
old.pop("foreign_owned_lights")
old["passages"]["P01"]["retain"] = [r for r in old["passages"]["P01"]["retain"] if r.get("bay") != 1]
old_after, unused = L.apply_plain_state(plan_for("P01", scores=old), cues)
old_w01 = next(c for c in old_after if c["label"] == "P01 Wing 001")
check("- control: the pre-4-Oct data (no retain, no foreign_owned) DOES disable both warmers (hazard is real)",
      not any(a["enabled"] for a in old_w01["attachments"] if a["label"].endswith((" House L", " House R"))))
bad = copy.deepcopy(SCORES)
bad["passages"]["P01"]["retain"] = [r for r in bad["passages"]["P01"]["retain"] if r.get("label_suffix") != " House L"]
expect_error("- control: dropping the House L retain rule is refused", lambda: L.validate_scores(bad, LOOKS, TOOL),
             "FOREIGN_OWNED_NOT_RETAINED")
bad = copy.deepcopy(SCORES)
next(r for r in bad["passages"]["P01"]["retain"] if r.get("label_suffix") == " House R")["owner"] = "lighting_scores_apply.py"
expect_error("- control: a retain rule naming a different owner is refused",
             lambda: L.validate_scores(bad, LOOKS, TOOL), "FOREIGN_OWNED_NOT_RETAINED")
gone = copy.deepcopy(cues)
w = next(c for c in gone if c["label"] == "P01 Wing 001")
w["attachments"] = [a for a in w["attachments"] if not a["label"].endswith(" House R")]
expect_error("- control: a Show missing House R stops the plan (RETAIN_COUNT)", lambda: plan_for("P01", cues=gone),
             "RETAIN_COUNT")

print("\n== 13. P02 relight (Gary 5 Oct ~15:10): top wash + practicals + uplights, NO cross shots")
p02_static = L.validate_scores(SCORES, LOOKS, TOOL)["P02"]
nc = p02_static["no_cross"]
check("+ P02 enables no_cross_shots; every SPOT in bays 1-23 stays on its own side (static, nominal panels)",
      nc is not None and nc["rows"] and all(r["verdict"].startswith("OK") for r in nc["rows"]),
      "spots=%d verdicts=%s" % (len(nc["rows"]), sorted({r["verdict"] for r in nc["rows"]})))
check("+ the rule is opt-in: only P02 and P03 enable it",
      all(L.validate_scores(SCORES, LOOKS, TOOL)[k]["no_cross"] is None for k in PAIRS if k not in ("P02", "P03")))
p02_plan = plan_for("P02")
p02_bays = {t["ordinal"]: t for t in p02_plan["targets"]}
p02_lights = [(t["ordinal"], f) for t in p02_plan["targets"] for f in t["fixtures"] if f["authored_kind"] == "LIGHT"]
check("+ BEAM_R is gone from every P02 bay", not any(f["slot"] == "BEAM_R" for unused, f in p02_lights))
check("+ every P02 SPOT has volumetric scattering <= 0.15",
      all(float(f["volumetric_scattering"]) <= 0.15 for unused, f in p02_lights if f["type"] == "SPOT"),
      "max=%.2f" % max(float(f["volumetric_scattering"]) for unused, f in p02_lights if f["type"] == "SPOT"))
ups = {o: f for o, f in p02_lights if f["role"] == "LOW_SIDE"}
check("+ uplights only on bays 3, 7, 10, 12, 20, 21, 23, each wing-aimed at its OWN side (aim-aware mirror)",
      sorted(ups) == [3, 7, 10, 12, 20, 21, 23]
      and all((f["transform"]["location_cm"][1] < 0) == (f["aim_wing_side"] == "LEFT") for f in ups.values())
      and [o for o, f in sorted(ups.items()) if f.get("aim_mirrored")] == [3, 10, 21],
      " ".join("B%d:%s@%+.0f" % (o, f["aim_wing_side"][0], f["transform"]["location_cm"][1]) for o, f in sorted(ups.items())))
revived = [f for o, f in p02_lights if f["slot"] in ("PRACTICAL_BULB_DEAD", "PRACTICAL_R")]
check("+ the dead practicals are revived (intensity > 0, lit lamp body) wherever their look is used",
      revived and all(float(f["intensity"]) > 0.0 for f in revived)
      and all(f["visible_mesh"]["mesh"].endswith("SM_Lamp_Ceiling") and f["visible_mesh"]["emissive"] for f in revived),
      "%d lamps" % len(revived))
failing = [p02_bays[o] for o in range(12, 20)]
counts = [t["light_fixture_count"] for t in failing]
check("+ FAILING 12-19 kills the new rig lamp by lamp (light count strictly falls 12->16, then the clamp decays alone)",
      counts[:5] == [5, 4, 3, 2, 1] and counts[4:] == [1, 1, 1, 1]
      and all(t["output"]["LUMENS"] > u["output"]["LUMENS"] for t, u in zip(failing, failing[1:])), str(counts))
check("+ P02 shadow casters fall (uplights only); budget holds",
      p02_plan["shadow"]["budget_ok"] and sum(t["new_shadow_casters"] for t in p02_plan["targets"]) == 7,
      "before=%d after=%d" % (p02_plan["shadow"]["passage_before"], p02_plan["shadow"]["passage_after"]))


def live_goals(plan, panel_abs=1000.0, overrides=None):
    """Fake _apply_live_aims: panels at +-panel_abs, goal = panel + offset."""
    plan = copy.deepcopy(plan)
    for target in plan["targets"]:
        target["aims"] = []
        for fixture in target["fixtures"]:
            if fixture["authored_kind"] != "LIGHT" or (fixture["role"] != "TOP" and "aim_wing_side" not in fixture):
                continue
            side = fixture.get("aim_wing_side") or ("LEFT" if fixture["slot"].endswith("_L") else "RIGHT")
            offset = fixture.get("aim_offset_pair_cm", [0.0, 0.0, 0.0])
            goal = [offset[0], (-panel_abs if side == "LEFT" else panel_abs) + offset[1], offset[2]]
            goal = (overrides or {}).get((target["ordinal"], fixture["slot"]), goal)
            target["aims"].append({"fixture": fixture["label"], "panel": side[0], "target_cm": goal})
    return plan


live = L.require_no_cross_live(live_goals(p02_plan))
check("+ live re-check passes on panels at +-1000 cm (every SPOT, LIVE_PANEL basis)",
      live and all(r["basis"] == "LIVE_PANEL" and r["verdict"] == "OK_SAME_SIDE" for r in live), "spots=%d" % len(live))
expect_error("- control: a live goal past the centre line (TOP_L bay 1 -> y=+900) is refused",
             lambda: L.require_no_cross_live(live_goals(p02_plan, overrides={(1, "TOP_L"): [0.0, 900.0, 300.0]})),
             "NO_CROSS_SHOT|passage=P02|bay=1|slot=TOP_L")
check("+ a TOP goal inside the centre tolerance is allowed (OK_TOP_CENTRE_TOLERANCE)",
      any(r["verdict"] == "OK_TOP_CENTRE_TOLERANCE" for r in L.require_no_cross_live(
          live_goals(p02_plan, overrides={(1, "TOP_L"): [0.0, 60.0, 300.0]}))))
expect_error("- control: an uplight goal inside the tolerance is NOT (tolerance is TOP-only)",
             lambda: L.require_no_cross_live(live_goals(p02_plan, overrides={(7, "LOW_SIDE_L_KEY"): [0.0, 60.0, 700.0]})),
             "verdict=CROSS")
expect_error("- control: a narrow bay (panels +-600) puts the y=-800 uplight BEHIND its wing",
             lambda: L.require_no_cross_live(live_goals(p02_plan, panel_abs=600.0)), "verdict=BEHIND_PANEL")
old = json.load(open(os.path.join(HERE, "lighting_scores.json.bak-20261005-preP02relight"), encoding="utf-8"))
old["passages"]["P02"]["no_cross_shots"] = True
expect_error("- control: the pre-relight P02 score (BEAM_R across, LOW_SIDE yaw 72) fails the rule",
             lambda: L.validate_scores(old, L.resolve_looks(old, BASE), TOOL), "NO_CROSS_SHOT|passage=P02|bay=1")
bad = copy.deepcopy(SCORES)
bad["variants"]["P02_THEATRICAL_TOP"]["drop_slots"] = ["BEAM_R", "LOW_SIDE_R_FILL"]
expect_error("- control: keeping the base cross-aimed LOW_SIDE_L_KEY (fixed rotation) fails",
             lambda: L.validate_scores(bad, L.resolve_looks(bad, BASE), TOOL), "slot=LOW_SIDE_L_KEY,role=LOW_SIDE")
bad = copy.deepcopy(SCORES)
bad["passages"]["P02"]["segments"][0]["cycle"][0]["overrides"] = {"TOP_L": {"aim_wing_side": "RIGHT"}}
expect_error("- control: a bay override aiming TOP_L at the RIGHT wing fails",
             lambda: L.validate_scores(bad, LOOKS, TOOL), "slot=TOP_L,role=TOP")
saved_mirror = L._mirror_explicit_aims
L._mirror_explicit_aims = lambda fixtures, spec: None
try:
    expect_error("- control: legacy mirror (position flipped, aim not) makes bay 3's uplight a cross shot",
                 lambda: L.validate_scores(SCORES, LOOKS, TOOL), "NO_CROSS_SHOT|passage=P02|bay=3|slot=LOW_SIDE_L_KEY")
    legacy = {k: v["specs"] for k, v in L.validate_scores(
        {**SCORES, "passages": {k: p for k, p in SCORES["passages"].items() if k not in ("P02", "P03")}},
        LOOKS, TOOL).items()}
    legacy_fx = {k: [L.bay_fixtures(TOOL, SCORES, LOOKS, k, s) for s in specs if s["look"] != "PROTOTYPE"]
                 for k, specs in legacy.items()}
finally:
    L._mirror_explicit_aims = saved_mirror
now_fx = {k: [L.bay_fixtures(TOOL, SCORES, LOOKS, k, s) for s in specs if s["look"] != "PROTOTYPE"]
          for k, specs in legacy.items()}
check("+ aim-aware mirroring changes no fixture outside P02/P03 (P01, P04-P06 byte-identical)",
      L._canonical(now_fx) == L._canonical(legacy_fx), "passages=%s" % ",".join(sorted(now_fx)))
bad = copy.deepcopy(SCORES)
bad["passages"]["P02"]["no_cross_shots"] = {"enabled": True, "centre_tolerance": 50}
expect_error("- control: a misspelt no_cross_shots key is refused", lambda: L.validate_scores(bad, LOOKS, TOOL),
             "BAD_NO_CROSS_CONFIG")
bad = copy.deepcopy(SCORES)
bad["variants"]["P02_LURID_POP"]["instrument_overrides"]["PRACTICAL_BULB_DEAD"]["visible_mesh"]["mesh"] = "SM_Lamp_Ceiling"
expect_error("- control: a revived-body mesh outside /Game or /Engine is refused",
             lambda: L.resolve_looks(bad, BASE), "PRACTICAL_MESH_MISSING")

print("\n== 14. P03 side lights in ~1 bay in 5 (Gary 5 Oct ~15:35: 'keep only 20% of L R side lighting')")
p03_static = L.validate_scores(SCORES, LOOKS, TOOL)["P03"]
check("+ P03 no-cross rule passes in all 21 bays (static, nominal panels +-500)",
      p03_static["no_cross"] and all(r["verdict"].startswith("OK") for r in p03_static["no_cross"]["rows"]),
      "spots=%d" % len(p03_static["no_cross"]["rows"]))
p03_plan = plan_for("P03")
side_slots = ("LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "BEAM_R")
side_bays = {t["ordinal"]: [f for f in t["fixtures"] if f["authored_kind"] == "LIGHT" and f["slot"] in side_slots]
             for t in p03_plan["targets"]}
kept = sorted(o for o, rows in side_bays.items() if rows)
check("+ side lights (key, fill, shaft) only in bays 4, 8, 13, 18 = 4/21 (19%)", kept == [4, 8, 13, 18]
      and all(len(side_bays[o]) == 3 for o in kept), str(kept))
keys = {o: next(f for f in side_bays[o] if f["slot"] == "LOW_SIDE_L_KEY") for o in kept}
check("+ the kept key alternates L/R/L/R and every kept side lamp is aimed at its own side",
      [("L" if keys[o]["transform"]["location_cm"][1] < 0 else "R") for o in kept] == ["L", "R", "L", "R"]
      and all((f["transform"]["location_cm"][1] < 0) == (f["aim_wing_side"] == "LEFT") for o in kept for f in side_bays[o]))
check("+ pyre bays without side lights keep the fire clamp (1600 lm x level, FAULT)",
      all(any(f["slot"] == "PRACTICAL_CLAMP" and f["flicker"]["mode"] == "FAULT" and f["color_rgb_linear"] == [1.0, 0.5, 0.18]
              for f in t["fixtures"]) for t in p03_plan["targets"] if t["look"] == "P03_PYRE"),
      "pyre-no-side bays=%s" % [t["ordinal"] for t in p03_plan["targets"] if t["look"] == "P03_PYRE"])
check("+ the 14 Rig Slash + Blink Spot are still retained, budget holds",
      len(p03_plan["retained"]) == 15 and p03_plan["shadow"]["budget_ok"],
      "casters before=%d after=%d" % (p03_plan["shadow"]["passage_before"], p03_plan["shadow"]["passage_after"]))
check("+ P03 live re-check passes on panels at +-500 cm (the narrowest measured)",
      all(r["verdict"].startswith("OK") for r in L.require_no_cross_live(live_goals(p03_plan, panel_abs=500.0))))
expect_error("- control: P03 panels at +-380 put the |y| 400 side lamps BEHIND their wing",
             lambda: L.require_no_cross_live(live_goals(p03_plan, panel_abs=380.0)), "verdict=BEHIND_PANEL")
old3 = json.load(open(os.path.join(HERE, "lighting_scores.json.bak-20261005-preP02relight"), encoding="utf-8"))
old3["passages"]["P03"]["no_cross_shots"] = True
expect_error("- control: the pre-5-Oct P03 score fails the rule (side lights across)",
             lambda: L.validate_scores(old3, L.resolve_looks(old3, BASE), TOOL), "NO_CROSS_SHOT|passage=P03|bay=1")

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
