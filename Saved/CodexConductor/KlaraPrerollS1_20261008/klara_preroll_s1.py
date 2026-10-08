"""KLARA PREROLL S1 (8 Oct): the three S1 animals are ALREADY EATING while the light strikes reveal them, and nothing
restarts or snaps at the reveal cut (Scene frame 594). Gary 8 Oct chose option (c) "pre-roll" from
Docs/Conductor/S1_ANIMALS_SNAP_INVESTIGATION_2026-10-08.md section 4.2.
Offline-written, NEVER RUN IN UNREAL by its author. Harness: test_klara_preroll_s1.py (pure parts + a fake editor).

Mirrors KlaraIngest/klara_preroll_s4.py (stripped duplicate, a new sub track, record-first, narrow save, read back),
with three S1 differences:
  1. the strip is a WHITELIST: only the three animal bindings survive, and on them only SkeletalAnimation and
     ControlRigParameter tracks (their Transform tracks go too); every root track (camera cut, audio) goes;
  2. LOOP ALIGNMENT: in the duplicate, the skeletal section each animal plays at the cut is EXTENDED EARLIER by a whole
     number of its own clip loops (start moved, end kept), so its clip phase is unchanged at every time [inf: wrap at
     the clip length is MapTimeToAnimation, .cpp only] and it covers the whole pre-roll; the duplicate's PlaybackRange
     start is moved earlier to cover it;
  3. the pre-roll sub-section maps Scene 594 onto the SAME tick of hers as the main slot (her -161600 = her frame -202),
     so at 593 the duplicate is one Scene frame before the main slot's first pose. The section ends at 594 EXCLUSIVE:
     the Pig/Deer cross-fade into their second eating loop (0.6-0.7 s after the cut) is never evaluated by it.
The main slot (Shots, LS_Animals_1_S1Hangar over [594, 5769), offset 86400) is NOT touched. Her original
/Game/KK_S1_Animals/LS_Animals_1, the copy LS_Animals_1_S1Hangar and her streamed levels are never written.

Modes (args klara_preroll_s1_args.json; confirm "<MODE> KLARAPREROLLS1" for APPLY/REVERT):
  PROBE  PIE only, READ ONLY: arms a post-tick callback (prec klara_pendulum_s4.py run_probe [meas: its probe file
         KLARAPENDULUM-20261007-134048 status complete]); at Scene frames args.probe.frames (default 300, 593 + 600 as
         a post-cut reference) it records, per animal, AnimationMode, anim-instance class, actor location and three
         bone transforms on `burst` consecutive ticks -> klara_preroll_s1_probe_<run>.json;
         KLARAPREROLLS1_PROBE_OK|run=..|answer=.. ("do they move before 594").
  DRY    editor, read only -> klara_preroll_s1_dry.json; KLARAPREROLLS1_DRY_OK|run=..|apply_ready=..
  APPLY  gates -> Backups/PreKlaraPrerollS1-<run>/ -> exclusive record -> duplicate -> strip -> read back -> extend
         sections + playback start -> read back + alignment from LIVE values -> sub track + section [P0, 594) ->
         mapping read back -> census exactly {scene, dup} + 0 maps -> save those two -> census 0+0 -> reload read back
         -> KLARAPREROLLS1_APPLY_OK|run=..
  REVERT drift check -> Backups/PreKlaraPrerollS1Revert-<run>/ -> remove OUR track (one section) -> read back -> census
         exactly {scene} -> save -> 0+0 -> referencers of the duplicate must be none -> record renamed
         -> KLARAPREROLLS1_REVERT_OK|run=..|dup_left_on_disk=<path>. The duplicate stays on disk, unreferenced.
Failure: KLARAPREROLLS1_FAILED|run=<id>|<reason> (nothing saved unless the reason says so).
Never: Save All, reload a level, open/scrub Sequencer or the Master, save any map (her streamed levels above all),
end PIE, issue transport commands; no unreal objects in module globals (memory: editor crash).
Tiers in comments: [decl] UE 5.8 header, [prec] in-repo precedent (which may itself be unrun), [meas] record/log of a
live run, [bin] offline .uasset read, [inf] inferred (probed in the DRY api table where possible).
"""
import datetime
import hashlib
import json
import math
import os
import shutil
import time

try:
    import unreal
except ModuleNotFoundError:  # Offline harness without the fake.
    unreal = None

TOOL = "klara_preroll_s1"
MARK = "KLARAPREROLLS1"
CONFIRM_WORD = "KLARAPREROLLS1"
MODES = ("PROBE", "DRY", "APPLY", "REVERT")
FOLDER = "KlaraPrerollS1_20261008"
ARGS_NAME = "klara_preroll_s1_args.json"
RECORD_NAME = "klara_preroll_s1_record.json"
DRY_NAME = "klara_preroll_s1_dry.json"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE_SEQUENCE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_01"
OUR_PREFIX = "/Game/InfinityStage/KlaraHookin/"
HER_LEVELS = ("/Game/KK_S1_Animals/L_Animals", "/Game/L_KK_children", "/Game/Japanese_Alley/Maps/Japanese_Alley")
HER_PREFIXES = ("/Game/KK_", "/Game/L_KK_children", "/Game/Japanese_Alley/")
KEEP_TRACK_CLASSES = ("MovieSceneSkeletalAnimationTrack", "MovieSceneControlRigParameterTrack")
SKEL_TRACK = "MovieSceneSkeletalAnimationTrack"


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure (harness-tested)
# =====================================================================================================================

def is_her_asset(path, her_original=None):
    p = str(path or "")
    return p.startswith(HER_PREFIXES) or p in HER_LEVELS or (her_original is not None and p == her_original)


def validate_args(a):
    r = []
    mode = str(a.get("mode") or "").upper()
    if mode not in MODES:
        r.append("MODE_INVALID: %r" % a.get("mode"))
    for k in ("scene_sequence", "copy", "her_original", "dup_path", "track_name", "reveal_record", "her_level",
              "animals", "preroll_range"):
        if not a.get(k):
            r.append("MISSING_%s" % k.upper())
    sp, cp, dp, ho = (str(a.get(k) or "") for k in ("scene_sequence", "copy", "dup_path", "her_original"))
    if sp and sp != SCENE_SEQUENCE:
        r.append("TARGET_NOT_LS_DEVSCENE_01: %s" % sp)
    if "Master" in sp:
        r.append("TARGET_IS_THE_MASTER")
    if dp:
        if not dp.startswith(OUR_PREFIX):
            r.append("DUP_PATH_NOT_OURS: %s (must be under %s)" % (dp, OUR_PREFIX))
        if is_her_asset(dp, ho or None):
            r.append("DUP_PATH_IS_HERS: %s" % dp)
        if dp in (cp, ho, sp):
            r.append("DUP_PATH_COLLIDES: %s" % dp)
    if cp and not cp.startswith(OUR_PREFIX):
        r.append("COPY_NOT_OURS: %s" % cp)
    if ho and not is_her_asset(ho):
        r.append("HER_ORIGINAL_NOT_UNDER_HER_PREFIXES: %s" % ho)
    if a.get("completion", "RESTORE_STATE") not in ("RESTORE_STATE", "KEEP_STATE"):
        r.append("COMPLETION_INVALID: %r" % a.get("completion"))
    pr = a.get("preroll_range")
    if pr is not None and (not isinstance(pr, (list, tuple)) or len(pr) != 2 or int(pr[0]) >= int(pr[1])):
        r.append("PREROLL_RANGE_INVALID: %r" % (pr,))
    an = a.get("animals")
    if an is not None and (not isinstance(an, dict) or not all(isinstance(v, dict) and v.get("binding")
                                                               for v in an.values())):
        r.append("ANIMALS_INVALID: each needs a 'binding' (the copy's binding display name)")
    if int(a.get("extra_loops", 0)) < 0:
        r.append("EXTRA_LOOPS_NEGATIVE")
    return r


