# Job 92 — S2 envelope runbook

Offline-authored only. Nothing in this folder has been run in Unreal.

1. Run `s2_bounds_probe_request.json`. Require `S2_BOUNDS_OK`, zero census delta, and inspect the JSON's
   `content_bounds_renderable`, `components`, `hangar_actors`, `arrival_drives`, `handoff_cameras`, and four sequence
   inventories. This read-only step never saves Klara's level.
2. Compare the reported renderable bounds with `s2_envelope_args.json`. The shipped 25 m half-width / 45 m height /
   28 m landed lattice / 42 m rest lattice are conservative defaults, not visual approval. Increase them if the
   report's `recommended` envelope is larger. Do not reduce either margin below 3 m without Gary's approval.
3. Run `s2_envelope_request.json` in `DRY`. Require `S2_ENVELOPE_DRY_OK`, `mutated=0`, and inspect
   `s2_envelope_dry.json`. Review every actor row and the exact dirty census (must be 0+0).
4. Set `mode=APPLY`, `confirm="APPLY S2ENVELOPE"`, paste the DRY digest into `dry_plan_digest`, and replace
   `approved_by` with the conductor's review note. Run once. Require `S2_ENVELOPE_APPLY_OK`, saves of exactly the
   vertical-slice map and `LS_S2_HangarRise`, post-save census 0+0, and the backup/record paths in the marker.
5. Run the stills plan, then PIE review. Automation is not rendered acceptance.
6. To undo, set `mode=REVERT`, `confirm="REVERT S2ENVELOPE"`. REVERT refuses drift, takes a new backup, restores the
   exact recorded actors/keys, saves the same two packages only, reads back, and archives the record by rename.

Do not run old all-scene hangar, exit-door, arrival-mover, wall-hide, overlay, floor or camera REVERT tools over an
applied Job 92 record. Their historical records describe the smaller box. Coordinate a Job 92 REVERT first.
