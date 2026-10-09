# P79 Nap interlude — offline delivery report

Date: 2026-10-09

## Verdict

- **[measured] OFFLINE TOOLING PASS.** The pure-Python harness completes 3/3 positive controls, 9/9 negative controls, and 25 assertions, ending `P79_NAP_HARNESS_OK|positive=3/3|negative=9/9|checks=25` (`Saved/CodexConductor/NapInterlude_20261009/test_nap_interlude.py:136-209`; `Saved/CodexConductor/NapInterlude_20261009/harness_result.json:1-11`).
- **[UNCLEAR] LIVE/RENDERED ACCEPTANCE.** Unreal, Blender, MCP, PIE, package saves, stage output, and the Cue Desk were not run, as required by the offline brief (`Docs/Conductor/codex_briefs/_house_rules.md:2-4`; `Docs/Conductor/codex_briefs/p79_nap_interlude.md:3-4`).

## Delivered

- **[declaration-proven]** `nap_interlude.py` provides guarded DRY/APPLY/REVERT entry points with exact confirm strings (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:726-739`; `Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:742-804`; `Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:807-825`).
- **[declaration-proven]** APPLY refuses changed-since-DRY state and unpinned S4/P05 identities; it writes an exclusive record after required backups and before mutation (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:742-757`).
- **[declaration-proven]** APPLY requires an exact four-package dirty census, targets only the Show, Master, level, and new sequence, then repeats semantic read-back before its success marker (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:757-776`).
- **[declaration-proven]** REVERT removes the exact Nap GUID and exactly the tagged owned actors, rebuilds the managed Master, and archives rather than deletes the new sequence (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:686-705`; `Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:779-804`).
- **[declaration-proven]** The operator wrapper and editable defaults are `nap_interlude_run.py`, `nap_interlude_request.json`, and `nap_interlude_args.json`; the ordered live procedure is documented (`Saved/CodexConductor/NapInterlude_20261009/README.md:21-52`).
- **[measured]** The default plan preview was generated offline as `nap_interlude_preview_default.png`; the harness validates its PNG signature and nontrivial payload (`Saved/CodexConductor/NapInterlude_20261009/test_nap_interlude.py:166-170`).

## Authored plan

- **[declaration-proven]** Defaults expose Gary-owned values: 20-second vamp loop, 1-second wake tail, 4-second breathing period, 1.5 cm amplitude, held-pose fraction, cat/camera transforms, 65 mm lens, 4 cm drift, and two light definitions with new shadow casting off (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:99-159`).
- **[declaration-proven]** The selected catalogue clip is `Rest/A_Cat_Rest_Sleep_to` (`Saved/CodexConductor/CatSilhouettes_20261009/cat_silhouette_bench.py:19-26`; `Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:118-120`).
- **[inferred]** Holding that transition clip at 85% should read as sleeping Puss, but pose quality, mesh compatibility, floor contact, and silhouette have not been rendered (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:116-120`; `Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:564-573`).
- **[declaration-proven]** Breathing keys close on the same value and slope, require whole four-quarter cycles, and are verified at read-back (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:170-198`; `Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:355-373`).
- **[declaration-proven]** The new Level Sequence owns cat, camera, at most two non-shadow-casting Rect Lights, visibility/transform tracks, camera cut, and three marked frames (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:549-604`; `Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:606-669`).
- **[declaration-proven]** Passage authoring data is not changed, so no Passage Actor is materialized; managed-Master rebuild is followed by numeric carry verification for every later Passage channel key (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:257-269`; `Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:668-670`).
- **[declaration-proven]** Patch K moves an existing Passage section before resetting its range, carrying all proxy channels when earlier content changes duration (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp:300-309`).

## Operator semantics and open decision

- **[declaration-proven]** Transport converts any HOLD at or inside a vamp range to PASS (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1105-1123`).
- **[declaration-proven]** The tool therefore marks `VampStart` at frame 0, `VampEnd` at frame 500, and `GO 79 HOLD Wake Puss` at frame 525, producing a 20-second repeatable loop plus a 1-second wake tail (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:301-335`).
- **[inferred]** With current transport code, the first GO releases the vamp and plays to segment end, then the out-of-vamp HOLD requires a second GO to enter P05 (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1572-1603`; `Saved/CodexConductor/NapInterlude_20261009/README.md:62-68`).
- **[UNCLEAR]** Gary/conductor must choose two-GO operation as authored, or one-GO operation by changing the wake marker to PASS or changing the transport contract; the tool deliberately does not conceal this choice (`Saved/CodexConductor/NapInterlude_20261009/README.md:62-68`).

## Fallback and transition

- **[declaration-proven]** APPLY emits `nap_fallback_job_<run>.json` for exactly the 500-frame vamp loop, not the wake tail (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:342-350`; `Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:769-775`).
- **[declaration-proven]** Current fallback registry parsing accepts a `scenes` object keyed by S-number (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageVideoFallback.cpp:58-97`).
- **[declaration-proven]** Current Cue Desk fallback selection skips every non-Scene segment (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageVideoFallback.cpp:317-329`).
- **[UNCLEAR]** The delivered capture specification can drive later filming, but a rendered Nap clip cannot yet be selected for this Sequence cue without a separate reviewed fallback-registry/Cue-Desk extension; no such C++ change was authorized or tested here (`Saved/CodexConductor/NapInterlude_20261009/README.md:45-52`).
- **[declaration-proven]** The plan reports three non-applied P05 transition options: fade-through, clouds rising, and camera drift up (`Saved/CodexConductor/NapInterlude_20261009/nap_interlude.py:346-350`).

## Harness coverage

- **[measured]** Positive controls cover plan anchors/markers/seam/timing, a fake-backend DRY→APPLY→REVERT round trip with success markers/read-back, and preview creation (`Saved/CodexConductor/NapInterlude_20261009/test_nap_interlude.py:136-170`).
- **[measured]** Negative controls catch seam discontinuity, missing wake marker, downstream timing drift, S4 GUID drift, P05 GUID drift, pre-existing sequence asset, actor collision, incompatible breath period, and wrong confirmation (`Saved/CodexConductor/NapInterlude_20261009/test_nap_interlude.py:172-203`).
- **[UNCLEAR]** Live gates remain `InfinityStage.Editor.SavedMasterMatchesShow`, `InfinityStage.Editor.SceneCutBindingsResolve`, repeated-vamp seam viewing, wake/HOLD behavior, P05 handoff, lighting/shadows/framing, and real battery-change duration (`Saved/CodexConductor/NapInterlude_20261009/README.md:41-52`).

## Live order

1. **[declaration-proven]** Run DRY in the correct open level with clean census; require `P79_NAP_DRY_OK` (`Saved/CodexConductor/NapInterlude_20261009/README.md:23-29`).
2. **[declaration-proven]** Review the JSON/PNG, approve creative values and two-GO semantics, pin the discovered S4/P05 GUIDs, then repeat DRY (`Saved/CodexConductor/NapInterlude_20261009/README.md:29-34`).
3. **[declaration-proven]** Run APPLY against the identical snapshot/plan; require `P79_NAP_APPLY_OK` only after targeted save and read-back (`Saved/CodexConductor/NapInterlude_20261009/README.md:34-40`).
4. **[declaration-proven]** Run both named automation tests separately, then complete PIE/rendered/operator acceptance and film one loop after the fallback integration decision (`Saved/CodexConductor/NapInterlude_20261009/README.md:41-52`).
