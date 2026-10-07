"""PASSAGE SPEED PROBE (6 Oct, offline-written, NOT RUN): READ-ONLY per-Passage length / route / speed census.

Why: Gary (6 Oct) says P02 and P03 are "still very slow walking". The record says P03 was retimed 180 -> 42.24 s and
P04 180 -> 50.40 s at 01:46 6 Oct (passage_retime_to_music_record_P03-P04.json, run RETIME-20261006-014626).

For every Passage P01-P06 it reads, and writes nothing to Unreal:
  - compiled segment [start, end) in ticks (24000/s) from a TRANSIENT InfinityStageTransportController.build_segments
    (passage_retime_to_music.py:826-831 _segments; exact ints) and InfinityStageCameraPilotLibrary.get_passage_frame_range
    (InfinityStageCameraPilotLibrary.cpp:817-837, compiles the Show, exact ints);
  - the live Master's managed Passage section (passage_retime_to_music.py:1026-1060 read path; FLOAT-SECONDS reads,
    +-2..6 ticks, so compared with an 8-tick tolerance = SECTION_READ_TOL_TICKS, passage_retime_to_music.py:450);
  - timing (lead / IntervalToNext / tail frames + distances, passage_retime_to_music.py:863-898) and the compiled route
    lead_cm + sum(gaps[:-1]) + tail_cm (passage_retime_to_music.py:263-284 speeds());
  - the Passage actor's GetRouteLengthStatus (InfinityStagePassageActor.h:167; .cpp compiles the Show) + spline length;
  - MEASURED camera travel: the Passage's rig sampled with GetCameraViewAtMasterFrame (InfinityStageCameraRig.h:281-286,
    BlueprintPure const) at 121 points -> path length, mean / min / max windowed cm/s, first/last 10 % speeds;
  - the rig's shadow-cat animation knobs (InfinityStageCameraRig.h:111-147) and the play rate the cat's walk cycle
    would get at the mean speed (formula InfinityStageCameraRig.cpp:568-573: clamp(v / ref * mult, min, max));
  - Master Passage-section channels (Camera.SpeedMultiplier etc.);
  - drift vs the retime record's AFTER values (and REVERTED if it matches BEFORE);
  - if PIE is running: the runtime Show Root's transport segments, master sequence and player play rate (no scrub).
Never saves, never opens or scrubs the Master in Sequencer, never calls GetBoundObjects, no unreal objects in module
globals, no Saved/ module imports. The dirty-package census is read before and after and must be identical.
Output: Saved/CodexConductor/passage_speed_probe_<run>.json and ONE marker
  PASSAGE_SPEED_PROBE_OK|run=<id>|json=<path>|census_unchanged=<bool>|<per-passage summary>
or PASSAGE_SPEED_PROBE_FAILED|run=<id>|reason=... . Per-read failures: PASSAGE_SPEED_PROBE_READ_ERROR|run=<id>|... (warning).
"""
import datetime
import json
import math
import os
import traceback

import unreal

TOOL = "passage_speed_probe"
MARK = "PASSAGE_SPEED_PROBE"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                 # passage_retime_to_music.py:121
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"   # passage_retime_to_music.py:122
RECORD_NAME = "passage_retime_to_music_record_P03-P04.json"
SECTION_READ_TOL_TICKS = 8                                                     # passage_retime_to_music.py:450
SAMPLES = 120
LABELS = ["Passage %d" % i for i in range(1, 7)]


def _here():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")


class Probe(object):
    def __init__(self, run):
        self.run = run
        self.errors = []

    def read(self, what, fn, default=None):
        """Every Unreal read goes through here: an exception is logged + recorded, never raised."""
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - logged and reported
            msg = "%s: %r" % (what, exc)
            self.errors.append(msg)
            unreal.log_warning("%s_READ_ERROR|run=%s|%s" % (MARK, self.run, msg))
            return default


