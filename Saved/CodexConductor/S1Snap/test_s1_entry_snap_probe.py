"""Offline -/+ controls for the probe's analyser (no Unreal). python test_s1_entry_snap_probe.py"""
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("probe", os.path.join(HERE, "s1_entry_snap_probe.py"))
sys.argv = ["x"]                       # keep the module's __main__ branch from running main()
P = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(P)         # main() fails without unreal; the failure path imports unreal -> guard
except ImportError:
    pass

S1 = 4624705


def rows(look_deg=0.0, jump_cm=0.0, fov_jump=0.0, wrong_vt=False, stall=False, exp_jump=0.0, focal_jump=0.0):
    out = [{"header": True, "p01_end_vs_s1_start_ticks": 0}]
    prev = None
    for k in range(-50, 126):                    # 2 s before .. 5 s after at 25 fps
        m = S1 + k * 960 + 38
        seg = 1 if m < S1 else 2
        sf = (m - S1) / 960.0
        x = 28784.0 - (0.2 * (-k) ** 2 / 50.0 if k < 0 else 0.0)
        rot = [0.0, 0.0, 0.0]
        if seg == 1:
            vt = {"label": "Passage 1 Camera Rig", "cam_vs_actor_deg": look_deg, "aperture": 2.8, "pp_weight": 1.0,
                  "focal": 25.0}
            rot = [0.0, 0.0, look_deg]
            exp = "P01 rig"
        else:
            name = "Entry" if sf < 119 else "Glide"
            lab = "Scene 1 — External Sound — Entry Handoff Camera" if name == "Entry" else "Klara Reveal - S1 Reveal Glide Camera"
            if wrong_vt and name == "Entry":
                lab = "CineCameraActor (hers)"
            vt = {"label": lab, "cam_vs_actor_deg": 0.0, "aperture": 2.8, "pp_weight": 1.0, "focal": 25.0}
            x += jump_cm
            vt["focal"] = 25.0 + focal_jump
            exp = name
        r = {"tick": k + 60, "dt": 0.04 if not (stall and k == 0) else 0.3, "master": m, "seg": seg, "scene_frame": sf,
             "playing": True, "expected_owner": exp, "pov_loc": [x, 0.0, 150.0], "pov_rot": rot,
             "pov_fov": 50.8 + (fov_jump if seg == 2 else 0.0), "vt": vt,
             "ppvs": [{"label": "S1 Hangar Pinned Exposure", "enabled": True, "unbound": False, "inside": True,
                       "blend_weight": 1.0, "pp": {"auto_exposure_bias": 0.5 + (exp_jump if seg == 2 else 0.0)}}]}
        if prev:
            r["step_cm"] = P._dist(r["pov_loc"], prev["pov_loc"])
            r["step_deg"] = P._ang_deg(r["pov_rot"], prev["pov_rot"])
            r["step_fov"] = r["pov_fov"] - prev["pov_fov"]
            r["step_master"] = m - prev["master"]
        prev = r
        out.append(r)
    return out


def run(name, data, want, forbid=()):
    path = os.path.join(tempfile.gettempdir(), "probe_TEST_%s.jsonl" % name)
    with open(path, "w", encoding="utf-8") as f:
        for r in data:
            f.write(json.dumps(r) + "\n")
    out = P.report(path, name)
    got = set(out["flags"])
    ok = set(want) <= got and not (set(forbid) & got)
    print(("PASS" if ok else "FAIL"), name, sorted(got))
    return ok


results = [
    run("clean", rows(), ["NO_STEP_FOUND"]),
    run("look_drop", rows(look_deg=8.0), ["LOOK_OFFSET_DROPPED_AT_CUT", "CROSSING_TURN_STEP"]),
    run("pose_jump", rows(jump_cm=21.0), ["CROSSING_POSE_STEP"], ["CROSSING_TURN_STEP"]),
    run("fov_jump", rows(fov_jump=2.0), ["CROSSING_FOV_STEP"]),
    run("wrong_owner", rows(wrong_vt=True), ["CUT_OWNER_MISMATCH"]),
    run("stall", rows(stall=True), ["STALL"]),
    run("exposure_jump", rows(exp_jump=1.5), ["STEP_EXPOSURE_EV_PROXY", "EXPOSURE_SETTINGS_CHANGE"], ["STEP_POSITION_CM"]),
    run("focal_jump", rows(focal_jump=10.0), ["STEP_FOCAL_MM"], ["STEP_POSITION_CM", "EXPOSURE_SETTINGS_CHANGE"]),
]
print("%d/%d" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
