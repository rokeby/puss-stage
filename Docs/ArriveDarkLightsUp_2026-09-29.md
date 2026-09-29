# Arrive in near dark, then lights up: the ghost light and the strike

Design only, 29 September 2026, Rig & atmosphere. Gary: *"keep the new
box/hangar/soundstage virtually unlit, only lit via an 'exit sign' style light
when we enter them, before pinging the lights on when we're ready, in a
dramatic way"*, and *"maybe the new passage only gets fully lit with a delay."*
It's one rhythm for the whole show, at every scene and every passage.

## 1. The ghost light: what the one light is

**Recommendation: a real ghost light.** A bare incandescent bulb in a wire cage
on a stand about 1.8 m tall, on a small wheeled base: the lamp a theatre leaves
burning on an empty stage. It's practical geometry the audience can see, so it
reads as a work light on an empty stage, not as ambient.

- **Where:** on the floor a few metres in from the entrance, **off the cat's
  line** (down-left of centre), in the arriving camera's view. It stands *in*
  the space and gives it scale.
- **Light:** one point light at the bulb, warm (2400–2700 K), small reach
  (8–12 m), and low (tuned so its pool is a few lux at the stand, falling to
  near black at the walls). **It casts shadows:** the stand's long shadows up
  the walls are the ghost light's signature. One shadowed light is affordable;
  it's hundreds that aren't.
- **Bulb:** an emissive bulb material so the lamp itself glows, plus a
  hint of haze bloom (below).
- **At the ping:** it can stay on (humble among the new lights), or dim out as
  the rank comes up, like a theatre's work light giving way to the rig. That
  handover is its own small beat. Gary's choice.
- **Alternative, if he means it literally:** a caged lamp, or a small emissive
  sign, above the entrance doorway. It's quieter and reads as architecture, not
  stagecraft. The ghost light is the stronger image.

## 2. The fold happens in the dark

The box folds lit only by the ghost light, so the VSM spike from big moving
walls **doesn't happen**: there's one shadowed light, not hundreds. Moving walls
invalidate only its pages, briefly. The fold reads as shapes moving through a
single warm pool and long shadows, which suits it.

## 3. The ping: lights up

The practicals rank from the light-event design (warm 2700–3000 K, shadowless,
each ramping on over about 0.2 s) now comes **after** the fold. It strikes in a
**wave running ahead of the camera**: nearest first, then further along, not
all on one frame. That's the drama, and the cost is spread out (Gary's "never
visible in the same frame"). The interior Local Fog Volume rises with it
(0 → about 0.02), blooming the lamps. The ghost light holds or gives way.

## 4. Exposure is the precondition

A near-dark arrival is exactly what auto exposure flattens: it would brighten
"virtually unlit" to "merely dim" within a second or two, then pull the ping
back down. **Pin exposure** in the box (a post-process volume, manual or min =
max) and **key an exposure bias** across the ping. Without it the rhythm doesn't
read.

## 5. Passages: the same rhythm

- **Before:** in a passage the exterior dusk sky still fills (passages are
  open), so arriving dark means the rig unstruck. The dusky fill plus the ghost
  light at the passage mouth; P04–P06 "barely lit" was an accidental version of
  this. **Then:** at a lights-up point a few metres in, the passage's rig
  strikes in a wave running ahead.
- **Mechanism, which mostly exists:** Light Drama already strikes lamps on
  approach, **driven by camera distance** (the house rule: scrub-safe,
  deterministic under transport jumps), and an unstruck lamp is switched off
  (`SetVisibility(false)`), so it costs nothing while dark. What's missing is a
  **passage-level gate**:
  - a lights-up distance per passage;
  - each lamp striking when the camera passes the gate plus a small travel per
    rank (e.g. 50 cm of camera travel per lamp rank);
  - so the wave runs quickly ahead and settles, instead of each lamp striking
    only when the camera reaches it.
- **Cost:**
  - C++ in Light Drama and the passage settings, and one build.
  - A Show write to opt the rig in, per passage.
  - Render cost: lower than now until the gate, then the same.

## 6. Not built. Open for Gary

- Ghost light on a stand, or the exit lamp.
- Does it stay on or give way at the ping?
- Wave speed: a snap, or a roll.
- Whether every passage takes the rhythm, or only the ones after a scene.
