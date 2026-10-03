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

## Gary, second message (verbatim)
> In the video, opening to p01 played well as to current designs, rig opened, but after 20s or so camera cuts to looking up at
> rig ceiling, before cutting to next curtain, so we don't currently have an effective exit curtain cut for the shadow cat bot
> interaction or a clean passage to next passage.
> Then second wing set plays for barely 10s between walk start and cutting out, to the rig open shot but there's only a pit and
> maybe the camera moves in right but it's evidentalt out of sync with any rig rising up
> Same p03 cuts from wings early, goes to rising rig and show though there's much to tune with the sequence. Also the figures
> need a beach to stand on, so perhaps megascan rocks that're already in content and some plants and actually lets make the
> side walls marble like the plinth before the bloody hand stains.
> P04 cuts to rig transition curtain early (it's the only one that shows up). Rig shows up we cut to next passage curtain no
> exit curtain, again. That exit curtain doorway might just need building at the back of the rig hangar? P05 jumps most of the
> wing passage and the screen blacks out as we approach the rig pit. Next thing we know we're in passage 6, which moves to end
> of passage and there's some movement happening but it's not quite the rig more like a black out that comes and goes but i
> guess that's just s06 being built

## Triage (conductor)
- RECORDING ARTEFACT (not the show): each window started 15 s before a passage's end and jumped from Scene +30 s to the Scene's
  last 5 s, so passages look cut short and Scenes jump to their ends. Passages are full length (P02-P04 3:00).
- 10 SCENE EXITS: no exit curtain / clean handover from a Scene to its Interaction (S1: a cut to looking up at the rig ceiling,
  then the next curtain; S4 the same). Gary's idea: an exit-curtain DOORWAY built at the back of each rig hangar. Design item
  for tomorrow (structure + camera + soft goods): which hangars, the door, the camera's exit move.
- 11 S2 (and S5) don't rise: confirmed again; read-only probe running (NotNested). S5's black-out approaching the pit fits.
- 12 S3: a BEACH for the figures (Megascans rocks already in Content + some plants) and the S3 side walls MARBLE like the
  plinth (before the hand stains). Draft placement for Gary to adjust (like the shot-list draft).
- 13 S6: blackouts coming and going = S6's new dim-instead-of-strike + being built (as expected).

## Later 3 Oct (Gary; some via Wings and Textures, marked)
- Lighting looks (P04 prototype video): "moody should have more partial lighting ... variation in what is visible and how
  visible as we move gives some mystery while blackness gets dissolved into muddiness"; "5-6 are nice but could be less warm
  or more varied between warm and cool, could also bring in more colour spaces" -> tune 1 (specs/LIGHTING_LOOKS_P04_TUNE1.md).
- "occasional detail on the type of reflection you get of light on slightly glossy paper" -> W&T (Billboard master, add nodes only).
- "practicals was a nice idea" -> tune 2.
- White feathered edge on some wings under dark light -> edge contact sheets (DerivedAssets/FlatV3/Review_2026-10-03/edges/).
- Via W&T: P05 "lighting doesn't need to be so warm in this passage as the cloud colours are strong"; "might look at bringing
  in more on-the-ground objects" in P05 (future); P05 clouds lower/more spread, no flat bottoms, sources too low-res (W&T).
