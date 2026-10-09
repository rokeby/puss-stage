# P36 authored breath: insertion and retime report

Offline investigation, 9 October 2026. No Unreal Editor, MCP, PIE, build, Blender, asset mutation, or write to
`E:/PussStage` was performed.

Proof labels used on every finding:

- **PROVEN — declaration-proven**: stated by source, header, config, or tracked data at the cited lines.
- **PROVEN — measured**: an intervention or read-back exists at the cited lines/log.
- **INFERRED**: follows from declarations or maths but has not been exercised for this exact breath operation.
- **UNCLEAR**: the named search did not establish the saved/live state; the required check is stated.

## Answer

1. **PROVEN — declaration-proven.** A Passage has no independent duration field. Its duration is
   `LeadInFrames + sum(IntervalToNext) + TailFrames`; the compiler advances the global cursor to that end, so every
   later segment starts later. The fields are declared at
   `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:740-744,982-1001`, and the compile is at
   `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageCompiler.cpp:249-316`.
2. **INFERRED — derived design.** For a breath at interior Master frame **F**, add the exact insertion **D** to the
   one timing span containing F: `LeadInFrames` in the lead-in, the preceding Wing Pair's `IntervalToNext` between
   passes, or `TailFrames` in the tail. Do not add pairs or distance. The existing resize library changes pair count,
   fit mode, spacing/tail data and can extend route extent; that is a different operation
   (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStagePassageResizeLibrary.cpp:247-281,380-423`).
3. **PROVEN — declaration-proven.** A managed Master rebuild resets playback end to the new compiled Show end, moves
   later Passage sections with `MoveSection`, re-ranges Scene, Choreo and music sections, and rebuilds music envelopes
   (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:224-230,245-365,367-483,485-608`).
