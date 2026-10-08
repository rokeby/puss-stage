"""READ-ONLY: list P_Fire's emitters (name, render mode, LOD count) and the S3 fire emitter actors (scale, template).
PROBE_PFIRE_OK / _FAILED."""
import json


def main():
    import unreal as u
    em = []
    acts = []
    for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        l = str(a.get_actor_label())
        if l.startswith("S3 Fire") or l == "S3 Ghost Light Flame":
            c = a.get_component_by_class(u.ParticleSystemComponent)
            s = a.get_actor_scale3d()
            mats = [(i, c.get_material(i).get_path_name() if c.get_material(i) else None) for i in range(c.get_num_materials())] if c else []
            acts.append([l, a.get_class().get_name(), round(s.x, 3), str(c.get_editor_property("template").get_path_name()) if c else None, mats])
    u.log("PROBE_PFIRE_OK|emitters=%s|actors=%s" % (json.dumps(em), json.dumps(acts)))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("PROBE_PFIRE_FAILED|%r" % (exc,))
