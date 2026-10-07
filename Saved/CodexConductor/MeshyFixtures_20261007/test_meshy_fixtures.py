"""Offline harness for meshy_common / meshy_import / meshy_swap (python test_meshy_fixtures.py).

Every gate is run with a POSITIVE control (good input passes) and at least one NEGATIVE control (a specific bad input
fails with the specific code), so a gate that cannot fail is caught (memory puss-assert-dont-print). Real data: the 13
cleaned fixtures (cleanup_report.json + FBX sha256) and the on-disk 6 Oct row snapshots for P03 and P05.
Marker: MESHYFIX_HARNESS|pass=<n>|fail=<m>.
"""
from __future__ import annotations

import copy
import json
import math
import os
import random
import runpy
import shutil
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
C = types.SimpleNamespace(**runpy.run_path(os.path.join(HERE, "meshy_common.py"), run_name="_t_common"))
IMP = runpy.run_path(os.path.join(HERE, "meshy_import.py"), run_name="_t_import")
SWP = runpy.run_path(os.path.join(HERE, "meshy_swap.py"), run_name="_t_swap")
RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def raises(fn, code):
    try:
        fn()
    except C.MeshyError as error:
        return code in str(error)
    except Exception as error:  # noqa: BLE001 - a non-MeshyError counts only if it carries the code
        return code in str(error)
    return False


def rand_quat(rng):
    q = [rng.gauss(0, 1) for _ in range(4)]
    n = math.sqrt(sum(v * v for v in q))
    return [v / n for v in q]


TABLE = C.load_fixture_table(check_files=True)


