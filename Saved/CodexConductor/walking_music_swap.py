"""WALKING MUSIC SWAP: put Cameron's six new walking tracks (5 Oct) on the six Passages, KEEPING every Passage length.
Offline-written 5 Oct, NEVER RUN IN UNREAL. Harness: test_walking_music_swap.py (system Python, no Unreal).

Decisions (args walking_music_swap_args.json): mapping P0n_WalkingN.wav -> Passage n confirmed by Gary 5 Oct; Passage
lengths are KEPT (no retime, no refit) - Gary fills spare time with pauses / set pieces; P04 imports the "+10 s silence"
copy P04_Walking4_pad10.wav (Gary 5 Oct "+10 silence for now"), the unpadded file is kept for Cameron's real 0:48.

Tiers per claim: [decl] declaration-proven (plugin header/source we can read, cited file:line), [prec] in-repo precedent
call (cited), [meas] an earlier run's read-back record (cited), [inf] inferred (why stated).

WHERE THE MUSIC LIVES
  * A Passage's "Defining Music" is NOT a field of the Passage: the Cue Desk's Passage proxy shows the Show's
    MusicRails[] entry whose RailGuid == PassageSettings.Music.PrimaryRailGuid under the category "Defining Music"
    [decl InfinityStagePassageProxy.h:26-27, InfinityStagePassageProxy.cpp:23-32 (read), :101-109 (write-back)].
  * The rail: FInfinityMusicRail {RailGuid, Label, Sound (TSoftObjectPtr<USoundBase>), SourceInFrame, SourceOutFrame,
    FadeInFrames, FadeOutFrames, SourceFingerprint (VisibleAnywhere/BlueprintReadOnly), AnalysisMap (soft
    UInfinityStageMusicMapAsset)} [decl InfinityStageTypes.h:733-765]; Show.MusicRails [decl InfinityStageShowAsset.h:54-55];
    the binding FInfinitySectionMusicBinding {Mode Start/Continue/Silence/ExplicitCrossfade, PrimaryRailGuid,
    SecondaryRailGuid, RailOffsetFrames} [decl InfinityStageTypes.h:28-35, 767-783]; Passage.Music [decl :1002-1003];
    Scene/Sequence cue Scene.Music [decl :816-817].
  * So this tool writes rail.Sound (the property the Show uses). Python names music_rails / rail_guid / sound /
    primary_rail_guid / mode [prec Saved/CodexCueing/choreo_tool.py:89-96, opening_sequence_apply.py:179-182, 605-609].
  * SourceFingerprint is VisibleAnywhere+BlueprintReadOnly [decl InfinityStageTypes.h:759-760]: Python cannot set it
    [inf: UE Python refuses read-only properties]. Nothing reads it [decl: grep of Plugins/InfinityStage/Source - only
    InfinityStageDevFixtureBuilder.cpp:357 writes it]. It stays stale (old file's MD5) - cosmetic; reported.

WHAT THE BUILDER DOES WITH IT (why the Passage length does not move)
  * Passage length = LeadIn + sum(IntervalToNext) + Tail; the compiler never reads the rail [decl
    InfinityStageCompiler.cpp:250-288; rails are only validated at :181-196]. Swapping Sound cannot retime [decl].
  * RebuildManagedMaster places ONE Infinity audio section per Start/ExplicitCrossfade Passage over the WHOLE Passage
    segment [SegmentStart, SegmentEnd), start offset SourceIn + RailOffset, SetRepeating(false)
    [decl InfinityStageSequenceBuilderLibrary.cpp:503-544]. Scenes/Sequence cues the same [decl :545-595].
  * Fades ("SB:78-95" = InfinityStageSequenceBuilderLibrary.cpp:78-96 ApplyVolumeEnvelope): FadeIn 0->1 from the
    PASSAGE start; FadeOut 1->0 ending at the PASSAGE END, not the song end [decl]. Song shorter than the Passage: the
    song ends naturally and the Passage runs on in silence; the fade-out ramps over silence (inaudible) [inf: a
    non-repeating audio section plays the sound once; engine runtime .cpp absent, MovieSceneAudioSection.h:112,126-133
    declares SetRepeating / PlayUntilFinished]. Song longer (P06): cut at the Passage end, faded over FadeOutFrames
    (hard cut if 0) [decl :89-93 + inf as above]. PlayUntilFinished is never set by the builder [decl :521-528].
  * SourceOutFrame is NOT used by the builder [decl: :521-528 use SourceIn only]; it IS used by the Cue Desk (Used
    Music, scrub stop, Refit duration, music-marker anchor normalisation) [decl SInfinityStageCueDesk.cpp:336-337,
    4920-4930, 5128, 4697-4700]. Policy args.source_out_policy: "new_duration" (default; old value would describe the
    old song) or "keep". 0 stays 0 (= whole sound).

REBUILD PATH
  * Library call UInfinityStageSequenceBuilderLibrary.RebuildManagedMaster(Show, Master)
    [decl InfinityStageSequenceBuilderLibrary.h:26]; Cue Desk "Rebuild Managed Master Sequence" calls the same
    [decl SInfinityStageCueDesk.cpp:3921-3924, 6043-6055]; the standing guarded step is
    Scripts/rebuild_managed_master_guarded.py:89 (same call, then save Master/Show only, compare to 0.05 s). That script
    refuses ANY dirty package (:78-79), so it cannot run after this tool's unsaved write: this tool makes the same call
    in-process [prec opening_sequence_apply.py:803] and keeps the guarded script's discipline (backup first, save only
    expected packages, compare after).

STALE WHEN THE SOUND CHANGES (DRY reports each, per Passage; APPLY changes none of them)
  1. Choreo song markers: LS_Choreo_Passage_N carries marked frames "bar n" / "§ <label>" made from the OLD song's
     analysis beats/major changes [prec Saved/CodexCueing/choreo_tool.py:14-15, 89-122; meas choreo_report_choreo-apply-3.json
     marker_count P1 35 .. P6 7].
  2. MusicMap MM_Pnn_Analysis (rail.AnalysisMap): describes the old song (duration, beats, curves) [decl
     InfinityStageMusicAnalysisImporter.cpp:180-196]. Consumers are Cue-Desk editor actions only [decl grep:
     SInfinityStageCueDesk.cpp:334, 777, 3326, 3370, 4684, 4928, 6952]. Policy args.analysis_map_policy "keep" (default,
     reported stale) or "unlink" (set None; REVERT restores).
  3. Camera anchors: "Pin Confirmed Music Markers" writes PinnedPassageFrames from CONFIRMED map markers, normalised by
     the rail's used length [decl SInfinityStageCueDesk.cpp:4670-4746]. Hand pins look identical; DRY reports counts.
  4. "Apply Music Analysis Curve" keys on the Passage camera section's Wing/Speed channels [decl
     SInfinityStageCueDesk.cpp:3356-3420]; DRY reports keyed-channel counts as CANDIDATES (cannot tell origin).
  5. Refit from Music would derive a NEW wing count from SourceOut (or map duration) [decl SInfinityStageCueDesk.cpp:
     3759-3766, 4920-4930, 5953-6040]. NEVER run (Gary: keep lengths). DRY prints what it would derive, as a warning.
  6. NOT stale: Light Drama is distance-driven [decl InfinityStageLightDrama.h:24-26]; lighting_scores.json has no
     music/beat/analysis field [meas grep 5 Oct: 0 hits]; Passage lengths are unchanged so distance keys hold.

OPENING INTERPLAY (P01): opening_sequence_apply.py moved P01's rail onto the Opening cue (Opening Scene.Music = Start on
P01's rail, P01 = Silence) [prec opening_sequence_apply.py:761-768; meas opening_sequence_report_apply.json readback
music: opening START 2E86171B..., p01 SILENCE 2E86171B...]. Setting that rail's Sound would put Walking1 in the OPENING.
So: a rail referenced by any other enabled Start/Crossfade binding is REFUSED (RAIL_SHARED), and a Silence Passage is
refused unless args.silence_policy == "set_start". P01 therefore waits until the Opening has its own rail
(opening_reconcile_plan.md); args.apply_passages selects which Passages a run touches (one record per set).

Modes (walking_music_swap_run.py <- walking_music_swap_args.json, confirm "<MODE> WALKING MUSIC"):
  DRY    read-only; walking_music_swap_dry.json; WALKING_MUSIC_DRY_OK|run=..
  APPLY  guards -> import NEW SoundWaves (refuse if any exists) -> backup Show+Master -> exclusive record -> set rails ->
         read back -> rebuild Master -> Passage segments UNCHANGED (refuse) -> Master music sections carry the new waves
         -> save ONLY Show, Master, the new waves -> census clean -> WALKING_MUSIC_APPLY_OK|run=..
  REVERT restore every recorded rail field + mode exactly, rebuild, same gates; WALKING_MUSIC_REVERT_OK|run=..
  Failure: WALKING_MUSIC_STOPPED|run=..|reason=..
Never: Save All, level save, reload, open/scrub Sequencer, refit, end PIE, Python audio analysis; no unreal objects in
module globals. Importing without `unreal` runs nothing.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import wave

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


TOOL = "walking_music_swap"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"                 # rebuild_managed_master_guarded.py:22
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"   # rebuild_managed_master_guarded.py:23
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
DEST_FOLDER = "/Game/InfinityStage/Audio/PassageMusic/Cameron_20261005"
ARGS_NAME = "walking_music_swap_args.json"
DRY_NAME = "walking_music_swap_dry.json"
RECORD_PREFIX = "walking_music_swap_record_"
PASSAGE_KEYS = ("1", "2", "3", "4", "5", "6")
SOURCE_OUT_POLICIES = ("new_duration", "keep")
ANALYSIS_MAP_POLICIES = ("keep", "unlink")
SILENCE_POLICIES = ("refuse", "set_start")
PLAYING_MODES = ("START", "EXPLICITCROSSFADE", "EXPLICIT_CROSSFADE")
DURATION_TOL_S = 0.02      # imported SoundWave duration vs WAV header
HEADER_TOL_S = 0.002       # WAV header vs args
LENGTH_TOL_TICKS = 0       # Passage segment lengths must be bit-identical
CHOREO_SONG_PREFIXES = ("bar ", "§ ")   # choreo_tool.py:110,117


class PlanError(Exception):
    pass


# =====================================================================================================================
# Pure: args, inputs, maths, gates
# =====================================================================================================================

def validate_args(args):
    """Refusals for the args file itself (pure)."""
    r = []
    mode = str(args.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % args.get("mode"))
    if args.get("keep_passage_lengths") is not True:
        r.append("KEEP_LENGTHS_REQUIRED: Gary 5 Oct keeps Passage lengths; this tool never retimes or refits")
    if args.get("dest_folder") != DEST_FOLDER:
        r.append("DEST_FOLDER_INVALID: %r, want %s" % (args.get("dest_folder"), DEST_FOLDER))
    if args.get("source_out_policy", "new_duration") not in SOURCE_OUT_POLICIES:
        r.append("SOURCE_OUT_POLICY_INVALID: %r" % args.get("source_out_policy"))
    if args.get("analysis_map_policy", "keep") not in ANALYSIS_MAP_POLICIES:
        r.append("ANALYSIS_MAP_POLICY_INVALID: %r" % args.get("analysis_map_policy"))
    if args.get("silence_policy", "refuse") not in SILENCE_POLICIES:
        r.append("SILENCE_POLICY_INVALID: %r" % args.get("silence_policy"))
    passages = args.get("passages") or {}
    if sorted(passages) != list(PASSAGE_KEYS):
        r.append("PASSAGES_NOT_P01_P06: %r" % sorted(passages))
    names = []
    for key, row in sorted(passages.items()):
        for field in ("wav", "sha256", "duration_s", "asset_name"):
            if field not in row:
                r.append("P%s_MISSING_%s" % (key, field.upper()))
        names.append(row.get("asset_name"))
        base = os.path.basename(str(row.get("wav", "")).replace("\\", "/"))
        if not base.startswith("P%02d_" % int(key)):
            r.append("P%s_MAPPING: %s does not carry the P%02d_ prefix" % (key, base, int(key)))
        if not str(row.get("asset_name", "")).startswith("SW_P%02d_" % int(key)):
            r.append("P%s_ASSET_NAME: %r must start SW_P%02d_" % (key, row.get("asset_name"), int(key)))
        pad = row.get("pad")
        if pad is not None:
            for field in ("unpadded_wav", "unpadded_sha256", "pad_s", "decided_by"):
                if field not in pad:
                    r.append("P%s_PAD_MISSING_%s" % (key, field.upper()))
    if len(set(names)) != len(names):
        r.append("ASSET_NAMES_NOT_UNIQUE")
    targets = args.get("apply_passages")
    if not isinstance(targets, list) or not targets or any(str(t) not in PASSAGE_KEYS for t in targets) \
            or len(set(map(str, targets))) != len(targets):
        r.append("APPLY_PASSAGES_INVALID: %r" % targets)
    return r


def wav_facts(path):
    """sha256 + header facts of a PCM WAV (pure; stdlib wave reads 24-bit headers)."""
    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    w = wave.open(path, "rb")
    try:
        frames, rate = w.getnframes(), w.getframerate()
        return {"sha256": digest, "channels": w.getnchannels(), "rate": rate, "sample_width": w.getsampwidth(),
                "frames": frames, "duration_s": frames / float(rate)}
    finally:
        w.close()


def _abs(project_dir, rel):
    return os.path.join(project_dir, *str(rel).replace("\\", "/").split("/"))


def check_inputs(args, project_dir):
    """Per-Passage file facts + refusals: present, sha256 equal, header duration equal; padding consistent."""
    facts, r = {}, []
    for key, row in sorted((args.get("passages") or {}).items()):
        path = _abs(project_dir, row["wav"])
        if not os.path.isfile(path):
            r.append("WAV_MISSING_P%s: %s" % (key, path))
            continue
        f = wav_facts(path)
        f["path"] = path
        facts[key] = f
        if f["sha256"] != str(row["sha256"]).lower():
            r.append("WAV_SHA_MISMATCH_P%s: %s != args %s" % (key, f["sha256"][:12], str(row["sha256"])[:12]))
        if abs(f["duration_s"] - float(row["duration_s"])) > HEADER_TOL_S:
            r.append("WAV_DURATION_MISMATCH_P%s: header %.4f s, args %.4f s" % (key, f["duration_s"], row["duration_s"]))
        pad = row.get("pad")
        if pad:
            upath = _abs(project_dir, pad["unpadded_wav"])
            if not os.path.isfile(upath):
                r.append("PAD_UNPADDED_MISSING_P%s: %s" % (key, upath))
                continue
            u = wav_facts(upath)
            f["unpadded"] = dict(u, path=upath)
            if u["sha256"] != str(pad["unpadded_sha256"]).lower():
                r.append("PAD_UNPADDED_SHA_MISMATCH_P%s" % key)
            if abs((f["duration_s"] - u["duration_s"]) - float(pad["pad_s"])) > HEADER_TOL_S:
                r.append("PAD_LENGTH_P%s: padded %.4f - unpadded %.4f != pad %.4f" % (
                    key, f["duration_s"], u["duration_s"], float(pad["pad_s"])))
            if (u["rate"], u["channels"], u["sample_width"]) != (f["rate"], f["channels"], f["sample_width"]):
                r.append("PAD_FORMAT_P%s: padded and unpadded formats differ" % key)
    return facts, r


def fit(passage_s, song_s, source_in_s=0.0, offset_s=0.0, fade_in_s=0.0, fade_out_s=0.0):
    """How a song plays in a Passage section [decl SequenceBuilderLibrary.cpp:78-96, 521-528]: section = whole Passage,
    sound from source_in+offset, non-repeating; fade-in from the Passage start; fade-out ENDS at the Passage end."""
    if passage_s <= 0:
        raise PlanError("PASSAGE_LENGTH_NONPOSITIVE: %r" % passage_s)
    remaining = float(song_s) - float(source_in_s) - float(offset_s)
    if remaining <= 0:
        raise PlanError("SONG_STARTS_PAST_ITS_END: song %.3f s, start %.3f s" % (song_s, source_in_s + offset_s))
    overrun = remaining - passage_s
    audible = min(remaining, passage_s)
    fade_out_from = max(0.0, passage_s - float(fade_out_s))
    if float(fade_out_s) <= 0:
        fade = "no fade-out: " + ("hard cut at the Passage end" if overrun > 0 else "song ends naturally")
    elif overrun > 0:
        fade = "song CUT at the Passage end, faded %.3f-%.3f s (Passage time)" % (fade_out_from, passage_s)
    elif remaining <= fade_out_from:
        fade = ("song ends naturally at %.3f s; fade-out %.3f-%.3f s ramps over silence (inaudible)"
                % (remaining, fade_out_from, passage_s))
    else:
        fade = "song ends at %.3f s INSIDE the fade-out window %.3f-%.3f s (partly faded)" % (
            remaining, fade_out_from, passage_s)
    return {"passage_s": round(passage_s, 6), "song_s": round(float(song_s), 6), "start_in_song_s": round(
        float(source_in_s) + float(offset_s), 6), "audible_s": round(audible, 6), "fits": overrun <= 1e-6,
        "overrun_s": round(max(0.0, overrun), 6), "silence_tail_s": round(max(0.0, -overrun), 6),
        "fade_in": ("%.3f s from the Passage start" % min(float(fade_in_s), passage_s)) if fade_in_s > 0 else "none",
        "fade_out": fade}


def segment_rows(segments):
    """[{label, start, end}] (ticks) -> {label: [start, end]}; duplicate labels are a refusal."""
    out, dup = {}, []
    for s in segments:
        if s["label"] in out:
            dup.append(s["label"])
        out[s["label"]] = [int(s["start"]), int(s["end"])]
    return out, dup


def length_gate(before, after, tol_ticks=LENGTH_TOL_TICKS):
    """Failures unless every compiled segment (Passages AND sequences) is unchanged: same set, lengths, starts."""
    b, bd = segment_rows(before)
    a, ad = segment_rows(after)
    out = []
    if bd or ad:
        out.append("SEGMENT_LABELS_DUPLICATED: before %r after %r" % (bd, ad))
    if sorted(b) != sorted(a):
        out.append("SEGMENT_SET_CHANGED: gone %r new %r" % (sorted(set(b) - set(a)), sorted(set(a) - set(b))))
    for label in sorted(set(a) & set(b)):
        lb, la = b[label][1] - b[label][0], a[label][1] - a[label][0]
        if abs(lb - la) > tol_ticks:
            out.append("LENGTH_MOVED: %s %d -> %d ticks" % (label, lb, la))
        if abs(b[label][0] - a[label][0]) > tol_ticks:
            out.append("START_MOVED: %s %d -> %d ticks" % (label, b[label][0], a[label][0]))
    return out


def mode_token(text):
    """'<InfinityMusicBindingMode.START: 0>' / 'InfinityMusicBindingMode.START' / 'START' -> 'START'."""
    return str(text).strip(" <>").split(":")[0].split(".")[-1].strip().upper()


def sync_gate(show_rows, master_rows, tol_s=0.05):
    """Failures unless the Master already matches the Show (labels -> [start_s, end_s]); 0.05 s as
    rebuild_managed_master_guarded.py:56-58. A stale Master would be silently re-laid by this tool's rebuild (e.g. the
    Opening Gary lengthened at 14:02) - that is the guarded rebuild's job, run first and on its own."""
    out = []
    for label in sorted(show_rows):
        m = master_rows.get(label)
        if m is None:
            out.append("MASTER_SECTION_MISSING: %s" % label)
            continue
        err = max(abs(show_rows[label][0] - m[0]), abs(show_rows[label][1] - m[1]))
        if err > tol_s:
            out.append("MASTER_STALE: %s Show %r Master %r (err %.3f s)" % (label, show_rows[label], m, err))
    for label in sorted(set(master_rows) - set(show_rows)):
        out.append("MASTER_EXTRA_SECTION: %s" % label)
    return out


