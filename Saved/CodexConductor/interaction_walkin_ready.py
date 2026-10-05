"""INTERACTION WALK-IN READY (5 Oct, offline-written, NEVER RUN IN UNREAL): make Interactions I2-I5 pass
curtain_sleight.py's WALKIN_NOT_READY gate (curtain_sleight.py:1350-1353) with values DERIVED from evidence, and do
only the prerequisite edits that are genuinely needed.

What the sleight actually consumes (declaration-proven, curtain_sleight.py):
  :1350-1353  registry landed_s and pile_edge_cm must be non-null; it uses landed_s ONLY as
              landed_after_release_s = landed_s - FALL_start / fps   (the FALL section start stands in for the release)
  :345-346    the live drape must be HOLD [0, F) + FALL [F, old_end): the FALL ends on the playback end
  :361-366    new_end = release + (FALL length) + extra_tail_frames; it lengthens the Interaction ITSELF
  :462        the re-timed FALL is [GO, new_end) with the SAME offsets; :1813 it replaces every cut section
  (grep)      minimum_end_frame is NOT read by curtain_sleight.py. Its only consumer is key_walkin_i1_p02.py:115-179 (the
              stalls-seat walk-in that the sleight supersedes; the sleight refuses while one is keyed, :749-751).
So Soft goods' "extend_scene_playback.py + fit_transition_drapes.py" lengthening is REDUNDANT for the sleight: the
same final FALL row and end come from extra_tail_frames += (lengthened FALL - current FALL). The harness proves this
with curtain_sleight.plan_sleight itself. The one prerequisite edit kept here is a narrow drape RE-FIT (GC section
ranges/offsets and the drape spawn range only, never the cut track, never the playback range), and only if DRY finds
a drape that does not match the canonical layout. Expected on the 30 Sep read-back: NOTHING to edit (APPLY_NOOP).

Derivations (pure, tested by test_interaction_walkin_ready.py):
  landed_s (registry convention, reproduces I1's 20.3): round(F/fps + (landed_bake_frame - release_frame)/30, 1)
  landed_s (exact, opening_walkin_probe.py:310-334):    F/fps + max(0, release_in_cache_s - hold_off/tick)
                                                         + (landed_bake_frame - release_frame)/30
     landed_bake_frame = first bake frame >= release_frame with top_z <= 1.0 m (opening_walkin_probe.py:27, :322-329)
  pile_edge_cm = |rig_limits.unreal_cm.X_min| of the bake (the approach side; OPENING's 203.0, walkin_transitions.json)
  FALL cache budget = floor((dur_ticks - start_off - end_off) / ticks_per_frame); a FALL longer than that WRAPS
     (fit_transition_drapes.py:125-126 refuses it as "it would LOOP"; the Opening adds a PILE section for exactly this,
     Docs/ChaosClothCurtain.md:627, 675-676). The sleight has no such guard (grep: no overrun check).

Modes (globals set by a runner):  WALKIN_READY_APPLY True, else DRY;  WALKIN_READY_RUN_ID optional.
Offline (system Python):  python interaction_walkin_ready.py --offline   -> proposal from the 30 Sep/5 Oct files.
Markers: INTERACTION_WALKIN_READY_DRY_OK / _APPLY_OK / _APPLY_NOOP |run=<id>|... or INTERACTION_WALKIN_READY_STOPPED|run=<id>|reason=...
Never Save All, never end PIE, never reload the level, no Sequencer UI, no unreal objects in module globals.
Tiers: [decl] read in a file (cited); [prec] an in-repo precedent call (cited, run or not); [meas] read back; [inf] inferred.
"""
import copy
import datetime
import difflib
import hashlib
import json
import math
import os
import shutil
import sys

try:
    import unreal
except ModuleNotFoundError:  # offline harness / --offline
    unreal = None


EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SEQ_DIR = "/Game/InfinityStage/Interactions"
SEQS = {1: "LS_Interaction_01_WashingTheBoy", 2: "LS_Interaction_02_Turnips", 3: "LS_Interaction_03_ForgetsHisName",
        4: "LS_Interaction_04_GetsAName", 5: "LS_Interaction_05_BecomesKing"}      # fit_transition_drapes.py:28-29
GC_PATH = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
MOUTH_DRAPE = "Transition Drape (baked)"                                            # fit_transition_drapes.py:31
WALK_TRACK = "WalkIn (Look & camera)"                                               # curtain_sleight.py:79
SLEIGHT_MARKER_PREFIX = "CST "                                                      # curtain_sleight.py:89
SLEIGHT_BINDING_PREFIXES = ("Sleight ", "I%d Sleight", "S%d Sleight")              # curtain_sleight.py:82-87
CACHE_FPS = 30.0                                                                    # fit_transition_drapes.py:42
LANDED_TOP_Z_M = 1.0                                                                # opening_walkin_probe.py:27
SITE_NOTES = {2: "P03 mouth is FRAME ONLY (no stage front; Wet Ground landscape): the pile baked onto P01's stage front "
                 "may float or clip here (fit_transition_drapes.py:32-34); 2 P03 fixtures sit inside the pile footprint "
                 "(Docs/ChaosClothCurtain.md:46).",
              3: "P04 has open chariot slots under the pile; the pile bridges them (Docs/ChaosClothCurtain.md:46)."}
