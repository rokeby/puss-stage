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
