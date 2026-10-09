# P75 chandelier staging - conductor runbook

Offline delivery only. This worktree run did not open Unreal, MCP, PIE or
Blender. The live tool owns only chandelier body placement, 24 chain-link
actors per instance, grouped lights, and the Opening drive-by light keys.

P56 owns every flame actor. P52/P52B own every swing key. P75 writes neither.

## Production assets

- Body: `/Game/Scenes/Props/Chandelier/SM_Chandelier_Iron3`
- Material: `/Game/Scenes/Props/Chandelier/MI_Chandelier_Iron3`
- Links: `/Game/Scenes/Props/Chandelier/Chain/ChainLink_00..23`
- Pivots: `DerivedAssets/ChandelierBuild/Output/Iron3/chandelier_Iron3_chain.json`

The tool refuses the retired `/Game/Scenes/Chandelier/Iron3` root. Before any
mutation it requires exactly `Candle_01..44` plus `ChainAttach` on the body mesh;
UE's imported names must not retain the `SOCKET_` prefix.

## Offline order

1. `python Saved/CodexConductor/P75ChandelierStaging_20261009/test_chandelier_staging_offline.py`
2. `python Saved/CodexConductor/P75ChandelierStaging_20261009/make_timeline_previews.py`
3. Review `p75_offline_plan.json`, both PNGs, and the args.

The harness currently contains 8 positive and 12 negative controls. It covers
the level-global light cap, inclusion of the drive-by caster, part isolation,
the 24-link pivot contract, production/retired paths, hidden-shadow flags, and
the absence of flame/swing writes.

## Separate live stages

DRY may inspect both parts together (`"parts": ["opening", "p06"]`). APPLY and
REVERT deliberately require exactly one part, which prevents a combined record
or a cross-part rollback.

For each part:

1. Set `mode` to `DRY` and `parts` to the single part. Execute
   `chandelier_staging_request.json`. Require `P75_CHANDELIER_DRY_OK`,
   `flames=0`, `swing_keys=0`, `dirty=0+0`, and `mutated=0`.
2. Copy that part's `plan_sha256` into the same key under
   `reviewed_plan_sha256`.
3. Set `mode` / `confirm` to `APPLY` / `APPLY P75 CHANDELIER`. Execute again.
4. Require `P75_CHANDELIER_APPLY_OK`, the named part, clean read-back, and the
   part-specific active record:
   - `chandelier_staging_opening_ACTIVE.json`
   - `chandelier_staging_p06_ACTIVE.json`
5. Repeat for the other part only after reviewing the first result.

Opening saves only the level and Opening sequence. P06 saves only the level and
writes no sequence tracks. Each part takes its own
`Backups/PreP75Chandelier<Part>-<run>` snapshot.

To reverse one part, select only that part and use `REVERT` /
`REVERT P75 CHANDELIER`. The tool validates that part's actor/track read-back,
backs up its exact package scope, removes only its tagged actors and owned
Opening tracks, target-saves, then archives only that part's record.

## Global light guard

The cap is evaluated against every P75-owned light already in the level plus
the selected part's candidates. The tool refuses totals above 4 lights or 2
shadow casters. Defaults are:

- Opening drive-by: 1 light, 1 caster.
- Opening candle group: 2 lights, 1 caster.
- P06 candle group: 1 light, 0 casters, intensity 0 by default.
- Global total after both parts: 4 lights, 2 casters.

The P06 body label and all 24 P06 link labels are emitted in the plan and APPLY
record for P56/P52B. The same exposure is provided for the Opening instance.

## Proof boundary

The harness is measured offline. Asset existence on disk is measured, but UE
loading, socket read-back, chain placement, saves, sequence key read-back and
rendered appearance remain unproved until the conductor runs the stages in UE
5.8. Never use Save All.