def write_guard(path, args):
    """Every save goes through this: only the Scene sequence and OUR duplicate; never hers, the copy or a map."""
    r = []
    p = str(path or "")
    if p not in (args.get("scene_sequence"), args.get("dup_path")):
        r.append("WRITE_NOT_ALLOWED: %s (allowed: scene_sequence, dup_path)" % p)
    if is_her_asset(p, args.get("her_original")):
        r.append("WRITE_TARGETS_HER_ASSET: %s" % p)
    if p == args.get("copy"):
        r.append("WRITE_TARGETS_THE_COPY: %s" % p)
    if p == EXPECTED_WORLD or "/Maps/" in p:
        r.append("WRITE_TARGETS_A_MAP: %s" % p)
    return r


def her_dirty(census):
    c = census or {}
    return sorted([m for m in c.get("maps") or [] if is_her_asset(m)] +
                  [p for p in c.get("content") or [] if is_her_asset(p)])


def live_gates(state):
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode in ("APPLY", "REVERT") and state.get("confirm") != "%s %s" % (mode, CONFIRM_WORD):
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s %s" % (mode, CONFIRM_WORD)))
    if mode == "PROBE":
        if not state.get("pie"):
            r.append("PROBE_NEEDS_PIE (start S1 in PIE first; this never starts or ends PIE)")
        return r
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("wrong_world"):
        r.append("WRONG_WORLD: %s" % state["wrong_world"])
    if state.get("sequencer_open"):
        r.append("SEQUENCER_OPEN: %s (close it with close_sequencer.py; opening/scrubbing dirties the map)"
                 % state["sequencer_open"])
    hd = her_dirty(state.get("census"))
    if hd:
        r.append("KLARA_LEVEL_DIRTY: %s (never saved here; Don't-Save restart, memory klara-streamed-levels-traps)" % hd)
    c = state.get("census") or {}
    if c.get("content") or c.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(c, sort_keys=True))
    if mode == "APPLY" and not str(state.get("decided_by") or "").strip():
        r.append("NOT_DECIDED: args decided_by is empty")
    if mode == "APPLY" and state.get("record_exists"):
        r.append("RECORD_EXISTS: %s (REVERT first)" % state["record_exists"])
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


def census_gate(census, want_content):
    out = []
    if sorted(census.get("content") or []) != sorted(want_content):
        out.append("CONTENT_CENSUS: got %s want %s" % (sorted(census.get("content") or []), sorted(want_content)))
    if census.get("maps"):
        out.append("MAP_CENSUS: got %s want []" % sorted(census["maps"]))
    hd = her_dirty(census)
    if hd:
        out.append("KLARA_LEVEL_DIRTY: %s" % hd)
    return out


def _int_ratio(a, b, what):
    q = float(a) / float(b)
    if abs(q - round(q)) > 1e-9:
        raise PlanError("%s_NOT_INTEGER: %s / %s = %r" % (what, a, b, q))
    return int(round(q))


def preroll_mapping(pr_range, slot, copy_play_start_frame, her_tick_res, her_fps, scene_fps):
    """slot = {"range": [C, E], "offset_ticks"} (the main slot, live) -> the pre-roll's time mapping, all in HER ticks.
    The main slot plays her tick  copy_start*her_tpf + offset + (f - C)*hps  at Scene frame f (prec klara_reveal
    SLOT_MAPPING_READBACK; start_frame_offset in her TICKS [meas klara_reveal_record_S1.json slot start_offset_ticks
    86400 = her frame -202 at the cut]). The duplicate must play the SAME tick at every f in [P0, C): its playback
    start is floor(pre_start / her_tpf) her frames, its offset the remainder."""
    r = []
    her_tpf = _int_ratio(her_tick_res, her_fps, "HER_TICKS_PER_FRAME")
    hps = _int_ratio(her_tick_res, scene_fps, "HER_TICKS_PER_SCENE_FRAME")
    P0, P1 = int(pr_range[0]), int(pr_range[1])
    C = int(slot["range"][0])
    if P1 > C:
        r.append("DUP_PAST_CUT: pre-roll ends %d > cut %d (the duplicate must end at the cut, exclusive)" % (P1, C))
    elif P1 != C:
        r.append("PREROLL_END_NOT_THE_CUT: %d vs cut %d (a gap would show the static level pose)" % (P1, C))
    if not P0 < P1:
        r.append("PREROLL_EMPTY: [%d, %d)" % (P0, P1))
    cut_tick = int(copy_play_start_frame) * her_tpf + int(slot["offset_ticks"])
    pre_start = cut_tick - (C - P0) * hps
    dps = int(math.floor(float(pre_start) / her_tpf))
    off = pre_start - dps * her_tpf
    return {"refusals": r, "range": [P0, P1], "cut": C, "her_tpf": her_tpf, "her_ticks_per_scene_frame": hps,
            "cut_her_tick": cut_tick, "cut_her_frame": cut_tick / float(her_tpf), "pre_start_her_tick": pre_start,
            "dup_playback_start_frame": dps, "offset_ticks": off}


def her_tick_dup(m, f):
    return m["dup_playback_start_frame"] * m["her_tpf"] + m["offset_ticks"] + (int(f) - m["range"][0]) * \
        m["her_ticks_per_scene_frame"]


def her_tick_main(m, f):
    return m["cut_her_tick"] + (int(f) - m["cut"]) * m["her_ticks_per_scene_frame"]


def plan_loop_shifts(secs_by_animal, m, extra_loops=0, expected_loops=None):
    """secs_by_animal = {animal: [{"key", "track", "start", "end" (her ticks), "anim", "len_s", "tick_res",
    "start_off", "end_off", "first_loop_off", "rate", "reverse", "bounded"}]} (the copy's skeletal sections, live).
    Per animal: exactly one section active at the cut tick; it is extended earlier by k whole clip loops (k minimal to
    cover the pre-roll start, + extra_loops); clip phase at the cut is unchanged by construction."""
    rows, r = [], []
    cut, pre = m["cut_her_tick"], m["pre_start_her_tick"]
    INF = float("inf")
    for animal in sorted(secs_by_animal):
        secs = [dict(s, start=-INF if s.get("start") is None else s["start"],
                     end=INF if s.get("end") is None else s["end"]) for s in secs_by_animal[animal]]
        active = [s for s in secs if s["start"] <= cut < s["end"]]
        if len(active) != 1:
            r.append("ACTIVE_AT_CUT_COUNT: %s has %d skeletal sections at her tick %d" % (animal, len(active), cut))
            continue
        a = active[0]
        bad = []
        if not a.get("bounded", True) or a["start"] == -INF or a["end"] == INF:
            bad.append("unbounded range")
        if int(a.get("start_off") or 0) or int(a.get("end_off") or 0) or int(a.get("first_loop_off") or 0):
            bad.append("offsets start %s end %s first_loop %s" % (a.get("start_off"), a.get("end_off"),
                                                                  a.get("first_loop_off")))
        if a.get("rate") is None or abs(float(a["rate"]) - 1.0) > 1e-9:
            bad.append("play rate %r" % a.get("rate"))
        if a.get("reverse"):
            bad.append("reverse")
        if not a.get("len_s") or float(a["len_s"]) <= 0:
            bad.append("clip length %r" % a.get("len_s"))
        if bad:
            r.append("UNSUPPORTED_SECTION: %s %s (%s): loop maths assumes offsets 0, rate 1, forward" %
                     (animal, a["key"], "; ".join(bad)))
            continue
        exact = float(a["len_s"]) * float(a["tick_res"])
        L = int(round(exact))
        if abs(exact - L) > 1.0:
            r.append("CLIP_LEN_NOT_ON_TICK: %s %.6f s = %.3f ticks" % (animal, a["len_s"], exact))
            continue
        others = [s for s in secs if s is not a and s["start"] < cut and s["end"] > pre]
        if others:
            r.append("OTHER_SECTION_IN_PREROLL: %s %s" % (animal, [s["key"] for s in others]))
            continue
        k = 0 if a["start"] <= pre else int(math.ceil(float(a["start"] - pre) / L)) + int(extra_loops)
        shift = k * L
        if shift % m["her_tpf"]:
            r.append("SHIFT_NOT_ON_FRAME: %s %d ticks (%d loops x %d) not a multiple of %d" %
                     (animal, shift, k, L, m["her_tpf"]))
            continue
        new_start = a["start"] - shift
        clash = [s["key"] for s in secs if s is not a and s["start"] < a["end"] and s["end"] > new_start and
                 not (s["start"] < a["end"] and s["end"] > a["start"])]
        if clash:
            r.append("NEW_OVERLAP: %s extended section would overlap %s" % (animal, clash))
            continue
        if expected_loops and animal in expected_loops and int(expected_loops[animal]) != k:
            r.append("LOOPS_DIFFER_FROM_EXPECTED: %s computed %d, args expected %d" % (animal, k, expected_loops[animal]))
        rows.append({"animal": animal, "key": a["key"], "track": a.get("track"), "anim": a["anim"],
                     "clip_s": float(a["len_s"]), "loop_ticks": L, "loops": k, "shift_ticks": shift,
                     "shift_s": shift / float(a["tick_res"]), "old_range": [a["start"], a["end"]],
                     "new_range": [new_start, a["end"]], "tick_res": a["tick_res"],
                     "clip_time_at_cut_s": ((cut - a["start"]) % L) / float(a["tick_res"])})
    return {"rows": rows, "refusals": r}


