# Meshy prompts: light bulbs and stage-light housings (6 Oct 2026)

Rewritten from `FUSER_PROMPTS_BULB_HOUSING_2026-10-06.md` for **Meshy** (Text to 3D, or Image to 3D using the Fuser
reference images). One object per generation.

## Meshy settings (all prompts)

| Setting | Bulbs | Housings |
| --- | --- | --- |
| Art style | Realistic | Realistic |
| Topology | Triangle | Triangle |
| Target polycount | ~3,000 (lowest preset) | ~10,000 |
| Symmetry | On (bulbs are round) | Auto |
| PBR maps | On | On |
| Export | FBX (or GLB) | FBX (or GLB) |

Paste the **Prompt** into the prompt box and the **Negative** into the negative prompt. Meshy prompts work best short and
physical: shape, parts, materials and size, with no photo or lighting language.

**Shared negative (both batches):** `hands, cable, socket, lamp holder, chain, text, logo, label, packaging, base plate, ground, stand, multiple objects, cartoon, toy, low detail, glowing, emissive light, beam`

---

## Batch A: bulbs (scale reference: an A60 is 6 cm wide × 11 cm tall)

1. **SM_Bulb_A60_Clear.** Prompt: `A single bare incandescent light bulb, classic A60 pear shape, clear thin glass, visible coiled tungsten filament on two thin support wires and a glass stem inside, E27 screw base in dull brass with black glass insulator and solder contact tip, realistic, 6 cm wide, 11 cm tall, upright with the screw base at the top`
2. **SM_Bulb_A60_Frost.** Prompt: `A single incandescent light bulb, A60 pear shape, frosted white glass that hides the filament, E27 screw base in dull aluminium with black glass insulator, realistic, 6 cm wide, 11 cm tall, screw base at the top`
3. **SM_Bulb_G95_Clear.** Prompt: `A single large globe light bulb, G95 round shape, clear glass, long looped carbon filament on thin support wires inside, E27 screw base in dull brass, realistic, 9.5 cm diameter, 13.5 cm tall, screw base at the top`
4. **SM_Bulb_C35_Clear.** Prompt: `A single candle light bulb, slim C35 flame-tip shape, clear glass, short coiled filament inside, E27 screw base in dull brass, realistic, 3.5 cm wide, 10 cm tall, screw base at the top`
5. **SM_Bulb_ST64_Cage.** Prompt: `A single antique squirrel-cage filament light bulb, elongated ST64 teardrop shape, clear slightly amber glass, many vertical filament loops arranged in a cage around a central glass stem, E27 screw base in darkened brass, realistic, 6.4 cm wide, 14 cm tall, screw base at the top`
6. **SM_Bulb_A60_Opal.** Prompt: `A single opal milk-glass light bulb, A60 pear shape, smooth milky white glass, E27 screw base in dull aluminium, realistic, 6 cm wide, 11 cm tall, screw base at the top`
7. **SM_Bulb_A60_Worn.** Prompt: `A single old worn clear light bulb, A60 pear shape, glass faintly smoky and dusty with grey-brown haze near the top, filament visible and slightly sagging, tarnished brass E27 screw base with a little corrosion, realistic, 6 cm wide, 11 cm tall, screw base at the top`

**Extra negative for bulbs:** `broken glass, chandelier, lamp shade`

---

## Batch B: stage-light housings (scale reference: a small fresnel body is about 30 × 26 × 28 cm)

1. **SM_Lantern_Fresnel.** Prompt: `A small theatre fresnel stage light, compact boxy steel lamp body with cooling vents, round stepped fresnel glass lens at the front, U-shaped steel yoke with two side tilt knobs, pipe clamp on top of the yoke, matte black paint worn through to bare steel on edges and corners, old working theatre equipment, realistic, body 30 cm long, lens 15 cm diameter`
2. **SM_Lantern_FresnelDoors.** Prompt: `A small theatre fresnel stage light with four-leaf barn doors open on a ring at the front, compact boxy steel body with cooling vents, round fresnel lens, U-shaped steel yoke with two side knobs and a pipe clamp on top, matte black paint worn to bare steel on edges, old theatre equipment, realistic, body 30 cm long`
3. **SM_Lantern_Profile.** Prompt: `A theatre profile spotlight (ellipsoidal spot), long cylindrical lens barrel in front of a rounded lamp housing, four shutter handles around the middle, U-shaped steel yoke with two side knobs and a pipe clamp on top, matte black paint worn to bare steel on edges, old theatre equipment, realistic, 60 cm long`
4. **SM_Lantern_ParCan.** Prompt: `A theatre PAR can stage light, plain cylindrical steel can with a flat round lamp face at the front, frame-holder bracket at the front, simple bent steel yoke with two side knobs and a pipe clamp on top, matte black paint scuffed to bare steel, realistic, can 40 cm long, 22 cm diameter`
5. **SM_Lantern_Birdie.** Prompt: `A very small theatre birdie spotlight, tiny cylindrical black housing with a small round lens, short bent yoke and little clamp, matte black scuffed at the rim, realistic, 12 cm long`
6. **SM_Lantern_1950s.** Prompt: `An old 1950s theatre spotlight, rounded pressed-steel lamp body with a chimney-style vented top, round plano-convex glass lens at the front, simple flat-bar yoke with wing-nut knobs and a hook clamp, chipped black enamel showing grey primer and rust spots on the edges, realistic, 35 cm long`

**Extra negative for housings:** `colour filter, gel, safety chain, truss, stand, tripod, light beam, lens flare`

---

## If using Image to 3D instead

Use the Fuser Stage A reference images: single object, grey background, 3/4 view. Same settings as above. If Meshy offers
multi-view input, add the side and front elevations; Fuser prompts B7–B8 and A8 make them.

## After Meshy (an agent does this offline, then a create-only import)

Drop each export in `DerivedAssets/Lighting/Meshy/<name>/` and tell the conductor. The cleanup pass then:
- **scale:** sets the real size in cm (checked against the sizes above, ±10%);
- **pivot:** bulbs at the tip of the screw cap (+Z up, glass hanging in −Z); housings on the yoke tilt axis, with the
  beam along +X;
- **material slots:** **slot 0 = the part that glows** (bulb: the filament, plus the glass on frosted/opal/globe;
  housing: the lens). This is required, because the bulb code drives slot 0 only. Slot 1 = metal (cap / body + yoke).
  Slot 2 = clear glass shell (clear bulbs only);
- **triangles:** bulbs ≤ 3k; housings LOD0 ≤ 12k plus a LOD1 ≤ 3k;
- **import:** into `/Game/InfinityStage/Lighting/Bulbs` and `/Game/InfinityStage/RigAtmos/Lanterns`.

Swapping them into the lighting score (replacing today's sphere and cube stand-ins) is a separate look step, and waits
for Gary's yes.
