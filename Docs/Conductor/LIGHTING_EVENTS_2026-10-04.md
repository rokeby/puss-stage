# Lighting events: polaroid flash, rare blinkers, black passage (4 Oct, offline)

Gary's notes (3 Oct, verbatim in `Saved/CodexConductor/specs/LIGHTING_LOOKS_P04_TUNE1.md:53-63`)
ask for three things: a polaroid flash, rare bright blinkers in moody bays, and one passage
(P04 is the candidate) kept almost black and shown in trickles of flashes. The flare sweep
is being built by another agent and is not covered here.

Nothing here has run in Unreal. Every claim is tagged: **declaration-proven** (read in
source or config), **measured** (an offline run of the harness), or **inferred**.

## What Gary will see

- **Polaroid flash.** A cool-white (6500 K) hard burst from just above the lens. It
  reaches full brightness in about 1.5 frames and is gone in 0.3 s. Everything in front
  of the camera shows up flat and frontal for an instant, then goes black again.
  - *measured* (harness, Python port of the C++): built engine gives 1.49-frame attack,
    half-level at 0.15 s, off by 0.29 s.
  - *measured*: with the held patch the fall is cubic: half-level at 0.06 s, off by 0.22 s.
- **Black passage (P04 bays 1-6).** The only steady light is a faint warm glimmer along
  the left floor edge of each bay, 8 cd, capped at 15. On top of that come bursts of 2-5
  flashes, with 6-18 s of darkness between bursts. About 40% of flashes come from the
  camera. The rest come from fixtures: high side raking the opposite wing, floor grazers,
  and back-lights behind the wings that shaft through the gaps.
  - *measured*: seed 20261004 gives 4 bursts and 14 flashes across the ~50 s of the
    six bays.
- **Blinkers (moody bays 1-2).** The *dead* practical of each bay (the one the looks
  author at 0 cd) blinks bright and warm a few times on the approach. Blinks are spaced
  irregularly: at least 2.5 s apart, 9 s apart on average.
  - **Not buildable on the current engine**: they need the held patch (below). The tool
    lists them as `deferred` until the patch is built.

## Mechanism and what can be keyed

- *declaration-proven*: Light Drama is keyed by **camera route distance**, never by
  elapsed time (`InfinityStageLightDrama.h:20-31`).
  - Strike is a ramp, and After Pass can be Hold, Decay or Extinguish
    (`InfinityStageLightDrama.cpp:24-60`).
  - The intensity scale is the only keyable output, apart from the slow-move aim
    (`InfinityStageLightDrama.cpp:81-98`).
  - An unlit lamp is switched off, so it costs no shadow map (`:112-128`).
- *declaration-proven*: the lamp's route position is `Wing.DistanceCm + RelativeTransform.X`
  (`InfinityStagePassageActor.cpp:1648-1660`). Drama runs in game worlds only (`:1620-1624`).
  **Consequence:** with today's fields, a flash (strike over `attack` cm, then Decay
  starting at 0 cm) always peaks when the camera reaches the lamp's own X.
  - **Phase A (built engine):** every flash fires from the camera's current X. Lateral,
    high, floor and behind-wing sources work. Fixtures *deeper in the bay* do not, and
    neither do blinkers seen from a distance. The decay is linear in camera travel.
- *declaration-proven*: there is no camera anchor for attachments. The anchors are
  Station, Left, Right, Top and PairCentre (`InfinityStageTypes.h:149-159`).
  - The rig's `FollowLight` is a fixed on/off spot with no drama
    (`InfinityStageCameraRig.h:50-71`, `.cpp:117-148`).
  - So the "camera" flash is a Station lamp placed on the camera path (Y 0, Z 150 + 25)
    at the trigger X.
  - *inferred*: camera height 150 cm is taken from P01's start; P04 has not been
    measured. The camera may wander sideways; an error of a few cm is irrelevant to
    a 60° flash.
- *declaration-proven*: the effect-source linked light cannot blink rarely.
  - Its flicker is a sum of three sines, so it is continuous and quasi-periodic
    (`InfinityStageEffectSource.cpp:218-224`).
  - Its pump is strictly periodic (`:193-216`).
- **Held patch** `Scripts/patches/2026-10-04_LD_flash_events.draft.patch` (150 lines, unapplied):
  - Adds `bFlash`, `FlashCameraOffsetsCm[]`, `FlashAttackCm`, `FlashDecayCm` and
    `FlashRestScale` to `FInfinityStageLightDrama`.
  - Adds a pure `EvaluateFlash` with a cubic fall, ORs it into `IsActive`, and adds it
    to the visibility switch in `ApplyToLamp`.
  - Adds one automation test, `InfinityStage.LightDrama.FlashIsBriefAndKeyedToDistance`.
  - Defaults are off, so every existing lamp is unchanged.
  - Status: *measured* that `git apply --check` is clean. **Not compiled.** Applying it
    is `git show`/`git apply` in a build window, per the held-patch convention.
  - The negative offsets decouple the trigger from the lamp's X. That makes deep
    fixtures and many-blink lamps possible.
  - The tool probes for the field (`_probe_capabilities`) and only emits Phase-B rows
    when the field exists.
  - After the build, `_infinity_attachment_state.DRAMA_FIELDS` must gain the five new
    fields. Until then, read-back does not see them. *inferred* risk: low, because
    labels and GUIDs still cover add and remove.