ARGS_NAME = "interaction_walkin_ready_args.json"
DRY_NAME = "interaction_walkin_ready_dry.json"
RECORD_NAME = "interaction_walkin_ready_record.json"
PROPOSED_NAME = "walkin_transitions.proposed.json"
DIFF_NAME = "walkin_transitions.proposed.diff"
REGISTRY_REL = os.path.join("CodexCameraPilot", "walkin_transitions.json")
BAKE_DIR_REL = os.path.join("CodexSoftGoods", "DropBake")

DEFAULT_ARGS = {
    "interactions": [2, 3, 4, 5],
    "reference_interactions": [1],          # read-only rows (I1 is post-sleight; never edited here)
    "expected": {"end": 500, "fps": 25.0, "tick_rate": 24000.0, "cache": GC_PATH,
                 "bake_id": "final13_opening_a06_w188", "lead_s": 4.0, "hold_at": "release"},
    "landed_top_z_m": LANDED_TOP_Z_M,
    "landed_rounding": "round_0p1",         # I1's registry convention (reproduces 20.3)
    "allow_drape_refit": True,
    "planned_playback_changes": {},         # MUST stay empty: lengthening is not a prerequisite (see docstring)
}


class ReadyError(ValueError):
    pass


# =====================================================================================================================
# Pure derivations
# =====================================================================================================================

def merged_args(args):
    out = copy.deepcopy(DEFAULT_ARGS)
    for k, v in (args or {}).items():
        if k == "expected":
            out["expected"].update(v)
        else:
            out[k] = v
    return out


def bake_id_from_source(source_basename):
    """fit_transition_drapes.py:104-115 / opening_walkin_probe.py:268-275: the cache's import file names its bake."""
    stem = GC_PATH.split("/")[-1] + "_"
    if source_basename and source_basename.startswith(stem) and source_basename.endswith(".abc"):
        return source_basename[len(stem):-4]
    if source_basename == "CurtainDrop_Opening_final2.abc":
        return "final2_stage_v2"
    return None


def cache_duration_ticks(start_frame, end_frame, tick_rate):
    return int(round((float(end_frame) - float(start_frame)) / CACHE_FPS * float(tick_rate)))


def hold_offset_ticks(release_in_cache_s, tick_rate, hold_at):
    """fit_transition_drapes.py:121-122: the held sample is one cache frame before the release (or the first)."""
    if hold_at == "release":
        return int(round((float(release_in_cache_s) - 1.0 / CACHE_FPS) * float(tick_rate)))
    return 0


def release_in_cache_s(bake):
    if bake.get("release_frame") is None or bake.get("show_start") is None:
        raise ReadyError("BAKE_RELEASE_NONE|%s: release_frame/show_start is null (memory: release_frame may be None)"
                         % bake.get("id"))
    return (float(bake["release_frame"]) - float(bake["show_start"])) / CACHE_FPS


def landed_bake_frame(bake, threshold_m=LANDED_TOP_Z_M):
    """opening_walkin_probe.py:316-329: first frame >= release with top_z <= threshold."""
    release_in_cache_s(bake)
    top_z, frames = bake.get("top_z"), bake.get("frames")
    if not isinstance(top_z, list) or not top_z or frames is None:
        raise ReadyError("BAKE_NO_TOP_Z|%s" % bake.get("id"))
    first = int(frames) - len(top_z) + 1
    rel = int(bake["release_frame"])
    for i, v in enumerate(top_z):
        if first + i >= rel and float(v) <= float(threshold_m):
            return first + i
    raise ReadyError("BAKE_NEVER_LANDS|%s|threshold=%.3f m" % (bake.get("id"), threshold_m))


def derive_landed(fall_start, fps, bake, hold_off_ticks, tick_rate, threshold_m=LANDED_TOP_Z_M, rounding="round_0p1"):
    rel_s = release_in_cache_s(bake)
    landed = landed_bake_frame(bake, threshold_m)
    after_release = (landed - int(bake["release_frame"])) / CACHE_FPS
    fall_s = float(fall_start) / float(fps)
    exact = fall_s + max(0.0, rel_s - float(hold_off_ticks) / float(tick_rate)) + after_release
    raw_registry = fall_s + after_release                       # curtain_sleight.py:1353 treats F as the release
    if rounding == "round_0p1":
        registry = round(raw_registry, 1)
    elif rounding == "ceil_0p1":
        registry = math.ceil(exact * 10.0 - 1.0e-9) / 10.0
    elif rounding == "exact":
        registry = exact
    else:
        raise ReadyError("UNKNOWN_ROUNDING|%s" % rounding)
    return {"landed_s": registry, "landed_s_exact": exact, "landed_bake_frame": landed,
            "release_frame": int(bake["release_frame"]), "show_start": int(bake["show_start"]),
            "release_in_cache_s": rel_s, "landed_after_release_s": after_release,
            "sleight_landed_after_release_s": registry - fall_s, "threshold_m": float(threshold_m),
            "rounding": rounding}


