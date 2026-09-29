# The hangar's light event: what changes when the space assembles

Design only, 29 September 2026, Rig & atmosphere. Gary: *"it's the rotation
into the LIGHTING of the big box, at least significantly."* Working hypothesis:
the geometry is the cause, and the light is the event.

## Before and after

**Before: the dusky, flat end of a passage.** It is lit by the celestial rig: a
low warm dusk sun, a sky light and the exponential height fog. The flatness is
the sky light: omnidirectional fill with no direction and no enclosure.

**After: the interior of a big machine.** Six changes, cheapest and biggest
first:

1. **The sky goes out.** The project runs **Lumen** (GI and reflections method 1,
   distance fields on). So when walls and roof close, Lumen occludes the sky
   light **by itself**. The flat fill drains out of the space as it closes, with
   no keying: the geometry literally is the light change. It is the biggest
   single effect, and it is free.
2. **The practicals strike.** A rank of work lamps along the walls and lattice
   comes on in sequence: warm tungsten, 2700–3000 K, each ramping 0 → on over
   about 0.2 s, staggered about 0.1 s. All shadowless. It is the clearest
   "suddenly lit differently", and the cheapest. *Keyable.*
3. **A shaft through the roof.** If the folded roof leaves a slot, the dusk sun
   cuts one blade of light through the haze inside. That is *geometry*: it exists
   only if the slot does, and it needs the sun to reach the slot at that hour.
4. **Interior haze.** A **Local Fog Volume** inside the hangar, its density keyed
   from 0 to about 0.02 as the space closes. It is warmer than the blue-grey
   exterior fog, and it makes the practicals bloom and the shaft read. Cheap.
   *Keyable.*
5. **Bounce colour.** Lumen bounces the walls' material colour into the space.
   Timber walls give a warm interior with no extra lights. Lumen takes about
   0.5–1 s to converge after big geometry changes, so the bounce *blooms in*
   just after the walls stand. That can be a feature: the light settling after
   the event.
6. **Exposure: pin it, or the event disappears.** Auto exposure is on in this
   project. Eye adaptation will quietly undo a darkening or brightening over a
   second or two, flattening exactly the change we're making. Inside the hangar,
   a post-process volume should **pin exposure** (manual, or min = max) and
   **key an exposure bias** for the moment. *Keyable.* Without this the A/B/C
   comparison is unfair to B and C.

## Keyable or not

| Change | How | Keyable on the Scene sequence? |
| --- | --- | --- |
| Sky occlusion | Lumen, when the geometry closes | No keys: geometry-driven |
| Practicals strike | a few spot and rect lights | Yes: intensity and colour tracks |
| Shaft | a slot in the roof plus the sun and fog | Geometry; the haze density is keyable |
| Interior haze | Local Fog Volume | Yes: density and colour |
| Bounce | Lumen and wall material | No keys: follows the geometry |
| Exposure | post-process volume | Yes: exposure bias and blend weight |

**No actor swaps.**

**One trap:** don't key the celestial rig's own actors (the sun, moon, sky light
and height fog). The rig re-applies its phase every frame while a passage
evaluates, so keys on those actors fight it. Everything above avoids them. If
the hangar ever needs the sky itself dimmed beyond what Lumen does, that would
be a small rig feature (an interior-occlusion multiplier), not keys.

## The A/B/C test, adjusted for Lumen

- **A: the flats stand, nothing keyed.** With Lumen this is *not* "lighting
  static". The sky occlusion and bounce still change as the walls rise, so A
  measures the **geometry and its own light**.
- **B: a static box, keyed events** (practicals, interior haze, exposure bias).
  It measures the **authored light alone**.
- **C: both.**
- Pin exposure in all three, or the comparison measures the eye adaptation.

## Cost

About 10–20 shadowless lights, one Local Fog Volume and one post-process volume.
The moving flats are shadowless during the fold (the VSM trap), and take shadows,
if any, once standing. Lumen's surface-cache update while big planes move is
transient. No C++.
