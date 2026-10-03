# Run-through notes, 3 Oct (Gary, on the PIE transitions recording 20261003_042428; verbatim, then triage)

## Gary, verbatim
> Indeed not seeing rig rise in s2 5 or 6.
> There's a popup that freezes every 2s but i guess that must be the screenshots.
> First main issue is there's a weird hatching visual on many of the wings that otherwise look not bad.
> Wings need to touch the ground if they are physical objects, currently some float awkwardly. Cloud wings are at ok height
> but poles don't reach ground.
> The chainlink fence and fence with tarp would work better if they weren't fully rectangular, ie if it's an asset then angle
> it inwards towards distance on inner side.
> The steps and stones are both a bit too large, especiallly the steps
> Then the next major mood building thing is to have lighting not so constant. We may need to introduce more spots for more
> partial and varied lighting.
> P01 needs a slower build, the opening should move in with the lights dark and for that passage only, they ping on in
> sequence like lights down an office hallway.
> We can talk through how lights are placed and the mood for each sequence of wings tomorrow, but the idea is for the walk to
> feel like we are moving through some spaces even though the wings are regular patterns, so it's a bit up to the lights to
> create mood and attention
> Can't remember what standard lighting rig is now but seems to make sense for there to be two upper lights for each wing and
> two lower lights perhaps coming from vertical lighting trees on either side. Would this perhaps come to resolving the desire
> for a lateral rig also, or something that blocks out the full landscape peeping out the sides. Perhaps this is actually
> where the chainlink fence with bits of holey tarp can come in useful? Is that asset good enough to develop as the main outer
> wall material? With barbed wire over the top? So it can serve as a kind of lighting rig side trees for all the wing passages
> while mostly blocking all the external light except perhaps the odd beam, and give the glimpses of the passages' outer walls
> a sinister trapped feel despite colourful insides

## Triage (conductor; owners and status)
| # | Item | Owner | Now |
|---|---|---|---|
| 1 | S2/S5/S6 hangars don't rise (confirmed by Gary; lengthening to 25 s didn't fix it) | Conductor | read-only probe of why "NotNested" tonight |
| 2 | 2 s freeze = the per-2 s `shot` screenshots (inferred: each forces a render) | Conductor | next recording: video only, or async shots |
| 3 | Hatching on many wings | Wing materiality / W&T | read-only probe tonight: material features (halftone/sheet-grid hash on UV1, masked/dither edges) vs mips |
| 4 | Wings must touch the ground; P05 cloud poles don't reach the floor after the float | W&T | asset/placement fix |
| 5 | Chain-link + tarp fence: taper the inner side toward the distance (not rectangular) | W&T | asset fix |
| 6 | Steps and stones too large, especially steps | W&T | rescale |
| 7 | Lighting less constant: more spots, partial and varied | Gary + conductor, TOMORROW | discussion |
| 8 | P01: slower build; dark opening; lights ping on in sequence like an office hallway (P01 only) | TOMORROW (spec ready for the talk) | |
| 9 | Standard rig proposal: 2 upper lights per wing + 2 lower from vertical lighting trees each side; chain-link + holey tarp + barbed wire as the main OUTER WALL, carrying the side trees, blocking the landscape except odd beams | TOMORROW | conductor prepares: today's rig facts + fence asset fitness |
Current rig (declaration-proven, docs): P01's tuned per-wing rig was copied to P04-P06 on 29 Sep ("1521 lamps rewritten in
place", shadow casters 1643 -> 612; RigAndAtmosphere_Handover_2026-09-28.md:170-173) plus six blinking gobo spots across
P02-P06 (InfinityStageSessionHandover.md:136). A related earlier proposal with "side frame, floating lamps":
Docs/LegibleMachineSpec_2026-09-29.md.
