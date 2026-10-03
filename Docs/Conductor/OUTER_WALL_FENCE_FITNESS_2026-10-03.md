# Can the chain-link fence become the main outer wall? (for the 3 Oct talk)

By the Wings & Textures stream, 3 Oct. This answers Gary's question: "Is that asset good enough to develop as the main outer wall material? With barbed wire over the top?"

## Short answer

**The look is a good starting point. The current asset is not the wall: it was built as a stage wing, not a wall module.** Developing it into one is a moderate job, roughly one offline build session plus one placement slot, and the placement belongs to the Structure/Rig stream.

## What the current asset is (each claim marked with how it is known)

| Fact | Value | Proof tier |
|---|---|---|
| Size of one panel | 8.5 m wide × 12 m tall (plus 1 m pole below the base) | **measured**: `DerivedAssets/FlatV3/Overnight/P02Industrial/validation.json` (bounds_m) |
| Geometry | real wire diamonds (about 25 cm) as geometry, with barbed-wire coil on top, a tarp panel (FenceTarp) and baked steel poles | **declaration-proven**: `P02Industrial/REPORT.md`, `build_p02_industrial.py` |
| Triangles | LOD0 29,646 / LOD1 2,558 per panel | **measured**: `P02Industrial/REPORT.md:22` |
| Material slots | Front/Flap/Timber/Edge. Edge and Flap hold only **token faces** (Edge 2 faces, Flap 1), added so the slots import | **measured**: the Edge rebuild report, 2 Oct |
| Surfaces | CC0 scans (galvanised, rusted steel, grimy tarp) in Blender. In Unreal the panel uses the billboard Front material with baked skin textures | **inferred**: the import created baked SkinColor/Mask/Normal textures for each asset; the Unreal render of the fence has not been reviewed yet |
| Edges | not designed to butt seamlessly against the next panel (each panel ends at its own pole) | **declaration-proven**: built as an L/R wing pair with backbone poles |

## Why it isn't the wall as-is

1. **Not modular.** A wall is a long run of identical bays that must butt cleanly with shared posts. These are one-off wing panels with their own poles at each end, so a run of them shows doubled posts every 8.5 m.
2. **Thin wire as geometry, viewed at a distance:** the wire is about 1 cm thick with 25 cm cells. Seen at an angle and from far away, it is a classic source of shimmer and moiré under TSR. That could plausibly be part of the **"hatching"** Gary saw. This is **inferred**: the conductor's hatching probe should confirm or exclude it before we commit to this construction.
3. **Cost at wall scale:** both sides of six passages at 8.5 m per panel need a few hundred panels. At about 30k triangles each that is several million triangles of thin wire. Nanite or LODs can carry it, but this is the wrong place to spend triangles (**inferred**, not profiled).
4. **The "holey tarp"** is currently opaque cloth with a few holes. As a wall that "mostly blocks external light except the odd beam", the holes are what make the beams. They would need placing deliberately against the lighting plan, not randomly.
5. **Lighting trees:** the posts have no mounts. Two lower lamps per wing on vertical trees means sockets (e.g. `SOCKET_Lamp_n`) at fixed heights on each post, which is easy to add in a purpose-built module.

## Proposed path (if Gary says go)

- **Wall bay module**, built offline with the same pipeline:
  - 4 m bays sharing posts; 12 m tall; barbed-wire coil as geometry on top only;
  - chain-link as a **masked opacity texture** on a single plane, with real-scale tiling and mips, instead of wire geometry (removes the moiré risk and the triangle cost);
  - tarp as a separate overlay with authored holes ("beam windows");
  - post sockets for the lamp trees;
  - a few bay variants: open, tarp, torn tarp, door gap.
- **Placement:** run continuously along each passage's outer edge as a kit, owned by Structure/Rig (outside the wing positions). Light rigs mount on the post sockets.
- **Cost estimate:** about one offline Codex session for the module, plus a review render, then one placement slot. That is an estimate, not measured.
- **Prerequisites:**
  - the hatching probe result: confirm whether thin geometry or masked edges are part of the problem;
  - Gary's choice on the fence taper (item 5, renders in progress).

## What is NOT claimed

How the current fence actually looks in Unreal under the show lighting has not been reviewed. Everything above about the Unreal render, moiré and cost is inferred.
