"""Offline harness for interaction_walkin_ready.py (system Python, no Unreal). 5 Oct.

Real files used (no Unreal): CodexSoftGoods/DropBake/final13_opening_a06_w188.json (the bake), fit_transition_drapes.json
(I1 30 Sep apply rows), verify_transition_fit.json (I1-I5 30 Sep read-back), import_passing_bake.json (cache frames),
CodexCameraPilot/walkin_transitions.json (I1 20.3, OPENING 6.3267/203), curtain_sleight_record_I1.json and
curtain_sleight_I1_dry.json (5 Oct). curtain_sleight.plan_sleight is called for the redundancy proof; its fixture is
test_curtain_sleight.py's I1 fixture (inferred P02 pose/lens/speed, as there).
Every negative control must FAIL with its named id. Run: python test_interaction_walkin_ready.py
-> WALKIN_READY_TESTS|pass=N|fail=0
"""
import copy
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import interaction_walkin_ready as wr  # noqa: E402
import curtain_sleight as cs  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def load(*parts):
    with open(os.path.join(SAVED, *parts), "r", encoding="utf-8") as handle:
        return json.load(handle)


def raises(fn, prefix):
    try:
        fn()
    except wr.ReadyError as exc:
        return str(exc).startswith(prefix)
    return False


BAKE = load("CodexSoftGoods", "DropBake", "final13_opening_a06_w188.json")
REG = load("CodexCameraPilot", "walkin_transitions.json")
FIT_I1 = [r for r in load("CodexSoftGoods", "fit_transition_drapes.json")["rows"] if r["interaction"] == 1][0]
VERIFY = {r["interaction"]: r for r in load("CodexSoftGoods", "verify_transition_fit.json")["rows"]}
GC_FRAMES = load("CodexSoftGoods", "import_passing_bake.json")["read_back"]["gc_frames"]
REC_I1 = load("CodexConductor", "curtain_sleight_record_I1.json")
DRY_I1 = load("CodexConductor", "curtain_sleight_I1_dry.json")
DUR = wr.cache_duration_ticks(GC_FRAMES[0], GC_FRAMES[1], 24000.0)
HOLD_OFF = wr.hold_offset_ticks(wr.release_in_cache_s(BAKE), 24000.0, "release")

# ======================================================================================== A. landed_s / pile derivation
i1_fall_start = FIT_I1["sections_planned"][1][0]
d1 = wr.derive_landed(i1_fall_start, 25.0, BAKE, FIT_I1["sections_planned"][1][2], 24000.0)
check("POS I1 landed_s reproduces the registry's 20.3 (FALL start 400 @25 + bake 480->610 @30, round 0.1)",
      d1["landed_s"] == REG["I1"]["landed_s"] == 20.3, d1)
check("POS landed bake frame 610 = the OPENING probe's measured landed_bake_frame",
      d1["landed_bake_frame"] == REG["OPENING"]["file_evidence"]["landed_bake_frame"] == 610, d1["landed_bake_frame"])
dop = wr.derive_landed(49, 25.0, BAKE, 23200, 24000.0, rounding="exact")
check("POS exact formula reproduces OPENING landed_s 6.326666666666666 (FALL start 49, held sample 479)",
      abs(dop["landed_s"] - REG["OPENING"]["landed_s"]) <= 1.0e-9, dop["landed_s"])
check("POS sleight's landed_after_release for I1 = 4.3 = curtain_sleight_I1_dry.json inputs.walk",
      abs(d1["sleight_landed_after_release_s"] - DRY_I1["inputs"]["walk"]["landed_after_release_s"]) <= 1.0e-9,
      (d1["sleight_landed_after_release_s"], DRY_I1["inputs"]["walk"]["landed_after_release_s"]))
check("POS I1 sleight plan landed_s 71.3 = GO 1675/25 + 4.3 (record)",
      abs(REC_I1["plan"]["walk"]["landed_s"] - (1675 / 25.0 + d1["sleight_landed_after_release_s"])) <= 1.0e-9,
      REC_I1["plan"]["walk"]["landed_s"])
