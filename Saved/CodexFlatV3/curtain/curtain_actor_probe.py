"""Read-only: list geometry-cache / curtain-like actors (label, class, cache, materials). Marker CURTAIN_PROBE_OK."""
import unreal
rows = []
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    lab = str(a.get_actor_label())
    comps = list(a.get_components_by_class(unreal.GeometryCacheComponent))
    if comps or any(k in lab.lower() for k in ("drape", "curtain", "backcloth")):
        info = []
        for c in comps:
            gc = c.get_editor_property("geometry_cache")
            mats = [str(c.get_material(i).get_name()) if c.get_material(i) else None for i in range(int(c.get_num_materials()))]
            info.append("%s|%s" % (gc.get_name() if gc else None, mats))
        loc = a.get_actor_location()
        rows.append("%s :: %s :: x=%.0f y=%.0f z=%.0f :: %s" % (lab, a.get_class().get_name(), loc.x, loc.y, loc.z, info))
for r in sorted(rows):
    unreal.log("CURTAIN_PROBE_ROW " + r)
unreal.log("CURTAIN_PROBE_OK rows=%d" % len(rows))
