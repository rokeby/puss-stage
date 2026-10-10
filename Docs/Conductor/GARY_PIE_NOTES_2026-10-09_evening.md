# Gary's PIE notes — 9 Oct evening (Conductor 5)

| # | Where | Note (Gary) | Route |
|---|---|---|---|
| E1 | S3 figures | underwear colour unchanged; feet sunk in dune; hessian shrouds BLACK/shiny/untextured; one figure without shroud; T-shirts white; a figure looks translucent | read-only diag (blocked by PIE; rerun) |
| E2 | S3 pearl | disappears at ~3:25 with a brief ghost — must fade over 2 s | diag + fix |
| E3 | Opening | curtain falls twice → ONE fall at 00:37:50 then hold; dark before except subtle lighting; camera wider then slow move-in after the fall; flashes first, add stage-front uplights; bulbs scattered randomly on floor | Codex 87 (done, review) |
| E4 | Proscenium | greenscreen fringe on new front-stage wings | Codex 88 |
| E5 | I1 | curtain must be hung before the shadow spot fades up (also I3/I4/I5) | Codex 89 (done, review) |
| E6 | I1 / P02 entry | camera too zoomed on curtain (just fill frame); lighting jump at ~0:50 sleight cut; 20 s camera lowering into P02 | Codex 90 |
| E7 | I2 (reference) | ~0:50 zooms in too close then out; after curtain drop the camera doesn't travel through the curtain plane into P03's opening frame | Codex 90b |
| E8 | P02 | lighting should start = P01 (tool ready, Q7/Q10); practicals dangling + old domestic lamps not removed (P01 floor tool has a passage arg) | live runs after PIE |
| E9 | P02 | Top wings look backwards | Codex 91 (diag) |
| E10 | S2 | raise the rig + hangar height AND widen so Klara's S2 scene fits fully, not cutting our ceiling | Codex 92 |
| E11 | P03 | wings: interleave the 3 old square wings with the green ones along depth; P03 lacks the shiny floor | Codex 93 |
| E12 | P03→S3 | hangar behind the ragged curtain lit/visible → must be DARK; fires/smoke visible early → spawn only when the scene is dark and become visible when brought in at scene start; S3 arrival is dim not dark — figures visible, more pop in; lighting brightens before the spawn completes | Codex 94 |
| E13 | Passage end → Scene start | detectable rig-position jump even with dog view at default (also: free dog view should ease back to default over a few seconds before) | Codex 95 (see memory puss-gait-bob-biased) |
| E14 | Cue Desk | rehearsal bar timeline (job 86) ready for a 20–30 min build window | after PIE |
| E15 | Interlude | Unreal Nap label → "Interlude: Puss Sleep/Wet Tennis Ball/Battery" | small rename, after diag |
| E16 | I3 | curtain drop + camera move land in the right place, but I3 must BEGIN at the end of the last scene in TOTAL DARKNESS, get into position (like I2), THEN light the shadow; big lighting pop at 0:50.0 (sleight cut) | Codex 90b |
| E17 | P04 → S4 | "everything is off": simplify — enter the hangar in TOTAL darkness and CUT to Klara's sequence (which also begins in darkness). Klara's sequence camera currently comes out to the curtain, which is UP again → visual problems + likely light leakage from the passage into the scene: P04 lights OFF by then; curtain stays dropped or hidden (whichever is easier) | Codex 96 |
| E18 | Nap | flooded with light — probably the shadow-puppetry spot still on (it must turn off after the shadow sequence); the CAT MODEL is visible — must NOT be (we stay in cat view); it is the cat's own view that gently breathes as if sleeping, camera by the ground; label still "Nap — battery change" (rename to "Interlude: Puss Sleep/Wet Tennis Ball/Battery") | Codex 97 |

