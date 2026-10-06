# Fuser prompts: light bulb and lamp housing (6 Oct 2026)

**For:** Gary, for tomorrow's Fuser session.
- Gary 6 Oct ~02:00: "Bulb + housing: Gary makes them in Fuser tomorrow as separate assets"
  (`Docs/Conductor/GARY_PIE_NOTES_2026-10-06_overnight.md:50`).
- Earlier note: dead bulbs must "LOOK like light bulbs", and the cuboid lamp "holders should look like minimal
  stage-lighting pieces" (`GARY_PIE_NOTES_2026-10-05.md:255-256`).

**Format.** The same as the queue's no-reference blocks
(`DerivedAssets/FlatV3/FuserQueue/BATCH8_no_reference_blocks.txt`, `BATCH8_series_gobos_2026-10-05.txt`):
- one prompt per paragraph;
- `§§` between the Text Split slots: input, subject, look, form, avoid, framing;
- `~~` between prompts;
- 8 per paste.
- Like the queue's own check, these prompts avoid the words the queue refuses ("curtain", "gobo", "slide";
  `MORNING_SUMMARY_2026-10-05_overnight.md:47`).

**Two stages, because the Fuser jobs so far are image jobs.**
1. **Stage A (below)** makes ONE clean reference image per asset: a single object, neutral background, even light, a
   3/4 view, all of it in frame. That is the input an image-to-3D node wants.
