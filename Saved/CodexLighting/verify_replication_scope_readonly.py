"""Read-only: dump every Wing Pair's Light attachments from the live Show plus the passage cue ranges,
so the scope of the 18/19 Sep light replication can be audited offline. Writes no assets."""
import json, os
import unreal
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting")
def rot(r): return [round(r.pitch, 3), round(r.yaw, 3), round(r.roll, 3)]
def vec(v): return [round(v.x, 2), round(v.y, 2), round(v.z, 2)]
def g(o, n, default=None):
    try: return o.get_editor_property(n)
    except Exception: return default
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
if not show: raise RuntimeError("Show did not load")
cues = list(show.get_editor_property("cues"))
label = lambda i: str(cues[i].get_editor_property("label")) if 0 <= i < len(cues) else None
passages = []
for pi, ps in enumerate(show.get_editor_property("passage_settings")):
    f = show.find_cue_index(ps.get_editor_property("first_cue_guid")); l = show.find_cue_index(ps.get_editor_property("last_cue_guid"))
    passages.append({"passage": pi + 1, "first_index": f, "first_label": label(f), "last_index": l, "last_label": label(l)})
pairs = {}; other_kind_lights = []
for i, cue in enumerate(cues):
    if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR: continue
    atts = list(cue.get_editor_property("wing_pair").get_editor_property("attachments"))
    lights = []; kinds = {}
    for a in atts:
        k = str(a.get_editor_property("kind")).split(".")[-1]; kinds[k] = kinds.get(k, 0) + 1
        if a.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT: continue
        t = a.get_editor_property("relative_transform"); L = a.get_editor_property("lighting")
        lf = g(L, "light_function_material")
        lights.append({"slot": len(lights), "label": str(a.get_editor_property("label")), "guid": str(a.get_editor_property("attachment_guid")),
                       "enabled": bool(a.get_editor_property("enabled")), "type": str(g(L, "type")).split(".")[-1],
                       "loc": vec(t.translation), "rot": rot(t.rotation.rotator()), "intensity": round(float(g(L, "intensity", 0.0)), 4),
                       "color": str(g(L, "color")), "cone": [g(L, "inner_cone_angle_degrees"), g(L, "outer_cone_angle_degrees")],
                       "radius": g(L, "attenuation_radius_cm"), "source_radius": g(L, "source_radius_cm"), "cast_shadows": g(L, "cast_shadows"),
                       "lf": lf.get_name() if lf else None})
    pairs[str(i)] = {"label": str(cue.get_editor_property("label")), "kinds": kinds, "lights": lights}

dirty = {"show_dirty": SHOW_PATH in [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
         "dirty_content": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
         "dirty_maps": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
world = ed.get_editor_world(); wp = world.get_path_name().split(".", 1)[0] if world else None
out = os.path.join(OUT, "replication_scope_verify.json")
json.dump({"world": wp, "pie": ed.get_game_world() is not None, "cue_count": len(cues), "passages": passages, "pairs": pairs, "dirty": dirty},
          open(out, "w", encoding="utf-8"), indent=1, default=str)
unreal.log(f"PUSS_REPL_SCOPE_VERIFY_SUCCESS|pairs={len(pairs)}|passages={len(passages)}|world={wp}|show_dirty={dirty['show_dirty']}")
