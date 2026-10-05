"""OPENING OWN RAIL: give the Opening cue its OWN music rail playing Cameron's "Opening sketch 2", and hand rail
2E86171B... back to Passage 1 so walking_music_swap can put the new walking track on P01 (no RAIL_SHARED refusal).
Offline-written 5 Oct, NEVER RUN IN UNREAL. Harness: test_opening_own_rail.py (system Python, no Unreal).

Tiers per claim: [decl] declaration-proven (plugin header/source, cited file:line), [prec] in-repo precedent call
(cited; run status stated), [meas] an earlier run's read-back (cited), [inf] inferred (why stated).

HOW THE OPENING REFERENCES MUSIC TODAY
  * The Opening is a Show cue (Type SEQUENCE, label "Opening — Curtain", CueGuid 5674D113...) [meas
    opening_readback_OPRB-20261005-143737.json show.opening_cue_guid]. Its music is the cue's Scene.Music, an
    FInfinitySectionMusicBinding {Mode, PrimaryRailGuid, SecondaryRailGuid, RailOffsetFrames} [decl
    InfinityStageTypes.h:817 (FInfinitySceneCueData::Music), :767-783 (binding), FInfinityShowCue::Scene :928].
  * Today it is Mode START, PrimaryRailGuid 2E86171B614D036D59FEDCB9C6C5788A, offset 0; P01's binding is SILENCE on
    the same rail [meas readback show.opening_music / show.p01_music]. Rail 2E86 is "Passage 1 Music", Sound
    /Game/InfinityStage/Audio/Passages/SW_P01_IntroWalking [meas readback show.rails].
  * That state was written by opening_sequence_apply's first-time-only music move (Opening := P01's binding, P01 :=
    SILENCE on the same rail) [prec opening_sequence_apply.py:761-768, writer :611-631; meas
    opening_sequence_report_apply.json]. Before it: Opening SILENCE rail 0, P01 START 2E86 offset 0 [meas
    opening_sequence_record.json original.music].
  * RebuildManagedMaster places one Infinity audio section per enabled non-WingPair cue whose Scene.Music is
    START/ExplicitCrossfade, BlockGuid = CueGuid, rail found by PrimaryRailGuid in Show.MusicRails, over the cue's
    whole segment, offset SourceIn + RailOffset, non-repeating, fades from ApplyVolumeEnvelope [decl
    InfinityStageSequenceBuilderLibrary.cpp:545-595, FindRail :62-68, envelope :78-96]. Passages the same, keyed by
    PassageGuid [decl :503-544]. Measured: the Master's Opening music section plays SW_P01_IntroWalking 0-96.36 s and
    P01 has no music section [meas readback master.opening_music_section / p01_music_section].

WHAT APPLY WRITES (Show only; the Master by RebuildManagedMaster)
  * NEW SoundWave /Game/InfinityStage/Audio/Opening/SW_Opening_Tuning_Sketch2 (refused if it exists). Import pattern
    walking_music_swap.py:861-885 [meas: WALKING_MUSIC_APPLY_OK|run=WALK-20261005-143843 in Saved/Logs] - but that
    run imported 16-bit PCM copies; this input is 24-bit WAVE_FORMAT_EXTENSIBLE, whose import is UNVERIFIED [inf].
    The import gate (SoundWave, duration within 0.02 s, not looping) runs before any Show write; a failed import
    saves nothing. Fallback: a 16-bit PCM copy = change args wav + sha256 + duration_s only.
  * MusicRails APPEND (never a Passage index: rails 0-5 are addressed by index as Passages 1-6 [decl
    InfinityStageMusicAnalysisImporter.cpp:142-146, 267; SInfinityStageCueDesk.cpp:6238-6239]): Label "Opening
    (Cameron sketch 2)", Sound = the new wave, SourceIn 0, SourceOut = wave duration in Show ticks, Fade In/Out
    COPIED from rail 2E86, AnalysisMap None. RailGuid is VisibleAnywhere/BlueprintReadOnly [decl
    InfinityStageTypes.h:738-739] -> minted by show.ensure_stable_ids() (BlueprintCallable [decl
    InfinityStageShowAsset.h:68-69]; mints ONLY invalid Show/Cue/Occurrence/Passage/Rail GUIDs [decl
    InfinityStageShowAsset.cpp:91-124]) [prec Saved/CodexFlatV3/p06/p6_workflow.py:728, live run status unverified].
    Gate: the ONLY identity that changes is one new, unique, valid rail GUID at the end of the array.
  * Opening cue Scene.Music := START, PrimaryRailGuid = new rail, offset args.opening_offset_frames (0); secondary
    untouched [prec writer opening_sequence_apply.py:601-631, measured to work 4 Oct].
  * P01 Music := the 4 Oct ORIGINAL (START, rail 2E86, offset 0) read from opening_sequence_record.json
    original.music.p01 [meas]; refused unless that equals START on the shared rail.
  * The mint has to come BEFORE the re-point (the binding needs the GUID); the task's step 8 is therefore step 5b.
  * Record (exclusive, fsync) is written BEFORE the import, not after it: a stop after the import must leave a trace
    [prec walking_music_swap.py:962].
  * After APPLY, P01 plays rail 2E86's CURRENT sound (SW_P01_IntroWalking, the pre-4-Oct P01 song) until
    walking_music_swap runs for P01. P01 is then START, so walking_music_swap needs no silence_policy "set_start".

Modes (opening_own_rail_run.py <- opening_own_rail_args.json, confirm "<MODE> OPENINGRAIL"):
  DRY    read-only + an in-memory struct probe (no package touched); opening_own_rail_dry.json;
         OPENING_OWN_RAIL_DRY_OK|run=..
  APPLY  guards -> backup Show+Master -> exclusive record -> import wave -> append rail -> ensure_stable_ids ->
         re-point Opening, restore P01 -> read back -> RebuildManagedMaster -> every compiled segment tick-identical,
         Master sections unmoved, Master music: Opening = new wave, P01 = rail 2E86's sound, all others unchanged ->
         census = exactly {Show, Master, wave} -> save those three -> post-save read-back -> census clean ->
         OPENING_OWN_RAIL_APPLY_OK|run=..
  REVERT drift gate (state == what APPLY wrote, incl. rail 2E86 untouched: revert walking_music_swap P01 FIRST) ->
         backup -> bindings back -> remove the appended rail -> exact read-back (rails, bindings, every GUID) ->
         rebuild -> same gates -> save Show+Master -> OPENING_OWN_RAIL_REVERT_OK|run=.. (wave kept unless
         delete_asset_on_revert, referencer-checked)
  Failure: OPENING_OWN_RAIL_STOPPED|run=..|reason=..
Never: Save All, level save, reload, open/scrub Sequencer, refit, end PIE. No unreal objects in module globals.
Helpers shared with walking_music_swap.py are loaded from its source with the trailing main() call stripped (the
same technique as opening_sequence_apply.py:122-128), so both tools judge segments/sync the same way.
"""
import datetime
import hashlib
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "opening_own_rail"
MARK = "OPENING_OWN_RAIL"
CONFIRM_WORD = "OPENINGRAIL"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ASSET_PATH = "/Game/InfinityStage/Audio/Opening/SW_Opening_Tuning_Sketch2"
ARGS_NAME = "opening_own_rail_args.json"
DRY_NAME = "opening_own_rail_dry.json"
RECORD_NAME = "opening_own_rail_record.json"
ZERO_GUID = "0" * 32
PASSAGE_RAIL_SLOTS = 6          # rails 0-5 are Passages 1-6 by index (see docstring)
DURATION_TOL_S = 0.02           # imported SoundWave vs WAV header
HEADER_TOL_S = 0.002            # WAV header vs args
NEW_RAIL_FIELDS = ("label", "sound", "source_in", "source_out", "fade_in", "fade_out", "analysis_map", "fingerprint")


