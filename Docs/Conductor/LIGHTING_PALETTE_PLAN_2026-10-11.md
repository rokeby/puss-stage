# Lighting direction and PC implementation handoff

Prepared for Gary and the main project-PC agent. This document combines the 19-segment palette reference with the directed changes, a procedure for capturing Gary's physical examples, and the implementation/acceptance steps. Use live fixture identities and values; no cloud-side lighting scripts or asset changes have been made.

## Read first — current implementation scope

**User-directed workflow:** Gary will intervene on the PC to set representative physical transforms and some lighting states, showing what to replicate and vary. The agent captures those examples and implements the intensity, colour and other lighting-state directions below around them. Do not overwrite a demonstrated transform with an old preset or silently substitute a different example.

| Work | Current instruction | Scope |
|---|---|---|
| Opening + P01 | Softer, brighter cool rose/grey-blue; more upper light down onto the ground; wing uplighting; fewer low forward-diagonal beams; magical traditional-theatre entry. | Directed. Match Opening uplights to P01. |
| P02 | Same arrangement, cooler lavender/light blue, a little dimmer than revised P01. | Directed. Preserve the existing driveby light. |
| P03 | Same softened arrangement, light green/pale yellow/orange, sickly tone. | Directed. Preserve its intentional special effects. No comparative brightness ratio specified. |
| P05 | Preserve the successful overall look; remove the domestic half-moon fence practicals. | Directed cleanup. Its curtain falls into a **very bright space ready for a white-out transition**. |
| End-curtain legibility spots | Soft spotlight on each upright Passage-end curtain. | **P01–P05 only. P06 has no curtain and gets no curtain spot.** |
| Smoke machines | Remove any remaining Passage smoke machines and their emitted smoke; verify prior removals remain effective. | Identified machine effects, separate from fog, shafts and intentional fire/candle effects. |
| P06 | Leave its current look and curtain-free ending alone. | No new end-curtain fixture or general relight from the palette reference. |
| Other Scenes/Interactions/P04 | Palette/tone reference below. | Still proposals. Do not interpret the table as a command to recolour every sequence. Shared approved cleanup/curtain requirements still apply where specified. |

**User-directed tuning authority:** the agent has the colour and intensity directions, not a preselected set of RGB/Kelvin/candela numbers. Choose and adjust numerical candidates on the PC from the measured current state and the demonstrated look; compare the visual result and record the resulting values. Missing preset numbers do not require stopping before a first controlled tuning pass. Ask Gary when the identity, physical example, intended state or mechanism is unclear; do not invent a new system to bridge that uncertainty.

## Evidence and status

- **Declaration-proven:** the saved show snapshot lists the 19 segments in the order used below (`Tools/MusicAnalysis/p11_timing_snapshot.json:15`). Its own evidence block says it is an offline saved read-back, not a fresh Unreal census (`:3`). Use its order and names here; do not copy its absolute timing into lighting keys.
- **Document-stated:** Klara's lighting email of 10 October, supplied by Gary on 11 October, asks for muted colours, readable wings/floor, warm/grey P01, cold whites/lavender/pale blue P02, grey/faint off-green P03, cold Shore lighting, a coherent warm-or-cold choice for P04, and preservation of the qualities she likes in P05/P06. It proposes mild golden/grey, silver/blue, olive/grey and rose/cold-white combinations. It also asks for theatrical black around P01–P04 and continuity from the Opening into P01.
- **User-directed:** Gary describes current P01 as very dark golden amber with occasional red and chooses a brighter, more muted, cooler rose/grey-blue direction, with upper parcans aimed down at the ground, wing uplighting, and fewer lower forward-diagonal beams. The Opening uplights should share that direction. This supersedes the first draft's grey-gold P01/Opening palette. The current-look description is user-reported, not an independent cloud measurement.
- **User-directed:** P02 follows the same softening and ground/wing lighting approach as P01, with cooler lavenders and light blues at a slightly dimmer overall level. Gary explicitly retains the driveby light for its hint of exteriority.
- **User-directed:** P03 follows the same softened ground/wing lighting approach, with light greens, pale yellow and orange forming a sickly set of hues. This supersedes the first draft's grey/olive P03 palette. No separate P03 brightness level is specified.
- **User-directed, clarified:** P01–P05 should have a soft spotlight aimed at their end curtain, making its imagery more legible. Leave P06 alone: it has no curtain. P05's curtain falls to reveal a very bright space ready for a white-out transition.
- **User-directed:** P05 is pretty good overall. Preserve its existing look, but remove the half-moon-shaped, domestic-looking practicals lining the fence if they are still present; Gary says these were intended to have been removed earlier.
- **Inferred proposal:** the other palettes and emotional descriptions below remain design recommendations for review. None is a measured production colour or an approved numerical preset. The approved P01/Opening/P02/P03 directions do not identify fixture bindings or establish live implementation.

