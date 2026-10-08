"""Remove the S3 shore figures' mid-chorus TELEPORT keys (Gary 8 Oct evening, own words: "remove the teleport, that was
me fudging a hidden movement of the figures"). P21C DRY [measured]: each of the five figures' Transform track (absolute)
has keys at 1461, 3144, 3145 (LS_Clams display frames), with the jump between 3144 and 3145. Removing the 3144 and 3145
keys on every channel leaves each figure at its 1461 pose for the rest of the scene.
Args s3_remove_teleport_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3NOTELEPORT", "frames": [3144, 3145]}.
Record + Backups/PreS3NoTeleport-<run>; saves only the sequence that owns the tracks. S3NOTELEPORT_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil
import unreal
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_remove_teleport_record.json"
FIGS = ["Shore01_M56", "Shore02_F52", "Shore03_M59", "Shore04_F55", "Shore06_F25"]
SEQS = ["/Game/Scenes/LS_Clams", "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"]


def pkg_file(path):
    base = "E:/PussStage/Content/" + path[len("/Game/"):]
    return base + ".uasset"


def main():
    a = json.load(open(HERE + "s3_remove_teleport_args.json"))
    mode, frames = a["mode"], [int(x) for x in a.get("frames", [3144, 3145])]
    run = datetime.datetime.now().strftime("S3NOTP-%Y%m%d-%H%M%S")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    dirty = lambda: ([p.get_name() for p in lib.get_dirty_content_packages()], [p.get_name() for p in lib.get_dirty_map_packages()])
    if dirty() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (dirty(),))
    hits = []   # (seq_path, seq, fig, channel)
    for sp in SEQS:
        seq = unreal.load_asset(sp)
        for b in seq.get_bindings():
            nm = str(b.get_display_name())
            fig = next((f for f in FIGS if nm.startswith(f)), None)
            if not fig: continue
            for t in b.get_tracks():
                if t.get_class().get_name() != "MovieScene3DTransformTrack": continue
                for s in t.get_sections():
                    bt = s.get_blend_type()
                    txt = str(bt) + (str(bt.to_tuple()) if hasattr(bt, "to_tuple") else "")
                    if "ADDITIVE" in txt: continue
                    for ch in s.get_all_channels():
                        hits.append((sp, seq, fig, s, ch))
    found = {}
    for sp, seq, fig, s, ch in hits:
        ks = [(int(k.get_time().frame_number.value), float(k.get_value())) for k in ch.get_keys() if int(k.get_time().frame_number.value) in frames]
        if ks: found.setdefault(sp, {}).setdefault(fig, {})[str(ch.get_name())] = ks
    figs_found = sorted({f for d in found.values() for f in d})
    if mode == "DRY":
        unreal.log("S3NOTELEPORT_DRY_OK|run=%s|seqs=%s|figures=%s|keys=%d" % (run, sorted(found), figs_found, sum(len(v) for d in found.values() for c in d.values() for v in c.values())))
        return
    if a.get("confirm") != "%s S3NOTELEPORT" % mode: raise RuntimeError("CONFIRM")
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        if sorted(figs_found) != sorted(FIGS) or len(found) != 1: raise RuntimeError("UNEXPECTED|%s|%s" % (sorted(found), figs_found))
        sp = list(found)[0]
        bd = "E:/PussStage/Backups/PreS3NoTeleport-" + run; os.makedirs(bd); shutil.copy2(pkg_file(sp), bd)
        json.dump({"run": run, "seq": sp, "frames": frames, "removed": found[sp], "backup": bd}, open(REC, "w"), indent=1)
        seq = unreal.load_asset(sp); seq.modify()
        for _sp, _seq, fig, s, ch in hits:
            if _sp != sp: continue
            for k in list(ch.get_keys()):
                if int(k.get_time().frame_number.value) in frames: ch.remove_key(k)
        left = [(fig, str(ch.get_name())) for _sp, _seq, fig, s, ch in hits if _sp == sp and any(int(k.get_time().frame_number.value) in frames for k in ch.get_keys())]
        if left: raise RuntimeError("READBACK_LEFT|%s|NOTHING SAVED; Don't-Save restart" % left)
        if dirty() != ([sp], []): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (dirty(),))
        if not unreal.EditorAssetLibrary.save_asset(sp, only_if_is_dirty=False) or dirty() != ([], []): raise RuntimeError("SAVE")
        unreal.log("S3NOTELEPORT_APPLY_OK|run=%s|seq=%s|figures=%d|backup=%s" % (run, sp, len(found[sp]), bd))
    elif mode == "REVERT":
        rec = json.load(open(REC)); seq = unreal.load_asset(rec["seq"]); seq.modify()
        DR = unreal.MovieSceneTimeUnit.DISPLAY_RATE
        for _sp, _seq, fig, s, ch in hits:
            if _sp != rec["seq"]: continue
            for f, v in rec["removed"].get(fig, {}).get(str(ch.get_name()), []):
                ch.add_key(unreal.FrameNumber(int(f)), float(v), time_unit=DR, interpolation=unreal.MovieSceneKeyInterpolation.CONSTANT)
        if not unreal.EditorAssetLibrary.save_asset(rec["seq"], only_if_is_dirty=False): raise RuntimeError("SAVE")
        os.rename(REC, REC + ".reverted-" + run)
        unreal.log("S3NOTELEPORT_REVERT_OK|run=%s" % run)


try:
    main()
except Exception as e:
    unreal.log_error("S3NOTELEPORT_FAILED|%r" % (e,))