def section_gate(before, after, tol_s=1e-3):
    """Failures unless every Master Passage section ({label: [start_s, end_s]}) is where it was."""
    out = []
    for label in sorted(set(before) | set(after)):
        b, a = before.get(label), after.get(label)
        if b is None or a is None or max(abs(b[0] - a[0]), abs(b[1] - a[1])) > tol_s:
            out.append("MASTER_PASSAGE_SECTION_MOVED: %s %r -> %r" % (label, b, a))
    return out


def rail_plan(passages, bindings, rails, targets, silence_policy):
    """Which rail each target Passage writes, with refusals.
    passages: {key: {"label", "guid", "mode", "rail"}}; bindings: [{"owner", "mode", "rail", "secondary"}] for EVERY
    enabled cue/Passage binding; rails: {guid: rail-state}; targets: ["1", ...]."""
    plan, r = {}, []
    for key in targets:
        p = passages.get(key)
        if p is None:
            r.append("P%s_PASSAGE_NOT_FOUND" % key)
            continue
        mode = mode_token(p["mode"])
        rail = p["rail"]
        if rail not in rails:
            r.append("P%s_RAIL_MISSING: %s" % (key, rail))
            continue
        if mode.replace("_", "") == "EXPLICITCROSSFADE" or mode == "CONTINUE":
            r.append("P%s_MODE_UNSUPPORTED: %s (secondary rail / continuation not handled)" % (key, mode))
            continue
        set_start = False
        if mode == "SILENCE":
            if silence_policy != "set_start":
                r.append("P%s_SILENT: Passage music is Silence (opening_sequence_apply moved P01's rail to the Opening); "
                         "silence_policy 'set_start' restores Start once the rail is not shared" % key)
                continue
            set_start = True
        others = [b for b in bindings if b["owner"] != p["label"] and
                  (b["rail"] == rail or b.get("secondary") == rail) and mode_token(b["mode"]).replace("_", "") in
                  ("START", "EXPLICITCROSSFADE")]
        if others:
            r.append("P%s_RAIL_SHARED: rail %s also plays for %s" % (key, rail, [b["owner"] for b in others]))
            continue
        plan[key] = {"rail": rail, "mode_before": mode, "set_start": set_start}
    return plan, r


