# Scene shot stepping (Gary, 2 Oct): tap RIGHT/LEFT steps camera-cut boundaries inside a Scene
Gary's rulings (his own answers, this session): stops = the Scene's ROOT camera-cut section starts; the play state
is KEPT (playing keeps playing from the new shot, paused stays paused on the shot's first frame); hold RIGHT is
UNCHANGED (4x through everything until released). Outside Scenes, nothing changes.

## Behaviour
- Tap RIGHT in a Scene segment: jump to the first root cut START strictly after the current Master frame, within
  this Scene. If there is none (in the last shot), fall through to today's AdvanceToNextSegment() unchanged.
- LEFT in a Scene segment: if the current frame is more than ~0.5 s (a UPROPERTY, default 12 display frames) past
  the current shot's start, go to that start; otherwise go to the previous shot's start. Before or at the first
  shot, fall through to today's JumpToPreviousSegment() unchanged. (This is the same "restart, then previous"
  rule JumpToPreviousSegment already uses for cues, InfinityStageTransportController.cpp:920-927.)
- Cuts come from the Scene sequence's ROOT camera-cut track only (nested cuts never count; see
  FindSceneCameraCut, :1287), active sections only, mapped scene-local -> Master by the same transform
  FindSceneCameraCut/handover already use. Sort the starts and de-duplicate them. Cache them per segment with the
  segments; never recompute per tick.
- Play state: record IsTransportPlaying() before the jump; after it, Play() if it was playing, else stay paused.
- Every shot jump must go through the SAME navigation path as cue jumps: VampPlaybackState.OnNavigation(target)
  (:1008/:1099), JumpResettleState (the geometry-cache re-pose after jumps, patch S), camera claim/handover, and
  the performance-mode interlock and DeclaredUnpausable refusals exactly as JumpToSegment applies them. Return the
  same EInfinityTransportResult codes. Do not add a second jump implementation; factor a JumpToMasterFrame helper
  out of JumpToSegment if needed, without changing JumpToSegment's behaviour.
- Vamp: BeginRightInput's vamp release stays FIRST and untouched. A shot jump that lands exactly on a VampStart
  frame must engage that vamp on the next tick (check FInfinityVampPlaybackState::Tick's PreviousFrame <= Start
  condition after OnNavigation; fix only if the test shows it doesn't). A jump that lands past a VampStart does not.
- Log: INFINITY_SHOT_STEP dir=next|prev segment=%d from=%d to=%d shot=%d/%d playing=%d result=%d.
- Wire it in AInfinityStageShowPlayerController: the tap Advance action and PreviousShowSegment call new
  controller methods StepShotForward()/StepShotBack(), which do the fall-through themselves.

## Tests (new file InfinityStageShotStepTests.cpp; names UTF-8, see memory puss-dll-marker-encoding)
`InfinityStage.Transport.ShotStepNextAndPrevious`: a synthetic Scene with root cuts at 0/100/250 (+ a NESTED cut
at 50 and an INACTIVE root cut at 180, both ignored): next from 10 -> 100 -> 250 -> falls through to the next cue;
prev from 260 -> 250; from 252 -> 100 (inside the grace window); keeps the play state both ways.
`InfinityStage.Transport.ShotStepEngagesVampAtStart`: landing on VampStart engages the vamp; landing past it doesn't.
`InfinityStage.Transport.ShotStepOutsideSceneUnchanged`: in a WingPair segment, tap RIGHT == AdvanceToNextSegment.
Negative control: each test must fail with the feature stubbed (StepShotForward returning the old Advance); state
how you proved that.

## Deliverable: a HELD patch, nothing built
Edit the files, then write `Scripts/patches/2026-10-02_SS_scene_shot_step.patch` (git diff of only your files,
from the repo root), confirm `git apply --check` of it on a clean HEAD, then RESTORE the source files
(`git checkout -- <your files>`, delete your new test file), so the working tree compiles exactly HEAD. Any build
compiles the working tree; a held edit must not leak into another stream's build (memory: puss-held-cpp-edits-as-patches).
NO Unreal, NO build, NO UBT, NO editor contact. Commit nothing. Final message: the files touched, the patch path, the
apply --check result, each claim tagged declaration-proven/inferred, and anything you were unsure of.
