"""Read-only: P01 Wing 001's materialized light actors (world pose + settings), the row's Show attachments,
and the derived station anchor (from the untouched Low rects), plus the current Gap To Next per P01 row."""
import json, os, re
import unreal
def vec(v): return [round(v.x,2), round(v.y,2), round(v.z,2)]
def rot(r): return [round(r.pitch,3), round(r.yaw,3), round(r.roll,3)]
def tf(t): return {"loc": vec(t.translation), "rot": rot(t.rotation.rotator()), "scale": vec(t.scale3d)}
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = {}
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.Light) and a.get_actor_label().startswith("P01 Wing 001 "):
        c = a.get_component_by_class(unreal.LightComponent)
        rec = {"class": a.get_class().get_name(), "world": tf(a.get_actor_transform())}
        for n in ("intensity","intensity_units","light_color","attenuation_radius","inner_cone_angle","outer_cone_angle","source_radius","source_width","source_height","cast_shadows","temperature","use_temperature","light_function_material"):
            try:
                v = c.get_editor_property(n); rec[n] = v if isinstance(v,(int,float,bool)) else (v.get_path_name() if hasattr(v,"get_path_name") else str(v))
            except Exception: pass
        actors[a.get_actor_label()[len("P01 Wing 001 "):]] = rec
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
row = None; gaps = []
for cue in show.get_editor_property("cues"):
    label = str(cue.get_editor_property("label"))
    if label.startswith("P01 Wing"):
        try: gaps.append(float(cue.get_editor_property("wing_pair").get_editor_property("gap_to_next_cm")))
        except Exception as exc: gaps.append(repr(exc))
    if label == "P01 Wing 001":
        row = {}
        for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT: continue
            row[str(att.get_editor_property("label"))[len("P01 Wing 001 "):]] = {"rel": tf(att.get_editor_property("relative_transform")), "enabled": bool(att.get_editor_property("enabled")),
                "intensity": float(att.get_editor_property("lighting").get_editor_property("intensity"))}
# anchor from a rect: Anchor = Rel^-1 * World
anchor = None
for name in ("Low +Y", "Low -Y"):
    if name in actors and name in row:
        rel = unreal.Transform(); rel.translation = unreal.Vector(*row[name]["rel"]["loc"]); rel.rotation = unreal.Rotator(roll=row[name]["rel"]["rot"][2], pitch=row[name]["rel"]["rot"][0], yaw=row[name]["rel"]["rot"][1]).quaternion()
        w = unreal.Transform(); w.translation = unreal.Vector(*actors[name]["world"]["loc"]); w.rotation = unreal.Rotator(roll=actors[name]["world"]["rot"][2], pitch=actors[name]["world"]["rot"][0], yaw=actors[name]["world"]["rot"][1]).quaternion()
        anc = unreal.MathLibrary.compose_transforms(unreal.MathLibrary.invert_transform(rel), w)
        (anchor := anchor or {})[name] = tf(anc)
out = {"actors": actors, "show_row": row, "anchor_from_rects": anchor, "p01_gap_to_next": sorted(set(gaps)) if all(isinstance(g,float) for g in gaps) else gaps[:3]}
p = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting", "p01_tuned.json")
with open(p, "w", encoding="utf-8") as fh: json.dump(out, fh, indent=1, default=str)
unreal.log(f"PUSS_P01_TUNED_SUCCESS|actors={len(actors)}|row_lights={len(row or {})}|gaps={out['p01_gap_to_next']}")
