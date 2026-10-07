# Klara ingest census (offline, read-only)

Generated 2026-10-06T21:03:38 by `Tools/KlaraIngest/census.py` + `analyse.py`. Source: `C:\KlaraIngest\KK_Children_copy\Content`; target: `E:\PussStage\Content`.

Proof tiers: **measured** = the scripts read the bytes and the number/string is in the JSON; **inferred** = interpretation the scan cannot verify (no Unreal was run).

Method (limits): raw byte scan of each package for `/Mount/...` strings (ASCII + UTF-16LE), soft refs treated as hard, recursion to closure. Conservative: strings in metadata (import paths, thumbnails) also count, so closure may be a superset (inferred). FName number-suffix siblings (`X_1` stored as `X`+number) were included when the base had no file.

## Per scene

### S1: `/Game/KK_S1_Animals/LS_Animals_1`

- Maps the sequence mentions (measured, string in LS): `/Game/KK_S1_Animals/L_Animals`; bound actors: 25 `PersistentLevel.*` paths, so its possessables resolve into a level (inferred from UniversalObjectLocator strings).
- Sequence-only closure (maps not expanded): 54 packages, 58.9 MB (measured).
- Full closure (maps expanded): 183 packages, 1.45 GB; level-only packages: 129 (measured).
- Top folders (full): `KK_S1_Animals/Dirt_etc` 0.37 GB; `TwineTrees/TXT` 0.36 GB; `KK_S1_Animals/Wooden_Floor` 0.22 GB; `KK_S1_Animals/PN_MeadowFlowers` 0.14 GB; `TwineTrees/SM` 0.14 GB; `KK_S1_Animals/Deer` 77.9 MB
- Playback range -10.333 s to 200.267 s = **210.6 s**; tick 24000/1, display 30/1 fps (measured, decoded tagged properties; Denominator defaulted to 1 when the tag was absent).
- Track/section classes (measured, name table): 3DTransformSection, 3DTransformTrack, AudioSection, AudioTrack, CameraCutSection, CameraCutTrack, ColorSection, ColorTrack, ControlRigParameterSection, ControlRigParameterTrack, FloatSection, FloatTrack, SkeletalAnimationSection, SkeletalAnimationTrack
- Bound actors (measured strings): CineCameraActor_0, CineCameraActor_1, CineCameraActor_3, CineCameraActor_4, CineCameraActor_7, Floor_0, RectLight_14, RectLight_15, RectLight_16, SkeletalMeshActor_13, SkeletalMeshActor_15, SkeletalMeshActor_7, SpotLight_1, SpotLight_11, SpotLight_13, SpotLight_15, SpotLight_17, SpotLight_18, SpotLight_19, SpotLight_20, SpotLight_22, SpotLight_23, SpotLight_8, StaticMeshActor_14, StaticMeshActor_2
- Audio in closure (measured, asset-registry tags):
  - `KK_S1_Animals/Animals_Project_CLICK` 149.207535 s, 44100 Hz, 2 ch (direct ref of sequence); source `../../Animals_Project_CLICK.wav`
- Unresolved /Game refs: 102 — STALE_PATH_OF_MOVED_ASSET (current copy exists) / string-only: 101; MISSING / string-only: 1
  - MISSING: `/Game/Pig/pig_fbx/Pig`

### S2: `/Game/KK_S2_Shrine/LS_NEW_SHRINE`

