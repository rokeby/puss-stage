# Job 190 - S6 live-3D post-process warp

This package is offline-authored. It does not open Unreal, call MCP, run PIE, build C++, or save a package by itself.

Primary route: create-only `/Game/InfinityStage/Effects/S6/M_PP_S6Warp`, sampling `SceneTexture:PostProcessInput0` three times at displaced screen UVs; `/Game/InfinityStage/Effects/S6/MPC_S6Warp`; and one unbound PostProcessVolume whose actor default is weight 0 and whose `BlendWeight` is 1 only while `LS_DevScene_06` evaluates. MPC keys may be authored only in `LS_DevScene_06` (the current plan) or the Master. The nested `/Game/InfinityStage/KlaraHookin/LS_Void_S6` sequence and `CineCameraActor5` are read-only discovery inputs: they are never edited, backed up as mutation targets, or saved.

The P06 move-in may key only the P06 camera section in the Master. DRY predicts the cut from that pushed endpoint to the unchanged nested first camera. If it cannot meet 0.01 cm / 0.001 degree without a nested-camera edit, the combined plan is deliberately `apply_ready=0` with `MOVE_IN_DRY_ONLY|P06_MASTER_ONLY_CANNOT_MATCH_READ_ONLY_NESTED_CAMERA`; do not bypass that refusal. No source patch or build is required.

The default args are `mode=DRY`, `preset=both`, `void_mode=off`. The void is proposal-only: selecting `void_mode=proposal` deliberately makes DRY non-green until a live CustomStencil/hair-coverage probe exists and Gary approves it.

Live order after Job 185 releases the editor:

1. `python Scripts/ue58_api_preflight.py Saved/CodexConductor/Job190S6WarpPP_20261011` and require `deny=0`.
2. In the correct Puss editor, stop PIE/SIE, close Sequencer, load the vertical-slice world, and reach zero dirty packages.
3. Use a fresh run id in `job190_args.json`, leave `mode=DRY`, execute `job190_request.json`, and require `JOB190_DRY_OK`. Inspect `apply_ready` and every refusal; never treat a successful DRY execution as permission to APPLY.
4. Review the DRY record and `previews/both.svg`. Expect the move-in ownership refusal unless a P06/Master-only plan also proves the nested cut already matches. Do not run APPLY when `apply_ready=0`. A future green DRY must name exactly five saves: Master, `LS_DevScene_06`, the material, the MPC and the show map; no path under `KlaraHookin` is permitted.
5. Capture seam/S6 evidence in the order documented in `Docs/Conductor/JOB190_REPORT_2026-10-11.md`.
6. To revert a future green APPLY, point `record` at the apply record, set `mode=REVERT` and `confirm="REVERT JOB190 S6 WARP PP"`; require `JOB190_REVERT_OK`. REVERT removes the owned volume, binding and tracks and restores only the P06/Master camera channels. It retains the now-unreferenced material/MPC because asset deletion was not authorised.

