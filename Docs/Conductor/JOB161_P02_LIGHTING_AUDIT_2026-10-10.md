# Job 161 — P02 lighting audit and lean proposal

**Run boundary:** offline only. No Unreal, MCP, PIE, package save, editor launch, or APPLY was performed. Gary decides before APPLY.

## Verdict

- **Measured (saved record + PIE stills):** Gary's two descriptions are compatible. P02 has **too much lighting work** but not enough useful surface light: the saved P01-copy contains 462 P02 light rows, 160 were materialized, every enabled row has positive volumetric scattering, and the 30%/60% stills are dominated by bright integrated fog while most wing faces remain dark (`E:/PussStage/Saved/CodexFlatV3/p02lighting/passage_lighting_record.json:24797-364562`; `E:/PussStage/Saved/Logs/PussStage-backup-2026.10.10-07.16.23.log:3185`; `E:/PussStage/Saved/CodexConductor/PassageStills/PSTILLS-P02-20261010-070928-p02-floor-check/passage_stills_manifest.json:70-77,140-147`).
- **Measured:** the owned P02 replay failed p95: **40.673 ms vs 33.4 ms**, while p99 43.054 ms passed its 50 ms ceiling; the same replay's GPU-loss scan was clean (`E:/PussStage/Saved/CodexFlatV3/p02lighting/passage_lighting_perf_PLFT-20261009-224600.json:2-21`). The shortfall is 7.273 ms.
- **Inferred:** the dominant mechanism is many overlapping local-light volumes feeding VSM, volumetric fog, and Lumen, not a shortage of light emitters. This audit has no GPU pass timings, VSM-page count, light-grid occupancy, or matched P01 replay, so it does **not** prove which pass owns the 7.273 ms.
- **Measured / causality UNCLEAR:** the later 04:49 local device removal occurred before Pass 14 mutation, at frame 3150, with active GPU breadcrumbs in skin cache, distance fields/global distance field, Niagara, visibility/VRS, and Lumen scene update. DRED had no page-fault data; local VRAM was 8408/15227 MB. It is evidence of a broad rendering failure, **not proof that P02 lighting caused it** (`E:/PussStage/Saved/Logs/PussStage.log:2841-2890`).

## 1. Per-role inventory

**Measured offline aggregation:** P01 is the full saved/read-back 8 Oct `FLOOR` snapshot (862 rows; 237 enabled). P02 is the 9 Oct P01-copy saved/read-back snapshot (462 rows; 160 enabled), after the 44-row P02 practical operation. Counts are `authored/enabled`; shadow counts are authored `cast_shadows=True` flags. `VSI` is volumetric scattering intensity. All attachment rows use inverse-square falloff, affect GI, have `cast_volumetric_shadow=False`, and have no IES; 302/462 P02 rows carry a light-function material (`E:/PussStage/Saved/CodexConductor/P01FloorPracticals_20261008/p01_floor_record.json:338-171496,392682-392689`; `E:/PussStage/Saved/CodexConductor/P01FloorPracticals_20261008/p02_floor_record.json:58838-58861,132667-132674`; `E:/PussStage/Saved/CodexFlatV3/p02lighting/passage_lighting_record.json:24,24765-24797,27603-364562`).