- Maps the sequence mentions (measured, string in LS): `/Game/Japanese_Alley/Maps/Japanese_Alley`; bound actors: 1 `PersistentLevel.*` paths, so its possessables resolve into a level (inferred from UniversalObjectLocator strings).
- Sequence-only closure (maps not expanded): 2 packages, 0.6 MB (measured).
- Full closure (maps expanded): 223 packages, 0.86 GB; level-only packages: 221 (measured).
- Top folders (full): `Japanese_Alley/Materials` 0.60 GB; `KK_S2_Shrine/Turnips` 0.20 GB; `Japanese_Alley/Maps` 26.6 MB; `KK_S2_Shrine/NewShrine_wing` 19.0 MB; `KK_S2_Shrine/StarterContent` 6.6 MB; `Japanese_Alley/Meshes` 4.4 MB
- Playback range 0.0 s to 5.0 s = **5.0 s**; tick 24000/1, display 30/1 fps (measured, decoded tagged properties; Denominator defaulted to 1 when the tag was absent).
- Track/section classes (measured, name table): 3DTransformSection, 3DTransformTrack, CameraCutSection, CameraCutTrack, FloatSection, FloatTrack
- Bound actors (measured strings): CineCameraActor_1
- Unresolved /Game refs: 11 — MISSING / in-name-table: 1; STALE_PATH_OF_MOVED_ASSET (current copy exists) / string-only: 7; MISSING / string-only: 3
  - MISSING: `/Game/Japanese_Alley/Materials/Textures/T_Fornitures_Bar_Metal_Roughness`, `/Game/KK_S2_Shrine/Turnips/Materials/MatID_1`, `/Game/TOOLS/Falling_Leaves/Mesh/LEAF_1/AmbientOcclusionMap`, `/Game/TOOLS/Falling_Leaves/Mesh/LEAF_1/Leaf_1`

### S4: `/Game/LS_Children`

- Maps the sequence mentions (measured, string in LS): `/Game/KK_S1_Animals/L_Animals`, `/Game/L_KK_children`; bound actors: 26 `PersistentLevel.*` paths, so its possessables resolve into a level (inferred from UniversalObjectLocator strings).
- Sequence-only closure (maps not expanded): 345 packages, 1.88 GB (measured).
- Full closure (maps expanded): 596 packages, 3.59 GB; level-only packages: 251 (measured).
- Top folders (full): `MetaHumans/MHC_Child` 0.50 GB; `MetaHumans/MH_Test` 0.46 GB; `KK_S1_Animals/Dirt_etc` 0.37 GB; `TwineTrees/TXT` 0.36 GB; `CaptureManager/Imports` 0.30 GB; `KK_S1_Animals/Wooden_Floor` 0.22 GB
- Playback range 0.0 s to 164.0 s = **164.0 s**; tick 24000/1, display 30/1 fps (measured, decoded tagged properties; Denominator defaulted to 1 when the tag was absent).
- Track/section classes (measured, name table): 3DTransformSection, 3DTransformTrack, AudioSection, AudioTrack, CameraCutSection, CameraCutTrack, ColorSection, ColorTrack, ControlRigParameterSection, ControlRigParameterTrack, FloatSection, FloatTrack, GeometryCacheSection, GeometryCacheTrack, ObjectPropertySection, ObjectPropertyTrack, SkeletalAnimationSection, SkeletalAnimationTrack, VisibilitySection, VisibilityTrack
- Bound actors (measured strings): BP_MHC_Child_C_0, BP_MHC_Child_C_1, BP_MHC_Child_C_2, BP_MHC_Child_C_3, BP_MHC_Child_C_4, BP_MHC_Child_C_5, BP_MHC_Child_C_6, BP_Pendulum_C_0, CineCameraActor_0, CineCameraActor_1, CineCameraActor_5, Floor_0, GeometryCacheActor_0, SkeletalMeshActor_0, SkeletalMeshActor_2, SpotLight_0, SpotLight_1, SpotLight_17, SpotLight_2, SpotLight_20, SpotLight_22, SpotLight_23, SpotLight_3, SpotLight_5, SpotLight_6, SpotLight_8
- Audio in closure (measured, asset-registry tags):
  - `KK_S1_Animals/Animals_Project_CLICK` 149.207535 s, 44100 Hz, 2 ch; source `../../Animals_Project_CLICK.wav`
  - `L_K_Children/Children_Project_CENTRE` 165.886505 s, 44100 Hz, 2 ch (direct ref of sequence); source `../../Children_Project_CENTRE.wav`
  - `L_K_Children/Children_Project_CLICK` 165.886505 s, 44100 Hz, 2 ch (direct ref of sequence); source `../../Children_Project_CLICK.wav`
  - `L_K_Children/Children_Project_wFlute_1_` 165.886505 s, 44100 Hz, 2 ch (direct ref of sequence); source `../../Children_Project_wFlute(1).wav`
