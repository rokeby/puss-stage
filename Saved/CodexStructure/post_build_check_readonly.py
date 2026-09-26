"""Read-only, after the 25 Sep build: are the new types live in the editor, and did
the Show pick up the Drama field without changing any light?

Checks the structure actor class and its layer defaults, the Light Drama struct,
and every light attachment's Drama (all must still be off), plus zero dirty.
Spawns nothing and saves nothing.
"""
import collections
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
report = {}

report["structure_class_loaded"] = hasattr(unreal, "InfinityStageStructureActor")
report["drama_struct_loaded"] = hasattr(unreal, "InfinityStageLightDrama")
if report["structure_class_loaded"]:
    cdo = unreal.get_default_object(unreal.InfinityStageStructureActor)
    grid = cdo.get_editor_property("gridiron")
    ground = cdo.get_editor_property("ground")
    cloth = cdo.get_editor_property("cloth")
    fixtures = cdo.get_editor_property("fixtures")
    report["defaults"] = {
        "gridiron_height_cm": grid.get_editor_property("height_cm"),
        "gridiron_overhang_cm": grid.get_editor_property("overhang_cm"),
        "ground_enabled": ground.get_editor_property("enabled"),
        "slot_cat_clearance_cm": ground.get_editor_property("cat_clearance_cm"),
        "cloth_enabled": cloth.get_editor_property("enabled"),
        "cloth_pieces": [p.get_path_name() if hasattr(p, "get_path_name") else str(p)
                         for p in cloth.get_editor_property("pieces")],
        "fixtures_enabled": fixtures.get_editor_property("enabled"),
    }

sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
report["structure_actors_in_level"] = sum(
    1 for a in sub.get_all_level_actors()
    if report["structure_class_loaded"] and isinstance(a, unreal.InfinityStageStructureActor))

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
drama_states = collections.Counter()
lights = 0
for cue in show.get_editor_property("cues"):
    try:
        atts = cue.get_editor_property("wing_pair").get_editor_property("attachments")
    except Exception:
        continue
    for att in atts:
        if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT:
            continue
        lights += 1
        d = att.get_editor_property("lighting").get_editor_property("drama")
        drama_states[(bool(d.get_editor_property("strike_on_approach")), bool(d.get_editor_property("slow_move")))] += 1
report["show_lights"] = lights
report["drama_states"] = {f"strike={k[0]},move={k[1]}": n for k, n in drama_states.items()}

c = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
report["dirty"] = {"content": c, "maps": m}
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "post_build_check.json")
json.dump(report, open(out, "w"), indent=1, default=str)
active = sum(n for k, n in drama_states.items() if k != (False, False))
unreal.log(f"POST_BUILD_CHECK_OK|structure_class={report['structure_class_loaded']}|drama_struct={report['drama_struct_loaded']}"
           f"|lights={lights}|drama_active={active}|structure_actors={report['structure_actors_in_level']}"
           f"|dirty={len(c)}+{len(m)}|mutated=0")
