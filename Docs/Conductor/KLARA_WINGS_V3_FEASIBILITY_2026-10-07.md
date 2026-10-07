# Klara's wings → Flat V3: feasibility (7 Oct 2026, offline, read-only)

Gary's question: is it OK, or useful, to update Klara's wing assets to V3 and to **replace** them so the V3 versions sit
exactly where hers sit (same position, rotation, scale, outline, pivot, handedness and image registration)?
Gary clarified that "bring back" means *replace in place*.

Method: I read the files and grepped the binary .uasset/.umap files for ASCII strings. No Unreal session and no MCP
were used, and nothing in the project was edited. Tiers: **[decl]** a doc, source or config file says it;
**[bin]** a string found in a .uasset/.umap byte scan; **[meas]** a recorded run result or a file stat;
**[inf]** a conclusion I could not verify (the reason is given). Mesh dimensions inside her .uasset files **cannot be
read offline**. Every size below comes from a recorded probe of *our* sibling meshes, not of hers.

## 0. Answer

- **Is it OK?** Yes, with two conditions. The V3 copies go at **new paths**, and her assets are never overwritten.
  Her originals must stay byte-identical so that a re-delivery or a revert still works. [inf, from §3b]
- **Is a cm-exact replacement possible?** Only for a *declared subset* of properties. The base, the height and the
  inner (onstage) edge can be held to about 0.5–1.5 cm, the same way rzswap REMAP does it. The art plane can be held
  coincident. "Perfect" outline and image registration are **not achievable by construction**, because V3 changes
  three things:
  - the pivot convention (centre → backbone edge);
  - the depth: a 1.8 cm board plus a frame about 12 cm deep, against her symmetric slab of roughly 7–11 cm;
  - the silhouette: V3 smooths it to a jigsaw line with no feature under about 3 cm, and the art bleeds past it.

  [decl, §3a] Whether a residual of 1–3 cm is "consistent" is Gary's call.
- **Is it useful?** Low. "Plan A is video": her cinematic slot becomes a pre-rendered Media track. V3 would therefore
  only be seen in our intro and outro glide, in the dark, with her lights striking in. It would also only reach the
  video if her renders are made *after* the swap. [decl `REVEAL_PLAN.md:22,39`; inf]
- **Recommendation:** do not do it now. If Gary wants it, run the read-only probe in §5 first (one S1 pair), then
  pilot one pair.

## 1. Inventory

Placement is [bin]: the mesh path string appears in her map's name table. The **number of actors** per mesh comes
from the reveal DRY footprint [meas]. It is only available for S1 and S4.

| Scene / her map | Mesh (package) | Actors (labels) | Status of our file | Source art |
|---|---|---|---|---|
| S1 `KK_S1_Animals/L_Animals.umap` | `/Game/KK_S1_Animals/Wings/PNG/StaticMeshes/StaticMeshes/SM_L_Wing_2_Animals` | 5 (`SM_L_Wing_2_Animals2`–`6`) | **real asset now (276 694 B)**; it was an ObjectRedirector at census time | `L_Wing_2_Animals.png` |
| S1 | `…/SM_R__Wing_2_Animals` | 4 (`…2`–`5`) | real asset now (275 776 B) | `R._Wing_2_Animals.png` |
| S1 | `…/SM_Celing_Animals_Wing_Final` | 5 (`…Final4`–`8`) | real asset now (308 473 B) | `Celing_Animals_Wing_Final.png` |
| S1 | (labels `SM_L/R_Wing_1_Animals`) | 2, "zero bounds" | the umap names no `Wing_1` mesh path | — |
| S2 `Japanese_Alley/Maps/Japanese_Alley.umap` | `/Game/KK_S2_Shrine/NewShrine_wing/StaticMeshes/SM_S2_L_Wing_Shrine`, `SM_S2_R_Wing_Shrine`, `SM_S2_ceiling_wing`, `SM_MudTower_SeeThrough` | UNCLEAR (S2 has no reveal DRY) | real assets, NEW in the ingest | `S2_L/R_Wing_Shrine.png`, `S2_ceiling_wing.png` |
| S4 `L_KK_children.umap` | `/Game/L_K_Children/Assets/Wings/wings_fbx/SM_L_Children_Wing1`, `SM_L_Children_Wing2`, `SM_R_Children_Wing2`; MIs `Lacquer/MI_Wing1/Wing2/R_Wing2/WingEdge_LacqueredWood` | 6 (`SM_L_Children_Wing1`–`4`, `SM_R_Children_Wing2`–`3`); which mesh each uses is UNCLEAR | real assets, NEW | `L/R_Children_Wing*.png` |
| S6 `L_KK_Void.umap` | none | — | — | — |

