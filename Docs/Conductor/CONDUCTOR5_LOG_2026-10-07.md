# Conductor 5 log — 7 Oct 2026 (from ~16:45 UTC)

## Gary's answers (this session, 7 Oct ~16:50 UTC — his own words, summarised)
- **S3 washed out** — investigate *after his PIE*. Measured: held stills PSTILLS-S3-20261007-144232-held mean luma
  248 / 245 (p5 241 / 240) [meas]. Cause not yet investigated.
- **S4 entry — redesign (creative brief, Gary):**
  - Observed in PIE: during the glide the children are static (expected) but the **pendulum swings in the wrong
    place**; after the glide her sequence starts from that angle, the pendulum keeps swinging at the wrong angle, the
    children animate correctly, but **the camera comes to rest behind the P4–S4 transition curtain**, blocking the view.
  - Wanted: a **different glide entry view** that shows the scene **in darkness**; **strike lights** on the
    children / pigeon / etc. with their animation **already in motion** (no static assets seen); then **cut into
    Klara's first shot**, where the animation **restarts** (they idle at first, so the restart goes unnoticed) and her
    cuts play normally.
  - Lighting **like S1**: near-total darkness with only faint rig lights showing the rig rising into place; Klara's
    lights strike **one by one** during the glide-in; then cut into her sequence.
  - Supersedes the handover's "keep her set hidden/unlit until the hand-over" offer.
- **S2 length** — Gary will **ask Klara** (no offline scan).
- **Morning build** (W&T sound a7c89c5 + fence top-row patch, then barbed_apply "nw") — run **when Gary is done in PIE**.

## Work
- S4 entry: read-only investigation running → `Docs/Conductor/S4_ENTRY_INVESTIGATION_2026-10-07.md`.
- Klara wings → Flat V3 (Gary 7 Oct): "is it OK or useful to update Klara's wing asset with v3 while being able to
  bring them back in with perfect consistency" — read-only feasibility running →
  `Docs/Conductor/KLARA_WINGS_V3_FEASIBILITY_2026-10-07.md`. Her wings: S1 Animals L/R/ceiling, S2 Shrine ceiling,
  S4 Children L1/L2/R2 (census_report.md:80-117; some are redirector collisions with our StageTest actors).
  - Gary clarified: "bring back" = **replace in place** (same position, scale, etc.) — the question is an exact
    in-place V3 replacement of her wings, not revert/re-ingest.
  - **Report in** (KLARA_WINGS_V3_FEASIBILITY_2026-10-07.md): feasible + revertable, NOT exact (pivot centred vs
    backbone edge, depth/flap, outline smoothing ~3 cm, skin changes the art); base/top/inner edge/art plane
    holdable to ~0.5–1.5 cm via the rzswap REMAP method on live bounds; needs a new actor-level tool (rzswap/swapkit
    only write Show panels). Low value now (Plan A = her cinematic as video, REVEAL_PLAN.md:22). Recommendation:
    not now. Spot-checked: klara_reveal.py:2758-2771 saves her maps (backup + allow-list) [decl]; REVEAL_PLAN.md:22 [decl].
- **S4 entry report in** (S4_ENTRY_INVESTIGATION_2026-10-07.md): curtain = HER first shot dollies back to x 10241,
  209 cm behind the P04 backcloth (x 10450) from her frame ~780; glide itself ends in front. Pendulum = BP_Pendulum_C_0
  with its own Tick rotating PivotRoot (fights her LS keys, which start at her frame 191). Plan: klara_reveal v5
  `strike_preroll` + klara_preroll_s4.py; DRY gate on her whole camera path. Spot-checked klara_reveal.py:237 and
  args reveal_style_note [decl].
- **Gary's S4 answers (~17:40 UTC):** curtain → "back cloth should be on the floor by this point, and kept there";
  pendulum → turn its own Tick swing off in the show (probe first); strikes → like S1 flicker strikes; pre-roll → whole glide.
