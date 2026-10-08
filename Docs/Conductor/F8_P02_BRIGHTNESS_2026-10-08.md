# F8: why P02 is "overwhelmingly bright" (offline reconstruction, 8 Oct 2026)

Gary (8 Oct, GARY_FINISHING_NOTES_2026-10-08.md row F8): "Passage 2 is overwhelmingly bright right now, way too
bright. I'm not sure if lighting doubled up there or something else happened."

**Scope.** This was a read-only offline pass. Unreal and MCP were not run, no existing file was edited, nothing was
applied or committed, and nothing was rendered. The numbers are computed from saved records.

**Proof tiers, per claim** (AGENTS.md):

- **[decl]**: a header or source line.
- **[meas-rec]**: read from a saved record, report, stills manifest or log, or computed offline from one.
- **[inf]**: inferred, with the reason.

Nothing here is binary-proven.

**Time zone.** Run ids and mtimes are local time (UTC-4); log stamps are UTC. Evidence [meas-rec]:
`PSTILLS-P02-20261008-223703` has `started_utc` 22:37 and file mtime 18:37.

---

## 1. Summary

1. **No row-level double-up [meas-rec].** P02 has 132 enabled lights in 23 bays.
   - No duplicate GUIDs, no slot lit twice in a bay, no two enabled lights within 5 cm of each other.
   - All 138 pre-score lights stay disabled.
   - No REVERT left extra rows: row counts are identical across every before/after pair read.
2. **No light was multiplied twice [meas-rec].**
   - The two p02_brighten REVERTs were exact (`revert_drifts: []`, `saved: true`). The pre-APPLY Show backups of
     APPLY1 and APPLY2 are byte-identical (sha256 `664aad43…`).
   - APPLY3's "before" intensities equal APPLY1's and APPLY2's for every shared row.
   - All 165 APPLY3 after-values are still in the latest full snapshot: the Meshy swap, 7 Oct 08:26.
3. **What *did* double is how much light is on near the camera.** APPLY3 (`20261007-025331`, the one in force) put two
   boosts on the same 57 rows:
   - **Intensity set** at APPLY2's levels: practicals 800 lm, tops ×4 to 300-800 cd.
   - **Drama set**: strike 650 → 2500 cm, DECAY/EXTINGUISH → HOLD.

   Each boost alone adds about 30%. Together they multiply. **Proxy [meas-rec, offline]:** colour-weighted flux lit
   within ±30 m of the camera rose **×2.2 over the passage and ×3.5 in the second half**. P02 now carries 2.5× P01's
   local flux; before the brighten it carried about P01's.
4. **The brightest frames are the first-half BEAM_R beams [meas-rec].**
   - There are 12 rows of 6160-8100 cd, volumetric scattering 2.5-6.0, inner cones hand-widened to 6°/12°.
   - They give 52% of P02's haze load from 12 lamps. Stills at the beam bays read luma 110-116, and have read about
     100-116 since 5 Oct.
   - They come from the 5 Oct a.m. "already more broken" score. Gary's 5 Oct relight with no L/R beams **never
     landed**: the 6 Oct 02:21 scores REVERT stopped on drift, and rescoring was then held.
5. **No exposure or post-process change for P02 in any record [meas-rec, searched].**
   - The P02 fog bench's exposure lock was PIE-only and restored.
   - Klara's S2 PPV is keyed to S2 frames [104,376] only.
6. **Editor logs cannot confirm the 5-7 Oct APPLY/REVERT markers.** Only 8 Oct logs remain (from 09:22 UTC), with 0
   hits [searched]. The applied state is confirmed instead by record status `saved_readback_verified`, report `ok`
   and `saved`, and the backup sha chain [meas-rec].
7. **Ranked causes** (§7):
   - (1) p02_brighten APPLY3, both boosts stacked on the same rows;
   - (2) the stale beam score;
   - (3) changes made after the last measured stills (7 Oct 06:53 UTC). The P02 Car Light at 9000 cd peak is the
     most likely of these; the Meshy can lenses, the 20 realism wings and a Klara alley visibility leak follow.

   Each has a reversible fix that needs no code.

---

## 2. Timeline of everything that touched P02 lights or light bodies since 5 Oct

