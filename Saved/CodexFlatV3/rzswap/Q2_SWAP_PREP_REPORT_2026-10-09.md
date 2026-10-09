# Q2 swap preparation — P03 V2, P01/P04 realism, P04 Top valances

Offline implementation only. No Unreal, MCP, PIE or Blender was used. Nothing was applied to the Show.

## What is proved

- **Measured (saved-record reconstruction):** the supplied audit ranks exactly seven low-density P03 V2 sides: Wing
  001 L/R, 002 L/R, 003 L/R and 004 L. The ranking records cue label, side and expected live mesh, so it can be used as
  a stale-data gate (`Saved/CodexFlatV3/p02p03_audit/AUDIT.md:13-14`,
  `Saved/CodexFlatV3/p02p03_audit/AUDIT.md:25-31`;
  `Saved/CodexFlatV3/p02p03_audit/audit.json:1`).
- **Declaration-proven:** P03 does not carry P02's matched-pair rule. The rule is explicitly scoped to P02; ordinary
  assignment remains side-based, with maximum two uses and no adjacent same-side repeat
  (`Saved/CodexFlatV3/rzswap/rzswap_core.py:51-56`, `Saved/CodexFlatV3/rzswap/rzswap_core.py:409-425`).
- **Declaration-proven:** `--targets-from` resolves every audit row to the fresh DRY's cue GUID and requires the audit's
  mesh to still be standing. The plan refuses unless its swaps equal the target set exactly
  (`Saved/CodexFlatV3/rzswap/make_swap_plan.py:97-120`, `Saved/CodexFlatV3/rzswap/rzswap_core.py:458-489`,
  `Saved/CodexFlatV3/rzswap/rzswap_core.py:607-613`).
  The exact user-directed set may waive only the broad `END_ROW` heuristic; pins, special mechanisms, effects,
  protect records, authored-transform and measurement guards remain hard
  (`Saved/CodexFlatV3/rzswap/rzswap_core.py:476-489`).
- **Declaration-proven:** scored plan support now includes P01 and P04
  (`Saved/CodexFlatV3/rzswap/rzswap_core.py:71-79`).
- **Declaration-proven:** P04's gate computes the proposed longitudinal interval from the current materialized interval
  plus candidate front/back growth, then tests every materialized L/R/T panel and measured PROP bound on the previous
  and next fresh-DRY rows. Front growth over 6 cm or any interval overlap refuses the plan
  (`Saved/CodexFlatV3/rzswap/rzswap_core.py:340-393`). Fresh DRY records panel faces plus panel and PROP route intervals
  (`Saved/CodexFlatV3/rzswap/rzswap.py:280-325`, `Saved/CodexFlatV3/rzswap/rzswap.py:380-408`).
- **Declaration-proven:** the Show owns a real `Top` panel when `bHasTop` is true
  (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:720-738`). RZSWAP now measures/writes side
  `T`; a replacement uses identity rotation/scale, centres its width on the existing Top centre Y, and aligns its upper
  edge to the existing Top upper Z (`Saved/CodexFlatV3/rzswap/rzswap_core.py:97-103`,
  `Saved/CodexFlatV3/rzswap/rzswap_core.py:321-336`, `Saved/CodexFlatV3/rzswap/rzswap_core.py:615-617`). APPLY/REVERT
  read-back checks Top centre and upper edge as well as L/R inner edges
  (`Saved/CodexFlatV3/rzswap/rzswap_core.py:948-977`).
- **Measured (offline harness):** 131 positive and negative controls pass, including exact seven targets, stale target,
  retained MASTER_PIN, P04 5 cm success, >6 cm failure, adjacent-PROP collision failure, Top placement, missing Top
  anchor, and Top read-back drift (`Saved/CodexFlatV3/rzswap/test_rzswap_offline_report.json:1`).

## What remains unproved

- **Inferred pending live measurement:** P01/P04 assignments, the exact P04 clearances, and valance placements cannot be
  claimed until the conductor runs a fresh DRY and reviews the generated sheets. Old DRYs are deliberately not accepted.
- **Inferred pending rendered review:** a passing plan/read-back does not establish that any realism wing or valance
  looks right in the passage.

## Conductor run order

Use `swap_prep_args_templates.json`. For each item: copy its `dry_args` to `rzswap_args.json`; run the guarded DRY;
run its `offline_plan`; require `gates_ok=true`; review the PNG sheet; only then create the hash-bound APPLY args with
Gary's exact approval words. APPLY already takes `Backups/PreRZSwap<P>-<stamp>`, writes originals + ACTIVE record, saves
only Show and level, reads back, requires a clean census, and emits `FLATV3_RZSWAP_APPLY_OK`. REVERT remains field-scoped.
