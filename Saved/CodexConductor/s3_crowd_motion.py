"""S3 CROWD MOTION (Gary 8 Oct ~20:40 PIE run-through, his words):
  "The many new figures don't seem to all spawn at once by the time the lights have come on."
  "at about 2min ... the figures that are duplicated are too closely synced ... offset their motion track a bit."
  "At 2.10, there is a Snap ... causes the figures in view to have their fabric and body position suddenly displaced".
[meas] probe_crowd_tracks.json (8 Oct): the 15 copies have NO animation before LS_Clams 358 (reference pose until the
lights' cue), every CALM span is a LOOP of identical sections whose wraps fall at LS_Clams 2904-3171 (Scene ~2:06-2:10;
each wrap jumps the pose back to the span start), and copies of one source share in/out/rate (offsets <= 2 s).
WRITES (LS_Clams only; record s3_crowd_motion_record.json + Backups/PreS3CrowdMotion-<run>; REVERT exact):
  PREROLL (copies): the first animation section starts at 0 instead of ~358, its start offset pulled back by the same
    source time (continuous by construction: frame 358 still shows the same source instant).
  CHAINS (20 figures, the CALM loop chain starting >= CHAIN_FROM): the chain's sections are DEACTIVATED (kept) and a new
    ping-pong chain is added over the same [start, end): play rate x (1 + d), d in [-RATE_JIT, +RATE_JIT], first section
    starts PHASE into the span, then alternate REVERSED/forward full spans, abutting exactly (a reversed span starts on
    the pose the forward one ended on, so no wrap jump).  The first new section copies the old first section's weight
    (ease-in) keys.  d and PHASE are deterministic per figure (hash of the label).
Run BEFORE s3_crowd_late.py (that tool trims whatever sections run past the wall-shot swap).
Args s3_crowd_motion_args.json {"mode": DRY|APPLY|REVERT, "confirm": "<MODE> S3MOTION", "run", "parts": ["preroll","chains"]}.
Markers S3MOTION_<MODE>_OK / _FAILED."""
import hashlib, json, os, shutil

HERE = "E:/PussStage/Saved/CodexConductor/"
REC = HERE + "s3_crowd_motion_record.json"
CLAMS = "/Game/Scenes/LS_Clams"
CLAMS_FILE = "E:/PussStage/Content/Scenes/LS_Clams.uasset"
CHAIN_FROM = 2400
RATE_JIT = 0.12


def _h(label, k):
    return int(hashlib.sha256(("%s|%s" % (label, k)).encode()).hexdigest()[:8], 16) / float(0xFFFFFFFF)


def _rate(p):
    v = p.get_editor_property("play_rate")
    return float(v.to_fixed_play_rate()) if hasattr(v, "to_fixed_play_rate") else float(v)


