# Infinity Stage Director — Overnight Build Plan

**Plan date:** 11 August 2026  
**Target runtime:** live PIE using UE5 Sequencer for narrative visuals  
**Source specification:** `Docs/InfinityStageDirectorSpecification.md`  
**Build rule:** V1 reliability comes first; V2 music intelligence begins only after the V1 gate passes. Every red gate, crash, or reported 403 sends work back through the last known-good checkpoint before feature work continues.

---

## 1. Honest overnight objective

One overnight is not enough to truthfully finish and production-harden the complete V1 and V2 described in the full specification. The achievable objective is:

1. produce the first compiling, side-by-side **InfinityStage** plugin foundation;
2. prove the highest-risk V1 vertical path using the supplied music and live PIE;
3. leave a usable editor-facing V1 slice rather than disconnected experiments;
4. run a bounded V2 analysis-provider spike on generated golden audio, followed by the actual recordings when their sync is stable; and
5. deliver a morning report that distinguishes completed, tested, partial, and blocked work.

The night must not end with a broad collection of uncompiled files. A smaller compiling V1 slice is preferred over a larger broken implementation.

---

## 2. Locked production assumptions

### Runtime and output

- The final visual output is the live theatrical performance running in PIE/UE5 Sequencer.
- Movie Render Queue is only a deterministic test/offline-review path.
- nDisplay is not assumed.
- The current development machine is a development baseline only; no production performance claim is made until the target show workstation/GPU is known.

### Wing diversity and scale

- Assume **at least 30 unique wing source assets per Passage**.
- Assume six Passages, therefore at least **180 unique wings overall**.
- The conservative performance fixture treats those 180 assets as separate mesh/material render keys until real asset inspection proves otherwise.
- Within a Passage, the 30 assets may repeat across its longer Wing Pair cue list; logical cue identity is still unique.

### Music and external Scene sound

- Passage defining music is wholly controlled by the one Master Sequence Player.
- Scene sound may also be external to Unreal.
- A Scene with external, unpausable sound is marked **External Sound Authority**.
- In Performance mode, unsafe reverse, hold, or rate changes are disabled while such a Scene is active unless an external synchronisation/control adapter is configured.
- Rehearsal may still seek Scene visuals with external audio muted/absent.
- The exact external protocol—manual operator cue, OSC, LTC/MTC, or another source—remains an adapter decision and must not leak into the core timeline model.

### World size

- World footprint, vertical range, and minimum turn radius are not fixed tonight.
- Routes use normalized/editable splines and provisional separate bays.
- Route length is derived from music duration, camera speed, spacing, and clearances.
- Unknown footprint produces a visible **Layout Unconfirmed** warning, not a hard-coded bend radius or false production-ready result.

---

## 3. Music input and sync gate

At the start of execution, locate the supplied performance tracks and record:

- source path/Unreal asset path;
- intended Passage number/name;
- file format, sample rate, channels, and duration;
- whether it is final audio, a rehearsal mix, or a reference;
- required source In/Out and fade assumptions; and
- whether a composer tempo map, MIDI file, cue sheet, or named structural markers exist.

The production Google Drive has now exposed the following candidate Passage rails under `2026. SHS 3 Evenings/Sound/Gary_For_Infinity_Scenes/`:

- `Intro_WalkingMusic_1.wav`;
- `WalkingMusic_2.wav`;
- `WalkingMusic_3.wav`;
- `WalkingMusic_4.wav`;
- `WalkingMusic_5_with_Tennis_Ball_Moment.wav`; and
- `WalkingMusic_6_into_void.wav`.

It also currently exposes Scene WAVs and four placeholder theatre-winch/pulley files. Treat this as a preliminary inventory while Google Drive is still syncing. Recheck the folder after at least 30 minutes, compare file count, size and modification state, and prove each candidate is locally readable before fingerprinting or import. Never edit, rename, move, or analyze a cloud-placeholder file in place. Copy a stable source into the agreed project import/staging location, preserve the original filename and fingerprint, and do **not** substitute Unreal Starter Content music.

If any track is still unavailable, V1 continues with exact synthetic-duration/audio fixtures and marks only the real-track integration checks **Waiting for Source**. V2 provider and contract testing must continue without waiting for music or user review.