check("NEG threshold 1.35 m does NOT reproduce 20.3 -> the 1.0 m rule is load-bearing",
      wr.derive_landed(i1_fall_start, 25.0, BAKE, 23200, 24000.0, threshold_m=1.35)["landed_s"] != 20.3)
check("NEG FALL start 401 does NOT reproduce 20.3 -> the live FALL start is load-bearing",
      wr.derive_landed(401, 25.0, BAKE, 23200, 24000.0)["landed_s"] != 20.3)
ex = wr.derive_landed(i1_fall_start, 25.0, BAKE, 23200, 24000.0, rounding="exact")["landed_s"]
check("NEG(convention) probe-exact I1 = 20.3667 != 20.3: the registry convention (F as release, round 0.1) is what I1 used",
      abs(ex - 20.366666666666667) <= 1.0e-9 and round(ex, 1) != 20.3, ex)
nb = copy.deepcopy(BAKE)
nb["release_frame"] = None
check("NEG release_frame None -> BAKE_RELEASE_NONE (never assumed)",
      raises(lambda: wr.derive_landed(400, 25.0, nb, 23200, 24000.0), "BAKE_RELEASE_NONE"))
check("NEG top_z never under 0.5 m -> BAKE_NEVER_LANDS",
      raises(lambda: wr.derive_landed(400, 25.0, BAKE, 23200, 24000.0, threshold_m=0.5), "BAKE_NEVER_LANDS"))
edge, extent = wr.pile_edge_from_bake(BAKE)
check("POS pile_edge 203 from the bake = OPENING's probe value (same cache)",
      edge == REG["OPENING"]["pile_edge_cm"] == 203.0 and extent == [-203.0, 467.0], (edge, extent))
tb = copy.deepcopy(BAKE)
tb["rig_limits"]["unreal_cm"]["X_min"] = -190
check("NEG tampered X_min -190 -> 190 != 203 (detects a different bake extent)", wr.pile_edge_from_bake(tb)[0] != 203.0)

# ======================================================================================== drape layout
check("POS hold offset 23200 ticks (sample 479 = release - 1 cache frame); cache 264000 ticks (450-780 @30)",
      HOLD_OFF == 23200 and DUR == 264000, (HOLD_OFF, DUR))
ok_canon = all(wr.canonical_drape(500, 25.0, 4.0, HOLD_OFF, DUR)["hold"] == VERIFY[n]["gc_sections"][0]
               and wr.canonical_drape(500, 25.0, 4.0, HOLD_OFF, DUR)["fall"] == VERIFY[n]["gc_sections"][1]
               for n in (2, 3, 4, 5))
check("POS canonical(500, lead 4.0) = the 30 Sep read-back rows of I2-I5", ok_canon)
c1 = wr.canonical_drape(638, 25.0, 9.52, HOLD_OFF, DUR)
check("POS canonical(638, lead 9.52) = I1's 30 Sep read-back rows", [c1["hold"], c1["fall"]] == VERIFY[1]["gc_sections"])
check("NEG lead 5.0 -> not the read-back rows",
      wr.canonical_drape(500, 25.0, 5.0, HOLD_OFF, DUR)["fall"] != VERIFY[2]["gc_sections"][1])
check("NEG hold_at first -> offset 0, not the read-back rows",
      wr.canonical_drape(500, 25.0, 4.0, wr.hold_offset_ticks(1.0, 24000.0, "first"), DUR)["hold"] != VERIFY[2]["gc_sections"][0])

# ======================================================================================== B. assess
LIVES = wr.offline_live_rows(SAVED)
ARGS = wr.merged_args({})


def assess(n, mut=None, args=None, bake=BAKE):
    live = copy.deepcopy(LIVES[n])
    if mut:
        mut(live)
    return wr.assess(n, live, args or ARGS, bake)


