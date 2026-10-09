# P87 — Opening fixes from Gary's PIE notes (Codex, offline tools; live by conductor)

Read `_house_rules.md` + known 5.8 traps (str(enum) '<E.V: n>' normalise; str(FGuid) changes per call; accessor vs
property names; read-only engine-minted fields; StaticSwitch pins True/False; channel names carry suffixes). Offline only.
DEDUPE first: Codex job 31 brief (5ab1b93a, `codex_briefs/p31*`) = prelude camera move (find any tool it produced);
opening curtain sequence `LS_Opening_Curtain_Baked` + W&T q17 ragged swap (`Saved/CodexSoftGoods/q17/`); opening
lighting `Saved/CodexConductor/opening_lighting_p13.py` (+ job 43 parcans), uplights job 35 (ADD_UPLIGHTS);
P01 floor practicals `Saved/CodexConductor/P01FloorPracticals_20261008/` (dead bulbs moved to wing feet).

## Gary, 9 Oct (his words)
1. "The curtain currently falls twice, oddly … The first 'flurry' is actually at 00:37:50. The curtains fall that one time
   and they can hold thereafter. no more curtain action. Then the lights get going, before that is dark except for some
   subtle lighting choreo." → ONE fall at the first flurry (Opening timeline 00:37:50 — confirm the clock: Master vs
   Opening segment; report evidence), hold after; remove/deactivate the second fall (keep it recorded, revertible).
2. "the camera needs to be more zoomed out in order to see the full stage at first. After the curtain falls on the first
   flurry, we can very slowly move into the position we end on: in the passage." → wide opening framing that shows the
   full stage front (fit the proscenium bounds, report focal length/position), hold until the fall, then a very slow
   move ending exactly on the current end pose (camera-is-the-cat rules apply in Passages: keep the end pose identical).
3. "the first lights we see are the flashes … we could also bring uplights on parts of the stage front as that's more
   traditional and brings grandeur" → add a small set of stage-front uplights (reuse the uplight/parcan models; GPU cap:
   no new shadow casters by default), keyed on after the flashes; levels as args.
4. "these small lightbulbs should be rotated and placed a bit more randomly 'on the ground' in front of the wings not
   necessarily all neatly next to them" → seeded scatter (single draw per value) of position/yaw/tilt within a band in
   front of each wing, on the floor (trace to floor), not intersecting wings; revertible.
Each part: DRY/APPLY/REVERT, record + backup, exact census, targeted saves, read-back, stills plan. Harness +/-.
Tiered report; deliver in your worktree; the conductor commits.