def rail_targets(rail_before, new_sound, new_duration_s, tick_rate, source_out_policy, analysis_map_policy):
    """The rail fields APPLY writes (pure). Unchanged fields are not listed."""
    out = {"sound": new_sound}
    if source_out_policy == "new_duration" and int(rail_before.get("source_out", 0)) > 0:
        out["source_out"] = int(round(float(new_duration_s) * float(tick_rate)))
        if out["source_out"] <= int(rail_before.get("source_in", 0)):
            raise PlanError("SOURCE_OUT_NOT_AFTER_SOURCE_IN")    # InfinityStageCompiler.cpp:192-195
    if analysis_map_policy == "unlink" and rail_before.get("analysis_map"):
        out["analysis_map"] = None
    return out


RAIL_FIELDS = ("sound", "source_in", "source_out", "fade_in", "fade_out", "analysis_map", "label")


def rail_descriptor(state):
    return {k: state.get(k) for k in RAIL_FIELDS}


def swap_rails(show, plan, targets):
    """Write targets through an adapter (live or fake) and judge by re-reading. Returns failures."""
    failures = []
    for key in sorted(plan):
        guid = plan[key]["rail"]
        show.write_rail(guid, targets[key])
        if plan[key]["set_start"]:
            show.write_mode(key, "START")
    rails = show.read_rails()
    modes = show.read_modes()
    for key in sorted(plan):
        live = rails.get(plan[key]["rail"]) or {}
        for field, want in targets[key].items():
            if live.get(field) != want:
                failures.append("P%s READBACK_%s: %r != %r" % (key, field.upper(), live.get(field), want))
        if plan[key]["set_start"] and mode_token(modes.get(key)) != "START":
            failures.append("P%s READBACK_MODE: %r" % (key, modes.get(key)))
    return failures


