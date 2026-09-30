"""Undo MY refused Scene 3 match (30 Sep 12:51), in memory only. Nothing was saved; the disk already equals the backup
Backups/PreSceneExtend-LS_DevScene_03-20260930-125152.

Why: extend_scene_playback's coverage gate refused (the match put the Exit cut at 1549-1573 while ClamCam1 ends at 1501,
leaving 1501-1549 uncovered), so it saved nothing. But the match (one transaction, "Match Named Scene Camera Handoffs")
left LS_DevScene_03 and the level modified in memory. A save by anyone would write the gapped layout.

Guard: acts ONLY if Scene 3's root cuts are exactly the refused layout [[0,81],[81,1501],[1549,1573]] and no PIE is
running. Then TRANSACTION UNDO, and a read-back: the cuts must return to [[0,95],[81,1501],[1273,1550]] (the on-disk
layout). If they don't, it issues TRANSACTION REDO (the undo hit something else) and says so. The dirty flags stay: the
packages then match the disk but are still flagged; the Conductor decides between a relaunch without saving and a net-nil
save. Logs PUSS_SOFTGOODS_SCENE3_UNDO|... Crash rules: everything inside main().
"""
import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LABEL = "Scene 3 — External Sound"
REFUSED = [[0, 81], [81, 1501], [1549, 1573]]
ON_DISK = [[0, 95], [81, 1501], [1273, 1550]]


def cuts(seq):
    return sorted([s.get_start_frame(), s.get_end_frame()] for t in seq.get_tracks()
                  if t.get_class().get_name() == "MovieSceneCameraCutTrack" for s in t.get_sections())


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        return unreal.log("PUSS_SOFTGOODS_SCENE3_UNDO|refused: PIE is running")
    show = unreal.load_asset(SHOW)
    cue = next(c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == LABEL)
    seq = cue.get_editor_property("scene").get_editor_property("sequence")
    before = cuts(seq)
    if before != REFUSED:
        return unreal.log(f"PUSS_SOFTGOODS_SCENE3_UNDO|refused: cuts are {before}, not the refused layout; nothing done")
    world = editor.get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, "TRANSACTION UNDO")
    after = cuts(seq)
    if after == ON_DISK:
        verdict = "restored"
    else:
        unreal.SystemLibrary.execute_console_command(world, "TRANSACTION REDO")
        verdict = f"NOT restored (got {after}); REDO issued, now {cuts(seq)}"
    dirty = sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    del show, cue, seq, world
    unreal.log(f"PUSS_SOFTGOODS_SCENE3_UNDO|{verdict}|before={before}|after={after}|dirty={dirty}")


main()
