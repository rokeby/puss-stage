"""P01 SHORTEN: drop the LAST N wing pairs ("bays") of Passage 1 by DISABLING their cues (never deleting them), so the
walk is a few bays shorter before passage_retime_to_music.py retimes it to Cameron's walk song + 2 s.
Gary 7 Oct: "Split the difference" - a bit faster AND a few bays fewer. Plan: P01_SHORTEN_PLAN.md.
Offline-written 7 Oct, NEVER RUN IN UNREAL. Harness: test_p01_shorten_offline.py (system Python).

Tiers per claim: [decl] declaration-proven (source/header, file:line), [prec] in-repo precedent call (cited), [meas] an
earlier run's read-back record (cited), [inf] inferred (why stated).

WHY DISABLE (and not delete, and not ResizePassageToDuration)
  * The compiler builds a Passage from each maximal run of ENABLED WingPair cues; a disabled cue ends the run and is
    skipped [decl InfinityStageCompiler.cpp:200-205, 240-246]. Its settings row is found by an EXACT (First, Last) cue
    GUID match [decl :81-89], so the P01 row's LastCueGuid must follow the new last bay or P01 loses its settings
    (lead/tail, music, Choreo). ReconcilePassageSettings (called inside RebuildManagedMaster [decl
    InfinityStageSequenceBuilderLibrary.cpp:208-209, 632-633]) re-derives it the same way - keeps the row whose old First
    lies in the new run and rewrites First/Last [decl InfinityStageShowAsset.cpp:126-181] - this tool ALSO writes it
    explicitly and asserts the rebuild left it there.
  * Disabled cues keep every field (GUIDs, meshes, attachments, timing), stay at the same array INDEX (records that hold
    show_index, e.g. lighting_scores_record_P01.json plan.scratch.show_index 51, stay valid), and are not materialised:
    attachments need a compiled wing [decl InfinityStagePassageActor.cpp:1850-1875 via :902-917]. REVERT = re-enable +
    old LastCueGuid: exact.
  * ResizePassageToDuration (the engine's resize) was REJECTED: it DELETES the trailing cues (Cues.RemoveAt [decl
    InfinityStageWingSequenceInterchange.cpp:709]), rewrites every interval/gap to PreferredSpacing/Speed and sets
    ManualPassage [decl InfinityStagePassageResizeLibrary.cpp:247-281], shifting later cue indices.
  * The Master rebuild DROPS wing pins of wings no longer in the Passage and relative pins >= the new length [decl
    InfinityStageSequenceBuilderLibrary.cpp:280-291]: both REFUSED here (they would not come back on REVERT).

WHAT MOVES
  * P01 length shrinks by the dropped bays' IntervalToNext (the new last bay's own interval becomes unused); the route
    (TotalDistanceCm) by their GapToNextCm [decl Compiler.cpp:262-288]. Lead/tail frames and distances are unchanged.
  * Every later Master section moves earlier by that time (rebuild MoveSection [decl SequenceBuilderLibrary.cpp:300-309]);
    the same gates as passage_retime_to_music.py (segments, managed sections, Passage keys, artist content, music fit).
  * P01's auto-fit straight route shrinks at materialise [decl InfinityStagePassageActor.cpp:772-786; meas
    probe_routes.json auto_fit_straight true]: the END VIEW moves back by the dropped distance (6 bays: 3600 cm [inf from
    600 cm spacing]). Scene 1's Entry Handoff camera and the S1 hangar dock sit at the OLD end (28784.0135, 0, 150)
    [meas Saved/CodexStructure/hangar_s1_record.json dock, scene_docks.json]. So Scene 1 goes STALE (allowed and
    asserted: only that Scene may newly go stale) and the S1 re-dock is a FOLLOW-ON this tool does not do (APPLY needs
    followons_ack, p02_straighten.py:76-82 precedent).

Modes (p01_shorten_run.py <- p01_shorten_args.json, confirm "<MODE> P01SHORTEN"):
  DRY    read-only; p01_shorten_dry.json; P01_SHORTEN_DRY_OK|run=..
  APPLY  guards -> refusals -> backup Show + Master + level to Backups/PreP01Shorten-<run> -> exclusive fsynced record
         (full export_text of every dropped cue + the P01 row) -> disable cues + LastCueGuid (read back; nothing else
         changed) -> RebuildManagedMaster -> gates -> MaterializePassage P01 (+ Structure 01 refit) -> end view moved
         by the dropped distance -> census subset {Show, Master, level} -> save those -> read-back -> census clean ->
         P01_SHORTEN_APPLY_OK|run=..
  REVERT LIFO (refuses while a P01 retime record is applied) -> drift check -> backup -> re-enable + old LastCueGuid
         -> rebuild -> == the record's BEFORE -> materialise -> save -> P01_SHORTEN_REVERT_OK|run=..
  Failure: P01_SHORTEN_STOPPED|run=..|reason=.. (nothing saved: Don't-Save restart; backup named)
Never: Save All, reload, open/scrub Sequencer, rematch, end PIE; no unreal objects in module globals. Importing without
`unreal` runs nothing.
"""
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "p01_shorten"
MARK = "P01_SHORTEN"
CONFIRM_SUFFIX = "P01SHORTEN"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ARGS_NAME = "p01_shorten_args.json"
DRY_NAME = "p01_shorten_dry.json"
RECORD_NAME = "p01_shorten_record.json"
RETIME_FILE = "passage_retime_to_music.py"
RETIME_RECORD_PREFIX = "passage_retime_to_music_record_"
PASSAGE_ACTOR_PREFIX = "Passage 01"           # lighting_scores_record_P01.json materialized.passage
END_VIEW_TOL_CM = 5.0
REQUIRED_ACKS = ("S1_REDOCK", "MATCH_S1_HANDOFF")
FOLLOWON_TEXT = {
    "S1_REDOCK": "move/rebuild the S1 hangar set (RigAtmos.Scene1* tags, exit doors, rise root key) to the new P01 end; "
                 "no tool yet (P01_SHORTEN_PLAN.md step 7)",
    "MATCH_S1_HANDOFF": "Saved/CodexCameraPilot/match_scene1_handoff.py (MatchNamedSceneHandoffs, Scene 1 only)",
    "RETIME_P01": "passage_retime_to_music.py passages [\"1\"] (DRY -> APPLY), prerequisite this record",
    "WALKIN_REEASE": "opening_sequence_apply.py DRY -> APPLY (re-measures P01's entry speed, :341-358)",
    "RECORDS_REPLAN": "re-plan records that name dropped bays (DRY orphan_scan) and p01_note_lamps (timing model)",
}
HEX32 = re.compile(r"^[0-9A-F]{32}$")


