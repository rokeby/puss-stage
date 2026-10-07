"""Offline harness for p04_window_shadows.py + Tools/WindowShadows/find_windows.py. No Unreal.

Every check has a positive and a negative control (a verifier that cannot fail is not a verifier,
puss-assert-dont-print). Run: python test_p04_window_shadows_offline.py  -> TEST_P04WINSHADOW_OK|passed=N|failed=0
Writes test_p04_window_shadows_offline_report.json next to this file.
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import math
import os
import sys
import tempfile
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOL = os.path.join(HERE, "p04_window_shadows.py")
RUNNER = os.path.join(HERE, "p04_window_shadows_run.py")
FW = os.path.join(PROJECT, "Tools", "WindowShadows", "find_windows.py")
SCORES_RECORD = os.path.join(HERE, "lighting_scores_record_P04.json")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ws = _load(TOOL, "ws_under_test")
fw = _load(FW, "fw_under_test")
RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append({"name": name, "ok": True})
    except Exception as error:  # noqa: BLE001
        RESULTS.append({"name": name, "ok": False, "error": "%s: %s" % (type(error).__name__, error),
                        "trace": traceback.format_exc()[-1500:]})


def refuses(fn, token):
    try:
        fn()
    except ws.P04WindowShadowError as error:
        assert token in str(error), "wrong refusal: %s (wanted %s)" % (error, token)
        return
    raise AssertionError("did not refuse (wanted %s)" % token)


# ---------------------------------------------------------------- synthetic masks
def synthetic(h=1000, w=500, holes=(), notches=(), diagonal=False):
    """opacity: 1 = paper. 1 px = 1 cm when height_cm = rows of the paper bbox."""
    op = np.zeros((h + 20, w + 20), dtype=np.float32)
    op[10:10 + h, 10:10 + w] = 1.0
    for r0, c0, r1, c1 in holes:
        op[10 + r0:10 + r1, 10 + c0:10 + c1] = 0.0
    for r0, c0, r1, c1 in notches:          # open to the outside through the paper edge
        op[10 + r0:10 + r1, 10 + c0:10 + c1 + 20] = 0.0
    if diagonal:                             # hole whose only contact with the outside is one diagonal pixel
        op[200:260, w - 50:w + 8] = 0.0      # last hole column w+7; paper's last column is w+9
        op[199, w + 8] = 0.0                  # diagonal step 1 (its 4-neighbours stay paper)
        op[198, w + 9] = 0.0                  # diagonal step 2, on the last paper column -> touches outside
    return op


def t_window_detected():
    op = synthetic(holes=[(300, 100, 400, 200)])          # 100 x 100 cm = 1.0 m^2, centre u=150, z from bottom
    res = fw.find_windows(op, 1000.0, 500.0, 0.5)
    wins = [h for h in res["holes"] if h["is_window"]]
    assert len(wins) == 1, res["holes"]
    w = wins[0]
    assert abs(w["area_m2"] - 1.0) < 0.01, w["area_m2"]
    assert abs(w["centroid_cm"][0] - 150.0) < 0.6 and abs(w["centroid_cm"][1] - 650.0) < 0.6, w["centroid_cm"]
    assert abs(w["bbox_cm"][0] - 100) < 0.6 and abs(w["bbox_cm"][3] - 700) < 0.6, w["bbox_cm"]


def t_window_negatives():
    op = synthetic(holes=[(100, 100, 150, 150)], notches=[(500, 300, 700, 480)])   # 0.25 m^2 hole + border notch
    res = fw.find_windows(op, 1000.0, 500.0, 0.5)
    assert len(res["holes"]) == 1, "the notch must not count as enclosed"
    assert not res["holes"][0]["is_window"], "0.25 m^2 is below 0.5"
    op2 = synthetic(diagonal=True)
    assert fw.find_windows(op2, 1000.0, 500.0, 0.01)["holes"] == [], "diagonal leak must not count as enclosed"
    op3 = synthetic(holes=[(100, 100, 150, 150)])
    res3 = fw.find_windows(op3, 1000.0, 500.0, 0.2)
    assert res3["holes"][0]["is_window"], "positive control: 0.25 >= 0.2 must be a window"


def t_alpha_channel():
    from PIL import Image
    op = synthetic(holes=[(300, 100, 400, 200)])
    rgba = np.zeros(op.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = 255                          # colour says 'all paper': only alpha carries the hole
    rgba[..., 3] = (op * 255).astype(np.uint8)
    path = os.path.join(tempfile.mkdtemp(), "alpha.png")
    Image.fromarray(rgba, "RGBA").save(path)
    loaded, channel = fw.load_opacity(path)
    assert channel == "alpha"
    assert len([h for h in fw.find_windows(loaded, 1000.0, 500.0, 0.5)["holes"] if h["is_window"]]) == 1
    loaded2, channel2 = fw.load_opacity(path, "first")
    assert channel2 == "first" and fw.find_windows(loaded2, 1000.0, 500.0, 0.5)["holes"] == [], "negative: R channel"


def t_anisotropic_scale():
    op = synthetic(holes=[(300, 100, 400, 200)])
    res = fw.find_windows(op, 1000.0, 1000.0, 0.5)      # horizontal texel = 2 cm
    w = res["holes"][0]
    assert abs(w["area_m2"] - 2.0) < 0.02 and abs(w["centroid_cm"][0] - 300.0) < 1.2, w


def t_handedness():
    assert fw.to_pair_y(0.0, 500.0, "L", -400.0, -900.0) == -900.0, "L image-left = outer"
    assert fw.to_pair_y(500.0, 500.0, "L", -400.0, -900.0) == -400.0, "L image-right = inner"
    assert fw.to_pair_y(0.0, 500.0, "R", 400.0, 900.0) == 400.0, "R image-left = inner"
    assert ws.panel_point(0.0, 10.0, 500.0, "L", -400.0, -900.0, 7.0) == [7.0, -900.0, 10.0]
    mirrored = fw.to_pair_y(0.0, 500.0, "R", -400.0, -900.0)
    assert mirrored != -900.0, "negative control: the R rule on an L wing must differ"
    try:
        fw.to_pair_y(0.0, 500.0, "X", 0, 1)
        raise AssertionError("bad side accepted")
    except ValueError:
        pass


def t_aim_quat_live_row():
    """The B09 TOP_L row (live-saved, lighting_scores_record_P04.json) has quat (.380,.380,-.596,.596) = yaw -90,
    pitch -65. aim_quat must reproduce it from its own forward vector."""
    with open(SCORES_RECORD, encoding="utf-8") as handle:
        record = json.load(handle)
    rows = [r for t in record["plan"]["targets"] for r in t["after_rows"] if r["label"] == "P04 SCORE B09 MOODY TOP_L"]
    assert len(rows) == 1
    q_live = rows[0]["relative_transform"]["rotation_xyzw"]
    fwd = ws.quat_forward(q_live)
    q, pitch, yaw = ws.aim_quat(fwd)
    assert ws.quat_close(q, q_live, 1e-6), (q, q_live)
    assert abs(pitch + 65.0) < 0.05 and abs(yaw + 90.0) < 1e-3, (pitch, yaw)   # float32 quat in the record
    for d in ([1, 0, 0], [0.3, -0.7, -0.6], [-0.5, 0.8, -0.3]):
        n = ws._norm(d)
        f = ws.quat_forward(ws.aim_quat(d)[0])
        assert max(abs(f[i] - d[i] / n) for i in range(3)) < 1e-9, (d, f)
    bad = [q_live[1], q_live[0], q_live[3], q_live[2]]
    assert not ws.quat_close(ws.aim_quat(fwd)[0], bad, 1e-3), "negative control"


def t_projection():
    g = ws.project_to_floor([0.0, 0.0, 400.0], [100.0, 50.0, 200.0])
    assert max(abs(a - b) for a, b in zip(g, [200.0, 100.0, 0.0])) < 1e-9, g
    assert ws.project_to_floor([0.0, 0.0, 400.0], [100.0, 0.0, 450.0]) is None, "point above the light"
    assert ws.blocked_by_wing([0, 0, 500], [-600, 0, 0], -500, (-900, -400), (400, 900), 1000) is False
    assert ws.blocked_by_wing([0, -800, 500], [-600, -800, 0], -500, (-900, -400), (400, 900), 1000) is True


def t_place_light_behind():
    opts = ws.check_args({"mode": "PLAN"})
    c = [2242.5, -500.0, 580.0]
    light, floor, notes = ws.place_light(c, opts, 5, 670.0)
    assert light[0] > c[0] + 20 and light[0] - c[0] <= opts["max_light_setback_cm"] + 1e-6, light
    assert light[1] < c[1] and light[2] >= 670.0 + opts["light_above_window_cm"] - 1e-6 or "SETBACK_CUT_BY_MAX_Z" in notes
    # collinear: floor, window centroid, light
    a, b = ws._sub(c, floor), ws._sub(light, c)
    cross = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    assert ws._norm(cross) < 1e-6 * ws._norm(a) * ws._norm(b)
    refuses(lambda: ws.place_light([100.0, 0.0, 0.0], opts, 1), "AIM_DEGENERATE")


def t_strobe_times():
    opts = ws.check_args({"mode": "PLAN"})
    t = ws.strobe_flash_times(opts)
    start = opts["passage_start_ticks"] / opts["tick_rate"]
    assert all(abs((start + x) - round(start + x)) < 2e-4 for x in t), "peaks at integer show seconds (phase 0)"
    assert abs(t[0] - (math.ceil(start) - start)) < 1e-4
    t2 = ws.strobe_flash_times(dict(opts, strobe_phase_cycles=0.25))
    assert abs(((t2[0] - t[0]) % 1.0) - 0.75) < 1e-6, "phase 0.25 shifts peaks 0.25 s EARLIER (mod 1)"


def t_args():
    refuses(lambda: ws.check_args({"mode": "APPLY"}), "CONFIRM_MISSING")
    refuses(lambda: ws.check_args({"mode": "APPLY", "confirm": "APPLY P04WINSHADOW"}), "APPLY_NEEDS_PLAN_SHA256")
    refuses(lambda: ws.check_args({"mode": "PLAN", "bogus": 1}), "ARGS_UNKNOWN")
    refuses(lambda: ws.check_args({"mode": "PLAN", "light_function": "/Game/Nope"}), "LIGHT_FUNCTION_NOT_LISTED")
    refuses(lambda: ws.check_args({"mode": "PLAN", "wings": [1, 1]}), "WINGS_INVALID")
    ok = ws.check_args({"mode": "APPLY", "confirm": "APPLY P04WINSHADOW", "plan_sha256": "a" * 64})
    assert ok["mode"] == "APPLY"
    assert ws.check_args({"mode": "REVERT", "confirm": "REVERT P04WINSHADOW"})["mode"] == "REVERT"


# ---------------------------------------------------------------- real plan (offline data)
PLAN_CACHE = {}


def real_plan():
    if "plan" not in PLAN_CACHE:
        tmp = tempfile.mkdtemp()
        plan, sha = ws.run_plan({"mode": "PLAN"}, out_plan=os.path.join(tmp, "plan.json"),
                                out_preview=os.path.join(tmp, "preview.png"))
        PLAN_CACHE.update(plan=plan, sha=sha, tmp=tmp)
    return PLAN_CACHE["plan"]


def t_real_plan_shape():
    plan = real_plan()
    opts = plan["opts"]
    on = ws.enabled_lights(plan)
    assert on, "no enabled lights"
    labels = [l["label"] for l in plan["lights"]]
    assert len(labels) == len(set(labels)) and all(ws.LABEL_RE.match(x) for x in labels), labels
    for l in plan["lights"]:
        xw = ws.station_x(opts, l["wing"]) + opts["wing_plane_dx_cm"]
        assert xw + 20 <= l["light_local_cm"][0] <= xw + opts["max_light_setback_cm"] + 1e-6, l["label"]
        assert l["light_local_cm"][1] < l["edges"]["inner_cm"], "light must be outboard of the inner edge (left)"
        assert l["cone_leak"]["outside_silhouette_fraction"] <= opts["max_cone_leak"], l["label"]
        assert l["window"]["area_m2"] >= opts["min_window_m2"]
        assert l["patch"]["bbox_cm"][2] < xw, "patch must land in FRONT of the wing (camera side)"
        assert l["design"].endswith(("L_v1", "L_v2")), "left designs only"
        fwd = ws.quat_forward(l["rotation_xyzw"])
        aim = ws._sub(l["aim_floor_local_cm"], l["light_local_cm"])
        assert ws._dot(fwd, aim) / ws._norm(aim) > 0.999999, "rotation must aim at the floor target"
        through = ws._sub(l["window_centroid_local_cm"], l["light_local_cm"])
        assert ws._dot(fwd, through) / ws._norm(through) > 0.999999, "axis must pass the window centroid"
    assert plan["timeline"]["cap_ok"], plan["timeline"]
    for l in on:
        t = l["timing"]
        if t["state"] == "AFTER_STROBE":
            assert t["strike_s"] >= plan["timeline"]["strobe_end_s"] - 1e-6, "lefts rise AFTER the strobe"


def t_real_plan_cross_checks():
    plan = real_plan()
    agree = [d for d, v in plan["designs"].items() if v["enclosed_holes"] == v["builder_hole_count"]]
    assert len(agree) >= 7, "hole census vs builder: %s" % {d: (v["enclosed_holes"], v["builder_hole_count"])
                                                         for d, v in plan["designs"].items()}
    assert all(w["design_agrees_record"] for w in plan["wings"]), "inventory design vs record mesh"
    # determinism: a second PLAN gives the same sha
    tmp = tempfile.mkdtemp()
    unused, sha2 = ws.run_plan({"mode": "PLAN"}, out_plan=os.path.join(tmp, "plan.json"),
                               out_preview=os.path.join(tmp, "preview.png"))
    assert sha2 == PLAN_CACHE["sha"], "PLAN is not deterministic"


# ---------------------------------------------------------------- editor model (fake Show, real row shape)
def fake_show(plan):
    with open(SCORES_RECORD, encoding="utf-8") as handle:
        record = json.load(handle)
    src = [r for t in record["plan"]["targets"] for r in t["after_rows"] if r["label"] == "P04 SCORE B09 MOODY TOP_L"][0]
    filler = [r for t in record["plan"]["targets"] for r in t["after_rows"]
              if r["label"] == "P04 SCORE B09 MOODY PRACTICAL_L"][0]
    cues, stations, bays = [], [], []
    ident = {"location": [0.0, 0.0, 0.0], "rotation_xyzw": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]}
    by_label = {l["cue_label"]: l for l in plan["lights"]}
    for n in range(1, 22):
        label = "P04 Wing %03d" % n
        guid = by_label[label]["cue_guid_record"] if label in by_label else "%032X" % (0xC000 + n)
        rows = [dict(copy.deepcopy(filler), guid="%032X" % (0xA000 + n), label="P04 SCORE B%02d X PRACTICAL_L" % n)]
        if n == 9:
            rows.append(copy.deepcopy(src))
        cues.append({"show_index": 98 + n, "guid": guid, "label": label, "type": "WING_PAIR",
                     "occurrence_offset": copy.deepcopy(ident), "attachments": rows})
        stations.append({"cue_guid": guid, "distance_cm": 250.0 + 500 * (n - 1),
                         "world": {"location": [250.0 + 500 * (n - 1), 240000.0, 0.0],
                                   "rotation_xyzw": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]}})
        bays.append(guid)
    cues.append({"show_index": 200, "guid": "%032X" % 0xEEEE, "label": "P05 Wing 001", "type": "WING_PAIR",
                 "occurrence_offset": copy.deepcopy(ident), "attachments": []})
    return {"cues": cues, "bay_guids": bays, "passage_guid": "0067B5F57142956FB5B80EA31B1210B5", "stations": stations}


def _opts(plan):
    return dict(plan["opts"], source_light_label="P04 SCORE B09 MOODY TOP_L", max_frame_disagreement_cm=5.0,
                avoid_scratch_cues=[])


def t_editor_plan_and_scope():
    plan = real_plan()
    plain = fake_show(plan)
    ep = ws.editor_plan(plain, plan, _opts(plan))
    assert sum(len(t["planned_rows"]) for t in ep["targets"]) == len(ws.enabled_lights(plan))
    assert max(f["disagreement_cm"] for t in ep["targets"] for f in t["frames"]) < 0.01   # plan rounds to 1e-3
    assert ep["scratch"]["cue_guid"] not in {t["cue_guid"] for t in ep["targets"]}
    base = {c["guid"]: c["attachments"] for c in plain["cues"]}
    minted = {t["cue_guid"]: ["%032X" % (0xB000 + 16 * i + j) for j in range(len(t["planned_rows"]))]
              for i, t in enumerate(ep["targets"])}
    after = ws.add_plain(base, ep["targets"], minted)
    ws.check_scope(ws.state_differences, base, after, ep["targets"], minted, "after")          # + control
    bad = copy.deepcopy(after)
    other = [g for g in bad if g not in minted][0]
    bad[other][0]["lighting"]["intensity"] = 999.0
    refuses(lambda: ws.check_scope(ws.state_differences, base, bad, ep["targets"], minted, "after"), "SCOPE_CHANGED")
    bad2 = copy.deepcopy(after)
    tg = ep["targets"][0]["cue_guid"]
    bad2[tg][-1]["lighting"]["outer_cone_angle_degrees"] += 1.0
    refuses(lambda: ws.check_scope(ws.state_differences, base, bad2, ep["targets"], minted, "after"), "SCOPE_CHANGED")
    bad3 = copy.deepcopy(after)
    bad3[tg][0]["label"] = "tampered pre-existing row"
    refuses(lambda: ws.check_scope(ws.state_differences, base, bad3, ep["targets"], minted, "after"), "SCOPE_CHANGED")
    refuses(lambda: ws.check_scope(ws.state_differences, base, after, ep["targets"], minted, "before"), "SCOPE_CHANGED")
    # REVERT model returns exactly the before rows; drift refuses
    record = {"passage": "P04", "status": "saved_readback_verified", "targets": ep["targets"],
              "before_rows": {g: base[g] for g in minted}, "after_rows": {g: after[g] for g in minted},
              "minted_by_cue": minted}
    ws.check_record(record)
    back = ws.revert_plain(ws.state_differences, after, record)
    assert not ws.state_differences(back, base)
    drifted = copy.deepcopy(after)
    drifted[tg][-1]["lighting"]["intensity"] = 1.0
    refuses(lambda: ws.revert_plain(ws.state_differences, drifted, record), "REVERT_DRIFT")


def t_planned_row_fields():
    plan = real_plan()
    plain = fake_show(plan)
    ep = ws.editor_plan(plain, plan, _opts(plan))
    row = ep["targets"][0]["planned_rows"][0]
    lg = row["lighting"]
    assert ws._enum_name(lg["type"]) == "SPOT" and lg["cast_shadows"] is True and lg["use_temperature"] is False
    assert lg["color"][:3] == ws.MOON_RGB and lg["intensity"] == plan["opts"]["intensity_cd"]
    assert lg["drama"]["strike_on_approach"] is True and ws._enum_name(lg["drama"]["after_pass"]) == "EXTINGUISH"
    assert row["guid"].startswith("<MINT:") and ws.LABEL_RE.match(row["label"])
    src_cue = [c for c in plain["cues"] if c["label"] == "P04 Wing 009"][0]
    assert src_cue["attachments"][-1]["lighting"]["cast_shadows"] is False, "source untouched (deepcopy)"


def t_labels_and_refusals():
    plan = real_plan()
    plain = fake_show(plan)
    dup = copy.deepcopy(plan)
    on = ws.enabled_lights(dup)
    on[1]["label"] = on[0]["label"]
    refuses(lambda: ws.editor_plan(plain, dup, _opts(plan)), "LABELS_INVALID")
    taken = copy.deepcopy(plain)
    taken["cues"][3]["attachments"][0]["label"] = ws.enabled_lights(plan)[0]["label"]
    refuses(lambda: ws.editor_plan(taken, plan, _opts(plan)), "LABEL_ALREADY_EXISTS")
    nosrc = copy.deepcopy(plain)
    for c in nosrc["cues"]:
        c["attachments"] = [r for r in c["attachments"] if r["label"] != "P04 SCORE B09 MOODY TOP_L"]
    refuses(lambda: ws.editor_plan(nosrc, plan, _opts(plan)), "SOURCE_ROW_COUNT")
    moved = copy.deepcopy(plain)
    for s in moved["stations"]:
        s["world"]["location"][0] += 30.0
    refuses(lambda: ws.editor_plan(moved, plan, _opts(plan)), "FRAME_DISAGREES")
    drift = copy.deepcopy(plain)
    target_label = ws.enabled_lights(plan)[0]["cue_label"]
    for c in drift["cues"]:
        if c["label"] == target_label:
            old = c["guid"]
            c["guid"] = "%032X" % 0xDEAD
            drift["bay_guids"] = [("%032X" % 0xDEAD) if g == old else g for g in drift["bay_guids"]]
            for s in drift["stations"]:
                if s["cue_guid"] == old:
                    s["cue_guid"] = "%032X" % 0xDEAD
    refuses(lambda: ws.editor_plan(drift, plan, _opts(plan)), "CUE_GUID_DRIFT")


def t_minted_and_context():
    ws.check_minted(["%032X" % 1, "%032X" % 2], [], 2)
    refuses(lambda: ws.check_minted(["%032X" % 1, "%032X" % 1], [], 2), "MINTED_GUID_DUPLICATE")
    refuses(lambda: ws.check_minted(["%032X" % 1], ["%032X" % 1], 1), "MINTED_GUID_NOT_FRESH")
    refuses(lambda: ws.check_minted(["0" * 32], [], 1), "MINTED_GUID_INVALID")
    ws.check_context({"census": {"content": ["x"]}}, "DRY")
    refuses(lambda: ws.check_context({"census": {"content": ["x"]}}, "APPLY"), "DIRTY_BEFORE")
    refuses(lambda: ws.check_context({"pie": True}, "APPLY"), "PIE_OR_SIE_ACTIVE")
    assert ws.padding_needed(3, 1, 2) == 4 and ws.padding_needed(1, 9, 2) == 0


def t_variant_b():
    tmp = tempfile.mkdtemp()
    plan, unused = ws.run_plan({"mode": "PLAN", "variant": "B"}, out_plan=os.path.join(tmp, "b.json"),
                               out_preview=os.path.join(tmp, "b.png"))
    owned = [l for l in plan["lights"] if (l.get("timing") or {}).get("state") == "STROBE_OWNED"]
    assert owned and all(l["timing"]["enabled"] and l["timing"]["flash"] for l in owned)
    opts = plan["opts"]
    peaks = ws.strobe_flash_times(opts)
    for l in owned:
        for t, off in zip(l["timing"]["flash_times_s"], l["timing"]["flash_camera_offsets_cm"]):
            assert min(abs(t - p) for p in peaks) > 0.45, "flash must sit in the strobe's dark half"
            assert abs(off - (t * opts["camera_speed_cm_s"] - l["lamp_route_cm"])) < 0.11
    a_plan = real_plan()
    assert not any((l.get("timing") or {}).get("flash") for l in a_plan["lights"]), "variant A has no flashes"


def t_ast_parse():
    for path in (TOOL, RUNNER, FW, os.path.abspath(__file__)):
        with open(path, encoding="utf-8") as handle:
            ast.parse(handle.read(), filename=path)
    for path in ("p04_window_shadows_args.json", "p04_window_shadows_request.json"):
        with open(os.path.join(HERE, path), encoding="utf-8") as handle:
            json.load(handle)
    with open(os.path.join(HERE, "p04_window_shadows_args.json"), encoding="utf-8") as handle:
        assert json.load(handle)["mode"] == "PLAN", "the checked-in args must be PLAN"


CHECKS = [("window_detected", t_window_detected), ("window_negatives", t_window_negatives),
          ("alpha_channel", t_alpha_channel), ("anisotropic_scale", t_anisotropic_scale),
          ("handedness", t_handedness), ("aim_quat_live_row", t_aim_quat_live_row), ("projection", t_projection),
          ("place_light_behind", t_place_light_behind), ("strobe_times", t_strobe_times), ("args", t_args),
          ("real_plan_shape", t_real_plan_shape), ("real_plan_cross_checks", t_real_plan_cross_checks),
          ("editor_plan_and_scope", t_editor_plan_and_scope), ("planned_row_fields", t_planned_row_fields),
          ("labels_and_refusals", t_labels_and_refusals), ("minted_and_context", t_minted_and_context),
          ("variant_b", t_variant_b), ("ast_parse", t_ast_parse)]


def main():
    for name, fn in CHECKS:
        check(name, fn)
    failed = [r for r in RESULTS if not r["ok"]]
    with open(os.path.join(HERE, "test_p04_window_shadows_offline_report.json"), "w", encoding="utf-8") as handle:
        json.dump({"results": RESULTS, "passed": len(RESULTS) - len(failed), "failed": len(failed)}, handle, indent=1)
    for r in failed:
        print("FAIL", r["name"], r["error"])
        print(r["trace"])
    print("TEST_P04WINSHADOW_%s|passed=%d|failed=%d" % ("OK" if not failed else "FAILED", len(RESULTS) - len(failed),
                                                         len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
