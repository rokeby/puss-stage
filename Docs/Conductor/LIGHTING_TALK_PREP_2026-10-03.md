# Gary lighting talk prep — 3 October 2026

**measured execution scope:** offline, read-mostly briefing for today's talk.
No Unreal session was opened and no rendered judgement was made.

## How to read the evidence

- **declaration-proven** — stated by current project source or a cited project
  document.
- **measured** — written by a saved survey/read-back/record. This proves saved
  or inspected data, not the rendered look.
- **inferred** — arithmetic, interpretation, or a design recommendation from
  those declarations and measurements.
- **UNCLEAR** — the cited offline evidence cannot close the point.

**measured scope boundary:** the latest relevant records used below are the
29–30 September passage-light saves/read-backs. The 3 October conductor prompt
still names this lighting/per-wing-rig talk as today's work, but this document
does not claim a 3 October live Unreal read-back. Gary's rendered acceptance is
therefore still open. `Docs/Conductor/CONDUCTOR_START_PROMPT.md:166-167`;
`Docs/InfinityStageSessionHandover.md:8-14`

## 1. Today's Passage rig

### What the Show can store

- **declaration-proven:** a cue attachment can be a Light, can anchor to the
  fixed station or Left/Right/Top panel (or pair centre), and stores a relative
  transform. `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:135-168`;
  `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:426-464`
- **declaration-proven:** native attachment light kinds are Spot, Rect and Point;
  shadow flags, light functions, temperature, intensity and Light Drama are
  serialized in the Show. `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:161-168`;
  `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:190-240`;
  `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:302-362`
- **measured:** the current P01–P06 wing-pair rigs use **Spot and Rect only**;
  no Point attachment appears in the saved passage survey. All ordinary rows are
  station-anchored. `Saved/CodexStructure/passage_lighting_survey.json:11-1034`;
  `Saved/CodexStructure/passage_lighting_survey.json:1035-1440`;
  `Saved/CodexStructure/passage_lighting_survey.json:1441-2390`;
  `Saved/CodexStructure/passage_lighting_survey.json:2391-4528`

### The common nine-light bay

**Measured:** P01 and P04–P06 have the same nine enabled lights per wing pair:
seven Spots plus two Rects. The names describe the placement, not nine identical
front lights. `Saved/CodexStructure/passage_lighting_survey.json:12-477`;
`Saved/CodexStructure/passage_lighting_survey.json:758-897`;
`Saved/CodexStructure/passage_lighting_survey.json:2392-2993`;
`Saved/CodexStructure/passage_lighting_survey.json:3062-3663`;
`Saved/CodexStructure/passage_lighting_survey.json:3732-4333`

| Position in a pair | Current fixtures | Reading |
|---|---:|---|
| upper/central | 1 Spot: `Entry Top` | **measured:** high and near the corridor centre. `Saved/CodexStructure/passage_lighting_survey.json:412-477` |
| upper/side | 4 Spots: `Entry Fwd ±Y`, `Entry High ±Y` | **measured:** high or forward rakes from both sides. `Saved/CodexStructure/passage_lighting_survey.json:144-411` |
| lateral/cross | 2 Spots: `Cross ±Y` | **measured:** outboard cross-light from the two sides. `Saved/CodexStructure/passage_lighting_survey.json:12-143` |
| lower/side | 2 Rects: `Low ±Y` | **measured:** low, near-floor side light; shadowless in the saved survey. `Saved/CodexStructure/passage_lighting_survey.json:758-897` |

**Measured:** every passage also serializes one disabled `Top Down` Spot per
pair; P01 additionally has one disabled old Opening Light. These are not counted
as today's enabled rig. `Saved/CodexStructure/passage_lighting_survey.json:898-1034`;
`Saved/CodexStructure/passage_lighting_survey.json:1374-1440`;
`Saved/CodexStructure/passage_lighting_survey.json:2324-2390`;
`Saved/CodexStructure/passage_lighting_survey.json:2994-3060`;
`Saved/CodexStructure/passage_lighting_survey.json:3664-3730`;
`Saved/CodexStructure/passage_lighting_survey.json:4334-4400`

