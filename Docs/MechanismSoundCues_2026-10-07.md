# Wing mechanism sound cues (held patch, 7 Oct 2026)

**Status: NOT APPLIED, NOT COMPILED.** The patch is
`Scripts/patches/2026-10-07_mechanism_sound_cues.patch`. It applies cleanly to
4c110e4 (`git apply --check`, measured). It has never been built, so every claim
below about compile or runtime behaviour is **[inf]** until a build window runs
it.

Apply it only inside a build window you own. Use the committed blob:
`git show <commit>:Scripts/patches/2026-10-07_mechanism_sound_cues.patch | git apply`.

## Goal (Gary, 7 Oct)

Wing mechanisms should make sound, including a slam when a toppling wing hits
the floor or a neighbour. The sound must follow any re-time, so it cannot be a
Master sequencer key.

## What existed before the patch

- **[decl]** `FInfinityMechanismSoundSet` is at `InfinityStageTypes.h:396-426`
  (HEAD numbering). `FInfinityPassageSettings::MechanismSound` is at `:961`, and
  `FInfinityWingOccurrence::bMuteMechanismSound` is at `:737`.
- **[decl]** Nothing played them. In `Plugins/InfinityStage/Source`:
  - `MovementThreshold` and `AudibleRadiusCm` are read in no `.cpp`.
  - No runtime `.cpp` calls `PlaySound*`, `SpawnSound*` or uses an audio
    component. The only `UAudioComponent` is the Cue Desk music preview
    (`SInfinityStageCueDesk.h:278`).
  - The only consumer of the set was `GetMechanismSoundIndexForCue`
    (`InfinityStagePassageActor.cpp:2033-2098`), and only tests called it
    (`InfinityStageCompilerTests.cpp:1723-1790`).
- **[decl]** The phase is `PhaseOffset + Seconds * Rate` (`PassageActor.cpp:1424`
  at HEAD). OneShot clamps it to 0..1 (`:1429-1432`). Loops wrap it (`:1435`).
  The curve is evaluated at that phase (`:1459`). The camera rig calls it every
  evaluation (`InfinityStageCameraRig.cpp:530`).

## Design

### Authoring: `FInfinityMechanismMotion::SoundCues`

The new type is `FInfinityMechanismSoundCue`, in the new header
`Public/InfinityStageMechanismSound.h`. Each pair's `Mechanism` gets a
`TArray<FInfinityMechanismSoundCue> SoundCues`, which is empty by default.

| Field | Meaning |
|---|---|
| `Label` (FName) | For authoring and logs, e.g. `slam_floor`. Tests match on it. |
| `Phase` (0..1) | Where in the motion the sound starts: 0..1 of a OneShot, or of every cycle of a loop. |
| `Side` | `Pair` places the sound at the pair's station root. `Left`, `Right` and `Top` place it at that panel's evaluated pose. |
| `Sound` | A soft `USoundBase`. An empty sound makes the cue a no-op. |
| `VolumeMultiplier`, `PitchMultiplier` | Passed straight to `PlaySoundAtLocation`. |
| `LocalOffsetCm` | Offset in the panel's frame (or the station's frame for `Pair`). For example, the top edge that hits the floor. |
| `AttenuationOverride` | Optional `USoundAttenuation`. If it is empty, a transient sphere is used: linear falloff, a 200 cm inner radius, and an outer radius equal to the Passage set's `AudibleRadiusCm`. The sound is therefore always spatialised. |

The patch also adds `FInfinityMechanismSoundSet::bMuteSoundCues`, a
Passage-level mute that defaults to false.

**Why the cues ride the phase.** A cue sits on the same phase axis as the curve
keys. Anything that moves the motion therefore moves the sound with it:
`PhaseOrigin = PassFrame` re-times, `ExplicitOriginFrame`, the rate, the offset,
and even the wing-modulation rate integral (`:1396-1411`). The slam always lands
on the visual key at that phase **[inf]** (same expression, not run).

### Runtime: `AInfinityStagePassageActor::EvaluateMechanismsInternal`

1. **Worlds.** The runtime runs only when `GetWorld()->IsGameWorld()` (PIE or
   game), a `Route` exists, and the CVar `InfinityStage.MechanismSound.Enable`
   is not 0 (default 1).
   - Editor worlds never make a sound. This covers the Cue Desk scrub
     (`SInfinityStageCueDesk.cpp:4998`) and authoring evaluation.
   - This matches the existing Light Drama gate (`PassageActor.cpp:1628` at HEAD).
2. **Freeze outside the Passage.** The existing early return for a frame outside
   `[SegmentStart, SegmentEnd]` now also clears the sound history. Re-entering a
   Passage records history first and fires nothing.
3. **History.** Each (cue, panel side) stores the last phase and normalized
   travel. Pair-level sound uses its own key, `0xFF`, and is voiced once per pair
   per evaluation on the pair's first materialized panel. That is the Left panel,
   because `AddPanelInstance` adds Left first (`:844-846` at HEAD).
   - Loops store the **unwrapped** phase, so a cue repeats every cycle and a cue
     near 0 still fires across the wrap.
