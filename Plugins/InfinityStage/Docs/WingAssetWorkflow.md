# Infinity Stage Wing Asset Workflow

## Canonical asset contract

Every scenic wing mesh used by Infinity Stage should be authored as a fixed, editor-visible stage panel:

- **X** is panel depth, normally 5 cm.
- **Y** is horizontal span across the passage.
- **Z** is height, with the lowest point at Z = 0.
- The pivot is centred in X/Y and bottom-centred in Z.
- A Left architectural wing has its taller outside edge at negative local Y.
- A Right architectural wing has its taller outside edge at positive local Y.
- Neutral objects and buildings are classified as `SideNeutral`; they do not receive a left/right mirror merely because of their silhouette and may be used safely on either side.
- Curtain assets are classified as `Excluded`. They are scenic transitions, not Passage wings, and are never chosen by automatic Passage setup or repair.
- Top assets are hanging scenic borders. They are not floor-like horizontal ceiling planes.

The persistent source of classification and audit state is:

`/Game/InfinityStage/WingLibrary/DA_InfinityStageWingLibrary`

## Auditing and repairing source meshes

Open **Window → Infinity Stage Wing Assets**. The resizable window has a searchable list on the left and the selected record's details on the right. Use the single **Actions** menu to avoid a strip of one-purpose buttons.

1. Choose **Scan / Refresh**. The audit searches the project wing folders and reads all available `DerivedAssets/**/wing_pipeline_report*.json` files.
2. Review Role, bounds, thickness axis, taller edge and the proposed correction.
3. Edit an incorrect Role in the detail panel before applying anything.
4. Choose **Apply All Safe Corrections**. Only deterministic, plausible panel corrections are applied.
5. Use **Revert Selected** if an applied correction needs to be undone.

Applied changes rewrite the Static Mesh source geometry, rebuild the mesh, and save the asset. Before the first rewrite, the original package is copied to `Saved/InfinityStage/WingAssets/OriginalPackages` without overwriting an earlier backup. The exact transform is also retained in the Wing Library so the normal **Revert Selected** operation is reversible. The machine-readable report is saved at:

`Saved/InfinityStage/WingAssets/wing_asset_audit.json`

Do not apply source-mesh corrections while another Unreal Editor instance has the same project open. Save All and close it first; otherwise an older in-memory package could later overwrite the repaired asset.

## Assigning and editing wings in the Cue Desk

The fixture builder only chooses assets approved by the Wing Library for the required slot:

- Left slots: `LeftArchitectural` or `SideNeutral`
- Right slots: `RightArchitectural` or `SideNeutral`
- Top slots: `Top`
- `GroundOrProp`, `Unknown`, and `Excluded` are never silently substituted into a side/top slot

For manual placement:

1. Select one Wing Pair row in the Cue Desk.
2. Enable **Actions → Follow Selection in Level Viewport** to select and frame its visible instances.
3. Choose **Actions → Edit Selected Wing in Level Viewport**, then **Whole Pair**, **Left**, **Right**, or **Top**.
4. Move, rotate, or scale the temporary edit proxy with Unreal's normal viewport gizmo.
5. Choose **Finish Viewport Edit** to write the transform to the cue, or **Cancel Viewport Edit** to restore it.

The proxy is transient and editor-only. The cue's occurrence or panel-local transform remains authoritative; raw instanced-mesh transforms are never treated as authored data.

Generated Passages begin with 30 render groups but reserve a 64-component authoring budget so replacing individual meshes can introduce new groups. Materialization validates the complete replacement before removing existing instances. If a future edit exceeds the configured budget or has an invalid route, the last valid visible Passage remains in the editor and the log reports the rejected edit.

For mass spacing edits, multi-select cue rows and use the Cue Desk's bulk edit controls. Source-mesh repair and cue placement are intentionally separate: repair a bad pivot/orientation once in the Wing Library, then make artistic per-occurrence changes in the Cue Desk.

## Rebuilding and validating

After changing source geometry:

1. Scan again. A second scan should propose no further correction for repaired assets.
2. Rebuild the current Infinity Stage fixture so its fixed, editor-visible instances use the corrected geometry and role-aware assignment.
3. Open the fixture level and inspect representative Left, Right and Top rows.
4. Verify Cue Desk selection, frame-selection and viewport editing.
5. Run the Infinity Stage automation suite and inspect the newest Unreal log for crashes and HTTP 403 failures.

Older reference levels are not migration targets. The audit changes reusable mesh assets, while only the current Infinity Stage fixture is rebuilt.
