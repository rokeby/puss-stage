"""OPENING READBACK (READ-ONLY): what Gary's 14:02 hand edits to LS_Opening_Curtain_Baked did to the Opening, the Show
and the Master, and what a reconcile needs. Offline-written 5 Oct, NEVER RUN IN UNREAL. Prints log rows and writes
opening_readback_<run>.json here; writes NOTHING to Unreal (asserts the dirty census is unchanged). Harness:
test_opening_readback.py.

Tiers per claim: [decl] declaration-proven (cited), [prec] in-repo precedent (cited), [meas] earlier read-back (cited),
[inf] inferred (why stated).

What it reads (every reader copies opening_sequence_apply.py so hashes are comparable with its record):
  * Opening playback range / display rate / tick [prec opening_sequence_apply.py:148-155, 402-404].
  * The drape's GeometryCache sections HOLD/FALL/PILE [prec :198-212]; release = FALL start + release_in_cache_s -
    FALL start_frame_offset (the rule curtain_sections() inverts) [prec opening_sequence_plan.py:224-248; meas
    opening_sequence_report_apply.json: FALL 1871, offset 23200 ticks -> release 74.873 s, landed 79.207 s].
  * Rig + walk-in key rows and their 16-hex digests exactly as the apply hashes them [prec :332-369, 908-909], compared
    with opening_sequence_record.json track_hashes; OPN markers vs last_applied_frames [prec :293-302, 907].
    Also EVERY track on 'Opening Rig - *' bindings, so keys Gary put on a different track are not missed.
  * Show: the Opening cue (Sequence; UseSequenceLength [meas step opening_cue use_sequence_length True]), its and P01's
    music bindings [prec :179-185], the rail's sound; compiled segments from a transient transport
    [prec rebuild_managed_master_guarded.py:38-42]. With UseSequenceLength the COMPILE follows the sequence's playback
    range on its own [decl InfinityStageCompiler.cpp:13-32 ResolveSceneDuration, :217-226]; the Master does not until
    RebuildManagedMaster runs [decl InfinityStageSequenceBuilderLibrary.cpp:503-595 lays sections from the compile].
  * Master: Scene-track sections (EXACT type - the Choreo track is a sub-track too [decl
    MovieSceneInfinityChoreoTrack.h:32; MovieSceneSequenceExtensions.h:55-69]), Passage sections, managed music sections.
  * Sketch 2: what the NEXT opening_sequence_apply DRY would plan (planner run here, pure) - as-is ('auto' end = track
    rounded up) and with opening_end pinned to Gary's playback end.
Marker: OPENING_READBACK_OK|run=..|... or OPENING_READBACK_STOPPED|run=..|reason=..
Never: write, save, reload, open/scrub Sequencer, evaluate, end PIE; no unreal objects in module globals.
"""
import datetime
import hashlib
import json
import os
import re

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None

TOOL = "opening_readback"
SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
DRAPE = "Opening Drape (baked)"                 # opening_sequence_apply.py:59-63
WALK_TRACK = "WalkIn (Look & camera)"
RIG_TRACK = "OpeningRig (Conductor)"
RIG_PREFIX = "Opening Rig - "
WATCHED = ("Opening Rig - FOH L/MovieSceneFloatTrack/Intensity", "Opening Rig - FOH R/MovieSceneFloatTrack/Intensity",
           "Opening Rig - Wash C/MovieSceneFloatTrack/Intensity")
TOL_S = 0.05                                    # rebuild_managed_master_guarded.py:58


# =====================================================================================================================
# Pure
# =====================================================================================================================

def digest(rows):
    """Identical to opening_sequence_apply.py:368-369."""
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def curtain_timing(gc, fps, tps, curtain):
    """gc: [[start, end, start_offset_ticks, end_offset_ticks]] x3 (HOLD, FALL, PILE), display frames.
    curtain: opening_timing.json 'curtain' (release_in_cache_s, release_frame, landed_bake_frame, cache_fps)."""
    if len(gc) != 3:
        return {"error": "expected 3 GC sections, got %d" % len(gc)}
    hold, fall, pile = gc
    release_s = fall[0] / fps + float(curtain["release_in_cache_s"]) - fall[2] / tps
    landed_s = release_s + (float(curtain["landed_bake_frame"]) - float(curtain["release_frame"])) / float(curtain["cache_fps"])
    return {"release_s": round(release_s, 4), "landed_s": round(landed_s, 4), "fall_frames": [fall[0], fall[1]],
            "contiguous": hold[1] == fall[0] and fall[1] == pile[0], "pile_end_frame": pile[1]}


