# Lighting direction notes (living document)

Gary's direction for each passage, in his words where quoted, with what the show does today and what each note needs.
Add to this as you direct. It feeds the score data (`Saved/CodexConductor/lighting_scores.json`) and any small build.

How to read the "today" lines: the scores were applied on 5 Oct overnight (P05 on 4 Oct). Each is the 4 Oct
proposal in `LIGHTING_SCORES_PLAN_2026-10-04.md` ("Every score is inferred: a proposal for Gary"). So where a note
below differs from "today", the note wins.

---

## P01: the magical introduction (Gary, 5 Oct)
> "Passage one uses full, rich, theatrical lighting to achieve the magical introduction."

- **Today:** dark walk-in, then a hallway ping-on (bays 3–12 strike ahead of the camera), then warm theatrical
  pools with candle-moody bays (W/c). TOP lamps are being re-hung under the new iron girders, ~1.3 m lower (5 Oct).
- **Fits the note?** Mostly. "Full, rich" suggests fewer GAP bays and fewer candle-dim bays than today's score
  (it has a GAP about every 6–7 bays, and c7–c8 levels). Judge in PIE first.
- **Needs:** score data only (levels, fewer gaps). No build.

## P02: the breakdown (Gary, 5 Oct)
> "Passage two is already more broken. Many of what would be the stage lights are blinking or completely off,
> while we actually mostly make use of what feels like the theater's fluorescent lighting and cold lighting upon
> these lurid, organic wings. Perhaps this … breakdown and shift comes in halfway through passage two, and that's
> where we could also try out things like the window car light."

- **Today:** "industrial night": sodium side light plus one gel pop per bay (magenta, acid green, oxblood),
  then a mystic run to the shrine in bays 21–23. It is warm/sodium, not cold, and nothing is failing.
- **What the note asks for:**
  1. **First half (bays 1–~11):** stage lighting still mostly working. Theatrical, perhaps already a little unwell.
  2. **The shift at ~bay 12:** the stage lights start to fail: blinking, then off. The P06 failing generator
     already does exactly this (fixed failure order, ignition stutter, lamps that decay or snuff), so it can be
     reused here.
  3. **Second half:** the light that is left is the theatre's own working light: cold fluorescent tubes (the
     INDUSTRIAL look's 5000 K "flickering cold-white tube", HUM/BUZZ/FAULT flicker materials) falling on the lurid
     wings. Cold against lurid colour is the point.
  4. **The window car light** (below) tried here, in the second half.
- **Needs:** a P02 rescore (data: two segments plus a FAILING segment, like P06's), then REVERT + APPLY of P02's
  score. No build, except the car light if it's done as a reusable actor.
- **Open:** does the shrine run (bays 21–23) keep its mystic look, or is it cold too?

## Window car light: a moving headlight effect (Gary, 5 Oct)
> "Moving lamps, which had a similar effect to traffic outside of a window, headlights projecting onto the wall,
> and curving off or moving past at a diagonal … a projection through the gaps in the sides of the passage that
> moves at a certain rate, creating a change in both shape and angle of the projection."

- **How it works:** a lamp outside the wing line, moving along a path. The light through the wing gaps slides,
  stretches as the angle flattens, skews on a diagonal, and is cut by wing edges. All of that comes from the lamp's
  movement alone, with no animated shapes.
- **Must cast shadows** (or nothing breaks through the gaps).
- **Two routes:**
  1. **No build:** a spot or rect light keyed in Sequencer (start → end over a few seconds, intensity fade in and
     out), with a soft headlight-pair mask (light-pattern series 72–75 style). Try it on one cue first.
  2. **Small build (held patch, one build window):** `AInfinityStageSweepLight`, like the strobe actor.
     Path (line, or arc to "curve off"), speed, repeat every N s with random jitter, fade envelope, colour/temperature,
     optional mask. Placed and tuned by hand like the strobe. Show-owned, so it moves with Passage edits.
- **Performance** (inferred, to be measured on the bench with the frame cap off): each moving shadow-casting light
  redraws its own shadow every frame, because shadow caching doesn't help a moving source. Expect a fraction of a
  millisecond each, so 1–3 cars at once is fine. A dozen at once, or volumetric (haze-beam) shadows on every car,
  is heavy. Keep each car's attenuation radius short (just reaching the wall).
- **Proposed first trial:** one car pass in P02's second half, then stills and an uncapped frame-time run.

---

## Other directing notes already recorded elsewhere
- P03 Rig Slash spots are the gobo breakups (Gary, 4 Oct); lowered 20 cm under the iron girders on 5 Oct.
- P04: tune-4 beams are deliberately intermittent (Slow and Fault flicker); bays 1–6 keep the approved looks.
- P05: cool, shadowless, clouds up-lit. "Looks good to start tweaking with" (Gary, 5 Oct, with the underpass rig).
- P06: grand gold failing bay by bay into the void; no candle (removed 5 Oct); "only darkness but the curtain's
  already on the ground on fire".
- Strobe: 1 s, point light, preset ghost (~1/3 s afterimage).