- Unresolved /Game refs: 162 — STALE_PATH_OF_MOVED_ASSET (current copy exists) / string-only: 133; MISSING / string-only: 29
  - MISSING: `/Game/Developers/Jeremie/MetaHuman/FootRoll/FootRoll_A`, `/Game/Developers/Jeremie/MetaHuman/IKSpine/IKSpine_A_003`, `/Game/Developers/Jeremie/MetaHuman/MetaHuman_ControlRig_Functions`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype/FlowMap_2_flow`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype/Pore_Mask`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype/Tests`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype/Tests/RegionMask2`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype/temp`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype/temp/pores_horizontal_N3C`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype/temp/pores_neutral_N3C`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype/temp/pores_nose_N3C`, `/Game/Developers/zahratilling/OptimisedSkinNormals/PaperPrototype/temp/pores_vertical_N3C`, `/Game/NewFolder/Book/Textures`, `/Game/NewFolder/Book/Textures/BookCloth_BaseColor`, `/Game/NewFolder/Book/Textures/BookCloth_Normal`, `/Game/NewFolder/Book/Textures/BookCloth_Roughness`, `/Game/NewFolder/Book/Textures/BookCover_BaseColor`, `/Game/NewFolder/Book/Textures/BookCover_Normal`, `/Game/NewFolder/Book/Textures/BookCover_Roughness`, `/Game/NewFolder/Book/Textures/Page1_BaseColor`, `/Game/NewFolder/Book/Textures/Pages_BaseColor`, `/Game/NewFolder/Book/Textures/Pages_Normal`, `/Game/Pig/pig_fbx/Pig`, `/Game/WoodMaterial3/Textures/MG-wood_01_Base_Color`, `/Game/lookdev/chars/alice/textures/Head/T_EyeSclera_D`, `/Game/lookdev/chars/alice/textures/Head/T_EyeSclera_N2`, `/Game/lookdev/chars/alice/textures/Head/T_Iris001_01_D`, `/Game/lookdev/chars/alice/textures/Head/T_TilingNoise_001`

## Collision diff (union of full closures)

- **NEW**: 781 files, 4.40 GB (of which in a sequence-only closure: 397 files, 1.93 GB) — measured, SHA-256.
- **IDENTICAL**: 13 files, 7.6 MB (of which in a sequence-only closure: 0 files, 0.0 MB) — measured, SHA-256.
- **COLLIDES**: 25 files, 37.1 MB (of which in a sequence-only closure: 3 files, 4.4 MB) — measured, SHA-256.
- E: free 196.94 GB; NEW bytes are 2.2% of it (measured).

### COLLIDES (need Gary's decision: keep ours / take Klara's / import under a new root)

