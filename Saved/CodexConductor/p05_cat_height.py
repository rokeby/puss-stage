"""P05 cat height: DRY / APPLY / REVERT / TEST_CUTS. Lower Puss's eye in Passage 5 to ~half (Gary, 7 Oct).

Gary 7 Oct: "in P05 ... Puss's height can be about half as high, so he's mostly not running into the lower wings and
kind of crawling around them and this also allows him to look upwards at the clouds". Gary (via conductor, 7 Oct):
NO pitch-up - "the tilt will come from me controlling the dog angle". Height only. pitch_up_deg exists in the maths
(default 0, NOT in the args file) and must stay 0 unless Gary says otherwise.

WHAT CONTROLS THE P05 EYE (proof tiers per AGENTS.md):
* declaration-proven: rig world pose = Route spline transform at the evaluated distance, translated by
  route-frame (CameraOffset + LocalOffsetCm) [InfinityStageCameraRig.cpp:834-839]; LocalOffsetCm.Z is the managed
  Master Passage section's Camera.HeightOffsetCm channel, pitch is Camera.PitchDegrees, both evaluated at ABSOLUTE
  Master time [MovieSceneInfinityPassageTrack.cpp:473-480, channel names :504-505]; gait bob is then added in world z
  and faded to exactly 0 at the Passage end by the crossing settle [InfinityStageCameraRig.cpp:395-415, 637-640].
  The Route spline is rebuilt at local z=0 [InfinityStagePassageActor.cpp:819-825]. The 180 cm comes from the rig's
  CameraOffset (fixture default FVector(0,0,180) [InfinityStageEditor/Private/InfinityStageDevFixtureBuilder.cpp:540]).
  CameraOffset is a level property of the rig, not Show data (no CameraOffset/ShadowCat field in
  InfinityStageShowAsset.h; searched).
* measured (26 Sep, Saved/CodexCameraPilot/audit_cat_offsets.json): P05 rig camera_offset (0,0,180), route_start_z 0,
  cat_position_offset_z -175.883635, cat_world_z 4.116 (cat feet ~on the floor). Stills manifests for P05 (5 runs,
  5-6 Oct) read camera z 180.0, pitch 0, roll 0 at fractions 0.1..0.95 (scrubbed, so no bob).
* declaration-proven, THE SIDE EFFECT: the shadow cat rides the rig. ShadowFigureRoot = actor location +
  rotated ShadowFigureOffset - bob [InfinityStageCameraRig.cpp:427-430], the cat sits at ShadowCatPositionOffset
  under it [:297-300]. Nothing grounds it (no trace/floor code in InfinityStageShadowCatComponent.cpp; searched).
  So lowering the camera 90 cm sinks the cat 90 cm into the floor unless compensated. Only the gait bob is countered.
  The follow light is attached to SceneRoot [:118-125] and drops with the camera (it is off by default, h:61).
* declaration-proven: GO1 receiver adds a look ROTATION on top of the driven camera's pitch/yaw
  [Plugins/Go1Input/Source/Go1Input/Private/Go1RemoteReceiverComponent.cpp:155-164]; no location read in that file
  (grep GetActorLocation|Translation|.Z: no hits). The eye-height change does not touch the GO1 mapping. No GO1 file
  is read or written by this tool.

PLAN (APPLY): key Camera.HeightOffsetCm on the P05 section only: 0 at segment start S, delta at S+B, delta at E-B,
0 at E (delta = target_eye_cm - live base eye, default 90-180 = -90; B = blend_s*tick, default 1.5 s), cubic with
USER tangents 0, i.e. exactly smoothstep in each ramp. Endpoints keep their old pose, so the Scene handoff
cameras matched to the Passage endpoints stay matched (checked: check_scene_handoffs stale list unchanged and pose
read-back at S and E equal to before). cat_mode "static_interior" (default) raises the P05 rig's
ShadowCatPositionOffset.Z by -delta so the cat stands on the floor through the interior; it then floats up to
-delta cm during the two blend ramps (cat_float_cm). cat_mode "none" leaves the cat sunk by -delta in the interior.
A time-exact fix needs C++ (ShadowFigureRoot countering LocalOffsetCm.Z the way it counters the bob) - not done here.
REFUSES if HeightOffsetCm already has keys or a non-zero default, if LookAheadDistanceCm is non-zero anywhere (the
aim would then tilt with height, cpp:840-856), or if live base eye differs from expected_base_eye_cm by > 0.5 cm.

Writes: the Master sequence (keys) + the level (rig ShadowCatPositionOffset, only for static_interior). Never the
Show. Backups/PreP05CatHeight-<run> holds both packages first. Record p05_cat_height_record.json is written BEFORE
the first write. Save is narrow (Master + current level; any other dirty package stops it). Then
SavedMasterMatchesShow is queued alone; run mode TEST_CUTS afterwards to queue SceneCutBindingsResolve alone.

inferred (the first live run confirms; each is asserted, never trusted): MovieSceneScriptingDoubleChannel exposes
get_default/has_default/set_default/remove_default/add_key/remove_key and its keys set_arrive_tangent/
set_leave_tangent/get_arrive_tangent (USER interpolation enum MovieSceneKeyInterpolation.USER); UE's cubic segment
with zero user tangents is the flat Hermite modelled by eval_keys (checked by pose read-back at 9 ticks, 0.05 cm);
rig.set_editor_property re-runs ConfigureShadowCat (checked by cat child-actor z after evaluate_at_master_frame).

Args (p05_cat_height_args.json via p05_cat_height_run.py):
  {"mode": "DRY"|"APPLY"|"REVERT"|"TEST_CUTS", "confirm": "<MODE> P05CATHEIGHT", "passage_label": "Passage 5",
   "target_eye_cm": 90.0, "blend_s": 1.5, "cat_mode": "static_interior"|"none", "expected_base_eye_cm": 180.0,
   "allow_dirty": []}
Markers: P05CATHEIGHT_DRY_OK / _APPLY_OK / _REVERT_OK / _TEST_QUEUED |run=<id>|...; any stop P05CATHEIGHT_STOPPED.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import shutil

MARK = "P05CATHEIGHT"
VALID_MODES = ("DRY", "APPLY", "REVERT", "TEST_CUTS")
CAT_MODES = ("static_interior", "none")
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                 # p06_tail_extend.py:85
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"   # p06_tail_extend.py:86
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MASTER_TEST = "InfinityStage.Editor.SavedMasterMatchesShow"
CUTS_TEST = "InfinityStage.Editor.SceneCutBindingsResolve"
HEIGHT_CH = "Camera.HeightOffsetCm"
PITCH_CH = "Camera.PitchDegrees"
LOOKAHEAD_CH = "Camera.LookAheadDistanceCm"
RECORD_NAME = "p05_cat_height_record.json"
POS_TOL_CM = 0.05
ROT_TOL_DEG = 0.01
BASE_TOL_CM = 0.5
MIN_INTERIOR_S = 1.0


class P05Error(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise P05Error(message)


def _finite(value, label):
    value = float(value)
    require(math.isfinite(value), "ARG_NOT_FINITE|" + label)
    return value


# ----------------------------------------------------------------------------------------------- pure key maths
def check_args(args):
    args = dict(args or {})
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in VALID_MODES, "MODE_INVALID|" + mode)
    if mode != "DRY":
        require(args.get("confirm") == "%s %s" % (mode, MARK), "CONFIRM_MISSING|need='%s %s'" % (mode, MARK))
    out = {
        "mode": mode, "confirm": args.get("confirm"),
        "passage_label": str(args.get("passage_label", "Passage 5")),
        "target_eye_cm": _finite(args.get("target_eye_cm", 90.0), "target_eye_cm"),
        "blend_s": _finite(args.get("blend_s", 1.5), "blend_s"),
        "pitch_up_deg": _finite(args.get("pitch_up_deg", 0.0), "pitch_up_deg"),
        "cat_mode": str(args.get("cat_mode", "static_interior")),
        "expected_base_eye_cm": _finite(args.get("expected_base_eye_cm", 180.0), "expected_base_eye_cm"),
        "allow_dirty": sorted(str(x) for x in (args.get("allow_dirty") or [])),
    }
    require(out["cat_mode"] in CAT_MODES, "CAT_MODE_INVALID|" + out["cat_mode"])
    require(20.0 <= out["target_eye_cm"] <= 300.0, "TARGET_EYE_OUT_OF_RANGE|%r" % out["target_eye_cm"])
    require(0.25 <= out["blend_s"] <= 5.0, "BLEND_OUT_OF_RANGE|%r" % out["blend_s"])
    require(abs(out["pitch_up_deg"]) <= 15.0, "PITCH_OUT_OF_RANGE|%r" % out["pitch_up_deg"])
    return out


def smoothstep(u):
    u = min(1.0, max(0.0, float(u)))
    return u * u * (3.0 - 2.0 * u)


def eval_keys(keys, tick, default=0.0):
    """Value of a channel whose keys are cubic with zero USER tangents (flat Hermite = smoothstep per span).
    Constant extrapolation outside the keys; the default when there are none."""
    if not keys:
        return float(default)
    keys = sorted(keys, key=lambda k: k[0])
    if tick <= keys[0][0]:
        return float(keys[0][1])
    if tick >= keys[-1][0]:
        return float(keys[-1][1])
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= tick <= t1:
            if t1 == t0:
                return float(v1)
            return float(v0) + (float(v1) - float(v0)) * smoothstep((tick - t0) / float(t1 - t0))
    raise P05Error("EVAL_UNREACHABLE")


def ramp_keys(seg_start, seg_end, blend_ticks, value):
    """0 at S, value at S+B and E-B, 0 at E (absolute Master ticks)."""
    return [[int(seg_start), 0.0], [int(seg_start + blend_ticks), float(value)],
            [int(seg_end - blend_ticks), float(value)], [int(seg_end), 0.0]]


def plan_keys(seg_start, seg_end, tick_rate, base_eye_cm, target_eye_cm, blend_s, pitch_up_deg=0.0):
    seg_start, seg_end = int(seg_start), int(seg_end)
    require(seg_end > seg_start, "SEGMENT_EMPTY|%d..%d" % (seg_start, seg_end))
    require(tick_rate > 0, "TICK_RATE_INVALID")
    blend_ticks = int(round(blend_s * tick_rate))
    interior = seg_end - seg_start - 2 * blend_ticks
    require(interior >= MIN_INTERIOR_S * tick_rate,
            "SEGMENT_TOO_SHORT|len=%d|blend=%d" % (seg_end - seg_start, blend_ticks))
    require(base_eye_cm > 0, "BASE_EYE_INVALID|%r" % base_eye_cm)
    delta = float(target_eye_cm) - float(base_eye_cm)
    plan = {"seg_start": seg_start, "seg_end": seg_end, "tick_rate": float(tick_rate), "blend_ticks": blend_ticks,
            "base_eye_cm": float(base_eye_cm), "target_eye_cm": float(target_eye_cm), "delta_cm": delta,
            "scale": float(target_eye_cm) / float(base_eye_cm),
            "height_keys": ramp_keys(seg_start, seg_end, blend_ticks, delta),
            "pitch_up_deg": float(pitch_up_deg),
            "pitch_keys": ramp_keys(seg_start, seg_end, blend_ticks, pitch_up_deg) if pitch_up_deg else []}
    return plan


def sample_ticks(plan):
    s, e, b = plan["seg_start"], plan["seg_end"], plan["blend_ticks"]
    return sorted(set([s, s + b // 4, s + b // 2, s + b, (s + e) // 2, e - b, e - b // 2, e - b // 4, e]))


def expected_pose(before_pose, plan, tick):
    """before_pose = (x, y, z, pitch, yaw, roll) read with no keys; route frame level (checked live)."""
    x, y, z, pitch, yaw, roll = before_pose
    dz = eval_keys(plan["height_keys"], tick)
    dp = eval_keys(plan["pitch_keys"], tick) if plan["pitch_keys"] else 0.0
    return (x, y, z + dz, pitch + dp, yaw, roll)


def pose_diff(want, got):
    return {"pos": max(abs(a - b) for a, b in zip(want[:3], got[:3])),
            "rot": max(abs(((a - b) + 180.0) % 360.0 - 180.0) for a, b in zip(want[3:], got[3:]))}


def channel_refusals(channels, pitch_up_deg):
    """channels: {name: {"keys": [[tick, value], ...], "default": float|None}}"""
    out = []
    for name in (HEIGHT_CH, PITCH_CH, LOOKAHEAD_CH):
        if name not in channels:
            out.append("CHANNEL_MISSING|" + name)
    if out:
        return out
    h = channels[HEIGHT_CH]
    if h["keys"]:
        out.append("HEIGHT_ALREADY_KEYED|keys=%d (merge not supported; revert/clear first)" % len(h["keys"]))
    if h["default"] not in (None, 0.0) and abs(h["default"]) > 1e-9:
        out.append("HEIGHT_DEFAULT_NONZERO|%r" % h["default"])
    la = channels[LOOKAHEAD_CH]
    if any(abs(v) > 1e-9 for _, v in la["keys"]) or (la["default"] not in (None, 0.0) and abs(la["default"]) > 1e-9):
        out.append("LOOKAHEAD_NONZERO (aim would tilt with height)")
    if pitch_up_deg:
        p = channels[PITCH_CH]
        if p["keys"] or (p["default"] not in (None, 0.0) and abs(p["default"]) > 1e-9):
            out.append("PITCH_ALREADY_AUTHORED")
    return out


def cat_offset_after(old_offset_z, delta_cm, cat_mode):
    return float(old_offset_z) - float(delta_cm) if cat_mode == "static_interior" else float(old_offset_z)


def cat_float_cm(plan, tick, cat_mode):
    """How far the cat's feet sit above (+) / below (-) where they stand today, at one tick (no bob, pitch 0)."""
    h = eval_keys(plan["height_keys"], tick)
    return h - plan["delta_cm"] if cat_mode == "static_interior" else h


