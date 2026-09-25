# Wing materiality — brief

For the session **"Puss · Wing materiality"**, from the conductor session, 2026-09-25.
Read `Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md` first, then this.

## What the user wants

> "we need to develop the texture of the wings themselves, so they look like
> oily painted surfaces and some look like old billboards, even though they are
> just flat images on flat planes we need to work out a way to give them a sense
> of deep materiality."

The wings are photographic cutouts on flat planes 5–10 cm thick. They cannot be
given depth by geometry — it has to come from the material. Target: **oily
painted scenic canvas** and **weathered billboard paper**, with enough variation
that 48 pairs in a row do not read as one repeated finish.

Register is Baroque stagecraft: paint, varnish, canvas, size, wear, dust in the
crevices. Not clean modern print.

## What you own

`/Game/Scenes/Wings` **materials only**. Do not touch the Show asset, the level,
the meshes, or another stream's files. If a wing needs different geometry, brief
the conductor.

## What is there now

113 meshes are in use across the six Passages, in two material families:

- **55 V2 meshes** on `M_StageOpeningV2_Relief_Master` — a relief master with
  Base/alpha, a `_H` height map driving **bump offset**, and a `_N` normal map.
  Two-sided. Slots: Front / Back / Edge.
- **58 legacy meshes** on `FBXLegacyPhongSurfaceMaterial` — separate Front and
  Back material instances, not two-sided.

So roughly half the show is on a good master and half is on an FBX import
default. Unifying that is likely your first structural decision.

## Where the depth can come from

- **Parallax occlusion** instead of simple bump offset — the height maps already
  exist, and POM is the single biggest gain in apparent depth on a flat plane.
- **Anisotropic specular** for oil paint; a varnish layer with its own roughness
  so highlights travel across the surface as the camera moves. Movement is what
  sells depth, and the camera is always moving.
- **Grime and dust driven by the height map** — darkening in the crevices,
  lightening on the raised edges, so the painted relief reads as physical.
- **Per-instance variation** so neighbours differ: tint, roughness, wear amount,
  and a per-instance random seed. The wings are placed as ISM instances, so
  per-instance custom data is the mechanism.
- **Edge treatment.** The Edge slot is currently an afterthought; a 10 cm canvas
  edge with visible batten or frayed canvas does a lot at close range.

## Constraints

- The camera passes **within a metre or two** of wings at the opening and the
  interactions, and sees them from grazing angles under raking light. Judge at
  that distance and under the stage lights, not in the material editor.
- Lighting is now **deep night with volumetric beams** — 136 shaft-casting
  fixtures on every 4th bay, everything else dim. Materials must read under
  raking, low-intensity, coloured light, not neutral daylight.
- The user may **regenerate the wing imagery entirely** if source resolution or
  look turns out to be the limit. Tell the conductor early if you conclude the
  textures, not the shader, are the ceiling — that is a big call and it is his.
- `M_wooden_floor` currently fails to compile ("Missing input texture"). Not
  yours, but do not copy its pattern.

## What you need from other streams

- **Rig & atmosphere** owns lighting. If materials need a different light to
  read, brief them; do not change lights.
- Nothing should need the Show asset. If it does, stop and ask.

## Working rules

- Source is in **git**; commit your own material work, never another stream's files.
- Content is not in git — it is covered by snapshots to `D:\PussStageBackups`.
- **Never Save All.** Save only the material assets you touched.
- Puss serves MCP on **port 8010** (MHFat holds 8000). Every script must assert
  the expected world before mutating, or a port mix-up edits the wrong project.
- Report DONE / NEXT / NEEDS-YOU to the conductor at milestones.

## Relevant paths

- `Content/Scenes/Wings/StageOpeningV2/Materials/M_StageOpeningV2_Relief_Master`
- `Content/Scenes/Wings/StageOpeningV2/Materials/Instances/`
- `Saved/CodexWingHandedness2/mesh_sections.json`, `materials.json` — per-mesh
  slot names, Front/Back material assignments and two-sidedness, already surveyed.
- `Docs/WingGenerationConventions.md` — the V2 profile the meshes were built to.