| path | Klara bytes | ours bytes | Klara mtime | ours mtime | in sequence closure |
|---|---|---|---|---|---|
| `KK_S1_Animals/Cauldron/Cauldron.uasset` | 3500366 | 1257 | 2026-09-16T18:27:42 | 2026-08-22T16:09:50 | False |
| `KK_S1_Animals/Cauldron/old-cauldron/textures/M_cauldron.uasset` | 20094 | 1355 | 2026-09-16T18:27:42 | 2026-08-22T16:10:46 | False |
| `KK_S1_Animals/Deer/reddeerfamily_fbx/M_Deer.uasset` | 20929 | 1295 | 2026-09-16T18:27:42 | 2026-08-22T16:10:46 | False |
| `KK_S1_Animals/Deer/reddeerfamily_fbx/RedDeer_Calf_anim_IP.uasset` | 1855258 | 1401 | 2026-09-16T18:27:43 | 2026-08-22T16:10:46 | True |
| `KK_S1_Animals/Dirt_etc/StaticMeshes/play-dig.uasset` | 21494599 | 1309 | 2026-09-16T18:27:44 | 2026-08-22T16:12:39 | False |
| `KK_S1_Animals/Pig/pig_fbx/Pig_anim_RM.uasset` | 1685184 | 1294 | 2026-09-16T18:27:40 | 2026-08-22T16:12:39 | True |
| `KK_S1_Animals/Pig/pig_fbx/pig_textures/texture/M_Pig.uasset` | 19280 | 1328 | 2026-09-16T18:27:40 | 2026-08-22T16:12:39 | False |
| `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_02_01.uasset` | 139312 | 1389 | 2026-09-16T18:27:42 | 2026-08-22T16:12:39 | False |
| `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_02_03.uasset` | 170321 | 1389 | 2026-09-16T18:27:42 | 2026-08-22T16:12:39 | False |
| `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_02_04.uasset` | 196388 | 1389 | 2026-09-16T18:27:40 | 2026-08-22T16:12:39 | False |
| `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_05_05.uasset` | 121682 | 1389 | 2026-09-16T18:27:42 | 2026-08-22T16:12:39 | False |
| `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_09_06.uasset` | 135078 | 1389 | 2026-09-16T18:27:41 | 2026-08-22T16:12:39 | False |
| `KK_S1_Animals/Raccoon/medhue_raccoon.uasset` | 834263 | 1299 | 2026-09-16T18:27:40 | 2026-08-22T16:12:40 | True |
| `KK_S1_Animals/Train/subway-train/subway_train.uasset` | 76439 | 1321 | 2026-09-16T18:27:08 | 2026-08-22T16:10:47 | False |
| `KK_S1_Animals/Train/subway-train/subway_train1.uasset` | 3274837 | 1336 | 2026-09-16T18:27:08 | 2026-08-22T16:12:40 | False |
| `KK_S1_Animals/Wings/PNG/M_Ceiling_Animals.uasset` | 28195 | 1320 | 2026-09-16T18:27:40 | 2026-08-22T16:10:47 | False |
| `KK_S1_Animals/Wings/PNG/M_L_2_Animals.uasset` | 26262 | 1292 | 2026-09-16T18:27:39 | 2026-08-22T16:10:47 | False |
| `KK_S1_Animals/Wings/PNG/M_R_2_Animals.uasset` | 26145 | 1292 | 2026-09-16T18:27:39 | 2026-08-22T16:10:47 | False |
| `KK_S1_Animals/Wings/PNG/StaticMeshes/StaticMeshes/SM_Celing_Animals_Wing_Final.uasset` | 308473 | 1505 | 2026-09-16T18:27:08 | 2026-08-22T16:12:40 | False |
| `KK_S1_Animals/Wings/PNG/StaticMeshes/StaticMeshes/SM_L_Wing_2_Animals.uasset` | 276694 | 1442 | 2026-09-16T18:27:08 | 2026-08-22T16:12:40 | False |
| `KK_S1_Animals/Wings/PNG/StaticMeshes/StaticMeshes/SM_R__Wing_2_Animals.uasset` | 275776 | 1449 | 2026-09-16T18:27:08 | 2026-08-22T16:12:40 | False |
| `KK_S2_Shrine/Falling_Leaves/FX/NS_Falling_Leaves.uasset` | 905664 | 905051 | 2026-09-16T18:37:24 | 2026-07-24T07:44:05 | False |
| `KK_S2_Shrine/Falling_Leaves/Mesh/SM_Leaf_1.uasset` | 20226 | 20226 | 2026-09-16T18:37:24 | 2026-07-24T07:44:06 | False |
| `KK_S2_Shrine/StarterContent/Particles/P_Fire.uasset` | 311874 | 311874 | 2026-09-16T18:37:23 | 2026-07-25T05:28:41 | False |
| `KK_S2_Shrine/WINGS/Materials/S2_ceiling_wing.uasset` | 1359627 | 1359532 | 2026-09-16T18:37:24 | 2026-07-24T11:54:32 | False |

Our side (measured: our package name tables; referrers from `Tools/KlaraIngest/our_referrers.py`, first 8 MB of every package in our Content, ASCII+UTF-16):

