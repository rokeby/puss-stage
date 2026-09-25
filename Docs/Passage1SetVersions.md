# Passage 1 set versions

## Pre-V2 set — saved 14 August 2026

Restorable Show Asset snapshot:

`/Game/InfinityStage/Dev/SavedVersions/DA_InfinityStage_V1Show_P01_PreV2_20260814`

This records the exact state immediately before the all-V2 trial. Passage 1 had 48 wing rows and one repeated ceiling:

- Rows 2–48 followed the three-pair cycle Rococo → Pillar 1 BW → Pillar 2 BW.
- Row 1 had already been changed for the earlier test: left `SM_SaltFormation_01_L_v2`, right `SM_R__1_roccoco`.
- All 48 top panels were `SM_Ceiling_bw`.
- Passage fit: Music Locked / Derive Count.
- Preferred spacing: 500 cm.
- Preferred camera speed: 250 cm/s.
- Lead-in: 24,000 ticks and 250 cm.
- Tail: 32,065 ticks and 334.014 cm.
- Side transforms: left Y = -750 cm; right Y = +750 cm; identity rotation and scale.
- Before the V2 trial, the left panel image-flip flag was enabled and the right flag disabled; both used Auto by Role.
- Passage actor component budget: 64.

The snapshot is a complete copy of the Show Asset, not merely a list of mesh names, so motion curves, timings, transforms, overrides, passage settings and the remainder of the show are preserved with it.

## All-V2 trial — applied 14 August 2026

The live Show Asset now cycles these nine pairs across Passage 1:

1. Bamboo Scaffold L / R
2. Ceramic Totem L / R
3. Covered Pillar L / R
4. Gauze Lattice L / R
5. Salt Formation L / R
6. Steel Scaffold L / R
7. Mutated Pelt Flora L / Ceramic Totem R
8. Covered Biomech Ceramic, rococo-painterly L / Covered Pillar R
9. Covered Biomech Ceramic, exposed rococo-painterly L / Steel Scaffold R

The cycle repeats over all 48 rows. It uses every one of the 15 StageOpeningV2 meshes. Left panels preserve the baked asset face; right panels rotate 180° around stage up. Neither side mirrors its photographic image. All existing tops and non-mesh Passage 1 settings remain unchanged.

Verified Unreal marker:

`P01_V2_SEQUENCE_VERIFY_SUCCESS|rows=48|sequence_pairs=9|unique_v2_meshes=15|tops=48|materialized_pairs=48|materialized_panels=144|orientation=left_preserve+right_rotate180|backup_readback=1`