def _set_rate(p, r, unreal):
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
    a = json.load(open(HERE + "s3_crowd_motion_args.json"))
    run, mode, parts = a["run"], a["mode"], a.get("parts", ["preroll", "chains"])
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if ed.get_game_world() is not None: raise RuntimeError("PIE_RUNNING")
    lib = unreal.EditorLoadingAndSavingUtils
    census = lambda: (sorted(p.get_name() for p in lib.get_dirty_content_packages()), sorted(p.get_name() for p in lib.get_dirty_map_packages()))
    if mode != "DRY" and census() != ([], []): raise RuntimeError("DIRTY_AT_START|%s" % (census(),))
    clams = unreal.load_asset(CLAMS)
    tick = clams.get_tick_resolution(); tps = float(tick.numerator) / float(tick.denominator); fps = 24.0
    tracks = {}
    for b in clams.get_bindings():
        par = b.get_parent()
        owner = str(par.get_display_name()) if par is not None else str(b.get_display_name())
        if not (owner.startswith("S3 Crowd") or (owner.startswith("Shore0") and not owner.startswith("Shore05"))): continue
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieSceneSkeletalAnimationTrack): tracks.setdefault(owner, []).append(t)
    bad = {k: len(v) for k, v in tracks.items() if len(v) != 1}
    if bad or len(tracks) != 20: raise RuntimeError("ANIM_TRACKS|%d|%s" % (len(tracks), bad))
    plan = {}
    for owner, (t,) in sorted(tracks.items()):
        secs = sorted([s for s in t.get_sections() if s.is_active()], key=lambda s: int(s.get_start_frame()))
        row = {"preroll": None, "chain": None}
        if owner.startswith("S3 Crowd") and secs and int(secs[0].get_start_frame()) > 0:
            p = secs[0].get_editor_property("params")
            st = int(secs[0].get_start_frame()); back = st / fps * _rate(p)
            row["preroll"] = {"section": str(secs[0].get_name()), "start": st, "in_s": p.get_editor_property("start_frame_offset").value / tps,
                              "new_in_s": p.get_editor_property("start_frame_offset").value / tps - back}
        late = [s for s in secs if int(s.get_start_frame()) >= CHAIN_FROM]
        kf = lambda s: (s.get_editor_property("params").get_editor_property("start_frame_offset").value,
                        s.get_editor_property("params").get_editor_property("end_frame_offset").value, round(_rate(s.get_editor_property("params")), 6))
        i0 = next((i for i in range(len(late) - 1) if kf(late[i]) == kf(late[i + 1])), None)   # first repeated span = the loop
        late = late[i0:] if i0 is not None else []
        if late:
            p0 = late[0].get_editor_property("params")
            key = (p0.get_editor_property("start_frame_offset").value, p0.get_editor_property("end_frame_offset").value, round(_rate(p0), 6))
            chain = []
            for s in late:
                p = s.get_editor_property("params")
                if (p.get_editor_property("start_frame_offset").value, p.get_editor_property("end_frame_offset").value, round(_rate(p), 6)) != key: break
                chain.append(s)
            if len(chain) >= 2:
                anim = p0.get_editor_property("animation"); length = float(anim.get_play_length())
                src_in = key[0] / tps; src_out = length - key[1] / tps
                row["chain"] = {"sections": [str(s.get_name()) for s in chain], "start": int(chain[0].get_start_frame()),
                                "end": int(chain[-1].get_end_frame()), "src": [round(src_in, 4), round(src_out, 4)], "rate": key[2],
                                "new_rate": round(key[2] * (1.0 + RATE_JIT * (2.0 * _h(owner, "rate") - 1.0)), 5),
                                "phase": round(_h(owner, "phase"), 4), "row": int(chain[0].get_row_index())}
        plan[owner] = row
    if mode == "DRY":
        json.dump(plan, open(HERE + "s3_crowd_motion_dry.json", "w"), indent=1)
        unreal.log("S3MOTION_DRY_OK|run=%s|prerolls=%d|chains=%d|no_chain=%s" % (run, sum(1 for r in plan.values() if r["preroll"]),
                   sum(1 for r in plan.values() if r["chain"]), [k for k, r in plan.items() if not r["chain"]]))
        return
    if a.get("confirm") != "%s S3MOTION" % mode: raise RuntimeError("CONFIRM")
    bd = "E:/PussStage/Backups/PreS3CrowdMotion-%s" % run
    if mode == "APPLY":
        if os.path.exists(REC): raise RuntimeError("RECORD_EXISTS")
        os.makedirs(bd); shutil.copy2(CLAMS_FILE, bd)
        rec = {"run": run, "backup": bd, "plan": plan, "added": {}, "preroll_done": {}}
        json.dump(rec, open(REC, "w"), indent=1)
        for owner, row in plan.items():
            t = tracks[owner][0]; by = {str(s.get_name()): s for s in t.get_sections()}
            if "preroll" in parts and row["preroll"]:
                s = by[row["preroll"]["section"]]; p = s.get_editor_property("params")
                w = _weight(s); wk = [[int(k.get_time().frame_number.value), float(k.get_value())] for k in w.get_keys()] if w else []
                rec["preroll_done"][owner] = {"weight_keys": wk}
                p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(round(max(0.0, row["preroll"]["new_in_s"]) * tps))))
                s.set_editor_property("params", p); s.set_start_frame(0)
                if w:
                    for k in list(w.get_keys()):
                        if int(k.get_time().frame_number.value) < row["preroll"]["start"] + 30: w.remove_key(k)
                    w.set_default(1.0)
            if "chains" in parts and row["chain"]:
                c = row["chain"]; old = [by[n] for n in c["sections"]]
                anim = old[0].get_editor_property("params").get_editor_property("animation")
                length = float(anim.get_play_length())
                w0 = _weight(old[0]); wkeys = [[int(k.get_time().frame_number.value), float(k.get_value())] for k in w0.get_keys()] if w0 else []
                for s in old: s.set_is_active(False)
                span = c["src"][1] - c["src"][0]; r = c["new_rate"]
                cur, rev, first, added = c["start"], False, True, []
                while cur < c["end"]:
                    a_in, a_out = c["src"]
                    if first: a_in = c["src"][0] + c["phase"] * span
                    dur = int(round((a_out - a_in) / r * fps))
                    stop = min(c["end"], cur + max(1, dur))
                    ns = t.add_section(); p = ns.get_editor_property("params")
                    p.set_editor_property("animation", anim)
                    p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(round(a_in * tps))))
                    p.set_editor_property("end_frame_offset", unreal.FrameNumber(int(round(max(0.0, length - a_out) * tps))))
                    p.set_editor_property("reverse", rev); _set_rate(p, r, unreal)
                    ns.set_editor_property("params", p); ns.set_range(cur, stop); ns.set_row_index(c["row"])
                    if first and wkeys:
                        w = _weight(ns)
                        for f, v in wkeys:
                            if f < cur + 40: w.add_key(unreal.FrameNumber(f), v)
                    added.append(str(ns.get_name()))
                    if abs(_rate(ns.get_editor_property("params")) - r) > 1e-5: raise RuntimeError("RATE_READBACK|%s|NOTHING SAVED; Don't-Save restart" % owner)
                    cur, rev, first = stop, (not rev), False
                    if len(added) > 60: raise RuntimeError("CHAIN_RUNAWAY|%s|NOTHING SAVED; Don't-Save restart" % owner)
                rec["added"][owner] = added
        json.dump(rec, open(REC, "w"), indent=1)
    elif mode == "REVERT":
        if not os.path.exists(REC): raise RuntimeError("NO_RECORD")
        rec = json.load(open(REC)); os.makedirs(bd); shutil.copy2(CLAMS_FILE, bd)
        for owner, names in rec["added"].items():
            t = tracks[owner][0]
            for s in list(t.get_sections()):
                if str(s.get_name()) in names: t.remove_section(s)
            for s in t.get_sections():
                if str(s.get_name()) in rec["plan"][owner]["chain"]["sections"]: s.set_is_active(True)
        for owner, pre in rec["preroll_done"].items():
            t = tracks[owner][0]; pr = rec["plan"][owner]["preroll"]
            for s in t.get_sections():
                if str(s.get_name()) == pr["section"]:
                    p = s.get_editor_property("params")
                    p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(round(pr["in_s"] * tps))))
                    s.set_editor_property("params", p); s.set_start_frame(pr["start"])
                    w = _weight(s)
                    if w:
                        for k in list(w.get_keys()): w.remove_key(k)
                        for f, v in pre["weight_keys"]: w.add_key(unreal.FrameNumber(f), v)
    else:
        raise RuntimeError("MODE")
    if census() != ([CLAMS], []): raise RuntimeError("CENSUS|%s|NOTHING SAVED; Don't-Save restart" % (census(),))
    if not unreal.EditorAssetLibrary.save_asset(CLAMS, only_if_is_dirty=False) or census() != ([], []):
        raise RuntimeError("SAVE|%s" % (census(),))
    if mode == "REVERT": os.rename(REC, REC + ".reverted-" + run)
    unreal.log("S3MOTION_%s_OK|run=%s|prerolls=%d|chains=%d|backup=%s" % (mode, run, len(rec.get("preroll_done", {})), len(rec.get("added", {})), bd))


try:
    main()
except Exception as exc:  # noqa: BLE001
    import unreal
    unreal.log_error("S3MOTION_FAILED|%r" % (exc,))
