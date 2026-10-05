# Curtain sleight: Scene → Passage transition (plan, 5 Oct, offline)

> **Summary.**
> 1. The far side of the sleight already exists. Each Interaction I1–I5 hangs the shared `GC_CurtainDrop_Opening` drape at the mouth of P02–P06, on a tagged stalls camera, then drops it, and I1 also has a walk-in. The engine also has a "lower, hold for shadow play, hidden changeover, lift" cue mode. **New work:** a matching curtain in the hangar, a fold-down of the hangar, and the cut itself.
> 2. **Recommendation (B):** the **Interaction owns the whole curtain moment.** One camera-cut track: the hangar wide → the hangar curtain → a **cut inside that same track** to the matching mouth framing (the sleight) → drop → walk-in. Everything behind the mouth is then spawned about 60 s before anyone sees it.
> 3. Fallback (A): reuse the +71.64 s already added to each Scene for the hangar half, with the sleight on the Scene→Interaction boundary. It costs less to write, but it puts the cut on the one seam with a **measured one-frame dev-grid flash** (30 Sep). That flash was never fixed.
> 4. "No glitchy previews" becomes a numbered gate list (§3) and a pre-registered PIE capture across the cut, with ± controls. A plan alone does not count as proof.
> 5. Revert the back-door exit block on S1, S2, S4, S5 and S6 with `scene_exit_block.py` REVERT, one Scene at a time. **REVERT has never run.** It removes only the block's additions; the doors stay built and unused, per Gary on 5 Oct. Add a check that the door leaf reads back closed, because REVERT does not check it. Leave the lengthening alone until Gary picks A or B (§4).
> 6. Python only for the first pass. C++ only if the flash survives B, or for a sleight-match automation test (§5). Five questions for Gary are in §6.

Tiers (AGENTS.md), per claim: **[decl]** read in source, header or file; **[bin]** from a binary; **[meas]** an
intervention plus its read-back (dated); **[inf]** inferred, with the reason. Offline only: nothing here was run in
Unreal.

## 1. What exists to reuse