def drift_since_apply(show, record):
    """Failures if any recorded rail/mode no longer equals what APPLY wrote (someone edited since)."""
    out = []
    rails, modes = show.read_rails(), show.read_modes()
    for key, row in sorted(record["passages"].items()):
        live = rail_descriptor(rails.get(row["rail"]) or {})
        if live != row["rail_after"]:
            out.append("P%s RAIL_CHANGED_SINCE_APPLY: %r" % (key, {k: (live.get(k), row["rail_after"].get(k))
                                                                 for k in RAIL_FIELDS
                                                                 if live.get(k) != row["rail_after"].get(k)}))
        if mode_token(modes.get(key)) != mode_token(row["mode_after"]):
            out.append("P%s MODE_CHANGED_SINCE_APPLY: %r" % (key, modes.get(key)))
    return out


def restore_rails(show, record):
    """REVERT: write every recorded field back exactly, then judge by re-reading. Returns failures."""
    drift = drift_since_apply(show, record)
    if drift:
        return ["STATE_DRIFTED: " + d for d in drift]
    for key, row in sorted(record["passages"].items()):
        before = row["rail_before"]
        show.write_rail(row["rail"], {k: before[k] for k in RAIL_FIELDS if k != "label" and
                                      before[k] != row["rail_after"][k]})
        if mode_token(row["mode_before"]) != mode_token(row["mode_after"]):
            show.write_mode(key, mode_token(row["mode_before"]))
    rails, modes = show.read_rails(), show.read_modes()
    out = []
    for key, row in sorted(record["passages"].items()):
        if rail_descriptor(rails.get(row["rail"]) or {}) != row["rail_before"]:
            out.append("P%s REVERT_RAIL_NOT_EXACT" % key)
        if mode_token(modes.get(key)) != mode_token(row["mode_before"]):
            out.append("P%s REVERT_MODE_NOT_EXACT" % key)
    return out


def live_gates(state):
    """Refusals from editor state (pure)."""
    r = []
    mode = str(state.get("mode") or "").upper()
    if mode not in ("DRY", "APPLY", "REVERT"):
        r.append("MODE_INVALID: %r" % state.get("mode"))
    if state.get("confirm") != "%s WALKING MUSIC" % mode:
        r.append("CONFIRM_MISMATCH: %r, want %r" % (state.get("confirm"), "%s WALKING MUSIC" % mode))
    if state.get("pie"):
        r.append("PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if state.get("sequencer_open"):
        r.append("SEQUENCER_IS_OPEN (an open Sequencer evaluates and dirties the map)")
    census = state.get("census") or {}
    if census.get("content") or census.get("maps"):
        r.append("DIRTY_CENSUS: %s" % json.dumps(census, sort_keys=True))
    if mode == "APPLY":
        if state.get("overlapping_records"):
            r.append("RECORD_COVERS_TARGET: %s (REVERT that set first)" % state["overlapping_records"])
        if not str(state.get("decided_by") or "").strip():
            r.append("NOT_DECIDED: args decided_by is empty")
        if not str(state.get("mapping_confirmed_by") or "").strip():
            r.append("MAPPING_NOT_CONFIRMED: args mapping_confirmed_by is empty")
        if state.get("assets_exist"):
            r.append("ASSET_EXISTS: %s" % ", ".join(state["assets_exist"]))
    if mode == "REVERT" and not state.get("record_applied"):
        r.append("NO_APPLIED_RECORD for this passage set")
    return r


def census_gate(census, expected_content):
    out = []
    got, want = sorted(census.get("content") or []), sorted(expected_content)
    if not set(got) <= set(want):
        out.append("UNEXPECTED_DIRTY: %s" % sorted(set(got) - set(want)))
    if census.get("maps"):
        out.append("MAP_DIRTY: %s" % census["maps"])
    return out


def record_name(targets):
    return RECORD_PREFIX + "-".join("P%02d" % int(t) for t in sorted(targets, key=int)) + ".json"


def records_covering(folder, targets):
    """Live (non-archived) record files whose passage set overlaps targets."""
    hits = []
    want = set("P%02d" % int(t) for t in targets)
    for name in sorted(os.listdir(folder)):
        if name.startswith(RECORD_PREFIX) and name.endswith(".json"):
            got = set(name[len(RECORD_PREFIX):-5].split("-"))
            if got & want:
                hits.append(name)
    return hits


def write_record_exclusive(path, data):
    """Create-only, fsynced BEFORE any mutation [prec scene_narration_standin.py:374-380]."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def update_record(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def sound_paths(args, keys=PASSAGE_KEYS):
    folder = args["dest_folder"].rstrip("/")
    return {k: "%s/%s" % (folder, args["passages"][k]["asset_name"]) for k in keys}


_PATH_RX = re.compile(r"(/Game/[A-Za-z0-9_/\-]+)(?:\.[A-Za-z0-9_\-]+)?")


def soft_path_from_export(text, field):
    """Package path of a soft-object field in a struct's export_text, or None ('None'/empty). [inf: UE T3D struct text
    writes Field=/Game/P.O or Field="/Script/Cls'/Game/P.O'"; harness covers both + None]."""
    m = re.search(r"(?:^|[,(])%s=(\"[^\"]*\"|[^,)]*)" % re.escape(field), str(text))
    if not m:
        return None
    hit = _PATH_RX.search(m.group(1))
    return hit.group(1) if hit else None


def stale_report(key, facts, new_song_s, fit_row):
    """Per-Passage list of music-driven things the swap leaves stale (DRY). facts: plain data from _gather."""
    items = []
    ch = facts.get("choreo") or {}
    items.append({"item": "choreo_song_markers", "stale": bool(ch.get("song_markers")),
                  "detail": "%s: %d song markers ('bar'/'§') of %d marked frames, placed from the OLD analysis "
                            "(choreo_tool.py:89-122)" % (ch.get("path"), ch.get("song_markers", 0), ch.get("marks", 0))
                  if ch.get("path") else "no Choreography sequence"})
    am = facts.get("analysis_map") or {}
    items.append({"item": "analysis_map", "stale": bool(am.get("path")),
                  "detail": "%s describes %s (%.3f s; %d confirmed markers); new song %.3f s" % (
                      am.get("path"), am.get("source_filename"), am.get("duration_s") or 0.0,
                      am.get("confirmed", 0), new_song_s) if am.get("path") else "no MusicMap linked"})
    pins = facts.get("pinned_frames", 0)
    items.append({"item": "camera_anchors_pinned_frames", "stale": pins > 0,
                  "detail": "%d PinnedPassageFrames (Pin Confirmed Music Markers writes these; hand pins look the "
                            "same)" % pins})
    keyed = facts.get("keyed_channels") or {}
    items.append({"item": "camera_channel_keys_candidates", "stale": bool(keyed),
                  "detail": "keyed Passage camera channels %r (Apply Music Analysis Curve writes Wing/Speed "
                            "channels; origin not provable)" % keyed})
    items.append({"item": "refit_from_music", "stale": False,
                  "detail": "DO NOT REFIT: it would size the wing count for %.3f s instead of the kept %.3f s" % (
                      facts.get("refit_duration_s_after") or new_song_s, fit_row["passage_s"])})
    items.append({"item": "source_fingerprint", "stale": bool(facts.get("rail", {}).get("fingerprint")),
                  "detail": "rail SourceFingerprint is read-only to Python and read by nothing (cosmetic)"})
    items.append({"item": "light_drama_and_lighting_scores", "stale": False,
                  "detail": "distance-driven (InfinityStageLightDrama.h:24-26); Passage lengths unchanged"})
    return items


# =====================================================================================================================
# Live (Unreal) side. Every unreal handle is a local or an adapter attribute.
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _project():
    if unreal is not None:
        return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.dirname(os.path.dirname(_here()))


def _stop(run, reason):
    unreal.log_error("WALKING_MUSIC_STOPPED|run=%s|reason=%s" % (run, reason))
    raise RuntimeError(reason)


def _census():
    return {"content": sorted(p.get_path_name().split(".")[0]
                              for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
            "maps": sorted(p.get_path_name().split(".")[0]
                           for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())}


def _guid(value):
    return unreal.GuidLibrary.conv_guid_to_string(value)


def _path(obj):
    return obj.get_path_name().split(".")[0] if obj is not None else None


def _content_file(path):
    return os.path.join(_project(), "Content", *path[len("/Game/"):].split("/")) + ".uasset"


def _soft(struct, field, prop):
    """(path, loaded object) of a soft field: the property value first; if None, the export text path, loaded."""
    obj = struct.get_editor_property(prop)
    if obj is not None and hasattr(obj, "load_synchronous"):    # choreo_tool.py:96-98
        obj = obj.load_synchronous()
    text = struct.export_text() if hasattr(struct, "export_text") else str(struct)
    path = soft_path_from_export(text, field)
    if obj is None and path:
        obj = unreal.load_asset(path)
    if obj is not None and path and _path(obj) != path:
        raise RuntimeError("SOFT_PATH_DISAGREES: %s %s vs %s" % (field, _path(obj), path))
    return (_path(obj) if obj is not None else path), obj


class _LiveShow(object):
    """Adapter over the Show's music rails + Passage music modes (same interface as the harness fake)."""

    def __init__(self, show, passage_index):
        self.show = show
        self.passage_index = passage_index        # {"1": index into passage_settings}
        tick = show.get_editor_property("tick_resolution")
        self.tick_rate = float(tick.numerator) / float(tick.denominator)

    def _state(self, r):
        sound, _ = _soft(r, "Sound", "sound")
        amap, _ = _soft(r, "AnalysisMap", "analysis_map")
        return {"guid": _guid(r.get_editor_property("rail_guid")), "label": str(r.get_editor_property("label")),
                "sound": sound, "source_in": int(r.get_editor_property("source_in_frame").value),
                "source_out": int(r.get_editor_property("source_out_frame").value),
                "fade_in": int(r.get_editor_property("fade_in_frames").value),
                "fade_out": int(r.get_editor_property("fade_out_frames").value),
                "analysis_map": amap, "fingerprint": str(r.get_editor_property("source_fingerprint"))}

    def read_rails(self):
        return {s["guid"]: s for s in (self._state(r) for r in self.show.get_editor_property("music_rails"))}

    def read_modes(self):
        ps = list(self.show.get_editor_property("passage_settings"))
        return {k: str(ps[i].get_editor_property("music").get_editor_property("mode"))
                for k, i in self.passage_index.items()}

    def write_rail(self, guid, fields):
        rails = list(self.show.get_editor_property("music_rails"))
        idx = [i for i, r in enumerate(rails) if _guid(r.get_editor_property("rail_guid")) == guid]
        if len(idx) != 1:
            raise RuntimeError("RAIL_COUNT %s %d" % (guid, len(idx)))
        r = rails[idx[0]]
        for field, value in fields.items():
            if field == "sound":
                obj = unreal.load_asset(value) if value else None
                if value and not isinstance(obj, unreal.SoundBase):
                    raise RuntimeError("SOUND_NOT_LOADED %s" % value)
                r.set_editor_property("sound", obj)
            elif field == "analysis_map":
                r.set_editor_property("analysis_map", unreal.load_asset(value) if value else None)
            elif field in ("source_in", "source_out", "fade_in", "fade_out"):
                prop = {"source_in": "source_in_frame", "source_out": "source_out_frame", "fade_in": "fade_in_frames",
                        "fade_out": "fade_out_frames"}[field]
                r.set_editor_property(prop, unreal.FrameNumber(int(value)))
            else:
                raise RuntimeError("FIELD_NOT_WRITABLE %s" % field)
        rails[idx[0]] = r
        self.show.set_editor_property("music_rails", rails)     # struct arrays are copies: write the array back

    def write_mode(self, key, mode):
        ps = list(self.show.get_editor_property("passage_settings"))
        p = ps[self.passage_index[key]]
        m = p.get_editor_property("music")
        m.set_editor_property("mode", getattr(unreal.InfinityMusicBindingMode, mode))
        p.set_editor_property("music", m)
        ps[self.passage_index[key]] = p
        self.show.set_editor_property("passage_settings", ps)    # opening_sequence_apply.py:611-631