2. **Stage B** feeds the picked image to whatever image-to-3D node Gary's Fuser has. Its node name and options are not
   known here [inferred: the queue's README describes image jobs only, `FuserQueue/README.md:1-5`]. If Fuser has no 3D
   node, the same images go to any image-to-3D tool.

Tiers, per AGENTS.md:
- **[decl]** = read in a file (cited);
- **[inf]** = inferred, with the reason.

---

## What each mesh must satisfy before import

These hold for both assets. AI 3D output arrives at an arbitrary scale and orientation, with one merged material and
often 100k+ triangles [inf: typical image-to-3D output]. So expect one Blender cleanup pass per mesh: decimate, split by
material, set the pivot, set the scale, export FBX.

| | Bulb | Housing (lantern) |
| --- | --- | --- |
| **Units / scale** | Real size, in cm: A60 = Ø 6.0 × 10.8 cm; G95 globe = Ø 9.5 × 13.5 cm; C35 candle = Ø 3.5 × 9.8 cm; E27 cap = Ø 2.7 cm thread, about 2.5 cm tall | Real size: small fresnel body about 30 × 26 × 28 cm (L × W × H), lens Ø 15 cm; yoke about 40 cm across; profile body 55–65 cm long; barn-door leaves about 18 × 20 cm |
| **Pivot** | At the **tip of the E27 cap** (the hanging point). Axis +Z up; the glass hangs in −Z | On the **yoke tilt axis** (through the two yoke bolts), centred between the arms. The beam points along **+X** (UE forward = a spot light's direction); the yoke clamp is up (+Z), for hanging from a pipe |
| **Material slot 0** | **Everything that glows**: the filament, plus the glass for frosted/opal/globe variants. An emissive MI of `M_UP_TubeEmissive`, scalar `Intensity` | **The lens** (the front glass), so it can glow with its light |
| **Material slot 1** | The metal cap and contact (dull brass/aluminium) | The body + yoke (matte black, worn) |
| **Material slot 2** | Clear variants only: the clear glass shell (thin, glossy, not emissive) | Barn doors / hardware, if they are kept separate; otherwise merge them into slot 1 |
| **Triangles** | ≤ 3k (many instances; one sits in every PRACTICAL slot) | LOD0 ≤ 12k, LOD1 ≤ 3k beyond about 15 m (as Flat V3's LOD rule, AGENTS.md "Exception, Flat V3") |
| **UVs** | One clean channel; the glass needs none beyond the default | One channel, no overlaps on the body; the worn-paint texture is local, not AI |
| **Name** | `SM_Bulb_A60_Clear`, `SM_Bulb_A60_Frost`, `SM_Bulb_G95_Clear`, `SM_Bulb_C35_Clear`, … | `SM_Lantern_Fresnel`, `SM_Lantern_FresnelDoors`, `SM_Lantern_Profile`, `SM_Lantern_ParCan` |

**Why slot 0 must be the glowing part [decl]:**
- The bulb-body code reads the authored `Intensity` from **material 0** and makes its dynamic instance on **slot 0**
  (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:1790-1803`).
- The header names the glass material: "M_UP_TubeEmissive or an MI of it, scalar 'Intensity'"
  (`Public/InfinityStageBulbBody.h:11-13`).
- So any glow on another slot will not follow the light's drama or flicker.

**Today's stand-in [decl]:** an engine Sphere scaled 0.10 × 0.10 × 0.13 (about 10 × 10 × 13 cm), plus a dull cylinder
cap, because "no real light-bulb mesh exists in Content (searched 6 Oct …)"
(`Saved/CodexConductor/lighting_scores_round2_build.py:31, 83-86`).
- A real A60 is smaller (6 × 11 cm). If it reads too small from the camera, place it at scale 1.3–1.5. That is a look
  call, not an import one.

**Import traps** (memory *ue58-fbx-import-traps*): Interchange ignores FbxImportUI; a LodGroup can split LODs; V must run
down; call `modify()` before setters. Import create-only into `/Game/InfinityStage/Lighting/Bulbs` [decl: the folder the
score uses, `lighting_scores_apply.py`] and `/Game/InfinityStage/RigAtmos/Lanterns` (new).

---

## Batch A: the bulb (8 prompts, one paste)

=== BULB_bare_incandescent_series (8 prompts) ===
no input image; a single product reference image for 3D reconstruction is required §§ create one bare incandescent light bulb, classic A60 pear shape, CLEAR glass, a visible coiled tungsten filament on two thin support wires and a glass stem inside, an E27 screw base in dull brass with a black glass insulator and a small solder contact at the tip; the bulb unlit §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, crisp but not over-sharpened, accurate proportions §§ one object only, the screw base at the TOP and the glass hanging below it, upright and straight, seen from a gentle three-quarter view slightly above, the whole bulb in frame §§ hands; socket; lamp holder; cable; reflections of a room; text; logos; brand marks; packaging; cartoon; stylisation; dramatic shadows; glow; lens flare §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one bare incandescent light bulb, A60 pear shape, FROSTED white glass that hides the filament, an E27 screw base in dull aluminium with a black glass insulator and a small solder contact at the tip; the bulb unlit §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, accurate proportions §§ one object only, the screw base at the TOP and the glass hanging below it, upright and straight, seen from a gentle three-quarter view slightly above, the whole bulb in frame §§ hands; socket; lamp holder; cable; text; logos; brand marks; packaging; cartoon; stylisation; dramatic shadows; glow §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one large GLOBE light bulb, G95 round shape, CLEAR glass, a long single looped carbon filament visible inside on thin support wires, an E27 screw base in dull brass with a black glass insulator §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, accurate proportions §§ one object only, the screw base at the TOP and the round glass hanging below it, upright and straight, seen from a gentle three-quarter view slightly above, the whole bulb in frame §§ hands; socket; lamp holder; cable; text; logos; packaging; cartoon; stylisation; dramatic shadows; glow §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one CANDLE light bulb, slim C35 flame-tip shape, CLEAR glass, a short coiled filament visible inside, an E27 screw base in dull brass with a black glass insulator §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, accurate proportions §§ one object only, the screw base at the TOP and the pointed glass tip hanging below it, upright and straight, seen from a gentle three-quarter view slightly above, the whole bulb in frame §§ hands; socket; chandelier; cable; text; logos; packaging; cartoon; stylisation; dramatic shadows; glow §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one antique squirrel-cage filament light bulb, elongated ST64 teardrop shape, CLEAR slightly amber-tinted glass, many vertical filament loops in a cage around the stem, an E27 screw base in darkened brass §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, accurate proportions §§ one object only, the screw base at the TOP and the glass hanging below it, upright and straight, seen from a gentle three-quarter view slightly above, the whole bulb in frame §§ hands; socket; lamp holder; cable; text; logos; packaging; cartoon; stylisation; dramatic shadows; glow §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one OPAL milk-glass light bulb, A60 pear shape, smooth milky white glass, an E27 screw base in dull aluminium with a black glass insulator §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, accurate proportions §§ one object only, the screw base at the TOP and the glass hanging below it, upright and straight, seen from a gentle three-quarter view slightly above, the whole bulb in frame §§ hands; socket; lamp holder; cable; text; logos; packaging; cartoon; stylisation; dramatic shadows; glow §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one OLD WORN clear A60 light bulb, the glass faintly smoky and dusty with a grey-brown haze near the top, the filament visible and slightly sagging, an E27 screw base in tarnished brass with a little corrosion §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, accurate proportions §§ one object only, the screw base at the TOP and the glass hanging below it, upright and straight, seen from a gentle three-quarter view slightly above, the whole bulb in frame §§ hands; socket; broken glass; cable; text; logos; packaging; cartoon; stylisation; dramatic shadows; glow §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one bare incandescent light bulb, A60 pear shape, CLEAR glass, a visible coiled filament, an E27 screw base in dull brass; shown EXACTLY SIDE-ON at eye level as a straight orthographic elevation for measuring proportions §§ neutral technical product photograph, flat even light, no perspective distortion, accurate proportions §§ one object only, the screw base at the TOP and the glass hanging below it, perfectly vertical, the whole bulb in frame §§ hands; socket; cable; text; logos; packaging; cartoon; stylisation; shadows; glow; three-quarter view §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; portrait 1:2

**Variants this batch gives:**
- clear A60 (the default);
- frosted A60;
- globe G95;
- candle C35;
- plus three looks: squirrel-cage, opal, worn.

The 8th prompt is a side elevation of the clear A60, for checking proportions. It is not a 3D input. A real C35 candle
usually takes an E14 cap; the brief says E27, so the prompt says E27, which is Gary's call.

---

## Batch B: the housing (8 prompts, one paste)

=== LANTERN_minimal_stage_light_series (8 prompts) ===
no input image; a single product reference image for 3D reconstruction is required §§ create one small theatre FRESNEL stage light: a compact boxy lamp body with cooling vents, a round stepped fresnel lens at the front, a U-shaped steel yoke with two side knobs, a pipe clamp on top of the yoke, matte black paint worn through to bare steel on the edges and corners, no barn doors §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, plain and minimal, old working theatre equipment §§ one object only, the lens facing toward the viewer's left in a three-quarter view slightly above, the yoke above the body with the clamp at the top, the whole lantern in frame, the lens unlit §§ hands; cable; safety chain; label; text; logos; brand marks; colour filter; cartoon; stylisation; dramatic shadows; glow; beam; lens flare §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one small theatre FRESNEL stage light with FOUR-LEAF BARN DOORS on a rotating ring at the front: a compact boxy lamp body with cooling vents, a round stepped fresnel lens behind the barn doors, a U-shaped steel yoke with two side knobs, a pipe clamp on top, matte black paint worn to bare steel on the edges §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, plain and minimal, old working theatre equipment §§ one object only, the barn doors open, the front facing toward the viewer's left in a three-quarter view slightly above, the yoke above the body with the clamp at the top, the whole lantern in frame, the lens unlit §§ hands; cable; safety chain; label; text; logos; colour filter; cartoon; stylisation; dramatic shadows; glow; beam §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one theatre PROFILE spotlight (an ellipsoidal spot): a long cylindrical lens barrel in front of a rounded lamp housing, four shutter handles sticking out around the middle, a U-shaped steel yoke with two side knobs and a pipe clamp on top, matte black paint worn to bare steel on the edges §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, plain and minimal, old working theatre equipment §§ one object only, the barrel pointing toward the viewer's left in a three-quarter view slightly above, the yoke above the body with the clamp at the top, the whole lantern in frame, the lens unlit §§ hands; cable; safety chain; label; text; logos; colour filter; cartoon; stylisation; dramatic shadows; glow; beam §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; landscape 2:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one theatre PAR CAN stage light: a plain cylindrical steel can with a flat round lamp face at the front, a simple bent steel yoke with two side knobs and a pipe clamp on top, a frame-holder bracket at the front, matte black paint scuffed to bare steel §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, plain and minimal, old working theatre equipment §§ one object only, the face pointing toward the viewer's left in a three-quarter view slightly above, the yoke above the can with the clamp at the top, the whole lantern in frame, the lamp unlit §§ hands; cable; safety chain; label; text; logos; colour filter; cartoon; stylisation; dramatic shadows; glow; beam §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one very small theatre BIRDIE spotlight: a tiny cylindrical black housing about the size of a fist with a small round lens, a short bent yoke and a little clamp, matte black paint scuffed at the rim §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, plain and minimal, old working theatre equipment §§ one object only, the lens toward the viewer's left in a three-quarter view slightly above, the yoke above with the clamp at the top, the whole lantern in frame, the lens unlit §§ hands; cable; label; text; logos; colour filter; cartoon; stylisation; dramatic shadows; glow; beam §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one OLD 1950s theatre spotlight: a rounded pressed-steel lamp body with a chimney-style vented top, a round plano-convex lens at the front, a simple flat-bar yoke with wing-nut knobs and a hook clamp, chipped black enamel showing grey primer and rust spots on the edges §§ neutral studio product photograph, soft even light from all sides, true-to-life materials, plain, minimal and well used §§ one object only, the lens toward the viewer's left in a three-quarter view slightly above, the yoke above the body with the clamp at the top, the whole lantern in frame, the lens unlit §§ hands; cable; label; text; logos; colour filter; cartoon; stylisation; dramatic shadows; glow; beam §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one small theatre FRESNEL stage light, compact boxy body with vents, round fresnel lens, U-shaped steel yoke with two side knobs and a pipe clamp on top, matte black worn to bare steel on the edges; shown EXACTLY SIDE-ON as a straight orthographic elevation, the lens pointing LEFT, the yoke vertical above §§ neutral technical product photograph, flat even light, no perspective distortion, accurate proportions §§ one object only, perfectly level, the whole lantern in frame §§ hands; cable; label; text; logos; cartoon; stylisation; shadows; glow; beam; three-quarter view §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1
~~
no input image; a single product reference image for 3D reconstruction is required §§ create one small theatre FRESNEL stage light, compact boxy body with vents, round fresnel lens, U-shaped steel yoke with two side knobs and a pipe clamp on top, matte black worn to bare steel on the edges; shown from DIRECTLY IN FRONT, looking straight into the lens, the yoke arms on both sides §§ neutral technical product photograph, flat even light, no perspective distortion, accurate proportions §§ one object only, perfectly level and centred, the whole lantern in frame, the lens unlit §§ hands; cable; label; text; logos; cartoon; stylisation; shadows; glow; beam; three-quarter view §§ the object centred and isolated on a plain flat mid-grey background #808080, touching no edge, with a clear gap all round; square 1:1

**Variants this batch gives:**
- fresnel (the default);
- fresnel with barn doors;
- profile;
- PAR can;
- birdie (small, for floor and practical spots);
- an old 1950s lantern.

Prompts 7–8 are side and front elevations of the fresnel, for proportions. If the 3D node accepts several views, feed
them as extra views with the 3/4 image.

---

## Picking and handing over

1. **Pick one 3/4 image per asset** for Stage B, judged on silhouette and proportions. Surface detail is re-textured
   locally anyway.
2. **Run image-to-3D.** Save the GLB/FBX next to the picked image, as `DerivedAssets/Lighting/Fuser/<name>/`.
3. **Cleanup and import, by an agent, offline then create-only:**
   - decimate to the budget;
   - split the materials into the slot order above;
   - set the pivot and the real-size scale;
   - check: bounds against the table above (±10%), the pivot at the cap tip / yoke axis, the beam along +X, slot 0 =
     the glowing part, and the triangle count.
4. **The score swap is a separate step.** The `visible_mesh.mesh` of the PRACTICAL slots in `lighting_scores.json`
   goes to the new mesh. It is a look decision, so it waits for Gary's own yes.