class PlanError(Exception):
    pass


# =====================================================================================================================
# Shared pure/live helpers from passage_retime_to_music.py, loaded WITHOUT running its main() (RETIME_IMPORT_ONLY).
# A fresh load per run (never sys.modules): editor Python keeps imports across MCP runs (memory: stale module cache).
# =====================================================================================================================

def load_retime(folder=None):
    path = os.path.join(folder or os.path.dirname(os.path.abspath(__file__)), RETIME_FILE)
    spec = importlib.util.spec_from_file_location("p01_shorten_retime_helpers", path)
    mod = importlib.util.module_from_spec(spec)
    mod.RETIME_IMPORT_ONLY = True
    spec.loader.exec_module(mod)
    if "1" not in mod.VALID_KEYS:
        raise PlanError("RETIME_TOOL_LACKS_P01: %s VALID_KEYS %r" % (path, mod.VALID_KEYS))
    return mod


# =====================================================================================================================
# Pure: args, plan, chain maths, orphan scan, gates (exercised by test_p01_shorten_offline.py)
# =====================================================================================================================

def _int_ok(v, minimum):
    return isinstance(v, int) and not isinstance(v, bool) and v >= minimum


def _num_ok(v, minimum=0.0):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v >= minimum


def bay_labels(fmt, count):
    return [fmt % (i + 1) for i in range(int(count))]


def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % args.get("mode"))
    if str(args.get("passage_label") or "") != "Passage 1":
        r.append("PASSAGE_LABEL_INVALID: %r (this tool is P01-only)" % args.get("passage_label"))
    if not HEX32.match(str(args.get("passage_guid") or "")):
        r.append("PASSAGE_GUID_INVALID: %r" % args.get("passage_guid"))
    bays = args.get("expected_bays")
    if not _int_ok(bays, 3):
        r.append("EXPECTED_BAYS_INVALID: %r" % bays)
        bays = None
    n = args.get("drop_last")
    if not _int_ok(n, 1) or (bays is not None and n > bays - 2):
        r.append("DROP_LAST_INVALID: %r (1 .. expected_bays - 2)" % n)
    fmt = str(args.get("bay_label_format") or "")
    if "%03d" not in fmt:
        r.append("BAY_LABEL_FORMAT_INVALID: %r" % fmt)
    guids = args.get("bay_guids")
    if not isinstance(guids, list) or (bays is not None and len(guids) != bays) or \
            not all(HEX32.match(str(g)) for g in guids or []) or len(set(guids or [])) != len(guids or []):
        r.append("BAY_GUIDS_INVALID: need %r distinct 32-hex GUIDs in bay order" % bays)
    if not isinstance(args.get("keep_labels"), list):
        r.append("KEEP_LABELS_INVALID")
    for f in ("song_s",):
        if not _num_ok(args.get(f), 0.001):
            r.append("ARG_%s_INVALID: %r" % (f.upper(), args.get(f)))
    for f in ("tail_s", "crossing_settle_s"):
        if not _num_ok(args.get(f)):
            r.append("ARG_%s_INVALID: %r" % (f.upper(), args.get(f)))
    if not str(args.get("sound") or "").startswith("/Game/"):
        r.append("SOUND_MISSING")
    if mode == "APPLY":
        if not str(args.get("decided_by") or "").strip():
            r.append("NOT_DECIDED: decided_by is empty")
        missing = [a for a in REQUIRED_ACKS if a not in (args.get("followons_ack") or [])]
        if missing:
            r.append("FOLLOWONS_NOT_ACKED: %s" % ",".join(missing))
        exp = args.get("expected") or {}
        for f in ("old_len_ticks", "new_len_ticks", "removed_ticks"):
            if not _int_ok(exp.get(f), 1):
                r.append("EXPECTED_%s_MISSING (copy it from the DRY)" % f.upper())
        if not _num_ok(exp.get("removed_cm"), 0.01):
            r.append("EXPECTED_REMOVED_CM_MISSING (copy it from the DRY)")
        if not isinstance(exp.get("dropped_guids"), list) or not exp.get("dropped_guids"):
            r.append("EXPECTED_DROPPED_GUIDS_MISSING (copy it from the DRY)")
    return r


def compiled_length(lead, intervals, tail):
    """Compiler.cpp:262-286: lead + every interval but the last wing's + tail."""
    return int(lead) + sum(int(x) for x in list(intervals)[:-1]) + int(tail)


def route_length(lead_cm, gaps, tail_cm):
    """Compiler.cpp:263-287: TotalDistanceCm = lead distance + every gap but the last wing's + tail distance."""
    return float(lead_cm) + sum(float(g) for g in list(gaps)[:-1]) + float(tail_cm)


def _label_no(label):
    m = re.search(r"(\d+)$", str(label))
    return int(m.group(1)) if m else None


def dropped_numbers(plan):
    """Bay numbers to look for in records: Show positions AND label numbers (they differ where cues were reordered)."""
    nums = set()
    for d in plan["dropped"]:
        nums.add(int(d["pos"]))
        if d.get("label_no") is not None:
            nums.add(int(d["label_no"]))
    return sorted(nums)