Suggested project organization after the paths are confirmed:

```text
Content/InfinityStage/Audio/Passages/P01/
Content/InfinityStage/Audio/Passages/P02/
...
Content/InfinityStage/MusicMaps/
```

The original source recording remains outside cooked content under the production backup policy; the Unreal `USoundWave` is the playback asset.

---

## 4. Overnight safety and scope rules

1. Create `Plugins/InfinityStage`; do not refactor `Plugins/StageWingDirector` in place.
2. Do not modify old Show Assets or migrate their serialized data.
3. Reuse old meshes only through ordinary soft asset references.
4. Do not place core logic in the Level Blueprint.
5. Do not spawn or generate fixed stage geometry at BeginPlay.
6. Do not let analysis suggestions mutate Cue rows automatically.
7. Compile after every structural module/schema step.
8. Stop expanding a feature when its test is red; repair or reduce scope first.
9. Do not claim production performance from placeholder cubes or the development laptop alone.
10. Preserve user-authored world content and unrelated dirty files.

Because the workspace is not currently a Git working tree, keep a precise changed-file ledger in the morning report and confine all new implementation to the new plugin, its tests, and explicitly named Infinity Stage content.

### Crash and 403 recovery loop

The existing project search has not established that “403” is an Unreal crash code. Treat it as an observed failure label until evidence identifies whether it is an HTTP 403 from a service/sync/tool, an application exit value, or shorthand for another recurring crash. Do not merge those failure classes in the report.

Run this loop at every 60–90-minute checkpoint and immediately after any abnormal exit:

1. stop feature work and preserve the last command/test name, UTC/local timestamp, process exit code or HTTP status, and the last known-good checkpoint;
2. collect the relevant Unreal build output, `Saved/Logs`, `Saved/Crashes`, macOS crash report, call stack, request ID, and service/tool name where available;
3. classify the event as compile failure, Unreal assertion/crash, operating-system termination, HTTP 403/authentication denial, cloud-placeholder/sync failure, or unknown;
4. reproduce once with the smallest exact prior test—never with the whole night’s test suite first;
5. if it is an HTTP 403, avoid a retry storm: preserve local work, check credentials/session/service scope without exposing secrets, wait for the designated retry point, and continue with an offline/local path where possible;
6. if it is an Unreal crash, reopen from the last green build, repeat the failing frame/action, and check whether a clean Editor restart changes the outcome;
7. apply the smallest repair, rerun the failing test, then rerun the preceding green test; and
8. only declare recovery after two consecutive clean repetitions plus a clean Editor reopen when Editor state was involved.

If the same unresolved 403/crash recurs three times, quarantine that path for the night, preserve a minimal reproduction, and redirect effort to independent V1 work. Loop back at the next major gate rather than silently abandoning it. The morning report must include occurrence count, evidence paths, impact, workaround, and whether the failure is project code or external infrastructure.

---

## 5. Priority gates

### Gate A — baseline

Must pass before implementation:

- UE 5.8 project opens/builds at its current baseline;
- old Stage Wing Director remains loadable and untouched;
- supplied music is located or explicitly marked unavailable;
- target Editor build command and Automation invocation are recorded; and
- no pre-existing project error is misreported as new Infinity Stage breakage.

### Gate B — V1 core

Must pass before any V2 work:

- new Runtime, Editor, and Tests modules compile;
- Show/Cue/Passage/Music binding schemas serialize and reload;
- the music-led fit solver passes exact unit tests;
- a Passage Actor and fixed materialized wing content exist before PIE;
- camera and mechanisms evaluate from absolute Sequence time; and
- one Master audio/camera authority exists.

### Gate C — live PIE vertical slice

Must pass before calling the night successful:

- Passage A → externally sounded Scene → Passage B plays in PIE;
- Passage music comes only from the Master Sequence;
- camera owner is unique across both handoffs;
- the Scene exposes External Sound status and transport restrictions;
- direct seek/reverse returns deterministic visuals;
- BeginPlay creates no fixed wing stage content; and
- at least one real/representative unique-wing fixture is exercised.

### Gate D1 — V2 provider without production music

Starts only if Gates A–C are green or the remaining C work is a clearly isolated manual PIE check:

- generated golden fixtures exercise the decoder/provider/cache pipeline;
- results are versioned proposals;
- the Cue Score remains unchanged;
- ambiguity is reported rather than hidden; and
- output can be reopened and reviewed.

### Gate D2 — supplied-track integration

Runs when the Drive sync is stable, without waiting for the user:

- every locally readable walking track decodes and fingerprints;
- analysis completes or reports a bounded provider error without crashing;
- reanalysis is stable and stale-source behavior is correct;
- machine-readable and visual review artifacts are produced; and
- all musical interpretations remain unapproved suggestions.

Gate D1 can pass while D2 is legitimately **Waiting for Sync**. This does not hold V1 hostage.

---

## 6. Sixteen-hour iterative execution schedule

Times are elapsed time, not fixed clock times.

| Elapsed | Work block | Required output | Stop/fallback rule |
| --- | --- | --- | --- |
| 00:00–00:30 | Baseline and music inventory | Baseline build result, music manifest, changed-file ledger started | If baseline is broken, diagnose and report; do not attribute it to the new plugin. |
| 00:30–01:15 | Scaffold `InfinityStage` | Runtime/Editor/Tests modules and descriptor compile empty | If module load fails, fix this before adding schemas. |
| 01:15–02:45 | V1 data model and compiler core | Show Asset, Cue kinds, Passage Span, Section Music Binding, stable GUIDs, custom version, basic validators | Cut editor polish first; never cut stable identity or transaction safety. |
| 02:45–03:45 | Music-led fit with supplied track | Source fingerprint/metadata, exact In/Out duration, speed/spacing/count/distance solver, reset recipe, unit tests | If audio is missing, use an explicit synthetic duration fixture and mark real-music checks waiting. |
| 03:45–05:00 | Compact Cue Desk and Guided Setup | Virtualized Cue Score shell; tabbed Music/Fit/Route setup; persistent status rail; no tall stacked form | Use functional Slate structure over pixel polish. |
| 05:00–06:30 | Persistent Passage materialization | One spline Passage Actor; persistent chunks/components; 30-unique-wing Passage fixture; no BeginPlay construction | If full ISM mapping slips, preserve persistent Static Mesh fallback and manifest identity. |
| 06:30–08:00 | Sequencer, Show Root, camera, transport | One Master player; Passage evaluation from absolute frame; basic forward/reverse/seek; camera handoff records | A minimal native Passage track/section plus deterministic evaluator outranks transition UI polish. |
| 08:00–08:45 | Hybrid Scene sound boundary | External Sound Authority field/status; unsafe command rejection; Passage → Scene → Passage test data | Do not attempt a venue protocol without its actual specification; leave an adapter interface. |
| 08:45–09:00 | **V1 gate** | Compile + unit tests + Editor materialization check | If red, all remaining time returns to V1. |
| 09:00–10:30 | V2 provider and analysis spike | Golden synthetic fixtures first; then stable supplied tracks when available; waveform, loudness/onset/spectral features, tempo candidates, major-change proposals, source/version metadata | No Cue edits. Gate D1 proceeds without music; D2 may wait for sync. If confidence is weak, retain features and report uncertainty. |
| 10:30–11:15 | Live PIE vertical-slice verification | Passage A → Scene → Passage B, camera/music ownership, seek/reverse, no runtime stage creation | If automated PIE is not viable, perform a recorded manual checklist and keep the failure explicit. |
| 11:15–12:00 | Regression checkpoint | Clean rebuild, focused Automation results, performance counters, screenshots/log references, blocker list | If this is the available overnight limit, stop here with a truthful handoff. If more time remains and V1 is green, enter the extension passes below. |
| 12:00–13:00 | Extension pass 1: cue authoring | Transactional multi-select, duplicate/repeat/move/delete block operations, compact context menus, undo/redo tests | Cut spreadsheet polish before transactional correctness. |
| 13:00–14:00 | Extension pass 2: tweening minimum | One compile-time range lane for camera speed/timing and one mechanism loop-rate lane; phase-continuity tests; bake preview only | Do not broaden to every parameter. Prove the lane/override/priority contract first. |
| 14:00–15:00 | Extension pass 3: six-Passage music/show fixture | Import/stage all stable walking tracks, create six Passage bindings, generate a managed macro Master fixture, validate unique music/camera ownership | If the sync is incomplete, use bindings plus metadata without inventing audio results. |
| 15:00–15:30 | Extension pass 4: scale and recovery | 3,000-row compile/materialization stress pass, rapid seek/reverse, editor reopen, crash/403 review | Repair regressions; do not add a new feature. |
| 15:30–16:00 | Final hardening and handoff | Repeat last green tests twice, verify clean Editor restart, finalize report and continuation checkpoint | No implementation work in the final 30 minutes except a small regression fix with an immediate test. |

