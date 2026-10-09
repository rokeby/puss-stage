# P46b — extend the HELD P46 shadow-cat patch: POV camera follows actions, body visibility modes (Codex, offline)

Read `_house_rules.md`; all rules apply. Extend `Scripts/patches/2026-10-09_shadow_cat_actions.patch` (HELD; never
build). Base it on the current patch and README in `Tools/ShadowCatActions/`, and keep all existing tests passing.

## Gary's direction (9 Oct, his words condensed)
- Puss is only ever seen from his own POV, in reflections and in shadows. Every action is only as useful as the
  shadow, the reflection, or the camera's ability to follow it.
- **While moving:** walk only. Trot ≈ walk, and could stand for the GO1's other gait. GO1 note:
  - its stair-climbing gait is the steady default;
  - its regular walk is for the running treadmill.
- **During breaths (scripted; the rehearsal knob is WHEN), the wanted actions:**
  1. **Stretch** (Idle_Stretching): we should SEE Puss's front paws reach out in front of the eye camera.
  2. **Look down** (Idle_LookDown) into a puddle or a shiny wet patch, and see his own face reflected.
  3. **Sharpen claws** (Action_SharpensClaws) on a wing during a breath. Test idea: in P06 this is what topples the
     wings (the domino finale, job 37). The camera and cat leave the main route for that moment.
  4. **Sit and lick** (Action_Licking_sit), with the paw visible to the camera.
  5. **End of show:** Puss falls asleep (Rest_Sleep_to / Sleep_idle, or Lie_to first), coordinated with the dog.
  6. **Optional:** crouch-walk (Move_Crouch_F) for the low sequence in P05. The dog can't crouch, so it's low
     priority.
- **The camera should be smarter "Puss's eyes".** During an action it follows the cat's head. The cat's head and body
  must never block the lens, yet the body must not be fully hidden either: it has to stay in shadows and
  reflections, and paws must be visible when the action calls for it.

## Facts to build on (verify, cite)
- The camera rig owns the cat. In game the body is shadow-only (`ShouldDrawShadowCatBody`,
  `InfinityStageCameraRig.cpp:258-261`, `ApplyShadowCatBodyRendering` :264+).
- The flags `bShadowCatCastShadow`, `bShadowCatRenderInMainPass` and `bShadowCatVisibleInReflections` exist
  (`InfinityStageCameraRig.h:160-170`).
- Leaving the route needs no new system: the Passage section already has keyable LongitudinalOffsetCm,
  LateralOffsetCm, HeightOffsetCm, Pitch/Yaw/Roll and LookAhead channels (`MovieSceneInfinityPassageTrack.h:16-31`).
  An off-track move is keys on those channels during the breath, and the cat rides with the rig. Confirm the cat
  follows those offsets.

## Build (in the held patch)
1. **Per-action `CameraMode`:**
   - `Route` (today's behaviour);
   - `HeadPOV`: the camera blends (BlendIn/Out) to a socket/bone on the cat's head (the eye midpoint; pick the bone
     from the AnimX skeleton names; give an offset arg) and follows it, Master-time-locked. That gives a real POV
     during the stretch, look-down, licking and sleep.
   - Any GO1 coupling stays outside: the camera pose is the score.
2. **Per-action `BodyVisibility`:**
   - `ShadowOnly` (today);
   - `POVBody`: render in the main pass but hide the head/neck from the camera (HideBoneByName on the head chain, or
     a head-masked material scalar), keep the shadow, and keep it visible in reflections;
   - `ReflectionOnly`: not in the main pass, visible in reflections plus the shadow.
   - Document what UE 5.8 actually supports for "visible in reflections but not to the camera" (Lumen/SSR vs planar
     reflection; `bVisibleInRayTracing`, `bVisibleInReflectionCaptures`, `bVisibleInSceneCaptureOnly`, owner-no-see,
     etc.) with header citations, and recommend the look-down-puddle setup (likely a planar reflection or an
     SSR-friendly wet decal). Mark it inferred where it can't be verified offline.
3. **Near-clip safety:** assert the camera's near plane never intersects visible cat geometry in HeadPOV + POVBody
   (offset forward of the eye, hidden head), so the camera never sees inside the mesh.
4. **Tests and harness:** extend them with camera-mode blend continuity, visibility-mode switching at the action
   edges, and determinism.
5. **README:** add a worked "breath recipe" for each wanted action, giving the clip, CameraMode, BodyVisibility, and
   the off-track offset keys if any. Claws-on-wing is the off-track example: the Lateral/Longitudinal/Yaw keys that
   step to a wing and back.
