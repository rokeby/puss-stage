"""The long Opening (Gary, 4 Oct ~01:00): DRY / APPLY / REVERT. Drafted offline 4 Oct; NEVER RUN LIVE YET.

Plan and phase table: Docs/Conductor/OPENING_SEQUENCE_PLAN_2026-10-04.md. Pure planning lives in
opening_sequence_plan.py (offline harness: test_opening_sequence.py). Timing table: opening_timing.json.

Mode: the global OPENING_MODE (DRY default; APPLY; REVERT), set by the wrappers
opening_sequence_{dry,apply,revert}_run.py through ExecuteProjectPythonFile. Run id: OPENING_RUN_ID.

What APPLY writes (and REVERT undoes, from the first apply's snapshot in opening_sequence_record.json):
  LS_Opening_Curtain_Baked
    - playback end 375 -> opening_end (default 2409 = 96.36 s), the one camera cut's end with it, and every
      non-owned section that ended at the old end (the drape's spawn section) — listed in the report;
    - the drape's three GeometryCache sections re-timed (HOLD/FALL/PILE: the FALL starts so the release
      lands at curtain_release; the bake is unchanged; the rule of opening_hold_at_release.py);
    - the walk-in tracks 'WalkIn (Look & camera)' replaced by a walk ending exactly at opening_end
      (walkin_plan.py, Look & camera's planner, unchanged), keys compressed to [frame 0] + the moving block;
    - the Opening rig: possessable bindings to level SpotLight actors 'Opening Rig - <name>' with an
      'OpeningRig (Conductor)' Intensity track (component) and, for movers, a transform track;
    - marked frames 'OPN <moment>' for every moment (the manual-tuning handles).
  The level: the rig actors (created once; level default intensity 0, parked aim), then save_map.
  The Show: the Opening cue's Scene.Music takes P01's rail; P01's Music becomes Silence (flag in the JSON);
    the two House warmers disabled ONLY when house_warmers.disable is true AND decided_by is set.
  The Master: rebuilt with the library call. Patch K (built; PassageKeysFollowSection Success,
    Saved/Logs/SS-FullInfinityStage-20261002.log:2776) carries Passage keys; this tool MEASURES that the
    carry happened for this Show (every Passage section's keys, section-relative, identical before/after)
    and saves NOTHING if not.

Why not extend_scene_playback.py directly: it supports Sequence cues, but its key gate REFUSES whenever a
later Passage carries a varying channel, and P01 does (its wing score: Saved/CodexConductor/
p01_score_shift_report.json). The gate predates patch K. This tool reuses that script's helper functions
(loaded from its source, never edited) and replaces the gate with the measured carry check.

Rules kept: no PIE (refuse; never end it); right project + world; 0 dirty before APPLY/REVERT; backups of
every touched package first; nothing saved unless every pre-save assertion passed; saves name exact
packages (never Save All); no Sequencer UI, evaluation or scrub; never reload the level; no Unreal objects
in module globals; success marker only after asserted read-back. Afterwards run, ONE AT A TIME:
run_saved_master_test_request.json, then run_scene_cut_test_request.json, and read each result in the log.
If APPLY stops after a mutation and before its saves: nothing was saved; discard with a Don't-Save restart.
"""

MODE = str(globals().get("OPENING_MODE", "DRY")).upper()


