"""Offline positive and required negative controls for the S3 ClamCam cut tool."""
import copy
import sys

from s3_remove_root_clamcam_cut import PlanError, plan_removal


def valid_match():
    return {
        "range": [81, 1501],
        "active": False,
        "binding_guid": "11111111-2222-3333-4444-555555555555",
        "binding_exists": True,
    }


def fixture_state():
    return {"matches": [valid_match()]}


def expect_failure(name, function):
    try:
        function()
    except PlanError:
        print("PASS negative %s: FAIL observed as required" % name)
        return 0
    print("FAIL negative %s: invalid case was accepted" % name)
    return 1


def main():
    failures = 0
    plan = plan_removal(fixture_state())
    if plan["range"] == [81, 1501] and not plan["active"] and \
            plan["operations"] == [{"op": "remove_section", "target": "root ClamCam1 cut"}]:
        print("PASS positive: deterministic root ClamCam1 removal plan is valid")
    else:
        print("FAIL positive: unexpected plan %r" % plan)
        failures += 1

    two = copy.deepcopy(fixture_state())
    two["matches"].append(copy.deepcopy(two["matches"][0]))
    failures += expect_failure("two matches", lambda: plan_removal(two))

    active = copy.deepcopy(fixture_state())
    active["matches"][0]["active"] = True
    failures += expect_failure("active section", lambda: plan_removal(active))

    wrong_range = copy.deepcopy(fixture_state())
    wrong_range["matches"][0]["range"] = [81, 1500]
    failures += expect_failure("wrong range", lambda: plan_removal(wrong_range))

    if failures == 0:
        print("S3_CLAMCUT_HARNESS_OK|positive=1|negative=3")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