base = [assess(n) for n in (2, 3, 4, 5)]
check("POS I2-I5 (30 Sep rows): no refusals, no edits needed, derived (500, 20.3, 203)",
      all(not r["refusals"] and not r["needs"] and (r["derived"]["minimum_end_frame"], r["derived"]["landed_s"],
                                                    r["derived"]["pile_edge_cm"]) == (500, 20.3, 203.0) for r in base),
      [(r["refusals"], r["needs"]) for r in base])
check("POS I2-I5 still 20.0 s on 5 Oct (I1 sleight segment rows)",
      all(LIVES[n]["segment_seconds_5oct"] == 20.0 for n in (2, 3, 4, 5)))


def first(r):
    return (r["refusals"] or [""])[0]


r = assess(2, lambda l: l.__setitem__("gc", [[0, 375, 23200, 240799], [375, 500, 23200, 0]]))
check("NEG drifted drape (FALL at 375) -> DRAPE_REFIT need to the canonical rows",
      [x["kind"] for x in r["needs"]] == ["DRAPE_REFIT"] and r["needs"][0]["to"] == VERIFY[2]["gc_sections"], r["needs"])
r = assess(2, lambda l: l.__setitem__("gc", [[0, 375, 23200, 240799], [375, 500, 23200, 0]]),
           args=wr.merged_args({"allow_drape_refit": False}))
check("NEG refit disallowed -> DRAPE_NOT_CANONICAL refusal", any(x.startswith("DRAPE_NOT_CANONICAL") for x in r["refusals"]))
r = assess(3, lambda l: l.__setitem__("playback", [0, 638]))
check("NEG end 638 (someone lengthened) -> END_UNPLANNED", first(r).startswith("END_UNPLANNED"), r["refusals"])
r = assess(3, lambda l: l.__setitem__("cache", "/Game/Scenes/Curtain/Baked/GC_Other"))
check("NEG other cache -> MOUTH_DRAPE_CACHE", any(x.startswith("MOUTH_DRAPE_CACHE") for x in r["refusals"]))
r = assess(4, lambda l: l.__setitem__("bake_id", "final12_x"))
check("NEG other bake id -> BAKE_ID", any(x.startswith("BAKE_ID") for x in r["refusals"]))
r = assess(4, lambda l: l.__setitem__("sleight_markers", [["CST drop", 1675]]))
check("NEG CST marker present -> SLEIGHT_ALREADY_APPLIED", any(x.startswith("SLEIGHT_ALREADY_APPLIED") for x in r["refusals"]))
r = assess(5, lambda l: l.__setitem__("walkin_tracks", ["Interaction 5 — Stalls Camera"]))
check("NEG stalls walk-in keyed -> WALKIN_PRESENT", any(x.startswith("WALKIN_PRESENT") for x in r["refusals"]))
r = assess(5, lambda l: l.__setitem__("drape_bindings", 2))
check("NEG two drape bindings -> MOUTH_DRAPE_COUNT", any(x.startswith("MOUTH_DRAPE_COUNT") for x in r["refusals"]))
r = assess(5, lambda l: l.__setitem__("spawn", [[0, 400]]))
check("NEG drape spawn [0,400) -> SPAWN_RANGE need", [x["kind"] for x in r["needs"]] == ["SPAWN_RANGE"], r["needs"])
r = assess(2, args=wr.merged_args({"planned_playback_changes": {"2": 638}}))
check("NEG a planned playback change -> PLAYBACK_CHANGE_NOT_SUPPORTED (no range change from this tool)",
      any(x.startswith("PLAYBACK_CHANGE_NOT_SUPPORTED") for x in r["refusals"]))

refit = assess(2, lambda l: l.__setitem__("gc", [[0, 375, 23200, 240799], [375, 500, 23200, 0]]))
plan = wr.plan_from_assessments([refit] + base[1:])
check("POS edit plan for a refit passes the range guard", wr.check_edit_plan(plan) == [], wr.check_edit_plan(plan))
bad = copy.deepcopy(plan)
bad["edits"]["2"][0]["to"][1][1] = 638
check("NEG an edit that moves the drape end -> EDIT_CHANGES_END",
      any(x.startswith("EDIT_CHANGES_END") for x in wr.check_edit_plan(bad)))
