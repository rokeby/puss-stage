"""Mass-edit the generated stage-light attachments in the Show from light_adjust.json (no save).

Spec (light_adjust.json):
{
  "dry_run": false,
  "edits": [
    {
      "match": {"passages": [1,2], "slots": ["Cross +Y", "Cross -Y"], "ordinals": [1,2,3], "types": ["Spot"]},
      "translate_cm": [0, 0, 40],          # added to the relative location (station frame: X route, Y right, Z up)
      "rotate_deg": [-5, 0, 0],            # added to [pitch, yaw, roll]
      "intensity_multiply": 1.5,           # or "intensity_set": 4.0 (candelas)
      "radius_cm": 2200, "cone_deg": [12, 40], "color": [1.0, 0.7, 0.4], "temperature_k": null,
      "cast_shadows": true, "flicker": "Hum", "enabled": true
    }
  ]
}
Every key except "match" is optional. Matching is by slot label suffix (the part after the cue label),
Passage number, ordinal within the Passage, and light type. Edits are applied in order.
Writes adjust_result.json and mirrors the changes into lighting_plan.json so a later re-apply keeps them."""
import json
import os

import unreal

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexLighting")
LIGHTING_ROOT = "/Game/InfinityStage/Lighting"


def require(c, m):
    if not c:
        raise RuntimeError(m)


spec = json.load(open(os.path.join(OUT, "light_adjust.json"), encoding="utf-8"))
dry = bool(spec.get("dry_run", False))
plan = json.load(open(os.path.join(OUT, "lighting_plan.json"), encoding="utf-8"))
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
require(ed.get_game_world() is None, "PIE active")
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
require(show is not None, "Show did not load")


def matches(m, passage, ordinal, slot_name, ltype):
    if "passages" in m and passage not in m["passages"]:
        return False
    if "ordinals" in m and ordinal not in m["ordinals"]:
        return False
    if "slots" in m and slot_name not in m["slots"]:
        return False
    if "types" in m and ltype not in m["types"]:
        return False
    return True


cues = list(show.get_editor_property("cues"))
touched_passages = set()
counts = [0] * len(spec.get("edits", []))
changed_rows = 0
for i, cue in enumerate(cues):
    prow = plan.get(str(i))
    if not prow:
        continue
    pair = cue.get_editor_property("wing_pair")
    atts = list(pair.get_editor_property("attachments"))
    lights = [k for k, a in enumerate(atts) if a.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT]
    require(len(lights) == len(prow["lights"]), f"row {i}: {len(lights)} light slots vs plan {len(prow['lights'])}")
    row_changed = False
    for slot in prow["lights"]:
        att = atts[lights[slot["slot"]]]
        slot_name = slot["label"][len(prow["label"]) + 1:]
        for e_index, e in enumerate(spec.get("edits", [])):
            if not matches(e.get("match", {}), prow["passage"], prow["ordinal"], slot_name, slot["type"]):
                continue
            counts[e_index] += 1
            row_changed = True
            if dry:
                continue
            L = att.get_editor_property("lighting")
            if "translate_cm" in e:
                slot["loc"] = [round(a + b, 2) for a, b in zip(slot["loc"], e["translate_cm"])]
            if "rotate_deg" in e:
                slot["rot"] = [round(a + b, 3) for a, b in zip(slot["rot"], e["rotate_deg"])]
            if "intensity_multiply" in e:
                slot["intensity_cd"] = round(slot["intensity_cd"] * float(e["intensity_multiply"]), 4)
            if "intensity_set" in e:
                slot["intensity_cd"] = float(e["intensity_set"])
            for key in ("radius_cm", "cast_shadows", "enabled", "flicker", "temperature_k"):
                if key in e:
                    slot[{"radius_cm": "radius"}.get(key, key)] = e[key]
            if "cone_deg" in e:
                slot["cone"] = list(e["cone_deg"])
            if "color" in e:
                slot["color"] = list(e["color"])
            t = unreal.Transform()
            t.translation = unreal.Vector(*slot["loc"])
            t.rotation = unreal.Rotator(roll=slot["rot"][2], pitch=slot["rot"][0], yaw=slot["rot"][1]).quaternion()
            att.set_editor_property("relative_transform", t)
            att.set_editor_property("enabled", bool(slot["enabled"]))
            L.set_editor_property("intensity", float(slot["intensity_cd"]))
            L.set_editor_property("attenuation_radius_cm", float(slot["radius"]))
            c = slot["color"]
            L.set_editor_property("color", unreal.LinearColor(c[0], c[1], c[2], 1.0))
            L.set_editor_property("use_temperature", slot.get("temperature_k") is not None)
            if slot.get("temperature_k") is not None:
                L.set_editor_property("temperature_kelvin", float(slot["temperature_k"]))
            if slot["cone"][0] is not None:
                L.set_editor_property("inner_cone_angle_degrees", float(slot["cone"][0]))
                L.set_editor_property("outer_cone_angle_degrees", float(slot["cone"][1]))
            L.set_editor_property("cast_shadows", bool(slot["cast_shadows"]))
            if "max_draw_distance_cm" in e:
                L.set_editor_property("max_draw_distance_cm", float(e["max_draw_distance_cm"]))
                L.set_editor_property("max_distance_fade_range_cm", float(e.get("fade_range_cm", 0.0)))
            mi = unreal.EditorAssetLibrary.load_asset(f"{LIGHTING_ROOT}/MI_LF_Flicker_{slot['flicker']}")
            require(mi is not None, f"unknown flicker profile {slot['flicker']}")
            L.set_editor_property("light_function_material", mi)
            att.set_editor_property("lighting", L)
            atts[lights[slot["slot"]]] = att
    if row_changed:
        changed_rows += 1
        touched_passages.add(prow["passage"])
        if not dry:
            pair.set_editor_property("attachments", atts)
            cue.set_editor_property("wing_pair", pair)
            cues[i] = cue

materialized = {}
if not dry and changed_rows:
    show.modify()
    show.set_editor_property("cues", cues)
    json.dump(plan, open(os.path.join(OUT, "lighting_plan.json"), "w", encoding="utf-8"), indent=1)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in sub.get_all_level_actors():
        if a.get_class().get_name() != "InfinityStagePassageActor":
            continue
        label = a.get_actor_label()
        p = int(label[8:10]) if label.startswith("Passage 0") else None
        if p in touched_passages:
            require(bool(a.materialize_passage()), f"materialize failed: {label}")
            materialized[p] = int(a.get_editor_property("materialized_wing_pair_count"))
result = {"dry_run": dry, "matches_per_edit": counts, "rows_changed": changed_rows,
          "passages_rematerialized": sorted(materialized), "saved": False}
json.dump(result, open(os.path.join(OUT, "adjust_result.json"), "w", encoding="utf-8"), indent=1)
unreal.log(f"STAGE_LIGHT_ADJUST_{'DRYRUN' if dry else 'SUCCESS'}|matches={counts}|rows={changed_rows}|passages={sorted(materialized)}|saved=0")
