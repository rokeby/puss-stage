# F1: P01 practicals that "just float there" (offline inventory and plan, 8 Oct 2026)

Gary's note (8 Oct, GARY_FINISHING_NOTES_2026-10-08.md row F1): many practicals visible from the wings "just float
there". He wants them hidden, moving with the wings, or with the physical object "on the floor or in the bottom
corner", which "might be enough".

**Scope.** This was a read-only offline pass. Unreal and MCP were not run. No existing file was edited. Nothing was
applied or committed. The only new file is this report.

**Proof tiers, per claim** (AGENTS.md):

- **[decl]**: a header or source line we can read (declaration-proven).
- **[meas-rec]**: read back from an existing saved record or log, or from an offline computation over one.
- **[inf]**: inferred, with the reason given.

No claim here is binary-proven.

**Time zone.** Run ids and file mtimes are local time (UTC-4). Editor log stamps are UTC.
Evidence [meas-rec]: `PSTILLS-P02-20261008-223703` has `started_utc` 22:37 and file mtime 18:37 local.

---

## 1. Summary

1. **Nothing in P01 moves with a wing today [meas-rec].**
   - All 960 attachments of the 48 P01 cues carry `anchor = STATION`. This is read from
     `MeshyFixtures_20261007/meshy_swap_record_P01.json` `after_rows` (run 20261007-082523,
     `saved_readback_verified`), the latest full-row snapshot of P01.
   - So none of the 95 practical light/body pairs is class (a).
2. **The 95 practical pairs** [meas-rec, same record]:
   - **48 Meshy bulb bodies (class b, float in view):** PRACTICAL_BULB_DEAD 28, PRACTICAL_DEAD 8 (7 GAP + 1 VOID),
     PRACTICAL_R 12. Their lights are 0 lm for 47 of them. The one exception is B04 BULB_DEAD at 300 lm.
   - **47 domestic StarterContent bodies (class d, F2):**
     - PRACTICAL_CLAMP 28: `SM_Lamp_Wall`, 600-1170 lm.
     - PRACTICAL_L 12: `SM_Lamp_Ceiling`, 1380 lm.
     - PRACTICAL_GLIMMER 7: `SM_Lamp_Ceiling`, 96-160 lm.
   - **0 practical bodies on the rig (class c).**
3. **Every body sits low and beside a wing [meas-rec].**
   - Bodies are at |y| 700-815 cm and z 100-219 cm in their pair frame, beside the wing panels. The panels span
     roughly |y| 140-400 cm (inner edge) out to 650-1130 cm (outer edge).
   - Where the panel span is derivable, 66 bodies sit inside the panel's lateral span, 13 sit outside it, and 16 are
     unknown.
4. **The bulb is not the only floating object [decl + meas-rec].**
   - Every *enabled Station-anchored LIGHT* also gets a Structure "can" (housing ISM instance) at the light
     (`InfinityStageStructureActor.cpp:164`, `:168-171`).
   - P01 has 284 such cans, of which 95 sit on the practicals. That includes the 47 dead lights at 0 lm.
   - It also has 80 LOW_SIDE and 28 BEAM_R cans hanging at z 130-896 cm at or outboard of the wing edges.
   - **Moving only the bulb mesh would leave a SM_Lantern_Fresnel can floating where it was.**
5. **The cheapest real fix for the 47 dead practicals [decl + inf]:**
   - Disable the 0 lm light row, so its can disappears (cans exist only for enabled lights, `:164`).
   - Drop the bulb body to the floor at the wing foot.
   - No light is lost (0 lm), and the glass keeps its authored glow (`bFollowLight` defaults false,
     `InfinityStageBulbBody.h:40`; all 225 swapped bodies have `follow_light` False per FIXTURES doc D2).
