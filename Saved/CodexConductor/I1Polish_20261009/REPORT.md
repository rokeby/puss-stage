# Job 90 — Interaction 1 polish hand-off

## Scope and evidence

- **declaration-proven:** I1's authored sleight is Hangar → Mouth at 50 s, curtain release is 67 s, and the old P02 walk-in follows release (`Saved/CodexConductor/curtain_sleight.py:17-23`). The applied record declares a 35 mm matched lens and a route ending at frame 2183 (`Saved/CodexConductor/curtain_sleight_record_I1.json:4378`, `:9903`).
- **measured (offline):** the framing calculation for the recorded 23.76 × 13.365 mm filmback and 1880 × 1000 cm hang bounds produces **2852.44 cm** at 35 mm with the default 3% margin. The harness passes **15/15 positive + 9/9 negative = 24/24** (`i1_polish.py:102-120`, `test_i1_polish.py:45-164`).
- **inferred:** moving from the recorded 1200 cm matched seat to 2852.44 cm while preserving 35 mm should make the whole curtain only just fit. Gary must judge this in rendered PIE; the PNG is an analytical card, not rendered evidence.
- **UNCLEAR pending live DRY:** exact current I1 camera positions, all moving channels from f1675 to f2183, and the ranked Hangar/Mouth light/exposure/fog discontinuities. DRY searches and records those (`i1_polish.py:227-370`).

## Ownership and safety

The tool owns only `/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy`. It does not call playback-range, section-range, or marker timing mutators, protecting job 89's order/timing (`test_i1_polish.py:112-117`). APPLY creates `Backups/PreI1Polish-<run>`, requires an exact zero-dirty preflight, checks an exact one-package dirty census, saves only I1, reads keys/tracks back numerically, and writes a transaction record (`i1_polish.py:437-504`). REVERT takes a second backup and restores recorded keys/tracks.

UE 5.8 traps are handled: enums and suffixed channel names are normalised (`i1_polish.py:65-78`); GUIDs use job 39's stable converter; light visibility uses its `bHidden`/visible-bool implementation (`Saved/CodexConductor/I2Polish_20261009/i2_polish.py:840-906`). Non-linear terminal channels refuse APPLY rather than having their interpolation flattened.

## Conductor run order

1. Copy `i1_polish_args.example.json` to `i1_polish_args.json`; set a unique DRY run id and keep `f17_fix_steps` empty.
2. Run `i1_polish_request.json`. Require `I1_POLISH_DRY_OK`, `apply_ready=1`, `census=0/0`; inspect the report's exact focal/positions, F17 ranking/proposals, F18 inventory/selection, and stills plan.
3. If Gary chooses an F17 proposal, express only that proposal in `f17_fix_steps`; rerun DRY and archive its JSON. Otherwise leave lighting as diagnosis-only and do not claim part 2 fixed.
4. Change only mode/run id/confirm to `APPLY` / `APPLY I1POLISH`; run. Require `I1_POLISH_APPLY_OK`, the named backup/record, one-package save, numerical read-back, and dirty=0.
5. Capture rendered stills at f274, f1249/f1250, f1674/f1675, f1701, and f2182. Check the curtain fit, cut continuity, and absence of the lowering. This is visual acceptance.
6. To undo, set `REVERT` / `REVERT I1POLISH`; require `I1_POLISH_REVERT_OK` and dirty=0.