def main(mode):
    import datetime
    import hashlib
    import json
    import os
    import shutil

    import unreal

    SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
    MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
    WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
    DRAPE = "Opening Drape (baked)"
    WALK_TRACK = "WalkIn (Look & camera)"
    RIG_TRACK = "OpeningRig (Conductor)"
    RIG_PREFIX = "Opening Rig - "
    RIG_TAG = "InfinityStage.OpeningRig"
    run = str(globals().get("OPENING_RUN_ID", datetime.datetime.now().strftime("OPENING-%Y%m%d-%H%M%S")))
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    here = os.path.join(saved, "CodexConductor")
    report_path = os.path.join(here, "opening_sequence_report_%s.json" % mode.lower())
    report = {"run": run, "mode": mode, "ok": False, "steps": []}

    def write_report():
        with open(report_path, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str, ensure_ascii=False)

    def fail(msg):
        report["error"] = str(msg)
        write_report()
        full = "PUSS_OPENING_STOPPED|run=%s|mode=%s|%s" % (run, mode, msg)
        unreal.log_error(full)
        raise RuntimeError(full)

    def step(name, **kw):
        report["steps"].append(dict(step=name, **kw))

    def census():
        return {"content": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
                "maps": sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}

    def content_file(path, ext=".uasset"):
        return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ext

    def unwrap(result, count, label):
        if result is None:
            fail(label + " returned None")
        if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
            if not result[0]:
                fail(label + " returned false")
            result = result[1:]
        if not isinstance(result, tuple) or len(result) != count:
            fail("%s returned unexpected %r" % (label, result))
        return result

    # ------------------------------------------------------------------ guards
    if os.path.normcase(os.path.normpath(project)).rstrip("\\/") != os.path.normcase("e:\\pussstage"):
        fail("wrong project %s" % project)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        fail("PIE/SIE is active (this tool never ends it)")
    world = editor.get_editor_world()
    if world is None or world.get_outermost().get_name() != WORLD:
        fail("wrong editor world")
    dirty0 = census()
    report["dirty_before"] = dirty0
    if mode in ("APPLY", "REVERT") and (dirty0["content"] or dirty0["maps"]):
        fail("refusing: dirty packages before %s: %r" % (mode, dirty0))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    # ------------------------------------------------------------------ planner + extend helpers (no globals)
    planner = {"__name__": "opening_sequence_plan", "__file__": os.path.join(here, "opening_sequence_plan.py")}
    with open(planner["__file__"], "r", encoding="utf-8") as h:
        exec(compile(h.read(), planner["__file__"], "exec"), planner)
    ext_path = os.path.join(saved, "CodexSoftGoods", "extend_scene_playback.py")
    with open(ext_path, "r", encoding="utf-8") as h:
        ext_src = h.read()
    if not ext_src.rstrip().endswith("\nmain()"):
        fail("extend_scene_playback.py no longer ends with main(); refusing to load its helpers")
    ext = {"__name__": "extend_scene_playback_helpers", "__file__": ext_path}
    exec(compile(ext_src.rstrip()[:-len("main()")], ext_path, "exec"), ext)
    for need in ("cut_coverage", "compiled_segments", "show_master_match", "segment_deltas"):
        if need not in ext:
            fail("extend helper %s missing" % need)

    paths = planner["default_paths"](saved)
    with open(paths["timing"], "r", encoding="utf-8") as h:
        cfg = json.load(h)
    analysis = planner["load_json"](os.path.join(saved, cfg["analysis"]))
    record = None
    if os.path.isfile(paths["record"]):
        with open(paths["record"], "r", encoding="utf-8") as h:
            record = json.load(h)
    fps_cfg = float(cfg["fps"])

    show = unreal.load_asset(SHOW)
    master = unreal.load_asset(MASTER)
    seq = unreal.load_asset(cfg["sequence"])
    if show is None or master is None or seq is None:
        fail("Show, Master or Opening sequence did not load")
    rate = seq.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    tick = seq.get_tick_resolution()
    tps = tick.numerator / float(tick.denominator)
    tpf = tps / fps
    if abs(fps - fps_cfg) > 1e-6 or abs(tpf - round(tpf)) > 1e-9:
        fail("Opening rate %.3f fps / %.1f ticks/s does not match the timing table" % (fps, tps))
    tpf = int(round(tpf))

    # ------------------------------------------------------------------ the Opening cue + P01 row
    cues = list(show.get_editor_property("cues"))
    opening_idx = [i for i, c in enumerate(cues) if str(c.get_editor_property("label")) == cfg["cue_label"]]
    if len(opening_idx) != 1:
        fail("expected one '%s' cue, found %d" % (cfg["cue_label"], len(opening_idx)))
    oc = cues[opening_idx[0]]
    if str(oc.get_editor_property("type")) != str(unreal.InfinityCueType.SEQUENCE):
        fail("the Opening cue is not a Sequence cue")
    oscene = oc.get_editor_property("scene")
    if oscene.get_editor_property("sequence") is None or \
            oscene.get_editor_property("sequence").get_path_name().split(".")[0] != cfg["sequence"]:
        fail("the Opening cue does not point at %s" % cfg["sequence"])
    try:
        use_len = bool(oscene.get_editor_property("use_sequence_length"))
    except Exception as exc:  # noqa: BLE001
        use_len = "unreadable: %s" % exc
    step("opening_cue", index=opening_idx[0], use_sequence_length=use_len)
    psets = list(show.get_editor_property("passage_settings"))
    p01_idx = [i for i, p in enumerate(psets) if str(p.get_editor_property("label")) == cfg["next_passage_label"]]
    if len(p01_idx) != 1:
        fail("expected one %s row, found %d" % (cfg["next_passage_label"], len(p01_idx)))

    def music_state(binding):
        return {"mode": str(binding.get_editor_property("mode")),
                "rail": unreal.GuidLibrary.conv_guid_to_string(binding.get_editor_property("primary_rail_guid")),
                "offset": int(binding.get_editor_property("rail_offset_frames").value)}

    music_now = {"opening": music_state(oscene.get_editor_property("music")),
                 "p01": music_state(psets[p01_idx[0]].get_editor_property("music"))}
    step("music_now", **music_now)

    # ------------------------------------------------------------------ live sequence facts
    def bindings_named(name):
        return [b for b in seq.get_bindings() if str(b.get_display_name()) == name]

    def all_track_hosts():
        hosts = [("<root>", seq, t) for t in seq.get_tracks()]
        for b in seq.get_bindings():
            hosts += [(str(b.get_display_name()), b, t) for t in b.get_tracks()]
        return hosts

    drapes = bindings_named(DRAPE)
    if len(drapes) != 1:
        fail("expected one '%s' binding, found %d" % (DRAPE, len(drapes)))
    gc_tracks = [t for t in drapes[0].get_tracks() if t.get_class().get_name() == "MovieSceneGeometryCacheTrack"]
    gc_secs = sorted(gc_tracks[0].get_sections(), key=lambda s: s.get_start_frame()) if len(gc_tracks) == 1 else []
    if len(gc_secs) != 3:
        fail("expected one GC track with 3 sections")

    def gc_state():
        out = []
        for s in gc_secs:
            p = s.get_editor_property("params")
            out.append([s.get_start_frame(), s.get_end_frame(), p.get_editor_property("start_frame_offset").value,
                        p.get_editor_property("end_frame_offset").value])
        return out

    cache = gc_secs[1].get_editor_property("params").get_editor_property("geometry_cache_asset")
    if cache is None or cache.get_path_name().split(".")[0] != cfg["curtain"]["cache"]:
        fail("the FALL section does not play %s" % cfg["curtain"]["cache"])
    src = os.path.basename(cache.get_editor_property("asset_import_data").get_first_filename())
    stem = cfg["curtain"]["cache"].split("/")[-1] + "_"
    bake_id = src[len(stem):-4] if src.startswith(stem) and src.endswith(".abc") else None
    if bake_id != cfg["curtain"]["bake_id"]:
        fail("cache import source %s is not bake %s" % (src, cfg["curtain"]["bake_id"]))
    with open(os.path.join(saved, "CodexSoftGoods", "DropBake", bake_id + ".json"), encoding="utf-8") as h:
        bake = json.load(h)
    cfps = float(cfg["curtain"]["cache_fps"])
    live_curtain = {
        "release_frame": int(bake["release_frame"]),
        "release_in_cache_s": (bake["release_frame"] - bake["show_start"]) / cfps,
        "cache_duration_ticks": int(round((cache.get_editor_property("end_frame") - cache.get_editor_property("start_frame")) / cfps * tps)),
    }
    for k, v in live_curtain.items():
        if abs(float(v) - float(cfg["curtain"][k])) > 1e-6:
            fail("curtain fact %s live %r != timing table %r" % (k, v, cfg["curtain"][k]))
    step("curtain_live", bake=bake_id, gc_sections=gc_state(), **live_curtain)

    cut_tracks = [t for t in seq.get_tracks() if t.get_class().get_name() == "MovieSceneCameraCutTrack"]
    cut_secs = [s for t in cut_tracks for s in t.get_sections() if s.is_active()]
    if len(cut_secs) != 1:
        fail("expected one active camera cut section, found %d" % len(cut_secs))
    cut = cut_secs[0]
    cut_guid = unreal.GuidLibrary.conv_guid_to_string(cut.get_camera_binding_id().get_editor_property("guid"))
    cam_bindings = [b for b in seq.get_bindings() if unreal.GuidLibrary.conv_guid_to_string(b.get_id()) == cut_guid]
    if len(cam_bindings) != 1:
        fail("camera cut binding resolves to %d bindings" % len(cam_bindings))
    cam_binding = cam_bindings[0]
    bound = list(seq.locate_bound_objects(cam_binding, world))
    if len(bound) != 1 or not isinstance(bound[0], unreal.CineCameraActor):
        fail("the cut camera does not resolve to one CineCameraActor")
    camera = bound[0]
    cam_comp = camera.get_cine_camera_component()
    comp_bindings = [c for c in cam_binding.get_child_possessables()
                     if any(o.get_path_name() == cam_comp.get_path_name() for o in seq.locate_bound_objects(c, world))]
    if len(comp_bindings) > 1:
        fail("camera has %d component bindings" % len(comp_bindings))
    comp_binding = comp_bindings[0] if comp_bindings else None

    # P01 start pose + arrival speed, measured the way key_walkin_i1_p02.py does
    lib = unreal.InfinityStageCameraPilotLibrary
    pguid = psets[p01_idx[0]].get_editor_property("passage_guid")
    p_start, p_end = unwrap(lib.get_passage_frame_range(show, pguid), 2, "get_passage_frame_range")
    view0, focal1, focus1 = unwrap(lib.get_passage_camera_pose(show, pguid, int(p_start)), 3, "pose(start)")
    view1, _, _ = unwrap(lib.get_passage_camera_pose(show, pguid, int(p_start) + tpf), 3, "pose(start+1)")
    v_end = (view1.translation - view0.translation).length() / (tpf / tps)
    sl, sr = camera.get_actor_location(), camera.get_actor_rotation()
    tl, tr_ = view0.translation, view0.rotation.rotator()
    fs = cam_comp.get_editor_property("focus_settings")
    if any(t.get_class().get_name() == "MovieScene3DTransformTrack" and str(t.get_display_name()) == WALK_TRACK
           for t in cam_binding.get_tracks()):
        # the seat is keyed already: read the seat from the planner record, never from an evaluated actor
        seat_live = None
    else:
        seat_live = {"x": sl.x, "y": sl.y, "z": sl.z, "pitch": sr.pitch, "yaw": sr.yaw, "roll": sr.roll}
    live_walk = {"target": {"x": tl.x, "y": tl.y, "z": tl.z, "pitch": tr_.pitch, "yaw": tr_.yaw, "roll": tr_.roll},
                 "v_end_cm_s": v_end, "focal1_mm": float(focal1), "focus1_cm": float(focus1)}
    if seat_live:
        live_walk["seat"] = seat_live
        live_walk["focal0_mm"] = float(cam_comp.get_editor_property("current_focal_length"))
        live_walk["focus0_cm"] = float(fs.get_editor_property("manual_focus_distance"))
    drift = {}
    for k, v in live_walk.items():
        if isinstance(v, dict):
            d = max(abs(float(v[a]) - float(cfg["walkin"][k][a])) for a in v)
        else:
            d = abs(float(v) - float(cfg["walkin"][k]))
        drift[k] = d
        cfg["walkin"][k] = v                   # measured beats tabled
    step("walk_live", p01_range_ticks=[int(p_start), int(p_end)], drift_vs_table=drift, seat_from="live" if seat_live else "table")
    if max(drift.values()) > 1.0:
        fail("P01 start / seat drifted > 1 unit from the timing table: %r (re-measure before applying)" % drift)

    # ------------------------------------------------------------------ markers (API resolved at run time)
    unit = unreal.MovieSceneTimeUnit

    def read_markers():
        if hasattr(seq, "get_marked_frames_from_sequence"):
            raw = seq.get_marked_frames_from_sequence(unit.DISPLAY_RATE)
            return [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)] for m in raw], "display"
        raw = seq.get_marked_frames()
        out = []
        for m in raw:
            t = int(m.get_editor_property("frame_number").value)
            out.append([str(m.get_editor_property("label")), t // tpf if t % tpf == 0 else t / float(tpf)])
        return out, "ticks"

    def write_markers(rows):
        """Delete every OPN marker, then add rows [[label, frame]]. Foreign markers are left alone."""
        current, _ = read_markers()
        for i in sorted([i for i, m in enumerate(current) if m[0].startswith(planner["MARKER_PREFIX"])], reverse=True):
            seq.delete_marked_frame(i)
        for label, frame in rows:
            mf = unreal.MovieSceneMarkedFrame()
            mf.set_editor_property("label", label)
            try:
                mf.set_editor_property("comment", "opening_sequence_apply %s" % run)
            except Exception:  # noqa: BLE001
                pass
            if hasattr(seq, "add_marked_frame_to_sequence"):
                mf.set_editor_property("frame_number", unreal.FrameNumber(int(frame)))
                seq.add_marked_frame_to_sequence(mf, unit.DISPLAY_RATE)
            else:
                mf.set_editor_property("frame_number", unreal.FrameNumber(int(frame) * tpf))
                seq.add_marked_frame(mf)
        if hasattr(seq, "sort_marked_frames"):
            seq.sort_marked_frames()

    markers_now, marker_api = read_markers()
    step("markers_now", api=marker_api, markers=markers_now)
    non_integral = [m for m in markers_now if m[0].startswith(planner["MARKER_PREFIX"]) and not isinstance(m[1], int)]
    if non_integral:
        fail("OPN markers off the display-frame grid: %r (snap them to whole frames)" % non_integral)

    # ------------------------------------------------------------------ owned-track readers
    def float_keys(channel):
        return [[int(k.get_time().frame_number.value), round(float(k.get_value()), 4)] for k in channel.get_keys()]

    def named_tracks(name):
        return [(host_name, host, t) for host_name, host, t in all_track_hosts() if str(t.get_display_name()) == name]

    def track_key(host_name, t, ch):
        """'<binding>/<track class>/<channel or property>' - float tracks are named by their PROPERTY
        (CurrentFocalLength, ManualFocusDistance, Intensity), transform channels by channel name."""
        cls = t.get_class().get_name()
        if cls == "MovieSceneFloatTrack":
            return "%s/%s/%s" % (host_name, cls, str(t.get_property_name()))
        return "%s/%s/%s" % (host_name, cls, str(ch.channel_name))

    def read_named(name):
        out = {}
        for host_name, _, t in named_tracks(name):
            for s in t.get_sections():
                for ch in s.get_all_channels():
                    keys = float_keys(ch)
                    if keys:
                        out[track_key(host_name, t, ch)] = keys
        return out

    def read_walk():
        return read_named(WALK_TRACK)

    def rig_actor(name):
        hits = [a for a in actors.get_all_level_actors() if a.get_actor_label() == RIG_PREFIX + name]
        if len(hits) > 1:
            fail("duplicate rig actor %s" % name)
        return hits[0] if hits else None

    def read_rig():
        return read_named(RIG_TRACK)

    def digest(rows):
        return hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    def tail_sections(old_end):
        """Non-owned sections ending at the old end (or one past it, as key_walkin's ranges do)."""
        rows = []
        for host_name, host, t in all_track_hosts():
            cls = t.get_class().get_name()
            if cls in ("MovieSceneCameraCutTrack", "MovieSceneGeometryCacheTrack") or \
                    str(t.get_display_name()) in (WALK_TRACK, RIG_TRACK):
                continue
            for i, s in enumerate(t.get_sections()):
                if s.has_end_frame() and s.get_end_frame() in (old_end, old_end + 1):
                    rows.append({"host": host_name, "track": cls, "index": i, "range": [s.get_start_frame(), s.get_end_frame()],
                                 "section": s})
        return rows

    def master_passage_keys():
        out = {}
        for track in master.get_tracks():
            if "InfinityPassage" not in track.get_class().get_name():
                continue
            for sec in track.get_sections():
                start_tick = int(round(sec.get_start_frame_seconds() * 24000.0))
                rows = {}
                for ch in sec.get_all_channels():
                    keys = [[int(k.get_time(time_unit=unit.TICK_RESOLUTION).frame_number.value) - start_tick,
                             round(float(k.get_value()), 6)] for k in ch.get_keys()]
                    if keys:
                        rows[str(ch.get_editor_property("channel_name"))] = keys
                out[str(sec.get_editor_property("passage_guid"))] = {"start_s": round(sec.get_start_frame_seconds(), 4), "keys": rows}
        return out

    # ------------------------------------------------------------------ snapshot (first apply only)
    old_end = seq.get_playback_end()
    snapshot_now = {
        "playback": [seq.get_playback_start(), old_end],
        "cut": [cut.get_start_frame(), cut.get_end_frame()],
        "gc_sections": gc_state(),
        "tail_sections": [{k: v for k, v in r.items() if k != "section"} for r in tail_sections(old_end)],
        "walk": read_walk(),
        "rig": read_rig(),
        "markers": markers_now,
        "music": music_now,
        "rig_actors": sorted(a.get_actor_label() for a in actors.get_all_level_actors()
                             if a.get_actor_label().startswith(RIG_PREFIX)),
    }
    report["snapshot_now"] = snapshot_now

    # hand edits since the last apply. hand_tuned_tracks lists BINDING names (the first part of a track key):
    # the camera's two bindings for the walk-in, 'Opening Rig - <name>' for a lamp. Those are left untouched.
    hand = set(cfg.get("hand_tuned_tracks", []))

    def host_of(key):
        return key.split("/")[0]

    walk_hosts = sorted({host_of(k) for k in snapshot_now["walk"]})
    walk_hand = bool(set(walk_hosts) & hand)
    if record and record.get("status") == "applied":
        edited = []
        for kind, rows in (("walk", snapshot_now["walk"]), ("rig", snapshot_now["rig"])):
            old = record["track_hashes"].get(kind, {})
            for key in sorted(set(rows) | set(old)):
                if old.get(key) != (digest(rows[key]) if key in rows else None) and host_of(key) not in hand:
                    edited.append(key)
        report["hand_edited_tracks"] = edited
        if edited and mode == "APPLY" and not cfg.get("overwrite_hand_edits", False):
            fail("tracks were edited by hand in Sequencer since the last apply: %r. Add their binding names to "
                 "hand_tuned_tracks to keep them, or set overwrite_hand_edits true to discard them." % edited)

    report["segments_before"] = ext["compiled_segments"](show)
    report["master_keys_before"] = master_passage_keys()

    # ------------------------------------------------------------------ plan
    if mode != "REVERT":
        marker_moments = planner["markers_to_moments"](markers_now)
        last = record.get("last_applied_frames") if record and record.get("status") == "applied" else None
        plan = planner["build_plan"](cfg, analysis, paths["walk_planner"], marker_moments, last)
        report["plan"] = {k: plan[k] for k in ("frames", "seconds", "sources", "reasons", "conflicts", "writeback",
                                               "swells", "curtain", "master_delta_s", "failures")}
        report["plan"]["walkin"] = {k: v for k, v in plan["walkin"].items() if k != "keys"}
        report["plan"]["walkin"]["key_count"] = len(plan["walkin"]["keys"])
        report["plan"]["lamps"] = {n: {"intensity_keys": len(l["intensity"]), "rotation_keys": len(l["rotation"])}
                                   for n, l in plan["lamps"].items()}
        moved_derived = [n for n, f in marker_moments.items()
                         if n in planner["DERIVED_MOMENTS"] and last and f != plan["frames"].get(n)]
        report["plan"]["moved_derived_markers_put_back"] = moved_derived
        if plan["failures"]:
            fail("plan failures: %r" % plan["failures"])
        new_end = plan["frames"]["opening_end"]
        tails = tail_sections(old_end)
        report["tail_sections_to_extend"] = [{k: v for k, v in r.items() if k != "section"} for r in tails]
        ws = cfg["house_warmers"]
        warmers_write = bool(ws.get("disable")) and bool(ws.get("decided_by"))
        report["house_warmers_write"] = warmers_write
        if not warmers_write:
            report.setdefault("warnings", []).append(
                "house warmers stay ON (not decided): phase 0 is not dark until Gary decides house_warmers.disable")
        if mode == "DRY":
            report["ok"] = True
            write_report()
            unreal.log("PUSS_OPENING_DRY|run=%s|end=%d|delta_s=%.3f|release_s=%.3f|walk=%.3f-%.3f|markers_api=%s|report=%s"
                       % (run, new_end, plan["master_delta_s"], plan["curtain"]["release_s"], plan["walkin"]["start_s"],
                          plan["walkin"]["end_s"], marker_api, report_path))
            return

    if mode == "REVERT" and (not record or "original" not in record):
        fail("no first-apply snapshot to revert to (%s)" % paths["record"])
    if mode == "DRY":
        return

    # ------------------------------------------------------------------ backups + intent record (before any mutation)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    backup = os.path.join(project, "Backups", "PreOpeningSequence%s-%s" % ("Revert" if mode == "REVERT" else "", stamp))
    os.makedirs(backup, exist_ok=False)
    for p in (SHOW, MASTER, cfg["sequence"]):
        shutil.copy2(content_file(p), backup)
    shutil.copy2(content_file(WORLD, ".umap"), backup)
    for p in (paths["timing"], paths["record"]):
        if os.path.isfile(p):
            shutil.copy2(p, backup)
    for p in (SHOW, MASTER, cfg["sequence"]):
        if os.path.getsize(os.path.join(backup, os.path.basename(content_file(p)))) != os.path.getsize(content_file(p)):
            fail("backup size mismatch for %s" % p)
    report["backup"] = backup
    if record is None:
        record = {"version": 1, "sequence": cfg["sequence"], "status": "applying", "original": snapshot_now,
                  "first_run": run, "runs": []}
    record["runs"].append({"run": run, "mode": mode, "backup": backup, "at": stamp})
    record["status"] = "applying" if mode == "APPLY" else "reverting"
    with open(paths["record"], "w", encoding="utf-8") as h:
        json.dump(record, h, indent=1, default=str, ensure_ascii=False)
        h.flush()
        os.fsync(h.fileno())

    # ------------------------------------------------------------------ write helpers
    import re

    def remove_named(name, keep_hosts=()):
        removed = []
        for host_name, host, t in named_tracks(name):
            if host_name in keep_hosts:
                continue
            if not host.remove_track(t):
                fail("remove_track failed on %s" % host_name)
            removed.append(host_name)
        return removed

    def add_float_track(binding, prop, path, keys, end_frame, display, interp_of=None):
        track = binding.add_track(unreal.MovieSceneFloatTrack)
        if track is None:
            fail("add float track %s" % path)
        track.set_property_name_and_path(unreal.Name(prop), path)
        track.set_display_name(display)
        sec = track.add_section()
        sec.set_range(0, end_frame + 1)
        ch = list(sec.get_all_channels())
        if len(ch) != 1:
            fail("%s has %d channels" % (path, len(ch)))
        for k in keys:
            how = interp_of(k) if interp_of else unreal.MovieSceneKeyInterpolation.LINEAR
            if ch[0].add_key(unreal.FrameNumber(int(k[0])), float(k[1]), time_unit=unit.DISPLAY_RATE, interpolation=how) is None:
                fail("add_key %s frame %d" % (path, k[0]))
        return track

    def transform_track(binding, name, end_frame, chan_keys, interp, scale=(1.0, 1.0, 1.0)):
        track = binding.add_track(unreal.MovieScene3DTransformTrack)
        if track is None:
            fail("add transform track on %s" % binding.get_display_name())
        track.set_display_name(name)
        sec = track.add_section()
        sec.set_range(0, end_frame + 1)
        chans = {str(c.channel_name): c for c in sec.get_all_channels()}
        for i, n in enumerate(("Scale.X", "Scale.Y", "Scale.Z")):
            if n not in chans:
                fail("transform channel %s missing" % n)
            chans[n].set_default(float(scale[i]))
        for n, keys in chan_keys.items():
            if n not in chans:
                fail("transform channel %s missing" % n)
            for f, v in keys:
                if chans[n].add_key(unreal.FrameNumber(int(f)), float(v), time_unit=unit.DISPLAY_RATE, interpolation=interp) is None:
                    fail("add_key %s %d" % (n, f))
        return track

    def key_walk(ch, end_frame):
        """ch: {'Location.X': [[f, v]], ..., 'focal': [...], 'focus': [...]} (display frames)."""
        nonlocal comp_binding
        s3 = camera.get_actor_scale3d()
        transform_track(cam_binding, WALK_TRACK, end_frame,
                        {n: ch[n] for n in ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z")},
                        unreal.MovieSceneKeyInterpolation.LINEAR, scale=(s3.x, s3.y, s3.z))
        if comp_binding is None:
            comp_binding = seq.add_possessable(cam_comp)
            if comp_binding is None or not comp_binding.is_valid():
                fail("could not bind the CineCameraComponent")
            comp_binding.set_parent(cam_binding)
        add_float_track(comp_binding, "CurrentFocalLength", "CurrentFocalLength", ch["focal"], end_frame, WALK_TRACK)
        add_float_track(comp_binding, "ManualFocusDistance", "FocusSettings.ManualFocusDistance", ch["focus"], end_frame, WALK_TRACK)

    def walk_channels_from_plan(keys):
        idx = {"Location.X": 1, "Location.Y": 2, "Location.Z": 3, "Rotation.X": 6, "Rotation.Y": 4, "Rotation.Z": 5,
               "focal": 7, "focus": 8}
        return {n: [[int(round(k[0] * fps)), k[i]] for k in keys] for n, i in idx.items()}

    def channel_of_key(key):
        last = key.split("/")[-1]
        return "focal" if last == "CurrentFocalLength" else "focus" if last == "ManualFocusDistance" else last

    def walk_channels_from_snapshot(rows):
        out = {channel_of_key(key): keys for key, keys in rows.items()}
        if sorted(out) != sorted(["Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z", "focal", "focus"]):
            fail("original walk snapshot has channels %r" % sorted(out))
        return out

    def set_section_end(section, end):
        section.set_range(section.get_start_frame(), int(end))

    def set_gc(rows):
        for s, (a, b, so, eo) in zip(gc_secs, rows):
            s.set_range(int(a), int(b))
            p = s.get_editor_property("params")
            p.set_editor_property("start_frame_offset", unreal.FrameNumber(int(so)))
            p.set_editor_property("end_frame_offset", unreal.FrameNumber(int(eo)))
            s.set_editor_property("params", p)

    def parse_guid(text):
        res = unreal.GuidLibrary.parse_string_to_guid(text)
        guid, ok = (res if isinstance(res, tuple) else (res, True))
        if not ok or unreal.GuidLibrary.conv_guid_to_string(guid) != text:
            fail("cannot parse guid %s" % text)
        return guid

    def binding_from_state(state):
        token = re.search(r"\.([A-Z_]+)", state["mode"])
        if not token:
            fail("cannot parse music mode %r" % state["mode"])
        m = unreal.InfinitySectionMusicBinding()
        m.set_editor_property("mode", getattr(unreal.InfinityMusicBindingMode, token.group(1)))
        m.set_editor_property("primary_rail_guid", parse_guid(state["rail"]))
        m.set_editor_property("rail_offset_frames", unreal.FrameNumber(int(state["offset"])))
        return m

    def set_music(target):
        """target: {'opening': {mode, rail, offset}, 'p01': {...}} - exact states; secondary rails untouched."""
        show.modify()
        cues_ = list(show.get_editor_property("cues"))
        psets_ = list(show.get_editor_property("passage_settings"))
        c = cues_[opening_idx[0]]
        sc = c.get_editor_property("scene")
        old = sc.get_editor_property("music")
        new = binding_from_state(target["opening"])
        new.set_editor_property("secondary_rail_guid", old.get_editor_property("secondary_rail_guid"))
        sc.set_editor_property("music", new)
        c.set_editor_property("scene", sc)
        cues_[opening_idx[0]] = c
        ps = psets_[p01_idx[0]]
        old = ps.get_editor_property("music")
        new = binding_from_state(target["p01"])
        new.set_editor_property("secondary_rail_guid", old.get_editor_property("secondary_rail_guid"))
        ps.set_editor_property("music", new)
        psets_[p01_idx[0]] = ps
        show.set_editor_property("cues", cues_)
        show.set_editor_property("passage_settings", psets_)

    def music_after():
        c = list(show.get_editor_property("cues"))[opening_idx[0]]
        p = list(show.get_editor_property("passage_settings"))[p01_idx[0]]
        return {"opening": music_state(c.get_editor_property("scene").get_editor_property("music")),
                "p01": music_state(p.get_editor_property("music"))}

    def warmers_state():
        labels = set(cfg["house_warmers"]["labels"])
        out = {}
        for c in show.get_editor_property("cues"):
            for a in c.get_editor_property("wing_pair").get_editor_property("attachments"):
                if str(a.get_editor_property("label")) in labels:
                    out[str(a.get_editor_property("label"))] = bool(a.get_editor_property("enabled"))
        return out

    def set_warmers(enabled):
        labels = set(cfg["house_warmers"]["labels"])
        show.modify()
        cues_ = list(show.get_editor_property("cues"))
        hits = 0
        for i, c in enumerate(cues_):
            pair = c.get_editor_property("wing_pair")
            atts = list(pair.get_editor_property("attachments"))
            changed = False
            for j, a in enumerate(atts):
                label = str(a.get_editor_property("label"))
                if label in labels:
                    a.set_editor_property("enabled", bool(enabled[label]))
                    atts[j] = a
                    changed = True
                    hits += 1
            if changed:
                pair.set_editor_property("attachments", atts)
                c.set_editor_property("wing_pair", pair)
                cues_[i] = c
        if hits != len(labels):
            fail("found %d of %d house warmers" % (hits, len(labels)))
        show.set_editor_property("cues", cues_)
        passage = [a for a in actors.get_all_level_actors()
                   if isinstance(a, unreal.InfinityStagePassageActor) and a.get_actor_label().startswith("Passage 01")]
        if len(passage) != 1 or not passage[0].materialize_passage():
            fail("Passage 01 did not materialize")
        for a in actors.get_all_level_actors():
            if isinstance(a, unreal.InfinityStageStructureActor) and a.get_editor_property("passage") == passage[0]:
                if not a.materialize_structure():
                    fail("Structure 01 did not re-fit")
        if warmers_state() != {l: bool(v) for l, v in enabled.items()}:
            fail("house warmers did not land: %r" % warmers_state())

    def setp(obj, name, value):
        """Set only when different, so a re-run does not dirty the level for nothing."""
        cur = obj.get_editor_property(name)
        same = (abs(float(cur) - float(value)) < 1e-6) if isinstance(value, float) else (cur == value)
        if not same:
            obj.set_editor_property(name, value)

    def ensure_rig_actor(fx):
        a = rig_actor(fx["name"])
        loc = unreal.Vector(*fx["location"])
        fin, off = fx["final_aim"], fx.get("park_offset", {"pitch": 0.0, "yaw": 0.0})
        rot = unreal.Rotator(roll=fin.get("roll", 0.0), pitch=fin["pitch"] + off["pitch"], yaw=fin["yaw"] + off["yaw"])
        created = a is None
        if created:
            a = actors.spawn_actor_from_class(unreal.SpotLight, loc, rot)
            if a is None:
                fail("could not spawn rig actor %s" % fx["name"])
            a.set_actor_label(RIG_PREFIX + fx["name"])
            a.set_editor_property("tags", [unreal.Name(RIG_TAG), unreal.Name(RIG_TAG + "." + fx["name"].replace(" ", ""))])
        else:
            if (a.get_actor_location() - loc).length() > 0.01:
                a.set_actor_location(loc, False, False)
            r0 = a.get_actor_rotation()
            if max(abs(r0.pitch - rot.pitch), abs(r0.yaw - rot.yaw), abs(r0.roll - rot.roll)) > 1e-3:
                a.set_actor_rotation(rot, False)
        c = a.get_editor_property("spot_light_component")
        if c.get_editor_property("mobility") != unreal.ComponentMobility.MOVABLE:
            c.set_mobility(unreal.ComponentMobility.MOVABLE)
        setp(c, "intensity_units", unreal.LightUnits.CANDELAS)
        setp(c, "intensity", 0.0)                       # dark wherever the Opening is not driving it
        setp(c, "use_temperature", True)
        setp(c, "temperature", float(fx["kelvin"]))
        setp(c, "outer_cone_angle", float(fx["outer_cone_deg"]))
        setp(c, "inner_cone_angle", float(fx["inner_cone_deg"]))
        setp(c, "attenuation_radius", float(fx["attenuation_radius_cm"]))
        setp(c, "cast_shadows", bool(fx["cast_shadows"]))
        setp(c, "volumetric_scattering_intensity", float(fx["volumetric_scattering"]))
        return a, created

    def rig_binding(a):
        existing = [b for b in seq.get_bindings()
                    if any(o.get_path_name() == a.get_path_name() for o in seq.locate_bound_objects(b, world))]
        if len(existing) > 1:
            fail("rig actor %s bound %d times" % (a.get_actor_label(), len(existing)))
        b = existing[0] if existing else seq.add_possessable(a)
        if b is None or not b.is_valid():
            fail("could not bind rig actor %s" % a.get_actor_label())
        b.set_display_name(a.get_actor_label())
        comp = a.get_editor_property("spot_light_component")
        kids = [c for c in b.get_child_possessables()
                if any(o.get_path_name() == comp.get_path_name() for o in seq.locate_bound_objects(c, world))]
        if len(kids) > 1:
            fail("rig component bound %d times" % len(kids))
        kb = kids[0] if kids else seq.add_possessable(comp)
        if kb is None or not kb.is_valid():
            fail("could not bind the light component of %s" % a.get_actor_label())
        if not kids:
            kb.set_parent(b)
        kb.set_display_name(a.get_actor_label())
        return b, kb

    # ------------------------------------------------------------------ MUTATE
    if mode == "APPLY":
        end = plan["frames"]["opening_end"]
        seq.modify()
        seq.set_playback_end(end)
        set_section_end(cut, end)
        for r in tails:
            r["section"].set_range(r["range"][0], end + (r["range"][1] - old_end))
        set_gc(plan["curtain"]["sections"])
        if walk_hand:
            report.setdefault("warnings", []).append("walk-in left as hand-tuned (hand_tuned_tracks)")
        else:
            remove_named(WALK_TRACK)
            key_walk(walk_channels_from_plan(plan["walkin"]["keys"]), end)
        remove_named(RIG_TRACK, keep_hosts=hand)
        created = []
        imap = {"constant": unreal.MovieSceneKeyInterpolation.CONSTANT,
                "linear": unreal.MovieSceneKeyInterpolation.LINEAR}
        for fx in cfg["fixtures"]:
            if not fx.get("enabled", True):
                continue
            a, was_created = ensure_rig_actor(fx)
            if was_created:
                created.append(fx["name"])
            if RIG_PREFIX + fx["name"] in hand:
                continue
            b, kb = rig_binding(a)
            lamp = plan["lamps"][fx["name"]]
            add_float_track(kb, "Intensity", "Intensity", [[f, v, i] for f, v, i in lamp["intensity"]], end, RIG_TRACK,
                            interp_of=lambda k: imap[k[2]])
            if lamp["rotation"]:
                L = fx["location"]
                transform_track(b, RIG_TRACK, end, {
                    "Location.X": [[0, L[0]]], "Location.Y": [[0, L[1]]], "Location.Z": [[0, L[2]]],
                    "Rotation.Y": [[r[0], r[1]] for r in lamp["rotation"]],
                    "Rotation.Z": [[r[0], r[2]] for r in lamp["rotation"]],
                    "Rotation.X": [[r[0], r[3]] for r in lamp["rotation"]]},
                    unreal.MovieSceneKeyInterpolation.AUTO)
        disabled_with_actor = [fx["name"] for fx in cfg["fixtures"] if not fx.get("enabled", True) and rig_actor(fx["name"])]
        if disabled_with_actor:
            report.setdefault("warnings", []).append("disabled fixtures still have level actors (left as is, intensity 0): %r"
                                                     % disabled_with_actor)
        step("rig", created=created)
        write_markers(planner["marker_list"](plan))
        music_moved = (cfg["music"]["move_p01_track_to_opening"] and "SILENCE" in music_now["opening"]["mode"].upper()
                       and "SILENCE" not in music_now["p01"]["mode"].upper())
        if music_moved:                     # first time only: later P01 music Gary assigns is never moved
            target = {"opening": dict(music_now["p01"]),
                      "p01": {"mode": "InfinityMusicBindingMode.SILENCE", "rail": music_now["p01"]["rail"],
                              "offset": music_now["p01"]["offset"]}}
            set_music(target)
            step("music_moved", target=target)
        if warmers_write:
            if "warmers_original" not in record:
                record["warmers_original"] = warmers_state()
            set_warmers({l: False for l in cfg["house_warmers"]["labels"]})
    else:  # REVERT
        orig = record["original"]
        end = int(orig["playback"][1])
        seq.modify()
        tails_now = tail_sections(old_end)
        seq.set_playback_end(end)
        set_section_end(cut, int(orig["cut"][1]))
        for r in tails_now:
            match = [o for o in orig["tail_sections"] if o["host"] == r["host"] and o["track"] == r["track"] and o["index"] == r["index"]]
            if len(match) != 1:
                fail("no original range for tail section %s/%s" % (r["host"], r["track"]))
            r["section"].set_range(*match[0]["range"])
        set_gc(orig["gc_sections"])
        remove_named(WALK_TRACK)
        remove_named(RIG_TRACK)
        if orig["walk"]:
            key_walk(walk_channels_from_snapshot(orig["walk"]), end)
        tops = [b for b in seq.get_bindings() if str(b.get_display_name()).startswith(RIG_PREFIX)
                and not (b.get_parent() is not None and b.get_parent().is_valid())]
        for b in tops:
            for kid in list(b.get_child_possessables()):
                kid.remove()
            b.remove()
        if [b for b in seq.get_bindings() if str(b.get_display_name()).startswith(RIG_PREFIX)]:
            fail("rig bindings survived the revert")
        for label in [l for l in snapshot_now["rig_actors"] if l not in orig["rig_actors"]]:
            hit = [x for x in actors.get_all_level_actors() if x.get_actor_label() == label]
            if len(hit) == 1 and not actors.destroy_actor(hit[0]):
                fail("could not delete rig actor %s" % label)
        write_markers([m for m in orig["markers"] if m[0].startswith(planner["MARKER_PREFIX"])])
        if music_now != orig["music"]:
            set_music(orig["music"])
        if record.get("warmers_original"):
            set_warmers(record["warmers_original"])

    # ------------------------------------------------------------------ rebuild + pre-save assertions
    result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
    report["rebuild"] = str(result)
    if not result:
        fail("rebuild_managed_master returned %r; NOTHING saved (Don't-Save restart; backup %s)" % (result, backup))
    segs_after = ext["compiled_segments"](show)
    report["segments_after"] = segs_after
    open_seg = [s for s in segs_after if s["label"] == cfg["cue_label"]]
    if len(open_seg) != 1 or abs(open_seg[0]["end"] - end / fps) > 0.001:
        fail("compiled Opening segment %r does not end at %.3f s; NOTHING saved" % (open_seg, end / fps))
    delta = round((end - old_end) / fps, 3)
    rows, bad = ext["segment_deltas"](report.get("segments_before") or ext["compiled_segments"](show), segs_after, cfg["cue_label"], delta)
    report["segment_rows"] = rows
    if bad:
        fail("segment shifts wrong: %r; NOTHING saved" % bad)
    keys_after = master_passage_keys()
    before_keys = report.get("master_keys_before") or {}
    carry = []
    for g, b in before_keys.items():
        a = keys_after.get(g)
        if a is None:
            carry.append("%s vanished" % g)
            continue
        for ch, kb in b["keys"].items():
            ka = a["keys"].get(ch)
            if ka is None or len(ka) != len(kb) or any(abs(x[0] - y[0]) > 1 or abs(x[1] - y[1]) > 1e-5 for x, y in zip(ka, kb)):
                carry.append("%s %s: %r -> %r" % (g, ch, kb[:3], (ka or [])[:3]))
    report["key_carry_failures"] = carry
    if carry:
        fail("Passage keys did not travel with their sections (patch K): %r; NOTHING saved" % carry[:5])
    cov = ext["cut_coverage"](seq)
    report["coverage"] = cov
    if cov["gaps"]:
        fail("camera cut gaps %r; NOTHING saved" % cov["gaps"])
    if any(a.get_actor_label().startswith("ZZ_") for a in actors.get_all_level_actors()):
        fail("ZZ_ bench actors in the level; refusing to save it")
    now = census()
    allowed_content = {cfg["sequence"], MASTER, SHOW}
    stray = [p for p in now["content"] if p not in allowed_content] + [p for p in now["maps"] if p != WORLD]
    if stray:
        fail("unexpected dirty packages %r; NOTHING saved" % stray)

    # ------------------------------------------------------------------ narrow saves
    saves = {}
    for p in (cfg["sequence"], MASTER, SHOW):
        if p in now["content"]:
            saves[p] = bool(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True))
    if WORLD in now["maps"]:
        saves[WORLD] = bool(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD))
    report["saves"] = saves
    if not all(saves.values()):
        fail("a save failed: %r" % saves)

    # ------------------------------------------------------------------ read-back (asserted)
    rb = {"playback": [seq.get_playback_start(), seq.get_playback_end()], "cut": [cut.get_start_frame(), cut.get_end_frame()],
          "gc_sections": gc_state(), "walk": read_walk(), "rig": read_rig(), "markers": read_markers()[0],
          "music": music_after(), "show_master": ext["show_master_match"](show, master), "census": census()}
    report["readback"] = rb
    problems = []
    if rb["census"]["content"] or rb["census"]["maps"]:
        problems.append("dirty after save %r" % rb["census"])
    if not rb["show_master"]["match"]:
        problems.append("Show/Master mismatch %r" % rb["show_master"])
    if mode == "APPLY":
        if rb["playback"][1] != end or rb["cut"][1] != end:
            problems.append("playback/cut end %r %r" % (rb["playback"], rb["cut"]))
        if rb["gc_sections"] != [list(x) for x in plan["curtain"]["sections"]]:
            problems.append("GC sections %r" % rb["gc_sections"])
        want = walk_channels_from_plan(plan["walkin"]["keys"])
        for key, keys in rb["walk"].items():
            ref = want.get(channel_of_key(key))
            if ref is None or len(ref) != len(keys) or abs(keys[-1][1] - ref[-1][1]) > 0.1 or keys[-1][0] != end:
                problems.append("walk channel %s read-back" % key)
        if len(rb["walk"]) != 8 and not walk_hand:
            problems.append("walk channels read back %d, expected 8" % len(rb["walk"]))
        want_markers = planner["marker_list"](plan)
        got = sorted([m for m in rb["markers"] if m[0].startswith(planner["MARKER_PREFIX"])], key=lambda x: (x[1], x[0]))
        if got != want_markers:
            problems.append("markers %r != %r" % (got, want_markers))
        if music_moved and (rb["music"]["opening"] != music_now["p01"]
                            or "SILENCE" not in rb["music"]["p01"]["mode"].upper()):
            problems.append("music did not move %r" % rb["music"])
        if cfg["music"]["move_p01_track_to_opening"] and "SILENCE" in rb["music"]["opening"]["mode"].upper():
            problems.append("the Opening carries no music after APPLY %r" % rb["music"])
    else:
        orig = record["original"]
        for k in ("playback", "cut", "gc_sections", "music"):
            if rb[k] != orig[k]:
                problems.append("REVERT %s %r != original %r" % (k, rb[k], orig[k]))
        if rb["walk"].keys() != orig["walk"].keys() or any(
                len(rb["walk"][k]) != len(orig["walk"][k]) or any(abs(a[1] - b[1]) > 1e-3 or a[0] != b[0]
                                                                   for a, b in zip(rb["walk"][k], orig["walk"][k]))
                for k in orig["walk"]):
            problems.append("REVERT walk keys differ from the original")
        if rb["rig"]:
            problems.append("REVERT left rig tracks %r" % list(rb["rig"]))
    report["problems"] = problems
    if problems:
        fail("read-back failed AFTER save (backup %s): %r" % (backup, problems))

    # ------------------------------------------------------------------ record + JSON write-back
    if mode == "APPLY":
        record["status"] = "applied"
        record["last_applied_frames"] = {n: plan["frames"][n] for n in planner["INPUT_MOMENTS"]}
        record["track_hashes"] = {"walk": {k: digest(v) for k, v in rb["walk"].items()},
                                  "rig": {k: digest(v) for k, v in rb["rig"].items()}}
        if plan["writeback"]:
            with open(paths["timing"], "r", encoding="utf-8") as h:
                table = json.load(h)                    # fresh: the measured walk values are NOT written back
            for n, f in plan["writeback"].items():
                table["moments"][n] = {"value": round(f / fps, 4), "source": "sequencer", "run": run}
            with open(paths["timing"], "w", encoding="utf-8") as h:
                json.dump(table, h, indent=2, ensure_ascii=False)
            report["json_writeback"] = plan["writeback"]
    else:
        record["status"] = "reverted"
    with open(paths["record"], "w", encoding="utf-8") as h:
        json.dump(record, h, indent=1, default=str, ensure_ascii=False)
    report["ok"] = True
    write_report()
    unreal.log("PUSS_OPENING_%s_OK|run=%s|end=%d|saves=%s|backup=%s|report=%s"
               % ("APPLIED" if mode == "APPLY" else "REVERTED", run, end, json.dumps(saves), backup, report_path))


if MODE not in ("DRY", "APPLY", "REVERT"):
    raise RuntimeError("OPENING_MODE must be DRY, APPLY or REVERT, got %r" % MODE)
main(MODE)
