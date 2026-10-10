# Job 119: replace S2 floor with P01-derived actors

Offline-built; no Unreal, MCP or PIE call was made. The old actors are never deleted.

1. Run with the checked-in DRY args. Require `J119_S2_P01_FLOOR_REPLACE_DRY_OK`, unchanged dirty census, four floors, zero component-binding blockers, and review every `sequence_scan_unclear` row.
2. Review the fitted transforms, scale ratios, persistent-level ownership, and stills plan in `j119_dry_<run>.json`.
3. Copy its `plan_sha256` into args. Gary/conductor must explicitly acknowledge that equal texel density is inferred until live material mapping and stills are checked; set `ack_texel_density_inferred=true`. Acknowledge unclear sequence scans only after manual inspection.
4. Set `mode=APPLY`, `confirm=APPLY J119S2P01FLOOR`, then run once. Require the APPLY marker, four owned actors, persistent map as the sole save, `klara_saved=0`, empty final census and post-save read-back.
5. Execute the report's stills plan, including all visibility sections and hangar movement. Rendered acceptance remains Gary's.
6. To undo, set `mode=REVERT`, `confirm=REVERT J119S2P01FLOOR`. REVERT restores the four old component locations, removes only the four tagged/recorded replacements, targets only the persistent map, and archives its record.

Design: each replacement is a duplicate of `Passage 01 - Opening Floor`, fitted to one old S2 slab and attached to that unchanged old actor. Only the old actor's mesh component is shifted 1 km below stage. Actor/ancestor transform tracks and actor `bHidden` visibility therefore continue to govern the replacement. APPLY refuses component-bound transform/visibility tracks because inheritance cannot preserve them.
