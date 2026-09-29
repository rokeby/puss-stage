"""Read-only: plan baseline lighting for P04, P05 and P06 from P01's hand-tuned rig
(Gary, 29 Sep: "lighting on all the wing series"; P04 "light them like P01", P05
"gentle Baroque cloud painting, Raphael", P06 "P01/P02 treatment with a slight
variation"). Writes p456_baseline_plan.json for p456_baseline_apply.py. Mutates
nothing.

Method: every target pair already carries the nine rig slots. Each is REWRITTEN
IN PLACE (its GUID kept) with its P01 counterpart's values, carried to the
target's geometry:
 - the lamp position is scaled by the passage's bay, lateral and height ratios;
 - the aim: where the P01 spot's axis lands (floor, or the far wing line) is
   scaled the same way, and the lamp re-aimed at it;
 - the intensity is scaled by throw squared, so the lit surface gets P01's
   illuminance, then a per-passage look factor and a +-10% seeded per-pair
   variation.
Shadows: P04 and P06 keep them only on the two keys (Entry Top, Entry Fwd +Y);
P05 is all shadowless.
"""
import json
import math
import os
import random
import re
import statistics

import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "p456_baseline_plan.json")
SLOTS = ("Cross +Y", "Cross -Y", "Entry Fwd +Y", "Entry Fwd -Y", "Entry High +Y", "Entry High -Y",
         "Entry Top", "Low +Y", "Low -Y")
KEYS = ("Entry Fwd +Y", "Entry Fwd -Y", "Entry High +Y", "Entry High -Y", "Entry Top")
FILLS = ("Cross +Y", "Cross -Y", "Low +Y", "Low -Y")
SHADOW_KEYS = ("Entry Top", "Entry Fwd +Y")
P01_HALF = 750.0
P01_CARD = 1000.0
LOOK = {
    "P04": {"key": 1.0, "fill": 1.0, "cone_add": 0.0, "soft_inner": None, "key_k": None, "fill_k": None,
            "shadows": SHADOW_KEYS, "half": 600.0, "card": 1000.0},
    "P05": {"key": 0.7, "fill": 1.3, "cone_add": 10.0, "soft_inner": 0.3, "key_k": 3800.0, "fill_k": 7000.0,
            "shadows": (), "half": 250.0, "card": 600.0},
    "P06": {"key": 1.0, "fill": 1.0, "cone_add": 0.0, "soft_inner": None, "key_k": 4300.0, "fill_k": 6500.0,
            "shadows": SHADOW_KEYS, "half": 750.0, "card": 1000.0},
}
LABEL = re.compile(r"^(P\d\d) Wing (\d{3})$")

ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert ed.get_editor_world() and ed.get_game_world() is None, "PIE is running or no editor world"
show = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passages = {p.get_actor_label()[8:10]: p for p in sub.get_all_level_actors() if isinstance(p, unreal.InfinityStagePassageActor)}
gs = unreal.GuidLibrary.conv_guid_to_string


def pairs_of(pn):
    """Wing-pair cues of passage Pnn in route order, with their pair roots."""
    p = passages[pn]
    guids = {gs(g) for g in show.get_wing_pair_cue_guids_in_passage(p.get_editor_property("passage_guid"))}
    out = []
    for cue in show.get_editor_property("cues"):
        if gs(cue.get_editor_property("cue_guid")) not in guids:
            continue
        atts = cue.get_editor_property("wing_pair").get_editor_property("attachments")
        st = next((a for a in atts if "STATION" in str(a.get_editor_property("anchor"))), None)
        if not st:
            continue
        root = p.get_attachment_anchor_world_transform(cue.get_editor_property("cue_guid"), st.get_editor_property("attachment_guid"))
        route_x = unreal.MathLibrary.inverse_transform_location(p.get_actor_transform(), root.translation).x
        out.append({"cue": cue, "label": str(cue.get_editor_property("label")), "route_x": route_x})
    return sorted(out, key=lambda r: r["route_x"])


def spacing(pairs):
    xs = [r["route_x"] for r in pairs]
    return statistics.median(b - a for a, b in zip(xs, xs[1:]))


def slot_map(cue, label):
    found = {}
    for i, att in enumerate(cue.get_editor_property("wing_pair").get_editor_property("attachments")):
        name = str(att.get_editor_property("label"))
        if name.startswith(label + " ") and name[len(label) + 1:] in SLOTS:
            found.setdefault(name[len(label) + 1:], []).append((i, att))
    return found


def panel_laterals(pn, cue):
    p = passages[pn]
    g = gs(cue.get_editor_property("cue_guid"))
    lat = {}
    for ref in p.get_editor_property("materialized_panels"):
        if gs(ref.get_editor_property("cue_guid")) == g:
            side = str(ref.get_editor_property("side")).split(".")[-1].split(":")[0]
            t = unreal.MathLibrary.inverse_transform_location(p.get_actor_transform(), ref.get_editor_property("base_world_transform").translation)
            lat[side] = round(t.y)
    return lat


# The template: a symmetric +-750 P01 pair nearest the passage middle.
p01 = pairs_of("01")
mid = (p01[0]["route_x"] + p01[-1]["route_x"]) / 2
candidates = [r for r in p01 if panel_laterals("01", r["cue"]) in ({"LEFT": -750, "RIGHT": 750, "TOP": 0}, {"LEFT": -750, "RIGHT": 750})]
assert candidates, "no symmetric +-750 P01 pair"
template = min(candidates, key=lambda r: abs(r["route_x"] - mid))
tslots = slot_map(template["cue"], template["label"])
assert sorted(tslots) == sorted(SLOTS) and all(len(v) == 1 for v in tslots.values()), f"template slots {sorted(tslots)}"
p01_spacing = spacing(p01)


