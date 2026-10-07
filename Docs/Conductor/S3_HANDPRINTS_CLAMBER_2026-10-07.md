# S3 hand prints: "clamber" layout over the set-B dunes (7 Oct 2026)

Gary (7 Oct, his words): dunes set B (~2.4 m at the walls) "seems fine, but prints can go up higher than only 20cm
more, since the implication should be that people are trying to clamber out desperately".

**Status: OFFLINE ONLY.** No Unreal MCP call was made, nothing was committed, the Show, the level and Content were not touched. The layout is data. Applying it needs the editor and two MCP calls, plus one revert of the live 449 prints (run order below).

Tiers: **[decl]** declaration-proven (a record, config or source we can read) · **[meas]** computed offline from files on disk, or a harness result · **[inf]** inferred, not verifiable offline (the reason is given).

## 1. What was built

All files are in `Saved/CodexFlatV3/handprints/clamber/`:

| File | Role |
|---|---|
| `hp_clamber_config.json` | Every knob, including seed 20261007 |
| `hp_clamber_layout.py` | Deterministic generator. It reuses the frame, exclusion and row helpers of `Tools/FlatV3/handprints/build_handprint_placement(_scramble).py` and does not change them |
| `placement_S03_clamber.json` | The table (schema `hp_placement/1`). sha256 `f0dd01f9d4bc2128ebdf62ba26499ae0f1f8d7b79b04884cdc7123a47e966620` |
| `hp_clamber_preview.py` → `previews/` | Wall elevations and the main-camera composite |
| `test_hp_clamber.py` → `test_hp_clamber_report.json` | Harness: **11/11 PASS** [meas] |
| `hp_place_clamber_dry.py` / `hp_place_clamber.py` and their `_request.json` | Wrappers that run the existing placer in a new mode |

**Placer edit (additive).** `Saved/CodexFlatV3/handprints/hp_place_decals.py` gains `HP_PLACE_MODE="clamber"`:

- `:64-65` the pin `CLAMBER_PLACEMENT_SHA256` and `CLAMBER_Z_CEILING_WORLD = 2880`;
- `:75-83` the branch: table `clamber/placement_S03_clamber.json`, the same tag `HP_S03`, the same label prefix, folder and `hp_place_record.json` as the full mode, and backup prefix `PreHPS03Clamber-`;
- `:228-234` a guard: the table's landed box must equal the walls_S03 box, except that its max z may rise to at most 2880 (the marble top).

The backup is at `hp_place_decals.py.bak-20261007-preclamber`. Harness test 11 proves that every line of the old placer survives, in order [meas]. The default and test modes are unchanged: the full-mode pin is still `c9fc3e…` (harness test 1). The existing suite `Tools/FlatV3/handprints/test_handprints.py` still passes **54/54**, the same as before the edit [meas, run before and after].

## 2. The layout (all heights are cm above the S3 floor top, i.e. world z + 5)

