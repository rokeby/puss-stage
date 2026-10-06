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

print("\n== 6. P06 failing gold decays monotonically to dark (6 Oct round 2: the failing tail is the last third, 43-64)")
rows = L.validate_scores(SCORES, LOOKS, TOOL)["P06"]["rows"]
seg = [r for r in rows if 43 <= r["ordinal"] <= 64]
mono = all(b["output"][u] <= a["output"][u] for a, b in zip(seg, seg[1:]) for u in L.UNITS)
check("+ P06 bays 43-64: per-bay output non-increasing (cd and lm), ends at zero",
      mono and not L._is_lit(seg[-1]["output"]),
      "bay43=%.0fcd/%.0flm  bay53=%.0fcd/%.0flm  bay64=0" % (seg[0]["output"]["CANDELAS"], seg[0]["output"]["LUMENS"],
                                                             seg[10]["output"]["CANDELAS"], seg[10]["output"]["LUMENS"]))
lit = [r for r in seg if L._is_lit(r["output"])]
check("+ P06 ignition stutter rises while lamps still emit",
      all(b["stutter"] >= a["stutter"] for a, b in zip(lit, lit[1:])),
      "%.2f -> %.2f" % (lit[0]["stutter"], lit[-1]["stutter"]))
bad = copy.deepcopy(SCORES)
bad["passages"]["P06"]["segments"][5]["cycle"][0]["look"] = "GAP"
expect_error("- control: a glimmering GAP as the last bay breaks the monotone-to-dark rule",
             lambda: L.validate_scores(bad, LOOKS, TOOL), "NOT_MONOTONE_DARK")
bad = copy.deepcopy(SCORES)
bad["passages"]["P06"]["segments"][4]["level_to"] = 0.95
expect_error("- control: a failing segment that brightens is refused",
             lambda: L.validate_scores(bad, LOOKS, TOOL), "FAILING_LEVEL_NOT_DECAYING")
bad = copy.deepcopy(SCORES)
bad["passages"]["P06"]["segments"][4]["slot_failures"] = []
bad["passages"]["P06"]["segments"][5]["cycle"][0]["look"] = "P06_GRAND_GOLD"
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
bad["passages"]["P05"]["segments"][3]["cycle"][0]["look"] = "P05_SOFT_POOL"  # 6 Oct: phrase now 19-84, its gap at bay 19
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
l6["segments"][4]["bays"] = [43, 54]
l6["segments"][5]["bays"] = [55, 55]
l6["max_consecutive_lit_exempt"] = [[2, 10], [22, 55]]
l6["monotone_dark_segment"] = [43, 55]
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
check("+ the rule is opt-in: only P02, P03, P04 (7-21, 11 exempt) and P06 (22-42) enable it (6 Oct round 2)",
      all(L.validate_scores(SCORES, LOOKS, TOOL)[k]["no_cross"] is None for k in PAIRS if k not in ("P02", "P03", "P04", "P06")))
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
revived = [f for o, f in p02_lights if f["slot"] in ("PRACTICAL_BULB_DEAD", "PRACTICAL_R") and not f.get("dim_bulb")]
check("+ the dead practicals are revived (intensity > 0, lit lamp body) wherever their look is used",
      revived and all(float(f["intensity"]) > 0.0 for f in revived)
      and all(f["visible_mesh"]["material"]["mode"] == "MATCH_LIGHT" and f["visible_mesh"]["emissive"] for f in revived),
      "%d lamps" % len(revived))
failing = [p02_bays[o] for o in range(12, 20)]
counts = [t["light_fixture_count"] for t in failing]
check("+ FAILING 12-19 kills the new rig lamp by lamp (light count strictly falls 12->16, then the clamp decays alone)",
      counts[:5] == [5, 4, 3, 2, 1] and counts[4:] == [1, 1, 1, 1]
      and all(t["output"]["LUMENS"] > u["output"]["LUMENS"] for t, u in zip(failing, failing[1:])), str(counts))
check("+ P02 shadow casters (5 Oct ~16:25: 7 uplights + 32 TOP washes) stay within budget",
      p02_plan["shadow"]["budget_ok"] and sum(t["new_shadow_casters"] for t in p02_plan["targets"]) == 39,
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
        {**SCORES, "passages": {k: p for k, p in SCORES["passages"].items() if k not in ("P02", "P03", "P04")}},
        LOOKS, TOOL).items()}
    legacy_fx = {k: [L.bay_fixtures(TOOL, SCORES, LOOKS, k, s) for s in specs if s["look"] != "PROTOTYPE"]
                 for k, specs in legacy.items()}
finally:
    L._mirror_explicit_aims = saved_mirror
now_fx = {k: [L.bay_fixtures(TOOL, SCORES, LOOKS, k, s) for s in specs if s["look"] != "PROTOTYPE"]
          for k, specs in legacy.items()}
