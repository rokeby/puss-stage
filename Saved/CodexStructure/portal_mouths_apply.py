"""Portals at every passage mouth (Gary, 29 Sep late: yes). Structures 02-06 get
their portal switched on at its DEFAULTS, as Structure 01 did. This is the
constant module that lets one curtain bake serve every mouth, where the mouths
themselves vary up to 3x.

Defaults include bExtendGridiron (ON at a mouth: the carried rails run only
the 2.5 m to the first station) and bStageFront (fascia, house floor and
returns, where the structure has ground; Structure 03 has none). Gary will see
both in capture.

Per target, only portal_piece_count may change, and each portal component must
hold its predicted count (the stage front's boards only as present). Nothing
else changes on any of the six structures, and all six must read current. One
level save. Refuses on dirty state, PIE, ZZ_ actors, or a target whose portal
is already on. Revert: portal_mouths_revert.py. Take Backups/PrePortalMouths-*
(umap) first. Dry run: PORTAL_MOUTHS_DRY_RUN. Lean: all work in main().
"""
import datetime
import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "portal_mouths_revert_record.json")
OUT = os.path.join(HERE, "portal_mouths.json")
TARGETS = ("02", "03", "04", "05", "06")
COUNTS = ("station_count", "cross_beam_count", "rail_segment_count", "board_count", "slot_count", "cloth_count",
          "fixture_body_count", "hanging_line_count", "portal_piece_count", "groove_piece_count")


def fail(message):
    raise RuntimeError(f"PORTAL_MOUTHS_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def state(actor):
    return {"current": bool(actor.is_structure_current()), **{c: int(actor.get_editor_property(c)) for c in COUNTS}}


def predicted_pieces(actor):
    """As portal_enable_apply.py: the portal's components from the actor's own settings."""
    portal = actor.get_editor_property("portal")
    ground = actor.get_editor_property("ground")
    grid = actor.get_editor_property("gridiron")
    half = max(50.0, portal.get_editor_property("opening_half_width_cm"))
    stage_front = bool(portal.get_editor_property("stage_front")) and ground.get_editor_property("enabled")
    timbers = 3
    if portal.get_editor_property("float_trough") and portal.get_editor_property("forestage_depth_cm") > 1.0:
        timbers += 1
    if (portal.get_editor_property("extend_gridiron") and grid.get_editor_property("enabled")
            and actor.get_editor_property("grid_half_width_cm") > 0.0):
        timbers += 3
    if stage_front and portal.get_editor_property("nosing_depth_cm") > 0.5 and portal.get_editor_property("nosing_height_cm") > 0.5:
        timbers += 1
    lanes = 0
    if ground.get_editor_property("enabled"):
        width = max(4.0, ground.get_editor_property("board_width_cm"))
        gap = max(0.0, ground.get_editor_property("board_gap_cm"))
        if stage_front:
            mouth = max(half, portal.get_editor_property("mouth_half_width_cm"))
            lanes = max(1, round((mouth * 2.0 + gap) / (width + gap)))
        else:
            lanes = max(1, math.floor((half * 2.0 + gap) / (width + gap)))
    lines = max(0, int(portal.get_editor_property("hanging_lines")))
    return {"StructurePortal": timbers, "StructureForestage": lanes, "StructurePortalLines": lines,
            "StructureStageFront": "present" if stage_front else 0}


def built_pieces(actor, breakdown):
    comps = [c for c in actor.get_editor_property("managed_components")
             if c and "InfinityStage.Structure.Portal" in [str(t) for t in c.get_editor_property("component_tags")]]
    built = {}
    for c in comps:
        stem = next((k for k in sorted(breakdown, key=len, reverse=True) if c.get_name().startswith(k)), c.get_name())
        built[stem] = built.get(stem, 0) + c.get_instance_count()
    return built, sum(c.get_instance_count() for c in comps)


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
    structures = {a.get_actor_label()[-2:]: a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)}
    if sorted(structures) != ["01", "02", "03", "04", "05", "06"]:
        fail(f"structures: {sorted(structures)}")
    before = {k: state(a) for k, a in structures.items()}
    stale = [k for k, v in before.items() if not v["current"]]
    if stale:
        fail(f"not current before the change: {stale}")
    breakdown = {}
    for k in TARGETS:
        a = structures[k]
        portal = a.get_editor_property("portal")
        if portal.get_editor_property("enabled"):
            fail(f"Structure {k} already has its portal on")
        if before[k]["portal_piece_count"] != 0:
            fail(f"Structure {k} has portal pieces with the portal off")
        if portal.get_editor_property("extend_gridiron") and abs(portal.get_editor_property("offset_from_first_station_cm")) > 2000.0:
            fail(f"Structure {k}: bExtendGridiron with the portal more than 20 m from the first station")
        breakdown[k] = predicted_pieces(a)
    record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "targets": list(TARGETS), "before": before}
    with open(RECORD, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    if json.load(open(RECORD, encoding="utf-8"))["before"] != before:
        fail("revert record did not read back")
    unreal.log(f"PORTAL_MOUTHS_REVERT_RECORD_OK|predicted={breakdown}")
    if globals().get("PORTAL_MOUTHS_DRY_RUN"):
        json.dump({"before": before, "predicted": breakdown}, open(OUT, "w"), indent=1)
        unreal.log("PORTAL_MOUTHS_DRY_RUN_OK|mutated=0")
        return "dry"

    for k in TARGETS:
        a = structures[k]
        a.modify()
        portal = a.get_editor_property("portal")
        portal.set_editor_property("enabled", True)
        a.set_editor_property("portal", portal)
        if not a.materialize_structure():
            fail(f"Structure {k} did not re-fit")
    after = {k: state(a) for k, a in structures.items()}
    problems, built_all = [], {}
    for k, rec in after.items():
        if not rec["current"]:
            problems.append(f"{k} not current")
        for c in COUNTS:
            if k in TARGETS and c == "portal_piece_count":
                continue
            if rec[c] != before[k][c]:
                problems.append(f"{k} {c}: {before[k][c]} -> {rec[c]}")
    for k in TARGETS:
        built, instances = built_pieces(structures[k], breakdown[k])
        built_all[k] = built
        if instances != after[k]["portal_piece_count"]:
            problems.append(f"{k}: portal components hold {instances}, count says {after[k]['portal_piece_count']}")
        for stem, want in breakdown[k].items():
            got = built.get(stem, 0)
            if (want == "present" and got <= 0) or (want != "present" and got != want):
                problems.append(f"{k} {stem}: built {got}, predicted {want}")
        extra = set(built) - set(breakdown[k])
        if extra:
            problems.append(f"{k}: unpredicted portal components {sorted(extra)}")
    json.dump({"before": before, "after": after, "predicted": breakdown, "built": built_all, "problems": problems},
              open(OUT, "w"), indent=1)
    if problems:
        fail(f"unexpected changes, NOT saved: {problems}")
    c1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    m1 = [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    if c1 or m1 != [EXPECTED_WORLD]:
        fail(f"unexpected dirty set before save: {c1} {m1}")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    pieces = {k: after[k]["portal_piece_count"] for k in TARGETS}
    unreal.log(f"PORTAL_MOUTHS_OK|pieces={pieces}|current=6/6|level_saved=1")
    return "applied"


result = main()
