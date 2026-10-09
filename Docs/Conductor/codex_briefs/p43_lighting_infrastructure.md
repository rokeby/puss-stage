# P43 — Lighting infrastructure for Gary's review: P02 lit like P01, S2 seam + dark shots probe, P30 parcans one model (Codex, offline)

Read `_house_rules.md`. Offline only. Gary 9 Oct: infrastructure "can be done to await my review"; P02 P01-style
lighting "try it, with a perf gate + stills"; P30 parcans "one model across the entire show is totally fine".
1. **P02 = P01 lighting**: generalise `Saved/CodexConductor/p03_lighting_as_p01*.py` (P03 run 8 Oct, request
   `p03_lighting_as_p01_request.json`) to a passage arg; DRY/APPLY/REVERT for P02; a PERF GATE (light count, shadow-casting
   count, VSM-relevant settings) that refuses beyond args thresholds; read memory note gpu-lost-after-p03-relight
   (device removed in VolumetricFog after P03=P01 relight; Gary thinks it was S3 fire shadows) and add a REVERT runbook.
2. **S2 F10 seam (9:34) + F13 dark shots**: a read-only probe tool that, for the P02→S2 boundary (±2 s) and each S2 shot,
   lists every light's evaluated intensity/visibility, exposure/post-process, fog, and reports the deltas across the seam;
   then an opt-in DRY/APPLY that matches the seam (smallest change) and lifts S2 shot exposure/lights by args factors.
3. **P30 parcans**: `Saved/CodexConductor/opening_lighting_p13.py` pass 2 refuses the bay-1 practical; make the subset
   explicit in args (default: the 6 non-bay-1 facade PARs, ONE parcan model everywhere) and verify the mesh is the same
   asset across all placements (report any others in the show).
Harness +/- controls; tiered report; deliver in your worktree.
