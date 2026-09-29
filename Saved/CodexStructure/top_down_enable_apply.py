"""Gary, 29 Sep: enable "Top Down", shadows OFF. The 261 attachments whose label
ends "Top Down" (all six passages, all currently disabled, all with shadows on)
become enabled, with cast_shadows and cast_volumetric_shadow off; nothing else
changes. Then materialize every passage, re-fit every structure (each lit lamp
gets a housing, so the fixture signature changes), and save the Show and the
level only.

Proof that no shadow caster moved: the enabled-caster count across the Show
must be identical before and after (1643 when surveyed), with enabled lights
+261. Take a Backups/PreTopDown-* snapshot (Show + umap) first. The revert record
holds each attachment's GUID and flags; top_down_enable_revert.py restores
them. Refuses on any dirty state or bench actor. Rehearse with TOP_DOWN_DRY_RUN.
"""
import datetime
import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "top_down_enable_revert_record.json")
EXPECTED_COUNT = 261
COUNTS = ("station_count", "cross_beam_count", "rail_segment_count", "board_count", "slot_count",
          "fixture_body_count", "hanging_line_count", "portal_piece_count")


def fail(message):
    raise RuntimeError(f"TOP_DOWN_ENABLE_FAILED|{message}")


def pk(p):
    s = str(p)
    return s.split("'")[1].split(".")[0] if "'" in s else s


