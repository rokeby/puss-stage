"""Guarded import for a mode-selected curtain texture set."""

import json
import os

import unreal


def main():
    expected_world = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
    destination = "/Game/Scenes/Curtain/Chaos/Textures"
    default_textures = [
        {
            "name": "T_CurtainVelvetCrush",
            "source": "DerivedAssets/CurtainCloth/Textures/T_CurtainVelvetCrush.png",
            "normal": False,
        },
        {
            "name": "T_CurtainVelvetCrush_N",
            "source": "DerivedAssets/CurtainCloth/Textures/T_CurtainVelvetCrush_N.png",
            "normal": True,
        },
    ]

    def finish(detail):
        clean = str(detail).replace("\r", " ").replace("\n", " ")
        return unreal.log(f"PUSS_SOFTGOODS_VELVET_IMPORT|{clean}")

    try:
        saved_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
        project_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        mode_path = os.path.join(saved_dir, "CodexSoftGoods", "import_velvet_textures_mode.json")
        with open(mode_path, encoding="utf-8") as handle:
            mode = json.load(handle)
        if not isinstance(mode, dict) or set(mode) not in (
            {"dry_run"},
            {"dry_run", "textures"},
        ):
            return finish(
                "refused: mode keys must be exactly {'dry_run'} or "
                f"{{'dry_run', 'textures'}}, got {mode!r}"
            )
        if not isinstance(mode["dry_run"], bool):
            return finish(f"refused: dry_run must be true or false, got {mode['dry_run']!r}")
        dry_run = mode["dry_run"]

        texture_specs = mode.get("textures", default_textures)
        if not isinstance(texture_specs, list) or not texture_specs:
            return finish("refused: textures must be a non-empty list")
        checked_specs = []
        seen_names = set()
        for index, spec in enumerate(texture_specs):
            if not isinstance(spec, dict) or set(spec) != {"name", "source", "normal"}:
                return finish(
                    f"refused: textures[{index}] must contain exactly name, source, normal; got {spec!r}"
                )
            name = spec["name"]
            source = spec["source"]
            is_normal = spec["normal"]
            if (
                not isinstance(name, str)
                or not name
                or not name.replace("_", "").isalnum()
                or "/" in name
                or "\\" in name
            ):
                return finish(f"refused: invalid texture name at textures[{index}]: {name!r}")
            if name in seen_names:
                return finish(f"refused: duplicate texture name {name!r}")
            if (
                not isinstance(source, str)
                or not source
                or "\\" in source
                or os.path.isabs(source)
            ):
                return finish(
                    f"refused: textures[{index}].source must be a relative forward-slash path"
                )
            if not isinstance(is_normal, bool):
                return finish(f"refused: textures[{index}].normal must be true or false")
            seen_names.add(name)
            checked_specs.append({"name": name, "source": source, "normal": is_normal})

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

        project_root = os.path.normcase(os.path.abspath(project_dir))
        sources = {}
        normal_by_name = {}
        for spec in checked_specs:
            source_path = os.path.abspath(os.path.join(project_dir, *spec["source"].split("/")))
            try:
                inside_project = os.path.commonpath(
                    (project_root, os.path.normcase(source_path))
                ) == project_root
            except ValueError:
                inside_project = False
            if not inside_project:
                return finish(f"refused: source escapes the project directory {spec['source']!r}")
            sources[spec["name"]] = source_path
            normal_by_name[spec["name"]] = spec["normal"]
        missing_sources = sorted(path for path in sources.values() if not os.path.isfile(path))
        if missing_sources:
            return finish(f"refused: missing source files {missing_sources}")

        asset_paths = {name: f"{destination}/{name}" for name in sources}
        existing = sorted(
            path for path in asset_paths.values() if unreal.EditorAssetLibrary.does_asset_exist(path)
        )
        if existing:
            return finish(f"refused: destination assets already exist {existing}")
        if dry_run:
            return finish(
                f"dry_run=true|sources={sources}|destinations={asset_paths}"
                f"|normal_by_name={normal_by_name}|all_srgb=false"
                "|normal_compression=TC_NORMALMAP|dirty_before=[]"
            )

        tasks = []
        for name in sources:
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
        for name, texture in textures.items():
            texture.set_editor_property("srgb", False)
            if normal_by_name[name]:
                texture.set_editor_property(
                    "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP
                )

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
                "normal": normal_by_name[name],
            }
        dirty_final = sorted(
            package.get_path_name()
            for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        )
        properties_ok = all(
            not values["srgb"]
            and (
                not values["normal"]
                or values["compression_settings"].endswith("TC_NORMALMAP")
            )
            for values in readback.values()
        )
        ok = all(saved.values()) and not dirty_final and properties_ok
        return finish(
            f"dry_run=false|ok={ok}|saved={saved}|readback={readback}|dirty_final={dirty_final}"
            "|all_srgb=false|normal_compression=TC_NORMALMAP"
        )
    except Exception as exc:
        return finish(f"refused: {type(exc).__name__}: {exc}")


main()
