"""Apply p456_baseline_plan.json: baseline lighting for P04, P05 and P06 (Gary, 29 Sep,
"build the lighting across all the dark scenes", relayed with his yes on the plan by
the conductor). Every planned lamp is an EXISTING attachment, rewritten IN PLACE:
same GUID, same list position, same count. P01, P02 and P03 are untouched, and
the script proves it by fingerprinting every other cue before and after.

Shadow census: enabled casters must not rise anywhere, show-wide or in any
passage; enabled lights must be unchanged. Then P04, P05 and P06 are materialized,
Structures 04, 05 and 06 re-fitted, and only the Show and the level saved.
Take a Backups/PreP456Baseline-* snapshot (Show + umap) first.
p456_baseline_revert.py restores every field from the record, by GUID.

Written lean after the 17:00 editor crash (an access violation in Python during
an MCP run): everything happens inside main(), no UE objects are kept at module
level, and references are dropped before returning. Rehearse with P456_DRY_RUN.
"""
import datetime
import json
import os
import re

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
PLAN = os.path.join(HERE, "p456_baseline_plan.json")
RECORD = os.path.join(HERE, "p456_baseline_revert_record.json")
TARGETS = ("P04", "P05", "P06")
FIELDS = ("type", "intensity_units", "intensity", "use_temperature", "temperature_kelvin", "color",
          "attenuation_radius_cm", "inner_cone_angle_degrees", "outer_cone_angle_degrees",
          "cast_shadows", "cast_volumetric_shadow", "volumetric_scattering_intensity")


