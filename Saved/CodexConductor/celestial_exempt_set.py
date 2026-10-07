"""Set InfinityStageCelestialRig.ForeignLightingExemptLevels to Klara's three levels (Gary 7 Oct: her lighting in her
scenes; CE patch e0e04ed). Record before -> backup umap -> set -> read back -> save level only -> census clean.
Marker CELESTIAL_EXEMPT_OK|run=..  REVERT: set CELESTIAL_EXEMPT_REVERT=True in a runner (restores the recorded list)."""
import datetime, json, os, shutil
import unreal
RUN = datetime.datetime.now().strftime("CEX-%Y%m%d-%H%M%S")
HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "celestial_exempt_record.json"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LEVELS = ["/Game/KK_S1_Animals/L_Animals", "/Game/L_KK_children", "/Game/Japanese_Alley/Maps/Japanese_Alley"]
def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}
def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("CELESTIAL_EXEMPT_FAILED|PIE")
    if census() != {"content": [], "maps": []}: raise RuntimeError("CELESTIAL_EXEMPT_FAILED|DIRTY|%s" % census())
    rigs = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if a.get_class().get_name() == "InfinityStageCelestialRig"]
    if len(rigs) != 1: raise RuntimeError("CELESTIAL_EXEMPT_FAILED|RIG_COUNT|%d" % len(rigs))
    rig = rigs[0]
    before = [str(x) for x in rig.get_editor_property("foreign_lighting_exempt_levels")]
    revert = bool(globals().get("CELESTIAL_EXEMPT_REVERT"))
    if revert:
        want = json.load(open(REC, encoding="utf-8"))["before"]
    else:
        if os.path.exists(REC): raise RuntimeError("CELESTIAL_EXEMPT_FAILED|RECORD_EXISTS")
        bk = "E:/PussStage/Backups/PreCelestialExempt-" + RUN; os.makedirs(bk); shutil.copy2(UMAP, bk)
        with open(REC, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "before": before, "backup": bk, "decided_by": "Gary 7 Oct: Klara's lighting in her scenes"}, h, indent=1); h.flush(); os.fsync(h.fileno())
        want = LEVELS
    rig.modify()
    rig.set_editor_property("foreign_lighting_exempt_levels", [unreal.SoftObjectPath(p if "." in p.split("/")[-1] else p + "." + p.split("/")[-1]) for p in want] if False else [unreal.load_asset(p) for p in want])
    got = [str(x) for x in rig.get_editor_property("foreign_lighting_exempt_levels")]
    unreal.log("CELESTIAL_EXEMPT_READBACK|run=%s|%s" % (RUN, got))
    if len(got) != len(want) or any(w.split("/")[-1] not in g for w, g in zip(want, got)):
        raise RuntimeError("CELESTIAL_EXEMPT_FAILED|READBACK|%s|NOTHING SAVED; Don't-Save restart" % got)
    c = census()
    if c["content"] or c["maps"] != [WORLD]: raise RuntimeError("CELESTIAL_EXEMPT_FAILED|SCOPE|%s" % c)
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD): raise RuntimeError("CELESTIAL_EXEMPT_FAILED|SAVE")
    if census() != {"content": [], "maps": []}: raise RuntimeError("CELESTIAL_EXEMPT_FAILED|DIRTY_AFTER")
    if revert: os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("CELESTIAL_EXEMPT_%s|run=%s|before=%s|after=%s" % ("REVERT_OK" if revert else "OK", RUN, before, got))
main()
