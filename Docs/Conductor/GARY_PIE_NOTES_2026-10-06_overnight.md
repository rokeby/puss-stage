# Overnight plan — 6 Oct (Gary's answers ~00:40–00:55, his own session with the conductor)

- **Look applies:** "Apply all, stills for the morning" — every lighting change goes in tonight (each reversible, one REVERT per passage); stills for review.
- **P06 wings:** "Swap tonight with ceramic towers" — routed to Wings & Textures (they write the swap; conductor runs DRY/stills/APPLY).
- **C++ tonight (if ready by build time):** club "mover" spots (P05); bulb glass follows its light — per bulb STABLE / SLIGHT flicker / FAIL
  ("a flickering and dying bulb, not all bulbs! some should flicker only slightly and others be stable").
- **Rain:** "Prototype rain tonight" — P04, bench only, stills; nothing saved into the show.
- **Song markers:** refresh to Cameron's tracks (bar/§ grid for timing camera moves; GO markers untouched).
- **Tubes:** everywhere, low glow, 20% blinking; light only from fence-top rows outside P02.
- **Build:** yes — HUD (bay/cue/sequence), hold-Left rewind, light events, tubes, hangar-snap diagnostic/fix (+ movers, bulb glass).
- **P06 music:** the current Into Void track.

Editor order: S3 backdrop+marble -> S1 extend 245 s + narration after voices -> song markers -> P06 tail -> Opening -> P02 straighten (+handoffs, route actors)
-> retime P02–P05 -> P03 floor -> P06 wing swap (W&T) -> lighting P01–P06 (stills each) -> tests -> build -> reopen -> tubes -> rain bench
-> fog bench (after midnight) -> stills of every passage.

## Timing (Gary ~01:30): "transport gets confused or frustrated by something to do with sound or passage or sequence timing being out of sync"
- **Measured tonight:** the managed Master's section boundaries are NOT exactly the compiled Show segments — P06's end was 2 ticks
  SHORT before the rebuild (50603057 vs 50603059) and 2 ticks LONG after it (50973621 vs 50973619); Scene 6 started 2 ticks early.
  It tripped the P06 tool twice (Don't-Save restarts). A boundary frame can therefore belong to P06 by one clock and to Scene 6 by the
  other — a plausible contributor to "arrive at the hangar, camera snaps after a pause". Routed to the C++ build pass: find the rounding,
  check which clock the transport/CueDesk/Pilot uses, check audio pause/resume, fix if proven, else a cvar-gated two-clock logger.

## Overnight log (conductor)
- 01:18 **S3** backdrop restored (squashed by the 3 Oct far-wall rescale) + 8 marble tiles to 28.8 m (S3BWM-20261006-011800).
- 01:19 **S1** extended to 245 s (cuts cover, handoffs unmoved, Master match) + narration after Animal_Voices_1, 208.64–243.64 s.
- 01:19 **Song markers** refreshed (P01 35→28, P02 24→23, P03 16→17, P04 15→16, P05 90→16; no GO markers present).
- 01:24 **P06** +15.44 s → 126.0 s (two Don't-Save restarts first: the tool read section ranges as float seconds — a ~2-tick READ
  error, NOT Master drift; corrected by the C++ agent's float32 round-trip proof; gates now tolerate 8 ticks).
- 01:32 **Opening** applied: strobe on the 36.2 s entry, swivel 43.8–50 s, smooth rise to the curtain, warmers off (their live
  cones were 14.9/15.9, not the 33 recorded on 4 Oct — the cone write is parked as moot).
- 01:43 **P02 straighten HELD** for a supervised session: with the DOCK anchor P02's mouth moves 97 m / −66°, stranding the I1
  sleight mouth camera, the I1 stalls camera, the S2 handoff cameras, the car light and the lantern (no re-place tool for the I1 sleight).
- 01:46 **Retime P03 180→42.24 s (~262 cm/s), P04 180→50.40 s (~214 cm/s)**; tests green. **P05 refused**: 93 bays in 44 s =
  1070 cm/s and a tail shorter than the settle — needs Gary's call (keep long, loop/extend the song, or cut bays). P02 waits for its straighten.
- 01:47 **P04 back curtain** lead after the retime = 3.87 s (needs ~2.2 s) — left as is; restoring 5.0 s is one APPLY (−1.13 s) if wanted.
- 01:47 **P03 floor STOPPED (nothing saved)**: Ground off also blanked the Structure **Fixtures** and **Gridiron** layers. Parked;
  P02's floor step has the same flaw. Needs a different method (hide only the board layers, or bury them).
- 01:50 Build started with 7 held patches (LE, HD, RW, SD, TU, BG, MV).

## Gary ~02:00 answers
- **P04 back curtain:** restore the fall lead to **5 s, always** (re-fit after any retime).
- **Shadow-play spot:** after each Scene's curtain falls into the boy-cat-shadow (I1–I5), a large central spot lights the curtain,
  soft but defined edge — the placeholder for the shadow play — held until the next cue (lights down, curtain falls to the next P).
  Tool: shadow_play_spot.py (per Interaction; inner_ratio raised for a more defined edge).
- **Curtain pictures:** UV-mapped, printed on the cloth (squashed by the pleats).
- **P05 blue-sky curtains:** cascade starts at P05's beginning and moves with the walk but completes in HALF the walk time; full fence height, no taller.
- **P01 "flickers nicely" beam:** the gobo one — bay 20's orange BEAM_R (as assumed), "maybe".
- **Bunched drop:** questions the 3–4 day estimate — re-estimating the bake alone (overnight bake).
- **Bulb + housing:** Gary makes them in Fuser tomorrow as separate assets — prompts to be written.
- **Research:** a better curtain fabric (effective velvet that responds to the lighting, or another textile); animated gobos for
  the shadow puppetry from iPhone videos of live puppets (cheap stop-motion gobos in front of lights).
- 02:00 **Build 2 (FIX1)**: suite **208/0** (HUD, rewind, seam diag, tubes, bulb glass, movers, light events all in).
- 01:56 **Shadow-play spots I2–I5** applied (3.6 m circle — the frame is only ~4.4 m tall; edge inner 85 %; held to the GO,
  1 s fade into the drop). **I1 refused**: its sequence bindings changed since the sleight record (hand edits?) — Gary to check I1.
- 01:52 **P04 back curtain lead = 5.0 s** (BLF-20261006-015230).
- W&T slot: P04 gallery re-place, edge v2 on pillar1 L (P01 before/after stills), Pillar2 R, chinoiserie → ceramic towers (P06
  before/after stills), HF kit P02–P06 (P01 parked for the edge verdict). **Editor crashed (out of memory) on the hand-print atlas
  import** — nothing saved was lost; W&T is making the import lighter; hand prints not placed tonight.
- 02:17 **Structures 01/02/04/06 were stale** after the wing placements -> re-fit (REFIT-20261006-021730); only Ground board counts changed (boards re-rolled; cosmetic).
- 02:18 **P01 lighting held**: the score REVERT refuses — the house warmers on P01 Wing 001 differ from the score's record (Opening
  switched them off tonight; cones/intensity/reach had also been hand-changed: inner 12.4, 800 cd, 3467 cm). Needs a morning
  reconciliation before P01's fairy-tale colours can go in. P01 lamp re-hang being restored.
- 02:23 **Tubes everywhere** applied (all 6 structures; low glow, ~20 % blink; light only from fence-top rows outside P02).
- 02:23 **P04 strobe → local halo** (20000→3500 cd, reach 1500→450 cm, ghost 1.0→0.35; originals saved).
- 02:30 **P06 car drive-by** placed on the 68.55 s music change (first attempt stopped on a tool bug, fixed).
- 02:31 **Lighting drift report** (Docs/Conductor/LIGHTING_DRIFT_2026-10-06.md): hand-tuned lamps P01 4, P02 12, P03 0, P04 1, P05 0, P06 2.
  **P01/P02/P04/P06 rescoring HELD** — re-scoring would overwrite Gary's hand tuning; decide keep / overwrite / fold-into-score per light.
- 02:33 **P05 relit** (round 2: sky spots + fills bays 1–6, blink 7–12, all-on 13–18; dim bulbs; movers skipped until the C++ field is wired).
- 02:35 **P03 relit** (round 1+2: side lights only in bays 4/8/13/18, own-side tops, live practicals, no-cross PASS 46 spots, shadows 54→49).
  **Regression:** P03's 14 lamp housings could NOT be re-dropped (the housing tool's source DRY predates the girder phase A: beam depth
  34 vs live 90 → DRY_SOURCE_STALE). They are back at their pre-5-Oct height. Fix in the morning (refresh the housing source).
