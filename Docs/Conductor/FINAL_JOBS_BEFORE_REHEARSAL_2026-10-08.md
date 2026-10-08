# Final jobs before rehearsal: Tue 13 Oct 2026

Gary's walk-through, 8 Oct (first chunk: Opening → Interaction 1 → P02). The scene video fallbacks are due Sun 11 Oct
lunchtime, once scenes are sealed. Priority: **P1** = must be done for Tuesday; **P2** = should be done; **P3** = nice
to have.

## Chunk 1: Opening → P02

| # | Segment | Job | Pri | State / notes |
|---|---|---|---|---|
| 1.1 | Opening | **The lighting sequence is not correct.** Rework the opening's lighting cues. | P1 | Not started. Plan of record: Docs/Conductor/OPENING_SEQUENCE_PLAN_2026-10-04.md. Next step: walk the current cues with Gary and agree the target sequence. |
| 1.2 | Opening | **The opening structure on the front of the stage** (ornamental stage front / proscenium). "Not a big job, but fundamentally important." | P1 | The stage front was unbuilt as of 28 Sep (memory rig-handover, c467046). Next step: find the current state and build or finish it. Stills to Gary. |
| 1.3 | Opening → P01 | The movement into Passage 1 needs work. | P1 | Not started. |
| 1.4 | Opening → P01 | The change from the opening's mood stage lighting into the dark stage we move into is **awkward**. | P1 | Not started. Pairs with 1.1. |
| 1.5 | P01 | Overall presentable; tweaks only. | P3 | — |
| 1.6 | P01 → S1 | The **hangar snap** at the cut. | — | **FIXED 8 Oct** (ARRMOV-20261008-073648: the roof hinge and lattice now posed at Play start, all six Arrivals; measured smooth in Play). |
| 1.7 | P01 → S1 | **Minimal lighting cues that take us down to the darkness S1 starts in.** | P2 | Not started. |
| 1.8 | S1 | **Record the Scene 1 video** (fallback). | P1 | Waits for S1 to be sealed. The MRQ tool is ready (Saved/CodexConductor/MRQ/, plan MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md). S1 animals run-up DONE (KLARAPREROLLS1-20261008-034340). |
| 1.9 | S1 → Interaction 1 (**and every Interaction**) | **The interaction curtain transition.** We go into darkness; a spotlight discovers a new curtain; the shadow-puppetry gobo animation plays out ON that curtain. "Very important." | P1 | Plan: Docs/Conductor/SCENE_EXIT_SHADOW_CURTAIN_PLAN_2026-10-07.md (Gary 7 Oct: the curtain must already be there before the spot slowly comes up; the shadow scene plays on the curtain, not on a card; then the light dims and the curtain switch is made). |
| 1.9a | All Interactions | **First step: remove the white shadow card** in every Interaction (two 480×270 cards per Interaction, 1 cm in front of each drape: "Sleight Mouth/Hangar Shadow Card", curtain_sleight.py). | P1 | Gary already removed the I4 hangar card (saved 7 Oct 17:05). The other cards remain. Removing them "loses nothing but a grey rectangle" [declaration, plan §A]. |
| 1.9b | All Interactions | **Bring the shadow-play spot into place** on the curtain, as set up in the Interaction Gary remembers (I4's "Shadow Play Spot", shadow_play_spot.py: 7483 cd, cast shadows), and make it come up **slowly**. | P1 | Today the spot snaps up in 0.5 s (plan: frames 175–187) and needs a slow fade. Next step: confirm with Gary which Interaction is the reference, then replicate it to I1–I5. |
| 1.10 | Interaction 1 → P02 | Curtain drop. | — | OK as is. |


## Chunk 2: P02 → Interaction 3 (Gary 8 Oct)

| # | Segment | Job | Pri | State / notes |
|---|---|---|---|---|
| 2.1 | P02 | **Lighting** "really doesn't look good", likely quick to fix. Timing is correct. | P1 | Not started. |
| 2.2 | P01 (all walks) | **Check the Passage timings.** Gary thinks P01 may be a little too long, and that the walking music up to P06 is all about 1:07. | P2 | [measured, Master music track, 25 fps] Track lengths do NOT match: P01 73.5 s (section 96.3 s), P02 45.5 s (47.5), P03 40.2 s (42.2), P04 48.4 s (50.4), P05 42.0 s (section 186.4 s), P06 110.6 s (126.0). Next step: compare each Passage segment with its music and with Gary's "about 1:07", then decide trims. |
| 2.3 | P02 → S2 (Shrine) | Waiting on **Klara's final shrine (arrives tomorrow)**. The shrine, and maybe her school scene, need **Klara's wings upgraded to V3**. | P1 | Feasibility: Docs/Conductor/KLARA_WINGS_V3_FEASIBILITY_2026-10-07.md (replace in position/scale exactly). |
| 2.4 | S2 → Interaction 2 | The transition is the known pattern (darkness, spot discovers the curtain). **Do it.** | P1 | Same as 1.9. |
| 2.5 | Interaction 2 | The interaction itself is not known yet: we design it together. **URGENT investigation: animated gobos / shadow puppetry with spotlights in Unreal.** | P1 | Existing groundwork: Docs/ShadowGoboPipeline_2026-10-06.md + Tools/ShadowGobo/make_gobo_flipbook.py (flipbook pipeline), Docs/ShadowPuppetCaptureSpec.md. Next step: a working test (a spotlight light function playing a flipbook onto a curtain), stills/clip to Gary. |
| 2.6 | Interaction 2 → P03 | The known curtain-drop pattern; just needs doing. | P1 | — |
| 2.7 | P03 | **Lighting**: it looks "quite milky". | P1 | Not started (haze/fog suspect [inferred]). |
| 2.8 | P03 → S3 | Transition OK, but some external or rig light comes on too bright and spoils the deep-darkness sleight of hand while the MetaHumans spawn (S3 0:04). | P1 | Tonight S3's strike and rig lights are 0 and the rects off until 0:15; whatever is left still needs measuring (every light's intensity over S3 0–8 s in Play). |
| 2.9 | S3 → Interaction 3 | Where the curtain goes is undecided; **S3's backdrop needs changing**, and the two may solve each other. | P2 | Backdrop: Gary directs it in Blender/Fuser. |
| 2.10 | Interaction 3 | Same as all Interactions (cards out, spot in, gobo play). | P1 | Same as 1.9. |


