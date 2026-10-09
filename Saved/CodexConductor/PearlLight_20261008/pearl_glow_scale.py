"""Scale the S3 Drama Pearl Glow intensity KEYS in LS_DevScene_03 by one factor (Gary 9 Oct, option B: the light at
~15 %, the cello swell kept in shape).  Keys, not the component default: a PIE-side set_intensity does not stick
(measured 8 Oct, pearl_variant_shots) because the sequence re-evaluates the 'S3.Drama.Light' Intensity track every tick.

ARGS pearl_glow_scale_args.json {"mode": DRY|APPLY|REVERT|PIEREAD, "confirm": "<MODE> PEARLGLOW", "run": "<id>",
                                 "factor": 0.15, "pie_scene_frame": 4400}
  DRY     editor idle, census clean; reads the one Intensity track under the "S3 Drama Pearl Glow" binding (exactly one
          track, one section, one channel) -> pearl_glow_scale_dry_<run>.json. Mutates nothing.
  APPLY   record (originals, fsync + read-back, path printed) -> Backups/PreS3PearlGlow-<run>/LS_DevScene_03.uasset ->
          every key value x factor -> read back -> census (only LS_DevScene_03 newly dirty) -> save_asset(scene only) ->
          read back after save -> PEARLGLOW_APPLY_OK.  Refuses while an applied record exists.
  REVERT  the recorded original values, frame-matched, same gates.
  PIEREAD read-only, PIE running (after MiScalars/pvs_scrub_4400): the PIE light component intensity vs the recorded
          scaled channel evaluated at pie_scene_frame (linear keys) -> PEARLGLOW_PIEREAD_OK|match=0/1.
Never Save All, never the map, no UE objects at module level, never ends PIE.
Markers PEARLGLOW_<MODE>_OK|run=.. / PEARLGLOW_FAILED|run=..|reason (after a set: do NOT save; Don't-Save restart).
"""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/PearlLight_20261008/"
ARGS = HERE + "pearl_glow_scale_args.json"
REC = HERE + "pearl_glow_scale_record.json"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
SCENE_FILE = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
LABEL = "S3 Drama Pearl Glow"
TOL = 1e-3


class Stop(RuntimeError):
    pass


def keys_of(ch):
    return sorted((int(k.get_time().frame_number.value), float(k.get_value())) for k in ch.get_keys())


def eval_linear(keys, frame):
    if not keys:
        return None
    if frame <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if f0 <= frame <= f1:
            return v0 + (v1 - v0) * (frame - f0) / float(f1 - f0) if f1 != f0 else v1
    return keys[-1][1]


def same(a, b):
    return len(a) == len(b) and all(fa == fb and abs(va - vb) <= TOL * max(1.0, abs(vb)) for (fa, va), (fb, vb) in zip(a, b))


