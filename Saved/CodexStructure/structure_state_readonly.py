"""Read-only: the six structures' current flags and counts, and the dirty set, as
the editor holds them now. Mutates nothing."""
import json
import os

import unreal

COUNTS = ("station_count", "board_count", "slot_count", "fixture_body_count", "portal_piece_count")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
now = {a.get_actor_label(): {"current": bool(a.is_structure_current()), **{c: int(a.get_editor_property(c)) for c in COUNTS}}
       for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStageStructureActor)}
c = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
m = [str(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "structure_state.json")
json.dump({"structures": now, "dirty": {"content": c, "maps": m},
           "zz": [a.get_actor_label() for a in sub.get_all_level_actors() if a.get_actor_label().startswith("ZZ_")]},
          open(out, "w"), indent=1)
unreal.log(f"STRUCTURE_STATE_OK|current={sum(v['current'] for v in now.values())}/{len(now)}"
           f"|p05_slots={now.get('Infinity Stage - Structure 05', {}).get('slot_count')}|dirty={len(c)}+{len(m)}|mutated=0")
