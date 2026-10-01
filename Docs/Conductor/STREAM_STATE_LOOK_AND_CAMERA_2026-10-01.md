# Look & camera: stream state at parking (1 Oct 2026)

Written for the next conductor and for whoever picks the stream up (Codex or Claude).
Evidence tiers follow AGENTS.md: **measured**, **declaration-proven**, **inferred**.
Status: **PARKED**. I hold nothing in the editor and no held patches; every Look & camera patch is built.

## 1. Walk-in, Interaction 1 → Passage 2 (a trial; Gary has NOT judged it yet)

Gary's ruling (30 Sep): "We teleport into the stage after the curtain drop rather than moving into it… let's
do this", a trial on I1 → P02 only, with a "slow zoom 15→35 during the walk".

**What is keyed (measured 30 Sep 20:09, read back, census clean before and after):**
- Sequence: `LS_Interaction_01_WashingTheBoy`, playback 0–638 at 25 fps (25.52 s). Soft goods lengthened it.
  Its drape holds until frame 400 (16.0 s) and then falls.
- Three tracks named **"WalkIn (Look & camera)"**:
  - a transform track on the cut's camera binding, "Interaction 1 — Stalls Camera";
  - `CurrentFocalLength` and `FocusSettings.ManualFocusDistance` on its CineCameraComponent binding. The apply
    created that binding: it did not exist before.
- 639 keys per channel, one per frame, linear interpolation.
- Last key = P02's start pose, exactly: (0, 80000, 180), yaw 22.9077, 35 mm, focus 600 cm.
- The walk: it holds the seat until **19.454 s**, then walks **1400.3 cm** to the end. It eases in over 1.0 s
  and arrives at **251.6 cm/s**, which is P02's own speed at its start, measured from two Passage poses.
- Lens: focal 15 → 35 mm (log-linear in time). Focus 100000 → 600 cm, linear in **diopters**: mid-walk it
  sits at ~1189 cm against a ~1360 cm subject. Linear in distance would hold infinity until the last ~0.4 s.
- Rotation: smoothstep from the seat to the target.
- Backup: `Backups/PreWalkInI1-20260930-200958/`.
- Commits: tools `1f9b5e8`, the diopter focus `7a5daad`.

**Knobs** (in `Saved/CodexCameraPilot/key_walkin_i1_p02.py` and `walkin_plan.py`):
- **Walk length is nearly fixed by the speed match** (declaration-proven, `walkin_plan.py:88-90`):
  duration = distance / v_end + ease / 2 ≈ 5.57 s + 0.5 s. `ease_s` lengthens it a little.
- A longer or slower walk needs one of:
  - a lower v_end, which breaks the speed match at the cut into P02;
  - a seat further back. The seat is the stalls camera's placement, from `place_transition_stalls.py`.
- `landed_s` (20.3) and `pile_edge_cm` (190): the camera may not come within 190 cm of the target before the
  drape has settled. The planner's `check_plan` enforces this.
- The zoom law (log-linear) and the focus law (diopters) live in `walkin_plan.py`.

**Changing it:**
1. Run `revert_walkin_i1_p02.py`. It removes the three named tracks, saves I1 only and prints
   `PUSS_WALKIN_REVERTED`, or `PUSS_WALKIN_REVERT_NOOP` if there is nothing to remove. It has no dry-run guard:
   running it = reverting.
2. Change the knob.
3. Run `python test_walkin_plan.py`. It must print 5 PASS.
4. Run the key script with `DRY_RUN = True`, then False, and set it back to True afterwards. The key script
   REFUSES if the named tracks exist, or if anything is dirty.
5. Success marker: `PUSS_WALKIN_KEYED|…|dirty_after={"maps": [], "content": []}`.

The revert leaves the CineCameraComponent child binding in place, with no tracks. That's harmless. For a
byte-exact revert, restore the backup `.uasset` with the editor closed.

**Extending it to the Opening → P01 and I2–I5 (only if Gary likes I1):**
- I2–I5 have stalls cameras already (declaration-proven, `place_transition_stalls.py:95-104`):
  "Interaction N — Stalls Camera", tagged `InfinityStage.TransitionStalls` and `InfinityStage.Mouth.P0{N+1}`.
- Per transition, Soft goods first lengthens the Interaction and re-fits its drape (as for I1, with `lead` =
  end − drop start). They also supply that drape's settle time (`landed_s`) from its bake
  (`Saved/CodexSoftGoods/DropBake/<bake_id>.json`).
- The key and revert scripts are I1-specific constants: `sequence_path`, `camera_label`, `camera_tags`, the
  "Passage 2" label, `minimum_end_frame` (638), `landed_s`, `pile_edge_cm`. The obvious Codex task is to
  move them into a per-transition JSON and keep `walkin_plan.py` as it is.
- **The Opening → P01 is different and unprobed** (inferred). Its camera is "Opening — Stalls Camera"
  (`place_transition_stalls.py:36`), but the Opening's sequence, cut structure and opening-reveal claim
  were never read for a walk-in. Probe it before keying.
- Inferred, unmeasured: if the dog's free look is live in an Interaction, its offset adds on top of the walk.
  Patch O resets it at the cut into P02.

