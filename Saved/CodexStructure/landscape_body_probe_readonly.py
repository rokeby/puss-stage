"""Read-only: what the failed collision step left. Per landscape: the proxy's own body_instance collision fields, and
a sample heightfield collision component's get_collision_enabled() and its own body_instance fields; dirty packages."""
import unreal


def fields(bi):
    out = {}
    for k in ("collision_enabled", "collision_profile_name", "object_type"):
        try:
            out[k] = str(bi.get_editor_property(k))
        except Exception as exc:  # noqa: BLE001
            out[k] = f"n/a ({exc.__class__.__name__})"
    return out


def main():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    by = {a.get_actor_label(): a for a in sub.get_all_level_actors()}
    rows = []
    for label in ("Passage 1 - ForestedLandscape", "Passage 3 - Wet Ground"):
        L = by[label]
        try:
            proxy_bi = fields(L.get_editor_property("body_instance"))
        except Exception as exc:  # noqa: BLE001
            proxy_bi = f"n/a ({exc})"
        comps = list(L.get_components_by_class(unreal.LandscapeHeightfieldCollisionComponent))
        c = comps[0]
        rows.append(f"{label}: proxy_body={proxy_bi} | comp0 enabled={c.get_collision_enabled().name} comp0_body={fields(c.get_editor_property('body_instance'))} "
                    f"| comps states={sorted({x.get_collision_enabled().name for x in comps})}")
    dirty = [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()] + [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    unreal.log("LS_BODY_PROBE|" + " || ".join(rows) + f" || dirty={dirty}")


main()