## Shared colour language

**Inferred proposal:** the show should feel like painted theatre seen under light: colour in the wings, floor, cloth, skin and objects remains legible. Light supports those colours instead of replacing them with a red, green or blue blanket.

**Inferred proposal:** each segment has one dominant neutral family and one restrained accent. The visibility light stays close to warm, neutral or cold white; the mood colour occupies selected areas. A shift in tone does not require every lamp to change colour.

**Inferred proposal:** use colour words as visual targets at this stage:

- **Old gold:** pale, greyed straw/honey; not orange or saturated amber.
- **Silver:** cool white/pearl/pewter; not dark blue.
- **Olive:** grey with a faint earthy green; not acid green.
- **Rose:** grey with a restrained rose tint; it can be warm or cool. P01 and the Opening use the **cool** version, not pink, magenta or red.
- **Grey-blue:** a pale, desaturated blue carried by grey/pearl; it provides cool contrast without a dark-blue wash.
- **Parchment:** neutral-to-warm ivory, suitable for legible black shadow play; not yellow illumination covering the whole frame.

**Document-stated constraint:** Klara praises the coherent state of the last Passage and the houselight character of P05. These are references to preserve during tuning, rather than invitations to impose new colour effects everywhere.

## Palette in show order

The Scene subtitles are descriptive names from the project notes; their saved cue labels remain `Scene N - External Sound`. Interaction 5 retains the saved cue name `Becomes King`, even though the rehearsal notes describe boots being put on. This plan does not rename any cue.