def main():
    import unreal as u
    a = json.load(open(ARGS, encoding="utf-8"))
    run, mode = str(a["run"]), str(a["mode"]).upper()
    factor = float(a.get("factor", 0.15))
    state = {"mutated": False}

    def stop(reason):
        tail = "|NOT saved: Don't-Save restart" if state["mutated"] else ""
        u.log_error("PEARLGLOW_FAILED|run=%s|mode=%s|%s%s" % (run, mode, reason, tail))
        raise Stop(reason)

    if not 0.01 <= factor <= 1.0:
        stop("FACTOR_RANGE|%s" % factor)
    if mode != "DRY" and a.get("confirm") != "%s PEARLGLOW" % mode:
        stop("CONFIRM|need '%s PEARLGLOW'" % mode)
    ed = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    pie = ed.get_game_world()

    if mode == "PIEREAD":
        if pie is None:
            stop("NO_PIE")
        rec = json.load(open(REC, encoding="utf-8"))
        frame = int(a.get("pie_scene_frame", 4400))
        hits = [x for x in u.GameplayStatics.get_all_actors_of_class(pie, u.Actor) if x.get_actor_label() == LABEL]
        if len(hits) != 1:
            stop("PIE_LIGHT_COUNT|%d" % len(hits))
        lc = hits[0].get_component_by_class(u.LightComponent)
        got = float(lc.get_editor_property("intensity"))
        want_now = eval_linear([tuple(k) for k in rec.get("final", rec["originals"]["keys"])], frame)
        want_orig = eval_linear([tuple(k) for k in rec["originals"]["keys"]], frame)
        ok = want_now is not None and abs(got - want_now) <= max(0.05, 0.02 * abs(want_now))
        out = {"run": run, "scene_frame": frame, "pie_intensity": got, "expected_scaled": want_now,
               "expected_original": want_orig, "match": ok, "visible": bool(lc.is_visible())}
        json.dump(out, open(HERE + "pearl_glow_pieread_%s.json" % run, "w"), indent=1)
        u.log("PEARLGLOW_PIEREAD_OK|run=%s|frame=%d|pie=%.4f|expected=%s|original=%s|match=%d" % (
            run, frame, got, want_now, want_orig, int(ok)))
        return

    if pie is not None:
        stop("PIE_RUNNING")
    lib = u.EditorLoadingAndSavingUtils

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))

    c0 = census()
    if c0 != ([], []):
        stop("DIRTY_AT_START|%s" % (c0,))

    def find_channel(scene):
        found = []
        for b in scene.get_bindings():
            p = b.get_parent()
            owner = str(p.get_display_name()) if p is not None and p.is_valid() else str(b.get_display_name())
            if owner != LABEL:
                continue
            for t in b.get_tracks():
                if isinstance(t, u.MovieSceneFloatTrack) and str(t.get_property_name()) == "Intensity":
                    found.append((str(b.get_display_name()), t))
        if len(found) != 1:
            stop("TRACK_COUNT|%d|%s" % (len(found), [f[0] for f in found]))
        secs = found[0][1].get_sections()
        if len(secs) != 1:
            stop("SECTION_COUNT|%d" % len(secs))
        chs = list(secs[0].get_all_channels())
        if len(chs) != 1:
            stop("CHANNEL_COUNT|%d" % len(chs))
        return found[0][0], found[0][1], chs[0]

    scene = u.load_asset(SCENE)
    if scene is None:
        stop("SCENE_LOAD")
    bname, track, ch = find_channel(scene)
    keys = keys_of(ch)
    if not keys:
        stop("NO_KEYS")

    if mode == "DRY":
        out = {"run": run, "binding": bname, "track": str(track.get_display_name()), "keys": keys, "factor": factor,
               "scaled": [(f, v * factor) for f, v in keys], "peak": max(v for _, v in keys)}
        p = HERE + "pearl_glow_scale_dry_%s.json" % run
        json.dump(out, open(p, "w"), indent=1)
        u.log("PEARLGLOW_DRY_OK|run=%s|mutated=0|binding=%s|keys=%d|peak=%.4f|peak_after=%.4f|file=%s" % (
            run, bname, len(keys), out["peak"], out["peak"] * factor, p))
        return

    if mode == "APPLY":
        if os.path.exists(REC) and json.load(open(REC, encoding="utf-8")).get("state") in ("applying", "applied"):
            stop("RECORD_APPLIED|REVERT or retire %s first" % REC)
        target = [(f, v * factor) for f, v in keys]
        rec = {"run": run, "state": "applying", "factor": factor, "binding": bname, "originals": {"keys": keys}}
    elif mode == "REVERT":
        rec = json.load(open(REC, encoding="utf-8"))
        if rec.get("state") != "applied":
            stop("RECORD_STATE|%s" % rec.get("state"))
        if not same(keys, [tuple(k) for k in rec["final"]]):
            stop("CHANGED_SINCE_APPLY|now=%s" % keys)
        target = [tuple(k) for k in rec["originals"]["keys"]]
    else:
        stop("MODE|%s" % mode)

    with open(REC, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if json.load(open(REC, encoding="utf-8"))["originals"]["keys"] != json.loads(json.dumps(rec["originals"]["keys"])):
        stop("RECORD_READBACK")
    u.log("PEARLGLOW_RECORD|run=%s|path=%s" % (run, REC))
    bdir = "E:/PussStage/Backups/PreS3PearlGlow-%s" % run
    os.makedirs(bdir, exist_ok=False)
    shutil.copy2(SCENE_FILE, bdir)
    if os.path.getsize(os.path.join(bdir, os.path.basename(SCENE_FILE))) != os.path.getsize(SCENE_FILE):
        stop("BACKUP_SIZE")

    state["mutated"] = True
    scene.modify()
    tmap = dict(target)
    for k in ch.get_keys():
        f = int(k.get_time().frame_number.value)
        k.set_value(float(tmap[f]))      # return ignored: read back below
    if not same(keys_of(ch), target):
        stop("READBACK_AFTER_SET|%s" % keys_of(ch))
    c1 = census()
    if c1[1] or [p for p in c1[0] if p != SCENE]:
        stop("CENSUS|%s" % (c1,))
    if not u.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False):
        stop("SAVE_FAILED")
    _, _, ch2 = find_channel(u.load_asset(SCENE))
    final = keys_of(ch2)
    if not same(final, target):
        stop("READBACK_AFTER_SAVE|%s" % final)
    if census() != ([], []):
        stop("DIRTY_AFTER_SAVE|%s" % (census(),))
    rec.update(state="applied" if mode == "APPLY" else "reverted", final=final, backup=bdir, last_run=run)
    json.dump(rec, open(REC, "w", encoding="utf-8"), indent=1)
    u.log("PEARLGLOW_%s_OK|run=%s|keys=%d|peak_was=%.4f|peak_now=%.4f|saved=%s|backup=%s|record=%s" % (
        mode, run, len(final), max(v for _, v in keys), max(v for _, v in final), SCENE, bdir, REC))


try:
    main()
except Stop:
    pass
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("PEARLGLOW_FAILED|unexpected %s: %s" % (type(exc).__name__, exc))
