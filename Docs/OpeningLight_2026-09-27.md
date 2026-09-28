# The opening light — design

Rig & atmosphere, 27 September 2026. **Design only: nothing authored.** For
Gary's eye before anything is built.

## The brief

Gary: the show opens on "a light on a curtain, which is still down", and then the
curtain falls to reveal the theatre machine. So the first thing the audience ever
sees is a lit curtain in darkness. It has never been built, which is why Soft
goods' in-situ recording of the guided fall came out black (frame mean 1.1 of 255).

## The idea in one sentence

**One warm spot, from the house, lights the curtain; when the curtain falls, the
same beam — no longer stopped by it — flies on and rakes down the dark floor of
Passage 1.** The machine is revealed by the curtain falling, not by lights
coming up: the light was always on, the cloth was just in its way.

## Placement and why

| | Value | Reason |
| --- | --- | --- |
| Position | x ≈ 3200, y ≈ −125, z ≈ 650 (≈22 m in front of the curtain, just behind the opening camera) | "From the house": frontal, behind the audience's eye, so it is never in shot on the way in. y −125 centres it on P01's asymmetric corridor (wings at −750 / +500). |
| Height | 650 cm | **Below P01's cloud borders (800 cm).** Anything hung above them is shadowed by them, the likely reason P01's floor is black. At 650 the whole beam travels under every border between lamp and curtain. |
| Aim | at (5400, −125, 250), the curtain's lower middle | pitch ≈ −10° |
| Cone | outer 10°, inner ~6° | A soft-edged iris, not a razor follow spot: oil-lamp-and-reflector register, not modern. |
| Pool on the hanging curtain | ≈ 7.8 m wide, floor to 6.4 m | The curtain is 17.8 × 10 m, so its top ~3.5 m and both flanks stay dark. It reads as *a light on a curtain*, not a wash. |
| Where the lower edge meets the floor | x ≈ 4957 | The guided fall sprawls the cloth ≈ 4.5 m forward (x 4950–5400). **The whole pile lands inside the lit pool.** |
| After the fall | centre ray reaches the floor at x ≈ 6775; the upper edge runs nearly level at ≈ 6.4 m | A long raking light down the corridor floor and across the near wings, still under the borders. The first light P01's new floor has ever received. |

**It survives the fall by design.** Framed tightly on the hanging cloth it would
end up lighting an empty batten. Framed like this it lights three things in
turn: the hanging curtain, the cloth falling through the beam, and the heap in its
pool, while the beam continues into the machine.

## Register

- **Colour: warm, about 2800 K.** The first light of the evening sets what the
  machine is. Warm says theatre, Baroque, lamp oil; cold would say industrial,
  and the plan names industrial precision as a deliberate wrongness for later,
  not the default.
- **Hardness: soft-edged.** Inner ≈ 60% of outer.
- **Optionally breathing:** the existing `MI_LF_Flicker_Breath` light function,
  a slow ~5 s swell. A lamp that breathes before the show begins is alive
  without drawing attention. Off by default; Gary's call.
- **Brightness: about 3000 cd to start** (≈6 lux at 22 m). The velvet is dark:
  roughly five times darker than the painted wings, which P03's pools light at
  about 2 lux. Tune by capture, not by number.

## Cost

- **One light**, spot, shadows ON: the falling cloth casting a moving shadow onto
  the floor and into the machine is half the drama. Volumetric shadow OFF: it
  throws away from the camera, so the haze would show it faintly at best (the P03
  A/B lesson). One more shadowed light against a frame that already overflows:
  small, and it is the one light in frame at the opening.
- **Authored as a Show attachment**, Station-anchored to the P01 cue whose
  station is nearest upstream of x = 3200, with its offset derived by script the
  way the P03 rig's were. The structure pass then hangs a lantern housing and a
  hemp line on it for free, so if the audience looks around (the dog free-look)
  they see a lamp hanging in the machine, not light from nowhere.
- **Drama: none.** It is on before the show starts and stays on. Not striking it
  on approach is deliberate: it is the one light that does not notice you.

## Gary's answers (27 Sep, via the conductor)

