"""Read-only: every enabled light attachment on Passage 01's cues, grouped by rig slot (the
attachment label's suffix after the wing name), with how many cast shadows, carry a light
function, or are set to blink (Light Drama). For the P01 shadow pass (P03's recipe: fills
shadowless, keys keep shadows). Writes p01_caster_survey.json. Mutates nothing."""
import json
import os
import re

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure", "p01_caster_survey.json")


def main():
    show = unreal.load_asset(SHOW)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    p01 = next(a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
    guid = p01.get_editor_property("passage_guid").to_string()
    settings = next(s for s in show.get_editor_property("passage_settings") if s.get_editor_property("passage_guid").to_string() == guid)
    cues = list(show.get_editor_property("cues"))
    ids = [c.get_editor_property("cue_guid").to_string() for c in cues]
    first, last = ids.index(settings.get_editor_property("first_cue_guid").to_string()), ids.index(settings.get_editor_property("last_cue_guid").to_string())
    slots, examples = {}, {}
    total = casters = 0
    for c in cues[first:last + 1]:
        wp = c.get_editor_property("wing_pair")
        cue_label = str(c.get_editor_property("label"))
        for att in wp.get_editor_property("attachments"):
            if not att.get_editor_property("enabled") or str(att.get_editor_property("kind")).split(".")[-1].split(":")[0].upper().find("LIGHT") < 0:
                continue
            L = att.get_editor_property("lighting")
            label = str(att.get_editor_property("label"))
            slot = re.sub(r"^P0?1 Wing \d+\s*", "", label) or label
            shadows = bool(L.get_editor_property("cast_shadows"))
            lf = None
            for name in ("light_function_material", "light_function"):
                try:
                    v = L.get_editor_property(name)
                    lf = v.get_name() if v else None
                    break
                except Exception:
                    pass
            drama = None
            try:
                d = att.get_editor_property("drama")
                drama = str(d.get_editor_property("mode")) if d else None
            except Exception:
                pass
            s = slots.setdefault(slot, {"n": 0, "casters": 0, "light_function": 0, "drama": {}, "type": str(L.get_editor_property("type"))})
            s["n"] += 1
            s["casters"] += shadows
            s["light_function"] += 1 if lf else 0
            if drama:
                s["drama"][drama] = s["drama"].get(drama, 0) + 1
            examples.setdefault(slot, f"{cue_label} | {label}")
            total += 1
            casters += shadows
    json.dump({"lights": total, "casters": casters, "slots": slots, "examples": examples}, open(OUT, "w"), indent=1)
    unreal.log(f"P01_CASTER_SURVEY_OK|lights={total}|casters={casters}|slots={len(slots)}")


main()