def pitch_cat_shift_cm(shadow_figure_offset, pitch_deg):
    """Vertical move of ShadowFigureRoot from TransformVectorNoScale(ShadowFigureOffset) under a camera pitch
    (UE: positive pitch raises +X) [InfinityStageCameraRig.cpp:428]. Height-only plan: pitch 0 -> 0."""
    x, _y, z = shadow_figure_offset
    p = math.radians(pitch_deg)
    return x * math.sin(p) + z * (math.cos(p) - 1.0)


def same_channel(a, b, tol=1e-6):
    if len(a["keys"]) != len(b["keys"]):
        return False
    if (a["default"] is None) != (b["default"] is None):
        return False
    if a["default"] is not None and abs(a["default"] - b["default"]) > tol:
        return False
    return all(ka[0] == kb[0] and abs(ka[1] - kb[1]) <= tol for ka, kb in zip(a["keys"], b["keys"]))


def revert_drift(record, live_height, live_cat_z):
    """Before REVERT: live must equal what APPLY left (else someone edited since)."""
    out = []
    want = {"keys": record["plan"]["height_keys"], "default": record["before"]["height"]["default"]}
    if not same_channel(want, live_height):
        out.append("HEIGHT_DRIFT|live=%s" % json.dumps(live_height))
    if abs(record["after_cat_offset_z"] - live_cat_z) > 1e-4:
        out.append("CAT_OFFSET_DRIFT|want=%r|live=%r" % (record["after_cat_offset_z"], live_cat_z))
    return out


