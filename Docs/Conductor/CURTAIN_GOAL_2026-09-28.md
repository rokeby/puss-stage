# Curtain — the goal, and what the benches settled

**2026-09-28, late afternoon. Supersedes the fall-mechanism work in
`PAUSE_2026-09-28.md`.**

## The goal (Gary, verbatim)

> "resolve why the material isn't falling in the way one might expect a heavy,
> rough cloth to fall in a wider pile than on top of itself completely... I just
> want a dramatic sense of physical stage hefty material falling... I just want
> it to feel heavy and physical and not like a pile of virtual silk falling into
> a thin slice of space almost folding on itself"

He explicitly permits **removing the guiding**, **adding bones**, and **baking
the fall in Blender**. The mechanism is free. The objective is weight and the
width of the pile.

## What is now settled by measurement, not argument

**Moving a `ChaosClothComponent` moves the entire simulation frame. The free
cloth rides with it and feels none of that motion as inertia.**

The decisive test: the heading was jerked 300 cm straight **up** in 0.25 s.
Heading 998 -> 1299. Hem -1 -> 299. Same tick, same distance. Cloth cannot be
pushed upward; a real drape jerked up bunches and collapses.

Consequences:

- **A guided fall driven by moving the component cannot work** — at any speed,
  any `LinearVelocityScale`, any collision setup.
- It explains every symptom at once: the taut descent, the hem welded to the
  heading, and the floor "failing" (a carried sheet has the floor slide up
  through it).
- Five explanations died to reach it: wrong pin (real, fixed), teleport reset,
  CCD/tunnelling, collider snapshot, slow tick. Four were the conductor's.

**Falsified along the way:** `LinearVelocityScale` is not in the causal path
(1.0 is indistinguishable from the asset; hem falls 215 cm while the heading
falls 217 cm and free fall would give 86 cm). Kinematic-majority pinning is not
the cause (147 pinned of 9,849; free particles drift in the baked air).

**Validated:** transient in-memory bench copies behave identically to the saved
assets through hang and drop, diverging only in the chaotic pile phase. The
bench technique is trustworthy.

## THE CAUSE (found 28 Sep, Blender scout): compression stiffness, not fullness

**Virtual cloth resists being squashed as hard as it resists being stretched.
Real cloth resists squashing not at all — it buckles the instant you push on
it.** That asymmetry is the entire difference between cloth and cardboard, and a
symmetric solver makes cardboard.

Demonstrated in Blender: with the hem at z=0, the pleated sheet **stood 10 m
tall on its own hem after release, and with no pins at all** — a corrugated
column. Compression 40 and bending 5 out-stiffed gravity; dropping them to 1 and
0.5 still stood, because Blender's stiffness is not normalised by mass and the
physical 0.8 kg/m² gave ~0.06 kg per scout vertex.

With a **heavy vertex mass (1 kg) plus low compression (1)** it falls and heaps.

> "Heavy" means weight dominates the fabric's resistance to compression, so it
> buckles OUT of plane instead of concertina-ing IN plane.

That is Gary's complaint restated as mechanics: "thin slice of space almost
folding on itself" is in-plane concertina; "heavy, physical" is out-of-plane
buckling.

**Untested hypothesis for Chaos:** our PBD stretch at stiffness 1.0 resists
compression as hard as tension — the same column behaviour. **First thing to
check when the editor returns:** does the Chaos cloth expose compression
stiffness separately from stretch, and is ours symmetric?

Measured at fullness 1.25 (frame 90, still settling): bending 5 gives pile depth
2.0 m = **6.7× the 0.30 m hang**; bending 0.5 gives 1.37 m = 4.6×. Stiffer bend
makes the bigger heap, as predicted. Metric validated against renders before any
number was used.

## Fullness: a contributor, DEMOTED from prime suspect

The conductor's fullness hypothesis was **wrong as a cause**. A 1.25× curtain
heaps 6.7× its hanging depth once it is heavy and buckles. Fullness contributes;
it is not why the pile was thin.

The numbers, still worth having. PLAIN (the Opening curtain): 22.22 m of flat
fabric on a 17.77 m track = **1.25×**, hanging **29 cm** deep. RAGGED: 35.47 m =
**2.0×**, hanging 70 cm. A real gathered drape is 1.5-2.5×.

Remaining candidates, as hypotheses to test:

2. **Self-collision thickness** — pile volume comes from layers refusing to
   occupy each other.
3. **Bending stiffness** — "heavy" reads visually as a *large fold radius*.
   Silk crinkles small; velvet folds big and slow. Heavier cloth needs *more*
   bend stiffness, not less.
4. **Friction**, cloth-on-cloth and cloth-on-floor — low spreads into a puddle,
   high heaps.
5. **Damping and areal mass** — a thud, not a flutter, and no bounce.
6. **Perfect planarity** — a dead-flat sheet has no out-of-plane perturbation to
   buckle into.

## Method requirement

**Define the metric before running, and validate it against a case you can see.**
Two metrics on this problem have already measured the opposite of what we wanted
(fold contrast went *down* as the image improved; red-dominance reported "51%
cloth" with no curtain in frame).

What Gary describes is geometric: **the footprint of the settled pile** (extent
in X and Y) and its **height**. Report pile depth against cloth thickness and
pile height against drop height. A good fall heaps several times thicker than
the fabric; a bad one makes a slab. **Take a screen grab** — the numbers have
repeatedly agreed with each other while the picture stayed wrong.

## Traps recorded today

- **Never give a `ChaosClothAsset` to a registered `PoseableMeshComponent` or
  `SkeletalMeshComponent`.** The cloth asset has no Skeleton object, so the bone
  container asserts — `BoneContainer.cpp:163`, a hard crash, not a Python error.
  It took the editor down at 17:09:53. Nothing was lost (last content write
  11:52; all four streams confirmed no unsaved work).
- **A check that does not exercise the same *state* as the real operation is not
  a check.** The bone-list read called the same function on an *unregistered*
  component, which never builds a bone container, so it passed and gave false
  confidence. Same family as "a guard must live inside the thing it protects".
- **Durations on this problem are delta-time seconds, not wall seconds.** Above
  125 ms per frame Unreal clamps the physics step and the sim silently runs in
  slow motion. Every fall timing quoted before today is stretched.
- **Two Unreal editors on one GPU** (Puss + MHFat) accounts for the 333 ms
  frame. Cloth cost is ~7 ms for three curtains, measured under that contention
  and therefore pessimistic. The cloth is cheap; the frame is not.
