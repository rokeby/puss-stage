# P02/P03 wing audit

Audit date: 2026-10-08. Scope: offline, read-only reconstruction of the saved P02/P03 assignments after the 7 Oct RZSW APPLY records. No Unreal Editor, MCP, PIE, Blender, source asset, Show asset, or level was opened or changed.

## Proof boundary

- **Measured:** DRY rows were joined to the corresponding APPLY `written` maps, yielding 23 P02 rows / 46 sides and 21 P03 rows / 42 sides. Both APPLY records saved the Show asset and level after readback (`E:/PussStage/Saved/CodexFlatV3/rzswap/rzswap_dry_P02_LATEST.json:1`; `rzswap_apply_P02_RZSW-20261007-103331.json:1`; `rzswap_dry_P03_LATEST.json:1`; `rzswap_apply_P03_RZSW-20261007-103341.json:1`).
- **Measured:** source PNG dimensions, mesh bounds, flap manifests, edge probes, import-verification records, and saved lighting records were parsed; arithmetic and joins are in `audit.json`.
- **Inferred / not accepted:** source-art density and offline review images indicate risk, not rendered TSR, silhouette, lighting, or aesthetic acceptance. Those remain UNCLEAR because this brief forbids Unreal/PIE.

## Verdict

- **Measured:** family census is 42 Flat V3 thick5 realism sides, 23 older thick5 sides, 16 industrial 3D sides, seven V2 10 cm cards, and zero current 1.8 cm Flat V3 sides.
- **Measured:** the only sides below the brief?s ~250 source-px/m threshold are the seven surviving P03 V2 cards (167.6?184.7 px/m). P02 has no threshold failures. The red borders in the contact sheets mark exactly those seven.
- **Measured:** all 42 realism thick5 sides have outward edge winding (inward fraction <= 0.0018); all 23 older thick5 sides measure inward or mostly inward (>= 0.9828). All thick5 meshes are assigned the rolled-out `M_Wing_CanvasEdge_Master_v3`; rollout readback was 208/208 with no bad assets (`E:/PussStage/Saved/CodexFlatV3/edge/edge_family_probe.json:1`; `edge_rollout_plan.json:1`; `edge_rollout_verify_result.json:1`).
- **Declaration-proven:** Flat V3 standard art is POT 2048x4096 with full mips, four Front/Flap/Timber/Edge slots, no POM by default, and LOD1 beyond about 15 m (`E:/PussStage/Docs/FlatV3Spec_2026-09-30.md:138-183`).
- **Measured:** the seven V2 sources are non-POT; their saved mip stopgap is FromTextureGroup + StretchToPowerOfTwo. Their P03 Front/Back MIs use the painted master and relief maps (`E:/PussStage/Saved/CodexFlatV3/REPORT_FV3E-20261002-01.md:105-122`; `E:/PussStage/Docs/WingMateriality.md:287-293`).
- **Declaration-proven:** the painted master supplies POM from `_H`; Flat V3 instead uses SkinNormal plus real board/frame/flap depth (`E:/PussStage/Docs/WingMateriality.md:368-375`; `E:/PussStage/Docs/FlatV3Spec_2026-09-30.md:157-171`).
- **Measured:** industrial sides use authored 3D assemblies with tiled 2K/4K CC0 scans and four slots; a single front-art px/m value is not meaningful. Current Unreal mip readback and edge winding are UNCLEAR because no saved text probe covers them (`E:/PussStage/DerivedAssets/FlatV3/Overnight/P02Industrial/REPORT.md:7-16`; `REPORT.md:20-33`).

## Low-quality ranking

| Rank | Current side | Source px/m | Reason |
|---:|---|---:|---|
| 1 | P03 Wing 003 L | 167.6 | V2 source below ~250 px/m; replace first |
| 2 | P03 Wing 003 R | 170.4 | V2 source below ~250 px/m; replace first |
| 3 | P03 Wing 004 L | 177.4 | V2 source below ~250 px/m; replace first |
| 4 | P03 Wing 002 L | 180.8 | V2 source below ~250 px/m; replace first |
| 5 | P03 Wing 001 L | 182.5 | V2 source below ~250 px/m; replace first |
| 6 | P03 Wing 001 R | 184.3 | V2 source below ~250 px/m; replace first |
| 7 | P03 Wing 002 R | 184.7 | V2 source below ~250 px/m; replace first |

## Current per-side inventory