def revert_exact(record, live_height, live_cat_z, live_poses):
    """After REVERT: channel, cat offset and every sampled pose equal the recorded BEFORE state."""
    out = []
    if not same_channel(record["before"]["height"], live_height):
        out.append("HEIGHT_NOT_RESTORED")
    if abs(record["before"]["cat_offset_z"] - live_cat_z) > 1e-4:
        out.append("CAT_OFFSET_NOT_RESTORED")
    for tick, pose in record["before"]["poses"].items():
        d = pose_diff(pose, live_poses[str(tick)])
        if d["pos"] > POS_TOL_CM or d["rot"] > ROT_TOL_DEG:
            out.append("POSE_NOT_RESTORED|tick=%s|%s" % (tick, json.dumps(d)))
    return out


# ----------------------------------------------------------------------------------------------- Unreal side
def _u():
    import unreal  # noqa: PLC0415 - only inside the editor
    return unreal


def _here():
    u = _u()
    return os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()), "CodexConductor")


def _project():
    u = _u()
    return u.Paths.convert_relative_path_to_full(u.Paths.project_dir())


def _log(text):
    _u().log(text)


def unwrap(result, count):
    """UE Python out-params [prec p06_tail_extend.py:472-480]."""
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    if count == 1 and not isinstance(result, tuple):
        return (result,)
    return result if isinstance(result, tuple) and len(result) == count else None


