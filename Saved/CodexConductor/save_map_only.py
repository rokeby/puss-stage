"""Save ONLY the main level when it is the sole dirty package (Gary 8 Oct: "Save it"). SAVE_MAP_OK / SAVE_MAP_FAILED."""
def main():
    import unreal
    lib = unreal.EditorLoadingAndSavingUtils
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    d = ([p.get_name() for p in lib.get_dirty_content_packages()], [p.get_name() for p in lib.get_dirty_map_packages()])
    if d != ([], ["/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"]):
        raise RuntimeError("CENSUS|%s" % (d,))
    if not lib.save_dirty_packages(True, False):
        raise RuntimeError("SAVE")
    unreal.log("SAVE_MAP_OK")
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("SAVE_MAP_FAILED|%r" % (exc,))
