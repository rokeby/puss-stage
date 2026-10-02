# Build prep: AT v2 + PR v2 (Conductor 4, 2 Oct evening). Gary's answers, his own words in the Conductor 4 session.
Inputs: Scripts/patches/2026-10-02_AT_hangar_timing_details.draft.patch (spec specs/HANGAR_TIMING_DETAILS.md) and
Scripts/patches/2026-10-02_PR_passage_resize.patch (spec specs/PASSAGE_RESIZE_A.md). Work in your worktree: apply both
(--ignore-whitespace), amend, then emit v2 patches.

## AT amendments (Gary's answers)
1. S3: the six `S3 Strike` lights (S3 Strike Key / Fill L / Fill R / Cyc 1-3; keys in Saved/CodexStructure/s3_strike_record.json)
   MOVE with the strike: the earliest strike of ALL S3 lights lands on LightStrikeSeconds (default +10 s), keeping per-light
   offsets and ramp shapes. Gary: "Ok move it but I will have to retime each again when the cues come", so keep it data-driven.
2. S6: NO strike. Its lights fade to near-black: a `bDimInsteadOfStrike` (default true for S6, derived from the actor
   label or set on the S6 Arrival) that keys every S6 light-intensity channel from its current value at LandSeconds down to
   ~2% over `DimSeconds` (default 10 s). No lights turn ON. Refuse nothing else in S6 (roofless: lattice timing still applies).
3. S5: STANDARDISE (Gary: "Standardise S5"). Remove the S5 refusal; ApplyHangarTiming re-keys S5's roof and lattice into the
   standard shape (roof [0,-90],[start,-90],[end,0]; lattice [0,2800],[start,2800],[end,1200], same VALUES the standard
   hangars use only if S5's own values match; if S5's values differ, keep S5's values and change only the TIMES). Report
   S5's before/after keys. Its light strike follows +10 s like the others.
4. Review AT's InfinityStage.Build.cs change: editor-only dependencies must not be added to the runtime module; move the
   editor code to the editor module or guard it properly so packaging can't break. Explain the choice.
5. Add automation tests: `InfinityStage.Hangar.TimingMovesS3StrikeLights`, `...TimingS6DimsInsteadOfStrike`,
   `...TimingStandardisesS5Shape`, each with a negative control described.

## PR amendments
1. Add the C++ automation test `InfinityStage.Editor.PassageResizeAppendsToDuration`: a transient Show with one passage
   of 23 pairs / 47.4 s at 2.5 m/s / 5 m -> 180 s gives 90 pairs, 67 appended with NEW GUIDs, existing GUIDs preserved in
   order, exact 180.000 s; plus refusals (residual not closing; shaped route too short). Negative control described.
2. Targets are run-time arguments only (Gary: P01 stays as is; the resize is P02, P03, P04). No hard-coded passage list.

## Then
Adversarial review of BOTH v2 diffs (crash, packaging, data loss, a refit that silently erases overrides, keys moved in the
wrong track, S6 lights turned on). Emit Scripts/patches/2026-10-02_AT_hangar_timing_details.v2.patch and
Scripts/patches/2026-10-02_PR_passage_resize.v2.patch (each git diff from repo root), confirm both `git apply --check`
on HEAD and that they apply TOGETHER (AT then PR). No Unreal, no build. FINAL MESSAGE: the review findings, files
touched, test names, apply checks, open questions; tags per AGENTS.md.
