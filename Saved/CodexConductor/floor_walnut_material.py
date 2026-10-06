"""Gary 6 Oct: "P03 still has old floor? Needs walnut". MATERIAL-ONLY swap (boards untouched: Ground-off blanks the Fixtures
and Gridiron layers, p03_floor stopped 01:47) on the P02/P03 floor slabs: every material slot -> the walnut herringbone,
set explicitly (P01's slab is DarkWet now, so nothing is copied). Record old materials first, umap backup, read back,
census = level only, save the level. Args floor_walnut_material_args.json {"mode": "DRY"|"APPLY"|"REVERT",
"confirm": "<MODE> WALNUT"}. Marker FLOOR_WALNUT_<MODE>_OK|run=.."""
import datetime, json, os, shutil
import unreal
HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
REC = HERE + "floor_walnut_material_record.json"
WALNUT = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/M_Walnut_Hrrngbn_02_Mat_Inst_Dup.M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
LABELS = ["Passage 02 - Floor Near", "Passage 02 - Floor Left", "Passage 02 - Floor Right", "Passage 02 - Floor Far",
          "Passage 03 - Floor"]
RUN = datetime.datetime.now().strftime("WALNUT-%Y%m%d-%H%M%S")


def stop(m):
    unreal.log_error("FLOOR_WALNUT_FAILED|run=%s|%s" % (RUN, m))
    raise RuntimeError(m)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def mats(comp):
    return [m.get_path_name() if m else None for m in comp.get_materials()]


def main():
    a = json.load(open(HERE + "floor_walnut_material_args.json", encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    if mode != "DRY" and a.get("confirm") != "%s WALNUT" % mode:
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    found = {}
    for lab in LABELS:
        hits = [x for x in acts if str(x.get_actor_label()) == lab]
        if len(hits) != 1:
            stop("COUNT|%s|%d" % (lab, len(hits)))
        found[lab] = hits[0].get_component_by_class(unreal.StaticMeshComponent)
    before = {lab: mats(c) for lab, c in found.items()}
    unreal.log("FLOOR_WALNUT_PLAN|run=%s|before=%s" % (RUN, json.dumps(before)))
    walnut = unreal.load_asset(WALNUT)
    if walnut is None:
        stop("WALNUT_MISSING")
    if mode == "DRY":
        unreal.log("FLOOR_WALNUT_DRY_OK|run=%s|slabs=%d" % (RUN, len(found)))
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    if mode == "APPLY":
        if os.path.exists(REC):
            stop("RECORD_EXISTS")
        backup = "E:/PussStage/Backups/PreFloorWalnut-" + RUN
        os.makedirs(backup)
        shutil.copy2(UMAP, backup)
        with open(REC, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "before": before, "backup": backup}, h, indent=1)
            h.flush(); os.fsync(h.fileno())
        want = {lab: [WALNUT] * len(before[lab]) for lab in before}
    else:
        if not os.path.exists(REC):
            stop("NO_RECORD")
        want = json.load(open(REC, encoding="utf-8"))["before"]
    for lab, c in found.items():
        c.get_owner().modify()
        for i, p in enumerate(want[lab]):
            c.set_material(i, unreal.load_asset(p) if p else None)
    got = {lab: mats(c) for lab, c in found.items()}
    if got != want:
        stop("READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(got))
    cc = census()
    if cc["content"] or cc["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(cc))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY")
    if mode == "REVERT":
        os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("FLOOR_WALNUT_%s_OK|run=%s|slabs=%d|level_saved=1" % (mode, RUN, len(found)))


main()
