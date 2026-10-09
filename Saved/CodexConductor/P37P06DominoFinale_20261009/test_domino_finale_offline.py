"""Falsifiable offline harness for the P37/P06 domino finale planner."""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import domino_finale_core as D


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
RESULTS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


T = load("p37_harness_topple_core", PROJECT / "Saved/CodexFlatV3/topple/topple_core.py")
A = load("p37_harness_domino_apply", HERE / "domino_finale_apply.py")
TA = load("p37_harness_topple_apply", PROJECT / "Saved/CodexFlatV3/topple/topple_apply.py")


def check(name, condition):
    ok = bool(condition)
    RESULTS.append(ok)
    print(("PASS " if ok else "FAIL ") + name)


def raises(fn, token):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - the token is the assertion
        return token in str(exc)
    return False


def guid(i):
    return ("%032X" % (i + 1))[-32:]


def side(i, name):
    route = 500.0 + i * 1200.0
    lateral = 700.0 if name == "R" else -700.0
    return {"mesh": "/Game/Test/SM_%s_%02d" % (name, i), "materialized": True, "upright": True,
            "external_curve": None, "thickness_cm": 25.0, "height_cm": 1000.0,
            "axis_dot_tangent": 0.0, "hinge_route_cm": route,
            "hinge_world": [route, lateral, -100.0],
            "lateral_min_cm": lateral - 200.0, "lateral_max_cm": lateral + 200.0,
            "has_hinge_socket": False, "pivot_local": [0.0, 0.0, -100.0]}


def fixture():
    tick = 24000.0
    rows = []
    for i in range(20):
        rows.append({"ordinal": i, "show_index": 100 + i, "cue_guid": guid(i), "label": "Synthetic %02d" % i,
                     "enabled": True, "has_top": False, "station_cm": 500.0 + i * 1200.0,
                     "pass_frame": int((2.0 + i * 4.0) * tick), "mechanism_sha": "m%02d" % i,
                     "sides": {"L": side(i, "L"), "R": side(i, "R")}})
    measurement = {"dry_ok": True, "run_id": "SYNTH-DRY", "tick": tick,
                   "passage_guid": T.P06_GUID, "rows": rows,
                    "law": {"points": ([[0, 0.0]] + [[r["pass_frame"], r["station_cm"]] for r in rows] +
                                       [[int(126.001125 * tick), 40000.0]]),
                           "segment_end": int(126.001125 * tick)},
                   "modulation": {"wing_modulation": False, "speed_shaped": False,
                                  "longitudinal_offset": False}}
    a_rows = [{"cue_guid": r["cue_guid"], "label": r["label"], "side": "L", "timing": {"start_s": i * .3}}
              for i, r in enumerate(rows[:6])]
    a_plan = {"inputs_hash": "CHAINA", "chain": {"side": "L", "start_ordinal": 0, "n": 6, "end": "braced",
              "rows": a_rows, "events": ([{"type": "domino", "slab": i, "hits": i + 1, "t": 2.0 + i * .3}
                                             for i in range(5)] +
                                            [{"type": "wall", "slab": 5, "t": 3.5}]),
              "timing": {"creak_s": 29.79, "final_impact_s": 33.29, "rest_s": 34.0}}}
    active = {"run_id": "TOPPLE-A", "originals": "topple_originals_TOPPLE-A.json"}
    inventory = {"dust_candidates": [{"asset": "/Game/KK_S2_Shrine/StarterContent/Particles/P_Ambient_Dust",
                                       "particle_light_module_strings": []}],
                 "sound_candidates": [
                     {"asset": "/Game/KK_S2_Shrine/StarterContent/Audio/Collapse01",
                      "embedded_wave": {"rms_dbfs": -14.66}},
                     {"asset": "/Game/KK_S2_Shrine/StarterContent/Audio/Collapse02",
                      "embedded_wave": {"rms_dbfs": -14.76}}]}
    return measurement, a_plan, active, inventory


