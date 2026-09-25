# UE Assets Pile — UE5.8 ground-building audit

Audit date: 2026-08-13  
Target project: PussStage, UE 5.8  
Source: `UE Assets Pile` on the GZZ Studio shared Google Drive

## Outcome

- Expanded all 21 top-level archives plus two nested muddy-road generator ZIPs.
- Verified the Unreal package/map/project count in every archive against its extracted copy before deleting archives.
- Deleted 23 verified archives, reclaiming approximately 35.7 GB.
- Deleted two byte-identical duplicate folders: `MeadowGrass(1) - Unpacked` and the standalone `Lowlands Landscape - Unpacked` (Lowlands remains in `Realistic Landscapes Bundle 2 - Unpacked`).
- Deleted 12 verified-invalid package stubs: nine zero-byte Brushify assets, two tiny redirector/stale Forest maps, and one tiny stale Spring material-function redirector.
- Following the audit, deleted both Muddy Roads V6 and V11 at the user's direction (approximately 2.7 GB combined).
- Deleted Nanite Sand Dunes 1 after confirming its nine meshes are authored as roughly 100 × 100 m terrain tiles, each carrying an approximately 8.38-million-triangle Nanite source. They can be numerically scaled down, but are not sensible small-scale stage meshes.
- Current pile: about 34 GB, 6,038 Unreal packages/maps, zero remaining ZIP/RAR/7z archives.

The UE5.8 audit mounted the original content roots in a disposable project and attempted to load every map plus representative Blueprints, PCG graphs, landscape materials/functions/layers, foliage types, textures and meshes. The combined audit loaded 417 of 420 selected packages. The three failed items were the invalid stubs removed above; the content libraries containing them remained loadable.

## Imported into PussStage — 2026-08-14

The production-ready subset has now been copied into the live project's `Content` folder while preserving every original top-level `/Game/...` root. Source-to-project `rsync` dry runs reported exact parity after the copy, and no existing project content roots were overwritten.

Imported roots: `LSM`, `MWMeadowWetlands`, `HighGrassLandscape`, `LowlandsLandscape`, `SpringLandscape`, `DeadHillsLandscape`, `Brushify`, `PCGForestBlueprint`, `ProceduralNtr_vol2`, `PN_FoliageCollection`, `MeadowGrass`, `Forest_Environment_Set`, `Desert`, and `OceanFloor`.

- Imported size: approximately 27 GB across 4,281 Unreal packages/maps.
- Project `Content` size after import: approximately 34 GB.
- Enabled the built-in `PCG` plugin in `PussStage.uproject` for the forest graphs and Blueprints.
- A live-project UE5.8 headless scan loaded 275 of 275 selected assets across all 14 roots with zero load failures. The selection included every imported map plus representative landscape assets, materials, foliage types, PCG graphs, Blueprints, meshes, and textures.
- The first scan populated derived data for old meshes, materials, animations, and distance fields. Procedural Nature still reports several old meshes that should be resaved in UE5.8 before a deterministic production cook.
- Available disk space after import was approximately 53 GiB. Allow extra headroom for DDC and cooked builds; remove unused demo/template content before packaging if space gets tight.

## Best production choices for rich ground

| Priority | Pack | UE5.8 result | Best use | Important caveats |
|---|---|---|---|---|
| 1 | MWMeadowWetlands | Pass | Hero wet ground: mud, saturated soil, water, cover, debris, roots, rocks, plants and dense meadow foliage | Large (6.1 GB). Ignore/remove the bundled UE4 first-person template; its legacy input mappings warn but environment content loads. |
| 2 | Landscape Smart Material | Pass | Base landscape shader and layer workflow; grass, detail, rock, peaks, river/lake, mist/weather support | Resave in UE5.8. Demo cameras contain stale focus enum values, but landscape assets load. |
| 3 | Realistic Landscapes Bundle 2 | Pass after invalid stub removal | Four terrain looks: High Grass, Lowlands, Spring and Dead Hills; useful layer materials and broad midground coverage | Old content triggers resave/migration work. The removed Spring stub was an unused redirector to `/Game/AL2/...`, not the functional landscape material. |
| 4 | Brushify Canyons | Pass after invalid zero-byte removal | Large-scale cliffs, canyon silhouettes, distance meshes, alpha brushes and rock slabs | The source archive contained nine zero-byte files; removed. Some procedural foliage placements referencing those types will need reassignment. |
| 5 | PCG Forest Blueprint | Pass | Procedural placement and variation over a terrain base | PCG plugin must be enabled. One bundled ThirdPerson map has a missing External Actor; use the forest graphs/Blueprints, not that template map. |
| 6 | Procedural Nature Seasons | Pass with resave | Seasonal bushes, root splines, ground dressing and procedural nature details | Demo map has stale BSP/video references; several meshes require UE5.8 resave for deterministic cooking. Assets themselves load. |
| 7 | PN Foliage Collection (`草地`) | Pass | Very large foliage/grass library for close and middle distance | Ignore the bundled UE4 ThirdPerson template; its obsolete XR node fails to compile. Foliage types and materials load. |
| 8 | MeadowGrass | Pass | Lightweight close-up grass clumps, flower/grass dressing and a simple meadow ground | UE5.0 project; migrate the `MeadowGrass` content folder and resave. |