| Role | P01 count | P02 count | Type; intensity + units (P01 / P02) | radius cm (P01 / P02) | shadows (P01 / P02) | VSI (P01 / P02) | source radius cm | light function (P01 / P02) | IES |
|---|---:|---:|---|---|---:|---|---|---|---|
| CROSS +Y | 48/0 | 23/0 | Spot; 1.79–2.64 cd / 1.79–2.64 cd | 1800 / 1800 | 0 / 0 | 0.6 or 9 / 0.6 or 9 | 22 | Steady / Steady | none |
| CROSS −Y | 48/0 | 23/0 | Spot; 9.60–14.39 cd / 9.76–14.37 cd | 1800 / 1800 | 0 / 0 | 0.6 or 9 / 0.6 or 9 | 4 | Steady / Steady | none |
| ENTRY_FWD +Y | 48/0 | 23/0 | Spot; 47.09–70.05 cd / 47.09–69.87 cd | 2016 / 2016 | 48 / 23 | 0.6 / 0.6 | 4 | Fault/Slow/Steady / same | none |
| ENTRY_FWD −Y | 48/0 | 23/0 | Spot; 33.72–50.19 cd / same | 1107 / 1107 | 0 / 0 | 0.6 / 0.6 | 22 | Breath / Breath | none |
| ENTRY_HIGH +Y | 48/0 | 23/0 | Spot; 3.38–4.98 cd / same | 3594 / 3594 | 0 / 0 | 0.6 / 0.6 | 4 | Slow / Slow | none |
| ENTRY_HIGH −Y | 48/1 | 23/0 | Spot; 23.25–2000 cd / 23.25–34.25 cd | 3547 or 4515 / 3547 | 1 / 0 | 0.6 / 0.6 | 22 | Buzz / Buzz | none |
| ENTRY_TOP | 48/0 | 23/0 | Spot; 37.25–54.41 cd / 38.34–54.06 cd | 3594 / 3594 | 48 / 23 | 0.6 / 0.6 | 0 | Slow / Slow | none |
| FLOAT_L | 48/0 | 23/0 | Spot; 5.14–6.87 cd / 5.35–6.87 cd | 350 / 350 | 0 / 0 | 0.3 / 0.3 | 0 | none / none | none |
| FLOAT_R | 48/0 | 23/0 | Spot; 5.20–6.79 cd / 5.26–6.73 cd | 350 / 350 | 0 / 0 | 0.3 / 0.3 | 0 | none / none | none |
| LOW +Y | 48/0 | 23/0 | Rect; 3.12–4.66 cd / 3.15–4.65 cd | 723 / 723 | 0 / 0 | 0.6 / 0.6 | 0 | Slow / Slow | none |
| LOW −Y | 48/0 | 23/0 | Rect; 0.56–0.83 cd / 0.57–0.83 cd | 657 / 657 | 0 / 0 | 0.6 / 0.6 | 0 | Breath / Breath | none |
| TOP_DOWN | 48/0 | 23/0 | Spot; 2.37–3.47 cd / 2.40–3.47 cd | 1107 / 1107 | 48 / 23 | 0.6 / 0.6 | 10 | Fault / Fault | none |
| BEAM_R | 28/28 | 17/17 | Spot; 2000–4500 cd / 2000–8100 cd | 2600 / 2600 | 0 / 0 | 6 / 2.5 or 6 | 2 | SoftSlats or none / same | none |
| LOW_SIDE_L_KEY | 40/40 | 23/23 | Spot; 256–1000 cd / 144–1000 cd | 1800–4243 / 1800–4243 | 40 / 23 | 0.45 or 0.8 / same | 2 | Breath or none / Breath/Fault/none | none |
| LOW_SIDE_R_FILL | 40/40 | 23/23 | Spot; 39–1500 cd / 36–1500 cd | 1500–2505 / same | 40 / 23 | 0.08 or 0.55 / same | 2 | none / none | none |
| TOP_L | 40/40 | 22/22 | Spot; 0–550 cd / same | 1279–1700 / same | 0 / 0 | 0.25 or 0.35 / same | 2 | none / Hum or none | none |
| TOP_R | 40/40 | 22/22 | Spot; 0–600 cd / same | 1700–2176 / same | 0 / 0 | 0.25 or 0.35 / same | 2 | none / none | none |
| PRACTICAL_BULB_DEAD | 28/1 | 32/19 | Point; 0–300 lm / same | 168 or 520 / same | 0 / 0 | 0.25 / 0.25 | 4 or 16 | Hum / Hum | none |
| PRACTICAL_CLAMP | 28/28 | 21/21 | Spot; 200–1170 lm / 120–990 lm | 650 / 650 | 0 / 0 | 0.3 / 0.3 | 4 | none / Buzz or none | none |
| PRACTICAL_DEAD | 8/0 | 6/1 | Point; 0 lm / 0–120 lm | 400 / 400 | 0 / 0 | 0 or 0.2 / same | 4 | Hum or none / same | none |
| PRACTICAL_GLIMMER | 7/7 | 5/5 | Point; 96–160 lm / same | 300 / 300 | 0 / 0 | 0.2 / 0.2 | 4 | Slow / Slow | none |
| PRACTICAL_L | 12/12 | 6/6 | Spot; 1260–1440 lm / 960–1440 lm | 520 / 520 | 0 / 0 | 0.24 / 0.24 | 4 | Slow / Slow | none |
| PRACTICAL_R | 12/0 | 6/1 | Point; 0 lm / 0–120 lm | 460 / 460 | 0 / 0 | 0.22 / 0.22 | 4 | Hum / Hum | none |
| OPENING_LIGHT | 1/0 | 1/0 | Spot; 19,600 cd / same | 12,000 / 12,000 | 1 / 1 | 1 / 1 | 0 | none / none | none |
| HOUSE_L / HOUSE_R | 1/0 each | 1/0 each | Spot; 800 cd / 800 cd | 3468 / 3025, same | 1 each / 1 each | 1 / 1 | 0 | none / none | none |
| Car sweep (level actor) | 0 | 1 runtime actor | Spot; 9000 cd peak | — / **10,000** | — / true | — / **UNCLEAR: not in tune record** | — / 0 (8 Oct probe) | — / none (8 Oct probe) | **UNCLEAR** |

