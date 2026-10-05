# Underpass ambience: Gary's creative brief (5 Oct 2026, voice note from Cypress Hills, Brooklyn)

**Authority:** Gary's own words, verbatim below. The breakdown after them is the conductor's reading (inferred).

## Gary, verbatim
> I'm currently standing under an underpass in Cypress Hills in Brooklyn under a subway train. And this large lumbering
> structure is actually the perfect model for how the current wind stage and framing structure should look and feel. So
> here we're talking heavy iron girder and pipe structures. They don't need to be terribly high resolution if only having a
> decent metallic or concrete texture. And what's quite basically doing something similar to this subway train can create
> a really heavy, convincing um, upper roof surface for the moments in which there are not ceiling wings like in P05 at
> the moment. I'm also standing under a regularly blinking, almost once per second strobe light that's bouncing off the
> wet, slick floor and this kind of deep urban underpass, even with pools of puddles. on the floor is exactly what we want
> for much of the show as a kind of external ambience that the stage machine is heavy, iron, grimy and it adds quite a
> richness if we only glimpse it occasionally and are mostly focused on the beautiful wings and the very clear magical
> story that we are hearing as well as the kind of magical transitions into hangars and so on.

## Conductor's breakdown (inferred)
1. **Structure language:** the wing stage's framing rig, the InfinityStageStructureActor (cube ISMs today), becomes elevated-subway iron:
   - heavy riveted girders and I-beams, pipes, concrete piers;
   - low-res but convincing metal or concrete materials, grimy.
2. **Overhead deck:** where there are no ceiling wings (P05; P06 since tonight), a heavy subway-deck underside: beams, stringers and dark plate. It is mostly glimpsed.
3. **Floor:** dark, wet, slick, with puddle pools that reflect lights. This merges with Gary's "bring back the dark glossy floor" (one plane per Passage, stage lip to hangar).
4. **Light:** a ~1 Hz strobe/blinker bouncing off the wet floor, plus haze. Lighting events already do seeded blinkers. Note they are aperiodic by design; Gary describes a regular ~1 s strobe, so check whether he wants regular.
5. **Hierarchy:** the iron ambience is glimpsed and peripheral. The wings, the story and the hangar transitions stay the focus, so keep the rig dark, edge-lit and haze-softened.

## Next (proposed)
- Reference: Gary's photos/video from the underpass.
- A look-bench toggle for a wet-floor plane with a puddle mask and a ~1 Hz strobe.
- An underpass rig-kit plan (beam/pipe meshes + materials swapped into the Structure actor, overhead deck): Rig & atmosphere scope.

## Gary's reference photos (5 Oct, Cypress Hills): Docs/Reference/Underpass_CypressHills_2026-10-05/
What they show (conductor's read):
- **ref_01, the intersection:**
  - Deep plate girders crossing over the street, with graffiti tags on the green paint.
  - Layered decks receding into the distance.
  - A hanging traffic signal (cyan/green).
  - Wet asphalt with long red tail-light streaks.
  - Haze halos round the lights.
- **ref_02, looking down the corridor:** a rhythm of columns and repeating cross-beams under the deck.
  - The open tie/grate deck lets sky glow through in strips, so a light from above would give slatted shafts.
  - Streetlights recede in a row: a strong perspective cue, the same as our wing bays.
  - Wet road sheen.
- **ref_03 / ref_04, the columns:**
  - Built-up columns of two channels with X lacing, heavily riveted.
  - Bolted splice plates, a cast downpipe, and knee brackets into the girders.
  - Paint: green above a black lower band at about 1.5 m. Chipped, peeling and rusty.
  - Concrete pier bases, battered, spalled and graffitied.
  - The catwalk with a cable railing overhead.
- **ref_05:** a corrugated-metal fence panel with a printed vinyl banner and layered graffiti. A flat, painted, sheet-metal object: kin to the wings and to the P04 fence/tarp bays.

Design notes (inferred):
- **The bay rhythm.** The column/cross-beam rhythm maps one-to-one onto the Passage wing bays: rig columns at bay spacing, with cross-girders over each bay.
- **The deck.** The open deck gives beams for free: a light above shining down through the tie gaps makes slatted shafts in haze.
- **Materials.** Two cover nearly everything: green-painted riveted steel (rivet normals, paint chips, rust and a black lower band), and grimy concrete for the piers. Low-res is fine.
- **Floor.** Wet black asphalt or stage-floor sheen with puddles, and long specular streaks from warm and red sources.

## Gary, 5 Oct (later), verbatim
> The rigging is kind of a piece of the wider structure that only, as far as I know, changes in length and does not need
> to be immensely detailed. It would be great to build that in Blender and in the most efficient way. implement that across
> all passages as a replacement or, if more effectively, an adaptation of the current thinner stage rig system. We actually
> don't see it very often, although we might glimpse it even from the beginning. opening stage moment. And don't worry too
> much about the strobe for now. Please build a strobe and make it possible so that I can set a regular strobe light in an
> area if I need. As far as I can tell, what's distinctive about the strobe is not only its flash, but the sense of safety.
> It's like maybe a third of a second that takes it in the ground.

Conductor's reading (inferred):
- **The rig** is a modular kit authored in Blender. Only its length varies. It goes across ALL Passages, as a replacement for or adaptation of the current Structure rig, and is visible from the Opening.
- **The strobe** is a placeable, regular strobe, with Gary setting it per area.
  - CORRECTION from Gary: "sense of safety" was a mistranscription. He meant **"the ghosting that happens for about a third of a second after a strobe light takes place"**: a ~1/3 s afterimage/ghost after each flash.