- `KK_S1_Animals/Cauldron/Cauldron.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Cauldron/Cauldron`; our packages naming this path: 1 (__ExternalActors__/Levels/StageTest/8/JQ/RDWW64Y99XG4ACAUYGQI44.uasset)
- `KK_S1_Animals/Cauldron/old-cauldron/textures/M_cauldron.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Cauldron/old-cauldron/textures/M_cauldron`; our packages naming this path: 1 (__ExternalActors__/Levels/StageTest/8/JQ/RDWW64Y99XG4ACAUYGQI44.uasset)
- `KK_S1_Animals/Deer/reddeerfamily_fbx/M_Deer.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Deer/reddeerfamily_fbx/M_Deer`; our packages naming this path: 1 (__ExternalActors__/Levels/StageTest/D/8E/PNSWQX34M0BM7UTKHEBDYB.uasset)
- `KK_S1_Animals/Deer/reddeerfamily_fbx/RedDeer_Calf_anim_IP.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Deer/reddeerfamily_fbx/RedDeer_Calf_anim_IP`; our packages naming this path: 3 (Scenes/Deer/reddeerfamily_fbx/RedDeer_Calf_anim_IP_PhysicsAsset.uasset, Scenes/Deer/reddeerfamily_fbx/RedDeer_Calf_anim_IP_Skeleton.uasset, __ExternalActors__/Levels/StageTest/D/8E/PNSWQX34M0BM7UTKHEBDYB.uasset)
- `KK_S1_Animals/Dirt_etc/StaticMeshes/play-dig.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Dirt_etc/StaticMeshes/play-dig`; our packages naming this path: 4 (__ExternalActors__/Levels/StageTest/1/P0/SEO83BLO27VHHCX48LAVAK.uasset, __ExternalActors__/Levels/StageTest/6/BE/1VRHWRRI214E4A875R704B.uasset, __ExternalActors__/Levels/StageTest/7/U8/N7E7ZZEHP7OPD5JMTYG2AI.uasset)
- `KK_S1_Animals/Pig/pig_fbx/Pig_anim_RM.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Pig/pig_fbx/Pig_anim_RM`; our packages naming this path: 3 (Scenes/Pig/pig_fbx/Pig_anim_RM_PhysicsAsset.uasset, Scenes/Pig/pig_fbx/Pig_anim_RM_Skeleton.uasset, __ExternalActors__/Levels/StageTest/0/WJ/CDZCBZW9UVJBA3VQUEIPCA.uasset)
- `KK_S1_Animals/Pig/pig_fbx/pig_textures/texture/M_Pig.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Pig/pig_fbx/pig_textures/texture/M_Pig`; our packages naming this path: 1 (__ExternalActors__/Levels/StageTest/0/WJ/CDZCBZW9UVJBA3VQUEIPCA.uasset)
- `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_02_01.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/PN_MeadowFlowers/Meshes/flowerMesh/flower_02_01`; our packages naming this path: 1 (__ExternalActors__/Levels/StageTest/B/C2/MAI0VGS4ERS7NC915D76NL.uasset)
- `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_02_03.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/PN_MeadowFlowers/Meshes/flowerMesh/flower_02_03`; our packages naming this path: 1 (__ExternalActors__/Levels/StageTest/D/WR/4ROMQDFKXU2DPDH5RG2NAK.uasset)
- `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_02_04.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/PN_MeadowFlowers/Meshes/flowerMesh/flower_02_04`; our packages naming this path: 1 (__ExternalActors__/Levels/StageTest/E/LW/33TGUSMA99VP04OB8EXBKA.uasset)
- `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_05_05.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/PN_MeadowFlowers/Meshes/flowerMesh/flower_05_05`; our packages naming this path: 2 (__ExternalActors__/Levels/StageTest/B/MD/XAUBF6R64ER46AVNYYVYMF.uasset, __ExternalActors__/Levels/StageTest/E/5H/HDB7GWUZT0FIHFHV163XGD.uasset)
- `KK_S1_Animals/PN_MeadowFlowers/Meshes/flowerMesh/flower_09_06.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/PN_MeadowFlowers/Meshes/flowerMesh/flower_09_06`; our packages naming this path: 1 (__ExternalActors__/Levels/StageTest/C/IB/EX8GQV6R2SHLOVQJJBTKAJ.uasset)
- `KK_S1_Animals/Raccoon/medhue_raccoon.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Raccoon/medhue_raccoon`; our packages naming this path: 3 (Scenes/Raccoon/medhue_raccoon_PhysicsAsset.uasset, Scenes/Raccoon/medhue_raccoon_Skeleton.uasset, __ExternalActors__/Levels/StageTest/1/1X/JL1SVQF1HQHU2HQDHGC60V.uasset)
- `KK_S1_Animals/Train/subway-train/subway_train.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Train/subway-train/subway_train`; our packages naming this path: 5 (KK_S1_Animals/Train/subway-train/subway_train1.uasset, Scenes/Train/subway-train/subway_train_PhysicsAsset.uasset, Scenes/Train/subway-train/subway_train_Skeleton.uasset)
- `KK_S1_Animals/Train/subway-train/subway_train1.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Train/subway-train/subway_train1`; our packages naming this path: 4 (Scenes/Train/subway-train/subway_train_PhysicsAsset.uasset, Scenes/Train/subway-train/subway_train_Skeleton.uasset, __ExternalActors__/Levels/StageTest/8/XB/WLWBAO6C5KU4KENE39IGQ4.uasset)
- `KK_S1_Animals/Wings/PNG/M_Ceiling_Animals.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Wings/PNG/M_Ceiling_Animals`; our packages naming this path: 4 (__ExternalActors__/Levels/StageTest/8/MQ/D26TDF72WR5BLKSVX770KP.uasset, __ExternalActors__/Levels/StageTest/D/Y6/33VCWRZ86U2B1QD737YOSV.uasset, __ExternalActors__/Levels/StageTest/E/1Y/BBBVFCD431X04DDT4VY75I.uasset)
- `KK_S1_Animals/Wings/PNG/M_L_2_Animals.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Wings/PNG/M_L_2_Animals`; our packages naming this path: 2 (__ExternalActors__/Levels/StageTest/2/3T/AI9FY3CGYB2HN950O6OK0J.uasset, __ExternalActors__/Levels/StageTest/4/YF/GYPII9PTO5X5RG9VGI9H82.uasset)
- `KK_S1_Animals/Wings/PNG/M_R_2_Animals.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Wings/PNG/M_R_2_Animals`; our packages naming this path: 2 (__ExternalActors__/Levels/StageTest/3/6M/LVSLM6FHXOHDGZ7WYS926N.uasset, __ExternalActors__/Levels/StageTest/7/ZD/F6MXJIZCZ78FSM9NY7IAA3.uasset)
- `KK_S1_Animals/Wings/PNG/StaticMeshes/StaticMeshes/SM_Celing_Animals_Wing_Final.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Wings/PNG/StaticMeshes/StaticMeshes/SM_Celing_Animals_Wing_Final`; our packages naming this path: 4 (__ExternalActors__/Levels/StageTest/8/MQ/D26TDF72WR5BLKSVX770KP.uasset, __ExternalActors__/Levels/StageTest/D/Y6/33VCWRZ86U2B1QD737YOSV.uasset, __ExternalActors__/Levels/StageTest/E/1Y/BBBVFCD431X04DDT4VY75I.uasset)
- `KK_S1_Animals/Wings/PNG/StaticMeshes/StaticMeshes/SM_L_Wing_2_Animals.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Wings/PNG/StaticMeshes/StaticMeshes/SM_L_Wing_2_Animals`; our packages naming this path: 2 (__ExternalActors__/Levels/StageTest/2/3T/AI9FY3CGYB2HN950O6OK0J.uasset, __ExternalActors__/Levels/StageTest/4/YF/GYPII9PTO5X5RG9VGI9H82.uasset)
- `KK_S1_Animals/Wings/PNG/StaticMeshes/StaticMeshes/SM_R__Wing_2_Animals.uasset`: our file is an ObjectRedirector -> `/Game/Scenes/Wings/PNG/StaticMeshes/StaticMeshes/SM_R__Wing_2_Animals`; our packages naming this path: 2 (__ExternalActors__/Levels/StageTest/3/6M/LVSLM6FHXOHDGZ7WYS926N.uasset, __ExternalActors__/Levels/StageTest/7/ZD/F6MXJIZCZ78FSM9NY7IAA3.uasset)
- `KK_S2_Shrine/Falling_Leaves/FX/NS_Falling_Leaves.uasset`: our file is a real asset; our packages naming this path: 4 (KK_S2_Shrine/KK_Main_S2_Shrine.umap, KK_S2_Shrine/Falling_Leaves/BP_Falling_Leaves.uasset, __ExternalActors__/Levels/StageTest/1/C6/HYWZOWG07434GDI0LYNAM5.uasset)
- `KK_S2_Shrine/Falling_Leaves/Mesh/SM_Leaf_1.uasset`: our file is a real asset; our packages naming this path: 0 ()
- `KK_S2_Shrine/StarterContent/Particles/P_Fire.uasset`: our file is a real asset; our packages naming this path: 1 (KK_S2_Shrine/StarterContent/Blueprints/Blueprint_Effect_Fire.uasset)
- `KK_S2_Shrine/WINGS/Materials/S2_ceiling_wing.uasset`: our file is a real asset; our packages naming this path: 1 (KK_S2_Shrine/WINGS/Materials/M_Shrine_ceiling.uasset)