### Passage-by-passage census

**measured table scope:** counts below are enabled Show-attached lights and the
fixture rows are measured. **Inferred:** the final per-passage caster totals are
an explicitly marked arithmetic reconstruction. Five separate mouth-lantern
actors at P02–P06 are listed afterwards so that Show authority is not confused
with level-only extras.

| Tier | Passage | Wing pairs | Enabled rig per pair | Passage-specific additions | Enabled Show-attached lights | Current Show shadow casters | Blinking spot/gobo |
|---|---|---:|---|---|---:|---:|---|
| **measured; caster total inferred** | P01 | 48 | 9 = 7 Spot + 2 Rect | 96 serialized footlight/floats, 91 enabled; 2 house-warmer Spots | 525 | 99 | Wing 041 `Entry High -Y` is the praised blinking shadow Spot; it is one of the nine, not an extra lamp. |
| **measured; caster total inferred** | P02 | 23 | 5 = 3 Spot (`Cross ±Y`, `Entry Top`) + 2 low Rect | 1 added blinking Spot | 116 | 70 | Wing 019, +Y; explicit timber gobo. |
| **measured; caster total inferred** | P03 | 21 | 9 = 7 Spot + 2 Rect, all retained as shadowless fill | 53 upper Spots: 33 pools, 14 slashes, 6 back-lights; 1 added blinking Spot | 243 | 54 | Wing 017, −Y; explicit timber gobo. |
| **measured; caster total inferred** | P04 | 21 | 9 = 7 Spot + 2 Rect | 1 added blinking Spot | 190 | 43 | Wing 017, +Y; explicit timber gobo. |
| **measured; caster total inferred** | P05 | 93 | 9 = 7 Spot + 2 Rect | 2 added blinking Spots | 839 | 2 | Wings 008 and 007; two explicit timber gobos. |
| **measured; caster total inferred** | P06 | 55 | 9 = 7 Spot + 2 Rect | 1 added blinking Spot | 496 | 111 | Wing 044; explicit timber gobo. |

Evidence and tier for that table:

- **measured:** pair counts are P01 48, P02 23, P03 21, P04 21, P05 93,
  P06 55. `Saved/CodexStructure/passage_lighting_survey.json:2-9`
- **measured:** P01's warmer read-back found 579 serialized lights, 96 floats,
  the old Opening Light disabled, both house Spots enabled, and no dirty packages.
  The saved survey has 91 enabled floats; the later caster survey totals 525
  enabled P01 lights. `Saved/CodexStructure/verify_p01_warmer.json:2-53`;
  `Saved/CodexStructure/passage_lighting_survey.json:478-757`;
  `Saved/CodexStructure/p01_caster_survey.json:1-4`
- **measured:** P03's read-back found 210 old slots, 53 new rig Spots (15 L +
  18 R + 14 Slash + 6 Back), 242 enabled lights and 53 casters before the added
  blinking Spot. `Saved/CodexStructure/verify_p03_rig.json:1-22`;
  `Docs/RigAndAtmosphere_Handover_2026-09-28.md:29-37`
- **measured:** P04–P06 retained their 1,521 existing lamp attachments
  (169 pairs × 9), rewritten in place; their baseline caster plan was 152 total,
  split P04 42 / P05 0 / P06 110. `Saved/CodexStructure/p456_baseline_apply.py:1-11`;
  `Saved/CodexStructure/p456_baseline_plan.json:33677-33680`;
  `Docs/RigAndAtmosphere_Handover_2026-09-28.md:164-179`
- **measured:** six added light+timber-gobo pairs read back clean across P02–P06;
  P05 has two and each other passage has one. `Saved/CodexStructure/verify_blink_spots.json:2-146`;
  `Saved/CodexStructure/verify_blink_spots.json:147-293`
- **measured:** the explicit gobos are movable, visible, shadow-casting timber
  props inside shadow-casting Spot beams; their lens distances run 0.9–5.5 m.
  `Saved/CodexStructure/blink_gobo_in_beam.json:1-121`;
  `Docs/RigAndAtmosphere_Handover_2026-09-28.md:207-226`
