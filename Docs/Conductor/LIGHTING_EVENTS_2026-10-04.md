# Lighting events: polaroid flash, rare blinkers, black passage (4 Oct, offline)

Gary's notes (3 Oct, verbatim in `Saved/CodexConductor/specs/LIGHTING_LOOKS_P04_TUNE1.md:53-63`)
ask for three things: a polaroid flash, rare bright blinkers in moody bays, and one passage
kept almost black and shown in trickles of flashes. The flare sweep is being built by
another agent and is not covered here.

**Decision (Gary, 4 Oct questionnaire): black mode goes on P06 bays 2-10, not P04.** The
tool and config were retargeted the same day (section "P06 retarget" below). The P04
looks-prototype conflict that the first draft gated on no longer applies.

Nothing here has run in Unreal. Every claim is tagged: **declaration-proven** (read in
source or config), **measured** (an offline run of the harness, or a read of a saved live
dump), or **inferred**.

## What Gary will see

- **Polaroid flash.** A cool-white (6500 K) hard burst from just above the lens. It
  reaches full brightness in about 1.5 frames and is gone in 0.3 s. Everything in front
  of the camera shows up flat and frontal for an instant, then goes black again.
  - *measured* (harness, Python port of the C++, at the P06 speed of 250 cm/s): built
    engine gives 1.49-frame attack, half-level at 0.15 s, off by 0.29 s.
  - *measured*: with the held patch the fall is cubic: half-level at 0.06 s, off by 0.22 s.
- **Black passage (P06 bays 2-10 of the 64-cue layout).** The only steady light is a
  faint warm glimmer along the left floor edge of each bay, 8 cd, capped at 15. On top of
  that come bursts of 2-5 flashes, with 6-18 s of darkness between bursts. About 40% of
  flashes come from the camera; the rest from high side, floor grazers and back-lights.
  - *measured* (`black_schedule`, seed 20261004): the nine bays last **15.4 s** at
    250 cm/s, and the train is **one burst of 2 flashes** (camera at ~2.0 s, BACK_L at
    ~2.7 s), then ~12.7 s of glimmer only. Across seeds 20261001-10: 2-7 flashes in 1-2
    bursts.
  - **For Gary:** the sequence values (6-18 s dark gaps) were sized for P04's ~50 s at
    59 cm/s. On P06's 15 s window they give a single trickle. If that is too sparse,
    shorten `black_mode.sequence.dark_gap_s` or change the seed; both are creative calls
    and were not changed.
- **Blinkers.** Disabled in the config since the retarget: they were anchored to P04's
  looks practicals, and re-homing them is a separate call. They also need the held patch.

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
  **Consequence:** with today's fields, a flash always peaks when the camera reaches the
  lamp's own X.
  - **Phase A (built engine):** every flash fires from the camera's current X. Lateral,
    high, floor and behind-wing sources work. Fixtures *deeper in the bay* do not, and
    neither do blinkers seen from a distance. The decay is linear in camera travel.
- *declaration-proven*: there is no camera anchor for attachments. The anchors are
  Station, Left, Right, Top and PairCentre (`InfinityStageTypes.h:149-159`).
  - The rig's `FollowLight` is a fixed on/off spot with no drama
    (`InfinityStageCameraRig.h:50-71`, `.cpp:117-148`).
  - So the "camera" flash is a Station lamp placed on the camera path (Y 0, Z 150 + 25)
    at the trigger X.
  - *inferred*: camera height 150 cm is taken from P01's start; P06 has not been measured.
- *declaration-proven*: the effect-source linked light cannot blink rarely
  (`InfinityStageEffectSource.cpp:218-224` three sines; `:193-216` periodic pump).
- **Held patch** `Scripts/patches/2026-10-04_LD_flash_events.draft.patch` (unapplied,
  not compiled; `git apply --check` clean, *measured* 4 Oct). Adds `bFlash`,
  `FlashCameraOffsetsCm[]`, `FlashAttackCm`, `FlashDecayCm`, `FlashRestScale`; the tool
  probes for them and emits Phase-B rows only when they exist. After the build,
  `_infinity_attachment_state.DRAMA_FIELDS` must gain the five fields.
