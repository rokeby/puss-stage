# Decisions waiting for Gary — 30 September 2026, 07:30

Every row leads with a **recommendation**, so a "yes to all" is a valid answer and
anything you disagree with is the only thing you have to read twice. Each says what
it **unblocks**, because several streams are idle behind these.

Nothing in this list has been decided for you. Where the conductor approved
something on your 29 Sep delegation — reversible, backed-up, non-creative — it is
marked **[conductor approved]** and named as mine, not yours.

---

## DECIDED 30 Sep evening (Gary, in the conductor session unless noted)

- **Show length is not a constraint:** *"no limits on length, all good for all things"*
  (asked about Interaction 1 growing to 25.5 s). This settles B0 option (1) in principle:
  lengthening Scenes 2, 5 and 6 to fit their rises is length he's fine with, though still
  gated on K and L being built.
- The border: keep at 10.2 m. P02, P05, P06: trim like P03 (P02 then "leave for now").
- Free dog look in all Scenes 1–6 (applied). Look **resets at every cut** (patch O).
- S4 arrival: lights and exposure dim together with the rise, from the curtain (re-key, plus patch P).
  Curtain 2 s earlier (confirmed in Rig's session). No picture sheet.
- Walk-in after the curtain instead of a cut: trial at I1 → P02, slow zoom 15→35 mm (patch R first).
- Wing mipmaps: P01+P02 applied. The blur persists "only while moving" in P02 and other passages; probing next.

## DECIDED 1 Oct morning — the hangar arrival and Scene 3 (Gary, conductor session)

- **The S4 rise timing is right** ("its dim lit form rises up and swallows the frame").
  Cameron will add a chain-rolling sound once each rise has a defined duration (Rig to supply).
- **The real lights strike only AFTER landing**, per scene, coordinated with Klara for S1, S2 and S4.
- **Scene 3 first.** The shore cast doesn't ride the box: they can appear while the landed hangar is
  dark, then a very bright strike (this settles B0b, option 2). Behind them, layers of wooden
  waves sliding back and forth. On the back wall, a painted backdrop (maybe for every hangar): a grey,
  foggy Atlantic coastline with one island, barely visible. Later maybe a shack, firewood, rocks or a boat.
- Velvet texture parked; the curtain stays plain oxblood B.

## GARY'S NOTES, 1 Oct evening

**Decided (Gary, via Wings and Textures' session, 1-2 Oct):** S3 hand prints come from FUSER (job
FuserQueue/24_S03_hand_prints_atlas); W&T then build the decal atlas + JSON placement table for Rig.
P02 is a FULL REDO: a chain-link fence overgrown with lurid plants; the ~60 existing P02 plant wings are
NOT rebuilt in V3 (card updated, add0a14). This supersedes the P02 card brief sent 1 Oct evening.

**Production order (Gary):** wings (new high-quality feel, placed in order) -> lighting ->
lighting FX -> other props -> other FX. (his words, condensed; conductor session) — NOT YET ACTIONED

- **Music.** P01 currently carries the opening-curtain music, which is wrong. The opening
  curtain is crucial and needs real timing and music decisions, not a flat lit curtain that
  falls. Soon. (Cameron.)
- **Drift onto the stage.** P02 drifts from the curtain onto the stage nicely (the I1->P02
  walk-in trial); P01 and the others still do not.
- **Transport.** Wants RIGHT held down to FAST-FORWARD through movement (to see transitions),
  rather than skip to the next part. (InfinityStageTransportController: C++, unowned.)
- **S03.** Shifting from AI-driven design to designing the camera angles himself. The white
  strike floods the L and R black walls and looks bad: needs a solution. S03 "looks rough
  still"; better with backdrop and curtains. Needs to edit the lights by hand, but the
  hangar is only "up" mid-play.
- **P03 wings** to be replaced: stones, pyres, folk horror (consistent with the P03 card).
  Some white staircases faintly echoing the windowed forms. Two L/R clean 19th-century
  white walls with lab coats / doctors' coats hanging, sinister, many shoes piled at the base.
- **Queued for Rig (nothing built):** (1) hanging birds on cables under clouds, real cable
  physics + cue-released drop, first use P05 — Docs/Conductor/PROPOSAL_HANGING_PROPS_CABLE_2026-10-01.md;
  (2) P04 rose-window GOBOS: Fuser tracery (FuserQueue/03_P04_gothic_tracery_colour) as light
  functions on P04 lamps ("rose windows for lamps is a great idea!" — Gary, via W&T); W&T supply
  greyscale masks under DerivedAssets/FlatV3/Gobos/, Rig the lamp/light-function side.
- **P02 wings** due a replacement (he couldn't recall which): per
  Docs/FlatV3PassageCards_2026-09-30.md:48 — Rousseau plants enlarged, alternating with a
  red thorny bramble/briar mass and brown biomechanical piping increasing toward the shrine.

## A. THE FOUR THAT UNBLOCK PEOPLE

### A1. Exposure on the approach — ANSWERED, and the premise was wrong
**He rejected all three options because all three tied the drop to POSITION ON
THE PATH. He wants it tied to THE RIG.** His words:

> *"I'm not really sure why the light needs to drop, or if it does so it should
> be quite slowly as the rig comes up. Right now it's as if the lights just
> switch off from the sky. It does make sense for the lights to start lowering
> as we pass through the cloth but it should happen over 5-10 seconds AS the rig
> is rising — almost as if it's the shadow of the rig, or the new exposure
> settings of adjusting to the rig's (brightened) lights."*

So: **5 to 10 seconds, not a switch. The cloth is the TRIGGER, not the event.
And it must be motivated** — by the box's own shadow, or by an eye adapting to
the rig's lights.

**FIRST CONSEQUENCE: it may not need authoring at all.** A box rising around you
physically blocks skylight. Rig is measuring whether that occlusion is real and
substantial at the stop across the rise. **If it is, the keyed drop is
duplicating a physical effect and the fix is to DELETE a key, not reshape one.**

**SECOND CONSEQUENCE: A1 and A2 are now one decision.** "Exposure adjusting to
the rig's brightened lights" only works if the lattice is bright enough to be
something an eye would stop down TO. That is exactly his *"it just needs to be a
bit brighter"*. So the 20 / 40 / 80 cd sheet coming from Rig answers a sharper
question than "which looks best": **which is bright enough that stopping down to
it is plausible.**

**Timing, for when it is authored:** the cloth releases at about −3.9 s and the
box lands at 16 s, so a 5–10 s drop starting at the cloth settles between about
+1 and +6 s — inside the first third of the rise, well before the landing. The
dark hold survives it, with the lattice as the thing seen during it.

### A2. The box rise — early, or the authored timing
**You have the picture** (`EarlyVsAuthored_forGary.png`), now with a measurement
on it.

**RECOMMENDATION CHANGED AT 08:00, AND I WANT THE CHANGE ON THE RECORD.** An hour
ago I recommended early release, because the authored hold measured **black** —
p99 of 2 at the +3 s angle, with glow only by +9.5 s, and you made Scene 4 Dog
Gaze so the look-down is live. Roughly nine of the hold's twelve seconds had
nothing lit to find. That was a fair reading of the evidence then.

**A measurement since has rescued the authored option, so I now recommend
AUTHORED PLUS THE LATTICE GLOW FADING UP FROM THE CUT.** Reason: it is what your
own words asked for. *"Keep the new box virtually unlit, only lit via an exit-sign
style light when we enter, before pinging the lights on when we're ready, in a
dramatic way."* The authored hold with the lattice lit IS that — you arrive into a
dark pit with the machine's own rigging glowing above you, and then the strike.
Early release deletes the dark hold entirely and arrives into a nearly landed,
already glowing box, which is a good image but a different one, and further from
the Tier 2 note you have repeated all week about wanting to feel **inside a big
machine** rather than in a wide dusky space.

**Early release remains a real option** and the sheet still shows it honestly: it
arrives in 4 s with the rise hidden behind the cloth while you walk, and it has no
dark-hold problem to solve because the rise is the thing you watch.

**ANSWERED 07:45 — the ghost light cannot rescue the hold. It is OCCLUDED by the
box's own floor.** The stop sits 471 cm below the floor plane at the cut and only
31 cm by +9.5 s, so the lamp and its whole 15 m reach are behind the floor slab
until exactly the moment that was measured from rendered frames. Two independent
methods — geometry and photometry — landed on +9.5 s separately. Removing the
lamp's reach entirely still gives at most 0.08 lux at +3 s against 1.6 lux at
+9.5 s; moving it to the mouth buys about 3 s of the 12. **No lamp inside the box
fixes this, and nobody needs to try.**

**BUT THERE IS ALREADY A LIT THING IN FRAME, AND IT IS DARK BY A DECISION RATHER
THAN BY GEOMETRY.** The lattice sits on the trough's open side, outside the floor's
shadow, with 6 of 24 bulbs in a look-down at the cut, 9 at +3 s, 12 at +6 s. It is
black only because its glow lights are keyed to 0 until +4 s — a fix for a leak
into the P04 approach, and that leak was a rest-state problem, so **a fade starting
AT the cut would light the hold without reopening it.** One measurement is in
flight: whether 20 cd on 9–12 bulbs actually reads at the show's exposure.

**MEASURED 08:00 — THE LATTICE READS, CLEARLY, AND YOU HAVE THE PICTURE**
(`LatticeGlow_forGary.png`). Benched by scrubbing the scene to +3 s so Rig's own
keys posed the box, not a hand pose — the root read −66.39° against −66.5°
expected, so the measurement is of the thing that will actually run.

| At +3 s, −15° look-down | p99 | Pixels above 40 |
| --- | --- | --- |
| Glow as keyed (0 cd) | **1** | 434, bulb meshes only |
| Glow at 20 cd | **112** | **59,900** (24,400 above 100) |

At −25° it still gives p99 44 with one row in frame. What reads is two rows of
three bulbs, each with a warm halo on the structure beside it: **the lattice
becomes a lit object in the pit rather than points in a void.**

**So the choice is now genuinely about taste, not about a dead option.** No new
lamp is needed — the fix is a timing change to an element already in frame, and
the fade curve and level are Rig's once you say yes. **Nothing has been changed:
what is lit at the cut is a look decision and it is yours.**

**Unblocks:** the same held re-key, and every scene's rise start.

### A3. The two-recipe cloth split
The three cloth jobs turned out to be two recipes, because **the transition drapes
ARE the shadow-play screens** — the interaction plays on the drape, which then
falls. So the drapes carry the hardest combination: hang, stillness and a fall.
The Opening is the only site with slack, since its stillness is satisfied by a
one-tick hold on sample 0.

**Recommendation: accept the split.** The Opening takes whichever bake gives the
best **pile**; the five drapes and the P04 backcloth take whichever gives the best
**hang plus stillness** at an acceptable pile. One cloth was never going to win at
both — the measurement says pleats held by a flat rest store bending energy, and
the fall spends it unfolding instead of heaping.

**Unblocks:** placing any cloth anywhere.

**A4b. WHICH OPENING CACHE — and the recommendation is nearly forced.**
Two candidates: **`final9`**, ready about 12:30, which **fails coverage by 0.615 m
per side**; and **`final13`**, about 15:30, which does not. **That 0.615 m gap IS
your own complaint** — "the curtain blocks only about 80% of the stage, light
leaks past both sides". **Recommendation: wait for `final13`.** Placing `final9`
would knowingly re-install the fault you asked us to fix, to save three hours, on
a day when nothing downstream is waiting on the Opening. Say if you would rather
see something sooner; it is reversible either way.

**UPDATE 09:15 — TWO OF THE THREE GATES ARE PASSED, AND THE THIRD IS YOURS.**

- **Stillness: PASSED, and derived.** 0.41 mm/frame against a 2 mm limit, and the
  motion that used to GROW is gone — 10.9 in the first second, then settling under
  1.4. The hem guide cured it.
- **Hang: PASSED.** 8 folds at every height, depth 99–100%, flare 1.00, bulge 1.00.
- **Pile: YOURS TO JUDGE, and Soft goods refused to call it a pass.** The heap is
  the right size and shape — height 0.91, depth 1.16, width 1.11, layers 0.82,
  all inside 25% of the fall you approved. **But its creases are 1.58× coarser,
  and that IS visible from the stalls:** crease spacing goes from about 80 px to
  130 px in a 45 px band at the lip. Tens of pixels, not the one or two where
  stillness lives.

**Why this one comes to you rather than being settled by a number: the pile is
judged against the fall you already approved, and you did not approve a number —
you approved an image.** The 25% tolerance has no derivation, and Soft goods said
so rather than hiding behind it. A side-by-side of the two piles at the stalls
camera's framing is being made for you.

**Recommendation: look at the two piles before spending more bakes on it.** There
is a real possibility that the hem guide — the thing that cured the stillness — is
also what coarsens the creases, in which case this cloth may not be able to have
both, and that is a cleaner thing to know than another night of bakes.

**One honest caveat on the 1.58×, raised by Soft goods against their own result:
every pile comparison today is ONE run against ONE run, and a falling cloth is
chaotic. The noise floor has never been measured.** If re-running the same recipe
with a different seed moves fold size by 25% on its own, then the tolerance is
measuring nothing and 1.58× is partly luck. That test is running now, with its
thresholds written down before it started. **So treat the pile numbers as
provisional until it reports** — the stillness and hang results are unaffected,
because a trend measured over 30 s is not a single-draw artifact.

**UPDATE 09:40 — THE FOUR AMOUNTS ARE IN, AND THE RECIPE ALREADY BAKING MAY
SIMPLY PASS.** Fold size against the approved fall: 0.4 → 1.51, **0.6 → 1.12**,
**0.8 → 1.08**, 1.0 → 1.58. **As single runs, 0.6 and 0.8 pass the pile test on
all five numbers** — and 0.6 is the amount already baking. Stillness 0.41 and a
perfect hang at every amount.

**Two honest qualifications.** The pre-registered verdict is **INCONCLUSIVE**: the
curve is U-shaped rather than flat or monotonic, so the switch amount is not
reported as a lever even though 0.6 looks best. And **0.6 was a guess that held,
not a choice made on evidence** — it was picked speculatively hours before these
numbers existed. Whether 0.6 and 0.8 really pass still rests on the seed repeat.

**What this means for you: there is a real chance the pile question resolves
itself before you have to judge it.** If the seed repeat says single runs are
trustworthy, the cloth passes all three gates on numbers and the comparison image
becomes confirmation rather than a decision. If it does not, the picture is
waiting and the call is yours as described above.

### A4. Nesting the five hangars
Rig has authored the rises and placed five Arrival actors for Scenes 1, 2, 3, 5, 6.
**All inert, nothing nested, the Show asset byte-identical to its backup.**
Nesting is the switch that makes them live, and it is yours.

**THREE OF THE FAULTS YOU REPORTED ARE THIS ONE DECISION, not three problems.**
Verified by read-back: only Scene 4 is nested. So —
- *"P05's hangar movement does not play"* — Scene 5 is not nested.
- *"the next hangar after P06 also does not play"* — Scene 6 is not nested.
- *"Space does nothing at P01's lattice-light-dark-bg moment"* — Scene 1 is not
  nested. An unnested hangar rests at −90° in its pit with its bulb **meshes**
  still emissive, which is exactly the few unmoving points of light you saw.

**Nothing needs building before nesting. The rises, Arrivals and records are
ready and waiting on your word.** Everything else in your transition list is
transport, which is the item below with nobody on it.

**Recommendation: nest once a drape passes acceptance** — `final13` is due about
15:30. The rise start is currently a transplanted number (see B1), so the first
3.6 s of rise would otherwise show with nothing in front of it. Wait for the cloth and the
question never arises live.

---

## B. RIG'S THREE FLAGGED JUDGEMENTS — he separated these out himself

### B1. The rise start is a GUESS at all five sites
−3.567 s is Scene 4's applied RISE start, transplanted. (Corrected ~17:55 by Rig: P04's cloth releases at −3.874, 0.3 s earlier. Before the cut the Arrival drives the root; Sequencer plays the Scene only from frame 0.)
**~17:58 Gary chose the shared window at S4:** the rise runs with the cloth over ~10 s, the lights and exposure ramp across the same window, and they also dim from the cloth itself (patch P, C++, next build). No
backcloth exists in those passages, so **the first 3.6 s of rise shows with nothing
masking it.** Not a timing number — it is "you can see the machinery".
**Recommendation:** leave provisional; set each start from its own passage's cloth
release once a bake passes. Formula is in place: start = cross − lead, every
passage ends at 2.50 m/s.

### B2. Scene 5 is not too fast. It is UNSEEN — and that is a different problem
**You have the picture** (`RiseSpeed_S5_vs_S4_Sheet.png`), and it overturns the
way I put this to you an hour ago.

**I framed this as "the far wall peaks near 12 m/s against Scene 4's 7 — thrilling
or absurd?" That was the wrong measure and the answer is neither.** From the stop
the cat is nearly ON the hinge, so the eye reads the **sweep**, not the far wall's
linear speed: **4.7°/s against Scene 4's 6.9°/s.** Scene 5 therefore reads about
**1.5× SLOWER and heavier** than Scene 4, which for a box four times the size is
right. The 12 m/s is real and happens 150 m away, where it registers as a streak.
The sheet shows it directly with a 1-second exposure at each rise's fastest moment.

**So the K law is vindicated, and the real finding is elsewhere: from where the cat
stands, Scene 5's rise is mostly invisible.**

**Corrected at 08:30 — the first numbers compared mismatched phases.** Measured
from the stop at Scene 4's beats scaled by K, and there is a second sheet for it
(`WhyS5Dark_Sheet.png`):

| Phase | Scene 4 lit | Scene 5 lit |
| --- | --- | --- |
| landed | 1.0% | 1.2% — the same |
| uplights on | 20.7% | **2.8%** |
| roof shut | 20.7% | **2.8%** |
| end | 24.0% | **4.9%** |

**So Scene 5 is 5–7× darker, not 17×.** On the floor half of the frame alone it is
20.6% against 2.0%. It is also black from the stop until about 12 s.

**The why, in a picture rather than a number:** Scene 4's lights sit metres from
surfaces the cat sees, so light fills the frame. Scene 5's walls are 100 m to each
side and the far wall 150 m, so the same rig hangs as **points and cones in a
void**. The sheet's last panel brightens the frame by 6.6 stops — measured from
the pixels, not assumed — and shows the floor is there and unlit except under the
ghost light. **The rig scaled in number; its distance to anything the cat can see
scaled too.** That is why scaling cannot fix it. If you take the lattice glow for
Scene 4 (A2), it scales here to 6.3–12.6 s.

**Recommendation: accept the rise; treat Scene 5's lighting as its own job.** It
is Tier 3 work, not a rise problem, and it is now measured rather than suspected.

### B3. Scene 6's roofless rise — and a question about Scene 4's roof
**You have the picture** (`RoofBeat_S6_vs_S4_Sheet.png`), 12 s to 29 s.

**From outside, Scene 6's empty roof beat is a missing piece.** The frame changes
**0.00%** between 18.5 and 24.5 s: a landed box and nothing, with light escaping
upward through the open top. If you want that beat to be a held breath rather than
an absence, it needs something to happen in it.

**But from the cat's position it is nearly a non-event — and so is Scene 4's.**
This is the finding Rig went and got without being asked, and it is the more
interesting half:

- Scene 4's roof, seen from the stop on a 25° look-up, shows only as **a glint
  around 22.5 s** and a faintly lit ceiling behind the lattice at 24.5 s — **at
  most 3.7% of the frame**. On a level look it never enters frame at all.
- **Once shut, Scene 4 and Scene 6 are the same frame from inside: 0.4% of pixels
  differ.**

**So the real question is yours and it is about Scene 4, not Scene 6: does the roof
beat need to read from the cat at all?** If yes, Scene 4's roof needs help too and
this stops being a Scene 6 item. If no, then Scene 6's missing roof costs nothing
where the audience is looking, and only matters from outside — which nobody sees.

**Also visible on the sheet:** at 12 s Scene 6 is still rising **through its flat
ground plane**. That is the known S1/S5/S6 fault, now with a picture of it.

### B4. The hangars rise through the ground at FIVE sites, not three
Found by two read-only surveys. **Two different mechanisms, so two different
jobs** — and Rig's own note is that their builder allowed all five by name, so
these were deferrals rather than misses.

**The three PLANES — S1, S5, S6 — are DONE AND VERIFIED. [conductor approved]**
`PlaneTrim_S6_BeforeAfter.png` is the proof, and one step reverts it.

**The fault was worse than "sunk in the ground".** Mid-rise, the floor plane
**sliced the box, leaving a seam across the lattice** — so if you take the lattice
glow in A2, this trim removes a fault that decision would have lit up. At +8 s
from the stop, 8.2% of the frame changed and the interior now reads whole into the
pit; from outside at 12 s the box hangs in the void past the floor's edge, like
Scene 4, instead of sunk in ground.

**My "dark either way" was tested, not assumed:** from the stop the frame changes
**0.00% at the cut, 0.03% at +4 s, 0.01% after landing.** The only visible
difference is the fix itself.

The mechanics, for the record:
Each Passage's hand-placed floor plane runs on past the Passage end: S1's by
**399 m**, S6's by 139 m, S5's by 16 m. Nothing stands on any of them beyond the
hinge line. The fix ends each plane AT its hinge line, exactly as P04's Structure
Ground already does — void beyond, the box hanging in it. **The near end is
untouched, so the Passages themselves do not change.** I approved this as
conforming three sites to a convention P04 already sets, not as a new look:
reversible, backed up, with a revert script. **Say if you disagree and it comes
straight back out** — the visible change is that ground beyond the stop becomes
void, which at show exposure is dark either way.

**The two LANDSCAPES — S2, S3 — are NOT approved and are waiting for you.** S2's
forested landscape covers its whole footprint at hinge level; **S3's wet ground
sits 1.2 m ABOVE its lowered hinge**, so that box rises through terrain where your
cast is standing. A landscape cannot be shortened — it needs a hole.

**INVESTIGATED 11:00, and it changes what the job is: this CANNOT BE SCRIPTED.**
The two engine calls it needs are not exposed to Unreal Python (verified in the
headers, no `UFUNCTION` on either). So it is an **editor-mode manual job, or
someone writes a C++ helper first** — not a script anyone can run. Deleting whole
landscape components instead is far too coarse: they are 63–67 m wide. And
**eight skeletal actors stand on the landscape at P3**, which is the site where a
bad edit shows up in a scene you care about. It touches the P02 and P03
environments, and **no stream currently owns those**.
**Recommendation: yes in principle, but say who owns it**, and let it be a
daylight job rather than an overnight one. Previously recorded as S3 being "built
around its cast", which undersold it.

### B0. THREE SCENES ARE SHORTER THAN THEIR HANGAR RISES — blocking, and new
**Nesting is done at Scene 1 and refused at Scenes 2, 5 and 6, correctly.** The
Show says every scene is 15 s, but the compiler follows each Scene **sequence's**
playback range, and those three are still 15 s while their rises are 31, 49 and
31 s. Scene 1 is 210.8 s and Scene 3 is 65.5 s, so both fit; Scene 4 was
lengthened to 31 s by hand to host its hangar.

**What nesting them as-is would do:**
- **S2 and S6** — cut at **−0.7°**, a fraction short of landing, with **none** of
  their light, roof or lattice beats, which start at 16.5 s.
- **S5** — cut **mid-rise at about −24°.**

The apply script refuses rather than truncating silently, so nothing is broken;
it is simply waiting.

**Your options:**
1. **Lengthen Scenes 2, 5 and 6** to 31 / 49 / 31 s, as Scene 4 already was.
   **THE REASON THIS WAS BEING HELD HAS GONE.** It was held because the Master
   was believed 425 s out of step from Scene 3 onward, making the two repairs one
   job. **The suite's own `SavedMasterMatchesShow` test passed at 11:06 today with
   zero failed assertions** — it compares every Master subsection against the
   Show-compiled segment to 0.05 s, so that discrepancy cannot still exist. **The
   Master and the Show agree.** The staleness was repaired at some point and
   nobody noticed, because that test only logs when it fails.
   So this is now an ordinary job through the gated script, and the remaining
   care is the opposite of what it was: **a rebuild now has a correct Master to
   preserve, not a broken one to fix.**
2. **Accept a truncated fold** at those three.
3. **Compress those hangars' beats into 15 s**, which is a look change to the
   rise itself.

**Recommendation: (1), but not today and not piecemeal.** It is the same
timeline that the stale Master sits on, and doing it twice would be worse than
doing it once.

**Meanwhile, the transplanted start now has a picture** (`Captures/S1Transplant/`).
From the cat's approach it is much milder than the number suggested: nothing
visible until −2.5 s, then three lattice bulbs rising in a dark pit, peaking at
**1.7% of the frame** around −1.0 s as the box's mouth frame breaks the far floor
line. **It reads as lights rising in a pit and a silhouette at the horizon, not
as the box arriving early.** Whether that is acceptable is yours, but it is no
longer a number.

### A3b. THE CURTAIN DOESN'T MASK THE TOP — and at the Opening it's bright
**You have both pictures.** Rays cast from the stalls seat through every other
pixel, against the baked cloth and the real colliders: **4,132 samples get past
the top of the curtain**, forming a **21-notch comb** — one V per upstage pleat
trough, about 58 px tall.

**The cause is the pleats themselves.** The heading is pinned at 10.20 m; the
header's underside is at 10.50. Where a pleat swings up to 40 cm **upstage**,
behind the header's back face, a sightline clears the curtain and still passes
under the beam. **The pleating that makes the hang good is what opens the gap.**

**It only matters at one mouth, and it is the worst one.** Overlaying the notches
on the no-drape view:

| | mean / p99 |
| --- | --- |
| **Opening (P01)** | **28 / 146 — bright**, on the lit gilded relief |
| Interaction 1 (P02) | 6.6 / 118 — dark but for a green lantern |
| Interactions 2–4 | p99 10–15 — invisible |
| Interaction 5 | p99 22 — faint |

**So this is not "the curtain leaks". It is "the first image of the show has a row
of bright slots above the curtain"** — at the moment the audience is most
attentive and least able to explain what it is seeing. **It is already live**: the
current Opening drape has the same comb, plus the side wedges and lifted hem of
the known hold-still fault.

**Bottom edge: masked.** Sides: the known leak the 18.8 m track fixes.

**THE ANSWER IS A BORDER, AND IT IS MEASURED: 0 RAYS, WITH THE CLOTH UNCHANGED.**

A border 5 cm thick, hung **upstage of the heading** (x +45 to +50 cm) with its
**bottom at 10.20 m** — 30 cm below the header underside, level with the drape's
own heading — lets **not one ray through**, including the post-corner slivers. At
10.35 m, 157 leak. **So 10.20 is the number, with margin.**

**Upstage is what makes it work without hiding anything.** A border hung
*downstage* would have to come down to 9.65 m to mask — and that **hides the top
55 cm of the curtain.** At 9.90 it leaks 1,104 rays. **The border goes BEHIND the
heading, not in front of it.**

**Why this beats the alternatives:**
- **No bake.** The cloth stays exactly as approved — the fall and the pile you
  signed off are untouched.
- **It fixes the class.** Any future drape, at any drop, is masked by the
  architecture rather than by being tall enough.
- **It is what a theatre does.** A house masks the top of its opening with a
  border; it does not make the house curtain taller.
- **It is more of what you have asked for all week** — *"more scaffold/rig
  structure"*, *"situated inside a stage structure, not just under an open sky"*.
  **A border is stage structure doing a job.**

**SO THE BORDER CAN MOVE — but only in some directions, and one is closed.** This
paragraph was wrong in an earlier version of this sheet, which said the geometry was
"spoken for". **Corrected 30 Sep evening, by the stream that made the original
measurement.**

**To TOUCH the hang the border must overlap it on BOTH axes at once** — moved more
than **5.9 cm downstage** *and* lowered. Either alone clears it. The hang reaches
**x ≤ +39.1 cm** against a border face at **+45**; its top reaches **z ≤ 1019.98**
against a border bottom at **1020**. **The 0.2 mm vertical coincidence therefore
only matters if the border has already been moved downstage into the pleats' depth**
— on its own it is not a constraint.

| move it | what happens | tier |
| --- | --- | --- |
| **bottom DOWN**, at its current x | **clear of the hang AND of the fall, as far down as about 8.1 m.** Inside the border's footprint the cloth's highest reach in any of 331 frames is **z 812.5 cm**, at frame 501, as the falling cloth swings upstage 0.7 s after release | measured, every vertex, all frames |
| **UPSTAGE** | more clearance, **and it still masks** with the same bottom, since sightlines over the drape top keep rising. **Its top must rise with it** — sightlines under the header reach about **10.69 m at x +50**, higher further back | measured records, geometry inferred |
| **DOWNSTAGE more than 5.9 cm** | fine **only if the bottom stays at or above 1020** | measured |
| **bottom UP** (10.35 m) | **157 rays leak — the comb returns.** **This is the one closed direction.** | measured |
| **removed** | **4,105 rays** | measured |

> **In one line: the border can move upstage, or its bottom can come down as far as
> about 8.1 m. It cannot go up.** Plus its material, which is fully free.

**THAT 2.1 m OF HEADROOM IS AN OPPORTUNITY RATHER THAN SLACK, and it connects to
something you have asked for twice this week.** You wanted *"more scaffold/rig
structure to make the lattice more heavy looking"*, and the passage to feel
*"situated inside a stage structure, not just under an open sky"*. **A deeper border
is stage structure doing a job** — and it is now measured as free to take rather
than a risk to manage.

**The trade, stated plainly, because it is real.** While the curtain is up the border
shows only as **black through the notches between the pleat crests** — which is its
whole job, and is what replaced the bright slots (**p99 77 in that band**, measured).
**Lowering it does not change that**: the extra depth hangs upstage at x +45..+50
behind a drape covering the full height, so the notch band still reads the same
black. **What changes is after the fall. The border's bottom edge becomes the top of
the apparent stage opening** — so lowering it does not hide the curtain, **it lowers
the proscenium**, permanently, in every Scene seen through that mouth.

**So the question is not "how much clearance is safe". It is "how high should the
opening read".** A look decision with no engineering cost attached to either answer.

**The clearance was designed from the BORDER's side, not the cloth's** — the cloth
never knew the border existed. **final13's bake ran against 18 collider boxes with
no border** (its own launch log, measured); the border was added to the collider set
at 14:52 as box 19. x +45 was chosen in the ray test to clear final9's +40.7 cm
pleats, and Rig built exactly that. **So it fits this cache and was meant to — but
it is not a constraint the cloth respects, it is a gap two records agree on.**

**THE THREE ALTERNATIVES TO THE BORDER, NOW ALL COSTED, so this is a complete choice
rather than an open one:**
- **(a) accept the comb** — bright slots at the Opening, **p99 146/255** (measured
  on the no-drape capture). This is the fault as you saw it.
- **(b) a 0.5 m longer drop** — masks on final9's hang with the masks shifted up,
  **not on a real bake**, and **the fall changes.** Four to five hours.
- **(c) a downstage border down to 9.65 m** — masks (measured), but **hides the top
  55 cm of the curtain.**

> **So your border question is: keep the border, or pick one of those three. Not
> "keep or remove" — removing it is (a).**

**A BLIND SPOT FOUND AND CLOSED, approved under the delegation rather than sent to
you**, since it is offline tooling and mutates nothing: until this evening a border
edit would have been reported as *"the stage changed"* while the cloth quietly
intersected it. **A stage-clearance gate now counts cloth vertices inside every stage
box, every frame, recast whenever the stage bytes change** — so a border edit reads
*"the cloth intersects Portal border at frame N"*. **It is now a REQUIRED gate**, and
it has already done its second job: **it is what measured the 8.1 m figure above.**

**Non-contact boxes (border, header, posts) must hold ZERO vertices.** final13
against the current stage: **zero, in all 331 frames, hang and fall.** **Contact
surfaces (floors, lip, fascia, returns, lamp housings) must not be penetrated deeper
than 1.0 cm — which is not a number somebody picked, it is the cloth's own collision
margin — and the measured depth is recorded in every verdict**, so drift shows as a
number moving rather than as a pass against a chosen threshold. final13's deepest
contact: **0.12 cm into the stage floor**, one vertex, frame 518.

**One trap the gate caught on itself, and this is the more useful lesson:** its first
run tested the 16 lamp housings as axis-aligned boxes and reported a **13.6 cm
penetration that did not exist** — the housings are rotated. They are now tested as
exact oriented boxes, validated against the file's own bounds to within 0.065 cm.
**A gate whose first act is a false red is a gate nobody obeys.**

**final13 has been re-judged and passes all six gates** — still, hang, coverage,
top_masked, stage_clear, and the pile by recorded override — now carrying the
LF-normalised stage hash, so the import's stage check matches again.

**Also fixed today, and it explains a gate that would have cried wolf:** the
collider file's working copy is CRLF under git's autocrlf, so raw-byte hashing
called a line-ending-only change a "stage change". All four tools now hash
LF-normalised bytes, equal to git's blob hash. **That pins final13's bake to commit
`c467046` (v3) — which is how we know the border was not in it.**

### A1b. ANSWERED — the tilt goes, the height stays, and ONE NEW QUESTION opened underneath
**Gary, 30 Sep: *"the crossing pop needs to force the cat's bob to be straight at
that moment? but actually in that moment between passages, we don't need the cat's
bob at all"*, then *"no need to permanently tilt and the camera is at an ok height
as it is."*** Both halves ruled; the section is kept because what it uncovered is
not closed.

**RULED — the constant roll goes.** Roll is derived from lift at 0.12°/cm, and the
lift is always negative, so the horizon sat tilted 1–2.8° to the same side for the
length of every Passage. **A gait rolls one way and then the other; a constant roll
is a crooked camera.** Roll will be derived from the lift's deviation from its own
running mean instead of from its absolute value.

**RULED — the height stays.** The 7–23 cm ride below authored height during a walk
is accepted as the cat's crouch. **This forces the roll derivation rather than
merely permitting it**, since keeping a negative lift is exactly what produced the
constant tilt — the two rulings are one change.

**RULED — no bob between passages, and the reason is better than the mechanism.**
The bob is a walk cycle; between Passages the cat is not walking. So it is scoped
to walking rather than eased before a crossing. **The rig already has the signal it
needs** (`bIsMoving` from `CurrentShadowCatCameraSpeedCmPerSecond`,
`InfinityStageCameraRig.cpp:430-434, 508-516`) — `SampleShadowCatGaitLiftCm` simply
ignores it and samples the Spine whatever clip is playing, so the idle clip bobs too.

**AND THAT RULING CANNOT ACT, WHICH IS THE NEW QUESTION.** Measured from today's
PIE logs: at **both** crossings the camera is travelling at a constant **~250 cm/s
on the last frame before the cut** — 246–256 over P04's last 0.51 s, 244–255 over
P01's last 0.54 s. **The cat is legitimately still walking when the cut lands, so
gating the bob on the walk signal changes nothing there.**

**A SECOND JUMP NOBODY HAD NAMED, and it is the stronger argument:** 2.5 m/s to a
dead stop in one frame. Today it hides behind the tilt and the black; at 35 mm a
dead stop from walking pace reads as a **lurch** (inferred — there is no picture
for it yet).

> **THE OPEN QUESTION: the cat should come to a stop before the Scene begins. How
> long a settle?** One settle fixes both jumps — the walk ends, the bob fades with
> it, and the cut lands on a still, level view already at its authored height.
> **A picture sequence of the last 2 s will answer this better than a number**, and
> is queued behind the stutter test for the editor. Conductor's starting frame for
> that sequence, not a decision: **about 1 second** — a cat stops in a stride or
> two, not over two seconds, but an instant stop is the lurch above.

**THE MECHANISM QUESTION IS ANSWERED, AND THE ANSWER IS THAT THE SETTLE IS FREE.**
It was neither of the two worrying options. `EvaluateCamera` normalises the
SpeedMultiplier integral **within each span between pinned frames**, and a
Passage's start and end are always pins
(`MovieSceneInfinityPassageTrack.cpp:318-367`, declaration-proven). **So a settle
keyed into the last span still arrives at the end point exactly on the end frame:
no downstream cue moves, and the Entry camera picks up its geometry exactly where
it does today.** The lost distance is made up earlier in the same span — a 1 s
linear settle at 250 cm/s loses about 125 cm, which over a 20 s span is roughly
2.6% quicker beforehand (inferred arithmetic; real span lengths depend on each
Passage's pinned wings).

> **In plain terms, and this is how it should be put to Gary: the cat arrives at
> the same place at the same moment. It walks very slightly quicker beforehand and
> comes to rest over the last N seconds.** The ONLY thing "how long" decides is how
> much quicker — which is worth showing in the pictures too, since it is the entire
> cost.

**And the bob must then be weighted by SPEED, not by the walk/idle boolean.** The
boolean is `speed > KINDA_SMALL_NUMBER` and the walk clip's play rate scales down
to zero while keeping **full vertical amplitude** — it cycles slower, it does not
shrink. So a boolean gate would leave a full-size bob running until the final
instant of the settle. Weight = `saturate(speed / reference walk speed)`, smoothed.
With that, the camera ends the settle at its authored height — 180 at P04
(measured).

**No longer coupled to A1.** The pop was invisible only because the crossing is
black at the hangar's pinned exposure; with the settle it stops existing rather
than staying hidden, so A1 can be answered on its own merits.

**Not a build-window item** — runtime look, no patch, nothing held.

### A5. THE EXIT FROM A SCENE — the cost is now complete, and the cheap version is cheap
**You asked how the hangar leads you to the next passage. Two options were mocked
up for you; here is what each actually costs, with nothing left uncounted except
one question.**

**THE BLOCKER IS REAL AND NOW MEASURED, not modelled.** The live rise was posed
every 0.5 s and read: **Scene 1's roof crosses ground level 113.7 m out — 48.2 m
PAST its far wall.** Scene 5's is 100 m past. **So nothing can stand behind a far
wall while the roof sweeps up**, and any docked exit needs **a new roof beat**.
The live rise matches the model to 0.1 m.

**But you already know that beat barely reads**: at most 3.7% of the frame at its
peak, never in frame on a level look, and Scenes 4 and 6 differing by 0.4% of
pixels once shut. **So the climax you would be changing is one the audience
essentially does not see** — and two leaves sweeping sideways may read better
than a roof that currently arrives unnoticed. **Still yours; you have not seen
either.**

**THE CHEAP MIX — three places, two cloth cuts.** Dock only where the headings
already agree (S3→P04, S4→P05, S5→P06 are pure translations, no turn, no
relight); the two bent links stay cloth cuts. **What it costs, counted:**

| | |
| --- | --- |
| Passage + Structure actors to move | **6** |
| Camera rigs | **0 work.** They derive their transform from the route spline every evaluation, and the spline is attached to the Passage — so a moved Passage carries them, and authored camera offsets are in the route's frame so they follow too. |
| Scene handoff cameras | **One gated rematch per adjacent Scene**, minutes each — but **only AFTER the build**, or the clamp eats the hold again. |
| Transition stalls cameras | **One small re-seat script**, for moved mouths only. They are placed once, not derived, and the Interaction cuts bind them **as actors** — so they must be moved in place, never replaced. |
| Hand-placed actors (lanterns, stalls cameras, floors, liners, the backcloth) | **24**, none with children |
| Handoff cameras | 6, they regenerate |
| Hangar actors + Arrivals | 1,127 + 3, **rebuilt anyway for the new roof** |
| **World-space re-keys outside the hangars** | **ZERO** |

**The zero-re-keys row is the one that mattered.** The uncounted remainder was expected
to *"turn this into hours"*. It is **zero**. The full chain adds P02, P03 and
Scene 3's cast, five Scene 3 re-keys and the turns — **so the cheap mix is not a
compromise, it is most of the value for a small fraction of the work.**

**The image in it: a portal-sized panel falls outward as a drawbridge across the
pit onto the next forestage, and the cat walks out over it.** The fold vocabulary
in reverse.

**The alternative stays on the table:** one drape bake serves all five exits,
since every portal is the same size, plus one hangar stalls camera and one cut.
Nothing moves, the rise is untouched, **and the real cost is matching the light on
the cloth across the cut.** In Look & camera's phrase: *a trick, where the first
option is a place.*

### B0. AN AUTHORED WING SCORE ON P01 HAS NEVER PLAYED — restore it?
**Found by a read-only probe, 16:46.** Passage 1 carries **three keys on every
wing channel**:

- **InwardTravelScale** 0.5 → 1.3 → 1.0
- **CycleRateScale** 0.6 → 2.0 → 1.0
- **PhaseBias** 0 → 1 → 0

That is a tempo: the wings open slow and wide, accelerate to double rate, and
settle. **Every key sits between 0.0 and 14.52 s — and P01 does not start until
15.0 s.** So none of it ever plays. P01 holds the last values (1.0 / 1.0 / 0.0)
from beginning to end, and **nobody has ever seen this.**

**The likeliest cause is the 15 s Opening being inserted ahead of P01**, which
would have made 0–14.52 s P01's own first fifteen seconds. It is not a recent
regression, and it is not from any of today's work.

**Restoring it means shifting those keys +15.0 s — a precise number, not an
estimate.** The Opening is 375 frames at 25 fps, exactly 15.0 s, which is what
pushed P01 from 0 to 15.0. **Confirm against a pre-Opening Master backup before
shifting**, in case P01 has moved more than once. Reversible, small, and entirely
a look decision — it changes how the first passage's wings behave for its opening
fifteen seconds.

**A possible connection, offered as a possibility and not a claim.** You said
this morning that P01's flicker *"seems both expensive and not visually
effective"*, and P01 has recurred in your notes as wanting more happening in it.
**A tempo arc that has never once played is the kind of absence that reads as
monotony.** It is about wings rather than the lights you named, so this may be
unrelated — but it is authored motion the show has never shown.

### B0a. THE LANDSCAPES CARRY ~2,950 GRASS COMPONENTS — and that may be your load complaint
**You said:** *"P02 open curtain is OK although everything loaded at once and the
background loaded less than a second before the curtain, ruining the effect."*

**The two landscapes generate about 2,950 landscape-grass components** — 1,467 at
P02, 1,482 at P03 — and **landscape grass generates ASYNCHRONOUSLY around the
camera and pops in.** That is a much better candidate for a background arriving a
second late than anything else found today.

It was nearly missed: there are **no foliage ACTORS**, so an actor census reports
none. The grass is generated by the landscape itself.

**WHAT THIS CHANGES: the deletion stops being housekeeping and becomes a repair.**
It is currently staged as hide-first, with the irreversible delete held for your
eyes — and **hiding a landscape does not reliably stop its grass generating.** A
free check is running now to settle that: if the grass count is still ~2,950 with
both landscapes hidden, **only the delete fixes the pop-in**, and the case for it
is your own complaint rather than tidiness.

**Recommendation unchanged in shape, stronger in force: look at the hidden-and-
floored version, then approve the delete.** Everything reversible is already done.

### B0b. SCENE 3's CAST STANDS WHERE ITS HANGAR RISES — a staging decision
**At P03, and you called P03 the first place you would test characters with the
hangar.** The six "Shore" cast figures, the Celadon set and a light stand all sit
**inside the hangar's swept footprint** — which is why they are on its exemption
list.

**So the fix applied everywhere else cannot be applied here.** Cutting a pit-hole
in the floor under a rising box is what stops it slicing through the ground; at
S3 it would leave **your cast hovering over an open pit**, visible from the
approach, until the box lands beneath them.

**So S3 keeps a flat floor and keeps its existing behaviour: the box rises
through the ground there, as it always has.** That is a **knowingly retained
known fault**, not an oversight — recorded as such so nobody later reads it as
one. The lattice also sweeps through floor level near the cast, 28 to 62 m past
the hinge, which is inherent to how S3 is staged rather than new.

**The real fix is yours, and it is about the cast rather than the floor:**
1. **The cast rides the box floor up** — they are part of the machine, arriving with it.
2. **The cast appears at landing** — the box arrives empty and they are revealed in it.
3. **The cast moves out of the footprint** — the box rises beside them rather than under them.

Each is a different piece of theatre, not a different fix. Nothing will be done
at S3 until you choose.


### B0c. SUPERSEDED — P03 already HAS P01's stage front. One edit, and one small look question
**This section previously said the floors replacing the landscapes needed a stage
front built into them, or the shared cloth cache would die at five of six mouths.
Its premise was FALSE and is now measured false.** Kept because what replaced it is
a real, much smaller question.

**P03 ALREADY BUILDS P01's STAGE FRONT.** Structure 03's ground has been on since
12:25 today, and a read-only probe over the pile footprint, instance by instance,
with P01 read the same way as the reference, found from the curtain line:

| piece | extent | top | instances |
| --- | --- | --- | --- |
| forestage | x −150..0 | 0 | 89 |
| portal pieces | (lip trough) | to 25 | 3 |
| ground | 0..+906 | 0 | 139 |
| **StageFront — fascia and house floor** | | **−120..0** | **250** (P01 has 192) |
| understage | | −255 | |

**So the lip and the fascia are there.** The cache's site assumptions are met
upstage of the lip, and the pile lies on forestage and ground at z 0 exactly as it
does at P01.

### WHAT IS ACTUALLY WRONG: the oak plane buries the stage front

**`"Passage 03 - Floor"` — top −5.0, 1 cm thick — runs from 84 m DOWNSTAGE to 451 m
upstage.** In the house-side band (x −200..−155) **every sample's top surface is that
plane at −5**: it covers the house floor at −120 and **buries the fascia except its
top 5 cm.**

**At P01 the equivalent floor STARTS at the lip (x −150) and leaves the drop
exposed.** That is the whole difference between the two mouths, and it confirms Rig's
own worry, measured rather than suspected.

**Consequence for the drape at P03's mouth** (inferred from these surfaces plus the
cache's measured extents): the pile lies correctly on forestage and ground, but **the
spill down the fascia — which reaches z −71 — CLIPS INTO the oak plane at −5.** It
does not float. Plus a small cosmetic: **P03 has 2 lamp-housing fixtures in the
footprint against P01's 5**, so there are a few phantom dents where the pile drapes
over housings that are not there.

### THE FIX IS ONE RIG EDIT — no bake, no new stage front

**Trim `"Passage 03 - Floor"` to start at the lip** (x ≥ −150 from P03's route
start), as P01's floor already does. **Then P03's mouth matches P01's, the shared
cache fits, and the pending I2 check becomes the formality it was predicted to be.**
Upstage the plane is harmless — under ground at top 0, a plane at −5 is invisible.

> **THE ONLY THING LEFT FOR YOU, and it is small: should the house side at P03 read
> as a DROP, the way it does at P01 — fascia visible, house floor 1.2 m below — or as
> OAK FLOOR carried right through?** The measured difference is above. **A drop is
> what the cache was built for and what P01 does; oak through is what P03 has today,
> by accident rather than by choice.**

**"One asset feeds six sites" survives**, and per-site bakes are off the table.

### B5. A cloth can show a stale frame after a scrub — and it needs an owner
**Measured today, and it is a rehearsal problem rather than a performance one.** A
Geometry Cache decodes asynchronously: a jump requests a frame that is not
decoded yet, and the proxy keeps drawing its **last decoded** frame until
something requests again. Continuous playback re-requests every frame, so it
self-heals. **The damaging case is a jump followed by a HOLD** — scrub to a
moment, then pause and look — where nothing re-requests, so a fallen curtain can
keep drawing as a standing one **for as long as you are looking at it.**

**Use this today:** after scrubbing onto a cloth shot, **nudge the playhead one
frame** (or play a moment) before judging the cloth.

**The fix, and why it is not built:** an investigation confirmed UE 5.8 exposes
**no API** that waits for a decode to be presented — no completion event, fence
or presented-frame query. So the right fix is to have the transport re-evaluate
the current time once more a few frames after any jump. **That is
`InfinityStageTransportController`, which no session owns**, and it is core show
code. **Recommendation: name an owner** — or let Soft goods' cloth actor do it
locally, which is narrower and needs no transport change.

---

## C. THE REST — real, not urgent

- **Where does the traveller live?** You asked for the side-opening curtain as a
  second option to compare. All three current cloth sites FALL. If it has no site,
  `final12` is a comparison piece rather than a deliverable — fine, but it changes
  whether it needs siblings.
- **Floor A (continuous herringbone) vs C (dark waxed lacquer).** Now known to be a
  decision about **boards**: the grooves are invisible from eye height, measured at
  0.05% of pixels changed. `SlotInboardCm` (~380) is the real lever, not width.
  **~17:40 (Wing materiality):** you said "A seems good", then asked what the grooves
  are for. They're the chariot slots across the floor at each wing. **A is not yet
  confirmed.** Also yours: whether the slots should start further inboard, to read
  more as a feature. If you say A, it's ~30 min of editor for Wing, landing with Rig's
  steel groove in the post-build re-fit.
- **Flat V3 pilot: a mixed stage.** V3 flats carry baked poles, and the ~260 legacy
  cards have none until LegibleMachineSpec §2's follow exists. The pilot pair at P01
  would show both side by side. A look state, so yours (Rig, 30 Sep evening).
- **"Smudged in motion": a new suspect, unmeasured.** `InfinityStagePassageActor.cpp:1461`
  recreates each moving wing's render state every frame, right after supplying its
  motion history, which may discard its motion vectors (Rig: inferred plausible). An
  A/B with the call removed would settle it; it's a C++ edit, so it waits for a build
  window. It's also a candidate alongside the missing mipmaps on the wing textures.
  **Mipmaps re-verified ~17:45 (Wing materiality, read from the .uasset files): 367 of
  371 live wing textures across ALL six passages have NO mipmaps**, and 63 are also
  uncompressed. Inferred cause: the importer turns mips off for non-power-of-two
  images, and nobody chose it. A test on duplicates is queued (settings only, sources
  untouched). **Rolling it out to P01+P02 will come to you for your eye**, since only
  you can judge whether the smudge is cured.
- **Wing materiality, also yours:** P05 at full relief, flat clouds (HeightRatio 0,
  POM steps 1), or not yet; **which wings burn**; and **installing an upscaler**,
  which is a download, so your call.
- **Scene 3's four issues.** The lattice clip is now located precisely: Scene time
  **8.43–10.03 s**. Lights calibrated at the wrong EV; the ghost light lands among
  the cast; enclosure changes the open-sky lighting.
- **Scene 5's centre floor** needs a new element — work lights on rails — not a
  count.
- **Scene 3's true length**, and the robot's own body pitch range. The second is an
  operator measurement nobody else can take.
- **The ~1 Hz stutter.** Still unsolved, still unattached to a cause. Needs a
  re-record at your PC; deliberately deferred while four Blender bakes saturate the
  machine, because a loaded machine cannot measure a load.

---

## Done overnight, for context, not for decision

- **The suite is 90 passing / 0 failing / 90 total — green for the first time.**
  All six of yesterday's failures were **fixture** faults. Not one was a product
  fault.
- Five hangar rises authored and five Arrival actors placed, inert and reverted by
  script. **[conductor approved]** — reversible, backed up to
  `Backups/PreArrivalSequences-20260930-0652`, and the Show was not touched.
- Patch G3 approved to silence five expected log warnings and save 0.25 ms/frame.
  **[conductor approved]** — a log severity and an early-out, against a known-green
  baseline.
- The traveller's 21 mm/frame was **the two halves colliding**, not the cloth. A
  0.4 m track gap takes it to 0.06.
- The stillness limit now carries its derivation: one pixel is about 1.2 cm at the
  stalls camera, so 2 mm/frame is a sixth of a pixel. Your word "bouncy" measured
  out at 20 px of swim in a second.