- **measured:** P01's shadow pass retained only `Entry Top` and `Entry Fwd +Y`
  per pair, plus the Wing 041 blink Spot and two house Spots: 338 → 99 P01
  casters and 618 → 379 Show-wide. `Saved/CodexStructure/p01_shadow_pass_apply.py:1-18`;
  `Docs/InfinityStageSessionHandover.md:484-494`
- **inferred:** the per-passage caster column after all recorded changes is
  P01 99; P02 69 standard + 1 gobo = 70; P03 53 upper-rig + 1 gobo = 54;
  P04 42 + 1 = 43; P05 0 + 2 = 2; P06 110 + 1 = 111. The arithmetic sums to
  the measured current total of 379. `Saved/CodexStructure/p01_shadow_pass_apply.py:4-11`;
  `Saved/CodexStructure/verify_p03_rig.json:1-19`;
  `Docs/RigAndAtmosphere_Handover_2026-09-28.md:170-173`;
  `Saved/CodexStructure/verify_blink_spots.json:2-290`
- **inferred:** enabled Show-attached light arithmetic is 525 + 116 + 243 +
  190 + 839 + 496 = **2,409**. This is a reconstruction from the saved records,
  not a fresh census. The older project headline's “~2,500 attachments” was
  approximate. `README.md:80-85`; evidence listed immediately above.

### Mouth and opening lights outside the repeating bay

- **measured:** P01 has two warm (2,800 K), shadow-casting house Spots at the
  mouth and the old Opening Light is disabled. `Saved/CodexStructure/p01_warmer_plan.json:8-69`;
  `Saved/CodexStructure/verify_p01_warmer.json:2-45`
- **measured:** P02–P06 each have one separate low, house-left mouth Spot,
  210 cd / 2,800 K / shadowed. These five are level actors, not part of the
  Show-attachment table above. `Saved/CodexStructure/mouth_lanterns_record.json:1-28`;
  `Saved/CodexStructure/mouth_lanterns_apply.py:37-47`;
  `Saved/CodexStructure/mouth_lanterns_apply.py:147-165`;
  `Docs/RigAndAtmosphere_Handover_2026-09-28.md:493-497`

### The reason to change the shadow strategy

- **measured:** the recording-era hard coloured rectangles were diagnosed as
  VSM one-pass projection overflow; the log contained
  `[VSM] One Pass Projection max lights overflow`. At that checkpoint about
  1,700 local lights cast shadows show-wide. `Docs/RigAndAtmosphere_Handover_2026-09-28.md:60-70`
- **measured:** a later pass attributed repeated render spikes to 338 P01
  casters; the subsequent saved pass reduced the Show attachment total to 379.
  `Docs/RigAndAtmosphere_Handover_2026-09-28.md:243-250`;
  `Docs/InfinityStageSessionHandover.md:491-493`
- **inferred:** 379 is much safer than 1,700 but it is not permission to let
  every lamp in a new physical rig cast a dynamic shadow. The proposal below
  separates visible fixture count from concurrent caster count.

## 2. Gary's outer-wall / lighting-tree proposal

### The proposal in one sentence

**declaration-proven:** Gary proposes two upper lights per wing plus two lower
lights per wing from side trees; the trees become part of a chain-link, holey-
tarp and barbed-wire outer wall that blocks the exterior except for selected
beams. `Docs/Conductor/RUNTHROUGH_NOTES_2026-10-03.md:12-25`;
`Docs/Conductor/RUNTHROUGH_NOTES_2026-10-03.md:36-42`

**inferred interpretation for counting:** “per wing” is literal: a wing pair
has two wings, so the standard physical bay is 4 upper + 4 lower = **8 fixtures
per pair**. Confirm this reading with Gary before implementation.

### One wing bay — sketch

