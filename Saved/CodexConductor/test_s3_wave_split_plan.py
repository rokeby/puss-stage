"""Offline positive and required negative controls for s3_wave_split_apply.py."""
import copy
import pathlib
import sys

from s3_wave_split_apply import (PIECE_WIDTH_CM, PlanError, TARGET_LABELS,
                                 VAMP_RANGE, compute_strike_frame, plan_wave_split)


def fixture():
    widths = {
        "S3 Wave Row1 A": 1431.7, "S3 Wave Row1 B": 1627.5,
        "S3 Wave Row2 A": 1531.9, "S3 Wave Row2 B": 1460.8,
        "S3 Wave Row3 A": 1833.4, "S3 Wave Row3 B": 1439.2,
    }
    actors = [{"label": label, "actor_path": "/Game/Test.%s" % label.replace(" ", "_"),
               "parent_label": "S3 Hangar Root", "transform_track_count": 1,
               "landed_width_cm": widths[label], "tool_owned": False,
               "landed_origin_dock_cm": [3700.0 + 800.0 * ((int(label[11]) - 1)), 0.0, 115.0]}
              for label in TARGET_LABELS]
    return {"fps": 24.0, "playback": [0, 6240],
            "strike": compute_strike_frame(24.0, 30.0, 0, 0, 300, 1.0),
            "actors": actors, "existing_labels": list(TARGET_LABELS)}


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
    plan = plan_wave_split(fixture())
    phases = {(piece["row"], piece["phase_delay_frames"]) for piece in plan["pieces"]}
    positive = (
        plan["piece_count"] == 9 and plan["period_frames"] == 360 and plan["period_seconds"] == 15.0 and
        plan["piece_width_fraction"] == 0.60 and plan["worst_gap_cm"] == 0.0 and
        plan["inside_box_guard"] and plan["max_controlled_overhang_cm"] <= 200.0 and
        all(piece["target_width_cm"] == PIECE_WIDTH_CM for piece in plan["pieces"]) and
        all(piece["seam_error_cm"] <= 0.01 for piece in plan["pieces"]) and
        all(piece["keys"][0][0] == 239 and piece["keys"][-1][0] == 6240 for piece in plan["pieces"]) and
        len(phases) == 9 and plan["vamp_range"] == list(VAMP_RANGE)
    )
    if positive:
        print("PASS positive: 3 rows x 3 pieces, 60% width, overlap cover, independent phases, 15 s seam")
    else:
        print("FAIL positive: %r" % plan)
        failures += 1

    bad = fixture(); bad["actors"].pop()
    failures += reject("missing original", lambda: plan_wave_split(bad), "exactly the six")
    bad = fixture(); bad["actors"][0]["transform_track_count"] = 0
    failures += reject("original track absent", lambda: plan_wave_split(bad), "exactly one original")
    bad = fixture(); bad["actors"][0]["parent_label"] = "World"
    failures += reject("wrong parent", lambda: plan_wave_split(bad), "not attached")
    bad = fixture(); bad["strike"]["frame"] = 216
    failures += reject("old six-second strike", lambda: plan_wave_split(bad), "not +10 s")
    bad = fixture(); bad["existing_labels"].append("S3 Wave Split Row1 Piece1")
    failures += reject("label collision", lambda: plan_wave_split(bad), "already exist")
    bad = fixture(); bad["actors"][0]["landed_width_cm"] = 0.0
    failures += reject("missing landed width", lambda: plan_wave_split(bad), "no usable landed width")
    bad = fixture(); bad["actors"][0]["landed_origin_dock_cm"][0] = -6500.0
    failures += reject("rest-pose/outside-box source", lambda: plan_wave_split(bad), "outside the live landed")
    failures += reject("bad mapped strike",
                       lambda: compute_strike_frame(24.0, 30.0, 0, 0, 270, 1.0),
                       "not the mapped +10 s")
    source = pathlib.Path(__file__).with_name("s3_wave_split_apply.py").read_text(encoding="utf-8")
    if "actor.is_hidden()" in source or 'get_editor_property("hidden")' not in source:
        print("FAIL UE 5.8 visibility contract: unsupported actor read remains")
        failures += 1
    else:
        print("PASS UE 5.8 visibility contract: Actor.hidden + component visibility read-back")
    if failures == 0:
        print("S3_WAVE_SPLIT_HARNESS_OK|positive=2|negative=8|pieces=9|period_frames=360|seam=3480/4200|worst_gap_cm=0|ue58_visibility=1")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