| # | Segment | Dominant family | Restrained accent / contrast | Intended tone and hierarchy | Evidence tier |
|---|---|---|---|---|---|
| 1 | **Opening — Curtain** | Soft ivory/pearl and muted cool rose-grey | Pale grey-blue, continuous with P01 | A magical, traditional theatre invitation. Opening uplights introduce the same softened, brighter colour world that we enter in P01. | user-directed colour/continuity; descriptive palette remains qualitative |
| 2 | **P01** | Muted cool rose-grey and soft near-white | Pale grey-blue | Magical, welcoming and materially readable. Brighter overall than the reported dark amber/red state: downward upper-rig light reveals the ground, uplights reveal the wings, and fewer low forward-diagonal lights fill the view with thick beams. | user-directed |
| 3 | **S1 — Animals** | Natural ivory and pale straw-white | Soft warm-grey shadows | Living, tactile and intimate. Animal colours and surfaces carry the scene; illumination feels gentle rather than gilded or strongly gelled. | inferred proposal |
| 4 | **I1 — Washing the Boy** | Parchment and chalk-white | A faint warm-grey surround | Plain, intimate storytelling. The boy's dark silhouette is the central contrast; supporting colour does not compete with it. | inferred proposal |
| 5 | **P02** | Muted cool lavender and silver-white | Light blue; retain the existing driveby light | The same softened, readable theatre space as P01, a little dimmer and cooler. Ground-facing upper lights and wing uplights carry the base state; the driveby provides a fleeting hint of exteriority. | user-directed |
| 6 | **S2 — Shrine** | Ash-white and mineral grey-green | Local candle/fire warmth where it already belongs | Still, ritual and material. Cool surroundings make any actual flame warmth meaningful; the shrine's authored colours remain readable. | inferred proposal |
| 7 | **I2 — Turnips** | Warm parchment and flax-grey | A faint earthy sage-grey outside the shadow image | A dry, earthy fairy tale. Keep the shadow surface clear and neutral enough for the action; any green is a minor contextual accent. | inferred proposal |
| 8 | **P03** | Light green and pale yellow | Softened orange, with near-white visibility as needed | Sickly and uneasy, while the stage remains softly lit and materially readable. The same downward ground lighting, wing uplighting and reduced low diagonal beams distinguish coloured surfaces from a thick coloured veil. | user-directed hues, tone and lighting approach; hierarchy is a qualitative proposal |
| 9 | **S3 — Shore people** | Pearl-grey, cold white and grey-blue | Restrained existing cool/neon character; pearl/fire highlights remain local | Exposed, uncanny and mournful. Water, marble, waves and faces have material detail. The scene's attention can gather on the pearl without recolouring everything. | inferred proposal |
| 10 | **I3 — Forgets His Name** | Ash-parchment and pewter-white | A trace of lavender-grey | Quiet estrangement and uncertainty. Desaturation does the emotional work; shadow detail remains clear. | inferred proposal |
| 11 | **P04** | Clean cool white and platinum-grey | Pearl-white variation, with very little coloured tint | Clear, bright and dazzling through texture, direction and contrast. Choose a coherent cool register here; avoid pink and dark-blue washes. | inferred proposal |
| 12 | **S4 — Children** | Daylight ivory and pale warm grey | A little rose-grey, with cool-white clarity retained | Poised, luminous and slightly unsettling. Warmer human detail sits inside a clear scene; no cheerful pink wash. | inferred proposal |
| 13 | **I4 — Gets a Name** | Pearl-parchment and soft rose-grey | Neutral-white clarity on the shadow surface | Recognition and a little returning warmth. Different from I3's ash tone, while retaining the same legible shadow-play language. | inferred proposal |
| 14 | **P05** | Retain the current successful palette | Remove the half-moon-shaped domestic fence practicals | Pretty good overall: preserve its passage look. At its curtain fall, retain the very bright revealed space ready for the white-out transition. | user-directed preservation/removal/reveal; palette values unmeasured |
| 15 | **S5 — Village / video scene** | Weathered ivory and pale stone | Muted honey/gold if compatible with the actual scene image | A familiar, inhabited world. This is a palette target for the handover; the authored video remains the colour reference rather than footage to automatically tint or grade. | inferred proposal |
| 16 | **I5 — Becomes King** | Ivory and pale old gold | Pewter-grey restraint | Modest fairy-tale ceremony, not a saturated royal-gold finale. The boy's final shadow action remains the focus. | inferred proposal |
| 17 | **P06** | Retain the current look | Preserve its intentional effects | Leave P06 alone in this pass. No end curtain or curtain spotlight. The earlier smoked-gold description is a palette reference, not a relighting command. | user-directed preservation; actual values unmeasured |
| 18 | **S6 — Void** | Black | Isolated candle-gold and faint neutral/pewter readability | Absence, proximity and concentration. Candle/woman/swarm are isolated presences; black has priority over a general blue or purple night wash. | inferred proposal |
| 19 | **Closing — Sweeping Up** | Return to Opening ivory/pearl and rose-grey | A subdued trace of grey-blue | The same theatre, now quiet and lived-in. A gentle homecoming and closure; retain material detail as the stage is put to bed. | inferred proposal |

## How the differences should read

**Inferred proposal:** the six Passages should be distinguishable in a still frame by their prevailing quality:

| Passage | Short name | Main distinction | Evidence tier |
|---|---|---|---|
| P01 | **Cool rose and grey-blue** | A softened, brighter, magical theatre invitation | user-directed |
| P02 | **Lavender and light blue** | Softer and slightly dimmer than P01, with a retained driveby hint of exteriority | user-directed |
| P03 | **Sickly green, yellow and orange** | Pale, uneasy hues over the softened ground/wing lighting approach | user-directed |
| P04 | **Platinum white** | Clear and crystalline; the least tinted Passage | inferred proposal |
| P05 | **Existing look retained** | Preserve the successful overall state; remove the domestic half-moon fence practicals | user-directed |
| P06 | **Existing look retained** | Leave alone; no curtain or curtain spot | user-directed |

**User-directed P01/P02 and P06 preservation, inferred contrast with other proposals:** P01's cool rose/grey-blue should feel soft and inviting; leave P06's existing character alone. P01's stronger ground/wing readability also distinguishes it from the reported dark amber state. P02 carries the same softened approach into cooler lavender/light blue at a slightly dimmer level, with its retained driveby light. Distinguish P02 from P04's proposed clarity by tint: lavender/light blue in P02, nearly uncoloured cool light in P04. P05 retains its successful passage state with its distinct bright curtain reveal. Exact brightness is a live visual tuning step.

## P01 and Opening — implementation intent from Gary's clarification

**User-reported baseline:** P01 is currently very dark golden amber, with occasional red. Gary identifies the low forward-diagonal lights as producing the thick foggy beams. Treat this as the problem described by the operator, not as a measured fixture attribution or proof that all haze has one cause.