def _segments(show):
    """Compiled segments via a transient transport [prec rebuild_managed_master_guarded.py:38-42]; ticks."""
    tr = unreal.new_object(unreal.InfinityStageTransportController)
    tr.build_segments(show)
    return [{"label": str(s.get_editor_property("label")), "start": int(s.get_editor_property("start_frame").value),
             "end": int(s.get_editor_property("end_frame").value)} for s in tr.get_editor_property("segments")]


def _bindings(show):
    """Every enabled music binding: Passages by label, Scene/Sequence cues by label."""
    out = []
    for p in show.get_editor_property("passage_settings"):
        m = p.get_editor_property("music")
        out.append({"owner": str(p.get_editor_property("label")), "mode": str(m.get_editor_property("mode")),
                    "rail": _guid(m.get_editor_property("primary_rail_guid")),
                    "secondary": _guid(m.get_editor_property("secondary_rail_guid"))})
    for c in show.get_editor_property("cues"):
        if not c.get_editor_property("enabled") or c.get_editor_property("type") == unreal.InfinityCueType.WING_PAIR:
            continue
        m = c.get_editor_property("scene").get_editor_property("music")
        out.append({"owner": "cue:" + str(c.get_editor_property("label")), "mode": str(m.get_editor_property("mode")),
                    "rail": _guid(m.get_editor_property("primary_rail_guid")),
                    "secondary": _guid(m.get_editor_property("secondary_rail_guid"))})
    return out


def _master_rows(master):
    """Managed music sections and Passage camera sections of the Master, by block GUID (read-only)."""
    music, passage = {}, {}
    for track in master.get_tracks():
        cls = track.get_class().get_name()
        for sec in track.get_sections():
            if cls == "MovieSceneInfinityAudioTrack":
                music[_guid(sec.get_editor_property("block_guid"))] = {
                    "sound": _path(sec.get_sound()), "range_s": [round(sec.get_start_frame_seconds(), 4),
                                                                 round(sec.get_end_frame_seconds(), 4)],
                    "looping": bool(sec.get_looping()),
                    "play_until_finished": bool(sec.get_play_until_finished())
                    if hasattr(sec, "get_play_until_finished") else None}
            elif cls == "MovieSceneInfinityPassageTrack":
                keyed = {}
                for ch in sec.get_all_channels():
                    n = len(ch.get_keys())
                    if n:
                        keyed[str(ch.get_editor_property("channel_name"))] = n
                passage[_guid(sec.get_editor_property("block_guid"))] = {
                    "pinned_frames": len(sec.get_editor_property("pinned_passage_frames")), "keyed_channels": keyed,
                    "range_s": [sec.get_start_frame_seconds(), sec.get_end_frame_seconds()]}
    return music, passage