def phase_gap(t_a, start_a, t_b, start_b, L):
    """Circular distance, in ticks, between two clip phases."""
    d = ((t_a - start_a) - (t_b - start_b)) % L
    return min(d, L - d)


def check_alignment(plan_rows, m, live_new_starts=None, dup_range=None):
    """At the cut the duplicate (continued) and the main slot must sit at the same clip phase, within ONE her frame
    (strictly less), the extended section must cover the pre-roll start, the duplicate must end at the cut."""
    r = []
    C = m["cut"]
    rng = list(dup_range) if dup_range is not None else list(m["range"])
    if int(rng[1]) > C:
        r.append("DUP_PAST_CUT: duplicate section ends %d > cut %d" % (int(rng[1]), C))
    if her_tick_dup(m, C) != her_tick_main(m, C):
        r.append("MAPPING_MISALIGNED: dup %d vs main %d her ticks at Scene %d" %
                 (her_tick_dup(m, C), her_tick_main(m, C), C))
    if m["dup_playback_start_frame"] * m["her_tpf"] > m["pre_start_her_tick"]:
        r.append("DUP_PLAYBACK_START_LATE: %d > %d" % (m["dup_playback_start_frame"] * m["her_tpf"],
                                                      m["pre_start_her_tick"]))
    for row in plan_rows:
        ns = int((live_new_starts or {}).get(row["animal"], row["new_range"][0]))
        L = int(row["loop_ticks"])
        gap = phase_gap(her_tick_dup(m, C), ns, her_tick_main(m, C), int(row["old_range"][0]), L)
        if gap >= m["her_tpf"]:
            r.append("MISALIGNED_AT_CUT: %s phase gap %d ticks (>= one her frame %d)" % (row["animal"], gap, m["her_tpf"]))
        if ns > her_tick_dup(m, rng[0]):
            r.append("PREROLL_NOT_COVERED: %s section starts %d after the pre-roll start %d" %
                     (row["animal"], ns, her_tick_dup(m, rng[0])))
    return r


def classify_strip(rows, animal_bindings, root_tracks):
    """WHITELIST. rows = [{"guid", "name", "parent", "tracks": [{"cls", "name"}]}]. Keep the top-level animal bindings
    (and their children); remove every other binding (children before parents), every root track, and on kept
    bindings every track whose class is not in KEEP_TRACK_CLASSES."""
    by = {r["guid"]: r for r in rows}
    want = set(animal_bindings)
    r = []
    tops = [x for x in rows if x["name"] in want and not (x.get("parent") and x["parent"] in by)]
    for n in sorted(want):
        c = len([x for x in tops if x["name"] == n])
        if c != 1:
            r.append("ANIMAL_BINDING_COUNT: %r x%d" % (n, c))
    keep = {x["guid"] for x in tops}
    changed = True
    while changed:
        changed = False
        for x in rows:
            if x["guid"] not in keep and x.get("parent") in keep:
                keep.add(x["guid"])
                changed = True
    depth = lambda g: 0 if not by.get(g, {}).get("parent") or by[g]["parent"] not in by else 1 + depth(by[g]["parent"])
    remove = sorted([{"guid": x["guid"], "name": x["name"]} for x in rows if x["guid"] not in keep],
                    key=lambda x: (-depth(x["guid"]), x["name"]))
    strip_tracks = [{"binding": by[g]["name"], "guid": g, "cls": t["cls"], "name": t.get("name")}
                    for g in sorted(keep) for t in by[g].get("tracks") or [] if t["cls"] not in KEEP_TRACK_CLASSES]
    for x in tops:
        if not any(t["cls"] == SKEL_TRACK for t in x.get("tracks") or []):
            r.append("NO_SKELETAL_TRACK: %s" % x["name"])
    return {"keep": sorted(keep), "remove": remove, "strip_tracks": strip_tracks,
            "root_tracks": [t["cls"] for t in root_tracks or []], "refusals": r}


def verify_strip(after_rows, after_root, cut_sections, animal_bindings):
    """Read-back of the stripped duplicate; any leftover is a refusal (NOTHING SAVED)."""
    r = []
    by = {x["guid"]: x for x in after_rows}
    if after_root:
        r.append("ROOT_TRACKS_LEFT: %s" % [t["cls"] for t in after_root])
    if cut_sections:
        r.append("CUT_SECTIONS_LEFT: %d" % cut_sections)
    tops = [x for x in after_rows if not (x.get("parent") and x["parent"] in by)]
    foreign = sorted(x["name"] for x in tops if x["name"] not in set(animal_bindings))
    if foreign:
        r.append("FOREIGN_BINDINGS_LEFT: %s" % foreign)
    missing = sorted(set(animal_bindings) - {x["name"] for x in tops})
    if missing:
        r.append("ANIMAL_BINDINGS_MISSING: %s" % missing)
    extra = sorted({"%s:%s" % (x["name"], t["cls"]) for x in after_rows for t in x.get("tracks") or []
                    if t["cls"] not in KEEP_TRACK_CLASSES})
    if extra:
        r.append("NON_ANIMATION_TRACK_LEFT: %s" % extra)
    return r


def skel_fingerprint(secs_by_animal):
    h = hashlib.sha256()
    for animal in sorted(secs_by_animal):
        for s in sorted(secs_by_animal[animal], key=lambda x: (x["start"], x["end"], x["anim"])):
            h.update(("%s|%s|%d|%d|%s|%s|%s;" % (animal, s["anim"], s["start"], s["end"], s.get("start_off"),
                                                 s.get("end_off"), s.get("first_loop_off"))).encode())
    return h.hexdigest()


def revert_check(rec, now, args):
    """now = {"ours": [{"sections": [{"range", "sequence", "offset"}]}], "others": [scene track names, ours excluded]}"""
    r = []
    ours = now.get("ours") or []
    secs = [s for t in ours for s in t.get("sections") or []]
    sec = (rec or {}).get("section") or {}
    if len(ours) != 1 or len(secs) != 1:
        r.append("STATE_DRIFTED: %d tracks %d sections named %r" % (len(ours), len(secs), args.get("track_name")))
    else:
        s = secs[0]
        if s.get("sequence") != args.get("dup_path"):
            r.append("STATE_DRIFTED: section plays %s, record %s" % (s.get("sequence"), args.get("dup_path")))
        if list(s.get("range") or []) != list(sec.get("range") or []):
            r.append("STATE_DRIFTED: range %s, record %s" % (s.get("range"), sec.get("range")))
        if s.get("offset") != sec.get("offset_ticks"):
            r.append("STATE_DRIFTED: offset %s, record %s" % (s.get("offset"), sec.get("offset_ticks")))
    if list(now.get("others") or []) != list(((rec or {}).get("before") or {}).get("scene_tracks") or []):
        r.append("STATE_DRIFTED: other scene tracks %s vs record %s" % (now.get("others"),
                                                                       (rec.get("before") or {}).get("scene_tracks")))
    return r


def _quat_angle_deg(q1, q2):
    d = abs(sum(a * b for a, b in zip(q1, q2)))
    return math.degrees(2.0 * math.acos(min(1.0, d)))