| Asset / mechanism | What it gives us | Tier, evidence |
| --- | --- | --- |
| **Segment order** | Opening → P1 → S1 → **I1** → P2 → S2 → I2 → P3 → S3 → I3 → P4 → S4 → I4 → P5 → S5 → I5 → P6 → S6 → Closing. **Between each Scene and the next Passage sits exactly one Interaction** (a Sequence cue). S6 is followed by the Closing (ClosingCover), not a Passage | [meas, 26 Sep] `Saved/CodexCameraPilot/audit_camera_owners.json` "segments"; [meas, 30 Sep] `probe_interaction_cut_binding.json` rows |
| **Interaction cues** | All five are `retain=true`, `curtain_mode=PostSceneInterstitial`, and have one explicit cut [0,500] on "Interaction N — Stalls Camera" | [meas, 30 Sep] `probe_interaction_cut_binding.json` |
| **The mode itself** | `PostSceneInterstitial`: "Lower over the preceding Scene, hold for shadow play, then lift" | [decl] `InfinityStageTypes.h:71-72` |
| Its fields | `bRetainPreviousCamera`, `bRevealNextPassageWhenCovered`, entry, hold and exit frames | [decl] `InfinityStageTypes.h:830-875` |
| Hidden changeover | An `InfinityStage.HiddenChangeover` marker in the sequence sets the changeover frame | [decl] `InfinityStageTransportController.cpp:28, 96-146` |
| **But an explicit cut always wins** over the retain and the covered handoff. So that machinery is inert while the Interactions carry stalls-camera cuts | | [decl] `InfinityStageTransportController.cpp:1612-1618` (rule), `:1636-1652` (covered branch) |
| **Mouth drapes** | `GC_CurtainDrop_Opening` (final13) feeds the Opening and I1–I5 at the mouths of P02–P06. I1 ends at 638 and holds until 400, then falls 400→638. I2–I5 end at 500 with the same release at 16.0 s | [decl, citing 1 Oct read-back] `Docs/ChaosClothCurtain.md:6-15` |
| Drape timing | A long hold costs nothing: HOLD loops a single cache frame. Re-fit after any length change with `fit_transition_drapes.py` (`lead_s = end − 16.0`), then `verify_transition_fit.py` | [decl] `ChaosClothCurtain.md:551-558, 58-59` |
| Drape draw order | **The drape is drawn at tick 0** of Interaction 1 (real-time playback, dense and sparse runs) | [meas, 30 Sep] `ChaosClothCurtain.md:424-430` |
| **The one-frame flash** | At **tick 1** after Scene→Interaction, one frame shows "an empty dark box with a grid floor, no drape". The handover was logged a frame late | [meas, 30 Sep] `ChaosClothCurtain.md:431-434`; `RUNTHROUGH_NOTES_2026-09-30.md:82` |
| | The suspected mechanism is Sequencer restoring its pre-animated view target when a cut section ends | [inf] `SCENE_ARCHITECTURE_2026-09-30.md:62-66` |
| | The planned fixes, `SnapToView` and `CoveredHandoffGuardFrames`, are **not in source** | [decl: grep of `Plugins/InfinityStage/Source`, 0 hits]; plan in `MECHANISM_PLAN_2026-09-29.md:53-54` |
| Opening curtain | `LS_Opening_Curtain_Baked` was **applied** on 4 Oct (run OPENING-APPLY-20261004-131449). It has marked frames `OPN …` and a precedent for marker scripting | [decl] `Saved/CodexConductor/opening_sequence_record.json`; `opening_sequence_apply.py:291-323` |
| Curtain material | `MI_CurtainVelvet_DeepRed_Drop`, plain oxblood B | [decl] `ChaosClothCurtain.md:18` |
| **Walk-ins** | The Opening is applied. **I1** is "Ready"; **I2–I5 are "Not ready"** until Soft goods lengthens and re-fits them | [decl] `Saved/CodexCameraPilot/walkin_transitions.json` (2 Oct) |
| | Whether I1's walk-in is *applied* is **UNCLEAR**. There is `key_walkin_i1_p02.py` but no I1 record file | |
| Planner | `walkin_plan.py:34-90` | [decl] |
| **Hangar rise** | `LS_S1..S6_HangarRise` exist. Each is nested in its Scene and ends at or before the old Scene end | [decl] `Content/InfinityStage/RigAtmos/`; [meas] `SCENE_EXIT_BLOCK_PLAN_2026-10-04.md` §5 |
| **Fold-down** | **None exists.** `LS_S4_HangarFold` is the v1 wall swing, "kept but no longer referenced". Its keys are world-space, so it snaps on translation | [decl] `RigAndAtmosphere_Handover_2026-09-28.md:259, 355`; `SCENE_DOCKING_AUDIT_2026-09-29.md:78` |
| Mouth lanterns | One spot per mouth (P02–P06), low house-left rake, 210 cd, 2800 K | [decl] `RigAndAtmosphere_Handover_2026-09-28.md:494-498` |
| Scene handoff cameras | The builder makes Entry = [start, first interior) and the retained Exit = [last interior end, end) as a copy of the last interior pose. It **treats a following retain-camera cue as the exit target** | [decl] `InfinityStageSceneHandoffBuilder.cpp:187-206, 396-461` |
| **GO and vamp** | A `GO` marker in a Scene or Sequence cue **defaults to HOLD**. `InfinityStage.VampStart` / `VampEnd` loop a range | [decl] `InfinityStageTransportController.cpp:29-30, 237-280, 958-959` |
| | A HOLD freezes the playhead, so a frame-keyed puppet flipbook also freezes | [inf: same playhead] |
| Jump re-settle | Re-evaluates **only when paused** on the jump frame | [decl] `InfinityStageTransportController.cpp:738-760, 832-866` |
| Shadow puppets | Plan: a filmed flipbook, frame-keyed, used as a **light function on the mouth lantern**. Nothing shot or built; no MediaTexture or flipbook asset exists | [decl] `Docs/ShadowPuppetCaptureSpec.md` §7; [meas: byte search] `SCENE_EXIT_BLOCK_PLAN` §2 |

## 2. Beat timeline and who owns each beat

Defaults below; every time is a named marker (`CST …`) so it can be tuned by hand.