bad = copy.deepcopy(plan)
bad["edits"]["2"].append({"kind": "PLAYBACK", "from": [0, 500], "to": [[0, 638]]})
check("NEG a playback edit kind -> EDIT_KIND_NOT_ALLOWED",
      any(x.startswith("EDIT_KIND_NOT_ALLOWED") for x in wr.check_edit_plan(bad)))
check("POS plan digest is deterministic and changes with the plan",
      wr.plan_digest(plan) == wr.plan_digest(copy.deepcopy(plan)) and wr.plan_digest(plan) != wr.plan_digest(bad))

# ======================================================================================== C. soft-goods lengthening is redundant
WALK = cs.load_walk_planner(os.path.join(SAVED, cs.WALKIN_PLANNER))
DOORS = load("CodexConductor", cs.DOORS_RECORD)


def hangar_for(n):                                                   # test_curtain_sleight.py:48-58
    row = [x for x in DOORS["plan"]["scenes"] if int(x["scene"]) == n][0]
    leaf = [p for p in row["pieces"] if p["role"] == "leaf"][0]
    rec = DOORS["root_before"][str(n)]
    root = {"loc": list(rec["location"]), "rot": list(rec["rotation"])}
    hplan = load("CodexStructure", "hangar_s%d_plan.json" % n)
    dims = row["hangar_dimensions"]
    return {"root": root, "half_w": float(dims["half_w"]), "height": float(dims["height"]), "depth": float(dims["depth"]),
            "door_face_x": float(leaf["location_cm"][0]) - float(leaf["size_cm"][0]) / 2.0,
            "floor_z": float(leaf["location_cm"][2]) - float(leaf["size_cm"][2]) / 2.0 - 0.5,
            "dock_local": cs.to_local({"loc": root["loc"], "yaw": root["rot"][2]}, hplan["dock"]["loc"])}


def sleight_fixture(old_end, fall):                                  # test_curtain_sleight.py:61-96, I1
    hold = FIT_I1["sections_planned"][0]
    sample = BAKE["show_start"] + int(round(hold[2] / 24000.0 * cs.CACHE_FPS))
    a = BAKE["checkpoints"][str(sample)]["aabb_m"]
    yi = min(abs(a["x"][0]), abs(a["x"][1]))
    lan = load("CodexStructure", "mouth_lanterns_record.json")["lantern"]
    dv = [lan["aim_local_cm"][i] - lan["local_cm"][i] for i in range(3)]
    norm = math.sqrt(sum(v * v for v in dv))
    m = FIT_I1["mouth"]
    mouth = {"loc": [m["x"], m["y"], m["z"]], "yaw": m["yaw"]}
    start = cs.to_world(mouth, [0.0, 0.0, 150.0])
    return {
        "n": 1, "fps": 25.0, "tick_rate": 24000.0, "cue_guid": "FIXTURE", "cue_label": "Interaction 1 — Washing the Boy",
        "sequence": "%s/%s" % (cs.SEQ_DIR, cs.SEQS[1]), "old_end": old_end,
        "drape": {"frame": mouth, "hold": [0, fall[0], hold[2], hold[3]], "fall": list(fall), "spawn": [0, old_end],
                  "cache": cs.GC_PATH},
        "cache": {"bake_id": BAKE["id"], "hold_sample_bake_frame": sample, "duration_ticks": DUR,
                  "hang_aabb_cm": {"x": [a["y"][0] * 100.0, a["y"][1] * 100.0], "y": [-yi * 100.0, yi * 100.0],
                                   "z": [a["z"][0] * 100.0, a["z"][1] * 100.0]}},
        "hangar": hangar_for(1),
        "lantern": {"label": "S02 Mouth Lantern", "rel_loc": list(lan["local_cm"]), "rel_dir": [v / norm for v in dv],
                    "candela": lan["candela"], "kelvin": lan["kelvin"], "outer_deg": lan["outer_deg"],
                    "inner_deg": lan["inner_deg"], "radius_cm": lan["radius_cm"], "shadows": lan["shadows"]},
        "next": {"label": "Passage 2", "start_pose": {"x": start[0], "y": start[1], "z": start[2], "pitch": 0.0,
                                                      "yaw": mouth["yaw"], "roll": 0.0},
                 "focal": 25.0, "focus": 600.0, "v_end": 250.0},
        "walk": {"landed_after_release_s": float(REG["I1"]["landed_s"]) - fall[0] / 25.0,
                 "pile_edge_cm": float(REG["I1"]["pile_edge_cm"])},
        "filmback_mm": [23.76, 13.365],
        "hangar_lights": [{"label": "S1 Hangar Work Light", "intensity": 5000.0}],
        "existing_markers": [], "vamps": [], "walkin_tracks": [], "nested": [], "existing_labels": [],
        "scene": {"live_end": 5270, "content_end": 5270}, "exit_block_applied": False, "external_sound": "",
        "use_sequence_length": True, "reveal_when_covered": False, "fold_sequence_exists": False,
    }