### Iteration rhythm inside every work block

Each block is a small closed loop rather than a one-way feature sprint:

1. write or update the acceptance test;
2. implement the smallest coherent slice;
3. compile locally with Unreal Editor closed when reflected types/modules changed;
4. launch the appropriate commandlet or Editor test gate;
5. inspect errors, warnings, crash records, and 403 evidence;
6. fix and rerun the exact failed test;
7. reopen/save/reload when serialization or materialization changed; and
8. record the last known-good checkpoint before expanding scope.

Target a checkpoint every 60–90 minutes. A feature is not credited merely because it compiled once; it must survive the relevant reload or repeat test.

### UE 5.8 process policy

The user does **not** need to leave UE 5.8 running at the start of the night.

- Keep Unreal Editor closed while scaffolding modules, changing `UCLASS`/`USTRUCT` declarations, running Unreal Header Tool work, or replacing plugin binaries. This prevents stale-module and file-lock ambiguity.
- Use command-line build and Automation/commandlet tests first where they cover the behavior.
- Launch the Editor for asset serialization, Slate layout, materialization, spline editing, Sequencer integration, audio audition, and PIE gates.
- It may remain open during a short asset/UI/PIE iteration batch that does not change reflected C++ types. Close and relaunch at each structural code boundary and after any crash.
- Do not rely on Live Coding for schema/module changes in this overnight pass.
- Gate C and final acceptance require a deliberately launched clean UE 5.8 session. Merely inheriting an already-running Editor is not a clean-start test.

---

## 7. V1 overnight implementation scope

### Must complete

- Side-by-side plugin/module skeleton.
- `UInfinityStageShowAsset` with ordered Wing Pair/Scene/Sequence cues.
- Stable GUID identity and custom serialization version.
- Derived contiguous Passage Span compilation.
- `FInfinityMusicRail` and `FInfinitySectionMusicBinding` sufficient for Start, Continue, Silence, Explicit Crossfade data, and External Scene Sound declaration.
- Music duration/speed/spacing/clearance/count solver with the exact 240 s example plus the supplied-track duration.
- Compact editor shell with the Cue Score always dominant.
- Music/Fit/Route internal setup tabs with one expanded section at a time.
- Persistent status rail showing music duration, Passage duration, camera speed, distance, count, spacing, residual, stage sync, camera/music owner, and readiness.
- One persistent spline Passage Actor and fixed wing representation present before PIE.
- Absolute-time camera movement and at least Static + Continuous Loop mechanism evaluation.
- One Show Root and one Master Sequence Player.
- Basic forward, reverse, pause, seek, Previous, and Next Segment API.
- External Scene Sound status and safe transport rejection.
- Core unit tests and one PIE vertical-slice checklist.

### Should complete if Must is green

- Materialization manifest with Cue GUID/side mapping.
- Thirty unique wing source assets exercised inside one Passage fixture.
- Conservative 180-unique-render-key synthetic compile/performance report across six Passage datasets.
- Basic persistent chunk grouping and repeated-key ISM path.
- Scene entry/exit camera pose capture data.
- Source In/Out and fade controls on the Music tab.
- Music asset fingerprint/stale-fit detection.
- One Attachment Anchor and temporary Ground Zone registration.

### Stretch only

- Full Stage viewport selection bridge.
- Hero promotion/demotion.
- Serpentine/Normalized Custom path editing beyond a basic spline.
- Mechanism audio pool.
- Complete Master sequence rebuilding and managed decorations.
- World Partition/Data Layer runtime streaming.
- Operator hardware adapters.

Stretch work may not make a Must item unbuildable.

---

## 8. V2 analysis scope