6. **The 40 lit domestic practicals (28 clamps, 12 PRACTICAL_L) are not covered by F2 [inf].**
   - F2 removes their bodies, but their lights and cans would still float.
   - They need a creative call:
     - (i) move light and can to the floor at the wing foot as an uplight on the wing face (overlaps F3 "more
       uplights");
     - (ii) disable them, losing the practical pools;
     - (iii) leave the cans.
7. **"Attach to the wing" is declared but would not move [decl + inf].**
   - The anchor enum offers LeftPanel/RightPanel/TopPanel/PairCentre (`InfinityStageTypes.h:152-161`).
   - Attachment actors are placed only at materialize (`InfinityStagePassageActor.cpp:956` is the only runtime caller
     of `GetAttachmentWorldTransform`). No tick re-places them [searched], so they would **not** follow wing travel
     during the show.
   - Light Drama strikes, flashes and movers also skip non-Station lights (`:1865`, `:1917`). P01's 30 note lamps
     would stop flashing. 13 of them are practicals: 6 CLAMP, 5 PRACTICAL_L, 2 GLIMMER.
   - Wing-riding therefore needs C++. Recommendation: floor, not wing.
8. **A tool for most of this already exists, unrun:** `FixturesFollow/fixtures_follow.py` RELOCATE.
   - Its offline harness is 53/53 (`harness_result.json`). For P01 it proposes 47 relocated, 27 hang, 20 ground,
     7 glimmers to bare bulb, and 54 lights retired.
   - Gary's F1 wording ("on the floor") maps to RELOCATE with `hang_fraction` 0. Section 6 plans the remainder: the lit
     domestic practicals and the LOW_SIDE/BEAM cans.

---

## 2. Sources read (and what was not found)

| Source | Use | Tier |
|---|---|---|
| `Saved/CodexConductor/MeshyFixtures_20261007/meshy_swap_record_P01.json` (`after_rows`, 48 cues / 960 rows, run 20261007-082523) | Every row: label, GUID, kind, enabled, anchor, mesh, `relative_transform`, lighting | [meas-rec] |
| `p01_note_lamps_record.json` (run 20261007-160203, `saved_readback_verified`) | Later than the swap. Writes **drama only** (`drama_before`/`drama_after` per target; 30 lamps, of which 13 are practicals (6 CLAMP, 5 PRACTICAL_L, 2 GLIMMER), flagged "flash" in the table). Also gives route `wings[].distance_cm` per cue. | [meas-rec] |
| `p01_rig_pattern_record.json` (run 20261006-184409) | Earlier. Copied relative location/rotation from template bays (229 target rows). The swap rows already include it. | [meas-rec] |
| `rig_lamp_drop_record_P01.json` (run 20261006-022035) | Earlier. TOP rows dropped to the rig; `live.fixture_body_count` 284. | [meas-rec] |
| `lighting_scores_record_P01.json` (run 20261005-024851) | Earliest. The 5 Oct score that created the practical rows. | [meas-rec] |
| `dead_bulbs_warm_record.json` (run 20261007-024628) | `per_passage.P01`: targets 0, already_warm 48. **No P01 change.** | [meas-rec] |
| `GlimmerBulbs_20261007/glimmer_targets_from_records.json`, `FixturesFollow/glimmer_attachments_snapshot.json` | The 7 P01 glimmer light/body GUID pairs (match this table) | [meas-rec] |
| `Effects_20261007/fx_attach_enable_record.json` (run 20261008-042536) | P01 FX SMOKE effects only (not practicals) | [meas-rec] |
| `Saved/CodexFlatV3/swapkit/hf_preflight_FV3HF-20261006-P01.json` + `floorgap/GAP_AUDIT.json` | Wing panel local y and front width for 80 of 96 P01 panels → panel y-span per side | [meas-rec] |
| Plugin source `Plugins/InfinityStage/Source/InfinityStage/...` | Anchor semantics, can generation, drama gating | [decl] |

**Searched and found nothing:**

- A Show write to P01 practical transforms after 7 Oct 08:25. Every `*record*`/`*APPLY*` JSON under `Saved/` newer
  than 7 Oct 08:20 that names P01 was checked. Only note_lamps (drama), fx_attach_enable (effects),
  stage_front_wings, and the P03 relight's ack list touch P01.
- `INFINITY_STAGE_ATTACHMENT_MOVED` / `ATTACHMENT_LIGHT_UPDATED` in the remaining editor logs: 0 hits. Only 8 Oct
  logs remain in `Saved/Logs`, so hand moves on 7 Oct cannot be seen.
- Station distances for P03/P04. Not needed here.

**[inf]** The live Show may differ from the records by hand edits made after the last record. The tool's DRY
re-reads live.

---

## 3. Mechanism (why "floating" happens, and what each option can do)

| Fact | Source | Tier |
|---|---|---|
| Anchors: `Station` (fixed at the pair's spline station; wings move past it), `LeftPanel`, `RightPanel`, `TopPanel`, `PairCentre` (midpoint of L/R panels) | `InfinityStageTypes.h:150-162`; field `Anchor` `:462`; `RelativeTransform` "offset from the resolved anchor" `:464-467` | [decl] |
| Panel anchors resolve to the panel's *live ISM instance* transform; PairCentre uses the live L/R midpoint; a missing panel falls back to the station | `InfinityStagePassageActor.cpp:2137-2190` | [decl] |
| The resolved world transform is used to spawn attachment actors at materialize; no other runtime caller | `InfinityStagePassageActor.cpp:956` (only runtime call; the editor module uses the anchor for write-back only, `InfinityStageEditorModule.cpp:269`, `:389`) | [decl] + [inf: no per-tick re-placement found; searched `GetAttachmentWorldTransform`, `GetAttachmentAnchorWorldTransform`, `SetActorTransform` in the plugin] |
| Light Drama (strike/flash) and Movers only run for Station-anchored lights | `InfinityStagePassageActor.cpp:1865`, `:1917`; Mover header comment "Station anchor only" `InfinityStageTypes.h:494` | [decl] |
| A Structure can is generated for every **enabled** LIGHT that is **Station**-anchored; non-Station lights are counted as moving lights and get none | `InfinityStageStructureActor.cpp:164`, `:168-171` | [decl] |
| One can mesh per Structure: P01 = `SM_Lantern_Fresnel`, 30.28×23.8×49.27 cm, 284 instances; 95 of them on practicals | swap record `plan.housing`, `structure_after` | [meas-rec] |
| Bulb bodies are PROP rows paired to lights by label only; placed with the glass centre on the light origin; they do not follow their light | swap record; `Docs/Conductor/FIXTURES_FOLLOW_SCALE_BULBS_2026-10-07.md` §A1 | [meas-rec] |
| Do P01 wings actually travel during the show (fan reveal / gust)? | not determinable offline; Gary's "move with the wings" implies they do | [inf] UNCLEAR |

**Consequences:**

- **"Attach to the wing":** the data model accepts it. The body would appear at the panel's pose *as materialized*,
  but would not ride later inward travel without a C++ change (per-tick re-placement of panel-anchored attachment
  actors) [inf].
- A panel-anchored practical **light** would also lose its strike/flash, losing P01's note-lamp flashes [decl], and
  lose its can [decl]. The second effect is the only useful one.
- **"Floor":** a pure Show write (PROP `relative_transform` plus LIGHT `enabled`/`relative_transform`) and a
  Structure re-fit. No C++ needed [decl, the tools already do this].

---

## 4. Classification and counts (P01)

| Class | Meaning | Practical bodies | Their lights | Their cans | Tier |
|---|---|---|---|---|---|
| (a) | already moves with a wing | **0** | 0 | 0 | [meas-rec] |
| (b) | floats in view (Meshy bulb, Station anchor, z 100-219, beside a wing) | **48** (BULB_DEAD 28, DEAD 8, R 12) | 47 at 0 lm; B04 BULB_DEAD 300 lm | 48 Fresnel cans at the lights | [meas-rec] |
| (c) | on the rig / ceiling | **0** practical bodies | none | **81 non-practical cans**: TOP_L 40 + TOP_R 40 (z 1249-1444) + Wing 041 "Entry High -Y" (z 1886) | [meas-rec]; whether they sit on the crossbeam is [inf] (they were moved above the 1100 cm rig-drop height by the 6 Oct rig pattern) |
| (d) | domestic `SM_Lamp_*` (F2) | **47**: CLAMP 28 `SM_Lamp_Wall` ×1.25; PRACTICAL_L 12 `SM_Lamp_Ceiling`; GLIMMER 7 `SM_Lamp_Ceiling` ×0.4 | 40 lit at 600-1380 lm; 7 glimmers at 96-160 lm | 47 Fresnel cans | [meas-rec] |
| (b′) | non-practical cans floating at the wings | – | LOW_SIDE_L_KEY 40 (z 203-896), LOW_SIDE_R_FILL 40 (z 604-763), BEAM_R 28 (z 130-378); 84 of these 108 are outboard of \|y\| 1130 | 108 cans | [meas-rec] |

**Estimated objects Gary may read as "floating from the wings" [inf]:**

- 95 practical bodies, plus 95 practical cans, plus up to 108 LOW_SIDE/BEAM cans.
- About 300 meshes in total.
- After F2 removes the 47 domestic bodies, about 250 remain.

---

## 5. Per-item proposal rules

**Frame and floor:**

- Pair frame: x along the route (the camera travels +x), y lateral (left −), z up.
- **Floor z ≈ 0** [inf]: P01 FlatV3 panels sit at `panel_z_cm` 0, and front bottoms are at 0-1 cm (`GAP_AUDIT.json`
  placements, `front_min_z_cm`). The tool must read the floor live (RELOCATE already does, with a no-floor list).
- **Wing face at x ≈ −15** [meas-rec from FBX probe `edge_x_probe_t5j_all.json`]: P01 Front slot at x −15, facing −X.
  **[inf]** the panel's local rotation is identity, so that is pair-frame x −15.
- **Panel y-span** = `[y_panel, y_panel + width]` (left) or `[y_panel − width, y_panel]` (right).
  - Sources: `hf_preflight` `local_transform.location.y` and `GAP_AUDIT` `front_width_cm`.
  - **[inf]** the right meshes extend toward −y from their pivot. The recorded inner edges in `run_p1.json` (−399 /
    +384 for Wing 001) agree.
  - **[inf]** the TK lateral-shift mirror trap may put these up to 35 cm off (memory tk-lateral-shift-frame-mirrored).
    The tool must use the live panel instance bounds.

**Rules:**

- **(b) dead bulbs (47):**
  - Light row: `enabled` → false. Its can disappears; there is no light loss at 0 lm.
  - Body:
    - x unchanged;
    - y clamped into the panel span with 30 cm margin, which lands it at the wing foot;
    - z = floor − `bounds.min.z × scale` (standing on its cap), or lying on its side per the RELOCATE GROUND rules.
- **(b) B04 BULB_DEAD at 300 lm (1):** move the light *and* the body to the floor point. The can follows to the floor.
  Or keep it as RELOCATE's "working practical, stays in can". Gary's call.
- **(d) lit domestic (40):** body removal per F2. For each light, either:
  - (i) move it to the floor at its wing foot, aimed up the wing face (uplight; can on the floor); or
  - (ii) disable it.

  This is creative, so it goes to Gary. Keeping the light where it is keeps a floating can.
- **(d) glimmers (7):** RELOCATE already converts each to a bare bulb (`HANG_AT_SPOT` default, or `GROUND_UNDER_SPOT`).
  "On the floor" means `GROUND_UNDER_SPOT`.
- **(b′) LOW_SIDE/BEAM cans (108):** not practicals. Options:
  - (i) drop each light to the floor at the wing's outer foot (changes aim and look);
  - (ii) a stand or boom mesh (C++: one BodyMesh per Structure today, `InfinityStageStructureActor.h:396-416` per the
    FIXTURES doc);
  - (iii) accept.

  Gary's call. Listed here so the count is not missed.

The full per-item table is §8. Its "proposed body target" column applies the (b) rule. For (d) it records F2.

---

## 6. Tool plan (not written)

**Recommended route:** extend the existing `FixturesFollow` RELOCATE rather than writing a new tool.

- It already has DRY/APPLY/REVERT, record-first, `Backups/` snapshot, rollback in memory, narrow save, read-back and
  markers. Its harness has negative controls (53/53).
- What is missing for F1:
  - (1) `hang_fraction` 0 / floor-only for P01;
  - (2) a **LIGHT_TO_FLOOR** option for lit practicals (moves the light row's `relative_transform` with the body, so
    the can follows);
  - (3) the lit domestic clamps / PRACTICAL_L as targets. These are excluded today because the Meshy swap skipped
    them as `NOT_A_SPHERE_BULB`;
  - (4) an optional group for LOW_SIDE/BEAM cans.

**Plan (P01 only; op `FLOOR`):**

1. **DRY** (editor, no PIE, no open Sequencer):
   - Read the live P01 rows and Structure 01 stations, the live panel ISM instance bounds per cue/side, and the floor
     bounds under each target spot. Compose against the live root, not the sunk REST pose (memory
     puss-level-saved-landed-frame-trap).
   - Classify (a-d, b′) exactly as §4.
   - For each target compute the body pose; for LIGHT_TO_FLOOR also the light pose and aim (aim = the wing face's
     inward normal pitched up).
   - Predict the can count: 284 − disabled + moved-stay.
   - List foreign active records that name a target GUID. Expected: meshy_swap_record_P01, p01_note_lamps_record,
     p01_rig_pattern_record, lighting_scores_record_P01, rig_lamp_drop_record_P01.
   - Print `plan_sha256`, counts, and a top-down + route-cam preview (`fixtures_preview.py`).
   - Marker `FIXFOLLOW_FLOOR_DRY_OK|run=<id>|plan=<sha>|targets=<n>`.
2. **APPLY** (confirm token, `expected_targets` = DRY count, `ack_records` verbatim):
   - `Backups/PreFixFollowFloorP01-<run>` (Show + level).
   - Fsynced record of every before row **before** the first write.
   - Writes are limited to: PROP `relative_transform`, LIGHT `enabled`, and, for LIGHT_TO_FLOOR, LIGHT
     `relative_transform`. No GUID minting: rows are reused (`EnsureStableIds` does not mint, FIXTURES doc).
   - Scope check: every other row and field bit-identical; outside hash.
   - Materialize Passage 01 and **re-fit Structure 01**, so cans vanish or follow.
   - Verify the can ISM count equals the prediction, every moved light's can sits on the floor, and the 8-corner gap
     is mirror-safe.
   - Narrow save (Show + level only; refuse other dirty packages).
   - Read back from the saved asset.
   - `FIXFOLLOW_FLOOR_APPLY_OK|run=<id>` only after asserted returns.
3. **REVERT:**
   - Drift check: every target must read its after value.
   - Restore the before values bit-exact.
   - Same materialize, re-fit, save and read-back chain.
   - Archive `.reverted-<run>`.
   - Order with SCALE/RELOCATE as the tool already enforces.
4. **Gates:**
   - Rendered still or PIE look check by Gary (automation is not acceptance).
   - Note lamps: moving a flash lamp's light keeps its drama, because the anchor stays Station.
   - **Do not** re-anchor to panels (it kills flashes and does not follow travel).
   - A scores re-APPLY on P01 would discard all of this, and is refused while score rows exist. Re-run after any
     rescore.

**Decisions for Gary before APPLY:**

1. Dead bulbs to the floor, as standing or lying mix, or some on cords (RELOCATE default 27 hang / 20 ground)?
2. The 40 lit domestic practicals: floor uplight or off?
3. B04's 300 lm bulb: floor or stay?
4. LOW_SIDE/BEAM cans (108): floor, stand mesh (C++), or accept?

---

## 7. Open / UNCLEAR

- **UNCLEAR** whether P01 wings travel during the show. Not derivable offline.
- **UNCLEAR** live drift since 7 Oct 08:25. The editor logs for 7 Oct have rotated.
- **[inf]** the panel spans (±35 cm). The DRY must measure live.
- **[inf]** the rest heights per bulb mesh (scale 3.2, glass-centre anchoring). The DRY reads mesh bounds.

---

## 8. Per-item inventory (95 practical light/body pairs, P01)

All rows are [meas-rec] from `meshy_swap_record_P01.json` `after_rows`, with route distance from
`p01_note_lamps_record.json`.

- **Anchor** is `STATION` for every light and body. Every light shown is enabled and has a Structure can.
- **Light lm:** the authored intensity, in LUMENS (point lights).
- **"(flash)":** the light is one of the 30 note-lamp targets.
- **Wing panel y-span:** derived as in §5 [inf ±35 cm]. "inside"/"OUTSIDE" says whether the body's y lies within it;
  "n/a" means the panel is not FlatV3, so no width was recorded.
- **Proposed target** is in the cue's pair frame: (x unchanged, y clamped to span ±30 cm, z = floor + mesh rest height).

| Bay (cue, route cm) | Role | Light GUID | Light lm | Light rel (x,y,z) cm | Body GUID | Body mesh (scale) | Body rel (x,y,z) cm | Wing panel y-span (side) | Class | Proposed body target (pair frame) |
|---|---|---|---|---|---|---|---|---|---|---|
| 001 (250) | PRACTICAL_DEAD | `FDF5DFC64D45681345CE5FA13C55F6EA` | 0 | [15, 700, 115] | `032BA4334122D8DCC1F6558878466B8A` | SM_Bulb_A60_Worn (3.2) | [15, 700, 138] | 390..1115 inside | b | (15, 700, floor+rest) |
| 002 (850) | PRACTICAL_DEAD | `EF38078B4FAFD55AC4541DBBFCF4ECB3` | 0 | [-10, 700, 115] | `CEBC51B645479C05BB1E0D887297C87C` | SM_Bulb_A60_Clear (3.2) | [-10, 700, 138] | 500..1001 inside | b | (-10, 700, floor+rest) |
| 002 (850) | PRACTICAL_GLIMMER | `07C6C4424357A9334CDFE89FE9705D69` | 96 | [-20, -700, 140] | `5840444948F3C807A6FD6CB7516B2DA9` | SM_Lamp_Ceiling (0.4) | [-20, -700, 140] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 003 (1450) | PRACTICAL_BULB_DEAD | `F895DDBA4CD714E37F01868BB7D37D73` | 0 | [-20, 700, 125] | `65FF4B784080CAC6EEB318B8B15530D7` | SM_Bulb_A60_Clear (3.2) | [-20, 700, 148] | n/a | b | (-20, 700, floor+rest) |
| 003 (1450) | PRACTICAL_CLAMP | `817064014AFA20C3DA0381B826A67A8E` | 600 | [-58, -811, 139] | `AC5E922544D8FA99A4F58789BFE8385E` | SM_Lamp_Wall (1.25) | [-73, -722, 145] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 004 (2050) | PRACTICAL_BULB_DEAD | `6E43EFE54CF93B85512B61A024D21FAC` | 300 | [-46, 700, 194] | `C5A2693E4DA1D34DDAD77CA7ABCDD98D` | SM_Bulb_C35_Clear (3.2) | [-46, 700, 215] | 140..865 inside | b | (-46, 700, floor+rest) |
| 004 (2050) | PRACTICAL_CLAMP | `C270A80F44518BCC8083F587E409AD4F` | 200 | [-80, -720, 145] | `5BB977634D6AA462CA6BC397CCFC80C8` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 005 (2650) | PRACTICAL_BULB_DEAD | `54D4434D4C7DEE15DF0C40B542E8A77E` | 0 | [-38, 683, 133] | `15D5567A4FA29FCBF72891A1F9E1838D` | SM_Bulb_ST64_Cage (3.2) | [-39, 683, 160] | 500..1001 inside | b | (-39, 683, floor+rest) |
| 005 (2650) | PRACTICAL_CLAMP | `CCD03E624363DC9349FDCD9362F4A4CE` | 715 | [-68, -813, 123] | `C7726E33430FCE1FE1C74486FB30E044` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 006 (3250) | PRACTICAL_BULB_DEAD | `CCB8444C48E5A575D72758A0BECBB411` | 0 | [-40, 702, 203] | `FC7AF83E445093C69497D882E0A94DF9` | SM_Bulb_A60_Clear (3.2) | [-40, 702, 226] | n/a | b | (-40, 702, floor+rest) |
| 006 (3250) | PRACTICAL_CLAMP | `48F047734412015811AEAA830F91B05B` | 910 | [-104, -725, 140] | `73DA8E5A4DD19C8D9B9AC99712E1EC1F` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 007 (3850) | PRACTICAL_BULB_DEAD | `6364339441C3080229BE3A87D81121B4` | 0 | [-4, 691, 100] | `3368445B4D28BB9FDD183BBD2D720D2F` | SM_Bulb_C35_Clear (3.2) | [-4, 691, 121] | 140..865 inside | b | (-4, 691, floor+rest) |
| 007 (3850) | PRACTICAL_CLAMP (flash) | `687289AE4AE29F520729AF9347B2D9BC` | 585 | [-61, -818, 114] | `E03CEBD6450B6B3B1409B38349885139` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 008 (4450) | PRACTICAL_DEAD | `404F8CBC4FE1575C3A8EF0AB9505DE5C` | 0 | [-10, 700, 115] | `D81AE3C24242214716ED26AE07FD0763` | SM_Bulb_A60_Frost (3.2) | [-10, 700, 137] | 500..1001 inside | b | (-10, 700, floor+rest) |
| 008 (4450) | PRACTICAL_GLIMMER | `A1D1D15D4FE4ADEE49A71191DAA38186` | 160 | [-20, -700, 140] | `A58CCA914DBF34233156BBAA90E5E65D` | SM_Lamp_Ceiling (0.4) | [-20, -700, 140] | -651..-150 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 009 (5050) | PRACTICAL_BULB_DEAD | `5B6F0A4D4CC8648FDF3F3DA1AE428B86` | 0 | [-36, 715, 219] | `C11788E742D01BFFB7CE57913702E3F3` | SM_Bulb_G95_Clear (3.2) | [-36, 715, 246] | n/a | b | (-36, 715, floor+rest) |
| 009 (5050) | PRACTICAL_CLAMP (flash) | `D0C40D41497DA497E74D2392C3C930F0` | 910 | [-57, -717, 141] | `0C1D4E75407459B282D006A534C8C341` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -666..-139 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 011 (5650) | PRACTICAL_BULB_DEAD | `C403754341CFEAAE487B088A7C4F95BE` | 0 | [-42, 698, 104] | `FB685890475930E5C8C1A3BEF1375C63` | SM_Bulb_A60_Worn (3.2) | [-42, 698, 126] | 500..1001 inside | b | (-42, 698, floor+rest) |
| 011 (5650) | PRACTICAL_CLAMP | `211C8C2F4C5C26B5DE3B29BF3CA5232C` | 715 | [-46, -815, 121] | `F945D281400D79D779F5F58012EFF925` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -651..-150 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 012 (6250) | PRACTICAL_BULB_DEAD | `BD4F871D4459AB3F37B52CB19EA2C5BE` | 0 | [-40, 694, 170] | `F916388A45D34CDD1A89EC8DD73549A7` | SM_Bulb_A60_Clear (3.2) | [-40, 693, 193] | n/a | b | (-40, 693, floor+rest) |
| 012 (6250) | PRACTICAL_CLAMP (flash) | `71C5CECF49A857514A07C88F9FA6C28D` | 520 | [-99, -713, 149] | `0FCC7828428D6212AD5DD5A24E31229A` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -666..-139 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 010 (6850) | PRACTICAL_BULB_DEAD | `2EE5A2E44FB0EA7A2BF3E0B940773DA5` | 0 | [-43, 693, 143] | `D9F5F3D14BB9472ACB9348921F02D17F` | SM_Bulb_A60_Opal (3.2) | [-43, 693, 165] | 140..865 inside | b | (-43, 693, floor+rest) |
| 010 (6850) | PRACTICAL_CLAMP (flash) | `094B2758404B6C095825CD972D561029` | 910 | [-82, -804, 133] | `2E61E6554F4110F496F5FDB12BE0E993` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 013 (7450) | PRACTICAL_BULB_DEAD | `91D36FC64A964E14EE0A5DA8D48E09B8` | 0 | [-44, 681, 134] | `6DEFFB2449BA3F5E91652CBACC973585` | SM_Bulb_A60_Frost (3.2) | [-44, 681, 156] | 140..865 inside | b | (-44, 681, floor+rest) |
| 013 (7450) | PRACTICAL_CLAMP | `A99E4FB94D0E5E27B4537E858F09942D` | 910 | [-49, -804, 119] | `EFF9D72848227E8FC92730BCBC61DFA7` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 014 (8050) | PRACTICAL_L (flash) | `53271C244C3E43BF21754298EA34848C` | 1440 | [-20, -700, 150] | `884D59F344B5CCBF81D26EBED193F5C0` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -651..-150 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 014 (8050) | PRACTICAL_R | `580FD1994224BAD764B4AE82195E6298` | 0 | [-20, 700, 115] | `3200051446FB1C099C39BFAD5C90850D` | SM_Bulb_G95_Clear (3.2) | [-20, 700, 142] | 150..651 OUTSIDE | b | (-20, 621, floor+rest) |
| 015 (8650) | PRACTICAL_BULB_DEAD | `90E71DED4F0C7A16D08324A5BF21912F` | 0 | [-57, 713, 180] | `CDE00997485F6FC5788E2598342C8DDD` | SM_Bulb_A60_Opal (3.2) | [-56, 713, 202] | n/a | b | (-56, 713, floor+rest) |
| 015 (8650) | PRACTICAL_CLAMP | `AF906FBF40F207D147415CBB9EA5F5C4` | 715 | [-63, -737, 132] | `1D301483490D8C1EBC929090BA2BC71F` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -666..-139 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 016 (9250) | PRACTICAL_L | `EB38A1F046BDB3ACC47881A7BB9CE7FB` | 1440 | [-20, -700, 150] | `A58A0892426DFA4EC83DB89536251683` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 016 (9250) | PRACTICAL_R | `1323FF6442F8C848E474C6826CCFA445` | 0 | [-20, 700, 115] | `FED0623C426CE1A117903DA0FE9A8944` | SM_Bulb_A60_Opal (3.2) | [-20, 699, 137] | 140..865 inside | b | (-20, 699, floor+rest) |
| 017 (9850) | PRACTICAL_DEAD | `2B87AA544F6D666C203EC4AB171FDF1B` | 0 | [-10, 700, 115] | `633B4C2A42D98FEF75341CA1E36787D4` | SM_Bulb_G95_Clear (3.2) | [-10, 700, 142] | 150..651 OUTSIDE | b | (-10, 621, floor+rest) |
| 017 (9850) | PRACTICAL_GLIMMER (flash) | `004FA2164F0E970C46A12FB3F3D4B71D` | 160 | [-20, -700, 140] | `5CF2373946B9F1585CA8A7801664B103` | SM_Lamp_Ceiling (0.4) | [-20, -700, 140] | -651..-150 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 018 (10450) | PRACTICAL_BULB_DEAD | `C0278D254CC5AF16FC3359843FA73406` | 0 | [-19, 721, 148] | `E0CE01714FE502FD1CCE7E9FB853648F` | SM_Bulb_A60_Worn (3.2) | [-20, 721, 171] | n/a | b | (-20, 721, floor+rest) |
| 018 (10450) | PRACTICAL_CLAMP | `FFCB596149F980296635FEB91DEA4A50` | 780 | [-80, -795, 122] | `8B76F3D244F848564913348B482D79AD` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -666..-139 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 019 (11050) | PRACTICAL_L (flash) | `C2746FFC45AA6A1E025AC290C24F6D1E` | 1260 | [-20, -700, 150] | `CCE388C14EB792CD96F507AA37E62E17` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 019 (11050) | PRACTICAL_R | `3ED79B894CEABE0304E4309F47D30DCA` | 0 | [-20, 700, 115] | `FB83E0E64604773ABACB2AAC00438CAB` | SM_Bulb_A60_Opal (3.2) | [-20, 699, 137] | 140..865 inside | b | (-20, 699, floor+rest) |
| 020 (11650) | PRACTICAL_BULB_DEAD | `84811A8D4775BB11391039AC824EE8AB` | 0 | [4, 703, 133] | `D95795C646BFADDBEA01FF8495C2304E` | SM_Bulb_A60_Frost (3.2) | [4, 703, 155] | 150..651 OUTSIDE | b | (4, 621, floor+rest) |
| 020 (11650) | PRACTICAL_CLAMP | `BDF4BF5F4B5DA5DF18171F92FD928A5E` | 910 | [-58, -804, 138] | `ABE27952423FA234F5C4B7BBA8CF740C` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -651..-150 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 021 (12250) | PRACTICAL_L | `880601374C82F521D41BB0AAD054736D` | 1440 | [-20, -700, 150] | `79CEB8264857F22A6FE55380D8184661` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -666..-139 OUTSIDE | d | F2 removal (domestic); light+can stay unless also moved |
| 021 (12250) | PRACTICAL_R | `4C09C3CA40721782679D7F87972AC131` | 0 | [-20, 700, 115] | `78F46E3F4DB1C6B4CDD603832BE0468E` | SM_Bulb_A60_Frost (3.2) | [-20, 700, 137] | n/a | b | (-20, 700, floor+rest) |
| 022 (12850) | PRACTICAL_BULB_DEAD | `B8F83D4F4AA2AD18EBF7FBB2EFC8E2EB` | 0 | [-46, 708, 184] | `D67C358445BC328684405DBB51499F24` | SM_Bulb_A60_Clear (3.2) | [-46, 708, 207] | 140..865 inside | b | (-46, 708, floor+rest) |
| 022 (12850) | PRACTICAL_CLAMP | `18D7497C4787F95043ED14862E38F2F2` | 715 | [-61, -719, 129] | `38497AF544BD1BB9C9D727ADEF5AB79D` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 023 (13450) | PRACTICAL_L | `D51B462649C1111E7E270785AC73E8B7` | 1440 | [-20, -700, 150] | `E8FE77634BEE8D094584EBB0A19A9B1E` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 023 (13450) | PRACTICAL_R | `859A5AC34BCBF9FEB1133C882BCC1576` | 0 | [-20, 700, 115] | `FB688BAD4DDEE5BA32FA8F9D611C3954` | SM_Bulb_A60_Worn (3.2) | [-20, 700, 138] | 500..1001 inside | b | (-20, 700, floor+rest) |
| 024 (14050) | PRACTICAL_DEAD | `026B2D104B36EF82F269C58E70424BE7` | 0 | [-10, 700, 115] | `82BE65D84D7EEDABE93D59B59E6EFA4B` | SM_Bulb_ST64_Cage (3.2) | [-10, 699, 142] | n/a | b | (-10, 699, floor+rest) |
| 024 (14050) | PRACTICAL_GLIMMER (flash) | `018DFE69422093E054846DAAA6F21FD2` | 160 | [-20, -700, 140] | `B584D98349AC5E222577678134845257` | SM_Lamp_Ceiling (0.4) | [-20, -700, 140] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 025 (14650) | PRACTICAL_BULB_DEAD | `B8FF3969477A1CD3637005A1248C7A18` | 0 | [-41, 690, 129] | `29D106F148F73D168BD2589513078315` | SM_Bulb_A60_Opal (3.2) | [-41, 689, 151] | 140..865 inside | b | (-41, 689, floor+rest) |
| 025 (14650) | PRACTICAL_CLAMP (flash) | `7EC39A434F74CBBB07D6368E33450FC2` | 780 | [-67, -797, 152] | `F91839A94CD7ABCCCB49F8A626E8789D` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 026 (15250) | PRACTICAL_L | `7C1AD8D1428BCCC64FA336853D86038E` | 1260 | [-20, -700, 150] | `EBD1A77A48BE82A3110CAA8E7A98E2FA` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 026 (15250) | PRACTICAL_R | `4040692A4D9123EDE587368657A9AE6B` | 0 | [-20, 700, 115] | `EF75F2D94662AAB1B9B977855DD12E20` | SM_Bulb_G95_Clear (3.2) | [-20, 700, 142] | 500..1001 inside | b | (-20, 700, floor+rest) |
| 027 (15850) | PRACTICAL_BULB_DEAD | `216A441841C7DB24A7ADC284C51462F9` | 0 | [4, 690, 121] | `1C6310924D060A55DF6889BC37AD2445` | SM_Bulb_A60_Worn (3.2) | [4, 690, 144] | n/a | b | (4, 690, floor+rest) |
| 027 (15850) | PRACTICAL_CLAMP | `EBBB83EE4C042DB9550F549A08EBAB77` | 910 | [-33, -820, 146] | `46E50B0549A0AE14EFCC1FBF146CC0A2` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 028 (16450) | PRACTICAL_L | `A23CD8864A562C5A0CD00FB73193CB8D` | 1440 | [-20, -700, 150] | `08A3FC6E49B82BB76D266CB4AA0B4FD4` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 028 (16450) | PRACTICAL_R | `B564DE6B451DE5EC5466F3B079854696` | 0 | [-20, 700, 115] | `43813411495FB3FD6090B9ABE5F7EDE5` | SM_Bulb_A60_Clear (3.2) | [-20, 700, 138] | 140..865 inside | b | (-20, 700, floor+rest) |
| 029 (17050) | PRACTICAL_BULB_DEAD | `AE8A06DF429F4C360CA90F83431C079A` | 0 | [-64, 688, 209] | `D6565F164CEA7F11FA8F7CA304B55517` | SM_Bulb_A60_Frost (3.2) | [-64, 688, 231] | 500..1001 inside | b | (-64, 688, floor+rest) |
| 029 (17050) | PRACTICAL_CLAMP | `29BB7B2C44546DBCC9C80DA5336D68C8` | 715 | [-91, -715, 147] | `5CD48C6A476AEA6E2E0227AA9E53BF68` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 030 (17650) | PRACTICAL_L | `984BAC3D45861936A31F33AB5FA50E82` | 1440 | [-20, -700, 150] | `6EA39F0349B62D379DB6869D1CEEED1D` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 030 (17650) | PRACTICAL_R | `A7CF87FE43BFF8C7438182A549700A4A` | 0 | [-20, 700, 115] | `C0DA5D894EAE9784FF291A8885C00858` | SM_Bulb_ST64_Cage (3.2) | [-20, 699, 142] | n/a | b | (-20, 699, floor+rest) |
| 031 (18250) | PRACTICAL_DEAD | `8B89F0D64218FF7DC54B13A9BA7C96F9` | 0 | [-10, 700, 115] | `0019045E4F59F4302B717BB4AC358FD4` | SM_Bulb_G95_Clear (3.2) | [-10, 700, 142] | 140..865 inside | b | (-10, 700, floor+rest) |
| 031 (18250) | PRACTICAL_GLIMMER | `EA1ABA8046A3C41FB5806490FC35B9B8` | 160 | [-20, -700, 140] | `84EFD359454695A0B54E36A3ACA13F15` | SM_Lamp_Ceiling (0.4) | [-20, -700, 140] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 032 (18850) | PRACTICAL_BULB_DEAD | `043923534C6B72B7034965B4DE6E0919` | 0 | [-41, 723, 119] | `B6CBE33846EB68670FEB4C87CC0B3236` | SM_Bulb_A60_Opal (3.2) | [-41, 723, 141] | 500..1001 inside | b | (-41, 723, floor+rest) |
| 032 (18850) | PRACTICAL_CLAMP | `CAE6EC0D46B62B27969D638FB077DAE5` | 780 | [-44, -815, 152] | `E3F9492D472E0BC1229C99B671AC8FAA` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 033 (19450) | PRACTICAL_L (flash) | `1DF5300042F5848C4E564D8C4A1155F0` | 1260 | [-20, -700, 150] | `D294CBEB435BA7D58E8B50A6628BDE93` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 033 (19450) | PRACTICAL_R | `C82071AD463477F49C65A8B6932C83E8` | 0 | [-20, 700, 115] | `181B5C6D45B0AED272CE90BB2B07D147` | SM_Bulb_A60_Worn (3.2) | [-20, 700, 138] | n/a | b | (-20, 700, floor+rest) |
| 034 (20050) | PRACTICAL_BULB_DEAD | `A648637142817D2E074A029674CE3DF0` | 0 | [-25, 724, 141] | `025D7CA6402F79C84F69E4B4E05707B8` | SM_Bulb_A60_Opal (3.2) | [-25, 723, 163] | 140..865 inside | b | (-25, 723, floor+rest) |
| 034 (20050) | PRACTICAL_CLAMP | `508547A743FF2A2D499B40B00B7B8E0B` | 910 | [-59, -788, 127] | `7292B1134ABD9B3E1E2F47989CF2B116` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 035 (20650) | PRACTICAL_L | `A5D532D84ABD2A34DFB06DBC9260B770` | 1440 | [-20, -700, 150] | `BC6751004DB0BDC7D13FAD8185686229` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 035 (20650) | PRACTICAL_R | `6F48B0814A6071544803AC9C10B3C797` | 0 | [-20, 700, 115] | `63180D1B47086F0668ABFD9E199F7374` | SM_Bulb_ST64_Cage (3.2) | [-20, 699, 142] | 500..1001 inside | b | (-20, 699, floor+rest) |
| 036 (21250) | PRACTICAL_BULB_DEAD | `566522D9406FAB6F96596B9AAF2C8434` | 0 | [-24, 720, 188] | `474174CF4ADA65879D927CA32527E4A2` | SM_Bulb_ST64_Cage (3.2) | [-25, 720, 215] | n/a | b | (-25, 720, floor+rest) |
| 036 (21250) | PRACTICAL_CLAMP | `656AE7DA49BF1F31D7CEACAACD42A8C3` | 715 | [-92, -709, 128] | `F95461CB48CE8906CDA5E1A3E34CDC52` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 037 (21850) | PRACTICAL_L (flash) | `59A61CC941CE05B93E4A29BDE3310D2F` | 1440 | [-20, -700, 150] | `6E34A3A94A9133F82A1B649E38A84136` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 037 (21850) | PRACTICAL_R | `624F6B1C46B6D3870CB3A0A310C377FA` | 0 | [-20, 700, 115] | `8D645090494E45A693A30EA9E1B26E36` | SM_Bulb_G95_Clear (3.2) | [-20, 700, 142] | 140..865 inside | b | (-20, 700, floor+rest) |
| 038 (22450) | PRACTICAL_DEAD | `95FA85BD4EABED42AF1DFD91995035B4` | 0 | [-10, 700, 115] | `04988CB7420FBEF35D3F0190EABD76BB` | SM_Bulb_A60_Frost (3.2) | [-10, 700, 137] | 500..1001 inside | b | (-10, 700, floor+rest) |
| 038 (22450) | PRACTICAL_GLIMMER | `BB51E8BF4924A92DB6281B81CDB3868D` | 160 | [-20, -700, 140] | `9A56F2AE46B0A51F957402A20AE5E4A7` | SM_Lamp_Ceiling (0.4) | [-20, -700, 140] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 039 (23050) | PRACTICAL_BULB_DEAD | `98390F5E4C2D5FBF85507280EFA768A8` | 0 | [4, 718, 110] | `586489BD41519A143D0D62AABECE9B62` | SM_Bulb_A60_Worn (3.2) | [4, 718, 133] | n/a | b | (4, 718, floor+rest) |
| 039 (23050) | PRACTICAL_CLAMP (flash) | `B079879844A20B47A9E4B28D8F8D6329` | 780 | [-78, -787, 143] | `C6E3C7084003F1C887E16FAECEB012DF` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 040 (23650) | PRACTICAL_L (flash) | `4D03703A40BC9636988C8EB9211530D5` | 1260 | [-20, -700, 150] | `0276473E46FA9F2892280BB274AF6385` | SM_Lamp_Ceiling (0.5) | [-20, -700, 150] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 040 (23650) | PRACTICAL_R | `CD4D652944105B7B733E829897DA9BE9` | 0 | [-20, 700, 115] | `23DE3E964F0F03472F88E6810592185B` | SM_Bulb_A60_Worn (3.2) | [-20, 700, 138] | 140..865 inside | b | (-20, 700, floor+rest) |
| 041 (24250) | PRACTICAL_BULB_DEAD | `B209F7714823ECF12E0C7A996EB79127` | 0 | [-29, 691, 125] | `A9A06E0C4E2B2F93D796FDA9B49E9789` | SM_Bulb_G95_Clear (3.2) | [-29, 691, 152] | 500..1001 inside | b | (-29, 691, floor+rest) |
| 041 (24250) | PRACTICAL_CLAMP | `3C9EED1B4439277792F194ABD1998DFC` | 650 | [-40, -792, 115] | `74E684B942E3198F7CD16D8D796E460F` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 042 (24850) | PRACTICAL_BULB_DEAD | `3C37D9954E2A2065D6863D980A3C692A` | 0 | [-38, 725, 122] | `8F9252AC45E76BB24A1A5EBA8F6AF10B` | SM_Bulb_A60_Worn (3.2) | [-38, 725, 144] | n/a | b | (-38, 725, floor+rest) |
| 042 (24850) | PRACTICAL_CLAMP | `B28B0B544F72251EA328F6AF2F44E2CB` | 975 | [-69, -803, 162] | `C489DEE646017610C73A8491EAB07B3C` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 043 (25450) | PRACTICAL_BULB_DEAD | `BC1D9BE5449802486CF4FD88A79D924C` | 0 | [-24, 695, 176] | `634FC202482EE0FAACA65DAB4E105E61` | SM_Bulb_A60_Clear (3.2) | [-24, 695, 199] | 140..865 inside | b | (-24, 695, floor+rest) |
| 043 (25450) | PRACTICAL_CLAMP | `64FD3E8F4AC81F48BE7A2B994C047DD9` | 1105 | [-81, -730, 139] | `BB3F591A42F92AE7DA31F09EEA42B530` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 044 (26050) | PRACTICAL_DEAD | `26B88E644949619168281E84FE9F9205` | 0 | [-10, 700, 115] | `72F3ABC64DC2A0CA5BE950B7D24DB6BD` | SM_Bulb_A60_Worn (3.2) | [-10, 700, 138] | 500..1001 inside | b | (-10, 700, floor+rest) |
| 044 (26050) | PRACTICAL_GLIMMER | `AF0A1D63449177E73B7A9982AA5B9E9C` | 160 | [-20, -700, 140] | `72CDB22C4ECFCDE3B8FC258A27DB5456` | SM_Lamp_Ceiling (0.4) | [-20, -700, 140] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 045 (26650) | PRACTICAL_BULB_DEAD | `B1A810EA46188272502B39A308EB21CF` | 0 | [-11, 680, 137] | `F6942ECC4B72D1F0886066AE0B94A691` | SM_Bulb_G95_Clear (3.2) | [-11, 680, 163] | n/a | b | (-11, 680, floor+rest) |
| 045 (26650) | PRACTICAL_CLAMP | `8114F24844545D84551430A7360F664B` | 1105 | [-38, -811, 145] | `D15FC22449A6F4B812BDAEBF6374B983` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 046 (27250) | PRACTICAL_BULB_DEAD | `B1E8089D43E7275FC19345A1B89339B9` | 0 | [-63, 700, 170] | `62E2A7F34D21AD88DAD7CFBC7C368F1E` | SM_Bulb_A60_Opal (3.2) | [-63, 699, 192] | 140..865 inside | b | (-63, 699, floor+rest) |
| 046 (27250) | PRACTICAL_CLAMP | `14CF3594413FB50590E7488AF97AB57A` | 910 | [-79, -728, 143] | `D9CE4F6B4B4FEF6C77169E8E1E350EC7` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -866..-142 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 047 (27850) | PRACTICAL_BULB_DEAD | `D115B96F4EBDD10DB6155F93B4948F8D` | 0 | [-22, 677, 136] | `7FDEB31A4F986B225F0643A8111BE3A1` | SM_Bulb_A60_Opal (3.2) | [-22, 676, 158] | 500..1001 inside | b | (-22, 676, floor+rest) |
| 047 (27850) | PRACTICAL_CLAMP | `FE2068A84C07545DC361C1898322A2F5` | 1170 | [-41, -827, 136] | `EFB5C5CE4AB5777F76784388FDFB3C11` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1001..-500 inside | d | F2 removal (domestic); light+can stay unless also moved |
| 048 (28450) | PRACTICAL_BULB_DEAD | `D6529E0F4A64043DA93DA8A06350BB87` | 0 | [-68, 700, 194] | `41FB21A246FDEF81B82074B823B5FD75` | SM_Bulb_A60_Frost (3.2) | [-68, 700, 217] | n/a | b | (-68, 700, floor+rest) |
| 048 (28450) | PRACTICAL_CLAMP | `AD2A09B64A48088A69DC67B9F1F7F2F5` | 1040 | [-96, -708, 169] | `4FE9DEF14F3910EF1EEFDEBE19398656` | SM_Lamp_Wall (1.25) | [-30, -720, 145] | -1016..-489 inside | d | F2 removal (domestic); light+can stay unless also moved |