def pile_edge_from_bake(bake):
    lim = bake.get("rig_limits", {}).get("unreal_cm", {})
    if "X_min" not in lim:
        raise ReadyError("BAKE_NO_RIG_LIMITS|%s" % bake.get("id"))
    return abs(float(lim["X_min"])), [float(lim["X_min"]), float(lim.get("X_max", float("nan")))]


def canonical_drape(end, fps, lead_s, hold_off, dur_ticks):
    """fit_transition_drapes.py:118-164 layout: HOLD [0, F) one-tick window, FALL [F, end) from the held sample."""
    end = int(end)
    fall_start = max(0, end - int(round(float(lead_s) * float(fps))))
    return {"hold": [0, fall_start, int(hold_off), int(dur_ticks) - int(hold_off) - 1],
            "fall": [fall_start, end, int(hold_off), 0], "spawn": [[0, end]]}


def fall_budget_frames(dur_ticks, start_off, end_off, tick_rate, fps):
    ticks_per_frame = float(tick_rate) / float(fps)
    return int(math.floor((int(dur_ticks) - int(start_off) - int(end_off)) / ticks_per_frame + 1.0e-9))


def fall_wrap(fall_row, dur_ticks, tick_rate, fps):
    """None if the FALL fits the cache, else the display frame where it wraps back to its first sample."""
    a, b, so, eo = [int(v) for v in fall_row]
    window = int(dur_ticks) - so - eo
    ticks_per_frame = float(tick_rate) / float(fps)
    if (b - a) * ticks_per_frame <= window:
        return None
    return a + window / ticks_per_frame


def sleight_tails(snapshot_bindings, root_tracks, old_end):
    """Sections curtain_sleight APPLY stretches by delta (curtain_sleight.py:1683-1699): every non-cut section ending
    on old_end or old_end + 1, except the mouth drape's GC track (re-timed separately)."""
    out = []
    for b in snapshot_bindings:
        for t in b["tracks"]:
            if b["name"] == MOUTH_DRAPE and t["class"] == "MovieSceneGeometryCacheTrack":
                continue
            for s in t["sections"]:
                if int(s[1]) in (int(old_end), int(old_end) + 1):
                    out.append([b["name"], t["class"], t.get("name", ""), list(s)])
    for t in root_tracks:
        if t["class"] == "MovieSceneCameraCutTrack":
            continue
        for s in t["sections"]:
            if int(s[1]) in (int(old_end), int(old_end) + 1):
                out.append(["<root>", t["class"], t.get("name", ""), list(s)])
    return sorted(out)


def assess(n, live, args, bake):
    """live: plain data read from one Interaction. Returns needs (edits this tool may make), refusals, derived values."""
    a = merged_args(args)
    e = a["expected"]
    refusals, needs, warnings = [], [], []
    start, end = [int(v) for v in live["playback"]]
    if start != 0:
        refusals.append("PLAYBACK_START_NOT_ZERO|%d" % start)
    planned = a.get("planned_playback_changes") or {}
    if planned:
        refusals.append("PLAYBACK_CHANGE_NOT_SUPPORTED|%r (lengthening is not a sleight prerequisite; use "
                        "extend_scene_playback.py and a Master rebuild if Gary wants it)" % planned)
    if end != int(e["end"]):
        refusals.append("END_UNPLANNED|I%d ends at %d, planned %d (re-derive before editing)" % (n, end, int(e["end"])))
    if abs(float(live["fps"]) - float(e["fps"])) > 1.0e-6:
        refusals.append("FPS|%r" % live["fps"])
    if abs(float(live["tick_rate"]) - float(e["tick_rate"])) > 1.0e-6:
        refusals.append("TICK_RATE|%r" % live["tick_rate"])
    if int(live["drape_bindings"]) != 1:
        refusals.append("MOUTH_DRAPE_COUNT|%d" % int(live["drape_bindings"]))
    if live.get("cache") != e["cache"]:
        refusals.append("MOUTH_DRAPE_CACHE|%s" % live.get("cache"))
    if live.get("bake_id") != e["bake_id"] or bake is None or bake.get("id") != e["bake_id"]:
        refusals.append("BAKE_ID|live=%s|expected=%s" % (live.get("bake_id"), e["bake_id"]))
    if live.get("sleight_markers") or live.get("sleight_bindings"):
        refusals.append("SLEIGHT_ALREADY_APPLIED|markers=%r|bindings=%r" % (live.get("sleight_markers"),
                                                                           live.get("sleight_bindings")))
    if live.get("walkin_tracks"):
        refusals.append("WALKIN_PRESENT|%r (curtain_sleight.py:749-751 refuses; Look & camera's revert first)"
                        % live["walkin_tracks"])
    if refusals:
        return {"n": n, "refusals": refusals, "needs": [], "warnings": warnings, "derived": None, "canonical": None}

    rel_s = release_in_cache_s(bake)
    hold_off = hold_offset_ticks(rel_s, live["tick_rate"], e["hold_at"])
    dur = int(live["cache_duration_ticks"])
    canon = canonical_drape(end, live["fps"], e["lead_s"], hold_off, dur)
    gc = [list(map(int, r)) for r in live["gc"]]
    if gc != [canon["hold"], canon["fall"]]:
        if a.get("allow_drape_refit"):
            needs.append({"kind": "DRAPE_REFIT", "from": gc, "to": [canon["hold"], canon["fall"]]})
        else:
            refusals.append("DRAPE_NOT_CANONICAL|%r vs %r" % (gc, [canon["hold"], canon["fall"]]))
    spawn = [list(map(int, r)) for r in live["spawn"]]
    if spawn != canon["spawn"]:
        if len(spawn) == 1 and a.get("allow_drape_refit"):
            needs.append({"kind": "SPAWN_RANGE", "from": spawn, "to": canon["spawn"]})
        else:
            refusals.append("SPAWN_NOT_ONE_SECTION|%r" % spawn)
    landed = derive_landed(canon["fall"][0], live["fps"], bake, hold_off, live["tick_rate"],
                           a["landed_top_z_m"], a["landed_rounding"])
    edge, extent = pile_edge_from_bake(bake)
    budget = fall_budget_frames(dur, canon["fall"][2], canon["fall"][3], live["tick_rate"], live["fps"])
    fall_len = canon["fall"][1] - canon["fall"][0]
    if live.get("cut_rows") and len(live["cut_rows"]) != 1:
        warnings.append("CUTS_NOT_ONE|%r (the sleight replaces them all, curtain_sleight.py:1813)" % live["cut_rows"])
    derived = {"minimum_end_frame": end, "landed_s": landed["landed_s"], "pile_edge_cm": edge,
               "fps": float(live["fps"]), "fall_start_s": canon["fall"][0] / float(live["fps"]), "bake_id": bake["id"],
               "landed": landed, "pile_route_extent_cm": extent, "hold_offset_ticks": hold_off,
               "cache_duration_ticks": dur, "fall_cache_budget_frames": budget, "fall_len_frames": fall_len,
               "max_extra_tail_frames_without_wrap": budget - fall_len}
    return {"n": n, "refusals": refusals, "needs": needs, "warnings": warnings, "derived": derived, "canonical": canon}


