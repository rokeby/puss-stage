"""Editor read at a Scene-3 frame: opens LS_DevScene_03 in Sequencer (if not open), sets the playhead, reads the
PearlClam parts' world location + visibility and the active camera-cut camera's pose.  Census reported before/after
(scrubbing can dirty the map; nothing is saved).  Args seq_eval_clam_args.json {"frame":1248}.  SEQ_EVAL_CLAM_OK|json."""
import json
def main():
    import unreal
    a = json.load(open("E:/PussStage/Saved/CodexConductor/seq_eval_clam_args.json"))
    lib = unreal.EditorLoadingAndSavingUtils
    cen = lambda: ([p.get_name() for p in lib.get_dirty_content_packages()], [p.get_name() for p in lib.get_dirty_map_packages()])
    c0 = cen()
    L = unreal.LevelSequenceEditorBlueprintLibrary
    seq = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03")
    cur = L.get_current_level_sequence()
    if cur is None or cur.get_path_name() != seq.get_path_name():
        L.open_level_sequence(seq)
    L.set_current_time(int(a["frame"]))
    L.refresh_current_level_sequence()
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    out = {"frame": a["frame"], "census_before": c0}
    for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        l = str(x.get_actor_label())
        if l.startswith("S3 PearlClam") or l.startswith("S3 Shot B0"):
            p = x.get_actor_location(); r = x.get_actor_rotation()
            out[l] = [round(p.x), round(p.y), round(p.z), round(r.pitch, 1), round(r.yaw, 1), x.is_hidden_ed(), bool(x.get_editor_property("hidden"))]
    out["census_after"] = cen()
    unreal.log("SEQ_EVAL_CLAM_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("SEQ_EVAL_CLAM_FAILED|%r" % (exc,))
