"""Read-only: Scene 4's cameras (position, facing, lens) and anything already
built within 80 m of its establishing camera. Mutates nothing."""
import json
import os

import unreal


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cams, near = [], []
    anchor = None
    for a in sub.get_all_level_actors():
        label = a.get_actor_label()
        if label.startswith(("Scene 04", "Scene 4 ")) or "Scene 4" in label:
            t = a.get_actor_transform()
            r = t.rotation.rotator()
            rec = {"label": label, "class": a.get_class().get_name(),
                   "loc": [round(t.translation.x), round(t.translation.y), round(t.translation.z)],
                   "rot": [round(r.roll, 1), round(r.pitch, 1), round(r.yaw, 1)]}
            cc = a.get_component_by_class(unreal.CineCameraComponent)
            if cc:
                rec["focal_mm"] = round(cc.get_editor_property("current_focal_length"), 1)
                fb = cc.get_editor_property("filmback")
                rec["filmback"] = [round(fb.sensor_width, 2), round(fb.sensor_height, 2)]
            cams.append(rec)
            if "Establishing" in label and anchor is None:
                anchor = t.translation
    if anchor:
        for a in sub.get_all_level_actors():
            o, e = a.get_actor_bounds(False)
            if max(e.x, e.y, e.z) > 50000:
                continue
            if abs(o.x - anchor.x) < 8000 and abs(o.y - anchor.y) < 8000 and a.get_actor_label() not in [c["label"] for c in cams]:
                near.append({"label": a.get_actor_label(), "class": a.get_class().get_name(),
                             "centre": [round(o.x), round(o.y), round(o.z)], "extent": [round(e.x), round(e.y), round(e.z)]})
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "scene4_site.json")
    json.dump({"cameras": cams, "near_80m": near}, open(out, "w"), indent=1)
    unreal.log(f"SCENE4_SITE_OK|cameras={len(cams)}|near={len(near)}|mutated=0")


main()