def unwrap(result, count):
    """passage_retime_to_music.py:689-697: out-params tuple, None on false."""
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == count + 1 and isinstance(result[0], bool):
        return result[1:] if result[0] else None
    if count == 1 and not isinstance(result, tuple):
        return (result,)
    return result


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _ticks(seconds, tick):
    return int(round(float(seconds) * tick))


def _census():
    return {"content": sorted(p.get_path_name().split(".")[0]
                              for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0]
                           for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _segments(show):
    tr = unreal.new_object(unreal.InfinityStageTransportController)   # transient, never saved
    tr.build_segments(show)
    return [{"label": str(s.get_editor_property("label")), "start": int(s.get_editor_property("start_frame").value),
             "end": int(s.get_editor_property("end_frame").value)} for s in tr.get_editor_property("segments")]


def _passage_facts(show, label):
    """passage_retime_to_music.py:845-898 (read part only)."""
    rows = {}
    for i, p in enumerate(show.get_editor_property("passage_settings")):
        rows[str(p.get_editor_property("label"))] = (i, p)
    if label not in rows:
        return None
    index, p = rows[label]
    cues = list(show.get_editor_property("cues"))
    by_guid = {_guid(c.get_editor_property("cue_guid")): i for i, c in enumerate(cues)}
    first = by_guid.get(_guid(p.get_editor_property("first_cue_guid")))
    last = by_guid.get(_guid(p.get_editor_property("last_cue_guid")))
    intervals, gaps = [], []
    if first is not None and last is not None:
        for i in range(first, last + 1):
            if cues[i].get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
                continue
            wp = cues[i].get_editor_property("wing_pair")
            intervals.append(int(wp.get_editor_property("interval_to_next").value))
            gaps.append(float(wp.get_editor_property("gap_to_next_cm")))
    out = {"index": index, "guid": _guid(p.get_editor_property("passage_guid")), "first_cue": first, "last_cue": last,
           "lead": int(p.get_editor_property("lead_in_frames").value),
           "tail": int(p.get_editor_property("tail_frames").value),
           "lead_cm": float(p.get_editor_property("lead_in_distance_cm")),
           "tail_cm": float(p.get_editor_property("tail_distance_cm")),
           "intervals": intervals, "gaps": gaps}
    for prop in ("fit_mode", "preferred_camera_speed_cm_per_second"):
        try:
            v = p.get_editor_property(prop)
            out[prop] = float(v) if isinstance(v, (int, float)) else str(v)
        except Exception as exc:  # noqa: BLE001
            out[prop] = "unreadable: %r" % exc
    return out


def _guid_obj(show, label):
    """The Passage's FGuid as an unreal struct, fresh per call (never cached in globals)."""
    for p in show.get_editor_property("passage_settings"):
        if str(p.get_editor_property("label")) == label:
            return p.get_editor_property("passage_guid")
    raise LookupError("no passage_settings row %s" % label)


def compiled_speeds(f, tick):
    """passage_retime_to_music.py:263-284 (no settle term)."""
    lead, tail, iv, gaps = f["lead"], f["tail"], f["intervals"], f["gaps"]
    length_ticks = lead + sum(iv[:-1]) + tail if iv else lead + tail
    pieces = []
    if lead > 0:
        pieces.append(f["lead_cm"] / (lead / tick))
    pieces += [g / (i / tick) for i, g in zip(iv[:-1], gaps[:-1]) if i > 0]
    route = f["lead_cm"] + sum(gaps[:-1]) + f["tail_cm"]
    length_s = length_ticks / tick if length_ticks else None
    return {"length_ticks_from_timing": length_ticks, "route_cm_compiled": round(route, 4),
            "mean_cm_s": round(route / length_s, 3) if length_s else None,
            "bay_min_cm_s": round(min(pieces), 3) if pieces else None,
            "bay_max_cm_s": round(max(pieces), 3) if pieces else None,
            "tail_cm_s": round(f["tail_cm"] / (tail / tick), 3) if tail > 0 else None,
            "intervals_distinct": sorted(set(iv)), "gaps_distinct": sorted(set(round(g, 3) for g in gaps)),
            "wing_pairs": len(iv)}


def _channel_keys(section):
    """p06_tail_extend.py:588-605 via passage_retime_to_music.py:981-999."""
    out = {}
    for ch in section.get_all_channels():
        try:
            keys = ch.get_keys()
        except Exception:  # noqa: BLE001
            continue
        rows = []
        for k in keys:
            t = int(k.get_time(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value)
            try:
                v = float(k.get_value())
            except Exception:  # noqa: BLE001
                v = None
            rows.append([t, v])
        if rows:
            out[str(ch.get_editor_property("channel_name"))] = sorted(rows, key=lambda r: r[0])
    return out


def _master_passage_sections(master, show_guid, tick):
    """{block_guid: {"range": [s, e], "channels": {...}}} for root, Show-owned MovieSceneInfinityPassageTrack sections.
    Reads float seconds (+-2..6 ticks; compare with SECTION_READ_TOL_TICKS)."""
    out = {}
    for track in master.get_tracks():
        if track.get_class().get_name() != "MovieSceneInfinityPassageTrack":
            continue
        try:
            if _guid(track.get_editor_property("owner_guid")) != show_guid:
                continue
        except Exception:  # noqa: BLE001
            continue
        for sec in track.get_sections():
            g = _guid(sec.get_editor_property("block_guid"))
            s = _ticks(sec.get_start_frame_seconds(), tick) if sec.has_start_frame() else None
            e = _ticks(sec.get_end_frame_seconds(), tick) if sec.has_end_frame() else None
            out.setdefault(g, []).append({"range": [s, e], "channels": _channel_keys(sec)})
    return out


def _level_actors():
    return list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())


def _passage_actor(actors, guid, show):
    hits = []
    for a in actors:
        if a.get_class().get_name() != "InfinityStagePassageActor":
            continue
        try:
            if _guid(a.get_editor_property("passage_guid")) == guid and a.get_editor_property("show_asset") == show:
                hits.append(a)
        except Exception:  # noqa: BLE001
            continue
    return hits


def _rigs(actors, passage_actor):
    return [a for a in actors if a.get_class().get_name() == "InfinityStageCameraRig"
            and a.get_editor_property("passage_actor") == passage_actor]


def _view(rig, frame):
    res = rig.get_camera_view_at_master_frame(unreal.FrameNumber(int(frame)))
    if isinstance(res, tuple):
        if res and isinstance(res[0], bool):
            if not res[0]:
                return None
            res = res[1:]
        xf = next((r for r in res if isinstance(r, unreal.Transform)), None)
    else:
        xf = res if isinstance(res, unreal.Transform) else None
    if xf is None:
        return None
    loc = xf.translation
    return [float(loc.x), float(loc.y), float(loc.z)]


def measured_speed(rig, start, end, tick):
    """Sample the camera at SAMPLES+1 Master ticks across [start, end) (end-1 = last frame of the Passage)."""
    pts = []
    last = end - 1
    for i in range(SAMPLES + 1):
        f = int(round(start + (last - start) * i / float(SAMPLES)))
        p = _view(rig, f)
        if p is not None:
            pts.append((f, p))
    if len(pts) < 3:
        return {"samples": len(pts), "error": "too few camera samples"}
    segs = []
    for (f0, p0), (f1, p1) in zip(pts, pts[1:]):
        d = math.sqrt(sum((p1[i] - p0[i]) ** 2 for i in range(2)))     # horizontal travel (gait bob excluded by Z)
        dt = (f1 - f0) / tick
        segs.append((f0, d, dt))
    total = sum(d for _f, d, _t in segs)
    dur = (pts[-1][0] - pts[0][0]) / tick
    v = [d / t for _f, d, t in segs if t > 0]
    n10 = max(1, len(v) // 10)
    return {"samples": len(pts), "path_xy_cm": round(total, 2), "duration_s": round(dur, 4),
            "mean_cm_s": round(total / dur, 3) if dur > 0 else None,
            "min_window_cm_s": round(min(v), 3), "max_window_cm_s": round(max(v), 3),
            "first10pct_cm_s": round(sum(v[:n10]) / n10, 3), "last10pct_cm_s": round(sum(v[-n10:]) / n10, 3),
            "mid_cm_s": round(v[len(v) // 2], 3),
            "start_xyz": [round(c, 1) for c in pts[0][1]], "end_xyz": [round(c, 1) for c in pts[-1][1]]}


CAT_PROPS = ("shadow_cat_reference_walk_speed_cm_per_second", "shadow_cat_animation_speed_multiplier",
             "shadow_cat_min_play_rate", "shadow_cat_max_play_rate", "b_shadow_cat_force_walk",
             "shadow_cat_force_walk", "b_shadow_cat_use_direct_walk_animation", "shadow_cat_use_direct_walk_animation",
             "crossing_settle_seconds", "current_shadow_cat_play_rate")


def rig_facts(probe, rig):
    out = {"label": str(rig.get_actor_label())}
    for prop in CAT_PROPS:
        try:
            v = rig.get_editor_property(prop)
            out[prop] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
        except Exception:  # noqa: BLE001 - renamed bools (memory puss-python-api-gotchas): try both spellings
            continue
    return out


def cat_play_rate(mean_cm_s, rf):
    """InfinityStageCameraRig.cpp:568-573 [decl]; inputs are the live instance values when readable."""
    ref = max(1.0, float(rf.get("shadow_cat_reference_walk_speed_cm_per_second", 250.0)))
    mult = max(0.0, float(rf.get("shadow_cat_animation_speed_multiplier", 0.6)))
    lo = max(0.0, float(rf.get("shadow_cat_min_play_rate", 0.0)))
    hi = max(lo, float(rf.get("shadow_cat_max_play_rate", 1.25)))
    if mean_cm_s is None:
        return None
    return round(min(hi, max(lo, mean_cm_s / ref * mult)), 4)


def record_compare(probe, folder, facts_by_guid, master_secs, segs_by_label, tick):
    path = os.path.join(folder, RECORD_NAME)
    if not os.path.exists(path):
        return {"record": None, "note": "record missing"}
    rec = json.load(open(path, encoding="utf-8"))
    out = {"record": RECORD_NAME, "run": rec.get("run"), "written": rec.get("written"), "applied": rec.get("applied"),
           "per": {}}
    for key in rec.get("passages", []):
        row = {}
        guid = rec["rows_by_key"][key]["guid"]
        live = facts_by_guid.get(guid)
        after_t = rec["after"]["timing"].get(key)
        before_t = rec["before"]["timing"].get(key)
        if live is None:
            row["status"] = "LIVE_UNREADABLE"
        else:
            lt = {"lead": live["lead"], "intervals": live["intervals"], "tail": live["tail"]}
            row["timing_live"] = {"lead": lt["lead"], "tail": lt["tail"], "intervals_distinct": sorted(set(lt["intervals"]))}
            if lt == after_t:
                row["status"] = "RETIME_INTACT"
            elif lt == before_t:
                row["status"] = "REVERTED_TO_BEFORE"
            else:
                row["status"] = "DRIFTED"
                row["timing_after_record"] = {"lead": after_t["lead"], "tail": after_t["tail"],
                                              "intervals_distinct": sorted(set(after_t["intervals"]))}
        rec_rng = rec["after"]["managed"].get("Passage:%s" % guid)
        live_rng = [s["range"] for s in master_secs.get(guid, [])]
        row["master_after_record"] = rec_rng
        row["master_live"] = live_rng
        if rec_rng and len(live_rng) == 1 and None not in live_rng[0]:
            ds = [abs(live_rng[0][0] - rec_rng[0]), abs(live_rng[0][1] - rec_rng[1])]
            row["master_delta_ticks"] = ds
            row["master_vs_record"] = "OK" if max(ds) <= SECTION_READ_TOL_TICKS else "MASTER_MOVED"
            # a pure shift (same length) is expected if something EARLIER in the show was lengthened later
            row["master_len_live_vs_record"] = (live_rng[0][1] - live_rng[0][0]) - (rec_rng[1] - rec_rng[0])
        out["per"][key] = row
    return out


def pie_facts(probe):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        return {"pie": False}
    out = {"pie": True, "world": world.get_path_name()}
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    out["show_roots"] = len(roots)
    if len(roots) != 1:
        return out
    root = roots[0]
    out["master"] = probe.read("pie master", lambda: _path(root.get_editor_property("master_sequence")))
    out["show"] = probe.read("pie show", lambda: _path(root.get_editor_property("show_asset")))
    player = probe.read("pie player", lambda: root.get_editor_property("sequence_player"))
    if player is not None:
        out["play_rate"] = probe.read("pie play rate", lambda: float(player.get_play_rate()))
    tr = probe.read("pie transport", lambda: root.get_editor_property("transport"))
    if tr is not None:
        out["segments"] = probe.read("pie segments", lambda: [
            {"label": str(s.label), "start": int(s.start_frame.value), "end": int(s.end_frame.value)}
            for s in list(tr.segments) if str(s.label).startswith("Passage")])
    return out


def main():
    run = "PSPEED-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    probe = Probe(run)
    census0 = probe.read("census before", _census)
    report = {"tool": TOOL, "run": run, "written": datetime.datetime.now().isoformat(timespec="seconds"),
              "census_before": census0, "passages": {}}
    show = probe.read("load show", lambda: unreal.load_asset(SHOW_PATH))
    master = probe.read("load master", lambda: unreal.load_asset(MASTER_PATH))
    if show is None or master is None:
        unreal.log_error("%s_FAILED|run=%s|reason=SHOW_OR_MASTER_DID_NOT_LOAD" % (MARK, run))
        return
    tick = probe.read("tick", lambda: _rate(show.get_editor_property("tick_resolution")), 24000.0)
    report["tick_rate"] = tick
    show_guid = probe.read("show guid", lambda: _guid(show.get_editor_property("show_guid")))
    segs = probe.read("segments", lambda: _segments(show), [])
    segs_by_label = {s["label"]: s for s in segs}
    report["segments"] = segs
    master_secs = probe.read("master sections", lambda: _master_passage_sections(master, show_guid, tick), {})
    report["master_playback_ticks"] = probe.read("master playback", lambda: [
        _ticks(master.get_playback_start_seconds(), tick), _ticks(master.get_playback_end_seconds(), tick)])
    actors = probe.read("level actors", _level_actors, [])
    facts_by_guid = {}
    summary = []
    for label in LABELS:
        row = {"label": label}
        f = probe.read("%s facts" % label, lambda: _passage_facts(show, label))
        if f is None:
            row["error"] = "no passage_settings row"
            report["passages"][label] = row
            continue
        facts_by_guid[f["guid"]] = f
        row.update({k: f[k] for k in ("guid", "lead", "tail", "lead_cm", "tail_cm", "first_cue", "last_cue")})
        row.update({k: f.get(k) for k in ("fit_mode", "preferred_camera_speed_cm_per_second")})
        row["compiled"] = compiled_speeds(f, tick)
        seg = segs_by_label.get(label)
        row["segment_ticks"] = [seg["start"], seg["end"]] if seg else None
        fr = probe.read("%s frame range" % label, lambda: unwrap(
            unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, _guid_obj(show, label)), 2))
        row["frame_range_ticks"] = [int(fr[0]), int(fr[1])] if fr else None
        rng = row["segment_ticks"] or row["frame_range_ticks"]
        if rng:
            row["length_ticks"] = rng[1] - rng[0]
            row["length_s"] = round((rng[1] - rng[0]) / tick, 4)
        ms = master_secs.get(f["guid"], [])
        row["master_sections"] = [m["range"] for m in ms]
        row["master_channels"] = {k: v for m in ms for k, v in m["channels"].items()}
        if rng and len(ms) == 1 and None not in ms[0]["range"]:
            d = [ms[0]["range"][0] - rng[0], ms[0]["range"][1] - rng[1]]
            row["master_vs_segment_ticks"] = d
            row["master_in_sync"] = max(abs(x) for x in d) <= SECTION_READ_TOL_TICKS
        elif rng:
            row["master_in_sync"] = "MASTER_SECTION_COUNT_%d" % len(ms)
        pas = _passage_actor(actors, f["guid"], show) if actors else []
        row["passage_actors"] = [str(a.get_actor_label()) for a in pas]
        route_req = None
        if len(pas) == 1:
            pa = pas[0]
            st = probe.read("%s route status" % label, lambda: unwrap(pa.get_route_length_status(), 2))
            if st:
                route_req = float(st[0])
                row["route_required_cm"] = round(float(st[0]), 3)
                row["route_current_cm"] = round(float(st[1]), 3)
            row["spline_length_cm"] = probe.read("%s spline" % label, lambda: round(float(
                pa.get_editor_property("route").get_spline_length()), 3))
            rigs = probe.read("%s rigs" % label, lambda: _rigs(actors, pa), [])
            row["rigs"] = [rig_facts(probe, r) for r in rigs]
            if len(rigs) == 1 and rng:
                row["measured"] = probe.read("%s measured speed" % label, lambda: measured_speed(rigs[0], rng[0], rng[1],
                                                                                                tick))
        route = route_req if route_req else row["compiled"]["route_cm_compiled"]
        row["route_cm_used"] = route
        if rng and route:
            row["mean_cm_s_route_over_length"] = round(route / ((rng[1] - rng[0]) / tick), 3)
        meas = (row.get("measured") or {}).get("mean_cm_s")
        if row.get("rigs"):
            row["cat_play_rate_at_mean"] = cat_play_rate(meas or row.get("mean_cm_s_route_over_length"), row["rigs"][0])
        report["passages"][label] = row
        summary.append("%s=%ss/%scm/%scm_s(meas %s,cat %s,sync %s)" % (
            label.replace("Passage ", "P0"), row.get("length_s"), round(route or 0), row.get("mean_cm_s_route_over_length"),
            meas, row.get("cat_play_rate_at_mean"), row.get("master_in_sync")))
    report["retime_record"] = probe.read("record compare", lambda: record_compare(
        probe, _here(), facts_by_guid, master_secs, segs_by_label, tick), {})
    report["pie"] = probe.read("pie facts", lambda: pie_facts(probe), {"pie": "unreadable"})
    census1 = probe.read("census after", _census)
    report["census_after"] = census1
    report["census_unchanged"] = census0 == census1
    report["read_errors"] = probe.errors
    out = os.path.join(_here(), "%s_%s.json" % (TOOL, run))
    try:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=1, sort_keys=True, default=str)
    except Exception as exc:  # noqa: BLE001
        unreal.log_error("%s_FAILED|run=%s|reason=JSON_WRITE %r" % (MARK, run, exc))
        return
    rec = report.get("retime_record") or {}
    rstat = ",".join("P0%s:%s" % (k, v.get("status")) for k, v in sorted((rec.get("per") or {}).items()))
    unreal.log("%s_OK|run=%s|json=%s|census_unchanged=%s|read_errors=%d|retime=%s|%s" % (
        MARK, run, out, report["census_unchanged"], len(probe.errors), rstat, "|".join(summary)))


try:
    main()
except Exception:  # noqa: BLE001 - one failure marker, nothing written to Unreal
    unreal.log_error("%s_FAILED|reason=%s" % (MARK, traceback.format_exc().replace("\n", " / ")))