def _label_rows(master, segments, tick, guid_by_label):
    """(show_rows, master_rows, passage_ranges) keyed by segment label, seconds. Sequence segments pair with the
    Master's sub-track sections in start order [prec rebuild_managed_master_guarded.py:44-55]; Passage segments with
    the Passage track section whose block GUID is that Passage's GUID [prec choreo_tool.py:80-86]."""
    show_rows = {s["label"]: [s["start"] / tick, s["end"] / tick] for s in segments}
    secs = []
    # EXACT type: the Choreo track is also a MovieSceneSubTrack [decl MovieSceneInfinityChoreoTrack.h:32] and
    # find_tracks_by_type matches subclasses [decl MovieSceneSequenceExtensions.h:55-69], so the guarded script's
    # compare() (:44) would now pair Choreo sections with sequence segments.
    for track in master.find_tracks_by_exact_type(unreal.MovieSceneInfinitySceneTrack):
        for sec in track.get_sections():
            secs.append([sec.get_start_frame_seconds(), sec.get_end_frame_seconds()])
    secs.sort()
    seq_labels = [s["label"] for s in sorted(segments, key=lambda x: x["start"]) if not s["label"].startswith("Passage")]
    master_rows = dict(zip(seq_labels, secs))
    _m, passage = _master_rows(master)
    ranges = {}
    for label, guid in guid_by_label.items():
        if guid in passage:
            ranges[label] = passage[guid]["range_s"]
            master_rows[label] = passage[guid]["range_s"]
    if len(secs) != len(seq_labels):
        master_rows["<sub-section count %d vs %d sequence segments>" % (len(secs), len(seq_labels))] = [0.0, 0.0]
    return show_rows, master_rows, ranges


def _choreo(settings):
    seq = settings.get_editor_property("choreography")
    if seq is not None and hasattr(seq, "load_synchronous"):
        seq = seq.load_synchronous()
    if seq is None:
        return {}
    labels = [str(m.get_editor_property("label")) for m in seq.get_marked_frames()]
    return {"path": _path(seq), "marks": len(labels),
            "song_markers": sum(1 for l in labels if l.startswith(CHOREO_SONG_PREFIXES))}


def _map_facts(path):
    if not path:
        return {}
    m = unreal.load_asset(path)
    if m is None:
        return {"path": path, "error": "did not load"}
    confirmed = 0
    for field in ("beat_proposals", "onset_proposals", "major_change_proposals"):
        confirmed += sum(1 for x in m.get_editor_property(field)
                         if x.get_editor_property("state") == unreal.InfinityMusicProposalState.CONFIRMED)
    return {"path": path, "source_filename": str(m.get_editor_property("source_filename")),
            "duration_s": float(m.get_editor_property("duration_seconds")), "confirmed": confirmed}


def _gather(args, run):
    """All live facts as plain data + the plan (read-only)."""
    project = _project()
    inputs, refusals = check_inputs(args, project)
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    if show is None or master is None:
        raise PlanError("SHOW_OR_MASTER_DID_NOT_LOAD")
    psets = list(show.get_editor_property("passage_settings"))
    index, passages, warnings = {}, {}, []
    for key in PASSAGE_KEYS:
        hits = [i for i, p in enumerate(psets) if str(p.get_editor_property("label")) == "Passage %s" % key]
        if len(hits) != 1:
            refusals.append("P%s_LABEL_COUNT: %d rows labelled 'Passage %s'" % (key, len(hits), key))
            continue
        index[key] = hits[0]
        p = psets[hits[0]]
        m = p.get_editor_property("music")
        passages[key] = {"label": "Passage %s" % key, "guid": _guid(p.get_editor_property("passage_guid")),
                         "mode": str(m.get_editor_property("mode")),
                         "rail": _guid(m.get_editor_property("primary_rail_guid")),
                         "offset": int(m.get_editor_property("rail_offset_frames").value),
                         "choreo": _choreo(p)}
    adapter = _LiveShow(show, index)
    rails = adapter.read_rails()
    segments = _segments(show)
    segs, dup = segment_rows(segments)
    if dup:
        refusals.append("SEGMENT_LABELS_DUPLICATED: %r" % dup)
    music_rows, passage_rows = _master_rows(master)
    guid_by_label = {p["label"]: p["guid"] for p in passages.values()}
    show_rows, master_rows, passage_ranges = _label_rows(master, segments, adapter.tick_rate, guid_by_label)
    refusals += sync_gate(show_rows, master_rows)
    targets = [str(t) for t in args["apply_passages"]]
    plan, plan_refusals = rail_plan(passages, _bindings(show), rails, targets, args.get("silence_policy", "refuse"))
    refusals += plan_refusals
    tick = adapter.tick_rate
    rows = {}
    for key in PASSAGE_KEYS:
        if key not in passages or key not in inputs:
            continue
        p, rail = passages[key], rails.get(passages[key]["rail"]) or {}
        seg = segs.get(p["label"])
        if seg is None:
            refusals.append("P%s_NO_SEGMENT" % key)
            continue
        passage_s = (seg[1] - seg[0]) / tick
        new_s = inputs[key]["duration_s"]
        old_sound = rail.get("sound")
        old_obj = unreal.load_asset(old_sound) if old_sound else None
        old_s = float(old_obj.get_editor_property("duration")) if old_obj is not None else None   # SoundBase.h:200-202
        f_new = fit(passage_s, new_s, rail.get("source_in", 0) / tick, p["offset"] / tick,
                    rail.get("fade_in", 0) / tick, rail.get("fade_out", 0) / tick)
        f_old = fit(passage_s, old_s, rail.get("source_in", 0) / tick, p["offset"] / tick,
                    rail.get("fade_in", 0) / tick, rail.get("fade_out", 0) / tick) if old_s else None
        facts = {"choreo": p["choreo"], "analysis_map": _map_facts(rail.get("analysis_map")), "rail": rail,
                 "pinned_frames": (passage_rows.get(p["guid"]) or {}).get("pinned_frames", 0),
                 "keyed_channels": (passage_rows.get(p["guid"]) or {}).get("keyed_channels", {}),
                 "refit_duration_s_after": (new_s if args.get("source_out_policy", "new_duration") == "new_duration"
                                            and rail.get("source_out", 0) > 0 else
                                            (rail.get("source_out", 0) - rail.get("source_in", 0)) / tick
                                            if rail.get("source_out", 0) > 0 else
                                            (_map_facts(rail.get("analysis_map")) or {}).get("duration_s"))}
        rows[key] = {"passage": p, "segment_ticks": seg, "passage_s": round(passage_s, 6), "rail": rail,
                     "old_sound": old_sound, "old_sound_s": old_s, "new_wav": args["passages"][key]["wav"],
                     "new_sound": sound_paths(args)[key], "new_s": new_s, "pad": args["passages"][key].get("pad"),
                     "fit_new": f_new, "fit_old": f_old,
                     "master_music_section": music_rows.get(p["guid"]),
                     "target": key in targets, "planned": plan.get(key),
                     "stale": stale_report(key, facts, new_s, f_new)}
        if not f_new["fits"]:
            warnings.append("P%s OVERRUN: new song %.3f s plays %.3f s past the kept Passage (%.3f s): cut, %s" % (
                key, new_s, f_new["overrun_s"], passage_s, f_new["fade_out"]))
        if args["passages"][key].get("pad"):
            warnings.append("P%s PADDED: %s = unpadded + %.2f s digital silence (%s); Cameron's real version replaces it"
                            % (key, args["passages"][key]["wav"], float(args["passages"][key]["pad"]["pad_s"]),
                               args["passages"][key]["pad"]["decided_by"]))
        if music_rows.get(p["guid"]) and music_rows[p["guid"]].get("play_until_finished"):
            warnings.append("P%s PLAY_UNTIL_FINISHED_SET on the Master section (song may run past the Passage)" % key)
        warnings.append("P%s REFIT_FORBIDDEN: Refit from Music would derive a wing count for %s s; never run" % (
            key, facts["refit_duration_s_after"]))
    return {"inputs": inputs, "rows": rows, "plan": plan, "refusals": refusals, "warnings": warnings,
            "segments": segments, "tick_rate": tick, "index": index, "guid_by_label": guid_by_label,
            "show_rows": show_rows, "master_rows": master_rows, "passage_ranges": passage_ranges}, show, master, adapter


