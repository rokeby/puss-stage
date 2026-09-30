"""Read-only: which lights are in frame from P04's approach camera (x 10100, y 240000,
z 180, level, hfov 37.5, 960x540)? Projects every Light actor within 80 m ahead into
pixel coordinates, with its label, intensity, radius and world position, so bright spots
in the exposure-blend captures can be named rather than guessed. Mutates nothing."""
import math

import unreal

CAM = (10100.0, 240000.0, 180.0)
W, H, HFOV = 960, 540, 37.5


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    fx = (W / 2.0) / math.tan(math.radians(HFOV / 2.0))
    rows = []
    for a in sub.get_all_level_actors():
        if not isinstance(a, unreal.Light):
            continue
        p = a.get_actor_location()
        dx, dy, dz = p.x - CAM[0], p.y - CAM[1], p.z - CAM[2]
        if dx <= 50.0 or dx > 8000.0 or abs(dy) > 4000.0:
            continue
        u, v = W / 2.0 + fx * dy / dx, H / 2.0 - fx * dz / dx
        c = a.get_component_by_class(unreal.LightComponent)
        if not c or c.get_editor_property("intensity") <= 0.0:
            continue
        inframe = 0 <= u < W and 0 <= v < H
        rows.append((inframe, a.get_actor_label(), round(u), round(v), round(c.get_editor_property("intensity"), 1),
                     round(c.get_editor_property("attenuation_radius")), [round(p.x), round(p.y), round(p.z)],
                     a.get_attach_parent_actor().get_actor_label() if a.get_attach_parent_actor() else None))
    rows.sort(key=lambda r: (not r[0], r[3]))
    for r in rows[:60]:
        unreal.log(f"P04_LIGHT|inframe={r[0]}|{r[1]}|px=({r[2]},{r[3]})|cd={r[4]}|radius={r[5]}|world={r[6]}|parent={r[7]}")
    unreal.log(f"P04_LIGHTS_OK|lit_ahead={len(rows)}|in_frame={sum(1 for r in rows if r[0])}")


main()