4. **PROVEN — measured.** The formerly held patch K is already integrated in current source. The builder carries every
   channel in a later Passage section with `MoveSection` before `SetRange`
   (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:300-309`), its regression test passed
   (`E:/PussStage/Saved/Logs/SuiteAfterBuild-20261007-Rerun2.log:3531`), and the wider retime test passed while loudly
   reporting the changed-Passage gap (`E:/PussStage/Saved/Logs/SuiteAfterBuild-20261007-Rerun2.log:3606-3612`).
   Patch K is therefore **not an unapplied prerequisite**.
   Its behaviour is a prerequisite and is present.
5. **PROVEN — measured.** Patch K does not solve an insertion *inside the Passage whose start stays fixed*: current
   keys remain at their old section-relative frames, a key can drift off its wing pass, and an out-of-range pin is
   dropped (`E:/PussStage/Saved/Logs/SuiteAfterBuild-20261007-Rerun2.log:3609-3612`; test assertions at
   `Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageRetimeTests.cpp:770-833`). An authored-breath
   **INFERRED — derived design.** An authored-breath tool must ripple the changed Passage's own keys/pins after F itself.

## Show timing and the camera stop

| Item | Verdict | Required operation |
|---|---|---|
| Passage length | **PROVEN — declaration-proven.** Compiler formula cited above. | **INFERRED — recommended.** Add D frames to exactly one containing timing span. All later compiled starts then gain D. |
| Route distance | **PROVEN — declaration-proven.** Distance is independently accumulated from lead/gaps/tail (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageCompiler.cpp:255-288`) and interpolated piecewise linearly (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageCompiler.cpp:380-410`). | **INFERRED — recommended.** Change no distance field; the extra time is not extra travel. |
| Camera stop | **PROVEN — declaration-proven.** Speed is non-negative, integrated, and normalized between pinned anchors; yaw/pitch are independent absolute-time channels (`Plugins/InfinityStage/Source/InfinityStage/Public/MovieSceneInfinityPassageTrack.h:98-115,158-209`; implementation `Plugins/InfinityStage/Source/InfinityStage/Private/MovieSceneInfinityPassageTrack.cpp:381-485`). | **INFERRED — recommended.** Author SpeedMultiplier 1→0 at F, hold 0 through F+D, return 1; author Gary's Yaw/Pitch look keys over that window. |
| Spatial anchors | **INFERRED — derived design.** The compiler span is linear and the rate integral is normalized over the chosen pin span (`Plugins/InfinityStage/Source/InfinityStage/Private/MovieSceneInfinityPassageTrack.cpp:381-471`). | **INFERRED — recommended.** Pin the *bounding linear-distance anchors*: the Wing cue before and after F, or automatic Passage start/end in lead/tail. With the timing span enlarged by D and its rate zero for D, the maths preserves speed outside the hold. Do **not** add breath-start/end frame pins: those frames resolve to different compiled distances. Add a transient numerical test before APPLY. |
| Existing changed-Passage score | **PROVEN — declaration-proven.** Keys are absolute Master frames; relative pins are culled, not re-fitted (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:280-309`). | **INFERRED — recommended.** Shift every pre-existing Passage-channel key at/after F by D, including camera and Wing modulation; shift every `PinnedPassageFrames` value at/after passage-relative F by D. Preserve `PinnedWingCueGuids`. Add breath keys only after the pre-state snapshot. |
| Wings and squeaks during hold | **PROVEN — declaration-proven.** Mechanisms evaluate from Master frame; phase integrates elapsed Master frames, and sound advance compares Master frames (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:1288-1323,1408-1418,1502-1542`). | **INFERRED — expected behaviour.** Leave mechanism clocks running. SpeedMultiplier stops route distance, not Master time. |
| Flicker/light drama during hold | **PROVEN — declaration-proven.** slow movement uses Show seconds while strike/flash use camera distance (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageLightDrama.cpp:24-59,62-93,104-127`); the actor passes Master-derived Show seconds (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:1843-1888`). | **INFERRED — expected behaviour.** Time-driven flicker/move continues; distance-driven strike/flash holds with the stopped camera. This matches “lights continue” only for time-driven modes, so DRY must list each active mode. |

## What a managed rebuild moves — and what it does not

| Holder after F | Verdict | Breath action |
|---|---|---|
| Later Passage camera and Wing-modulation keys | **PROVEN — measured.** Whole-section carry passed (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStagePassageKeyCarryTests.cpp:83-129`; `E:/PussStage/Saved/Logs/SuiteAfterBuild-20261007-Rerun2.log:3531`). | **INFERRED — recommended.** Rebuild moves them by D; read back every relative key/value numerically. No second manual shift. |
| Changed Passage camera/Wing keys | **PROVEN — measured.** Known gap (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageRetimeTests.cpp:770-833`; `E:/PussStage/Saved/Logs/SuiteAfterBuild-20261007-Rerun2.log:3609-3612`). | **INFERRED — recommended.** Manual ripple at/after F by D, then breath Speed/Yaw/Pitch keys. |
| Choreo in later Passages | **PROVEN — declaration-proven.** Outer sections move by GUID with the Passage (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:367-458`). | **INFERRED — recommended.** No inner edit; outer move carries local content. |
| Choreo in changed Passage | **INFERRED — derived risk.** Its outer start is unchanged and only its end grows; content past the child playback end is merely warned (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:424-475`). | **INFERRED — recommended.** Ripple child sections, channel keys and marked frames at/after local F by D; extend child playback end. Refuse unknown/infinite/straddling constructs rather than guessing. |
| Managed Scene/Sequence sections and Klara Scene work | **PROVEN — declaration-proven.** Scene assets are nested at compiled segment ranges (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:329-365`); Klara's hook-in explicitly targets Scene sequences, not the Master (`E:/PussStage/Saved/CodexConductor/KlaraIngest/klara_hookin.py:37-46,1090-1125`). | **INFERRED — expected behaviour.** Later Scene outer sections move by D; their internal Klara keys remain local and need no edit. |
| Managed music sections | **PROVEN — declaration-proven.** Identity is Owner/Block/Rail GUID (`Plugins/InfinityStage/Source/InfinityStage/Public/MovieSceneInfinityAudioTrack.h:8-39`); rebuild resets sound, source offset, range, repeating state and envelope (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:485-599`). | **INFERRED — recommended.** Point the rail to the imported rendered WAV, then rebuild. Verify section start/end, offset, Sound, envelope and output duration. |
| Music analysis / song markers | **PROVEN — declaration-proven.** Music-map markers/curves/sections store source seconds (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageMusicMapAsset.h:35-77,80-99,111-156`); Choreo song markers are generated from analysis seconds (`E:/PussStage/Saved/CodexConductor/choreo_song_markers_refresh.py:8-33,243-251`). | **INFERRED — recommended.** Reanalyse the rendered WAV or transform every post-T proposal through the renderer's sample map; refresh Choreo song markers. A stale map is a refusal. |
| Root artist tracks and binding tracks in Master | **PROVEN — declaration-proven.** Rebuild touches only four owned track classes; the resize census explicitly records all other root/binding tracks as not rippled (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStagePassageResizeLibrary.cpp:117-200,510-512`). | **INFERRED — recommended.** For sections wholly after F, move by D; for a section spanning F, extend its end and shift channel keys at/after F. Refuse unsupported sub-sections/time warps. |
| Root camera-cut track | **PROVEN — declaration-proven.** Managed Master rebuild never edits it; only the separate render-wrapper rebuild clears and derives wrapper cuts (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:612-780`). | **INFERRED — recommended.** Ripple artist root cuts, and explicitly rebuild/read back any render wrapper used for rehearsal/render. Scene-internal cuts travel with their Scene. |
| Master marked frames | **PROVEN — declaration-proven.** The rebuild contains no marker operation; the census lists them as artist content (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStagePassageResizeLibrary.cpp:138-156`). | **INFERRED — recommended.** Shift every Master marker at/after F by D. Use `find_marked_frame_by_label` for deletions during REVERT. |
| GO markers in segment sequences | **PROVEN — declaration-proven.** Cue Book `At` is segment-relative and converted to the target child sequence frame (`Tools/CueBook/unreal/go_markers_sync.py:460-481`). BREATH rows are deliberately not written because transport has no BREATH state (`Tools/CueBook/unreal/go_markers_sync.py:102-126`). | **INFERRED — recommended.** Later segments need no local shift. In the changed Passage Choreo, add D to post-F `At`/GO frames. Keep BREATH documentary; do not turn it into a transport hold. |
| Cue Desk CSV / cue sheet times | **PROVEN — declaration-proven.** `At`, `GO`, and “Pause possible” are explicit external fields parsed as relative times (`Tools/CueSheet/cue_sync.py:55-76,81-110,233-255`). **PROVEN — measured.** Current tracked `working.csv` has the columns but zero non-empty At/GO rows (current checkout audit of `Docs/CueSheet/working.csv:1-100`). | **INFERRED — recommended.** Shift post-F rows within the changed Passage by D, regenerate exports, and update any human running-time sheet. Later segment-relative rows do not change. |
| Light/drama property keys | **PROVEN — declaration-proven** for ownership; **UNCLEAR — saved-state check.** Root artist tracks are not rippled; current-Choreo keys stay local; later child sequences move as above. | **INFERRED — recommended.** Census root and changed-Choreo light/property tracks. Ripple post-F keys in those two authorities only. Saved counts require Unreal read-back, prohibited by this brief. |
| Mechanism `ExplicitOriginFrame` | **PROVEN — declaration-proven.** It is an absolute `FFrameNumber` used directly as phase origin (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:662-669`; `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:1502-1512`). | **INFERRED — recommended.** Shift any explicit origin at/after F by D. **UNCLEAR — saved-state check.** Which saved cues use it must be listed from the Show during DRY. |