| Local time | Run | Tool / op | What it did to P02 | Effect in force now? | Evidence |
|---|---|---|---|---|---|
| 5 Oct 02:50 | 20261005-025042 | lighting_scores APPLY (spec sha `501f3183`) | first P02 score | **No.** Reverted 09:07 (`.reverted-20261005-090713`) | [meas-rec] record |
| 5 Oct 09:08 | 20261005-090808 | lighting_scores APPLY (spec sha `4045a628` = `lighting_scores.json.bak-20261005-preP02relight`, "already more broken") | 131 score lights + 46 bodies; 115 existing lights disabled; **BEAM_R 9000 cd × level** on bays 1-13 | **Yes** (record `saved_readback_verified`; never reverted) | [meas-rec] `lighting_scores_record_P02.json` `scores_sha256`, `plan.existing_lights_disabled` 115 |
| 5 Oct 09:12 | 20261005-091239 | rig_lamp_drop APPLY | TOP_L/R z 1180 → 1052 (transforms only) | Reverted 6 Oct 02:20, re-APPLY 6 Oct 02:22 (`20261006-022250`), **yes** | [meas-rec] diff of `before/after_target_rows`: 33 transform fields, 0 intensity |
| 5 Oct 09:23 | UPT-20261005-092351 | underpass tubes, Structure 02 | tubes stations 11-18 with rect tube lights | yes | [meas-rec] `underpass_tubes_record_02.json` |
| 5 Oct 09:24 | CAR-20261005-092430 | place_p02_car_light (**level actor**, not Show) | SweepLight peak **9000 cd**, cast shadows, every 11 ± 4 s | yes; re-placed by straighten 7 Oct 01:56. No later intensity record [searched] | [meas-rec] record; "too bright as placed … try ~2500" `DIRECTING_BY_HAND_GUIDE_2026-10-05.md:323` |
| 5 Oct ~15:10 | – | Gary's relight questionnaire → `lighting_scores.json` P02 rewritten (no BEAM_R, tops from above) | spec only | **Never applied** (see 6 Oct 02:21) | [meas-rec] current spec sha `2280f1b7`; P02 variants have `drop_slots: ["BEAM_R", …]` |
| 5-6 Oct | – | hand edits (inferred Gary) on 12 P02 lights | BEAM_R colour; **inner cone 2→6 (THEATRICAL), 4→12 (LURID/FAILING)**; no intensity edits | yes | [meas-rec] `LIGHTING_DRIFT_2026-10-06.md` §P02 (12 colour + 10 cone fields); hand-edit attribution [inf] |
| 6 Oct 02:21 | 20261006-022105 | lighting_scores **REVERT** (for the relight re-apply) | **stopped**: `REVERT_CURRENT_STATE_DRIFT|cue=P02 Wing 001`, `ok: false` | nothing changed | [meas-rec] `lighting_scores_report_P02.json`; `GARY_PIE_NOTES_2026-10-06_overnight.md:67-68` "rescoring HELD" |
| 6 Oct 02:23 | RTE-20261006-022318 | rig tubes everywhere | Structure 02: `all_rows_light` (only P02); glow 0.15, blink 20% | yes | [meas-rec] record args |
| 6 Oct 22:35 | TT-20261006-223555 | tubes tweak (all six) | glow ×4, tube light ×0.3 (375 → ~112 lm, P02 45 lights) | yes [inf: record has no after/status field] | [meas-rec] record |
| 6 Oct 22:38 | 20261006-223825 | p02_rig_pattern APPLY | **transforms only** on 121 rows, copied from P01. BEAM_R moved (−150, ±1250, 140) → (−611..−502, ±954..1270, 134..379), aim from nearly lateral to about 30° down-route | yes | [meas-rec] diff `before/after_cue_rows`: only `relative_transform` fields |
| 7 Oct 01:55 / 02:10 | P02STR / RETIME-20261007-021031 | straighten; retime 180 → 47.52 s | route and timing; no light row values | yes | [meas-rec] `MORNING_SUMMARY_2026-10-07_overnight.md:17` |
| 7 Oct 02:25 | 20261007-022538 | **p02_brighten APPLY1** (schema 1) | 26 intensity targets: practical floor 120 lm, tops ×2 (60-200 cd) | reverted 02:27 (`drifts []`, saved) | [meas-rec] |
| 7 Oct 02:28 | 20261007-022814 | **p02_brighten APPLY2** (schema 1) | 32 intensity targets: **practical floor 800 lm, tops ×4 (300-800 cd)** | reverted 02:49 (`drifts []`, saved). Stills: "no measurable effect" (lamps unstruck) | [meas-rec] stills `brighten2` = `retimed` lumas |
| 7 Oct 02:41 | GV3A-20261007-024125 | girders v3 | Structure 02 hanging lines 35 → 50 (cables, not lights) | yes | [meas-rec] `MORNING_SUMMARY_2026-10-07_overnight.md` |
| 7 Oct 02:46 | 20261007-024628 | dead_bulbs_warm APPLY | 18 P02 rows: 10 first-half dead bulbs **0 → 40 lm** + warm colour; 8 B12-B19 rows **colour only**. At that moment APPLY2 had those 8 at 800 lm, so the tool classed them as lit | yes | [meas-rec] `after_live`, `p02_brighten_overlap` |
| 7 Oct 02:53 | 20261007-025331 | **p02_brighten APPLY3** (schema 2), args = APPLY2 levels + drama | **165 fields on 57 rows:** 32 intensities (19 practicals → 800 lm, 13 tops → 300 cd); strike → 2500 cm and ramp 600 on 57; 19 after_pass → HOLD; BEAM_R skipped | **yes** (`saved_readback_verified`; still matches the 08:26 snapshot) | [meas-rec] record; stills `strike`: 0.6 luma 3.2 → 29.1, 0.8: 0.0 → 5.1 |
| 7 Oct 08:14 / 08:25 / 08:26 | meshy_swap P02 APPLY / REVERT / APPLY | 23 PROP bodies → Meshy bulbs ×3.2; Structure 02 cans → `SM_Lantern_ParCan` (132, lens MI emissive `Intensity` 0.6) | **no LIGHT row changed** (diff: only PROP mesh + transform) | yes | [meas-rec] swap records; `meshy_import_record.json` MI scalars |
| 7 Oct 10:33 | RZSW-20261007-103331 | rzswap P02 (W&T) | 20 wing panels → "realism" FlatV3 meshes | yes; unmeasured for brightness | [meas-rec] apply record |
| 7 Oct 10:39, 8 Oct 18:31 | S2HOLD | s4_hangar_hold scene 2 | S2 hangar transforms, S2 frames 775-3891 only | S2 only | [meas-rec] |
| 8 Oct 05:11 | 20261008-051137 | p03_lighting_as_p01 | P03 only (P02 appears only in its ack list) | – | [meas-rec] |
| 8 Oct 18:23 | KLARAHOOK-S2-APPLYSEQ-20261008-1845 | Klara S2 hook-in | her S2 lights/PPV/fog keyed in S2 [104,376]; Japanese_Alley visible S2 [104,3891]. Record: "p02: hidden: streaming level initially_visible=False" | S2 only (claimed) | [meas-rec] `klara_hookin_seq_record_S2.json`, `klara_hookin_s2_dry.json` |
| 8 Oct 18:37 | PSTILLS-P02-…-p02end | stills, P02 0.85-1.0 | luma 4.3 / 16.8 / 15.3 / 16.9 (same as 7 Oct 0.98: 13.4) | – | [meas-rec] manifest |

