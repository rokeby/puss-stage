"""Offline positive/negative harness for p01_lip_clear.py.  No Unreal import."""
import json
import os
import runpy


HERE = os.path.dirname(os.path.abspath(__file__))
api = runpy.run_path(os.path.join(HERE, "p01_lip_clear.py"),
                     init_globals={"P01_LIP_CLEAR_IMPORT_ONLY": True})
LipClearError = api["LipClearError"]
parse_args = api["parse_args"]
classify_historical = api["classify_historical"]
count_problems = api["count_problems"]
transition_problems = api["transition_problems"]
dirty_problems = api["dirty_problems"]
matched_centres = api["matched_centres"]
TARGETS = api["TARGET_ATTACHMENTS"]
COUNTS = api["COUNTS"]
SHOW = api["SHOW"]
WORLD = api["WORLD"]

passed = []
positive = 0
negative = 0


def check(name, condition, kind="positive"):
    global positive, negative
    if not condition:
        raise AssertionError(name)
    passed.append(name)
    if kind == "positive":
        positive += 1
    else:
        negative += 1


def rejects(name, func, text):
    global negative
    try:
        func()
    except Exception as exc:
        if text not in str(exc):
            raise AssertionError("%s: %r lacks %r" % (name, exc, text))
        passed.append(name)
        negative += 1
        return
    raise AssertionError("%s: did not reject" % name)


def structures():
    base = {"current": True}
    base.update({name: 100 for name in COUNTS})
    return {"Infinity Stage - Structure %02d" % index: dict(base) for index in range(1, 7)}


def cue_rows(enabled=True):
    return [{"label": TARGETS[0], "enabled": enabled, "x": 1},
            {"label": "kept", "enabled": True, "x": 2},
            {"label": TARGETS[1], "enabled": enabled, "x": 3}]


def state(enabled=True, portal=True, trough=1, housings=2):
    return {"portal_float_trough": portal,
            "target_enabled": {label: enabled for label in TARGETS},
            "trough_instances": trough, "matched_housing_instances": housings,
            "cue_attachments": cue_rows(enabled)}


# Positive controls: the intended DRY/APPLY/REVERT contracts pass.
check("parse_dry", parse_args({"mode": "DRY", "confirm": "DRY LIPCLEAR", "run_id": "LC-DRY"})["mode"] == "DRY")
check("parse_apply", parse_args({"mode": "apply", "confirm": "APPLY LIPCLEAR", "run_id": "LC-A"})["mode"] == "APPLY")
check("parse_revert", parse_args({"mode": "REVERT", "confirm": "REVERT LIPCLEAR", "run_id": "LC-R", "apply_run": "LC-A"})["apply_run"] == "LC-A")
classification = classify_historical(list(TARGETS) + ["unrelated"], False)
check("classification_exact", classification == {"historical": 16, "real": 2, "prediction_only": 14, "lip_labels": [], "problems": []})
before_counts = structures()
after_counts = json.loads(json.dumps(before_counts))
after_counts["Infinity Stage - Structure 01"]["portal_piece_count"] -= 1
after_counts["Infinity Stage - Structure 01"]["fixture_body_count"] -= 2
check("apply_counts", count_problems(before_counts, after_counts, "Infinity Stage - Structure 01", "APPLY") == [])
check("revert_counts", count_problems(after_counts, before_counts, "Infinity Stage - Structure 01", "REVERT") == [])
check("apply_transition", transition_problems(state(), state(False, False, 0, 0), "APPLY") == [])
check("revert_transition", transition_problems(state(False, False, 0, 0), state(), "REVERT") == [])
check("dirty_initial", dirty_problems({"content": [], "maps": []}, "initial") == [])
check("dirty_presave", dirty_problems({"content": [SHOW], "maps": [WORLD]}, "pre_save") == [])
check("centre_match", len(matched_centres([(298.8, -729.4, 23.0), (298.8, 729.4, 23.0), (0, 0, 0)])) == 2)