def _guid(value):
    return _u().GuidLibrary.conv_guid_to_string(value)


def _census():
    u = _u()
    return {"maps": sorted(p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": sorted(p.get_path_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def _package_file(package):
    base = os.path.join(_project(), "Content", *package[len("/Game/"):].split("/"))
    for ext in (".uasset", ".umap"):
        if os.path.isfile(base + ext):
            return base + ext
    raise P05Error("PACKAGE_FILE_MISSING|" + package)


def _sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _backup(run, prefix):
    root = os.path.join(_project(), "Backups", prefix + run)
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in (MASTER_PATH, EXPECTED_WORLD):
        src = _package_file(package)
        dst = os.path.join(root, package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(src)[1])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        require(_sha(src) == _sha(dst), "BACKUP_HASH_MISMATCH|" + package)
        rows.append({"package": package, "source": src, "backup": dst, "sha256": _sha(dst)})
    return {"root": root, "packages": rows}


def _context(args):
    u = _u()
    require(os.path.normcase(os.path.normpath(_project())).rstrip("\\/")
            == os.path.normcase(os.path.normpath("E:/PussStage")), "WRONG_PROJECT")
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None and world.get_path_name().split(".")[0] == EXPECTED_WORLD, "WRONG_WORLD")
    require(editor.get_game_world() is None, "PIE_ACTIVE")
    census = _census()
    if args["mode"] != "DRY":
        dirty = set(census["maps"]) | set(census["content"])
        require(dirty <= set(args["allow_dirty"]), "DIRTY_BEFORE|" + json.dumps(census))
    return world, census


def _load(args, world):
    u = _u()
    show, master = u.load_asset(SHOW_PATH), u.load_asset(MASTER_PATH)
    require(show is not None and master is not None, "ASSET_LOAD_FAILED")
    rows = [p for p in show.get_editor_property("passage_settings")
            if str(p.get_editor_property("label")) == args["passage_label"]]
    require(len(rows) == 1, "PASSAGE_ROW_COUNT|%d" % len(rows))
    guid = rows[0].get_editor_property("passage_guid")
    tick = show.get_editor_property("tick_resolution")
    tick_rate = tick.numerator / float(tick.denominator)
    mtick = master.get_tick_resolution()
    require(abs(mtick.numerator / float(mtick.denominator) - tick_rate) < 1e-6,
            "MASTER_TICK_MISMATCH|master=%r|show=%r" % (str(mtick), tick_rate))
    sections = []
    for track in master.get_tracks():
        if track.get_class().get_name() != "MovieSceneInfinityPassageTrack":
            continue
        for sec in track.get_sections():
            if _guid(sec.get_editor_property("passage_guid")) == _guid(guid):
                sections.append(sec)
    require(len(sections) == 1, "PASSAGE_SECTION_COUNT|%d" % len(sections))
    rigs = []
    for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class().get_name() != "InfinityStageCameraRig":
            continue
        pa = actor.get_editor_property("passage_actor")
        if pa is not None and _guid(pa.get_editor_property("passage_guid")) == _guid(guid):
            rigs.append(actor)
    require(len(rigs) == 1, "RIG_COUNT|%d" % len(rigs))
    rng = unwrap(u.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, guid), 2)
    require(rng is not None, "FRAME_RANGE_FAILED")
    return {"show": show, "master": master, "guid": guid, "section": sections[0], "rig": rigs[0],
            "tick_rate": tick_rate, "master_tick": str(mtick), "seg": (int(rng[0]), int(rng[1]))}


