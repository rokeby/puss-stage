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
| 8 | **S4 dark cut (96), KEY (Gary E17)**: arrive in a blacked-out hangar, then a straight cut to Klara's sequence (it begins dark); P04 lights off; curtain stays down. Verify with stills at the P04 end, the cut frame and S4+1 s | P04→S4 | TODO (pass-1 DRY OK: 209 additions) |
| 9 | Girders (98) | S5 | TODO |
| 10 | Proscenium fringe (88) | opening | TODO |
| 11 | P05 → 42.04 s (103) | P05 | TODO |
| 11b | P06 → Walking6, 125 s (104, IMPORT_AND_SWAP approved) | P06 | TODO |
| 12 | Car drive-by radius 10000 (110) | **P02** | TODO |
| 13 | 87 opening, **92 S2 hangar size (BIG DEAL, Gary 10 Oct: fully fit Klara's scene; verify with a still from inside her S2 camera)**, 94 S3 arrival, 97 Nap, pearl 2 s, 99 (S6 non-PIE), 101 ending | as listed | TODO. Note: 99 was mis-scoped (Gary: it is P06); job 126 replaces it |
| — | Job 119 | S2 floor | **HELD**: wrong target. Gary meant P02 (→ job 129) |
| 14 | Stills | — | TODO |

## B. After pass 2 (conductor runs these, in order)

1. **P05 deer curtain** (Finishing Touches): `curtain_image_request.json`, run CI-20261009-SETDEER-P05. Report the "previous" texture to FT.
2. **Shadow radii, all P01–P06 casters** (job 111; Gary approved overnight):
   - DRY survey.
   - Raise-only APPLY.
   - Perf check.
   - Auto-REVERT if the frame time regresses beyond the gate.
3. **S2 hangar resize (job 92) FIRST**, if pass 2 has not applied it; then the still from Klara's S2 camera.
4. **Jobs 126 / 127 / 128 / 129 / 130 (S2 shrine fires in PIE)**, as each lands, after an import and a harness rerun:
   - 126: **P06** parcan in the arrival shot plus the sun disc.
   - 127: **P04** smoke-machine prop hidden.
   - 128: **P05** LEFT wings +20 cm on local X.
   - 129: **P02** floor = P01 floor copy.
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
