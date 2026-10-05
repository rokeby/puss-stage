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
