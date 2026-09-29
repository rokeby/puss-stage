"""Read-only, before baseline lighting for P04, P05 and P06: for P01 (the reference
rig) and P02 to P06, every light slot per wing pair (the label after "Pxx Wing
nnn "), with how many pairs carry it, how many are lit, its intensity range and
units, colour, cone, reach, shadows, volumetrics, and its position relative to
the pair root (min, median, max). Plus each passage's wing laterals and card
heights, from the materialized panels. Mutates nothing.
"""
import collections
import json
import os
import re
import statistics

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "passage_lighting_survey.json")
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_editor_world() and ed.get_game_world() is None, "PIE is running or no editor world"
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
LABEL = re.compile(r"^(P\d\d) Wing (\d{3}) (.+)$")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passages = {p.get_actor_label()[:10]: p for p in sub.get_all_level_actors() if isinstance(p, unreal.InfinityStagePassageActor)}


def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return [round(min(vals), 2), round(statistics.median(vals), 2), round(max(vals), 2)]


slots = collections.defaultdict(lambda: collections.defaultdict(list))
pairs = collections.Counter()
for cue in show.get_editor_property("cues"):
    if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
        continue
    m = re.match(r"^(P\d\d) Wing", str(cue.get_editor_property("label")))
    if not m:
        continue
    pk = m.group(1)
    pairs[pk] += 1
    for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
        if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT:
            continue
        lm = LABEL.match(str(att.get_editor_property("label")))
        slot = lm.group(3) if lm else str(att.get_editor_property("label"))
        L = att.get_editor_property("lighting")
        t = att.get_editor_property("relative_transform")
        r = t.rotation.rotator()
        col = L.get_editor_property("color")
        slots[pk][slot].append({
            "enabled": bool(att.get_editor_property("enabled")), "anchor": str(att.get_editor_property("anchor")).split(".")[-1].split(":")[0],
            "type": str(L.get_editor_property("type")).split(".")[-1].split(":")[0],
            "units": str(L.get_editor_property("intensity_units")).split(".")[-1].split(":")[0],
            "intensity": L.get_editor_property("intensity"),
            "kelvin": L.get_editor_property("temperature_kelvin") if L.get_editor_property("use_temperature") else None,
            "color": [round(col.r, 2), round(col.g, 2), round(col.b, 2)] if hasattr(col, "r") else None,
            "inner": L.get_editor_property("inner_cone_angle_degrees"), "outer": L.get_editor_property("outer_cone_angle_degrees"),
            "radius": L.get_editor_property("attenuation_radius_cm"), "shadows": bool(L.get_editor_property("cast_shadows")),
            "vol": L.get_editor_property("volumetric_scattering_intensity"),
            "x": t.translation.x, "y": t.translation.y, "z": t.translation.z,
            "pitch": r.pitch, "yaw": r.yaw})

report = {"pairs": dict(pairs), "passages": {}}
for pk in sorted(slots):
    rows = {}
    for slot, items in sorted(slots[pk].items()):
        lit = [i for i in items if i["enabled"]]
        rows[slot] = {"pairs": len(items), "lit": len(lit), "shadows_lit": sum(i["shadows"] for i in lit),
                      "type": collections.Counter(i["type"] for i in items).most_common(1)[0][0],
                      "units": collections.Counter(i["units"] for i in items).most_common(1)[0][0],
                      "anchor": collections.Counter(i["anchor"] for i in items).most_common(1)[0][0],
                      "intensity": stats([i["intensity"] for i in lit] or [i["intensity"] for i in items]),
                      "kelvin": stats([i["kelvin"] for i in items]),
                      "color": collections.Counter(tuple(i["color"]) for i in items if i["color"]).most_common(1)[0][0] if items else None,
                      "cone": [stats([i["inner"] for i in items]), stats([i["outer"] for i in items])],
                      "radius": stats([i["radius"] for i in items]), "vol": stats([i["vol"] for i in items]),
                      "rel_x": stats([i["x"] for i in items]), "rel_y": stats([i["y"] for i in items]),
                      "rel_z": stats([i["z"] for i in items]), "pitch": stats([i["pitch"] for i in items]),
                      "yaw": stats([i["yaw"] for i in items])}
    report["passages"][pk] = rows

geometry = {}
for label, p in passages.items():
    lat, tops = [], []
    for ref in p.get_editor_property("materialized_panels"):
        side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0]
        t = ref.get_editor_property("base_world_transform").translation
        local = unreal.MathLibrary.inverse_transform_location(p.get_actor_transform(), t)
        if side in ("LEFT", "RIGHT"):
            lat.append(round(local.y))
    geometry[label] = {"wing_laterals": collections.Counter(lat).most_common(8)}
report["geometry"] = geometry
json.dump(report, open(OUT, "w"), indent=1, default=str)
unreal.log(f"PASSAGE_LIGHTING_SURVEY_OK|passages={len(report['passages'])}|mutated=0")
