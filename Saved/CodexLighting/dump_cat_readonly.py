"""Read-only: every camera rig's shadow-cat settings, the child cat actor's mesh/animation/relative
transforms and a few bones. Saves nothing."""
import json
import os

import unreal


def vec(v):
    return [round(v.x, 2), round(v.y, 2), round(v.z, 2)]


def rot(r):
    return [round(r.pitch, 3), round(r.yaw, 3), round(r.roll, 3)]


def pkg(v):
    return v.get_path_name().split(".", 1)[0] if v is not None and hasattr(v, "get_path_name") else None


def tf(t):
    return {"loc": vec(t.translation), "rot": rot(t.rotation.rotator()), "scale": vec(t.scale3d)}


def props(o, names):
    out = {}
    for n in names:
        try:
            v = o.get_editor_property(n)
            if isinstance(v, (int, float, bool, str)) or v is None:
                out[n] = v
            elif isinstance(v, unreal.Vector):
                out[n] = vec(v)
            elif isinstance(v, unreal.Rotator):
                out[n] = rot(v)
            elif isinstance(v, unreal.Transform):
                out[n] = tf(v)
            elif hasattr(v, "get_path_name"):
                out[n] = pkg(v)
            else:
                out[n] = str(v)
        except Exception:  # noqa: BLE001
            pass
    return out


RIG_PROPS = ["camera_offset", "shadow_figure_offset", "keep_shadow_figures_world_upright", "enable_shadow_cat",
             "shadow_cat_position_offset", "shadow_cat_rotation_offset", "shadow_cat_uniform_scale",
             "shadow_cat_relative_transform", "shadow_cat_force_walk", "shadow_cat_use_direct_walk_animation",
             "shadow_cat_animation_speed_multiplier", "shadow_cat_min_play_rate", "shadow_cat_max_play_rate",
             "enable_follow_light", "follow_light_offset", "follow_light_rotation"]
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
rigs = []
cats = []
for a in sub.get_all_level_actors():
    cls = a.get_class().get_name()
    if cls == "InfinityStageCameraRig":
        rec = {"label": a.get_actor_label(), "loc": vec(a.get_actor_location()), "rot": rot(a.get_actor_rotation())}
        rec.update(props(a, RIG_PROPS))
        comps = []
        for c in a.get_components_by_class(unreal.SceneComponent):
            comps.append({"name": c.get_name(), "class": c.get_class().get_name(),
                          "rel_loc": vec(c.get_editor_property("relative_location")), "rel_rot": rot(c.get_editor_property("relative_rotation")),
                          "rel_scale": vec(c.get_editor_property("relative_scale3d")),
                          "parent": c.get_attach_parent().get_name() if c.get_attach_parent() else None})
        rec["components"] = comps
        rigs.append(rec)
    elif cls == "InfinityStageShadowCatActor":
        rec = {"label": a.get_actor_label(), "loc": vec(a.get_actor_location()), "rot": rot(a.get_actor_rotation()),
               "parent": a.get_attach_parent_actor().get_actor_label() if a.get_attach_parent_actor() else None}
        comps = []
        for c in a.get_components_by_class(unreal.SceneComponent):
            crec = {"name": c.get_name(), "class": c.get_class().get_name(),
                    "rel_loc": vec(c.get_editor_property("relative_location")), "rel_rot": rot(c.get_editor_property("relative_rotation")),
                    "rel_scale": vec(c.get_editor_property("relative_scale3d")),
                    "parent": c.get_attach_parent().get_name() if c.get_attach_parent() else None}
            if isinstance(c, unreal.SkeletalMeshComponent):
                crec.update(props(c, ["skeletal_mesh_asset", "animation_mode", "anim_class"]))
                try:
                    crec["anim_to_play"] = pkg(c.get_editor_property("animation_data").get_editor_property("anim_to_play"))
                except Exception:  # noqa: BLE001
                    pass
                try:
                    n = c.get_num_bones()
                    crec["bones"] = [str(c.get_bone_name(i)) for i in range(min(n, 12))]
                    crec["bone_count"] = n
                    for b in ("root", "pelvis", "Root", "Pelvis", "spine_01", "Spine1", "hips"):
                        if c.get_bone_index(b) >= 0:
                            crec.setdefault("bone_world", {})[b] = vec(c.get_bone_location(b, unreal.BoneSpaces.WORLD_SPACE))
                except Exception as exc:  # noqa: BLE001
                    crec["bones_error"] = repr(exc)
            comps.append(crec)
        rec["components"] = comps
        cats.append(rec)
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "cat_dump.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump({"rigs": rigs, "cats": cats}, fh, indent=1, default=str)
unreal.log(f"PUSS_CAT_DUMP_SUCCESS|rigs={len(rigs)}|cats={len(cats)}")
