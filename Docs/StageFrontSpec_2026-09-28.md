# Stage front: proposed spec for Gary, 28 September 2026

Gary chose: "Build it, and let the curtain hit the posts." This spec proposes
the stage front, with a recommendation and alternatives, so he has something to
react to. Nothing is built yet. The owner is Rig & atmosphere, in the portal
layer (`AInfinityStageStructureActor::BuildPortal`), using the same constant
modules: timber from the gridiron kit, boards from the ground kit (24 cm wide,
0.8 cm gaps, 5 cm thick, staggered 240–480 cm lengths).

All coordinates are UE world cm on Passage 01. The curtain line and the posts
are at x 0, the lip at x −150, and the stalls camera at (−1400, 0, 150),
tilted +14°, on a 15 mm lens.

## What the camera sees (assumed Super 35 filmback, NOT yet confirmed)

| Quantity | Super 35 (assumed) | If full frame instead |
| --- | --- | --- |
| Bottom ray | −10.0° | −20.0° |
| Crosses the lip plane at | z ≈ −70 | z ≈ −305 |
| Stage plane z 0 enters frame at | x ≈ −550 | x ≈ −990 |
| Frame half-width at the curtain line | ±1110 | ±1680 |
| Frame half-width at the pile's upstage end (x +235) | ±1290 | ±1960 |
| A house floor 120 below stage | never in shot | in shot from x ≈ −660 |

Every row depends on the filmback. Look & camera can confirm it in one line,
and the spec below is sized to survive either answer.

## The recommendation: A, a raised stage

| Part | A (recommended) | Why |
| --- | --- | --- |
| **Stage front (fascia)** | Horizontal boards, same kit as the floor, from the lip (z 0) down to the house floor: 5 courses for 120 cm. A timber **nosing rail** along the lip edge (26 × 12 cm, gridiron timber). | Boards coursed like the floor read as the same built stage. The nosing gives the lip a hard line in frame, and the curtain's overshoot breaks over it. Only about 70 cm (3 courses) is in the opening shot. |
| **House floor depth** | **120 cm** below stage. | A real stage sits about 90–120 cm above the stalls. On Super 35 the house floor is out of the opening shot, so the fascia reads as a stage front, not a step. On full frame it shows as a strip in front of the fascia, which is why it's boarded and runs past the camera. |
| **Pit** | **None.** | Out of shot, and it adds pieces. The overshoot hangs down the fascia and lands on the house floor. |
| **House floor extent** | From the fascia to **x −2600** (past the camera and the house spots at −2100), **±2000** wide. Boards, same kit. | The frame must never run off its far edge into void again. It covers the opening shot on either filmback, plus the dog's gaze during the operator-stop hold looking down or around. |
| **Mouth floor** | Stage-level floor widened to **±1300** from the lip (x −150) to the first station (x 250), covering the ±1220 settled spill plus a margin. The forestage lanes follow this width, not the portal opening. | The ground spans ±970 and the forestage ±950, so the spill lies on air today. |
| **Mouth sides** | The fascia **returns along both sides** of the widened mouth (y ±1300, x −150 … 250), down to the house floor. | Near x +235 the frame's half-width is about ±1290, so the mouth's side edges are at the frame edge. A return makes them a built edge, not a board end floating in fog. |
| **Posts** | Unchanged: ±950–990, x −20…+20, up to z 1095. | Gary's frame needs them in shot. The curtain now meets them. |

## Alternatives

- **B, with a pit.** Same as A, but the fascia drops **250 cm** into an
  orchestra pit 300 cm deep (x −450 … −150). A pit wall then rises to a house
  floor at −120 beyond it. The overshoot spills into a dark well at the lip: a
  strong image in the dog's downward gaze, out of the opening shot. Costs about
  two more fascia runs and a pit floor.
- **C, a painted fascia.** Same geometry as A, but the stage front is a single
  canvas-covered flat painted like the wings, instead of boards. It's closer to
  the show's painted world and a little cheaper. It loses the "built stage"
  continuity with the floor, and needs an art pass (Wing materiality's domain).

## For Soft goods: the colliders

Every box below is a collider for the curtain bake. I can hand them over
**now**, from these numbers, before anything is built. After the build, a
read-only check confirms the built geometry matches them to 1 cm.

- Posts: x −20…+20, |y| 950…990, z 0…1095.
- Header: x −20…+20, |y| ≤ 990, z 1050…1095 (not reached; the top peaks at 1000).
- Trough: x −150…−115, |y| ≤ 950, z 0…25.
- Floor top z 0: forestage x −150…0 and mouth floor x 0…250, both |y| ≤ 1300; the ground beyond x 250 as today (±970).
- Lip and fascia: face at x −150, z −120…0, |y| ≤ 1300; side returns at |y| = 1300, x −150…250, z −120…0.
- House floor top z −120: x −2600…−150, |y| ≤ 2000.
- If the footlights (3b) go ahead, their 16 housings are colliders too. That's
  deferred: the overshoot now covers the forestage, so the burial question
  (shadowless lamps leaking light under the cloth) comes back after the
  collider bake.

## Proposed order

1. Gary picks A, B or C.
2. The collider list goes to Soft goods at once, and the collider bake (~80 min)
   runs in parallel with the next two steps.
3. The C++ is written, with tests (portal pieces, and the house floor staying
   ahead of the camera).
4. A build window, negotiated with MHFat, then the suite.
5. When my session is cleared: the below-lip sweep, the Wing 001 probe, steps 1
   and 2 (the slot re-fit), then 3a (portal enable). 3a waits until after the
   build, so the portal and its stage front land in one re-fit and the first
   capture shows the whole thing.
6. A read-only check that the built geometry matches the collider list, then
   the capture.
7. 3b (footlights), once the collider bake's pile extents are final.
