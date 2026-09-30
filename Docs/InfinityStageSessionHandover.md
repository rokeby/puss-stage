# Infinity Stage — session handover

**Current as of 30 September 2026, 17:00.** Supersedes the 25 September version.
Written by the conductor across an overnight run and a full day with three streams
(Rig & atmosphere, Soft goods, Look & camera) plus Wing materiality.

**READ SECTION 5 FIRST IF YOU ARE PICKING THIS UP TODAY.** The ~1 Hz stutter is
gone as of 16:47 and **nobody knows what removed it** — narrowed to two candidates
with a pre-registered test not yet run. It also carries a correction to a claim this
document itself had been making all week (*"the rhythm survives on a virgin
editor"* — false; that editor was 85 minutes old).

**AND GARY DELETED ALL THE LANDSCAPES AT 16:36**, saved. Verified: `strings -a` on
`L_InfinityStage_V1VerticalSlice.umap` returns zero matches for "landscape". His
words: *"I just deleted the landscapes as I don't need them any more."* The floors
Rig built today survive (P02, P03's 535.6 m oak plane, P05, P06). **P03 did not lose
its floor — it lost about 10 cm of height**, because the Wet Ground landscape sat
above the surface beneath it.

---

## 1. THE HEADLINE

**The show walks end to end for the first time.** Gary played it through on 29 Sep
and confirmed: *"works end to end in terms of operator"*. Every segment is
reachable. That was the day's blocker and it is gone.

**Show length is now 16:49** (1009.4 s), up from 13:17.6, because Scene 1 was
restored to its full 210.8 s and Scene 4 grew to hold the hangar rise.

---

## 2. WHAT IS NEW AND WORKING

### The Opening

- The **baked drape is placed** at the front of the stage with a stalls camera cut,
  replacing the old fire-safety curtain. Gary: *"the animation, the feel, looks good"*.
- **It falls.** The fault was a `running = False` flag on the GeometryCache
  component, which meant Sequencer never advanced it — it spawned, hung, and froze
  on frame 0. Proven by reading bounds back at frames 10/150/350 from disk.
- **The velvet still reads flat and orange.** Diagnosed as the LIGHT, not the
  material: the fold crests facing the house lights are bright and the troughs
  dark, which is the correct way round, and the same material read the same on
  28 Sep. Today's lighting is frontal and floods it. Rig's drape lighting is
  queued; the 28 Sep look is the reference.

### Transitions

- **Five transition drapes are placed**, one at each of Passages 2–6's mouths,
  each bound to its own stalls camera by tag. The fire-safety curtain is keyed off.
- **Five stalls cameras are placed**, carrying the Opening's exact seat (1400 cm
  back, +150 up, pitch +14°, 15 mm) to every mouth, derived live rather than typed —
  so P02 gets its 22.908° yaw from its bent route.
- **Portals are enabled at all six mouths**, with stage front, which is what makes
  one curtain bake serve them all. **S03 is FRAME ONLY** — Structure 03 has no
  ground, so there is nothing to build a stage front from.
- **The design settled**: the interaction happens ON the curtain (60 s+ of
  boy-and-cat shadow play), and it falls at the END, revealing the passage.

### Scene 4 — the hangar

- **A hangar exists and you can stand inside it**: 60 × 20 × 30 m, walnut
  herringbone floor, black-metal walls and roof, a 12 m lattice, ghost light and
  14 practicals.
- **v2 implements Gary's sketch**: the WHOLE BOX hangs below the passage floor,
  hinged 5 m ahead of the camera, and **rotates up as one thing**. It rises
  assembled and dark over about 15 s with only the ghost light glowing inside, so
  its glow breaks over the lip before the room arrives. Then lights strike, the
  roof swings over, the lattice flies in.
- **The walls' inward swing is dropped** — that was the thing that read as a box
  closing around you rather than a world unfolding.
- **The speed dial is the Hangar Fold section's Time Scale** in `LS_DevScene_04`.
  1.0 or faster is safe; slower needs `scene4_fold_nest.py` re-run.
- **Scene 4 is Dog Gaze** (applied 30 Sep 01:55): Puss keeps camera ownership, so
  peering over the lip and looking up at the stars are the dog's movement, live,
  in sync with the robot.
- **v1 is kept unreferenced** with a one-command revert.

### Lighting

- **P04/P05/P06 have baseline lighting**: 1521 lamps rewritten in place, GUIDs and
  positions kept, **shadow casters 1643 to 612**. P01–P03 fingerprint-proven untouched.
- **Six blinking gobo spots placed** across P02–P06, reproducing the one Gary
  praised in P01 — with **deliberately varied lens-to-gobo distance** (0.9 m to
  5.5 m) so each shadow has a different character, from vast and soft to small and
  hard-cored.
- **The hangar's upper volume is lit**: three shadowless uplights raking the far
  wall, and 24 emissive lattice bulbs. **At 30° of look-up it reads; at 48° it is
  still black** (grazing light on 4%-reflectance black metal).

### Floors and structure

- **Walnut on the boards** across all five passages with ground.
- **Steel grooves are real geometry** — recessed U-channels in each slot.
- **Floor material is unresolved.** Gary rejected the plank articulation
  (*"the floorboard like slats don't work great, we only needed the metal grooves"*).
  Options A (continuous herringbone) and C (dark waxed lacquer) are rendered and
  with him.

  **AND A MEASUREMENT THAT CHANGES WHAT THAT DECISION IS: THE GROOVES ARE NOT
  VISIBLE FROM EYE HEIGHT.** He approved widening them 8 cm to 16 cm; done across
  all six floors, it changed **0.05% of pixels** from the standing and rhythm
  views — and a difference image shows even that was temporal noise on the wing
  cards, not the floor. Only the close view down a slot changed (13.9%).
  **Because the slots start 150 cm inboard of each wing, under the wing bases.**
  So **width was never the legibility lever — `SlotInboardCm` is** (about 380
  would bring them toward the cat line). **As things stand his A-vs-C choice is a
  judgement about BOARDS, not about grooves.** The widening is harmless and stays;
  it simply achieved nothing visible.

### Build

- **90 passing / 0 failing / 90 total. THE SUITE IS GREEN FOR THE FIRST TIME**,
  up from 84/1/85 at midnight, and **still 90/0/90 after patch G3 at 07:06**.
  **Nine patches applied across six build windows**, every one verified linked by
  UTF-16 string literal in the DLLs rather than by exit code. Zero hot-reload
  leftovers.
- **G3 is the shape a verification should take.** Its marker was proven ABSENT
  from all three plugin DLLs before the build and PRESENT after, in both the
  plugin and the test DLL — which distinguishes "these binaries are the new code"
  from "these binaries are merely consistent with it", something an exit code
  cannot do. And the automation warning count stayed at **29, identical to the
  patch-H baseline**: the noise floor was shown not to move, not just the tally.
- **ALL SIX `SavedFixturePIE` FAILURES WERE FIXTURE FAULTS. NOT ONE WAS A
  PRODUCT FAULT.** Four came from the rehearsal-mode flag the conductor set in
  the saved level on 29 Sep morning; one from curtain keying the transition
  redesign had retired; the last was caused at 01:00 on 30 Sep by a stalls camera
  the reverse assertion did not know about. **The transport was right every
  time.** The test was measuring a world that kept moving underneath it.
- The last red — *"Reverse navigation restores the retained Scene 1 exit camera"* —
  was patch F's own blind spot: F branched the **forward** Interaction assertions
  on `bInteractionAuthorsCut` and left the **reverse** one asserting the retired
  retained-camera behaviour. Patch H (`10d3244`) corrected the assertion, not the
  product. Diagnosed by a Codex agent, verified first-hand against the 04:00 log
  by Soft goods before the patch was written.
- Every fix also added a log line, so the test now names **which** camera it got
  instead of reporting a bare `false`. It is becoming a test that explains
  itself, which is exactly what it was not the six times it misled us.

---

## 3. DECISIONS GARY MADE (his, not inferred)

| Topic | Decision |
| --- | --- |
| Transition curtain | A thing in the world, not a lens wipe. The interaction happens ON it; it falls at the end. |
| Hangar arrival | The whole box rises from below the horizon, hinged at the mouth. Assembled and dark, about 15 s. |
| Camera at the rise | Option C's image, but the look-down is **the dog's**, performed live — not a keyed track. |
| Horizon illusion | Dropped — irrelevant once the curtain is at the passage end. |
| The stars | **A glimpse of open sky between the curtain falling and the box enclosing is a BEAT, not a fault.** |
| Scene 4 ownership | Dog Gaze. Puss keeps the camera. |
| Fold lighting | Light it — practicals strike before the walls rise, so the lamps ride them up. |
| Mechanical-rig lighting | *"The passage rig again"* — the lattice carries the passage gridiron's own fixture housings. |
| Grooves | Widen to 16 cm on all six floors. |
| P01 casters | Apply P03's recipe — fill lights shadowless, key lamps keep shadows. |
| Portals | Enable at all mouths, full stage front. |
| Scene content | **Nothing in any scene is precious.** S01/S02 come from Klara later; S04–S06 are open. |
| Hangars | Build all six; **make them RESIZABLE**, since scaling to fit later content is the whole job. |
| Cloths | Bake freely. Structured hanging profile, the good fall already achieved, a couple of versions. |

---

## 4. OPEN — NEEDS GARY

1. **Floor: A or C**, once he has seen real grooves.
2. **The robot's own body pitch range.** Nobody here may command the GO1. Only the
   operator with the remote can measure it. `PitchRangeDeg` is the knob that
   matches the projection's look to the robot's once known.
3. **Scene 3's true length.** He said *"isn't done yet, will eventually be about
   3–4 min"*. It currently plays 65.5 s.
4. **The transition seat**, once the mouth lanterns light the curtains.
5. **P03's mouth** — frame-only, no stage front. Accept, re-bake against its
   landscape, or give Structure 03 ground.
6. **The pleat/pile trade**, if the hem-guide sweep cannot resolve it (see §6).

---

## 5. THE FRAME-RATE STUTTER — GONE AS OF 16:47, CAUSE NOT ATTRIBUTED

**The ~1 Hz rhythm is not there any more.** Measured 30 Sep 16:47 in a fresh
editor, four 60-second phases with a 5-second settle, cluster starts counted
(`Saved/CodexStructure/stutter_abab_164704.json`, commit f3afebf):

| phase | cluster starts / 60 s | spikes | max |
| --- | --- | --- | --- |
| P1 — Master playing inside P05's section | 4 | 8 | 102 ms |
| X1 — Sequencer closed | 2 | 2 | 65 ms |
| P2 | 3 | 5 | 147 ms |
| X2 | 2 | 3 | 137 ms |

**Median gap between starts 3–59 s: no rhythm.** Several "starts" sit at
t ≈ 0.05 s, the first frame after a phase switch, so the true rate is lower still.
**Against the same definitions applied to 29 Sep's editor-only files: 23–58 cluster
starts/min and 53–265 spikes/min.** Mean frame **16.8–17.8 ms** now against 19–35 ms
then.

**THE A/B PROTOCOL'S 90% CRITERION WAS NOT MEASURABLE and Rig said so rather than
filing "not decisive"** — you cannot show a 90% reduction against a baseline of
nearly nothing. Verdict fields 0.50 / 0.33, with the reason recorded.

### What removed it: TWO candidates, narrowed from five by Gary's own timeline

**Gary reported the stutter in PIE on the AFTERNOON of 30 Sep**
(`Docs/Conductor/RUNTHROUGH_NOTES_2026-09-30.md`): *"there's a regular stutter still
which really needs solving."* **Anything that changed before that cannot be the
fix.** That kills three candidates outright:

- **The power plan is REFUTED as the fix.** Switched Balanced → Ultimate Performance
  at **30 Sep 01:50** — hours before he saw it. It may explain part of the 29 Sep →
  30 Sep mean-frame improvement; **it did not remove what he is complaining about.**
  **Do not spend a run switching it back.**
- **Code landed before his run-through: refuted**, same argument.
- **"Nothing baking": refuted** — `final14` was still baking while he complained.

**Only three things changed between his complaint and the clean run:** final13 going
in at 16:21–16:23 (which **adds** content), **Gary deleting all the landscapes at
16:36** (~2,950 grass components), and **the editor being force-closed and relaunched
at 16:44:50** — age reset from ~9.5 hours to ~2 minutes.

**So it is the landscapes or it is editor age.** The consequences differ sharply:

- **Landscapes → permanently fixed**, by deleting something Gary did not want anyway.
- **Editor age → it returns every session**, and he meets it again in rehearsal.

**THE DISCRIMINATING TEST, pre-registered and not yet run:** re-run
`stutter_abab.py` late in a session after hours of normal work, landscapes still
gone. **Rhythm returns → editor age. Stays clean → the landscapes.** Report the
editor's age when it runs; an inconclusive late run beats a confident early one.

### CORRECTION: "the rhythm survives on a virgin editor" was FALSE

**Earlier versions of this section carried that line, and it was wrong.** Checked
against `Saved/Logs/PussStage-backup-2026.09.29-22.41.14.log`: the session opened
15:07 local, and **its first MCP dispatch — `virgin_1`'s own call — was at 20:32:12
UTC. The editor was about 85 MINUTES OLD.** "Virgin" meant **no scripts had run**,
not freshly started.

**So `virgin_1` weakens "our scripts leak" and does NOT weaken "editor age".** No
fresh-minutes editor was ever measured on 29 Sep. **The handover's own "a restart
helped materially: p95 49.6 → 34.2, slow frames 33 → 13" is exactly
`editor_pie_off → virgin_1`** — which is the restart effect, recorded without being
recognised as one.

**Rig found this by going looking to be wrong about their own claim.** It is the
single most consequential correction of the day.

### Also refuted, at no build cost: the celestial rig

**`ApplyCyclePhase` was the leading suspect** — it rewrites sun, moon, sky and fog
unconditionally, and is reachable with PIE off. **Refuted by construction:** the
celestial rig never ticks (`CelestialRig.cpp:49`), its only per-frame editor path is
the Master's Passage track (`MovieScenePassageTrack.cpp:187`), and the Cue Desk
timer is one-shot (`CueDesk.cpp:1531`). **In the P phase the Master calls
`ApplyCyclePhase` every frame and there is no rhythm.**

**So patch C (`2026-09-30_C_celestial_write_only_on_change.patch`) is DEMOTED: a
harmless write-reduction, not a stutter fix.** It stays in the build queue because
it applies cleanly and removes work, not because it fixes anything.

### Still true, still unmeasured against the current state

- **The GPU is flat** — 14.8–15.5 ms, max 17.2, while CPU frames reached 113 ms.
- **Every thread inflated together** on a spike, GPU unmoved.
- **The per-process sampling CANNOT see what we were looking for**: spikes are
  40–100 ms and the sampling interval was 250 ms. That ruled out a **sustained**
  competing load and nothing else. It was carried as "ruled out" and should not be.
- **Ruled out by measurement earlier, and not re-tested since:** cloth simulation,
  the celestial world-walk, wing motion, all 432 flicker light functions, the shadow
  cache, every dynamic shadow, lights-per-pixel, GPU contention with MHFat, timers,
  scene captures and reflections, the Go1 socket, fog, the structure kit, every
  wing, and PIE itself.
- **Suspending Scene 3's head cloths is worth about 6 ms a frame and three-quarters
  of the slow frames.** Baking rather than simulating them is the real win and is
  still not done. **Unaffected by today's result.**

### WHAT GARY ACTUALLY CARES ABOUT IS STILL UNMEASURED

**His complaint was in PIE. Every number above is editor-only.** A 60-second PIE
cluster count under the same definitions is the check that would mean something to
him. **Take it free on the next PIE session — do not schedule one for it.**

---

## 6. THE OVERNIGHT RUN — RESULTS

### Built and passing: 90 / 0 / 90 — GREEN

Two more build windows after the first. **Patch G: `AInfinityStageArrival`.** The
hangar's rise now **starts while you are still walking**, driven from Master time,
and hands to Sequencer at Scene 4's first frame **with no seam** — one curve read
by two evaluators at negative sequence time. Measured at the boundary: the Arrival
says −82.119°, Sequencer says −82.119°.

**Patch G2:** the Arrival also drives the backcloth, so **the cloth finishes its
fall inside the scene** instead of freezing six seconds short at the boundary.
That matters because Scene 4 is Dog Gaze — peering over the lip at what you just
walked through is the look the staging invites, and it is the one view that would
have seen a pile stopped in mid-air.

**G failed its first build on one line** (`GetActorRelativeRotation` is not a
member of `AActor`). Reverted rather than patched, fixed by its owner, rebuilt.

### All six scenes have a hangar, from one parametric builder

Dimensions, layout, switches, exposure and **beat timings** all driven by numbers —
a taller box rises more slowly, automatically. **Scene 3 was built AROUND its cast;
nothing moved.** Scene 5 is 200 × 150 × 50 m. Scene 6 has no roof. **None is
nested**, so none affects the show until you approve it.

**And the lighting scales too**, after Scene 5 first read as a dark void: rails and
uplights placed by pitch and margin, glow lights riding every Nth bulb past a
budget. The proof that the generalisation is sound is that **Scene 4 still
reproduces exactly** — 115/115 pieces at zero error.

### Also landed

- **Mouth lanterns at all five transitions.** Every mouth was black; they now read
  at the show's own exposure with the drape lit for the shadow play.
- **The lattice reads as architecture** — legible pixels in the upper frame from
  0.06% to 9.84% during the sweep-up, and unchanged after, so the fix is confined
  to the moment you described.
- **P01's shadow casters 338 → 99**, show-wide 618 → 379, every light still
  enabled. Your blinking spot at Wing 041 deliberately exempt, because you like it
  *for* its shadow.
- **Grooves widened to 16 cm** — and measured to be invisible (see §2).

### The cloths: the acceptance test earned its place

`final3_settled` **failed stillness at 15.7 mm against a 2 mm limit** and was NOT
placed. Its settle curve showed it needed about ten more seconds. **Without the
test it would have been imported to all six sites on the strength of looking
plausible.** Its sibling was stopped rather than allowed to fail identically.

**The breakthrough is `pleated_switch`:** the cloth hangs with its pleats as its
rest shape — true columns, 21 folds at every height, flare 1.00 — and **the rest
shape ramps to flat at release**, so the pile has no pleat memory. Proven at coarse
resolution by two piles from an identical hang: **a loose crumpled heap versus
regimented corrugated rows.** That is the thing that was thought impossible: the
hang you want and the fall you approved, from one cloth.

**UPDATE 06:50 — the full-resolution result split the verdict, and the three
bakes in that config were STOPPED.** `sw_b5_pswitch` at full resolution:

- **Hang: perfect.** 8 folds at every height, depth 99-100%, flare 1.00, bulge 1.00.
- **Stillness: fails, and getting worse.** 2.87 mm/frame, and the worst move per
  second **grows** — 1.4 to 2.9 across 30 s. It never settles.
- **Pile: fails.** Depth 1.34x the control, layers 0.70x, fold size 2.05x, centre
  of mass still sinking at 10 s. The side view shows a thin sheet slid out over
  the lip, not a heap.

**The measured reading:** cloth hanging in pleats its *flat* rest shape does not
want **stores bending energy**, and the fall spends that energy **unfolding the
cloth** — so it lands flat. The pleats and the pile were trading against each
other after all, just one level deeper than the first test could see.
`final6/7/8` were stopped rather than allowed to fail the same way at 08:00.

**The remedy, from measurements not hunches** (running since 06:35): switch the
rest shape only **part way** to flat (`REST_SWITCH_AMOUNT`), storing less
unfolding energy while leaving faint pleat memory — strips at 0.4 / 0.6 / 0.8 /
1.0, all with the hem guide at 0.7, which measured 0.08 mm/frame on a pleated
rest. Three speculative full bakes run in parallel at 0.6
(`final9_opening_a06`, `final10_opening_dense_a06`, `final11_backcloth_p04_a06`),
ready if 0.6 wins and re-baked if a strip picks another amount.

**The traveller (`final5`) also failed stillness — 21 mm/frame — and the cause
was LOCATED in the cache, not guessed.** In the hold the motion is at the centre
overlap, a 21 cm drift per second: the halves' lower fabric swung into each other
and **crossed by 1.57 m** against a 0.4 m design. At the end both stacks move at
every height, because a pleated rest shape pushes back against its bunched
carriers forever. Fix under smoke test: the rest shape **follows the carriers**
via Dynamic Mesh so the stack is at rest, and the track gap goes 0.15 to 0.4 m so
the pleats stop colliding — with a static-rest control at the same gap to
separate the two effects.

**UPDATE 07:15 — the traveller's hold is FIXED, and the split has a shape.**

- **The traveller's 21 mm/frame was the two halves COLLIDING, not the cloth.**
  Opening the track gap from 0.15 to 0.4 m took the hold to **0.06 mm/frame**,
  under the 2 mm limit by 3.5 s. `final12_traveller` is running at full
  resolution with a static rest, that gap, and air damping x10 applied only over
  the second **after the opening ends** — so the motion you liked is untouched.
  The stacks stayed restless at coarse resolution, but 27 cm quads cannot resolve
  7 cm stack loops, so that reading proves nothing either way.
- **THE 2 mm LIMIT NOW HAS ITS PROVENANCE WRITTEN DOWN**, which it did not before.
  At the stalls camera — 14 m, 15 mm on Super 35, 1920 px — **one pixel is about
  1.2 cm of cloth**, so 2 mm/frame is about **1/6 of a pixel per frame** and
  leaves no visible seam where the hold ends. For contrast, `final2`'s "bouncy"
  hang was about 8 mm/frame: 0.7 px per frame, and **20 px of swim over its last
  second**. That is the number Gary was reacting to when he called it bouncy.
- **The three jobs are not three cloths, and the split narrows accordingly.** The
  shadow play is not a separate screen: **the five transition drapes ARE the
  screens** — the Interaction plays on the drape, which then falls. So the drapes
  carry the same demands as the backcloth: hang, stillness AND a fall. The
  Opening is the only site that can trade stillness away, because its stillness
  is met for any bake by the one-tick hold on sample 0. **So the likely outcome
  is two recipes, not one and not three:** the Opening takes whichever amount
  gives the best PILE, and the drapes and backcloth take whichever gives the best
  HANG plus STILLNESS at an acceptable pile.

**THE SWITCH AMOUNT ACTS ONLY AFTER RELEASE — which is why the strips gate less
than anyone assumed.** The hold is a pleated rest plus the hem guide at 0.7 and is
**identical at every amount**, so stillness and hang read the same at 0.4 as at
1.0. The amount decides only the **pile**. And the P04 backcloth is judged on
stillness, hang and its SITE — pile short of the hinge, inside the boards, on the
floor — not on pile-against-`final2` the way the Opening and the drapes are. So
the backcloth bake stands or falls on its own numbers whatever the strips pick,
and a later preference is an optional re-bake rather than a gate. **This converted
a blocking dependency into an option and saved the morning's integration.**

**AS OF 10:45, `final11` IS PLACED AND INTEGRATED AT P04** — through stillness,
hang, site, at-rest and the rendered gate, with the section applied, the seam
measured clean and no loop past the end. Everything else is still unplaced: the
Opening and the five transitions wait on `final13`. `Docs/` carries the numbers;
the acceptance test has now
refused three bakes.

### Codex

Set up and working, **but not dependable**: it hit "model at capacity" twice,
including partway through drafting the Arrival, which a stream then wrote by hand.
**Use it where a failure costs nothing.** See `Docs/CodexAgents.md`.

---

## 6b. A DOCUMENT THIS PROJECT DOES NOT HAVE

**Operator's notes.** There is a growing set of things that are neither code nor
authored data: cues for the live performer. *"The cloth is still settling for the
first few seconds of Scene 4 — look back at it if the dog would."* What the dog
should be curious about and when; what the stick can and cannot reach (Gaze is
±18.2°, and the look-down and the look-up are opposite deflections, so they do not
share a budget). **Scene 4 is Dog Gaze precisely so these are performed rather than
keyed — which means they have to be written down somewhere, and currently they are
not.**

---

## 7. THINGS THAT WOULD HAVE COST DAYS

Recorded because each is a class of fault, not a one-off.

- **A test can silently measure the wrong thing — and six times running, the test
  was wrong and the product was right.** Every one of `SavedFixturePIE`'s six
  failures was a **fixture** fault: four from the saved level's performance mode,
  one from retired curtain keying, one from a camera placed after the assertion
  was written. **The tally hid it: 84/1 looked identical to 84/1 while the
  failing SET changed completely underneath.** Report assertion names, never
  tallies — and when a long-standing red keeps moving, suspect the fixture before
  the product.
- **Procedural layout can change between BUILDS.** `FRandRange(a,b) * FRandRange(c,d)`
  — C++ leaves the operand order unspecified, the compiler picks per call site, and
  editing the function flipped it. **288 of 337 floor lanes silently re-rolled, and
  every staleness guard reported clean.** The same bug existed in light replication,
  where **126 real lights** in P02's corridor depend on it.
- **A Sequencer spawnable's identity lives in its template.** `set_actor_location`
  on one does not persist — five drapes would have spawned stacked at the Opening
  with every check reporting success. And editing a *spawned* actor writes back
  into the template.
- **"Read-only" does not mean safe.** Four of five editor crashes were inspection
  scripts. A bad argument crashes as hard as a bad write.
- **A GUARD THAT CANNOT SEE WHAT IT GUARDS AGAINST IS WORSE THAN NONE, because it
  reports clean.** An actor spawned **transient** does not appear in
  `EditorActorSubsystem.get_all_level_actors()` — so every "no `ZZ_` actors left"
  check written that way is blind to exactly the actors that leak.
  `GameplayStatics.get_all_actors_of_class` sees them.
  **Found on 30 Sep when a sweep written the working way turned up two
  `ZZ_P04HistoryProbe` actors still live** — transient `SceneCapture2D`s with
  `capture_every_frame = TRUE`, **re-rendering the level every editor frame from
  about 15:00 to 16:30 UTC.** Discount or re-take any frame-time measurement from
  that window.
  **Two consequences.** A bench must destroy what it spawns **by object
  reference**, not by looking it up afterwards. And **the stutter's "census found
  zero SceneCapture actors" exclusion must be re-checked** — if that census used
  the blind call, it could not have counted the kind that leak, and it comes off
  the ruled-out list.

- **A REVERT COUNTS AS A SAFETY NET WHEN IT HAS BEEN EXERCISED OR READ, NOT WHEN
  IT HAS BEEN NAMED.** Risky writes were approved all day on the grounds that a
  named revert existed. An audit of all 47 revert-shaped scripts on 30 Sep found
  **four that WOULD FAIL** and several destructive ones that might:
  - one reads a record saying `steel_grooves: true` and **hardcodes `False`** —
    it would succeed into the WRONG state and emit its success marker. **A revert
    that fails is recoverable; one that succeeds wrongly is not**, because nobody
    looks afterwards.
  - **three have neither a record file nor a matching backup**, which makes the
    changes they guard effectively permanent while reading as reversible.
  - `hangar_revert.py` never requires `deleted == len(created)` — **exactly the
    113-of-114 seen in the S2 rebuild the same afternoon.** A stream verified by
    hand that nothing from the record survived; the script would have emitted
    `HANGAR_REVERTED` either way.
  Separately, a revert found by reading it rather than by needing it compared its
  read-back against the **current** keys instead of the **recorded originals**,
  so it would have refused to save at exactly the moment it mattered. Fixed, and
  its first live run worked.

- **"APPLIES CLEANLY" IS NOT "STILL VALID", and a held TEST patch is the most
  likely thing in this repo to be stale.** A patch held from 29 Sep applied
  cleanly to HEAD a day later, would have compiled, and **would never have
  executed one of its assertions.** The redesign it predated had not deleted the
  old lines — it had wrapped them in an `else` branch that runs only when an
  Interaction has no camera cut of its own. **So the patch's context still
  matched perfectly, while the branch it targeted was measured never to run.**
  Its premise was superseded too: it required the curtain within 250 cm of the
  camera, and the stalls drape now hangs about 1400 cm away.
  **Check a held patch against what the code now DOES, not against whether it
  applies.** And prefer deleting a stale patch to leaving it, because one that
  applies cleanly is read as ready — this one survived eight patches and three
  build windows by looking fine.

- **TO FIND OUT WHICH BAKE IS ACTUALLY IN THE LEVEL, GREP THE `.uasset` FOR
  `FileMD5`.** Unreal Python does **not** expose an import's MD5 —
  `AssetImportInfo.source_files` is not a property — so a script cannot recover a
  GeometryCache's provenance, and one stream reported it unconfirmable. **The
  saved `.uasset` carries the record on disk**: a `RelativeFilename` and a
  `FileMD5`. Grep for it, match the MD5 against the `.abc`, then match that
  `.abc` by SHA-256 against the bake archive.
  **Settled on 30 Sep in five links**: the asset's record named
  `CurtainDrop_Opening_final2.abc`; the file on disk carried that MD5; it was
  byte-identical to `final2_stage_v2.abc`; the cache frames 120–450 matched that
  bake's export window; and the Opening sequence holds frame 120.
  **Older caches predate the `<cache>_<bake_id>.abc` naming**, so the filename
  alone does not identify them — which is why the naming convention exists now.

- **Every MCP call costs a 40–80 ms hitch.** A session polling the editor
  manufactures the stutter it is measuring.
- **A GEOMETRY CACHE DECODES ASYNCHRONOUSLY, AND A CAPTURE AFTER A JUMP SHOWS
  THE PREVIOUS FRAME.** A jump requests a frame that is not decoded yet; the
  proxy keeps drawing its last decoded frame; only the **next request after the
  decode lands** shows the new one. On 30 Sep this made a placed cloth render as
  a full-height standing curtain after its fall, and it survived three wrong
  explanations: a second object in the `.abc` (refuted — one object, and a
  static-mesh import of the last frame agreed), temporal AA history (refuted —
  AA off changed the frame by **0.00%**), and a one-frame render lag (refuted —
  a later call **without re-posing** was still stale).
  **The component's BOUNDS were correct throughout**, because those come from
  always-resident per-sample data — which is why every number agreed while the
  picture lied.
  **The capture rule: pose, tick, RE-POSE THE SAME TIME, then capture.**
  "Repeat until it stops changing" is NOT sufficient and is actively dangerous
  here: repeat captures without re-posing sit on the stale frame and look
  perfectly stable, so a bench converges confidently on the wrong answer. This
  applies to any capture that *contains* a Geometry Cache, not only one whose
  subject is one.
  **Live playback is unaffected** — it re-requests every frame — which is why the
  Opening always fell cleanly in a viewport.
  **ONE SHOW-LEVEL CONSEQUENCE, unresolved:** after a transport **jump** (a
  rehearsal scrub, a reverse, or the Arrival's first evaluation after one) the
  cloth may show a stale frame until its chunk decodes. The operator scrubs in
  rehearsal, so this is real behaviour, not a bench artifact. A PIE transport
  jump, first frame only, would show it.
- **A SHARED MUTABLE FILE IS NOT A SOURCE OF TRUTH — it is a cache of the last
  thing that happened.** The backcloth section script defaulted its release time
  to 1.0 s, which was `final8`'s value: a bake that had been stopped and no
  longer existed. Every precondition would still have passed and the fall would
  simply have been mistimed. The conductor's fix — read it from
  `import_passing_bake.json` — was **the same bug one step later**, because that
  file is overwritten by every import, so a later Opening import would have made
  it describe the wrong cache. The working answer is to follow the **artifact
  chain**: placed actor, its cache, the Alembic it was imported from, that bake's
  own `DropBake/<id>.json`. Each link is immutable once written, so the number is
  derived from the thing it describes and cannot drift. A value that lives in no
  artifact — `BackclothLeadS` — is required with no default instead, because a
  default there is a guess wearing a number's clothes.
- **AND MEASURE THE NOISE FLOOR BEFORE TRUSTING A MEASUREMENT.** On 30 Sep the
  cloth pile was gated on numbers from **one run against one run**, on a chaotic
  simulation whose run-to-run variation nobody had measured. When it finally was
  measured — the same recipe, only the seed changed — it came back at **28%**,
  past a **25%** line written down before the test ran. Consequences, taken in
  full rather than argued around: **the U-shaped fold-size curve was noise** (the
  same recipe scored 1.58 on one seed and 1.13 on the other), **the switch amount
  is not shown to be a lever**, **0.6 is not shown to be better than 1.0**, and
  the pile half of the `final6/7/8` stop softens — while the stillness half, a
  *trend* over 30 s rather than a single draw, stands. Stillness and hang are
  robust to the seed; the pile was not.
  **Gary was right before any of it.** He looked at three piles and said all
  three were usable; the metric said two failed. **The metric was measuring
  noise.** The pile is now reported as "look", with numbers as context, gated by
  a recorded approval with a name and a date.
  **What made this honest rather than embarrassing was the pre-registration** —
  the thresholds and their consequences written down before the numbers existed,
  by the stream whose own morning it invalidated.

- **Measure before judging.** Four cloth bakes were rejected on look this week
  before anyone measured anything. Every bake now carries a number.
- **THE CAPTURE CONVENTION EVERY STREAM USED WAS SEVERAL STOPS DARK.** Setting
  `auto_exposure_method` to MANUAL plus an `auto_exposure_bias` — what we all
  called "EV 1.0" — is **not** EV100. On one frame: our convention gave a curtain
  p99 of **16** and looked black; the show's real setting gave **194**; and a
  capture with **no exposure override at all** was **byte-identical to the show**,
  because a SceneCapture2D picks up the unbound global PostProcessVolume by itself.
  **RE-MEASURED AND RESOLVED (30 Sep 02:30):** every Scene 4 reading was re-taken
  with no override and **stands, to 0.05 of 255** — because the override had never
  taken effect there at all (min/max brightness only act in an AUTO exposure
  method, and the hangar has its own bound volume). Only the Opening seat moved,
  by about half a stop. **So the 30° tilt cap rests on photometry as well as
  composition: 48° is black in v2 (p99 0.0), and at 17.8 s even 30° is black
  because the upright roof is unlit BEFORE the swing — while at 21.5 s, 30° reads
  strongly (p99 213). The look-up should therefore start WITH the swing at 18.5 s,
  not before it.** Also:
  a capture's `HiddenComponents` hides **primitives only, not lights**, so a true
  "before" frame must be taken before the light exists.

---

## 8. CODEX AGENTS

Set up 30 Sep. See **`Docs/CodexAgents.md`**. `Scripts/codex.sh` runs a Codex agent
in this folder, **read-only by default**. A real bug was fixed: `.codex/config.toml`
pointed Codex's Unreal MCP at port 8000 — **MHFat's editor, not this project's.**

---

## 9. STANDING RULES (unchanged)

- **Two authorities**: the Show owns cues and attachments; the Master sequence owns
  time and the camera.
- **Never Save All.** Snapshot to `Backups/Pre<Thing>-YYYYMMDD-HHMM` before
  mutating Show data, the level, or C++.
- **Never broaden the suite filter to `PussStage`** — it matches a bootstrap test
  that rebuilds AND SAVES the Master.
- **The build gate is machine-wide**: any open UE editor blocks any build.
- **The GO1 is read-only infrastructure**: no sudo, no installs, nothing outside
  `~/go1_bridge/`, and no command that could move the robot.
- **Permission boundaries are per-session.** A relayed approval is not a stream's
  own approval, and a conductor who can route around any session's guard makes
  every guard decorative.
