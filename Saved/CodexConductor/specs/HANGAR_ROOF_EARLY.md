# Hangar roof closes earlier (Gary, 2 Oct, his own answer in the Conductor 4 session)
Gary: in every hangar that rises, the roof reads as an opened lid for too long; "can the closure come earlier? by 4s
or so". Ruling: the roof starts closing THE MOMENT THE BOX LANDS and swings faster; the lattice follows straight after.
Times relative to the cut (W1 = the landing, +4.1261 s; see hangar_retime_apply.py EXPECTED_W1):
  roof_pitch:    today +6.63 -> +12.63 (-90 -> 0)   NEW: landing (+4.1261) -> +8.6261 (4.5 s), same values, same interp
  lattice_fly_z: today +12.63 -> +16.63            NEW: +8.6261 -> +12.6261 (4.0 s, unchanged duration)
Read the CURRENT keys first; if they are not today's values above (within 1 frame), STOP and report them.

## Tool `Saved/CodexStructure/hangar_roof_early_apply.py` (dry / apply / revert)
Reuse hangar_retime_apply.py's discovery (discover_sequence, _one_track_channel, keys_of, set_keys,
interpolation_matches, package census, record + backup pattern) by import or copy; do not modify that file. Scope:
every LS_S<N>_HangarRise that has a `S<N> Hangar Roof Hinge` binding (S6 has no roof: lattice only, or skip if its
lattice is already non-overlapping; report the decision). Discover S4 and S5 too (S4's rise is the original Scene 4
fold, S5 is undecided): include them only if their roof/lattice keys match the standard shape; otherwise report them
and leave them alone. Keep each sequence's playback range, root rise keys, exposure/PPV weights and light drives
UNTOUCHED, except that a light or exposure key timed to the roof or lattice must be REPORTED, not moved.
Report (do not change) any CAMERA key in LS_DevScene_0N or the Master within ±1 s of the old roof start (+6.63) or the
old lattice start (+12.63): e.g. Scene 4's look-up was tied to the swing (Docs/InfinityStageSessionHandover.md:761).
Gary decides those.
Backup: Backups/PreHangarRoofEarly-<stamp> with every touched rise asset. Census = exactly the touched rise assets.
save_asset each one. After the apply: SavedMasterMatchesShow alone, exact name. Revert restores recorded keys.
Clearance: the roof now swings while the lattice is still parked above it. Using the existing swept-check method
(rise_sweep_measure_readonly.py), assert the roof's swept volume never intersects the parked lattice or the side
walls over its new window; report the minimum clearance.
Harness `test_hangar_roof_early_plan.py` (Unreal-free, like plan_scene): + case (roof/lattice windows as above, root
keys unchanged); − cases: roof start before landing, lattice overlapping roof, keys not matching today's (must
refuse), a scene without a roof hinge handled without error.

THIS PASS: write the tool + harness, run the harness only. DO NOT contact Unreal (Wings and Textures hold the
editor). Commit nothing. Final message: per scene, before/after key tables, what was included or skipped and why,
anything reported for Gary, each claim tagged measured/declaration-proven/inferred.
STANDING RULES: NEVER stop PIE/SIE, NEVER quit or restart the editor; no Sequencer UI/eval/scrub, no SequencerTools,
no open-range get_bound_objects, no unreal objects in module globals, no reload, never Save All, no deletes of
pre-existing things.
