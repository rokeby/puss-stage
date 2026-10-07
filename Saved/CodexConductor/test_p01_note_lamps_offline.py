"""Offline harness for p01_note_lamps.py with positive and negative controls. No Unreal, writes only to a temp dir.

Run: python Saved/CodexConductor/test_p01_note_lamps_offline.py
Final line: TEST_P01_NOTE_LAMPS|pass=<n>|fail=<m>
"""
import ast
import copy
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))
spec = importlib.util.spec_from_file_location("p01_note_lamps_under_test", os.path.join(HERE, "p01_note_lamps.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print("%s|%s%s" % ("PASS" if condition else "FAIL", name, ("|" + str(detail)) if detail and not condition else ""))


def raises(fn, token):
    try:
        fn()
    except M.P01NoteLampsError as error:
        return token in str(error), str(error)[:300]
    return False, "no error"


BASE = M.load_config()
NOTES, LAMPS, ROUTE = M.offline_inputs(BASE)


def plan_with(**overrides):
    cfg = copy.deepcopy(BASE)
    cfg.update(overrides)
    cfg = M.validate_config(cfg)
    return M.build_plan(NOTES, LAMPS, ROUTE, cfg)


def must_have(plan, token, mutate):
    bad = copy.deepcopy(plan)
    mutate(bad)
    return raises(lambda: M.check_plan(bad), token)


P = plan_with()

# ---- parse every deliverable
for path in (os.path.join(HERE, "p01_note_lamps.py"), os.path.join(HERE, "p01_note_lamps_run.py"),
             os.path.join(HERE, "test_p01_note_lamps_offline.py"),
             os.path.join(PROJECT, "Tools", "MusicNotes", "note_lamps_preview.py")):
    with open(path, encoding="utf-8") as handle:
        try:
            ast.parse(handle.read(), filename=path)
            check("ast_parse|" + os.path.basename(path), True)
        except SyntaxError as error:
            check("ast_parse|" + os.path.basename(path), False, error)

# ---- determinism (+ control: a different seed must change the plan, else the check is vacuous)
P2 = plan_with()
check("determinism_same_plan_sha", P["plan_sha256"] == P2["plan_sha256"] and P["events"] == P2["events"])
P_seed = plan_with(seed=BASE["seed"] + 1)
check("determinism_control_seed_changes_plan", P_seed["plan_sha256"] != P["plan_sha256"])
src = open(os.path.join(HERE, "p01_note_lamps.py"), encoding="utf-8").read()
two_draws = [line for line in src.splitlines() if len(re.findall(r"draw01\(|\.random\(\)|\.uniform\(", line)) > 1]
check("rng_one_draw_per_expression", not two_draws, two_draws)

# ---- count knob
check("count_default_30", P["selected_count"] == 30 and P["requested_count"] == 30, P["selected_count"])
for n in (25, 35):
    pn = plan_with(target_count=n)
    check("count_knob_%d" % n, pn["selected_count"] == n or any(w.startswith("SHORTFALL") for w in pn["warnings"]),
          (pn["selected_count"], pn["warnings"]))
ok, msg = must_have(P, "COUNT_EXCEEDED", lambda b: b["events"].append(copy.deepcopy(b["events"][-1])))
check("count_negative_extra_event_refused", ok, msg)

# ---- Gary's marks
musts = {m["show_s"] for m in P["must"]}
chosen = {e["show_s"] for e in P["events"]}
check("gary_marks_resolved_7", len(P["must"]) == 7, P["must"])
check("gary_marks_all_selected", musts <= chosen, sorted(musts - chosen))
for mark in (101.0, 102.5, 103.2, 109.0, 112.0):
    near = [m for m in P["must"] if m["mark"] == mark]
    check("gary_mark_%.1f_within_0.75s" % mark, near and abs(near[0]["show_s"] - mark) <= 0.75, near)
check("gary_range_143_145_has_note", any(isinstance(m["mark"], list) and 142.75 <= m["show_s"] <= 145.25 for m in P["must"]))
one_must = sorted(musts)[0]
ok, msg = must_have(P, "MUST_NOT_SELECTED", lambda b: b.__setitem__("events", [e for e in b["events"] if e["show_s"] != one_must]))
check("gary_negative_dropped_mark_refused", ok, msg)
ok, msg = raises(lambda: plan_with(must_include_show_s=[50.0]), "MUST_INCLUDE_UNRESOLVED")
check("gary_negative_mark_outside_music_refused", ok, msg)

# ---- lookahead
lo, hi = [v * 100 for v in BASE["lookahead_m"]]
check("lookahead_all_events_15_45m", all(lo <= e["ahead_cm"] <= hi for e in P["events"]),
      [round(e["ahead_cm"]) for e in P["events"]])
check("lookahead_offsets_negative_lamp_ahead", all(o < 0 for t in P["targets"] for o in t["drama_after"]["flash_camera_offsets_cm"]))
pw = plan_with(lookahead_m=[20.0, 30.0])
check("lookahead_knob_20_30m", all(2000 <= e["ahead_cm"] <= 3000 for e in pw["events"]))
ok, msg = must_have(P, "LOOKAHEAD_VIOLATED", lambda b: b["events"][0].__setitem__("ahead_cm", 500.0))
check("lookahead_negative_near_lamp_refused", ok, msg)

# ---- no lamp double-fired within 3 s (force reuse by restricting the pool, so the check is not vacuous)
pr = plan_with(roles=["PRACTICAL_CLAMP"], target_count=30)
reused = [t for t in pr["targets"] if len(t["notes_show_s"]) > 1]
check("refire_control_reuse_happens", bool(reused), len(reused))
gaps_ok = all(b - a >= 3.0 for t in pr["targets"] for a, b in zip(t["notes_show_s"], t["notes_show_s"][1:]))
check("refire_gap_ge_3s_under_reuse", gaps_ok)
check("refire_max_flashes_per_lamp", all(len(t["notes_show_s"]) <= BASE["max_flashes_per_lamp"] for t in pr["targets"]))
check("behaviour_single_per_lamp", all(len({e["behaviour"] for e in pr["events"] if e["lamp_guid"] == t["attachment_guid"]}) == 1
                                       for t in pr["targets"]))
check("stay_lamps_one_note", all(len(t["notes_show_s"]) == 1 for t in pr["targets"] if t["behaviour"] == "stay"))


ok, msg = must_have(P, "LAMP_REFIRED_WITHIN_GAP", lambda b: (b["events"].__setitem__(1, dict(b["events"][1], show_s=b["events"][0]["show_s"] + 1.0,
                                                                                               lamp_guid=b["events"][0]["lamp_guid"]))))
check("refire_negative_1s_refire_refused", ok, msg)

# ---- exclusions / mix
check("gary_bays_3_4_never_chosen", not any(t["cue_label"] in ("P01 Wing 003", "P01 Wing 004") for t in P["targets"]))
pa = plan_with(allow_gary_bays=True, roles=["TOP_L", "TOP_R", "PRACTICAL_CLAMP", "PRACTICAL_L", "PRACTICAL_GLIMMER"])
check("gary_bays_control_eligible_when_allowed", any(l["guid"] for l in pa["eligible_lamps"] if l["ordinal"] in (3, 4)))
check("mix_has_all_three_behaviours", all(P["behaviour_counts"][b] > 0 for b in M.BEHAVIOURS), P["behaviour_counts"])
check("roles_whitelisted", all(t["role"] in BASE["roles"] for t in P["targets"]))
check("lamps_have_intensity", all(t["intensity"] >= BASE["min_intensity"] for t in P["targets"]))
check("stay_holds_at_pass", all(M.eval_drama(dict(t["drama_context"], **t["drama_after"]), t["lamp_route_cm"], t["lamp_route_cm"]) >= 0.5 - 1e-3
                                for t in P["targets"] if t["behaviour"] == "stay"))
glint = [t for t in P["targets"] if t["behaviour"] == "glint"]
check("glint_decay_about_0p8s", glint and all(0.7 <= s <= 0.9 for t in glint for s in t["decay_s_at_notes"]))

# ---- strike policy
ok, msg = raises(lambda: plan_with(strike_policy="keep"), "MUST_INCLUDE_UNASSIGNABLE")
check("strike_keep_no_distant_flash_possible", ok, msg)
ok, msg = must_have(P, "FLASH_NOT_AT_PEAK", lambda b: b["targets"][0]["drama_after"].__setitem__("strike_on_approach", True))
check("strike_negative_gated_flash_caught_by_check_plan", ok, msg)
pk = None
try:
    pk = plan_with(strike_policy="keep", lookahead_m=[1.0, 6.0], target_count=10, must_include_show_s=[])
except M.P01NoteLampsError as error:
    pk = error
check("strike_keep_control_near_flash_allowed", isinstance(pk, dict) and pk["selected_count"] > 0, pk if not isinstance(pk, dict) else "")
check("strike_flash_owns_sets_strike_false", all(t["drama_after"]["strike_on_approach"] is False for t in P["targets"]))

# ---- EvaluateFlash port against the held patch's own automation test values
d = {"flash": True, "flash_camera_offsets_cm": [-400.0, -100.0], "flash_attack_cm": 3.0, "flash_decay_cm": 18.0,
     "flash_rest_scale": 0.0}
at = lambda past, dd=d: M.eval_drama(dd, 0.0, past)  # noqa: E731
check("port_patch_test_values", at(-500) == 0 and at(-403.5) == 0 and abs(at(-400) - 1) < 1e-4 and at(-391) < 0.126
      and at(-381) == 0 and abs(at(-100) - 1) < 1e-4 and at(0) == 0)
d2 = dict(d, flash_rest_scale=0.02)
check("port_rest_floor", abs(at(-250, d2) - 0.02) < 1e-6)
d3 = dict(d2, strike_on_approach=True, strike_distance_cm=50.0, strike_ramp_cm=10.0, unstruck_intensity_scale=0.0)
check("port_strike_gates_flash", at(-400, d3) < 1e-6)

# ---- route law port
wings = [{"cue_guid": "A", "interval_ticks": 24000, "gap_cm": 300.0}, {"cue_guid": "B", "interval_ticks": 48000, "gap_cm": 300.0},
         {"cue_guid": "C", "interval_ticks": 1, "gap_cm": 1.0}]
r = M.route_from_settings(10.0, 14.0, 24000, 0, 0.0, 24000, 200.0, wings)
check("route_port_stations", [w["distance_cm"] for w in r["wings"]] == [0.0, 300.0, 600.0]
      and abs(M.distance_at(r, 11.0) - 300.0) < 1e-9 and abs(M.distance_at(r, 12.0) - 450.0) < 1e-9
      and abs(M.distance_at(r, 14.0) - 800.0) < 1e-9 and abs(M.speed_at(r, 12.0) - 150.0) < 1e-6)
ok, msg = raises(lambda: M.route_from_settings(10.0, 15.0, 24000, 0, 0.0, 24000, 200.0, wings), "ROUTE_END_MISMATCH")
check("route_negative_end_mismatch", ok, msg)
check("route_offline_marked_inferred", P["route_basis"] == "INFERRED_MODEL_CONSTANT_SPEED")

# ---- scope check (catches a stray field write)
import json  # noqa: E402
scores = json.load(open(M.SCORES_RECORD_P01, encoding="utf-8"))
base_all = {}
for t in scores["plan"]["targets"]:
    rows = copy.deepcopy(t["after_rows"])
    for row in rows:
        for k, v in M.FLASH_DEFAULTS.items():
            row["lighting"]["drama"][k] = copy.deepcopy(v)
    base_all[t["cue_guid"]] = rows
after_all = M.apply_plain(base_all, P, "after")
check("scope_positive_planned_write_passes", not M.scope_differences(base_all, after_all, P, "after"))
check("scope_positive_before_identity", not M.scope_differences(base_all, base_all, P, "before"))
tg = P["targets"][0]


def mutate_row(all_rows, guid, fn):
    out = copy.deepcopy(all_rows)
    for rows in out.values():
        for row in rows:
            if row["guid"] == guid:
                fn(row)
    return out


stray = mutate_row(after_all, tg["attachment_guid"], lambda r: r["lighting"].__setitem__("intensity", r["lighting"]["intensity"] + 1))
check("scope_negative_target_intensity_caught", bool(M.scope_differences(base_all, stray, P, "after")))
stray = mutate_row(after_all, tg["attachment_guid"], lambda r: r["lighting"]["drama"].__setitem__("strike_distance_cm", 1.0))
check("scope_negative_target_strike_distance_caught", bool(M.scope_differences(base_all, stray, P, "after")))
other = next(r["guid"] for rows in base_all.values() for r in rows if r["guid"] not in set(P["target_attachment_guids"]))
stray = mutate_row(after_all, other, lambda r: r["lighting"]["drama"].__setitem__("flash", True))
check("scope_negative_nontarget_flash_caught", bool(M.scope_differences(base_all, stray, P, "after")))
stray = mutate_row(after_all, tg["attachment_guid"], lambda r: r["lighting"]["drama"].__setitem__("flash_decay_cm", 1.0))
check("scope_negative_wrong_flash_value_caught", bool(M.scope_differences(base_all, stray, P, "after")))
ok, msg = raises(lambda: M.check_scope(base_all, stray, P, "after"), "SCOPE_CHANGED")
check("scope_check_raises", ok, msg)
check("revert_drift_none_after_apply", not M.revert_drifts(after_all, {"plan": P}))
check("revert_drift_detected", bool(M.revert_drifts(stray, {"plan": P})))
swapped = M._swap_sides(P)
check("revert_scope_restores_before", not M.scope_differences(after_all, base_all, swapped, "after"))
bad = copy.deepcopy(P)
bad["targets"][0]["drama_after"]["intensity"] = 5.0
ok, msg = raises(lambda: M.check_plan(bad), "PLAN_WRITES_UNOWNED_FIELD")
check("plan_negative_unowned_field_refused", ok, msg)

# ---- export mask
g_t, g_o = "A" * 32, "B" * 32
text = ("(Attachments=((AttachmentGuid=%s,Label=\"t\",Lighting=(Intensity=5.0,Drama=(bStrikeOnApproach=True,bFlash=False,"
        "FlashCameraOffsetsCm=(),FlashAttackCm=3.0))),(AttachmentGuid=%s,Lighting=(Intensity=7.0,Drama=(bFlash=False)))))") % (g_t, g_o)
h = M.export_hash([text], [g_t])
t1 = text.replace("bStrikeOnApproach=True,bFlash=False,FlashCameraOffsetsCm=(),FlashAttackCm=3.0",
                  "bStrikeOnApproach=False,bFlash=True,FlashCameraOffsetsCm=(-1500.0,-2000.0),FlashAttackCm=18.0")
check("export_mask_target_flash_change_invisible", M.export_hash([t1], [g_t]) == h)
check("export_mask_target_intensity_change_visible", M.export_hash([text.replace("Intensity=5.0", "Intensity=6.0")], [g_t]) != h)
check("export_mask_nontarget_flash_change_visible", M.export_hash([text.replace("Intensity=7.0,Drama=(bFlash=False)", "Intensity=7.0,Drama=(bFlash=True)")], [g_t]) != h)

# ---- engine lacks flash: pure gate, then the real _run path with a fake editor (no backup, no record, marker)
ok, msg = raises(lambda: M.check_engine({"drama_flash": False}), "ENGINE_LACKS_FLASH")
check("engine_gate_refuses", ok, msg)
check("engine_gate_control_passes", M.check_engine({"drama_flash": True}) is None)

tmp = tempfile.mkdtemp(prefix="p01_note_lamps_test_")
calls = {"backup": 0, "errors": [], "record": 0}


class FakeTool:
    SHOW_PATH = "/Game/X"
    EXPECTED_WORLD = "/Game/W"

    def _dirty_census(self):
        return {"content": [], "maps": []}

    def _backup(self, *a):
        calls["backup"] += 1

    def _write_json(self, *a, **k):
        calls["record"] += 1


fake_rig = types.SimpleNamespace(load_modules=lambda: (object(), FakeTool()),
                                 _ctx_facts=lambda tool: {"census": {"content": [], "maps": []}},
                                 check_context=lambda *a, **k: None)
fake_unreal = types.SimpleNamespace(log=lambda s: None, log_error=lambda s: calls["errors"].append(s))
saved = (M.unreal, M._load_rig_module, M._probe_capabilities, M._report_path)
M.unreal, M._load_rig_module = fake_unreal, (lambda: fake_rig)
M._probe_capabilities = lambda: {"drama_flash": False}
M._report_path = lambda mode, run: os.path.join(tmp, "report_%s_%s.json" % (mode, run))
try:
    try:
        M._run(M.check_args({"mode": "APPLY", "confirm": "APPLY P01NOTELAMPS"}))
        refused = False
    except M.P01NoteLampsError as error:
        refused = "ENGINE_LACKS_FLASH" in str(error)
    marker = calls["errors"][-1] if calls["errors"] else ""
    check("engine_apply_refused", refused)
    check("engine_apply_marker", marker.startswith("P01NOTELAMPS_STOPPED|") and "ENGINE_LACKS_FLASH" in marker
          and "|mode=APPLY|saved=0|" in marker and marker.endswith("NOTHING SAVED"), marker)
    check("engine_apply_no_backup_no_record", calls["backup"] == 0 and calls["record"] == 0, calls)
    M._probe_capabilities = lambda: {"drama_flash": True}
    calls["errors"].clear()
    try:
        M._run(M.check_args({"mode": "APPLY", "confirm": "APPLY P01NOTELAMPS"}))
    except Exception:  # noqa: BLE001 - the fake has no Show; any later stop is fine
        pass
    check("engine_control_flash_present_gets_past_gate", calls["errors"] and "ENGINE_LACKS_FLASH" not in calls["errors"][-1],
          calls["errors"][-1:] if calls["errors"] else "")
finally:
    M.unreal, M._load_rig_module, M._probe_capabilities, M._report_path = saved
    shutil.rmtree(tmp, ignore_errors=True)

# ---- args
ok, msg = raises(lambda: M.check_args({"mode": "APPLY"}), "CONFIRM_MISSING")
check("args_apply_needs_confirm", ok, msg)
check("args_plan_default", M.check_args({})["mode"] == "PLAN")

passed = sum(1 for _, ok in RESULTS if ok)
failed = len(RESULTS) - passed
print("TEST_P01_NOTE_LAMPS|pass=%d|fail=%d" % (passed, failed))
sys.exit(1 if failed else 0)
