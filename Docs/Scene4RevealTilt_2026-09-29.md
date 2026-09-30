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

## Stills (29 Sep evening, `Saved/CodexCameraPilot/capture_scene4_stepwise.py`)

- The survey (read-only, dirty 0/0) found the camera is Super 35 at 35 mm, at
  (10668.5, 240000, 180), rotation 0. LS_DevScene_04 runs 25 s at 25 fps. The
  Entry camera holds 0–24 s, then the Scene **cuts to a level Exit camera**
  (retained hold) at the same position. The fold subsection starts at frame 0.
- **At level, nothing changes after 12 s**: the swing and the lattice happen
  above the frame, which confirms the need to look up.
- **Geometry pass (unlit base colour):** 30° frames the wall tops, the gaps to
  the void and the flown lattice; 48° frames the upright plate and the roof
  closing. The design works geometrically.
- **True pass (EV100 0.5):** everything above about 20° is **black at every
  moment**. The plate, roof and lattice are unlit. **The look-up reveals darkness
  until the upper hangar is lit.** That's Rig's lighting and Gary's call, and it
  comes before choosing the cap.
- A brighter pass using min/max brightness changed nothing; the room's exposure
  ignores those overrides. Use the base-colour pass to judge framing.
- A single-call capture that scrubs and captures in one frame DOES render the
  new state, because SceneCapture flushes it. Identical PNG byte sizes had
  suggested otherwise, and pixel diffs disproved that. The stepwise script and
  its structure fingerprint remain the checked path.

## GO1 performability (source and docs only)

- The camera look comes from the handheld remote's right stick, not the robot's
  body. In Gaze the stick adds at most ±18.2° of pitch, so **a 30° look-up
  can't be performed live in Gaze**; Free Look can reach it, by rate.
- Scene 4 is Timeline-owned: the keys play the score and the stick doesn't
  touch the camera, so the dog can follow the score physically without adding
  to it. If it were ever dog-owned, the keys and the live look would add
  together, and the operator should perform glances only.
- The robot's body-pitch range is unknown (not in the docs; standing with the
  bridge is not yet exercised). Only the operator can find it; nothing here
  commands the robot.
- About 8°/s peak is trackable by hand, and the eased edges make it easier.

## Exit

The Exit cut at 24 s is level. Either the rest pitch returns to 0 in the 1.5 s
after the lattice settles (the attention releasing), or the Exit camera carries
the rest pitch with KeepState, so the end of the Scene doesn't snap it back.

## Keyed (29 Sep, 18:40) and verified by playing (after the relaunch)

- `LS_S4_CameraScore` is nested in `LS_S4_HangarFold`, which is nested in
  `LS_DevScene_04`. The keys sit on the Entry Handoff Camera's COMPONENT
  (binding parent confirmed by Guid string): 0/0/8/8/30/30/0° at 0, 2.3, 4.3,
  8.8, 11.0, 18.8 and 23.9 s, with flat tangents. Peak rates are about 6, 15 and
  9 deg/s.
- Stepwise read-back of the component pitch at 8 beats, each within 0.5° of the
  smoothstep prediction: 0.0, 3.88, 8.0, 19.3, 26.89, 30.0, 14.91 and 0.48. The
  actor's pitch stayed 0.000 throughout, and the component restored to 0 when
  Sequencer closed. Scripts: `key_scene4_score.py`, `verify_scene4_score.py`,
  `revert_scene4_score.py`.
- True stills: at 15.5 s and 30° the roof underside glows through the lattice (the
  image the design exists for). **The chase frames (9.9 and 10.5 s) are nearly
  black**: the rising plate's dark metal barely catches the uplight, so in stills
  the tilt goes up into dark. Judge it in motion before changing anything. The
  fix, if one is needed, is a lighter plate surface (Rig's default, never Gary's
  choice), not a different score.
- **The Time Scale caveat:** the Entry→Exit cut at 24 s is in `LS_DevScene_04` and
  does not scale with the fold. Below 1.0, the descent runs past the cut.
- The first inspection script crashed the editor (an open range passed to
  `SequencerTools.get_bound_objects`); nothing unsaved was lost.

## v2 (29 Sep, late): the whole hangar rises from below the mouth

Gary's sketch meant the WHOLE BOX hangs below the passage floor, hinged at the
mouth (x 10668.5, axis Y), and rotates up as one piece: assembled, dark except
the ghost light, over 1–16 s. Then the practicals strike (16.5–18.3), the roof
swings over (18.5–24.5), and the lattice flies in (24.5–28.5). Scene 4 grows to
about 31 s, with the exit cut at about 30 s. It is a new asset,
`LS_S4_HangarRise`; the old fold is kept unreferenced. **The score was unhosted
from the old fold (hosted 0) and waits for v2 to be re-keyed and re-hosted.**

- **Roll: rejected (Look & camera's call).** The box turns about the hinge, which
  is the camera's PITCH axis: a symmetric fore-and-aft tip whose edges stay
  horizontal in frame. A roll, even one proportional to the box's angle, lays a
  sideways lean over a straight-ahead motion, so it reads as two motions. A head
  answers the world on the axis the world tips: a nod, not a cock.
- **Gary's "the horizon rotates with the box" is a PITCH illusion.** A ground
  plane tipping about a hinge at the viewer slides the horizon vertically. The
  cheap version: camera pitch coupled to the box's rise curve, starting level
  (to match P04's end) and easing about 6–8° DOWN over the rise, so the horizon
  rises in frame with the box. It's a device: it's locked to the box but moves
  opposite to it. The creature alternative is a level frame that the room rises
  into. Gary picks, from stills.
- **The "look down at the lip" beat: undecided.** The camera stands on the hinge
  line, so the lip is at its feet (about 84–90° down). A −12 to −20° look sees
  mostly void unless the ghost light or the box interior falls in −9 to −31°. It
  also conflicts with the pitch illusion (the horizon would move opposite to the
  box). Decide from a still. If the edge must be seen, dock the mouth about 5 m
  ahead of the camera (Rig's call).
- **Needed from Rig:** the ghost light's position in the box, the box's
  extents, the rise easing, and the new exit-cut frame.

## v2 option stills (29 Sep, late; `capture_scene4_v2_options.py`, sheet `Captures/Scene4V2/Scene4V2_options.png`)

Rig docked the hinge 5 m ahead of the camera, so the lip sits at −19.8°. The
ghost light lands 30 m ahead at eye height; while hanging it is 25 m below. The
Scene sequence is 25 fps, 31 s, with the exit cut at 30.0 s.

- **1–9 s: near-black at every pitch.** The box rises dark by design; only a
  faint silhouette shows against the dusk.
- **A (level):** the glow first clears the frame bottom at about 12.5 s.
- **B (horizon illusion, 0 → −8°):** like A, but the horizon ends about a third
  of the way up the frame. Subtle in stills; judge it in motion.
- **C (look down −15°, then rise with the light):** the light enters at about
  11 s and the camera rises with it to centre at landing. The earliest and most
  legible subject; the creature watching the only light.
- **After landing (all):** 30° for the roof swing (the underside glows through the
  lattice at 21.5 s), then down with the lattice, level by 29.5 s.
- Recommendation to Gary: **C**.

## Open

- From Rig: the lattice footprint (distance, depth); the plate width and hinge
  line; whether the edge heights ease; hosting the camera section in the fold.
- For Gary, from stills: (1) the tilt cap during the plate rise: **30°
  recommended**, ~48°, or ~20°; (2) the rest pitch after the lattice.
