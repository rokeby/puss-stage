# Scene 3 — beat sheet (Gary, 1 Oct 2026, conductor session)

**Authority:** Gary's own words, verbatim below. Everything after the beats is the
conductor's reading of what it implies — marked as such, not decided.

## The beats (Gary, verbatim)

1. we arrive at the scene, the lights strike and we are in this eerie seaside place
2. we see the figures swaying, camera cuts from wide to figures.
3. Beyond the crowd of figures we see them surrounding a clam on a pedastal, the clam is shut
4. More shots of the figures with moving waves in background, they are getting more agitated and we get a couple more angles on them
5. As they agitate a lot (2min or so in) the clam mouth slowly opens
6. We see close up of it opening
7. There is a pearl inside glowing, we hear the song of forgetting
8. The figures (still out of focus in bg) start to calm
9. they stand calmly again, swaying (basically return to start of each figure's animation
10. we defocus a bit as we hear puss's thoughts (in the narration)
11. the pearl rises out to be at the centre of the camera, kind of dangling in front of it, showing that Puss has taken it.
12. We float with the pearl out of the scene, as it drops out of view and we go to the curtain for the boy cat interaction.

## Related rulings (Gary, same session)

- The centre of the diorama should be **about 10 m in front of the camera**, mid-box —
  today the figures stand right up close to it.
- Scene 3 cameras get defined **after** the diorama is set up, and **won't be moving**.
- `LS_Clams` was a test of the clam animation. **The animation stays in use; its cameras
  start from scratch.**
- Earlier (1 Oct morning): the cast appears while the landed hangar is dark, then a very
  bright strike; layers of wooden waves sliding back and forth behind them; a painted
  backdrop on the back wall (grey, foggy Atlantic coast, one island, barely visible).

## What exists vs what this needs (conductor's reading — INFERRED unless marked)

| Beat | Exists | Needs |
|---|---|---|
| 1 arrive, strike | Rise re-timed, cast reveal, pit + deck, strike — all applied and saved 1 Oct (measured, markers in CONDUCTOR_START_PROMPT) | Gary's judgement on strike brightness |
| 2–4 figures, clam on pedestal, waves | Six Shore figures + `Clam_with_Pearl` in the level (measured: actor list, run 123004) | Re-blocking to mid-box (~10 m); a pedestal (not checked whether one exists); wave rows + backdrop (Wings and Textures); static cameras (Gary) |
| 4–5, 8–9 agitation builds, then calms back to each figure's animation start | Figures have swaying animation (seen in PIE) | An agitation layer/ramp over ~2 min and a return — animation work, owner TBD |
| 5–7 clam opens slowly, close-up, pearl glows | `LS_Clams` clam animation (Gary: stays) | Timing to the ~2 min mark; pearl glow; the song (Cameron) |
| 10 defocus with narration | — | Focus key on the static camera |
| 11–12 pearl rises to dangle at camera centre; float out with it; it drops away; go to curtain | — | A pearl move keyed to the camera; the "float out" is a camera move — **check against the rule that camera moves are a score the live GO1 must be able to follow**; the exit to the curtain / boy-cat interaction |

## Blocking rulings (Gary, 1 Oct ~12:50)

- Crowd: a **loose ring around the clam, thinner on the camera side** so the wide sees the
  clam between the figures.
- Pedestal: the existing one. Gary **renamed `Clam_with_Pearl_Clam_with_Pearl_0` to
  `Clam_Pedastal`** (the pedestal; the clam sits on it) and saved the level 12:54:14.
  **TRAP:** `s3_cast_reveal_apply.py:44` and `s3_pit_deck_apply.py:46` still list the old
  label, and the cast-reveal record is keyed by it. A revert of either will fail its
  label lookup (INFERRED, not tested: both tools resolve targets by exact label and fail on
  a missing one, so it should fail closed rather than mis-target). Left as is on purpose: editing
  the label would desync the record. Map the label explicitly if a revert is ever needed.