def plan_drop(facts, n, keep_labels, label_fmt, expected_bays, expected_guids=None):
    """facts: labels, guids, intervals, gaps, lead, tail, lead_cm, tail_cm, segment {start, end} of the live P01 range.
    Returns (plan, refusals)."""
    r = []
    labels, guids = list(facts["labels"]), list(facts["guids"])
    bays = len(labels)
    if bays != int(expected_bays):
        r.append("BAY_COUNT: live %d != expected %d (re-plan before dropping)" % (bays, expected_bays))
    want = bay_labels(label_fmt, bays)
    if sorted(labels) != want:
        r.append("BAY_LABEL_SET: live labels are not exactly %s..%s once each" % (want[0], want[-1]))
    # Show order is NOT label order: bays at positions 10-12 read 011, 012, 010 [meas show_wing_dump.json 4 Oct]. The
    # drop is by Show POSITION (the compiler's order, Compiler.cpp:240-246); labels are reported, never assumed.
    reordered = [(i + 1, a) for i, (a, b) in enumerate(zip(labels, want)) if a != b]
    if expected_guids is not None and list(expected_guids) != guids:
        r.append("BAY_GUIDS_CHANGED: live order != args bay_guids (lighting_scores_record_P01.json plan.bay_guids)")
    n = int(n)
    if n < 1 or n > bays - 2:
        raise PlanError("DROP_OUT_OF_RANGE: %d of %d bays" % (n, bays))
    kept = bays - n
    dropped = list(range(kept, bays))
    hit = [labels[i] for i in dropped if labels[i] in set(keep_labels or [])]
    if hit:
        r.append("KEEP_BAY_IN_DROP: %s (Gary's hand-set bays must stay)" % hit)
    seg = facts["segment"]
    old_len = int(seg["end"]) - int(seg["start"])
    c = compiled_length(facts["lead"], facts["intervals"], facts["tail"])
    if c != old_len:
        r.append("COMPILE_MODEL_MISMATCH: lead+intervals+tail %d != segment %d" % (c, old_len))
    removed_ticks = sum(int(x) for x in facts["intervals"][kept - 1:bays - 1])
    removed_cm = sum(float(x) for x in facts["gaps"][kept - 1:bays - 1])
    new_len = compiled_length(facts["lead"], facts["intervals"][:kept], facts["tail"])
    if old_len - removed_ticks != new_len and not r:
        raise PlanError("DROP_ARITHMETIC: %d - %d != %d" % (old_len, removed_ticks, new_len))
    route_old = route_length(facts["lead_cm"], facts["gaps"], facts["tail_cm"])
    route_new = route_length(facts["lead_cm"], facts["gaps"][:kept], facts["tail_cm"])
    plan = {"bays_before": bays, "drop": n, "bays_after": kept,
            "dropped": [{"pos": i + 1, "label": labels[i], "label_no": _label_no(labels[i]), "guid": guids[i]}
                        for i in dropped],
            "reordered_positions": reordered,
            "dropped_guids": [guids[i] for i in dropped],
            "new_last": {"pos": kept, "label": labels[kept - 1], "guid": guids[kept - 1]},
            "old_last": {"pos": bays, "label": labels[-1], "guid": guids[-1]},
            "old_len_ticks": old_len, "new_len_ticks": new_len, "removed_ticks": removed_ticks,
            "route_old_cm": round(route_old, 4), "route_new_cm": round(route_new, 4),
            "removed_cm": round(removed_cm, 4), "unused_last_interval": int(facts["intervals"][kept - 1]),
            "unused_last_gap_cm": float(facts["gaps"][kept - 1])}
    return plan, r


def chain_numbers(R, facts, n, song_s, tail_s, settle_s, tick, fps, settle_compensation=True):
    """Shorten by n, then retime to song + tail exactly as passage_retime_to_music.plan_passage does (same functions)."""
    kept = len(facts["intervals"]) - int(n)
    lead, iv, tail = facts["lead"], list(facts["intervals"][:kept]), facts["tail"]
    gaps = list(facts["gaps"][:kept])
    tgt = R.target_ticks(song_s, tail_s, tick, fps[0], fps[1])
    comp = R.settle_compensation_ticks(settle_s, tick) if settle_compensation else 0
    plan = R.add_settle_compensation(R.plan_scaled_timing(lead, iv, tail, tgt - comp), comp)
    old_v = R.speeds(facts["lead"], facts["intervals"], facts["tail"], facts["lead_cm"], facts["gaps"],
                     facts["tail_cm"], tick, settle_s)
    short_v = R.speeds(lead, iv, tail, facts["lead_cm"], gaps, facts["tail_cm"], tick, settle_s)
    new_v = R.speeds(plan["lead_frames"], plan["intervals"], plan["tail_frames"], facts["lead_cm"], gaps,
                     facts["tail_cm"], tick, settle_s)
    lead_old = facts["lead_cm"] / (facts["lead"] / float(tick)) if facts["lead"] else None
    lead_new = facts["lead_cm"] / (plan["lead_frames"] / float(tick)) if plan["lead_frames"] else None
    return {"drop": int(n), "bays": kept, "target_ticks": tgt, "target_s": tgt / float(tick),
            "shortened_len_s": round(compiled_length(lead, iv, tail) / float(tick), 6), "k": round(plan["k"], 6),
            "route_cm": short_v["route_cm"], "bay_speed_old": old_v["bay_max"], "bay_speed_new": new_v["bay_max"],
            "bay_speed_rise_pct": round((new_v["bay_max"] / old_v["bay_max"] - 1.0) * 100.0, 2),
            "mean_new": new_v["mean"], "tail_pre_settle_new": new_v["tail_pre_settle"],
            "lead_speed_old": round(lead_old, 3) if lead_old else None,
            "lead_speed_new": round(lead_new, 3) if lead_new else None, "new_len_s": plan["new_ticks"] / float(tick)}


def sweep(R, facts, ns, song_s, tail_s, settle_s, tick, fps):
    return [chain_numbers(R, facts, n, song_s, tail_s, settle_s, tick, fps) for n in ns]


def wing_pin_refusals(wing_pins, dropped_guids):
    hit = sorted(set(wing_pins or []) & set(dropped_guids))
    return ["WING_PIN_ON_DROPPED_BAY: %s (the rebuild deletes it, SequenceBuilderLibrary.cpp:280-285; REVERT could "
            "not restore it)" % hit] if hit else []