m, a_plan, active, inventory = fixture()

args, bad = D.validate_args({})
check("args +: choreographed B defaults validate", not bad and args["mode_b"] == "choreographed" and
      args["restyle_chain_a"] is False and args["side"] == "R" and args["min_fall_s"] == 1.4)
check("args -: dust auto_activate true refused",
      "DUST_AUTO_ACTIVATE_TRUE_REFUSED" in D.validate_args({"dust_auto_activate": True})[1])
check("args -: bounce over 3 degrees refused",
      "BOUNCE_OUTSIDE_0_3_DEG" in D.validate_args({"bounce_deg": 3.01, "bounce_jitter_deg": 0.0})[1])
check("args -: bounce plus jitter over 3 refused",
      "BOUNCE_PLUS_JITTER_GT_3_DEG" in D.validate_args({"bounce_deg": 2.9, "bounce_jitter_deg": .2})[1])
check("args -: unknown B mode refused", "MODE_B_INVALID" in D.validate_args({"mode_b": "physics"})[1])
check("args -: fall shorter than minimum refused",
      any("FALL_BELOW_MINIMUM" in x for x in D.validate_args({"fall_s": 1.39})[1]))

draws1 = D.seeded_draws(3706, 4, .08, 2.0, .35)
draws2 = D.seeded_draws(3706, 4, .08, 2.0, .35)
check("random +: same seed is bit-stable", draws1 == draws2)
check("random -control: another seed changes the ordered draws", draws1 != D.seeded_draws(3707, 4, .08, 2.0, .35))
check("random +: one signed shockwave jitter per transition and one bounce draw per row",
      len(draws1) == 4 and draws1[0]["shockwave_jitter_s"] is None and
      all(-.08 <= r["shockwave_jitter_s"] <= .08 for r in draws1[1:]) and
      all(0 <= r["bounce_deg"] <= 3 for r in draws1))

raw = D.gravity_solver_keys(1.65, .62, 2.5, 2.35)
pre = [r for r in raw if r["phase"] <= 1.65 / (1.65 + .62)]
check("drama +: pre-impact profile accelerates late and is not linear",
      pre[1]["value"] < .34 and pre[2]["value"] < .70 and pre[-1]["value"] == 1.0)
check("bounce +: exactly one rebound no greater than 3 degrees",
      len([r for r in raw if 0 < r["phase"] < 1 and r["value"] < 1 and r["phase"] > pre[-1]["phase"]]) == 1
      and min(r["value"] for r in raw if r["phase"] >= pre[-1]["phase"]) >= 1 - 3 / 90.0)

projected = D.project_post_p33(m, 110.561125, 25.0)
chosen, table, reason = D.choose_choreographed_suffix(
    projected, 12, "R", D.guid_set_from_chain(a_plan["chain"]), args, T)
check("chain +: valid synthetic 12-row choreographed suffix reaches the end",
      chosen["n"] == 12 and chosen["start_ordinal"] == 8 and reason is None)
check("chain +: diagnostics are ordered 12 down to 1", [r["n"] for r in table] == list(range(12, 0, -1)))

plan = D.build_plan(m, a_plan, active, inventory, {}, T)
check("plan +: valid synthetic plan is APPLY-ready", plan["apply_ready"] and plan["selected_rows"] == 12)
check("plan +: P33 rounds selected 110.561125 s music to a 110.6 s Passage",
      plan["post_p33_projection"]["selected_music_s"] == 110.561125 and
      plan["post_p33_projection"]["post_p33_segment_end_s"] == 110.6)
check("plan +: final impact is exactly post-P33 end minus two seconds",
      abs(plan["chain_b"]["timing"]["final_impact_s"] - 108.6) < 1e-9)
check("plan +: solved rest remains inside P06", plan["chain_b"]["timing"]["rest_s"] <=
      plan["chain_b"]["timing"]["segment_end_s"])