def plan_digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def plan_from_assessments(rows):
    return {"edits": {str(r["n"]): r["needs"] for r in rows if r["needs"]},
            "derived": {str(r["n"]): r["derived"] for r in rows}}


def check_edit_plan(plan):
    """Range-change guard: only drape GC/spawn section edits; never playback; every 'to' ends on the same end."""
    fail = []
    for n, edits in plan["edits"].items():
        for ed in edits:
            if ed["kind"] not in ("DRAPE_REFIT", "SPAWN_RANGE"):
                fail.append("EDIT_KIND_NOT_ALLOWED|I%s|%s" % (n, ed["kind"]))
                continue
            der = plan["derived"].get(n) or {}
            end = der.get("minimum_end_frame")
            last = ed["to"][-1]
            if end is None or int(last[1]) != int(end):
                fail.append("EDIT_CHANGES_END|I%s|%r vs end %r" % (n, last, end))
    return fail


def readiness_note(n, derived, source):
    d = derived
    lan = d["landed"]
    note = ("Ready for curtain_sleight.py (option B) from %s: live end %d = the drape FALL end (curtain_sleight.py:345); "
            "landed_s %.1f = FALL start %.1f s + bake %s frames %d->%d (top_z <= %.1f m) %.3f s, rounded to 0.1 as I1's "
            "registry (exact %.4f s); pile_edge_cm %.1f = |bake rig_limits X_min| (approach side). The sleight lengthens "
            "and re-times this Interaction itself, so Soft goods' extend/fit steps are not needed. NOT ready for the "
            "stalls-seat key_walkin_i1_p02.py (landed %.1f s > end %.1f s); that path is superseded by the sleight's walk. "
            "Sleight caveat: FALL + extra_tail_frames must stay <= %d frames or the cache wraps (max extra %d) until "
            "curtain_sleight.py adds a PILE hold section."
            % (source, d["minimum_end_frame"], d["landed_s"], d["fall_start_s"],
               d["bake_id"], lan["release_frame"], lan["landed_bake_frame"], lan["threshold_m"], lan["landed_after_release_s"],
               lan["landed_s_exact"], d["pile_edge_cm"], d["landed_s"], d["minimum_end_frame"] / d["fps"],
               d["fall_cache_budget_frames"], d["max_extra_tail_frames_without_wrap"]))
    if n in SITE_NOTES:
        note += " Site: " + SITE_NOTES[n]
    return note


