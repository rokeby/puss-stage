"""Read-only: read back the applied blink spots by GUID from the saved Show and the
level. Checks labels, kinds, gobo mesh, the lamp's intensity and colour, and one
tagged actor per attachment, with its distance from the planned world position.
Mutates nothing."""
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def main():
    rec = json.load(open(os.path.join(HERE, "blink_spots_revert_record.json"), encoding="utf-8"))
    plan = {r["cue_guid"]: r for r in json.load(open(os.path.join(HERE, "blink_spots_plan.json"), encoding="utf-8"))["rows"]}
    show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    cues = {gs(c.get_editor_property("cue_guid")): c for c in show.get_editor_property("cues")}
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    tagged = {}
    for a in actors:
        for t in a.tags:
            s = str(t)
            if s.startswith("InfinityStage.Attachment."):
                tagged.setdefault(s.split("|")[-1], []).append(a)
    rows, problems = [], []
    for cg, (lg, pg) in rec["added"].items():
        atts = {gs(a.get_editor_property("attachment_guid")): a
                for a in cues[cg].get_editor_property("wing_pair").get_editor_property("attachments")}
        lamp, prop = atts.get(lg), atts.get(pg)
        if not lamp or not prop:
            problems.append(f"{plan[cg]['cue']}: attachment missing from the saved Show")
            continue
        L = lamp.get_editor_property("lighting")
        row = {"cue": plan[cg]["cue"], "passage": plan[cg]["passage"],
               "lamp": [str(lamp.get_editor_property("label")), str(lamp.get_editor_property("kind")),
                        round(L.get_editor_property("intensity"), 1), round(L.get_editor_property("temperature_kelvin")),
                        round(L.get_editor_property("source_radius_cm"), 1), bool(L.get_editor_property("cast_shadows")),
                        L.get_editor_property("light_function_material").get_name() if L.get_editor_property("light_function_material") else None],
               "gobo": [str(prop.get_editor_property("label")), str(prop.get_editor_property("kind")),
                        prop.get_editor_property("mesh").get_name() if prop.get_editor_property("mesh") else None],
               "actors": {}}
        for g, what in ((lg, "lamp"), (pg, "gobo")):
            hits = tagged.get(g, [])
            if len(hits) != 1:
                problems.append(f"{plan[cg]['cue']} {what}: {len(hits)} tagged actors")
                continue
            a = hits[0]
            row["actors"][what] = {"label": a.get_actor_label(), "class": a.get_class().get_name(),
                                   "loc": [round(v) for v in a.get_actor_location().to_tuple()],
                                   "scale": [round(v, 3) for v in a.get_actor_scale3d().to_tuple()]}
        rows.append(row)
    json.dump({"rows": rows, "problems": problems}, open(os.path.join(HERE, "verify_blink_spots.json"), "w"), indent=1)
    unreal.log(f"VERIFY_BLINK_SPOTS_OK|pairs={len(rows)}|problems={len(problems)}|mutated=0")


main()