def relative_pin_refusals(pins_rel, new_len):
    late = [int(p) for p in pins_rel or [] if int(p) >= int(new_len)]
    return ["RELATIVE_PIN_PAST_NEW_END: %r >= %d (the rebuild deletes it, SequenceBuilderLibrary.cpp:286-291)" % (
        late, new_len)] if late else []


def label_patterns(dropped_positions, label_fmt):
    """Labels that name a dropped bay in records: the cue label and the score/lamp bay tag ("P01 SCORE B43 ...")."""
    out = []
    for pos in dropped_positions:
        out.append((label_fmt % pos, re.escape(label_fmt % pos) + r"(?!\d)"))
        out.append(("P01 SCORE B%02d" % pos, r"P01 SCORE B%02d(?!\d)" % pos))
    return out


def scan_orphans(paths, dropped_guids, dropped_positions, label_fmt):
    """Plain-text scan of records for dropped-bay GUIDs and labels. Read-only; hits are WHAT TO RE-PLAN, not errors."""
    pats = [(shown, re.compile(rx)) for shown, rx in label_patterns(dropped_positions, label_fmt)]
    rows = []
    for path in paths:
        row = {"path": path, "exists": os.path.exists(path), "guid_hits": {}, "label_hits": {}}
        if row["exists"]:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            for g in dropped_guids:
                c = text.upper().count(str(g).upper())
                if c:
                    row["guid_hits"][g] = c
            for src, rx in pats:
                c = len(rx.findall(text))
                if c:
                    row["label_hits"][src] = c
        row["orphaned"] = bool(row["guid_hits"] or row["label_hits"])
        rows.append(row)
    return rows


def expected_view_after(before, cue_rows, passage_row, new_last_guid):
    """protected_view() of the retime tool, patched with exactly this tool's writes: enabled False on the dropped cue
    rows (field 3) and LastCueGuid (field 3) on the P01 Passage row. Anything else differing = a stray write."""
    want = json.loads(json.dumps(before))
    for key in cue_rows:
        if key not in want:
            raise PlanError("VIEW_ROW_MISSING: %s" % key)
        want[key][3] = False
    want[passage_row][3] = new_last_guid
    return want


def view_diff(want, got):
    return sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))


def handoff_after_gate(stale_before, stale_after, allowed):
    new = sorted(set(stale_after or []) - set(stale_before or []))
    bad = [g for g in new if g not in set(allowed)]
    return ["HANDOFF_NEWLY_STALE_UNEXPECTED: %s (only Scene 1 may go stale)" % bad] if bad else []


def end_view_gate(before_xyz, after_xyz, removed_cm, tol=END_VIEW_TOL_CM):
    if before_xyz is None or after_xyz is None:
        return ["END_VIEW_UNREADABLE"]
    moved = sum((a - b) ** 2 for a, b in zip(after_xyz, before_xyz)) ** 0.5
    if abs(moved - float(removed_cm)) > tol:
        return ["END_VIEW_MOVED_WRONG: %.2f cm, want %.2f +- %.1f" % (moved, removed_cm, tol)]
    return []


def expected_refusals(plan, expected, mode):
    if mode != "APPLY":
        return []
    r = []
    for f in ("old_len_ticks", "new_len_ticks", "removed_ticks"):
        if int(expected.get(f, -1)) != int(plan[f]):
            r.append("%s_CHANGED_SINCE_DRY: live %d, args %r" % (f.upper(), plan[f], expected.get(f)))
    if abs(float(expected.get("removed_cm", -1)) - plan["removed_cm"]) > 0.01:
        r.append("REMOVED_CM_CHANGED_SINCE_DRY: live %.4f, args %r" % (plan["removed_cm"], expected.get("removed_cm")))
    if list(expected.get("dropped_guids") or []) != plan["dropped_guids"]:
        r.append("DROPPED_GUIDS_CHANGED_SINCE_DRY")
    return r


def live_gates(state):
    r = []
    mode = str(state.get("mode") or "").upper()
    want = "%s %s" % (mode, CONFIRM_SUFFIX)
    if state.get("confirm") != want:
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), want))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN (an open Sequencer evaluates and dirties the map)")
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode == "APPLY" and state.get("record_exists"):
        r.append("RECORD_EXISTS: %s (REVERT first)" % RECORD_NAME)
    if mode == "REVERT":
        if not state.get("record_applied"):
            r.append("NO_APPLIED_RECORD: %s" % RECORD_NAME)
        if state.get("retime_records"):
            r.append("P01_RETIME_STILL_APPLIED: %s (revert the retime first - LIFO)" % state["retime_records"])
    return r


def drift_refusals(live, record):
    return ["STATE_DRIFTED_SINCE_APPLY: %s" % f for f in ("timing", "segments", "managed", "flags")
            if live.get(f) != record["after"].get(f)]


def revert_exact_gate(live, record):
    return ["REVERT_NOT_EXACT: %s" % f for f in ("timing", "segments", "managed", "keys", "flags")
            if live.get(f) != record["before"].get(f)]


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local; R = the retime module loaded per run.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _range_rows(R, show, label):
    """Labels/guids/flags of P01's range plus the rows right after it (the disabled ones after an APPLY)."""
    f = R._passage_facts(show, label)
    cues = list(show.get_editor_property("cues"))
    rows = []
    for i in range(f["first"], f["last"] + 1):
        c = cues[i]
        rows.append({"index": i, "label": str(c.get_editor_property("label")), "guid": R._guid(c.get_editor_property(
            "cue_guid")), "enabled": bool(c.get_editor_property("enabled"))})
    return f, cues, rows


def _flags(R, show, guids):
    by = {}
    for i, c in enumerate(show.get_editor_property("cues")):
        g = R._guid(c.get_editor_property("cue_guid"))
        if g in guids:
            by[g] = [i, bool(c.get_editor_property("enabled"))]
    return by


def _p01_row(R, show, label):
    for i, p in enumerate(show.get_editor_property("passage_settings")):
        if str(p.get_editor_property("label")) == label:
            return i, p
    raise PlanError("PASSAGE_NOT_FOUND: %s" % label)


