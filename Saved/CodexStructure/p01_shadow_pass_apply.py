"""P01's shadow pass (Gary, 29 Sep night: "Yes, P03's recipe": fill lights shadowless, keys keep
their shadows; conductor, 30 Sep: the largest frame-rate item left, 338 casters).

P01 runs the same nine-slot rig P04 and P06 were derived from, and their established rule is
applied: shadows stay only on the two keys, "Entry Top" and "Entry Fwd +Y". Everything else that
casts now (Cross +-Y, Entry Fwd -Y, Entry High +-Y) goes shadowless, cast_shadows and
cast_volumetric_shadow both. EXEMPT, keeping their shadows:
- "P01 Wing 041 Entry High -Y": the blinking spot Gary liked FOR its shadow (22 cm source);
- "House L" / "House R": the Opening's curtain warmer.
Nothing else changes: intensities, colours, light functions (the flickers stay), positions.
Expected: 338 casters -> 48 x 2 + 1 + 2 = 99.

Edits in place by attachment GUID (P05 reuses cue labels, so labels never identify a pair).
Checks: enabled lights unchanged; casters fall only in P01; every other passage's cues
fingerprinted identical before and after. Then P01 materialized and Structure 01 re-fitted
(housing count unchanged, current). Saves only the Show and the level. Plain record first;
backups of the Show and the level. Dry run: P01_SHADOW_DRY_RUN. Revert: P01_SHADOW_REVERT puts
every recorded flag back by GUID. Lean: all work in main()."""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")
RECORD = os.path.join(HERE, "p01_shadow_pass_record.json")
KEEP_SLOTS = ("Entry Top", "Entry Fwd +Y")
EXEMPT_LABELS = ("P01 Wing 041 Entry High -Y",)
EXEMPT_SLOTS = ("House L", "House R")


def fail(msg):
    unreal.log_error("P01_SHADOW_STOPPED|" + msg)
    raise RuntimeError(msg)