def classify_probe(samples, cut, tol_cm=0.01, tol_deg=0.01):
    """samples = [{"window", "animal", "scene_frame", "master_frame", "found", "mode", "anim_class",
    "bones": {name: {"t": [x,y,z], "q": [x,y,z,w]}}, "loc"}] -> per window/animal verdicts and per-animal answers
    for "do they move before the cut". A window counts only its samples BEFORE the cut (except windows at/after it).
    UNCLEAR when fewer than two usable samples, when the transport did not advance, or when an actor was missing."""
    win = {}
    for s in samples:
        win.setdefault((s["window"], s["animal"]), []).append(s)
    out, answers = {}, {}
    for (w, animal), rows in sorted(win.items()):
        pre = float(w) < cut
        use = [x for x in rows if (x.get("scene_frame") is not None and x["scene_frame"] < cut) or not pre]
        v = {"samples": len(rows), "used": len(use), "modes": sorted({str(x.get("mode")) for x in use}),
             "anim_classes": sorted({str(x.get("anim_class")) for x in use}), "pre_cut": pre}
        if any(not x.get("found") for x in rows):
            v.update(state="unclear", why="actor not found")
        elif len(use) < 2:
            v.update(state="unclear", why="fewer than 2 samples before the cut")
        elif len({x.get("master_frame") for x in use}) < len(use):
            v.update(state="unclear", why="transport did not advance between ticks (paused?)")
        else:
            moved, dmax, amax = False, 0.0, 0.0
            for a, b in zip(use, use[1:]):
                for bn in set(a.get("bones") or {}) & set(b.get("bones") or {}):
                    dt = math.dist(a["bones"][bn]["t"], b["bones"][bn]["t"])
                    da = _quat_angle_deg(a["bones"][bn]["q"], b["bones"][bn]["q"])
                    dmax, amax = max(dmax, dt), max(amax, da)
                    moved = moved or dt > tol_cm or da > tol_deg
            if not (use[0].get("bones")):
                v.update(state="unclear", why="no bone samples")
            else:
                v.update(state="moving" if moved else "static", max_cm=dmax, max_deg=amax)
        out["%s|%s" % (w, animal)] = v
        if pre:
            prev = answers.get(animal)
            st = v["state"].upper()
            answers[animal] = st if prev in (None, st) else ("MOVING" if "MOVING" in (prev, st) else "UNCLEAR")
    overall = sorted(set(answers.values()))
    return {"windows": out, "answers": answers,
            "answer": overall[0] if len(overall) == 1 else "MIXED:" + json.dumps(answers, sort_keys=True)}


def load_json(path):
    with open(path, "r", encoding="utf-8") as h:
        return json.load(h)


def write_json(path, data, exclusive=False):
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        h = os.fdopen(fd, "w", encoding="utf-8")
    else:
        h = open(path + ".tmp", "w", encoding="utf-8")
    with h:
        json.dump(data, h, indent=1, sort_keys=True, default=str)
        h.flush()
        os.fsync(h.fileno())
    if not exclusive:
        os.replace(path + ".tmp", path)


# =====================================================================================================================
# Live (Unreal). Every unreal handle is a local.
# =====================================================================================================================

class _Stopped(RuntimeError):
    pass


def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                            "CodexConductor", FOLDER)
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _file(path, ext):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ext


def _stop(run, reason):
    unreal.log_error("%s_FAILED|run=%s|%s" % (MARK, run, reason))
    raise _Stopped(reason)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _rate(fr):
    return float(fr.numerator) / float(fr.denominator)


def _gs(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)          # memory: never compare Guid structs with ==


def _enum_name(v):
    return str(getattr(v, "name", v)).split(".")[-1]


def _binding_rows(seq):                                       # prec klara_preroll_s4.py:282-295
    rows = []
    for b in seq.get_bindings():
        par = b.get_parent()
        pg = _gs(par.get_id()) if (par is not None and hasattr(par, "is_valid") and par.is_valid()) else None
        rows.append({"guid": _gs(b.get_id()), "name": str(b.get_display_name()), "parent": pg,
                     "tracks": [{"cls": t.get_class().get_name(), "name": str(t.get_display_name())}
                                for t in b.get_tracks()]})
    return rows


def _cut_section_count(seq):
    return sum(len(list(t.get_sections())) for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneCameraCutTrack))


def _root_rows(seq):
    return [{"cls": t.get_class().get_name(), "name": str(t.get_display_name())} for t in seq.get_tracks()
            if not (isinstance(t, unreal.MovieSceneCameraCutTrack) and not list(t.get_sections()))]


def _sec_ticks(s, tick_res, tpf):
    """(start, end) in ticks from frames AND seconds; refuses a boundary that is not on a display frame."""
    if not (s.has_start_frame() and s.has_end_frame()):
        return None, None, False
    out = []
    for f, sec in ((s.get_start_frame(), s.get_start_frame_seconds()), (s.get_end_frame(), s.get_end_frame_seconds())):
        t = int(round(float(sec) * tick_res))
        if abs(t - int(f) * tpf) > 1:
            raise PlanError("SECTION_OFF_FRAME: frame %s x %d vs %s s x %d" % (f, tpf, sec, tick_res))
        out.append(int(f) * tpf)
    return out[0], out[1], True


def _params(s):
    p = s.get_editor_property("params")                       # decl MovieSceneSkeletalAnimationSection.h:119-120
    anim = p.get_editor_property("animation")                 # decl :50-51
    try:
        rate = float(p.get_editor_property("play_rate").to_fixed_play_rate())   # decl MovieSceneTimeWarpExtensions.h:37-38
    except Exception:  # noqa: BLE001 - a non-constant time warp is unsupported -> refusal
        rate = None
    rev = None
    for nm in ("reverse", "b_reverse"):                       # memory: renamed bools
        try:
            rev = bool(p.get_editor_property(nm))
            break
        except Exception:  # noqa: BLE001
            continue
    fn = lambda nm: int(p.get_editor_property(nm).value)     # decl :54-63 (FFrameNumber, ticks)
    return {"anim": _path(anim), "len_s": float(anim.get_play_length()) if anim is not None else None,  # decl AnimationAsset.h:1060-1061
            "start_off": fn("start_frame_offset"), "end_off": fn("end_frame_offset"),
            "first_loop_off": fn("first_loop_start_frame_offset"), "rate": rate, "reverse": rev}


def _skel_rows(seq, animals):
    """{animal: [section rows]} from the top-level animal bindings' skeletal tracks; each row keeps a 'key' that
    survives the strip (binding|anim|start|end)."""
    tick_res = _rate(seq.get_tick_resolution())
    tpf = int(round(tick_res / _rate(seq.get_display_rate())))
    want = {v["binding"]: k for k, v in animals.items()}
    out = {k: [] for k in animals}
    for b in seq.get_bindings():
        par = b.get_parent()
        if par is not None and hasattr(par, "is_valid") and par.is_valid():
            continue
        animal = want.get(str(b.get_display_name()))
        if animal is None:
            continue
        for ti, t in enumerate(b.get_tracks()):
            if not isinstance(t, unreal.MovieSceneSkeletalAnimationTrack):
                continue
            for s in t.get_sections():
                st, en, bounded = _sec_ticks(s, tick_res, tpf)
                row = dict(_params(s), start=st, end=en, bounded=bounded, tick_res=tick_res, track=ti)
                row["key"] = "%s|%s|%s|%s" % (b.get_display_name(), row["anim"], st, en)
                out[animal].append(row)
    return out


def _find_skel_section(seq, key):
    hits = []
    tick_res = _rate(seq.get_tick_resolution())
    tpf = int(round(tick_res / _rate(seq.get_display_rate())))
    for b in seq.get_bindings():
        for t in b.get_tracks():
            if isinstance(t, unreal.MovieSceneSkeletalAnimationTrack):
                for s in t.get_sections():
                    st, en, _bd = _sec_ticks(s, tick_res, tpf)
                    if "%s|%s|%s|%s" % (b.get_display_name(), _params(s)["anim"], st, en) == key:
                        hits.append(s)
    return hits


def _subsections_playing(seq, path):
    return [s for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack) for s in t.get_sections()
            if s.get_sequence() is not None and _path(s.get_sequence()) == path]


def _our_track(seq, name):
    return [t for t in seq.get_tracks() if isinstance(t, unreal.MovieSceneSubTrack) and
            str(t.get_display_name()) == name]


def _offset(sec):
    return int(sec.get_editor_property("parameters").get_editor_property("start_frame_offset").value)