**Measured qualification:** the car tune record's `current` field is the pre-change 9000 cm state; its `target` and saved `values` are 10,000 cm, 9000 cd, 28° (`E:/PussStage/Saved/CodexConductor/p02_car_light_tune_applied_P02CAR-TUNE-20261010-012009.json:8-12,24,38-52`). The older runtime probe establishes Spot/source radius 0/no light function at 3200 cm, not the post-tune VSI or IES (`E:/PussStage/Saved/CodexConductor/animated_gobo_pie_probe_AGPIE-20261009-02.json:34415-34438`). Those two car fields remain UNCLEAR rather than guessed.

**Measured:** the beam bootstrap added four visible, non-shadowing beam-mesh proxies at B03/B07/B12/B20; they are atmosphere geometry, not four additional `ULightComponent`s (`E:/PussStage/Saved/CodexFlatV3/p02lighting/p02_beam_bootstrap_record.json:8-13,962`).

## 2. Why it is HEAVY

1. **Measured:** P02 carries 118 authored shadow flags: 110 on the 414 copied rows and 8 on retained rows. Of the 160 enabled/materialized lights, 46 are shadow casters; the car is an additional shadow-casting level light. P01's saved comparison is also heavy (227 authored flags, 81 enabled), so “P02 = P01” copied a costly baseline rather than a lean look (`E:/PussStage/Saved/CodexFlatV3/p02lighting/passage_lighting_record.json:24797-364562`; `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageSweepLight.cpp:148-151`).
2. **Measured historical / inferred current risk:** coloured rectangles are the project's established VSM one-pass overflow symptom. Raising the limit did not help; the shader fallback is a single unfiltered VSM lookup at page granularity. The correct lever is less per-pixel/froxel overlap (`E:/PussStage/Docs/LightingEfficiencyPlan_2026-09-29.md:81-83`; `Docs/RigAndAtmosphere_Handover_2026-09-28.md:64-70`). No fresh P02 VSM stat capture was made tonight, so current page pressure is inferred from caster/overlap counts, not directly measured.
3. **Measured:** enabled attachment radii total 237,323 cm (median 1700, p90 2600, max 4243) before adding the **10,000 cm car sphere**. Large local spheres/cones overlap many wings and fog cells even when the resulting surface contribution is weak. The original far-wing geometry estimate was ~3816 cm, which is why 4600 cm—not 10,000—was the prior reach proposal (`Docs/Conductor/JOB110_P02_CAR_LIGHT_TUNE_REPORT_2026-10-09.md:24-31`).
4. **Measured:** all 160 enabled P02 attachment lights have VSI > 0; their summed authored VSI is 150.26. Global haze is density 0.022, anisotropy `g=0.55`; with forward scattering, shafts read only when light travels toward the viewer, so non-backlit contributors can still consume fog work without drawing a useful shaft (`Docs/Conductor/DIRECTING_BY_HAND_GUIDE_2026-10-05.md:318-320`; `Docs/RigAndAtmosphere_Handover_2026-09-28.md:60-65`).
5. **Measured configuration / inferred cost:** all 462 P02 rows affect GI, while the crash-session configuration had hardware-ray-traced Lumen, reflections, translucency volumes, and an 8-light direct-lighting tile limit active (`E:/PussStage/Saved/Logs/PussStage.log:625,766-816`). More overlapping, moving or shadowed local lights therefore create work in several render systems; this audit cannot apportion the frame cost to Lumen versus VSM/fog.

