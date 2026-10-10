# P135: live pass 3, overnight 10 Oct (Codex --unreal)

HARD RULES: those in `p49_postbake_editor_runner.md` plus `p113_apply_pass.md`'s rules, verbatim:
- Purge the module cache first.
- Each item: DRY → APPLY (exact confirm) → `*_APPLY_OK` with this run id → read-back → clean census.
- Leave args files in DRY.
- A zero-mutation failure with a clean census: record it and CONTINUE.
- A failure after a mutation (dirty census, a `prepared` record or a missing APPLY_OK): STOP the whole pass.
- Before each item, if the census is dirty and not yours: wait 60 s ×5, then skip.
- Never Save All. Never save Klara's levels. Never move S3 figure transforms.
- Never end a PIE you did not start. Never quit or restart the editor.

You may start and end your OWN PIE for stills and probes.

**Stills are the acceptance evidence.** Save every still to `Saved/CodexConductor/ApplyPass_20261010/stills/` with the item number in the name.
- Describe what each still shows, honestly.
- A still that does not show the intended change means the item is "VISUAL FAIL" in the report. It is not a pass.

Report: append to `Docs/Conductor/APPLY_PASS_REPORT_2026-10-10.md` as "Pass 3":
- a table: item | target | run id | APPLY marker | census | still path | visual verdict
- tiers on every claim.

## Order (Gary's priorities; every target is the passage or scene Gary named)
1. **S2 hangar fit (92, already APPLIED).** Visual check only. Take a WIDE still from OUTSIDE Klara's S2 set, above and behind, showing the hangar box and her whole scene, plus one from her camera at a wide frame.
   - Verdict: does any part of her scene poke through the hangar walls or ceiling?
   - If it does, measure by how much, and do NOT re-apply.
2. **P05 deer curtain** (Finishing Touches): `curtain_image_request.json` with run `CI-20261009-SETDEER-P05`. Record the previous texture from the log. Then a still of the P05 transition curtain.
3. **P02 floor = P01 floor copy** (tool `Saved/CodexConductor/J119S2P01FloorReplace_20261009`, args target = **P02**):
   - First the J118 probe, P02 vs P01.
   - Then the floor DRY. Review the segment count and bindings.
   - Copy `plan_sha256` into the args, then APPLY.
   - Still: the P02 floor at the camera's height, which must show REFLECTIONS.
4. **P04 smoke-machine prop hide** (`J127P04SmokePropHide_20261010`): DRY, then copy `plan_sha256`, then APPLY with `ack_clear_apparatus_mesh_for_pie=true`. Still near the final P04 wing.
5. **P05 left wings +20 cm local X** (`J128P05LeftX_20261010`): DRY, then copy the generated confirm, then APPLY. Still: the P05 wing pairs, no overlap.
6. **P02 car drive-by radius 10000** (110, `p02_car_light_tune`): DRY → APPLY. Still: the far wings at mid-pass.
7. **S5 girders (98).** Still.
8. **Proscenium fringe IMPORT (88).** Still: a proscenium edge close-up.
9. **S3 arrival (94).** Then the **pearl 2 s fade** (it now uses `remove_key`; verify before save). Then **90b**.
10. **3D stage front (job 131,** `StageFront3D_20261010`**):** IMPORT, one piece per call, Nanite, textures capped at 4K, **Dusty** maps, all six pieces. Then the MATERIAL step, then PLACE (DRY → APPLY → VERIFY). Iron3 is the chandelier. Then a WIDE still from the opening camera.
11. **Shadow radii, all P01–P06 casters** (job 111, `shadow_radius_reach`): DRY survey, then the raise-only APPLY, then a perf check.
    - Reuse the P02 lighting tool's perf gate, or measure the p95 frame time in PIE at three P0x spots before and after.
    - If p95 regresses more than 10% or beyond 33.4 ms where it was under: REVERT, and record "reverted on perf".
12. **Chandelier chain (P75):** ADOPT_OR_CLEAN DRY; CLEAN only of failed-run leftovers; then staging (opening + P06), then P56 candles, then P52 swing. Stills.
13. **Ending (101).**

## Do NOT run
- Job 87: re-plan after the 3D stage front; the conductor handles it.
- Jobs 99/126: they need Gary's selection.
- Job 104 RESUME: job 134 delivers it.
- Job 96 extra darkness: job 134 delivers it.
- LS_Nap_BatteryChange.
