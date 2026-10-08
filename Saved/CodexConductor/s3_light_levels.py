"""S3 light levels from chat (Gary 7 Oct: "switch lights on and off from here").

The S3 hangar lights are KEYED in LS_S3_HangarRise (fade/strike keys, probe_s3_light_keys.json), so an editor-side
intensity change is overridden in PIE.  This tool sets a group's LIT level in both places:
  * every NONZERO Intensity key of the group's tracks in LS_S3_HangarRise -> target (zero keys stay zero: the fade
    and strike timing is untouched);
  * the editor actor's LightComponent intensity -> target (so the viewport matches).  The MAP IS NOT SAVED here:
    it stays dirty for Gary's own save (he is working in the level).  Only the rise asset is saved.
Groups = actor-label prefix after "S3 " (e.g. "Lattice Glow", "Uplight", "Practical L").
Args s3_light_levels_args.json {"mode":"DRY"|"APPLY"|"REVERT","run":"..","set":{"Lattice Glow":1.0}}.
Every APPLY writes s3_light_levels_record_<run>.json (before values) + Backups/PreS3LightLevels-<run>/ first;
REVERT takes {"revert_run": "<run>"}.  Markers S3LIGHTS_<MODE>_OK|run=.. / S3LIGHTS_FAILED|run=..|reason."""
import json
import os
import shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
RISE_FILE = "E:/PussStage/Content/InfinityStage/RigAtmos/LS_S3_HangarRise.uasset"
RUN = {"run": "?"}


def _group(label, names):
    for n in names:
        if label == "S3 " + n or label.startswith("S3 " + n + " ") or label.startswith("S3 " + n + "_"):
            return n
        if n.endswith(tuple("LR")) and label.startswith("S3 " + n) and label[len("S3 " + n):].isdigit():
            return n
    return None


