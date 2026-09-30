"""Read-only: plan the blink spots for P02-P06 from P01's (Gary: "the blinking
spotlight with a shadow in it near the end of P01 is really effective").

Source: P01 Wing 041 "Entry High -Y", read exactly from the Show. It's a 2000 cd,
9.8/11.7 deg, 22 cm source radius, shadowed spot with MI_LF_Flicker_Buzz, high
on one side, thrown across into the centre of the path. Gary put a test object
1.25 m in front of the lens "about tuning shadow focus distance".

One lamp per passage (two in long P05), at the pair nearest the route fraction,
alternating sides. The lamp's offset from its pair root is scaled by the
passage's bay, lateral and height ratios. It's re-aimed at P01's pool point,
scaled the same way, and the intensity is scaled by throw squared so the pool
keeps P01's brightness.

Each lamp gets a gobo made of the machine (timber from the rig, not scenery),
placed WITH the lamp. The gobo's distance from the lens is varied deliberately.
With a 44 cm source, a bar of width w at distance d throws a shadow of
geometric width w*D/d, blurred by 44*(D-d)/d. Its peak darkness is about
w/44 (1.0 or more means a hard core). Its share of the pool is its share of
the beam at d. Close means vast and soft; far, with a bigger bar, means
smaller and hard-cored.

Writes blink_spots_plan.json. Lean: all work in main(); cues are found by GUID.
"""
import json
import math
import os
import statistics

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
GEOMETRY = {"02": (600.0, 1000.0), "03": (500.0, 800.0), "04": (600.0, 1000.0), "05": (250.0, 600.0), "06": (750.0, 1000.0)}
P01_HALF, P01_CARD = 750.0, 1000.0
BEAM = "/Game/EnvironmentPacks/Forest_Environment_Set/Environment/Small_Architecture/Meshes/SM_wood_beam_01"
POST = "/Game/EnvironmentPacks/Forest_Environment_Set/Environment/Small_Architecture/Meshes/SM_wood_beam_02"
# Mesh bounds, read 29 Sep (gobo_candidates.json): min and max in cm.
BOUNDS = {BEAM: ((-136.5, -6.7, -2.3), (155.4, 1.4, 17.0)), POST: ((-5.6, -3.6, -0.4), (5.2, 5.7, 117.8))}
# Gobo kinds: "bar" is a horizontal timber across the beam, presenting w cm to it,
# 8 cm deep along it. "lines" is a vertical bundle of w cm hanging through it.
KINDS = {"batten_flat": ("bar", BEAM, 10.0), "batten_edge": ("bar", BEAM, 19.0),
         "flown_timber": ("bar", BEAM, 30.0), "flown_timber_wide": ("bar", BEAM, 45.0),
         "line_bundle": ("lines", POST, 12.0)}
# (route fraction, side, kelvin or None = P01's 9280 K, gobo kind, lens-to-gobo cm).
# The two cold lamps take the extremes: P05's second the vastest, softest shadow,
# P06 the crispest. The warm four sit between; P02 repeats P01's own 1.25 m.
PLACES = {"02": [(0.80, 1.0, 4000.0, "batten_flat", 125.0)],
          "03": [(0.80, -1.0, 4000.0, "line_bundle", 250.0)],
          "04": [(0.80, 1.0, 4000.0, "batten_edge", 200.0)],
          "05": [(0.60, -1.0, 4000.0, "flown_timber", 350.0), (0.85, 1.0, None, "batten_edge", 90.0)],
          "06": [(0.80, -1.0, None, "flown_timber_wide", 550.0)]}
OFF_RATIO = 14.0 / 26.0   # P01's test object sat 14 cm off a 26 cm beam radius.


def gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def band_fraction(R, lo, hi):
    """Share of a disc of radius R lying between two parallel chords."""
    def seg(h):
        h = max(-R, min(R, h))
        return R * R * math.acos(h / R) - h * math.sqrt(R * R - h * h)
    return (seg(lo) - seg(hi)) / (math.pi * R * R)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    assert ed.get_editor_world() and ed.get_game_world() is None, "PIE or no editor world"
    show = unreal.EditorAssetLibrary.load_asset(SHOW)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    passages = {p.get_actor_label()[8:10]: p for p in sub.get_all_level_actors() if isinstance(p, unreal.InfinityStagePassageActor)}

    def pairs_of(pn):
        p = passages[pn]
        wanted = {gs(g) for g in show.get_wing_pair_cue_guids_in_passage(p.get_editor_property("passage_guid"))}
        route = p.get_editor_property("route")
        rows = []
        for cue in show.get_editor_property("cues"):
            cg = gs(cue.get_editor_property("cue_guid"))
            if cg not in wanted:
                continue
            st = next((a for a in cue.get_editor_property("wing_pair").get_editor_property("attachments")
                       if "STATION" in str(a.get_editor_property("anchor"))), None)
            if not st:
                continue
            root = p.get_attachment_anchor_world_transform(cue.get_editor_property("cue_guid"), st.get_editor_property("attachment_guid"))
            key = route.find_input_key_closest_to_world_location(root.translation)
            rows.append({"cue_guid": cg, "label": str(cue.get_editor_property("label")),
                         "route_cm": route.get_distance_along_spline_at_spline_input_key(key)})
        return sorted(rows, key=lambda r: r["route_cm"])

    # The source lamp, exactly.
    src = None
    for cue in show.get_editor_property("cues"):
        if str(cue.get_editor_property("label")) != "P01 Wing 041":
            continue
        for a in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if str(a.get_editor_property("label")) == "P01 Wing 041 Entry High -Y":
                src = a
    assert src is not None, "P01 Wing 041 Entry High -Y not found"
    L = src.get_editor_property("lighting")
    t = src.get_editor_property("relative_transform")
    r = t.rotation.rotator()
    loc = (t.translation.x, t.translation.y, t.translation.z)
    pr, yr = math.radians(r.pitch), math.radians(r.yaw)
    fwd = (math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), math.sin(pr))
    tpool = -loc[2] / fwd[2]
    pool = tuple(loc[i] + fwd[i] * tpool for i in range(3))
    source = {"loc": [round(v, 1) for v in loc], "pool": [round(v, 1) for v in pool], "throw": round(tpool, 1),
              "roll": r.roll, "intensity": L.get_editor_property("intensity"),
              "inner": L.get_editor_property("inner_cone_angle_degrees"), "outer": L.get_editor_property("outer_cone_angle_degrees"),
              "use_temperature": bool(L.get_editor_property("use_temperature")),
              "kelvin": L.get_editor_property("temperature_kelvin"), "radius": L.get_editor_property("attenuation_radius_cm"),
              "source_radius": L.get_editor_property("source_radius_cm"),
              "soft_source_radius": L.get_editor_property("soft_source_radius_cm"),
              "cast_shadows": bool(L.get_editor_property("cast_shadows")),
              "light_function": L.get_editor_property("light_function_material").get_path_name()
              if L.get_editor_property("light_function_material") else None}
    tan_outer = math.tan(math.radians(source["outer"]))
    src_d = 2.0 * source["source_radius"]
    p01 = pairs_of("01")
    sx01 = statistics.median(b["route_cm"] - a["route_cm"] for a, b in zip(p01, p01[1:]))

    plan = []
    for pn, spots in PLACES.items():
        pairs = pairs_of(pn)
        spacing = statistics.median(b["route_cm"] - a["route_cm"] for a, b in zip(pairs, pairs[1:]))
        sx, sy, sz = spacing / sx01, GEOMETRY[pn][0] / P01_HALF, GEOMETRY[pn][1] / P01_CARD
        total = pairs[-1]["route_cm"] - pairs[0]["route_cm"]
        for frac, side, kelvin, kind, dist in spots:
            target = min(pairs, key=lambda q: abs(q["route_cm"] - (pairs[0]["route_cm"] + frac * total)))
            mirror = -side   # P01's lamp is on -Y; side +1 mirrors it to +Y.
            lp = (loc[0] * sx, loc[1] * sy * mirror, loc[2] * sz)
            pp = (pool[0] * sx, pool[1] * sy * mirror, 0.0)
            d = [pp[i] - lp[i] for i in range(3)]
            throw = math.sqrt(sum(v * v for v in d))
            pitch = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
            yaw = math.degrees(math.atan2(d[1], d[0]))
            u = tuple(v / throw for v in d)
            h = math.hypot(u[0], u[1])
            right = (-u[1] / h, u[0] / h, 0.0)
            up = cross(right, u)
            if up[2] < 0:
                up = tuple(-v for v in up)
            shape, mesh, w = KINDS[kind]
            R = dist * tan_outer
            off = OFF_RATIO * R
            mn, mx = BOUNDS[mesh]
            ext = [mx[i] - mn[i] for i in range(3)]
            mid = [(mx[i] + mn[i]) / 2.0 for i in range(3)]
            if shape == "bar":
                # Mesh X across the beam (right), Z = the presented width (beam-up).
                centre = [lp[i] + u[i] * dist + up[i] * off for i in range(3)]
                length = max(60.0, 2.4 * R)
                scale = (length / ext[0], 8.0 / ext[1], w / ext[2])
                ax_x, ax_z = right, up
            else:
                # A vertical bundle through the beam, offset sideways, long enough
                # to cross the beam's full vertical extent twice over.
                centre = [lp[i] + u[i] * dist + right[i] * off for i in range(3)]
                length = max(300.0, 4.0 * R / max(0.2, h))
                scale = (w / ext[0], w / ext[1], length / ext[2])
                ax_x, ax_z = right, (0.0, 0.0, 1.0)
            ax_y = cross(ax_z, ax_x)
            axes = (ax_x, ax_y, ax_z)
            frac_blocked = band_fraction(R, off - w / 2.0, off + w / 2.0)
            # Actor location puts the mesh's bounds centre on the planned centre.
            pivot = [centre[i] - sum(axes[j][i] * mid[j] * scale[j] for j in range(3)) for i in range(3)]
            rot = unreal.MathLibrary.make_rot_from_xz(unreal.Vector(*ax_x), unreal.Vector(*ax_z))
            half = GEOMETRY[pn][0]
            plan.append({"passage": f"P{pn}", "cue_guid": target["cue_guid"], "cue": target["label"],
                         "route_frac": frac, "side": "+Y" if side > 0 else "-Y",
                         "spot": {"loc": [round(v, 1) for v in lp], "pitch": round(pitch, 3), "yaw": round(yaw, 3),
                                  "roll": source["roll"],
                                  "intensity_cd": round(source["intensity"] * (throw / source["throw"]) ** 2, 1),
                                  "kelvin": kelvin if kelvin is not None else source["kelvin"],
                                  "radius_cm": round(max(source["radius"] * throw / source["throw"], throw * 1.1), 1)},
                         "gobo": {"kind": kind, "mesh": mesh, "lens_cm": dist, "presented_cm": w,
                                  "loc": [round(v, 1) for v in pivot], "centre": [round(v, 1) for v in centre],
                                  "rot": [round(rot.roll, 3), round(rot.pitch, 3), round(rot.yaw, 3)],
                                  "scale": [round(v, 4) for v in scale], "length_cm": round(length, 1),
                                  "outboard_cm": round(abs(centre[1]) - half, 1), "height_cm": round(centre[2], 1)},
                         "predicted": {"beam_share": round(frac_blocked, 3), "peak_darkness": round(min(1.0, w / src_d), 2),
                                       "pool_m": round(2.0 * throw * tan_outer / 100.0, 2),
                                       "shadow_m": round(w * throw / dist / 100.0, 2),
                                       "blur_m": round(src_d * (throw - dist) / dist / 100.0, 2)},
                         "throw_cm": round(throw), "scale": [round(sx, 3), round(sy, 3), round(sz, 3)]})
    report = {"source": source, "p01_spacing": sx01, "rows": plan}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexStructure", "blink_spots_plan.json")
    json.dump(report, open(out, "w"), indent=1)
    unreal.log(f"BLINK_SPOTS_PLAN_OK|spots={len(plan)}|mutated=0")


main()