check("plan +: each next creak follows prior impact by bounded shockwave delay",
      all(.27 <= row["timing"]["shockwave_from_previous_s"] <= .43 for row in plan["chain_b"]["rows"][1:]))
check("geometry +: downstage fall audit has no standing-panel intersections",
      all(not row["standing_panel_intersections"] for row in plan["chain_b"]["fall_sweep_audit"]))
slow = D.build_plan(m, a_plan, active, inventory, {"fall_s": 10.0}, T)
check("timing +: oversized requested chain reduces N without squeezing fall below its requested time",
      slow["apply_ready"] and 2 <= slow["selected_rows"] < 12 and
      all(abs(row["timing"]["impact_s"] - row["timing"]["creak_s"] - 10.0) < 1e-8
          for row in slow["chain_b"]["rows"]))

contact_m = copy.deepcopy(m)
for fixture_row in contact_m["rows"]:
    fixture_row["sides"]["R"]["height_cm"] = 1500.0
contact = D.build_plan(contact_m, a_plan, active, inventory, {"mode_b": "contact"}, T)
check("compatibility +: explicit contact mode remains available", contact["apply_ready"] and
      contact["chain_b"]["mode_b"] == "contact")
check("dust +: one capped, non-auto burst per impact", len(plan["dust_bursts"]) == 12 and
      all(x["auto_activate"] is False and x["cast_shadow"] is False and x["light_count"] == 0
          for x in plan["dust_bursts"]))
check("dust +: only B's final burst is slam-scaled", sum(x["slam_scaled"] for x in plan["dust_bursts"]) == 1 and
      plan["dust_bursts"][-1]["scale"] > plan["dust_bursts"][0]["scale"])
check("sound +: measured loudest candidate selected", plan["slam_sound"]["asset"].endswith("Collapse01"))
check("restyle +: Chain A remains read-only by default", plan["chain_a"]["adopted_read_only"] and
      plan["chain_a_restyle"] is None)
restyled = D.build_plan(m, a_plan, active, inventory, {"restyle_chain_a": True}, T)
check("restyle +: opt-in A restyle has a separate legacy plan and confirm",
      restyled["chain_a_restyle_plan"]["chain"]["chain_id"] == D.CHAIN_A_RESTYLE and
      "A_RESTYLE" in restyled["chain_a_restyle_confirm"])

late = D.build_plan(m, a_plan, active, inventory, {"slam_s": 108.61}, T)
check("guard -: slam after end-minus-two is refused",
      not late["apply_ready"] and any("SLAM_AFTER_END_MINUS_LEAD" in x for x in late["blockers"]))

collision_m = copy.deepcopy(m)
first = collision_m["rows"][-12]["sides"]["R"]
standing = collision_m["rows"][-13]["sides"]["R"]
standing["hinge_route_cm"] = first["hinge_route_cm"] - 500.0
standing["hinge_world"][0] = standing["hinge_route_cm"]
collision = D.build_plan(collision_m, a_plan, active, inventory, {}, T)
check("guard -: fall sweep through a standing panel is refused",
      not collision["suffix_diagnostics"][0]["eligible"] and
      any("FALL_SWEEP_INTERSECTS_STANDING_PANEL" in x
          for x in collision["suffix_diagnostics"][0]["reasons"]))

overlap_rows = a_plan["chain"]["rows"] + plan["chain_b"]["rows"][:1]
check("guard -: Chain B over a Chain A row is refused",
      raises(lambda: D.require_disjoint(overlap_rows, plan["chain_b"]["rows"]), "CHAIN_B_OVERLAPS_CHAIN_A_ROWS"))

bad_dust = D.build_plan(m, a_plan, active, inventory, {"dust_auto_activate": True}, T)
check("guard -: whole plan refuses dust auto_activate true", not bad_dust["apply_ready"] and
      "DUST_AUTO_ACTIVATE_TRUE_REFUSED" in bad_dust["blockers"])
