# Infinity Stage ground design

## Creative direction

The ground is not a background texture. It is the closest piece of scenery to the camera and should carry evidence of use: repairs, compression, dampness, swept paths, footprints, leaf fall, and the boundary between tended and untended space.

The visual target is **tactile theatrical realism**: materially convincing at close range, slightly composed and storybook in shape and colour, and controlled enough that the wing artwork remains the visual lead.

![Floorboards, forest floor, and beaten-track transition concept](../DerivedAssets/GeneratedConcepts/GroundSystem/Ground_Surface_Transition_Concept_v01.png)

This image is a visual-development reference, not a texture source. Its useful idea is the transition language: soil and moss invade the timber joints; forest litter becomes thinner and more compressed until it reads as a track.

## Core decision

Use separate, section-owned **Ground Zones**, in line with the Infinity Stage specification, rather than one enormous plane whose material changes for the whole show.

- A Passage or Scene can own one or more Ground Zones.
- Separate spatial bays are the default for major world changes.
- A Ground Zone can be a modular mesh floor, spline strip, terrain mesh/Landscape, Level Instance, or artist-built set.
- Continuous changes use an art-directed overlap zone.
- Disconnected worlds change behind a Scene cut.
- The ground remains persistent and visible in the editor; it is not spawned at playback time.

This preserves editability and lets forest, theatre floor, path, shore, or stone exist together without forcing one universal shader to solve every geometric problem.

## The three-layer construction

Every Ground Zone should separate three responsibilities.

### 1. Walkable substrate

A simple, stable collision surface defines the performance floor. It must not inherit the tiny bumps, cracks, or scattered pieces used for appearance.

- Keep the main walking line broadly level.
- Use simple collision even when the visible surface is Nanite/high detail.
- Keep ordinary dressing below about 8 cm on the safe walking line.
- Push roots, stones, lifted boards, plants, and deep ruts toward the margins.

### 2. Hero surface

The hero surface supplies the large and middle scales: board layout, terrain undulation, compacted track, ruts, eroded edges, repairs, and main material breakup.

It may be modular geometry, a spline strip, a terrain mesh, or Landscape. Material displacement alone should not be expected to create every silhouette or transition.

### 3. Dressing and history

Small geometry, decals, and controlled scatter provide specificity: leaves in cracks, twigs, pebbles, nail heads, mud splashes, footprints, worn board centres, damp pockets, and sparse plants.

Dressing density should be mask-driven and biased away from the central walking line. Manual hero placements remain possible on top of procedural scatter.

## Master material family

Create one shared surface framework, `M_Ground_Master`, but allow specialised child materials where the geometry differs. Each material instance should expose the same art-direction vocabulary where practical.

| Control | Purpose |
| --- | --- |
| Base colour, normal, packed AO/roughness/height | Primary PBR surface set |
| Local or world UV scale/rotation | Correct scale without re-authoring textures |
| Macro tint and macro roughness breakup | Prevent repetition over long passages |
| Detail normal and detail roughness | Hold up in low, grazing camera angles |
| Dampness | Darken colour, reduce roughness, and strengthen normals selectively |
| Dirt/litter overlay | Connect adjacent surface types and accumulate history |
| Wear/compaction mask | Create the travelled centre and protected edges |
| Per-instance variation | Break repeated modular panels without extra instances |
| Distance fade | Remove expensive micro detail when it no longer contributes |

Do not blend only base colour. A believable change must blend colour, normal, roughness, height response, and dressing density together.

The current `M_StageMovingGround` is useful as a legacy reference for tiling/offset, but it only samples the wooden colour texture. It should not become the new master.

## Surface recipes

### Worn floorboards

Use the existing high-poly wooden floor as the first hero-surface candidate:

- `/Game/KK_S1_Animals/Wooden_Floor/StaticMeshes/wooden_floor_highpoly`
- `/Game/KK_S1_Animals/Wooden_Floor/Textures/wooden_floor_Albedo`
- `/Game/KK_S1_Animals/Wooden_Floor/Textures/wooden_floor_Normal`
- `/Game/KK_S1_Animals/Wooden_Floor/Textures/wooden_floor_Roughness`

Visual notes:

- Run boards primarily along the direction of travel so perspective reinforces the passage.
- Establish several board widths and lengths rather than a perfect grid.
- Use dark, shallow joints; avoid deep gaps on the walking line.
- Add repaired boards, restrained nail/peg detail, heel scuffs, and a slightly polished central route.
- Keep dampness local to edges, entrances, or the forest transition.
- Vary repeated modules with 180-degree rotation, tint, roughness, and decal passes.

### Natural forest floor

Build the forest floor as layers, not as one green-brown texture.