check("+ aim-aware mirroring changes no fixture outside P02/P03/P04 (P01, P05, P06 byte-identical; 6 Oct: P04 bay 9 mirrors a wing-aimed uplight)",
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

print("\n== 15. P04 last third (Gary 5 Oct ~16:00): dark, bulbs on the ground by the wings, a strike on the ceiling wing")
LAST = range(15, 22)
RIG_DROP = 127.6  # rig_lamp_drop_record_P04.json plan.drop_cm (score TOPs are authored pre-drop)
# Ceiling border of P04 Wing 017 after the 3 Oct lift: pair x ~0..500, y +-600, z 700..1126 (p04_top_lift.py:8,31-32,53;
# probe_p04_tops_out.json x_center 250, y span 1200). In the pre-drop frame the score is authored in, z is + RIG_DROP.
CEILING = {"x": (0.0, 500.0), "y": (-600.0, 600.0), "z": (700.0 + RIG_DROP, 1126.0 + RIG_DROP)}


def bulb_faults(fixtures):
    """Every practical: on the floor (z 10-20) - or, 6 Oct round 2, a PRACTICAL_HANG bulb hanging at z 180-260 -
    near a wing (|y| 700-1300), warm (2200-2700 K), small pool (<= 400 cm), a bulb body (Sphere). Returns the failures."""
    bad = []
    for f in fixtures:
        if f["authored_kind"] != "LIGHT" or f["role"] != "PRACTICAL":
            continue
        x, y, z = f["transform"]["location_cm"]
        height_ok = (180.0 <= z <= 260.0) if f["slot"] == "PRACTICAL_HANG" else (10.0 <= z <= 20.0)
        if not (height_ok and 700.0 <= abs(y) <= 1300.0 and 2200.0 <= f["temperature_kelvin"] <= 2700.0
                and f["attenuation_cm"] <= 400.0 and f["visible_mesh"]["mesh"] == "/Engine/BasicShapes/Sphere"):
            bad.append("%s B%02d (%.0f,%.0f,%.0f) %.0fK att%.0f" % (f["slot"], f["bay_index"], x, y, z,
                                                                   f["temperature_kelvin"], f["attenuation_cm"]))
    return bad


def strike_faults(fixtures):
    """The ONE non-practical lamp of a strike bay: a SPOT from high (z >= 1100 pre-drop) on the RIGHT (y > 300), aimed by a
    fixed point inside the ceiling border, its rotation = look-at of that point, volumetric <= 0.15."""
    lamps = [f for f in fixtures if f["authored_kind"] == "LIGHT" and f["role"] != "PRACTICAL"]
    if len(lamps) != 1:
        return ["lamps=%s" % [f["slot"] for f in lamps]]
    f = lamps[0]
    src, tgt = f["transform"]["location_cm"], f.get("aim_target_pair_cm")
    bad = []
    if f["type"] != "SPOT" or src[2] < 1100.0 or src[1] <= 300.0:
        bad.append("not from upper right: %s" % src)
    if tgt is None or not all(CEILING[k][0] <= v <= CEILING[k][1] for k, v in zip("xyz", tgt)):
        bad.append("not aimed at the ceiling border: %s" % tgt)
    elif [round(v, 6) for v in f["transform"]["rotation_rpy_deg"]] != [round(v, 6) for v in TOOL._look_at_rpy(src, tgt, "t")]:
        bad.append("rotation is not the look-at of the target")
    if float(f["volumetric_scattering"]) > 0.15:
        bad.append("volumetric %.2f" % f["volumetric_scattering"])
    return bad


p04_plan = plan_for("P04")
p04_bays = {t["ordinal"]: t for t in p04_plan["targets"]}
last_lights = [f for o in LAST for f in p04_bays[o]["fixtures"] if f["authored_kind"] == "LIGHT"]
check("+ bays 15-21 are dark: no LOW_SIDE, no BEAM, and the only TOP is the bay-17 strike",
      not [f for f in last_lights if f["role"] in ("LOW_SIDE", "BEAM")]
      and [(f["bay_index"], f["slot"]) for f in last_lights if f["role"] == "TOP"] == [(17, "TOP_R")],
      " ".join("B%d:%s" % (o, p04_bays[o]["look"]) for o in LAST))
bad = copy.deepcopy(SCORES)
bad["variants"]["P04_GROUND_BULBS"]["drop_slots"] = ["TOP_L", "TOP_R", "LOW_SIDE_R_FILL"]
expect_error("- control: keeping MOODY's cross-aimed LOW_SIDE_L_KEY in the bulb look is refused by the tool",
             lambda: plan_for("P04", scores=bad), "NO_CROSS_SHOT|passage=P04|bay=15|slot=LOW_SIDE_L_KEY")
faults = [x for o in LAST for x in bulb_faults(p04_bays[o]["fixtures"])]
bulbs = [f for f in last_lights if f["role"] == "PRACTICAL"]
check("+ every bulb in 15-21 is on the floor (or hanging, PRACTICAL_HANG) by a wing, warm, small pool, bulb body",
      bulbs and not faults, "%d bulbs, %d dim (were dead), %d flickering%s" % (
          len(bulbs), sum(bool(f.get("dim_bulb")) for f in bulbs), sum(f["flicker"]["mode"] != "STEADY" for f in bulbs),
          (" | " + "; ".join(faults)) if faults else ""))
check("+ each bulb sits on its own side, inside the wing the live P04 record read (bay-level positions)",
      all((f["transform"]["location_cm"][1] < 0) == (f["slot"].endswith("_L") != bool(o == 19))
          for o in LAST for f in p04_bays[o]["fixtures"] if f["authored_kind"] == "LIGHT" and f["role"] == "PRACTICAL"
          and f["slot"] in ("PRACTICAL_L", "PRACTICAL_R")))
check("+ variety: pairs, singles (one dim) and HUM/BUZZ flicker all occur (floor pair counted; dim = revived dead bulb)",
      {sum(f["intensity"] > 0 and not f.get("dim_bulb") for f in p04_bays[o]["fixtures"]
           if f["authored_kind"] == "LIGHT" and f["slot"] in ("PRACTICAL_L", "PRACTICAL_R"))
       for o in LAST} == {1, 2} and {"HUM", "BUZZ"} <= {f["flicker"]["mode"] for f in bulbs})
raised = copy.deepcopy(p04_bays[15]["fixtures"])
next(f for f in raised if f["slot"] == "PRACTICAL_L")["transform"]["location_cm"][2] = 140.0
check("- control: a bulb lifted to z 140 (the old practical height) fails the floor predicate", bulb_faults(raised))
crossed = copy.deepcopy(p04_bays[15]["fixtures"])
next(f for f in crossed if f["slot"] == "PRACTICAL_L")["temperature_kelvin"] = 6500.0
check("- control: a cold 6500 K bulb fails the warm predicate", bulb_faults(crossed))
check("+ bay 17: one hard spot from the upper RIGHT aimed at the ceiling border (Wing 017), low volumetric",
      not strike_faults(p04_bays[17]["fixtures"]) and p04_bays[17]["cue_label"] == "P04 Wing 017",
      str(next(f["aim_target_pair_cm"] for f in p04_bays[17]["fixtures"] if f["slot"] == "TOP_R")))
moved = copy.deepcopy(SCORES)
moved["variants"]["P04_CEILING_STRIKE"]["instrument_overrides"]["TOP_R"]["location_cm"] = [-350.0, -750.0, 1167.6]
expect_error("- control: the same spot moved to the upper LEFT (aimed at the border's right half) is refused by the tool",
             lambda: plan_for("P04", scores=moved), "NO_CROSS_SHOT|passage=P04|bay=17|slot=TOP_R")
lowered = copy.deepcopy(p04_bays[17]["fixtures"])
next(f for f in lowered if f["slot"] == "TOP_R")["transform"]["location_cm"] = [-350.0, 750.0, 300.0]
check("- control: the same spot from LOW on the right fails the strike predicate", strike_faults(lowered))
low = copy.deepcopy(SCORES)
low["variants"]["P04_CEILING_STRIKE"]["instrument_overrides"]["TOP_R"]["aim_target_pair_cm"] = [250.0, 150.0, 300.0]
check("- control: aimed at the wing foot instead of the ceiling fails the strike predicate",
      strike_faults(plan_for("P04", scores=low)["targets"][17 - 7]["fixtures"]))
p04_nc = L.validate_scores(SCORES, LOOKS, TOOL)["P04"]["no_cross"]
check("+ P04 no-cross passes on bays 7-21 (11 exempt): wing tops/uplights own side, strike = AIM_POINT (6 Oct round 2)",
      p04_nc["rows"] and {r["bay"] for r in p04_nc["rows"]} == {8, 9, 12, 17}
      and all(r["verdict"] == "OK_SAME_SIDE" for r in p04_nc["rows"])
      and [r["basis"] for r in p04_nc["rows"] if r["bay"] == 17] == ["AIM_POINT"],
      "%d spots" % len(p04_nc["rows"]))
x = copy.deepcopy(SCORES)
x["variants"]["P04_CEILING_STRIKE"]["instrument_overrides"]["TOP_R"]["aim_target_pair_cm"] = [250.0, -300.0, 1077.6]
expect_error("- control: strike aimed at the LEFT half of the border is a cross shot",
             lambda: L.validate_scores(x, L.resolve_looks(x, BASE), TOOL), "NO_CROSS_SHOT|passage=P04|bay=17|slot=TOP_R")
x = copy.deepcopy(SCORES)
x["variants"]["P04_CEILING_STRIKE"]["instrument_overrides"]["TOP_R"]["attenuation_cm"] = 2000.0
expect_error("- control: the same strike with a 20 m reach carries on past centre (CROSS_BEYOND_TARGET)",
             lambda: L.validate_scores(x, L.resolve_looks(x, BASE), TOOL), "verdict=CROSS_BEYOND_TARGET")
x = copy.deepcopy(SCORES)
x["passages"]["P04"]["no_cross_shots"].pop("exempt_bays")
expect_error("- control: without the bay-11 exemption the cold breakage beam (4 Oct look) is a cross shot",
             lambda: L.validate_scores(x, LOOKS, TOOL), "NO_CROSS_SHOT|passage=P04|bay=11|")
check("+ the bay-17 strike casts shadows (Gary 5 Oct ~16:25; the LOW_SIDE-only rule is gone)",
      next(f for f in p04_bays[17]["fixtures"] if f["slot"] == "TOP_R")["cast_shadows"] is True)
x = copy.deepcopy(SCORES)
x["variants"]["P04_CEILING_STRIKE"]["instrument_overrides"]["TOP_R"]["aim_wing_side"] = "RIGHT"
expect_error("- control: an aim point plus a wing aim on one lamp is refused",
             lambda: L.resolve_looks(x, BASE), "AIM_TARGET_BAD")


class _V:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _Obj:
    def __init__(self, **props):
        self.props = props

    def get_editor_property(self, name):
        return self.props[name]


def fake_show(plan, panel_abs=1000.0):
    def panel(y):
        return _Obj(local_transform=types.SimpleNamespace(translation=_V(0.0, y, 0.0)))
    pair = _Obj(left=panel(-panel_abs), right=panel(panel_abs))
    size = max(t["show_index"] for t in plan["targets"]) + 1
    return _Obj(cues=[_Obj(wing_pair=pair) for unused in range(size)])


live04 = copy.deepcopy(p04_plan)
before = copy.deepcopy(next(f for f in live04["targets"][17 - 7]["fixtures"] if f["slot"] == "TOP_R"))
L._apply_live_aims(TOOL, fake_show(live04), live04)
after = next(f for f in live04["targets"][17 - 7]["fixtures"] if f["slot"] == "TOP_R")
check("+ _apply_live_aims leaves the fixed-point strike alone (it would otherwise re-aim TOP_R at the right wing)",
      after["transform"]["rotation_rpy_deg"] == before["transform"]["rotation_rpy_deg"]
      and not [a for a in live04["targets"][17 - 7]["aims"] if a["fixture"].endswith("TOP_R")])
legacy04 = copy.deepcopy(p04_plan)
for f in legacy04["targets"][17 - 7]["fixtures"]:
    f.pop("aim_target_pair_cm", None)
L._apply_live_aims(TOOL, fake_show(legacy04), legacy04)
check("- control: without the aim point the live-aim pass DOES re-aim TOP_R at the right wing panel",
      any(a["fixture"].endswith("TOP_R") and a["panel"] == "R" for a in legacy04["targets"][17 - 7]["aims"]))
check("+ P04 live re-check passes; P04 retains its Blink Spot; prototype bays 1-6 still skipped; budget holds",
      L.require_no_cross_live(live04) is not None and len(p04_plan["retained"]) == 1
      and [sk["bay"] for sk in p04_plan["skipped"]] == [1, 2, 3, 4, 5, 6] and p04_plan["shadow"]["budget_ok"],
      "casters %d -> %d" % (p04_plan["shadow"]["passage_before"], p04_plan["shadow"]["passage_after"]))

print("\n== 16. lamp bodies get a material (lit = emissive matched to the lamp, dead = dull); all lights may cast")
import importlib.util  # noqa: E402


def load_backup_tool(path, name):
    import importlib.machinery
    spec = importlib.util.spec_from_loader(name, importlib.machinery.SourceFileLoader(name, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OLD_TOOL = load_backup_tool(os.path.join(HERE, "lighting_scores_apply.py.bak-20261005-preBulbBodies"), "_scores_pre_bodies")
OLD_SCORES = json.load(open(os.path.join(HERE, "lighting_scores.json.bak-20261005-preBulbBodies"), encoding="utf-8"))
OLD_P04 = OLD_TOOL.load_p04_tool()
OLD_LOOKS = OLD_TOOL.resolve_looks(OLD_SCORES, OLD_TOOL.load_base_looks(OLD_SCORES)[0])


def fixtures_of(module, tool, scores, looks, key, keep=lambda o: True):
    specs = module.validate_scores(scores, looks, tool)[key]["specs"]
    return [module.bay_fixtures(tool, scores, looks, key, s) for s in specs if s["look"] != "PROTOTYPE" and keep(s["ordinal"])]


# 6 Oct round 2: P01/P04/P05/P06 change on purpose and dead bulbs glow everywhere, so the 5 Oct identity against
# the pre-bodies tool is re-stated against the preRound2 tool + data in section 17 (features off -> identical).
p04_bodies = [f for o in LAST for f in p04_bays[o]["fixtures"] if f.get("role") == "PRACTICAL_BODY"]
p02_bodies = [f for t in p02_plan["targets"] for f in t["fixtures"] if f.get("role") == "PRACTICAL_BODY"
              and f["paired_slot"] in ("PRACTICAL_BULB_DEAD", "PRACTICAL_R") and f["body"]["mode"] == "MATCH_LIGHT"]
lights04 = {(f["bay_index"], f["slot"]): f for o in LAST for f in p04_bays[o]["fixtures"] if f["authored_kind"] == "LIGHT"}
check("+ every P04 bulb body is a derived Bulbs/ mesh: lit -> emissive matched, revived dead -> DIM glow",
      p04_bodies and all(f["mesh"].startswith(L.BODY_ASSET_DIR + "/SM_PB_Bulb_") for f in p04_bodies)
      and all((f["body"]["mode"] == "DIM") == bool(lights04[(f["bay_index"], f["paired_slot"])].get("dim_bulb"))
              for f in p04_bodies), "%d bodies, %d dim" % (len(p04_bodies), sum(f["body"]["mode"] == "DIM" for f in p04_bodies)))
warm = [f["body"]["colour"] for f in p04_bodies if f["body"]["mode"] == "MATCH_LIGHT"]
check("+ live warm bodies are warm (r >= g >= b, b <= 0.25) and brighter than the DIM glow",
      all(c[0] >= c[1] >= c[2] and c[2] <= 0.25 for c in warm)
      and min(f["body"]["intensity"] for f in p04_bodies if f["body"]["mode"] == "MATCH_LIGHT") > L.BODY_DIM_INTENSITY,
      str(sorted({tuple(c) for c in warm})))
k22, k27 = L.kelvin_rgb_linear(2200), L.kelvin_rgb_linear(2700)
check("+ Kelvin tint: 2200 K is redder than 2700 K, 6500 K is near white",
      k22[2] < k27[2] and k22[1] < k27[1] and min(L.kelvin_rgb_linear(6500)) > 0.85, "%s %s" % (k22, k27))
check("+ P02 revived bulbs carry matched emissive bodies (rose / acid / violet keep their hue)",
      len(p02_bodies) == 16 and all(f["body"]["mode"] == "MATCH_LIGHT" for f in p02_bodies)
      and len({tuple(f["body"]["colour"]) for f in p02_bodies}) == 3
      and all(max(range(3), key=lambda i: f["body"]["colour"][i])
              == max(range(3), key=lambda i: next(l for l in p02_lights if l[1]["label"] == f["label"].rsplit("_BODY", 1)[0])[1]
                     ["color_rgb_linear"][i]) for f in p02_bodies),
      str(sorted({tuple(f["body"]["colour"]) for f in p02_bodies})))
assets = L.body_asset_plan([f for t in p04_plan["targets"] + p02_plan["targets"] for f in t["fixtures"]])
check("+ the derived asset plan is small and all under /Game/InfinityStage/Lighting/Bulbs",
      0 < len(assets["mis"]) <= 40 and len(assets["meshes"]) == len(assets["mis"])  # 6 Oct: + DIM tints + caps
      and all(p.startswith(L.BODY_ASSET_DIR + "/") for p in list(assets["mis"]) + list(assets["meshes"])),
      "MIs=%d meshes=%d" % (len(assets["mis"]), len(assets["meshes"])))
x = copy.deepcopy(SCORES)
x["variants"]["P04_GROUND_BULBS"]["instrument_overrides"]["PRACTICAL_L"]["visible_mesh"]["material"]["mode"] = "DEAD"
expect_error("- control: the retired DEAD body mode is refused (6 Oct: dead bulbs glow DIM)",
             lambda: L.resolve_looks(x, BASE), "BAD_BODY_MATERIAL")
x = copy.deepcopy(SCORES)
x["variants"]["P04_GROUND_BULBS"]["instrument_overrides"]["PRACTICAL_L"]["visible_mesh"]["material"]["mode"] = "DIM"
expect_error("- control: a DIM body on a bright (220 lm) lamp is refused",
             lambda: L.validate_scores(x, L.resolve_looks(x, BASE), TOOL), "BODY_DIM_ON_BRIGHT_LAMP")
x = copy.deepcopy(SCORES)
x["dim_bulbs"]["enabled"] = False
expect_error("- control: with the dim policy OFF a dead lamp with a body material is refused (no glowing dead body)",
             lambda: L.validate_scores(x, L.resolve_looks(x, BASE), TOOL), "BODY_GLOWS_ON_DEAD_LAMP")
x = copy.deepcopy(SCORES)
x["passages"]["P04"]["segments"][2]["cycle"][0]["overrides"]["PRACTICAL_L"]["intensity"] = 0.0
px = L.validate_scores(x, LOOKS, TOOL)
f15 = L.bay_fixtures(TOOL, x, LOOKS, "P04", px["P04"]["specs"][14])
lamp = next(f for f in f15 if f["slot"] == "PRACTICAL_L")
check("+ a bay override that kills a lamp now turns it into a DIM bulb (18 lm orange) instead of a dark glowing body",
      lamp.get("dim_bulb") == "ORANGE" and lamp["intensity"] == 18.0
      and next(f for f in f15 if f["slot"] == "PRACTICAL_L_BODY")["body"]["mode"] == "DIM")
x = copy.deepcopy(SCORES)
x["variants"]["P04_GROUND_BULBS"]["instrument_overrides"]["PRACTICAL_L"]["visible_mesh"]["material"]["parent"] = "/Game/Foo/M_Bar"
expect_error("- control: an unknown parent material is refused", lambda: L.resolve_looks(x, BASE), "BAD_BODY_MATERIAL")
x = copy.deepcopy(SCORES)
x["variants"]["P04_GROUND_BULBS"]["instrument_overrides"]["PRACTICAL_L"]["visible_mesh"]["emissive"] = False
expect_error("- control: emissive flag disagreeing with the body mode is refused", lambda: L.resolve_looks(x, BASE),
             "BODY_EMISSIVE_FLAG_DISAGREES")


class FakeAssets:
    def __init__(self, existing=None):
        self.assets = copy.deepcopy(existing or {})
        self.calls = []

    def exists(self, path):
        return path in self.assets

    def read_mi(self, path):
        return dict(self.assets[path])

    def create_mi(self, path, parent, colour, intensity):
        self.calls.append(("create_mi", path))
        self.assets[path] = {"parent": parent, "colour": list(colour), "intensity": intensity}

    def read_mesh(self, path):
        return dict(self.assets[path])

    def create_mesh(self, path, source, material):
        self.calls.append(("create_mesh", path))
        self.assets[path] = {"source": source, "material": material}

    def save(self, path):
        self.calls.append(("save", path))
        return True

    def delete(self, path):
        self.calls.append(("delete", path))
        return self.assets.pop(path, None) is not None

    def list_meshes(self, folder):
        return [p for p in self.assets if p.startswith(folder + "/SM_PB_Bulb_")]


api = FakeAssets()
created = L.ensure_body_assets(api, assets)
check("+ ensure creates every planned MI + mesh once and saves them", sorted(created) == sorted(list(assets["mis"]) + list(assets["meshes"]))
      and sum(c[0] == "save" for c in api.calls) == len(created))
again = FakeAssets(api.assets)
check("+ a second run reuses identical assets (creates nothing)", L.ensure_body_assets(again, assets) == [] and not again.calls)
tampered = copy.deepcopy(api.assets)
first_mi = sorted(assets["mis"])[0]
tampered[first_mi]["intensity"] = 99.0
bad_api = FakeAssets(tampered)
expect_error("- control: an existing asset with different values stops the run (never edited)",
             lambda: L.ensure_body_assets(bad_api, assets), "BODY_ASSET_EXISTS_DIFFERENT|" + first_mi)
check("  ... and nothing was created or written on that stop", not bad_api.calls and bad_api.assets == tampered)
p04_only = L.body_asset_plan([f for t in p04_plan["targets"] for f in t["fixtures"]])
shared = FakeAssets()
created04 = L.ensure_body_assets(shared, p04_only)
created02 = L.ensure_body_assets(shared, L.body_asset_plan([f for t in p02_plan["targets"] for f in t["fixtures"]]))
foreign = "/Game/InfinityStage/Lighting/MI_LF_Flicker_Hum"
shared.assets[foreign] = {"parent": "x", "colour": [0, 0, 0], "intensity": 0}
still_used = sorted(p04_only["meshes"])[0]
result = L.revert_body_assets(shared, created04, referenced={still_used})
check("+ revert deletes only its own created, unreferenced assets; a referenced mesh and its MI stay",
      still_used in result["kept_referenced"] and p04_only["meshes"][still_used]["material"] in result["kept_referenced"]
      and still_used in shared.assets and foreign in shared.assets
      and all(p not in shared.assets for p in result["deleted"]) and len(result["deleted"]) == len(created04) - 2,
      "deleted=%d kept=%d" % (len(result["deleted"]), len(result["kept_referenced"])))
check("+ revert of P04 never touches P02's assets", all(p in shared.assets for p in created02))
expect_error("- control: a record naming an asset outside Bulbs/ is refused (no deleting foreign assets)",
             lambda: L.revert_body_assets(shared, [foreign], referenced=set()), "BODY_REVERT_UNKNOWN_ASSET")
x = copy.deepcopy(SCORES)
for name in ("P03_PYRE", "P03_PYRE_SIDES"):
    x["variants"][name]["instrument_overrides"]["TOP_R"]["cast_shadows"] = True
expect_error("- control: the shadow BUDGET still refuses: P03 with the 0 cd pyre TOP_R also casting exceeds 54",
             lambda: plan_for("P03", scores=x), "SHADOW_BUDGET_EXCEEDED|passage=P03|before=54|after=57")
casters = {k: (plan_for(k)["shadow"]["passage_before"], plan_for(k)["shadow"]["passage_after"]) for k in ("P02", "P03", "P04")}
check("+ shadow counts within budget (model census): P02 70->40, P03 54->49, P04 43->25 (6 Oct: +3 wing-wash casters, bays 8, 9, 12 tops/uplights)",
      casters == {"P02": (70, 40), "P03": (54, 49), "P04": (43, 25)}, str(casters))

print("\n== 17. round 2 (Gary note 59, 6 Oct): dim bulbs, caps, bulb behaviours, new light functions, P01/P04/P05/P06")
R2_TOOL = load_backup_tool(os.path.join(HERE, "lighting_scores_apply.py.bak-20261006-preRound2"), "_scores_pre_round2")
R2_SCORES = json.load(open(os.path.join(HERE, "lighting_scores.json.bak-20261006-preRound2"), encoding="utf-8"))
# The retired DEAD body mode (2 lamps, P04) is refused by the round-2 code, so the identity runs on the preRound2
# data with those two bodies as plain spheres (both tools get the same data).
for _name in ("P04_GROUND_BULB_ONE_DEAD", "P04_CEILING_STRIKE"):
    _body = R2_SCORES["variants"][_name]["instrument_overrides"]["PRACTICAL_R"]["visible_mesh"]
    assert _body["material"]["mode"] == "DEAD"
    _body.pop("material")
    _body["emissive"] = False
R2_P04 = R2_TOOL.load_p04_tool()
R2_LOOKS = R2_TOOL.resolve_looks(R2_SCORES, R2_TOOL.load_base_looks(R2_SCORES)[0])
ALL = ("P01", "P02", "P03", "P04", "P05", "P06")


new_on_old = {k: L._canonical(fixtures_of(L, TOOL, R2_SCORES, L.resolve_looks(R2_SCORES, BASE), k))
              == L._canonical(fixtures_of(R2_TOOL, R2_P04, R2_SCORES, R2_LOOKS, k)) for k in ALL}
same_plans = {}
for key in ALL:
    built_cues, built_passages, built_record = build_show(R2_SCORES)
    new = L.build_score_plan(TOOL, R2_SCORES, L.resolve_looks(R2_SCORES, BASE), key, built_passages, built_cues, built_record)
    old = R2_TOOL.build_score_plan(R2_P04, R2_SCORES, R2_LOOKS, key, built_passages, built_cues, built_record)
    new.pop("warnings")
    for t in new["targets"]:
        t.pop("cpp_pending")
    same_plans[key] = L._canonical(new) == L._canonical(old)
check("+ the round-2 code on the preRound2 data: every fixture AND whole plan byte-identical, all six passages (new passes are no-ops without their data)",
      all(new_on_old.values()) and all(same_plans.values()), "%s %s" % (new_on_old, same_plans))
x = copy.deepcopy(R2_SCORES)
x["dim_bulbs"] = copy.deepcopy(SCORES["dim_bulbs"])
check("- control: the same old data WITH the dim policy differs (the identity check can fail)",
      L._canonical(fixtures_of(L, TOOL, x, L.resolve_looks(x, BASE), "P01"))
      != L._canonical(fixtures_of(R2_TOOL, R2_P04, R2_SCORES, R2_LOOKS, "P01")))
OFF = copy.deepcopy(SCORES)
OFF["dim_bulbs"]["enabled"] = False
OFF["bulb_caps"]["enabled"] = False
del OFF["bulb_body_behaviours"]
for _variant in OFF["variants"].values():  # policy off: every DIM-coded 0-lm body goes back to a plain sphere
    for _row in list(_variant.get("instrument_overrides", {}).values()) + _variant.get("add_instruments", []):
        _body = _row.get("visible_mesh", {})
        if _body.get("material", {}).get("mode") == "DIM":
            _body.pop("material")
            _body["emissive"] = False
LOOKS_OFF = L.resolve_looks(OFF, BASE)
untouched = {k: L._canonical(fixtures_of(L, TOOL, OFF, LOOKS_OFF, k))
             == L._canonical(fixtures_of(R2_TOOL, R2_P04, R2_SCORES, R2_LOOKS, k)) for k in ("P02", "P03")}
check("+ P02/P03 score data untouched: with the bulb features off their fixtures equal preRound2 byte for byte",
      all(untouched.values()), str(untouched))


def _lights(bays):
    """Every lamp field except visible_mesh (the dim body's style text is new on 6 Oct)."""
    return [[{k: v for k, v in f.items() if k != "visible_mesh"} for f in bay if f.get("authored_kind") == "LIGHT"]
            for bay in bays]


p04_17 = L._canonical(_lights(fixtures_of(L, TOOL, OFF, LOOKS_OFF, "P04", lambda o: o == 17))) == L._canonical(
    _lights(fixtures_of(R2_TOOL, R2_P04, R2_SCORES, R2_LOOKS, "P04", lambda o: o == 17)))
p05_tail = L._canonical(fixtures_of(L, TOOL, OFF, LOOKS_OFF, "P05", lambda o: o >= 19)) == L._canonical(
    fixtures_of(R2_TOOL, R2_P04, R2_SCORES, R2_LOOKS, "P05", lambda o: o >= 19))
check("+ kept as Gary loves them: P04 bay-17 lamps and P05 bays 19-93 identical to preRound2 (bulb features off)",
      p04_17 and p05_tail, "p04_17=%s p05_19_93=%s" % (p04_17, p05_tail))

# -- dim bulbs everywhere
fx_all = {k: fixtures_of(L, TOOL, SCORES, LOOKS, k) for k in ALL}
pract = [(k, f) for k in ALL for bay in fx_all[k] for f in bay if f.get("authored_kind") == "LIGHT" and f["role"] == "PRACTICAL"]
dims = [(k, f) for k, f in pract if f.get("dim_bulb")]
pol = SCORES["dim_bulbs"]
check("+ no dead practical is left: every former 0-lumen practical glows (orange/white/pink), <= 40 lm, short reach",
      not [f for k, f in pract if float(f["intensity"]) <= 0.0] and dims
      and all(f["intensity"] == pol["lumens"] and f["attenuation_cm"] <= L.DIM_MAX_ATTENUATION_CM
              and f["dim_bulb"] in pol["tints"] and f["color_rgb_linear"] == pol["tints"][f["dim_bulb"]]["rgb"] for k, f in dims),
      "%d dim bulbs: %s" % (len(dims), {k: sum(1 for kk, f in dims if kk == k) for k in ALL}))
check("+ P01's dead bulbs are pale PINK (note 59); P04's are ORANGE (warm floor-bulb rule)",
      {f["dim_bulb"] for k, f in dims if k == "P01"} == {"PINK"} and {f["dim_bulb"] for k, f in dims if k == "P04"} == {"ORANGE"})
bodies_all = [(k, f) for k in ALL for bay in fx_all[k] for f in bay if f.get("role") == "PRACTICAL_BODY"]
sphere_dims = [(k, f) for k, f in dims if f["visible_mesh"]["mesh"] == L.BULB_MESH]
check("+ every dim bulb with a Sphere body has a DIM glass body (emissive MI, colour of its tint)",
      all(any(b["label"] == f["label"] + "_BODY" and b.get("body", {}).get("mode") == "DIM" for kk, b in bodies_all if kk == k)
          for k, f in sphere_dims), "%d sphere-bodied dim bulbs" % len(sphere_dims))
x = copy.deepcopy(SCORES)
x["variants"]["P01_WARM_EARLY"]["instrument_overrides"]["PRACTICAL_BULB_DEAD"]["dim_tint"] = "GREEN"
expect_error("- control: an unknown dim tint is refused", lambda: L.resolve_looks(x, BASE), "DIM_TINT_BAD")
x = copy.deepcopy(SCORES)
x["dim_bulbs"]["lumens"] = 120.0
expect_error("- control: a 'dim' bulb at 120 lm is refused (DIM means minimal glow)",
             lambda: L.validate_scores(x, L.resolve_looks(x, BASE), TOOL), "BODY_DIM_ON_BRIGHT_LAMP")

# -- caps
caps = [(k, f) for k in ALL for bay in fx_all[k] for f in bay if f.get("role") == "PRACTICAL_CAP"]
sphere_bodies = [(k, b) for k, b in bodies_all
                 if (b["body"]["source_mesh"] if b.get("body") else b["mesh"]) == L.BULB_MESH]


def cap_ok(body, cap):
    bz, sz = body["transform"]["location_cm"][2], body["transform"]["scale"][2]
    cz, ch = cap["transform"]["location_cm"][2], cap["transform"]["scale"][2] * 100.0
    return (abs((cz - ch / 2.0) - (bz + sz * 50.0 - 1.0)) < 1.0e-6 and cap["transform"]["location_cm"][:2] == body["transform"]["location_cm"][:2]
            and cap["mesh"].startswith(L.BODY_ASSET_DIR + "/SM_PB_Bulb_") and cap["body"]["mode"] == "CAP")


cap_by_label = {(k, c["label"]): c for k, c in caps}
check("+ every Sphere bulb body has exactly one dull screw cap sitting on its top; fixtures (SM_Lamp_*) get none",
      len(caps) == len(sphere_bodies) and all(cap_ok(b, cap_by_label[(k, b["label"][:-5] + "_CAP")]) for k, b in sphere_bodies),
      "%d caps" % len(caps))
bad_cap = copy.deepcopy(caps[0][1])
bad_cap["transform"]["location_cm"][2] += 30.0
check("- control: a cap floating 30 cm above its bulb fails the predicate",
      not cap_ok(next(b for k, b in sphere_bodies if b["label"][:-5] + "_CAP" == caps[0][1]["label"]), bad_cap))
check("- control: caps OFF -> no caps", not [f for bay in fixtures_of(L, TOOL, OFF, LOOKS_OFF, "P04") for f in bay
                                         if f.get("role") == "PRACTICAL_CAP"])

# -- bulb behaviours (data only)
modes = [b["body_behaviour"]["mode"] for k, b in bodies_all]
frac = {m: modes.count(m) / float(len(modes)) for m in L.BODY_BEHAVIOURS}
check("+ bulb behaviours: ~65%% STABLE, ~25%% SLIGHT, ~10%% FAIL over all %d bodies (deterministic hash split)" % len(modes),
      0.05 <= frac["FAIL"] <= 0.15 and 0.18 <= frac["SLIGHT"] <= 0.32, str({m: round(v, 3) for m, v in frac.items()}))
again = [b["body_behaviour"] for k in ALL for bay in fixtures_of(L, TOOL, SCORES, LOOKS, k) for b in bay if b.get("role") == "PRACTICAL_BODY"]
check("+ the split is stable across runs (no random stream: same modes and seeds on a second expansion)",
      again == [b["body_behaviour"] for k, b in bodies_all])
x = copy.deepcopy(SCORES)
x["variants"]["P04_GROUND_BULBS"]["instrument_overrides"]["PRACTICAL_L"]["body_mode"] = "FAIL"
fx = [f for bay in fixtures_of(L, TOOL, x, L.resolve_looks(x, BASE), "P04", lambda o: o == 15) for f in bay]
check("+ an explicit body_mode on the lamp wins over the split",
      next(f for f in fx if f["slot"] == "PRACTICAL_L_BODY")["body_behaviour"]["mode"] == "FAIL")
x["variants"]["P04_GROUND_BULBS"]["instrument_overrides"]["PRACTICAL_L"]["body_mode"] = "EXPLODE"
expect_error("- control: an unknown body_mode is refused", lambda: L.resolve_looks(x, BASE), "BODY_MODE_BAD")
import inspect as _inspect  # noqa: E402
_wired = [f for o in ALL for t in plan_for(o)["targets"] for f in t["fixtures"] if f.get("role") == "PRACTICAL_BODY"]
check("+ behaviours are WIRED (6 Oct C++ Body): every glass-bodied practical carries a body_write (follow its own lamp + "
      "its mode); glassless bodies are left default-off and say so",
      SCORES["bulb_body_behaviours"]["cpp_field"] == "Body"
      and all((f.get("body_write") is not None) == bool(f.get("body") and f["body"]["mode"] in ("MATCH_LIGHT", "DIM"))
              for f in _wired)
      and all(f["body_write"]["follow_light"] and f["body_write"]["flicker"] == f["body_behaviour"]["mode"]
              and f["body_write"]["light_attachment_guid"] == "PAIRED:" + f["paired_slot"] for f in _wired if f.get("body_write"))
      and all(f["body_behaviour"].get("unwired") == "NO_EMISSIVE_GLASS" for f in _wired if not f.get("body_write")),
      "wired=%d unwired=%d" % (sum(1 for f in _wired if f.get("body_write")), sum(1 for f in _wired if not f.get("body_write"))))
x = copy.deepcopy(SCORES)
x["bulb_body_behaviours"]["cpp_field"] = None
check("- control: cpp_field null -> no body_write anywhere (the old data-only path is intact)",
      not any(f.get("body_write") for t in plan_for("P04", scores=x)["targets"] for f in t["fixtures"]))

# -- new light functions (the parent graph in Python; INFERRED vs the binary: Sine Period default 1)
LFI = L.validate_flicker_instances(SCORES)


def lf_series(params, seconds=40.0, dt=0.005):
    return [(i * dt, L.lf_level(i * dt, params)) for i in range(int(seconds / dt))]


def bursts(params, seconds=40.0):
    series, flashes, start = lf_series(params, seconds), [], None
    for t, v in series:
        if v > 0.5 and start is None:
            start = t
        elif v <= 0.5 and start is not None:
            flashes.append((start, t))
            start = None
    groups = []
    for a, b in flashes:
        if groups and a - groups[-1][1] < 0.7:
            groups[-1][1], groups[-1][2] = b, groups[-1][2] + 1
        else:
            groups.append([a, b, 1])
    return groups


def dips_per_second(params, seconds=30.0):
    series = lf_series(params, seconds)
    mins = sum(1 for (unused, a), (unused2, b), (unused3, c) in zip(series, series[1:], series[2:]) if b < a and b <= c and b < 0.97)
    return mins / seconds, min(v for unused, v in series), max(v for unused, v in series)


rate, low, high = dips_per_second(LFI[L.FLICKER_ROOT + "Pulse1Hz_A"]["params"])
check("+ Pulse1Hz: gentle irregular ~1 Hz pulse (0.6-1.6 dips/s, never below 60%)", 0.6 <= rate <= 1.6 and low >= 0.6 and high > 0.99,
      "dips/s=%.2f min=%.2f" % (rate, low))
groups = {n: bursts(LFI[L.FLICKER_ROOT + "Burst2Hz_" + n]["params"]) for n in "ABC"}
def burst_ok(gs):
    return len(gs) >= 5 and all(g[2] == 2 and g[1] - g[0] <= 0.7 for g in gs[1:-1])


shape = all(burst_ok(groups[n]) for n in "ABC")
period = all(abs((groups[n][i + 1][0] - groups[n][i][0]) - 4.0) < 0.05 for n in "ABC" for i in range(1, len(groups[n]) - 2))
starts = sorted(groups[n][2][0] % 4.0 for n in "ABC")
check("+ Burst2Hz A/B/C: 2 flashes at 2 Hz inside <= 0.7 s, every 4 s, the three phases >= 0.5 s apart",
      shape and period and min(b - a for a, b in zip(starts, starts[1:] + [starts[0] + 4.0])) >= 0.5,
      "starts=%s" % [round(v, 2) for v in starts])
soft = dict(LFI[L.FLICKER_ROOT + "Burst2Hz_A"]["params"], Hardness=0.0, OnBias=0.5)
check("- control: the same burst with Hardness 0 / OnBias 0.5 is NOT a 2-flash burst (the predicate can fail)",
      not burst_ok(bursts(soft)), "groups=%d" % len(bursts(soft)))
rate, low, high = dips_per_second(LFI[L.FLICKER_ROOT + "HarpFlutter"]["params"])
check("+ HarpFlutter: shallow harp-rate flutter (5-10 dips/s, never below 84%)", 5.0 <= rate <= 10.0 and low >= 0.84, "dips/s=%.1f min=%.2f" % (rate, low))
x = copy.deepcopy(SCORES)
x["flicker_instances"]["/Game/Other/MI_X"] = x["flicker_instances"].pop(L.FLICKER_ROOT + "HarpFlutter")
expect_error("- control: a flicker instance outside MI_LF_Flicker_ is refused", lambda: L.validate_flicker_instances(x),
             "BAD_FLICKER_INSTANCE")
used = {f["flicker"]["material"] for k in ALL for bay in fx_all[k] for f in bay if f.get("authored_kind") == "LIGHT"} - {None}
check("+ every new MI the scores use is declared (create-only); every declared MI is used",
      {p for p in used if p.split("_Flicker_")[1] not in ("Steady", "Slow", "Breath", "Hum", "Buzz", "Fault")}
      == set(LFI), str(sorted(set(LFI))))


class FakeLF:
    def __init__(self, assets=None):
        self.assets, self.calls = copy.deepcopy(assets or {}), []

    def exists(self, path):
        return path in self.assets

    def read_lf(self, path):
        return copy.deepcopy(self.assets[path])

    def create_lf(self, path, parent, params):
        self.calls.append(("create", path))
        self.assets[path] = {"parent": parent, "params": dict(params)}

    def save(self, path):
        self.calls.append(("save", path))
        return True


api = FakeLF()
check("+ flicker MIs: created once and saved, a second run reuses them", sorted(L.ensure_flicker_instances(api, LFI)) == sorted(LFI)
      and L.ensure_flicker_instances(FakeLF(api.assets), LFI) == [])
tampered = copy.deepcopy(api.assets)
tampered[L.FLICKER_ROOT + "Pulse1Hz_A"]["params"]["Speed"] = 3.0
expect_error("- control: an existing MI with other parameters stops the run (never edited)",
             lambda: L.ensure_flicker_instances(FakeLF(tampered), LFI), "FLICKER_INSTANCE_EXISTS_DIFFERENT")

# -- per-lamp keying, P01
p01p = {t["ordinal"]: t for t in plan_for("P01")["targets"]}
beam = {o: next((f for f in p01p[o]["fixtures"] if f.get("role") == "BEAM"), None) for o in range(13, 41)}
lit_beams = {o: f for o, f in beam.items() if f is not None}
check("+ P01 ground beams: bay 20 = the original orange BEAM_R; 18/21/22 burst (A/B/C) and strike at 5400/1500/4200 cm while the rest of their bay keeps 650",
      [round(lit_beams[o]["distance_keying"]["strike_distance_cm"]) for o in (18, 20, 21, 22)] == [5400, 650, 1500, 4200]
      and [lit_beams[o]["flicker"]["material"].rsplit("_", 1)[-1] if lit_beams[o]["flicker"]["material"] else None
           for o in (18, 20, 21, 22)] == ["A", None, "B", "C"]
      and all(f["distance_keying"]["strike_distance_cm"] == 650.0 for o in (18, 21, 22) for f in p01p[o]["fixtures"]
              if f.get("authored_kind") == "LIGHT" and f.get("role") != "BEAM")
      and len({tuple(lit_beams[o]["color_rgb_linear"]) for o in (18, 20, 21, 22)}) == 4)
old20 = next(f for f in fixtures_of(R2_TOOL, R2_P04, R2_SCORES, R2_LOOKS, "P01", lambda o: o == 20)[0] if f["slot"] == "BEAM_R")
new20 = dict(lit_beams[20])
check("+ bay 20's BEAM_R is the 5 Oct lamp (colour, intensity, aim, flicker, keying) apart from its new label look name",
      all(new20[k] == old20[k] for k in ("color_rgb_linear", "intensity", "transform", "flicker", "distance_keying", "volumetric_scattering")))
x = copy.deepcopy(SCORES)
x["passages"]["P01"]["segments"][3]["cycle"][5]["overrides"]["BEAM_R"]["keying"]["strike_cm"] = 10.0
expect_error("- control: a misspelt per-lamp keying key is refused", lambda: L.validate_scores(x, LOOKS, TOOL), "BAD_DRAMA_FIELDS")
tops = {o: [f for f in p01p[o]["fixtures"] if f.get("role") == "TOP"] for o in range(1, 49)}
check("+ P01 tops: dark in 3-5, ping on from bay 6 with the 1 Hz pulse in red/green/cream/pink (>= 4 colours)",
      all(f["intensity"] == 0.0 for o in (3, 4, 5) for f in tops[o])
      and all(f["intensity"] > 0 and "Pulse1Hz" in f["flicker"]["material"] for o in range(6, 49) for f in tops[o])
      and len({tuple(f["color_rgb_linear"]) for o in range(6, 49) for f in tops[o]}) >= 4)
low = {o: sum(f["intensity"] for f in p01p[o]["fixtures"] if f.get("role") == "LOW_SIDE") / p01p[o]["level_scale"]
       for o in range(3, 49) if any(f.get("role") == "LOW_SIDE" for f in p01p[o]["fixtures"])}
topsum = {o: sum(f["intensity"] for f in tops[o]) / p01p[o]["level_scale"] for o in low}
check("+ P01 low sides darken after bay 12 (<= 40% of the early level) and the tops then out-shine them",
      max(low[o] for o in low if o > 12) <= 0.4 * min(low[o] for o in low if o <= 12)
      and all(topsum[o] >= low[o] for o in low if o > 12), "early min %.0f, late max %.0f" % (
          min(low[o] for o in low if o <= 12), max(low[o] for o in low if o > 12)))
clamps = [f for t in p01p.values() for f in t["fixtures"] if f.get("slot") == "PRACTICAL_CLAMP"]
check("+ P01 clamp lamps are pale pink and lit", clamps and all(f["color_rgb_linear"] == [1.0, 0.72, 0.8] and f["intensity"] > 0 for f in clamps))

# -- P04
p04p = {t["ordinal"]: t for t in plan_for("P04")["targets"]}
lit_pr = {o: [f for f in p04p[o]["fixtures"] if f.get("role") == "PRACTICAL" and f["intensity"] > 0 and not f.get("dim_bulb")]
          for o in range(7, 22)}
check("+ P04 7-21: active (non-dim) practicals in every bay but the VOID (14); hanging bulbs in the bulb bays",
      all(lit_pr[o] for o in range(7, 22) if o != 14) and not lit_pr[14]
      and all(any(f["transform"]["location_cm"][2] > 150 for f in p04p[o]["fixtures"] if f.get("role") == "PRACTICAL")
              for o in (7, 8, 9, 10, 13, 15, 16, 18, 19, 20, 21)),
      " ".join("B%d:%d" % (o, len(v)) for o, v in sorted(lit_pr.items())))
wing = [(o, f) for o in (8, 9, 12) for f in p04p[o]["fixtures"] if f.get("authored_kind") == "LIGHT"
        and f["role"] in ("TOP", "LOW_SIDE")]
check("+ P04 8/9/12: tops and the uplight wash their own wing (aim_wing_side, volumetric <= 0.1)",
      wing and all(f.get("aim_wing_side") and f["volumetric_scattering"] <= 0.1 for o, f in wing), "%d lamps" % len(wing))

# -- P05
p05_plan = plan_for("P05")
p05p = {t["ordinal"]: t for t in p05_plan["targets"]}


def roles(o):
    return sorted(f["role"] for f in p05p[o]["fixtures"] if f.get("authored_kind") == "LIGHT")


fills = [[f["distance_keying"]["strike_distance_cm"] for f in p05p[o]["fixtures"] if f.get("role") == "FILL"] for o in range(1, 7)]
check("+ P05 1-6: upper spots + fills + up-spots; the fills come on in sequence (each bay's strikes further ahead, L before R)",
      all({"FILL", "UPLIGHT", "TOP", "LOW_SIDE", "BEAM"} <= set(roles(o)) for o in range(1, 7))
      and all(a[0] < b[0] and a[1] < b[1] for a, b in zip(fills, fills[1:])) and all(l > r for l, r in fills), str(fills))
check("+ P05 7-12: sky cut (no FILL/BEAM/LOW_SIDE), tops + up-spots blink (FAULT), snuffed just behind Puss (EXTINGUISH)",
      all(not {"FILL", "BEAM", "LOW_SIDE"} & set(roles(o)) for o in range(7, 13))
      and all(f["flicker"]["mode"] == "FAULT" and f["distance_keying"]["after_pass"] == "EXTINGUISH"
              for o in range(7, 13) for f in p05p[o]["fixtures"] if f.get("role") in ("TOP", "UPLIGHT")))
check("+ P05 13-18: everything on; the 12 club movers are AUTHORED with their Mover settings (C++ 6 Oct), no warnings",
      all({"FILL", "UPLIGHT", "TOP", "LOW_SIDE", "BEAM"} <= set(roles(o)) for o in range(13, 19))
      and sorted(o for o in p05p for r in roles(o) if r == "MOVER") == sorted(list(range(13, 19)) * 2)
      and all(f["mover_write"]["enabled"] for o in range(13, 19) for f in p05p[o]["fixtures"] if f.get("role") == "MOVER")
      and p05_plan["warnings"] == [])
x = copy.deepcopy(SCORES)
for row in x["variants"]["P05_ALL_ON"]["add_instruments"]:
    if row.get("role") == "MOVER":
        row.pop("mover")
        row["requires_cpp"] = "gate test"
_skip = plan_for("P05", scores=x)
check("- control: the same movers behind a requires_cpp gate are SKIPPED with 12 warnings (the gate still works)",
      len(_skip["warnings"]) == 12 and all(w.startswith("SKIPPED_PENDING_CPP|passage=P05") for w in _skip["warnings"])
      and not any(f.get("role") == "MOVER" for t in _skip["targets"] for f in t["fixtures"]))
x = copy.deepcopy(SCORES)
for row in x["variants"]["P05_ALL_ON"]["add_instruments"]:
    row.pop("mover", None)
expect_error("- control: a MOVER with neither Mover settings nor a requires_cpp gate is refused",
             lambda: L.resolve_looks(x, BASE), "MOVER_WITHOUT_CPP_GATE")
own = [(o, f) for o in range(1, 19) for f in p05p[o]["fixtures"] if f.get("role") in ("FILL", "UPLIGHT", "TOP")]
check("+ P05 new spots stay on their own side (FILL aimed outward at the fence line, TOP/UPLIGHT own wing)",
      all(L.no_cross_rows("P05", o, [f], dict(L.NO_CROSS_DEFAULTS)) for o, f in own if f["type"] == "SPOT"), "%d spots" % len(own))
x = copy.deepcopy(SCORES)
x["variants"]["P05_SKY_APPROACH"]["add_instruments"][0]["aim_target_pair_cm"] = [0.0, 2100.0, 450.0]
expect_error("- control: a sky fill aimed at the OTHER fence fails the cross rule",
             lambda: [L.no_cross_rows("P05", 1, [f], dict(L.NO_CROSS_DEFAULTS)) for f in L.bay_fixtures(
                 TOOL, x, L.resolve_looks(x, BASE), "P05", L.validate_scores(x, L.resolve_looks(x, BASE), TOOL)["P05"]["specs"][0])
                 if f.get("role") == "FILL"], "NO_CROSS_SHOT|passage=P05|bay=1|slot=FILL_L")
x = copy.deepcopy(SCORES)
x["variants"]["P05_ALL_ON"]["add_instruments"][-1]["drama"] = {"slow_move": True, "pan_amplitude_degrees": 60.0}
expect_error("- control: slow-move amplitude above the C++ clamp (45 deg) is refused", lambda: L.resolve_looks(x, BASE),
             "LAMP_DRAMA_RANGE")

# -- P06
model = SCORES["passages"]["P06"]["beat_map"]
p06_plan = plan_for("P06")
p06p = {t["ordinal"]: t for t in p06_plan["targets"]}
blue = all(f["color_rgb_linear"][2] > f["color_rgb_linear"][0] for o in [1] + list(range(11, 22)) if o in p06p
           for f in p06p[o]["fixtures"] if f.get("role") == "LOW_SIDE")
check("+ P06 first third: the sideways wash (low sides) is cool blue, not orange (bays 1, 11-21)", blue)
embers = {o: [f for f in p06p[o]["fixtures"] if f.get("role") == "PRACTICAL"] for o in range(22, 43)}
check("+ P06 middle: four ember bulbs per bay (2 hanging, 2 on the floor), deep orange, <= 40 lm, short reach; tops blink",
      all(len(v) == 4 and sum(f["transform"]["location_cm"][2] > 100 for f in v) == 2
          and all(f["temperature_kelvin"] <= 1800 and f["intensity"] <= 40 and f["attenuation_cm"] <= 200 for f in v)
          for v in embers.values())
      and all(f["flicker"]["mode"] in ("FAULT", "HARPFLUTTER") for o in range(22, 43) for f in p06p[o]["fixtures"]
              if f.get("slot") == "TOP_L"))
T, D = 110.561125, 27640.28
v6, pitch = D / T, D / 64
uniform = {k: {"t_s": (k - 1) * pitch / v6, "d_cm": (k - 1) * pitch} for k in range(1, 65)}
bc = L.beat_check(model["beats"], uniform)
check("+ P06 beats (major changes 36.22 / 48.85 / 61.90 / 68.55 s) each strike a cold top ON the beat (uniform-speed model)",
      [b["beat_s"] for b in model["beats"]] == [36.22, 48.85, 61.9, 68.55] and all(b["verdict"] == "ON_BEAT" for b in bc)
      and all(next(f for f in p06p[b["bay"]]["fixtures"] if f.get("slot") == "TOP_R")["distance_keying"]["strike_distance_cm"]
              == b["strike_distance_cm"] for b in model["beats"]),
      " ".join("B%d@%.2fs(%+.2f)" % (b["bay"], b["beat_s"], b["drift_s"]) for b in bc))
shifted = [dict(b, strike_distance_cm=b["strike_distance_cm"] + 300.0) for b in model["beats"]]
check("- control: the same beats with strikes 300 cm early are OFF_BEAT (the check can fail)",
      all(b["verdict"] == "OFF_BEAT_RETUNE" for b in L.beat_check(shifted, uniform)))
harp = [o for o in range(22, 43) if any(f["flicker"]["mode"] == "HARPFLUTTER" for f in p06p[o]["fixtures"] if f.get("slot") == "TOP_L")]
check("+ P06 harp lilting parts (rhythmicDensity > 0.5: 61-64, 68-71, 74-76, 80-83 s) flutter in their bays",
      harp == model["harp_bays"] and harp, str(harp))
check("+ P06 middle third passes the no-cross rule; last third (43-64) keeps the failing gold for tomorrow's fires",
      all(r["verdict"].startswith("OK") for r in L.validate_scores(SCORES, LOOKS, TOOL)["P06"]["no_cross"]["rows"])
      and all(p06p[o]["look"] == "P06_FAILING_GOLD" for o in range(43, 64)))

# -- budgets with everything on
budget = {k: plan_for(k)["shadow"] for k in ALL}
check("+ every passage within its shadow budget after round 2 (after <= before)",
      all(b["budget_ok"] for b in budget.values()),
      " ".join("%s %d->%d" % (k, b["passage_before"], b["passage_after"]) for k, b in sorted(budget.items())))

# ============================================================================ 6 Oct: C++ wiring + drift decisions
print("\n== 20. C++ Mover/Body wiring (FInfinityCueAttachment::Mover / ::Body, built 6 Oct)")
import re as _re  # noqa: E402

PUBLIC = os.path.join(os.path.dirname(os.path.dirname(HERE)), "Plugins", "InfinityStage", "Source", "InfinityStage", "Public")


def header_fields(path, struct):
    """(python_name, default) per UPROPERTY of ``struct`` in a header, by UE's naming rule (bool b-prefix dropped,
    CamelCase -> snake_case). The declaration is the source of truth the tool's tables must match."""
    text = open(path, encoding="utf-8").read()
    body = text[text.index("struct INFINITYSTAGE_API " + struct):]
    body = body[: body.index("};")]
    out = []
    for ctype, name, default in _re.findall(r"UPROPERTY\([^;]*?\)\s*(\w+)\s+(\w+)(?:\s*=\s*([^;]+))?;", body, _re.S):
        if ctype == "bool" and name.startswith("b") and name[1:2].isupper():
            name = name[1:]
        snake = _re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).lower()
        if not default:
            value = "0" * 32 if ctype == "FGuid" else None
        else:
            d = default.strip()
            if d in ("true", "false"):
                value = d == "true"
            elif "::" in d:
                value = _re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", d.split("::")[-1]).upper()
            elif d.startswith("TEXT("):
                value = d[len('TEXT("'):-2]
            elif ctype == "int32":
                value = int(d)
            else:
                value = float(d.rstrip("f"))
        out.append((snake, value))
    return out


mover_h = header_fields(os.path.join(PUBLIC, "InfinityStageLightMover.h"), "FInfinityLightMoverSettings")
body_h = header_fields(os.path.join(PUBLIC, "InfinityStageBulbBody.h"), "FInfinityBulbBodySettings")
check("+ MOVER_DEFAULTS == the header's UPROPERTYs (names by UE's rule, order, defaults) [declaration-proven]",
      tuple(mover_h) == L.MOVER_DEFAULTS, str(mover_h))
check("+ BODY_DEFAULTS == the header's UPROPERTYs (names by UE's rule, order, defaults) [declaration-proven]",
      tuple(body_h) == L.BODY_DEFAULTS, str(body_h))
_tmp_h = tempfile.mkdtemp(prefix="hdr_")
open(os.path.join(_tmp_h, "m.h"), "w", encoding="utf-8").write(open(os.path.join(
    PUBLIC, "InfinityStageLightMover.h"), encoding="utf-8").read().replace("StepsPerSecond = 3.0f;", "StepsPerSecond = 4.0f;"))
check("- control: the same parse of a header with one changed default disagrees (the comparison can fail)",
      tuple(header_fields(os.path.join(_tmp_h, "m.h"), "FInfinityLightMoverSettings")) != L.MOVER_DEFAULTS)
shutil.rmtree(_tmp_h, ignore_errors=True)
types_h = open(os.path.join(PUBLIC, "InfinityStageTypes.h"), encoding="utf-8").read().splitlines()
check("+ the attachment carries both structs where the tool cites them (InfinityStageTypes.h:484 Body, :491 Mover)",
      types_h[483].strip() == "FInfinityBulbBodySettings Body;" and types_h[490].strip() == "FInfinityLightMoverSettings Mover;",
      "%r %r" % (types_h[483].strip(), types_h[490].strip()))

p05_movers = [f for t in plan_for("P05")["targets"] for f in t["fixtures"] if f.get("role") == "MOVER"]
m0 = p05_movers[0]["mover_write"]
check("+ P05 movers carry Gary's brief: ground aim first (ON_APPROACH 500 cm, inside the 650 cm strike; calm 0), then "
      "+-40/+-25 deg jolts at 4 steps/s, ease 0.2; own seeds L/R",
      len(p05_movers) == 12 and m0["trigger"] == "ON_APPROACH" and m0["calm_scale"] == 0.0
      and m0["approach_distance_cm"] < p05_movers[0]["distance_keying"]["strike_distance_cm"]
      and m0["steps_per_second"] == 4.0 and m0["ease_fraction"] == 0.2 and m0["enabled"]
      and {f["mover_write"]["seed"] for f in p05_movers} == {1, 2}
      and all(f["aim_target_pair_cm"][2] == 0.0 for f in p05_movers), str(m0))
for name, edit, needle in (
        ("pitch above the 89 deg clamp", {"pitch_amplitude_degrees": 95.0}, "MOVER_RANGE"),
        ("ease below the 0.01 clamp", {"ease_fraction": 0.0}, "MOVER_RANGE"),
        ("an unknown field", {"spin": 1.0}, "MOVER_FIELDS_BAD"),
        ("an unknown trigger", {"trigger": "SOMETIMES"}, "MOVER_FIELDS_BAD"),
        ("a 64-bit seed", {"seed": 2 ** 40}, "MOVER_FIELDS_BAD"),
        ("enabled false", {"enabled": False}, "MOVER_NOT_ENABLED")):
    x = copy.deepcopy(SCORES)
    x["variants"]["P05_ALL_ON"]["add_instruments"][4]["mover"].update(edit)
    expect_error("- control: a mover with %s is refused" % name, lambda: L.resolve_looks(x, BASE), needle)
x = copy.deepcopy(SCORES)
x["variants"]["P05_ALL_ON"]["add_instruments"][4]["requires_cpp"] = "both"
expect_error("- control: Mover settings AND a requires_cpp gate together are refused", lambda: L.resolve_looks(x, BASE),
             "MOVER_HOST_BAD")
x = copy.deepcopy(SCORES)
x["variants"]["P05_ALL_ON"]["add_instruments"][0]["mover"] = {"enabled": True}
expect_error("- control: Mover settings on a non-MOVER lamp are refused", lambda: L.resolve_looks(x, BASE), "MOVER_HOST_BAD")

pol = L.body_policy(SCORES)
check("+ body policy: STABLE steady glass; SLIGHT glass-only shimmer; FAIL dies at the lamp and drives the lamp",
      pol["STABLE"]["flicker"] == "STABLE" and not pol["SLIGHT"]["flicker_also_drives_light"]
      and pol["FAIL"]["flicker_also_drives_light"] and pol["FAIL"]["fail_at_cm"] == 0.0
      and all(p["full_intensity"] == -1.0 and p["intensity_parameter"] == "Intensity" for p in pol.values()))
for name, mutate, needle in (
        ("a missing mode", lambda b: b["modes"].pop("SLIGHT"), "BODY_MODES_BAD"),
        ("a mode whose flicker disagrees", lambda b: b["modes"]["FAIL"].update(flicker="SLIGHT"), "BODY_MODE_BAD"),
        ("a slight depth above 1", lambda b: b["modes"]["SLIGHT"].update(slight_depth=1.5), "BODY_RANGE"),
        ("an unknown cpp_field", lambda b: b.update(cpp_field="Glass"), "BODY_CPP_FIELD_UNKNOWN")):
    x = copy.deepcopy(SCORES)
    mutate(x["bulb_body_behaviours"])
    expect_error("- control: body policy with %s is refused" % name, lambda: L.body_policy(x), needle)


# ---- fake UE objects (value semantics like UE Python struct wrappers: getters return copies)
class EnumV:
    def __init__(self, enum, name, value=0):
        self.enum, self.name, self.value = enum, name, value

    def __eq__(self, other):
        return isinstance(other, EnumV) and (self.enum, self.name) == (other.enum, other.name)

    def __hash__(self):
        return hash((self.enum, self.name))

    def __str__(self):
        return "<%s.%s: %d>" % (self.enum, self.name, self.value)


class V:
    def __init__(self, *xyz):
        self.x, self.y, self.z = [float(v) for v in xyz]


class Q:
    def __init__(self, x, y, z, w):
        self.x, self.y, self.z, self.w = float(x), float(y), float(z), float(w)


class C:
    def __init__(self, r, g, b, a):
        self.r, self.g, self.b, self.a = r, g, b, a


class V2:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)


def struct_value(value):
    """A row list back to the UE struct _plain_struct_value reads: 2 -> Vector2D, 3 -> Vector, 4 -> LinearColor."""
    if isinstance(value, list) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
        return {2: lambda: V2(*value), 3: lambda: V(*value), 4: lambda: C(*value)}.get(len(value), lambda: value)()
    return value


class FT:
    def __init__(self, location, rotation, scale):
        self.translation, self.rotation, self.scale3d = V(*location), Q(*rotation), V(*scale)


class FS:
    """A struct: get returns a copy; set of an unknown name raises (as UE does)."""
    ignore = ()

    def __init__(self, **props):
        self.__dict__["_p"] = props

    def get_editor_property(self, name):
        if name not in self._p:
            raise AttributeError("no property " + name)
        return copy.deepcopy(self._p[name])

    def set_editor_property(self, name, value):
        if name not in self._p:
            raise AttributeError("no property " + name)
        if name in self.ignore:
            return True  # a setter that LIES: reports success, changes nothing
        self._p[name] = copy.deepcopy(value)
        return True

    def modify(self):
        return True


class LyingFS(FS):
    ignore = ("steps_per_second", "light_attachment_guid", "enabled")


class LyingMoverFS(FS):
    ignore = ("steps_per_second",)


KIND = {"LIGHT": EnumV("InfinityAttachmentKind", "LIGHT", 1), "PROP": EnumV("InfinityAttachmentKind", "PROP", 0)}
ENUMS = {"trigger": lambda n: EnumV("InfinityLightMoverTrigger", n), "flicker": lambda n: EnumV("InfinityBulbBodyFlicker", n),
         "name": lambda s: str(s), "zero_guid": lambda: "0" * 32}


def fake_mover(cls=FS, **over):
    p = {k: (EnumV("InfinityLightMoverTrigger", v) if k == "trigger" else v) for k, v in L.MOVER_DEFAULTS}
    p.update(over)
    return cls(**p)


def fake_body(cls=FS, **over):
    p = {k: (EnumV("InfinityBulbBodyFlicker", v) if k == "flicker" else v) for k, v in L.BODY_DEFAULTS}
    p.update(over)
    return cls(**p)


def fake_from_row(row, cls=FS, mover=None, body=None):
    """A fake attachment whose attachment_state is exactly ``row`` (+ Mover/Body structs)."""
    kind_name = str(row["kind"]).split(".")[-1].split(":")[0]
    lighting = {k: struct_value(v) for k, v in row["lighting"].items() if k != "drama"}
    lighting["drama"] = FS(**{k: struct_value(v) for k, v in row["lighting"]["drama"].items()})
    t = row["relative_transform"]
    return cls(attachment_guid=row["guid"], label=row["label"],
               kind=KIND.get(kind_name, EnumV("InfinityAttachmentKind", kind_name, 2)),
               enabled=row["enabled"], actor_class=row["actor_class"], mesh=row["mesh"], anchor=row["anchor"],
               relative_transform=FT(t["location"], t["rotation_xyzw"], t["scale"]),
               lighting=FS(**lighting), effect=FS(**{k: struct_value(v) for k, v in row["effect"].items()}),
               trigger_distance_cm=row["trigger_distance_cm"],
               mover=mover or fake_mover(), body=body or fake_body())


def fake_cue(guid_text, label, rows, cls=FS):
    return FS(cue_guid=guid_text, label=label, type="WING_PAIR",
              wing_pair=FS(attachments=[fake_from_row(r, cls) for r in rows],
                           occurrence_offset=FT([0, 0, 0], [0, 0, 0, 1], [1, 1, 1])))


REC = {k: json.load(open(L._record_path(k), encoding="utf-8")) for k in ("P01", "P02", "P04", "P06")}
sample = REC["P02"]["plan"]["targets"][0]["after_rows"][0]
_saved_tool_unreal = TOOL.unreal
TOOL.unreal = types.SimpleNamespace(InfinityAttachmentKind=types.SimpleNamespace(**KIND))
try:
    check("+ fake attachments are lossless: attachment_state(fake(row)) == row on a real record row",
          TOOL._attachment_rows([fake_from_row(sample)]) == [sample])
    p05t = next(t for t in plan_for("P05")["targets"] if t["ordinal"] == 13)
    p04t = next(t for t in plan_for("P04")["targets"] if any(f.get("body_write") for f in t["fixtures"]))

    def vessels(target, cls=FS, poison=False):
        out = []
        for f in target["fixtures"]:
            row = copy.deepcopy(sample)
            row.update(guid=guid("vessel", target["ordinal"], f["slot"]), label=f["label"])
            mover = fake_mover(cls, enabled=True, steps_per_second=9.0) if poison else fake_mover(cls)
            body = (fake_body(cls, follow_light=True, flicker=EnumV("InfinityBulbBodyFlicker", "FAIL")) if poison
                    else fake_body(cls))
            out.append(fake_from_row(row, cls, mover, body))
        return out

    def planned_ok(target, atts):
        by_slot = {f["slot"]: a for f, a in zip(target["fixtures"], atts)}
        return all(not L.extension_mismatches(L.planned_extensions(f, TOOL._guid_text(
            by_slot[f["paired_slot"]].get_editor_property("attachment_guid")) if f.get("body_write") else L.ZERO_GUID),
            L.read_extensions(TOOL, a)) for f, a in zip(target["fixtures"], atts))

    for name, target in (("P05 bay 13 (2 movers)", p05t), ("P04 bay %d (glass bodies)" % p04t["ordinal"], p04t)):
        atts = vessels(target)
        got = L.apply_extensions(TOOL, target["fixtures"], atts, ENUMS)
        lamp_guid = {f["slot"]: TOOL._guid_text(a.get_editor_property("attachment_guid"))
                     for f, a in zip(target["fixtures"], atts)}
        bodies = [(f, got[f["label"]]) for f in target["fixtures"] if f.get("body_write")]
        check("+ %s: every vessel written + read back; movers on, glass follows ITS OWN lamp's GUID, rest default-off" % name,
              all(got[f["label"]]["mover"]["enabled"] == bool(f.get("mover_write")) for f in target["fixtures"])
              and all(g["body"]["follow_light"] and g["body"]["light_attachment_guid"] == lamp_guid[f["paired_slot"]]
                      and g["body"]["flicker"] == f["body_behaviour"]["mode"] for f, g in bodies)
              and all(got[f["label"]]["body"] == dict(L.BODY_DEFAULTS) for f in target["fixtures"] if not f.get("body_write"))
              and planned_ok(target, atts),
              "movers=%d bodies=%d" % (sum(1 for f in target["fixtures"] if f.get("mover_write")), len(bodies)))
    poisoned = vessels(p04t, poison=True)
    plain_lamp = next(i for i, f in enumerate(p04t["fixtures"]) if not f.get("mover_write") and not f.get("body_write"))
    check("- control: a vessel replicated from a scratch light that carried a Mover/Body is NOT default-off before the "
          "write (the inheritance hazard is real)",
          L.read_extensions(TOOL, poisoned[plain_lamp])["mover"] != dict(L.MOVER_DEFAULTS))
    L.apply_extensions(TOOL, p04t["fixtures"], poisoned, ENUMS)
    check("+ ... and after apply_extensions every poisoned vessel holds exactly its planned values (defaults written in full)",
          planned_ok(p04t, poisoned))
    expect_error("- control: a mover setter that lies (steps_per_second ignored) refuses EXTENSION_READBACK",
                 lambda: L.apply_extensions(TOOL, p05t["fixtures"], vessels(p05t, LyingMoverFS), ENUMS),
                 "EXTENSION_READBACK|P05 SCORE B13 P05_ALL_ON MOVER_L|mover.steps_per_second want=4.0 got=3.0")
    bi = next(i for i, f in enumerate(p04t["fixtures"]) if f.get("body_write"))
    lying_body = vessels(p04t)
    lying_body[bi] = fake_from_row(TOOL._attachment_rows([lying_body[bi]])[0], FS, fake_mover(), fake_body(LyingFS))
    expect_error("- control: a body setter that lies (light_attachment_guid ignored) refuses EXTENSION_READBACK",
                 lambda: L.apply_extensions(TOOL, p04t["fixtures"], lying_body, ENUMS), "body.light_attachment_guid")
    lone = p04t["fixtures"][bi]["paired_slot"]
    expect_error("- control: a body whose paired lamp is not in the bay refuses BODY_PAIRED_LIGHT_MISSING",
                 lambda: L.apply_extensions(TOOL, [f for f in p04t["fixtures"] if f["slot"] != lone],
                                            [a for f, a in zip(p04t["fixtures"], vessels(p04t)) if f["slot"] != lone],
                                            ENUMS), "BODY_PAIRED_LIGHT_MISSING")

    t = copy.deepcopy(p04t)
    pre = [fake_from_row(r) for r in REC["P04"]["plan"]["targets"][0]["before_rows"][:3]]
    authored = vessels(t)
    L.apply_extensions(TOOL, t["fixtures"], authored, ENUMS)
    t["before_extensions"] = L.extension_rows(TOOL, pre)
    L.verify_target_extensions(TOOL, t, pre + authored)
    check("+ saved-readback check passes on the authored cue (planned values, own-lamp GUIDs, pre-existing untouched)", True)
    swapped = copy.deepcopy(pre + authored)
    body_lamp = t["fixtures"][bi]["paired_slot"]
    i0 = len(pre) + next(i for i, f in enumerate(t["fixtures"]) if f["slot"] == body_lamp)
    i1 = len(pre) + next(i for i, f in enumerate(t["fixtures"]) if f["authored_kind"] == "LIGHT" and f["slot"] != body_lamp)
    g0, g1 = swapped[i0].get_editor_property("attachment_guid"), swapped[i1].get_editor_property("attachment_guid")
    swapped[i0].set_editor_property("attachment_guid", g1)
    swapped[i1].set_editor_property("attachment_guid", g0)
    expect_error("- control: a glass pointing at ANOTHER lamp's GUID refuses EXTENSION_SAVED_READBACK",
                 lambda: L.verify_target_extensions(TOOL, t, swapped), "EXTENSION_SAVED_READBACK")
    touched = copy.deepcopy(pre + authored)
    mv = touched[0].get_editor_property("mover")
    mv.set_editor_property("enabled", True)
    touched[0].set_editor_property("mover", mv)
    expect_error("- control: a pre-existing attachment whose Mover changed refuses EXTENSION_PREEXISTING_CHANGED",
                 lambda: L.verify_target_extensions(TOOL, t, touched), "EXTENSION_PREEXISTING_CHANGED")

    def poke(show, index, att_index, struct, field, value):
        cues = show.get_editor_property("cues")
        pair = cues[index].get_editor_property("wing_pair")
        atts = pair.get_editor_property("attachments")
        s = atts[att_index].get_editor_property(struct)
        s.set_editor_property(field, value)
        atts[att_index].set_editor_property(struct, s)
        pair.set_editor_property("attachments", atts)
        cues[index].set_editor_property("wing_pair", pair)
        show.set_editor_property("cues", cues)
        return atts

    show_x = FS(cues=[fake_cue("A" * 32, "inside", REC["P04"]["plan"]["targets"][0]["before_rows"][:2]),
                      fake_cue("B" * 32, "outside", REC["P04"]["plan"]["targets"][1]["before_rows"][:2])])
    h0 = L.extension_outside_hash(TOOL, show_x, ["A" * 32])
    poke(show_x, 0, 0, "mover", "enabled", True)
    check("+ extension outside hash ignores the target cues' Mover/Body", L.extension_outside_hash(TOOL, show_x, ["A" * 32]) == h0)
    atts = poke(show_x, 1, 1, "body", "follow_light", True)
    check("- control: one Body changed on an OUTSIDE cue changes the extension outside hash",
          L.extension_outside_hash(TOOL, show_x, ["A" * 32]) != h0)
    check("- control: the P04 tool's own rows cannot see it (attachment_state has no Mover/Body: why the new hash exists)",
          "mover" not in TOOL._attachment_rows(atts)[1] and "body" not in TOOL._attachment_rows(atts)[1])
finally:
    TOOL.unreal = _saved_tool_unreal

src = _inspect.getsource(L._mutate_apply)
check("+ _mutate_apply writes Mover/Body on the authored vessels BEFORE they are set into the Show [source]",
      0 < src.index('apply_extensions(tool, target["fixtures"], authored, enums)')
      < src.index("tool._set_pair_attachments(show, index, modified + authored)"))
src = _inspect.getsource(L._run)
check("+ DRY/APPLY build every template AND write+read back its Mover/Body before any mutation; APPLY checks the "
      "saved Show (in-memory + after save) incl. the extension outside hash [source]",
      src.index('apply_extensions(tool, t["fixtures"], built, enums)') < src.index('if mode == "DRY":')
      and src.count("_verify_applied(tool, show, plan, outside_before, extension_outside_before)") == 1
      and src.count("_verify_applied(tool, readback, plan, outside_before, extension_outside_before)") == 1)

print("\n== 21. every other passage byte-identical to the pre-wiring tool + data (.bak-20261006-preCppWire)")
PRE = load_backup_tool(os.path.join(HERE, "lighting_scores_apply.py.bak-20261006-preCppWire"), "_scores_pre_cppwire")
PRE_SCORES = json.load(open(os.path.join(HERE, "lighting_scores.json.bak-20261006-preCppWire"), encoding="utf-8"))
PRE_LOOKS = PRE.resolve_looks(PRE_SCORES, PRE.load_base_looks(PRE_SCORES)[0])
NEW_KEYS = ("mover", "mover_write", "body_write")


def normalise(plan, drop_movers=False):
    plan = copy.deepcopy(plan)
    for t in plan["targets"]:
        if drop_movers:
            t["fixtures"] = [f for f in t["fixtures"] if f.get("role") != "MOVER"]
            for key in ("fixture_count", "light_fixture_count", "output", "cpp_pending"):
                t.pop(key, None)
        for f in t["fixtures"]:
            for key in NEW_KEYS:
                f.pop(key, None)
            for key in ("cpp_field", "authored", "unwired"):
                (f.get("body_behaviour") or {}).pop(key, None)
    if drop_movers:
        for key in ("fixture_count", "light_fixture_count", "warnings"):
            plan.pop(key, None)
    return plan


def pre_plan(key):
    cues, passages, record = build_show(PRE_SCORES)
    return PRE.build_score_plan(TOOL, PRE_SCORES, PRE_LOOKS, key, passages, cues, record, None)


IDENT = {}
for key in ALL:
    old, new = pre_plan(key), plan_for(key)
    IDENT[key] = (old, new)
    check("+ %s plan identical to the pre-wiring tool except the new Mover/Body write keys%s" % (
        key, " and P05's 12 movers" if key == "P05" else ""),
        L._canonical(normalise(old, key == "P05")) == L._canonical(normalise(new, key == "P05")))
old5, new5 = IDENT["P05"]
added = {(t["ordinal"], f["slot"]) for t in new5["targets"] for f in t["fixtures"]} - {
    (t["ordinal"], f["slot"]) for t in old5["targets"] for f in t["fixtures"]}
check("+ P05's only additions are MOVER_L/R in bays 13-18; its 12 warnings are gone; casters unchanged",
      added == {(o, s) for o in range(13, 19) for s in ("MOVER_L", "MOVER_R")} and len(old5["warnings"]) == 12
      and new5["warnings"] == [] and old5["shadow"] == new5["shadow"], str(sorted(added)))
x = copy.deepcopy(IDENT["P03"][1])
x["targets"][4]["fixtures"][0]["intensity"] += 1.0e-9
check("- control: one 1e-9 intensity change in one P03 fixture breaks the identity (the comparison can fail)",
      L._canonical(normalise(IDENT["P03"][0])) != L._canonical(normalise(x)))
check("+ the only new keys on any non-P05 fixture are the write keys (mover/mover_write/body_write)",
      all(set(f) - set(g) <= set(NEW_KEYS) for key in ("P01", "P02", "P03", "P04", "P06")
          for to, tn in zip(IDENT[key][0]["targets"], IDENT[key][1]["targets"])
          for g, f in zip(to["fixtures"], tn["fixtures"])))

print("\n== 22. per-light drift decisions (option c)")
REPORT = json.load(open(L.DRIFT_REPORT_PATH, encoding="utf-8"))
REPORT_SHA = L._sha256_path(L.DRIFT_REPORT_PATH)
TPL = {k: json.load(open(L._decisions_path(k), encoding="utf-8")) for k in L.DRIFT_TEMPLATE_PASSAGES}
counts = {k: len([g for g in v if L.GUID_KEY.match(g)]) for k, v in TPL.items()}
unknown_counts = {p["passage"]: p["lights_by_class"].get(L.DRIFT_UNKNOWN, 0) for p in REPORT["passages"] if not p.get("skipped")}
check("+ templates exist for P01/P02/P04/P06, one entry per UNKNOWN light in the report, all proposed keep, status TEMPLATE",
      counts == {k: unknown_counts[k] for k in counts} and all(v["status"] == "TEMPLATE" for v in TPL.values())
      and all(e["decision"] == e["proposed"] == "keep" for v in TPL.values() for g, e in v.items() if L.GUID_KEY.match(g))
      and all(v["report_sha256"] == REPORT_SHA and v["report_run"] == REPORT["run"] for v in TPL.values()), str(counts))
check("+ P03/P05 get no template (no UNKNOWN drift: attributed classes only)",
      unknown_counts.get("P03") == 0 and unknown_counts.get("P05") == 0)
check("+ every template entry is readable (label, cue, kind, old -> new per field, a consequence per option) and pinned",
      all(e["label"] and e["cue"] and e["row_kind"] and e["changes"] and set(e["options"]) == {"keep", "overwrite", "fold"}
          and isinstance(e["row_hash"], str) for v in TPL.values() for g, e in v.items() if L.GUID_KEY.match(g)))


def report_live(passage, target, unknown_only=True):
    """The target's live rows as the report saw them; by default with ATTRIBUTED drift already reverted by its tool."""
    rp = L._report_passage(REPORT, passage)
    cue = next(c for c in rp["cues"] if c["cue_guid"] == target["cue_guid"])
    after_by = {r["guid"]: r for r in target["after_rows"]}
    removed, recon = set(), {}
    for light in cue["lights"]:
        if light["class"] != L.DRIFT_UNKNOWN and unknown_only:
            continue
        row = L.reconstruct_live_row(TOOL, after_by[light["guid"]], light)
        if row is None:
            removed.add(light["guid"])
        else:
            recon[light["guid"]] = row
    return [recon.get(r["guid"], r) for r in target["after_rows"] if r["guid"] not in removed], cue


def decided_from(tpl, decision=None, per=None, status="DECIDED"):
    d = copy.deepcopy(tpl)
    d["status"], d["decided_by"] = status, "harness"
    for g, e in d.items():
        if L.GUID_KEY.match(g):
            e["decision"] = (per or {}).get(g, decision or e["decision"])
    return d


def target_of(passage, label):
    return next(t for t in REC[passage]["plan"]["targets"] if t["cue_label"] == label)


def fake_show(passage, live_by_cue=None, cls=FS):
    targets = REC[passage]["plan"]["targets"]
    size = max(t["show_index"] for t in targets) + 2
    cues = [fake_cue(guid("filler", passage, i), "filler %d" % i, targets[0]["before_rows"][:1], cls) for i in range(size)]
    for t in targets:
        cues[t["show_index"]] = fake_cue(t["cue_guid"], t["cue_label"], (live_by_cue or {}).get(t["cue_guid"], t["after_rows"]), cls)
    return FS(cues=cues)


def rows_of(show):
    return {TOOL._guid_text(c.get_editor_property("cue_guid")): TOOL._attachment_rows(
        c.get_editor_property("wing_pair").get_editor_property("attachments")) for c in show.get_editor_property("cues")}


_saved_tool_unreal = TOOL.unreal
TOOL.unreal = types.SimpleNamespace(InfinityAttachmentKind=types.SimpleNamespace(**KIND))
_tmp = tempfile.mkdtemp(prefix="decisions_")
try:
    ok = L.validate_drift_decisions(TOOL, decided_from(TPL["P02"]), "P02", REPORT, REPORT_SHA, REC["P02"])
    check("+ a DECIDED P02 file validates: 12 GUIDs, all SCORE_FIXTURE", len(ok) == 12
          and {e["row_kind"] for e in ok.values()} == {"SCORE_FIXTURE"})
    expect_error("- control: the TEMPLATE itself is refused until marked DECIDED",
                 lambda: L.validate_drift_decisions(TOOL, TPL["P02"], "P02", REPORT, REPORT_SHA, REC["P02"]),
                 "DRIFT_DECISIONS_NOT_DECIDED")
    expect_error("- control: DECIDED without decided_by is refused",
                 lambda: L.validate_drift_decisions(TOOL, dict(decided_from(TPL["P02"]), decided_by=" "), "P02", REPORT,
                                                    REPORT_SHA, REC["P02"]), "DRIFT_DECISIONS_NOT_DECIDED")
    expect_error("- control: decisions bound to another report (sha) are refused",
                 lambda: L.validate_drift_decisions(TOOL, decided_from(TPL["P02"]), "P02", REPORT, "0" * 64, REC["P02"]),
                 "DRIFT_DECISIONS_REPORT_MISMATCH")
    expect_error("- control: decisions for another scores record run are refused",
                 lambda: L.validate_drift_decisions(TOOL, decided_from(TPL["P02"]), "P02", REPORT, REPORT_SHA,
                                                    dict(REC["P02"], run="20990101-000000")), "DRIFT_DECISIONS_RECORD_MISMATCH")
    rp02 = L._report_passage(REPORT, "P02")
    rig = next(l for c in rp02["cues"] for l in c["lights"] if l["class"] == "RIG_LAMP_DROP")
    x = decided_from(TPL["P02"])
    x[rig["guid"]] = {"decision": "overwrite", "row_hash": "x"}
    expect_error("- control: a decision on a RIG_LAMP_DROP light is refused (attributed: revert that tool first)",
                 lambda: L.validate_drift_decisions(TOOL, x, "P02", REPORT, REPORT_SHA, REC["P02"]),
                 "DRIFT_DECISION_NOT_UNKNOWN|%s|class=RIG_LAMP_DROP" % rig["guid"])
    expect_error("- control: fold on a RETAINED lamp (P01 House L) is refused",
                 lambda: L.validate_drift_decisions(TOOL, decided_from(TPL["P01"], per={"24F0FC454E591513FB387DBE58E881DC": "fold"}),
                                                    "P01", REPORT, REPORT_SHA, REC["P01"]), "FOLD_NOT_APPLICABLE")
    expect_error("- control: an unknown decision word is refused",
                 lambda: L.validate_drift_decisions(TOOL, decided_from(TPL["P04"], decision="maybe"), "P04", REPORT,
                                                    REPORT_SHA, REC["P04"]), "DRIFT_DECISION_BAD")
    dup = os.path.join(_tmp, "dup.json")
    g4 = next(g for g in TPL["P04"] if L.GUID_KEY.match(g))
    open(dup, "w").write('{"%s": {"decision": "keep"}, "%s": {"decision": "overwrite"}}' % (g4, g4))
    expect_error("- control: a GUID listed twice is refused (json.load would keep only the last)",
                 lambda: L._load_json_unique(dup), "JSON_DUPLICATE_KEY")
    check("+ no decisions file -> load_revert_decisions is None -> REVERT runs the unchanged pre-6-Oct path",
          L.load_revert_decisions(TOOL, "P02", REC["P02"], os.path.join(_tmp, "absent.json")) is None)

    t02 = target_of("P02", "P02 Wing 001")
    live, unused = report_live("P02", t02)
    dec_over = L.validate_drift_decisions(TOOL, decided_from(TPL["P02"], "overwrite"), "P02", REPORT, REPORT_SHA, REC["P02"])
    dec_keep = L.validate_drift_decisions(TOOL, decided_from(TPL["P02"], "keep"), "P02", REPORT, REPORT_SHA, REC["P02"])
    steps = L.revert_target_plan(TOOL, t02, live, dec_over)
    check("+ P02 Wing 001, all overwrite: the 3 hand-edited score lamps are removed and the cue returns EXACTLY to "
          "before_rows", steps["expected_rows"] == t02["before_rows"] and not steps["kept_score_fixtures"])
    steps = L.revert_target_plan(TOOL, t02, live, dec_keep)
    kept = [r for r in live if r["guid"] in dec_keep]
    check("+ P02 Wing 001, all keep: the 3 edited score lamps stay as they are (and are listed), everything else reverts",
          steps["expected_rows"] == t02["before_rows"] + kept and len(steps["kept_score_fixtures"]) == 3)
    expect_error("- control: the same drift with NO decision for it refuses DRIFT_UNDECIDED (lists the lamps)",
                 lambda: L.revert_target_plan(TOOL, t02, live, {}), "DRIFT_UNDECIDED|cue=P02 Wing 001|")
    stale = copy.deepcopy(live)
    next(r for r in stale if r["guid"] in dec_keep)["lighting"]["intensity"] += 1.0
    expect_error("- control: a decided lamp edited AGAIN after it was pinned refuses DRIFT_DECISION_STALE",
                 lambda: L.revert_target_plan(TOOL, t02, stale, dec_keep), "DRIFT_DECISION_STALE|cue=P02 Wing 001")
    with_rig, unused = report_live("P02", t02, unknown_only=False)
    expect_error("- control: attributed drift left in place (rig lamp drop not reverted first) refuses DRIFT_UNDECIDED",
                 lambda: L.revert_target_plan(TOOL, t02, with_rig, dec_keep), "DRIFT_UNDECIDED|cue=P02 Wing 001")
    t03 = target_of("P02", "P02 Wing 003")
    check("+ an undrifted cue under a decisions file reverts exactly to before_rows",
          L.revert_target_plan(TOOL, t03, t03["after_rows"], dec_keep)["expected_rows"] == t03["before_rows"])
    t01 = target_of("P01", "P01 Wing 001")
    live01, unused = report_live("P01", t01)
    s01 = L.revert_target_plan(TOOL, t01, live01, L.validate_drift_decisions(
        TOOL, decided_from(TPL["P01"], "keep"), "P01", REPORT, REPORT_SHA, REC["P01"]))
    house = [r for r in live01 if r["label"].endswith((" House L", " House R"))]
    check("+ P01 Wing 001 keep: House L/R (retained, hand-tuned, warmers off by the Opening) stay EXACTLY as live",
          len(house) == 2 and all(r in s01["expected_rows"] for r in house) and all(not r["enabled"] for r in house))
    s01o = L.revert_target_plan(TOOL, t01, live01, L.validate_drift_decisions(
        TOOL, decided_from(TPL["P01"], "overwrite"), "P01", REPORT, REPORT_SHA, REC["P01"]))
    check("+ P01 overwrite on a RETAINED lamp == keep (REVERT never writes a retained lamp); the score lamp is removed",
          all(r in s01o["expected_rows"] for r in house)
          and not any(r["label"] == "P01 SCORE B01 VOID PRACTICAL_DEAD" for r in s01o["expected_rows"]))
    t06 = target_of("P06", "P06 Wing 055")
    live06, unused = report_live("P06", t06)
    s06 = L.revert_target_plan(TOOL, t06, live06, L.validate_drift_decisions(
        TOOL, decided_from(TPL["P06"], "keep"), "P06", REPORT, REPORT_SHA, REC["P06"]))
    gone = {g for g in TPL["P06"] if L.GUID_KEY.match(g)}
    check("+ P06 Wing 055: the removed FX TEST candle rows stay removed; the rest returns to before_rows",
          s06["expected_rows"] == [r for r in t06["before_rows"] if r["guid"] not in gone] and len(gone) == 2)

    plan02 = REC["P02"]["plan"]
    s_old, s_new = fake_show("P02"), fake_show("P02")
    PRE._mutate_revert(TOOL, s_old, plan02)
    L._mutate_revert(TOOL, s_new, plan02)
    r_old, r_new = rows_of(s_old), rows_of(s_new)
    check("+ clean P02 (live == after), fake Show: old and new _mutate_revert give byte-identical Shows, every target == "
          "before_rows", L._canonical(r_old) == L._canonical(r_new)
          and all(r_new[t["cue_guid"]] == t["before_rows"] for t in plan02["targets"]))
    s_dec = fake_show("P02")
    L._mutate_revert_decided(TOOL, s_dec, plan02, {})
    check("+ clean P02 through the DECIDED path with no decisions: the same Show as the old path",
          L._canonical(rows_of(s_dec)) == L._canonical(r_old))
    check("+ _mutate_revert is source-identical to the pre-6-Oct tool's (no-decisions REVERT unchanged) [source]",
          _inspect.getsource(L._mutate_revert) == _inspect.getsource(PRE._mutate_revert))
    rp02_cues = {c["cue_guid"] for c in rp02["cues"]}
    drift_live = {tt["cue_guid"]: report_live("P02", tt)[0] for tt in plan02["targets"] if tt["cue_guid"] in rp02_cues}
    kept_by = {cg: [r for r in rows if r["guid"] in dec_keep] for cg, rows in drift_live.items()}
    errs = []
    for module in (PRE, L):
        try:
            module._mutate_revert(TOOL, fake_show("P02", drift_live), plan02)
            errs.append(None)
        except Exception as error:  # noqa: BLE001
            errs.append(str(error))
    check("+ drifted P02 with no decisions file: old and new refuse with the IDENTICAL message (REVERT_CURRENT_STATE_DRIFT)",
          errs[0] is not None and errs[0] == errs[1] and errs[0].startswith("REVERT_CURRENT_STATE_DRIFT|cue=P02 Wing 001"),
          (errs[0] or "")[:90])
    s_keep = fake_show("P02", drift_live)
    L._mutate_revert_decided(TOOL, s_keep, plan02, dec_keep)
    after_keep = rows_of(s_keep)
    check("+ drifted P02 (all 17 drifted cues, hand edits only), DECIDED keep (fake Show): each cue == before_rows + its "
          "own kept edited lamps (12 in all); undrifted cues == before_rows",
          all(after_keep[tt["cue_guid"]] == tt["before_rows"] + kept_by.get(tt["cue_guid"], []) for tt in plan02["targets"])
          and sum(len(v) for v in kept_by.values()) == 12 and kept_by[t02["cue_guid"]] == kept)
    s_over = fake_show("P02", drift_live)
    L._mutate_revert_decided(TOOL, s_over, plan02, dec_over)
    check("+ drifted P02, DECIDED overwrite (fake Show): EXACTLY every before_rows, as a clean REVERT would give",
          all(rows_of(s_over)[t["cue_guid"]] == t["before_rows"] for t in plan02["targets"]))
    s_lie = fake_show("P02", drift_live, cls=LyingFS)
    snapshot = L._canonical(rows_of(s_lie))
    expect_error("- control: an `enabled` setter that lies refuses REVERT_NOT_EXACT ...",
                 lambda: L._mutate_revert_decided(TOOL, s_lie, plan02, dec_keep), "REVERT_NOT_EXACT|cue=P02 Wing 0")
    check("- ... and the in-memory rollback leaves the fake Show exactly as it was", L._canonical(rows_of(s_lie)) == snapshot)
    live_casts = sum(L._row_casts(r) for t in plan02["targets"] for r in t["after_rows"])
    exp_casts = sum(L._row_casts(r) for t in plan02["targets"] for r in t["before_rows"])
    check("+ shadow arithmetic: (before - live target casters + expected casters) == the old formula on a clean P02",
          exp_casts - live_casts == plan02["shadow"]["target_before"] - plan02["shadow"]["target_after"],
          "%d-%d vs %d-%d" % (exp_casts, live_casts, plan02["shadow"]["target_before"], plan02["shadow"]["target_after"]))

    clamp = "6E40E1EE4C897401D96E5C9B5EEC1EA4"
    after_by = {r["guid"]: r for r in t02["after_rows"]}
    live_by = {r["guid"]: r for r in live}
    folded, rows = L.fold_scores(TOOL, SCORES, LOOKS, "P02", [(t02, after_by[clamp], live_by[clamp])])
    bay1 = [f for f in L.bay_fixtures(TOOL, folded, LOOKS, "P02", L.validate_scores(folded, LOOKS, TOOL)["P02"]["specs"][0])
            if f.get("slot") == "PRACTICAL_CLAMP"][0]
    check("+ fold P02 B01 PRACTICAL_CLAMP: writes bay_overrides['1'] colour; the re-expanded lamp carries the hand colour",
          folded["passages"]["P02"]["bay_overrides"] == {"1": {"PRACTICAL_CLAMP": rows[0]["overrides"]}}
          and L._close_list(bay1["color_rgb_linear"], live_by[clamp]["lighting"]["color"][:3], 1e-9), str(rows[0]["overrides"]))
    again, unused = L.fold_scores(TOOL, folded, LOOKS, "P02", [(t02, after_by[clamp], live_by[clamp])])
    check("+ fold is idempotent (folding again changes nothing)", L._canonical(again) == L._canonical(folded))
    check("+ fold leaves every OTHER passage's plan byte-identical, and P02's other bays too",
          all(L._canonical(plan_for(k, scores=folded)) == L._canonical(IDENT[k][1]) for k in ("P01", "P03", "P04", "P05", "P06"))
          and all(L._canonical(a) == L._canonical(b) for a, b in zip(plan_for("P02", scores=folded)["targets"][1:],
                                                                         IDENT["P02"][1]["targets"][1:])))
    beam = "2138879B4CD8983A937508A54FCB6C1B"
    expect_error("- control: fold of a re-aimed lamp (rotation changed) is refused FOLD_FIELD_UNSUPPORTED",
                 lambda: L.fold_scores(TOOL, SCORES, LOOKS, "P02", [(t02, after_by[beam], live_by[beam])]),
                 "FOLD_FIELD_UNSUPPORTED|P02 SCORE B01 THEATRICAL BEAM_R|field=relative_transform.rotation_xyzw")
    t02b = target_of("P02", "P02 Wing 002")
    live_b, unused = report_live("P02", t02b)
    g_b = next(g for g in TPL["P02"] if g.startswith("734A455A"))
    expect_error("- control: fold onto a slot the round-2 look no longer has is refused FOLD_SLOT_ABSENT",
                 lambda: L.fold_scores(TOOL, SCORES, LOOKS, "P02", [(t02b, {r["guid"]: r for r in t02b["after_rows"]}[g_b],
                                                                    {r["guid"]: r for r in live_b}[g_b])]), "FOLD_SLOT_ABSENT")
    g_d = next(g for g in TPL["P01"] if g.startswith("FDF5DFC6"))
    expect_error("- control: a fold the dim-bulb pass would overwrite (P01 B01 dead practical colour) is refused "
                 "FOLD_NOT_REPRODUCED",
                 lambda: L.fold_scores(TOOL, SCORES, LOOKS, "P01", [(t01, {r["guid"]: r for r in t01["after_rows"]}[g_d],
                                                                    {r["guid"]: r for r in live01}[g_d])]),
                 "FOLD_NOT_REPRODUCED")
    x = copy.deepcopy(SCORES)
    x["passages"]["P02"]["bay_overrides"] = {"99": {"PRACTICAL_CLAMP": {"intensity": 1.0}}}
    expect_error("- control: a bay override outside the passage is refused BAD_BAY_OVERRIDES",
                 lambda: L.validate_scores(x, LOOKS, TOOL), "BAD_BAY_OVERRIDES")
    x["passages"]["P02"]["bay_overrides"] = {"1": {"PRACTICAL_CLAMP": {"rotation_rpy_deg": [0, 0, 0]}}}
    expect_error("- control: a bay override field outside BAY_OVERRIDE_FIELDS is refused",
                 lambda: L.validate_scores(x, LOOKS, TOOL), "BAD_BAY_OVERRIDE_FIELDS")
    real_sha = L._sha256_path(L.SCORES_PATH)
    saved_path = L.SCORES_PATH
    tmp_scores = os.path.join(_tmp, "lighting_scores.json")
    shutil.copyfile(saved_path, tmp_scores)
    L.SCORES_PATH = tmp_scores
    try:
        first = L._fold_into_scores(TOOL, SCORES, LOOKS, "P02", [(t02, after_by[clamp], live_by[clamp])], "RUN1")
        second = L._fold_into_scores(TOOL, L.load_scores(tmp_scores), LOOKS, "P02", [(t02, after_by[clamp], live_by[clamp])], "RUN2")
        on_disk = json.load(open(tmp_scores, encoding="utf-8"))
        check("+ fold write: backup of the old bytes, new scores read back, LF only, a second REVERT run is a no-op",
              first["changed"] and os.path.isfile(first["backup"]) and not second["changed"]
              and L._sha256_path(first["backup"]) == real_sha
              and on_disk["passages"]["P02"]["bay_overrides"]["1"]["PRACTICAL_CLAMP"] == rows[0]["overrides"]
              and open(tmp_scores, "rb").read().count(b"\r\n") == 0)
    finally:
        L.SCORES_PATH = saved_path
    check("+ the real lighting_scores.json was not touched by the fold tests",
          L._sha256_path(L.SCORES_PATH) == real_sha and "bay_overrides" not in json.dumps(L.load_scores()))
    dpath = os.path.join(_tmp, "lighting_drift_decisions_P02.json")
    L._write_json_lf(dpath, decided_from(TPL["P02"], per={clamp: "fold"}))
    pre_flight = L.check_drift_decisions("P02", dpath)
    check("+ offline pre-flight of a DECIDED P02 (11 keep, 1 fold): fold reproduced, nothing undecided, RIG drift listed",
          pre_flight["counts"] == {"keep": 11, "overwrite": 0, "fold": 1} and len(pre_flight["folds"]) == 1
          and not pre_flight["undecided_unknown"] and pre_flight["attributed_lights"] == {"RIG_LAMP_DROP": 33},
          str(pre_flight["counts"]))
    regen = L.build_drift_decisions_template(TOOL, SCORES, LOOKS, "P02", REPORT, REPORT_SHA, REC["P02"],
                                             decided_from(TPL["P02"], per={clamp: "fold"}))
    check("+ regenerating from the same report carries every decision over (row unchanged) and keeps DECIDED",
          regen["status"] == "DECIDED" and regen[clamp]["decision"] == "fold")
    moved = decided_from(TPL["P02"], per={clamp: "fold"})
    moved[clamp]["row_hash"] = "0" * 64
    regen = L.build_drift_decisions_template(TOOL, SCORES, LOOKS, "P02", REPORT, REPORT_SHA, REC["P02"], moved)
    check("- control: a decision whose row changed is NOT carried (back to the keep proposal, status TEMPLATE)",
          regen["status"] == "TEMPLATE" and regen[clamp]["decision"] == "keep")
    bad_light = copy.deepcopy(next(l for c in rp02["cues"] for l in c["lights"] if l["guid"] == clamp))
    bad_light["fields"][0]["new"] = copy.deepcopy(bad_light["fields"][0]["old"])
    expect_error("- control: a report light whose listed field does not actually differ (not a readable row) cannot be pinned",
                 lambda: L.reconstruct_live_row(TOOL, after_by[clamp], bad_light), "DRIFT_ROW_RECONSTRUCT")
finally:
    TOOL.unreal = _saved_tool_unreal
    shutil.rmtree(_tmp, ignore_errors=True)
src = _inspect.getsource(L._run)
check("+ REVERT: decisions load first; every refusal (undecided/stale/drift) and the fold run BEFORE the backup and any "
      "Show write; no file -> _mutate_revert + the old shadow formula + before_rows readback [source]",
      src.index("load_revert_decisions(tool, passage_key, record)") < src.index("plan_decided_revert(")
      < src.index("_fold_into_scores(") < src.index('tool._backup("PreLightingScores%sRevert-"')
      < src.index("_mutate_revert(tool, show, plan)")
      and 'expected = before_revert - plan["shadow"]["target_after"] + plan["shadow"]["target_before"]' in src
      and 'target["before_rows"] if expected_rows is None' in src)

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