def hash_compare(recorded, live_rows):
    """{key: status} where status is match / EDITED / MISSING_NOW / NEW_TRACK."""
    out = {}
    for key in sorted(set(recorded) | set(live_rows)):
        if key not in live_rows:
            out[key] = "MISSING_NOW"
        elif key not in recorded:
            out[key] = "NEW_TRACK"
        else:
            out[key] = "match" if digest(live_rows[key]) == recorded[key] else "EDITED"
    return out


def marker_compare(markers, last_applied, prefix="OPN "):
    """{moment: {last, now, moved}} for the planner's input moments."""
    now = {}
    for label, frame in markers:
        if label.startswith(prefix):
            now[label[len(prefix):]] = frame
    return {k: {"last": v, "now": now.get(k), "moved": now.get(k) != v} for k, v in sorted(last_applied.items())}


def key_diff(rows_a, rows_b):
    """Frames whose value differs / that exist on one side only (two [[frame, value]] lists)."""
    a, b = dict((int(f), v) for f, v in rows_a), dict((int(f), v) for f, v in rows_b)
    return {"changed": sorted(f for f in set(a) & set(b) if abs(a[f] - b[f]) > 1e-4),
            "only_before": sorted(set(a) - set(b)), "only_now": sorted(set(b) - set(a))}


def drift_findings(f):
    """Plain facts -> ordered findings. f keys: fps, playback, seg_opening, master_opening, seg_p01, master_p01,
    music_opening, cut, curtain, rig_section_ends, walk_section_ends, music_s."""
    out = []
    fps = float(f["fps"])
    end_s = f["playback"][1] / fps
    so = f.get("seg_opening")
    if so is None:
        out.append(("ERROR", "SHOW_HAS_NO_OPENING_SEGMENT"))
        return out
    if abs(so[1] - end_s) > TOL_S:
        out.append(("DRIFT", "SHOW_OPENING_END %.3f s != sequence playback end %.3f s (UseSequenceLength off?)"
                    % (so[1], end_s)))
    mo = f.get("master_opening")
    if mo is None or abs(mo[1] - so[1]) > TOL_S:
        out.append(("DRIFT", "MASTER_STALE: Master Opening section %r vs Show %r (delta %+.3f s); every later Master "
                    "section is off by the same amount until RebuildManagedMaster" % (
                        mo, [round(so[0], 3), round(so[1], 3)], (so[1] - mo[1]) if mo else float("nan"))))
    if f.get("seg_p01") and f.get("master_p01") and abs(f["seg_p01"][0] - f["master_p01"][0]) > TOL_S:
        out.append(("DRIFT", "P01_STARTS_EARLY_IN_MASTER: Master P01 at %.3f s, Show P01 at %.3f s: the Master cuts "
                    "to P01 %.3f s before the Opening sequence ends" % (
                        f["master_p01"][0], f["seg_p01"][0], f["seg_p01"][0] - f["master_p01"][0])))
    mus = f.get("music_opening")
    if mus is not None and abs(mus["range_s"][1] - so[1]) > TOL_S:
        out.append(("DRIFT", "OPENING_MUSIC_SECTION %r ends %.3f s from the Show's Opening end" % (
            mus["range_s"], so[1] - mus["range_s"][1])))
    if f.get("cut") and f["cut"][1] < f["playback"][1]:
        out.append(("GAP", "CAMERA_CUT_ENDS_EARLY: cut ends frame %d < playback end %d" % (f["cut"][1], f["playback"][1])))
    c = f.get("curtain") or {}
    if c.get("pile_end_frame") is not None and c["pile_end_frame"] < f["playback"][1]:
        out.append(("GAP", "PILE_ENDS_EARLY: GC PILE ends frame %d < playback end %d (curtain vanishes)" % (
            c["pile_end_frame"], f["playback"][1])))
    if c and not c.get("contiguous", True):
        out.append(("WARN", "GC_SECTIONS_NOT_CONTIGUOUS"))
    for kind in ("rig_section_ends", "walk_section_ends"):
        short = {k: e for k, e in (f.get(kind) or {}).items() if e is not None and e < f["playback"][1]}
        if short:
            out.append(("GAP", "%s before the playback end: %r" % (kind.upper(), short)))
    if f.get("music_s") is not None:
        diff = end_s - float(f["music_s"])
        if diff < -1.0 / fps:
            out.append(("WARN", "SKETCH2_LONGER_THAN_OPENING: 95.5 s track runs %.3f s past Gary's end %.3f s and is "
                        "cut by the Opening segment" % (-diff, end_s)))
        elif diff > 1.0 / fps:
            out.append(("INFO", "OPENING_LONGER_THAN_SKETCH2: Gary's end %.3f s leaves %.3f s after the 95.504 s track "
                        "(silence under the walk-in)" % (end_s, diff)))
    return out


