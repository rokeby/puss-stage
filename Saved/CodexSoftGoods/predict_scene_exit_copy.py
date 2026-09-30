"""READ-ONLY (30 Sep): what will MatchSceneHandoffs do to a Scene's Exit camera? Predict before applying.

InfinityStageSceneHandoffBuilder.cpp:409-411: for a retained exit (the next segment retains the camera), the match
COPIES the view of the LAST INTERIOR cut's camera (the latest-starting root cut that is neither the Entry nor the Exit
handoff) into the Exit camera, or the Entry camera's view when there is no interior cut. This lists the scene's root
cuts, resolves each cut's camera in the level, and compares the camera the Exit would copy with the Exit as it is now.
Mode: predict_scene_exit_copy_mode.json {"scene_label": ...}. Writes predict_scene_exit_copy.json; logs
PUSS_SOFTGOODS_EXIT_PREDICT|... Nothing is modified. Crash rules: everything inside main().
"""
import json
import os

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def view(a):
    cc = a.get_editor_property("camera_component")
    loc, rot = a.get_actor_location(), a.get_actor_rotation()
    return {"label": a.get_actor_label(), "loc": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)],
            "rot": [round(rot.pitch, 3), round(rot.yaw, 3), round(rot.roll, 3)],
            "focal_mm": round(cc.get_editor_property("current_focal_length"), 3),
            "focus_cm": round(cc.get_editor_property("focus_settings").get_editor_property("manual_focus_distance"), 2)}


def main():
    with open(os.path.join(HERE, "predict_scene_exit_copy_mode.json"), encoding="utf-8") as h:
        label = json.load(h)["scene_label"]
    dirty0 = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    show = unreal.load_asset(SHOW)
    cue = next(c for c in show.get_editor_property("cues") if str(c.get_editor_property("label")) == label)
    seq = cue.get_editor_property("scene").get_editor_property("sequence")
    actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if isinstance(a, unreal.CineCameraActor)}
    cuts = []
    for t in seq.get_tracks():
        if t.get_class().get_name() != "MovieSceneCameraCutTrack":
            continue
        for s in t.get_sections():
            proxy = seq.resolve_binding_id(s.get_camera_binding_id())
            name = str(proxy.get_display_name()) if proxy is not None and proxy.is_valid() else None
            cam = actors.get(name) if name else None
            cuts.append({"range": [s.get_start_frame(), s.get_end_frame()], "active": s.is_active(), "binding": name,
                         "camera": view(cam) if cam else None})
    cuts.sort(key=lambda c: c["range"][0])
    entry_label, exit_label = f"{label} — Entry Handoff Camera", f"{label} — Exit Handoff Camera"
    interior = [c for c in cuts if c["binding"] not in (entry_label, exit_label)]
    source = (interior[-1]["camera"] if interior else (view(actors[entry_label]) if entry_label in actors else None))
    exit_now = view(actors[exit_label]) if exit_label in actors else None
    delta = None
    if source and exit_now:
        delta = {"moved_cm": round(sum((a - b) ** 2 for a, b in zip(source["loc"], exit_now["loc"])) ** 0.5, 2),
                 "turned_deg": round(max(abs(a - b) for a, b in zip(source["rot"], exit_now["rot"])), 3),
                 "focal_delta_mm": round(source["focal_mm"] - exit_now["focal_mm"], 3),
                 "focus_delta_cm": round(source["focus_cm"] - exit_now["focus_cm"], 2)}
    dirty1 = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    report = {"scene": label, "cuts": cuts, "copy_source": source, "exit_now": exit_now, "predicted_exit_delta": delta,
              "dirty_changed": dirty0 != dirty1}
    with open(os.path.join(HERE, "predict_scene_exit_copy.json"), "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1)
    del show, cue, seq, actors
    unreal.log(f"PUSS_SOFTGOODS_EXIT_PREDICT|{label}|source={source['label'] if source else None}|delta={delta}"
               f"|dirty_changed={dirty0 != dirty1}")


main()