def propose_registry(registry, rows, source, tier):
    out = copy.deepcopy(registry)
    for r in rows:
        key = "I%d" % r["n"]
        if key not in out:
            raise ReadyError("REGISTRY_HAS_NO|%s" % key)
        entry = out[key]
        if r["refusals"] or r["needs"] or r["derived"] is None:
            entry["readiness_note"] = ("Not ready (%s): %s" % (source, "; ".join(r["refusals"] + [x["kind"] for x in r["needs"]])))
            continue
        d = r["derived"]
        entry["minimum_end_frame"] = int(d["minimum_end_frame"])
        entry["landed_s"] = float(d["landed_s"])
        entry["pile_edge_cm"] = float(d["pile_edge_cm"])
        entry["readiness_note"] = readiness_note(r["n"], d, source)
        entry["soft_goods_steps_superseded"] = entry.get("soft_goods_steps", [])
        entry["soft_goods_steps"] = []
        lan = d["landed"]
        entry["file_evidence"] = {
            "tier": tier, "source": source, "playback_frames": [0, int(d["minimum_end_frame"])], "fps": 25.0,
            "drape_hold": r["canonical"]["hold"], "drape_fall": r["canonical"]["fall"], "curtain_cache": GC_PATH,
            "bake_id": d["bake_id"], "release_frame": lan["release_frame"],
            "cache_show_start_frame": lan["show_start"], "hold_offset_ticks": d["hold_offset_ticks"],
            "landed_bake_frame": lan["landed_bake_frame"], "landed_top_z_m": lan["threshold_m"],
            "landed_after_release_s": lan["landed_after_release_s"], "landed_s_exact": lan["landed_s_exact"],
            "landed_rounding": lan["rounding"], "pile_route_extent_cm": d["pile_route_extent_cm"],
            "cache_duration_ticks": d["cache_duration_ticks"], "fall_cache_budget_frames": d["fall_cache_budget_frames"],
            "max_extra_tail_frames_without_wrap": d["max_extra_tail_frames_without_wrap"],
            "minimum_end_frame_meaning": "the live end the sleight lengthens from (FALL ends here); not a stalls-walk end",
        }
    return out


def registry_diff(old, new, name="walkin_transitions.json"):
    a = json.dumps(old, indent=2, ensure_ascii=False).splitlines(keepends=True)
    b = json.dumps(new, indent=2, ensure_ascii=False).splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, "a/Saved/CodexCameraPilot/" + name, "b/Saved/CodexCameraPilot/" + name))


# =====================================================================================================================
# Files
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _saved():
    return os.path.dirname(_here())


def _load_json(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise ReadyError("MISSING|" + path)
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, default=str)
        handle.write("\n")


def _load_bake(bake_id):
    if not bake_id:
        return None
    return _load_json(os.path.join(_saved(), BAKE_DIR_REL, bake_id + ".json"))


def write_proposal(rows, source, tier):
    registry = _load_json(os.path.join(_saved(), REGISTRY_REL))
    proposed = propose_registry(registry, rows, source, tier)
    _write_json(os.path.join(_here(), PROPOSED_NAME), proposed)
    with open(os.path.join(_here(), DIFF_NAME), "w", encoding="utf-8", newline="\n") as h:
        h.write(registry_diff(registry, proposed))
    return proposed


# =====================================================================================================================
# Offline proposal from files (30 Sep measured fit/verify read-back + 5 Oct I1-sleight segment rows)
# =====================================================================================================================

def offline_live_rows(saved):
    """Live-shaped rows from files. [meas 30 Sep] verify_transition_fit.json (gc rows, end), fit_transition_drapes_final13
    (cache bake); [meas 5 Oct] curtain_sleight_record_I1.json segment_rows (I2-I5 still 20.0 s after I1's sleight)."""
    def load(*p):
        with open(os.path.join(saved, *p), "r", encoding="utf-8") as h:
            return json.load(h)
    verify = {r["interaction"]: r for r in load("CodexSoftGoods", "verify_transition_fit.json")["rows"]}
    fit13 = load("CodexSoftGoods", "fit_transition_drapes_final13.json")
    imp = load("CodexSoftGoods", "import_passing_bake.json")
    seg = {r["label"]: r for r in load("CodexConductor", "curtain_sleight_record_I1.json")["segment_rows"]}
    gc_frames = imp["read_back"]["gc_frames"]
    rows = {}
    for n in (2, 3, 4, 5):
        v = verify[n]
        label = [k for k in seg if k.startswith("Interaction %d " % n)][0]
        a, b = seg[label]["after"]
        rows[n] = {"playback": [0, int(v["end"])], "fps": 25.0, "tick_rate": 24000.0, "drape_bindings": 1,
                   "gc": v["gc_sections"], "spawn": [[0, int(v["end"])]] if v["checks"].get("spawn_range") else [],
                   "cache": GC_PATH, "bake_id": fit13["cache_bake"],
                   "cache_duration_ticks": cache_duration_ticks(gc_frames[0], gc_frames[1], 24000.0),
                   "cut_rows": [[v.get("cut_camera")]], "sleight_markers": [], "sleight_bindings": [],
                   "walkin_tracks": [], "segment_seconds_5oct": round(b - a, 3), "verify_ok_30sep": v["ok"]}
    return rows