def soft_path_from_export(text, field):
    """Same parser as walking_music_swap.py (harness-tested there)."""
    m = re.search(r"(?:^|[,(])%s=(\"[^\"]*\"|[^,)]*)" % re.escape(field), str(text))
    if not m:
        return None
    hit = re.search(r"(/Game/[A-Za-z0-9_/\-]+)(?:\.[A-Za-z0-9_\-]+)?", m.group(1))
    return hit.group(1) if hit else None


def planner_preview(planner, cfg, analysis, walk_planner, markers, last, end_frame, fps):
    """What the next opening_sequence_apply would plan: (a) cfg as-is, (b) opening_end pinned to Gary's end."""
    out = {}
    for name, pin in (("as_is", None), ("keep_gary_end", end_frame)):
        c = json.loads(json.dumps(cfg))
        if pin is not None:
            c["moments"]["opening_end"] = {"value": round(pin / fps, 4), "source": "readback proposal"}
        try:
            p = planner["build_plan"](c, analysis, walk_planner, planner["markers_to_moments"](markers), last)
            out[name] = {"frames": p["frames"], "sources": p["sources"], "conflicts": p["conflicts"],
                         "writeback": p["writeback"], "curtain": p["curtain"], "failures": p["failures"],
                         "walkin": {k: v for k, v in p["walkin"].items() if k != "keys"},
                         "master_delta_vs_baseline_s": round(p["master_delta_s"], 4)}
        except Exception as exc:  # noqa: BLE001 - reported, the readback stays useful
            out[name] = {"error": repr(exc)}
    return out


# =====================================================================================================================
# Live (read-only)
# =====================================================================================================================

