# Morning brief — 29 September 2026

Gary, 02:00, verbatim. This is the requirement; everything below it is
interpretation.

> the priority again for Puss in rehearsal mode is
>
> being able to actually run through the different visual segments of the show,
> so I can move from curtain open to P01 walk to S01 to hand off cam to P01 and
> so on and so on
>
> And to have clear big rig spaces for the Scene spaces with the sense of
> mechanism clearly established and ready for the scenery including the
> metahumans with the cloths on their heads in S03
>
> And lighting on all the wing series even the ones that aren't fully done which
> is about half of them, tomorrow will be for working them out too
>
> and implementing the curtain in many of those transition areas ready for later
> different more tattered and otherwise dramatic curtains to replace them in
> their fall to transition between scenes
>
> to be able to advance through all of this easily and with least lag ideally is
> best to get a sense of what a clean run could feel like
>
> tomorrow's work will be primarily in shaping scene 3 and perhaps the final void
> scene, as well as the visual and lighting sensibility for all the mechanism and
> transitions, so the most you can get done of that the better

## The five deliverables, in his order

1. **A walkable spine.** Curtain open -> P01 walk -> S01 -> camera handoff ->
   next Passage, and so on through all 19 segments.
2. **Clear big rig spaces at the Scenes**, with the mechanism legible, ready to
   receive scenery — including the MetaHumans with cloths on their heads in S03.
3. **Lighting on every wing series**, including the roughly half that are not
   finished. He will work those out himself tomorrow.
4. **A curtain at many transition areas**, as a placeholder for later, more
   tattered and dramatic curtains that fall to transition between scenes.
5. **Low lag**, so a run-through gives the feel of a clean show.

His own work tomorrow: **shaping Scene 3 and possibly the final void scene**,
plus the visual and lighting sensibility for the mechanism and transitions.

## State at 02:00 (what he is walking into)

- **Rehearsal mode is ON.** `bPerformanceMode` false on the saved level;
  `bAutoPlaySceneAfterPassage` was already true. Right/Left/Space have always
  been bound (`InfinityStageShowGameMode.cpp:44-46`).
- **Two transport fixes built tonight.** `AdvanceToNextSegment` now plays the
  segment it is parked on instead of skipping it; `IsUnsafeExternalHold` replaces
  a guard that compared a frame against itself and therefore always passed.
  Built, suite 77/78, **not yet exercised in PIE**.
- **A stage front is built** (fascia, house floor, widened mouth) in the portal
  layer. `Portal.bStageFront` defaults on *within* the portal — but the portal
  itself is **off on every structure** and has not been enabled.
- **Wings:** P01, P02, P03, P06 on the new painted-surface master, plus 6 P04
  panels. P04's other 39 and all of P05 are not.
- **The baked curtain exists but is not imported.** Cue 0 still points at the old
  `LS_Opening_Curtain`.
- **Cue 97 anomaly:** "Scene 3 — External Sound" has a Master section of 585.64 s
  against a 160.375 s sequence, and is the only 24 fps sequence. Scene 3 is
  exactly what he wants to shape tomorrow, so this is likely to surface.

## Blocked

- **Rig & atmosphere** — owns structure AND lighting, i.e. deliverables 2 and 3.
  Blocked by its session's permission classifier. Gary must add the allow rule;
  it cannot add it itself, and no other session may add it for it.