def forward(rot):
    p, y = math.radians(rot.pitch), math.radians(rot.yaw)
    return (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))


def aim_target(loc, d):
    """Where the axis lands: the floor, or the far wing line, whichever is first."""
    ts = []
    if d[2] < -1e-6:
        ts.append(-loc[2] / d[2])
    far = -math.copysign(P01_HALF, loc[1]) if abs(loc[1]) > 1.0 else None
    if far is not None and abs(d[1]) > 1e-6:
        t = (far - loc[1]) / d[1]
        if t > 0:
            ts.append(t)
    t = min(ts) if ts else 2000.0
    t = min(max(t, 100.0), 4000.0)
    return tuple(loc[i] + d[i] * t for i in range(3))


template_rows = {}
for slot, [(idx, att)] in tslots.items():
    t = att.get_editor_property("relative_transform")
    L = att.get_editor_property("lighting")
    loc = (t.translation.x, t.translation.y, t.translation.z)
    d = forward(t.rotation.rotator())
    tgt = aim_target(loc, d)
    template_rows[slot] = {"loc": loc, "target": tgt, "throw": math.dist(loc, tgt),
                           "type": str(L.get_editor_property("type")), "intensity": L.get_editor_property("intensity"),
                           "use_temperature": bool(L.get_editor_property("use_temperature")),
                           "kelvin": L.get_editor_property("temperature_kelvin"),
                           "inner": L.get_editor_property("inner_cone_angle_degrees"),
                           "outer": L.get_editor_property("outer_cone_angle_degrees"),
                           "radius": L.get_editor_property("attenuation_radius_cm"),
                           "vol": L.get_editor_property("volumetric_scattering_intensity")}

plan, problems = [], []
for pn, look in (("04", LOOK["P04"]), ("05", LOOK["P05"]), ("06", LOOK["P06"])):
    pairs = pairs_of(pn)
    sx = spacing(pairs) / p01_spacing
    sy = look["half"] / P01_HALF
    sz = look["card"] / P01_CARD
    for r in pairs:
        smap = slot_map(r["cue"], r["label"])
        if sorted(smap) != sorted(SLOTS) or any(len(v) != 1 for v in smap.values()):
            problems.append(f"{r['label']}: slots {sorted(smap)}")
            continue
        rng = random.Random(f"P456-baseline-{r['label']}")
        for slot in SLOTS:
            tr = template_rows[slot]
            loc = (tr["loc"][0] * sx, tr["loc"][1] * sy, tr["loc"][2] * sz)
            tgt = (tr["target"][0] * sx, tr["target"][1] * sy, tr["target"][2] * sz)
            d = [tgt[i] - loc[i] for i in range(3)]
            throw = math.sqrt(sum(v * v for v in d))
            pitch = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
            yaw = math.degrees(math.atan2(d[1], d[0]))
            kind = "key" if slot in KEYS else "fill"
            factor = look[kind] * (throw / tr["throw"]) ** 2 * rng.uniform(0.9, 1.1)
            outer = min(80.0, tr["outer"] + look["cone_add"])
            inner = outer * look["soft_inner"] if look["soft_inner"] else min(tr["inner"], outer)
            kelvin = look["key_k"] if kind == "key" else look["fill_k"]
            row = {"slot": slot, "loc": [round(v, 1) for v in loc], "pitch": round(pitch, 3), "yaw": round(yaw, 3),
                   "intensity_cd": round(tr["intensity"] * factor, 3), "inner": round(inner, 2), "outer": round(outer, 2),
                   "radius_cm": round(tr["radius"] * min(1.0, max(0.6, throw / tr["throw"])), 1),   # never more reach than P01's
                   "cast_shadows": slot in look["shadows"], "volumetric_scattering": tr["vol"],
                   "use_temperature": kelvin is not None or tr["use_temperature"],
                   "kelvin": kelvin if kelvin is not None else tr["kelvin"]}
            plan.append({"passage": f"P{pn}", "cue": r["label"], "guid": gs(smap[slot][0][1].get_editor_property("attachment_guid")),
                         "index": smap[slot][0][0], **row})

report = {"template": template["label"], "p01_spacing": round(p01_spacing, 1),
          "scales": {f"P{pn}": {"sx": round(spacing(pairs_of(pn)) / p01_spacing, 3), "sy": LOOK[f"P{pn}"]["half"] / P01_HALF,
                                "sz": LOOK[f"P{pn}"]["card"] / P01_CARD} for pn in ("04", "05", "06")},
          "template_rows": {k: {**v, "loc": [round(x, 1) for x in v["loc"]], "target": [round(x, 1) for x in v["target"]]}
                            for k, v in template_rows.items()},
          "rows": plan, "problems": problems,
          "casters_planned": sum(r["cast_shadows"] for r in plan), "lamps": len(plan)}
json.dump(report, open(OUT, "w"), indent=1)
unreal.log(f"P456_BASELINE_PLAN_OK|template={template['label']}|lamps={len(plan)}|casters={report['casters_planned']}"
           f"|problems={len(problems)}|mutated=0")
