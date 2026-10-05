# Gary's PIE notes, 5 Oct (as he drops them; status per note)

1. **Waves in P01** (editor viewport screenshot): the 9 "S3 Wave Split" flats sit inside P01 at world x 3,665–5,335,
   y −500…500, which are exactly their recorded offsets relative to "S3 Hangar Root". Their attachment to the root has been lost
   [measured: probe_waves.json; cause inferred]. **Fix ready:** `Saved/CodexConductor/s3_wave_reattach.py` (DRY, then APPLY with
   a beach-landing gate). Runs when PIE is off. Owner: conductor.
2. **"There really doesn't look like there's a 5 cm edge on these wings"** (P01 PIE screenshot: the stone pillar wing
   on the left and the foliage wing behind it read paper-thin at a grazing angle). Routed to Wings & Textures, who own
   wing thickness (V2 = 10 cm explicit thickness; V3 = Front/Flap/Timber/Edge slots; the pipeline's 5 cm default is legacy).
   Status: asked W&T which profile these P01 wings were built with and whether the Edge slot renders.
3. On-screen in PIE: "RAY TRACING GEOMETRY – ALWAYS RESIDENT MEMORY EXCEEDS 20% OF THE BUDGET (97.6 MiB / 400 MiB)" and
   "GO1 NO DATA" (expected: the dog isn't connected). The ray-tracing line is a warning, not an error [inferred]; the
   new rig and tube ISMs add ray-tracing geometry. Worth a look if Lumen hardware RT is on.
4. **"Lots to do on P01 lighting but that's ok."** (Directing, his.)
5. **Stand-in curtain that falls at the end of the passage ("we had that once already").** Records: the transitions only
   ever had the velvet drape flying in and out with no fall (`Docs/ChaosClothCurtain.md:683-690`); a drape that falls at
   each passage end was listed as not built. Options put to Gary (stand-in drape falls / painted flat only / investigate);
   he dismissed the question for now. **Waiting.**
6. **Camera snap when the camera moves to the rising hangar rig** ("like a switch between two non-identically
   calibrated cameras"). The cat-bob pop was fixed by patch MR (cc1331e, 30 Sep). So this is something else, to be
   **measured** at the P01 crossing (height, FOV, roll, speed: Passage camera vs the Scene's Entry camera) when PIE is off.
7. **Girders visible, "nice"; might want them twice as thick and heavy later.** Noted, not actioned (BeamWidthCm 40 /
   BeamDepthCm 90 today; doubling re-hangs every TOP lamp again).
8. **"In the spaces between the girders the rig should still be lined with fencing?"** The FenceBay kit exists (W&T: open,
   tarp half/full/torn, door gap; placed in P04). The height question (ground to ~3 m / full height / options first)
   was put to Gary; he dismissed it for now. **Waiting.**
9. **Hangar top lights (detail):** "the lights at the top of the hangar — which are not going to be mostly very visible
   when scene lights come in — could be rectangular with two bars of light, similar to floodlight type." Proposal when
   picked up: swap the hangar top lamp bodies for a rectangular twin-tube floodlight body (emissive bars) and, if
   they are lights, rect lights with a twin-bar mask; low priority since the Scene lights dominate. **Not actioned.**

## Gary's answers, 5 Oct (questionnaire, his own clicks)
- Wing edges: **test the new edge material on one wing** (P01 pillar1 L) → W&T, offline prep; editor slot after PIE.
- Pillar2 R: **convert to V3** → W&T, offline prep.
- Rig fencing: **ground to ~3 m**, mostly open chain-link, some half/torn tarp, rare door gaps → held C++ patch UF being
  written (Underpass Fence part, FenceBay meshes, seeded variants), next build window.
- End curtain: **stand-in drape falls** at the end of P01–P05 as the hangar starts rising (P06 excluded) → tool being
  written offline (passage_end_drape.py).
10. **S01 → P02: Right arrow at the end of S01 jumps straight to P02**, skipping Interaction 1. "I need the transitions to
    be their own cue moment that I can move to with transport and examine." **Cause [declaration-proven]:** playback stops
    on the segment's exclusive EndFrame (`InfinityStageTransportController.cpp:1104`), which `FindSegmentAtFrame` (:1478)
    already counts as the NEXT segment, so Advance/Next (+1, :1167/:1173) skip it. Also, Sequences auto-play on Advance
    (:1184-1189). **Fix:** held patch TB being written: "held at end of K" → Right lands on K+1; transitions hold at
    their first frame (new `bAutoPlaySequenceOnAdvance`, default false). Needs a build window (editor closed).
    Workaround until the build: put the Master playhead at Interaction 1's start in Sequencer and use PIE Starts At
    Playhead (inferred to work; not tested).
11. **P02 "needs a lot of work, maybe mostly lighting; wings look quite flat."** Floor = lowest-hanging fruit: "the wooden
    waxed shiny floor, not the slats" → **P01's walnut herringbone** (his pick). Tool `p02_floor_walnut.py` ready (raises
    P02's four slabs above the boards and copies P01's slab material). Runs after PIE.
12. **Fog / flatness** ("a big blur of light … layered flat foggy lit pieces look quite bad … lack of reflectivity").
    He chose ALL tests: A haze only on hero beams, B low ground mist, C rake the wings, D lock exposure, plus E reflectivity
    (his addition). Restorable P02 bench being written (`p02_fog_bench.py`), two bays (~8 and ~15), stills per variant.
13. **"The car drive-by lighting is a good start in P02. Can the chain-link fence be a shadow actor?"** Yes: a masked
    chain-link panel between the car and the wings throws a moving diamond-mesh shadow. The rig-fence patch (UF) is
    already set to cast shadows (default true), and its panels sit on the column line, between the car (2400 cm out) and the
    wings. To check at build: the FenceBay material's masked shadow, plus the cost of a masked shadow from a moving light
    (VSM re-render each frame) [inferred].
14. **P03 "looks better than P02 (maybe the straight line is actually more effective than P02's curved path for
    depthiness)".** Noted against his earlier "keep the curve": a possible future P02 straightening (structural, needs a plan).
15. **P03 foliage props "look good but are in the wrong place"; Gary will move them.** How: in the EDITOR (not PIE), the
    move gizmo writes back to the Show for props too (guide §3.3); then save the Show and the level only. PIE edits are lost.
16. **Small holes in many wings, show-wide** → routed to W&T: a read-only hole audit, then a fill proposal (alpha close
    with a max area; patch in place, band-only, so the peel doesn't re-roll), with before/after crops for Gary.
17. **P03 floor "needs raising/replacing with the shiny one".** P03's slab WAS raised to +0.5 at 01:55 [measured], but
    it kept its matte oak herringbone. → the floor tool now takes "passage": P03 too and copies P01's waxed walnut.
18. **P03 also very flat; "the lighting here is pretty much just fog".** → the fog bench should run on P03 as well as P02.
19. **"We should basically never see the dusky horizon; the outer world of the stage can be entirely black, so the rig
    emerges to swallow us from nothing into its rigging light."** Asked where: his answer, "keep the possibility of a sky,
    but shouldn't S03 be 'artificial' lighting that creates the beach light?" → Plan: black void by default show-wide
    (the Celestial rig's sun/moon/sky-light intensities 0, fog colours black, stars off; values recorded and restorable,
    so the sky remains possible), and S3's beach light made by stage fixtures (an "artificial sun" key plus cyc washes),
    not the celestial sun. Runs after PIE; S3's lighting is a first pass for his review.
20. **TB transport patch is back (held, unbuilt).** Behaviour choice to confirm in PIE: Right from a held segment end LANDS
    on the transition and arms it (the view may not change); the next Right is its GO and plays it (GO 10 still holds).
    So repeated Right walks every segment once. `auto_play_sequence_on_advance` = false for rehearsal, true restores
    the old auto-play for performance.
21. **S3: "looking better but severely needs lighting and directing."**
    - **Marble:** shinier, wetter-looking, more light, so it reads as white walls → re-tune with s3_marble_tune.py (roughness
      down, specular up, albedo up) plus light. A look write: stills before/after.
    - **Stained hands on:** the side-wall hand prints (beat sheet :114-121; Fuser job 24 → decal atlas + placement table).
      Asked W&T for status.
    - **"Back door needs removal - it doesn't work"** → hide/remove S3's back door actor(s) (identify after PIE; earlier
      decision "Scene 3: no door").
22. **"Something broke transitioning into P04 — a mess of cat and wings before the next cue puts us into the more correct
    looking version of the passage."** (Screenshot: during Interaction 3 (S3 → P04), the stalls view of P04's mouth: the old
    drape pile on the floor, P04's wings in the wrong layout, and the black shadow-cat silhouette in front.) Known open gaps,
    first noted in the 30 Sep run-through: **G7** "Passage P(N+1) seen in its pre-section state when the curtain drops: its
    Master section starts only after the Interaction; wing mechanisms freeze outside their Passage"
    (CURTAIN_SLEIGHT_TRANSITION_PLAN:98) and **"the cat spawning in front of the curtain"** (RUNTHROUGH_NOTES_2026-09-30:11,35,39).
    Plan after PIE:
    - (a) M4 measurement at I3: P04 wing ISM read-back during I3 vs P04 frame 0;
    - (b) identify which cat actor shows during the Interaction and hold it hidden until the walk-in or the Passage start;
    - (c) the I3 curtain-sleight rollout replaces this view with the hangar wide → sleight → drop → walk-in.
23. **Strobe:** "overall effect works well" (P04 default strobe, 1 s, ghost ~1/3 s).
24. **"P04 does end on a curtain but it doesn't drop now; we walk straight through it."** Plus: dusk is visible behind it
    (→ the black-void note) and "the curtain should also reach the floor more". This is the 30 Sep "P04 Backcloth (baked)"
    in S4's Arrival backcloth slot, which has had an open render fault. Plan, within Gary's "stand-in drape falls at the end
    of P01–P05": revert the P04 backcloth (its own revert script ran once already on 30 Sep), then passage_end_drape S4 like
    the others. Add a check to the drape tool: the hem must touch the floor in the hanging pose (bottom ≤ floor top + 5 cm).
25. **Rig detail (P05 screenshot): "the X bars on the girder rig currently float off of it … should be connected and heavy.
    The lighting objects can sit on the rig and even overlap a bit to close the gap rather than floating."**
    - Cause, lacing [declaration-proven, Tools/UnderpassKit/build_underpass_kit.py:276-291]: the X bars are 6 × 1.5 cm,
      centred at z = ±19.25, so they only TOUCH the flange face (18.5) with zero overlap. The 500 cm column module is
      also stretched ~3.8× to ~19 m, so they read as a thin separate lattice. Fix: SM_UP_LacedColumn_v2 (a NEW asset, no
      in-place reimport): bars ~10 × 3 cm sunk ~1 cm into the flanges, batten plates at the ends, maybe 2 modules per
      height so the lacing isn't stretched; then set column_mesh per Structure.
    - Lamp bodies: the floor "cubes" are the scores' PRACTICAL bodies on the floor. Gary wants the rig lamps mounted ON the
      rig (on columns, piers, girders), overlapping slightly rather than floating. → A score/fixture placement change:
      snap the practical and TOP lamp bodies to the nearest rig member. Design needed; not today's priority.
26. **P05 clouds: "across the show, these kinds of small holes can be filled … ideally the crinkly edge of the second
    incoming wing should be fixed too, whereas the forefront wing has a nice rounded edge even though still quite
    detailed."** → Added to W&T's show-wide hole audit: an outline-roughness pass (flag crinkly cuts; propose a smooth +
    round at a radius that keeps the big shapes, like cv12's blunt curves), with before/after crops for Gary.
27. **Pending decision (asked, dismissed for now): drape hem.** The final13 bake's hanging hem is 20 cm above the
    floor. Lowering it puts the fallen pile 20 cm into the floor, so no single height passes both gates. Options:
    lower while hanging and lift during the fall (recommended); lower and accept a sunk pile; re-bake longer; leave the gap.
    Also before S4: the old "P04 Backcloth (baked)" ACTOR stays in the level after its revert (the revert only clears the slot
    and binding, with no backup and no read-back, and it overwrites the 30 Sep .reverted archive), so it needs a backed-up
    removal first.
28. **Passage width: "for the cloud sequence they are basically all bunched in the middle rather than flanking the stage …
    maintaining the structural visual of a stage. Should be easy enough to adjust by hand in the params."** By hand: select
    the wing cue → Details, top: **Rest Opening Width (Pivot-to-Pivot)** (+ Opening Centre Offset), per pair (guide §3.1d).
    P05 has 93 pairs, so a bulk tool is offered: set or scale the opening width for every pair in a Passage (or a range),
    with a record and revert, then re-materialize the Passage AND re-fit its Structure (the rig half-width and the lamps
    follow the pairs). Check the TOP-lamp and girder clearance after.
29. **Hangar rise and ceiling-rig drop are "nice but far too smooth".** He wants "the movement curve of something hugely heavy
    being wrenched up in a heave, its momentum shifting halfway through, falling forwards with a crunking thud". → A tool is
    being written offline (hangar_heave.py): a strain dip, 2–3 wrenched heaves with winch-catch stalls, a strained climb,
    then momentum tipping forward, a hard landing with a damped bounce, and a THUD marker. Start and end keys are kept
    exactly, so timing doesn't change. A preview plot (old vs heave) goes to Gary before any apply.
30. **Fence realism (not today):** the short bays "look pretty good", but "the big X grid is too perfect". Ideally build
    "the interlinked wire structure in 3D … good detail for reflection and shadow" (ref photo: galvanised chain-link,
    zig-zag pickets woven through each other, knuckled tops, a round top rail through the loops).
    Options for W&T:
    - (a) now-ish: a better masked texture: a woven picket pattern with knuckles at the crossings, a per-wire normal map, slight
      irregularity (sag, small diamond-size jitter, a few bent wires);
    - (b) later: true 3D: each picket a crimped zig-zag wire tube interlocked with its neighbours, knuckled selvage and a top
      rail. Probably Nanite (high tri count per bay) [inf]; real shadows and reflections.
    Routed to W&T as a backlog item.
31. **Seams are the priority** ("fixing the cues so that all the transitional moments are themselves visible"). Status:
    - **Scene → transition via the transport: FIXED and BUILT** (82035bd, suite 179/0). Right from a played-to-end segment now
      lands on the next segment (the transition) and holds it armed; the next Right plays it.
    - **Passage → Scene snap: MEASURED** (PIE, P01 → S1, scene1_crossing_pop_20261005.json). Last rig frame x 28750.7,
      z 133.0; first Entry camera x 28784.0, z 150.0 → **+33 cm forward, +17 cm up, a slight roll to 0, and a ~400 ms frame
      gap**. Fix: held patch CS ("crossing settle", 1 s: bob fades out, the pose converges to the route end at the boundary)
      being written; the gap is to be measured separately.
    - **Interactions 2–5:** the sleight refuses WALKIN_NOT_READY (no landed_s / minimum_end_frame; they were never prepared
      like I1). A readiness tool is being written.
32. **Beginning / end:** the end "is not yet implemented and needs to start tomorrow or Weds". Beginning: extend the stage
    forward so we start ON the shiny floor, not in the "audience"; forget the slatted wood, P01's waxed floor is better.
    Also make puddles and pools of slick, thick water or oil on the floor.
33. **Heave shake:** the heavy heave needs "a little bit of shake, coming up and on landing thud".
34. **P04 gallery mirrored-shift: CONFIRMED** (W&T probe FV3TKAUDIT-20261006-01, matches the pre-registered prediction to
    0.01 cm; the 15 controls show 0 error). L_v1 inner edge 35 cm into the walkway; R_v1/R_v3 inner edges recede 28.5 / 22.6 cm;
    R_v2 −3.6 cm. Cause: TK's lateral shift was computed in the raw-FBX frame (Y reflected) and added to Unreal Y.
    Gary: "save this til end of day too" → END-OF-DAY SESSION, with W&T's hole/outline kit:
    (b) corrected CV12B re-apply (recommended) or (a) tk_cv_revert. Take P04 "as-is" stills before it.
35. Short FenceBays imported (FV3FBS-20261005-01): SM_FenceBay_short_open, _short_door_gap, SM_FenceTarp_short_half,
    _short_torn, SM_FencePost_short.
36. **W&T correction:** the 4 Oct TK 5 cm run (FV3TK-20261004-02) ALSO used mirrored raw-frame shifts on 326 of 406 sides
    (P01 none). Predicted [inf]: inner edges off ≤2.45 cm (small); backbone edges up to ±13.6 cm (worst P02 Wing 022).
    The CR P05 cloud run had been placed correctly, then TK 4 Oct re-swapped 185 sides. Read-only audit probes are ready
    (~1 min each) → run them in the END-OF-DAY session before deciding whether to fix.
37. **END-OF-DAY SESSION plan (W&T):**
    1. gallery fix (b), FV3D-20261006-02, ~15–20 min; R_v2 allowed 16 cm out per Gary; fallback (a) revert prepared;
    2. TK 4 Oct audit probes;
    3. hole/outline kit per passage (P03/P05 first), 1–2 h. Take P04 "as-is" stills first.
38. **SEAMS, end of afternoon (5 Oct ~15:40):**
    - **Passage → Scene snap FIXED** (CS v2, 37eac9a, suite green). PIE re-measure, P01 → S1: last rig frame (28783.65, 0, 149.58),
      roll −0.004° vs the Entry camera (28784.01, 0, 150.0), roll 0 → **0.36 cm / 0.42 cm, down from 33 / 17 cm**. The 0.4 s stall
      at the cut remains (Master clamps one 400 ms frame: MaxUndilatedFrameTime) → separate Insights measurement.
    - **Transitions:** the curtain sleight is on ALL of I1–I5 (I2–I5 applied 11:17–11:18 local; tails 451/463/62/62). I1's PILE hold is
      fixed (the fall would have wrapped at 77 s). Right lands on each transition (TB).
    - Camera Pilot keying works with the settle (KeysInsideCrossingSettle test).
39. **Rig rise: the camera still snaps from cat view to the wider hangar view.** This is a hard camera cut inside the Scene. By-hand fix
    given: tick Can Blend on the owning Camera Cuts track (the Scene's or the nested shot's) and ease into the wide cut, ~3 s.
    Gary will try it on S1 and report the length; the conductor copies it to the other Scenes.
40. **END-OF-DAY SESSION, final order (W&T):**
    1. S3 wall probe (<1 min, read-only);
    2. P04 gallery re-place, FV3D-20261006-02 (~15–20 min);
    3. hand prints import + place (~20–30 min) + 1 PIE still;
    4. holes/outlines per passage, P03→P05→P01→P02→P04→P06 (~45–60 min). Runbook:
       DerivedAssets/FlatV3/Review_2026-10-05/holes/hf/RUNBOOK.md. 85 meshes; flags for Gary: cvl6 trims card tops
       (P02 SET16_L −37.8 cm, SET04_R −13.5 cm); 3 still crinkly; the P02 _C top borders are excluded.
    Before step 2: P04 "as-is" stills (conductor).
41. **Narration stand-ins (via Directing):** Gary confirmed S1 Animals / S2 Shrine / S3 Shore, start when the hangar lands
    (~4.13 s), and "Lengthen S2 to fit" (S2 is 31 s; the clip is 74.75 s). WAVs are in DerivedAssets/Audio/Narration_Standin;
    tool scene_narration_standin.py (12/97). Runs when the editor is free: extend S2 → Master rebuild → tests → narration DRY/APPLY → tests.
42. **Light-event on-screen print (Gary):** held patch LE being written (cvar InfinityStage.ShowLightEvents, a game-world
    OFF→ON poller with hysteresis, Show attachment labels, rate-limited strobes). Build in the end-of-day restart session.
43. **Opening FOH flicker/envelope stays PROGRAMMATIC from the music** (Gary gave up hand-keying it; the music will change).
    Re-run opening_sequence_plan/apply when Cameron's new music arrives. If Gary saved hand edits to LS_Opening_Curtain_Baked,
    reconcile the hash drift first.
44. **Opening music sketch 2** (Cameron, 95.5 s): analysed offline (swells 39.0/46.3/53.6/64.9/76.4 s; music starts at 7.0 s).
    Gary: curtain after the LAST swell (release ≈77.4 s, walk-in ≈84.9 s) and the FOH swivel follows the music (36–44 s).
    opening_timing.json is repointed (all moments still auto). Refit folds into the Opening reconcile when the editor is free.
45. **Walking music:** Cameron's 6 tracks converted (P01 73.5, P02 45.5, P03 40.2, P04 38.4 → padded to 48.4 s with 10 s of silence
    per Gary, P05 42.0, P06 125.0 s, which overruns P06's ~111 s). Passage lengths are KEPT. The swap tool is being written.
46. **Music, 5 Oct afternoon:**
    - Narration stand-ins IN: S1/S2/S3 at the hangar land; S2 extended 31 → 81 s.
    - Cameron walking tracks IN on P02–P05 (lengths unchanged; long silent tails of 131–144 s).
    - **P06:** Gary "Lengthen P06 to fit" → p06_tail_extend tool being written (+≈15.4 s tail).
    - **P01:** waits for the Opening's own rail (opening_own_rail tool being written).
    - **Opening refit to sketch 2:** Gary "yes, refit" (programmatic FOH overwrites his 14:02 FOH L/R edits, which are backed up;
      end kept at his 96.36 s).
    - The music-driven Choreo bar/§ markers and MM_Pnn analyses are now STALE for P02–P05. New analyses need 16-bit copies
      run outside Unreal.
47. **Opening refit DONE** (OPENING-APPLY-20261005-144820 + own rail OPENRAIL-20261005-144921): sketch 2 on its own rail.
    Flicker at 4.0 s on the gentle early swell (Gary); FOH swivel 36–44 s; curtain release 77.39 s; walk-in 85.8–96.36 s; end 96.36 s.
    Gary's 14:02 FOH edits were overwritten as agreed (backed up). **Walking music P01–P05 IN.** P06 waits for the tail-extend tool.
    Tests green. Editor handed back to Gary for PIE.
48. **Opening: the tuning section lasts ~20 s or more; the lights must not flicker until after it** (Gary, ~15:05). The 4.0 s
    "gentle early swell" is part of the tuning, so note 47's flicker is wrong. Sketch 2 analysis [measured, offline]:
    intensity is ~0 from 0–34 s apart from a small bump at 8–10 s (peak 0.22); the first real entry is at **36.18 s**
    (major change, strength 1.0; first onset 35.0 s). Not re-run yet (Gary: "don't run this now"). Music analyses
    imported (MAI-20261005-145425, b8cea61). Choreo song-marker refresh DRY refused on a dirty level (not ours).
49. **Opening flicker decided** (Gary ~15:15): **start on the entry** (36.18 s; the FOH swivel moves to the next change, 43.8 s);
    look **"Brutal with a bit of that strobe falloff"**: flashes up to ~3x nominal, black between, single-frame pops,
    each flash decaying over a few frames, longer dead gaps early.
50. **P02 re-light** (Gary ~15:10): the L/R lurid/theatrical beams "give a really foggy blur of light across the whole screen
    and make the wings look flat". Use the practicals (currently dead) and light the wings in those lurid/theatrical
    colours **from above**, or **uplight** some; **no light may shoot through from L to R**. Questionnaire: top wash +
    practicals + some uplights; **all of P02**; and **"also please straighten that passage"** (reverses the earlier keep-the-curve call).
51. **Walk speed to music** (Gary ~15:25): "P02 walk speed can also now be corrected after straightening to time of music, the
    prev placeholder length made it very slow". Measured: P02/P03/P04 Passages 180 s, P05 186.4 s vs songs 45.5/40.2/48.4/42.0 s
    (~4x slow). Questionnaire: **retime P02–P05 in one run, P02 after straightening; song + short tail for the crossing**
    (P04 keeps its +10 s pad). Tool being written (passage_retime_to_music.py); runs after P02 straighten, before P06 tail extend args are re-read.
52. **P02 floor** (Gary ~15:30): "P02 also needs waxed floor to be in shot and the slatted stage floor removed". The slats are the
    structure's Ground boards (InfinityStageStructureActor.h:113-160); the 10:35 walnut fix raised four slabs placed around the
    old bend, which will not fit a straight P02. Folded into the P02 straighten tool: boards off, walnut re-laid over the straight route.
