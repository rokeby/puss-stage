"""Read-only: for the three plane grounds (S1, S5, S6), is anything but the hangar standing on the
part of the plane BEYOND the hinge line (so that ending the plane at the hinge would leave it
floating)? Actors whose bounds bottom sits within 60 cm of the plane's top, beyond the hinge and
inside the plane's width. Mutates nothing."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
PLANES = {1: "Passage 01 - Opening Floor", 5: "Passage 03 - Dark Wood Floor2", 6: "Passage 01 - Opening Floor2"}


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    by = {a.get_actor_label(): a for a in actors}
    out = []
    for n, label in PLANES.items():
        rec = json.load(open(os.path.join(HERE, f"hangar_s{n}_record.json"), encoding="utf-8"))
        hinge_x = rec["dock"]["loc"][0] + rec["hangar"]["apron"]
        po, pe = by[label].get_actor_bounds(False)
        top = po.z + pe.z
        on = []
        for a in actors:
            if a is by[label] or a.get_actor_label().startswith(f"S{n} ") or isinstance(a, (unreal.PostProcessVolume, unreal.CameraActor)):
                continue
            o, e = a.get_actor_bounds(False)
            if e.length() < 1.0 or max(e.x, e.y) > 2.0e5:
                continue
            if (o.x + e.x) > hinge_x and (o.x - e.x) < po.x + pe.x and abs(o.y - po.y) < pe.y + e.y and abs((o.z - e.z) - top) < 60.0:
                on.append(f"{a.get_actor_label()} x[{o.x - e.x:.0f},{o.x + e.x:.0f}]")
        out.append(f"S{n} {label}: hinge_x={hinge_x:.0f} plane_x[{po.x - pe.x:.0f},{po.x + pe.x:.0f}] beyond_m={(po.x + pe.x - hinge_x) / 100:.1f} standing_beyond={len(on)} {on[:8]}")
    unreal.log("GROUND_BEYOND|" + " || ".join(out))


main()