## 2. The cat's ear shadow under patch T (OPEN; Gary to look in PIE)

- T (built in cc1331e) keeps the Shadow Cat's body out of the main pass, ray tracing, reflection and sky
  captures, and the depth pass in game worlds. It keeps CastShadow on.
- **Not measured.** The conductor asked Gary to look for the ear shadow in PIE instead.
- Config (declaration-proven): `Config/DefaultEngine.ini:18` sets `r.RayTracing=True`; `:22` sets
  `r.Shadow.Virtual.Enable=1`. There is no `r.RayTracing.Shadows` line, so the engine default applies.
- **Inferred:** with VSM shadows, the shadow depends on CastShadow, so it should still render. The only way T
  removes it is a light with ray-traced shadows enabled on it.
- **If Gary can't see the shadow,** write a controlled PIE check (Codex, `--unreal`):
  1. Pause the transport on a Passage frame with the shadow in view.
  2. Shot A in the current state.
  3. Shot B with a control that removes only the cat's shadow. Use a show flag or a light property, NOT a
     component property: the rig may re-apply the cat's visibility on every evaluation (inferred).
  4. Diff the two. If A ≠ B in the shadow's region, the shadow renders.
  Use `shot` screenshots: on-screen PIE recording doesn't work while the editor is in the background
  (`Docs/CodexUnrealMCPRunbook.md`).

## 3. Jump re-settle, patch S (built in 35094de)

- **Settings** (declaration-proven):
  - `UInfinityStageTransportController::JumpResettleSeconds`: default 0.1 s, ClampMin 0, 0 disables.
  - At least 2 ticks (`JumpResettleMinTicks`, in the .cpp).
  - `JumpResettleCount` (Transient) counts the fires.
  - Verbose log line: `INFINITY_JUMP_RESETTLE frame=%d` on `LogInfinityStageTransport`.
- **What it does:** after a paused jump or scrub, once the playhead has held the same frame for that long,
  it calls `SetPlaybackPosition(same frame, Jump)` once. Play, PlayTo, Shuttle, a new jump or a frame
  change cancel it.
- v2 runs it BEFORE the Passage reassert, so a view-target steal is repaired in the same tick, and O doesn't
  reset the dog's look.
- **Measured:** suite 102/0/102. The markers `JumpResettlesOnce` and `JumpResettleReassertsPassageSameTick`
  are in the DLLs (the conductor, 35094de).
- **Open (Codex's P2):** no test observes a Geometry Cache actually presenting the frame, so 0.1 s may come
  before the decode. If Gary still sees a stale curtain after a jump-and-hold:
  1. Raise `JumpResettleSeconds` to about 0.3 (no rebuild).
  2. Check that `JumpResettleCount` rises.
  3. If it rises and the curtain is still stale, the decode is slower than one retry: a second retry is a
     held patch.

## 4. The smudge A/B (not Look & camera's, listed for completeness)

Gary's judgement is still open: the cvar `InfinityStage.Mechanism.MarkRenderStateDirty` 1 vs 2 (patch Q,
Rig's). The smudge was traced to TSR history; FXAA cures it. See `Docs/Conductor/CONDUCTOR_START_PROMPT.md`.

## 5. Built and done (for reference)

- **Patches**, all built: K (Passage keys follow their section), L v2 (retained exit, no gap, exclusive
  ranges), MR (gait bob: roll centred on the raw lift's mean, everything scaled by walk weight, driven by
  Master time), N v2 (Scene cut bindings must resolve; fails closed), O v2 (the look resets at every cut and
  eases during blends), T (the cat's body is never seen), S v2.
  Notes: `Scripts/patches/2026-09-30_KL_STAGING.md`.
- **Gary's camera rulings now in force:**
  - no permanent tilt; the height is kept;
  - no cat bob between passages;
  - free dog look in hangar Scenes 1–6 until the cutscene handover;
  - the look resets at every cut.
- **Docs:**
  - `Docs/SceneImportCameras_2026-09-30.md`: spawnable cameras, nested-cut precedence, import gates.
  - `Docs/HangarAsHouse_2026-09-30.md`.
  - `Docs/CodexUnrealMCPRunbook.md`: recording PIE doesn't work in the background.
- **Probes and harnesses:** `Saved/CodexCameraPilot/`. The census is `census_dirty.py`; its marker is
  `PUSS_DIRTY_CENSUS`.

## 6. Open, not started

- **Settle length** at the Passage → Scene arrival. Parked until the rise, cloth and light timing settle;
  Gary may judge it by eye. Tools: `capture_settle_options.py` and `compose_settle_options.py`.
- **SpeedMultiplier keying for a settle.** Not started.
- **A stalls re-seat script, if Passages dock into hangars.** Not started. The stalls cameras are placed by
  `place_transition_stalls.py` and are NOT derived live.
- **Working method from 1 Oct** (the conductor, on Gary's behalf): Codex writes AND runs editor steps through
  `Scripts/codex.sh --unreal`. Each spec names the crash rules, the success marker and the census, and Claude
  verifies the marker.
