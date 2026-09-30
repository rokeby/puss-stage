"""Read-only: what LS_DevScene_04's camera cuts bind to (actor label and world
location), and how the shot section's parameters, including its time scale,
look to Python in UE 5.8. Settles whether a subsequence Time Scale can be the
fold's speed dial. Mutates nothing. Lean: all work in main()."""
import json
import os

import unreal

SCENE4 = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    seq = unreal.EditorAssetLibrary.load_asset(SCENE4)
    out = {"cuts": [], "shot": None}
    gs = unreal.GuidLibrary.conv_guid_to_string
    bindings = {gs(b.get_id()): b for b in seq.get_bindings()}
    for t in seq.get_tracks():
        for s in t.get_sections():
            if isinstance(s, unreal.MovieSceneCameraCutSection):
                bid = s.get_camera_binding_id()
                guid = gs(bid.get_editor_property("guid"))
                b = bindings.get(guid)
                row = {"start_s": round(s.get_start_frame_seconds(), 3), "end_s": round(s.get_end_frame_seconds(), 3),
                       "binding_guid": guid, "binding_name": str(b.get_display_name()) if b else None}
                if b:
                    try:
                        objs = seq.locate_bound_objects(b, world) if hasattr(seq, "locate_bound_objects") else []
                    except Exception as exc:
                        objs = [f"locate failed: {exc}"]
                    row["bound"] = [(o.get_actor_label(), [round(v) for v in o.get_actor_location().to_tuple()])
                                    if isinstance(o, unreal.Actor) else str(o) for o in objs]
                out["cuts"].append(row)
            elif isinstance(s, unreal.MovieSceneSubSection):
                p = s.get_editor_property("parameters")
                fields = {}
                for name in dir(p):
                    if name.startswith("_") or callable(getattr(p, name, None)):
                        continue
                    try:
                        fields[name] = str(getattr(p, name))[:200]
                    except Exception as exc:
                        fields[name] = f"<{exc}>"
                out["shot"] = {"class": s.get_class().get_name(), "params_type": type(p).__name__, "fields": fields,
                               "section_methods": [m for m in dir(s) if "scale" in m.lower() or "time" in m.lower()][:40]}
    json.dump(out, open(os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                                     "CodexStructure", "scene4_sequence_probe.json"), "w"), indent=1, default=str)
    unreal.log(f"SCENE4_SEQUENCE_PROBE_OK|cuts={len(out['cuts'])}|mutated=0")


main()