| Claim | Tier | Source |
|---|---|---|
| Totals: **752 decals: L 400, R 352** (old table: 449). L has 368 prints and 32 smears; R has 322 prints and 30 smears. They use 149 distinct v3 MIs, **all among the 178 that exist**. No new MI is needed. | meas | table `stats`; harness test 9 |
| **Floor rule.** Every decal's lowest ROTATED extent is ≥ the dune max + 20, and none is below. The dune max is the per-metre set-B maximum, taken over every metre the decal's own along-extent touches (±5 cm). The minimum margin over all 752 is 20.01. The same rule also holds against the built grid itself (`SM_S3_ShoreGround_grid_h.npy`), using the max over the 10 cm strip in front of the face, which the decal box reaches into. | meas | test 4 |
| **+ control:** one decal is lowered to 10 cm above the dune, and the check catches it. **− control:** the live scramble table, with its flat 160 cm line, has **21 prints that set B would bury** under the 20 cm rule. | meas | test 4 |
| The per-metre lists in `s3_shore_height_sets.json` set B equal the grid npy exactly (60/60 per wall, max diff 0.0). The table pins the height-sets sha256 and the grid_sha256 `0c97d7a6…`, which is the same as the FBX manifest. | meas | test 3, test 1 |
| **Follows the dune, not a flat line.** Over metres with ≥5 prints, the correlation between the lowest print and the dune is **L 0.75 / R 0.80**. The median gap is 39 / 35 cm. The lowest-print SD is 60 / 70 cm. **− control:** the scramble table gives 0.12 / 0.19 on the same measure. | meas | test 5 |
| **Density.** It is highest just above the sand and thins upward. By the highest extent in 150 cm bands (0-150, 150-300, 300-450, 450-600, 600-750+), L is 53 / 214 / 85 / 37 / 8 and R is 40 / 170 / 85 / 38 / 14. Event positions are weighted by the local dune height (`base 0.25 + (dune/max)^1.3`), so clusters gather where people stood on the dunes. | meas | test 6; config |
| **Top envelope** = clamp(dune line + 230 + 320·noise, 360, 720), where the noise is smooth seeded value noise with knots every 400 cm. Measured range: L 360–720, R 360–642. Non-outlier decals: 0 above the envelope. Decals above 500 cm: L 29, R 41. Above 700: L 5, R 8. | meas | test 6 (+ control: a decal raised 400 cm is caught) |
| **Outliers:** "desperate" climbs, L 2 and R 3, steps 35–65 cm. Their own ceilings are drawn from 780–900. The tallest extents are **827 (L) and 856 (R)**. They are steered away from the practical-lamp columns (±60 cm), because those columns would cut them off. | meas | test 6; config `outliers` |
| **Event kinds.** Each wall has 3–5 corner scrabbles in the last 30–450 cm before the backdrop corner, where the dunes are deepest. Decals by kind across both walls: climb 305, scrabble 213, pair 85, single 40, drag 40, corner scrabble 35, outlier climb 34. The kinds are: scrabble clusters of 4–8 overlapping prints right above the sand; alternating-hand climbs (18–38 cm steps, each with its own lean and diagonal); mirrored hand pairs 38–60 cm apart; singles; and drags. | meas | `Counter(event_kind)` |
| **Drags.** 39 point up (roll 180 ± 4–22°) and 17 run diagonal (180 ± 22–48°). The 6 drip smears stay within ±22° of upright, which is inside Gary's ±30° rule. 35 % come as 2–3 parallel finger/hand drags. | meas | test 10 |
| **Partial fingers: NOT available.** The atlas has no partial-finger element (122 elements: 81 adult prints, 9 child prints, 32 smears), and v3 MIs exist only for whole elements. Partial dropout is instead part of the grime stream's grease atlas (`T_S3MG_GreaseAtlas.png` R channel). New atlas cells would need new MIs, which was out of scope here. | decl | `atlas_job24d/atlas.json`; `S3_MARBLE_GRIME_PREP_2026-10-07.md` §2 |
| **Keep-outs.** The back wall gets **no prints**: the S3 Backdrop (the mural) covers it edge to edge, and the closed door sits behind it, so the back wall has **no marble**. Side-wall decals keep the walls' 150 cm end margin. The nearest box is **141.8 cm** from the backdrop plane, and the gate is ≥120. No decal is on any wall but L/R. **+ controls:** a decal moved next to the plane, and a decal relabelled onto a far wall, are both caught. | backdrop extent decl (`s3_shore_footprint.json` walls; `S3_MURAL_LOWER_2026-10-07.md` §1); keep-out meas (test 7) |
| **Exclusions.** Practicals (+30 cm), waves (slide envelope), backdrop and deck give 0 hits. The lamps skip many attempts: 116 on L and 37 on R. That is why the 3–7.6 m band thins in 7 columns per wall (see the amber boxes in the elevations). | meas | test 8; table `stats.excluded` |
| **Determinism.** Same seed + same inputs gives byte-identical output (rebuilt three times in the harness). seed+1 differs. The one-draw-per-statement lint is clean. The shipped table equals a fresh rebuild. | meas | tests 1, 2 |
| **Above z 600**, decals project onto the "Upper" marble tiles. Those tiles are coplanar with the base liner (same y face) and run to 2880. | decl | `s3_backwall_marble_record.json` spawned aabbs; `s3_backwall_marble.py:158-207` |
| That the Upper tiles **receive decals** is **inferred**: they use the same mesh and `MI_S3_Marble_Tiling_Daylight_{L,R}1..4`, and bReceivesDecals was never read. **Live read needed before APPLY.** | inf | — |

## 3. Previews (`Saved/CodexFlatV3/handprints/clamber/previews/`)

- `elev_L.png`, `elev_R.png`: each wall as seen from the room, 1 px = 1 cm, z 0–950. The background is Marble021 tiled at 150 cm. Overlays:
  - the set-B sand at the face;
  - the per-metre dune max (black);
  - the floor rule (red dashes);
  - the envelope (blue);
  - the lamps and waves;
  - the z 605 tile seam.

  `elev_both_small.png` shows both at 40 %.
- `composite_main_cam.png` and `composite_vs_still.png` are a **sketch, not a render** [meas geometry / inf look]:
  - Pose: the floathold still 0 pose (14421.973, 159250, 120), yaw 75.457, pitch −5.464, FOV 37.497, root (11421.97, 160000, −120).
  - The set-B heightfield is ray-marched and lambert-shaded.
  - Wall pixels come from the 17:32 live still. Its old prints are removed with a 75th-percentile filter, then the new decals are pasted in a flat dark-brown stain colour. The live OpacityGain and StainTint were not read.
  - Wave pixels are kept from the still.
- **Finding for Gary [meas]:** the main camera sees only the R wall at x 14281–15588, and only up to ≈ 2.9 m. **48 R decals fall in frame and 44 are visible**, against 60 in frame for the old table. The clamber above 3 m is **out of the main shot**. It reads only in wider or upward shots, or from the L-wall side. The dune bank on the R wall (metres 23–29, about 1.7–2.1 m) also fills the right third of the frame.

