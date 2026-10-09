"""S2 EXIT WALL HIDE (Gary 9 Oct, recording 'S2 and shadow i2 transitoin.mp4' at 2:37: "there seems to be a huge black wall
that spawns ... Is it the back wall of the hangar box? Probably easiest to solve by disappearing it").
[meas, PIE screen-find 9 Oct 01:40 at S2 0.94]: the exit camera looks at "S2 Hangar Far Wall Above Exit" (+ its Left/Right/
Below pieces and door actors) at the S2 end.  Hides every actor whose label starts with one of PREFIXES over [FROM, END]
in LS_DevScene_02 with a bHidden visibility track (channel = VISIBLE, rule 9).  Existing bindings are reused (add_possessable
returns them, so no rename); a new binding gets display name "S2 Exit Wall Hide: <label>".
Record + backup; REVERT exact.  Args s2_exit_wall_hide_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S2WALLHIDE"}.
Markers S2WALLHIDE_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/KlaraIngest/"
REC = HERE + "s2_exit_wall_hide_record.json"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_02"
SCENE_FILE = "E:/PussStage/Content/InfinityStage/Dev/Sequences/LS_DevScene_02.uasset"
PREFIXES = ("S2 Hangar Far Wall", "S2 Hangar Exit", "S2 Exit")
FROM, END = 3300, 3891
PREFIX = "S2 Exit Wall Hide: "


def main():
    import unreal
    a = json.load(open(HERE + "s2_exit_wall_hide_args.json")); mode = a["mode"]
    run = datetime.datetime.now().strftime("S2WALLHIDE-%Y%m%d-%H%M%S")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    acts = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if str(x.get_actor_label()).startswith(PREFIXES) and "Block" not in str(x.get_actor_label())]
    labels = sorted(str(x.get_actor_label()) for x in acts)
    if mode == "DRY":
        unreal.log("S2WALLHIDE_DRY_OK|n=%d|labels=%s|range=[%d,%d]" % (len(labels), labels, FROM, END)); return
    if a.get("confirm") != "%s S2WALLHIDE" % mode: raise RuntimeError("CONFIRM")
    seq = unreal.load_asset(SCENE)
    bd = "E:/PussStage/Backups/PreS2WallHide-%s" % run; os.makedirs(bd); shutil.copy2(SCENE_FILE, bd)
    if mode == "APPLY":
        if os.path.exists(REC) or not acts: raise RuntimeError("PRECONDITION|n=%d" % len(acts))
        rec = {"run": run, "backup": bd, "rows": []}
        for x in acts:
            before = {str(b.get_id().export_text()): str(b.get_display_name()) for b in seq.get_bindings()}
            b = seq.add_possessable(x)
            gid = b.get_id().export_text(); reused = gid in before
            if not reused: b.set_display_name(PREFIX + str(x.get_actor_label()))
            t = b.add_track(unreal.MovieSceneVisibilityTrack); t.set_property_name_and_path("bHidden", "bHidden")
            s = t.add_section(); s.set_range(FROM, END); s.set_completion_mode(unreal.MovieSceneCompletionMode.RESTORE_STATE)
            list(s.get_all_channels())[0].set_default(False)                        # visible=False -> hidden
            if str(t.get_property_name()) != "bHidden": raise RuntimeError("READBACK_PROP|NOTHING SAVED; Don't-Save restart")
            rec["rows"].append({"label": str(x.get_actor_label()), "binding": gid, "reused": reused,
                                "name_before": before.get(gid), "track": str(t.get_name())})
        json.dump(rec, open(REC, "w"), indent=1)
    elif mode == "REVERT":
        rec = json.load(open(REC))
        by = {b.get_id().export_text(): b for b in seq.get_bindings()}
        for r in rec["rows"]:
            b = by.get(r["binding"])
            if b is None: continue
            if r["reused"]:
                for t in list(b.get_tracks()):
                    if str(t.get_name()) == r["track"]: b.remove_track(t)
            else:
                b.remove()
    else:
        raise RuntimeError("MODE")
    if census() != ([SCENE], []): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(SCENE, only_if_is_dirty=False) or census() != ([], []): raise RuntimeError("SAVE")
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S2WALLHIDE_%s_OK|run=%s|n=%d|backup=%s" % (mode, run, len(acts), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S2WALLHIDE_FAILED|%r" % (exc,))