AUTHORED = ("new_end", "mouth_drape", "cuts", "markers", "go", "mouth_camera", "hangar_camera", "hangar_drape",
            "mouth_card", "hangar_card", "lantern", "lights")
long_in = sleight_fixture(638, [400, 638, HOLD_OFF, 0])
short_in = sleight_fixture(500, [400, 500, HOLD_OFF, 0])
p_long = cs.plan_sleight(long_in, {"extra_tail_frames": 270}, WALK)
p_short = cs.plan_sleight(short_in, {"extra_tail_frames": 270 + (638 - 500)}, WALK)
same = {k: p_long[k] == p_short[k] for k in AUTHORED}
check("POS lengthened (638, extra 270) and NOT lengthened (500, extra 408) author the SAME sleight (curtain_sleight.plan_sleight)",
      all(same.values()) and p_long["walk"]["report"] == p_short["walk"]["report"], same)
check("POS both plans pass curtain_sleight.check_sleight identically",
      cs.check_sleight(p_long, long_in) == cs.check_sleight(p_short, short_in), (cs.check_sleight(p_long, long_in),
                                                                                cs.check_sleight(p_short, short_in)))
check("POS the planned end matches I1's applied record (2183) and FALL [1675, 2183, 23200, 0]",
      p_short["new_end"] == REC_I1["plan"]["new_end"] == 2183
      and p_short["mouth_drape"]["fall"] == REC_I1["plan"]["mouth_drape"]["fall"], p_short["mouth_drape"])
p_same_extra = cs.plan_sleight(short_in, {"extra_tail_frames": 270}, WALK)
check("NEG not lengthened with the SAME extra (270) -> a different end (extra must absorb the 138 frames)",
      p_same_extra["new_end"] != p_long["new_end"], (p_same_extra["new_end"], p_long["new_end"]))
check("POS curtain_sleight.py never reads minimum_end_frame (its only consumer is key_walkin_i1_p02.py)",
      "minimum_end_frame" not in open(os.path.join(HERE, "curtain_sleight.py"), encoding="utf-8").read())

# ======================================================================================== D. the one side effect: tails
snap = REC_I1["snapshot_before"]
t638 = wr.sleight_tails(snap["bindings"], snap["root_tracks"], 638)
t500 = wr.sleight_tails(snap["bindings"], snap["root_tracks"], 500)
rig500 = [t for t in t500 if t[0] == "Curtain Rig - Fire Safety Curtain"]
check("POS tails differ: at old_end 500 the sleight also stretches the inactive Fire Safety rig's [0,500] sections",
      not [t for t in t638 if t[0] == "Curtain Rig - Fire Safety Curtain" and t[3][1] == 500] and len(rig500) >= 3,
      (t638, rig500))