1. Warm, about 2800 K. 2. Steady, no breath. 3. The beam runs on down the floor
after the fall: not irised, not widened ("nothing changed except what was in
the way"). 4. Floats designed together with it, below. **Design approved as
written.** Still to do before authoring: the three read-only checks at the end,
and Gary's yes in the Rig & atmosphere session for the Show write.

## The floats, designed with the opening light

**The image:** the curtain falls, and beyond it a double row of warm floats
recedes into the machine, with the opening beam laid down the boards between
them. The floats are not lit up by the fall. They were burning behind the
curtain all along, and the fall reveals them, which is the same principle as
the beam.

| | Value | Reason |
| --- | --- | --- |
| Where | One per wing station per side, just inboard of each wing's foot (the panel's line minus ~40 cm), **60 cm downstream of the station's slot**, and **only downstream of the curtain** (x > 5400) | Along the wing and slot lines, the Baroque float row, but never standing over a slot's gap. None upstream: the approach to the curtain stays dark, so the opening is still one light in darkness. |
| Height | ≈ 25 cm above the boards | A low trough of lamps. |
| Aim | Inward and forward, yaw about ±60° toward the corridor centre, pitch +5° | Each float fans across the floor ahead of it, so the cat's path gets warm light from both sides and underlight as it passes. |
| Cone / reach | Outer 35°, attenuation radius 350 cm | Short and wide. The cone's lower edge would only reach the understage after 485 cm, beyond the radius, so the dark under the slots stays dark. Re-checked after the per-side slot fix (c8aee3b): the clearance depends only on lamp height, cone and understage depth, not on where the slots are, because a shadowless lamp ignores the boards either way. It still holds. |
| Shadows | **Off** | Cheap, because P01 already overflows VSM, and safe because the short radius keeps them off the understage. |
| Colour | ≈ 2500 K | Warmer than the opening spot, so the spot stays the evening's "white". |
| Level | ≈ 6 cd ±15% per lamp (≈ 1.5 lux at 2 m) | A floor under the composition, not a key. Tuned by capture with the spot. |
| Wear | About 1 in 12 dead (disabled), chosen by a fixed seed per station | Evidence of use; a perfect row reads as generated. |
| Drama | None | Revealed by the fall, steady after it, like the beam. |

Count: about 2 × (P01 stations downstream of x = 5400) ≈ 80 lamps, all shadowless.
Authored the same way as the P03 rig: station-anchored Show attachments, GUIDs
minted by replicate, revert record written first. The structure pass gives each
a housing but no hemp line, because they stand on the floor rather than hanging
under the grid.

**Placed from the wing, not the slot.** The floats key off each wing panel's
actual line. This matters because of a bug found while designing them: the
ground layer started every station's slots from the *wider* side's wing on both
sides, so in P01 (wings at −750 / +500) the right-hand slots began at 600 cm and
the right-hand wings did not stand over them. Fixed in source (c8aee3b,
per-side extents, new asymmetric test), unbuilt. It takes effect after the next
build window and a structure re-materialize, a level write sequenced after the
opening light.

## With the P01 floor problem

The opening beam lights P01's floor at the start and nowhere else. The rest of
P01's floor still needs the separate decision already on Gary's list, footlights
along the slots. Designed together, the natural pairing is **floats**: a row of
low, warm lamps along the slot lines, throwing along the floor. It's the
Baroque float row of oil lamps, and it would visibly continue the line the
opening beam starts. Sketch only.

## Open questions for Gary

1. Warm (≈2800 K) or something else for the first light of the evening?
2. Should it breathe (a slow flicker), or burn perfectly steady?
3. Keep the beam running on down the floor after the fall (as designed), or
   iris it down to the heap once the curtain lands?
4. Design the P01 floats with it, or separately?

## Checks before authoring (read-only, once the editor is free)

- Where the opening camera actually is at frame 0 of `LS_Opening_Curtain`
  (assumed ≈ x 3600, z 150). The lamp must sit behind it.
- The P01 borders' true bottom edge (pivot is at 800 cm; the mesh may hang lower).
- That the curtain actor's track spans y ≈ −890…+890 at x = 5400, and which way
  "forward" is for its fall (assumed −x, toward the audience).

## State, 28 September 2026

**Authored** on Gary's "Yes" in the Rig & atmosphere session, re-solved for the
measured opening camera (x 0, z 150, facing +X, held for the whole Opening):
the lamp at (−300, −125, 650), 4° cone, 19,600 cd, 2800 K, steady, on P01
Wing 001 as a Station offset; 78 floats on 39 pairs past the curtain, 5 dark.

- Backup `Backups/PreOpeningLight-20260928-0826` (Show + umap, md5-matched, with
  the plan and revert record). Undo: `Saved/CodexStructure/p01_opening_revert.py`.
- `P01_OPENING_APPLY_OK`: 79 added, existing P01 lights verified field-for-field,
  Structure 01 re-fitted (506 housings), only the Show and level saved, 0/0.
