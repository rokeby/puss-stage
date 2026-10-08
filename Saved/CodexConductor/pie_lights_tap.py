"""READ-ONLY PIE tap: seconds into the segment named in pie_lights_tap_args.json {"segment": "Scene 3"}, camera
location, and the top 12 visible light components by intensity/dist^2 (cd-ish, unit-agnostic rank) with owner label,
class, intensity, units, dist.  First tap also logs every segment label.  PIE_LIGHTSTAP|json"""
import json
def main():
    import unreal
    a = json.load(open("E:/PussStage/Saved/CodexConductor/pie_lights_tap_args.json"))
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    root = list(unreal.GameplayStatics.get_all_actors_of_class(w, unreal.InfinityStageShowRoot))[0]
    tr = root.transport
    segs = list(tr.segments)
    seg = [s for s in segs if str(s.label).startswith(a["segment"])][0]
    m = tr.get_current_master_frame().value
    pc = unreal.GameplayStatics.get_player_camera_manager(w, 0)
    cam = pc.get_camera_location()
    rows = []
    for act in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        for lc in act.get_components_by_class(unreal.LightComponent):
            if not lc.is_visible():
                continue
            i = float(lc.intensity)
            if i <= 0:
                continue
            p = lc.get_world_location()
            d = max(100.0, ((p.x - cam.x) ** 2 + (p.y - cam.y) ** 2 + (p.z - cam.z) ** 2) ** 0.5)
            hid = bool(act.get_editor_property("hidden"))
            rows.append([round(i / (d / 100.0) ** 2, 3), str(act.get_actor_label())[:48], lc.get_class().get_name()[:18], round(i, 2),
                         str(getattr(lc, "intensity_units", "")).split(".")[-1][:6] if hasattr(lc, "intensity_units") else "", round(d), hid])
    rows.sort(key=lambda r: -r[0])
    out = {"t": round((m - seg.start_frame.value) / 24000.0, 2), "cam": [round(cam.x), round(cam.y), round(cam.z)], "top": rows[:12], "n_lit": len(rows)}
    if a.get("labels"):
        out["segments"] = [str(s.label) for s in segs]
    unreal.log("PIE_LIGHTSTAP|" + json.dumps(out))
main()
