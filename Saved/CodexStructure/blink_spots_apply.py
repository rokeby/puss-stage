"""Apply blink_spots_plan.json: the blink spots for P02-P06, each with its gobo
placed in the same write (Gary liked P01's blinking spot; conductor approved 29 Sep
"additive, GUID-keyed, backed up, named revert, shadows confined to the six").

Each planned pair gains two attachments after its existing ones, which stay
exactly as they are:
- "<cue> Blink Spot": P01 Wing 041 Entry High -Y's full light settings (flicker
  light function, 22 cm source, shadows), re-posed, with the plan's intensity,
  colour temperature and reach.
- "<cue> Blink Gobo": a timber prop across or through the beam at the plan's
  lens distance.

GUIDs are read-only from Python; only ReplicateLightAttachments mints them, and
only for lights. So a SCRATCH P01 pair outside the plan is padded with blank
lamps and replicated onto the six pairs. Each pair is then rebuilt from its own
snapshot, with two fresh ordinals appended: one written as the lamp, one
converted to the prop (a kind change keeps the GUID). The scratch pair is
restored exactly.

Before any save, verified:
- each pair's old attachments, and every other cue, are unchanged;
- enabled lights and shadow casters rise by exactly 6, in the planned passages;
- every new actor materializes where planned.

Structures 02-06 are re-fitted, and only the Show and the level are saved. Take a
Backups/PreBlinkSpots-* snapshot (Show + umap) first; blink_spots_revert.py
removes the twelve by GUID. Rehearse with BLINK_DRY_RUN (blink_spots_dryrun.py):
all guards, world-space traces and the revert record, no write. Lean: all work
inside main().
"""
import datetime
import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
PLAN = os.path.join(HERE, "blink_spots_plan.json")
RECORD = os.path.join(HERE, "blink_spots_revert_record.json")
DRY_OUT = os.path.join(HERE, "blink_spots_dryrun.json")
SRC_CUE, SRC_LABEL = "P01 Wing 041", "P01 Wing 041 Entry High -Y"
SPOT, GOBO = "Blink Spot", "Blink Gobo"
PER_PASSAGE = {"P02": 1, "P03": 1, "P04": 1, "P05": 2, "P06": 1}
LIGHT_FIELDS = ("type", "intensity_units", "intensity", "color", "use_temperature", "temperature_kelvin",
                "attenuation_radius_cm", "inner_cone_angle_degrees", "outer_cone_angle_degrees",
                "source_radius_cm", "soft_source_radius_cm", "cast_shadows", "cast_volumetric_shadow",
                "volumetric_scattering_intensity", "light_function_material")