## Audio renderer delivered

- **PROVEN — declaration-proven.** `Tools/Breath/breath_audio.py` takes JSON args, defaults W=2.5 s and U=0, validates
  mono/stereo and expected sample rate, refuses invalid T/N/W, and forbids every output under Content
  (`Tools/Breath/breath_audio.py:137-236,240-297`).
- **PROVEN — declaration-proven.** T means “source sample where wind-down starts.” The exponential-ish down curve
  advances to an integer, low-amplitude stop sample; silence is exact; optional mirrored wind-up starts from that same
  sample; unity playback resumes without a skipped source sample (`Tools/Breath/breath_audio.py:299-407`). Exact length:
  `input + N + (Wout-Wsource) + (Uout-Usource)`; every term is recorded in samples and seconds
  (`Tools/Breath/breath_audio.py:353-405`).
- **PROVEN — declaration-proven.** The wind-down tail reaches zero, the resume point is selected near zero, and the
  first resumed sample is numerically identical to the stopped source sample (`Tools/Breath/breath_audio.py:314-369`).
  The tool writes dependency-free waveform and scipy spectrogram PNGs (`Tools/Breath/breath_audio.py:428-485`).
- **PROVEN — declaration-proven.** DRY writes nothing; APPLY requires `APPLY_BREATH_AUDIO:<run>`, makes
  `Backups/PreBreathAudio-<run>` plus a pre-change record before named writes, reads WAV/PNG back, records an empty
  offline package census, and emits a run marker (`Tools/Breath/breath_audio.py:517-610,710-740`). REVERT requires
  `REVERT_BREATH_AUDIO:<source-run>`, refuses drift, archives applied bytes, restores old bytes, reads back, and never
  permanently deletes them (`Tools/Breath/breath_audio.py:646-707`).
