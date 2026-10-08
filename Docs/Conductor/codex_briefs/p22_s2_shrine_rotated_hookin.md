# P22: hook Klara's NEW S2 shrine into a ROTATED hangar (rotation-capable re-key) (Gary 8 Oct evening)
State (measured by the conductor, 8 Oct):
- Klara's PUSS_Shrine is copied into Content (backup Backups/PreShrineV2-20261008-1650):
  - her sequence /Game/KK_S2_Shrine/LS_NEW_SHRINE binds into /Game/Japanese_Alley/Maps/Japanese_Alley;
  - audio /Game/Japanese_Alley/Shrine_Stereo__3_.
- Gary: it "replaces everything we have in that scene". The opening is "Same as S1/S4" (land in the dark, then her
  first shot); our S2 stays in the file but is deactivated.
- Tool: Saved/CodexConductor/KlaraIngest/klara_hookin.py. It is applied for S1/S4 under klara_hookin_seq_record.json,
  which must NOT be touched. For S2 it takes args klara_hookin_s2_args.json with "seq_record":
  "klara_hookin_seq_record_S2.json" (the override the conductor added).
- DRY KLARAHOOK-20261008-165229 refused:
  - (1) NO_FIT: alley 3390 x 2556 cm vs hangar interior 5800 x 1800, side overhang 378 cm. Gary chose to KEEP THE
    HANGAR WALLS (the box illusion), so the overhang is ACCEPTED: make it an explicit arg accept_overhang_cm,
    default 400, recorded.
  - (2) WORLD_YAW_NONZERO 316.43. The S2 hangar is rotated in the world (P02 curves); S1/S4 hangars are yaw 0. The
    re-keyed sequence copy is translation-only.
  - Warnings: TALLER_THAN_LATTICE 1220 > 1200 cm (accept, report); LENGTH_OFF_GRID 3514.167 → 3515.
- Stream placement for Japanese_Alley (klara_hookin_stream_record.json): loc (13828.16, 78182.35, -790), yaw 316.43,
  docked at the S2 hangar.
Job (offline, no Unreal):
1. Extend the re-key to ROTATION about the level pivot.
   - Every world-space transform key in the duplicated LS copy (top-level possessables and spawnables, cameras, any
     3DTransform section) is rotated by the level yaw about the level-transform origin: location keys rotate in XY,
     and the yaw key gets +yaw (with wrap continuity: no 359 → 0 flips).
   - Attached/relative bindings are NOT rotated.
   - Camera cut and focus targets follow. Handle additive sections (leave them).
   - Prove it with the harness: synthetic keys at yaw 0 vs rotated, positive and negative controls, incl. Euler wrap.
2. Allow WORLD_YAW_NONZERO when rotation re-key is enabled (arg rekey_rotation: true).
3. Visibility: her level visible ONLY during S2, via the scene sequence's level visibility (as S1/S4: visible_levels).
   Report how the level is hidden in P02 and every other segment (it must never show in P02, Gary: "it should only be in
   S02").
4. DRY report: the placement, what overhangs where (left/right m), the 4 corner points vs the hangar walls, and a top-
   down PNG of her footprint + hangar walls + HER CAMERA positions/frusta from her LS (so the conductor and Gary can
   see whether any camera looks into the wall cut).
5. Runbook: DRY → APPLY_SEQ (S2 record) → tests → stills from her camera cuts.
Never save Klara's levels (only klara_reveal-style allow-listed saves; memory: her levels get dirty unexplained).
Deliver Docs/Conductor/P22_S2_SHRINE_HOOKIN_2026-10-08.md + harness results.
