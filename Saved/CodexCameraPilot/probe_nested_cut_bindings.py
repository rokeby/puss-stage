"""Read-only: what do the NESTED shots' camera cuts bind to, and do those actors exist in the level? (30 Sep)

Scene 3 play-through (scene3_cut_view.json): the view went P03 rig -> ClamCam1 at Scene-local +0.1 s, although the
ROOT ClamCam1 cut starts at 3.375 s; the nested LS_Clams shot has a cut spanning its whole range. Scene 1
(scene1_tail_view.json): nothing of Sequencer's ever took the view; LS_Animals_1 has four nested cuts. Candidate
(inferred): nested cuts outrank the root cuts, and they resolve in Scene 3 but not in Scene 1. This lists each
nested cut's binding (name, possessable or spawnable) and whether a level actor carries that label.
Plain property reads only; no SequencerTools helpers. Success marker: PUSS_NESTED_CUT_BINDINGS
"""
import json
import os

import unreal

NESTED = ["/Game/Scenes/LS_Animals_1", "/Game/Scenes/LS_Clams", "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01",
          "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"]


def guid(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def main():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        unreal.log("PUSS_NESTED_CUT_BINDINGS|refused: PIE still running")
        return
    world = editor.get_editor_world()
    labels = {}
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.CineCameraActor):
        labels.setdefault(actor.get_actor_label(), []).append(actor.get_name())
    report = {}
    for path in NESTED:
        sequence = unreal.load_asset(path)
        if sequence is None:
            report[path] = "not found"
            continue
        possessables = {guid(b.get_id()): str(b.get_display_name()) for b in sequence.get_possessables()}
        spawnables = {guid(b.get_id()): str(b.get_display_name()) for b in sequence.get_spawnables()}
        cuts = []
        for track in sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
            for section in track.get_sections():
                g = guid(section.get_camera_binding_id().get_editor_property("guid"))
                name = possessables.get(g) or spawnables.get(g)
                cuts.append({"span": [section.get_start_frame() if section.has_start_frame() else None,
                                      section.get_end_frame() if section.has_end_frame() else None],
                             "binding": name,
                             "kind": "possessable" if g in possessables else "spawnable" if g in spawnables else "UNKNOWN",
                             "level_actors_with_label": labels.get(name, [])})
        report[path] = cuts
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexCameraPilot", "probe_nested_cut_bindings.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False)
    unreal.log("PUSS_NESTED_CUT_BINDINGS|%s" % json.dumps(report, ensure_ascii=False))


main()