def _level_actors(world, pkg):                                 # prec klara_preroll_s4.py:307-312
    for lv in unreal.EditorLevelUtils.get_levels(world):
        if lv.get_outer() is not None and _path(lv.get_outer()) == pkg:
            acts = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
            return [a for a in acts if a.get_level() == lv]
    return []


def _transform_at_cut(copy, animals, cut_tick):
    """Value-before-first-key of each animal's Location channels on the transform sections live at the cut [inf:
    constant pre-extrapolation]; plain data."""
    tick_res = _rate(copy.get_tick_resolution())
    out = {}
    want = {v["binding"]: k for k, v in animals.items()}
    for b in copy.get_bindings():
        animal = want.get(str(b.get_display_name()))
        if animal is None:
            continue
        for t in b.get_tracks():
            if not isinstance(t, unreal.MovieScene3DTransformTrack):
                continue
            for s in t.get_sections():
                if s.has_start_frame() and int(round(float(s.get_start_frame_seconds()) * tick_res)) > cut_tick:
                    continue
                if s.has_end_frame() and int(round(float(s.get_end_frame_seconds()) * tick_res)) <= cut_tick:
                    continue
                for c in s.get_all_channels():
                    nm = str(c.channel_name) if hasattr(c, "channel_name") else str(c.get_name())
                    base = nm.rsplit("_", 1)[0] if nm.rsplit("_", 1)[-1].isdigit() else nm   # memory: Location.X_183
                    if not base.startswith("Location."):
                        continue
                    ks = sorted(c.get_keys(), key=lambda k: int(k.get_time().frame_number.value))
                    v = float(ks[0].get_value()) if ks else (float(c.get_default()) if c.has_default() else None)
                    out.setdefault(animal, {})[base] = v
    return out


def _api_table():
    rows = []

    def probe(api, tier, fn):
        try:
            res = fn()
            rows.append({"api": api, "tier": tier, "ok": bool(res) if not isinstance(res, list) else all(res),
                         "result": repr(res)[:160]})
        except Exception as exc:  # noqa: BLE001 - a probe failure is a finding
            rows.append({"api": api, "tier": tier, "ok": False, "result": "%s: %s" % (type(exc).__name__, exc)})

    u = unreal
    probe("EditorAssetLibrary.duplicate_asset/save_asset/does_asset_exist/find_package_referencers_for_asset",
          "decl EditorAssetLibrary.h:70,95,175,281; prec klara_hookin.py:1076 (duplicate ran live)",
          lambda: [hasattr(u.EditorAssetLibrary, n) for n in ("duplicate_asset", "save_asset", "does_asset_exist",
                                                               "find_package_referencers_for_asset")])
    probe("MovieSceneBindingExtensions.remove_track / remove", "decl MovieSceneBindingExtensions.h:136,144",
          lambda: [hasattr(u.MovieSceneBindingExtensions, n) for n in ("remove_track", "remove")])
    probe("MovieSceneSectionExtensions.set_start_frame / get_start_frame_seconds / get_parent_sequence_frame",
          "decl MovieSceneSectionExtensions.h:54,164,255",
          lambda: [hasattr(u.MovieSceneSectionExtensions, n) for n in ("set_start_frame", "get_start_frame_seconds",
                                                                       "get_parent_sequence_frame")])
    probe("MovieSceneSequenceExtensions.set_playback_start", "decl MovieSceneSequenceExtensions.h:210",
          lambda: hasattr(u.MovieSceneSequenceExtensions, "set_playback_start"))
    probe("MovieSceneTimeWarpExtensions.to_fixed_play_rate", "decl MovieSceneTimeWarpExtensions.h:37-38",
          lambda: hasattr(u.MovieSceneTimeWarpExtensions, "to_fixed_play_rate"))
    probe("AnimSequenceBase.get_play_length", "decl AnimationAsset.h:1060-1061",
          lambda: hasattr(u.AnimSequenceBase, "get_play_length"))
    probe("MovieSceneSubSection.set_sequence / MovieSceneSection.set_completion_mode",
          "decl MovieSceneSubSection.h:159-162; MovieSceneSection.h:432-433",
          lambda: [hasattr(u.MovieSceneSubSection, "set_sequence"), hasattr(u.MovieSceneSection, "set_completion_mode")])
    return rows


def _gather(args, world, run):
    here = _here()
    seq = unreal.load_asset(args["scene_sequence"])
    copy = unreal.load_asset(args["copy"])
    if seq is None or copy is None:
        raise PlanError("ASSETS: scene %s copy %s" % (seq is not None, copy is not None))
    refusals, warnings = [], []
    rp = os.path.normpath(os.path.join(here, args["reveal_record"]))
    rec = load_json(rp) if os.path.exists(rp) else None
    if not rec or not rec.get("applied"):
        raise PlanError("REVEAL_NOT_APPLIED: %s" % rp)
    rslot = (rec.get("plan") or {}).get("slot") or {}
    fs = ((rec.get("plan") or {}).get("strike_schedule") or {}).get("frames") or []
    if not fs:
        raise PlanError("NO_STRIKE_SCHEDULE in %s" % rp)
    first_strike = int(fs[0])
    slots = _subsections_playing(seq, args["copy"])
    if len(slots) != 1:
        raise PlanError("MAIN_SLOT_COUNT: %d sections play %s" % (len(slots), args["copy"]))
    slot = {"range": [int(slots[0].get_start_frame()), int(slots[0].get_end_frame())], "offset_ticks": _offset(slots[0])}
    if slot["range"] != list(rslot.get("range") or []) or slot["offset_ticks"] != rslot.get("start_offset_ticks"):
        refusals.append("SLOT_DRIFT: live %s vs reveal record %s/%s" % (slot, rslot.get("range"),
                                                                       rslot.get("start_offset_ticks")))
    her_tick_res = _rate(copy.get_tick_resolution())
    m = preroll_mapping(args["preroll_range"], slot, int(copy.get_playback_start()), her_tick_res,
                        _rate(copy.get_display_rate()), _rate(seq.get_display_rate()))
    refusals += m["refusals"]
    if rslot.get("her_frame_at_cut") is not None and m["cut_her_frame"] != float(rslot["her_frame_at_cut"]):
        refusals.append("CUT_HER_FRAME_DRIFT: live %.3f vs record %s" % (m["cut_her_frame"], rslot["her_frame_at_cut"]))
    if int(args["preroll_range"][0]) > first_strike:
        refusals.append("PREROLL_AFTER_FIRST_STRIKE: %d > %d" % (int(args["preroll_range"][0]), first_strike))
    secs = _skel_rows(copy, args["animals"])
    plan = plan_loop_shifts(secs, m, int(args.get("extra_loops", 0)), args.get("expected_loops"))
    refusals += plan["refusals"]
    refusals += check_alignment(plan["rows"], m)
    rows = _binding_rows(copy)
    strip = classify_strip(rows, [v["binding"] for v in args["animals"].values()], _root_rows(copy))
    refusals += strip["refusals"]
    labels = set()
    level_loc = {}
    for a in _level_actors(world, args["her_level"]):
        labels.update([str(a.get_actor_label()), str(a.get_name())])
        loc = a.get_actor_location()
        level_loc[str(a.get_actor_label())] = [float(loc.x), float(loc.y), float(loc.z)]
    for k, v in sorted(args["animals"].items()):
        if v["binding"] not in labels:
            refusals.append("ANIMAL_NOT_IN_HER_LEVEL: %s %r (bindings must resolve in the show level)" % (k, v["binding"]))
    tr = _transform_at_cut(copy, args["animals"], m["cut_her_tick"])
    pops = {}
    for k, v in sorted(args["animals"].items()):
        lv, kv = level_loc.get(v["binding"]), tr.get(k) or {}
        vec = [kv.get("Location.X"), kv.get("Location.Y"), kv.get("Location.Z")]
        if lv is None or None in vec:
            warnings.append("TRANSFORM_AT_CUT_UNKNOWN: %s level %s keys %s" % (k, lv, vec))
            continue
        pops[k] = math.dist(lv, vec)
        if pops[k] > float(args.get("transform_pop_tol_cm", 1.0)):
            msg = ("TRANSFORM_POP_AT_CUT: %s level %s vs copy transform %s (%.1f cm) [inf]: the duplicate carries no "
                   "Transform track, so the animal eats at its level placement until 594" % (k, lv, vec, pops[k]))
            (warnings if args.get("accept_transform_pop") else refusals).append(msg)
    facts = {"slot": slot, "mapping": m, "first_strike": first_strike, "plan": plan["rows"], "strip": strip,
             "copy_fingerprint": skel_fingerprint(secs), "skel_sections": secs, "transform_pop_cm": pops,
             "dup_exists": bool(unreal.EditorAssetLibrary.does_asset_exist(args["dup_path"])),
             "our_tracks": len(_our_track(seq, args["track_name"])),
             "scene_tracks": [str(t.get_display_name()) for t in seq.get_tracks()]}
    return facts, refusals, warnings, seq, copy


