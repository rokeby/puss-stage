"""READ-ONLY in PIE: state of the S3 clam + figure actors in the PIE world (location, hidden in game, root visible,
skeletal anim mode/position) and the Master frame.  PIE_S3_ACTORS_OK|<json> / _FAILED."""
import json
def main():
    import unreal
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if w is None:
        raise RuntimeError("NO_PIE")
    out = {}
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))
    if roots:
        try:
            out["master_frame"] = roots[0].sequence_player.get_current_time().time.frame_number.value
        except Exception as e:
            out["master_frame"] = repr(e)
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        l = str(a.get_actor_label()) if hasattr(a, "get_actor_label") else a.get_name()
        n = a.get_name()
        key = l or n
        if not any(x in key for x in ("PearlClam", "Clam_with_Pearl", "Shore0", "source_Anim", "S3 Hangar Root")):
            continue
        r = a.get_editor_property("root_component")
        loc = a.get_actor_location()
        row = {"loc": [round(loc.x), round(loc.y), round(loc.z)], "hidden": a.is_hidden() if hasattr(a, "is_hidden") else None,
               "root_visible": r.is_visible() if r else None, "level": a.get_outermost().get_name().split("/")[-1]}
        sk = a.get_component_by_class(unreal.SkeletalMeshComponent)
        if sk:
            row["sk_visible"] = sk.is_visible()
            row["anim_mode"] = str(sk.get_animation_mode())
        out[key] = row
    unreal.log("PIE_S3_ACTORS_OK|" + json.dumps(out, default=str))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PIE_S3_ACTORS_FAILED|%r" % (exc,))