def fail(message):
    raise RuntimeError(f"P456_BASELINE_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def plain(v):
    if isinstance(v, float):
        return round(v, 5)
    if isinstance(v, (bool, int, str)) or v is None:
        return v
    if isinstance(v, unreal.LinearColor):
        return [v.r, v.g, v.b, v.a]
    if isinstance(v, unreal.Color):
        return [v.r, v.g, v.b, v.a]
    return str(v)


def snapshot(att):
    t = att.get_editor_property("relative_transform")
    r = t.rotation.rotator()
    L = att.get_editor_property("lighting")
    return {"enabled": bool(att.get_editor_property("enabled")),
            "loc": [t.translation.x, t.translation.y, t.translation.z],
            "rot": [r.roll, r.pitch, r.yaw], "scale": [t.scale3d.x, t.scale3d.y, t.scale3d.z],
            **{f: plain(L.get_editor_property(f)) for f in FIELDS}}


def census(show, passage_of_cue):
    lit, casters, per = 0, 0, {}
    for cue in show.get_editor_property("cues"):
        if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            continue
        pn = passage_of_cue.get(unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid")), "?")
        for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT or not att.get_editor_property("enabled"):
                continue
            c = int(bool(att.get_editor_property("lighting").get_editor_property("cast_shadows")))
            lit += 1
            casters += c
            per.setdefault(pn, [0, 0])
            per[pn][0] += 1
            per[pn][1] += c
    return lit, casters, per


def fingerprints(show, skip_cue_guids):
    """Every other wing pair's lights, keyed by cue GUID (P05 reuses cue labels)."""
    out = {}
    for cue in show.get_editor_property("cues"):
        key = unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid"))
        if key in skip_cue_guids or cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            continue
        out[key] = json.dumps([snapshot(a) for a in cue.get_editor_property("wing_pair").get_editor_property("attachments")
                                 if a.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT])
    return out


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE active")
    c0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m0 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if c0 or m0:
        fail(f"editor already dirty: {c0} {m0}")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
        fail("bench actors in the level")
    plan = json.load(open(PLAN, encoding="utf-8"))
    rows = plan["rows"]
    if len(rows) != 1521 or {r["passage"] for r in rows} != set(TARGETS):
        fail(f"plan has {len(rows)} rows over {sorted({r['passage'] for r in rows})}")

    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    passages = {("P" + p.get_actor_label()[8:10]): p for p in actors if isinstance(p, unreal.InfinityStagePassageActor)}
    passage_of_cue = {}
    for pn, p in passages.items():
        for g in show.get_wing_pair_cue_guids_in_passage(p.get_editor_property("passage_guid")):
            passage_of_cue[unreal.GuidLibrary.conv_guid_to_string(g)] = pn
    # Locate every planned attachment by its own GUID: cue labels repeat in P05,
    # so a label cannot identify a pair. The plan's index and label must agree.
    cues = list(show.get_editor_property("cues"))
    where = {}
    for ci, c in enumerate(cues):
        if c.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            continue
        for ai, a in enumerate(c.get_editor_property("wing_pair").get_editor_property("attachments")):
            where[unreal.GuidLibrary.conv_guid_to_string(a.get_editor_property("attachment_guid"))] = (ci, ai)
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "rows": {}}
    target_ci = set()
    for r in rows:
        if r["guid"] not in where:
            fail(f"{r['cue']} {r['slot']}: GUID {r['guid']} not in the Show")
        ci, ai = where[r["guid"]]
        cue = cues[ci]
        att = cue.get_editor_property("wing_pair").get_editor_property("attachments")[ai]
        cg = unreal.GuidLibrary.conv_guid_to_string(cue.get_editor_property("cue_guid"))
        ok = (ai == r["index"] and str(cue.get_editor_property("label")) == r["cue"]
              and str(att.get_editor_property("label")) == f"{r['cue']} {r['slot']}"
              and passage_of_cue.get(cg) in TARGETS)
        if not ok:
            fail(f"{r['cue']} {r['slot']}: found at cue {ci} index {ai}, not as planned")
        target_ci.add(ci)
        record["rows"][r["guid"]] = {"cue": r["cue"], "cue_index": ci, "index": ai, "slot": r["slot"], "before": snapshot(att)}
    in_targets = {ci for ci, c in enumerate(cues)
                  if passage_of_cue.get(unreal.GuidLibrary.conv_guid_to_string(c.get_editor_property("cue_guid"))) in TARGETS}
    if target_ci != in_targets:
        fail(f"planned pairs ({len(target_ci)}) differ from the three passages' pairs ({len(in_targets)})")
    target_cue_guids = {unreal.GuidLibrary.conv_guid_to_string(cues[ci].get_editor_property("cue_guid")) for ci in target_ci}
    lit0, casters0, per0 = census(show, passage_of_cue)
    others0 = fingerprints(show, target_cue_guids)
    record.update({"lit_before": lit0, "casters_before": casters0, "per_passage_before": per0})
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if len(json.load(open(RECORD, encoding="utf-8"))["rows"]) != len(rows):
        fail("revert record did not read back")
    unreal.log(f"P456_REVERT_RECORD_OK|rows={len(rows)}|lit={lit0}|casters={casters0}|per={per0}")
    if globals().get("P456_DRY_RUN"):
        unreal.log("P456_DRY_RUN_OK|mutated=0")
        return "dry"

    show.modify()
    by_cue = {}
    for r in rows:
        by_cue.setdefault(record["rows"][r["guid"]]["cue_index"], []).append(r)
    for ci, rs in by_cue.items():
        cue = cues[ci]
        pair = cue.get_editor_property("wing_pair")
        atts = list(pair.get_editor_property("attachments"))
        for r in rs:
            att = atts[r["index"]]
            old = att.get_editor_property("relative_transform")
            att.set_editor_property("relative_transform", unreal.Transform(
                location=unreal.Vector(*r["loc"]), rotation=unreal.Rotator(roll=0.0, pitch=r["pitch"], yaw=r["yaw"]),
                scale=old.scale3d))
            L = att.get_editor_property("lighting")
            L.set_editor_property("intensity_units", unreal.InfinityStageLightIntensityUnits.CANDELAS)
            L.set_editor_property("intensity", float(r["intensity_cd"]))
            L.set_editor_property("use_temperature", bool(r["use_temperature"]))
            L.set_editor_property("temperature_kelvin", float(r["kelvin"]))
            L.set_editor_property("attenuation_radius_cm", float(r["radius_cm"]))
            L.set_editor_property("inner_cone_angle_degrees", float(r["inner"]))
            L.set_editor_property("outer_cone_angle_degrees", float(r["outer"]))
            L.set_editor_property("cast_shadows", bool(r["cast_shadows"]))
            L.set_editor_property("cast_volumetric_shadow", bool(r["cast_shadows"]))
            L.set_editor_property("volumetric_scattering_intensity", float(r["volumetric_scattering"]))
            att.set_editor_property("lighting", L)
            att.set_editor_property("enabled", True)
            atts[r["index"]] = att
        pair.set_editor_property("attachments", atts)
        cue.set_editor_property("wing_pair", pair)
        cues[ci] = cue
    show.set_editor_property("cues", cues)

    lit1, casters1, per1 = census(show, passage_of_cue)
    problems = []
    if lit1 != lit0:
        problems.append(f"enabled lights {lit0} -> {lit1}")
    if casters1 > casters0:
        problems.append(f"casters rose {casters0} -> {casters1}")
    for pn, (lit, cas) in per1.items():
        if cas > per0.get(pn, [0, 0])[1]:
            problems.append(f"{pn} casters rose {per0.get(pn)} -> {[lit, cas]}")
    if fingerprints(show, target_cue_guids) != others0:
        problems.append("a cue outside P04/P05/P06 changed")
    if problems:
        fail(f"Show edit wrong, NOT saved: {problems}")

    for pn in TARGETS:
        if not passages[pn].materialize_passage():
            fail(f"{pn} did not materialize")
    refit = {}
    for s in actors:
        if isinstance(s, unreal.InfinityStageStructureActor) and s.get_actor_label()[-2:] in ("04", "05", "06"):
            before_h = int(s.get_editor_property("fixture_body_count"))
            if not s.materialize_structure():
                fail(f"{s.get_actor_label()} did not re-fit")
            refit[s.get_actor_label()] = [before_h, int(s.get_editor_property("fixture_body_count")),
                                          bool(s.is_structure_current())]
    if len(refit) != 3 or not all(v[2] for v in refit.values()) or any(v[0] != v[1] for v in refit.values()):
        fail(f"structures after re-fit: {refit}")
    c1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()}
    m1 = {pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()}
    if c1 - {SHOW_PATH} or m1 - {EXPECTED_WORLD}:
        fail(f"out-of-scope dirty: {sorted(c1)} {sorted(m1)}")
    if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
        fail("Show save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    c2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    m2 = len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    unreal.log(f"P456_BASELINE_OK|lamps={len(rows)}|lit={lit0}->{lit1}|casters={casters0}->{casters1}"
               f"|per_before={per0}|per_after={per1}|refit={refit}|show_saved=1|level_saved=1|dirty_after={c2}+{m2}")
    return "applied"


result = main()