```text
PLAN (camera travels ->; one left/right wing pair at a station)

 OUTER WALL / TREE L                         OUTER WALL / TREE R
 barbed + chain-link + tarp                 tarp + chain-link + barbed
        [L2][L1]                                      [L1][L2]
            \       LEFT WING | route | RIGHT WING       /
             \        U1  U2  |  ->   |  U2  U1         /
              +-------- selected pools / odd beam -------+

 ELEVATION (one side)

        barbed-wire coil
   ~~~~~~~~~~~~~~~~~~~~~~~~~  12 m wall
   | chain-link / HOLE / tarp|    U1 U2 = two upper wing lamps
   |          [U1] [U2]      |    L1 L2 = two lower tree lamps
   |                         |
   | post sockets [L2]       | <- high lower/tree lamp
   |              [L1]       | <- low lower/tree lamp
   |____4 m shared-post bay__|
           wing card   floor
```

**inferred:** the sketch places the wall continuously outboard of the widest
wing, puts the lower pair on fixed-height post sockets, and treats tarp holes as
authored beam windows rather than random damage. This combines Gary's proposal
with W&T's module path. `Docs/LegibleMachineSpec_2026-09-29.md:89-103`;
`Docs/Conductor/OUTER_WALL_FENCE_FITNESS_2026-10-03.md:25-36`

### Fixture count if the eight-light reading is approved

| Tier | Passage | Pairs | 8-fixture bays | Draft simultaneous ordinary casters: one on every other bay |
|---|---|---:|---:|---:|
| **inferred** | P01 | 48 | 384 | 24 |
| **inferred** | P02 | 23 | 184 | 12 |
| **inferred** | P03 | 21 | 168 | 11 |
| **inferred** | P04 | 21 | 168 | 11 |
| **inferred** | P05 | 93 | 744 | 47 |
| **inferred** | P06 | 55 | 440 | 28 |
| **inferred** | **Total** | **261** | **2,088** | **133** |

- **inferred:** the fixture arithmetic is pair count × 8. The pair counts are
  measured in `Saved/CodexStructure/passage_lighting_survey.json:2-9`.
- **inferred:** designate the seven existing blinking looks from the standard
  upper Spots where possible, rather than adding seven more fixtures. Five mouth
  lanterns remain separate cue-transition lights. This makes the physical total
  2,088 bay fixtures + 5 mouth lights, versus the reconstructed 2,409 Show-
  attached lights + 5 mouth lights today. `Saved/CodexStructure/verify_blink_spots.json:2-290`;
  `Saved/CodexStructure/mouth_lanterns_record.json:1-28`

### Shadow-caster budget

- **inferred recommendation:** all four lower tree fixtures are shadowless fill
  by default. Of the four upper fixtures, only one selected key casts in a lit
  bay; activate a caster on no more than every other bay at one time. That is
  **133 ordinary casters**. Allow seven special gobo casters as a conservative
  separate reserve: **140 Show-attached casters maximum**, or **145** while all
  five mouth lanterns are active.
- **inferred comparison:** 140 versus today's measured 379 Show-attached casters
  is 239 fewer, a **63% reduction**. Even the fallback worst case of one ordinary
  caster on every bay plus seven gobos is 268, still 111 / **29% below** today.
  Today's 379 is measured at `Docs/InfinityStageSessionHandover.md:491-493`.
- **inferred operating rule:** caster budget is concurrent, not installed. A
  physical fixture may exist in every bay while its light is off or shadowless;
  this is how the wall can look like a complete rig without recreating the VSM
  overload. The built Light Drama system already switches unstruck lamps fully
  off, avoiding shadow cost away from the camera.
  `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageLightDrama.h:20-32`

### Why it solves both lateral-rig and exterior-leak problems

- **declaration-proven:** today's side masking does not exist; the earlier side-
  frame proposal was specifically meant to stop the camera seeing dusky void
  beyond the wings and to give the grid something to rest on.
  `Docs/LegibleMachineSpec_2026-09-29.md:89-103`
- **inferred:** continuous shared posts become the missing lateral structure and
  a believable mounting surface for the lower lamps; the lights no longer float
  beside unrelated wing cards.
- **inferred:** continuous tarp/chain-link masks the broad exterior, while a few
  deliberately aligned tarp holes make the “odd beam” controlled and repeatable.
  `Docs/Conductor/OUTER_WALL_FENCE_FITNESS_2026-10-03.md:25-36`
