"""Gary 3 Oct: lift P04's 3 old ceiling top borders by +476 cm (world 2.24-6.50 m -> 7.00-11.26 m).
Top local_transform Z only. Originals to JSON first; materialize P04 only; save Show + level only; read back."""
import json, os, unreal
BASE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexFlatV3")
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
GUIDS = ["75FD539B104815DC315DBB85D6E69939", "D84BDBAEDF4EE4A952894D82ECD2841F", "51127A0ADA4FEED69D4CE693D1A650C0"]
LIFT = 476.0
def census():
    n = lambda ps: sorted(str(p.get_name()).split(".", 1)[0] for p in ps)
    return {"content": n(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": n(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
if ed.get_game_world() is not None: raise RuntimeError("P04TOP_PIE_ACTIVE")
if census() != {"content": [], "maps": []}: raise RuntimeError("P04TOP_DIRTY_START|" + json.dumps(census()))
show = unreal.load_asset(SHOW); cues = list(show.get_editor_property("cues"))
idx = {c.get_editor_property("cue_guid").to_string(): i for i, c in enumerate(cues)}
if any(g not in idx for g in GUIDS): raise RuntimeError("P04TOP_GUID_MISSING")
orig = {}
for g in GUIDS:
    top = cues[idx[g]].get_editor_property("wing_pair").get_editor_property("top")
    t = top.get_editor_property("local_transform")
    orig[g] = {"index": idx[g], "label": str(cues[idx[g]].get_editor_property("label")),
               "mesh": top.get_editor_property("mesh").get_path_name(), "loc": [t.translation.x, t.translation.y, t.translation.z]}
op = os.path.join(BASE, "p04_top_lift_originals.json")
if not os.path.isfile(op): open(op, "w").write(json.dumps(orig, indent=1))
unreal.log("FLATV3_P04TOP_ORIGINALS path=%s %s" % (op, json.dumps(orig)))
for g in GUIDS:
    cue = cues[idx[g]]; pair = cue.get_editor_property("wing_pair"); top = pair.get_editor_property("top")
    t = top.get_editor_property("local_transform")
    if abs(t.translation.z - 650.0) > 0.5: raise RuntimeError("P04TOP_UNEXPECTED_Z|%s|%s" % (g, t.translation.z))
    nt = unreal.Transform(location=unreal.Vector(t.translation.x, t.translation.y, t.translation.z + LIFT),
                          rotation=t.rotation.rotator(), scale=t.scale3d)
    top.set_editor_property("local_transform", nt); pair.set_editor_property("top", top)
    cue.set_editor_property("wing_pair", pair); cues[idx[g]] = cue
show.modify(); show.set_editor_property("cues", cues)
actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
          if a.get_class().get_name() == "InfinityStagePassageActor" and "Passage 04" in a.get_actor_label()]
if len(actors) != 1: raise RuntimeError("P04TOP_ACTOR_COUNT|%d" % len(actors))
if not actors[0].materialize_passage(): raise RuntimeError("P04TOP_MATERIALIZE_FAIL")
if census() != {"content": [SHOW], "maps": [WORLD]}: raise RuntimeError("P04TOP_DIRTY_SCOPE|" + json.dumps(census()))
if not unreal.EditorAssetLibrary.save_asset(SHOW, only_if_is_dirty=False): raise RuntimeError("P04TOP_SAVE_SHOW")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(): raise RuntimeError("P04TOP_SAVE_LEVEL")
if census() != {"content": [], "maps": []}: raise RuntimeError("P04TOP_DIRTY_AFTER|" + json.dumps(census()))
zs = {}
for ref in actors[0].get_editor_property("materialized_panels"):
    g = ref.get_editor_property("cue_guid").to_string()
    if g in GUIDS and "TOP" in str(ref.get_editor_property("side")).upper():
        comp = ref.get_editor_property("component"); mesh = comp.get_editor_property("static_mesh")
        tr = comp.get_instance_transform(int(ref.get_editor_property("instance_index")), True); b = mesh.get_bounding_box()
        pz = [tr.transform_location(unreal.Vector(x, y, z)).z for x in (b.min.x, b.max.x) for y in (b.min.y, b.max.y) for z in (b.min.z, b.max.z)]
        zs[g] = [round(min(pz), 1), round(max(pz), 1)]
if len(zs) != 3 or any(abs(v[0] - 700.0) > 1.5 or v[1] > 1150.0 for v in zs.values()):
    raise RuntimeError("P04TOP_READBACK_FAIL|" + json.dumps(zs))
unreal.log("FLATV3_P04TOP_OK saved_roots=%s world_z=%s" % (json.dumps([SHOW, WORLD]), json.dumps(zs)))
