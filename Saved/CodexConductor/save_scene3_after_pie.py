"""Save LS_DevScene_03 once PIE has ended, only if it is the sole dirty package (finishes S3ENV-20261008-064956 APPLY,
whose save was refused because Gary started PIE).  Verifies the graze lift is in memory first.  SAVE_S3_OK / SAVE_S3_FAILED."""
def main():
    import unreal
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    SC = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
    d = ([p.get_name() for p in lib.get_dirty_content_packages()], [p.get_name() for p in lib.get_dirty_map_packages()])
    if d[0] != [SC]:
        raise RuntimeError("CENSUS|%s" % (d,))
    seq = unreal.load_asset(SC)
    got = None
    for b in seq.get_bindings():
        p = b.get_parent()
        if p is not None and p.is_valid() and str(p.get_display_name()) == "S3 Drama Graze L1":
            for t in b.get_tracks():
                if str(t.get_display_name()) == "S3.Drama.Light":
                    got = {int(k.get_time().frame_number.value): round(k.get_value()) for k in t.get_sections()[0].get_all_channels()[0].get_keys()}
    if not got or got.get(3960) != 3750:
        raise RuntimeError("LIFT_NOT_IN_MEMORY|%s" % got)
    if not unreal.EditorAssetLibrary.save_asset(SC, only_if_is_dirty=False):
        raise RuntimeError("SAVE")
    unreal.log("SAVE_S3_OK|graze_L1=%s" % sorted(got.items()))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("SAVE_S3_FAILED|%r" % (exc,))
