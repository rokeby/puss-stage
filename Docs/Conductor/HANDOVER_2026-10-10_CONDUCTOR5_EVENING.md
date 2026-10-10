# Handover: Conductor 5, evening of 10 Oct 2026

Written at Gary's request because Claude usage is nearly out. Start here, then read
`OVERNIGHT_QUEUE_2026-10-10.md` (the single tracker), `APPLY_PASS_REPORT_2026-10-10.md`
(every live pass, with evidence) and `GARY_PIE_NOTES_2026-10-09_evening.md` (Gary's
own words, with targets confirmed).

## Running at hand-over

- **Codex job 184 (live, `--unreal`)** was still running:
  - the P06 chandelier candle lights (job 182 tool);
  - the P06 sun disc APPLY (job 178B, bounded-axis rule);
  - the S1 lights-out check (frame 3880 still looked fully lit to the conductor).

  When it ends:
  1. Read the "Job 184" section of the apply-pass report.
  2. Look at the `184_*` stills in `Saved/CodexConductor/ApplyPass_20261010/stills/`.
  3. Commit the changed tool files by explicit path, then push.
  4. Check the editor is open, clean and not in PIE: run the census, and confirm `pie=false`.

## Applied and saved today (live, read back)

| Item | Commit / job | Visual verdict |
|---|---|---|
| I2/I3 back-wall shadows | 177 (`b1ccf606`) | PASS. Gary likes the I2 still (boy in the lit window). |
| P52 chandelier swing | 177 | Applied. The body was too dark to judge. |
| P56 44 candle flames + activators | 176/177 | Applied. The candles have NEVER been seen yet: the gold cluster in the P06 stills is a misplaced Niagara SWARM, not the candles (Gary). |
| 3D stage-front uplights (8) | 181 (`4874cc1b`) | The outer architecture reads; Gary: "looks good". Textures are subtle in close-ups (183). |
| Shadow reach, middle point (P01/02/03/05/06; P04 skipped, no tags) | 183 (`24e5e7c9`) | Perf was only spot-sampled. Watch P01/P03/P06 frame time. |
| P02 haze/beam trim (rig kept at low intensity) | 183 | PARTIAL: fewer beams, a lot of haze remains. Gary's call whether to go lower. |
| S1 ending: camera to the corner-wing fire (transform only), fire 0.10 scale / 150 lm, LIGHTS_OUT, SHRINK (S1 ends at 3900), VALIDATE | 177/183 | QUALIFIED: 183_13 at frame 3880 still looks lit. Job 184 is checking. |
| S3 hair (long, dark/grey) + blue-grey fires | 175 | Applied. The hair is hidden by the shrouds; the fire colour has not been seen in any still. Gary: keep the hair (it is for covering faces). |
| S3 song surtitles, 8 lines, S3-relative 2:09–3:07 | `Content/InfinityStage/CueSheet/Puss_Surtitles.csv` | Not yet seen on screen. Add them to the Cue Book too, or a pull may not carry them. |
| P06 parcan body hidden (ISM instance 8 scaled to 0) | 173 | Holds until any rebuild of Structure 06. Job 180's flag makes it permanent after the build. |

Earlier on 10 Oct: S4 blackout, pearl fade, S3 arrival and garments, P04 smoke props, P05 deer curtain, P05 42 s, P06 Walking6 125 s, P02 floor = P01 copy, the fringe, the opening (job 87), chandelier staging, the shadow-cat build. See the morning report.

## Ready but not applied

- **Job 180, parcans auto-rebuild when Gary moves a light** (`2ccc7ca4`). The C++ is HELD in `Scripts/patches/job180_fixture_autorebuild.patch`; Python passes 11/11.
  - It **needs an editor-closed build window** (any UE editor blocks the build). The steps are in `JOB180_REPORT_2026-10-10.md`.
  - After the build, run the P06 no-parcan APPLY: `Saved/CodexStructure/job180_suppress_p06_fixture_body*`.
  - The menu item *Puss > Rebuild Passage Fixtures* does nothing until the build.
- If job 184 fails on them: job 182 (chandelier candle lights) and job 178B (sun disc).

## Waiting on Gary

1. **P02 haze:** keep the partial trim as a tuning start, or trim further?
2. **The build window** for job 180.
3. **Ending 101:** it needs Gary in the studio.
4. **TdrDelay** (a Windows GPU timeout). Gary sets it himself in an Administrator PowerShell; the command is in `MORNING_REPORT_2026-10-10.md`. Until then, use the safe launcher `PussStage_ScriptedSafe.ps1`.

## Parked by Gary (note only, do not build)

- A doorway-based transition in the back wall (as an alternative to the curtain).
- Fix the swarm placement (the gold cluster in P06).
- Garment stains, girders everywhere (job 116), swarm (job 100), the S6 old-lady cuts, gobo content.
- The 4 pre-existing failing automation tests.

## Hand-offs done

- **P05 cloud wings for Rob:** `G:\Shared drives\GZZ Studio Drive\Projects\2026. SHS 3 Evenings\P05_CloudWings_Rob_20261010.zip` (440 MB, UE 5.8 uassets plus their shared materials, with a README). An unzipped copy is in `Saved/Handover/`. Not test-imported in a clean project.

## How the conductor works (and what to keep)

- **Codex executes everything:**
  - offline: `Scripts/codex.sh --worktree`;
  - live: `CODEX_EFFORT=high bash Scripts/codex.sh --unreal`, with the rules in `codex_briefs/p135_live_pass3.md` and the self-recovery in `p165_self_recovering_slot.md`.
- **Importing a worktree:**
  1. `git -C <wt> diff -- . ':!*__pycache__*'`.
  2. If you get "does not match index", commit the main tree's live edits to those files first.
  3. `git apply --3way`.
  4. Copy the untracked files.
  5. Rerun the harnesses.
  6. `git add -f` by explicit path; never `-a`, never stash.
- **Stills are the acceptance evidence.** Codex's verdicts were wrong twice today:
  - it called the swarm cluster "lit candles";
  - it called S1 "darkening" when frame 3880 was still lit.

  Look at every still yourself.
- **Before a live run, check each tool's UE 5.8 API calls** against proven working tools. Most capped attempts today were API trivia: `DateTime.now`, `get_root_component`, `is_child_of`, focal-length tracks.
- **Gary's location words are exact** (P0n vs S0n). Record each instruction in the notes with his words.
