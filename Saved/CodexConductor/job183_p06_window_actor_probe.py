"""Read-only label/class/bounds probe for P06 end-window geometry."""
import json
import os
import unreal


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world is None or unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
    raise RuntimeError("JOB183_P06_WINDOW_PROBE_EDITOR_WORLD_REQUIRED")
rows = []
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    label = str(actor.get_actor_label())
    cls = actor.get_class().get_name()
    text = (label + " " + cls).lower()
    origin, extent = actor.get_actor_bounds(False, False)
    p06_end_spatial = (23000.0 <= origin.x <= 31000.0 and
                       396000.0 <= origin.y <= 404000.0 and
                       -1000.0 <= origin.z <= 4000.0)
    if any(token in text for token in ("p06", "window", "end", "sun", "portal", "opening")) or p06_end_spatial:
        rows.append({
            "label": label,
            "class": cls,
            "path": str(actor.get_path_name()),
            "origin_cm": [origin.x, origin.y, origin.z],
            "extent_cm": [extent.x, extent.y, extent.z],
            "hidden_ed": bool(actor.get_is_hidden_ed()) if hasattr(actor, "get_is_hidden_ed") else None,
            "tags": [str(t) for t in actor.get_editor_property("tags")],
        })
path = "E:/PussStage/Saved/CodexConductor/job183_p06_window_actor_probe.json"
with open(path, "w", encoding="utf-8") as handle:
    json.dump({"rows": rows}, handle, indent=2, sort_keys=True)
unreal.log("JOB183_P06_WINDOW_ACTOR_PROBE_OK|rows=%d|path=%s" % (len(rows), path))