## Secondary/specialized packs

| Pack | UE5.8 result | Recommendation |
|---|---|---|
| Desert | Pass with missing optional references | Useful sand, gravel, dry grass, shrubs, cactus, cliffs and mountains. Some master assets reference two missing `/Game/MWDuneDesert/...` sand textures and a missing mannequin material. Use the terrain materials/instances and present textures; inspect any imported master instance. |
| Ocean Floor Environment | Environment assets pass | Excellent for unusual ground detail: sand, rock, debris, algae/coralline. Two textures are missing and the obsolete Matinee/demo Blueprint logic does not compile in UE5.8; migrate meshes/materials, not the demonstration logic. |
| Stylized Azure Hillside | Pass | Useful only if the scene wants a stylized ground language. Strong grass/dirt/sand layer set and foliage, but not photoreal. |
| Stylized Village Fatpack | Pass with missing demo dependencies | Broad stylized terrain/foliage/stone library. Three terrain LayerInfo assets reference missing demo physical materials; reassign physical materials. One showcase sequence is missing. |
| Advanced Road Materials | Pass | Lightweight supplement for asphalt, gravel, ground and moss road surfaces; visually dated but technically loadable. |
| Road — Materials and Decals | Pass | Large road texture/decal library. Original content appears very old (some packages carry UE4.19-era markers), so resave and visually validate shading. Better for roads than natural hero ground. |
| Procedural Tunnels | Core tunnel Blueprint passes | Useful only if terrain holes/tunnels are needed. Its landscape-hole materials depend on missing Starter Content textures; add Starter Content or replace those texture references. |
| Forest Environment Set | Main and overview maps pass after stale stub removal | Good forest floor, roots, slopes, roads and vegetation. The two deleted tiny maps were redirectors/stale packages with old `/Game/Meadow_Environment_Set` and `/Game/Environment_Set` paths. |

## Recommended ground recipe

1. Use Landscape Smart Material as the terrain master, or lift only the required layer/material functions into a clean PussStage landscape master.
2. Build broad terrain zones from Realistic Landscapes: Lowlands/High Grass for the main surface, Dead Hills for drier transitions, Spring for fresher green areas.
3. Use MWMeadowWetlands for the hero wet zone: darker soil, puddle/water edges, moss, cover and debris.
4. Scatter PN Foliage and Procedural Nature assets through PCG Forest graphs. Keep hero plants hand-directed near camera paths.
5. Use Brushify cliffs/alpha brushes and Forest Environment roots/rocks to break the landscape silhouette and hide terrain transitions.
6. Treat Ocean Floor sand/rock/debris as a texture-and-prop donor for wet or uncanny areas; do not migrate its demo logic.

## First-use workflow in PussStage

The selected packs are now present in the live project. Before promoting particular assets into the show level:

- Open the overview/demo map and the chosen master material.
- Fix missing references listed above.
- Resave migrated packages in UE5.8.
- Compile affected materials and Blueprints.
- Run Map Check and a target-platform cook before promoting the pack into the show project.
- Validate Nanite, Virtual Shadow Maps, masked foliage overdraw, PCG density and texture memory on the actual playback machine.

## Audit artifacts

- Combined machine-readable results: `Saved/AssetAuditHarness/Saved/AuditResults/combined.json`
- Combined UE5.8 log: `Saved/AssetAuditHarness/Saved/AuditResults/combined.log`
- Historical Muddy Roads V6 results (pack subsequently deleted): `Saved/AssetAuditHarness/Saved/AuditResults/muddy_v6.json`
- Historical Muddy Roads V6 log: `Saved/AssetAuditHarness/Saved/AuditResults/muddy_v6.log`
- Historical dune scale metadata (pack subsequently deleted): `Saved/AssetAuditHarness/Saved/AuditResults/dune_registry.json`
- Live-project import validation: `Saved/AssetImportAudit/live_import.json`
- Live-project UE5.8 validation log: `Saved/AssetImportAudit/live_import.log`

The headless editor returns exit code 1 after the audit requests normal shutdown, but both runs reached `UE58_AUDIT_RESULT` and `UE58_AUDIT_END` and wrote complete JSON results.