def main():
    run = str(globals().get("READBACK_RUN_ID") or datetime.datetime.now().strftime("OPRB-%Y%m%d-%H%M%S"))
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    here = os.path.join(saved, "CodexConductor")
    out_path = os.path.join(here, "opening_readback_%s.json" % run)
    report = {"tool": TOOL, "run": run, "ok": False, "warnings": []}

    def stop(reason):
        report["error"] = reason
        with open(out_path, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str, ensure_ascii=False)
        unreal.log_error("OPENING_READBACK_STOPPED|run=%s|reason=%s" % (run, reason))
        raise RuntimeError(reason)

    def census():
        return {"content": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
                "maps": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}

    def guid(v):
        return unreal.GuidLibrary.conv_guid_to_string(v)

    def path(o):
        return o.get_path_name().split(".")[0] if o is not None else None

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        stop("PIE/SIE active (read-only tool still refuses; never ends PIE)")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != WORLD:
        stop("wrong editor world")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        report["warnings"].append("a sequence is open in Sequencer: it may evaluate; census compared before/after")
    census0 = census()
    report["census_before"] = census0

    with open(os.path.join(here, "opening_timing.json"), encoding="utf-8") as h:
        cfg = json.load(h)
    with open(os.path.join(here, "opening_sequence_record.json"), encoding="utf-8") as h:
        record = json.load(h)
    seq, show, master = unreal.load_asset(cfg["sequence"]), unreal.load_asset(SHOW), unreal.load_asset(MASTER)
    if seq is None or show is None or master is None:
        stop("sequence/Show/Master did not load")
    rate, tick = seq.get_display_rate(), seq.get_tick_resolution()
    fps, tps = rate.numerator / float(rate.denominator), tick.numerator / float(tick.denominator)
    playback = [int(seq.get_playback_start()), int(seq.get_playback_end())]
    report["sequence"] = {"path": cfg["sequence"], "fps": fps, "tps": tps, "playback": playback,
                          "playback_s": [playback[0] / fps, playback[1] / fps],
                          "record_playback_after_apply": [0, record.get("last_applied_frames", {}).get("opening_end")]}

    # ---------------------------------------------------------------- tracks (readers copied from the apply)
    def hosts():
        rows = [("<root>", t) for t in seq.get_tracks()]
        for b in seq.get_bindings():
            rows += [(str(b.get_display_name()), t) for t in b.get_tracks()]
        return rows

    def track_key(host_name, t, ch):
        cls = t.get_class().get_name()
        if cls == "MovieSceneFloatTrack":
            return "%s/%s/%s" % (host_name, cls, str(t.get_property_name()))
        return "%s/%s/%s" % (host_name, cls, str(ch.channel_name))

    def float_keys(ch):
        return [[int(k.get_time().frame_number.value), round(float(k.get_value()), 4)] for k in ch.get_keys()]

    def read(select):
        rows, ends = {}, {}
        for host_name, t in hosts():
            if not select(host_name, t):
                continue
            for s in t.get_sections():
                for ch in s.get_all_channels():
                    keys = float_keys(ch)
                    if keys:
                        k = track_key(host_name, t, ch)
                        rows[k] = keys
                        ends[k] = s.get_end_frame() if s.has_end_frame() else None
        return rows, ends

    rig, rig_ends = read(lambda h, t: str(t.get_display_name()) == RIG_TRACK)
    walk, walk_ends = read(lambda h, t: str(t.get_display_name()) == WALK_TRACK)
    rig_any, _ = read(lambda h, t: h.startswith(RIG_PREFIX) and str(t.get_display_name()) != RIG_TRACK)
    hashes = record.get("track_hashes", {})
    report["rig"] = {"status": hash_compare(hashes.get("rig", {}), rig),
                     "watched_keys": {k: rig.get(k) for k in WATCHED},
                     "other_tracks_on_rig_bindings": rig_any, "live_digests": {k: digest(v) for k, v in rig.items()}}
    report["walk"] = {"status": hash_compare(hashes.get("walk", {}), walk),
                      "live_digests": {k: digest(v) for k, v in walk.items()}}
    for k in WATCHED:
        unreal.log("OPENING_READBACK_KEYS|run=%s|%s|status=%s|n=%d|keys=%s" % (
            run, k, report["rig"]["status"].get(k), len(rig.get(k) or []), json.dumps(rig.get(k))[:900]))

    # ---------------------------------------------------------------- markers, curtain, cut
    unit = unreal.MovieSceneTimeUnit
    if hasattr(seq, "get_marked_frames_from_sequence"):
        markers = [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)]
                   for m in seq.get_marked_frames_from_sequence(unit.DISPLAY_RATE)]
    else:
        tpf = int(round(tps / fps))
        markers = [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value) // tpf]
                   for m in seq.get_marked_frames()]
    report["markers"] = {"all": markers, "vs_last_applied": marker_compare(markers, record.get("last_applied_frames", {}))}
    drapes = [b for b in seq.get_bindings() if str(b.get_display_name()) == DRAPE]
    gc = []
    if len(drapes) == 1:
        gct = [t for t in drapes[0].get_tracks() if t.get_class().get_name() == "MovieSceneGeometryCacheTrack"]
        if len(gct) == 1:
            for s in sorted(gct[0].get_sections(), key=lambda s: s.get_start_frame()):
                p = s.get_editor_property("params")
                gc.append([s.get_start_frame(), s.get_end_frame(), p.get_editor_property("start_frame_offset").value,
                           p.get_editor_property("end_frame_offset").value])
    curtain = curtain_timing(gc, fps, tps, cfg["curtain"])
    applied_gc = None
    try:
        with open(os.path.join(here, "opening_sequence_report_apply.json"), encoding="utf-8") as h:
            applied_gc = json.load(h).get("readback", {}).get("gc_sections")      # last APPLY's read-back [meas]
    except (OSError, ValueError):
        report["warnings"].append("opening_sequence_report_apply.json unreadable")
    report["curtain"] = dict(curtain, gc_sections=gc, gc_sections_last_apply=applied_gc,
                             gc_changed_since_apply=(applied_gc is not None and gc != applied_gc))
    cuts = [s for t in seq.get_tracks() if t.get_class().get_name() == "MovieSceneCameraCutTrack"
            for s in t.get_sections() if s.is_active()]
    cut = [cuts[0].get_start_frame(), cuts[0].get_end_frame()] if len(cuts) == 1 else None
    report["cut"] = {"active_sections": len(cuts), "range": cut}
    report["sequence_audio_tracks"] = [
        {"track": str(t.get_display_name()), "sections": [[s.get_start_frame() if s.has_start_frame() else None,
                                                           s.get_end_frame() if s.has_end_frame() else None,
                                                           path(s.get_sound())] for s in t.get_sections()]}
        for t in seq.find_tracks_by_type(unreal.MovieSceneAudioTrack)]

    # ---------------------------------------------------------------- Show
    show_tick = show.get_editor_property("tick_resolution")
    st = show_tick.numerator / float(show_tick.denominator)
    cues = list(show.get_editor_property("cues"))
    oc = [c for c in cues if str(c.get_editor_property("label")) == cfg["cue_label"]]
    if len(oc) != 1:
        stop("expected one '%s' cue, found %d" % (cfg["cue_label"], len(oc)))
    oscene = oc[0].get_editor_property("scene")

    def music(b):
        return {"mode": str(b.get_editor_property("mode")), "rail": guid(b.get_editor_property("primary_rail_guid")),
                "offset": int(b.get_editor_property("rail_offset_frames").value)}

    p01 = [p for p in show.get_editor_property("passage_settings")
           if str(p.get_editor_property("label")) == cfg["next_passage_label"]]
    rails = {}
    for r in show.get_editor_property("music_rails"):
        text = r.export_text() if hasattr(r, "export_text") else str(r)
        s = r.get_editor_property("sound")
        rails[guid(r.get_editor_property("rail_guid"))] = {
            "label": str(r.get_editor_property("label")), "sound": path(s) if s is not None else soft_path_from_export(text, "Sound")}
    report["show"] = {
        "opening_cue_guid": guid(oc[0].get_editor_property("cue_guid")),
        "use_sequence_length": bool(oscene.get_editor_property("use_sequence_length")),
        "duration_frames_ticks": int(oscene.get_editor_property("duration_frames").value),
        "opening_music": music(oscene.get_editor_property("music")),
        "p01_music": music(p01[0].get_editor_property("music")) if len(p01) == 1 else None,
        "p01_guid": guid(p01[0].get_editor_property("passage_guid")) if len(p01) == 1 else None,
        "rails": rails, "music_after_last_apply_meas": "opening START rail 2E86..., p01 SILENCE (opening_sequence_report_apply.json)"}
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    segs = [{"label": str(s.get_editor_property("label")), "start_s": s.get_editor_property("start_frame").value / st,
             "end_s": s.get_editor_property("end_frame").value / st} for s in tr.get_editor_property("segments")]
    report["show"]["segments"] = segs

    # ---------------------------------------------------------------- Master
    scene_secs = sorted([[sec.get_start_frame_seconds(), sec.get_end_frame_seconds(), path(sec.get_sequence())]
                         for t in master.find_tracks_by_exact_type(unreal.MovieSceneInfinitySceneTrack)
                         for sec in t.get_sections()])
    passage_secs, music_secs = {}, {}
    for t in master.get_tracks():
        cls = t.get_class().get_name()
        for sec in t.get_sections():
            if cls == "MovieSceneInfinityPassageTrack":
                passage_secs[guid(sec.get_editor_property("block_guid"))] = [sec.get_start_frame_seconds(),
                                                                              sec.get_end_frame_seconds()]
            elif cls == "MovieSceneInfinityAudioTrack":
                music_secs[guid(sec.get_editor_property("block_guid"))] = {
                    "sound": path(sec.get_sound()), "range_s": [sec.get_start_frame_seconds(), sec.get_end_frame_seconds()]}
    report["master"] = {"scene_sections": scene_secs, "first_section": scene_secs[0] if scene_secs else None,
                        "p01_section": passage_secs.get(report["show"]["p01_guid"]),
                        "opening_music_section": music_secs.get(report["show"]["opening_cue_guid"]),
                        "p01_music_section": music_secs.get(report["show"]["p01_guid"])}

    # ---------------------------------------------------------------- sketch 2 + planner preview
    analysis_path = os.path.join(saved, cfg["analysis"])
    with open(analysis_path, encoding="utf-8") as h:
        analysis = json.load(h)
    planner = {"__name__": "opening_sequence_plan", "__file__": os.path.join(here, "opening_sequence_plan.py")}
    with open(planner["__file__"], encoding="utf-8") as h:
        exec(compile(h.read(), planner["__file__"], "exec"), planner)
    last = record.get("last_applied_frames") if record.get("status") == "applied" else None
    report["sketch2"] = {"analysis": cfg["analysis"], "duration_s": float(analysis["durationSeconds"]),
                         "preview": planner_preview(planner, cfg, analysis,
                                                    os.path.join(saved, "CodexCameraPilot", "walkin_plan.py"),
                                                    markers, last, playback[1], fps)}

    seg = {s["label"]: s for s in segs}
    so = seg.get(cfg["cue_label"])
    sp = seg.get(cfg["next_passage_label"])
    facts = {"fps": fps, "playback": playback, "seg_opening": [so["start_s"], so["end_s"]] if so else None,
             "master_opening": scene_secs[0][:2] if scene_secs else None,
             "seg_p01": [sp["start_s"], sp["end_s"]] if sp else None, "master_p01": report["master"]["p01_section"],
             "music_opening": report["master"]["opening_music_section"], "cut": cut, "curtain": curtain,
             "rig_section_ends": rig_ends, "walk_section_ends": walk_ends,
             "music_s": report["sketch2"]["duration_s"]}
    report["findings"] = drift_findings(facts)
    edited = [k for k, v in report["rig"]["status"].items() if v != "match"]
    report["reconcile_inputs"] = {
        "opening_end_seconds_to_pin": round(playback[1] / fps, 4),
        "hand_tuned_tracks_candidates": sorted({k.split("/")[0] for k in edited}),
        "record_refresh_track_hashes": {"walk": report["walk"]["live_digests"], "rig": report["rig"]["live_digests"]},
        "note": "PROPOSAL ONLY. Refreshing the record hashes lets the next APPLY OVERWRITE these edits; listing the "
                "bindings in hand_tuned_tracks KEEPS them (and skips their sketch-2 refit). Gary decides."}

    census1 = census()
    report["census_after"] = census1
    if census1 != census0:
        stop("READ CHANGED THE DIRTY CENSUS %r -> %r (nothing was saved; Don't-Save the listed packages)" % (census0, census1))
    report["ok"] = True
    with open(out_path, "w", encoding="utf-8") as h:
        json.dump(report, h, indent=1, default=str, ensure_ascii=False)
    for level, text in report["findings"]:
        unreal.log("OPENING_READBACK_FINDING|run=%s|%s|%s" % (run, level, text))
    unreal.log("OPENING_READBACK_OK|run=%s|mutated=0|playback=%s|show_opening=%s|master_first=%s|release_s=%s|"
               "landed_s=%s|rig_edited=%d|findings=%d|report=%s"
               % (run, playback, facts["seg_opening"], facts["master_opening"], curtain.get("release_s"),
                  curtain.get("landed_s"), len(edited), len(report["findings"]), out_path))


if unreal is not None:
    main()