Evidence for the table:

- **S1 placement** [bin]: grep of `Content/KK_S1_Animals/L_Animals.umap` shows six wing paths: the three meshes plus
  `M_Ceiling_Animals`, `M_L_2_Animals` and `M_R_2_Animals`.
- **S1 actor counts** [meas]: `KlaraIngest/klara_reveal_dry_S1.json`, `/facts/footprint/kept[7–9,21–29,36,49]`.
  The two "zero bounds" labels are at `excluded[9–10]`. That the `Wing_1` actors are empty is [inf]: the umap
  contains no `Wing_1` path string.
- **S1 file status** [meas]: before the ingest, the three S1 meshes and three materials were ObjectRedirectors to
  `/Game/Scenes/Wings/PNG/...` (`census_report.md:83-85,108-113`). Their sizes now equal Klara's byte counts, so
  `klara_copy.ps1` ran and took hers, per Gary's 7 Oct decision (`klara_copy.ps1:1`). The snapshot
  `D:\PussStageBackups\PreKlaraIngest-20261006-2208` exists.
- **S2 placement** [bin]: grep of `Japanese_Alley.umap` shows the four NewShrine_wing meshes, the
  `S2_L/R_Wing_Shrine_Mat` materials and `WINGS/Materials/M_Shrine_ceiling`. `KK_Main_S2_Shrine.umap`, dated
  25 Jul, refers to an older `WINGS/...` set. It is not in her copy list (`copy_list.txt`), so it is a pre-ingest
  map [meas].
- **S2 collision** [decl `census_report.md:89,117`]: `WINGS/Materials/S2_ceiling_wing` was a collision, and both
  sides of it were real assets.
- **S4 placement** [bin]: grep of `L_KK_children.umap`. The actor counts are [meas] from
  `klara_reveal_dry_S4.json` `/facts/footprint/kept[3–7,15]`.
- **S4 redirectors** [bin]: `Content/Assets/Wings/wings_fbx/SM_*_Children_Wing*` are 1 439-byte ObjectRedirectors to
  `/Game/L_K_Children/Assets/Wings/wings_fbx/...`.
- **S6** [bin]: grep of `L_KK_Void.umap` for `wing` found nothing.

**Our packages that reference her wing paths.** The ASCII grep covered `Content/InfinityStage`,
`Content/__ExternalActors__` and `Content/Stage`:

- 12 packages reference `/Game/KK_S1_Animals/Wings`, and **all of them are StageTest external actors** [bin].
  `our_referrers.json:66-93` lists them per asset [meas].
- 0 packages reference the S2 or S4 wing paths [bin].
- **Collision risk, already realised:** those StageTest actors once resolved through our redirectors to
  `/Game/Scenes/Wings/PNG/...`. They now load Klara's assets [inf: same path, and it is now a real asset].
  `census_report.md:129` predicted this.
- Is StageTest in the show? UNCLEAR. I found no StageTest string in `Content/InfinityStage/Dev/Maps/*.umap`.
- Method limit: UTF-16 strings and FName number-suffixed names were not searched in this pass.

**Her wings descend from ours** [bin]. The AssetImportData in each of her packages names its source:

| Her mesh | Source named in its AssetImportData |
|---|---|
| `SM_L_Wing_2_Animals` | `Downloads/drive-download-20260723…/SM_L_Wing_2_Animals.fbx` |
| `SM_L_Children_Wing2` | `Users/garyz/Desktop/Klara/Wings/SM_L_Children_Wing2.fbx` |
| `SM_S2_L_Wing_Shrine` | `PUSS_IN_BOOTS/2. Old Man and Shrine/Assets/SM_S2_L_Wing_Shrine.fbx` |

