"""READ-ONLY: which camera the Master shows during the Opening (0-15 s) and the first seconds of Passage 01, and where
it is. Writes nothing; everything inside main()."""
import json
import os

import unreal


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def rot(r):
    return [round(r.roll, 2), round(r.pitch, 2), round(r.yaw, 2)]


def main():
    master = unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master")
    report = {"master_tracks": [], "bindings": []}
    for t in master.get_tracks():
        row = {"class": t.get_class().get_name(), "name": str(t.get_display_name()), "sections": []}
        for s in t.get_sections()[:12]:
            sec = {"start": s.get_start_frame() if s.has_start_frame() else None,
                   "end": s.get_end_frame() if s.has_end_frame() else None}
            if isinstance(s, unreal.MovieSceneCameraCutSection):
                try:
                    b = s.get_camera_binding_id()
                    sec["camera_guid"] = str(b.get_editor_property("guid"))
                except Exception as exc:  # noqa: BLE001
                    sec["camera_err"] = str(exc)
            if isinstance(s, unreal.MovieSceneSubSection):
                sub = s.get_sequence()
                sec["sub"] = sub.get_name() if sub else None
            row["sections"].append(sec)
        report["master_tracks"].append(row)
    for b in master.get_bindings():
        report["bindings"].append({"name": str(b.get_display_name()), "guid": str(b.get_id()),
                                   "tracks": [t.get_class().get_name() for t in b.get_tracks()]})
    ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cams = []
    for a in ss.get_all_level_actors():
        if a.get_class().get_name() == "InfinityStageCameraRig" and "Passage 01" in a.get_actor_label():
            row = {"label": a.get_actor_label(), "loc": vec(a.get_actor_location())}
            for c in a.get_components_by_class(unreal.CameraComponent):
                row.setdefault("cameras", []).append({"name": c.get_name(), "world": vec(c.get_world_location()),
                                                      "rot": rot(c.get_world_rotation()),
                                                      "fov": round(c.get_editor_property("field_of_view"), 2)})
            for prop in ("route_start_cm", "start_distance_cm", "camera_height_cm", "passage_actor"):
                try:
                    v = a.get_editor_property(prop)
                    row[prop] = v.get_actor_label() if hasattr(v, "get_actor_label") else v
                except Exception:  # noqa: BLE001
                    pass
            cams.append(row)
    report["p01_camera"] = cams
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "inspect_opening_camera.json")
    with open(out, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str)
    unreal.log("PUSS_SOFTGOODS_OPENING_CAMERA_OK|" + out)


main()
