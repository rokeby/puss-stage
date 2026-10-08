# P16: P03 lighting = P01 lighting structure (final jobs 4.4; Gary 8 Oct, explicit request)
Gary: "For passage 03, please keep any special effects we currently have there, such as the car lighting move ... But otherwise, for simplicity's sake for now, just give that passage the identical lighting in structure, in direction and position relative to wings, albeit not in color. Give it identical lighting to passage one."
Earlier he found P03 "quite milky" and "ridiculously foggy": the P03 atmosphere (tags P03ATMOS, "P03 Smoke Test 1-3" actors, any local fog / LFV / haze on P03) is part of what to normalise to P01's atmosphere settings. List it, and make it an arg whether to match P01's atmosphere (default true).
Read first:
- the light attachments model (Show cues → wing_pair.attachments, kind LIGHT);
- the replication scopes (grep "replicat" in Plugins/InfinityStage and Saved/; the memory says Whole Passage follows the template cue);
- Saved/CodexConductor/lighting_scores_apply.py, lighting_looks_*.py, and Saved/CodexConductor/Effects_20261007/fx_smoke_place.py, for the exact Show struct copy-back + materialize + narrow-save pattern, proven live.
Build one DRY/APPLY/REVERT tool:
- For each P03 wing-pair cue (by ordinal), take P01's light attachments at the same ordinal. Wrap when P03 has more bays than P01, and report it.
- Write P03 lights with P01's pair-relative transform, type, intensity, cone, attenuation, shadows and keys/score STRUCTURE, but P03's existing colour/temperature per role (map roles by label; when no P03 colour exists for a role, use P03's dominant existing colour; report each mapping).
- Keep (never touch) P03 special effects: anything labelled/tagged as car, moving, score events, effect attachments (smoke pots etc.) and any light keyed by a cue event that has no P01 counterpart. List them in DRY.
- Record + Backups/Pre<Thing>-<run> (Show + level).
- Exact census {Show, level}; materialize Passage 03 only; save; read back every written light; saved-master test queued.
DRY must print a table: P03 cue → removed lights / added lights / kept specials. Also give a top-down PNG of P01 vs P03 light positions relative to wings.
Deliver Docs/Conductor/P16_P03_LIGHTING_2026-10-08.md. The conductor runs DRY → APPLY tonight.
