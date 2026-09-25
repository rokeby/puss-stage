# Passage-to-Scene transition repair — 14 September 2026

The production Show now continues normal Passage playback into its following cinematic Scene. All six handoffs passed in normal Play In Editor, and an uninterrupted Passage 3 run reached the Shore camera and animation. The current full regression suite is **43/44**, with the previously recorded curtain hidden-changeover assertion still failing.

## Working on Scenes

- Leave **View → Play Through Boundaries** off for ordinary Passage-plus-Scene playback followed by a hold. Turn it on only to run through all subsequent Show segments.
- **Play Selected** still enters a selected Scene/SEQ at its first frame. With the production Show's new setting enabled, **Next Segment** also starts a Scene automatically; entering a new Passage still holds at its start.
- Edit Scene content in its own sequence. Shore routing is Show → `LS_DevScene_03` → `LS_Clams`.
- After changing a containing Scene's playback range, use **Actions → Rebuild Managed Master Sequence**. All thirteen non-Wing cues now derive their duration from their own sequence. A nested content sequence does not automatically resize its parent shot or containing Scene.
- Re-run **Actions → Scene Camera Handoff → Check All Scenes (read-only)** after changing a Passage route or lens. All six currently match.

Scene 3's authored 14,641-frame range at 25 fps is preserved (585.64 seconds). Its `LS_Clams` shot still begins at containing frame 589, or 23.56 seconds into the Scene. Its 30 fps animation timebase is preserved. This repair removes the old 15-second Show cap; it does not retime the artist's Scene content or shorten its lead-in.

## Repairs

- Added the opt-in `Auto Play Scene After Passage` setting to the Transport component and enabled it on the production Show Root. One uninterrupted root-player operation plays Passage → Scene and holds at the Scene end. Existing Shows retain their previous behavior unless enabled.
- Camera ownership now uses an exclusive segment end, so the new Scene owns its exact first frame. The terminal Show endpoint still resolves to its last segment.
- Explicit Scene camera lookup converts Show ticks to the Scene sequence's tick resolution.
- Enabled sequence-derived lengths on all six Scene cues and rebuilt the managed Master: six Passage sections, thirteen Scene/SEQ sections, six music sections, no missing references.
- Closed Scene 3's cut gaps by extending the preceding cuts to the next cut or playback end: 561 → 605, 13,575 → 13,606, and 14,509 → 14,641. Shot starts, bindings and animation keys were preserved.

## Verification

- UE 5.8.2 clean build passed. Both new runtime symbols are present in the base DLL; no numbered hot-reload DLLs were present.
- Focused Transport group: 2/2 passed. Full suite: 43/44, including exact-boundary camera ownership. The sole failure is `PussStage.InfinityStage.Functional.SavedFixturePIE`, “Interaction sequence is fully lowered at its hidden-changeover marker.” It also failed in the 28 August baseline.
- Independent Unreal read-back passed for sequence lengths, cut coverage, resolved camera bindings and all six handoff endpoint comparisons.
- Normal PIE verified all six Passage → Scene transitions, continued playback and the subsequent Scene-end hold. Stop positions differ from the target by one 24,000-Hz tick (about 42 microseconds), within the verifier's one-tick tolerance.
- The single production Show player drove all six Shore bodies with changing head transforms and attached, enabled Chaos drapes. No separate animation player or binding overrides were used.
- An uninterrupted normal PIE run from one second before the Passage 3 boundary reached the Scene entry shot and then `ClamCam1` at 30.2 seconds into the Scene. Native game-viewport screenshots were inspected. The preceding SIE render attempt did not advance the native cinematic camera cut; normal PIE is the evidence for camera-cut playback.
- The saved production level was reloaded and the enabled transport setting plus all thirteen sequence-derived cue lengths were confirmed again. Validation restored the temporary background CPU-throttle preference and ended outside PIE.

Evidence under `Saved/CodexSceneTransitions/`: `authoring_result.json`, `authoring_verification.json`, `runtime_result.json` (normal PIE), `runtime_simulation_result.json`, `render_result.json`, `Passage3_Into_Scene3.png`, `Scene3_Shore_From_Show.png`, and `source_repair.diff`. Named build/test logs are `Saved/Logs/SceneTransitions-*-20260914.log`.

Backups: `Backups/PreSceneTransitions-20260914-145718`. `UserSavedCheckpoint` preserves the user's saved state from immediately before this implementation; `BeforeAuthoring` preserves the assets immediately before authoring changes. `LS_Clams` and the Shore character/animation/cloth assets were not changed by this repair. Final scene composition, cloth aesthetics, curtain coverage and a full eighteen-seam rehearsal remain separate work.