def gid(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def census(show, p01_cues):
    lit = casters = p01_casters = 0
    for cue in show.get_editor_property("cues"):
        if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            continue
        for att in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if att.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT or not att.get_editor_property("enabled"):
                continue
            c = int(bool(att.get_editor_property("lighting").get_editor_property("cast_shadows")))
            lit += 1
            casters += c
            p01_casters += c if gid(cue.get_editor_property("cue_guid")) in p01_cues else 0
    return lit, casters, p01_casters


def fingerprints(show, skip):
    out = {}
    for cue in show.get_editor_property("cues"):
        key = gid(cue.get_editor_property("cue_guid"))
        if key in skip or cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            continue
        rows = []
        for a in cue.get_editor_property("wing_pair").get_editor_property("attachments"):
            if a.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT:
                continue
            L = a.get_editor_property("lighting")
            rows.append([gid(a.get_editor_property("attachment_guid")), bool(a.get_editor_property("enabled")),
                         bool(L.get_editor_property("cast_shadows")), round(float(L.get_editor_property("intensity")), 4)])
        out[key] = json.dumps(rows)
    return out


def main():
    dry, revert = bool(globals().get("P01_SHADOW_DRY_RUN")), bool(globals().get("P01_SHADOW_REVERT"))
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if not world or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD or ed.get_game_world() is not None:
        fail("wrong world, or PIE")
    if unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages() or unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages():
        fail("something is already dirty")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence():
        fail("Sequencer is open")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = sub.get_all_level_actors()
    if any(a.get_actor_label().startswith("ZZ_") for a in actors):
        fail("bench actors (ZZ_) in the level")
    show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
    p01 = next(a for a in actors if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01"))
    s01 = next(a for a in actors if isinstance(a, unreal.InfinityStageStructureActor) and a.get_actor_label().endswith("01"))
    p01_cues = {gid(g) for g in show.get_wing_pair_cue_guids_in_passage(p01.get_editor_property("passage_guid"))}
    cues = list(show.get_editor_property("cues"))
    changes = []            # (cue index, attachment index, guid, label, new flag)
    if revert:
        rec = json.load(open(RECORD, encoding="utf-8"))
        where = {}
        for ci, c in enumerate(cues):
            if c.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
                continue
            for ai, a in enumerate(c.get_editor_property("wing_pair").get_editor_property("attachments")):
                where[gid(a.get_editor_property("attachment_guid"))] = (ci, ai)
        for g, row in rec["rows"].items():
            if g not in where:
                fail(f"recorded attachment {g} ({row['label']}) is not in the Show")
            changes.append((*where[g], g, row["label"], row["before"]))
    else:
        for ci, c in enumerate(cues):
            if gid(c.get_editor_property("cue_guid")) not in p01_cues:
                continue
            for ai, a in enumerate(c.get_editor_property("wing_pair").get_editor_property("attachments")):
                if a.get_editor_property("kind") != unreal.InfinityAttachmentKind.LIGHT or not a.get_editor_property("enabled"):
                    continue
                L = a.get_editor_property("lighting")
                if not L.get_editor_property("cast_shadows"):
                    continue
                label = str(a.get_editor_property("label"))
                slot = label.split(" ", 3)[-1] if label.startswith("P01 Wing ") else label
                if slot in KEEP_SLOTS or label in EXEMPT_LABELS or slot in EXEMPT_SLOTS:
                    continue
                changes.append((ci, ai, gid(a.get_editor_property("attachment_guid")), label,
                                {"cast_shadows": True, "cast_volumetric_shadow": bool(L.get_editor_property("cast_volumetric_shadow"))}))
    lit0, cas0, p01_0 = census(show, p01_cues)
    others0 = fingerprints(show, p01_cues)
    exempt_found = sum(1 for c in cues if gid(c.get_editor_property("cue_guid")) in p01_cues
                       for a in c.get_editor_property("wing_pair").get_editor_property("attachments")
                       if str(a.get_editor_property("label")) in EXEMPT_LABELS and a.get_editor_property("lighting").get_editor_property("cast_shadows"))
    unreal.log(f"P01_SHADOW_PLAN|{'revert' if revert else 'apply'}|changes={len(changes)}|lit={lit0}|casters={cas0}|p01_casters={p01_0}"
               f"|p01_after_expected={p01_0 - len(changes) if not revert else p01_0 + len(changes)}|blink_spot_kept={exempt_found}")
    if not revert and exempt_found != 1:
        fail(f"the blink spot {EXEMPT_LABELS[0]} was not found casting ({exempt_found})")
    if dry:
        unreal.log("P01_SHADOW_DRY_RUN_OK|mutated=0")
        return
    if not revert:
        record = {"written": datetime.datetime.now().isoformat(timespec="seconds"), "casters_before": cas0, "p01_casters_before": p01_0,
                  "rows": {g: {"label": label, "cue_index": ci, "index": ai, "before": before} for ci, ai, g, label, before in changes}}
        with open(RECORD, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        if len(json.load(open(RECORD, encoding="utf-8"))["rows"]) != len(changes):
            fail("revert record did not read back")
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreP01ShadowPass-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
        os.makedirs(backup, exist_ok=True)
        shutil.copy2(os.path.join(project, "Content", *EXPECTED_WORLD[len("/Game/"):].split("/")) + ".umap", backup)
        shutil.copy2(os.path.join(project, "Content", *SHOW_PATH[len("/Game/"):].split("/")) + ".uasset", backup)
        shutil.copy2(RECORD, backup)

    show.modify()
    by_cue = {}
    for ci, ai, g, label, before in changes:
        by_cue.setdefault(ci, []).append((ai, before))
    for ci, rows in by_cue.items():
        cue = cues[ci]
        pair = cue.get_editor_property("wing_pair")
        atts = list(pair.get_editor_property("attachments"))
        for ai, before in rows:
            att = atts[ai]
            L = att.get_editor_property("lighting")
            L.set_editor_property("cast_shadows", bool(before["cast_shadows"]) if revert else False)
            L.set_editor_property("cast_volumetric_shadow", bool(before["cast_volumetric_shadow"]) if revert else False)
            att.set_editor_property("lighting", L)
            atts[ai] = att
        pair.set_editor_property("attachments", atts)
        cue.set_editor_property("wing_pair", pair)
        cues[ci] = cue
    show.set_editor_property("cues", cues)

    lit1, cas1, p01_1 = census(show, p01_cues)
    problems = []
    if lit1 != lit0:
        problems.append(f"enabled lights {lit0} -> {lit1}")
    if (cas0 - cas1) != (p01_0 - p01_1):
        problems.append("casters changed outside P01")
    if fingerprints(show, p01_cues) != others0:
        problems.append("a cue outside P01 changed")
    if abs(p01_1 - p01_0) != len(changes):
        problems.append(f"P01 casters {p01_0} -> {p01_1}, expected a change of {len(changes)}")
    if problems:
        fail(f"Show edit wrong, NOT saved: {problems}")
    housings0 = int(s01.get_editor_property("fixture_body_count"))
    if not p01.materialize_passage():
        fail("Passage 01 did not materialize")
    if not s01.materialize_structure():
        fail("Structure 01 did not re-fit")
    if int(s01.get_editor_property("fixture_body_count")) != housings0 or not s01.is_structure_current():
        fail("Structure 01's housings changed or it is not current")
    c1 = sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    if c1 != [SHOW_PATH]:
        fail(f"out-of-scope dirty content {c1}")
    if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
        fail("Show save failed")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
        fail("level save failed")
    if revert:
        os.replace(RECORD, RECORD + ".reverted")
    after = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()), len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
    unreal.log(f"P01_SHADOW_OK|{'reverted' if revert else 'applied'}|changed={len(changes)}|p01_casters={p01_0}->{p01_1}"
               f"|show_casters={cas0}->{cas1}|lit={lit0}->{lit1}|dirty_after={after[0]}+{after[1]}")


main()
