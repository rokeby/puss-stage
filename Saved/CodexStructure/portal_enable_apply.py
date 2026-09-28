"""Step 3a: switch the portal on for Structure 01 (Passage 01) and re-fit it, saving
the level only. Gary approved the portal in the Rig & atmosphere session
(28 Sep, "go ahead"); run inside a conductor-granted level slot, AFTER
structure_refit_all.py (all six must already read current) and after a
Backups/PrePortal-* umap snapshot. portal_enable_revert.py undoes it.

The portal (68057a2) is built from the gridiron's timber: two posts framing the
curtain, a header, the gridiron carried forward, a forestage with a float trough
at its lip, and hemp lines from the header. Every piece is counted in
PortalPieceCount, so the guard is exact: on Structure 01 only portal_piece_count
may change (0 -> the predicted count), and nothing on the other five changes at
all. Refuses on any dirty state or stray ZZ_ actor. A read-only rehearsal: set
PORTAL_ENABLE_DRY_RUN via runpy (portal_enable_dryrun.py).
"""
import datetime
import json
import math
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "portal_enable_revert_record.json")
OUT = os.path.join(HERE, "portal_enable.json")
# None keeps the C++ default (150). Set it only from the chosen bake's all-frame
# downstage extent: p01_lip_floats_plan_readonly.py names the depth it needs.
FORESTAGE_DEPTH_CM = None
COUNTS = ("station_count", "cross_beam_count", "rail_segment_count", "board_count", "slot_count",
          "cloth_count", "fixture_body_count", "hanging_line_count", "portal_piece_count")


def fail(message):
    raise RuntimeError(f"PORTAL_ENABLE_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def dirty():
    return ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def state(actor):
    return {"current": bool(actor.is_structure_current()),
            **{c: int(actor.get_editor_property(c)) for c in COUNTS}}


def predicted_pieces(actor):
    """PortalPieceCount as BuildPortal will make it, from the actor's own settings."""
    portal = actor.get_editor_property("portal")
    ground = actor.get_editor_property("ground")
    grid = actor.get_editor_property("gridiron")
    half = max(50.0, portal.get_editor_property("opening_half_width_cm"))
    timbers = 3                                                   # two posts and a header
    breakdown = {"frame": 3}
    if portal.get_editor_property("float_trough") and portal.get_editor_property("forestage_depth_cm") > 1.0:
        timbers += 1
        breakdown["trough"] = 1
    if (portal.get_editor_property("extend_gridiron") and grid.get_editor_property("enabled")
            and actor.get_editor_property("grid_half_width_cm") > 0.0):
        timbers += 3                                              # a cross beam and two rails
        breakdown["grid_forward"] = 3
    # The forestage covers only floor the ground layer does not (see BuildPortal).
    lanes = 0
    if ground.get_editor_property("enabled"):
        width = max(4.0, ground.get_editor_property("board_width_cm"))
        gap = max(0.0, ground.get_editor_property("board_gap_cm"))
        lanes = max(1, math.floor((half * 2.0 + gap) / (width + gap)))
    breakdown["forestage_lanes_if_any"] = lanes
    lines = max(0, int(portal.get_editor_property("hanging_lines")))
    breakdown["lines"] = lines
    return timbers, lanes, lines, breakdown


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    fail("wrong project or world")
if ed.get_game_world() is not None:
    fail("PIE active")
if not hasattr(unreal, "InfinityStagePortalSettings"):
    fail("the loaded plugin predates the 28 Sep build (no portal settings) - stale binaries")
content0, maps0 = dirty()
if content0 or maps0:
    fail(f"editor already dirty: {content0} {maps0}")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()
if any(a.get_actor_label().startswith("ZZ_") for a in actors):
    fail("stray ZZ_ actors in the level")

structures = sorted((a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)),
                    key=lambda a: a.get_actor_label())
if len(structures) != 6:
    fail(f"expected 6 structure actors, found {len(structures)}")
passage = next((a for a in actors if isinstance(a, unreal.InfinityStagePassageActor)
                and a.get_actor_label().startswith("Passage 01")), None)
if passage is None:
    fail("no Passage 01")
targets = [a for a in structures if a.get_editor_property("passage") == passage]
if len(targets) != 1:
    fail(f"expected one structure on Passage 01, found {len(targets)}")
