# Scene 4 reveal tilt: design (Look & camera, 29 Sep 2026)

**Status:** design only. Nothing is keyed. It waits for Rig's hangar rebuild, a
render of stills, and two calls from Gary (below).

## Why

Rig built Scene 4's hangar 30 m tall. The upright roof plate stands to 90 m
before it swings over. At 35 mm, level, from the handoff camera at 1.8 m, the
frame top at the far wall (60 m) is about 13 m. Gary chose *"Pitch up since
other hangars may even be higher"*: the hangars stay tall, and the camera learns
to look up.

## The rule

The camera moves only while the thing it follows moves, in the same direction,
and slower than it. It is still during the fold's biggest move. It never looks
at something before that thing exists.

## Beats (as proportions of the fold; times at speed 1.0 from Scene 4 start)

| Fold | Camera | Why |
| --- | --- | --- |
| 0–2 s arrival | level, still | |
| 2–4 s practicals strike, beams vertical | 0 → ~8°, following the beams | the shafts already leave the top of frame; the beams are the subject |
| 4–8.5 s side walls rise | hold | the walls cross the frame on their own |
| 8–12 s far wall lifts the plate to 90 m | ~8 → ~30° cap, lagging the plate's top edge | the plate is faster (~14°/s) than the camera (~5.5°/s avg), so the camera chases it; at the cap the plate outgrows the frame (~9.6–10.5 s) |
| 12.5–18.5 s roof swings 90° | **still** | the edge goes from 55.8° to overhead and can't be followed; the swing reads as the plate leaning in and widening past the frame |
| 18.5–22.5 s lattice 28 → 12 m | tilt down with the lattice to rest (~5–8°) | the lattice brings the camera home, so it doesn't fly in unseen |
| 22.5–25 s hold | still | |

Geometry, all to be confirmed from stills (the Super 35 filmback is assumed, not
read): half vertical FOV 10.81° at 35 mm; 30 m roof line at 25.2°; 90 m plate top
at 55.8°; ~17° of pitch holds the roof line at 88% of frame height; ~48° holds the
whole plate but loses the nave.

## Mechanism

- **Camera:** the Scene 4 **Entry Handoff Camera** (the show never cuts to the
  establishing camera).
- **Key the camera COMPONENT, never the actor.** The handoff stale check
  (`InfinityStageSceneHandoffBuilder.cpp`, CheckOneScene) compares the handoff
  camera's actor transform, lens and focus with the Passage end. Actor keys
  would be baked into level saves as whatever frame was last evaluated, get
  flagged stale, and fight Match. Component keys leave the matched root alone.
- **Same layer as the dog's look** (Go1 receiver, 01d3152): the root is where
  the camera stands, the component is where it looks. The receiver adopts
  sequence writes on the component as the driven rotation, so in a dog-owned
  hangar the dog looks around the authored reveal.
- **Speed dial:** the pitch keys live in a small camera subsequence nested
  inside Rig's fold subsequence, so the fold's Time Scale retimes both (one
  number, no drift). Rig hosts one section.
- **Exit:** Scene 4's Exit handoff camera is level (matched to P05). Return the
  rest pitch to 0 before the exit cut, or let the cut absorb it; check which cut
  the Scene uses first.

## Generalising

Hand-key Scene 4 first. If Gary likes the shape, a solver in
`InfinityStageCameraPilotLibrary` takes a hangar's moving edges and writes the
same beats, with a dry-run report. Rough examples: 60 m tall at 150 m ≈ 13°;
40 m at 150 m ≈ 6°; 60 m at 300 m ≈ 3°. Wider hangars need less tilt. No ceiling:
the cap governs.

## Open

- From Rig: the lattice footprint (distance, depth); the plate width and hinge
  line; whether the edge heights ease; hosting the camera section in the fold.
- For Gary, from stills: (1) the tilt cap during the plate rise: **30°
  recommended**, ~48°, or ~20°; (2) the rest pitch after the lattice.
