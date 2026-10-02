# P06 Flat V3 swap plan — beats 1-3 only

Authority: Gary approval in the conductor session, 2 October 2026.

## Scope and gates

- **[measured]** `Saved/CodexWingHandedness2/rows_dump.json` contains 55 P06
  occurrences at cue indices 217-271. Their indices, labels and ordinals are
  unique; the source does not contain cue GUIDs, so GUID uniqueness remains a
  live read-only preflight gate.
- **[declaration-proven]** Positions 1-32 are swapped. Positions 33-55 explicitly
  keep their current left, right and top panels because the fire, drape and
  monochrome work does not exist yet.
- **[declaration-proven]** Every swapped position below uses one matched L/R
  family. No painted art is mirrored, and no position mixes families.
- **[measured]** The three P06 art pairs and the three selected P02 industrial
  pairs have both L and R FBXs on disk. The BlenderTest scaffold and girder
  deliveries do not have true delivered L/R FBX pairs, so they are not placed.
- **[inferred]** The exact family rhythm below is a deterministic interpretation
  of Gary's approved three-beat arc; rendered pacing remains unproven.

Import rule: if all six selected industrial meshes already exist under
`/Game/Scenes/Wings/FlatV3/Passage02`, reuse that complete set. If none exists
there, import and use the complete set under `Passage06`. Any partial Passage02
set fails closed. Only the six used P06 art meshes and the six used industrial
meshes are admitted; the unused bronze-tree L_v1 is not imported.

All tops are `KEEP current`. The swap changes L/R only.

## Beat 1 — grand chinoiserie + bronze (positions 1-10)

| Position | Family | L asset | R asset | Top |
| ---: | --- | --- | --- | --- |
| 1 | grand_pavilion | SM_FlatV3_P06_grand_pavilion_L_v1 | SM_FlatV3_P06_grand_pavilion_R_v1 | KEEP current |
| 2 | chinoiserie_garden | SM_FlatV3_P06_chinoiserie_garden_L_v1 | SM_FlatV3_P06_chinoiserie_garden_R_v1 | KEEP current |
| 3 | grand_pavilion | SM_FlatV3_P06_grand_pavilion_L_v1 | SM_FlatV3_P06_grand_pavilion_R_v1 | KEEP current |
| 4 | bronze_tree | SM_FlatV3_P06_bronze_tree_L_v2 | SM_FlatV3_P06_bronze_tree_R_v1 | KEEP current |
| 5 | chinoiserie_garden | SM_FlatV3_P06_chinoiserie_garden_L_v1 | SM_FlatV3_P06_chinoiserie_garden_R_v1 | KEEP current |
| 6 | grand_pavilion | SM_FlatV3_P06_grand_pavilion_L_v1 | SM_FlatV3_P06_grand_pavilion_R_v1 | KEEP current |
| 7 | chinoiserie_garden | SM_FlatV3_P06_chinoiserie_garden_L_v1 | SM_FlatV3_P06_chinoiserie_garden_R_v1 | KEEP current |
| 8 | bronze_tree | SM_FlatV3_P06_bronze_tree_L_v2 | SM_FlatV3_P06_bronze_tree_R_v1 | KEEP current |
| 9 | grand_pavilion | SM_FlatV3_P06_grand_pavilion_L_v1 | SM_FlatV3_P06_grand_pavilion_R_v1 | KEEP current |
| 10 | chinoiserie_garden | SM_FlatV3_P06_chinoiserie_garden_L_v1 | SM_FlatV3_P06_chinoiserie_garden_R_v1 | KEEP current |

## Beat 2 — fence and shutter hoarding appears (positions 11-20)

No scaffold is placed in this round: every inspected BlenderTest scaffold
delivery lacks a delivered true L/R FBX pair. The available paired fence and
shutter families carry the structural intrusion without violating the pair rule.

