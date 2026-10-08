"""S3 opening (Gary 8 Oct): total dark, dim rig folds up, figures appear IN THE DARK after the rig has settled, then the
ghost light, then the wave lights fade up.  (The strike group goes to 0 and the practicals to 15 cd via
s3_light_levels.py, a separate run.)

Measured timeline before this tool (probe_s3_opening.json run 20261008-002325; rise 30 fps nested 1:1 at Scene 0,
LS_DevScene_03 24 fps):  root lands 4.0 s, roof 4.0-8.8 s, lattice 8.8-12.8 s, figures visible at rise frame 139
(4.8 s), wave lights 0 -> lit at Scene frame 240 (10 s), ghost light unkeyed (always 60 cd).

Edits (args s3_opening_args.json; plan values are in seconds):
  A. LS_S3_HangarRise: every Visibility key with value True at FIG_FROM_FRAME (139) -> figures_s.  (Zero keys and the
     float hold, which holds True after the fold, are untouched.)
  B. LS_DevScene_03: the 7 'S3.WavesV3.Light' tracks: the 0-key at the strike -> waves_start_s, the lit key ->
     waves_full_s (linear ramp).  End key untouched.
  C. LS_DevScene_03: a new Intensity track 'S3.Opening.Ghost' on S3 Ghost Light's component: 0 to ghost_s, linear to
     its current intensity at ghost_s + ghost_ramp_s, held to the Scene end.
Saves ONLY the two sequences (map untouched).  Record s3_opening_record.json + Backups/PreS3Opening-<run>/ first.
REVERT restores A/B key times and removes C's binding.  Markers S3OPEN_<MODE>_OK|run=.. / S3OPEN_FAILED|run=..|reason."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_opening_record.json"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
FILES = ["E:/PussStage/Content/InfinityStage/RigAtmos/LS_S3_HangarRise.uasset",
         "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"]
FIG_FROM_FRAME = 139
WAVE_TRACK = "S3.WavesV3.Light"
GHOST_TRACK = "S3.Opening.Ghost"
GHOST_LABEL = "S3 Ghost Light"
RUN = {"run": "?"}


def _f(k):
    return int(k.get_time().frame_number.value)


def main():
    import unreal
    a = json.load(open(HERE + "s3_opening_args.json", encoding="utf-8"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    c0 = census()
    if RISE in c0[0] or SCENE in c0[0]:
        raise RuntimeError("SEQ_ALREADY_DIRTY|%s" % (c0[0],))
    rise, scene = unreal.load_asset(RISE), unreal.load_asset(SCENE)
    rfps = rise.get_display_rate().numerator / float(rise.get_display_rate().denominator)
    sfps = scene.get_display_rate().numerator / float(scene.get_display_rate().denominator)
    if abs(rfps - 30.0) > 1e-6 or abs(sfps - 24.0) > 1e-6:
        raise RuntimeError("FPS|%s|%s" % (rfps, sfps))
    end = int(scene.get_playback_end())

    # ---- A: figure visibility keys in the rise
    vis = []
    for b in rise.get_bindings():
        for t in b.get_tracks():
            if t.get_class().get_name() != "MovieSceneVisibilityTrack":
                continue
            for s in t.get_sections():
                for ch in s.get_all_channels():
                    for k in ch.get_keys():
                        if bool(k.get_value()):
                            vis.append((str(b.get_display_name()), k))
    # ---- B: wave light tracks
    waves = []
    for b in scene.get_bindings():
        for t in b.get_tracks():
            if str(t.get_display_name()) != WAVE_TRACK:
                continue
            p = b.get_parent()
            owner = str(p.get_display_name()) if p is not None and p.is_valid() else str(b.get_display_name())
            for s in t.get_sections():
                chs = list(s.get_all_channels())
                if len(chs) != 1:
                    raise RuntimeError("WAVE_CHANNELS|%s" % owner)
                ks = sorted(chs[0].get_keys(), key=_f)
                if len(ks) != 4 or abs(ks[0].get_value()) > 1e-6 or abs(ks[1].get_value()) > 1e-6 \
                        or ks[2].get_value() <= 0 or abs(ks[3].get_value() - ks[2].get_value()) > 1e-4:
                    raise RuntimeError("WAVE_SHAPE|%s|%s" % (owner, [(_f(k), k.get_value()) for k in ks]))
                waves.append((owner, ks))
    # ---- C: ghost
    w = ed.get_editor_world()
    ghosts = [x for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor) if str(x.get_actor_label()) == GHOST_LABEL]
    if len(ghosts) != 1:
        raise RuntimeError("GHOST_COUNT|%d" % len(ghosts))
    gcomp = ghosts[0].get_component_by_class(unreal.LightComponent)
    ghost_existing = [b for b in scene.get_bindings() for t in b.get_tracks() if str(t.get_display_name()) == GHOST_TRACK]

    state = {"vis": sorted(set((n, _f(k)) for n, k in vis)),
             "waves": {o: [(_f(k), round(k.get_value(), 3)) for k in ks] for o, ks in waves},
             "ghost_intensity": gcomp.intensity, "ghost_track": len(ghost_existing), "end": end}
    if mode == "DRY":
        unreal.log("S3OPEN_DRY_OK|run=%s|vis=%d|waves=%d|ghost_cd=%.1f|ghost_track=%d|census=%s|%s" % (
            run, len(vis), len(waves), gcomp.intensity, len(ghost_existing), c0, json.dumps(state)[:1500]))
        return

    if mode == "APPLY":
        if a.get("confirm") != "APPLY S3OPEN" or os.path.exists(REC):
            raise RuntimeError("CONFIRM_OR_RECORD_EXISTS")
        if ghost_existing:
            raise RuntimeError("GHOST_TRACK_EXISTS")
        if len(waves) != 7:
            raise RuntimeError("WAVE_COUNT|%d" % len(waves))
        bad = [(n, _f(k)) for n, k in vis if _f(k) != FIG_FROM_FRAME]
        if bad or not vis:
            raise RuntimeError("VIS_UNEXPECTED|%s" % bad[:5])
        P = a["plan"]
        fig = int(round(P["figures_s"] * rfps))
        w0, w1 = int(round(P["waves_start_s"] * sfps)), int(round(P["waves_full_s"] * sfps))
        g0, g1 = int(round(P["ghost_s"] * sfps)), int(round((P["ghost_s"] + P["ghost_ramp_s"]) * sfps))
        if not (FIG_FROM_FRAME < fig < 744 * 30 / 24 and 0 < g0 < g1 < w0 < w1 < end):
            raise RuntimeError("PLAN_ORDER|fig=%d g=%d-%d w=%d-%d" % (fig, g0, g1, w0, w1))
        gcd = float(gcomp.intensity)
        rec = {"run": run, "state": "applying", "before": state, "plan": P,
               "frames": {"fig": fig, "ghost": [g0, g1], "waves": [w0, w1]}, "ghost_cd": gcd}
        json.dump(rec, open(REC, "w"), indent=1)
        bdir = "E:/PussStage/Backups/PreS3Opening-%s" % run
        os.makedirs(bdir)
        for f in FILES:
            shutil.copy2(f, bdir)
        rise.modify()
        scene.modify()
        for n, k in vis:
            k.set_time(unreal.FrameNumber(fig), 0.0, DR)
        for o, ks in waves:
            ks[2].set_time(unreal.FrameNumber(w1), 0.0, DR)
            ks[1].set_time(unreal.FrameNumber(w0), 0.0, DR)
        b = scene.add_possessable(gcomp)
        t = b.add_track(unreal.MovieSceneFloatTrack)
        t.set_property_name_and_path("Intensity", "Intensity")
        t.set_display_name(GHOST_TRACK)
        s = t.add_section()
        s.set_range(0, end + 1)
        ch = list(s.get_all_channels())[0]
        for fr, v in ((0, 0.0), (g0, 0.0), (g1, gcd), (end, gcd)):
            ch.add_key(unreal.FrameNumber(fr), v, time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        rec["ghost_binding"] = str(b.get_id())
        # read back
        if sorted(set(_f(k) for _, k in vis)) != [fig]:
            raise RuntimeError("VIS_READBACK|NOTHING SAVED; Don't-Save restart")
        for o, ks in waves:
            if [_f(k) for k in ks][1:3] != [w0, w1]:
                raise RuntimeError("WAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % o)
        got = sorted([(_f(k), round(k.get_value(), 3)) for k in ch.get_keys()])
        if got != [(0, 0.0), (g0, 0.0), (g1, round(gcd, 3)), (end, round(gcd, 3))]:
            raise RuntimeError("GHOST_READBACK|%s|NOTHING SAVED; Don't-Save restart" % got)
    elif mode == "REVERT":
        if a.get("confirm") != "REVERT S3OPEN" or not os.path.exists(REC):
            raise RuntimeError("CONFIRM_OR_NO_RECORD")
        rec = json.load(open(REC))
        rise.modify()
        scene.modify()
        for n, k in vis:
            k.set_time(unreal.FrameNumber(FIG_FROM_FRAME), 0.0, DR)
        for o, ks in waves:
            orig = rec["before"]["waves"][o]
            ks[1].set_time(unreal.FrameNumber(orig[1][0]), 0.0, DR)
            ks[2].set_time(unreal.FrameNumber(orig[2][0]), 0.0, DR)
        for b in ghost_existing:
            b.remove()
        if [b for b in scene.get_bindings() for t in b.get_tracks() if str(t.get_display_name()) == GHOST_TRACK]:
            raise RuntimeError("GHOST_REMOVE_READBACK|NOTHING SAVED; Don't-Save restart")
        for o, ks in waves:
            if [[_f(k), round(k.get_value(), 3)] for k in sorted(ks, key=_f)] != [list(x) for x in rec["before"]["waves"][o]]:
                raise RuntimeError("WAVE_REVERT_READBACK|%s" % o)
    else:
        raise RuntimeError("MODE")
    c1 = census()
    extra = sorted(set(c1[0]) - set(c0[0]))
    if extra != sorted([RISE, SCENE]) or c1[1] != c0[1]:
        raise RuntimeError("CENSUS|%s|%s|NOTHING SAVED; Don't-Save restart" % (extra, c1[1]))
    for pkg in (RISE, SCENE):
        if not unreal.EditorAssetLibrary.save_asset(pkg, only_if_is_dirty=False):
            raise RuntimeError("SAVE_FAILED|%s" % pkg)
    if set(census()[0]) & {RISE, SCENE}:
        raise RuntimeError("DIRTY_AFTER_SAVE")
    if mode == "APPLY":
        rec["state"] = "applied"
        json.dump(rec, open(REC, "w"), indent=1)
        unreal.log("S3OPEN_APPLY_OK|run=%s|vis=%d->%d|ghost=%s|waves=%s|saved=2" % (
            run, len(vis), rec["frames"]["fig"], rec["frames"]["ghost"], rec["frames"]["waves"]))
    else:
        os.rename(REC, REC + ".reverted-" + run)
        unreal.log("S3OPEN_REVERT_OK|run=%s" % run)


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3OPEN_FAILED|run=%s|%r" % (RUN["run"], exc))
