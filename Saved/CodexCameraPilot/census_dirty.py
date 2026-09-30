"""Read-only census of BOTH dirty lists (maps and content), stamped with a run id.
get_dirty_content_packages() does NOT include maps (30 Sep), so both are always printed.
Success marker: PUSS_DIRTY_CENSUS"""
import datetime
import unreal


def main():
    maps = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    content = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    run_id = "lookcam-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    pie = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None
    unreal.log("PUSS_DIRTY_CENSUS|run=%s|pie=%s|dirty_maps=%s|dirty_content=%s" % (run_id, pie, maps, content))


main()
