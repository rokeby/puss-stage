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

## The prime suspect for the thin pile: no fullness

A real theatre curtain is **gathered** — 12–18 m of fabric on a 7 m bar, 1.5x to
2.5x fullness. That excess is why a dropped drape lands in a deep heap: the
fabric has nowhere to go but outward. A flat plane the same width as its heading
has no slack and **can only concertina in its own plane** — which is exactly
"a thin slice of space almost folding on itself".

If that holds, every solver parameter tuned so far is downstream of missing
fabric. **Check the cloth's flat width against the heading span first.**

Ranked candidates behind it, as hypotheses to test:

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