Every row below is **measured** from the saved records and source files. `out`/`in` are edge-winding probe results; `?` means no applicable saved probe. `POT/full` means the source is POT and follows the Flat V3 full-mip policy; `stretch` is the saved V2 stopgap; `scan/?` means POT scan sources but current Unreal mip readback is absent.

| Passage cue | Side | Mesh | Family | Board cm | Edge / material | Art px | min px/m | Mips | Relief | Flaps |
|---|:---:|---|---|---:|---|---:|---:|---|---|---:|
| P02 Wing 001 | L | `SM_FlatV3_P02_SET01_L_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 291.5 | POT/full | normal/no POM | 5 |
| P02 Wing 001 | R | `SM_FlatV3_P02_SET01_R_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 002 | L | `SM_FlatV3_P02_IND_FenceTarp_L` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 002 | R | `SM_FlatV3_P02_IND_FenceTarp_R` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 004 | L | `SM_FlatV3_P02_real_23_moss_covered_rock_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 004 | R | `SM_FlatV3_P02_real_32_entangled_roots_mossy_R_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 005 | L | `SM_FlatV3_P02_IND_FenceOpen_L` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 005 | R | `SM_FlatV3_P02_IND_FenceOpen_R` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 006 | L | `SM_FlatV3_P02_real_26_moss_covered_rock_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 006 | R | `SM_FlatV3_P02_real_37_wooden_stilt_hut_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 007 | L | `SM_FlatV3_P02_IND_RollerShutter_L` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 007 | R | `SM_FlatV3_P02_IND_RollerShutter_R` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 008 | L | `SM_FlatV3_P02_real_26_moss_covered_rock_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 008 | R | `SM_FlatV3_P02_real_37_wooden_stilt_hut_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 009 | L | `SM_FlatV3_P02_IND_FenceTarp_L` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 009 | R | `SM_FlatV3_P02_IND_FenceTarp_R` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 010 | L | `SM_FlatV3_P02_real_44_moss_covered_stone_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 010 | R | `SM_FlatV3_P02_real_42_rustic_wooden_hut_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 011 | L | `SM_FlatV3_P02_IND_FenceOpen_L` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 011 | R | `SM_FlatV3_P02_IND_FenceOpen_R` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 012 | L | `SM_FlatV3_P02_real_63_jungle_hut_mossy_L_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.5 | POT/full | normal/no POM | 5 |
| P02 Wing 012 | R | `SM_FlatV3_P02_real_53_wooden_stilt_house_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 013 | L | `SM_FlatV3_P02_IND_RollerShutter_L` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 013 | R | `SM_FlatV3_P02_IND_RollerShutter_R` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 014 | L | `SM_FlatV3_P02_real_23_moss_covered_rock_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 014 | R | `SM_FlatV3_P02_real_32_entangled_roots_mossy_R_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 003 | L | `SM_FlatV3_P02_real_19_moss_covered_driftwood_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 003 | R | `SM_FlatV3_P02_real_28_moss_covered_tree_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 015 | L | `SM_FlatV3_P02_real_44_moss_covered_stone_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 015 | R | `SM_FlatV3_P02_real_42_rustic_wooden_hut_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 016 | L | `SM_FlatV3_P02_IND_FenceOpen_L` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 016 | R | `SM_FlatV3_P02_IND_FenceOpen_R` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 017 | L | `SM_FlatV3_P02_real_63_jungle_hut_mossy_L_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.5 | POT/full | normal/no POM | 5 |
| P02 Wing 017 | R | `SM_FlatV3_P02_real_53_wooden_stilt_house_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 018 | L | `SM_FlatV3_P02_IND_RollerShutter_L` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 018 | R | `SM_FlatV3_P02_IND_RollerShutter_R` | 3D IND | n/a | ?; Edge v1 | 640x900 | n/a | scan/? | 3D/no POM | 0 |
| P02 Wing 019 | L | `SM_FlatV3_P02_SET19_L_t5j` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 019 | R | `SM_FlatV3_P02_SET19_R_t5j` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 309.4 | POT/full | normal/no POM | 5 |
| P02 Wing 020 | L | `SM_FlatV3_P02_SET20_L_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 323.3 | POT/full | normal/no POM | 5 |
| P02 Wing 020 | R | `SM_FlatV3_P02_SET20_R_t5j` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 322.2 | POT/full | normal/no POM | 5 |
| P02 Wing 021 | L | `SM_FlatV3_P02_real_19_moss_covered_driftwood_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 021 | R | `SM_FlatV3_P02_real_28_moss_covered_tree_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 335.7 | POT/full | normal/no POM | 5 |
| P02 Wing 022 | L | `SM_FlatV3_P04_ruined_gallery_L_v1_sc1_t5j` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 274.4 | POT/full | normal/no POM | 5 |
| P02 Wing 022 | R | `SM_FlatV3_P04_ruined_gallery_R_v1_sc1_t5j` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 264.1 | POT/full | normal/no POM | 3 |
| P02 Wing 023 | L | `SM_FlatV3_P04_coventry_ruin_L_v2_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 314.8 | POT/full | normal/no POM | 5 |
| P02 Wing 023 | R | `SM_FlatV3_P04_coventry_ruin_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 358.0 | POT/full | normal/no POM | 5 |
| P03 Wing 001 | L | `SM_P03_SunWashedAdministration_01_L` | V2 card | 10.0 | ?; P03 Edge MI | 862x1825 | 182.5 **LOW** | stretch | POM H+N | 0 |
| P03 Wing 001 | R | `SM_P03_SunWashedAdministration_01_R` | V2 card | 10.0 | ?; P03 Edge MI | 853x1843 | 184.3 **LOW** | stretch | POM H+N | 0 |
| P03 Wing 003 | L | `SM_P03_YellowCurtainThreshold_01_L` | V2 card | 10.0 | ?; P03 Edge MI | 938x1676 | 167.6 **LOW** | stretch | POM H+N | 0 |
| P03 Wing 003 | R | `SM_P03_YellowCurtainThreshold_01_R` | V2 card | 10.0 | ?; P03 Edge MI | 923x1704 | 170.4 **LOW** | stretch | POM H+N | 0 |
| P03 Wing 002 | L | `SM_P03_GlassBlockClassroom_01_L` | V2 card | 10.0 | ?; P03 Edge MI | 870x1808 | 180.8 **LOW** | stretch | POM H+N | 0 |
| P03 Wing 002 | R | `SM_P03_GlassBlockClassroom_01_R` | V2 card | 10.0 | ?; P03 Edge MI | 851x1847 | 184.7 **LOW** | stretch | POM H+N | 0 |
| P03 Wing 004 | L | `SM_P03_RepeatingSanatoriumArches_01_L` | V2 card | 10.0 | ?; P03 Edge MI | 887x1774 | 177.4 **LOW** | stretch | POM H+N | 0 |
| P03 Wing 004 | R | `SM_FlatV3_P03_real_39_rock_monolith_lichen_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 005 | L | `SM_FlatV3_P03_real_21_rock_formation_moss_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 005 | R | `SM_FlatV3_P03_real_45_rustic_wooden_cottage_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 379.2 | POT/full | normal/no POM | 5 |
| P03 Wing 006 | L | `SM_FlatV3_P03_real_40_stonehenge_portal_stone_L_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 006 | R | `SM_FlatV3_P03_real_43_weathered_wooden_tower_R_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 007 | L | `SM_FlatV3_P03_real_33_stone_pillar_ancient_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 007 | R | `SM_FlatV3_P03_real_52_rock_monolith_lichen_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 008 | L | `SM_FlatV3_P03_coat_wall_L_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 008 | R | `SM_FlatV3_P03_real_45_rustic_wooden_cottage_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 379.2 | POT/full | normal/no POM | 5 |
| P03 Wing 009 | L | `SM_FlatV3_P03_real_58_rock_formation_isolated_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 009 | R | `SM_FlatV3_P03_coat_wall_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 010 | L | `SM_FlatV3_P03_real_36_stone_monolith_with_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 010 | R | `SM_FlatV3_P03_real_52_rock_monolith_lichen_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 011 | L | `SM_FlatV3_P03_real_59_rock_formation_with_L_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 011 | R | `SM_FlatV3_P03_real_39_rock_monolith_lichen_R_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 012 | L | `SM_FlatV3_P03_real_33_stone_pillar_ancient_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 012 | R | `SM_FlatV3_P03_real_43_weathered_wooden_tower_R_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 013 | L | `SM_FlatV3_P03_real_41_rock_formation_with_L_t5p` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 013 | R | `SM_FlatV3_P03_stones_heavy_oblong_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 531.9 | POT/full | normal/no POM | 5 |
| P03 Wing 014 | L | `SM_FlatV3_P03_real_21_rock_formation_moss_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 014 | R | `SM_FlatV3_P03_pyre_small_burning_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 571.4 | POT/full | normal/no POM | 5 |
| P03 Wing 015 | L | `SM_FlatV3_P03_real_46_mossy_wooden_shack_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 015 | R | `SM_FlatV3_P03_stones_heavy_oblong_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 531.9 | POT/full | normal/no POM | 5 |
| P03 Wing 016 | L | `SM_FlatV3_P03_real_36_stone_monolith_with_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 016 | R | `SM_FlatV3_P03_stones_abstract_cluster_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 376.0 | POT/full | normal/no POM | 5 |
| P03 Wing 017 | L | `SM_FlatV3_P03_real_48_stone_pillar_ancient_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 017 | R | `SM_FlatV3_P03_pyre_small_burning_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 571.4 | POT/full | normal/no POM | 5 |
| P03 Wing 018 | L | `SM_FlatV3_P03_pyre_large_roaring_L_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 499.5 | POT/full | normal/no POM | 5 |
| P03 Wing 018 | R | `SM_FlatV3_P03_stones_abstract_cluster_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 376.0 | POT/full | normal/no POM | 5 |
| P03 Wing 019 | L | `SM_FlatV3_P03_real_51_stone_monolith_structure_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 019 | R | `SM_FlatV3_P03_stones_abstract_cluster_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 376.0 | POT/full | normal/no POM | 5 |
| P03 Wing 020 | L | `SM_FlatV3_P03_real_54_stone_monolith_with_L_t5j` | V3 t5 realism | 5.0 | out; ? | 2048x4096 | 401.6 | POT/full | normal/no POM | 5 |
| P03 Wing 020 | R | `SM_FlatV3_P03_pyre_small_burning_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 571.4 | POT/full | normal/no POM | 5 |
| P03 Wing 021 | L | `SM_FlatV3_P03_pyre_large_roaring_L_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 499.5 | POT/full | normal/no POM | 5 |
| P03 Wing 021 | R | `SM_FlatV3_P03_stones_abstract_cluster_R_v1_t5p` | V3 t5 older | 5.0 | in; Edge v3 | 2048x4096 | 376.0 | POT/full | normal/no POM | 5 |

Full object paths, bounds, exact inward fractions, source-art paths, flap evidence, and uncertainty fields are in `audit.json`. Contact sheets: `contact_sheet_P02.png`, `contact_sheet_P03.png`.

## Upgrade plan

1. **Measured priority:** replace the seven ranked P03 V2 sides first. Use the already PASS-verified P03 realism set; reserve `S2K_shrine_L/R` as a fresh L/R option for Wing 001 after an art-direction DRY review. Do not auto-assign P06 assets across passage identity. PASS inventories are in `rzimport_verify_887216a0_LATEST.json:1` (P02/P03 realism), `rzimport_verify_108927fa_LATEST.json:1` (S2K), and `rzimport_verify_70249bee_LATEST.json:1` (P06).
2. **Inferred proposal:** reduce obvious repeats when replacing: pair Wing 001 with S2K shrine L/R; choose less-repeated verified P03 rock/structure L/R candidates for Wings 002?004. Final pairings require a RZSW DRY sheet because fit, subject rhythm, and handedness are not proven by import PASS.
3. **Declaration-proven rebuild contract:** new art is approved in final L/R image handedness before derivatives; build POT SkinColor/SkinMask/SkinNormal at the current thick5 profile, four slots, two LODs, and outward edge walls. `_tools_v2` makes `--edge-walls-outward` mandatory and rejects inward fraction above 0.01 (`E:/PussStage/Docs/WingGenerationConventions.md:48-73`; `E:/PussStage/DerivedAssets/FlatV3/Realism_20261007/_tools_v2/rz2_build_one.py:26-62`; `rz2_build_one.py:307-323`; `rz2_build_one.py:460-474`).
4. **Measured hold:** do not rebuild the 23 older thick5 sides solely for resolution; all clear 250 px/m. Rebuild them when visual review exposes edge shading/silhouette problems, using the outward-edge path. The v3 edge material mitigates old inward winding, but rendered acceptance is UNCLEAR.
5. **Measured hold:** industrial art is not a low-density card problem. Judge it from the supplied front renders and later Unreal stills; only create new art if direction rejects the industrial subject, not to satisfy a card px/m metric.

## Open checks

- **UNCLEAR:** P03 V2 and industrial winding; searched the thick5 family/per-build edge probes, which do not include those families.
- **UNCLEAR:** industrial current Unreal mip settings; searched saved import/readback text and found no authoritative texture-property readback.
- **UNCLEAR:** rendered visibility of old inward walls under Edge v3 and all lighting/art judgments; no editor or renderer was permitted.