Available starting material:

- `/Game/MWTropicalRainforest/Textures/Ground/TEX_TRF_GroundMoss_col`
- `/Game/MWTropicalRainforest/Textures/Ground/TEX_TRF_GroundMoss_nrm`
- `/Game/MWTropicalRainforest/Textures/Ground/TEX_TRF_GroundMoss_msk`
- Rainforest grass and small-plant meshes under `/Game/MWTropicalRainforest/Meshes/Plants`
- Leaf meshes under `/Game/KK_S2_Shrine/Falling_Leaves/Mesh`

Visual notes:

- Begin with dark soil and make moss, litter, roots, stones, and plants separate distributions.
- Use a soft depression/compaction mask through the travelled centre.
- Concentrate intact leaves, moss, and shoots at protected edges.
- Mix a few recognisable hero roots and stones into lower-frequency random scatter.
- Use damp, darker roughness variation in hollows rather than making the whole floor glossy.

### Beaten track

The track is compacted forest soil, not a separate beige carpet.

Existing dirt assets under `/Game/KK_S1_Animals/Dirt_etc` can be evaluated as temporary source material; a dedicated earth PBR set will probably be required for the final result.

Visual notes:

- Shape two or three broad paths of use rather than a perfectly centred stripe.
- Let the middle be smoother, lighter, and more compacted, with damp dark pockets.
- Keep shallow ruts and footprints readable through grazing light without compromising the collision floor.
- Distribute pebbles, leaf fragments, and grass increasingly toward the edges.
- Break the track outline with erosion, puddled patches, and small areas where forest growth returns.

## Transition language

Transitions should tell a physical story and normally occupy 2–4 m, adjusted for camera speed.

### Floorboards to forest

1. Dirt gathers in board joints.
2. Moss and leaf fragments appear in protected cracks.
3. Several boards become darker, worn, or partly obscured.
4. Soil and litter cover more of the timber until only broken board rhythms remain.
5. Forest-floor geometry takes full ownership.

### Forest to beaten track

1. Plants and intact litter thin out.
2. Leaves fragment and soil becomes exposed.
3. A compaction band strengthens and the surface becomes smoother.
4. Repeated footprints/ruts establish direction.
5. Edge vegetation frames a clearly readable track.

For hard world changes, do not fake this blend. Use independent Ground Zones in separate bays and conceal the switch with the Scene's camera language.

## First vertical slice

Build a camera-test strip before authoring a full Passage:

- 15 m long by 6 m wide, or scaled to the current passage envelope.
- 5 m worn boards, 5 m forest floor, 5 m beaten track.
- Maintain one continuous safe collision plane.
- Include both transition types in the same strip.
- Dress the centre lightly and the outer 1–1.5 m richly.
- Test with the production camera height, focal length, speed, shadow figures, and representative wing lighting.
- Review from the actual moving camera and one low grazing angle; an overhead editor view is not an approval view.

The first pass succeeds when:

- repeated tiling is not obvious during a complete camera move;
- the surface reads as detailed without competing with characters and wings;
- transitions read as physical accumulation/erosion rather than shader crossfades;
- the performance line remains visually and physically safe;
- no bay edge or ground seam enters an establishing or closing shot; and
- material/dressing density can be reduced predictably for performance.

## Suggested asset layout

```text
/Game/InfinityStage/Ground/
  Materials/
    M_Ground_Master
    Functions/
      MF_Ground_MacroVariation
      MF_Ground_Dampness
      MF_Ground_WearMask
      MF_Ground_Transition
    Instances/
      MI_Ground_Floorboards_Worn
      MI_Ground_ForestFloor_Damp
      MI_Ground_BeatenTrack
  Meshes/
    Floorboards/
    ForestFloor/
    Track/
    Dressing/
  Blueprints/
    BP_GroundZone_Prototype
  PCG/
    PCG_GroundEdgeDressing
  Tests/
    L_GroundLookdev
```

`AInfinityStageGroundZone` is specified but not yet implemented in the plugin. The look-development strip can begin with a lightweight prototype Blueprint, then migrate to the registered actor once Ground Zone runtime/editor support is built.

## Deliberate non-goals for the first pass

- No single material graph that tries to solve wood, soil, stone, water, and vegetation identically.
- No runtime regeneration of fixed ground.
- No dense foliage across the central performance line.
- No deep tessellation/displacement collision.
- No full-show procedural generation before one camera-tested strip is approved.

## Generated concept provenance

The concept image was generated with the built-in image-generation tool from a project-specific prompt for a three-quarter overhead theatrical ground strip. It was requested as visual development only, with no characters, labels, walls, or large obstacles, and with surface dressing constrained to a broadly level, actor-safe plane.
