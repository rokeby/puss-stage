# P50 — Saturday-night filming of all Scenes: run sheet + ONE unattended script (Codex, offline build; Gary runs Sat night)

Read `_house_rules.md`. Offline only (no Unreal, no Blender while building). Gary 9 Oct: "plan the filming of all the
scenes for sat night … with the script for it". These are video FALLBACKS (stand-ins; will be re-recorded).

## Existing (extend, do not rewrite; dedupe rule)
- `Docs/Conductor/MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md` + tooling commit 50ce662 (`Saved/CodexConductor/MRQ/`: render via
  Master per Scene, P/C tiers, ffmpeg encode, QC/promote; harness 31/31; never run).
- Cue Desk video fallback contract (built 9 Oct, patch CD4 79f0eac): `Renders/Fallbacks/current.json` lists Scenes;
  "Use video" stays greyed until a Scene is listed — read the CD4 source for the exact schema and rate-following sync.
- Since 7 Oct: Scene lengths changed (Klara relengths S1/S2/S4; job 33 music lengths for Passages), S3 changes, GO→PASS.

## Build
1. **Refresh** the MRQ tooling to the CURRENT Master (read Scene section ranges live at run time, never hard-coded),
   all six Scenes (S1–S6), both tiers, and write/merge `Renders/Fallbacks/current.json` exactly per CD4's schema.
2. **ONE unattended entry script** `Tools/Fallbacks/saturday_night_film.ps1` (or .sh) Gary starts once: preflight (no
   other UE editor/Blender running, disk space per tier estimate, editor sky rule respected for renders = sky as the SHOW
   needs it), then each Scene in order, resumable (skip finished, checkpoint file), per-Scene log + QC (duration ±1 frame,
   black-frame / frozen-frame detection, audio present if the plan says so), promote to current.json only on QC pass,
   final summary JSON + a short human report. Stops a Scene on failure and continues to the next; never deletes renders.
3. **Run sheet** `Docs/Conductor/SATURDAY_FILMING_RUNSHEET_2026-10-10.md`: what to check before starting, expected
   total time per tier [inferred from plan estimates, marked], how to stop/resume, where outputs land, what Gary should
   eyeball in the morning, and how the Cue Desk picks them up.
4. Harness with +/- controls (missing Scene, QC fail does not promote, resume skips done, schema match with CD4).
Deliver in your worktree; the conductor reviews and commits.