def main():
    import unreal
    a = json.load(open(HERE + "s3_light_levels_args.json", encoding="utf-8"))
    run, mode = a["run"], a["mode"]
    RUN["run"] = run
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None:
        raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils

    def census():
        return (sorted(p.get_name() for p in lib.get_dirty_content_packages()),
                sorted(p.get_name() for p in lib.get_dirty_map_packages()))

    if mode == "REVERT":
        rec_path = HERE + "s3_light_levels_record_%s.json" % a["revert_run"]
        rec = json.load(open(rec_path))
        target_keys = {(r["owner"], r["idx"]): r["before"] for r in rec["keys"]}
        target_actor = rec["actors"]
        names = sorted(rec["set"])
    else:
        sets = a["set"]
        names = sorted(sets)
    seq = unreal.load_asset(RISE)
    c0 = census()
    if RISE in c0[0]:
        raise RuntimeError("RISE_ALREADY_DIRTY")
    # tracks
    tracks = []
    for b in seq.get_bindings():
        p = b.get_parent()
        owner = str(p.get_display_name()) if p is not None and p.is_valid() else str(b.get_display_name())
        g = _group(owner, names)
        if g is None:
            continue
        for t in b.get_tracks():
            if "ntensity" in str(t.get_display_name()):
                tracks.append((owner, g, t))
    w = ed.get_editor_world()
    actors = {}
    for x in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        lab = str(x.get_actor_label())
        g = _group(lab, names)
        if g is not None:
            lcs = x.get_components_by_class(unreal.LightComponent)
            if len(lcs) == 1:
                actors[lab] = (g, lcs[0])
    found = sorted(set(g for _, g, _ in tracks))
    if found != names:
        raise RuntimeError("GROUP_NOT_FOUND|want=%s|found=%s" % (names, found))
    plan, keys_before = [], []
    for owner, g, t in tracks:
        idx = 0
        for s in t.get_sections():
            for ch in s.get_all_channels():
                for k in ch.get_keys():
                    v = k.get_value()
                    if mode == "REVERT":
                        tgt = target_keys.get((owner, idx), v)
                    else:
                        tgt = sets[g] if abs(v) > 1e-6 else v
                    keys_before.append({"owner": owner, "group": g, "idx": idx, "frame": k.get_time().frame_number.value,
                                        "before": v, "target": tgt})
                    plan.append((k, tgt))
                    idx += 1
    actors_before = {lab: lc.intensity for lab, (g, lc) in actors.items()}
    summary = {g: {"tracks": sum(1 for _, gg, _ in tracks if gg == g),
                   "actors": sum(1 for _, (gg, _) in actors.items() if gg == g),
                   "lit_before": sorted(set(round(r["before"], 3) for r in keys_before if r["group"] == g and abs(r["before"]) > 1e-6)),
                   "lit_after": sorted(set(round(r["target"], 3) for r in keys_before if r["group"] == g and abs(r["target"]) > 1e-6))}
               for g in names}
    if mode == "DRY":
        unreal.log("S3LIGHTS_DRY_OK|run=%s|%s|census=%s" % (run, json.dumps(summary), c0))
        return
    if mode == "APPLY":
        rec_path = HERE + "s3_light_levels_record_%s.json" % run
        if os.path.exists(rec_path):
            raise RuntimeError("RECORD_EXISTS")
        json.dump({"run": run, "state": "applying", "set": sets, "keys": keys_before, "actors": actors_before,
                   "census_before": c0}, open(rec_path, "w"), indent=1)
        bdir = "E:/PussStage/Backups/PreS3LightLevels-%s" % run
        os.makedirs(bdir)
        shutil.copy2(RISE_FILE, bdir)
    seq.modify()
    for k, tgt in plan:
        k.set_value(tgt)
    for lab, (g, lc) in actors.items():
        tgt = target_actor[lab] if mode == "REVERT" else sets[g]
        lc.modify()
        lc.set_intensity(tgt)
    # read back
    i = 0
    for owner, g, t in tracks:
        for s in t.get_sections():
            for ch in s.get_all_channels():
                for k in ch.get_keys():
                    if abs(k.get_value() - plan[i][1]) > 1e-4:
                        raise RuntimeError("KEY_READBACK|%s|NOTHING SAVED; Don't-Save restart" % owner)
                    i += 1
    for lab, (g, lc) in actors.items():
        tgt = target_actor[lab] if mode == "REVERT" else sets[g]
        if abs(lc.intensity - tgt) > 1e-4:
            raise RuntimeError("ACTOR_READBACK|%s" % lab)
    c1 = census()
    extra_content = sorted(set(c1[0]) - set(c0[0]))
    if extra_content != [RISE]:
        raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (extra_content,))
    if not unreal.EditorAssetLibrary.save_asset(RISE, only_if_is_dirty=False):
        raise RuntimeError("SAVE_FAILED")
    if RISE in census()[0]:
        raise RuntimeError("RISE_DIRTY_AFTER_SAVE")
    seq2 = unreal.load_asset(RISE)
    n_ok = 0
    for b in seq2.get_bindings():
        p = b.get_parent()
        owner = str(p.get_display_name()) if p is not None and p.is_valid() else str(b.get_display_name())
        g = _group(owner, names)
        if g is None:
            continue
        for t in b.get_tracks():
            if "ntensity" in str(t.get_display_name()):
                for s in t.get_sections():
                    for ch in s.get_all_channels():
                        for k in ch.get_keys():
                            if abs(k.get_value()) > 1e-6:
                                n_ok += 1
    if mode == "APPLY":
        rec = json.load(open(rec_path))
        rec["state"] = "applied"
        json.dump(rec, open(rec_path, "w"), indent=1)
    else:
        os.rename(rec_path, rec_path + ".reverted")
    unreal.log("S3LIGHTS_%s_OK|run=%s|%s|lit_keys=%d|map_left_dirty_for_gary=%s" % (
        mode, run, json.dumps(summary), n_ok, census()[1]))


try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("S3LIGHTS_FAILED|run=%s|%r" % (RUN["run"], exc))
