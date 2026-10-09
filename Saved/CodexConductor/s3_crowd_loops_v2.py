"""S3 CROWD LOOPS v2 (Gary 9 Oct ~02:20 after recording S03 v2: "after 2min point, their cloths are flinging all over the
place ... very often twitching and the fabric flying everywhere ... it has to do with how the chaos cloth gets disturbed,
either by a sudden movement like a loop of movement").
[inf, strongly] S3MOTION-20261008-1 replaced the calm loops with PING-PONG chains: each turnaround reverses the body's
velocity in one frame, and 20 desynced figures turn somewhere every few seconds -> the cloth is whipped.  (Frames
2:22-2:46 of the recording show shrouds thrown over heads [measured by eye].)
FIX: for every figure, the S3MOTION ping-pong sections are DEACTIVATED (kept, recorded) and a FORWARD-ONLY chain is laid
over the same [start, cap): same per-figure rate and phase (desync kept), consecutive spans OVERLAP by XFADE frames with
weight ramps (out 1->0, in 0->1), so the pose never jumps and never reverses.  cap = the S3LATE frenzy swap (T_SWAP+22 =
4232) for figures S3LATE switched, else the chain end.  The first section copies the old first section's ease-in keys.
LS_Clams only; record s3_crowd_loops_v2_record.json + backup; REVERT exact (removes v2 sections, restores actives).
Args s3_crowd_loops_v2_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3LOOPS2", "xfade": 72}.
Markers S3LOOPS2_<MODE>_OK / _FAILED."""
import datetime, json, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_crowd_loops_v2_record.json"
CLAMS = "/Game/Scenes/LS_Clams"
CLAMS_FILE = "E:/PussStage/Content/Scenes/LS_Clams.uasset"
CAP = 4210 + 22


def _rate(p):
    v = p.get_editor_property("play_rate")
    return float(v.to_fixed_play_rate()) if hasattr(v, "to_fixed_play_rate") else float(v)


def _set_rate(p, r):
    v = p.get_editor_property("play_rate")
    if hasattr(v, "set_fixed_play_rate"):
        v.set_fixed_play_rate(float(r)); p.set_editor_property("play_rate", v)
    else:
        p.set_editor_property("play_rate", float(r))


def _weight(s):
    for c in s.get_all_channels():
        if str(c.get_name()).startswith("Weight"):
            return c
    return None