- **UNCLEAR:** Gary called the visible problem “landscape peeping out”, but the
  current handover says all Landscape actors were deleted and verified absent on
  30 September. Treat the talk problem as **side/exterior leakage**, not proof
  that a Landscape actor is currently present. The wall solves either visual
  case. `Docs/Conductor/RUNTHROUGH_NOTES_2026-10-03.md:19-25`;
  `Docs/InfinityStageSessionHandover.md:72-84`

### Asset fitness and acceptance gates

- **measured:** the current fence wing is 8.5 m × 12 m plus a 1 m pole and costs
  29,646 triangles at LOD0 / 2,558 at LOD1.
  `Docs/Conductor/OUTER_WALL_FENCE_FITNESS_2026-10-03.md:9-16`
- **declaration-proven:** it is a one-off wing with end poles, not a wall module;
  it has no lamp sockets and cannot butt without doubled posts.
  `Docs/Conductor/OUTER_WALL_FENCE_FITNESS_2026-10-03.md:18-26`
- **declaration-proven proposal:** W&T's build path is a **4 m × 12 m shared-post
  bay**, masked-texture chain-link, separate authored-hole tarp, top-only barbed
  wire, lamp sockets and open/tarp/torn/door variants.
  `Docs/Conductor/OUTER_WALL_FENCE_FITNESS_2026-10-03.md:28-37`
- **inferred safety/layout gate:** place the wall outside each passage's widest
  wing envelope before adding sockets; P02 must be measured route-relative.
  `Docs/LegibleMachineSpec_2026-09-29.md:97-100`
- **UNCLEAR:** the fence has not been reviewed in Unreal under show lighting;
  shimmer/moiré and wall-scale cost are inferred, not profiled. Do the hatching
  probe and one rendered 4 m bay before committing to all six passages.
  `Docs/Conductor/OUTER_WALL_FENCE_FITNESS_2026-10-03.md:20-24`;
  `Docs/Conductor/OUTER_WALL_FENCE_FITNESS_2026-10-03.md:38-44`

## 3. P01 “office hallway” ping-on

### What the cue needs

- **declaration-proven:** Gary wants the Opening/P01 walk-in dark, followed by
  lights pinging on in sequence down P01 only, like an office hallway.
  `Docs/Conductor/RUNTHROUGH_NOTES_2026-10-03.md:12-18`;
  `Docs/Conductor/RUNTHROUGH_NOTES_2026-10-03.md:36-38`
- **measured:** the Opening sequence is 15 s; its curtain lands at 6.33 s. P01
  starts at Master 15.0 s, from (0,0,150), at 25 mm and initially 2.5 m/s.
  `Saved/CodexConductor/opening_walkin_probe.json:2-18`;
  `Saved/CodexConductor/opening_walkin_probe.json:63-102`;
  `Saved/CodexConductor/opening_walkin_probe.json:118-133`
- **measured:** P01's nominal pair spacing is 600 cm. At the measured entry speed,
  the initial camera-spatial one-bay cadence is about 2.4 s. The saved P01
  Passage section has no keyed camera channels; its keys are Wing modulation,
  so this evidence supplies no music-beat-to-bay mapping. A literal musical beat
  and a route-distance strike must be reconciled deliberately.
  `Saved/CodexStructure/p456_baseline_plan.json:1-4`;
  `Saved/CodexConductor/p01_score_shift_report.json:2-72`

### Tools that actually exist

- **declaration-proven:** built Light Drama already provides per-attachment
  strike-on-approach, strike distance/ramp, ignition stutter, dark-before-strike,
  Hold/Decay/Extinguish, and deterministic camera-route evaluation. This is the
  safest existing tool for a spatial hallway cascade.
  `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageLightDrama.h:20-76`;
  `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageLightDrama.h:115-149`
- **measured:** ordinary Sequencer `Intensity` float tracks and keys exist and are
  already used in the HangarRise sequences. `Saved/CodexConductor/hangar_light_keys_probe.py:99-143`;
  `Saved/CodexConductor/hangar_light_keys_probe.json:542-609`
