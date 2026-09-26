"""Read-only survey for the upper-rig design: how each Passage is lit today.

Summarises light attachments per Passage by slot (the label after "P0N Wing NNN "),
with anchor, offset, type, intensity, cone, shadow and light-function settings,
plus the wing panel geometry the rig has to light. P01/P02/P06 read OK to Gary,
P03 is patchy, so the comparison is the point. Mutates nothing.
"""
import collections
import json
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
LABEL = re.compile(r"^P(?P<p>\d{2}) Wing (?P<o>\d{3})$")

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
assert world and world.get_path_name().split(".", 1)[0] == EXPECTED_WORLD, "wrong project"
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
assert show, "Show did not load"


def tf(t):
    r = t.rotation.rotator()
    return {"loc": [round(t.translation.x), round(t.translation.y), round(t.translation.z)],
            "pitch": round(r.pitch, 1), "yaw": round(r.yaw, 1), "roll": round(r.roll, 1)}


def enum_name(v):
    return str(v).split(".")[-1].split(":")[0].strip().rstrip(">")


summary = collections.defaultdict(lambda: {"pairs": 0, "slots": collections.defaultdict(list), "panels": []})
for cue in show.get_editor_property("cues"):
    m = LABEL.match(str(cue.get_editor_property("label")))
    if not m:
        continue
    p = "P" + m.group("p")
    pair = cue.get_editor_property("wing_pair")
    summary[p]["pairs"] += 1
    if len(summary[p]["panels"]) < 3:
        panels = {}
        for side in ("left", "right"):
            d = pair.get_editor_property(side)
            mesh = d.get_editor_property("mesh")
            panels[side] = {"mesh": str(mesh.get_path_name()) if mesh else None,
                            "local": tf(d.get_editor_property("local_transform"))}
        panels["gap_to_next_cm"] = float(pair.get_editor_property("gap_to_next_cm"))
        summary[p]["panels"].append(panels)
    prefix = str(cue.get_editor_property("label")) + " "
    for att in pair.get_editor_property("attachments"):
        if enum_name(att.get_editor_property("kind")) != "LIGHT":
            continue
        L = att.get_editor_property("lighting")
        lf = L.get_editor_property("light_function_material")
        slot = str(att.get_editor_property("label"))
        slot = slot[len(prefix):] if slot.startswith(prefix) else slot
        summary[p]["slots"][slot].append({
            "ordinal": int(m.group("o")),
            "enabled": bool(att.get_editor_property("enabled")),
            "anchor": enum_name(att.get_editor_property("anchor")),
            "offset": tf(att.get_editor_property("relative_transform")),
            "type": enum_name(L.get_editor_property("type")),
            "intensity": round(float(L.get_editor_property("intensity")), 1),
            "units": enum_name(L.get_editor_property("intensity_units")),
            "radius": round(float(L.get_editor_property("attenuation_radius_cm"))),
            "cone": [round(float(L.get_editor_property("inner_cone_angle_degrees")), 1),
                     round(float(L.get_editor_property("outer_cone_angle_degrees")), 1)],
            "shadows": bool(L.get_editor_property("cast_shadows")),
            "vol_scatter": round(float(L.get_editor_property("volumetric_scattering_intensity")), 2),
            "light_function": lf.get_path_name() if lf else None,
            "temperature": round(float(L.get_editor_property("temperature_kelvin"))) if L.get_editor_property("use_temperature") else None,
        })

report = {}
for p, data in sorted(summary.items()):
    slots = {}
    for slot, rows in sorted(data["slots"].items()):
        first = rows[0]
        varies = {k: len({json.dumps(r[k], sort_keys=True) for r in rows}) for k in rows[0] if k != "ordinal"}
        slots[slot] = {"count": len(rows), "first": first,
                       "distinct_values": {k: v for k, v in varies.items() if v > 1}}
    report[p] = {"pairs": data["pairs"], "light_slots": slots, "sample_panels": data["panels"]}

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "rig_survey.json")
json.dump(report, open(out, "w"), indent=1, default=str)
dirty = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
unreal.log(f"RIG_SURVEY_OK|passages={len(report)}|" + "|".join(
    f"{p}={sum(s['count'] for s in r['light_slots'].values())}" for p, r in report.items()) + f"|dirty={dirty}|mutated=0")
