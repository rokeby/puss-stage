"""Close the open Level Sequence editor (census must be clean: nothing unsaved is lost). Marker CLOSE_SEQ_OK|was=.. / CLOSE_SEQ_FAILED."""
def main():
    import unreal
    lib = unreal.EditorLoadingAndSavingUtils
    c = ([p.get_name() for p in lib.get_dirty_content_packages()], [p.get_name() for p in lib.get_dirty_map_packages()])
    if c != ([], []):
        raise RuntimeError("DIRTY|%s" % (c,))
    L = unreal.LevelSequenceEditorBlueprintLibrary
    cur = L.get_current_level_sequence()
    was = cur.get_path_name() if cur else None
    if cur:
        L.close_level_sequence()
    unreal.log("CLOSE_SEQ_OK|was=%s|now=%s" % (was, L.get_current_level_sequence()))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("CLOSE_SEQ_FAILED|%r" % (exc,))