def _backup(run, suffix, paths):
    folder = os.path.join(_project(), "Backups", "PreWalkingMusic%s-%s" % (suffix, run))
    os.makedirs(folder, exist_ok=False)
    manifest = []
    for path in paths:
        src = _content_file(path)
        dst = os.path.join(folder, os.path.basename(src))
        shutil.copy2(src, dst)
        digest = [hashlib.sha256(open(x, "rb").read()).hexdigest() for x in (src, dst)]
        if digest[0] != digest[1]:
            _stop(run, "BACKUP_HASH_MISMATCH|" + src)
        manifest.append({"asset": path, "source": src, "backup": dst, "sha256": digest[1]})
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as handle:
        json.dump({"run": run, "files": manifest}, handle, indent=1)
    return folder


def _import_sounds(args, inputs, keys):
    tasks = []
    for key in keys:
        task = unreal.AssetImportTask()                     # scene_narration_standin.py:739-747 [prec]
        task.set_editor_property("filename", inputs[key]["path"])
        task.set_editor_property("destination_path", args["dest_folder"])
        task.set_editor_property("destination_name", args["passages"][key]["asset_name"])
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", False)
        task.set_editor_property("save", False)
        tasks.append(task)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    failures = []
    for key in keys:
        path = sound_paths(args)[key]
        s = unreal.load_asset(path)
        if not isinstance(s, unreal.SoundWave):
            failures.append("P%s IMPORT_NOT_SOUNDWAVE: %s" % (key, path))
            continue
        dur = float(s.get_editor_property("duration"))
        if abs(dur - inputs[key]["duration_s"]) > DURATION_TOL_S:
            failures.append("P%s IMPORT_DURATION: %.4f vs WAV %.4f" % (key, dur, inputs[key]["duration_s"]))
        if bool(s.get_editor_property("looping")):
            failures.append("P%s IMPORTED_LOOPING (IsSoundLoopingAsset would loop it)" % key)
    return failures


def _master_check(master, plan, rows, args):
    music, _ = _master_rows(master)
    out = []
    for key in plan:
        sec = music.get(rows[key]["passage"]["guid"])
        if sec is None or sec["sound"] != sound_paths(args)[key]:
            out.append("P%s MASTER_MUSIC_SECTION: %r" % (key, sec))
    return out


def run_dry(args, run):
    g, _s, _m, _a = _gather(args, run)
    # 5 Oct: only the TARGETED passages' new sounds must be absent (P02-P05 were imported in an earlier run)
    targets = {str(t) for t in args.get("apply_passages", [])}
    existing = [p for k, p in sound_paths(args).items()
                if str(int(str(k).lstrip("P"))) in targets and unreal.EditorAssetLibrary.does_asset_exist(p)]
    if existing:
        g["refusals"].append("ASSET_EXISTS: %s" % existing)
    report = {"tool": TOOL, "run": run, "mode": "DRY", "args": args, "apply_ready": not g["refusals"],
              "rows": g["rows"], "plan": g["plan"], "refusals": g["refusals"], "warnings": g["warnings"],
              "segments": g["segments"], "tick_rate": g["tick_rate"], "inputs": g["inputs"]}
    out = os.path.join(_here(), DRY_NAME)
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, sort_keys=True, default=str, ensure_ascii=False)
    for text in g["refusals"]:
        unreal.log_warning("WALKING_MUSIC_REFUSAL|run=%s|%s" % (run, text))
    for text in g["warnings"]:
        unreal.log("WALKING_MUSIC_WARNING|run=%s|%s" % (run, text))
    for key, row in sorted(g["rows"].items()):
        f = row["fit_new"]
        unreal.log("WALKING_MUSIC_ROW|run=%s|P%s|old=%s(%.3fs)|new=%s(%.3fs)|passage=%.3fs|fits=%d|overrun=%.3fs|"
                   "silence_tail=%.3fs|fade_out=%s|stale=%s|target=%d"
                   % (run, key, row["old_sound"], row["old_sound_s"] or -1, row["new_sound"], row["new_s"],
                      row["passage_s"], int(f["fits"]), f["overrun_s"], f["silence_tail_s"], f["fade_out"],
                      ",".join(i["item"] for i in row["stale"] if i["stale"]) or "none", int(row["target"])))
    if _census() != {"content": [], "maps": []}:
        _stop(run, "DRY_DIRTIED|" + json.dumps(_census()))
    unreal.log("WALKING_MUSIC_DRY_OK|run=%s|mutated=0|apply_ready=%d|refusals=%d|warnings=%d|targets=%s|report=%s"
               % (run, int(not g["refusals"]), len(g["refusals"]), len(g["warnings"]),
                  ",".join(args["apply_passages"]), out))


def run_apply(args, run):
    g, show, master, adapter = _gather(args, run)
    targets = [str(t) for t in args["apply_passages"]]
    if g["refusals"]:
        _stop(run, "PLAN_REFUSED|" + " || ".join(g["refusals"]))
    if sorted(g["plan"]) != sorted(targets):
        _stop(run, "PLAN_INCOMPLETE|%s" % sorted(g["plan"]))
    record_path = os.path.join(_here(), record_name(targets))
    backup = _backup(run, "", [SHOW_PATH, MASTER_PATH])
    unreal.log("WALKING_MUSIC_BACKUP_OK|run=%s|backup=%s" % (run, backup))
    tick = g["tick_rate"]
    rails_before = adapter.read_rails()
    modes_before = adapter.read_modes()
    targets_fields = {}
    for k in targets:
        rb = rails_before[g["plan"][k]["rail"]]
        targets_fields[k] = rail_targets(rb, sound_paths(args)[k], g["inputs"][k]["duration_s"], tick,
                                         args.get("source_out_policy", "new_duration"),
                                         args.get("analysis_map_policy", "keep"))
    record = {"schema": 1, "tool": TOOL, "run": run, "world": EXPECTED_WORLD, "backup": backup, "args": args,
              "decided_by": args.get("decided_by"), "mapping_confirmed_by": args.get("mapping_confirmed_by"),
              "applied": False, "sounds_imported": False,
              "written": datetime.datetime.now().isoformat(timespec="seconds"),
              "segments_before": g["segments"],
              "passages": {k: {"rail": g["plan"][k]["rail"], "rail_before": rail_descriptor(rails_before[g["plan"][k]["rail"]]),
                               "rail_after": dict(rail_descriptor(rails_before[g["plan"][k]["rail"]]), **targets_fields[k]),
                               "mode_before": modes_before[k],
                               "mode_after": "START" if g["plan"][k]["set_start"] else modes_before[k],
                               "fingerprint_before": rails_before[g["plan"][k]["rail"]].get("fingerprint"),
                               "import": {"wav": args["passages"][k]["wav"], "sha256": g["inputs"][k]["sha256"],
                                          "duration_s": g["inputs"][k]["duration_s"], "asset": sound_paths(args)[k],
                                          "pad": (dict(args["passages"][k]["pad"],
                                                       unpadded_measured=g["inputs"][k].get("unpadded"))
                                                  if args["passages"][k].get("pad") else None)},
                               "fit": g["rows"][k]["fit_new"]} for k in targets}}
    write_record_exclusive(record_path, record)                  # BEFORE any change, including the import
    failures = _import_sounds(args, g["inputs"], targets)
    record["sounds_imported"] = True
    update_record(record_path, record)
    if not failures:
        show.modify()
        try:
            failures += swap_rails(adapter, g["plan"], targets_fields)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            failures.append("WRITE_RAISED: %r" % exc)
    if not failures:
        result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)   # guarded.py:89
        record["rebuild_result"] = str(result)
        if result is False or result is None:
            failures.append("REBUILD_RETURNED %r" % (result,))
        failures += length_gate(g["segments"], _segments(show))
        failures += section_gate(g["passage_ranges"], _label_rows(master, g["segments"], tick, g["guid_by_label"])[2])
        failures += _master_check(master, g["plan"], g["rows"], args)
    expected = [SHOW_PATH, MASTER_PATH] + [sound_paths(args)[k] for k in targets]
    failures += census_gate(_census(), expected)
    if failures:
        update_record(record_path, dict(record, applied=False, failed=failures))
        os.rename(record_path, record_path + ".failed-" + run)
        _stop(run, "APPLY_GATES|%r|NOTHING SAVED; Don't-Save restart (Show/Master/imports unsaved in memory); "
              "backup %s" % (failures[:10], backup))
    for path in expected:
        if path in _census()["content"] or path in [sound_paths(args)[k] for k in targets]:
            if not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
                _stop(run, "SAVE_FAILED|%s|record=%s (REVERT or restore %s)" % (path, record_path, backup))
    show2, master2 = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    dd = drift_since_apply(_LiveShow(show2, g["index"]), record)
    dd += length_gate(g["segments"], _segments(show2))
    dd += section_gate(g["passage_ranges"], _label_rows(master2, g["segments"], tick, g["guid_by_label"])[2])
    dd += _master_check(master2, g["plan"], g["rows"], args)
    for k in targets:
        if not os.path.isfile(_content_file(sound_paths(args)[k])):
            dd.append("P%s SOUND_FILE_NOT_ON_DISK" % k)
    if _census() != {"content": [], "maps": []}:
        dd.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    record["applied"] = True
    if dd:
        record["post_save_readback_failed"] = dd
        update_record(record_path, record)
        _stop(run, "POST_SAVE_READBACK|%r|record kept (REVERT or restore %s)" % (dd[:8], backup))
    update_record(record_path, record)
    over = ",".join("P%s:+%.3fs" % (k, g["rows"][k]["fit_new"]["overrun_s"]) for k in targets
                    if not g["rows"][k]["fit_new"]["fits"]) or "none"
    unreal.log("WALKING_MUSIC_APPLY_OK|run=%s|passages=%s|overruns=%s|lengths=unchanged|backup=%s|record=%s|decided_by=%s"
               % (run, ",".join("P%s" % k for k in targets), over, backup, record_path, args.get("decided_by")))


