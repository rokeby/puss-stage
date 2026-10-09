# P50 Saturday Scene filming — tiered delivery report (9 Oct 2026)

## Delivered

- **[declaration-proven]** One operator entry point now exposes guarded DRY/APPLY/REVERT modes with exact confirm
  strings, idle-process refusal, per-tier live estimates, a pre-change record/backup and non-deleting rollback
  (`Tools/Fallbacks/saturday_night_film.ps1:13-25,28-94,108-123,136-163`).
- **[declaration-proven]** APPLY invokes UnrealEditor-Cmd only after the interactive editor and Blender are absent. Its
  DRY and create-only BUILD call the existing survey, which re-reads all six Scene sections from the current Master,
  takes an exact dirty-package census, saves only new named MRQ configs and reads them back
  (`Tools/Fallbacks/saturday_night_film.ps1:37-70,127-175`;
  `Saved/CodexConductor/MRQ/mrq_fallbacks.py:792-890`).
- **[declaration-proven]** The resumable driver validates the complete S1-S6/P-C matrix, checkpoints each render,
  encode, QC and promotion stage, moves partial output aside, writes one log per Scene, stops the failed delivery and
  continues later Scenes (`Tools/Fallbacks/saturday_film.py:46-71,77-87,111-190,209-261`).
- **[declaration-proven]** Post-QC now detects frozen stretches, hard-fails missing required audio, retains the existing
  one-frame duration/frame/rate/resolution gates, validates CD4's schema-1 subset and atomically merges one Scene without
  discarding prior entries (`Saved/CodexConductor/MRQ/mrq_post.py:129-211,327-374,401-430`).
- **[declaration-proven]** Gary's ordered operation, stop/resume/revert procedure, output locations, inferred time/disk
  envelope, morning visual checklist and Cue Desk pickup are in
  `Docs/Conductor/SATURDAY_FILMING_RUNSHEET_2026-10-10.md:1-80`.

## Proof reached

- **[measured, offline]** `python Saved/CodexConductor/MRQ/test_mrq_fallbacks_offline.py` passed **31/31**. The missing
  `mrq_fallbacks_args.json` fixture was restored so the original positive/negative suite remains whole
  (`Saved/CodexConductor/MRQ/test_mrq_fallbacks_offline.py:445-450`).
- **[measured, offline]** `python Tools/Fallbacks/test_saturday_film_offline.py` passed **10/10: positive 5/5,
  negative 5/5**. It covers the requested missing-Scene refusal, QC-fail-no-promote, resume skip and CD4 schema controls,
  plus merge preservation and frozen-frame detection (`Tools/Fallbacks/test_saturday_film_offline.py:51-147`).
- **[measured, offline]** All four Python files compiled with `py_compile`; PowerShell parsed the unattended entry script;
  `git diff --check` reported no patch errors. These checks prove offline syntax and pure orchestration behavior only.
- **[measured, workspace]** No commit was created. The explicit-path `git add` was refused before staging because Git
  could not create `E:/PussStage/.git/worktrees/PussStage4/index.lock` (`Permission denied`). The P50 changes remain in
  this worktree for conductor review/commit; no repository metadata was changed.
- **[binary-proven]** No new binary claim was attempted: P50 changes Python, PowerShell and documentation, and the brief
  forbade Unreal/build execution.

## Not proved / acceptance boundary

- **[inferred]** The `-ExecutePythonScript` command-line DRY/BUILD should expose the same Unreal Python API used by the
  existing runner, but P50 did not launch Unreal, so process exit and marker capture remain unmeasured
  (`Saved/CodexConductor/MRQ/mrq_fallbacks_cmd.py:1-21`; `Tools/Fallbacks/saturday_night_film.ps1:53-70`).
- **[inferred]** Current Scene lengths, render time, disk use, sky/exposure, audio contents and frozen/black findings are
  deliberately unknown until Saturday DRY/render/QC. Runtime DRY supersedes the 7 Oct estimates
  (`Tools/Fallbacks/saturday_night_film.ps1:73-94`).
- **[inferred]** No MRQ config package, frame, MP4, WAV, QC artifact or `current.json` promotion was produced. No Cue Desk
  playback or rendered visual acceptance occurred. Gary's morning review remains required
  (`Docs/Conductor/SATURDAY_FILMING_RUNSHEET_2026-10-10.md:65-80`).

## Open questions for the conductor

1. **[inferred/open]** Confirm an unused Saturday version (the run sheet examples use `v01`; BUILD refuses collisions).
2. **[inferred/open]** Confirm enough free disk for both tiers after live DRY. The wrapper intentionally refuses rather
   than deleting earlier frames.
3. **[inferred/open]** Decide whether machine-QC-passing C should replace P automatically as written, or whether P should
   remain current until the morning eyeball. The brief says promote on QC pass; this implementation follows that wording.

Harness result: `SATFILM_HARNESS_OK|10/10|negative=5/5|positive=5/5`