V2 is not “automatically choreograph the whole show.” Its overnight target is a tested analysis provider plus credible, reviewable records for every stable supplied track. Technical progress does not depend on the user being present or on Drive sync finishing at a particular moment.

### V2 analysis pipeline

1. Decode/import the authoritative source and compute a fingerprint.
2. Cache a multiresolution waveform.
3. Compute loudness and onset/attack evidence.
4. Compute Constant-Q/spectral/chroma-style features available through the approved provider.
5. Produce competing tempo candidates, including half/double alternatives where supported.
6. Produce beat/downbeat candidates only with explicit confidence/provenance.
7. Produce major-change candidates from novelty/self-similarity evidence where the provider supports it.
8. Store confirmed, suggested, and rejected items separately.
9. Display proposals over the waveform with accept/reject/drag/rename operations designed, even if only the data layer is functional overnight.
10. Never create Wing Pair cues, Automation Lanes, or camera changes without an explicit preview-and-apply command.

### V2 tests that require no live user

The technical V2 gate is fully automatable. Human listening is needed later to judge artistic usefulness, not to prove the provider, cache, safety, and deterministic behavior.

**Layer 1 — generated golden audio fixtures**

Generate short test PCM/audio fixtures during the test run rather than depending on cloud music:

- silence and near-silence;
- one isolated impulse at a known sample;
- steady 60 BPM and 120 BPM click tracks;
- a deliberately half/double-tempo-ambiguous pulse;
- a 90→120 BPM step/ramp fixture;
- irregular/rubato pulses;
- a long fade-in/fade-out with silence; and
- two contrasting spectral/noise regions with a known boundary.

Verify exact decoded duration/sample mapping, repeatable fingerprints, onset timing within a declared provider tolerance, inclusion of the known tempo among the ranked hypotheses, structural boundary tolerance, no NaN/invalid outputs, stable reanalysis, cache invalidation after a changed sample, and zero Cue Score mutation. The expected values and tolerances live with the tests; they are not visually judged overnight.

**Layer 2 — supplied-track unattended integration**

Once each synced WAV proves locally readable, run all six walking tracks without requiring operator input. For each track verify decode, format/duration capture, fingerprint stability, bounded analysis time/memory, cache reopen, proposal serialization, source-change staleness, graceful low-confidence output, and no crash or 403. Produce waveform/feature artifacts and a machine-readable summary. This is a smoke/determinism test, not a claim that the inferred musical form is artistically correct.

**Layer 3 — deferred artistic review**

Queue the morning proposals for later listening. The user/composer may confirm, reject, rename, or move markers, but lack of that review does not block V1 or the technical V2 gate. Until reviewed, every result remains `Suggested` and nothing retimes wings or the camera.

### V2 morning acceptance

- Gate D1 passes on generated golden fixtures even if the production recordings are unavailable.
- Every stable supplied track processed by Gate D2 reopens with the same fingerprint and cached proposal set.
- Reanalysis with unchanged source/version is stable.
- Replacing the recording marks results stale.
- At least loudness, onset, and major-change evidence is inspectable.
- Tempo output shows alternative hypotheses when ambiguous.
- Applying nothing leaves the V1 Cue Score byte-for-byte/semantically unchanged.
- A short report identifies which inferred markers appear musically useful and which require composer/operator confirmation.

### V2 deferrals

- Production claims for beat/downbeat/form accuracy.
- Automatic camera-speed warping to every beat.
- Automatic formal-section naming.
- Live external Scene-audio synchronisation without protocol details.
- Quartz/MetaSound precision adapter unless an actual demonstrated requirement exceeds standard Sequencer audio behavior.

---

## 9. Music-led test cases

### Passage music

- Full-track In/Out derives exact Passage duration.
- Trimmed In/Out updates duration and marks count fit proposed/stale.
- Fade durations never alter source-time mapping.
- Continue binding crosses a Section boundary without duplicate output.
- Direct seek reconstructs the correct source offset.
- Reverse shuttle mutes defining music and resumes at the correct Master position.

### Hybrid Scene sound