class PlanError(Exception):
    pass


def _load_walking_helpers():
    """walking_music_swap.py's functions, without running its main() (pure in the harness, live in Unreal)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else _saved_here(),
                        "walking_music_swap.py")
    with open(path, "r", encoding="utf-8") as handle:
        src = handle.read()
    tail = "if unreal is not None:\n    main()"
    if not src.rstrip().endswith(tail):
        raise PlanError("WALKING_HELPERS_TAIL_CHANGED: walking_music_swap.py no longer ends with its main() guard")
    ns = {"__name__": "walking_music_swap_helpers", "__file__": path}
    exec(compile(src.rstrip()[:-len(tail)], path, "exec"), ns)
    ns["_sha256"] = hashlib.sha256(src.encode("utf-8")).hexdigest()
    return ns


def _saved_here():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")


WM = _load_walking_helpers()     # a dict of functions; holds no unreal objects


# =====================================================================================================================
# Pure: args, plan, gates
# =====================================================================================================================

def validate_args(args):
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % args.get("mode"))
    if args.get("asset_path") != ASSET_PATH:
        r.append("ASSET_PATH_INVALID: %r, want %s" % (args.get("asset_path"), ASSET_PATH))
    for field in ("wav", "sha256", "duration_s", "rail_label", "opening_cue_label", "opening_cue_guid", "p01_label",
                  "p01_guid", "shared_rail_guid", "opening_record"):
        if args.get(field) in (None, ""):
            r.append("MISSING_%s" % field.upper())
    for field in ("opening_cue_guid", "p01_guid", "shared_rail_guid"):
        v = str(args.get(field) or "")
        if len(v) != 32 or v != v.upper() or any(c not in "0123456789ABCDEF" for c in v) or v == ZERO_GUID:
            r.append("GUID_INVALID_%s: %r" % (field.upper(), v))
    if not isinstance(args.get("opening_offset_frames", 0), int) or args.get("opening_offset_frames", 0) < 0:
        r.append("OPENING_OFFSET_INVALID: %r" % args.get("opening_offset_frames"))
    if mode == "APPLY" and not str(args.get("decided_by") or "").strip():
        r.append("NOT_DECIDED: args decided_by is empty")
    return r


def wav_header_facts(path):
    """sha256 + header facts from the RIFF chunks directly. NOT the stdlib wave module: the input is
    WAVE_FORMAT_EXTENSIBLE (tag 0xFFFE) [meas: fmt tag read 5 Oct], which the editor's Python 3.11 wave module rejects
    [inf: python311.dll in UE_5.8 Engine/Binaries/ThirdParty/Python3/Win64; EXTENSIBLE support arrived in 3.12; the
    walking stream re-encoded its WAVs to 16-bit for this reason - walking_music_swap_args.json encoding_note]."""
    import struct
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise PlanError("WAV_NOT_RIFF_WAVE: %s" % path)
    pos, fmt, frames = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            tag, ch, rate, _bps, align, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE:
                tag = struct.unpack("<H", body[24:26])[0]       # SubFormat GUID's first two bytes
            fmt = {"tag": tag, "channels": ch, "rate": rate, "block_align": align, "bits": bits}
        elif cid == b"data":
            if fmt is None:
                raise PlanError("WAV_DATA_BEFORE_FMT")
            frames = size // fmt["block_align"]
        pos += 8 + size + (size & 1)
    if fmt is None or frames is None:
        raise PlanError("WAV_CHUNKS_MISSING: %s" % path)
    if fmt["tag"] != 1:
        raise PlanError("WAV_NOT_PCM: format %d" % fmt["tag"])
    return {"sha256": hashlib.sha256(data).hexdigest(), "channels": fmt["channels"], "rate": fmt["rate"],
            "sample_width": fmt["block_align"] // fmt["channels"], "frames": frames,
            "duration_s": frames / float(fmt["rate"])}


def check_input(args, project_dir):
    path = os.path.join(project_dir, *str(args["wav"]).replace("\\", "/").split("/"))
    if not os.path.isfile(path):
        return None, ["WAV_MISSING: %s" % path]
    try:
        f = wav_header_facts(path)
    except PlanError as exc:
        return None, ["WAV_UNREADABLE: %s" % exc]
    f["path"] = path
    r = []
    if f["sha256"] != str(args["sha256"]).lower():
        r.append("WAV_SHA_MISMATCH: %s != args %s" % (f["sha256"][:12], str(args["sha256"])[:12]))
    if abs(f["duration_s"] - float(args["duration_s"])) > HEADER_TOL_S:
        r.append("WAV_DURATION_MISMATCH: header %.4f s, args %.4f s" % (f["duration_s"], float(args["duration_s"])))
    return f, r


def original_p01(opening_record):
    """P01's binding before opening_sequence_apply moved it (its record's 'original' snapshot)."""
    try:
        o = opening_record["original"]["music"]["p01"]
        return {"mode": WM["mode_token"](o["mode"]), "rail": str(o["rail"]).upper(), "offset": int(o["offset"])}
    except (KeyError, TypeError, ValueError):
        return None


def binding(mode, rail, offset=0, secondary=ZERO_GUID):
    return {"mode": WM["mode_token"](mode), "rail": rail, "offset": int(offset), "secondary": secondary}


def _same_binding(a, b, fields=("mode", "rail", "offset", "secondary")):
    return all((a or {}).get(k) == (b or {}).get(k) for k in fields)


def plan_own_rail(live, args, wav_duration_s, tick_rate, p01_original):
    """live: {"rails": [rail-state with "guid"], "opening": binding, "p01": binding, "bindings": [{"owner", "mode",
    "rail", "secondary"}], "ids": {...}, "opening_cue_guid", "p01_guid"}. Returns (plan, refusals)."""
    r = []
    shared = args["shared_rail_guid"]
    rails = live["rails"]
    guids = [x["guid"] for x in rails]
    if live.get("opening_cue_guid") != args["opening_cue_guid"]:
        r.append("OPENING_CUE_GUID_MISMATCH: %r" % live.get("opening_cue_guid"))
    if live.get("p01_guid") != args["p01_guid"]:
        r.append("P01_GUID_MISMATCH: %r" % live.get("p01_guid"))
    if ZERO_GUID in guids or len(set(guids)) != len(guids):
        r.append("EXISTING_RAIL_GUIDS_INVALID: ensure_stable_ids would mint more than the new rail")
    ids = live.get("ids") or {}
    for k in ("cues", "passages"):
        if ZERO_GUID in (ids.get(k) or []):
            r.append("EXISTING_%s_GUID_ZERO: ensure_stable_ids would mint it too" % k.upper())
    if ids.get("show") == ZERO_GUID:
        r.append("SHOW_GUID_ZERO")
    if len(rails) < PASSAGE_RAIL_SLOTS:
        r.append("RAILS_BELOW_PASSAGE_SLOTS: %d rails; an append would land on a Passage index" % len(rails))
    if any(x.get("label") == args["rail_label"] for x in rails):
        r.append("RAIL_LABEL_EXISTS: %r (a previous run?)" % args["rail_label"])
    src = [x for x in rails if x["guid"] == shared]
    if len(src) != 1:
        r.append("SHARED_RAIL_MISSING: %s" % shared)
    op, p1 = live["opening"], live["p01"]
    if op["mode"] != "START":
        r.append("OPENING_NOT_START: %s" % op["mode"])
    if op["rail"] != shared:
        r.append("OPENING_RAIL_UNEXPECTED: %s, want %s" % (op["rail"], shared))
    if p1["mode"] != "SILENCE" or p1["rail"] != shared:
        r.append("P01_NOT_SILENT_ON_SHARED_RAIL: %s %s" % (p1["mode"], p1["rail"]))
    if p01_original is None:
        r.append("P01_ORIGINAL_UNKNOWN: opening_sequence_record.json has no original.music.p01")
    elif p01_original["mode"] != "START" or p01_original["rail"] != shared:
        r.append("P01_ORIGINAL_NOT_START_ON_SHARED: %r" % p01_original)
    others = [b["owner"] for b in live["bindings"]
              if b["owner"] not in ("cue:" + args["opening_cue_label"], args["p01_label"])
              and (b["rail"] == shared or b.get("secondary") == shared)
              and WM["mode_token"](b["mode"]).replace("_", "") in ("START", "EXPLICITCROSSFADE")]
    if others:
        r.append("SHARED_RAIL_OTHER_USERS: %r (walking_music_swap would still refuse RAIL_SHARED)" % others)
    source_out = int(round(float(wav_duration_s) * float(tick_rate)))
    if source_out <= 0:
        r.append("SOURCE_OUT_NONPOSITIVE")
    if r:
        return None, r
    s = src[0]
    plan = {"index": len(rails), "shared_rail": shared,
            "new_rail": {"label": args["rail_label"], "sound": args["asset_path"], "source_in": 0,
                         "source_out": source_out, "fade_in": int(s["fade_in"]), "fade_out": int(s["fade_out"]),
                         "analysis_map": None, "fingerprint": ""},
            "opening_after": binding("START", "<NEW>", args.get("opening_offset_frames", 0), op["secondary"]),
            "p01_after": binding(p01_original["mode"], p01_original["rail"], p01_original["offset"], p1["secondary"]),
            "opening_before": dict(op), "p01_before": dict(p1)}
    return plan, []


def ids_gate(before, after):
    """(new_rail_guid, failures): the only identity change allowed is ONE new valid unique rail GUID appended."""
    out = []
    for k in ("show", "cues", "occurrences", "passages"):
        if before.get(k) != after.get(k):
            out.append("IDS_CHANGED: %s (ensure_stable_ids minted more than the rail)" % k)
    b, a = before.get("rails") or [], after.get("rails") or []
    if len(a) != len(b) + 1:
        out.append("RAIL_COUNT: %d -> %d" % (len(b), len(a)))
        return None, out
    if a[:len(b)] != b:
        out.append("RAIL_GUIDS_CHANGED (not an append)")
    new = a[-1]
    if new == ZERO_GUID:
        out.append("NEW_RAIL_NOT_MINTED")
    elif new in b:
        out.append("NEW_RAIL_GUID_REUSED: %s" % new)
    return new, out


def rails_gate(before_rails, after_rails, want_new):
    out = []
    n = len(before_rails)
    if len(after_rails) != n + 1:
        return ["RAIL_COUNT: %d -> %d" % (n, len(after_rails))]
    for i, (b, a) in enumerate(zip(before_rails, after_rails[:n])):
        if b != a:
            out.append("RAIL_%d_CHANGED: %r" % (i, {k: (b.get(k), a.get(k)) for k in set(a) | set(b)
                                                   if a.get(k) != b.get(k)}))
    got = after_rails[n]
    for k in NEW_RAIL_FIELDS:
        if got.get(k) != want_new.get(k):
            out.append("NEW_RAIL_%s: %r != %r" % (k.upper(), got.get(k), want_new.get(k)))
    return out


def bindings_gate(live, want_opening, want_p01):
    out = []
    if not _same_binding(live["opening"], want_opening):
        out.append("OPENING_BINDING: %r != %r" % (live["opening"], want_opening))
    if not _same_binding(live["p01"], want_p01):
        out.append("P01_BINDING: %r != %r" % (live["p01"], want_p01))
    return out


def master_music_gate(before, after, opening_guid, p01_guid, want_opening_sound, want_p01_sound, seg_s,
                      opening_label, p01_label, tol_s=1e-3):
    """before/after: {block_guid: {"sound", "range_s", ...}}; seg_s: {label: [start_s, end_s]}.
    want_p01_sound None = P01 must have NO music section (Silence)."""
    out = []

    def near(r, s):
        return r is not None and s is not None and max(abs(r[0] - s[0]), abs(r[1] - s[1])) <= tol_s
    o = after.get(opening_guid)
    if o is None or o.get("sound") != want_opening_sound:
        out.append("MASTER_OPENING_MUSIC: %r, want %s" % (o, want_opening_sound))
    elif not near(o.get("range_s"), seg_s.get(opening_label)):
        out.append("MASTER_OPENING_RANGE: %r vs segment %r" % (o.get("range_s"), seg_s.get(opening_label)))
    p = after.get(p01_guid)
    if want_p01_sound is None:
        if p is not None:
            out.append("MASTER_P01_MUSIC_PRESENT: %r (P01 should be Silence)" % p)
    elif p is None or p.get("sound") != want_p01_sound:
        out.append("MASTER_P01_MUSIC: %r, want %s" % (p, want_p01_sound))
    elif not near(p.get("range_s"), seg_s.get(p01_label)):
        out.append("MASTER_P01_RANGE: %r vs segment %r" % (p.get("range_s"), seg_s.get(p01_label)))
    rest_b = {k: v for k, v in before.items() if k not in (opening_guid, p01_guid)}
    rest_a = {k: v for k, v in after.items() if k not in (opening_guid, p01_guid)}
    if sorted(rest_b) != sorted(rest_a):
        out.append("MASTER_MUSIC_SET_CHANGED: gone %r new %r" % (sorted(set(rest_b) - set(rest_a)),
                                                                 sorted(set(rest_a) - set(rest_b))))
    for k in sorted(set(rest_a) & set(rest_b)):
        if rest_a[k].get("sound") != rest_b[k].get("sound") or not near(rest_a[k].get("range_s"),
                                                                         rest_b[k].get("range_s")):
            out.append("MASTER_MUSIC_OTHER_CHANGED: %s %r -> %r" % (k, rest_b[k], rest_a[k]))
    return out


def apply_core(show, plan):
    """Mutate through an adapter (live or fake), judging by re-reading. Returns (new_guid, state_after, failures).
    Caller has already called Modify on the Show."""
    before = show.read()
    show.append_rail(plan["new_rail"])
    show.ensure_stable_ids()
    mid = show.read()
    new_guid, failures = ids_gate(before["ids"], mid["ids"])
    failures += rails_gate(before["rails"], mid["rails"], plan["new_rail"])
    if failures:
        return new_guid, mid, failures
    if mid["rails"][plan["index"]]["guid"] != new_guid:
        return new_guid, mid, ["NEW_RAIL_NOT_AT_INDEX_%d" % plan["index"]]
    want_opening = dict(plan["opening_after"], rail=new_guid)
    show.write_binding("opening", want_opening)
    show.write_binding("p01", plan["p01_after"])
    after = show.read()
    failures += bindings_gate(after, want_opening, plan["p01_after"])
    if after["rails"] != mid["rails"]:
        failures.append("RAILS_CHANGED_BY_REPOINT")
    if after["ids"] != mid["ids"]:
        failures.append("IDS_CHANGED_BY_REPOINT")
    return new_guid, after, failures


def drift_gate(live, record):
    """Failures unless the live state is exactly what APPLY left (rails incl. rail 2E86, bindings, every GUID)."""
    a = record["after"]
    out = []
    if live["rails"] != a["rails"]:
        changed = [i for i, (x, y) in enumerate(zip(live["rails"], a["rails"])) if x != y]
        out.append("RAILS_CHANGED_SINCE_APPLY: count %d vs %d, indices %r (walking_music_swap on P01? revert it "
                   "first)" % (len(live["rails"]), len(a["rails"]), changed))
    if not _same_binding(live["opening"], a["opening"]):
        out.append("OPENING_BINDING_CHANGED_SINCE_APPLY: %r" % live["opening"])
    if not _same_binding(live["p01"], a["p01"]):
        out.append("P01_BINDING_CHANGED_SINCE_APPLY: %r" % live["p01"])
    if live["ids"] != a["ids"]:
        out.append("IDS_CHANGED_SINCE_APPLY")
    users = [b["owner"] for b in live["bindings"] if b["owner"] != "cue:" + record["args"]["opening_cue_label"]
             and record["new_rail_guid"] in (b["rail"], b.get("secondary"))]
    if users:
        out.append("NEW_RAIL_REFERENCED_BY: %r" % users)
    return out


def revert_core(show, record):
    live = show.read()
    drift = drift_gate(live, record)
    if drift:
        return ["STATE_DRIFTED: " + d for d in drift]
    b = record["before"]
    show.write_binding("opening", b["opening"])
    show.write_binding("p01", b["p01"])
    show.remove_rail(record["plan"]["index"], record["new_rail_guid"])
    now = show.read()
    out = []
    if now["rails"] != b["rails"]:
        out.append("REVERT_RAILS_NOT_EXACT")
    if now["ids"] != b["ids"]:
        out.append("REVERT_IDS_NOT_EXACT")
    out += ["REVERT_" + x for x in bindings_gate(now, b["opening"], b["p01"])]
    return out


def live_gates(state):
    r = []
    mode = str(state.get("mode") or "").upper()
    want = "%s %s" % (mode, CONFIRM_WORD)
    if state.get("confirm") != want:
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), want))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN (an open Sequencer evaluates and dirties the map)")
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if not state.get("world_ok"):
        r.append("WRONG_WORLD")
    if mode == "APPLY":
        if state.get("record_exists"):
            r.append("RECORD_EXISTS: %s (REVERT first, or archive a failed one)" % RECORD_NAME)
        if state.get("asset_exists"):
            r.append("ASSET_EXISTS: %s" % ASSET_PATH)
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD")
    return r


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local or an adapter attribute.
# =====================================================================================================================

def _here():
    return _saved_here() if unreal is not None else os.path.dirname(os.path.abspath(__file__))


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _parse_guid(text):
    res = unreal.GuidLibrary.parse_string_to_guid(text)            # opening_sequence_apply.py:594-599 [prec, meas]
    guid, ok = (res if isinstance(res, tuple) else (res, True))
    if not ok or WM["_guid"](guid) != text:
        raise RuntimeError("GUID_PARSE %s" % text)
    return guid


class _LiveShow(object):
    """Adapter over the Show (same interface as the harness fake)."""

    def __init__(self, show, args):
        self.show = show
        self.args = args
        self.rail_reader = WM["_LiveShow"](show, {})
        self.tick_rate = self.rail_reader.tick_rate

    def _cue_index(self):
        cues = list(self.show.get_editor_property("cues"))
        hits = [i for i, c in enumerate(cues) if str(c.get_editor_property("label")) == self.args["opening_cue_label"]]
        if len(hits) != 1:
            raise PlanError("OPENING_CUE_LABEL_COUNT: %d" % len(hits))
        c = cues[hits[0]]
        if str(c.get_editor_property("type")) != str(unreal.InfinityCueType.SEQUENCE):
            raise PlanError("OPENING_CUE_NOT_SEQUENCE")
        return hits[0], cues

    def _p01_index(self):
        ps = list(self.show.get_editor_property("passage_settings"))
        hits = [i for i, p in enumerate(ps) if str(p.get_editor_property("label")) == self.args["p01_label"]]
        if len(hits) != 1:
            raise PlanError("P01_LABEL_COUNT: %d" % len(hits))
        return hits[0], ps

    @staticmethod
    def _binding(m):
        return binding(str(m.get_editor_property("mode")), WM["_guid"](m.get_editor_property("primary_rail_guid")),
                       int(m.get_editor_property("rail_offset_frames").value),
                       WM["_guid"](m.get_editor_property("secondary_rail_guid")))

    def read(self):
        g = WM["_guid"]
        ci, cues = self._cue_index()
        pi, ps = self._p01_index()
        rails = [self.rail_reader._state(r) for r in self.show.get_editor_property("music_rails")]
        return {"rails": rails,
                "opening": self._binding(cues[ci].get_editor_property("scene").get_editor_property("music")),
                "p01": self._binding(ps[pi].get_editor_property("music")),
                "opening_cue_guid": g(cues[ci].get_editor_property("cue_guid")),
                "p01_guid": g(ps[pi].get_editor_property("passage_guid")),
                "bindings": WM["_bindings"](self.show),
                "ids": {"show": g(self.show.get_editor_property("show_guid")),
                        "cues": [g(c.get_editor_property("cue_guid")) for c in cues],
                        "occurrences": [g(c.get_editor_property("wing_pair").get_editor_property("occurrence_guid"))
                                        for c in cues],
                        "passages": [g(p.get_editor_property("passage_guid")) for p in ps],
                        "rails": [x["guid"] for x in rails]}}

    def append_rail(self, desc):
        sound = unreal.load_asset(desc["sound"])
        if not isinstance(sound, unreal.SoundWave):
            raise RuntimeError("SOUND_NOT_LOADED %s" % desc["sound"])
        r = unreal.InfinityMusicRail()
        r.set_editor_property("label", unreal.Text(desc["label"]))         # lighting_events_apply.py:932 [prec]
        r.set_editor_property("sound", sound)
        r.set_editor_property("source_in_frame", unreal.FrameNumber(int(desc["source_in"])))
        r.set_editor_property("source_out_frame", unreal.FrameNumber(int(desc["source_out"])))
        r.set_editor_property("fade_in_frames", unreal.FrameNumber(int(desc["fade_in"])))
        r.set_editor_property("fade_out_frames", unreal.FrameNumber(int(desc["fade_out"])))
        rails = list(self.show.get_editor_property("music_rails"))
        rails.append(r)
        self.show.set_editor_property("music_rails", rails)      # struct arrays are copies: write the array back

    def ensure_stable_ids(self):
        self.show.ensure_stable_ids()

    def remove_rail(self, index, guid):
        rails = list(self.show.get_editor_property("music_rails"))
        if index >= len(rails) or WM["_guid"](rails[index].get_editor_property("rail_guid")) != guid:
            raise RuntimeError("REMOVE_RAIL_MISMATCH %d %s" % (index, guid))
        del rails[index]
        self.show.set_editor_property("music_rails", rails)

    def write_binding(self, which, state):
        m = unreal.InfinitySectionMusicBinding()                          # opening_sequence_apply.py:601-609
        m.set_editor_property("mode", getattr(unreal.InfinityMusicBindingMode, state["mode"]))
        m.set_editor_property("primary_rail_guid", _parse_guid(state["rail"]))
        m.set_editor_property("secondary_rail_guid", _parse_guid(state["secondary"]))
        m.set_editor_property("rail_offset_frames", unreal.FrameNumber(int(state["offset"])))
        if which == "opening":                                            # opening_sequence_apply.py:611-631
            ci, cues = self._cue_index()
            c = cues[ci]
            sc = c.get_editor_property("scene")
            sc.set_editor_property("music", m)
            c.set_editor_property("scene", sc)
            cues[ci] = c
            self.show.set_editor_property("cues", cues)
        elif which == "p01":
            pi, ps = self._p01_index()
            p = ps[pi]
            p.set_editor_property("music", m)
            ps[pi] = p
            self.show.set_editor_property("passage_settings", ps)
        else:
            raise RuntimeError("BINDING_OWNER %s" % which)


def _census():
    return WM["_census"]()


def _master_state(master, show, segments, tick, adapter_state):
    """(seg_s by label, show_rows, master_rows, music rows by block GUID)."""
    gbl = {}
    for p in show.get_editor_property("passage_settings"):
        label = str(p.get_editor_property("label"))
        if label.startswith("Passage"):
            gbl[label] = WM["_guid"](p.get_editor_property("passage_guid"))
    show_rows, master_rows, _ranges = WM["_label_rows"](master, segments, tick, gbl)
    music, _passage = WM["_master_rows"](master)
    return show_rows, master_rows, music


def _gather(args, run):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    facts, refusals = check_input(args, project)
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    if show is None or master is None:
        raise PlanError("SHOW_OR_MASTER_DID_NOT_LOAD")
    adapter = _LiveShow(show, args)
    live = adapter.read()
    tick = adapter.tick_rate
    with open(os.path.join(_here(), args["opening_record"]), "r", encoding="utf-8") as handle:
        p01_orig = original_p01(json.load(handle))
    plan, plan_refusals = (None, ["WAV_UNREADABLE"]) if facts is None else plan_own_rail(
        live, args, facts["duration_s"], tick, p01_orig)
    refusals += plan_refusals
    segments = WM["_segments"](show)
    _rows, dup = WM["segment_rows"](segments)
    if dup:
        refusals.append("SEGMENT_LABELS_DUPLICATED: %r" % dup)
    show_rows, master_rows, music = _master_state(master, show, segments, tick, live)
    refusals += WM["sync_gate"](show_rows, master_rows)
    warnings = []
    shared = [x for x in live["rails"] if x["guid"] == args["shared_rail_guid"]]
    op_seg = show_rows.get(args["opening_cue_label"])
    fit_row = None
    if plan and op_seg and facts:
        nr = plan["new_rail"]
        fit_row = WM["fit"](op_seg[1] - op_seg[0], facts["duration_s"], 0.0,
                            plan["opening_after"]["offset"] / tick, nr["fade_in"] / tick, nr["fade_out"] / tick)
        warnings.append("OPENING_FIT: Opening %.3f s, sketch 2 %.3f s, silence tail %.3f s, fade-in %s, fade-out %s"
                        % (fit_row["passage_s"], fit_row["song_s"], fit_row["silence_tail_s"], fit_row["fade_in"],
                           fit_row["fade_out"]))
        warnings.append("P01_PLAYS_%s_UNTIL_WALKING_SWAP: P01 returns to START on rail %s, whose sound is still the "
                        "pre-4-Oct P01 song" % (shared[0]["sound"] if shared else "?", args["shared_rail_guid"]))
    return {"facts": facts, "live": live, "plan": plan, "refusals": refusals, "warnings": warnings,
            "segments": segments, "tick_rate": tick, "show_rows": show_rows, "master_rows": master_rows,
            "music": music, "fit": fit_row, "p01_original": p01_orig}, show, master, adapter


def _probe(args, live):
    """DRY: build an InfinityMusicRail + binding STRUCT in memory (never added to the Show) and read it back with the
    same reader APPLY uses. Proves the setters and the Text/soft-pointer round-trip; touches no package."""
    out = {}
    shared = [x for x in live["rails"] if x["guid"] == args["shared_rail_guid"]]
    try:
        sound = unreal.load_asset(shared[0]["sound"]) if shared else None
        r = unreal.InfinityMusicRail()
        out["fresh_guid"] = WM["_guid"](r.get_editor_property("rail_guid"))
        r.set_editor_property("label", unreal.Text(args["rail_label"]))
        r.set_editor_property("sound", sound)
        r.set_editor_property("source_out_frame", unreal.FrameNumber(2292088))
        r.set_editor_property("fade_in_frames", unreal.FrameNumber(24000))
        st = WM["_LiveShow"]._state(None, r)           # the reader APPLY uses; it never touches self
        out["readback"] = st
        out["ok"] = (out["fresh_guid"] == ZERO_GUID and st["label"] == args["rail_label"] and
                     st["sound"] == (shared[0]["sound"] if shared else None) and st["source_out"] == 2292088 and
                     st["fade_in"] == 24000 and st["analysis_map"] is None)
        m = unreal.InfinitySectionMusicBinding()
        m.set_editor_property("mode", unreal.InfinityMusicBindingMode.START)
        m.set_editor_property("primary_rail_guid", _parse_guid(args["shared_rail_guid"]))
        out["binding_readback"] = _LiveShow._binding(m)
        out["ok"] = out["ok"] and out["binding_readback"]["rail"] == args["shared_rail_guid"] and \
            out["binding_readback"]["mode"] == "START"
        out["has_ensure_stable_ids"] = hasattr(unreal.InfinityStageShowAsset, "ensure_stable_ids")
        out["ok"] = out["ok"] and out["has_ensure_stable_ids"]
    except Exception as exc:  # noqa: BLE001 - reported
        out["ok"] = False
        out["error"] = repr(exc)
    return out


def run_dry(args, run):
    g, _show, _master, _adapter = _gather(args, run)
    if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
        g["refusals"].append("ASSET_EXISTS: %s" % ASSET_PATH)
    probe = _probe(args, g["live"])
    if not probe.get("ok"):
        g["refusals"].append("STRUCT_PROBE_FAILED: %r" % probe)
    live = g["live"]
    report = {"tool": TOOL, "run": run, "mode": "DRY", "args": args, "apply_ready": not g["refusals"],
              "plan": g["plan"], "refusals": g["refusals"], "warnings": g["warnings"], "probe": probe,
              "wav": g["facts"], "fit": g["fit"], "p01_original": g["p01_original"],
              "rails": live["rails"], "opening": live["opening"], "p01": live["p01"],
              "master_music": {k: g["music"].get(live[k + "_guid"] if k != "opening" else live["opening_cue_guid"])
                               for k in ("opening", "p01")},
              "segments": g["segments"], "tick_rate": g["tick_rate"], "walking_helpers_sha256": WM["_sha256"]}
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
    for text in g["refusals"]:
        unreal.log_warning("%s_REFUSAL|run=%s|%s" % (MARK, run, text))
    for text in g["warnings"]:
        unreal.log("%s_WARNING|run=%s|%s" % (MARK, run, text))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("%s_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|probe=%d|rails=%d|report=%s"
               % (MARK, run, int(not g["refusals"]), len(g["refusals"]), int(bool(probe.get("ok"))),
                  len(live["rails"]), out))


def _backup(run, suffix):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    folder = os.path.join(project, "Backups", "PreOpeningOwnRail%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for path in (SHOW_PATH, MASTER_PATH):
        src = WM["_content_file"](path)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"asset": path, "source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _import_wave(facts):
    folder, name = ASSET_PATH.rsplit("/", 1)
    task = unreal.AssetImportTask()                         # walking_music_swap.py:861-872 [meas, 16-bit]
    task.set_editor_property("filename", facts["path"])
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    s = unreal.load_asset(ASSET_PATH)
    if not isinstance(s, unreal.SoundWave):
        return ["IMPORT_NOT_SOUNDWAVE: %s" % ASSET_PATH]
    out = []
    dur = float(s.get_editor_property("duration"))
    if abs(dur - facts["duration_s"]) > DURATION_TOL_S:
        out.append("IMPORT_DURATION: %.4f vs WAV %.4f" % (dur, facts["duration_s"]))
    if bool(s.get_editor_property("looping")):
        out.append("IMPORTED_LOOPING")
    return out


def _post_rebuild_gates(show, master, args, segs_before, master_rows_before, music_before, tick, live,
                        want_opening_sound, want_p01_sound):
    segs_after = WM["_segments"](show)
    f = WM["length_gate"](segs_before, segs_after)                       # tolerance 0 ticks
    show_rows, master_rows, music = _master_state(master, show, segs_after, tick, live)
    f += WM["sync_gate"](show_rows, master_rows)
    f += WM["section_gate"](master_rows_before, master_rows)
    f += master_music_gate(music_before, music, live["opening_cue_guid"], live["p01_guid"], want_opening_sound,
                           want_p01_sound, show_rows, args["opening_cue_label"], args["p01_label"])
    return f, music


def run_apply(args, run):
    g, show, master, adapter = _gather(args, run)
    if g["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(g["refusals"]))
    plan, live, tick = g["plan"], g["live"], g["tick_rate"]
    record_path = os.path.join(_here(), RECORD_NAME)
    backup = _backup(run, "")
    unreal.log("%s_BACKUP_OK|run=%s|backup=%s" % (MARK, run, backup))
    record = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "backup": backup, "args": args,
              "decided_by": args.get("decided_by"), "applied": False, "sound_imported": False,
              "written": datetime.datetime.now().isoformat(timespec="seconds"), "wav": g["facts"], "plan": plan,
              "before": {k: live[k] for k in ("rails", "opening", "p01", "ids")},
              "segments_before": g["segments"], "master_music_before": g["music"],
              "walking_helpers_sha256": WM["_sha256"]}
    WM["write_record_exclusive"](record_path, record)                  # BEFORE any change, including the import
    failures = _import_wave(g["facts"])
    record["sound_imported"] = True
    WM["update_record"](record_path, record)
    new_guid, after = None, None
    if not failures:
        show.modify()
        try:
            new_guid, after, f = apply_core(adapter, plan)
            failures += f
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            failures.append("WRITE_RAISED: %r" % exc)
    record["new_rail_guid"] = new_guid
    if not failures:
        result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
        record["rebuild_result"] = str(result)
        if result is False or result is None:
            failures.append("REBUILD_RETURNED %r" % (result,))
        shared_sound = [x for x in live["rails"] if x["guid"] == plan["shared_rail"]][0]["sound"]
        f, music_after = _post_rebuild_gates(show, master, args, g["segments"], g["master_rows"], g["music"], tick,
                                             live, ASSET_PATH, shared_sound)
        failures += f
        record["master_music_after"] = music_after
    expected = [SHOW_PATH, MASTER_PATH, ASSET_PATH]
    failures += WM["census_gate"](_census(), expected)
    if failures:
        WM["update_record"](record_path, dict(record, applied=False, failed=failures))
        os.rename(record_path, record_path + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|NOTHING SAVED; Don't-Save restart (Show/Master/wave unsaved in memory); backup %s"
              % (failures[:10], backup))
    for path in expected:
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s|record=%s (REVERT or restore %s)" % (path, record_path, backup))
    record["after"] = {k: after[k] for k in ("rails", "opening", "p01", "ids")}
    record["applied"] = True
    WM["update_record"](record_path, record)
    # Post-save read-back through a fresh adapter.
    live2 = _LiveShow(unreal.load_asset(SHOW_PATH), args).read()
    dd = [x for x in drift_gate(live2, record)]
    dd += WM["length_gate"](g["segments"], WM["_segments"](unreal.load_asset(SHOW_PATH)))
    if not os.path.isfile(WM["_content_file"](ASSET_PATH)):
        dd.append("SOUND_FILE_NOT_ON_DISK")
    if _census() != {"content": [], "maps": []}:
        dd.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if dd:
        record["post_save_readback_failed"] = dd
        WM["update_record"](record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|record kept (REVERT or restore %s)" % (dd[:8], backup))
    unreal.log("%s_APPLY_OK|run=%s|new_rail=%s|index=%d|opening=%s|p01=START:%s|segments=unchanged|backup=%s|"
               "record=%s|decided_by=%s" % (MARK, run, new_guid, plan["index"], ASSET_PATH, plan["shared_rail"],
                                            backup, record_path, args.get("decided_by")))


def run_revert(args, run):
    record_path = os.path.join(_here(), RECORD_NAME)
    with open(record_path, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied"):
        _stop(run, "REVERT_RECORD_CONTEXT")
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    adapter = _LiveShow(show, record["args"])
    live = adapter.read()
    drift = drift_gate(live, record)
    if drift:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%r (restore from %s instead)" % (drift[:8], record["backup"]))
    tick = adapter.tick_rate
    seg0 = WM["_segments"](show)
    show_rows, master_rows0, music0 = _master_state(master, show, seg0, tick, live)
    stale = WM["sync_gate"](show_rows, master_rows0)
    if stale:
        _stop(run, "MASTER_NOT_IN_SYNC_BEFORE_REVERT|%r (run the guarded rebuild first)" % stale[:6])
    backup = _backup(run, "Revert")
    show.modify()
    try:
        errs = revert_core(adapter, record)
    except Exception as exc:  # noqa: BLE001
        errs = ["WRITE_RAISED: %r" % exc]
    if not errs:
        result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
        if result is False or result is None:
            errs.append("REBUILD_RETURNED %r" % (result,))
        shared_sound = [x for x in live["rails"] if x["guid"] == record["plan"]["shared_rail"]][0]["sound"]
        f, _m = _post_rebuild_gates(show, master, record["args"], seg0, master_rows0, music0, tick, live,
                                    shared_sound, None)
        errs += f
    errs += WM["census_gate"](_census(), [SHOW_PATH, MASTER_PATH])
    if errs:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart, then restore %s" % (errs[:8],
                                                                                              record["backup"]))
    for path in (SHOW_PATH, MASTER_PATH):
        if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % path)
    now = _LiveShow(unreal.load_asset(SHOW_PATH), record["args"]).read()
    final = []
    if now["rails"] != record["before"]["rails"] or now["ids"] != record["before"]["ids"]:
        final.append("RAILS_OR_IDS_NOT_AS_BEFORE")
    final += bindings_gate(now, record["before"]["opening"], record["before"]["p01"])
    if _census() != {"content": [], "maps": []}:
        final.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if final:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (final, record["backup"]))
    deleted = "kept"
    if args.get("delete_asset_on_revert") is True:
        refs = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(ASSET_PATH, False)]
        if refs:
            _stop(run, "DELETE_REFUSED_REFERENCED|%s|%s (Show already reverted and saved)" % (ASSET_PATH, refs))
        unreal.EditorAssetLibrary.delete_asset(ASSET_PATH)
        if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
            _stop(run, "DELETE_FAILED|%s" % ASSET_PATH)
        deleted = ASSET_PATH
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("%s_REVERT_OK|run=%s|removed_rail=%s|opening=START:%s|p01=SILENCE|sound=%s|backup=%s|record=%s"
               % (MARK, run, record["new_rail_guid"], record["plan"]["shared_rail"], deleted, backup, archived))


def main():
    g = globals()
    args = g.get("OPENING_RAIL_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("OPENRAIL-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    rp = os.path.join(_here(), RECORD_NAME)
    applied = False
    if os.path.exists(rp):
        with open(rp, "r", encoding="utf-8") as handle:
            applied = bool(json.load(handle).get("applied"))
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": _census(), "record_exists": os.path.exists(rp), "record_applied": applied,
             "asset_exists": unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH) if mode == "APPLY" else False,
             "world_ok": world is not None and str(world.get_outermost().get_name()) == EXPECTED_WORLD}
    early = live_gates(state)
    if early:
        _stop(run, "REFUSED|" + " || ".join(early))
    try:
        if mode == "REVERT":
            run_revert(args, run)
        elif mode == "APPLY":
            run_apply(args, run)
        else:
            run_dry(args, run)
    except PlanError as exc:
        _stop(run, "PLAN_REFUSED|" + str(exc))


if unreal is not None:
    main()
