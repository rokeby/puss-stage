"""Offline positive/negative harness for P28.  No Unreal import is required."""
import importlib.util
import json
import math
import os
import random
import traceback


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("s3_polish_tested", os.path.join(HERE, "s3_polish.py"))
T = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(T)


checks = []


def check(name, condition, detail=None, control="positive"):
    ok = bool(condition)
    checks.append({"name": name, "ok": ok, "control": control, "detail": detail})
    if not ok:
        raise AssertionError("%s|%r" % (name, detail))


def rejects(name, function, contains, control="negative"):
    try:
        function()
    except Exception as exc:  # noqa: BLE001 - refusal is the control
        check(name, contains in str(exc), str(exc), control)
        return
    check(name, False, "did not reject", control)


class FakeFrameNumber:
    def __init__(self, value):
        self.value = int(value)


class FakeTime:
    def __init__(self, frame):
        self.frame_number = FakeFrameNumber(frame)
        self.sub_frame = 0.0


class FakeKey:
    def __init__(self, frame, value):
        self.frame = int(frame)
        self.value = value

    def get_time(self, time_unit=None):
        del time_unit
        return FakeTime(self.frame)

    def get_value(self):
        return self.value


class FakeChannel:
    def __init__(self, rows):
        self.keys = [FakeKey(*row) for row in rows]

    def get_keys(self):
        return list(self.keys)

    def remove_key(self, key):
        self.keys.remove(key)

    def add_key(self, frame, value, **kwargs):
        del kwargs
        key = FakeKey(frame.value, value)
        self.keys.append(key)
        return key


class FakeUE:
    class MovieSceneTimeUnit:
        DISPLAY_RATE = "display"

    class MovieSceneKeyInterpolation:
        LINEAR = "linear"

    FrameNumber = FakeFrameNumber


