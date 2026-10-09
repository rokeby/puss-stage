# Post-bake editor queue — 9 Oct 2026 (Conductor 5)

Starts when the ragged bake prints `CURTAIN_DROP_BAKE_DONE` (expected 10:30–11:30 UTC). Then FIRST: tell every live
Puss session + Metamall 5.8 that the GPU is free (Gary). Blender work (Hyper3D mask APPLY / Rodin fetch, W&T rebuilds)
is cleared at the same time — but only ONE GPU-heavy job at a time alongside the editor.
Editor rules: one writer; DRY → APPLY → read-back; sky hidden after every restart; never Save All; P26/vis = bHidden.

Order (dependencies first; Gary's decisions 9 Oct in `memory/tonight-queue-9-oct.md`):

| # | Slot | Tool | Notes |
|---|---|---|---|
| 0 | W&T review stills (one short PIE) | `Saved/CodexFlatV3/review_stills/` (Q6) | Conductor starts/ends PIE; S2 wide/fall/ceiling, P02 rows, keeper, proscenium. |
| 1 | Passages = music lengths | Codex job 33 `passages_to_music.py` | APPLY without Gary's review (his word). P06 126.0 → 110.56 s. |
| 2 | P06 retime | Codex job 42 `p06_retime.py` | Sunset cycle × live k, car + bees scaled, FX distance-gated (unchanged). New dusk ≈ 32.48 s → W&T. |
| 3 | I2 shrink to 1950 | Codex job 24 `shrink_scene_playback.py` | Before I2 camera work. |
| 4 | I2 move-in at 0:50.4 | Codex job 34 (finishing touches) | |
| 5 | I2 polish | Codex job 39 `I2Polish_20261009` | Boundary probe (PIE) → repair; F17 diff; F18; run-on. |
| 6 | P06 chain A REVERT | W&T topple | Then 7, then 8. |
| 7 | P06 chain B (choreographed) | Codex job 37b | Rows disjoint from A's 6 + keeper; record by cue GUID + side. |
| 8 | P06 chain A re-time | W&T make_keys --slam-s <dusk> + exclude_rows(B) | |
| 9 | P06 FX re-time check | P06FX set | Fire/motes seconds vs new P06 length. |
| 10 | P02 floor shiny | `p02_floor_darkwet.py` | Material only. |
| 11 | S1 darkness before strike (F4) | Codex job 26 vis_fix S1 + PIE probe | |
| 12 | S1 rig fade at 3:44 (F5) | Codex job 29 S1RigFade | Verify the switch-off frames (found ~11 s, not 3:44). |
| 13 | S3 lid (F20) + 0:04 spoiler | Codex job 38 | |
| 14 | S3 figures: Shore05 (+variants), cloth settle, underwear colour | Codex job 40 | |
| 14b | S3 clam chain (existing tools, no new Codex) | `s3_pearl_fade.py` (S3-1 alpha fade + halo), `s3_shots_fix.py` (S3-2 new clam, B06 re-aim), `ClamSlime_20261008` (slime/ligament), then S3-3 grazes onto prints | Re-DRY each: tools are from 8 Oct, S3 has changed since. **ClamSlime is a two-stage mutation: run and verify `IMPORT CLAMSLIME` first; only then re-DRY and run `APPLY CLAMSLIME`.** See `CLAM_SLIME_RUNBOOK_2026-10-09.md`. |
| 14c | S3 dunes x2 (set D, existing tools) | `S3Shore/s3_shore_blender_build.py --set D` (headless Blender, ONE at a time, after the bake) → `s3_shore_ground_ue.py` import/APPLY | Set D generated 8 Oct (s3_shore_dunes_x2_record.json) but never imported [inferred]. Re-run feet/crowd z after. |
| 15 | S3 +50 % handprints, camera wall | Codex job 38 | Still before save. |
| 16 | Gobo 007 as stand-in | gobo session args 007 | Gary reviews content later. |
| 17 | Infrastructure for Gary's review | job 35 uplights P02–P06; parcans (job 43, one model SM_Lantern_ParCan, bay-1 refused); P02 P01-style lighting = W&T Q7 `p02lighting/` (perf gate; 415 vs 414 reconcile first; job 43 GPU-loss runbook); S2 seam + dark shots (job 43 `s2_lighting_seam.py`) | Stills after. |
| 18 | Trough clear | Codex job 25 | |
| 19 | W&T queue | Q1–Q3 (S2 overlay re-pose/sky start, poles, P03 cards, P02 fences, P06 scaffold, Wing 044 UVs) | W&T sequences. |
| 20 | GPU/RAM-heavy investigations LAST | Codex job 38 dune ground probe (fire shadows); P06 wing burn (after W&T Wing 044 UV spec) | Gary: only when GPU/RAM free. |
| 21 | Cue Book stills | cueing `cuebook_stills_driver.py` | Low priority. |

Gary-owned: Code.gs redeploy; pearl clear coat; video fallbacks (Sat night + tomorrow night); opening choreography after Hyper3D.

Creative backlog (later, Gary's call on where/when): iron chandelier with lit candles, swinging dramatically in a Passage — mesh from Hyper3D (Rodin iron variant, after Gary's review), then candle flames + swing rig: hang it on a CHAIN using the SAME rig as the lights on wings (Gary: "the same kind of physics as the lights on wings" = the fixtures bulb-sway, built 9 Oct 7f53ab6) — no new physics; P06 FX fire pattern for the candles. Image-based chandelier (~2.3 m, two tiers) delivered; iron variant generating.
- Chandelier (Gary picked Iron 3: two hoops, ~40 candles): job 55 aging + sockets + 3 m chain (Hyper3D) → job 56 candles `P56ChandelierCandles_20261009` (2bb8a5a3; run ONLY after job 55's socket JSON exists; flame scale 0.035 inferred, needs a render) → job 52/52b swing keys.