def _channel(section, name):
    hits = [c for c in section.get_all_channels()
            if str(c.get_editor_property("channel_name")) == name
            or str(c.get_editor_property("channel_name")).startswith(name + "_")]
    require(len(hits) == 1, "CHANNEL_MATCH|%s|%d" % (name, len(hits)))
    return hits[0]


def _read_channel(ch):
    u = _u()
    keys = []
    for k in ch.get_keys():
        t = int(k.get_time(time_unit=u.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value)
        keys.append([t, float(k.get_value())])
    default = float(ch.get_default()) if ch.has_default() else None
    return {"keys": sorted(keys), "default": default}


def _channels(section):
    out = {}
    for name in (HEIGHT_CH, PITCH_CH, LOOKAHEAD_CH):
        try:
            out[name] = _read_channel(_channel(section, name))
        except P05Error:
            pass
    return out


def _pose(ctx, tick):
    u = _u()
    res = unwrap(u.InfinityStageCameraPilotLibrary.get_passage_camera_pose(ctx["show"], ctx["guid"], int(tick)), 3)
    require(res is not None, "POSE_READ_FAILED|tick=%d" % tick)
    t = res[0].translation
    r = res[0].rotation.rotator()
    return (float(t.x), float(t.y), float(t.z), float(r.pitch), float(r.yaw), float(r.roll))


def _poses(ctx, ticks):
    return {str(t): _pose(ctx, t) for t in ticks}


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _rig_facts(rig):
    return {"label": rig.get_actor_label(), "camera_offset": _vec(rig.get_editor_property("camera_offset")),
            "shadow_figure_offset": _vec(rig.get_editor_property("shadow_figure_offset")),
            "cat_position_offset": _vec(rig.get_editor_property("shadow_cat_position_offset")),
            "cat_scale": float(rig.get_editor_property("shadow_cat_uniform_scale")),
            "follow_light": bool(rig.get_editor_property("enable_follow_light")),
            "camera_bob": bool(rig.get_editor_property("shadow_cat_camera_bob")),
            "crossing_settle_s": float(rig.get_editor_property("crossing_settle_seconds"))}


def _handoffs(show):
    u = _u()
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    res = unwrap(u.InfinityStageSequenceBuilderLibrary.check_scene_handoffs(show, world), 2)  # read-only
    require(res is not None, "HANDOFF_CHECK_FAILED")
    return sorted(_guid(g) for g in res[0])


def _cat_world_z(ctx, tick, restore_transform):
    """Evaluate the rig at one tick, read the cat child actor z, put the rig back where it was."""
    u = _u()
    rig = ctx["rig"]
    require(bool(rig.evaluate_at_master_frame(u.FrameNumber(int(tick)))), "RIG_EVAL_FAILED|%d" % tick)
    comp = rig.get_editor_property("shadow_cat")
    cat = comp.get_editor_property("child_actor") if comp else None
    z = float(cat.get_actor_location().z) if cat else None
    rig.set_actor_transform(restore_transform, False, False)
    return z


def _plan_live(args, ctx):
    s, e = ctx["seg"]
    before = _channels(ctx["section"])
    refusals = channel_refusals(before, args["pitch_up_deg"])
    rig = _rig_facts(ctx["rig"])
    p0 = _pose(ctx, s)
    h0 = eval_keys(before.get(HEIGHT_CH, {}).get("keys", []), s, before.get(HEIGHT_CH, {}).get("default") or 0.0)
    base_eye = p0[2] - h0
    if abs(base_eye - args["expected_base_eye_cm"]) > BASE_TOL_CM:
        refusals.append("BASE_EYE_UNEXPECTED|live=%.3f|expected=%.3f" % (base_eye, args["expected_base_eye_cm"]))
    plan = plan_keys(s, e, ctx["tick_rate"], base_eye, args["target_eye_cm"], args["blend_s"], args["pitch_up_deg"])
    ticks = sample_ticks(plan)
    poses = _poses(ctx, ticks)
    for t, pose in poses.items():
        if abs(pose[3]) > ROT_TOL_DEG or abs(pose[5]) > ROT_TOL_DEG:
            refusals.append("ROUTE_FRAME_NOT_LEVEL|tick=%s|pitch=%.4f|roll=%.4f" % (t, pose[3], pose[5]))
    cat = {"old_offset_z": rig["cat_position_offset"][2],
           "new_offset_z": cat_offset_after(rig["cat_position_offset"][2], plan["delta_cm"], args["cat_mode"]),
           "float_cm_at_samples": {str(t): cat_float_cm(plan, t, args["cat_mode"]) for t in ticks},
           "pitch_shift_cm": pitch_cat_shift_cm(rig["shadow_figure_offset"], args["pitch_up_deg"])}
    return {"plan": plan, "before_channels": before, "rig": rig, "poses_before": poses, "cat": cat,
            "refusals": refusals, "segment": [s, e], "master_tick": ctx["master_tick"],
            "go1": "receiver adds look rotation only (Go1RemoteReceiverComponent.cpp:155-164); no location read"}


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)


