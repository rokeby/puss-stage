"""READ-ONLY (30 Sep): the lane inventory could not place LS_OrtalanSheetSway's eight "SkeletalMesh" bindings (Location
defaults of 0, no actor with that label). If they are COMPONENT bindings under an actor binding, their transforms are
relative and they ride with that actor. For each binding: its parent binding, the class it possesses, and the lane of
the actor the parent's name matches (by label; labels can drift, so a miss is reported, not guessed). Also where the
LevelSequenceActor that plays it points. Mutates nothing. Marker ORTOLAN_OWNERS|run=<id>."""
import datetime
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    seq = unreal.load_asset("/Game/Scenes/LS_OrtalanSheetSway")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_label = {}
    for a in actors:
        by_label.setdefault(a.get_actor_label(), []).append(a)
    rows = []
    for b in seq.get_bindings():
        parent = b.get_parent()
        pname = str(parent.get_display_name()) if parent and parent.is_valid() else None
        cls = b.get_possessed_object_class()
        hit = by_label.get(pname, []) if pname else by_label.get(str(b.get_display_name()), [])
        loc = hit[0].get_actor_location() if len(hit) == 1 else None
        rows.append({"binding": str(b.get_display_name()), "class": cls.get_name() if cls else None, "parent": pname,
                     "tracks": [t.get_class().get_name() for t in b.get_tracks()],
                     "owner_matches": len(hit), "owner_loc_m": [round(loc.x / 100, 1), round(loc.y / 100, 1), round(loc.z / 100, 1)] if loc else None})
    player = [a for a in actors if a.get_actor_label() == "LS_OrtalanSheetSway"]
    with open(os.path.join(HERE, f"ortolan_sway_owners_{run}.json"), "w", encoding="utf-8") as fh:
        json.dump({"run": run, "rows": rows}, fh, indent=1)
    unreal.log(f"ORTOLAN_OWNERS|run={run}|players={len(player)}|" + " || ".join(
        f"{r['binding']}<{r['class']}> parent={r['parent']} owner_matches={r['owner_matches']} at={r['owner_loc_m']} tracks={r['tracks']}" for r in rows))


main()
