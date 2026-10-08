# P12: S3 handprints, readable, desperate, dense where the camera looks (final jobs 4.5)
Gary 8 Oct: Cameron watched the latest S3 video and could not make out the handprints. "They should look like handprints with perhaps some darker marks than we have now ... scrabbling and scratching desperate people, perhaps very, very many of them, scrabbling up ... no need for any of those ... decal actors in areas of the wall other than where my camera shot is ... concentrate probably twice as many of those marks in that area of the wall where the camera shot is."
Existing pipeline:
- Saved/CodexFlatV3/handprints/ (clamber/placement_S03_grease.json, 1034 placements) and the tools beside it; grep for how the grease decals were placed and applied.
- Gary liked the "pale greasy" look as a sheen, "not stain". He also chose tint "E: dried blood, core" for a held red variant (8 Oct, built, not implemented): find it.
- The camera shot is S3 Shot B06, a wall-following camera ~10 cm off the RIGHT wall at z 171-220 over Scene frames ~3000-3480 (24 fps). Its keys can be read offline from the .uasset if your tools allow; otherwise take the path as an arg with the numbers above.
Build:
1. A placement generator: ~2x density inside the B06 frustum band (args: band, density), ZERO outside it. Prints form desperate upward climbing trails: hand pairs reaching up, drag-smears and finger SCRATCH marks (long thin streaks under prints), clusters, overlaps, many sizes. Deterministic seed; note the memory trap that two random draws in one expression re-roll across builds.
2. A darker mark variant: a decal material-instance parameter set with darker cores and scratch streaks, keeping the sheen. Values are args; use Gary's dried-blood core as one option.
3. Preview PNGs: a wall elevation of the B06 band, old vs new.
4. An editor tool with DRY/APPLY/REVERT that replaces the S3 handprint decal actors: remove those outside the band and place the new set. The conductor runs it after Gary sees the previews.
Deliver Docs/Conductor/P12_HANDPRINTS_2026-10-08.md.
