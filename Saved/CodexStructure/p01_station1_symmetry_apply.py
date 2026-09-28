"""Make P01's first wing pair symmetric: its Right panel from +500 to +750, matching
its Left (-750) and the next two pairs (both +-750), so the mouth of the machine
revealed by the falling curtain is a uniform three-pair frame. Gary chose it
(28 Sep: "Yes", Rig & atmosphere session).

Guards the exact expected starting state, writes and re-reads a revert record
before changing anything, verifies every other P01 panel is untouched, then saves
only the Show and the level. p01_station1_symmetry_revert.py restores +500.
"""
import json
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
TARGET = "P01 Wing 001"
FROM_Y, TO_Y = 500.0, 750.0
RECORD = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                      "CodexStructure", "p01_station1_symmetry_record.json")
LABEL = re.compile(r"^P01 Wing \d{3}$")


def fail(message):
    raise RuntimeError(f"P01_STATION1_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def dirty():
    return ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def panel_state(cue):
    pair = cue.get_editor_property("wing_pair")
    out = []
    for side in ("left", "right", "top"):
        t = pair.get_editor_property(side).get_editor_property("local_transform")
        r = t.rotation.rotator()
        out.append([round(c, 3) for c in (t.translation.x, t.translation.y, t.translation.z,
                                          r.roll, r.pitch, r.yaw, t.scale3d.x, t.scale3d.y, t.scale3d.z)])
    return out


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
content0, maps0 = dirty()
if content0 or maps0:
    fail(f"editor already dirty: {content0} {maps0}")

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
cues = list(show.get_editor_property("cues"))
index = next((i for i, c in enumerate(cues) if str(c.get_editor_property("label")) == TARGET), None)
if index is None:
    fail(f"{TARGET} not in Show")
pair = cues[index].get_editor_property("wing_pair")
right_t = pair.get_editor_property("right").get_editor_property("local_transform")
left_t = pair.get_editor_property("left").get_editor_property("local_transform")
if abs(right_t.translation.y - FROM_Y) > 0.5 or abs(left_t.translation.y + TO_Y) > 0.5:
    fail(f"unexpected start: left {left_t.translation.y}, right {right_t.translation.y}")
before = {str(c.get_editor_property("label")): panel_state(c) for c in cues if LABEL.match(str(c.get_editor_property("label")))}

record = {"cue": TARGET, "right_local_y_before": right_t.translation.y, "right_local_y_after": TO_Y}
with open(RECORD, "w", encoding="utf-8") as fh:
    json.dump(record, fh, indent=1)
    fh.flush()
    os.fsync(fh.fileno())
if json.load(open(RECORD, encoding="utf-8")) != record:
    fail("revert record did not read back")
unreal.log(f"P01_STATION1_RECORD_OK|{RECORD}")

if globals().get("P01_STATION1_DRY_RUN"):
    unreal.log("P01_STATION1_DRY_RUN_OK|mutated=0")
    raise RuntimeError("P01_STATION1_DRY_RUN_COMPLETE")

show.modify()
right = pair.get_editor_property("right")
# Build the new transform explicitly: assigning into a struct copy's field may not
# write back through the Python wrapper.
moved = unreal.Transform(location=unreal.Vector(right_t.translation.x, TO_Y, right_t.translation.z),
                         rotation=right_t.rotation.rotator(), scale=right_t.scale3d)
right.set_editor_property("local_transform", moved)
pair.set_editor_property("right", right)
cue = cues[index]
cue.set_editor_property("wing_pair", pair)
cues[index] = cue
show.set_editor_property("cues", cues)

after_cues = list(show.get_editor_property("cues"))
after = {str(c.get_editor_property("label")): panel_state(c) for c in after_cues if LABEL.match(str(c.get_editor_property("label")))}
changed = [label for label in before if before[label] != after[label]]
if changed != [TARGET]:
    fail(f"expected only {TARGET} to change, changed: {changed}")
if abs(after[TARGET][1][1] - TO_Y) > 0.01 or before[TARGET][0] != after[TARGET][0] or before[TARGET][2] != after[TARGET][2]:
    fail("the edit touched more than the Right panel's y")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage = next(a for a in sub.get_all_level_actors()
               if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
if not passage.materialize_passage():
    fail("Passage 01 did not materialize")
guid = after_cues[index].get_editor_property("cue_guid")
live_y = None
for ref in passage.get_editor_property("materialized_panels"):
    if ref.get_editor_property("cue_guid") == guid and "RIGHT" in str(ref.get_editor_property("side")):
        live_y = ref.get_editor_property("base_world_transform").translation.y - passage.get_actor_location().y
if live_y is None or abs(live_y - TO_Y) > 1.0:
    fail(f"materialized right panel at {live_y}, expected {TO_Y}")
refit = False
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage:
        if not a.is_structure_current():
            if not a.materialize_structure():
                fail("Structure 01 did not re-fit")
            refit = True

content1, maps1 = dirty()
if set(content1) - {SHOW_PATH} or set(maps1) - {EXPECTED_WORLD}:
    fail(f"out-of-scope dirty before save: {content1} {maps1}")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
content2, maps2 = dirty()
unreal.log(f"P01_STATION1_APPLY_OK|cue={TARGET}|right_y={FROM_Y}->{TO_Y}|live_right_y={round(live_y, 2)}"
           f"|structure_refit={refit}|show_saved=1|level_saved=1|dirty_after={len(content2)}+{len(maps2)}")
