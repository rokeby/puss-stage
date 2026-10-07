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
