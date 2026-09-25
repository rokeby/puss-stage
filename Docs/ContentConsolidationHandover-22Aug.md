# Content Consolidation + PC Migration — Handover (22 Aug 2026)

## What this was

Content root had ~20 third-party packs sitting alongside your own folders. An
earlier attempt to drag them into `Content/EnvironmentPacks` in the Content
Browser was slow and crashed partway, leaving several packs half-moved and some
references broken.

This session finished that consolidation, repaired the reference damage, and
staged the project for PC migration. **Nothing was deleted.** Every pack you
imported but haven't used yet is intact, just filed.

## Final layout

| Location | Contents |
|---|---|
| `Content/EnvironmentPacks/` | all environment packs (LSM, Megascans_2K/4K, MWTropicalRainforest, OceanFloor, SpringLandscape, PCGForestBlueprint, ProceduralNtr_vol2, PN_FoliageCollection + the 13 already there) |
| `Content/CharacterPacks/` | AnimX (Cats), Animalia (HoneyBee) |
| `Content/` root | your own work only: Scenes, InfinityStage, Levels, Blueprints, Stage, Wings, Materials, SkeletalMeshes, KK_S2_Shrine, Fab, StarterContent + redirector stubs |

**1,895 assets relocated, zero move failures.**

## How the move was done (and why it matters if you repeat it)

Not the Content Browser. A headless `UnrealEditor-Cmd -run=pythonscript` calling
`AssetTools.rename_assets()`, which rewrites referencing packages as part of the
rename — that's what makes it a move-and-relink instead of move-then-repair.

Three things that made it survive where the manual drag didn't:

1. **One editor process per pack.** The first attempt died on a SIGSEGV and took
   every remaining pack with it. Per-pack process isolation means a crash costs
   one pack, and re-runs are resumable (already-moved assets are skipped).
2. **Verify on disk, never trust the API.** `rename_assets()` can fail without
   raising. The first run logged "137/137 moved" for OceanFloor when nothing had
   moved. Every rename is now checked with `does_asset_exist()`.
3. **Pack demo maps are the crash source.** OceanFloor's `Demonstration.umap`
   has editor-only Level Sequence nodes in its level Blueprint that throw
   compiler errors and destabilise the batch. Removing the `Maps/` folders let
   OceanFloor and SpringLandscape move first try. Those demo maps are parked in
   `Backups/PreEnvConsolidation-20260822-2013/RemovedDemoMaps/`.

## Reference repairs

Broken references from your own content: **144 → 65**.

Fixed (75 targets):
- **The Ortolan sheet mannequin.** `BP_OrtalanSheet`, `LS_OrtalanSheetSway` and
  `CA__OrtolanSheets` pointed at `/Game/EnvironmentPacks/PCGForestBlueprint/.../Mannequins/...`
  — a path with nothing at it, because the original crash hit before the assets
  arrived. Finishing that pack's move repaired it automatically.
- **75 relinked** via a round-trip rename (see technique below), mostly
  `KK_S1_Animals/*` and `Wings/*` references that resolve into `Scenes/`.

### The round-trip technique (reusable)

`AssetTools.fixup_referencers` **does not exist in UE 5.8's Python API** — it
throws `AttributeError`. And a *dangling* reference isn't in the dependency
graph, so `rename_assets` has no referencer to fix. The workaround:

1. Rename the asset from its current path **to the old (broken) path** — the
   dangling references now resolve, so the registry sees the referencers.
2. Rename it **back**. `rename_assets` now fixes up those referencers and leaves
   a redirector at the old path.

Either outcome repairs the reference. Script: `Saved/EnvConsolidation/relink_all.py`.

### Still broken (65) — not fixable from here

- **25** are folder/metadata strings (import-path records), not real asset
  references. Harmless.
- **40** are assets genuinely absent from the project. Grouped: `/Game/Scenes`
  (15 — mostly `_1`-suffixed rename artifacts where the original was deleted),
  `/Game/EnvironmentPacks` (9 — from your earlier interrupted move, in
  `Forest_Environment_Set`), `/Game/KK_S1_Animals` (5), `/Game/Wings` (5),
  `/Game/InfinityStage` (5 — `SavedVersions` data assets referencing their
  pre-rename selves), `/Game/Fab` (3).

`KK_S1_Animals` is worth a look: your `StageTest` level references it but the
folder isn't in the project. Check whether that pack is in the AssetsPile.

### One mistake worth knowing about

The redirector-fixup script caught the `fixup_referencers` AttributeError,
logged it, and **then deleted 371 redirectors anyway** — the delete should have
been gated on the fixup succeeding. That broke 5 reference targets (`Pig`,
`Raccoon`, `Train` from their `Scenes` counterparts), repaired by restoring the
stubs from the backup. Most of the 371 were genuinely unreferenced so the damage
was contained, but that was luck. **If you re-run any redirector cleanup, gate
the delete on the fixup.**

## Backups (local, APFS clones — near-zero disk cost)

