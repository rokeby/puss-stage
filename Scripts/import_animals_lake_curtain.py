"""Import the Animals by the Lake transition curtain into the project.

Run with UnrealEditor-Cmd -ExecutePythonScript=... . The script is deliberately
idempotent and does not modify the current map or Director show data.
"""

import os
from pathlib import Path

import unreal


def _stage_materials_root() -> Path:
    """The shared-drive folder holding FBX source art.

    Set PUSS_DRIVE_ROOT to the "2026. SHS 3 Evenings" folder. The macOS Google
    Drive path below is only a fallback and does not exist on Windows.
    """
    override = os.environ.get("PUSS_DRIVE_ROOT")
    if override:
        return Path(override) / "Stage Materials"
    return (
        Path.home()
        / "Library/CloudStorage/GoogleDrive-gary@zhexi.info/Shared drives"
        / "GZZ Studio Drive/Projects/2026. SHS 3 Evenings/Stage Materials"
    )


SOURCE_FBX = str(
    _stage_materials_root()
    / "FBX/Animals by the Lake/SM_Opening_Curtain_Animals_by_the_Lake_cool.fbx"
)
DESTINATION_PATH = "/Game/Stage/ContainedPieces/AnimalsByLake"
ASSET_NAME = "SM_Opening_Curtain_Animals_by_the_Lake_cool"
ASSET_PATH = f"{DESTINATION_PATH}/{ASSET_NAME}"


def main() -> None:
    library = unreal.EditorAssetLibrary
    if library.does_asset_exist(ASSET_PATH):
        unreal.log(f"StageWingDirector curtain already exists: {ASSET_PATH}")
        return

    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_materials", True)
    options.set_editor_property("import_textures", True)
    options.static_mesh_import_data.set_editor_property("combine_meshes", True)
    options.static_mesh_import_data.set_editor_property(
        "generate_lightmap_u_vs", True
    )

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", SOURCE_FBX)
    task.set_editor_property("destination_path", DESTINATION_PATH)
    task.set_editor_property("destination_name", ASSET_NAME)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("save", True)
    task.set_editor_property("options", options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    if not library.does_asset_exist(ASSET_PATH):
        raise RuntimeError(f"FBX import did not create {ASSET_PATH}")

    library.save_directory(DESTINATION_PATH, only_if_is_dirty=False, recursive=True)
    unreal.log(f"Imported StageWingDirector curtain: {ASSET_PATH}")


main()
