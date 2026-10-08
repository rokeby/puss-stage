"""S3 shot fixes (Gary 8 Oct ~02:50 UTC questionnaire):
  1. The clam is the NEW S3 PearlClam: hide Clam_with_Pearl_Clam_with_Pearl_0 for the whole scene (rise Visibility key at
     125 -> False; float-hold Visibility default -> False).
  2. The B07 orbit (S3.VampOrbit, 721 keys, centre (14421.97, 160000) r 200 [measured probe_b06]) re-centred on the risen
     PearlClam: location keys + (1062.43, 169.5, 22.0); rotations untouched (yaw still points at the centre).
  3. B06 -> the clam emergence 0:45-1:00: "move and reaim but only after it stops looking at the wall and turns to the
     clam, which it does for the last third of the shot".  Only B06's LAST THIRD (keys 3236 -> 3449: it turns from the
     wall to yaw -31.3, i.e. the new clam [measured: clam bearing -29.8]) is used [inferred reading]: its location is
     interpolated over Scene 1080 -> 1440 and its rotation is re-aimed every 24 frames at the clam's centre as it rises
     (clam pivot Z -28.03 -> 119.02, Y 160147.1 -> 160169.5, centre = pivot + 22 cm [measured]).  The old 3 keys are
     replaced (kept in the record).  B06's cut [3000, 3480] -> [1080, 1440]; 2:05-2:25 then falls to S3 Wide (Gary: "go to
     the wide for now").
Record s3_shots_fix_record.json + Backups/PreS3ShotsFix-<run> (scene + rise) first; saves those two only.
Args s3_shots_fix_args.json {"mode":"DRY"|"APPLY","confirm":"APPLY S3SHOTS","run":..}.  S3SHOTS_<MODE>_OK / S3SHOTS_FAILED."""
import json
import math
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_shots_fix_record.json"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset",
         "E:/PussStage/Content/InfinityStage/RigAtmos/LS_S3_HangarRise.uasset"]
OLD_CLAM = "Clam_with_Pearl_Clam_with_Pearl_0"
ORBIT_OLD_C = (14421.973, 160000.0)
CLAM_X = 15484.4
CLAM_Y = (160147.109, 160169.5)
CLAM_Z = (-28.03 + 22.0, 119.018 + 22.0)
ORBIT_D = (CLAM_X - ORBIT_OLD_C[0], CLAM_Y[1] - ORBIT_OLD_C[1], 22.0)
B06_FROM = (3236, 3449)
B06_TO = (1080, 1440)
B06_CUT = ((3000, 3480), (1080, 1440))
STEP = 24
RUN = {"run": "?"}


def look(px, py, pz, tx, ty, tz):
    dx, dy, dz = tx - px, ty - py, tz - pz
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return pitch, yaw


