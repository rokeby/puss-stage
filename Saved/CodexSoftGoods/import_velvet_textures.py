"""Guarded import for the procedural crushed-velvet texture pair."""

import json
import os

import unreal


def main():
    expected_world = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
    destination = "/Game/Scenes/Curtain/Chaos/Textures"
    names = ("T_CurtainVelvetCrush", "T_CurtainVelvetCrush_N")

    def finish(detail):
        clean = str(detail).replace("\r", " ").replace("\n", " ")
        return unreal.log(f"PUSS_SOFTGOODS_VELVET_IMPORT|{clean}")

    try:
        saved_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
        project_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        mode_path = os.path.join(saved_dir, "CodexSoftGoods", "import_velvet_textures_mode.json")
        with open(mode_path, encoding="utf-8") as handle:
            mode = json.load(handle)
        if set(mode) != {"dry_run"} or not isinstance(mode["dry_run"], bool):
            return finish(f"refused: mode must be exactly {{'dry_run': true|false}}, got {mode!r}")
        dry_run = mode["dry_run"]

        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            return finish("refused: PIE is running")
        world = editor.get_editor_world()
        actual_world = None if world is None else world.get_path_name().split(".", 1)[0]
        if actual_world != expected_world:
            return finish(f"refused: unexpected world {actual_world}")

        dirty_before = sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        )
        if dirty_before:
            return finish(f"refused: dirty content packages before import {dirty_before}")

        sources = {
            name: os.path.join(
                project_dir,
                "DerivedAssets",
                "CurtainCloth",
                "Textures",
                name + ".png",
            )
            for name in names
        }
        missing_sources = sorted(path for path in sources.values() if not os.path.isfile(path))
        if missing_sources:
            return finish(f"refused: missing source files {missing_sources}")

        asset_paths = {name: f"{destination}/{name}" for name in names}
        existing = sorted(
            path for path in asset_paths.values() if unreal.EditorAssetLibrary.does_asset_exist(path)
        )
        if existing:
            return finish(f"refused: destination assets already exist {existing}")
        if dry_run:
            return finish(
                f"dry_run=true|sources={sources}|destinations={asset_paths}|color_srgb=false"
                "|normal_srgb=false|normal_compression=TC_NORMALMAP|dirty_before=[]"
            )

        tasks = []
        for name in names:
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", sources[name])
            task.set_editor_property("destination_path", destination)
            task.set_editor_property("destination_name", name)
            task.set_editor_property("automated", True)
            task.set_editor_property("replace_existing", False)
            task.set_editor_property("save", False)
            tasks.append(task)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

        textures = {}
        for name, path in asset_paths.items():
            texture = unreal.load_asset(path)
            if texture is None:
                return finish(f"refused: import did not create {path}")
            textures[name] = texture
        textures["T_CurtainVelvetCrush"].set_editor_property("srgb", False)
        normal = textures["T_CurtainVelvetCrush_N"]
        normal.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        normal.set_editor_property("srgb", False)

        expected_dirty = set(asset_paths.values())
        dirty_after_import = sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        )
        unexpected_dirty = sorted(set(dirty_after_import) - expected_dirty)
        if unexpected_dirty:
            return finish(
                f"refused: unexpected dirty content packages after import {unexpected_dirty}; nothing saved"
            )

        saved = {
            path: unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
            for path in asset_paths.values()
        }
        readback = {}
        for name, path in asset_paths.items():
            texture = unreal.load_asset(path)
            readback[name] = {
                "compression_settings": str(texture.get_editor_property("compression_settings")),
                "srgb": bool(texture.get_editor_property("srgb")),
            }
        dirty_final = sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        )
        ok = all(saved.values()) and not dirty_final
        return finish(
            f"dry_run=false|ok={ok}|saved={saved}|readback={readback}|dirty_final={dirty_final}"
            "|color_choice=srgb_false_modulation_mask"
        )
    except Exception as exc:
        return finish(f"refused: {type(exc).__name__}: {exc}")


main()