4. **Forward-playback gate** (`IsForwardPlaybackStep`). A step can fire only when
   all of these hold:
   - `0 < ShowDelta`
   - `ShowDelta <= MaxStepSeconds` (CVar, default 0.25 s)
   - `ShowDelta <= RealElapsed × MaxRateRatio + 1/60 s` (CVar ratio, default 1.5)

   `RealElapsed` is the difference in `UWorld::GetTimeSeconds()` between
   evaluations. So pause, rewind, a jump, a scrub and the 4x hold-right
   fast-forward (`FastForwardRate` 4, `HoldRightFastForwardTests.cpp:19`) fire
   nothing. Every step still updates the history, so **a rewind re-arms** the
   cue.
5. **Crossing rule** (`CrossesForward`):
   - OneShot or CameraGust fires on `Prev < Cue <= Curr`.
   - A loop fires when some integer k satisfies `Prev < k + Cue <= Curr`.
   - A cue at exactly 0 cannot fire on a OneShot. Use a small positive phase.
6. **Mutes.** `WingPair.bMuteMechanismSound` and the Passage-level
   `MechanismSound.bMuteSoundCues` both silence the cues.
7. **Audible radius.** A sound farther than `AudibleRadiusCm` from the camera's
   rail point (the route at the evaluated camera distance) is skipped.
8. **Loading.** On the first game-world evaluation in a Passage, the actor
   synchronously loads every cue sound, every attenuation, and (if the set is
   enabled) every set sound. It keeps them in a `Transient` `UPROPERTY`. A cue
   therefore never loads mid-show, apart from one case: the Show edited during
   PIE.
9. **Playback.** `UGameplayStatics::PlaySoundAtLocation(this, Sound, Location,
   FRotator::ZeroRotator, Vol, Pitch, 0, Attenuation, nullptr, this)`. This is
   fire-and-forget, and the overload is declared at `GameplayStatics.h:732`
   **[decl]**. A `Verbose` log line `INFINITY_STAGE_MECHANISM_SOUND` is written
   per fire.

### The existing set, wired as a "start" sound

When `MechanismSound.bEnabled` is true, a pair's chosen set sound
(`GetMechanismSoundIndexForCue`, which already respects the pair mute) plays at
the station. It plays once when the pair's travel magnitude first rises through
`MovementThreshold` on a forward step, with volume `Gain`. It reuses the same
gate, so the cost is small.

**Risk [inf]:** if any Show already has `MechanismSound.bEnabled = true` with
sounds, that Passage will start making sound after this patch. Its default is
false (`Types.h:402` at HEAD), but I did not read the Show asset, so this is
**UNCLEAR**. Check it with Python before the build window, or set it false.

### Determinism

- No random draws are added. The set's `StableRandom` choice is the existing
  GUID hash.
- With `SoundCues` empty and the set disabled, nothing new runs except
  bookkeeping: a history map per panel in game worlds only. Panel transforms are
  computed exactly as before, because the sound block reads them but never
  writes them **[decl, by reading the diff]**.

## Authoring a slam from the topple solver

The solver output is
`DerivedAssets/FlatV3/Review_2026-10-07/p06_plan/topple/variant_<V>.json`. It
has `rows[k]` with `start_s`, `duration_s` and `CycleRateHz`, and `events[]`
with `t`, `type` (release, snag, domino, floor, wall, rest) and `slab`.

For an impact event on slab k, the phase on row k is:

```
phase = (t - rows[k].start_s) / rows[k].duration_s     # = (t - start_s) * CycleRateHz
```

**Worked values for variant C (chain4_away)** (measured, by running the formula
on the JSON):

| Event | Row (slab) | t (s) | Cue phase on that row |
|---|---|---|---|
| domino, slab 0 hits slab 1 | 0 | 4.0896 | 0.49164 |
| domino, slab 1 hits slab 2 | 1 | 5.0558 | 0.22849 |
| domino, slab 2 hits slab 3 | 2 | 5.6817 | 0.19184 |
| floor 1 | 3 | 6.7462 | 0.40374 |
| floor 2 (bounce) | 3 | 7.4171 | 0.65816 |
| floor 3 (settle) | 3 | 7.7179 | 0.77226 |

- **Put a domino hit on the striker's row.** The struck row starts moving at that
  same instant, so its phase is exactly 0, and a OneShot cue at 0 never fires.
- Use `Side = Left` or `Right` for the panel that actually falls, with
  `LocalOffsetCm` at its top edge. Use `Pair` if both panels fall together.
- The bounces can share one sound at a lower `VolumeMultiplier`.

Python shape, with snake_case per UE's reflection (**[inf]**: not run):