| # | Beat | Default (s from Scene content end) | **B (recommended): owner** | A (fallback): owner |
| --- | --- | --- | --- | --- |
| 0 | Scene content ends | 0 | Scene (unchanged) | Scene |
| 1 | Shift out to the hangar wide | 0–3 | **Interaction**, cut 1 on "S<N> Sleight Wide Camera" (a level actor in the hangar) | Scene tail (root cut, like the exit block) |
| 2 | Hangar curtain falls in, almost full frame | 3–7 | **Interaction**: hangar twin drape (fly-in, Q1) | Scene tail |
| 3 | Shadow play | 7–67 (60 s) | **Interaction**: one flipbook parameter track drives both lanterns | Scene tail, then the Interaction (two tracks to keep in step) |
| 4 | Behind it: fold-down, hangar lights to 0 | 10–40; **done ≥ 2 s before beat 5** | **Interaction**, nesting Rig's `LS_S<N>_HangarFoldDown` | Scene tail, nested |
| 5 | **SLEIGHT**: hard cut to the matching mouth framing | marker `CST sleight`, mid-shadow-play (≈ 50 s) | **Interaction: cut 2, same cut track, exact frame** | **Segment boundary** Scene→Interaction |
| 6 | Shadow play finishes on the mouth curtain | to 67 | Interaction | Interaction |
| 7 | Curtain drops (furi-otoshi), pile | 67–~73 (the drape's release-to-landing) | Interaction (existing drape) | Interaction |
| 8 | Walk into the Passage | to the Interaction's end | Interaction (walk-in, `walkin_plan.py`) | Interaction |
| 9 | Passage starts | Interaction end | P(N+1) | P(N+1) |

**Why B.** The cut in B is a section change inside one cut track. The transport makes no claim there: it claims at
segment boundaries and at the covered threshold (`InfinityStageTransportController.cpp:817-826`) **[decl]**. So the
flash mechanism, a cut section *ending* at a segment edge, is not on the sleight **[inf]**.

The mouth drape and everything else spawned in the Interaction exist from the Interaction's first frame, about 50 s
before the cut **[inf from the spawnable lifetime = section range]**. The shadow play crosses the cut on **one** keyed
parameter, so it cannot drift.

**What B costs:**
- Each Scene goes back to `content_end`, and each Interaction grows by the same amount. The net Show length is
  unchanged, so later Passages shift by about 0 ("shift, not stretch") **[arith]**. It is still two
  `extend_scene_playback.py` runs per transition, and the KEY GATE may refuse
  (`extend_scene_playback.py:193-218, 306-312`) **[decl]**.
- The Interaction must possess hangar level actors: the wide camera, the fold-down subsequence and the lights. They
  must resolve in the show level (memory: bindings must resolve in the show level).
- The Scene→Interaction seam still exists, now on the open hangar wide, so the **flash must be fixed in any case**
  (it is in the show today).

**Matched framing.** This is what makes the sleight invisible.
- The mouth's sleight camera is **not** today's mouth stalls camera, which is a wide proscenium view. It is a new
  camera whose pose **relative to its drape** equals the hangar camera's pose relative to the hangar drape. Lens,
  filmback, focus and exposure are identical too.
- Both drapes use the same GC asset, the same hold sample, the same MI and the same relative lantern. The frame margins
  must be black on both sides at the cut.
- The walk-in then starts from that framing, not from the stalls seat.

## 3. "Spawn in the correct order": what could show, and the gates

| # | What could leak | Evidence | Gate / ordering rule |
| --- | --- | --- | --- |
| G1 | **Dev-grid flash** at Scene→Interaction | [meas 30 Sep] above | Must measure 0 frames (M2). If it survives, C++ `SnapToView` + tick prerequisite (`MECHANISM_PLAN` item 5) |
| G2 | The camera claim lands one tick late: TickComponent reads the frame after evaluation | [decl] `.cpp:805-826`; log frame 7732091 vs 7731265 [meas 30 Sep] | Sleight inside one cut track (B), so no claim happens at the cut |
| G3 | **GeometryCache stale frame after a jump.** Async decode; a capture after a jump shows the old frame | [meas] memory ue58-geometrycache-sequencer-traps | Re-settle only fires when **paused** [decl `.cpp:738-760`]. Rehearsal jumps into the window must re-pose. Measure a jump while playing (M3) |
| G4 | **Mouth drape spawned late** | Drawn at tick 0 [meas 30 Sep], but that was a segment start | B: spawned ≈ 50 s earlier. A: spawns on the cut frame itself (risk) |
| G5 | **Nested shot cuts outrank root cuts.** S1's `LS_Animals_1` covers [-1,5270] with 4 nested cuts | [meas 30 Sep] probe | Offline gate: no nested cut overlaps any sleight cut range (reuse `NESTED_CUTS_IN_WINDOW` from `scene_exit_block.py`) |
| G6 | Covered-handoff machinery inert or surprising | [decl] `.cpp:1612-1618` | Use explicit cuts only. Set `bRevealNextPassageWhenCovered=false` on the five Interactions, or leave it inert and gate on it. Its live value is UNCLEAR: 27 Aug read `true` ×5 (`verify_sequence_curtains.json`), stale |
| G7 | **Passage P(N+1) seen in its pre-section state when the curtain drops.** Its Master section starts only after the Interaction; wing mechanisms freeze outside their Passage | [inf] memory ue58-ism-readback; "misloaded wings followed by cloth" still unexplained (`RUNTHROUGH_NOTES_2026-09-30.md:83`) | M4: compare the saved level state with Passage frame 0 (ISM matrices), and capture through the drop and the boundary |
| G8 | **Lights behind the mouth curtain not dark**, or striking during the walk. Light Drama strikes by camera route distance | [decl] `InfinityStageLightDrama.h:20-30` | "Fully dark behind" is a gate: every light in the sleight frustum reads 0 at the cut (read-back) |
| G9 | **Hangar fold or lights not finished** at the cut | Rise glow "rests at 0 cd" [decl Handover:502]; no fold-down exists | Offline: fold end and lights-to-0 ≤ `CST sleight` − 2 s; M1 margin black |
| G10 | **Exposure mismatch.** The S4 hangar volume pins EV100 0.5; the show's unbound PPV pins −3 | [decl] `RigAndAtmosphere_Handover_2026-09-28.md:256, 497` | M1 measures it; capture with no override (memory: capture exposure convention) |
| G11 | **Lumen / VSM cold history after a hard cut**: GI and shadow-page warm-up on the curtain for the first frames | [inf] engine internals are unverifiable here (memory: UE 5.8 source limits) | M1 frames cut+0…+30; light the curtain mostly by the direct lantern |
| G12 | Restore-State of the Scene's rise at the Scene end snaps the hangar on the wide | [inf] the level is saved LANDED, so it is probably a no-op | M2 also checks hangar pixels across the seam |
| G13 | A GO hold during the shadow play **freezes the puppets** | [inf] above | A HOLD only after the shadow play, or a vamp on an idle loop (Q2) |

**Pre-roll / ordering (B):**
1. The Interaction starts on the wide, with the drape and walk-in rig of P(N+1)'s mouth already spawned.
2. Fold-down and lights-to-0 finish ≥ 2 s before `CST sleight`.
3. The mouth side is dark and its lantern is at its matched state from the Interaction's start.
4. The cut happens on an exact frame inside one cut track.
5. The drop starts only after the shadow play ends.
6. Nothing at the mouth changes state across the cut.

**Must be MEASURED in PIE** (pre-registered, real-time playback, dense screenshots, the `drape_first_frame_test.py`
method, run-id-stamped log markers):
- **M1, the sleight.** Frames cut−5…cut+30.
  - The curtain-region mean RGB step across the cut must be ≤ 2× the within-side frame-to-frame noise (measured on the
    same run).
  - The margins must be ≤ the black threshold.
  - **−control:** the mouth camera offset by 5 cm, or a different hold sample. This must FAIL.
  - **+control:** two cuts on the same side. This must PASS.
- **M2, the seam.** Scene→Interaction ±5 frames. Zero frames without the expected content (the grid detector from the
  30 Sep run); the `INFINITY_HANDOVER` frame is logged.
- **M3, jumps.** A paused jump and a playing jump to cut+1 and to drop+1: the drape is at the right sample after the
  re-settle.
- **M4, the reveal.** Drop → Passage frame 0: wing ISM read-back unchanged across the Interaction→Passage boundary, and
  no pop in the capture.

## 4. The applied back-door exit block: what to do

**Facts.**
- S1, S2, S4, S5 and S6 are applied: `applied: true`, with one root cut each, e.g. S1 [5270,7036) and S2/S4/S6
  [775,2541), plus the curtain, card and camera actors **[decl]** `Saved/CodexConductor/scene_exit_block_record_S{1,2,4,5,6}.json`.
- Each Scene is now `content_end + 1791` frames (+71.64 s) **[decl, same records]**.
- S3 was never applied.
- S2 has two backup folders (`…-214626` and `…-214946`); the record names the second one **[decl]** `Backups/`.

**Steps, one Scene at a time.** Each is a reversible, backed-up write (conductor-approvable for Gary).
1. Preconditions: no PIE (the tool refuses; **never end PIE**), the Sequencer closed, a clean census, the show world
   (`scene_exit_block.py:1113-1130`) **[decl]**.
2. Write a runner `Saved/CodexConductor/scene_exit_block_revert_S<N>.py`, which is `runpy.run_path(...scene_exit_block.py,
   init_globals={"SCENE_EXIT_BLOCK_SCENE": N, "SCENE_EXIT_BLOCK_REVERT": True})`, plus its request JSON (the apply runner's
   shape). No revert runner exists today **[decl: dir listing]**.
3. Run it via `Saved/CodexMocap/mcp_request.py`. Accept only `SCENE_EXIT_BLOCK_REVERT_OK|run=<id>` for that run.
   - It backs up to `Backups/PreSceneExitBlock-S<N>-<run>-revert/`.
   - It removes exactly one cut, the five recorded bindings, the `EXB` markers and the three actors.
   - It rematches the handoffs.
   - It requires the cuts and markers to equal the pre-apply state and the dirty set to equal {sequence, level}.
   - It saves only those, and archives the record (`:1036-1110`) **[decl]**.
   - Any `_STOPPED` means "Don't-Save restart", per its own messages.
4. Run `InfinityStage.Editor.SceneCutBindingsResolve`, then `SavedMasterMatchesShow`, singly.
5. **The length.**
   - Under **A**, keep it: the 71.64 s window becomes the hangar half.
   - Under **B**, shorten with `extend_scene_playback.py new_end_frame=content_end` (printed by REVERT_OK). Then lengthen
     the Interaction by the same amount and re-fit its drape (`fit_transition_drapes.py`, `verify_transition_fit.py`).
   - Either way, do it only after Gary's pick.

**The doors stay (Gary, 5 Oct: "leave the exit door on stage where it is built for now, just unused").**
Remove only what the exit block added. Does REVERT do exactly that?

- **Matches, [decl] from the code:**

  | Removed by REVERT | Where |
  | --- | --- |
  | The block's one root cut | `scene_exit_block.py:1063-1070`, matched by the recorded camera GUID |
  | The five bindings it created: camera, camera component, **leaf**, curtain, card. Removing the leaf binding removes the leaf-swing transform track and its keys, which live only on that binding | `:1071-1074`; keys at `:939, 944` |
  | Every `EXB …` marker | `:1075-1077` |
  | The three spawned actors: curtain, card, camera | `:1078-1080`, guarded by the `SceneExitBlock.S<N>` tag at `:1053-1057` |
  | The focus track | on the camera-component binding (`:947-957`), so it goes with that binding |

  It then rematches the handoffs and requires the cuts and markers to equal the pre-apply record (`:1081-1093`).
- **Not touched by REVERT [decl]:** the door actors from `hangar_exit_doors.py`, i.e. the Far Wall pieces, the
  **Exit Door Leaf** and the Exit Black. They are only looked up by label (`:93, 666`), never destroyed.
- **The leaf's own transform was never written by APPLY [decl]:** APPLY only keys it in the sequence (`:939-944`).
  APPLY also never changes the leaf's mobility; it sets Movable only on its own spawned boxes (`:738`).
  - The leaf has been Movable since the doors tool (`hangar_exit_doors.py:621`), because it rides the rising hangar
    root.
  - So "static" here means **un-keyed**, not Static mobility. Do not change the mobility: the rise moves it.
- **GAP: REVERT does not verify that the leaf is closed.** It reads back no leaf pose. Once the binding is gone,
  nothing animates the leaf, so it shows whatever pose the **saved level** holds.
  - That pose should be the closed one, `[inf]`, for two reasons. APPLY saved straight after keying, with the
    Sequencer closed (gate `:1123-1124`). And nothing in the record says the leaf actor moved.
  - But a level save while the Scene sequence was evaluated could have persisted an open leaf (memory: "level saves
    persist evaluated state"; "opening/scrubbing the Master DIRTIES THE MAP").
  - **Add a read-back before trusting it:** after REVERT, the leaf's **relative** location must equal the doors
    record's closed pose (S1: `location_cm [6024.95, 0, 225]`, `state: "closed"`,
    `hangar_exit_doors_record.json` → `plan.scenes[].pieces`) within 0.1 cm. Its relative rotation must be
    (0, 0, 0), as the doors tool set it at `hangar_exit_doors.py:609-610`.
  - If it is not closed, STOP. Re-closing it is a separate, backed-up level write; do not fold it into REVERT.
  - The read-back needs a small read-only addition to the revert runner, or a separate read-only probe. It is not in
    `scene_exit_block.py` today.
- **REVERT has never executed [decl: no archived `.reverted-` record].** Its Unreal calls have APPLY-side precedents,
  but `binding.remove()` and `delete_marked_frame` on these assets are untested **[inf]**.

## 5. Tooling and ownership

- **Python-only first pass (B):** `curtain_sleight.py`, modelled on `scene_exit_block.py`, with DRY, APPLY and REVERT,
  backups, a record, the inside-box guard and ROOT_NOT_LANDED.
  - It authors per Interaction: the wide and sleight cameras, the hangar twin drape (same GC, sample and MI), the
    twin lantern, the two-section cut track, the `CST` markers, the flipbook parameter placeholder and the nested
    fold-down.
- **C++ only if needed:** the flash fix (G1). Optionally, an automation test `CurtainSleightMatched` that asserts the
  relative-pose match and lights-off at the cut. Both go through the held-patch protocol and a build window.
- **Owners:**
  - **Rig & atmosphere:** `LS_S<N>_HangarFoldDown` (root-relative keys, not world space), hangar lights to 0, the
    twin lantern and the hangar curtain's placement in the hangar box.
  - **Soft goods** (parked, so the conductor holds it): the drape asset, its hold sample and the re-fit.
  - **Look & camera:** the wide camera, the matched sleight camera and the walk-in re-key.
  - **Cueing:** GO and vamp markers, and the music across the moment.
  - **W&T:** none.
  - **Conductor:** Show lengths and the Master rebuild.
- **Falsifiable harness (offline, before any editor step):** `test_curtain_sleight.py`.
  - Pure planner from the mouth route frame (`probe_mouth_surfaces.py`) and the landed hangar root
    (`hangar_exit_doors_record.json`).
  - It asserts: the relative pose is equal (≤ 0.5 cm, ≤ 0.05°); the GC, sample and MI are equal; fold and lights end
    ≤ cut − 2 s; there are no nested cuts in the window; the cut track has no gaps; later Passage keys shift by Δ.
  - **Negative controls must fail:** a 5 cm offset, the wrong sample, a late fold, an injected nested cut.
  - Then M1–M4 in PIE.

## 6. Questions for Gary (recommendation first)

1. **Hangar curtain = the same red velvet drape as the mouth (`GC_CurtainDrop_Opening`, oxblood)?** *Recommended: yes.*
   The sleight needs the two to be identical. How it arrives in the hangar is a separate choice: fly-in from above
   (recommended) or appear on the cut to the wide.
2. **Shadow play timing:** *recommended: a fixed ~60 s in the timeline, then a GO HOLD on the still curtain before the
   drop.* A hold freezes the puppets, so a hold during the play would need a looping idle vamp instead.
3. **The mouth curtain drops (furi-otoshi, as now)?** *Recommended: yes, it drops.* That is your word, and it is what
   the existing bake does. A rise would need new work.
4. **Which joins?** *Recommended: S1, S2, S4 and S5 → I1, I2, I4 and I5 first, then S3 → I3.* S3 has no door problem in
   this design, but it is 24 fps with a stale tail gap. **S6** has no Passage after it; does the Closing use the hangar
   half only (curtain falls, stays)?
5. **Do the Interactions I1–I5 become this curtain moment** (their shadow play is the boy and cat), or is there
   Interaction content beyond the shadow play? *Recommended: they become it* (option B).

**UNCLEAR, and what was searched:**
- The live `bRevealNextPassageWhenCovered` and marker state: only a 27 Aug read exists.
- Whether I1's walk-in is applied: a key script exists, but no record.
- Level streaming: only Config was grepped; World Partition settings appear only as the editor commandlet.
- What P(N+1) looks like pre-section: G7, never captured.
- Lumen/VSM post-cut behaviour (G11): no engine .cpp is available.
- Whether the extension KEY GATE refuses on any Passage after S1–S6 today.
