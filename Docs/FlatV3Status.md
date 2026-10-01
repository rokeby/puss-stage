# Flat V3 status

Stream: "Puss - Wings and Textures". Spec: [FlatV3Spec_2026-09-30.md](FlatV3Spec_2026-09-30.md).
Passage cards: [FlatV3PassageCards_2026-09-30.md](FlatV3PassageCards_2026-09-30.md).
Updated 1 Oct 2026. As of then the conductor (v2) is retired, so editor needs go
in `Docs/Conductor/BUILD_WINDOW_QUEUE.md` or to Gary.

## Done (offline, verified)

| What | Where | Proof tier |
| --- | --- | --- |
| Sourcing, passes 1-3: 205 scored candidates, contact sheets, BY_PASSAGE pairs | `DerivedAssets/FlatV3/Sourcing/` | measured (licence fields read per item) |
| 175 PD/CC0 originals, 2.6 GB, SHA-256 verified | `D:\PussStageSources\FlatV3\` (+ `MANIFEST.json`; E: copy in Sourcing/) | measured |
| Gallica Torelli sheets: reference only | `use_restriction` in the manifest | declared (Gary, 1 Oct) |
| Local toolchain (SAM 2.1, Grounding DINO, LaMa, Real-ESRGAN, torch cu128) | `D:\PussStageTools\FlatV3\` (+ `DerivedAssets/FlatV3/TOOLS.md`) | measured (5/5 smoke tests) |
| Cutout test A/A2 (Ruisdael), B (Hollar row), C (Torelli colour) | `DerivedAssets/FlatV3/CutoutTest/` | measured; A2 cut accepted without hand fix |
| Blender scaffold bay and thunderbolt placeholder | `DerivedAssets/FlatV3/BlenderTest/` | measured |
| Frame/pole v1 + CC0 timber, ply, steel and paper library | `DerivedAssets/FlatV3/FrameTest/`, `DerivedAssets/TextureLibrary/` | measured (re-import PASS, head-on containment PASS) |
| Billboard skin v1 | `DerivedAssets/FlatV3/SkinTest/` | measured; look: paper good, peels wrong (fixed in the fix-up) |
| Billboard master (built by Wing materiality) | `/Game/Scenes/Wings/PaintedSurface/Billboard` | their read-back; not rendered |

## Running / next

1. **Pilot fix-up and package:** torn peels, aged timber, the four-slot contract,
   the pilot FBX and import plan. Run: `Saved/CodexRuns/flatv3_fixup_prompt.md` ->
   `DerivedAssets/FlatV3/Pilot/` (`IMPORT_PLAN.md`). Then: **editor slot** to import
   under `/Game/Scenes/Wings/FlatV3/Pilot/` (new names only), via
   `Scripts/codex.sh --unreal`. The one test Show occurrence needs a backup, a dry
   run, read-back, a revert script and Gary's OK on the position.
2. **Scene 3 backdrop: Gary chose option 5, Whistler *Opal Beach*** (Smithsonian
   CC0), NOT van Goyen. Gary's edits: 20-30 huddled figures in white head-cloths
   in three huddles; a few dotted distant cottages; a sketchy trail of bones.
   Edit route: Nano Banana in Fuser, run by Gary manually (pack:
   `DerivedAssets/FlatV3/Scene3/fuser_pack/FUSER_EDIT.md`). Then Codex composites
   the edited regions into the full-resolution scan and builds the 20x30 m backdrop
   (a child MI of `MI_Billboard_Front` on Rig's plane). Picks and mockups:
   `DerivedAssets/FlatV3/Sourcing/SCENE3_COAST/picks/`.
3. **Scene 3 wave rows:** 3 rows x 2 halves (>= 12 m), heights about
   1.2 / 1.8 / 2.6 m at about 35 / 45 / 55 m. Sources: Bakhuysen *Rough Sea*,
   Porcellis, Hollar (on D:). Starts when the GPU is free. Keyed by Rig, no sockets.
4. **Torelli colour test:** Gary's Fuser run (pack:
   `DerivedAssets/FlatV3/CutoutTest/C/nano_banana_pack/FUSER_PIPELINE.md`).
5. Gary picks per passage from the contact sheets, starting with P04.

## Later / bonus (Gary, 1 Oct)

- Flats hanging from the rig, such as clouds (P05's good cloud flats are the
  obvious first family). Hung on Rig's gridiron; the hanging hardware is Rig's.
- S3 backdrop: Gary's Fuser run produced a PORTRAIT version with lots of sky.
  It may replace the fog-gradient extension. Evaluate it against the plan: does
  the lower painting stay faithful to Whistler, and at what resolution? If it
  drifts, use only its sky over the full-resolution scan.

## Open decisions for Gary

- Mixed stage (V3 flats with poles beside legacy cards without), judged at the pilot.
- Topple, turn and trap mechanism C++ (with Rig; nothing built without his go).
- Celadon L3 in S3 (row 3 moves to about 52 m if it stays).
