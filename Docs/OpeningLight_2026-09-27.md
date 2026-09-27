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
| Where | One per wing station per side, just inboard of each wing's foot (the panel's line minus ~40 cm), **only downstream of the curtain** (x > 5400) | Along the wing and slot lines, the Baroque float row. None upstream: the approach to the curtain stays dark, so the opening is still one light in darkness. |
| Height | ≈ 25 cm above the boards | A low trough of lamps. |
| Aim | Inward and forward, yaw about ±60° toward the corridor centre, pitch +5° | Each float fans across the floor ahead of it, so the cat's path gets warm light from both sides and underlight as it passes. |
| Cone / reach | Outer 35°, attenuation radius 350 cm | Short and wide. The cone's lower edge would only reach the understage after 485 cm, beyond the radius, so the dark under the slots stays dark. |
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
ground layer currently starts every station's slots from the *wider* side's
wing on both sides, so in P01 (wings at −750 / +500) the right-hand slots begin
at 600 cm and the right-hand wings do not stand over them. Fix pending in the
structure pass (per-side slot extents), C++, next build window.

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
