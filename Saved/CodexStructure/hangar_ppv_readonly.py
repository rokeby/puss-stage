"""Read-only: the S4 and S5 hangar post-process volumes' exposure settings and extent, and
how many lights each hangar carries by kind. Mutates nothing."""
import unreal


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    out = []
    for a in sub.get_all_level_actors():
        lab = a.get_actor_label()
        if isinstance(a, unreal.PostProcessVolume) and ("S4" in lab or "S5" in lab or "Hangar" in lab):
            s = a.get_editor_property("settings")
            b = a.get_actor_bounds(False)
            out.append(f"{lab}: unbound={a.get_editor_property('unbound')} method={s.get_editor_property('auto_exposure_method')} "
                       f"ov_method={s.get_editor_property('override_auto_exposure_method')} bias={s.get_editor_property('auto_exposure_bias')} "
                       f"ov_bias={s.get_editor_property('override_auto_exposure_bias')} phys={s.get_editor_property('auto_exposure_apply_physical_camera_exposure')} "
                       f"minb={s.get_editor_property('auto_exposure_min_brightness')} maxb={s.get_editor_property('auto_exposure_max_brightness')} "
                       f"origin={b[0].to_tuple()} extent={b[1].to_tuple()}")
    for n in (4, 5):
        tag = unreal.Name(f"RigAtmos.Scene{n}Hangar")
        kinds = {}
        for a in sub.get_all_level_actors():
            if tag in a.tags:
                lc = a.get_component_by_class(unreal.LightComponent)
                if lc:
                    k = a.get_actor_label().split()[1] if len(a.get_actor_label().split()) > 1 else "?"
                    key = f"{lc.get_class().get_name()}"
                    kinds.setdefault(key, []).append(round(float(lc.get_editor_property("intensity")), 1))
        out.append(f"S{n} lights: " + "; ".join(f"{k} x{len(v)} rest {sorted(set(v))[:6]}" for k, v in kinds.items()))
    unreal.log("HANGAR_PPV|" + " || ".join(out))


main()
