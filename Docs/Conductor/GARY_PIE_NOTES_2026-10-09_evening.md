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
- **Gary ~02:05**: S3 T-shirts MATCH the hessian (desaturated sackcloth tone), so the shroud/shirt overlap does not create visual interference.
- **Gary ~02:20 10 Oct**: the P02 Top wings now flip nicely. The S2 hangar is still the wrong size for Klara's scene: job 92 (fixed in 112, envelope 85x160 m) is not applied yet; it is pass 2 item 13. The S2 floor has the wrong texture: to clarify with Gary (since 8 Oct it is MI_Floor_DarkWet on S2 Hangar Floor 1-3 + Apron).
- **Gary ~02:35**: S2 floor: the easiest fix is to REPLACE it with a copy of the P01 floor (his drag test reflected correctly) → Codex job 119.
- **Gary ~03:00**: approved the I1 restore (done: backup copied over, hash match). Crowd 15 yaw: FORGET it (small move). Conductor finding from the diag-v2 JSON [measured params; look inferred]: the job-40 hessian SHORTS MIs inherit the MetaHuman DefaultGarment params `c_metalness value 0.8` and `C_roughness value 0.2`, i.e. metal-like, so likely the black/shiny/untextured look. They carry no hessian textures. The shrouds are M_Shroud_Hessian (RoughnessDry 0.85, Wet 0.45, WeaveTiling 8). Shore05 still wears MI_Sackcloth_OldGrey_Cloth_v2.
- **Gary ~03:40 (LATER)**: S3 figures: replace the unique short hair with VERY, VERY LONG, maximally unkempt, dark brown and grey hair on all figures (MetaHuman groom swap or cards; crowd copies too). Not tonight.
- **Gary ~03:50 (later, low priority)**: the last NPC to get the brown shirt (S3 Hangar Float Hold: Shore05_M53) did NOT get the hessian back-face fix. Reason [measured, diag v2]: both Shore05 actors still wear MI_Sackcloth_OldGrey_Cloth_v2, not M_Shroud_Hessian. Fix later: assign an MI_Shroud_Hessian_0N to the Shore05 shroud slots. Garments now carry the hessian weave on layer A (12 MIs, tiling 12, weave_a_record.json); stains were skipped (they need the mask-channel proof).
- **Gary 10 Oct ~00:10 (passages check)**:
  - **Correction to E23**: the parcan in the middle of the arrival shot, and the sun disc that never shows (its LIGHT shows although the sun is ahead of us), are in **P06**, not S6. Job 99 targeted S6 → job 126 re-scopes it to P06.
  - **P04**: hide the smoke-machine object near the final wing → job 127.
  - **P05**: every LEFT wing is offset 20 cm on its LOCAL X relative to the right, so the two don't overlap → job 128.
  - **Shadow radii (E29)**: run overnight: the job 111 DRY survey, then the raise-only APPLY, then the perf check; auto-REVERT if frame time regresses beyond the gate.
  - **P02 floor is NOT reflective** (the dark-wet MI was applied 9 Oct). Same symptom as S2 → job 129: compare with the P01 floor, then the job-119-style P01 floor copy for P02.
  - **CORRECTION (Gary)**: the floor that fails to reflect, where his P01-floor drag test worked, is **P02**, not S2 (the conductor misread "s2's top wings" as S2). Job 119 (S2 target) is HELD: its request was renamed so pass 2 cannot run it. Job 129 does P02. The S2 floor: no change.
  - **S2 shrine fires (Gary)**: the Niagara fires on the S2 shrine are visible in the editor but do NOT play in PIE, so the shrine is unlit → job 130 (diagnose; never save Klara's levels).
- **Nap camera (Gary ~01:00 10 Oct local)**: in LS_Nap_BatteryChange, RAISE +20 cm; head TILT (roll) 35°, as if resting on a paw; look UP-FORWARD to the LEFT, as if lying on its side looking up at the wings, a little upside down. Conductor values: Z +20 cm, roll 35°, yaw −20° (left), pitch +15° (up), all offset uniformly on every key so the breathing loop and seam survive. A still at Master 24:51.2; Gary fine-tunes.
- **3D stage front (Gary ~01:15 local 10 Oct)**: use the **Dusty** maps. Export the missing Crest / Solomonic Column / Cat Candelabra FBXs tonight (headless Blender, no bake). The chandelier is **Iron3**. Order: job 133 (export) → job 131 import + place (all six pieces) → wide still → job 87 re-DRY / re-plan → opening stills.
- **I2/I3 staging (Gary ~02:30 local 10 Oct, answers the 90b question)**: stage I2 and I3 at the HANGAR BACK WALL.
  1. During the dark transition the hangar/scene is EMPTIED (its set hidden).
  2. The curtain hangs on the back wall.
  3. The camera moves into the interaction, and the shadow scene plays on that curtain.
  4. Then the sleight move into the passage.

  → Codex job 144. It replaces the "missing I3 hangar/mouth spots" question, so 90b is superseded for those spots.
- **Job 144 decisions (Gary ~03:00 local)**:
  1. S3: FRONT projection (the spot in front of the curtain).
  2. Tight framing on the curtain. The curtain must take a SIMILAR PROPORTION of the frame in ALL interactions (match I1/I4/I5: measure their curtain frame fraction and fit the I2/I3 camera distance to it).
  3. I3: reuse ANY existing gobo for now; real gobos are coming.
- **P02 lighting (Gary, morning 10 Oct)**: needs an AUDIT: both too HEAVY (perf, haze, possibly the GPU hang) and SHOWING UP TOO LITTLE. → Codex job 161 (offline, from the records).
- **P02 lean lighting (Gary: "Sure")**: APPROVED for the first slot after the reboot: job 161 p02_lighting_lean DRY → APPLY → PIE perf (p95 at 3 P02 spots) + stills; auto-REVERT if p95 is not better than 40.7 ms or the look is worse. Car radius 10000 → 4600 cm approved.
- **P06 parcan (Gary 10 Oct ~12:30, screenshot)**: the parcan standing in the middle of the P06 arrival shot is the fixture body associated with / collocated with the light **"P06 EVT B02 BLACK F00 CAMERA"** (a SpotLight; a P06 lighting-score event light, bay 02). This is Gary's selection for job 126 (tool P99S6ArrivalSun_20261009): hide that body only (bHidden, revertible); the light stays unless the light itself is the problem.
- **Filming (Gary)**: the whole show run-through is best, but it should include all current improvements plus Gary's gobo animations. To save usage, Gary will probably run it through a collaborator.
- **Cue Book**: Gary has added the passcode to Saved/CueBook/cuebook_pass.txt. **Puss > Pull Cue Book** works after the next editor restart.
- **S1 (Gary 10 Oct ~12:40)**: the animals story finishes around S1 frame ~3600; just before that the animals disappear. That disappearance is correct, but it should be a **3 s FADE OUT**, not a pop. After that there is no need to keep playing: the **"lights out" sequence should begin from around frame 3800** (shorten S1 / move lights-out earlier). → Codex job 168.
- **Gobo timings** are arbitrary for now; when made, the shadow scenes will probably be ~60 s each.
- **The 12:19 local editor crash**: Python access violation during a Codex tool call (Codex's fault, not Gary's viewing).
- **S1 ending (Gary ~13:30)**: NO shrinking animals. Instead, around ~3600 the CAMERA PANS over to a WING in the corner where a SMALL FIRE has started (the animals vanish off-camera during the pan), then lights out from ~3800. → Codex job 169 revises job 168.
  - Gary: "and then we close out": after the hold on the fire, S1 closes out (lights out, then the end). That matches job 169.
- **Gary priorities (10 Oct ~14:00)**:
  1. **I2/I3 back walls** (job 144).
  2. **Chandelier** (the P06 part, candles, swing).
  3. Ending: LOWER, it needs Gary in the studio.

  If time after:
  - **S3 MetaHumans: LONG, dark + grey hair, messy and unkempt, on ALL S3 figures** (incl. the crowd copies).
  - **Fires turn a cool bluish grey** (the S3 fires).

## Gary, 10 Oct ~19:00 (his words, targets confirmed)
- **The gold particle cloud** seen in the P06 chandelier still (176_05) is a LEFTOVER from preparing Scene 6, NOT the P56 candles. Ignore it (Gary may delete it himself). Do not treat it as candle evidence.
- **3D stage front (opening, main/front stage):** in the wide stills Gary sees the uplights but NOT the new 3D front geometry (likely in the dark). If the pieces are there, **they need uplights too**.
- **P06 sun disc (end of the passage):** not visible in the still. **The sun disc should be small enough to fit in the end window of the passage.** (Resolves the 0.5 deg vs 1.22 deg question: size = fits the P06 end window.)