def _next_scene(R, cues, after_index):
    for i in range(after_index + 1, len(cues)):
        c = cues[i]
        if c.get_editor_property("enabled") and c.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            return {"index": i, "guid": R._guid(c.get_editor_property("cue_guid")),
                    "label": str(c.get_editor_property("label"))}
    return None


def _end_view(R, show, passage_guid_text):
    """match_scene1_handoff.py:104-106 precedent: compiled end-frame camera view of P01 (no gait bob)."""
    lib = unreal.InfinityStageCameraPilotLibrary
    guid = None
    for p in show.get_editor_property("passage_settings"):
        if R._guid(p.get_editor_property("passage_guid")) == passage_guid_text:
            guid = p.get_editor_property("passage_guid")
    if guid is None:
        return None
    fr = R.unwrap(lib.get_passage_frame_range(show, guid), 2)
    if fr is None:
        return None
    pose = R.unwrap(lib.get_passage_camera_pose(show, guid, int(fr[1])), 3)
    if pose is None:
        return None
    t = pose[0].translation
    return [float(t.x), float(t.y), float(t.z)]


def _region_inventory(old_end, removed_cm):
    """Read-only list of level actors near the old P01 end (the S1 dock region) - what the S1 re-dock must carry.
    The P01 lane was never inventoried (lane_inventory_130421.json covers lanes 2-6 only) [meas]."""
    if old_end is None:
        return {"error": "no end view"}
    x0, y0 = old_end[0] - float(removed_cm) - 1000.0, old_end[1]
    x1 = old_end[0] + 15000.0
    rows, by_tag = [], {}
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        loc = a.get_actor_location()
        if not (x0 <= loc.x <= x1 and abs(loc.y - y0) <= 5000.0):
            continue
        tags = [str(t) for t in a.tags]
        key = tags[0] if tags else "(untagged) " + a.get_class().get_name()
        by_tag[key] = by_tag.get(key, 0) + 1
        parent = a.get_attach_parent_actor()
        rows.append({"label": a.get_actor_label(), "class": a.get_class().get_name(), "loc": [round(loc.x, 1),
                     round(loc.y, 1), round(loc.z, 1)], "tags": tags[:4],
                     "parent": parent.get_actor_label() if parent else None})
    return {"window_x": [x0, x1], "window_dy": 5000.0, "count": len(rows), "by_first_tag": by_tag,
            "unparented": [r for r in rows if r["parent"] is None][:200]}


def _snapshot(R, show, master, dropped_guids):
    snap = R._snapshot(show, master, ["1"])
    snap["flags"] = _flags(R, show, dropped_guids)
    return snap


def _plain(snap):
    return {"timing": snap["timing"], "segments": snap["segments"], "managed": snap["managed"], "keys": snap["keys"],
            "flags": snap["flags"]}


def _orphan_paths(folder, args):
    saved = os.path.dirname(folder)
    return [os.path.normpath(os.path.join(saved, p)) for p in args.get("orphan_records") or []]


def _gather(R, args):
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    if show is None or master is None:
        raise PlanError("SHOW_OR_MASTER_DID_NOT_LOAD")
    label = args["passage_label"]
    tick = R._rate(show.get_editor_property("tick_resolution"))
    dr = show.get_editor_property("display_rate")
    fps = (dr.numerator, dr.denominator)
    f, cues, rows = _range_rows(R, show, label)
    refusals, warnings = [], []
    if f["guid"] != args["passage_guid"]:
        refusals.append("PASSAGE_GUID: live %s != args %s" % (f["guid"], args["passage_guid"]))
    snap0 = R._snapshot(show, master, ["1"])
    seg = [s for s in snap0["segments"] if s["label"] == label]
    if len(seg) != 1:
        raise PlanError("SEGMENT_MISSING: %s" % label)
    seg = seg[0]
    facts = {"labels": [x["label"] for x in rows], "guids": [x["guid"] for x in rows], "intervals": f["intervals"],
             "gaps": f["gaps"], "lead": f["lead"], "tail": f["tail"], "lead_cm": f["lead_cm"], "tail_cm": f["tail_cm"],
             "segment": seg}
    plan, r = plan_drop(facts, args["drop_last"], args.get("keep_labels"), args["bay_label_format"],
                        args["expected_bays"], args.get("bay_guids"))
    refusals += r
    snap = _snapshot(R, show, master, plan["dropped_guids"])
    pk = snap["keys"].get(f["guid"])
    if pk is None:
        refusals.append("MASTER_P01_SECTION_MISSING")
        pk = {"channels": {}, "pins_rel": [], "wing_pins": []}
    cr, notes = R.channel_refusals("1", pk["channels"], seg["start"], seg["end"])
    refusals += cr
    warnings += notes
    refusals += relative_pin_refusals(pk["pins_rel"], plan["new_len_ticks"])
    refusals += wing_pin_refusals(pk["wing_pins"], plan["dropped_guids"])
    refusals += R.mechanism_refusals("1", f["origins"])
    for lab, (_idx, _p) in sorted(R._passage_rows(show).items()):
        s = [x for x in snap["segments"] if x["label"] == lab]
        if lab != label and s and s[0]["start"] >= seg["end"]:
            refusals += R.mechanism_refusals(lab.replace("Passage ", ""), R._passage_facts(show, lab)["origins"],
                                             later=True)
    choreo = R._choreo_facts(f["choreo_obj"], master, f["guid"], tick)
    chr_, chw = R.choreo_refusals("1", choreo, plan["new_len_ticks"], False)
    refusals += chr_
    warnings += chw
    rail = R._rail(show, f["music_binding"]["rail"])
    music = dict(rail, mode=f["music_binding"]["mode"], offset=f["music_binding"]["offset"]) if rail else None
    mr, fit_row = R.music_refusals("1", dict(music, args_sound=args["sound"]) if music else None,
                                   plan["new_len_ticks"], tick, args["song_s"])
    refusals += mr
    deltas = {label: -plan["removed_ticks"]}
    old_end = snap["managed"]["Playback:master"][1]
    ar, aw = R.artist_refusals(snap["artist"], snap["markers"], seg["start"], old_end, -plan["removed_ticks"])
    refusals += ar
    warnings += aw
    if snap["dup"]:
        refusals.append("MANAGED_BLOCK_DUPLICATED: %s" % snap["dup"])
    show_rows, master_rows = R._label_rows(master, snap["segments"], tick, R._guid_by_label(show))
    refusals += R.sync_gate(show_rows, master_rows)
    stale, handoff_report = R._handoffs(show)
    if stale is None:
        refusals.append("HANDOFF_CHECK_FAILED: %s" % handoff_report)
    nxt = _next_scene(R, cues, f["last"])
    if nxt is None:
        refusals.append("NO_SCENE_AFTER_P01")
    settle_s, settle_src = R._settle_seconds(args.get("crossing_settle_s", 1.0))
    chain = sweep(R, facts, sorted(set([0, 4, 5, 6, 7, 8, int(args["drop_last"])])), args["song_s"], args["tail_s"],
                  settle_s, tick, fps)
    end_before = _end_view(R, show, f["guid"])
    orphans = scan_orphans(_orphan_paths(_here(), args), plan["dropped_guids"], dropped_numbers(plan),
                           args["bay_label_format"])
    refusals += expected_refusals(plan, args.get("expected") or {}, str(args.get("mode")).upper())
    report = {"tick_rate": tick, "display_rate": list(fps), "plan": plan, "deltas": deltas,
              "segments_predicted": R.predict_segments(snap["segments"], deltas), "old_show_end": old_end,
              "new_show_end": old_end - plan["removed_ticks"], "music_fit_after_shorten": fit_row,
              "settle_s": settle_s, "settle_source": settle_src, "chain_sweep": chain, "end_view_before": end_before,
              "predicted_end_view_after_x": (end_before[0] - plan["removed_cm"]) if end_before else None,
              "next_scene": nxt, "handoff_stale_before": stale, "handoff_report": handoff_report,
              "region_inventory": _region_inventory(end_before, plan["removed_cm"]), "orphan_scan": orphans,
              "choreo": choreo, "channels": pk["channels"], "pins_rel": pk["pins_rel"], "wing_pins": pk["wing_pins"],
              "followons": FOLLOWON_TEXT, "refusals": refusals, "warnings": warnings}
    return report, snap, show, master, f