| Layer | Required direction | PC-agent interpretation boundary | Evidence tier |
|---|---|---|---|
| Overall colour | Move to muted **cool roses and grey-blues**, supported by soft near-white visibility. Reduce the dominant dark golden-amber/red character. | Tune the actual selected lamp colours/temperature combination; no RGB, Kelvin or desaturation percentage is specified. | user-directed |
| Overall brightness | Make the passage **brighter overall**, with clearer floor, wing and rig material detail, while softening the image. | Demonstrate a visibly brighter, more readable stage. Do not count brighter haze or a lifted black background as the improvement. Preserve theatrical black beyond the stage. | user-directed brightness; acceptance interpretation from that direction |
| Upper rig parcans | Point substantially more of the existing upper lights **down toward the ground**. | Identify the actual upper/parcan fixtures and their current controllers; choose ground targets from live geometry. No count or fixed rotation is specified. | user-directed |
| Uplights | Use uplighting to reveal **the wings themselves**. | Identify the receiving wing and actual light. Aim at the painted surface and evaluate its texture/colour; do not substitute an upward beam in empty space. | user-directed |
| Lower cross-lighting | Use **fewer lower lights shooting forward-diagonally across the passage**, reducing their thick foggy beams. | Identify the contributing subset. Do not remove all lower lamps, uplights, practicals or intentional effects by role name. Fewer may mean disabling selected lamps; that selection requires a live comparison. | user-directed; selection unresolved |
| Entry character | Within this brighter, softer look, make entry into P01 feel **magical and more like a traditional theatre**. | The magic should coexist with material visibility and consistent colour; it is not a request to invent extra effects, flashes, rig structures or a new reveal system. | user-directed |
| Opening uplights | Apply the same **muted cool rose/grey-blue, softened and brighter** direction to the Opening uplights. | Keep the Opening's stage-facing uplight palette and wing treatment continuous with P01. Resolve the actual Opening binding/fixture before changing it; do not assume a passage role controls an Opening sequence light. | user-directed |

**Declaration-proven implementation trap:** the existing score tool can auto-aim a `TOP` fixture at its side wing, while an explicit `aim_target_pair_cm` is a separate target path (`Saved/CodexConductor/lighting_scores_apply.py:1091`). Explicit point aiming is validated for Spot fixtures (`:420`). A direct actor rotation can therefore be the wrong authoring change: identify the actual fixture type and stored aiming mechanism, then make the downward-ground target there. Do not assume every parcan is a native Spot or that a role label uniquely identifies the user's lamp.