- **Speed coupling.** *inferred*: P06 camera speed is 250 cm/s. Basis: W&T's interleave
  holds P06's distance AND duration (63 intervals re-split from today's 54 x 48000 frames
  = 108 s over 27,000 cm; `Saved/CodexRuns/slots/P6_additive.md`, "4 Oct (later)"). It
  assumes a constant walk; P06's camera score was not read.
  - Flash length in seconds depends on camera speed. **If the camera stops inside a flash
    window, the light holds** until it moves again. Before APPLY, check that P06 has no
    stop or vamp inside bays 2-10.
  - *inferred*: bay spacing 428.571 cm = 27,000 / 63 (`p6_core.py:101-108`). DRY
    re-measures it from station transforms (tolerance 15%); it does not re-measure speed.

## P06 retarget (4 Oct)

### Layout gate: applies only after W&T's P6 lands

- *declaration-proven*: W&T's interleave re-splits P06 into **64** WingPair cues
  (`Saved/CodexFlatV3/p06/run_p6.json` `result_count` 64, `expected_compiled_wings` 64).
  The 9 restored cues are labelled `P06 OLD NN - family` (`p6_workflow.py:387`).
- *measured* (saved-state dump `Saved/CodexConductor/light_guid_audit_20261004-102539.json`):
  P06 has **55** WingPair cues today.
- The tool resolves bays as **WingPair ordinals** inside the `Passage 6` PassageSettings
  range: a first..last walk (`resolve_passage_bays`), then in Unreal the Show's own
  `GetWingPairCueGuidsInPassage`, which must agree (`_require_show_resolution`, same route
  as `lighting_scores_apply.py`). It never finds a cue by label; labels are a drift guard
  (`^P06 (Wing \d{3}|OLD \d{2} - .+)$`).
- It refuses with `CUE_COUNT_NOT_POST_INTERLEAVE|expected=64|actual=55` until the
  interleave lands. The count is `passage.expected_cue_count` in the config.
- *inferred* from W&T's plan (`p06_interleave_plan_v3.json` `order_rows`), not live: bays
  2-10 will be Wing 037, 002, OLD 02 (restored, lights cloned from Wing 008), 003, 038,
  004, 036, 005, 039. DRY prints the live resolution (`resolved_black_bays`).

### Ownership vs the lighting scores tool

The simplest safe interlock is a declared hand-over, checked from both sides:

- **Scores side (edited):** `lighting_scores.json` `passages.P06.yield_to_events` declares
  bays 2-10, `layout_bay_count` 64, owner `lighting_events_apply.py black_mode`.
  `lighting_scores_apply.py` `yield_state` skips those ordinals (no fixtures, existing
  lights untouched, reported in `skipped` with the owner) **only when P06 resolves to 64
  bays**. At today's 55 the yield is DORMANT and the P06 score is unchanged (*measured*,
  scores harness section 11). The scores tool also avoids yielded cues as its scratch cue.
- **Events side:** `scores_interlock` refuses unless the yield covers exactly the black
  bays at the same layout count (`SCORES_DO_NOT_YIELD_BLACK_BAYS`,
  `SCORES_YIELD_LAYOUT_MISMATCH`). It also refuses if an active (non-terminal)
  `lighting_scores_record_P06.json` targets any black bay (`BLACK_BAYS_CARRY_ACTIVE_SCORE`:
  revert that score first).
- The events revert record names **only** the nine black bays' GUIDs (the full bay list
  is stored as a hash). The scores tool's foreign-record scan therefore does not trip on
  the rest of P06.
- **Still needed on the scores side when P06 is rescored to 64 bays:** the P06
  `cue_label_drift_guard` `^P06 Wing \d{3}$` refuses W&T's restored labels
  (`CUE_LABEL_DRIFT`, *measured* in the cross-tool harness test). The rescore must widen it,
  e.g. to the events tool's guard. Its `expected_bay_count`/segments must move to 64 anyway.

### Shadow budget (P06's own; no reliance on the looks)