**Not touching P02 lights** [meas-rec]: the fixtures follow/scale/relocate tools (nothing applied, per
`P4_FIXTURES_DELIVERY_2026-10-08.md`), the P02 fog bench (PIE-only, restored, non-saving), and the beam texture bench
(non-saving).

**Logs.** `Saved/Logs/PussStage*.log` covers only 8 Oct 09:22-23:23 UTC. A grep for P02BRIGHTEN, BRIGHTEN,
LIGHTING_SCORES, MESHY, DEADBULB, RIG_LAMP, RIGLAMP, FIXFOLLOW, P03ASP01 and RIG_PATTERN found none of these tools'
markers. The only hits were unrelated "Exposure"/"PostProcess" config lines. **UNCLEAR from logs.** Applied state is
taken from records as listed.

---

## 3. P02 now, per bay (latest full snapshot: `meshy_swap_record_P02.json` `after_rows`, 7 Oct 08:26)

Units: spots in **candelas** (peak), points in **lumens** (total) [meas-rec, row `intensity_units`]. The two are not
added together here. "was" is the value before p02_brighten, from `p02_brighten_record.json` `plan.targets[].before`.

| Bay | Cue | Enabled lights | Σ cd (spots) | Σ lm (points) | Σ lm before brighten | strike 2500/HOLD rows |
|---|---|---|---|---|---|---|
| B01 | 001 | 7 | 7821 | 1030 | 1030 | 0 |
| B02 | 002 | 7 | 8730 | 1030 | 1030 | 0 |
| B03 | 004 | 7 | 7386 | 975 | 975 | 0 |
| B04 | 005 | 7 | 8245 | 975 | 975 | 0 |
| B05 | 006 | 7 | 6952 | 920 | 920 | 0 |
| B06 | 007 | 2 | 0 | 160 | 160 | 0 |
| B07 | 008 | 7 | 7821 | 1030 | 1030 | 0 |
| B08 | 009 | 7 | 8730 | 1030 | 1030 | 0 |
| B09 | 010 | 7 | 7386 | 975 | 975 | 0 |
| B10 | 011 | 7 | 8245 | 975 | 975 | 0 |
| B11 | 012 | 7 | 6952 | 920 | 920 | 0 |
| B12 | 013 | 7 | 8760 (was 8245) | 1735 | 935 | 6 |
| B13 | 014 | 7 | 7704 (was 7178) | 1614 | 814 | 6 |
| B14 | 003 | 6 | 978 (was 441) | 1600 | 693 | 6 |
| B15 | 015 | 5 | 612 (was 343) | 1600 | 572 | 5 |
| B16 | 016 | 4 | 246 | 1600 | 451 | 4 |
| B17 | 017 | 4 | 180 | 1600 | 330 | 4 |
| B18 | 018 | 3 | 91 | 1600 | 209 | 3 |
| B19 | 019 | 4 | 1777 | 1600 | 88 | 4 |
| B20 | 020 | 6 | 1365 (was 765) | 1760 | 960 | 6 |
| B21 | 021 | 6 | 1461 (was 861) | 1880 | 1080 | 6 |
| B22 | 022 | 2 | 0 | 1600 | 160 | 2 |
| B23 | 023 | 6 | 1556 (was 956) | 2000 | 1200 | 6 |
| **Σ** | | **132** | **102999** (was 99352) | **30209** | **17512** | |