def run_revert(args, run):
    targets = [str(t) for t in args["apply_passages"]]
    record_path = os.path.join(_here(), record_name(targets))
    with open(record_path, "r", encoding="utf-8") as handle:
        record = json.load(handle)
    if record.get("world") != EXPECTED_WORLD or not record.get("applied"):
        _stop(run, "REVERT_RECORD_CONTEXT")
    show, master = unreal.load_asset(SHOW_PATH), unreal.load_asset(MASTER_PATH)
    psets = list(show.get_editor_property("passage_settings"))
    index = {}
    for k in record["passages"]:
        hits = [i for i, p in enumerate(psets) if str(p.get_editor_property("label")) == "Passage %s" % k]
        if len(hits) != 1:
            _stop(run, "REVERT_PASSAGE_LABEL|P%s %d" % (k, len(hits)))
        index[k] = hits[0]
    adapter = _LiveShow(show, index)
    drift = drift_since_apply(adapter, record)
    if drift:
        _stop(run, "STATE_DRIFTED_SINCE_APPLY|%r (restore from %s instead)" % (drift[:8], record["backup"]))
    seg0 = _segments(show)
    tick = adapter.tick_rate
    gbl = {"Passage %s" % k: _guid(psets[i].get_editor_property("passage_guid")) for k, i in index.items()}
    show_rows, master_rows, ranges0 = _label_rows(master, seg0, tick, gbl)
    stale = sync_gate(show_rows, master_rows)
    if stale:
        _stop(run, "MASTER_NOT_IN_SYNC_BEFORE_REVERT|%r (run the guarded rebuild first)" % stale[:6])
    backup = _backup(run, "Revert", [SHOW_PATH, MASTER_PATH])
    show.modify()
    errs = restore_rails(adapter, record)
    if not errs:
        result = unreal.InfinityStageSequenceBuilderLibrary.rebuild_managed_master(show, master)
        if result is False or result is None:
            errs.append("REBUILD_RETURNED %r" % (result,))
        errs += length_gate(seg0, _segments(show))
        errs += section_gate(ranges0, _label_rows(master, seg0, tick, gbl)[2])
        music, _ = _master_rows(master)
        for k, row in record["passages"].items():
            guid = _guid(psets[index[k]].get_editor_property("passage_guid"))
            sec = music.get(guid)
            want = row["rail_before"]["sound"] if mode_token(row["mode_before"]) == "START" else None
            got = sec["sound"] if sec else None
            if got != want:
                errs.append("P%s MASTER_SECTION_SOUND %r != %r" % (k, got, want))
    errs += census_gate(_census(), [SHOW_PATH, MASTER_PATH])
    if errs:
        _stop(run, "REVERT_NOT_EXACT|%r|NOTHING SAVED; Don't-Save restart, then restore %s" % (errs[:8], record["backup"]))
    for path in (SHOW_PATH, MASTER_PATH):
        if path in _census()["content"] and not unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False):
            _stop(run, "SAVE_FAILED|%s" % path)
    final = []
    rails = _LiveShow(unreal.load_asset(SHOW_PATH), index).read_rails()
    for k, row in record["passages"].items():
        if rail_descriptor(rails.get(row["rail"]) or {}) != row["rail_before"]:
            final.append("P%s RAIL_NOT_AS_BEFORE" % k)
    if _census() != {"content": [], "maps": []}:
        final.append("DIRTY_AFTER_SAVE: %s" % json.dumps(_census()))
    if final:
        _stop(run, "REVERT_READBACK|%r|restore from %s" % (final, record["backup"]))
    deleted = []
    if args.get("delete_assets") is True:
        for k, row in sorted(record["passages"].items()):
            asset = row["import"]["asset"]
            refs = [str(r) for r in unreal.EditorAssetLibrary.find_package_referencers_for_asset(asset, False)]
            if refs:
                _stop(run, "DELETE_REFUSED_REFERENCED|%s|%s (rails already reverted and saved)" % (asset, refs))
            unreal.EditorAssetLibrary.delete_asset(asset)
            if unreal.EditorAssetLibrary.does_asset_exist(asset):
                _stop(run, "DELETE_FAILED|%s" % asset)
            deleted.append(asset)
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    unreal.log("WALKING_MUSIC_REVERT_OK|run=%s|passages=%s|sounds_deleted=%s|backup=%s|record=%s"
               % (run, ",".join("P%s" % k for k in sorted(record["passages"])), ",".join(deleted) or "kept", backup,
                  archived))


def main():
    g = globals()
    args = g.get("WALKING_ARGS")
    if args is None:
        with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
            args = json.load(handle)
    run = str(args.get("run_id") or datetime.datetime.now().strftime("WALK-%Y%m%d-%H%M%S"))
    mode = str(args.get("mode") or "").upper()
    bad = validate_args(args)
    if bad:
        _stop(run, "ARGS|" + " || ".join(bad))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    targets = [str(t) for t in args["apply_passages"]]
    rp = os.path.join(_here(), record_name(targets))
    applied = False
    if os.path.exists(rp):
        with open(rp, "r", encoding="utf-8") as handle:
            applied = bool(json.load(handle).get("applied"))
    state = {"mode": mode, "confirm": args.get("confirm"), "pie": editor.get_game_world() is not None,
             "sequencer_open": unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None,
             "census": _census(), "overlapping_records": records_covering(_here(), targets),
             "record_applied": applied, "decided_by": args.get("decided_by"),
             "mapping_confirmed_by": args.get("mapping_confirmed_by"),
             "assets_exist": [p for k, p in sound_paths(args, targets).items()
                              if unreal.EditorAssetLibrary.does_asset_exist(p)] if mode == "APPLY" else []}
    early = live_gates(state)
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        early.append("WRONG_WORLD")
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


if unreal is not None and not globals().get("WALKING_MUSIC_SWAP_IMPORT_ONLY"):
    main()
