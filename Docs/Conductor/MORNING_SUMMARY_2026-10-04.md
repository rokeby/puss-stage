# Morning summary, 4 Oct (Conductor 4); built up overnight

## Done offline
- **P06 docking:** NOT cleared at +45 m (4c4264e). Docs/Conductor/P06_DOCKING_CLEARANCE_2026-10-04.md has the two options; option A (keep the end, tighter spacing) is recommended and was sent to W&T.
- **GL held patch (e1626f4, unbuilt):** adds a Scene-cue flag `bGo1DrivesCamera`. In a flagged Scene the dog's look carries across that Scene's cuts and the vamp re-cut. There are 2 tests; `git apply --check` passes on HEAD (measured).

## For Gary
- **FOUND [measured in a 3 Oct log; Scene attribution inferred]:** all six Scenes are still Dog Free Look in the data (camera_owner_plan.json, 30 Sep 17:42). Your 2 Oct "GO1 not engaged in Scenes" ruling never reached the Show. Should S1–S5 be set to Timeline?
- **S6:** should the dog's look carry across S6's cuts (apply GL), or keep "reset at every cut" (no patch needed, because S6 is already dog-owned)?
- **S6 "running forward":** the receiver only writes pitch and yaw (declaration-proven), so the forward run must be a keyed camera move.
- **P06:** W&T report you chose option A (end held at 27,640.28 cm, kit FV3P6-20261004-01, 20 offline controls). The pass beat is set per wing (IntervalToNext), not by distance (source-proven, InfinityStageCompiler.cpp:255-315; my earlier "+18 s is stale" and "880 cm" were wrong). W&T are asking you: (a) keep the 2 s beat, +18 s, camera walks ~214 cm/s; or (b) keep 250 cm/s and today's duration, a pair every ~1.7 s. Their runtime mechanism swing at the closer spacing is unchecked.
- **Scene exits:** the options page is Docs/Conductor/SCENE_EXIT_OPTIONS_2026-10-04.md.
  - A: the cat walks out (blocked in all six Scenes).
  - B, recommended: cut to the hidden door, about 8.6 s on screen.
  - C: the room dims and the lens pushes in.
  - The B tool (scene_exit_move.py) passes 57/0 offline (measured by me). It refuses to apply until your pick is written down.
  - Findings: doors are 65 m from the dock (not 60); S3's door is blocked by its backdrop; the Exit Black is metal black and should become velvet.
- **Flash events and black passage:** the tool is lighting_events_apply.py; design in Docs/Conductor/LIGHTING_EVENTS_2026-10-04.md. Its harness runs 27/27 (measured by me).
  - Today's engine can only fire flashes AT the camera's current position. Deep-bay flashes and far blinkers need held patch LD (unbuilt, apply-check clean).
  - **For you:** black mode on P04 turns the approved looks off in bays 1–6, so it is gated `gary_approved=false`.
  - The intensities (6000–9000 cd) are first guesses.
- **Lighting tune 4 (2a2b72c, offline):** the harness passes 17 positive / 23 negative checks (measured by me).
  - Low lights and practicals move onto the fence tree-post sockets.
  - 4 shadowed beams through the tarp tears, plus one flare sweep.
  - The P04 bays are now found by GUID, never by label.
  - **For you:** the beams come out as DIAGONAL shafts (62–65° off the fence). Practicals move up to 8 m (the B03 cage lamp).
  - Editor order: revert tune 3d → W&T place the fence → DRY → APPLY + tests → bay-3 trace in PIE.
- **Lighting scores P01–P06:** one tool plus one data file; plan in Docs/Conductor/LIGHTING_SCORES_PLAN_2026-10-04.md. The harness passes 54/54 (measured by me, against the final tune 4 code).
  - **The scores are proposals for you.** Judge P05 first (cool, clouds up-lit, shadowless), then P06 failing bay by bay, then the P01 ping-on cascade.
  - **Your calls:**
    - Should the P01 dark walk-in disable the house warmers?
    - P03 has no gobo asset: are the Rig Slash spots enough?
    - Should p01_hallway_pingon.py be retired (the scores do the ping-on)?
  - Every count is from the 29 Sep survey; the first DRY stops if one has drifted.
