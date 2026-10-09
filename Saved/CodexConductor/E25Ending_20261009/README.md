# E25 ending — conductor runbook

Status: offline-authored only. No Unreal, MCP, PIE, or Blender was opened by
this job. The Show Asset remains authority.

## Placement and scope

The minimum ending is a new Sequence cue, `Ending — Opening Stage`, inserted
after `Scene 6 — External Sound` and before the existing `Closing — Sweeping Up`. It is
not a tail on S6: S6 retains its terminal black, while the arrival owns its own
camera cut, visibility census, duration, and exact revert identity.

The tool builds only Gary's E25 minimum:

- 2 seconds of total black by default;
- the opening camera's P87 wide pose, then a 10-second move to the live Opening
  sequence's current end pose and focal length;
- the live Opening/P01 stage composition shown after black;
- all DRY-discovered Passage 02-06, hangar, infinity and sky actors held hidden;
- one owned, collisionless black mask behind the opening stage;
- the existing Closing remains next and is not edited.

It does not build animals, workers, a lights-off sequence, curtain closing, or
other “closing up” action. Those are listed in the plan as optional later beats.

## Ordered live run

1. Use the canonical Puss editor and vertical-slice level. Stop PIE/SIE, close
   Sequencer, and require an empty exact dirty-package census.
2. Give `e25_ending_args.json` a fresh run id; keep `mode=DRY` and use the exact
   confirm string `DRY E25 <run>`. Execute `e25_ending_run.py` through the
   guarded project-Python tool. Require `E25_ENDING_DRY_OK`.
3. Review the DRY JSON actor census and preview. Confirm that every stage actor
   belongs in `stage_actor_paths`, every Passage/hangar/infinity/sky actor belongs
   in `hidden_actor_paths`, and the mask sits immediately behind the stage front.
   Copy the reported S6/Closing GUIDs, camera path, and both actor-path arrays into
   the corresponding `expected_*` arguments. Do not infer or shorten the arrays.
4. Repeat DRY with all identities pinned and final creative values. The snapshot
   and plan digests must remain unchanged.
5. Change to `mode=APPLY`, choose a fresh run, and confirm `APPLY E25 <run>`.
   APPLY creates `Backups/PreE25Ending-<run>` and an exclusive prepared record
   before mutation. It creates the sequence/mask, adds the engine-minted cue,
   rebuilds Master, checks its exact four-package dirty scope, saves only Show,
   Master, level and the new sequence, reloads/read-backs, then emits
   `E25_ENDING_APPLY_OK`.
6. Run `InfinityStage.Editor.SavedMasterMatchesShow` and
   `InfinityStage.Editor.SceneCutBindingsResolve` separately. Require each test's
   own Success line; MCP transport success is not a test result.
7. Capture the four planned stills: total black, first wide stage reveal, mid
   arrival, and final Opening-stage home. Judge the absence of infinity/hangar/sky,
   the mask edge, curtain, P87 bulbs/uplights, and final composition.
8. In PIE, verify S6 ends in true black, the new camera cut resolves without a
   frame leak, the stage-only arrival plays once, and Closing follows. This is
   rendered/runtime acceptance and remains outside the offline result.

## Revert

With the applied state unchanged, set `mode=REVERT`, set `source_run_id` to the
APPLY run, and confirm `REVERT E25 <source-run>`. REVERT takes
`Backups/PreE25EndingRevert-<run>`, removes only the recorded label/GUID cue and
owned mask, rebuilds Master, moves (does not delete) the sequence under
`/Game/InfinityStage/Dev/Sequences/_Reverted/`, saves named packages, and reads
back the original spine. Run both editor tests again.

## Offline harness

```powershell
python Saved/CodexConductor/E25Ending_20261009/test_e25_ending.py
```

Expected: `E25_ENDING_HARNESS_OK|positive=10|negative=20|checks=30`.