lit_inventory = copy.deepcopy(inventory)
lit_inventory["dust_candidates"][0]["particle_light_module_strings"] = ["ParticleModuleLight"]
lit_dust = D.build_plan(m, a_plan, active, lit_inventory, {}, T)
check("guard -: dust asset with a particle light module is refused",
      "DUST_ASSET_HAS_PARTICLE_LIGHT_MODULE" in lit_dust["blockers"])

check("records +: B and A-restyle active pointers cannot collide",
      D.active_record_name(D.CHAIN_B) != D.active_record_name(D.CHAIN_A_RESTYLE))
check("records -: unknown chain id cannot name a pointer",
      raises(lambda: D.active_record_name("A"), "ACTIVE_RECORD_CHAIN_ID"))

state = {"rows": {"A1": {"keys": [1, 2, 3]}, "B1": {"keys": [8, 9]}},
         "chains": {"A": {"active": True, "original_rows": {"A1": {"keys": [0]}}},
                    "B": {"active": True, "original_rows": {"B1": {"keys": [7]}}}}}
a_before = copy.deepcopy(state["rows"]["A1"])
registry = D.registry_entry("B", "APPLY-B", ["B1"], {"B1": "hash"}, "originals-B.json")
before_apply, applied = D.apply_scope(state, "B", {"B1": {"keys": [10, 11]}})
check("APPLY -control: B apply leaves A keys bit-identical",
      applied["rows"]["A1"] == a_before and before_apply["rows"]["A1"] == a_before)
before, after = D.revert_scope(applied, registry)
check("REVERT +: B is restored and deactivated", after["rows"]["B1"] == {"keys": [7]} and
      after["chains"]["B"]["active"] is False)
check("REVERT -control: B revert leaves A keys bit-identical", after["rows"]["A1"] == a_before and
      after["chains"]["A"]["active"] is True and before["rows"]["A1"] == after["rows"]["A1"])

forecast = plan["p33_forecast"]
check("P33 +: B is solved inside the post-P33 P06", forecast["chain_b_past_new_end"] is False)
check("P33 +: Chain A row shifts are non-uniform", len({round(x["shift_s"], 6) for x in forecast["chain_a"]}) > 1)

production = json.loads((HERE / "domino_finale_plan.json").read_text(encoding="utf-8"))
check("production +: choreographed plan reduces 12 to 11 rather than crossing standing panels",
      production["apply_ready"] and production["selected_rows"] == 11 and
      production["requested_rows"] == 12 and production["args"]["mode_b"] == "choreographed" and
      production["reduction_reason"] == "REDUCED_TO_11_TO_FIT_WITHOUT_SQUEEZING")
check("production +: inherited dust and Collapse01 inventory gates passed",
      not production["dust_asset_inventory"]["particle_light_module_strings"] and
      production["slam_sound"]["asset"].endswith("Collapse01"))

legacy_view = A._legacy_chain_plan(production)
check("live adapter +: B uses the exact legacy chain-only plan schema",
      set(legacy_view) == {"parts", "still", "keeper", "chain", "inputs", "inputs_hash"} and
      legacy_view["parts"] == ["chain"] and legacy_view["still"] == [] and
      legacy_view["keeper"] is None and legacy_view["chain"] is production["chain_b"])
check("live adapter +: post-A legacy and finale input hashes match and B rows are present",
      legacy_view["inputs_hash"] == production["inputs_hash"] and
      [r["cue_guid"] for r in legacy_view["chain"]["rows"]] ==
      [r["cue_guid"] for r in production["chain_b"]["rows"]])

thick_refusals = [
    "P06 Wing 016 R: TOO_THICK_FOR_SLAB: 72.0 cm",
    "P06 Wing 022 R: TOO_THICK_FOR_SLAB: 96.8 cm",
    "P06 Wing 025 R: TOO_THICK_FOR_SLAB: 72.0 cm",
    "P06 Wing 044 R: PANEL_NOT_UPRIGHT",
]
check("live window +: choreographed mode bypasses only slab-thickness refusals",
      TA._window_refusals_for_apply({"refusals": thick_refusals}, legacy_view) ==
      ["P06 Wing 044 R: PANEL_NOT_UPRIGHT"])
