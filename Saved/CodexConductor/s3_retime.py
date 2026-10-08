"""S3 retime to the audio (Gary 8 Oct ~02:05 UTC questionnaire):
  clam rise -> 0:45-1:00 (was Scene frames 3593-4170), lights follow; B07 orbit -> the cello 1:00-2:00 (was 145-175 s,
  stretched x2); B04's move -> 145-175 s (was 60-120 s, compressed x0.5); figures' teleport -> exactly on the 1:00 cut
  (Gary: "the point is to teleport them when camera's distracted"); cut trims B02 15-30 s, B03 30-45 s.
All frames are display frames @24 in LS_DevScene_03 unless named.  LS_Clams is nested at Scene -1 with start offset 21
frames [measured probe_s3_shots run 20261008-020233: range [-1, 6313], start_offset_ticks 21000 @1000 ticks/frame], so
LS_Clams frame = Scene frame + 22 [inferred: rate 1].
Moves are by key TIME only (values untouched).  Every moved key is recorded (sequence, binding, track, channel, from, to)
in s3_retime_record.json BEFORE any change; backups Backups/PreS3Retime-<run>/.  REVERT moves them back and restores
the cut/section ranges.  Saves LS_DevScene_03 and LS_Clams only.
Args s3_retime_args.json {"mode":"DRY"|"APPLY"|"REVERT","confirm":"<MODE> S3RETIME","run":..}.
Markers S3RETIME_<MODE>_OK|run=.. / S3RETIME_FAILED|run=..|reason."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_retime_record.json"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
CLAMS = "/Game/Scenes/LS_Clams"
FILES = ["E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset", "E:/PussStage/Content/Scenes/LS_Clams.uasset"]
RUN = {"run": "?"}

CLAM_MAP = {3593: 1080, 4170: 1440}                      # clam/lid/mantle/pearl/millstone transform + vis keys
CLAM_WORDS = ("PearlClam", "Granite Mills")
DRAMA_MAP = {"S3 Drama Clam Key": {3593: 1080, 4170: 1440},
             "S3 Drama Pearl Glow": {3593: 1080, 3700: 1147, 4170: 1440, 4290: 1560}}
B07 = {"cut": (3480, 4200), "to": (1440, 2880)}          # orbit x2
B04 = {"cut": (1440, 2880), "to": (3480, 4200)}          # move x0.5
TRIMS = {"S3 Shot B02": ((360, 960), (360, 720)), "S3 Shot B03": ((782, 1440), (720, 1080))}
FIG_MAP = {1494: 1461, 1495: 1462}                        # LS_Clams frames: teleport onto Scene 1439/1440 (the cut)


def lin(t, a, b):
    return int(round(b[0] + (t - a[0]) * float(b[1] - b[0]) / float(a[1] - a[0])))


def main():
    import unreal
    a = json.load(open(HERE + "s3_retime_args.json", encoding="utf-8"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        raise RuntimeError("SEQUENCER_OPEN")
    lib = unreal.EditorLoadingAndSavingUtils
    DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if census() != ([], []):
        raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    scene, clams = unreal.load_asset(SCENE), unreal.load_asset(CLAMS)
    fr = lambda k: int(k.get_time().frame_number.value)

    def owner(b):
        p = b.get_parent()
        return str(p.get_display_name()) if p is not None and p.is_valid() else ""

    moves = []      # (key, from, to, desc)
    sections = []   # (section, (from_lo, from_hi), (to_lo, to_hi), desc)

    def chan_keys(t):
        for s in t.get_sections():
            for ch in s.get_all_channels():
                try:
                    ks = list(ch.get_keys())
                except Exception:
                    continue
                yield s, ch, ks

    bindings = list(scene.get_bindings())
    by_name = {}
    for b in bindings:
        by_name.setdefault(str(b.get_display_name()), []).append(b)
    # A. clam rise
    n_clam = 0
    for b in bindings:
        nm = str(b.get_display_name())
        if not any(w in nm for w in CLAM_WORDS):
            continue
        for t in b.get_tracks():
            for s, ch, ks in chan_keys(t):
                for k in ks:
                    if fr(k) in CLAM_MAP:
                        moves.append((k, fr(k), CLAM_MAP[fr(k)], "clam|%s|%s|%s" % (nm, t.get_display_name(), ch.get_name())))
                        n_clam += 1
    # B. drama lights (component bindings; owner = actor label)
    n_drama = 0
    for b in bindings:
        lab = owner(b)
        if lab not in DRAMA_MAP:
            continue
        for t in b.get_tracks():
            if str(t.get_display_name()) != "S3.Drama.Light":
                continue
            for s, ch, ks in chan_keys(t):
                for k in ks:
                    if fr(k) in DRAMA_MAP[lab]:
                        moves.append((k, fr(k), DRAMA_MAP[lab][fr(k)], "drama|%s" % lab))
                        n_drama += 1
    # C. cameras: cuts by camera name, and their keys
    cut_secs = {}
    for mt in scene.get_tracks():
        if mt.get_class().get_name() != "MovieSceneCameraCutTrack":
            continue
        for s in mt.get_sections():
            g = s.get_camera_binding_id().get_editor_property("guid").export_text()
            cam = next((str(b.get_display_name()) for b in bindings if b.get_id().export_text() == g), None)
            cut_secs.setdefault(cam, []).append(s)

    def one_cut(cam, rng):
        hits = [s for s in cut_secs.get(cam, []) if (s.get_start_frame(), s.get_end_frame()) == tuple(rng)]
        if len(hits) != 1:
            raise RuntimeError("CUT_NOT_FOUND|%s|%s|have=%s" % (cam, rng, [(s.get_start_frame(), s.get_end_frame()) for s in cut_secs.get(cam, [])]))
        return hits[0]
    if mode != "REVERT":
        sections.append((one_cut("S3 Shot B07", B07["cut"]), B07["cut"], B07["to"], "cut|B07"))
        sections.append((one_cut("S3 Shot B04", B04["cut"]), B04["cut"], B04["to"], "cut|B04"))
        for cam, (fr_, to_) in TRIMS.items():
            sections.append((one_cut(cam, fr_), fr_, to_, "cut|" + cam))
    n_cam = 0
    for cam, spec in (("S3 Shot B07", B07), ("S3 Shot B04", B04)):
        bs = [b for b in bindings if str(b.get_display_name()) == cam or owner(b) == cam]
        if not bs:
            raise RuntimeError("CAMERA_BINDING|%s" % cam)
        for b in bs:
            for t in b.get_tracks():
                if t.get_class().get_name() == "MovieSceneSpawnTrack":
                    continue
                for s, ch, ks in chan_keys(t):
                    for k in ks:
                        if spec["cut"][0] <= fr(k) <= spec["cut"][1] + 1:
                            moves.append((k, fr(k), lin(fr(k), spec["cut"], spec["to"]),
                                          "cam|%s|%s|%s" % (cam, t.get_display_name(), ch.get_name())))
                            n_cam += 1
                    if str(t.get_display_name()) == "S3.VampOrbit" and mode != "REVERT" and not any(x[0] == s for x in sections):
                        lo, hi = s.get_start_frame(), s.get_end_frame()
                        sections.append((s, (lo, hi), (lin(lo, spec["cut"], spec["to"]), lin(hi - 1, spec["cut"], spec["to"]) + 1),
                                         "sec|B07 VampOrbit"))
    # D. LS_Clams figure teleport
    n_fig = 0
    for b in clams.get_bindings():
        for t in b.get_tracks():
            for s, ch, ks in chan_keys(t):
                for k in ks:
                    if fr(k) in FIG_MAP:
                        moves.append((k, fr(k), FIG_MAP[fr(k)], "fig|%s|%s|%s" % (b.get_display_name(), t.get_display_name(), ch.get_name())))
                        n_fig += 1
    summary = {"clam": n_clam, "drama": n_drama, "cam": n_cam, "fig": n_fig, "sections": [d for _, _, _, d in sections]}

    if mode == "DRY":
        json.dump({"run": run, "summary": summary, "moves": [(f, t, d) for _, f, t, d in moves],
                   "sections": [(list(f), list(t), d) for _, f, t, d in sections]},
                  open(HERE + "s3_retime_dry.json", "w"), indent=1)
        unreal.log("S3RETIME_DRY_OK|run=%s|%s" % (run, json.dumps(summary)))
        return
    if mode == "APPLY":
        if a.get("confirm") != "APPLY S3RETIME" or os.path.exists(REC):
            raise RuntimeError("CONFIRM_OR_RECORD_EXISTS")
        if n_clam == 0 or n_drama != 6 or n_fig == 0 or n_cam == 0:
            raise RuntimeError("UNEXPECTED_COUNTS|%s" % summary)
        rec = {"run": run, "state": "applying", "summary": summary,
               "moves": [(f, t, d) for _, f, t, d in moves], "sections": [(list(f), list(t), d) for _, f, t, d in sections]}
        json.dump(rec, open(REC, "w"), indent=1)
        bdir = "E:/PussStage/Backups/PreS3Retime-%s" % run
        os.makedirs(bdir)
        for f in FILES:
            shutil.copy2(f, bdir)
        scene.modify()
        clams.modify()
        # sections first (widen before keys land), then keys
        for s, f_, t_, d in sections:
            s.set_range(int(t_[0]), int(t_[1]))
        for k, f, t, d in moves:
            k.set_time(unreal.FrameNumber(t), 0.0, DR)
        bad = [d for k, f, t, d in moves if fr(k) != t] + \
              [d for s, f_, t_, d in sections if (s.get_start_frame(), s.get_end_frame()) != tuple(t_)]
        if bad:
            raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % bad[:5])
    else:
        raise RuntimeError("MODE (REVERT: restore from Backups/PreS3Retime-<run> with a Don't-Save restart + file copy; "
                           "in-editor revert not implemented for this first pass)")
    c1 = census()
    if c1 != (sorted([SCENE, CLAMS]), []):
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (c1,))
    for p in (SCENE, CLAMS):
        if not unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False):
            raise RuntimeError("SAVE_FAILED|%s" % p)
    if census() != ([], []):
        raise RuntimeError("DIRTY_AFTER|%s" % (census(),))
    rec["state"] = "applied"
    json.dump(rec, open(REC, "w"), indent=1)
    unreal.log("S3RETIME_APPLY_OK|run=%s|%s|backup=%s" % (run, json.dumps(summary), bdir))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3RETIME_FAILED|run=%s|%r" % (RUN["run"], exc))