# ======================================================================================== E. cache wrap (sleight caveat)
budget = wr.fall_budget_frames(DUR, HOLD_OFF, 0, 24000.0, 25.0)
check("POS FALL cache budget = 250 frames @25 (264000 - 23200 ticks)", budget == 250, budget)
wrap_i1 = wr.fall_wrap(REC_I1["plan"]["mouth_drape"]["fall"], DUR, 24000.0, 25.0)
walk0 = REC_I1["plan"]["walk"]["start_frame"]
check("DETECT I1 applied sleight FALL [1675,2183) wraps at ~1925.8, inside its walk [%d, 2183)" % walk0,
      wrap_i1 is not None and abs(wrap_i1 - (1675 + 240800 / 960.0)) <= 1.0e-9 and walk0 < wrap_i1 < 2183, wrap_i1)
check("NEG control: I1's 30 Sep FALL [400,638) does not wrap", wr.fall_wrap([400, 638, 23200, 0], DUR, 24000.0, 25.0) is None)
check("NEG control: FALL of exactly 250 frames does not wrap; 251 does",
      wr.fall_wrap([0, 250, 23200, 0], DUR, 24000.0, 25.0) is None
      and wr.fall_wrap([0, 251, 23200, 0], DUR, 24000.0, 25.0) is not None)

# ======================================================================================== F. the proposal
prop = wr.propose_registry(REG, base, "test", "test")
check("POS proposal changes only I2-I5; I1 and OPENING byte-identical",
      prop["I1"] == REG["I1"] and prop["OPENING"] == REG["OPENING"] and set(prop) == set(REG))


def sleight_gate(reg_row):                                             # curtain_sleight.py:1351
    return reg_row.get("landed_s") is None or reg_row.get("pile_edge_cm") is None


check("POS curtain_sleight's WALKIN_NOT_READY gate now passes for I2-I5",
      not any(sleight_gate(prop["I%d" % n]) for n in (2, 3, 4, 5)) and all(sleight_gate(REG["I%d" % n]) for n in (2, 3, 4, 5)))
check("POS proposal's sleight landed_after_release for I2-I5 = I1's 4.3 (same release frame 400)",
      all(abs(prop["I%d" % n]["landed_s"] - 400 / 25.0 - (REG["I1"]["landed_s"] - 400 / 25.0)) <= 1.0e-9 for n in (2, 3, 4, 5)))
refused = assess(3, lambda l: l.__setitem__("playback", [0, 638]))
prop_bad = wr.propose_registry(REG, [refused], "test", "test")
check("NEG a refused Interaction keeps nulls (gate still refuses)", sleight_gate(prop_bad["I3"]), prop_bad["I3"]["landed_s"])
cs_src = open(os.path.join(HERE, "curtain_sleight.py"), encoding="utf-8").read()
check("POS the gate text the proposal satisfies is still in curtain_sleight.py",
      'reg.get("landed_s") is None or reg.get("pile_edge_cm") is None' in cs_src)
on_disk = os.path.join(HERE, wr.PROPOSED_NAME)
if os.path.isfile(on_disk):
    disk = load("CodexConductor", wr.PROPOSED_NAME)
    check("POS walkin_transitions.proposed.json on disk has I2-I5 = (500, 20.3, 203.0)",
          all((disk["I%d" % n]["minimum_end_frame"], disk["I%d" % n]["landed_s"], disk["I%d" % n]["pile_edge_cm"])
              == (500, 20.3, 203.0) for n in (2, 3, 4, 5)) and disk["I1"] == REG["I1"])

# ======================================================================================== report
passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = [(name, detail) for name, ok, detail in RESULTS if not ok]
for name, ok, detail in RESULTS:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  | " + str(detail)[:400]))
print("WALKIN_READY_SUMMARY|I2-I5=(500, 20.3, 203.0)|i1_exact=%.4f|budget=%d|i1_fall_wraps_at=%.2f|i1_walk=[%d,2183)"
      % (ex, budget, wrap_i1 or -1, walk0))
print("WALKIN_READY_TESTS|pass=%d|fail=%d" % (passed, len(failed)))
sys.exit(1 if failed else 0)