| Path | Contents |
|---|---|
| `Backups/PreEnvConsolidation-20260822-2013/` | all user content + Config, pre-consolidation; also `RemovedDemoMaps/` |
| `Backups/PreRelink-20260822-2108/` | user content immediately before the reference relinking |

Not migrated to Drive (they're local safety nets, ~7 GB).

## Migration to Google Drive

Destination: `.../2026. SHS 3 Evenings/UE5.8/PussStage/`

**Included:** `PussStage.uproject`, `AGENTS.md`, `Config/`, `Content/`,
`Plugins/` (source only), `Scripts/`, `Docs/`, `Tools/`,
`StageWingCutoutPipeline/`, `go1_pi_bridge/`, `DerivedAssets/`, `Saved/`
(pipeline scripts; logs/autosaves/crashes excluded).

**Excluded** (rebuildable or local-only): `Binaries/`, `Intermediate/`,
`DerivedDataCache/`, `Backups/`, `PackagedPlugins/`, `ArchivedPlugins/`,
plugin `Binaries/`+`Intermediate/`.

**Relocated:** `Content/Megascans_ForestUnde_Source.zip` (8.3 GB) now sits at
`_SourceArchives/` rather than inside `Content/`, so UE doesn't scan an archive
on every load. Move it back into `Content/` if you ever want it there.

### Resuming / verifying the upload

The migration is `rsync`-based and **safe to re-run** — it skips what already
transferred and never deletes at either end:

```
"/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage/Saved/EnvConsolidation/migrate_to_drive.sh"
```

Progress log: `Saved/EnvConsolidation/migration.log`. Check the tail for
`rsync exit=0` per item and `=== migration finished ===`. Re-run it if the
laptop slept or Drive throttled mid-transfer. Note the Shared Drive needs
~46 GB of free quota.

## On the PC

1. Let Drive finish syncing `UE5.8/PussStage/`.
2. Open `PussStage.uproject` with **UE 5.8** (`EngineAssociation` is `"5.8"`).
3. It will rebuild `Binaries/`, `Intermediate/` and the DDC on first open — the
   first launch will be slow; that's expected, not a fault.
4. Custom plugins `InfinityStage` and `Go1Input` ship as source and will compile
   on first open. If it offers to rebuild missing modules, say yes.
5. Expect the 65 remaining broken references above as load warnings.

## Scripts left behind (`Saved/EnvConsolidation/`)

| Script | Purpose |
|---|---|
| `move_one_pack.py` + `drive.sh` | crash-isolated, resumable per-pack mover |
| `relink_all.py` | round-trip reference repair, driven by `fixmap.json` |
| `fixup_redirectors.py` | **do not re-run as-is** — its delete step isn't gated on the fixup |
| `migrate_to_drive.sh` | resumable Drive migration |

## Appendix — the 40 absent references, characterised

Investigated after the repairs. **None are regressions from this session**, and
none are recoverable by copying from the AssetsPile.

**`Forest_Environment_Set` foliage (9, in the vertical slice)** — checked
against the pile copy: the project's pack is **complete**, 52 models with an
identical file list. The pack only ever ships suffixed variants
(`SM_grass_01_1`, `SM_grass_01_3`, `SM_foliage_fern_01_1`…). The map references
*unsuffixed* names (`SM_grass_01`, `SM_foliage_fern_01`) that have never existed
in this pack — so these were authored against a different pack version, or are
foliage-type records rather than mesh references. Copying from the pile will not
fix them; the meshes would need repointing to the suffixed variants in the map.

**Rename artifacts (20)** — assets referencing their own pre-rename selves,
from the FBX import pipeline: `RedDeer_Calf_anim_IP_Anim_Arm_Deer_Idle_2`
references `…_Idle`, `Animal_Voices_1` references `Animal_Voices`, and the five
`InfinityStage/Dev/SavedVersions/DA_*_2026081*` data assets each reference their
undated original. The originals were replaced, not moved. Harmless unless you
want the version history to resolve.

**Wing textures/meshes (10)** — `Scenes/Wings/*/Materials/M_*_Back` referencing
textures (`L_wing`, `Villagers`, `Wet_wave`, `Shrine_curtain`, `wing`) and
`StageTest` external actors referencing `SM_Villagers`, `SM_Wet_wave`,
`SM_Cloud`, `SM_Shrine_curtain`, `SM_wing`. These predate this session and are
consistent with the wing reimport pipeline history — see the
`wing-import-cannot-reimport` note.

**Odds and ends (5)** — `/Game/KK_S1_Animals/M_Puddle` and `Animal_Voices`,
`KK_S2_Shrine/Falling_Leaves/Mesh/SM_Leaf`, three `Fab` meshes (Clam, Megascans
plinth) in the vertical slice, and `/Game/Maps/2kmTemplate` referenced by
`StageTest.umap` (a landscape template that was never in the project).

### Suggested triage order if you want these cleaned up

1. The 9 foliage references — highest visible impact (missing foliage in the
   vertical slice). Repoint to the suffixed meshes that do exist.
2. The 3 `Fab` meshes in the vertical slice — same reasoning, visible content.
3. The rest are cosmetic warnings.
