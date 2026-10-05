# Spec: strobe with ghosting (Cueing stream, 5 Oct)

**Gary's words, as corrected by the conductor:** "the ghosting that happens for about a third of a second after a strobe light takes place".

**Patch:** `Scripts/patches/cueing_S1_strobe_light.patch`. It is held, adds new files only, and is unbuilt.

## Layer 1: the light's tail (built into the patch; the cheap default)

`AInfinityStageStrobeLight` is a placeable actor with a point light. Shadows are off, for cost.

**Settings.** All of these can be keyed in Sequencer, so a cue can switch the strobe or change its rate: Period, Flash, Decay (default **0.33 s**), Peak cd, Colour and Phase. Two more are not keyable: Enabled, and the segment filter, which is a list of Passage or Scene GUIDs.

**Timing:** the pure function `InfinityStageStrobe::LevelAt`. The flash holds at 1, then decays exponentially and is cut to black at Decay.
- In PIE it runs on the **Master clock**, through ShowRoot's transport, so it is deterministic on scrub, reverse and re-run.
- In the editor viewport it is a free-running preview [inf: it does not follow the Sequencer playhead].
- Between flashes the light is switched off (`SetVisibility(false)`), as Light Drama does.

## Layer 2: the camera ghost

**2a, built into the patch; the cheapest credible version.**
- The strobe's optional `GhostVolume` is a Post Process Volume whose settings *are* the ghost look, for example bloom up, exposure bias up and a tint. That look is Gary's to set.
- The strobe drives only its `BlendWeight`: full at the flash, then fading over `GhostSeconds` (default 0.33), in phase with the flash. This happens in game worlds only, so the saved level keeps the authored weight.
- **Declared:** `APostProcessVolume::BlendWeight` and `bUnbound` (`Engine/Classes/Engine/PostProcessVolume.h:43,51`); `BloomIntensity`, `AutoExposureBias` and `WeightedBlendables` in `FPostProcessSettings` (`Engine/Classes/Engine/Scene.h:1629,1933,2575`).
- **Inferred:** a bloom and exposure swell that fades over 0.33 s reads as an after-flash ghost. It is a whole-image glow, *not* a retained image of the flash frame.

**2b, spec only; the true afterimage.**
- A `USceneCaptureComponent2D` with `bCaptureEveryFrame` off calls `CaptureScene()` once per flash. That is declared at `SceneCaptureComponent2D.h:299` and `SceneCaptureComponent.h:85`.
- The capture writes to a render target. A post-process material (a blendable on the ghost volume) mixes that render target over the scene, fading over about 0.33 s. When the camera moves, the frozen flash image then trails behind as a ghost.
- **Inferred:** a PP material can sample a render target as a texture parameter (standard material usage, not checked here).
- **Cost:** one extra scene render per flash, not one per frame.
- **It needs content:** a material and a render-target asset, which are Gary's look to approve.

**Recommendation:** try 2a first; it costs nothing and you tune it in the volume. Build 2b only if 2a doesn't read as ghosting.

## Tests (pure, with controls)

- `InfinityStage.Strobe.FlashThenAfterglow`: shape, black after decay, a zero-decay control and a zero-period control.
- `InfinityStage.Strobe.DeterministicOnMasterTime`: reverse visiting gives identical levels; the strobe repeats each period; phase shifts the flash, checked against a no-phase control.
- `InfinityStage.Strobe.SegmentFilter`: an empty filter means active everywhere; an unlisted segment stays dark (control).

## Open questions for Gary (to ask in the build window, not now)

- The default rate: once per second, or faster?
- Is a point light right, or does he want a spot aimed at the floor?
- Does he want the 2a look preset by the stream (as a starting point), or will he set it himself?

## Built (2497c96, suite 145/0) and Gary's defaults (5 Oct)

**Build fix, measured by the conductor.** `CreateDefaultSubobject(..., bTransient=true)` did **not** leave `RF_Transient` on the spawned instance. The build sets it in `PostRegisterAllComponents()` instead, and `Strobe.EditorPreviewNeverPersists` is green.

**Gary's defaults:** period **1 s**, a **point light**, and a **preset subtle ghost**.

### Preset ghost volume ("PPV_StrobeGhost_Subtle")

All values are starting points, inferred and not yet seen on screen; Gary tunes them.

**Volume:**
- `bUnbound = false`. A box around the strobe's area, so the ghost happens only when the camera is in that area.
- `BlendRadius = 300 cm`, so it doesn't snap at the edge.
- `Priority = 10`, above the show's other volumes.
- `BlendWeight = 0` as saved. The strobe drives it in PIE only.
- Strobe settings: `GhostSeconds 0.33` and `GhostMaxWeight 1.0`. The ghost's strength is in the overrides below, not in the weight.

**Overrides.** Only these are enabled (`bOverride_…`); everything else inherits the show's look.

| Setting | Value | Why |
|---|---|---|
| `BloomIntensity` | **2.0** (UE default 0.675) | The flash leaves a glow that fades over 1/3 s. |
| `BloomThreshold` | **0.5** | Only the brightest areas (the wet floor, the lamp) bloom, not the whole frame. |
| `AutoExposureBias` | **+0.4 EV** | A slight "eyes still dazzled" lift. Kept small because the show's exposure convention differs from captures [memory: capture exposure convention]. |
| `SceneColorTint` | **(1.00, 1.00, 1.04)** | A barely cool afterimage. Set to (1,1,1) for neutral. |
| `MotionBlurAmount` | **0.9** (default 0.5) | If the camera is moving, the 1/3 s smears slightly: a cheap ghost trail. |
| `MotionBlurMax` | **8 %** | Caps the smear. |

**Because BlendWeight interpolates each override from the show's value to these** [inf: standard PPV blending], the peak only occurs right at the flash.

**If it's too strong:** lower `GhostMaxWeight`. That keeps the look's shape and scales the whole ghost.

**If it doesn't read as ghosting:** build route 2b, the true retained-frame afterimage (above).