# Negative controls: each material guard is shown to refuse the wrong state.
rejects("bad_mode", lambda: parse_args({"mode": "VERIFY", "confirm": "VERIFY LIPCLEAR", "run_id": "X"}), "MODE")
rejects("bad_confirm", lambda: parse_args({"mode": "APPLY", "confirm": "yes", "run_id": "X"}), "CONFIRM")
rejects("bad_run", lambda: parse_args({"mode": "DRY", "confirm": "DRY LIPCLEAR", "run_id": "../x"}), "RUN_ID")
rejects("revert_no_apply", lambda: parse_args({"mode": "REVERT", "confirm": "REVERT LIPCLEAR", "run_id": "R"}), "APPLY_RUN")
rejects("revert_same_run", lambda: parse_args({"mode": "REVERT", "confirm": "REVERT LIPCLEAR", "run_id": "R", "apply_run": "R"}), "own run_id")
rejects("unknown_arg", lambda: parse_args({"mode": "DRY", "confirm": "DRY LIPCLEAR", "run_id": "X", "force": True}), "ARGS_UNKNOWN")
check("missing_real_refused", bool(classify_historical([TARGETS[0]], False)["problems"]), "negative")
check("lip_attachment_refused", bool(classify_historical(list(TARGETS) + ["P01 Wing 001 Lip 01"], False)["problems"]), "negative")
check("lip_record_refused", bool(classify_historical(list(TARGETS), True)["problems"]), "negative")
wrong = json.loads(json.dumps(after_counts)); wrong["Infinity Stage - Structure 01"]["portal_piece_count"] += 1
check("portal_delta_refused", bool(count_problems(before_counts, wrong, "Infinity Stage - Structure 01", "APPLY")), "negative")
wrong = json.loads(json.dumps(after_counts)); wrong["Infinity Stage - Structure 01"]["fixture_body_count"] += 1
check("fixture_delta_refused", bool(count_problems(before_counts, wrong, "Infinity Stage - Structure 01", "APPLY")), "negative")
wrong = json.loads(json.dumps(after_counts)); wrong["Infinity Stage - Structure 01"]["board_count"] += 1
check("other_target_count_refused", bool(count_problems(before_counts, wrong, "Infinity Stage - Structure 01", "APPLY")), "negative")
wrong = json.loads(json.dumps(after_counts)); wrong["Infinity Stage - Structure 02"]["board_count"] += 1
check("other_structure_refused", bool(count_problems(before_counts, wrong, "Infinity Stage - Structure 01", "APPLY")), "negative")
wrong = json.loads(json.dumps(after_counts)); wrong["Infinity Stage - Structure 03"]["current"] = False
check("not_current_refused", bool(count_problems(before_counts, wrong, "Infinity Stage - Structure 01", "APPLY")), "negative")
check("portal_readback_refused", bool(transition_problems(state(), state(False, True, 0, 0), "APPLY")), "negative")
check("enabled_readback_refused", bool(transition_problems(state(), state(True, False, 0, 0), "APPLY")), "negative")
check("trough_readback_refused", bool(transition_problems(state(), state(False, False, 1, 0), "APPLY")), "negative")
check("housing_readback_refused", bool(transition_problems(state(), state(False, False, 0, 1), "APPLY")), "negative")
changed = state(False, False, 0, 0); changed["cue_attachments"][1]["x"] = 99
check("non_target_fingerprint_refused", bool(transition_problems(state(), changed, "APPLY")), "negative")
check("dirty_initial_refused", bool(dirty_problems({"content": [SHOW], "maps": []}, "initial")), "negative")
check("dirty_scope_refused", bool(dirty_problems({"content": [SHOW, "/Game/Other"], "maps": [WORLD]}, "pre_save")), "negative")
check("centre_missing_refused", matched_centres([(298.8, -729.4, 23.0)]) == [], "negative")
check("centre_ambiguous_refused", matched_centres([(298.8, -729.4, 23.0), (298.8, -729.4, 23.0), (298.8, 729.4, 23.0)]) == [], "negative")

print("P01_LIP_CLEAR_HARNESS_OK|pass=%d|positive=%d|negative=%d" %
      (len(passed), positive, negative))
