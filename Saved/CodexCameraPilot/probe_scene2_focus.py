"""Read-only: Scene 2 Entry handoff focus vs Passage 2's authored end focus. Marker: PUSS_SCENE2_FOCUS_PROBE"""
import unreal
show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
lib = unreal.InfinityStageCameraPilotLibrary
def unwrap(r, n):
    if r is None: return None
    if isinstance(r, tuple) and len(r) == n + 1 and isinstance(r[0], bool): return r[1:] if r[0] else None
    return r
p2 = next(p for p in show.get_editor_property("passage_settings") if str(p.get_editor_property("label")) == "Passage 2")
g = p2.get_editor_property("passage_guid")
start, end = unwrap(lib.get_passage_frame_range(show, g), 2)
mid = (start + end) // 2
focus = {name: unwrap(lib.get_passage_camera_pose(show, g, int(f)), 3)[2] for name, f in (("start", start), ("mid", mid), ("end", end))}
entry = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
         if isinstance(a, unreal.CineCameraActor) and a.actor_has_tag("InfinityStage.SceneEntry") and a.get_actor_label().startswith("Scene 2 ")]
entry_focus = entry[0].get_cine_camera_component().get_editor_property("focus_settings").get_editor_property("manual_focus_distance") if len(entry) == 1 else None
unreal.log(f"PUSS_SCENE2_FOCUS_PROBE|p2_focus_start={focus['start']:.1f}|mid={focus['mid']:.1f}|end={focus['end']:.1f}|s2_entry_focus={entry_focus}|entry_cams={len(entry)}")