def _backup(run, suffix):
    proj = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(proj, "Backups", "PreP01Shorten%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for path, ext in ((SHOW_PATH, ".uasset"), (MASTER_PATH, ".uasset"), (EXPECTED_WORLD, ".umap")):
        src = os.path.join(proj, "Content", *path[len("/Game/"):].split("/")) + ext
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = []
        for x in (src, dst):
            with open(x, "rb") as handle:
                digest.append(hashlib.sha256(handle.read()).hexdigest())
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"asset": path, "source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _write_flags(R, show, passage_index, indices, enabled, last_guid_text):
    """Arrays of structs are copies -> write back [prec passage_retime_to_music.py _write_timing]. The LastCueGuid is
    set from the live cue's own Guid object (no string parsing)."""
    show.modify()
    cues = list(show.get_editor_property("cues"))
    last_obj = None
    for c in cues:
        if R._guid(c.get_editor_property("cue_guid")) == last_guid_text:
            last_obj = c.get_editor_property("cue_guid")
    if last_obj is None:
        raise PlanError("LAST_GUID_NOT_IN_SHOW: %s" % last_guid_text)
    for i in indices:
        c = cues[i]
        c.set_editor_property("enabled", bool(enabled))
        cues[i] = c
    show.set_editor_property("cues", cues)
    ps = list(show.get_editor_property("passage_settings"))
    p = ps[passage_index]
    p.set_editor_property("last_cue_guid", last_obj)
    ps[passage_index] = p
    show.set_editor_property("passage_settings", ps)


def _materialize(show):
    """lighting_scores_apply.py:2879-2896 precedent: the one P01 Passage actor + its Structure refit."""
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStagePassageActor"
              and a.get_actor_label().startswith(PASSAGE_ACTOR_PREFIX) and a.get_editor_property("show_asset") == show]
    if len(actors) != 1:
        return ["PASSAGE_ACTOR_COUNT: %d" % len(actors)], None
    if not actors[0].materialize_passage():
        return ["PASSAGE_MATERIALIZE_FAILED"], None
    structs = [a for a in sub.get_all_level_actors() if a.get_class().get_name() == "InfinityStageStructureActor"
               and a.get_editor_property("passage") == actors[0]]
    if len(structs) > 1:
        return ["STRUCTURE_COUNT: %d" % len(structs)], None
    if structs and not structs[0].materialize_structure():
        return ["STRUCTURE_REFIT_FAILED"], None
    return [], {"passage": actors[0].get_actor_label(), "structure": structs[0].get_actor_label() if structs else None}


def _census_gate(R, allow_map):
    c = R._census()
    out = R.census_gate({"content": c["content"], "maps": []}, [SHOW_PATH, MASTER_PATH])
    bad_maps = [m for m in c["maps"] if not (allow_map and m == EXPECTED_WORLD)]
    if bad_maps:
        out.append("MAP_DIRTY: %s" % bad_maps)
    return out, c


def _save(run, R, record_path, backup):
    for path in (SHOW_PATH, MASTER_PATH):
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s|record=%s (REVERT or restore %s)" % (path, record_path, backup))
    if EXPECTED_WORLD in R._census()["maps"]:
        if not unreal.EditorLoadingAndSavingUtils.save_map(_world(), EXPECTED_WORLD):    # match_scene1_handoff.py:122
            _stop(run, "LEVEL_SAVE_FAILED|record=%s (restore %s)" % (record_path, backup))


