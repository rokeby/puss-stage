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
