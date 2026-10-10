# Overnight queue: 10 Oct 2026 (Conductor 5)

**The single source of truth for tonight.** Update the status on every change.

Rules:
- One editor writer at a time.
- Every item runs DRY → APPLY → read-back → clean census.
- A zero-mutation failure: record it and continue.
- A post-mutation failure: STOP, then a Don't-Save restart.
- The morning report is built from this file.

Status values: `TODO` · `RUNNING` · `DONE (marker)` · `SKIPPED (reason)` · `FAILED (reason)` · `HELD (reason)`

## A. Pass 2: Codex job 113 resume 5 (running in the editor)

| # | Item | Target, as stated by Gary | Status |
|---|---|---|---|
| 1 | P02 practicals | P02 | DONE (P02FLOOR APPLY, 44 rows) |
| 2 | P02 beams, then P02 lighting = P01 | P02 | DONE. Perf gate FAILED: p95 40.7 vs 33.4 ms; job 125 has trim options for Gary |
| 2a | S3 shirts / shorts / crowd / weave / back-face | S3 | DONE (conductor). Stains skipped (Gary OK) |
| — | P02 Top flip (106) | P02 | DONE |
| — | S3 feet | S3 LS_Clams | DONE (S3FEET-20261010-015655). Crowd 15 yaw dropped (Gary) |
| 95 | Camera seams | all seams | DONE (J95-R5-APPLY) |
| 90 | I1 polish | I1 | DONE (I1POLISH-R5-APPLY-...0344) |
| 90b | I2/I3 | I2, I3 | SKIPPED (DRY I2_NOT_THR..., zero mutation); investigate |
| 89 | Curtain before shadow | I1/I3/I4/I5 | RUNNING (I1, I3 done) |
| 3 | Chandelier: P75 adopt/clean → staging → P56 candles → P52 swing | opening + P06 | TODO |
| 8 | **S4 dark cut (96), KEY (Gary E17)**: arrive in a blacked-out hangar, then a straight cut to Klara's sequence (it begins dark); P04 lights off; curtain stays down. Verify with stills at the P04 end, the cut frame and S4+1 s | P04→S4 | APPLIED (96 R6). **STILL FAILS VISUALLY:** the P04 end still shows rig bulbs and glows; the S4 cut is dark but not black → job 134 (tool fixed and merged, 18/18; runs AFTER pass 3) |
| 9 | Girders (98) | S5 | TODO |
| 10 | Proscenium fringe (88) | opening | TODO |
| 11 | P05 → 42.04 s (103) | P05 | DONE (P103-E26-P05) |
| 11b | P06 → Walking6, 125 s (104, IMPORT_AND_SWAP approved) | P06 | PARTIAL: swap + 125 s SAVED; retime FAILED (unbounded Spawn section) → Don't-Save restart; job 134 RESUME (tool fixed and merged, 46/46; runs AFTER pass 3) |
| 12 | Car drive-by radius 10000 (110) | **P02** | TODO |
| 13 | (87 opening HELD: its requests renamed; it runs AFTER job 131 places the 3D stage front, because stage scale and camera angle change all opening visuals; then RE-DRY, and possibly re-plan the camera/uplights) **92 S2 hangar size [APPLIED R6: 99 actors + 3 lattice keys; Klara-camera still is INCONCLUSIVE (it looks up at the shrine) → needs a wide/outside still] (BIG DEAL, Gary 10 Oct: fully fit Klara's scene; verify with a still from inside her S2 camera)**, 94 S3 arrival, 97 Nap, pearl 2 s, 99 (S6 non-PIE), 101 ending | as listed | TODO. Note: 99 was mis-scoped (Gary: it is P06); job 126 replaces it |
| — | Job 119/129 floor tool | **P02** floor (args target=P02; the S2 target is never used) | TODO: probe J118 P02 vs P01, then DRY (review segments + bindings) → APPLY → stills |
| 14 | Stills | — | TODO |

## B. After pass 2 (conductor runs these, in order)

0. **Nap camera offset** (LS_Nap_BatteryChange, all keys): Z +20, roll 35, yaw −20, pitch +15, then a still at 24:51.2 (Gary).

1. **P05 deer curtain** (Finishing Touches): `curtain_image_request.json`, run CI-20261009-SETDEER-P05. Report the "previous" texture to FT.
2. **Shadow radii, all P01–P06 casters** (job 111; Gary approved overnight):
   - DRY survey.
   - Raise-only APPLY.
   - Perf check.
   - Auto-REVERT if the frame time regresses beyond the gate.
3. **S2 hangar resize (job 92) FIRST**, if pass 2 has not applied it; then the still from Klara's S2 camera.
4. **Jobs 126 / 127 / 128 / 129 / 130 (S2 shrine fires in PIE)**, as each lands, after an import and a harness rerun:
   - 126: **P06** parcan in the arrival shot plus the sun disc.
   - 127: **P04** smoke-machine prop hidden (tool IN main tree, harness rerun; needs a DRY, then plan_sha256 into args, then APPLY with ack_clear_apparatus_mesh_for_pie=true).
   - 128: **P05** LEFT wings +20 cm on local X (tool IN main tree; DRY → copy the confirm into args → APPLY).
   - 129: **P02** floor = P01 floor copy.
   - 130: **S2** shrine fires in PIE (tool IN main tree: PROBE → PIE +5 s probe → select the fire paths → DRY → APPLY → PIE re-probe + still).
   - 131: **3D STAGE FRONT** [Gary: Dusty, all six pieces tonight, Iron3 chandelier; job 133 DONE: all six FBXs import-ready, harness 41/41. Crest + Cat are 2M tris each, so import with Nanite] (Arch/Gilt/Wall FBX + Crest/Column/CatCandelabra; baked in Blender 9 Oct, NEVER imported: found 10 Oct on Gary's question). Import + place next to the paper proscenium, then the wide stills.
4. **Retry** any pass-2 items skipped because Gary was in PIE.
5. **Build window** (editor closed):
   - Shadow-cat v2 patch (job 123 output, reviewed first).
   - Build, then tests.
   - Revert on red.
   - Metamall gets its window after the build, if it asks.
   - Relaunch, then confirm the sky is hidden.

## C. Waiting on Gary (morning)

- P02 lighting: keep / trim (job 125) / revert.
- Shadow-radii result.
- Stills review.
- 90b investigation result.
- Later items: S3 hair (very long, unkempt, dark brown/grey), garment stains, Shore05 hessian shroud (dropped), girders everywhere (116), swarm (100).

## Lessons tonight (apply them)

- **Gary's location words are exact.** Confirm the passage or scene from his message, or ask, before targeting.
  - E23: "S6" was really P06.
  - E28: the floor was P02, not S2.
- **mcprun.sh takes paths RELATIVE to Saved/CodexConductor.** A full path silently hangs.
- **A 5.8 API miss is the commonest live failure.** Known misses:
  - Rotator has no `rotate_vector`; use Quat.
  - Transform has no `rotator()`; use `rotation.rotator()`.
  - `set_actor_transform` needs sweep and teleport.
  - `MovieSceneSequencePlaybackSettings(restore_state=)` fails.
- **Evaluating a sequence from Python cannot restore figure state.** Never do it on a level that might be saved.

## D. Priority order beyond tonight (Gary, 10 Oct)

1. **Key fixes first:**
   - S4 blackout cut (96).
   - S2 hangar fits Klara's scene (92).
   - S2 shrine fires (130).
   - The P02 floor (129), P05 wings (128), P06 parcan + sun (126), P04 smoke machine (127).
   - The S3 fabrics.
2. **Then a gate (GARY runs this himself on 11 Oct).** Passages look basically to a standard, and every scene PLAYS to a standard. Verify by a stills/recording run-through, S1–S6 and P01–P06.
3. **After that gate, the focus is SHADOW SCENES and TRANSITIONS:**
   - The interactions I1–I5: gobo/shadow-puppetry content, curtain timing, shadow spots off after each sequence.
   - Every passage↔scene seam: arrivals, rig jumps, dog-view ease, darkness handoffs.

**Tonight (Gary):** ONLY the fixes, plus VISUAL confirmation of each (a still per fix: before/after where possible) into `Saved/CodexConductor/ApplyPass_20261010/stills/`, linked in the morning report.

## E. Metamall (other project, the same machine; Gary: lower priority than Puss)
- After the Puss build in B.5: send "BUILD WINDOW OPEN" (their UBT build, 3–10 min, no editor), then wait for "build done".
- After the Puss overnight queue is complete and the editor is CLOSED: "SLOT OPEN" (about 3 h; Metamall peaks ~36 GB, so the Puss editor must stay closed). Their GPU items are cleared with the conductor one at a time.

## Pass 3 results (job 135) and pass 4 (job 137, running)

Stills are in `Saved/CodexConductor/ApplyPass_20261010/stills/`. Verdicts are by the conductor's eye.

| Item | Result | Visual verdict |
|---|---|---|
| S2 hangar fit (92) | already applied | **probably passed.** From outside/above the set sits inside the box with nothing visible poking out, but the image is very dark. Gary to confirm in PIE |
| P05 deer curtain | applied | **passed.** The deer looks at camera, small |
| P05 left wings (128) | applied as **−20 cm** local X (the tool's geometry chose the direction that removes the overlap); minimum gap 0.15 cm | inconclusive. Gary to check |
| P02 car radius 10000 (110) | applied | still too dark to judge |
| S5 girders (98) | applied | still too dark to judge |
| P02 floor (119/129) | DRY guard stopped it, zero mutation | → job 136 |
| P04 smoke prop (127) | DRY guard stopped it, zero mutation | → job 136 |
| Fringe (88) | FAILED mid-import (5.8 API); Don't-Save restart; record retired | → job 136 |

**Pass 4 (job 137), in order:**
1. 96 RESUME (P04 black + cut fade).
2. 104 RESUME (P06 retime).
3. 94, the pearl 2 s fade, 90b.
4. The 3D stage front (all six pieces, Dusty, Iron3).
5. Shadow radii with the perf auto-revert.
6. The chandelier chain.
7. Ending 101.

**Job 136 (merged):**
- Fringe and P02 floor: ready for pass 5.
- **P04 smoke prop: GARY DECISION.** The smoke actor is stale or outside the Show's identity contract. Options:
  - (a) re-materialize P04 from the Show (its managed attachment actors get respawned), then re-DRY; or
  - (b) decline / hide it by hand.

  Waiting for Gary.
- **P04 smoke (Gary: "just hide the prop")**: DONE. FX SMOKE P04 B18 L (nearest the final wing) has its Apparatus mesh cleared and the level is saved; the smoke FX stays. Verify after the next editor restart that the BP construction did not restore the cube. The other two P04 smoke pots (B04 L, B11 R) still show their cube props: ask Gary.
- **P04 smoke pots B04 L + B11 R (Gary: hide them too)**: script ready (hide_b04_b11_props_request.json); run it when pass 5 releases the editor, then a still.

**Next live pass after pass 7: job 144** (I2, then I3; Gary's decisions in the notes):
- DRY → review the census and shadow source.
- Set the args:
  - `spot_side=front`
  - `camera_distance_override_cm` fitted so the curtain frame fraction matches I1/I4/I5 (measure those first)
  - `approved_shadow_source_labels` = the existing I2 gobo/puppet; I3 reuses it
- APPLY, then the stills.


## Pass 7 (job 143) and pass 8 (job 146, running)

**Pass 7, checked by the conductor's eye:**
- **S4 blackout: PASSED.** The P04 end, the cut and S4+1 s are all fully black.
- **Pearl: PASSED.** The clam is empty at frame 5040.
- **P06 retime to Walking6 125 s:** APPLIED; dusk not yet seen by eye.
- **Stage front:** all six Nanite meshes and 30 textures imported and SAVED. The material step failed (CONNECT_MASK_r), so a Don't-Save restart → job 145 fixes it.

**Pass 8, in order:**
1. Job 144 I2/I3 back wall (matched framing, front spot, reuse a gobo).
2. The P02 floor.
3. Fringe.
4. Shadow radii.
5. Chandelier.
6. Ending.
7. A P06 dusk still.
- **Fringe (88): HELD until 11 Oct**: two live failures (post_edit_change, then the SkinColor setter); low priority; retired records.
- **Metamall**: build done 03:53 local; **SLOT OPEN** until 06:30 local (soak + one visual check cleared). The Puss editor stays CLOSED until they send "slot done".
- **Shadow-cat v3 (job 154)**: still fails to compile (ShadowCatActionTolerance undeclared in the tests; a bad dereference + nodiscard at InfinityStageCameraRig.cpp:1329). REVERTED, clean rebuild Succeeded. Needs a proper compile-fix round in the morning.
- **END OF NIGHT**: the GPU device was removed in pass 14 (no mutation); the editor was closed with Don't-Save. Live work stopped; Gary to reboot. Next-slot order is in the morning report.
- **Tonight (Gary, 10 Oct)**: Puss SATURDAY FILMING gets the machine first (Tools/Fallbacks/saturday_night_film.ps1). Metamall: its 3-min UBT build in the gap after the current Puss slot; its 6-8 h soak only after filming, or another night.

- 18:20 Job 175 (S3 hair+fires, Job171 tool): APPLY_OK + read-back, clean census (measured; 2 Don't-Save recoveries). Conductor eye on 175_09/175_10: shrouds cover most heads, hair barely readable; no fire in frame, so blue-grey is unverified (inferred: fire is out of these camera views). VISUAL: unconfirmed. Job 176 launched: I2/I3 back walls, P56 candles + P52 swing, job 169 S1 fire ending.

- 19:00 Gary: S6-prep particle cloud = ignore (not candles); 3D stage front needs its own uplights; P06 sun disc sized to fit the passage end window (job 178, after 177).

- 19:20 Gary: P02 trim haze+beams keep rig (job 179); shadow reach middle = neighbouring/opposite wings, perf-gated (job 179); keep S3 hair.

- 19:40 Job 178 imported (4ddf2990): 3D front uplights 14/0, P06 sun disc 13/0; live after 177. Sun disc invisible because the Dusk Sky Atmosphere was hidden in PIE (measured in the job 126 probe); the tool adds P06-only visibility tracks. Job 179 (P02 trim + shadow reach) running offline.

- 19:50 Job 180 (offline) launched: auto-rebuild parcans when Gary moves a light (C++ patch, needs an editor-closed build window), per-light no-parcan flag (P06), Puss > Rebuild Passage Fixtures menu fallback. Replication extension DROPPED (Gary).

- 20:00 Job 180 imported (2ccc7ca4): auto-rebuild C++ held in Scripts/patches/job180_fixture_autorebuild.patch (applies to main), Python 11/11; menu item works only after the build (calls rebuild_fixtures_only). NEEDS an editor-closed build window (Gary), then the P06 no-parcan APPLY.