**Comparisons:**

- **"After lighting_scores only"** (5 Oct 09:08) has the same intensities as "before brighten": Σ 99,352 cd and
  17,512 lm. The drift report lists no intensity hand edits for P02.
- Drama then was strike 650 cm on every SCORE lamp, with DECAY/EXTINGUISH on B15-B19 (19 rows).
- The colours and inner cones were the score's: narrower beams, before the 5-6 Oct hand edits [meas-rec].

---

## 4. P02 against P01, P03 and P04 (computed the same way)

**Static sums** (enabled LIGHT rows, latest full snapshot per passage = Meshy swap `after_rows`, 7 Oct 08:2x)
[meas-rec]:

| Passage | Bays | Enabled lights | Σ cd (spots) | Σ lm (points) | cd + lm/4π per bay | Route |
|---|---|---|---|---|---|---|
| P01 | 48 | 284 | 121,072 | 40,556 | 2,590 | 28,784 cm |
| **P02** | 23 | 132 | **102,999** | **30,209** | **4,583** | 11,858 cm |
| P03 | 21 | 103 | 14,686 | 18,773 | 770 | – |
| P04 | 15 | 83 | 52,342 | 11,070 | 3,548 | – |

- **P03** was relit on 8 Oct (`p03_lighting_as_p01_record.json`: 286 lights removed, 377 added). That record holds no
  intensity values, so the P03 row is **stale** and was not recomputed [meas-rec: searched the record's keys].
- **lm/4π** is the point-light candela equivalent [inf: isotropic point; header `LocalLightComponent.h:24` defines cd
  as peak intensity and lm as flux].

**Lit near the camera** [meas-rec, offline simulation]. This is what the camera actually sees, with drama evaluated.

- **Method:**
  - Each lamp's route position = its wing distance + `relative_transform.x`. P02 wing distances come from
    `p02_brighten_record.json` `plan.bays`; P01 from `p01_note_lamps_record.json` `plan.route.wings`.
  - Lamp level comes from a Python port of `EvaluateStrike` (`InfinityStageLightDrama.cpp:24-60`, [decl]): smoothstep
    ramp, then HOLD / DECAY / EXTINGUISH. Stutter and flash are ignored [inf].
  - Every lamp within −30 m … +30 m of the camera is summed, sampling every 250 cm.
- **Metrics:**
  - *cd-eq* = cd, or lm/4π.
  - *flux* = colour-luminance × (lm for points; cd × cone solid angle at the mean of the inner and outer half-angles
    for spots).
  - *haze* = flux × `volumetric_scattering_intensity`.
  - These are proxies, not rendered light [inf]: no attenuation, IES, light function, Lumen, fog density or exposure.

| Window mean (first half / second half) | cd-eq | flux | haze |
|---|---|---|---|
| **P02 now** | 31,465 (43,714 / 19,217) | **10,567 (7,432 / 13,703)** | **5,196 (5,903 / 4,490)** |
| P02 before p02_brighten | 28,712 (42,397 / 15,027) | 4,812 (5,747 / 3,877) | 3,655 (5,403 / 1,907) |
| P02 intensity set only | – | 6,593 | 4,104 |
| P02 drama set only | – | 6,109 | 4,047 |
| P02 with APPLY1 levels (120 lm, tops ×2) + drama | – | 6,632 | – |
| P02 now, BEAM_R disabled | 7,247 | 9,644 | 2,798 |
| **P01 now** | 16,524 | 4,205 | 2,054 |

**Reading** [inf, from the proxies]:

- The brighten's two sets compound to ×2.2 flux (×3.5 in the second half).
- BEAM_R dominates cd and haze but not flux. The beams are narrow, so they read as shafts and fog glow, not fill.
- P02 is about 2.5× P01 in local flux and haze. Before the brighten it was 1.1-1.8×.

**Measured on screen** (`PassageStills/PSTILLS-P02-*` manifests, mean luma) [meas-rec]:

| Stills | 0.02 | 0.2 | 0.4 | 0.6 | 0.8 | 0.98 |
|---|---|---|---|---|---|---|
| 7 Oct 06:11 UTC `retimed` (before brighten) | 114.6 | 9.4 | 110.5 | 3.3 | 0.0 | 13.3 |
| 7 Oct 06:28 UTC `brighten2` (APPLY2, intensity only) | 114.7 | 9.0 | 110.6 | 3.2 | 0.0 | 13.3 |
| 7 Oct 06:53 UTC `strike` (APPLY3, in force) | 114.6 | 8.6 | 115.9 | **29.1** | **5.1** | 13.4 |

- 5 Oct `scores` stills were already 83-103 at 0.1/0.7.
- 8 Oct `p02end`: 0.85-1.0 at 4.3-16.9.
- **[inf]** 0.02 and 0.4 are beam bays: B01/B02 and B10, the green LURID_POP beam.
- **Nothing has measured 0.02-0.8 since 7 Oct 06:53 UTC.** Everything applied after that is unmeasured.

---

## 5. Double-application checks

| Check | Result | Tier |
|---|---|---|
| Same light GUID twice | none (P01-P04) | [meas-rec] |
| Two enabled rows for one slot (`B## role`) in a bay | none | [meas-rec] |
| Two enabled lights within ~5 cm in one cue | none | [meas-rec] |
| Pre-score lights still enabled beside the score | none. 138 disabled LIGHT rows; enabled = 131 score + 1 retained Blink Spot = 132 = `light_fixture_count` + `retained` | [meas-rec] |
| A REVERT left extra rows | none. Meshy before/after row counts identical; brighten writes no rows (by design and by record) | [meas-rec] |
| A light boosted twice from a boosted base (×2 then ×4) | **no**. APPLY3 `before` = APPLY1/APPLY2 `before` for every shared intensity (0 mismatches). REVERTs `revert_drifts: []`. APPLY1/APPLY2 pre-backups byte-identical (`664aad43…`) | [meas-rec] |
| Same rows boosted by two tools | **yes, but not multiplicatively.** 8 B12-B19 PRACTICAL_BULB_DEAD rows: brighten 0 → 800 lm, plus dead_bulbs_warm colour/temperature. 10 B01-B11 dead bulbs: dead_bulbs_warm 0 → 40 lm only | [meas-rec] |
| Same rows boosted twice by one tool | **yes.** APPLY3 sets intensity (×4 levels chosen while the lamps were invisible) **and** extends their lit range (strike 2500/HOLD) on the same 57 rows | [meas-rec] |
| Exposure / post-process change for P02 | **none found.** Searched every JSON under `Saved/CodexConductor` newer than 4 Oct for `exposure`, `post_process`, `PostProcess` (hits: light-row field names, other passages' atmos, Klara S1/S2/S4/S6, benches). Fog bench D (exposure lock) is PIE-only and restored (`restore_scrub` SUCCEEDED). Klara S2 PPV is S2 [104,376]. Auto-exposure state cannot be read offline | [meas-rec] + UNCLEAR (live PPV) |

---

## 6. Things that would add light but are not Show rows (not in the sums)

| Source | Value | Tier |
|---|---|---|
| P02 Car Light (SweepLight, level) | 9000 cd peak, 3200 cm, cast shadows. Stills spiked to luma 137/145 on 5 Oct (`tubes_car` 0.55/0.63) | [meas-rec] |
| Structure 02 tube rect lights | 45 lights, 375 lm → ~112 lm after the ×0.3 tweak (≈5 klm total; P01 has 44) | [meas-rec] counts; tweak applied [inf] |
| Structure 02 cans | 132 `SM_Lantern_ParCan`, lens MI emissive `Intensity` 0.6 | [meas-rec]; on-screen effect [inf, small] |
| 23 Meshy bulb bodies ×3.2 | emissive glass | [meas-rec]; effect [inf] |
| Klara `Japanese_Alley` (198 actors on the P02 route per memory) | record says hidden in P02 | [meas-rec] claim; PIE state UNCLEAR |

---

## 7. Ranked causes and the smallest reversible fix for each

### 1. p02_brighten APPLY3 stacked two boosts on the same rows (the "doubling")

**Rows.** All 57 in `p02_brighten_record.json` (run 20261007-025331), bays B12-B23:

- 8 × `P02 SCORE B12…B19 P02_FAILING_STAGE PRACTICAL_BULB_DEAD`: 0 → **800 lm**. The dead-bulb design is 18-40 lm
  (`lighting_scores.json` `dim_bulbs.lumens` 18; dead_bulbs_warm floor 40).
- 6 × `PRACTICAL_CLAMP` B14-B19: 88-693 → 800 lm.
- 3 × `B20/21/23 P02_MYSTIC PRACTICAL_R`: 0 → 800 lm.
- `B22 GAP PRACTICAL_DEAD`: 0 → 800 lm. `B22 GAP PRACTICAL_GLIMMER`: 160 → 800 lm.
- 13 tops: B12-B15 25-51 cd and B20-B23 0 cd → 300 cd.
- Plus strike 2500 / ramp 600 on all 57 and HOLD on 19.

**Evidence.**

- [meas-rec] stills: 0.6 luma 3 → 29, 0.8: 0 → 5.
- [meas-rec, offline proxy] window flux ×2.2 overall, ×3.5 second half; the intensity set and the drama set each add
  about 30% alone. APPLY2's levels (800 lm / ×4) were chosen after APPLY1 showed "no measurable effect", which was
  the drama gating, not the level (p02_brighten.py docstring, schema 2 note).
- **[inf]** this is the change most likely to read as "doubled" against Gary's earlier view.

**Smallest reversible fix (no code).**

1. `p02_brighten` REVERT. The tool exists, and both earlier REVERTs were exact.
2. Then DRY → APPLY with only the args changed: `practical_floor` 120, `top_scale` 2.0, `top_floor_cd` 60,
   `top_max_cd` 200 (APPLY1's levels), keeping `drama` true.

- Proxy: flux 10,567 → 6,632 (−37%), and the second half stays lit.
- Gentler options: drop `PRACTICAL_BULB_DEAD` from the intensity set (leave them at the dead-bulb glow), or
  `drama: false`.
- Record, backup, narrow save and read-back as the tool already does. `ack_records` must include
  dead_bulbs_warm_record.

### 2. The first-half beams: a stale score Gary had already rejected, widened and re-aimed

**Rows.** 12 × `P02 SCORE B01…B13 … BEAM_R` (not B06):

- THEATRICAL B01/B03/B05/B07/B09/B11: 6160-6930 cd, cone 6/7°, vol 6.0.
- LURID_POP B02/B04/B08/B10: 7650-8100 cd, cone **12/14°**, vol 2.5, green on B02/B04/B10, dark green on B08.
- FAILING_STAGE B12/B13: 6660-7650 cd, cone 4/14°, vol 2.5.

They come from the 5 Oct 09:08 score (`lighting_scores_record_P02.json`, spec sha `4045a628`).

**Evidence.**

- [meas-rec] They are 52% of P02's haze load (8,407 of 16,314) from 12 of 132 lamps. A LURID beam carries about 10-20×
  the flux of a P01 BEAM_R (P01: 2000-4500 cd, cone 2/7°).
- [meas-rec] Disabling them in the proxy halves haze (5,196 → 2,798).
- [meas-rec] Stills at the beam bays read luma 110-116.
- [meas-rec] Gary already named these "a foggy blur across the whole screen" on 5 Oct, and the replacement score
  (no BEAM_R) is in `lighting_scores.json` but was never applied: REVERT drift 6 Oct 02:21, rescoring HELD for the
  hand-edit decisions in `LIGHTING_DRIFT_2026-10-06.md`.
- [meas-rec] The 6 Oct rig pattern turned them from lateral to about 30° down-route (§2).

**Smallest reversible fix.**

- A guarded Show write on those 12 rows only: `lighting.intensity` ×0.35 (→ about 2.2-2.8 k cd, P01's range), or inner
  cones back to the score's 2°/4°. Use the p01_rig_pattern/p02_brighten writer pattern: record first, backup,
  materialize, narrow save, read-back.
- A zero-tool alternative: Gary lowers them in Details. Write-back to the Show is declared (`INFINITY_STAGE_ATTACHMENT_LIGHT_UPDATED`,
  FIXTURES doc §A2).
- The proper fix is applying the P02 relight, once Gary answers the 12 P02 hand-edit keep/overwrite decisions.

### 3. Changes after the last measured stills (7 Oct 06:53 UTC): Car Light first

| Candidate | Change | Evidence | Smallest reversible fix |
|---|---|---|---|
| **P02 Car Light** (level `Infinity Stage Sweep Light`) | Peak 9000 cd; "too bright as placed … try ~2500" since 5 Oct, with no later tuning in any record [searched]; moved onto the straightened route 7 Oct 01:56 | [meas-rec] place record; stills spikes 137/145 on 5 Oct; [inf] the new placement sweeps along the straight view | Set Peak Intensity 9000 → 2500 on the level actor, record the before value, save the level narrowly. Or hide it in game. |
| Meshy cans (132 ParCan, emissive lens 0.6) and 3.2× emissive bulbs | 7 Oct 08:26 | [meas-rec] swap/import records; [inf] small next to 100 k cd of spots | Structure `BodyMaterial` override, or lens MI `Intensity` → 0, record first |
| 20 realism wing panels | 7 Oct 10:33 | [meas-rec] rzswap record; [inf] brighter albedo under 8 k cd beams | `rzswap` REVERT (originals recorded) |
| Klara `Japanese_Alley` leaking into P02 | 8 Oct 18:23 hook-in | [meas-rec] record claims hidden; 8 Oct `p02end` stills unchanged | none needed if a PIE probe confirms hidden |

**First step for 3** (read-only): one PIE stills run of P02 at 0.02/0.2/0.4/0.6/0.8/0.98, the same fractions as 7 Oct.

- Probe the Car Light's intensity and `Japanese_Alley` visibility.
- Compare luma per fraction with the 7 Oct `strike` stills.
- Any rise at 0.02-0.4 isolates a post-7-Oct cause; a rise only at 0.6-0.8 isolates the brighten.

---

## 8. UNCLEAR, and what was searched

- **5-7 Oct log markers:** UNCLEAR; the logs have rotated (above).
- **Live Show vs the 7 Oct 08:26 snapshot:** hand edits after it are not visible offline. The newest editor logs
  have 0 `ATTACHMENT_MOVED`/`LIGHT_UPDATED` lines for P02.
- **P02 auto-exposure / PPV settings:** not stored in any record read.
- **P03 after the 8 Oct relight:** intensities absent from its record, so P03 was not recomputed.
- **Proxies:** not renders; the ranking of 1 vs 2 rests on the proxies plus the stills at fixed fractions [inf].