## Chunk 3: Interaction 3 → end (Gary 8 Oct)

| # | Segment | Job | Pri | State / notes |
|---|---|---|---|---|
| 3.1 | Interaction 3 → P04 | The curtain-drop pattern. | P1 | Same as 1.10 / 2.6. |
| 3.2 | P04 | One of the successful passages; could be "even more dazzling". | P3 | — |
| 3.3 | P04 → S4 | **CHECK TONIGHT**: do we move smoothly into Klara's S4, with a short loop of the children + pigeon animation in the transitional moment? Does the **pendulum swing as in Klara's sequence**, not freely in the wrong place? Then an easy, smooth handover into her sequence. "One of the most dazzling scenes": the transitions must be good. | P1 | Background: S4_ENTRY_INVESTIGATION / S4_ENTRY_V5_BUILD_2026-10-07.md ("arrive in the dark", no strikes); pendulum tick was turned off 7 Oct. |
| 3.4 | S4 | Switch Klara's S4 wings to **V3**. | P2 | Same feasibility doc as 2.3. |
| 3.5 | S4 → Interaction 4 | Same curtain + spotlight sleight of hand, so the next Passage emerges when the curtain falls (may already be partly there; I4 is the furthest along). | P1 | Same as 1.9. |
| 3.6 | Interaction 4 → P05 | Curtain drop. | P1 | — |
| 3.7 | P05 | "Pretty excellent"; improve later. | P3 | — |
| 3.8 | P05 → S5 | **Rob (animator)** sends the village S5 arrives at, tomorrow. S5 is a video; we transition into it in-level. | P1 | Waits on Rob. |
| 3.9 | S5 → Interaction 5 | A regular Interaction (the end of the boy's role): **Puss gets his boots put on.** | P1 | Same as 1.9 + its own shadow play. |
| 3.10 | Interaction 5 → P06 | Curtain drop. | P1 | — |
| 3.11 | P06 | In a pretty good place. **The domino-falling animation has not been looked at yet**, and it matters (W&T: 6-slab chain slam at ~37 s, TOPPLE runs 7 Oct). **Fire and the planned FX: start building tonight.** | P1 | FX plan: Docs/Conductor/EFFECTS_PLAN_2026-10-07.md (smoke plumes, candle + wing-burn, beam motes, rain, bees earlier; Cascade assets usable without new C++). P06 is the most musical passage. |
| 3.12 | P06 → S6 the Void | Total blackness; bees and an old lady. The Void sequence needs many considerations and **doesn't properly exist yet** (Klara started some work). Needed by Sunday. | P1 | Klara's void hookup: klara_void_s6.py (4c110e4). |
| 3.13 | S6 → ENDING (new) | Exit from the Void through blackness, then arrive at **a lovely stage being closed up**: the lights go off, happy animals there, some animals from earlier recur, "all the creatures a puss can go to bed happy with". The fairy tale ends. | P1 | New scene: not started. Needs a design pass with Gary. |

## Carried over (already on other lists, for reference)
- S3: done or in progress tonight (see GARY_NOTES_LIST_2026-10-08.md). Open items: pearl twin look-match stills; dunes 2× (with the wall-camera clash); fabric and MetaHuman look (texture A/B/C, full-body rebuild?); the vamp fix in the build window.
- Fixtures: proposals in; the C++ patch is held for a build.
- W&T curtain production bake: running overnight (unfurl_sleight_b1hop10_p02).

_Walk-through complete (chunks 1–3)._

## Gary's notes, 8 Oct ~08:30 UTC (before bed)
| # | Segment | Job | Pri | State / notes |
|---|---|---|---|---|
| 4.1 | All Passages | **Timing = the music.** Each Passage's length comes from its own music (set-piece pauses maybe later). Run the **musical analysis** (flurries/beats) so lights can be cued to it. Replaces 2.2. | P1 | Tonight: Codex P11 (analysis + relength tool, DRY only). |
| 4.2 | Opening | Lighting is "too large and washy". It should be **tighter soft-edge spots that move into the centre**, plus lights in the **upper-left and upper-right corners that dramatise the flurries**. **The curtain must come down in the final flurry** (now we see a dark stage, lit only by the opening light, while the music runs). Gary's cue list: (1) "second flurry/wave: curtain falls"; (2) "second flurry/wave: lights come on"; (3) "third flurry, end of opening: perspective adjustment". | P1 | Items (1) and (2) both say "second", so which flurry drops the curtain is still to confirm. Tonight: Codex P13 proposal + stills; nothing applied. |
| 4.3 | Stage front | For now, **take the wings of P01's first bay and fix them to the front of the stage**. | P1 | Tonight: conductor. |
| 4.4 | P03 | **Lighting identical to P01** in structure, direction and position relative to the wings; colour stays. Keep P03's special effects (e.g. the "car lighting move", if it is in P03). Replaces 2.7. | P1 | Tonight: conductor (census first). |
| 4.5 | S3 | **Handprints not readable** (Cameron, on the latest S3 video). They need to read as handprints: darker marks; scrabbling, scratching, desperate, very many people. Only where the camera shot is (the B06 wall); about **2× density** there, none needed elsewhere. | P1 | Tonight: Codex P12 (placement + darker variant), stills for Gary. |
| 4.6 | P01 | **Hide the smoke machines** ("little graphical patches of smoke"). | P1 | Tonight: conductor. |

### 4.2 Opening cue order, Gary's clarification (8 Oct, own words, after bed-time note)
- **Flurry 1** (peak 37.44 s, P11 analysis): **curtain falls**.
- **Flurry 2** (peak 57.36 s): **lights.** Parcans "lighting gloriously the front facade of the stage", plus SOME lights
  inside the Passage, so it is not totally dark in there and outside and inside connect.
- **Flurry 3** (peak 70.44 s): **moving in to the stage** (the perspective adjustment / camera move in).
- **When the walking music starts** (P01): the rest of the P01 lights add up to today's state.
- For P13: set the flurry args to 1 / 2 / 3. A partial P01 light preset at flurry 2 builds up to full when P01's music
  starts.