- **E19 (S5)**: awfully bright, but Gary doesn't mind it here; a little washed out by fog. The brightness exposes the metal girder structures: they need more texture, like the Hyper3D work on parts of the front. → Codex job 98 (offline girder texture plan, dedupe against Hyper3D front work).
- **E20 (cloud wings)**: the last few bays of cloud wings should widen a lot — **Gary does this manually**. No job.
- **E21 (P05 transition curtain image)**: change it from a rabbit in a circle of toadstools to a **deer looking at the camera**, with the deer drawn a bit smaller. **Gary's note to self**: no job unless he asks.
- **E22 (I5 curtain)**: hidden behind a wall. Not urgent, since the S5 hangar will change or go when Rob's material comes in. Revisit after Rob's S5 lands. No job now.
- **E23 (S6)**: (a) a parcan stands in the middle of the frame as we arrive; Gary thinks it may be a misplaced Puss light. (b) The sunset is good, but the sun disc itself isn't visible, only its reflection. S6 is the ONLY place in the show where the sun should be visible. → Codex job 99.
- **E24 (S6)**: the old-lady cuts, minimal as they are, are good; they could be darker. The swarm is uncompelling and needs work. Whose swarm it is [inferred, from records]: Klara's `/Game/FX/NS_BeeSwarm`, a Sequencer spawnable in S6 from 1 s (EFFECTS_PLAN_2026-10-07.md:55; it has no User. params and a constant spawn rate). Our C++ bee swarm (33212163, 8 tests green) was built but never shown, because it lacks its renderer Niagara system (EFFECTS_PLAN:150). Darker cuts and a swarm rework are pending Gary's go.
- **E24b (S6 swarm, Gary)**: run the Frenzy analysis tool (the S3 mocap-intensity tool, job P5) on the old lady, and use it to modulate the swarm's position and concentration so the bees respond when she bats her hands. → Codex job 100.
- **E25 (Ending)**: not built yet. Gary: S6 ends in blackness, then we arrive at the opening stage again, but only the stage part with no infinity behind it. Earlier design is in P10_FRONT_VOID_ENDING_2026-10-08.md §3 (stage being closed up, happy animals recurring). → Job 101 when dispatched.
- **E26 (P05 length, Gary decision 9 Oct ~22:50)**: cut P05 to its audio track time (42.04 s). Bring the camera keys that fall past the new end forward, where they are needed. → Codex job 103 (offline prep), then live after job 102.
- **E27 (P06 length, Gary 9 Oct ~23:00)**: "The full 125 is correct". P06 should run the FULL 125 s track; today it is set to 110.6 s. To confirm before acting: does `SW_P06_IntoVoid` = Cameron's `P06_Walking6.wav` (125.000 s)? A read-only duration probe is queued behind job 102. Lengthening P06 re-times the P06 retime (dusk 32.48 s), chain A/B (slam 108.6 s), the domino finale and FX. → job 104 after the probe.
- **E27b (Gary ~23:15)**: "Leave the sound waves". No SoundWave import or swap. Job 104 runs ONLY if its DRY verdict is `LENGTHEN_ONLY`; an `IMPORT_AND_SWAP` verdict means STOP and ask Gary.
- **E9 decision (Gary ~00:05)**: YES. Flip the 23 P02 Top wings 180° (DRY RZSW-20261009-194606: 23/23 Tops reversed against the L/R convention). Physical turn only, no image flip. → Codex job 106. **E8 decision**: yes, add the P02 beams so P02 lighting = P01 can run → job 105, already dispatched.
- **E28 (P02 car drive-by, Gary ~01:20 10 Oct)**: the shadow doesn't travel across to the far wings. Gary: set the drive-by attenuation (cutoff) radius to **10000 cm**. Use job 110's tune tool with `attenuation_radius_cm=10000`, applied in pass 2. Aim and intensity stay unchanged unless Gary asks.
- **E29 (all shadow casters, Gary ~01:25)**: like the drive-by, every shadow-casting light should REACH ACROSS the wings. Gary suspects lights whose radius ends mid-corridor add milky fog when unfocused. Conductor's note [inferred]: a likelier fog contributor is lights that light the volumetric fog WITHOUT volumetric shadows (the drive-by has cast_volumetric_shadow=False), which gives uniform haze with no shafts. Job 111 reports both, per light. → Codex job 111.
- **E27c (Gary ~01:40 10 Oct)**: P06 SWITCHES to Cameron's `P06_Walking6` (125 s): "the right one and right length". This overrides E27b ("leave the sound waves") for P06 only. Job 104 runs with the `IMPORT_AND_SWAP` verdict in pass 2.
- **Gary 10 Oct ~01:50, list replies**:
  - Girder texture (job 98) can apply to girders EVERYWHERE, not only S5. Low priority; extend after the S5 apply is seen.
  - Cloud-wing widening: DONE (Gary).
  - Cue Book dark stills: low priority; take them from the video after recording.
  - Code.gs: up to date.
  - S6 old-lady cuts darker: eventually, after Gary directs them by hand.
- **Gary 10 Oct ~02:00**: S3 dune set D is PARKED; the scene is already framed. The S3 MetaHuman material rendering and clothing colour is **CRITICAL**: the black, shiny, untextured hessian; the white T-shirts; the underwear colour; the no-shroud and translucent figures. Next: pass-2 item 0 (S3 diag v2) feeds a fix job straight away.
