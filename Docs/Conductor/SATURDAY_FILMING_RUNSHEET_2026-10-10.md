# Saturday Scene filming run sheet — 10 Oct 2026

This makes temporary video fallbacks for all six Scenes. They are stand-ins, not final recordings. The single entry
point is `Tools/Fallbacks/saturday_night_film.ps1`; do not run the individual render or post scripts by hand unless
diagnosing a stopped delivery.

## Before starting

1. **[declaration-proven]** Save only the named work that should appear in the fallbacks, then close every Unreal Editor
   and Blender. The wrapper refuses if `UnrealEditor`, `UnrealEditor-Cmd` or `blender` is running
   (`Tools/Fallbacks/saturday_night_film.ps1:28-35`). Do not use Save All.
2. **[declaration-proven]** Stop the GO1 bridge and leave the mouse alone during render. The Master, Show, map and Scene
   assets on disk are what render; unsaved edits cannot appear (`Docs/Conductor/MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md:119-122`).
3. **[declaration-proven]** Do not run `editor_sky_toggle.py`. The command-line render starts from saved Show/sequence
   state; the wrapper records that policy (`Tools/Fallbacks/saturday_night_film.ps1:127-129`). Morning QC must judge
   whether each Scene's intended sky/exposure is present.
4. Pick an unused `vNN`. BUILD is create-only and refuses an existing MRQ config version. Use the **same RunId and
   Version** for DRY, APPLY and any resume.

## Start once

From PowerShell in `E:\PussStage`:

```powershell
$run = "SATFILM-20261010"
powershell -NoProfile -ExecutionPolicy Bypass -File .\Tools\Fallbacks\saturday_night_film.ps1 `
  -Mode APPLY -Confirm "APPLY SATURDAY_FILM" -RunId $run -Version v01
```

That is the unattended Saturday invocation: APPLY performs its own live DRY before BUILD. To inspect current time/disk
estimates without creating configs or rendering, an optional earlier check is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Tools\Fallbacks\saturday_night_film.ps1 `
  -Mode DRY -RunId $run -Version v01
```

**[declaration-proven]** DRY reads current Scene section ranges from the live Master, probes transient UE 5.8 MRQ
settings, performs the exact dirty-package census, and prints disk plus low/mid/high time estimates. APPLY repeats that
read, creates and reads back only the named MRQ config packages, then renders S1 through S6 in P and C tiers
(`Saved/CodexConductor/MRQ/mrq_fallbacks.py:792-890`; `Tools/Fallbacks/saturday_night_film.ps1:165-201`).

APPLY stops unless its internal DRY and disk gate pass. Its successful terminal marker is `SATFILM_APPLY_OK`.
`SATFILM_APPLY_INCOMPLETE` means inspect the summary and resume.

## Time and disk

- **[inferred from the 7 Oct fixture, not a render measurement]** P: 1.1 / 3.0 / 7.5 render hours at low/mid/high
  assumptions; C: 7.8 / 15.5 / 31.1 hours. Startup and encode/QC add time. The new DRY output supersedes these numbers.
- **[inferred from the 7 Oct 3.5 MB/frame estimate]** P raw frames: about 92.2 GB; C: about 95.9 GB. The wrapper gates
  free disk at 1.3 times both selected tier estimates plus 5 GB. It never deletes frames
  (`Tools/Fallbacks/saturday_night_film.ps1:76-94`; `Saved/CodexConductor/MRQ/mrq_render.ps1:1-21`).

## Stop and resume

- Ctrl+C stops the active wrapper. Wait until its `UnrealEditor-Cmd` child is gone before restarting.
- Run the identical APPLY command. **[declaration-proven]** The checkpoint skips completed render/encode/QC/promote
  stages. A partial frame directory or partial encoded file is renamed aside, never deleted
  (`Tools/Fallbacks/saturday_film.py:68-87,124-174`).
- One failed delivery stops at that failure and the script continues to the next Scene. C is skipped when that Scene's P
  delivery failed. Failures never reach promotion (`Tools/Fallbacks/saturday_film.py:183-196,222-236`).

To roll back only the published registry/jobs pointer while retaining all configs and render evidence:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Tools\Fallbacks\saturday_night_film.ps1 `
  -Mode REVERT -Confirm "REVERT SATURDAY_FILM" -RunId $run -Version v01
```

## Outputs and morning review

- Per-Scene media/QC: `Renders/Fallbacks/S1` … `S6`.
- Checkpoint, per-Scene logs, summary and short report: `Renders/Fallbacks/_Saturday/<RunId>/`.
- Registry consumed by Cue Desk: `Renders/Fallbacks/current.json`.
- Pre-change record: `Backups/PreSaturdayFilm-<RunId>/prechange_record.json`.

**[declaration-proven]** QC blocks promotion on frame count, duration beyond one frame, resolution/rate, or missing audio;
it detects black and frozen stretches for human review (`Saved/CodexConductor/MRQ/mrq_post.py:164-174,322-374`).
In the morning, open every contact sheet and clip and judge: intended darkness versus missing image; static staging versus
a frozen cache; sky/exposure; streamed sets; camera cuts; cloth/foam motion; no HUD/debug text; audio sync; no click track.

**[declaration-proven]** Cue Desk reloads `current.json`; only Scenes present under `scenes.S<n>` enable **Use video**.
Select the desired Scene checkboxes and audio owner, then reload with F5
(`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageVideoFallback.cpp:48-98`;
`Plugins/InfinityStage/Source/InfinityStageEditor/Private/SInfinityStageCueDirectorPanel.cpp:248-251`).
