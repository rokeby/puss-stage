"""6 Oct: s3_sack_livecloth APPLY (S3LIVESACK-20261006-172656) saved the six BP templates with the new sack cloth, then
refused INSTANCE_READBACK: each placed figure carries its own ShoreHeadCloth asset value (an instance override set by
create_pinned_shore_drape.py's c.set_asset on the level actor), so the level still shows CA_ShoreHeadDrape. This sets the
INSTANCE asset to the record's planned cloth on each placed figure (fresh lookup), reads back, saves the map only, and
rewrites the APPLY record as applied (+ instance_asset_override with the old values) so run_revert can restore both.
Marker S3LIVESACK_INSTFIX_OK|run=.."""
import datetime, json, os
import unreal
HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FAILED = HERE + "s3_sack_livecloth_apply_record.json.failed-S3LIVESACK-20261006-172656"
REC = HERE + "s3_sack_livecloth_apply_record.json"
RUN = datetime.datetime.now().strftime("S3LSFIX-%Y%m%d-%H%M%S")


def stop(m):
    unreal.log_error("S3LIVESACK_INSTFIX_FAILED|run=%s|%s" % (RUN, m))
    raise RuntimeError(m)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def main():
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None:
        stop("PIE_ACTIVE")
    if os.path.exists(REC):
        stop("APPLY_RECORD_EXISTS")
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    rec = json.load(open(FAILED, encoding="utf-8"))
    figs = rec["figures"]
    acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    plan = {}
    for f in figs:
        a = [x for x in acts if str(x.get_actor_label()) == f + " Clam"]
        if len(a) != 1:
            stop("ACTOR_COUNT|%s|%d" % (f, len(a)))
        c = [x for x in a[0].get_components_by_class(unreal.ChaosClothComponent) if str(x.get_name()) == "ShoreHeadCloth"]
        if len(c) != 1:
            stop("CLOTH_COUNT|%s|%d" % (f, len(c)))
        new = "/Game/Metahuman/ShoreCast_20260910/Cloth/LiveSack/CA_ShoreSack_%s_v%d" % (f, rec["version"])
        asset = unreal.load_asset(new)
        if asset is None:
            stop("MISSING|" + new)
        old = rec["before"][f]["instance"]["asset"]
        cur = c[0].get_asset().get_path_name().split(".")[0] if c[0].get_asset() else None
        plan[f] = {"old_recorded": old, "current": cur, "new": new}
    unreal.log("S3LIVESACK_INSTFIX_PLAN|run=%s|%s" % (RUN, json.dumps(plan)))
    for f in figs:
        a = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if str(x.get_actor_label()) == f + " Clam"][0]
        c = [x for x in a.get_components_by_class(unreal.ChaosClothComponent) if str(x.get_name()) == "ShoreHeadCloth"][0]
        c.modify()
        c.set_asset(unreal.load_asset(plan[f]["new"]))
    for f in figs:
        a = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if str(x.get_actor_label()) == f + " Clam"][0]
        c = [x for x in a.get_components_by_class(unreal.ChaosClothComponent) if str(x.get_name()) == "ShoreHeadCloth"][0]
        got = c.get_asset().get_path_name().split(".")[0] if c.get_asset() else None
        if got != plan[f]["new"]:
            stop("READBACK|%s|%s|NOTHING SAVED; Don't-Save restart" % (f, got))
    cc = census()
    if cc["content"] or cc["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(cc))
    if not unreal.EditorLoadingAndSavingUtils.save_map(unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY")
    rec["saved"] = True
    rec["instance_asset_override"] = {f: plan[f]["old_recorded"] for f in figs}
    rec["instance_fix_run"] = RUN
    with open(REC, "w", encoding="utf-8") as h:
        json.dump(rec, h, indent=1, default=str)
    os.replace(FAILED, FAILED + ".superseded-" + RUN)
    unreal.log("S3LIVESACK_INSTFIX_OK|run=%s|figures=%d|level_saved=1|record=%s" % (RUN, len(figs), REC))


main()
