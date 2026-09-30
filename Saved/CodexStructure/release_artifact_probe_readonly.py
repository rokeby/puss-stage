"""Read-only: exercise p04_backcloth_section_apply.release_from_artifact on every GeometryCache in the
project (without running that script's main). Mutates nothing."""
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    src = open(os.path.join(HERE, "p04_backcloth_section_apply.py"), encoding="utf-8").read()
    ns = {"__name__": "probe"}
    exec(compile(src.rsplit("\nmain()", 1)[0], "p04_backcloth_section_apply", "exec"), ns)
    rows = []
    for path in unreal.EditorAssetLibrary.list_assets("/Game", recursive=True, include_folder=False):
        if str(unreal.EditorAssetLibrary.find_asset_data(path).asset_class_path.asset_name) == "GeometryCache":
            rows.append(f"{path.split('.')[0]} -> {ns['release_from_artifact'](unreal.load_asset(path))}")
    unreal.log("RELEASE_ARTIFACT_PROBE|" + " || ".join(rows))


main()
