"""Round 2 (Gary note 59, 6 Oct ~00:30) score data, built from lighting_scores.json.bak-20261006-preRound2.

Deterministic and re-runnable: reads the preRound2 backup, writes lighting_scores.json. No Unreal. Every value
that is a creative choice says so in the data ("note"/"intent"); every timing value derived from the P06 music
analysis is recomputed here from the analysis JSON (P06_BEAT_MODEL below), so a reader can check it.
Run: python lighting_scores_round2_build.py
"""
from __future__ import annotations

import copy
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "lighting_scores.json.bak-20261006-preRound2")
DST = os.path.join(HERE, "lighting_scores.json")
ANALYSIS = os.path.join(HERE, "..", "InfinityStage", "MusicAnalysis", "P06_WalkingMusic_6_into_void.analysis.json")
LF = "/Game/InfinityStage/Lighting/MI_LF_Flicker_"
EMISSIVE = "/Game/InfinityStage/RigAtmos/Underpass/Materials/M_UP_TubeEmissive"
SPHERE = "/Engine/BasicShapes/Sphere"

RED, GREEN, CREAM, PINK = [1.0, 0.12, 0.1], [0.2, 1.0, 0.3], [1.0, 0.95, 0.7], [1.0, 0.4, 0.7]
FAIRY = [RED, GREEN, CREAM, PINK]


def flick(name):
    return {"mode": name.upper(), "material": LF + name} if name else {"mode": "STEADY", "material": None}


def bulb(slot, location, lumens, rgb, kelvin, att, flicker=None, scale=(0.1, 0.1, 0.13), style="bare bulb",
         dim_tint=None, body_mode=None):
    row = {"slot": slot, "role": "PRACTICAL", "type": "POINT",
           "transform": {"location_cm": list(location), "rotation_rpy_deg": [0.0, 0.0, 0.0]},
           "intensity_units": "LUMENS", "intensity": float(lumens), "color_rgb_linear": list(rgb),
           "temperature_kelvin": float(kelvin), "attenuation_cm": float(att), "inner_cone_deg": None,
           "outer_cone_deg": None, "flicker": flick(flicker), "cast_shadows": False, "volumetric_scattering": 0.04,
           "visible_mesh": {"style": style, "mesh": SPHERE, "emissive": True, "rotation_rpy_deg": [0.0, 0.0, 0.0],
                            "scale": list(scale), "material": {"parent": EMISSIVE,
                                                               "mode": "MATCH_LIGHT" if lumens > 0 else "DIM"}}}
    if dim_tint:
        row["dim_tint"] = dim_tint
    if body_mode:
        row["body_mode"] = body_mode
    return row


def spot(slot, role, location, cd, rgb, kelvin, att, inner, outer, vol=0.08, shadows=False, flicker=None, **extra):
    row = {"slot": slot, "role": role, "type": "SPOT",
           "transform": {"location_cm": list(location), "rotation_rpy_deg": [0.0, 0.0, 0.0]},
           "intensity_units": "CANDELAS", "intensity": float(cd), "color_rgb_linear": list(rgb),
           "temperature_kelvin": float(kelvin), "attenuation_cm": float(att), "inner_cone_deg": float(inner),
           "outer_cone_deg": float(outer), "flicker": flick(flicker), "cast_shadows": shadows,
           "volumetric_scattering": float(vol)}
    row.update(extra)
    return row


def wing_top(cd, rgb, kelvin, side, flicker=None, z_offset=300.0, shadows=True):
    """P02 pattern: a top washing its OWN side's wing face from above (aim_wing_side + offset)."""
    return {"color_rgb_linear": rgb, "temperature_kelvin": kelvin, "intensity": cd, "inner_cone_deg": 9.0,
            "outer_cone_deg": 20.0, "volumetric_scattering": 0.1, "aim_wing_side": side,
            "aim_offset_pair_cm": [0.0, 0.0, z_offset], "flicker": flick(flicker), "cast_shadows": shadows}


