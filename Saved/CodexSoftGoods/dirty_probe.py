"""READ-ONLY: list dirty content and map packages, and the undo buffer's next undo title. Logs PUSS_SOFTGOODS_DIRTY|..."""
import unreal


def main():
    c = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"PUSS_SOFTGOODS_DIRTY|content={c}|maps={m}")


main()
