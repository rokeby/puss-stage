# Job 144 - I2/I3 back-wall shadow interaction

Offline-authored only. It has not run in Unreal and is not visual acceptance.
The single tool takes `params.interaction` = `2` or `3` and has DRY/APPLY/REVERT modes.

## Ordered conductor run

1. Stop PIE/SIE without ending anyone else's session, close Sequencer, load the
   vertical-slice show world, and require a zero dirty-package census.
2. Set `interaction` and run DRY with `DRY JOB144`. Require
   `JOB144_INTERACTION_HANGAR_DRY_OK`, `mutated=0`, and `dirty=0`.
3. Review the full actor census and `candidate_hide`. Copy only the scene's set
   dressing, figures, props, emitters and scene lights into
   `hide_actor_labels`; never select walls, floor, roof, lattice, roots,
   cameras, curtain/drapes, or shadow rig. Copy `inventory.digest` to
   `approved_inventory_digest`, then rerun DRY. Klara actors are possessed by
   the Interaction sequence; her levels are never saved.
4. Review `puppet_bindings` and copy the exact binding(s) that genuinely cast
   the intended approved performance to `approved_shadow_source_labels`. The
   tool deliberately does not invent a missing puppet performance. Review
   `wall`, curtain/camera target, spot throw/diameter,
   active cut resolution, and every warning. APPLY refuses any warning, empty
   hide list, changed args/state, unresolved show-level camera, existing fade
   conflict, or nonzero dirty census.
5. Change only mode/confirmation/run id to APPLY. Require
   `JOB144_INTERACTION_HANGAR_APPLY_OK`, exactly the Interaction and our
   `LS_DevScene_0N` wrapper in `saved=`, a backup, durable record, and `dirty=0`.
   Never save the show map or Klara's streamed packages.
6. Run `InfinityStage.Editor.SceneCutBindingsResolve` and
   `InfinityStage.Editor.SavedMasterMatchesShow` separately, then follow
   `STILLS_PLAN.md`. Gary judges the result.
7. REVERT uses `REVERT JOB144`, drift-checks owned channels/tracks, takes a new
   `Backups/PreJob144I<N>Revert-<run>`, restores state, saves only the two
   recorded packages, and archives the record.

Important: visibility binds `("bHidden", "bHidden")`, but its bool channel is
VISIBLE state (`False` hides). Existing bindings are looked up before
`add_possessable`, so they are never accidentally renamed.
