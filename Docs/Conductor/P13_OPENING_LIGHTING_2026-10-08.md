# P13 opening lighting proposal — 8 October 2026

**Status: built and tested offline; NOTHING APPLIED.** The tool, runner, args,
request and offline harness are in `Saved/CodexConductor/`. The harness passes
**62/62** **[measured: `Saved/CodexConductor/test_opening_lighting_p13_offline.py:20-133`]**.
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
`Saved/CodexConductor/opening_lighting_p13.py:768-777`]**.

The lamps are not new free-floating level lights. They are Show attachments on
P01's first WingPair cue, so the Show remains the authoring authority
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
- P11 had not landed under `DerivedAssets/MusicAnalysis/` when this proposal was
  built **[measured: `Test-Path DerivedAssets/MusicAnalysis` returned false, 8
  Oct; exact searched path named here]**. The preview therefore uses
  `Saved/InfinityStage/MusicAnalysis/OpeningSketch2/P01_Opening_Tuning_sketch2.analysis.json`.
  Its major-change proposals at 36.1767 / 43.8393 / 59.5360 s are defaults only,
  exposed as `flurry_times_s` **[declaration-proven:
  `Saved/InfinityStage/MusicAnalysis/OpeningSketch2/P01_Opening_Tuning_sketch2.analysis.json:2749-2761`;
  `Saved/CodexConductor/opening_lighting_p13_args.json:6`]**.

## Default proposal

| Element | Default | Evidence tier |
|---|---:|---|
| Moving spots | 4 × 800 cd, 12° outer / 7° inner, falloff exponent 12 | inferred look |
| Moving-spot colour | 2950 K, linear RGB 1.0 / 0.80 / 0.58 | inferred look |
| Corner accents | 2 × 1500 cd, 10° / 5°, 0.08 s attack, 0.55 s release | inferred look |
| Flurry 1 | 36.1767 s / frame 904 | declaration-proven default |
| Flurry 2 | 43.8393 s / frame 1096 | declaration-proven default |
| Flurry 3 | 59.5360 s / frame 1488 | declaration-proven default |
| Curtain FALL begins | flurry 2 / frame 1096 | inferred interpretation |
| Moving spots come on | flurry 2 / frame 1096 | inferred interpretation |
| Perspective adjustment | flurry 3; 15→25 mm over 2.4 s | inferred interpretation |

Every delivered default, including intensity, cone/source angles, colour,
position and timing, is exposed in the args **[declaration-proven:
`Saved/CodexConductor/opening_lighting_p13_args.json:6-67`; measured control:
`Saved/CodexConductor/test_opening_lighting_p13_offline.py:127`]**.

The moving spots hold at 55% after converging, lighting only the mouth/first part
of the machine, then fade to zero over the final 1.25 s **[inferred: this is the
proposal's reading of “dark stage with only the first parts lit”]**. Corner lamps
return to zero after every flurry **[declaration-proven:
`Saved/CodexConductor/opening_lighting_p13.py:261-292`]**.

Gary's list says both curtain and lights use the “second” flurry, while the prose
says the curtain falls in the “final” flurry. The default honours the numbered
list (`curtain_flurry_index=2`) and makes the index an arg exactly as requested.
**[declaration-proven: `Docs/Conductor/codex_briefs/p13_opening_lighting.md:2-3`;
inferred: choice between conflicting prose and list.]**

## Scope and safety

APPLY writes exactly three packages:

1. `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show` — six new Light attachments
   on P01's first cue;
2. the Opening sequence resolved live from the Show — attachment bindings,
   intensity/rotation tracks, named P13 markers, curtain section ranges and the
   focal track;
3. `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` — only the
   rematerialized P01 attachment actors.

Before mutation it requires the correct world, no PIE/SIE, no open Sequencer,
zero dirty packages, no `ZZ_` actors, the exact confirmation string, and a prior
matching DRY plan. It then creates `Backups/PreP13OpeningLighting-<run>/` containing
hash-verified copies of all three packages and writes the revert record before
changing them **[declaration-proven: tool gates and transaction order]**.
The gates and transaction order are declaration-proven at
`Saved/CodexConductor/opening_lighting_p13.py:346-365,587-594,802-822`.

APPLY saves only those named packages, reloads them, reads back attachment GUIDs,
curtain sections, focal keys, markers and bindings, requires zero dirty packages,
then prints `P13_OPENING_LIGHTING_APPLY_OK` **[declaration-proven; not measured
until the conductor runs it; `Saved/CodexConductor/opening_lighting_p13.py:734-785,802-823`]**.
REVERT drift-checks against APPLY, takes a second
backup, removes only its own bindings/attachments, restores prior spawn, curtain,
focal and marker state, saves/read-backs, then prints
`P13_OPENING_LIGHTING_REVERT_OK` **[declaration-proven; not run;
`Saved/CodexConductor/opening_lighting_p13.py:753-765,828-860`]**.

## Preview files

- `DerivedAssets/OpeningLighting/P13_opening_rig_top_front.png`
- `DerivedAssets/OpeningLighting/P13_opening_cue_timeline.png`

These are diagrams, not rendered acceptance **[measured: PNGs generated and
visually inspected offline; inferred: their look in Unreal]**.

## Ordered runbook for the conductor

1. Edit `opening_lighting_p13_args.json`; specifically confirm the curtain
   flurry index and the focal-only interpretation.
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

Result: `P13_OPENING_LIGHTING_TESTS|pass=62|fail=0` **[measured, offline;
success output is emitted at `Saved/CodexConductor/test_opening_lighting_p13_offline.py:133`]**.
Positive controls cover the rig, timing, args, authority, diagrams and exact
dark-at-end behavior. Negative controls cover dirty state, wrong world, PIE,
open Sequencer, existing records, bad confirmations, invalid flurries, cone and
falloff errors, and unsupported camera-walk interpretation.

## Open questions for Gary

1. Curtain on flurry **2** (the numbered list/default) or flurry **3** (the prose's
   “final flurry”)?
2. Does “perspective adjustment” mean the proposed 15→25 mm focal pull, or the
   camera translation/walk-in as well? The latter is intentionally untouched.
3. Approve or tune the default intensity, warmth, cone and pulse values after the
   first rendered capture. Offline geometry cannot approve the look.