def fail(message):
    raise RuntimeError(f"BLINK_SPOTS_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def dirty():
    return ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def norm(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (unreal.Color, unreal.LinearColor)):
        return [round(v.r, 4), round(v.g, 4), round(v.b, 4), round(v.a, 4)]
    if isinstance(v, unreal.Transform):
        r = v.rotation.rotator()
        return [round(c, 2) for c in (v.translation.x, v.translation.y, v.translation.z,
                                      r.roll, r.pitch, r.yaw, v.scale3d.x, v.scale3d.y, v.scale3d.z)]
    if isinstance(v, unreal.Object):
        return v.get_path_name()
    return str(v)


def fingerprint(att):
    L = att.get_editor_property("lighting")
    head = [gs(att.get_editor_property("attachment_guid")), str(att.get_editor_property("label")),
            str(att.get_editor_property("kind")), str(att.get_editor_property("anchor")),
            bool(att.get_editor_property("enabled")), norm(att.get_editor_property("relative_transform")),
            norm(att.get_editor_property("mesh")), norm(att.get_editor_property("actor_class"))]
    return json.dumps(head + [norm(L.get_editor_property(n)) for n in LIGHT_FIELDS])


def is_light(att):
    return att.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT


def census(show, passage_of_cue):
    lit, casters, per = 0, 0, {}
    for cue in show.get_editor_property("cues"):
        if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            continue
        pn = passage_of_cue.get(gs(cue.get_editor_property("cue_guid")), "?")
        for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if not is_light(att) or not att.get_editor_property("enabled"):
                continue
            c = int(bool(att.get_editor_property("lighting").get_editor_property("cast_shadows")))
            lit += 1
            casters += c
            per.setdefault(pn, [0, 0])
            per[pn][0] += 1
            per[pn][1] += c
    return lit, casters, per


def trace(world, start, end):
    hit = unreal.SystemLibrary.line_trace_single(world, start, end, unreal.TraceTypeQuery.ECC_VISIBILITY, True, [],
                                                 unreal.DrawDebugTrace.NONE, True)
    h = hit.to_tuple() if hit else None
    if not (h and h[0]):
        return None
    actor = next((x for x in h if isinstance(x, unreal.Actor)), None)
    comp = next((x for x in h if isinstance(x, unreal.PrimitiveComponent)), None)
    return {"actor": actor.get_actor_label() if actor else None, "component": comp.get_name() if comp else None,
            "distance_cm": round(h[3]) if isinstance(h[3], float) else None}


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE active")
    content0, maps0 = dirty()
    if content0 or maps0:
        fail(f"editor already dirty: {content0} {maps0}")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
        fail("bench actors in the level")
    plan = json.load(open(PLAN, encoding="utf-8"))
    rows = plan["rows"]
    got = {}
    for r in rows:
        got[r["passage"]] = got.get(r["passage"], 0) + 1
    if got != PER_PASSAGE:
        fail(f"plan rows per passage {got}")

    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    passages = {("P" + p.get_actor_label()[8:10]): p for p in actors if isinstance(p, unreal.InfinityStagePassageActor)}
    passage_of_cue = {}
    for pn, p in passages.items():
        for g in show.get_wing_pair_cue_guids_in_passage(p.get_editor_property("passage_guid")):
            passage_of_cue[gs(g)] = pn
    cues = list(show.get_editor_property("cues"))
    index = {gs(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}

    # The source lamp must still be the one the plan read.
    src = src_cue = None
    for c in cues:
        if str(c.get_editor_property("label")) == SRC_CUE:
            for a in c.get_editor_property("wing_pair").get_editor_property("attachments"):
                if str(a.get_editor_property("label")) == SRC_LABEL:
                    src, src_cue = a, c
    if src is None:
        fail("source lamp not found")
    st = src.get_editor_property("relative_transform")
    sL = src.get_editor_property("lighting")
    ps = plan["source"]
    if (abs(st.translation.x - ps["loc"][0]) > 0.5 or abs(st.translation.y - ps["loc"][1]) > 0.5
            or abs(st.translation.z - ps["loc"][2]) > 0.5 or abs(sL.get_editor_property("intensity") - ps["intensity"]) > 0.01
            or abs(sL.get_editor_property("source_radius_cm") - ps["source_radius"]) > 0.01):
        fail("the P01 source lamp changed since the plan was read")
    src_anchor = src.get_editor_property("anchor")

    # Targets, by GUID; none may already carry a blink spot.
    targets = {}
    for r in rows:
        ci = index.get(r["cue_guid"])
        if ci is None:
            fail(f"{r['cue']}: cue GUID not in the Show")
        c = cues[ci]
        if str(c.get_editor_property("label")) != r["cue"] or passage_of_cue.get(r["cue_guid"]) != r["passage"]:
            fail(f"{r['cue']}: label or passage differs from the plan")
        atts = list(c.get_editor_property("wing_pair").get_editor_property("attachments"))
        if any(str(a.get_editor_property("label")).endswith((SPOT, GOBO)) for a in atts):
            fail(f"{r['cue']}: already has a blink spot; run blink_spots_revert.py first")
        station = next((a for a in atts if a.get_editor_property("anchor") == unreal.InfinityAttachmentAnchor.STATION), None)
        if station is None:
            fail(f"{r['cue']}: no station attachment to resolve its anchor")
        if r["cue_guid"] in targets:
            fail(f"{r['cue']}: two spots planned on one pair")
        targets[r["cue_guid"]] = {"row": r, "ci": ci, "atts": atts, "station": gs(station.get_editor_property("attachment_guid")),
                                  "station_guid": station.get_editor_property("attachment_guid"),
                                  "lights": sum(1 for a in atts if is_light(a))}

    # World-space checks: the beam reaches its pool, nothing stands between lamp
    # and gobo, and each gobo end is outboard of the wing line or above the cards.
    geometry = {"P02": (600.0, 1000.0), "P03": (500.0, 800.0), "P04": (600.0, 1000.0), "P05": (250.0, 600.0), "P06": (750.0, 1000.0)}
    report = {"rows": []}
    for cg, t in targets.items():
        r = t["row"]
        p = passages[r["passage"]]
        anchor = p.get_attachment_anchor_world_transform(cues[t["ci"]].get_editor_property("cue_guid"), t["station_guid"])
        if not isinstance(anchor, unreal.Transform):
            fail(f"{r['cue']}: anchor did not resolve")
        s, g = r["spot"], r["gobo"]
        pr, yr = math.radians(s["pitch"]), math.radians(s["yaw"])
        u = unreal.Vector(math.cos(pr) * math.cos(yr), math.cos(pr) * math.sin(yr), math.sin(pr))
        lamp = unreal.MathLibrary.transform_location(anchor, unreal.Vector(*s["loc"]))
        uw = unreal.MathLibrary.transform_direction(anchor, u)
        gc = unreal.MathLibrary.transform_location(anchor, unreal.Vector(*g["centre"]))
        rot = unreal.Rotator(roll=g["rot"][0], pitch=g["rot"][1], yaw=g["rot"][2])
        long_axis = (unreal.MathLibrary.get_up_vector(rot) if g["kind"] == "line_bundle"
                     else unreal.MathLibrary.get_forward_vector(rot))
        half, card = geometry[r["passage"]]
        ends = []
        for sign in (-1.0, 1.0):
            e = [g["centre"][i] + sign * long_axis.to_tuple()[i] * g["length_cm"] / 2.0 for i in range(3)]
            ends.append({"outboard_cm": round(abs(e[1]) - half, 1), "above_card_cm": round(e[2] - card, 1)})
        clear = all(e["outboard_cm"] >= 0.0 or e["above_card_cm"] >= 100.0 for e in ends)
        la = unreal.MathLibrary.transform_direction(anchor, long_axis)
        report["rows"].append({
            "passage": r["passage"], "cue": r["cue"], "side": r["side"], "kelvin": s["kelvin"], "cd": s["intensity_cd"],
            "gobo": g["kind"], "lens_cm": g["lens_cm"], "lamp_world": [round(v) for v in lamp.to_tuple()],
            "beam_first_hit": trace(world, lamp, lamp + uw * (r["throw_cm"] * 1.15)), "throw_cm": r["throw_cm"],
            "lamp_to_gobo_hit": trace(world, lamp, gc - uw * 10.0),
            "gobo_span_hit": trace(world, gc - la * (g["length_cm"] / 2.0), gc + la * (g["length_cm"] / 2.0)),
            "gobo_ends": ends, "gobo_clear": clear, "predicted": r["predicted"]})
        if not clear:
            fail(f"{r['cue']}: gobo end inside the wing line below card height: {ends}")
    # P01, as it is now: what its blink spot's axis lands on (the walnut boards?).
    p01 = passages["P01"]
    w01 = p01.get_attachment_world_transform(src_cue.get_editor_property("cue_guid"), src.get_editor_property("attachment_guid"))
    if isinstance(w01, unreal.Transform):
        f01 = unreal.MathLibrary.get_forward_vector(w01.rotation.rotator())
        report["p01_now"] = {"lamp_world": [round(v) for v in w01.translation.to_tuple()],
                             "beam_first_hit": trace(world, w01.translation, w01.translation + f01 * 3000.0)}

    # Scratch: a light-only P01 pair outside the plan, never the source pair.
    scratch_ci = None
    for i in reversed(range(len(cues))):
        c = cues[i]
        cg = gs(c.get_editor_property("cue_guid"))
        if (passage_of_cue.get(cg) == "P01" and cg not in targets and str(c.get_editor_property("label")) != SRC_CUE
                and all(is_light(a) for a in c.get_editor_property("wing_pair").get_editor_property("attachments"))):
            scratch_ci = i
            break
    if scratch_ci is None:
        fail("no light-only P01 pair for the scratch")
    scratch_guid = cues[scratch_ci].get_editor_property("cue_guid")
    scratch_original = list(cues[scratch_ci].get_editor_property("wing_pair").get_editor_property("attachments"))
    padding = max(0, max(t["lights"] for t in targets.values()) + 2 - len(scratch_original))

    # Load the gobo meshes BEFORE fingerprinting, so no soft pointer can read
    # differently between the before and after snapshots.
    meshes = {}
    for t in targets.values():
        path = t["row"]["gobo"]["mesh"]
        if path not in meshes:
            meshes[path] = unreal.EditorAssetLibrary.load_asset(path)
            if not isinstance(meshes[path], unreal.StaticMesh):
                fail(f"gobo mesh {path} did not load")
    src_class = src.get_editor_property("actor_class")
    lit0, casters0, per0 = census(show, passage_of_cue)
    others0 = {cg: [fingerprint(a) for a in c.get_editor_property("wing_pair").get_editor_property("attachments")]
               for cg, c in ((gs(c.get_editor_property("cue_guid")), c) for c in cues)
               if cg not in targets and c.get_editor_property("type") == unreal.InfinityCueType.WING_PAIR}
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"),
              "pairs": {cg: {"cue": t["row"]["cue"], "passage": t["row"]["passage"],
                             "before": [gs(a.get_editor_property("attachment_guid")) for a in t["atts"]]}
                        for cg, t in targets.items()},
              "scratch": gs(scratch_guid), "lit_before": lit0, "casters_before": casters0, "per_passage_before": per0}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if len(json.load(open(RECORD, encoding="utf-8"))["pairs"]) != len(rows):
        fail("revert record did not read back")
    report.update({"census_before": {"lit": lit0, "casters": casters0, "per": per0},
                   "census_expected_after": {"lit": lit0 + len(rows), "casters": casters0 + len(rows)},
                   "scratch": str(cues[scratch_ci].get_editor_property("label")), "padding": padding,
                   "source_drama": str(sL.get_editor_property("drama"))[:400],
                   "source_actor_class": norm(src_class), "meshes": {k: norm(v) for k, v in meshes.items()},
                   "fingerprints_stable": others0 == {cg: [fingerprint(a) for a in c.get_editor_property("wing_pair").get_editor_property("attachments")]
                                                      for cg, c in ((gs(c.get_editor_property("cue_guid")), c) for c in show.get_editor_property("cues"))
                                                      if cg not in targets and c.get_editor_property("type") == unreal.InfinityCueType.WING_PAIR}})
    unreal.log(f"BLINK_REVERT_RECORD_OK|pairs={len(rows)}|lit={lit0}|casters={casters0}|scratch={report['scratch']}|padding={padding}")
    if globals().get("BLINK_DRY_RUN"):
        json.dump(report, open(DRY_OUT, "w", encoding="utf-8"), indent=1)
        unreal.log(f"BLINK_DRY_RUN_OK|pairs={len(rows)}|mutated=0")
        return "dry"

    # ---- Mutate ----------------------------------------------------------------
    show.modify()

    def set_atts(ci, atts):
        cs = list(show.get_editor_property("cues"))
        c = cs[ci]
        pair = c.get_editor_property("wing_pair")
        pair.set_editor_property("attachments", atts)
        c.set_editor_property("wing_pair", pair)
        cs[ci] = c
        show.set_editor_property("cues", cs)

    def atts_of(ci):
        return list(show.get_editor_property("cues")[ci].get_editor_property("wing_pair").get_editor_property("attachments"))

    blank = unreal.InfinityCueAttachment()
    blank.set_editor_property("label", unreal.Text("Scratch"))
    blank.set_editor_property("kind", unreal.InfinityAttachmentKind.LIGHT)
    blank.set_editor_property("enabled", False)
    set_atts(scratch_ci, scratch_original + [blank] * padding)
    show.replicate_light_attachments(scratch_guid, [cues[t["ci"]].get_editor_property("cue_guid") for t in targets.values()])
    set_atts(scratch_ci, scratch_original)
    added = {}
    for cg, t in targets.items():
        r, s, g = t["row"], t["row"]["spot"], t["row"]["gobo"]
        lights = [a for a in atts_of(t["ci"]) if is_light(a)]
        if len(lights) < t["lights"] + 2:
            fail(f"{r['cue']}: replicate gave {len(lights)} lights, need {t['lights'] + 2}")
        lamp, prop = lights[t["lights"]], lights[t["lights"] + 1]
        minted = [gs(lamp.get_editor_property("attachment_guid")), gs(prop.get_editor_property("attachment_guid"))]
        if minted[0] in record["pairs"][cg]["before"] or minted[1] in record["pairs"][cg]["before"]:
            fail(f"{r['cue']}: fresh ordinal reused an existing GUID")
        L = src.get_editor_property("lighting")          # a copy of the source's whole light
        L.set_editor_property("intensity", float(s["intensity_cd"]))
        L.set_editor_property("temperature_kelvin", float(s["kelvin"]))
        L.set_editor_property("attenuation_radius_cm", float(s["radius_cm"]))
        lamp.set_editor_property("label", unreal.Text(f"{r['cue']} {SPOT}"))
        lamp.set_editor_property("kind", unreal.InfinityAttachmentKind.LIGHT)
        lamp.set_editor_property("anchor", src_anchor)
        lamp.set_editor_property("enabled", True)
        lamp.set_editor_property("relative_transform", unreal.Transform(
            location=unreal.Vector(*s["loc"]), rotation=unreal.Rotator(roll=s["roll"], pitch=s["pitch"], yaw=s["yaw"])))
        lamp.set_editor_property("lighting", L)
        lamp.set_editor_property("actor_class", src_class)
        lamp.set_editor_property("mesh", None)
        lamp.set_editor_property("effect", unreal.InfinityStageEffectSettings())
        lamp.set_editor_property("trigger_distance_cm", 800.0)
        prop.set_editor_property("label", unreal.Text(f"{r['cue']} {GOBO}"))
        prop.set_editor_property("kind", unreal.InfinityAttachmentKind.PROP)
        prop.set_editor_property("anchor", unreal.InfinityAttachmentAnchor.STATION)
        prop.set_editor_property("enabled", True)
        prop.set_editor_property("mesh", meshes[g["mesh"]])
        prop.set_editor_property("lighting", unreal.InfinityStageLightSettings())
        prop.set_editor_property("actor_class", None)
        prop.set_editor_property("effect", unreal.InfinityStageEffectSettings())
        prop.set_editor_property("trigger_distance_cm", 800.0)
        prop.set_editor_property("relative_transform", unreal.Transform(
            location=unreal.Vector(*g["loc"]), rotation=unreal.Rotator(roll=g["rot"][0], pitch=g["rot"][1], yaw=g["rot"][2]),
            scale=unreal.Vector(*g["scale"])))
        if [gs(lamp.get_editor_property("attachment_guid")), gs(prop.get_editor_property("attachment_guid"))] != minted:
            fail(f"{r['cue']}: a minted GUID changed while being written")
        set_atts(t["ci"], t["atts"] + [lamp, prop])
        added[cg] = minted

    # ---- Verify before any save --------------------------------------------------
    problems = []
    cues1 = list(show.get_editor_property("cues"))
    seen = set()
    for c in cues1:
        if c.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            continue
        for a in c.get_editor_property("wing_pair").get_editor_property("attachments"):
            gg = gs(a.get_editor_property("attachment_guid"))
            if set(gg) <= {"0", "-"} or gg in seen:
                problems.append(f"invalid or duplicate GUID {gg}")
            seen.add(gg)
    for cg, t in targets.items():
        now = atts_of(t["ci"])
        if [fingerprint(a) for a in now[:len(t["atts"])]] != [fingerprint(a) for a in t["atts"]] or len(now) != len(t["atts"]) + 2:
            problems.append(f"{t['row']['cue']}: existing attachments changed or count wrong")
        if [str(a.get_editor_property("label")) for a in now[-2:]] != [f"{t['row']['cue']} {SPOT}", f"{t['row']['cue']} {GOBO}"]:
            problems.append(f"{t['row']['cue']}: new attachments are not the planned ones")
        if now[-1].get_editor_property("kind") != unreal.InfinityAttachmentKind.PROP:
            problems.append(f"{t['row']['cue']}: gobo is not a prop")
    others1 = {cg: [fingerprint(a) for a in c.get_editor_property("wing_pair").get_editor_property("attachments")]
               for cg, c in ((gs(c.get_editor_property("cue_guid")), c) for c in cues1)
               if cg not in targets and c.get_editor_property("type") == unreal.InfinityCueType.WING_PAIR}
    if others1 != others0:
        problems.append(f"{sum(1 for k in others0 if others0[k] != others1.get(k))} other cues changed (scratch included)")
    lit1, casters1, per1 = census(show, passage_of_cue)
    if lit1 != lit0 + len(rows) or casters1 != casters0 + len(rows):
        problems.append(f"census lit {lit0}->{lit1}, casters {casters0}->{casters1}; expected +{len(rows)} each")
    for pn in set(per0) | set(per1):
        want = PER_PASSAGE.get(pn, 0)
        b, a = per0.get(pn, [0, 0]), per1.get(pn, [0, 0])
        if a[0] - b[0] != want or a[1] - b[1] != want:
            problems.append(f"{pn}: {b} -> {a}, expected +{want}")
    if problems:
        fail(f"Show edit wrong, NOT saved: {problems}")

    for pn in PER_PASSAGE:
        if not passages[pn].materialize_passage():
            fail(f"{pn} did not materialize")
    placed = {}
    actors1 = sub.get_all_level_actors()
    for cg, (lg, pg) in added.items():
        for gg, what in ((lg, "lamp"), (pg, "gobo")):
            hits = [a for a in actors1 if any(gg in str(tag) for tag in a.tags)]
            if len(hits) != 1:
                fail(f"{targets[cg]['row']['cue']} {what}: {len(hits)} actors carry its tag")
            placed[gg] = [round(v) for v in hits[0].get_actor_location().to_tuple()]
            if what == "gobo":
                smc = hits[0].get_component_by_class(unreal.StaticMeshComponent)
                if not smc or not smc.get_editor_property("static_mesh"):
                    fail(f"{targets[cg]['row']['cue']}: gobo has no mesh")
    refit = {}
    for s in actors1:
        if isinstance(s, unreal.InfinityStageStructureActor) and ("P" + s.get_actor_label()[-2:]) in PER_PASSAGE:
            before_h = int(s.get_editor_property("fixture_body_count"))
            if not s.materialize_structure():
                fail(f"{s.get_actor_label()} did not re-fit")
            refit[s.get_actor_label()] = [before_h, int(s.get_editor_property("fixture_body_count")), bool(s.is_structure_current())]
    if len(refit) != len(PER_PASSAGE) or not all(v[2] for v in refit.values()):
        fail(f"structures after re-fit: {refit}")
    content1, maps1 = dirty()
    if set(content1) - {SHOW_PATH} or set(maps1) - {EXPECTED_WORLD}:
        fail(f"out-of-scope dirty: {content1} {maps1}")
    if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
        fail("Show save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    content2, maps2 = dirty()
    record["added"] = added
    record["placed"] = placed
    json.dump(record, open(RECORD, "w", encoding="utf-8"), indent=1)
    unreal.log(f"BLINK_SPOTS_OK|pairs={len(added)}|lit={lit0}->{lit1}|casters={casters0}->{casters1}|refit={refit}"
               f"|show_saved=1|level_saved=1|dirty_after={len(content2)}+{len(maps2)}")
    return "applied"


result = main()
