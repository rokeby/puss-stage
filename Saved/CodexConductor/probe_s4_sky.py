"""Read-only: what gives S4 its sky. Lists sky/atmosphere/backdrop-ish actors per level (incl. her L_KK_children)
with bounds size, and the S4 hangar wall/roof actors' hidden flags. Marker S4SKY|"""
import json

import unreal

acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
sky = []
walls = []
for a in acts:
    cls = a.get_class().get_name()
    lab = str(a.get_actor_label())
    lvl = a.get_outermost().get_name().split("/")[-1]
    o, e = a.get_actor_bounds(False)
    big = max(e.x, e.y, e.z) * 2
    if any(k in cls for k in ("Sky", "Atmosphere", "Cloud", "Fog")) or any(k in lab.lower() for k in ("sky", "backdrop", "horizon", "ocean", "sea", "water", "cyc")) or (lvl == "L_KK_children" and big > 20000):
        sky.append([lvl, cls, lab[:40], round(big), bool(a.is_hidden_ed()), bool(a.get_editor_property("hidden"))])
    if lab.startswith("S4 Hangar") or lab.startswith("S4 ") and ("Wall" in lab or "Roof" in lab):
        walls.append([lab[:40], bool(a.get_editor_property("hidden"))])
unreal.log("S4SKY|sky=%s" % json.dumps(sky))
unreal.log("S4SKY_WALLS|%s" % json.dumps(walls))
