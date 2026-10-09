# S6 old-lady hand-driven swarm — 9 October 2026

## Outcome

- **[binary-proven]** The imported Animation Sequence is `/Game/CaptureManager/Imports/Mono_Video_Ingest/Old_woman_1/AS_MHP_Void_woman`; the S6 hook-in binds `AS_MHP_Void_woman` on the woman's Body inside `/Game/InfinityStage/KlaraHookin/LS_Void_S6` (`Saved/CodexConductor/KlaraIngest/Void/census_report.json:8166-8167`; `Saved/CodexConductor/KlaraIngest/klara_void_s6_args.json:239-244`). **[measured from saved record]** The Scene 6 shot nests at frame 104 in a 25 fps scene, hence S6 +4.16 s (`Saved/CodexConductor/KlaraIngest/klara_void_s6_record.json:179-190`; `:418`).
- **[measured]** No matching FBX/BVH/CSV source was found in the active project's DerivedAssets, Saved, SourceAssets, ContentSource or Import roots, so the required fallback is the read-only editor sampler (`DerivedAssets/S6OldLadySwarm/source_search.json:2-26`).
- **[binary-proven, prior census]** Klara's `/Game/FX/NS_BeeSwarm` has no `User.` parameters and a constant spawn rate, while our C++ swarm still lacks `/Game/Scenes/Effects/Swarm/NS_BeeSwarm`; therefore this job uses Klara's existing actor binding and never edits the Niagara asset (`Docs/Conductor/EFFECTS_PLAN_2026-10-07.md:55`).
- **[inferred, creative proposal]** The swarm centre follows the hand midpoint and recoils opposite the faster hand's velocity at batting peaks. Uniform actor scale expands on a bat and decays back over 0.65 s; inverse scale volume is reported as concentration density. Recoil (180 cm), dispersion (0.55), smoothing and thresholds are CLI arguments and remain Gary's values (`Tools/Mocap/s6_old_lady_swarm.py:85-105`; `Tools/Mocap/s6_old_lady_swarm.py:169-175`).

## Deliverables

- **[declaration-proven]** `sample_hands.py` is read-only: it evaluates the existing hook-in copy at 24 fps, records both hand world positions, the resolved Animation Sequence, its section range, internal start offset and play rate, and requires an unchanged dirty-package census (`Saved/CodexConductor/S6OldLadySwarm/sample_hands.py:1-6`; `:82-157`).
- **[declaration-proven]** `s6_old_lady_swarm.py` emits contiguous 24 fps S6-time JSON keys with per-hand speed, batting peaks, world/local swarm centre, scale and density, plus an 1800×720 PNG (`Tools/Mocap/s6_old_lady_swarm.py:69-135`; `:139-185`).
- **[declaration-proven]** `swarm_sequence.py` provides DRY/APPLY/REVERT. APPLY records the normalized cue GUID and exact census, snapshots `LS_DevScene_06`, duplicates `LS_Void_S6` create-only, writes suffixed transform channels by normalized base name, saves only the duplicate and Scene sequence, and reads back all six key counts. REVERT restores the source nesting and archives the generated asset without deletion (`Saved/CodexConductor/S6OldLadySwarm/swarm_sequence.py:43-64`; `:146-218`; `:221-240`).
- **[measured, offline]** The harness passes **17/17** positive, negative and static safety controls (`Tools/Mocap/test_s6_old_lady_swarm.py:48-88`). Python compilation also passes for all four scripts.
- **[measured, synthetic only]** `DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_response_SYNTHETIC_PREVIEW.png` demonstrates the curve relationship and is visibly watermarked; it is not old-lady evidence. The real JSON/PNG cannot honestly exist until the editor sampler is run (`DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_preview_manifest.json:2-8`).

## Conductor run order

1. **[declaration-proven]** Close Sequencer and require a clean PussStage editor in the vertical-slice world. Run `sample_hands_request.json`; require `S6_OLD_LADY_HAND_SAMPLE_OK`.
2. **[declaration-proven]** Offline: `python Tools/Mocap/s6_old_lady_swarm.py Saved/CodexConductor/S6OldLadySwarm/hand_samples.json --json DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_drive.json --png DerivedAssets/S6OldLadySwarm/s6_old_lady_swarm_curves.png`; require `S6_SWARM_CURVES_OK`.
3. **[declaration-proven]** Run `swarm_sequence_request.json`; a missing runtime args file defaults safely to `DRY S6_OLD_LADY_SWARM`. Inspect cue GUID, source counts, proposed key count and zero dirty packages.
4. **[declaration-proven]** Change args to `APPLY` / `APPLY S6_OLD_LADY_SWARM`; require `S6_SWARM_SEQUENCE_APPLY_OK`, six identical read-back key counts, exactly two named saves and dirty=0.
5. **[inferred]** Gary judges the result in motion. The actor-scale route changes both cloud spread and sprite size; if that reads as inflation rather than dispersion, the next route is a create-only Niagara copy with an exposed concentration parameter. No such asset was authored offline.

## Acceptance boundary

- **[measured]** Offline algorithms, PNG rendering, guard ordering and syntax pass.
- **[inferred]** UE API execution, actual old-lady hand curves, saved/read-back state, and rendered quality remain unmeasured because this job was explicitly offline-only.