def _log(run, report):
    p = report["plan"]
    unreal.log("%s_PLAN|run=%s|bays %d->%d|drop %s|new last %s|len %d->%d (-%d ticks, %.3f s)|route %.2f->%.2f cm" % (
        MARK, run, p["bays_before"], p["bays_after"], ",".join(d["label"] for d in p["dropped"]), p["new_last"]["label"],
        p["old_len_ticks"], p["new_len_ticks"], p["removed_ticks"], p["removed_ticks"] / report["tick_rate"],
        p["route_old_cm"], p["route_new_cm"]))
    for row in report["chain_sweep"]:
        unreal.log("%s_CHAIN|run=%s|%s" % (MARK, run, json.dumps(row, sort_keys=True)))
    for row in report["orphan_scan"]:
        if row["orphaned"] or not row["exists"]:
            unreal.log("%s_ORPHAN|run=%s|%s" % (MARK, run, json.dumps(row, sort_keys=True)))
    for text in report["refusals"]:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, text))
    for text in report["warnings"]:
        unreal.log("%s_WARNING|run=%s|%s" % (MARK, run, text))


def run_dry(R, args, run):
    report, _snap, _s, _m, _f = _gather(R, args)
    out = os.path.join(_here(), DRY_NAME)
    p = report["plan"]
    expected = {"old_len_ticks": p["old_len_ticks"], "new_len_ticks": p["new_len_ticks"],
                "removed_ticks": p["removed_ticks"], "removed_cm": p["removed_cm"], "dropped_guids": p["dropped_guids"]}
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(dict(report, tool=TOOL, run=run, mode="DRY", args=args, apply_ready=not report["refusals"],
                       expected_for_apply_args=expected), handle, indent=1, sort_keys=True, default=str,
                  ensure_ascii=False)
    _log(run, report)
    if R._census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(R._census()))
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|drop=%d|len_s=%.4f->%.4f|"
               "route_cm=%.2f->%.2f|report=%s" % (MARK, run, int(not report["refusals"]), len(report["refusals"]),
                                                  len(report["warnings"]), p["drop"], p["old_len_ticks"] / report[
                                                      "tick_rate"], p["new_len_ticks"] / report["tick_rate"],
                                                  p["route_old_cm"], p["route_new_cm"], out))


def _post_gates(R, report, before, after, show, label, passage_guid):
    f = []
    spans = R.retimed_spans(before["segments"], report["deltas"])
    f += R.segment_shift_gate(before["segments"], after["segments"], report["deltas"])
    f += R.managed_shift_gate(before["managed"], after["managed"], spans)
    keys_b = {g: v for g, v in before["keys"].items()}
    keys_a = {g: v for g, v in after["keys"].items()}
    f += R.keys_gate(keys_b, keys_a, spans)
    if after["dup"]:
        f.append("MANAGED_BLOCK_DUPLICATED_AFTER: %s" % after["dup"])
    if after["artist"] != before["artist"] or after["markers"] != before["markers"]:
        f.append("ARTIST_CONTENT_OR_MARKERS_CHANGED")
    seg = [s for s in after["segments"] if s["label"] == label]
    if len(seg) != 1 or seg[0]["end"] - seg[0]["start"] != report["plan"]["new_len_ticks"]:
        f.append("NEW_LENGTH_WRONG: %r" % seg)
    i, p = _p01_row(R, show, label)
    if R._guid(p.get_editor_property("passage_guid")) != passage_guid or \
            R._guid(p.get_editor_property("last_cue_guid")) != report["plan"]["new_last"]["guid"]:
        f.append("P01_ROW_AFTER_REBUILD: guid/last not as planned (ReconcilePassageSettings disagreed)")
    if any(v[1] for v in after["flags"].values()) or len(after["flags"]) != report["plan"]["drop"]:
        f.append("DROPPED_FLAGS_AFTER: %r" % after["flags"])
    if report["handoff_stale_before"] is not None:
        stale_after, rep = R._handoffs(show)
        allowed = [report["next_scene"]["guid"]] if report.get("next_scene") else []
        f += ["HANDOFF_CHECK_FAILED_AFTER: %s" % rep] if stale_after is None else handoff_after_gate(
            report["handoff_stale_before"], stale_after, allowed)
    return f