- *measured* (saved dump, 4 Oct): every P06 cue has 10 lights, 9 enabled, with 2 enabled
  casters (Entry Top, Entry Fwd +Y). Wing 044 adds a casting Blink Spot. Wing 055 adds a
  casting `FX TEST - S6 Candle Light`. That is 112 enabled casters across today's 55 cues.
- Black mode disables every enabled light in bays 2-10. On the 64-cue model that frees 18
  casters, and the seed-20261004 train adds 2 (camera + BACK_L). P06 goes from 130 to 114
  (*measured* on the model; *inferred* for the live 64-cue Show, where restored cues'
  lights are cloned from current cues per `p6_workflow.py:369-379,415`).
- The rule stays `after <= before` over all WingPair cues of the P06 range. The P04 looks'
  casters are not counted (harness control).

## Exposure

- *declaration-proven via memory* (`puss-capture-exposure-convention`, measured by Rig
  30 Sep): the show renders through one unbound PPV with Histogram min = max = EV100 -3.
  With exposure pinned, a flash cannot make it pump.
- DRY reads every PPV read-only; APPLY refuses with `EXPOSURE_NOT_PINNED` if it is not
  pinned. *inferred*: the UE 5.8 Python property names are unverified; a wrong name stops
  the run.
- **Spill.** Bay 1 (grand gold) and bay 11 stay lit and can spill into the black bays.
  That cannot be modelled offline.

## Tool and harness

- `Saved/CodexConductor/lighting_events.json`: passage P06, expected cue count 64, black
  bays 2-10, `gary_approved` true, `decided_by` "Gary 4 Oct questionnaire: P06 bays 2-10",
  `ownership` block, blinkers disabled.
- `Saved/CodexConductor/lighting_events_apply.py`: DRY (default), APPLY, REVERT through the
  guarded ExecuteProjectPythonFile route with `LIGHTING_EVENTS_MODE`.
  - Every write is GUID-keyed; new attachments are recorded by their minted GUIDs (the
    looks tool's scratch-replicate route). The scratch cue is a non-target P06 WingPair
    that is also not owned by an active score.
  - APPLY backs up to `Backups/PreLightingEventsP06-<run>`, and checks census, the
    outside-target hash, a narrow Show + level save and a read-back. It then queues
    SavedMasterMatchesShow on its own.
  - Markers: `LIGHTING_EVENTS_{DRY,APPLY,REVERT}_OK|run=...|passage=P06...`,
    `LIGHTING_EVENTS_STOPPED`. REVERT refuses a record from another passage.
  - **Ordering:** revert this tool before any W&T re-split of P06 (interleave revert or
    redo), and before any scores APPLY that would target these bays.
  - It imports neither the looks tool nor the scores tool. It reads `lighting_scores.json`
    as JSON only.
- `Saved/CodexConductor/test_lighting_events_apply.py`: **41 tests, all passing**
  (*measured* 4 Oct). New controls since the retarget:
  - layout gate: 55 cues refused, 64 resolved by ordinal (restored slot included, a
    label-reusing decoy outside the range untouched), the count is configurable, a
    SEQUENCE row in range is not a bay but the same row as a WingPair trips the gate,
    label drift refused;
  - interlock: the real scores config passes; no yield, a short yield, a yield for another
    layout, and an active score on a black bay each refuse; reverted or disjoint score
    records pass. A cross-tool test runs the REAL scores tool rescored to 64: disjoint
    targets, budget held, both reverts exact. Without the yield the scores tool does
    target the black bays;
  - budget: P06 130 -> 114 on the census model; no casters to free, and an all-casting
    dense train, each refused; P04 looks casters excluded;
  - the record names only black-bay GUIDs (control: the full list would name all).
- `test_lighting_scores_apply.py`: **68/68** (*measured* 4 Oct). That is the 54 from
  before, 7 yield controls (section 11), and 7 checks a parallel session added the same
  day for `foreign_owned_lights`.
- **Unverified until an editor run:** the post-interleave Show itself (count, order,
  labels, restored cues' lights); the PPV Python names and
  `get_attachment_anchor_world_transform` out-param form; whether
  `replicate_light_attachments` mints enough vessels (10 existing lights + up to ~3 events
  per bay); P06 camera speed and stops; how a flash looks against EV -3 (intensities
  6000-9000 cd are first values).
