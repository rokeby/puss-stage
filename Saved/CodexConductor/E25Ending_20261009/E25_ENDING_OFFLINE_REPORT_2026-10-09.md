# E25 ending — offline report (Codex job 101)

Evidence terms follow `_house_rules.md`: declaration-proven, binary-proven,
measured, inferred. No live Unreal claims are made.

## Result and placement

- **[measured]** E25 was still explicitly “not built yet” at dispatch; the note
  asks for S6 black followed by the Opening stage with no infinity behind it
  (`Docs/Conductor/GARY_PIE_NOTES_2026-10-09_evening.md:31`). The dedupe search
  found no prior E25 tool or tracked ending sequence
  (`Saved/CodexConductor/E25Ending_20261009/dedupe_inventory.json:2-13`).
- **[inferred, implemented as a plan]** The ending belongs in a new Sequence cue
  after S6 and before Closing, rather than in S6. This preserves the Void's
  terminal black and leaves the existing Closing available for later business;
  the planner declares and verifies that exact placement
  (`Saved/CodexConductor/E25Ending_20261009/e25_ending.py:256-271`).
- **[measured from prior offline records]** The pre-E25 spine ended S6 → Closing,
  and Closing already has a curtain-close scaffold but no sweeping-up figures
  (`Docs/Conductor/P10_FRONT_VOID_ENDING_2026-10-08.md:55`).

## What was built

- **[declaration-proven]** `e25_ending.py` implements guarded DRY/APPLY/REVERT,
  exact S6/Closing GUID and actor-census pinning, an exclusive record, hashed
  backups, an exact named-package dirty census, targeted saves, post-save
  read-back, and success markers
  (`Saved/CodexConductor/E25Ending_20261009/e25_ending.py:705-762`).
- **[declaration-proven]** `InfinityShowCue.cue_guid` is never authored: caller
  input is discarded, Unreal mints it during managed-Master rebuild, and the
  tool reads and persists it before verification/save
  (`Saved/CodexConductor/E25Ending_20261009/e25_ending.py:148-149,284-291,732-736`).
- **[declaration-proven]** Stage, hidden-world and mask visibility tracks bind
  `bHidden`; their bool channel deliberately uses visible semantics (`True =
  shown`). Existing bindings are looked up before `add_possessable`
  (`Saved/CodexConductor/E25Ending_20261009/e25_ending.py:570-593`).
- **[declaration-proven]** The camera cut is bound to the exact DRY-pinned Opening
  camera actor from the show level, and read-back rejects a different actor
  (`Saved/CodexConductor/E25Ending_20261009/e25_ending.py:308-316,465-502`).
- **[declaration-proven]** The minimum beat is 2 seconds black then a 10-second
  move from P87's wide start to the live Opening sequence's current end pose.
  Stage actors become visible only after black; Passage/hangar/infinity/sky actors
  remain hidden; an owned collisionless black mask covers residual depth
  (`Saved/CodexConductor/E25Ending_20261009/e25_ending.py:237-279`).

## Optional later beats — deliberately not built

- **[binary-proven/measured inventory]** Reusable later animals are pig, red deer
  calf and raccoon from S1, plus the S4 pigeon
  (`Docs/Conductor/P10_FRONT_VOID_ENDING_2026-10-08.md:52-53`).
- **[inferred creative scope]** Stage closing-up, lights going off, happy animals
  settling, and earlier animals recurring remain optional. The tool records them
  as `optional_later_beats_not_built` and creates no animal, worker, light-off or
  curtain-closing tracks (`Saved/CodexConductor/E25Ending_20261009/e25_ending.py:125-130,279`).

## Verification and acceptance boundary

- **[measured, offline]** `test_e25_ending.py` passes 30/30: 10 positive and 20
  negative controls (`Saved/CodexConductor/E25Ending_20261009/harness_result.json:1-6`).
- **[declaration-proven]** The stills plan covers total black, wide reveal,
  mid-arrival and final Opening-stage home
  (`Saved/CodexConductor/E25Ending_20261009/e25_ending.py:273-278`).
- **[inferred/unverified]** Exact live actor membership, mask placement, camera
  binding resolution, saved state, runtime transition, and rendered look remain
  unproved until the conductor runs DRY/APPLY, both named editor tests, the stills,
  and PIE. Offline green is not visual acceptance.