- **Long Opening (the full 96.4 s P01 track before P01):** plan in Docs/Conductor/OPENING_SEQUENCE_PLAN_2026-10-04.md; tool opening_sequence_apply.py; harness 55/55 (measured by me). No C++ change was needed.
  - **Phases** (defaults derived from the track):
    1. Unlit curtain to 1.5 s.
    2. Lights flicker on, 1.5–4 s.
    3. FOH swivel, 5.5–12 s.
    4. Light follows the music, 12–86 s.
    5. Curtain released at 74.9 s, after the last swell (67.5 s) and the start of the final quarter (72.3 s).
    6. Dark walk-in, 86–96.4 s.
  - **Tuning:** edit opening_timing.json, or drag an "OPN …" marker in Sequencer and re-run. Hand-keyed lights are protected.
  - **Your calls:**
    - P01 goes silent: what music should it get?
    - Disable the two house warmers? Until then the opening isn't dark.
    - Is "last swell" the one at 67.5 s or the one at 84.8 s?
    - Dark or lit move-in?
    - Look levels and footlights.
    - Silence before the music needs a builder change.
  - Run it BEFORE the P01 ping-on; everything after the Opening moves +81.4 s.
- **S6 bee swarm:** the review found 3 faults in v2 (bees never moved in the editor viewport, the sim ran on while paused, Niagara missing from the plugin's dependencies). These are fixed in held patch **v3** (apply-check clean, never compiled). v3 adds a no-Blueprint swarm actor, a brightness control for the release dim, and an 8th test.
  - A Python mirror of the sim passes all its gates and controls (measured by me).
  - Mirror numbers for 200 bees: median 133 cm from the target; a bee within 60 cm of the camera in 54% of frames.
  - Python can't build Niagara emitters in 5.8, so the runbook has click steps: Docs/BeeSwarmBuildRunbook_2026-10-04.md.
  - The sandbox map script opens a new map, so it must be announced first. The S6 write waits for your yes.

## Next editor session (start with "skip restore"; one run at a time)
1. Run the read-only light_guid_audit.py and its comparer, to check the FB force-close spill.
2. W&T: CR+CS (clouds) → FB (fence).
3. My tune 4: revert tune 3d → DRY → APPLY → both tests → bay-3 trace in PIE.
4. W&T: P1 → TK (_t5j + S1 gallery) → P6 (option A; once you pick (a) or (b)).
5. My S3 chain: beach v2 → marble → wave split → B03 → stills.
6. Long Opening: DRY → APPLY → both tests → PIE. It must land before any P01 ping-on.
7. Lighting scores: DRY per passage, P05 first. APPLY only after you've judged them.
8. A build window for held patches BS v3, GL and LD, if you want them.

## Everything waiting on you
- P06: (a) 2 s beat, +18 s; or (b) keep speed, ~1.7 s pairs (W&T asked you).
- Scene camera owners: S1–S5 to Timeline? Should the S6 look carry across cuts (GL)?
- Scene exit: A / B (recommended) / C.
- Black passage on P04 (it turns your approved looks off while on).
- Opening: P01 music, house warmers off, which swell, dark or lit move-in.
- Lighting scores: P01 house warmers, P03 gobos, retire the P01 ping-on draft.
- Tune 4 beams are diagonal shafts: OK?

## Gary's answers (4 Oct, Conductor 4 questionnaire; his own words where quoted)
- **P06 pace:** "Timing not final, whatever is cheaper" (relayed by W&T). W&T took (b): the end and duration are held, and a pair passes every ~1.71 s. Nothing downstream moves.
- **Opening:** the curtain falls after the 67.5 s swell, then a DARK move-in (the defaults). P01 is silent for now.
- **House warmers:** OFF for the opening ONLY. (They are P01 Wing 001 Show lamps, so "only" needs a distance strike-on rather than a disable; being built.)
- **Scene exits:** "It's a door but the curtain hangs over it and we have a 1min cat boy shadowpuppet scene on it first, just block for now." So each exit = a curtain over the door, a ~60 s shadow-puppet scene played on it, then through. Blocking only. Options A/B/C are superseded.
- **Scene cameras:** "Keep all camera locked and let dog freelook be optional." All six Scenes go to Timeline (including S6). Dog free-look is an operator option (Force Dog is already allowed in Scenes, declaration-proven). GL patch PARKED.
- **Black passage:** P06 bays 2–10 (not P04). It must be re-keyed after W&T's P6 interleave lands.
- **Lighting:** tune 4 diagonal beams OK; P03 rig spots stand in for gobos ("There will be more gobos but for now can place placeholder or nothing"); the old P01 ping-on draft is retired; judge the scores on P05 first.

## Editor session 4 Oct ~10:25 (Gary restarted UE)
- Light-GUID audit (read-only, run 20261004-102539): 274 cues, 2,717 lights, all UNCHANGED against the baselines, and all 20 outside-target hashes match (measured). The FB force-close left no spill. The editor slot went to W&T: CR+CS → FB.

## Afternoon 4 Oct (editor live)
- W&T, done and verified:
  - CS: P05 skins stain-free.
  - P05 ComponentBudget 64→128 (conductor approval; 82 components measured).
  - CR -04: P05 clouds.
  - FB: P04 fence, 47 props.
  - P1: P01 SaltFormation → rococo L.
  - TK: 406 sides, 5 cm boards + inset + S1 gallery + P06 lattice closed.
  - P6: 64 cues; length and duration held; pair every ~1.71 s.
- Tune 4 APPLIED:
  - The tune 3d revert kept the fence props (Gary: quick route).
  - The APPLY stopped on a late PPV gate, then FINISH saved it (Gary: finish with flare). Lens flare is 0.35 on the P04 camera; the engine default is 1.0.
  - Both tests passed.
  - Re-recorded run 20261004_161445: video + 6 stills sent to Gary.
- Light-GUID audits:
  - 10:25: 274/274 unchanged.
  - 12:13 vs 10:25, by cue GUID: 268 identical, 6 changed (P04 tune 4, expected), 9 new (P06 restored). All 2,878 attachment GUIDs unique (measured).
- Bay-3 traces: inconclusive, because the wings are NO_COLLISION (measured). The rays went to W&T for an offline intersect.
- Cueing: audit Docs/Conductor/LIGHT_SOUND_CUEING_AUDIT_2026-10-04.md. New stream brief Docs/Conductor/BRIEF_CUEING_STREAM_2026-10-04.md (Gary opening the session).
- **Scene cameras:** all six Scenes are now TIMELINE (run 20261004-122821; backup PreSceneCameraOwner-20261004-1228; outside hash same). Both tests passed. Dog free-look is an operator option: Cue Desk → View → Live Camera Owner → Force Dog, re-selected after each PIE restart.
- **P06 black mode APPLIED** on bays 2–10 (run 20261004-123343): 15 lights added, 81 existing lights disabled, shadow casters 130→117. Bursts were made denser on Gary's choice: 6 flashes in 2 bursts (offline schedule). Both tests passed.
- **Cueing stream:** Gary widened the brief to Sequencer as the directing surface:
  - A1: lamp binding + capture guard.
  - A2: Choreo nest per Passage.
  - A3: GO markers + fast-forward mute.
  - I approved it for review with conditions. The build window needs reviewed patches, a clear editor queue and Gary closing UE.
- **S3 chain APPLIED, each followed by both tests passing:**
  - Beach v2: OBJ axes measured as +x,-y,+z after a safe pre-destructive stop. FINISH saved one Megascans MI the level save had dirtied, and read back 9 actors + 6 figure feet.
  - Marble: the material setter "lied"; the tool now gates on read-back.
  - Wave split: the stale 3 Oct record was proven unapplied by hash; read-back OK.
- **Long Opening APPLIED** (run OPENING-APPLY-20261004-131449). The Opening is now 96.4 s; everything after it moved +81.4 s. Both tests passed.
  - The first try stopped mid-apply: BindingProxy.remove_track returns None. The tool now checks by re-listing. A Don't-Save restart (Gary's OK) cleared the in-memory partial; nothing was lost.
  - The house warmers still burn through the Opening until cueing build A lands (Gary keys them himself).
