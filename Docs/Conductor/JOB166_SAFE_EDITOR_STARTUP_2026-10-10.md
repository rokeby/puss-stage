# Job 166: opt-in safe editor startup for scripted work

**Date:** 2026-10-10
**Scope:** offline log/config/installed-engine inspection and reversible launcher/profile authoring only. Unreal was not opened and no build was run.

## Verdict

- **measured:** The 04:49 local crash was a D3D12 device reset, but it was not literally in the first rendered frames: the log reaches frame 3150. The vertical-slice map began loading at 08:47:52 UTC, its startup script completed at 08:48:10, and the reset was reported at 08:49:09. Active breadcrumbs included GPU skin cache, Global Distance Field update, Niagara GPU dispatch and Lumen scene-buffer update. `E:/PussStage/Saved/Logs/PussStage-backup-2026.10.10-08.49.12.log:2265,2800-2811,2847-2877`
- **measured:** The 11:34 local event did occur in the first viewport frames. The same vertical-slice map started at 15:33:54 UTC; the editor startup script finished at 15:34:12; 3D and Compute payloads both exceeded 5 seconds at 15:34:27. The breadcrumb frame is 5 and the log frame is 7. `E:/PussStage/Saved/Logs/PussStage.log:2265,2800-2824,3115-3176,3378-3405`
- **measured:** The reset log reports 8408.14 MB local VRAM used against a 15227 MB local budget. This is not evidence of VRAM-budget exhaustion. `E:/PussStage/Saved/Logs/PussStage-backup-2026.10.10-08.49.12.log:2886-2890`
- **inferred:** Both failures are consistent with an expensive first render/update of the full show world, but the breadcrumbs do not identify one proven root cause. In the first reset several passes are simultaneously marked active; in the second many named passes are still “Not Started.” Driver/hardware instability remains unexcluded.

## Existing startup state

- **declaration-proven:** Both game and editor default maps are the 37.9 MB vertical-slice map; mesh distance fields, Lumen GI/reflections and ray tracing are enabled project-wide. `Config/DefaultEngine.ini:3-25`; map size measured read-only at `E:/PussStage/Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap`.
- **declaration-proven:** `DefaultEditorPerProjectUserSettings.ini` configures MCP on port 8010 but has no startup rendering override. `Config/DefaultEditorPerProjectUserSettings.ini:1-8`
- **declaration-proven:** `DefaultEditor.ini` contains asset-preview profiles, not the level startup map or a scripted-work profile. `Config/DefaultEditor.ini:1-5`

## Delivered profile

- **declaration-proven:** `PussStage_ScriptedSafe.ps1` launches this project with `-CustomConfig=ScriptedSafe`, refuses an accidental second editor unless explicitly overridden, and supports `-DryRun`. `PussStage_ScriptedSafe.ps1:1-50`
- **declaration-proven:** The custom layer changes only `EditorStartupMap` to the installed 28 KB `/Engine/Maps/Entry` and appends one Python startup hook. It is loaded only when the custom-config argument is present. `Config/Custom/ScriptedSafe/DefaultEngine.ini:1-9`; `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Core/Public/Misc/ConfigHierarchy.h:24-29`; `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Core/Public/Misc/ConfigCacheIni.h:1807-1811`
- **declaration-proven:** The hook captures the project's actual cvar values, applies the safe values below, turns level-editor viewport realtime off, restores every captured value at PreBeginPIE, and reapplies safe mode at EndPIE. `Scripts/Unreal/p166_scripted_safe_startup.py:18-113`
- **declaration-proven:** The hook never sets `r.RayTracing=0`. UE 5.8 marks that project capability restart-required, so disabling it at process startup would prevent a trustworthy restoration for PIE stills. Only Lumen's hardware-ray-tracing path is disabled transiently. `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Engine/RendererSettings.h:617-621,673-677`
- **inferred:** Starting on `/Engine/Maps/Entry` should remove the vertical slice's initial skinning/distance-field/Niagara/Lumen burst. Stability improvement is not measured until the conductor runs the profile in Unreal.

### Safe cvars