## 4. Knock-on effects (read before applying)

1. **`s3_marble_tiling_apply.py` hard-codes 449 HP_S03 decals.** See `HP_EXPECTED = 449` at `:66`, and the gates at `:384-385` and `:705-711` (`HP_COUNT`, `HP_DIGEST_CHANGED_SINCE_APPLY`). Once the clamber table is placed, that tool's verify/revert will FAIL until HP_EXPECTED and the digest are updated. That file is not ours, so it was not changed [decl].
2. **The grime bench (S3 marble grime, variant C) is keyed to the old labels.**
   - `s3mg_bench.py:192` and `s3mg_geometry.py` read `DerivedAssets/FlatV3/HandPrints/placement_S03.json`.
   - The 60 in-frame labels in `geometry.json` and the band anchor `HP_S03 R 0150` all refer to the scramble decals.

   After placing the clamber table, re-run `s3mg_geometry.py` against `clamber/placement_S03_clamber.json` and rebuild `s3mg_bench_plan.json` / the prespawn pool. **The layout itself stays compatible**: it uses the same atlas, the same `MI_HP_S03_v3_<element>_F<flip>` instances, the same `HP_S03 <wall> <nnnn>` labels, and DecalActors attached to the wall actors. The grease decals SNAP to their print decal, so they follow any layout [decl, `S3_MARBLE_GRIME_PREP` §7-8].
3. **`s3_backwall_marble.py`** (`:44`, `:61`, `:205-207`) refuses to plan tiles over decals above z 600. It only does this on a fresh APPLY. The tiles are already in the level (record `applied: true`), so nothing changes unless someone reverts and re-applies that tool [decl].
4. **Inputs that are another stream's live files:**
   - `s3_shore_height_sets.json` is uncommitted and modified in git status;
   - the exclusion probe is from 6 Oct, before the 7 Oct wave redesign.

   The table pins the dune sha256. If the dune pass or the waves change, re-run the generator, `test_hp_clamber.py`, and re-pin `CLAMBER_PLACEMENT_SHA256` [decl/inf].
5. **Live state not re-read here [inf]:**
   - that 449 HP_S03 decals are still saved (record `hp_place_record.json`, run 115927);
   - that the wall actors have not moved (the placer refuses `WALL_MOVED_SINCE_TABLE` anyway);
   - Upper-tile decal receipt;
   - that the practical lamps are still where the 6 Oct probe put them.

## 5. Run order (each step is one MCP call through `Saved/CodexMocap/mcp_request.py`; wait for the marker)

0. Offline: `python Saved/CodexFlatV3/handprints/clamber/test_hp_clamber.py` should give `HP_CLAMBER_TESTS|ran=11|fail=0`. Optionally run `python Tools/FlatV3/handprints/test_handprints.py`, which should give 54 OK.
1. Editor up, no PIE, clean census: `Saved/CodexFlatV3/handprints/hp_revert_decals_request.json` should give `HP_S03_REVERT_SUCCESS|run=..|removed=449|planned=449|saved=1|backup=Backups/PreHPS03Revert-…`. It removes the scramble decals, saves only the level, and archives `hp_place_record.json`.
2. `Saved/CodexFlatV3/handprints/clamber/hp_place_clamber_dry_request.json` should give `HP_S03_PLACE_DRY_RUN_OK|run=..|mode=clamber|count=752|mutated=0`. Any `HP_S03_PLACE_STOPPED|reason=…` stops the sequence. Expected possible reasons: `PLACEMENT_SHA256_MISMATCH`, `WALL_MOVED_SINCE_TABLE`, `MI_V3_NOT_CREATED`, `CLAMBER_BOX_…`.
3. `Saved/CodexFlatV3/handprints/clamber/hp_place_clamber_request.json` should give `HP_S03_PLACE_SUCCESS|run=..|mode=clamber|tag=HP_S03|count=752|saved=1|backup=Backups/PreHPS03Clamber-…`. The placer backs up the umap, writes the record before spawning, reads back every decal, refuses a save with ZZ_/TEMP actors present, saves only the current level, and asserts a clean census.
4. Take a still (fresh PIE, the conductor's call), plus a wider or upward shot of the walls, so Gary sees above 3 m.

**REVERT:**
- Send `hp_revert_decals_request.json` again. Its marker is `removed=752`, and it archives the record.
- To restore the old scramble table, then send `hp_place_decals_dry_request.json` → `hp_place_decals_request.json`. That is the full mode, still pinned to `c9fc3e…`.
- The umap snapshots are `Backups/PreHPS03Revert-*` and `Backups/PreHPS03Clamber-*`.

**Approval:** steps 1 and 3 are level writes. They are reversible and backed up. The layout is a look decision, and Gary's own words ask for it. Show these previews first.