def run_dry(args, run, world):
    facts, refusals, warnings, seq, _copy = _gather(args, world, run)
    rp = os.path.join(_here(), RECORD_NAME)
    applied = os.path.exists(rp) and bool(load_json(rp).get("applied"))
    if applied:
        rec = load_json(rp)
        dup = unreal.load_asset(args["dup_path"])
        fp = skel_fingerprint(_skel_rows(dup, args["animals"])) if dup is not None else None
        if facts["copy_fingerprint"] != rec.get("copy_fingerprint") or fp != rec.get("dup_fingerprint"):
            refusals.append("PREROLL_STALE: copy/duplicate skeletal sections changed since APPLY (keys are absolute; "
                            "a reveal REVERT/re-APPLY moves the copy, not the duplicate) -> REVERT this, then re-APPLY")
        ours = _our_track(seq, args["track_name"])
        now = {"ours": [{"sections": [{"range": [int(s.get_start_frame()), int(s.get_end_frame())],
                                       "sequence": _path(s.get_sequence()), "offset": _offset(s)}
                                      for s in t.get_sections()]} for t in ours],
               "others": [n for n in facts["scene_tracks"] if n != args["track_name"]]}
        refusals += revert_check(rec, now, args)
        warnings.append("ALREADY_APPLIED: %s" % rp)
    else:
        if facts["dup_exists"]:
            refusals.append("DUP_EXISTS: %s (REVERT leaves it on disk: set a new dup_path, or delete it by hand after "
                            "checking referencers)" % args["dup_path"])
        if facts["our_tracks"]:
            refusals.append("TRACK_EXISTS: %r in %s" % (args["track_name"], args["scene_sequence"]))
    api = _api_table()
    refusals += ["API_MISSING: %s" % r["api"] for r in api if not r["ok"]]
    report = {"tool": TOOL, "run": run, "args": args, "api_table": api, "facts": facts, "refusals": refusals,
              "warnings": warnings, "apply_ready": not refusals and not applied, "census": _census()}
    out = os.path.join(_here(), DRY_NAME)
    write_json(out, report)
    for r in api:
        unreal.log("%s_API|run=%s|ok=%d|%s|%s|%s" % (MARK, run, int(r["ok"]), r["api"], r["tier"], r["result"]))
    unreal.log("%s_MAPPING|run=%s|%s" % (MARK, run, json.dumps(facts["mapping"], sort_keys=True)))
    for row in facts["plan"]:
        unreal.log("%s_PLAN_ROW|run=%s|%s" % (MARK, run, json.dumps(row, sort_keys=True)))
    for r in facts["strip"]["remove"]:
        unreal.log("%s_REMOVE_BINDING|run=%s|%s" % (MARK, run, r["name"]))
    for r in facts["strip"]["strip_tracks"]:
        unreal.log("%s_REMOVE_TRACK|run=%s|%s|%s" % (MARK, run, r["binding"], r["cls"]))
    for t in refusals:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, t))
    for t in warnings:
        unreal.log("%s_WARNING|run=%s|%s" % (MARK, run, t))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|report=%s"
               % (MARK, run, int(report["apply_ready"]), len(refusals), len(warnings), out))


def _strip(dup, strip, args, run):
    for t in list(dup.get_tracks()):
        dup.remove_track(t)                        # decl MovieSceneSequenceExtensions.h:89; return ignored: read back
    for t in list(dup.get_tracks()):               # the camera cut track may survive remove_track [inf] (prec S4)
        if isinstance(t, unreal.MovieSceneCameraCutTrack):
            for s in list(t.get_sections()):
                t.remove_section(s)
    for r in strip["remove"]:                      # children first
        for b in dup.get_bindings():
            if _gs(b.get_id()) == r["guid"]:
                b.remove()                         # decl MovieSceneBindingExtensions.h:144 [prec klara_hookin.py:1282]
    for b in dup.get_bindings():
        for t in list(b.get_tracks()):
            if t.get_class().get_name() not in KEEP_TRACK_CLASSES:
                b.remove_track(t)                  # decl MovieSceneBindingExtensions.h:136; read back below
    bad = verify_strip(_binding_rows(dup), _root_rows(dup), _cut_section_count(dup),
                       [v["binding"] for v in args["animals"].values()])
    if bad:
        _stop(run, "STRIP_READBACK|%s|NOTHING SAVED; Don't-Save restart" % " || ".join(bad))


def _guarded_save(path, args, run):
    g = write_guard(path, args)
    if g:
        _stop(run, "WRITE_GUARD|%s" % " || ".join(g))
    if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
        _stop(run, "SAVE_FAILED|%s" % path)