- **Speed coupling.** *inferred*: P04 camera speed is about 59 cm/s. That comes from
  the looks run `LightingLooks/20261004_001334` (8.44 s per bay) against a 500 cm bay
  spacing, which is itself inferred from two live light X values.
  - Flash length in seconds therefore depends on camera speed. **If the camera stops
    inside a flash window, the light holds** until it moves again.
  - DRY re-measures the bay spacing from station transforms. It does *not* re-measure
    speed.
  - Before APPLY, check that P04 has no stop or vamp inside bays 1-6.

## Exposure

- *declaration-proven via memory* (`puss-capture-exposure-convention`, measured by Rig
  30 Sep): the show renders through one unbound PPV with Histogram min = max = EV100 -3.
  With exposure pinned, a flash cannot make it pump.
- The tool's DRY reads every PPV read-only, and APPLY refuses with `EXPOSURE_NOT_PINNED`
  if exposure is not pinned. *inferred*: the UE 5.8 Python property names
  (`auto_exposure_min_brightness` and related) are unverified. A wrong name stops the
  run. It does not pass silently.
- Captures must use no exposure override. Never use Manual plus bias.

## Conflict: P04 black vs the looks prototype

*declaration-proven*: `lighting_looks_revert_record.json` is `saved_readback_verified`
(run 20261003-201156) on P04 Wing 001-006, the same six bays.

- **Any events write on bays 1-6 breaks the looks REVERT.** That includes the moody
  blinkers. The looks revert requires those cues to equal its `after_rows` exactly
  (`lighting_looks_apply.py:1081-1083`), so it would refuse with
  `REVERT_CURRENT_STATE_DRIFT`.
- **Rule:** revert the events tool *before* any looks REVERT, re-APPLY or tune. The
  events REVERT restores the cues exactly to their state before the events APPLY.
  That state is the looks' `after_rows`, so the looks tool can then proceed.
- **Black mode turns off the looks lights in bays 1-6.** The tunes 1-3d that Gary
  approved go dark there while black is on. They come back on revert. Gary chooses one:
  - (a) black over bays 1-6 and the looks move elsewhere;
  - (b) black on other P04 bays (needs a bay list edit and the budget re-proved);
  - (c) blinkers and polaroids only, layered on the looks.
- **Gates in the config.** APPLY refuses unless `black_mode.gary_approved` is true and
  `conflicts.allow_over_looks_prototype` is true. Both ship false.
- **Shadow budget.** *measured* on the fixture: the black mode adds 10 casting flashes
  (camera and back-lights). That fits only because it frees the looks' 2 casters per
  bay. On bays without the looks it exceeds the P04 budget and the tool refuses.
- **Emissive bodies.** The looks' practical BODY props stay enabled in black mode. If
  they are emissive they will glow. DRY lists them under `enabled_props_left`.
- **Spill from neighbours.** Light from bay 7 and from neighbouring passages can spill
  into the black bays. That cannot be modelled offline.

## Tool and harness

- `Saved/CodexConductor/lighting_events.json` holds the seed, the sources, the black
  sequence, the blinkers and the gates.
- `Saved/CodexConductor/lighting_events_apply.py` has three modes, DRY, APPLY and
  REVERT; DRY is the default. Run it as `LIGHTING_EVENTS_MODE` through the guarded
  ExecuteProjectPythonFile route.
  - Cue labels are resolved once to an index and a CueGuid. After that every write is
    GUID-keyed, and new attachments are recorded by their minted GUIDs.
  - GUID minting follows the looks tool's proven scratch-replicate route.
  - APPLY backs up to `Backups/PreLightingEventsP04-<run>`.
  - Every run has a census check, an outside-target hash guard, a narrow Show and level
    save, a read-back, and a SavedMasterMatchesShow test queued on its own.
  - Log markers are `LIGHTING_EVENTS_{DRY,APPLY,REVERT}_OK|run=...` and
    `LIGHTING_EVENTS_STOPPED`.
  - The tool does **not import** `lighting_looks_apply.py`, because importing it runs
    that tool's `main()` (`:1276-1277`). It loads `_infinity_attachment_state.py`
    fresh by path.
- `Saved/CodexConductor/test_lighting_events_apply.py` has 27 tests, all passing
  (*measured* 4 Oct). Negative controls cover:
  - periodicity: an exact period and a ±5%-jittered period are both rejected; seeded
    blinkers pass for 10 seeds (CV about 0.84, autocorrelation peak about 0.15);
  - flash shape: the looks keying and a slow ramp are rejected;
  - black mode: a looks light left on, and a flash set to HOLD, both produce violations;
  - determinism: a different seed differs, and a blinker change does not re-roll the
    black train;
  - single draw per expression: an AST check, which flags a deliberate two-draw line;
  - outside-hash change, shadow budget overflow, and Phase-B rows without the engine
    are each detected or refused.
  - The C++ port matches the existing C++ test's values.
- **Unverified until an editor run:**
  - the Python names on the PPV and `get_attachment_anchor_world_transform` (out-param
    form);
  - whether `replicate_light_attachments` mints enough vessels when a black bay
    carries 6 events plus 10 existing lights;
  - how a flash actually looks. Intensities (6000-9000 cd) are *inferred* first values
    for Gary to tune against the pinned EV -3.
