# P13 opening lighting proposal — 8 October 2026

**Status: pass 2 built and tested offline; NOTHING APPLIED.** The tool, runner,
args, request and offline harness are in `Saved/CodexConductor/`. The pass-2
harness passes **85/85** **[measured:
`Saved/CodexConductor/test_opening_lighting_p13_offline.py:20-166`]**.
No Unreal Editor, MCP, PIE, build or Blender process was used **[measured: this
offline worktree run]**.

Evidence labels follow `AGENTS.md`: **[declaration-proven]** is source/header or
config that can be read; **[measured]** is an intervention whose result was read
back; **[inferred]** is a proposal awaiting rendered acceptance.

## Outcome

Replace the current broad Opening rig with four tight, soft-penumbra spots whose
aims travel from separate edge pools into the centre, plus upper-left and
upper-right accents that pulse on every flurry **[inferred: creative proposal;
Gary owns every value in the args]**. The old `Opening Rig - *` bindings are
disabled, not deleted **[declaration-proven: tool design,
`Saved/CodexConductor/opening_lighting_p13.py:1118-1127`]**.

Pass 2 adds seven warm, tight PAR beams in a row at x -135 cm, aimed upward at
the paper facade's x -60 cm valance plane, plus an exact-label P01 subset that
rises to 35% of its live P01 intensity on flurry 2 and reaches the full P01
level over the final 0.8 s **[inferred: the placement,
warmth, cone, count and 35% level are look proposals; declaration-proven args:
`Saved/CodexConductor/opening_lighting_p13_args.json:70-99`]**. The default subset is
the first-bay practical `P01 SCORE B01 VOID PRACTICAL_DEAD`; DRY refuses rather
than silently substituting another light if that exact row is absent, disabled,
duplicated or non-positive **[declaration-proven:
`Saved/CodexConductor/opening_lighting_p13.py:691-723`]**.

The thirteen new lamps are not free-floating level lights. They are Show
attachments on P01's first WingPair cue, so the Show remains the authoring authority
**[declaration-proven: attachment storage and identity,
`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:434-498`]**.
The Opening sequence addresses them through the stable attachment-tag custom
binding, which was explicitly built to survive materialization and PIE
duplication **[declaration-proven,
`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageAttachmentBinding.h:12-66`]**.

## What exists now

- The saved Opening plan records a 2,409-frame, 25 fps Opening (96.36 s), with
  the current curtain release at frame 1,935 **[measured: prior APPLY/read-back,
  `Saved/CodexConductor/opening_sequence_record.json:12122-12131`]**.
- The current plan's active level rig is FOH L/R plus `Wash C`; the wash is 30°
  outer / 27° inner at 900 cd **[declaration-proven,
  `Saved/CodexConductor/opening_timing.json:109-194`]**.
- The separately applied P01 floor-practicals record reports the literal bay-1
  practical disabled at 0 lm **[measured saved-record read-back, not a current
  Unreal read: `E:/PussStage/Saved/CodexConductor/P01FloorPracticals_20261008/p01_floor_record.json:354058-354159`]**.
  Therefore the brief-mandated default is expected to make DRY refuse until Gary
  chooses a live exact-label subset **[inferred from that saved record;
  declaration-proven gate: `Saved/CodexConductor/opening_lighting_p13.py:691-723`]**.
- `DerivedAssets/MusicAnalysis/Opening.json` is absent from this worktree, so the
  offline preview uses
  `Saved/InfinityStage/MusicAnalysis/OpeningSketch2/P01_Opening_Tuning_sketch2.analysis.json`.
  This is measured file-presence/fallback behavior, not evidence for the cue
  times **[measured: `Saved/CodexConductor/opening_lighting_p13.py:501-523`]**.
  Pass 2 uses the landed P11/Gary order in the args: 37.44 / 57.36 / 70.44 s
  **[declaration-proven:
  `Docs/Conductor/FINAL_JOBS_BEFORE_REHEARSAL_2026-10-08.md:76-83`]**.

## Default proposal

| Element | Default | Evidence tier |
|---|---:|---|
| Moving spots | 4 × 800 cd, 12° outer / 7° inner, falloff exponent 12 | inferred look |
| Moving-spot colour | 2950 K, linear RGB 1.0 / 0.80 / 0.58 | inferred look |
| Corner accents | 2 × 1500 cd, 10° / 5°, 0.08 s attack, 0.55 s release | inferred look |
| Facade PAR row | 7 × 2600 cd, 9° / 4°, 2700 K, x -135, y -850..850, z 45 cm | inferred look |
| P01 opening subset | exact label list; 35% partial in 0.75 s; full P01 level over final 0.8 s | inferred look; declaration-proven selection discipline |
| Flurry 1 | 37.44 s / frame 936; curtain falls | declaration-proven default |
| Flurry 2 | 57.36 s / frame 1434; all opening lights + facade PARs + P01 subset | declaration-proven timing; inferred look |
| Flurry 3 | 70.44 s / frame 1761; focal move | declaration-proven timing; inferred focal-only interpretation |

Every delivered default, including intensity, cone/source angles, colour,
position and timing, is exposed in the args **[declaration-proven:
`Saved/CodexConductor/opening_lighting_p13_args.json:6-109`; measured control:
`Saved/CodexConductor/test_opening_lighting_p13_offline.py:151-163`]**.

