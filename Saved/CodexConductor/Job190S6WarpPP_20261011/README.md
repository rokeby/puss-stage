# Job 190 - S6 live-3D post-process warp

This package is offline-authored. It does not open Unreal, call MCP, run PIE, build C++, or save a package by itself.

Primary route: create-only `/Game/InfinityStage/Effects/S6/M_PP_S6Warp`, sampling `SceneTexture:PostProcessInput0` three times at displaced screen UVs; `/Game/InfinityStage/Effects/S6/MPC_S6Warp`; one unbound PostProcessVolume whose actor default is weight 0 and whose `BlendWeight` is 1 only while `LS_DevScene_06` evaluates; and the Job 189 P06 move-in. The live-3D route additionally retakes `LS_Void_S6`'s static first camera (`CineCameraActor5`) to the moved S6 entry pose, preventing a 240 cm backward cut when the nested shot begins. No source patch or build is required.

The default args are `mode=DRY`, `preset=both`, `void_mode=off`. The void is proposal-only: selecting `void_mode=proposal` deliberately makes DRY non-green until a live CustomStencil/hair-coverage probe exists and Gary approves it.

Live order after Job 185 releases the editor:

1. `python Scripts/ue58_api_preflight.py Saved/CodexConductor/Job190S6WarpPP_20261011` and require `deny=0`.
2. In the correct Puss editor, stop PIE/SIE, close Sequencer, load the vertical-slice world, and reach zero dirty packages.
3. Use a fresh run id in `job190_args.json`, leave `mode=DRY`, execute `job190_request.json`, and require `JOB190_DRY_OK|apply_ready=1`.
4. Review the DRY record and `previews/both.svg`. With the same run id and values, set `mode=APPLY` and `confirm="APPLY JOB190 S6 WARP PP"`; require `JOB190_APPLY_OK`, `volume_s6_only=1`, `build=none`, `dirty=0` in the record, and retain the backup and apply record.
5. Capture seam/S6 evidence in the order documented in `Docs/Conductor/JOB190_REPORT_2026-10-11.md`.
6. To revert, point `record` at the apply record, set `mode=REVERT` and `confirm="REVERT JOB190 S6 WARP PP"`; require `JOB190_REVERT_OK`. REVERT removes the owned volume, binding and tracks and restores the camera, but retains the now-unreferenced material/MPC because asset deletion was not authorised.

