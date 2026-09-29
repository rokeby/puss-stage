"""Read-only, before enabling "Top Down" (Gary: yes, shadows off): every attachment
whose label ends "Top Down", per passage: enabled or not, where it sits against
the grid, its aim, cone, level and shadow and volumetric settings. Plus the
current shadow-caster count, so before and after can be compared. Mutates nothing.
"""
import collections
import json
import os

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "top_down_survey.json")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_editor_world() and ed.get_game_world() is None, "PIE is running or no editor world"
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passages = [a for a in sub.get_all_level_actors() if isinstance(a, unreal.InfinityStagePassageActor)]
cue_passage = {}
for p in passages:
    for g in show.get_wing_pair_cue_guids_in_passage(p.get_editor_property("passage_guid")):
        cue_passage[unreal.GuidLibrary.conv_guid_to_string(g)] = p

rows, casters_enabled, lights_enabled = [], 0, 0
for cue in show.get_editor_property("cues"):
    if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
        continue
    cg = unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid"))
    passage = cue_passage.get(cg)
    for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
        if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT:
            continue
        L = att.get_editor_property("lighting")
        if att.get_editor_property("enabled"):
            lights_enabled += 1
            casters_enabled += int(bool(L.get_editor_property("cast_shadows")))
        label = str(att.get_editor_property("label"))
        if not label.endswith("Top Down"):
            continue
        z = pitch = None
        if passage:
            wt = passage.get_attachment_world_transform(cue.get_editor_property("cue_guid"), att.get_editor_property("attachment_guid"))
            if isinstance(wt, unreal.Transform):
                local = unreal.MathLibrary.inverse_transform_location(passage.get_actor_transform(), wt.translation)
                z = round(local.z, 1)
                pitch = round(wt.rotation.rotator().pitch, 1)
        rows.append({"label": label, "passage": passage.get_actor_label() if passage else None,
                     "enabled": bool(att.get_editor_property("enabled")), "anchor": str(att.get_editor_property("anchor")),
                     "z": z, "pitch": pitch, "type": str(L.get_editor_property("type")),
                     "intensity": L.get_editor_property("intensity"), "units": str(L.get_editor_property("intensity_units")),
                     "cone": [L.get_editor_property("inner_cone_angle_degrees"), L.get_editor_property("outer_cone_angle_degrees")],
                     "radius": L.get_editor_property("attenuation_radius_cm"),
                     "cast_shadows": bool(L.get_editor_property("cast_shadows")),
                     "cast_volumetric_shadow": bool(L.get_editor_property("cast_volumetric_shadow")),
                     "volumetric_scattering": L.get_editor_property("volumetric_scattering_intensity")})

per = collections.defaultdict(lambda: {"count": 0, "enabled": 0, "shadows": 0, "z": set(), "pitch": set()})
for r in rows:
    k = per[r["passage"]]
    k["count"] += 1
    k["enabled"] += int(r["enabled"])
    k["shadows"] += int(r["cast_shadows"])
    k["z"].add(r["z"])
    k["pitch"].add(r["pitch"])
summary = {p: {**v, "z": sorted(x for x in v["z"] if x is not None)[:6], "pitch": sorted(x for x in v["pitch"] if x is not None)[:6]}
           for p, v in per.items()}
json.dump({"rows": rows, "summary": summary, "lights_enabled": lights_enabled, "casters_enabled": casters_enabled},
          open(OUT, "w"), indent=1, default=str)
unreal.log(f"TOP_DOWN_SURVEY_OK|top_down={len(rows)}|enabled={sum(r['enabled'] for r in rows)}"
           f"|with_shadows={sum(r['cast_shadows'] for r in rows)}|lights_enabled={lights_enabled}"
           f"|casters_enabled={casters_enabled}|mutated=0")
