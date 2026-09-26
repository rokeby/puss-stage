"""Replace the Python gridiron preview with the C++ structure pass and save the
level only. Approved by Gary on 26 Sep 2026 ("1 yes"); run inside the
conductor's level slot, after a Backups/PreStructureSwap-* snapshot.

Ownership: the preview is destroyed by its InfinityStage.Gridiron tag and by
nothing else. The C++ actors carry InfinityStage.Structure, so neither pass can
eat the other's output, and hand-placed actors are never touched. One
structure actor per Passage is reused on reruns, so this is idempotent.

Ground is on where the corridor floor is empty and off for Passage 03, whose
"Wet Ground" Landscape sits at about +10 cm and would bury the boards
(ground_conflict_probe_readonly.py, 26 Sep). Cloth stays off until Soft goods'
pieces are imported.
"""
import json
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LEGACY_TAG = "InfinityStage.Gridiron"
GRIDIRON_LAYER = "InfinityStage.Structure.Gridiron"
PASSAGE_LABEL = re.compile(r"^Passage (\d{2})\b")
GROUND_OFF = {"03"}
# The conductor's offscreen capture flags the map dirty with no net change and
# no API clears it. Set True only once the conductor confirms that is the sole
# cause, because the level save below persists whatever made it dirty.
ACCEPT_MAP_ALREADY_DIRTY = False


def fail(message):
    raise RuntimeError(f"STRUCTURE_SWAP_FAILED|{message}")


def dirty():
    def pk(p):
        s = str(p)
        return s.split("'")[1].split(".")[0] if "'" in s else s
    return ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def layer(structure, tag):
    for comp in structure.get_editor_property("managed_components"):
        if comp and tag in [str(t) for t in comp.get_editor_property("component_tags")]:
            return comp
    return None


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
if not hasattr(unreal, "InfinityStageStructureActor"):
    fail("InfinityStageStructureActor is not in the loaded plugin - stale binaries")
content0, maps0 = dirty()
if content0:
    fail(f"content already dirty: {content0}")
if maps0 and not ACCEPT_MAP_ALREADY_DIRTY:
    fail(f"level already dirty: {maps0} - confirm the cause with the conductor first")

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
legacy = {}
removed = 0
for a in list(sub.get_all_level_actors()):
    if LEGACY_TAG in [str(t) for t in a.get_editor_property("tags")]:
        isms = a.get_components_by_class(unreal.InstancedStaticMeshComponent)
        legacy[a.get_actor_label()[-2:]] = sum(c.get_instance_count() for c in isms)
        a.destroy_actor()
        removed += 1

existing = {}
for a in sub.get_all_level_actors():
    if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage"):
        existing[a.get_editor_property("passage").get_path_name()] = a

report = {"legacy_removed": removed, "legacy_instances": legacy, "passages": {}}
for passage in sub.get_all_level_actors():
    if not isinstance(passage, unreal.InfinityStagePassageActor):
        continue
    m = PASSAGE_LABEL.match(passage.get_actor_label())
    if not m:
        continue
    number = m.group(1)
    structure = existing.get(passage.get_path_name())
    spawned = structure is None
    if spawned:
        structure = sub.spawn_actor_from_class(
            unreal.InfinityStageStructureActor, passage.get_actor_location(), passage.get_actor_rotation())
        structure.set_actor_label(f"Infinity Stage - Structure {number}")
        structure.set_folder_path("Infinity Stage/Structure")
        structure.set_editor_property("passage", passage)
    ground = structure.get_editor_property("ground")
    ground.set_editor_property("enabled", number not in GROUND_OFF)
    structure.set_editor_property("ground", ground)
    if not structure.materialize_structure():
        fail(f"materialize_structure returned false for Passage {number}")
    grid = layer(structure, GRIDIRON_LAYER)
    grid_instances = grid.get_instance_count() if grid else 0
    entry = {
        "spawned": spawned,
        "stations": int(structure.get_editor_property("station_count")),
        "cross_beams": int(structure.get_editor_property("cross_beam_count")),
        "rail_segments": int(structure.get_editor_property("rail_segment_count")),
        "gridiron_instances": grid_instances,
        "half_span_cm": round(float(structure.get_editor_property("grid_half_width_cm")), 1),
        "ground": number not in GROUND_OFF,
        "boards": int(structure.get_editor_property("board_count")),
        "slots": int(structure.get_editor_property("slot_count")),
        "housings": int(structure.get_editor_property("fixture_body_count")),
        "lines": int(structure.get_editor_property("hanging_line_count")),
        "moving_lights_skipped": int(structure.get_editor_property("moving_lights_without_housing")),
        "structure_current": bool(structure.is_structure_current()),
    }
    report["passages"][number] = entry
    if not entry["structure_current"]:
        fail(f"Passage {number} structure is not current straight after building")
    if number in legacy and legacy[number] != grid_instances:
        fail(f"Passage {number}: C++ gridiron has {grid_instances} timbers, preview had {legacy[number]}")

if len(report["passages"]) != 6:
    fail(f"expected 6 Passages, built {len(report['passages'])}")
content1, maps1 = dirty()
if content1 or maps1 != [EXPECTED_WORLD]:
    fail(f"unexpected dirty set before save: {content1} {maps1}")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
content2, maps2 = dirty()
report["dirty_after_save"] = {"content": content2, "maps": maps2}

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "swap_gridiron_to_cpp.json")
json.dump(report, open(out, "w"), indent=1)
grid_total = sum(p["gridiron_instances"] for p in report["passages"].values())
unreal.log(f"STRUCTURE_SWAP_OK|legacy_removed={removed}|passages={len(report['passages'])}|gridiron={grid_total}"
           f"|boards={sum(p['boards'] for p in report['passages'].values())}"
           f"|housings={sum(p['housings'] for p in report['passages'].values())}"
           f"|level_saved=1|dirty_after={len(content2)}+{len(maps2)}")