- **Gary, S4 EXIT (~17:55 UTC) — "excellent, with amendments"; aim for ALL scenes with shadow interaction:**
  1. End of her sequence has a long tail (~20 s) where nothing happens → trim.
  2. Lights go off at the end → in MORE STEPS; ends in darkness where camera/assets move invisibly (good, keep).
  3. Then a light appears on the back wall reflecting on the floor (great) — BUT the **curtain must already be there
     BEFORE** the spotlight slowly comes on: the shadow interaction plays **ON the curtain**, not on a separate shadow
     card (**Gary removed the shadow card himself in the editor** — check saved/dirty state before any write).
  4. After the shadow scene: light dims, the curtain switcheroo is already made, the curtain falls, revealing the next
     Passage.
- **S3 white — ROOT CAUSE [meas]:** 'S3 Hangar Pinned Exposure' BlendWeight is keyed only in LS_S3_HangarRise
  (Hangar Fold sub-section [0,744) = 31 s); weight 1.0 at +10/+30 s, 0.0 at +33/40/55/78/182 s (own PIE,
  s3_white_probe_S3WHITE-r*.json; scene_exposure_weight_read.json). Camera then gets the unbound PPV (EV100 −3) → white.
  This morning's holds kept transforms only; the tool's own not_held_rise_tracks lists the exposure weight, ~12 rise
  light intensities and **P04 Backcloth GeometryCache** (→ backcloth back to hanging in S4 = Gary's curtain note).
  Same structure in S1/S2/S4/S6. Fix being written offline: hold float + cache rise tracks past the fold
  (HANGAR_HOLD_FLOAT_EXTENSION_2026-10-07.md). Probe bug fixed: scrub phase now FAILS on refusal (in-S3 scrubs refuse
  UNSAFE_EXTERNAL_CLOCK; fresh PIE per sample).
- Exit/shadow-curtain plan in: SCENE_EXIT_SHADOW_CURTAIN_PLAN_2026-10-07.md (Gary's I4 card removal SAVED 17:05).
- **S3 white FIXED [meas]:** float hold APPLY S3FLOATHOLD-20261007-132954 (DRY S3FLOATHOLD-20261007-132933: held 50,
  refused 0, conflicts 0; exposure weight 1.0 + 49 light intensities over [744, 6240)). Census clean; SavedMasterMatchesShow
  + SceneCutBindingsResolve green. Re-probe: weight 1.0 at +30/+33/+78/+182 s (was 0.0). Still PSTILLS-S3-20261007-173228-floathold
  00_f300 luma 110 (was 248); 01 failed scrub_refused (in-S3 scrub vs the singer clock; stills-tool limit).
- Morning build: patches applied to the tree + Backups/PreMorningBuild-20261007-1315; **editor close was blocked by the
  permission classifier** — waiting for Gary to close the editor (Don't Save).
- S4 entry v5 tooling in (S4_ENTRY_V5_BUILD_2026-10-07.md): harness v5 27/27, existing 75/75 [meas, conductor re-ran: OK].
  v5 DRY needs the S4 backcloth/cache hold first; cache hold NOT implemented (headers give no clean last-frame hold;
  PIEPROBE mode added). Note: backcloth section already ends at S4 +3.0 s KEEP_STATE — "reverts to hanging" UNMEASURED.
- **Pendulum PROBE [meas]** KLARAPENDULUM-20261007-134048 (own PIE, played S4 from +3 s): verdict tick_wins. t10s: at
  level loc (12300.8, 240040.3), pitch 2.6→1.2 per tick, tick on. t24s (her frame 240): LS location (12810.8, 240090.3)
  but rotation yaw 0 / pitch 10.7→9.0 from the tick vs LS-predicted yaw 130 / pitch −1.6. Fixes: probe used
  LevelSequenceActor.get_sequence_player (absent in 5.8 Python) → transport time; v5 harness baseline pinned to 8cb2830
  (HEAD-compare skipped after ae84495 and a v4→v5 routing mutation survived). Harnesses OK again. Pendulum APPLY waits
  for the v5 order (after reveal v5 + pre-roll).
