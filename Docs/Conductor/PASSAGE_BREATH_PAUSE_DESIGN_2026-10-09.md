# Passage "breath" pause — design note (9 Oct 2026, investigation only; nothing built)

**Ask (Gary, via the Cueing session, 9 Oct):** Puss pauses mid-Passage. The music winds down, slows and de-pitches,
then stops. Only ambience remains while Puss looks around, perhaps as a set piece. The wings must keep squeaking and
shattering ("if they stopped … weird time travel gag"). Pause points: the ambience moments, not yet identified.
Timings are not fixed.

## Why a transport pause is not enough

**Passage time is Master time** [declaration-proven, `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp`]:
- Wing mechanisms are evaluated from the Master frame: `EvaluateMechanismsAtMasterFrame` / `…AtCameraDistance`,
  :1288-1300.
- The camera distance itself comes from the frame: `EvaluateDistanceAtFrame`, :1320-1321.
- Time-phased wings integrate a rate from a phase-origin frame ("RateIntegralByOriginFrame", :1361-1363).
- Wing modulation keys are read at the Master frame, :1349-1358.
- The squeak sound step uses `ShowDeltaSeconds` = the Master frame delta, :1408-1415.
  `IsForwardPlaybackStep` compares it with real elapsed seconds, so a frozen Master means no forward step and no squeak
  [declaration-proven that the gate exists; that it silences the squeak is inferred].
- Lights, movers and bulbs use `ShowSeconds = MasterFrame / TickResolution` (≈ :1848, :1886-1888).

**Consequences:**
- A pause freezes everything Gary wants alive.
- A vamp loops the Master, so the wings replay and the squeaks repeat. That is the "time travel gag".

## Two mechanism families behave differently

[declaration-proven that both exist; behaviour under a breath is inferred]
- **CameraGust wings** (`EInfinityMotionPlaybackMode::CameraGust`, :1334-1345) are triggered by the camera
  passing. If Puss stops walking, no new gust fires. A gust already under way needs time to finish.
- **Time-phased wings** need a clock that keeps advancing.

## Options

**A. Live "breath" on the transport** (recommended for "live"). Unbuilt; needs C++ and a build window.
- The transport gains a BREATH state:
  - The Master and camera distance stay frozen, so Puss stops on the route and the GO1 score stops with the camera
    (per the "camera is the cat" rule).
  - A separate breath clock runs.
- Passage evaluation takes `PhaseSeconds = ShowSeconds + BreathElapsed` for:
  - mechanism phase and rate integrals;
  - gust completion;
  - squeak stepping (`ShowDeltaSeconds` comes from the breath clock while breathing);
  - light flicker.
- Route position stays put.
- Music: ramp the music AudioComponent's pitch multiplier and volume down over 2-4 s, then mute or stop. Resume ramps
  them back.
  - This needs the music on its own component or SoundClass, not only on Master audio tracks. A Sequencer audio track
    stops dead on pause.
  - That ties in with the deferred Music SoundClass step from the Cue Desk work.
- Ambience must live outside the Master: a looping spatial component per Passage. Gary already asked for Passage
  sound to be kept apart from the music.
- The look-around is a camera-only rotation layer applied on top of the frozen pose (head turn), so it doesn't
  touch the route.
- Exit: a GO resumes. The breath length is live, not authored.

**B. Authored breath** (quick prototype of the *look*):
- Key a stop-and-look stretch into one Passage: the camera holds, a de-pitch/fade is keyed on the music track, and
  the wings keep running on the timeline.
- Fixed length; a GO can't extend it without a vamp, which replays the wings.
- Good for judging the feel this week; no C++.

## Open questions (Gary / Klara)
1. Where are the pause points? Proposed: mark them on the Cue Book ("pause possible" flag; the Cueing stream offered
   this).
2. Is the breath length live (operator GO) or fixed?
3. What happens to Cameron's live Foley during a breath?
4. Is the look-around free (GO1-driven) or a scored set piece?
5. Do lights hold their state or keep flickering?

## Suggested path
B in one Passage as a look test → if liked, A as a Codex C++ brief:
- transport BREATH state + breath clock;
- Passage phase plumbing;
- music component ramp;
- a fake-clock harness proving the wings advance while the Master is frozen;
- then a build window.