| Setting applied for scripted editor work | Tier and UE 5.8 on-disk verification |
| --- | --- |
| `r.Lumen.DiffuseIndirect.Allow=0` | **declaration-proven:** exact spelling/value used by Low GI scalability. `D:/Unreal Engine/UE_5.8/Engine/Config/BaseScalability.ini:318-324` |
| `r.Lumen.Reflections.Allow=0` | **declaration-proven:** exact spelling/value used by Low reflections scalability. `D:/Unreal Engine/UE_5.8/Engine/Config/BaseScalability.ini:514-522` |
| `r.Lumen.HardwareRayTracing=0` | **declaration-proven:** exact console-variable name and fallback-to-software semantics. `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Engine/RendererSettings.h:617-621` |
| `r.DistanceFields.TextureUploadLimitKBytes=1024` | **binary-proven:** the installed 5.8 renderer DLL contains the exact name and help text “Max KB of distance field texture data to upload per frame from streaming requests.” No `r.DistanceFields.UpdateBudget` declaration was found in the installed 5.8 headers/config; this is the supported per-frame distance-field upload budget. The 1024 KB value is **inferred** as a conservative first live trial, not an Epic default. `D:/Unreal Engine/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Renderer.dll` UTF-16 strings near `r.DistanceFields.TextureUploadLimitKBytes`. |
| `fx.NiagaraAllowGPUParticles=0` | **declaration-proven:** exact spelling/value is used by an Epic device profile specifically to disable Niagara GPU compute. `D:/Unreal Engine/UE_5.8/Engine/Config/BaseDeviceProfiles.ini:1477-1482` |
| `fx.Niagara.QualityLevel=0` | **declaration-proven:** exact spelling/value is Low effects quality. `D:/Unreal Engine/UE_5.8/Engine/Config/BaseScalability.ini:818-825` |
| `t.MaxFPS=30` | **binary-proven:** the installed Engine DLL contains the exact name and help “Caps FPS to the given value. Set to <= 0 to be uncapped.” `D:/Unreal Engine/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Engine.dll` UTF-16 strings near `t.MaxFPS`. |

**inferred:** `t.MaxFPS=30` reduces sustained submission pressure; it does not alter Windows TDR thresholds and is not, by itself, proof that a frame cannot time out. This job intentionally makes no registry/TDR change.

## Show-look / still isolation

- **declaration-proven:** PreBeginPIE restores the values captured before safe mode; EndPIE restores safe mode. A PIE still therefore must be taken only after the log marker `P166_SCRIPTED_SAFE_APPLIED|reason=pre-begin-pie` and must not proceed after `P166_SCRIPTED_SAFE_PIE_RESTORE_FAILED`. `Scripts/Unreal/p166_scripted_safe_startup.py:66-103`
- **declaration-proven:** For a non-PIE editor-viewport still, call `p166_scripted_safe_startup.restore_show_settings("editor-still")` first and verify its `P166_SCRIPTED_SAFE_APPLIED` marker. Reapply with `apply_safe_settings("after-editor-still")` when finished. `Scripts/Unreal/p166_scripted_safe_startup.py:57-77`
- **declaration-proven:** Global hardware-RT capability remains enabled, so the captured show value of `r.Lumen.HardwareRayTracing` can be restored without an editor restart. `Config/DefaultEngine.ini:16-23`; `Scripts/Unreal/p166_scripted_safe_startup.py:18-27,89-109`
- **inferred:** Delegate timing and visual equivalence remain live acceptance gates. A cvar read-back marker is not rendered proof of the show look.

## How to use

1. **measured offline:** Inspect without launching: `powershell -NoProfile -ExecutionPolicy Bypass -File .\PussStage_ScriptedSafe.ps1 -DryRun`.
2. **declaration-proven:** Close any existing Unreal Editor, then run `powershell -NoProfile -ExecutionPolicy Bypass -File .\PussStage_ScriptedSafe.ps1`.
3. **declaration-proven:** Require `P166_SCRIPTED_SAFE_INSTALLED` plus `P166_SCRIPTED_SAFE_APPLIED|reason=editor-start` in `Saved/Logs/PussStage.log` before loading the show.
4. **declaration-proven:** A scripted tool may then load `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` explicitly with its existing guarded map-loading route. The profile does not change the Show asset or the normal startup map.
5. **declaration-proven:** To revert, close this editor and start the project normally. No config rewrite or cleanup is needed.

**declaration-proven:** The repository's root-only ignore rule also ignores the new root launcher, so the conductor must import/commit `PussStage_ScriptedSafe.ps1` explicitly with `git add -f`; the custom ini, Python hook, harness and this report are normally visible to git. `.gitignore:11`

## Offline validation and acceptance boundary

- **measured:** `test_p166_scripted_safe_startup.py` passed 11/11 controls using UE 5.8's bundled Python. Positive controls cover capture, safe apply, viewport disable, PreBeginPIE restore and EndPIE reapply. Negative controls cover idempotence, rejected cvar read-back and missing originals. `Scripts/Unreal/test_p166_scripted_safe_startup.py:1-113`
- **measured:** Launcher dry-run printed the correct editor executable, quoted worktree project path, custom profile, Entry map, and `DRY_RUN_OK|no_process_started=true`.
- **measured:** `Config/DefaultEngine.ini`, `Config/DefaultEditor.ini`, and `Config/DefaultEditorPerProjectUserSettings.ini` were not modified by this job.
- **inferred / pending conductor:** No Unreal startup, live cvar read-back, PIE transition, still comparison, GPU trace, or crash-free soak was performed because Job 166 is offline-only. Those are the remaining acceptance gates.