**Declaration-proven implementation trap:** runtime Drama can offset aim, a mover can own aim afterward, and bulb-body flicker can subsequently drive brightness (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:1843`, `:1885`, `:2034`). A static preview alone does not prove the intended downward/uplight treatment survives playback.

**Recommended live review:** compare the same entry and passage views before/after: visible floor and painted wings, brighter stage without amber/red dominance, muted cool rose/grey-blue, reduced low diagonal beam obstruction, and continuity from Opening uplights into P01. Exact values, fixture IDs, ground/wing targets and any residual fog tuning remain to be recorded by the PC agent. This is not an instruction to guess a new fog-density value.

## P02 — same softened rig, cooler and slightly dimmer

**User-directed:** apply the P01 approach to P02: muted cooler lavenders and light blues, more upper-rig parcans directed down at the ground, uplights revealing the wings, and fewer low forward-diagonal lamps producing thick beams. Keep the stage and its materials readable, at a slightly dimmer overall level than the revised P01. No numerical brightness ratio is specified.

**User-directed retained exception:** keep the existing **driveby light**. Its passing light gives the space a hint of exteriority and remains part of the intended P02 look. Exclude it from the general reduction of low cross-lighting and blanket palette/level changes; preserving it does not request a new exterior lighting system or broad visibility of the surrounding space.

**Declaration-proven candidate, live identity unresolved:** `Saved/CodexConductor/place_p02_car_light.py:1` describes a placed `AInfinityStageSweepLight`, and `:16` declares the actor label `P02 Car Light (trial, Gary to tune)`. These identify an existing implementation to inspect, not proof of the current actor's identity or values. Confirm the actual driveby on the PC before changing the base rig; preserve its current path, timing, colour, output and shadow behavior through this pass.

**Recommended live review:** compare P01/P02 at representative views and compare P02 immediately before, during and after the driveby. Require a visibly cooler lavender/light-blue base and a modest dimming relative to P01, readable ground/wing surfaces, fewer obstructive low beams, and the existing driveby gesture intact. Do not satisfy the dimmer target by restoring unreadable black gaps or dimming the retained driveby indiscriminately.

## P03 — softened lighting with sickly hues

**User-directed:** use **light greens, pale yellow and orange** to create a sickly set of hues. Apply the same overall softening and lighting arrangement: more upper-rig lamps directed down toward the ground, uplights revealing the wings, and fewer lower forward-diagonal lights producing thick beams. Maintain floor/wing readability while giving P03 a distinctly uneasy colour character.

**Unspecified:** the relative amounts of green/yellow/orange, exact colour values and P03's brightness relative to P01/P02. Do not carry P02's dimming instruction into P03 as an assumed numerical target. Tune the hues against actual surfaces so orange does not simply restore the earlier dominant amber/red look.

**Declaration-proven tooling limitation:** the earlier `p03_lighting_as_p01.py:1` tool copies P01's lighting structure while keeping P03 colour. Reusing that old colour-preservation behavior alone will not implement this new palette. Map the new direction to the identified P03 authoring controls; do not blindly reapply the older whole lighting/atmosphere copy as a colour adjustment.

**Recommended live review:** require distinct but pale green/yellow/orange contributions, a sickly overall tone, readable painted wings and floor, and reduced obstructive low beams. Retain the previously protected P03 special effects during base-rig tuning; this palette instruction is not a blanket recolouring of effect sources, fire, materials or the subsequent Shore scene.

## P05 — remove the domestic fence practicals

**User-directed:** P05 is **pretty good overall**. Remove the practicals lining the fence that Gary identifies as **half-moon-shaped and domestic-looking**, if they are still present. This is a specific cleanup, not a general P05 relight. Gary says they should have been removed a while ago; that is an operator report of earlier intent, not a verified removal record.

**Recommended implementation:** identify the exact fixture assemblies in the live scene, including their visible bodies and associated light sources. Remove/disable the identified group through its actual authoring controller and confirm it stays absent after materialization/playback; deleting a generated actor alone may not remove its authored source. Do not target every PRACTICAL role or every fence-mounted light by name alone.

**Recommended live review:** the half-moon domestic fittings and their associated illumination are gone, the remainder of P05 retains its successful lighting, and regeneration does not bring those fittings back. The shared smoke-machine cleanup and end-curtain legibility requirement still apply separately.

**User-directed transition exception:** P05's curtain **does fall**, revealing a **very bright space ready for a white-out transition**. Preserve that bright destination and readiness for white-out. Do not apply a generic post-curtain blackout, dim the destination to match another Passage, or treat this as P06's curtain-free ending. Read the actual timing and identify any existing white-out controls before adjusting them; if the mechanism is not established, report that rather than inventing one. This direction does not specify a new exposure ramp, white overlay, material fade or video-processing mechanism.

## All Passages — remove remaining smoke machines

**User-directed:** check all Passages and remove any remaining smoke-machine placements and their smoke effects if they have not already been removed. Existing disabled/removed machines should stay that way.

**Document-stated historical reference:** `Docs/Conductor/MORNING_SUMMARY_2026-10-09.md:38` records P01 smoke pots hidden through Show `enabled=false`. Verify the current state rather than assuming this covers every Passage or remains true on the PC.

**Recommended implementation:** identify the actual machine and its emitter/controller, disable or remove its placement through the established authoring path, and verify both the visible machine and emitted smoke are gone in playback. This is a smoke-machine cleanup, separate from height-fog tuning, light shafts and the intentional fire/candle effects.

## P01–P05 — soft end-curtain legibility spot

**User-directed, clarified:** provide a **soft spotlight pointing at the end curtain in P01–P05**, so what is on that curtain becomes more legible. This shared requirement applies alongside their individual palettes, including Passages not otherwise being relit. **P06 has no curtain; leave it alone.**

**Recommended implementation:** identify the actual end-curtain surface and a suitable existing spotlight first; retarget/tune that fixture where possible. If a dedicated light is required, use the established authoring path after confirming the target, mounting position and controller. Aim and coverage should come from the actual curtain geometry and the audience's view, not assumed end-of-route coordinates or a fixed cone angle.

**Recommended visual treatment:** a soft-edged pool that reveals the relevant curtain image/material without a distracting hot centre or thick beam obscuring it. A near-neutral visibility colour is a proposal to try, not an approved RGB/temperature setting. Tune colour and output against the curtain so the Passage palette does not overwhelm its content.

**Recommended scope:** give this light an explicit curtain-legibility purpose and exclude it from indiscriminate reduction of the low cross-lighting. Evaluate it while the end curtain is present and visible; coordinate its fade/visibility with the existing curtain state and subsequent reveal/darkness. No new cue times or always-on rule are specified. Check legibility from the intended approach/ending views, not just a close editor view.

**Declaration-proven distinction:** `Saved/CodexConductor/shadow_play_spot.py:1` targets paired shadow-play spots inside an Interaction. That is a different sequence/receiving-surface contract; do not assume those lights already provide the Passage-end requirement or automatically repurpose them. This request adds no new gobo animation or curtain artwork.

**User-directed exceptions:** P06 is explicitly excluded; do not add or light a curtain there. P05's receiving curtain falls into a very bright revealed space ready for white-out; its legibility spot must cooperate with that state rather than imposing the usual darkness treatment after the fall.

**To determine on the PC:** exact fixtures, placement, aim, cone/penumbra, intensity/units, colour and active window. The agent should record these after checking the actual curtains and transitions. Acceptance is visibly improved curtain-content legibility with soft coverage and intact transition behavior, including P05's bright reveal and P06's exclusion.

**Inferred proposal:** give all five Interactions a common neutral parchment/pearl shadow surface, so the audience recognises the storytelling mode. Their subtle accents distinguish them; the shadow itself remains black and readable. A palette target does not authorize replacing the current curtain, canvas, material or animation.

## Continuity requirements for the PC agent

- **Document-stated:** Opening beat order remains curtain at flurry 1, lights at flurry 2, moving into the stage at flurry 3 (`Docs/Conductor/FINAL_JOBS_BEFORE_REHEARSAL_2026-10-08.md:76`). This colour plan changes no timing.
- **User-directed:** Opening uplights → P01 should continue the same muted cool rose/grey-blue, brighter and softer treatment. Avoid presenting one stage colour at the front and a completely different wash after the camera enters.
- **Inferred proposal:** neutral shadow-play colour is the bridge between adjacent scene palettes. Palette changes should follow the existing reveal/darkness structure; this document adds no new transition mechanism.
- **Inferred proposal:** P03's sickly pale green/yellow/orange can give way to S3's cooler pearl/water through the existing transition. Keep these distinct palettes rather than applying P03's colours to the Shore. P04's clarity can support S4's slightly warmer human scene without an added strike in its dark entry.
- **User-directed:** P05's curtain fall reveals a very bright space prepared for white-out. This exception takes precedence over any generic curtain-to-darkness recipe in older notes/tools.
- **Inferred proposal:** P06 → Void takes colour away. Void → Closing restores the Opening's soft ivory/rose-grey family, providing the bookend.

## Implementation boundary

This is the colour-and-tone section of the plan, with explicit P01/Opening/P02/P03 lighting intent, a retained P02 driveby exception and a shared soft end-curtain spotlight requirement. The next stage should identify the selected fixtures/roles, visibility versus mood lighting, and the existing sequence controls that will carry each target.

- **Declaration-proven:** passage lamps have authored colour, temperature, intensity/units and transform controls in `FInfinityStageLightSettings` / `FInfinityCueAttachment` (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:194`, `:434`). Runtime Drama/movers/bulb bodies can subsequently own intensity or aim (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:1843`).
- **Declaration-proven:** some scene lighting has both rise keys and Scene hold values (`Saved/CodexConductor/s3_light_levels.py:1`). Passage colour presets must not be assumed to control every Scene.
- **Recommended implementation constraint:** retain light units and the distinction between colour and temperature. Map colour targets to identified authoring controls; do not blanket-recolour all lamps, body emissives, materials, fire or media.
- **Recommended implementation constraint:** keep Klara's requested theatrical black around P01–P04 through appropriate selected-light tuning. Do not create visibility by lifting the entire world's exposure or adding an assumed environment-light system.
- **Recommended implementation constraint:** preserve the current successful P05/P06 state as the baseline while comparing the palette target. Do not overwrite it from source defaults or an old preset name.
- **To determine through the PC tuning process:** numerical RGB/temperature/intensity, colour weights, cone/fog changes, fixture targets and any required light placement. Use the current state, Gary's physical examples and comparisons against actual frames. Additional cue timing or a new mechanism is not authorized merely by a colour direction.

## PC agent — capture, tune, replicate, verify

### 1. Establish the live baseline

**Required process:** read the PC checkout's current `AGENTS.md` and latest handover; compare its revision with this document's branch before integrating. Preserve local work and existing manual adjustments. Record which of the directed removals/changes are already present, so they are not re-created or repeated blindly.

**Declaration-proven connection context:** the checked-out `README.md:71` and `Saved/CodexMocap/mcp_request.py:9` specify PussStage on loopback **8010**, separate from MHFat on 8000. Older portions of `Docs/CodexUnrealMCPRunbook.md` still quote 8000. Confirm the PC's actual configuration and expected world, `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`, before using the guarded Saved-script route. Use the repository client with its configured URL/override, not a second editor or an assumed connection.

**Required process:** take the repository-required backup before authoring changes. Coordinate a single writer with Gary. Scripts must refuse while PIE or a conflicting editing operation is active; do not stop his session or close the editor unasked. Record and resolve pre-existing dirty packages before any narrow save, so it cannot accidentally persist unrelated changes.

**Required inventory for each selected fixture:** passage/cue and attachment GUIDs, or the actual sequence binding/object path; fixture type and units; light versus visible body; enabled/visibility state; colour and temperature state; intensity; authored transform and its coordinate frame; active Drama/mover/body/sequence writers; any generation preset/override that can recreate or re-aim it. The label is a human aid, not the sole identity. Record the actual receiving ground, wing or curtain for each demonstrated aim.

### 2. Capture Gary's physical examples before changing them

**User-directed division of work:** Gary demonstrates representative placement/angles and some lighting states. The agent records the complete state of the selected examples, resolves the persistent authoring owner, and uses those examples as the physical basis for replication. Subsequent numeric colour/intensity tuning follows the directed palette and brightness targets.

**Required process:** capture at least the demonstrated upper-ground-light and wing-uplight families, plus the low-light subset selected for reduction. Use the actual examples Gary chooses, including the entry bays when relevant. Record left/right or other distinct arrangements separately. If an example is made in PIE, establish how to transfer it to its authored counterpart; a runtime copy is not by itself a saved authoring change.

**Required replication rule:** reproduce the demonstrated relative placement/aim for the same fixture role in applicable bays, composing through each bay's real station/route frame. Do not paste world transforms down a curved route. Adapt to actual left/right geometry and receiving surfaces where needed, recording the variation; do not introduce random jitter, new mounting structures or a guessed mirroring rule. Keep light and body transforms distinct unless the actual assembly/example establishes how they move together.

**Declaration-proven existing precedent and limits:** `Saved/CodexConductor/p01_rig_pattern.py:1` copies live template attachment translations/rotations, with passage support described in its header. Its older defaults use specific B03/B04 templates, exclude P01 B01/B02 and can leave some missing/parity roles untouched. It also defaults to lights rather than their body props (`:102`). Review its actual target list and current template mapping before reuse; it is not automatic coverage of every new entry/uplight example.

### 3. Tune states around the demonstrated transforms

| Group | Agent's tuning target | Physical/retention constraint |
|---|---|---|
| Opening/P01 | Muted cool rose/grey-blue; visibly brighter, softer floor/wing readability; magical theatre entry. | Preserve the demonstrated aims; match the Opening uplight treatment and established opening beats. |
| P02 | Cooler lavender/light blue, modestly dimmer than the revised P01 while readable. | Preserve its demonstrated aims and the driveby's complete existing behavior. |
| P03 | Light green/pale yellow/orange; sickly but pale and legible. | Preserve intentional special effects. Start from its measured brightness and tune for readability; no implied P02 gain ratio. |
| P05 | Preserve current passage lighting; remove the identified fence fittings. | Preserve its bright post-curtain space/white-out readiness. |
| End curtains, P01–P05 | Soft, readable image/material with controlled spill. | Use actual curtain geometry/state; P05's reveal is bright. P06 has no spot. |

**Required tuning method:** read actual values first. Change colour/saturation, intensity and any cone/source-softness controls in small, reviewable passes while comparing the same camera/frame/state. Record the exact accepted values and units. P01's brightness target is improved stage/surface visibility, not simply brighter haze; P02's dimming is relative to that revised look. Preserve floor/wing colour and theatrical black outside the intended area.

**Required persistence rule:** retain the accepted manual transforms while writing the selected lighting fields. Avoid whole-struct reconstruction from old defaults and broad score regeneration. For a proposed replication/rebuild, enumerate the expected targets and prove the retained transforms/effects survive it. For keyed lights, modify the actual controlling keys/defaults and any relevant hold/pre-drive rather than just the preview component.

**Declaration-proven critical trap:** `lighting_scores_apply.py:2026` supports folding some manual fields, including location and lighting values, but not arbitrary rotation; `fold_overrides` refuses unsupported fields (`:2171`). `_apply_live_aims` can recompute TOP/wing aim (`:2573`). Do not claim a hand-set angle is safely folded into a score because its intensity/location was folded. Preserve it through a supported authoring/override path and verify regeneration; if the existing path cannot represent it, stop that part and explain the exact limitation.

**Required scope of reduction/removal:** use explicit identified target sets for lower diagonal beams, smoke machines and P05 half-moon fittings. Capture their pre-change state and update their actual source so they stay removed. Preserve the driveby, curtain-legibility lights and unrelated practicals/effects. Treat fog tuning separately and only after identifying the responsible fog/shaft mechanism.

### 4. Work order and acceptance

**Recommended order:** baseline and cleanup census → identify/capture Gary's examples → tune one representative P01/Opening treatment → review → replicate within P01 → adapt P02 and P03 → check P05 cleanup/bright reveal → tune the P01–P05 curtain spots. Interleave cleanup with visual comparison where it materially changes the baseline; keep each saved step reversible. Existing successful work should not be re-run just to follow this order.

**Required authoring loop:** live read-only plan/DRY with resolved targets → named backup and before-state record → scoped change → materialize only the required Passage actor(s), where applicable → save only the affected authoring packages/level after checking dirty scope → independent read-back and playback checks. Use existing project transports/helpers and contracts; do not introduce a new timing clock or a new generic lighting system.

**Declaration-proven test obligations for reused score tools:** `Saved/CodexConductor/lighting_scores_apply.py:1` requires SavedMasterMatchesShow and SceneCutBindingsResolve after its apply/revert workflow. Run the applicable focused tests when that path is used and read completed results; queued tests are not passes. Do not broaden automation to the mutating PussStage bootstrap filter (`Docs/WindowsBuildProcedure.md:73`). No C++ build is implied by a data-only lighting adjustment.

| Check before reporting an item complete | Evidence to retain |
|---|---|
| Correct identity, explicit scope and unchanged unrelated state | Actual target IDs, before/after field list, preserved-target checks and save/dirty census. |
| Gary's demonstrated angles persist | Captured authoring transforms and read-back after materialization/save; replay/reload when needed to establish persistence. |
| P01/Opening achieve the revised look | Comparable views showing brighter, softer cool rose/grey-blue, readable ground/wings, reduced low beam obstruction and continuous entry colour. |
| P02 remains distinct and its driveby intact | Comparable base-state views plus before/during/after driveby, with its retained path/timing/colour/output. |
| P03 reads as sickly and remains clear | Representative views showing light green/pale yellow/orange and intact special effects. |
| P05 cleanup preserves its success and transition | Half-moon fixtures absent after regeneration; curtain before/during/after fall; very bright revealed space and existing white-out readiness. |
| Curtain spots meet their purpose | Approach/end views showing legible content and soft coverage for P01–P05; no new curtain light in P06. |
| Removal and runtime states survive playback | Smoke machines remain absent; fixture aims/levels behave correctly under their actual runtime writers and relevant pause/scrub/reveal states. |

**Required hand-back:** list completed items, selected fixture IDs, numerical settings, demonstrated-transform mappings, changes to generating configuration or sequence controls, named backups/revert records, saved read-back and test outcomes, and representative images. Separate source/declaration evidence, measured runtime results and visual acceptance. Report any exact unresolved identity/mechanism rather than filling it with an inferred system.

## Scene-context references

**Declaration-proven context:** Scene identities and transition descriptions are recorded in `Docs/Conductor/FINAL_JOBS_BEFORE_REHEARSAL_2026-10-08.md:18` (S1), `:31` (S2), `:36` (S3), `:47` (S4), `:52` (S5), and `:56` (S6). The Void's candle choice is stated in `Docs/Scene6BeatSheet_2026-10-02.md:73`. These references establish context; they do not establish the current rendered palette.

**Measured scope of this delivery:** a document was prepared from the saved segment order, Klara's supplied notes and repository source/context. No lighting code, fixture values, Show asset, level, camera, material, media or project-PC state was changed.
