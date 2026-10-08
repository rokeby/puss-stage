"""Offline positive/negative harness for P6 animated_gobo.py.

Run from the project root:
    python Saved/CodexConductor/test_animated_gobo_offline.py

No Unreal import is required and no project asset is touched.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import animated_gobo as ag  # noqa: E402


RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def raises(name, code, fn):
    try:
        fn()
        check(name, False, "did not raise")
    except ag.PlanError as exc:
        check(name, code in str(exc), str(exc))


OUT = ROOT / "Tools" / "ShadowGobo" / "P6_TestBird"
MANIFEST = OUT / "manifest.json"
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
ATLAS = OUT / manifest["atlas"]["file"]

RAW = {
    "mode": "DRY", "confirm": "DRY ANIMATED_GOBO", "run_id": "HARNESS",
    "sequence": "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips",
    "light_labels": ["Shadow Play Spot (Hangar)", "Shadow Play Spot (Mouth)"],
    "atlas_png": str(ATLAS), "manifest": str(MANIFEST),
    "mi_path": "/Game/InfinityStage/Lighting/Gobo/MI_ShadowGobo_P6_TestBird",
    "texture_path": "/Game/InfinityStage/Lighting/Gobo/T_Gobo_P6_TestBird_6x4",
    "frame_start": 175, "frame_end": 250,
}
ARGS = ag.normalized_args(RAW)
PLAN = ag.plan_from_args(ARGS)

# A. Test flipbook artifact.
image = Image.open(ATLAS)
check("A01 atlas is 2048 square", image.size == (2048, 2048), image.size)
check("A02 manifest has 24 frames", PLAN["atlas"]["frames"] == 24, PLAN["atlas"])
check("A03 manifest grid is 6x4", (PLAN["atlas"]["cols"], PLAN["atlas"]["rows"]) == (6, 4), PLAN["atlas"])
check("A04 playback is 3 seconds at 8 fps", manifest["take"]["duration_s"] == 3.0 and manifest["take"]["fps"] == 8.0)
check("A05 atlas SHA-256 is verified by planner", len(PLAN["atlas_sha256"]) == 64)
cell, gutter = PLAN["atlas"]["cell_px"], PLAN["atlas"]["gutter_px"]
pixels = image.load()
centres = [pixels[(i % 6) * cell + cell // 2, (i // 6) * cell + cell // 2] for i in range(24)]
check("A06 every used cell contains the black bird", all(v < 128 for v in centres), centres)
check("A07 contact and animated preview ship", (OUT / "contact.png").is_file() and (OUT / "preview.gif").is_file())
check("A08 gutter is non-zero and fits cell", 0 < gutter * 2 < cell, (gutter, cell))

# B. Pure plan and negative controls.
check("B01 frame keys map range to 0..Frames (end value = cell count)", PLAN["frame_keys"] == [[175, 0.0], [250, 24.0]], PLAN["frame_keys"])
check("B02 fresh project creates master/MPC/texture/MI", ag.created_assets_for(PLAN, []) == [ag.MASTER, ag.MPC, RAW["texture_path"], RAW["mi_path"]])
check("B02b existing master+MPC are reused, only texture/MI created",
      ag.created_assets_for(PLAN, [ag.MASTER, ag.MPC]) == [RAW["texture_path"], RAW["mi_path"]])
check("B02c only missing shared asset is created", ag.created_assets_for(PLAN, [ag.MPC]) == [ag.MASTER, RAW["texture_path"], RAW["mi_path"]])
check("B03 look defaults are Gary-tunable args", all(k in PLAN["params"] for k in ("BlurUV", "Softness", "Contrast", "Depth", "Scale", "FlipU", "FlipV")))
check("B04 planning is deterministic", ag.plan_from_args(ARGS)["digest"] == PLAN["digest"])
check("B05 DRY confirm exact", ag.confirm_ok("DRY", "DRY ANIMATED_GOBO") and not ag.confirm_ok("DRY", "APPLY ANIMATED_GOBO"))
check("B06 destructive REVERT confirm is explicit", ag.confirm_text("REVERT") == "REVERT ANIMATED_GOBO DELETE CREATED ASSETS")
raises("B07 -control empty labels", "LIGHT_LABELS", lambda: ag.normalized_args(dict(RAW, light_labels=[])))
raises("B08 -control duplicate labels", "LIGHT_LABELS", lambda: ag.normalized_args(dict(RAW, light_labels=["A", "A"])))
raises("B09 -control reversed frame range", "FRAME_RANGE", lambda: ag.normalized_args(dict(RAW, frame_start=250, frame_end=175)))
raises("B10 -control MI outside create-only root", "MI_PATH", lambda: ag.normalized_args(dict(RAW, mi_path="/Game/X/MI_Bad")))
raises("B11 -control texture outside create-only root", "TEXTURE_PATH", lambda: ag.normalized_args(dict(RAW, texture_path="/Game/X/T_Bad")))
raises("B12 -control unknown look parameter", "UNKNOWN_PARAMS", lambda: ag.normalized_args(dict(RAW, params={"BlurMagic": 1})))
raises("B13 -control invalid softness", "LOOK_PARAMS", lambda: ag.plan_from_args(ag.normalized_args(dict(RAW, params={"Softness": 0.8}))))
raises("B13b -control blur exceeds cell gutter", "LOOK_PARAMS", lambda: ag.plan_from_args(ag.normalized_args(dict(RAW, params={"BlurUV": 0.02}))))
import tempfile  # noqa: E402
_tmp = Path(tempfile.mkdtemp(prefix="gobo_harness_"))
_thin = json.loads(MANIFEST.read_text(encoding="utf-8"))
_thin["atlas"]["gutter_px"] = 1  # 1/2048 = 0.00049 atlas uv < default BlurUV 0.00075
(_tmp / "manifest.json").write_text(json.dumps(_thin), encoding="utf-8")
raises("B13c -control blur wider than a thin gutter", "exceeds the 1 px gutter",
       lambda: ag.plan_from_args(ag.normalized_args(dict(RAW, manifest=str(_tmp / "manifest.json")))))
check("B13d thin gutter plans when blur fits inside it", ag.plan_from_args(ag.normalized_args(dict(
    RAW, manifest=str(_tmp / "manifest.json"), params={"BlurUV": 0.0004})))["params"]["BlurUV"] == 0.0004)
raises("B14 -control missing atlas", "ATLAS_MISSING", lambda: ag.normalized_args(dict(RAW, atlas_png=str(OUT / "missing.png"))))
raises("B15 -control missing run_id", "RUN_ID", lambda: ag.normalized_args({k: v for k, v in RAW.items() if k != "run_id"}))
raises("B16 -control path-unsafe run_id", "RUN_ID", lambda: ag.normalized_args(dict(RAW, run_id="../x")))
VERIFY_RAW = dict(RAW, mode="VERIFY", confirm="VERIFY ANIMATED_GOBO", run_id="HARNESS-V", apply_run="HARNESS")
check("B17 VERIFY with apply_run normalizes", ag.normalized_args(VERIFY_RAW)["apply_run"] == "HARNESS")
raises("B18 -control VERIFY without apply_run", "APPLY_RUN", lambda: ag.normalized_args(
    {k: v for k, v in VERIFY_RAW.items() if k != "apply_run"}))
raises("B19 -control REVERT reusing the APPLY run_id", "APPLY_RUN", lambda: ag.normalized_args(
    dict(VERIFY_RAW, mode="REVERT", run_id="HARNESS")))
check("B20 plan and record files are per run", ag.plan_file("X", "R1") != ag.plan_file("X", "R2") and
      ag.record_file("X", "R1") != ag.record_file("X", "R2"))

# C. Preflight positive and every important refusal.
CLEAN = {"pie": False, "sequencer_open": False, "world_ok": True,
         "census": {"content": [], "maps": []},
         "label_counts": {label: 1 for label in ARGS["light_labels"]},
         "record_exists": False, "existing_own": [], "existing_shared": [], "shared_problems": [],
         "owned_track_count": 0, "ticks_per_frame": 800, "playback": [0, 2183]}
check("C01 positive DRY preflight", ag.preflight_refusals("DRY", ARGS, CLEAN, PLAN) == [])
check("C01b positive DRY preflight reusing valid shared assets", ag.preflight_refusals(
    "DRY", ARGS, dict(CLEAN, existing_shared=[ag.MASTER, ag.MPC]), PLAN) == [])
cases = [
    ("PIE", {"pie": True}, "PIE_OR_SIE_ACTIVE"),
    ("Sequencer open", {"sequencer_open": True}, "SEQUENCER_IS_OPEN"),
    ("wrong world", {"world_ok": False}, "WRONG_WORLD"),
    ("dirty content", {"census": {"content": ["/Game/X"], "maps": []}}, "DIRTY_CENSUS"),
    ("dirty map", {"census": {"content": [], "maps": ["/Game/M"]}}, "DIRTY_CENSUS"),
    ("missing label", {"label_counts": dict(CLEAN["label_counts"], **{"Shadow Play Spot (Mouth)": 0})}, "LIGHT_LABEL_COUNT"),
    ("duplicate label", {"label_counts": dict(CLEAN["label_counts"], **{"Shadow Play Spot (Mouth)": 2})}, "LIGHT_LABEL_COUNT"),
    ("existing per-run texture", {"existing_own": [RAW["texture_path"]]}, "CREATE_ONLY_TARGET_EXISTS"),
    ("existing per-run MI", {"existing_own": [RAW["mi_path"]]}, "CREATE_ONLY_TARGET_EXISTS"),
    ("invalid shared asset", {"existing_shared": [ag.MASTER], "shared_problems": ["MASTER_WITHOUT_MPC"]}, "SHARED_ASSET_INVALID"),
    ("owned track already on sequence", {"owned_track_count": 1}, "OWNED_TRACK_EXISTS"),
    ("non-integer tick rate", {"ticks_per_frame": None, "rate_error": "TICKS_PER_FRAME_NOT_INTEGER"}, "TICK_RATE"),
    ("end key on exclusive playback end", {"playback": [0, 250]}, "KEYS_OUTSIDE_PLAYBACK"),
    ("existing record", {"record_exists": True}, "RECORD_EXISTS"),
    ("keys outside playback", {"playback": [200, 220]}, "KEYS_OUTSIDE_PLAYBACK"),
]
for label, delta, code in cases:
    state = copy.deepcopy(CLEAN)
    state.update(delta)
    got = ag.preflight_refusals("DRY", ARGS, state, PLAN)
    check("C -control %s" % label, any(code in row for row in got), got)
bad_confirm = dict(ARGS, confirm="APPLY ANIMATED_GOBO")
check("C12 -control confirm mismatch", any("CONFIRM_MISMATCH" in row for row in ag.preflight_refusals("DRY", bad_confirm, CLEAN, PLAN)))
verify_state = dict(CLEAN, record_exists=True, existing_own=PLAN["own_assets"], existing_shared=list(ag.shared_assets(PLAN)))
check("C13 VERIFY allows its recorded assets to exist", ag.preflight_refusals("VERIFY", dict(ARGS, confirm="VERIFY ANIMATED_GOBO"), verify_state, PLAN) == [])
check("C14 -control VERIFY without record", any("NOTHING_TO_VERIFY" in r for r in ag.preflight_refusals(
    "VERIFY", dict(ARGS, confirm="VERIFY ANIMATED_GOBO"), CLEAN, PLAN)))

# D. State model, exact read-back, and revert drift controls.
BEFORE = {"playback": [0, 2183], "lights": {label: None for label in ARGS["light_labels"]}, "track": None}
AFTER = ag.apply_model(BEFORE, PLAN)
RECORD = {"snapshot_before": BEFORE, "snapshot_after": AFTER}
check("D01 apply model assigns MI to both spots", all(AFTER["lights"][v] == PLAN["mi"] for v in ARGS["light_labels"]))
check("D02 apply model adds one named Frame track", AFTER["track"]["name"] == ag.TRACK_NAME and AFTER["track"]["keys"] == PLAN["frame_keys"])
check("D02b apply model expects section range [start, end+1)", AFTER["track"]["range"] == [175, 251], AFTER["track"]["range"])
check("D03 exact APPLY snapshot passes", ag.snapshot_diff(AFTER, RECORD["snapshot_after"]) == [])
check("D04 exact REVERT restores before", ag.revert_model(AFTER, RECORD) == BEFORE)
drift = copy.deepcopy(AFTER)
drift["track"]["keys"][1][1] = 23.0
check("D05 -control keyed frame drift is detected", bool(ag.snapshot_diff(drift, RECORD["snapshot_after"])))
drift = copy.deepcopy(AFTER)
drift["lights"][ARGS["light_labels"][0]] = "/Game/X/MI_HandEdit"
check("D06 -control light-function drift is detected", bool(ag.snapshot_diff(drift, RECORD["snapshot_after"])))
check("D07 exact dirty census passes", ag.exact_dirty({"content": ag.created_assets_for(PLAN, []) + [PLAN["sequence"]], "maps": []},
                                                       ag.created_assets_for(PLAN, []) + [PLAN["sequence"]]) == [])
check("D08 -control unexpected dirty package fails", bool(ag.exact_dirty(
    {"content": ag.created_assets_for(PLAN, []) + [PLAN["sequence"], "/Game/Other"], "maps": []},
    ag.created_assets_for(PLAN, []) + [PLAN["sequence"]])))
tick_drift = copy.deepcopy(AFTER)
tick_drift["track"]["keys"] = [[0.21875, 0.0], [0.3125, 24.0]]  # tick numbers read back as display frames at 800 tpf
check("D05b -control keys landing in tick units are detected", bool(ag.snapshot_diff(tick_drift, RECORD["snapshot_after"])))
check("D09 -control dirty map fails", bool(ag.exact_dirty(
    {"content": ag.created_assets_for(PLAN, []) + [PLAN["sequence"]], "maps": ["/Game/Map"]},
    ag.created_assets_for(PLAN, []) + [PLAN["sequence"]])))

# F. Frame-time conversion, channel naming, timing and shared-asset validation.
check("F01 30 fps at 24000 ticks = 800 ticks/frame", ag.ticks_per_display_frame(24000, 1, 30, 1) == 800)
check("F02 24 fps at 24000 ticks = 1000 ticks/frame", ag.ticks_per_display_frame(24000, 1, 24, 1) == 1000)
raises("F03 -control 29.97 fps at 24000 ticks refuses rounding", "TICKS_PER_FRAME_NOT_INTEGER",
       lambda: ag.ticks_per_display_frame(24000, 1, 30000, 1001))
raises("F04 -control zero rate", "FRAME_RATE", lambda: ag.ticks_per_display_frame(24000, 1, 0, 1))
check("F05 Frame channel names accepted (plain and suffixed)", ag.channel_is_frame("Frame") and ag.channel_is_frame("Frame_183"))
check("F06 -control other channel names rejected", not any(ag.channel_is_frame(n) for n in
      ("Frames", "FrameRate", "Location.Y_183", "frame", "Frame_")))
timing30 = ag.timing_report(PLAN, 30.0)
check("F07 timing at 30 fps flags 1.2x speed and native end 265",
      abs(timing30["speed_vs_take"] - 1.2) < 1e-9 and timing30["native_frame_end"] == 265, timing30)
timing25 = ag.timing_report(PLAN, 25.0)
check("F08 timing at 25 fps is native speed", abs(timing25["speed_vs_take"] - 1.0) < 1e-9, timing25)


def cell_counts(keys, frames):
    (s0, v0), (s1, v1) = keys
    counts = [0] * frames
    for t in range(s0, s1 + 1):  # section range [s0, s1+1)
        value = v0 + (v1 - v0) * (t - s0) / float(s1 - s0)
        counts[int(min(max(value, 0.0), frames - 1.0) + 1e-4)] += 1
    return counts


counts = cell_counts(PLAN["frame_keys"], 24)
check("F09 every cell holds ~equal frames (3-5 of 76)", min(counts) >= 3 and max(counts) <= 5 and sum(counts) == 76, counts)
old_counts = cell_counts([[175, 0.0], [250, 23.0]], 24)
check("F10 -control old Frames-1 end key starves the last cell", old_counts[-1] == 1, old_counts)
GOOD = {"master": {"domain_ok": True, "atlas_compat": True, "scalars": list(ag.SCALAR_DEFAULTS),
                   "textures": [ag.TEXTURE_PARAMETER]},
        "mpc": {"scalars": ["Frame"]}, "mpc_referencers": [ag.MASTER]}
check("F11 valid shared assets pass", ag.shared_asset_problems(GOOD) == [])
check("F11b -control atlas master offered for a no-atlas plan", any("MASTER_ATLAS_COMPAT" in r for r in
      ag.shared_asset_problems(GOOD, ag.MASTER, atlas_compatible=False)))
NOATLAS_GOOD = copy.deepcopy(GOOD)
NOATLAS_GOOD["master"]["atlas_compat"] = False
NOATLAS_GOOD["mpc_referencers"] = [ag.MASTER_NOATLAS]
check("F11c valid no-atlas master passes", ag.shared_asset_problems(NOATLAS_GOOD, ag.MASTER_NOATLAS, False) == [])
check("F11d -control no-atlas master not reading MPC", any("MASTER_NOT_ON_MPC" in r for r in
      ag.shared_asset_problems(dict(NOATLAS_GOOD, mpc_referencers=[ag.MASTER]), ag.MASTER_NOATLAS, False)))
check("F12 nothing existing passes", ag.shared_asset_problems({"master": None, "mpc": None}) == [])
bad_cases = [
    ("wrong domain", lambda d: d["master"].update(domain_ok=False), "MASTER_DOMAIN"),
    ("atlas compat off", lambda d: d["master"].update(atlas_compat=False), "MASTER_ATLAS_COMPAT"),
    ("missing scalar", lambda d: d["master"].update(scalars=list(ag.SCALAR_DEFAULTS)[1:]), "MASTER_SCALARS"),
    ("extra texture param", lambda d: d["master"].update(textures=["FlipbookAtlas", "Other"]), "MASTER_TEXTURES"),
    ("MPC without Frame", lambda d: d["mpc"].update(scalars=["Other"]), "MPC_FRAME"),
    ("master without MPC", lambda d: d.update(mpc=None), "MASTER_WITHOUT_MPC"),
    ("master not reading MPC", lambda d: d.update(mpc_referencers=[]), "MASTER_NOT_ON_MPC"),
]
for label, mutate, code in bad_cases:
    desc = copy.deepcopy(GOOD)
    mutate(desc)
    got = ag.shared_asset_problems(desc)
    check("F -control shared %s" % label, any(code in row for row in got), got)

# G. Border, UV centring, atlas variant, cone geometry (Gary 8 Oct: large soft-edged rectangle filling the curtain).
NOATLAS = ag.plan_from_args(ag.normalized_args(dict(RAW, atlas_compatible=False)))
check("G01 atlas_compatible=false selects the no-atlas master", NOATLAS["master"] == ag.MASTER_NOATLAS and
      ag.created_assets_for(NOATLAS, [ag.MASTER, ag.MPC])[0] == ag.MASTER_NOATLAS)
check("G02 default stays on the atlas master", PLAN["master"] == ag.MASTER and PLAN["atlas_compatible"] is True)
check("G02b atlas choice changes the digest", NOATLAS["digest"] != PLAN["digest"])
raises("G03 -control atlas_compatible must be a bool", "ATLAS_COMPATIBLE",
       lambda: ag.normalized_args(dict(RAW, atlas_compatible="no")))
check("G04 border defaults off (beam keeps its own edge)", PLAN["params"]["BorderDepth"] == 0.0)
BORDER = dict(PLAN["params"], BorderDepth=1.0, BorderWidth=1.0, BorderAspect=1.88, BorderFeather=0.03, Scale=0.85)
check("G05 border centre is lit", abs(ag.border_mask(0.5, 0.5, BORDER) - 1.0) < 1e-9)
# Image half-width in cone UV = 0.5*Scale; height = width/1.88.
hx, hy = 0.5 * 0.85, 0.5 * 0.85 / 1.88
check("G06 outside the rectangle is black (x)", ag.border_mask(0.5 + hx + 0.01, 0.5, BORDER) == 0.0)
check("G07 outside the rectangle is black (y)", ag.border_mask(0.5, 0.5 + hy + 0.01, BORDER) == 0.0)
check("G08 inside height is lit: aspect works", ag.border_mask(0.5, 0.5 + hy - 0.04, BORDER) > 0.99)
inner = ag.border_mask(0.5 + hx - 0.005, 0.5, BORDER)
check("G09 feather is a soft ramp, not a hard edge", 0.0 < inner < 1.0, inner)
ramp = [ag.border_mask(0.5 + hx - d, 0.5, BORDER) for d in (0.0, 0.005, 0.01, 0.02, 0.03)]
check("G10 feather ramp is monotonic", all(a <= b for a, b in zip(ramp, ramp[1:])) and ramp[0] == 0.0, ramp)
check("G11 BorderDepth 0 passes light everywhere (control for G06)",
      ag.border_mask(0.5 + hx + 0.01, 0.5, dict(BORDER, BorderDepth=0.0)) == 1.0)
RECTL = dict(BORDER, UVCentre=0.5)
check("G12 UVCentre 0.5 centres the border on UV 0 (light-space UVs)",
      abs(ag.border_mask(0.0, 0.0, RECTL) - 1.0) < 1e-9 and ag.border_mask(0.5, 0.5, RECTL) == 0.0)
check("G13 max Scale: square in circle = 0.7071", abs(ag.max_scale_for_border(1.0, 1.0) - 0.5 ** 0.5) < 1e-9)
check("G14 max Scale: 1.88 rectangle in circle = 0.8829", abs(ag.max_scale_for_border(1.0, 1.88) - 0.88287) < 1e-4)
corner = (0.5 * ag.max_scale_for_border(1.0, 1.88)) ** 2 * (1 + 1 / 1.88 ** 2)
check("G15 at max Scale the border corner sits on the cone circle (r=0.5)", abs(corner - 0.25) < 1e-9, corner)
raises("G16 -control border corners outside the cone", "BORDER_OUTSIDE_CONE", lambda: ag.plan_from_args(
    ag.normalized_args(dict(RAW, params={"BorderDepth": 1.0, "BorderAspect": 1.88, "Scale": 0.95}))))
check("G17 border at Scale 0.85 plans", ag.plan_from_args(ag.normalized_args(dict(
    RAW, params={"BorderDepth": 1.0, "BorderAspect": 1.88, "Scale": 0.85})))["params"]["Scale"] == 0.85)
check("G18 cone-limit check skipped for light-space UVs (no cone)", ag.plan_from_args(ag.normalized_args(dict(
    RAW, params={"BorderDepth": 1.0, "BorderAspect": 1.88, "Scale": 0.95, "UVCentre": 0.5})))["params"]["UVCentre"] == 0.5)
raises("G19 -control UVCentre other than 0 / 0.5", "BORDER_PARAMS", lambda: ag.plan_from_args(
    ag.normalized_args(dict(RAW, params={"UVCentre": 0.25}))))
raises("G20 -control zero feather", "BORDER_PARAMS", lambda: ag.plan_from_args(
    ag.normalized_args(dict(RAW, params={"BorderFeather": 0.0}))))
a17 = ag.spot_half_angle_deg(17.0, 30.0, 0.8829)
a07 = ag.spot_half_angle_deg(17.0, 30.0, 0.7071)
check("G21 17 m image at 30 m: ~17.8 deg at Scale 0.883 vs ~21.8 deg at 0.707",
      abs(a17 - 17.79) < 0.05 and abs(a07 - 21.84) < 0.05, (a17, a07))
check("G22 border shader and Python twin share the formula", "smoothstep(0.0, f, hx - q.x) * smoothstep(0.0, f, hy - q.y)"
      in ag.CODE_BORDER and "rect = smooth(0.0, f, hx - qx) * smooth(0.0, f, hy - qy)" in (HERE / "animated_gobo.py").read_text(encoding="utf-8"))
check("G23 border multiplies the final output", "* Border;" in ag.CODE_EDGE)
check("G24 UV maths centring matches the border", "(UV + UVCentre - 0.5)" in ag.CODE_UV and "(UV + UVCentre - 0.5)" in ag.CODE_BORDER)

# E. Static safety contract: cheap but catches accidental erosion of house rules.
source = (HERE / "animated_gobo.py").read_text(encoding="utf-8")
runner = (HERE / "animated_gobo_run.py").read_text(encoding="utf-8")
check("E01 never deletes existing material expressions", "delete_all_material_expressions" not in source)
check("E02 never Save All/save_directory", "save_directory" not in source and "save_all" not in source.lower())
check("E03 all four operational modes ship", all(('"%s"' % mode) in source for mode in ag.MODES))
check("E04 record is exclusive before mutation", "_write_json(record_path, record, exclusive=True)" in source and
      source.index("_write_json(record_path, record, exclusive=True)") < source.index("# Mutation begins"))
check("E05 APPLY requires independent VERIFY", "APPLY_OK_PENDING_VERIFY" in source and "def run_verify" in source)
check("E06 success marker is generated from MARK", '"%s_SUCCESS|run=%s' in source)
check("E07 revert backs up before delete", source.index("PreAnimatedGoboRevert") < source.index("delete_asset(path)"))
check("E08 runner purges Saved module cache", "sys.modules.pop" in runner and "runpy.run_path" in runner)
check("E09 offline import did not load Unreal", ag.unreal is None)
check("E10 revert refuses external referencers before delete", source.index("REVERT_EXTERNAL_REFERENCERS") < source.index("delete_asset(path)"))
check("E11 existing make_gobo_flipbook manifest names are accepted", all(name in source for name in
      ("GoboCols", "GoboRows", "GoboFrames", "GoboGutterUV", "GoboCellUV")))
check("E12 no UE5.8-absent master-track API", not any(n in source for n in
      ("get_master_tracks", "add_master_track", "remove_master_track")))
check("E13 track uses get_tracks/add_track/remove_track", all(n in source for n in
      ("seq.get_tracks()", "seq.add_track(", "seq.remove_track(")))
check("E14 keys are converted to ticks", "unreal.FrameNumber(int(frame) * ticks_per_frame)" in source)
check("E15 revert deletes only what its run created", "if path in created and" in source)
check("E16 no single global record file", "RECORD_NAME" not in source and "PLAN_NAME" not in source)

passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = [(name, detail) for name, ok, detail in RESULTS if not ok]
(OUT / "offline_harness_report.json").write_text(json.dumps({
    "marker": "ANIMATED_GOBO_HARNESS", "passed": passed, "failed": len(failed),
    "results": [{"name": name, "pass": ok, "detail": detail} for name, ok, detail in RESULTS],
}, indent=2, default=str) + "\n", encoding="utf-8")
for name, detail in failed:
    print("FAIL", name, str(detail)[:500])
print("ANIMATED_GOBO_HARNESS|pass=%d|fail=%d" % (passed, len(failed)))
sys.exit(1 if failed else 0)