def main():
    s = json.load(open(SRC, encoding="utf-8"))
    v = s["variants"]
    P = s["passages"]
    s["score_round"] = "2026-10-06 round 2 (Gary note 59): dim bulbs + caps, P01 fairy tops/ground beams, P04 wings + bulbs, P05 sky approach, P06 sleepy blue / embers / beats. Built by lighting_scores_round2_build.py from lighting_scores.json.bak-20261006-preRound2"

    # ------------------------------------------------------------------ global: bulbs
    s["dim_bulbs"] = {
        "enabled": True,
        "decided_by": "Gary 6 Oct ~00:30 (note 59): 'make all the dead bulbs minimally glowing even if not functionally producing much light, i.e. a bulb can still glow orange, white, pink, and cast a small reflection'",
        "lumens": 18.0, "attenuation_cm": 150.0, "volumetric_scattering": 0.02, "body_parent": EMISSIVE,
        "tints": {"ORANGE": {"rgb": [1.0, 0.5, 0.18], "kelvin": 2200.0},
                  "WHITE": {"rgb": [1.0, 0.94, 0.86], "kelvin": 3300.0},
                  "PINK": {"rgb": [1.0, 0.6, 0.74], "kelvin": 3400.0}},
        "passage_tints": {"P01": ["PINK"], "P02": ["PINK", "ORANGE", "WHITE"], "P03": ["WHITE", "ORANGE"],
                          "P04": ["ORANGE"], "P05": ["WHITE", "PINK"], "P06": ["ORANGE", "PINK"]},
        "note": "PINK in P01 is Gary's 'pale pink' for PRACTICAL_BULB_DEAD; P04 stays ORANGE (warm floor-bulb rule, 5 Oct); creative choice elsewhere"}
    s["bulb_caps"] = {"enabled": True, "parent": EMISSIVE, "height_fraction": 0.3, "width_fraction": 0.42,
                      "overlap_cm": 1.0,
                      "why": "no real light-bulb mesh exists in Content (searched 6 Oct: only StarterContent SM_Lamp_Ceiling/SM_Lamp_Wall fixtures); a Sphere glass + a dull Cylinder screw cap reads as a bulb. Derived create-only like the bodies"}
    s["bulb_body_behaviours"] = {
        "fractions": {"SLIGHT": 0.25, "FAIL": 0.10},
        "decided_by": "Gary 6 Oct (via conductor): 'a flickering and dying bulb, not all bulbs! some should flicker only slightly and others be stable'",
        "cpp_field": None,
        "status": "DATA ONLY: the C++ per-attachment body option (STABLE/SLIGHT/FAIL + seed, glass follows evaluated intensity) is being built by the C++ agent; the field name is filled in from Scripts/patches/2026-10-06_*.patch when it lands. Until then nothing is written"}

    # dead-mode bodies in the P04 data become DIM (the policy would convert them; the look must validate first)
    for name in ("P04_GROUND_BULB_ONE_DEAD", "P04_CEILING_STRIKE"):
        body = v[name]["instrument_overrides"]["PRACTICAL_R"]["visible_mesh"]
        body["emissive"] = True
        body["material"]["mode"] = "DIM"
        body["style"] = "dim bare bulb on the floor (6 Oct: dead bulbs glow)"

    # ------------------------------------------------------------------ new light functions
    s["flicker_instances"] = {
        LF + "Pulse1Hz_A": {"parent": "/Game/InfinityStage/Lighting/M_LF_StageFlicker",
                            "params": {"Speed": 1.0, "SpeedRatio": 1.47, "Depth": 0.35, "Phase": 0.0, "Hardness": 0.1, "OnBias": 0.5},
                            "why": "P01 fairy tops: gentle irregular ~1 Hz pulse (dips to 65%)"},
        LF + "Pulse1Hz_B": {"parent": "/Game/InfinityStage/Lighting/M_LF_StageFlicker",
                            "params": {"Speed": 1.0, "SpeedRatio": 1.47, "Depth": 0.35, "Phase": 0.37, "Hardness": 0.1, "OnBias": 0.5},
                            "why": "the same pulse, other phase, so TOP_L and TOP_R never pulse together"},
        LF + "Burst2Hz_A": {"parent": "/Game/InfinityStage/Lighting/M_LF_StageFlicker",
                            "params": {"Speed": 2.0, "SpeedRatio": 0.125, "Depth": 1.0, "Phase": 0.0, "Hardness": 1.0, "OnBias": 0.92},
                            "why": "2 Hz x ~0.6 s burst (2 flashes) every 4 s, starting ~0.6 s into each 4 s cycle (model: lf_level)"},
        LF + "Burst2Hz_B": {"parent": "/Game/InfinityStage/Lighting/M_LF_StageFlicker",
                            "params": {"Speed": 2.0, "SpeedRatio": 0.125, "Depth": 1.0, "Phase": 0.5, "Hardness": 1.0, "OnBias": 0.92},
                            "why": "as A, bursts start ~1.3 s into the cycle"},
        LF + "Burst2Hz_C": {"parent": "/Game/InfinityStage/Lighting/M_LF_StageFlicker",
                            "params": {"Speed": 2.0, "SpeedRatio": 0.125, "Depth": 1.0, "Phase": 0.95, "Hardness": 1.0, "OnBias": 0.92},
                            "why": "as A, bursts start ~2.1 s into the cycle"},
        LF + "HarpFlutter": {"parent": "/Game/InfinityStage/Lighting/M_LF_StageFlicker",
                             "params": {"Speed": 6.0, "SpeedRatio": 1.31, "Depth": 0.15, "Phase": 0.0, "Hardness": 0.0, "OnBias": 0.5},
                             "why": "P06 harp lilting parts: shallow fast flutter (85-100%)"},
    }

    # ------------------------------------------------------------------ P01
    v["P01_WARM_EARLY"] = {"base": "THEATRICAL", "intent": "P01 bays 3-5 (note 59): the orange fog-flood low sides dominate; tops not yet on (they ping on after bay 5)",
                           "instrument_overrides": copy.deepcopy(v["P01_WARM_THEATRICAL"]["instrument_overrides"])}
    v["P01_WARM_EARLY"]["instrument_overrides"]["TOP_L"]["intensity"] = 0.0
    v["P01_WARM_EARLY"]["instrument_overrides"]["TOP_R"]["intensity"] = 0.0
    v["P01_WARM_EARLY"]["instrument_overrides"]["PRACTICAL_BULB_DEAD"]["dim_tint"] = "PINK"
    v["P01_WARM_EARLY"]["instrument_overrides"]["PRACTICAL_CLAMP"].update({"color_rgb_linear": [1.0, 0.72, 0.8], "temperature_kelvin": 4000.0})

    def fairy(name, low_scale, top_cd, intent):
        o = copy.deepcopy(v["P01_WARM_THEATRICAL"]["instrument_overrides"])
        o["TOP_L"] = {"color_rgb_linear": RED, "temperature_kelvin": 6500.0, "intensity": top_cd,
                      "inner_cone_deg": 10.0, "outer_cone_deg": 24.0, "volumetric_scattering": 0.2,
                      "flicker": flick("Pulse1Hz_A")}
        o["TOP_R"] = {"color_rgb_linear": GREEN, "temperature_kelvin": 6500.0, "intensity": top_cd,
                      "inner_cone_deg": 10.0, "outer_cone_deg": 24.0, "volumetric_scattering": 0.2,
                      "flicker": flick("Pulse1Hz_B")}
        o["LOW_SIDE_L_KEY"]["intensity"] = round(640.0 * low_scale, 2)
        o["LOW_SIDE_R_FILL"]["intensity"] = round(160.0 * low_scale, 2)
        o["PRACTICAL_BULB_DEAD"]["dim_tint"] = "PINK"
        o["PRACTICAL_CLAMP"].update({"color_rgb_linear": [1.0, 0.72, 0.8], "temperature_kelvin": 4000.0})
        v[name] = {"base": "THEATRICAL", "intent": intent, "instrument_overrides": o}

    fairy("P01_FAIRY", 1.0, 150.0, "P01 bays 6-12 (note 59): fairy-tale tops ping on (red / green / whitish-yellow / pink per bay, gentle irregular ~1 Hz pulse, own-side auto-aim); the orange low sides still dominate; pale pink clamp + dim pink bulb")
    fairy("P01_FAIRY_TOPS", 0.35, 230.0, "P01 after bay 12 (note 59): the low sides drop to 35% so the coloured tops dominate")
    mo = copy.deepcopy(v["P01_CANDLE_MOODY"]["instrument_overrides"])
    mo.update({"TOP_L": {"color_rgb_linear": PINK, "temperature_kelvin": 6500.0, "intensity": 200.0, "inner_cone_deg": 10.0,
                         "outer_cone_deg": 24.0, "volumetric_scattering": 0.2, "flicker": flick("Pulse1Hz_A")},
               "TOP_R": {"color_rgb_linear": CREAM, "temperature_kelvin": 6500.0, "intensity": 200.0, "inner_cone_deg": 10.0,
                         "outer_cone_deg": 24.0, "volumetric_scattering": 0.2, "flicker": flick("Pulse1Hz_B")}})
    mo["LOW_SIDE_L_KEY"]["intensity"] = 250.0
    mo["PRACTICAL_R"] = {"dim_tint": "PINK"}
    v["P01_CANDLE_FAIRY"] = {"base": "MOODY", "intent": "P01's candle bay after bay 12: blade dimmed (700 -> 250 cd), coloured pulsing tops dominate, dead bulb glows pale pink",
                             "instrument_overrides": mo}
    v["P01_CANDLE_FAIRY_BEAM"] = copy.deepcopy(v["P01_CANDLE_FAIRY"])
    v["P01_CANDLE_FAIRY_BEAM"]["intent"] = "P01_CANDLE_FAIRY plus ONE ground beam (MOODY has no BEAM slot): note 59 'around bay 20: ground BEAM_Rs of different colours'"
    v["P01_CANDLE_FAIRY_BEAM"]["add_instruments"] = [spot(
        "BEAM_R", "BEAM", [-150.0, -1250.0, 140.0], 5000.0, [1.0, 0.0, 0.6], 6500.0, 2600.0, 2.0, 7.0, vol=6.0,
        rotation=None)]
    beam = v["P01_CANDLE_FAIRY_BEAM"]["add_instruments"][0]
    beam.pop("rotation")
    beam["transform"]["rotation_rpy_deg"] = [0.0, -5.0, 76.0]  # THEATRICAL BEAM_R's own aim (lighting_looks.json)

    def tops(i):
        return {"TOP_L": {"color_rgb_linear": FAIRY[i % 4]}, "TOP_R": {"color_rgb_linear": FAIRY[(i + 2) % 4]}}

    seg = P["P01"]["segments"]
    # bays 3-12 keep the strike cascade, levels and mirrors; bays 3-5 early, 6-12 fairy tops with per-bay colours
    for position, row in enumerate(seg[2]["cycle"]):
        bay = 3 + position
        if row["look"] == "P01_WARM_THEATRICAL":
            if bay <= 5:
                row["look"] = "P01_WARM_EARLY"
            else:
                row["look"] = "P01_FAIRY"
                row["overrides"] = tops(bay)
    # bays 13-40: the same 7-bay phrase, tops dominate; 18-23 carry the ground beams (bay 20's original kept)
    phrase = seg[3]["cycle"]
    cyc = []
    for position in range(28):
        bay = 13 + position
        src = copy.deepcopy(phrase[position % 7])
        if src["look"] == "P01_WARM_THEATRICAL":
            src["look"] = "P01_FAIRY_TOPS"
            src["overrides"] = tops(bay)
        elif src["look"] == "P01_CANDLE_MOODY":
            src["look"] = "P01_CANDLE_FAIRY"
            src["overrides"] = tops(bay)
        cyc.append(src)
    # Ground beams (note 59): keep bay 20's BEAM_R exactly (the one that 'flickers nicely' - see report, UNCLEAR
    # which beam Gary meant; bay 20 is the only BEAM near 'bay 20'), add 3 pulsing 2 Hz x 0.5 s at staggered moments.
    beams = {
        18: ("P01_FAIRY_TOPS", {"BEAM_R": {"color_rgb_linear": [0.2, 1.0, 0.35], "temperature_kelvin": 6500.0,
                                           "flicker": flick("Burst2Hz_A"),
                                           "keying": {"strike_distance_cm": 5400.0, "ramp_distance_cm": 60.0}}},
             "green ground beam, bursts A; strikes ~9 bays out: seen in the distance"),
        21: ("P01_CANDLE_FAIRY_BEAM", {"BEAM_R": {"flicker": flick("Burst2Hz_B"),
                                                  "keying": {"strike_distance_cm": 1500.0, "ramp_distance_cm": 40.0}}},
             "magenta ground beam, bursts B; strikes only ~2.5 bays ahead of Puss"),
        22: ("P01_FAIRY_TOPS", {"BEAM_R": {"color_rgb_linear": [0.2, 0.55, 1.0], "temperature_kelvin": 6500.0,
                                           "flicker": flick("Burst2Hz_C"),
                                           "keying": {"strike_distance_cm": 4200.0, "ramp_distance_cm": 60.0}}},
             "blue ground beam (mirrored side), bursts C; strikes ~7 bays out"),
    }
    for bay, (look, beam_over, note) in beams.items():
        row = cyc[bay - 13]
        assert row["look"] in ("P01_FAIRY_TOPS", "P01_CANDLE_FAIRY"), (bay, row)
        row["look"] = look
        row.setdefault("overrides", {}).update(beam_over)
        row["note"] = note
    assert cyc[20 - 13]["look"] == "P01_FAIRY_TOPS"
    cyc[20 - 13]["note"] = "bay 20: the original orange BEAM_R, unchanged (steady, strike 650 cm)"
    seg[3] = {"bays": [13, 40], "cycle": cyc,
              "note": "6 Oct round 2: the 5 Oct 7-bay phrase written out per bay (colours vary per bay; bays 18/21/22 carry the new pulsing ground beams)"}
    seg[4]["cycle"][0]["look"] = "P01_FAIRY_TOPS"
    seg[4]["cycle"][0]["overrides"] = tops(41)
    for position, row in enumerate(seg[5]["cycle"]):
        if row["look"] == "P01_WARM_THEATRICAL":
            row["look"] = "P01_FAIRY_TOPS"
            row["overrides"] = tops(42 + position)
    P["P01"]["score_revision"] = "2026-10-06 round 2: fairy tops ping on after bay 5 (1 Hz pulse), low sides darken after bay 12, pale pink clamp/bulbs, ground beams at 18/20/21/22 (20 = the original)"

    # ------------------------------------------------------------------ P04
    hang = lambda slot, y, lm, flicker="Slow", body=None: bulb(  # noqa: E731
        slot, [-40.0, y, 215.0], lm, [1.0, 0.6, 0.3], 2400.0, 260.0, flicker, scale=(0.11, 0.11, 0.14),
        style="hanging bare bulb (6 Oct)", body_mode=body)
    floor = lambda slot, y, lm, flicker=None, body=None: bulb(  # noqa: E731
        slot, [30.0, y, 15.0], lm, [1.0, 0.62, 0.3], 2300.0, 300.0, flicker, style="bare bulb on the floor (5 Oct)",
        body_mode=body)
    v["P04_MOODY_WINGS"] = {
        "base": "MOODY",
        "intent": "P04 bays 8-9 (note 59 'more light on the wings, to feel their texture'): tops wash their OWN wing from above (cold moon, P02 pattern, shadows on); the left key becomes an own-side uplight grazing the wing; no fill across; practicals dim: one hanging, one on the floor",
        "drop_slots": ["LOW_SIDE_R_FILL"],
        "instrument_overrides": {
            "TOP_L": wing_top(150.0, [0.55, 0.68, 1.0], 7600.0, "LEFT"),
            "TOP_R": wing_top(130.0, [0.55, 0.68, 1.0], 7600.0, "RIGHT"),
            "LOW_SIDE_L_KEY": {"location_cm": [60.0, -800.0, 25.0], "rotation_rpy_deg": [0.0, 65.0, -90.0],
                               "intensity": 160.0, "inner_cone_deg": 8.0, "outer_cone_deg": 22.0,
                               "volumetric_scattering": 0.08, "attenuation_cm": 1200.0, "aim_wing_side": "LEFT",
                               "aim_offset_pair_cm": [0.0, 0.0, 650.0], "flicker": flick(None)},
            "PRACTICAL_L": {"location_cm": [-40.0, -840.0, 215.0], "intensity": 260.0, "attenuation_cm": 320.0,
                            "temperature_kelvin": 2400.0, "volumetric_scattering": 0.05}},
        "add_instruments": [floor("PRACTICAL_FLOOR", 900.0, 140.0, "Hum")]}
    v["P04_INDUSTRIAL_WINGS"] = {
        "base": "INDUSTRIAL",
        "intent": "P04 bay 12: the sodium tops wash their own wings (volumetric 0.45 -> 0.1, shadows on) instead of the fog; the crossing low sides and the FAULT beam go; one sodium uplight; tube + dim cage stay; a floor bulb",
        "drop_slots": ["LOW_SIDE_R", "BEAM_L"],
        "instrument_overrides": {
            "TOP_L": wing_top(120.0, [1.0, 0.9, 0.66], 2050.0, "LEFT", "Hum"),
            "TOP_R": wing_top(100.0, [1.0, 0.9, 0.66], 2000.0, "RIGHT", "Hum"),
            "LOW_SIDE_L": {"location_cm": [60.0, -800.0, 25.0], "rotation_rpy_deg": [0.0, 65.0, -90.0],
                           "intensity": 150.0, "inner_cone_deg": 8.0, "outer_cone_deg": 22.0,
                           "volumetric_scattering": 0.08, "attenuation_cm": 1200.0, "aim_wing_side": "LEFT",
                           "aim_offset_pair_cm": [0.0, 0.0, 650.0]}},
        "add_instruments": [floor("PRACTICAL_FLOOR", -900.0, 120.0, "Buzz")]}
    v["P04_DARK_BULBS"] = {
        "base": "MOODY",
        "intent": "P04 gap bays 7/10/13 (note 59: 'more active practicals ... floor + hanging, dim, through the passage'): dark, one hanging and two floor bulbs, dim",
        "drop_slots": ["TOP_L", "TOP_R", "LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL"],
        "instrument_overrides": {
            "PRACTICAL_L": {"location_cm": [-40.0, -860.0, 215.0], "intensity": 90.0, "attenuation_cm": 260.0,
                            "temperature_kelvin": 2400.0, "volumetric_scattering": 0.04,
                            "visible_mesh": {"style": "hanging bare bulb (6 Oct)", "mesh": SPHERE, "emissive": True,
                                             "rotation_rpy_deg": [0.0, 0.0, 0.0], "scale": [0.11, 0.11, 0.14],
                                             "material": {"parent": EMISSIVE, "mode": "MATCH_LIGHT"}}},
            "PRACTICAL_R": {"location_cm": [40.0, 880.0, 15.0], "dim_tint": "ORANGE",
                            "visible_mesh": {"style": "dim bare bulb on the floor (6 Oct)", "mesh": SPHERE, "emissive": True,
                                             "rotation_rpy_deg": [0.0, 0.0, 0.0], "scale": [0.1, 0.1, 0.13],
                                             "material": {"parent": EMISSIVE, "mode": "DIM"}}}},
        "add_instruments": [floor("PRACTICAL_FLOOR", -920.0, 110.0, "Hum")]}
    v["P04_COLD_BREAK_BULBS"] = copy.deepcopy(v["P04_COLD_BREAK"])
    v["P04_COLD_BREAK_BULBS"]["intent"] += " | 6 Oct: plus one dim floor bulb by the right wing (the breakage beam is unchanged: no-cross exempt bay)"
    v["P04_COLD_BREAK_BULBS"]["add_instruments"] = [floor("PRACTICAL_FLOOR", 940.0, 110.0)]
    for name in ("P04_GROUND_BULBS", "P04_GROUND_BULB_ONE_DEAD"):
        v[name]["add_instruments"] = [hang("PRACTICAL_HANG", 860.0, 60.0)]
        v[name]["intent"] += " | 6 Oct (note 59): plus one dim hanging bulb by the right wing"
    seg = P["P04"]["segments"]
    seg[1]["cycle"] = [
        {"look": "P04_DARK_BULBS", "level": 1.0, "note": "was GAP"},
        {"look": "P04_MOODY_WINGS", "level": 0.8, "note": "was MOODY"},
        {"look": "P04_MOODY_WINGS", "level": 0.8, "mirror": ["LOW_SIDE", "PRACTICAL"], "note": "was MOODY mirrored"},
        {"look": "P04_DARK_BULBS", "level": 1.0, "mirror": ["PRACTICAL"], "note": "was GAP"},
        {"look": "P04_COLD_BREAK_BULBS", "level": 1.0, "note": "the cold breakage beam (unchanged) + a floor bulb"},
        {"look": "P04_INDUSTRIAL_WINGS", "level": 0.6, "note": "was INDUSTRIAL"},
        {"look": "P04_DARK_BULBS", "level": 1.0, "note": "was GAP"},
        {"look": "VOID", "level": 1.0, "note": "second complete dark bay before the last third (its dead bulb now glows dim)"}]
    # bays 15-21 keep Gary's 5 Oct 'fairly dark' brief: only the hanging bulbs are added; bay 17 untouched
    P["P04"]["no_cross_shots"] = {"enabled": True, "bays": [7, 21], "exempt_bays": [11],
                                  "centre_tolerance_cm": 100.0, "nominal_panel_abs_y_cm": 900.0,
                                  "note": "6 Oct round 2: bays 7-21 own-side only (tops/uplights on their own wing); bay 11 exempt = P04_COLD_BREAK's hard back-lit breakage shaft (a 4 Oct look Gary has not asked to change). 1-6 are the prototype (lighting_looks_apply.py)."}
    P["P04"]["score_revision"] = "2026-10-06 round 2: bays 7-14 wing-aimed tops/uplights + floor/hanging bulbs, 15-21 + hanging bulbs, dead bulbs glow; strobe halo is a separate level tool (p04_strobe_halo.py); bay-17 strike untouched"

    # ------------------------------------------------------------------ P05
    sky = [0.45, 0.65, 1.0]
    fills = [spot("FILL_L", "FILL", [0.0, -1250.0, 900.0], 140.0, sky, 9000.0, 1600.0, 30.0, 55.0, vol=0.05,
                  aim_target_pair_cm=[0.0, -2100.0, 450.0]),
             spot("FILL_R", "FILL", [0.0, 1250.0, 900.0], 140.0, sky, 9000.0, 1600.0, 30.0, 55.0, vol=0.05,
                  aim_target_pair_cm=[0.0, 2100.0, 450.0])]
    for f in fills:
        f["note"] = "fence-facing soft fill for the 'blue skies' curtains (not built yet): points OUTWARD at the rig-fence line; the fence |y| (2100 here) is INFERRED - re-aim when the curtains exist"
    ups = [spot("UPLIGHT_L", "UPLIGHT", [40.0, -900.0, 20.0], 90.0, [1.0, 0.95, 0.85], 4500.0, 1000.0, 10.0, 24.0,
                vol=0.05, aim_wing_side="LEFT", aim_offset_pair_cm=[0.0, 0.0, 250.0]),
           spot("UPLIGHT_R", "UPLIGHT", [40.0, 900.0, 20.0], 90.0, [1.0, 0.95, 0.85], 4500.0, 1000.0, 10.0, 24.0,
                vol=0.05, aim_wing_side="RIGHT", aim_offset_pair_cm=[0.0, 0.0, 250.0])]
    for u in ups:
        u["note"] = "small bottom up-spot for Gary's new mountain pieces (low on the wing: offset z +250)"
    movers = [spot("MOVER_L", "MOVER", [0.0, -500.0, 1050.0], 900.0, [0.8, 0.3, 1.0], 6500.0, 2200.0, 3.0, 9.0, vol=0.6,
                   aim_target_pair_cm=[200.0, -300.0, 0.0], requires_cpp="club mover drama (C++ agent, 6 Oct): see report spec"),
              spot("MOVER_R", "MOVER", [0.0, 500.0, 1050.0], 900.0, [0.3, 0.9, 1.0], 6500.0, 2200.0, 3.0, 9.0, vol=0.6,
                   aim_target_pair_cm=[200.0, 300.0, 0.0], requires_cpp="club mover drama (C++ agent, 6 Oct): see report spec")]
    upper = {"TOP_L": wing_top(170.0, [0.92, 0.95, 1.0], 5600.0, "LEFT", z_offset=450.0, shadows=False),
             "TOP_R": wing_top(170.0, [0.8, 0.88, 1.0], 6800.0, "RIGHT", z_offset=450.0, shadows=False)}
    base = copy.deepcopy(v["P05_COOL_THEATRICAL"]["instrument_overrides"])
    sky_o = copy.deepcopy(base)
    sky_o.update(copy.deepcopy(upper))
    v["P05_SKY_APPROACH"] = {"base": "THEATRICAL", "intent": "P05 bays 1-6 (note 59): the cloud look Gary likes (up-lit clouds, back-lit sky) + upper L/R spots on the cloud wings + blue-sky fills coming on in sequence + small mountain up-spots",
                             "instrument_overrides": sky_o, "add_instruments": copy.deepcopy(fills + ups)}
    blink_o = copy.deepcopy(base)
    blink_o.update(copy.deepcopy(upper))
    blink_o["TOP_L"]["flicker"] = flick("Fault")
    blink_o["TOP_R"]["flicker"] = flick("Fault")
    blink_ups = copy.deepcopy(ups)
    for u in blink_ups:
        u["flicker"] = flick("Fault")
    v["P05_SKY_CUT_BLINK"] = {"base": "THEATRICAL", "intent": "P05 bays 7-12 (note 59 'after ~bay 6 the sky lights cut out and the new spots blink, only the current lights on'): sky beam + fills + low sides cut; upper spots and up-spots blink (FAULT) and are snuffed just behind Puss",
                              "drop_slots": ["BEAM_R", "LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL"],
                              "instrument_overrides": {k: blink_o[k] for k in ("TOP_L", "TOP_R", "PRACTICAL_CLAMP", "PRACTICAL_BULB_DEAD")},
                              "add_instruments": blink_ups}
    all_o = copy.deepcopy(sky_o)
    v["P05_ALL_ON"] = {"base": "THEATRICAL", "intent": "P05 bays 13-18 (note 59 '~6 bays later everything comes on'): clouds, sky beam, upper spots, fills, up-spots; the club movers are DATA ONLY until the C++ mover lands (skipped with a warning)",
                       "instrument_overrides": all_o, "add_instruments": copy.deepcopy(fills + ups + movers)}
    seg = P["P05"]["segments"]
    phrase = seg[0]["cycle"]
    sky_cycle = []
    for i in range(6):
        bay = 1 + i
        sky_cycle.append({"look": "P05_SKY_APPROACH", "level": 0.9,
                          "overrides": {"FILL_L": {"keying": {"strike_distance_cm": 650.0 + 500.0 * i, "ramp_distance_cm": 200.0}},
                                        "FILL_R": {"keying": {"strike_distance_cm": 400.0 + 500.0 * i, "ramp_distance_cm": 200.0}}},
                          "note": "fills strike in sequence (L then R), each bay's a little further ahead" if bay == 1 else ""})
    blink_cycle = [{"look": "P05_SKY_CUT_BLINK", "level": 0.9,
                    "drama": {"after_pass": "EXTINGUISH", "after_pass_distance_cm": 100.0}} for unused in range(6)]
    all_cycle = [{"look": "P05_ALL_ON", "level": lvl} for lvl in (0.85, 0.9, 1.0, 0.9, 1.0, 0.95)]
    rest = [copy.deepcopy(phrase[(18 + i) % 7]) for i in range(7)]  # keep the old phrase phase from bay 19 on
    P["P05"]["segments"] = [{"bays": [1, 6], "cycle": sky_cycle}, {"bays": [7, 12], "cycle": blink_cycle},
                            {"bays": [13, 18], "cycle": all_cycle}, {"bays": [19, 84], "cycle": rest}, seg[1]]
    P["P05"]["max_consecutive_lit_exempt"] = [[1, 18]]
    P["P05"]["no_cross_note"] = ("6 Oct round 2: NOT enabled - the cloud low sides of P05_COOL_THEATRICAL (which Gary"
                                 " likes: 'cloud lighting very good') aim across (bay 1: LOW_SIDE_L_KEY y -1100 -> +575)."
                                 " The new FILL/UPLIGHT/TOP spots are own-side (harness checks them separately)")
    P["P05"]["score_revision"] = "2026-10-06 round 2: bays 1-18 sky approach / cut + blink / all on (movers data only); 19-93 unchanged phrase + crush"

    # ------------------------------------------------------------------ P06
    model = p06_beat_model()
    s["passages"]["P06"]["beat_map"] = model
    gold = copy.deepcopy(v["P06_GRAND_GOLD"]["instrument_overrides"])
    gold["LOW_SIDE_L_KEY"].update({"color_rgb_linear": [0.42, 0.58, 1.0], "temperature_kelvin": 9000.0, "intensity": 620.0,
                                   "flicker": flick("Breath")})
    gold["LOW_SIDE_R_FILL"].update({"color_rgb_linear": [0.3, 0.38, 0.85], "temperature_kelvin": 10000.0, "intensity": 170.0})
    gold["BEAM_R"].update({"color_rgb_linear": [0.6, 0.75, 1.0], "temperature_kelvin": 9000.0, "intensity": 5000.0})
    v["P06_SLEEPY_BLUE"] = {"base": "THEATRICAL", "intent": "P06 first third (note 59): the sideways wash goes cool 'sleepy hollow' blue (key breathes gently), gold tops and warm lantern practicals stay as the only warmth",
                            "instrument_overrides": gold}
    ember = lambda slot, loc, lm, flicker, body=None: bulb(  # noqa: E731
        slot, loc, lm, [1.0, 0.3, 0.06], 1800.0, 200.0, flicker, scale=(0.09, 0.09, 0.12), style="ember bulb (6 Oct)",
        body_mode=body)
    v["P06_EMBER_DARK"] = {
        "base": "THEATRICAL",
        "intent": "P06 middle third (note 59 'keep it dark with blinking; hanging and floor ember bulbs ... glowing like embers, reflecting on the floor, with little light'): one blinking cold top, four ember bulbs (two hanging, two on the floor)",
        "drop_slots": ["TOP_R", "LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "BEAM_R", "PRACTICAL_CLAMP", "PRACTICAL_BULB_DEAD"],
        "instrument_overrides": {"TOP_L": wing_top(70.0, [0.6, 0.72, 1.0], 8000.0, "LEFT", "Fault")},
        "add_instruments": [ember("EMBER_HANG_L", [-40.0, -820.0, 230.0], 35.0, "Slow"),
                            ember("EMBER_HANG_R", [60.0, 860.0, 175.0], 28.0, "Breath"),
                            ember("EMBER_FLOOR_L", [20.0, -960.0, 12.0], 22.0, "Slow"),
                            ember("EMBER_FLOOR_R", [-30.0, 1010.0, 12.0], 30.0, None)]}
    v["P06_EMBER_BEAT"] = copy.deepcopy(v["P06_EMBER_DARK"])
    v["P06_EMBER_BEAT"]["drop_slots"] = ["LOW_SIDE_L_KEY", "LOW_SIDE_R_FILL", "BEAM_R", "PRACTICAL_CLAMP", "PRACTICAL_BULB_DEAD"]
    v["P06_EMBER_BEAT"]["instrument_overrides"]["TOP_R"] = wing_top(280.0, [0.78, 0.86, 1.0], 7000.0, "RIGHT")
    v["P06_EMBER_BEAT"]["instrument_overrides"]["TOP_R"]["keying"] = {"ramp_distance_cm": 25.0, "ignition_stutter": 0.0,
                                                                     "after_pass": "DECAY", "after_pass_distance_cm": 150.0,
                                                                     "decay_distance_cm": 500.0}
    v["P06_EMBER_BEAT"]["intent"] = "P06_EMBER_DARK plus a cold moon top that STRIKES ON A MUSIC MOMENT (per-bay strike distance from beat_map) and decays behind Puss"
    sleepy = []
    for i, bay in enumerate(range(11, 22)):
        row = [{"look": "P06_SLEEPY_BLUE", "level": 0.9}, {"look": "P06_SLEEPY_BLUE", "level": 0.75, "mirror": ["LOW_SIDE", "BEAM"]},
               {"look": "P06_SLEEPY_BLUE", "level": 0.85}, {"look": "GAP", "level": 1.0}][i % 4]
        sleepy.append(copy.deepcopy(row))
    middle = []
    beats = {b["bay"]: b for b in model["beats"]}
    harp = set(model["harp_bays"])
    for bay in range(22, 43):
        if bay in beats:
            row = {"look": "P06_EMBER_BEAT", "level": 1.0, "mirror": ["PRACTICAL"] if bay % 2 else [],
                   "overrides": {"TOP_R": {"keying": {"strike_distance_cm": beats[bay]["strike_distance_cm"]}}},
                   "note": "beat %.2f s (%s)" % (beats[bay]["beat_s"], beats[bay]["kind"])}
        else:
            row = {"look": "P06_EMBER_DARK", "level": 1.0, "mirror": ["PRACTICAL"] if bay % 2 else []}
        if bay in harp:
            row.setdefault("overrides", {}).setdefault("TOP_L", {})["flicker"] = flick("HarpFlutter")
            for slot in ("EMBER_HANG_L", "EMBER_HANG_R"):
                row["overrides"][slot] = {"flicker": flick("HarpFlutter")}
            row["note"] = (row.get("note", "") + " | harp flutter").strip(" |")
        middle.append(row)
    seg = P["P06"]["segments"]
    failing = copy.deepcopy(seg[1])
    failing["bays"] = [43, 63]
    failing["level_from"] = 0.45
    failing["note"] = "6 Oct round 2: the failing gold now only in the last third (fires come tomorrow, Niagara: leave room); starts at 0.45 after the dark middle"
    P["P06"]["segments"] = [{"bays": [1, 1], "cycle": [{"look": "P06_SLEEPY_BLUE", "level": 1.0}]},
                            {"bays": [2, 10], "cycle": [{"look": "P06_SLEEPY_BLUE", "level": 1.0, "note": "yielded to lighting_events black mode (ACTIVE at 64 bays): never authored here"}]},
                            {"bays": [11, 21], "cycle": sleepy},
                            {"bays": [22, 42], "cycle": middle},
                            failing, seg[2]]
    P["P06"]["monotone_dark_segment"] = [43, 64]
    P["P06"]["max_consecutive_lit_exempt"] = [[2, 10], [22, 64]]
    P["P06"]["score_revision"] = "2026-10-06 round 2: first third sleepy-hollow blue wash; middle dark + blinking + ember bulbs + beat strikes + harp flutter; last third failing gold kept (fires tomorrow)"
    P["P06"]["no_cross_shots"] = {"enabled": True, "bays": [22, 42], "centre_tolerance_cm": 100.0,
                                  "nominal_panel_abs_y_cm": 900.0, "note": "6 Oct: the middle third is own-side only"}
    with open(DST, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(s, handle, indent=2)
        handle.write("\n")
    print("wrote", DST)


def p06_beat_model():
    """Music -> bays for P06 (SW_P06_IntoVoid, the current track: no P06 walking-swap record exists).
    INFERRED timing model: constant walk speed v = 27640.28 cm / 110.561 s (run_p6.json expected_new_distance_cm and
    p06_tail_extend_args.json expected_old_len), bay k passes at d_k = (k - 0.5) * D / 64 (uniform spacing - the 4 Oct
    'fixed_length_and_time' re-space; lead-in/tail not measured). A beat lamp in bay k strikes when Puss is
    S = d_k - v * t_beat short of it; k is the first bay at least 1.5 bays ahead of Puss at the beat.
    The DRY's beat_check re-derives each strike time from the LIVE per-bay intervals and gaps."""
    a = json.load(open(ANALYSIS, encoding="utf-8"))
    T, D, N = 110.561125, 27640.28, 64
    v = D / T
    pitch = D / N
    beats = []
    for row in a["majorChangeProposals"]:
        t = float(row["timeSeconds"])
        k = int(math.ceil((v * t) / pitch + 0.5 + 1.5))
        if not 22 <= k <= 42:
            continue  # first third is black-mode (2-10) / quiet; last third waits for the fires
        strike = (k - 0.5) * pitch - v * t
        beats.append({"bay": k, "beat_s": round(t, 2), "strength": round(float(row["strength"]), 2), "kind": "major change",
                      "strike_distance_cm": round(strike, 1), "first_pass_s": round(0.5 * pitch / v, 3)})
    dense = []
    curve = a["featureCurves"]["curves"]["rhythmicDensity"]
    rate = float(a["featureCurves"]["rateHz"])
    for i in range(0, len(curve) - 20, 10):
        if sum(curve[i:i + 20]) / 20.0 > 0.5:
            dense.append(i / rate)
    harp = sorted({int(math.ceil(v * t / pitch + 0.5)) + j for t in dense for j in (0, 1)})
    return {"source": "Saved/InfinityStage/MusicAnalysis/P06_WalkingMusic_6_into_void.analysis.json (sha f13530cf...)",
            "model": "INFERRED constant speed %.2f cm/s, uniform pitch %.1f cm, first pass %.2f s" % (v, pitch, 0.5 * pitch / v),
            "beats": beats, "harp_windows_s": dense, "harp_bays": [b for b in harp if 22 <= b <= 42],
            "moments_outside_middle": [round(float(r["timeSeconds"]), 2) for r in a["majorChangeProposals"]
                                       if not any(abs(float(r["timeSeconds"]) - b["beat_s"]) < 0.01 for b in beats)],
            "note": "major changes at 12.40 (black-mode bays) and 73.79/80.06 (last third, fires tomorrow) are left for later; the 68.55 s change (strength 1.0) also gets the P06 car drive-by (place_p06_car_light.py)"}


if __name__ == "__main__":
    main()
