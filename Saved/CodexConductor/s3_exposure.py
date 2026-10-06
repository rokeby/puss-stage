"""Gary 6 Oct: S3 "feels that exposure or daylight is too bright" (keep the marble wet, glossy, bright). Adjust ONLY the
pinned exposure of the "S3 Hangar Pinned Exposure" post-process volume: Min = Max EV100 (+ optional bias), recorded and
revertible; level-only save. Higher EV100 = darker (one stop per 1.0).
Args s3_exposure_args.json {"mode": "DRY"|"APPLY"|"REVERT", "confirm": "<MODE> S3EXPOSURE", "ev100": 3.0}.
Marker S3_EXPOSURE_<MODE>_OK|run=.."""
import datetime, json, os, shutil
import unreal
HERE = "E:/PussStage/Saved/CodexConductor/"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = "E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
LABEL = "S3 Hangar Pinned Exposure"
REC = HERE + "s3_exposure_record.json"
FIELDS = ("auto_exposure_min_brightness", "auto_exposure_max_brightness", "auto_exposure_bias",
          "override_auto_exposure_min_brightness", "override_auto_exposure_max_brightness", "override_auto_exposure_bias",
          "auto_exposure_method", "override_auto_exposure_method")
RUN = datetime.datetime.now().strftime("S3EXP-%Y%m%d-%H%M%S")


def stop(m):
    unreal.log_error("S3_EXPOSURE_FAILED|run=%s|%s" % (RUN, m))
    raise RuntimeError(m)


def census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_name() for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_name() for p in lib.get_dirty_map_packages())}


def read(s):
    out = {}
    for f in FIELDS:
        try:
            v = s.get_editor_property(f)
            out[f] = v if isinstance(v, (bool, int, float)) else str(v)
        except Exception as e:  # noqa: BLE001
            out[f] = "ERR %s" % e
    return out


def main():
    a = json.load(open(HERE + "s3_exposure_args.json", encoding="utf-8"))
    mode = str(a.get("mode", "DRY")).upper()
    if mode != "DRY" and a.get("confirm") != "%s S3EXPOSURE" % mode:
        stop("CONFIRM_MISSING")
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        stop("PIE_ACTIVE")
    hits = [x for x in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            if str(x.get_actor_label()) == LABEL]
    if len(hits) != 1:
        stop("COUNT|%d" % len(hits))
    ppv = hits[0]
    s = ppv.get_editor_property("settings")
    before = read(s)
    unreal.log("S3_EXPOSURE_READ|run=%s|%s" % (RUN, json.dumps(before)))
    if mode == "DRY":
        unreal.log("S3_EXPOSURE_DRY_OK|run=%s" % RUN)
        return
    if census() != {"content": [], "maps": []}:
        stop("DIRTY_BEFORE|" + json.dumps(census()))
    if mode == "APPLY":
        if os.path.exists(REC):
            stop("RECORD_EXISTS (REVERT first, or edit ev100 via REVERT+APPLY)")
        ev = float(a["ev100"])
        backup = "E:/PussStage/Backups/PreS3Exposure-" + RUN
        os.makedirs(backup)
        shutil.copy2(UMAP, backup)
        with open(REC, "w", encoding="utf-8") as h:
            json.dump({"run": RUN, "before": before, "ev100": ev, "backup": backup}, h, indent=1)
            h.flush(); os.fsync(h.fileno())
        want = {"auto_exposure_min_brightness": ev, "auto_exposure_max_brightness": ev,
                "override_auto_exposure_min_brightness": True, "override_auto_exposure_max_brightness": True}
    else:
        if not os.path.exists(REC):
            stop("NO_RECORD")
        b = json.load(open(REC, encoding="utf-8"))["before"]
        want = {k: b[k] for k in ("auto_exposure_min_brightness", "auto_exposure_max_brightness",
                                  "override_auto_exposure_min_brightness", "override_auto_exposure_max_brightness")}
    ppv.modify()
    for k, v in want.items():
        s.set_editor_property(k, v)
    ppv.set_editor_property("settings", s)
    got = read(ppv.get_editor_property("settings"))
    bad = {k: (got[k], v) for k, v in want.items() if (abs(float(got[k]) - float(v)) > 1e-4 if isinstance(v, float) else got[k] != v)}
    if bad:
        stop("READBACK|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(bad))
    c = census()
    if c["content"] or c["maps"] != [WORLD]:
        stop("DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(c))
    if not unreal.EditorLoadingAndSavingUtils.save_map(ed.get_editor_world(), WORLD):
        stop("SAVE_FAILED")
    if census() != {"content": [], "maps": []}:
        stop("POST_SAVE_DIRTY")
    if mode == "REVERT":
        os.replace(REC, REC + ".reverted-" + RUN)
    unreal.log("S3_EXPOSURE_%s_OK|run=%s|now=%s" % (mode, RUN, json.dumps(got)))


main()