- `P01_OPENING_VERIFY_OK` (independent): live lamp at the designed position and
  aim to 0.0 cm / 0.000°, settings as designed, 73 live floats, Structure 01
  current, 0/0.
- **Tier: saved read-back. Not yet seen in a frame.** Intensity is a starting
  point to be tuned by capture (expect two or three passes: the velvet is dark).

## Re-staging, 28 September — notes before the re-solve

Gary has fixed the staging: the camera sits where an imagined audience would
(0, 0, 150), centred on the curtain, which moves to about 15 m (x ≈ 1500). The
whole proscenium should read, and the curtain should be "fully visible and
nicely lit in a conventional way while being a relatively dark stage". The lens
is undecided (16 mm at 15 m, or 25 mm with the camera back at 23.4 m), so the
geometry waits for that choice. What already follows:

- **The idea survives; the instrument changes.** It becomes a curtain warmer:
  the whole 17.8 × 10 m cloth lit evenly and softly, with the darkness coming
  from everything around it. Conventionally that is two crossing spots from the
  house, behind and either side of the camera, plus the Baroque convention of
  **floats at the stage lip** glowing up the cloth. The floats already designed
  for P01 would move forward to the proscenium edge rather than start past the
  curtain. Still steady, warm, shadowed, under the borders, and the beam still
  runs on down the floor after the fall.
- **The third border masks the curtain's top.** P01's borders hang 800–1800 cm
  at stations 250, 850 and 1450. With the curtain 50 cm behind the third one, the
  camera sees the cloth only up to about 8.2 m (either lens option): the top
  ~1.8 m is behind the border. That is the conventional header over a house
  curtain, but it is what "fully visible" will actually mean, and moving the
  curtain in front of station 1450 would change it.
- **Today's authored lamp will be wrong the moment the curtain moves.** Solved
  for 57 m, on a curtain at 18.4 m it makes a 2.6 m pool at about 58 lux, ten
  times the designed level. The curtain move and the re-solve should land
  together, or the lamp should be disabled in between.
- **The opening frame will be asymmetric.** P01's first station has wings at
  −750 / +500 where the rest are ±750. Characterful or a mistake: Gary's call,
  but it is in the most scrutinised shot of the show.

## Re-staging 2, 28 September — the curtain in front of the machine

Gary: the curtain should be "fully in front of all of the wings… the full curtain
filling the frame with a little sense of the surrounding structure… curtain in
the beginning of an empty space, maybe with rigging and some lighting, maybe as
an implication of a tunnel." The curtain stands at x ≈ 0, just upstream of P01's
first station. At 17.77 m it is wider than the 15 m corridor, so it hides every
wing and border behind it. The camera sits back at about x −1400 on a 15 mm lens
(curtain ≈ 80% of frame width). It falls **upstage**, so the pile lands at
x ≈ 0–450, at the mouth of the machine, and the camera travels over it. Gary
has confirmed the warmer (house spots plus floats at the lip) and fixing P01's
first station to ±750.

**The idea survives, turned round.** The curtain falls away from the audience
now, so after the fall the house light no longer rakes a floor in front of us:
it pours *into the mouth of the machine*, lighting the heap on the threshold
and fading into the first bays. The light was always on; the cloth was in its
way. Only the shape of what it reveals has changed.

**The warmer (not yet solved; lens and camera still open):** two house spots
crossing from behind and either side of the camera, e.g. about (−2000, ±650, 700),
each wide enough (~39° half-angle) to reach the far edge of the cloth, ≈1450 cd
each for ≈6 lux combined at ≈22 m, the level at which the dark velvet read well
in the 28 Sep capture (R ≈ 152, unsaturated). Plus a float trough along the lip,
glowing up the cloth. Warm, steady, no drama. The lone 4° lamp authored today
is replaced, not kept.

**Framing, for Look & camera:** at 15 mm from 14 m the frame at the curtain is
22.2 × 12.5 m. A *level* camera at z 150 sees only z −474…774 there, cutting off
the top 2.3 m of the 10 m cloth and filling half the frame with the void below
the stage. Centring the cloth needs the eye at about z 500 or a ~14° tilt up.
That is their call, but the warmer is solved against it.

**The surrounding structure is the portal.** "Empty space, rigging, the
implication of a tunnel" around a curtain is the portal already costed for the
hangar returns (Docs/SceneScaleAudit §5): one object doing both jobs. A sketch,
from the same constant modules as the rest of the machine:

- Two timber **posts** just outside the curtain's track (about ±950), and a
  **header** beam above the cloth: the proscenium frame, visible in the 20%
  margin around the curtain.
- The **gridiron runs forward** over the header to meet it, so above the curtain
  the rails recede into the dark behind: the tunnel, implied rather than shown.
- A short **forestage**: boards extended ~1.5 m in front of the curtain (the
  floor currently starts at the route's start, x 0) with the **float trough**
  at its lip.
- A few **hemp lines** dropping from the dark to the header and the curtain's
  batten; the house spots' own lanterns stay behind the camera, never in shot.

This is a structure-pass layer (C++, a build), a "portal" placed at a Passage's
start (and later at hangar mouths). It is the first image of the show, so it is
Gary's to see as a design before anything is built.

## State, 28 September (warmer)

**The curtain warmer is authored** for Gary's stalls view (camera −1400, 0, 150,
tilted up 14°, 15 mm; curtain at x 0 as a spawnable in LS_Opening_Curtain_Chaos):
two crossing house spots at (−2100, ±650, 1265), 33°/20°, 1740 cd each, 2800 K,
steady, shadows on; 18 floats added behind the curtain's new line (stations
x 250–5050); the lone 4° Opening Light disabled (kept, for the revert).

- Backup `Backups/PreWarmer-20260928-0928` (with plan and revert record). Undo:
  `Saved/CodexStructure/p01_warmer_revert.py`.
- `P01_WARMER_APPLY_OK` (GUIDs minted from scratch pair Wing 048, restored
  exactly) and independent `P01_WARMER_VERIFY_OK`: live spots at the designed
  pose to 0.0 cm / 0.000°, 96 floats, 579 P01 lights with unique GUIDs,
  Structure 01 current, 0/0.
- **Held for the portal build:** the float trough's lip floats. From the stalls
  the hem is the feature, and it gets no modelling uplight until the portal is
  enabled. Tier: saved read-back; the look is Gary's to judge from the capture.

## The portal and the forward fall, 28 September (evening)

Gary approved the portal and its lip floats ("go ahead"). Scripts are written but
not run, because this session's permission layer blocked editor runs:
`portal_enable_*` (3a) and `p01_lip_floats_*` (3b), plus a read-only
`wing001_footprint_probe` with a file-side analyser.

- **The fall goes forward.** The upstage throw was dropped ("It falling forward
  doesnt seem an issue"). The pile centres near the curtain line and reaches
  about x +190 upstage, short of Wing 001 (250) and station 1's floats (310).
  Downstage it reaches −250 to −320, and that number is not final.
- **The stage edge.** The portal's forestage is 150 cm deep (boards x −150…0).
  The bake lands on an infinite plane, so fabric past −150 lies flat on air.
- **The frame sees below the lip.** At eye z 150, tilt 14° and 15 mm on the
  Super 35 filmback (23.76 × 13.365 mm, which this doc's 22.2 × 12.5 m framing
  already assumes), the bottom ray crosses the lip plane at z ≈ −70. So about
  the bottom 7% of the frame height, at the lip, looks below stage level into
  what is very likely void, though not yet swept. (First reported as z −305 and
  17%, which wrongly used a full-frame sensor. The filmback itself is still to
  be confirmed from the camera.) The portal has no stage front, which is a
  design gap independent of the cloth.
- **The coarse pile (good2, every frame).** Downstage to x −383, still
  creeping. Upstage to +235, only 15 cm short of Wing 001. Top 1000 in show
  placement, with no upward kick. Width ±890 while hanging, ±964 mid-fall and
  ±1220 settled. The frame's half-width is about ±1110 at the curtain line, so
  posts widened past ±1220 would leave the shot. The floor spans only ±970
  (ground) and ±950 (forestage), so the side spill also lies on air.
- **The options, for Gary:** (i) deepen the apron to 430–460 cm, which clears
  the lamps but recomposes his frame; (ii) drape the cloth over the lip, which
  needs (iii); (iii) a stage front (fascia plus house floor) in the portal
  layer, C++; (iv) bury the lamps: the trough and housings must be bake
  colliders, and shadowless buried lamps leak light (+16 VSM casters to fix).
  Rig & atmosphere recommends (iii), with (ii) as the cloth fix it enables.
- **Guards in place.** The 3b plan refuses until `PILE_DOWNSTAGE_X` (the
  chosen bake's all-frame reach) is set, and names the forestage depth that
  would clear it. The lamps' aim and level follow their distance from the
  cloth (centre ray at 110 cm, 4 lux per lamp there).