def run_offline(args=None):
    saved = _saved()
    a = merged_args(args or _load_json(os.path.join(_here(), ARGS_NAME), required=False))
    rows = []
    lives = offline_live_rows(saved)
    for n in a["interactions"]:
        live = lives[n]
        if abs(live["segment_seconds_5oct"] - live["playback"][1] / 25.0) > 1.0e-6:
            raise ReadyError("OFFLINE_INCONSISTENT|I%d segment %.3f s vs end %d" % (n, live["segment_seconds_5oct"],
                                                                                     live["playback"][1]))
        rows.append(assess(n, live, a, _load_bake(live["bake_id"])))
    write_proposal(rows, "offline files (verify_transition_fit.json 30 Sep read-back; I1 sleight segment rows 5 Oct)",
                   "measured 30 Sep (drape rows) + measured 5 Oct (segment lengths) + declaration (bake record); "
                   "the live DRY supersedes")
    for r in rows:
        print("I%d refusals=%r needs=%r derived=%s" % (r["n"], r["refusals"], [x["kind"] for x in r["needs"]],
                                                       json.dumps({k: r["derived"][k] for k in (
                                                           "minimum_end_frame", "landed_s", "pile_edge_cm",
                                                           "fall_cache_budget_frames",
                                                           "max_extra_tail_frames_without_wrap")}) if r["derived"] else None))
    print("WALKIN_READY_OFFLINE_PROPOSAL|%s" % os.path.join(_here(), PROPOSED_NAME))
    return rows


# =====================================================================================================================
# Unreal (everything inside functions; no wrappers in module globals)
# =====================================================================================================================

class Stopped(RuntimeError):
    pass


def _stop(run, reason):
    unreal.log_error("INTERACTION_WALKIN_READY_STOPPED|run=%s|reason=%s" % (run, reason))
    raise Stopped(reason)


