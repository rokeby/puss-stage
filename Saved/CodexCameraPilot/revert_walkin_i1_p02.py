"""Remove exactly the Interaction 1 WalkIn tracks and save only that sequence."""


def main():
    import json
    import os

    import unreal

    sequence_path = "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy"
    expected_world = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
    expected_project = os.path.normcase(os.path.normpath("E:/PussStage"))
    track_name = "WalkIn (Look & camera)"

    def fail(message):
        full = "PUSS_WALKIN_REVERT_FAILED|" + str(message)
        unreal.log_error(full)
        raise RuntimeError(full)

    def asset_id(value):
        return value.get_path_name().split(".", 1)[0] if value is not None else None

    def census():
        maps = sorted(package.get_path_name() for package in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
        content = sorted(package.get_path_name() for package in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
        return {"maps": maps, "content": content}

    def find_tracks(sequence):
        found = []
        for track in sequence.get_tracks():
            if str(track.get_display_name()) == track_name:
                found.append((sequence, "sequence", track))
        for binding in sequence.get_bindings():
            for track in binding.get_tracks():
                if str(track.get_display_name()) == track_name:
                    found.append((binding, str(binding.get_display_name()), track))
        return found

    try:
        project_dir = os.path.normcase(os.path.normpath(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        )).rstrip("\\/")
        if project_dir != expected_project.rstrip("\\/"):
            fail("wrong project directory %s (expected E:/PussStage)" % project_dir)
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_editor_world()
        if world is None or asset_id(world) != expected_world:
            fail("wrong editor world %s" % asset_id(world))
        if editor.get_game_world() is not None:
            fail("PIE/SIE is active")

        dirty_before = census()
        if dirty_before["maps"] or dirty_before["content"]:
            fail("revert requires zero dirty map and content packages: %r" % dirty_before)
        sequence = unreal.load_asset(sequence_path)
        if sequence is None:
            fail("Interaction 1 sequence did not load")
        found = find_tracks(sequence)
        if not found:
            dirty_after = census()
            if dirty_after != dirty_before:
                fail("NOOP lookup changed dirty-package state: before=%r after=%r" % (dirty_before, dirty_after))
            unreal.log(
                "PUSS_WALKIN_REVERT_NOOP|tracks=0|dirty_before=%s|dirty_after=%s"
                % (json.dumps(dirty_before), json.dumps(dirty_after))
            )
            return

        removed_hosts = []
        for host, host_name, track in found:
            removed = host.remove_track(track)
            if not removed:
                fail("remove_track returned False on %s" % host_name)
            removed_hosts.append(host_name)
        remaining_before_save = find_tracks(sequence)
        if remaining_before_save:
            fail("named tracks remain before save on %r" % [name for _, name, _ in remaining_before_save])

        saved = unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
        if not saved:
            fail("save_loaded_asset returned False for Interaction 1")
        remaining_after_save = find_tracks(sequence)
        if remaining_after_save:
            fail("named tracks remain after save on %r" % [name for _, name, _ in remaining_after_save])
        dirty_after = census()
        if dirty_after["maps"] or dirty_after["content"]:
            fail("packages remain dirty after revert save: %r" % dirty_after)
        unreal.log(
            "PUSS_WALKIN_REVERTED|removed=%d|hosts=%s|saved=1|dirty_before=%s|dirty_after=%s"
            % (
                len(found), json.dumps(removed_hosts),
                json.dumps(dirty_before), json.dumps(dirty_after),
            )
        )
    except Exception as error:
        if "PUSS_WALKIN_REVERT_FAILED|" not in str(error):
            unreal.log_error("PUSS_WALKIN_REVERT_FAILED|" + str(error))
        raise


main()