- Entering an External Sound Scene stops/continues Passage music exactly as its binding declares.
- Scene status visibly reads `EXTERNAL SOUND` plus Ready/Not Ready/Uncontrolled as appropriate.
- Performance reverse/hold/rate is rejected when the external clock is unpausable.
- Rehearsal visual seek is permitted with external sound explicitly absent/muted.
- Returning to the next Passage starts/seeks only the Master-owned Passage Rail.
- Physical overlap of Scene/Passage bays never starts audio.

### Analysis

- Analysis never changes cue count.
- Suggestions and confirmed markers remain distinct.
- Half/double-tempo ambiguity is represented.
- Source replacement invalidates/remaps by explicit review only.
- Silence/long fade does not create a burst of false cue insertions.

---

## 10. Wing diversity and performance fixture

Create two complementary fixtures:

### Passage-realistic fixture

- 120 Wing Pair cues;
- 30 unique wing source assets reused across the Passage;
- realistic masked photographic materials and shadows where available;
- Continuous Loop absolute phase;
- persistent chunks visible before PIE; and
- fixed camera-visible plus conservative rear-shadow relevance.

### Show-diversity fixture

- six Passage datasets;
- 30 unique wing source assets per Passage;
- 180 unique source assets/render keys in the conservative case;
- no ordinary Wing Pair Actors;
- compile/materialization/component/draw-call estimates; and
- explicit warning if unique render keys defeat batching.

The morning report must not collapse “180 unique source wings” into “180 Wing Pair cues.” They are separate scale measures.

---

## 11. Verification matrix

| Area | Overnight verification |
| --- | --- |
| Build | Editor target compiles and plugin modules load. |
| Serialization | Save/reload Show Asset preserves Cue order, GUIDs, Passage boundaries, and music bindings. |
| Solver | Exact count/distance/cadence cases plus non-closing residual cases pass. |
| Editor | Cue list remains dominant; Music/Fit/Stage tabs preserve values; window works at the compact height. |
| Materialization | Fixed wing components exist before PIE; BeginPlay adds none. |
| Sequencer | Play, direct seek, reverse visual evaluation, and camera owner are deterministic. |
| Music | One Master Passage music owner; correct source offset after seek; no autonomous per-Passage player. |
| External Scene sound | Status and unsafe transport restrictions behave as declared. |
| Performance | Thirty-unique Passage and 180-unique Show fixtures report components/render keys honestly. |
| V2 synthetic | Golden fixtures prove duration, onset, tempo-hypothesis, structural-change, cache, stale-source, and non-mutation contracts without user input. |
| V2 supplied tracks | All locally readable walking tracks complete unattended smoke/determinism analysis; artistic correctness remains unapproved. |
| Recovery | Checkpoint review finds/classifies crashes and 403s; a recovered failure passes twice and survives a clean reopen. |

---

## 12. Morning handoff format

The overnight work ends with `Docs/InfinityStageOvernightReport.md` containing:

1. **Outcome:** V1 Gate status and V2 Gate status.
2. **Music used:** exact source fingerprint, duration, format, and Passage mapping.
3. **What works in PIE:** concise end-to-end behavior.
4. **Tests:** passed, failed, skipped, synthetic, supplied-track unattended, and why.
5. **Performance:** 30-unique Passage and 180-unique Show fixture counters.
6. **Files changed:** every new/modified file because the workspace has no Git status.
7. **Known limitations:** never disguised as completed.
8. **Screenshots/log references:** Cue Desk, setup tabs, spline/materialized stage, Sequencer, and analysis proposals.
9. **Crash/403 ledger:** classification, recurrence, evidence, reproduction, recovery, and remaining external dependency.
10. **First next task:** one concrete continuation, not a diffuse wishlist.

---

## 13. Questions that remain after this plan

These do not block the first overnight build, but they do block final live-show sign-off:

1. Confirm that the numbered `Intro_WalkingMusic_1`/`WalkingMusic_2`–`6` filenames map directly to Passages 1–6 after the sync completes.
2. Target performance workstation/GPU.
3. External Scene sound protocol and whether it provides timecode, start acknowledgement, pause, or seek.
4. Final Scene/Passage world footprint and acceptable route curvature.
5. Whether “30 unique wings per section” means individual panel assets, complete Left/Right pair designs, or both; the overnight fixture conservatively treats them as individual source/render assets.
6. Final venue audio routing and output channels.

Until answered, the implementation remains configurable and uses the conservative assumptions above.