contact_view = copy.deepcopy(legacy_view)
contact_view["chain"]["mode_b"] = "contact"
for row in contact_view["chain"]["rows"]:
    row["chain_mode"] = "contact"
check("live window -: contact mode still refuses thick slabs",
      TA._window_refusals_for_apply({"refusals": thick_refusals}, contact_view) == thick_refusals)

input_rows = {row["label"]: row for row in production["inputs"]["rows"]}
audits = {row["label"]: row for row in production["chain_b"]["fall_sweep_audit"]}
thick_ind = {"P06 Wing 016": 72.0, "P06 Wing 022": 96.793, "P06 Wing 025": 72.0}
check("production +: all three thick IND pieces are explicitly in B and thickness-hashed",
      all(label in input_rows and abs(input_rows[label]["thickness_cm"] - thickness) < 1e-6
          for label, thickness in thick_ind.items()))
check("production +: all three thick IND pieces have clean standing-panel sweep audits",
      all(label in audits and not audits[label]["standing_panel_intersections"] for label in thick_ind))
check("production +: B end-margin gate covers the thick IND chain",
      production["chain_b"]["timing"]["final_impact_s"] <=
      production["chain_b"]["timing"]["segment_end_s"] - production["args"]["slam_lead_s"] + 1e-9)

live_source = (HERE / "domino_finale_apply.py").read_text(encoding="utf-8")
apply_b_source = live_source[live_source.index("def run_apply(args, plan, run):"):
                             live_source.index("def run_revert(args, plan, run):")]
apply_a_source = live_source[live_source.index("def run_apply_restyle(args, plan, run):"):
                             live_source.index("def run_apply(args, plan, run):")]
check("live safety +: record and backup occur before legacy mutation",
      apply_b_source.index("_write(overall_path, record, exclusive=True)") < apply_b_source.index("legacy.run_apply(") and
      apply_b_source.index("backup = _backup(run") < apply_b_source.index("legacy.run_apply(") and
      apply_a_source.index("_write(overall, record, exclusive=True)") < apply_a_source.index("legacy.run_apply("))
check("live safety +: exact targeted saves and no Save All/permanent asset deletion",
      "save_dirty_packages" not in live_source and "delete_asset" not in live_source and
      "save_asset(package, only_if_is_dirty=False)" in live_source)
check("live FX +: dust is tagged, non-auto, shadowless, and particle-triggered",
      all(token in live_source for token in ('unreal.Name("P37_DOMINO_B")', '"auto_activate", False',
                                             '"cast_shadow", False', 'ParticleKey', '"TRIGGER"')))
check("live records +: B and A_RESTYLE route to separate record directories",
      '"records", C.CHAIN_B' in live_source and '"records", C.CHAIN_A_RESTYLE' in live_source)
check("live proof +: post-A matching hashes and exact B write set are logged/checked",
      "B_POST_A_PLAN" in apply_b_source and "b_after = legacy.run_apply" in apply_b_source and
      "CHAIN_B_WRITE_SET_MISMATCH" in apply_b_source and "B_LEGACY_APPLY_OK" in apply_b_source)

from PIL import Image
with Image.open(HERE / "p06_domino_finale_timeline.png") as timeline:
    check("preview +: timeline PNG rendered at review resolution", timeline.size == (1800, 1000))

passed = sum(RESULTS)
failed = len(RESULTS) - passed
result_line = "P37B_P06_CHOREOGRAPHED_DOMINO_HARNESS|PASS=%d|FAIL=%d|TOTAL=%d" % (
    passed, failed, len(RESULTS))
(HERE / "harness_result.txt").write_text(result_line + "\n", encoding="utf-8")
print(result_line)
raise SystemExit(0 if failed == 0 else 1)
