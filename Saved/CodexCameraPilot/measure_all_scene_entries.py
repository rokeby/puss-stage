"""Read-only: every Scene's Entry handoff camera against its incoming Passage's end,
in cm and degrees, whether or not it counts as stale. Marker: PUSS_SCENE_ENTRY_MEASURED"""
import json, math, os
import unreal
show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
lib = unreal.InfinityStageCameraPilotLibrary
def unwrap(r, n):
    if r is None: return None
    if isinstance(r, tuple) and len(r) == n + 1 and isinstance(r[0], bool): return r[1:] if r[0] else None
    return r
passages = {str(p.get_editor_property("label")): p.get_editor_property("passage_guid") for p in show.get_editor_property("passage_settings")}
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rows = []
for n in range(1, 7):
    guid = passages[f"Passage {n}"]
    rng = unwrap(lib.get_passage_frame_range(show, guid), 2)
    view, focal, focus = unwrap(lib.get_passage_camera_pose(show, guid, int(rng[1])), 3)
    entry = [a for a in actors if isinstance(a, unreal.CineCameraActor) and a.actor_has_tag("InfinityStage.SceneEntry") and a.get_actor_label().startswith(f"Scene {n} ")]
    if len(entry) != 1:
        rows.append({"scene": n, "entry_cameras": len(entry)}); continue
    e = entry[0]
    a, b = view.rotation, e.get_actor_transform().rotation
    ang = math.degrees(2.0 * math.acos(min(1.0, abs(a.x*b.x + a.y*b.y + a.z*b.z + a.w*b.w))))
    lens = e.get_cine_camera_component()
    rows.append({"scene": n, "cm": (e.get_actor_location() - view.translation).length(), "deg": ang,
                 "focal": [focal, lens.get_editor_property("current_focal_length")],
                 "focus": [focus, lens.get_editor_property("focus_settings").get_editor_property("manual_focus_distance")]})
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexCameraPilot", "measure_all_scene_entries.json")
with open(out, "w", encoding="utf-8") as h: json.dump(rows, h, indent=2)
unreal.log("PUSS_SCENE_ENTRY_MEASURED|" + "|".join(f"S{r['scene']}={r.get('cm', -1):.2f}cm/{r.get('deg', -1):.2f}deg" for r in rows))