def _census():
    return {"content": sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _content_file(path):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _span(section, start, end):
    a = section.get_start_frame() if section.has_start_frame() else start
    b = section.get_end_frame() if section.has_end_frame() else end
    return [int(a), int(b)]


def _gc_row(section):                                                   # curtain_sleight.py:1047-1050 [prec, run 5 Oct]
    prm = section.get_editor_property("params")
    return [int(section.get_start_frame()), int(section.get_end_frame()),
            int(prm.get_editor_property("start_frame_offset").value), int(prm.get_editor_property("end_frame_offset").value)]


def _track_rows(tracks, start, end):
    rows = []
    for t in tracks:
        cls = t.get_class().get_name()
        secs = [(_gc_row(s) if cls == "MovieSceneGeometryCacheTrack" else _span(s, start, end)) for s in t.get_sections()]
        rows.append({"class": cls, "name": str(t.get_display_name()), "sections": sorted(secs)})
    return rows


def _read_live(n):
    """Read-only. Returns (plain data, handles)."""
    path = "%s/%s" % (SEQ_DIR, SEQS[n])
    seq = unreal.load_asset(path)
    if seq is None:
        raise ReadyError("SEQUENCE_DID_NOT_LOAD|" + path)
    rate, tick = seq.get_display_rate(), seq.get_tick_resolution()
    fps = rate.numerator / float(rate.denominator)
    tick_rate = tick.numerator / float(tick.denominator)
    start, end = int(seq.get_playback_start()), int(seq.get_playback_end())
    drapes = [b for b in seq.get_bindings() if str(b.get_display_name()) == MOUTH_DRAPE]
    gc_rows, spawn_rows, gsecs, ssecs, cache_path, bake_id, dur = [], [], [], [], None, None, None
    if len(drapes) == 1:
        for t in drapes[0].get_tracks():
            cls = t.get_class().get_name()
            if cls == "MovieSceneGeometryCacheTrack":
                gsecs.extend(sorted(t.get_sections(), key=lambda s: s.get_start_frame()))
            elif cls == "MovieSceneSpawnTrack":
                ssecs.extend(t.get_sections())
        gc_rows = [_gc_row(s) for s in gsecs]
        spawn_rows = sorted(_span(s, start, end) for s in ssecs)
        if gsecs:
            cache = gsecs[-1].get_editor_property("params").get_editor_property("geometry_cache_asset")
            if cache is not None:
                cache_path = cache.get_path_name().split(".")[0]
                src = os.path.basename(cache.get_editor_property("asset_import_data").get_first_filename())
                bake_id = bake_id_from_source(src)
                dur = cache_duration_ticks(cache.get_editor_property("start_frame"), cache.get_editor_property("end_frame"),
                                           tick_rate)
    names = {unreal.GuidLibrary.conv_guid_to_string(b.get_id()): str(b.get_display_name()) for b in seq.get_bindings()}
    cut_rows = []
    for t in seq.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        for s in t.get_sections():
            g = unreal.GuidLibrary.conv_guid_to_string(s.get_camera_binding_id().get_editor_property("guid"))
            cut_rows.append([names.get(g, "?"), _span(s, start, end), bool(s.is_active())])
    markers = [[str(m.get_editor_property("label")), int(m.get_editor_property("frame_number").value)]
               for m in seq.get_marked_frames_from_sequence(unreal.MovieSceneTimeUnit.DISPLAY_RATE)]
    sleight_markers = [m for m in markers if m[0].startswith(SLEIGHT_MARKER_PREFIX)]
    prefixes = (SLEIGHT_BINDING_PREFIXES[0], SLEIGHT_BINDING_PREFIXES[1] % n, SLEIGHT_BINDING_PREFIXES[2] % n)
    sleight_bindings = sorted(v for v in names.values() if v.startswith(prefixes))
    walk_tracks = sorted(str(b.get_display_name()) for b in seq.get_bindings() for t in b.get_tracks()
                         if str(t.get_display_name()) == WALK_TRACK)
    bindings = [{"name": str(b.get_display_name()), "tracks": _track_rows(b.get_tracks(), start, end)}
                for b in seq.get_bindings()]
    root_tracks = _track_rows(seq.get_tracks(), start, end)
    live = {"sequence": path, "playback": [start, end], "fps": fps, "tick_rate": tick_rate,
            "drape_bindings": len(drapes), "gc": gc_rows, "spawn": spawn_rows, "cache": cache_path, "bake_id": bake_id,
            "cache_duration_ticks": dur, "cut_rows": cut_rows, "markers": markers, "sleight_markers": sleight_markers,
            "sleight_bindings": sleight_bindings, "walkin_tracks": walk_tracks,
            "sleight_tails_if_applied_now": sleight_tails(bindings, root_tracks, end)}
    return live, {"seq": seq, "gc_sections": gsecs, "spawn_sections": ssecs}


def _guards(run):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE")                                   # never end PIE; refuse
    world = editor.get_editor_world()
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD")
    if unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
        _stop(run, "SEQUENCER_IS_OPEN")                                   # curtain_sleight.py:2058-2059 [prec]


def _gather_all(run, a):
    rows, lives, refs = [], {}, {}
    for n in a["interactions"]:
        live, _ = _read_live(n)
        lives[str(n)] = live
        rows.append(assess(n, live, a, _load_bake(live.get("bake_id"))))
    for n in a.get("reference_interactions", []):
        live, _ = _read_live(n)
        wrap = None
        if live["cache_duration_ticks"] and len(live["gc"]) >= 2:
            wrap = fall_wrap(live["gc"][-1], live["cache_duration_ticks"], live["tick_rate"], live["fps"])
        refs[str(n)] = {"playback": live["playback"], "gc": live["gc"], "cuts": live["cut_rows"],
                        "sleight_markers": live["sleight_markers"], "fall_wraps_at_frame": wrap}
    return rows, lives, refs


def run_dry(run, a):
    census0 = _census()
    rows, lives, refs = _gather_all(run, a)
    plan = plan_from_assessments(rows)
    census1 = _census()
    report = {"run": run, "mode": "DRY", "args": a, "census_before": census0, "census_after": census1,
              "mutated": census0 != census1, "lives": lives, "assessments": rows, "reference": refs,
              "plan": plan, "plan_digest": plan_digest(plan), "plan_failures": check_edit_plan(plan),
              "master_rebuild_required": False,
              "master_note": "No playback range is changed by this tool (planned_playback_changes must be empty), so "
                             "no Master rebuild follows it. curtain_sleight APPLY rebuilds the Master itself."}
    _write_json(os.path.join(_here(), DRY_NAME), report)
    if report["mutated"]:
        _stop(run, "DRY_MUTATED|%r -> %r" % (census0, census1))
    ready = [r for r in rows if not r["refusals"] and not r["needs"]]
    write_proposal(rows, "live DRY run=%s" % run, "measured (live read of playback, drape sections, cache import "
                   "chain) + declaration (DropBake record)")
    unreal.log("INTERACTION_WALKIN_READY_DRY_OK|run=%s|mutated=0|digest=%s|ready=%s|needs=%s|refused=%s|i1_fall_wraps_at=%s|"
               "master_rebuild_required=false|proposal=%s"
               % (run, report["plan_digest"], ",".join("I%d" % r["n"] for r in ready),
                  ",".join("I%d:%s" % (r["n"], "+".join(x["kind"] for x in r["needs"])) for r in rows if r["needs"]),
                  ",".join("I%d:%s" % (r["n"], r["refusals"][0].split("|")[0]) for r in rows if r["refusals"]),
                  (refs.get("1") or {}).get("fall_wraps_at_frame"), PROPOSED_NAME))


def run_apply(run, a):
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_BEFORE|" + json.dumps(_census()))
    rows, lives, _ = _gather_all(run, a)
    plan = plan_from_assessments(rows)
    dry = _load_json(os.path.join(_here(), DRY_NAME), required=False)
    if dry.get("plan_digest") != plan_digest(plan):
        _stop(run, "PLAN_CHANGED_SINCE_DRY|dry=%s|now=%s|rerun DRY" % (dry.get("plan_digest"), plan_digest(plan)))
    refused = [r for r in rows if r["refusals"]]
    if refused:
        _stop(run, "REFUSED|" + " || ".join("I%d:%s" % (r["n"], ";".join(r["refusals"])) for r in refused))
    fails = check_edit_plan(plan)
    if fails:
        _stop(run, "EDIT_PLAN|" + ";".join(fails))
    if not plan["edits"]:
        write_proposal(rows, "live APPLY run=%s (no edit needed)" % run, "measured (live read) + declaration (bake)")
        unreal.log("INTERACTION_WALKIN_READY_APPLY_NOOP|run=%s|edits=0|saved=0|master_rebuild_required=false|"
                   "proposal=%s" % (run, PROPOSED_NAME))
        return

    # 0. backups + record BEFORE any change
    touched = sorted(int(n) for n in plan["edits"])
    paths = ["%s/%s" % (SEQ_DIR, SEQS[n]) for n in touched]
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    backup = os.path.join(project, "Backups", "PreWalkinReady-%s" % run)
    os.makedirs(backup, exist_ok=False)
    copied = []
    for p in paths:
        src = _content_file(p)
        dst = os.path.join(backup, os.path.basename(src))
        shutil.copy2(src, dst)
        if os.path.getsize(dst) != os.path.getsize(src):
            _stop(run, "BACKUP_SIZE_MISMATCH|" + src)
        copied.append(dst)
    record = {"schema_version": 1, "run": run, "world": EXPECTED_WORLD, "backup": backup, "backup_files": copied,
              "applied": False, "plan": plan, "plan_digest": plan_digest(plan),
              "before": {str(n): {"playback": lives[str(n)]["playback"], "gc": lives[str(n)]["gc"],
                                  "spawn": lives[str(n)]["spawn"]} for n in touched},
              "revert": "restore the backup .uassets with the editor closed (fit_transition_drapes.py precedent)"}
    _write_json(os.path.join(_here(), RECORD_NAME), record)

    # 1. edits (drape section ranges/offsets and the spawn range ONLY)
    for n in touched:
        _, h = _read_live(n)
        seq = h["seq"]
        seq.modify()
        for ed in plan["edits"][str(n)]:
            if ed["kind"] == "DRAPE_REFIT":
                if len(h["gc_sections"]) != 2:
                    _stop(run, "DRAPE_REFIT_SECTION_COUNT|I%d|%d (nothing saved; Don't-Save restart)" % (n, len(h["gc_sections"])))
                for s, row in zip(h["gc_sections"], ed["to"]):      # curtain_sleight.py:1703-1708 [prec, run 5 Oct]
                    s.set_range(int(row[0]), int(row[1]))
                    prm = s.get_editor_property("params")
                    prm.set_editor_property("start_frame_offset", unreal.FrameNumber(int(row[2])))
                    prm.set_editor_property("end_frame_offset", unreal.FrameNumber(int(row[3])))
                    s.set_editor_property("params", prm)
            elif ed["kind"] == "SPAWN_RANGE":
                h["spawn_sections"][0].set_range(int(ed["to"][0][0]), int(ed["to"][0][1]))   # fit_transition_drapes.py:149
        del seq, h

    # 2. exact dirty set, then save only those sequences
    census = _census()
    if census["maps"] or sorted(census["content"]) != sorted(paths):
        _stop(run, "UNEXPECTED_DIRTY|%s (nothing saved; Don't-Save restart; backup %s)" % (json.dumps(census), backup))
    saves = {p: bool(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False)) for p in paths}
    if not all(saves.values()):
        _stop(run, "SAVE_FAILED|%r" % saves)

    # 3. read back (asserted, not printed)
    after, problems = {}, []
    for n in touched:
        live, _ = _read_live(n)
        after[str(n)] = {"playback": live["playback"], "gc": live["gc"], "spawn": live["spawn"]}
        if live["playback"] != record["before"][str(n)]["playback"]:
            problems.append("PLAYBACK_CHANGED|I%d|%r" % (n, live["playback"]))
        for ed in plan["edits"][str(n)]:
            got = live["gc"] if ed["kind"] == "DRAPE_REFIT" else live["spawn"]
            if got != ed["to"]:
                problems.append("READBACK|I%d|%s|%r vs %r" % (n, ed["kind"], got, ed["to"]))
    census_after = _census()
    if census_after != {"content": [], "maps": []}:
        problems.append("DIRTY_AFTER|" + json.dumps(census_after))
    record.update({"saves": saves, "after": after, "census_after": census_after, "readback_problems": problems,
                   "applied": not problems})
    _write_json(os.path.join(_here(), RECORD_NAME), record)
    if problems:
        _stop(run, "READBACK_FAILED|" + ";".join(problems) + "|backup " + backup)
    rows2, _, _ = _gather_all(run, a)
    write_proposal(rows2, "live APPLY run=%s (after re-fit)" % run, "measured (live read-back after save) + declaration")
    unreal.log("INTERACTION_WALKIN_READY_APPLY_OK|run=%s|edited=%s|saved=%s|playback_unchanged=true|"
               "master_rebuild_required=false|backup=%s|proposal=%s"
               % (run, ",".join("I%d" % n for n in touched), json.dumps(saves), backup, PROPOSED_NAME))


def main():
    run = str(globals().get("WALKIN_READY_RUN_ID") or datetime.datetime.now().strftime("WR-%Y%m%d-%H%M%S"))
    try:
        _guards(run)
        a = merged_args(_load_json(os.path.join(_here(), ARGS_NAME), required=False))
        if bool(globals().get("WALKIN_READY_APPLY")):
            run_apply(run, a)
        else:
            run_dry(run, a)
    except Stopped:
        raise
    except ReadyError as exc:
        _stop(run, "READY_ERROR|" + str(exc))
    except Exception as exc:  # noqa: BLE001  (a STOPPED marker for every failure, never a silent one)
        _stop(run, "UNEXPECTED|%s: %s" % (type(exc).__name__, exc))


if unreal is not None:
    main()
elif __name__ == "__main__" and "--offline" in sys.argv:
    run_offline()
