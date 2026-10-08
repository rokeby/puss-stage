# Infinity Stage rehearsal operator runbook — 8 Oct 2026

## Before pressing Play

1. **[declaration-proven]** Open the vertical-slice level and Cue Desk. Require the status rail to say `READY`, never `SHOW MISMATCH`; the rail compares the desk's Show with the level Show (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:6747-6770`).
2. **[declaration-proven]** For rehearsal, tick **Rehearsal**. **Current-binary workaround:** after PIE starts, toggle it off/on once or click a Cue Desk transport button before using viewport-held Left/Right; the saved preference is otherwise not pushed on an ordinary PIE start. The held fix is `Scripts/patches/2026-10-08_rehearsal_preference_on_pie.patch:33-78`. For performance, leave Rehearsal off.
3. **[declaration-proven]** Leave **Play Through Boundaries** off except for the deliberate 18-seam test; when on, forward play runs to Show end and bypasses operator stops (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:3031-3052`, `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1206-1215`).
4. **[declaration-proven]** Leave **PIE Starts At Playhead** off for a top-to-bottom run; turn it on only for a bounded rehearsal entry (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:2987-3008`).
5. **[declaration-proven]** Press **H** for the Director HUD (segment, bay, GO context); H is bound in the show controller (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageShowGameMode.cpp:42-59`).

## Controls

| Input | Operator result |
|---|---|
| **Space** | GO through an active HOLD; otherwise play/hold. In performance, an unpausable external-sound Scene refuses hold; `bSpaceNeverPauses` may also deliberately ignore pause (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageShowGameMode.cpp:170-185`). **[declaration-proven]** |
| **Right tap** | Release an active GO HOLD or vamp; otherwise next Scene shot, then next segment (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageShowGameMode.cpp:111-161`). **[declaration-proven]** |
| **Right hold ≥ 0.30 s** | 4× forward, audio muted. Performance mode refuses it inside a `DeclaredUnpausable` segment (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1365-1389`). **[declaration-proven]** |
| **Left tap** | Restart the current Scene shot after the 12-frame grace; near its start, step to the prior shot/segment (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1551-1599`). **[declaration-proven]** |
| **Left hold ≥ 0.30 s** | 4× rewind, audio muted; refused inside, and will not rewind into, an unpausable external clock (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1417-1482`). **[declaration-proven]** |
| **Play Selected** | Select exactly one Scene/SEQ. It enables Rehearsal, cues the exact first frame, and plays only to its boundary (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:5586-5675`). **[declaration-proven]** |
| Cue Desk transport row | Previous, start, reverse-to-boundary, hold, forward, end, next (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:4087-4100`). **[declaration-proven]** |
| View → Live Camera Owner | **Force Timeline** is the dog-loss recovery; **Follow Show** restores authored ownership (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:5457-5492`). **[declaration-proven]** |

## Failure table

| Symptom | Meaning | Recovery |
|---|---|---|
| `result=4` / `UnsafeExternalClock` in S3 | **[declaration-proven]** Enum value 4 is the performance interlock (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTransportController.h:23-31`); hold/rate change/move is refused while the current segment is `DeclaredUnpausable` (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:2563-2589`). | **Rehearsal:** tick Rehearsal after PIE starts, click a Cue Desk transport button, retry. **Performance:** do not fight the clock; continue at 1× or coordinate a restart with the cellist. |
| VampEnd jumps to S3 end | **[measured]** Gary's 8 Oct recording did this; the current markers are removed (`Docs/Conductor/codex_briefs/p2_vamp_bug.md:1-4`). | Do not restore the vamp markers until the held patch is built. If encountered, stop when safe, select S3, use **Play Selected**, and restart the music/cellist together. |
| GO does not hold in S3 | **[declaration-proven]** An unsafe GO HOLD is consumed as PASS (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:2661-2683`). | Continue the external clock. For rehearsal inspection, enable Rehearsal first. |
| `NoPlayer` | **[declaration-proven]** No matching live sequence player (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1150-1156`). | Start PIE; if PIE is already running, clear `SHOW MISMATCH` with **View → Use Current Level Show**, then restart PIE. |
| `NotReady` | **[declaration-proven]** The selected or stop segment did not load/compile ready (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1157-1161`). | Do not skip blindly. Stop PIE, check the selected cue has a sequence, restart from the last known curtain/Scene. |
| Play Selected is disabled/fails | **[declaration-proven]** It requires one non-Wing Scene/SEQ with a non-null sequence and the same Show in PIE (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:5586-5605`, `Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:5624-5683`). | Select one Scene/SEQ row; fix Show mismatch; restart PIE. |
| Actor/light vanishes before Scene end | **[binary-proven]** S1 and S4 contain mid-Scene `RESTORE_STATE` visibility sections; the review census is `Docs/Conductor/P14_SEQUENCE_COMPLETION_CENSUS_2026-10-08.json:1-752`. | Hold outside S3 if safe; restart from the preceding curtain. Do **not** bulk-fix during rehearsal—the candidate list includes intentional lighting exits. |
| Dog telemetry is lost | **[declaration-proven]** Live camera ownership can be overridden without editing the Show (`Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:5495-5524`). | Immediately choose **Force Timeline**. Restore **Follow Show** only when telemetry is stable. |
| Editor/PIE crashes or a blocking dialog appears | **[declaration-proven]** No blackout, checkpoint, or restart-from-curtain action exists in the searched operator source (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageShowGameMode.cpp:42-185`, `Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDesk.cpp:4087-4100`). | Use venue/house-light fallback, stop external sound, restart editor/PIE from saved state, select the last agreed Scene/SEQ, enable Rehearsal, and **Play Selected**. S3 restart must be coordinated with the cellist. |

**[inferred]** Treat the preceding curtain as the human checkpoint: the software has exact segment entry, but no persisted crash checkpoint or automatic external-clock resynchronisation.
