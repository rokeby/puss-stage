"""Offline +/- controls for Job 179 P02 trim. No Unreal/MCP/PIE."""
import copy
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("p02_trim", os.path.join(HERE, "p02_trim.py"))
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        print("FAIL|" + name)


def rejects(name, fn, token):
    try:
        fn()
    except Exception as error:
        check(name, token in str(error))
    else:
        check(name, False)


def light(guid, label, intensity=2000.0, scatter=4.0):
    return {"guid": guid, "label": label, "kind": "LIGHT", "enabled": True,
            "lighting": {"intensity": intensity, "volumetric_scattering_intensity": scatter,
                         "cast_shadows": True, "cast_volumetric_shadow": True},
            "effect": {}}


def haze(guid, density=0.30):
    return {"guid": guid, "label": "P02 Haze Pot", "kind": "EFFECT", "enabled": True,
            "lighting": {}, "effect": {"type": "HAZE", "feeds_local_medium": True,
                                         "medium_density": density}}


rows = []
for ordinal in range(1, 21):
    attachments = [light("B%02d" % ordinal, "P02 SCORE B%02d BEAM_R" % ordinal)]
    if ordinal == 1:
        attachments += [haze("HAZE1"), light("PRACT1", "P02 B01 PRACTICAL_CLAMP", 500.0, 1.0)]
    attachments.append({"guid": "PROP%02d" % ordinal, "label": "Parcan body", "kind": "PROP",
                        "enabled": True, "lighting": {}, "effect": {}})
    rows.append({"guid": "CUE%02d" % ordinal, "show_index": ordinal, "attachments": attachments})

args = T.check_args({})
plan = T.build_plan(copy.deepcopy(rows), args, {"HAZE1": {"density": 0.10, "record": "old.json", "record_run": "OLD"}})
check("positive one haze found", plan["counts"]["haze_effects"] == 1)
check("positive pre-copy and half both reported", plan["density_report"][0]["pre_p01_copy_density"] == 0.10
      and plan["density_report"][0]["half_density"] == 0.15)
check("positive safer half chosen", plan["density_report"][0]["chosen_density"] == 0.15)
check("positive four hero beams", plan["counts"]["hero_beams"] == 4)
check("positive most beams zeroed", plan["counts"]["zeroed_beams"] == 16)
check("positive rig light retained low", plan["counts"]["low_rig_lights"] == 1)
check("positive attachment count unchanged", plan["counts"]["attachments_enabled_before"] == plan["counts"]["attachments_enabled_after"])
check("positive plan hash", len(plan["plan_sha256"]) == 64)
nonheroes = [x for x in plan["changes"] if x["guid"].startswith("B") and x["ordinal"] not in T.HERO_ORDINALS]
check("positive nonhero beams keep enabled out of patch", all("enabled" not in x["after"] for x in nonheroes))
check("positive nonhero scatter zero", all(x["after"]["lighting"]["volumetric_scattering_intensity"] == 0.0 for x in nonheroes))
check("positive props never changed", not any(x["guid"].startswith("PROP") for x in plan["changes"]))

fallback = T.build_plan(copy.deepcopy(rows), args, {})
check("positive no baseline uses half", fallback["density_report"][0]["chosen_density"] == 0.15)
rejects("negative apply needs exact confirm", lambda: T.check_args({"mode": "APPLY", "expected_changes": 1,
                                                                    "expected_plan_sha256": "a" * 64}), "CONFIRM_MISSING")
rejects("negative apply needs expected count", lambda: T.check_args({"mode": "APPLY", "confirm": "APPLY P02TRIM",
                                                                      "expected_plan_sha256": "a" * 64}), "EXPECTED_CHANGES")
rejects("negative wrong heroes", lambda: T.check_args({"hero_ordinals": [1]}), "HERO_ORDINALS")
rejects("negative no haze", lambda: T.build_plan(rows[1:], args, {}), "NO_P02_HAZE")
rejects("negative too few beams", lambda: T.build_plan([rows[0]], args, {}), "NOT_ENOUGH")

perf_ok = T.evaluate_perf({"05": 40, "20": 42, "35": 39}, {"05": 42, "20": 43, "35": 40})
check("positive p02 perf passes", perf_ok["pass"] and perf_ok["auto_revert"] is False)
perf_bad = T.evaluate_perf({"05": 40, "20": 40, "35": 40}, {"05": 45, "20": 40, "35": 40})
check("negative p02 perf fails without auto revert", not perf_bad["pass"] and perf_bad["auto_revert"] is False)
rejects("negative p02 perf needs three spots", lambda: T.evaluate_perf({"a": 1}, {"a": 1}), "THREE")

source = open(os.path.join(HERE, "p02_trim.py"), encoding="utf-8").read()
check("static backup before mutation", source.index('"PreP02Trim-"') < source.index('mutate(show, plan, "after")'))
check("static nested attachment writeback", "P._set_pair_attachments(show, index, attachments)" in source)
check("static no actor delete", "destroy_actor" not in source and "delete_asset" not in source)
check("static markers", all(x in source for x in ("_DRY_OK", "_APPLY_OK", "_REVERT_OK")))

print("P02_TRIM_OFFLINE_HARNESS|passed=%d|failed=%d" % (passed, failed))
raise SystemExit(1 if failed else 0)
