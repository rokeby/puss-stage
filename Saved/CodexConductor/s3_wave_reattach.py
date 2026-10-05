"""Fix (Gary 5 Oct: "there are waves in P01"): the 9 "S3 Wave Split" pieces (s3_wave_split_apply.py, 4 Oct) sit inside
P01 at world (3665..5335, -500..500, 115) - exactly their recorded offsets RELATIVE to "S3 Hangar Root". So their
attachment to the root has been lost [measured: probe_waves.json world == record offsets; how it was lost: inferred].

DRY   read-only: per piece, the attach parent, relative and world location; the hidden originals' world locations
      (S3 Wave Row*); where each piece would land if re-attached KEEP_RELATIVE.
APPLY guards (no PIE, clean census) -> umap backup + record (fsync) -> attach each piece to S3 Hangar Root keeping its
      current location values as the RELATIVE offset -> read back -> GATE: every piece now lies inside the originals'
      box grown by 1500 cm in x/y (the beach), else NOTHING SAVED -> census = level only -> save level -> census clean.
      Marker S3_WAVE_REATTACH_APPLY_OK|run=..
Args: s3_wave_reattach_args.json {"mode": "DRY"|"APPLY", "confirm": "APPLY S3WAVES"}.
"""
import datetime
import json
import os
import shutil

import unreal

HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
RUN = datetime.datetime.now().strftime("S3WR-%Y%m%d-%H%M%S")
GROW = 1500.0


def stop(msg):
    unreal.log_error("S3_WAVE_REATTACH_FAILED|run=%s|%s" % (RUN, msg))
    raise RuntimeError(msg)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def v3(v):
    return [round(v.x, 2), round(v.y, 2), round(v.z, 2)]


def main():
    args = json.load(open(HERE + "s3_wave_reattach_args.json", encoding="utf-8"))
    mode = str(args.get("mode", "DRY")).upper()
    if mode == "APPLY" and args.get("confirm") != "APPLY S3WAVES":
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    pieces = sorted([a for a in acts if str(a.get_actor_label()).startswith("S3 Wave Split")],
                    key=lambda a: str(a.get_actor_label()))
    roots = [a for a in acts if str(a.get_actor_label()) == "S3 Hangar Root"]
    origs = [a for a in acts if str(a.get_actor_label()).startswith("S3 Wave Row")]
    if len(pieces) != 9 or len(roots) != 1 or len(origs) != 6:
        stop("COUNTS|pieces=%d|roots=%d|originals=%d" % (len(pieces), len(roots), len(origs)))
    root = roots[0]
    rx = root.get_actor_transform()
    ow = [a.get_actor_location() for a in origs]
    box = (min(p.x for p in ow) - GROW, max(p.x for p in ow) + GROW, min(p.y for p in ow) - GROW, max(p.y for p in ow) + GROW)
    plan = []
    for a in pieces:
        par = a.get_attach_parent_actor()
        rel = a.get_editor_property("root_component").get_relative_transform()
        land = unreal.MathLibrary.transform_location(rx, rel.translation)
        plan.append({"label": str(a.get_actor_label()), "parent": par.get_actor_label() if par else None,
                     "relative": v3(rel.translation), "world": v3(a.get_actor_location()), "would_land": v3(land),
                     "lands_on_beach": box[0] <= land.x <= box[1] and box[2] <= land.y <= box[3]})
    rep = {"run": RUN, "root_world": v3(rx.translation), "root_rot": str(rx.rotation.rotator()),
           "originals_box_grown": box, "plan": plan}
    for r in plan:
        unreal.log("S3_WAVE_REATTACH_ROW|run=%s|%s" % (RUN, json.dumps(r)))
    if mode == "DRY":
        unreal.log("S3_WAVE_REATTACH_DRY_OK|run=%s|root=%s|detached=%d|all_land_on_beach=%s"
                   % (RUN, v3(rx.translation), sum(r["parent"] is None for r in plan), all(r["lands_on_beach"] for r in plan)))
        json.dump(rep, open(HERE + "s3_wave_reattach_dry_%s.json" % RUN, "w", encoding="utf-8"), indent=1)
        return
    if any(r["parent"] is not None for r in plan):
        stop("SOME_STILL_ATTACHED|%s" % [r["label"] for r in plan if r["parent"] is not None])
    if not all(r["lands_on_beach"] for r in plan):
        stop("WOULD_NOT_LAND_ON_BEACH")
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    backup = "E:/PussStage/Backups/PreS3WaveReattach-" + RUN
    os.makedirs(backup)
    with open(HERE + "s3_wave_reattach_record.json", "w", encoding="utf-8") as h:
        json.dump(dict(rep, backup=backup), h, indent=1)
        h.flush()
        os.fsync(h.fileno())
    shutil.copy2(UMAP, backup)
    for a in pieces:
        rel = a.get_editor_property("root_component").get_relative_transform()
        a.modify()
        a.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE,
                          unreal.AttachmentRule.KEEP_RELATIVE, False)
        after = a.get_editor_property("root_component").get_relative_transform().translation
        if a.get_attach_parent_actor() != root or v3(after) != v3(rel.translation):
            stop("ATTACH_READBACK|%s|NOTHING SAVED; Don't-Save restart" % a.get_actor_label())
        w = a.get_actor_location()
        if not (box[0] <= w.x <= box[1] and box[2] <= w.y <= box[3]):
            stop("NOT_ON_BEACH_AFTER|%s|%s|NOTHING SAVED; Don't-Save restart" % (a.get_actor_label(), v3(w)))
    dirty = census()
    if dirty["content"] or dirty["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(dirty))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY|" + json.dumps(census()))
    unreal.log("S3_WAVE_REATTACH_APPLY_OK|run=%s|pieces=9|backup=%s|level_saved=1|dirty_after=0+0" % (RUN, backup))


main()