target = targets[0]
before = {a.get_actor_label(): state(a) for a in structures}
stale = [label for label, rec in before.items() if not rec["current"]]
if stale:
    fail(f"not current, run structure_refit_all.py first: {stale}")
if target.get_editor_property("portal").get_editor_property("enabled"):
    fail(f"{target.get_actor_label()} already has its portal on")
if before[target.get_actor_label()]["portal_piece_count"] != 0:
    fail(f"{target.get_actor_label()} has portal pieces with the portal off")
timbers, lanes, lines, breakdown = predicted_pieces(target)

# ---- Revert record: on disk, flushed and re-read before anything changes ----
record = {"written": datetime.datetime.now().isoformat(timespec="seconds"),
          "structure": target.get_actor_label(), "portal_enabled_before": False, "before": before,
          "forestage_depth_before": target.get_editor_property("portal").get_editor_property("forestage_depth_cm")}
with open(RECORD, "w", encoding="utf-8") as fh:
    json.dump(record, fh, indent=1)
    fh.flush()
    os.fsync(fh.fileno())
if json.load(open(RECORD, encoding="utf-8"))["before"] != before:
    fail("revert record did not read back complete")
unreal.log(f"PORTAL_ENABLE_REVERT_RECORD_OK|structure={target.get_actor_label()}|predicted={breakdown}")

if globals().get("PORTAL_ENABLE_DRY_RUN"):
    json.dump({"before": before, "structure": target.get_actor_label(), "predicted": breakdown},
              open(OUT, "w"), indent=1)
    unreal.log(f"PORTAL_ENABLE_DRY_RUN_OK|structure={target.get_actor_label()}|current_before="
               f"{sum(v['current'] for v in before.values())}/6|mutated=0")
    raise RuntimeError("PORTAL_ENABLE_DRY_RUN_COMPLETE")

# ---- Mutate -----------------------------------------------------------------
target.modify()
portal = target.get_editor_property("portal")
portal.set_editor_property("enabled", True)
if FORESTAGE_DEPTH_CM is not None:
    portal.set_editor_property("forestage_depth_cm", float(FORESTAGE_DEPTH_CM))
target.set_editor_property("portal", portal)
if not target.get_editor_property("portal").get_editor_property("enabled"):
    fail("Portal.bEnabled did not take")
if not target.materialize_structure():
    fail(f"{target.get_actor_label()} did not re-fit")

# ---- Verify before any save ---------------------------------------------------
after = {a.get_actor_label(): state(a) for a in structures}
problems = []
for label, rec in after.items():
    if not rec["current"]:
        problems.append(f"{label} not current after the change")
    for c in COUNTS:
        if label == target.get_actor_label() and c == "portal_piece_count":
            continue
        if rec[c] != before[label][c]:
            problems.append(f"{label} {c}: {before[label][c]} -> {rec[c]}")
pieces = after[target.get_actor_label()]["portal_piece_count"]
# The forestage exists only where the ground layer leaves floor uncovered, which
# the plan puts at 150 cm for P01 (its ground starts at the route start); allow
# either, but nothing else.
allowed = {timbers + lanes + lines, timbers + lines}
if pieces not in allowed:
    problems.append(f"portal_piece_count {pieces}, predicted {sorted(allowed)} ({breakdown})")
portal_components = [c for c in target.get_editor_property("managed_components")
                     if c and "InfinityStage.Structure.Portal" in [str(t) for t in c.get_editor_property("component_tags")]]
instances = sum(c.get_instance_count() for c in portal_components)
if instances != pieces:
    problems.append(f"portal components hold {instances} instances, count says {pieces}")
json.dump({"before": before, "after": after, "predicted": breakdown, "portal_instances": instances,
           "problems": problems}, open(OUT, "w"), indent=1)
if problems:
    fail(f"unexpected changes, NOT saved: {problems}")
content1, maps1 = dirty()
if content1 or maps1 != [EXPECTED_WORLD]:
    fail(f"unexpected dirty set before save: {content1} {maps1}")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
content2, maps2 = dirty()
unreal.log(f"PORTAL_ENABLE_OK|structure={target.get_actor_label()}|portal_pieces={pieces}|breakdown={breakdown}"
           f"|forestage_cm={target.get_editor_property('portal').get_editor_property('forestage_depth_cm'):.0f}"
           f"|current={sum(v['current'] for v in after.values())}/6|level_saved=1|dirty_after={len(content2)}+{len(maps2)}")