def main():
    import unreal
    a = json.load(open(HERE + "s3_shots_fix_args.json"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise RuntimeError("SEQUENCER_OPEN")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: ([p.get_name() for p in lib.get_dirty_content_packages()], [p.get_name() for p in lib.get_dirty_map_packages()])
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    scene, rise = unreal.load_asset(SCENE), unreal.load_asset(RISE)
    fr = lambda k: int(k.get_time().frame_number.value)

    def chans(seq, name, cls=None, track=None):
        out = {}
        for b in seq.get_bindings():
            if str(b.get_display_name()) != name:
                continue
            for t in b.get_tracks():
                if cls and t.get_class().get_name() != cls:
                    continue
                if track and str(t.get_display_name()) != track:
                    continue
                for s in t.get_sections():
                    for ch in s.get_all_channels():
                        out[str(ch.get_name()).rsplit("_", 1)[0]] = ch
        return out
    # 1. old clam
    rv = chans(rise, OLD_CLAM, "MovieSceneVisibilityTrack")
    hv = chans(scene, "S3 Hangar Float Hold: " + OLD_CLAM, "MovieSceneVisibilityTrack")
    if len(rv) != 1 or len(hv) != 1:
        raise RuntimeError("OLD_CLAM_TRACKS|%d|%d" % (len(rv), len(hv)))
    rch, hch = list(rv.values())[0], list(hv.values())[0]
    rkeys = [(fr(k), bool(k.get_value())) for k in rch.get_keys()]
    if rkeys != [(0, False), (125, True)] or hch.get_num_keys() != 0:
        raise RuntimeError("OLD_CLAM_SHAPE|%s|hold_keys=%d" % (rkeys, hch.get_num_keys()))
    # 2. orbit
    orb = chans(scene, "S3 Shot B07", track="S3.VampOrbit")
    loc = {c: orb.get("Location." + c) for c in "XYZ"}
    if any(v is None or v.get_num_keys() != 721 for v in loc.values()):
        raise RuntimeError("ORBIT_SHAPE")
    xs = [k.get_value() for k in loc["X"].get_keys()]
    ys = [k.get_value() for k in loc["Y"].get_keys()]
    c_now = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2)
    if abs(c_now[0] - ORBIT_OLD_C[0]) > 1 or abs(c_now[1] - ORBIT_OLD_C[1]) > 1:
        raise RuntimeError("ORBIT_CENTRE|%s" % (c_now,))
    # 3. B06
    b6 = chans(scene, "S3 Shot B06", "MovieScene3DTransformTrack")
    need = ["Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z"]
    if any(n not in b6 for n in need):
        raise RuntimeError("B06_CHANNELS|%s" % sorted(b6))
    b6_before = {n: [(fr(k), float(k.get_value())) for k in ch.get_keys()] for n, ch in b6.items()}
    lx = dict(b6_before["Location.X"]); ly = dict(b6_before["Location.Y"]); lz = dict(b6_before["Location.Z"])
    if sorted(lx) != [3002, 3236, 3449]:
        raise RuntimeError("B06_KEYS|%s" % sorted(lx))
    p0 = (lx[B06_FROM[0]], ly[B06_FROM[0]], lz[B06_FROM[0]])
    p1 = (lx[B06_FROM[1]], ly[B06_FROM[1]], lz[B06_FROM[1]])
    plan = []
    f = B06_TO[0]
    while True:
        u = (f - B06_TO[0]) / float(B06_TO[1] - B06_TO[0])
        e = u * u * (3 - 2 * u)
        p = tuple(p0[i] + (p1[i] - p0[i]) * e for i in range(3))
        t = (CLAM_X, CLAM_Y[0] + (CLAM_Y[1] - CLAM_Y[0]) * u, CLAM_Z[0] + (CLAM_Z[1] - CLAM_Z[0]) * u)
        pitch, yaw = look(p[0], p[1], p[2], *t)
        plan.append((f, p, (0.0, pitch, yaw)))
        if f == B06_TO[1]:
            break
        f = min(f + STEP, B06_TO[1])
    cut6 = None
    for mt in scene.get_tracks():
        if mt.get_class().get_name() != "MovieSceneCameraCutTrack":
            continue
        for s in mt.get_sections():
            g = s.get_camera_binding_id().get_editor_property("guid").export_text()
            cam = next((str(b.get_display_name()) for b in scene.get_bindings() if b.get_id().export_text() == g), None)
            if cam == "S3 Shot B06" and (s.get_start_frame(), s.get_end_frame()) == B06_CUT[0]:
                cut6 = s
    if cut6 is None:
        raise RuntimeError("B06_CUT")
    summary = {"orbit_delta": [round(v, 2) for v in ORBIT_D], "b06_keys": len(plan),
               "b06_first": [round(v, 1) for v in plan[0][1] + plan[0][2]], "b06_last": [round(v, 1) for v in plan[-1][1] + plan[-1][2]]}
    if mode == "DRY":
        unreal.log("S3SHOTS_DRY_OK|run=%s|%s" % (run, json.dumps(summary)))
        return
    if a.get("confirm") != "APPLY S3SHOTS" or os.path.exists(REC):
        raise RuntimeError("CONFIRM_OR_RECORD")
    json.dump({"run": run, "state": "applying", "rise_old_clam": rkeys, "hold_default": hch.get_default(),
               "b06_before": b6_before, "b06_cut_before": B06_CUT[0], "orbit_delta": ORBIT_D, "plan": plan},
              open(REC, "w"), indent=1)
    bdir = "E:/PussStage/Backups/PreS3ShotsFix-%s" % run
    os.makedirs(bdir)
    for x in FILES:
        shutil.copy2(x, bdir)
    scene.modify()
    rise.modify()
    for k in rch.get_keys():
        if fr(k) == 125:
            k.set_value(False)
    hch.set_default(False)
    for c, d in zip("XYZ", ORBIT_D):
        for k in loc[c].get_keys():
            k.set_value(k.get_value() + d)
    for n in need:
        for k in list(b6[n].get_keys()):
            b6[n].remove_key(k)
    idx = {"Location.X": (1, 0), "Location.Y": (1, 1), "Location.Z": (1, 2),
           "Rotation.X": (2, 0), "Rotation.Y": (2, 1), "Rotation.Z": (2, 2)}
    for n in need:
        part, i = idx[n]
        for row in plan:
            b6[n].add_key(unreal.FrameNumber(row[0]), float(row[part][i]), time_unit=DR,
                          interpolation=unreal.MovieSceneKeyInterpolation.AUTO)
    cut6.set_range(*B06_CUT[1])
    # read back
    if [bool(k.get_value()) for k in rch.get_keys()] != [False, False] or hch.get_default() is not False:
        raise RuntimeError("OLD_CLAM_READBACK|NOTHING SAVED; Don't-Save restart")
    xs2 = [k.get_value() for k in loc["X"].get_keys()]
    if abs((max(xs2) + min(xs2)) / 2 - (c_now[0] + ORBIT_D[0])) > 0.5:
        raise RuntimeError("ORBIT_READBACK|NOTHING SAVED; Don't-Save restart")
    if b6["Rotation.Z"].get_num_keys() != len(plan) or (cut6.get_start_frame(), cut6.get_end_frame()) != B06_CUT[1]:
        raise RuntimeError("B06_READBACK|NOTHING SAVED; Don't-Save restart")
    if sorted(dirty()[0]) != sorted([SCENE, RISE]) or dirty()[1]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
    for p in (SCENE, RISE):
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            raise RuntimeError("SAVE|%s" % p)
    if dirty() != ([], []):
        raise RuntimeError("DIRTY_AFTER|%s" % (dirty(),))
    r = json.load(open(REC)); r["state"] = "applied"; json.dump(r, open(REC, "w"), indent=1)
    unreal.log("S3SHOTS_APPLY_OK|run=%s|%s" % (run, json.dumps(summary)))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3SHOTS_FAILED|run=%s|%r" % (RUN["run"], exc))
