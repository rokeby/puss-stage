"""S3 FIRE VISIBILITY BIND (9 Oct).  [meas] S3 polish DRY stopped VISIBILITY_TRACK_BINDING: the fire emitters' visibility
tracks (s3_fires.py:95-98, keys 0=False, ignite=True = VISIBLE semantics) carry property None.  Gary 9 Oct: "the fire
effects/niagaras that give off smoke are visible before we even settle the rig, they float" -> inert [inferred].
Binds every property-None visibility track on bindings "S3 Fire A/B/C" and "S3 Ghost Light Flame" in LS_DevScene_03 to
("bHidden","bHidden") (rule 9); keys untouched.  Record + backup; REVERT restores None.
Args s3_fire_vis_bind_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3FIREVIS"}.  S3FIREVIS_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_fire_vis_bind_record.json"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
SCENE_FILE = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset"
NAMES = ("S3 Fire A", "S3 Fire B", "S3 Fire C", "S3 Ghost Light Flame")


def main():
    import unreal
    a = json.load(open(HERE + "s3_fire_vis_bind_args.json")); mode = a["mode"]
    run = datetime.datetime.now().strftime("S3FIREVIS-%Y%m%d-%H%M%S")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    seq = unreal.load_asset(SCENE)
    rows = []
    for b in seq.get_bindings():
        if str(b.get_display_name()) not in NAMES: continue
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieSceneVisibilityTrack):
                rows.append((b, t, str(t.get_property_name())))
    def desc(t):
        out = []
        for s in t.get_sections():
            ch = list(s.get_all_channels())[0]
            out.append({"active": bool(s.is_active()), "range": [s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None],
                        "default": ch.get_default() if ch.has_default() else None,
                        "keys": [[int(k.get_time().frame_number.value), bool(k.get_value())] for k in ch.get_keys()]})
        return out
    plan = [(str(b.get_display_name()), str(t.get_name()), p, desc(t)) for b, t, p in rows]
    if mode == "DRY":
        unreal.log("S3FIREVIS_DRY_OK|tracks=%s" % plan); return
    if a.get("confirm") != "%s S3FIREVIS" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3FireVis-%s" % run; os.makedirs(bd); shutil.copy2(SCENE_FILE, bd)
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        todo = [(b, t) for b, t, p in rows if p in ("None", "")]
        json.dump({"run": run, "backup": bd, "changed": [[str(b.get_display_name()), str(t.get_name())] for b, t in todo]}, open(REC, "w"), indent=1)
        for b, t in todo: t.set_property_name_and_path("bHidden", "bHidden")
        bad = [str(b.get_display_name()) for b, t in todo if str(t.get_property_name()) != "bHidden"]
    else:
        rec = json.load(open(REC)); want = {tuple(x) for x in rec["changed"]}
        todo = [(b, t) for b, t, p in rows if (str(b.get_display_name()), str(t.get_name())) in want]
        for b, t in todo: t.set_property_name_and_path("", "")
        bad = []
    if bad: raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % bad)
    if census() != ([SCENE], []): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False) or census() != ([], []): raise RuntimeError("SAVE")
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3FIREVIS_%s_OK|run=%s|n=%d|backup=%s" % (mode, run, len(todo), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3FIREVIS_FAILED|%r" % (exc,))