```python
cue = unreal.InfinityMechanismSoundCue()
cue.set_editor_property("label", "slam_floor")
cue.set_editor_property("phase", 0.40374)
cue.set_editor_property("side", unreal.InfinityMechanismSoundCueSide.LEFT)
cue.set_editor_property("sound", unreal.load_asset("/Game/.../SC_FlatSlam"))
motion = row.wing_pair.mechanism        # copy, edit, write back
motion.sound_cues = list(motion.sound_cues) + [cue]
```

Follow the usual rules for this: back up the Show first, make a narrow edit,
read it back, and save only the Show.

**Trap [inf]:** a tool that assigns a whole `FInfinityMechanismMotion` (for
example a movement-preset applier) replaces `SoundCues` with the preset's
version. I searched the plugin C++ for whole-motion assignment and found none. I
did not search the `Saved/` Python tools.

## Tests added

They are in `InfinityStageTests/Private/InfinityStageMechanismSoundTests.cpp`.
All are EditorContext | EngineFilter.

1. `InfinityStage.MechanismSound.CrossingRule` is pure. It covers:
   - OneShot boundaries, including a landing exactly on the cue, a start on the
     cue, rewind, pause, a cue at 1, and a cue at 0.
   - Loop wrap and repeat.
   - A 300-step run that fires once for a OneShot and three times over three
     loop cycles.
   - The playback gate: 1x, a hitch, pause, rewind, 4x FF, a jump, and
     MaxStepSeconds.
   - The movement threshold, by magnitude and upward only.
2. `InfinityStage.MechanismSound.CollectRespectsSideMuteAndEmpty` is pure. It
   covers:
   - The defaults are empty and unmuted.
   - An empty list fires nothing.
   - Side filtering.
   - A null sound fires nothing.
   - Authored order.
   - Mute.
3. `InfinityStage.MechanismSound.PassageFiresOnForwardPlaybackOnlyInGame` uses
   the actor. It follows the BulbBody fixture pattern: build in an EditorPreview
   world, then retype it to Game. The actor runs in a dry-run test seam that
   records labels instead of playing. It checks:
   - An editor world fires nothing.
   - Forward playback fires each cue once, in phase order.
   - Pause fires nothing.
   - A rewind fires nothing, and the cues re-arm and fire again.
   - A forward jump fires nothing.
   - Leaving the Passage forgets history, so arriving just past a cue fires
     nothing.
   - The pair mute and the Passage mute both silence the cues.
   - A positive control: unmuted, the cues fire again.
   - An empty list fires nothing.

   **[inf]** This test depends on a world that never ticks, so that
   `GetTimeSeconds()` stays constant. It steps 0.01 s, which is inside the 1/60 s
   slack.

## Unverified, because nothing was compiled

- **Header-checked [decl]:**
  - `UGameplayStatics::PlaySoundAtLocation` (ENGINE_API overload, `GameplayStatics.h:732`)
  - `USoundAttenuation::Attenuation` (`SoundAttenuation.h:458`)
  - `FSoundAttenuationSettings::bAttenuate` and `bSpatialize` (`:154`, `:158`)
  - `FBaseAttenuationSettings::{DistanceAlgorithm, AttenuationShape, AttenuationShapeExtents, FalloffDistance}` (`Attenuation.h:64-95`)
  - `EAttenuationDistanceModel::Linear` (`Attenuation.h:18`)
  - `UWorld::GetTimeSeconds` and `IsGameWorld` (`World.h:2847`, `:4172`)
  - `USplineComponent::GetLocationAtDistanceAlongSpline` and `GetTransformAtDistanceAlongSpline` (`SplineComponent.h:727`, `:778`)
  - `AActor::GetActorNameOrLabel` (`Actor.h:1242`)
  - `FVector::ToCompactString` (`Vector.h:871`)
  - `TSet::Add(…, bool*)` (`CompactSet.h.inl:699`)
  - `GetTypeHash(TTuple)` (`Tuple.h:582`)
  - `FMath::FloorToDouble` (`GenericPlatformMath.h:296`)
- **Not verifiable here [inf]:**
  - UHT accepting the new USTRUCT header, which is included from
    `InfinityStageTypes.h`.
  - The shadow-variable rules, which are errors in UE.
  - Whether `PlaySoundAtLocation` is audible in this project's PIE setup
    (audio device, listener on the camera rig).
  - The fallback attenuation's audible character.
  - Whether the Sequencer's evaluation cadence in PIE always passes the
    1.5x + 1/60 s gate at 1x. If cues go silent at 1x, raise
    `InfinityStage.MechanismSound.MaxRateRatio`.
- **Build window checks:**
  - UTF-8 test names in the Tests DLL, for example
    `PassageFiresOnForwardPlaybackOnlyInGame`.
  - The UTF-16 runtime literal `INFINITY_STAGE_MECHANISM_SOUND` in the
    InfinityStage DLL.
  - Both with +/- controls.
  - Run the narrow suite and compare against the 29-warning baseline.