## 3. Why it SHOWS TOO LITTLE

1. **Measured + inferred photometry:** the parent tool explicitly remapped 327 rows to an own-side wing target at z=600 cm. Recorded source-to-target distances are 4.0–17.4 m depending on role (`E:/PussStage/Saved/CodexFlatV3/p02lighting/passage_lighting_record.json:48,70,1249-17273`). With inverse-square falloff, Cross +Y at ~1.8–2.6 cd and ~9–10.6 m contributes only ~0.016–0.033 lux on beam centre; Entry High −Y at 23–34 cd and ~13–16 m contributes ~0.09–0.19 lux. These are inferred upper bounds before cosine loss and light-function masks. By contrast the useful L key and BEAM_R families are hundreds/thousands of candela.
2. **Measured:** the still runner introduced no exposure override; the trusted capture convention is to inherit the show's post process. Manual exposure plus compensation is not EV100 and previously rendered several stops too dark. The show passage volume is the unbound Histogram setup pinned around EV100 −3 (`Docs/InfinityStageSessionHandover.md:760-769`; `Docs/RigAndAtmosphere_Handover_2026-09-28.md:489-497`; `Docs/Conductor/JOB138_REPORT_2026-10-10.md:21-23`). Therefore the milky/dark-surface contradiction in these stills is not dismissed as the old manual-capture error.
3. **Measured visual / inferred mechanism:** both trusted stills show bright fog veiling and isolated practicals while broad wing faces remain near-black. Every enabled light scatters, so energy integrated through the view ray can lift the fog before the same light delivers enough irradiance to a surface. This is the literal “showing up too little” failure: the light is visible as atmosphere, not as modelling on the flats.
4. **Measured / UNCLEAR:** 281 of 342 Spot rows have an explicit wing-target mapping; 61 do not. The unmapped group includes ENTRY_TOP, TOP_DOWN, the opening light and practical clamps. Absence of a mapping does not prove each misses geometry, but it means the records cannot prove their cone intersects a useful face. A live cone/wing intersection read is still required before calling any individual spot “aimed at nothing.”
5. **Measured:** 302/462 rows have light-function materials (Steady/Slow/Breath/Fault/Buzz/Hum/SoftSlats). These masks can lower or spatially gate already small surface contributions. None uses IES to concentrate the throw.

## 4. Concrete LEAN plan — Gary decides

**Inferred creative proposal:** keep P01's colour, temperatures, cones, timing/drama, practicals, and the four B03/B07/B12/B20 hero shafts, but make the readable system one stronger own-side key per bay instead of four score/fill families per bay.

| change | record-scoped result |
|---|---|
| Keep all 23 L keys; multiply only the 19 copied/owned keys by **1.35**, cap their radius at **1800 cm** | preserves one aimed modelling key per bay; leaves the four retained non-owned keys untouched |
| Disable copied `LOW_SIDE_R_FILL`, `TOP_L`, `TOP_R`; disable copied non-hero `BEAM_R` | owned enabled rows **113 → 46**; whole P02 predicted materialized lights **160 → 93** |
| Keep shadows only on owned L keys at B03/B07/B12/B20 | owned shadow flags **110 → 4**; including retained rows, whole P02 authored/enabled casters **118/46 → 12/12**, plus the car |
| VSI 0 on every copied row except hero BEAM_R at B03/B07/B12/B20 | owned enabled scatter contributors **113 → 4**; whole P02 **160 → 51** because 47 retained rows are deliberately out of scope |
| Car radius **10,000 → 4600 cm**, no aim/intensity/cone change | still exceeds the inferred ~3816 cm far-wing throw with ~784 cm margin; removes the huge overlap sphere |
| Preserve all 44 practical-operation rows and all four beam meshes | practical placement/look and bootstrap atmosphere geometry remain unchanged |