- **declaration-proven:** the Master is an artist-visible persistent container;
  rebuild owns only its managed tracks, so artist tracks can carry a keyed P01
  lighting score. `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageShowAsset.h:54-59`
- **declaration-proven correction:** the managed Passage section currently has
  camera and three Wing-modulation channels, **not a lighting channel**. The
  checklist still marks music-driven Passage light channels as unbuilt.
  `Plugins/InfinityStage/Source/InfinityStage/Public/MovieSceneInfinityPassageTrack.h:13-43`;
  `Plugins/InfinityStage/Source/InfinityStage/Public/MovieSceneInfinityPassageTrack.h:112-175`;
  `Docs/ShowBuildTodo.md:93-98`
- **declaration-proven risk:** materializing a passage destroys and respawns its
  managed attachment actors. Raw Sequencer bindings to those actors can therefore
  become stale after a re-materialize; Light Drama stored on the Show attachment
  survives because attachment GUIDs remain authoritative.
  `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:859-918`;
  `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:935-1009`

### Draft timing to discuss

**inferred draft — prefer Light Drama for the first trial:** keep all nine P01
bay lights dark through the Opening. At Master 15.0 s, ping the first bay; then
strike each following bay one station ahead of the camera. At the initial speed
this is roughly one bay every 2.4 s. Give each ping a 0.15–0.25 s hard rise,
hold the two upper key Spots, bring low Rects up one beat later at 30–50%, and
let non-key fill extinguish one to two bays behind. The 91 footlight/floats stay
off for the first four bays, then enter sparsely so the reveal grows rather than
switching the whole corridor on. Basis: the measured start/spacing above and the
built Hold/Decay/Extinguish controls at
`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageLightDrama.h:41-76`.

**inferred musical alternative:** if “one bay per beat” is literal music timing,
author artist-owned Intensity tracks in the Master, using the P01 section's
absolute Master range (15.0–111.336 s) as the clip boundary. Do not call this a
Passage-light channel; that system is not built. Prototype eight bays first and
verify that a Master rebuild and a passage re-materialize do not break bindings.
`Saved/CodexConductor/p01_score_shift_report.json:271-279`;
`Docs/ShowBuildTodo.md:93-98`

## 4. “Lighting not so constant” — concrete passage options

These are talk options, not authored states. Every item below is **inferred**
from Gary's passage card and should be selected, cut or combined by Gary.

### P01 — warm first fairytale entry

Mood authority: **declaration-proven** — warm, mysterious, not too dark/cold;
foliage alternates with classical architecture; warm golden low contrast.
`Docs/FlatV3PassageCards_2026-09-30.md:37-46`

1. **inferred:** make the office-hallway ping the structural spine: upper key
   Spots strike bay by bay; organic bays receive softer, later low Rect fill.
2. **inferred:** alternate 70/40/55% intensity rather than equal output so the
   first fairytale corridor has breathing warm pools, not a uniform wash.
3. **inferred:** let a few 2,500 K footlight/floats arrive after bay four as
   practical “candles”, with the rest remaining dark.
4. **inferred:** retain the Wing 041 cool blinking shadow as one late uncanny
   interruption, not a repeated effect.

### P02 — magic-realist anthropocene forest

Mood authority: **declaration-proven** — lurid plants against fence/industrial
sets; darker deep green, oxblood, rust and oily sheen, with mystical fragments
near the shrine. `Docs/FlatV3PassageCards_2026-09-30.md:48-80`

1. **inferred:** green partial pools on plant bays; keep alternate fence bays
   mostly silhouette so the industrial structure arrives by absence.
2. **inferred:** use oxblood/rust side light only on thorn/piping bays, at lower
   intensity than the green, so colour marks families instead of tinting all.
3. **inferred:** align one or two cold shafts with authored tarp holes; all other
   wall holes remain unlit.
4. **inferred:** use rare dirty fluorescent buzz on tree/practical lamps, then a
   steadier pale mystical pool for the last shrine-facing bays.

### P03 — bright Protestant folk horror