## Plugins / modules

- Klara enables, PussStage does not even via dependencies (declaration-proven, both .uproject files + engine .uplugin EnabledByDefault/Plugins deps): AjaMedia, AllToolsets, AppleProResMedia, BlackmagicMedia, Composite, DMXProtocol, HAPMedia, HDRIBackdrop, MediaFrameworkUtilities, MetaHumanLiveLink, OpenXR, PerformanceCaptureWorkflow, PixelStreaming, RemoteControl, SunPosition, Terminal, VirtualCamera, VirtualProductionUtilities, VirtualScouting, nDisplay
- `/Script/` modules referenced by the closure whose plugin PussStage does not enable (measured string + declaration): none
- Non-/Game content mounts referenced: `/Engine/` (209, engine content); `/Niagara/` (75, enabled in PussStage (direct, default or via dependency)); `/MetaHumanCharacter/` (7, enabled in PussStage (direct, default or via dependency)); `/ControlRig/` (6, enabled in PussStage (direct, default or via dependency)); `/InterchangeAssets/` (5, enabled in PussStage (direct, default or via dependency)); `/Interchange/` (3, enabled in PussStage (direct, default or via dependency)); `/ACLPlugin/` (2, enabled in PussStage (direct, default or via dependency)); `/Water/` (2, enabled in PussStage (direct, default or via dependency)); `/MetaHumanBodyTracker/` (2, enabled in PussStage (direct, default or via dependency)); `/HairStrands/` (2, enabled in PussStage (direct, default or via dependency)); `/MetaHumanSDK/` (1, enabled in PussStage (direct, default or via dependency)). Plus 0 pseudo-mounts with no plugin of that name (byte noise, or MetaHuman authoring paths like `/Lookdev_UHM/`, `/CharacterParts/` — inferred harmless, UNCLEAR without Unreal).

