"""Offline positive and required negative controls for s3_daylight_apply.py."""
import copy
import sys

from s3_daylight_apply import (DAYLIGHT_LABELS, EXPOSURE_LABEL, LINER_LABELS,
                               PlanError, STRIKE_LABELS, plan_daylight)


def fixture():
    strike = []
    for index, label in enumerate(STRIKE_LABELS):
        strike.append({"label": label, "binding_guid": "strike-%d" % index,
                       "keys": [[0.0, 0.0], [10.0, 0.0], [10.2, 4000.0 if index == 0 else 1000.0]]})
    rig = []
    for index in range(14):
        rig.append({"label": "S3 Practical L%d" % (index + 1), "binding_guid": "p-%d" % index,
                    "keys": [[0.0, 0.0], [10.0, 0.0], [10.2, 400.0]]})
    for index in range(3):
        rig.append({"label": "S3 Uplight %d" % (index + 1), "binding_guid": "u-%d" % index,
                    "keys": [[0.0, 0.0], [10.0, 0.0], [10.2, 10000.0]]})
    return {
        "strike_lights": strike, "rig_lights": rig, "strike_seconds": 10.0,
        "existing_labels": list(STRIKE_LABELS) + [EXPOSURE_LABEL] + list(LINER_LABELS),
        "exposure": {"label": EXPOSURE_LABEL, "fixed": True, "ev100": 0.5, "blend_weight": 1.0},
        "liner_materials": [{"label": label, "material_path": "/Game/MarbleMI"} for label in LINER_LABELS],
        "material_profile": {"is_material_instance": True, "has_normal_texture": True,
                             "has_roughness_response": True, "edits_shared_master": False,
                             "normal_scalar_names": [], "roughness_scalar_names": []},
    }


def reject(name, fn, contains):
    try:
        fn()
    except PlanError as exc:
        if contains not in str(exc):
            print("FAIL negative %s: wrong refusal %s" % (name, exc))
            return 1
        print("PASS negative %s: STOP observed as required" % name)
        return 0
    print("FAIL negative %s: invalid plan accepted" % name)
    return 1


def main():
    failures = 0
    state = fixture()
    plan = plan_daylight(state)
    positive = (
        len(plan["strike_lights"]) == 6 and len(plan["new_lights"]) == 2 and
        all([key[0] for key in row["before_keys"]] == [key[0] for key in row["after_keys"]]
            for row in plan["strike_lights"] + plan["rig_lights"]) and
        all(abs(row["after_keys"][-1][1] - row["before_keys"][-1][1] * 0.4) < 1e-9
            for row in plan["strike_lights"] + plan["rig_lights"]) and
        [row["label"] for row in plan["new_lights"]] == list(DAYLIGHT_LABELS) and
        all(row["keys"][:2] == [[0.0, 0.0], [10.0, 0.0]] for row in plan["new_lights"]) and
        plan["exposure"]["after_ev100"] == 2.0 and plan["material"]["action"] == "reuse"
    )
    if positive:
        print("PASS positive: six strike + rig keys scale to 40%, times preserved, two daylight lights, fixed EV100")
    else:
        print("FAIL positive: %r" % plan)
        failures += 1

    bad = copy.deepcopy(state); bad["strike_lights"].pop()
    failures += reject("missing strike light", lambda: plan_daylight(bad), "exactly the six")
    bad = copy.deepcopy(state); bad["strike_seconds"] = 9.0
    failures += reject("strike moved from +10 s", lambda: plan_daylight(bad), "not +10 s")
    bad = copy.deepcopy(state); bad["exposure"]["fixed"] = False
    failures += reject("auto exposure", lambda: plan_daylight(bad), "not currently fixed")
    bad = copy.deepcopy(state); bad["existing_labels"].append(DAYLIGHT_LABELS[0])
    failures += reject("label collision", lambda: plan_daylight(bad), "already exist")
    bad = copy.deepcopy(state); bad["material_profile"].update({"has_normal_texture": False,
                                                                  "has_roughness_response": False})
    failures += reject("flat untunable marble", lambda: plan_daylight(bad), "flat marble")
    bad = copy.deepcopy(state); bad["rig_lights"][0]["label"] = "S4 Practical L1"
    failures += reject("out of scope rig light", lambda: plan_daylight(bad), "out-of-scope")

    tune = copy.deepcopy(state)
    tune["material_profile"].update({"has_roughness_response": False,
                                      "roughness_scalar_names": ["Roughness"]})
    if plan_daylight(tune)["material"]["action"] != "copy_tune":
        print("FAIL positive copy-tune: flat tunable MI did not select copy")
        failures += 1
    else:
        print("PASS positive copy-tune: S3-only MI copy selected; shared master untouched")
    if failures == 0:
        print("S3_DAYLIGHT_HARNESS_OK|positive=2|negative=6|scale=0.40|strike_s=10.0|new_lights=2")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
