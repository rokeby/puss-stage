# P89 curtain before shadow

Offline-authored only. This bundle has not run Unreal and does not claim a
rendered result. It audits I1/I3/I4/I5 and repairs only interactions where the
existing hangar curtain is not continuously spawned, Geometry-Cache-present,
hung, and visible for the requested margin before the existing hangar shadow
spot first becomes non-zero.

Default margin: **0.5 s** (Gary-owned argument). The I2 order fix is the pattern:
the curtain is held in its existing evaluated hung pose from frame 0. Existing
unspawn, fall/release, light plateau/fade-out, bindings, GUIDs, channel defaults,
GC asset/offsets, camera cuts, markers, and every unowned track are preserved.
The tool normalises UE 5.8 enum wrappers and suffixed channel names and converts
each FGuid once.

## Ordered run

1. Stop PIE/SIE, close Sequencer, load the vertical-slice world, and require zero
   dirty content/maps and no `ZZ_` actors.
2. Set `p89_args.json` to a unique id with `DRY`, `ALL`, `DRY P89`; execute
   `p89_request.json`. Require `P89_CURTAIN_BEFORE_SHADOW_DRY_OK`. Review the
   report's before/after table for I1/I3/I4/I5.
3. Apply **I1 first**. Keep the exact DRY parameters, set `interaction` to `1`,
   `mode` to `APPLY`, confirmation to `APPLY P89 I1`, and a fresh run id. Require
   `P89_CURTAIN_BEFORE_SHADOW_APPLY_OK` and `changed=1` (or the explicit
   `already_compliant` no-save result).
4. Re-run `DRY ALL`. Then, only for rows with `needs_change=true`, apply I3, I4,
   and I5 one at a time in that order with confirmations `APPLY P89 I<n>`.
5. Re-run `DRY ALL`; require every row `needs_change=false`, zero dirty packages,
   then perform rendered review. Automation cannot prove the shadow is visually
   on opaque cloth.

Each changing APPLY creates `Backups/PreP89CurtainBeforeShadow-I<n>-<run>`, an
exclusive per-interaction record before mutation, saves only that interaction
sequence, reloads it, checks evaluated order, and requires every unowned track to
remain identical.

## Revert

For one interaction, set `mode` to `REVERT`, confirmation to `REVERT P89 I<n>`,
and a fresh run id. REVERT drift-checks the saved after-state, takes a second
backup, restores the exact recorded originals, saves only the named sequence,
and compares the complete sequence snapshot.

## Offline harness

```powershell
python Saved\CodexConductor\P89CurtainBeforeShadow_20261009\run_offline_harness.py
```

The harness contains both required controls: curtain-after-spot is refused;
curtain-before-spot is accepted and compliant interactions remain untouched.