def run_apply(R, args, run):
    report, before, show, master, facts = _gather(R, args)
    if report["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(report["refusals"]))
    label, plan = args["passage_label"], report["plan"]
    record_path = os.path.join(_here(), RECORD_NAME)
    view_before = R.protected_view(show)
    p_index, p_row = _p01_row(R, show, label)
    cues = list(show.get_editor_property("cues"))
    drop_idx = [facts["first"] + d["pos"] - 1 for d in plan["dropped"]]
    for i, d in zip(drop_idx, plan["dropped"]):
        if R._guid(cues[i].get_editor_property("cue_guid")) != d["guid"]:
            _stop(run, "INDEX_GUID_MISMATCH|%d" % i)
    backup = _backup(run, "")
    unreal.log("%s_BACKUP_OK|run=%s|backup=%s" % (MARK, run, backup))
    record = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "backup": backup, "args": args,
              "decided_by": args.get("decided_by"), "applied": False, "plan": plan,
              "passage_index": p_index, "passage_row_export": p_row.export_text(),
              "dropped_rows": [{"index": i, "guid": d["guid"], "label": d["label"], "pos": d["pos"],
                                "export_text": cues[i].export_text()} for i, d in zip(drop_idx, plan["dropped"])],
              "old_last_guid": plan["old_last"]["guid"], "new_last_guid": plan["new_last"]["guid"],
              "end_view_before": report["end_view_before"], "followons_ack": args.get("followons_ack"),
              "written": datetime.datetime.now().isoformat(timespec="seconds"), "before": _plain(before)}
    R.write_record_exclusive(record_path, record)                  # BEFORE any change
    failures = []
    try:
        _write_flags(R, show, p_index, drop_idx, False, plan["new_last"]["guid"])
        want = expected_view_after(view_before, ["cue%03d" % i for i in drop_idx], "passage%02d" % p_index,
                                   plan["new_last"]["guid"])
        diff = view_diff(want, R.protected_view(show))
        if diff:
            failures.append("WRITE_NOT_EXACT: %s" % diff[:10])
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        failures.append("WRITE_RAISED: %r" % exc)
    if not failures:
        ok, text = R._rebuild(show, master)
        record["rebuild_report"] = text
        if not ok:
            failures.append("REBUILD_FAILED: %s" % text)
    if not failures:
        after = _snapshot(R, show, master, plan["dropped_guids"])
        failures += _post_gates(R, report, before, after, show, label, args["passage_guid"])
        record["after"] = _plain(after)
    if not failures and args.get("materialize", True):
        mf, mat = _materialize(show)
        failures += mf
        record["materialized"] = mat
        end_after = _end_view(R, show, args["passage_guid"])
        record["end_view_after"] = end_after
        failures += end_view_gate(report["end_view_before"], end_after, plan["removed_cm"])
    cg, census = _census_gate(R, bool(args.get("materialize", True)))
    failures += cg
    if failures:
        R.update_record(record_path, dict(record, applied=False, failed=failures))
        os.rename(record_path, record_path + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|NOTHING SAVED; Don't-Save restart (Show/Master/level unsaved in memory); backup %s" % (
            failures[:10], backup))
    _save(run, R, record_path, backup)
    record["applied"] = True
    R.update_record(record_path, record)
    final = _plain(_snapshot(R, unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH), plan["dropped_guids"]))
    dd = ["POST_SAVE_%s_DIFFERS" % k for k in ("timing", "segments", "managed", "keys", "flags")
          if final[k] != record["after"][k]]
    if R._census() != {"content": [], "maps": []}:
        dd.append("DIRTY_AFTER_SAVE: %s" % json.dumps(R._census()))
    if dd:
        record["post_save_readback_failed"] = dd
        R.update_record(record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|record kept (REVERT or restore %s)" % (dd, backup))
    unreal.log("%s_APPLY_OK|run=%s|dropped=%s|len_ticks=%d->%d|route_cm=%.2f->%.2f|end_view=%s|backup=%s|record=%s|"
               "tests_required_singly=InfinityStage.Editor.SavedMasterMatchesShow,"
               "InfinityStage.Editor.SceneCutBindingsResolve|followons=%s" % (
                   MARK, run, ",".join(d["label"] for d in plan["dropped"]), plan["old_len_ticks"],
                   plan["new_len_ticks"], plan["route_old_cm"], plan["route_new_cm"], record.get("end_view_after"),
                   backup, record_path, ",".join(sorted(FOLLOWON_TEXT))))


def run_revert(R, args, run):
    record_path = os.path.join(_here(), RECORD_NAME)
    with open(record_path, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied") or not record.get("after"):
        _stop(run, "REVERT_RECORD_CONTEXT")
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    plan, label = record["plan"], record["args"]["passage_label"]
    snap = _snapshot(R, show, master, plan["dropped_guids"])
    drift = drift_refusals(_plain(snap), record)
    p_index, p_row = _p01_row(R, show, label)
    if p_index != record["passage_index"] or R._guid(p_row.get_editor_property("last_cue_guid")) != \
            record["new_last_guid"]:
        drift.append("P01_ROW_MOVED_OR_LAST_CHANGED")
    if drift:
        _stop(run, "%r (restore from %s instead)" % (drift, record["backup"]))
    show_rows, master_rows = R._label_rows(master, snap["segments"], snap["tick"], R._guid_by_label(show))
    stale = R.sync_gate(show_rows, master_rows)
    if stale:
        _stop(run, "MASTER_NOT_IN_SYNC_BEFORE_REVERT|%r" % stale[:6])
    view_before = R.protected_view(show)
    end_before = _end_view(R, show, record["args"]["passage_guid"])
    backup = _backup(run, "Revert")
    idx = [row["index"] for row in record["dropped_rows"]]
    errs = []
    try:
        _write_flags(R, show, p_index, idx, True, record["old_last_guid"])
        want = json.loads(json.dumps(view_before))
        for i in idx:
            want["cue%03d" % i][3] = True
        want["passage%02d" % p_index][3] = record["old_last_guid"]
        diff = view_diff(want, R.protected_view(show))
        if diff:
            errs.append("WRITE_NOT_EXACT: %s" % diff[:10])
    except Exception as exc:  # noqa: BLE001
        errs.append("WRITE_RAISED: %r" % exc)
    if not errs:
        ok, text = R._rebuild(show, master)
        if not ok:
            errs.append("REBUILD_FAILED: %s" % text)
        else:
            errs += revert_exact_gate(_plain(_snapshot(R, show, master, plan["dropped_guids"])), record)
    if not errs and record["args"].get("materialize", True):
        mf, _mat = _materialize(show)
        errs += mf
        errs += end_view_gate(end_before, _end_view(R, show, record["args"]["passage_guid"]), plan["removed_cm"])
    cg, _c = _census_gate(R, bool(record["args"].get("materialize", True)))
    errs += cg
    if errs:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart, then restore %s" % (errs[:8], record["backup"]))
    _save(run, R, record_path, backup)
    final = revert_exact_gate(_plain(_snapshot(R, unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH),
                                               plan["dropped_guids"])), record)
    if R._census() != {"content": [], "maps": []}:
        final.append("DIRTY_AFTER_SAVE: %s" % json.dumps(R._census()))
    if final:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (final, record["backup"]))
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("%s_REVERT_OK|run=%s|reenabled=%d|backup=%s|record=%s" % (MARK, run, len(idx), backup, archived))


def main():
    g = globals()
    args = g.get("P01SHORTEN_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("P01SHORT-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    R = load_retime(_here())
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    here = _here()
    rp = os.path.join(here, RECORD_NAME)
    applied = False
    if os.path.exists(rp):
        with open(rp, "r", encoding="utf-8") as handle:
            applied = bool(json.load(handle).get("applied"))
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": R._census(), "record_exists": os.path.exists(rp), "record_applied": applied,
             "retime_records": R.records_covering(here, ["1"]) if mode == "REVERT" else []}
    early = live_gates(state)
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        if mode == "REVERT":
            run_revert(R, args, run)
        elif mode == "APPLY":
            run_apply(R, args, run)
        else:
            run_dry(R, args, run)
    except (PlanError, R.PlanError) as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