The moving spots hold at 55% after converging, lighting only the mouth/first part
of the machine, then fade to zero over the final 1.25 s **[inferred: this is the
proposal's reading of “dark stage with only the first parts lit”]**. Corner lamps
return to zero after every flurry. The facade PARs also fade to zero at the
Opening end; the selected P01 light rises from the 35% partial state to its full
authored P01 intensity over the final 0.8 s **[declaration-proven:
`Saved/CodexConductor/opening_lighting_p13.py:286-325,389-421`; inferred: visual continuity]**.

Gary clarified the order as 1 curtain / 2 lights / 3 move-in, and the delivered
defaults now match it **[declaration-proven:
`Docs/Conductor/FINAL_JOBS_BEFORE_REHEARSAL_2026-10-08.md:76-83`;
`Saved/CodexConductor/opening_lighting_p13_args.json:6-12`]**.

## Scope and safety

APPLY writes exactly three packages:

1. `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show` — thirteen new Light
   attachments on P01's first cue (four sweeps, two corner accents, seven PARs);
2. the Opening sequence resolved live from the Show — attachment bindings,
   intensity/rotation tracks, the existing P01 subset's intensity track, named
   P13 markers, curtain section ranges and the focal track;
3. `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` — only the
   rematerialized P01 attachment actors.

Before mutation it requires the correct world, no PIE/SIE, no open Sequencer,
zero dirty packages, no `ZZ_` actors, the exact confirmation string, and a prior
matching DRY plan. It then creates `Backups/PreP13OpeningLighting-<run>/` containing
hash-verified copies of all three packages and writes the revert record before
changing them **[declaration-proven: tool gates and transaction order]**.
The gates and transaction order are declaration-proven at
`Saved/CodexConductor/opening_lighting_p13.py:479-498,654-687,778-785,1152-1178`.

APPLY saves only those named packages, reloads them, reads back attachment GUIDs,
curtain sections, focal keys, markers, binding ownership and every P13 intensity/
rotation channel numerically, requires zero dirty packages,
then prints `P13_OPENING_LIGHTING_APPLY_OK` **[declaration-proven; not measured
until the conductor runs it; `Saved/CodexConductor/opening_lighting_p13.py:1010-1100,1152-1178`]**.
REVERT drift-checks against APPLY, takes a second
backup, removes only its own bindings/attachments, restores prior spawn, curtain,
focal and marker state, saves/read-backs, then prints
`P13_OPENING_LIGHTING_REVERT_OK` **[declaration-proven; not run;
`Saved/CodexConductor/opening_lighting_p13.py:1038-1080,1102-1115,1181-1210`]**.

## Preview files

- `DerivedAssets/OpeningLighting/P13_opening_rig_top_front.png`
- `DerivedAssets/OpeningLighting/P13_opening_cue_timeline.png`

These are diagrams, not rendered acceptance **[measured: PNGs generated and
visually inspected offline; inferred: their look in Unreal]**.

## Ordered runbook for the conductor

1. Edit `opening_lighting_p13_args.json`; specifically confirm the facade PAR
   look/placement, exact P01 label subset and the focal-only interpretation.
2. Set `mode` / `confirm` to `DRY` / `DRY P13`. Run
   `opening_lighting_p13_request.json` through
   `MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset.ExecuteProjectPythonFile`.
3. Require `P13_OPENING_LIGHTING_DRY_OK`, `apply_ready=true`, zero dirty packages,
   and review both PNGs with Gary.
4. Set `mode` / `confirm` to `APPLY` / `APPLY P13`; rerun the same request.
5. Require the APPLY marker, saved read-back block and zero dirty packages. Then
   do rendered Editor/PIE acceptance separately; transport success is not visual
   acceptance.
6. To undo, set `mode` / `confirm` to `REVERT` / `REVERT P13` and rerun. Do not
   hand-delete the record or bindings.

## Harness

`python Saved/CodexConductor/test_opening_lighting_p13_offline.py`

Result: `P13_OPENING_LIGHTING_TESTS|pass=85|fail=0` **[measured, offline;
success output is emitted by
`Saved/CodexConductor/test_opening_lighting_p13_offline.py:166`]**.
Positive controls cover the rig, timing, args, authority, diagrams and exact
dark-at-end behavior, facade geometry, exact P01 selection and float32 tolerance.
Negative controls cover dirty state, wrong world, PIE, open Sequencer, existing
records, bad confirmations, invalid flurries, cone/falloff errors, malformed PAR
rows, widened/missing P01 selections, zero live P01 intensity and unsupported
camera-walk interpretation **[measured: same harness run]**.

## Open questions for Gary

1. Approve or tune the facade row's count, x/y/z, aim height, warmth, cone and
   2600 cd intensity after the first rendered capture **[inferred look]**.
2. Confirm the exact P01 subset after live DRY. The default names the first-bay
   practical only; the latest separate saved record says it is disabled/0 lm,
   while current Unreal state remains unmeasured **[measured saved record:
   `E:/PussStage/Saved/CodexConductor/P01FloorPracticals_20261008/p01_floor_record.json:354058-354159`;
   declaration-proven refusal: `Saved/CodexConductor/opening_lighting_p13.py:691-723`]**.
3. Does “perspective adjustment” mean the proposed 15→25 mm focal pull, or the
   camera translation/walk-in as well? The latter is intentionally untouched
**[declaration-proven: `Saved/CodexConductor/opening_lighting_p13_args.json:100-103`]**.
4. Approve or tune the remaining intensity, warmth, cone and pulse values after the
   first rendered capture **[inferred: offline geometry cannot approve the look]**.