def dirty():
    return ([pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
            [pk(p) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def census(show):
    lit = casters = 0
    for cue in show.get_editor_property("cues"):
        if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            continue
        for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if att.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT and att.get_editor_property("enabled"):
                lit += 1
                casters += int(bool(att.get_editor_property("lighting").get_editor_property("cast_shadows")))
    return lit, casters


ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = ed.get_editor_world()
if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
    fail("wrong world, or PIE active")
c0, m0 = dirty()
if c0 or m0:
    fail(f"editor already dirty: {c0} {m0}")
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = sub.get_all_level_actors()
if any(a.get_actor_label().startswith(("ZZ_", "TEMP", "Temp")) for a in actors):
    fail("bench actors in the level")
show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
cues = list(show.get_editor_property("cues"))
targets = []
for ci, cue in enumerate(cues):
    if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
        continue
    for ai, att in enumerate(cue.get_editor_property("wing_pair").get_editor_property("attachments")):
        if str(att.get_editor_property("label")).endswith("Top Down") \
                and att.get_editor_property("kind") == unreal.InfinityAttachmentKind.LIGHT:
            L = att.get_editor_property("lighting")
            targets.append({"cue": ci, "att": ai, "guid": gs(att.get_editor_property("attachment_guid")),
                            "label": str(att.get_editor_property("label")),
                            "enabled": bool(att.get_editor_property("enabled")),
                            "cast_shadows": bool(L.get_editor_property("cast_shadows")),
                            "cast_volumetric_shadow": bool(L.get_editor_property("cast_volumetric_shadow"))})
if len(targets) != EXPECTED_COUNT:
    fail(f"{len(targets)} Top Down lights, expected {EXPECTED_COUNT}")
if any(t["enabled"] for t in targets):
    fail("some Top Down lights are already enabled; survey again before changing anything")
lit0, casters0 = census(show)
structures = sorted((a for a in actors if isinstance(a, unreal.InfinityStageStructureActor)), key=lambda a: a.get_actor_label())
before = {a.get_actor_label(): {"current": bool(a.is_structure_current()), **{c: int(a.get_editor_property(c)) for c in COUNTS}}
          for a in structures}
if not all(v["current"] for v in before.values()):
    fail(f"structures not current before the change: {[k for k, v in before.items() if not v['current']]}")

record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "targets": targets,
          "lit_before": lit0, "casters_before": casters0, "structures_before": before}
with open(RECORD, "w", encoding="utf-8") as fh:
    json.dump(record, fh, indent=1)
    fh.flush()
    os.fsync(fh.fileno())
if len(json.load(open(RECORD, encoding="utf-8"))["targets"]) != EXPECTED_COUNT:
    fail("revert record did not read back")
unreal.log(f"TOP_DOWN_REVERT_RECORD_OK|targets={len(targets)}|lit_before={lit0}|casters_before={casters0}")
if globals().get("TOP_DOWN_DRY_RUN"):
    unreal.log("TOP_DOWN_DRY_RUN_OK|mutated=0")
    raise RuntimeError("TOP_DOWN_DRY_RUN_COMPLETE")

show.modify()
by_cue = {}
for t in targets:
    by_cue.setdefault(t["cue"], set()).add(t["att"])
for ci, indices in by_cue.items():
    cue = cues[ci]
    pair = cue.get_editor_property("wing_pair")
    atts = list(pair.get_editor_property("attachments"))
    for ai in indices:
        att = atts[ai]
        L = att.get_editor_property("lighting")
        L.set_editor_property("cast_shadows", False)
        L.set_editor_property("cast_volumetric_shadow", False)
        att.set_editor_property("lighting", L)
        att.set_editor_property("enabled", True)
        atts[ai] = att
    pair.set_editor_property("attachments", atts)
    cue.set_editor_property("wing_pair", pair)
    cues[ci] = cue
show.set_editor_property("cues", cues)

lit1, casters1 = census(show)
problems = []
if casters1 != casters0:
    problems.append(f"enabled shadow casters {casters0} -> {casters1}")
if lit1 != lit0 + EXPECTED_COUNT:
    problems.append(f"enabled lights {lit0} -> {lit1}, want +{EXPECTED_COUNT}")
check = {t["guid"] for t in targets}
seen = 0
for cue in show.get_editor_property("cues"):
    if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
        continue
    for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
        if gs(att.get_editor_property("attachment_guid")) in check:
            seen += 1
            L = att.get_editor_property("lighting")
            if not att.get_editor_property("enabled") or L.get_editor_property("cast_shadows") \
                    or L.get_editor_property("cast_volumetric_shadow"):
                problems.append(f"{att.get_editor_property('label')} not enabled shadowless")
if seen != EXPECTED_COUNT:
    problems.append(f"found {seen} of the targeted GUIDs after the edit")
if problems:
    fail(f"Show edit wrong, NOT saved: {problems}")

for p in (a for a in actors if isinstance(a, unreal.InfinityStagePassageActor)):
    if not p.materialize_passage():
        fail(f"{p.get_actor_label()} did not materialize")
after = {}
for a in structures:
    if not a.materialize_structure():
        fail(f"{a.get_actor_label()} did not re-fit")
    after[a.get_actor_label()] = {"current": bool(a.is_structure_current()), **{c: int(a.get_editor_property(c)) for c in COUNTS}}
for label, rec in after.items():
    if not rec["current"]:
        problems.append(f"{label} not current")
    for c in COUNTS:
        if c in ("fixture_body_count", "hanging_line_count"):
            continue
        if rec[c] != before[label][c]:
            problems.append(f"{label} {c}: {before[label][c]} -> {rec[c]}")
added = sum(after[k]["fixture_body_count"] - before[k]["fixture_body_count"] for k in after)
if added != EXPECTED_COUNT:
    problems.append(f"housings added {added}, want {EXPECTED_COUNT}")
c1, m1 = dirty()
if set(c1) - {SHOW_PATH} or set(m1) - {EXPECTED_WORLD}:
    problems.append(f"out-of-scope dirty: {c1} {m1}")
json.dump({**record, "lit_after": lit1, "casters_after": casters1, "structures_after": after, "problems": problems},
          open(os.path.join(HERE, "top_down_enable.json"), "w"), indent=1)
if problems:
    fail(f"NOT saved: {problems}")
if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
    fail("Show save failed")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    fail("level save failed")
c2, m2 = dirty()
unreal.log(f"TOP_DOWN_ENABLE_OK|enabled={EXPECTED_COUNT}|shadows=off|casters={casters0}->{casters1}|lit={lit0}->{lit1}"
           f"|housings=+{added}|lines={sum(v['hanging_line_count'] for v in before.values())}->{sum(v['hanging_line_count'] for v in after.values())}"
           f"|show_saved=1|level_saved=1|dirty_after={len(c2)}+{len(m2)}")