def main():
    import unreal
    a = json.load(open(HERE + "s3_crowd_loops_v2_args.json")); mode = a["mode"]; X = int(a.get("xfade", 72))
    run = datetime.datetime.now().strftime("S3LOOPS2-%Y%m%d-%H%M%S")
    if unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    mrec = json.load(open(HERE + "s3_crowd_motion_record.json"))
    lrec = json.load(open(HERE + "s3_crowd_late_record.json")) if os.path.exists(HERE + "s3_crowd_late_record.json") else {"ocean": []}
    late_owners = {o["label"] for o in lrec.get("ocean", [])}
    clams = unreal.load_asset(CLAMS)
    tick = clams.get_tick_resolution(); tps = float(tick.numerator) / float(tick.denominator); fps = 24.0
    tracks = {}
    for b in clams.get_bindings():
        par = b.get_parent()
        owner = str(par.get_display_name()) if par is not None else str(b.get_display_name())
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieSceneSkeletalAnimationTrack) and owner in mrec["added"]:
                tracks[owner] = t
    missing = [o for o in mrec["added"] if o not in tracks]
    if missing: raise RuntimeError("NO_TRACK|%s" % missing)
    plan = {}
    for owner, names in mrec["added"].items():
        c = mrec["plan"][owner]["chain"]
        cap = min(int(c["end"]), CAP) if owner in late_owners else int(c["end"])
        span = c["src"][1] - c["src"][0]; r = c["new_rate"]
        full = int(round(span / r * fps))
        secs, cur, first = [], int(c["start"]), True
        while cur < cap:
            a_in = c["src"][0] + (c["phase"] * span if first else 0.0)
            dur = int(round((c["src"][1] - a_in) / r * fps))
            stop = min(cap, cur + max(X + 1, dur))
            secs.append([cur, stop, round(a_in, 4)])
            if stop >= cap: break
            cur, first = stop - X, False
            if len(secs) > 60: raise RuntimeError("RUNAWAY|" + owner)
        plan[owner] = {"old": names, "cap": cap, "rate": r, "src": c["src"], "row": c["row"], "full": full, "sections": secs}
    if mode == "DRY":
        json.dump(plan, open(HERE + "s3_crowd_loops_v2_dry.json", "w"), indent=1)
        unreal.log("S3LOOPS2_DRY_OK|figures=%d|sections=%d|xfade=%d|caps=%s" % (len(plan), sum(len(p["sections"]) for p in plan.values()), X,
                   sorted({p["cap"] for p in plan.values()})))
        return
    if a.get("confirm") != "%s S3LOOPS2" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3Loops2-%s" % run; os.makedirs(bd); shutil.copy2(CLAMS_FILE, bd)
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        rec = {"run": run, "backup": bd, "xfade": X, "old_active": {}, "added": {}}
        json.dump(rec, open(REC, "w"), indent=1)
        for owner, p in plan.items():
            t = tracks[owner]; by = {str(s.get_name()): s for s in t.get_sections()}
            olds = [by[n] for n in p["old"] if n in by]
            rec["old_active"][owner] = {str(s.get_name()): bool(s.is_active()) for s in olds}
            anim = olds[0].get_editor_property("params").get_editor_property("animation")
            length = float(anim.get_play_length())
            w0 = _weight(olds[0]); wk = [[int(k.get_time().frame_number.value), float(k.get_value())] for k in w0.get_keys()] if w0 else []
            for s in olds: s.set_is_active(False)
            added = []
            for i, (s0, e0, a_in) in enumerate(p["sections"]):
                ns = t.add_section(); pp = ns.get_editor_property("params")
                pp.set_editor_property("animation", anim)
                pp.set_editor_property("start_frame_offset", unreal.FrameNumber(int(round(a_in * tps))))
                pp.set_editor_property("end_frame_offset", unreal.FrameNumber(int(round(max(0.0, length - p["src"][1]) * tps))))
                pp.set_editor_property("reverse", False); _set_rate(pp, p["rate"])
                ns.set_editor_property("params", pp); ns.set_range(s0, e0); ns.set_row_index(p["row"])
                w = _weight(ns)
                if i == 0:
                    for f, v in wk:
                        if f < s0 + 40: w.add_key(unreal.FrameNumber(f), v)
                else:
                    w.add_key(unreal.FrameNumber(s0), 0.0); w.add_key(unreal.FrameNumber(s0 + X), 1.0)
                if i < len(p["sections"]) - 1:
                    w.add_key(unreal.FrameNumber(e0 - X), 1.0); w.add_key(unreal.FrameNumber(e0), 0.0)
                if abs(_rate(ns.get_editor_property("params")) - p["rate"]) > 1e-5 or ns.get_editor_property("params").get_editor_property("reverse"):
                    raise RuntimeError("READBACK|%s|NOTHING SAVED; Don't-Save restart" % owner)
                added.append(str(ns.get_name()))
            rec["added"][owner] = added
        json.dump(rec, open(REC, "w"), indent=1)
    elif mode == "REVERT":
        rec = json.load(open(REC))
        for owner, names in rec["added"].items():
            t = tracks[owner]
            for s in list(t.get_sections()):
                if str(s.get_name()) in names: t.remove_section(s)
            for s in t.get_sections():
                if str(s.get_name()) in rec["old_active"][owner]: s.set_is_active(rec["old_active"][owner][str(s.get_name())])
    else:
        raise RuntimeError("MODE")
    if census() != ([CLAMS], []): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(CLAMS, only_if_is_dirty=False) or census() != ([], []): raise RuntimeError("SAVE")
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3LOOPS2_%s_OK|run=%s|figures=%d|backup=%s" % (mode, run, len(rec.get("added", {})), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3LOOPS2_FAILED|%r" % (exc,))