- **PROVEN — measured.** `python Tools/Breath/test_breath_audio.py` passed
  `BREATH_AUDIO_HARNESS_OK|positive=3/3|negative=5/5|checks=23`. Positives cover exact no-wind-up resume/length,
  mono wind-up, PNGs and APPLY/REVERT recovery; negatives cover T beyond EOF, N<0, W too long, channel mismatch and
  sample-rate mismatch (`Tools/Breath/test_breath_audio.py:71-199`).

## Recommended future Unreal tool: `breath_insert.py`

**INFERRED — recommendation derived from the risks above.** This tool is not part of P36's requested implementation;
it should be built and live-tested before any authoring apply.

### Args

**INFERRED — recommended design.** JSON fields: `mode`, `run_id`, exact `confirm`, `passage_guid`,
`passage_offset_frame` (F, never label/ordinal), `audio_apply_record`, `insert_frames` (must exactly equal the renderer
record's delta transformed to Show tick resolution), `look_yaw_degrees`, `look_pitch_degrees`, easing/fade frames,
`changed_choreo_policy`, and named Show/Master/level/Choreo/music packages. Gary's look and timing values remain args;
the tool supplies no hidden creative constants.

### DRY

1. **INFERRED — recommended guard.** Require expected world, no PIE, closed Sequencer, exact empty dirty-package census,
   unique Passage GUID, F strictly inside its compiled range, renderer record/hash match, representable D, and an
   imported SoundWave/analysis map matching the rendered WAV.
2. **INFERRED — recommended census.** Record compiled before/after simulation; containing linear span; all 13 Passage
   channels and pins; every root/binding track, cut and marker; changed Choreo tracks/markers; explicit mechanism
   origins; managed sections/music; adjacent handoffs; Cue Book At/GO; render wrapper; exact named package set.
3. **INFERRED — recommended refusal.** Refuse overlap with an existing breath, unsupported straddling sub-sections,
   locked markers, stale analysis, non-empty census, unexpected packages, or any holder that cannot be classified.

### APPLY

1. **INFERRED — recommended recovery.** Require `APPLY BREATH <run>`; create exclusive record and
   `Backups/PreBreathInsert-<run>` containing every named package before the first mutation.
2. **INFERRED — recommended mutation.** Add D to the containing Show timing span; ripple changed-Passage channel keys,
   relative pins, changed-Choreo content, root artist content, Master markers, current-segment GO/At, and explicit
   origins; add Speed/Yaw/Pitch breath keys; change the rail Sound/analysis to the rendered import.
3. **INFERRED — recommended managed work.** Rebuild managed Master, materialize only the affected Passage, rematch/check
   adjacent Scene handoffs, and rebuild the named render wrapper if used.
4. **INFERRED — recommended save/read-back.** Require the dirty census to equal the named packages; save only those
   packages. Reload/read back exact compiled D, every numeric key (float tolerance 1e-4), markers, managed ranges,
   music Sound/offset/envelope/duration, handoff coverage, wrapper cuts, zero final dirty packages, then emit
   `P36_BREATH_APPLY_OK|run=<id>`.

### REVERT

**INFERRED — recommended recovery.** Require `REVERT BREATH <source-run>`, clean census and exact applied fingerprints;
archive current applied packages under `Backups/PreBreathInsertRevert-<run>`, restore every recorded pre-state package,
reload and read back fingerprints/timing, save no unrelated package, and emit `P36_BREATH_REVERT_OK|run=<id>`.

## Rehearsal runbook

1. **INFERRED — operational procedure.** Copy `Tools/Breath/breath_audio_args.example.json` into `Saved/CodexBreath/<run>/args.json`.
   Gary/Klara choose source T, silence N, W (default 2.5 s), optional U (default 0), and listen/look intent. Run DRY;
   inspect the printed exact delta plus both preview PNGs. DRY applies nothing.
2. **INFERRED — operational procedure.** Change mode to APPLY, add `confirm: APPLY_BREATH_AUDIO:<run>`, run the same command, and
   preserve `apply_record.json`. Import the resulting WAV through the normal guarded audio-import route; do not put the
   WAV or previews in Content directly.
3. **INFERRED — operational procedure.** Feed the renderer record's exact delta—not merely N—into the future breath-insert tool,
   DRY it, approve its complete holder/package census, then APPLY and read back before rehearsal.
4. **INFERRED — acceptance procedure.** In rehearsal, verify by eye/ear: Puss has zero route movement through the approved look,
   Wing motion/squeaks and time-driven flicker continue, ambience remains, music resumes at the recorded source sample,
   and the first post-breath cue is delayed by exactly D. This is required rendered acceptance, not established here.

## Open questions for Gary/Klara

- **UNCLEAR — creative choice.** Does Puss stop for the entire audible W+N+U effect, or only for the exact music-delay
  D reported by the renderer? Those differ because wind-down/up still consume source samples. Search: Gary's 9 Oct
  decisions in the P36 brief define true pause and defaults but do not resolve this clock distinction. Recommended:
  stop for D to keep route and music delay identical; judge the feel in rehearsal.
- **UNCLEAR — creative choice.** Exact Passage, F/T, N, W/U, Yaw/Pitch amplitude, direction, number of glances and ease
  shape remain Gary/Klara's. Search: the brief supplies no numeric choice beyond W=2.5 and U=0 defaults.
- **UNCLEAR — saved-state check.** Actual current root artist tracks/cuts/markers, changed-Choreo contents, explicit
  origins, active light-drama modes, rail mode, SoundWave and MusicMap cannot be established offline from source.
  Search performed: current source, tracked Cue Sheet/Cue Book tools/data, tracked Klara/marker tools, and read-only
  `E:/PussStage/Saved/Logs`; no Unreal asset read-back was allowed.
- **UNCLEAR — audio acceptance.** No production WAV or chosen args were supplied, so only synthetic mono/stereo controls
  were rendered. Gary/Klara must listen to the production APPLY and approve its de-pitch, silence join and resume.