| Position | Family | L asset | R asset | Top |
| ---: | --- | --- | --- | --- |
| 11 | grand_pavilion | SM_FlatV3_P06_grand_pavilion_L_v1 | SM_FlatV3_P06_grand_pavilion_R_v1 | KEEP current |
| 12 | fence_tarp | SM_FlatV3_P02_IND_FenceTarp_L | SM_FlatV3_P02_IND_FenceTarp_R | KEEP current |
| 13 | chinoiserie_garden | SM_FlatV3_P06_chinoiserie_garden_L_v1 | SM_FlatV3_P06_chinoiserie_garden_R_v1 | KEEP current |
| 14 | fence_open | SM_FlatV3_P02_IND_FenceOpen_L | SM_FlatV3_P02_IND_FenceOpen_R | KEEP current |
| 15 | grand_pavilion | SM_FlatV3_P06_grand_pavilion_L_v1 | SM_FlatV3_P06_grand_pavilion_R_v1 | KEEP current |
| 16 | roller_shutter | SM_FlatV3_P02_IND_RollerShutter_L | SM_FlatV3_P02_IND_RollerShutter_R | KEEP current |
| 17 | chinoiserie_garden | SM_FlatV3_P06_chinoiserie_garden_L_v1 | SM_FlatV3_P06_chinoiserie_garden_R_v1 | KEEP current |
| 18 | fence_tarp | SM_FlatV3_P02_IND_FenceTarp_L | SM_FlatV3_P02_IND_FenceTarp_R | KEEP current |
| 19 | bronze_tree | SM_FlatV3_P06_bronze_tree_L_v2 | SM_FlatV3_P06_bronze_tree_R_v1 | KEEP current |
| 20 | roller_shutter | SM_FlatV3_P02_IND_RollerShutter_L | SM_FlatV3_P02_IND_RollerShutter_R | KEEP current |

## Beat 3 — crumble / peel (positions 21-32)

The `PEEL` values are recorded as stepped intent in `p06_layout.json`. Applying
per-instance `PEEL` is Wing materiality's job and is deliberately not done by
this swapkit.

| Position | Family | L asset | R asset | Top |
| ---: | --- | --- | --- | --- |
| 21 | grand_pavilion | SM_FlatV3_P06_grand_pavilion_L_v1 | SM_FlatV3_P06_grand_pavilion_R_v1 | KEEP current |
| 22 | fence_open | SM_FlatV3_P02_IND_FenceOpen_L | SM_FlatV3_P02_IND_FenceOpen_R | KEEP current |
| 23 | chinoiserie_garden | SM_FlatV3_P06_chinoiserie_garden_L_v1 | SM_FlatV3_P06_chinoiserie_garden_R_v1 | KEEP current |
| 24 | fence_tarp | SM_FlatV3_P02_IND_FenceTarp_L | SM_FlatV3_P02_IND_FenceTarp_R | KEEP current |
| 25 | roller_shutter | SM_FlatV3_P02_IND_RollerShutter_L | SM_FlatV3_P02_IND_RollerShutter_R | KEEP current |
| 26 | fence_open | SM_FlatV3_P02_IND_FenceOpen_L | SM_FlatV3_P02_IND_FenceOpen_R | KEEP current |
| 27 | bronze_tree | SM_FlatV3_P06_bronze_tree_L_v2 | SM_FlatV3_P06_bronze_tree_R_v1 | KEEP current |
| 28 | fence_tarp | SM_FlatV3_P02_IND_FenceTarp_L | SM_FlatV3_P02_IND_FenceTarp_R | KEEP current |
| 29 | roller_shutter | SM_FlatV3_P02_IND_RollerShutter_L | SM_FlatV3_P02_IND_RollerShutter_R | KEEP current |
| 30 | fence_open | SM_FlatV3_P02_IND_FenceOpen_L | SM_FlatV3_P02_IND_FenceOpen_R | KEEP current |
| 31 | fence_tarp | SM_FlatV3_P02_IND_FenceTarp_L | SM_FlatV3_P02_IND_FenceTarp_R | KEEP current |
| 32 | roller_shutter | SM_FlatV3_P02_IND_RollerShutter_L | SM_FlatV3_P02_IND_RollerShutter_R | KEEP current |

## Explicit keep block

Positions **33-55: KEEP current L, R and top**. No fire, drape, monochrome,
burning-curtain or darkness proposal from the earlier draft is executed.

## Not placed — needs a true pair

| Family / asset | Status |
| --- | --- |
| ScaffoldBay | Needs delivered L and R FBXs |
| SM_FlatV3_P06_ChainLinkFence_L | Needs R |
| SM_FlatV3_P06_RollerShutterFrame_L | Needs R |
| SM_FlatV3_P06_GirderColumn_L | Needs R |
| SM_FlatV3_P06_GirderBent_L | Needs R |
| SM_FlatV3_P06_GirderBroken_L | Needs R |
| SM_FlatV3_P06_CableStay_L | Needs R |
| SM_FlatV3_P06_StonePier_L | Needs R |

The BambooScaffold, SteelScaffold, CoveredPillar and GauzeLattice sources named
in `KEPT_PICKS.json` have no Flat V3 FBX builds under the overnight `Kept`
output, so they are also excluded from this Flat V3 swap.