- Our siblings carry the same FBX names under `GZZ Studio Drive/.../Stage Materials/FBX/...`.
- Her materials use the Front/Back/Edge slot names of our legacy pipeline (for example
  `M_L_Wing_2_Animals_Front/Back/Edge`, `copy_list.txt:314-316`).
- So her meshes were most likely made by our legacy cutout pipeline [inf].
- Whether her geometry is identical to ours is UNCLEAR: these are separate imports with different byte counts.

## 2. What "update to V3" would mean

- **Source art is available** [meas].
  - The PNG originals are in `D:\PussStageArchive\Keep-20261003\Klara Scenes WIP\1. Animals by the lake\` (L/R Wing_2,
    Celing) and `...\2. Old Man and Shrine\` (S2 L/R, ceiling, Mainwing).
  - The same files are in `D:\PussStageBackups\FullSnapshot-20260925-1853\Klara Scenes WIP\`.
  - Group-B exports and relief maps are in `E:\PussStage\DerivedAssets\WingMateriality\SourceExports\GroupB\`
    (`L_Wing_2_Animals.png`, `L_Children_Wing2.png`, `S2_L_Wing_Shrine.png`).
  - **The Children wing PNGs were not found on disk.** The texture imports name `Users/garyz/Desktop/Klara/Wings/*.png`
    [bin], and the find had depth ≤7 on C:, D: and E:. There are UE texture assets
    (`L_K_Children/Assets/Wings/wings_fbx/L_Children_Wing1.uasset` etc.), so an export from UE is possible [inf].
- **Build:** `Tools/FlatV3/build_v3_flat.py` with `--art`/`--mask`, `--side L|R`, `--height-cm`, `--name`
  (`:57-110` [decl]). It produces four slots (Front, Flap, Timber, Edge) and LOD1 beyond ~15 m
  (`FlatV3Spec_2026-09-30.md:180-185`).
- **No V3 build of any of these images exists yet** [meas]: no file under `Content/Scenes/Wings/FlatV3` or
  `DerivedAssets/FlatV3` matches `Animals`, `Children_Wing` or `Wing_Shrine`. The FV3E slot only stop-gapped mips on
  our copies of these textures (`Saved/CodexFlatV3/slot_e_originals_FV3E-20261002-01/Scenes__Wings__AnimalsLake__*`).
- **Handedness:** L and R are *separate art* (`L_Wing_2_Animals.png` and `R._Wing_2_Animals.png`), not a mirrored
  pair [meas, file names]. V3 rules [decl `FlatV3Spec:115-119`]:
  - Front faces −X.
  - L extends +Y from its backbone, R extends −Y.
  - Image U runs +Y on both.
  - No `bFlipImageHorizontally`.

  `WingGenerationConventions.md` requires final handedness *before* any derived maps (AGENTS.md).
  The Interchange import negates Y (memory `tk-lateral-shift-frame-mirrored`, [meas] 6 Oct). Every placement check
  must therefore run in the **Unreal frame from live bounds**, never in the FBX frame.

## 3a. In-place replacement: what decides a cm-exact match

| Property | Hers (legacy pipeline) | V3 | Can it be matched? |
|---|---|---|---|
| Pivot / origin | centre of the silhouette's X extent (`blender_png_to_wing.py:378,393` [decl]). Our sibling `SM_L_Wing_2_Animals` spans Y −369.6…+372.6 [meas `CodexWingHandedness2/mesh_geometry.json:2`] | pole line × **backbone edge** × floor (`FlatV3Spec:111-113` [decl]) | Not by a mesh-only swap. The actor location must change by about half the width, or the V3 mesh must be built with a legacy-style pivot [inf] |
| Depth / art plane | symmetric extrude: `extrude = t/2` about the centre (`blender_png_to_wing.py:385` [decl]). Siblings are 10.68 / 8.95 / 7.46 cm in X [meas `mesh_geometry.json:2,1427,1788`], so the face is at about −t/2 | board front at X = −15 cm (`build_v3_flat.py:33` [decl]), board 1.8 cm, frame to about 12 cm (`FlatV3Spec:180-182`); flaps stand up to about 5 cm proud (`rzswap_core.py:500-503` [meas P06]) | Keep the **front art plane** coincident by offsetting the actor 15 − t/2 cm along the facing axis. The back face then sits about 1–5 cm further back [inf] |
| Height / base | built 10 m tall; scaled by the actor [decl `FlatV3Spec:20-24`] | built at final size, scale 1 [decl `:108-109`] | Build V3 at her *world* height so the actor scale becomes 1. **Non-uniform actor scale would squash the V3 frame and flaps** [inf]. Her actor scales are UNCLEAR (§5 reads them) |
| Outline | traced from the alpha, at pipeline trace resolution | smoothed jigsaw line, no feature under ~3 cm, art bleeds past it [decl `FlatV3Spec:105-106`] | Residual ≤ about 3 cm along the edge, by design [inf] |
| Image registration | planar UV of the PNG over its bounds | UV derived from the same PNG at the declared height | Close if the height and crop are equal. The FV3 skin (sheets, peel, halftone) **changes the picture itself** [decl `FlatV3Spec:124-135`] |
| Material look | her own MIs (S4 uses the Lacquer MIs; S1/S2 use pipeline Front/Back/Edge) | billboard skin, timber back | Her S4 lacquer MIs would be lost unless they are re-applied to the V3 Front slot. That is a creative call |

**How our own swaps hit "in place"** [decl `rzswap_core.py:486-507`, `swapkit/dry.py:98-123`]:

- REMAP holds the **inner (onstage) edge** from live Unreal bounds: `lateral_mode: "inner_edge"`, L inner = max Y,
  R inner = min Y.
- It holds the back face to ≤0.5 cm, the height to ≤1.5 cm and the width to ≤1.5 cm.
- It allows ≤6 cm of front growth.
- It refuses any side whose old transform is not plain `(0, y, 0)` or that has MaterialOverrides, FacingPolicy or a
  flip.
- It has run live: P02/P03/P06 `rzswap_apply_*_RZSW-20261007-*.json` [meas].

**The method transfers, but the tool does not:**

- rzswap and swapkit write **Show-asset cue panels** only: `SHOW_PATH`, `WRITTEN_PANEL_FIELDS` =
  Mesh/MaterialOverrides/LocalTransform/FacingPolicy/flip (`rzswap_core.py:63,79` [decl]).
- Her wings are plain `StaticMeshActor`s inside her .umap (`klara_reveal_dry_S*.json` classes [meas]). Her Content
  has no OFPA (`census_report.md:133`).
- The inner-edge maths (`lateral.inner_edge_local_y`) and the gates can be reused in a new actor-level tool. Its frame
  is actor-local, composed with her LevelTransform. That LevelTransform **changes whenever klara_reveal moves her
  level** (`klara_reveal.py:2450-2467`, remove + re-add [decl]).
- So an actor-local swap inside her level follows the level for free. A copy placed in *our* persistent level would
  have to follow the LevelTransform and would break on every reveal re-run [inf].

## 3b. Revert and re-delivery (secondary)

- **Where the swap persists.**
  - A swap has to be saved into her map, or applied at runtime.
  - `klara_reveal.py` APPLY *already* saves her map, after a .umap backup (`:2758-2766` [decl]). `L_Animals.umap`
    and `L_KK_children.umap` have mtimes of 7 Oct 10:40 and 09:50, matching the S1/S4 records [meas].
  - The memory rule "never save her levels" (`klara-streamed-levels-traps.md`) is therefore already overridden by a
    guarded path. A wing swap should reuse exactly that guard: an explicit her-maps allow-list, a backup, then
    `DIRTY_AFTER_SAVE`.
- **Revert:** record each actor (label, package path, StaticMesh, OverrideMaterials, actor and root-component
  transform) to JSON before the write. REVERT writes back only those fields, if the current value equals the swap's.
  This is the field-scoped pattern of 007acb9.
- **Re-delivery:**
  - `klara_copy.ps1:13` does `Copy-Item -Force` over `copy_list.txt`, which includes her .umap files (lines 21, 227,
    459). A re-ingest **silently clobbers** any swap saved into her maps, and the reveal edits too.
  - V3 assets at new paths (`/Game/Scenes/Wings/FlatV3/Klara/...`) survive.
  - Re-applying is deterministic if the record is keyed on map package + actor label + original mesh path, and REFUSES
    when her new delivery moved the actor (transform ≠ recorded).
  - Never edit her assets in place.

## 4. Usefulness

- **For:** V3 gives depth (frame, timber back, edge), flutter flaps, LOD1 and mips (it fixes the motion smudge of
  no-mip legacy textures, `FlatV3Spec:10-16`) [decl]. It would also match our passages' wings when the camera glides
  from the passage into her diorama [inf].
- **Against:**
  - Her cinematic is to become video (`REVEAL_PLAN.md:22`). In-engine V3 shows only during the dark intro and outro
    and the strike-in [decl/inf].
  - Her cameras, lights and lacquer MIs were tuned on her flat slabs. The billboard skin repaints her art.
  - Fourteen S1 and six S4 actors plus S2's set means a new actor-level tool, a pivot shift, and saves into her maps.
- **Visibility in our hangar framing:** UNCLEAR offline. It needs PIE stills at L, G0 and C (the reveal's own still
  set).
- **Look consistency with Klara's intent is Gary's and Klara's creative call, not an engineering one.**

## 5. Plan, if Gary says go (minimal risk)

**Step 0 — read-only probe, no saves.** One `ExecuteProjectPythonFile` script.

- For every StaticMeshActor in her three maps whose mesh path is in §1, it records:
  - label;
  - world and relative transform, including scale;
  - the LevelTransform;
  - the mesh path;
  - OverrideMaterials;
  - `StaticMesh.get_bounding_box()`;
  - the world AABB.
- It also writes the X/Y/Z extents of the mesh, the face plane and the inner edge in the actor frame, with
  `run=<id>` in the log markers.
- **+control:** her actor against its own mesh must give 0.000 cm on every edge and plane.
- **−control:** her L mesh scored in an R actor, and a copy offset by 10 cm, must both FAIL the ≤0.5 cm gates.
- Pre-register the prediction first: the centre pivot gives an edge delta of about half the width.

**Step 1 — offline build.** Build one S1 pair (L/R Wing_2_Animals) with `build_v3_flat.py`, at her measured world
height. Import it to a **new path**. Run the rzimport bounds gate.

**Step 2 — DRY.** Compute the actor transform that holds the inner edge, the base and the front art plane. Print the
residuals for the outline and the back face, plus a contact sheet. No writes.

**Step 3 — APPLY (one pair, S1).**

- Back up `Backups/PreKlaraWingV3-YYYYMMDD-HHMM` and the .umap.
- Write the record first.
- Set the mesh and location, and clear the scale to 1.
- Save her map, using klara_reveal's guarded allow-list.
- Read back, then run the world-edge probe with controls.
- Take PIE stills.

**Step 4 — REVERT** from the record. Prove it once on the pilot pair.

**Decisions for Gary (and Klara):**

1. Is V3 wanted in her dioramas at all, given that her cinematic becomes video?
2. Which residual is acceptable: the outline (≤3 cm by design) and the back-face shift (1–5 cm)? Which face must stay
   coincident: the art plane (recommended) or the back?
3. Skin: billboard, or her own art kept clean? And in S4, her lacquer MIs or the V3 timber/skin?
4. May our tools save her maps for this purpose? klara_reveal already does.
5. Re-delivery policy: does Klara's next delivery reset to hers (re-run the record), or does she adopt V3?
6. S2 is "untouched" by Gary's 7 Oct instruction. Is it out of scope here too?

## Searched and found nothing in

- `Content/Scenes/Wings/FlatV3/**` and `DerivedAssets/FlatV3/**` for V3 builds of Animals, Children or Shrine wings.
- C:, D: and E: (find, depth ≤7) for `*Children_Wing*.png`; only the Group-B relief exports of `L_Children_Wing2`
  were found.
- `L_KK_Void.umap` for any `wing` path.
- `Content/InfinityStage`, `Content/Stage` and non-StageTest `__ExternalActors__` (ASCII only) for references to
  her wing paths.
- `Docs/FlatV3Status.md`, `Docs/FlatV3Spec_2026-09-30.md` and `Docs/WingGenerationConventions.md` for "Klara",
  "KK_" and her wing names.
- rzswap and swapkit for any StaticMeshActor or level-actor write path. Both are Show-panel only.
- Her mesh .uasset binaries, for dimensions. These are not readable offline, so every size above comes from our
  sibling meshes.