## Risks

- The scan is conservative; a few closure members may come only from metadata strings (inferred). Unreal's own reference viewer / migrate would be the authority.
- Level-bound possessables: copying the LS without its map leaves bindings unresolved; the bindings name actors by `PersistentLevel.<name>` in Klara's map, which will not exist in our Scene levels (inferred).
- COLLIDES files would overwrite ours on a blind copy; copy must skip or redirect them. 21 of 25 are our ObjectRedirectors (KK_S1_Animals -> /Game/Scenes/...) that our StageTest external actors and /Game/Scenes skeleton/physics assets still name: overwriting them with Klara's real assets would silently re-point those references to Klara's copies (inferred). 4 are real KK_S2_Shrine assets used by KK_Main_S2_Shrine / BPs (measured referrers).
- S2: LS_NEW_SHRINE is a 5 s, single-CineCamera shot (camera cut + transform + float tracks) bound into Klara's `/Game/Japanese_Alley/Maps/Japanese_Alley`, not into any KK_S2_Shrine level; it references no KK_S2_Shrine asset itself (measured). Everything else in its closure comes via that map (Japanese_Alley materials 0.6 GB, Turnips 0.2 GB).
- S1 names `/Game/KK_S1_Animals/LS_Animals` (no such file in Klara's Content; string-only, likely the pre-duplicate name) (measured absence; meaning inferred). LS_Children also names `/Game/KK_S1_Animals/L_Animals` alongside `/Game/L_KK_children` (measured); which bindings resolve there is UNCLEAR offline.
- Referrer counts for FName-suffixed names (e.g. `SM_Leaf_1`, stored as `SM_Leaf`+number) undercount (method limit).
- Klara's Content has no `__ExternalActors__` folder, so her maps are not OFPA; the map .umap holds its actors (measured absence).