- 02:37 Tests green after the P03/P05 relight. **Morning stills** of P02–P06 at 0.1/0.3/0.5/0.7/0.9 (all 25 frames captured; the
  drift flags are flicker): Saved/CodexConductor/PassageStills/PSTILLS-P0n-20261006-06*-morning. P01 edge before/after and P06
  chinoiserie before/after are in the same folder.
- 02:42 **Rain bench: not authorable from Python** (the engine template has no stateless emitter) → Niagara session tomorrow with the fires.
- 02:43 **Fog bench**: PREPARE ok; CAPTURE failed at once on an untested API call (pp_sources: AttributeError) — nothing changed;
  PIE ended; Don't-Save restart cleared the bench mist actors. Fix + run in a supervised session.

## Morning: what needs Gary
1. **Lighting hand edits** (Docs/Conductor/LIGHTING_DRIFT_2026-10-06.md): P01 4, P02 12, P04 1, P06 2 hand-tuned lamps — keep /
   overwrite / fold-into-score per light; then P01/P02/P04/P06 get their new scores.
2. **P02 straighten**: the I1 sleight mouth camera, stalls camera, S2 handoffs, car light and lantern need re-placing (supervised).
3. **P05 retime**: 93 bays can't fit the 42 s song (1070 cm/s) — keep long, extend/loop the song, or cut bays.
4. **P03 floor**: Ground-off blanks Fixtures + Gridiron — new method needed (also P02's floor step).
5. **P03 housings** are back at their old height (source DRY stale) — refresh and re-drop.
6. **I1 shadow-play spot**: I1's bindings changed since its sleight (hand edits?) — check, then apply.
7. Edge v2 verdict (P01 stills) → HF P01; chinoiserie → towers look (P06 stills); hand prints (lighter import pending, W&T).
8. Snap after pause: run with `InfinityStage.SeamDiag 1` and reproduce; HUD toggles with H; hold Left rewinds.
