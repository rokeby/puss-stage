# P37b — P06 right side: CHOREOGRAPHED slow domino (no contact) + music-length P06 (Codex, offline)

Read `_house_rules.md`. Builds on job 37 (committed 3284471: `Saved/CodexConductor/P37P06DominoFinale_20261009/`,
report `Docs/Conductor/P37_P06_DOMINO_FINALE_REPORT_2026-10-09.md`). Offline only.

## Gary, 9 Oct (his words)
"Choreographed fall is okay indeed as if each fall was just a small shockwave that [triggers] the next as long as [it]
can fall at a nice movement and have a little bit of dust to show the heaviness of its impact and then therefore if they
don't touch each other, it becomes more of a very slow domino effect of the impact of each [one] triggering the next one."

## Change
1. Add chain mode `choreographed` (args `mode_b: contact|choreographed`, default choreographed for B): the last up to 12
   RIGHT-side rows each fall on their own (no contact eligibility), sequenced so wing k's creak starts when wing k-1
   IMPACTS plus a shockwave delay (args, default 0.35 s, seeded jitter ±0.08 s, single draw per value). Fall motion =
   job 37's gravity ease + one small rebound; fall direction away from camera route or toward the floor (pick the one
   that never intersects standing panels; report). Each impact: dust burst (P_Ambient_Dust, capped, never auto-activate,
   no shadows); the LAST impact = the slam (dust scale 2.25 + slam sound, default Collapse01).
2. **P06 = music length.** Codex job 33 (passages_to_music.py) will relength P06 from 126.001 s to 110.561125 s
   (passages_to_music.py:10-11) — runs BEFORE this applies. Plan both against the post-P33 P06: slam default
   = end − 2.0 s (args); if the sequence of N falls does not fit before the slam, reduce N (report) rather than squeeze
   falls below a minimum fall time (args, default 1.4 s).
3. Report timing table (creak/impact per wing, camera distance at each impact), refusals, and a timeline PNG.
4. Harness: + controls (12-wing choreographed plan fits), − controls (falls through a standing panel refused; slam
   after end−2 refused; auto-activate dust refused; chain A untouched by B APPLY/REVERT).
Deliver in your worktree; the conductor reviews and commits.