def _save_narrow(touch_level):
    u = _u()
    census = _census()
    allowed_maps = {EXPECTED_WORLD} if touch_level else set()
    require(not (set(census["content"]) - {MASTER_PATH}) and not (set(census["maps"]) - allowed_maps),
            "OUT_OF_SCOPE_DIRTY_BEFORE_SAVE|" + json.dumps(census))
    require(u.EditorAssetLibrary.save_asset(MASTER_PATH, only_if_is_dirty=False), "MASTER_SAVE_FAILED")
    if EXPECTED_WORLD in census["maps"]:
        require(u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")
    require(_census() == {"content": [], "maps": []}, "DIRTY_AFTER_SAVE|" + json.dumps(_census()))


def _queue(world, test, run):
    u = _u()
    require(_census() == {"content": [], "maps": []}, "DIRTY_BEFORE_TEST")
    u.SystemLibrary.execute_console_command(world, "Automation RunTests " + test)
    _log("%s_TEST_QUEUED|run=%s|test=%s|alone=true" % (MARK, run, test))


def _add_flat_keys(ch, keys):
    u = _u()
    added = []
    for tick, value in keys:
        key = ch.add_key(u.FrameNumber(int(tick)), float(value), 0.0, u.MovieSceneTimeUnit.TICK_RESOLUTION,
                         u.MovieSceneKeyInterpolation.USER)
        require(key is not None, "ADD_KEY_NONE|tick=%d" % tick)
        added.append(key)
        key.set_arrive_tangent(0.0)
        key.set_leave_tangent(0.0)
        require(abs(float(key.get_arrive_tangent())) < 1e-9 and abs(float(key.get_leave_tangent())) < 1e-9,
                "TANGENT_READBACK|tick=%d" % tick)
    return added


def _remove_keys_at(ch, ticks):
    u = _u()
    ticks = set(int(t) for t in ticks)
    for key in list(ch.get_keys()):
        if int(key.get_time(time_unit=u.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value) in ticks:
            ch.remove_key(key)


def _set_cat_z(rig, z):
    u = _u()
    v = rig.get_editor_property("shadow_cat_position_offset")
    rig.modify()
    rig.set_editor_property("shadow_cat_position_offset", u.Vector(v.x, v.y, float(z)))
    require(abs(float(rig.get_editor_property("shadow_cat_position_offset").z) - float(z)) < 1e-4, "CAT_Z_READBACK")


def _run(raw):
    run = datetime.datetime.now().strftime("P05CH-%Y%m%d-%H%M%S")
    report = {"run": run, "ok": False}
    try:
        args = check_args(raw)
        report["args"] = args
        world, census_before = _context(args)
        mode = args["mode"]
        record_path = os.path.join(_here(), RECORD_NAME)
        if mode == "TEST_CUTS":
            _queue(world, CUTS_TEST, run)
            return
        ctx = _load(args, world)
        if mode in ("DRY", "APPLY"):
            live = _plan_live(args, ctx)
            report.update(live)
            report["handoff_stale_before"] = _handoffs(ctx["show"])
            plan = live["plan"]
            if mode == "DRY":
                require(_census() == census_before, "DRY_CENSUS_CHANGED")
                report.update({"ok": True, "apply_ready": not live["refusals"]})
                path = os.path.join(_here(), "p05_cat_height_report_DRY_%s.json" % run)
                _write_json(path, report)
                _log("%s_DRY_OK|run=%s|seg=%d..%d|base_eye=%.3f|target=%.3f|delta=%.3f|blend_ticks=%d|cat_offset=%.3f->%.3f"
                     "|max_cat_float=%.3f|refusals=%d|report=%s" % (
                         MARK, run, plan["seg_start"], plan["seg_end"], plan["base_eye_cm"], plan["target_eye_cm"],
                         plan["delta_cm"], plan["blend_ticks"], live["cat"]["old_offset_z"], live["cat"]["new_offset_z"],
                         max(abs(v) for v in live["cat"]["float_cm_at_samples"].values()), len(live["refusals"]), path))
                return
            require(not live["refusals"], "REFUSED|" + json.dumps(live["refusals"]))
            require(not os.path.exists(record_path), "RECORD_EXISTS|revert first|" + record_path)
            touch_level = args["cat_mode"] == "static_interior"
            backup = _backup(run, "PreP05CatHeight-")
            restore_tf = ctx["rig"].get_actor_transform()
            cat_mid_before = _cat_world_z(ctx, (plan["seg_start"] + plan["seg_end"]) // 2, restore_tf)
            record = {"version": 1, "run": run, "args": args, "plan": plan, "backup": backup,
                      "segment": live["segment"], "rig_label": live["rig"]["label"],
                      "before": {"height": live["before_channels"][HEIGHT_CH],
                                 "pitch": live["before_channels"][PITCH_CH],
                                 "cat_offset_z": live["cat"]["old_offset_z"], "poses": live["poses_before"],
                                 "cat_world_z_mid": cat_mid_before},
                      "after_cat_offset_z": live["cat"]["new_offset_z"], "status": "WRITING"}
            with open(record_path, "x", encoding="utf-8") as handle:
                json.dump(record, handle, indent=1, sort_keys=True, default=str)
            hch = _channel(ctx["section"], HEIGHT_CH)
            pch = _channel(ctx["section"], PITCH_CH)
            try:
                _add_flat_keys(hch, plan["height_keys"])
                if plan["pitch_keys"]:
                    _add_flat_keys(pch, plan["pitch_keys"])
                if touch_level:
                    _set_cat_z(ctx["rig"], live["cat"]["new_offset_z"])
                got = _read_channel(hch)
                require(same_channel({"keys": plan["height_keys"], "default": live["before_channels"][HEIGHT_CH]["default"]},
                                     got), "HEIGHT_READBACK|" + json.dumps(got))
                worst = {"pos": 0.0, "rot": 0.0}
                for t, pose in live["poses_before"].items():
                    d = pose_diff(expected_pose(pose, plan, int(t)), _pose(ctx, int(t)))
                    worst = {k: max(worst[k], d[k]) for k in worst}
                    require(d["pos"] <= POS_TOL_CM and d["rot"] <= ROT_TOL_DEG, "POSE_READBACK|tick=%s|%s" % (t, d))
                cat_mid_after = _cat_world_z(ctx, (plan["seg_start"] + plan["seg_end"]) // 2, restore_tf)
                if touch_level and cat_mid_before is not None:
                    require(cat_mid_after is not None and abs(cat_mid_after - cat_mid_before) < 1.0,
                            "CAT_NOT_GROUNDED|before=%r|after=%r" % (cat_mid_before, cat_mid_after))
                require(_handoffs(ctx["show"]) == report["handoff_stale_before"], "HANDOFF_STALENESS_CHANGED")
            except Exception:
                _remove_keys_at(hch, [k[0] for k in plan["height_keys"]])
                if plan["pitch_keys"]:
                    _remove_keys_at(pch, [k[0] for k in plan["pitch_keys"]])
                if touch_level:
                    _set_cat_z(ctx["rig"], live["cat"]["old_offset_z"])
                ctx["rig"].set_actor_transform(restore_tf, False, False)
                _log("%s_ROLLED_BACK_IN_MEMORY|run=%s|NOTHING SAVED|if census stays dirty: Don't-Save restart" % (MARK, run))
                raise
            _save_narrow(touch_level)
            record.update({"status": "APPLIED", "readback_worst": worst, "cat_world_z_mid_after": cat_mid_after})
            _write_json(record_path, record)
            _log("%s_APPLY_OK|run=%s|keys=%d|delta=%.3f|worst_pos=%.4f|worst_rot=%.4f|cat_mid=%r->%r|backup=%s|record=%s"
                 "|tests_required_singly=%s,%s" % (MARK, run, len(plan["height_keys"]), plan["delta_cm"], worst["pos"],
                                                   worst["rot"], cat_mid_before, cat_mid_after, backup["root"],
                                                   record_path, MASTER_TEST, CUTS_TEST))
            _queue(world, MASTER_TEST, run)
            return
        # REVERT
        require(os.path.isfile(record_path), "NO_RECORD")
        with open(record_path, encoding="utf-8") as handle:
            record = json.load(handle)
        require(record.get("status") in ("APPLIED", "WRITING"), "RECORD_STATUS|%r" % record.get("status"))
        hch = _channel(ctx["section"], HEIGHT_CH)
        pch = _channel(ctx["section"], PITCH_CH)
        cat_z = float(ctx["rig"].get_editor_property("shadow_cat_position_offset").z)
        drift = revert_drift(record, _read_channel(hch), cat_z)
        require(not drift, "REVERT_DRIFT|" + json.dumps(drift))
        backup = _backup(run, "PreP05CatHeightRevert-")
        _remove_keys_at(hch, [k[0] for k in record["plan"]["height_keys"]])
        if record["plan"]["pitch_keys"]:
            _remove_keys_at(pch, [k[0] for k in record["plan"]["pitch_keys"]])
        touch_level = abs(cat_z - record["before"]["cat_offset_z"]) > 1e-6
        if touch_level:
            _set_cat_z(ctx["rig"], record["before"]["cat_offset_z"])
        live_poses = _poses(ctx, [int(t) for t in record["before"]["poses"]])
        bad = revert_exact(record, _read_channel(hch),
                           float(ctx["rig"].get_editor_property("shadow_cat_position_offset").z), live_poses)
        require(not bad, "REVERT_NOT_EXACT|" + json.dumps(bad))
        _save_narrow(touch_level)
        record.update({"status": "REVERTED", "revert_run": run, "revert_backup": backup})
        os.replace(record_path, record_path.replace(".json", ".reverted-%s.json" % run))
        _write_json(record_path.replace(".json", ".reverted-%s.json" % run), record)
        _log("%s_REVERT_OK|run=%s|backup=%s" % (MARK, run, backup["root"]))
        _queue(world, MASTER_TEST, run)
    except Exception as error:
        _u().log_error("%s_STOPPED|run=%s|%s" % (MARK, run, error))
        raise


if __name__ == "__p05_cat_height_runner__":
    _run(globals().get("P05CATHEIGHT_ARGS") or {})
