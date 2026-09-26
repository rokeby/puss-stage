# Scene scale audit — walls and rigging at Scene scale

Rig & atmosphere, 26 September 2026, for
`Docs/Conductor/BRIEF_TRANSITIONS_AND_SCALE_2026-09-26.md`. **Read-only: nothing
was spawned, changed or saved.** Evidence: `Saved/CodexStructure/scene_scale_audit.json`
and `scene_sites_probe.json`, from `scene_scale_audit_readonly.py` and
`scene_sites_probe_readonly.py`.

## 1. What is in each Scene today

**Almost nothing.** The vertical-slice level holds no Level Instances and loads
only its persistent level. Each Scene cue plays a dev sequence
(`/Game/InfinityStage/Dev/Sequences/LS_DevScene_0N`) that only cuts between that
Scene's handoff cameras and an establishing camera.

| Scene | Brief | Sequence | Where it plays | Geometry within 150 m |
| --- | --- | --- | --- | --- |
| 1 | animals, "campfire train wreck" — small | 375 frames, 3 camera bindings | establishing camera at (0, 40 000), in the gap between P01 and P02 | none, no lights |
| 2 | shrine — bigger | 375 frames | (0, 120 000) | none |
| 3 | shore — first to open out | 3 849 frames, `ClamCam1`/`ClamCam2` | at the **end of Passage 3's corridor** (x 9–12 k, y 160 000): the Shore bodies and clams | the P03 corridor itself |
| 4 | school — Baroque interior | 375 frames | (0, 280 000) | none |
| 5 | mountains — grandest | 375 frames | (0, 360 000) | none |
| 6 | old lady in the void — open | 375 frames, dog free look | handoff cameras at P06's end | P06's end |

- Nothing anywhere yet reads as a Scene wall or rig. The only structure in the
  world is the Passages' own (gridiron, floor, housings).
- Scene-specific maps exist on disk but are **not instanced**: `/Game/Scenes/Main`
  (Scene 1, animals) and `/Game/KK_S2_Shrine/KK_Main_S2_Shrine` (Scene 2). Earlier
  notes describe both as Level Instances carrying their own sun, sky and fog;
  that is no longer true of this level.
- Candidate environments are purchased packs under `Content/EnvironmentPacks/`
  (Brushify Canyons, Dead Hills, High Grass, Lowlands, Meadow Wetlands, Desert,
  Forest, and others). Their Landscapes run to kilometres. `KlaraDioramaLevelSetup.md`
  describes Scene sets arriving as self-contained diorama levels built around an
  origin marker.
- The spec's **Scene Volume** ("the registered world-space bounds/content adapter
  in which a Scene plays") is specified but **not implemented**. A Scene
  currently has no registered space at all.

## 2. What walls and rigging at Scene scale would cost

The structure pass (`AInfinityStageStructureActor`) builds every layer from
**stations**: a frame (forward, across, up) and a half-width, one per wing pair,
read from a Passage's route. The layers themselves (gridiron, ground, cloth,
housings) only consume that station list. A Scene has no route and no wing
pairs, so it has no stations.

**Recommendation: one generator, two station sources, same ownership.**

1. **Implement the Scene Volume first**, since it's the spec's missing piece
   anyway: an oriented box per Scene (length, width, height, pitch) that also
   registers what content the Scene uses. It is the "sound stage" as an object.
2. **Let the structure actor take its stations from a Scene Volume** as well as
   from a Passage. A volume emits stations at a chosen **bay pitch** along its
   length, with its half-width, exactly the struct the layers already read. The
   gridiron, ground and housings then work unchanged, and the ownership
   discipline (tagged components only, hand-placed survives, deterministic
   variation, revert by regeneration) carries over for free.
3. **Add the two layers Scenes need that corridors don't:**
   - **Walls:** perimeter bays around the volume. This is the same "wall bays"
     job already due for Passages (job 4), so it is built once and serves both.
   - **A field gridiron:** beams in both directions over an area. A corridor's
     one-way grid reads as a hallway ceiling; a stage needs a lattice.

