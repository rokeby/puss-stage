# Exit proposal: the hangar is the house for the next Passage

Look & camera, 30 Sep 2026. A proposal for Gary's open question: *"how do we exit
the rig moment and move into the next passage"*. See
`Docs/Conductor/SCENE_ARCHITECTURE_2026-09-30.md`. Nothing is built.

## The idea

The Opening is a house (a stalls seat, parquet, a gilded ceiling) looking at
Passage 1's proscenium and drape. **Every hangar can be that house again.**

1. The box rises around the cat, the lights strike, and we cut into the Scene's
   own sequence (Gary's entry).
2. At the Scene's end, **the hangar's far wall opens**, for example hinging down
   and outward like a drawbridge. **Behind it stands the next Passage's
   proscenium with its drape.**
3. The cat moves to a **stalls seat inside the hangar**, about 46 m from the stop
   and 14 m back from the portal.
4. The Interaction's shadow play runs on the drape ("it happens on the curtain").
5. The drape falls, and the cat **walks out of the house onto the next stage**.

No teleport, no hand-off camera, no retained-camera machinery. The box itself
leads to the next opening.

## Why it fits

- **The geometry is right:** the far wall is 21 × 30 m and the portal opening is
  19 × 10.5 m. The seat sits inside the 60 m nave.
- **The transition cameras are already this seat,** placed once from each
  route start (`place_transition_stalls.py`). They are NOT derived live
  (corrected 30 Sep): after a Passage moves they must be re-seated IN PLACE,
  because the Interaction cuts bind them as actors, and a revert-and-replace
  would break those bindings. The drape lives at the mouth, and the portal is
  built at the route start. The Passage camera rigs DO follow a moved Passage
  with no work: they derive their transform from the route spline every
  evaluation (InfinityStageCameraRig.cpp:356, :701–703).
- **It's the Opening's grammar at every transition,** now always from inside the
  machine that just rose around the cat.

## Costs by owner

- **Rig:** dock each Passage N+1's mouth at Hangar N's far wall (the docking
  audit found P04 a pure translation; Passages are distance-driven, so Master
  timing is unchanged). Plus a far-wall opening mechanism.
- **Soft goods:** none new.
- **Look & camera:** the move from the stop to the seat (dog-driven or authored),
  and the stalls cut timing.
- **Director:** the segment order is unchanged.

## Unknowns

The Passages sit in 800 m lanes, so docking moves their wings, lights and
celestial frame. P03 stands on a landscape. And the walk to the seat could be
the dog's or authored.

## Cheaper fallback: the match cut behind a curtain

At the Scene's end the drape flies in inside the hangar, in front of a stalls
seat there. When it fills the frame, cut to the real stalls camera at the next
mouth: same cloth, same framing, so the cut is invisible. The world changes
behind the curtain, as in a theatre. No docking. It's a trick where the first
option is a place.

Both should reach Gary as pictures before either is built.