**Inferred performance prediction:** compared with the failed 40.673 ms p95, a reasonable pre-registered range is **29–34 ms p95** (about 6.5–11.5 ms saved). It may still fail: the earlier all-shadows-off result only supports ~4.5 ms mean, and light-count/fog/radius savings are not locally benchmarked. Acceptance remains p95 ≤33.4 ms, p99 ≤50 ms, no GPU-loss signature, then Gary's still review. Do not present 29–34 ms as measured.

## 5. Guarded tool and run order

- **Declaration-proven:** `p02_lighting_lean.py` accepts only DRY/APPLY/REVERT confirmations, requires the exact saved parent run and 414 minted GUIDs, requires the exact saved 10,000 cm car-tune record, and hashes a deterministic plan (`Saved/CodexFlatV3/p02lighting/p02_lighting_lean.py:69-181`). The actual-record offline plan is `4d22160f9f98a5cbf289409497eac4de2f45e5d369489e909ec709ceb05065b5`; shipped args remain DRY.
- **Declaration-proven:** APPLY/REVERT can edit only those GUIDs plus the exact recorded car actor path; non-owned rows are hashed before/after. It creates `Backups/PreP02LightingLean-*`, requires the exact Show+level dirty census, saves only those packages, reads back, queues the saved-master test, and writes a run-id marker (`p02_lighting_lean.py:194-248,255-352`).
- **Measured offline:** the harness passed **20/20** positive and negative controls (`Saved/CodexFlatV3/p02lighting/P02_LIGHTING_LEAN_OFFLINE_HARNESS_RESULTS.md:1-7`). Unreal compatibility, live DRY, saved read-back, performance and rendered acceptance remain unverified.
- **Measured environment blocker:** explicit-path `git add`/`git add -f` could not create `E:/PussStage/.git/worktrees/PussStage17/index.lock` (`Permission denied`). The scoped files are complete but uncommitted; no commit hash is claimed.

Ordered conductor step after Gary says **DRY only**:

1. Run `python Saved/CodexFlatV3/p02lighting/test_p02_lighting_lean_offline.py`; require `P02LIGHTLEAN_HARNESS|pass=20|fail=0`.
2. Run `p02_lighting_lean_request.json` with shipped DRY args. Require `P02LIGHTLEAN_DRY_OK`, `enabled=113->46`, `shadows=110->4`, `scatter=113->4`, `car=10000->4600`, a clean unchanged census, and review the SHA. **Stop for Gary.**
3. Only after Gary explicitly approves APPLY: copy the DRY SHA, set `mode=APPLY`, `confirm="APPLY P02LIGHTLEAN"`, rerun. Require backup, `P02LIGHTLEAN_APPLY_OK`, Show+level-only save, read-back, saved-master test, clean census.
4. Start a conductor-owned P02-from-start PIE. Run the existing `passage_lighting_perf_probe_request.json` with the same 60 s / skip-30 / 33.4 ms p95 / 50 ms p99 gate. Use a fresh post-APPLY log cursor and fail on `DXGI_ERROR_DEVICE_REMOVED`, `DXGI_ERROR_DEVICE_RESET`, GPU crash or hung transport.
5. With that same owned PIE and **no exposure override**, run `passage_stills_request.json` at fractions **0.30 and 0.60**, plus an early 0.05 frame and matched near/far car-sweep frames. Re-scrub the same time before capture. Gary checks: wing faces read, four hero shafts read from their back-light direction, no milky wall, no colour rectangles, and the car reaches the far wings without flooding the corridor.
6. On any perf/render rejection: end owned PIE, set `mode=REVERT`, `confirm="REVERT P02LIGHTLEAN"`, rerun and require `P02LIGHTLEAN_REVERT_OK`, saved read-back and clean census. To parent-REVERT P02=P01, lean-REVERT first.

## Decision boundary

**No APPLY decision was made.** Gary chooses: keep the current P01 copy; approve this lean DRY then separately approve APPLY; use Job 125's gentler ranked trim; or revert the parent P02=P01 copy. The 04:49 GPU loss increases caution but is not attributed to P02 without a repeatable A/B.
