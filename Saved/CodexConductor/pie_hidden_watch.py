"""READ-ONLY in PIE: actor bHidden (the flag visibility tracks write) + root visible for clam parts, millstone, figures,
sampled now.  PIE_HIDDEN_OK|json"""
import json
def main():
    import unreal
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
    out = {"playing": root.sequence_player.is_playing()}
    try:
        out["t"] = root.sequence_player.get_current_time().time.frame_number.value
    except Exception:
        pass
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        l = str(a.get_actor_label()) if hasattr(a, "get_actor_label") else a.get_name()
        if l.startswith("S3 PearlClam") or "Millstone" in l or l.startswith("Shore0") or "Shore05" in l:
            out[l[:26]] = [bool(a.get_editor_property("hidden")), a.get_editor_property("root_component").is_visible(), round(a.get_actor_location().z)]
    unreal.log("PIE_HIDDEN_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIE_HIDDEN_FAILED|%r" % (exc,))
