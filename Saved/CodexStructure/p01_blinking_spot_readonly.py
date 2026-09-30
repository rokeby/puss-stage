"""Read-only: find and characterise Gary's "blinking spotlight with a shadow in it
near the end of P01". Lists every P01 light that stands out: a light function (a
flicker), Light Drama active (strike, stutter, slow move), an intensity far above
its slot's median, or a narrow cone. For each: cue, route position, all settings,
world pose, and what its axis hits first (what it throws a shadow OF). Mutates
nothing.
"""
import json
import os
import re
import statistics

import unreal

LABEL = re.compile(r"^(P01 Wing \d{3}) (.+)$")


def plain(v):
    if isinstance(v, (bool, int, str)) or v is None:
        return v
    if isinstance(v, float):
        return round(v, 3)
    if isinstance(v, unreal.Object):
        return v.get_path_name()
    if isinstance(v, (unreal.LinearColor, unreal.Color)):
        return [round(v.r, 3), round(v.g, 3), round(v.b, 3)]
    return str(v)


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    p01 = next(p for p in sub.get_all_level_actors()
               if isinstance(p, unreal.InfinityStagePassageActor) and p.get_actor_label().startswith("Passage 01"))
    ptf = p01.get_actor_transform()
    rows = []
    for cue in show.get_editor_property("cues"):
        label = str(cue.get_editor_property("label"))
        if not label.startswith("P01 Wing"):
            continue
        for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT:
                continue
            m = LABEL.match(str(att.get_editor_property("label")))
            L = att.get_editor_property("lighting")
            D = L.get_editor_property("drama")
            wt = p01.get_attachment_world_transform(cue.get_editor_property("cue_guid"), att.get_editor_property("attachment_guid"))
            rec = {"cue": label, "slot": m.group(2) if m else str(att.get_editor_property("label")),
                   "enabled": bool(att.get_editor_property("enabled")),
                   "type": plain(L.get_editor_property("type")), "intensity": plain(L.get_editor_property("intensity")),
                   "kelvin": plain(L.get_editor_property("temperature_kelvin")) if L.get_editor_property("use_temperature") else None,
                   "cone": [plain(L.get_editor_property("inner_cone_angle_degrees")), plain(L.get_editor_property("outer_cone_angle_degrees"))],
                   "radius": plain(L.get_editor_property("attenuation_radius_cm")),
                   "shadows": bool(L.get_editor_property("cast_shadows")),
                   "light_function": plain(L.get_editor_property("light_function_material")),
                   "drama": {"strike": bool(D.get_editor_property("strike_on_approach")),
                             "stutter": plain(D.get_editor_property("ignition_stutter")),
                             "slow_move": bool(D.get_editor_property("slow_move")),
                             "after_pass": plain(D.get_editor_property("after_pass"))}}
            if isinstance(wt, unreal.Transform):
                loc = wt.translation
                local = unreal.MathLibrary.inverse_transform_location(ptf, loc)
                fwd = unreal.MathLibrary.get_forward_vector(wt.rotation.rotator())
                rec["world"] = [round(loc.x), round(loc.y), round(loc.z)]
                rec["route_x"] = round(local.x)
                rec["aim"] = [round(fwd.x, 3), round(fwd.y, 3), round(fwd.z, 3)]
                hit = unreal.SystemLibrary.line_trace_single(world, loc, loc + fwd * 6000.0,
                                                             unreal.TraceTypeQuery.ECC_VISIBILITY, True, [],
                                                             unreal.DrawDebugTrace.NONE, True)
                h = hit.to_tuple() if hit else None
                if h and h[0]:
                    actor = next((x for x in h if isinstance(x, unreal.Actor)), None)
                    comp = next((x for x in h if isinstance(x, unreal.PrimitiveComponent)), None)
                    rec["axis_hits"] = {"actor": actor.get_actor_label() if actor else None,
                                        "component": comp.get_name() if comp else None,
                                        "distance_cm": round(h[3]) if isinstance(h[3], float) else None}
            rows.append(rec)
    by_slot = {}
    for r in rows:
        by_slot.setdefault(r["slot"], []).append(r["intensity"])
    med = {s: statistics.median(v) for s, v in by_slot.items()}
    notable = [r for r in rows if r["light_function"] not in (None, "None")
               or r["drama"]["strike"] or r["drama"]["slow_move"]
               or (med.get(r["slot"]) and r["intensity"] > 3.0 * med[r["slot"]])
               or (r["type"] and "SPOT" in r["type"] and r["cone"][1] and r["cone"][1] < 20.0)]
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexStructure", "p01_blinking_spot.json")
    json.dump({"notable": notable, "slot_median_intensity": med, "p01_lights": len(rows)}, open(out, "w"), indent=1)
    unreal.log(f"P01_BLINKING_SPOT_OK|lights={len(rows)}|notable={len(notable)}|mutated=0")


main()