- **Cueing build A review:** NOT ready.
  - BLOCKER: a missing UMovieSceneTrack forward declaration.
  - MUST-FIX:
    - M1: hold-Right fast-forward overruns a hold.
    - M2: a stale hold eats Right.
    - M3: a hold bypasses the performance interlock.
    - Editor-only overrides break non-editor targets.
  - A1 also needs proof for possessable-bound lamps and handler-level tests. Findings were sent to the cueing stream.
- **P05 lighting score APPLIED** (run 20261004-132338): 724 attachments, 837 old lights disabled, shadows 2→2; blink-spot record acknowledged. Both tests passed. Gary: P05 warmth to be adjusted when directing (a note for the cue system).
- **Cueing build A BUILT** (20613f0, Gary asked me to close UE). Build fixes: a const-overload name-hiding fix in the tests, and the UniversalObjectLocator dependency.
  - Full InfinityStage suite: 129 pass, 2 fail.
    - Choreo.FollowsRetime is a real A2 bug (the section doesn't move on retime). Choreo APPLY is blocked until it's fixed.
    - SavedFixturePIE: the fixture expects 261 wing pairs; today's 9 restored P06 cues make 270. Fixture update owed.
  - After relaunch: SavedMasterMatchesShow and SceneCutBindingsResolve both passed.
  - Pending: cueing INSPECT/DRY, the M4 recipe, and the PIE checks with Gary.
- **Cueing builds 2 and 3** (Gary asked me to close UE each time):
  - Build 2 (5935992): SavedFixturePIE green via the FX fixture fix. FollowsRetime measured as a real A2 bug (passage 72000→312000, section stuck at 72000).
  - Build 3 (2684fb7): A2c makes MoveSection then SetRange. **Full InfinityStage suite 131/0.** Both single tests passed after relaunch.
- Choreo APPLY was handed to the cueing stream; M4 and the PIE checks with Gary follow.
- **Choreo crash caught and fixed:**
  - Build 4 (0506a2f) crashed Sequencer in MasterSequenceOpens. The cause was the saved Master holding Choreo tracks with no track editor. I reverted the Choreos on disk (PreChoreo-20261004-163459) and the restored suite ran 131/0.
  - Build 5 (e3999f1): A2e makes the track editor claim the Choreo track, plus the test MasterWithChoreoOpensInSequencer. Suite 132/0.
  - Choreos re-applied (choreo-apply-3, backup PreChoreo-20261004-173416).
  - **Headless full suite WITH Choreos: 132/0, no crash.** MasterSequenceOpens and SavedMasterMatchesShow are green.
  - Next: M4 (one lamp, Show backup, then revert), then the PIE checks with Gary.
- **M4 measured** (P01 House L, via a possessable): the keyed Intensity was withheld from the Show and the hand-edited Color was written. Caveat: the key never evaluated, so "would leak otherwise" is inferred. The probe's cleanup left 3 throwaway dirty packages; a Don't-Save restart (Gary's OK) discarded them. The disk Show was verified equal to its backup. After restart both tests passed.
  - Open: why setting the colour back did not capture, and why delete_asset on the temp sequence returned False.
- **Next:** Gary's PIE checks (M1 hold+FF, GO hold, S8 audio), set up by the cueing stream.

## Late night 4 Oct
- **Scene ExternalSound** (cueing; Gary: only S3 has the cellist): S1, S2, S4, S5 and S6 are now pausable and can hold GO; S3 is still DeclaredUnpausable. Both tests passed.
- **Exit block APPLIED** on S1, S2, S4, S5 and S6: each Scene is +71.64 s, with a curtain over the door, a puppet card, a 60 s hold, then the door move. Both tests passed.
  - extend_scene_playback's pre-K key gate was replaced by a measured key-carry check (tolerance: half a frame).
  - The occupancy check now skips pure light actors.
  - The live inside-box guard now uses oriented bounds (S2 is rotated).
  - Two Don't-Save restarts (Gary's OK) discarded the stopped attempts.
- **Bee swarm v3 BUILT** (3321216): all 8 BeeSwarm tests pass.
  - The suite ran 139/1. SavedFixturePIE is red only because its fixture assumed S1 is unpausable. The fix is held as cueing F1 (85166df) for the next window.
  - The swarm is NOT placed in S6 yet.
- **Retime audit:** Docs/Conductor/RETIME_ROBUSTNESS_AUDIT_2026-10-04.md.
  - Scene/Opening length changes are safe.
  - **Passage length changes are NOT**: keys stay authored while the wings move, pins past the end drop silently, and handoffs aren't rematched.
  - Tools with stale absolute frames: p04_bay3_trace, run_p6.json, the S3 family's (0,6240) guards.
  - Proposed: a RetimeEverythingFollows test, and a GUID-plus-offset rule for tools.
- W&T: P05 stills under the new score were sent to Gary. The P05 "boxes" are Structure 05 rig cubes (inferred). W&T is probing the P06 soft piece read-only tonight.
- **P06 soft piece solved (W&T, Gary approved the test):** it was parallax-occlusion smear on SM_CeramicTotem_01_L, not depth of field.
  - Fix: MI_CeramicTotem_01_L_Relief at HeightRatio 0 and POM steps 1. Stills FV3STL-20261005-02 show it sharp (measured).
  - Left APPLIED pending Gary's keep/revert; revert script p06/p6_pom_off_L_revert.py.
  - Other StageOpeningV2 relief pieces carry the same POM (inferred). A blanket rule is Gary's call.
- **P06 parallax OFF on all old pieces** (Gary: "Turn it off but also remove these ceiling wings in p06"):
  - 15 MIs changed. This includes M_Ceiling_bw_Front/Back, which P01's 24 ceiling tops share, so **P01's ceiling has parallax off too**. Revert: p6_pom_all_revert.py.
  - P06's 64 ceiling tops are hidden (bHasTop=False, data kept). Revert: p6_ceiling_off_revert.py.
  - SavedMasterMatchesShow passed. Stills FV3STL-20261005-03.
  - **Design item for Gary:** "ceiling needs a little thought".

## Gary, 5 Oct ~02:30 (his words, paraphrased only where marked)
- **Passage retime policy:** "Passage camera is basically always in dog gaze mode but on a track, so there are no camera moves in passage music bit, in non music bits like opening and transition, they should get nudged forward or backwards correspondingly, not stretch. The only thing likely to shift around is music and wing passage length."
  - So: SHIFT, never stretch. Non-music keys move with the boundary they belong to.
  - The RT test's known-gap TODO resolves to "keep + shift". Pins past a new end must move with the end, not be dropped.
- **Scene → Passage transition REDESIGN (supersedes the back-door exit block):** "At the end of a scene, we could shift out to wide view of its hangar and then a curtain falls that almost covers the whole screen, upon which shadow play happens. Behind it, the rig folds back down again leaving darkness, and we do a slight of hand where the new passage switches over (we switch to identical curtain at mouth of next passage, which is fully dark and therefore smooth transition while audience is distracted by boy cat shadow), and when that's done the curtain can drop, letting us onto the new scene. The key here will be letting the sleight of hand spawn in the correct order so we're not getting glitchy previews of behind the curtain."
- **Curtain sleight, Gary's answers (5 Oct questionnaire):**
  - The Interaction owns the curtain moment (option B).
  - Same red velvet drop in the hangar.
  - Fixed ~60 s shadow play, then a GO hold on the closed curtain.
  - "Scene 6 will be done differently, scene 3 is done this way". So it applies to S1–S5→I1–I5; S6 is separate.
  - Exit doors stay on stage, unused. The back-door exit block is to be REVERTED (doors kept; leaf-closed check).
  - Plan: Docs/Conductor/CURTAIN_SLEIGHT_TRANSITION_PLAN_2026-10-05.md.
  - Open: whether the Scenes keep the +71.64 s, which option B doesn't need.
- **P05 soft cloud (W&T):** NOT parallax. No P05 material has POM (34 checked, measured).
  - It was texture streaming not yet resident at capture: the same cloud is sharp in later stills (measured; cause inferred).
  - Gary chose "keep them loaded": never_stream on the 18 _CR02 cloud textures (about 100 MB VRAM, inferred). Revert: p05_nostream_revert.py.
  - Lesson for captures: stills right after a jump can be under-streamed, as well as under-exposed and unsettled.
- **Rig (Gary 5 Oct):** "All iron, but don't worry about the opening stage portal, that is not the infrastructural hulk, it's got to be changed from simple cuboid beam to a proper baroque stage front (using wings)".
  - All six Passages' rigs become underpass iron.
  - The P01/opening PORTAL is EXCLUDED. The portal shares the girder mesh slot (StructureActor.cpp:470-476), so the swap must decouple it.
  - New design item: a baroque stage front built from wings.
  - Plan: Docs/Conductor/UNDERPASS_RIG_KIT_PLAN_2026-10-05.md.
- **Editor time tomorrow (Gary):** AI editor runs go FIRST THING, ~60–90 min. After that the editor is Gary's, and I stay out unless he calls.
  - Morning AI queue: build window (F1, RT, S1 strobe rev2 b31073f), exit-block revert S1, shorten S1, curtain sleight I1 DRY/APPLY, look bench (incl. the glint light Gary approved via W&T), rig P05 prototype if time.
- **Wet paper test (W&T):** M_Wing_Billboard_Master_v3 is on Wing 008 R. The approach frames show darker, richer patches but NO glints, because no light sits at a mirror angle. Gary: "Add a test light", so a glint light goes in the morning look bench and W&T retake 7 frames.
