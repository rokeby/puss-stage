"""Generate a timber gridiron over each Passage, derived from the materialized wing
stations so it shares the wings' rhythm. Regenerable: destroys its own previous
output only, by tag, and never touches hand-placed actors. No save.

Env: PUSS_GRID_HEIGHT_CM, PUSS_GRID_MARGIN_CM, PUSS_GRID_BEAM_W_CM,
     PUSS_GRID_BEAM_H_CM, PUSS_GRID_EVERY (cross beam every Nth bay)
"""
import collections
import json
import os

import unreal

EXPECTED_WORLD = "L_InfinityStage_V1VerticalSlice"
TAG = "InfinityStage.Gridiron"
CUBE = "/Engine/BasicShapes/Cube.Cube"
HEIGHT = float(os.environ.get("PUSS_GRID_HEIGHT_CM", "1150"))   # above the 10 m wings
MARGIN = float(os.environ.get("PUSS_GRID_MARGIN_CM", "220"))    # beams overhang the corridor
BEAM_W = float(os.environ.get("PUSS_GRID_BEAM_W_CM", "26"))     # timber section across route
BEAM_H = float(os.environ.get("PUSS_GRID_BEAM_H_CM", "34"))     # timber section vertical
EVERY = int(os.environ.get("PUSS_GRID_EVERY", "1"))

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and EXPECTED_WORLD in world.get_path_name(), "wrong project"
assert ed.get_game_world() is None, "PIE active - stop PIE first"
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
cube = unreal.EditorAssetLibrary.load_asset(CUBE)
assert cube, "engine cube missing"

removed = 0
for a in list(sub.get_all_level_actors()):
    if any(str(t) == TAG for t in a.get_editor_property("tags")):
        a.destroy_actor()
        removed += 1

report = {"removed": removed, "passages": {}}
for passage in sub.get_all_level_actors():
    if passage.get_class().get_name() != "InfinityStagePassageActor":
        continue
    label = passage.get_actor_label()
    if not label.startswith("Passage 0"):
        continue

    # Stations come from what materialization actually placed, so the gridiron
    # cannot drift out of step with the wings.
    by_cue = collections.defaultdict(dict)
    for ref in passage.get_editor_property("materialized_panels"):
        g = unreal.GuidLibrary.conv_guid_to_string(ref.get_editor_property("cue_guid"))
        side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0].strip().rstrip(">")
        by_cue[g][side] = ref.get_editor_property("base_world_transform").translation
    stations = []
    for sides in by_cue.values():
        if "LEFT" in sides and "RIGHT" in sides:
            L, R = sides["LEFT"], sides["RIGHT"]
            stations.append((
                unreal.Vector((L.x + R.x) / 2.0, (L.y + R.y) / 2.0, (L.z + R.z) / 2.0),
                abs(L.y - R.y)))
    if not stations:
        continue
    stations.sort(key=lambda s: s[0].x)
    half = max(s[1] for s in stations) / 2.0 + MARGIN

    actor = sub.spawn_actor_from_class(unreal.Actor, stations[0][0], unreal.Rotator())
    actor.set_actor_label(f"Infinity Stage - Gridiron {label[8:10]}")
    actor.set_folder_path("Infinity Stage/Gridiron")
    actor.tags = [unreal.Name(TAG)]
    # SubobjectDataSubsystem is the exposed editor route for adding a component to
    # a placed actor; the direct AActor helpers are not available to Python.
    handles = sds.k2_gather_subobject_data_for_instance(actor)
    params = unreal.AddNewSubobjectParams(
        parent_handle=handles[0], new_class=unreal.InstancedStaticMeshComponent, blueprint_context=None)
    handle, fail = sds.add_new_subobject(params)
    assert not fail or str(fail) in ("", "None"), f"add_new_subobject failed: {fail}"
    sds.rename_subobject(handle, unreal.Text("GridironBeams"))
    ism = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(
        unreal.SubobjectDataBlueprintFunctionLibrary.get_data(handle))
    ism.set_static_mesh(cube)
    ism.set_mobility(unreal.ComponentMobility.STATIC)

    crosses = rails = 0
    origin = actor.get_actor_location()

    def add(local_loc, scale):
        t = unreal.Transform()
        t.translation = local_loc
        t.scale3d = scale
        ism.add_instance(t, False)

    for index, (centre, _width) in enumerate(stations):
        if index % EVERY == 0:
            # Cross beam: spans the corridor, overhanging both sides.
            add(unreal.Vector(centre.x - origin.x, centre.y - origin.y, HEIGHT),
                unreal.Vector(BEAM_W / 100.0, (half * 2.0) / 100.0, BEAM_H / 100.0))
            crosses += 1
        if index + 1 < len(stations):
            nxt = stations[index + 1][0]
            span = nxt.x - centre.x
            midx = (centre.x + nxt.x) / 2.0 - origin.x
            midy = (centre.y + nxt.y) / 2.0 - origin.y
            for side in (-1.0, 1.0):
                add(unreal.Vector(midx, midy + side * half, HEIGHT + BEAM_H),
                    unreal.Vector(span / 100.0, BEAM_W / 100.0, BEAM_H / 100.0))
                rails += 1

    report["passages"][label[:10]] = {
        "stations": len(stations), "cross_beams": crosses, "rail_segments": rails,
        "half_width_cm": round(half), "height_cm": HEIGHT,
        "instances": ism.get_instance_count(),
    }

d = {"content": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
     "maps": [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]}
report["dirty"] = d
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexLighting", "gridiron_build.json")
json.dump(report, open(out, "w"), indent=1, default=str)
total = sum(p["instances"] for p in report["passages"].values())
unreal.log(f"GRIDIRON_BUILT|removed={removed}|passages={len(report['passages'])}|instances={total}"
           f"|height={HEIGHT}|dirty={len(d['content'])}+{len(d['maps'])}|saved=0")