Mood authority: **declaration-proven** — cool, architectural, sinister stiff
bright rural light; hard bright cool whites/straw/pale sky, with stones, pyres
and holes where light peeps through. `Docs/FlatV3PassageCards_2026-09-30.md:82-116`

1. **inferred:** keep the 33 upper pools hard and cool, but light only selected
   rectilinear planes; leave intervening bays blank-white or dark.
2. **inferred:** make the 14 slashes pass through holes/wattle as narrow, rigid
   geometry rather than a continuous convent wash.
3. **inferred:** reserve warm flicker for pyre bays and step its intensity/size
   upward along the run; do not warm the architectural base.
4. **inferred:** let the six back-lights silhouette stones and people at widely
   spaced beats, preserving the stiff Wicker-Man brightness between them.

### P04 — ruined church-school

Mood authority: **declaration-proven** — very cool English light; heavy ruined
church architecture, with windows and breakages as the light's way in; leaden
grey, cold daylight and black lead. `Docs/FlatV3PassageCards_2026-09-30.md:118-134`

1. **inferred:** cold window shafts occur only at broken arches; intact piers
   stay heavy and underlit.
2. **inferred:** alternate high tracery light with low rubble pools so attention
   moves vertically rather than every nine-light bay reading the same.
3. **inferred:** add a few dim school-practical pools, slightly green/cold, among
   the church daylight; keep them shadowless.
4. **inferred:** allow one or two complete dark bays before a hard breakage beam,
   making the ruin reveal by cuts rather than a graded fade.

### P05 — sugary mountain whimsy

Mood authority: **declaration-proven** — whimsical and sugary, good clouds,
scaffolding/bamboo supports, playful lightning and a sugared pastel/cream/blue
palette. `Docs/FlatV3PassageCards_2026-09-30.md:136-152`

1. **inferred:** bright soft cloud pools at unequal levels (60/85/45%), with
   clean shadowless fill so the passage stays lovely rather than ominous.
2. **inferred:** small warm practicals on bamboo/scaffold supports make the
   physical support rhythm visible without filling the sky.
3. **inferred:** let flat zigzag lightning trigger a brief cool pulse in only the
   adjacent bay; no show-wide flash.
4. **inferred:** keep the two existing gobo effects as playful soft interruptions
   (one warm, one cool), while darker clouds remain locally underexposed.

### P06 — the stage fiction deteriorates

Mood authority: **declaration-proven** — grand/extravagant becomes scaffold,
netting, peel, fire, monochrome and finally darkness; the scaffold reference is
a lit bay grid with one lamp per bay. `Docs/FlatV3PassageCards_2026-09-30.md:154-168`;
`Docs/FlatV3PassageCards_2026-09-30.md:169-203`

1. **inferred:** begin with warm extravagant upper keys, then remove one circuit
   at each stepped stage so the familiar rig visibly fails rather than merely dims.
2. **inferred:** switch to one practical per scaffold bay, alternating left/right
   and intensity, with black netting swallowing the unlit half.
3. **inferred:** introduce rare cold/green flicker and the hard-core P06 gobo as
   the construction site takes over; keep other fills shadowless.
4. **inferred:** step colour toward monochrome/infrared, then extinguish all bay
   lamps before the smoking/burning curtain and Void; practical fire is the last
   colour source.

## Decisions to get from Gary in the room

1. **inferred question:** confirm whether “two upper + two lower per wing” really
   means eight fixtures per pair, or four per pair. Basis: Gary's wording at
   `Docs/Conductor/RUNTHROUGH_NOTES_2026-10-03.md:19-23`.
2. **inferred question:** approve the shadow rule: at most one ordinary caster
   on every other bay concurrently, with seven named gobo exceptions.
3. **inferred question:** for P01, choose spatial strike-on-approach (robust to
   retiming) or literal musical beats on Master artist tracks.
4. **inferred question:** choose which wall bays are open/tarp/torn/door and mark
   every beam window; no random holes.
5. **inferred question:** approve one rendered 4 m wall/tree bay as the gate
   before six-passage placement, because current fence render fitness is UNCLEAR.