def run_apply(args, run, world):
    facts, refusals, _w, seq, copy = _gather(args, world, run)
    if facts["dup_exists"]:
        refusals.append("DUP_EXISTS: %s" % args["dup_path"])
    if facts["our_tracks"]:
        refusals.append("TRACK_EXISTS: %r" % args["track_name"])
    if refusals:
        _stop(run, "PLAN_REFUSED|" + " || ".join(refusals))
    g = write_guard(args["dup_path"], args) + write_guard(args["scene_sequence"], args)
    if g:
        _stop(run, "WRITE_GUARD|%s" % " || ".join(g))
    m = facts["mapping"]
    rpath = os.path.join(_here(), RECORD_NAME)
    folder = os.path.join(_project(), "Backups", "PreKlaraPrerollS1-%s" % run)
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for src in (_file(args["scene_sequence"], ".uasset"), _file(args["copy"], ".uasset")):
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        hs = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if hs[0] != hs[1]:
            _stop(run, "BACKUP_HASH|%s" % src)
        manifest.append({"source": src, "sha256": hs[1]})
    rec = {"schema": 1, "tool": TOOL, "run": run, "applied": False, "backup": folder, "manifest": manifest,
           "decided_by": args.get("decided_by"), "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "args": args, "mapping": m, "plan": facts["plan"], "strip": facts["strip"], "slot": facts["slot"],
           "copy_fingerprint": facts["copy_fingerprint"], "before": {"scene_tracks": facts["scene_tracks"]}}
    write_json(rpath, rec, exclusive=True)                      # record-first: before any mutation
    dup = unreal.EditorAssetLibrary.duplicate_asset(args["copy"], args["dup_path"])    # decl EditorAssetLibrary.h:175
    if dup is None or not unreal.EditorAssetLibrary.does_asset_exist(args["dup_path"]):
        _stop(run, "DUPLICATE_FAILED|%s|NOTHING SAVED; Don't-Save restart" % args["dup_path"])
    rec["dup_created"] = True
    write_json(rpath, rec)
    _strip(dup, facts["strip"], args, run)
    # loop alignment: extend each active section earlier by whole loops (end kept); then the playback start
    tpf = m["her_tpf"]
    live_new = {}
    for row in facts["plan"]:
        hits = _find_skel_section(dup, row["key"])
        if len(hits) != 1:
            _stop(run, "SECTION_NOT_FOUND_IN_DUP|%s x%d|NOTHING SAVED; Don't-Save restart" % (row["key"], len(hits)))
        s = hits[0]
        before = _params(s)
        s.set_start_frame(int(row["new_range"][0] // tpf))      # decl MovieSceneSectionExtensions.h:164 (display frames)
        st, en, _bd = _sec_ticks(s, _rate(dup.get_tick_resolution()), tpf)
        if [st, en] != list(row["new_range"]) or _params(s) != before:
            _stop(run, "EXTEND_READBACK|%s got %s want %s params %s|NOTHING SAVED; Don't-Save restart"
                  % (row["animal"], [st, en], row["new_range"], _params(s) != before))
        live_new[row["animal"]] = st
    dup.set_playback_start(int(m["dup_playback_start_frame"]))   # decl MovieSceneSequenceExtensions.h:210
    if int(dup.get_playback_start()) != int(m["dup_playback_start_frame"]):
        _stop(run, "PLAYBACK_START_READBACK|%s|NOTHING SAVED; Don't-Save restart" % dup.get_playback_start())
    m_live = dict(m, dup_playback_start_frame=int(dup.get_playback_start()))
    bad = check_alignment(facts["plan"], m_live, live_new)
    re_plan = plan_loop_shifts(_skel_rows(dup, args["animals"]), m_live)     # re-derive from the LIVE duplicate
    if re_plan["refusals"] or any(r["loops"] != 0 for r in re_plan["rows"]):
        bad.append("DUP_REPLAN: %s %s" % (re_plan["refusals"], [(r["animal"], r["loops"]) for r in re_plan["rows"]]))
    if bad:
        _stop(run, "ALIGNMENT_READBACK|%s|NOTHING SAVED; Don't-Save restart" % " || ".join(bad))
    rec["dup_fingerprint"] = skel_fingerprint(_skel_rows(dup, args["animals"]))
    # the sub track + section [P0, C)
    trk = seq.add_track(unreal.MovieSceneSubTrack)
    trk.set_display_name(args["track_name"])
    sec = trk.add_section()
    sec.set_sequence(dup)                                                 # decl MovieSceneSubSection.h:159-162
    sec.set_range(int(m["range"][0]), int(m["range"][1]))                # decl MovieSceneSectionExtensions.h:145
    prm = sec.get_editor_property("parameters")                           # struct copy: set back [prec hookin:1065]
    prm.set_editor_property("start_frame_offset", unreal.FrameNumber(int(m["offset_ticks"])))
    sec.set_editor_property("parameters", prm)
    sec.set_completion_mode(getattr(unreal.MovieSceneCompletionMode, args.get("completion", "RESTORE_STATE")))
    got = [int(sec.get_start_frame()), int(sec.get_end_frame())]
    off = _offset(sec)
    PSF = unreal.MovieSceneSectionExtensions.get_parent_sequence_frame    # decl :255 [prec klara_reveal live]
    cut_hf = int(round(m["cut_her_frame"]))
    probe_hf = cut_hf - 6                                                 # 6 her frames = 5 Scene frames at 30/25
    mapped = [int(PSF(sec, cut_hf, seq)), int(PSF(sec, probe_hf, seq))]
    main = _subsections_playing(seq, args["copy"])
    main_mapped = int(PSF(main[0], cut_hf, seq)) if len(main) == 1 else None
    want_mapped = [m["cut"], m["cut"] - 5]
    if got != list(m["range"]) or got[1] > m["cut"] or off != int(m["offset_ticks"]) or mapped != want_mapped or \
            main_mapped != m["cut"] or _path(sec.get_sequence()) != args["dup_path"]:
        _stop(run, "SECTION_READBACK|range %s want %s|offset %d want %d|her %d,%d -> %s want %s|main -> %s|NOTHING "
                   "SAVED; Don't-Save restart" % (got, m["range"], off, m["offset_ticks"], cut_hf, probe_hf, mapped,
                                                  want_mapped, main_mapped))
    if len(main) != 1 or [int(main[0].get_start_frame()), int(main[0].get_end_frame())] != facts["slot"]["range"] or \
            _offset(main[0]) != facts["slot"]["offset_ticks"]:
        _stop(run, "MAIN_SLOT_CHANGED|NOTHING SAVED; Don't-Save restart")
    gate = census_gate(_census(), [args["scene_sequence"], args["dup_path"]])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart (backup %s; her maps are never saved here)"
              % (" || ".join(gate), folder))
    for p in (args["scene_sequence"], args["dup_path"]):
        _guarded_save(p, args, run)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_SAVE|%s" % json.dumps(_census()))
    seq2 = unreal.load_asset(args["scene_sequence"])
    t2 = _our_track(seq2, args["track_name"])
    s2 = [s for t in t2 for s in t.get_sections()]
    if len(t2) != 1 or len(s2) != 1 or [int(s2[0].get_start_frame()), int(s2[0].get_end_frame())] != list(m["range"]) \
            or _offset(s2[0]) != int(m["offset_ticks"]):
        _stop(run, "POST_SAVE_READBACK|%d tracks %d sections (SAVED: scene + dup; REVERT or restore %s)"
              % (len(t2), len(s2), folder))
    rec.update(applied=True, section={"range": got, "offset_ticks": off, "mapped": mapped,
                                      "completion": args.get("completion", "RESTORE_STATE")}, live_new_starts=live_new)
    write_json(rpath, rec)
    unreal.log("%s_APPLY_OK|run=%s|range=%s|offset=%d|dup=%s|loops=%s|backup=%s|record=%s|next=SavedMasterMatchesShow"
               " + SceneCutBindingsResolve (singly) + PIE PROBE again + stills 560-640"
               % (MARK, run, got, off, args["dup_path"], {r["animal"]: r["loops"] for r in facts["plan"]}, folder,
                  rpath))


def run_revert(args, run, world):
    rpath = os.path.join(_here(), RECORD_NAME)
    rec = load_json(rpath)
    seq = unreal.load_asset(args["scene_sequence"])
    ours = _our_track(seq, args["track_name"])
    now = {"ours": [{"sections": [{"range": [int(s.get_start_frame()), int(s.get_end_frame())],
                                   "sequence": _path(s.get_sequence()), "offset": _offset(s)}
                                  for s in t.get_sections()]} for t in ours],
           "others": [str(t.get_display_name()) for t in seq.get_tracks() if str(t.get_display_name()) !=
                      args["track_name"]]}
    bad = revert_check(rec, now, args)
    if bad:
        _stop(run, "%s|nothing changed (restore from %s)" % (" || ".join(bad), rec.get("backup")))
    g = write_guard(args["scene_sequence"], args)
    if g:
        _stop(run, "WRITE_GUARD|%s" % " || ".join(g))
    folder = os.path.join(_project(), "Backups", "PreKlaraPrerollS1Revert-%s" % run)
    os.makedirs(folder, exist_ok=False)
    for src in (_file(args["scene_sequence"], ".uasset"), _file(args["dup_path"], ".uasset")):
        if os.path.exists(src):
            shutil.copy2(src, folder)
    seq.remove_track(ours[0])                      # return value ignored: read back
    if _our_track(seq, args["track_name"]):
        _stop(run, "REMOVE_TRACK_READBACK|NOTHING SAVED; Don't-Save restart")
    names = [str(t.get_display_name()) for t in seq.get_tracks()]
    if names != rec["before"]["scene_tracks"]:
        _stop(run, "SCENE_TRACKS_READBACK|%s vs %s|NOTHING SAVED; Don't-Save restart" % (names,
                                                                                        rec["before"]["scene_tracks"]))
    gate = census_gate(_census(), [args["scene_sequence"]])
    if gate:
        _stop(run, "CENSUS|%s|NOTHING SAVED; Don't-Save restart" % " || ".join(gate))
    _guarded_save(args["scene_sequence"], args, run)
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_AFTER_REVERT|%s" % json.dumps(_census()))
    refs = [str(x) for x in unreal.EditorAssetLibrary.find_package_referencers_for_asset(args["dup_path"], False)]
    if refs:
        _stop(run, "DUP_STILL_REFERENCED|%s|LS_DevScene_01 SAVED without the track; duplicate kept" % refs)
    on_disk = bool(unreal.EditorAssetLibrary.does_asset_exist(args["dup_path"]))
    os.rename(rpath, rpath + ".reverted-" + run)
    unreal.log("%s_REVERT_OK|run=%s|removed_track=%s|dup_left_on_disk=%s|exists=%d|referencers=0|backup=%s|note=the "
               "duplicate is NOT deleted; a re-APPLY needs a new dup_path or a manual delete"
               % (MARK, run, args["track_name"], args["dup_path"], int(on_disk), folder))


# ---- PROBE (PIE, read only) ------------------------------------------------------------------------------------------

def _pick_bones(names):
    low = [(n, n.lower()) for n in names]
    pick = []
    for want in (("head",), ("pelvis", "hip", "spine")):
        hit = [n for n, l in low if any(w in l for w in want)]
        if hit:
            pick.append(hit[0])
    if names:
        pick.append(names[len(names) // 2])
    out = []
    for n in pick:
        if n not in out:
            out.append(n)
    return out[:3]


def run_probe(args, run):
    """PIE, READ ONLY. Arms a post-tick callback; returns at once (the callback logs the result later)."""
    pa = dict({"scene_label": "Scene 1", "frames": [300, 593, 600], "burst": 3, "timeout_s": 900.0,
               "tol_cm": 0.01, "tol_deg": 0.01}, **(args.get("probe") or {}))
    cut = int(args["preroll_range"][1])
    frames = sorted(float(f) for f in pa["frames"])
    level_short = args["her_level"].rsplit("/", 1)[-1]
    animals = {k: dict(v) for k, v in args["animals"].items()}
    st = {"handle": None, "samples": [], "pending": list(frames), "burst": 0, "window": None, "t0": time.time(),
          "bones": {}, "out": os.path.join(_here(), "klara_preroll_s1_probe_%s.json" % run), "done": False}

    def finish(status):
        if st["done"]:
            return
        st["done"] = True
        try:
            unreal.unregister_slate_post_tick_callback(st["handle"])
        except Exception:  # noqa: BLE001
            pass
        verdict = classify_probe(st["samples"], cut, float(pa["tol_cm"]), float(pa["tol_deg"]))
        write_json(st["out"], {"tool": TOOL, "run": run, "status": status, "samples": st["samples"], "verdict": verdict,
                               "probe_args": pa, "cut": cut})
        if status == "complete":
            unreal.log("%s_PROBE_OK|run=%s|answer=%s|answers=%s|file=%s" % (MARK, run, verdict["answer"],
                                                                          json.dumps(verdict["answers"]), st["out"]))
        else:
            unreal.log_error("%s_FAILED|run=%s|PROBE_%s|file=%s" % (MARK, run, status.upper(), st["out"]))

    def scene_frame(world):
        # prec klara_pendulum_s4.py:326-339 [meas: its probe file KLARAPENDULUM-20261007-134048 'complete']
        roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
        if len(roots) != 1:
            return None, None, "SHOW_ROOTS_%d" % len(roots)
        tr = roots[0].transport
        lab = pa["scene_label"]
        segs = [g for g in list(tr.segments) if g.type == unreal.InfinityCueType.SCENE
                and (str(g.label) == lab or str(g.label).startswith(lab + " "))]
        if len(segs) != 1:
            return None, None, "SCENE_SEGMENTS_%d" % len(segs)
        mf = float(tr.get_current_master_frame().value)
        return (mf - float(segs[0].start_frame.value)) / 24000.0 * 25.0, mf, None

    def sample(world, sf, mf):
        acts = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.SkeletalMeshActor))
        for animal, v in sorted(animals.items()):
            hits = [a for a in acts if str(a.get_name()) == v["actor_name"] and
                    level_short in str(a.get_level().get_outer().get_name())]
            row = {"window": st["window"], "animal": animal, "scene_frame": sf, "master_frame": mf,
                   "found": len(hits) == 1, "hits": len(hits)}
            if len(hits) == 1:
                a = hits[0]
                comp = a.get_component_by_class(unreal.SkeletalMeshComponent)
                mesh = comp.get_skinned_asset()                                  # decl SkinnedMeshComponent.h:1222-1223
                inst = comp.get_anim_instance()                                  # decl SkeletalMeshComponent.h:1110-1111
                loc = a.get_actor_location()
                if animal not in st["bones"]:
                    names = [str(comp.get_bone_name(i)) for i in range(int(comp.get_num_bones()))]  # decl SkinnedMeshComponent.h:1143-1165
                    st["bones"][animal] = _pick_bones(names)
                bones = {}
                for bn in st["bones"][animal]:
                    t = comp.get_socket_transform(bn, unreal.RelativeTransformSpace.RTS_COMPONENT)  # decl SceneComponent.h:42-49,800-801
                    q = t.rotation
                    bones[bn] = {"t": [float(t.translation.x), float(t.translation.y), float(t.translation.z)],
                                 "q": [float(q.x), float(q.y), float(q.z), float(q.w)]}
                row.update(mode=_enum_name(comp.get_animation_mode()),           # decl SkeletalMeshComponent.h:1248-1249
                           anim_class=inst.get_class().get_name() if inst is not None else None,
                           mesh=_path(mesh), mesh_ok=bool(mesh is not None and _path(mesh).endswith(v.get("mesh", ""))),
                           loc=[float(loc.x), float(loc.y), float(loc.z)], bones=bones)
                a = comp = mesh = inst = None
            st["samples"].append(row)
            unreal.log("%s_PROBE_SAMPLE|run=%s|%s" % (MARK, run, json.dumps(row, default=str)))

    def tick(_dt):
        try:
            world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if world is None:
                return finish("pie_ended")
            if time.time() - st["t0"] > float(pa["timeout_s"]):
                return finish("timeout")
            sf, mf, err = scene_frame(world)
            if sf is None:
                return finish("no_time_" + err)
            if st["burst"] == 0:
                if not st["pending"] or sf < st["pending"][0]:
                    return None
                st["window"] = st["pending"].pop(0)
                st["burst"] = int(pa["burst"])
            sample(world, sf, mf)
            world = None
            st["burst"] -= 1
            if st["burst"] == 0 and not st["pending"]:
                finish("complete")
        except Exception as exc:  # noqa: BLE001 - a probe never raises into Slate; it stops itself
            unreal.log_error("%s_PROBE_ERROR|run=%s|%s: %s" % (MARK, run, type(exc).__name__, exc))
            finish("error")
        return None

    st["handle"] = unreal.register_slate_post_tick_callback(tick)    # prec klara_pendulum_s4.py:381 [meas]
    unreal.log("%s_PROBE_ARMED|run=%s|frames=%s|burst=%s|file=%s|read-only: no save, no transport command; play S1 "
               "through frame %s" % (MARK, run, frames, pa["burst"], st["out"], int(frames[-1]) + 1))


# ---- entry -----------------------------------------------------------------------------------------------------------

def main():
    args = globals().get("KLARAPREROLLS1_ARGS")
    if args is None:
        args = load_json(os.path.join(_here(), ARGS_NAME))
    run = str(args.get("run_id") or datetime.datetime.now().strftime("KLARAPREROLLS1-%Y%m%d-%H%M%S"))
    try:
        mode = str(args.get("mode") or "").upper()
        bad = validate_args(args)
        if bad:
            _stop(run, "ARGS|" + " || ".join(bad))
        ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        pie = ed.get_game_world() is not None
        if mode == "PROBE":
            early = live_gates({"mode": mode, "pie": pie})
            if early:
                _stop(run, "REFUSED|" + " || ".join(early))
            return run_probe(args, run)
        world = None if pie else ed.get_editor_world()
        wname = str(world.get_outermost().get_name()) if world is not None else None
        cur = None if pie else unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()  # decl LevelSequenceEditorBlueprintLibrary.h:42
        rpath = os.path.join(_here(), RECORD_NAME)
        state = {"mode": mode, "confirm": args.get("confirm"), "pie": pie,
                 "wrong_world": None if (pie or wname == EXPECTED_WORLD) else str(wname),
                 "sequencer_open": _path(cur) if cur is not None else None, "census": _census(),
                 "decided_by": args.get("decided_by"), "record_exists": rpath if os.path.exists(rpath) else None,
                 "record_applied": os.path.exists(rpath) and bool(load_json(rpath).get("applied"))}
        cur = None
        early = live_gates(state)
        if early:
            _stop(run, "REFUSED|" + " || ".join(early))
        try:
            {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}[mode](args, run, world)
        except PlanError as exc:
            _stop(run, "PLAN|" + str(exc))
    except _Stopped:
        raise
    except Exception as exc:  # noqa: BLE001 - every exit leaves a FAILED marker
        unreal.log_error("%s_FAILED|run=%s|EXCEPTION|%s: %s" % (MARK, run, type(exc).__name__, exc))
        raise


if unreal is not None and not getattr(unreal, "_PUSS_FAKE", False):
    main()
