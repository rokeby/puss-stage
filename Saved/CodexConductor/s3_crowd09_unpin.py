"""S3 Crowd 09 unpin (8 Oct): the only copy the body fix skipped (Body offset < 20 cm, S3CROWDBODY-20261008-1), so its
constant ABSOLUTE transform section in LS_Clams still overrides the level placement written by S3REGATHER-20261008-1
[meas PIE t=200: pelvis (13436, 160424) = old spot].  Removes that one section (defaults recorded) so the regathered
level transform holds, like the other 14.  Record s3_crowd09_unpin_record.json + backup; REVERT re-adds it.
Args s3_crowd09_unpin_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3C09"}.  S3C09_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_crowd09_unpin_record.json"
CLAMS = "/Game/Scenes/LS_Clams"
def main():
    import unreal
    a = json.load(open(HERE + "s3_crowd09_unpin_args.json")); mode = a["mode"]
    run = datetime.datetime.now().strftime("S3C09-%Y%m%d-%H%M%S")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    clams = unreal.load_asset(CLAMS)
    crec = json.load(open(HERE + "s3_crowd_structure_record.json"))
    g = [c["actor_binding_guid"] for c in crec["copies"] if c["label"].startswith("S3 Crowd 09 (")][0]
    b = [x for x in clams.get_bindings() if x.get_id().export_text() == g][0]
    t = [x for x in b.get_tracks() if isinstance(x, unreal.MovieScene3DTransformTrack)][0]
    def absolute(s):
        bt = s.get_blend_type(); v = str(bt.get_editor_property("blend_type")).upper() if bt.get_editor_property("is_valid") else "UNSET"
        return "ADDITIVE" not in v and "RELATIVE" not in v
    abs_s = [s for s in t.get_sections() if absolute(s)]
    if mode == "DRY":
        unreal.log("S3C09_DRY_OK|abs_sections=%d" % len(abs_s)); return
    if a.get("confirm") != "%s S3C09" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3C09-%s" % run; os.makedirs(bd); shutil.copy2("E:/PussStage/Content/Scenes/LS_Clams.uasset", bd)
    if mode == "APPLY":
        if os.path.exists(REC) or len(abs_s) != 1: raise RuntimeError("PRECONDITION|%d" % len(abs_s))
        s = abs_s[0]; ch = {str(c.get_name()).split("_")[0]: c for c in s.get_all_channels()}
        if any(len(c.get_keys()) for c in ch.values()): raise RuntimeError("KEYED_NOT_CONSTANT")
        json.dump({"run": run, "backup": bd, "range": [int(s.get_start_frame()), int(s.get_end_frame())],
                   "defaults": {k: float(c.get_default()) for k, c in ch.items() if c.has_default()}}, open(REC, "w"), indent=1)
        t.remove_section(s)
    elif mode == "REVERT":
        r = json.load(open(REC)); s = t.add_section(); s.set_range(*r["range"]); s.set_blend_type(unreal.MovieSceneBlendType.ABSOLUTE)
        ch = {str(c.get_name()).split("_")[0]: c for c in s.get_all_channels()}
        for k, v in r["defaults"].items(): ch[k].set_default(v)
    if census() != ([CLAMS], []): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(CLAMS, only_if_is_dirty=False) or census() != ([], []): raise RuntimeError("SAVE")
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3C09_%s_OK|run=%s|abs_left=%d|backup=%s" % (mode, run, len([s for s in t.get_sections() if absolute(s)]), bd))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3C09_FAILED|%r" % (exc,))
