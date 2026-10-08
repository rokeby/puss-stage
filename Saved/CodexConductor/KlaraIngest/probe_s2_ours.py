"""READ-ONLY probe (8 Oct): every actor inside the S2 hangar box (dock (11104, 80954) yaw -43.57; interior x 500..6500,
|y| <= 1000 in hangar-local cm, +5 m margin) that is NOT in Klara's Japanese_Alley level: label, class, level, folder,
tags, hidden flags.  probe_s2_ours.json.  PROBE_S2OURS_OK / _FAILED.  Saves nothing."""
import json, math

OUT = "E:/PussStage/Saved/CodexConductor/KlaraIngest/probe_s2_ours.json"
DOCK, YAW = (11104.483, 80954.388), -43.5725


def main():
    import unreal as u
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    c, s = math.cos(math.radians(-YAW)), math.sin(math.radians(-YAW))
    rows = []
    for a in u.GameplayStatics.get_all_actors_of_class(w, u.Actor):
        l = a.get_actor_location()
        dx, dy = l.x - DOCK[0], l.y - DOCK[1]
        lx, ly = dx * c - dy * s, dx * s + dy * c
        if not (0 <= lx <= 7000 and abs(ly) <= 1500):
            continue
        lvl = a.get_outer().get_outer().get_name() if a.get_outer() and a.get_outer().get_outer() else "?"
        if "Japanese_Alley" in lvl:
            continue
        p = a.get_attach_parent_actor()
        rows.append({"label": str(a.get_actor_label()), "cls": a.get_class().get_name(), "level": lvl,
                     "folder": str(a.get_folder_path()), "tags": [str(t) for t in a.tags],
                     "local": [round(lx), round(ly), round(l.z)], "parent": str(p.get_actor_label()) if p else None,
                     "hidden_game": bool(a.get_editor_property("hidden"))})
    json.dump(rows, open(OUT, "w"), indent=1)
    u.log("PROBE_S2OURS_OK|n=%d|%s" % (len(rows), OUT))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("PROBE_S2OURS_FAILED|%r" % (exc,))
