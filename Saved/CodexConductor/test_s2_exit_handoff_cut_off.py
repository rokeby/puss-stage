"""Offline positive and negative controls for s2_exit_handoff_cut_off.py."""
import copy
import sys

from s2_exit_handoff_cut_off import PlanError, plan_change


def fixture():
    return {
        "root_cuts": [
            {"section_index": 0, "range": [0, 3866], "active": True,
             "binding_guid": "AAAA", "camera": "Scene 2 Main Camera"},
            {"section_index": 1, "range": [3866, 3891], "active": True,
             "binding_guid": "BBBB",
             "camera": "Scene 2 \u2014 External Sound \u2014 Exit Handoff Camera"},
        ],
        "nested_coverage": [
            {"track_index": 3, "section_index": 0, "track_class": "MovieSceneSubTrack",
             "range": [0, 3892], "active": True,
             "sequence": "/Game/InfinityStage/KlaraHookin/LS_NEW_SHRINE_S2Hangar",
             "final_camera": "CineCameraActor2"},
        ],
    }


def rejected(name, value):
    try:
        plan_change(value)
    except PlanError:
        print("PASS negative: " + name)
        return 0
    print("FAIL negative: " + name)
    return 1


def main():
    failures = 0
    plan = plan_change(fixture())
    if plan["operation"] == "set_is_active(False)" and plan["target"]["binding_guid"] == "BBBB":
        print("PASS positive: exact name/range target and nested coverage")
    else:
        print("FAIL positive: %r" % plan)
        failures += 1

    value = fixture(); value["root_cuts"].append(copy.deepcopy(value["root_cuts"][1]))
    failures += rejected("root cut count drift", value)
    value = fixture(); value["root_cuts"][1]["range"] = [3866, 3892]
    failures += rejected("target range drift", value)
    value = fixture(); value["root_cuts"][1]["camera"] = "wrong camera"
    failures += rejected("target name drift", value)
    value = fixture(); value["root_cuts"][1]["active"] = False
    failures += rejected("already inactive", value)
    value = fixture(); value["nested_coverage"][0]["final_camera"] = "wrong nested camera"
    failures += rejected("nested camera drift", value)
    value = fixture(); value["nested_coverage"][0]["range"][1] = 3891
    failures += rejected("nested coverage drift", value)

    if failures == 0:
        print("S2_EXIT_CUT_HARNESS_OK|positive=1|negative=6")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