Cost, honestly: the station-source split and the volume actor are a modest C++
change with tests, similar in size to the ground layer. Walls and the field grid
are one layer each. The expensive part isn't code. It's deciding how each Scene's
content sits *inside* its volume, because a kilometre-scale Landscape has to be
cropped, framed or faded by the walls, and that is a design call per Scene.

## 3. Where the scale contrast can honestly come from

The Passages set the audience's yardstick: corridors 9.4 m (P05) to 19.4 m (P01)
wide, wings 8–10 m tall, the grid at 11.5 m, 26 × 34 cm timbers, 45 cm lanterns,
and a cat.

- **Keep the modules constant; change the count.** Scale reads through
  repetition of known things. A 60 m stage should show more bays of the same
  26 × 34 cm beams and 45 cm lanterns, never bigger beams. That is what lets the
  audience measure the room.
- **The ceiling is the fog.** At density 0.022 the medium thins sight to a few
  tens of metres, so walls much beyond ~80–120 m dissolve. Past that, size is
  read from the **rig overhead and the lit shafts**, not the walls. That's a
  resource, not a limit: the grandest room is the one whose walls you can't see.
- **A plausible ladder**, as a proposal for Gary, not a decision:

| Scene | Width | Grid height | Ratio to P01 | How it reads |
| --- | --- | --- | --- | --- |
| 1 small | ~20–25 m | 12–14 m | ~1.2× | close to the corridor: the machine opens only slightly |
| 2 bigger | ~35–40 m | 16 m | ~2× | a stage, with the far wall still visible |
| 3 opens out | ~60–80 m | 20 m | ~3–4× | walls recede into haze; first sense of air |
| 4 Baroque interior | ~15–20 m wide, **30 m tall** | 30 m | 1× wide, **3× tall** | contrast by verticality, a nave, not by width |
| 5 grandest | 150–300 m | 40–60 m, seen as silhouettes | ~8–15× | walls lost in haze; scale carried by the rig and shafts |
| 6 void | open | — | — | Gary left it open; a deliberate absence of rig would itself be a statement |

Scene 4 is the one that plays with expectation. After Scene 3 opens out, a
cathedral that is *narrower but far taller* resets the yardstick instead of
extending it. The limiting factor at the top is lamps, not geometry: shafts need
back-light, and every shadowed lamp costs VSM budget. MegaLights is the likely
precondition for Scene 5.

## 4. What could plausibly move (notes toward the unfinished idea)

Gary's sentence ended on "a different style of movement for the larger stage
widths … a sense of mechanical movements of parts of the stage". **Not a
design**, just what the machine already has, or nearly has, that could move:

- **Chariots in the slots.** The wings already travel inward on their
  mechanisms, and the floor now has a slot under every wing. Chariots visible
  through the slots would make the existing movement read as machinery.
- **Borders flying.** Top panels already have a mechanism (`bTopFollowsMechanism`).
  At Scene scale, borders flying in or out in sequence is the classic Baroque
  change of scene.
- **The grid and battens.** Lamps on battens lowering or rising, and hemp lines
  running as counterweights move. The lines exist as geometry now.
- **Walls opening.** At the Passage → Scene change, wall bays sliding or pivoting
  apart is the most literal "the machine produces the scene", and it is movement
  that only makes sense at the larger scale.
- A possible vocabulary by scale, for Gary to accept or discard: corridors
  **slide** (wings on chariots), stages **fly** (borders, battens), the grandest
  rooms **open** (walls). Drama's distance-driven strike already gives a model
  for timing: movement keyed to where the audience is, not to a clock.

## 5. Questions for Gary

1. Scene content: are Scenes 1–5 to be built as self-contained dioramas (per
   the Klara setup) and then instanced, or assembled from the environment packs
   inside a volume?
2. Is the scale ladder above the right *shape*, especially Scene 4's
   narrow-and-tall reset?
3. Should the walls always be visible, or should the largest Scenes let them
   dissolve into haze?
4. Does movement belong to the transition (walls opening, borders flying) or
   continue *inside* the Scene?

Nothing here is built. The next engineering step, if he agrees, is the Scene
Volume plus the station-source split; walls follow as the shared job-4 layer.