def t_table():
    check("table.13_assets", len(TABLE) == 13 and set(TABLE) == set(C.BULBS) | set(C.LANTERNS))
    check("table.fbx_sha_matches_report", all(os.path.isfile(f["fbx"]) for f in TABLE.values()))
    tmp = tempfile.mkdtemp()
    try:
        with open(C.REPORT_PATH, encoding="utf-8") as handle:
            rep = json.load(handle)
        for name in TABLE:
            shutil.copytree(os.path.join(C.MESHY_ROOT, name), os.path.join(tmp, name))
        rep["assets"]["SM_Bulb_A60_Clear"]["fbx_sha256"] = "0" * 64
        bad = os.path.join(tmp, "cleanup_report.json")
        with open(bad, "w", encoding="utf-8") as handle:
            json.dump(rep, handle)
        check("table.NEG_tampered_sha_refused", raises(lambda: C.load_fixture_table(bad), "FBX_SHA_MISMATCH"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    clear = TABLE["SM_Bulb_A60_Clear"]
    check("table.clear_bulb_3_slots_glass_mi", len(clear["slots"]) == 3 and "Glass" in clear["mis"])
    check("table.frost_2_slots", len(TABLE["SM_Bulb_A60_Frost"]["slots"]) == 2 and "Glass" not in TABLE["SM_Bulb_A60_Frost"]["mis"])
    check("table.lanterns_2_lods", all(TABLE[n]["lods"] == 2 for n in C.LANTERNS) and all(TABLE[n]["lods"] == 1 for n in C.BULBS))


def good_rb(f):
    return {"class": "StaticMesh", "num_lods": f["lods"], "bounds_min": list(f["bounds_min"]),
            "bounds_max": list(f["bounds_max"]), "slot_names": list(f["slots"]), "nanite_enabled": False,
            "new_assets": [f["mesh"]]}


def t_import_gates():
    for name, f in TABLE.items():
        check("gate.POS_%s" % name, C.check_import_readback(f, good_rb(f)) == [])
    f = TABLE["SM_Lantern_Fresnel"]
    rb = good_rb(f); rb["num_lods"] = 1
    check("gate.NEG_lods", any(x.startswith("LODS") for x in C.check_import_readback(f, rb)))
    rb = good_rb(f); rb["bounds_min"][0], rb["bounds_max"][0] = -f["bounds_max"][0], -f["bounds_min"][0]
    check("gate.NEG_beam_flipped_x", any(x.startswith("BOUNDS") for x in C.check_import_readback(f, rb)))
    rb = good_rb(f)
    rb["bounds_min"] = [f["bounds_min"][1], f["bounds_min"][0], f["bounds_min"][2]]
    rb["bounds_max"] = [f["bounds_max"][1], f["bounds_max"][0], f["bounds_max"][2]]
    check("gate.NEG_axes_swapped", any(x.startswith("BOUNDS") for x in C.check_import_readback(f, rb)))
    rb = good_rb(f); rb["bounds_max"] = [v * 1.01 for v in rb["bounds_max"]]
    check("gate.NEG_scale_1pct", any(x.startswith("BOUNDS") for x in C.check_import_readback(f, rb)))
    rb = good_rb(f); rb["slot_names"] = list(reversed(rb["slot_names"]))
    check("gate.NEG_slot_order", any(x.startswith("SLOTS") for x in C.check_import_readback(f, rb)))
    rb = good_rb(f); rb["nanite_enabled"] = True
    check("gate.NEG_nanite", "NANITE_ON" in C.check_import_readback(f, rb))
    rb = good_rb(f); rb["new_assets"] = [f["mesh"], f["mesh"] + "_LOD1"]
    check("gate.NEG_lod_split_asset", any(x.startswith("LOD_SPLIT_ASSETS") for x in C.check_import_readback(f, rb)))
    g = TABLE["SM_Bulb_A60_Clear"]; rb = good_rb(g); rb["slot_names"] = rb["slot_names"][:2]
    check("gate.NEG_missing_glass_slot", any(x.startswith("SLOTS") for x in C.check_import_readback(g, rb)))
    check("gate.lens_sign_provable_all_lanterns", all(C.lens_sign_provable(TABLE[n]) for n in C.LANTERNS))
    sym = dict(TABLE["SM_Lantern_Fresnel"], bounds_min=[-15.0, -1, -1], bounds_max=[15.0, 1, 1])
    check("gate.NEG_symmetric_not_provable", not C.lens_sign_provable(sym))


def t_import_plan():
    common = C
    args = IMP["check_args"]({"mode": "DRY"}, common)
    for name, f in TABLE.items():
        mis, slots = IMP["mi_plan"](f, args, common)
        parents = [mis[s]["parent"] for s in slots]
        want = [C.MASTERS["glow"], C.MASTERS["lit"]] + ([C.MASTERS["glass"]] if len(f["slots"]) == 3 else [])
        check("import.mi_parents_%s" % name, parents == want and slots[0].endswith(("_Glow", "_Lens")))
    check("import.NEG_apply_needs_confirm", raises(lambda: IMP["check_args"]({"mode": "APPLY"}, common), "CONFIRM_MISSING"))
    check("import.NEG_unknown_arg", raises(lambda: IMP["check_args"]({"mode": "DRY", "foo": 1}, common), "ARGS_UNKNOWN"))
    check("import.NEG_bad_batch", raises(lambda: IMP["check_args"]({"mode": "APPLY", "confirm": "APPLY MESHYIMPORT",
                                                                     "batch": "SM_Nope"}, common), "BATCH_INVALID"))
    check("import.POS_apply_args", IMP["check_args"]({"mode": "APPLY", "confirm": "APPLY MESHYIMPORT"}, common)["batch"] == "next")
    rec = {"fixtures": {n: {} for n in C.IMPORT_ORDER[:3]}}
    check("import.next_batch", IMP["next_batch"](rec, C.IMPORT_ORDER) == C.IMPORT_ORDER[3]
          and IMP["next_batch"](None, C.IMPORT_ORDER) == "SM_Lantern_Fresnel"
          and IMP["next_batch"]({"fixtures": {n: {} for n in C.IMPORT_ORDER}}, C.IMPORT_ORDER) is None)
    check("import.lantern_first_has_no_glass", "Glass" not in TABLE[C.IMPORT_ORDER[0]]["mis"])
    check("import.texture_settings", IMP["texture_settings"]("Roughness") == (False, "TC_GRAYSCALE")
          and IMP["texture_settings"]("BaseColor") == (True, "TC_DEFAULT"))


def t_variant():
    rng = random.Random(7)
    guids = ["%032X" % rng.getrandbits(128) for _ in range(700)]
    a = {g: C.bulb_variant(g, "20261007", C.BULBS) for g in guids}
    shuffled = list(guids); rng.shuffle(shuffled)
    b = {g: C.bulb_variant(g, "20261007", C.BULBS) for g in shuffled}
    check("variant.POS_stable_order_independent", a == b)
    check("variant.POS_lowercase_guid_same", all(C.bulb_variant(g.lower(), "20261007", C.BULBS) == a[g] for g in guids[:50]))
    check("variant.all_seven_used", set(a.values()) == set(C.BULBS))
    other = {g: C.bulb_variant(g, "other-seed", C.BULBS) for g in guids}
    check("variant.NEG_seed_changes_picks", sum(a[g] != other[g] for g in guids) > len(guids) * 0.6)
    check("variant.NEG_bad_pool", raises(lambda: C.bulb_variant(guids[0], "s", ["SM_Bulb_Nope"]), "BULB_POOL"))


def t_bulb_placement():
    rng = random.Random(11)
    worst = 0.0
    neg_min = 1e9
    for name in C.BULBS:
        f = TABLE[name]
        for _ in range(40):
            q = rand_quat(rng)
            body = {"relative_transform": {"location": [rng.uniform(-500, 500) for _ in range(3)], "rotation_xyzw": q,
                                           "scale": [0.2, 0.2, 0.24]}}
            target = [rng.uniform(-800, 800) for _ in range(3)]
            s = rng.uniform(0.8, 4.0)
            t = C.bulb_transform(body, target, f, s)
            glass = [l + r for l, r in zip(t["location"], C.quat_rotate(t["rotation_xyzw"], [c * s for c in f["glass_centre"]]))]
            worst = max(worst, max(abs(a - b) for a, b in zip(glass, target)))
            pivot_glass = [l + r for l, r in zip(target, C.quat_rotate(q, [c * s for c in f["glass_centre"]]))]
            neg_min = min(neg_min, math.sqrt(sum((a - b) ** 2 for a, b in zip(pivot_glass, target))))
    check("place.POS_glass_centre_on_target", worst < 1e-3, "worst=%.2e" % worst)
    check("place.NEG_pivot_placement_misses", neg_min > 2.5, "min_miss=%.2f" % neg_min)
    sphere = {"relative_transform": {"location": [1, 2, 3], "rotation_xyzw": [0, 0, 0, 1], "scale": [0.18, 0.18, 0.22]}}
    centre, diameter = C.old_glass(sphere, C.PLAIN_SPHERE_BOUNDS)
    check("place.old_glass_sphere", centre == [1, 2, 3] and abs(diameter - 18.0) < 1e-9)
    check("place.scale_match_clamped", C.bulb_scale("MATCH_SPHERE", 18.0, 6.0, [0.75, 4.0]) == 3.0
          and C.bulb_scale("MATCH_SPHERE", 60.0, 6.0, [0.75, 4.0]) == 4.0 and C.bulb_scale("REAL", 18, 6, [0.75, 4]) == 1.0)
    check("place.NEG_bad_scale_mode", raises(lambda: C.bulb_scale("HUGE", 1, 1, [1, 2]), "BULB_SCALE_MODE"))


def t_housing():
    for name in C.LANTERNS:
        f = TABLE[name]
        size = C.housing_size(f, 1.0)
        throw = C._norm([0.3, -0.5, -0.8])
        light = [100.0, -360.0, 1100.0]
        h = C.housing_world(f, size, light, throw)
        check("housing.POS_uniform_scale_%s" % name, all(abs(s - 1.0) < 1e-3 for s in h["scale"]))
        front = [l + r for l, r in zip(h["location"], C.quat_rotate(h["rotation"], [f["bounds_max"][0],
                                                                                       (f["bounds_min"][1] + f["bounds_max"][1]) / 2,
                                                                                       (f["bounds_min"][2] + f["bounds_max"][2]) / 2]))]
        check("housing.POS_front_face_on_light_%s" % name, max(abs(a - b) for a, b in zip(front, light)) < 1e-3)
        lens_local = C.lens_offset_local(f, 1.0)
        lens_pred = [l + r for l, r in zip(light, C.quat_rotate(h["rotation"], lens_local))]
        check("housing.POS_lens_offset_consistent_%s" % name, max(abs(a - b) for a, b in zip(lens_pred, h["lens_world"])) < 1e-2)
    cube = C.housing_world(TABLE["SM_Lantern_Fresnel"], [45.0, 32.0, 32.0], [0, 0, 0], [1, 0, 0])
    check("housing.NEG_cube_size_squashes", max(cube["scale"]) / min(cube["scale"]) > 1.3)
    check("housing.choose_majority", C.choose_lantern({"TOP": 3, "LOW_SIDE": 5, "PRACTICAL": 9})[0] == C.ROLE_LANTERN["LOW_SIDE"])
    check("housing.choose_tie_top", C.choose_lantern({"TOP": 5, "LOW_SIDE": 5})[0] == C.ROLE_LANTERN["TOP"])
    check("housing.choose_override", C.choose_lantern({"TOP": 1}, "SM_Lantern_Birdie")[0] == "SM_Lantern_Birdie")
    check("housing.NEG_override_unknown", raises(lambda: C.choose_lantern({"TOP": 1}, "SM_Cube"), "HOUSING_LANTERN_UNKNOWN"))
    check("housing.NEG_only_practicals", raises(lambda: C.choose_lantern({"PRACTICAL": 4}), "NO_HOUSED_ROLE"))
    check("housing.NEG_scale_range", raises(lambda: C.housing_size(TABLE["SM_Lantern_Fresnel"], 9.0), "HOUSING_SCALE_RANGE"))


def _plan(p, **over):
    cues, unused = C.snapshot_cues(p, os.path.dirname(HERE))
    opts = dict(C.SWAP_DEFAULTS); opts.update(over)
    return cues, C.plan_passage(p, cues, C.offline_mesh_info(cues), TABLE, opts)


def t_plan_scope():
    for p in ("P03", "P05"):
        cues, plan = _plan(p)
        before = {c["guid"]: c["attachments"] for c in cues}
        rows = {r["guid"]: r for c in cues for r in c["attachments"]}
        touched = [b for t in plan["targets"] for b in t["bulbs"]] + [c for t in plan["targets"] for c in t["caps"]]
        check("plan.%s_has_targets" % p, plan["counts"]["bulbs"] > 0 and plan["counts"]["caps"] > 0)
        check("plan.%s_no_light_row_touched" % p, all(C.is_kind(rows[x["guid"]], "PROP") for x in touched))
        bad = []
        for t in plan["targets"]:
            for b in t["bulbs"]:
                d = {x["path"].split(".")[1] for x in C.row_differences(rows[b["guid"]], b["after"])}
                if not d <= {"mesh", "relative_transform"}:
                    bad.append((b["label"], d))
                if C.row_differences(rows[b["guid"]]["relative_transform"]["rotation_xyzw"], b["after"]["relative_transform"]["rotation_xyzw"]):
                    bad.append((b["label"], "rotation"))
            for c in t["caps"]:
                d = {x["path"] for x in C.row_differences(rows[c["guid"]], c["after"])}
                if d != {".enabled"}:
                    bad.append((c["label"], d))
        check("plan.%s_only_planned_fields" % p, not bad, str(bad[:3]))
        lamp_targets = [b for t in plan["targets"] for b in t["bulbs"] if "SM_Lamp_" in str(b["mesh_before"])]
        check("plan.%s_lamp_fixtures_never_targeted" % p, not lamp_targets
              and plan["counts"]["skipped"] == sum(1 for s in plan["skipped"] if s["why"] == "NOT_A_SPHERE_BULB"))
        want = C.expected_after(before, plan)
        check("scope.%s_POS_exact" % p, C.scope_problems(want, copy.deepcopy(want)) == [])
        noisy = copy.deepcopy(want)
        first = plan["targets"][0]["bulbs"][0]["guid"]
        for r in noisy[plan["targets"][0]["cue_guid"]]:
            if r["guid"] == first:
                r["relative_transform"]["location"][0] += 1e-5
        check("scope.%s_POS_float_noise_tolerated" % p, C.scope_problems(want, noisy) == [])
        light_guid = plan["targets"][0]["bulbs"][0]["light_guid"]
        moved = copy.deepcopy(want)
        for r in moved[plan["targets"][0]["cue_guid"]]:
            if r["guid"] == light_guid:
                r["relative_transform"]["location"][2] += 0.5
        check("scope.%s_NEG_light_moved" % p, raises(lambda: C.check_scope(want, moved, "t"), "SCOPE_CHANGED"))
        other = copy.deepcopy(want)
        untouched = next(g for g in other if g not in {t["cue_guid"] for t in plan["targets"]}) if len(other) > len(plan["targets"]) else None
        if untouched is None:
            untouched = plan["targets"][-1]["cue_guid"]
            other[untouched][0]["enabled"] = not other[untouched][0]["enabled"]
        else:
            other[untouched][0]["label"] += "x"
        check("scope.%s_NEG_other_row_changed" % p, raises(lambda: C.check_scope(want, other, "t"), "SCOPE_CHANGED"))
        reordered = copy.deepcopy(want)
        cue = plan["targets"][0]["cue_guid"]
        reordered[cue] = list(reversed(reordered[cue]))
        check("scope.%s_NEG_reordered" % p, raises(lambda: C.check_scope(want, reordered, "t"), "SCOPE_CHANGED"))
        unchanged_apply = copy.deepcopy(before)
        check("scope.%s_NEG_write_missing" % p, raises(lambda: C.check_scope(want, unchanged_apply, "t"), "SCOPE_CHANGED"))
        # revert
        rec = {"after_rows": {t["cue_guid"]: want[t["cue_guid"]] for t in plan["targets"]},
               "before_rows": {t["cue_guid"]: before[t["cue_guid"]] for t in plan["targets"]}}
        model = C.revert_model(rec, want)
        check("revert.%s_POS_restores_before" % p, C.scope_problems(before, model) == [])
        drift = copy.deepcopy(want)
        for r in drift[cue]:
            if r["guid"] == first:
                r["relative_transform"]["location"][1] += 3.0
        check("revert.%s_NEG_drift_refused" % p, raises(lambda: C.revert_model(rec, drift), "REVERT_DRIFT"))
        sha1, sha2 = C.plan_sha(plan), C.plan_sha(_plan(p)[1])
        check("plan.%s_sha_stable" % p, sha1 == sha2)
        check("plan.%s_NEG_sha_moves_with_seed" % p, C.plan_sha(_plan(p, bulb_seed="x")[1]) != sha1)
        check("plan.%s_NEG_no_caps_when_disabled" % p, _plan(p, disable_caps=False)[1]["counts"]["caps"] == 0)
        body_plan = _plan(p, bulb_anchor="BODY")[1]
        check("plan.%s_body_anchor_keeps_glass_centre" % p, all(
            max(abs(a - b) for a, b in zip(C.old_glass(rows[x["guid"]], C.PLAIN_SPHERE_BOUNDS)[0],
                                          [l + r for l, r in zip(x["after"]["relative_transform"]["location"],
                                                                 C.quat_rotate(x["after"]["relative_transform"]["rotation_xyzw"],
                                                                               [c * x["scale"] for c in TABLE[x["variant"]]["glass_centre"]]))])) < 1e-3
            for t in body_plan["targets"] for x in t["bulbs"]))
    cues, plan = _plan("P03")
    derived = plan["derived_meshes"]
    check("plan.P03_derived_slot0_is_old_mi", derived and all(v["slot0"].startswith("/Game/") for v in derived.values()))
    check("plan.derived_name_stable", C.derived_mesh_path("SM_Bulb_A60_Opal", "/Game/X/MI_A") ==
          C.derived_mesh_path("SM_Bulb_A60_Opal", "/Game/X/MI_A.MI_A")
          and C.derived_mesh_path("SM_Bulb_A60_Opal", "/Game/X/MI_A") != C.derived_mesh_path("SM_Bulb_A60_Opal", "/Game/X/MI_B"))
    # a body whose Body.light_attachment_guid names another light is refused, not re-paired
    cue = copy.deepcopy(cues[0])
    body = next(r for r in cue["attachments"] if r["label"].endswith("_BODY") and "/SM_Lamp_" not in str(r["mesh"]))
    body["ext"] = {"body": {"light_attachment_guid": "F" * 32}}
    p2 = C.plan_passage("P03", [cue], C.offline_mesh_info([cue]), TABLE, dict(C.SWAP_DEFAULTS))
    check("plan.NEG_body_follows_other_light", any(s["why"] == "BODY_FOLLOWS_ANOTHER_LIGHT" for s in p2["skipped"]))


def t_swap_args():
    a = SWP["check_args"]
    a.__globals__["C"] = C      # runpy returns a copy of the globals; the functions keep the live dict
    C2 = C
    check("swaparg.POS_dry", a({"mode": "DRY", "passage": "p03"}, C2)["passage"] == "P03")
    check("swaparg.NEG_no_passage", raises(lambda: a({"mode": "DRY"}, C2), "PASSAGE_INVALID"))
    check("swaparg.NEG_confirm", raises(lambda: a({"mode": "APPLY", "passage": "P03", "confirm": "APPLY MESHYSWAP P04",
                                                   "plan_sha256": "a" * 64}, C2), "CONFIRM_MISSING"))
    check("swaparg.NEG_no_sha", raises(lambda: a({"mode": "APPLY", "passage": "P03", "confirm": "APPLY MESHYSWAP P03"}, C2),
                                       "APPLY_NEEDS_PLAN_SHA256"))
    check("swaparg.POS_apply", a({"mode": "APPLY", "passage": "P03", "confirm": "APPLY MESHYSWAP P03",
                                  "plan_sha256": "a" * 64}, C2)["mode"] == "APPLY")
    check("swaparg.NEG_unknown", raises(lambda: a({"mode": "DRY", "passage": "P03", "colour": 1}, C2), "ARGS_UNKNOWN"))
    check("swaparg.NEG_housing", raises(lambda: a({"mode": "DRY", "passage": "P03", "housing": "SM_Cube"}, C2), "HOUSING_INVALID"))
    check("swaparg.NEG_pool", raises(lambda: a({"mode": "DRY", "passage": "P03", "bulb_pool": ["SM_Cube"]}, C2), "BULB_POOL_INVALID"))
    SWP["C"] = C
    globals_ok = True
    try:
        SWP["check_pins"]({"counts": {"bulbs": 17, "caps": 17}}, {"expected_bulbs": 17, "expected_caps": None})
    except Exception:  # noqa: BLE001
        globals_ok = False
    check("swaparg.POS_pins", globals_ok)
    # check_pins reads the module's C; give it ours
    SWP["check_pins"].__globals__["C"] = C
    check("swaparg.NEG_pin_mismatch", raises(lambda: SWP["check_pins"]({"counts": {"bulbs": 17, "caps": 17}},
                                                                        {"expected_bulbs": 16, "expected_caps": None}), "PIN_BULBS"))
    SWP["check_import_record"].__globals__["C"] = C
    plan = {"targets": [{"bulbs": [{"variant": "SM_Bulb_A60_Opal"}]}], "housing": {"mode": "STRUCTURE", "lantern": "SM_Lantern_Fresnel"}}
    check("swap.NEG_import_missing", raises(lambda: SWP["check_import_record"]({"fixtures": {"SM_Bulb_A60_Opal": {"status": "saved_readback_verified"}}}, plan),
                                            "FIXTURES_NOT_IMPORTED"))
    check("swap.POS_import_ok", SWP["check_import_record"]({"fixtures": {n: {"status": "saved_readback_verified"} for n in ("SM_Bulb_A60_Opal", "SM_Lantern_Fresnel")}}, plan)
          == ["SM_Bulb_A60_Opal", "SM_Lantern_Fresnel"])
    SWP["check_apply_gate"].__globals__["C"] = C
    tmp = tempfile.NamedTemporaryFile(delete=False); tmp.close()
    check("swap.NEG_active_record", raises(lambda: SWP["check_apply_gate"](tmp.name, []), "ACTIVE_RECORD_EXISTS"))
    os.unlink(tmp.name)
    check("swap.NEG_unacked", raises(lambda: SWP["check_apply_gate"](tmp.name, ["x.json"]), "FOREIGN_ACTIVE_RECORDS_OVERLAP"))
    check("swap.POS_gate_clear", SWP["check_apply_gate"](tmp.name, []) is None)
    check("ack.POS_and_NEG", C.check_ack([{"path": "a"}, {"path": "b"}], ["a"]) == ["b"] and C.check_ack([{"path": "a"}], ["a"]) == [])
    check("role.parse", C.role_of("P01 SCORE B03 X LOW_SIDE_L_KEY") == "LOW_SIDE" and C.role_of("P03 SCORE B01 X TOP_L") == "TOP"
          and C.role_of("P04 WINDOW SHADOW W003") == "OTHER" and C.role_of("P05 SCORE B01 X PRACTICAL_BULB_DEAD") == "PRACTICAL")


def main():
    for fn in (t_table, t_import_gates, t_import_plan, t_variant, t_bulb_placement, t_housing, t_plan_scope, t_swap_args):
        try:
            fn()
        except Exception as error:  # noqa: BLE001 - a crashing group is a failure, not a skip
            RESULTS.append((fn.__name__ + ".CRASH", False, "%s: %s" % (type(error).__name__, error)))
    fails = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        if not ok or detail:
            print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))
    print("MESHYFIX_HARNESS|pass=%d|fail=%d" % (len(RESULTS) - len(fails), len(fails)))
    return not fails


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