def main():
    # Args / independent part controls.
    p = T.merged_params({})
    check("P01.defaults", (p["common_ignite_frame"], p["fire_ramp_frames"], p["b11_factor"],
                           p["b11_ramp_frames"], p["stylish_apply"]) == (230, 72, 0.25, 24, False))
    check("P02.partial_stylish_merge", len(T.merged_params({"stylish_systems": {"S3 Fire B": "/X"}})["stylish_systems"]) == 4)
    check("P03.parts", T.selected_parts(["fires_together", "dune_shadow"]) == ["fires_together", "dune_shadow"])
    rejects("N01.bad_factor", lambda: T.merged_params({"b11_factor": 1.1}), "B11_DIM_RANGE")
    rejects("N02.bad_fire_ramp", lambda: T.merged_params({"fire_ramp_frames": 0}), "FIRE_TIMING_RANGE")
    rejects("N03.duplicate_parts", lambda: T.selected_parts(["b11_dim", "b11_dim"]), "PARTS")
    rejects("N04.unknown_part", lambda: T.selected_parts(["not_a_part"]), "PARTS")
    rejects("N05.bad_candidate", lambda: T.merged_params({"b11_dim_labels": ["Other"]}), "B11_DIM_LABEL_NOT_CANDIDATE")

    # Fire B/C retime and slow envelope.
    source = [[0, 0.0], [260, 0.0], [284, 100.0], [302, 120.0], [332, 90.0], [6240, 110.0]]
    fire = T.fire_key_plan(source, 260, 230, 72)
    check("P04.fire_delta", fire["delta"] == -30)
    check("P05.fire_baseline_untouched", fire["after"][0] == [0, 0.0])
    check("P06.fire_ignite_shift", [230, 0.0] in fire["after"])
    check("P07.fire_first_flicker_envelope", abs(dict(fire["after"])[254] - 100.0 / 3.0) < 1.0e-9)
    check("P08.fire_envelope_full", abs(dict(fire["after"])[302] - 90.0) < 1.0e-9)
    check("P09.fire_every_move_recorded", len(fire["moved"]) == len(source) - 1)
    cfire = T.fire_key_plan([[0, 0], [290, 0], [314, 90], [362, 80]], 290, 230, 72)
    check("P10.fire_c_delta", cfire["delta"] == -60 and dict(cfire["after"])[302] == 80.0)
    rejects("N06.fire_missing_ignite", lambda: T.fire_key_plan([[0, 0], [261, 0]], 260, 230, 72), "FIRE_IGNITION_KEY_MISSING")
    rejects("N07.duplicate_key", lambda: T.fire_key_plan([[260, 0], [260, 1]], 260, 230, 72), "DUPLICATE_KEY_FRAME")

    vis = T.visibility_key_plan([[0, False], [290, True]], 290, 230)
    check("P11.visibility_visible_polarity", vis["after"] == [[0, False], [230, True]])
    check("P12.visibility_move_record", vis["moved"] == [{"old_frame": 290, "new_frame": 230, "value": True}])
    rejects("N08.visibility_multiple_shows", lambda: T.visibility_key_plan([[0, False], [290, True], [300, True]], 290, 230),
            "VISIBILITY_IGNITION_KEYS")

    # B11-only dim: inserted exact boundaries and restoration.
    wave_source = [[5180, 100.0], [5182, 120.0], [5204, 80.0], [5206, 100.0], [6240, 60.0]]
    wave = T.b11_dim_plan(wave_source, 5181, 6253, 0.25, 24)
    values = dict(wave["after"])
    check("P13.b11_start_insert", abs(values[5181] - 110.0) < 1.0e-9)
    check("P14.b11_full_factor", abs(values[5205] - 22.5) < 1.0e-9)
    check("P15.b11_inside_dim", abs(values[6240] - 15.0) < 1.0e-9)
    check("P16.b11_end_restores", abs(values[6253] - 60.0) < 1.0e-9)
    check("P17.b11_pre_cut_untouched", values[5180] == 100.0)
    rejects("N09.b11_ramp_outside", lambda: T.b11_dim_plan(wave_source, 5181, 5200, 0.25, 24), "B11_RAMP_OUTSIDE_CUT")

    # Camera-space ranking and deterministic inferred selector.
    camera = {"location": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]}
    positions = {"R2": [100, -30, 0], "R3": [200, -20, 0], "R4": [300, -10, 0]}
    ranking = T.rank_candidates(camera, positions)
    chosen, source_name = T.choose_b11_labels(ranking, dict(p, b11_candidate_labels=list(positions), b11_dim_labels=[]))
    check("P18.rank_left", [row["left_depth_rank"] for row in ranking] == [1, 2, 3])
    check("P19.second_left", chosen == ["R3"] and source_name == "inferred.second_left")
    chosen2, source2 = T.choose_b11_labels(ranking, dict(p, b11_candidate_labels=list(positions), b11_dim_labels=["R4"]))
    check("P20.explicit_override", chosen2 == ["R4"] and source2 == "args.b11_dim_labels")
    rejects("N10.second_left_missing", lambda: T.choose_b11_labels(T.rank_candidates(camera, {"R": [100, -1, 0]}), p),
            "B11_SECOND_LEFT_UNRESOLVED")
    rejects("N11.explicit_empty", lambda: T.choose_b11_labels(ranking, dict(p, b11_selection="explicit", b11_dim_labels=[])),
            "B11_EXPLICIT_SELECTION_EMPTY")

    # UE transform convention copied from the measured waves tool.
    point = T.transform_point({"location": [10, 20, 30], "rotation": [0, 0, 90], "scale": [1, 1, 1]}, [100, 0, 0])
    check("P21.transform_yaw", max(abs(a - b) for a, b in zip(point, [10, 120, 30])) < 1.0e-9)
    matrix = T.rot_matrix([0, 0, 0])
    check("P22.identity_matrix", matrix == ((1.0, 0.0, 0.0), (0.0, 1.0, -0.0), (-0.0, 0.0, 1.0)))

    # Numeric read-back and seeded mutation controls.
    check("P23.float_tolerance", not T.numeric_diff({"v": 1.0}, {"v": 1.00005}, tolerance=0.0001))
    check("N12.float_drift", bool(T.numeric_diff({"v": 1.0}, {"v": 1.001}, tolerance=0.0001)), control="negative")
    check("N13.key_frame_drift", bool(T.numeric_diff(fire["after"], [row[:] for row in fire["after"][:-1]] + [[999, 1]],
                                                      tolerance=0.0001)), control="negative")
    rng = random.Random(2809)
    mutated = json.loads(json.dumps(wave["after"]))
    mutated[rng.randrange(len(mutated))][1] += 0.01
    check("N14.seeded_value_mutation", bool(T.numeric_diff(wave["after"], mutated, tolerance=0.0001)), control="negative")

    # Fake-Unreal channel rewrite: exact float and visibility round-trips.
    original_ue = T._ue
    T._ue = lambda: FakeUE
    try:
        fc = FakeChannel([[0, 1.0]])
        T._replace_channel(fc, [[0, 0.0], [230, 12.5]])
        check("P24.fake_float_channel", T._channel_keys(fc) == [[0, 0.0], [230, 12.5]])
        bc = FakeChannel([[0, True]])
        T._replace_channel(bc, [[0, False], [230, True]], boolean=True)
        check("P25.fake_visibility_channel", T._channel_keys(bc, boolean=True) == [[0, False], [230, True]])
    finally:
        T._ue = original_ue

    # Exact dirty-package scope planner.
    check("P26.packages_seq", T._packages_for_plan({"mutating_parts": ["fires_together"]}) == [T.SEQ_PATH])
    check("P27.packages_map", T._packages_for_plan({"mutating_parts": ["dune_shadow"]}) == [T.MAP_PATH])
    check("P28.packages_both", T._packages_for_plan({"mutating_parts": ["stylish_fire"]}) == [T.SEQ_PATH, T.MAP_PATH])
    check("P29.stylish_dry_no_package", T._packages_for_plan({"mutating_parts": []}) == [])

    # Planned read-back is checked against authored values, not merely captured after-state.
    semantic_plan = {"mutating_parts": ["fires_together", "dune_shadow"],
                     "fires_together": {"L": {"intensity": {"after": [[0, 0.0], [230, 2.0]]},
                                                     "visibility": {"after": [[0, False], [230, True]]}}}}
    semantic_state = {"fires": {"L": {"intensity": {"keys": [[0, 0.0], [230, 2.0]]},
                                          "visibility": {"keys": [[0, False], [230, True]]}}},
                      "dune": {"shadow": {"supported": {"cast_shadow": True, "cast_dynamic_shadow": True}}}}
    check("P30.semantic_readback", not T._plan_state_problems(semantic_state, semantic_plan, p))
    bad_semantic = json.loads(json.dumps(semantic_state))
    bad_semantic["fires"]["L"]["intensity"]["keys"][1][1] = 3.0
    check("N15.semantic_key_mutation", bool(T._plan_state_problems(bad_semantic, semantic_plan, p)), control="negative")
    bad_dune = json.loads(json.dumps(semantic_state))
    bad_dune["dune"]["shadow"]["supported"]["cast_dynamic_shadow"] = False
    check("N16.semantic_dune_mutation", bool(T._plan_state_problems(bad_dune, semantic_plan, p)), control="negative")

    vis_row = {"class": "MovieSceneVisibilityTrack", "property": "bHidden", "path": "bHidden",
               "range": [0, 6241], "active": True, "keys": [[0, False], [230, True]]}
    tf = {"location": [1.0, 2.0, 3.0], "rotation": [0.0, 0.0, 0.0], "scale": [0.5, 0.5, 0.5]}
    stylish_plan = {"mutating_parts": ["stylish_fire"], "stylish_fire": {"swaps": [
        {"old_label": "Old", "new_label": "Old Stylish", "system": "/NS", "transform": tf,
         "old_hidden": False, "visibility": vis_row}]}}
    stylish_state = {"stylish": {"originals": {"Old": {"hidden": True,
                                                            "visibility": dict(vis_row, active=False)}},
                                  "created": [{"label": "Old Stylish", "asset": "/NS", "transform": tf,
                                               "hidden": False, "visibility": vis_row}]}}
    check("P31.semantic_stylish_readback", not T._plan_state_problems(stylish_state, stylish_plan, p))
    bad_old_vis = json.loads(json.dumps(stylish_state))
    bad_old_vis["stylish"]["originals"]["Old"]["visibility"]["active"] = True
    check("N17.semantic_old_emitter_reenabled", bool(T._plan_state_problems(bad_old_vis, stylish_plan, p)), control="negative")
    bad_style_tf = json.loads(json.dumps(stylish_state))
    bad_style_tf["stylish"]["created"][0]["transform"]["location"][0] += 0.1
    check("N18.semantic_stylish_transform", bool(T._plan_state_problems(bad_style_tf, stylish_plan, p)), control="negative")

    passed = sum(row["ok"] for row in checks)
    report = {"tool": T.TOOL, "tool_version": T.TOOL_VERSION, "passed": passed,
              "failed": len(checks) - passed,
              "positive": sum(row["ok"] and row["control"] == "positive" for row in checks),
              "negative": sum(row["ok"] and row["control"] == "negative" for row in checks),
              "checks": checks}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("S3_POLISH_HARNESS_OK|passed=%d|failed=0|positive=%d|negative=%d" %
          (report["passed"], report["positive"], report["negative"]))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        raise
