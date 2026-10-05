"""Conductor 5 Oct: copy of revert_walkin_i1_p02.py WITHOUT the apply-record requirement (no record exists for I1) and
without trusting remove_track's return value. Same backup, same re-list before/after save, same narrow save."""
"""Remove exactly one configured transition's WalkIn tracks and save only that sequence."""


TRANSITION_ID = str(globals().get("WALKIN_TRANSITION_ID", "I1"))


def main(transition_id):
    import datetime
    import json
    import os
    import shutil

    import unreal

    expected_world = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
    expected_project = os.path.normcase(os.path.normpath("E:/PussStage"))
    track_name = "WalkIn (Look & camera)"
    run_id = str(globals().get(
        "WALKIN_RUN_ID", datetime.datetime.now().strftime("WALKIN-REVERT-%Y%m%d-%H%M%S")
    ))

    def fail(message):
        full = "PUSS_WALKIN_REVERT_FAILED|run=%s|" % run_id + str(message)
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

        transition_id = str(transition_id).strip().upper()
        config_path = os.path.join(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
            "CodexCameraPilot", "walkin_transitions.json",
        )
        if not os.path.isfile(config_path):
            fail("transition registry is missing at %s" % config_path)
        with open(config_path, "r", encoding="utf-8") as config_handle:
            transitions = json.load(config_handle)
        if transition_id not in transitions:
            fail("unknown transition id %r (expected one of %r)" % (transition_id, sorted(transitions)))
        sequence_path = transitions[transition_id].get("sequence_path")
        if not sequence_path:
            fail("%s registry entry has no sequence_path" % transition_id)

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
            fail("%s sequence did not load" % transition_id)
        found = find_tracks(sequence)
        if not found:
            dirty_after = census()
            if dirty_after != dirty_before:
                fail("NOOP lookup changed dirty-package state: before=%r after=%r" % (dirty_before, dirty_after))
            unreal.log(
                "PUSS_WALKIN_REVERT_NOOP|run=%s|transition=%s|tracks=0|dirty_before=%s|dirty_after=%s"
                % (run_id, transition_id, json.dumps(dirty_before), json.dumps(dirty_after))
            )
            return

        saved_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
        record_path = "none (no apply record exists; conductor 5 Oct, sleight I1 needs the walk-in removed)"
        sequence_file = os.path.join(
            project_dir, "Content", *sequence_path[len("/Game/"):].split("/"),
        ) + ".uasset"
        if not os.path.isfile(sequence_file):
            fail("sequence file is missing: %s" % sequence_file)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = os.path.join(project_dir, "Backups", "PreWalkInRevert%s-%s" % (transition_id, stamp))
        os.makedirs(backup_dir, exist_ok=False)
        backup_file = os.path.join(backup_dir, os.path.basename(sequence_file))
        shutil.copy2(sequence_file, backup_file)
        if not os.path.isfile(backup_file) or os.path.getsize(backup_file) != os.path.getsize(sequence_file):
            fail("revert backup verification failed")

        removed_hosts = []
        for host, host_name, track in found:
            host.remove_track(track)  # returns None in UE 5.8 Python; judged by the re-list below
            removed_hosts.append(host_name)
        remaining_before_save = find_tracks(sequence)
        if remaining_before_save:
            fail("named tracks remain before save on %r" % [name for _, name, _ in remaining_before_save])

        saved = unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
        if not saved:
            fail("save_loaded_asset returned False for %s" % transition_id)
        remaining_after_save = find_tracks(sequence)
        if remaining_after_save:
            fail("named tracks remain after save on %r" % [name for _, name, _ in remaining_after_save])
        dirty_after = census()
        if dirty_after["maps"] or dirty_after["content"]:
            fail("packages remain dirty after revert save: %r" % dirty_after)
        unreal.log(
            "PUSS_WALKIN_REVERTED|run=%s|transition=%s|removed=%d|hosts=%s|saved=1|backup=%s|record=%s|dirty_before=%s|dirty_after=%s"
            % (
                run_id, transition_id, len(found), json.dumps(removed_hosts), backup_dir, record_path,
                json.dumps(dirty_before), json.dumps(dirty_after),
            )
        )
    except Exception as error:
        if "PUSS_WALKIN_REVERT_FAILED|" not in str(error):
            unreal.log_error("PUSS_WALKIN_REVERT_FAILED|run=%s|" % run_id + str(error))
        raise


main(TRANSITION_ID)
