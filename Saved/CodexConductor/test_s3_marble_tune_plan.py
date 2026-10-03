"""Offline positive and negative controls for s3_marble_tune.py."""
import copy
import sys

from s3_marble_tune import (COPY_MI_PATH, LINER_LABELS, PlanError,
                            luminance_summary, plan_marble_tune,
                            validate_luminance_pair)


SOURCE = "/Game/Fab/Megascans/3D/Roman_Marble_Plinth/Materials/MI_Source"


def fixture():
    return {"liners": [{"label": label, "material_path": SOURCE} for label in LINER_LABELS],
            "target_exists": False,
            "profile": {"is_material_instance": True,
                        "scalar_names": ["Brightness", "Min Roughness", "Max Roughness", "Normal Intensity"],
                        "vector_names": ["BaseColor Tint"],
                        "texture_names": ["BaseColorTexture", "NormalTexture", "MetallicRoughnessTexture"]}}


def reject(name, function, contains):
    try:
        function()
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
    plan = plan_marble_tune(fixture())
    if (plan["copy_mi_only"] and not plan["shared_master_mutated"] and
            plan["target"] == COPY_MI_PATH and plan["parameters"]["Brightness"] == 0.70 and
            plan["parameters"]["Min Roughness"] == 0.28 and
            plan["parameters"]["Max Roughness"] == 0.38 and
            plan["pie_luminance"]["status"] == "REQUIRED_AFTER_APPLY"):
        print("PASS positive: S3-only copy MI, darker albedo response, 0.28-0.38 roughness, PIE gate explicit")
    else:
        print("FAIL positive: %r" % plan)
        failures += 1

    before = luminance_summary([(1.0, 0.95, 0.90), (0.96, 0.90, 0.84), (0.80, 0.76, 0.72)])
    after = luminance_summary([(0.88, 0.82, 0.76), (0.82, 0.77, 0.71), (0.65, 0.61, 0.57)])
    measured = validate_luminance_pair(before, after)
    if measured["after"]["max"] < 1.0 and measured["p95_reduction"] > 0.0:
        print("PASS positive luminance contract: after below clipping and p95 reduced")
    else:
        failures += 1

    bad = fixture(); bad["target_exists"] = True
    failures += reject("copy MI collision", lambda: plan_marble_tune(bad), "already exists")
    bad = fixture(); bad["profile"]["is_material_instance"] = False
    failures += reject("shared master source", lambda: plan_marble_tune(bad), "not a MaterialInstanceConstant")
    bad = fixture(); bad["profile"]["scalar_names"].remove("Brightness")
    failures += reject("no albedo control", lambda: plan_marble_tune(bad), "Brightness")
    bad = fixture(); bad["profile"]["scalar_names"].remove("Max Roughness")
    failures += reject("no roughness maximum", lambda: plan_marble_tune(bad), "Max Roughness")
    bad = fixture(); bad["profile"]["texture_names"].remove("NormalTexture")
    failures += reject("no normal response", lambda: plan_marble_tune(bad), "normal")
    failures += reject("after still clips",
                       lambda: validate_luminance_pair(before,
                           luminance_summary([(1.0, 1.0, 1.0)] * 3)),
                       "still clips")
    if failures == 0:
        print("S3_MARBLE_TUNE_HARNESS_OK|positive=2|negative=6|copy_mi_only=1|roughness=0.28..0.38|luminance_gate=1")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
